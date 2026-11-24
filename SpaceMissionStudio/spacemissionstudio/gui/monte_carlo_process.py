#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""The GUI's Monte Carlo batch, run in a child process.

Basilisk's ``MonteCarlo.Controller`` calls ``signal.signal()`` at the start
of every case, which Python allows only on a process's main thread. With
``thread_count`` 1 the controller runs each case in the calling process, so
called from the GUI's worker ``QThread`` every case failed with "signal only
works in main thread of the main interpreter". :func:`run_batch` runs
:func:`engine.monte_carlo.run_monte_carlo` in a spawned process instead,
where it runs on that process's main thread, as ``spacemissionstudio
monte-carlo`` does. With ``thread_count`` > 1 the controller's own process
pool starts from that child, as it did from the GUI process before.

The child's log records come back through a queue to the GUI process's
loggers (so the Log view and the log file get them as before); its stdout
and stderr are the GUI's. Importing this module imports no Qt and no
Basilisk: the child imports only what the batch needs.

A batch can be cancelled (audit G3): the controller has no way to stop
part way, so a thread in the child waits for a cancel event, then ends the
controller's own processes (its pool, data writer and manager) and the
child. The cases finished by then stay in the archive folder, and a second,
short child writes their summary for the Monte Carlo view.

**No process of a batch outlives it.** The cancel thread can end only the
processes that it sees when it starts. The controller's process pool
replaces a worker that ends, so it started a new worker while the cancel
thread ended the others, and that worker outlived the child: it waited for
work for ever, and it kept the resource tracker and the output of the
process that started the batch open (a test run that did not end,
2026-11-23; ``docs/DECISIONS.md``). So the child first makes a group of its
own (:func:`_own_process_group`): on Windows a job that ends every process
in it when the child ends; elsewhere a process group, which
:func:`run_batch` ends when the child has ended without a result
(:func:`_end_process_group`).
"""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing
import os
import queue
import signal
import threading
from pathlib import Path

_logger = logging.getLogger(__name__)

_POLL_S = 0.2  # [s] how often the waiting thread checks that the child is alive
_LAST_RESULT_S = 2.0  # [s] how long to wait for a result after the child has exited
_CANCEL_WAIT_S = 15.0  # [s] how long a cancelled child has to end its processes before it is terminated
_CANCELLED_EXIT = 3  # the child's exit code when it was cancelled
_JOB: list = []  # Windows: the batch child's job (kill on close), kept open until the child ends


class BatchProcessError(Exception):
    """The batch did not end with a result: the child raised something other
    than :class:`engine.monte_carlo.MonteCarloError`, or ended without one."""


class BatchCancelled(Exception):
    """The batch was cancelled; ``finished`` cases had ended by then (their
    files, and a summary when there is any, are in the archive folder)."""

    def __init__(self, finished: int) -> None:
        super().__init__(f"cancelled after {finished} finished case(s)")
        self.finished = finished


def _stop_on(cancel_event) -> None:
    """In the child: once ``cancel_event`` is set, end the processes the
    controller started from this one, then this process. A process started
    after the list was taken (the pool replaces the workers ended here) is
    not in it: the child's group ends that one (:func:`_own_process_group`)."""
    cancel_event.wait()
    children = multiprocessing.active_children()
    for child in children:
        child.terminate()
    for child in children:
        child.join(5.0)
    os._exit(_CANCELLED_EXIT)


def _own_process_group() -> None:
    """In the batch's child, before it starts any process: put this process
    and every process it starts, and theirs, in a group of their own.

    On Windows a job object that ends every process in it when its last
    handle closes, that is when this process ends (however it ends). On
    other systems a process group whose ID is this process's ID;
    :func:`run_batch` ends it (:func:`_end_process_group`). When the system
    refuses, the batch runs as before."""
    try:
        if os.name == "nt":
            _JOB.append(_kill_on_close_job())
        else:
            os.setpgid(0, 0)
    except OSError:
        _logger.warning("The Monte Carlo batch could not get a process group of its own: a cancelled batch can "
                        "leave a process running", exc_info=True)


def _kill_on_close_job():
    """Windows: a new job with ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` that
    holds this process; the processes it starts join the job too."""
    import ctypes
    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):  # 9: extended
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        raise ctypes.WinError(ctypes.get_last_error())
    return job


def _end_process_group(process) -> None:
    """In this process, once the batch's child ``process`` has ended: end
    every process of its group that is still running (not on Windows, where
    the child's job did that when the child ended)."""
    if os.name == "nt" or process.pid is None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):  # none is left (the usual case)
        pass


def _batch_main(target, *args) -> None:
    """The batch's child: its own process group first, then ``target``
    (:func:`_child`)."""
    _own_process_group()
    target(*args)


def failure_text(exc: BaseException) -> str:
    """What a worker reports for ``exc``. Basilisk's device factories call
    ``exit()`` (``SystemExit``) on settings they refuse, printing the reason
    first; ``str()`` of that is only the exit status."""
    if isinstance(exc, SystemExit):
        return (f"Basilisk stopped the run (exit status {exc.code}) on a setting it refuses; its reason is "
                "printed in the terminal and the log file")
    return str(exc) or type(exc).__name__


class _ToLocalLoggers(logging.Handler):
    """Hands each record from the child to the logger of the same name here."""

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


def _child(scenario, mc_config, archive_dir: str, allow_scripts: bool, overwrite: bool, log_queue,
           result_queue, cancel_event=None, scenario_file: dict | None = None) -> None:
    """The child process: the batch, then one ``(kind, value)`` result."""
    root = logging.getLogger()
    root.handlers[:] = [logging.handlers.QueueHandler(log_queue)]
    root.setLevel(logging.INFO)
    if cancel_event is not None:
        threading.Thread(target=_stop_on, args=(cancel_event,), name="cancel", daemon=True).start()
    try:
        from ..engine.monte_carlo import MonteCarloError, run_monte_carlo

        failures = run_monte_carlo(scenario, mc_config, archive_dir, allow_scripts=allow_scripts,
                                   overwrite=overwrite, scenario_file=scenario_file)
    except MonteCarloError as exc:
        result_queue.put(("error", str(exc)))
    except (Exception, SystemExit) as exc:  # noqa: BLE001 -- report ANY failure (Basilisk's exit() too) to the GUI
        logging.getLogger(__name__).exception("Monte Carlo batch failed")
        result_queue.put(("failed", failure_text(exc)))
    else:
        result_queue.put(("ok", [int(index) for index in failures]))


def _summary_child(scenario, archive_dir: str, num_runs: int) -> None:
    """A cancelled batch's summary, from the cases it finished (in a child,
    as the batch's own: the run files are pickles, read only by the process
    kind that had them written, security analysis S-04)."""
    from ..engine import monte_carlo, monte_carlo_results

    batch = monte_carlo.collect_batch(scenario, archive_dir, num_runs, [], scenario.monte_carlo.seed)
    batch.failed = []  # the cases not finished were stopped, not failed: the controller's own list is gone
    batch.failed_drawn = {}  # so their draws are not those of crashed runs (Monte Carlo plan A4)
    if batch.runs:
        monte_carlo_results.save(batch, archive_dir)


def _summarized_runs(archive_dir) -> int:
    """How many finished cases a cancelled batch's summary holds (0 when
    none finished, or it could not be written)."""
    from ..engine import monte_carlo_results

    try:
        return len(monte_carlo_results.load(archive_dir).runs)
    except monte_carlo_results.MonteCarloResultsError:
        return 0


def run_batch(scenario, mc_config, archive_dir: str | Path, allow_scripts: bool = False,
              overwrite: bool = False, should_cancel=None, scenario_file: dict | None = None) -> list[int]:
    """:func:`engine.monte_carlo.run_monte_carlo` in a child process: the
    indices of the failed runs (``scenario_file`` as there). Raises
    ``MonteCarloError`` with the batch's own message, or
    :class:`BatchProcessError`; :class:`BatchCancelled` when
    ``should_cancel()`` turned True (checked every 0.2 s). Blocks until the
    batch ends, so call it from a worker thread."""
    from ..engine.monte_carlo import MonteCarloError

    context = multiprocessing.get_context("spawn")  # a fresh interpreter: no Qt state forked into it
    log_queue = context.Queue()
    result_queue = context.Queue()
    cancel_event = context.Event()
    listener = logging.handlers.QueueListener(log_queue, _ToLocalLoggers())
    listener.start()
    process = context.Process(target=_batch_main, name="spacemissionstudio-monte-carlo",
                              args=(_child, scenario, mc_config, str(archive_dir), allow_scripts, overwrite,
                                    log_queue, result_queue, cancel_event, scenario_file))
    result = None
    cancelled = False
    try:
        process.start()
        while result is None:
            if should_cancel is not None and should_cancel() and not cancelled:
                cancelled = True
                cancel_event.set()
                process.join(_CANCEL_WAIT_S)
                if process.is_alive():
                    process.terminate()
                break
            try:
                result = result_queue.get(timeout=_POLL_S)
            except queue.Empty:
                if not process.is_alive():
                    try:  # the result can arrive just after the child exits
                        result = result_queue.get(timeout=_LAST_RESULT_S)
                    except queue.Empty:
                        break
        process.join()
        if cancelled or result is None:  # a process the child started may still run (see the module's docstring)
            _end_process_group(process)
        if cancelled:
            summary = context.Process(target=_summary_child, name="spacemissionstudio-monte-carlo-summary",
                                      args=(scenario, str(archive_dir), mc_config.num_runs))
            summary.start()
            summary.join()
    finally:
        listener.stop()
    if cancelled:
        finished = _summarized_runs(archive_dir)
        _logger.info("Monte Carlo batch cancelled: %d case(s) finished", finished)
        raise BatchCancelled(finished)
    if result is None:
        _logger.error("The Monte Carlo process ended without a result (exit code %s)", process.exitcode)
        raise BatchProcessError(f"The Monte Carlo process ended unexpectedly (exit code {process.exitcode}); "
                                "the terminal and the log file have its output")
    kind, value = result
    if kind == "ok":
        return value
    if kind == "error":
        raise MonteCarloError(value)
    raise BatchProcessError(value)

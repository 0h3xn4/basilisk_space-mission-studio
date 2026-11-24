"""TEMPORARY diagnostic for SRelD K-40 (the 3D View's move on the Windows
runner). It fails on purpose on Windows to print its measurements in the
CI log; it is removed before the branch is merged."""
import json
import os
import sys
import time

import pytest

from test_breakout import _isolated, _js, _with_run, unopened, window  # noqa: F401

pytestmark = pytest.mark.requires_gui
ROUNDS = 8


def _threads():
    """{thread id: (name, priority, cpu ms)} of this process (Windows only)."""
    if sys.platform != "win32":
        return {}
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class THREADENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ThreadID", wintypes.DWORD),
                    ("th32OwnerProcessID", wintypes.DWORD), ("tpBasePri", wintypes.LONG),
                    ("tpDeltaPri", wintypes.LONG), ("dwFlags", wintypes.DWORD)]

    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k32.OpenThread.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(4, 0)
    entry = THREADENTRY32()
    entry.dwSize = ctypes.sizeof(THREADENTRY32)
    out = {}
    pid = os.getpid()
    ok = k32.Thread32First(snap, ctypes.byref(entry))
    while ok:
        if entry.th32OwnerProcessID == pid:
            tid = entry.th32ThreadID
            h = k32.OpenThread(0x0800, False, tid)
            if h:
                prio = k32.GetThreadPriority(wintypes.HANDLE(h))
                c, e, kt, ut = (wintypes.FILETIME() for _ in range(4))
                k32.GetThreadTimes(wintypes.HANDLE(h), ctypes.byref(c), ctypes.byref(e), ctypes.byref(kt), ctypes.byref(ut))
                cpu = ((kt.dwHighDateTime << 32 | kt.dwLowDateTime) + (ut.dwHighDateTime << 32 | ut.dwLowDateTime)) / 1e4
                name = ""
                try:
                    p = ctypes.c_wchar_p()
                    if k32.GetThreadDescription(wintypes.HANDLE(h), ctypes.byref(p)) >= 0 and p.value:
                        name = p.value
                        k32.LocalFree(p)
                except (AttributeError, OSError):
                    pass
                k32.CloseHandle(wintypes.HANDLE(h))
                out[tid] = (name, prio, cpu)
        ok = k32.Thread32Next(snap, ctypes.byref(entry))
    k32.CloseHandle(wintypes.HANDLE(snap))
    return out


def _busy(before, after, top=12):
    rows = []
    for tid, (name, prio, cpu) in after.items():
        used = cpu - before.get(tid, (name, prio, 0.0))[2]
        if used > 0:
            rows.append((round(used, 1), name or str(tid), prio))
    rows.sort(reverse=True)
    return rows[:top]


def _moves(b, pe, qtbot, pause_ms=0, view_id="3d_view"):
    rows = []
    for _ in range(ROUNDS):
        for move in (b.detach, b.attach):
            c, t = time.thread_time(), time.perf_counter()
            move(view_id)
            rows.append((round(1000 * (time.perf_counter() - t), 1), round(1000 * (time.thread_time() - c), 1)))
            pe()
            if pause_ms:
                qtbot.wait(pause_ms)
    walls = sorted(w for w, _c in rows)
    return {"max": walls[-1], "median": walls[len(walls) // 2], "over50": sum(w >= 50 for w in walls),
            "cpu_max": max(c for _w, c in rows), "moves": rows}


def test_zz_windows_diagnostic_of_the_3d_view_move(window, qtbot):
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication

    from spacemissionstudio.gui.app import freeze_start_up_objects

    pe = QApplication.processEvents
    view = _with_run(window, qtbot)
    freeze_start_up_objects()
    b = window.breakouts
    window.show_view(view)
    pe()
    gui = QThread.currentThread()
    report = {"gui_priority": str(gui.priority()), "cpus": os.cpu_count(),
              "gl": _js(qtbot, view, "MV.glRenderer()"), "quality": _js(qtbot, view, "MV.quality"),
              "frame": _js(qtbot, view, "JSON.stringify(MV.benchmark(3))")}
    _js(qtbot, view, "MV._n=0; MV._r=MV.render; MV.render=function(){MV._n++; return MV._r.apply(this, arguments)}; 1")
    t0 = _threads()
    report["A_as_test"] = _moves(b, pe, qtbot)
    t1 = _threads()
    report["A_busy_threads"] = _busy(t0, t1)
    report["A_draws"] = _js(qtbot, view, "MV._n")
    report["all_threads"] = sorted({(n, p) for n, p, _c in t1.values()})
    report["B_pause_400"] = _moves(b, pe, qtbot, 400)
    gui.setPriority(QThread.Priority.HighPriority)
    report["C_gui_high"] = _moves(b, pe, qtbot)
    report["C_prio_read"] = str(gui.priority())
    gui.setPriority(QThread.Priority.HighestPriority)
    report["D_gui_highest"] = _moves(b, pe, qtbot)
    gui.setPriority(QThread.Priority.NormalPriority)
    _js(qtbot, view, "MV._render0=MV.render; MV.render=function(){}; 1")
    report["E_no_page_draws"] = _moves(b, pe, qtbot)
    _js(qtbot, view, "MV.render=MV._render0; 1")
    view.set_layout("map", remember=False)
    pe()
    report["F_map_layout"] = _moves(b, pe, qtbot)
    view.set_layout("globe", remember=False)
    pe()
    qtbot.wait(500)
    report["G_as_test_again"] = _moves(b, pe, qtbot)
    window.show_view(b.widget("thermal"))
    pe()
    report["H_thermal"] = _moves(b, pe, qtbot, view_id="thermal")
    text = json.dumps(report)
    print("K40DIAG " + text)
    if sys.platform == "win32" or os.environ.get("K40_DIAG_FAIL"):
        pytest.fail("K40DIAG " + text)

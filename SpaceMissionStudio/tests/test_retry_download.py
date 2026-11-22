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
"""CI's download steps run again after a failure (scripts/retry_download.py):
on 2026-11-22 the ITU server answered HTTP 404 for a few minutes and CI
stopped before any test."""

from __future__ import annotations

import http.server
import importlib.util
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = _ROOT / "scripts" / "retry_download.py"
_WORKFLOWS = _ROOT.parent / ".github" / "workflows"


@pytest.fixture(scope="module")
def retry():
    spec = importlib.util.spec_from_file_location("smstudio_retry_download", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_command_that_fails_twice_passes_on_the_third_attempt(retry):
    """Two failed attempts, a pause after each, then the command passes:
    the step passes."""
    statuses = iter([1, 1, 0])
    runs, pauses = [], []

    def run(command):
        runs.append(list(command))
        return next(statuses)

    assert retry.run_with_retries(["fetch"], attempts=4, pause_s=60.0, run=run, sleep=pauses.append) == 0
    assert runs == [["fetch"]] * 3
    assert pauses == [60.0, 60.0]  # [s] after each failed attempt, none after the passed one


def test_a_command_that_always_fails_still_fails_the_step(retry, capsys):
    """After the last attempt the step fails, with the command's own exit
    status: a download is never skipped."""
    runs, pauses = [], []

    def run(command):
        runs.append(command)
        return 3

    assert retry.run_with_retries(["fetch"], attempts=4, pause_s=5.0, run=run, sleep=pauses.append) == 3
    assert len(runs) == 4 and pauses == [5.0, 5.0, 5.0]  # no pause after the last attempt
    out = capsys.readouterr().out
    assert out.count("::warning::") == 3 and "::error::all 4 attempts failed" in out


def test_a_command_that_passes_runs_once(retry):
    """A download that works runs once, with no pause."""
    runs = []
    assert retry.run_with_retries(["fetch"], run=lambda command: runs.append(command) or 0, sleep=pytest.fail) == 0
    assert len(runs) == 1


class _FlakyServer(http.server.BaseHTTPRequestHandler):
    """Answers 404 to the first ``failures`` requests, then 200 (the outage)."""

    failures = 2
    answered: list = []

    def do_GET(self):  # noqa: N802 -- http.server's name
        status = 404 if len(self.answered) < self.failures else 200
        self.answered.append(status)
        body = b"data" if status == 200 else b"not found"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


def test_a_download_through_a_short_outage_passes(tmp_path):
    """The script, run as the workflows run it, against a local server that
    answers 404 twice and then the file: the third attempt downloads it."""
    _FlakyServer.answered = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _FlakyServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    target = tmp_path / "file.txt"
    fetch = ("import sys, urllib.request\n"
             "opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))\n"
             "open(sys.argv[2], 'wb').write(opener.open(sys.argv[1], timeout=10).read())\n")
    url = f"http://127.0.0.1:{server.server_address[1]}/file.txt"
    try:
        done = subprocess.run([sys.executable, str(SCRIPT), "--attempts", "4", "--pause", "0", "--",  # noqa: S603
                               sys.executable, "-c", fetch, url, str(target)],
                              capture_output=True, text=True, timeout=120)
    finally:
        server.shutdown()
        server.server_close()
    assert done.returncode == 0, done.stdout + done.stderr
    assert _FlakyServer.answered == [404, 404, 200]
    assert target.read_bytes() == b"data"
    assert done.stdout.count("::warning::attempt") == 2


def test_the_script_refuses_a_missing_command_or_no_attempt():
    """No command, or fewer than one attempt, is a usage error (status 2)."""
    for args in ([], ["--"], ["--attempts", "0", "--", "x"]):
        done = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,  # noqa: S603
                              timeout=60)
        assert done.returncode == 2, args


@pytest.mark.skipif(not _WORKFLOWS.is_dir(), reason="the repository's workflows are not here")
def test_every_reference_data_download_in_the_workflows_runs_through_the_script():
    """Each fetch step of SpaceMissionStudio's workflows, and the support
    data's first download (kernels-status in the test workflows), goes
    through the script. The release workflows' kernels-status checks that
    the installed package has the files (an empty cache) and downloads
    nothing, so it runs once."""
    found, missing = 0, []
    for path in sorted(_WORKFLOWS.glob("spacemissionstudio*.yml")):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            downloads = re.search(r"spacemissionstudio [a-z-]+ --fetch", line) or (
                path.name in ("spacemissionstudio.yml", "spacemissionstudio-sil-stress.yml")
                and re.search(r"spacemissionstudio kernels-status", line))
            if downloads:
                found += 1
                if "scripts/retry_download.py" not in line:
                    missing.append(f"{path.name}:{number}: {line.strip()}")
    assert found >= 9
    assert missing == []

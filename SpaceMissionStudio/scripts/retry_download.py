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
"""Run a reference data download again when it fails: CI's download steps.

On 2026-11-22 the ITU server answered HTTP 404 for the ITU-R P.676-13 data
file for a few minutes, and CI stopped before any test (SRelD issue 50). The
workflows therefore run each download through this script::

    python scripts/retry_download.py -- spacemissionstudio gaseous-attenuation --fetch

It runs the command; when the command fails, it waits ``--pause`` seconds
and runs it again, ``--attempts`` times in all. The exit status is the
command's: 0 as soon as one attempt passes, else the last attempt's status,
so a step still fails after the last attempt. Each failed attempt is logged
as a GitHub Actions warning. Standard library only; the same on Linux and
Windows.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Callable, Sequence

ATTEMPTS = 4  # three more after the first: about three minutes of pauses in all
PAUSE_S = 60.0  # [s]


def run_with_retries(command: Sequence[str], attempts: int = ATTEMPTS, pause_s: float = PAUSE_S,
                     run: Callable[[Sequence[str]], int] | None = None,
                     sleep: Callable[[float], None] = time.sleep) -> int:
    """Run ``command`` until it exits with 0, at most ``attempts`` times,
    ``pause_s`` seconds apart; return its last exit status."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    run = run or (lambda args: subprocess.run(list(args), check=False).returncode)  # noqa: S603 -- the workflow's own command
    status = 1
    for attempt in range(1, attempts + 1):
        status = run(command)
        if status == 0:
            return 0
        if attempt < attempts:
            print(f"::warning::attempt {attempt} of {attempts} failed (exit status {status}): "
                  f"{' '.join(command)}; again in {pause_s:g} s", flush=True)
            sleep(pause_s)
    print(f"::error::all {attempts} attempts failed (last exit status {status}): {' '.join(command)}", flush=True)
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a download command again when it fails.")
    parser.add_argument("--attempts", type=int, default=ATTEMPTS, help=f"attempts in all (default {ATTEMPTS})")
    parser.add_argument("--pause", type=float, default=PAUSE_S, help=f"[s] between attempts (default {PAUSE_S:g})")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="the command, after --")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("no command given")
    if args.attempts < 1 or args.pause < 0:
        parser.error("--attempts must be at least 1 and --pause at least 0")
    return run_with_retries(command, args.attempts, args.pause)


if __name__ == "__main__":
    sys.exit(main())

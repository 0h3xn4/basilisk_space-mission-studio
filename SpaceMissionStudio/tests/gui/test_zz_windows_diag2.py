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
"""TEMPORARY diagnostic for SRelD K-40, with the fix. It fails on purpose
on Windows to print its measurements in the CI log; it is removed before
the branch is merged."""
import json
import os
import sys
import threading

import pytest

from test_breakout import (_VIEWS, _isolated, _threads, _time_the_moves, _with_run, unopened,  # noqa: F401
                           window)

pytestmark = pytest.mark.requires_gui


def test_zz_windows_diagnostic_of_the_3d_view_move_with_the_fix(window, qtbot):
    import gc

    from PySide6.QtCore import QThread

    from spacemissionstudio.gui.app import freeze_start_up_objects

    _with_run(window, qtbot)
    freeze_start_up_objects()
    report = {"gui_priority": str(QThread.currentThread().priority())}
    before = _threads()
    runs = []
    try:
        for _ in range(10):
            took, _shown = _time_the_moves(window, _VIEWS)
            runs.append({view_id: round(max(times), 1) for view_id, times in took.items()})
    finally:
        gc.unfreeze()
    after = _threads()
    gui = threading.get_native_id()
    report["gui_os_priority"] = after.get(gui, ("", None, 0))[1]
    report["busy"] = sorted(((round(cpu - before[t][2], 1), name, prio) for t, (name, prio, cpu) in after.items()
                             if t in before and cpu > before[t][2]), reverse=True)[:12]
    report["slowest_move_per_run"] = runs
    report["max"] = {v: max(r[v] for r in runs) for v in _VIEWS}
    text = json.dumps(report)
    print("K40DIAG2 " + text)
    if sys.platform == "win32" or os.environ.get("K40_DIAG_FAIL"):
        pytest.fail("K40DIAG2 " + text)

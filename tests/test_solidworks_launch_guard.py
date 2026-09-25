"""The root conftest refuses every SolidWorks start from a test process.

Each refused call names a path that does not exist, and each assertion is on
the guard's own message, so a guard regression fails here instead of reaching
a real launch.
"""

import os
import subprocess
import sys

import pytest

BLOCKED = "SolidWorks launch blocked"
MISSING_SHORTCUT = r"X:\launch-guard-test\never-exists\SOLIDWORKS Design.lnk"


def _expect_blocked(refusals, call):
    # Never reach a real process or shell action, even on a guard regression.
    assert subprocess.Popen.__init__.__name__ == "guarded_init"
    assert os.system.__name__ == "guarded_system"
    with pytest.raises(RuntimeError, match=BLOCKED):
        call()
    assert len(refusals) == 1
    refusals.clear()


def test_shortcut_child_is_refused(solidworks_launch_refusals):
    """The SolidworksMCP-python launch shape: a child that os.startfile's a .lnk."""
    argv = [
        sys.executable,
        "-I",
        "-c",
        "import os, sys; os.startfile(sys.argv[1])",
        MISSING_SHORTCUT,
    ]
    _expect_blocked(
        solidworks_launch_refusals, lambda: subprocess.run(argv, check=False)
    )


def test_connector_launch_is_refused(solidworks_launch_refusals):
    command = r'"X:\never-exists\CATSTART.exe" -run "SWXDesktopLauncher.exe"'
    _expect_blocked(solidworks_launch_refusals, lambda: subprocess.Popen(command))


def test_taskkill_of_solidworks_is_refused(solidworks_launch_refusals):
    # A made-up image name: were the guard broken, taskkill would find nothing.
    argv = ["taskkill", "/F", "/IM", "sldworks-launch-guard-test.exe"]
    _expect_blocked(
        solidworks_launch_refusals, lambda: subprocess.run(argv, check=False)
    )


def test_os_system_is_refused(solidworks_launch_refusals):
    # echo, not start: were the guard broken, nothing opens.
    command = f"echo {MISSING_SHORTCUT}"
    _expect_blocked(solidworks_launch_refusals, lambda: os.system(command))


@pytest.mark.skipif(not hasattr(os, "startfile"), reason="os.startfile is Windows-only")
def test_in_process_startfile_is_refused(solidworks_launch_refusals):
    # Never call the real os.startfile, even on a guard regression.
    assert os.startfile.__name__ == "refuse_startfile"
    _expect_blocked(solidworks_launch_refusals, lambda: os.startfile(MISSING_SHORTCUT))


def test_unrelated_subprocess_passes(solidworks_launch_refusals):
    result = subprocess.run(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "ok"
    assert solidworks_launch_refusals == []

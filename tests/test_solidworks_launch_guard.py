"""The root conftest refuses every SolidWorks start from a test process.

Each refused call names a path that does not exist, and each assertion is on
the guard's own message, so a guard regression fails here instead of reaching
a real launch.
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

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


def _require_refuser(module, attribute, name):
    # Never reach a real COM activation or launch, even on a guard regression.
    assert getattr(module, attribute).__name__ == name, (module, attribute)


@pytest.mark.skipif(sys.platform != "win32", reason="pywin32 is Windows-only")
@pytest.mark.parametrize(
    "module_name,attribute",
    [
        ("win32com.client", "Dispatch"),
        ("win32com.client", "DispatchEx"),
        ("win32com.client.dynamic", "Dispatch"),
        ("win32com.client.gencache", "EnsureDispatch"),
        ("comtypes.client", "CreateObject"),
    ],
)
def test_com_activation_of_solidworks_is_refused(
    solidworks_launch_refusals, module_name, attribute
):
    """``SldWorks.Application``'s COM server is SLDWORKS.exe: a Dispatch starts it."""
    module = importlib.import_module(module_name)
    _require_refuser(module, attribute, "refuse_solidworks_activation")
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: getattr(module, attribute)("SldWorks.Application"),
    )


@pytest.mark.skipif(sys.platform != "win32", reason="pywin32 is Windows-only")
def test_com_activation_by_class_id_is_refused(solidworks_launch_refusals):
    import pythoncom
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CLSID"
        ) as key:
            clsid = winreg.QueryValue(key, None)
    except OSError:
        pytest.skip("SldWorks.Application is not registered here")
    _require_refuser(pythoncom, "CoCreateInstance", "refuse_solidworks_activation")
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: pythoncom.CoCreateInstance(
            clsid, None, pythoncom.CLSCTX_LOCAL_SERVER, pythoncom.IID_IDispatch
        ),
    )

    import comtypes

    _require_refuser(comtypes, "CoCreateInstance", "refuse_solidworks_activation")
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: comtypes.CoCreateInstance(comtypes.GUID(clsid)),
    )


@pytest.mark.skipif(sys.platform != "win32", reason="pywin32 is Windows-only")
def test_unrelated_com_activation_passes(solidworks_launch_refusals):
    import win32com.client

    _require_refuser(win32com.client, "Dispatch", "refuse_solidworks_activation")
    dictionary = win32com.client.Dispatch("Scripting.Dictionary")
    dictionary.Add("k", "v")
    assert dictionary.Count == 1
    assert solidworks_launch_refusals == []


@pytest.mark.parametrize(
    "module_name,attribute,args",
    [
        ("solidworks_mcp.adapters.sw_recovery", "start_solidworks", ()),
        ("solidworks_mcp.adapters.sw_recovery", "stop_solidworks", ()),
        ("solidworks_mcp.adapters.sw_recovery", "kill_connector_processes", ()),
        ("solidworks_mcp.adapters.sw_recovery", "recover_solidworks", ()),
        (
            "solidworks_mcp.adapters.sw_install",
            "launch_via_platform_shortcut",
            (MISSING_SHORTCUT,),
        ),
    ],
)
def test_solidworks_mcp_launch_entry_points_are_refused(
    solidworks_launch_refusals, module_name, attribute, args
):
    module = importlib.import_module(module_name)
    _require_refuser(module, attribute, "refuse_solidworks_launch")
    _expect_blocked(
        solidworks_launch_refusals, lambda: getattr(module, attribute)(*args)
    )


def test_autostart_is_off_unless_a_test_opts_in():
    assert os.environ.get("HARMONIC_SW_AUTOSTART") == "0"


def test_swallowed_autostart_launch_still_fails_the_test(
    solidworks_launch_refusals, monkeypatch
):
    """``_sw_lifecycle.ensure_ready`` swallows every exception.

    With autostart forced on and SolidWorks reported down it reaches
    ``start_solidworks``; the refusal it swallows must still be recorded, so the
    autouse teardown check fails the test.
    """
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "cad" / "scripts")
    )
    import _sw_lifecycle
    from solidworks_mcp.adapters import sw_recovery
    from solidworks_mcp.adapters.sw_recovery import SolidWorksState

    _require_refuser(sw_recovery, "start_solidworks", "refuse_solidworks_launch")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    monkeypatch.setattr(
        sw_recovery, "detect_state", lambda: SolidWorksState.NOT_RUNNING
    )

    assert _sw_lifecycle.ensure_ready() == "error"
    assert len(solidworks_launch_refusals) == 1
    assert "start_solidworks" in solidworks_launch_refusals[0]
    solidworks_launch_refusals.clear()

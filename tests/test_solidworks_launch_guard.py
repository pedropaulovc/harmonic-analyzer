"""The root conftest refuses every SolidWorks start from a test process.

Each refused call names a path that does not exist, and each assertion is on
the guard's own message, so a guard regression fails here instead of reaching
a real launch.
"""

import contextlib
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BLOCKED = "SolidWorks launch blocked"
MISSING_SHORTCUT = r"X:\launch-guard-test\never-exists\SOLIDWORKS Design.lnk"
REPO_ROOT = Path(__file__).resolve().parents[1]
# A COM build script that does not exist: were the guard broken, the child
# python would only fail to open it.
MISSING_BUILD = REPO_ROOT / "cad" / "scripts" / "build_tripwire_probe_never_exists.py"


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
        ("win32com.client", "GetActiveObject"),
        ("win32com.client.dynamic", "Dispatch"),
        ("win32com.client.gencache", "EnsureDispatch"),
        ("pythoncom", "GetActiveObject"),
        ("comtypes.client", "CreateObject"),
        ("comtypes.client", "GetActiveObject"),
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


@pytest.mark.parametrize(
    "argv,cwd",
    [
        ([sys.executable, str(MISSING_BUILD)], None),
        (
            [sys.executable, "cad/scripts/draw_tripwire_probe_never_exists.py"],
            str(REPO_ROOT),
        ),
        (
            [sys.executable, "build_tripwire_probe_never_exists.py"],
            str(MISSING_BUILD.parent),
        ),
        # verify.py exists in this checkout, so name one on a drive that does not.
        (f'"{sys.executable}" "X:\\never-exists\\cad\\scripts\\verify.py"', None),
    ],
    ids=["absolute", "relative-to-cwd", "bare-in-scripts", "command-line"],
)
def test_com_build_script_child_is_refused(solidworks_launch_refusals, argv, cwd):
    """The child every dodo COM task launches: python on a ``cad/scripts`` script."""
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: subprocess.run(argv, cwd=cwd, check=False, capture_output=True),
    )


def test_com_build_script_in_os_system_is_refused(solidworks_launch_refusals):
    command = subprocess.list2cmdline([sys.executable, str(MISSING_BUILD)])
    _expect_blocked(solidworks_launch_refusals, lambda: os.system(command))


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_a_program_that_only_reads_a_build_script_passes(solidworks_launch_refusals):
    """git hashes the file; only an interpreter or shell runs it."""
    result = subprocess.run(
        ["git", "hash-object", "--stdin", "--path", str(MISSING_BUILD)],
        input=b"probe\n",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert solidworks_launch_refusals == []


def _root_conftest(request):
    root = REPO_ROOT / "conftest.py"
    for plugin in request.config.pluginmanager.get_plugins():
        if Path(getattr(plugin, "__file__", "") or "").resolve() == root:
            return plugin
    raise LookupError(root)


_BUILD = str(MISSING_BUILD)


@pytest.mark.parametrize(
    "args,executable",
    [
        ([_BUILD], None),
        (["python", _BUILD], None),
        (["python", "-X", "utf8", "-u", _BUILD], None),
        (["worker", _BUILD], sys.executable),
        (subprocess.list2cmdline(["echo", "probe"]) + " & python " + _BUILD, None),
        (["cmd", "/c", subprocess.list2cmdline(["python", _BUILD, "--x"])], None),
        (["cmd", "/c", "python", _BUILD], None),
        (["uv", "run", "--with", "x", "python", _BUILD], None),
        (["uv", "run", _BUILD], None),
        (["pwsh", "-NoProfile", "-File", _BUILD], None),
    ],
)
def test_a_build_script_in_command_position_counts(request, args, executable):
    assert _root_conftest(request)._com_script(args, executable)


@pytest.mark.parametrize(
    "args",
    [
        ["git", "hash-object", "--path", _BUILD],
        ["certutil", "-hashfile", _BUILD, "SHA256"],
        ["uv", "run", "ruff", "check", _BUILD],
        ["python", "-m", "py_compile", _BUILD],
        ["python", "-c", "print(1)", _BUILD],
        ["python", "other.py", _BUILD],
    ],
)
def test_a_build_script_only_read_does_not_count(request, args):
    assert _root_conftest(request)._com_script(args) is None


@pytest.mark.skipif(sys.platform != "win32", reason="_winapi is Windows-only")
def test_create_process_below_popen_is_refused(solidworks_launch_refusals):
    """A ``Popen`` subclass or direct caller still meets ``_winapi.CreateProcess``."""
    import _winapi

    assert _winapi.CreateProcess.__name__ == "guarded_create_process"
    command = subprocess.list2cmdline([sys.executable, str(MISSING_BUILD)])
    with pytest.raises(RuntimeError, match=BLOCKED):
        _winapi.CreateProcess(None, command, None, None, False, 0, None, None, None)
    assert len(solidworks_launch_refusals) == 1
    solidworks_launch_refusals.clear()


@pytest.mark.skipif(sys.platform != "win32", reason="pywin32 is Windows-only")
def test_pywin32_process_creation_is_refused(solidworks_launch_refusals):
    import win32api
    import win32process

    assert win32process.CreateProcess.__name__ == "guarded_create_process"
    command = subprocess.list2cmdline([sys.executable, str(MISSING_BUILD)])
    with pytest.raises(RuntimeError, match=BLOCKED):
        win32process.CreateProcess(
            None, command, None, None, False, 0, None, None, win32process.STARTUPINFO()
        )
    assert len(solidworks_launch_refusals) == 1
    solidworks_launch_refusals.clear()
    for attribute, args in (
        ("ShellExecute", (0, "open", MISSING_SHORTCUT, None, None, 1)),
        ("WinExec", (f'"{sys.executable}" "{MISSING_BUILD}"',)),
    ):
        _require_refuser(win32api, attribute, "refuse_solidworks_launch")
        _expect_blocked(
            solidworks_launch_refusals,
            lambda attribute=attribute, args=args: getattr(win32api, attribute)(*args),
        )


@pytest.mark.skipif(not hasattr(os, "spawnv"), reason="os.spawnv is unavailable")
def test_spawn_of_a_com_build_script_is_refused(solidworks_launch_refusals):
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: os.spawnv(
            os.P_WAIT, sys.executable, [sys.executable, str(MISSING_BUILD)]
        ),
    )


@pytest.mark.skipif(sys.platform != "win32", reason="nt.startfile is Windows-only")
def test_startfile_below_os_is_refused(solidworks_launch_refusals):
    import nt

    # An unknown verb as well as a missing file: even unguarded, nothing opens.
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: nt.startfile(MISSING_SHORTCUT, "tripwire-no-such-verb"),
    )


@pytest.mark.skipif(sys.platform != "win32", reason="kernel32 is Windows-only")
@pytest.mark.parametrize(
    "library,symbol", [("kernel32", "CreateProcessW"), ("shell32", "ShellExecuteW")]
)
def test_ctypes_binding_of_a_process_launcher_is_refused(
    solidworks_launch_refusals, library, symbol
):
    import ctypes

    # Resolving the symbol is the refused step; nothing is ever called.
    _expect_blocked(
        solidworks_launch_refusals, lambda: getattr(ctypes.WinDLL(library), symbol)
    )


@contextlib.contextmanager
def _fresh_dodo():
    """A private dodo, loaded the way the recipe tests load it, without leaking
    its process-wide doit patches."""
    from doit.dependency import CHECKERS, Dependency, JsonDB

    save_success, json_dump = Dependency.save_success, JsonDB.dump
    checkers = dict(CHECKERS)
    try:
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module
    finally:
        Dependency.save_success, JsonDB.dump = save_success, json_dump
        CHECKERS.clear()
        CHECKERS.update(checkers)


def test_dodo_part_build_with_a_real_runner_is_refused(
    solidworks_launch_refusals, monkeypatch, tmp_path
):
    """dodo's part path: a cache miss with no farm reaches ``_exec_com``."""
    with _fresh_dodo() as dodo:
        assert dodo._exec_com.__code__.co_name == "refuse_com_task"
        monkeypatch.setattr(dodo, "LOGS", tmp_path / "logs")
        monkeypatch.setattr(dodo, "_part_cache_outputs", lambda _stem: [])
        monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [])
        monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
        monkeypatch.setattr(dodo, "_probe_cache", lambda *_a: "miss")
        monkeypatch.setattr(dodo._farm, "enabled", lambda: False)
        monkeypatch.setattr(
            dodo, "_com_seat", lambda _label: contextlib.nullcontext(0.0)
        )
        monkeypatch.setattr(dodo, "_reprobe_under_seat", lambda *_a: False)
        monkeypatch.setattr(dodo, "_sw_ensure_once", lambda: None)
        with pytest.raises(RuntimeError, match=BLOCKED):
            dodo._cached_part_action("ch_pivot_shaft", MISSING_BUILD)
        assert "dodo._exec_com" in solidworks_launch_refusals[0]
        assert not (tmp_path / "logs").exists()
        solidworks_launch_refusals.clear()

        with pytest.raises(RuntimeError, match=BLOCKED):
            dodo._run_subprocess(
                [sys.executable, str(MISSING_BUILD)], "part:ch_pivot_shaft"
            )
        assert "dodo._run_subprocess" in solidworks_launch_refusals[0]
        solidworks_launch_refusals.clear()

        # Faking only ``run`` leaves the logged path's real ``Popen``.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(dodo.subprocess, "run", lambda *_a, **_kw: None)
            with pytest.raises(RuntimeError, match=BLOCKED):
                dodo._run_subprocess(
                    [sys.executable, str(MISSING_BUILD)],
                    "part:ch_pivot_shaft",
                    "part-ch_pivot_shaft",
                )
        assert "dodo._run_subprocess" in solidworks_launch_refusals[0]
        assert not (tmp_path / "logs").exists()
        solidworks_launch_refusals.clear()


def test_dodo_com_paths_with_a_faked_runner_still_run(
    solidworks_launch_refusals, monkeypatch, tmp_path
):
    """The guard keys on the runner: a test that fakes it keeps the real logic."""
    ran = []
    with _fresh_dodo() as dodo:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                dodo, "_run_subprocess", lambda cmd, *_a, **_kw: ran.append(cmd) or 0
            )
            dodo._exec_com([sys.executable, str(MISSING_BUILD)], "part:ch_pivot_shaft")
        assert ran == [[sys.executable, str(MISSING_BUILD)]]

        class FakePopen:
            def __init__(self, cmd, **_kw):
                ran.append(cmd)
                self.stdout = iter(())

            def wait(self):
                return 0

        monkeypatch.setattr(dodo, "LOGS", tmp_path / "logs")
        monkeypatch.setattr(dodo.subprocess, "Popen", FakePopen)
        command = [sys.executable, str(MISSING_BUILD)]
        assert dodo._run_subprocess(command, "part:ch_pivot_shaft", "part-x") == 0
        assert ran[-1] == command
    assert solidworks_launch_refusals == []

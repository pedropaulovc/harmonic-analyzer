"""The root conftest refuses every SolidWorks start from a test process and,
through ``tests/_child_guard``, from every Python child it starts.

Each refused call names a path that does not exist, or reaches only an entry
point the guard has replaced, and each assertion is on the guard's own
message, so a guard regression fails here instead of reaching a real launch.
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
from harmonic_solidworks_guard import (
    MARKER,
    REFUSED_EXIT,
    guard_module,
    launches_solidworks,
)

# SolidWorks runs only on Windows, and the root conftest guards only there.
pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="SolidWorks runs only on Windows"
)

BLOCKED = "SolidWorks launch blocked"
MISSING_SHORTCUT = r"X:\launch-guard-test\never-exists\SOLIDWORKS Design.lnk"
MISSING_SOLIDWORKS = r"X:\launch-guard-test\never-exists\SLDWORKS.exe"
MISSING_PART = r"X:\launch-guard-test\never-exists\part.SLDPRT"
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


@pytest.mark.parametrize(
    "module_name,attribute",
    [
        ("win32com.client", "Dispatch"),
        ("win32com.client", "DispatchEx"),
        ("win32com.client", "GetActiveObject"),
        ("win32com.client.dynamic", "Dispatch"),
        ("win32com.client.gencache", "EnsureDispatch"),
        ("pythoncom", "GetActiveObject"),
        ("pythoncom", "Connect"),
        ("pythoncom", "CoGetObject"),
        ("comtypes", "CoGetClassObject"),
        ("comtypes.client", "CreateObject"),
        ("comtypes.client", "GetActiveObject"),
        ("comtypes.client", "GetClassObject"),
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


@pytest.mark.parametrize(
    "module_name,attribute,target",
    [
        # Classes that start any program: ShellExecute, Run/Exec, ExecuteShellCommand.
        ("win32com.client", "Dispatch", "Shell.Application"),
        ("win32com.client", "Dispatch", "WScript.Shell"),
        ("comtypes.client", "CreateObject", "MMC20.Application"),
        ("win32com.client", "Dispatch", "Schedule.Service"),
        ("win32com.client", "GetObject", "winmgmts:"),
        # ShellWindows has no ProgID.
        ("pythoncom", "CoCreateInstance", "{9BA05972-F6A8-11CF-A442-00A0C90A8F39}"),
        # A moniker naming a document activates the class that opens it.
        ("win32com.client", "GetObject", MISSING_PART),
        ("pythoncom", "MkParseDisplayName", MISSING_PART),
    ],
)
def test_com_activation_of_a_launcher_or_document_is_refused(
    solidworks_launch_refusals, module_name, attribute, target
):
    module = importlib.import_module(module_name)
    _require_refuser(module, attribute, "refuse_solidworks_activation")
    _expect_blocked(
        solidworks_launch_refusals, lambda: getattr(module, attribute)(target)
    )


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
        ("win32com.shell.shell", "ShellExecuteEx", ()),
        ("win32process", "CreateProcessAsUser", ()),
        ("win32service", "CreateService", ()),
        ("win32service", "StartService", ()),
        ("win32service", "ChangeServiceConfig", ()),
        ("win32service", "ChangeServiceConfig2", ()),
    ],
)
def test_launch_entry_points_are_refused(
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


def test_isolated_python_child_naming_solidworks_is_refused(
    solidworks_launch_refusals,
):
    """``-I`` skips the children's guard; the command line still meets this one."""
    argv = [sys.executable, "-I", "-c", "raise SystemExit('SldWorks.Application')"]
    _expect_blocked(
        solidworks_launch_refusals, lambda: subprocess.run(argv, check=False)
    )


# What a Python child of this session runs. Each binds or launches only through
# an entry point its guard has replaced: unguarded, it says so and exits rather
# than reach a real COM server or process. "SldWorks" is split so the parent's
# argv check does not refuse the child before its own guard is exercised.
_CHILD_BINDS_SOLIDWORKS = """\
import sys
import win32com.client

bind = win32com.client.GetActiveObject
if not getattr(bind, "solidworks_guard", False):
    print("UNGUARDED: the real win32com.client.GetActiveObject")
    sys.exit(3)
bind("SldWo" + "rks.Application")
print("NOT REFUSED")
sys.exit(4)
"""
_CHILD_LAUNCHES_SOLIDWORKS = """\
import subprocess

subprocess.run([r"X:\\launch-guard-test\\never-exists\\SLDWo" + "rks.exe"])
print("NOT REFUSED")
"""
# Resolving the symbol is the refused step; the child never calls it, so an
# unguarded child only prints and exits.
_CHILD_RESOLVES_A_LAUNCHER = """\
import ctypes

ctypes.WinDLL("kernel32")["Create" + "ProcessW"]
print("NOT REFUSED")
"""
# Each checks the entry point is the guard's wrapper first, and builds every
# name the parent's command-line check knows at runtime, so the child's own
# guard is what refuses.
_CHILD_SHELL_EXECUTES = """\
import sys
from win32com.shell import shell

if not getattr(shell.ShellExecuteEx, "solidworks_guard", False):
    print("UNGUARDED: the real ShellExecuteEx")
    sys.exit(3)
shell.ShellExecuteEx(lpFile="X:\\\\never-exists\\\\p.SLD" + "PRT")
print("NOT REFUSED")
"""
_CHILD_CREATES_A_SHELL_OPEN = """\
import _winapi
import sys

if not getattr(_winapi.CreateProcess, "solidworks_guard", False):
    print("UNGUARDED: the real _winapi.CreateProcess")
    sys.exit(3)
command = "c" + "md /c echo X:\\\\never-exists\\\\p.SLD" + "PRT"
_winapi.CreateProcess(None, command, None, None, False, 0, None, None, None)
print("NOT REFUSED")
"""
_CHILD_ACTIVATES_A_LAUNCHER = """\
import sys
import win32com.client

if not getattr(win32com.client.Dispatch, "solidworks_guard", False):
    print("UNGUARDED: the real win32com.client.Dispatch")
    sys.exit(3)
win32com.client.Dispatch("Shell.Appl" + "ication")
print("NOT REFUSED")
"""
# A dodo whose COM task reaches a stand-in ``_exec_com``.
_DODO_WITH_A_COM_TASK = """\
def _run_subprocess(cmd, label, log_stem=None, *, task=None):
    raise AssertionError("unreached")


def _exec_com(cmd, label, log_stem=None, *, task=None):
    print("UNGUARDED: the stand-in _exec_com ran")


def task_probe():
    return {"actions": [lambda: _exec_com(["probe"], "part:probe")], "verbosity": 2}
"""


def _expect_child_refused(child_refusals, result, route):
    output = f"exit {result.returncode}\n{result.stdout}\n{result.stderr}"
    assert BLOCKED in result.stderr, output
    assert f"via {route}" in result.stderr, output
    assert MARKER in result.stderr, output
    recorded = "".join(child_refusals())
    assert f"via {route}" in recorded, recorded


def _run_child(argv, **kwargs):
    return subprocess.run(
        argv, capture_output=True, text=True, check=False, timeout=120, **kwargs
    )


def test_python_child_binding_solidworks_is_refused(solidworks_child_refusals):
    result = _run_child([sys.executable, "-c", _CHILD_BINDS_SOLIDWORKS])
    _expect_child_refused(
        solidworks_child_refusals, result, "win32com.client.GetActiveObject"
    )
    assert result.returncode == REFUSED_EXIT


def test_python_child_launching_solidworks_is_refused(solidworks_child_refusals):
    result = _run_child([sys.executable, "-c", _CHILD_LAUNCHES_SOLIDWORKS])
    _expect_child_refused(solidworks_child_refusals, result, "subprocess.Popen")
    assert result.returncode == REFUSED_EXIT


def test_python_child_resolving_a_process_launcher_is_refused(
    solidworks_child_refusals,
):
    """A name built at runtime meets no argv check; the binding itself is refused."""
    result = _run_child([sys.executable, "-c", _CHILD_RESOLVES_A_LAUNCHER])
    _expect_child_refused(solidworks_child_refusals, result, "ctypes")
    assert result.returncode == REFUSED_EXIT


@pytest.mark.parametrize(
    "script,route",
    [
        (_CHILD_SHELL_EXECUTES, "win32com.shell.shell.ShellExecuteEx"),
        (_CHILD_CREATES_A_SHELL_OPEN, "_winapi.CreateProcess"),
        (_CHILD_ACTIVATES_A_LAUNCHER, "win32com.client.Dispatch"),
    ],
    ids=["shell-execute-ex", "winapi-shell-open", "launcher-class"],
)
def test_python_child_shell_open_is_refused(solidworks_child_refusals, script, route):
    result = _run_child([sys.executable, "-c", script])
    _expect_child_refused(solidworks_child_refusals, result, route)
    assert result.returncode == REFUSED_EXIT


def _root_conftest(request):
    root = REPO_ROOT / "conftest.py"
    for plugin in request.config.pluginmanager.get_plugins():
        if Path(getattr(plugin, "__file__", "") or "").resolve() == root:
            return plugin
    raise LookupError(root)


def test_a_child_refusal_the_test_ignores_still_fails_it(
    solidworks_child_refusals, request
):
    """The autouse check reads the children's log, whatever their exit codes."""
    result = _run_child([sys.executable, "-c", _CHILD_LAUNCHES_SOLIDWORKS])
    assert result.returncode == REFUSED_EXIT, result.stderr
    taken = _root_conftest(request)._take_refusals()
    assert any("via subprocess.Popen" in entry for entry in taken), taken


def test_doit_child_running_a_com_task_is_refused(solidworks_child_refusals, tmp_path):
    """``python -m doit part:x`` runs dodo's ``_exec_com`` in the child."""
    dodo = tmp_path / "dodo.py"
    dodo.write_text(_DODO_WITH_A_COM_TASK, encoding="utf-8")
    result = _run_child(
        [
            sys.executable,
            "-m",
            "doit",
            "-f",
            str(dodo),
            "--db-file",
            str(tmp_path / "doit.db"),
            "probe",
        ],
        cwd=tmp_path,
    )
    _expect_child_refused(solidworks_child_refusals, result, "dodo._exec_com")
    assert result.returncode == REFUSED_EXIT


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
def test_git_external_diff_binding_solidworks_is_refused(
    solidworks_child_refusals, tmp_path
):
    """git runs ``diff.external`` (or a textconv filter) as a child of its own."""
    repo = tmp_path / "repo"
    repo.mkdir()
    helper = tmp_path / "external_diff.py"
    helper.write_text(_CHILD_BINDS_SOLIDWORKS, encoding="utf-8")
    git = ["git", "-C", str(repo), "-c", "core.autocrlf=false"]
    subprocess.run([*git, "init", "-q"], check=True)
    (repo / "probe.txt").write_text("before\n", encoding="utf-8")
    subprocess.run([*git, "add", "probe.txt"], check=True)
    (repo / "probe.txt").write_text("after\n", encoding="utf-8")
    external = f'"{Path(sys.executable).as_posix()}" "{helper.as_posix()}"'
    result = _run_child([*git, "-c", f"diff.external={external}", "diff", "--ext-diff"])
    _expect_child_refused(
        solidworks_child_refusals, result, "win32com.client.GetActiveObject"
    )
    assert result.returncode != 0


def test_child_guard_runs_the_sitecustomize_it_shadows(
    solidworks_child_refusals, monkeypatch, tmp_path
):
    shadowed = tmp_path / "shadowed"
    shadowed.mkdir()
    (shadowed / "sitecustomize.py").write_text(
        "import os\nos.environ['SHADOWED_SITECUSTOMIZE_RAN'] = '1'\n", encoding="utf-8"
    )
    monkeypatch.setenv(
        "PYTHONPATH", os.pathsep.join([os.environ["PYTHONPATH"], str(shadowed)])
    )
    result = _run_child(
        [
            sys.executable,
            "-c",
            "import os, sys; print(os.environ.get('SHADOWED_SITECUSTOMIZE_RAN'),"
            " 'harmonic_solidworks_guard' in sys.modules)",
        ]
    )
    assert result.stdout.split() == ["1", "True"], result.stderr
    assert solidworks_child_refusals() == []


def test_create_process_below_popen_is_refused(solidworks_launch_refusals):
    """A ``Popen`` subclass or direct caller still meets ``_winapi.CreateProcess``."""
    import _winapi

    assert _winapi.CreateProcess.__name__ == "guarded_create_process"
    command = subprocess.list2cmdline([MISSING_SOLIDWORKS])
    with pytest.raises(RuntimeError, match=BLOCKED):
        _winapi.CreateProcess(None, command, None, None, False, 0, None, None, None)
    assert len(solidworks_launch_refusals) == 1
    solidworks_launch_refusals.clear()


def test_pywin32_process_creation_is_refused(solidworks_launch_refusals):
    import win32api
    import win32process

    assert win32process.CreateProcess.__name__ == "guarded_create_process"
    command = subprocess.list2cmdline([MISSING_SOLIDWORKS])
    with pytest.raises(RuntimeError, match=BLOCKED):
        win32process.CreateProcess(
            None, command, None, None, False, 0, None, None, win32process.STARTUPINFO()
        )
    assert len(solidworks_launch_refusals) == 1
    solidworks_launch_refusals.clear()
    for attribute, args in (
        ("ShellExecute", (0, "open", MISSING_SHORTCUT, None, None, 1)),
        ("WinExec", (f'"{MISSING_SOLIDWORKS}"',)),
    ):
        _require_refuser(win32api, attribute, "refuse_solidworks_launch")
        _expect_blocked(
            solidworks_launch_refusals,
            lambda attribute=attribute, args=args: getattr(win32api, attribute)(*args),
        )


def test_a_tasklist_argv_with_another_executable_is_refused(solidworks_launch_refusals):
    """Windows starts ``executable``/the application name, not ``args[0]``."""
    import _winapi

    _expect_blocked(
        solidworks_launch_refusals,
        lambda: subprocess.Popen(["tasklist"], executable=MISSING_SOLIDWORKS),
    )
    assert _winapi.CreateProcess.__name__ == "guarded_create_process"
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: _winapi.CreateProcess(
            MISSING_SOLIDWORKS, "tasklist", None, None, False, 0, None, None, None
        ),
    )
    assert launches_solidworks(["tasklist"], r"X:\never-exists\explorer.exe")
    assert not launches_solidworks(["tasklist"], r"C:\Windows\System32\tasklist.exe")


def test_pywin32_logon_process_creation_is_refused():
    """pywin32 312 lacks these; a build that has them gets them refused."""
    import types

    class Refused(Exception):
        pass

    def refuse(route, detail):
        raise Refused(route)

    def create_process(*args, **kwargs):
        raise AssertionError("the stand-in ran: not refused")

    module = types.ModuleType("win32process")
    module.CreateProcessWithLogonW = module.CreateProcessWithTokenW = create_process
    guard_module("win32process", module, refuse, set())
    for attribute in ("CreateProcessWithLogonW", "CreateProcessWithTokenW"):
        with pytest.raises(Refused, match=attribute):
            getattr(module, attribute)("user", None, "pw", 0, MISSING_SOLIDWORKS)


@pytest.mark.parametrize("entry", ["os.spawnv", "os.spawnl", "nt.spawnv"])
def test_spawn_of_solidworks_is_refused(solidworks_launch_refusals, entry):
    """Every spawn entry point meets the ``os.spawn`` audit event in ``nt``."""
    import nt

    argv = [MISSING_SOLIDWORKS]
    calls = {
        "os.spawnv": lambda: os.spawnv(os.P_WAIT, MISSING_SOLIDWORKS, argv),
        "os.spawnl": lambda: os.spawnl(os.P_WAIT, MISSING_SOLIDWORKS, *argv),
        "nt.spawnv": lambda: nt.spawnv(os.P_WAIT, MISSING_SOLIDWORKS, argv),
    }
    _expect_blocked(solidworks_launch_refusals, calls[entry])


def test_startfile_below_os_is_refused(solidworks_launch_refusals):
    import nt

    # An unknown verb as well as a missing file: even unguarded, nothing opens.
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: nt.startfile(MISSING_SHORTCUT, "tripwire-no-such-verb"),
    )


_RUNTIME_TARGET = "('X:\\never-exists\\' + 'p.SLD' + 'PRT')"


@pytest.mark.parametrize(
    "args,shell",
    [
        (["cmd", "/c", "start", "", MISSING_PART], False),
        ('cmd.exe /c start "" probe', False),
        ("start probe", True),  # os.system / popen run it under cmd /c
        (["explorer.exe", MISSING_PART], False),
        ([r"C:\Windows\explorer.exe", "/select,probe"], False),
        (["rundll32.exe", "shell32.dll,ShellExec_RunDLL", "probe"], False),
        (["cmd", "/c", "rundll32", "url.dll,FileProtocolHandler", "probe"], False),
        (
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Start-Process {_RUNTIME_TARGET}",
            ],
            False,
        ),
        (["pwsh", "-c", f"saps {_RUNTIME_TARGET}"], False),
        (["pwsh", "-c", f"ii {_RUNTIME_TARGET}"], False),
        (["pwsh", "-c", f"Invoke-Item -Path {_RUNTIME_TARGET}"], False),
        (["pwsh", "-c", f"start {_RUNTIME_TARGET}"], False),
        (["pwsh", "-c", "iex $env:PROBE"], False),
        (["pwsh", "-c", "[Diagnostics.Process]::Start($env:PROBE)"], False),
        (["pwsh", "-c", "(New-Object -ComObject $env:PROBE).Run(1)"], False),
        (["pwsh", "-c", "Invoke-CimMethod Win32_Process -MethodName Create"], False),
        (["cmd", "/c", MISSING_PART], False),  # a document as a command opens it
        (f'cmd /c "{MISSING_PART}"', False),
        ("probe.SLDASM", True),
        (["uv", "run", "pwsh", "-c", "saps probe"], False),
        # A shell runs what follows ``&``: tasklist is no exemption there.
        ("tasklist & start probe", True),
        ('tasklist /FI "PID eq 0" | start probe', True),
        # ``-f`` inside a -Command script is Start-Process's -FilePath.
        (["pwsh", "-c", "Start-Process -f $env:PROBE"], False),
        (["pwsh", "-NoProfile", "-Command", "saps -f probe"], False),
        ("pwsh -Command Start-Process -f probe", False),
        # Not the host's own -File: a cmd chain, or after -Command.
        (["cmd", "/c", "pwsh", "-File", "s.ps1", "&", "start", "probe"], False),
        (["pwsh", "-Command", "start probe", "-File", "s.ps1"], False),
        (["pwsh", "-UnknownOption", "-File", "s.ps1", "start"], False),
        ("pwsh -File s.ps1 & start probe", True),
    ],
)
def test_a_shell_told_to_open_something_counts(args, shell):
    """A verb is refused whatever its target, so a target built at runtime is too."""
    assert launches_solidworks(args, shell=shell)


@pytest.mark.parametrize(
    "args,shell",
    [
        (["python", "script.py", MISSING_PART], False),
        (["git", "add", "cad/out/part.SLDPRT"], False),
        (["cmd", "/c", "echo", "hello"], False),
        ("echo hello", True),
        (["pwsh", "-NoProfile", "-File", "scripts/farm-run.ps1", "-Status"], False),
        (["pwsh", "-c", "(Get-CimInstance Win32_Process).ParentProcessId"], False),
        (["python", "-m", "pytest", "-k", "start"], False),
        (["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe"], False),
        # The host's -File: the rest is the script's parameters.
        (
            [
                "pwsh",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "s.ps1",
                "-Mode",
                "start",
            ],
            False,
        ),
        (["powershell.exe", "-nop", "-f", "s.ps1", "start"], False),
        (["pwsh", "s.ps1", "-Action", "Start-Process"], False),
    ],
)
def test_an_ordinary_command_does_not_count(args, shell):
    assert not launches_solidworks(args, shell=shell)


# Each would only print were the guard broken.
@pytest.mark.parametrize(
    "call",
    [
        lambda: subprocess.run(["cmd", "/c", "echo", MISSING_PART], check=False),
        lambda: subprocess.run(f"echo {MISSING_PART}", shell=True, check=False),
        lambda: subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Write-Output 'Start-Process'"],
            check=False,
        ),
        lambda: os.system(f"echo {MISSING_PART}"),
        lambda: __import__("nt").system(f"echo {MISSING_PART}"),
        # tasklist, then an echo: inert even unguarded.
        lambda: os.system('tasklist /NH /FI "PID eq 0" & echo start'),
        lambda: __import__("nt").system('tasklist /NH /FI "PID eq 0" & echo start'),
    ],
    ids=[
        "cmd-document",
        "shell-true",
        "powershell-verb",
        "os.system",
        "nt.system",
        "os.system-tasklist-chain",
        "nt.system-tasklist-chain",
    ],
)
def test_a_shell_open_through_a_real_entry_point_is_refused(
    solidworks_launch_refusals, call
):
    _expect_blocked(solidworks_launch_refusals, call)


@pytest.mark.parametrize("attribute", ["popen", "popen2", "popen3", "popen4"])
def test_shell_command_runners_are_refused(solidworks_launch_refusals, attribute):
    import win32pipe

    _require_refuser(win32pipe, attribute, "guarded_command")
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: getattr(win32pipe, attribute)(f"echo {MISSING_PART}", "r"),
    )


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

        command = [sys.executable, str(MISSING_BUILD)]
        with pytest.raises(RuntimeError, match=BLOCKED):
            dodo._exec_com(command, "part:ch_pivot_shaft")
        assert "dodo._exec_com" in solidworks_launch_refusals[0]
        solidworks_launch_refusals.clear()

        # Faking only ``run`` leaves the logged path's real ``Popen``.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(dodo.subprocess, "run", lambda *_a, **_kw: None)
            with pytest.raises(RuntimeError, match=BLOCKED):
                dodo._exec_com(command, "part:ch_pivot_shaft", "part-ch_pivot_shaft")
        assert "dodo._exec_com" in solidworks_launch_refusals[0]
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
        dodo._exec_com(command, "part:ch_pivot_shaft", "part-x")
        assert ran[-1] == command
    assert solidworks_launch_refusals == []

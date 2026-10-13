"""What starts SolidWorks, and the guard every Python child of pytest loads.

The root conftest refuses these acts in the pytest process itself. It also
prepends this directory to ``PYTHONPATH`` and sets :data:`MARKER`, so every
Python descendant (``python -m doit``, ``build.py``, a git textconv or external
diff helper, a ``cmd /c`` chain, ``uv run``) imports ``sitecustomize`` here at
startup and refuses the same acts:

- COM activation of, or binding to, SolidWorks, a SolidWorks document (a
  moniker), or a class that launches programs (:data:`COM_MARKERS`,
  :func:`launcher_class_ids`), through every activator in
  :data:`COM_ACTIVATORS`;
- a process whose command line names SolidWorks or its 3DEXPERIENCE launchers,
  is a shell-open helper, or is a shell told to open something
  (:func:`launches_solidworks`), at every process creator in
  :data:`PROCESS_CREATORS` and :data:`COMMAND_RUNNERS` and, through the audit
  hook, ``os.system``/``spawn*``/``exec*``;
- outright, the entry points in :data:`LAUNCH_ENTRY_POINTS` (shell-open,
  services, other-user processes, the SolidworksMCP launchers),
  ``os.startfile`` and a ctypes binding of :data:`NATIVE_LAUNCHERS`;
- dodo's ``_exec_com``.

A refused child records the refusal in the session log :data:`MARKER` names,
says why on stderr and exits :data:`REFUSED_EXIT` at once, so no caller can
swallow it.

Threat model: accidental launches only. The guard catches repo code and tests
that start SolidWorks by mistake, through the APIs that code actually uses
and their obvious neighbours. Deliberate evasion is out of scope: a native
binary, raw ole32 activation through ctypes (comtypes binds those symbols
itself at import), a shell verb assembled at runtime, a child started with
``-I``/``-E``/``-S`` or without ``PYTHONPATH`` (it skips ``sitecustomize``; the
parent's command-line check still sees its command line), and what a
``.ps1``/``.cmd``/``.vbs`` file does past its command line.
"""

import ntpath
import os
import sys
from importlib.machinery import ExtensionFileLoader, SourceFileLoader

# The path of the pytest session's refusal log; set means "refuse".
MARKER = "HARMONIC_TEST_FORBID_SOLIDWORKS"
# Outside dodo's SolidWorks crash/timeout/modal/seat codes (86-89).
REFUSED_EXIT = 97

# A command line naming one of these starts SolidWorks, whatever runs it.
LAUNCH_MARKERS = (
    "startfile",
    ".lnk",
    "sldworks",
    "swxdesktop",
    "3dexperiencelauncher",
    "catstart",
)
_READ_ONLY_PROGRAMS = frozenset({"tasklist", "tasklist.exe"})
# Opening one of these starts SolidWorks through its file association.
SOLIDWORKS_DOCUMENTS = (
    ".sldprt",
    ".sldasm",
    ".slddrw",
    ".slddrt",
    ".prtdot",
    ".asmdot",
    ".drwdot",
)
# Programs whose job is opening what they are given.
SHELL_OPENERS = frozenset({"explorer", "explorer.exe", "rundll32", "rundll32.exe"})
SHELLS = frozenset(
    {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe"}
)
# Words that make a shell open, start or evaluate something: cmd's ``start``;
# PowerShell's ``Start-Process`` (``saps``/``start``), ``Invoke-Item`` (``ii``),
# ``Invoke-Expression`` (``iex``), WMI/CIM method calls, COM objects and .NET's
# ``[Diagnostics.Process]::Start``; the shell-open helpers. A verb is refused
# whatever its target, so a target built at runtime does not matter.
SHELL_OPEN_WORDS = frozenset(
    {
        "start",
        "start.exe",
        "saps",
        "start-process",
        "ii",
        "invoke-item",
        "iex",
        "invoke-expression",
        "invoke-wmimethod",
        "invoke-cimmethod",
        "-com",
        "-comobject",
        *SHELL_OPENERS,
    }
)
_WORD_SEPARATORS = "&|();{}\"'^,[]:@<>"

# COM classes that start SolidWorks, or start any program: the Shell
# (``ShellExecute``), WScript (``Run``/``Exec``), MMC
# (``ExecuteShellCommand``), the Task Scheduler and WMI (``Win32_Process``).
LAUNCHER_PROGIDS = (
    "SldWorks.Application",
    "Shell.Application",
    "WScript.Shell",
    "MMC20.Application",
    "Schedule.Service",
    "WbemScripting.SWbemLocator",
)
# Launcher classes without a ProgID: ShellWindows, ShellBrowserWindow, the
# Task Scheduler 1.0 agent.
LAUNCHER_CLASS_IDS = frozenset(
    {
        "{9ba05972-f6a8-11cf-a442-00a0c90a8f39}",
        "{c08afd90-f2a1-11d1-8455-00a0c91f3880}",
        "{148bd52a-a2ab-11ce-b11f-00aa00530503}",
    }
)
COM_MARKERS = (
    "sldworks",
    *SOLIDWORKS_DOCUMENTS,
    *(progid.lower() for progid in LAUNCHER_PROGIDS[1:]),
    "winmgmts",
)
# COM activation. ``SldWorks.Application``'s LocalServer32 is SLDWORKS.exe
# itself, so an activation starts SolidWorks without any visible process
# launch; a moniker naming a document activates the class that opens it.
COM_ACTIVATORS = {
    "win32com.client": ("Dispatch", "DispatchEx", "GetObject", "GetActiveObject"),
    "win32com.client.dynamic": ("Dispatch", "DumbDispatch"),
    "win32com.client.gencache": ("EnsureDispatch",),
    "pythoncom": (
        "CoCreateInstance",
        "CoCreateInstanceEx",
        "CoGetObject",
        "GetActiveObject",
        "MkParseDisplayName",
        "connect",
        "Connect",
    ),
    "comtypes": (
        "CoCreateInstance",
        "CoCreateInstanceEx",
        "CoGetClassObject",
        "CoGetObject",
        "GetActiveObject",
    ),
    "comtypes.client": (
        "CreateObject",
        "CoGetObject",
        "GetActiveObject",
        "GetClassObject",
    ),
}
# Refused outright: each starts or stops SolidWorks, shell-opens a document (a
# part opens SolidWorks through its file association), starts a process as
# another user, or registers or starts a service.
LAUNCH_ENTRY_POINTS = {
    "solidworks_mcp.adapters.sw_recovery": (
        "start_solidworks",
        "stop_solidworks",
        "kill_connector_processes",
        "recover_solidworks",
    ),
    "solidworks_mcp.adapters.sw_install": ("launch_via_platform_shortcut",),
    "win32api": ("ShellExecute", "WinExec"),
    "win32com.shell.shell": ("ShellExecuteEx",),
    # pywin32 312 has only the first; later builds may add the other two.
    "win32process": (
        "CreateProcessAsUser",
        "CreateProcessWithLogonW",
        "CreateProcessWithTokenW",
    ),
    "win32service": (
        "CreateService",
        "StartService",
        "ChangeServiceConfig",
        "ChangeServiceConfig2",
    ),
}
# Each takes (application, command line, ...) first.
PROCESS_CREATORS = {"_winapi": ("CreateProcess",), "win32process": ("CreateProcess",)}
# Each runs a command line through the shell (``%COMSPEC% /c``).
COMMAND_RUNNERS = {"win32pipe": ("popen", "popen2", "popen3", "popen4")}
# ctypes symbols that start a process or shell-open a document. Resolving one
# is refused: the call it enables is past every Python-level check. (ole32's
# COM activators are not here: comtypes resolves them at import, and its
# wrappers are guarded above; raw ole32 calls are deliberate evasion.)
NATIVE_LAUNCHERS = frozenset(
    {
        "CreateProcessA",
        "CreateProcessW",
        "CreateProcessAsUserA",
        "CreateProcessAsUserW",
        "CreateProcessInternalA",
        "CreateProcessInternalW",
        "CreateProcessWithLogonW",
        "CreateProcessWithTokenW",
        "NtCreateUserProcess",
        "ZwCreateUserProcess",
        "RtlCreateUserProcess",
        "ShellExecuteA",
        "ShellExecuteW",
        "ShellExecuteExA",
        "ShellExecuteExW",
        "ShellExec_RunDLL",
        "ShellExec_RunDLLA",
        "ShellExec_RunDLLW",
        "SHInvokePrinterCommandA",
        "SHInvokePrinterCommandW",
        "WinExec",
    }
)


def _text(args, executable=None):
    parts = args if isinstance(args, (list, tuple)) else [args]
    return " ".join(
        os.fsdecode(part) if isinstance(part, (str, bytes, os.PathLike)) else str(part)
        for part in [*parts, executable]
        if part is not None
    ).lower()


def _words(text):
    for separator in _WORD_SEPARATORS:
        text = text.replace(separator, " ")
    return {ntpath.basename(word) for word in text.split()}


def program(args):
    if isinstance(args, (list, tuple)):
        return ntpath.basename(str(args[0])).lower() if args else ""
    words = str(args).split()
    return ntpath.basename(words[0].strip('"')).lower() if words else ""


_POWERSHELL_HOSTS = frozenset({"powershell", "powershell.exe", "pwsh", "pwsh.exe"})
_HOST_FLAGS = frozenset(
    {
        "-noprofile",
        "-nop",
        "-nologo",
        "-nol",
        "-noninteractive",
        "-noni",
        "-noexit",
        "-noe",
        "-mta",
        "-sta",
        "-login",
        "-l",
    }
)
# Host options whose next word is their value, not the script.
_HOST_VALUE_OPTIONS = frozenset(
    {
        "-executionpolicy",
        "-ep",
        "-ex",
        "-exec",
        "-workingdirectory",
        "-wd",
        "-windowstyle",
        "-w",
        "-inputformat",
        "-if",
        "-outputformat",
        "-of",
        "-configurationname",
        "-psconsolefile",
        "-version",
        "-settingsfile",
    }
)
_HOST_FILE_OPTIONS = frozenset({"-f", "-fi", "-fil", "-file"})


def _runs_a_script_file(args, shell):
    """Whether ``args`` starts a PowerShell host on a script file.

    Only then is the rest the script's parameters, not code: ``-File`` (or a
    ``.ps1`` path) among the host's own options, before any ``-Command``. A
    host started through a shell may be followed by more commands, so never.
    Any option not known here ends the scan: unknown means code.
    """
    if shell:
        return False
    words = list(args) if isinstance(args, (list, tuple)) else str(args).split()
    if not words or program(words) not in _POWERSHELL_HOSTS:
        return False
    rest = iter(words[1:])
    for word in rest:
        option = str(word).lower()
        if option in _HOST_FILE_OPTIONS:
            return True
        if option in _HOST_VALUE_OPTIONS:
            next(rest, None)
        elif option not in _HOST_FLAGS:
            return not option.startswith("-") and option.endswith(".ps1")
    return False


def launches_solidworks(args, executable=None, shell=False):
    """Whether starting ``args`` could start SolidWorks or shell-open anything.

    ``shell`` says the command runs under ``cmd /c`` (``os.system``, popen).
    """
    first = program(args)
    # Windows starts ``executable`` when given, whatever ``args[0]`` says; a
    # shell runs whatever follows ``&``/``|`` too.
    if (
        not shell
        and first in _READ_ONLY_PROGRAMS
        and (
            executable is None
            or program([_text([], executable)]) in _READ_ONLY_PROGRAMS
        )
    ):
        return False
    text = _text(args, executable)
    if any(marker in text for marker in LAUNCH_MARKERS):
        return True
    words = _words(text)
    programs = {first, ntpath.basename(_text([], executable))}
    if programs & SHELL_OPENERS:
        return True
    if not (shell or words & SHELLS):
        return False
    # A script file takes the rest as parameters, not code: only what names a
    # document or launcher class counts there.
    verbs = () if _runs_a_script_file(args, shell) else words & SHELL_OPEN_WORDS
    return bool(
        verbs
        or any(marker in text for marker in COM_MARKERS)
        or any(document in text for document in SOLIDWORKS_DOCUMENTS)
    )


def launcher_class_ids():
    """The CLSIDs the launcher ProgIDs resolve to here, and the ProgID-less ones.

    A caller may activate a class by CLSID instead of ProgID.
    """
    class_ids = set(LAUNCHER_CLASS_IDS)
    try:
        import winreg
    except ImportError:
        return class_ids
    for progid in LAUNCHER_PROGIDS:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{progid}\CLSID") as key:
                class_ids.add(str(winreg.QueryValue(key, None)).lower())
        except OSError:
            continue
    return class_ids


def activates_a_launcher(args, kwargs, class_ids):
    text = " ".join(str(part) for part in (*args, *kwargs.values())).lower()
    return any(marker in text for marker in COM_MARKERS) or any(
        clsid in text for clsid in class_ids
    )


def _guard_wrapper(function):
    function.solidworks_guard = True
    return function


def refuse_com_activation(module_name, attribute, original, class_ids, refuse):
    @_guard_wrapper
    def refuse_solidworks_activation(*args, **kwargs):
        if activates_a_launcher(args, kwargs, class_ids):
            refuse(f"{module_name}.{attribute}", args)
        return original(*args, **kwargs)

    return refuse_solidworks_activation


def refuse_launch(module_name, attribute, refuse):
    @_guard_wrapper
    def refuse_solidworks_launch(*args, **kwargs):
        refuse(f"{module_name}.{attribute}", args)

    return refuse_solidworks_launch


def refuse_create_process(module_name, original, refuse):
    @_guard_wrapper
    def guarded_create_process(application, command_line, *rest, **kwargs):
        if launches_solidworks(command_line or "", application):
            refuse(f"{module_name}.CreateProcess", command_line or application)
        return original(application, command_line, *rest, **kwargs)

    return guarded_create_process


def refuse_command(module_name, attribute, original, refuse):
    @_guard_wrapper
    def guarded_command(command, *rest, **kwargs):
        if launches_solidworks(command, shell=True):
            refuse(f"{module_name}.{attribute}", command)
        return original(command, *rest, **kwargs)

    return guarded_command


GUARDED_MODULES = (
    *COM_ACTIVATORS,
    *LAUNCH_ENTRY_POINTS,
    *PROCESS_CREATORS,
    *COMMAND_RUNNERS,
)


def guard_module(module_name, module, refuse, class_ids):
    """Replace ``module``'s SolidWorks entry points with refusing wrappers.

    An entry point already replaced (pywin32 copies ``pythoncom``'s DLL module
    into ``pythoncom.py``) keeps its wrapper.
    """

    def originals(table):
        for attribute in table.get(module_name, ()):
            original = getattr(module, attribute, None)
            if original is not None and not getattr(original, "solidworks_guard", 0):
                yield attribute, original

    for attribute, original in originals(COM_ACTIVATORS):
        setattr(
            module,
            attribute,
            refuse_com_activation(module_name, attribute, original, class_ids, refuse),
        )
    for attribute, _original in originals(LAUNCH_ENTRY_POINTS):
        setattr(module, attribute, refuse_launch(module_name, attribute, refuse))
    for attribute, original in originals(PROCESS_CREATORS):
        setattr(module, attribute, refuse_create_process(module_name, original, refuse))
    for attribute, original in originals(COMMAND_RUNNERS):
        setattr(
            module, attribute, refuse_command(module_name, attribute, original, refuse)
        )


def make_audit_hook(refuse):
    """Refuse what the patched Python entry points cannot see.

    ``nt.spawn*``/``nt.exec*``/``nt.system``/``nt.startfile`` called directly,
    and a ctypes binding of a native process or shell launcher.
    """

    def audit(event, args):
        if event == "ctypes.dlsym":
            if args[1] in NATIVE_LAUNCHERS:
                refuse("ctypes", args[1])
        elif event == "os.startfile":
            refuse(event, args[0])
        elif event == "os.system":
            if launches_solidworks(args[0], shell=True):
                refuse(event, args[0])
        elif event in ("os.spawn", "os.exec", "subprocess.Popen"):
            if event == "os.spawn":
                executable, argv = args[1], args[2]
            else:
                executable, argv = args[0], args[1]
            if not isinstance(argv, (str, bytes, os.PathLike)):
                argv = list(argv)
            if launches_solidworks(argv, executable):
                refuse(event, argv)

    return audit


def after_module_load(callback):
    """Call ``callback(loader, module)`` as each source or extension module loads."""
    for loader_class in (SourceFileLoader, ExtensionFileLoader):
        original = loader_class.exec_module

        def exec_module(self, module, original=original):
            original(self, module)
            callback(self, module)

        loader_class.exec_module = exec_module


def _child_refuse(route, detail):
    test = os.environ.get("PYTEST_CURRENT_TEST", "<no test>")
    message = (
        f"SolidWorks launch blocked in a child process of {test} via {route}: "
        f"{str(detail)[:300]}\n"
        f"{MARKER} is set: this process descends from a pytest session, which "
        "must never start SolidWorks or a COM build on the machine running it. "
        "Inject a fake runner, adapter or subprocess instead.\n"
    )
    log = os.environ.get(MARKER, "")
    try:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(message)
    except OSError:
        pass
    try:
        os.write(2, message.encode("utf-8", "replace"))
    finally:
        os._exit(REFUSED_EXIT)


def install_child_guard():
    """Refuse SolidWorks in this process; any refusal ends it."""
    class_ids = launcher_class_ids()

    def refuse_com_task(cmd, label, *_args, **_kwargs):
        _child_refuse("dodo._exec_com", f"{label}: {cmd}")

    def guard_loaded(loader, module):
        name = module.__name__
        guard_module(name, module, _child_refuse, class_ids)
        # pywin32's pythoncom.py swaps the DLL module into sys.modules.
        if sys.modules.get(name) not in (None, module):
            guard_module(name, sys.modules[name], _child_refuse, class_ids)
        path = getattr(loader, "path", "")
        if os.path.basename(path).lower() == "dodo.py" and hasattr(module, "_exec_com"):
            module._exec_com = refuse_com_task

    after_module_load(guard_loaded)
    # A builtin module loads past the loader hook.
    import _winapi  # noqa: F401

    for name in GUARDED_MODULES:
        if name in sys.modules:
            guard_module(name, sys.modules[name], _child_refuse, class_ids)
    sys.addaudithook(make_audit_hook(_child_refuse))

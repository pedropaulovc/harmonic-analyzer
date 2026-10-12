"""What starts SolidWorks, and the guard every Python child of pytest loads.

The root conftest refuses these acts in the pytest process itself. It also
prepends this directory to ``PYTHONPATH`` and sets :data:`MARKER`, so every
Python descendant (``python -m doit``, ``build.py``, a git textconv or external
diff helper, a ``cmd /c`` chain, ``uv run``) imports ``sitecustomize`` here at
startup and refuses the same acts: COM activation of, or binding to,
``SldWorks.Application``; a process whose argv or image names SolidWorks or
its 3DEXPERIENCE launchers; ``os.startfile``, ``ShellExecute`` and the
SolidworksMCP start/stop/launch entry points; and dodo's ``_exec_com``. A
refused child records the refusal in the session log :data:`MARKER` names,
says why on stderr and exits :data:`REFUSED_EXIT` at once, so no caller can
swallow it.

A child started with ``-I``, ``-E`` or ``-S``, or with an environment that
drops ``PYTHONPATH``, skips ``sitecustomize``; the parent's argv check still
refuses one whose command line names SolidWorks.
"""

import ntpath
import os
import sys
from importlib.machinery import ExtensionFileLoader, SourceFileLoader

# The path of the pytest session's refusal log; set means "refuse".
MARKER = "HARMONIC_TEST_FORBID_SOLIDWORKS"
# Outside dodo's SolidWorks crash/timeout/modal/seat codes (86-89).
REFUSED_EXIT = 97

LAUNCH_MARKERS = (
    "startfile",
    ".lnk",
    "sldworks",
    "swxdesktop",
    "3dexperiencelauncher",
    "catstart",
)
_READ_ONLY_PROGRAMS = frozenset({"tasklist", "tasklist.exe"})

# COM activation. ``SldWorks.Application``'s LocalServer32 is SLDWORKS.exe
# itself, so an activation starts SolidWorks without any visible process
# launch. ``pythoncom`` and ``comtypes`` are the layers every wrapper reaches.
COM_ACTIVATORS = {
    "win32com.client": ("Dispatch", "DispatchEx", "GetObject", "GetActiveObject"),
    "win32com.client.dynamic": ("Dispatch", "DumbDispatch"),
    "win32com.client.gencache": ("EnsureDispatch",),
    "pythoncom": (
        "CoCreateInstance",
        "CoCreateInstanceEx",
        "GetActiveObject",
        "connect",
    ),
    "comtypes": ("CoCreateInstance", "CoCreateInstanceEx", "GetActiveObject"),
    "comtypes.client": ("CreateObject", "CoGetObject", "GetActiveObject"),
}
# Entry points refused outright: they start or stop SolidWorks, or open a
# document (a part opens SolidWorks through its file association).
LAUNCH_ENTRY_POINTS = {
    "solidworks_mcp.adapters.sw_recovery": (
        "start_solidworks",
        "stop_solidworks",
        "kill_connector_processes",
        "recover_solidworks",
    ),
    "solidworks_mcp.adapters.sw_install": ("launch_via_platform_shortcut",),
    "win32api": ("ShellExecute", "WinExec"),
}
# Each takes (application, command line, ...) first.
PROCESS_CREATORS = {"win32process": ("CreateProcess",)}


def program(args):
    if isinstance(args, (list, tuple)):
        return ntpath.basename(str(args[0])).lower() if args else ""
    words = str(args).split()
    return ntpath.basename(words[0].strip('"')).lower() if words else ""


def launches_solidworks(args, executable=None):
    if program(args) in _READ_ONLY_PROGRAMS:
        return False
    parts = args if isinstance(args, (list, tuple)) else [args]
    text = " ".join(str(part) for part in [*parts, executable] if part is not None)
    return any(marker in text.lower() for marker in LAUNCH_MARKERS)


def solidworks_class_ids():
    """The CLSID ``SldWorks.Application`` resolves to on this machine, if any.

    A caller may activate the class by CLSID instead of ProgID.
    """
    try:
        import winreg
    except ImportError:
        return set()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CLSID"
        ) as key:
            return {str(winreg.QueryValue(key, None)).lower()}
    except OSError:
        return set()


def names_solidworks(args, kwargs, class_ids):
    text = " ".join(str(part) for part in (*args, *kwargs.values())).lower()
    return "sldworks" in text or any(clsid in text for clsid in class_ids)


def _guard_wrapper(function):
    function.solidworks_guard = True
    return function


def refuse_com_activation(module_name, attribute, original, class_ids, refuse):
    @_guard_wrapper
    def refuse_solidworks_activation(*args, **kwargs):
        if names_solidworks(args, kwargs, class_ids):
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


_AUDITED = frozenset({"subprocess.Popen", "os.system", "os.spawn", "os.exec"})


def _child_audit(event, args):
    if event == "os.startfile":
        _child_refuse(event, args[0])
    if event not in _AUDITED:
        return
    if event == "subprocess.Popen":
        executable, argv = args[0], args[1]
    elif event == "os.system":
        executable, argv = None, args[0]
    elif event == "os.spawn":
        executable, argv = args[1], args[2]
    else:
        executable, argv = args[0], args[1]
    if not isinstance(argv, (str, bytes, os.PathLike)):
        argv = list(argv)
    if launches_solidworks(argv, executable):
        _child_refuse(event, argv)


def install_child_guard():
    """Refuse SolidWorks in this process; any refusal ends it."""
    class_ids = solidworks_class_ids()

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
    for name in (*COM_ACTIVATORS, *LAUNCH_ENTRY_POINTS, *PROCESS_CREATORS):
        if name in sys.modules:
            guard_module(name, sys.modules[name], _child_refuse, class_ids)
    sys.addaudithook(_child_audit)

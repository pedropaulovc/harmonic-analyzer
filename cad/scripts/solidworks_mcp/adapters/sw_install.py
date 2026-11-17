"""Detect the installed SolidWorks edition and resolve a launch strategy.

The "for Makers" / 3DEXPERIENCE edition of SolidWorks cannot be cold-started by
activating the ``SldWorks.Application`` COM class or by running ``sldworks.exe``
directly: both paths pop the modal

    "SOLIDWORKS Design must be launched from the 3DEXPERIENCE Platform or from
     the desktop shortcut created from the Platform."

dialog and the process exits without ever registering a usable COM server. The
only supported way to *start* that edition is the Platform-generated desktop
shortcut; COM is then used solely to *attach* to the running instance.

This module lets the adapter validate how the locally-installed edition must be
started *before* it triggers that dialog, so it can fall back to the Platform
shortcut for the Makers edition and only cold-start standard installs via COM.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from enum import StrEnum
from pathlib import Path

from loguru import logger

from solidworks_mcp.adapters.sw_launch_env import solidworks_launch_environment

try:
    import winreg
except ImportError:  # pragma: no cover - winreg only exists on Windows
    winreg = None  # type: ignore[assignment]


# ProgID whose registered COM server tells us which edition is installed.
COM_PROGID = "SldWorks.Application"

# SolidWorks main process image name.
_SW_PROCESS = "sldworks.exe"

# Start-menu glob (folder/file) for the Platform-generated launch shortcut.
_PLATFORM_SHORTCUT_GLOB = "Dassault Systemes SOLIDWORKS 3DEXPERIENCE*/SOLIDWORKS Design.lnk"


class LaunchStrategy(StrEnum):
    """How a fresh SolidWorks instance must be started when none is running.

    Attributes:
        COM_DISPATCH: Standard install — cold-start via the ``SldWorks.Application``
            COM class (``win32com`` ``Dispatch``). Safe; raises no Platform dialog.
        PLATFORM_SHORTCUT: 3DEXPERIENCE / "for Makers" edition — start through the
            Platform-generated desktop shortcut, then attach over COM.
        PLATFORM_REQUIRED: 3DEXPERIENCE / "for Makers" edition detected, but no
            Platform launch shortcut could be located, so the adapter must ask the
            user to start SolidWorks themselves rather than trigger the dialog.
    """

    COM_DISPATCH = "com_dispatch"
    PLATFORM_SHORTCUT = "platform_shortcut"
    PLATFORM_REQUIRED = "platform_required"


def resolve_com_server_path() -> str | None:
    """Return the executable registered as the ``SldWorks.Application`` COM server.

    Walks ``HKEY_CLASSES_ROOT\\SldWorks.Application\\CLSID`` to the CLSID, then
    reads that CLSID's ``LocalServer32`` command and strips it down to the bare
    ``.exe`` path.

    Returns:
        str | None: The server executable path, or ``None`` when SolidWorks is not
        registered or the registry is unavailable (e.g. non-Windows).
    """
    if winreg is None:
        return None

    clsid = _read_default_value(winreg.HKEY_CLASSES_ROOT, rf"{COM_PROGID}\CLSID")
    if not clsid:
        return None

    command = _read_default_value(
        winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32"
    )
    exe_path = _strip_server_command(command)
    if not exe_path:
        return None
    # The registry usually stores an 8.3 short path (PROGRA~1\...), which hides
    # the "3DEXPERIENCE" marker the edition check relies on — expand it.
    return _expand_short_path(exe_path)


def is_3dexperience_install(exe_path: str | None) -> bool:
    """Report whether a COM-server path is the 3DEXPERIENCE / "for Makers" edition.

    The Makers edition installs under a ``...\\SOLIDWORKS 3DEXPERIENCE R<year>x\\``
    tree, so the marker is unambiguous in the registered server path.

    Args:
        exe_path: The COM-server executable path from :func:`resolve_com_server_path`.

    Returns:
        bool: ``True`` for the 3DEXPERIENCE edition, ``False`` otherwise.
    """
    if not exe_path:
        return False
    return "3dexperience" in exe_path.lower()


def find_platform_shortcut() -> Path | None:
    """Locate the Platform-generated "SOLIDWORKS Design" Start-menu shortcut.

    Searches the all-users and per-user Start-menu ``Programs`` trees. When more
    than one release is installed the newest (highest ``R<year>x``) wins.

    Returns:
        Path | None: The ``.lnk`` to launch, or ``None`` when none is found.
    """
    for programs in _start_menu_program_dirs():
        for shortcut in sorted(programs.glob(_PLATFORM_SHORTCUT_GLOB), reverse=True):
            return shortcut
    return None


def launch_via_platform_shortcut(shortcut: Path) -> None:
    """Start SolidWorks through its 3DEXPERIENCE Platform shortcut.

    A hidden Python child calls ``os.startfile`` to resolve the licensed ``.lnk``
    through the Windows shell, so the
    Platform licence handoff happens exactly as it would from a desktop
    double-click. The child receives the recovered standard Windows variables;
    this process's environment is untouched. Its bounded wait covers only shell
    handoff, not SolidWorks startup. ``os.startfile`` has no environment argument:
    https://docs.python.org/3/library/os.html#os.startfile

    Args:
        shortcut: The Platform launch shortcut from :func:`find_platform_shortcut`.
    """
    logger.info("Launching SolidWorks via 3DEXPERIENCE Platform shortcut: {}", shortcut)
    subprocess.run(
        [sys.executable, "-I", "-c", "import os, sys; os.startfile(sys.argv[1])", str(shortcut)],
        env=solidworks_launch_environment(os.environ),
        check=True,
        timeout=15,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def is_solidworks_process_running() -> bool:
    """Report whether an ``sldworks.exe`` process is already running.

    A running instance that is not yet COM-attachable (still initialising its
    Running Object Table entry, or sitting on a startup dialog) must NOT be
    cold-started or Platform-launched again: a second launch pops the "Another
    session of SOLIDWORKS may already be running" journal warning. Callers use
    this to poll for attach instead of spawning a duplicate.

    Returns:
        bool: ``True`` when at least one ``sldworks.exe`` process exists.
    """
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {_SW_PROCESS}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return False
    return _SW_PROCESS in result.stdout.lower()


def resolve_launch_strategy() -> tuple[LaunchStrategy, Path | None]:
    """Decide how to start SolidWorks when no instance is already running.

    Returns:
        tuple[LaunchStrategy, Path | None]: The chosen strategy and, for
        :attr:`LaunchStrategy.PLATFORM_SHORTCUT`, the shortcut to launch
        (``None`` for the other strategies).
    """
    exe_path = resolve_com_server_path()
    if not is_3dexperience_install(exe_path):
        return LaunchStrategy.COM_DISPATCH, None

    shortcut = find_platform_shortcut()
    if shortcut is None:
        logger.warning(
            "SolidWorks 'for Makers' (3DEXPERIENCE) edition detected at {} but no "
            "Platform launch shortcut was found; it cannot be cold-started via COM.",
            exe_path,
        )
        return LaunchStrategy.PLATFORM_REQUIRED, None

    return LaunchStrategy.PLATFORM_SHORTCUT, shortcut


def _read_default_value(root: int, subkey: str) -> str | None:
    """Read a registry key's unnamed ``(Default)`` value as text.

    Args:
        root: A ``winreg`` predefined root handle (e.g. ``HKEY_CLASSES_ROOT``).
        subkey: The subkey path under ``root``.

    Returns:
        str | None: The default value, or ``None`` when the key is missing.
    """
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, subkey) as key:
            value, _ = winreg.QueryValueEx(key, None)
    except OSError:
        return None
    text = str(value or "").strip()
    return text or None


def _strip_server_command(command: str | None) -> str | None:
    """Extract the bare executable path from a ``LocalServer32`` command string.

    The registered command may be quoted and carry switches, e.g.
    ``"C:\\...\\sldworks.exe" /automation``.

    Args:
        command: The raw ``LocalServer32`` default value.

    Returns:
        str | None: The executable path, or ``None`` when ``command`` is empty.
    """
    if not command:
        return None
    text = command.strip()
    if not text:
        return None
    if text.startswith('"'):
        closing = text.find('"', 1)
        if closing != -1:
            return text[1:closing]
    marker = text.lower().find(".exe")
    if marker != -1:
        return text[: marker + 4]
    return text


def _expand_short_path(path: str) -> str:
    """Expand a Windows 8.3 short path (``PROGRA~1``) to its long form.

    ``LocalServer32`` is frequently stored in 8.3 form, which collapses
    ``SOLIDWORKS 3DEXPERIENCE R2026x`` to something like ``SOLIDW~1`` and hides
    the ``3DEXPERIENCE`` marker the edition check depends on. Best-effort:
    returns ``path`` unchanged when expansion is unavailable (non-Windows) or
    the path no longer exists on disk.

    Args:
        path: A filesystem path, possibly containing 8.3 short components.

    Returns:
        str: The long-form path, or ``path`` unchanged on failure.
    """
    if os.name != "nt":
        return path
    try:
        get_long_path_name = ctypes.windll.kernel32.GetLongPathNameW  # type: ignore[attr-defined]
    except (AttributeError, OSError):  # pragma: no cover - non-Windows only
        return path
    buffer = ctypes.create_unicode_buffer(4096)
    length = get_long_path_name(path, buffer, len(buffer))
    if 0 < length < len(buffer):
        return buffer.value
    return path


def _start_menu_program_dirs() -> list[Path]:
    """Return the existing Start-menu ``Programs`` directories to search.

    Returns:
        list[Path]: All-users (``ProgramData``) first, then per-user (``APPDATA``).
    """
    dirs: list[Path] = []
    for env_var in ("ProgramData", "APPDATA"):
        base = os.environ.get(env_var)
        if not base:
            continue
        programs = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if programs.is_dir():
            dirs.append(programs)
    return dirs

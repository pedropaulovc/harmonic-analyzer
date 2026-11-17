"""Start, stop and recover the 3DEXPERIENCE ("for Makers") SolidWorks connector.

This complements :mod:`solidworks_mcp.adapters.sw_install` (which only decides
*how* to cold-start an edition) with the operations needed to drive SolidWorks
through its whole lifecycle on a Makers seat — including recovering the specific
failure this module is named for:

    SolidWorks launches, sits on its splash, and puts up a modal
    "SOLIDWORKS Design" dialog reading **"Failed to load Microsoft .NET
    Framework."**. The process never becomes COM-attachable, so a build just
    blocks on ``sw.connect``; the watchdog's crash/op-timeout signals never fire.

Everything here is derived empirically (Sysmon capture of a real
SOLIDWORKS Rx *"Troubleshoot ▸ 3DEXPERIENCE Troubleshooting ▸ Restart connector
processes ▸ Launch SOLIDWORKS"* run on this seat), not from Rx internals — Rx is
not automation-friendly. The three observed facts this module reproduces:

1. **The launch chain.** Rx spawns, connected to the tenant read from the
   registry::

       sldrx.exe
         └─ CATSTART.exe -run "SWXDesktopLauncher.exe"
                         -object "-Url=<SpaceURL> --AppName=SWXCSWK_AP
                                  -MyAppsURL=<MyAppsURL> -tenant=<TenantId>
                                  -3DRegistryURL=<RegistryURL>"
              └─ SWXDesktopLauncher.exe   (transient — exits once SW is up)
                   └─ sldworks.exe
   :func:`start_solidworks` reproduces exactly this command. It is the
   automation-friendly replacement for Rx's *"Launch SOLIDWORKS"* button and for
   the Platform Start-menu shortcut — a direct connector launch that never pops
   the "must be launched from the 3DEXPERIENCE Platform" dialog.

2. **"Restart connector processes" = kill the session-scoped connector agents.**
   With SW down there is nothing to restart, so the checkbox reduces to the plain
   launch above; with SW up it first kills the connector agent set
   (:data:`CONNECTOR_AGENTS`). It does **not** touch the persistent platform
   daemons (``3DEXPERIENCELauncher*``, ``sldworks_fs.exe``) — killing those would
   drop the login/CAS session. :func:`kill_connector_processes` mirrors that.

3. **Connector health is readable from the registry.** As it connects,
   ``sldworks.exe`` writes ``HKCU\\Software\\SolidWorks\\SOLIDWORKS 2026\\General\\
   Last Run SolidWorks``: the terminal healthy state is
   ``CONNECTED_LOAD_STATUS == 2`` with ``SOLIDWORKS_ISCONNECTED == 1``.
   :func:`wait_until_connected` polls exactly that.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import subprocess
import time
from ctypes import wintypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from loguru import logger

try:
    import winreg
except ImportError:  # pragma: no cover - winreg only exists on Windows
    winreg = None  # type: ignore[assignment]

from solidworks_mcp.adapters import sw_install

# --------------------------------------------------------------------------- #
# Process sets (image names, case-insensitive) — from the Sysmon launch capture.
# --------------------------------------------------------------------------- #

#: The SolidWorks main process.
SW_MAIN_PROCESS = "sldworks.exe"

#: SolidWorks' own crash-report handler. It only ever runs AFTER ``sldworks.exe``
#: has crashed (it owns the ``#32770`` "SOLIDWORKS Design" / "…encountered a
#: problem… Generating crash report" dialog), so a NEW instance appearing is the
#: earliest reliable "SolidWorks crashed" signal — see :func:`crash_report_pids`.
SW_CRASH_HANDLER = "sldexitapp.exe"

#: SolidWorks' own session children — die with the main process, swept for safety.
SW_SESSION_PROCESSES: tuple[str, ...] = (
    "sldworks.exe",
    "sldProcMon.exe",
    "swCefSubProc.exe",
    "sldsurfacing.exe",
)

#: 3DEXPERIENCE connector agents spawned per SolidWorks session. These are what
#: Rx's "Restart connector processes" cycles. Killing them is safe — they are
#: recreated on the next connected launch.
CONNECTOR_AGENTS: tuple[str, ...] = (
    "SWXDesktopLauncher.exe",
    "CATSTART.exe",
    "ENOUSWCStart2.exe",
    "ENOUSWCStart3.exe",
    "ENOPLMCSAClient.exe",
    "SWConnectorTasksAgent.exe",
    "EdmServerV6.exe",
)

#: Persistent platform daemons that hold the login/CAS session. NEVER killed by
#: recovery — Rx leaves them running too. Documented so the boundary is explicit.
PERSISTENT_PLATFORM_PROCESSES: tuple[str, ...] = (
    "3DEXPERIENCELauncher.exe",
    "3DEXPERIENCELauncherBackbone.exe",
    "3DEXPERIENCELauncherSysTray.exe",
    "sldworks_fs.exe",
)

# --------------------------------------------------------------------------- #
# Registry locations.
# --------------------------------------------------------------------------- #

#: Per-user connector connection parameters (tenant/URLs) written by the login.
_SERVERS_KEY = r"Software\Dassault Systemes\SOLIDWORKSPDM\Servers\3DEXPERIENCE"

#: Per-user connector load status written by sldworks.exe during startup.
_LAST_RUN_KEY = r"Software\SolidWorks\SOLIDWORKS 2026\General\Last Run SolidWorks"

#: Constant connector application name in the launch command.
_APP_NAME = "SWXCSWK_AP"

#: ``CONNECTED_LOAD_STATUS`` value meaning the connector finished loading.
_CONNECTED_OK = 2

# --------------------------------------------------------------------------- #
# .NET-splash-wedge dialog signature (Win32-only, no UI Automation dependency).
# --------------------------------------------------------------------------- #

_DIALOG_CLASS = "#32770"
_DIALOG_TITLE = (
    "SOLIDWORKS Design"  # NOT "...Error Report" (that's the SLDEXITAPP crash handler)
)
_SPLASH_TITLE = "splash"


class SolidWorksState(StrEnum):
    """Coarse SolidWorks lifecycle state, resolved from processes + registry.

    Attributes:
        NOT_RUNNING: No ``sldworks.exe`` process exists.
        DOTNET_SPLASH_WEDGE: Running but stuck on the splash behind the
            "Failed to load Microsoft .NET Framework." modal — never usable.
        STARTING: Running, no wedge, but the connector has not reported loaded
            yet (``CONNECTED_LOAD_STATUS`` != 2).
        CONNECTED: Running and the connector reports loaded — the healthy state.
        RUNNING_DISCONNECTED: Running, not wedged, but the connector reports a
            non-loaded/failed status after startup should have completed.
    """

    NOT_RUNNING = "not_running"
    DOTNET_SPLASH_WEDGE = "dotnet_splash_wedge"
    STARTING = "starting"
    CONNECTED = "connected"
    RUNNING_DISCONNECTED = "running_disconnected"


@dataclass(frozen=True)
class ConnectorParams:
    """Tenant connection parameters for a connector launch (read from the registry)."""

    space_url: str
    my_apps_url: str
    registry_url: str
    tenant: str


# --------------------------------------------------------------------------- #
# Registry reads.
# --------------------------------------------------------------------------- #


def _read_key_values(subkey: str) -> dict[str, object]:
    """Return all values of an ``HKCU`` subkey as a name→value dict (empty on miss)."""
    if winreg is None:
        return {}
    out: dict[str, object] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as key:
            index = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, index)
                except OSError:
                    break
                out[name] = value
                index += 1
    except OSError:
        return {}
    return out


def read_connector_params() -> ConnectorParams | None:
    """Read the tenant connection parameters the connector launch needs.

    Source: ``HKCU\\...\\SOLIDWORKSPDM\\Servers\\3DEXPERIENCE`` (written by the
    3DEXPERIENCE login). Reading them keeps the launch portable — no tenant/URL
    is ever hardcoded.

    Returns:
        ConnectorParams | None: The parameters, or ``None`` if the seat has never
        logged in (key/values absent).
    """
    v = _read_key_values(_SERVERS_KEY)
    space = str(v.get("SpaceURL") or v.get("Address") or "").strip()
    my_apps = str(v.get("MyAppsURL") or "").strip()
    registry = str(v.get("RegistryURL") or "").strip()
    tenant = str(v.get("TenantId") or v.get("Tenant") or "").strip()
    if not (space and registry and tenant):
        logger.warning(
            "Connector params incomplete under {} (never logged in?)", _SERVERS_KEY
        )
        return None
    return ConnectorParams(space, my_apps, registry, tenant)


def read_last_run_status() -> dict[str, object]:
    """Return the ``Last Run SolidWorks`` connector-status values (empty on miss).

    Notable keys: ``CONNECTED_LOAD_STATUS`` (2 == loaded), ``SOLIDWORKS_ISCONNECTED``
    (1 == connected), ``CONNECTOR_LOAD_STATUS``, ``SW_3DEXPERIENCE_ADDIN``.
    """
    return _read_key_values(_LAST_RUN_KEY)


def is_connector_loaded() -> bool:
    """Report whether SolidWorks is running AND the connector finished loading.

    Requires ``sldworks.exe`` to be alive, because ``CONNECTED_LOAD_STATUS`` /
    ``SOLIDWORKS_ISCONNECTED`` are **persistent** — they survive a kill and still
    read the *previous* session's success. Without the liveness check a wait
    right after a stop would trust that stale value and return a false positive
    (observed). :func:`reset_connector_status` clears them on launch so a fresh
    ``2`` only ever reflects the current session.
    """
    if not _running_images((SW_MAIN_PROCESS,)):
        return False
    s = read_last_run_status()
    try:
        connected = int(s.get("CONNECTED_LOAD_STATUS", -1))
        is_conn = int(s.get("SOLIDWORKS_ISCONNECTED", 0))
    except (TypeError, ValueError):
        return False
    return connected == _CONNECTED_OK and is_conn == 1


def reset_connector_status() -> None:
    """Clear the persistent connector-load flags so the next connect is detectable.

    Sets ``CONNECTED_LOAD_STATUS`` and ``SOLIDWORKS_ISCONNECTED`` to 0. These are
    values SolidWorks itself rewrites on every launch (it writes 0 early in
    startup, then 2 once connected), so zeroing them is benign — it just makes
    "not connected yet" true immediately after a stop, which it is. Best-effort.
    """
    if winreg is None:
        return
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _LAST_RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "CONNECTED_LOAD_STATUS", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "SOLIDWORKS_ISCONNECTED", 0, winreg.REG_DWORD, 0)
    except OSError as exc:
        logger.warning("Could not reset connector status flags: {}", exc)


# --------------------------------------------------------------------------- #
# .NET-splash-wedge detection (structural Win32 signature).
# --------------------------------------------------------------------------- #

if os.name == "nt":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _GW_OWNER = 4
    _PROC_QUERY = 0x1000


def _win_text(hwnd: int) -> str:
    n = _user32.GetWindowTextLengthW(hwnd)
    b = ctypes.create_unicode_buffer(n + 1)
    _user32.GetWindowTextW(hwnd, b, n + 1)
    return b.value


def _win_class(hwnd: int) -> str:
    b = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, b, 256)
    return b.value


def _proc_name_of_window(hwnd: int) -> str:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = _kernel32.OpenProcess(_PROC_QUERY, False, pid.value)
    if not h:
        return ""
    try:
        b = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        if _kernel32.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(size)):
            return b.value.rsplit("\\", 1)[-1].lower()
        return ""
    finally:
        _kernel32.CloseHandle(h)


def find_dotnet_splash_dialog() -> int | None:
    """Return the hwnd of the ".NET Framework" splash-wedge modal, or ``None``.

    Structural signature (no UI Automation needed): a visible ``#32770`` window
    titled exactly "SOLIDWORKS Design", owned by an ``sldworks.exe`` process,
    whose owner window is the still-up ``'splash'`` window and is disabled
    (a modal child is blocking it). This is specific enough to exclude the
    ``SLDEXITAPP.exe`` "SOLIDWORKS Design Error Report" crash dialog.

    The body text ("Failed to load Microsoft .NET Framework.") lives in a
    DirectUIHWND and is only readable via UI Automation, so it is NOT required
    here — the structure alone is unambiguous for "wedged on a splash-time modal".
    """
    if os.name != "nt":
        return None
    hits: list[int] = []

    @_WNDENUMPROC
    def _cb(hwnd, _):
        if not _user32.IsWindowVisible(hwnd):
            return True
        if _win_class(hwnd) != _DIALOG_CLASS or _win_text(hwnd) != _DIALOG_TITLE:
            return True
        if _proc_name_of_window(hwnd) != SW_MAIN_PROCESS:
            return True
        owner = _user32.GetWindow(hwnd, _GW_OWNER)
        if not owner:
            return True
        if _win_text(owner) == _SPLASH_TITLE and not _user32.IsWindowEnabled(owner):
            hits.append(hwnd)
        return True

    _user32.EnumWindows(_cb, 0)
    return hits[0] if hits else None


def is_dotnet_splash_wedged() -> bool:
    """True when SolidWorks is stuck on the ".NET Framework" splash modal."""
    return find_dotnet_splash_dialog() is not None


# --------------------------------------------------------------------------- #
# Process helpers.
# --------------------------------------------------------------------------- #

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _running_images(candidates: tuple[str, ...]) -> set[str]:
    """Return the subset of ``candidates`` (image names) currently running."""
    if os.name != "nt":
        return set()
    running: set[str] = set()
    try:
        result = subprocess.run(
            ["tasklist", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return set()
    low = result.stdout.lower()
    for image in candidates:
        if image.lower() in low:
            running.add(image)
    return running


def _taskkill(image: str, *, tree: bool = False) -> None:
    """Force-kill every process with ``image`` (optionally its child tree)."""
    args = ["taskkill", "/F", "/IM", image]
    if tree:
        args.append("/T")
    try:
        subprocess.run(
            args, capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        logger.warning("taskkill {} failed", image)


def _wait_gone(image: str, timeout: float) -> bool:
    """Poll until no process named ``image`` remains, up to ``timeout`` seconds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _running_images((image,)):
            return True
        time.sleep(0.5)
    return not _running_images((image,))


# --------------------------------------------------------------------------- #
# SolidWorks health probes — crash-handler presence + hung top-level window.
#
# The "is SolidWorks crashed or wedged?" facts a COM watchdog needs, kept here
# with the rest of the lifecycle library (harmonic-analyzer's cad/scripts/
# _watchdog.py consumes them). Pure ctypes (no psutil); each is best-effort and
# returns the benign answer on any error so a probe glitch never kills a healthy
# build. These use a PRIVATE ``WinDLL`` with the signatures DECLARED — distinct
# from the shared ``ctypes.windll`` handles the splash probe above uses —
# because ctypes defaults an undeclared call's return/args to ``c_int``, which
# truncates a 64-bit HANDLE (the Toolhelp snapshot) or HWND before the next call
# and would make the suppressed probe silently return nothing (codex #344).
# --------------------------------------------------------------------------- #


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


_INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
_kernel32_declared = None
_user32_declared = None


def _toolhelp():
    """kernel32 with the Toolhelp signatures DECLARED. Private WinDLL (declarations
    never leak onto the shared ``ctypes.windll`` cache); lazy + cached. Windows-only."""
    global _kernel32_declared
    if _kernel32_declared is None:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.restype = wintypes.BOOL
        k32.Process32FirstW.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
        k32.Process32NextW.restype = wintypes.BOOL
        k32.Process32NextW.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        _kernel32_declared = k32
    return _kernel32_declared


def pids_of_image(image_name: str) -> set[int]:
    """Pids of every running process whose image name matches (case-insensitive).

    Uses a Toolhelp process snapshot (in-process, no ``tasklist`` spawn) — cheap
    enough for a watchdog to poll on a short interval. ``set()`` off-Windows or on
    any probe error.
    """
    pids: set[int] = set()
    if os.name != "nt":
        return pids
    with contextlib.suppress(Exception):
        TH32CS_SNAPPROCESS = 0x2
        kernel32 = _toolhelp()
        snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == _INVALID_HANDLE_VALUE:
            return pids
        try:
            entry = _PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
            wanted = image_name.lower()
            ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() == wanted:
                    pids.add(int(entry.th32ProcessID))
                ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snap)
    return pids


def crash_report_pids() -> set[int]:
    """Pids of SolidWorks' crash-report handler (:data:`SW_CRASH_HANDLER`).

    A NEW pid appearing means ``sldworks.exe`` crashed — sldexitapp owns the
    ``#32770`` "SOLIDWORKS Design" ("…encountered a problem… Generating crash
    report") dialog and only ever runs post-crash. A caller decides "crashed" by
    baselining the pids present when it starts (a stale dialog left over from a
    previous crash) and treating only a NEW pid as a fresh crash. Do NOT wait on
    the Windows event log instead: sldexitapp intercepts WER, so the
    ``AppCrash_sldworks.exe`` entry lands only once the report completes (observed
    stuck 8.5 h+) — process appearance is the earliest reliable event.
    """
    return pids_of_image(SW_CRASH_HANDLER)


def _declared_user32():
    """user32 with the HWND-taking signatures DECLARED (same truncation hazard as
    :func:`_toolhelp`; private WinDLL, lazy + cached). Windows-only."""
    global _user32_declared
    if _user32_declared is None:
        u32 = ctypes.WinDLL("user32", use_last_error=True)
        u32.IsWindowVisible.restype = wintypes.BOOL
        u32.IsWindowVisible.argtypes = [wintypes.HWND]
        u32.IsHungAppWindow.restype = wintypes.BOOL
        u32.IsHungAppWindow.argtypes = [wintypes.HWND]
        u32.GetWindowThreadProcessId.restype = wintypes.DWORD
        u32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        _user32_declared = u32
    return _user32_declared


def is_sldworks_window_hung() -> bool:
    """True when a visible ``sldworks.exe`` top-level window fails ``IsHungAppWindow``.

    A best-effort wedge signal that is NOISY on its own: SolidWorks legitimately
    stops pumping window messages while resolving complex geometry, so a caller
    should treat this as advisory (observe/log), not a hard failure. ``False``
    off-Windows or on any probe error.
    """
    if os.name != "nt":
        return False
    try:
        sw_pids = pids_of_image(SW_MAIN_PROCESS)
        if not sw_pids:
            return False
        user32 = _declared_user32()
        hung = False

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _on_window(hwnd, _lparam):
            nonlocal hung
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in sw_pids and user32.IsHungAppWindow(hwnd):
                hung = True
                return False
            return True

        user32.EnumWindows(_on_window, 0)
        return hung
    except Exception:  # noqa: BLE001 - probe is best-effort, never fatal
        return False


# --------------------------------------------------------------------------- #
# Stop / restart connector processes.
# --------------------------------------------------------------------------- #


def kill_connector_processes() -> set[str]:
    """Kill the session-scoped 3DEXPERIENCE connector agents that were running.

    This is the "Restart connector processes" *kill* half — the persistent
    platform daemons are deliberately left alone. Returns the set of image names
    that were actually running and got killed (best-effort).
    """
    were_running = _running_images(CONNECTOR_AGENTS)
    for image in were_running:
        logger.info("Killing connector agent {}", image)
        _taskkill(image)
    return were_running


def stop_solidworks(timeout: float = 60.0) -> bool:
    """Stop SolidWorks and its connector agents, waiting for a full exit.

    Kills the main process tree first (so its children cascade), then sweeps any
    lingering session/connector processes, then blocks until ``sldworks.exe`` is
    gone. Waiting for the exit is essential: a relaunch while the old process is
    still terminating trips Rx's / the Platform's "SOLIDWORKS is already running"
    guard and no-ops (observed).

    Args:
        timeout: Seconds to wait for ``sldworks.exe`` to disappear.

    Returns:
        bool: ``True`` once no ``sldworks.exe`` remains, ``False`` on timeout.
    """
    if not _running_images((SW_MAIN_PROCESS,)) and not _running_images(
        CONNECTOR_AGENTS
    ):
        logger.info("SolidWorks already stopped")
        return True

    logger.info("Stopping SolidWorks (main tree + connector agents)")
    _taskkill(SW_MAIN_PROCESS, tree=True)
    for image in _running_images(SW_SESSION_PROCESSES + CONNECTOR_AGENTS):
        if image.lower() != SW_MAIN_PROCESS.lower():
            _taskkill(image)

    if not _wait_gone(SW_MAIN_PROCESS, timeout):
        logger.error("sldworks.exe still present {}s after kill", timeout)
        return False
    logger.info("SolidWorks stopped")
    return True


# --------------------------------------------------------------------------- #
# Start (connector launch).
# --------------------------------------------------------------------------- #


def resolve_install_root() -> Path | None:
    """Resolve the ``SOLIDWORKS 3DEXPERIENCE R<year>x`` install root, or ``None``.

    Derived from the registered COM server path
    (``...\\<root>\\SOLIDWORKS\\sldworks.exe`` → ``<root>``).
    """
    server = sw_install.resolve_com_server_path()
    if not server:
        return None
    root = Path(server).parent.parent
    return root if root.exists() else None


def build_connector_launch_command(params: ConnectorParams, root: Path) -> str:
    """Build the exact CATSTART connector-launch command line Rx uses.

    Args:
        params: Tenant connection parameters from :func:`read_connector_params`.
        root: Install root from :func:`resolve_install_root`.

    Returns:
        str: A ready-to-spawn command line. Returned as a string (not a list) so
        Windows ``CreateProcess`` receives the nested ``-object "..."`` token
        verbatim without Python re-quoting the embedded arguments.
    """
    catstart = root / "win_b64" / "code" / "bin" / "CATSTART.exe"
    obj = (
        f"-Url={params.space_url} "
        f"--AppName={_APP_NAME} "
        f"-MyAppsURL={params.my_apps_url} "
        f"-tenant={params.tenant} "
        f"-3DRegistryURL={params.registry_url}"
    )
    return f'"{catstart}" -run "SWXDesktopLauncher.exe" -object "{obj}"'


def start_solidworks() -> bool:
    """Launch SolidWorks connected to the 3DEXPERIENCE platform (Rx-equivalent).

    Spawns the ``CATSTART.exe -run SWXDesktopLauncher.exe`` connector launch
    (detached), which is the exact chain Rx's "Launch SOLIDWORKS" uses. Falls
    back to the Platform Start-menu shortcut (:mod:`sw_install`) when the connector
    params or CATSTART are unavailable.

    Refuses to launch when an ``sldworks.exe`` is already running (mirrors the
    "already running" guard) — stop it first.

    Returns:
        bool: ``True`` when a launch was initiated, ``False`` otherwise.
    """
    if _running_images((SW_MAIN_PROCESS,)):
        logger.warning("sldworks.exe already running; not launching a second instance")
        return False

    # Clear the previous session's persistent health flags so wait_until_connected
    # only sees a fresh "connected" from THIS launch, not a stale one.
    reset_connector_status()

    params = read_connector_params()
    root = resolve_install_root()
    if params and root:
        cmd = build_connector_launch_command(params, root)
        bin_dir = root / "win_b64" / "code" / "bin"
        logger.info("Launching SolidWorks via connector: {}", cmd)
        launch_environment = sw_install.solidworks_launch_environment(os.environ)
        try:
            subprocess.Popen(
                cmd,
                cwd=str(bin_dir),
                env=launch_environment,
                creationflags=_NO_WINDOW
                | getattr(subprocess, "DETACHED_PROCESS", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                close_fds=True,
            )
            return True
        except (OSError, subprocess.SubprocessError) as exc:
            logger.error(
                "Connector launch failed ({}); falling back to Platform shortcut", exc
            )

    strategy, shortcut = sw_install.resolve_launch_strategy()
    if strategy is sw_install.LaunchStrategy.PLATFORM_SHORTCUT and shortcut is not None:
        sw_install.launch_via_platform_shortcut(shortcut)
        return True
    logger.error(
        "No usable launch path (connector params missing and no Platform shortcut)"
    )
    return False


def wait_until_connected(timeout: float = 300.0) -> bool:
    """Block until the connector reports loaded, or a wedge/timeout ends the wait.

    Polls :func:`is_connector_loaded` (registry ``CONNECTED_LOAD_STATUS == 2`` and
    ``SOLIDWORKS_ISCONNECTED == 1``). Aborts early and returns ``False`` if the
    ".NET Framework" splash wedge reappears — no point waiting on a dead launch.

    Args:
        timeout: Seconds to wait for a connected state.

    Returns:
        bool: ``True`` if connected within ``timeout``, ``False`` otherwise.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_dotnet_splash_wedged():
            logger.error(".NET Framework splash wedge during startup — launch failed")
            return False
        if is_connector_loaded():
            logger.info("Connector loaded (CONNECTED_LOAD_STATUS=2)")
            return True
        time.sleep(2.0)
    logger.error("Connector not loaded within {}s", timeout)
    return False


# --------------------------------------------------------------------------- #
# State + recovery orchestration.
# --------------------------------------------------------------------------- #


def detect_state() -> SolidWorksState:
    """Resolve the current SolidWorks lifecycle state from processes + registry."""
    if not _running_images((SW_MAIN_PROCESS,)):
        return SolidWorksState.NOT_RUNNING
    if is_dotnet_splash_wedged():
        return SolidWorksState.DOTNET_SPLASH_WEDGE
    if is_connector_loaded():
        return SolidWorksState.CONNECTED
    # Running, not wedged, connector not (yet) loaded.
    s = read_last_run_status()
    if str(s.get("CONNECTED_LOAD_STATUS", "")) in ("", "0", "1"):
        return SolidWorksState.STARTING
    return SolidWorksState.RUNNING_DISCONNECTED


def recover_solidworks(
    *, stop_timeout: float = 60.0, connect_timeout: float = 300.0
) -> SolidWorksState:
    """Recover SolidWorks to a connected state (the ".NET splash wedge" fix).

    Full cycle, matching the manual Rx recovery: stop SolidWorks and its
    connector agents (waiting for a clean exit), then relaunch via the connector
    (which restarts the connector agents fresh), then wait until the connector
    reports loaded.

    Idempotent shortcut: if already :attr:`SolidWorksState.CONNECTED`, does
    nothing.

    Args:
        stop_timeout: Seconds to allow for the stop to complete.
        connect_timeout: Seconds to allow for the connector to load after launch.

    Returns:
        SolidWorksState: The state after recovery (``CONNECTED`` on success).
    """
    state = detect_state()
    logger.info("recover_solidworks: initial state = {}", state)
    if state is SolidWorksState.CONNECTED:
        return state

    if not stop_solidworks(timeout=stop_timeout):
        logger.error("Stop did not complete; aborting recovery")
        return detect_state()

    if not start_solidworks():
        logger.error("Launch could not be initiated; aborting recovery")
        return detect_state()

    wait_until_connected(timeout=connect_timeout)
    final = detect_state()
    logger.info("recover_solidworks: final state = {}", final)
    return final


# --------------------------------------------------------------------------- #
# CLI — manual driving / testing: python -m solidworks_mcp.adapters.sw_recovery <cmd>
# --------------------------------------------------------------------------- #


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Start/stop/recover 3DEXPERIENCE SolidWorks."
    )
    parser.add_argument(
        "command",
        choices=["status", "stop", "restart-connectors", "start", "recover"],
    )
    args = parser.parse_args(argv)

    if args.command == "status":
        print("state:", detect_state().value)
        print("dotnet_splash_wedge:", is_dotnet_splash_wedged())
        print("connector_loaded:", is_connector_loaded())
        print(
            "last_run:",
            {
                k: read_last_run_status().get(k)
                for k in (
                    "CONNECTED_LOAD_STATUS",
                    "SOLIDWORKS_ISCONNECTED",
                    "CONNECTOR_LOAD_STATUS",
                )
            },
        )
        return 0
    if args.command == "stop":
        return 0 if stop_solidworks() else 1
    if args.command == "restart-connectors":
        print("killed:", sorted(kill_connector_processes()))
        return 0
    if args.command == "start":
        return 0 if start_solidworks() else 1
    if args.command == "recover":
        return 0 if recover_solidworks() is SolidWorksState.CONNECTED else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())

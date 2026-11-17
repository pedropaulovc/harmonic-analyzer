"""Recover four omitted Windows standards in an isolated launch environment.

This repair requires 64-bit Python on native AMD64 Windows. It copies the caller's
complete environment and preserves every supplied value, matching keys
case-insensitively. It never reads a user's environment registry or credentials.
CommonX64 is unsupported from a 32-bit caller, even on AMD64 Windows. A complete
supplied environment needs no repair and performs no architecture or folder query.

The CEF startup control (2026-09-06, SW 34.3.0) reproduced the missing-installation
modal with these four values absent, then reached the licensed main window and
native attach with only these values restored in the launcher child. Registration
already worked before the repair; this is not an installation-health detector.

Native path and architecture contracts:
https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath
https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid
https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getnativesysteminfo
https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/ns-sysinfoapi-system_info
"""

from __future__ import annotations

import ctypes
import ntpath
import os
from collections.abc import Mapping
from ctypes import wintypes
from uuid import UUID

_COMMON_X64 = "6365D5A7-0F0D-45E5-87F6-0DA56B6A4F7D"
_COMMON_X86 = "DE974D24-D9C6-4D3E-BF91-F4455120B917"
_PATH_FOLDERS = {
    "CommonProgramFiles": _COMMON_X64,
    "CommonProgramW6432": _COMMON_X64,
    "CommonProgramFiles(x86)": _COMMON_X86,
}
_STANDARD_NAMES = (*_PATH_FOLDERS, "PROCESSOR_ARCHITECTURE")


class _Guid(ctypes.Structure):
    _fields_ = [
        ("data1", ctypes.c_uint32),
        ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16),
        ("data4", ctypes.c_ubyte * 8),
    ]


class _SystemInfo(ctypes.Structure):
    # The first two WORDs are the documented union's architecture/reserved pair.
    _fields_ = [
        ("architecture", wintypes.WORD),
        ("reserved", wintypes.WORD),
        ("page_size", wintypes.DWORD),
        ("minimum_address", ctypes.c_void_p),
        ("maximum_address", ctypes.c_void_p),
        ("processor_mask", ctypes.c_size_t),
        ("processor_count", wintypes.DWORD),
        ("processor_type", wintypes.DWORD),
        ("allocation_granularity", wintypes.DWORD),
        ("processor_level", wintypes.WORD),
        ("processor_revision", wintypes.WORD),
    ]


def _native_architecture() -> int:
    if os.name != "nt":
        raise OSError("SolidWorks launch environment repair requires AMD64 Windows")
    function = ctypes.WinDLL("kernel32").GetNativeSystemInfo
    function.argtypes = [ctypes.POINTER(_SystemInfo)]
    function.restype = None
    result = _SystemInfo()
    function(ctypes.byref(result))
    return int(result.architecture)


def _known_folder(folder_id: str) -> str:
    function = ctypes.WinDLL("shell32").SHGetKnownFolderPath
    function.argtypes = [
        ctypes.POINTER(_Guid),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    function.restype = ctypes.c_long
    release = ctypes.WinDLL("ole32").CoTaskMemFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = None
    identifier = _Guid.from_buffer_copy(UUID(folder_id).bytes_le)
    result = ctypes.c_void_p()
    try:
        status = function(ctypes.byref(identifier), 0, None, ctypes.byref(result))
        if status != 0 or not result.value:
            raise OSError(
                f"Windows common-program-files lookup failed (HRESULT {status:#x})"
            )
        path = ctypes.wstring_at(result)
        if (
            not ntpath.isabs(path)
            or not ntpath.splitdrive(path)[0]
            or not os.path.isdir(path)
        ):
            raise OSError(
                "Windows common-program-files lookup returned no existing absolute directory"
            )
        return path
    finally:
        release(result)  # Microsoft requires freeing the output even on failure.


def solidworks_launch_environment(parent: Mapping[str, str]) -> dict[str, str]:
    """Copy task context and fill only absent standard names for an AMD64 child."""
    result = dict(parent)
    present = {name.casefold() for name in result}
    missing = tuple(name for name in _STANDARD_NAMES if name.casefold() not in present)
    if not missing:
        return result
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("SolidWorks launch environment repair requires 64-bit Python")
    if _native_architecture() != 9:  # PROCESSOR_ARCHITECTURE_AMD64
        raise OSError(
            "SolidWorks launch environment repair supports native AMD64 Windows only"
        )
    folders = {}
    for name in missing:
        if name == "PROCESSOR_ARCHITECTURE":
            result[name] = "AMD64"
            continue
        identifier = _PATH_FOLDERS[name]
        if identifier not in folders:
            folders[identifier] = _known_folder(identifier)
        result[name] = folders[identifier]
    return result

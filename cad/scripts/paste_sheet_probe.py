"""Farm-only positive-control discriminator for the complete-machine PasteSheet failure.

THROWAWAY DIAGNOSTIC (route B leaf, attach-only owned-diagnostic runner). It
never edits, saves or regenerates any recipe, template or source document and
retries nothing to get green. One execution runs at most six native
``IDrawingDoc.PasteSheet`` calls, in a fixed matrix:

    A0  exact incident shape: new portrait 1:5 target (initial sheet renamed
        ASSEMBLED) -> new portrait 1:5 donor -> checked named SHEET selection
        -> EditCopy -> ActivateDoc3(target, False, 2) -> PasteSheet(2, 2).
        Runs first, before any successful copy/paste in this session.
    P   positive control: the FIRST ATTEMPT of
        ``_drawing_sheets.create_blank_drawing_sheets`` (fresh portrait 1:5
        drawing, ActivateSheet(initial), clear/select/copy, SAME-document
        PasteSheet(2, 2)); exactly one new sheet expected; no retry loop.
    B   A0 with ActivateDoc3's rebuild option 2 -> 1 (swDontRebuildActiveDoc);
        the documented swDocNeedsRebuildWarning (2) is recorded and native
        identity of the activated document is still required.
    C   A0 with the target's ASSEMBLED sheet explicitly selected after
        activation and before the unchanged PasteSheet(2, 2).
    A1  exact incident shape again, bracketing B/C against order effects.
    R   only when A0 and A1 both reproduce the incident's paste failure, P
        passes and EXACTLY ONE of B/C passes: one fresh repetition of that
        variant. Otherwise the matrix stops.

Between EditCopy's preceding snapshot and the post-PasteSheet snapshot the only
calls are the production recipe's own native calls (the cloned
``_activate_package`` identity check and sheet inventory included) and
non-mutating, non-locking Win32 clipboard metadata reads buffered in
preallocated slots: GetClipboardSequenceNumber, GetClipboardOwner,
GetOpenClipboardWindow and GetUpdatedClipboardFormats. No OpenClipboard,
GetClipboardData, EmptyClipboard or SetClipboardData, no sleep, no message
pump, no file I/O, logging or extra COM getter in that interval. Owner process
identities and registered format names are resolved AFTER the interval.

An expected case failure (no sheet pasted, activation refused, a native call
raising inside the interval) is report data. A setup, ownership, cleanup or
probe malfunction fails the process loudly after flushing the partial report
under ``cad/out/reports/failures/paste-sheet-probe/<run>/``. The final report is
``cad/out/reports/paste-sheet-probe/result.json``.

Session contract (``diagnostics._owned_native_session``): attach only, never
launch or recover; requires ``HARMONIC_COM_SEAT`` and
``HARMONIC_SW_AUTOSTART=0``; the starting document inventory must be EMPTY (no
unknown document is ever closed); this probe owns the read-only source
assembly, every document that opening it loads, and its fresh drawings, and
closes all of them before returning. No seat preference is written: the
annotation-ink preferences ``new_project_drawing`` pins must already hold their
pinned value, or the probe refuses before creating a drawing.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time
from typing import Any, Callable

import _seat_forensics
import _telemetry
from _com import _early_bound
from _drawing_common import (
    _COLORREF_BLACK,
    _PREF_COLOR_IMPORTED_DRIVEN_ANNOTATION,
    _PREF_COLOR_NON_IMPORTED_ANNOTATION,
    new_project_drawing,
    read_required_properties,
)
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from _paths import CAD_ROOT
from diagnostics._owned_native_session import (
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)
import draw_ha_harmonic_analyzer_assembly as incident
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import iter_views

SCHEMA = "harmonic-analyzer/paste-sheet-probe@1"
REPO_ROOT = CAD_ROOT.parent
REPORT = CAD_ROOT / "out" / "reports" / "paste-sheet-probe" / "result.json"
PARTIAL_ROOT = CAD_ROOT / "out" / "reports" / "failures" / "paste-sheet-probe"

# Exact incident inputs (approved plan). The token is sha256 of the SLDASM bytes
# (dodo._stamp_execution); the token file's md5 is dodo's content digest of it.
SOURCE = incident.SOURCE
SOURCE_TOKEN = CAD_ROOT / "out" / "sldasm" / ".ha-harmonic-analyzer.execution"
EXPECTED_SOURCE_TOKEN = (
    "324bc29bf6659cc91eaa67a3438cd4f7af256c23b7c651cf6828b0347ae3b610"
)
EXPECTED_TOKEN_FILE_MD5 = "815bc4ef1fe268ca36d191b4b2391bbd"
# Recorded only: the SLDASM's content digest is dodo's recipe-stable digest
# (ContentChecker), not recomputable here; the cache key carries it.
INCIDENT_SOURCE_RECIPE_DIGEST = "528c21697dded7af8700160ea55f368d"
INCIDENT_ASSEMBLY_CACHE_KEY = (
    "26d1715777903a4ebb12bb83cbf9bb727d63f3318acdbec7306ba73a6a7fecf3"
)
# Git blob ids of the incident's template and recipe sources (baseline
# 504f4274c == head 943b17b7e for each).
EXPECTED_BLOBS = {
    "cad/templates/harmonic-analyzer-portrait.DRWDOT": (
        "fdc6eda2e9e1099a6cb13d33d2284aa03636aef4"
    ),
    "cad/templates/harmonic-analyzer-landscape.DRWDOT": (
        "806d3665a6a1ab3e49ede3dc91b114d2d8078ba9"
    ),
    "cad/scripts/draw_ha_harmonic_analyzer_assembly.py": (
        "2e36615b806bc1a597e753874ba9e2773ca92b18"
    ),
    "cad/scripts/_drawing_common.py": "9f10a3ad6596aa66afa708cc38581d0f9fda829b",
}
RECORDED_BLOBS = ("cad/scripts/_drawing_sheets.py",)

TARGET_SHEET = incident.SHEET_NAMES[0]  # "ASSEMBLED"
PASTED_SHEET = incident.SHEET_NAMES[1]  # "FINISHED MACHINE"

MAX_NATIVE_PASTES = 6
SELECTION_BOUND = 8
CLIPBOARD_FORMAT_CAPACITY = 64

SW_DOC_ASSEMBLY = 2  # swDocumentTypes_e.swDocASSEMBLY
OPEN_SILENT_READ_ONLY = 1 | 2  # swOpenDocOptions_Silent | swOpenDocOptions_ReadOnly
SW_SEL_SHEETS = 19  # swSelectType_e.swSelSHEETS ("SHEET" -> ISheet)
INSERT_MOVE_TO_END = 2  # swInsertOptions_e.swInsertOption_MoveToEnd
RENAME_NO = 2  # swRenameOptions_e.swRenameOption_No
REBUILD_ACTIVE_DOC = 2  # swRebuildOnActivation_e.swRebuildActiveDoc (incident)
DONT_REBUILD_ACTIVE_DOC = 1  # swRebuildOnActivation_e.swDontRebuildActiveDoc
ACTIVATE_GENERIC_ERROR = 1  # swActivateDocError_e.swGenericActivateError
ACTIVATE_NEEDS_REBUILD_WARNING = 2  # swActivateDocError_e.swDocNeedsRebuildWarning
SEAT_ANNOTATION_PREFERENCES = (
    _PREF_COLOR_NON_IMPORTED_ANNOTATION,
    _PREF_COLOR_IMPORTED_DRIVEN_ANNOTATION,
)

# The incident's failure is production's sheet-count check; a native call that
# raises is a different failure and is not counted as reproducing it.
INCIDENT_PASTE_FAILURES = frozenset({"paste_created_no_sheet", "paste_inventory_anomalous"})

_ERROR_INSUFFICIENT_BUFFER = 122
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_UOI_NAME = 2
_STANDARD_CLIPBOARD_FORMATS = {
    1: "CF_TEXT",
    2: "CF_BITMAP",
    3: "CF_METAFILEPICT",
    4: "CF_SYLK",
    5: "CF_DIF",
    6: "CF_TIFF",
    7: "CF_OEMTEXT",
    8: "CF_DIB",
    9: "CF_PALETTE",
    10: "CF_PENDATA",
    11: "CF_RIFF",
    12: "CF_WAVE",
    13: "CF_UNICODETEXT",
    14: "CF_ENHMETAFILE",
    15: "CF_HDROP",
    16: "CF_LOCALE",
    17: "CF_DIBV5",
    0x80: "CF_OWNERDISPLAY",
    0x81: "CF_DSPTEXT",
    0x82: "CF_DSPBITMAP",
    0x83: "CF_DSPMETAFILEPICT",
    0x8E: "CF_DSPENHMETAFILE",
}
# Environment values safe to record verbatim; every other HARMONIC_/FARM_ name
# is recorded without its value.
_RECORDED_ENVIRONMENT = (
    "HARMONIC_SW_AUTOSTART",
    "HARMONIC_COM_SEAT",
    "HARMONIC_DIAGNOSTIC_SW_PID",
    "HARMONIC_FARM_PARALLELISM",
    "HARMONIC_REMOTE_CACHE_MODE",
    "COMPUTERNAME",
    "USERNAME",
)


class ProbeMalfunction(RuntimeError):
    """Setup, ownership, cleanup or probe failure: never a case outcome."""


# ---------------------------------------------------------------------------
# Value capture
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return f"<{type(value).__name__}>"


def _error(exc: BaseException) -> dict[str, Any]:
    hresult = getattr(exc, "hresult", None)
    if not isinstance(hresult, int) and exc.args and isinstance(exc.args[0], int):
        hresult = exc.args[0]
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "hresult": hresult,
        "args": _jsonable(list(exc.args[:4])),
    }


def _observe(read: Callable[[], Any]) -> dict[str, Any]:
    """A read's value (None kept as null) or its error -- never conflated."""
    try:
        value = read()
    except Exception as exc:  # noqa: BLE001 - captured as evidence
        return {"ok": False, "error": _error(exc)}
    return {"ok": True, "value": _jsonable(value)}


def _write_json(path: Path, payload: Any, *, indent: int | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    separators = None if indent else (",", ":")
    temporary.write_text(
        json.dumps(payload, indent=indent, separators=separators, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _canonical_bytes(path: Path) -> bytes:
    """dodo._canonical_file_bytes: Git-canonical (LF) text, raw binary."""
    data = path.read_bytes()
    if b"\0" not in data[:8000]:
        data = data.replace(b"\r\n", b"\n")
    return data


def _git_blob(path: Path) -> str:
    data = _canonical_bytes(path)
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _git_head() -> dict[str, Any]:
    marker = REPO_ROOT / ".git"
    if marker.is_file():
        line = marker.read_text(encoding="utf-8").strip()
        if not line.startswith("gitdir:"):
            return {"unresolved": line}
        gitdir = (REPO_ROOT / line.removeprefix("gitdir:").strip()).resolve()
    else:
        gitdir = marker
    head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return {"detached": head}
    ref = head.removeprefix("ref: ")
    loose = gitdir / ref
    return {
        "ref": ref,
        "commit": loose.read_text(encoding="utf-8").strip() if loose.is_file() else None,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class Report:
    """The full report, flushed as partial JSON and compact checkpoints."""

    def __init__(self) -> None:
        stamp = datetime.now(UTC)
        self.directory = (
            PARTIAL_ROOT
            / f"{stamp:%Y%m%dT%H%M%S}{stamp.microsecond // 1000:03d}Z-pid{os.getpid()}"
        )
        self.sequence = 0
        self.data: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "in_progress",
            "started_at": _utc_now(),
            "report": str(REPORT.relative_to(REPO_ROOT).as_posix()),
            "partial_directory": str(self.directory.relative_to(REPO_ROOT).as_posix()),
            "cases": [],
        }

    def flush(self) -> None:
        _write_json(self.directory / "partial.json", self.data, indent=2)

    def checkpoint(self, label: str, compact: dict[str, Any]) -> None:
        self.sequence += 1
        payload = {"sequence": self.sequence, "label": label, "at": _utc_now(), **compact}
        self.data.setdefault("checkpoints", []).append(payload)
        _write_json(
            self.directory / f"checkpoint-{self.sequence:02d}-{label}.json",
            payload,
            indent=None,
        )
        self.flush()
        _telemetry.info(
            "paste-sheet-probe checkpoint "
            + json.dumps(payload, separators=(",", ":"), default=str)
        )

    def malfunction(self, exc: BaseException) -> None:
        self.data["status"] = "probe_malfunction"
        self.data["finished_at"] = _utc_now()
        self.data["malfunction"] = _error(exc)
        self.checkpoint("malfunction", {"error": _error(exc)})

    def complete(self) -> None:
        self.data["status"] = "complete"
        self.data["finished_at"] = _utc_now()
        self.flush()
        _write_json(REPORT, self.data, indent=2)


# ---------------------------------------------------------------------------
# Preflight (no COM)
# ---------------------------------------------------------------------------


def _probe_environment() -> dict[str, Any]:
    recorded = {name: os.environ.get(name) for name in _RECORDED_ENVIRONMENT}
    other = sorted(
        name
        for name in os.environ
        if name.startswith(("HARMONIC_", "FARM_", "TEMPORAL_"))
        and name not in recorded
    )
    return {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "executable": sys.executable,
        "python": sys.version,
        "argv": list(sys.argv),
        "environment": recorded,
        "other_environment_names": other,
    }


def preflight(report: Report) -> None:
    """Exact source identity and recipe/template bytes, before any COM call."""
    failures: list[str] = []
    identity: dict[str, Any] = {
        "source": str(SOURCE.relative_to(REPO_ROOT).as_posix()),
        "token_file": str(SOURCE_TOKEN.relative_to(REPO_ROOT).as_posix()),
        "expected_token": EXPECTED_SOURCE_TOKEN,
        "expected_token_file_md5": EXPECTED_TOKEN_FILE_MD5,
        "incident_source_recipe_digest_recorded_only": INCIDENT_SOURCE_RECIPE_DIGEST,
        "incident_assembly_cache_key_recorded_only": INCIDENT_ASSEMBLY_CACHE_KEY,
    }
    if not SOURCE_TOKEN.is_file():
        failures.append(f"source execution token is missing: {SOURCE_TOKEN}")
    else:
        token = SOURCE_TOKEN.read_text(encoding="utf-8").strip()
        token_md5 = hashlib.md5(_canonical_bytes(SOURCE_TOKEN)).hexdigest()
        identity.update(token=token, token_file_md5=token_md5)
        if token != EXPECTED_SOURCE_TOKEN:
            failures.append(f"source execution token {token!r} != expected")
        if token_md5 != EXPECTED_TOKEN_FILE_MD5:
            failures.append(f"source token file digest {token_md5} != expected")
    if not SOURCE.is_file():
        failures.append(f"source assembly is missing: {SOURCE}")
    else:
        source_sha = _sha256(SOURCE)
        identity.update(source_sha256_before=source_sha, source_bytes=SOURCE.stat().st_size)
        if source_sha != EXPECTED_SOURCE_TOKEN:
            failures.append(f"source assembly bytes sha256 {source_sha} != token")
    report.data["source_identity"] = identity

    blobs: dict[str, Any] = {}
    for relative, expected in EXPECTED_BLOBS.items():
        path = REPO_ROOT / relative
        actual = _git_blob(path) if path.is_file() else None
        blobs[relative] = {"expected": expected, "actual": actual}
        if actual != expected:
            failures.append(f"{relative} blob {actual} != incident {expected}")
    for relative in RECORDED_BLOBS:
        path = REPO_ROOT / relative
        blobs[relative] = {"actual": _git_blob(path) if path.is_file() else None}
    blobs[Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()] = {
        "actual": _git_blob(Path(__file__).resolve()),
        "sha256": _sha256(Path(__file__).resolve()),
    }
    report.data["provenance"] = {"git_head": _observe(_git_head), "blobs": blobs}

    layouts = {
        "target": (incident.SHEET_LAYOUTS[TARGET_SHEET], incident.SHEET_SCALES[TARGET_SHEET]),
        "donor": (incident.SHEET_LAYOUTS[PASTED_SHEET], incident.SHEET_SCALES[PASTED_SHEET]),
    }
    for role, (layout, scale) in layouts.items():
        if layout is not DrawingLayout.PORTRAIT or tuple(scale) != (1.0, 5.0):
            failures.append(f"incident {role} sheet is {layout} {scale}, expected portrait 1:5")
    report.data["templates_declared"] = {
        str(layout): {
            "path": str(spec.path.relative_to(REPO_ROOT).as_posix()),
            "width_m": spec.width_m,
            "height_m": spec.height_m,
            "sha256": _sha256(spec.path) if spec.path.is_file() else None,
        }
        for layout, spec in DRAWING_TEMPLATES.items()
    }
    report.data["incident_sheets"] = {
        "target": {"name": TARGET_SHEET, "layout": str(layouts["target"][0]), "scale": list(layouts["target"][1])},
        "donor": {"name": PASTED_SHEET, "layout": str(layouts["donor"][0]), "scale": list(layouts["donor"][1])},
    }
    report.checkpoint("preflight", {"failures": failures})
    if failures:
        raise ProbeMalfunction("preflight refused: " + "; ".join(failures))


# ---------------------------------------------------------------------------
# Clipboard metadata (Win32, non-mutating, non-locking)
# ---------------------------------------------------------------------------


class _ClipboardSlot:
    """Preallocated storage for one in-interval observation."""

    __slots__ = ("label", "formats", "count", "count_pointer", "raw")

    def __init__(self, label: str) -> None:
        self.label = label
        self.formats = (wintypes.UINT * CLIPBOARD_FORMAT_CAPACITY)()
        self.count = wintypes.UINT(0)
        self.count_pointer = ctypes.pointer(self.count)
        self.raw: tuple[Any, ...] | None = None


class _Clipboard:
    def __init__(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        prototypes = (
            (user32.GetClipboardSequenceNumber, [], wintypes.DWORD),
            (user32.GetClipboardOwner, [], wintypes.HWND),
            (user32.GetOpenClipboardWindow, [], wintypes.HWND),
            (
                user32.GetUpdatedClipboardFormats,
                [ctypes.POINTER(wintypes.UINT), wintypes.UINT, ctypes.POINTER(wintypes.UINT)],
                wintypes.BOOL,
            ),
            (
                user32.GetClipboardFormatNameW,
                [wintypes.UINT, wintypes.LPWSTR, ctypes.c_int],
                ctypes.c_int,
            ),
            (user32.IsWindow, [wintypes.HWND], wintypes.BOOL),
            (
                user32.GetWindowThreadProcessId,
                [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
                wintypes.DWORD,
            ),
            (user32.GetProcessWindowStation, [], wintypes.HANDLE),
            (
                user32.GetUserObjectInformationW,
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            ),
            (
                kernel32.OpenProcess,
                [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                wintypes.HANDLE,
            ),
            (
                kernel32.QueryFullProcessImageNameW,
                [
                    wintypes.HANDLE,
                    wintypes.DWORD,
                    wintypes.LPWSTR,
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            ),
            (kernel32.CloseHandle, [wintypes.HANDLE], wintypes.BOOL),
            (
                kernel32.ProcessIdToSessionId,
                [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)],
                wintypes.BOOL,
            ),
            (kernel32.GetCurrentProcessId, [], wintypes.DWORD),
        )
        for function, argtypes, restype in prototypes:
            function.argtypes = argtypes
            function.restype = restype
        self.user32 = user32
        self.kernel32 = kernel32
        self._sequence = user32.GetClipboardSequenceNumber
        self._owner = user32.GetClipboardOwner
        self._opener = user32.GetOpenClipboardWindow
        self._formats = user32.GetUpdatedClipboardFormats

    def take(self, slot: _ClipboardSlot) -> None:
        """In-interval observation: four Win32 reads into preallocated storage."""
        set_error = ctypes.set_last_error
        get_error = ctypes.get_last_error
        at = time.perf_counter_ns()
        set_error(0)
        sequence = self._sequence()
        sequence_error = get_error()
        set_error(0)
        owner = self._owner()
        owner_error = get_error()
        set_error(0)
        opener = self._opener()
        opener_error = get_error()
        set_error(0)
        listed = self._formats(slot.formats, CLIPBOARD_FORMAT_CAPACITY, slot.count_pointer)
        formats_error = get_error()
        slot.raw = (
            at,
            sequence,
            sequence_error,
            owner,
            owner_error,
            opener,
            opener_error,
            listed,
            formats_error,
        )

    # ---- resolution AFTER the critical interval ----

    def _last_error_call(self, call: Callable[[], Any]) -> tuple[Any, int]:
        ctypes.set_last_error(0)
        value = call()
        return value, ctypes.get_last_error()

    def session_of(self, pid: int) -> dict[str, Any]:
        session = wintypes.DWORD(0)
        ok, error = self._last_error_call(
            lambda: self.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session))
        )
        return {"session_id": int(session.value)} if ok else {"session_error": error}

    def image_of(self, pid: int) -> dict[str, Any]:
        handle, error = self._last_error_call(
            lambda: self.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        )
        if not handle:
            return {"image_error": error}
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            ok, error = self._last_error_call(
                lambda: self.kernel32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(size)
                )
            )
            return {"image": buffer.value} if ok else {"image_error": error}
        finally:
            self.kernel32.CloseHandle(handle)

    def window(self, hwnd: int | None, *, seat_pid: Any) -> dict[str, Any] | None:
        if hwnd is None:
            return None
        pid = wintypes.DWORD(0)
        thread, error = self._last_error_call(
            lambda: self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        )
        result: dict[str, Any] = {
            "hwnd": int(hwnd),
            "resolved_after_interval": True,
            "is_window_at_resolution": bool(self.user32.IsWindow(hwnd)),
            "thread_id": int(thread),
        }
        if not thread:
            result["thread_process_error"] = error
            return result
        result["pid"] = int(pid.value)
        result["is_seat_process"] = (
            int(pid.value) == seat_pid if isinstance(seat_pid, int) else None
        )
        result.update(self.image_of(int(pid.value)))
        result.update(self.session_of(int(pid.value)))
        return result

    def format_name(self, format_id: int) -> dict[str, Any]:
        if format_id in _STANDARD_CLIPBOARD_FORMATS:
            return {"id": format_id, "name": _STANDARD_CLIPBOARD_FORMATS[format_id]}
        if 0x200 <= format_id <= 0x2FF:
            return {"id": format_id, "name": f"CF_PRIVATEFIRST+{format_id - 0x200}"}
        if 0x300 <= format_id <= 0x3FF:
            return {"id": format_id, "name": f"CF_GDIOBJFIRST+{format_id - 0x300}"}
        if format_id >= 0xC000:
            buffer = ctypes.create_unicode_buffer(256)
            length, error = self._last_error_call(
                lambda: self.user32.GetClipboardFormatNameW(format_id, buffer, len(buffer))
            )
            if length:
                return {"id": format_id, "registered": buffer.value}
            return {"id": format_id, "registered_name_error": error}
        return {"id": format_id, "name": None}

    def describe(self, slot: _ClipboardSlot, *, seat_pid: Any) -> dict[str, Any]:
        if slot.raw is None:
            return {"label": slot.label, "taken": False}
        (
            at,
            sequence,
            sequence_error,
            owner,
            owner_error,
            opener,
            opener_error,
            listed,
            formats_error,
        ) = slot.raw
        count = int(slot.count.value)
        ids = (
            [int(value) for value in slot.formats[:count]]
            if listed and count <= CLIPBOARD_FORMAT_CAPACITY
            else None
        )
        return {
            "label": slot.label,
            "taken": True,
            "perf_counter_ns": at,
            "sequence": {
                "value": int(sequence),
                "last_error_raw": sequence_error,
                "qualifier": (
                    "zero: no clipboard access or unavailable; NOT evidence of an empty clipboard"
                    if sequence == 0
                    else "nonzero sequence observed; delayed rendering need not increment it"
                ),
            },
            "owner": {
                "hwnd": None if owner is None else int(owner),
                "last_error": owner_error,
                "qualifier": (
                    "non-null owner window observed"
                    if owner is not None
                    else (
                        "null owner, no error: not owned by a window; NOT proof that no data is present"
                        if owner_error == 0
                        else "null owner WITH error: the call failed"
                    )
                ),
                "resolved": self.window(owner, seat_pid=seat_pid),
            },
            "open_window": {
                "hwnd": None if opener is None else int(opener),
                "last_error": opener_error,
                "qualifier": (
                    "a window held the clipboard open"
                    if opener is not None
                    else (
                        "null, no error: no window reported; NOT proof of unlocked (null-owner opens are possible)"
                        if opener_error == 0
                        else "null WITH error: the call failed"
                    )
                ),
                "resolved": self.window(opener, seat_pid=seat_pid),
            },
            "formats": {
                "call_succeeded": bool(listed),
                "count_out": count,
                "capacity": CLIPBOARD_FORMAT_CAPACITY,
                "last_error": formats_error,
                "buffer_too_small": (not listed) and formats_error == _ERROR_INSUFFICIENT_BUFFER,
                "ids": ids,
                "names": None if ids is None else [self.format_name(i) for i in ids],
            },
        }

    def process_context(self) -> dict[str, Any]:
        pid = int(self.kernel32.GetCurrentProcessId())
        context: dict[str, Any] = {"pid": pid, **self.session_of(pid)}
        station, error = self._last_error_call(self.user32.GetProcessWindowStation)
        if not station:
            context["window_station_error"] = error
            return context
        buffer = ctypes.create_unicode_buffer(256)
        needed = wintypes.DWORD(0)
        ok, error = self._last_error_call(
            lambda: self.user32.GetUserObjectInformationW(
                station, _UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
            )
        )
        if ok:
            context["window_station"] = buffer.value
        else:
            context["window_station_error"] = error
        return context


# ---------------------------------------------------------------------------
# Native evidence outside the critical interval
# ---------------------------------------------------------------------------


def _sheet_state(sheet: Any) -> dict[str, Any]:
    sheet = _early_bound(sheet, "ISheet")
    return {
        "name": _observe(lambda: sheet.GetName()),
        "properties2": _observe(lambda: sheet.GetProperties2()),
        "template_name": _observe(lambda: sheet.GetTemplateName()),
        "sheet_format_name": _observe(lambda: sheet.GetSheetFormatName()),
    }


def _drawing_state(model: Any) -> dict[str, Any]:
    def read() -> dict[str, Any]:
        doc = _early_bound(model, "IModelDoc2")
        drawing = _early_bound(model, "IDrawingDoc")
        return {
            "title": _observe(lambda: doc.GetTitle()),
            "path": _observe(lambda: doc.GetPathName()),
            "type": _observe(lambda: doc.GetType()),
            "save_flag": _observe(lambda: doc.GetSaveFlag()),
            "edit_sheet": _observe(lambda: drawing.GetEditSheet()),
            "sheet_names": _observe(lambda: drawing.GetSheetNames()),
            "current_sheet": _observe(lambda: _sheet_state(drawing.GetCurrentSheet())),
        }

    state = _observe(read)
    return state["value"] if state["ok"] else state


def _active_relations(app: Any, named: dict[str, Any]) -> dict[str, Any]:
    try:
        handle = app.ActiveDoc
    except Exception as exc:  # noqa: BLE001 - captured as evidence
        return {"active_doc": {"ok": False, "error": _error(exc)}}
    relations: dict[str, Any] = {"active_is_null": handle is None}
    if handle is not None:
        relations["active_title"] = _observe(
            lambda: _early_bound(handle, "IModelDoc2").GetTitle()
        )
        for name, model in named.items():
            relations[f"is_same_{name}"] = _observe(
                lambda model=model: int(app.IsSame(handle, model))
            )
    return relations


def _selection_state(app: Any, model: Any, expected_sheet: Any) -> dict[str, Any]:
    def read() -> dict[str, Any]:
        manager = _early_bound(_early_bound(model, "IModelDoc2").SelectionManager, "ISelectionMgr")
        count_all = int(manager.GetSelectedObjectCount2(-1))
        state: dict[str, Any] = {
            "count_all_marks": count_all,
            "count_unmarked": _observe(lambda: int(manager.GetSelectedObjectCount2(0))),
            "items": [],
        }
        for index in range(1, min(count_all, SELECTION_BOUND) + 1):
            item: dict[str, Any] = {
                "index": index,
                "type": _observe(lambda i=index: int(manager.GetSelectedObjectType3(i, -1))),
                "mark": _observe(lambda i=index: int(manager.GetSelectedObjectMark(i))),
            }
            try:
                obj = manager.GetSelectedObject6(index, -1)
            except Exception as exc:  # noqa: BLE001 - captured as evidence
                item["object"] = {"ok": False, "error": _error(exc)}
                obj = None
            else:
                item["object"] = {"ok": True, "is_null": obj is None}
            if obj is not None:
                item["sheet_name"] = _observe(lambda o=obj: _early_bound(o, "ISheet").GetName())
                if expected_sheet is not None:
                    item["is_same_expected_sheet"] = _observe(
                        lambda o=obj: int(app.IsSame(o, expected_sheet))
                    )
            state["items"].append(item)
        state["truncated"] = count_all > SELECTION_BOUND
        return state

    state = _observe(read)
    return state["value"] if state["ok"] else state


def _selection_matches(state: dict[str, Any], expected_name: str) -> bool:
    items = state.get("items")
    if state.get("count_all_marks") != 1 or not items:
        return False
    item = items[0]
    return (
        item.get("type", {}).get("value") == SW_SEL_SHEETS
        and item.get("sheet_name", {}).get("value") == expected_name
        and item.get("is_same_expected_sheet", {}).get("value") == 1
    )


# ---------------------------------------------------------------------------
# Session ownership
# ---------------------------------------------------------------------------


class Session:
    """Owned native state: the read-only source, what it loads, fresh drawings."""

    def __init__(self, adapter: Any, report: Report) -> None:
        self.adapter = adapter
        self.app = _early_bound(adapter.swApp, "ISldWorks")
        self.report = report
        self.clipboard = _Clipboard()
        self.source: Any = None
        self.source_claims: dict[str, Any] = {}
        self.fresh: list[tuple[str, Any]] = []
        self.native_pastes = 0
        self.seat_pid: Any = None
        self.working_directory: str | None = None

    # ---- inventory ----

    def documents(self) -> list[Any]:
        return [_early_bound(raw, "IModelDoc2") for raw in self.app.GetDocuments() or ()]

    def assert_owned_inventory(self, phase: str) -> int:
        documents = self.documents()
        for document in documents:
            path = str(document.GetPathName() or "")
            if path:
                claimed = self.source_claims.get(os.path.normcase(str(Path(path).resolve())))
                if claimed is None or int(self.app.IsSame(claimed, document)) != 1:
                    raise ProbeMalfunction(f"{phase}: unowned native document {path!r}")
                continue
            if not any(int(self.app.IsSame(handle, document)) == 1 for _, handle in self.fresh):
                raise ProbeMalfunction(
                    f"{phase}: unowned unsaved native document {document.GetTitle()!r}"
                )
        return len(documents)

    def claim_fresh(self, role: str, model: Any) -> Any:
        model = _early_bound(model, "IModelDoc2")
        if model is None:
            raise ProbeMalfunction(f"{role}: no document returned")
        if str(model.GetPathName() or ""):
            raise ProbeMalfunction(f"{role}: fresh drawing unexpectedly has a path")
        self.fresh.append((role, model))
        return model

    def close_fresh(self, role: str) -> dict[str, Any]:
        """CloseDoc one owned unsaved drawing by its exact current title."""
        index = next(i for i, (name, _) in enumerate(self.fresh) if name == role)
        model = self.fresh[index][1]
        title = str(model.GetTitle() or "")
        if not title:
            raise ProbeMalfunction(f"{role}: refusing CloseDoc('') on an owned drawing")
        before = self.documents()
        if not any(int(self.app.IsSame(model, document)) == 1 for document in before):
            raise ProbeMalfunction(f"{role}: owned drawing is no longer open")
        returned = self.app.CloseDoc(title)
        remaining = self.documents()
        titles = [str(document.GetTitle() or "") for document in remaining]
        if title in titles or len(remaining) != len(before) - 1:
            raise ProbeMalfunction(f"{role}: owned drawing {title!r} did not close")
        del self.fresh[index]
        return {"role": role, "title": title, "close_doc_returned": _jsonable(returned)}

    # ---- source ----

    def open_source(self) -> dict[str, Any]:
        if self.app.GetDocuments() or self.app.ActiveDoc is not None:
            raise ProbeMalfunction("probe requires an EMPTY document inventory; nothing closed")
        self.working_directory = str(self.app.GetCurrentWorkingDirectory() or "")
        result = self.app.OpenDoc6(str(SOURCE), SW_DOC_ASSEMBLY, OPEN_SILENT_READ_ONLY, "", 0, 0)
        model, errors, warnings = (result + (None, None))[:3] if isinstance(result, tuple) else (result, None, None)
        evidence = {
            "call": "ISldWorks.OpenDoc6(path, swDocASSEMBLY, Silent|ReadOnly, '', 0, 0)",
            "errors": _jsonable(errors),
            "warnings": _jsonable(warnings),
            "returned_null": model is None,
        }
        documents = self.documents()
        # The session started empty, so every document now resident was loaded
        # by this open: claim them all (the source and its referenced models).
        for document in documents:
            path = str(document.GetPathName() or "")
            if not path:
                raise ProbeMalfunction("opening the source loaded an unsaved document")
            key = os.path.normcase(str(Path(path).resolve()))
            if key in self.source_claims:
                raise ProbeMalfunction(f"ambiguous native document path {path!r}")
            self.source_claims[key] = document
        if model is None:
            raise ProbeMalfunction(f"source open failed: {evidence}")
        self.source = _early_bound(model, "IModelDoc2")
        source_key = os.path.normcase(str(SOURCE.resolve()))
        claimed = self.source_claims.get(source_key)
        if claimed is None or int(self.app.IsSame(claimed, self.source)) != 1:
            raise ProbeMalfunction("opened document is not the exact source path")
        if int(self.source.GetType()) != SW_DOC_ASSEMBLY:
            raise ProbeMalfunction("source is not an assembly document")
        self.adapter.currentModel = self.source
        evidence.update(
            path=_observe(lambda: self.source.GetPathName()),
            title=_observe(lambda: self.source.GetTitle()),
            opened_read_only=_observe(lambda: self.source.IsOpenedReadOnly()),
            save_flag=_observe(lambda: self.source.GetSaveFlag()),
            claimed_documents=len(self.source_claims),
            working_directory_before_open=self.working_directory,
        )
        return evidence

    def close_all(self) -> dict[str, Any]:
        """Close every owned document; never one this probe did not claim."""
        result: dict[str, Any] = {
            "fresh": [self.close_fresh(role) for role, _ in list(self.fresh)]
        }
        if self.source is None:
            if self.app.GetDocuments():
                raise ProbeMalfunction("failed open left unclaimed documents; cleanup refused")
        else:
            self.assert_owned_inventory("final close")
            source_title = str(self.source.GetTitle() or "")
            if not source_title:
                raise ProbeMalfunction("refusing CloseDoc('') on the source assembly")
            closes = [
                {"title": source_title, "returned": _jsonable(self.app.CloseDoc(source_title))}
            ]
            self.source = None
            for _ in range(len(self.source_claims)):
                remaining = self.documents()
                if not remaining:
                    break
                self.assert_owned_inventory("final close residue")
                title = str(remaining[0].GetTitle() or "")
                if not title:
                    raise ProbeMalfunction("refusing CloseDoc('') on an owned residue")
                closes.append({"title": title, "returned": _jsonable(self.app.CloseDoc(title))})
                if len(self.documents()) >= len(remaining):
                    raise ProbeMalfunction(f"owned residue {title!r} did not close")
            if self.app.GetDocuments() or self.app.ActiveDoc is not None:
                raise ProbeMalfunction("owned documents remain after final close")
            result["source"] = closes
        self.adapter.currentModel = None
        result["working_directory_restored"] = None
        current = str(self.app.GetCurrentWorkingDirectory() or "")
        if self.working_directory and current != self.working_directory:
            # Opening moved the seat into this checkout; put back what was observed.
            if self.app.SetCurrentWorkingDirectory(self.working_directory) is not True:
                raise ProbeMalfunction("seat working directory restore rejected")
            if str(self.app.GetCurrentWorkingDirectory() or "") != self.working_directory:
                raise ProbeMalfunction("seat working directory restore differs")
            result["working_directory_restored"] = {
                "from": current,
                "to": self.working_directory,
            }
        return result

    # ---- seat ----

    def annotation_preferences(self) -> dict[str, int]:
        return {
            str(pref): int(self.app.GetUserPreferenceIntegerValue(pref))
            for pref in SEAT_ANNOTATION_PREFERENCES
        }


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def _paste_outcome(before: tuple[str, ...], after: tuple[str, ...]) -> tuple[str, list[str]]:
    added = [name for name in after if name not in before]
    if len(after) == len(before) + 1 and len(added) == 1:
        return "pasted", added
    if after == before:
        return "paste_created_no_sheet", added
    return "paste_inventory_anomalous", added


def _guard_paste_budget(session: Session, case_id: str) -> None:
    if session.native_pastes >= MAX_NATIVE_PASTES:
        raise ProbeMalfunction(f"{case_id}: native PasteSheet budget ({MAX_NATIVE_PASTES}) exhausted")


def _rename_pasted(drawing: Any, added: str) -> dict[str, Any]:
    """Production's post-paste step: activate the new sheet and name it."""
    result: dict[str, Any] = {}
    try:
        activated = drawing.ActivateSheet(added)
        result["activate_sheet_returned"] = _jsonable(activated)
        if not activated:
            return result
        sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
        sheet.SetName(PASTED_SHEET)
        result["renamed_to"] = str(sheet.GetName() or "")
        result["rename_ok"] = result["renamed_to"] == PASTED_SHEET
        result["pasted_sheet"] = _sheet_state(sheet)
    except Exception as exc:  # noqa: BLE001 - post-paste data, not a malfunction
        result["error"] = _error(exc)
    return result


def _cross_document_case(
    session: Session,
    case_id: str,
    *,
    activation_option: int,
    select_target: bool,
) -> dict[str, Any]:
    """``_create_mixed_package_sheets`` + ``_append_template_sheet`` for the
    first appended sheet, with exactly one declared delta."""
    adapter, app, clipboard = session.adapter, session.app, session.clipboard
    record: dict[str, Any] = {
        "case": case_id,
        "kind": "cross_document",
        "activation_call": f"ActivateDoc3(title, False, {activation_option}, 0)",
        "accepted_activation_errors": (
            [0, ACTIVATE_NEEDS_REBUILD_WARNING]
            if activation_option == DONT_REBUILD_ACTIVE_DOC
            else [0]
        ),
        "select_target_before_paste": select_target,
        "paste_call": f"PasteSheet({INSERT_MOVE_TO_END}, {RENAME_NO})",
    }
    # Target, as _create_mixed_package_sheets.
    target, initial = new_project_drawing(
        adapter,
        layout=incident.SHEET_LAYOUTS[TARGET_SHEET],
        scale=incident.SHEET_SCALES[TARGET_SHEET],
    )
    target = session.claim_fresh(f"{case_id}:target", target)
    initial = _early_bound(initial, "ISheet")
    initial.SetName(TARGET_SHEET)
    if str(initial.GetName() or "") != TARGET_SHEET:
        raise ProbeMalfunction(f"{case_id}: failed to name the target's primary sheet")
    # Donor, as _append_template_sheet.
    donor, donor_sheet = new_project_drawing(
        adapter,
        layout=incident.SHEET_LAYOUTS[PASTED_SHEET],
        scale=incident.SHEET_SCALES[PASTED_SHEET],
    )
    donor = session.claim_fresh(f"{case_id}:donor", donor)
    donor_sheet = _early_bound(donor_sheet, "ISheet")
    donor_title = str(donor.GetTitle() or "")
    donor_name = str(donor_sheet.GetName() or "")
    if not donor_title or not donor_name:
        raise ProbeMalfunction(f"{case_id}: donor drawing is incomplete")

    named = {"source": session.source, "target": target, "donor": donor}
    record["before_copy"] = {
        "documents": session.assert_owned_inventory(f"{case_id} before copy"),
        "active": _active_relations(app, named),
        "target_is_same_donor": _observe(lambda: int(app.IsSame(target, donor))),
        "target": _drawing_state(target),
        "donor": _drawing_state(donor),
        "target_initial_sheet": _sheet_state(initial),
        "donor_sheet": _sheet_state(donor_sheet),
    }
    donor.ClearSelection2(True)
    record["selection_after_clear"] = _selection_state(app, donor, donor_sheet)
    callout = null_callout()
    selected = donor.Extension.SelectByID2(
        donor_name, "SHEET", 0.0, 0.0, 0.0, False, 0, callout, 0
    )
    record["donor_select_returned"] = _jsonable(selected)
    if not selected:
        raise ProbeMalfunction(f"{case_id}: failed to select donor sheet {donor_name!r}")
    record["selection_before_copy"] = _selection_state(app, donor, donor_sheet)
    record["selection_is_named_donor_sheet"] = _selection_matches(
        record["selection_before_copy"], donor_name
    )

    slots = {
        label: _ClipboardSlot(label)
        for label in ("pre_copy", "post_copy", "post_activate", "post_paste", "at_exception")
    }
    _guard_paste_budget(session, case_id)
    stage = "edit_copy"
    failure: BaseException | None = None
    refusal: str | None = None
    title = ""
    activation: Any = None
    activated: Any = None
    errors: Any = None
    fallback_active_doc = False
    identity: Any = None
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    target_selected: Any = None
    returned: Any = None
    pasted_call = False
    # ---- critical interval: native calls + buffered clipboard reads only ----
    clipboard.take(slots["pre_copy"])
    try:
        donor.EditCopy()
        clipboard.take(slots["post_copy"])
        stage = "activate"
        # Clone of _activate_package (rebuild option is the B delta).
        title = str(target.GetTitle() or "")
        if not title:
            refusal = "empty_target_title"
        else:
            activation = app.ActivateDoc3(title, False, activation_option, 0)
            clipboard.take(slots["post_activate"])
            if not activation:
                refusal = "activation_returned_nothing"
            else:
                activated, errors = activation
                if int(errors) not in (
                    (0, ACTIVATE_NEEDS_REBUILD_WARNING)
                    if activation_option == DONT_REBUILD_ACTIVE_DOC
                    else (0,)
                ):
                    refusal = "activation_errors"
                else:
                    if activated is None:
                        fallback_active_doc = True
                        activated = app.ActiveDoc
                    identity = None if activated is None else int(app.IsSame(activated, target))
                    if identity != 1:
                        refusal = "activated_document_is_not_target"
                    else:
                        adapter.currentModel = _early_bound(activated, "IModelDoc2")
        if refusal is None:
            stage = "inventory_before"
            ddoc = _early_bound(target, "IDrawingDoc")
            before = tuple(ddoc.GetSheetNames() or ())
            if select_target:
                stage = "select_target"
                target_selected = target.Extension.SelectByID2(
                    TARGET_SHEET, "SHEET", 0.0, 0.0, 0.0, False, 0, callout, 0
                )
            stage = "paste"
            session.native_pastes += 1
            pasted_call = True
            returned = ddoc.PasteSheet(INSERT_MOVE_TO_END, RENAME_NO)
            clipboard.take(slots["post_paste"])
            stage = "inventory_after"
            after = tuple(ddoc.GetSheetNames() or ())
    except Exception as exc:  # noqa: BLE001 - a native case failure is data
        clipboard.take(slots["at_exception"])
        failure = exc
    # ---- end of critical interval ----

    record["activation"] = {
        "target_title": title,
        "returned_tuple": isinstance(activation, tuple),
        "activated_is_null": None if activation is None else activated is None,
        "errors": _jsonable(errors),
        "errors_meaning": {
            0: "none",
            ACTIVATE_GENERIC_ERROR: "swGenericActivateError (document not activated)",
            ACTIVATE_NEEDS_REBUILD_WARNING: "swDocNeedsRebuildWarning (activated, not rebuilt)",
        }.get(errors if isinstance(errors, int) else -1, "other/unknown"),
        "fallback_active_doc_used": fallback_active_doc,
        "is_same_target": identity,
        "refusal": refusal,
    }
    if select_target:
        record["target_select_returned"] = _jsonable(target_selected)
    record["native_paste_called"] = pasted_call
    record["paste_returned_raw"] = _jsonable(returned)
    record["paste_returned_bool"] = bool(returned) if pasted_call and failure is None else None
    record["inventory_before_paste"] = list(before)
    record["inventory_after_paste"] = list(after)
    if failure is not None:
        record["outcome"] = f"{stage}_raised"
        record["failure"] = {"stage": stage, "error": _error(failure)}
        added: list[str] = []
    elif refusal is not None:
        record["outcome"] = "activation_refused"
        added = []
    else:
        record["outcome"], added = _paste_outcome(before, after)
    record["added_sheets"] = added
    record["delta_applied"] = bool(target_selected) if select_target else True
    record["passed"] = record["outcome"] == "pasted" and record["delta_applied"]
    record["reproduces_incident_paste_failure"] = record["outcome"] in INCIDENT_PASTE_FAILURES
    seat_pid = session.seat_pid
    record["clipboard"] = [
        clipboard.describe(slot, seat_pid=seat_pid) for slot in slots.values()
    ]
    record["after_paste"] = {
        "active": _active_relations(app, named),
        "target": _drawing_state(target),
        "target_selection": _selection_state(app, target, None),
        "donor": _drawing_state(donor),
    }
    if record["outcome"] == "pasted":
        record["post_paste_rename"] = _rename_pasted(
            _early_bound(target, "IDrawingDoc"), added[0]
        )
        if record["paste_returned_bool"] is False:
            record["returned_false_but_created"] = True
    return record


def _same_document_case(session: Session, case_id: str) -> dict[str, Any]:
    """First attempt of ``create_blank_drawing_sheets`` on a fresh portrait
    1:5 drawing: ASSEMBLED duplicated into the same document."""
    adapter, app, clipboard = session.adapter, session.app, session.clipboard
    record: dict[str, Any] = {
        "case": case_id,
        "kind": "same_document_positive_control",
        "paste_call": f"PasteSheet({INSERT_MOVE_TO_END}, {RENAME_NO})",
    }
    draw, _ = new_project_drawing(
        adapter,
        layout=incident.SHEET_LAYOUTS[TARGET_SHEET],
        scale=incident.SHEET_SCALES[TARGET_SHEET],
    )
    draw = session.claim_fresh(f"{case_id}:drawing", draw)
    ddoc = _early_bound(draw, "IDrawingDoc")
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise ProbeMalfunction(f"{case_id}: drawing template has no initial sheet")
    initial_names = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    if len(initial_names) != 1:
        raise ProbeMalfunction(f"{case_id}: template has {len(initial_names)} sheets")
    if next(iter_views(adapter), None) is not None:
        raise ProbeMalfunction(f"{case_id}: initial drawing sheet is not blank")
    sheet.SetName(TARGET_SHEET)
    if str(adapter._get_attr_or_call(sheet, "GetName") or "") != TARGET_SHEET:
        raise ProbeMalfunction(f"{case_id}: failed to rename initial sheet")
    if not ddoc.ActivateSheet(TARGET_SHEET):
        raise ProbeMalfunction(f"{case_id}: failed to activate {TARGET_SHEET!r}")
    before = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    reference = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    named = {"source": session.source, "drawing": draw}
    record["before_copy"] = {
        "documents": session.assert_owned_inventory(f"{case_id} before copy"),
        "active": _active_relations(app, named),
        "drawing": _drawing_state(draw),
        "sheet": _sheet_state(reference),
    }
    draw.ClearSelection2(True)
    record["selection_after_clear"] = _selection_state(app, draw, reference)
    selected = draw.Extension.SelectByID2(
        TARGET_SHEET, "SHEET", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    record["select_returned"] = _jsonable(selected)
    if not selected:
        raise ProbeMalfunction(f"{case_id}: failed to select {TARGET_SHEET!r}")
    record["selection_before_copy"] = _selection_state(app, draw, reference)
    record["selection_is_named_sheet"] = _selection_matches(
        record["selection_before_copy"], TARGET_SHEET
    )

    slots = {
        label: _ClipboardSlot(label)
        for label in ("pre_copy", "post_copy", "post_paste", "at_exception")
    }
    _guard_paste_budget(session, case_id)
    stage = "edit_copy"
    failure: BaseException | None = None
    after: tuple[str, ...] = ()
    returned: Any = None
    pasted_call = False
    # ---- critical interval: native calls + buffered clipboard reads only ----
    clipboard.take(slots["pre_copy"])
    try:
        draw.EditCopy()
        clipboard.take(slots["post_copy"])
        stage = "paste"
        session.native_pastes += 1
        pasted_call = True
        returned = ddoc.PasteSheet(INSERT_MOVE_TO_END, RENAME_NO)
        clipboard.take(slots["post_paste"])
        stage = "inventory_after"
        after = tuple(adapter._get_attr_or_call(ddoc, "GetSheetNames") or ())
    except Exception as exc:  # noqa: BLE001 - a native case failure is data
        clipboard.take(slots["at_exception"])
        failure = exc
    # ---- end of critical interval ----

    record["native_paste_called"] = pasted_call
    record["paste_returned_raw"] = _jsonable(returned)
    record["paste_returned_bool"] = bool(returned) if pasted_call and failure is None else None
    record["inventory_before_paste"] = list(before)
    record["inventory_after_paste"] = list(after)
    if failure is not None:
        record["outcome"] = f"{stage}_raised"
        record["failure"] = {"stage": stage, "error": _error(failure)}
        added: list[str] = []
    else:
        record["outcome"], added = _paste_outcome(before, after)
    record["added_sheets"] = added
    record["delta_applied"] = True
    record["passed"] = record["outcome"] == "pasted"
    record["reproduces_incident_paste_failure"] = record["outcome"] in INCIDENT_PASTE_FAILURES
    record["clipboard"] = [
        clipboard.describe(slot, seat_pid=session.seat_pid) for slot in slots.values()
    ]
    record["after_paste"] = {
        "active": _active_relations(app, named),
        "drawing": _drawing_state(draw),
        "selection": _selection_state(app, draw, None),
    }
    if record["outcome"] == "pasted":
        record["post_paste_rename"] = _rename_pasted(ddoc, added[0])
        if record["paste_returned_bool"] is False:
            record["returned_false_but_created"] = True
    return record


def _run_case(session: Session, case_id: str, run: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """One case, then close exactly its owned drawings (donor first, as
    production does); a setup or cleanup failure is a malfunction."""
    report = session.report
    started = _utc_now()
    pastes_before = session.native_pastes
    record: dict[str, Any] | None = None
    errors: list[BaseException] = []
    with _telemetry.span("paste_sheet_probe.case", case=case_id):
        try:
            record = run()
        except Exception as exc:  # noqa: BLE001 - re-raised below
            errors.append(exc)
        cleanup: list[dict[str, Any]] = []
        for suffix in ("donor", "target", "drawing"):
            role = f"{case_id}:{suffix}"
            if any(name == role for name, _ in session.fresh):
                try:
                    cleanup.append(session.close_fresh(role))
                except Exception as exc:  # noqa: BLE001 - re-raised below
                    errors.append(exc)
                    break
        session.adapter.currentModel = session.source
    if errors:
        partial = record or {"case": case_id}
        partial["cleanup"] = cleanup
        report.data["cases"].append(partial)
        if len(errors) == 1:
            raise errors[0]
        raise ExceptionGroup(f"{case_id}: case and cleanup failed", errors)
    assert record is not None
    record["started_at"] = started
    record["finished_at"] = _utc_now()
    record["native_paste_calls_in_case"] = session.native_pastes - pastes_before
    record["cleanup"] = cleanup
    record["after_cleanup"] = {
        "documents": session.assert_owned_inventory(f"{case_id} after cleanup"),
        "active": _active_relations(session.app, {"source": session.source}),
        "seat_pid": _observe(lambda: int(session.app.GetProcessID())),
    }
    seat_pid = record["after_cleanup"]["seat_pid"].get("value")
    if seat_pid != session.seat_pid:
        report.data["cases"].append(record)
        raise ProbeMalfunction(f"{case_id}: seat PID changed {session.seat_pid} -> {seat_pid}")
    report.data["cases"].append(record)
    report.data["native_paste_calls"] = session.native_pastes
    report.checkpoint(
        f"case-{case_id}",
        {
            "case": case_id,
            "outcome": record["outcome"],
            "passed": record["passed"],
            "reproduces_incident_paste_failure": record["reproduces_incident_paste_failure"],
            "paste_returned_raw": record["paste_returned_raw"],
            "before": record["inventory_before_paste"],
            "after": record["inventory_after_paste"],
            "activation": {
                key: record.get("activation", {}).get(key)
                for key in ("errors", "is_same_target", "refusal")
            },
            "clipboard_sequence": {
                item["label"]: item.get("sequence", {}).get("value")
                for item in record["clipboard"]
                if item.get("taken")
            },
            "native_paste_calls": session.native_pastes,
        },
    )
    return record


# ---------------------------------------------------------------------------
# Matrix and classification
# ---------------------------------------------------------------------------

CROSS_DOCUMENT_CASES = {
    "A0": {"activation_option": REBUILD_ACTIVE_DOC, "select_target": False},
    "B": {"activation_option": DONT_REBUILD_ACTIVE_DOC, "select_target": False},
    "C": {"activation_option": REBUILD_ACTIVE_DOC, "select_target": True},
    "A1": {"activation_option": REBUILD_ACTIVE_DOC, "select_target": False},
}


def _repeat_variant(cases: dict[str, dict[str, Any]]) -> str | None:
    if not cases["P"]["passed"]:
        return None
    if not (
        cases["A0"]["reproduces_incident_paste_failure"]
        and cases["A1"]["reproduces_incident_paste_failure"]
    ):
        return None
    passing = [name for name in ("B", "C") if cases[name]["passed"]]
    return passing[0] if len(passing) == 1 else None


def classify(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matrix = {
        name: {
            "outcome": case["outcome"],
            "passed": case["passed"],
            "reproduces_incident_paste_failure": case["reproduces_incident_paste_failure"],
        }
        for name, case in cases.items()
    }
    a0, a1, b, c = (cases[name] for name in ("A0", "A1", "B", "C"))
    if not cases["P"]["passed"]:
        verdict, reason = (
            "unhealthy_positive_control",
            "same-document control did not paste exactly one sheet; no variant success "
            "demonstrates a healthy shared copy path",
        )
    elif a0["passed"] and a1["passed"]:
        verdict, reason = "no_reproduction", "both exact incident-shape trials pasted"
    elif not (
        a0["reproduces_incident_paste_failure"] and a1["reproduces_incident_paste_failure"]
    ):
        verdict, reason = (
            "ambiguous",
            f"incident shape not consistently reproduced (A0={a0['outcome']}, A1={a1['outcome']})",
        )
    elif b["passed"] and c["passed"]:
        verdict, reason = "ambiguous", "incident reproduced; BOTH deltas pasted"
    elif not b["passed"] and not c["passed"]:
        verdict, reason = "ambiguous", "incident reproduced; NEITHER delta pasted"
    else:
        delta = "B" if b["passed"] else "C"
        repeat = cases.get(f"{delta}_repeat")
        if repeat is None:
            raise ProbeMalfunction("discriminating repeat was required but not run")
        if repeat["passed"]:
            verdict = (
                "reproducible_activation_delta"
                if delta == "B"
                else "reproducible_target_selection_delta"
            )
            reason = f"incident reproduced twice; only {delta} pasted, and its fresh repeat pasted"
        else:
            verdict, reason = (
                "ambiguous",
                f"incident reproduced; only {delta} pasted but its fresh repeat did not",
            )
    return {
        "classification": verdict,
        "reason": reason,
        "matrix": matrix,
        "rules": (
            "pass = exactly one new sheet (production's count check) with the case's delta "
            "applied; incident reproduction = production's count check failing after a "
            "PasteSheet that returned (not a raised native call or refused activation); the "
            "repeat runs only when A0 and A1 reproduce, P passes and exactly one of B/C passes"
        ),
        "limits": [
            "A verdict names which recipe delta changed this seat's observed outcome; it does "
            "not establish why, and is not a validated production fix.",
            "Clipboard metadata can positively show an owner/format/sequence transition or an "
            "open-clipboard window at the four sampled instants; it cannot exclude short-lived "
            "contention between samples.",
            "One seat and one session: a different worker or seat limits reproduction claims.",
        ],
    }


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


async def probe(adapter: Any, report: Report) -> dict[str, str]:
    session = Session(adapter, report)
    primary: BaseException | None = None
    try:
        report.data["seat"] = {"at_attach": _seat_forensics.seat_provenance(adapter)}
        session.seat_pid = int(session.app.GetProcessID())
        report.data["seat"]["pid"] = session.seat_pid
        report.data["seat"]["revision"] = _observe(lambda: session.app.RevisionNumber())
        context = session.clipboard.process_context()
        seat_session = report.data["seat"]["at_attach"].get("seat_session_id")
        report.data["clipboard_context"] = {
            "probe_process": context,
            "seat_session_id": seat_session,
            "same_session_as_seat": (
                context.get("session_id") == seat_session
                if isinstance(seat_session, int) and "session_id" in context
                else None
            ),
            "note": (
                "Clipboard metadata is read from THIS process's window station; it "
                "describes the seat's clipboard only when both run in the same session."
            ),
        }
        preferences = session.annotation_preferences()
        report.data["seat_preferences_before"] = preferences
        if any(value != _COLORREF_BLACK for value in preferences.values()):
            raise ProbeMalfunction(
                "new_project_drawing would write seat annotation preferences "
                f"{preferences}; refusing to mutate seat state"
            )

        report.data["source_open"] = session.open_source()
        # The incident build's own preamble before any sheet transfer.
        properties = read_required_properties(
            session.source,
            ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
            required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
        )
        if properties["Number"] != incident.notes.DRAWING_NUMBER:
            raise ProbeMalfunction(
                f"source Number {properties['Number']!r} != {incident.notes.DRAWING_NUMBER!r}"
            )
        incident._validate_source(session.source)
        report.data["incident_preamble"] = {
            "properties": properties,
            "validate_source": "passed",
            "documents": session.assert_owned_inventory("after preamble"),
            "active": _active_relations(session.app, {"source": session.source}),
            "source_save_flag": _observe(lambda: session.source.GetSaveFlag()),
        }
        baseline = _ClipboardSlot("session_baseline")
        session.clipboard.take(baseline)
        report.data["clipboard_baseline"] = session.clipboard.describe(
            baseline, seat_pid=session.seat_pid
        )
        report.checkpoint(
            "source-open",
            {
                "seat_pid": session.seat_pid,
                "claimed_documents": len(session.source_claims),
                "opened_read_only": report.data["source_open"]["opened_read_only"],
            },
        )

        cases: dict[str, dict[str, Any]] = {}
        for case_id in ("A0", "P", "B", "C", "A1"):
            if case_id == "P":
                cases[case_id] = _run_case(
                    session, case_id, lambda: _same_document_case(session, "P")
                )
                continue
            options = CROSS_DOCUMENT_CASES[case_id]
            cases[case_id] = _run_case(
                session,
                case_id,
                lambda case_id=case_id, options=options: _cross_document_case(
                    session, case_id, **options
                ),
            )
        repeat = _repeat_variant(cases)
        report.data["repeat_selected"] = repeat
        if repeat is not None:
            repeat_id = f"{repeat}_repeat"
            options = CROSS_DOCUMENT_CASES[repeat]
            cases[repeat_id] = _run_case(
                session,
                repeat_id,
                lambda: _cross_document_case(session, repeat_id, **options),
            )
        report.data["classification"] = classify(cases)
        report.data["seat_preferences_after"] = session.annotation_preferences()
        report.data["seat"]["after_cases"] = _seat_forensics.seat_provenance(adapter)
    except BaseException as exc:
        primary = exc
        raise
    finally:
        try:
            report.data["cleanup"] = session.close_all()
        except Exception as exc:  # noqa: BLE001 - surfaced below
            report.data["cleanup"] = {"error": _error(exc)}
            if primary is None:
                report.malfunction(exc)
                raise
            _telemetry.warn(f"paste-sheet-probe cleanup failed after a malfunction: {exc}")
        if primary is not None:
            report.malfunction(primary)

    after = _sha256(SOURCE)
    report.data["source_identity"]["source_sha256_after"] = after
    report.data["source_identity"]["source_bytes_unchanged"] = after == EXPECTED_SOURCE_TOKEN
    if after != EXPECTED_SOURCE_TOKEN:
        exc = ProbeMalfunction("source assembly bytes changed during the probe")
        report.malfunction(exc)
        raise exc
    if report.data["seat_preferences_after"] != report.data["seat_preferences_before"]:
        exc = ProbeMalfunction("seat annotation preferences changed during the probe")
        report.malfunction(exc)
        raise exc
    report.checkpoint(
        "complete",
        {
            "classification": report.data["classification"]["classification"],
            "reason": report.data["classification"]["reason"],
            "native_paste_calls": session.native_pastes,
        },
    )
    report.complete()
    return {"report": str(REPORT)}


def main() -> int:
    require_owned_diagnostic_environment()
    report = Report()
    report.data["process"] = _probe_environment()
    try:
        preflight(report)
    except Exception as exc:
        report.malfunction(exc)
        raise
    return run_owned_diagnostic(lambda adapter: probe(adapter, report))


if __name__ == "__main__":
    sys.exit(main())

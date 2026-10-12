"""Temporary display-data first-reconcile matrix on the existing pn farm leaf.

The normal pn build retains its original Copy11/reconcile/render/fingerprint
tail. After its initial Copy11, two extra copies of the still-untitled source
compare unmarked and Default-only marked serialization before any reconcile.
Two independent pn constructions set Default-only or both configurations' LDR
marks before their first-ever serialization. All use cached parts, never part builds.

All snapshots are siblings of pn-pen.SLDASM, preserving its reference directory
layout. No part build is dispatched; no part file is saved, copied, or
reference-rewritten by the probe.
Every minimal multi-config trial starts from the same single-config copy, not
the previous trial. Four normal-assembly trials each start from the
untouched normal snapshot and retain its real referenced-part configurations.
Save9 vs Save1 differs only in AvoidRebuildOnSave; the switch trial adds
ShowConfiguration2/EditRebuild3/AddRebuildSaveMark for derived then Default;
the controls preserve inherited native marks. The clear-both trial supplies an
explicitly unmarked comparator for the three selected-LDR trials and emodel
trial (OverrideSaveEmodel, 32). Nothing changes global SOLIDWORKS preferences.
Original assembly and referenced input bytes are hashed
before/after. A failed native operation aborts the leaf; parser observations never
act as a production visibility gate.

Follow-on reference trials use a separate single-Default baseline with two
hangers and one cached vn-pen-set-screw. They change references only when a real
part Default Simplified configuration exists, requiring a genuine switch.
A/B/C isolate no explicit rebuild, derived deep rebuild, then Default deep
rebuild before Copy11. Final D controls use the same C operation sequence:
Save3(1) removes both Copy and AvoidRebuildOnSave, while Save3(9) removes only
Copy and retains AvoidRebuildOnSave. They run last to contain dirty-child risk.
E reconciles an independent copy of C using the existing production helper.
F freshly reopens an independent E copy and Save3(1)-saves without explicit
switches/rebuilds/mark writes; G repeats the derived/Default EditRebuild3 and
AddRebuildSaveMark loop on another E copy before Save3(1). F still performs the
explicitly logged _state inspections (including GetComponents) before save.
Native GetSaveFlag is recorded in each state snapshot and immediately before
every diagnostic Save3, including the original helper's conditional first save.
Preserved C-mark-Default and C-mark-both copies each undergo their FIRST original
reconcile on a separate byte-identical output copy. Fresh untitled fixtures
explicitly clear both marks or mark only Default before their first-ever Copy11,
then undergo the same original first reconcile. These primary controls exclude
reopening-to-set-mark and prior serialization confounds. Actual independent pn
constructions supply Default-only and both-config production-builder counterparts;
extra same-source pn copies remain secondary because their serialization ordinals differ.
These are differential observations, not a production fix or root-cause claim.

The manifest and stdout retain native config/mark/rebuild/GetSaveFlag state,
save results, input hashes, snapshot hashes, and exploratory swfile-style raw
display flags. The original reconcile's optional diagnostic dictionary observes
only its pre-Save3 GetSaveFlag and returned native tuple; it adds no repair save.
The undocumented flag reader is NOT proof of component visibility, config
association or format completeness. Parent must compare snapshots in eDrawings.
All native snapshots and source-history JSON are declared pn-only cache outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
from enum import StrEnum
import hashlib
import json
import mmap
from pathlib import Path
import shutil
import struct
from typing import Any
import zlib


# One inventory shared with dodo's temporary pn-only cache-output declaration.
TRIALS = (
    ("add-second-save9", 9, False, None, "single-copy11"),
    ("add-second-save1", 1, False, None, "single-copy11"),
    ("switch-second-default-save1", 1, True, None, "single-copy11"),
    ("clear-both-save1", 1, True, (), "single-copy11"),
    ("mark-default-save1", 1, True, ("Default",), "single-copy11"),
    ("mark-second-save1", 1, True, ("Default Simplified",), "single-copy11"),
    ("mark-both-save1", 1, True, ("Default", "Default Simplified"), "single-copy11"),
    ("override-emodel-save33", 33, True, (), "single-copy11"),
    ("normal-resave-inherited", 1, True, None, "normal"),
    ("normal-mark-default-save1", 1, True, ("Default",), "normal"),
    ("normal-mark-second-save1", 1, True, ("Default Simplified",), "normal"),
    ("normal-mark-both-save1", 1, True, ("Default", "Default Simplified"), "normal"),
)


class ReferenceSource(StrEnum):
    THREADED_SINGLE = "single-threaded-copy11"
    BOTH_REBUILT_COPY = "refcfg-c-both-rebuild-copy11"
    RECONCILED_COPY = "refcfg-e-reconcile-save1"
    MARKED_DEFAULT_COPY = "refcfg-c-mark-default-copy11"
    MARKED_BOTH_COPY = "refcfg-c-mark-both-copy11"
    FRESH_UNMARKED_COPY = "fresh-refcfg-c-unmarked-copy11"
    FRESH_MARKED_DEFAULT_COPY = "fresh-refcfg-c-mark-default-copy11"
    NORMAL_EXTRA_UNMARKED_COPY = "normal-extra-unmarked-copy11"
    NORMAL_EXTRA_MARKED_DEFAULT_COPY = "normal-extra-mark-default-copy11"
    FRESH_THREADED = "fresh-untitled-threaded"


class ReferenceOperation(StrEnum):
    ADD_DERIVED = "add-derived-no-rebuild"
    ACTIVATE_DERIVED = "activate-derived"
    SELECT_SIMPLIFIED_REFERENCES = "select-available-simplified-references"
    REBUILD_DERIVED = "derived-ForceRebuild3(False)"
    RESTORE_DEFAULT = "restore-Default"
    REBUILD_DEFAULT = "Default-ForceRebuild3(False)"
    RECONCILE = "reconcile_saved_rebuild_state"
    REBUILD_SAVE_MARKS = "derived-Default-EditRebuild3-AddRebuildSaveMark"
    CLEAR_MARKS = "LDR-clear-both"
    MARK_DEFAULT = "LDR-mark-Default-only"
    MARK_BOTH = "LDR-mark-both"


class ReferenceSave(StrEnum):
    COPY = "IModelDoc2.SaveAs3"
    IN_PLACE = "IModelDoc2.Save3"
    RECONCILE = "reconcile_saved_rebuild_state (conditional IModelDoc2.Save3)"


@dataclass(frozen=True)
class ReferenceTrial:
    stage: str
    source: ReferenceSource
    operations: tuple[ReferenceOperation, ...]
    save_api: ReferenceSave
    save_options: int
    comparison: str | None = None


_REFERENCE_SETUP = (
    ReferenceOperation.ADD_DERIVED,
    ReferenceOperation.ACTIVATE_DERIVED,
    ReferenceOperation.SELECT_SIMPLIFIED_REFERENCES,
)
_REFERENCE_A = (*_REFERENCE_SETUP, ReferenceOperation.RESTORE_DEFAULT)
_REFERENCE_B = (
    *_REFERENCE_SETUP,
    ReferenceOperation.REBUILD_DERIVED,
    ReferenceOperation.RESTORE_DEFAULT,
)
_REFERENCE_C = (*_REFERENCE_B, ReferenceOperation.REBUILD_DEFAULT)
REFERENCE_TRIALS = (
    ReferenceTrial(
        "refcfg-a-no-rebuild-copy11",
        ReferenceSource.THREADED_SINGLE,
        _REFERENCE_A,
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "refcfg-b-child-rebuild-copy11",
        ReferenceSource.THREADED_SINGLE,
        _REFERENCE_B,
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "refcfg-c-both-rebuild-copy11",
        ReferenceSource.THREADED_SINGLE,
        _REFERENCE_C,
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "refcfg-c-mark-default-copy11",
        ReferenceSource.THREADED_SINGLE,
        (*_REFERENCE_C, ReferenceOperation.MARK_DEFAULT),
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "refcfg-c-mark-both-copy11",
        ReferenceSource.THREADED_SINGLE,
        (*_REFERENCE_C, ReferenceOperation.MARK_BOTH),
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "refcfg-e-reconcile-save1",
        ReferenceSource.BOTH_REBUILT_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "refcfg-e-mark-default-first-reconcile-save1",
        ReferenceSource.MARKED_DEFAULT_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "refcfg-e-mark-both-first-reconcile-save1",
        ReferenceSource.MARKED_BOTH_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "normal-extra-unmarked-first-reconcile-save1",
        ReferenceSource.NORMAL_EXTRA_UNMARKED_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "normal-extra-mark-default-first-reconcile-save1",
        ReferenceSource.NORMAL_EXTRA_MARKED_DEFAULT_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "refcfg-f-fresh-resave-save1",
        ReferenceSource.RECONCILED_COPY,
        (),
        ReferenceSave.IN_PLACE,
        1,
    ),
    ReferenceTrial(
        "refcfg-g-repeat-rebuild-mark-save1",
        ReferenceSource.RECONCILED_COPY,
        (ReferenceOperation.REBUILD_SAVE_MARKS,),
        ReferenceSave.IN_PLACE,
        1,
    ),
    ReferenceTrial(
        "fresh-refcfg-c-copy11",
        ReferenceSource.FRESH_THREADED,
        _REFERENCE_C,
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "fresh-refcfg-c-mark-default-copy11",
        ReferenceSource.FRESH_THREADED,
        (*_REFERENCE_C, ReferenceOperation.MARK_DEFAULT),
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "fresh-refcfg-c-unmarked-copy11",
        ReferenceSource.FRESH_THREADED,
        (*_REFERENCE_C, ReferenceOperation.CLEAR_MARKS),
        ReferenceSave.COPY,
        11,
    ),
    ReferenceTrial(
        "fresh-refcfg-e-unmarked-first-reconcile-save1",
        ReferenceSource.FRESH_UNMARKED_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "fresh-refcfg-e-mark-default-first-reconcile-save1",
        ReferenceSource.FRESH_MARKED_DEFAULT_COPY,
        (ReferenceOperation.RECONCILE,),
        ReferenceSave.RECONCILE,
        1,
    ),
    ReferenceTrial(
        "refcfg-d-both-rebuild-save9",
        ReferenceSource.THREADED_SINGLE,
        _REFERENCE_C,
        ReferenceSave.IN_PLACE,
        9,
        comparison=(
            "Copy versus in-place comparison against C Copy11: removes only "
            "Copy (2), retaining AvoidRebuildOnSave (8)."
        ),
    ),
    ReferenceTrial(
        "refcfg-d-both-rebuild-save1",
        ReferenceSource.THREADED_SINGLE,
        _REFERENCE_C,
        ReferenceSave.IN_PLACE,
        1,
        comparison=(
            "Two-variable comparison against C Copy11: removes Copy (2) "
            "and AvoidRebuildOnSave (8)."
        ),
    ),
)
EXTRA_COPY_STAGES = (
    "normal-extra-unmarked-copy11",
    "normal-extra-mark-default-copy11",
)


@dataclass(frozen=True)
class IndependentPenTrial:
    marks: tuple[str, ...]
    stages: tuple[str, str]
    history_filename: str
    history_key: str


INDEPENDENT_PN_TRIALS = {
    "independent-default": IndependentPenTrial(
        marks=("Default",),
        stages=(
            "independent-normal-mark-default-copy11",
            "independent-normal-mark-default-first-reconcile-save1",
        ),
        history_filename="pn-pen-display-independent-normal-mark-default.json",
        history_key="display_independent_source_history",
    ),
    "independent-both": IndependentPenTrial(
        marks=("Default", "Default Simplified"),
        stages=(
            "independent-normal-mark-both-copy11",
            "independent-normal-mark-both-first-reconcile-save1",
        ),
        history_filename="pn-pen-display-independent-normal-mark-both.json",
        history_key="display_independent_both_source_history",
    ),
}
INDEPENDENT_STAGES = tuple(
    stage for trial in INDEPENDENT_PN_TRIALS.values() for stage in trial.stages
)
SOURCE_HISTORY_FILENAMES = (
    "pn-pen-display-normal-extra-copy11.json",
    *(trial.history_filename for trial in INDEPENDENT_PN_TRIALS.values()),
)
STAGES = (
    "normal",
    *EXTRA_COPY_STAGES,
    *INDEPENDENT_STAGES,
    "single-copy11",
    *(trial[0] for trial in TRIALS),
    "single-threaded-copy11",
    *(trial.stage for trial in REFERENCE_TRIALS),
)
OUTPUT_FILENAMES = (
    *(f"pn-pen-display-{stage}.SLDASM" for stage in STAGES),
    *SOURCE_HISTORY_FILENAMES,
    "pn-pen-display-matrix.json",
)
_STREAM_MARKER = bytes.fromhex("140006000800")
_STRING_MARKER = b"\xff\xfe\xff"
_MAX_DISPLAY_BYTES = 64 * 1024 * 1024
_PN_CAPTURE_MODE: ContextVar[str] = ContextVar(
    "pn_display_capture_mode", default="normal"
)


def _digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _exploratory_flags(path: Path) -> dict[str, Any]:
    """Report the supplied swfile observations, without a production parser claim.

    Deliberately scans marker candidates as the original swfile.py does. Footer
    copies/decoys may occur; only successfully inflated exact DisplayLists names
    are reported. All such streams are retained, with largest-stream summary for
    comparison to the parent's original display_flags() evidence. Never edits
    native bytes and never rejects a zero flag.
    """
    streams = []
    skipped = 0
    with path.open("rb") as source:
        with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as data:
            cursor = 0
            while (offset := data.find(_STREAM_MARKER, cursor)) != -1:
                cursor = offset + len(_STREAM_MARKER)
                if offset + 26 > len(data):
                    skipped += 1
                    continue
                _, size, _, units = struct.unpack_from("<4I", data, offset + 10)
                start = offset + 26 + units
                if not 0 < units < 300 or start + size > len(data):
                    skipped += 1
                    continue
                encoded = data[offset + 26 : start]
                name = bytes(((b << 4) & 0xF0) | (b >> 4) for b in encoded)
                if name != b"Contents/DisplayLists":
                    continue
                inflater = zlib.decompressobj(-15)
                try:
                    display = inflater.decompress(
                        data[start : start + size], _MAX_DISPLAY_BYTES + 1
                    )
                except zlib.error:
                    skipped += 1
                    continue
                if len(display) > _MAX_DISPLAY_BYTES or not inflater.eof:
                    skipped += 1
                    continue
                flags = []
                string_cursor = 0
                while (
                    string_offset := display.find(_STRING_MARKER, string_cursor)
                ) != -1:
                    string_cursor = string_offset + 4
                    if string_cursor > len(display):
                        break
                    length = display[string_offset + 3]
                    end = string_cursor + 2 * length
                    if length == 0xFF or end > len(display):
                        continue
                    text = display[string_cursor:end].decode("utf-16le", "replace")
                    string_cursor = end
                    if text.upper().endswith(".SLDPRT") and end + 24 <= len(display):
                        flag = struct.unpack_from("<I", display, end + 20)[0]
                        flags.append(
                            {"part": text, "flag": flag, "string_offset": string_offset}
                        )
                streams.append(
                    {
                        "file_offset": offset,
                        "expanded_bytes": len(display),
                        "records": len(flags),
                        "zero": sum(row["flag"] == 0 for row in flags),
                        "flags": flags,
                    }
                )
    largest = max(streams, key=lambda row: row["expanded_bytes"], default=None)
    return {
        "parser": "exploratory swfile-style marker/short-string reader, not a visibility gate",
        "skipped_candidates": skipped,
        "streams": streams,
        "largest_stream_offset": largest["file_offset"] if largest else None,
        "records": largest["records"] if largest else 0,
        "zero": largest["zero"] if largest else 0,
        "flags": largest["flags"] if largest else [],
    }


def _model(adapter: Any) -> Any:
    from _com import _early_bound

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if model is None or int(model.GetType()) != 2:  # swDocASSEMBLY
        raise RuntimeError("display matrix requires the active assembly document")
    active = _early_bound(adapter.swApp.ActiveDoc, "IModelDoc2")
    if active is None or active.GetTitle() != model.GetTitle():
        raise RuntimeError("display matrix assembly is not the active native document")
    return model


def _configuration(model: Any, name: str) -> Any:
    from _com import _early_bound

    config = _early_bound(model.GetConfigurationByName(name), "IConfiguration")
    if config is None:
        raise RuntimeError(f"display matrix missing configuration {name!r}")
    return config


def _state(model: Any) -> dict[str, Any]:
    from _com import _early_bound

    names = tuple(str(name) for name in model.GetConfigurationNames() or ())
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    active = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if not names or active is None:
        raise RuntimeError("display matrix cannot read native configuration inventory")
    configs = {}
    for name in names:
        config = _configuration(model, name)
        configs[name] = {
            # Native docs say LargeDesignReviewMark is valid only for multiple configs.
            "large_design_review_mark": bool(config.LargeDesignReviewMark)
            if len(names) > 1
            else None,
            "add_rebuild_save_mark": bool(config.AddRebuildSaveMark),
            "derived": bool(config.IsDerived()),
        }
    assembly = _early_bound(model, "IAssemblyDoc")
    references = []
    components = []
    for raw in assembly.GetComponents(True) or ():
        component = _early_bound(raw, "IComponent2")
        path = str(component.GetPathName() or "")
        if not path:
            raise RuntimeError(
                "display matrix found a component with no external reference"
            )
        path = str(Path(path).resolve())
        references.append(path)
        components.append(
            {
                "path": path,
                "name": str(component.Name2),
                "referenced_configuration": str(component.ReferencedConfiguration),
            }
        )
    return {
        "active_configuration": str(active.Name),
        "configurations": configs,
        "ldr_mark_applicable": len(names) > 1,
        "get_save_flag": bool(model.GetSaveFlag()),
        "needs_rebuild2": int(
            _early_bound(model.Extension, "IModelDocExtension").NeedsRebuild2
        ),
        "references": sorted(references),
        "components": sorted(
            components, key=lambda row: (row["path"], row["referenced_configuration"])
        ),
    }


def _set_marks(model: Any, ldr_names: tuple[str, ...]) -> None:
    # Explicitly clear inherited marks too: 'Default only' must mean ONLY Default.
    for name in ("Default", "Default Simplified"):
        config = _configuration(model, name)
        config.LargeDesignReviewMark = name in ldr_names
        if bool(config.LargeDesignReviewMark) != (name in ldr_names):
            raise RuntimeError(f"display matrix LDR mark assignment refused for {name}")


@contextmanager
def independent_pn_capture(capture_mode: str):
    """Select one independent construction's mark/stage/history contract."""
    if capture_mode not in INDEPENDENT_PN_TRIALS:
        raise ValueError(f"unknown independent pn capture mode: {capture_mode!r}")
    token = _PN_CAPTURE_MODE.set(capture_mode)
    try:
        yield
    finally:
        _PN_CAPTURE_MODE.reset(token)


def pn_capture_mode() -> str:
    return _PN_CAPTURE_MODE.get()


def _protected_records(protected: dict[Path, str]) -> list[dict[str, Any]]:
    records = []
    for path, before in sorted(protected.items()):
        try:
            after = _digest(path)
        except OSError as error:
            after = None
            evidence = {"error": repr(error)}
        else:
            evidence = {}
        records.append(
            {
                "path": str(path),
                "before_sha256": before,
                "after_sha256": after,
                "unchanged": before == after,
                **evidence,
            }
        )
    return records


def _require_preserved(records: list[dict[str, Any]]) -> None:
    changed = [row["path"] for row in records if not row["unchanged"]]
    if changed:
        raise RuntimeError(f"display matrix changed protected input bytes: {changed}")


@contextmanager
def preserve_normal_pn_build_inputs(normal_path: str | Path):
    """Guard normal assembly, cached parts and DOF around each entire construction."""
    from _assembly import dof_manifest_path

    normal_path = Path(normal_path).resolve()
    history = json.loads(
        (normal_path.parent / SOURCE_HISTORY_FILENAMES[0]).read_text(encoding="utf-8")
    )
    if not history["complete"]:
        raise RuntimeError("normal pn source history is incomplete before independent build")
    paths = {
        normal_path,
        dof_manifest_path("pn-pen"),
        *(Path(row["path"]) for row in history["protected_inputs"]),
    }
    protected = {path: _digest(path) for path in paths}
    try:
        yield
    finally:
        _require_preserved(_protected_records(protected))


def _untitled_pn_state(adapter: Any) -> tuple[Any, dict[str, Any]]:
    model = _model(adapter)
    if model.GetPathName():
        raise RuntimeError(
            "pre-copy pn display probe requires the untitled build source"
        )
    state = _state(model)
    if set(state["configurations"]) != {"Default", "Default Simplified"}:
        raise RuntimeError(
            "pre-copy pn display probe requires both native configurations"
        )
    if state["active_configuration"] != "Default":
        raise RuntimeError("pre-copy pn display probe requires active Default")
    return model, state


def _display_observation(path: Path) -> dict[str, Any]:
    try:
        return _exploratory_flags(path)
    except (OSError, ValueError, zlib.error) as error:
        return {"parser_error": repr(error), "parser": "exploratory, not a gate"}


def _capture_copy11(model: Any, path: Path, row: dict[str, Any]) -> None:
    path.unlink(missing_ok=True)
    row["save_api"] = ReferenceSave.COPY.value
    row["save_options"] = 11
    row["before_save"] = _state(model)
    row["native_source_path"] = str(model.GetPathName() or "") or None
    row["save_result"] = model.SaveAs3(str(path), 0, 11)
    if not path.is_file() or path.stat().st_size <= 0:
        raise RuntimeError(f"display matrix Copy11 produced no snapshot: {path}")
    row.update(
        path=str(path),
        filename=path.name,
        sha256=_digest(path),
        bytes=path.stat().st_size,
        untitled_after_copy=_state(model),
        display_data=_display_observation(path),
    )


def capture_pn_marked_copy(adapter: Any, normal_path: Path) -> None:
    """Capture two extra copies; neither is an independent first serialization."""
    from _telemetry import info

    normal_path = Path(normal_path).resolve()
    model, source_state = _untitled_pn_state(adapter)
    protected = {
        path: _digest(path)
        for path in {normal_path, *(Path(p) for p in source_state["references"])}
    }
    original_marks = tuple(
        name
        for name, config in source_state["configurations"].items()
        if config["large_design_review_mark"]
    )
    report: dict[str, Any] = {
        "complete": False,
        "normal_assembly_sha256": protected[normal_path],
        "source_before_extra_copies": source_state,
        "source_save_history": (
            "Same live untitled pn source: unchanged normal Copy11 is serialization "
            "1, explicitly unmarked extra Copy11 is 2, Default-only marked extra "
            "Copy11 is 3. No reopen or reconcile precedes either extra copy. "
            "Serialization count/order remains a confound; use fresh/independent "
            "first-serialization controls for the primary conclusion."
        ),
        "stages": [],
    }
    try:
        for ordinal, stage, marks in (
            (2, EXTRA_COPY_STAGES[0], ()),
            (3, EXTRA_COPY_STAGES[1], ("Default",)),
        ):
            row = {
                "stage": stage,
                "source_stage": "same-untitled-normal-pn-source",
                "assembly_serialization_ordinal": ordinal,
                "source_sha256": None,
                "before_mark_assignment": _state(model),
                "requested_ldr_marks": marks,
                "mark_first_set": (
                    "After baseline normal Copy11, before this extra Copy11; "
                    "before any source discard/reopen/first reconcile."
                ),
            }
            report["stages"].append(row)
            _set_marks(model, marks)
            row["after_mark_assignment"] = _state(model)
            _capture_copy11(
                model, normal_path.parent / f"pn-pen-display-{stage}.SLDASM", row
            )
        report["complete"] = True
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        _set_marks(model, original_marks)
        report["restored_source_state"] = _state(model)
        report["protected_inputs"] = _protected_records(protected)
        if any(not row["unchanged"] for row in report["protected_inputs"]):
            report["complete"] = False
        (normal_path.parent / SOURCE_HISTORY_FILENAMES[0]).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        info("display matrix extra pn copies " + json.dumps(report))
        _require_preserved(report["protected_inputs"])


async def capture_independent_pn_first_reconcile(
    adapter: Any, normal_path: Path, capture_mode: str
) -> dict[str, str]:
    """Mark an independently constructed pn before its first-ever assembly save."""
    from _assembly import (
        _discard_copy_source,
        _ensure_assembly_identity,
        _ensure_assembly_title,
        reconcile_saved_rebuild_state,
    )
    from _check import check
    from _session import discard_open_documents
    from _telemetry import info

    normal_path = Path(normal_path).resolve()
    trial = INDEPENDENT_PN_TRIALS[capture_mode]
    stages = trial.stages
    paths = {
        stage: normal_path.parent / f"pn-pen-display-{stage}.SLDASM"
        for stage in stages
    }
    manifest = normal_path.parent / trial.history_filename
    model, initial = _untitled_pn_state(adapter)
    protected = {
        path: _digest(path)
        for path in {normal_path, *(Path(p) for p in initial["references"])}
    }
    report: dict[str, Any] = {
        "complete": False,
        "capture_mode": capture_mode,
        "requested_ldr_marks": trial.marks,
        "normal_assembly_sha256": protected[normal_path],
        "initial_native_untitled_state": initial,
        "source_save_history": (
            "Independent construction through the unchanged pn builder "
            "using cached parts. No assembly serialization, reopen or reconcile "
            "precedes the requested LDR marks and initial Copy11."
        ),
        "stages": [],
    }
    try:
        # Match the original copy-save's metadata without changing diagnostic filenames.
        _ensure_assembly_identity(adapter, "pn-pen", model)
        _ensure_assembly_title(adapter, "pn-pen", model)
        row = {
            "stage": stages[0],
            "source_stage": "independent-fresh-untitled-normal-pn-build",
            "assembly_serialization_ordinal": 1,
            "source_sha256": None,
            "before_mark_assignment": _state(model),
            "requested_ldr_marks": trial.marks,
            "mark_first_set": "Before the independent source's FIRST-ever Copy11.",
        }
        report["stages"].append(row)
        _set_marks(model, trial.marks)
        row["after_mark_assignment"] = _state(model)
        _capture_copy11(model, paths[stages[0]], row)
        _discard_copy_source(adapter)
        model = None
        check(
            "display matrix reopen independent initial copy",
            await adapter.open_model(str(paths[stages[0]])),
        )
        row["after_save"] = _state(_model(adapter))
        row["reopened"] = row["after_save"]
        if row["reopened"]["references"] != initial["references"]:
            raise RuntimeError("independent pn copy changed cached references")
        protected[paths[stages[0]]] = row["sha256"]
        discard_open_documents(adapter)
        adapter.currentModel = None
        source = paths[stages[0]]
        destination = paths[stages[1]]
        shutil.copy2(source, destination)
        if _digest(destination) != row["sha256"]:
            raise RuntimeError(
                "independent pn first reconcile did not start from source bytes"
            )
        check(
            "display matrix inspect independent reconcile input",
            await adapter.open_model(str(destination)),
        )
        row = {
            "stage": stages[1],
            "source_stage": stages[0],
            "source_sha256": _digest(source),
            "baseline_display_data": report["stages"][0]["display_data"],
            "before_save": _state(_model(adapter)),
            "save_api": ReferenceSave.RECONCILE.value,
            "save_options": 1,
            "operations": [ReferenceOperation.RECONCILE.value],
            "native_reconcile_save": {},
        }
        report["stages"].append(row)
        discard_open_documents(adapter)
        adapter.currentModel = None
        await reconcile_saved_rebuild_state(
            adapter,
            stages[1],
            destination,
            diagnostic_save=row["native_reconcile_save"],
        )
        row.update(
            path=str(destination),
            filename=destination.name,
            sha256=_digest(destination),
            bytes=destination.stat().st_size,
            after_save=_state(_model(adapter)),
            display_data=_display_observation(destination),
        )
        row["reopened"] = row["after_save"]
        if row["reopened"]["references"] != initial["references"]:
            raise RuntimeError("independent pn reconcile changed cached references")
        protected[destination] = row["sha256"]
        report["complete"] = True
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        discard_open_documents(adapter)
        adapter.currentModel = None
        report["protected_inputs"] = _protected_records(protected)
        if any(not row["unchanged"] for row in report["protected_inputs"]):
            report["complete"] = False
        manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")
        info("display matrix independent pn " + json.dumps(report))
        _require_preserved(report["protected_inputs"])
    return {f"display_{stage}": str(path) for stage, path in paths.items()} | {
        trial.history_key: str(manifest)
    }


def _select_available_simplified_references(
    adapter: Any, model: Any
) -> list[dict[str, Any]]:
    """Change only genuinely available part configs; re-query handles after each set."""
    from _com import _early_bound

    assembly = _early_bound(model, "IAssemblyDoc")
    # ReferencedConfiguration assignments invalidate an enumerated component array.
    # Retain names only, release that inventory, and obtain each handle afresh.
    names = []
    for raw in assembly.GetComponents(True) or ():
        component = _early_bound(raw, "IComponent2")
        names.append(str(component.Name2))
    raw = component = None
    if not names:
        raise RuntimeError("reference trial has no top-level components")
    known: dict[str, set[str]] = {}
    rows = []
    switched = 0
    for name in names:
        component = _early_bound(assembly.GetComponentByName(name), "IComponent2")
        if component is None:
            raise RuntimeError(f"reference trial lost component {name!r}")
        path = str(component.GetPathName())
        if path not in known:
            known[path] = {
                str(config)
                for config in adapter.swApp.GetConfigurationNames(path) or ()
            }
        before = str(component.ReferencedConfiguration)
        wanted = "Default Simplified" if "Default Simplified" in known[path] else before
        if wanted != before:
            component.ReferencedConfiguration = wanted
            switched += 1
        after = str(component.ReferencedConfiguration)
        if after != wanted:
            raise RuntimeError(
                f"reference trial refused {name}: {before!r} -> {wanted!r}"
            )
        rows.append(
            {
                "component": name,
                "path": path,
                "available_configurations": sorted(known[path]),
                "before": before,
                "after": after,
                "changed": before != after,
            }
        )
        component = None
    if switched == 0:
        raise RuntimeError(
            "reference trial made no genuine simplified-reference switch"
        )
    return rows


async def probe_assembly_display_data(
    adapter: Any, normal_path: str | Path
) -> dict[str, str]:
    """Collect cache-published snapshots using the already-admitted pn farm seat."""
    from _assembly import place_component, reconcile_saved_rebuild_state
    from _check import check
    from _com import _early_bound
    from _rebuild import active_configuration_name
    from _session import discard_open_documents
    from _telemetry import info, span
    from _transforms import IDENTITY

    normal_path = Path(normal_path).resolve()
    if normal_path.name != "pn-pen.SLDASM":
        raise RuntimeError(
            f"display matrix refuses a non-pn normal result: {normal_path}"
        )
    directory = normal_path.parent
    paths = {stage: directory / f"pn-pen-display-{stage}.SLDASM" for stage in STAGES}
    scratch_paths = {
        trial.stage: directory / f".pn-pen-display-source-{trial.stage}.SLDASM"
        for trial in REFERENCE_TRIALS
        if trial.save_api == ReferenceSave.COPY
        and trial.source != ReferenceSource.FRESH_THREADED
    }
    manifest = directory / OUTPUT_FILENAMES[-1]
    # Independent capture discarded its source; reload the untouched normal result.
    discard_open_documents(adapter)
    adapter.currentModel = None
    check("display matrix reload normal", await adapter.open_model(str(normal_path)))
    normal_state = _state(_model(adapter))
    inputs = {normal_path, *(Path(path) for path in normal_state["references"])}
    protected = {path: _digest(path) for path in inputs}
    source_histories = [
        json.loads((directory / filename).read_text(encoding="utf-8"))
        for filename in SOURCE_HISTORY_FILENAMES
    ]
    for history in source_histories:
        if not history["complete"]:
            raise RuntimeError("display matrix pre-copy source history is incomplete")
        for evidence in history["protected_inputs"]:
            path = Path(evidence["path"])
            # The extra-copy hook protects the initial NORMAL Copy11 only while
            # branching; its normal build intentionally reconciles those bytes
            # afterward. Independent capture protects the final normal instead.
            if path == normal_path and history is source_histories[0]:
                continue
            if _digest(path) != evidence["before_sha256"]:
                raise RuntimeError(
                    f"display matrix pre-copy protected input changed: {path}"
                )
            protected[path] = evidence["before_sha256"]
    for filename in SOURCE_HISTORY_FILENAMES:
        path = directory / filename
        protected[path] = _digest(path)
    report: dict[str, Any] = {
        "leaf": "assembly:pn_pen",
        "solidworks_revision": str(adapter.swApp.RevisionNumber()),
        "normal_assembly": str(normal_path),
        "complete": False,
        "stages": [],
        "source_histories": source_histories,
    }

    def checkpoint() -> None:
        manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def discard() -> None:
        discard_open_documents(adapter)
        adapter.currentModel = None

    async def create_threaded_fixture() -> Any:
        """Create the shared fixture, without rebuilding or saving its assembly."""
        check(
            "display matrix create threaded single assembly",
            await adapter.create_assembly(),
        )
        for part, position in (
            ("pn-pen-hanger", [0.0, 0.0, 0.0]),
            ("pn-pen-hanger", [50.0, 0.0, 0.0]),
            ("vn-pen-set-screw", [100.0, 0.0, 0.0]),
        ):
            await place_component(adapter, part, position, [0.0, 0.0, 0.0], IDENTITY)
        model = _model(adapter)
        names = tuple(str(name) for name in model.GetConfigurationNames() or ())
        if names != ("Default",):
            raise RuntimeError(
                f"threaded display baseline needs only Default, got {names!r}"
            )
        return model

    async def capture(
        stage: str, row: dict[str, Any], expected_references: list[str]
    ) -> None:
        path = paths[stage]
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(
                f"display matrix native save produced no snapshot: {path}"
            )
        row.update(
            path=str(path),
            filename=path.name,
            sha256=_digest(path),
            bytes=path.stat().st_size,
        )
        row["after_save"] = _state(_model(adapter))
        discard()
        check(f"display matrix reopen {stage}", await adapter.open_model(str(path)))
        row["reopened"] = _state(_model(adapter))
        if row["reopened"]["references"] != expected_references:
            raise RuntimeError(
                f"display matrix changed component references in {stage}"
            )
        try:
            row["display_data"] = _exploratory_flags(path)
        except (OSError, ValueError, zlib.error) as error:
            row["display_data"] = {
                "parser_error": repr(error),
                "parser": "exploratory, not a gate",
            }
        row["status"] = "saved-and-reopened"
        checkpoint()
        info("display matrix " + json.dumps(row, ensure_ascii=True))
        discard()

    with span("probe.assembly_display_data", asm="pn-pen"):
        try:
            # Normal and independent pn captures have finished; preserve their files.
            discard()
            early_outputs = {
                *SOURCE_HISTORY_FILENAMES,
                *(
                    paths[stage].name
                    for stage in (*EXTRA_COPY_STAGES, *INDEPENDENT_STAGES)
                ),
            }
            for filename in OUTPUT_FILENAMES:
                if filename not in early_outputs:
                    (directory / filename).unlink(missing_ok=True)
            checkpoint()
            shutil.copy2(normal_path, paths["normal"])
            if _digest(paths["normal"]) != protected[normal_path]:
                raise RuntimeError(
                    "normal display snapshot is not a byte-identical copy"
                )
            check(
                "display matrix open normal snapshot",
                await adapter.open_model(str(paths["normal"])),
            )
            row = {
                "stage": "normal",
                "save_api": "byte-copy only",
                "before_save": normal_state,
            }
            report["stages"].append(row)
            await capture("normal", row, normal_state["references"])
            protected[paths["normal"]] = protected[normal_path]

            for history in source_histories:
                for saved_row in history["stages"]:
                    stage = saved_row["stage"]
                    row = dict(saved_row)
                    if _digest(paths[stage]) != row["sha256"]:
                        raise RuntimeError(
                            f"display matrix early snapshot changed: {stage}"
                        )
                    report["stages"].append(row)
                    check(
                        f"display matrix open early snapshot {stage}",
                        await adapter.open_model(str(paths[stage])),
                    )
                    await capture(stage, row, normal_state["references"])
                    protected[paths[stage]] = row["sha256"]

            check(
                "display matrix create single assembly", await adapter.create_assembly()
            )
            for part, position in (
                ("pn-pen-hanger", [0.0, 0.0, 0.0]),
                ("pn-pen-hanger", [50.0, 0.0, 0.0]),
                ("pn-pen-rod", [100.0, 0.0, 0.0]),
            ):
                await place_component(
                    adapter, part, position, [0.0, 0.0, 0.0], IDENTITY
                )
            model = _model(adapter)
            names = tuple(str(name) for name in model.GetConfigurationNames() or ())
            if names != ("Default",):
                raise RuntimeError(
                    f"display matrix needs a single-Default assembly template, got {names!r}"
                )
            if not model.ForceRebuild3(False):
                raise RuntimeError(
                    "display matrix single-config ForceRebuild3(False) failed"
                )
            single_state = _state(model)
            single_refs = single_state["references"]
            if not set(single_refs).issubset({str(path) for path in protected}):
                raise RuntimeError(
                    "minimal display assembly references inputs outside normal pn assembly"
                )
            row = {
                "stage": "single-copy11",
                "save_api": "IModelDoc2.SaveAs3",
                "save_options": 11,
                "before_save": single_state,
            }
            report["stages"].append(row)
            # Silent (1) | Copy (2) | AvoidRebuildOnSave (8); never SaveReferenced (4).
            row["save_result"] = model.SaveAs3(str(paths["single-copy11"]), 0, 11)
            model = None
            await capture("single-copy11", row, single_refs)
            source_hashes = {
                "single-copy11": _digest(paths["single-copy11"]),
                "normal": protected[normal_path],
            }
            protected[paths["single-copy11"]] = source_hashes["single-copy11"]
            source_references = {
                "single-copy11": single_refs,
                "normal": normal_state["references"],
            }

            for stage, options, switches, marks, source_stage in TRIALS:
                with span("probe.assembly_display_data.stage", stage=stage):
                    row = {
                        "stage": stage,
                        "source_stage": source_stage,
                        "save_api": "IModelDoc2.Save3",
                        "save_options": options,
                        "switch_rebuild_and_mark": switches,
                        "requested_ldr_marks": marks,
                    }
                    report["stages"].append(row)
                    shutil.copy2(paths[source_stage], paths[stage])
                    if _digest(paths[stage]) != source_hashes[source_stage]:
                        raise RuntimeError(
                            f"display matrix {stage} did not start from the {source_stage} bytes"
                        )
                    check(
                        f"display matrix open {stage}",
                        await adapter.open_model(str(paths[stage])),
                    )
                    model = _model(adapter)
                    row["opened_source"] = _state(model)
                    if source_stage == "single-copy11":
                        manager = _early_bound(
                            model.ConfigurationManager, "IConfigurationManager"
                        )
                        child = manager.AddConfiguration2(
                            "Default Simplified", "", "", 0, "Default", "", False
                        )
                        if (
                            child is None
                            or not _early_bound(child, "IConfiguration").IsDerived()
                        ):
                            raise RuntimeError(
                                f"display matrix {stage}: AddConfiguration2 failed to create derived config"
                            )
                        child = None
                        manager = None
                    elif not _configuration(model, "Default Simplified").IsDerived():
                        raise RuntimeError(
                            f"display matrix {stage}: normal snapshot lacks its derived configuration"
                        )
                    if marks is not None:
                        _set_marks(model, marks)
                    if switches:
                        row["configuration_switches"] = []
                        for name in ("Default Simplified", "Default"):
                            if (
                                active_configuration_name(adapter, model) != name
                                and not model.ShowConfiguration2(name)
                            ) or not model.EditRebuild3():
                                raise RuntimeError(
                                    f"display matrix {stage}: switch/rebuild refused {name}"
                                )
                            config = _configuration(model, name)
                            config.AddRebuildSaveMark = True
                            if not config.AddRebuildSaveMark:
                                raise RuntimeError(
                                    f"display matrix {stage}: rebuild/save mark refused {name}"
                                )
                            config = None
                            row["configuration_switches"].append(_state(model))
                    row["before_save"] = _state(model)
                    row["get_save_flag_before_save3"] = bool(model.GetSaveFlag())
                    result = model.Save3(options, 0, 0)
                    row["save_result"] = result
                    if not isinstance(result, tuple) or len(result) != 3:
                        raise RuntimeError(
                            f"display matrix {stage}: Save3 missing native retval/error/warning tuple: {result!r}"
                        )
                    saved, errors, warnings = result
                    row.update(
                        saved=bool(saved), errors=int(errors), warnings=int(warnings)
                    )
                    if not saved or errors:
                        raise RuntimeError(
                            f"display matrix {stage}: Save3 failed: {result!r}"
                        )
                    model = None
                    await capture(stage, row, source_references[source_stage])
                    protected[paths[stage]] = _digest(paths[stage])
            # Keep every prior stage unchanged. This separate baseline contains a
            # real threaded part; the original hanger/rod baseline remains intact.
            stage = ReferenceSource.THREADED_SINGLE.value
            model = await create_threaded_fixture()
            if not model.ForceRebuild3(False):
                raise RuntimeError(
                    "threaded display baseline ForceRebuild3(False) failed"
                )
            threaded_state = _state(model)
            threaded_refs = threaded_state["references"]
            if not set(threaded_refs).issubset({str(path) for path in protected}):
                raise RuntimeError(
                    "threaded display baseline references inputs outside normal pn"
                )
            row = {
                "stage": stage,
                "source_stage": "cached-normal-pn-parts",
                "save_api": ReferenceSave.COPY.value,
                "save_options": 11,
                "before_save": threaded_state,
            }
            report["stages"].append(row)
            row["save_result"] = model.SaveAs3(str(paths[stage]), 0, 11)
            model = None
            await capture(stage, row, threaded_refs)
            protected[paths[stage]] = _digest(paths[stage])

            for trial in REFERENCE_TRIALS:
                stage = trial.stage
                source_stage = trial.source.value
                with span("probe.assembly_display_data.references", stage=stage):
                    row = {
                        "stage": stage,
                        "source_stage": source_stage,
                        "source_sha256": None,
                        "baseline_display_data": None,
                        "save_api": trial.save_api.value,
                        "save_options": trial.save_options,
                        "comparison": trial.comparison,
                        "operations": [
                            operation.value for operation in trial.operations
                        ],
                        "operation_states": [],
                        "configuration_switches": [],
                        "pre_save_instrumentation": {
                            "opened_source": "_state reads native configuration/mark/rebuild properties and GetComponents(True)",
                            "operation_states": "_state before and after each listed operation",
                            "before_save": "_state repeats these reads immediately before save; not an uninstrumented open/save",
                        },
                    }
                    report["stages"].append(row)
                    if trial.source == ReferenceSource.FRESH_THREADED:
                        # No baseline assembly file, intermediate save, or source
                        # byte hash exists for this independent untitled fixture.
                        working_path = None
                        row["working_source_path"] = None
                        row["baseline_display_data_note"] = (
                            "No assembly file exists before this first native save."
                        )
                        model = await create_threaded_fixture()
                        if model.GetPathName():
                            raise RuntimeError(
                                "fresh threaded fixture is already saved"
                            )
                        initial = _state(model)
                        row["initial_native_default_state"] = initial
                        row["opened_source"] = initial
                        trial_references = threaded_refs
                        if initial["references"] != threaded_refs:
                            raise RuntimeError(
                                "fresh threaded fixture changed cached references"
                            )
                    else:
                        source_row = next(
                            saved_row
                            for saved_row in report["stages"]
                            if saved_row["stage"] == source_stage
                        )
                        row["source_sha256"] = _digest(paths[source_stage])
                        row["baseline_display_data"] = source_row["display_data"]
                        trial_references = source_row["reopened"]["references"]
                        if row["source_sha256"] != protected[paths[source_stage]]:
                            raise RuntimeError(
                                f"reference trial source changed: {source_stage}"
                            )
                        # Saved-source Copy11 edits a separate temporary sibling;
                        # in-place/reconcile stages open their own output copy.
                        working_path = scratch_paths.get(stage, paths[stage])
                        if stage in scratch_paths:
                            working_path.unlink(missing_ok=True)
                        shutil.copy2(paths[source_stage], working_path)
                        if _digest(working_path) != row["source_sha256"]:
                            raise RuntimeError(
                                f"reference trial {stage} did not start from source bytes"
                            )
                        row["working_source_path"] = str(working_path)
                        check(
                            f"reference trial open {stage}",
                            await adapter.open_model(str(working_path)),
                        )
                        model = _model(adapter)
                        row["opened_source"] = _state(model)
                    for operation in trial.operations:
                        evidence = {
                            "operation": operation.value,
                            "before": _state(model),
                        }
                        row["operation_states"].append(evidence)
                        if operation == ReferenceOperation.ADD_DERIVED:
                            manager = _early_bound(
                                model.ConfigurationManager, "IConfigurationManager"
                            )
                            child = manager.AddConfiguration2(
                                "Default Simplified", "", "", 0, "Default", "", False
                            )
                            if (
                                child is None
                                or not _early_bound(child, "IConfiguration").IsDerived()
                            ):
                                raise RuntimeError(
                                    f"reference trial {stage}: derived configuration creation failed"
                                )
                            child = manager = None
                        elif operation in (
                            ReferenceOperation.ACTIVATE_DERIVED,
                            ReferenceOperation.RESTORE_DEFAULT,
                        ):
                            name = (
                                "Default Simplified"
                                if operation == ReferenceOperation.ACTIVATE_DERIVED
                                else "Default"
                            )
                            if active_configuration_name(
                                adapter, model
                            ) != name and not model.ShowConfiguration2(name):
                                raise RuntimeError(
                                    f"reference trial {stage}: refused activation {name}"
                                )
                        elif (
                            operation == ReferenceOperation.SELECT_SIMPLIFIED_REFERENCES
                        ):
                            if (
                                active_configuration_name(adapter, model)
                                != "Default Simplified"
                            ):
                                raise RuntimeError(
                                    "reference selection requires the derived configuration"
                                )
                            evidence["reference_selection"] = (
                                _select_available_simplified_references(adapter, model)
                            )
                        elif operation in (
                            ReferenceOperation.REBUILD_DERIVED,
                            ReferenceOperation.REBUILD_DEFAULT,
                        ):
                            expected = (
                                "Default Simplified"
                                if operation == ReferenceOperation.REBUILD_DERIVED
                                else "Default"
                            )
                            if active_configuration_name(
                                adapter, model
                            ) != expected or not model.ForceRebuild3(False):
                                raise RuntimeError(
                                    f"reference trial {stage}: deep rebuild failed in {expected}"
                                )
                        elif operation == ReferenceOperation.REBUILD_SAVE_MARKS:
                            evidence["configuration_states"] = []
                            for name in ("Default Simplified", "Default"):
                                if (
                                    active_configuration_name(adapter, model) != name
                                    and not model.ShowConfiguration2(name)
                                ) or not model.EditRebuild3():
                                    raise RuntimeError(
                                        f"reference trial {stage}: repeat switch/rebuild refused {name}"
                                    )
                                config = _configuration(model, name)
                                config.AddRebuildSaveMark = True
                                if not config.AddRebuildSaveMark:
                                    raise RuntimeError(
                                        f"reference trial {stage}: repeat rebuild/save mark refused {name}"
                                    )
                                config = None
                                state = _state(model)
                                evidence["configuration_states"].append(state)
                                row["configuration_switches"].append(
                                    {
                                        "operation": operation.value,
                                        **state,
                                    }
                                )
                        elif operation in (
                            ReferenceOperation.CLEAR_MARKS,
                            ReferenceOperation.MARK_DEFAULT,
                            ReferenceOperation.MARK_BOTH,
                        ):
                            if active_configuration_name(adapter, model) != "Default":
                                raise RuntimeError(
                                    "initial-C LDR marks require active Default"
                                )
                            marks = {
                                ReferenceOperation.CLEAR_MARKS: (),
                                ReferenceOperation.MARK_DEFAULT: ("Default",),
                                ReferenceOperation.MARK_BOTH: (
                                    "Default",
                                    "Default Simplified",
                                ),
                            }[operation]
                            _set_marks(model, marks)
                            evidence["requested_ldr_marks"] = marks
                            evidence["mark_first_set"] = (
                                "Before FIRST-ever serialization of this fresh untitled fixture."
                                if trial.source == ReferenceSource.FRESH_THREADED
                                else "After independent source reopen and C rebuilds, before initial Copy11."
                            )
                        elif operation == ReferenceOperation.RECONCILE:
                            row["before_save"] = evidence["before"]
                            row["reconcile_input_sha256"] = _digest(paths[stage])
                            row["pre_reconcile_get_save_flag"] = bool(
                                model.GetSaveFlag()
                            )
                            row["native_reconcile_save"] = {}
                            model = None
                            discard()
                            await reconcile_saved_rebuild_state(
                                adapter,
                                stage,
                                paths[stage],
                                diagnostic_save=row["native_reconcile_save"],
                            )
                            model = _model(adapter)
                            row["reconcile_changed_bytes"] = (
                                _digest(paths[stage]) != row["reconcile_input_sha256"]
                            )
                        else:
                            raise RuntimeError(
                                f"unsupported reference operation {operation}"
                            )
                        evidence["after"] = _state(model)
                        if operation in (
                            ReferenceOperation.ACTIVATE_DERIVED,
                            ReferenceOperation.REBUILD_DERIVED,
                            ReferenceOperation.RESTORE_DEFAULT,
                            ReferenceOperation.REBUILD_DEFAULT,
                        ):
                            row["configuration_switches"].append(
                                {
                                    "operation": operation.value,
                                    **evidence["after"],
                                }
                            )
                        checkpoint()
                    if trial.save_api != ReferenceSave.RECONCILE:
                        row["before_save"] = _state(model)
                    if trial.save_api == ReferenceSave.COPY:
                        native_source_path = str(model.GetPathName() or "")
                        row["native_source_path"] = native_source_path or None
                        if working_path == paths[stage] or (
                            native_source_path
                            and Path(native_source_path).resolve() == paths[stage]
                        ):
                            raise RuntimeError(
                                "reference Copy11 source must differ from destination"
                            )
                        row["save_result"] = model.SaveAs3(
                            str(paths[stage]), 0, trial.save_options
                        )
                    elif trial.save_api == ReferenceSave.IN_PLACE:
                        row["get_save_flag_before_save3"] = bool(model.GetSaveFlag())
                        result = model.Save3(trial.save_options, 0, 0)
                        row["save_result"] = result
                        if not isinstance(result, tuple) or len(result) != 3:
                            raise RuntimeError(
                                f"reference trial {stage}: Save3 missing native outputs: {result!r}"
                            )
                        saved, errors, warnings = result
                        row.update(
                            saved=bool(saved),
                            errors=int(errors),
                            warnings=int(warnings),
                        )
                        if not saved or errors:
                            raise RuntimeError(
                                f"reference trial {stage}: Save3 failed: {result!r}"
                            )
                    # Reconcile owns its conditional Save3; don't add a save here.
                    model = None
                    await capture(stage, row, trial_references)
                    if stage in scratch_paths:
                        working_path.unlink()
                    protected[paths[stage]] = _digest(paths[stage])
            report["complete"] = True
        except Exception as error:
            report["error"] = repr(error)
            if (
                report["stages"]
                and report["stages"][-1].get("status") != "saved-and-reopened"
            ):
                report["stages"][-1]["status"] = "failed"
            raise
        finally:
            try:
                discard()
            finally:
                cleanup_errors = []
                for scratch in scratch_paths.values():
                    try:
                        scratch.unlink(missing_ok=True)
                    except OSError as error:
                        cleanup_errors.append(
                            {"path": str(scratch), "error": repr(error)}
                        )
                if cleanup_errors:
                    report["complete"] = False
                    report["scratch_cleanup_errors"] = cleanup_errors
                report["protected_inputs"] = []
                changed = []
                for path, before in sorted(protected.items()):
                    try:
                        after = _digest(path)
                    except OSError as error:
                        after = None
                        changed.append(str(path))
                        evidence = {"error": repr(error)}
                    else:
                        evidence = {}
                        if after != before:
                            changed.append(str(path))
                    report["protected_inputs"].append(
                        {
                            "path": str(path),
                            "before_sha256": before,
                            "after_sha256": after,
                            "unchanged": before == after,
                            **evidence,
                        }
                    )
                if changed:
                    report["complete"] = False
                    report["input_preservation_error"] = changed
                checkpoint()
                info(
                    "display matrix protected inputs "
                    + json.dumps(report["protected_inputs"])
                )
                if changed:
                    raise RuntimeError(
                        f"display matrix changed protected input bytes: {changed}"
                    )
                if cleanup_errors:
                    raise RuntimeError(
                        f"display matrix failed to remove transient source files: {cleanup_errors}"
                    )

    return {f"display_{stage}": str(paths[stage]) for stage in STAGES} | {
        "display_matrix": str(manifest),
        "display_extra_copy_source_history": str(
            directory / SOURCE_HISTORY_FILENAMES[0]
        ),
        **{
            trial.history_key: str(directory / trial.history_filename)
            for trial in INDEPENDENT_PN_TRIALS.values()
        },
    }

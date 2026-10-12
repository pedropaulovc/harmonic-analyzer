"""Temporary display-data save matrix, invoked AFTER the normal pn assembly build.

Run through the existing farm leaf ``assembly:pn_pen``; this module deliberately
has no standalone entry point that could start a local SOLIDWORKS seat. The pn
builder first finishes its unchanged save/reconcile/render/fingerprint tail.
Only then does this probe byte-copy its saved result and create an independent
three-component assembly from cached pn-pen-hanger and pn-pen-rod inputs.

All snapshots are siblings of pn-pen.SLDASM, preserving its reference directory
layout. No part build is dispatched; no part file is saved, copied, or
reference-rewritten by the probe.
Every minimal multi-config trial starts from the same single-config copy, not
the previous trial. Four final normal-assembly trials each start from the
untouched normal snapshot and retain its real referenced-part configurations.
Save9 vs Save1 differs only in AvoidRebuildOnSave; the switch trial adds
ShowConfiguration2/EditRebuild3/AddRebuildSaveMark for derived then Default;
the controls preserve inherited native marks. The clear-both trial supplies an
explicitly unmarked comparator for the three selected-LDR trials and emodel
trial (OverrideSaveEmodel, 32). Nothing changes global SOLIDWORKS preferences.
Original assembly and referenced input bytes are hashed
before/after. A failed native operation aborts the leaf; parser observations never
act as a production visibility gate.

The manifest and stdout retain native config/mark/rebuild state before save,
after save and on a fresh reopen, save results, input hashes, snapshot hashes,
and exploratory swfile-style raw display flags. The undocumented flag reader is
NOT proof of component visibility, config association or format completeness.
Parent must compare these native snapshots in eDrawings before choosing any fix.
Remove the temporary builder hook and cache declaration after collecting proof;
this reproduction module may remain as requested evidence.
"""

from __future__ import annotations

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
STAGES = ("normal", "single-copy11", *(trial[0] for trial in TRIALS))
OUTPUT_FILENAMES = (
    *(f"pn-pen-display-{stage}.SLDASM" for stage in STAGES),
    "pn-pen-display-matrix.json",
)
_STREAM_MARKER = bytes.fromhex("140006000800")
_STRING_MARKER = b"\xff\xfe\xff"
_MAX_DISPLAY_BYTES = 64 * 1024 * 1024


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
                "referenced_configuration": str(component.ReferencedConfiguration),
            }
        )
    return {
        "active_configuration": str(active.Name),
        "configurations": configs,
        "ldr_mark_applicable": len(names) > 1,
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


async def probe_assembly_display_data(
    adapter: Any, normal_path: str | Path
) -> dict[str, str]:
    """Collect cache-published snapshots using the already-admitted pn farm seat."""
    from _assembly import place_component
    from _check import check
    from _com import _early_bound
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
    manifest = directory / OUTPUT_FILENAMES[-1]
    normal_state = _state(_model(adapter))
    inputs = {normal_path, *(Path(path) for path in normal_state["references"])}
    protected = {path: _digest(path) for path in inputs}
    report: dict[str, Any] = {
        "leaf": "assembly:pn_pen",
        "solidworks_revision": str(adapter.swApp.RevisionNumber()),
        "normal_assembly": str(normal_path),
        "complete": False,
        "stages": [],
    }

    def checkpoint() -> None:
        manifest.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def discard() -> None:
        discard_open_documents(adapter)
        adapter.currentModel = None

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
            # The normal build has already finished. No probe operation precedes it.
            discard()
            for filename in OUTPUT_FILENAMES:
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
                                not model.ShowConfiguration2(name)
                                or not model.EditRebuild3()
                            ):
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

    return {f"display_{stage}": str(paths[stage]) for stage in STAGES} | {
        "display_matrix": str(manifest)
    }

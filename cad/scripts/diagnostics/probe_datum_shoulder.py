"""Compare straight/bent native leaders on the exact rocker B datum face.

Each trial opens an independent saved-drawing copy, verifies B starts with a
non-forced straight shoulder, applies exactly one shoulder policy, then asks
for the SAME derived outboard XYZ. Native boolean and actual positions are
observations; geometry, label, rendered text and source dimensions must survive.
The original drawing and part are never saved and their hashes are guarded.
``--mode bent_length`` instead compares native/extended bent-leader length,
without moving the elbow. The extension comes from actual rendered deficit.
``--mode document_length`` tests the documented drawing-wide annotation leader
length preference instead, capturing all view/sheet annotation bodies and leaders
so intended layout changes are visible while semantics and attachments stay exact.

Evidence checkpoint (2026-09-06, original commit 3efbf8a2): document_length
passed on the saved pre-policy rocker. Document length 6.35 -> 13.36625 mm
moved B's actual frame by +7.01625 mm, preserving its elbow, face and reopened
render. A/C and one GTol leader also moved; this was not a full-sheet fit proof.
Report: cad/out/reports/datum-shoulder-42ahzbdc/datum-shoulder.json (ha-perf-channel).
The older shoulder and bent_length modes remain explicit historical controls:
SetPosition2 clamped, and the annotation length setter retained -1 while document
control was active. Neither is a verdict against the native leader mechanism.
The default is the positive document-length route; no historical commits are
required to run it. An independently saved pre-policy drawing must have B's
non-forced Shoulder=False; pass --part when using an archived drawing copy.
The diagnostic requires an empty native document session and refuses pre-existing
documents; it never clears them. Cleanup closes only the exact owned copy with
save=False. A later unrelated active/open document makes cleanup refuse, while
source hashes and the final report are still checked/written.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from enum import StrEnum
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_view_packing import Rect  # noqa: E402
from _drawing_annotation_bounds import (  # noqa: E402
    _native_snapshot,
    _installed_swconst,
    bounds_from_snapshot,
)
from diagnostics import probe_datum_frame_anchors as frames  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_datum_dimension_attachment import (  # noqa: E402
    outboard_target,
    same_handles,
    without_datum,
    raw_display_data,
)
from diagnostics.probe_datum_sheet_z import guard_sources  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402


class ShoulderPolicy(StrEnum):
    STRAIGHT = "straight"
    BENT = "bent"


class ControlMode(StrEnum):
    SHOULDER = "shoulder"
    BENT_LENGTH = "bent_length"
    DOCUMENT_LENGTH = "document_length"


class OwnedDrawingCopy:
    """One owned native drawing; references are witnessed, never close targets.

    ISldWorks.CloseDoc may unload non-active hidden references. Consequently this
    copy-only diagnostic requires an initially empty document inventory and
    refuses any later unrelated document before even calling the scoped close.
    """

    def __init__(self, adapter, directory, source_part):
        self.adapter = adapter
        self.app = _early_bound(adapter.swApp, "ISldWorks")
        self.directory = directory.resolve()
        self.source_part = source_part.resolve()
        self.handle = self.reference = self.expected = None
        self.paths = set()
        self.titles = {}
        if (
            self.app.GetDocuments()
            or self.app.ActiveDoc is not None
            or adapter.currentModel is not None
        ):
            raise RuntimeError(
                "datum control requires an empty native document session; no existing documents were closed"
            )

    def _path(self, path):
        path = path.resolve()
        if path.parent != self.directory or path.suffix.lower() != ".slddrw":
            raise RuntimeError(
                "owned drawing path must be one exact copy inside the diagnostic directory"
            )
        return path

    def _inventory(self, owned=None):
        found = []
        names = set()
        for raw in self.app.GetDocuments() or ():
            document = _early_bound(raw, "IModelDoc2")
            native_path = str(document.GetPathName())
            if not native_path:
                raise RuntimeError(
                    "unrelated unsaved document prevents isolated cleanup"
                )
            path = Path(native_path).resolve()
            if path in names:
                raise RuntimeError(
                    "duplicate native document paths prevent isolated cleanup"
                )
            names.add(path)
            if owned is not None and int(self.app.IsSame(document, owned)) == 1:
                found.append(document)
                continue
            if (
                path == self.source_part
                and self.reference is not None
                and int(self.app.IsSame(document, self.reference)) == 1
            ):
                continue  # never a close target, including when still loaded after close
            if (
                path == self.source_part
                and owned is not None
                and self.reference is None
                and int(document.GetType()) == 1
            ):
                self.reference = (
                    document  # first loaded implicitly by the owned drawing
                )
                continue
            raise RuntimeError("unrelated native document prevents isolated cleanup")
        if owned is not None and len(found) != 1:
            raise RuntimeError(
                "owned drawing is not the unique native inventory member"
            )
        if self.source_part not in names:
            self.reference = None  # SW may unload an implicitly opened reference

    def expect_open(self, path):
        if self.handle is not None:
            raise RuntimeError(
                "previous owned drawing must close before another is opened"
            )
        self._inventory()
        if self.app.ActiveDoc is not None or self.adapter.currentModel is not None:
            raise RuntimeError(
                "unrelated active document prevents opening a diagnostic copy"
            )
        self.expected = self._path(path)
        self.paths = {self.expected}
        self.titles.clear()

    def _validate_active(self):
        current = _early_bound(self.adapter.currentModel, "IModelDoc2")
        active = _early_bound(self.app.ActiveDoc, "IModelDoc2")
        if (
            current is None
            or active is None
            or int(self.app.IsSame(current, active)) != 1
        ):
            raise RuntimeError("active document is not the exact owned drawing")
        path = Path(str(current.GetPathName())).resolve()
        if path not in self.paths or int(current.GetType()) != 3:
            raise RuntimeError(
                "active native drawing path is not owned by this control"
            )
        named = self.app.GetOpenDocumentByName(str(path))
        if named is None or int(self.app.IsSame(named, current)) != 1:
            raise RuntimeError(
                "owned path does not resolve to the exact active native drawing"
            )
        if self.handle is not None and int(self.app.IsSame(current, self.handle)) != 1:
            raise RuntimeError("owned native drawing identity was replaced")
        # GetTitle is a native window title, not a filename parser: drawings may
        # include " - Sheet1". Witness it only after full-path/native identity.
        title = str(current.GetTitle())
        if not title or self.titles.get(path, title) != title:
            raise RuntimeError("owned drawing native title changed unexpectedly")
        self.titles[path] = title
        self._inventory(current)
        return current

    def claim(self):
        if self.expected is None:
            raise RuntimeError("no diagnostic copy opening was authorized")
        self.handle = self._validate_active()

    def authorize_save(self, path):
        if self.handle is None:
            raise RuntimeError("only an already owned native drawing may be exported")
        self._validate_active()
        self.paths.add(self._path(path))

    async def close(self):
        if self.handle is None:
            # A failed open may have reached SW before the adapter returned.
            # Claim only the exact authorized path with the same full guards.
            if self.expected is None:
                return
            if self.adapter.currentModel is None:
                if (
                    self.app.ActiveDoc is not None
                    or self.app.GetOpenDocumentByName(str(self.expected)) is not None
                ):
                    raise RuntimeError(
                        "failed open left an unclaimed active document; refusing cleanup"
                    )
                return
            self.claim()
        self._validate_active()
        closed_paths = tuple(self.paths)
        check(
            "close exact owned datum copy without saving",
            await self.adapter.close_model(save=False),
        )
        if any(
            self.app.GetOpenDocumentByName(str(path)) is not None
            for path in closed_paths
        ):
            raise RuntimeError("owned datum drawing remained open after scoped close")
        self.handle = self.expected = None
        self.paths.clear()
        self.titles.clear()
        self._inventory()


async def finalize_probe(owned, report, report_path):
    """Source hashes and evidence survive a refusal to close unrelated state."""
    try:
        if owned is not None:
            await owned.close()
    except Exception as error:
        report["cleanup_error"] = repr(error)
        raise
    finally:
        try:
            guard_sources(report)
        finally:
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            _telemetry.info(f"native datum shoulder observations: {report_path}")


def document_length(extension):
    constants = _installed_swconst()
    preference = int(constants.swDetailingAnnotationBentLeaderLength)
    option = int(constants.swDetailingNoOptionSpecified)
    value = float(extension.GetUserPreferenceDouble(preference, option))
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError("document bent leader length must be positive and finite")
    return value, preference, option


def set_document_length(extension, requested):
    if not math.isfinite(requested) or requested <= 0:
        raise RuntimeError(
            "requested document leader length must be positive and finite"
        )
    before, preference, option = document_length(extension)
    returned = bool(extension.SetUserPreferenceDouble(preference, option, requested))
    after, _, _ = document_length(extension)
    return {
        "before_m": before,
        "returned": returned,
        "requested_m": requested,
        "after_m": after,
    }


def all_annotation_layout(adapter):
    """Record global property effects, including sheet/template-owned annotations."""
    records, handles = {}, {}
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet in drawing.GetViews() or ():
        for raw_view in sheet:
            view = _early_bound(raw_view, "IView")
            view_key = str(view.GetName2())
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                name = f"{view_key}/{annotation.GetName()}"
                if name in records:
                    raise RuntimeError("global annotation inventory is duplicated")
                entities = tuple(annotation.GetAttachedEntities3() or ())
                kinds = tuple(int(k) for k in annotation.GetAttachedEntityTypes() or ())
                if len(entities) != len(kinds) or len(entities) != int(
                    annotation.GetAttachedEntityCount3()
                ):
                    raise RuntimeError("global annotation attachment arrays disagree")
                kind = int(annotation.GetType())
                generic = raw_display_data(annotation)
                semantic = {
                    "kind": kind,
                    "owner_type": int(annotation.OwnerType),
                    "owner_null": annotation.Owner is None,
                    "visible": int(annotation.Visible),
                    "dangling": bool(annotation.IsDangling()),
                    "attachment_types": kinds,
                    "null_attachments": tuple(entity is None for entity in entities),
                    "texts": tuple(
                        {
                            key: value
                            for key, value in text.items()
                            if key not in {"position", "plane"}
                        }
                        for text in generic["texts"]
                    ),
                }
                if kind == 2:
                    tag = _early_bound(annotation.GetSpecificAnnotation(), "IDatumTag")
                    semantic["datum"] = (
                        str(tag.GetLabel()),
                        bool(tag.Shoulder),
                        bool(tag.ForcedShoulder),
                        int(tag.GetDisplayStyle()),
                    )
                if kind == 5:
                    gtol = _early_bound(annotation.GetSpecificAnnotation(), "IGtol")
                    frame_xml = []
                    for index in range(1, frames.count(gtol.GetFrameCount()) + 1):
                        raw_frame = gtol.GetFrame(index)
                        frame_xml.append(
                            str(_early_bound(raw_frame, "IGtolFrame").GetSymbolXml())
                            if raw_frame is not None
                            else None
                        )
                    semantic["frames"] = tuple(frame_xml)
                row = {
                    "semantic": semantic,
                    "generic": generic,
                    "position": tuple(annotation.GetPosition() or ()),
                }
                try:
                    native = _native_snapshot(
                        annotation, adapter.currentModel.Extension
                    )
                    row["native"] = asdict(native)
                    row["measurement"] = asdict(bounds_from_snapshot(native))
                except ValueError as error:
                    row["measurement_exclusion"] = str(error)
                records[name] = row
                handles[name] = (
                    annotation,
                    *(
                        entity
                        for entity in (annotation.Owner, *entities)
                        if entity is not None
                    ),
                )
    return records, handles


def compare_all_annotation_layout(
    app, before, after, before_handles=None, after_handles=None
):
    if before.keys() != after.keys():
        raise RuntimeError("document leader policy changed annotation inventory")
    changes = {}
    for name, initial in before.items():
        actual = after[name]
        if initial["semantic"] != actual["semantic"]:
            raise RuntimeError(
                f"{name}: document leader policy changed annotation semantics"
            )
        if before_handles is not None:
            same_handles(app, before_handles[name], after_handles[name])
        if initial.get("measurement_exclusion") != actual.get("measurement_exclusion"):
            raise RuntimeError(f"{name}: document leader policy changed bounds support")
        if (
            initial["generic"] != actual["generic"]
            or initial["position"] != actual["position"]
        ):
            changes[name] = {
                "position_before": initial["position"],
                "position_after": actual["position"],
                "body_before": initial.get("measurement", {}).get("body"),
                "body_after": actual.get("measurement", {}).get("body"),
            }
    return changes


def bent_length_target(record, gap_m=0.003):
    """Only the positively observed rightward shoulder geometry is in scope."""
    anchor = record["position"]
    frame = record["frame_relation"]["frame"]
    joint = (frame[0], (frame[1] + frame[3]) / 2)
    if abs(anchor[1] - joint[1]) > 1e-8 or joint[0] <= anchor[0]:
        raise RuntimeError("bent-length control requires the native rightward shoulder")
    matches = []
    for line in record["generic"]["lines"]:
        if len(line) != 10 or not all(math.isfinite(v) for v in line):
            raise RuntimeError("native shoulder line is invalid")
        start, end = tuple(line[4:6]), tuple(line[7:9])
        if (math.dist(start, anchor[:2]) <= 1e-8 and math.dist(end, joint) <= 1e-8) or (
            math.dist(end, anchor[:2]) <= 1e-8 and math.dist(start, joint) <= 1e-8
        ):
            matches.append(math.dist(start, end))
    if len(matches) != 1:
        raise RuntimeError("native elbow-to-frame shoulder segment is not unique")
    native = matches[0]
    body = record["measurement"]["body"]
    deficit = max(0.0, record["view_outline"][2] + gap_m - body["xmin"])
    return {
        "native_measured_m": native,
        "deficit_m": deficit,
        "requested_m": native + deficit,
        "gap_m": gap_m,
    }


def verify_length_change(trial):
    length = trial["length"]
    expected = (
        length["requested_m"]
        if trial["variant"] == "extended_bent"
        else length["initial_readback_m"]
    )
    if any(
        not math.isfinite(value) or abs(value - expected) > 1e-8
        for value in (length["after_readback_m"], length["reopened_readback_m"])
    ):
        raise RuntimeError("native BentLeaderLength did not retain requested value")
    if math.dist(trial["styled"]["position"], trial["after"]["position"]) > 1e-8:
        raise RuntimeError("native bent length moved the datum elbow")
    if trial["variant"] != "extended_bent":
        return
    delta = length["requested_m"] - length["native_measured_m"]
    expected_body = Rect(**trial["styled"]["measurement"]["body"]).translated(
        (delta, 0)
    )
    expected_frame = Rect(*trial["styled"]["frame_relation"]["frame"]).translated(
        (delta, 0)
    )
    for phase in ("after", "reopened"):
        actual_body = Rect(**trial[phase]["measurement"]["body"])
        actual_frame = Rect(*trial[phase]["frame_relation"]["frame"])
        if any(
            abs(a - b) > 1e-8
            for a, b in zip(
                (*expected_body.bounds, *expected_frame.bounds),
                (*actual_body.bounds, *actual_frame.bounds),
            )
        ):
            raise RuntimeError(
                "native bent length did not translate the measured datum body"
            )
    actual = trial["after"]["measurement"]["body"]
    if actual["xmin"] - trial["after"]["view_outline"][2] < length["gap_m"] - 1e-8:
        raise RuntimeError("native bent length does not clear the measured view")


def verify_document_length(trial):
    document = trial["document_length"]
    if not document["returned"]:
        raise RuntimeError("native document bent leader length setter rejected")
    candidate = trial["variant"] == "extended_document"
    # Reuse only the geometric witness, not the annotation getter: -1 remains
    # a diagnostic observation when the length is owned by the document.
    verify_length_change(
        {
            **trial,
            "variant": "extended_bent" if candidate else "native_bent",
            "length": {
                **trial["length"],
                "initial_readback_m": document["before_m"],
                "after_readback_m": document["after_m"],
                "reopened_readback_m": document["reopened_m"],
            },
        }
    )


def find_target(records):
    found = tuple(key for key, record in records.items() if record["label"] == "B")
    if len(found) != 1:
        raise RuntimeError("rocker B must be a unique native datum")
    key = found[0]
    row = records[key]
    if (
        row["attachment_types"] != (2,)
        or row["null_attachments"] != (False,)
        or row["style"] != 1
    ):
        raise RuntimeError("rocker B is not a square datum on one exact face")
    if row["shoulder"] or row["forced_shoulder"]:
        raise RuntimeError(
            "positive control requires initial non-forced Shoulder=False"
        )
    return key


def same_target(before, after):
    fields = (
        "label",
        "owner_type",
        "visible",
        "dangling",
        "attachment_types",
        "null_attachments",
        "geometry",
        "configuration",
        "style",
        "label_render",
    )
    if any(before[field] != after[field] for field in fields):
        raise RuntimeError(
            "shoulder control changed target geometry, identity or label"
        )
    old, new = before["frame_relation"]["frame"], after["frame_relation"]["frame"]
    if any(
        abs(a - b) > 1e-8
        for a, b in zip(
            (old[2] - old[0], old[3] - old[1]), (new[2] - new[0], new[3] - new[1])
        )
    ):
        raise RuntimeError("shoulder control changed native datum frame size")


def set_shoulder(tag, policy):
    policy = ShoulderPolicy(policy)
    tag.Shoulder = policy is ShoulderPolicy.BENT
    actual = bool(tag.Shoulder)
    if actual != (policy is ShoulderPolicy.BENT):
        raise RuntimeError(f"native Shoulder rejected requested policy {policy.value}")
    return {
        "policy": policy.value,
        "actual": actual,
        "forced": bool(tag.ForcedShoulder),
    }


async def probe(
    adapter, source, directory, mode=ControlMode.DOCUMENT_LENGTH, *, part=None
):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    part = (part or source.parent.parent / "sldprt/rocker-arm.SLDPRT").resolve(
        strict=True
    )
    report = {
        "mode": ControlMode(mode).value,
        "source_hashes": {str(p): file_digest(p) for p in (source, part)},
        "trials": [],
    }
    app = _early_bound(adapter.swApp, "ISldWorks")
    report_path = directory / "datum-shoulder.json"
    baseline, target = None, None
    owned = None

    def export(stem):
        drawing = directory / f"{directory.name}-{stem}.SLDDRW"
        pdf, png = drawing.with_suffix(".pdf"), drawing.with_suffix(".png")
        owned.authorize_save(drawing)
        save_drawing(adapter, str(drawing), pdf_path=str(pdf))
        render_pdf_png(pdf, png)
        return {"drawing": str(drawing), "pdf": str(pdf), "png": str(png)}

    try:
        owned = OwnedDrawingCopy(adapter, directory, part)
        variants = {
            ControlMode.SHOULDER: ("straight", "bent"),
            ControlMode.BENT_LENGTH: ("native_bent", "extended_bent"),
            ControlMode.DOCUMENT_LENGTH: ("native_document", "extended_document"),
        }[mode]
        for variant in variants:
            policy = (
                ShoulderPolicy.STRAIGHT
                if variant == "straight"
                else ShoulderPolicy.BENT
            )
            trial = {"variant": variant, "policy": policy.value}
            report["trials"].append(trial)
            try:
                copy = directory / f"{directory.name}-{variant}-source.SLDDRW"
                owned.expect_open(copy)
                shutil.copy2(source, copy)
                check(
                    "open unique rocker shoulder copy",
                    await adapter.open_model(str(copy)),
                )
                if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                    raise RuntimeError(
                        "active drawing is not the unique requested copy"
                    )
                owned.claim()
                records, handles = frames.capture(adapter, part)
                key = find_target(records)
                before = records[key]
                trial["before"] = before
                if baseline is None:
                    baseline = before
                    target, direction = before["position"], "native_elbow_stationary"
                    if mode == ControlMode.SHOULDER:
                        target, direction = outboard_target(
                            before["position"],
                            Rect(**before["measurement"]["body"]),
                            Rect(*before["view_outline"]),
                        )
                        target = (*target[:2], before["position"][2])
                    report["shared_target"] = {"xyz": target, "direction": direction}
                same_target(baseline, before)
                if math.dist(baseline["position"], before["position"]) > 1e-8:
                    raise RuntimeError(
                        "independent shoulder copies changed initial position"
                    )
                original_handles = handles[key]
                annotation, tag = original_handles[:2]
                manufacturing = without_datum(
                    attachments.snapshot(adapter.currentModel, app=app), key + "/2"
                )
                trial["before_export"] = export(variant + "-before")
                trial["shoulder"] = set_shoulder(tag, policy)
                styled, styled_handles = frames.capture(adapter, part)
                trial["styled"] = styled[key]
                same_target(before, styled[key])
                same_handles(app, original_handles, styled_handles[key])
                if mode == ControlMode.DOCUMENT_LENGTH:
                    trial["all_annotations_before"], global_handles = (
                        all_annotation_layout(adapter)
                    )
                if mode == ControlMode.SHOULDER:
                    trial["position_returned"] = bool(annotation.SetPosition2(*target))
                else:
                    trial["length"] = bent_length_target(styled[key])
                    trial["length"]["initial_readback_m"] = float(
                        annotation.BentLeaderLength
                    )
                    if variant == "extended_bent":
                        annotation.BentLeaderLength = trial["length"]["requested_m"]
                    if mode == ControlMode.DOCUMENT_LENGTH:
                        extension = adapter.currentModel.Extension
                        current_length, preference, option = document_length(extension)
                        trial["document_length"] = {
                            "before_m": current_length,
                            "after_m": current_length,
                            "requested_m": current_length,
                            "returned": True,
                            "operation": "read_only_baseline",
                            "preference": preference,
                            "option": option,
                        }
                        if variant == "extended_document":
                            trial["document_length"].update(
                                set_document_length(
                                    extension,
                                    trial["length"]["requested_m"],
                                )
                            )
                            trial["document_length"]["operation"] = (
                                "set_document_length"
                            )
                        trial["document_length"]["rebuild_returned"] = bool(
                            adapter.currentModel.EditRebuild3()
                        )
                        if not trial["document_length"]["rebuild_returned"]:
                            raise RuntimeError("document leader policy rebuild failed")
                    trial["length"]["after_readback_m"] = float(
                        annotation.BentLeaderLength
                    )
                observed, observed_handles = frames.capture(adapter, part)
                trial["after"] = observed[key]
                if mode == ControlMode.DOCUMENT_LENGTH:
                    trial["all_annotations_after"], after_global_handles = (
                        all_annotation_layout(adapter)
                    )
                    trial["global_layout_changes"] = compare_all_annotation_layout(
                        app,
                        trial["all_annotations_before"],
                        trial["all_annotations_after"],
                        global_handles,
                        after_global_handles,
                    )
                same_target(before, observed[key])
                same_handles(app, original_handles, observed_handles[key])
                if observed[key]["shoulder"] != (policy is ShoulderPolicy.BENT):
                    raise RuntimeError(
                        "native position changed requested shoulder policy"
                    )
                trial["xy_error_m"] = math.dist(
                    target[:2], observed[key]["position"][:2]
                )
                trial["after_export"] = export(variant + "-after")
                attachments.compare(
                    manufacturing,
                    without_datum(
                        attachments.snapshot(adapter.currentModel, app=app), key + "/2"
                    ),
                    "shoulder position",
                )
                await owned.close()
                owned.expect_open(Path(trial["after_export"]["drawing"]))
                check(
                    "reopen saved rocker shoulder copy",
                    await adapter.open_model(trial["after_export"]["drawing"]),
                )
                owned.claim()
                reopened, reopened_handles = frames.capture(adapter, part)
                trial["reopened"] = reopened[key]
                if mode in (ControlMode.BENT_LENGTH, ControlMode.DOCUMENT_LENGTH):
                    trial["length"]["reopened_readback_m"] = float(
                        reopened_handles[key][0].BentLeaderLength
                    )
                if mode == ControlMode.DOCUMENT_LENGTH:
                    trial["document_length"]["reopened_m"], _, _ = document_length(
                        adapter.currentModel.Extension
                    )
                    trial["all_annotations_reopened"], _ = all_annotation_layout(
                        adapter
                    )
                    trial["global_reopen_layout_changes"] = (
                        compare_all_annotation_layout(
                            app,
                            trial["all_annotations_after"],
                            trial["all_annotations_reopened"],
                        )
                    )
                same_target(observed[key], reopened[key])
                if (
                    reopened[key]["shoulder"] != (policy is ShoulderPolicy.BENT)
                    or math.dist(observed[key]["position"], reopened[key]["position"])
                    > 1e-8
                ):
                    raise RuntimeError("native shoulder or position changed on reopen")
                attachments.compare(
                    manufacturing,
                    without_datum(
                        attachments.snapshot(adapter.currentModel, app=app), key + "/2"
                    ),
                    "shoulder reopen",
                )
                trial["reopened_export"] = export(variant + "-reopened")
                if mode == ControlMode.BENT_LENGTH:
                    verify_length_change(trial)
                if mode == ControlMode.DOCUMENT_LENGTH:
                    verify_document_length(trial)
                if mode == ControlMode.SHOULDER and not trial["position_returned"]:
                    raise RuntimeError(
                        "native position returned false; actual state retained"
                    )
            except Exception as error:
                trial["error"] = repr(error)
            finally:
                await owned.close()
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        await finalize_probe(owned, report, report_path)
    if any("error" in trial for trial in report["trials"]):
        raise RuntimeError(f"native shoulder witness failed; evidence: {report_path}")
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument(
        "--part",
        type=Path,
        help="exact referenced rocker part for an archived drawing copy",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(ControlMode),
        default=ControlMode.DOCUMENT_LENGTH,
        type=ControlMode,
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    part = args.part.resolve(strict=True) if args.part is not None else None
    if source.name.lower() != "rocker-arm.slddrw" and part is None:
        raise ValueError("this bounded control requires saved rocker-arm.SLDDRW")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--mode",
                args.mode.value,
                "--worker",
                *(["--part", str(part)] if part is not None else []),
            ],
            "native datum shoulder control",
            com=True,
            log_stem="datum-shoulder",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("shoulder control requires the coordinated COM seat")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="datum-shoulder-", dir=reports))
    return run_build(
        lambda adapter: probe(adapter, source, directory, args.mode, part=part)
    )


if __name__ == "__main__":
    raise SystemExit(main())

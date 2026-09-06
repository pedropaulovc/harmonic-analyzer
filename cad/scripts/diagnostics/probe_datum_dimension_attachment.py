"""Copy-only paired gear datum insertion, with an optional no-shoulder control.

Run with the saved cone-gear.SLDDRW. Each route starts from an independent byte
copy. Default routes replace A by native dimension-name selection: compare
insert/label/clear/rebuild against insert/label/position/clear/rebuild, using a
target derived from the measured dimension body. ``--mode shoulder_false``
tests the existing edge datum separately. Export insertion before a derived
nonzero outboard move and save/reopen. Capture both
IDatumTag primitives and IAnnotation.GetDisplayData without assuming that their
coordinate frames agree. Original part/drawing hashes are checked on all exits.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check, run_build  # noqa: E402
from _drawing_annotation_bounds import (  # noqa: E402
    annotation_box,
    bounds_from_snapshot,
    _native_snapshot,
    _frame_lines,
)
from _drawing_common import null_callout  # noqa: E402
from _drawing_marks import _named_dimension  # noqa: E402
from _drawing_native_callouts import placement_candidates  # noqa: E402
from _drawing_view_packing import Rect  # noqa: E402
from diagnostics import probe_drawing_attachments as attachments  # noqa: E402
from diagnostics.probe_datum_sheet_z import guard_sources  # noqa: E402
from diagnostics.probe_native_model_pmi import file_digest, render_pdf_png  # noqa: E402
import _telemetry  # noqa: E402

EPSILON = 1e-8


def select_bore(adapter, bore):
    model, app = adapter.currentModel, adapter.swApp
    drawing = _early_bound(model, "IDrawingDoc")
    if not drawing.ActivateView(str(bore["view"].GetName2())):
        raise RuntimeError("cannot activate bore dimension view")
    model.ClearSelection2(True)
    name = str(bore["display"].GetNameForSelection() or "")
    if not name or not model.Extension.SelectByID2(
        name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError("native named bore dimension selection rejected")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if (
        int(selection.GetSelectedObjectCount2(-1)) != 1
        or int(selection.GetSelectedObjectType3(1, -1)) != 14
        or int(app.IsSame(selection.GetSelectedObject6(1, -1), bore["display"])) != 1
    ):
        raise RuntimeError("named selection is not the exact bore display dimension")
    annotation = _early_bound(bore["display"].GetAnnotation(), "IAnnotation")
    if (
        int(app.IsSame(annotation, bore["annotation"])) != 1
        or int(annotation.OwnerType) != 0
        or int(app.IsSame(annotation.Owner, bore["view"])) != 1
    ):
        raise RuntimeError("selected bore dimension has the wrong native owner")


def bore_target(adapter):
    matches = []
    for view_key, view in attachments.views(adapter.currentModel).items():
        for raw in view.GetAnnotationsByType(4) or ():
            annotation = _early_bound(raw, "IAnnotation")
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            if str(dimension.Name) != "BoreCutDia":
                continue
            full = str(dimension.FullName)
            if (
                full != "BoreCutDia@BoreProfile@cone-gear.Part"
                or display.IsReferenceDim()
            ):
                raise RuntimeError(
                    f"bore display has the wrong source dimension: {full}"
                )
            source = _early_bound(view.ReferencedDocument, "IModelDoc2")
            _, source_dimension = _named_dimension(
                SimpleNamespace(currentModel=source), "BoreProfile", "BoreCutDia"
            )
            if int(adapter.swApp.IsSame(dimension, source_dimension)) != 1:
                raise RuntimeError(
                    "bore display is not the exact source feature dimension"
                )
            values = tuple(
                dimension.GetSystemValue3(3, str(view.ReferencedConfiguration)) or ()
            )
            if len(values) != 1 or not math.isfinite(float(values[0])):
                raise RuntimeError("bore source value is unreadable")
            matches.append(
                {
                    "view_key": view_key,
                    "view": view,
                    "annotation": annotation,
                    "display": display,
                    "dimension": dimension,
                    "full_name": full,
                    "value_m": float(values[0]),
                    "configuration": str(view.ReferencedConfiguration),
                    "source": str(Path(source.GetPathName()).resolve()),
                }
            )
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one BoreCutDia drawing instance, found {len(matches)}"
        )
    return matches[0]


def datum_a(adapter, bore):
    matches = []
    for raw in bore["view"].GetAnnotationsByType(2) or ():
        annotation = _early_bound(raw, "IAnnotation")
        tag = _early_bound(annotation.GetSpecificAnnotation(), "IDatumTag")
        if str(tag.GetLabel()) == "A":
            matches.append(annotation)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one native datum A, found {len(matches)}")
    return matches[0]


def binding(app, entities, kinds, display):
    if len(entities) != len(kinds) or len(entities) != 1:
        raise RuntimeError("datum attachment array is not one complete entity")
    if kinds == (14,):
        if int(app.IsSame(entities[0], display)) != 1:
            raise RuntimeError("datum is attached to a different display dimension")
        return "exact_display_dimension"
    if kinds == (0,) and entities[0] is None:
        return "unsupported_null"
    if kinds[0] in {1, 2, 3} and entities[0] is not None:
        return "model_geometry"
    raise RuntimeError(f"unverified datum attachment kind: {kinds}")


def raw_display_data(annotation):
    """Capture the coordinate-frame question before applying calibrated bounds."""
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")

    def count(method):
        result = int(getattr(data, method)())
        if not 0 <= result <= 10000:
            raise RuntimeError(f"unbounded datum primitive count: {method}={result}")
        return result

    return {
        "lines": [tuple(data.GetLineAtIndex3(i)) for i in range(count("GetLineCount"))],
        "arcs": [tuple(data.GetArcAtIndex2(i)) for i in range(count("GetArcCount"))],
        "texts": [
            {
                "value": str(data.GetTextAtIndex(i)),
                "position": tuple(data.GetTextPositionAtIndex(i) or ()),
                "plane": tuple(data.GetTextPlaneAtIndex(i) or ()),
                "height": float(data.GetTextHeightAtIndex(i)),
                "font": str(data.GetTextFontAtIndex(i)),
                "angle": float(data.GetTextAngleAtIndex(i)),
                "reference": int(data.GetTextRefPositionAtIndex(i)),
            }
            for i in range(count("GetTextCount"))
        ],
    }


def datum_state(adapter, bore, annotation):
    app, view = adapter.swApp, bore["view"]
    tag = _early_bound(annotation.GetSpecificAnnotation(), "IDatumTag")
    owner = annotation.Owner
    if (
        int(annotation.GetType()) != 2
        or int(annotation.OwnerType) != 0
        or int(annotation.Visible) != 1
        or annotation.IsDangling()
        or int(app.IsSame(owner, view)) != 1
        or int(app.IsSame(tag.GetAnnotation(), annotation)) != 1
    ):
        raise RuntimeError(
            "datum native identity/view/visibility/dangling witness failed"
        )
    entities = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(int(v) for v in annotation.GetAttachedEntityTypes() or ())
    if int(annotation.GetAttachedEntityCount3()) != len(entities):
        raise RuntimeError("datum native attachment count changed")
    binding_error = None
    try:
        tag_binding = binding(app, entities, kinds, bore["display"])
    except RuntimeError as error:
        # Preserve native display evidence, export it, then fail the route.
        # This is an observation, never an accepted attachment fallback.
        tag_binding, binding_error = "unverified", str(error)
    raw_display = raw_display_data(annotation)
    measurement_error = None
    try:
        snapshot = _native_snapshot(annotation, adapter.currentModel.Extension)
        measured = bounds_from_snapshot(snapshot)  # datum A has no symbol-font tokens
        frame = _frame_lines(snapshot.lines)
    except ValueError as error:
        snapshot, measured, frame, measurement_error = None, None, (), str(error)
    point = tuple(float(v) for v in annotation.GetPosition() or ())
    if len(point) != 3 or not all(math.isfinite(v) for v in point):
        raise RuntimeError("datum has no finite native position")
    state = {
        "name": str(annotation.GetName()),
        "label": str(tag.GetLabel()),
        "shoulder": bool(tag.Shoulder),
        "forced_shoulder": bool(tag.ForcedShoulder),
        "style": int(tag.GetDisplayStyle()),
        "attachment_types": kinds,
        "binding": tag_binding,
        "binding_error": binding_error,
        "null_attachments": tuple(entity is None for entity in entities),
        "geometry": tuple(
            attachments.geometry(e, k)
            for e, k in zip(entities, kinds)
            if k in {1, 2, 3} and e is not None
        ),
        "text": tuple(
            str(tag.GetTextAtIndex(i)) for i in range(int(tag.GetTextCount()))
        ),
        "frame_edge_lengths_m": tuple(
            sorted(round(math.dist(line.start, line.end), 10) for line in frame)
        ),
        "frame_witness": "rectangle" if len(frame) == 4 else "unverified",
        "format": tuple(snapshot.format_signature) if snapshot is not None else (),
        "position": point,
        "specific_data": {
            "lines": [
                tuple(tag.GetLineAtIndex(i)) for i in range(int(tag.GetLineCount()))
            ],
            "text_positions": [
                tuple(tag.GetTextPositionAtIndex(i))
                for i in range(int(tag.GetTextCount()))
            ],
        },
        "raw_display_data": raw_display,
        "display_data": asdict(snapshot) if snapshot is not None else None,
        "measurement": asdict(measured) if measured is not None else None,
        "measurement_error": measurement_error,
    }
    if state["label"] != "A" or not state["text"]:
        raise RuntimeError("native datum label/text did not persist")
    return state, (annotation, tag, owner, *entities)


def same_semantics(before, after):
    ignored = {
        "position",
        "specific_data",
        "display_data",
        "raw_display_data",
        "measurement",
    }
    if before.keys() != after.keys():
        raise RuntimeError("native datum witness fields changed")
    for field in before.keys() - ignored:
        if before[field] != after[field]:
            raise RuntimeError(f"native datum {field} changed")


def same_handles(app, before, after):
    if len(before) != len(after) or any(
        int(app.IsSame(a, b)) != 1
        for a, b in zip(before, after)
        if a is not None or b is not None
    ):
        raise RuntimeError("native datum/owner/attachment identity changed")


def without_datum(snapshot, key):
    result = deepcopy(snapshot)
    if sum(key in result[section] for section in ("checked", "excluded")) != 1:
        raise RuntimeError(
            "target datum missing or duplicated in manufacturing snapshot"
        )
    for section in ("checked", "excluded"):
        result[section].pop(key, None)
    return result


def outboard_target(position, body, outline):
    candidates = placement_candidates(body, outline, ())
    moving = [c for c in candidates if math.hypot(*c.delta) > EPSILON]
    if not moving:
        raise RuntimeError("derived datum control has no nonzero target")
    candidate = moving[0]
    return (
        position[0] + candidate.delta[0],
        position[1] + candidate.delta[1],
        0.0,
    ), candidate.direction.value


def dimension_target_xy(position, dimension_body, datum_body):
    """Put the datum beside the measured dimension body, without feature picks."""
    if len(position) != 3 or not all(math.isfinite(v) for v in position):
        raise RuntimeError("dimension has no finite native sheet anchor")
    dx = (
        dimension_body.xmin
        - position[0]
        - (datum_body.xmax - datum_body.xmin) / 2
        - 0.003
    )
    dy = dimension_body.ymin - position[1] - (datum_body.ymax - datum_body.ymin) - 0.003
    return position[0] + dx, position[1] + dy, 0.0


def replace_on_dimension(
    adapter, bore, old_annotation, *, target=None, observations=None
):
    model, app = adapter.currentModel, adapter.swApp
    model.ClearSelection2(True)
    if not old_annotation.Select2(False, 0):
        raise RuntimeError("copied datum A selection rejected before replacement")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if (
        int(selection.GetSelectedObjectCount2(-1)) != 1
        or int(selection.GetSelectedObjectType3(1, -1)) != 36
    ):
        raise RuntimeError("datum replacement would delete an unexpected selection")
    selected = _early_bound(selection.GetSelectedObject6(1, -1), "IDatumTag")
    if int(app.IsSame(selected.GetAnnotation(), old_annotation)) != 1:
        raise RuntimeError("datum replacement would delete the wrong annotation")
    if not model.Extension.DeleteSelection2(0):
        raise RuntimeError("exact copied datum A deletion failed")
    if tuple(bore["view"].GetAnnotationsByType(2) or ()):
        raise RuntimeError("unexpected datum remains after exact copied A deletion")
    select_bore(adapter, bore)
    raw_tag = model.InsertDatumTag2()
    if raw_tag is None:
        raise RuntimeError("InsertDatumTag2 rejected selected bore display dimension")
    tag = _early_bound(raw_tag, "IDatumTag")
    if not tag.SetLabel("A"):
        raise RuntimeError("new copied dimension-attached datum label rejected")
    annotation = _early_bound(tag.GetAnnotation(), "IAnnotation")
    if target is not None:
        returned = bool(annotation.SetPosition2(*target))
        if observations is not None:
            observations.update(
                requested=target,
                returned=returned,
                actual=tuple(annotation.GetPosition() or ()),
            )
        if not returned:
            raise RuntimeError("datum insertion-finalization position rejected")
    model.ClearSelection2(True)
    if not model.EditRebuild3():
        raise RuntimeError("datum insertion-finalization rebuild failed")
    return annotation


async def probe(adapter, source, directory, mode="paired_dimensions"):
    from solidworks_mcp.adapters.solidworks.drawing import save_drawing

    part = (source.parent.parent / "sldprt/cone-gear.SLDPRT").resolve(strict=True)
    report = {
        "source_hashes": {str(p): file_digest(p) for p in (source, part)},
        "trials": [],
    }
    report_path = directory / "datum-dimension-attachment.json"
    app = _early_bound(adapter.swApp, "ISldWorks")

    def close():
        if not app.CloseAllDocuments(True):
            raise RuntimeError("failed to close copied datum mechanism drawings")
        adapter.currentModel = None

    def export(stem):
        drawing = directory / f"{directory.name}-{stem}.SLDDRW"
        pdf, png = drawing.with_suffix(".pdf"), drawing.with_suffix(".png")
        save_drawing(adapter, str(drawing), pdf_path=str(pdf))
        if not pdf.is_file():
            raise RuntimeError("native datum mechanism export produced no PDF")
        render_pdf_png(pdf, png)
        return {"drawing": str(drawing), "pdf": str(pdf), "png": str(png)}

    try:
        modes = (
            ("dimension", "dimension_placed")
            if mode == "paired_dimensions"
            else ("shoulder_false",)
        )
        for mode in modes:
            trial = {"mode": mode}
            report["trials"].append(trial)
            try:
                copy = directory / f"{directory.name}-{mode}-source.SLDDRW"
                shutil.copy2(source, copy)
                check(
                    "open copied datum mechanism drawing",
                    await adapter.open_model(str(copy)),
                )
                if Path(adapter.currentModel.GetPathName()).resolve() != copy:
                    raise RuntimeError(
                        "active drawing is not the requested unique copy"
                    )
                bore = bore_target(adapter)
                if Path(bore["source"]) != part:
                    raise RuntimeError(
                        "bore dimension references an unguarded source part"
                    )
                trial["bore"] = {
                    k: bore[k]
                    for k in (
                        "full_name",
                        "value_m",
                        "configuration",
                        "source",
                        "view_key",
                    )
                }
                annotation = datum_a(adapter, bore)
                before, _ = datum_state(adapter, bore, annotation)
                trial["before"] = before
                original_key = f"{bore['view_key']}/{before['name']}/2"
                manufacturing = without_datum(
                    attachments.snapshot(adapter.currentModel), original_key
                )
                trial["before_export"] = export(f"{mode}-before")
                if mode in {"dimension", "dimension_placed"}:
                    target = None
                    if mode == "dimension_placed":
                        dimension_bounds = annotation_box(adapter, bore["annotation"])
                        dimension_position = tuple(
                            float(v) for v in bore["annotation"].GetPosition() or ()
                        )
                        target = dimension_target_xy(
                            dimension_position,
                            dimension_bounds.body,
                            Rect(**before["measurement"]["body"]),
                        )
                        trial["dimension_anchor"] = dimension_position
                        trial["dimension_body"] = asdict(dimension_bounds.body)
                    trial["insertion_finalization"] = {
                        "sequence": "insert_label_position_clear_rebuild"
                        if target is not None
                        else "insert_label_clear_rebuild"
                    }
                    annotation = replace_on_dimension(
                        adapter,
                        bore,
                        annotation,
                        target=target,
                        observations=trial["insertion_finalization"],
                    )
                else:
                    _early_bound(
                        annotation.GetSpecificAnnotation(), "IDatumTag"
                    ).Shoulder = False
                native, native_handles = datum_state(adapter, bore, annotation)
                trial["native"] = native
                trial["native_export"] = export(f"{mode}-native")
                if (
                    native["frame_witness"] != "rectangle"
                    or native["measurement"] is None
                ):
                    raise RuntimeError(
                        "native datum frame/bounds remain unverified; raw primitives and PNG captured"
                    )
                if native["binding_error"]:
                    raise RuntimeError(native["binding_error"])
                if (
                    mode in {"dimension", "dimension_placed"}
                    and native["binding"] != "exact_display_dimension"
                ):
                    raise RuntimeError(
                        f"native insertion did not prove dimension attachment: {native['binding']}"
                    )
                if mode == "shoulder_false" and native["shoulder"]:
                    raise RuntimeError(
                        "native datum refuses Shoulder=False; ForcedShoulder is recorded"
                    )
                key = f"{bore['view_key']}/{native['name']}/2"
                attachments.compare(
                    manufacturing,
                    without_datum(attachments.snapshot(adapter.currentModel), key),
                    "native mechanism",
                )
                target, direction = outboard_target(
                    native["position"],
                    Rect(**native["measurement"]["body"]),
                    Rect(*bore["view"].GetOutline()),
                )
                trial["placement"] = {"requested": target, "direction": direction}
                trial["placement"]["returned"] = bool(annotation.SetPosition2(*target))
                after, after_handles = datum_state(adapter, bore, annotation)
                trial["after"] = after
                trial["placement"]["xy_error_m"] = math.dist(
                    target[:2], after["position"][:2]
                )
                same_semantics(native, after)
                same_handles(app, native_handles, after_handles)
                trial["after_export"] = export(f"{mode}-after")
                saved, saved_handles = datum_state(adapter, bore, annotation)
                trial["saved"] = saved
                same_semantics(after, saved)
                same_handles(app, after_handles, saved_handles)
                close()
                check(
                    "reopen saved datum mechanism",
                    await adapter.open_model(trial["after_export"]["drawing"]),
                )
                bore = bore_target(adapter)
                reopened, _ = datum_state(adapter, bore, datum_a(adapter, bore))
                trial["reopened"] = reopened
                same_semantics(saved, reopened)
                if math.dist(saved["position"], reopened["position"]) > EPSILON:
                    raise RuntimeError("datum position changed on save/reopen")
                key = f"{bore['view_key']}/{reopened['name']}/2"
                attachments.compare(
                    manufacturing,
                    without_datum(attachments.snapshot(adapter.currentModel), key),
                    "saved mechanism",
                )
                trial["reopened_export"] = export(f"{mode}-reopened")
            except Exception as error:
                trial["error"] = repr(error)
            finally:
                close()
    finally:
        try:
            close()
        finally:
            try:
                guard_sources(report)
            finally:
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                _telemetry.info(
                    f"datum dimension attachment observations: {report_path}"
                )
    if any("error" in trial for trial in report["trials"]):
        raise RuntimeError(
            f"datum mechanism witness failed; complete evidence: {report_path}"
        )
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing", type=Path)
    parser.add_argument(
        "--mode",
        choices=("paired_dimensions", "shoulder_false"),
        default="paired_dimensions",
    )
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.drawing.resolve(strict=True)
    if source.name.lower() != "cone-gear.slddrw":
        raise ValueError("this bounded mechanism control requires cone-gear.SLDDRW")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--mode",
                args.mode,
                "--worker",
            ],
            "native datum dimension attachment",
            com=True,
            log_stem="datum-dimension-attachment",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("worker requires the coordinated COM seat lock")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="datum-dimension-", dir=reports))
    return run_build(lambda adapter: probe(adapter, source, directory, args.mode))


if __name__ == "__main__":
    raise SystemExit(main())

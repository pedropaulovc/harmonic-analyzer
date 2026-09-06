"""Probe part-drawing attachments and dimension values through layout/reopen.

Run ``uv run python cad/scripts/diagnostics/probe_drawing_attachments.py DRAWING``.
The parent takes the pipeline's COM seat lock. Only a uniquely named drawing
copy under cad/out/reports/drawing-attachments is modified. The JSON report
records every phase and excludes unsupported annotation/geometry kinds from
the checked count. This compares geometry signatures, not persistent entity IDs.
Datums attached to one model IDisplayDimension have a separate semantic attachment
witness: exact native view/target identity, source feature/parameter identity,
configuration, value and tolerance. They are not counted as checked geometry.
Only drawings referencing native parts are supported. Assembly drawings are
rejected before copying or movement: their component ownership and transitive
model dependencies need a separate snapshot contract.

Dimension semantics include the source dimension's native tolerance type/BASIC
designation, separately from attachment geometry, including imported dimensions
with no supported attached entities. Multi-value hole-callout variable overrides
are not represented by IDimensionTolerance.Type and are outside this witness.
--dimension-values
api-capture also records the current/older getter call shapes used to investigate
native reference dimensions. Those observations are evidence, not fallback logic.
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check, run_build  # noqa: E402
from _part_pmi import _face_geometry  # noqa: E402
import _telemetry  # noqa: E402
from solidworks_mcp.adapters.com_variant import double_array  # noqa: E402

_ANNOTATIONS = {2, 4, 5, 7}  # swAnnotationType_e: datum, dimension, GTol, finish
_ENTITY_KINDS = {1, 2, 3}  # swSelectType_e: edge, face, vertex
_SURFACES = {4001, 4002, 4003, 4004, 4005}  # analytic ISurface identities
_LAYOUT_TOLERANCE = 1e-8


class UnsupportedGeometry(ValueError):
    """An attachment exists, but this probe has no geometry signature for it."""


def rounded(values):
    result = tuple(round(float(value), 9) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise RuntimeError(f"non-finite geometry values: {result}")
    return result


def geometry(entity, kind):
    if kind == 1:
        edge = _early_bound(entity, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            raise RuntimeError("attached edge has no curve")
        curve = _early_bound(raw_curve, "ICurve")
        if curve.IsCircle():
            trim = _early_bound(edge.GetCurveParams3(), "ICurveParamData")
            return (
                "circle",
                rounded(curve.CircleParams),
                rounded((trim.UMinValue, trim.UMaxValue)),
                rounded(trim.StartPoint),
                rounded(trim.EndPoint),
            )
        if curve.IsLine():
            vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if any(vertex is None for vertex in vertices):
                raise RuntimeError("attached line has a missing endpoint")
            points = (
                rounded(_early_bound(vertex, "IVertex").GetPoint())
                for vertex in vertices
            )
            return ("line", tuple(sorted(points)))
        raise UnsupportedGeometry("edge is neither a line nor a circle")
    if kind == 2:
        face = _face_geometry(entity)
        if face is None:
            raise RuntimeError("attached face has no surface")
        if face.identity not in _SURFACES:
            raise UnsupportedGeometry(f"surface identity {face.identity}")
        return (
            "face",
            face.identity,
            rounded(face.parameters),
            rounded(face.box),
            rounded(face.outward_normal) if face.outward_normal is not None else None,
        )
    if kind == 3:
        return ("vertex", rounded(_early_bound(entity, "IVertex").GetPoint()))
    raise UnsupportedGeometry(f"attachment kind {kind}")


def views(model):
    """Key views by sheet and stable view name, independent of sheet ordering."""
    drawing = _early_bound(model, "IDrawingDoc")
    found = {}
    for raw_sheet in drawing.GetViews() or ():
        sheet = tuple(raw_sheet)
        if not sheet:
            raise RuntimeError("GetViews returned an empty sheet array")
        sheet_name = str(_early_bound(sheet[0], "IView").GetName2())
        for raw in sheet[1:]:
            view = _early_bound(raw, "IView")
            name = str(view.GetUniqueName() or view.GetName2())
            key = f"{sheet_name}/{name}"
            if key in found:
                raise RuntimeError(f"duplicate drawing view key: {key}")
            found[key] = view
    return found


def referenced_model(view):
    """Resolve a part reference through a section view's base when needed."""
    configuration = str(view.ReferencedConfiguration)
    visited = set()
    while view is not None:
        name = str(view.GetUniqueName() or view.GetName2())
        if name in visited:
            raise RuntimeError(f"cycle in base views while resolving {name}")
        visited.add(name)
        raw_model = view.ReferencedDocument
        if raw_model:
            model = _early_bound(raw_model, "IModelDoc2")
            path = str(model.GetPathName())
            if not path:
                raise RuntimeError(f"{name}: referenced model has no saved path")
            if Path(path).suffix.upper() != ".SLDPRT":
                raise ValueError(
                    f"attachment probe supports part drawings only; {name} references {path}"
                )
            return {
                "path": str(Path(path).resolve(strict=True)),
                "configuration": configuration,
            }
        raw_parent = view.GetBaseView()
        view = _early_bound(raw_parent, "IView") if raw_parent is not None else None
    raise RuntimeError("drawing view has no resolved source model")


def dimension_api_observations(dimension, configuration):
    """Reproduce the bounded system-value call shapes without changing a model.

    On R2026x, an arbor-pedestal drawing reference RD1 returned None for the
    three GetSystemValue3 calls below, while GetSystemValue2 returned 0.012 m.
    Imported HeadHt was the positive control (0.003 m via GetSystemValue3).
    Untested: other releases, typed BSTR-array configuration names,
    swAllConfiguration, and the native IGet interface.
    """
    calls = {
        "GetSystemValue3(1,empty)": lambda: dimension.GetSystemValue3(1, ""),
        "GetSystemValue3(3,view_configuration)": lambda: dimension.GetSystemValue3(
            3, configuration
        ),
        "GetSystemValue3(1,None)": lambda: dimension.GetSystemValue3(1, None),
        "GetSystemValue2(empty)": lambda: dimension.GetSystemValue2(""),
    }
    result = {}
    for name, getter in calls.items():
        try:
            result[name] = {"status": "returned", "value": getter()}
        except Exception as error:
            result[name] = {"status": "error", "error": repr(error)}
    return result


def dimension_semantics(annotation, model, reference, *, observation="system"):
    """Read identity, configuration, SI value and source tolerance designation."""
    raw_display = annotation.GetSpecificAnnotation()
    if raw_display is None:
        return None, {"reason": "annotation has no concrete display dimension"}
    display = _early_bound(raw_display, "IDisplayDimension")
    display_type = int(display.Type2)
    is_reference = bool(display.IsReferenceDim())
    kind = "drawing_reference" if is_reference else "model_dimension"
    configuration = reference["configuration"]
    if not configuration:
        raise RuntimeError("dimension view has no referenced configuration")
    owner_path = Path(model.GetPathName()) if is_reference else Path(reference["path"])
    owner_suffix = f"@{owner_path.stem}.{'Drawing' if is_reference else 'Part'}"
    components, observations = [], []
    # swDimensionType_e.swChamferDimension has two underlying model dimensions.
    for index in range(2 if display_type == 10 else 1):
        raw_dimension = display.GetDimension2(index)
        if raw_dimension is None:
            raise RuntimeError(f"display dimension has no dimension at index {index}")
        dimension = _early_bound(raw_dimension, "IDimension")
        name, full_name = str(dimension.Name or ""), str(dimension.FullName or "")
        if not name or not full_name.casefold().endswith(owner_suffix.casefold()):
            raise RuntimeError(
                f"dimension identity does not match its {kind} owner: {full_name!r}"
            )
        # Only the verified current drawing owner is normalized across copies.
        # Model owners, feature names and dimension names remain exact.
        qualified_name = (
            full_name[: -len(owner_suffix)] + "@<drawing>"
            if is_reference
            else full_name
        )
        if is_reference:
            # Explicitly use the documented system-unit reference getter. The
            # current GetSystemValue3 shapes return None on the observed seat;
            # --dimension-values api-capture retains a reproducible comparison.
            value = dimension.GetSystemValue2("")
            value_api = "GetSystemValue2"
        else:
            values = tuple(dimension.GetSystemValue3(3, configuration) or ())
            if len(values) != 1:
                raise RuntimeError(
                    f"{full_name}: expected one system value for {configuration!r}: {values}"
                )
            value = values[0]
            value_api = "GetSystemValue3"
        if value is None or not math.isfinite(float(value)):
            raise RuntimeError(
                f"{full_name}: dimension system value is unreadable: {value}"
            )
        native_tolerance = dimension.Tolerance
        if native_tolerance is None:
            raise RuntimeError(f"{full_name}: dimension has no native tolerance")
        tolerance_type = int(_early_bound(native_tolerance, "IDimensionTolerance").Type)
        components.append(
            {
                "name": name,
                "qualified_name": qualified_name,
                "parameter_type": int(dimension.GetType()),
                "value_system": round(float(value), 12),
                "value_api": value_api,
                "tolerance_type": tolerance_type,
                "designation": "basic"
                if tolerance_type == 1
                else "other",  # swTolBASIC
            }
        )
        row = {"full_name": full_name}
        if observation == "api-capture":
            row["value_api_calls"] = dimension_api_observations(
                dimension, configuration
            )
        observations.append(row)
    return {
        "kind": kind,
        "display_type": display_type,
        "view_configuration": configuration,
        "components": components,
    }, observations


def datum_dimension_attachment(
    app, model, view, view_key, datum, display, reference, inventory
):
    """Prove a datum's native dimension link without inventing entity geometry."""
    if display is None:
        raise RuntimeError("dimension-attached datum has a null display dimension")
    if int(datum.OwnerType) != 0 or int(app.IsSame(datum.Owner, view)) != 1:
        raise RuntimeError("dimension-attached datum has the wrong native view owner")
    display = _early_bound(display, "IDisplayDimension")
    target = _early_bound(display.GetAnnotation(), "IAnnotation")
    if target is None or int(target.GetType()) != 4:
        raise RuntimeError("datum display dimension has no dimension annotation")
    if target.IsDangling() or int(target.Visible) != 1:
        raise RuntimeError("datum target dimension must be visible and non-dangling")
    if int(target.OwnerType) != 0 or int(app.IsSame(target.Owner, view)) != 1:
        raise RuntimeError("datum target dimension has the wrong native view owner")
    target_name = str(target.GetName())
    matches = [
        candidate
        for candidate in inventory
        if str(candidate.GetName()) == target_name and int(candidate.GetType()) == 4
    ]
    if len(matches) != 1 or int(app.IsSame(matches[0], target)) != 1:
        raise RuntimeError("datum target is not exactly one native view dimension")
    if int(app.IsSame(target.GetSpecificAnnotation(), display)) != 1:
        raise RuntimeError("datum target dimension failed its exact native roundtrip")
    semantic, _ = dimension_semantics(target, model, reference)
    if semantic is None or semantic["kind"] != "model_dimension":
        raise RuntimeError(
            "datum attachment currently requires a source model dimension"
        )
    source = _early_bound(view.ReferencedDocument, "IModelDoc2")
    if source is None or Path(source.GetPathName()).resolve(strict=True) != Path(
        reference["path"]
    ):
        raise RuntimeError("datum target has the wrong resolved source part")
    for index, component in enumerate(semantic["components"]):
        # IDimension.FullName includes dimension, feature and verified model.
        # IModelDoc2.Parameter takes the dimension@feature portion.
        local_name = component["qualified_name"].rsplit("@", 1)[0]
        if (
            not local_name.startswith(component["name"] + "@")
            or not local_name.split("@", 1)[1]
        ):
            raise RuntimeError("datum target lacks a complete source feature identity")
        native_parameter = source.Parameter(local_name)
        if (
            native_parameter is None
            or int(app.IsSame(native_parameter, display.GetDimension2(index))) != 1
        ):
            raise RuntimeError("datum target is not the exact source feature parameter")
    tag = _early_bound(datum.GetSpecificAnnotation(), "IDatumTag")
    return {
        "kind": "datum_to_model_display_dimension",
        "owner_view": view_key,
        "target_annotation": target_name,
        "source": dict(reference),
        "dimension": semantic,
        "datum": {
            "label": str(tag.GetLabel()),
            "shoulder": bool(tag.Shoulder),
            "display_style": int(tag.GetDisplayStyle()),
        },
    }


@_telemetry.traced("diagnostic.drawing_attachments.snapshot")
def snapshot(model, *, app, dimension_values="system"):
    checked, excluded, models = {}, {}, {}
    dimensions, dimensions_excluded, dimension_observations = {}, {}, {}
    semantic_attachments = {}
    for view_key, view in views(model).items():
        models[view_key] = referenced_model(view)
        inventory = tuple(
            _early_bound(raw, "IAnnotation") for raw in view.GetAnnotations() or ()
        )
        for annotation in inventory:
            annotation_kind = int(annotation.GetType())
            key = f"{view_key}/{annotation.GetName()}/{annotation_kind}"
            if key in checked or key in excluded or key in semantic_attachments:
                raise RuntimeError(f"duplicate annotation key: {key}")
            if annotation_kind not in _ANNOTATIONS:
                excluded[key] = {
                    "reason": "annotation type not checked",
                    "kind": annotation_kind,
                }
                continue
            # swSelNOTHING + NULL alone cannot distinguish an origin attachment
            # from lost geometry. IsDangling is the documented disambiguator.
            if annotation.IsDangling():
                raise RuntimeError(f"{key}: annotation is dangling")
            if annotation_kind == 4:
                semantic, observed = dimension_semantics(
                    annotation, model, models[view_key], observation=dimension_values
                )
                if semantic is None:
                    dimensions_excluded[key] = observed
                else:
                    dimensions[key] = semantic
                    dimension_observations[key] = observed
            entities = tuple(annotation.GetAttachedEntities3() or ())
            kinds = tuple(
                int(kind) for kind in annotation.GetAttachedEntityTypes() or ()
            )
            if len(entities) != len(kinds):
                raise RuntimeError(f"{key}: attachment arrays have different lengths")
            if annotation_kind == 2 and 14 in kinds:
                if kinds != (14,) or int(annotation.GetAttachedEntityCount3()) != 1:
                    raise RuntimeError(
                        f"{key}: datum needs exactly one complete dimension attachment"
                    )
                semantic_attachments[key] = datum_dimension_attachment(
                    app,
                    model,
                    view,
                    view_key,
                    annotation,
                    entities[0],
                    models[view_key],
                    inventory,
                )
                continue
            for entity, kind in zip(entities, kinds, strict=True):
                if entity is None and kind in _ENTITY_KINDS:
                    raise RuntimeError(f"{key}: supported attachment is null")
            if not entities:
                excluded[key] = {
                    "reason": "no model-geometry attachments",
                    "kinds": kinds,
                }
                continue
            if any(kind not in _ENTITY_KINDS for kind in kinds):
                excluded[key] = {
                    "reason": "attachment kind not checked",
                    "kinds": kinds,
                }
                continue
            try:
                checked[key] = tuple(
                    geometry(entity, kind)
                    for entity, kind in zip(entities, kinds, strict=True)
                )
            except UnsupportedGeometry as error:
                excluded[key] = {"reason": str(error), "kinds": kinds}
    return {
        "checked": checked,
        "excluded": excluded,
        "models": models,
        "dimensions": dimensions,
        "dimensions_excluded": dimensions_excluded,
        "dimension_observations": dimension_observations,
        "semantic_attachments": semantic_attachments,
    }


def compare(before, after, phase):
    differences = {}
    for section in (
        "checked",
        "excluded",
        "models",
        "dimensions",
        "dimensions_excluded",
        "semantic_attachments",
    ):
        differences[section] = sorted(
            key
            for key in before[section].keys() | after[section].keys()
            if before[section].get(key) != after[section].get(key)
        )
    if any(differences.values()):
        raise RuntimeError(f"{phase}: attachment snapshot changed: {differences}")


def layout(model):
    result = {}
    for key, view in views(model).items():
        position, scale = rounded(view.Position), float(view.ScaleDecimal)
        if len(position) != 2 or not math.isfinite(scale) or scale <= 0:
            raise RuntimeError(f"{key}: invalid view position or scale")
        result[key] = {"position": position, "scale": scale}
    return result


def check_layout(expected, actual, phase):
    if expected.keys() != actual.keys():
        raise RuntimeError(f"{phase}: drawing view inventory changed")
    for key, target in expected.items():
        measured = actual[key]
        pairs = [
            *zip(target["position"], measured["position"], strict=True),
            (target["scale"], measured["scale"]),
        ]
        if any(
            not math.isclose(a, b, rel_tol=0, abs_tol=_LAYOUT_TOLERANCE)
            for a, b in pairs
        ):
            raise RuntimeError(
                f"{phase}: {key} layout mismatch: {measured} != {target}"
            )


@_telemetry.traced("diagnostic.drawing_attachments.move_scale")
def move_and_scale(model):
    before = layout(model)
    if not before:
        raise RuntimeError("drawing has no views to move and scale")
    requested = {
        key: {
            "position": (row["position"][0] + 0.008, row["position"][1] - 0.006),
            "scale": row["scale"] * 0.75,
        }
        for key, row in before.items()
    }
    drawing_views = views(model)
    # Release all child alignments/scales before changing any parent's layout.
    for view in drawing_views.values():
        view.RemoveAlignment()
        view.PositionLocked = False
        view.UseSheetScale = 0
        view.UseParentScale = False
    for key, view in drawing_views.items():
        target = requested[key]
        view.ScaleDecimal = target["scale"]
        if not view.SetViewPosition(double_array(target["position"]), False):
            raise RuntimeError(
                f"{key}: SetViewPosition rejected the requested movement"
            )
    if not model.EditRebuild3():
        raise RuntimeError("drawing rebuild after layout changes failed")
    after = layout(model)
    check_layout(requested, after, "move and scale")
    return {"before": before, "requested": requested, "after": after}


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@asynccontextmanager
async def open_drawing(adapter, path):
    check(f"open {path.name}", await adapter.open_model(str(path)))
    try:
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        active_path = Path(model.GetPathName()).resolve(strict=True)
        if active_path != path.resolve(strict=True):
            raise RuntimeError(f"opened wrong drawing: {active_path} != {path}")
        yield model
    finally:
        check(f"close {path.name}", await adapter.close_model())


async def probe(adapter, source, report_root, *, dimension_values="system"):
    report_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="attachment-probe-", dir=report_root))
    copy = run_dir / f"{source.stem}-{run_dir.name}.SLDDRW"
    result_path = run_dir / "attachments.json"
    report = {
        "source": str(source),
        "copy": str(copy),
        "status": "running",
        "scope": "part drawings; separate model-geometry and dimension-semantic checks, not persistent entity IDs",
        "dimension_values": dimension_values,
        "snapshots": {},
    }

    def checkpoint():
        result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    _telemetry.info(f"drawing attachment probe report: {result_path}")
    try:
        source_digests = {str(source): file_digest(source)}
        async with open_drawing(adapter, source) as model:
            before = snapshot(
                model, app=adapter.swApp, dimension_values=dimension_values
            )
            report["snapshots"]["source"] = before
            report["coverage"] = {
                "geometry_annotations_checked": len(before["checked"]),
                "geometry_annotations_excluded": len(before["excluded"]),
                "dimension_annotations_checked": len(before["dimensions"]),
                "dimension_annotations_excluded": len(before["dimensions_excluded"]),
                "semantic_attachments_checked": len(before["semantic_attachments"]),
            }
            report["source_layout"] = layout(model)
            checkpoint()
        if (
            not before["checked"]
            and not before["dimensions"]
            and not before["semantic_attachments"]
        ):
            raise RuntimeError(
                "probe found no supported model-geometry attachments or dimension semantics"
            )
        for reference in before["models"].values():
            path = reference["path"]
            source_digests[path] = file_digest(path)
        report["source_digests"] = source_digests
        shutil.copy2(source, copy)
        async with open_drawing(adapter, copy) as model:
            report["snapshots"]["copy"] = snapshot(
                model, app=adapter.swApp, dimension_values=dimension_values
            )
            compare(before, report["snapshots"]["copy"], "untouched drawing copy")
            check_layout(
                report["source_layout"], layout(model), "untouched drawing copy"
            )
            checkpoint()
            report["layout"] = move_and_scale(model)
            report["snapshots"]["moved_scaled"] = snapshot(
                model, app=adapter.swApp, dimension_values=dimension_values
            )
            compare(before, report["snapshots"]["moved_scaled"], "move and scale")
            checkpoint()
            with _telemetry.span("diagnostic.drawing_attachments.save"):
                saved = model.Save3(1, 0, 0)  # swSaveAsOptions_Silent
                if not (saved[0] if isinstance(saved, tuple) else saved):
                    raise RuntimeError(f"saving drawing copy failed: {saved!r}")
        async with open_drawing(adapter, copy) as model:
            report["snapshots"]["reopened"] = snapshot(
                model, app=adapter.swApp, dimension_values=dimension_values
            )
            compare(before, report["snapshots"]["reopened"], "saved and reopened")
            report["reopened_layout"] = layout(model)
            check_layout(
                report["layout"]["requested"],
                report["reopened_layout"],
                "saved and reopened",
            )
        for path, digest in source_digests.items():
            if file_digest(path) != digest:
                raise RuntimeError(f"probe changed a source document on disk: {path}")
        report["status"] = "passed"
        checkpoint()
    except Exception as error:
        report.update(status="failed", error=str(error))
        checkpoint()
        raise
    _telemetry.success(
        f"{len(before['checked'])} annotations have unchanged supported attachment geometry; "
        f"{len(before['excluded'])} geometry exclusions; "
        f"{len(before['dimensions'])} dimension annotations have unchanged identity/configuration/value; "
        f"{len(before['semantic_attachments'])} dimension-attached datums have unchanged semantic targets; "
        f"{len(before['dimensions_excluded'])} dimension exclusions (see report reasons)"
    )
    return {"probe": str(result_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "drawing", type=Path, help="native drawing referencing only .SLDPRT models"
    )
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/drawing-attachments"
    )
    parser.add_argument(
        "--dimension-values",
        choices=("system", "api-capture"),
        default="system",
        help="also record dimension getter call shapes with api-capture",
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    source = args.drawing.resolve(strict=True)
    if source.suffix.upper() != ".SLDDRW":
        raise ValueError("probe input must be a native drawing")
    report_root = args.report_root.resolve()
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--report-root",
                str(report_root),
                "--dimension-values",
                args.dimension_values,
                "--worker",
            ],
            "drawing attachment stability probe",
            log_stem="drawing-attachment-probe",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError(
            "attachment probe worker requires the pipeline COM seat lock"
        )
    return run_build(
        lambda adapter: probe(
            adapter, source, report_root, dimension_values=args.dimension_values
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

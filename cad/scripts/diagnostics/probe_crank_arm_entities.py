"""Crank-arm-only native evidence, using the shared attach-only owned runner."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from crank_arm_spec import DRAWING_DIMENSIONS  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics._source_dimension_snapshot import dimension_snapshot  # noqa: E402
from diagnostics.probe_source_basic_dimensions import part_dimensions  # noqa: E402
import _telemetry  # noqa: E402

SOURCE = ROOT / "cad/out/sldprt/crank-arm.SLDPRT"
TOKEN = SOURCE.with_name(".crank-arm.execution")
EXPECTED_SOURCE_SHA = "6b086d5dbcb6e904fb794822728b705f69cd3903a0e8b2c5cf7abb8d9621f102"
BASELINE = "bc593d784fba08fc6552224767a460338f51b664"
BASELINE_DRAWING_REPORT = (
    ROOT / "cad/out/reports/crank-arm-entities-6x1gg817/measurements.json"
)
BASELINE_DRAWING_REPORT_SHA = (
    "e24efe0444d38f0cfcdafb3eb9413623807d28f36d700256ca0ef0fae71b2c06"
)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_default(value):
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"unsupported evidence type: {type(value)}")


def persist_report(path, report):
    primary = sys.exception()
    try:
        path.write_text(
            json.dumps(report, indent=2, default=json_default), encoding="utf-8"
        )
    except Exception as error:
        if primary is not None and primary is not error:
            raise ExceptionGroup(
                "native operation and report failures", [primary, error]
            ) from None
        raise


def revision(directory):
    return subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True
    ).strip()


def provenance():
    import solidworks_mcp.adapters.pywin32_adapter as native
    import draw_crank_arm as recipe

    source_hash = sha(SOURCE)
    token = TOKEN.read_text(encoding="utf-8").strip()
    if source_hash != token or source_hash != EXPECTED_SOURCE_SHA:
        raise RuntimeError("source SHA differs from its original execution token")
    return {
        "root_commit": revision(ROOT),
        "adapter_commit": revision(ROOT / "SolidworksMCP-python"),
        "python": sys.executable,
        "recipe_import": recipe.__file__,
        "adapter_import": native.__file__,
        "host": platform.node(),
        "platform": platform.platform(),
        "source": str(SOURCE),
        "source_sha256": source_hash,
        "execution_token": token,
        "source_size": SOURCE.stat().st_size,
    }


@_telemetry.traced("diagnostic.crank_arm.source_snapshot")
def source_snapshot(adapter, path):
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if (
        int(model.GetType()) != 1
        or Path(model.GetPathName()).resolve() != path.resolve()
        or int(
            adapter.swApp.IsSame(adapter.swApp.GetOpenDocumentByName(str(path)), model)
        )
        != 1
    ):
        raise RuntimeError("crank-arm snapshot has the wrong exact source owner")
    before = bool(model.GetSaveFlag())
    raw, _ = dimension_snapshot(adapter.swApp, model, path, required=DRAWING_DIMENSIONS)
    required, _ = part_dimensions(
        adapter, path, raw["configuration"], targets=DRAWING_DIMENSIONS
    )
    return {
        "dirty_before": before,
        "dirty_after": bool(model.GetSaveFlag()),
        "required_dimensions": required,
        "observed_dimensions": raw,
    }


async def capture_source(adapter, directory):
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    report = {"status": "running", "provenance": provenance()}
    report_path = directory / "measurements.json"
    try:
        report["session"] = {
            "pid": int(adapter.swApp.GetProcessID()),
            "revision": str(adapter.swApp.RevisionNumber()),
            "inventory": adapter.ownership.evidence(),
        }
        check("open crank-arm for readback", await adapter.open_model(str(SOURCE)))
        report["source_snapshot"] = source_snapshot(adapter, SOURCE)
        report["status"] = "captured"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        primary = sys.exception()
        errors = []
        for field, read, expected in (
            (
                "source_sha256_after",
                lambda: sha(SOURCE),
                report["provenance"]["source_sha256"],
            ),
            (
                "execution_token_after",
                lambda: TOKEN.read_text(encoding="utf-8").strip(),
                report["provenance"]["execution_token"],
            ),
        ):
            try:
                report[field] = read()
                if report[field] != expected:
                    raise RuntimeError(
                        f"crank-arm source or original token changed: {field}"
                    )
            except Exception as error:
                report[field] = {"error": repr(error)}
                errors.append(error)
        if errors:
            report.update(
                status="failed", final_errors=[repr(error) for error in errors]
            )
        try:
            persist_report(report_path, report)
        except Exception as error:
            errors.append(error)
        _telemetry.info(f"crank-arm evidence: {report_path}")
        if errors:
            raise ExceptionGroup(
                "source snapshot/final evidence failures",
                ([primary] if primary else []) + errors,
            ) from None
    return {"report": str(report_path)}


async def capture_drawing(adapter, directory):
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics.probe_datum_shoulder import all_annotation_layout
    import draw_crank_arm as recipe

    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    adapter.ownership.register_source(recipe.OUTPUTS.slddrw)
    copy = directory / f"{directory.name}.SLDDRW"
    shutil.copy2(recipe.OUTPUTS.slddrw, copy)
    report = {"status": "running", "provenance": provenance()}
    try:
        async with attachments.open_drawing(adapter, copy) as model:
            report["attachments"] = attachments.snapshot(model, app=adapter.swApp)
            report["annotations"], _ = all_annotation_layout(adapter)
            report["layout"] = attachments.layout(model)
            source_model = _early_bound(
                adapter.swApp.GetOpenDocumentByName(str(SOURCE)), "IModelDoc2"
            )
            report["source_snapshot"] = source_snapshot(
                SimpleNamespace(currentModel=source_model, swApp=adapter.swApp), SOURCE
            )
        report["status"] = "captured"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        persist_report(directory / "measurements.json", report)
    return {"report": str(directory / "measurements.json")}


def positive_roles():
    from _drawing_entities import CircleEdge, FaceBoundary, FeatureFace, LineEdge
    from _gtol_spec import CylinderFace, PlanarFace
    from crank_arm_spec import (
        ARM_C2C,
        ARM_END_X,
        ARM_THICKNESS,
        HALF_WIDTH,
        PIN_HOLE_DIA,
        SHAFT_BORE_DIA,
    )

    end = FeatureFace("Arm", PlanarFace((1, 0, 0), ARM_END_X))
    return {
        "shaft": FaceBoundary(
            FeatureFace("ShaftBore", CylinderFace(SHAFT_BORE_DIA)),
            CircleEdge(SHAFT_BORE_DIA / 2, (0, 0, ARM_THICKNESS), (0, 0, 1)),
        ),
        "pivot": FaceBoundary(
            FeatureFace("PivotBore", CylinderFace(15 / 64 * 25.4)),
            CircleEdge(15 / 64 * 25.4 / 2, (ARM_C2C, 0, ARM_THICKNESS), (0, 0, 1)),
        ),
        "pin": FaceBoundary(
            FeatureFace("Arm", PlanarFace((0, 1, 0), HALF_WIDTH)),
            CircleEdge(PIN_HOLE_DIA / 2, (0, HALF_WIDTH, ARM_THICKNESS / 2), (0, 1, 0)),
        ),
        "width_lo": FaceBoundary(
            end, LineEdge((ARM_END_X, -HALF_WIDTH, ARM_THICKNESS / 2), (0, 0, 1))
        ),
        "width_hi": FaceBoundary(
            end, LineEdge((ARM_END_X, HALF_WIDTH, ARM_THICKNESS / 2), (0, 0, 1))
        ),
    }


def require_attachment(adapter, annotation, view, entities, label):
    """Read exact source identities for all attached edges, including dimensions."""
    from _drawing_common import _drawing_entity_in_source

    annotation = _early_bound(annotation, "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(annotation.GetAttachedEntityTypes() or ())
    if (
        int(annotation.GetAttachedEntityCount3()) != len(entities)
        or len(attached) != len(entities)
        or kinds != (1,) * len(entities)
        or int(annotation.OwnerType) != 0
        or int(adapter.swApp.IsSame(annotation.Owner, view)) != 1
        or annotation.IsDangling()
    ):
        raise RuntimeError(f"{label}: attachment count/type/view/dangling mismatch")
    for actual, expected in zip(attached, entities, strict=True):
        source = _drawing_entity_in_source(
            view, actual, entity_type="EDGE", label=label
        )
        if int(adapter.swApp.IsSame(source, expected)) != 1:
            raise RuntimeError(f"{label}: attached source entity changed")
    return {
        "name": str(annotation.GetName()),
        "view": str(view.GetName2()),
        "attachment_types": kinds,
    }


async def positive_control(adapter, directory):
    from diagnostics import benchmark_drawing_recipes as benchmark
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics._owned_native_documents import DocumentKind, save_drawing
    from diagnostics._recipe_template_factory import (
        DrawingFactory,
        RecipeTemplateFactory,
    )
    from diagnostics.probe_datum_shoulder import all_annotation_layout
    from _drawing_entities import ModelEntities
    import _drawing_common as drawing

    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    report = {"status": "running", "provenance": provenance(), "observations": []}
    report_path = directory / "measurements.json"

    def checkpoint():
        persist_report(report_path, report)

    source = directory / f"{directory.name}-part.SLDPRT"
    shutil.copy2(SOURCE, source)
    module = benchmark.load_recipe(BASELINE, "crank_arm", directory, source=source)
    controller = RecipeTemplateFactory(DrawingFactory.PREPARED)
    checkpoint()
    try:
        factory = await controller.configure(adapter, module, report, directory)
        check(
            "open positive-control source copy", await adapter.open_model(str(source))
        )
        adapter.ownership.assert_current_owned()
        source_model = adapter.currentModel
        report["source_before"] = source_snapshot(adapter, source)
        roles = positive_roles()
        report["requests"] = {name: repr(value) for name, value in roles.items()}
        started = time.perf_counter()
        bank = ModelEntities(source_model).resolve(roles)
        report["resolver_seconds"] = time.perf_counter() - started
        report["resolved"] = {
            name: attachments.geometry(entity, 1) for name, entity in bank.items()
        }
        checkpoint()
        originals = {
            name: getattr(module, name)
            for name in (
                "add_edge_dimension",
                "add_datum_feature",
                "add_native_hole_callout",
            )
        }

        def insert(name, actual_adapter, view, **kwargs):
            label = kwargs["label"]
            selected = {
                "arm-width overall": ("width_lo", "width_hi"),
                "crank shaft axis": ("shaft",),
                "crank-arm cross-hole": ("pin",),
                "handle pivot hole": ("pivot",),
            }.get(label)
            if selected is None:
                return originals[name](actual_adapter, view, **kwargs)
            adapter.ownership.assert_current_owned()
            if (
                actual_adapter is not adapter
                or int(adapter.swApp.IsSame(view.ReferencedDocument, source_model)) != 1
            ):
                raise RuntimeError("positive control has the wrong adapter/source view")
            entities = tuple(bank[role] for role in selected)
            row = {"label": label, "roles": selected, "status": "inserting"}
            report["observations"].append(row)
            checkpoint()
            adapter.currentModel.ClearSelection2(True)
            row["selection_witnesses"] = []
            manager = _early_bound(
                adapter.currentModel.SelectionManager, "ISelectionMgr"
            )
            for index, entity in enumerate(entities):
                adapter.ownership.assert_current_owned()
                selected_ok = bool(view.SelectEntity(entity, index > 0))
                count = int(manager.GetSelectedObjectCount2(-1))
                selected_entity = manager.GetSelectedObject6(index + 1, -1)
                owner = manager.GetSelectedObjectsDrawingView2(index + 1, -1)
                mapped = drawing._drawing_entity_in_source(
                    view, selected_entity, entity_type="EDGE", label=label
                )
                witness = {
                    "return": selected_ok,
                    "count": count,
                    "source_identity": int(adapter.swApp.IsSame(mapped, entity)),
                    "view_identity": int(adapter.swApp.IsSame(owner, view)),
                }
                row["selection_witnesses"].append(witness)
                checkpoint()
                if (
                    not selected_ok
                    or count != index + 1
                    or witness["source_identity"] != 1
                    or witness["view_identity"] != 1
                ):
                    raise RuntimeError(f"{label}: native selection witness failed")
            if name == "add_edge_dimension":
                for key in ("p0", "p1"):
                    kwargs.pop(key)
                result = drawing.add_entity_dimension(
                    adapter, view, entities=entities, **kwargs
                )
            else:
                kwargs.pop("edge_xy")
                if name == "add_datum_feature":
                    kwargs.pop("symbol_xy")
                    kwargs.pop("position_tolerance_m")
                kwargs["edge" if name == "add_native_hole_callout" else "entity"] = (
                    entities[0]
                )
                result = originals[name](adapter, view, **kwargs)
            result = _early_bound(
                result,
                "IDatumTag" if name == "add_datum_feature" else "IDisplayDimension",
            )
            row["attachment"] = require_attachment(
                adapter, result.GetAnnotation(), view, entities, label
            )
            row["status"] = "passed"
            checkpoint()
            return result

        started = time.perf_counter()
        with ExitStack() as stack:
            stack.enter_context(
                adapter.ownership.creating_document(
                    DocumentKind.DRAWING, module.OUTPUTS.slddrw
                )
            )
            stack.enter_context(patch("_drawing_common.save_drawing", save_drawing))
            for name in originals:
                stack.enter_context(
                    patch.object(
                        module,
                        name,
                        lambda a, v, _name=name, **kw: insert(_name, a, v, **kw),
                    )
                )
            report["artifacts"] = await module.build(adapter, drawing_factory=factory)
        report["recipe_seconds"] = time.perf_counter() - started
        controller.require_used()
        if len(report["observations"]) != 4:
            raise RuntimeError(
                "positive control did not exercise all four required call sites"
            )
        report["attachments"] = attachments.snapshot(
            adapter.currentModel, app=adapter.swApp
        )
        report["annotations"], _ = all_annotation_layout(adapter)
        report["source_after"] = source_snapshot(
            SimpleNamespace(currentModel=source_model, swApp=adapter.swApp), source
        )
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        try:
            adapter.ownership.assert_current_owned()
            if int(adapter.currentModel.GetType()) == 3:
                report["partial_annotations"], _ = all_annotation_layout(adapter)
                report["partial_attachments"] = attachments.snapshot(
                    adapter.currentModel, app=adapter.swApp
                )
        except Exception as snapshot_error:
            report["partial_snapshot_error"] = repr(snapshot_error)
        raise
    finally:
        primary = sys.exception()
        errors = []
        for field, action in (
            ("template_guards", lambda: _require_template_guards(controller)),
            ("source_copy_sha256_after", lambda: _require_hash(source)),
            ("source_original_sha256_after", lambda: _require_hash(SOURCE)),
            ("execution_token_after", _require_token),
        ):
            try:
                report[field] = action()
            except Exception as error:
                report[field] = {"error": repr(error)}
                errors.append(error)
        report["template_guard_details"] = controller.guards
        if errors:
            report.update(
                status="failed", final_errors=[repr(error) for error in errors]
            )
        try:
            checkpoint()
        except Exception as error:
            errors.append(error)
        if errors:
            raise ExceptionGroup(
                "positive control/final evidence failures",
                ([primary] if primary else []) + errors,
            ) from None
    return {"report": str(report_path)}


CALLOUT_ROLES = {
    "arm-width overall": ("width_lo", "width_hi"),
    "shaft-to-handle-pivot location": ("shaft", "pivot"),
    "handle-pivot transverse location": ("side_c", "pivot"),
    "dimple transverse location from datum C": ("side_c", "dimple"),
    "cross-hole station from datum A": ("station_a", "pin"),
    "cross-hole true position": ("pin",),
    "crank-arm cross-hole": ("pin",),
    "crank broad face": ("datum_a",),
    "crank shaft axis": ("shaft",),
    "crank width side": ("side_c",),
    "handle pivot position": ("pivot",),
    "handle pivot hole": ("pivot",),
    "crank broad-face parallelism": ("opposite_a",),
    "shaft bore finish": ("shaft",),
}


def drawing_dimensions(model):
    """Raw drawing values and presentation, supplementing the shared SI snapshot."""
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics._source_dimension_snapshot import display_presentation, finite

    rows = {}
    for view in attachments.views(model).values():
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) != 4:
                continue
            display = _early_bound(
                annotation.GetSpecificAnnotation(), "IDisplayDimension"
            )
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            configuration = str(view.ReferencedConfiguration)
            value = (
                dimension.GetSystemValue2("")
                if display.IsReferenceDim()
                else tuple(dimension.GetSystemValue3(3, configuration))[0]
            )
            key = f"{view.GetName2()}/{annotation.GetName()}"
            if key in rows:
                raise RuntimeError(f"duplicate drawing dimension identity: {key}")
            rows[key] = {
                "name": str(dimension.FullName),
                "value_system": finite(value),
                "tolerance_type": int(tolerance.Type),
                "tolerance_min": finite(tolerance.GetMinValue()),
                "tolerance_max": finite(tolerance.GetMaxValue()),
                "primary_precision": int(display.GetPrimaryPrecision2()),
                "tolerance_precision": int(display.GetPrimaryTolPrecision2()),
                "arc_conditions": tuple(
                    int(dimension.GetArcEndCondition(index)) for index in (1, 2)
                ),
                "hole_callout": bool(display.IsHoleCallout()),
                **display_presentation(display),
            }
    return rows


def require_source_unchanged(before, after):
    from diagnostics._source_dimension_snapshot import compare_source

    changes = compare_source(
        before["observed_dimensions"], after["observed_dimensions"]
    )
    if changes or before["required_dimensions"] != after["required_dimensions"]:
        raise RuntimeError(
            "crank-arm source presentation or required dimensions changed"
        )
    if after["dirty_before"] or after["dirty_after"]:
        raise RuntimeError("crank-arm source became dirty")


def require_manufacturing(row, recorded):
    """Pin the five added SI measurements and their native BASIC/arc meanings."""
    if sha(BASELINE_DRAWING_REPORT) != BASELINE_DRAWING_REPORT_SHA:
        raise RuntimeError("crank-arm native baseline receipt changed")
    baseline = json.loads(BASELINE_DRAWING_REPORT.read_text(encoding="utf-8"))
    if (
        baseline["status"] != "captured"
        or baseline["provenance"]["source_sha256"] != EXPECTED_SOURCE_SHA
    ):
        raise RuntimeError("crank-arm native baseline has the wrong source")
    required = {
        "arm-width overall": (0.016, 0, (0, 0)),
        "shaft-to-handle-pivot location": (0.075, 1, (1, 1)),
        "handle-pivot transverse location": (0.008, 1, (0, 1)),
        "dimple transverse location from datum C": (0.008, 0, (0, 1)),
        "cross-hole station from datum A": (0.004, 1, (0, 1)),
    }
    for label, (nominal, basic, arcs) in required.items():
        key = "/".join(recorded[label])
        dimension = row["dimensions"][key]
        native_baseline = baseline["attachments"]["dimensions"][f"Sheet1/{key}/4"][
            "components"
        ][0]
        # Same 12-place SI readback boundary as the shared attachment snapshot;
        # raw values are additionally retained and compared exactly across saves.
        if (
            round(dimension["value_system"], 12) != native_baseline["value_system"]
            or (dimension["tolerance_type"] == 1) != (basic == 1)
            or dimension["arc_conditions"] != arcs
            or not dimension["show_dimension_value"]
        ):
            raise RuntimeError(
                f"{label} (nominal {nominal} m): native measurement/BASIC/arc meaning changed: {dimension}"
            )
    for label in ("crank-arm cross-hole", "handle pivot hole"):
        key = "/".join(recorded[label])
        if not row["dimensions"][key]["hole_callout"]:
            raise RuntimeError(f"{label}: not a native Hole Wizard callout")
        if not row["annotations"][key]["semantic"]["texts"]:
            raise RuntimeError(f"{label}: missing actual displayed hole text")
    expected = {
        f"{name}@{feature}"
        for feature, names in DRAWING_DIMENSIONS.items()
        for name in names
    }
    marked = {
        value["name"].rsplit("@", 1)[0]
        for value in row["dimensions"].values()
        if value["name"].endswith(".Part")
        and value["name"].rsplit("@", 1)[0] in expected
    }
    if marked != expected or row["sheet"][2:4] != (2.0, 1.0):
        raise RuntimeError("marked dimension union or sheet scale changed")


def save_moved_drawing(adapter, path):
    """Save an already-open owned copy in place, as the shared attachment probe does."""
    adapter.ownership.assert_current_owned()
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if (
        int(model.GetType()) != 3
        or Path(model.GetPathName()).resolve() != path.resolve()
    ):
        raise RuntimeError("moved save requires the exact owned drawing")
    with _telemetry.span("diagnostic.crank_arm.save_moved"):
        result = model.Save3(1, 0, 0)
    if not (result[0] if isinstance(result, tuple) else result):
        raise RuntimeError(f"moved drawing Save3 failed: {result!r}")
    if isinstance(result, tuple) and result[1] != 0:
        raise RuntimeError(f"moved drawing Save3 returned errors: {result!r}")
    return result


def render_details(pdf, prefix):
    """Rasterize native vector-PDF detail windows, without altering any geometry."""
    import pypdfium2 as pdfium

    windows = {
        "shaft-finish": (0.012, 0.108, 0.094, 0.184),
        "front-dimensions": (0.065, 0.074, 0.277, 0.180),
        "stock-datums": (0.267, 0.090, 0.375, 0.165),
        "cross-hole": (0.033, 0.181, 0.196, 0.240),
        "title": (0.260, 0.012, 0.420, 0.073),
        "notes": (0.012, 0.024, 0.262, 0.063),
    }
    paths = {}
    with pdfium.PdfDocument(str(pdf)) as document:
        if len(document) != 1:
            raise RuntimeError("crank-arm detail rendering requires one native sheet")
        page = document[0]
        width, height = page.get_size()
        points_per_metre = 72 / 0.0254
        for label, (left, bottom, right, top) in windows.items():
            target = prefix.with_name(f"{prefix.name}-{label}.png")
            if target.exists():
                raise RuntimeError(f"detail target already exists: {target}")
            crop = (
                left * points_per_metre,
                bottom * points_per_metre,
                width - right * points_per_metre,
                height - top * points_per_metre,
            )
            bitmap = page.render(scale=600 / 72, crop=crop)
            bitmap.to_pil().save(target, dpi=(600, 600))
            bitmap.close()
            paths[label] = {"path": str(target), "sha256": sha(target)}
        page.close()
    return paths


async def candidate_control(adapter, directory):
    """Execute the committed recipe, then inspect fresh cold and relocated handles."""
    from diagnostics import benchmark_drawing_recipes as benchmark
    from diagnostics import probe_drawing_attachments as attachments
    from diagnostics._owned_native_documents import DocumentKind, save_drawing
    from diagnostics._recipe_template_factory import (
        DrawingFactory,
        RecipeTemplateFactory,
    )
    from diagnostics._reopen_annotation_comparison import compare_reopened_annotations
    from diagnostics.probe_datum_shoulder import all_annotation_layout
    from diagnostics.probe_retained_drawing_export import export_pdf_only
    from _drawing_entities import ModelEntities
    import _drawing_common as drawing

    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(SOURCE)
    source = directory / f"{directory.name}-part.SLDPRT"
    report = {
        "status": "running",
        "provenance": provenance(),
        "observations": [],
        "phases": {},
    }
    report_path = directory / "measurements.json"
    controller = RecipeTemplateFactory(DrawingFactory.PREPARED)

    def checkpoint():
        persist_report(report_path, report)

    recorded = {}
    try:
        shutil.copy2(SOURCE, source)
        module = benchmark.load_recipe(
            revision(ROOT), "crank_arm", directory, source=source
        )
        report["recipe_sha256"] = sha(directory / "recipe-source.py")
        factory = await controller.configure(adapter, module, report, directory)
        check("open candidate source copy", await adapter.open_model(str(source)))
        source_model = module.require_source(adapter, adapter.currentModel)
        report["source_before"] = source_snapshot(adapter, source)
        requests = dict(module.ENTITY_ROLES)
        requests.update(
            {
                f"face:{role}": selector.face
                for role, selector in module.ENTITY_ROLES.items()
            }
        )

        def resolve(model):
            module.require_source(adapter, model)
            bank = ModelEntities(model).resolve(requests)
            geometry = {
                name: attachments.geometry(entity, 2 if name.startswith("face:") else 1)
                for name, entity in bank.items()
            }
            return bank, geometry

        bank, report["entities_before"] = resolve(source_model)
        checkpoint()
        originals = {
            name: getattr(module, name)
            for name in (
                "add_entity_dimension",
                "add_datum_feature",
                "add_feature_control_frame",
                "add_native_hole_callout",
                "add_surface_finish",
            )
        }
        types = {
            "add_entity_dimension": "IDisplayDimension",
            "add_datum_feature": "IDatumTag",
            "add_feature_control_frame": "IGtol",
            "add_native_hole_callout": "IDisplayDimension",
            "add_surface_finish": "ISFSymbol",
        }

        def insert(name, actual_adapter, view, **kwargs):
            adapter.ownership.assert_current_owned()
            module.require_source(adapter, source_model)
            label = kwargs["label"]
            roles = CALLOUT_ROLES[label]
            expected = tuple(bank[role] for role in roles)
            supplied = kwargs.get("entities") or (
                kwargs.get("entity") or kwargs.get("edge"),
            )
            if (
                actual_adapter is not adapter
                or label in recorded
                or len(supplied) != len(expected)
            ):
                raise RuntimeError(
                    f"{label}: wrong adapter, duplicate or missing entity argument"
                )
            if (
                int(adapter.swApp.IsSame(view.ReferencedDocument, source_model)) != 1
                or str(view.ReferencedConfiguration) != "Default"
                or any(
                    int(adapter.swApp.IsSame(a, b)) != 1
                    for a, b in zip(supplied, expected, strict=True)
                )
            ):
                raise RuntimeError(f"{label}: wrong exact source/view/entity arguments")
            row = {
                "label": label,
                "roles": roles,
                "status": "inserting",
                "selection_witnesses": [],
            }
            report["observations"].append(row)
            checkpoint()
            # Read the native selected object/view, not just SelectEntity's return.
            # These pre-insertion witnesses do not replace the actual helper's
            # own selection, insertion, attachment or final layout validators.
            adapter.currentModel.ClearSelection2(True)
            manager = _early_bound(
                adapter.currentModel.SelectionManager, "ISelectionMgr"
            )
            for index, entity in enumerate(supplied):
                adapter.ownership.assert_current_owned()
                ok = bool(view.SelectEntity(entity, index > 0))
                actual = manager.GetSelectedObject6(index + 1, -1)
                mapped = drawing._drawing_entity_in_source(
                    view, actual, entity_type="EDGE", label=label
                )
                witness = {
                    "return": ok,
                    "count": int(manager.GetSelectedObjectCount2(-1)),
                    "source_identity": int(adapter.swApp.IsSame(mapped, entity)),
                    "view_identity": int(
                        adapter.swApp.IsSame(
                            manager.GetSelectedObjectsDrawingView2(index + 1, -1), view
                        )
                    ),
                }
                row["selection_witnesses"].append(witness)
                checkpoint()
                if (
                    not ok
                    or witness["count"] != index + 1
                    or witness["source_identity"] != 1
                    or witness["view_identity"] != 1
                ):
                    raise RuntimeError(f"{label}: native selection witness failed")
            result = _early_bound(
                originals[name](actual_adapter, view, **kwargs), types[name]
            )
            annotation = _early_bound(result.GetAnnotation(), "IAnnotation")
            row["attachment"] = require_attachment(
                adapter, annotation, view, expected, label
            )
            recorded[label] = (str(view.GetName2()), str(annotation.GetName()))
            row["status"] = "passed"
            checkpoint()
            return result

        started = time.perf_counter()
        with ExitStack() as stack:
            stack.enter_context(
                adapter.ownership.creating_document(
                    DocumentKind.DRAWING, module.OUTPUTS.slddrw
                )
            )
            stack.enter_context(patch("_drawing_common.save_drawing", save_drawing))
            for name in originals:
                stack.enter_context(
                    patch.object(
                        module,
                        name,
                        lambda a, v, _name=name, **kw: insert(_name, a, v, **kw),
                    )
                )
            report["artifacts"] = await module.build(adapter, drawing_factory=factory)
        report["instrumented_recipe_seconds"] = time.perf_counter() - started
        controller.require_used()
        if recorded.keys() != CALLOUT_ROLES.keys():
            raise RuntimeError(
                "candidate did not exercise all fourteen annotations / fifteen former pick sites"
            )

        def scene(phase, source_handle, expected_bank):
            adapter.ownership.assert_current_owned()
            module.require_source(adapter, source_handle)
            current = _early_bound(adapter.currentModel, "IModelDoc2")
            if (
                int(current.GetType()) != 3
                or Path(current.GetPathName()).resolve()
                != module.OUTPUTS.slddrw.resolve()
            ):
                raise RuntimeError("candidate scene is not its exact owned drawing")
            row = {}
            report["phases"][phase] = row
            row["attachments"] = attachments.snapshot(current, app=adapter.swApp)
            row["annotations"], _ = all_annotation_layout(adapter)
            row["dimensions"] = drawing_dimensions(current)
            row["layout"] = attachments.layout(current)
            row["sheet"] = tuple(
                _early_bound(
                    _early_bound(current, "IDrawingDoc").GetCurrentSheet(), "ISheet"
                ).GetProperties2()
            )
            row["source"] = source_snapshot(
                SimpleNamespace(currentModel=source_handle, swApp=adapter.swApp), source
            )
            inventory = {}
            for view in attachments.views(current).values():
                if (
                    int(adapter.swApp.IsSame(view.ReferencedDocument, source_handle))
                    != 1
                    or str(view.ReferencedConfiguration) != "Default"
                ):
                    raise RuntimeError(
                        "candidate scene has the wrong view source/configuration"
                    )
                for raw in view.GetAnnotations() or ():
                    annotation = _early_bound(raw, "IAnnotation")
                    key = (str(view.GetName2()), str(annotation.GetName()))
                    if key in inventory:
                        raise RuntimeError(
                            "candidate annotation inventory is ambiguous"
                        )
                    inventory[key] = (annotation, view)
            row["explicit_roles"] = {}
            for label, key in recorded.items():
                annotation, view = inventory[key]
                row["explicit_roles"][label] = require_attachment(
                    adapter,
                    annotation,
                    view,
                    tuple(expected_bank[role] for role in CALLOUT_ROLES[label]),
                    label,
                )
            checkpoint()
            require_source_unchanged(report["source_before"], row["source"])
            require_manufacturing(row, recorded)
            if row["attachments"]["dimensions_excluded"]:
                raise RuntimeError("candidate has unsupported dimension semantics")
            return row

        def compare(before, after, phase):
            attachments.compare(before["attachments"], after["attachments"], phase)
            if (
                before["dimensions"] != after["dimensions"]
                or before["sheet"] != after["sheet"]
                or before["explicit_roles"] != after["explicit_roles"]
            ):
                raise RuntimeError(
                    f"{phase}: raw dimensions, sheet or explicit roles changed"
                )

        built = scene("built", source_model, bank)
        shutil.copy2(module.OUTPUTS.slddrw, directory / "built.SLDDRW")
        report["built_details"] = render_details(
            module.OUTPUTS.pdf, directory / "built"
        )
        await adapter.close_owned_documents()
        bank = source_model = None  # never reuse closed native handles
        check("cold-open owned source", await adapter.open_model(str(source)))
        source_model = module.require_source(adapter, adapter.currentModel)
        bank, report["entities_reopened"] = resolve(source_model)
        if report["entities_before"] != report["entities_reopened"]:
            raise RuntimeError("cold source role geometry changed")
        check(
            "cold-open owned drawing",
            await adapter.open_model(str(module.OUTPUTS.slddrw)),
        )
        reopened = scene("reopened", source_model, bank)
        # Retain a fresh cold print even if the subsequent exact comparison fails.
        export_pdf_only(adapter, directory / "cold.pdf")
        drawing.render_pdf_png(directory / "cold.pdf", directory / "cold.png")
        report["cold_details"] = render_details(
            directory / "cold.pdf", directory / "cold"
        )
        compare(built, reopened, "cold reopen")
        attachments.check_layout(built["layout"], reopened["layout"], "cold reopen")
        report["cold_annotations"] = compare_reopened_annotations(
            built["annotations"], reopened["annotations"]
        )
        checkpoint()
        if report["cold_annotations"]["status"] != "passed":
            raise RuntimeError("cold reopen annotation contents/layout changed")
        adapter.ownership.assert_current_owned()
        report["movement"] = attachments.move_and_scale(adapter.currentModel)
        moved = scene("moved_scaled", source_model, bank)
        compare(reopened, moved, "view movement and scale")
        adapter.ownership.assert_current_owned()
        report["moved_save"] = save_moved_drawing(adapter, module.OUTPUTS.slddrw)
        await adapter.close_owned_documents()
        bank = source_model = None
        check("reopen moved source", await adapter.open_model(str(source)))
        source_model = module.require_source(adapter, adapter.currentModel)
        bank, report["entities_moved_reopened"] = resolve(source_model)
        if report["entities_before"] != report["entities_moved_reopened"]:
            raise RuntimeError("moved-cold source role geometry changed")
        check(
            "reopen moved drawing", await adapter.open_model(str(module.OUTPUTS.slddrw))
        )
        moved_cold = scene("moved_reopened", source_model, bank)
        compare(moved, moved_cold, "moved drawing cold reopen")
        attachments.check_layout(
            report["movement"]["requested"],
            moved_cold["layout"],
            "moved drawing cold reopen",
        )
        report["moved_cold_annotations"] = compare_reopened_annotations(
            moved["annotations"], moved_cold["annotations"]
        )
        checkpoint()
        if report["moved_cold_annotations"]["status"] != "passed":
            raise RuntimeError("moved-cold annotation contents/layout changed")
        export_pdf_only(adapter, directory / "moved-cold.pdf")
        drawing.render_pdf_png(
            directory / "moved-cold.pdf", directory / "moved-cold.png"
        )
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        try:
            adapter.ownership.assert_current_owned()
            if int(adapter.currentModel.GetType()) == 3:
                report["partial_annotations"], _ = all_annotation_layout(adapter)
                report["partial_attachments"] = attachments.snapshot(
                    adapter.currentModel, app=adapter.swApp
                )
                export_pdf_only(adapter, directory / "failure.pdf")
                drawing.render_pdf_png(
                    directory / "failure.pdf", directory / "failure.png"
                )
        except Exception as evidence_error:
            report["partial_evidence_error"] = repr(evidence_error)
        raise
    finally:
        primary = sys.exception()
        errors = []
        for label, action in (
            ("template_guards", lambda: _require_template_guards(controller)),
            ("source_original", lambda: _require_hash(SOURCE)),
            ("source_copy", lambda: _require_hash(source)),
            ("execution_token", lambda: _require_token()),
        ):
            try:
                report[label] = action()
            except Exception as error:
                report[label] = {"error": repr(error)}
                errors.append(error)
        report["template_guard_details"] = controller.guards
        if errors:
            report.update(
                status="failed", final_errors=[repr(error) for error in errors]
            )
        try:
            checkpoint()
        except Exception as error:
            errors.append(error)
        if errors:
            raise ExceptionGroup(
                "candidate operation/final evidence failures",
                ([primary] if primary else []) + errors,
            ) from None
    return {"report": str(report_path)}


def _require_template_guards(controller):
    errors = controller.final_guards()
    if errors:
        raise ExceptionGroup("candidate template/helper guards", errors)
    return "passed"


def _require_hash(path):
    value = sha(path)
    if value != EXPECTED_SOURCE_SHA:
        raise RuntimeError(f"source hash changed: {path}")
    return value


def _require_token():
    value = TOKEN.read_text(encoding="utf-8").strip()
    if value != EXPECTED_SOURCE_SHA:
        raise RuntimeError("original execution token changed")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("source", "drawing", "positive", "candidate"))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if not args.worker:
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), args.mode, "--worker"],
            "crank-arm entity diagnostic",
            com=True,
            log_stem="crank-arm-entities-probe",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("crank-arm worker requires the locked parent")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="crank-arm-entities-", dir=reports))
    callback = {
        "source": capture_source,
        "drawing": capture_drawing,
        "positive": positive_control,
        "candidate": candidate_control,
    }[args.mode]
    return run_copy_diagnostic(lambda adapter: callback(adapter, directory))


if __name__ == "__main__":
    raise SystemExit(main())

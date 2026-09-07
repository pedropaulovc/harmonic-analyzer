"""One native PMI import into an exactly selected view, at native positions.

Composes the safe all-view control without modifying it. Uses a fresh unique
transgear-stub bytecopy, three native orthographic views and exactly two imports.
Default only changes AllViews to False. Each explicit Right-only spacing option
runs one native 317 OR 313 command on the three imported annotations, with no setter,
manual position, additional command or retry.
Missing coverage remains a failed observation even when diagnostic exports exist.
"""

from __future__ import annotations

import argparse
from enum import StrEnum
from itertools import combinations
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
import _telemetry  # noqa: E402
from solidworks_mcp.adapters.pywin32_adapter import null_callout  # noqa: E402
from solidworks_mcp.adapters.solidworks import drawing as native_drawing  # noqa: E402
from transgear_stub_spec import DRAWING_DIMENSIONS  # noqa: E402
from diagnostics import probe_native_model_pmi as pmi  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics import probe_retained_drawing_export as retained  # noqa: E402
from diagnostics.probe_prepared_template_cache import require_environment  # noqa: E402
from diagnostics._owned_native_documents import (  # noqa: E402
    DocumentKind,
    run_copy_diagnostic,
    save_drawing,
)
from diagnostics._source_dimension_snapshot import dimension_snapshot, compare_source  # noqa: E402
from diagnostics._reopen_annotation_comparison import compare_reopened_annotations  # noqa: E402
from diagnostics._source_pmi_comparison import SourcePmiBoundary, compare_source_pmi  # noqa: E402


class PmiArrangement(StrEnum):
    SPACE_TIGHTLY_DOWN = "space-tightly-down"
    SPACE_EVENLY_DOWN = "space-evenly-down"


PMI_SPACING_COMMANDS = {
    PmiArrangement.SPACE_TIGHTLY_DOWN: 317,
    PmiArrangement.SPACE_EVENLY_DOWN: 313,
}


def require_arrangement(orientation, arrangement):
    if arrangement is None:
        return
    if orientation != "*Right" or not isinstance(arrangement, PmiArrangement):
        raise ValueError("PMI spacing control requires the explicit native Right view")


def space_imported_pmi(adapter, view, imported, row, checkpoint, *, arrangement):
    """One selected spacing command, never stacked, on the same exact native bank."""
    require_arrangement("*Right", arrangement)
    command = PMI_SPACING_COMMANDS[arrangement]
    adapter.ownership.assert_current_owned()
    model, app = _early_bound(adapter.currentModel, "IModelDoc2"), adapter.swApp
    drawing = _early_bound(model, "IDrawingDoc")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    annotations = tuple(_early_bound(item, "IAnnotation") for item in imported)
    if len(annotations) != 3 or any(item is None for item in annotations):
        raise RuntimeError(
            "PMI spacing needs exactly three nonnull imported annotations"
        )
    kinds = tuple(int(item.GetType()) for item in annotations)
    if sorted(kinds) != [2, 5, 5] or any(
        int(app.IsSame(first, second)) == 1
        for first, second in combinations(annotations, 2)
    ):
        raise RuntimeError(
            "PMI spacing needs two distinct GTols and one distinct datum"
        )
    row.update(command=command, selections=[], status="selecting")
    model.ClearSelection2(True)
    try:
        if not drawing.ActivateView(str(view.GetName2())):
            raise RuntimeError("PMI spacing could not activate its exact Right view")
        for annotation, kind in zip(annotations, kinds, strict=True):
            if (
                int(annotation.OwnerType) != 0
                or int(app.IsSame(annotation.Owner, view)) != 1
            ):
                raise RuntimeError(
                    "PMI spacing imported annotation has a different owner"
                )
            # Same native-proven call shape as the existing GTol command control.
            # Select2 is obsolete in favor of Select3, but not a coordinate pick.
            if not annotation.Select2(True, 0):
                raise RuntimeError("PMI spacing annotation selection rejected")
        if int(selection.GetSelectedObjectCount2(-1)) != 3:
            raise RuntimeError("PMI spacing selected bank is not exactly three")
        for index, (annotation, kind) in enumerate(
            zip(annotations, kinds, strict=True), 1
        ):
            expected_type, interface = (36, "IDatumTag") if kind == 2 else (13, "IGtol")
            selected_type = int(selection.GetSelectedObjectType3(index, -1))
            if selected_type != expected_type:
                raise RuntimeError(
                    "PMI spacing selected native annotation type differs"
                )
            specific = _early_bound(selection.GetSelectedObject6(index, -1), interface)
            selected = (
                _early_bound(specific.GetAnnotation(), "IAnnotation")
                if specific is not None
                else None
            )
            selected_view = selection.GetSelectedObjectsDrawingView2(index, -1)
            identity = (
                int(app.IsSame(selected, annotation)) if selected is not None else None
            )
            row["selections"].append(
                {
                    "name": str(annotation.GetName()),
                    "type": selected_type,
                    "identity": identity,
                    "selected_view_null": selected_view is None,
                }
            )
            if (
                identity != 1
                or (
                    selected_view is not None
                    and int(app.IsSame(selected_view, view)) != 1
                )
                or int(selected.OwnerType) != 0
                or int(app.IsSame(selected.Owner, view)) != 1
            ):
                raise RuntimeError(
                    "PMI spacing selection changed annotation/view identity"
                )
        row["enabled"] = bool(app.IsCommandEnabled(command))
        checkpoint()
        if not row["enabled"]:
            raise RuntimeError(f"native PMI {arrangement.value} {command} is disabled")
        adapter.ownership.assert_current_owned()
        started = time.perf_counter()
        try:
            with _telemetry.span(
                f"diagnostic.selected_view_pmi.{arrangement.name.lower()}",
                command=command,
                count=3,
            ):
                row["returned"] = bool(app.RunCommand(command, ""))
        finally:
            row["command_seconds"] = time.perf_counter() - started
        if not row["returned"]:
            raise RuntimeError(
                f"native PMI {arrangement.value} {command} rejected the bank"
            )
        row["status"] = "returned"
    finally:
        primary_error = sys.exception()
        try:
            adapter.ownership.assert_current_owned()
            model.ClearSelection2(True)
        except Exception as error:
            row["selection_cleanup_error"] = repr(error)
            raise BaseExceptionGroup(
                "PMI spacing/selection cleanup failed",
                ([primary_error] if primary_error is not None else []) + [error],
            )
        finally:
            checkpoint()


def compare_arranged_pmi(
    adapter,
    before,
    after,
    before_views,
    after_views,
    before_handles,
    after_handles,
    selected_name,
):
    """Exact semantic/identity checks; allow only the imported bank's native ink to move."""
    if before["views"] != after["views"] or before_views.keys() != after_views.keys():
        raise RuntimeError(
            "PMI spacing changed native view/source/configuration inventory"
        )
    if any(
        int(adapter.swApp.IsSame(view, after_views[name])) != 1
        for name, view in before_views.items()
    ):
        raise RuntimeError("PMI spacing replaced a native view")
    pilot.attachments.check_layout(before["layout"], after["layout"], "PMI spacing")
    if {key: value for key, value in before["pmi"].items() if key != "annotations"} != {
        key: value for key, value in after["pmi"].items() if key != "annotations"
    }:
        raise RuntimeError("PMI spacing changed native sheet/view geometry")
    initial_pmi = {row["name"]: row for row in before["pmi"]["annotations"]}
    actual_pmi = {row["name"]: row for row in after["pmi"]["annotations"]}
    if (
        len(before["pmi"]["annotations"]) != 3
        or len(after["pmi"]["annotations"]) != 3
        or len(initial_pmi) != 3
        or initial_pmi.keys() != actual_pmi.keys()
    ):
        raise RuntimeError("PMI spacing changed the imported semantic inventory")
    for name, initial in initial_pmi.items():
        actual = actual_pmi[name]
        if {key: value for key, value in initial.items() if key != "position_m"} != {
            key: value for key, value in actual.items() if key != "position_m"
        }:
            raise RuntimeError(
                f"PMI spacing changed manufacturing/attachment semantics: {name}"
            )
    pilot.shoulder.compare_all_annotation_layout(
        adapter.swApp,
        before["annotations"],
        after["annotations"],
        before_handles,
        after_handles,
    )
    permitted = {f"{selected_name}/{name}" for name in initial_pmi}
    if not permitted <= before["annotations"].keys():
        raise RuntimeError("PMI spacing has no exact raw bank in the selected view")
    movement, bodies = {}, {}
    for key, initial in before["annotations"].items():
        actual = after["annotations"][key]
        if key not in permitted:
            if initial != actual:
                raise RuntimeError(
                    f"PMI spacing changed unselected annotation ink: {key}"
                )
            continue
        old, new = initial.get("measurement"), actual.get("measurement")
        if old is None or new is None:
            raise RuntimeError(f"PMI spacing lacks native body measurement: {key}")
        if any(
            old[field] != new[field] for field in ("name", "kind", "format_signature")
        ):
            raise RuntimeError(f"PMI spacing changed native annotation format: {key}")
        movement[key] = {
            "anchor_before": initial["position"],
            "anchor_after": actual["position"],
            "body_before": old["body"],
            "body_after": new["body"],
            "native_before": initial["native"],
            "native_after": actual["native"],
        }
        bodies[key] = new["body"]
    gaps, failures = [], coverage_failures(after["pmi"], selected_name, "after spacing")
    for first, second in combinations(bodies, 2):
        a, b = bodies[first], bodies[second]
        gap = max(
            b["xmin"] - a["xmax"],
            a["xmin"] - b["xmax"],
            b["ymin"] - a["ymax"],
            a["ymin"] - b["ymax"],
        )
        gaps.append({"first": first, "second": second, "axis_gap_m": gap})
        if gap <= 0:
            failures.append(
                f"native PMI bodies still overlap/touch: {first} / {second}"
            )
    if not any(
        row["anchor_before"] != row["anchor_after"]
        for key, row in movement.items()
        if before["annotations"][key]["semantic"]["kind"] == 5
    ):
        failures.append("Native PMI spacing did not move either imported GTol anchor")
    return {"movement": movement, "body_gaps": gaps, "failures": failures}


def select_exact_view(adapter, view, observation):
    adapter.ownership.assert_current_owned()
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    drawing = _early_bound(model, "IDrawingDoc")
    name = str(view.GetName2())
    observation["name"] = name
    if not name or not drawing.ActivateView(name):
        raise RuntimeError("selected-view control cannot activate the exact named view")
    model.ClearSelection2(True)
    extension = _early_bound(model.Extension, "IModelDocExtension")
    # Official named DRAWINGVIEW shape. These zeros are not geometry picks.
    observation["returned"] = extension.SelectByID2(
        name, "DRAWINGVIEW", 0, 0, 0, False, 0, null_callout(), 0
    )
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    observation["count"] = int(selection.GetSelectedObjectCount2(-1))
    if not observation["returned"] or observation["count"] != 1:
        raise RuntimeError("native drawing-view selection failed or is not singular")
    observation["type"] = int(selection.GetSelectedObjectType3(1, -1))
    selected = selection.GetSelectedObject6(1, -1)
    observation["identity"] = (
        int(adapter.swApp.IsSame(selected, view)) if selected is not None else None
    )
    if observation["type"] != 12 or observation["identity"] != 1:
        raise RuntimeError("native drawing-view selection is not the exact IView")


def selected_imports(adapter, view, rows, checkpoint):
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    returned = []
    for label, mask in (("gtols", 32), ("datums", 2)):
        row = {
            "kind": label,
            "mask": mask,
            "all_views": False,
            "status": "selecting",
            "selection": {},
        }
        rows.append(row)
        checkpoint()
        try:
            select_exact_view(adapter, view, row["selection"])
            row["status"] = "importing"
            checkpoint()
            adapter.ownership.assert_current_owned()
            started = time.perf_counter()
            try:
                with _telemetry.span(
                    "diagnostic.selected_view_pmi.import", annotation_kind=label
                ):
                    result = drawing.InsertModelAnnotations3(
                        0, mask, False, True, False, True
                    )
            finally:
                row["import_seconds"] = time.perf_counter() - started
            if isinstance(result, str):
                raise RuntimeError(
                    "native import returned text instead of an annotation array"
                )
            bank = tuple(result or ())
            row.update(
                status="returned",
                returned_count=len(bank),
                null_count=sum(item is None for item in bank),
            )
            returned.extend(bank)
        except Exception as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            # No assumption that the first import leaves the view selected.
            primary_error = sys.exception()
            try:
                adapter.ownership.assert_current_owned()
                adapter.currentModel.ClearSelection2(True)
            except Exception as error:
                row.update(status="failed", selection_cleanup_error=repr(error))
                raise BaseExceptionGroup(
                    "selected import/selection cleanup failed",
                    ([primary_error] if primary_error is not None else []) + [error],
                )
            finally:
                checkpoint()
    return returned


def native_views(adapter, source, configuration, source_model):
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheets = tuple(drawing.GetViews() or ())
    if len(sheets) != 1 or len(tuple(sheets[0] or ())) != 4:
        raise RuntimeError(
            "selected-view control needs one sheet and three native views"
        )
    handles, rows = {}, {}
    for raw in sheets[0][1:]:
        view = _early_bound(raw, "IView")
        name = str(view.GetName2())
        if not name or name in handles:
            raise RuntimeError("native view names must be nonempty and unique")
        model = _early_bound(view.ReferencedDocument, "IModelDoc2")
        reference = str(model.GetPathName()) if model is not None else ""
        current_configuration = str(view.ReferencedConfiguration)
        source_identity = (
            int(adapter.swApp.IsSame(model, source_model))
            if model is not None
            else None
        )
        if (
            not reference
            or Path(reference).resolve() != source
            or current_configuration != configuration
            or source_identity != 1
        ):
            raise RuntimeError(
                f"native view {name!r} has the wrong copied source/configuration: "
                f"path={reference!r}, configuration={current_configuration!r}, identity={source_identity}"
            )
        handles[name] = view
        rows[name] = {
            "orientation": str(view.GetOrientationName()),
            "rotation": rotation_values(
                _early_bound(view.ModelToViewTransform, "IMathTransform").ArrayData[:9]
            ),
            "source": reference,
            "configuration": current_configuration,
            "source_identity": source_identity,
        }
    return handles, rows


def rotation_values(raw):
    values = tuple(float(value) for value in raw)
    if len(values) != 9 or not all(math.isfinite(value) for value in values):
        raise RuntimeError("native view rotation must contain nine finite values")
    axes = (values[:3], values[3:6], values[6:9])
    for i, first in enumerate(axes):
        for j, second in enumerate(axes):
            if not math.isclose(
                sum(a * b for a, b in zip(first, second)), float(i == j), abs_tol=1e-9
            ):
                raise RuntimeError("native view rotation is not orthonormal")
    return values


def orientation_view(handles, rows, orientation, standard_rotations):
    if orientation not in ("*Front", "*Top", "*Right"):
        raise ValueError(
            f"unsupported native orthographic orientation: {orientation!r}"
        )
    front = [name for name, row in rows.items() if row["orientation"] == "*Front"]
    if len(front) != 1:
        raise RuntimeError(f"native *Front orientation is not unique: {rows}")

    def matches(actual, expected):
        return all(
            math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
            for a, b in zip(
                rotation_values(actual), rotation_values(expected), strict=True
            )
        )

    # Positive control for the matrix convention before selecting any projected
    # view. GetOrientationName is documented empty for projected views.
    if not matches(rows[front[0]]["rotation"], standard_rotations["*Front"]):
        raise RuntimeError(
            "named Front view does not match the source standard Front rotation"
        )
    candidates = [
        name
        for name, row in rows.items()
        if matches(row["rotation"], standard_rotations[orientation])
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"native {orientation} orientation is not unique: {rows}")
    return handles[candidates[0]]


def coverage_failures(snapshot, selected_name, stage):
    failures = pmi.witness_failures(snapshot["annotations"], stage=stage)
    for row in snapshot["annotations"]:
        if row["view"] != selected_name or row["owner_type"] != 0:
            failures.append(
                f"{stage}: {row['name']} is not owned by the selected drawing view"
            )
    return failures


def exact_returned_inventory(app, returned, before, after, after_handles):
    new_names = set(after) - set(before)
    actual = [after_handles[name][0] for name in new_names]
    if len(returned) != len(actual) or any(item is None for item in returned):
        raise RuntimeError(
            "returned annotation array does not match the new native inventory"
        )
    if any(
        sum(int(app.IsSame(item, candidate)) == 1 for candidate in actual) != 1
        for item in returned
    ):
        raise RuntimeError(
            "returned annotations do not identify the exact imported view instances"
        )
    if any(
        sum(int(app.IsSame(item, candidate)) == 1 for item in returned) != 1
        for candidate in actual
    ):
        raise RuntimeError(
            "native imported annotation identity is duplicated or omitted"
        )


def snapshot(adapter, copy, configuration, source_model):
    handles, views = native_views(adapter, copy, configuration, source_model)
    records = pmi.drawing_snapshot(
        adapter.swApp, _early_bound(adapter.currentModel, "IDrawingDoc"), copy
    )
    annotations, annotation_handles = pilot.shoulder.all_annotation_layout(adapter)
    return (
        {
            "pmi": records,
            "views": views,
            "layout": pilot.attachments.layout(adapter.currentModel),
            "annotations": annotations,
        },
        handles,
        annotation_handles,
    )


def unchanged_live(
    adapter, before, after, before_views, after_views, before_handles, after_handles
):
    if before["pmi"] != after["pmi"] or before["views"] != after["views"]:
        raise RuntimeError("native save/export changed PMI or view witnesses")
    pilot.attachments.check_layout(
        before["layout"], after["layout"], "selected PMI save/export"
    )
    for name, handle in before_views.items():
        if int(adapter.swApp.IsSame(handle, after_views[name])) != 1:
            raise RuntimeError("native save/export replaced a view")
    if pilot.shoulder.compare_all_annotation_layout(
        adapter.swApp,
        before["annotations"],
        after["annotations"],
        before_handles,
        after_handles,
    ):
        raise RuntimeError("native save/export changed actual annotation layout")


async def probe(
    adapter,
    source,
    output_root,
    expected_pid,
    expected_source_sha,
    *,
    orientation="*Front",
    arrangement=None,
):
    require_arrangement(orientation, arrangement)
    require_environment(expected_pid)
    app = _early_bound(adapter.swApp, "ISldWorks")
    if int(app.GetProcessID()) != expected_pid:
        raise RuntimeError("native PID differs from the explicitly approved process")
    # Resolve exactly the configured default used by the old all-view control;
    # do not fall back to another template if it is missing.
    template_value = str(
        app.GetUserPreferenceStringValue(native_drawing._SW_PREF_TEMPLATE_DRAWING) or ""
    )
    if not template_value:
        raise RuntimeError("configured default drawing template is empty")
    template = Path(template_value).resolve(strict=True)
    if (
        template.suffix.lower() != ".drwdot"
        or not template.is_file()
        or not template.stat().st_size
    ):
        raise RuntimeError(
            "configured default drawing template is not a complete DRWDOT"
        )
    expected = {
        str(source): expected_source_sha,
        str(template): pmi.file_digest(template),
    }
    retained.require_hashes(expected, "before selected-view PMI")
    output_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="selected-view-pmi-", dir=output_root))
    adapter.ownership.register_directory(directory)
    for path in expected:
        adapter.ownership.register_source(Path(path))
    copy = directory / f"{directory.name}-transgear-stub.SLDPRT"
    native = directory / f"{directory.name}.SLDDRW"
    report_path = directory / "observations.json"
    report = {
        "status": "running",
        "visual_review": "pending",
        "scope": "two imports into one exactly selected native orthographic view; no layout/source edits or retry",
        "requested_orientation": orientation,
        "requested_arrangement": arrangement.value if arrangement is not None else None,
        "source": str(source),
        "copy": str(copy),
        "inputs_before": expected,
        "revision": pilot.benchmark.revision("HEAD"),
        "helpers_before": pilot.helper_fingerprints(),
        "adapter_before": pilot.adapter_fingerprints(),
        "expected_pid": expected_pid,
        "configured_template": template_value,
        "imports": [],
        "failures": [],
        "artifacts": {},
    }
    errors = []
    if arrangement is not None:
        report["scope"] = (
            f"two exact Right-view PMI imports plus one native{PMI_SPACING_COMMANDS[arrangement]} spacing command on their exact three annotations; no manual placement/source edits/retry"
        )
    copy_expected = {}
    started = time.perf_counter()

    def checkpoint():
        report_path.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )

    def source_witness(
        model, phase, before=None, handles=None, *, boundary=SourcePmiBoundary.LIVE
    ):
        if (
            model is None
            or int(model.GetType()) != 1
            or Path(model.GetPathName()).resolve() != copy
        ):
            raise RuntimeError("source witness is not the exact owned part path/type")
        annotations = pmi.source_snapshot(app, model)
        values, current_handles = dimension_snapshot(
            app, model, copy, required=DRAWING_DIMENSIONS
        )
        report[phase] = {"pmi": annotations, "dimensions": values}
        if before is None:
            failures = pmi.witness_failures(annotations, stage="source")
            if failures:
                report["failures"].extend(failures)
                raise RuntimeError(
                    "source does not satisfy the authored PMI positive control"
                )
        else:
            comparison = compare_source_pmi(before["pmi"], annotations, boundary=boundary)
            report[phase]["pmi_comparison"] = comparison
            if comparison["status"] != "passed":
                raise RuntimeError("source PMI changed during drawing import/export")
            changes = compare_source(
                before["dimensions"],
                values,
                app=app,
                handles_before=handles,
                handles_after=current_handles,
            )
            report[phase]["presentation_changes"] = changes
            if changes:
                raise RuntimeError(
                    "source dimension presentation changed during PMI control"
                )
        return report[phase], current_handles

    checkpoint()
    _telemetry.info("selected-view model PMI report", path=str(report_path))
    try:
        shutil.copy2(source, copy)
        copy_expected[str(copy)] = expected_source_sha
        retained.require_hashes(copy_expected, "initial unique source copy")
        check("open unique source copy", await adapter.open_model(str(copy)))
        adapter.ownership.assert_current_owned()
        source_model = _early_bound(adapter.currentModel, "IModelDoc2")
        source_before, source_handles = source_witness(source_model, "source_before")
        report["standard_rotations"] = {
            name: rotation_values(source_model.GetStandardViewRotation(view_id))
            for name, view_id in (("*Front", 1), ("*Right", 4), ("*Top", 5))
        }  # swStandardViews_e; read-only source API.
        configuration = source_before["dimensions"]["configuration"]
        with adapter.ownership.creating_document(DocumentKind.DRAWING, native):
            native_drawing.new_drawing(adapter, template=str(template))
            drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
            # Native third-angle creation renames an unsaved drawing after its
            # source. Keep that observed transition inside the creation scope;
            # the scope still requires the same native handle and declared path.
            if not drawing.Create3rdAngleViews2(str(copy)):
                raise RuntimeError("native third-angle views rejected the owned copy")
        before, view_handles, before_handles = snapshot(
            adapter, copy, configuration, source_model
        )
        report["before_import"] = before
        if before["pmi"]["annotations"]:
            raise RuntimeError(
                "fresh native views already contain PMI; import baseline is not empty"
            )
        view = orientation_view(
            view_handles, before["views"], orientation, report["standard_rotations"]
        )
        selected_name = str(view.GetName2())
        report["selected_view"] = selected_name
        imported = selected_imports(adapter, view, report["imports"], checkpoint)
        initial, initial_views, initial_handles = snapshot(
            adapter, copy, configuration, source_model
        )
        report["initial"] = initial
        report["failures"].extend(
            coverage_failures(initial["pmi"], selected_name, "initial")
        )
        exact_returned_inventory(
            app,
            imported,
            before["annotations"],
            initial["annotations"],
            initial_handles,
        )
        if before["views"] != initial["views"]:
            raise RuntimeError(
                "PMI import changed view ownership/orientation/configuration"
            )
        if any(
            int(app.IsSame(handle, initial_views[name])) != 1
            for name, handle in view_handles.items()
        ):
            raise RuntimeError("PMI import replaced a native drawing view")
        pilot.attachments.check_layout(
            before["layout"], initial["layout"], "PMI import"
        )
        existing = {
            name: initial["annotations"][name] for name in before["annotations"]
        }
        if pilot.shoulder.compare_all_annotation_layout(
            app,
            before["annotations"],
            existing,
            before_handles,
            {name: initial_handles[name] for name in before_handles},
        ):
            raise RuntimeError("PMI import changed a pre-existing drawing annotation")
        source_witness(
            source_model, "source_after_import", source_before, source_handles
        )
        checkpoint()
        if arrangement is not None:
            if report["failures"]:
                raise RuntimeError("PMI arrangement requires complete initial coverage")
            arrangement_report = report["arrangement"] = {"variant": arrangement.value}
            space_imported_pmi(
                adapter,
                view,
                imported,
                arrangement_report,
                checkpoint,
                arrangement=arrangement,
            )
            arranged, arranged_views, arranged_handles = snapshot(
                adapter, copy, configuration, source_model
            )
            report["arranged"] = arranged
            arrangement_report.update(
                compare_arranged_pmi(
                    adapter,
                    initial,
                    arranged,
                    initial_views,
                    arranged_views,
                    initial_handles,
                    arranged_handles,
                    selected_name,
                )
            )
            report["failures"].extend(arrangement_report["failures"])
            source_witness(
                source_model, "source_after_arrangement", source_before, source_handles
            )
            initial, initial_views, initial_handles = (
                arranged,
                arranged_views,
                arranged_handles,
            )
            checkpoint()
        # Diagnostic output is retained even when coverage is incomplete; the
        # final machine status stays failed. No source-part save is authorized.
        pdf, png = directory / "initial.pdf", directory / "initial.png"
        save_drawing(adapter, str(native), pdf_path=str(pdf))
        pmi.render_pdf_png(pdf, png)
        report["artifacts"]["initial"] = {
            "drawing": str(native),
            "pdf": str(pdf),
            "png": str(png),
        }
        retained.require_hashes(copy_expected, "after owned drawing save")
        saved, saved_views, saved_handles = snapshot(
            adapter, copy, configuration, source_model
        )
        report["saved"] = saved
        unchanged_live(
            adapter,
            initial,
            saved,
            initial_views,
            saved_views,
            initial_handles,
            saved_handles,
        )
        source_witness(source_model, "source_after_save", source_before, source_handles)
        saved_sha = pmi.file_digest(native)
        await adapter.close_owned_documents()
        retained.require_hashes(copy_expected, "after cold close")
        check("cold reopen unique PMI drawing", await adapter.open_model(str(native)))
        adapter.ownership.assert_current_owned()
        reopened_source = _early_bound(
            app.GetOpenDocumentByName(str(copy)), "IModelDoc2"
        )
        cold_source, cold_source_handles = source_witness(
            reopened_source,
            "source_reopened",
            source_before,
            boundary=SourcePmiBoundary.COLD,
        )
        reopened, reopened_views, reopened_handles = snapshot(
            adapter, copy, configuration, reopened_source
        )
        report["reopened"] = reopened
        report["failures"].extend(
            coverage_failures(reopened["pmi"], selected_name, "reopened")
        )
        if saved["pmi"] != reopened["pmi"] or saved["views"] != reopened["views"]:
            report["failures"].append("cold reopen changed PMI/view witnesses")
        pilot.attachments.check_layout(
            saved["layout"], reopened["layout"], "cold PMI reopen"
        )
        report["cold_comparison"] = compare_reopened_annotations(
            saved["annotations"], reopened["annotations"]
        )
        if report["cold_comparison"]["status"] != "passed":
            report["failures"].append("cold reopen changed actual annotation layout")
        pdf, png = directory / "reopened.pdf", directory / "reopened.png"
        retained.export_pdf_only(adapter, pdf)
        pmi.render_pdf_png(pdf, png)
        report["artifacts"]["reopened"] = {"pdf": str(pdf), "png": str(png)}
        exported, exported_views, exported_handles = snapshot(
            adapter, copy, configuration, reopened_source
        )
        report["after_reopened_export"] = exported
        unchanged_live(
            adapter,
            reopened,
            exported,
            reopened_views,
            exported_views,
            reopened_handles,
            exported_handles,
        )
        source_witness(
            reopened_source,
            "source_after_reopened_export",
            cold_source,
            cold_source_handles,
        )
        retained.require_hashes(
            {str(native): saved_sha, **copy_expected}, "PDF-only cold export"
        )
    except Exception as error:
        report["operation_error"] = repr(error)
        errors.append(error)
    finally:
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            report["cleanup_error"] = repr(error)
            errors.append(error)
        for label, expected_value, reader in (
            (
                "inputs",
                expected,
                lambda: {path: pmi.file_digest(Path(path)) for path in expected},
            ),
            (
                "copy",
                copy_expected,
                lambda: {path: pmi.file_digest(Path(path)) for path in copy_expected},
            ),
            ("helpers", report["helpers_before"], pilot.helper_fingerprints),
            ("adapter", report["adapter_before"], pilot.adapter_fingerprints),
            (
                "configured_template",
                template_value,
                lambda: str(
                    app.GetUserPreferenceStringValue(
                        native_drawing._SW_PREF_TEMPLATE_DRAWING
                    )
                    or ""
                ),
            ),
        ):
            try:
                actual = reader()
                report[label + "_after"] = actual
                if actual != expected_value:
                    raise RuntimeError(
                        f"frozen {label} changed during selected-view control"
                    )
            except Exception as error:
                report[label + "_guard_error"] = repr(error)
                errors.append(error)
        report["artifact_sha256"] = {}
        for stage in report["artifacts"].values():
            for path in stage.values():
                try:
                    if not Path(path).is_file() or not Path(path).stat().st_size:
                        raise RuntimeError(
                            f"missing or empty diagnostic artifact: {path}"
                        )
                    report["artifact_sha256"][path] = pmi.file_digest(Path(path))
                except Exception as error:
                    report["artifact_sha256"][path] = {"error": repr(error)}
                    errors.append(error)
        report.update(
            status="failed" if errors or report["failures"] else "passed",
            seconds=time.perf_counter() - started,
        )
        report["errors"] = [repr(error) for error in errors]
        checkpoint()
    if errors:
        raise ExceptionGroup(
            "selected-view PMI operation/cleanup/guard failures", errors
        )
    if report["failures"]:
        raise RuntimeError(
            "selected-view PMI witness failed: " + "; ".join(report["failures"])
        )
    return {"report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--expected-pid", type=int, required=True)
    parser.add_argument(
        "--orientation",
        choices=("*Front", "*Top", "*Right"),
        default="*Front",
        help="one explicitly selected native view; each invocation uses a fresh source copy",
    )
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument(
        "--arrangement", type=PmiArrangement, choices=tuple(PmiArrangement)
    )
    parser.add_argument("--source-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_arrangement(args.orientation, args.arrangement)
    require_environment(args.expected_pid)  # Before dodo._run in the parent.
    source = args.source.resolve(strict=True)
    if source.suffix.upper() != ".SLDPRT" or not source.is_file():
        raise ValueError("selected-view control requires a native transgear-stub part")
    digest = pmi.file_digest(source)
    if args.worker:
        if args.source_sha256 != digest:
            raise RuntimeError("source identity changed between parent and worker")
        return run_copy_diagnostic(
            lambda adapter: probe(
                adapter,
                source,
                args.report_root.resolve(),
                args.expected_pid,
                digest,
                orientation=args.orientation,
                **(
                    {"arrangement": args.arrangement}
                    if args.arrangement is not None
                    else {}
                ),
            )
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            str(source),
            "--expected-pid",
            str(args.expected_pid),
            "--orientation",
            args.orientation,
            *(
                ["--arrangement", args.arrangement.value]
                if args.arrangement is not None
                else []
            ),
            "--report-root",
            str(args.report_root.resolve()),
            "--source-sha256",
            digest,
            "--worker",
        ],
        "selected-view native model PMI control",
        com=True,
        log_stem="selected-view-model-pmi",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

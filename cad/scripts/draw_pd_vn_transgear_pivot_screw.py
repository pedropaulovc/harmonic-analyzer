"""Create MHA-PD-VN-57's faced-to-fit stock drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name, place_view, set_view_position, view_name,
)

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_attachment import _is_same_attachment
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import offset_dimension_text, set_dimension_callouts
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_property_linked_callout
from _drawing_notes import add_property_linked_note, property_link
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from pd_vn_transgear_pivot_screw_spec import (
    CHAMFER_ANGLE,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    DIMENSION_CALLOUTS,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    FITTED_THREAD_LEN,
    HEAD_DIA,
    HEAD_H,
    SHOULDER_END_Y,
    SHOULDER_DIA,
    SKU,
    SOCKET_AF,
    SUPPLIER_DRAWING_DIMENSIONS,
    SUPPLIER_REFERENCE_BANDS,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_TITLE,
    THREAD_LEN,
    THREAD_LENGTH_MIN,
    THREAD_MAJOR,
    TIP_Y,
)

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_screw"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
SHEET_NAMES = ("FINISHED", "90325A174-STOCK")
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
# Sheet metres. The Front view centres the part's Y box (faced tip to head
# top), so the tip lands half the scaled part height below it.
FRONT_CENTER = (0.140, 0.150)
TIP_SHEET_Y = FRONT_CENTER[1] - (HEAD_H - TIP_Y) / 2 * _SHEET_PER_MODEL_MM
SHOULDER_END_SHEET_Y = TIP_SHEET_Y + FITTED_THREAD_LEN * _SHEET_PER_MODEL_MM
# The chamfer meets the tip face one leg inside the thread major radius.
_CHAMFER_VERTEX = (
    FRONT_CENTER[0] + (THREAD_MAJOR / 2 - CHAMFER_WIDTH) * _SHEET_PER_MODEL_MM,
    TIP_SHEET_Y,
)
_ANGLE_TEXT_RADIUS = 0.016
# The B-size inner border is 12.7 mm in from the sheet edge; the title block
# spans x >= 0.216 below y = 0.065.
FRONT_KEEP = {
    # The reference length's dimension line stands left of the thread, level
    # with the span from the shoulder end to the tip; its text leaves on a
    # leader (CUT_LENGTH_TEXT_XY).
    "CutLength": (0.115, (TIP_SHEET_Y + SHOULDER_END_SHEET_Y) / 2),
    # The tail's text stands right of the shank, above its top extension
    # line, so neither extension line crosses the text or its lines.
    "ThreadLengthMin": (
        0.180,
        TIP_SHEET_Y + THREAD_LENGTH_MIN * _SHEET_PER_MODEL_MM + 0.016,
    ),
    # Dimension line 6 mm under the chamfer leg; its text leaves on a leader.
    "ChamferWidth": (
        FRONT_CENTER[0] + (THREAD_MAJOR - CHAMFER_WIDTH) / 2 * _SHEET_PER_MODEL_MM,
        TIP_SHEET_Y - 0.006,
    ),
    # The native 45 degrees in the open wedge right of the tip, 16 mm out on
    # the angle's bisector, below the tail's top extension line.
    "ChamferAngle": (
        _CHAMFER_VERTEX[0]
        + _ANGLE_TEXT_RADIUS * math.cos(math.radians(CHAMFER_ANGLE / 2)),
        _CHAMFER_VERTEX[1]
        + _ANGLE_TEXT_RADIUS * math.sin(math.radians(CHAMFER_ANGLE / 2)),
    ),
}
# The chamfer callout stands below-right of the tip, under the tail's lower
# extension line and right of the leg's own extension lines.
CHAMFER_TEXT_XY = (0.185, TIP_SHEET_Y - 0.018)
# The reference length's four lines stand wholly left of its dimension line
# (73 mm wide), so neither its arrows nor its extension lines strike them.
CUT_LENGTH_TEXT_XY = (0.062, (TIP_SHEET_Y + SHOULDER_END_SHEET_Y) / 2)
# The purchased-screw note flags the unmodified head and shoulder: its leader
# lands on the head-top edge, the note stands up and right in the open field.
HEAD_PICK_MM = (HEAD_DIA / 4, HEAD_H, 0.0)
PURCHASED_NOTE_XY = (0.150, 0.245)
# Every view and the sheet are 4:1, so the title-block SCALE is the view
# scale and the isometric carries no scale label.
ISO_CENTER = (0.360, 0.165)
STOCK_CENTER = (0.180, 0.155)
STOCK_ISO_CENTER = (0.325, 0.165)
TOP_CENTER = (0.295, 0.245)
# The cutting controls verify_machining_controls re-reads. CutLength, the
# fit-up length, still drives the facing cut but prints as a reference.
EXPECTED_CONTROLS = {
    "ChamferWidth": (CHAMFER_WIDTH / 1000, 0.0, 0.0),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE),
        -math.radians(CHAMFER_ANGLE_TOLERANCE),
        math.radians(CHAMFER_ANGLE_TOLERANCE),
    ),
    "ThreadLengthMin": (THREAD_LENGTH_MIN / 1000, 0.0, 0.0),
}
if not math.isclose(SHOULDER_END_Y - FITTED_THREAD_LEN, TIP_Y, abs_tol=1e-9):
    raise AssertionError("the reference length does not end at the faced tip")


def _verify_reference_length(adapter: Any, annotation: Any) -> None:
    """The fit-up length prints "(9.15)" with no band (rule 19)."""
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if not math.isclose(
        float(dimension.SystemValue), FITTED_THREAD_LEN / 1000, abs_tol=1e-9
    ):
        raise RuntimeError("CutLength: native reference nominal changed")
    if int(display.GetPrimaryPrecision2()) != DIMENSION_PRECISION["CutLength"]:
        raise RuntimeError("CutLength: native display precision changed")
    if (
        int(tolerance.Type) != DIMENSION_TOLERANCE_TYPES["CutLength"]
        or (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")")
        or not bool(display.ShowDimensionValue)
    ):
        raise RuntimeError("CutLength: reference display did not persist")


def _assert_supplier_tolerance(display: Any, name: str) -> None:
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    band = SUPPLIER_REFERENCE_BANDS.get(name)
    if int(tolerance.Type) != (2 if band is not None else 0):
        raise RuntimeError(f"{name}: native supplier tolerance type changed")
    if band is not None:
        lower, upper = (value / 1000 for value in band)
        if (
            not math.isclose(float(tolerance.GetMinValue()), lower, rel_tol=0.0, abs_tol=1e-12)
            or not math.isclose(float(tolerance.GetMaxValue()), upper, rel_tol=0.0, abs_tol=1e-12)
            or int(display.GetPrimaryTolPrecision2()) != SUPPLIER_REFERENCE_DIMENSIONS[name]["precision"]
        ):
            raise RuntimeError(f"{name}: model-owned source supplier band changed")


def _format_supplier_reference(adapter: Any, display: Any, name: str) -> Any:
    """Only purchased-reference presentation is drawing-owned; bands are read-only."""
    display = _early_bound(display, "IDisplayDimension")
    supplier_reference_dimension(
        adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
    )
    _assert_supplier_tolerance(display, name)
    return _early_bound(display.GetAnnotation(), "IAnnotation")


def _add_supplier_references(adapter: Any, front: Any, top: Any) -> dict[str, Any]:
    """Measure physical head/socket; import native nominal-major and source bands."""
    head_r, shoulder_r = HEAD_DIA / 2, SHOULDER_DIA / 2
    bearing_pick = (head_r + shoulder_r) / 2
    authored = {}
    for name, view, first, second, text_xy, orientation, entity_type in (
        (
            "SupplierHeadDiameter", front,
            (-head_r, HEAD_H / 2, 0.0), (head_r, HEAD_H / 2, 0.0),
            (0.140, 0.225), "horizontal", "SILHOUETTE",
        ),
        (
            "SupplierHeadHeight", front,
            (bearing_pick, 0.0, 0.0), (bearing_pick, HEAD_H, 0.0),
            (0.224, 0.201), "vertical", "EDGE",
        ),
        (
            "SupplierSocketAF", top,
            (-SOCKET_AF / 2, HEAD_H, 0.0), (SOCKET_AF / 2, HEAD_H, 0.0),
            (TOP_CENTER[0], 0.212), "horizontal", "EDGE",
        ),
    ):
        picks = model_points_in_view(
            adapter, view,
            [tuple(value / 1000 for value in point) for point in (first, second)],
            label=name,
        )
        display = add_edge_dimension(
            adapter, view, p0=picks[0], p1=picks[1], text_xy=text_xy,
            label=name, orientation=orientation, entity_type=entity_type,
        )
        authored[name] = _format_supplier_reference(adapter, display, name)
    references = curate_view_dimensions(
        adapter, front,
        keep={
            "SupplierThreadMajor": (0.239, 0.119),
            "SupplierShoulderDiameter": (0.202, 0.172),
            "SupplierShoulderLength": (0.065, 0.170),
        },
        view_label="supplier nominal envelopes and model-owned source bands",
        dimensions_by_feature=SUPPLIER_DRAWING_DIMENSIONS,
    )
    for annotation in references:
        name = dimension_name(adapter, annotation)
        if name in authored:
            raise RuntimeError(f"{name}: duplicate supplier reference")
        authored[name] = _format_supplier_reference(
            adapter, annotation.GetSpecificAnnotation(), name
        )
    return authored


def _add_stock_reference(adapter: Any) -> tuple[Any, Any, Any]:
    """Measure the original .375-inch thread on its separate stock-only sheet."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate original pivot-screw stock sheet")
    stock = place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=SHEET_SCALE)
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *STOCK_ISO_CENTER, scale=SHEET_SCALE
    )
    for view in (stock, iso):
        _early_bound(view, "IView").ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("source-stock views did not rebuild")
    for view, centre in ((stock, STOCK_CENTER), (iso, STOCK_ISO_CENTER)):
        if str(_early_bound(view, "IView").ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("source-stock view references the faced screw")
        if not set_view_position(adapter, view, *centre):
            raise RuntimeError("cannot position source-stock view")
        set_hidden_lines_removed(adapter, view)
    end_pick = (SHOULDER_DIA + THREAD_MAJOR) / 4
    picks = model_points_in_view(
        adapter, stock,
        (
            (end_pick / 1000, SHOULDER_END_Y / 1000, 0.0),
            (0.0, (SHOULDER_END_Y - THREAD_LEN) / 1000, 0.0),
        ),
        label="as-supplied stock thread length",
    )
    display = add_edge_dimension(
        adapter, stock, p0=picks[0], p1=picks[1], text_xy=(0.130, 0.118),
        label="SupplierStockThreadLength", orientation="vertical",
    )
    annotation = _format_supplier_reference(adapter, display, "SupplierStockThreadLength")
    drawing.ActivateView("")  # False is documented when activating the sheet.
    if drawing.GetEditSheet() is not True:
        raise RuntimeError("stock caption is not in sheet-edit mode")
    note = _early_bound(
        add_property_linked_note(adapter, "Supplier Reference Title", 0.016, 0.252), "INote"
    )
    if int(_early_bound(note.GetAnnotation(), "IAnnotation").OwnerType) != 1:
        raise RuntimeError("source-stock caption is not sheet-owned")
    return stock, iso, annotation


def _supplier_reference_identities(adapter: Any, references: dict[str, Any]) -> dict:
    """Capture exact native identities; no drawing text stands in for a source size."""
    identities = {}
    source_names = {name for names in SUPPLIER_DRAWING_DIMENSIONS.values() for name in names}
    for name, raw in references.items():
        annotation = _early_bound(raw, "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        full_name = str(_early_bound(display.GetDimension2(0), "IDimension").FullName)
        if not full_name or full_name in {value[0] for value in identities.values()}:
            raise RuntimeError(f"{name}: missing or duplicate native source identity")
        if name in source_names and full_name.split("@")[:2] != [name, "SupplierReference"]:
            raise RuntimeError(f"{name}: imported reference has the wrong model carrier")
        identities[name] = (
            full_name, view_name(adapter, annotation.Owner),
            tuple(annotation.GetAttachedEntities3() or ()),
            tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ())),
        )
    return identities


def _assert_supplier_references(adapter: Any, identities: dict, configurations: dict) -> None:
    """Fresh post-rebuild value/precision/band/identity/count/configuration checks."""
    if set(identities) != set(SUPPLIER_REFERENCE_DIMENSIONS):
        raise RuntimeError("supplier reference coverage is incomplete")
    required = {record[0]: name for name, record in identities.items()}
    counts = {name: 0 for name in identities}
    found_views = set()
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name in SHEET_NAMES:
        if not drawing.ActivateSheet(sheet_name):
            raise RuntimeError(f"cannot activate settled sheet {sheet_name}")
        sheet_view = _early_bound(drawing.GetFirstView(), "IView")
        if sheet_name == SHEET_NAMES[1]:
            titles = [
                _early_bound(annotation.GetSpecificAnnotation(), "INote")
                for raw in sheet_view.GetAnnotations() or ()
                if int((annotation := _early_bound(raw, "IAnnotation")).GetType()) == 6
                and int(annotation.OwnerType) == 1
                and str(_early_bound(annotation.GetSpecificAnnotation(), "INote").PropertyLinkedText or "")
                == property_link("Supplier Reference Title")
            ]
            if len(titles) != 1 or str(titles[0].GetText() or "").replace("\r", "") != SUPPLIER_STOCK_TITLE:
                raise RuntimeError("settled source-stock sheet caption changed")
        view = sheet_view.GetNextView()
        while view is not None:
            view = _early_bound(view, "IView")
            owner = view_name(adapter, view)
            found_views.add(owner)
            if configurations.get(owner) != (sheet_name, str(view.ReferencedConfiguration)):
                raise RuntimeError(f"{owner}: finished/source-stock configuration changed")
            if (sheet_name == SHEET_NAMES[1]) != (
                str(view.ReferencedConfiguration) == SUPPLIER_STOCK_CONFIGURATION
            ):
                raise RuntimeError(f"{owner}: finished/source-stock separation was lost")
            for raw in view.GetDisplayDimensions() or ():
                display = _early_bound(raw, "IDisplayDimension")
                dimension = _early_bound(display.GetDimension2(0), "IDimension")
                full_name = str(dimension.FullName)
                name = required.get(full_name)
                if name is None:
                    if sheet_name == SHEET_NAMES[1] or "@SupplierReference@" in full_name:
                        raise RuntimeError(f"unexpected source-stock dimension {full_name}")
                    continue
                counts[name] += 1
                _full_name, expected_owner, entities, kinds = identities[name]
                annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
                if owner != expected_owner or view_name(adapter, annotation.Owner) != owner:
                    raise RuntimeError(f"{name}: native source owner changed")
                assert_supplier_reference_dimension(
                    adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
                )
                attached = tuple(annotation.GetAttachedEntities3() or ())
                actual_kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
                if len(attached) != len(entities) or actual_kinds != kinds or any(
                    not _is_same_attachment(
                        adapter, actual, expected, "SILHOUETTE" if kind == 46 else "EDGE"
                    )
                    for actual, expected, kind in zip(attached, entities, kinds, strict=True)
                ):
                    raise RuntimeError(f"{name}: native source attachment changed")
                _assert_supplier_tolerance(display, name)
            view = view.GetNextView()
    if found_views != set(configurations) or any(count != 1 for count in counts.values()):
        raise RuntimeError(f"settled supplier view/dimension census changed: {counts}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open faced pivot screw", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Purchased Screw Note",
        "Supplier Reference Title",
    )
    properties = read_required_properties(
        adapter.currentModel, required, required=required
    )
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="finished and original pivot-screw stock")
    if not _early_bound(draw, "IDrawingDoc").ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate finished pivot-screw sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Transgear Pivot Screw — Modified Stock Drawing",
            1: "Faced tip, end chamfer and modified-part thread-tail acceptance",
            2: "Harmonic Analyzer Project",
            3: f"MHA-PD-VN-57; McMaster-Carr {SKU}",
            4: "Native reference length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    # Force drawing-quality cosmetic threads on the finished projections.
    for view in (front, iso, top):
        set_hidden_lines_removed(adapter, view)
    # The consumed deburr sketch, the trim sketch and the hidden thread-tail
    # acceptance sketch all lie on the Front plane, so the main view carries
    # every control.
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="fitted reference length, faced-tip chamfer and thread tail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    by_name = {dimension_name(adapter, item): item for item in annotations}
    if set(by_name) != {"CutLength", *EXPECTED_CONTROLS}:
        raise RuntimeError(f"Front view controls are {sorted(by_name)}")
    verify_machining_controls(
        adapter,
        [by_name[name] for name in EXPECTED_CONTROLS],
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )
    _verify_reference_length(adapter, by_name["CutLength"])
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if str(display.GetText(4) or "").replace("\r", "") != DIMENSION_CALLOUTS.get(
            name, ""
        ):
            raise RuntimeError(
                f"{name}: modified-part acceptance callout did not persist"
            )
    offset_dimension_text(
        adapter,
        annotations,
        {"ChamferWidth": CHAMFER_TEXT_XY, "CutLength": CUT_LENGTH_TEXT_XY},
    )
    supplier_refs = _add_supplier_references(adapter, front, top)
    head_edge = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000 for value in HEAD_PICK_MM),
        label="purchased socket head top edge",
    )
    note = _early_bound(
        add_property_linked_callout(
            adapter,
            front,
            property_name="Purchased Screw Note",
            edge_xy=head_edge,
            note_xy=PURCHASED_NOTE_XY,
        ),
        "INote",
    )
    printed = str(note.GetText() or "").replace("\r", "")
    if str(note.PropertyLinkedText or "") != property_link(
        "Purchased Screw Note"
    ) or printed != properties["Purchased Screw Note"].replace("\r", ""):
        raise RuntimeError("Purchased Screw Note: linked head note did not persist")
    stock, stock_iso, stock_annotation = _add_stock_reference(adapter)
    supplier_refs["SupplierStockThreadLength"] = stock_annotation
    identities = _supplier_reference_identities(adapter, supplier_refs)
    configurations = {
        view_name(adapter, view): (sheet, str(_early_bound(view, "IView").ReferencedConfiguration))
        for sheet, views in ((SHEET_NAMES[0], (front, iso, top)), (SHEET_NAMES[1], (stock, stock_iso)))
        for view in views
    }
    if properties["Supplier Reference Title"].replace("\r", "") != SUPPLIER_STOCK_TITLE:
        raise RuntimeError("source-stock title does not identify the original screw")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pivot Screw — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        settled_checks=(lambda: _assert_supplier_references(adapter, identities, configurations),),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

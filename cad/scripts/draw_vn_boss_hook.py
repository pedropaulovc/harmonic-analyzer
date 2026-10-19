"""Create the manufacturing drawing for the modified McMaster 9490T1 anchor."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts, set_dimension_precision
from _drawing_attachment import _is_same_attachment
from _drawing_layout_check import DEFAULT_BOUNDARY_ALLOWANCE_M
from _drawing_edges import visible_view_entities
from _drawing_hidden_sketches import (
    _show_hidden_owners,
    curate_view_dimensions as curate_stock_dimensions,
)
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_projection import model_points_in_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_sheet_region import sheet_drawable_region
from _purchased_fastener_drawing import _box, _inside, assert_supplier_view_fits
from _drawing_view_display import set_hidden_lines_removed
from _drawing_selection import _select_view_entity
from _session import run_build
import _stock_trim_drawing as trim_drawing
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import _telemetry
from vn_boss_hook_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DIMENSION_TOLERANCE_TYPES,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    SUPPLIER_EYE_ID_MM,
    SUPPLIER_FRACTION_DENOMINATOR,
    SUPPLIER_NOMINAL_EYE_OD_MM,
    SUPPLIER_NOMINAL_WIRE_MM,
    SUPPLIER_REFERENCE_PRECISION,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_AXIS_MM,
    SUPPLIER_STOCK_OVERALL_MM,
    SUPPLIER_STOCK_SHANK_MM,
    SUPPLIER_STOCK_WIRE_CENTER_MM,
    SUPPLIER_THREAD,
    SUPPLIER_THREAD_MAJOR_MM,
)

SPEC = DRAWINGS_BY_NAME["vn_boss_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = (2.0, 1.0)
STOCK_SCALE = (2.0, 1.0)
SHEET_NAMES = ("FINISHED", "SUPPLIER-STOCK")
STOCK_CENTER = (0.150, 0.175)
# The jam-nut shank (#1189) is 3.8 longer, 15 mm on the sheet: the view sits
# high enough that the cut-end chamfer dimensions clear the notes below it.
FRONT_CENTER = (0.100, 0.175)
ISO_CENTER = (0.310, 0.213)
# The cut-end deburr is dimensioned on the 4:1 front view itself (its 0.8 leg
# prints 3.2 long); a magnified detail added nothing a machinist needs.
FRONT_KEEP = {
    "FinishedOverall": (0.040, 0.175),
    "ChamferWidth": (0.150, 0.089),
    "ChamferAngle": (0.132, 0.106),
}
# The deburr band is tighter than the title block because its minimum leg
# must bring the cut end under the 3.797 tap drill, so the cut thread starts
# in the lever's tap: the callout names that mate.
CHAMFER_CALLOUT = {"ChamferWidth": "LEAD-IN TO MHA-SM-003 TAP"}
NOTES_Y = 0.076
EXPECTED_CONTROLS = {
    "FinishedOverall": (
        FINISHED_OVERALL_MM / 1000,
        -FINISHED_OVERALL_TOLERANCE_MM / 1000,
        FINISHED_OVERALL_TOLERANCE_MM / 1000,
    ),
    "ChamferWidth": (
        CHAMFER_WIDTH_MM / 1000,
        -CHAMFER_WIDTH_TOLERANCE_MM / 1000,
        CHAMFER_WIDTH_TOLERANCE_MM / 1000,
    ),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE_DEG),
        -math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
        math.radians(CHAMFER_ANGLE_TOLERANCE_DEG),
    ),
}


def _verify_controls(adapter: Any, annotations: list[Any]) -> None:
    trim_drawing.verify_machining_controls(
        adapter,
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )


def _supplier_references(
    adapter: Any, front: Any
) -> list[tuple[Any, dict[str, Any], Any]]:
    """Only the exact 5/16 eye ID is dimensioned on the finished solid."""
    eye = None
    thread = None
    for raw in visible_view_entities(
        front, 4, label="counter anchor supplier contours"
    ):
        silhouette = _early_bound(raw, "ISilhouetteEdge")
        raw_curve = silhouette.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if curve.IsCircle():
            circle = tuple(float(value) for value in curve.CircleParams)
            if (
                all(abs(value) < 1e-8 for value in circle[:3])
                and abs(abs(circle[5]) - 1.0) < 1e-8
                and abs(circle[6] * 2000.0 - SUPPLIER_EYE_ID_MM) < 1e-5
            ):
                eye = raw
        elif thread is None and curve.IsLine():
            face = silhouette.GetFace()
            if face is None:
                continue
            raw_surface = _early_bound(face, "IFace2").GetSurface()
            if raw_surface is None:
                continue
            surface = _early_bound(raw_surface, "ISurface")
            if not surface.IsCylinder():
                continue
            cylinder = tuple(float(value) for value in surface.CylinderParams)
            if (
                abs(cylinder[6] * 2000.0 - SUPPLIER_THREAD_MAJOR_MM) < 1e-5
                and abs(abs(cylinder[4]) - 1.0) < 1e-8
            ):
                thread = raw
    if eye is None:
        raise RuntimeError("unchanged counter eye has no exact ID circular silhouette")
    _select_view_entity(adapter, front, "SILHOUETTE", None, label="EyeID", entity=eye)
    display = adapter.currentModel.AddDiameterDimension2(0.150, 0.241, 0.0)
    adapter.currentModel.ClearSelection2(True)
    if display is None:
        raise RuntimeError("cannot dimension the counter eye ID silhouette")
    contract = dict(
        label="EyeID",
        expected_mm=SUPPLIER_EYE_ID_MM,
        units="in",
        precision=SUPPLIER_REFERENCE_PRECISION["EyeID"],
        presentation="diameter",
        fraction_denominator=SUPPLIER_FRACTION_DENOMINATOR,
    )
    supplier_reference_dimension(adapter, display, **contract)
    if thread is None:
        raise RuntimeError("counter anchor has no surviving supplier thread crest")
    add_attached_note(
        adapter,
        front,
        text=f"({SUPPLIER_THREAD} THREAD — SUPPLIER REF)",
        note_xy=(0.140, 0.170),
        label="counter anchor supplier thread",
        entity_type="SILHOUETTE",
        entity=thread,
        attached_to=thread,
    )
    return [(_early_bound(display, "IDisplayDimension").GetAnnotation(), contract, eye)]


def _supplier_stock_diagram(
    adapter: Any,
) -> tuple[Any, list[tuple[Any, dict[str, Any], Any]], list[tuple[Any, str]]]:
    """A full source stock envelope on its own sheet, never finished controls."""
    stock = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    stock.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if str(stock.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("supplier stock view references the finished configuration")
    set_hidden_lines_removed(adapter, stock)
    # A zero-body view has no honest outline until its actual source sketch
    # is revealed. Reuse the diagram prepare-before-fit convention, not the
    # dimension import's later visibility side effect.
    shown = _show_hidden_owners(
        adapter,
        stock,
        (SUPPLIER_STOCK_FEATURE,),
        view_label="counter anchor source diagram before fitting",
    )
    if set(shown) != {SUPPLIER_STOCK_FEATURE}:
        raise RuntimeError("counter anchor source diagram owner is not saved hidden")
    if adapter.currentModel.EditRebuild3() is not True:
        raise RuntimeError("cannot rebuild the revealed supplier nominal stock view")
    stock.UpdateViewDisplayGeometry()
    outline = _box(stock.GetOutline(), label="revealed counter anchor source diagram")
    ratio = STOCK_SCALE[0] / STOCK_SCALE[1]
    expected_spans = (
        (
            SUPPLIER_STOCK_WIRE_CENTER_MM[0]
            + SUPPLIER_NOMINAL_WIRE_MM / 2.0
            + SUPPLIER_NOMINAL_EYE_OD_MM / 2.0
        )
        / 1000.0
        * ratio,
        SUPPLIER_STOCK_OVERALL_MM / 1000.0 * ratio,
    )
    for actual, expected in zip(
        (outline[2] - outline[0], outline[3] - outline[1]), expected_spans, strict=True
    ):
        if (
            not expected - 1e-7
            <= actual
            <= expected + 2.0 * DEFAULT_BOUNDARY_ALLOWANCE_M
        ):
            raise RuntimeError(
                "revealed supplier diagram outline does not cover its source profile"
            )
    midpoint = (
        0.0,
        (SUPPLIER_STOCK_AXIS_MM[0][1] + SUPPLIER_STOCK_AXIS_MM[-1][1]) / 2000.0,
        0.0,
    )
    projected = model_points_in_view(
        adapter, stock, [midpoint], label="source stock envelope centre"
    )[0]
    before = tuple(float(value) for value in stock.Position)
    stock.Position = double_array(
        [
            before[0] + STOCK_CENTER[0] - projected[0],
            before[1] + STOCK_CENTER[1] - projected[1],
        ]
    )
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("cannot position the complete supplier stock envelope")
    keep = {
        "SupplierNominalEyeOD": (0.180, 0.244),
        "SupplierNominalWire": (0.255, 0.235),
        "SupplierStockShank": (0.105, 0.160),
        "SupplierStockOverall": (0.065, STOCK_CENTER[1]),
    }
    annotations = curate_stock_dimensions(
        adapter,
        stock,
        keep=keep,
        view_label="as-supplied nominal stock envelope and wire section",
        dimensions_by_feature=SUPPLIER_STOCK_DIMENSIONS,
    )
    expected = {
        "SupplierNominalEyeOD": SUPPLIER_NOMINAL_EYE_OD_MM,
        "SupplierNominalWire": SUPPLIER_NOMINAL_WIRE_MM,
        "SupplierStockShank": SUPPLIER_STOCK_SHANK_MM,
        "SupplierStockOverall": SUPPLIER_STOCK_OVERALL_MM,
    }
    refs = []
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        contract = dict(
            label=name,
            expected_mm=expected[name],
            units="in",
            precision=SUPPLIER_REFERENCE_PRECISION[name],
            presentation="diameter" if name.startswith("SupplierNominal") else "length",
            fraction_denominator=(
                None
                if name == "SupplierStockOverall"
                else SUPPLIER_FRACTION_DENOMINATOR
            ),
            callout={
                "SupplierNominalEyeOD": "NOMINAL EYE ENVELOPE",
                "SupplierNominalWire": "NOMINAL WIRE SECTION",
                "SupplierStockShank": "AS-SUPPLIED SHANK / THREAD",
                "SupplierStockOverall": "AS-SUPPLIED OVERALL",
            }[name],
        )
        supplier_reference_dimension(
            adapter, annotation.GetSpecificAnnotation(), **contract
        )
        refs.append((annotation, contract, None))
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter supplier stock sheet context for labels")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    notes = []
    for text, x, y in (
        (
            "SUPPLIER NOMINAL STOCK ENVELOPE — AS SUPPLIED",
            region.xmin + 0.0033,
            region.ymax - 0.004,
        ),
        (
            "STOCK REFERENCES ONLY — NOT FINISHED DIMENSIONS\n"
            "FINISHED TRIM AND CHAMFER CONTROLS: SHEET 1",
            0.016,
            0.089,
        ),
    ):
        note = add_note(adapter, text, x, y)
        if note is None:
            raise RuntimeError("cannot label the supplier nominal stock envelope")
        notes.append((_early_bound(note, "INote"), text))
    return stock, refs, notes


def _verify_supplier_references(adapter, refs, stock):
    if len(refs) != 5:
        raise RuntimeError("counter anchor must retain all five supplier dimensions")
    if str(stock.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("source stock view lost its separate stock configuration")
    for annotation, contract, expected_entity in refs:
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        assert_supplier_reference_dimension(adapter, display, **contract)
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(
                f"{contract['label']}: supplier reference acquired a tolerance band"
            )
        if expected_entity is None:
            if str(native.FullName).split("@")[:2] != [
                contract["label"],
                SUPPLIER_STOCK_FEATURE,
            ]:
                raise RuntimeError(
                    f"{contract['label']}: source stock dimension changed its model attachment"
                )
        else:
            current = _early_bound(display.GetAnnotation(), "IAnnotation")
            entities = tuple(current.GetAttachedEntities3() or ())
            kinds = tuple(
                int(value) for value in (current.GetAttachedEntityTypes() or ())
            )
            if (
                len(entities) != 1
                or kinds != (46,)
                or not _is_same_attachment(
                    adapter, entities[0], expected_entity, "SILHOUETTE"
                )
            ):
                raise RuntimeError(
                    f"{contract['label']}: supplier eye reference moved to another contour"
                )


def _verify_supplier_layout(adapter, view_names, notes):
    """Read every source dimension/label after the final rebuild, without fitting."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name, name in view_names.items():
        if drawing.ActivateSheet(sheet_name) is not True:
            raise RuntimeError(f"cannot inspect supplier ink on {sheet_name}")
        sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
        properties = tuple(sheet.GetProperties2())
        region = sheet_drawable_region(
            adapter, sheet, width=float(properties[5]), height=float(properties[6])
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        cell = (
            region.xmin,
            0.094 if sheet_name == SHEET_NAMES[1] else 0.0651,
            region.xmax,
            region.ymax - (0.009 if sheet_name == SHEET_NAMES[1] else 0.0),
        )
        views = {
            view_name(adapter, view): _early_bound(view, "IView")
            for view in iter_views(adapter)
        }
        if name not in views:
            raise RuntimeError(f"{sheet_name}: supplier dimension view disappeared")
        view = views[name]
        view.UpdateViewDisplayGeometry()
        assert_supplier_view_fits(
            adapter, view, cell, label=f"counter anchor {sheet_name}"
        )
        if sheet_name == SHEET_NAMES[1]:
            for note, text in notes:
                annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
                bounds = _box(note.GetExtent(), label=text, kind="note")
                if int(annotation.OwnerType) != 1 or not _inside(bounds, border):
                    raise RuntimeError(
                        f"supplier stock label leaves the usable sheet: {text}"
                    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified anchor", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Stock Name",
        "Supplier",
        "Supplier SKUs",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="counter anchor stock package"
    )
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate finished counter anchor sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Counter Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-VN-001; McMaster-Carr 9490T1",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # Hidden lines removed: the helix's back side, dashed, told the machinist
    # nothing about a purchased thread and cluttered the cut end.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="finished overall and cut end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_dimension_callouts(adapter, annotations, CHAMFER_CALLOUT)
    _verify_controls(adapter, annotations)
    refs = _supplier_references(adapter, front)
    add_property_linked_note(adapter, "Supplier", 0.016, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Supplier SKUs", 0.080, 0.060, char_height=0.003)
    add_property_linked_note(adapter, "Stock Name", 0.016, 0.049, char_height=0.003)
    add_property_linked_note(adapter, "Isometric View Note", 0.275, 0.163)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.016, NOTES_Y, char_height=0.003
    )
    # Re-assert after annotating: a real mode change regenerates the edge set.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate counter anchor supplier stock sheet")
    stock, stock_refs, stock_notes = _supplier_stock_diagram(adapter)
    refs.extend(stock_refs)
    set_hidden_lines_removed(adapter, stock)
    supplier_views = {
        SHEET_NAMES[0]: view_name(adapter, front),
        SHEET_NAMES[1]: view_name(adapter, stock),
    }
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Counter Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: STOCK_SCALE},
        settled_checks=(
            lambda: _verify_controls(adapter, annotations),
            lambda: _verify_supplier_references(adapter, refs, stock),
            lambda: _verify_supplier_layout(adapter, supplier_views, stock_notes),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

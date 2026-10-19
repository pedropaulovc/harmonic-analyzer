"""Create the manufacturing drawing for the modified McMaster 9489T111 anchor.

The anchor is purchased by SKU but is NOT installed as supplied: the captive
hex nut is discarded (the MHA-CH-014 round jam nut locks it) and the shank is cut to
cross the summing-lever plate and carry that nut, so the sheet carries the
same two cutting controls as the counter anchor (``draw_boss_hook``) -- the
finished overall length to the eye crown and the restored 45 deg deburr at the
new end. The length band is the title block's; ``vn_spring_hook_spec`` shows
the shortest in-band part still keeps two full threads past the nut.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_vn_spring_hook.py vn-spring-hook
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note, curate_dimensions, dimension_name, iter_views, place_view, view_name,
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
from _drawing_edges import visible_view_entities
from _drawing_hidden_sketches import curate_view_dimensions as curate_stock_dimensions
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
    assert_supplier_reference_dimension, supplier_reference_dimension,
)
import _telemetry
from vn_spring_hook_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DIMENSION_TOLERANCE_TYPES,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    SUPPLIER_EYE_MM,
    SUPPLIER_REFERENCE_PRECISION,
    SUPPLIER_THREAD,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_STOCK_AXIS_MM,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_STOCK_DIMENSIONS,
    SUPPLIER_STOCK_FEATURE,
    SUPPLIER_STOCK_MM,
)

SPEC = DRAWINGS_BY_NAME["vn_spring_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
# The finished part is 31.3 x 12.7 mm since its shank carries the MHA-CH-014
# jam nut under the lever's spring pad: 5:1 keeps the front view inside the counter
# anchor's 4:1 sheet band, raised so the cut end's deburr dimensions clear
# the notes.  The deburr is dimensioned on the front view itself, as on the
# counter anchor: machinist review r7 found a 20:1 detail for a plain end
# chamfer added nothing a machinist needs.
SHEET_SCALE = (5.0, 1.0)
ISO_SCALE = (3.0, 1.0)
STOCK_SCALE = (5.0, 1.0)
SHEET_NAMES = ("FINISHED", "SUPPLIER-STOCK")
STOCK_CENTER = (0.150, 0.1755)
FRONT_CENTER = (0.100, 0.18625)
ISO_CENTER = (0.310, 0.213)
# The cut end sits about 0.078 below the view centre (half the 31.3 at 5:1);
# the centre rose 0.00475 with the 1.9 mm longer shank and 0.0015 more with
# the 0.6 mm the pad's thickest limit added (code review C10), so the end,
# its deburr dimensions and the notes keep their 28.8-era stations; the
# eye's top stands ~2 mm under the top border.
# The deburr's value and callout hang right of the shank, clear of their own
# extension lines (review r8: centred under the 2.3 mm leg they were struck)
# and above the notes.
FRONT_KEEP = {
    "FinishedOverall": (0.042, 0.18625),
    "ChamferWidth": (0.168, 0.100),
    "ChamferAngle": (0.124, 0.117),
}
# The deburr band is tighter than the title block on both sides (review r8
# read it as a plain lead-in): its minimum leg brings the cut end under the
# #6-32 tap drill so the cut thread starts in the lever's tap, and its
# maximum, at the steepest angle, is charged to the full threads the shank
# keeps past the jam nut.  The callout names both mates.
CHAMFER_CALLOUT = {
    "ChamferWidth": (
        "MIN: CUT END STARTS IN MHA-SM-003 TAP\nMAX: KEEPS FULL THREAD PAST MHA-CH-014"
    )
}
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


def _supplier_references(adapter: Any, front: Any) -> list[tuple[Any, dict[str, Any], Any]]:
    """Reference the unchanged eye contours and identify the surviving thread."""
    eye = {}
    thread = None
    refs = []
    for raw in visible_view_entities(front, 4, label="spring anchor supplier contours"):
        silhouette = _early_bound(raw, "ISilhouetteEdge")
        raw_curve = silhouette.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if curve.IsCircle():
            circle = tuple(float(value) for value in curve.CircleParams)
            if (
                any(abs(value) > 1e-8 for value in circle[:3])
                or abs(abs(circle[5]) - 1.0) > 1e-8
            ):
                continue
            for name, diameter in SUPPLIER_EYE_MM.items():
                if abs(circle[6] * 2000.0 - diameter) < 1e-5:
                    eye.setdefault(name, raw)
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
    for name, text_xy in (
        ("EyeOD", (0.169, 0.255)),
        ("EyeID", (0.165, 0.228)),
    ):
        if name not in eye:
            raise RuntimeError(f"{name}: unchanged spring eye has no circular silhouette")
        _select_view_entity(
            adapter, front, "SILHOUETTE", None, label=name, entity=eye[name]
        )
        display = adapter.currentModel.AddDiameterDimension2(*text_xy, 0.0)
        adapter.currentModel.ClearSelection2(True)
        if display is None:
            raise RuntimeError(f"{name}: cannot dimension the spring eye silhouette")
        contract = dict(
            label=name, expected_mm=SUPPLIER_EYE_MM[name], units="in",
            precision=SUPPLIER_REFERENCE_PRECISION[name], presentation="diameter",
        )
        supplier_reference_dimension(adapter, display, **contract)
        refs.append((
            _early_bound(display, "IDisplayDimension").GetAnnotation(), contract, eye[name]
        ))
    if thread is None:
        raise RuntimeError("spring anchor has no surviving supplier thread crest")
    add_attached_note(
        adapter,
        front,
        text=f"({SUPPLIER_THREAD} THREAD — SUPPLIER REF)",
        note_xy=(0.140, 0.175),
        label="spring anchor supplier thread",
        entity_type="SILHOUETTE",
        entity=thread,
        attached_to=thread,
    )
    return refs


def _supplier_stock_sheet(adapter):
    """Dimension the original bolt body, independently of the finished cut."""
    stock = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=STOCK_SCALE),
        "IView",
    )
    iso = _early_bound(
        place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE),
        "IView",
    )
    for view in (stock, iso):
        view.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("cannot rebuild the as-supplied spring anchor views")
    for view in (stock, iso):
        set_hidden_lines_removed(adapter, view)
    keep = {
        "SupplierStockShank": (0.105, 0.150),
        "SupplierStockThread": (0.210, 0.140),
        "SupplierStockOverall": (0.065, STOCK_CENTER[1]),
    }
    annotations = curate_stock_dimensions(
        adapter, stock, keep=keep, view_label="as-supplied original bolt dimensions",
        dimensions_by_feature=SUPPLIER_STOCK_DIMENSIONS,
    )
    midpoint = (
        0.0,
        (SUPPLIER_STOCK_AXIS_MM[0][1] + SUPPLIER_STOCK_AXIS_MM[-1][1]) / 2000.0,
        0.0,
    )
    projected = model_points_in_view(
        adapter, stock, [midpoint], label="original stock bolt centre"
    )[0]
    before = tuple(float(value) for value in stock.Position)
    stock.Position = double_array([
        before[0] + STOCK_CENTER[0] - projected[0],
        before[1] + STOCK_CENTER[1] - projected[1],
    ])
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("cannot centre the full original stock bolt")
    annotations = curate_dimensions(adapter, annotations, reposition=keep)
    refs = []
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        contract = dict(
            label=name, expected_mm=SUPPLIER_STOCK_MM[name], units="in",
            precision=SUPPLIER_REFERENCE_PRECISION[name],
            callout={
                "SupplierStockShank": "AS-SUPPLIED SHANK",
                "SupplierStockThread": "AS-SUPPLIED THREAD LENGTH",
                "SupplierStockOverall": "AS-SUPPLIED OVERALL",
            }[name],
        )
        supplier_reference_dimension(adapter, annotation.GetSpecificAnnotation(), **contract)
        refs.append((annotation, contract, None))
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter original stock sheet context for labels")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    notes = []
    for text, x, y in (
        (
            "AS-SUPPLIED EYEBOLT BODY — SUPPLIER REFERENCE",
            region.xmin + 0.0033, region.ymax - 0.004,
        ),
        (
            "SUPPLIED HEX NUT OMITTED FROM THIS BODY VIEW\n"
            "STOCK REFERENCES ONLY — FINISHED CUTTING CONTROLS: SHEET 1",
            0.016, 0.089,
        ),
        (f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}", 0.275, 0.163),
    ):
        note = add_note(adapter, text, x, y)
        if note is None:
            raise RuntimeError("cannot label the original supplier stock body")
        notes.append((_early_bound(note, "INote"), text))
    for view in (stock, iso):
        set_hidden_lines_removed(adapter, view)
    return stock, iso, refs, notes


def _verify_supplier_references(adapter, refs, stock_views):
    if len(refs) != 5:
        raise RuntimeError("spring anchor must retain all five supplier dimensions")
    for view in stock_views:
        if str(view.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
            raise RuntimeError("original stock view lost its separate configuration")
    for annotation, contract, expected_entity in refs:
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        assert_supplier_reference_dimension(adapter, display, **contract)
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{contract['label']}: supplier reference acquired a tolerance band")
        if expected_entity is None:
            if str(native.FullName).split("@")[:2] != [
                contract["label"], SUPPLIER_STOCK_FEATURE
            ]:
                raise RuntimeError(f"{contract['label']}: source stock dimension changed its model attachment")
        else:
            current = _early_bound(display.GetAnnotation(), "IAnnotation")
            entities = tuple(current.GetAttachedEntities3() or ())
            kinds = tuple(int(value) for value in (current.GetAttachedEntityTypes() or ()))
            if len(entities) != 1 or kinds != (46,) or not _is_same_attachment(
                adapter, entities[0], expected_entity, "SILHOUETTE"
            ):
                raise RuntimeError(f"{contract['label']}: supplier eye reference moved to another contour")


def _verify_supplier_layout(adapter, view_names, notes):
    """Read settled source ink and sheet labels against actual native borders."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    for sheet_name, names in view_names.items():
        if drawing.ActivateSheet(sheet_name) is not True:
            raise RuntimeError(f"cannot inspect supplier ink on {sheet_name}")
        sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
        properties = tuple(sheet.GetProperties2())
        region = sheet_drawable_region(
            adapter, sheet, width=float(properties[5]), height=float(properties[6])
        )
        border = (region.xmin, region.ymin, region.xmax, region.ymax)
        cell = (
            region.xmin, 0.094 if sheet_name == SHEET_NAMES[1] else 0.0651,
            region.xmax, region.ymax - (0.009 if sheet_name == SHEET_NAMES[1] else 0.0),
        )
        views = {view_name(adapter, view): _early_bound(view, "IView") for view in iter_views(adapter)}
        for name in names:
            if name not in views:
                raise RuntimeError(f"{sheet_name}: supplier dimension view disappeared")
            view = views[name]
            view.UpdateViewDisplayGeometry()
            assert_supplier_view_fits(adapter, view, cell, label=f"spring anchor {sheet_name}")
        if sheet_name == SHEET_NAMES[1]:
            for note, text in notes:
                annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
                bounds = _box(note.GetExtent(), label=text, kind="note")
                if int(annotation.OwnerType) != 1 or not _inside(bounds, border):
                    raise RuntimeError(f"original stock label leaves the usable sheet: {text}")



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
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="spring anchor stock package")
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("cannot activate finished spring anchor sheet")
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Channel Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-VN-012; McMaster-Carr 9489T111",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # Hidden lines removed: the helix's back side, dashed, told the machinist
    # nothing about a purchased thread and cluttered the cut end (review r7).
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="finished overall and cut end",
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
        adapter, "Manufacturing Notes", 0.016, 0.083, char_height=0.003
    )
    # Re-assert after annotating: a real mode change regenerates the edge set.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("cannot activate spring anchor supplier stock sheet")
    stock, stock_iso, stock_refs, stock_notes = _supplier_stock_sheet(adapter)
    refs.extend(stock_refs)
    supplier_views = {
        SHEET_NAMES[0]: (view_name(adapter, front),),
        SHEET_NAMES[1]: (view_name(adapter, stock), view_name(adapter, stock_iso)),
    }
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: STOCK_SCALE},
        settled_checks=(
            lambda: _verify_controls(adapter, annotations),
            lambda: _verify_supplier_references(adapter, refs, (stock, stock_iso)),
            lambda: _verify_supplier_layout(adapter, supplier_views, stock_notes),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

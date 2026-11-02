"""Create the manufacturing drawing for the modified McMaster 9489T111 anchor.

The anchor is purchased by SKU but is NOT installed as supplied: the captive
hex nut is discarded (the MHA-CH-14 round jam nut locks it) and the shank is cut to
cross the summing-lever plate and carry that nut, so the sheet carries the
same two cutting controls as the counter anchor (``draw_boss_hook``) -- the
finished overall length to the eye crown and the restored 45 deg deburr at the
new end. The sheet prints decimal inch (``drawing_unit: in``). The length band
is the title block's .XX; ``ch_vn_spring_hook_spec`` shows the shortest
in-band part still keeps two full threads past the nut.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_ch_vn_spring_hook.py ch-vn-spring-hook
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import iter_views, place_view, view_name

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
from _drawing_hidden_sketches import curate_view_dimensions as curate_stock_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _drawing_sheet_region import sheet_drawable_region
from _purchased_fastener_drawing import assert_supplier_view_fits
from _rebuild import active_configuration_name
from _part_properties import part_drawing_unit
from _supplier_dimensions import (
    assert_supplier_reference_dimension, supplier_reference_dimension,
)
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
import _stock_trim_drawing as trim_drawing
import _telemetry
from ch_vn_spring_hook_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_MM,
    CHAMFER_WIDTH_TOLERANCE_MM,
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DIMENSION_TOLERANCE_TYPES,
    FINISHED_OVERALL_MM,
    FINISHED_OVERALL_TOLERANCE_MM,
    REFERENCE_SKETCHES,
    SUPPLIER_REFERENCE_PRECISION,
    SUPPLIER_THREAD,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_THREAD_DIMENSIONS,
    SUPPLIER_THREAD_FEATURE,
    SUPPLIER_STOCK_CONFIGURATION,
)

SPEC = DRAWINGS_BY_NAME["ch_vn_spring_hook"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
# The finished part is 30.7 x 12.7 mm (1.21 in overall) since its shank carries
# the MHA-CH-14 jam nut under the coefficient plate: 5:1 keeps the front view
# inside the counter anchor's 4:1 sheet band, raised so the cut end's deburr
# dimensions clear the notes.  The deburr is dimensioned on the front view
# itself, as on the counter anchor: machinist review r7 found a 20:1 detail for
# a plain end chamfer added nothing a machinist needs.
SHEET_SCALE = (5.0, 1.0)
ISO_SCALE = (3.0, 1.0)
# The view centres on its outline. The settled 31.3 mm part (run 0c4519c5
# read y 0.1014..0.2711 at centre 0.18625, a 0.0848 half-height) stood centred
# at 0.1805 with its cut end at 0.1023; the 30.734 mm inch part is 2.83 mm
# shorter on the sheet, so the centre drops half that to keep the cut end, and
# every deburr placement below, where it was. Its outline then spans about
# 0.0957..0.2625, inside the B sheet's 12.7 mm top zone border (y 0.2667) and
# clear of the 0.0651 notes band.
FRONT_CENTER = (0.100, 0.1791)
ISO_CENTER = (0.310, 0.209)
# The settled isometric outline is 0.0543 half-height about its centre (run
# 80ff6d1a read y 0.1587..0.2673 at centre 0.213, 0.6 mm past the border);
# centred at 0.209 its top is 0.2633 and its bottom 0.1547.
# Deburr texts. The 45 deg angle's vertex is where the chamfer meets the cut
# end, (106.5, 103.2) mm; SolidWorks runs the angle's arc through its text and
# breaks it at the text box. Parked at radius 22.3 next to the 45 deg ray it
# sat on its own chamfer extension line and arc arrowhead (machinist b344192,
# rule 14), so the text is centred on the bisector (22.5 deg) at radius 26.
# Settled native ink (runs fa43a1a5, ae121732; run boxes at SolidWorks'
# widths): the 45 deg's arrowheads stand 3.6 and 4.8 mm off its text, its
# extension lines 6.0 and 7.2 mm, its lower arrowhead 4.5 mm off the width
# block, and no own line runs inside any control's text. The width block
# drops 2 mm (its MIN row stood 1.5 mm under that arrowhead) and still stands
# right of the shank, clear of its own extension lines (review r8: centred
# under the 2.3 mm leg they were struck) and ~6 mm above the notes. The
# shared layout audit, not a sheet check, guards the settled ink.
FRONT_KEEP = {
    "FinishedOverall": (0.042, FRONT_CENTER[1]),
    "ChamferWidth": (0.168, 0.098),
    "ChamferAngle": (0.1305, 0.1132),
}
# The deburr band is tighter than the title block on both sides (review r8
# read it as a plain lead-in): its minimum leg brings the cut end under the
# #6-32 tap drill so the cut thread starts in the lever's tap, and its
# maximum, at the steepest angle, is charged to the full threads the shank
# keeps past the jam nut.  The callout names both mates.
CHAMFER_CALLOUT = {
    "ChamferWidth": (
        "MIN: CUT END STARTS IN MHA-SM-03 TAP\nMAX: KEEPS FULL THREAD PAST MHA-CH-14"
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


def _verify_controls(annotations: list[Any]) -> None:
    trim_drawing.verify_machining_controls(
        annotations,
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )


def _supplier_references(adapter: Any, front: Any) -> list[tuple[str, dict[str, Any]]]:
    """The one sourcing reference: the #6-32 thread on its nominal-major carrier.

    A replacement anchor must take the lever's tap and the jam nut, so the
    thread is kept. The eye sizes and the as-supplied lengths are not
    replacement criteria -- the 0.66 spring wire links the 6.35 eye with ~10x
    margin, and the finished overall already fixes the length the stock must
    give -- and the SKU names the catalogue part.
    """
    refs = []
    annotations = curate_stock_dimensions(
        adapter, front, keep={"SupplierThreadMajor": (0.166, 0.175)},
        view_label="supplier thread nominal major, not helical geometry",
        dimensions_by_feature=SUPPLIER_THREAD_DIMENSIONS,
    )
    for annotation in annotations:
        contract = dict(
            label="SupplierThreadMajor", expected_mm=SUPPLIER_THREAD_MAJOR_MM,
            units="in", precision=SUPPLIER_REFERENCE_PRECISION["SupplierThreadMajor"],
            presentation="diameter",
            callout=f"{SUPPLIER_THREAD} THREAD\nNOMINAL MAJOR — SUPPLIER REF",
        )
        display = supplier_reference_dimension(
            adapter, annotation.GetSpecificAnnotation(), **contract
        )
        refs.append((str(_early_bound(display.GetDimension2(0), "IDimension").FullName), contract))
    return refs


def _verify_supplier_references(adapter, refs, view_names, configuration):
    """Resolve source coverage from freshly enumerated post-rebuild dimensions."""
    if len(refs) != 1:
        raise RuntimeError("spring anchor must retain its supplier thread dimension")
    views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
    for name in view_names:
        if name not in views or str(views[name].ReferencedConfiguration) != configuration:
            raise RuntimeError("supplier view lost its source configuration")
    view = views[view_names[0]]
    view.UpdateViewDisplayGeometry()
    displays = {}
    display = view.GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        key = str(native.FullName)
        if key in displays:
            raise RuntimeError(f"duplicate native dimension {key}")
        displays[key] = display
        display = display.GetNext5()
    if len(displays) != len(refs) + len(FRONT_KEEP):
        raise RuntimeError("settled native dimension coverage changed")
    for key, contract in refs:
        if key not in displays:
            raise RuntimeError(f"{contract['label']}: settled supplier dimension disappeared")
        display = displays[key]
        assert_supplier_reference_dimension(adapter, display, **contract)
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
            raise RuntimeError(f"{contract['label']}: supplier reference acquired a tolerance band")
        if str(native.FullName).split("@")[:2] != [contract["label"], SUPPLIER_THREAD_FEATURE]:
            raise RuntimeError(f"{contract['label']}: nominal model attachment changed")


def _verify_supplier_layout(adapter, view_names):
    """Inspect every view's settled native ink inside the usable sheet cell."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    cell = (region.xmin, 0.0651, region.xmax, region.ymax)
    views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
    for name in view_names:
        if name not in views:
            raise RuntimeError("supplier dimension view disappeared")
        view = views[name]
        view.UpdateViewDisplayGeometry()
        assert_supplier_view_fits(adapter, view, cell, label="spring anchor")


def _verify_source_state(adapter, source_model, finished_configuration):
    if active_configuration_name(adapter, source_model) != finished_configuration:
        raise RuntimeError("supplier drawing changed the source part's active configuration")
    part = _early_bound(source_model, "IPartDoc")
    for name in REFERENCE_SKETCHES:
        feature = part.FeatureByName(name)
        if feature is None or int(_early_bound(feature, "IFeature").Visible) != 1:
            raise RuntimeError(f"{name}: supplier drawing changed saved-hidden source visibility")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified anchor", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    finished_configuration = active_configuration_name(adapter, source_model)
    if not finished_configuration or finished_configuration == SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("source spring anchor is not saved in its finished configuration")
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
        adapter,
        property_view=SPEC.artifact_stem,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("ch-vn-spring-hook"),
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Channel Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-CH-VN-51; McMaster-Carr 9489T111",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        view = _early_bound(view, "IView")
        view.ReferencedConfiguration = finished_configuration
    # Hidden lines removed: the helix's back side, dashed, told the machinist
    # nothing about a purchased thread and cluttered the cut end (review r7).
    set_hidden_lines_removed(adapter, front)
    annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="finished overall and cut end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_precision(adapter, annotations, DIMENSION_PRECISION)
    set_dimension_callouts(adapter, annotations, CHAMFER_CALLOUT)
    _verify_controls(annotations)
    refs = _supplier_references(adapter, front)
    # Footer notes belong to the sheet. The curates leave the front view
    # active, and a note added there is view-owned ink its cell polices (the
    # Supplier row at y 0.060 sits below the 0.0651 cell floor).
    drawing = _early_bound(draw, "IDrawingDoc")
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter spring anchor sheet context for its notes")
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
    view_names = (view_name(adapter, front), view_name(adapter, iso))
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _verify_controls(annotations),
            lambda: _verify_supplier_references(
                adapter, refs, view_names, finished_configuration
            ),
            lambda: _verify_supplier_layout(adapter, view_names),
            lambda: _verify_source_state(adapter, source_model, finished_configuration),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

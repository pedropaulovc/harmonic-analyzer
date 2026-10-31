"""Create the manufacturing drawing for the modified McMaster 9490T1 anchor."""

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
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_reference_dimensions,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _drawing_sheet_region import sheet_drawable_region
from _purchased_fastener_drawing import _box, _inside, assert_supplier_view_fits
from _rebuild import active_configuration_name
from _supplier_dimensions import (
    assert_supplier_reference_dimension, supplier_reference_dimension,
)
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
import _stock_trim_drawing as trim_drawing
import _telemetry
from sm_vn_boss_hook_spec import (
    CHAMFER_ANGLE_DEG,
    CHAMFER_ANGLE_TOLERANCE_DEG,
    CHAMFER_WIDTH_DEVIATIONS,
    CHAMFER_WIDTH_MM,
    DIMENSION_PRECISION,
    DRAWING_DIMENSIONS,
    DIMENSION_TOLERANCE_TYPES,
    FINISHED_OVERALL_DEVIATIONS,
    FINISHED_OVERALL_MM,
    REFERENCE_SKETCHES,
    SUPPLIER_REFERENCE_PRECISION,
    SUPPLIER_STOCK_CONFIGURATION,
    SUPPLIER_THREAD,
    SUPPLIER_THREAD_MAJOR_MM,
    SUPPLIER_THREAD_DIMENSIONS,
    SUPPLIER_THREAD_FEATURE,
)

SPEC = DRAWINGS_BY_NAME["sm_vn_boss_hook"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = (2.0, 1.0)
# Bottom of the cell for settled view-owned ink (views, dimensions): 5 mm above
# the Supplier / Supplier SKUs footer row, whose text tops out at y 0.060. The
# footer notes are sheet-owned and checked against the sheet border instead.
INK_CELL_YMIN = 0.0651
# The jam-nut shank (#1189) is 3.8 longer, 15 mm on the sheet: the view sits
# high enough that the cut-end chamfer dimensions clear the notes below it.
FRONT_CENTER = (0.100, 0.175)
ISO_CENTER = (0.310, 0.213)
# The cut-end deburr is dimensioned on the 4:1 front view itself (its .04 leg
# prints 4 mm long); a magnified detail added nothing a machinist needs.
FRONT_KEEP = {
    "FinishedOverall": (0.040, 0.175),
    "ChamferWidth": (0.150, 0.089),
    "ChamferAngle": (0.132, 0.106),
}
# The lead-in carries the title block's band: even its short leg brings the cut
# end under the #25 tap drill, so the cut thread starts in the lever's tap.
# The callout names that mate.
CHAMFER_CALLOUT = {"ChamferWidth": "LEAD-IN TO MHA-SM-03 TAP"}
NOTES_Y = 0.076
EXPECTED_CONTROLS = {
    "FinishedOverall": (
        FINISHED_OVERALL_MM / 1000,
        FINISHED_OVERALL_DEVIATIONS[0] / 1000,
        FINISHED_OVERALL_DEVIATIONS[1] / 1000,
    ),
    "ChamferWidth": (
        CHAMFER_WIDTH_MM / 1000,
        CHAMFER_WIDTH_DEVIATIONS[0] / 1000,
        CHAMFER_WIDTH_DEVIATIONS[1] / 1000,
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
    """The thread is the one supplier reference: a hidden nominal-major carrier.

    With the finished trim and deburr controls, the #10-24 designation is what
    a replacement eyebolt must match. Eye and as-supplied stock sizes are
    catalogue facts of the listed SKU, not sizes this sheet controls.
    """
    annotations = curate_reference_dimensions(
        adapter, front, keep={"SupplierThreadMajor": (0.166, 0.170)},
        view_label="supplier thread nominal major, not helical geometry",
        dimensions_by_feature=SUPPLIER_THREAD_DIMENSIONS,
    )
    refs = []
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
    """Resolve the final views/dimensions afresh; never repair settled state."""
    if len(refs) != 1:
        raise RuntimeError("counter anchor must retain its one supplier thread reference")
    views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
    for name in view_names:
        if name not in views or str(views[name].ReferencedConfiguration) != configuration:
            raise RuntimeError("counter anchor view lost its finished source configuration")
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


def _verify_supplier_layout(adapter, view_names, notes):
    """View-owned ink in its cell; sheet-owned footer notes inside the border."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    cell = (region.xmin, INK_CELL_YMIN, region.xmax, region.ymax)
    views = {view_name(adapter, raw): _early_bound(raw, "IView") for raw in iter_views(adapter)}
    for name in view_names:
        if name not in views:
            raise RuntimeError("counter anchor dimension view disappeared")
        view = views[name]
        view.UpdateViewDisplayGeometry()
        assert_supplier_view_fits(adapter, view, cell, label="counter anchor finished sheet")
    border = (region.xmin, region.ymin, region.xmax, region.ymax)
    for property_name, note in notes:
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        if int(annotation.OwnerType) != 1:  # swAnnotationOwner_DrawingSheet
            raise RuntimeError(f"{property_name}: footer note is no longer sheet-owned")
        if not _inside(_box(note.GetExtent(), label=property_name, kind="note"), border):
            raise RuntimeError(f"{property_name}: footer note leaves the usable sheet")


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
        raise RuntimeError("source counter anchor is not saved in its finished configuration")
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
        unit=part_drawing_unit("sm-vn-boss-hook"),
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Counter Spring Anchor — Modified Stock Drawing",
            1: "Manufacturing controls for modified purchased stock",
            2: "Harmonic Analyzer Project",
            3: "MHA-SM-VN-50; McMaster-Carr 9490T1",
            4: "Native dimension-driven trim and end deburr",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        view = _early_bound(view, "IView")
        view.ReferencedConfiguration = finished_configuration
    # Hidden lines removed: the helix's back side, dashed, told the machinist
    # nothing about a purchased thread and cluttered the cut end.
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
    # active, and a note added there is view-owned ink that its cell polices.
    drawing = _early_bound(draw, "IDrawingDoc")
    drawing.ActivateView("")  # False is documented for sheet context.
    if drawing.GetEditSheet() is not True or drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot enter counter anchor sheet context for its notes")
    notes = [
        (name, _early_bound(add_property_linked_note(adapter, name, x, y, **text), "INote"))
        for name, x, y, text in (
            ("Supplier", 0.016, 0.060, {"char_height": 0.003}),
            ("Supplier SKUs", 0.080, 0.060, {"char_height": 0.003}),
            ("Stock Name", 0.016, 0.049, {"char_height": 0.003}),
            ("Isometric View Note", 0.275, 0.163, {}),
            ("Manufacturing Notes", 0.016, NOTES_Y, {"char_height": 0.003}),
        )
    ]
    # Re-assert after annotating: a real mode change regenerates the edge set.
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    view_names = (view_name(adapter, front), view_name(adapter, iso))
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Counter Spring Anchor — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _verify_controls(annotations),
            lambda: _verify_supplier_references(
                adapter, refs, view_names, finished_configuration
            ),
            lambda: _verify_supplier_layout(adapter, view_names, notes),
            lambda: _verify_source_state(adapter, source_model, finished_configuration),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

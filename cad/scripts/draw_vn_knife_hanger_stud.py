"""Create MHA-VN-024's modified-stock cut and inspection drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    set_view_position,
)

import _telemetry
from _check import check
from _com import _early_bound
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
from _drawing_notes import property_link
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from vn_knife_hanger_stud_spec import (
    CHAMFER_ANGLE,
    CATALOG_LENGTH,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    CHAMFER_WIDTH_TOLERANCE,
    DIMENSION_CALLOUTS,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    HEAD_AF,
    HEAD_H,
    HEAD_TOP_Y,
    LENGTH,
    SHANK_DIA,
    SUPPLIER_DRAWING_DIMENSIONS,
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_STOCK_CONFIGURATION,
    THREAD_LENGTH_MIN,
)

SPEC = DRAWINGS_BY_NAME["vn_knife_hanger_stud"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (2.0, 1.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
# Sheet metres. The Front view centres the part's Y box (tip Y=0 to head
# top), so the finished tip lands half the scaled part height below it.
FRONT_CENTER = (0.110, 0.170)
TIP_SHEET_Y = FRONT_CENTER[1] - HEAD_TOP_Y / 2 * _SHEET_PER_MODEL_MM
# The chamfer meets the tip face one leg inside the thread major radius.
_CHAMFER_VERTEX = (
    FRONT_CENTER[0] + (SHANK_DIA / 2 - CHAMFER_WIDTH) * _SHEET_PER_MODEL_MM,
    TIP_SHEET_Y,
)
_ANGLE_TEXT_RADIUS = 0.016
# The B-size inner border is 12.7 mm in from the sheet edge; the title block
# spans x >= 0.216 below y = 0.065.
FRONT_KEEP = {
    # Text and dimension line left of the head, the three callout lines (under
    # 72 mm wide) centred 6 mm inside the left border and 10 mm clear of the hex.
    "CutLength": (0.055, FRONT_CENTER[1]),
    # The text stands wholly above the tail's top extension line and right of
    # the shank, so neither extension line crosses "10.62 min." or its lines.
    "ThreadLengthMin": (0.170, TIP_SHEET_Y + 0.039),
    # Dimension line 6 mm under the chamfer leg; its text leaves on a leader.
    "ChamferWidth": (
        FRONT_CENTER[0] + (SHANK_DIA - CHAMFER_WIDTH) / 2 * _SHEET_PER_MODEL_MM,
        TIP_SHEET_Y - 0.006,
    ),
    # The native 45 degrees in the open wedge right of the tip: its arc and
    # extension lines stand 16 mm out on the angle's bisector, below the
    # tail's top extension line and left of its dimension line.
    "ChamferAngle": (
        _CHAMFER_VERTEX[0]
        + _ANGLE_TEXT_RADIUS * math.cos(math.radians(CHAMFER_ANGLE / 2)),
        _CHAMFER_VERTEX[1]
        + _ANGLE_TEXT_RADIUS * math.sin(math.radians(CHAMFER_ANGLE / 2)),
    ),
}
# The chamfer callout stands below-right of the tip, under the tail's lower
# extension line and right of the leg's own extension lines.
CHAMFER_TEXT_XY = (0.157, TIP_SHEET_Y - 0.014)
# The purchased-screw note flags the unmodified head: its leader lands on
# the head-top edge, the note stands up and right in the open field.
HEAD_PICK_MM = (HEAD_AF / 4, HEAD_TOP_Y, 0.0)
PURCHASED_NOTE_XY = (0.130, 0.240)
# Every view and the sheet are 2:1, so the title-block SCALE is the view
# scale and the isometric carries no scale label.
ISO_CENTER = (0.340, 0.135)
STOCK_CENTER = (0.270, 0.165)
# MHA-SM-000 cuts each bolt to its measured stack, so the native CutLength
# still drives the modelled trim but prints as the bracketed reference
# nominal; every other control keeps its native band.
REFERENCE_CONTROL = "CutLength"
REFERENCE_NOMINAL = LENGTH / 1000
EXPECTED_CONTROLS = {
    "ChamferWidth": (
        CHAMFER_WIDTH / 1000,
        -CHAMFER_WIDTH_TOLERANCE / 1000,
        CHAMFER_WIDTH_TOLERANCE / 1000,
    ),
    "ChamferAngle": (
        math.radians(CHAMFER_ANGLE),
        -math.radians(CHAMFER_ANGLE_TOLERANCE),
        math.radians(CHAMFER_ANGLE_TOLERANCE),
    ),
    "ThreadLengthMin": (THREAD_LENGTH_MIN / 1000, 0.0, 0.0),
}


def verify_cut_length_reference(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Prove the one reference CutLength; return the banded controls.

    The reference still drives the trim at its nominal, carries no band and
    prints bracketed at its native precision.
    """
    controls, references = [], []
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        (references if name == REFERENCE_CONTROL else controls).append(annotation)
    if len(references) != 1:
        raise RuntimeError(
            f"{REFERENCE_CONTROL}: expected one sheet dimension, found {len(references)}"
        )
    display = _early_bound(references[0].GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(dimension.DrivenState) != 2:
        raise RuntimeError(f"{REFERENCE_CONTROL}: no longer drives the modelled trim")
    if not math.isclose(float(dimension.SystemValue), REFERENCE_NOMINAL, abs_tol=1e-9):
        raise RuntimeError(f"{REFERENCE_CONTROL}: native dimension nominal changed")
    brackets = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    if int(tolerance.Type) != DIMENSION_TOLERANCE_TYPES[
        REFERENCE_CONTROL
    ] or brackets != ("(", ")"):
        raise RuntimeError(f"{REFERENCE_CONTROL}: reference display did not persist")
    if int(display.GetPrimaryPrecision2()) != DIMENSION_PRECISION[REFERENCE_CONTROL]:
        raise RuntimeError(f"{REFERENCE_CONTROL}: native display precision changed")
    return controls


def _add_supplier_references(adapter: Any, front: Any) -> dict[str, Any]:
    """Dimension surviving stock, never relabel the fitted under-head length."""
    flat = HEAD_AF / 2
    authored = {}
    # The hex's lower straight edges survive the corner trim. Its annular
    # top rim also survives the crown dish, so both head sizes remain actual
    # geometric dimensions rather than nominal-envelope stand-ins.
    rows = (
        (
            "SupplierHeadAF",
            (-flat, LENGTH + HEAD_H / 3, HEAD_AF / (2 * math.sqrt(3))),
            (flat, LENGTH + HEAD_H / 3, HEAD_AF / (2 * math.sqrt(3))),
            (0.110, 0.255),
            "horizontal",
        ),
        (
            "SupplierHeadHeight",
            (0.95 * flat, LENGTH, 0.0),
            (0.95 * flat, HEAD_TOP_Y, 0.0),
            (0.218, 0.216),
            "vertical",
        ),
    )
    for name, first, second, text_xy, orientation in rows:
        picks = model_points_in_view(
            adapter,
            front,
            [tuple(value / 1000 for value in point) for point in (first, second)],
            label=name,
        )
        # Coordinate-picked edges are verified by the exact measured nominal,
        # native type and non-dangling attachments in the supplier formatter.
        display = add_edge_dimension(
            adapter,
            front,
            p0=picks[0],
            p1=picks[1],
            text_xy=text_xy,
            label=name,
            orientation=orientation,
        )
        authored[name] = _format_supplier_reference(adapter, display, name)
    references = curate_view_dimensions(
        adapter,
        front,
        keep={"SupplierThreadMajor": (0.170, 0.194)},
        view_label="nominal supplier thread-major envelope",
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


def _format_supplier_reference(adapter: Any, display: Any, name: str) -> Any:
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    # No head or thread-major band appears on the source engineering drawing.
    supplier_reference_dimension(
        adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
    )
    if int(tolerance.Type) != 0:
        raise RuntimeError(f"{name}: an unsupported supplier band was added")
    return _early_bound(display.GetAnnotation(), "IAnnotation")


def _add_stock_reference(adapter: Any) -> tuple[Any, Any]:
    """Measure the original stock solid, clearly separate from the fitted bolt."""
    stock = place_view(adapter, str(SOURCE), "*Front", *STOCK_CENTER, scale=SHEET_SCALE)
    bound = _early_bound(stock, "IView")
    bound.ReferencedConfiguration = SUPPLIER_STOCK_CONFIGURATION
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("source-stock view did not rebuild")
    if str(bound.ReferencedConfiguration) != SUPPLIER_STOCK_CONFIGURATION:
        raise RuntimeError("source-stock view references the finished bolt")
    if not set_view_position(adapter, stock, *STOCK_CENTER):
        raise RuntimeError("cannot position source-stock view")
    set_hidden_lines_removed(adapter, stock)
    picks = model_points_in_view(
        adapter,
        stock,
        (
            (0.95 * HEAD_AF / 2000, LENGTH / 1000, 0.0),
            (0.0, (LENGTH - CATALOG_LENGTH) / 1000, 0.0),
        ),
        label="as-supplied under-head stock length",
    )
    display = add_edge_dimension(
        adapter,
        stock,
        p0=picks[0],
        p1=picks[1],
        text_xy=(0.236, 0.160),
        label="SupplierStockLength",
        orientation="vertical",
    )
    return stock, _format_supplier_reference(adapter, display, "SupplierStockLength")


def _assert_supplier_references(
    adapter: Any,
    references: dict[str, Any],
    stock: Any,
    finished_views: tuple[Any, ...],
) -> None:
    """Re-read every source reference after the final rebuild, before saving."""
    if set(references) != set(SUPPLIER_REFERENCE_DIMENSIONS):
        raise RuntimeError("supplier reference coverage changed before saving")
    if (
        str(_early_bound(stock, "IView").ReferencedConfiguration)
        != SUPPLIER_STOCK_CONFIGURATION
    ):
        raise RuntimeError("source-stock view lost its stock configuration")
    if any(
        str(_early_bound(view, "IView").ReferencedConfiguration)
        == SUPPLIER_STOCK_CONFIGURATION
        for view in finished_views
    ):
        raise RuntimeError("a finished view switched to source stock")
    for name, annotation in references.items():
        annotation = _early_bound(annotation, "IAnnotation")
        if int(annotation.Visible) != 1:
            raise RuntimeError(f"{name}: supplier reference is no longer visible")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        assert_supplier_reference_dimension(
            adapter, display, label=name, **SUPPLIER_REFERENCE_DIMENSIONS[name]
        )
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:
            raise RuntimeError(f"{name}: an unsupported supplier band was added")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open modified knife-hanger bolt", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Purchased Screw Note",
    )
    properties = read_required_properties(
        adapter.currentModel, required, required=required
    )
    draw, _sheet = new_project_drawing(
        adapter, property_view=SPEC.artifact_stem, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Knife-Hanger Bolt — Modified Stock Drawing",
            1: "Reference cut length, end chamfer and modified-part thread-tail acceptance",
            2: "Harmonic Analyzer Project",
            3: "MHA-VN-024; McMaster-Carr 92314A253",
            4: "Native reference cut length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The consumed deburr sketch and the hidden thread-tail acceptance sketch
    # both lie on the Front plane, so the main view carries every control.
    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="under-head length, cut-end chamfer and inspected thread tail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    verify_machining_controls(
        adapter,
        verify_cut_length_reference(adapter, annotations),
        expected=EXPECTED_CONTROLS,
        tolerance_types=DIMENSION_TOLERANCE_TYPES,
        precision=DIMENSION_PRECISION,
    )
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
    offset_dimension_text(adapter, annotations, {"ChamferWidth": CHAMFER_TEXT_XY})
    supplier_refs = _add_supplier_references(adapter, front)
    head_edge = model_point_in_view(
        adapter,
        front,
        tuple(value / 1000 for value in HEAD_PICK_MM),
        label="purchased hex head top edge",
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
    stock, stock_annotation = _add_stock_reference(adapter)
    supplier_refs["SupplierStockLength"] = stock_annotation
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Knife-Hanger Bolt — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_supplier_references(
                adapter, supplier_refs, stock, (front, iso)
            ),
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

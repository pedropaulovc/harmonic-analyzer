"""Create MHA-PD-VN-57's faced-to-fit stock drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

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
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_property_linked_callout
from _drawing_notes import property_link
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
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
    SKU,
    THREAD_LENGTH_MIN,
    THREAD_MAJOR,
    TIP_Y,
)

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_screw"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)
ISO_SCALE = SHEET_SCALE  # One-scale sheet: no per-view scale label.
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
            0: "Transgear Pivot Screw — Modified Stock Drawing",
            1: "Faced tip, end chamfer and modified-part thread-tail acceptance",
            2: "Harmonic Analyzer Project",
            3: f"MHA-PD-VN-57; McMaster-Carr {SKU}",
            4: "Native reference length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A new view may already appear shaded; force both to hidden lines removed
    # so the cosmetic thread prints at drawing quality.
    for view in (front, iso):
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
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pivot Screw — Modified Stock Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

"""Create MHA-PD-VN-57's altered-item drawing (ASME Y14.24 tier 3, #2886).

The part is McMaster-Carr 90325A174 with its threaded end faced and
chamfered to fit. The purchased note names the item it is made from; the
sheet dimensions only the alterations: the faced length (a reference, set at
fit-up by note 1), the end chamfer and the thread-tail acceptance, all
imported from the model's native dimensions. The unaltered head and shoulder
are the supplier's and carry no dimensions here.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
)

from _machinist_review_mode import MachinistReviewMode
import _config
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
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _part_properties import part_drawing_unit
from _session import run_build
from _stock_trim_drawing import verify_machining_controls
from pd_vn_transgear_pivot_screw_spec import (
    CHAMFER_ANGLE,
    CHAMFER_ANGLE_TOLERANCE,
    CHAMFER_WIDTH,
    DIMENSION_PRECISION,
    DIMENSION_TOLERANCE_TYPES,
    DRAWING_DIMENSIONS,
    FITTED_THREAD_LEN,
    HEAD_H,
    PRINTED_THREAD,
    SHOULDER_END_Y,
    SKU,
    THREAD_LENGTH_MIN,
    THREAD_MAJOR,
    TIP_RECESS,
    TIP_Y,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_screw"]
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SHEET_SCALE = (4.0, 1.0)  # One-scale sheet: no per-view scale label.
_SHEET_PER_MODEL_MM = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000
# Sheet metres. The Front view centres the part's Y box (faced tip to head
# top), so the tip lands half the scaled part height below it.
FRONT_CENTER = (0.140, 0.150)
ISO_CENTER = (0.360, 0.165)
TIP_SHEET_Y = FRONT_CENTER[1] - (HEAD_H - TIP_Y) / 2 * _SHEET_PER_MODEL_MM
SHOULDER_END_SHEET_Y = TIP_SHEET_Y + FITTED_THREAD_LEN * _SHEET_PER_MODEL_MM
# The chamfer meets the tip face one leg inside the thread major radius.
_CHAMFER_VERTEX = (
    FRONT_CENTER[0] + (THREAD_MAJOR / 2 - CHAMFER_WIDTH) * _SHEET_PER_MODEL_MM,
    TIP_SHEET_Y,
)
_ANGLE_TEXT_RADIUS = 0.010
FRONT_KEEP = {
    # Left of the thread, level with the span from the shoulder end to the tip.
    "CutLength": (0.115, (TIP_SHEET_Y + SHOULDER_END_SHEET_Y) / 2),
    # Right of the shank, above its top extension line.
    "ThreadLengthMin": (
        0.180,
        TIP_SHEET_Y + THREAD_LENGTH_MIN * _SHEET_PER_MODEL_MM + 0.016,
    ),
    # Dimension line 6 mm under the chamfer leg; its text leaves on a leader.
    "ChamferWidth": (
        FRONT_CENTER[0] + (THREAD_MAJOR - CHAMFER_WIDTH) / 2 * _SHEET_PER_MODEL_MM,
        TIP_SHEET_Y - 0.006,
    ),
    # The native 45 degrees in the open wedge right of the tip.
    "ChamferAngle": (
        _CHAMFER_VERTEX[0]
        + _ANGLE_TEXT_RADIUS * math.cos(math.radians(CHAMFER_ANGLE / 2)),
        _CHAMFER_VERTEX[1]
        + _ANGLE_TEXT_RADIUS * math.sin(math.radians(CHAMFER_ANGLE / 2)),
    ),
}
CHAMFER_TEXT_XY = (0.185, TIP_SHEET_Y - 0.018)
CUT_LENGTH_TEXT_XY = (0.062, (TIP_SHEET_Y + SHOULDER_END_SHEET_Y) / 2)
FIT_UP_NOTE = 1
_RECESS_TEXT = f"{TIP_RECESS[0] / 25.4:.3f}-{TIP_RECESS[1] / 25.4:.3f}".replace(
    "0.", "."
)
FIT_UP_NOTE_TEXT = (
    f"{FIT_UP_NOTE}. TIP FACED AT ASSEMBLY {_RECESS_TEXT} BELOW\n"
    f"    FRONT FACE OF SUPPORT BAR {_config.parts('pd-support-bar')['number']}."
)
DIMENSION_CALLOUTS = {
    "CutLength": f"SEE NOTE {FIT_UP_NOTE}",
    # The native ChamferAngle prints its own 45 degrees.
    "ChamferWidth": "CUT-END CHAMFER\nPAST THE THREAD ROOT",
    "ThreadLengthMin": (
        f"{PRINTED_THREAD} FROM FACED TIP\nINCOMPLETE THREAD AT TIP 1 PITCH MAX"
    ),
}
# Sheet notes in the open field left of the Front view; the title block spans
# x >= 0.216 below y = 0.065.
PURCHASED_NOTE_XY = (0.025, 0.215)
FIT_UP_NOTE_XY = (0.025, 0.058)
# The altered features re-read after the final rebuild. CutLength, the fit-up
# length, still drives the facing cut but prints as a reference.
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


def _verify_reference_length(annotation: Any) -> None:
    """The fit-up length prints "(.360)" with no band (rule 19)."""
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
    read_required_properties(adapter.currentModel, required, required=required)
    draw, _sheet = new_project_drawing(
        adapter,
        property_view=SPEC.artifact_stem,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("pd-vn-transgear-pivot-screw"),
    )
    stamp_drawing_summary(
        adapter,
        draw,
        {
            0: "Transgear Pivot Screw — Altered Item Drawing",
            1: "Faced tip, end chamfer and thread-tail acceptance",
            2: "Harmonic Analyzer Project",
            3: f"MHA-PD-VN-57; McMaster-Carr {SKU}",
            4: "Native reference length, chamfer and thread-tail controls",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The trim, deburr and hidden thread-tail sketches all lie on the Front
    # plane, so the main view carries every alteration.
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
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    offset_dimension_text(
        adapter,
        annotations,
        {"ChamferWidth": CHAMFER_TEXT_XY, "CutLength": CUT_LENGTH_TEXT_XY},
    )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.ActivateView("")
    if drawing.ActiveDrawingView is not None:
        raise RuntimeError("cannot leave view context for the sheet notes")
    add_property_linked_note(adapter, "Purchased Screw Note", *PURCHASED_NOTE_XY)
    if add_note(adapter, FIT_UP_NOTE_TEXT, *FIT_UP_NOTE_XY) is None:
        raise RuntimeError("fit-up note 1: InsertNote failed")

    def settled_controls() -> None:
        verify_machining_controls(
            [by_name[name] for name in EXPECTED_CONTROLS],
            expected=EXPECTED_CONTROLS,
            tolerance_types=DIMENSION_TOLERANCE_TYPES,
            precision=DIMENSION_PRECISION,
        )
        _verify_reference_length(by_name["CutLength"])

    settled_controls()
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pivot Screw — Altered Item Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(settled_controls,),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

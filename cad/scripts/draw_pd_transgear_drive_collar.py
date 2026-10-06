r"""Create the manufacturing drawing for the transgear drive collar (MHA-PD-022).

The end view is the ``*Back`` orientation, looking at the front (seat) face:
it carries the reamed bore and the two reamed drive-pin holes with their
offsets from the axis.  The side view is ``*Right``, looking along the rear
slot, so the slot shows as a notch in the rear face: the turned diameters,
both lengths from the seat face, the reference overall and the slot's width,
depth and centring print on it (policy rule 7); the end view's pin-hole
callout squares the slot to the pin-hole line.  Every feature is a plain
through bore, a turned step or the open slot, so no section is needed.  No
roughness symbol: the seat face is a clamp face (policy rule 5).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pd_paper_drive_assembly_steps import step_ref
from pd_transgear_drive_collar_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    LENGTH,
    OD,
    OVERALL_LENGTH,
    PILOT_DIA,
    PILOT_LENGTH,
    PILOT_LENGTH_CALLOUT,
    PIN_CIRCLE_RADIUS,
    PIN_HOLE_CALLOUT,
    SLOT_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["pd_transgear_drive_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# A Ø17.5 × 6.9 collar: 4:1 draws the Ø2.38 pin holes 9.5 mm across and the
# 1.8 slot 7.2 mm wide, and leaves room round both views for their callouts.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
END_CENTER = (0.100, 0.165)
SIDE_CENTER = (0.235, END_CENTER[1])
ISO_CENTER = (0.345, END_CENTER[1])
ISO_SCALE = (2, 1)
HALF_OD = OD * _S / 2000.0
HALF_PILOT = PILOT_DIA * _S / 2000.0
PIN_R = PIN_CIRCLE_RADIUS * _S / 1000.0
# *Right looks along -X: sheet right is model -Z, so the pilot stands right
# of the seat face and the body (with the rear slot) runs left.  The view is
# centred on the part's box, z -2.9..4.0.
_SEAT_X = SIDE_CENTER[0] + (LENGTH - PILOT_LENGTH) * _S / 2000.0
_REAR_X = _SEAT_X - LENGTH * _S / 1000.0
_PILOT_X = _SEAT_X + PILOT_LENGTH * _S / 1000.0
# The end view: the bore off the upper right and the pin holes off the lower
# right, each leader running straight in, the two pin offsets stacked left.
END_KEEP = {
    "BoreDia": (END_CENTER[0] + 0.030, END_CENTER[1] + HALF_OD + 0.012),
    "PinPosDia": (END_CENTER[0] + 0.030, END_CENTER[1] - HALF_OD - 0.012),
    "PinPosY": (END_CENTER[0] - HALF_OD - 0.012, END_CENTER[1] + PIN_R / 2.0),
    "PinNegY": (END_CENTER[0] - HALF_OD - 0.012, END_CENTER[1] - PIN_R / 2.0),
}
# The side view: both lengths from the seat face stacked below with the
# overall under them, the O.D. left of the rear face outside the slot width,
# the pilot right of its front face, the slot depth above its notch.  The
# pilot length reads innermost; its three-line fit callout hangs ~0.016
# below it, so the collar length and the overall step out past it.
SIDE_KEEP = {
    "PilotLength": ((_SEAT_X + _PILOT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.012),
    "CollarLength": ((_REAR_X + _SEAT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.036),
    # 0.040 left: at 0.032 the O.D.'s band touched the slot width's value.
    "CollarDia": (_REAR_X - 0.040, SIDE_CENTER[1]),
    "PilotDia": (_PILOT_X + 0.014, SIDE_CENTER[1]),
    "SlotDepth": (_REAR_X + 0.004, SIDE_CENTER[1] + HALF_OD + 0.012),
    "SlotWidth": (_REAR_X - 0.014, SIDE_CENTER[1]),
}
OVERALL_TEXT_XY = ((_REAR_X + _PILOT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.050)
# The overall's picks, pilot front face then rear face.  Each face's outer
# circle stands edge-on here, so it is a model EDGE; only the turned flanks
# are drawing silhouettes, and a SILHOUETTE pick on the rear face missed
# (run 20261001T142942518Z).  Half the pilot radius up: off the slot
# (half-width 0.9), inside the pilot (r 5.0), clear of the pin holes (r 5.81+).
_OVERALL_PICK_Y = SIDE_CENTER[1] + PILOT_DIA * _S / 4000.0
OVERALL_PICKS = ((_PILOT_X, _OVERALL_PICK_Y), (_REAR_X, _OVERALL_PICK_Y))
# The pilot is supplied long and faced at assembly; the sheet prints the
# fitted band and points at the assembly step that faces it.
FIT_STEP_KEY = "pilot-faced-to-fit"
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT,
    "PinPosDia": PIN_HOLE_CALLOUT,
    "PilotLength": f"{PILOT_LENGTH_CALLOUT},\nPER {step_ref(FIT_STEP_KEY)}",
}
# The slot's centring reads above its depth, clear of the side view.
DIMENSION_CALLOUTS_ABOVE = {"SlotDepth": SLOT_CALLOUT}
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
# Fifteen note lines from 0.085 end at 0.0175, above the border; the block's
# right edge (66 chars, 0.198) stays left of the side view's callouts.
NOTES_XY = (0.016, 0.085)


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """The above-callouts, refused if any holds a line break: SolidWorks keeps
    such text but never prints it (this sheet's two-line slot callout, run
    20261001T151531763Z), while one-line above callouts print."""
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


def _overall_reference(adapter: Any, side: Any) -> None:
    """The (6.9) overall, pilot front face to rear face (rule 7)."""
    label = "drive-collar overall length reference"
    display = add_edge_dimension(
        adapter,
        side,
        p0=OVERALL_PICKS[0],
        p1=OVERALL_PICKS[1],
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="horizontal",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_LENGTH) > 1e-4:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {OVERALL_LENGTH:g}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open drive collar source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Transgear Drive Collar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear drive collar; turned and reamed brass; rear slot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*end_annotations, *side_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )
    set_dimension_callouts(
        adapter,
        annotations,
        _printable_above_callouts(DIMENSION_CALLOUTS_ABOVE),
        location="above",
    )
    _overall_reference(adapter, side)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the collar end view")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Drive Collar Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

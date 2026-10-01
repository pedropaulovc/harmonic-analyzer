r"""Create the manufacturing drawing for the transgear drive collar (MHA-152).

The end view is the ``*Back`` orientation, looking at the front (seat) face:
it carries the O.D., the pilot, the reamed bore and the two reamed drive-pin
holes with their offsets from the axis.  The side view is ``*Right``,
looking along the rear slot, so the slot shows as a notch in the rear face
and its width and depth print on it beside the collar and pilot lengths.
Every feature is a plain through bore, a turned step or the open slot, so no
section is needed.  No roughness symbol: the seat face is a clamp face
(policy rule 5).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from transgear_drive_collar_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OD,
    PILOT_DIA,
    PILOT_LENGTH,
    PIN_CIRCLE_RADIUS,
    PIN_HOLE_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["transgear_drive_collar"]
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

# A Ø17.5 × 5.9 collar: 4:1 draws the Ø2.38 pin holes 9.5 mm across and the
# 1.7 slot 6.8 mm wide, and leaves room round both views for their callouts.
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
# centred on the part's box, z -1.9..4.0.
_SEAT_X = SIDE_CENTER[0] + (LENGTH - PILOT_LENGTH) * _S / 2000.0
_REAR_X = _SEAT_X - LENGTH * _S / 1000.0
_PILOT_X = _SEAT_X + PILOT_LENGTH * _S / 1000.0
# The end view: the O.D. and the pilot off the upper half, the bore and the
# pin holes off the lower half, the two pin offsets stacked left of it.
END_KEEP = {
    "CollarDia": (END_CENTER[0] + 0.030, END_CENTER[1] + HALF_OD + 0.012),
    "PilotDia": (END_CENTER[0] - 0.030, END_CENTER[1] + HALF_OD + 0.012),
    "BoreDia": (END_CENTER[0] + 0.030, END_CENTER[1] - HALF_OD - 0.012),
    "PinPosDia": (END_CENTER[0] - 0.030, END_CENTER[1] - HALF_OD - 0.012),
    "PinPosY": (END_CENTER[0] - HALF_OD - 0.012, END_CENTER[1] + PIN_R / 2.0),
    "PinNegY": (END_CENTER[0] - HALF_OD - 0.012, END_CENTER[1] - PIN_R / 2.0),
}
# The side view: the lengths stacked below, the slot's depth above its
# notch and its width left of the rear face.
SIDE_KEEP = {
    "PilotLength": ((_SEAT_X + _PILOT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.012),
    "CollarLength": ((_REAR_X + _SEAT_X) / 2.0, SIDE_CENTER[1] - HALF_OD - 0.026),
    "SlotDepth": (_REAR_X + 0.004, SIDE_CENTER[1] + HALF_OD + 0.012),
    "SlotWidth": (_REAR_X - 0.014, SIDE_CENTER[1]),
}
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT,
    "PinPosDia": PIN_HOLE_CALLOUT,
}
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
NOTES_XY = (0.016, 0.070)


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

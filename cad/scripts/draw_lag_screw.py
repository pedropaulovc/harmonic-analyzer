r"""Create the curated machinist drawing for the rocker-support hold-down screw.

Uniform fastener slice (see draw_fillister_screw.py): a profile side view
with the head height and under-head length, the thread designation
leadered to the shank and the axis centerline; a slot-profile (*Right) view
where the driver slot is a visible notch, carrying its width and depth; a
head-end view with the round head diameter (leader ending at the rim) and
a center mark; plus an isometric.  Authored on the Top plane (axis +Y)
with the head DOWN (head at y in [-HEAD_H, 0], shank rising to +SHANK_LEN),
so it stands VERTICAL in the profile view with the head at the bottom; the
head-end circle is seen from below in the *Bottom view.  The vertical
profile cannot point-select the edge-on shoulder/tip silhouettes, so the
two lengths ship as the head/shank extrude-DEPTH model dimensions
(HeadHt/ShankLg) inserted in the side view.
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
    add_view_centerline,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _fastener_annotations import (
    add_circle_center_mark,
    add_thread_leader,
    end_diameter_leaders_at_rim,
)
from lag_screw_spec import (
    HEAD_DIA,
    HEAD_H,
    SHANK_DIA,
    SHANK_LEN,
    SLOT_D,
    THREAD_DESIGNATION,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["lag_screw"]
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

# 9/16-12 x 63 mm: 2:1 draws the ~69 mm length as ~138 mm and the head OD (22)
# as ~44 mm.
SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Authored on the Top plane, axis +Y, HEAD DOWN: head at y in [-HEAD_H, 0]
# (bottom), shank at y in [0, SHANK_LEN] (top).  The head-end circle is seen in
# the *Bottom view; the profile (axis VERTICAL, head at bottom) in *Front; the
# slot notch (at the head's bottom face) in *Right, aligned with the profile.
# The profiles sit at 0.185 so the ~138 mm profile's tip (0.254) clears the
# sheet's zone border and its head (0.116) clears the note block at 0.100.
END_CENTER = (0.085, 0.180)
SIDE_CENTER = (0.190, 0.185)
RIGHT_CENTER = (0.285, 0.185)
ISO_CENTER = (0.370, 0.175)

_Y_MID = (SHANK_LEN - HEAD_H) / 2.0


def _side_y(model_y: float) -> float:
    return SIDE_CENTER[1] + (model_y - _Y_MID) * _S


_HEAD_END_Y = _side_y(-HEAD_H)  # head outer (driver) face (bottom)
_JUNCTION_Y = _side_y(0.0)  # head/shank step
_SHANK_END_Y = _side_y(SHANK_LEN)  # shank tip (top)
_HEAD_HALF = HEAD_DIA / 2.0 * _S
_SHANK_HALF = SHANK_DIA / 2.0 * _S
_SHANK_MID_Y = (_JUNCTION_Y + _SHANK_END_Y) / 2.0

# Head-end view: the head diameter leadered from upper-left, arrow on the near
# rim; center mark picked on the lower-right rim, clear of the slot lines.
END_DIM_X = 0.043
END_KEEP = {
    "HeadDia": (END_DIM_X, END_CENTER[1] + 0.030),
}
END_DIAMETERS = ("HeadDia",)
END_CENTER_MARK_XY = (
    END_CENTER[0] + _HEAD_HALF * 0.7071,
    END_CENTER[1] - _HEAD_HALF * 0.7071,
)
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: the head-height and under-head length as the extrude-depth model
# dims (the vertical profile cannot point-select the edge-on shoulder/tip).
SIDE_KEEP = {
    "HeadHt": (SIDE_CENTER[0] + 0.052, (_HEAD_END_Y + _JUNCTION_Y) / 2.0),
    "ShankLg": (SIDE_CENTER[0] + 0.052, _SHANK_MID_Y),
}
# Slot-profile view: the notch is in the head's BOTTOM face, so its width
# sits below the head and its depth to the right of the head.
SLOT_KEEP = {
    "SlotWidth": (RIGHT_CENTER[0], _HEAD_END_Y - 0.014),
    "SlotDepth": (RIGHT_CENTER[0] + _HEAD_HALF + 0.016, _HEAD_END_Y + SLOT_D * _S / 2.0),
}
# Thread designation: leader to the shank's left outline, text left of the
# profile (the dimensions live on the right).
THREAD_LEADER_XY = (SIDE_CENTER[0] - _SHANK_HALF, _SHANK_MID_Y)
THREAD_NOTE_XY = (SIDE_CENTER[0] - 0.066, _SHANK_MID_Y - 0.006)
SIDE_AXIS_FACE_XY = (SIDE_CENTER[0], _SHANK_MID_Y - 0.015)
SLOT_AXIS_FACE_XY = (RIGHT_CENTER[0], (_HEAD_END_Y + _JUNCTION_Y) / 2.0)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lag-screw source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Lag Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lag screw; slotted round-head screw; black steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(2, 1))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # Hidden lines ON in both orthographic profiles (policy rule 7): the slot
    # floor reads through the head in the front, the notch shows in the right.
    # The tiny end view keeps HLR -- the shank-behind-head circle would read
    # as a hole.
    set_hidden_lines_visible(adapter, side)
    set_hidden_lines_visible(adapter, right)
    set_hidden_lines_removed(adapter, iso)
    set_hidden_lines_removed(adapter, end)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="head-end"
    )
    set_dimension_callouts(adapter, end_annotations, DIMENSION_CALLOUTS)
    end_diameter_leaders_at_rim(
        adapter, end_annotations, END_DIAMETERS, label="head-end diameters"
    )
    add_circle_center_mark(
        adapter, end, edge_xy=END_CENTER_MARK_XY, label="head rim center mark"
    )

    # Side-view lengths: the head/shank extrude-depth model dims (HeadHt/ShankLg),
    # inserted and positioned to the right of the vertical profile.
    curate_view_dimensions(adapter, side, keep=SIDE_KEEP, view_label="side")
    add_view_centerline(
        adapter, side, face_xy=SIDE_AXIS_FACE_XY, label="screw axis centerline"
    )
    add_thread_leader(
        adapter,
        side,
        designation=THREAD_DESIGNATION,
        silhouette_xy=THREAD_LEADER_XY,
        note_xy=THREAD_NOTE_XY,
        label="shank thread designation",
    )

    curate_view_dimensions(adapter, right, keep=SLOT_KEEP, view_label="slot profile")
    add_view_centerline(
        adapter, right, face_xy=SLOT_AXIS_FACE_XY, label="slot-profile axis centerline"
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.100)
    add_property_linked_note(adapter, "End View Note", END_CENTER[0] - 0.020, 0.230)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lag Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

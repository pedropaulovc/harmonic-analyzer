r"""Create the curated machinist drawing for the clamp screw.

Uniform fastener slice (see draw_fillister_screw.py): a profile side view
with the head height, under-head length and the driver slot (visible as a
notch in the driver face) as inserted model dimensions, the thread
designation leadered to the shank and the axis centerline; a head-end view
with the head diameter (leader ending at the rim) and a center mark; plus
an isometric.  Built on the Front plane (axis +Z), so the profile lies
HORIZONTAL with the head at the right end.
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
from clamp_screw_spec import (
    HEAD_DIA,
    HEAD_H,
    SHANK_DIA,
    SHANK_LEN,
    SLOT_D,
    THREAD_DESIGNATION,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["clamp_screw"]
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

# #8-32 x 28 mm: 4:1 draws the ~30.5 mm length as ~122 mm and the head OD (8)
# as ~32 mm.
SHEET_SCALE = (4.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm
# Built on the Front plane, axis +Z: head at z in [-HEAD_H, 0], shank at
# z in [0, SHANK_LEN].  Head-end circle in the *Back view; profile (axis
# HORIZONTAL) in the *Right view, which MIRRORS z (driver face at HIGH-x,
# shank tip at LOW-x).  The isometric sits right of the slot-width text.
END_CENTER = (0.065, 0.150)
SIDE_CENTER = (0.190, 0.190)
ISO_CENTER = (0.335, 0.180)

_Z_MID = (SHANK_LEN - HEAD_H) / 2.0


def _side_x(model_z: float) -> float:
    return SIDE_CENTER[0] + (_Z_MID - model_z) * _S


_DRIVER_FACE_X = _side_x(-HEAD_H)  # head outer (driver) face, right end
_JUNCTION_X = _side_x(0.0)  # head/shank step
_TIP_X = _side_x(SHANK_LEN)  # shank tip, left end
_HEAD_HALF = HEAD_DIA / 2.0 * _S
_SHANK_HALF = SHANK_DIA / 2.0 * _S
_SHANK_MID_X = (_JUNCTION_X + _TIP_X) / 2.0

# Head-end view: the head diameter leadered from upper-left, arrow on the near
# rim; center mark picked on the lower-right rim, clear of the slot lines.
END_KEEP = {
    "HeadDia": (0.028, END_CENTER[1] + 0.024),
}
END_DIAMETERS = ("HeadDia",)
END_CENTER_MARK_XY = (
    END_CENTER[0] + _HEAD_HALF * 0.7071,
    END_CENTER[1] - _HEAD_HALF * 0.7071,
)
DIMENSION_CALLOUTS: dict[str, str] = {}

# Side view: head height above the head, under-head length below the shank,
# slot width as a vertical across the driver-face notch (text right of the
# head) and slot depth as a horizontal below the head.
SIDE_KEEP = {
    "HeadHt": ((_DRIVER_FACE_X + _JUNCTION_X) / 2.0, SIDE_CENTER[1] + _HEAD_HALF + 0.014),
    "ShankLg": (_SHANK_MID_X, SIDE_CENTER[1] - _HEAD_HALF - 0.024),
    "SlotWidth": (_DRIVER_FACE_X + 0.018, SIDE_CENTER[1]),
    "SlotDepth": (_DRIVER_FACE_X - SLOT_D * _S / 2.0, SIDE_CENTER[1] - _HEAD_HALF - 0.012),
}
# Thread designation: a leader to the shank's upper outline, text upper-left
# of the profile, clear of the head-height dimension.
THREAD_LEADER_XY = (_SHANK_MID_X, SIDE_CENTER[1] + _SHANK_HALF)
THREAD_NOTE_XY = (SIDE_CENTER[0] - 0.050, SIDE_CENTER[1] + _HEAD_HALF + 0.016)
SIDE_AXIS_FACE_XY = (_SHANK_MID_X, SIDE_CENTER[1])


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open clamp-screw source", await adapter.open_model(str(SOURCE)))
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
            0: "Clamp Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "clamp screw; slotted machine screw; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    # Hidden lines ON in the profile (policy rule 7).  The tiny end view keeps
    # HLR -- the shank-behind-head circle would read as a hole.
    set_hidden_lines_visible(adapter, side)
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

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.115)
    add_property_linked_note(adapter, "End View Note", END_CENTER[0] - 0.018, 0.200)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Clamp Screw Manufacturing Drawing",
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

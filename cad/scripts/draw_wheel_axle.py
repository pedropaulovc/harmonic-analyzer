r"""Create the curated machinist drawing for the magnifying-wheel axle."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    auto_center_marks,
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from wheel_axle_spec import (
    COLLAR_DIA,
    FLANGE_DIA,
    FLANGE_LEN,
    STUD_DIA,
    STUD_LEN,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["wheel_axle"]
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

SHEET_SCALE = (3.0, 1.0)
_K = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters
END_VIEW_SCALE = (2.0, 1.0)
_END_K = END_VIEW_SCALE[0] / END_VIEW_SCALE[1] / 1000.0
_TOTAL_LEN = FLANGE_LEN + STUD_LEN

# Front view: the profile (axle axis vertical, flange at the bottom).
# End view: the tip-side circles, third-angle above the front view.
FRONT_CENTER = (0.105, 0.100)
# The O35 flange at the sheet's 3:1 scale leaves no room for SolidWorks' default
# O5/O9/O35 dimension text above it. Keep the third-angle centreline alignment,
# but use a precomputed 2:1 end-view scale so the default callouts stay on-sheet.
END_CENTER = (0.105, 0.190)
ISO_CENTER = (0.310, 0.185)


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _TOTAL_LEN / 2.0) * _K


FRONT_KEEP = frozenset({"FlangeLength", "StudLength", "CollarLength"})
END_KEEP = frozenset({"FlangeDia", "CollarDia", "StudDia"})
# The magnifying wheel's O5 bore rides the stud: unilateral-minus keeps a
# 0.02..0.05 running clearance against the nominal-on-nominal bore.
DIMENSION_CALLOUTS = {"StudDia": "-0.02/-0.05"}

# Datum B's symbol offset from the end-view centre, and the clock position that
# offset implies. The two MUST stay in sync: a datum tag on a circle re-attaches
# at the point nearest its symbol, so a pick whose clock position disagrees with
# the symbol direction makes symbol_xy inert and collapses the tag toward the
# circle (see the note at the add_datum_feature call below). Deriving the angle
# from the offset keeps them from drifting apart in a later edit.
_DATUM_B_OFFSET = (0.038, -0.052)
_DATUM_B_ANGLE = math.atan2(_DATUM_B_OFFSET[1], _DATUM_B_OFFSET[0])


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Wheel Axle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel axle; flanged stud; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=END_VIEW_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    # The O5 stud hides under the O9 collar from the tip side; show it greyed
    # so its diameter and GD&T attach to a real circle.

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *end_annotations], DIMENSION_CALLOUTS
    )
    if not auto_center_marks(adapter, end, holes=True):
        raise RuntimeError("failed to add ASME center marks to axle end view")

    flange_face_edge = (
        FRONT_CENTER[0] + FLANGE_DIA / 4.0 * _K,
        _front_y(0.0) - 0.00025,
    )
    stud_circle_top = (
        END_CENTER[0],
        END_CENTER[1] + STUD_DIA / 2.0 * _END_K,
    )
    collar_circle_left = (
        END_CENTER[0] - COLLAR_DIA / 2.0 * _END_K,
        END_CENTER[1],
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=flange_face_edge,
        symbol_xy=(
            FRONT_CENTER[0] + FLANGE_DIA / 4.0 * _K + 0.006,
            _front_y(0.0) - 0.016,
        ),
        datum="A",
        label="flange seating face",
    )
    # Picked at datum B's OWN clock position, not at 3 o'clock. A datum tag is
    # PINNED to the entity it attaches to -- on a circle that is the
    # circumference, so it re-attaches at the point nearest the symbol and
    # symbol_xy goes INERT (the draw_fulcrum_shaft.py finding). Picking 3 o'clock
    # while the symbol sits at -53.8 deg left this tag half-collapsed toward the
    # circle: measured, it rendered at r=0.047 instead of the requested r=0.0645,
    # dragging its box back to x 0.1349..0.1420, y 0.1723..0.1793 -- straight onto
    # the O35 dimension. That is easy to misread as the O5.00 (whose text is right
    # there); it is not. The O35 is DIAMETRAL, so its line runs from its text at
    # upper-left THROUGH the centre and out to its arrowhead on the flange arc in
    # THIS lower-right sector, 100 mm from its own text: measured as the ray
    # x = 0.105 + 1.2542*(0.208 - y) (cotangent constant to 3 decimals over 5
    # scanlines, and it terminates exactly on the arc at r=0.0525). It clipped the
    # box's top-right corner by 0.6 mm. The O5.00 is the ray at cot 1.6126 and
    # never reaches this box.
    #
    # Matching the pick to the symbol's clock position lets the leader run
    # radially out and symbol_xy be honoured -- the draw_pivot_bushing.py datum-A
    # spelling (12-o'clock pick, 12-o'clock symbol, clean radial leader). Honoured
    # at r=0.0645 the box clears the O35 ray by >=9.8 mm and the O5.00 text by
    # 14 mm. Its leader crosses the flange arc once, which is inherent to reaching
    # a concentric inner circle and is what the O9/O5/runout leaders already do.
    stud_circle_at_datum_b = (
        END_CENTER[0] + STUD_DIA / 2.0 * _END_K * math.cos(_DATUM_B_ANGLE),
        END_CENTER[1] + STUD_DIA / 2.0 * _END_K * math.sin(_DATUM_B_ANGLE),
    )
    add_datum_feature(
        adapter,
        end,
        edge_xy=stud_circle_at_datum_b,
        symbol_xy=(
            END_CENTER[0] + _DATUM_B_OFFSET[0],
            END_CENTER[1] + _DATUM_B_OFFSET[1],
        ),
        datum="B",
        label="stud bearing axis",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=stud_circle_top,
        # +0.052 in y put the frame's 8 mm half-box 8.3 mm over the top margin.
        # Held to +0.045 (box top ~0.261) and pushed out to +0.058 in x, which
        # keeps it clear of the flange circle (52.5 mm radius) without reaching
        # the 0.4191 right margin.
        #
        # STALE ARITHMETIC, placement still good: the "8 mm half-box" was the
        # audit's old model. An FCF's anchor is its frame's TOP-LEFT corner, so
        # it reaches only ~0.1 mm ABOVE the anchor (and ~7.0 mm below) -- the top
        # overrun that forced this move was never real. Kept as-is because the
        # placement is fine and re-tuning costs a COM rebuild for nothing. The
        # direction that DOES bite is the RIGHT: the frame grows right by its
        # full width (20-30 mm, not 8), which is what put platen_guide's frame
        # over the right margin. That is why the x note above still matters.
        frame_xy=(END_CENTER[0] + 0.058, END_CENTER[1] + 0.045),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        diameter=True,
        label="stud perpendicular to seating face",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=collar_circle_left,
        frame_xy=(END_CENTER[0] - 0.075, END_CENTER[1] - 0.045),
        characteristic="circular_runout",
        tolerance="0.05",
        datums=("B",),
        label="collar runout on the stud",
    )
    # The stud OD is dimensioned in the end view, but its Ra belongs on the
    # FRONT view. The symbol's TEXT renders ABOVE its arm (ASME Y14.36) and runs
    # ~13..39 mm to the RIGHT of the anchor, so in the end view it cannot clear
    # the O35 flange circle at ANY height the 12.7 mm left margin allows -- the
    # arc reaches x=0.0534 at bore height while the text would need to stop by
    # x=0.0144 -- and it printed over the arc. (The audit cannot catch that: it
    # boxes the symbol as a nominal square about its anchor.) On the profile the
    # stud's left flank has ~45 mm of empty sheet beside it, which takes the
    # short, roughly horizontal leader this symbol wants.
    stud_flank_y = _front_y(FLANGE_LEN + STUD_LEN / 2.0)
    add_surface_finish(
        adapter,
        front,
        # A cylinder's side outline is a SILHOUETTE, not a model edge.
        edge_xy=(FRONT_CENTER[0] - STUD_DIA / 2.0 * _K, stud_flank_y),
        # Text lands at x~0.058..0.084: clear of the stud flank (x=0.0975) and
        # of the O9 collar (x>=0.0915), which starts a further 9 mm up.
        symbol_xy=(0.045, stud_flank_y),
        roughness_ra="1.6",
        label="stud bearing finish",
        entity_type="SILHOUETTE",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.048)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Axle Manufacturing Drawing",
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

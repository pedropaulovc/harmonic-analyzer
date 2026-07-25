r"""Create the curated machinist drawing for the pen square rod."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    auto_center_marks,
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
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
from pen_rod_spec import ROD_LENGTH, WIRE_HOLE_DIA, WIRE_HOLE_Y
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_rod"]
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

SHEET_SCALE = (1.0, 1.0)
TOP_VIEW_SCALE = 4.0
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.140, 0.150)
TOP_CENTER = (0.070, 0.245)
ISO_CENTER = (0.340, 0.195)

FRONT_KEEP = frozenset({"Length", "Section"})
TOP_KEEP = frozenset({"Depth"})
# No-oversize on BOTH functional slide faces: Section (front, X width) and Depth
# (top, Z width) are the two 5 mm faces the rod rides on in the v-block, so each
# is controlled +0.00/-0.05 rather than leaning on the general SECTION +/-0.05.
DIMENSION_CALLOUTS = {"Section": "+0.00/-0.05"}
TOP_DIMENSION_CALLOUTS = {"Depth": "+0.00/-0.05"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-rod source", await adapter.open_model(str(SOURCE)))
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
            "Top View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Top View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen rod; square brass slide rod; wire hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, top_annotations, TOP_DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True):
        raise RuntimeError("failed to add ASME center mark to the wire hole")

    front_bottom = (FRONT_CENTER[0], FRONT_CENTER[1] - ROD_LENGTH / 2000.0)
    front_side = (FRONT_CENTER[0] - 0.0025, FRONT_CENTER[1])
    front_far_side = (FRONT_CENTER[0] + 0.0025, FRONT_CENTER[1])
    hole_center_y = front_bottom[1] + WIRE_HOLE_Y / 1000.0
    hole_bottom = (FRONT_CENTER[0], hole_center_y - WIRE_HOLE_DIA / 2000.0)
    hole_side = (FRONT_CENTER[0] + WIRE_HOLE_DIA / 2000.0, hole_center_y)

    add_edge_dimension(
        adapter,
        front,
        p0=front_bottom,
        p1=hole_bottom,
        text_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] + 0.030),
        label="wire-hole length location",
    )
    # Locate the wire hole ACROSS the square section too: the native callout gives
    # only the drill size, so without this the cross-hole could sit off-centre and
    # still satisfy every shown dimension. Left slide face -> hole (line-to-circle,
    # so the value is to the hole centre) reads 2.50 of the 5.00 section = centred.
    add_edge_dimension(
        adapter,
        front,
        p0=front_side,
        p1=hole_side,
        text_xy=(FRONT_CENTER[0] - 0.030, hole_center_y + 0.020),
        label="wire-hole centerline location",
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=hole_side,
        callout_xy=(FRONT_CENTER[0] + 0.034, hole_center_y + 0.017),
        label="pen-rod wire hole",
    )

    add_datum_feature(
        adapter,
        front,
        edge_xy=front_side,
        symbol_xy=(front_side[0] - 0.016, FRONT_CENTER[1] - 0.030),
        datum="A",
        label="pen-rod slide face",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=front_far_side,
        frame_xy=(FRONT_CENTER[0] + 0.032, FRONT_CENTER[1] - 0.018),
        characteristic="parallelism",
        tolerance="0.03",
        datums=("A",),
        label="pen-rod opposite slide face parallelism",
    )
    # BELOW the rod, not right of it. At (+0.032, -0.042) the frame sat up-right
    # of its own target, so its leader descended left to the rod's bottom corner
    # and crossed the Ra's leader -- which rises from its symbol right of the rod
    # up-left to the slide face -- in an X at (0.0802, 0.0958). Opposite diagonals
    # through one corner. (The Ra comment below documents why the Ra cannot move:
    # its target must sit on the slide face, so passing UNDER the frame's terminus
    # puts it off the face and passing OVER drives it through the frame's box.)
    #
    # So the frame moves. Measured against the live leader geometry: the Ra's
    # leader runs (0.1637, 0.0680) -> (0.0675, 0.1001), i.e. y = 0.0869..0.0976
    # across this box's x span, clearing its top (0.080) by 6.9 mm. The box also
    # clears the Section dim's text (ends x=0.0483) by 26.7 mm, the notes
    # (top y=0.0628) by 10.2 mm, and the right view (y>=0.090, x>=0.137) entirely.
    # Its leader now approaches the rod's bottom from BELOW, so the two run on
    # opposite sides of the corner instead of through each other.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=front_bottom,
        frame_xy=(FRONT_CENTER[0] + 0.005, FRONT_CENTER[1] - 0.070),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="pen-rod bottom end squareness",
    )
    # Sits RIGHT of the rod and BELOW the right view, reaching back up-left to the
    # slide face. At (0.0415, 0.165) the body printed "Ra 1.6" straight across the
    # rod, which is only 5 mm wide at 1:1 and sits at x 0.0675..0.0725.
    #
    # The symbol may not go LEFT of the rod, even though that corner is empty: the
    # leader leaves the ▽ tip AT the anchor and the ~46 mm body draws up-RIGHT of
    # it (text at x+0.013..x+0.039, y+0.010..y+0.017), so a target up-right forces
    # the leader to thread between the ▽ and its own text -- steeper than the ▽'s
    # ~1.8 flank slope is drawn through the glyph, shallower than ~1.9 clips the
    # text. That window is empty in practice: a 1.5 slope still grazed the "R".
    # Anchoring right of the rod puts the target up-LEFT instead, so the leader
    # runs away from the body and the constraint disappears.
    #
    # y=0.068 keeps the run under the right view (its box starts at y=0.090, and a
    # leader through a view it does not annotate fails the crossing gate) and above
    # the notes at y<=0.062; it also passes below the 115.00 line and the squareness
    # frame, both of which start at y>=0.095.
    add_surface_finish(
        adapter,
        front,
        edge_xy=(front_side[0], FRONT_CENTER[1] - 0.050),
        symbol_xy=(0.170, 0.068),
        roughness_ra="1.6",
        label="pen-rod slide face finish",
    )

    # 0.015 -- centred in the corridor. The tight window is REAL: this note is
    # 246.2 mm of text in a 251.2 mm corridor, bounded at BOTH ends, so 0.020 (the
    # safe anchor on every other sheet) drives the tail into the title block.
    #
    # ALL NUMBERS BELOW ARE MEASURED ON THE REBUILT 2026-07-16 SHEET, black-ink
    # only (threshold 200 sees the gray frame rule too; the note is black, the rule
    # is gray, and they are 0.6 mm apart -- only the black/gray split separates
    # them, an ALL-ink bbox reads the rule as the note's first glyph). Note ink at
    # anchor 0.013 measured x 0.0134..0.2596, i.e. ink_start = anchor + 0.0004.
    #
    # The bounds, tighter of drawn-vs-gated on each side:
    #     left   drawn rule right edge 0.0128 | gate bound (12.7 zone margin) 0.0127
    #     right  drawn title block     0.2658 | gate bound _TITLE_BLOCK_LEFT_M 0.264
    # so the governing corridor is 0.0128 -> 0.264 = 251.2 mm, slack 5.0 mm, and
    # centring puts ink at 0.0154..0.2616: 2.6 mm off the drawn rule, 2.4 mm off
    # the gate's keep-out, 4.2 mm off the drawn block. At the previous 0.013 the
    # note cleared both ends but sat 0.6 mm off the left rule with 6.2 mm unused on
    # the right -- legal, but visually jammed and inside render noise of touching.
    #
    # THE TITLE BLOCK DID NOT TRANSLATE WITH THE FRAME, and that is the whole
    # story here. A superseded comment predicted the tail would overrun the block
    # by ~0.1 mm, reasoning that the block is format geometry that moved with the
    # re-centred frame (keep-out 0.2672 -> ~0.2640, corridor MOVED not widened).
    # The block stayed put. Proof, measured: the block's horizontal cell rules
    # still run out to x=0.4223 -- exactly where the OLD right frame rule sat
    # (0.4221..0.4225) -- while the frame's right rule is now at 0.4188..0.4192.
    # The rules moved inward ~3.3 mm; the block did not follow AT FIRST, so it
    # protruded past the frame -- a template defect since FIXED (Codex #334): the
    # DRWDOT title-block right rules were re-anchored inward onto the frame
    # border. Measured on the current render, the frame's right rule and the
    # block's right rule now COINCIDE at x=0.4189 (both 0.4188..0.4192), no
    # protrusion. The note corridor is governed by the block's LEFT edge
    # (0.2658), which did not move, so this placement is unchanged; the corridor
    # WIDENED rather than moved:
    #     old  0.2658 - 0.0159 = 249.9 mm
    #     now  0.2658 - 0.0126 = 253.2 mm
    # which is the ~3.3 mm of new room the ORIGINAL comment claimed and the
    # superseded one denied.
    #
    # The 0.2672 in that superseded comment was NOT an error: the block's leftmost
    # BLACK TEXT measures 0.2675 (its outer RULE is 0.2658). Both are real bounds;
    # text is the tighter keep-out for a note on this y band. Do not "correct" it
    # to the rule. (It is also within 0.3 mm of the old TOP rule's y=0.2672 --
    # a coincidence that makes an axis-confusion story look compelling and wrong.)
    #
    # It cannot move UP: the band above is the Ra body, the Section callout, then
    # the view. 5 mm of slack on a 246 mm note is fragile by construction and no
    # anchor fixes that; shortening the "Manufacturing Notes" property is the only
    # durable answer, and that is a content call.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.015, 0.058)
    add_property_linked_note(adapter, "Top View Note", 0.036, 0.266)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Rod Manufacturing Drawing",
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

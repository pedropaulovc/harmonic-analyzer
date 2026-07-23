r"""Create the curated machinist drawing for the alignment-pinion arbor."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_arbor_spec import CAP_R, CAP_SAG, SHAFT_DIA, SHAFT_LEN
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
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
END_VIEW_SCALE = 2.0
# The part spans z 0..SHAFT_LEN+CAP_SAG (shaft + crown), so the side view is
# OVERALL_LEN wide on the 1:1 sheet and its outline centre is the mid-span.
OVERALL_LEN = SHAFT_LEN + CAP_SAG
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + OVERALL_LEN * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
# 226-long arbor: a 1:1 isometric would run off the ASME B sheet, so 1:2.
# NOT (0.377, 0.205): even at 1:2 the iso is ~86 x 52, so up there it overran
# the right zone margin (the border gate measured 2.1 mm) and crowded the side
# view's right end. The empty band below the side view and right of the notes
# block takes it whole, clear of the 226.25 dimension line at y=0.180.
ISO_CENTER = (0.345, 0.145)

# The shaft's flank in the *Right view: an 8-dia cylinder at 1:1, so its top
# silhouette runs 4 mm above the view centre. The cylindrical callouts anchor
# HERE rather than on the front view's end circle -- see the GD&T block below.
SHAFT_FLANK_Y = RIGHT_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0

FRONT_KEEP = {
    # x=0.030, not the bbox-derived 0.014: horizontal text made this callout
    # ~25 mm wide ("+0.00/-0.02"), so centred on 0.014 it ran over the 12.7 mm
    # zone margin (the border gate measured 2.7 mm). 0.030 clears the margin on
    # the left and stops short of the end circle at x=0.047 on the right.
    "ShaftDia": (0.030, 0.220),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
    # Held 20 mm clear of the view's left end, not the old 4 mm: horizontal text
    # makes "SR7.27 CROWN" ~35 mm wide, so a 4 mm offset ran the text's right
    # half back over the crown dimension's own extension lines.
    "CapSagDim": (
        RIGHT_CENTER[0] - OVERALL_LEN / 2000.0 - 0.020,
        RIGHT_CENTER[1] + 0.022,
    ),
}
DIMENSION_CALLOUTS = {"ShaftDia": "+0.00/-0.02"}
CAP_CALLOUTS = {"CapSagDim": f"SR{CAP_R:.2f} CROWN"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion arbor; zeroing-drum shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, right_annotations, CAP_CALLOUTS)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to arbor end view")

    # Pick the end circle at 12 o'clock, because the symbol goes straight ABOVE
    # it. Picked at 3 o'clock (the +r,0 point) with the symbol at 12, the tag
    # fought SetPosition2's along-the-edge rule -- on a CIRCLE the permitted set
    # IS the circumference, so the symbol collapsed to the nearest circle point
    # and its Y went inert: the requested 16 mm standoff rendered as ~1 mm, too
    # little for the ~3 mm attachment triangle, which then overlapped the box
    # and struck through the "A". Picking the clock position the symbol actually
    # sits at lets the leader run radially out to it -- the same spelling
    # draw_pivot_shaft.py / draw_pivot_bushing.py use. No gate sees this: a
    # datum symbol exposes no GetExtent, so only the render shows it.
    end_top = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + SHAFT_DIA * END_VIEW_SCALE / 2000.0,
    )
    # Screen-right in *Right is model -Z: the flat front tip (z 0) lands on the
    # RIGHT end of the side view, the crowned back end on the LEFT.
    flat_end = (RIGHT_CENTER[0] + OVERALL_LEN / 2000.0, RIGHT_CENTER[1])
    # Live readback normalizes this restricted axis tag by up to 10.699 um. Bound
    # only annotation placement; part dimensions and GD&T remain unchanged.
    add_datum_feature(
        adapter,
        front,
        edge_xy=end_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024),
        datum="A",
        label="pinion arbor axis",
        position_tolerance_m=0.00002,
    )
    # Cylindricity and the bearing finish both control the shaft's CYLINDRICAL
    # face, which the side view shows edge-on -- so both anchor to its flank
    # there instead of to the front view's end circle. Anchored on the front
    # circle they had to sit out at the side view's x to find free sheet, and
    # the leader then ran the whole way back across the side view (the leader
    # gate caught both). Off the flank the leader is a short vertical drop into
    # the empty band above the view. A cylinder carries no model edge along its
    # side, so these picks are SILHOUETTE entities (as in draw_transgear_stub).
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.050, SHAFT_FLANK_Y),
        frame_xy=(RIGHT_CENTER[0] - 0.050, 0.236),
        characteristic="cylindricity",
        tolerance="0.01",
        label="arbor bearing cylindricity",
        entity_type="SILHOUETTE",
    )
    # Only the flat FRONT tip gets a perpendicularity control -- the back end
    # is the SR crown, which has no face to square to the axis.
    # Above the view, not below it at y=0.180: the isometric now occupies that
    # band, and the leader ran across it.
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=flat_end,
        frame_xy=(flat_end[0] + 0.018, 0.228),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="front tip perpendicularity",
    )
    # Sits right of the cylindricity frame, whose text ends near x=0.184; the
    # Ra text renders ABOVE the arm (ASME Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.050, SHAFT_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.050, 0.222),
        roughness_ra="1.6",
        label="arbor bearing finish",
        entity_type="SILHOUETTE",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred border rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Arbor Manufacturing Drawing",
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

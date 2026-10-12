r"""Create the curated machinist drawing for the magnifying-lever bracket.

The bracket is the black fitting that affixes the Ø6 magnifying lever
(MHA-MG-003) to the summing plate: an extruded COLLAR tube (Ø12 OD, 10 long
about local X) whose bore is the lever's PRESS seat, a rectangular ARM
cantilevering +Z, and a mounting FLANGE that butts the summing-plate front
face.  The two extruded plan rectangles (arm, flange) carry the auto-imported
marked dimensions on the TOP view, including the flange thickness band, and
the collar's length rides there too, above the collar it measures. Native
counterbore callouts and banded coordinates face the -Z entries in the BACK
view. The collar axis is local +X, so the RIGHT view shows the collar end as
concentric circles (ASME centre mark) and carries their native dimensions --
the OD and the press-seat bore with its band -- and, from the part's blanked
``ArmSection`` witness, the arm's thickness, its lower face from the bore
axis (controlling) and from the hole-datum flange face (reference), and the
seat face from the bore axis: the arm's position across the flange and the
bore axis's station, which the machinist review found missing.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_bracket.py mg-magnifying-bracket
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_edges import scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from magnifying_bracket_joint_layout import (
    BRACKET_HOLE_POINTS,
    COUNTERBORE_DIA,
    SIDE_PLATE_Z,
)
from mg_magnifying_bracket_spec import DRAWING_DIMENSIONS

SPEC = DRAWINGS_BY_NAME["mg_magnifying_bracket"]
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
TOP_CENTER = (0.115, 0.180)
FRONT_CENTER = (0.115, 0.110)
# Supplemental entry view, not part of the aligned front/top/right group.
BACK_CENTER = (0.245, 0.095)
RIGHT_CENTER = (0.240, 0.180)
ISO_CENTER = (0.340, 0.130)

# The four plan dimensions ride the TOP view (both extruded rectangles lie on the
# part's Top plane), as does the collar's mid-plane extrude length (along X).
# Arm/flange dim names are disambiguated in the build (ArmWidth/ArmDepth vs
# FlangeWidth/FlangeDepth) so this keep map is unambiguous.  +Z runs DOWN the
# top view (the collar, Z -6..6, sits at its top, y 200..212 mm; the arm's
# end, Z 58.3, at its bottom, y 147.8 mm).  The collar's length therefore
# reads above the collar, its witnesses 4 mm long: below the view (v41) they
# ran the full height of the part and crossed the arm's 54.30.  That text
# slides to below the arm's end (its dimension line moves right with it, to
# x 142 mm, 3 mm clear of the flange width's witness at x 139 mm), and the
# flange width's text moves left so the collar length's outside arrows clear
# it.  Text requested beyond a vertical dimension's span hangs off its column
# on the side away from the witnesses (see RIGHT_SECTION_KEEP): the 54.30's
# two rows print RIGHT of x 142 mm, over x ~142..171 mm, y 136..147 mm, so
# that column is the left bound of the right view's arm-section texts.
TOP_KEEP = {
    "ArmWidth": (0.088, 0.170),
    "ArmDepth": (0.142, 0.141),
    "FlangeWidth": (0.104, 0.216),
    "FlangeDepth": (0.089, 0.205),
    "CollarLen": (0.155, 0.224),
}
BACK_KEEP = {
    "MountingX0": (0.205, 0.124),
    "MountingX1": (0.230, 0.132),
    "MountingY0": (0.203, 0.095),
}
FRONT_KEEP = {"FlangeHeight": (0.148, 0.110)}
# The collar's end-on circles: the annulus sketch lies on the part's Right
# plane, so its two diameters import here.  The collar centre sits right of the
# view centre by half the arm's reach (the arm runs +Z, to the sheet's left;
# the collar centre prints at (266.15, 180) mm).  The OD reads above-right of
# the collar.  The bore's callout -- its banded value over two callout rows,
# ~65 mm wide, the leader's shoulder under the last row -- keeps v41's place
# below-left of the collar: its block must clear the collar's x on one side,
# or the leader from the bore's rim to the shoulder's near end cuts through
# its own rows, and right of the collar is the isometric.  Its rows span
# x ~198..263 mm, y ~139..155 mm: under the arm section's "FROM BORE AXIS"
# (bottom y 161.5 mm) by more than a text height and above the back view's
# 36.00 (top y 133.75 mm) by the same.  v41's second line had sat on the back
# view's hole callout ("DRILL / COUNTERBORE ..."), which now hangs below the
# back view.
RIGHT_KEEP = {
    "CollarOd": (RIGHT_CENTER[0] + 0.044, RIGHT_CENTER[1] + 0.016),
    "CollarBore": (RIGHT_CENTER[0] - 0.014, RIGHT_CENTER[1] - 0.033),
}
# The arm's section, from the part's ArmSection witness (shown in this view
# by curate_hidden_dimensions).  Its dimensions take the arm's END corners
# (x 207.85 mm, y 177/184.5 mm), the bore-axis centerline's end on that same
# station and the seat face's corners (x 210.96 mm, y 173.65/186.35 mm), so
# the three vertical ones' witnesses run left, away from the part, sharing
# the arm's lower-face witness.  Text requested beyond such a dimension's
# span is NOT centred on its column: SolidWorks runs the dimension line on to
# the baseline of the text's lowest row (a lone value row 2.78 mm under the
# requested y; with a callout row, the value row at the requested y and the
# callout row 5.56 mm under it) and hangs the rows off the column on the side
# away from the witnesses -- here to the LEFT -- over a shoulder as wide as
# the widest row plus ~2 mm each end
# (retry08 native audit: "FROM BORE AXIS" requested at x 205 mm printed over
# x 167.6..204.7 mm; the reference offset requested at x 167 mm reached
# x 146.6 mm, and its shoulder cut the top view's 54.30 column at x 147 mm,
# the enforced finding).  Each column therefore clears, by its own text
# width, every line left of it:
#   - the thickness in the outer column (x 187 mm): "7.50 / ARM THICKNESS"
#     above the view, rows over x ~151..187 mm, y 192..203 mm, the shoulder
#     at y 192.4 mm; its dimension line ends there, under the seat-face text;
#   - the lower face from the bore axis in the inner column (x 205 mm): rows
#     below the view, x ~167..205 mm, y 161..171 mm, the shoulder at y 160.4
#     mm, 5 mm over the bore callout's block;
#   - the reference offset from the hole-datum flange face beside those rows,
#     never under them (x 164 mm): "(3.35)" over x ~151..162 mm, y 163..168
#     mm, 5 mm of air to the 3.00's rows and 7 mm right of the 54.30 column;
#     its dimension line ends at y 163.2 mm, above the 3.00's shoulder, and
#     its witness along the hole-datum face crosses the 3.00's dimension line
#     3 mm above that text, the one crossing three stacked offsets cannot
#     avoid.
# The seat face from the bore axis runs above the view, its three rows
# (value over two callout rows) between the thickness text and the collar
# OD's, its dimension line under the lowest row (y 194.7 mm) 8 mm clear of
# the flange's top edge; its witness from the origin runs through the
# collar's centre, where both diameters' lines cross it (advisory, inherent
# to dimensioning to the axis).
RIGHT_SECTION_KEEP = {
    "ArmThickness": (0.187, 0.198),
    "ArmBelowAxis": (0.205, 0.166),
    "ArmOffset": (0.164, 0.166),
    "SeatToAxis": (0.2385, 0.203),
}
# Blind-review round 1: the four plan values read unattached at a glance --
# label each with the feature it controls.  The collar's length names its
# direction (machinist review: 10.00 vs the Ø12 read as one feature).
DIMENSION_CALLOUTS = {
    "ArmWidth": "ARM WIDTH",
    "ArmDepth": "ARM LENGTH",
    "FlangeWidth": "FLANGE WIDTH",
    "FlangeDepth": "FLANGE DEPTH",
    "CollarLen": "COLLAR LENGTH\nALONG BORE AXIS",
}
# The bore names its process (policy rule 6) and the part it seats: the lever.
RIGHT_CALLOUTS = {
    "CollarOd": "COLLAR OD",
    "CollarBore": "REAM OR BORE: PRESS SEAT\nFOR MHA-MG-003 LEVER",
}
SECTION_CALLOUTS = {
    "ArmThickness": "ARM THICKNESS",
    "ArmBelowAxis": "FROM BORE AXIS",
    "SeatToAxis": "SEAT FACE\nTO BORE AXIS",
}
# ArmOffset prints in parentheses: the arm is controlled from the bore axis,
# and its offset from the hole-datum face is that same position, read as
# reference against the flange the machinist can measure.  It is a LINEAR
# reference, so it takes the singular set_reference_dimension: the plural
# helper prefixes every name with the diameter glyph, which printed it as
# "(Ø3.35)" on retry08.
SECTION_REFERENCE = ("ArmOffset",)


def _mounting_rims(back: Any) -> list[Any]:
    """Back looks from -Z onto the counterbore entries."""
    edges = scan_view_edges(back, label="bracket mounting face")
    return [
        edges.circle_at(
            (point[0], point[1], SIDE_PLATE_Z[0]),
            COUNTERBORE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=f"bracket mounting hole {index}",
        )
        for index, point in enumerate(BRACKET_HOLE_POINTS)
    ]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-bracket source", await adapter.open_model(str(SOURCE)))
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
            0: "Magnifying Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying bracket; collar + arm + flange; steel fitting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # Top carries the collar bore and arm/flange hidden edges; the counterbore
    # shape is fully defined by its native callout on the clean entry view.
    set_hidden_lines_visible(adapter, top)
    set_hidden_lines_removed(adapter, back)
    set_hidden_lines_removed(adapter, front)

    # Targeted imports: each view selects only the features owning its keep
    # map (the entire-model fallback warned on every view and imported the
    # whole marked set to delete most of it).  The back view keeps no model
    # dimension -- its mounting coordinates arrive with curate_hidden_dimensions
    # below -- so it imports nothing.
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, top_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, right_annotations, RIGHT_CALLOUTS)
    # The arm's section: the part blanks ArmSection, so this targeted import
    # shows it in the right view first (it stays shown there, printing the
    # bore axis as a centerline out to the arm's end; its construction lines
    # lie on the view's own edges).
    section_annotations = curate_hidden_dimensions(
        adapter,
        right,
        keep=RIGHT_SECTION_KEEP,
        view_label="right arm section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, section_annotations, SECTION_CALLOUTS)
    # ArmOffset is a LINEAR reference: the plural set_reference_dimensions
    # forces the diameter glyph, printing "(Ø3.35)" (retry08 native audit).
    for name in SECTION_REFERENCE:
        matches = [
            a for a in section_annotations if dimension_name(adapter, a) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"expected one arm section {name} reference dimension, "
                f"found {len(matches)}"
            )
        set_reference_dimension(adapter, matches[0], label=f"arm section {name}")
    rims = _mounting_rims(back)

    add_native_hole_callout(
        adapter,
        back,
        edge=rims[0].edge,
        # AddHoleCallout2 centres the ~117 mm-wide text on x and the leader
        # runs from the hole's counterbore rim (centre (265, 95) mm, r 1.9) to
        # an elbow 2 mm before the text end nearer the hole.  Below the back
        # view the near end is the text's left end, at x_c - 60.6 mm; the
        # leader must leave the elbow UP-LEFT, so the hole must be left of it
        # (centred at 300 mm the elbow sat at x 239.5 mm, the leader came
        # down-left from the hole, cut 3.3 mm of its own bottom row and
        # crossed the 6.35's lower witness, (202..264, 88.65) mm: retry08
        # native audit), and it must thread between the 4.00's witnesses at
        # x 265 and 269 mm, which reach down to y 89.6 mm.  Centred at 337 mm
        # the elbow is at (276.4, 70.7) mm and the leader climbs to the rim at
        # (265.8, 93.3) mm, at x 267.5 mm where those witnesses end: 1.5 mm
        # from either, 4 mm right of the 6.35 witness' end.  At (0.330, 0.160)
        # it rose through the 4.00 and 17.70 dimension lines (machinist
        # review); the text sits above the title block (y >= 66 mm) and 7 mm
        # under the isometric note (y 91.4 mm).  (0.205, 0.064) printed over
        # the title block; x = 0.150 and 0.270 both led through '17.70'.
        callout_xy=(0.337, 0.078),
        label="two bracket counterbores",
        process="DRILL / COUNTERBORE",
    )
    curate_hidden_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="bracket mounting coordinates",
        dimensions_by_feature={
            "MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0"),
        },
    )

    # ASME centre mark on the collar bore (a real circular edge in the end view).
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the collar bore")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.095)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Bracket Manufacturing Drawing",
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

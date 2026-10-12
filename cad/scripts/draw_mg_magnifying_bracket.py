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
from _drawing_dimensions import set_dimension_callouts, set_reference_dimensions
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
# x 147 mm), clear of the flange width's witness at x 139 mm, and the flange
# width's text moves left so the collar length's outside arrows clear it.
TOP_KEEP = {
    "ArmWidth": (0.088, 0.170),
    "ArmDepth": (0.147, 0.141),
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
# (x 207.85 mm, y 177/184.5 mm) and the bore-axis centerline's end on that
# same station, so their witnesses run left, away from the part, sharing the
# arm's lower-face witness: the thickness in the outer column (x 187 mm, text
# above the view), the lower face from the bore axis in the inner column
# (x 205 mm, text below the view) and the reference offset from the
# hole-datum flange face further left (x 167 mm, text below, beside -- never
# under -- the 3.00's rows; its witness along the flange's lower face crosses
# the 3.00's dimension line 3 mm above that text, the one crossing three
# stacked offsets cannot avoid).  The seat face from the bore axis runs above
# the view, its two callout rows hanging between the thickness text and the
# collar OD's, its dimension line ~7 mm clear of the flange's top edge.
RIGHT_SECTION_KEEP = {
    "ArmThickness": (0.187, 0.198),
    "ArmBelowAxis": (0.205, 0.166),
    "ArmOffset": (0.167, 0.165),
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
# reference against the flange the machinist can measure.
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

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, back, keep={}, view_label="back")
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
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
    set_reference_dimensions(adapter, section_annotations, SECTION_REFERENCE)
    rims = _mounting_rims(back)

    add_native_hole_callout(
        adapter,
        back,
        edge=rims[0].edge,
        # AddHoleCallout2 centres the ~120 mm-wide text on x and the leader
        # lands on the text end nearer the hole (263.6, 96.3 mm). Centred at
        # 300 mm, below the back view, the near end is the text's left end
        # (x 240 mm), so the leader drops left from the hole, out through
        # the flange's lower edge between the two counterbores, clear of
        # every back-view dimension line: at (0.330, 0.160) it rose through
        # the 4.00 and 17.70 dimension lines (machinist review). The text
        # sits above the title block (y >= 66 mm) and below the isometric
        # note (y 95 mm). (0.205, 0.064) printed over the title block;
        # x = 0.150 and 0.270 both led through '17.70'.
        callout_xy=(0.300, 0.078),
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

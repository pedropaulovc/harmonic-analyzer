r"""Create the cone-gear-shaft manufacturing drawing under drawing-guidelines.md.

The turned shaft is shown horizontally at 1:1 with baseline lengths below it,
one origin per chucking (rule 11): the journal and the collar web from the
collar's thrust face, the gear lands and the tip from its tip-side face; every
diameter is above it on that same side
view, each dimension line inside the land it measures (the 3.2 mm collar
instead takes one near-side arrow on its rim).  Land 1's keyseat is shown in
its own enlarged cut-only section A-A, carrying its sizes.  The tip end view,
projected left of the side view, carries the reamed socket's callout (owner
decision C1 keyed, 2026-11-09, PR #1992).  A standard isometric supplies
pictorial clarity.  Every tight band names its mate at its own callout or in
the numbered note linked from it.  Source geometry and native model fits stay
authoritative.  The front-to-tip overall is a reference and takes its display
precision from the spec.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_gear_shaft.py dt-cone-gear-shaft
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
import math
import sys
from typing import Any, NamedTuple

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound, _read_member
from _drawing_annotation_extent import (
    CLEAR_GAP_M,
    PLACE_SETTLE_M,
    Box,
    callout_ink,
    gdt_box,
    move_annotation,
    require_clear,
    require_inside,
    require_leader_clear,
    sheet_region,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_blind_ream_callout import add_blind_ream_callout
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_leaders import (
    Segment,
    dimension_segments,
    dimension_text_points,
    distance_to_box,
    leader_segments,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _gear_drawing_entities import visible_circle_edge
from _layout_geometry import estimate_text_box
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import supplier_reference_dimension
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_cone_gear_shaft_spec import (
    BOND_FLAG,
    COLLAR_DIA,
    COLLAR_DIA_FRACTION_DENOMINATOR,
    COLLAR_END_STATION,
    COLLAR_STOCK_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    KEYED_LAND,
    KEYSEAT_MATE_SUFFIXES,
    LAND_NOTE,
    JOURNAL_DIA,
    SEAT_MATE_CALLOUTS,
    SEAT_MATE_SUFFIXES,
    STACK_NOTE,
    SECTION_DIAS,
    SECTION_ENDS,
    SHAFT_LENGTH,
    SOCKET_DEPTH,
    SOCKET_DIA,
    SOCKET_DIA_BAND,
    SOCKET_PROCESS,
    SURFACE_FINISHES,
    inch_text,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_cone_gear_shaft"]
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
SIDE_SCALE = (1, 1)
ISO_SCALE = (1, 2)
# One sheet: the tip-side lengths run from the collar's tip-side face (rule
# 11, round 6), so the old setup sheet's references from that face would only
# repeat them.
SHEET_NAMES = ("Shaft Controls",)


# Landscape sheet, 0.4318 x 0.2794 m, title block bottom right (x > ~0.216,
# y < ~0.066).  The spec-derived shaft at 1:1 ends at BIG_END_X, leaving the
# right third for the pictorial (top) over section A-A.  The group sits
# just below mid-height so the baseline stack below and the diameters above
# share the field with the note block in the lower left (review 2026-09-23:
# at 0.170 rows A-B stood empty but for the note).  The view is placed by its
# large end: every dimension below is laid out from that datum face, so a
# change at the tip (C1 keyed ends the shaft inside T024's bore) moves only
# the tip.
BIG_END_X = 0.2526
SIDE_CENTER = (BIG_END_X - SHAFT_LENGTH / 2000.0, 0.150)
TIP_END_X = BIG_END_X - SHAFT_LENGTH / 1000.0
# 10 mm right of round 2's (0.363): the collar's two-line callout, its limits
# now at the feature, reaches x ~0.330 under the pictorial's low end.
ISO_CENTER = (0.373, 0.232)
# At the left frame, as the other part sheets' note blocks: the note lines
# run up to 72 characters before the title block.
NOTES_XY = (0.020, 0.060)
# Off-sheet-left donor: the land diameters are model dimensions of circular
# profile sketches, so they can only be IMPORTED into a view that faces those
# circles.  They are imported here, dragged onto the shoulder each one
# belongs to, and this view is then deleted.
DONOR_CENTER = (0.360, 0.090)

# Lengths, one origin per chucking (rule 11, round 6): the collar's thrust
# face at sheet x 0.2096 for the journal (to the right) and the collar web,
# both on the first tier; its tip-side face, one web left, for the land step
# and the tip (#917 R5 (a)), baseline below the shaft, one tier each, the
# shorter nearer the part.  Every tier is one line of text.  The
# front-to-tip overall, a reference, hangs lowest, above the title block.
# A station's text is centred in its span when it fits there with
# STATION_TEXT_CLEARANCE to spare; the web's 3.18 span is narrower than its
# text, so the text stands LEFT of the collar's north witness line (the 916a
# render had the web text touch that line).  The one radius rides
# above the 3/8-to-1/4 in step it attaches to (the fillet's first edge),
# right of the Ø.2500 line.  With its stacked +.000/-.002 band its text is
# 23.4 mm wide and its shoulder 25.4 mm, so it stands 0.4 mm nearer that line
# than the bare MAX text did.  PR 2 r2 (967cedb) measured it 0.0862..0.1122
# x 0.1612..0.1647: 4.1 mm short of section A-A's upper arrow with A cut
# A_CUT_FROM_STEP_MM from the step (1.1 mm at 25, under the proof's 2 mm),
# and its shoulder 1.3 mm right of the Ø.2500 line (r16 crossed it at +0.0085).
# PR 2 r3 (2aeedb78) measured the shoulder 0.0846..0.1130 at y 0.1612 about
# its 0.0996 position, 2.4 mm wider than r2's, crossing the Ø.2500 line
# (x 0.0849, 0.1532..0.1740).  Land 2 is too short to move that line left of
# the shoulder, so the radius moves 2.8 mm right (shoulder from ~0.0874,
# 2.5 mm right of the line) and A's cut 3 mm north to keep its arrow clear.
SIDE_KEEP = {
    "CollarWidth": (0.1740, 0.1355),
    "Sec0End": (0.2311, 0.1355),
    # Its " SEE NOTE 2" flag (round 4) widens the text to ~37 mm; 12 mm right
    # of the bare value's centre it starts right of section A's lower letter
    # (x <= 0.1409 with A cut 31 mm from the step), one tier above it.
    "Sec1End": (0.1620, 0.1275),
    "Sec2End": (0.1464, 0.1195),
    "ShoulderR": (BIG_END_X - SECTION_ENDS[1] / 1000.0 + 0.0124, 0.1640),
    # The keyseat end's centre from the collar face (machinist review of
    # 06460fb; .05 since Codjiflo #2331 4521933063).  Its 1.3 mm span puts both
    # arrows outside; it hangs below the shaft from land 1's lower corner,
    # where the collar diameter's line (x 0.2088, down to y 0.1357) and the
    # collar web's witnesses (down to 0.1323) end above its line: its right
    # arrow (to x ~0.213) crosses neither.  PR 1 r8 (1b3d39ffbd16) measured
    # the ".05" text box 2.8 mm left, 3.0 mm right, 1.8 mm under and 1.7 mm
    # over its (0.1965, 0.1308) position, its line 2.8 mm under it, and the
    # web's outside left arrow (0.1999..0.2062 at y 0.1327, 0.76 mm wide)
    # 0.41 mm from that box (layout audit arrow-near-text, gating; same on
    # PR 2 r5).  Here the box (~0.1917..0.1975 x 0.1275..0.1310) keeps 2.7 mm
    # of that arrow, its line (~0.1265) 1.8 mm over Sec1End's (0.1247) and
    # its text 2.8 mm over it, and the web's text (ends 0.1913, from 0.1337
    # up) 2.7 mm away.
    "Sec1KeyseatEndSet": (0.1945, 0.1293),
}
OVERALL_REFERENCE_TEXT_XY = (0.1515, 0.0795)
# Sheet width of one length digit or point at the dimension font (the 916a
# render measured "10.781" at 13.4 mm, 2.2 mm a character), and the ink every
# length text keeps from any extension line crossing its tier.
LENGTH_CHAR_WIDTH = 0.0023
# One capital letter of callout or suffix text: "EDGE BREAK 0.1 MAX" read
# 47.3 mm on the r1 render (20261018T054926125Z), 2.6 mm a character.
CALLOUT_CHAR_WIDTH = 0.0026
STATION_TEXT_CLEARANCE = 0.002
# Diameters, imported on the donor and dragged onto the side view.  A vertical
# linear dimension's line sits at its text x and the text hangs to the RIGHT
# of that line (~32 mm wide with its stacked band, and its mate suffix
# after it), so each x lies INSIDE the land it measures; land 2's line
# follows its end stations, one third of its length back from the tip.  Ø12.231 stands just off the faced end, its text and
# two mate lines above the journal's extension lines, 4 mm nearer the end
# than r2's so its widest mate line ends clear of section A-A's dimensions.
# Its text's lower-left corner is where the dimension line turns, so the
# block stands 3.5 mm higher than r4b's: there the shelf sat on the
# extension line and the 3 mm arrow rose into "MHA-DT-05" (machinist
# review r4b, 20261018T072511131Z).  Land 2's text, with its suffix, ends
# left of land 1's line; Ø9.525 stands right of it, its mate line centred on
# it clear above A-A's letter.
SIDE_DIAMETERS = {
    # The journal's text stands just off the faced end, where rounds 1 and 2
    # proved it hangs RIGHT of its line (r2 render 20261107T104940656Z: ink
    # from 0.2575).  Dragged onto the journal instead (round 3, 0.2190) the
    # proof's box hung LEFT, 0.1325..0.2041, onto section A's lower letter.
    # Its widest line, "(CLEARANCE .0010-.0023)", boxes 23 x 2.17 mm in the
    # proof's estimator (round 3: 33 characters 0.0716 wide), so the block
    # ends ~0.307, 6.7 mm short of section A-A's box (x 0.3141).  The round 3
    # box stood 10.1 mm below and 9.1 mm above the text position over four
    # rows; at 0.1785 a fifth row of 5.3 mm, grown either way, stays 7 mm
    # above the journal's upper extension line (0.1561) and 7 mm below the
    # collar callout (bottom ~0.200 on round 2).
    "Sec0Dia": (0.2575, 0.1785),
    "Sec1Dia": (0.1600, 0.1800),
    "Sec2Dia": (BIG_END_X - (2.0 * SECTION_ENDS[2] + SECTION_ENDS[1]) / 3000.0, 0.1785),
    # #914: the collar ring is 3.181 wide, too narrow for a dimension line
    # and two arrows inside it, so the collar alone takes the near-side
    # diametric style: one arrow on the top rim from outside, leader up to
    # the text, nothing drawn inside the ring.
    "CollarDia": (0.2088, 0.1760),
}
NEAR_SIDE_DIAMETERS = ("CollarDia",)
# The collar is the 5/8 bar's OD as supplied (user ruling 2026-09-26), so
# its diameter prints as a reference with the stock statement beside it,
# the U41 plate's form.
REFERENCE_DIAMETERS = ("CollarDia",)
# Sheet width of one diameter text with its stacked band, for the layout test.
DIAMETER_TEXT_WIDTH = 0.032
# One-line suffixes after a dimension's value: land 2's flag to the bond
# note, and the stack's three-place lengths' flag to the stack note (round 4
# review: a note naming the mates must be linked at each callout it serves,
# rule 7).  The tip station Sec2End is one of them: its .XXX band is what
# keeps the shaft's end inside T024's bore, so T018 butts T024 and not the
# shaft (the recess proof in dt_cone_gear_shaft_spec; at .XX the end could
# stand 0.10 mm proud of T024's north face).  PR 2 r4 review (7522757):
# unflagged, it read as a three-place length with no function.  Other
# lengths carry their value and band only.
STACK_FLAG_SUFFIX = f" SEE NOTE {STACK_NOTE}"
STACK_LENGTHS = ("Sec1End", "Sec2End", "CollarWidth")
DIMENSION_SUFFIXES = {
    **SEAT_MATE_SUFFIXES,
    **{name: STACK_FLAG_SUFFIX for name in STACK_LENGTHS},
}
# The collar prints its reference diameter over the stock line with its edge
# break and the roots line with its mates, lines as wide as "5/8 BAR AS
# SUPPLIED" or wider.  At LENGTH_CHAR_WIDTH a line
# that long is wider than the whole journal land, so hanging right from its
# rim arrow the block ran under the pivot-journal finish and that finish's
# leader crossed it (final877 eye pass).  The build lifts the block above the
# finish symbol, from its measured ink (_clear_collar_callout); the dimension
# line stays on the ring and simply runs longer.
COLLAR_CALLOUT_LINES = ("(Ø5/8 in)", *COLLAR_STOCK_CALLOUT.split("\n"))
COLLAR_CALLOUT_WIDTH = max(len(line) for line in COLLAR_CALLOUT_LINES) * LENGTH_CHAR_WIDTH
# A measured block narrower than this is a misread (a box around the value
# line alone), not a layout: the proof refuses it rather than clearing it.
COLLAR_CALLOUT_MIN_READ = 0.9 * COLLAR_CALLOUT_WIDTH
DONOR_KEEP = {
    name: (DONOR_CENTER[0], DONOR_CENTER[1] - 0.012 * index)
    for index, name in enumerate(SIDE_DIAMETERS)
}
# One step root, one radius dimension (the collar's roots stay sharp, #914,
# their limit in the collar callout).  The journal and land 1 name their
# mates below their diameters.
DIMENSION_CALLOUTS = {
    "CollarDia": COLLAR_STOCK_CALLOUT,
    **SEAT_MATE_CALLOUTS,
}
# The pivot-journal finish symbol, above whose ink the collar's text must
# stand; its leader lands on the journal's top flank
# PIVOT_FINISH_ATTACH_INSET in from the faced end (round 2's placement, left
# of the journal's text).
PIVOT_FINISH_XY = (0.2400, 0.1800)
PIVOT_FINISH_ATTACH_INSET = 0.020


# The tip end view (drawing-guidelines.md rules 9 and 12): the reamed socket
# is a standard blind ream, fully defined by its callout, so it needs no
# section.  The view looks at the tip end face (*Front looks along model -Z,
# the shaft's tip end on its +Z), projected LEFT of the side view in third
# angle at the sheet scale, on the side view's axis, so it needs no label.
# Its outline is the collar's Ø5/8 circle; TIP_END_VIEW_GAP leaves the axis
# overrun and the collar circle 12 mm apart.  The socket's rim faces the
# viewer there, so it carries a native hole callout (Codjiflo #2459
# 4523315375): SolidWorks prints the Socket cut's own diameter, band and
# depth, so the depth follows the model; the process joins before the depth
# (rule 26: size, process, depth) and the bond flag goes below.  Its text
# stands up and left of the view (the field the stepped-tip detail used to
# take), clear of land 2's diameter text, which hangs right of its line
# (0.0849) inside land 2.  The PR 2 r5 proof (20261110T081142602Z) measured
# the old imported SocketDia's rows about its (0.033, 0.185) position: the
# size row 33.9 mm wide from 0.0167, the "REAM ↧ .20" row 27.2 mm, the flag
# row 0.1749..0.1784, the band's top 0.1941.  The callout's one row joins
# both (~61 mm), so it moves 14 mm right: about 0.016..0.078 at 0.047, 3 mm
# inside the frame and 7 mm left of land 2's line.  The layout proof
# measures its box.
TIP_END_VIEW_GAP = 0.020
TIP_END_VIEW_CENTER = (TIP_END_X - TIP_END_VIEW_GAP, SIDE_CENTER[1])
SOCKET_CALLOUT_XY = (0.047, 0.185)
# The Socket cut's dimensions the callout prints (marked, with their model
# places): no view imports them.
SOCKET_CALLOUT_DIMENSIONS = frozenset({"SocketDia", "SocketDepth"})
# What the callout must print, read back: the Socket cut's diameter with
# its band, and its depth at the model's drawing places (SolidWorks resolves
# the depth from the cut at insertion; this only checks it).
SOCKET_DEPTH_READBACK = inch_text(
    SOCKET_DEPTH, DRAWING_PRECISION_BY_NAME["SocketDepth"]
)


class DSection(NamedTuple):
    """The keyed land's section: the station its cutting line crosses on the
    side view, how far the line reaches either side of the axis, where the
    removed section stands, and its own scale."""

    land: int
    label: str
    station_mm: float
    reach: float
    centre: tuple[float, float]
    scale: tuple[int, int]


# Land 1's keyseat (owner decision 2026-11-09, C1 keyed, PR #1992), on the
# shaft's +X.  The side view looks straight at it, so its size is only
# readable end-on: the land is cut across and shown cut-only (nothing beyond
# the plane prints), enlarged 2:1.  A-A cuts land 1 on the side view, left of
# the Ø9.525 line.  Its lower letter's top stands 4.8..6.3 mm above the
# line's end, by seat (6.3 on swmaker00000a in the 19e33c6c2 build, where a
# 12.5 mm reach left it 1.4 mm under land 1); the 15 mm reach leaves the
# worst 3.9 mm under the land.  The section stands right of the side view,
# under the pictorial, over its caption.  It prints the keyseat's S
# (Sec1KeyseatS, horizontal, centred over the section) and its width
# (Sec1KeyseatWidth, vertical, the land-note flag after it) above that on the
# keyseat's own side, placed at build time once the section reports which
# side +X lands on.  A's line is wider than its section: r3
# (20261018T065854075Z) and #290 batch 0 placed it 2.9 mm left of the
# frame-bound column, with Ø12.2555 (SIDE_DIAMETERS) 4.5 mm left to keep
# A's box clear of it.  The cutting line stands A_CUT_FROM_STEP_MM north of
# land 1's step: at 25 mm its upper arrow, 0.1133..0.1287 with the proof's
# 1.7 mm pad, stood 1.1 mm right of the R.004 text's 0.1122 (PR 2 r2,
# 967cedb).  At 28 mm the arrows started 0.1163.  r3's wider radius text
# moved 2.8 mm right (SIDE_KEEP), so at 31 mm the arrows start 0.1193, 3.5 mm
# clear of its shoulder's right end (~0.1158); its letters (0.1285..0.1349 at
# 25 mm) move to 0.1345..0.1409, and Sec1End's text (SIDE_KEEP) moves 6 mm
# right with them.
A_CUT_FROM_STEP_MM = 31.0
D_SECTIONS = (
    DSection(1, "A", SECTION_ENDS[1] - A_CUT_FROM_STEP_MM, 0.0150, (0.3371, 0.165), (2, 1)),
)
# The dimensions each section prints; the first is centred over its section
# (A-A's S shifted at build time, below).
SECTION_DIMENSION_NAMES = {
    KEYED_LAND: ("Sec1KeyseatS", "Sec1KeyseatWidth"),
}
D_SECTION_KEEP = {
    SECTION_DIMENSION_NAMES[section.land][0]: (section.centre[0], section.centre[1] + 0.017)
    for section in D_SECTIONS
}
# A-A's S text steps KEYSEAT_S_SHIFT away from the keyseat, and its arrows
# stand inside its extension lines (swDimensionArrowsSide_e.swDimArrowsInside),
# so the keyseat width's dimension line, rising at the keyseat's edge, crosses
# neither the S text nor its dimension line.  Machinist review of PR 1
# 5a4e41cb5f r3 (clarity, gating) and its layout audit measured the
# collision: the width line at x 0.3466 ran through the S band text
# (0.3227..0.3501, 14.4 mm left and 13.0 mm right of its 0.3371 position) and
# its outside arrow's line out to 0.3513.  At 7.0 mm off, the S text ends
# 0.3431, 3.5 mm short of the width line; inside arrows end its dimension line
# at the floor's extension line, 0.3449.  Its left end, 0.3157, stays clear of
# the Ø.4825 block (~0.307).
KEYSEAT_S_SHIFT = 0.0070
# S's text block (value, stacked band, and the NOTE flag above them) stands
# centred on its position, so the flag's row pushed the value DOWN: PR 1 r9
# (9b8efb7876) measured the block 0.3170..0.3424 x 0.1747..0.1872 about
# (0.3301, 0.182), 7.3 mm under and 5.2 mm over, its foot 0.2 mm off the
# face (top 0.1745; r8 without the flag: value foot 0.1775).  Lifting it
# KEYSEAT_S_FLAG_LIFT puts the foot at 0.1777, CLEAR_GAP_M plus 1.2 mm off
# the face, and its top 0.1902, 9.9 mm under the pictorial (0.2001); the
# block keeps its x, 2.6 mm right of the Ø.4825 text (to 0.3144) and 4.2 mm
# left of the width's line (0.3466).
KEYSEAT_S_FLAG_LIFT = 0.0030
ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# The keyseat width's text: KEYSEAT_WIDTH_RISE above the section centre, at
# the keyseat side's sheet x.  A vertical dimension's line stands at its
# text's left edge, so the text runs right from the keyseat, 46.1 mm wide:
# the PR #2331 proof (head 7f1dedc) measured it to 0.3927 from ~0.3466, wider
# than A-A's cell.  It rides one row above the section (PR #2331's farm fix,
# 5994f29c83), its own box in the layout proof, not inside A's cell.  That row
# is measured (5994f29 r2): A-A's S text top 0.1855, the pictorial's outline
# bottom 0.2001, and the text's box 4.5 mm under and 3.5 mm over its position
# (0.1905..0.1985 at 0.195, where it crowded the pictorial).  The rise centres
# it in that 14.6 mm row: 3.3 mm clear of each, 1.3 mm over CLEAR_GAP_M.
KEYSEAT_WIDTH_RISE = 0.0283
# A-A's S flags the land note like its width (PR 2 r5 machinist review,
# clarity: the depth lacked the width's flag).  Above, not after: an
# after-suffix would run the S line ~18 mm right, through the width's
# dimension line at the keyseat's edge (0.3466), and the Ø.4825 block (to
# 0.3144) holds its left (PR 2 r5, 20261110T081142602Z, as PR 1 r8).
# Centred on the S text, it joins S's block (KEYSEAT_S_FLAG_LIFT has the
# r9 measurement), 4.2 mm left of the width's line and shelf (from 0.3466
# at y 0.1888).  One line: a line break in the above compartment never
# prints.
SECTION_ABOVE_CALLOUTS = {"Sec1KeyseatS": f"NOTE {LAND_NOTE}"}


def _set_dimension_suffixes(
    adapter: Any, annotations: Iterable[Any], suffixes: Mapping[str, str]
) -> None:
    """Write each named dimension's native suffix (after its value and band,
    on its one line) and read it back; the value stays the model's."""
    remaining = dict(suffixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        text = remaining.pop(dimension_name(adapter, annotation), None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(2, text)  # swDimensionTextSuffix
        got = str(display.GetText(2) or "")
        if got != text:
            raise RuntimeError(f"dimension suffix {text!r} did not persist: {got!r}")
    if remaining:
        raise RuntimeError(f"dimension suffixes not applied: {sorted(remaining)}")


@_telemetry.traced("drawing.socket_callout")
def _add_socket_callout(adapter: Any, tip_end: Any) -> Any:
    """Call out the socket natively on its rim in the tip end view
    (_drawing_blind_ream_callout): the Socket cut's diameter, band and depth
    stay SolidWorks' own; REAM joins before the depth and the bond flag goes
    below.  Returns the callout's annotation."""
    return add_blind_ream_callout(
        adapter,
        tip_end,
        edge=visible_circle_edge(adapter, tip_end, SOCKET_DIA),
        callout_xy=SOCKET_CALLOUT_XY,
        label="socket",
        dia_mm=SOCKET_DIA,
        deviations_mm=deviations(SOCKET_DIA_BAND),
        depth_text=SOCKET_DEPTH_READBACK,
        process=SOCKET_PROCESS,
        below=BOND_FLAG,
    )


# A native "SECTION A-A / SCALE 2 : 1" caption measured 45.4 x 17.0 mm (leaf
# for c8b0aad); it is hung SECTION_CAPTION_GAP under its section's ink.
SECTION_CAPTION_SIZE = (0.046, 0.017)
SECTION_CAPTION_GAP = 0.003
# A caption lands within this of its target (its anchor is not its box).  A
# note's extent reads on a grid that differs by session: on two seats (leaves
# 20260930T011635Z-1-c8539f7a, 20260930T011941Z-1-30339b73) a caption top
# settled 0.30 mm under the target and another 0.31 mm over the same y, both
# to the micron on both seats, so 0.3 mm was half a step.  At 0.6 mm the
# caption still stands 2.4 mm or more under its face.  The layout proof
# measures the placed box, so the slack costs no clearance.
CAPTION_SETTLE_M = 0.0006
# A full section is given a centre mark, which is deleted so the section
# reads as the cut face alone (machinist review r7, 20261018T084331898Z).
# swAnnotationType_e.swCenterMarkSym:
_CENTER_MARK_ANNOTATION = 13
# An arrowhead's half-width across its shaft (the audit's 12.1 x 3.4 mm head).
SECTION_ARROW_HALF_WIDTH = 0.0017
if tuple(section.land for section in D_SECTIONS) != (KEYED_LAND,):
    raise AssertionError("the keyed land, and only it, takes a section")


@_telemetry.traced("drawing.cylindrical_face_scan")
def _cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible cylindrical face for one shaft diameter."""
    candidates: list[tuple[float, Any]] = []
    for face in visible_view_entities(view, 3, label="gear-shaft side faces"):
        face = _early_bound(face, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        radius_mm = float(surface.CylinderParams[6]) * 1000.0
        candidates.append((radius_mm, face))
    if not candidates:
        raise RuntimeError("side view has no visible cylindrical faces")
    target_radius = diameter_mm / 2.0
    radius_mm, face = min(candidates, key=lambda item: abs(item[0] - target_radius))
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no cylindrical face matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return face


@_telemetry.traced("drawing.end_face_circle", label_param="label")
def _end_circle(view: Any, *, station_mm: float, diameter_mm: float, label: str) -> Any:
    """The one visible end-face circle (or arc) at ``station_mm`` of ``diameter_mm``.

    The journal's circle also stands at the collar face and the socket's
    mouth on the tip face, so the pick is by station AND diameter.  The
    station is matched on |z|: the shaft runs along model Z from the front face, and the sign of
    that axis is the part's, not an assumption made here.
    """
    matches: list[Any] = []
    for raw in visible_view_entities(view, 1, label=f"{label} edges"):
        curve = _early_bound(raw, "IEdge").GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        if abs(abs(params[2]) * 1000.0 - station_mm) > 1e-3:
            continue
        if abs(params[6] * 2000.0 - diameter_mm) > 1e-3:
            continue
        matches.append(raw)
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: {len(matches)} end-face circles at z {station_mm:g} "
            f"of Ø{diameter_mm:g}, expected 1"
        )
    return matches[0]


def _add_overall_reference(adapter: Any, side: Any) -> Any:
    """Dimension front stub to tip as a REFERENCE (#917 R5 (a)).

    The journal and the collar web chain the front stub to the collar's
    tip-side face, the tip is a station from that face (rule 11, round 6), so
    the overall is the read-only sum of the three: a sheet-derived dimension
    between the two end faces, parenthesized, with the places the spec hands
    over, and its value proved against the part.
    """
    front = _end_circle(
        side, station_mm=0.0, diameter_mm=SECTION_DIAS[0], label="front end face"
    )
    tip = _end_circle(
        side,
        station_mm=SHAFT_LENGTH,
        diameter_mm=SECTION_DIAS[-1],
        label="tip end face",
    )
    display = add_edge_dimension(
        adapter,
        side,
        p0=(0.0, 0.0),
        p1=(0.0, 0.0),
        text_xy=OVERALL_REFERENCE_TEXT_XY,
        label="front-to-tip overall",
        orientation="horizontal",
        entities=(front, tip),
    )
    display = _early_bound(display, "IDisplayDimension")
    measured = abs(
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue)
    )
    if abs(measured * 1000.0 - SHAFT_LENGTH) > 1e-4:
        raise RuntimeError(
            f"front-to-tip overall measured {measured * 1000.0:.4f} mm, "
            f"expected {SHAFT_LENGTH:.4f}"
        )
    set_reference_dimension(
        adapter, display.GetAnnotation(), label="front-to-tip overall reference"
    )
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("front-to-tip overall reference precision did not persist")
    return display


# A centreline runs a short way past the part it marks.
AXIS_OVERRUN = 0.003


def _add_shaft_axis(adapter: Any, view: Any) -> None:
    """Draw the shaft axis end to end as ONE sheet centreline.

    A face-derived centreline (``add_view_centerline``) stops at its own land,
    so the first sheet showed an axis under the journal only (review
    2026-09-23), and ``InsertCenterLine2`` returned nothing for the third land
    (Ø6.35) on the farm (run 772bf5f3), after the first two had succeeded.
    So the axis is sketched on the sheet, as the swing platform's cone axis
    is: through the projected axis the finish leaders already attach to,
    checked against the view outline's mid-height, and AXIS_OVERRUN past each
    end face.
    """
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    tip_end_x = big_end_x - SHAFT_LENGTH / 1000.0
    axis_y = SIDE_CENTER[1]
    outline = tuple(float(value) for value in view.GetOutline())
    if abs(0.5 * (outline[1] + outline[3]) - axis_y) > 0.0005:
        raise RuntimeError(
            f"side view outline {outline!r} is not centred on the axis y={axis_y}"
        )
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    drawing.EditSheet()
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    centerline = manager.CreateCenterLine(
        tip_end_x - AXIS_OVERRUN, axis_y, 0.0, big_end_x + AXIS_OVERRUN, axis_y, 0.0
    )
    if centerline is None:
        raise RuntimeError("failed to sketch the shaft axis centreline")
    # A sheet sketch line prints in the under-defined sketch blue (run
    # f2e72b0f); colour it black, as draw_top_frame's owned centrelines are.
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("shaft axis centreline colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _collar_callout_dy(text: Box, finish: Box, finish_leader: Sequence[Segment]) -> float:
    """How far to lift the collar callout so its text clears the pivot-journal
    finish from above: the symbol and every leader run under the text's span.

    Only up: the collar diameter's dimension line stands at its text's left
    edge, so a sideways move drags that line off the ring and its extension
    lines along the rim (mha014-1 moved it 74 mm left, onto land 1's
    Ø9.525 text)."""
    left, right = text[0] - CLEAR_GAP_M, text[2] + CLEAR_GAP_M
    under = [finish[3]] if finish[0] < right and left < finish[2] else []
    under += [
        max(a[1], b[1])
        for a, b in finish_leader
        if min(a[0], b[0]) < right and left < max(a[0], b[0])
    ]
    return max([0.0] + [top + CLEAR_GAP_M + PLACE_SETTLE_M - text[1] for top in under])


def _dimension_text_box(annotation: Any, label: str) -> Box:
    """A dimension's rendered text block: every text item it draws (value,
    stacked band, callout lines), boxed by the layout audit's estimator, since
    no API returns a text's width."""
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    boxes = []
    for index in range(int(data.GetTextCount())):
        anchor = [float(value) for value in data.GetTextPositionAtIndex(index)]
        reference = int(data.GetTextRefPositionAtIndex(index))
        box = estimate_text_box(
            str(data.GetTextAtIndex(index) or ""),
            anchor=(anchor[0], anchor[1]),
            height=float(data.GetTextHeightAtIndex(index)),
            reference=reference if 0 <= reference <= 5 else 0,
            angle=float(data.GetTextAngleAtIndex(index)),
        )
        if box is not None:
            boxes.append(box)
    if not boxes:
        raise RuntimeError(f"{label} draws no text to measure")
    return (
        min(box.xmin for box in boxes),
        min(box.ymin for box in boxes),
        max(box.xmax for box in boxes),
        max(box.ymax for box in boxes),
    )


def _collar_text(adapter: Any, collar: Any, label: str) -> tuple[Any, Box]:
    """The collar callout's ink and its whole text block, refusing a misread.

    ``callout_ink`` boxes the text from its shoulder; the text positions widen
    that box to every line, so a stock line hung below the shoulder counts.
    """
    ink = callout_ink(adapter, collar, label=label)
    points = dimension_text_points(collar)
    xs = [ink.text[0], ink.text[2], *(x for x, _y in points)]
    ys = [ink.text[1], ink.text[3], *(y for _x, y in points)]
    text = (min(xs), min(ys), max(xs), max(ys))
    if text[2] - text[0] < COLLAR_CALLOUT_MIN_READ:
        raise RuntimeError(
            f"{label} read {text[2] - text[0]:.4f} m wide, under the "
            f"{COLLAR_CALLOUT_MIN_READ:.4f} its widest line needs: a misread"
        )
    return ink, text


@_telemetry.traced("drawing.collar_callout_clear")
def _clear_collar_callout(
    adapter: Any, collar: Any, finish: Any, dimensions: Mapping[str, Any]
) -> None:
    """Lift the collar's stock callout above the pivot-journal finish, then
    prove it from measured ink: its dimension line still on the ring, its
    text clear of the symbol and of every other dimension's text, its leader
    through none of them, no finish leader or dimension line by its text,
    and inside the frame."""
    label = "collar stock callout"
    rebuild_drawing(adapter, label=f"measure {label}")
    finish_annotation = finish.GetAnnotation()
    finish_box = gdt_box(adapter, finish_annotation, label="pivot journal finish")
    finish_leader = leader_segments(finish_annotation)
    _telemetry.info(f"pivot journal finish leader: {finish_leader}")
    _ink, placed = _collar_text(adapter, collar, label)
    dy = _collar_callout_dy(placed, finish_box, finish_leader)
    if dy:
        move_annotation(adapter, collar, 0.0, dy, label=label)
    ink, text = _collar_text(adapter, collar, label)
    if abs(text[0] - placed[0]) > PLACE_SETTLE_M:
        raise RuntimeError(
            f"{label} moved sideways ({placed[0]:.4f} -> {text[0]:.4f}): its "
            "dimension line left the collar ring"
        )
    neighbours = {"pivot journal finish": finish_box}
    lines = {"pivot journal finish": finish_leader}
    for name, dimension in dimensions.items():
        neighbours[name] = _dimension_text_box(dimension, name)
        lines[name] = dimension_segments(dimension)
    require_clear(label, text, neighbours)
    require_leader_clear(ink, neighbours)
    near = [
        name
        for name, segments in lines.items()
        if any(distance_to_box(segment, text) < CLEAR_GAP_M for segment in segments)
    ]
    if near:
        raise RuntimeError(f"{near} lines run by the {label} {text}")
    require_inside(label, text, sheet_region(adapter))
    _telemetry.success(
        f"{label} lifted {dy:.4f} m, clear of the pivot journal finish and "
        f"{len(dimensions)} dimensions"
    )


def _prepare_d_section(adapter: Any, view: Any, section: DSection) -> None:
    """Keep only the D's cut face, at the section's own independent scale."""
    bound = _early_bound(view, "IView")
    bound.UseParentScale = False
    bound.UseSheetScale = 0
    bound.ScaleRatio = double_array([float(section.scale[0]), float(section.scale[1])])
    cut = _early_bound(bound.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label=f"section {section.label} cut face and scale")
    ratio = tuple(float(value) for value in bound.ScaleRatio)
    if (
        bool(bound.UseParentScale)
        or int(bound.UseSheetScale) != 0
        or not math.isclose(ratio[0] / ratio[1], section.scale[0] / section.scale[1])
    ):
        raise RuntimeError(f"section {section.label} scale did not persist: {ratio}")
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError(f"section {section.label} kept geometry beyond the cut")
    if bool(cut.GetPartialSection()):
        raise RuntimeError(f"section {section.label} is a partial section")


class PlacedSection(NamedTuple):
    """The built section and the ink its layout proof measures."""

    section: DSection
    view: Any
    face: Box
    dimensions: tuple[Any, ...]
    caption: Box


def _axis_sign(adapter: Any, side: Any) -> int:
    """+1 when stations run along model +Z, -1 along -Z, read off the side view.

    A station is measured from the front face (the big end, sheet x
    BIG_END_X) toward the tip, leftward on the sheet.  The part owns the sign
    of its axis (``_end_circle`` matches |z|), so it is measured here, and a
    front face projecting anywhere but the big end fails before a cut is drawn
    on a wrong station."""
    front, along = model_points_in_view(
        adapter,
        side,
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.001)),
        label="shaft axis direction",
        names=("front face", "1 mm along +Z"),
    )
    step = along[0] - front[0]
    if (
        abs(front[0] - BIG_END_X) > 5e-4
        or abs(front[1] - SIDE_CENTER[1]) > 5e-4
        or abs(abs(step) - 0.001 * SIDE_SCALE[0] / SIDE_SCALE[1]) > 1e-6
        or abs(along[1] - front[1]) > 1e-6
    ):
        raise RuntimeError(
            f"the side view does not run the axis along sheet x from the big end: "
            f"front face {front}, 1 mm along +Z {along}"
        )
    return 1 if step < 0 else -1


def _station_point(
    station_mm: float, offset: float, sign: int
) -> tuple[float, float, float]:
    """The model point ``offset`` metres off the axis, in the side view's
    plane (model Y), at ``station_mm`` from the front face."""
    return (0.0, offset, sign * station_mm / 1000.0)


def _note_box(note: Any) -> Box:
    extent = tuple(float(value) for value in note.GetExtent())
    return (extent[0], extent[1], extent[3], extent[4])


def _caption_anchor(box: Box) -> tuple[float, float]:
    """A caption box's top centre."""
    return ((box[0] + box[2]) / 2.0, box[3])


def _place_view_caption(
    adapter: Any,
    view: Any,
    target: tuple[float, float],
    *,
    label: str,
) -> Box:
    """Move a view's native caption so its box's top centre lands on
    ``target``, its linked fields intact, and return the measured box.

    The caption's position is not its box, so the move is measured
    (``INote.GetExtent``), as draw_cone_swing_platform places its labels.
    The sheet scale is pinned first; finalization re-applying it must not
    move a dynamic caption after this readback."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    notes = tuple(_read_member(_early_bound(view, "IView"), "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label}, found {len(notes)} notes")
    note = _early_bound(notes[0], "INote")
    linked = str(note.PropertyLinkedText or "")
    if not linked:
        raise RuntimeError(f"{label} carries no linked view fields")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    for _attempt in range(4):
        box = _note_box(note)
        point = _caption_anchor(box)
        error = (target[0] - point[0], target[1] - point[1])
        if max(abs(error[0]), abs(error[1])) < CAPTION_SETTLE_M:
            break
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x + error[0], y + error[1], z):
            raise RuntimeError(f"failed to move the {label}")
        rebuild_drawing(adapter, label=f"place {label}")
    else:
        raise RuntimeError(
            f"{label} stayed at {box}, its top centre requested at {target}"
        )
    if str(note.PropertyLinkedText or "") != linked:
        raise RuntimeError(f"{label} lost its linked view fields")
    _telemetry.info(f"{label}: top centre at {target}, box {box}")
    return box


def _delete_centre_mark(adapter: Any, view: Any, section: DSection) -> None:
    """Delete the section's centre mark, if SolidWorks gave it one, and read
    none back (a full section gets one)."""
    label = f"section {section.label} centre mark"
    iview = _early_bound(view, "IView")
    marks = tuple(iview.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if not marks:
        _telemetry.info(f"{label}: none drawn")
        return
    if len(marks) != 1:
        raise RuntimeError(f"expected at most one {label}, found {len(marks)}")
    draw = adapter.currentModel
    draw.ClearSelection2(True)
    if not _early_bound(marks[0], "IAnnotation").Select2(False, 0):
        raise RuntimeError(f"cannot select {label}")
    draw.EditDelete()  # VT_VOID: the re-read below is the proof
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"delete {label}")
    left = tuple(iview.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if left:
        raise RuntimeError(f"{label} survived deletion ({len(left)} left)")
    _telemetry.info(f"{label}: deleted")


def _cut_endpoints(
    adapter: Any, parent: Any, section: DSection, sign: int
) -> tuple[tuple[float, float], tuple[float, float]]:
    """The cutting line's sheet endpoints on the side view, bottom first:
    drawn upward, the arrows look toward the big end."""
    offset = section.reach * SIDE_SCALE[1] / SIDE_SCALE[0]
    first, second = model_points_in_view(
        adapter,
        parent,
        (
            _station_point(section.station_mm, -offset, sign),
            _station_point(section.station_mm, offset, sign),
        ),
        label=f"section {section.label} cutting line",
        names=("one end", "other end"),
    )
    return (first, second) if first[1] < second[1] else (second, first)


@_telemetry.traced("drawing.d_sections")
def _add_d_sections(adapter: Any, side: Any, sign: int) -> list[PlacedSection]:
    """Cut the keyed land across and print its keyseat in the section, its
    centre mark deleted and its caption hung under it.

    ``curate_view_dimensions`` fails the build if a section's dimensions
    do not arrive, so every cut on the sheet carries its size."""
    placed = []
    for section in D_SECTIONS:
        start, end = _cut_endpoints(adapter, side, section, sign)
        view = create_section_view(
            adapter,
            side,
            line_start=start,
            line_end=end,
            view_xy=section.centre,
            section_label=section.label,
            scale=section.scale,
            partial=False,
            label=f"land {section.land} section",
        )
        _prepare_d_section(adapter, view, section)
        names = SECTION_DIMENSION_NAMES[section.land]
        keep = {names[0]: D_SECTION_KEEP[names[0]]}
        if section.land == KEYED_LAND:
            keyseat_x = _keyseat_side_x(adapter, view, section, sign)
            s_x, s_y = keep[names[0]]
            away = -math.copysign(KEYSEAT_S_SHIFT, keyseat_x - section.centre[0])
            keep[names[0]] = (s_x + away, s_y + KEYSEAT_S_FLAG_LIFT)
            keep[names[1]] = (keyseat_x, section.centre[1] + KEYSEAT_WIDTH_RISE)
        dimensions = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=f"section {section.label}",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
        by_name = {dimension_name(adapter, dimension): dimension for dimension in dimensions}
        kept = tuple(by_name[name] for name in names)
        _delete_centre_mark(adapter, view, section)
        face = _section_face(adapter, view, section, sign)
        caption = _place_view_caption(
            adapter,
            view,
            (section.centre[0], face[1] - SECTION_CAPTION_GAP),
            label=f"section {section.label} caption",
        )
        _set_dimension_suffixes(
            adapter,
            kept,
            {
                name: text
                for name, text in KEYSEAT_MATE_SUFFIXES.items()
                if name in names
            },
        )
        if section.land == KEYED_LAND:
            set_dimension_callouts(
                adapter,
                [kept[0]],
                {names[0]: SECTION_ABOVE_CALLOUTS[names[0]]},
                location="above",
            )
            _set_arrows_inside(kept[0], f"section {section.label} {names[0]}")
            rebuild_drawing(adapter, label=f"section {section.label} arrows inside")
        placed.append(PlacedSection(section, view, face, kept, caption))
    return placed


def _set_arrows_inside(raw: Any, label: str) -> None:
    """Put a dimension's arrows inside its extension lines and read it back."""
    annotation = _early_bound(raw, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.ArrowSide = ARROWS_INSIDE
    if int(display.ArrowSide) != ARROWS_INSIDE:
        raise RuntimeError(f"{label}: arrows did not move inside")


def _keyseat_side_x(adapter: Any, view: Any, section: DSection, sign: int) -> float:
    """Sheet x of the land's +X edge on its section, where the keyseat is
    (the section states which side)."""
    (keyseat,) = model_points_in_view(
        adapter,
        view,
        ((SECTION_DIAS[section.land] / 2000.0, 0.0, sign * section.station_mm / 1000.0),),
        label=f"section {section.label} keyseat side",
    )
    return keyseat[0]


def _section_face(adapter: Any, view: Any, section: DSection, sign: int) -> Box:
    """The land's cut face on its section, boxed round the land's full circle.

    A section's outline is no measure of its ink: SolidWorks boxes the whole
    part's depth (the Ø15.9 collar) and the cutting line's length, plus 5.6
    mm (leaf 20260929T212933Z-1-e35ef0ba: a section's outline ran 29 mm either
    side of its 9.5 mm face, past the right border).  The face is centred on the
    axis, which must stand where the layout put the section."""
    (centre,) = model_points_in_view(
        adapter,
        view,
        (_station_point(section.station_mm, 0.0, sign),),
        label=f"section {section.label} axis",
    )
    if math.dist(centre, section.centre) > 0.001:
        raise RuntimeError(
            f"section {section.label} centres its face at {centre}, not {section.centre}"
        )
    half = SECTION_DIAS[section.land] / 2000.0 * section.scale[0] / section.scale[1]
    return (centre[0] - half, centre[1] - half, centre[0] + half, centre[1] + half)


def _section_line_ink(view: Any) -> dict[str, dict[str, Box]]:
    """Each cutting line a view carries: its two arrows and two letters as
    boxes, by section letter.  ``GetArrowInfo`` gives each arrow's start and
    end, ``GetTextInfo`` each letter's upper-left corner, both on the sheet;
    a letter is boxed one character height square (the audit's 6.35 mm "A"
    measured 5.9 wide)."""
    ink: dict[str, dict[str, Box]] = {}
    for raw in _read_member(_early_bound(view, "IView"), "GetSectionLines") or ():
        cut = _early_bound(raw, "IDrSection")
        name = str(cut.GetLabel())
        height = float(_early_bound(cut.GetTextFormat(), "ITextFormat").CharHeight)
        arrows = [float(value) for value in cut.GetArrowInfo() or ()]
        texts = [float(value) for value in cut.GetTextInfo() or ()]
        if len(arrows) != 12 or len(texts) != 6:
            raise RuntimeError(f"section line {name}: arrows {arrows}, letters {texts}")
        pad = SECTION_ARROW_HALF_WIDTH
        boxes: dict[str, Box] = {}
        for index, base in enumerate((0, 6), start=1):
            x0, y0, x1, y1 = (
                arrows[base],
                arrows[base + 1],
                arrows[base + 3],
                arrows[base + 4],
            )
            boxes[f"section {name} arrow {index}"] = (
                min(x0, x1) - pad,
                min(y0, y1) - pad,
                max(x0, x1) + pad,
                max(y0, y1) + pad,
            )
        for index, base in enumerate((0, 3), start=1):
            x, y = texts[base], texts[base + 1]
            boxes[f"section {name} letter {index}"] = (x, y - height, x + height, y)
        _telemetry.info(f"section line {name} ink: {boxes}")
        ink[name] = boxes
    return ink


def _union(boxes: Iterable[Box]) -> Box:
    boxes = list(boxes)
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _view_outline(view: Any) -> Box:
    return tuple(float(value) for value in _early_bound(view, "IView").GetOutline())


def _land_boxes(adapter: Any, view: Any, sign: int, *, label: str) -> dict[str, Box]:
    """Each gear land's silhouette on ``view``, clipped to its outline."""
    outline = _view_outline(view)
    starts = (COLLAR_END_STATION, *SECTION_ENDS[1:-1])
    boxes = {}
    for land, start in enumerate(starts, start=KEYED_LAND):
        radius = SECTION_DIAS[land] / 2000.0
        corners = model_points_in_view(
            adapter,
            view,
            (
                _station_point(start, -radius, sign),
                _station_point(SECTION_ENDS[land], radius, sign),
            ),
            label=f"{label} land {land}",
        )
        box = (
            max(min(x for x, _ in corners), outline[0]),
            max(min(y for _, y in corners), outline[1]),
            min(max(x for x, _ in corners), outline[2]),
            min(max(y for _, y in corners), outline[3]),
        )
        if box[0] < box[2] and box[1] < box[3]:
            boxes[f"{label} land {land}"] = box
    return boxes


def _require_apart(groups: Mapping[str, Mapping[str, Box]]) -> None:
    """Every box of each group clear of every box of every other group."""
    names = list(groups)
    for index, name in enumerate(names):
        others = {
            box_name: box
            for other in names[index + 1 :]
            for box_name, box in groups[other].items()
        }
        for box_name, box in groups[name].items():
            require_clear(box_name, box, others)


@_telemetry.traced("drawing.section_layout_proof")
def _prove_section_layout(
    adapter: Any,
    *,
    side: Any,
    tip_end: Any,
    iso: Any,
    sections: Sequence[PlacedSection],
    dimensions: Mapping[str, Any],
    sign: int,
) -> None:
    """Prove from measured ink what the codex review of #1128 found broken:
    every section, caption, cutting line, the tip end view and the pictorial
    inside the frame and off the title block; the cutting line's arrows and
    letters clear of each other, of every dimension text and of the lands;
    and each section's caption and dimensions clear of its neighbours."""
    region = sheet_region(adapter)
    template = DRAWING_TEMPLATES[SPEC.layout]
    keep_out = {
        "title block": (
            template.title_block_left_m,
            0.0,
            template.width_m,
            template.title_block_top_m,
        )
    }
    texts = {
        name: _dimension_text_box(annotation, name)
        for name, annotation in dimensions.items()
    }
    side_lines = _section_line_ink(side)
    expected = sorted(s.label for s in D_SECTIONS)
    if sorted(side_lines) != expected:
        raise RuntimeError(
            f"cutting lines: side view {sorted(side_lines)}; expected {expected}"
        )
    groups: dict[str, dict[str, Box]] = {}
    for placed in sections:
        label = f"section {placed.section.label}"
        if _early_bound(placed.view, "IView").GetAnnotationsByType(
            _CENTER_MARK_ANNOTATION
        ):
            raise RuntimeError(
                f"{label} carries a centre mark again after its deletion"
            )
        texts_in_section = {
            f"{label} dimension {index}": _dimension_text_box(
                dimension, f"{label} dimension {index}"
            )
            for index, dimension in enumerate(placed.dimensions, start=1)
        }
        cell = {
            f"{label} face": placed.face,
            f"{label} dimension 1": texts_in_section[f"{label} dimension 1"],
            f"{label} caption": placed.caption,
        }
        if placed.section.land == KEYED_LAND:
            # A-A's S and its NOTE flag above it stand over the face; as one
            # box with the face they would reach up beside the width's row.
            # So S rides on its own, clear of the face and of the width.
            del cell[f"{label} dimension 1"]
        # A-A's keyseat width rides above the section (KEYSEAT_WIDTH_RISE):
        # its own box, clear of every other group, not part of A's cell.
        riders = {
            name: box for name, box in texts_in_section.items() if name not in cell
        }
        if placed.section.land == KEYED_LAND:
            s_name = f"{label} dimension 1"
            require_clear(
                s_name,
                riders[s_name],
                {
                    f"{label} face": placed.face,
                    **{name: box for name, box in riders.items() if name != s_name},
                },
            )
        require_clear(
            f"{label} caption",
            placed.caption,
            {
                name: box
                for name, box in (*cell.items(), *riders.items())
                if name != f"{label} caption"
            },
        )
        groups[label] = {label: _union(cell.values()), **riders}
    lands = _land_boxes(adapter, side, sign, label="side view")
    for name, boxes in side_lines.items():
        for box_name, box in boxes.items():
            if "letter" in box_name:
                require_clear(box_name, box, lands)
        groups[f"cutting line {name}"] = boxes
    groups["tip end view"] = {"tip end view": _view_outline(tip_end)}
    groups["isometric"] = {"isometric": _view_outline(iso)}
    groups["dimension texts"] = texts
    for group in groups.values():
        for name, box in group.items():
            require_inside(name, box, region)
            require_clear(name, box, keep_out)
    _require_apart(groups)
    _telemetry.success(
        f"section layout proved: {len(sections)} sections, "
        f"{len(side_lines)} cutting lines, {len(texts)} dimension texts"
    )


# swUserPreferenceDoubleValue_e.swDetailingWitnessLineExtension, the extension
# lines' run past the dimension line (read from swconst.tlb), document scope
# (swDetailingNoOptionSpecified).  The project standard runs them 0.9 mm past
# (r4b, 20261018T072511131Z: A-A's dimension line at y 174.7 mm, its
# extension lines to 175.6, the text's foot at 175.7), and every across-flat's
# text is wider than its flat, so the lines' ends struck the band and the gear
# names in all four sections (machinist review r2 and r4b).  0.4 mm past keeps
# a visible overrun and leaves the text's foot 0.6 mm clear.
_PREF_WITNESS_LINE_EXTENSION = 14
_PREF_OPTION_NONE = 0
WITNESS_LINE_EXTENSION = 0.0004


def _pin_witness_line_extension(drawing_model: Any) -> None:
    """Set this sheet's extension-line overrun, read back, raise on mismatch."""
    extension = drawing_model.Extension
    key, scope = _PREF_WITNESS_LINE_EXTENSION, _PREF_OPTION_NONE
    before = float(extension.GetUserPreferenceDouble(key, scope))
    ok = extension.SetUserPreferenceDouble(key, scope, WITNESS_LINE_EXTENSION)
    applied = float(extension.GetUserPreferenceDouble(key, scope))
    if not ok or abs(applied - WITNESS_LINE_EXTENSION) > 1e-7:
        raise RuntimeError(
            f"failed to set the extension-line overrun to {WITNESS_LINE_EXTENSION} m "
            f"(set returned {ok!r}, document reads {applied}, was {before})"
        )
    _telemetry.info(f"extension-line overrun {before * 1000:.2f} -> {applied * 1000:.2f} mm")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear-shaft source", await adapter.open_model(str(SOURCE)))
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit("dt-cone-gear-shaft"),
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="cone gear shaft package")
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate shaft controls sheet")
    _pin_witness_line_extension(drawing_model)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft; stepped turned steel; gear seats",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    donor = place_view(adapter, str(SOURCE), "*Front", *DONOR_CENTER, scale=SIDE_SCALE)
    tip_end = place_view(
        adapter, str(SOURCE), "*Front", *TIP_END_VIEW_CENTER, scale=SIDE_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The isometric too (PR #1436 fleet invariant): finalization's shaded
    # pass is then a real mode change, so its cosmetic edges print at quality.
    for view in (side, donor, tip_end, iso):
        set_hidden_lines_removed(adapter, view)

    pivot_face = _cylindrical_face(adapter, side, JOURNAL_DIA)
    _add_shaft_axis(adapter, side)

    # The donor is curated FIRST so the diameters cannot be claimed (and then
    # deleted) by a view that cannot show them.
    donor_annotations = curate_view_dimensions(
        adapter,
        donor,
        keep=DONOR_KEEP,
        view_label="diameter donor",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The socket's native hole callout, on the view that faces its rim.
    socket = _add_socket_callout(adapter, tip_end)
    annotations = list(side_annotations)
    collar = None
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        moved = _move_dimension(
            adapter, annotation, side, SIDE_DIAMETERS[name], source_view=donor
        )
        if name == "CollarDia":
            collar = moved
        if name in NEAR_SIDE_DIAMETERS:
            set_near_side_diameter(moved, f"{name} near-side diameter")
        if name in REFERENCE_DIAMETERS:
            # The bar's own size as supplied: an untoleranced 5/8 fraction
            # reference; its stock statement rides below (DIMENSION_CALLOUTS).
            supplier_reference_dimension(
                adapter,
                _early_bound(moved, "IAnnotation").GetSpecificAnnotation(),
                label=f"{name} stock reference",
                units="in",
                precision=DRAWING_PRECISION_BY_NAME[name],
                expected_mm=COLLAR_DIA,
                presentation="diameter",
                fraction_denominator=COLLAR_DIA_FRACTION_DENOMINATOR,
            )
        annotations.append(moved)
    # Every diameter is now native to the view that shows its shoulder; an
    # empty end view carries no manufacturing information.
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    if collar is None:
        raise RuntimeError("the donor view gave no CollarDia dimension")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _set_dimension_suffixes(adapter, annotations, DIMENSION_SUFFIXES)
    sign = _axis_sign(adapter, side)
    sections = _add_d_sections(adapter, side, sign)
    # Precision hidden-lines-removed on every section, after its dimensions
    # are attached: left on its parent's display, a section printed its round
    # as visible straight segments (machinist review r1, r2, r4b).
    for placed in sections:
        set_hidden_lines_removed(adapter, placed.view)
    overall = _add_overall_reference(adapter, side)
    # Every other dimension on the side view, which the collar callout's
    # proof measures it against.
    collar_neighbours = {
        dimension_name(adapter, annotation): annotation
        for annotation in annotations
        if annotation is not collar
    }
    collar_neighbours["front-to-tip overall"] = overall.GetAnnotation()
    if len(collar_neighbours) != len(annotations):
        raise RuntimeError(
            f"side view dimensions {sorted(collar_neighbours)} do not name "
            f"the {len(annotations) - 1} beside the collar uniquely"
        )

    # Leader anchor for the land that RUNS (sheet metres): the journal's top
    # flank, PIVOT_FINISH_ATTACH_INSET in from the faced end.
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    pivot_top = (
        big_end_x - PIVOT_FINISH_ATTACH_INSET,
        SIDE_CENTER[1] + SECTION_DIAS[0] / 2000.0,
    )
    pivot_finish = add_surface_finish(
        adapter,
        side,
        symbol_xy=PIVOT_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )
    _clear_collar_callout(adapter, collar, pivot_finish, collar_neighbours)
    _prove_section_layout(
        adapter,
        side=side,
        tip_end=tip_end,
        iso=iso,
        sections=sections,
        dimensions={
            **collar_neighbours,
            "CollarDia": collar,
            "socket callout": socket,
        },
        sign=sign,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Shaft Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales={SHEET_NAMES[0]: SHEET_SCALE},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

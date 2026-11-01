r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and make-critical annotations;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The support is a painted gray-iron frame with a trapezoidal wall, two opposed
pockets leaving a .50 central web, a through cavity, a chamfered window rim,
four 5/16 clearance holes through its mounting foot, and the rocker brackets'
two #8-32 seats in its top face, transferred from the set brackets at
assembly. The sheet runs 1:2 in decimal inch, with each view's scale pinned explicitly.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fr_rocker_arm_support.py fr-rocker-arm-support
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    remove_notes_matching,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _early_bound
import _config
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_dimension_precision,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_owner_dimensions,
    part_sketches_shown,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_point_in_view
from _part_properties import part_drawing_unit
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_tables import create_view_theoretical_datum, insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _gtol_cylinder import CylinderFace
from _gtol_face_resolve import resolve_faces
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_fr_rocker_arm_support import (
    BIG,
    BOSS_DEPTH,
    CAV,
    CHAMFER,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    HALF_Y,
    HOLD_DOWN_LOCAL_HALF_X,
    HOLD_DOWN_LOCAL_HALF_Z,
    HOLE_DIA,
    HOLES,
    NARROW,
    WEB,
    WIDE,
)
from fr_rocker_arm_support_drawing_spec import SURFACE_FINISHES
from rocker_bracket_seat_layout import SEAT_LOCAL_X, SEAT_SPEC, WEB_PLACES


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["fr_rocker_arm_support"]
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

SHEET_SCALE = (1.0, 2.0)

# Sheet layout (meters). A 177.8 mm casting with four views needs a 1:2 ASME B
# sheet. Section A-A replaces the side view, exposing the opposed pocket floors
# and web; the clearance-hole setup stays aligned below the front. The front
# shifts left of the section, and the bottom view drops to open an exterior
# annotation lane below the front without breaking the projected group.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.105, 0.185)
RIGHT_CENTER = (0.205, 0.185)
BOTTOM_CENTER = (0.105, 0.075)
ISO_CENTER = (0.350, 0.201)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters). Every front-view callout is outside the part silhouette:
# overall size above, nested pocket sizes below, radii beside their corners.
FRONT_KEEP = {
    "Depth": (0.105, 0.258),
    # Its leader's shelf stands 7 mm above the pocket's bottom wall, whose
    # PocketBottomStation extension line runs out left under it (r6 render:
    # at 0.150 the shelf sat 0.8 mm above that line).
    "PocketRadius": (0.035, 0.157),
    # CornerFillet's dimension belongs to the cavity's top-right corner (the
    # fix3 render), so the text sits up-right of that corner, on the arc's
    # own bisector. From the left column its leader crossed the whole cavity
    # and landed on the far side of the fillet's circle, off the arc.
    "CavityRadius": (0.161, 0.240),
    # Each stacked width prints its text just above its own dimension line,
    # so the lower one needs a full band: at 0.118 the 127.0 line ran
    # through "165.1" (fix3 render).
    "WinWidth": (0.105, 0.110),
    "CavWidth": (0.105, 0.128),
    # RimChamfer's size lands on its first edge, the +X end face's foot edge,
    # which the front view sees end-on at its bottom-right outside corner
    # (build_fr_rocker_arm_support.CHAMFER_EDGES). The dimension line stands
    # just outside that corner; the text rides an OffsetText leader up into
    # the lane between the front view and the section.
    "RimChamferSize": (
        FRONT_CENTER[0] + BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0 + 0.0025,
        FRONT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0 - 0.0025,
    ),
    # The cavity's and the pockets' locations (CavityLocationReference, blanked
    # in the part) stand above the view's left end, clear of the R6.35 low
    # left: from the -X end face, the pocket wall's 7.70 on the inner band
    # (its text outside left, its pocket-wall extension line stopping below
    # the outer band) and the cavity wall's 26.7 on the outer one, under the
    # 180.5; from the top face, the cavity's top wall left of the view. The
    # 7.70's BOTH SIDES stands left of the 25.4's dimension line and its line
    # above the 25.4's outside arrow tail (r9 review: the tail struck the
    # callout's E and crossed the pocket station's line).
    "PocketEndStation": (0.0365, 0.244),
    "CavityEndStation": (0.0668, 0.249),
    "CavityTopStation": (0.052, 0.2231),
    # The pockets' bottom wall up from the mounting face (r6 review: the
    # pocket had no vertical location). Its 6.35 spans only 3.2 mm of sheet,
    # so its dimension line runs on down past the mounting face's extension
    # line, and SolidWorks stands the text block, BOTH SIDES under it, LEFT of
    # that line, its right edge on it. At x 0.036 the block's left edge
    # crossed the sheet's left inner border by 1.6 mm (r7 review and layout
    # audit), so the line stands 10 mm further in, still left of the view and
    # of the 165.1's extension line and below the R6.35's leader.
    "PocketBottomStation": (0.046, 0.132),
}
# The cavity corner CornerFillet's dimension attaches to, as sheet signs.
CAVITY_RADIUS_CORNER = (1, 1)
# RimChamfer is ONE model feature: 1.27 x 45 on every edge of the two slant
# faces and the two end faces (all twelve outside edges plus both pocket
# rims) and on the cavity rims on both web faces. Its one size sits on an
# outside corner, so the caption names everything else it governs; drawn
# outside chamfers with no size read as breaks past the title block's 0.25
# MAX (machinist review, MHA-FR-05). The r7 review's "delete the chamfer"
# (over_spec) was rejected by Main: the callout stays.
DIMENSION_CALLOUTS = {
    "PocketRadius": "8X",
    "CavityRadius": "4X",
    # One SQ size covers both opposed pockets; the front view shows only the
    # near one (r6 machinist review).
    "WinWidth": "SQ POCKET BOTH SIDES",
    "CavWidth": "SQ CAVITY THRU",
    "RimChamferSize": " X 45 DEG\nALL OUTSIDE\nEDGES AND\nPOCKET AND\nCAVITY RIMS",
    # One location covers both opposed pockets, as the SQ size does.
    "PocketEndStation": "BOTH SIDES",
    "PocketBottomStation": "BOTH SIDES",
    # One flat edge prints for both (the section is symmetric about the web);
    # off its nearer web face it keeps the transferred seats clear of the
    # web's faces (owner Q13d, rocker_bracket_seat_layout's stack). r6 review:
    # "CENTERS" read as the mating part being centred, not what the 2.12 is.
    "TopFlatPlusZStation": (
        "BOTH SIDES\n"
        f"KEEPS {_config.parts('ch-pivot-bracket')['number']}\nSEAT TAPS IN WEB"
    ),
}
# The sheet's own places. RimChamferSize's, the seat REF
# stations' and the locations' are the PART's
# (build_fr_rocker_arm_support.DRAWING_PRECISION): read back
# (PART_PRECISION), never set here.
# Decimal inch: every size .XX (the 7.12 length's half locates the cavity
# and the pockets at .XX).
DIMENSION_PRECISION = {
    "Depth": 2,
    "WinWidth": 2,
    "CavWidth": 2,
    "PocketRadius": 2,
    "CavityRadius": 2,
    "WallHeight": 2,
    "FootSpan": 2,
    # A held thickness, .50 at the routine ±.01: the seats' thread-wall
    # stack reads the same places (rocker_bracket_seat_layout).
    "WebThickness": WEB_PLACES,
    "FootThickness": 2,
}


def imported_precision(kept: Any) -> dict[str, int]:
    """Precision for the imported model dimensions one curate pass keeps. The
    sheet-made ones (web, foot) set their own when they are created, after the
    import; set_dimension_precision fails on a name it cannot find, which
    is how the #743 rail's RailDepth entry broke r743-rocker-fix."""
    return {
        name: digits for name, digits in DIMENSION_PRECISION.items() if name in kept
    }


# The part-authored places by dimension name (each name is unique on the part).
PART_PRECISION = {
    name: digits
    for dimensions in DRAWING_PRECISION.values()
    for name, digits in dimensions.items()
}


def _assert_part_precision(adapter: Any, annotations: list[Any], kept: Any) -> None:
    """Read back the places the part build authored for the dimensions one
    curate pass ``kept`` (drawing-simplicity-policy.md): the sheet never
    rewrites them, and an import that lost them fails here instead of
    printing the sheet default."""
    assert_imported_precision(
        adapter,
        annotations,
        {name: digits for name, digits in PART_PRECISION.items() if name in kept},
    )


# The bracket seats print as ONE native Hole Wizard callout (Codex #936,
# PRRT_kwDOPHDy386mRSOJ): SolidWorks reads the count, thread and both depths
# from BracketSeats, so a model change moves the print. Only the transfer
# instruction is text, and its closing line break puts the native size on a
# row of its own (13be2ca03).
SEAT_CALLOUT_PROCESS = (
    f"TRANSFER FROM {_config.parts('ch-pivot-bracket')['number']}\nAT ASSEMBLY;\n"
)
# The tap drill prints .XXX (.136); both depths .XX (.46 thread, .59 drill).
SEAT_CALLOUT_PRECISION = {
    "hw-tapdrldia": 3,
    "hw-tapdrldepth": 2,
    "hw-threaddepth": 2,
}
SEAT_CALLOUT_X_MM = max(SEAT_LOCAL_X)
# The seats are drilled from the rail top, which no principal view shows, so
# they get VIEW B (Main's ruling): a partial top view of the rail strip,
# relocated to the band below Section A-A and right of the bottom view, named
# by a letter arrow looking down on the front view's top edge. The crop keeps
# the rail top (half-width NARROW) and stops short of the foot holes the view
# sees through the cavity: at 16 mm it cut them, leaving half hole symbols on
# its edges (r743-p1s-B2 render). The callout text sits right of VIEW B,
# between the hole table and the title block; its rows centre on its y.
VIEW_B_CENTER = (0.210, 0.108)
VIEW_B_CROP_HALF_Z_MM = 12.0
FOOT_HOLE_INNER_Z = min(abs(z) for _, z in HOLES) - HOLE_DIA / 2.0
if not NARROW < VIEW_B_CROP_HALF_Z_MM < FOOT_HOLE_INNER_Z:
    raise AssertionError(
        f"VIEW B fence half-width {VIEW_B_CROP_HALF_Z_MM} must keep the rail top "
        f"({NARROW}) and clear the foot holes ({FOOT_HOLE_INNER_Z:.2f})"
    )
VIEW_B_CAPTION = f"VIEW B\nSCALE {SHEET_SCALE[0]:g}:{SHEET_SCALE[1]:g}"
VIEW_B_CAPTION_XY = (
    VIEW_B_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
    VIEW_B_CENTER[1] - VIEW_B_CROP_HALF_Z_MM * VIEW_SCALE / 1000.0 - 0.004,
)
SEAT_CALLOUT_XY = (0.300, 0.081)
# The seats' REF stations (SeatStationReference, blanked in the part): each
# text stands just above VIEW B's fence, outboard of its end face, so its
# dimension line runs from the seat's centre mark out past the end line. The
# east text clears the hole table's left edge; the west one the front view's
# pocket-width extension lines and the section label.
VIEW_B_REF_RISE = 0.0055
VIEW_B_REF_OUTBOARD = 0.0045
VIEW_B_KEEP = {
    name: (
        VIEW_B_CENTER[0]
        + sign * (BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0 + VIEW_B_REF_OUTBOARD),
        VIEW_B_CENTER[1]
        + VIEW_B_CROP_HALF_Z_MM * VIEW_SCALE / 1000.0
        + VIEW_B_REF_RISE,
    )
    for name, sign in (("SeatEastStation", 1), ("SeatWestStation", -1))
}
# The letter matches the section's A (~5 mm) and stands square above its
# tip, clear of the section line (the cone-tip-block pattern). VIEW_B_ARROW
# is (note upper-left, leader tip) in sheet metres.
VIEW_LETTER_HEIGHT = 0.005
VIEW_B_ARROW = (
    (
        FRONT_CENTER[0] - 0.020 - 0.36 * VIEW_LETTER_HEIGHT,
        FRONT_CENTER[1] + HALF_Y * VIEW_SCALE / 1000.0 + 0.013,
    ),
    (FRONT_CENTER[0] - 0.020, FRONT_CENTER[1] + HALF_Y * VIEW_SCALE / 1000.0),
)
# The web thickness text sits right of the section, clear of the slanted
# wall and of the 177.8 dimension line at x 0.240; at x 0.221 it printed
# across the wall line (fix3 render).
WEB_TEXT_XY = (RIGHT_CENTER[0] + 0.026, RIGHT_CENTER[1] - 0.0122)
# The foot's 6.35 spans only 3.2 mm of sheet, too little for its text: at
# y 0.142 the text sat between the extension lines with its own dimension
# line through it (fix4 render). It prints just above the foot's top
# extension line instead, in the gap between the front view and the
# section's slanted wall.
FOOT_TEXT_XY = (RIGHT_CENTER[0] - 0.025, RIGHT_CENTER[1] - 0.0365)
# PocketFloorFillet prints no size: the title block's INSIDE CORNERS R1.0 MAX
# governs the pocket floor corners (ENFORCE review 2026-10-23: a local R0.8
# MAX named no mate or function). One top-flat edge prints off its
# nearer web face (WebLocationReference, blanked in the part; owner Q13d),
# its BOTH SIDES covering the other (r6 review), on the row above the
# section: the span is only about 1 mm of sheet, so its text stands outboard
# of the +Z edge, its reason rows hanging below the value. The 63.5 prints
# right of the web face's extension line WebFaceStation runs down to just
# above it, its row no lower than r8's (r10 review: 1 mm lower, its left
# extension line's overshoot struck the SECTION A-A label's E).
# WebFaceStation (to the web's face) measures from the base's -Z edge, the
# section's left.
RIGHT_KEEP = {
    "WallHeight": (0.256, 0.185),
    "FootSpan": (0.2125, 0.133),
    "TopFlatPlusZStation": (0.2385, 0.2475),
    "WebFaceStation": (0.1958, 0.1375),
}
# The chamfer text on its OffsetText leader (the text centres on its point),
# in the lane between the front view and the section, low enough that the
# leader down to the front view's corner stays short.
RIM_CHAMFER_TEXT_XY = (0.1717, 0.190)

# Top-left anchor; the native four-row table grows down and right while
# remaining clear of the isometric and title block.
HOLE_TABLE_ANCHOR = (0.270, 0.130)
HOLE_TABLE_DATUM_XZ_MM = (-BOSS_DEPTH / 2.0, -WIDE)
# Native hole tags land up-right of their holes. At the bottom view's right
# end that printed A3 and A4 across the pocket's hidden end lines (fix3
# render), so both move to the mirror spot left of their holes: twice the
# 4.6 mm hole-to-tag gap plus the 5.8 mm tag width, measured on A4 there.
RIGHT_END_HOLE_TAGS = ("A3", "A4")
HOLE_TAG_MIRROR_SHIFT = -0.0150
# The LOC cells print .XXX in the sheet's inch: X from the -X end face
# (3.56 -/+ 2.375), Y from the -Z foot edge (1.250 +/- .687). The table
# check converts them back to these millimetres.
EXPECTED_HOLE_TABLE_LOCATIONS_MM = tuple(
    (BOSS_DEPTH / 2.0 + sx * HOLD_DOWN_LOCAL_HALF_X, WIDE + sz * HOLD_DOWN_LOCAL_HALF_Z)
    for sz in (1, -1)
    for sx in (1, -1)
)
# The SIZE cells are generated from FootClearanceHoles and are not
# text-editable, so they print "Ø .313 THRU ALL" with no process; the
# machinist could not tell whether the title block's DRILLED HOLES row or the
# .XXX band governs them (ENFORCE review, rule 12). The header names the
# process, so each row reads DRILL Ø.313 THRU ALL; size and depth stay native.
HOLE_TABLE_SIZE_COLUMN = 3
HOLE_TABLE_SIZE_HEADING = "DRILL"
# The four foot clearances match the base's hold-down taps (machinist review
# b2: the .XXX table named no mate). MHA-FR-01's own hole table tags those
# taps C2-C5 at the same 4.750 x 1.374 pattern. The note stands under the
# table's right end, right of the seat callout and over the title block.
HOLE_PATTERN_NOTE = (
    f"HOLE PATTERN\nMATCHES\n{_config.parts('fr-harmonic-base')['number']} C2-C5"
)
HOLE_PATTERN_NOTE_XY = (0.392, 0.084)


@_telemetry.traced("drawing.rocker_support.hole_table_process")
def _name_hole_table_process(adapter: Any, table: Any) -> None:
    """Retitle the native SIZE column with the foot holes' process."""
    column = HOLE_TABLE_SIZE_COLUMN
    if not table.IsCellTextEditable(0, column):
        raise RuntimeError("native hole-table SIZE header is not editable")
    table.SetText2(0, column, False, HOLE_TABLE_SIZE_HEADING)
    rebuild_drawing(adapter, label="rocker-arm-support hole-table process")
    heading = str(table.DisplayedText2(0, column, False) or "")
    if heading.upper() != HOLE_TABLE_SIZE_HEADING:
        raise RuntimeError(f"hole-table process header did not persist: {heading!r}")
    sizes = {
        str(table.DisplayedText2(row, column, False) or "")
        for row in range(1, int(table.RowCount))
    }
    if len(sizes) != 1 or "THRU" not in next(iter(sizes)).upper():
        raise RuntimeError(f"hole-table DRILL column holds unexpected sizes: {sizes!r}")
    _telemetry.info(f"hole-table process header {heading!r} over sizes {sizes!r}")


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point on a foot-hole rim in the bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + HOLE_DIA / 2.0) * VIEW_SCALE / 1000.0,
    )


def _seat_entry_edge(view: Any) -> Any:
    """The east seat's entry rim on the rail top, as a part edge.

    Resolved through the part's typed seat cylinder rather than a sheet pick:
    each seat straddles the window's side edge, among the post's and web's
    edges on a 1:2 sheet. It is the
    drill-diameter circle on the top face, not the one where the drill point
    starts.
    """
    model = _early_bound(_early_bound(view, "IView").ReferencedDocument, "IModelDoc2")
    diameter = blind_cut_dia_mm(SEAT_SPEC)
    face = resolve_faces(
        model, {"seat": CylinderFace(diameter, contains_x_mm=SEAT_CALLOUT_X_MM)}
    )["seat"]
    matches = []
    for raw in _early_bound(face, "IFace2").GetEdges() or ():
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        _x, centre_y, _z, *_axis, radius = (float(v) for v in curve.CircleParams)
        if abs(radius - diameter / 2000.0) > 1e-7:
            continue
        if abs(centre_y - HALF_Y / 1000.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"expected one east-seat entry rim, found {len(matches)}")
    return matches[0]


def _crop_view_b_to_rail(adapter: Any, view: Any) -> None:
    """Crop VIEW B to the rail strip: the whole rail length and the rail top
    with the upper slopes, not the full 63.5 mm foot width."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    native_view = _early_bound(view, "IView")
    # The positive control (draw_pinion_arbor's cropped 2:1 *Top, 3107bfa95)
    # rebuilds after placing and locates the fence from the view's own model
    # transform. r743-p1s-A did neither, and its crop did not take. So: rebuild,
    # then prove where the part landed (origin on VIEW_B_CENTER, +X running
    # along the sheet at 1:2) and fence around THAT, not an assumed centre.
    rebuild_drawing(adapter, label="VIEW B placement")
    half_len = (BOSS_DEPTH / 2.0 + 2.0) * VIEW_SCALE / 1000.0
    half_z = VIEW_B_CROP_HALF_Z_MM * VIEW_SCALE / 1000.0
    origin = model_point_in_view(
        adapter, native_view, (0.0, 0.0, 0.0), label="VIEW B part origin"
    )
    east = model_point_in_view(
        adapter, native_view, (BOSS_DEPTH / 2000.0, 0.0, 0.0), label="VIEW B east end"
    )
    _telemetry.info(f"VIEW B part origin at {origin!r}, east end at {east!r}")
    end_run = BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0
    if (
        math.dist(origin, VIEW_B_CENTER) > 0.001
        or abs(abs(east[0] - origin[0]) - end_run) > 1e-4
        or abs(east[1] - origin[1]) > 1e-4
    ):
        raise RuntimeError(
            f"VIEW B is not the rail at 1:2 on {VIEW_B_CENTER!r}: part origin "
            f"{origin!r}, east end {east!r}"
        )
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate VIEW B for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native_view.GetOutline())
    sketch = _early_bound(native_view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for x, y in (
        (origin[0] - half_len, origin[1] + half_z),
        (origin[0] + half_len, origin[1] - half_z),
    ):
        point = _early_bound(
            math_utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        corners.append(tuple(float(value) for value in projected.ArrayData))
    _telemetry.info(
        f"VIEW B before crop: outline={before!r}, "
        f"scale={float(native_view.ScaleDecimal)!r}, "
        f"position={tuple(native_view.Position)!r}, "
        f"fence corners in view-sketch space={corners!r}"
    )
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    # Direct to the database, past sketch inference: the fence's east corner
    # stands 1 mm of sheet off the rail's end, and r7 printed VIEW B with no
    # east end line (its west end, drawn first, kept it) -- the signature of
    # a corner snapped onto the end edge, which the crop then trims away.
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        segments = tuple(
            sketch_manager.CreateCornerRectangle(*corners[0], *corners[1]) or ()
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if len(segments) != 4:
        raise RuntimeError(f"VIEW B crop fence has {len(segments)} segments, not 4")
    # Crop2 consumes the selected closed profile. A circle stays selected once
    # sketched (the positive control); whether all four rectangle lines do is
    # unproven, so select them all and log what Crop2 is handed.
    for segment in segments:
        if not _early_bound(segment, "ISketchSegment").Select4(True, None):
            raise RuntimeError("failed to select the VIEW B crop fence")
    selected = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    # IView.Crop2 returns swCropViewErrors_e, where 1 is NoError.
    status = int(native_view.Crop2(False, True, 0))
    _telemetry.info(f"VIEW B Crop2 status {status} with {selected} entities selected")
    if status != 1:
        raise RuntimeError(
            f"failed to crop VIEW B to the rail strip: Crop2 status {status}"
        )
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    native_view.UpdateViewDisplayGeometry()
    if not bool(native_view.IsCropped()):
        raise RuntimeError("VIEW B did not retain its crop")
    outline = tuple(float(value) for value in native_view.GetOutline())
    _telemetry.info(f"VIEW B outline after crop: {outline!r}")
    # r743-p1s-A read 0.116 x 0.035 here with Crop2 = 1 and IsCropped true:
    # larger than the 0.089 x 0.032 top view, so neither flag proves a fence
    # took. The crop is proved against the same view's outline before it:
    # narrower across the rail (the fence runs 2 mm past each end, so the
    # length is not compared) and still centred on the part.
    centre = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
    if (
        len(outline) != 4
        or outline[3] - outline[1] >= before[3] - before[1] - 0.002
        or math.dist(centre, origin) > 0.001
    ):
        raise RuntimeError(
            f"VIEW B crop is not the rail strip: before={before!r}, after={outline!r}"
        )


def _add_view_b_arrow(adapter: Any, front: Any) -> None:
    """The letter arrow on the front view that names VIEW B."""
    text_xy, tip_xy = VIEW_B_ARROW
    note = add_leader_note(
        adapter,
        "B",
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=front,
        label="view B viewing arrow",
    )
    # add_note leaves text at the document height; size the letter here and
    # prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError("view B arrow note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError("failed to size the view B arrow letter")
    rebuild_drawing(adapter, label="view B arrow letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError("view B arrow tip moved when its letter was sized")


def _mirror_right_end_hole_tags(view: Any) -> dict[str, tuple[float, float]]:
    """Shift the right-end hole tags left of their holes; return old -> new x."""
    moved: dict[str, tuple[float, float]] = {}
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in RIGHT_END_HOLE_TAGS:
            continue
        if tag in moved:
            raise RuntimeError(f"duplicate bottom-view hole tag {tag}")
        x, y = (float(value) for value in annotation.GetPosition()[:2])
        if x < BOTTOM_CENTER[0]:
            raise RuntimeError(f"hole tag {tag} is not at the right end: x={x:.4f}")
        target = (x + HOLE_TAG_MIRROR_SHIFT, y)
        if not annotation.SetPosition2(*target, 0.0):
            raise RuntimeError(f"failed to move hole tag {tag}")
        after = tuple(float(value) for value in annotation.GetPosition()[:2])
        if max(abs(a - b) for a, b in zip(after, target)) > 1e-6:
            raise RuntimeError(f"hole tag {tag} landed at {after!r}, not {target!r}")
        if str(note.GetText()).strip() != tag:
            raise RuntimeError(f"moving hole tag {tag} changed its text")
        moved[tag] = (x, after[0])
    if set(moved) != set(RIGHT_END_HOLE_TAGS):
        raise RuntimeError(
            f"bottom-view hole tags {sorted(set(RIGHT_END_HOLE_TAGS) - set(moved))} "
            "not found"
        )
    _telemetry.info(f"bottom-view hole tags moved left of their holes: {moved}")
    return moved


def _bottom_datum_axes(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the chamfer-inset edges used to create the native table."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    x_axes: list[Any] = []
    y_axes: list[Any] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(view, c, 1),
                default=(),
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if (
                abs(parameters[2] + (WIDE - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[3]) >= 0.99
            ):
                x_axes.append(edge)
            if (
                abs(parameters[0] + (BOSS_DEPTH / 2.0 - CHAMFER) / 1000.0) <= 2e-6
                and abs(parameters[5]) >= 0.99
            ):
                y_axes.append(edge)
    if not x_axes or not y_axes:
        raise RuntimeError("bottom view is missing a chamfer-inset datum edge")
    return x_axes[0], y_axes[0]


def _right_seat_edge(adapter: Any, view: Any) -> Any:
    """Return the longest right-view edge on the mounting-face plane."""
    span, edge = _longest_right_z_edge(adapter, view, -HALF_Y, label="mounting-face")
    if span < (2.0 * WIDE - 2.0 * CHAMFER - 0.1) / 1000.0:
        raise RuntimeError(f"mounting-face edge spans only {span * 1000.0:.3f} mm")
    return edge


def _longest_right_z_edge(
    adapter: Any, view: Any, y_mm: float, *, label: str
) -> tuple[float, Any]:
    """The longest visible model line along Z lying at local height ``y_mm``."""
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    candidates: list[tuple[float, Any]] = []
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(view, c, 1),
                default=(),
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            parameters = tuple(float(value) for value in curve.LineParams)
            if abs(parameters[1] - y_mm / 1000.0) > 2e-6 or abs(parameters[5]) < 0.99:
                continue
            start = _early_bound(edge.GetStartVertex(), "IVertex").GetPoint()
            end = _early_bound(edge.GetEndVertex(), "IVertex").GetPoint()
            candidates.append((abs(float(end[2]) - float(start[2])), edge))
    if not candidates:
        raise RuntimeError(f"right view has no model edge on the {label} plane")
    return max(candidates, key=lambda item: item[0])


@_telemetry.traced("drawing.planar_centerline", label_param="label")
def _create_view_centerline(
    adapter: Any,
    view: Any,
    *,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    label: str,
) -> Any:
    """Create a retained centerline in one drawing view's sketch."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate centerline view {name!r}")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    previous_display = bool(sketch_manager.DisplayWhenAdded)
    sketch_manager.AddToDB = True
    sketch_manager.DisplayWhenAdded = True
    try:
        centerline = sketch_manager.CreateCenterLine(
            start_xy[0],
            start_xy[1],
            0.0,
            end_xy[0],
            end_xy[1],
            0.0,
        )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
        sketch_manager.DisplayWhenAdded = previous_display
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError(f"failed to create {label} centerline")
    return centerline


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm-support source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    # Three document places: the native hole table's LOC and SIZE cells print
    # them (the .XXX stations and the 5/16 drill as .313).
    drawing_model, sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        decimals=3,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker-Arm Support Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker-arm support; manufacturing drawing; casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # swDetailingSectionViewLineStyleDisplay (swconst.tlb R2026x): end segments
    # only. Span the full parent view so SolidWorks derives a stable, complete
    # centre section; the dimensions occupy exterior lanes away from its arrows.
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")

    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # WebLocationReference lies in A-A's cutting plane, saved hidden: a
    # derived view takes it from the part as it stands when it is cut and
    # selects it through its base view, so the section is cut and curated
    # while the part shows it (draw_fr_nameplate's recipe).
    with part_sketches_shown(
        adapter,
        source_model,
        ("WebLocationReference",),
        label="section A-A web location",
        base_view=front,
    ):
        right = create_section_view(
            adapter,
            front,
            line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - 0.050),
            line_end=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.050),
            view_xy=RIGHT_CENTER,
            section_label="A",
            scale=(1, 2),
            label="rocker-arm support centre section",
        )
        set_hidden_lines_removed(adapter, right)
        right_dimensions = curate_hidden_owner_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    # Every view hides its hidden edges: Section A-A shows the pockets, web
    # and cavity, and View B the seats, so dashed lines in the front and the
    # hole-table view only buried the A1-A4 holes (r4 machinist review).
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    # The cavity's and the pockets' locations: CavityLocationReference is
    # saved hidden, so the hidden-owner curate shows it in this view only.
    front_dimensions = curate_hidden_owner_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    dimensions = [*front_dimensions, *right_dimensions]
    set_dimension_callouts(adapter, dimensions, DIMENSION_CALLOUTS)
    set_dimension_precision(
        adapter, dimensions, imported_precision(set(FRONT_KEEP) | set(RIGHT_KEEP))
    )
    _assert_part_precision(adapter, dimensions, set(FRONT_KEEP) | set(RIGHT_KEEP))
    offset_dimension_text(
        adapter, front_dimensions, {"RimChamferSize": RIM_CHAMFER_TEXT_XY}
    )
    _create_view_centerline(
        adapter,
        front,
        start_xy=(-BOSS_DEPTH / 2000.0, 0.0),
        end_xy=(BOSS_DEPTH / 2000.0, 0.0),
        label="front wall",
    )
    _create_view_centerline(
        adapter,
        front,
        start_xy=(0.0, -HALF_Y / 1000.0),
        end_xy=(0.0, HALF_Y / 1000.0),
        label="front vertical",
    )
    _create_view_centerline(
        adapter,
        right,
        start_xy=(0.0, -HALF_Y / 1000.0),
        end_xy=(0.0, HALF_Y / 1000.0),
        label="section web",
    )
    # Pick the two cut pocket floors in the LOWER web band, between the cavity
    # and the foot. HLR ensures the selected edges are visible section edges.
    web_y = RIGHT_CENTER[1] - (BIG + CAV) / 2.0 * VIEW_SCALE / 1000.0
    half_web = WEB * VIEW_SCALE / 1000.0
    web_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(RIGHT_CENTER[0] - half_web, web_y),
            p1=(RIGHT_CENTER[0] + half_web, web_y),
            text_xy=WEB_TEXT_XY,
            orientation="horizontal",
            label="section web thickness",
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(web_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - 2.0 * WEB) > 1e-5:
        raise RuntimeError(f"section web dimension measured {measured * 1000.0:.6f} mm")
    web_dimension.SetPrecision3(DIMENSION_PRECISION["WebThickness"], -1, -1, -1)
    if web_dimension.GetPrimaryPrecision2() != DIMENSION_PRECISION["WebThickness"]:
        raise RuntimeError("section web dimension precision did not persist")
    foot_pick_x = RIGHT_CENTER[0] + 0.010
    foot_dimension = _early_bound(
        add_edge_dimension(
            adapter,
            right,
            p0=(
                foot_pick_x,
                RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0,
            ),
            p1=(
                foot_pick_x,
                RIGHT_CENTER[1] - BIG * VIEW_SCALE / 1000.0,
            ),
            text_xy=FOOT_TEXT_XY,
            orientation="vertical",
            label="section foot thickness",
        ),
        "IDisplayDimension",
    )
    measured = float(
        _early_bound(foot_dimension.GetDimension2(0), "IDimension").SystemValue
    )
    if abs(measured * 1000.0 - (HALF_Y - BIG)) > 1e-5:
        raise RuntimeError(
            f"section foot dimension measured {measured * 1000.0:.6f} mm"
        )
    foot_dimension.SetPrecision3(DIMENSION_PRECISION["FootThickness"], -1, -1, -1)
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")

    # The mounting face is the trapezoid's visible bottom edge in section A-A.
    # Keep the symbol near the foot while clearing the 63.5 width dimension.
    # The leader lands 8 mm of sheet in from the foot's sharp: at 2 mm it hit
    # the corner where the rim chamfer meets the face (r5 review, minor).
    seat_y = RIGHT_CENTER[1] - HALF_Y * VIEW_SCALE / 1000.0
    seat_half_w = WIDE * VIEW_SCALE / 1000.0
    add_surface_finish(
        adapter,
        right,
        edge_entity=_right_seat_edge(adapter, right),
        symbol_xy=(RIGHT_CENTER[0] + seat_half_w + 0.020, seat_y - 0.010),
        control=surface_finish_by_key(SURFACE_FINISHES, "mounting_face"),
        label="mounting face finish",
        char_height=0.0025,
        leader_attach_xy=(RIGHT_CENTER[0] + seat_half_w - 0.008, seat_y),
    )

    datum_axes = _bottom_datum_axes(adapter, bottom)
    datum_point = create_view_theoretical_datum(
        adapter,
        bottom,
        point_xy=(
            HOLE_TABLE_DATUM_XZ_MM[0] / 1000.0,
            HOLE_TABLE_DATUM_XZ_MM[1] / 1000.0,
        ),
        label="rocker-arm-support lower-left theoretical corner",
    )
    # No position frame on this part (drawing-guidelines.md rule 5 (avoid excessive GD&T)), so the hole
    # coordinates are ordinary .XXX dimensions under the title block's
    # ±.005, the base's matching pattern named beside the table — NOT basic:
    # a basic dimension is toleranced only by the frame it feeds, and
    # without one it has no tolerance at all.
    hole_table = insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] + HOLE_TABLE_DATUM_XZ_MM[0] * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] + HOLE_TABLE_DATUM_XZ_MM[1] * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        datum_point=datum_point,
        expected_locations_mm=EXPECTED_HOLE_TABLE_LOCATIONS_MM,
        unit=part_drawing_unit(PART_STEM),
        location_places=3,
        datum_axes=datum_axes,
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="rocker-arm-support",
    )
    _name_hole_table_process(adapter, hole_table)
    if add_note(adapter, HOLE_PATTERN_NOTE, *HOLE_PATTERN_NOTE_XY) is None:
        raise RuntimeError("failed to name the foot holes' mating pattern")
    _mirror_right_end_hole_tags(bottom)
    # The drawing-sketch datum and hole table leave the bottom view's edge set
    # stale, so regenerate it before export.
    set_hidden_lines_removed(adapter, bottom)
    _telemetry.info(
        f"bottom view outline (uncropped 1:2 control): "
        f"{tuple(_early_bound(bottom, 'IView').GetOutline())!r}"
    )
    view_b = place_view(adapter, str(SOURCE), "*Top", *VIEW_B_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, view_b)
    _crop_view_b_to_rail(adapter, view_b)
    if not auto_center_marks(adapter, view_b, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to VIEW B")
    # The seats' stations off the end faces, as REF: the part saves their
    # sketch blanked, so the hidden-owner curate shows it in this view only.
    view_b_dimensions = curate_hidden_owner_dimensions(
        adapter,
        view_b,
        keep=VIEW_B_KEEP,
        view_label="VIEW B",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _assert_part_precision(adapter, view_b_dimensions, VIEW_B_KEEP)
    for annotation in view_b_dimensions:
        set_reference_dimension(adapter, annotation, label="VIEW B seat station")
    if add_note(adapter, VIEW_B_CAPTION, *VIEW_B_CAPTION_XY) is None:
        raise RuntimeError("failed to caption VIEW B")
    _add_view_b_arrow(adapter, front)
    seat_callout = add_native_hole_callout(
        adapter,
        view_b,
        edge=_seat_entry_edge(view_b),
        callout_xy=SEAT_CALLOUT_XY,
        label="rocker-bracket transfer seats",
        process=SEAT_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        seat_callout, SEAT_CALLOUT_PRECISION, label="rocker-bracket transfer seats"
    )

    # Materialize the iso's cosmetic threads before the strict final note
    # cleanup, so any descriptive BracketSeats label exists when it is counted
    # rather than first appearing during the native drawing save.
    # VIEW B shows the same seats face-on, so its cosmetic threads are
    # imported too (the thread circles print; nothing is left for the save to
    # add). r743-p1s-B showed the import brings NO label in that top view.
    import_cosmetic_threads(adapter, iso)
    import_cosmetic_threads(adapter, view_b)
    # Whether the iso draws BracketSeats' "#8-32 Tapped Hole" label is
    # SolidWorks' choice: on part key 40ff46054ba2 the q12q13-r3 render counted
    # none and the stack-top build one, past the right border. The tap is
    # stated once, on its hole callout, so any such label goes and the count
    # is logged, not gated (draw_sm_knife_mount); finalize_drawing then proves
    # none is left.
    removed_tap_labels = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(f"removed {removed_tap_labels} automatic tapped-hole label(s)")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # The sweep stays, so a label that appears after the removal above
        # fails the count instead of printing.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

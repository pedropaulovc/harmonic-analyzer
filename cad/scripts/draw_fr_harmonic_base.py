r"""Create the curated machinist drawing for the two-plate harmonic base.

The SLDPRT remains authoritative.  This recipe supplies only the base's views,
native footprint/socket dimensions, the ordinary-coordinate mounting-hole table,
and manufacturing notes; every shared sheet/template, import, curation, and
export behavior lives in ``_drawing_common``.

The base is a stepped gray-iron frame: a raised black deck stands 3.0 proud of
a green land on the pad, four column sockets open on that land, blind tapped
hardware seats run down into the deck, and the casting is cored from below by
a ribbed underside pocket whose bosses back every seat. The plate is 457 mm
long, so the whole package runs 1:4 -- the front elevation too -- except the
pictorial isometric (1:6) and the underside section and pads (1:2). Four
sheets: exterior geometry, holes and sockets, the underside, and the
underside's pads and lugs placed from the hole table's X0 Y0.

Run with SolidWorks open::

    uv run python cad\scripts\draw_fr_harmonic_base.py fr-harmonic-base
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from win32com.client.dynamic import Dispatch as dynamic_dispatch

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_native_hole_callout,
    add_surface_finish,
    create_blank_drawing_sheets,
    create_section_view,
    create_view_theoretical_datum,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    dimension_name,
    insert_hole_table,
    import_cosmetic_threads,
    model_point_in_view,
    model_points_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hole_callout_precision,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
    view_name,
    visible_component_entities,
)

from _drawing_common import _iter_tables, _iter_view_annotations, sheet_drawable_region
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_owner_dimensions,
)
from _drawing_layout_check import DrawableRegion
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME
from _part_pmi import _resolve_faces
from _surface_finish import surface_finish_by_key
from build_fr_harmonic_base import (
    BASE_CROSS_TAP_DRILL_DIA,
    BASE_CROSS_TAP_SPEC,
    BLOCK_PAD_SHAPES,
    BLOCK_SCREW_HOLE_DIA,
    BLOCK_SCREW_XZ,
    COLUMN_SOCKET_DIAMETER,
    CROSS_TAP_LUG_SHAPES,
    DEEP_BOSS_SHAPES,
    FOOT_SCREW_HOLE_DIA,
    FOOT_SCREW_XZ,
    HOLD_DOWN_TAP_DRILL_DIA,
    HOLE_XZ,
    LOCK_KNOB_XZ,
    LOCK_PAD_SHAPE,
    LOCK_SCREW_HOLE_DIA,
    LONG_RIB_SHAPE,
    NAMEPLATE_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_XZ,
    PEDESTAL_PAD_SHAPES,
    PEDESTAL_SCREW_HOLE_DIA,
    PEDESTAL_SCREW_XZ,
    SERIAL_HEIGHT_MM,
    SERIAL_TEXT,
    SERIAL_XZ,
    SHALLOW_BOSS_CENTRES,
    SHALLOW_BOSS_SHAPES,
    SOCKET_BOSS_SHAPES,
    PIVOT_SCREW_HOLE_DIA,
    PIVOT_SCREW_XZ,
    STOP_SCREW_HOLE_DIA,
    STOP_SCREW_XZ,
)
from fr_harmonic_base_spec import (
    BOTTOM_FRONT_Z,
    BOTTOM_LENGTH,
    BOTTOM_REAR_Z,
    BOTTOM_WIDTH,
    COLUMN_SOCKET_XZ,
    COLUMN_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    GREEN_TOP,
    PART_SURFACE_FINISHES,
    POCKET_CEILING_Y,
    STACK_HEIGHT,
    socket_bore_finish_key,
)
from fr_frame_attachment_spec import BASE_SCREW_SEAT_Z, BASE_SCREW_Y
from pinion_rig_fitup import RIG_SET_STEP, TRANSFER_AFTER_RIG_SET
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.solidworks.drawing import (
    _note_text,
    add_note,
    auto_center_marks,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fr_harmonic_base"]
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

SHEET_SCALE = (1.0, 4.0)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
SHEET_NAMES = ("GEOMETRY", "HOLES-SOCKETS", "UNDERSIDE", "UNDERSIDE-PADS")

# Section A-A is projected from a vertical cutting line, which lays machine +Y
# across the sheet: it reads as the upright section turned 90 degrees
# clockwise. That qualifier rides in the NATIVE view label beside the scale, so
# the sheet carries exactly one "SECTION A-A" and it is the one under the view.
# The custom-scale compartment PREFIXES the scale SolidWorks formats itself
# (label renders "<this text> 1 : 4"), so spelling the ratio here too printed
# it twice -- state the rotation and let the native value follow. The text is
# a document preference, so it labels every section: sheet 3's B-B is cut on
# a vertical line too and the build proves it turns the same way.
SECTION_LABEL_SCALE_TEXT = "ROTATED 90 DEG CW  SCALE"

if abs((BOTTOM_REAR_Z - BOTTOM_FRONT_Z) - BOTTOM_WIDTH) > 1e-12:
    raise AssertionError("base drawing extents disagree with the overall depth")

# Three landscape B sheets keep each annotation authoritative and readable:
# exterior geometry on sheet 1; the associative hole table, sockets and
# cross-taps on sheet 2; the underside pocket, its ribs and bosses on sheet 3.
TOP_CENTER = (0.145, 0.185)
SIDE_CENTER = (0.145, 0.100)
# The isometric owns the whole field right of the sheet-1 dimension envelope
# (x 0.275-0.410, y 0.070-0.265). At 1:6 the pictorial spans ~0.083 x 0.041,
# so it is centred in that region instead of floating above a dead strip.
ISO_SCALE = (1, 6)
ISO_CENTER = (0.3425, 0.175)
# The stamped-ID note's top-left corner, below the plan. SolidWorks runs its
# leader from the right end of the note's last line (hb-render-5: 44.0 mm
# right of and 11.8 mm below this anchor) to the serial in the deck's corner.
# From (0.125, 0.130) the leader to the old +X-rim serial ran through the A3
# socket bore (2026-09-25 Codex machinist review, clarity). With the serial
# now inboard on the deck, this anchor makes the leader short and steep: it
# stays well clear of every socket bore and crosses each plan outline's lower
# edge left of where that outline's width dimension starts its witness line,
# so it crosses no dimension.
SERIAL_NOTE_XY = (0.100, 0.135)
SERIAL_LEADER_START_OFFSET_M = (0.0440, -0.0118)
# The flange-perimeter finish symbol, in sheet 1's open field left of the
# plan. Its target, "FLANGE EDGES, 4 SIDES (TABLE ORIGIN)", runs ~63 mm at
# 2.5 mm text, too long for sheet 2's strip between the hole table and the
# plan (~50 mm), so the symbol moved here with its leader on the same west
# flange face (Main, 2026-09-25, option A). The anchor is the symbol's leader
# line; the leader lands on the straight west edge 100 mm in front of the
# plan centre, below the text row, so it runs down and clear of it.
FLANGE_FINISH_XY = (0.0168, 0.170)
FLANGE_FINISH_ATTACH_Z_MM = 100.0
# hb-render-5's sheet-2 flange symbol, measured at its 2.5 mm text: the vee
# starts 2.1 mm left of the anchor, the target text 5.3 mm right of it at
# 1.76 mm per character, and the text top sits 10.5 mm above the anchor.
FINISH_SYMBOL_VEE_LEFT_M = 0.0021
FINISH_TARGET_OFFSET_M = 0.0053
FINISH_TARGET_CHAR_M = 0.00176
FINISH_SYMBOL_TOP_M = 0.0105
HOLE_TOP_CENTER = (0.280, 0.195)
HOLE_SIDE_CENTER = (0.280, 0.095)
SECTION_CENTER = (0.375, 0.135)
HOLE_TABLE_ANCHOR = (0.018, 0.260)
# Rule 6: the A1-A4 matched fit sits on the sockets, not in a general note
# (Main's hb-render-6 eye pass). It is a leader note on A2 -- the rear-left
# socket, min(COLUMN_SOCKET_XZ) -- because A2 faces the open band between
# the hole table and the plan, under the TOP VIEW caption; "4X" carries it
# to all four. The table's SIZE cells are generated by SolidWorks and are
# not text-editable, so the note marks their diameter as reference.
SOCKET_FIT_NOTE = (
    "4X: FIT TO ASSIGNED\n"
    "MHA-FR-003 TUBE:\n"
    "CLOSE HAND-SLIP, NO\n"
    "PERCEPTIBLE ROCK.\n"
    "TABLE <MOD-DIAM> REF.\n"
    "RETAIN MATCH MARKS."
)
# Reflow the full tube ID without shrinking text; the hb-render-6 width model
# leaves 6.4 mm to the table and 6.54 mm to the plan's west edge.
SOCKET_FIT_NOTE_XY = (0.1690, 0.2262)
SOCKET_FIT_STATION = min(COLUMN_SOCKET_XZ)
# hb-render-6's sheet-2 notes at the default note height: 2.49 mm per
# character and 4.6 mm per row, the text hanging from its top-left anchor.
NOTE_CHAR_M = 0.00249
NOTE_ROW_M = 0.0046
# Sheet-2 hole callout text anchors. _check_hole_sheet_callouts proves each
# clears the others, the notes, the table, the table's datum origin and every
# view's casting outline, and that no leader runs through another text.
# SolidWorks centres a callout's text block on its anchor, 1 mm below it
# (hb-callout-cal display data), so the four-line transfer blocks share the
# 0.252 row and grow evenly, with no upward nudge towards the frame. The
# spring and cross-tap callouts moved 0.009 down together, so the spring text
# clears the plan's bottom rim, which struck through it (hb-notes-2 eye pass);
# the spring then moved right, off the datum origin's X axis and its "X"
# label (hb-render-2 eye pass), and on until its whole text sits right of the
# hole it points at (x 0.2716, hb-render-3 display data): its leader leaves
# the near, left shoulder end and rises clear of its own rows, which a leader
# from anywhere under the text cannot. Lowered with the cross-tap by 1 mm, it
# clears the section line's lower "A" arrow and label. The cross-tap block,
# cut to three rows (hb-render-4 eye pass), is centred in the gap between the
# front view and the spring block, about 10 mm clear of each.
PEDESTAL_CALLOUT_XY = (0.200, 0.252)
BLOCK_CALLOUT_XY = (0.272, 0.252)
SPRING_CALLOUT_XY = (0.315, 0.1448)
CROSS_TAP_CALLOUT_XY = (0.285, 0.120)
# The holes-sheet plan's view label, top-left corner. Centred over the plan it
# sat under the transfer callouts, and the MHA-DT-002 leader, which has to reach
# the pedestal seats beneath it, ran through "TOP" (hb-render-2 eye pass).
# It now reads beside the plan's top-left corner, left of every leader.
HOLES_TOP_LABEL_XY = (0.170, 0.237)

# Section A-A cuts the socket pair at x = +COLUMN_X and lays machine -Z up the
# sheet, so the lower-Z (front) socket of that pair is the UPPER one on paper.
# Its inner bore wall is the leader target, picked midway between the top of
# the window the cross tap opens through the wall and the socket's mouth on
# the green land: that puts the arrowhead 3.84 mm (1 mm on paper) clear of
# BOTH, so the symbol reads as the bore's and cannot be mistaken for the
# tapped cross hole whose cosmetic thread crowds the same wall. The deck-era
# 4 mm cannot survive: the mouth dropped 3.0 to the land, leaving 7.7 mm of
# bore wall between the window and the mouth.
SECTION_SOCKET_XZ = min(
    (station for station in COLUMN_SOCKET_XZ if station[0] > 0.0),
    key=lambda station: station[1],
)
SOCKET_LEADER_POINT_MM = (
    COLUMN_X,
    (BASE_SCREW_Y + BASE_CROSS_TAP_DRILL_DIA / 2.0 + GREEN_TOP) / 2.0,
    SECTION_SOCKET_XZ[1] + COLUMN_SOCKET_DIAMETER / 2.0,
)
# The symbol sits in the open field on the TOP side of the section, between
# the upper-rim and underside chamfer callouts, so its leader reaches the bore
# by crossing the land outline alone and its text clears both. The shoulder is
# short so the elbow stays out of the cut geometry it points into.
SOCKET_FINISH_SYMBOL_XY = (0.387, 0.1435)
SOCKET_FINISH_SHOULDER = 0.004

# Per-view survivors of the native marked-dimension import. Sheet 1 owns the
# exterior envelope and edge geometry. Sheet 2 owns socket and hole definition.
# Sheet 3 owns the underside pocket.
# Every manufacturing value on the sheets is imported here: the part marks
# and precises them (harmonic_base_spec.DRAWING_DIMENSIONS / DRAWING_PRECISION)
# and these tables only say WHICH view shows each one and WHERE its text sits
# -- the placement-only division policy rule 2 draws. The six keeps partition
# DRAWING_PRECISION_BY_NAME exactly, which assert_imported_precision proves at
# the end of the build.
GEOMETRY_TOP_KEEP = {
    # Three lengths stacked above the plan, shortest nearest the outline, and
    # three widths right of it the same way. The widths' texts stagger in y
    # so no value sits on a neighbour's dimension line.
    "BottomLen": (TOP_CENTER[0], 0.256),
    "TopLen": (TOP_CENTER[0], 0.244),
    "DeckLen": (TOP_CENTER[0], 0.230),
    "BottomWid": (0.250, 0.172),
    "TopWid": (0.236, 0.200),
    "DeckWid": (0.222, 0.186),
    "PadCornerRadius": (0.070, 0.236),
    "FlangeCornerRadius": (0.040, 0.215),
    # On the top-left deck corner, reading above the pad radius so the two
    # radial leaders do not cross.
    "DeckCornerRadius": (0.062, 0.252),
}
SIDE_KEEP = {
    "BottomThickness": (0.073, 0.085),
    "FlangeToDeck": (0.0625, 0.112),
    # Right of the front view, above the deck step it measures at its right
    # end; the 0.75 mm span on paper puts the arrows outside.
    "DeckRise": (0.228, 0.116),
    # The front view, not the plan: a chamfer dimension imports only where its
    # edge shows in profile (farm leaf 20261010T064423Z: the plan import
    # delivered every other plan dimension but this one). Above DeckRise in
    # the strip right of the front view and below the plan; the serial note
    # holds the matching strip on the left.
    "DeckEdgeChamfer": (0.205, 0.138),
}
HOLE_TOP_KEEP: dict[str, tuple[float, float]] = {}
# Section A-A lays machine +Y across the sheet, so the spotface depth -- a
# machine-Z value, which the rotation lays UP the sheet -- sits off the rear
# end it cuts.
# Both edge breaks land on the view's top-left corner, so their text stacks in
# the strip between the view (right edge 387.3 mm) and the sheet's right inner
# border (419.1 mm). The native layout audit measured what that strip costs:
# the underside break's text parked 67 mm below its own feature ran its
# dimension line straight through the socket-bore Ra symbol, and both chamfer
# captions ran off the sheet edge -- 433.6 mm on a 431.8 mm sheet. Both texts
# now sit beside the corner they dimension, captions inside the border.
SECTION_KEEP = {
    "TopRimChamfer": (0.400, 0.189),
    "BottomEdgeChamfer": (0.385, 0.1633),
    # Right of the section, not left: a display dimension anchors where
    # its leader meets the text box border, so a position LEFT of the
    # spotface ran the block back across the front cross-tap view (seen
    # on the 200 dpi sheet-2 render).  This lands it in the same
    # 382-418 mm callout column the two dimensions above use, ABOVE its own
    # dimension line: the leader drops from the arrow to the block's bottom-left
    # corner, so a block straddling the dimension line gets its widest caption
    # row struck by that drop (measured at y 0.103: the line crossed '4X
    # SPOTFACE' over 3.5 mm).
    "SpotFaceDepth": (0.3845, 0.113),
}
HOLE_SIDE_KEEP = {
    "SpotFaceDia": (0.193, 0.135),
    # 4 mm above the old station: three caption lines hang below this value and
    # the lowest reached the title-block band at y 66 mm (audit keep-out).
    "Spot0Y": (0.196, 0.0785),
    # One chained row beneath the front view, above its label: the tap X from
    # the flange's west face (the table's X0) reads left of the flange, since
    # its 7.9 mm witness span is narrower than its text, and the pitch sits
    # centred between the taps.
    "CrossTapX": (0.211, 0.0815),
    "CrossTapPitch": (0.280, 0.0815),
}
GEOMETRY_CALLOUTS = {
    "TopLen": "PAD CENTERED ON FLANGE",
    "DeckLen": "DECK CENTERED ON PAD",
    "PadCornerRadius": "PAD",
    "FlangeCornerRadius": "FLANGE",
    "DeckCornerRadius": "DECK",
    "DeckEdgeChamfer": "X 45 DEG\nDECK EDGE",
    "DeckRise": "DECK ABOVE\nLAND",
}
# One chamfer feature breaks both plates' top rims, so its caption names the
# feature -- in the PLURAL -- rather than whichever of its edges the import
# attached to. Plural, not spelled out: this column is 32 mm wide, and a
# caption row wider than that leaves the sheet (see SECTION_KEEP).
SECTION_CALLOUTS = {
    "TopRimChamfer": "X 45 DEG\nTOP RIMS",
    "BottomEdgeChamfer": "X 45 DEG\nUNDERSIDE",
    "SpotFaceDepth": "4X SPOTFACE\nDEPTH",
}
HOLE_SIDE_CALLOUTS = {
    "SpotFaceDia": "4X SPOTFACE\nCROSS-SCREW HOLES\nFRONT/REAR",
    "Spot0Y": "CROSS-SCREW AXIS\nFROM FLANGE\nUNDERSIDE",
}

# Native table tags keep their source association while short leaders separate
# the closely spaced screw patterns. Coordinates below are sheet layout only.
HOLE_TAG_POSITIONS = {
    "A3": (0.325, 0.176),
    "A4": (0.326, 0.215),
    "C1": (0.247, 0.216),
    "D1": (0.247, 0.187),
    # The transferred pinion-rig seats left the table (U28 corollary), and
    # with U34c the arbor-pedestal seats followed them, taking the last #4-40
    # rows (the former E) along. The native tags re-letter: the
    # rocker-support taps are now E and the nameplate seats are now F.
    # North-east of its tap, short of E3's tap and west of the nameplate's
    # rear-west tap, whose mark the former (0.306, 0.187) box sat on.
    "E1": (0.297, 0.1895),
    "E2": (0.289, 0.206),
    "E3": (0.312, 0.173),
    "E4": (0.312, 0.214),
}
# The nameplate taps sit on the plate's DXF screw marks, about 2 mm (at 1:4)
# inside the deck's east edge with section line A 7.5 mm east of that, so a
# tag east of section A's line crosses it (F3/F4 at ec323b4eb: crossed
# section line A and each other). Nor do four tags fit inside the 9 x 23 mm
# four-tap quad: two tags whose columns overlap read as one block unless a
# full row pitch (5.4 mm) separates them (enforced merged-blocks, ab1f78504),
# and E4 already stands over the quad. So the west taps' tags read just east
# of their taps, inside the quad -- the front one stepped down a row pitch
# under E4, the rear one stepped down away from E1, whose box ends beside
# that tap -- and the east taps' tags read in the open pad strip between the
# deck's east edge and section line A, a row pitch clear of A3 and A4. Placed
# from each tag's own table row, not its letter, so a re-lettered or
# re-sorted table still lands each tag beside its own tap.
# (east tap, rear tap) -> (tap centre to tag box's left edge, tap centre to
# tag mid-height), sheet m. A tag's insertion point is its box's top-left: F3
# at (342.5, 181.0) mm started its leader at (342.5, 179.2), mid-height of a
# 3.5 mm tag.
NAMEPLATE_TAG_OFFSETS = {
    (False, False): (0.0025, -0.0040),
    (False, True): (0.0025, -0.0020),
    (True, False): (0.0033, -0.0036),
    (True, True): (0.0033, 0.0010),
}
_HOLE_TAG_HALF_HEIGHT_M = 0.00175
_NAMEPLATE_QUAD_CENTRE_XZ = (
    sum(x for x, _ in NAMEPLATE_SCREW_XZ) / len(NAMEPLATE_SCREW_XZ),
    sum(z for _, z in NAMEPLATE_SCREW_XZ) / len(NAMEPLATE_SCREW_XZ),
)

# Hole-table origin is the finished plate's lower-left theoretical sharp
# corner. The physical corner is filleted, so the native table is seeded from
# the two visible outer edges and reattached to a retained view point there.
_TABLE_ORIGIN_XY = (
    HOLE_TOP_CENTER[0] - BOTTOM_LENGTH * VIEW_SCALE / 2000.0,
    HOLE_TOP_CENTER[1] - BOTTOM_REAR_Z * VIEW_SCALE / 1000.0,
)


def _plan_xy(
    x_mm: float, z_mm: float, *, center: tuple[float, float] = TOP_CENTER
) -> tuple[float, float]:
    """Sheet point for a machine X/Z station in one top view."""
    return (
        center[0] + x_mm * VIEW_SCALE / 1000.0,
        center[1] - z_mm * VIEW_SCALE / 1000.0,
    )


def _hole_rim(x_mm: float, z_mm: float, diameter_mm: float) -> tuple[float, float]:
    """Sheet pick on a hole-sheet plan rim, offset in machine +X."""
    return _plan_xy(x_mm + diameter_mm / 2.0, z_mm, center=HOLE_TOP_CENTER)


def _nameplate_tag_position(
    table_mm: tuple[float, float],
) -> tuple[float, float] | None:
    """Tag insertion point for the nameplate tap at hole-table ``table_mm``,
    or ``None`` when that row is not a nameplate tap."""
    x_mm = table_mm[0] - BOTTOM_LENGTH / 2.0
    z_mm = BOTTOM_REAR_Z - table_mm[1]
    # The table prints two places, so a row matches its tap within 0.01 mm.
    if not any(
        abs(x_mm - x) < 0.01 and abs(z_mm - z) < 0.01 for x, z in NAMEPLATE_SCREW_XZ
    ):
        return None
    hole_x, hole_y = _plan_xy(x_mm, z_mm, center=HOLE_TOP_CENTER)
    centre_x, centre_z = _NAMEPLATE_QUAD_CENTRE_XZ
    dx, dy = NAMEPLATE_TAG_OFFSETS[(x_mm > centre_x, z_mm > centre_z)]
    return (hole_x + dx, hole_y + dy + _HOLE_TAG_HALF_HEIGHT_M)


@_telemetry.traced("drawing.base_cross_tap_edge")
def _cross_tap_edge(view: Any, *, x_mm: float = COLUMN_X) -> Any:
    """Pick the tap entry itself, not the nearby larger spotface circle."""
    center = (x_mm / 1000.0, BASE_SCREW_Y / 1000.0, BASE_SCREW_SEAT_Z / 1000.0)
    radius = BASE_CROSS_TAP_DRILL_DIA / 2000.0
    matches = []
    for raw in visible_view_entities(view, 1, label="base cross-tap entry"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if not curve.IsCircle():
            continue
        values = tuple(float(value) for value in curve.CircleParams)
        if abs(values[6] - radius) > 1e-7:
            continue
        if any(abs(values[index] - center[index]) > 1e-7 for index in range(3)):
            continue
        if abs(abs(values[5]) - 1.0) > 1e-7:
            continue
        matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one base cross-tap entry edge, found {len(matches)}"
        )
    return matches[0]


@_telemetry.traced("drawing.base_cross_tap_readback")
def _check_cross_tap_callout(display: Any) -> None:
    expected = {
        "hw-tapdrldia": BASE_CROSS_TAP_DRILL_DIA,
        "hw-tapdrldepth": BASE_CROSS_TAP_SPEC.depth_mm,
        "hw-threaddepth": BASE_CROSS_TAP_SPEC.overrides_mm["ThreadDepth"],
    }
    expected_strings = {
        "hw-threaddesc": "10-32 UNF",
        "hw-threadclass": BASE_CROSS_TAP_SPEC.thread_class,
    }
    found = set()
    for raw in display.GetHoleCalloutVariables() or ():
        late = dynamic_dispatch(raw._oleobj_)
        name = str(late.VariableName)
        if name in expected_strings:
            if int(late.Type) != 3:
                raise RuntimeError(f"base tap callout {name} is not a string variable")
            actual = str(_early_bound(raw, "ICalloutStringVariable").String or "")
            if actual.strip(" -") != expected_strings[name]:
                raise RuntimeError(
                    f"base tap callout {name}: {actual!r} != {expected_strings[name]!r}"
                )
            found.add(name)
            continue
        if name not in expected:
            raise RuntimeError(f"unexpected base tap callout variable {name!r}")
        if int(late.Type) != 1:
            raise RuntimeError(f"base tap callout {name} is not a length variable")
        length = _early_bound(raw, "ICalloutLengthVariable")
        actual_mm = float(length.Length) * 1000.0
        if abs(actual_mm - expected[name]) > 1e-5:
            raise RuntimeError(
                f"base tap callout {name}: {actual_mm} != {expected[name]} mm"
            )
        if name == "hw-tapdrldepth" and int(length.Precision) != 0:
            raise RuntimeError(
                f"base tap-drill depth prints {length.Precision} decimals, not a whole-mm MIN"
            )
        found.add(name)
    required = set(expected) | set(expected_strings)
    if found != required:
        raise RuntimeError(
            f"base tap callout is missing native variables: {required - found}"
        )


def _set_cross_tap_callout_text(display: Any) -> None:
    """Aggregate both two-hole features and call the drill depth a minimum.

    Neither edit resolves a native size/depth token: the writable callout part
    keeps them, so the Hole Wizard variables stay associative.
    """
    definitions = {
        definition_part: str(display.GetText(definition_part) or "")
        for definition_part in (5, 6, 7, 8)
    }
    # swDimensionTextCalloutAboveDefinition=7 pairs with writable
    # swDimensionTextCalloutAbove=3; the raw count is not its resolved "2X".
    definition = definitions[7]
    if (
        not definition.lstrip().startswith("<NUM_INST>X ")
        or definition.count("<NUM_INST>") != 1
        or "<hw-tapdrldia>" not in definition
        or "<hw-tapdrldepth>" not in definition
        or not str(display.GetText(3) or "").lstrip().startswith("2X ")
    ):
        raise RuntimeError(f"expected one native two-instance drill definition: {definitions!r}")
    quantity = len(COLUMN_SOCKET_XZ)
    # The tap drill only has to reach deep enough for the bottoming tap to cut
    # full thread, so its depth is a MINIMUM, not the two-place band "48.00"
    # asked the shop to hold (2026-09 review).
    updated = definition.replace("<NUM_INST>", str(quantity), 1).replace(
        "<hw-tapdrldepth>", "<hw-tapdrldepth> MIN", 1
    )
    display.SetText(3, updated)
    resolved = str(display.GetText(3) or "")
    if (
        str(display.GetText(7)) != updated
        or not resolved.lstrip().startswith(f"{quantity}X ")
        or " MIN" not in resolved
        or any(
            str(display.GetText(part) or "") != definitions[part]
            for part in (5, 6, 8)
        )
    ):
        raise RuntimeError("aggregate cross-tap quantity or untouched native definitions did not persist")


def _horizontal_base_edge(view: Any, height_mm: float) -> Any:
    candidates = []
    for raw in visible_view_entities(view, 1, label="base height edges"):
        edge = _early_bound(raw, "IEdge")
        if not _early_bound(edge.GetCurve(), "ICurve").IsLine():
            continue
        x0, y0, z0, x1, y1, z1 = tuple(edge.GetCurveParams2())[:6]
        if (
            abs(y0 - height_mm / 1000.0) < 1e-7
            and abs(y1 - y0) < 1e-7
            and abs(z1 - z0) < 1e-7
            and abs(x1 - x0) > 1e-6
        ):
            candidates.append((abs(x1 - x0), edge))
    if not candidates:
        raise RuntimeError(f"base front lacks a horizontal edge at {height_mm} mm")
    return max(candidates, key=lambda item: item[0])[1]


def _add_base_height(
    adapter: Any,
    view: Any,
    upper_edge: Any,
    expected_mm: float,
    text_xy: tuple[float, float],
    label: str,
    *,
    lower_entity: Any | None = None,
) -> Any:
    drawing = adapter.currentModel
    if not _early_bound(drawing, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate {label} view")
    drawing.ClearSelection2(True)
    lower = _horizontal_base_edge(view, 0.0) if lower_entity is None else lower_entity
    for index, edge in enumerate((lower, upper_edge)):
        if not view.SelectEntity(edge, index > 0):
            raise RuntimeError(f"failed to select {label} edge {index}")
    display = drawing.AddVerticalDimension2(*text_xy, 0.0)
    drawing.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label}")
    display = _early_bound(display, "IDisplayDimension")
    actual_mm = (
        float(_early_bound(display.GetDimension2(0), "IDimension").SystemValue) * 1000.0
    )
    if abs(actual_mm - expected_mm) > 1e-5:
        raise RuntimeError(f"{label} measured {actual_mm}, expected {expected_mm} mm")
    return display


def _attached_note(
    adapter: Any,
    view: Any,
    edge: Any,
    text: str,
    position: tuple[float, float],
) -> None:
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(
        view_name(adapter, view)
    ):
        raise RuntimeError("failed to activate base feature-note view")
    note = add_note(adapter, text, *position)
    if note is None:
        raise RuntimeError(f"failed to create base feature note {text!r}")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetAttachedEntities(dispatch_array([edge])):
        raise RuntimeError(f"failed to attach base feature note {text!r}")
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
        raise RuntimeError(f"failed to give base feature note a leader: {text!r}")
    if not annotation.SetPosition2(*position, 0.0):
        raise RuntimeError(f"failed to position base feature note {text!r}")
    if int(annotation.GetAttachedEntityCount3()) != 1:
        raise RuntimeError(f"base feature note lost its source edge: {text!r}")


def _serial_edge(view: Any) -> Any:
    candidates = []
    for raw in visible_view_entities(view, 1, label="base stamped identifier"):
        edge = _early_bound(raw, "IEdge")
        values = tuple(float(value) for value in edge.GetCurveParams2())
        x0, y0, z0, x1, y1, z1 = values[:6]
        if max(abs(y0 - STACK_HEIGHT / 1000.0), abs(y1 - STACK_HEIGHT / 1000.0)) > 1e-7:
            continue
        distance = (
            ((x0 + x1) / 2.0 - SERIAL_XZ[0] / 1000.0) ** 2
            + ((z0 + z1) / 2.0 - SERIAL_XZ[1] / 1000.0) ** 2
        ) ** 0.5
        if distance < SERIAL_HEIGHT_MM / 1000.0:
            candidates.append((distance, edge))
    if not candidates:
        raise RuntimeError("base stamped identifier lacks a visible source edge")
    return min(candidates, key=lambda item: item[0])[1]


def _spread_hole_tags(view: Any, table: Any) -> None:
    table_locations = {}
    for row in range(1, int(table.RowCount)):
        tag = str(table.DisplayedText2(row, 0, False) or "").strip()
        if not tag or tag in table_locations:
            raise RuntimeError(f"duplicate or empty native hole-table tag at row {row}: {tag!r}")
        table_locations[tag] = tuple(
            float(table.DisplayedText2(row, column, False))
            for column in (1, 2)
        )
    nameplate_tags = {
        tag: position
        for tag, location in table_locations.items()
        if (position := _nameplate_tag_position(location)) is not None
    }
    if len(nameplate_tags) != len(NAMEPLATE_SCREW_XZ):
        raise RuntimeError(
            f"hole table carries {sorted(nameplate_tags)} for the "
            f"{len(NAMEPLATE_SCREW_XZ)} nameplate taps: {table_locations!r}"
        )
    if overlap := set(nameplate_tags) & set(HOLE_TAG_POSITIONS):
        raise RuntimeError(f"nameplate tags also placed by letter: {sorted(overlap)}")
    remaining = {**HOLE_TAG_POSITIONS, **nameplate_tags}
    found = set()
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag in table_locations:
            if tag in found:
                raise RuntimeError(f"duplicate native hole-table view tag: {tag}")
            found.add(tag)
        position = remaining.pop(tag, None)
        if position is None:
            continue
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"failed to give native hole tag {tag} a leader")
        if not annotation.SetPosition2(*position, 0.0):
            raise RuntimeError(f"failed to reposition native hole tag {tag}")
        if str(note.GetText()).strip() != tag:
            raise RuntimeError(f"moving native hole tag changed its text: {tag}")
        if tag in ("D1", "E1", "E3") or tag in nameplate_tags:
            points = tuple(float(value) for value in annotation.GetLeaderPointsAtIndex(0) or ())
            if len(points) < 6 or len(points) % 3:
                raise RuntimeError(f"native hole tag {tag} has no complete leader: {points!r}")
            expected = tuple(
                origin + coordinate * VIEW_SCALE / 1000.0
                for origin, coordinate in zip(_TABLE_ORIGIN_XY, table_locations[tag])
            )
            endpoint = points[-3:-1]
            if sum((actual - wanted) ** 2 for actual, wanted in zip(endpoint, expected)) > 0.001 ** 2:
                raise RuntimeError(
                    f"native {tag} leader does not reach its table hole: "
                    f"table_mm={table_locations[tag]!r}, end={endpoint!r}, centre={expected!r}"
                )
            _telemetry.info(
                f"native hole binding: tag={tag}, table_mm={table_locations[tag]!r}, "
                f"leader_end={endpoint!r}, centre={expected!r}"
            )
    if remaining:
        raise RuntimeError(f"native hole-table tags not found: {sorted(remaining)}")
    if found != set(table_locations):
        raise RuntimeError(f"native table/view tag bijection failed: missing={set(table_locations) - found}")


# U28 assembly corollary (Main ruling 2026-09-23, from the user's U27/U28):
# the pinion rig is set on the base by a 2.5 feeler at the parked tip gap,
# then the pivot-block and spring-foot seats are spotted THROUGH those parts.
# U34c does the same for the arbor pedestals: each is stood on the base with
# the arbor running in both straps, and its seat is spotted through the ledge
# hole. The sheet therefore prints no position for any of them: they leave
# the hole table and carry their native size on a callout naming their source.
# Along the bank nothing in the frame fixes the rig until the fitter sets it
# (user ruling P1-2), so the two rig callouts name the RIG SET note that
# states it and the spring pad's leaf (RIG_SET_STEP); printed on the callouts,
# the step ran through the top border, over the TOP VIEW caption, section
# arrow A and the MHA-VN-027 callout (pc-p1 render). The pedestal seats are not
# rig seats and keep AT ASSEMBLY.
TRANSFER_BLOCK_HOLES = tuple((x, z, BLOCK_SCREW_HOLE_DIA) for x, z in BLOCK_SCREW_XZ)
TRANSFER_SPRING_HOLE = (*FOOT_SCREW_XZ[0], FOOT_SCREW_HOLE_DIA)
TRANSFER_PEDESTAL_HOLES = tuple(
    (x, z, PEDESTAL_SCREW_HOLE_DIA) for x, z in PEDESTAL_SCREW_XZ
)
# The prefix lands before the tap line. The block and pedestal callouts
# share the band above the plan, so their thread goes on its own fourth
# line: side by side, two "AT ASSEMBLY; 8-32 UNC - 2B" lines ran into each
# other (hb-notes-2 eye pass). The spring callout keeps the semicolon joining
# the locating instruction to its "4-40 UNC - 2B" line. The trailing line
# break reaches the sheet through _drawing_common.compose_hole_callout_prefix.
TRANSFER_BLOCK_CALLOUT = f"TRANSFER FROM MHA-DT-018\n{TRANSFER_AFTER_RIG_SET}\n"
TRANSFER_SPRING_CALLOUT = f"TRANSFER FROM MHA-DT-024\n{TRANSFER_AFTER_RIG_SET}"
TRANSFER_PEDESTAL_CALLOUT = "TRANSFER FROM MHA-DT-002\nAT ASSEMBLY;\n"
# The RIG SET note heads the sheet-2 notes column, under the hole table and
# short of the 38.1 cross-screw-axis callout.  The sheet-2 callout check
# measures its read-back ink like a callout's: against every callout AND every
# other obstacle (the table, the views, the frame), so the note cannot land on
# the table or a view any more than a callout can (pc-p1 eye pass).
RIG_SET_NOTE_XY = (0.020, 0.108)
RIG_SET_NOTE_LABEL = "RIG SET note"


def is_rig_set_note(text: str) -> bool:
    """Whether a note read back off the sheet is the RIG SET note (INote text
    reads back with CRLF line breaks)."""
    return text.replace("\r\n", "\n").strip() == RIG_SET_STEP.strip()
# The cross-tap callout carries hole facts only, in three rows: count, drill
# and depth; this instruction; the thread and its depth, on its own row. The
# old "DEPTHS FROM SPOTFACE FLOOR" row restated the model: the Hole Wizard
# seats each tap ON the spotface floor (build_harmonic_base places it at
# BASE_SCREW_SEAT_Z), and its depths run from that face. "ON A1-A4 X
# CENTRES" was a location, now the CrossTapX/CrossTapPitch dimensions, and
# the spotface callout's 4X FRONT/REAR already counts the faces.
CROSS_TAP_PROCESS = "THRU BOTH WALLS, SINGLE CONTINUOUS THREAD\n"
TRANSFER_HOLES = (*TRANSFER_BLOCK_HOLES, TRANSFER_SPRING_HOLE, *TRANSFER_PEDESTAL_HOLES)

# One row per native Hole Wizard tapped-seat FEATURE build_harmonic_base cuts
# down into the deck (its SupportHoldDownSeats call plus its seat-group loop),
# in hole-table order: later seat groups stay after the earlier mounting-seat
# groups. The front/rear BaseCrossTaps features are side-face taps outside
# the table and outside this list.
DECK_TAPPED_SEAT_FEATURES = (
    ("SupportHoldDownSeats", HOLE_XZ, HOLD_DOWN_TAP_DRILL_DIA),
    ("PivotSeat", (PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
    ("StopSeat", (STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
    ("BlockScrewHoles", BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
    ("FootScrewHoles", FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
    ("PedestalSeats", PEDESTAL_SCREW_XZ, PEDESTAL_SCREW_HOLE_DIA),
    ("NameplateSeats", NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    ("LockSeat", (LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
)
ALL_HOLES = (
    *(
        (x, z, diameter)
        for _feature, stations, diameter in DECK_TAPPED_SEAT_FEATURES
        for x, z in stations
    ),
    *((x, z, COLUMN_SOCKET_DIAMETER) for x, z in COLUMN_SOCKET_XZ),
)
# SolidWorks drops a descriptive "<size> Tapped Hole" note into the views,
# and the final cleanup deletes every one. The count goes with deck seat
# FEATURES, not holes: 14 with seven deck features (pcbase-5945), 16 once U34c
# split the two pedestal seats out of FootScrewHoles into PedestalSeats with
# the hole count unchanged (warm-c486; both runs import 22 cosmetic threads).
# One note per feature in each plan view fits both runs, with the side-face
# BaseCrossTaps adding none. Sheets 3's and 4's bottom views count as plan
# views too: SolidWorks drops the same per-feature note there although every
# deck seat ends blind inside its boss (leaf 20261010T072847Z: 8 per view on
# all three sheets then). _log_tapped_hole_notes records the per-view split on
# every build, so a drifted count names the view it drifted in.
TAPPED_HOLE_NOTE = "Tapped Hole"
# finalize_drawing deletes every note containing one of these (case-blind, the
# adapter's remove_notes_matching), so none of them reaches the final sheet.
FINAL_SHEET_REMOVED_NOTES = (TAPPED_HOLE_NOTE,)
PLAN_VIEWS = (
    (SHEET_NAMES[0], "*Top"),
    (SHEET_NAMES[1], "*Top"),
    (SHEET_NAMES[2], "*Bottom"),
    (SHEET_NAMES[3], "*Bottom"),
)
TAPPED_HOLE_NOTES = len(DECK_TAPPED_SEAT_FEATURES) * len(PLAN_VIEWS)
TABLE_HOLES = tuple(hole for hole in ALL_HOLES if hole not in TRANSFER_HOLES)
if len(TABLE_HOLES) != len(ALL_HOLES) - len(TRANSFER_HOLES):
    raise AssertionError("a transferred seat is not a unique base hole")

# Sheet 3, the underside. The bottom view holds sheet 1's plan station, so it
# reads as the plan turned over. SolidWorks' *Bottom view keeps machine +X to
# the right and lays +Z UP the sheet (the plan mirrored top to bottom); the
# build proves that mapping before any pick or text position relies on it.
BOTTOM_CENTER = TOP_CENTER
UNDERSIDE_SECTION_SCALE = (1, 2)
# Right of the bottom view and its pocket-width dimension, above the title
# block: at 1:2 the section's 287.2 mm runs 143.6 mm up the sheet and its
# 50.8 mm height 25.4 mm across. Its caption hangs 31.2 mm under the cut's
# lowest edge (bp3 render: at y 0.160 the caption ran into the title block).
UNDERSIDE_SECTION_CENTER = (0.300, 0.176)


def _bottom_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a machine X/Z station in the sheet-3 bottom view."""
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + z_mm * VIEW_SCALE / 1000.0,
    )


def _x_span(shape: tuple) -> tuple[float, float]:
    """Machine-X extent of one build_fr_harmonic_base pocket shape."""
    if shape[0] == "disc":
        return (shape[1] - shape[3], shape[1] + shape[3])
    return (shape[1], shape[2])


# Section B-B is cut at constant X -- a vertical line on the bottom view, like
# A-A's, so the shared rotated label is true of it -- through the widest X
# band where a deep boss (bottom 12.0) and a shallow one (bottom 28.0) overlap,
# so one section shows the ceiling, the long rib's relief and both boss levels.
# That band is the spring-foot boss over the pinion-block pads; it lies
# between the foot and block-screw bores, so no thread clutters the cut.
_DEEP_SHALLOW_X_BANDS = [
    (max(deep[0], shallow[0]), min(deep[1], shallow[1]))
    for deep in map(_x_span, DEEP_BOSS_SHAPES)
    for shallow in map(_x_span, SHALLOW_BOSS_SHAPES)
]
_CUT_BAND = max(_DEEP_SHALLOW_X_BANDS, key=lambda band: band[1] - band[0])
UNDERSIDE_CUT_X = (_CUT_BAND[0] + _CUT_BAND[1]) / 2.0
if _CUT_BAND[1] <= _CUT_BAND[0]:
    raise AssertionError("no X band crosses both a deep and a shallow boss")
if any(abs(UNDERSIDE_CUT_X - x) <= diameter / 2.0 for x, _z, diameter in ALL_HOLES):
    raise AssertionError("section B-B would cut a hole bore")
if any(abs(UNDERSIDE_CUT_X - shape[1]) <= shape[3] for shape in SOCKET_BOSS_SHAPES):
    raise AssertionError("section B-B would cut a socket boss")
if not LONG_RIB_SHAPE[1] < UNDERSIDE_CUT_X < LONG_RIB_SHAPE[2]:
    raise AssertionError("section B-B misses the long rib that carries RibRelief")

# Bottom-view texts, sheet metres, all outside the casting's footprint. The
# pocket size reads below the view, clear of the B-B arrows; the corner group
# stacks left of the view. Each rib's thickness reads well clear of its own
# witness lines (bp3 machinist review: both "10.0 RIB" texts sat on lines):
# the long rib's above its span, left of the view; the cross rib's high above
# the B arrow, left of the rib. The two round-boss diameters' leaders drop
# from the top-right, one per cast level (the review read all eleven bosses
# as shallow): the deep diameter on E1's boss, the shallow one on the rear
# west nameplate tap's (ShallowBoss4, pinned by test).
UNDERSIDE_BOTTOM_KEEP = {
    "PocketLen": (0.170, 0.130),
    "PocketWid": (0.222, 0.200),
    "SocketBossDia": (0.055, 0.140),
    "PocketFilletRadius": (0.050, 0.165),
    "LongRibThickness": (0.070, 0.198),
    "CrossRibThickness": (0.128, 0.247),
    "HangingBossDia": (0.180, 0.248),
    "ShallowBoss4Dia": (0.240, 0.248),
}
UNDERSIDE_BOTTOM_NOTE_XY = (0.030, 0.258)
_DEEP_ROUND_BOSSES = sum(shape[0] == "disc" for shape in DEEP_BOSS_SHAPES)
_SHALLOW_ROUND_BOSSES = sum(shape[0] == "disc" for shape in SHALLOW_BOSS_SHAPES)
if _DEEP_ROUND_BOSSES != len(HOLE_XZ) + len(FOOT_SCREW_XZ):
    raise AssertionError("the deep round bosses are not E1-E4 and the foot boss")
if _SHALLOW_ROUND_BOSSES != len(SHALLOW_BOSS_CENTRES):
    raise AssertionError("the shallow round bosses are not B1, D1 and F1-F4")
# Each level is named, not typed: section B-B prints its height (DEEP LEVEL /
# SHALLOW LEVEL under the model's DeepBossBottom and ShallowBossBottom).
UNDERSIDE_BOTTOM_CALLOUTS = {
    "PocketLen": "POCKET CENTERED ON PAD",
    "SocketBossDia": f"{len(SOCKET_BOSS_SHAPES)}X SOCKET\nBOSSES",
    "PocketFilletRadius": f"{2 * len(SOCKET_BOSS_SHAPES)}X BOSS\nTO WALL",
    "LongRibThickness": "RIB",
    "CrossRibThickness": "RIB",
    "HangingBossDia": (
        f"{_DEEP_ROUND_BOSSES}X BOSSES UNDER\nE1-E4, MHA-DT-024\nTO DEEP LEVEL"
    ),
    "ShallowBoss4Dia": (
        f"{_SHALLOW_ROUND_BOSSES}X BOSSES UNDER\nB1, D1, F1-F4\nTO SHALLOW LEVEL"
    ),
}
# Section B-B texts as MACHINE (Y, Z) points in the cut plane, projected
# through the section at build time: which way +Z runs up a section is
# SolidWorks' choice, and these must land in the pocket's open air whichever
# it makes. The ceiling height reads inside the pocket, in the void in front
# of the front block pad; the 3.0 rib relief and the two level heights --
# too short for their text and its level caption -- read outside the
# underside, level with what they measure.
UNDERSIDE_OUTSIDE_Y_MM = -24.0
UNDERSIDE_SECTION_TEXT_MM = {
    "PocketDepth": (POCKET_CEILING_Y / 2.0, -110.0),
    "ShallowBossBottom": (UNDERSIDE_OUTSIDE_Y_MM, BLOCK_SCREW_XZ[0][1]),
    "DeepBossBottom": (UNDERSIDE_OUTSIDE_Y_MM, FOOT_SCREW_XZ[0][1]),
    "RibRelief": (UNDERSIDE_OUTSIDE_Y_MM, 0.0),
}
UNDERSIDE_SECTION_CALLOUTS = {
    "DeepBossBottom": "DEEP\nLEVEL",
    "ShallowBossBottom": "SHALLOW\nLEVEL",
}

# Sheet 4, the underside pads (Codex P2 on #1310). The rect pads, the
# cross-tap lugs, the ribs and the MHA-DT-024 foot boss stand under seats the
# hole table does not locate, or under none, so their sizes and their places
# are model dims, placed from the table's own X0 Y0 -- the flange's rear-west
# theoretical corner, top left in a bottom view (rule 7: one feature origin
# per view; baselines, never chains). One *Bottom view at 1:2: the X
# baselines stack in rows above it and the Y baselines in columns left of it,
# shortest innermost, so no extension line crosses a dimension line.
PADS_SCALE = (1.0, 2.0)
_PADS_M_PER_MM = PADS_SCALE[0] / PADS_SCALE[1] / 1000.0
# The view's 228.6 x 143.6 mm sit right of the nine Y columns and under the
# seven X rows, its bottom edge 9.7 mm above the title block.
PADS_CENTER = (0.2253, 0.1475)


def _pads_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point for a machine X/Z station in the sheet-4 bottom view."""
    return (
        PADS_CENTER[0] + x_mm * _PADS_M_PER_MM,
        PADS_CENTER[1] + z_mm * _PADS_M_PER_MM,
    )


PADS_DATUM = _pads_xy(-BOTTOM_LENGTH / 2.0, BOTTOM_REAR_Z)
# Baseline pitch: a 3.5 mm text row and its air; the first 8 mm off the view.
PADS_BASELINE_FIRST_M = 0.008
PADS_BASELINE_ROW_M = 0.0058
_LOCK_PAD = LOCK_PAD_SHAPE
_FRONT_PEDESTAL_PAD = PEDESTAL_PAD_SHAPES[0]
_FRONT_BLOCK_PAD = BLOCK_PAD_SHAPES[0]
# X rows, innermost first: (name, machine X of the text's centre). The lugs'
# 39.6 is shorter than its "2X" text, which reads just past its witness line.
# The foot boss's extension line rises 1.75 mm west of the rear block pad's.
PADS_X_ROWS = (
    ("Lug1X", -166.5),
    ("LockPadX", -168.6),
    ("PedestalPad1X", -148.6),
    ("FootBossX", -110.0),
    ("BlockPad1X", -129.8),
    ("CrossRibX", -90.0),
    ("Lug3X", -19.8),
)
# Y columns, innermost first: (name, column offset left of X0, text depth
# below X0; sheet mm). Each pitch clears the wider neighbouring text from the
# next dimension line by 2.5 mm; the depths step down column by column, so
# neighbouring texts never share a row, each inside its own span and clear of
# every longer column's extension line (stations 19.3, 24.1, 33.6, 34.3, 69.3,
# then 109.3 on). The foot boss's extension line runs 0.7 mm over the rear
# lugs' (their fronts stand 1.4 mm in front of the boss centre), its arrow on
# its own line above theirs.
PADS_Y_COLUMNS = (
    ("PedestalPad1Y", 8.0, 6.0),
    ("BlockPad1Y", 15.5, 14.0),
    ("FootBossY", 23.0, 21.0),
    ("Lug1Y", 34.25, 28.0),
    ("LongRibY", 45.5, 36.0),
    ("Lug0Y", 58.0, 45.0),
    ("PedestalPad0Y", 70.5, 55.0),
    ("BlockPad0Y", 79.25, 65.0),
    ("LockPadY", 88.0, 75.0),
)
# Sizes, machine (X, Z) of each text. In the pocket's open air: the pedestal
# pad's length rises from its west side and the block pad's width rises from
# its west side, a row above the length. Outside, either one's extension
# lines would lie on the Y columns' (the pedestal pad's rear edge IS
# PedestalPad0Y's, its front edge 0.03 from the lock pad's; the block pad's
# rear edge 0.4 from the pedestal pad's) and cross their dimension lines.
# A vertical dimension whose text reads beyond its span hangs the text WEST
# of its dimension line, which runs at the keep X (13f1ca261 render): the
# pedestal length's line hugs its pad so its "2X 26.0" ends clear of the
# lock pad's X extension line (at the gap's midpoint it ran through "2X").
PADS_SIZE_TEXT_MM = {
    "PedestalPadLength": (
        _FRONT_PEDESTAL_PAD[1] - 1.6,
        _FRONT_PEDESTAL_PAD[4] + 16.0,
    ),
    "BlockPad0Width": (
        (_FRONT_PEDESTAL_PAD[2] + _FRONT_BLOCK_PAD[1]) / 2.0,
        _FRONT_PEDESTAL_PAD[4] + 28.0,
    ),
}
# The lock and front pedestal pads' widths read below the view (machine X, Z
# of each text), outside the silhouette, in one column left of the lock pad
# and of the title block. A dimension with a callout runs its line under the
# callout's last row, so each text block stands over its own dimension line:
# the lock pad's first, the pedestal pad's under it, below the lock pad's
# extension lines.
PADS_SIZE_BELOW_MM = {
    "LockPadWidth": (_LOCK_PAD[1] - 28.5, BOTTOM_FRONT_Z - 10.6),
    "PedestalPad0Width": (_LOCK_PAD[1] - 28.5, BOTTOM_FRONT_Z - 50.2),
}


def _cast_level(shapes: tuple, *, deep: bool) -> str:
    """Section B-B's level word for rect pads cast with the deep or the
    shallow bosses; fails if the builder hung them at the other level."""
    if not set(shapes) <= set(DEEP_BOSS_SHAPES if deep else SHALLOW_BOSS_SHAPES):
        raise AssertionError(f"{shapes} are not cast at the {'deep' if deep else 'shallow'} level")
    return "DEEP LEVEL" if deep else "SHALLOW LEVEL"


# Each rect pad group's and the lugs' cast level (machinist review of bp4:
# section B-B cuts only the block pads and the foot boss, and the round-boss
# callouts named no pad), worded as section B-B captions its 12.0 and 28.0.
# The pad sizes below the view carry it as callouts; the block pads and the
# lugs, whose sizes read inside the view or are not printed, take pointer
# notes below the view -- the block pads' in the band over the title block,
# its arrow ON the front pad's front edge, east of the corner where the
# 2X 16.0's extension line leaves it (bp5: through the edge, it read as
# crossing that line).
# The builder hangs the lugs to the shallow level (CrossTapLugs' LugBottom
# is driven by "ShallowBossBottom"; CROSS_TAP_LUG_WALLS reckons from it).
PADS_CALLOUTS = {
    "LockPadWidth": f"PAD TO\n{_cast_level((_LOCK_PAD,), deep=True)}",
    "PedestalPad0Width": f"PADS TO\n{_cast_level(PEDESTAL_PAD_SHAPES, deep=True)}",
}
# label -> (text, top-left sheet xy, leader tip machine (X, Z)).
PADS_LEVEL_NOTES = {
    "pinion-block pads level": (
        f"{len(BLOCK_PAD_SHAPES)}X PADS TO {_cast_level(BLOCK_PAD_SHAPES, deep=False)}",
        (0.222, 0.0735),
        (-20.0, _FRONT_BLOCK_PAD[3]),
    ),
    "cross-tap lugs level": (
        f"{len(CROSS_TAP_LUG_SHAPES)}X LUGS TO\nSHALLOW LEVEL",
        (0.070, 0.071),
        (-200.0, -109.0),
    ),
}
UNDERSIDE_PADS_KEEP = {
    **{
        name: (
            _pads_xy(x_mm, 0.0)[0],
            PADS_DATUM[1] + PADS_BASELINE_FIRST_M + row * PADS_BASELINE_ROW_M,
        )
        for row, (name, x_mm) in enumerate(PADS_X_ROWS)
    },
    **{
        name: (
            PADS_DATUM[0] - offset_mm / 1000.0,
            PADS_DATUM[1] - depth_mm / 1000.0,
        )
        for name, offset_mm, depth_mm in PADS_Y_COLUMNS
    },
    **{
        name: _pads_xy(*xz)
        for name, xz in (*PADS_SIZE_TEXT_MM.items(), *PADS_SIZE_BELOW_MM.items())
    },
}
# Below the Y columns, left of the title block: the view's scale, the
# baselines' origin, named as sheet 2 names it, and where the levels print.
PADS_NOTE = (
    "BOTTOM VIEW SCALE 1:2\n"
    "PAD, LUG, RIB AND FOOT-BOSS\n"
    "LOCATIONS FROM HOLE TABLE\n"
    "X0 Y0: FLANGE OUTER SHARP CORNER\n"
    "LEVELS: SECTION B-B, SHEET 3"
)
PADS_NOTE_XY = (0.020, 0.052)


_SW_NOTE = 6  # swAnnotationType_e.swNote


def _log_tapped_hole_notes(adapter: Any, ddoc: Any) -> None:
    """Log each descriptive tapped-hole note by sheet and view before the final
    cleanup deletes them, so a TAPPED_HOLE_NOTES mismatch names where it is."""
    per_view: dict[str, list[str]] = {}
    for sheet_name in SHEET_NAMES:
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate {sheet_name} for the note inventory")
        for view in iter_views(adapter):
            texts = []
            annotation = _early_bound(view, "IView").GetFirstAnnotation3()
            while annotation is not None:
                annotation = _early_bound(annotation, "IAnnotation")
                if annotation.GetType() == _SW_NOTE:
                    text = str(_early_bound(annotation.GetSpecificAnnotation(), "INote").GetText() or "")
                    if TAPPED_HOLE_NOTE.lower() in text.lower():
                        texts.append(text)
                annotation = annotation.GetNext3()
            if texts:
                per_view[f"{sheet_name}/{view_name(adapter, view)}"] = texts
    _telemetry.info(
        f"tapped-hole notes before cleanup: {sum(map(len, per_view.values()))} "
        f"(expected {TAPPED_HOLE_NOTES}): {per_view!r}"
    )


# Sheet 2's native hole callouts are display dimensions, which the shared
# layout audit boxes only as a nominal square around their text anchor
# (_drawing_common._dim_element, NONE scope). So the MHA-DT-002/MHA-DT-018 transfer
# callouts running into each other, and the MHA-DT-024 callout struck through by
# the plan outline, both passed it (hb-notes-2 eye pass, 2026-09-25). This
# drawing-local check boxes each callout from its own display data and fails
# on any clash; it stays out of _drawing_common so no other drawing re-keys.
CALLOUT_CLEARANCE_M = 0.001
# Two callout blocks stacked in one column read as one block unless the gap
# between them is wider than the spacing between their own rows; the
# spring block 1.7 mm over the cross-tap block read as its fourth row
# (hb-render-4 eye pass). SolidWorks sets rows 5.556 mm apart at 3.5 mm.
CALLOUT_ROW_PITCH_M = 0.005556
# The drawing policy's note rule: a text block runs to four rows at most.
CALLOUT_ROW_LIMIT = 4
_LAYOUT_LABEL_WORDS = ("SCALE", "SECTION")  # view labels among a view's notes

Box = tuple[float, float, float, float]


def box_gap(a: Box, b: Box) -> float:
    """Clearance between two (xmin, ymin, xmax, ymax) boxes; negative on overlap."""
    return max(a[0] - b[2], b[0] - a[2], a[1] - b[3], b[1] - a[3])


def find_callout_clashes(
    callouts: dict[str, Box],
    obstacles: dict[str, Box],
    clearance: float = CALLOUT_CLEARANCE_M,
) -> list[str]:
    """Every callout pair, and every callout-obstacle pair, closer than
    ``clearance`` (sheet metres), named with its clearance in mm."""
    findings = []
    names = sorted(callouts)
    for index, name in enumerate(names):
        others = [(f"callout {other}", callouts[other]) for other in names[index + 1 :]]
        others += sorted(obstacles.items())
        for other, other_box in others:
            gap = box_gap(callouts[name], other_box)
            if gap < clearance:
                findings.append(f"callout {name} vs {other}: clearance {gap * 1000.0:.1f} mm")
    return findings


def find_merged_blocks(
    callouts: dict[str, Box], min_gap: float = CALLOUT_ROW_PITCH_M
) -> list[str]:
    """Every pair of callouts stacked in one column (their x spans overlap)
    with less than ``min_gap`` between them, so they read as one block."""
    findings = []
    names = sorted(callouts)
    for index, name in enumerate(names):
        a = callouts[name]
        for other in names[index + 1 :]:
            b = callouts[other]
            if min(a[2], b[2]) <= max(a[0], b[0]):
                continue
            gap = max(a[1] - b[3], b[1] - a[3])
            if gap < min_gap:
                findings.append(
                    f"callout {name} over callout {other}: {gap * 1000.0:.1f} mm apart, "
                    f"under the {min_gap * 1000.0:.1f} mm row pitch"
                )
    return findings


def find_tall_callouts(
    rows: dict[str, dict[str, Box]], limit: int = CALLOUT_ROW_LIMIT
) -> list[str]:
    """Every callout whose text runs over ``limit`` rows."""
    return [
        f"callout {label} runs {len(label_rows)} rows, over the {limit}-row note rule"
        for label, label_rows in sorted(rows.items())
        if len(label_rows) > limit
    ]


def frame_obstacles(
    sheet_size: tuple[float, float],
    drawable: DrawableRegion,
    title_block_corner: tuple[float, float],
) -> dict[str, Box]:
    """The sheet frame as obstacle boxes: the four border bands outside the
    drawable region (the zone band that carries the frame line), and the
    title block from its top-left corner down to the sheet's bottom right."""
    width, height = sheet_size
    xmin, ymin, xmax, ymax = drawable.xmin, drawable.ymin, drawable.xmax, drawable.ymax
    left, top = title_block_corner
    return {
        "frame left": (0.0, 0.0, xmin, height),
        "frame right": (xmax, 0.0, width, height),
        "frame bottom": (0.0, 0.0, width, ymin),
        "frame top": (0.0, ymax, width, height),
        "title block": (left, 0.0, width, top),
    }


def _sheet_frame_obstacles(adapter: Any, ddoc: Any) -> dict[str, Box]:
    """frame_obstacles for the active sheet: its zone margins read live, its
    title block from the checked-in template."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    sheet = ddoc.GetCurrentSheet()
    if sheet is None:
        raise RuntimeError("callout check found no current sheet")
    region = sheet_drawable_region(
        adapter, sheet, width=template.width_m, height=template.height_m
    )
    return frame_obstacles(
        (template.width_m, template.height_m),
        region,
        (template.title_block_left_m, template.title_block_top_m),
    )


Segment = tuple[float, float, float, float]  # x0, y0, x1, y1 in sheet metres

# The hole table's datum origin draws "0", "X" and "Y" labels one character
# past its axis segments; one callout text height covers them.
DATUM_LABEL_PAD_M = 0.0035
# swLeaderSide_e (R2026x swconst.dll): which end of the shoulder the leader
# leaves from.
_LEADER_SIDE_LEFT = 1
_LEADER_SIDE_RIGHT = 2


def _callout_display_data(
    display: Any, label: str
) -> tuple[list[float], list[Segment], list[tuple[str, list[float], float]]]:
    """A native hole callout's IDisplayData: its text anchor, its lines and
    its text rows (text, lower-left, height), all in sheet metres."""
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    anchor = [float(v) for v in annotation.GetPosition()][:2]
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    # GetLineAtIndex2 -> [color, lineType, ?, ?, start xyz, end xyz].
    lines = []
    for index in range(int(data.GetLineCount())):
        values = [float(v) for v in data.GetLineAtIndex2(index)]
        lines.append((values[4], values[5], values[7], values[8]))
    texts = [
        (
            str(data.GetTextAtIndex(index)),
            [float(v) for v in (data.GetTextPositionAtIndex(index) or ())],
            float(data.GetTextHeightAtIndex(index)),
        )
        for index in range(int(data.GetTextCount()))
    ]
    _telemetry.info(
        f"callout {label} display data: anchor={anchor!r} lines={lines!r} texts={texts!r}"
    )
    return anchor, lines, texts


def _is_shoulder(line: Segment) -> bool:
    return abs(line[1] - line[3]) < 1e-7


def leader_segments(lines: list[Segment]) -> list[Segment]:
    """A callout's leader: every line of its display data but the horizontal
    shoulder under its text."""
    return [line for line in lines if not _is_shoulder(line)]


def leader_sides(lines: list[Segment], label: str) -> tuple[int, int]:
    """(attached, nearest) as swLeaderSide_e: the shoulder end the leader
    leaves from now, and the end nearer the leader's tip (the hole)."""
    shoulders = [line for line in lines if _is_shoulder(line)]
    leaders = leader_segments(lines)
    if not shoulders or not leaders:
        raise RuntimeError(f"callout {label} has no shoulder or no leader: {lines!r}")
    left = min(x for line in shoulders for x in (line[0], line[2]))
    right = max(x for line in shoulders for x in (line[0], line[2]))
    shoulder_y = shoulders[0][1]
    ends = [(x, y) for line in leaders for x, y in ((line[0], line[1]), (line[2], line[3]))]
    joint = min(ends, key=lambda end: abs(end[1] - shoulder_y))
    tip = max(ends, key=lambda end: abs(end[1] - shoulder_y))
    attached = _LEADER_SIDE_LEFT if abs(joint[0] - left) < abs(joint[0] - right) else _LEADER_SIDE_RIGHT
    nearest = _LEADER_SIDE_LEFT if abs(tip[0] - left) < abs(tip[0] - right) else _LEADER_SIDE_RIGHT
    return attached, nearest


def segment_crosses_box(segment: Segment, box: Box) -> bool:
    """True when any part of ``segment`` lies inside ``box`` (Liang-Barsky)."""
    x0, y0, x1, y1 = segment
    dx, dy = x1 - x0, y1 - y0
    low, high = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0.0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True


# A leader leaves its shoulder at the corner of the text row sitting on it,
# so its own rows are tested shrunk by this much: the joint touches the row's
# corner without running through its text.
OWN_ROW_INSET_M = 0.0002


def callout_text_rows(
    lines: list[Segment], texts: list[tuple[str, list[float], float]], label: str
) -> dict[str, Box]:
    """A callout's text rows as boxes, keyed by their text. SolidWorks centres
    every row on the shoulder, which spans the widest one, so a row runs from
    its first item's lower-left to the mirror of that point about the
    shoulder's midpoint, and up one text height."""
    shoulders = [line for line in lines if _is_shoulder(line)]
    if not shoulders or not texts:
        raise RuntimeError(f"callout {label} has no shoulder or no text rows")
    centre = (
        min(x for line in shoulders for x in (line[0], line[2]))
        + max(x for line in shoulders for x in (line[0], line[2]))
    ) / 2.0
    rows: list[list[tuple[str, list[float], float]]] = []
    for item in sorted(texts, key=lambda item: -item[1][1]):
        if rows and abs(rows[-1][0][1][1] - item[1][1]) < 0.001:
            rows[-1].append(item)
            continue
        rows.append([item])
    boxes = {}
    for row in rows:
        left = min(position[0] for _, position, _ in row)
        bottom = min(position[1] for _, position, _ in row)
        height = max(item_height for _, _, item_height in row)
        name = "".join(text for text, _, _ in sorted(row, key=lambda item: item[1][0])).strip()
        boxes[name] = (left, bottom, 2.0 * centre - left, bottom + height)
    return boxes


def find_leader_crossings(
    leaders: dict[str, list[Segment]],
    texts: dict[str, Box],
    own_rows: dict[str, dict[str, Box]] | None = None,
    inset: float = OWN_ROW_INSET_M,
) -> list[str]:
    """Every callout leader that runs through a text: another callout's box,
    a note, a label, the table or the datum origin (``texts``, where a
    callout's own box is ``callout <label>`` and skipped), or one of its own
    callout's text rows (``own_rows``, shrunk by ``inset`` so the joint at the
    shoulder end does not count)."""
    findings = []
    for label, segments in sorted(leaders.items()):
        for name, box in sorted(texts.items()):
            if name == f"callout {label}":
                continue
            if any(segment_crosses_box(segment, box) for segment in segments):
                findings.append(f"leader of callout {label} crosses {name}")
        for row, box in (own_rows or {}).get(label, {}).items():
            inner = (box[0] + inset, box[1] + inset, box[2] - inset, box[3] - inset)
            if any(segment_crosses_box(segment, inner) for segment in segments):
                findings.append(f"leader of callout {label} crosses its own row {row!r}")
    return findings


def datum_origin_boxes(axis_points: list[float], pad: float = DATUM_LABEL_PAD_M) -> dict[str, Box]:
    """The hole table's datum origin as two obstacle boxes, one per axis:
    IDatumOrigin.GetAxisPoints2 gives X start, X tip, Y start, Y tip in sheet
    space, each padded by ``pad`` for the "0", "X" and "Y" labels."""
    if len(axis_points) != 8:
        raise RuntimeError(f"datum origin axis points are not 4 (x, y) pairs: {axis_points!r}")
    boxes = {}
    for name, (x0, y0, x1, y1) in (
        ("origin X axis", axis_points[0:4]),
        ("origin Y axis", axis_points[4:8]),
    ):
        boxes[name] = (min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad)
    return boxes


# Half the section arrowhead's width, around each arrow segment.
SECTION_ARROW_PAD_M = 0.002


def note_reaches_final_sheet(text: str, removed: tuple[str, ...] = FINAL_SHEET_REMOVED_NOTES) -> bool:
    """Whether a note is ink on the final sheet: it has visible text, and
    finalize_drawing's cleanup (the same case-blind substring match as
    remove_notes_matching) does not delete it."""
    if not text.strip():
        return False
    return not any(substring.lower() in text.lower() for substring in removed)


def section_line_boxes(
    name: str,
    arrow_info: list[float],
    text_info: list[float],
    text_height: float,
    label: str,
    sheet_size: tuple[float, float],
) -> dict[str, Box]:
    """A section line's two arrows and two labels as obstacle boxes, from
    IDrSection.GetArrowInfo (start and end xyz of each arrow) and GetTextInfo
    (each label's upper-left xyz). Refuses points off the sheet: the API does
    not say these are sheet coordinates, so a view-space reply fails loud."""
    if len(arrow_info) != 12 or len(text_info) != 6:
        raise RuntimeError(
            f"section {name}: expected 12 arrow and 6 text values, got {arrow_info!r} {text_info!r}"
        )
    width, height = sheet_size
    points = [arrow_info[i : i + 2] for i in (0, 3, 6, 9)] + [text_info[i : i + 2] for i in (0, 3)]
    off_sheet = [point for point in points if not (0.0 <= point[0] <= width and 0.0 <= point[1] <= height)]
    if off_sheet:
        raise RuntimeError(f"section {name}: arrow/label points are not in sheet space: {off_sheet!r}")
    pad = SECTION_ARROW_PAD_M
    boxes = {}
    for index, base in enumerate((0, 6), start=1):
        x0, y0, x1, y1 = arrow_info[base], arrow_info[base + 1], arrow_info[base + 3], arrow_info[base + 4]
        boxes[f"section {name} arrow {index}"] = (
            min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad
        )
    glyphs = max(1, len(label))
    for index, base in enumerate((0, 3), start=1):
        x, y = text_info[base], text_info[base + 1]
        boxes[f"label section {name} {index}"] = (x, y - text_height, x + glyphs * text_height, y)
    return boxes


def _section_line_obstacles(views: dict[str, Any]) -> dict[str, Box]:
    """section_line_boxes for every section line drawn in ``views``."""
    template = DRAWING_TEMPLATES[SPEC.layout]
    boxes: dict[str, Box] = {}
    for view in views.values():
        for section in _early_bound(view, "IView").GetSectionLines() or ():
            section = _early_bound(section, "IDrSection")
            label = str(section.GetLabel())
            text_height = float(_early_bound(section.GetTextFormat(), "ITextFormat").CharHeight)
            arrow_info = [float(v) for v in (section.GetArrowInfo() or ())]
            text_info = [float(v) for v in (section.GetTextInfo() or ())]
            _telemetry.info(
                f"section line {label}: arrows={arrow_info!r} labels={text_info!r} height={text_height}"
            )
            boxes.update(
                section_line_boxes(
                    label, arrow_info, text_info, text_height, label,
                    (template.width_m, template.height_m),
                )
            )
    return boxes


def _attach_leader_nearest_hole(adapter: Any, display: Any, label: str) -> None:
    """Ask SolidWorks to run ``display``'s leader from the shoulder end nearest
    its hole, and log what it did. IAnnotation.SetLeader3 documents leader-side
    control for notes and symbols, not dimensions, so a refusal or no change is
    logged as evidence rather than failing the build."""
    _anchor, lines, _texts = _callout_display_data(display, f"{label} (leader side)")
    attached, nearest = leader_sides(lines, label)
    if attached == nearest:
        _telemetry.info(f"callout {label} leader already leaves the shoulder end nearest its hole")
        return
    annotation = _early_bound(_early_bound(display, "IDisplayDimension").GetAnnotation(), "IAnnotation")
    side_before = int(annotation.GetLeaderSide())
    style = int(annotation.GetLeaderStyle())
    smart = bool(annotation.GetSmartArrowHeadStyle())
    try:
        status: Any = int(annotation.SetLeader3(style, nearest, smart, False, False, False))
    except Exception as error:  # the evidence is the point: record a refusal, keep building
        status = f"raised {error!r}"
    _early_bound(adapter.currentModel, "IModelDoc2").GraphicsRedraw2()
    _anchor, lines_after, _texts = _callout_display_data(display, f"{label} (leader side, after)")
    attached_after, _ = leader_sides(lines_after, label)
    _telemetry.info(
        f"callout {label} leader side: attached {attached} -> {attached_after}, wanted {nearest}; "
        f"GetLeaderSide {side_before} -> {int(annotation.GetLeaderSide())}; "
        f"SetLeader3(style={style}, side={nearest}, smart={smart}) returned {status}"
    )


def callout_text_box(
    anchor: list[float],
    lines: list[tuple[float, float, float, float]],
    texts: list[tuple[str, list[float], float]],
    label: str,
) -> Box:
    """The text block of a callout from its display data, in sheet metres.

    Each text row's position is its lower-left corner in sheet space, and the
    last row sits on the horizontal shoulder SolidWorks draws under the block,
    which spans the widest row. So the block runs across the shoulder, and from
    the shoulder up to the top row's position plus its height. The sloped
    leader is left out: it has to reach into the view it points at."""
    shoulders = [line for line in lines if abs(line[1] - line[3]) < 1e-7]
    if not shoulders:
        raise RuntimeError(f"callout {label} has no horizontal shoulder line: {lines!r}")
    if not texts:
        raise RuntimeError(f"callout {label} has no text rows")
    xs = [anchor[0], *(x for line in shoulders for x in (line[0], line[2]))]
    xs += [position[0] for _, position, _ in texts]
    ys = [anchor[1], *(line[1] for line in shoulders)]
    ys += [position[1] + height for _, position, height in texts]
    return (min(xs), min(ys), max(xs), max(ys))


def _view_geometry_box(adapter: Any, view: Any, label: str) -> Box:
    """The casting's own outline in ``view``: its bounding-box corners projected
    onto the sheet, free of GetOutline's padding and attached annotations."""
    points = [
        model_point_in_view(adapter, view, (x, y, z), label=f"{label} extent")
        for x in (-BOTTOM_LENGTH / 2000.0, BOTTOM_LENGTH / 2000.0)
        for y in (0.0, STACK_HEIGHT / 1000.0)
        for z in (BOTTOM_FRONT_Z / 1000.0, BOTTOM_REAR_Z / 1000.0)
    ]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


# A drawn station a hundredth of a millimetre off its intended sheet point is
# still that point; a wrong axis mapping is tens of millimetres off.
_PROJECTION_TOLERANCE_M = 1e-5


def _require_bottom_view_mapping(
    adapter: Any, view: Any, sheet_xy: Any = _bottom_xy, *, sheet: str = "sheet 3"
) -> None:
    """Fail unless the bottom view maps machine X/Z the way ``sheet_xy`` (and
    so the cutting line and every bottom-view text position) assumes."""
    stations = ((0.0, 0.0), (100.0, 0.0), (0.0, 100.0))
    drawn = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, z / 1000.0) for x, z in stations],
        label=f"{sheet} bottom view mapping",
    )
    for (x, z), point in zip(stations, drawn, strict=True):
        expected = sheet_xy(x, z)
        error = max(abs(point[0] - expected[0]), abs(point[1] - expected[1]))
        if error > _PROJECTION_TOLERANCE_M:
            raise RuntimeError(
                f"bottom view draws machine X/Z ({x}, {z}) mm at {point}, not {expected}: "
                f"{sheet} assumes +X right and +Z up"
            )


def _section_turns_clockwise(adapter: Any, section: Any) -> bool:
    """True when ``section`` lays machine +Y rightward and +Z up or down the
    sheet: the upright section turned 90 degrees clockwise, as the shared
    section-label text says."""
    underside, deck, rear = model_points_in_view(
        adapter,
        section,
        [
            (UNDERSIDE_CUT_X / 1000.0, 0.0, 0.0),
            (UNDERSIDE_CUT_X / 1000.0, STACK_HEIGHT / 1000.0, 0.0),
            (UNDERSIDE_CUT_X / 1000.0, 0.0, BOTTOM_REAR_Z / 1000.0),
        ],
        label="section B-B orientation",
    )
    return (
        deck[0] - underside[0] > _PROJECTION_TOLERANCE_M
        and abs(deck[1] - underside[1]) <= _PROJECTION_TOLERANCE_M
        and abs(rear[0] - underside[0]) <= _PROJECTION_TOLERANCE_M
    )


def _turn_underside_section_clockwise(adapter: Any, section: Any) -> None:
    """Make section B-B read the way its label says.

    The label's rotation text is a document preference that A-A's orientation
    fixes, and which way a section from a bottom view looks is SolidWorks'
    choice. If B-B lays +Y leftward, reversing its cut direction flips it;
    if neither way is clockwise, the build fails rather than print a false
    label."""
    if _section_turns_clockwise(adapter, section):
        return
    _early_bound(section.GetSection(), "IDrSection").SetReversedCutDirection(True)
    rebuild_drawing(adapter, label="section B-B reversed")
    if not _section_turns_clockwise(adapter, section):
        raise RuntimeError(
            "section B-B lays machine +Y leftward or along the cut either way round, "
            "so its 'ROTATED 90 DEG CW' label would be false"
        )


_TEXT_OBSTACLE_KINDS = ("note ", "label ", "table ", "origin ", "section ")


def _check_hole_sheet_callouts(
    adapter: Any,
    ddoc: Any,
    *,
    callouts: dict[str, Any],
    views: dict[str, Any],
    datum_origin: Any,
) -> None:
    """Fail loud on any sheet-2 callout that crowds another callout, a note, a
    view label, the hole table, the table's datum origin, any view's casting
    outline, the sheet frame or the title block; that sits closer than a row
    pitch over another callout; that runs over four rows; or whose leader
    runs through any of those texts or through its own text rows."""
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate the holes sheet for the callout check")
    boxes = {}
    leaders = {}
    own_rows = {}
    for label, display in callouts.items():
        anchor, lines, texts = _callout_display_data(display, label)
        boxes[label] = callout_text_box(anchor, lines, texts, label)
        leaders[label] = leader_segments(lines)
        own_rows[label] = callout_text_rows(lines, texts, label)
    obstacles = _sheet_frame_obstacles(adapter, ddoc)
    obstacles.update(
        (f"view {label}", _view_geometry_box(adapter, view, label))
        for label, view in views.items()
    )
    axis_points = [
        float(v) for v in (_early_bound(datum_origin, "IDatumOrigin").GetAxisPoints2() or ())
    ]
    obstacles.update(datum_origin_boxes(axis_points))
    obstacles.update(_section_line_obstacles(views))
    sheet_view = ddoc.GetFirstView()  # the sheet itself: its free notes and tables
    for view in (sheet_view, *views.values()):
        for element, annotation in _iter_view_annotations(adapter, view):
            # Display dimensions come back as (None, annotation) (#902); only
            # notes are measured here.
            if element is None or element.kind != "note":
                continue
            # The check runs before finalize_drawing deletes the Hole Wizard
            # "Tapped Hole" notes (hb-render-3 flagged leaders over them), so
            # only notes that reach the final sheet are obstacles.
            text = _note_text(adapter, annotation)
            if not note_reaches_final_sheet(text):
                continue
            if is_rig_set_note(text):
                boxes[RIG_SET_NOTE_LABEL] = element.box
                continue
            is_label = any(word in element.label.upper() for word in _LAYOUT_LABEL_WORDS)
            obstacles[f"{'label' if is_label else 'note'} {element.label}"] = element.box
    if RIG_SET_NOTE_LABEL not in boxes:
        raise RuntimeError("callout check found no RIG SET note on the holes sheet")
    tables = [
        element
        for view in (sheet_view, *views.values())
        for element in _iter_tables(adapter, view)
    ]
    if not tables:
        raise RuntimeError("callout check found no hole table on the holes sheet")
    for element in tables:
        obstacles[f"table {element.label}"] = element.box
    _telemetry.info(
        f"hole-sheet callout boxes: {boxes!r}; leaders: {leaders!r}; obstacles: {obstacles!r}"
    )
    texts = {f"callout {label}": box for label, box in boxes.items()}
    texts.update(
        (name, box) for name, box in obstacles.items() if name.startswith(_TEXT_OBSTACLE_KINDS)
    )
    findings = (
        find_callout_clashes(boxes, obstacles)
        + find_merged_blocks(boxes)
        + find_tall_callouts(own_rows)
        + find_leader_crossings(leaders, texts, own_rows)
    )
    if findings:
        raise RuntimeError("hole-sheet callout clashes: " + "; ".join(findings))


def _visible_hole_table_entities(
    adapter: Any, view: Any, holes: tuple[tuple[float, float, float], ...]
) -> tuple[tuple[Any, ...], Any, Any]:
    """Return hole rims and the two outer edges used as ordinary table axes.

    The plan corners are broken by the modelled corner radii, so no finished
    vertex exists at the table origin.  The caller supplies these visible
    outer edges to establish their virtual intersection, while the retained
    view point makes that same theoretical corner visible on the sheet.
    """
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    circles: list[tuple[float, float, float, Any]] = []
    lines: list[tuple[tuple[float, ...], Any]] = []

    for component in components:
        visible_edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in visible_edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve.IsCircle():
                parameters = tuple(float(value) for value in curve.CircleParams)
                circles.append((parameters[0], parameters[2], parameters[6], edge))
                continue
            if curve.IsLine():
                parameters = tuple(float(value) for value in curve.LineParams)
                lines.append((parameters, edge))

    selected_edges: list[Any] = []
    used: set[int] = set()
    for x_mm, z_mm, diameter_mm in holes:
        expected = (
            x_mm / 1000.0,
            z_mm / 1000.0,
            diameter_mm / 2000.0,
        )
        candidates = sorted(
            (
                abs(x - expected[0]) + abs(z - expected[1]) + abs(radius - expected[2]),
                index,
                edge,
            )
            for index, (x, z, radius, edge) in enumerate(circles)
            if index not in used
        )
        if not candidates or candidates[0][0] > 5e-5:
            nearest = candidates[0][0] if candidates else None
            raise RuntimeError(
                "harmonic-base plan has no visible circular rim for hole "
                f"({x_mm:g}, {z_mm:g}) diameter {diameter_mm:g} mm; "
                f"nearest error={nearest!r} m"
            )
        _, index, edge = candidates[0]
        used.add(index)
        selected_edges.append(edge)

    x_axis_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[2] - BOTTOM_REAR_Z / 1000.0) <= 2e-6
        and abs(parameters[3]) >= 0.99
    ]
    y_axis_candidates = [
        edge
        for parameters, edge in lines
        if abs(parameters[0] + BOTTOM_LENGTH / 2000.0) <= 2e-6
        and abs(parameters[5]) >= 0.99
    ]
    if not x_axis_candidates or not y_axis_candidates:
        raise RuntimeError(
            "harmonic-base plan is missing a visible outer table-axis edge"
        )

    return (
        tuple(selected_edges),
        x_axis_candidates[0],
        y_axis_candidates[0],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open harmonic-base source", await adapter.open_model(str(SOURCE)))
    for index in range(len(COLUMN_SOCKET_XZ)):
        name = "SocketDia" if index == 0 else f"Socket{index}Dia"
        raw = adapter.currentModel.Parameter(f"{name}@ColumnSocketProfile")
        if raw is None:
            raise RuntimeError(f"source is missing the native {name} socket dimension")
        dimension = _early_bound(raw, "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        if int(tolerance.Type) != 0:  # swTolNONE; the assigned tube governs fit
            raise RuntimeError(f"{name} retains a fixed bore tolerance; rebuild the match-fit source")
    read_required_properties(
        adapter.currentModel,
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="harmonic-base package")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Harmonic Base Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "harmonic base; stepped; gray-iron frame",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
        raise RuntimeError("section cutting-line style did not persist")
    # swDetailingSectionViewLabels_{PerStandard,Scale,CustomScale} = 242/247/84
    # and swDetailingViewLabelsScale_SCALEcustom = 3, read off this install's
    # swconst.tlb (R2026x). The custom scale compartment is the only writable
    # text in a native section label, and it is where the rotation qualifier
    # belongs: a second free-note label beside the view is what the 2026-09
    # review read as Section A-A labelled twice.
    if not extension.SetUserPreferenceToggle(242, 0, False):
        raise RuntimeError("failed to release the standard section-label defaults")
    if not extension.SetUserPreferenceInteger(247, 0, 3):
        raise RuntimeError("failed to select custom section-label scale text")
    if not extension.SetUserPreferenceString(84, 0, SECTION_LABEL_SCALE_TEXT):
        raise RuntimeError("failed to write the section-label scale text")
    if (
        extension.GetUserPreferenceToggle(242, 0)
        or int(extension.GetUserPreferenceInteger(247, 0)) != 3
        or str(extension.GetUserPreferenceString(84, 0)) != SECTION_LABEL_SCALE_TEXT
    ):
        raise RuntimeError("native section-label scale text did not persist")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate harmonic-base geometry sheet")
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # Rule 7: hidden lines only where they inform. Nothing on this sheet is
    # communicated by a dashed edge -- the envelope, the corner radii, the
    # heights and the stamped ID all read off the outline, and every internal
    # feature is defined by sheet 2's hole table, its callouts and section A-A
    # -- so both orthographic views stay hidden-lines-REMOVED and their
    # dimensions sit on clean geometry. The dashed B1-H4 tap haystack the front
    # elevation used to carry was the 2026-09 review's clarity finding: the
    # hole table already states every size and depth it drew.
    for view in (top, side, iso):
        set_hidden_lines_removed(adapter, view)

    # FlangeToDeck is owned by a construction sketch the part saves blanked
    # (build_harmonic_base REFERENCE_SKETCHES); the hidden-owner curate shows
    # it in the one view that dimensions it. The plan owns no blanked sketch.
    top_dimensions = curate_view_dimensions(
        adapter,
        top,
        keep=GEOMETRY_TOP_KEEP,
        view_label="geometry top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_dimensions = curate_hidden_owner_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="geometry front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        [*top_dimensions, *side_dimensions],
        GEOMETRY_CALLOUTS,
    )
    for annotation in top_dimensions:
        name = dimension_name(adapter, annotation)
        if name not in ("PadCornerRadius", "FlangeCornerRadius", "DeckCornerRadius"):
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArcExtensionLineOrOppositeSide = False
        if display.ArcExtensionLineOrOppositeSide:
            raise RuntimeError(f"{name} leader did not stay on its native corner arc")
    # All three height dimensions stack on the LEFT of the front view,
    # shortest nearest the outline: the part-owned 12.7 at x 0.073 and 38.1 at
    # 0.0625 (SIDE_KEEP), this derived overall at 0.0425. At 0.052 the two
    # outer dimensions sat inside each other's ink -- this text was struck by
    # the 38.1's lower witness line and its own dimension line ran through the
    # 38.1's text (native layout audit); 10 mm of extra offset clears both,
    # and the text still sits below the 50.8 witness lines it belongs to.
    # The overall is the ONLY dimension this sheet
    # creates: it is the read-only sum of two model-owned heights (12.7 +
    # 38.1), so there is no model dimension to import and no tolerance to
    # carry -- which is why its places are the one precision the part hands
    # over as a constant.
    overall_height = _add_base_height(
        adapter,
        side,
        _horizontal_base_edge(side, STACK_HEIGHT),
        STACK_HEIGHT,
        (0.0425, 0.099),
        "overall deck height",
    )
    set_reference_dimension(
        adapter,
        overall_height.GetAnnotation(),
        label="derived overall deck height",
    )
    overall_height.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(overall_height.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError("base overall reference precision did not persist")

    # Right of the 334.0/444.5/457.2 stack, under the border: at the stack's
    # old place the 457.2 now runs through it.
    add_note(adapter, "TOP VIEW SCALE 1:4", 0.212, 0.258)
    add_note(adapter, "FRONT VIEW SCALE 1:4", 0.105, 0.075)
    add_note(adapter, "ISOMETRIC VIEW SCALE 1:6", 0.3183, 0.145)
    _attached_note(
        adapter,
        top,
        _serial_edge(top),
        f'STAMPED ID "{SERIAL_TEXT}"\n{SERIAL_HEIGHT_MM:.1f} HIGH\nAPPROX AS SHOWN',
        SERIAL_NOTE_XY,
    )
    deck_control = surface_finish_by_key(PART_SURFACE_FINISHES, "deck")
    deck_face = _resolve_faces(
        _early_bound(top.ReferencedDocument, "IModelDoc2"),
        {"deck": deck_control.face},
    )["deck"]
    deck_box = tuple(float(value) for value in deck_face.GetBox())
    if len(deck_box) != 6:
        raise RuntimeError("qualified deck face has no native bounding box")
    deck_point = tuple(float(value) for value in (deck_face.GetClosestPointOn(
        deck_box[0] + (deck_box[3] - deck_box[0]) / 4.0,
        (deck_box[1] + deck_box[4]) / 2.0,
        deck_box[2] + 3.0 * (deck_box[5] - deck_box[2]) / 4.0,
    ) or ()))
    if len(deck_point) != 5 or abs(deck_point[1] - STACK_HEIGHT / 1000.0) > 1e-7:
        raise RuntimeError(f"native deck leader point is not on the deck plane: {deck_point!r}")
    deck_finish = add_surface_finish(
        adapter, top,
        symbol_xy=(0.040, 0.138),
        control=deck_control,
        label="deck seat finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=deck_face,
        leader_attach_xy=model_point_in_view(
            adapter, top, deck_point[:3], label="qualified deck face finish anchor",
        ),
    )
    underside_finish = add_surface_finish(
        adapter, side,
        symbol_xy=(0.040, 0.052),
        control=surface_finish_by_key(PART_SURFACE_FINISHES, "underside"),
        label="underside seat finish",
        char_height=0.0025,
        entity=_horizontal_base_edge(side, 0.0),
        leader_attach_xy=model_point_in_view(
            adapter, side, (-BOTTOM_LENGTH / 4000.0, 0.0, 0.0),
            label="underside finish edge",
        ),
    )
    # Rule 5: the flange perimeter is the hole table's datum -- every sheet-2
    # coordinate is measured from the virtual corner of its west and rear
    # faces -- so the plan carries the seat grade once, read off the west
    # flange edge, and its target names the surface AND its function. The
    # part owns one control per perimeter face; this callout states all four.
    flange_west_edge = _visible_hole_table_entities(adapter, top, ())[2]
    flange_finish = add_surface_finish(
        adapter, top,
        symbol_xy=FLANGE_FINISH_XY,
        control=surface_finish_by_key(PART_SURFACE_FINISHES, "flange_west"),
        label="flange perimeter seat finish",
        char_height=0.0025,
        edge_entity=flange_west_edge,
        leader_attach_xy=_plan_xy(-BOTTOM_LENGTH / 2.0, FLANGE_FINISH_ATTACH_Z_MM),
    )
    for label, symbol in (
        ("deck", deck_finish),
        ("underside", underside_finish),
        ("flange perimeter", flange_finish),
    ):
        annotation = _early_bound(symbol.GetAnnotation(), "IAnnotation")
        annotation.BentLeaderLength = 0.035
        if abs(float(annotation.BentLeaderLength) - 0.035) > 1e-7:
            raise RuntimeError(f"{label} finish leader did not clear its roughness text")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate harmonic-base holes sheet")
    hole_top = place_view(
        adapter, str(SOURCE), "*Top", *HOLE_TOP_CENTER, scale=SHEET_SCALE
    )
    hole_side = place_view(
        adapter, str(SOURCE), "*Front", *HOLE_SIDE_CENTER, scale=SHEET_SCALE
    )
    section_line_x = _plan_xy(COLUMN_X, 0.0, center=HOLE_TOP_CENTER)[0]
    section = create_section_view(
        adapter,
        hole_top,
        line_start=(section_line_x, HOLE_TOP_CENTER[1] - 0.040),
        line_end=(section_line_x, HOLE_TOP_CENTER[1] + 0.040),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SHEET_SCALE,
        label="base column-socket section",
    )
    # Rule 7 again: the hole table plus the cross-tap and spotface callouts
    # define every hole on this sheet, and section A-A shows the socket, its
    # depth and the cross tap through it in SOLID lines, so no view here needs
    # dashed edges -- plan, front cross-tap elevation and section are all
    # hidden-lines-removed. Every pick below therefore runs against the same
    # visible-entity set the sheet exports.
    for view in (hole_top, hole_side, section):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(
        adapter,
        hole_top,
        keep=HOLE_TOP_KEEP,
        view_label="holes top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_dimensions = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # CrossTapX/CrossTapPitch are owned by a reference sketch the part saves
    # blanked, so this view takes the hidden-owner curate.
    hole_side_dimensions = curate_hidden_owner_dimensions(
        adapter,
        hole_side,
        keep=HOLE_SIDE_KEEP,
        view_label="holes front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, section_dimensions, SECTION_CALLOUTS)
    set_dimension_callouts(adapter, hole_side_dimensions, HOLE_SIDE_CALLOUTS)
    # No root-radius callout: a 0.5 mm internal root at the pad-to-flange
    # junction is not measurable with hobby-shop kit, so the model keeps its
    # fillet and the deck cutter's own corner radius defines it (2026-09
    # review over-specification item).
    # Sheet-2 left notes column, below the hole table: the RIG SET note both
    # rig transfer callouts name (the A1-A4 matched fit is on the sockets).
    add_note(adapter, RIG_SET_STEP, *RIG_SET_NOTE_XY)
    if not auto_center_marks(adapter, hole_top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base hole pattern")

    table_origin = create_view_theoretical_datum(
        adapter,
        hole_top,
        point_xy=(-BOTTOM_LENGTH / 2000.0, -BOTTOM_REAR_Z / 1000.0),
        label="harmonic-base finished-corner table origin",
    )
    rim_entities, table_x_axis, table_y_axis = _visible_hole_table_entities(
        adapter,
        hole_top,
        (
            *TABLE_HOLES,
            TRANSFER_BLOCK_HOLES[1],
            TRANSFER_SPRING_HOLE,
            TRANSFER_PEDESTAL_HOLES[0],
        ),
    )
    hole_entities = rim_entities[: len(TABLE_HOLES)]
    transfer_block_rim, transfer_spring_rim, transfer_pedestal_rim = rim_entities[
        len(TABLE_HOLES) :
    ]
    hole_table = insert_hole_table(
        adapter,
        hole_top,
        datum_xy=_TABLE_ORIGIN_XY,
        datum_point=table_origin,
        hole_points=tuple(
            _hole_rim(x, z, diameter) for x, z, diameter in TABLE_HOLES
        ),
        datum_axes=(table_x_axis, table_y_axis),
        hole_entities=hole_entities,
        expected_locations_mm=tuple(
            (x + BOTTOM_LENGTH / 2.0, BOTTOM_WIDTH / 2.0 - z)
            for x, z, _diameter in TABLE_HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="harmonic-base mounting",
    )
    hole_feature = _early_bound(
        _early_bound(hole_table, "IHoleTableAnnotation").HoleTable, "IHoleTable"
    )
    hole_feature.CombineSameSize = True
    if not hole_feature.CombineSameSize or hole_feature.CombineTags:
        raise RuntimeError("base hole table did not retain individual coordinate tags")
    if int(hole_table.RowCount) != len(TABLE_HOLES) + 1:
        raise RuntimeError("combining base hole sizes changed individual table rows")
    for row in range(int(hole_table.RowCount)):
        hole_table.SetRowHeight(row, 0.007, 0)
    table_height = sum(
        float(hole_table.GetRowHeight(row)) for row in range(int(hole_table.RowCount))
    )
    if table_height > HOLE_TABLE_ANCHOR[1] - 0.025:
        raise RuntimeError(
            f"base hole table exceeds the inner border: {table_height} m"
        )
    drawing_model.EditRebuild3()
    _spread_hole_tags(hole_top, hole_table)
    _attached_note(
        adapter,
        hole_top,
        hole_entities[TABLE_HOLES.index((*SOCKET_FIT_STATION, COLUMN_SOCKET_DIAMETER))],
        SOCKET_FIT_NOTE,
        SOCKET_FIT_NOTE_XY,
    )
    # The transferred seats: each group is its own native Hole Wizard
    # feature, so one associative callout per group carries its size and
    # count -- 4X for the block seats, 2X for the pedestal seats, and the lone
    # spring-foot seat (U34c moved the pedestals off its #4-40 feature, so it
    # no longer needs a note pointing at a table row). The block and pedestal
    # callouts share the clear band above the plan, the pedestal one left of
    # the block one so their leaders fan apart onto the rear seats. The
    # spring callout keeps the band between the plan's bottom edge and the
    # cross-screw callout, left of the section-A arrow (render r4 had it
    # colliding with the 4X cross-screw callout).
    block_callout = add_native_hole_callout(
        adapter,
        hole_top,
        edge=transfer_block_rim,
        callout_xy=BLOCK_CALLOUT_XY,
        label="pinion-block transfer seats",
        process=TRANSFER_BLOCK_CALLOUT,
    )
    pedestal_callout = add_native_hole_callout(
        adapter,
        hole_top,
        edge=transfer_pedestal_rim,
        callout_xy=PEDESTAL_CALLOUT_XY,
        label="arbor-pedestal transfer seats",
        process=TRANSFER_PEDESTAL_CALLOUT,
    )
    spring_callout = add_native_hole_callout(
        adapter,
        hole_top,
        edge=transfer_spring_rim,
        callout_xy=SPRING_CALLOUT_XY,
        label="pinion-spring transfer seat",
        process=TRANSFER_SPRING_CALLOUT,
    )
    tap_callout = add_native_hole_callout(
        adapter,
        hole_side,
        edge=_cross_tap_edge(hole_side),
        callout_xy=CROSS_TAP_CALLOUT_XY,
        label="base column-retention taps",
        process=CROSS_TAP_PROCESS,
    )
    _set_cross_tap_callout_text(tap_callout)
    # The MIN tap-drill depth prints as a whole millimetre; the diameter keeps
    # its two places (per-variable, see set_hole_callout_precision).
    set_hole_callout_precision(
        tap_callout, {"hw-tapdrldepth": 0}, label="base cross-tap drill depth"
    )
    _check_cross_tap_callout(tap_callout)
    # 38.10 is also the deck above the flange (FlangeToDeck), so the axis height
    # has to SHOW which two features it spans (2026-09 review blocker). The
    # imported Spot0Y does that natively and for free: it is the spotface
    # sketch's own dimension, from the sketch origin -- which lies ON the
    # flange underside -- to the hole CENTRE, whose center mark this view
    # draws. Its caption (HOLE_SIDE_CALLOUTS) names that Ra 3.2 seating face,
    # and its text is parked BELOW the extension lines it would otherwise be
    # struck through by: at 1:4 the two witness lines are 9.5 mm apart on
    # paper, so a four-line block centred on the dimension line put the value
    # on the line and each caption line on an extension line. Outside the band
    # SolidWorks keeps the arrows inside and jogs a leader down to the text.
    if not auto_center_marks(adapter, hole_side, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the base cross-screw entries")
    # The four sockets locate the frame columns, so their bores carry the seat
    # grade (rule 5) -- the deck symbol stops at the deck plane and the hole
    # table's bore diameters are reference-only match-fit sizes. Section A-A is
    # the one view that draws a controlled bore wall in SOLID lines, so the
    # single sheet symbol lives here and its target names all four tags; the
    # part owns one native control per bore, and add_surface_finish validates
    # this leader against the very face the control qualifies.
    socket_control = surface_finish_by_key(
        PART_SURFACE_FINISHES, socket_bore_finish_key(*SECTION_SOCKET_XZ)
    )
    socket_face = _resolve_faces(
        _early_bound(hole_top.ReferencedDocument, "IModelDoc2"),
        {"socket": socket_control.face},
    )["socket"]
    socket_point = tuple(
        float(value)
        for value in (
            socket_face.GetClosestPointOn(
                *(station / 1000.0 for station in SOCKET_LEADER_POINT_MM)
            )
            or ()
        )
    )
    if len(socket_point) != 5:
        raise RuntimeError(
            f"socket bore face returned no closest point: {socket_point!r}"
        )
    bore_radius = math.hypot(
        socket_point[0] - COLUMN_X / 1000.0,
        socket_point[2] - SECTION_SOCKET_XZ[1] / 1000.0,
    )
    if abs(bore_radius - COLUMN_SOCKET_DIAMETER / 2000.0) > 1e-7:
        raise RuntimeError(
            f"native socket leader point is not on the bore wall: {socket_point!r}"
        )
    socket_finish = add_surface_finish(
        adapter, section,
        symbol_xy=SOCKET_FINISH_SYMBOL_XY,
        control=socket_control,
        label="column socket bore finish",
        char_height=0.0025,
        entity_type="FACE",
        entity=socket_face,
        leader_attach_xy=model_point_in_view(
            adapter, section, socket_point[:3],
            label="qualified socket bore finish anchor",
        ),
    )
    socket_annotation = _early_bound(socket_finish.GetAnnotation(), "IAnnotation")
    socket_annotation.BentLeaderLength = SOCKET_FINISH_SHOULDER
    if abs(float(socket_annotation.BentLeaderLength) - SOCKET_FINISH_SHOULDER) > 1e-7:
        raise RuntimeError("socket bore finish leader shoulder did not persist")
    add_note(adapter, "TOP VIEW SCALE 1:4", *HOLES_TOP_LABEL_XY)
    add_note(adapter, "FRONT CROSS-TAP VIEW SCALE 1:4", 0.245, 0.075)
    # Two nested outlines (flange, pad side) sit 1.6 mm apart at the table
    # origin, so the corner is named instead of left to
    # be inferred from A1-A4 symmetry. The note reads from the open field left
    # of the plan view: against the corner itself it ran into the E1/F3 hole
    # tags and the table's own X0/Y0 axis labels (2026-09 review clarity item).
    # That field is only 60 mm wide -- the hole table ends at x 0.163 and the
    # X0/Y0 arrows start at x 0.207 -- so the note is reflowed to three short
    # lines and sits BESIDE the arrows it explains, clear of the table border
    # and of the spotface callout below it.
    add_note(
        adapter, "ORIGIN: FLANGE\nOUTER SHARP\nCORNER (X0 Y0)", 0.165, 0.186,
    )
    section_threads = import_cosmetic_threads(adapter, section)
    if section_threads[1] == 0:
        raise RuntimeError("section A-A has no native cosmetic-thread instances")
    _telemetry.info(f"section A-A native cosmetic threads: seeds/instances={section_threads!r}")

    # Sheet 3, the underside: the pocket in plan from below, and section B-B
    # through it for the heights. Rule 7: both views hidden-lines-removed --
    # the pocket opens downward, so every rib, boss and fillet the bottom view
    # dimensions is a visible edge, and the section draws its cut solid.
    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate harmonic-base underside sheet")
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=SHEET_SCALE
    )
    _require_bottom_view_mapping(adapter, bottom)
    cut_line_x = _bottom_xy(UNDERSIDE_CUT_X, 0.0)[0]
    underside_section = create_section_view(
        adapter,
        bottom,
        line_start=(cut_line_x, BOTTOM_CENTER[1] - 0.040),
        line_end=(cut_line_x, BOTTOM_CENTER[1] + 0.040),
        view_xy=UNDERSIDE_SECTION_CENTER,
        section_label="B",
        scale=UNDERSIDE_SECTION_SCALE,
        label="base underside section",
    )
    _turn_underside_section_clockwise(adapter, underside_section)
    for view in (bottom, underside_section):
        set_hidden_lines_removed(adapter, view)
    bottom_dimensions = curate_view_dimensions(
        adapter,
        bottom,
        keep=UNDERSIDE_BOTTOM_KEEP,
        view_label="underside bottom",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_text_xy = model_points_in_view(
        adapter,
        underside_section,
        [
            (UNDERSIDE_CUT_X / 1000.0, y / 1000.0, z / 1000.0)
            for y, z in UNDERSIDE_SECTION_TEXT_MM.values()
        ],
        label="section B-B dimension texts",
        names=tuple(UNDERSIDE_SECTION_TEXT_MM),
    )
    underside_section_dimensions = curate_view_dimensions(
        adapter,
        underside_section,
        keep=dict(zip(UNDERSIDE_SECTION_TEXT_MM, section_text_xy, strict=True)),
        view_label="section B-B",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, bottom_dimensions, UNDERSIDE_BOTTOM_CALLOUTS)
    set_dimension_callouts(
        adapter, underside_section_dimensions, UNDERSIDE_SECTION_CALLOUTS
    )
    add_note(adapter, "BOTTOM VIEW SCALE 1:4", *UNDERSIDE_BOTTOM_NOTE_XY)

    # Sheet 4, the underside pads: the same bottom view at 1:2, carrying only
    # the pads', lugs', ribs' and foot boss's sizes and places from X0 Y0.
    # Hidden lines removed like sheet 3's, so each dimensioned edge draws as
    # the visible edge it is; the "2X" prefixes come with the part's dims.
    if not ddoc.ActivateSheet(SHEET_NAMES[3]):
        raise RuntimeError("failed to activate harmonic-base underside pads sheet")
    pads = place_view(adapter, str(SOURCE), "*Bottom", *PADS_CENTER, scale=PADS_SCALE)
    _require_bottom_view_mapping(adapter, pads, _pads_xy, sheet="sheet 4")
    set_hidden_lines_removed(adapter, pads)
    pads_dimensions = curate_view_dimensions(
        adapter,
        pads,
        keep=UNDERSIDE_PADS_KEEP,
        view_label="underside pads",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, pads_dimensions, PADS_CALLOUTS)
    add_note(adapter, PADS_NOTE, *PADS_NOTE_XY)
    # Pointer notes owned by the view (add_leader_note), after the sheet's
    # own note so that one stays sheet-owned.
    for label, (text, text_xy, tip_mm) in PADS_LEVEL_NOTES.items():
        add_leader_note(
            adapter,
            text,
            text_xy=text_xy,
            attach_xy=_pads_xy(*tip_mm),
            label=label,
            view=pads,
        )

    # Policy rule 2's proof obligation, now that no sheet code writes places:
    # every imported dimension must still print what its PART authored. A
    # silent fallback to the drawing document's two places would ask the shop
    # for a band nobody specified, and nothing else on the sheet would look
    # wrong. The seven keeps partition this map, so a missing name fails too.
    assert_imported_precision(
        adapter,
        [
            *top_dimensions,
            *side_dimensions,
            *section_dimensions,
            *hole_side_dimensions,
            *bottom_dimensions,
            *underside_section_dimensions,
            *pads_dimensions,
        ],
        DRAWING_PRECISION_BY_NAME,
    )

    hole_sheet_callouts = {
        "MHA-DT-018 block transfer": block_callout,
        "MHA-DT-002 pedestal transfer": pedestal_callout,
        "MHA-DT-024 spring transfer": spring_callout,
        "MHA-VN-027 cross-tap": tap_callout,
    }
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate the holes sheet for the leader sides")
    for label, display in hole_sheet_callouts.items():
        _attach_leader_nearest_hole(adapter, display, label)
    _check_hole_sheet_callouts(
        adapter,
        ddoc,
        callouts=hole_sheet_callouts,
        views={"holes top": hole_top, "holes front": hole_side, "section A-A": section},
        datum_origin=hole_feature.DatumOrigin,
    )
    _log_tapped_hole_notes(adapter, ddoc)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Base Manufacturing Drawing",
        scale=SHEET_SCALE,
        sheet_scales={
            **dict.fromkeys(SHEET_NAMES[:3], SHEET_SCALE),
            SHEET_NAMES[3]: PADS_SCALE,
        },
        redundant_note_substrings=FINAL_SHEET_REMOVED_NOTES,
        expected_redundant_notes=TAPPED_HOLE_NOTES,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

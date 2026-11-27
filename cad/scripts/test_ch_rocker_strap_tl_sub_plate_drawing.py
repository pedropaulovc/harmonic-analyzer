"""Offline contracts for the rocker-strap sub-plate (MHA-CH-13-TL-01)."""

from __future__ import annotations

import ast
import inspect
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import _buildgraph as bg
import _config
import build_ch_rocker_strap_tl_sub_plate as part
import ch_rocker_arm_spec as arm
import ch_rocker_strap_tl_sub_plate_spec as spec
import draw_ch_rocker_strap_tl_sub_plate as drawing
import export_features
from _drawing_contract import (
    drawing_specification_violations,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _gtol_face import FaceGeometry
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM
from _layout_audit import TEXT_ROW_LIMIT
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import printed_band_mm

STEM = "ch_rocker_strap_tl_sub_plate"
INCH = 25.4
X1 = printed_band_mm(1, unit="in")
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
# The B sheet's inner border and the title block's corner (sheet metres).
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.066)


def test_registry_row_is_inch_shop_tooling_on_a_landscape_learn_sheet() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-CH-13-TL-01"
    assert row["drawing_unit"] == spec.UNIT == "in"
    entry = DRAWINGS_BY_NAME[STEM]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.LEARN
    assert bg.is_shop_fixture(STEM)
    assert STEM in bg.references_of("ch_rocker_strap_tl_fixture")
    for machine in bg.MACHINE_ASSEMBLIES:
        assert STEM not in bg.references_of(machine)


def test_spec_build_and_drawing_never_read_the_shop_or_plan_tomls() -> None:
    """COM-leaf inputs: no TOML reader imported, no TOML path named."""
    for module in (spec, part, drawing):
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all("toml" not in alias.name for alias in node.names), module
            elif isinstance(node, ast.ImportFrom):
                assert "toml" not in (node.module or ""), module
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not re.fullmatch(r"[\w./\\-]+\.toml", node.value), node.value


def test_strap_mirror_is_the_arm_spec_thinnest_finished_strap() -> None:
    assert spec.STRAP_THICKNESS_MIN == pytest.approx(
        arm.ARM_THICKNESS + arm.ARM_THICKNESS_BAND[1]
    )


def test_the_face_cut_clears_the_fence_and_stop_at_their_tallest() -> None:
    assert spec.FENCE_HEIGHT_MAX == pytest.approx(spec.FENCE_HEIGHT + XXX)
    assert spec.FENCE_HEIGHT_MAX == pytest.approx(0.079 * INCH)
    assert spec.FACE_CUT_CLEARANCE_MIN > 0.4


def test_each_notch_covers_its_plan_station_at_the_worst_case() -> None:
    """R.07 MAX corners, the notch ends .XX short, the depth .16."""
    assert spec.CORNER_RADIUS == pytest.approx(0.07 * INCH)
    assert spec.CORNER_CUTTER_RADIUS == pytest.approx(INCH / 16.0)
    left, right = spec.PLAN_NOTCH_STATIONS
    assert left == pytest.approx((2.4, 21.4))
    assert right == pytest.approx((283.4, 302.4))
    for (lo, hi), (x_range, depth, rounded) in zip(
        spec.PLAN_NOTCH_STATIONS, spec.NOTCH_EXTENTS_WORST, strict=True
    ):
        assert depth == pytest.approx(0.16 * INCH)
        for corner in (
            (lo, spec.PLAN_FENCE_NOTCH_DEPTH),
            (hi, spec.PLAN_FENCE_NOTCH_DEPTH),
        ):
            assert spec._in_rounded_notch(corner, x_range, depth, rounded), corner
    # Negative control: the contract's first .875 left end misses the station
    # once its R.07 corner is at the worst case.
    short = 0.87 * INCH - XX
    assert not spec._in_rounded_notch(
        (21.4, spec.PLAN_FENCE_NOTCH_DEPTH), (0.0, short), 0.16 * INCH, (0.0, short)
    )


def test_the_clamp_seats_on_its_pocket_and_its_tap() -> None:
    assert spec.POCKET_BACK_WALL_Y + spec.CLAMP_C == pytest.approx(spec.BLANK_EDGE_Y)
    assert spec.BLANK_EDGE_Y - spec.CLAMP_A == pytest.approx(spec.CLAMP_SCREW_Y)
    assert spec.POCKET_DEPTH == spec.CLAMP_B
    # A square body clears both R.07 MAX corners at the pocket's shortest.
    assert spec.POCKET_END_CLEARANCE == pytest.approx(
        (spec.POCKET_LENGTH - XX - spec.CLAMP_BODY_WIDTH - 2.0 * spec.CORNER_RADIUS)
        / 2.0
    )
    assert spec.POCKET_END_CLEARANCE > 0.4
    for station in spec.CLAMP_STATIONS:
        lo, hi = station - spec.POCKET_LENGTH / 2.0, station + spec.POCKET_LENGTH / 2.0
        assert 0.0 < lo and hi < spec.RIGHT_END_X
    assert spec.CLAMP_TAP_DRILL == TAP_DRILL_MM["#4-40"]
    assert spec.CLAMP_THREAD_LENGTH_MIN >= 1.5 * THREAD_MAJOR_MM["#4-40"]


def test_the_hub_tap_states_its_worst_case_engagement() -> None:
    """Owner ruling 2026-11-23: "change the screw to #10-32. The sub-plate's
    tapped hole becomes #10-32" (reversing 2026-11-17's "Use a 1/4-20 hub
    screw", whose acceptance of the .23 in of thread stands), through from
    the counterbore floor; full thread after the .010 edge break at both tap
    mouths (Codjiflo review of #3056) is .21 nominal (1.11D). At the worst
    case it is .186 (0.98D; the 1/4-20 had .76D), the counterbore's depth
    taken at its wizard callout's .XX (#3622), stated as a fact floored to
    two places."""
    assert spec.HUB_TAP_THREAD == "#10-32"
    assert spec.HUB_TAP_DRILL == TAP_DRILL_MM["#10-32"] == pytest.approx(0.159 * INCH)
    assert spec.HUB_THREAD_MAJOR == pytest.approx(0.190 * INCH)
    assert spec.HUB_THREAD_LENGTH == pytest.approx(0.231 * INCH)
    assert spec.TAP_MOUTH_BREAK == pytest.approx(0.010 * INCH)
    assert spec.HUB_CBORE_BAND == pytest.approx((XX, -XX))
    assert spec.HUB_THREAD_LENGTH_MIN == pytest.approx(
        spec.HUB_THREAD_LENGTH - XX - XXX - XX - 2.0 * spec.TAP_MOUTH_BREAK
    )
    assert spec.HUB_THREAD_LENGTH_MIN == pytest.approx(0.186 * INCH)
    assert spec.CLAMP_THREAD_LENGTH_MIN == pytest.approx(
        spec.CLAMP_THREAD_LENGTH - XX - XXX - XXX - 2.0 * spec.TAP_MOUTH_BREAK
    )
    assert spec.HUB_ENGAGEMENT_STATEMENT == "ENGAGEMENT .18 MIN (.98D)"
    assert spec.HUB_THREAD_LENGTH_MIN < spec.HUB_THREAD_REQUIRED
    exception = _config.parts(spec.PART_NAME)["machinist_exceptions"][0]
    assert exception["id"] == "RV-01" and "(1.01D)" in exception["finding"]
    assert "Owner ruling 2026-11-23" in exception["reason"]
    assert "Use a 1/4-20 hub screw." in exception["reason"]
    for word in ("ACCEPT", "RULING", "RULE", "OWNER"):
        assert word not in spec.HUB_ENGAGEMENT_STATEMENT
    # At the shallowest wizard depth the drill and reamer tips stay clear of
    # the floor by more than the tool-length reading; at the nominal depth
    # they keep the plan's relief clearance.
    assert spec.HUB_CBORE_TIP_CLEARANCE_MIN == pytest.approx(0.445, abs=1e-9)
    assert spec.HUB_CBORE_TIP_CLEARANCE_MIN > 0.001 * INCH
    assert (
        spec.HUB_CBORE_DEPTH + max(spec.PLAN_DRILL_TIP_Z, spec.PLAN_REAM_TIP_Z)
        >= spec.PLAN_RELIEF_FLOOR_CLEARANCE
    )


def test_the_counterbore_is_what_the_plug_mirrors() -> None:
    import ch_rocker_strap_tl_hub_plug_spec as plug

    assert spec.HUB_CBORE_DIA == pytest.approx(0.500 * INCH)
    assert spec.HUB_CBORE_DEPTH == pytest.approx(0.185 * INCH)
    assert spec.COUNTERBORE_FLOOR_Z == pytest.approx(-spec.HUB_CBORE_DEPTH)
    assert plug.COUNTERBORE_DIA == spec.HUB_CBORE_DIA
    assert plug.COUNTERBORE_DEPTH == spec.HUB_CBORE_DEPTH


def test_the_hub_is_one_wizard_counterbore_over_its_tap_drill() -> None:
    """mr5, mr7: the counterbore's Ø and depth print on its callout with the
    drill (drawing-guidelines: "a depth is never deferred to a view"), so
    the hub is one Hole Wizard counterbore whose drill is the #10-32's, the
    thread a cosmetic thread on it, THRU."""
    hole = spec.HUB_HOLE_SPEC
    assert hole.kind == "counterbore_socket"
    assert hole.end == "through_all"
    assert hole.overrides_mm == {
        "HoleDiameter": spec.HUB_TAP_DRILL,
        "CounterBoreDiameter": spec.HUB_CBORE_DIA,
        "CounterBoreDepth": spec.HUB_CBORE_DEPTH,
    }
    assert (hole.size, spec.HUB_THREAD_ROW) == ("#10", "10-32 UNF")
    assert "Tapped Hole" in spec.HUB_THREAD_LABEL
    source = inspect.getsource(part._hub)
    assert "spec.HUB_HOLE_SPEC" in source
    assert 'name="HubHole"' in source
    assert "adapter.add_thread(" in source
    assert 'end_type="through"' in source
    assert "create_cut_extrude" not in source
    assert "HUB_" not in inspect.getsource(part._taps)
    assert spec.DRAWING_DIMENSIONS["HubHole"] == {"HubX", "HubY"}


def test_the_frame_stacks_from_the_faced_top_to_the_underside() -> None:
    assert spec.PLATE_LENGTH == pytest.approx(13.0 * INCH)
    assert spec.RIGHT_END_X == pytest.approx(spec.LEFT_END_X + spec.PLATE_LENGTH)
    assert spec.FRONT_EDGE_Y == pytest.approx(-2.5 * INCH)
    assert spec.UNDERSIDE_Z == pytest.approx(spec.FENCE_HEIGHT - spec.PLATE_THICKNESS)
    assert spec.POCKET_FLOOR_Z == pytest.approx(-spec.POCKET_DEPTH)


def test_finished_volume_is_the_blank_less_every_cut() -> None:
    r = spec.CORNER_RADIUS
    corner = (1.0 - math.pi / 4.0) * r * r
    pocket_width = spec.POCKET_NEAR_WALL_Y - spec.POCKET_BACK_WALL_Y
    expected = (
        330.2 * 76.2 * 12.446
        - 317.5 * 63.5 * 1.8796
        - (23.368 + 36.068) * 4.318 * 1.8796
        + 3 * corner * 1.8796
        - 4 * (14.224 * pocket_width - 4 * corner) * 3.556
        - math.pi / 4.0 * 12.7**2 * 4.699
        - 4 * math.pi / 4.0 * 2.261**2 * (10.5664 - 3.556)
        - math.pi / 4.0 * 4.0386**2 * (10.5664 - 4.699)
    )
    assert spec.V_FINISHED == pytest.approx(expected)
    assert pocket_width == pytest.approx(spec.CLAMP_C)


def test_printed_dimensions_sit_on_their_inch_grid() -> None:
    for name, places in spec.DRAWING_PRECISION_BY_NAME.items():
        value = spec.DIMENSION_VALUES[name]
        assert spec.inch_grid_mm(value, places) == pytest.approx(value, abs=1e-9), name


def test_explicit_bands_are_the_only_model_tolerances() -> None:
    bands = model_toleranced_dimensions(part)
    assert bands == {
        # #3713: the pocket's back wall takes the title block's .XXX.
        ("HubHole", "HubX"): "spec.HUB_LOCATION_TOL",
        ("HubHole", "HubY"): "spec.HUB_LOCATION_TOL",
    }
    resolved = {
        (getattr(spec, feature.removeprefix("spec.")), name)
        if feature.startswith("spec.")
        else (feature, name)
        for feature, name in bands
    }
    assert set(spec.SYMMETRIC_BANDS) == resolved
    for feature, name in (
        *spec.SYMMETRIC_BANDS,
        *spec.MAX_RADII,
        *spec.DIMENSION_PREFIXES,
    ):
        assert name in spec.DRAWING_DIMENSIONS[feature], (feature, name)
    # Every tight or three-place size states its mate or reason (rule 3);
    # routine tap locations print at two places (machinist review r24).
    three_place = {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 3
    }
    explained = set(spec.DIMENSION_CALLOUTS) | {
        name for _f, name in spec.SYMMETRIC_BANDS
    }
    assert three_place <= explained
    for name in ("ClampTapY", *spec.CLAMP_TAP_X_NAMES):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 2, name


def test_every_drive_expression_names_a_global() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(re.findall(r'"([A-Za-z]+)"', node.value))
    names.discard("in")
    assert names, "no drive expressions found"
    assert names <= set(part.GLOBALS), sorted(names - set(part.GLOBALS))
    for index in range(1, len(spec.CLAMP_STATIONS) + 1):
        assert f"ClampStation{index}" in part.GLOBALS


def test_section_sizes_live_in_hidden_reference_sketches_on_each_cut() -> None:
    """A section imports no sketch or extrusion size (farm run
    20261117T234245842Z), so each size a section prints is a reference
    chord's length or start in its cutting plane, and the sketch is saved
    hidden. Both planes cut across the plate's full width (Right-parallel):
    A-A beside pocket 3's tap inside its straight walls, B-B on the hub's
    axis (machinist review mr5: .15 off it, B-B missed the tapped hole)."""
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_A_REFERENCE] == set(
        drawing.SECTION_A_KEEP
    )
    assert spec.DRAWING_DIMENSIONS[spec.SECTION_B_REFERENCE] == set(
        drawing.SECTION_B_KEEP
    )
    for feature in ("Plate", "PlateTop", "ClampPockets", "HubThread"):
        assert feature not in spec.DRAWING_DIMENSIONS, feature
    station = spec.CLAMP_STATIONS[2]
    straight = spec.POCKET_LENGTH / 2.0 - spec.CORNER_RADIUS
    assert THREAD_MAJOR_MM["#4-40"] / 2.0 < spec.SECTION_A_X - station < straight
    assert spec.SECTION_B_X == spec.HUB_X
    # Each cutting line lies on its plane and runs past both long edges (mr5:
    # A-A stopping in the floor read as a part 2.55 wide).
    for start, end in (drawing.SECTION_A_LINE, drawing.SECTION_B_LINE):
        assert start[0] == end[0]
        assert start[1] > spec.BACK_EDGE_Y and end[1] < spec.FRONT_EDGE_Y
    assert drawing.SECTION_A_LINE[0][0] == spec.SECTION_A_X
    assert drawing.SECTION_B_LINE[0][0] == spec.SECTION_B_X
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    blanked = [
        ast.unparse(node.args[1])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "blank_reference_sketches"
    ]
    assert blanked == ["(spec.SECTION_A_REFERENCE, spec.SECTION_B_REFERENCE)"]


# --- The sheet, modelled offline (sheet mm) ------------------------------------------
# Calibrated on farm run 20261118T015112413Z (r15), the first to build the
# sheet whole, from its COM text widths and the audit's ink boxes; the
# primitives' checks against farm run 20261118T001932117Z's (r7) findings.
# Text: Century Gothic, rows 3.5 mm tall printing 3.6 mm of ink, 5.6 mm
# apart, a block centred on its text point; per character about 3.0-4.2 mm
# a wide capital, 2.4 a narrow one, 1.2 an I, 2.6 a digit, 1.3 a point or a
# space, 5.3 the Ø symbol (_GLYPH), the ⌴ and ↧ symbols taken at 4.0 and
# 2.6 (r16 printed neither). A dimension measured up the sheet whose
# text stands past its span prints the text beside its dimension line, on
# the side away from its points: from 0.3 mm (two rows or more) or 1.4 mm
# (one row) off the line, its dimension line rising to the bottom row and
# running under it (r15's FenceHeight, HubCboreDepth, PocketDepth,
# NotchDepth). Extension lines from 1 mm off their point to 1.5 mm past the
# dimension line; arrows 3.5 mm long inside each end, or outside a span
# under 8 mm; a text inside its span 1 mm clear of its own arrows
# (machinist review mr5: ClampTapY's arrow ran through its '6'). A cutting
# line's arrows 12 mm long, pointing +X, its letter 6.35 mm tall from 1.35
# mm under the line's end, 13.9..19.6 mm right of it (farm run
# 20261118T020401122Z, r16: GetTextInfo's origins 13.9 and 14.6 mm right of
# A's and B's ends, 5.0 mm over them); a hole callout's leader ending 1.1 mm
# under its block, 1.5 mm out from the side facing its arrow; a caption's
# title row 45.6 mm wide and 6.5 mm tall under its point, its scale row
# (r23: 11.1..14.7 mm under it) as wide as its text. The limits
# (_layout_audit.GATING_KINDS, with the reported text-separation and
# extension-near-text held too): 3.57 mm between texts, 2 mm from an
# extension line or an arrow to another's text, no text on a line, no leader
# across a line, a cutting line or another leader, no dimension line across
# another's extension line, a hole callout's leader at most 10 mm further
# over the part than its feature's shortest way out, everything inside the
# border and off the title block.
_ROW = 3.6
_ROW_PITCH = 5.6
_SECTION_ARROW = 12.0
_SHORT_SPAN = 8.0
_ARROW = 3.5
_OUTSIDE_LINE = 6.3
_OWN_ARROW_GAP = 1.0
_BESIDE_LINE = {1: 1.4, 2: 0.3}
_LETTER = (13.9, 19.6, -1.35, 5.0)
_CAPTION_TITLE = (22.8, 6.5)
_CAPTION_SCALE_ROW = (11.1, 15.6)
_TEXT_GAP = 3.57
_LINE_GAP = 2.0
_DETOUR_LIMIT = 10.0
_GLYPH = {
    **dict.fromkeys("MW", 4.2),
    **dict.fromkeys("GOQ", 3.6),
    **dict.fromkeys("CD", 3.4),
    **dict.fromkeys("ABHKNRUVXY", 3.2),
    **dict.fromkeys("EFLPSTZJ", 2.4),
    "I": 1.2,
    "m": 3.6,
    **dict.fromkeys("0123456789±", 2.6),
    **dict.fromkeys(". ()/:", 1.3),
    "-": 1.6,
    "Ø": 5.3,
    "⌴": 4.0,
    "↧": 2.6,
}
# r15's widths (mm): each text's COM width, a one-row dimension's less the
# 2.6 mm of the spaces round its value.
_R15_WIDTHS = {
    ".074": 9.1,
    "CLEARS MHA-CH-13 FACE CUT": 68.0,
    "CLEARS MHA-CH-13 DRILL AND REAMER": 88.9,
    "ENGAGEMENT .21 MIN (.84D)": 64.8,
    "SEATS TL-VN-50 HEEL": 44.7,
    "TL-VN-50 SEAT": 30.7,
    "4X .140": 15.8,
    "1.875 ±.002": 24.5,
    "4X 4-40 UNC THRU ALL": 49.0,
    "Ø.089 DRILL THRU ALL": 50.0,
    "1/4-20 UNC THRU ALL": 46.9,
    "LOCATES TL-02": 32.4,
    "1.000 ±.002": 24.5,
    "16X .07 max.": 28.2,
    "3X .07 max.": 25.6,
    "11.000": 14.2,
    "1.650": 11.6,
}


def _width(text: str) -> float:
    return sum(_GLYPH.get(char, 2.3) for char in text)


def _mm(point_m: tuple[float, float]) -> tuple[float, float]:
    return (point_m[0] * 1000.0, point_m[1] * 1000.0)


def _block(centre_mm: tuple[float, float], rows: list[str]) -> tuple[float, ...]:
    half_w = max(_width(row) for row in rows) / 2.0
    half_h = (_ROW + _ROW_PITCH * (len(rows) - 1)) / 2.0
    x, y = centre_mm
    return (x - half_w, y - half_h, x + half_w, y + half_h)


def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _point_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0.0 else ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2
    t = min(1.0, max(0.0, t))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _segments_meet(a, b, c, d) -> bool:
    d1, d2 = _cross(c, d, a), _cross(c, d, b)
    d3, d4 = _cross(a, b, c), _cross(a, b, d)
    return d1 * d2 <= 0.0 and d3 * d4 <= 0.0 and (d1, d2, d3, d4) != (0.0,) * 4


def _segment_distance(a, b, c, d) -> float:
    if _segments_meet(a, b, c, d):
        return 0.0
    return min(
        _point_segment(a, c, d),
        _point_segment(b, c, d),
        _point_segment(c, a, b),
        _point_segment(d, a, b),
    )


def _box_edges(box):
    x0, y0, x1, y1 = box
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


def _segment_box(segment, box) -> float:
    (a, b), (x0, y0, x1, y1) = segment, box
    if any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b)):
        return 0.0
    return min(_segment_distance(a, b, *edge) for edge in _box_edges(box))


def _box_gap(a, b) -> float:
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    return math.hypot(dx, dy)


# SolidWorks' symbol tokens as they print.
_SYMBOLS = {"<HOLE-SPOT>": "⌴", "<MOD-DIAM>": "Ø", "<HOLE-DEPTH>": "↧"}


def _printed(text: str) -> str:
    for token, glyph in _SYMBOLS.items():
        text = text.replace(token, glyph)
    return text


def _rows(name: str) -> list[str]:
    """A dimension's printed rows: prefix, value, band or limit, mate. A
    prefix replaces SolidWorks' own R or Ø, so each carries its symbol."""
    places = spec.DRAWING_PRECISION_BY_NAME[name]
    value = spec.inch_text(spec.DIMENSION_VALUES[name], places)
    prefixes = {n: p for (_f, n), p in spec.DIMENSION_PREFIXES.items()}
    prefix = _printed(prefixes.get(name, ""))
    if any(n == name for _f, n in spec.SYMMETRIC_BANDS):
        value += " ±.002"
    if any(n == name for _f, n in spec.MAX_RADII):
        value += spec.MAX_SUFFIX
    callout = spec.DIMENSION_CALLOUTS.get(name)
    return [prefix + value, *(callout.split("\n") if callout else [])]


def _top(x, y):
    return _mm(drawing.top_xy(x, y))


def _sec_a(y, z):
    return _mm(drawing.section_a_xy(y, z))


def _sec_b(y, z):
    return _mm(drawing.section_b_xy(y, z))


def _polyline(view, points, closed=True):
    sheet = [view(*p) for p in points]
    pairs = list(zip(sheet, sheet[1:] + sheet[:1] if closed else sheet[1:]))
    return [pair for pair in pairs if pair[0] != pair[1]]


def _circle(centre, radius, count=24):
    return [
        (
            (
                centre[0] + radius * math.cos(2 * math.pi * i / count),
                centre[1] + radius * math.sin(2 * math.pi * i / count),
            ),
            (
                centre[0] + radius * math.cos(2 * math.pi * (i + 1) / count),
                centre[1] + radius * math.sin(2 * math.pi * (i + 1) / count),
            ),
        )
        for i in range(count)
    ]


# The native counterbore callout's parts as SolidWorks writes them
# (draw_ch_fulcrum_keeper's foot hole), printed through row (7) first, the
# counterbore row (5), then the rows below (8).
_NATIVE_CBORE_PARTS = {
    5: "<HOLE-SPOT><MOD-DIAM><hw-cbdiam> <HOLE-DEPTH><hw-cbdepth>",
    6: "",
    7: "<MOD-DIAM><hw-diam> <hw-thru>",
    8: "",
}
_CALLOUT_PRINT_ORDER = (7, 5, 6, 8)


def _hub_callout_rows() -> list[str]:
    """The hub hole's callout as it prints: hub_hole_definitions over the
    native parts, each variable at its three places, THRU as THRU ALL."""
    places = spec.HUB_CALLOUT_PLACES
    values = {
        "<hw-diam>": spec.inch_text(spec.HUB_TAP_DRILL, places),
        "<hw-cbdiam>": spec.inch_text(spec.HUB_CBORE_DIA, places),
        "<hw-cbdepth>": spec.inch_text(spec.HUB_CBORE_DEPTH, places),
        "<hw-thru>": "THRU ALL",
    }
    parts = drawing.hub_hole_definitions(dict(_NATIVE_CBORE_PARTS))
    rows = []
    for key in _CALLOUT_PRINT_ORDER:
        text = parts[key]
        for token, value in values.items():
            text = text.replace(token, value)
        rows += [row for row in _printed(text).split("\n") if row.strip()]
    return rows


class _Sheet:
    """Texts, extension lines, dimension lines and leaders by owner, and the
    lines the views draw."""

    def __init__(self) -> None:
        self.texts: dict[str, tuple[float, ...]] = {}
        self.extensions: list[tuple[str, tuple]] = []
        self.dim_lines: list[tuple[str, tuple]] = []
        self.leaders: list[tuple[str, tuple]] = []
        self.geometry: list[tuple] = []
        self.cutting: list[tuple] = []
        self.arrows: list[tuple[str, tuple]] = []
        # Each dimension's arrows (owner, segment, its text inside its span).
        self.dim_arrows: list[tuple[str, tuple, bool]] = []

    def linear(self, name, view, keep_m, p1, p2, along) -> None:
        """A linear dimension between model points ``p1``, ``p2`` measured
        along the sheet's ``along`` axis ("x": extension lines vertical)."""
        rows = _rows(name)
        centre = _mm(keep_m)
        text = _block(centre, rows)
        line = centre[1 if along == "x" else 0]
        axis, across = (0, 1) if along == "x" else (1, 0)
        ends, feet = [], []
        for point in (view(*p1), view(*p2)):
            side = math.copysign(1.0, line - point[across])
            start, stop = list(point), list(point)
            start[across] += side * 1.0
            stop[across] = line + side * 1.5
            if abs(line - point[across]) > 1.0:
                self.extensions.append((name, (tuple(start), tuple(stop))))
            ends.append(point[axis])
            feet.append(point[across])
        lo, hi = min(ends), max(ends)
        past = not lo <= centre[axis] <= hi
        above = centre[axis] > hi
        out = -1.0 if hi - lo < _SHORT_SPAN else 1.0
        for end, inward in ((lo, 1.0), (hi, -1.0)):
            tip, tail = [0.0, 0.0], [0.0, 0.0]
            tip[axis], tail[axis] = end, end + inward * out * _ARROW
            tip[across] = tail[across] = line
            # A vertical span's text breaks its line between its arrows.
            inline = along == "y" and not past and out > 0.0
            self.dim_arrows.append((name, (tuple(tip), tuple(tail)), inline))
        if out < 0.0:
            # Too short for its arrows: they stand outside, and the line runs
            # 6.3 mm past each end (farm run r27: FenceWidth's line rose
            # 6.3 mm over the back edge into NotchDepth's text; r26 drew
            # NotchDepth's own the same).
            lo, hi = lo - _OUTSIDE_LINE, hi + _OUTSIDE_LINE
        if along == "y" and past:
            # Beside its line, away from its points, the line rising (or
            # falling) to the near row and running under it.
            width = text[2] - text[0]
            gap = _BESIDE_LINE[min(len(rows), 2)]
            if line > sum(feet) / 2.0:
                text = (line + gap, text[1], line + gap + width, text[3])
                far = text[2]
            else:
                text = (line - gap - width, text[1], line - gap, text[3])
                far = text[0]
            shoulder = text[1] if above else text[3] - _ROW
            lo, hi = min(lo, shoulder), max(hi, shoulder)
            self.dim_lines.append((name, ((line, shoulder), (far, shoulder))))
        else:
            lo, hi = min(lo, text[axis + 2]), max(hi, text[axis])
        self.texts[name] = text
        a, b = [0.0, 0.0], [0.0, 0.0]
        a[axis], b[axis], a[across], b[across] = lo, hi, line, line
        self.dim_lines.append((name, (tuple(a), tuple(b))))

    def leader(self, name, start, keep_m) -> None:
        """A radius or Ø dimension's leader from ``start`` to its text's side."""
        text = _block(_mm(keep_m), _rows(name))
        self.texts[name] = text
        end = (text[0] if text[0] > start[0] else text[2], _mm(keep_m)[1])
        self.dim_lines.append((name, (start, end)))

    def callout(self, name, centre, drill_mm, callout_m, rows) -> tuple:
        text = _block(_mm(callout_m), rows)
        self.texts[name] = text
        middle = (text[0] + text[2]) / 2.0
        end = (
            text[0] - 1.5 if centre[0] < middle else text[2] + 1.5,
            text[1] - 1.1,
        )
        angle = math.atan2(end[1] - centre[1], end[0] - centre[0])
        rim = drill_mm / 4.0  # radius at 1:2
        start = (centre[0] + rim * math.cos(angle), centre[1] + rim * math.sin(angle))
        self.leaders.append((name, (start, end)))
        return start, end

    def cutting_line(self, letter, line_mm) -> None:
        (x0, y0), (x1, y1) = line_mm
        a, b = _top(x0, y0), _top(x1, y1)
        self.geometry.append((a, b))
        self.cutting.append((a, b))
        for index, (x, y) in enumerate((a, b)):
            owner = f"letter {letter}{index}"
            self.arrows.append((owner, ((x, y), (x + _SECTION_ARROW, y))))
            self.texts[f"letter {letter}{index}"] = (
                x + _LETTER[0],
                y + _LETTER[2],
                x + _LETTER[1],
                y + _LETTER[3],
            )

    def caption(self, name, point_m) -> None:
        x, y = _mm(point_m)
        self.texts[name] = (
            x - _CAPTION_TITLE[0],
            y - _CAPTION_TITLE[1],
            x + _CAPTION_TITLE[0],
            y,
        )
        half = _width(f"{drawing.SECTION_LABEL_SCALE_TEXT} 2 : 1") / 2.0
        self.texts[f"{name} scale"] = (
            x - half,
            y - _CAPTION_SCALE_ROW[1],
            x + half,
            y - _CAPTION_SCALE_ROW[0],
        )


def _sheet() -> _Sheet:
    sheet = _Sheet()
    s = spec
    half, r = s.POCKET_LENGTH / 2.0, s.CORNER_RADIUS
    top, a_keep, b_keep = (
        drawing.TOP_KEEP,
        drawing.SECTION_A_KEEP,
        drawing.SECTION_B_KEEP,
    )
    # Top view geometry: the outline, the fence face and notches, the stop
    # face, the pockets, the counterbore.
    left, right, back, front = (
        s.LEFT_END_X,
        s.RIGHT_END_X,
        s.BACK_EDGE_Y,
        s.FRONT_EDGE_Y,
    )
    nle, nrs, nd = s.NOTCH_LEFT_END, s.NOTCH_RIGHT_START, s.NOTCH_DEPTH
    sheet.geometry += _polyline(
        _top, [(left, front), (right, front), (right, back), (left, back)]
    )
    for chain in (
        [
            (0.0, front),
            (0.0, nd),
            (nle, nd),
            (nle, 0.0),
            (nrs, 0.0),
            (nrs, nd),
            (right, nd),
        ],
    ):
        sheet.geometry += _polyline(_top, chain, closed=False)
    for station in s.CLAMP_STATIONS:
        sheet.geometry += _polyline(
            _top,
            [
                (station - half, s.POCKET_BACK_WALL_Y),
                (station + half, s.POCKET_BACK_WALL_Y),
                (station + half, s.POCKET_NEAR_WALL_Y),
                (station - half, s.POCKET_NEAR_WALL_Y),
            ],
        )
    sheet.geometry += _circle(_top(s.HUB_X, s.HUB_Y), s.HUB_CBORE_DIA / 4.0)
    origin = (0.0, 0.0)
    tap1 = (s.CLAMP_STATIONS[0], s.CLAMP_SCREW_Y)
    hub = (s.HUB_X, s.HUB_Y)
    for name, p1, p2, along in (
        ("LeftEnd", (left, back), origin, "x"),
        ("NotchLeftEnd", origin, (nle, nd), "x"),
        ("NotchRightStart", origin, (nrs, -part.CUT_OVERRUN), "x"),
        ("PlateLength", (right, back), (left, back), "x"),
        *(
            (name, origin, (station, s.CLAMP_SCREW_Y), "x")
            for name, station in zip(s.CLAMP_TAP_X_NAMES, s.CLAMP_STATIONS, strict=True)
        ),
        ("HubX", origin, hub, "x"),
        ("HubY", origin, hub, "y"),
        ("ClampTapY", origin, tap1, "y"),
        ("NotchDepth", origin, (0.0, nd), "y"),
        ("FenceWidth", origin, (left, back), "y"),
        ("PlateWidth", (left, back), (left, front), "y"),
        (
            "PocketLength",
            (s.CLAMP_STATIONS[1] + half, s.POCKET_NEAR_WALL_Y),
            (s.CLAMP_STATIONS[1] - half, s.POCKET_NEAR_WALL_Y),
            "x",
        ),
    ):
        sheet.linear(name, _top, top[name], p1, p2, along)
    sheet.leader("NotchCornerR", _top(nrs + r, nd - r), top["NotchCornerR"])
    sheet.leader(
        "PocketCornerR",
        _top(s.CLAMP_STATIONS[-1] + half, s.POCKET_BACK_WALL_Y),
        top["PocketCornerR"],
    )
    sheet.cutting_line("A", drawing.SECTION_A_LINE)
    sheet.cutting_line("B", drawing.SECTION_B_LINE)
    # Sections A-A and B-B across the full width at their planes, (model Y,
    # Z); B-B through the hub's axis: the counterbore, then the tap's drill
    # through to the underside, its thread's lines at the major diameter.
    zf, zu, zp = s.FENCE_HEIGHT, s.UNDERSIDE_Z, s.POCKET_FLOOR_Z
    near, wall = s.POCKET_NEAR_WALL_Y, s.POCKET_BACK_WALL_Y
    sheet.geometry += _polyline(
        _sec_a,
        [
            (back, zf),
            (0, zf),
            (0, 0),
            (near, 0),
            (near, zp),
            (wall, zp),
            (wall, 0),
            (front, 0),
            (front, zu),
            (back, zu),
        ],
    )
    cb_wall, cz = s.HUB_Y + s.HUB_CBORE_DIA / 2.0, s.COUNTERBORE_FLOOR_Z
    cbore_front = 2.0 * s.HUB_Y - cb_wall
    drill, major = s.HUB_TAP_DRILL / 2.0, THREAD_MAJOR_MM["#10-32"] / 2.0
    sheet.geometry += _polyline(
        _sec_b,
        [
            (back, zf),
            (0, zf),
            (0, 0),
            (cb_wall, 0),
            (cb_wall, cz),
            (s.HUB_Y + drill, cz),
            (s.HUB_Y + drill, zu),
            (back, zu),
        ],
    )
    sheet.geometry += _polyline(
        _sec_b,
        [
            (s.HUB_Y - drill, cz),
            (cbore_front, cz),
            (cbore_front, 0),
            (front, 0),
            (front, zu),
            (s.HUB_Y - drill, zu),
        ],
    )
    for side in (1.0, -1.0):
        y = s.HUB_Y + side * major
        sheet.geometry.append((_sec_b(y, cz), _sec_b(y, zu)))
    # A-A's thickness chord runs down Y0 from the fence's top through the
    # material; the shown reference sketch prints it.
    sheet.geometry.append((_sec_a(0.0, zf), _sec_a(0.0, zu)))
    for name, p1, p2, along in (
        ("PocketNearWallY", origin, (near, 0.0), "x"),
        ("PocketBackWallY", origin, (wall, 0.0), "x"),
        ("PocketDepth", (wall, 0.0), (wall, zp), "y"),
        ("PlateThickness", (0.0, zf), (0.0, zu), "y"),
    ):
        sheet.linear(name, _sec_a, a_keep[name], p1, p2, along)
    sheet.linear("FenceHeight", _sec_b, b_keep["FenceHeight"], origin, (0.0, zf), "y")
    sheet.caption("caption A", drawing.SECTION_A_CAPTION_XY)
    sheet.caption("caption B", drawing.SECTION_B_CAPTION_XY)
    # Note 1 by its upper-left corner, one row.
    x, y = _mm(drawing.POCKET_SEAT_NOTE_XY)
    sheet.texts["note 1"] = (x, y - _ROW, x + _width(spec.POCKET_SEAT_NOTE), y)
    sheet.callout(
        "clamp taps",
        _top(*drawing.CLAMP_TAP_CENTRE_MM),
        s.CLAMP_TAP_DRILL,
        drawing.CLAMP_TAP_CALLOUT_XY,
        ["4X 4-40 UNC THRU ALL", "Ø.089 DRILL THRU ALL"],
    )
    sheet.callout(
        "hub hole",
        _top(*drawing.HUB_TAP_CENTRE_MM),
        s.HUB_CBORE_DIA,
        drawing.HUB_TAP_CALLOUT_XY,
        _hub_callout_rows(),
    )
    return sheet


def test_sheet_model_reproduces_the_r15_widths_and_r7_findings() -> None:
    """Farm run r15's text widths within 3 mm (5 % on the long rows), and
    farm run 20261118T001932117Z's (r7) findings flagged by the model's
    checks."""
    for text, measured in _R15_WIDTHS.items():
        tolerance = max(3.0, 0.05 * measured)
        assert _width(text) == pytest.approx(measured, abs=tolerance), text
    # r15's FenceHeight text, beside its line at x 302 away from its points,
    # its second row's ink [302.3, 369.9]: struck by HubCboreDepth's line.
    assert (
        _segment_box(((341.0, 119.5), (341.0, 101.8)), (302.3, 107.5, 369.9, 111.1))
        == 0.0
    )
    # 'section-line A' crossed by the Y extension lines leaving Y0.
    letter = (86.0, 202.5, 91.9, 208.6)
    assert _segment_box(((97.8, 207.7), (57.5, 207.7)), letter) == 0.0
    # r16's letters: each GetTextInfo origin (upper left) on the model's box.
    for end, origin in (
        ((181.9975, 216.35), (195.9038, 221.354)),
        ((155.645, 166.25), (170.2661, 171.254)),
    ):
        assert origin[0] - end[0] == pytest.approx(_LETTER[0], abs=0.75)
        assert origin[1] - end[1] == pytest.approx(_LETTER[3], abs=0.01)
    # r16's ClampTapY, centred between the hub's and the tap's levels: its
    # lower arrow ran through its '6' (mr5).
    text = _block((30.0, 187.17), ["1.650"])
    assert _segment_box(((30.0, 183.05), (30.0, 186.55)), text) < _OWN_ARROW_GAP
    # '4X .140' run through by its own extension line.
    assert (
        _segment_box(((141.0, 105.0), (166.0, 105.0)), (157.2, 102.4, 172.7, 105.9))
        == 0.0
    )
    # Rows 7 mm apart read as one callout.
    assert (
        _box_gap((124.9, 151.1, 149.0, 154.7), (120.1, 158.1, 131.5, 161.7)) < _TEXT_GAP
    )
    # A dimension line across another's extension line (PocketLength, clamp 4).
    assert _segments_meet(
        (242.1, 169.2), (234.9, 169.2), (238.5, 183.9), (238.5, 135.2)
    )


def test_no_text_crowds_another_or_sits_on_a_line() -> None:
    sheet = _sheet()
    names = sorted(sheet.texts)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            gap = _box_gap(sheet.texts[a], sheet.texts[b])
            assert gap >= _TEXT_GAP, (a, b, gap)
    for name, box in sheet.texts.items():
        for segment in sheet.geometry:
            assert _segment_box(segment, box) > 0.0, (name, segment)
        for owner, arrow in sheet.arrows:
            if owner == name:
                continue
            assert _segment_box(arrow, box) >= _LINE_GAP, (name, arrow)
    # Every dimension's arrows 2 mm from another's text (arrow-near-text
    # gates), and 1 mm from its own text inside its span.
    for owner, arrow, inline in sheet.dim_arrows:
        for name, box in sheet.texts.items():
            if name != owner:
                assert _segment_box(arrow, box) >= _LINE_GAP, (owner, name)
            elif inline:
                assert _segment_box(arrow, box) >= _OWN_ARROW_GAP, owner


def _meet_point(a, b, c, d):
    """Where lines a-b and c-d meet (None when parallel)."""
    denominator = (b[0] - a[0]) * (d[1] - c[1]) - (b[1] - a[1]) * (d[0] - c[0])
    if denominator == 0.0:
        return None
    t = _cross(c, d, a) / denominator
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def _overlays(segment, own) -> bool:
    """Whether ``segment`` lies on the same line as, and overlaps, one of
    ``own``: two extension lines from one point print as one ink."""
    for other in own:
        if (
            _point_segment(other[0], *segment) < 0.01
            or _point_segment(segment[0], *other) < 0.01
        ):
            if abs(_cross(segment[0], segment[1], other[1])) < 0.01:
                return True
    return False


def test_no_extension_line_runs_near_another_text_or_under_a_dimension_line() -> None:
    sheet = _sheet()
    for owner, segment in sheet.extensions:
        for name, box in sheet.texts.items():
            distance = _segment_box(segment, box)
            own = [s for o, s in sheet.extensions if o == name]
            if name == owner:
                assert distance > 0.0, (owner, segment)
            elif not _overlays(segment, own):
                assert distance >= _LINE_GAP, (owner, name, distance)
            else:
                assert distance > 0.0, (owner, name)
        for name, line in sheet.dim_lines + sheet.leaders:
            if name == owner or not _segments_meet(*segment, *line):
                continue
            # The notch depth's line rises past the back corner to its 2X
            # text (machinist review r26), across the fence and overall
            # widths' extension lines from that corner: rule 14 does not
            # forbid it and the audit reports it advisory (r23-r26 drew
            # the same crossing with the line's outside arrow).
            if name == "NotchDepth" and owner in ("FenceWidth", "PlateWidth"):
                continue
            # Only where the dimension line ends, or on its own extension
            # line that this one overlays (both rising from one corner).
            point = _meet_point(*line, *segment)
            assert point is not None, (owner, name)
            own = [s for o, s in sheet.extensions if o == name]
            assert any(_point_segment(point, *s) < 0.01 for s in own) or any(
                math.dist(point, end) < 0.01 for end in line
            ), (owner, name, point)
    for owner, line in sheet.dim_lines + sheet.leaders:
        for name, box in sheet.texts.items():
            if name != owner:
                assert _segment_box(line, box) >= _LINE_GAP, (owner, name)


def test_tap_callout_leaders_take_their_hole_s_shortest_way_off_the_plate() -> None:
    """Farm run 20261118T001932117Z: the hub tap's leader ran 20 mm over the
    part (led off section B-B); on the top view each leader crosses the edge
    nearest its hole."""
    sheet = _sheet()
    x0, y0 = _top(spec.LEFT_END_X, spec.FRONT_EDGE_Y)
    x1, y1 = _top(spec.RIGHT_END_X, spec.BACK_EDGE_Y)
    for name, (start, end) in sheet.leaders:
        shortest = min(start[0] - x0, x1 - start[0], start[1] - y0, y1 - start[1])
        steps = 2000
        inside = sum(
            1
            for i in range(steps)
            if x0 < start[0] + (end[0] - start[0]) * (i + 0.5) / steps < x1
            and y0 < start[1] + (end[1] - start[1]) * (i + 0.5) / steps < y1
        )
        over = math.dist(start, end) * inside / steps
        assert over - shortest <= _DETOUR_LIMIT - 2.0, (name, over, shortest)
        # No leader crosses a cutting line, another annotation's line or
        # another leader (each gates).
        others = [
            *sheet.cutting,
            *(s for _o, s in sheet.extensions),
            *(s for _o, s in sheet.dim_lines),
            *(s for o, s in sheet.leaders if o != name),
        ]
        for line in others:
            assert not _segments_meet(start, end, *line), (name, line)


def test_every_marked_dimension_prints_once_inside_the_border() -> None:
    keeps = (drawing.TOP_KEEP, drawing.SECTION_A_KEEP, drawing.SECTION_B_KEEP)
    names = [name for keep in keeps for name in keep]
    assert sorted(names) == sorted(drawing.sheet_dimension_names())
    border = tuple(value * 1000.0 for value in BORDER)
    title_left, title_top = (value * 1000.0 for value in TITLE_BLOCK)
    for name, box in _sheet().texts.items():
        assert box[0] > border[0] + 2.0 and box[1] > border[1] + 2.0, name
        assert box[2] < border[2] - 2.0 and box[3] < border[3] - 2.0, name
        assert box[2] < title_left - 2.0 or box[1] > title_top + 2.0, name


def test_each_section_caption_stands_under_its_view() -> None:
    """r15 printed B-B's caption 40 mm over its view and A-A's under its
    own: both under their views, within their spans."""
    for view, caption_m in (
        (_sec_a, drawing.SECTION_A_CAPTION_XY),
        (_sec_b, drawing.SECTION_B_CAPTION_XY),
    ):
        x, top = _mm(caption_m)
        underside = view(0.0, spec.UNDERSIDE_Z)[1]
        assert underside - _TEXT_GAP > top > underside - 3.0 * _TEXT_GAP
        assert view(spec.BACK_EDGE_Y, 0.0)[0] < x < view(spec.FRONT_EDGE_Y, 0.0)[0]


def test_each_section_caption_states_its_turn_from_projection() -> None:
    """Machinist review r23: both sections lie turned 90 deg from where they
    project and their captions did not say so. Projected, a section keeps
    its cutting line's +Y up as the top view prints it; each prints +Y left,
    the counter-clockwise quarter turn its native caption states."""
    north = [b - a for a, b in zip(drawing.top_xy(0.0, 0.0), drawing.top_xy(0.0, 1.0))]
    projected = math.atan2(north[1], north[0])
    for view in (drawing.section_a_xy, drawing.section_b_xy):
        step = [b - a for a, b in zip(view(0.0, 0.0), view(1.0, 0.0))]
        turn = math.remainder(math.atan2(step[1], step[0]) - projected, 2.0 * math.pi)
        assert math.degrees(turn) == pytest.approx(90.0)
    assert drawing.SECTION_LABEL_SCALE_TEXT == "ROTATED 90° CCW  SCALE"


class _Extension:
    def __init__(self) -> None:
        self.values: dict[tuple[str, int], object] = {}

    def SetUserPreferenceToggle(self, key, _option, value):
        self.values["toggle", key] = value
        return True

    def GetUserPreferenceToggle(self, key, _option):
        return self.values["toggle", key]

    def SetUserPreferenceInteger(self, key, _option, value):
        self.values["integer", key] = value
        return True

    def GetUserPreferenceInteger(self, key, _option):
        return self.values["integer", key]

    def SetUserPreferenceString(self, key, _option, value):
        self.values["string", key] = value
        return True

    def GetUserPreferenceString(self, key, _option):
        return self.values["string", key]


def test_section_captions_take_the_custom_scale_text() -> None:
    extension = _Extension()
    adapter = SimpleNamespace(currentModel=SimpleNamespace(Extension=extension))
    drawing._set_section_label_text(adapter)
    assert extension.values == {
        ("toggle", 242): False,
        ("integer", 247): 3,
        ("string", 84): drawing.SECTION_LABEL_SCALE_TEXT,
    }
    source = inspect.getsource(drawing.build)
    assert source.index("_set_section_label_text(adapter)") < source.index("_section(")


class _Layer:
    Visible = False
    Style = 0
    Width = 0


class _LayerManager:
    def __init__(self) -> None:
        self.layers: dict[str, _Layer] = {}

    def GetLayer(self, name):
        return self.layers.get(name)

    def AddLayer(self, name, _description, _colour, style, width):
        self.layers[name] = _Layer()
        self.layers[name].Style, self.layers[name].Width = style, width
        return 1


class _Annotation:
    def __init__(self, kind: int) -> None:
        self.kind, self.Layer = kind, ""

    def GetType(self):
        return self.kind


def test_section_b_prints_the_hub_thread_solid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Machinist review r23: the hub's thread printed dashed inside B-B's
    hatching (rule 9). Its cosmetic thread moves onto a visible thin
    continuous layer; other annotations stay put, and a section with no
    thread fails."""
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_a, **_k: None)
    manager = _LayerManager()
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetLayerManager=lambda: manager)
    )
    thread, note = _Annotation(1), _Annotation(6)
    view = SimpleNamespace(GetAnnotations=lambda: (thread, note))
    assert drawing._show_section_cosmetic_threads(adapter, view, label="B-B") == 1
    layer = manager.layers[drawing.SECTION_THREAD_LAYER]
    assert layer.Visible and (layer.Style, layer.Width) == (0, 0)
    assert (thread.Layer, note.Layer) == (drawing.SECTION_THREAD_LAYER, "")
    bare = SimpleNamespace(GetAnnotations=lambda: (note,))
    with pytest.raises(RuntimeError, match="no cosmetic thread"):
        drawing._show_section_cosmetic_threads(adapter, bare, label="B-B")
    source = inspect.getsource(drawing.build)
    call = '_show_section_cosmetic_threads(adapter, section_b, label="section B-B")'
    assert call in source


def test_counterbore_and_radii_print_their_symbols_on_model_dimensions() -> None:
    """Machinist review mr5: the counterbore's Ø.500 printed without ⌴ and
    its .185 without ↧, the radii without R and with "max.". The counterbore
    prints on its wizard callout's native row (⌴Ø.500 ↧.185, mr7: drill,
    counterbore and depth on one callout); each radius is the model's own
    dimension (PR #1388), its symbol a native prefix and the MAX limit word
    a suffix: "3X R.07 MAX"."""
    prefixes = {name: p for (_f, name), p in spec.DIMENSION_PREFIXES.items()}
    assert _hub_callout_rows()[2].startswith("⌴Ø.500 ↧.185")
    assert _rows("NotchCornerR")[0] == "3X R.07 MAX"
    assert _rows("PocketCornerR")[0] == "16X R.07 MAX"
    for _feature, name in spec.MAX_RADII:
        assert prefixes[name].endswith("X R"), name
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "set_single_limit" not in source and "SW_TOL_MAX" not in source
    assert "_max_radius(adapter, feature_name, dimension_name)" in source


def test_each_three_place_section_size_names_the_strap_feature_it_serves() -> None:
    """Machinist review mr5: "CLEARS MHA-CH-13 FACE CUT" and "... DRILL AND
    REAMER" named no part feature. Each now names the strap (MHA-CH-13) and
    its feature, and its third place is what holds its limit (the spec's
    checks: .XX's band would break it). mr6: one line of six words or fewer
    besides the drawing number, in rule 3's "CLEARS ..." form."""
    for name, feature in (("FenceHeight", "TOP FACE"),):
        words = spec.DIMENSION_CALLOUTS[name]
        assert spec.STRAP_NUMBER in words and feature in words, name
        assert words.startswith("CLEARS ") and "\n" not in words, name
        assert len(words.replace(spec.STRAP_NUMBER, "").split()) <= 6, name
        assert "FACE CUT" not in words and spec.DRAWING_PRECISION_BY_NAME[name] == 3
    assert spec.FENCE_HEIGHT + spec.XX > spec.FENCE_TOP_LIMIT


def test_the_pocket_s_tight_sizes_flag_one_note_naming_the_clamp() -> None:
    """Machinist review mr7: the 1.875 ±.002 named no mate; TL-VN-50 stood
    only on the .140. Rule 4: one feature with several tight dimensions
    names its mate once, on one numbered note each of them flags (rule 7's
    SEE NOTE n, draw_ch_channel_lever's PLATE_OFFSET_NOTE); the values stay
    the model's own dimensions."""
    flag = f"SEE NOTE {spec.POCKET_SEAT_NOTE_NUMBER}"
    assert spec.DIMENSION_CALLOUTS["PocketBackWallY"] == flag
    assert spec.DIMENSION_CALLOUTS["PocketDepth"] == flag
    assert spec.POCKET_SEAT_NOTE.startswith(f"{spec.POCKET_SEAT_NOTE_NUMBER}. ")
    words = [*spec.DIMENSION_CALLOUTS.values(), spec.POCKET_SEAT_NOTE]
    assert sum(spec.CLAMP_NUMBER in text for text in words) == 1
    assert spec.CLAMP_NUMBER in spec.POCKET_SEAT_NOTE
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_note(adapter, spec.POCKET_SEAT_NOTE, *POCKET_SEAT_NOTE_XY)" in source


def test_top_view_keeps_four_y_lanes_and_the_sections_carry_the_rest() -> None:
    """r7 stacked seven Y lanes from Y0 left of the top view; the pocket
    walls print over A-A. The widths stay on the top view (r13/r14: B-B
    never imported them), in four lanes, no extension line crossing a lane's
    dimension line: each span inner to every span holding one of its
    extension lines."""
    top = drawing.TOP_KEEP
    left = drawing.top_xy(spec.LEFT_END_X, 0.0)[0]
    front = drawing.top_xy(0.0, spec.FRONT_EDGE_Y)[1]
    back = drawing.top_xy(0.0, spec.BACK_EDGE_Y)[1]
    lanes = [name for name, (x, _y) in top.items() if x < left and name != "LeftEnd"]
    assert sorted(lanes) == [
        "ClampTapY",
        "FenceWidth",
        "HubY",
        "NotchDepth",
        "PlateWidth",
    ]
    assert (
        top["NotchDepth"][0]
        > top["FenceWidth"][0]
        > top["HubY"][0]
        > top["ClampTapY"][0]
        > top["PlateWidth"][0]
    )
    # The left end under the plate (machinist review r26: the notch depth's
    # 2X text took its room over the back corner).
    assert top["LeftEnd"][1] < front
    for name in ("NotchLeftEnd", "NotchRightStart", "PlateLength"):
        assert top[name][1] > back, name
    below = ("ClampTapX1", "ClampTapX2", "HubX", "ClampTapX3", "ClampTapX4")
    rows = [top[name][1] for name in below]
    assert all(row < front for row in rows)
    assert rows == sorted(rows, reverse=True)
    # The plate at 1:2 stands clear of the isometric.
    right = drawing.top_xy(spec.RIGHT_END_X, 0.0)[0]
    assert right < drawing.ISO_CENTER[0] - 0.06


def test_tap_callouts_open_with_the_count_then_thread_then_drill() -> None:
    """The native THRU tap layout (farm run 20261118T000009756Z): the thread
    in part 5, the drill in part 7 carrying the native count."""
    native = {
        5: "<hw-threaddesc> - <hw-threadclass> <hw-thru>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-thrutapdrldia> <hw-thru>",
        8: "",
    }
    clamp = drawing.clamp_tap_definitions(native)
    assert clamp == {
        5: "4X <hw-threaddesc> <hw-thru>",
        6: "",
        7: "<MOD-DIAM><hw-thrutapdrldia> DRILL <hw-thru>",
        8: "",
    }
    countless = {**native, 7: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>"}
    assert drawing.clamp_tap_definitions(countless) == clamp
    with pytest.raises(RuntimeError):
        drawing.clamp_tap_definitions(clamp)
    with pytest.raises(RuntimeError):
        drawing.tap_callout_definitions({5: "", 6: "", 7: "", 8: ""})
    with pytest.raises(RuntimeError):
        drawing.clamp_tap_definitions({**native, 5: "<NUM_INST>X " + native[5]})


def test_the_hub_hole_callout_prints_drill_thread_counterbore_and_shortfall() -> None:
    """mr7: the counterbore's depth printed alone in B-B. The wizard
    counterbore's native callout carries the drill, the thread on the same
    THRU, the counterbore's Ø and depth (native variables, ⌴ and ↧) with the
    plug it holds (TL-02 floats in it, #3713), and the engagement
    shortfall: four rows, the audit's tall-block limit."""
    hub = drawing.hub_hole_definitions(dict(_NATIVE_CBORE_PARTS))
    assert hub == {
        5: "<HOLE-SPOT><MOD-DIAM><hw-cbdiam> <HOLE-DEPTH><hw-cbdepth> FOR TL-02",
        6: "",
        7: "<MOD-DIAM><hw-diam> DRILL <hw-thru>\n10-32 UNF <hw-thru>",
        8: spec.HUB_ENGAGEMENT_STATEMENT,
    }
    assert _hub_callout_rows() == [
        "Ø.159 DRILL THRU ALL",
        "10-32 UNF THRU ALL",
        "⌴Ø.500 ↧.185 FOR TL-02",
        "ENGAGEMENT .18 MIN (.98D)",
    ]
    assert len(_hub_callout_rows()) <= TEXT_ROW_LIMIT
    assert drawing.hub_hole_precision(hub) == {
        "hw-cbdepth": 3,
        "hw-cbdiam": 3,
        "hw-diam": 3,
    }
    # The plug mirrors the counterbore's Ø and depth: one mate for both.
    import ch_rocker_strap_tl_hub_plug_spec as plug

    assert (plug.COUNTERBORE_DIA, plug.COUNTERBORE_DEPTH) == (
        spec.HUB_CBORE_DIA,
        spec.HUB_CBORE_DEPTH,
    )
    # No separate counterbore dimension prints anywhere.
    assert not {"HubCboreDia", "HubCboreDepth"} & drawing.sheet_dimension_names()
    for bad in (
        hub,
        {**_NATIVE_CBORE_PARTS, 7: "<MOD-DIAM><hw-diam>"},
        {**_NATIVE_CBORE_PARTS, 5: "<MOD-DIAM><hw-diam> <hw-thru>"},
        {5: "", 6: "", 7: ""},
        {**_NATIVE_CBORE_PARTS, 8: "<NOTE>\n<NOTE>"},
    ):
        with pytest.raises(RuntimeError):
            drawing.hub_hole_definitions(dict(bad))


def test_drawing_owns_no_manufacturing_literals() -> None:
    path = Path(drawing.__file__)
    assert (
        drawing_specification_violations(
            path.read_text(encoding="utf-8"), filename=str(path)
        )
        == ()
    )


def test_feature_export_names_every_requirement_the_plate_program_reads() -> None:
    manifest = export_features.requirement_manifest(STEM)
    features = manifest["features"]
    expected = {
        "plate_top",
        "faced_top",
        "underside",
        "fence_face",
        "stop_face",
        "front_edge",
        "back_edge",
        "left_end",
        "right_end",
        "fence_notch_left",
        "fence_notch_right",
        "hub_counterbore",
        "hub_tap",
        *(f"clamp_pocket_{i}" for i in range(1, 5)),
        *(f"clamp_tap_{i}" for i in range(1, 5)),
    }
    assert set(features) == expected
    assert manifest["material"]["thickness"] == spec.PLATE_THICKNESS
    assert manifest["volume_mm3"] == spec.V_FINISHED
    assert features["right_end"]["plane"]["value"] - features["left_end"]["plane"][
        "value"
    ] == pytest.approx(spec.PLATE_LENGTH)
    assert {"x", "y"} <= set(features["hub_counterbore"]["requirements"])
    assert features["faced_top"]["height"] == pytest.approx(
        [spec.FENCE_HEIGHT - XXX, spec.FENCE_HEIGHT + XXX]
    )
    assert features["hub_counterbore"]["x"] == pytest.approx(
        [spec.HUB_X - spec.HUB_LOCATION_TOL, spec.HUB_X + spec.HUB_LOCATION_TOL]
    )
    pocket = features["clamp_pocket_1"]
    assert pocket["back_wall_y"] == pytest.approx(
        [
            -spec.POCKET_BACK_WALL_Y - XXX,
            -spec.POCKET_BACK_WALL_Y + XXX,
        ]
    )
    assert pocket["corner_radius_max"] == spec.CORNER_RADIUS
    assert features["fence_notch_left"]["end_x"] == pytest.approx(
        [spec.NOTCH_LEFT_END - XX, spec.NOTCH_LEFT_END + XX]
    )
    assert features["hub_tap"]["engagement_min"] == spec.HUB_THREAD_LENGTH_MIN
    assert features["clamp_tap_3"]["at"] == pytest.approx(
        [spec.CLAMP_STATIONS[2], spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z]
    )
    for feature in features.values():
        for key in feature["requirements"]:
            assert key in feature, (feature, key)


def _plane(normal, point_mm, box_mm=()):
    length = math.hypot(*normal)
    unit = tuple(value / length for value in normal)
    box = tuple(value / 1000.0 for value in box_mm)
    return FaceGeometry(None, 4001, (*unit, *(v / 1000.0 for v in point_mm)), unit, box)


def _cylinder(diameter_mm, centre_mm, depth_mm):
    x, y, z = centre_mm
    axis = (x / 1000.0, y / 1000.0, z / 1000.0, 0.0, 0.0, 1.0)
    r = diameter_mm / 2.0
    box = tuple(v / 1000.0 for v in (x - r, y - r, z - depth_mm, x + r, y + r, z))
    return FaceGeometry(None, 4002, (*axis, diameter_mm / 2000.0), None, box)


def _owners(geometry: FaceGeometry) -> list[str]:
    selectors = export_features.feature_selectors(STEM)
    return [
        name
        for name, specs in selectors.items()
        if any(selector.matches(geometry) for selector in specs)
    ]


def test_each_feature_face_has_one_owner() -> None:
    zf, zu = spec.FENCE_HEIGHT, spec.UNDERSIDE_Z
    faces = {
        "plate_top": _plane((0, 0, 1), (100.0, -30.0, 0.0)),
        "faced_top": _plane((0, 0, 1), (-5.0, 0.0, zf)),
        "underside": _plane((0, 0, -1), (0.0, 0.0, zu)),
        "fence_face": _plane((0, -1, 0), (100.0, 0.0, 1.0)),
        "stop_face": _plane((1, 0, 0), (0.0, -30.0, 1.0)),
        "front_edge": _plane((0, -1, 0), (0.0, spec.FRONT_EDGE_Y, 0.0)),
        "back_edge": _plane((0, 1, 0), (0.0, spec.BACK_EDGE_Y, 0.0)),
        "fence_notch_left": _plane(
            (0, -1, 0),
            (10.0, spec.NOTCH_DEPTH, 1.0),
            (0.0, spec.NOTCH_DEPTH, 0.0, spec.NOTCH_LEFT_END, spec.NOTCH_DEPTH, zf),
        ),
        "fence_notch_right": _plane(
            (0, -1, 0),
            (300.0, spec.NOTCH_DEPTH, 1.0),
            (
                spec.NOTCH_RIGHT_START,
                spec.NOTCH_DEPTH,
                0.0,
                spec.RIGHT_END_X,
                spec.NOTCH_DEPTH,
                zf,
            ),
        ),
        "hub_counterbore": _cylinder(
            spec.HUB_CBORE_DIA, (spec.HUB_X, spec.HUB_Y, 0.0), spec.HUB_CBORE_DEPTH
        ),
        "hub_tap": _cylinder(
            spec.HUB_TAP_DRILL,
            (spec.HUB_X, spec.HUB_Y, spec.COUNTERBORE_FLOOR_Z),
            spec.HUB_THREAD_LENGTH,
        ),
    }
    half = spec.POCKET_LENGTH / 2.0
    for index, station in enumerate(spec.CLAMP_STATIONS, 1):
        faces[f"clamp_pocket_{index}"] = _plane(
            (0, 0, 1),
            (station, spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z),
            (
                station - half,
                spec.POCKET_BACK_WALL_Y,
                spec.POCKET_FLOOR_Z,
                station + half,
                spec.POCKET_NEAR_WALL_Y,
                spec.POCKET_FLOOR_Z,
            ),
        )
        faces[f"clamp_tap_{index}"] = _cylinder(
            spec.CLAMP_TAP_DRILL,
            (station, spec.CLAMP_SCREW_Y, spec.POCKET_FLOOR_Z),
            spec.CLAMP_THREAD_LENGTH,
        )
    for name, geometry in faces.items():
        assert _owners(geometry) == [name], name
    # A corner fillet's cylinder belongs to no requirement.
    assert _owners(_cylinder(2.0 * spec.CORNER_RADIUS, (0.0, 0.0, 0.0), 1.0)) == []


def test_cli_accepts_only_its_stem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "ch-rocker-strap"])
    with pytest.raises(SystemExit):
        drawing._parse_args()

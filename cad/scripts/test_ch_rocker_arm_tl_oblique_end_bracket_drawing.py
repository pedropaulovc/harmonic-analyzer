"""Offline contracts for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import _drawing_contract
import build_ch_rocker_arm_tl_oblique_end_bracket as part
import ch_rocker_arm_tl_oblique_end_bracket_spec as spec
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_end_bracket as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm, printed_deviations

STEM = "ch_rocker_arm_tl_oblique_end_bracket"
ARTIFACT = "ch-rocker-arm-tl-oblique-end-bracket"
TITLE_BLOCK_TOP = 0.0652  # sheet m (base bar test)
TITLE_BLOCK_LEFT = 0.216
TOP_BORDER = 0.267
RIGHT_BORDER = 0.4194
LEFT_BORDER = 0.0124


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _on_grid(mm: float, places: int) -> bool:
    """``mm`` prints exactly at ``places`` inch decimals."""
    return abs(mm / 25.4 - round(mm / 25.4, places)) < 1e-9


def _lateral(x: float) -> float:
    """Bracket model X -> machine lateral (the leadscrew spec's placement)."""
    return leadscrew.BRACKET_INNER_LATERAL + x


def test_stock_is_the_half_by_one_flat_on_edge() -> None:
    assert (spec.BRACKET_THICK, spec.BRACKET_WIDTH) == (25.4, 12.7)
    # #290: the sawn length prints as modelled at .XX.
    assert spec.UNIT == "in"
    assert _on_grid(spec.BRACKET_LENGTH, spec.LENGTH_PLACES)
    # Ruling A′: the outer end flush with the 1/2 x 6 bar's column-side edge.
    assert leadscrew.BRACKET_INNER_LATERAL + spec.BRACKET_LENGTH == pytest.approx(
        trammel.BASE_BAR_COLUMN_EDGE
    )
    assert spec.BRACKET_LENGTH == pytest.approx(leadscrew.BRACKET_LENGTH)
    assert spec.BRACKET_WIDTH == pytest.approx(leadscrew.BRACKET_WIDTH)
    # Both stock sizes print their supplier fraction as an untoleranced
    # reference over STOCK (the supplier's catalogue tolerance governs).
    assert spec.STOCK_DIMENSIONS == {"BracketWidth", "BracketThick"}
    assert spec.STOCK_CALLOUTS == {"BracketWidth": "STOCK", "BracketThick": "STOCK"}
    assert not spec.STOCK_DIMENSIONS & set(spec.CALLOUTS_BELOW)
    sizes = {"BracketWidth": spec.BRACKET_WIDTH, "BracketThick": spec.BRACKET_THICK}
    for name, denominator in spec.STOCK_FRACTION_DENOMINATORS.items():
        assert sizes[name] / 25.4 * denominator == pytest.approx(
            round(sizes[name] / 25.4 * denominator)
        )
    # The 13 KP08 foot (UNVERIFIED) overhangs the 12.7 top 0.15 a side.
    assert spec.KP08_FOOT_OVERHANG == pytest.approx(0.15)


def test_two_holes_land_on_the_blocks_bolt_spacing_about_the_screw() -> None:
    # Owner ruling Main 2026-11-06 (option B): two THRU holes at the KP08's
    # 42 mm pitch, X 13.925 and 55.925, each tapped #8-32 from both faces.
    holes = [_features()[f"tap_{i}"] for i in (1, 2)]
    laterals = [_lateral(h["at"][0]) for h in holes]
    half = leadscrew.KP08_BOLT_SPACING / 2.0
    assert laterals == pytest.approx(
        [leadscrew.SCREW_LATERAL - half, leadscrew.SCREW_LATERAL + half]
    )
    assert laterals == pytest.approx(list(leadscrew.BAR_SCREW_LATERALS))
    # Owner ruling 4 (2026-11-01): the KP08's metric stations print exact
    # millimetres at three places, labelled mm, with the millimetre title
    # block's three-place band.
    assert spec.HOLE_X == pytest.approx((13.925, 55.925))
    assert spec.HOLE_X == pytest.approx(leadscrew.BRACKET_HOLES_X)
    assert all(x == round(x, 3) for x in spec.HOLE_X)
    assert spec.METRIC_DIMENSIONS == {
        ("KP08Taps", "KP08Tap1X"): (3, 0.13),
        ("KP08Taps", "KP08Tap2X"): (3, 0.13),
    }
    assert spec.HOLE_BAND == printed_band_mm(3, unit="mm")
    assert "set_metric_vendor_units(" in Path(part.__file__).read_text(encoding="utf-8")
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "print_imported_metric_dimensions(" in sheet
    for hole in holes:
        x = hole["at"][0]
        assert hole["station"] == pytest.approx([x - 0.13, x + 0.13])
        assert hole["at"][1] == 0.0  # the row on the screw's KP08_S
        assert hole["at"][2] == spec.BRACKET_THICK and hole["axis"] == [0.0, 0.0, -1.0]
        assert hole["thru"] is True
    assert spec.SCREW == leadscrew.BAR_SCREW == leadscrew.KP08_SCREW == "#8-32"
    # The KP08-face thread: THRU ALL from the intact top face.
    assert spec.KP08_TAP_SPEC.kind == "tapped"  # UNC: the block's holes are plain
    assert spec.KP08_TAP_SPEC.size == "#8-32"
    assert spec.KP08_TAP_SPEC.end == "through_all"
    assert spec.KP08_TAP_FACE == ((0.0, 0.0, 1.0), spec.BRACKET_THICK)
    # The bar-face thread: a blind wizard from the bottom, its drill stopping
    # where the KP08-face thread ends; one #29 tap drill for both.
    assert spec.BAR_TAP_SPEC.kind == "tapped"
    assert spec.BAR_TAP_SPEC.size == "#8-32"
    assert spec.BAR_TAP_SPEC.end == "blind"
    assert spec.BAR_TAP_SPEC.depth_mm == pytest.approx(
        spec.BRACKET_THICK - spec.KP08_THREAD_DEPTH
    )
    assert spec.BAR_TAP_SPEC.overrides_mm == {"ThreadDepth": spec.BAR_THREAD_DEPTH}
    assert spec.BAR_TAP_FACE == ((0.0, 0.0, -1.0), 0.0)
    assert spec.TAP_DRILL == pytest.approx(3.454)
    # No counterbore in this part: the bar screws come up through the bar.
    assert not spec.BAR_TAP_SPEC.kind.startswith("counterbore")


def test_both_patterns_fit_their_mates_at_three_places() -> None:
    # Each station's ±0.13 mm about the row's ±.005.
    band_mm = printed_band_mm(spec.HOLE_PLACES, unit="mm")
    row_band = printed_band_mm(spec.ROW_PLACES, unit="in")
    assert spec.POSITION_RADIUS >= math.hypot(band_mm, row_band)
    assert spec.POSITION_RADIUS == pytest.approx(0.182, abs=1e-3)
    # The uxcell block's listed Ø5 holes (UNVERIFIED, #2184) about the #8's
    # 4.166 major.
    assert spec.KP08_SCREW_FLOAT == pytest.approx(0.417, abs=1e-3)
    assert spec.KP08_PATTERN_ALLOWANCE > 0.0
    # TL-20's #12 (.189) clearance: each two-screw joint slides and turns, so
    # half the worst spacing difference must sit inside the least float.
    assert spec.BAR_HOLE_DIA == pytest.approx(4.801)
    assert spec.BAR_SCREW_FLOAT == pytest.approx(0.3175, abs=1e-4)
    assert spec.BAR_PAIR_MISFIT == pytest.approx(0.261, abs=1e-3)
    assert spec.BAR_PATTERN_ALLOWANCE == pytest.approx(
        spec.BAR_SCREW_FLOAT - spec.BAR_PAIR_MISFIT
    )
    assert spec.BAR_PATTERN_ALLOWANCE > 0.05
    stations = {*drawing.STATION_ORDER, "HoleRowY"}
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 3 for name in stations)
    # At the title block's two places this part's and TL-20's position
    # radii together would overrun the #8's float.
    two = printed_band_mm(2, unit="in")
    assert 2.0 * math.hypot(two, two) > spec.BAR_SCREW_FLOAT


def test_every_tight_band_names_its_mate() -> None:
    for name in ("KP08Tap1X", "KP08Tap2X", "HoleRowY"):
        assert spec.CALLOUTS_BELOW[name] == spec.MATE_CALLOUT == spec.ROW_CALLOUT
    assert spec.MATE_CALLOUT == "KP08 + MHA-CH-06-TL-20"
    # Every three-place dimension on the sheet carries its mate.
    three_place = {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 3
    }
    assert three_place <= set(spec.CALLOUTS_BELOW)
    for name, feature in _features().items():
        if name.startswith("tap_"):
            assert feature["note"].startswith(f"{spec.MATE_CALLOUT}; "), name


def test_no_vendor_sku_on_the_sheet() -> None:
    texts = (
        spec.MATE_CALLOUT,
        spec.ROW_CALLOUT,
        spec.CALLOUTS_BELOW[spec.BAR_THREAD_DEPTH_DIMENSION],
        drawing.BOTTOM_THREAD_CALLOUT,
        spec.DRAWING_NOTES,
        spec.ISOMETRIC_VIEW_NOTE,
    )
    for text in texts:
        assert not re.search(r"\b\d{4,}[A-Z]\d+\b", text), text  # McMaster style
        assert "AMPEC" not in text.upper()
        assert "RULING" not in text.upper() and "OWNER" not in text.upper()


def test_walls_hold_rule_17_at_worst_case() -> None:
    walls = spec.WALLS_MM
    assert spec.WALL_TARGET == WALL_TARGET_MM
    assert min(walls.values()) >= spec.WALL_TARGET
    # Each hole to its end, the two holes to each other, the row to both sides.
    holes = [name for name in walls if name.startswith("hole")]
    assert len(holes) == len(spec.HOLE_X) + 1
    assert {"row to -Y side", "row to +Y side"} <= set(walls)
    assert spec.RULE_20_SHORTFALLS == ()
    # Cross-check from the exported bands: each thread's major at its station
    # band's far end.
    features = _features()
    tap_1, tap_2 = features["tap_1"], features["tap_2"]
    r = THREAD_MAJOR_MM[spec.SCREW] / 2.0
    assert tap_1["station"][0] - r >= WALL_TARGET_MM
    assert tap_2["station"][0] - tap_1["station"][1] - 2.0 * r >= WALL_TARGET_MM
    assert tap_1["height"][0] - r >= WALL_TARGET_MM


def test_two_face_threads_hold_each_screw_and_keep_the_tips_apart() -> None:
    # Owner ruling Main 2026-11-06 (option B): a #8-32 x 3/4 SHCS up from the
    # bar, a #8-32 x 5/8 SHCS down from the KP08, each in at least 1.5 D of
    # full thread at the worst case, the tips never meeting.
    pitch = 25.4 / 32.0
    assert spec.TAP_LEAD == pytest.approx(2.0 * pitch)
    assert spec.THICK_MIN == pytest.approx(25.4 - 0.3048)
    assert spec.BAR_REACH_MAX == pytest.approx(leadscrew.BAR_SCREW_ENGAGEMENT_RANGE[1])
    assert spec.BAR_REACH_MAX == pytest.approx(12.294, abs=1e-3)
    # PR2229 review r1 (P2): the KP08 screw reaches deepest on the least foot
    # the receipt check accepts, so every window is taken there, not on the
    # UNVERIFIED nominal 5.0 (#2184).
    assert spec.KP08_SCREW_LENGTH_MM == pytest.approx(15.875)
    assert spec.KP08_REACH_MAX == pytest.approx(
        spec.KP08_SCREW_LENGTH_MM - spec.KP08_FOOT_THICK_MIN
    )
    assert spec.KP08_REACH_MAX > leadscrew.KP08_SCREW_REACH
    assert spec.SCREW_REACH_MAX == {"bar": spec.BAR_REACH_MAX, "kp08": spec.KP08_REACH_MAX}
    # Each printed depth's limits sit inside its window: the own screw's
    # reach in full thread, the other screw's reach clear of thread and lead.
    assert spec.BAR_THREAD_DEPTH == pytest.approx(0.491 * 25.4)
    assert spec.KP08_THREAD_DEPTH == pytest.approx(0.436 * 25.4)
    for (low, high), (lo, hi) in (
        (spec.BAR_THREAD_LIMITS, spec.BAR_THREAD_WINDOW),
        (spec.KP08_THREAD_LIMITS, spec.KP08_THREAD_WINDOW),
    ):
        assert lo <= low <= high <= hi
        assert low >= 1.5 * THREAD_MAJOR_MM[spec.SCREW]
    assert spec.BAR_THREAD_WINDOW[1] == pytest.approx(
        spec.THICK_MIN - spec.KP08_REACH_MAX - spec.TAP_LEAD
    )
    assert spec.KP08_THREAD_WINDOW[1] == pytest.approx(
        spec.THICK_MIN - spec.BAR_REACH_MAX - spec.TAP_LEAD
    )
    # The tips' worst-case gap; the common 3/4 from the top would collide.
    assert spec.SCREW_TIP_GAP_MIN == pytest.approx(
        spec.THICK_MIN - spec.BAR_REACH_MAX - spec.KP08_REACH_MAX
    )
    assert spec.SCREW_TIP_GAP_MIN > 1.9
    assert spec.COMMON_SCREW_TIP_GAP < 0.0
    taps = {name: f for name, f in _features().items() if name.startswith("tap_")}
    assert len(taps) == 2 and all(f["thru"] is True for f in taps.values())
    # prechips' Feature schema has no per-face thread-depth field: both
    # bounded windows ride the tap's cited note (the carrier precedent).
    from prechips.model import Feature

    for feature in taps.values():
        assert not {"thread_depth_top", "thread_depth_bottom"} & set(feature)
        assert not {"thread_depth_top", "thread_depth_bottom"} & set(
            feature["precision"]
        )
        assert "note" in feature["requirements"]
        for low, high in (spec.KP08_THREAD_LIMITS, spec.BAR_THREAD_LIMITS):
            assert f"{low:.3f} TO {high:.3f} mm" in feature["note"]
        # extra="forbid": every exported key is a Feature field (faces are
        # bound to STEP names only at write_manifest, so not validated here).
        assert set(feature) <= set(Feature.model_fields), set(feature) - set(
            Feature.model_fields
        )
    # The bar-face wizard first (blind, from the bottom), then the KP08-face
    # wizard THRU ALL from the top, its thread depth set from that face.
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert len(
        re.findall(r'_thread_from_face\(\s*adapter, "KP08Taps", KP08_THREAD_DEPTH', builder)
    ) == 1
    assert builder.index('"BarTaps"') < builder.index('"KP08Taps"')
    # The fastener table's receiving threads.
    assert fasteners.BRACKET_TO_BAR.thread_depth_mm == spec.BAR_THREAD_DEPTH
    assert fasteners.KP08_TO_BRACKET.thread_depth_mm == spec.KP08_THREAD_DEPTH
    assert fasteners.BRACKET_TO_BAR.protrusion_mm < 0.0
    assert fasteners.KP08_TO_BRACKET.protrusion_mm < 0.0
    assert fasteners.KP08_TO_BRACKET.engagement_mm == pytest.approx(
        leadscrew.KP08_SCREW_REACH
    )


def test_least_kp08_foot_is_set_by_both_threads_and_rounded_up() -> None:
    # PR2229 review r1 (P2): at the least foot the KP08 screw's tip must stop
    # in the top thread's full thread AND short of the bottom thread's
    # deepest partial thread (its deepest full depth plus the tap's lead) on
    # the thinnest stock. The printed .001 floor is rounded UP from the
    # tighter of the two.
    reach_allowed = min(
        spec.KP08_THREAD_LIMITS[0],
        spec.THICK_MIN - spec.BAR_THREAD_LIMITS[1] - spec.TAP_LEAD,
    )
    exact = spec.KP08_SCREW_LENGTH_MM - reach_allowed
    printed = math.ceil(exact / 25.4 * 1000.0 - 1e-9) / 1000.0
    assert spec.KP08_FOOT_THICK_MIN == pytest.approx(printed * 25.4)
    assert spec.KP08_FOOT_THICK_MIN >= exact
    assert spec.KP08_FOOT_THICK_MIN - exact < 0.0254
    # On the 1 in stock's thinnest, the bottom tap's lead is the tighter
    # bound (the top thread's least depth alone allowed .194).
    assert spec.THICK_MIN - spec.BAR_THREAD_LIMITS[1] - spec.TAP_LEAD < (
        spec.KP08_THREAD_LIMITS[0]
    )
    assert round(spec.KP08_FOOT_THICK_MIN / 25.4, 3) == 0.196
    assert spec.KP08_FOOT_THICK_MIN < leadscrew.KP08_FOOT_THICK
    # At the least foot the tip clears both bounds.
    assert spec.KP08_REACH_MAX <= spec.KP08_THREAD_LIMITS[0]
    assert spec.KP08_REACH_MAX + spec.BAR_THREAD_LIMITS[1] + spec.TAP_LEAD <= (
        spec.THICK_MIN
    )


def test_thickest_kp08_foot_keeps_the_kp08_screw_at_one_and_a_half_d() -> None:
    # Coordinator gate (post-cap #2237): the receipt check took any foot over
    # .196. A thicker foot takes the 5/8's engagement off one for one, so the
    # same check's upper bound is the foot at which its worst-case full thread
    # is still 1.5 D, rounded DOWN to .001. #2184: the foot stays UNVERIFIED.
    major = THREAD_MAJOR_MM[spec.SCREW]
    exact = (
        leadscrew.full_thread_min(leadscrew.KP08_SCREW_LENGTH, 0.0, spec.SCREW)
        - 1.5 * major
    )
    printed = math.floor(exact / 25.4 * 1000.0 + 1e-9) / 1000.0
    assert spec.KP08_FOOT_THICK_MAX == pytest.approx(printed * 25.4)
    assert round(spec.KP08_FOOT_THICK_MAX / 25.4, 3) == 0.292
    assert spec.KP08_FOOT_THICK_MAX <= exact
    full = leadscrew.full_thread_min(
        leadscrew.KP08_SCREW_LENGTH, spec.KP08_FOOT_THICK_MAX, spec.SCREW
    )
    assert full >= 1.5 * major
    assert (
        spec.KP08_FOOT_THICK_MIN
        < leadscrew.KP08_FOOT_THICK
        < spec.KP08_FOOT_THICK_MAX
    )
    # A thicker foot only shortens the 5/8's reach: the windows, taken on the
    # least foot, still hold.
    assert spec.KP08_SCREW_LENGTH_MM - spec.KP08_FOOT_THICK_MAX < spec.KP08_REACH_MAX


def test_three_place_depths_are_set_by_the_opposed_screws() -> None:
    # Machinist review 0c3ed35988 read .436/.491 as unexplained three places.
    # Each window runs from its own screw's deepest reach (full thread) to
    # the other face's thread and tap lead short of the other screw: the tip
    # gap less one lead, .0125 wide. A .XX band spans .020, so no two-place
    # depth fits; the central untapped band staying positive is not the test.
    width = spec.SCREW_TIP_GAP_MIN - spec.TAP_LEAD
    assert spec.DEPTH_WINDOW_WIDTH == pytest.approx(width)
    assert width == pytest.approx(0.317, abs=1e-3)
    for lo, hi in (spec.BAR_THREAD_WINDOW, spec.KP08_THREAD_WINDOW):
        assert hi - lo == pytest.approx(width)
    two = sum(abs(d) for d in printed_deviations(spec.BAR_THREAD_DEPTH, 2, unit=spec.UNIT))
    three = sum(
        abs(d) for d in printed_deviations(spec.BAR_THREAD_DEPTH, 3, unit=spec.UNIT)
    )
    assert two == pytest.approx(0.508) and three == pytest.approx(0.254)
    assert three <= width < two
    # The counterfactual roundings: .49 ±.01 and .44 ±.01 each leave their
    # window (the bar's both ways, the KP08's past the bar screw's reach).
    bar_low, bar_high = spec._limits(spec.BAR_THREAD_DEPTH, 2)
    kp08_low, kp08_high = spec._limits(spec.KP08_THREAD_DEPTH, 2)
    assert bar_low < spec.BAR_THREAD_WINDOW[0]
    assert bar_high > spec.BAR_THREAD_WINDOW[1]
    assert kp08_high > spec.KP08_THREAD_WINDOW[1]
    # The sheet names that function beside the depth, in plain words.
    text = spec.CALLOUTS_BELOW[spec.BAR_THREAD_DEPTH_DIMENSION]
    assert text.split("\n") == [
        "FULL THREAD FROM BOTTOM",
        "BOTH HOLES",
        "EACH SCREW TIP IN FULL",
        "THREAD, SHORT OF THE",
        "OTHER FACE'S TAP LEAD",
    ]


def test_section_draws_both_threads_solid_with_the_witness_on_the_thread() -> None:
    # Machinist review 0c3ed35988: A-A drew only the top thread, dashed, and
    # the .491's witness started in the plain bore. Both faces' threads on
    # both holes are imported and moved to a thin continuous layer; the
    # depth's reference points stand on the outer hole's major diameter.
    assert drawing.SECTION_THREAD_INSTANCES == 2 * len(spec.HOLE_X) == 4
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    body = sheet[sheet.index("async def build") :]
    assert body.index("_require_bar_thread_depth(section)") < body.index(
        "_section_threads_on_visible_layer(adapter, section)"
    )
    assert body.index("_section_threads_on_visible_layer(adapter, section)") < body.index(
        "finalize_drawing("
    )
    assert spec.THREAD_MAJOR == THREAD_MAJOR_MM[spec.SCREW]
    assert spec.BAR_THREAD_WITNESS_X == pytest.approx(
        spec.HOLE_X[-1] + THREAD_MAJOR_MM[spec.SCREW] / 2.0
    )
    # On the outer-end side, where the depth's text stands.
    assert spec.HOLE_X[-1] < spec.BAR_THREAD_WITNESS_X < spec.BRACKET_LENGTH
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert '("ThreadMajor", THREAD_MAJOR)' in builder
    assert (
        'thread_ref.record("BarThreadStation", f\'"HoleX{len(HOLE_X)}" + '
        '"ThreadMajor" / 2\')'
    ) in builder
    assert "_add_point(adapter, (witness_x, -BAR_THREAD_DEPTH)" in builder


def test_each_face_is_plug_started_bottoming_finished_with_a_bounded_tap_point() -> None:
    # PR2229 review r1 (P2): the geometry budgets two pitches of tap lead,
    # a bottoming tap's; a plug tap's 3-5 chamfered threads would cut past
    # it. Each face finishes with the bottoming tap, and neither tap's point
    # goes past its face's mark: the thread's deepest full depth plus the
    # bottoming tap's lead, rounded down to .001.
    for (_low, high), tip, other_reach in (
        (spec.BAR_THREAD_LIMITS, spec.BAR_TAP_TIP_MAX, spec.KP08_REACH_MAX),
        (spec.KP08_THREAD_LIMITS, spec.KP08_TAP_TIP_MAX, spec.BAR_REACH_MAX),
    ):
        assert _on_grid(tip, 3)
        assert high + spec.TAP_LEAD - 0.0254 < tip <= high + spec.TAP_LEAD
        assert tip <= spec.THICK_MIN - other_reach
    assert round(spec.BAR_TAP_TIP_MAX / 25.4, 3) == 0.558
    assert round(spec.KP08_TAP_TIP_MAX / 25.4, 3) == 0.503
    # The process names both taps, the bottoming tap finishing, and each
    # face's printed window and tap-point mark (spec values, not prose).
    process = _config.parts(ARTIFACT)["process"]
    assert "plug" in process and "bottoming" in process
    assert "min full thread" not in process
    for depth, tip in (
        (spec.BAR_THREAD_DEPTH, spec.BAR_TAP_TIP_MAX),
        (spec.KP08_THREAD_DEPTH, spec.KP08_TAP_TIP_MAX),
    ):
        assert f"{depth / 25.4:.3f}".lstrip("0") + " ±.005" in process
        assert f"{tip / 25.4:.3f}".lstrip("0") in process


def test_holes_carry_the_title_block_band_except_the_kp08_stations() -> None:
    # Only the KP08 stations carry a model band: millimetres on the inch
    # sheet, which the inch title block's rows do not cover (owner ruling 4).
    # (The loop over METRIC_DIMENSIONS reports its source names.)
    assert model_toleranced_dimensions(part) == {
        ("feature_name", "dimension_name"): "band"
    }
    holes = _features()
    band = printed_band_mm(spec.ROW_PLACES, unit="in")
    for name in ("tap_1", "tap_2"):
        # The tap drill prints .XXX with the title block's drilled-hole band.
        low, high = holes[name]["dia"]
        assert low == pytest.approx(round(spec.TAP_DRILL / 25.4, 3) * 25.4)
        assert high - low == pytest.approx(spec.DRILLED_BAND[0])
        low, high = holes[name]["station"]
        assert high - low == pytest.approx(2.0 * spec.HOLE_BAND)
        assert holes[name]["height"] == pytest.approx(
            [spec.HOLE_ROW_Y - band, spec.HOLE_ROW_Y + band]
        )
        assert holes[name]["height_from"] == "bracket_low_side"


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.PLAN_KEEP, drawing.END_KEEP, drawing.SECTION_KEEP)
    assert set().union(*keeps) == marked
    assert sum(len(keep) for keep in keeps) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) <= marked


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    stock = {("bar_seat", "thickness"), ("bar_seat", "width")}
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
            checked += 1
            if (name, requirement) in stock:
                continue  # the supplier's band about the stock size
            places = feature["precision"][requirement]
            metric = name.startswith("tap_") and requirement == "station"
            for end in band:
                if metric:  # exact millimetres (owner ruling 4)
                    assert end == pytest.approx(round(end, places), abs=1e-9), name
                else:
                    assert _on_grid(end, places), (name, requirement)
    assert checked


def test_row_is_located_from_the_faced_low_side() -> None:
    assert spec.HOLE_ROW_Y == pytest.approx(6.35)
    assert spec.DRAWING_DIMENSIONS["HoleRowReference"] == {"HoleRowY"}
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert 'row_station.record("HoleRowY", \'"BracketWidth" / 2\')' in build
    assert build.index('blank_sketch(adapter, "HoleRowReference")') < build.index(
        "save_part_and_images(adapter, PART_NAME)"
    )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in sheet
    assert drawing._FROM_LOW_SIDE[0] == "bracket_low_side"


def test_every_hole_has_its_own_callout() -> None:
    called = sorted(x for x, _xy, _side in drawing.TAP_CALLOUTS)
    assert called == sorted(spec.HOLE_X)
    assert drawing.CALLOUT_ROWS == 3
    assert drawing.CALLOUT_GLYPHS == len(drawing.BOTTOM_THREAD_CALLOUT)


def test_single_hole_definitions_drop_exactly_the_count() -> None:
    definitions = {
        5: "<hw-thread> UNC - <hw-threadclass> <HOLE-DEPTH><hw-threaddepth>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-tapdrldia> THRU ALL",
        8: "",
    }
    updated = drawing.single_hole_definitions(definitions)
    assert updated == {**definitions, 7: "<MOD-DIAM><hw-tapdrldia> THRU ALL"}
    with pytest.raises(RuntimeError):
        drawing.single_hole_definitions(updated)  # no count left to drop
    with pytest.raises(RuntimeError):
        drawing.single_hole_definitions({**definitions, 5: "<NUM_INST>X THRU"})
    with pytest.raises(RuntimeError):
        drawing.single_hole_definitions({5: "", 6: "", 7: ""})
    assert drawing._PRINTED_COUNT.search("x\n2X Ø3.45 THRU ALL")
    assert not drawing._PRINTED_COUNT.search("Ø3.45 THRU ALL\n8-32 UNC THRU ALL")


def test_thread_depth_definitions_put_the_section_pointer_on_its_own_row() -> None:
    definitions = {
        5: "<hw-thread> UNC - <hw-threadclass> <HOLE-DEPTH><hw-threaddepth>",
        6: "",
        7: "<MOD-DIAM><hw-tapdrldia> THRU ALL",
        8: "",
    }
    callout = drawing.BOTTOM_THREAD_CALLOUT
    updated = drawing.thread_depth_definitions(definitions, callout)
    assert updated == {
        **definitions,
        5: f"{definitions[5]}\n{callout}",
    }
    with pytest.raises(RuntimeError):
        drawing.thread_depth_definitions(
            {**definitions, 5: "<hw-thread> THRU ALL"}, callout
        )
    with pytest.raises(RuntimeError):
        drawing.thread_depth_definitions(
            {**definitions, 6: "<hw-threaddepth>"}, callout
        )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "thread_callout=BOTTOM_THREAD_CALLOUT" in sheet


def test_bottom_thread_depth_prints_from_its_own_native_dimension() -> None:
    # PR2229 review r1 (P2): the bottom thread's depth prints through a
    # source-owned native dimension, never a typed spec string. The pointer
    # row on the plan callout carries no number; section A-A's one dimension
    # is BarThreadDepth@BarThreadReference, proved equal to BarTaps' thread.
    assert not hasattr(spec, "FAR_SIDE_THREAD_CALLOUT")
    assert not re.search(r"\d", drawing.BOTTOM_THREAD_CALLOUT)
    label = drawing.SECTION_LABEL
    assert f"SECTION {label}-{label}" in drawing.BOTTOM_THREAD_CALLOUT
    assert spec.DRAWING_DIMENSIONS[spec.BAR_THREAD_REFERENCE] == {
        spec.BAR_THREAD_DEPTH_DIMENSION
    }
    assert spec.DRAWING_PRECISION_BY_NAME[spec.BAR_THREAD_DEPTH_DIMENSION] == 3
    assert set(drawing.SECTION_KEEP) == {spec.BAR_THREAD_DEPTH_DIMENSION}
    assert not re.search(r"\d", spec.CALLOUTS_BELOW[spec.BAR_THREAD_DEPTH_DIMENSION])
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert 'create_sketch("Top")' in builder
    assert "thread_ref.record(BAR_THREAD_DEPTH_DIMENSION, '\"BarThreadDepth\"')" in builder
    assert '("BarThreadDepth", BAR_THREAD_DEPTH)' in builder
    assert builder.index("_require_bar_thread_reference(adapter)") < builder.index(
        "save_part_and_images(adapter, PART_NAME)"
    )
    assert builder.index("blank_sketch(adapter, BAR_THREAD_REFERENCE)") < builder.index(
        "save_part_and_images(adapter, PART_NAME)"
    )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "BAR_THREAD_DEPTH / 25.4" not in sheet
    assert "FAR SIDE" not in sheet
    assert sheet.index("_section(adapter, end)") < sheet.index(
        "_require_bar_thread_depth(section)"
    )
    assert sheet.index("_require_bar_thread_depth(section)") < sheet.index(
        "assert_imported_precision(adapter, annotations"
    )


# --- Sheet layout (model mm in the plan, sheet m around it) -----------------------


def _plan(name: str) -> tuple[float, float]:
    x, y, _z = drawing.PLAN_KEEP[name]
    return x, y


_STATION_MATES = {"KP08Tap1X": spec.MATE_CALLOUT, "KP08Tap2X": spec.MATE_CALLOUT}
_STATION_X = {"KP08Tap1X": spec.HOLE_X[0], "KP08Tap2X": spec.HOLE_X[1]}


def _block(name: str) -> tuple[float, float, float, float]:
    """A text block's (left, right, bottom, top), model mm: a station's value
    over its mate (the mate the wider line), the length one line."""
    x, y = _plan(name)
    if name == "BracketLength":
        half, half_high = drawing.text_half("2.71"), drawing.text_half_high(1)
    else:
        half, half_high = (
            drawing.text_half(_STATION_MATES[name]),
            drawing.text_half_high(2),
        )
    return x - half, x + half, y - half_high, y + half_high


def _lane(name: str) -> float:
    if name == "BracketLength":
        return drawing.LENGTH_LANE
    return drawing.STATION_LANES[drawing.STATION_ORDER.index(name)]


def test_station_stacks_run_shortest_nearest_in_clear_lanes() -> None:
    order = list(drawing.STATION_ORDER)
    assert order == sorted(_STATION_X, key=_STATION_X.get)
    assert set(order) == set(_STATION_MATES)
    lanes = [_lane(n) for n in (*order, "BracketLength")]
    assert lanes == sorted(lanes, reverse=True)
    for name in order:
        assert _plan(name)[1] == pytest.approx(_lane(name) + drawing.TWO_LINE_DROP)
    assert _plan("BracketLength")[1] == pytest.approx(
        drawing.LENGTH_LANE + drawing.TEXT_DROP
    )
    # The first block clears the row's dimension line tail under the plan.
    assert _block(order[0])[3] <= -spec.HALF_WIDTH - drawing.ROW_TAIL - (
        drawing.TEXT_GAP - 1e-9
    )


def _extension_lines() -> list[tuple[float, float, float]]:
    """Every vertical extension line under the plan: (x, y_low, y_high), run
    from its feature (a tap from its centre) to its dimension line plus the
    overshoot."""
    over = drawing.EXT_OVERSHOOT
    bottom = -spec.HALF_WIDTH
    lines = [
        (0.0, drawing.LENGTH_LANE - over, bottom),
        (spec.BRACKET_LENGTH, drawing.LENGTH_LANE - over, bottom),
    ]
    lines += [(_STATION_X[n], _lane(n) - over, 0.0) for n in drawing.STATION_ORDER]
    return lines


def _dimension_lines() -> dict[str, tuple[float, float, float]]:
    """Each dimension line (x0, x1, y), run out under its text left of X 0."""
    lines = {
        name: (min(0.0, _block(name)[0]), _STATION_X[name], _lane(name))
        for name in drawing.STATION_ORDER
    }
    lines["BracketLength"] = (0.0, spec.BRACKET_LENGTH, drawing.LENGTH_LANE)
    return lines


def test_station_blocks_cross_no_extension_or_dimension_line() -> None:
    gap = drawing.TEXT_GAP - 1e-9
    names = [*drawing.STATION_ORDER, "BracketLength"]
    for name in names:
        left, right, bottom, top = _block(name)
        for x, y0, y1 in _extension_lines():
            if y0 < top + gap and bottom - gap < y1:
                assert x <= left - gap or x >= right + gap, (name, x)
        for other, (x0, x1, y) in _dimension_lines().items():
            if other != name and x0 < right and left < x1:
                assert y <= bottom - gap or y >= top + gap, (name, other)
        assert top <= -spec.HALF_WIDTH - 1.0, name
    # Every station text stands left of the inner end, inside the border.
    for name in drawing.STATION_ORDER:
        assert _block(name)[1] == pytest.approx(-drawing.TEXT_GAP)
        left, _ = drawing.plan_sheet(_block(name)[0], 0.0)
        assert left >= LEFT_BORDER + 0.01
    # The blocks clear one another.
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            l1, r1, b1, t1 = _block(first)
            l2, r2, b2, t2 = _block(second)
            assert r1 <= l2 or r2 <= l1 or t1 <= b2 or t2 <= b1, (first, second)


def test_row_block_sits_between_its_extension_lines_off_the_part() -> None:
    x, y = _plan("HoleRowY")
    rows = drawing._ROW_ROWS
    assert rows == 2
    half_high = drawing.text_half_high(rows)
    assert y - half_high >= -spec.HOLE_ROW_Y + 0.25
    assert y + half_high <= -0.25
    half = drawing.text_half(drawing._ROW_TEXT)
    assert x + half <= -drawing.SIDE_LANE
    left, _ = drawing.plan_sheet(x - half, y)
    assert left >= LEFT_BORDER + 0.01


def _callout_block(xy: tuple[float, float]) -> tuple[float, ...]:
    half = drawing.CALLOUT_GLYPHS * drawing.GLYPH / 2.0
    half_high = drawing.text_half_high(drawing.CALLOUT_ROWS)
    return xy[0] - half, xy[0] + half, xy[1] - half_high, xy[1] + half_high


def _leader(x: float, xy: tuple[float, float]) -> tuple[tuple[float, float], ...]:
    """Shelf end nearer the hole (the bottom row's baseline) to its centre."""
    left, right, bottom, _top = _callout_block(xy)
    near = left if abs(left - x) < abs(right - x) else right
    return (near, bottom), (x, 0.0)


def _cross(p, q, r, s) -> bool:
    """Whether segments pq and rs properly intersect."""

    def orient(a, b, c) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return (orient(p, q, r) * orient(p, q, s) < 0) and (
        orient(r, s, p) * orient(r, s, q) < 0
    )


def _box_edges(box: tuple[float, ...]) -> list[tuple[tuple[float, float], ...]]:
    left, right, bottom, top = box
    corners = [(left, bottom), (right, bottom), (right, top), (left, top)]
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


def test_each_leader_lands_on_its_own_hole_crossing_nothing() -> None:
    callouts = drawing.TAP_CALLOUTS
    leaders = [_leader(x, xy) for x, xy, _side in callouts]
    blocks = [_callout_block(xy) for _x, xy, _side in callouts]
    holes = [(x, spec.TAP_DRILL / 2.0) for x, _xy, _side in callouts]
    width_ext = (
        (spec.BRACKET_LENGTH + 0.5, spec.HALF_WIDTH),
        (
            spec.BRACKET_LENGTH + drawing.SIDE_LANE + drawing.EXT_OVERSHOOT,
            spec.HALF_WIDTH,
        ),
    )
    for i, ((x, xy, side), leader) in enumerate(zip(callouts, leaders, strict=True)):
        (sx, sy), _centre = leader
        # The edge pick is the rim on the leader's side, off the centre lines.
        ex, ey, _ez = drawing.tap_edge_model(x, side)
        assert math.hypot(ex - x, ey) == pytest.approx(spec.TAP_DRILL / 2.0)
        assert (sx - x) * side > 0 and ey > 0
        assert not _cross(*leader, *width_ext), i
        for j, other in enumerate(leaders):
            if j != i:
                assert not _cross(*leader, *other), (i, j)
        for j, box in enumerate(blocks):
            if j != i:
                assert not any(_cross(*leader, *edge) for edge in _box_edges(box)), (
                    i,
                    j,
                )
        # No other hole under the leader.
        for j, (hx, radius) in enumerate(holes):
            if j != i:
                (ax, ay), (bx, by) = leader
                t = max(
                    0.0,
                    min(
                        1.0,
                        ((hx - ax) * (bx - ax) + (0 - ay) * (by - ay))
                        / ((bx - ax) ** 2 + (by - ay) ** 2),
                    ),
                )
                gap = math.hypot(ax + t * (bx - ax) - hx, ay + t * (by - ay))
                assert gap >= radius + 1.0, (i, j)


def test_tap_callouts_stand_over_the_plan_inside_the_sheet() -> None:
    gap = drawing.TEXT_GAP - 1e-9
    blocks = [_callout_block(xy) for _x, xy, _side in drawing.TAP_CALLOUTS]
    end_top = drawing.END_CENTER[1] + spec.HALF_WIDTH * drawing._S / 1000.0
    end_left = drawing.END_CENTER[0] - spec.BRACKET_THICK / 2.0 * drawing._S / 1000.0
    for i, box in enumerate(blocks):
        left, right, bottom, top = box
        assert bottom >= spec.HALF_WIDTH + 1.0, i
        (sheet_left, sheet_bottom), (sheet_right, sheet_top) = (
            drawing.plan_sheet(left, bottom),
            drawing.plan_sheet(right, top),
        )
        assert sheet_left >= LEFT_BORDER + 0.01, i
        assert sheet_top <= TOP_BORDER - 0.01, i
        if sheet_right > end_left - 0.01:  # over the end view
            assert sheet_bottom >= end_top + 0.01, i
        assert sheet_right <= drawing.ISO_CENTER[0] - drawing.ISO_HALF[0] - 0.01, i
        for other in blocks[i + 1 :]:
            l2, r2, b2, t2 = other
            if right + gap <= l2 or r2 + gap <= left:
                continue
            # Stacked blocks stand the layout audit's row pitch apart (c4-r8:
            # 2.82 sheet mm, and it merged each side's three into one).
            pitch = drawing.STACK_PITCH
            assert top + pitch <= b2 or t2 + pitch <= bottom, i


def test_views_clear_each_other_the_border_and_the_title_block() -> None:
    s = drawing._S / 1000.0
    width_text_right, _ = drawing.plan_sheet(
        _plan("BracketWidth")[0] + drawing.text_half("(1/2 in)\nSTOCK"), 0.0
    )
    end_left = drawing.END_CENTER[0] - spec.BRACKET_THICK / 2.0 * s
    end_right = drawing.END_CENTER[0] + spec.BRACKET_THICK / 2.0 * s
    assert width_text_right + 0.01 <= end_left
    assert drawing.END_CENTER[1] == drawing.PLAN_CENTER[1]
    iso_x, iso_y = drawing.ISO_CENTER
    half_x, half_y = drawing.ISO_HALF
    assert end_right + 0.02 <= iso_x - half_x
    assert iso_x + half_x <= RIGHT_BORDER - 0.01
    assert iso_y + half_y <= TOP_BORDER - 0.01
    note_x, note_y = drawing.ISO_NOTE_XY
    assert note_y <= iso_y - half_y - 0.003
    assert note_y - 0.0042 >= TITLE_BLOCK_TOP + 0.01
    assert iso_x - half_x <= note_x <= iso_x
    # The lowest plan line (the length's, under six station lanes since
    # ruling A′; 25 above under four) stays well above the title block: 21.7
    # once c4-r8's tiers set the plan's height (the top tier 10 under the
    # border).
    _, length_line = drawing.plan_sheet(
        0.0, drawing.LENGTH_LANE - drawing.EXT_OVERSHOOT
    )
    assert length_line >= TITLE_BLOCK_TOP + 0.020
    plan_right, _ = drawing.plan_sheet(spec.BRACKET_LENGTH, 0.0)
    assert plan_right > TITLE_BLOCK_LEFT  # so the plan must stay above it
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'place_view(adapter, str(SOURCE), "*Right", *END_CENTER' in sheet
    assert "for view in (plan, end, iso):" in sheet


def test_section_stands_under_the_plan_above_the_title_block() -> None:
    s = drawing._S / 1000.0
    centre_x, centre_y = drawing.SECTION_CENTER
    top = centre_y + spec.BRACKET_THICK / 2.0 * s
    foot = centre_y - spec.BRACKET_THICK / 2.0 * s
    _, plan_lowest = drawing.plan_sheet(
        0.0,
        drawing.LENGTH_LANE + drawing.TEXT_DROP - drawing.text_half_high(1),
    )
    assert top + 0.008 <= plan_lowest
    assert foot >= TITLE_BLOCK_TOP + 0.010
    # The depth's text a TEXT_GAP off the outer end, wholly off the part and
    # inside the border whichever way +X reads in the cut.
    x, y, z = drawing.SECTION_KEEP[spec.BAR_THREAD_DEPTH_DIMENSION]
    half = drawing.text_half(spec.CALLOUTS_BELOW[spec.BAR_THREAD_DEPTH_DIMENSION])
    assert x - half >= spec.BRACKET_LENGTH + drawing.TEXT_GAP - 1e-9
    assert y == 0.0 and z == pytest.approx(spec.BAR_THREAD_DEPTH / 2.0)
    reach = (x + half - spec.BRACKET_LENGTH / 2.0) * s
    assert centre_x + reach <= RIGHT_BORDER - 0.01
    assert centre_x - reach >= LEFT_BORDER + 0.01
    rows = 1 + spec.CALLOUTS_BELOW[spec.BAR_THREAD_DEPTH_DIMENSION].count("\n") + 1
    assert (z - drawing.text_half_high(rows)) * s + foot >= TITLE_BLOCK_TOP + 0.010
    # The caption under the section, left of the title block.
    caption_x, caption_y = drawing.SECTION_CAPTION_XY
    assert caption_y < foot and caption_x < TITLE_BLOCK_LEFT - 0.02
    # The cutting line crosses the end view top to bottom, past both faces.
    (_x0, y0, z0), (_x1, y1, z1) = drawing.SECTION_LINE_MODEL_MM
    assert y0 == y1 == 0.0
    assert z0 < 0.0 and z1 > spec.BRACKET_THICK


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    row = _config.parts(ARTIFACT)
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", row["number"])
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-28"
    assert row["quantity"] == spec.QUANTITY == 2
    assert part.PART_NAME == ARTIFACT == leadscrew.END_BRACKET


def test_material_names_the_aluminium_flat_bar_family() -> None:
    # Machinist review ENFORCE (rule 2): only the taps need the metal, so the
    # title block names the family; the spec row keeps 6061-T6 as an example.
    row = _config.parts(ARTIFACT)
    assert row["material"].startswith("ALUMINUM FLAT BAR")
    assert "6061" not in row["material"]
    assert "6061-T6" in row["material_specification"]


def test_places_are_model_authored_and_the_sheet_is_pure() -> None:
    script = Path(drawing.__file__)
    assert script.name in _drawing_contract.PRECISION_MIGRATED_DRAWINGS
    assert not _drawing_contract.drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


def test_sheet_carries_no_notes() -> None:
    assert spec.DRAWING_NOTES == ""
    assert spec.SURFACE_FINISHES == ()
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in source


def test_prechips_solids_are_valid_fixture_solids() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    names = {solid["name"] for solid in spec.PRECHIPS_SOLIDS}
    assert names == {"end bracket", "tap 1", "tap 2"}
    box = spec.PRECHIPS_SOLIDS[0]
    assert box["size_mm"] == pytest.approx(
        [spec.BRACKET_LENGTH, spec.BRACKET_WIDTH, spec.BRACKET_THICK]
    )

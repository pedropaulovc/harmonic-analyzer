"""Offline contracts for the oblique-trammel jig's end bracket (MHA-CH-06-TL-28)."""

from __future__ import annotations

import math
import re
import tomllib
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
from _paths import CAD_ROOT
from _printed_tolerance import printed_band_mm

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
    # 42 mm pitch, X 13.925 and 55.925; Main's R4 ruling: each tapped #8-32
    # THRU from the top face.
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
        ("Taps", "Tap1X"): (3, 0.13),
        ("Taps", "Tap2X"): (3, 0.13),
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
    # One wizard: drill and thread THRU ALL from the intact top face, one #29
    # tap drill.
    assert spec.TAP_SPEC.kind == "tapped"  # UNC: the block's holes are plain
    assert spec.TAP_SPEC.size == "#8-32"
    assert spec.TAP_SPEC.end == "through_all"
    assert spec.TAP_FACE == ((0.0, 0.0, 1.0), spec.BRACKET_THICK)
    assert spec.TAP_DRILL == pytest.approx(3.454)
    for hole in holes:
        assert hole["thread"].startswith(f"{spec.SCREW} UNC")


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
    for name in ("Tap1X", "Tap2X", "HoleRowY"):
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
        drawing.THREAD_ROW,
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


def test_through_thread_holds_each_screw_and_keeps_the_tips_apart() -> None:
    # Main's R4 ruling: one #8-32 thread THRU each hole. A #8-32 x 3/4 SHCS
    # comes up from the bar and a #8-32 x 5/8 SHCS down from the KP08, each in
    # at least 1.5 D of full thread at the worst case; the tips never meet.
    # The gap comes from the stock and the screws' reaches alone: the worst
    # stock, TL-20's counterbore stack under the 3/4, the least KP08 foot
    # under the 5/8. No tap depth enters it.
    major = THREAD_MAJOR_MM[spec.SCREW]
    assert spec.THICK_MIN == pytest.approx(25.4 - 0.3048)
    assert spec.BAR_REACH_MAX == pytest.approx(leadscrew.BAR_SCREW_ENGAGEMENT_RANGE[1])
    assert spec.BAR_REACH_MAX == pytest.approx(12.294, abs=1e-3)
    # PR2229 review r1 (P2): the KP08 screw reaches deepest on the least foot
    # the receipt check accepts, not on the UNVERIFIED nominal 5.0 (#2184).
    assert spec.KP08_SCREW_LENGTH_MM == pytest.approx(15.875)
    assert spec.KP08_REACH_MAX == pytest.approx(
        spec.KP08_SCREW_LENGTH_MM - spec.KP08_FOOT_THICK_MIN
    )
    assert spec.KP08_REACH_MAX > leadscrew.KP08_SCREW_REACH
    assert spec.SCREW_TIP_GAP_MIN == pytest.approx(
        spec.THICK_MIN - spec.BAR_REACH_MAX - spec.KP08_REACH_MAX
    )
    assert spec.SCREW_TIP_GAP_MIN == pytest.approx(1.905, abs=1e-3)
    # The common 3/4 from the top would collide.
    assert spec.COMMON_SCREW_TIP_GAP < 0.0
    # Rule 18 in the through thread: each screw's worst-case full thread.
    assert leadscrew.BAR_SCREW_FULL_THREAD_MIN >= 1.5 * major
    assert (
        leadscrew.full_thread_min(
            leadscrew.KP08_SCREW_LENGTH, spec.KP08_FOOT_THICK_MAX, spec.SCREW
        )
        >= 1.5 * major
    )
    taps = {name: f for name, f in _features().items() if name.startswith("tap_")}
    assert len(taps) == 2 and all(f["thru"] is True for f in taps.values())
    from prechips.model import Feature

    for feature in taps.values():
        assert "note" in feature["requirements"]
        assert "THRU" in feature["note"]
        assert not re.search(r"\d\.\d", feature["note"]), feature["note"]  # no depth
        # extra="forbid": every exported key is a Feature field (faces are
        # bound to STEP names only at write_manifest, so not validated here).
        assert set(feature) <= set(Feature.model_fields), set(feature) - set(
            Feature.model_fields
        )
    # The fastener table's receiving thread is the whole THRU height; each
    # screw stops inside it.
    for row in (fasteners.BRACKET_TO_BAR, fasteners.KP08_TO_BRACKET):
        assert row.thread_depth_mm == spec.BRACKET_THICK
        assert row.protrusion_mm < 0.0
    assert fasteners.KP08_TO_BRACKET.engagement_mm == pytest.approx(
        leadscrew.KP08_SCREW_REACH
    )


def test_kp08_receipt_band_stands_and_its_least_foot_keeps_the_tips_apart() -> None:
    # The receipt check's floor (jig step 7) is the vendor-acceptance band,
    # not widened by the through thread: .196, just under the UNVERIFIED
    # nominal 5.0 (#2184). On it the 5/8 reaches deepest and the tips still
    # clear (the test above).
    assert spec.KP08_FOOT_THICK_MIN == pytest.approx(0.196 * 25.4)
    assert _on_grid(spec.KP08_FOOT_THICK_MIN, spec.FOOT_PLACES)
    assert spec.KP08_FOOT_THICK_MIN < leadscrew.KP08_FOOT_THICK
    assert spec.SCREW_TIP_GAP_MIN > 0.0


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
    # A thicker foot only shortens the 5/8's reach: the tip gap, taken on the
    # least foot, still holds.
    assert spec.KP08_SCREW_LENGTH_MM - spec.KP08_FOOT_THICK_MAX < spec.KP08_REACH_MAX


def test_threads_are_stated_by_the_callouts_alone() -> None:
    # SolidWorks pins a "Tapped Hole" note per tap feature and view; the
    # count is its grouping, bounded by the one tap feature. The contract is
    # the settled sheet: both callouts state their thread and drill THRU, and
    # no note repeats a thread.
    assert drawing.TAP_FEATURES == ("Taps",)
    assert drawing.REDUNDANT_THREAD_NOTES == range(1, 2)
    # The readback after the class row and the lengths are set.
    settled = [drawing.THREAD_ROW, "", "<MOD-DIAM> .136 THRU ALL", ""]
    assert drawing.THREAD_ROW == "8-32 UNC THRU ALL"
    assert drawing.callout_states_its_thread(settled)
    # Negative controls: a callout that lost its thread or its drill, or
    # whose thread stops short (a depth, not THRU), is refused.
    assert not drawing.callout_states_its_thread(["", "", settled[2], ""])
    assert not drawing.callout_states_its_thread([settled[0], "", "", ""])
    assert not drawing.callout_states_its_thread(
        ["8-32 UNC <HOLE-DEPTH> .436", "", settled[2], ""]
    )
    # Every note the sheet keeps passes; any thread statement in a note is
    # caught, whatever SolidWorks calls it.
    kept = [spec.ISOMETRIC_VIEW_NOTE, ""]
    assert drawing.stray_thread_notes(kept) == []
    for stray in ("#8-32 Tapped Hole", "8-32 Tapped Hole1", "#8-32 UNC - 2B"):
        assert drawing.stray_thread_notes([*kept, stray]) == [stray]
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    body = sheet[sheet.index("async def build") :]
    assert "expected_redundant_notes=REDUNDANT_THREAD_NOTES" in body
    assert "_require_threads_stated_by_callouts_only(adapter, callouts)" in body
    assert "callouts.append((label, callout))" in body
    # One plan and one end view: no section, so no depth to print.
    assert "create_section_view" not in sheet


def test_one_wizard_drills_and_threads_thru_from_the_top_face() -> None:
    builder = Path(part.__file__).read_text(encoding="utf-8")
    assert builder.count("wizard_holes(") == 1
    wizard = builder[builder.index("wizard_holes(") :]
    wizard = wizard[: wizard.index("\n    )\n")]
    assert "TAP_SPEC," in wizard and 'name="Taps"' in wizard
    assert '(f"Tap{k}X", f\'"HoleX{k}"\')' in wizard
    # No thread stopped short, no drawn second thread.
    assert "ThreadDepth" not in builder and "add_thread(" not in builder
    assert part.V_HOLES == pytest.approx(
        len(spec.HOLE_X) * math.pi * (spec.TAP_DRILL / 2.0) ** 2 * spec.BRACKET_THICK
    )


def test_through_tap_is_an_unowned_receipt_prerequisite() -> None:
    # The #8-32 hand taps on file thread .75 on a shank wider than the tap
    # drill: none passes 1 in from one face. The route needs a tap reaching
    # through the thickest stock with its plug chamfer (5 threads at most)
    # clear of the far face; it is required, not owned, its SKU unnamed.
    pitch = 25.4 / 32.0
    assert spec.THICK_MAX == pytest.approx(25.4 + 0.3048)
    assert spec.TAP_REACH_MIN == pytest.approx(spec.THICK_MAX + 5.0 * pitch)
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    hand = inventory["tools"]["taps-unc-hand"]["members"]["8-32-plug"]
    assert hand["shank_in"]["value"] > spec.TAP_DRILL / 25.4
    assert hand["flute_len_in"]["value"] < spec.TAP_REACH_MIN / 25.4
    tool = inventory["tools"][spec.TAP_TOOL]
    assert tool["kind"] == "tap" and tool["present"] is False
    assert "sku" not in tool
    assert spec.SCREW in tool["name"]
    assert f"{spec.TAP_REACH_MIN / 25.4:.3f}" in tool["purchase"]
    # The process taps through from the top face with that tool, received
    # first; no per-face depth or tap mark survives.
    process = _config.parts(ARTIFACT)["process"]
    assert spec.TAP_TOOL in process and "through" in process
    assert process.index(spec.TAP_TOOL) < process.index("tap both holes")
    assert not re.search(r"\.\d{3}", process)


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
    keeps = (drawing.PLAN_KEEP, drawing.END_KEEP)
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
    assert drawing.CALLOUT_ROWS == 2
    assert drawing.CALLOUT_GLYPHS == len(drawing.THREAD_ROW)


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


# --- Sheet layout (model mm in the plan, sheet m around it) -----------------------


def _plan(name: str) -> tuple[float, float]:
    x, y, _z = drawing.PLAN_KEEP[name]
    return x, y


_STATION_MATES = {"Tap1X": spec.MATE_CALLOUT, "Tap2X": spec.MATE_CALLOUT}
_STATION_X = {"Tap1X": spec.HOLE_X[0], "Tap2X": spec.HOLE_X[1]}


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

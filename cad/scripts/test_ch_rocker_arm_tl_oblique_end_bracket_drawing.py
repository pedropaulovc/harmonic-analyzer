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
    # A″ retains the two KP08-pitch #29 through bores, with independently
    # limited full thread from each screw face.
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
    assert spec.BAR_TAP_SPEC.kind == spec.KP08_TAP_SPEC.kind == "tapped"
    assert spec.BAR_TAP_SPEC.size == spec.KP08_TAP_SPEC.size == "#8-32"
    assert spec.BAR_TAP_SPEC.end == "blind"
    assert spec.BAR_TAP_SPEC.depth_mm == spec.BAR_TAP_DRILL_DEPTH
    assert spec.BAR_TAP_SPEC.overrides_mm == {"ThreadDepth": spec.MODELED_THREAD_DEPTH}
    assert spec.KP08_TAP_SPEC.end == "through_all"
    assert spec.BAR_TAP_FACE == ((0.0, 0.0, -1.0), 0.0)
    assert spec.KP08_TAP_FACE == ((0.0, 0.0, 1.0), spec.BRACKET_THICK)
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
        drawing.THREAD_LIMIT_CALLOUT,
        spec.CALLOUTS_BELOW[spec.BAR_THREAD_DEPTH_DIMENSION],
        spec.CALLOUTS_BELOW[spec.KP08_THREAD_DEPTH_DIMENSION],
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


def test_opposed_full_thread_limits_protect_each_screw_from_the_other_tap() -> None:
    major = THREAD_MAJOR_MM[spec.SCREW]
    assert leadscrew.BAR_SCREW_LENGTH == leadscrew.KP08_SCREW_LENGTH == "5/8"
    assert spec.BRACKET_THICK == pytest.approx(25.4)
    assert spec.BAR_THREAD_LIMITS == pytest.approx((0.370 * 25.4, 0.496 * 25.4))
    assert spec.KP08_THREAD_LIMITS == pytest.approx((0.429 * 25.4, 0.555 * 25.4))
    assert spec.MODELED_THREAD_DEPTH == pytest.approx(0.433 * 25.4)
    assert not hasattr(spec, "BAR_THREAD_DEPTH")
    assert not hasattr(spec, "KP08_THREAD_DEPTH")
    assert all(
        low < spec.MODELED_THREAD_DEPTH < high
        for low, high in (spec.BAR_THREAD_LIMITS, spec.KP08_THREAD_LIMITS)
    )
    assert spec.BAR_REACH_MAX == pytest.approx(leadscrew.BAR_SCREW_ENGAGEMENT_RANGE[1])
    for bounds, reach, opposed_reach in (
        (spec.BAR_THREAD_LIMITS, spec.BAR_REACH_MAX, spec.KP08_REACH_MAX),
        (spec.KP08_THREAD_LIMITS, spec.KP08_REACH_MAX, spec.BAR_REACH_MAX),
    ):
        low, high = bounds
        assert low >= reach - 1e-9
        assert low >= 1.5 * major
        assert high + spec.BOTTOMING_LEAD_LIMITS[1] + opposed_reach <= spec.THICK_MIN
        assert all(_on_grid(value, 3) for value in bounds)
    # Thread zones may overlap in the unused middle; no artificial central
    # web/non-overlap guard may replace either screw-zone exclusion.
    assert sum((spec.BAR_THREAD_LIMITS[1], spec.KP08_THREAD_LIMITS[1])) > spec.THICK_MIN
    assert leadscrew.BAR_SCREW_FULL_THREAD_MIN >= 1.5 * major
    assert leadscrew.full_thread_min(
        leadscrew.KP08_SCREW_LENGTH, spec.KP08_FOOT_THICK_MAX, spec.SCREW
    ) >= 1.5 * major
    assert spec.SCREW_TIP_GAP_MIN == pytest.approx(
        spec.THICK_MIN - spec.BAR_REACH_MAX - spec.KP08_REACH_MAX
    )
    assert spec.SCREW_TIP_GAP_MIN > 0.0
    assert fasteners.BRACKET_TO_BAR.thread_depth_mm == spec.BAR_THREAD_LIMITS[0]
    assert fasteners.KP08_TO_BRACKET.thread_depth_mm == spec.KP08_THREAD_LIMITS[0]
    from prechips.model import Feature

    for name in ("tap_1", "tap_2"):
        feature = _features()[name]
        assert feature["thru"] is True and "note" in feature["requirements"]
        for low, high in (spec.BAR_THREAD_LIMITS, spec.KP08_THREAD_LIMITS):
            assert f"{low:.3f} TO {high:.3f} mm" in feature["note"]
        assert set(feature) <= set(Feature.model_fields)


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


def test_threads_are_stated_by_native_callouts_and_section_limits() -> None:
    assert drawing.TAP_FEATURES == ("BarTaps", "KP08Taps")
    pointer = drawing.THREAD_LIMIT_CALLOUT
    assert drawing.callout_states_its_thread([f"8-32 UNC\n{pointer}", "", "", ""])
    assert not drawing.callout_states_its_thread([pointer, "", "", ""])
    assert not drawing.callout_states_its_thread(["8-32 UNC THRU ALL", "", "", ""])
    assert not drawing.callout_states_its_thread(
        [f"8-32 UNC <hw-threaddepth>\n{pointer}", "", "", ""]
    )
    for stray in ("#8-32 Tapped Hole", "8-32 Tapped Hole1", "#8-32 UNC - 2B"):
        assert drawing.stray_thread_notes([spec.ISOMETRIC_VIEW_NOTE, stray]) == [stray]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_require_thread_depths(section)" in source
    assert "_require_threads_drawn(adapter, section)" in source
    assert "_require_threads_stated_by_callouts_only(adapter, callouts)" in source


def test_bottom_blind_precursor_leaves_real_material_for_the_top_wizard() -> None:
    assert spec.BAR_TAP_DRILL_DEPTH == pytest.approx(0.625 * 25.4)
    from _hole_spec import DRILL_POINT_H

    assert spec.MODELED_THREAD_DEPTH < spec.BAR_TAP_DRILL_DEPTH
    assert spec.BAR_TAP_DRILL_DEPTH + spec.TAP_DRILL / 2.0 * DRILL_POINT_H < spec.THICK_MIN
    assert spec.BAR_TAP_DRILL_DEPTH != pytest.approx(
        spec.BRACKET_THICK - spec.MODELED_THREAD_DEPTH
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build"):]
    assert body.count("wizard_holes(") == 2
    assert body.index("BAR_TAP_SPEC,") < body.index("KP08_TAP_SPEC,")
    assert body.index("KP08_TAP_SPEC,") < body.index("_bar_face_cosmetic_threads(")
    assert body.index("_bar_face_cosmetic_threads(") < body.index("_drive_and_finalize_threads(")
    assert "_thread_from_face(" not in body
    assert "diameter=THREAD_MAJOR" in source
    assert part.V_HOLES == pytest.approx(
        len(spec.HOLE_X) * math.pi * (spec.TAP_DRILL / 2.0) ** 2 * spec.BRACKET_THICK
    )


def test_owned_hand_taps_replace_the_extension_tap_prerequisite() -> None:
    assert not hasattr(spec, "TAP_REACH_MIN") and not hasattr(spec, "TAP_TOOL")
    inventory = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "inventory.toml").read_text(encoding="utf-8")
    )
    assert "tap-8-32-extension-spiral-point" not in inventory["tools"]
    hand = inventory["tools"]["taps-unc-hand"]["members"]["8-32-plug"]
    assert hand["flute_len_in"]["value"] == pytest.approx(0.75)
    process = _config.parts(ARTIFACT)["process"].lower()
    assert "plug" in process and "bottoming" in process
    assert "tap-8-32-extension-spiral-point" not in process
    for low, high in (spec.BAR_THREAD_LIMITS, spec.KP08_THREAD_LIMITS):
        assert f"{low / 25.4:.3f}".lstrip("0") in process
        assert f"{high / 25.4:.3f}".lstrip("0") in process


def test_hole_size_row_and_stations_retain_their_existing_bands() -> None:
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
    assert drawing.CALLOUT_GLYPHS >= len(drawing.THREAD_LIMIT_CALLOUT)


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


def test_native_callouts_share_one_drill_requirement_and_never_type_depths() -> None:
    definitions = {
        5: "<hw-thread> UNC - <hw-threadclass> <HOLE-DEPTH><hw-threaddepth>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-tapdrldia> THRU ALL",
        8: "",
    }
    first = drawing.thread_limit_definitions(definitions, include_drill=True)
    second = drawing.thread_limit_definitions(definitions, include_drill=False)
    all_text = "\n".join((*first.values(), *second.values()))
    assert all_text.count("#29 DRILL") == all_text.count("THRU ALL") == 1
    assert "<hw-tapdrldia>" in first[7] and second[7] == ""
    assert all_text.count("<hw-thread>") == 2
    assert all_text.count(drawing.THREAD_LIMIT_CALLOUT) == 2
    assert "<hw-threaddepth>" not in all_text
    assert "<HOLE-DEPTH>" not in all_text
    assert not re.search(r"\d*\.\d", all_text)
    with pytest.raises(RuntimeError):
        drawing.thread_limit_definitions(
            {**definitions, 7: "<NUM_INST>X <hw-tapdrldia> BLIND"},
            include_drill=True,
        )
    with pytest.raises(RuntimeError):
        drawing.thread_limit_definitions(
            {**definitions, 5: "<hw-thread> THRU ALL"}, include_drill=True,
        )


def test_both_full_thread_depths_have_part_owned_limit_dimensions() -> None:
    for reference, name, nominal, bounds in (
        (spec.BAR_THREAD_REFERENCE, spec.BAR_THREAD_DEPTH_DIMENSION,
         spec.MODELED_THREAD_DEPTH, spec.BAR_THREAD_LIMITS),
        (spec.KP08_THREAD_REFERENCE, spec.KP08_THREAD_DEPTH_DIMENSION,
         spec.MODELED_THREAD_DEPTH, spec.KP08_THREAD_LIMITS),
    ):
        assert spec.DRAWING_DIMENSIONS[reference] == {name}
        assert spec.DRAWING_PRECISION[reference][name] == 3
        assert name in drawing.SECTION_KEEP and name in drawing.SECTION_TEXT
        assert bounds[0] < nominal < bounds[1]
        label = spec.CALLOUTS_BELOW[name]
        assert "FULL THREAD" in label and "BOTH HOLES" in label
        assert not re.search(r"\d*\.\d", label)
    assert spec.BAR_THREAD_WITNESS_X == pytest.approx(
        spec.HOLE_X[-1] + spec.THREAD_MAJOR / 2.0
    )
    assert spec.KP08_THREAD_WITNESS_X == pytest.approx(
        spec.HOLE_X[0] - spec.THREAD_MAJOR / 2.0
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "top_ref.record(KP08_THREAD_DEPTH_DIMENSION" in source
    assert "blank_sketch(adapter, KP08_THREAD_REFERENCE)" in source
    assert source.index("_set_thread_limits(") < source.index("save_part_and_images(")


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


@pytest.mark.parametrize("drift", [None, "drill_end", "thread_end", "depth"])
def test_local_post_wizard_edit_preserves_thru_drill_and_reads_thread_back(
    monkeypatch, drift,
) -> None:
    from types import SimpleNamespace

    definition = SimpleNamespace(EndCondition=1, ThreadEndCondition=0, ThreadDepth=0.012)
    feature = SimpleNamespace(GetDefinition=lambda: definition)
    model = SimpleNamespace(FeatureByName=lambda name: feature)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    edits_seen = []

    def commit(got_model, got_feature, got_definition, edits, label):
        assert (got_model, got_feature, got_definition) == (model, feature, definition)
        edits_seen.extend(edits)
        for name, value in edits:
            setattr(definition, name, value)
        if drift == "drill_end":
            definition.EndCondition = 0
        elif drift == "thread_end":
            definition.ThreadEndCondition = 1
        elif drift == "depth":
            definition.ThreadDepth += 0.001
        return definition

    monkeypatch.setattr(part, "_commit_definition_edits", commit)
    adapter = SimpleNamespace(currentModel=model)
    if drift:
        with pytest.raises(RuntimeError, match="thread did not stop short"):
            part._thread_from_face(adapter, "KP08Taps", 12.0, label="test")
    else:
        part._thread_from_face(adapter, "KP08Taps", 12.0, label="test")
    assert edits_seen == [("ThreadEndCondition", 0), ("ThreadDepth", 0.012)]


@pytest.mark.parametrize("face", ["bar", "kp08"])
@pytest.mark.parametrize("refuse", [False, True])
def test_limit_tolerance_is_written_to_the_part_and_read_back(monkeypatch, refuse, face) -> None:
    from types import SimpleNamespace

    class Tolerance:
        def __init__(self):
            self._type = 2
            self.low = self.high = 0.0

        @property
        def Type(self):
            return self._type

        @Type.setter
        def Type(self, value):
            if not refuse:
                self._type = value

        def GetMinValue(self):
            return self.low

        def GetMaxValue(self):
            return self.high

    tolerance = Tolerance()
    nominal = spec.MODELED_THREAD_DEPTH
    reference, dimension_name, bounds = (
        (spec.BAR_THREAD_REFERENCE, spec.BAR_THREAD_DEPTH_DIMENSION, spec.BAR_THREAD_LIMITS)
        if face == "bar" else
        (spec.KP08_THREAD_REFERENCE, spec.KP08_THREAD_DEPTH_DIMENSION, spec.KP08_THREAD_LIMITS)
    )
    low, high = bounds
    from _drawing_tolerances import _tolerance_places

    assert _tolerance_places(low - nominal, high - nominal, display_unit="in") == 3
    dimension = SimpleNamespace(SystemValue=nominal / 1000.0, Tolerance=tolerance)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (object(), dimension))
    calls = []

    def bilateral(adapter, reference, name, lower, upper, **kwargs):
        calls.append((reference, name, lower, upper, kwargs))
        tolerance.low, tolerance.high = lower / 1000.0, upper / 1000.0

    monkeypatch.setattr(part, "set_dimension_bilateral_tolerance", bilateral)
    args = (None, reference, dimension_name, nominal, (low, high))
    if refuse:
        with pytest.raises(RuntimeError, match="native thread limits differ"):
            part._set_thread_limits(*args)
    else:
        part._set_thread_limits(*args)
        assert tolerance.Type == 3
    assert calls == [
        (reference, dimension_name,
         low - nominal, high - nominal, {"places": 3, "display_unit": "in"})
    ]


@pytest.mark.parametrize("failure", [None, "missing", "owner", "band", "nominal", "wizard"])
def test_section_refuses_unowned_or_lost_full_thread_limits(monkeypatch, failure) -> None:
    from types import SimpleNamespace

    displays = []
    wizards = {}
    for index, (reference, name, feature, nominal, bounds) in enumerate((
        (spec.BAR_THREAD_REFERENCE, spec.BAR_THREAD_DEPTH_DIMENSION, "BarTaps",
         spec.MODELED_THREAD_DEPTH, spec.BAR_THREAD_LIMITS),
        (spec.KP08_THREAD_REFERENCE, spec.KP08_THREAD_DEPTH_DIMENSION, "KP08Taps",
         spec.MODELED_THREAD_DEPTH, spec.KP08_THREAD_LIMITS),
    )):
        low, high = bounds
        tolerance = SimpleNamespace(
            Type=2 if failure == "band" and index == 0 else 3,
            GetMinValue=lambda value=(low - nominal) / 1000.0: value,
            GetMaxValue=lambda value=(high - nominal) / 1000.0: value,
        )
        owner = "UnrelatedSketch" if failure == "owner" and index == 0 else reference
        dim = SimpleNamespace(
            FullName=f"{name}@{owner}@part",
            SystemValue=(nominal + (1.0 if failure == "nominal" and index == 0 else 0.0)) / 1000,
            Tolerance=tolerance,
        )
        displays.append(SimpleNamespace(
            GetDimension2=lambda _config, value=dim: value,
            GetPrimaryTolPrecision2=lambda: 3,
        ))
        wizard = SimpleNamespace(
            ThreadDepth=nominal / 1000.0,
            ThreadEndCondition=1 if failure == "wizard" and index == 0 else 0,
        )
        wizards[feature] = SimpleNamespace(GetDefinition=lambda value=wizard: value)
    if failure == "missing":
        displays.pop()
    model = SimpleNamespace(FeatureByName=lambda name: wizards[name])
    section = SimpleNamespace(
        ReferencedDocument=model, GetDisplayDimensions=lambda: displays,
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    if failure:
        with pytest.raises(RuntimeError):
            drawing._require_thread_depths(section)
    else:
        drawing._require_thread_depths(section)


def test_both_section_limit_blocks_stand_clear_of_the_body_and_title_block() -> None:
    scale = drawing._S / 1000.0
    for name, (text_x, _y, text_z) in drawing.SECTION_TEXT.items():
        half = drawing.text_half(spec.CALLOUTS_BELOW[name])
        rows = 2 + len(spec.CALLOUTS_BELOW[name].splitlines())
        half_high = drawing.text_half_high(rows)
        if name == spec.BAR_THREAD_DEPTH_DIMENSION:
            assert text_x - half >= spec.BRACKET_LENGTH + drawing.DEPTH_LANE
        else:
            assert text_x + half <= -drawing.DEPTH_LANE
        centre_x, centre_y = drawing.SECTION_CENTER
        left = centre_x + (text_x - half - spec.BRACKET_LENGTH / 2.0) * scale
        right = centre_x + (text_x + half - spec.BRACKET_LENGTH / 2.0) * scale
        bottom = centre_y + (text_z - half_high - spec.BRACKET_THICK / 2.0) * scale
        assert LEFT_BORDER < left < right < RIGHT_BORDER
        assert bottom > TITLE_BLOCK_TOP + 0.01


def test_thread_ink_requires_complete_native_depth_coverage() -> None:
    start, end = (0.1, 0.08), (0.1, 0.105)
    assert drawing._covers([(0.1, 0.08, 0.1, 0.105)], start, end)
    assert drawing._covers([(0.1, 0.08, 0.1, 0.105)], end, start)
    assert not drawing._covers([], start, end)
    assert not drawing._covers([(0.1, 0.08, 0.1, 0.09)], start, end)


def test_native_drill_token_is_preserved_without_assuming_blind_tap_names() -> None:
    definitions = {
        5: "<hw-thread> UNC <HOLE-DEPTH><hw-threaddepth>",
        6: "",
        7: "<NUM_INST>X <MOD-DIAM><hw-thruholedia> THRU ALL",
        8: "",
    }
    result = drawing.thread_limit_definitions(definitions, include_drill=True)
    assert "<hw-thruholedia>" in result[7]
    assert "<hw-tapdrldia>" not in result[7]


def test_tip_marks_finish_full_threads_without_reaching_the_opposed_screw() -> None:
    assert spec.BAR_TIP_MARK_LIMITS == pytest.approx((.433 * 25.4, .527 * 25.4))
    assert spec.KP08_TIP_MARK_LIMITS == pytest.approx((.492 * 25.4, .586 * 25.4))
    assert leadscrew.BAR_SCREW_ACTUAL_REACH_RANGE == pytest.approx((7.874, 9.398))
    assert (spec.KP08_REACH_MIN, spec.KP08_REACH_MAX) == pytest.approx((7.6962, 10.8966))
    assert leadscrew.BAR_SCREW_FULL_THREAD_MIN == pytest.approx(6.433375)
    assert spec.KP08_FULL_THREAD_AT_RECEIPT_MAX == pytest.approx(6.255575)
    lead_low, lead_high = spec.BOTTOMING_LEAD_LIMITS
    for full, marks, opposite_reach in (
        (spec.BAR_THREAD_LIMITS, spec.BAR_TIP_MARK_LIMITS, spec.KP08_REACH_MAX),
        (spec.KP08_THREAD_LIMITS, spec.KP08_TIP_MARK_LIMITS, spec.BAR_REACH_MAX),
    ):
        assert marks[0] - lead_high >= full[0] - 1e-9
        assert marks[1] - lead_low <= full[1] + 1e-9
        assert marks[1] + opposite_reach < spec.THICK_MIN
        assert marks[1] < spec.HAND_TAP_FLUTE_LENGTH
    assert min(
        spec.BAR_OPPOSED_CUT_CLEARANCE_MIN, spec.KP08_OPPOSED_CUT_CLEARANCE_MIN
    ) == pytest.approx(0.0127)
    assert spec.TIP_MARK_SEAM_CLEARANCE_MIN == pytest.approx(0.8128)
    assert spec.TIP_MARK_SEAM_CLEARANCE_MIN > min(
        spec.BAR_OPPOSED_CUT_CLEARANCE_MIN, spec.KP08_OPPOSED_CUT_CLEARANCE_MIN
    )


# Captured values are evidence, not regenerated expected output.
# 4031a82a: both wizards read 10.9982; the top witness remained 12.4968.
# 0e989113: editing the top to 12.4968 changed BOTH bottom cosmetic depths,
# but BarTaps and its witness remained 10.9982. Circle readbacks are from
# that second log (worker 4); no first-run cosmetic depths were captured.
_FIRST_WIZARD_DEPTHS_MM = {"BarTaps": 10.9982, "KP08Taps": 10.9982}
_FIRST_TOP_WITNESS_MM = 12.4968
_SECOND_NATIVE_DEPTHS_MM = {
    "BarTaps": 10.9982, "KP08Taps": 12.4968,
    "BarFaceThread1": 12.4968, "BarFaceThread2": 12.4968,
}
_SECOND_BOTTOM_CIRCLES_MM = (
    [13.925000090000001, 0.0, -6.938893903907228e-15, 1.7271999999999843],
    [55.92499991, 0.0, -6.938893903907228e-15, 1.7271999999999843],
)


def test_observed_native_depth_pairs_support_coupling_not_independence() -> None:
    assert tuple(_FIRST_WIZARD_DEPTHS_MM.values()) == pytest.approx(
        (spec.MODELED_THREAD_DEPTH, spec.MODELED_THREAD_DEPTH)
    )
    assert _FIRST_TOP_WITNESS_MM != pytest.approx(_FIRST_WIZARD_DEPTHS_MM["KP08Taps"])
    assert (
        _SECOND_NATIVE_DEPTHS_MM["KP08Taps"],
        _SECOND_NATIVE_DEPTHS_MM["BarFaceThread1"],
        _SECOND_NATIVE_DEPTHS_MM["BarFaceThread2"],
    ) == pytest.approx((12.4968, 12.4968, 12.4968))
    assert _SECOND_NATIVE_DEPTHS_MM["BarTaps"] != _SECOND_NATIVE_DEPTHS_MM["KP08Taps"]


@pytest.mark.parametrize("post_commit_drift", [None, "top", "bottom"])
def test_shared_thread_depth_survives_observed_coupling_driving_and_rebuild(
    monkeypatch, post_commit_drift,
) -> None:
    """Replay captured coupled state, then exercise the proposed common target.

    The initial readings below are the second native failure. Writing top depth
    also writes both bottom cosmetics, as observed in that run. A successful
    replay is an offline contract proof, not a new native observation at .433.
    """
    import asyncio
    from types import SimpleNamespace

    shared = {"depth": _SECOND_NATIVE_DEPTHS_MM["KP08Taps"] / 1000.0}

    class TopWizard:
        EndCondition = 1
        ThreadEndCondition = 0

        @property
        def ThreadDepth(self):
            return shared["depth"]

        @ThreadDepth.setter
        def ThreadDepth(self, value):
            shared["depth"] = value

    class BottomCosmetic:
        EndCondition = 0
        DiameterType = 2
        Diameter = 4.166 / 1000.0

        def __init__(self, circle):
            self.circle = circle
            self.corrupted_depth = None

        @property
        def BlindDepth(self):
            return shared["depth"] if self.corrupted_depth is None else self.corrupted_depth

    bar = SimpleNamespace(
        EndCondition=0, ThreadEndCondition=0,
        ThreadDepth=_SECOND_NATIVE_DEPTHS_MM["BarTaps"] / 1000.0,
    )
    top = TopWizard()
    cosmetics = {
        f"BarFaceThread{k}": BottomCosmetic(circle)
        for k, circle in enumerate(_SECOND_BOTTOM_CIRCLES_MM, start=1)
    }
    definitions = {"BarTaps": bar, "KP08Taps": top, **cosmetics}
    features = {
        name: SimpleNamespace(GetDefinition=lambda value=value: value)
        for name, value in definitions.items()
    }
    model = SimpleNamespace(FeatureByName=lambda name: features.get(name))
    adapter = SimpleNamespace(currentModel=model)
    monkeypatch.setattr(part, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        part, "_thread_edge_circle", lambda _model, definition, **_kwargs: definition.circle,
    )
    # Positive control: these exact captured cosmetic values are read, not
    # replaced with expectations. The old mismatched full state must fail.
    assert tuple(value.BlindDepth * 1000.0 for value in cosmetics.values()) == pytest.approx(
        (_SECOND_NATIVE_DEPTHS_MM["BarFaceThread1"], _SECOND_NATIVE_DEPTHS_MM["BarFaceThread2"])
    )
    with pytest.raises(RuntimeError, match="bar-face threads"):
        part._require_bar_face_threads(adapter, tuple(cosmetics))

    rows = {
        spec.BAR_THREAD_REFERENCE: {
            "BarThreadStation": spec.BAR_THREAD_WITNESS_X,
            spec.BAR_THREAD_DEPTH_DIMENSION: _SECOND_NATIVE_DEPTHS_MM["BarTaps"],
        },
        spec.KP08_THREAD_REFERENCE: {
            "KP08ThreadStation": spec.KP08_THREAD_WITNESS_X,
            "KP08ThreadFace": spec.BRACKET_THICK,
            spec.KP08_THREAD_DEPTH_DIMENSION: _FIRST_TOP_WITNESS_MM,
        },
    }
    monkeypatch.setattr(
        part, "dump_dimensions",
        lambda _adapter, reference: [
            {"full_name": f"{name}@{reference}@part", "value_mm": value}
            for name, value in rows[reference].items()
        ],
    )
    jobs = [
        (f"{spec.BAR_THREAD_DEPTH_DIMENSION}@{spec.BAR_THREAD_REFERENCE}", '"ModeledThreadDepth"'),
        (f"{spec.KP08_THREAD_DEPTH_DIMENSION}@{spec.KP08_THREAD_REFERENCE}", '"ModeledThreadDepth"'),
    ]
    events = []
    commits = []

    async def drive(_adapter, full_name, expression):
        assert expression == '"ModeledThreadDepth"'
        events.append(("drive", full_name, expression))
        name, reference = full_name.split("@")
        rows[reference][name] = spec.MODELED_THREAD_DEPTH

    async def rebuild(_adapter):
        events.append(("rebuild",))
        if commits and post_commit_drift == "top":
            top.ThreadDepth = _SECOND_NATIVE_DEPTHS_MM["KP08Taps"] / 1000.0
        elif commits and post_commit_drift == "bottom":
            next(iter(cosmetics.values())).corrupted_depth = 12.4968 / 1000.0

    def commit(got_model, got_feature, definition, edits, _label):
        assert got_model is model and got_feature is features["KP08Taps"]
        assert definition is top
        assert definition.ThreadDepth * 1000.0 == pytest.approx(
            _SECOND_NATIVE_DEPTHS_MM["KP08Taps"]
        )
        events.append(("commit",))
        commits.append(tuple(edits))
        for name, value in edits:
            setattr(definition, name, value)
        return definition

    monkeypatch.setattr(part, "drive_dimension", drive)
    monkeypatch.setattr(part, "force_rebuild", rebuild)
    monkeypatch.setattr(part, "_commit_definition_edits", commit)
    if post_commit_drift:
        with pytest.raises(RuntimeError, match="KP08ThreadReference|bar-face threads"):
            asyncio.run(part._drive_and_finalize_threads(adapter, jobs, tuple(cosmetics)))
    else:
        asyncio.run(part._drive_and_finalize_threads(adapter, jobs, tuple(cosmetics)))
        assert top.ThreadDepth == pytest.approx(spec.MODELED_THREAD_DEPTH / 1000.0)
        assert bar.ThreadDepth == pytest.approx(spec.MODELED_THREAD_DEPTH / 1000.0)
        assert all(
            value.BlindDepth == pytest.approx(spec.MODELED_THREAD_DEPTH / 1000.0)
            for value in cosmetics.values()
        )
    assert top.EndCondition == 1 and top.ThreadEndCondition == 0
    assert len(commits) == 1
    assert events == [
        ("rebuild",),
        *(("drive", name, expression) for name, expression in jobs),
        ("rebuild",), ("commit",), ("rebuild",),
    ]
    assert rows[spec.KP08_THREAD_REFERENCE][spec.KP08_THREAD_DEPTH_DIMENSION] == pytest.approx(
        spec.MODELED_THREAD_DEPTH
    )

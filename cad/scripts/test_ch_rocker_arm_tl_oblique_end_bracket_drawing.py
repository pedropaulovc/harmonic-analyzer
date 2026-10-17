"""Offline contracts for the oblique-trammel jig's end bracket (MHA-CH-006-TL-28)."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import _drawing_contract
import build_ch_rocker_arm_tl_oblique_end_bracket as part
import ch_rocker_arm_tl_oblique_end_bracket_spec as spec
import ch_rocker_arm_tl_oblique_leadscrew_spec as leadscrew
import draw_ch_rocker_arm_tl_oblique_end_bracket as drawing
import export_features
from _drawing_contract import model_toleranced_dimensions
from _hole_spec import METRIC_KINDS, THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_oblique_end_bracket"
ARTIFACT = "ch-rocker-arm-tl-oblique-end-bracket"
TITLE_BLOCK_TOP = 0.0652  # sheet m (base bar test)
TITLE_BLOCK_LEFT = 0.216
TOP_BORDER = 0.267
RIGHT_BORDER = 0.4194
LEFT_BORDER = 0.0124


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def _lateral(x: float) -> float:
    """Bracket model X -> machine lateral (the leadscrew spec's placement)."""
    return leadscrew.BRACKET_INNER_LATERAL + x


def test_stock_is_the_layouts_half_by_three_quarter_flat() -> None:
    assert (spec.BRACKET_THICK, spec.BRACKET_WIDTH, spec.BRACKET_LENGTH) == (
        12.7,
        19.05,
        64.5,
    )
    assert spec.BRACKET_LENGTH == pytest.approx(leadscrew.BRACKET_LENGTH)
    assert spec.BRACKET_WIDTH == pytest.approx(leadscrew.BRACKET_WIDTH)
    assert spec.STOCK_DIMENSIONS == {"BracketWidth", "BracketThick"}
    for name in spec.STOCK_DIMENSIONS:
        assert spec.CALLOUTS_BELOW[name] == "STOCK"
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 2  # 19.05, 12.70


def test_kp08_taps_land_on_the_blocks_bolt_spacing_about_the_screw() -> None:
    holes = [_features()[f"kp08_tap_{i}"] for i in (1, 2)]
    laterals = [_lateral(h["at"][0]) for h in holes]
    half = leadscrew.KP08_BOLT_SPACING / 2.0
    assert laterals == pytest.approx(
        [leadscrew.SCREW_LATERAL - half, leadscrew.SCREW_LATERAL + half]
    )
    assert spec.KP08_TAP_X == (14.0, 56.0)
    assert all(h["at"][1] == 0.0 for h in holes)  # the row on the screw's KP08_S
    assert spec.KP08_TAP_SPEC.kind in METRIC_KINDS
    assert spec.KP08_TAP_SPEC.size == "M4x0.7"
    assert spec.KP08_TAP_SPEC.end == "through_all"
    assert spec.KP08_TAP_DRILL == pytest.approx(3.3)


def test_bar_taps_land_on_the_base_bars_bracket_holes() -> None:
    holes = [_features()[f"bar_tap_{i}"] for i in (1, 2)]
    laterals = [_lateral(h["at"][0]) for h in holes]
    assert laterals == pytest.approx(list(leadscrew.BAR_SCREW_LATERALS))
    assert spec.BAR_TAP_X == (6.0, 24.0)
    assert spec.BAR_TAP_SPEC.kind == "tapped"
    assert spec.BAR_TAP_SPEC.size == leadscrew.BAR_SCREW == "#8-32"
    assert spec.BAR_TAP_SPEC.end == "through_all"
    # No counterbore in this part: the screws come up through the bar.
    assert not any(kind.startswith("counterbore") for kind in (spec.BAR_TAP_SPEC.kind,))


def test_both_patterns_fit_their_mates_at_three_places() -> None:
    assert spec.POSITION_RADIUS == pytest.approx(math.hypot(0.13, 0.13))
    assert spec.KP08_SCREW_FLOAT == pytest.approx(0.25)
    assert spec.KP08_PATTERN_ALLOWANCE == pytest.approx(0.0662, abs=1e-4)
    assert spec.BAR_HOLE_DIA == pytest.approx(4.978)
    assert spec.BAR_PATTERN_ALLOWANCE == pytest.approx(0.2222, abs=1e-4)
    stations = {"BarTap1X", "BarTap2X", "KP08Tap1X", "KP08Tap2X", "HoleRowY"}
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 3 for name in stations)
    # The title block's two-place ±0.51 would not fit either pattern.
    assert math.hypot(0.51, 0.51) > max(spec.KP08_SCREW_FLOAT, spec.BAR_SCREW_FLOAT)


def test_every_tight_band_names_its_mate() -> None:
    for name in ("KP08Tap1X", "KP08Tap2X"):
        assert spec.CALLOUTS_BELOW[name] == spec.KP08_MATE_CALLOUT
    for name in ("BarTap1X", "BarTap2X"):
        assert spec.CALLOUTS_BELOW[name] == spec.BAR_MATE_CALLOUT
    assert spec.CALLOUTS_BELOW["HoleRowY"] == spec.ROW_CALLOUT
    assert "KP08" in spec.KP08_MATE_CALLOUT
    assert "MHA-CH-006-TL-20" in spec.BAR_MATE_CALLOUT
    assert "KP08" in spec.ROW_CALLOUT and "MHA-CH-006-TL-20" in spec.ROW_CALLOUT
    # Every three-place dimension on the sheet carries its mate.
    three_place = {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 3
    }
    assert three_place <= set(spec.CALLOUTS_BELOW)
    for name, feature in _features().items():
        if name.startswith(("bar_tap", "kp08_tap")):
            assert feature["note"].startswith("MATCHES"), name


def test_no_vendor_sku_on_the_sheet() -> None:
    texts = (
        spec.KP08_MATE_CALLOUT,
        spec.BAR_MATE_CALLOUT,
        spec.ROW_CALLOUT,
        spec.DRAWING_NOTES,
        spec.ISOMETRIC_VIEW_NOTE,
    )
    for text in texts:
        assert not re.search(r"\b\d{4,}[A-Z]\d+\b", text), text  # McMaster style
        assert "AMPEC" not in text.upper()


def test_walls_hold_rule_17_at_worst_case() -> None:
    walls = spec.WALLS_MM
    assert min(walls.values()) >= spec.WALL_TARGET == 2.0
    assert walls["#8 tap at 6 to inner end"] == pytest.approx(3.787, abs=1e-3)
    assert walls["#8 tap at 6 to M4 tap at 14"] == pytest.approx(3.657, abs=1e-3)
    assert walls["M4 tap at 14 to #8 tap at 24"] == pytest.approx(5.657, abs=1e-3)
    assert walls["M4 tap at 56 to outer end"] == pytest.approx(5.57, abs=1e-3)
    assert walls["row to -Y side"] == pytest.approx(7.312, abs=1e-3)
    assert walls["row to +Y side"] == pytest.approx(6.802, abs=1e-3)
    assert spec.RULE_20_SHORTFALLS == ()
    # Cross-check from the exported bands: each thread's major at its station
    # band's far end.
    holes = _features()
    bar_1, kp08_1 = holes["bar_tap_1"], holes["kp08_tap_1"]
    bar_r = THREAD_MAJOR_MM[spec.BAR_SCREW] / 2.0
    kp08_r = THREAD_MAJOR_MM[spec.KP08_THREAD] / 2.0
    assert bar_1["station"][0] - bar_r >= 2.0
    assert kp08_1["station"][0] - bar_1["station"][1] - bar_r - kp08_r >= 2.0
    assert bar_1["height"][0] - bar_r >= 2.0


def test_through_thread_offers_one_and_a_half_diameters() -> None:
    for thread in (spec.BAR_SCREW, spec.KP08_THREAD):
        assert spec.BRACKET_THICK >= 1.5 * THREAD_MAJOR_MM[thread]


def test_holes_carry_the_title_block_band_only() -> None:
    assert model_toleranced_dimensions(part) == {}
    holes = _features()
    assert holes["bar_tap_1"]["dia"] == [3.45, 3.55]
    assert holes["kp08_tap_1"]["dia"] == [3.3, 3.4]
    assert holes["kp08_tap_2"]["station"] == [55.87, 56.13]
    assert holes["bar_tap_1"]["height"] == [9.395, 9.655]
    assert holes["bar_tap_1"]["height_from"] == "bracket_low_side"


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PLAN_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.PLAN_KEEP) & set(drawing.END_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) <= marked


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (name, requirement)
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement)
                assert abs(nominal - round(nominal, places)) < 1e-9
            checked += 1
    assert checked


def test_row_is_located_from_the_faced_low_side() -> None:
    assert spec.HOLE_ROW_Y == pytest.approx(9.525)
    assert spec.DRAWING_DIMENSIONS["HoleRowReference"] == {"HoleRowY"}
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert 'row_station.record("HoleRowY", \'"BracketWidth" / 2\')' in build
    assert build.index('blank_sketch(adapter, "HoleRowReference")') < build.index(
        "save_part_and_images(adapter, PART_NAME)"
    )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in sheet
    assert drawing._FROM_LOW_SIDE[0] == "bracket_low_side"


def test_every_tap_has_its_own_callout_and_the_bar_ones_drop_the_class() -> None:
    called = sorted((kind, x) for kind, x, _xy, _side in drawing.TAP_CALLOUTS)
    assert called == sorted(
        [("bar", x) for x in spec.BAR_TAP_X] + [("kp08", x) for x in spec.KP08_TAP_X]
    )
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert sheet.count("add_native_hole_callout(\n") == 1  # in the per-tap loop
    assert "for kind, x, (text_x, text_y), side in TAP_CALLOUTS:" in sheet
    assert "_call_out_one_hole(callout, label=label)" in sheet
    assert 'if kind == "bar":\n            _omit_tap_thread_class(callout)' in sheet
    # Two tap features in the plan, two auto notes (module comment).
    assert "expected_redundant_notes=2" in sheet


def test_single_hole_definitions_drop_exactly_the_count() -> None:
    definitions = {
        5: "<hw-thread> UNC - <hw-threadclass> THRU ALL",
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
    assert not drawing._PRINTED_COUNT.search("Ø3.45 THRU ALL\nM4x0.7 - 6H THRU ALL")


# --- Sheet layout (model mm in the plan, sheet m around it) -----------------------


def _plan(name: str) -> tuple[float, float]:
    x, y, _z = drawing.PLAN_KEEP[name]
    return x, y


_STATION_MATES = {
    "BarTap1X": spec.BAR_MATE_CALLOUT,
    "KP08Tap1X": spec.KP08_MATE_CALLOUT,
    "BarTap2X": spec.BAR_MATE_CALLOUT,
    "KP08Tap2X": spec.KP08_MATE_CALLOUT,
}
_STATION_X = {
    "BarTap1X": spec.BAR_TAP_X[0],
    "KP08Tap1X": spec.KP08_TAP_X[0],
    "BarTap2X": spec.BAR_TAP_X[1],
    "KP08Tap2X": spec.KP08_TAP_X[1],
}


def _block(name: str) -> tuple[float, float, float, float]:
    """A text block's (left, right, bottom, top), model mm: a station's value
    over its mate (the mate the wider line), the length one line."""
    x, y = _plan(name)
    if name == "BracketLength":
        half, half_high = drawing.text_half("64.5"), drawing.text_half_high(1)
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
    assert rows == 3
    half_high = drawing.text_half_high(rows)
    assert y - half_high >= -spec.HOLE_ROW_Y + 0.25
    assert y + half_high <= -0.25
    half = drawing.text_half(drawing._ROW_TEXT)
    assert x + half <= -drawing.SIDE_LANE
    left, _ = drawing.plan_sheet(x - half, y)
    assert left >= LEFT_BORDER + 0.01


def _callout_block(kind: str, xy: tuple[float, float]) -> tuple[float, ...]:
    half = drawing.CALLOUT_GLYPHS[kind] * drawing.GLYPH / 2.0
    half_high = drawing.text_half_high(2)
    return xy[0] - half, xy[0] + half, xy[1] - half_high, xy[1] + half_high


def _leader(
    kind: str, x: float, xy: tuple[float, float]
) -> tuple[tuple[float, float], ...]:
    """Shelf end nearer the hole (the bottom row's baseline) to its centre."""
    left, right, bottom, _top = _callout_block(kind, xy)
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
    leaders = [_leader(kind, x, xy) for kind, x, xy, _side in callouts]
    blocks = [_callout_block(kind, xy) for kind, _x, xy, _side in callouts]
    holes = [(x, drawing.TAP_DRILLS[kind] / 2.0) for kind, x, _xy, _side in callouts]
    width_ext = (
        (spec.BRACKET_LENGTH + 0.5, spec.HALF_WIDTH),
        (
            spec.BRACKET_LENGTH + drawing.SIDE_LANE + drawing.EXT_OVERSHOOT,
            spec.HALF_WIDTH,
        ),
    )
    for i, ((kind, x, xy, side), leader) in enumerate(
        zip(callouts, leaders, strict=True)
    ):
        (sx, sy), _centre = leader
        # The edge pick is the rim on the leader's side, off the centre lines.
        ex, ey, _ez = drawing.tap_edge_model(kind, x, side)
        assert math.hypot(ex - x, ey) == pytest.approx(drawing.TAP_DRILLS[kind] / 2.0)
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
    blocks = [_callout_block(kind, xy) for kind, _x, xy, _side in drawing.TAP_CALLOUTS]
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
            assert (
                right + gap <= l2
                or r2 + gap <= left
                or top + gap <= b2
                or (t2 + gap <= bottom)
            ), i


def test_views_clear_each_other_the_border_and_the_title_block() -> None:
    s = drawing._S / 1000.0
    width_text_right, _ = drawing.plan_sheet(
        _plan("BracketWidth")[0] + drawing.text_half("19.05\nSTOCK"), 0.0
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
    # The lowest plan line (the length's, under four station lanes) stays
    # well above the title block.
    _, length_line = drawing.plan_sheet(
        0.0, drawing.LENGTH_LANE - drawing.EXT_OVERSHOOT
    )
    assert length_line >= TITLE_BLOCK_TOP + 0.025
    plan_right, _ = drawing.plan_sheet(spec.BRACKET_LENGTH, 0.0)
    assert plan_right > TITLE_BLOCK_LEFT  # so the plan must stay above it
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'place_view(adapter, str(SOURCE), "*Right", *END_CENTER' in sheet
    assert "for view in (plan, end, iso):" in sheet


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    row = _config.parts(ARTIFACT)
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", row["number"])
    assert row["number"] == spec.NUMBER == "MHA-CH-006-TL-28"
    assert row["quantity"] == spec.QUANTITY == 2
    assert part.PART_NAME == ARTIFACT == leadscrew.END_BRACKET


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
    assert names == {
        "end bracket",
        "bar tap 1",
        "bar tap 2",
        "KP08 tap 1",
        "KP08 tap 2",
    }
    box = spec.PRECHIPS_SOLIDS[0]
    assert box["size_mm"] == [64.5, 19.05, 12.7]

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
    sizes = {"BracketWidth": spec.BRACKET_WIDTH, "BracketThick": spec.BRACKET_THICK}
    for name, denominator in spec.STOCK_FRACTION_DENOMINATORS.items():
        assert sizes[name] / 25.4 * denominator == pytest.approx(
            round(sizes[name] / 25.4 * denominator)
        )
    # The 13 KP08 foot (UNVERIFIED) overhangs the 12.7 top 0.15 a side.
    assert spec.KP08_FOOT_OVERHANG == pytest.approx(0.15)


def test_kp08_taps_land_on_the_blocks_bolt_spacing_about_the_screw() -> None:
    holes = [_features()[f"kp08_tap_{i}"] for i in (1, 2)]
    laterals = [_lateral(h["at"][0]) for h in holes]
    half = leadscrew.KP08_BOLT_SPACING / 2.0
    assert laterals == pytest.approx(
        [leadscrew.SCREW_LATERAL - half, leadscrew.SCREW_LATERAL + half]
    )
    # The model keeps the vendor's exact millimetres (owner ruling 4, the
    # part's native metric band). The sheet's hole table prints them at the
    # inch .XXX like every row, pending owner confirmation (the native table
    # cannot print a millimetre cell).
    assert spec.KP08_TAP_X == pytest.approx((13.925, 55.925))
    assert all(x == round(x, 3) for x in spec.KP08_TAP_X)
    assert "set_metric_vendor_units(" in Path(part.__file__).read_text(encoding="utf-8")
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "print_imported_metric_dimensions(" not in sheet
    band = printed_band_mm(spec.HOLE_PLACES, unit="in")
    for hole in holes:
        x = hole["at"][0]
        printed = round(x / 25.4, spec.HOLE_PLACES) * 25.4
        assert hole["station"] == pytest.approx([printed - band, printed + band])
    assert all(h["at"][1] == 0.0 for h in holes)  # the row on the screw's KP08_S
    assert spec.KP08_TAP_SPEC.kind == "tapped"  # UNC: the block's holes are plain
    assert spec.KP08_TAP_SPEC.size == leadscrew.KP08_SCREW == "#6-32"
    assert spec.KP08_TAP_SPEC.end == "through_all"
    assert spec.KP08_TAP_DRILL == pytest.approx(2.705)


def test_bar_taps_land_on_the_base_bars_bracket_holes() -> None:
    holes = [_features()[f"bar_tap_{i}"] for i in (1, 2, 3, 4)]
    laterals = [_lateral(h["at"][0]) for h in holes]
    assert laterals == pytest.approx(list(leadscrew.BAR_SCREW_LATERALS))
    # Ruling A′: two pairs symmetric about the screw axis; every station
    # prints as modelled at .XXX.
    assert all(_on_grid(x, spec.HOLE_PLACES) for x in spec.BAR_TAP_X)
    assert spec.BAR_TAP_SPEC.kind == "tapped"
    assert spec.BAR_TAP_SPEC.size == leadscrew.BAR_SCREW == "#8-32"
    assert spec.BAR_TAP_SPEC.end == "through_all"
    # No counterbore in this part: the screws come up through the bar.
    assert not any(kind.startswith("counterbore") for kind in (spec.BAR_TAP_SPEC.kind,))
    # Their threads start on the bar (bottom) face, where the screws enter.
    assert spec.BAR_TAP_FACE == ((0.0, 0.0, -1.0), 0.0)
    assert all(h["at"][2] == 0.0 and h["axis"] == [0.0, 0.0, 1.0] for h in holes)


def test_both_patterns_fit_their_mates_at_three_places() -> None:
    # Each station's band about the row's: the bar taps' .XXX, the KP08
    # taps' exact millimetres at ±0.13.
    band = printed_band_mm(spec.HOLE_PLACES, unit="in")
    assert spec.POSITION_RADIUS >= math.hypot(band, band)
    assert spec.POSITION_RADIUS <= math.hypot(band + 0.0127, band)
    # The uxcell block's listed Ø5 holes about the #6-32's 3.505 major.
    assert spec.KP08_SCREW_FLOAT == pytest.approx(0.7475)
    assert spec.KP08_PATTERN_ALLOWANCE > 0.0
    assert spec.BAR_HOLE_DIA == pytest.approx(4.978)
    assert spec.BAR_PATTERN_ALLOWANCE > 0.0
    stations = {*spec.DRAWING_DIMENSIONS["BarTaps"], *spec.DRAWING_DIMENSIONS["KP08Taps"]}
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == 3 for name in stations)
    assert spec.HOLE_PLACES == 3
    # The table's inch KP08 stations reach a little past the spec's exact
    # ±0.13 mm; both patterns still float clear at the table's limits.
    assert drawing.TABLE_POSITION_RADIUS >= spec.POSITION_RADIUS
    assert drawing.TABLE_POSITION_RADIUS <= math.hypot(band + 0.0127, band)
    assert spec.KP08_SCREW_FLOAT - drawing.TABLE_POSITION_RADIUS > 0.5
    assert spec.BAR_SCREW_FLOAT - drawing.TABLE_POSITION_RADIUS > 0.2
    assert 0.0 < drawing._KP08_EXTRA < 0.01
    # At the title block's two places this part's and TL-20's position
    # radii together would overrun the #8's float.
    two = printed_band_mm(2, unit="in")
    assert 2.0 * math.hypot(two, two) > spec.BAR_SCREW_FLOAT


def test_every_tap_group_names_its_mate_by_drawing_number() -> None:
    # Rule 4 (#2046): each group's mate once, in the table's MATCHES column,
    # by its full registry drawing number; the KP08's code may follow.
    assert drawing.MATE_NUMBERS == {
        "bar": _config.parts("ch-rocker-arm-tl-oblique-base-bar")["number"],
        "kp08": _config.parts("ch-rocker-arm-tl-vn-oblique-pillow-block")["number"],
    }
    assert drawing.MATE_NUMBERS == {"bar": "MHA-CH-06-TL-20", "kp08": "MHA-CH-06-TL-VN-56"}
    for kind, number in drawing.MATE_NUMBERS.items():
        assert drawing.MATE_CELLS[kind].split("\n")[0] == number
    assert drawing.MATE_CELLS["kp08"].split("\n")[1:] == [f"(KP08) {drawing.KP08_NOTE_LINK}"]
    assert drawing.MATE_COLUMN.startswith("MATCHES")
    for name, feature in _features().items():
        if name.startswith(("bar_tap", "kp08_tap")):
            kind = "bar" if name.startswith("bar") else "kp08"
            assert feature["note"] == f"MATCHES HOLES OF {drawing.MATE_NUMBERS[kind]}"
    # No location carries words (rule 7): the plan keeps no station at all.
    assert set(drawing.PLAN_KEEP) == {"BracketLength", "BracketWidth"}
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts(" not in sheet


def test_no_vendor_sku_on_the_sheet() -> None:
    texts = (
        *drawing.MATE_CELLS.values(),
        drawing.MATE_COLUMN,
        drawing.size_text("bar"),
        drawing.size_text("kp08"),
        spec.DRAWING_NOTES,
        drawing.KP08_SPACING_NOTE,
        spec.ISOMETRIC_VIEW_NOTE,
    )
    for text in texts:
        assert not re.search(r"\b\d{4,}[A-Z]\d+\b", text), text  # McMaster style
        assert "AMPEC" not in text.upper()
        assert "UXCELL" not in text.upper()


def test_walls_hold_rule_17_at_worst_case() -> None:
    walls = spec.WALLS_MM
    assert spec.WALL_TARGET == WALL_TARGET_MM
    assert min(walls.values()) >= spec.WALL_TARGET
    # Ruling A′: every tap to its row neighbours and the end taps to the
    # ends, in row order, plus the row to both sides.
    taps = [name for name in walls if "tap" in name]
    assert len(taps) == len(spec.BAR_TAP_X) + len(spec.KP08_TAP_X) + 1
    assert {"row to -Y side", "row to +Y side"} <= set(walls)
    assert spec.RULE_20_SHORTFALLS == ()
    # Cross-check from the exported bands: each thread's major at its station
    # band's far end.
    holes = _features()
    bar_1, kp08_1 = holes["bar_tap_1"], holes["kp08_tap_1"]
    bar_r = THREAD_MAJOR_MM[spec.BAR_SCREW] / 2.0
    kp08_r = THREAD_MAJOR_MM[spec.KP08_THREAD] / 2.0
    assert bar_1["station"][0] - bar_r >= WALL_TARGET_MM
    assert kp08_1["station"][0] - bar_1["station"][1] - bar_r - kp08_r >= WALL_TARGET_MM
    assert bar_1["height"][0] - bar_r >= WALL_TARGET_MM


def test_threads_stop_at_a_full_thread_from_the_screws_faces() -> None:
    # Owner ruling 2026-11-05: the CAD matches the 2026-11-02 hand traveler.
    # Drill THRU; thread .450 MIN from each screw's face.
    assert spec.FULL_THREAD_DEPTH == pytest.approx(0.450 * 25.4)
    assert spec.FULL_THREAD_DEPTH < spec.BRACKET_THICK - spec.THICK_STOCK_BAND
    assert spec.KP08_TAP_FACE == ((0.0, 0.0, 1.0), spec.BRACKET_THICK)
    assert spec.BAR_THREAD_CALLOUT == "MIN FAR SIDE"
    assert spec.KP08_THREAD_CALLOUT == "MIN"
    for thread, reach in spec.SCREW_REACH_MAX.items():
        assert spec.FULL_THREAD_DEPTH >= 1.5 * THREAD_MAJOR_MM[thread]
        assert 1.5 * THREAD_MAJOR_MM[thread] <= reach <= spec.FULL_THREAD_DEPTH
    assert spec.SCREW_REACH_MAX[spec.KP08_THREAD] == pytest.approx(10.875)
    taps = {name: f for name, f in _features().items() if "_tap_" in name}
    assert len(taps) == 6 and all(f["thru"] is True for f in taps.values())
    # Both wizard features take the blind thread after their THRU tap drill.
    builder = Path(part.__file__).read_text(encoding="utf-8")
    for feature in ("BarTaps", "KP08Taps"):
        assert builder.count(f'_thread_from_face(adapter, "{feature}"') == 1
    # The fastener table's receiving thread is the full thread, not the height.
    assert fasteners.BRACKET_TO_BAR.thread_depth_mm == spec.FULL_THREAD_DEPTH
    assert fasteners.KP08_TO_BRACKET.thread_depth_mm == spec.FULL_THREAD_DEPTH
    assert fasteners.BRACKET_TO_BAR.protrusion_mm < 0.0
    assert fasteners.KP08_TO_BRACKET.protrusion_mm < 0.0


def test_holes_carry_the_title_block_band() -> None:
    # The part still bands its KP08 dimensions natively (owner ruling 4); the
    # sheet no longer prints them. (The loop over METRIC_DIMENSIONS reports
    # its source names.)
    assert model_toleranced_dimensions(part) == {
        ("feature_name", "dimension_name"): "band"
    }
    holes = _features()
    # The tap drills print .XXX with the title block's drilled-hole band.
    for name, drill in (
        ("bar_tap_1", spec.BAR_TAP_DRILL),
        ("kp08_tap_1", spec.KP08_TAP_DRILL),
    ):
        low, high = holes[name]["dia"]
        assert low == pytest.approx(round(drill / 25.4, 3) * 25.4)
        assert high - low == pytest.approx(spec.DRILLED_BAND[0])
    band = printed_band_mm(spec.HOLE_PLACES, unit="in")
    for name, width in (
        ("kp08_tap_2", 2.0 * band),
        ("bar_tap_1", 2.0 * band),
    ):
        low, high = holes[name]["station"]
        assert high - low == pytest.approx(width)
    assert holes["bar_tap_1"]["height"] == pytest.approx(
        [spec.HOLE_ROW_Y - band, spec.HOLE_ROW_Y + band]
    )
    assert holes["bar_tap_1"]["height_from"] == "bracket_low_side"


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.PLAN_KEEP) | set(drawing.END_KEEP)
    assert not set(drawing.PLAN_KEEP) & set(drawing.END_KEEP)
    # The hole table prints the stations and the row instead.
    tabled = {
        *spec.DRAWING_DIMENSIONS["BarTaps"],
        *spec.DRAWING_DIMENSIONS["KP08Taps"],
        *spec.DRAWING_DIMENSIONS["HoleRowReference"],
    }
    assert kept | tabled == marked and not kept & tabled
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


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
            for end in band:
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


def test_hole_table_lists_every_tap_once_in_two_size_groups() -> None:
    assert sorted(drawing.TABLE_HOLES) == sorted(
        [("bar", x) for x in spec.BAR_TAP_X] + [("kp08", x) for x in spec.KP08_TAP_X]
    )
    xs = [x for _kind, x in drawing.TABLE_HOLES]
    assert xs == sorted(xs)
    # The origin is the faced inner end and the -Y side face (rule 10): the
    # stations' and the row's own datums.
    assert drawing.TABLE_ORIGIN_MODEL == (0.0, -spec.HALF_WIDTH, spec.BRACKET_THICK)
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "abs(y_mm - HOLE_ROW_Y) > _TABLE_LOCATION_TOLERANCE_MM" in sheet
    assert "basic_locations=False" in sheet  # no datums, no BASIC (rule 5)
    assert "location_places=_PLACES" in sheet


def _rows(*kinds: str) -> list[tuple[int, str, str, float]]:
    stations = {
        kind: iter([x for k, x in drawing.TABLE_HOLES if k == kind]) for kind in ("bar", "kp08")
    }
    counters = {"bar": 0, "kp08": 0}
    letters = {"bar": "A", "kp08": "B"}
    rows = []
    for row, kind in enumerate(kinds, start=1):
        counters[kind] += 1
        rows.append((row, f"{letters[kind]}{counters[kind]}", kind, next(stations[kind])))
    return rows


def test_table_groups_need_one_contiguous_tag_run_per_size() -> None:
    assert drawing.table_groups(_rows("bar", "bar", "bar", "bar", "kp08", "kp08")) == {
        "bar": (1, 4),
        "kp08": (5, 6),
    }
    assert drawing.table_groups(_rows("kp08", "kp08", "bar", "bar", "bar", "bar")) == {
        "kp08": (1, 2),
        "bar": (3, 6),
    }
    with pytest.raises(RuntimeError, match="not one tag run"):
        drawing.table_groups(_rows("bar", "kp08", "bar", "bar", "kp08", "bar"))
    mixed = _rows("bar", "bar", "bar", "bar", "kp08", "kp08")
    mixed[1] = (2, "C1", "bar", mixed[1][3])
    with pytest.raises(RuntimeError, match="not one tag run"):
        drawing.table_groups(mixed)
    with pytest.raises(RuntimeError, match="lacks a tap group"):
        drawing.table_groups(_rows("bar", "bar", "bar", "bar"))


def test_loc_cells_parse_with_any_generated_band_and_bare_where_visible() -> None:
    # The hidden generated X LOC carries the KP08 rows' native band, read back
    # as ".548 ±.005" (review round 1) and ".548±.01" (fix round 2 CAD).
    assert drawing.location_mm(".285", label="x") == pytest.approx(7.239)
    assert drawing.location_mm(".548 ±.005", label="x") == pytest.approx(13.9192)
    assert drawing.location_mm(".548±.01", label="x") == pytest.approx(13.9192)
    assert drawing.location_text("2.202±.005", label="x") == "2.202"
    assert drawing.location_mm(".250", label="y", bare=True) == pytest.approx(6.35)
    with pytest.raises(RuntimeError, match="prints a band"):
        drawing.location_mm(".250 ±.005", label="y", bare=True)
    with pytest.raises(RuntimeError, match="unparseable"):
        drawing.location_mm("13.925 mm", label="x")


def test_x_locs_print_bare_at_the_model_station() -> None:
    # Review round 1: the KP08 rows' ".548 ±.005" restated the title block.
    rows = [(i + 1, tag, kind, x) for i, (tag, (kind, x)) in enumerate(
        zip(("A1", "A2", "A3", "A4", "B1", "B2"), sorted(drawing.TABLE_HOLES))
    )]
    cells = {row: f"{x / 25.4:.3f}".lstrip("0") for row, _t, kind, x in rows}
    for row, _t, kind, _x in rows:
        if kind == "kp08":
            cells[row] += " ±.005"
    texts = drawing.x_loc_texts(rows, cells)
    assert sorted(texts.values()) == sorted([".285", ".942", "1.808", "2.465", ".548", "2.202"])
    cells = {row: cell.replace(" ±.005", "±.01") for row, cell in cells.items()}
    assert drawing.x_loc_texts(rows, cells) == texts
    assert not any("±" in text for text in texts.values())
    with pytest.raises(RuntimeError, match="is not"):
        drawing.x_loc_texts(rows[:1], {1: ".290"})


def test_each_size_prints_once_without_the_title_block_class() -> None:
    assert drawing.size_text("bar") == (
        "<MOD-DIAM>.136 THRU ALL\n8-32 UNC <HOLE-DEPTH>.450 MIN FAR SIDE"
    )
    assert drawing.size_text("kp08") == "<MOD-DIAM>.106 THRU ALL\n6-32 UNC <HOLE-DEPTH>.450 MIN"
    for kind in ("bar", "kp08"):
        text = drawing.size_text(kind)
        assert "2B" not in text and "#" not in text  # rule 2: the THREADS row
        assert len(text.split("\n")) == 2
        # The SIZE drill is the requirement's printed drill.
        feature = _features()[f"{kind}_tap_1"]
        assert f"{feature['nominal_dia'] / 25.4:.3f}".lstrip("0") in text
    assert drawing.THREAD_CALLOUTS == {
        "bar": spec.BAR_THREAD_CALLOUT,
        "kp08": spec.KP08_THREAD_CALLOUT,
    }
    assert drawing._glyphless("Ø.136 THRU ALL\n8-32  UNC ↧.450") == drawing._glyphless(
        "<MOD-DIAM>.136 THRU ALL 8-32 UNC <HOLE-DEPTH>.450"
    )


# --- Sheet layout (model mm in the plan, sheet m around it) -----------------------
GLYPH = 2.75 / 2.0  # one 3.5 mm capital's advance, model mm at 2:1 (c4-r2 readback)
TEXT_HALF_HIGH = 3.5 / 2.0 / 2.0


def test_tags_stand_above_the_plan_each_right_of_its_own_hole() -> None:
    xs = [x for _kind, x in drawing.TABLE_HOLES]
    tag_half = 2 * GLYPH / 2.0
    boxes = [
        (x + drawing.HOLE_TAG_DX - tag_half, x + drawing.HOLE_TAG_DX + tag_half) for x in xs
    ]
    for (left, right), x in zip(boxes, xs):
        assert left > x  # right of its hole: the leader runs down-left to it
    for (_l1, r1), (l2, _r2) in zip(boxes, boxes[1:]):
        assert r1 + 1.0 <= l2  # no two tags touch
    for (_left, right), next_x in zip(boxes, xs[1:]):
        assert right < next_x  # no tag reaches over the next hole's leader
    # Above the +Y side, clear of the centre marks (2.5 sheet mm past each rim).
    radius = max(drawing.TAP_DRILLS.values()) / 2.0
    assert drawing.HOLE_TAG_Y - TEXT_HALF_HIGH >= spec.HALF_WIDTH + 1.0
    assert drawing.HOLE_TAG_Y - TEXT_HALF_HIGH >= radius + 2.5 / drawing._S
    _, top = drawing.plan_sheet(0.0, drawing.HOLE_TAG_Y + TEXT_HALF_HIGH)
    assert top <= TOP_BORDER - 0.01


def test_hole_table_stands_under_the_plan_clear_of_views_and_title_block() -> None:
    x0, y0 = drawing.HOLE_TABLE_ANCHOR
    widths = drawing.HOLE_TABLE_WIDTHS
    # Every visible column; the generated X LOC and SIZE stand hidden.
    assert set(widths) == {0, drawing._X_LOC, drawing.FINISHED_COLUMNS["y"], drawing._SIZE, drawing._MATE}
    assert not set(widths) & set(drawing._HIDDEN)
    assert drawing.FINISHED_COLUMNS["y"] == drawing.NATIVE_COLUMNS["y"] + 1
    assert drawing.FINISHED_COLUMNS["size"] == drawing.NATIVE_COLUMNS["size"] + 1
    assert drawing._X_LOC == drawing.FINISHED_COLUMNS["x"] + 1
    assert (drawing._SIZE, drawing._MATE) == (drawing.FINISHED_COLUMNS["size"] + 1, drawing._SIZE + 1)
    right = x0 + sum(widths.values())
    assert x0 >= 0.020  # clears the sheet audit's 12.7 mm zone margin (pd_platen_guide)
    assert right <= TITLE_BLOCK_LEFT - 0.005
    # Under the length's text (one 3.5 mm row about its keep point).
    _, length_text = drawing.plan_sheet(0.0, drawing.PLAN_KEEP["BracketLength"][1])
    assert y0 <= length_text - 0.00175 - 0.005
    # Header plus six rows at ~6 sheet mm: well above the title block.
    assert y0 - 7 * 0.0065 >= TITLE_BLOCK_TOP + 0.01
    # Every custom cell's widest line fits its column (~2.5 sheet mm a glyph).
    glyph = 0.0025
    for kind in ("bar", "kp08"):
        size = drawing._glyphless(drawing.size_text(kind).split("\n")[1]) + "  "  # the depth symbol
        assert len(size) * glyph <= widths[drawing._SIZE]
        for line in drawing.MATE_CELLS[kind].split("\n"):
            assert len(line) * glyph <= widths[drawing._MATE]
    assert len(drawing.MATE_COLUMN) * glyph <= widths[drawing._MATE]


def test_views_clear_each_other_the_border_and_the_title_block() -> None:
    s = drawing._S / 1000.0
    width_text_right, _ = drawing.plan_sheet(
        drawing.PLAN_KEEP["BracketWidth"][0] + len("STOCK") * GLYPH / 2.0, 0.0
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


def test_sheet_carries_only_the_kp08_spacing_note() -> None:
    assert spec.DRAWING_NOTES == ""
    assert spec.SURFACE_FINISHES == ()
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in source


def test_kp08_spacing_note_is_the_catalogue_spacing_as_a_mm_ref() -> None:
    # Owner ruling 2026-11-06: an inch table plus one note, linked from the
    # KP08 group, giving the catalogue spacing as a millimetre REF.
    assert drawing.KP08_SPACING_MM == pytest.approx(leadscrew.KP08_BOLT_SPACING)
    assert drawing.KP08_SPACING_NOTE == (
        "1. B1 TO B2: 42.00 mm REF, KP08 CATALOGUE SPACING"
    )
    number = drawing.KP08_NOTE_LINK.rsplit(" ", 1)[1]
    assert drawing.KP08_SPACING_NOTE.startswith(f"{number}. B1 TO B2")
    assert drawing.KP08_NOTE_LINK in drawing.MATE_CELLS["kp08"]
    assert drawing.KP08_NOTE_LINK not in drawing.MATE_CELLS["bar"]
    # The B tags' printed span is the catalogue spacing at .XXX.
    b1, b2 = (round(x / 25.4, spec.HOLE_PLACES) for x in spec.KP08_TAP_X)
    assert (b2 - b1) * 25.4 == pytest.approx(42.0, abs=0.13)
    # Right of the table, above the title block, left of and under the iso.
    x, y = drawing.KP08_SPACING_NOTE_XY
    table_right = drawing.HOLE_TABLE_ANCHOR[0] + sum(drawing.HOLE_TABLE_WIDTHS.values())
    assert x >= table_right + 0.01
    assert x + len(drawing.KP08_SPACING_NOTE) * 0.0025 <= drawing.ISO_CENTER[0] - drawing.ISO_HALF[0]
    assert x + len(drawing.KP08_SPACING_NOTE) * 0.0025 <= RIGHT_BORDER - 0.01
    assert y - 0.0042 >= TITLE_BLOCK_TOP + 0.01
    assert y <= drawing.ISO_NOTE_XY[1] - 0.02


def test_prechips_solids_are_valid_fixture_solids() -> None:
    from prechips.model import FixtureSolid

    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    names = {solid["name"] for solid in spec.PRECHIPS_SOLIDS}
    assert names == {
        "end bracket",
        "bar tap 1",
        "bar tap 2",
        "bar tap 3",
        "bar tap 4",
        "KP08 tap 1",
        "KP08 tap 2",
    }
    box = spec.PRECHIPS_SOLIDS[0]
    assert box["size_mm"] == pytest.approx(
        [spec.BRACKET_LENGTH, spec.BRACKET_WIDTH, spec.BRACKET_THICK]
    )

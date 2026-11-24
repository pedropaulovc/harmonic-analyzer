"""Offline contracts for Option B scale placement and the V-engraved numerals."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


import build_ms_stick as builder
import draw_ms_stick as drawing
import ms_stick_callouts as callouts
import ms_stick_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box
from _named_views import octant_axes, octant_view_name

RULED_ISO = octant_view_name(*callouts.RULED_FACE_ISOMETRIC_OCTANT)


def test_numeral_details_ink_clears_border_and_each_other() -> None:
    """Translate r4 native ink/extents, not guessed annotation anchor boxes.

    Evidence: 20261011T045740079Z run's layout-audit/ms-stick.json,
    ENGRAVING Detail F. Retaining scale and relative dimension placement makes
    these measured offsets reusable; acceptance is clearance, not coordinates.
    """
    dx = drawing.NUMERAL_CENTER[0] - 0.140
    dy = drawing.NUMERAL_CENTER[1] - 0.135
    for name, old_xy in (
        ("NumeralXGap", (0.075, 0.170)),
        ("NumeralYGap", (0.075, 0.155)),
    ):
        # A rigid move preserves witness geometry and space between callouts.
        assert math.dist(drawing.NUMERAL_KEEP[name],
                         (old_xy[0] + dx, old_xy[1] + dy)) < 1e-9
    assert drawing.DETAIL_SCALE == (6.0, 1.0)
    # The NUMERAL HEIGHT text sits wholly right of its own extension lines
    # (the r3 review saw them strike through the centred text).
    height_text_left = drawing.NUMERAL_KEEP["NumeralHeight"][0] - len("NUMERAL HEIGHT") * 0.00275 / 2.0
    right_extension = drawing.NUMERAL_CENTER[0] + spec.NUMERAL_HEIGHT_MM * drawing.DETAIL_SCALE[0] / 2000.0
    assert height_text_left - right_extension >= 0.005
    # The label's measured leader/witness start is farther left than PDF ink.
    end_gap_left = drawing.NUMERAL_KEEP["NumeralYGap"][0] - 0.0618528
    assert end_gap_left - 0.0127 >= 0.005
    title_and_scale = Box(
        0.1239223 + dx, 0.0721882 + dy,
        0.1552167 + dx, 0.0887072 + dy,
    )
    # Detail H (the 10) takes the free corner under detail F's dimensions:
    # its fence, and its own title under it, clear of the border and of F.
    radius = drawing.NUMERAL_10_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    cx, cy = drawing.NUMERAL_10_CENTER
    fence = Box(cx - radius, cy - radius, cx + radius, cy + radius)
    assert fence.gap(title_and_scale) >= 0.004
    assert fence.xmin >= 0.0127 + 0.005
    # Room under the fence for DETAIL H and its scale (the F title is 16.5 mm).
    assert fence.ymin - (title_and_scale.ymax - title_and_scale.ymin) >= 0.0127 + 0.002
    text_x, text_y = drawing.NUMERAL_10_KEEP["Numeral10XGap"]
    assert fence.ymax < text_y < drawing.NUMERAL_KEEP["NumeralYGap"][1] - 0.05


def test_numeral_font_note_frees_the_shop_single_stroke_font() -> None:
    """A V bit follows centrelines: the model's strokes are representative."""
    import gen_ms_stick_numerals_dxf as numeral_generator

    assert "NUMERALS: ANY SINGLE-STROKE SANS FONT" in callouts.DRAWING_NOTES.splitlines()[-1]
    assert "SLDPRT" not in callouts.DRAWING_NOTES and "DEJAVU" not in callouts.DRAWING_NOTES
    assert sorted(numeral_generator.DIGIT_STROKES) == [str(digit) for digit in range(10)]
    for strokes in numeral_generator.DIGIT_STROKES.values():
        assert all(len(stroke) >= 2 for stroke in strokes)


def test_dimension_links_name_notes_that_print_on_sheet_one() -> None:
    """Rule 4: each shared mate is named once, in the note its dimensions link."""
    notes = callouts.DRAWING_NOTES.splitlines()
    for number, link in ((callouts.REBATE_NOTE_NUMBER, callouts.REBATE_LINK),
                         (callouts.STATION_NOTE_NUMBER, callouts.STATION_LINK)):
        assert link == f"SEE NOTE {number}"
        assert sum(line.startswith(f"{number}. ") for line in notes) == 1
    linked = {name for name, text in callouts.CALLOUTS.items() if "SEE NOTE" in text}
    assert linked == {"BodyWidth", "BodyThickness"}
    # The station table on sheet 2 links note 2 by sheet.
    assert callouts.STATION_TABLE_TITLE.splitlines()[-1] == callouts.STATION_LINK_FROM_SHEET_2
    assert "MHA-MS-02" in notes[0] and "MHA-CH-01" in notes[1]
    # Rule 7: a note gives the mate, not a method or a coined face name.
    assert notes[1] == "2. SETS MHA-CH-01 AMPLITUDE BAR STATIONS"


def test_current_identity_and_drawing_paths() -> None:
    assert builder.PART_NAME == drawing.PART_STEM == "ms-stick"
    assert DRAWINGS_BY_NAME["ms_stick"].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.name == "ms-stick.SLDDRW"
    assert drawing.PDF.name == "ms-stick.pdf"
    assert drawing.PNG.name == "ms-stick_drawing.png"
    assert [path.name for path in spec.NUMERAL_LAYER_DXFS] == [
        "ms-stick-numerals-1.dxf", "ms-stick-numerals-2.dxf", "ms-stick-numerals-3.dxf",
    ]


def test_inch_grid_blank_and_grooves_keep_the_calibrated_scale() -> None:
    # Issue #290: every printed fabrication size is the exact decimal of its
    # inch print value; scale zero and the configured pitch stay calibrated.
    assert spec.UNIT == "in"
    inch = {
        "BODY_LENGTH": 7.95, "BODY_WIDTH": 0.315, "BODY_THICKNESS": 0.125,
        "TICK_WIDTH": 0.016, "TICK_DEPTH": 0.020, "TICK_LENGTH": 0.12,
        "MINOR_TICK_LENGTH": 0.07, "HALF_TICK_LENGTH": 0.16,
        "NUMERAL_HEIGHT_MM": 0.08, "NUMERAL_GAP_MM": 0.02, "NUMERAL_DEPTH": 0.016,
    }
    for name, value_in in inch.items():
        assert getattr(spec, name) == pytest.approx(value_in * 25.4, rel=0.0, abs=1e-9), name
    assert spec.NUMERAL_ROTATION_DEG == 90
    assert spec.DIVISION_COUNT == 11 and spec.MINOR_PER_DIVISION == 10
    assert spec.SCALE_START_X == pytest.approx(56.5, rel=0.0, abs=1e-9)
    assert spec.SCALE_END_MARGIN == pytest.approx(3.43)
    assert spec.NUMERALS_BBOX == (57.2112, 1.7864, 197.7888, 4.4450)
    assert spec.SCALE_SPAN == pytest.approx(
        (spec.DIVISION_COUNT - 1) * spec.DIVISION_SPACING, rel=0.0, abs=1e-12,
    )
    assert spec.SCALE_START_X + spec.SCALE_SPAN + spec.SCALE_END_MARGIN == pytest.approx(
        spec.BODY_LENGTH, rel=0.0, abs=1e-9,
    )
    for name in ("BODY_LENGTH", "BODY_WIDTH", "BODY_THICKNESS", "SCALE_START_X",
                 "TICK_WIDTH", "TICK_DEPTH", "NUMERAL_LAYER_DXFS"):
        assert getattr(builder, name) == getattr(spec, name)


def test_every_printed_size_is_owned_and_precisioned_by_model() -> None:
    assert builder.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert builder.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP) | set(drawing.DETAIL_KEEP)
            | set(drawing.NUMERAL_KEEP) | set(drawing.NUMERAL_10_KEEP) | set(drawing.DEPTH_KEEP)
            | set(drawing.NUMERAL_DEPTH_KEEP)
            | set().union(*(set(row[4]) for row in drawing.LENGTH_DETAILS)))
    assert kept == marked == set(spec.DRAWING_VALUES_BY_NAME) == set(spec.DRAWING_PRECISION_BY_NAME)
    # Nothing on this part is .X (owner ruling): the overall length, tick
    # lengths and numeral layout print .XX; the bar's section in the stop
    # rebate, the engraving limits and the scale stations print .XXX,
    # except the minor pitch's .XXXX; both pitches print as references.
    assert {name: places for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places != 2} == (
        {**dict.fromkeys(("BodyWidth", "BodyThickness", "Tick0Width", "TickDepth", "NumeralDepth",
                         "Tick10FromEnd", "FullTickPitch"), 3), "MinorTickPitch": 4}
    )
    assert spec.DRAWING_PRECISION_BY_NAME["BodyLength"] == 2
    # No dimension carries its own band: the station table prints +/-.002 for
    # every graduation from one datum; the rest ride the title block.
    assert spec.DRAWING_TOLERANCES == {}
    assert {"BodyThickness", "TickDepth", "FullTickLength", "MinorTickLength",
            "HalfTickLength", "FullTickPitch", "MinorTickPitch", "NumeralHeight",
            "NumeralXGap", "NumeralYGap", "NumeralDepth"} <= marked
    assert drawing.SHEET_NAMES == ("BAR", "GRADUATIONS", "TICK LENGTHS", "ENGRAVING")
    assert drawing.DETAIL_SCALE[0] / drawing.DETAIL_SCALE[1] > drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1]


def test_reference_chords_measure_real_sizes_not_profile_overhangs() -> None:
    assert spec.DRAWING_VALUES_BY_NAME["FullTickLength"] == pytest.approx(
        spec.TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["MinorTickLength"] == pytest.approx(
        spec.MINOR_TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["HalfTickLength"] == pytest.approx(
        spec.HALF_TICK_LENGTH, rel=0.0, abs=1e-12,
    )
    assert spec.DRAWING_VALUES_BY_NAME["MinorTickPitch"] == pytest.approx(
        spec.DIVISION_SPACING / spec.MINOR_PER_DIVISION, rel=0.0, abs=1e-12,
    )
    for _name, start, end in spec.REFERENCE_DIMENSIONS.values():
        assert (start[0] == end[0]) != (start[1] == end[1])
        assert 0.0 <= min(start[0], end[0]) <= max(start[0], end[0]) <= spec.BODY_LENGTH
        assert 0.0 <= min(start[1], end[1]) <= max(start[1], end[1]) <= spec.BODY_WIDTH


def test_scale_has_one_printed_origin_at_the_ten_end_face() -> None:
    """#2434: the end face nearest the 10 bears on the amplitude bar, so the
    graduations run from it; nothing locates a graduation from the 0 end."""
    assert drawing.FRONT_KEEP.keys() == {"BodyLength", "BodyWidth", "Tick10FromEnd"}
    assert "ScaleStartX" not in spec.DRAWING_VALUES_BY_NAME
    assert "ScaleStartReference" not in spec.REFERENCE_DIMENSIONS
    end = spec.REFERENCE_DIMENSIONS["ScaleEndReference"]
    assert end[1] == (spec.SCALE_START_X + spec.SCALE_SPAN, spec.BODY_WIDTH)
    assert end[2] == (spec.BODY_LENGTH, spec.BODY_WIDTH)
    assert spec.DRAWING_VALUES_BY_NAME["Tick10FromEnd"] == pytest.approx(spec.SCALE_END_MARGIN)
    assert spec.inch_text(spec.SCALE_END_MARGIN, 3) == ".135"


def test_last_graduation_is_complete_at_printed_band_extremes() -> None:
    """The station table locates the 10 tick from the end face nearest the 10
    at +/-.002, so the length's band never reaches the land past it; the
    graduation width is a MIN limit, so the land bounds the widest groove
    that still leaves the last graduation whole, at the .080 rule-17 target."""
    values, bands = spec.DRAWING_VALUES_BY_NAME, spec.DRAWING_TOLERANCES
    station_band = spec.GRADUATION_POSITION_TOLERANCE_MM
    assert "BodyLength" not in bands
    assert spec.DRAWING_PRECISION_BY_NAME["BodyLength"] == 2
    assert station_band == pytest.approx(0.0508)
    # Rule 17 at the worst case: the widest stated groove keeps .080+ to the end.
    end_land = values["Tick10FromEnd"] - station_band - spec.GRADUATION_WIDTH_MAX_MM / 2.0
    assert end_land == pytest.approx(3.0744)
    assert end_land >= spec.WALL_TARGET_MM == 2.032
    # The stated .024 MAX keeps neighbours apart on the .0559 minor pitch even
    # with both stations at their band.
    land_min = spec.MINOR_SPACING - 2.0 * spec.GRADUATION_POSITION_TOLERANCE_MM - spec.GRADUATION_WIDTH_MAX_MM
    assert land_min == pytest.approx(0.7088)
    assert callouts.CALLOUTS["Tick0Width"].endswith(spec.GRADUATION_WIDTH_CALLOUT)
    assert values["Tick10FromEnd"] - values["Tick0Width"] / 2.0 == pytest.approx(3.2268)
    # The 0-end land is the rest of the bar: the length's .XX band is far
    # inside it.
    zero_land_min = (values["BodyLength"] - spec.BODY_LENGTH_TOLERANCE_MM
                     - values["Tick10FromEnd"] - station_band
                     - (spec.DIVISION_COUNT - 1) * values["FullTickPitch"] - station_band
                     - spec.GRADUATION_WIDTH_MAX_MM / 2.0)
    assert zero_land_min > 50.0


def test_printed_pitches_agree_across_all_calibrated_subdivisions() -> None:
    """Run 308 FIX: .559 full against .056 minor made ten minor pitches .560.
    As printed, ten minor pitches are one full pitch, and every calibrated
    station stays inside its printed noncumulative +/-.002."""
    full_text = spec.inch_text(spec.DIVISION_SPACING, spec.DRAWING_PRECISION_BY_NAME["FullTickPitch"])
    minor_text = spec.inch_text(spec.MINOR_SPACING, spec.DRAWING_PRECISION_BY_NAME["MinorTickPitch"])
    assert (full_text, minor_text) == (".559", ".0559")
    full, minor = float(full_text), float(minor_text)
    assert spec.MINOR_PER_DIVISION * minor == pytest.approx(full, rel=0.0, abs=1e-12)
    band = spec.GRADUATION_POSITION_TOLERANCE_MM / 25.4
    assert band == pytest.approx(0.002)
    # The calibrated pitch stays exact (owner ruling), never snapped to inch.
    assert (spec.DIVISION_SPACING, spec.MINOR_SPACING) == (14.2, 1.42)
    for index in range((spec.DIVISION_COUNT - 1) * spec.MINOR_PER_DIVISION + 1):
        assert abs(index * spec.MINOR_SPACING / 25.4 - index * minor) <= band, index
    # Rules 10 and 26: the pitches and the 10 tick's land print as
    # references; the station table locates every graduation from one datum,
    # the end face nearest the 10 (#2434), each cell inside its band.
    for name in ("FullTickPitch", "MinorTickPitch", "Tick10FromEnd"):
        assert (callouts.PREFIXES[name], callouts.SUFFIXES[name]) == ("(", ")"), name
    assert not {"FullTickPitch", "MinorTickPitch", "Tick10FromEnd"} & set(callouts.CALLOUTS)
    columns = [column.splitlines() for column in callouts.station_table_columns()]
    assert columns[0] == [callouts.STATION_ROW_HEADING, *(str(n) for n in range(spec.DIVISION_COUNT))]
    assert [column[0] for column in columns[1:]] == [f"+{m}" for m in range(spec.MINOR_PER_DIVISION)]
    cells = {
        numeral * spec.MINOR_PER_DIVISION + minor: text
        for minor, column in enumerate(columns[1:])
        for numeral, text in enumerate(column[1:])
    }
    last = (spec.DIVISION_COUNT - 1) * spec.MINOR_PER_DIVISION
    assert sorted(cells) == list(range(last + 1))
    for index, text in cells.items():
        from_face = spec.BODY_LENGTH - (spec.SCALE_START_X + index * spec.MINOR_SPACING)
        assert abs(from_face / 25.4 - float(text)) <= 0.0005, index
    assert (cells[0], cells[last - spec.MINOR_PER_DIVISION], cells[last]) == ("5.726", ".694", ".135")
    # The 10 tick's row is the same .135 sheet 1 shows as a reference.
    assert cells[last] == spec.inch_text(spec.DRAWING_VALUES_BY_NAME["Tick10FromEnd"], 3)
    assert callouts.STATION_TABLE_TITLE.startswith("GRADUATION STATIONS FROM END FACE NEAREST 10")
    assert "EACH ±.002" in callouts.STATION_TABLE_TITLE


def test_engraving_sizes_are_min_limits_and_graduation_depth_keeps_its_stock() -> None:
    """No mate needs a band on the engraving: width and both depths are
    single MIN limits (model value = printed limit), and the graduation
    depth's ceiling is the stated .080 of stock under it."""
    assert spec.MIN_LIMIT_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.MIN_LIMIT_DEVIATIONS_MM == {
        "Tick0Width": (0.0, spec.TICK_WIDTH),
        "TickDepth": (0.0, spec.TICK_DEPTH),
        "NumeralDepth": (0.0, spec.NUMERAL_DEPTH),
    }
    assert not set(spec.MIN_LIMIT_DEVIATIONS_MM) & set(spec.DRAWING_TOLERANCES)
    values = spec.DRAWING_VALUES_BY_NAME
    assert spec.GRADUATION_FLOOR_MIN_MM == spec.WALL_TARGET_MM
    assert spec.GRADUATION_FLOOR_CALLOUT == "STOCK UNDER GROOVE .080 MIN"
    assert callouts.CALLOUTS["TickDepth"].endswith(spec.GRADUATION_FLOOR_CALLOUT)
    # The V depth states the same stock under it, so it is bounded too.
    assert callouts.CALLOUTS["NumeralDepth"].endswith(spec.NUMERAL_FLOOR_CALLOUT)
    assert spec.NUMERAL_FLOOR_CALLOUT == "STOCK UNDER .080 MIN"
    # The thickness rides the title block's .XXX (+/-.005).
    assert spec.BODY_FIT_TOLERANCE_MM == pytest.approx(0.127)
    depth_max = values["BodyThickness"] - spec.BODY_FIT_TOLERANCE_MM - spec.GRADUATION_FLOOR_MIN_MM
    assert depth_max == pytest.approx(1.016)
    assert values["TickDepth"] == pytest.approx(0.508)
    assert values["TickDepth"] < depth_max and values["NumeralDepth"] < depth_max


def test_finish_preserves_polish_and_black_enamel_engraving_fill() -> None:
    registry = Path(builder.__file__).resolve().parents[1] / "config" / "parts" / "ms-stick.yaml"
    finish = yaml.safe_load(registry.read_text(encoding="utf-8"))["ms-stick"]["finish"]
    assert "polished brass" in finish
    assert "flat black enamel" in finish
    assert "all engraving" in finish
    assert "cured before final polish" in finish


def test_part_names_the_ruled_face_isometric_before_saving() -> None:
    assert RULED_ISO == "ISO REAR-BOTTOM-RIGHT"
    # The octant looks at the -Z ruled face; turned 180 deg on the sheet, model
    # +X runs right and +Y down, as in the turned *Back RULED FACE view.
    sheet_x, sheet_y, toward_viewer = octant_axes(*callouts.RULED_FACE_ISOMETRIC_OCTANT)
    assert toward_viewer[2] < 0
    assert -sheet_x[0] > 0 and -sheet_y[1] < 0


def test_graduation_location_chords_terminate_at_groove_centres() -> None:
    zero = (spec.SCALE_START_X, spec.BODY_WIDTH)
    assert spec.REFERENCE_DIMENSIONS["ScaleEndReference"][1] == (
        spec.SCALE_START_X + spec.SCALE_SPAN, spec.BODY_WIDTH)
    for feature, spacing in (
        ("FullPitchReference", spec.DIVISION_SPACING),
        ("MinorPitchReference", spec.MINOR_SPACING),
    ):
        _, start, end = spec.REFERENCE_DIMENSIONS[feature]
        assert start == zero
        assert end == (spec.SCALE_START_X + spacing, spec.BODY_WIDTH)


def test_numeral_fence_contains_real_full_tick_endpoint() -> None:
    centre = (
        spec.SCALE_START_X + spec.TICK_WIDTH / 2.0
        + spec.NUMERAL_GAP_MM + spec.NUMERAL_HEIGHT_MM / 2.0,
        spec.BODY_WIDTH - spec.TICK_LENGTH - spec.NUMERAL_GAP_MM,
    )
    endpoint = (spec.SCALE_START_X, spec.BODY_WIDTH - spec.TICK_LENGTH)
    assert math.dist(centre, endpoint) < drawing.NUMERAL_RADIUS_MM / 2.0


def test_local_length_fences_include_owned_ticks_without_cross_strip_routing() -> None:
    lengths = {
        "FullTickLength": spec.TICK_LENGTH,
        "MinorTickLength": spec.MINOR_TICK_LENGTH,
        "HalfTickLength": spec.HALF_TICK_LENGTH,
    }
    def outside(centre, radius, x0, x1, y0, y1):
        nearest = (min(max(centre[0], x0), x1), min(max(centre[1], y0), y1))
        return math.dist(centre, nearest) > radius

    def inside(centre, radius, x0, x1, y0, y1):
        return all(math.dist(centre, corner) < radius for corner in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)))

    half = spec.TICK_WIDTH / 2.0
    for label, _parent, detail, model, keep, diameter in drawing.LENGTH_DETAILS:
        name = next(name for name in keep if name in lengths)
        assert keep[name][0] < detail[0] - diameter * drawing.DETAIL_SCALE[0] / 1000.0
        if label != "D":
            assert diameter > math.hypot(half, lengths[name] / 2.0)
            assert model[1] == pytest.approx(spec.BODY_WIDTH - lengths[name] / 2.0)
            continue
        # Exact fence (EXACT_FENCES): sheet radius radius_mm / 2 at the 1:2
        # parent, so the model radius is radius_mm.
        assert label in drawing.EXACT_FENCES
        radius = diameter
        tick = spec.SCALE_START_X + spec.MINOR_SPACING
        edge = spec.BODY_WIDTH
        assert inside(model, radius, tick - half, tick + half, edge - spec.MINOR_TICK_LENGTH, edge)
        assert outside(model, radius, spec.SCALE_START_X - half, spec.SCALE_START_X + half,
                       edge - spec.TICK_LENGTH, edge)  # tick zero stays out
        nxt = spec.SCALE_START_X + 3 * spec.MINOR_SPACING
        assert outside(model, radius, nxt - half, nxt + half, edge - spec.MINOR_TICK_LENGTH, edge)
        assert 2.0 * math.sqrt(radius**2 - (edge - model[1]) ** 2) >= 2.0  # the edge reads as an edge


def test_numeral_v_contract_is_independent_of_graduations() -> None:
    import math as _math

    assert spec.NUMERAL_DEPTH == 0.4064  # .016 MIN
    assert spec.ENGRAVING_V_INCLUDED_ANGLE_DEG == 30.0
    assert spec.NUMERAL_STROKE_WIDTH_MM == 0.24
    # A true V: the 15-degree walls leave under 0.03 mm of root at .016 deep.
    assert spec.NUMERAL_TIP_FLAT_MM == pytest.approx(
        0.24 - 2.0 * 0.4064 * _math.tan(_math.radians(15.0)), abs=1e-12)
    assert 0.0 < spec.NUMERAL_TIP_FLAT_MM < 0.03
    assert spec.NUMERAL_DEPTH < spec.NUMERAL_DEPTH_MAX_MM
    assert spec.DRAWING_DIMENSIONS["Numerals"] == {"NumeralDepth"}
    assert spec.DRAWING_PRECISION["Numerals"] == {"NumeralDepth": 3}
    assert spec.DRAWING_VALUES_BY_NAME["NumeralDepth"] == spec.NUMERAL_DEPTH
    assert (spec.TICK_WIDTH, spec.TICK_DEPTH) == (0.4064, 0.508)
    assert "ALL ENGRAVING" not in callouts.CALLOUTS["TickDepth"]
    assert not hasattr(spec, "NUMERAL_TOOL_NOTE")
    assert not hasattr(drawing, "NUMERAL_TOOL_NOTE_XY")


def test_every_tight_band_states_its_function() -> None:
    """Rule 4: a band tighter than the title block names its mate or purpose;
    the .XXX fit sizes that ride the title block name their mate too. Each
    mate is named once, in the numbered note its dimensions link."""
    assert spec.DRAWING_TOLERANCES == {}
    # The station table's band links the stations' note.
    assert callouts.STATION_LINK in callouts.STATION_TABLE_TITLE
    # The bar's section slides in the stop rebate: the width .XXX (+/-.005)
    # from the title block, the thickness the 1/8 flat's as supplied, printed
    # as a reference over its stock (#2441); each links that fit's note,
    # which gives the acceptance (rule 4: a fit name alone is incomplete).
    for name in ("BodyWidth", "BodyThickness"):
        assert spec.DRAWING_PRECISION_BY_NAME[name] == 3, name
        assert name not in spec.DRAWING_TOLERANCES, name
        assert callouts.CALLOUTS[name].splitlines()[-1] == callouts.REBATE_LINK, name
    assert callouts.CALLOUTS["BodyWidth"] == callouts.REBATE_LINK
    assert (
        callouts.CALLOUTS["BodyThickness"]
        == f"1/8 FLAT AS SUPPLIED\n{callouts.REBATE_LINK}"
    )
    assert spec.BODY_THICKNESS == pytest.approx(25.4 / 8)
    assert (callouts.PREFIXES["BodyThickness"], callouts.SUFFIXES["BodyThickness"]) == (
        "(",
        ")",
    )
    assert "BodyWidth" not in callouts.PREFIXES and "BodyWidth" not in callouts.SUFFIXES
    assert callouts.DRAWING_NOTES.splitlines()[0] == (
        "1. SLIDING FIT IN MHA-MS-02 STOP BLOCK REBATE: STICK SLIDES FULL LENGTH"
    )
    # Rule 7: no callout carries more than two lines of words.
    assert all(len(text.splitlines()) <= 2 for text in callouts.CALLOUTS.values())
    for name in ("BodyLength", "FullTickLength", "MinorTickLength", "HalfTickLength",
                 "NumeralHeight", "NumeralXGap", "NumeralYGap", *spec.MIN_LIMIT_DEVIATIONS_MM):
        assert name not in spec.DRAWING_TOLERANCES, name


def _straight_tick_mm3(length_mm: float) -> float:
    return spec.TICK_WIDTH * length_mm * spec.TICK_DEPTH


def test_tick_v_volume_is_the_inward_drafted_groove() -> None:
    # Midpoint integral of the drafted cross-section, the closed form's own
    # definition, over a fine depth grid.
    slope = math.tan(math.radians(spec.ENGRAVING_V_INCLUDED_ANGLE_DEG / 2.0))
    steps = 4000
    dz = spec.TICK_DEPTH / steps
    for length in (spec.TICK_LENGTH, spec.MINOR_TICK_LENGTH, spec.HALF_TICK_LENGTH):
        numeric = sum(
            (spec.TICK_WIDTH - 2.0 * z * slope) * (length - z * slope) * dz
            for z in ((i + 0.5) * dz for i in range(steps))
        )
        assert spec.tick_v_volume_mm3(length) == pytest.approx(numeric, rel=1e-6)
    assert spec.TICK_TIP_FLAT_MM == pytest.approx(spec.TICK_WIDTH - 2.0 * spec.TICK_DEPTH * slope)
    assert spec.TICK_TIP_FLAT_MM > 0.0
    # 11 full ticks, 90 minor ticks less the one the half tick covers, 1 half.
    assert spec.TICK_VOLUME_MM3 == pytest.approx(
        11 * spec.tick_v_volume_mm3(spec.TICK_LENGTH) + 89 * spec.tick_v_volume_mm3(spec.MINOR_TICK_LENGTH)
        + spec.tick_v_volume_mm3(spec.HALF_TICK_LENGTH)
    )
    # The total gate catches one dropped minor tick; the seed gate cannot
    # mistake a straight-wall cut for the V.
    with pytest.raises(RuntimeError, match="dropped tick"):
        builder._check_engraving_volume(
            "all ticks", spec.TICK_VOLUME_MM3 - spec.tick_v_volume_mm3(spec.MINOR_TICK_LENGTH),
            spec.TICK_VOLUME_MM3, builder.TICK_VOLUME_ALLOWANCE_MM3, "dropped tick",
        )
    seed = spec.tick_v_volume_mm3(spec.TICK_LENGTH)
    assert _straight_tick_mm3(spec.TICK_LENGTH) - seed > builder.TICK_SEED_ALLOWANCE_MM3


def test_listed_engraving_bit_cuts_every_graduation_and_numeral() -> None:
    import _process_plans
    import _shop_equipment

    bit = _shop_equipment.load()["tools"]["ms-stick-engraver"]
    shop = _process_plans.load_shop()
    # One bit cuts both: its V is the model's.
    assert bit["included_angle_deg"] == spec.ENGRAVING_V_INCLUDED_ANGLE_DEG
    assert f"{spec.ENGRAVING_V_INCLUDED_ANGLE_DEG:g}°" in callouts.CALLOUTS["TickDepth"]
    assert f"{spec.ENGRAVING_V_INCLUDED_ANGLE_DEG:g}°" in callouts.CALLOUTS["NumeralDepth"]
    slope = math.tan(math.radians(bit["included_angle_deg"] / 2.0))
    tip = bit["tip_width_in"] * 25.4
    # Plunge depths that cut the printed face-width limits, against the depth
    # MIN and the deepest cut that leaves the stated stock at the thinnest bar.
    depth_for_width_min = (spec.TICK_WIDTH - tip) / (2.0 * slope)
    depth_for_width_max = (spec.GRADUATION_WIDTH_MAX_MM - tip) / (2.0 * slope)
    deepest = spec.BODY_THICKNESS - spec.BODY_FIT_TOLERANCE_MM - spec.GRADUATION_FLOOR_MIN_MM
    shallowest = max(spec.TICK_DEPTH, depth_for_width_min)
    # A window of .010+ for a plunge set on the Z handwheel.
    assert min(deepest, depth_for_width_max) - shallowest >= 0.254
    assert spec.NUMERAL_DEPTH < deepest
    # At the numeral depth MIN the bit's stroke runs wider than the modelled
    # near-sharp V; the excess a side stays inside the .02 numeral gap's .XX
    # band (+/-.01), so the printed gap still holds.
    stroke = tip + 2.0 * spec.NUMERAL_DEPTH * slope
    assert 0.0 < (stroke - spec.NUMERAL_STROKE_WIDTH_MM) / 2.0 < 0.254
    setting = shop["settings"]["ms-stick-engrave-brass"]
    assert setting["tool"] == "ms-stick-engraver" and "ms-stick-engraver" in shop["tools"]
    low, high = shop["machines"]["pm-30mv"]["rpm_ranges"][0]
    assert low <= setting["rpm"] <= high


@pytest.mark.parametrize("removed", [0.0, 2.0 * spec.NUMERAL_VOLUME_MM3])
def test_numeral_volume_gate_refuses_missed_or_square_cuts(removed) -> None:
    allowance = builder.NUMERAL_VOLUME_ALLOWANCE_MM3
    builder._check_numeral_volume("all numerals", spec.NUMERAL_VOLUME_MM3, spec.NUMERAL_VOLUME_MM3, allowance)
    with pytest.raises(RuntimeError, match="V cut removed"):
        builder._check_numeral_volume("all numerals", removed, spec.NUMERAL_VOLUME_MM3, allowance)


@pytest.mark.parametrize("layer", range(len(spec.NUMERAL_LAYER_VOLUMES_MM3)))
def test_numeral_layer_gate_refuses_one_dropped_stroke(layer) -> None:
    expected = spec.NUMERAL_LAYER_VOLUMES_MM3[layer]
    allowance = builder.NUMERAL_LAYER_ALLOWANCES_MM3[layer]
    # Run 20261024T020813087Z-49ce2da4: the seat read each layer within 7e-4.
    builder._check_numeral_volume("layer", expected + 7e-4, expected, allowance)
    builder._check_numeral_volume("layer", expected - 7e-4, expected, allowance)
    with pytest.raises(RuntimeError, match="dropped stroke"):
        builder._check_numeral_volume("layer", expected - spec.NUMERAL_LAYER_MIN_STROKE_MM3[layer], expected, allowance)
    # The aggregate gate is no looser than its tightest layer.
    assert builder.NUMERAL_VOLUME_ALLOWANCE_MM3 <= allowance


class _TextDisplay:
    """Display-dimension fake: one text lane per part, optionally dropping writes."""

    def __init__(self, text: str = "", keeps: bool = True, tol_type: int = spec.MIN_LIMIT_TOL_TYPE):
        self.lanes, self.keeps = {callouts.CALLOUT_BELOW: text}, keeps
        self.dimension = SimpleNamespace(Tolerance=SimpleNamespace(Type=tol_type))

    def SetText(self, lane, text):
        if self.keeps:
            self.lanes[lane] = text

    def GetText(self, lane):
        return self.lanes.get(lane, "")

    def GetDimension2(self, config):
        return self.dimension


def _imported(monkeypatch, displays):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, annotation: annotation.name)
    return [SimpleNamespace(name=name, GetSpecificAnnotation=lambda d=display: d)
            for name, display in displays.items()]


def test_drawing_reads_back_part_callouts_and_min_limit_types(monkeypatch) -> None:
    good = {}
    for lane, texts in callouts.LANES:
        for name, text in texts.items():
            good.setdefault(name, _TextDisplay()).SetText(lane, text.replace("\n", "\r\n"))
    drawing._assert_imported_text_and_limits(None, _imported(monkeypatch, good))
    with pytest.raises(RuntimeError, match="differ from the part"):
        drawing._assert_imported_text_and_limits(
            None, _imported(monkeypatch, {**good, "NumeralXGap": _TextDisplay()}))
    lost = {**good, "TickDepth": _TextDisplay(callouts.CALLOUTS["TickDepth"].rsplit("\n", 1)[0])}
    with pytest.raises(RuntimeError, match="differ from the part"):
        drawing._assert_imported_text_and_limits(None, _imported(monkeypatch, lost))
    retyped = {**good, "NumeralDepth": _TextDisplay(callouts.CALLOUTS["NumeralDepth"], tol_type=0)}
    with pytest.raises(RuntimeError, match="tolerance type"):
        drawing._assert_imported_text_and_limits(None, _imported(monkeypatch, retyped))
    with pytest.raises(RuntimeError, match="missing from the sheet"):
        drawing._assert_imported_text_and_limits(
            None, _imported(monkeypatch, {k: v for k, v in good.items() if k != "BodyWidth"}))


def test_numeral_volume_gate_refuses_a_non_finite_reading() -> None:
    with pytest.raises(RuntimeError, match="V cut removed"):
        builder._check_numeral_volume("layer", math.nan, spec.NUMERAL_LAYER_VOLUMES_MM3[0],
                                      builder.NUMERAL_LAYER_ALLOWANCES_MM3[0])


def test_numeral_profile_scale_makes_the_v_readable_without_crowding() -> None:
    ratio = drawing.NUMERAL_PROFILE_SCALE[0] / drawing.NUMERAL_PROFILE_SCALE[1]
    assert spec.NUMERAL_DEPTH * ratio >= 4.0
    assert spec.NUMERAL_STROKE_WIDTH_MM * ratio >= 2.4
    # The full .315 x .125 bar section reads upright: thickness across, width up.
    half_width = spec.BODY_THICKNESS * ratio / 2000.0
    half_height = spec.BODY_WIDTH * ratio / 2000.0
    x, y = drawing.NUMERAL_PROFILE_CENTER
    profile = Box(x - half_width, y - half_height, x + half_width, y + half_height)
    assert (profile.xmin, profile.ymin, profile.xmax, profile.ymax) == pytest.approx(
        (0.267125, 0.084995, 0.298875, 0.165005),
    )
    numeral_right = drawing.NUMERAL_CENTER[0] + drawing.NUMERAL_RADIUS_MM * drawing.DETAIL_SCALE[0] / 1000.0
    depth_left = drawing.DEPTH_CENTER[0] - drawing.DEPTH_RADIUS_MM * drawing.DEPTH_SCALE[0] / 1000.0
    # The V depth callout (placed by its centre) sits between detail F's circle
    # and the section, its dimension line level with the V grooves.
    depth_x, depth_y = drawing.NUMERAL_DEPTH_KEEP["NumeralDepth"]
    half_text = max(map(len, callouts.CALLOUTS["NumeralDepth"].splitlines())) * 0.00275 / 2.0
    assert numeral_right < depth_x - half_text and depth_x + half_text < profile.xmin - 0.005
    assert profile.ymin < depth_y < profile.ymax
    assert depth_left - profile.xmax > 0.020
    # Detail B's callout block runs right from its keep point (run
    # 20261111T180258983Z-3467590b rendered it 0.378-0.454 m from 0.380), so
    # it must end inside the B-size inner border at x 0.419 m, and its
    # shoulder, about 2.5 line pitches below the keep height, passes above
    # the section.
    tick_x, tick_y = drawing.DEPTH_KEEP["TickDepth"]
    block = max(map(len, callouts.CALLOUTS["TickDepth"].splitlines())) * 0.00275
    assert tick_x + block < 0.419 - 0.005
    assert tick_y - 2.5 * 0.0034 > profile.ymax + 0.008
    # The cutting line misses every graduation by a visible margin and still
    # crosses the zero's straight side strokes, short of its end facets.
    minor = spec.SCALE_START_X + spec.MINOR_SPACING
    assert drawing.NUMERAL_SECTION_X - (minor + spec.TICK_WIDTH / 2.0) > 0.3
    zero_start = spec.SCALE_START_X + spec.TICK_WIDTH / 2.0 + spec.NUMERAL_GAP_MM
    assert drawing.NUMERAL_SECTION_X < zero_start + 0.84 * spec.NUMERAL_HEIGHT_MM


def test_the_stick_is_a_feature_export_part_with_one_owner_per_face() -> None:
    import export_features
    from _gtol_face import FaceGeometry

    manifest = export_features.requirement_manifest("ms_stick")
    features = manifest["features"]
    assert {name: feature["kind"] for name, feature in features.items()} == {
        **dict.fromkeys(
            ("datum_end", "zero_end", "plain_edge", "ruled_edge", "ruled_face", "back_face"),
            "face",
        ),
        "graduations": "notch",
        "numerals": "profile",
    }
    assert manifest["notes"]["manufacturing"] == callouts.DRAWING_NOTES.splitlines()

    def plane(normal: tuple[float, float, float], offset: float) -> FaceGeometry:
        point = tuple(value * offset / 1000 for value in normal)
        return FaceGeometry(None, 4001, (*normal, *point), normal, ())

    expected = {
        "datum_end": plane((1.0, 0.0, 0.0), spec.BODY_LENGTH),
        "zero_end": plane((-1.0, 0.0, 0.0), 0.0),
        "plain_edge": plane((0.0, -1.0, 0.0), 0.0),
        "ruled_edge": plane((0.0, 1.0, 0.0), spec.BODY_WIDTH),
        "ruled_face": plane((0.0, 0.0, -1.0), 0.0),
        "back_face": plane((0.0, 0.0, 1.0), spec.BODY_THICKNESS),
        # Every tick floor lies at the tick depth, every stroke floor at the
        # numeral depth: one selector each claims them all.
        "graduations": plane((0.0, 0.0, -1.0), -spec.TICK_DEPTH),
        "numerals": plane((0.0, 0.0, -1.0), -spec.NUMERAL_DEPTH),
    }
    selectors = export_features.feature_selectors("ms_stick")
    assert set(selectors) == set(features)
    for name, face in expected.items():
        owners = [
            owner
            for owner, specs in selectors.items()
            if any(selector.matches(face) for selector in specs)
        ]
        assert owners == [name], name


def test_stick_feature_bands_are_the_printed_ones() -> None:
    import export_features

    inch = 25.4
    features = export_features.requirement_manifest("ms_stick")["features"]
    assert features["zero_end"]["length"] == pytest.approx([7.94 * inch, 7.96 * inch])
    assert features["ruled_edge"]["width"] == pytest.approx([0.310 * inch, 0.320 * inch], abs=1e-3)
    assert features["back_face"]["thickness"] == pytest.approx([0.120 * inch, 0.130 * inch], abs=1e-3)
    ticks = features["graduations"]
    assert ticks["count"] == 101
    assert ticks["width"] == pytest.approx([0.016 * inch, 0.024 * inch], abs=1e-4)
    assert ticks["depth_min"] == pytest.approx(0.020 * inch)
    # The station table's first row, 5.726 +/-.002 from the end nearest the 10.
    assert ticks["zero_station"] == pytest.approx([5.724 * inch, 5.728 * inch], abs=1e-4)
    assert ticks["zero_station_from"] == "datum_end"
    last = ticks["zero_station_nominal"] - (ticks["count"] - 1) * ticks["minor_pitch"]
    assert last == pytest.approx(ticks["ten_station_ref"])
    assert round(last / inch, 3) == 0.135
    assert features["numerals"]["depth_min"] == pytest.approx(0.016 * inch)
    assert features["numerals"]["height"] == pytest.approx([0.07 * inch, 0.09 * inch])

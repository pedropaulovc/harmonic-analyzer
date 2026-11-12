"""Offline contracts for the keyed tooth-cutting arbor (MHA-DT-03-TL-03)."""

from __future__ import annotations

import math
import sys

import pytest

import _buildgraph as bg
import _config
import build_dt_cone_gear_tl_keyed_arbor as part
import cone_land_key
import draw_dt_cone_gear_tl_keyed_arbor as drawing
import dt_cone_gear_tl_keyed_arbor_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_FLOOR_MM
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import angular_band_deg, printed_band_mm

INCH = 25.4
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
KIT = "dt_cone_gear_tl_arbor"


def test_registry_row_is_tooling_in_inch_inside_its_kit_only() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-03"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME["dt_cone_gear_tl_keyed_arbor"]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    stem = "dt_cone_gear_tl_keyed_arbor"
    assert bg.is_shop_fixture(stem)
    assert stem in bg.references_of(KIT)
    for machine in bg.MACHINE_ASSEMBLIES:
        assert stem not in bg.references_of(machine)


def test_the_arbor_serves_every_keyed_cone_and_the_64t() -> None:
    import dt_cone_gear_spec as cone
    import dt_crank_drive_gear_spec as crank

    tags = [blank.tag for blank in spec.KEYED_GEARS]
    assert tags == [f"T{t:03d}" for t in cone.KEYED_TEETH] + [f"{crank.TEETH}T"]


def test_every_blank_slides_on_and_its_play_keeps_inside_the_tir_share() -> None:
    seat_max = spec.SEAT_DIA + spec.SEAT_DIA_BAND[0]
    seat_min = spec.SEAT_DIA + spec.SEAT_DIA_BAND[1]
    assert seat_min < seat_max
    for blank in spec.KEYED_GEARS:
        assert blank.bore[0] >= seat_max - 1e-9, blank.tag
        play = blank.bore[1] - seat_min
        assert play <= spec.PLAY_SHARE * spec.TOOTH_RUNOUT_TIR_MM + 1e-9, blank.tag
    assert spec.PLAY_SHARE < 1.0
    assert spec.SEAT_RUNOUT_ALLOWANCE_MM > 0.0


def test_the_blank_stands_clear_of_the_jaws_and_the_seat_ends_inside_it() -> None:
    assert spec.STANDOFF - XX >= 0.75 * INCH - 1e-9
    for blank in spec.KEYED_GEARS:
        assert spec.SEAT_LENGTH + XX < blank.face[0], blank.tag
        assert spec.PILOT_END - XX > blank.face[1], blank.tag


def test_every_blank_is_backed_under_its_root_by_the_largest_clear_collar() -> None:
    """The cutter runs out past both faces: the shoulder and the collar stand
    under the root by the air at every limit, and each setup takes the largest
    collar that does."""
    floating = (spec.COLLAR_BORE + spec._DRILL_PLUS - (spec.PILOT_DIA - XXX)) / 2.0
    reach = [d / 2.0 + XX + floating for d in spec.COLLAR_DIAS]
    shoulder = spec.STANDOFF_DIA / 2.0 + XX
    for blank in spec.KEYED_GEARS:
        limit = blank.root_min_dia / 2.0 - spec.AIR_MIN
        index = spec.COLLAR_BY_GEAR[blank.tag]
        assert reach[index] <= limit, blank.tag
        assert shoulder <= limit, blank.tag
        if index + 1 < len(reach):
            assert reach[index + 1] > limit, blank.tag
        share = spec.COLLAR_DIAS[index] / blank.root_min_dia
        assert share >= spec.BACKING_SHARE_MIN, blank.tag
    assert set(spec.COLLAR_BY_GEAR.values()) == set(range(len(spec.COLLAR_DIAS)))


def test_the_nut_clamps_on_full_thread_with_thread_to_spare() -> None:
    pitch = INCH / 28.0
    smallest_root = min(blank.root_min_dia for blank in spec.KEYED_GEARS)
    corners = spec.NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
    assert corners / 2.0 + spec.AIR_MIN <= smallest_root / 2.0
    assert spec.NUT_ACROSS_FLATS > spec.COLLAR_BORE + spec._DRILL_PLUS
    thinnest = min(blank.face[0] for blank in spec.KEYED_GEARS)
    thickest = max(blank.face[1] for blank in spec.KEYED_GEARS)
    nearest_collar_face = thinnest + spec.COLLAR_LENGTH - XX
    farthest_collar_face = thickest + spec.COLLAR_LENGTH + XX
    assert nearest_collar_face - (spec.RELIEF_END + XX) > 2.0 * pitch
    assert spec.PILOT_END + XX < nearest_collar_face
    past = (spec.ARBOR_END - 2.0 * XX) - (farthest_collar_face + spec.NUT_THICKNESS_MAX)
    assert past >= 1.5 * pitch
    assert spec.RELIEF_DIA + XX < spec.THREAD_ROOT_MIN
    assert (spec.RELIEF_END - XX) - (spec.PILOT_END + XX) >= pitch


def test_both_centres_hold_their_walls() -> None:
    assert spec.HEAD_CENTRE_DIA + XX <= 0.125 * INCH + 1e-9
    wall = (spec.THREAD_ROOT_MIN - (spec.TAIL_CENTRE_DIA + XXX)) / 2.0
    assert wall >= WALL_FLOOR_MM
    assert spec.TAIL_CENTRE_DIA - XXX > spec.CENTRE_PILOT_MAX


def test_the_key_carries_the_clock_and_lies_under_every_blank() -> None:
    play = math.degrees(
        cone_land_key.KEYWAY_SIDE_CLEARANCE_MM[1] / 2.0 / (spec.BORE_MIN_MM / 2.0)
    )
    assert play < angular_band_deg(unit="in")
    far_end = spec.KEY_END_SET + XX + spec.KEY_LENGTH + XX
    assert far_end <= spec.SEAT_LENGTH - XX + 1e-9
    assert far_end < min(blank.face[0] for blank in spec.KEYED_GEARS)
    # The keyseat's straight run passes out over the pilot, under its floor.
    assert spec.KEYSEAT_FLOOR_MIN > (spec.PILOT_DIA + XXX) / 2.0
    assert spec.KEYSEAT_WIDTH == cone_land_key.KEYSEAT_WIDTH_MM
    assert spec.KEYSEAT_S == cone_land_key.KEYSEAT_S_MM


def test_the_stations_and_volume_close_on_the_sections() -> None:
    lengths = [
        (spec.GRIP_DIA, spec.GRIP_LENGTH),
        (spec.STANDOFF_DIA, spec.STANDOFF),
        (spec.SEAT_DIA, spec.SEAT_LENGTH),
        (spec.PILOT_DIA, spec.PILOT_END - spec.SEAT_LENGTH),
        (spec.RELIEF_DIA, spec.RELIEF_END - spec.PILOT_END),
        (spec.THREAD_MAJOR, spec.ARBOR_END - spec.RELIEF_END),
    ]
    assert sum(length for _dia, length in lengths) == pytest.approx(spec.OVERALL_LENGTH)
    turned = sum(math.pi / 4.0 * dia**2 * length for dia, length in lengths)
    assert spec.TURNED_VOLUME == pytest.approx(turned, rel=1e-9)
    assert 0.0 < spec.FINISHED_VOLUME < spec.TURNED_VOLUME
    names = {name for name, *_rest in spec.SECTIONS}
    assert names == set(spec.SECTION_DIMENSIONS)


def test_the_tight_bands_live_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part)
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    for (feature, name), band in spec.MODEL_BANDS_MM.items():
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert band[1] < band[0]
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DRAWING_VALUES_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    assert len(spec.SHEET_NOTES.splitlines()) <= 4


def _fake_projection(_adapter, _view, points_m, label, names):
    """The side view at 3:1, the axis horizontal, head right, model +Y up."""
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    half = spec.OVERALL_LENGTH / 2000.0
    cx, cy = drawing.SIDE_CENTER
    return [(cx + (half - z) * scale, cy + y * scale) for _x, y, z in points_m]


def test_the_side_view_places_every_marked_dimension_off_the_part(
    monkeypatch,
) -> None:
    monkeypatch.setattr(drawing, "model_points_in_view", _fake_projection)
    keep = drawing._side_keep(None, None)
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    in_section = spec.DRAWING_DIMENSIONS[spec.KEYSEAT_SKETCH]
    assert set(keep) == marked - in_section
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    top = drawing.SIDE_CENTER[1] + spec.GRIP_DIA / 1000.0 / 2.0 * scale
    bottom = drawing.SIDE_CENTER[1] - spec.GRIP_DIA / 1000.0 / 2.0 * scale
    for name, (_x, y) in keep.items():
        assert not bottom < y < top, name
    positions = list(keep.values())
    assert len(set(positions)) == len(positions)
    # Lengths that share a tier must not overlap along the axis.
    by_tier: dict[int, list[tuple[float, float]]] = {}
    for a, b, tier in drawing.LENGTH_SPANS_Z.values():
        by_tier.setdefault(tier, []).append((a, b))
    for spans in by_tier.values():
        spans.sort()
        for (_a0, b0), (a1, _b1) in zip(spans, spans[1:], strict=False):
            assert a1 >= b0 - 1e-9


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "dt-cone-gear"])
    with pytest.raises(SystemExit):
        drawing._parse_args()

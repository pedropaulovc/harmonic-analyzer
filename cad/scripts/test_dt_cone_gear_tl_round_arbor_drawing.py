"""Offline contracts for the round tooth-cutting arbor (MHA-DT-03-TL-07)."""

from __future__ import annotations

import math
import sys

import pytest

import _buildgraph as bg
import _config
import build_dt_cone_gear_tl_round_arbor as part
import draw_dt_cone_gear_tl_round_arbor as drawing
import dt_cone_gear_tl_round_arbor_spec as spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_FLOOR_MM
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
XX = printed_band_mm(2, unit="in")
XXX = printed_band_mm(3, unit="in")
STEM = "dt_cone_gear_tl_round_arbor"
OWNER_RULING = (
    "Option 2. #8-32 end, Ø.38 collar, purchased #8-32 nut under the root, no "
    "tail centre; the overhung compliance (1.85-2.59x the 64T setup, estimated "
    "0.65-1.3x its deflection at the lighter 48 DP cut) is accepted."
)


def test_registry_row_is_standalone_tooling_in_inch() -> None:
    """A shop tool with no kit assembly (owner ruling 2026-11-17, #2885):
    in no assembly at all, machine or fixture."""
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-03-TL-07"
    assert row["title"] == "Round Cutting Arbor"
    assert row["drawing_unit"] == "in"
    assert int(row["quantity"]) == 1
    entry = DRAWINGS_BY_NAME[STEM]
    assert entry.artifact_stem == spec.PART_NAME == part.PART_NAME
    assert entry.layout is DrawingLayout.LANDSCAPE
    assert entry.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert bg.is_shop_fixture(STEM)
    assert STEM in bg.part_stems()
    for assembly in bg.ASSEMBLY_ORDER:
        assert STEM not in bg.references_of(assembly), assembly


def test_the_spec_quotes_the_owner_ruling() -> None:
    assert OWNER_RULING in " ".join(spec.__doc__.split())


def test_the_arbor_carries_t024_alone_on_its_round_bore() -> None:
    import dt_cone_gear_spec as cone

    assert spec.TEETH == 24
    assert 24 not in cone.KEYED_TEETH and 24 in cone.ROUND_BORE_TEETH
    assert spec.BLANKS == (spec.BLANK,)
    assert spec.BLANK.tag == "T024"
    assert spec.BLANK.number == "MHA-DT-03-T024"
    assert spec.BORE_MIN_MM == pytest.approx(0.2510 * INCH)
    assert spec.BORE_MAX_MM == pytest.approx(0.2518 * INCH)
    assert spec.FACE_MIN_MM == pytest.approx(cone.FACE_WIDTH - 0.002 * INCH)
    assert spec.FACE_MAX_MM == pytest.approx(cone.FACE_WIDTH + 0.002 * INCH)
    assert spec.ROOT_MIN_MM == pytest.approx(0.4478 * INCH)


def test_the_rules_are_the_keyed_arbors() -> None:
    """Restated, not imported (the keyed kit stays out of this recipe's
    closure); each must still equal the keyed arbor's."""
    import dt_cone_gear_tl_keyed_arbor_spec as keyed

    for name in (
        "AIR_MIN",
        "BACKING_SHARE_MIN",
        "PLAY_SHARE",
        "CHUCK_STANDOFF_MIN",
        "SHOULDER_R",
        "SHOULDER_R_TOL_TYPE",
        "SHOULDER_R_SUFFIX",
        "GRIP_DIA",
        "GRIP_LENGTH",
        "STOCK_DIA",
        "SEAT_PLACES",
        "SEAT_LENGTH",
        "SEAT_NOTE_FLAG",
        "NOTE_LINE_CHARS",
        "ISOMETRIC_VIEW_NOTE",
    ):
        assert getattr(spec, name) == getattr(keyed, name), name
    assert spec._PAIR == keyed._PAIR
    assert spec.TOOTH_RUNOUT_TIR_MM >= keyed.TOOTH_RUNOUT_TIR_MM
    assert spec.SEAT_CLEARANCE_MM == keyed.SEAT_CLEARANCE_MM


def test_the_seat_fits_t024_inside_the_tir_share() -> None:
    """The seat is a matched sliding fit: line to line with the bore's low
    limit (it prints Ø.251 at .XXX) and never more play than the share in
    the largest bore."""
    low, high = spec.SEAT_CLEARANCE_MM
    assert low == 0.0
    assert high == pytest.approx(0.001 * INCH)
    assert high <= spec.PLAY_SHARE * spec.TOOTH_RUNOUT_TIR_MM + 1e-9
    assert spec.SEAT_DIA == spec.BORE_MIN_MM
    assert spec.SEAT_DIA_MIN == pytest.approx(0.2508 * INCH)
    assert spec.SEAT_DIA_MIN <= spec.SEAT_DIA
    assert spec.BLANK.bore[0] - spec.SEAT_DIA >= low - 1e-9
    assert spec.BLANK.bore[1] - spec.SEAT_DIA_MIN <= high + 1e-9
    assert spec.SEAT_RUNOUT_ALLOWANCE_MM > 0.0
    assert spec.DRAWING_PRECISION_BY_NAME["SeatDia"] == 3
    assert spec.CALLOUTS_BELOW["SeatDia"] == spec.SEAT_NOTE_FLAG == "SEE NOTE 1"
    assert spec.CALLOUTS_BELOW["ShoulderR"] == spec.SEAT_NOTE_FLAG
    assert spec.SHOULDER_R == pytest.approx(0.004 * INCH)


def test_the_note_names_t024_by_its_full_number() -> None:
    """Rule 4's matched pair: the mate by name and full drawing number; rule
    7's four lines, each inside the 72 characters before the title block."""
    note = " ".join(spec.SHEET_NOTES.split())
    assert note == (
        "1. SEAT: SLIDING FIT, MATCHED TO THE BORE OF CONE GEAR MHA-DT-03-T024, "
        "CLEARANCE .000-.001."
    )
    assert len(spec.SHEET_NOTES.splitlines()) <= 4
    assert max(map(len, spec.SHEET_NOTES.splitlines())) <= 72
    # The pilot only carries the loose collar: a clearance size at .XXX,
    # never a fit name; the collar by its short form, as the keyed sheet.
    pilot = spec.CALLOUTS_BELOW["PilotDia"]
    assert pilot == "CLEARS TL-08"
    assert "FIT" not in pilot
    assert spec.CALLOUTS_BELOW["GripDia"] == "STOCK OK"
    assert spec.THREAD_CALLOUT == "#8-32 UNC"
    assert spec.DIMENSION_TEXT == {"ThreadDia": "#8-32 UNC"}


def test_the_blank_stands_clear_of_the_jaws_and_the_seat_ends_inside_it() -> None:
    """Every station is from the grip's end face, so a length between two of
    them holds twice the .XX band; .77 is the .75 floor plus that pair."""
    assert spec.STANDOFF == pytest.approx(0.77 * INCH)
    assert spec.STANDOFF - 2.0 * XX == pytest.approx(0.75 * INCH)
    assert spec.SEAT_LENGTH + 2.0 * XX < spec.BLANK.face[0]
    assert spec.PILOT_END - 2.0 * XX > spec.BLANK.face[1]
    assert spec.SHOULDER_REACH == pytest.approx((0.20 + 0.01) * INCH)


def test_the_shoulder_collar_and_nut_stand_under_t024s_root() -> None:
    """The cutter runs out past both faces: the shoulder, the collar (with
    its float on the pilot) and the nut's corners stand under the root by
    the air at every limit; the collar backs over half the root."""
    limit = spec.BLANK.root_min_dia / 2.0 - spec.AIR_MIN
    assert spec.STANDOFF_DIA / 2.0 + XX <= limit
    floating = (
        spec.COLLAR_BORE + drilled_oversize_mm(unit="in") - (spec.PILOT_DIA - XXX)
    ) / 2.0
    assert spec.COLLAR_FLOAT == pytest.approx(floating)
    assert spec.COLLAR_FLOAT == pytest.approx(0.0085 * INCH)
    assert spec.COLLAR_REACH == pytest.approx(0.2085 * INCH)
    assert spec.COLLAR_DIA / 2.0 + XX + floating <= limit
    assert spec.COLLAR_DIA / spec.BLANK.root_min_dia >= spec.BACKING_SHARE_MIN
    corners = spec.NUT_ACROSS_FLATS / math.cos(math.radians(30.0))
    assert corners / 2.0 + spec.AIR_MIN <= spec.BLANK.root_min_dia / 2.0
    assert spec.NUT_ROOT_AIR == pytest.approx(0.0254 * INCH, abs=0.0001 * INCH)
    assert spec.ROOT_AIR >= spec.AIR_MIN - 1e-9


def test_the_collar_slides_on_the_pilot_and_the_blank_passes_over_it() -> None:
    """Pilot Ø.220 at .XXX (.215-.225) under the #1-drilled collar (.228)."""
    assert spec.PILOT_DIA == pytest.approx(0.220 * INCH)
    assert spec.PILOT_DIA + XXX < spec.BORE_MIN_MM
    assert spec.COLLAR_BORE - (spec.PILOT_DIA + XXX) > 0.0
    assert spec.PILOT_DIA - XXX > spec.THREAD_MAJOR_MAX + 0.005 * INCH
    assert spec.COLLAR_BORE > spec.THREAD_MAJOR
    assert spec.NUT_ACROSS_FLATS > spec.COLLAR_BORE + drilled_oversize_mm(unit="in")
    assert spec.DRAWING_PRECISION_BY_NAME["PilotDia"] == 3
    wall = (
        (spec.COLLAR_DIA - XX) - (spec.COLLAR_BORE + drilled_oversize_mm(unit="in"))
    ) / 2.0
    assert wall == pytest.approx(spec.COLLAR_WALL_MIN)
    assert wall >= WALL_FLOOR_MM


def test_the_nut_clamps_on_full_thread_with_thread_to_spare() -> None:
    pitch = INCH / 32.0
    # ASME B18.6.3 #8 hex machine screw nut: H max .130, over the 1/8 nominal.
    assert spec.NUT_THICKNESS_MAX == pytest.approx(0.130 * INCH)
    assert spec.ARBOR_END == pytest.approx(0.81 * INCH)
    nearest_collar_face = spec.BLANK.face[0] + spec.COLLAR_LENGTH - XX
    farthest_collar_face = spec.BLANK.face[1] + spec.COLLAR_LENGTH + XX
    past = (spec.ARBOR_END - 2.0 * XX) - (farthest_collar_face + spec.NUT_THICKNESS_MAX)
    assert past >= 1.5 * pitch
    assert past == pytest.approx(spec.THREAD_PAST_NUT_MIN)
    assert past == pytest.approx(0.0546 * INCH, abs=0.0001 * INCH)
    assert nearest_collar_face - (spec.RELIEF_END + 2.0 * XX) > 2.0 * pitch
    assert spec.PILOT_END + 2.0 * XX < nearest_collar_face
    assert (spec.PILOT_END - 2.0 * XX) - spec.BLANK.face[1] >= 0.10 * INCH
    assert spec.PILOT_ENGAGEMENT_MIN == pytest.approx(0.10458 * INCH, abs=1e-4)


def test_the_relief_is_a_pitch_wide_and_under_the_b1_1_root() -> None:
    """ASME B1.1 #8-32 UNC-2A major .1631/.1571; the UNR root stands
    1.22687 p under the major. The relief prints Ø.112 at .XXX (.107-.117)."""
    pitch = INCH / 32.0
    assert spec.THREAD_PITCH == pytest.approx(pitch)
    assert spec.THREAD_MAJOR_MAX == pytest.approx(0.1631 * INCH)
    assert spec.THREAD_MAJOR_MIN == pytest.approx(0.1571 * INCH)
    root = 0.1571 * INCH - 1.22687 * pitch
    assert spec.THREAD_ROOT_MIN == pytest.approx(root)
    assert spec.RELIEF_DIA == pytest.approx(0.112 * INCH)
    assert spec.DRAWING_PRECISION_BY_NAME["ReliefDia"] == 3
    assert spec.RELIEF_DIA + XXX < root
    assert (spec.RELIEF_END - XX) - (spec.PILOT_END + XX) >= pitch
    # Its third place is its function: Ø.11 at .XX reaches .12, over the root.
    assert 0.12 * INCH > root
    assert spec.CALLOUTS_BELOW["ReliefDia"] == "UNDER THREAD ROOT"


def test_the_relief_keeps_the_keyed_arbors_share_of_the_stress_area() -> None:
    """ASME B1.1 tensile stress areas: #8-32 UNC .0140 in², 1/4-28 UNF
    .0364 in². The keyed arbor's relief Ø.18 at .XX leaves Ø.17 MIN; the
    round arbor's least relief section keeps at least that share."""
    keyed_share = math.pi / 4.0 * 0.17**2 / 0.0364
    assert spec.RELIEF_AREA_SHARE_MIN == pytest.approx(keyed_share, abs=1e-4)
    least = math.pi / 4.0 * (spec.RELIEF_DIA - XXX) ** 2
    assert least == pytest.approx(spec.RELIEF_AREA_MIN_MM2)
    assert spec.THREAD_STRESS_AREA_MM2 == pytest.approx(0.0140 * INCH**2)
    share = least / spec.THREAD_STRESS_AREA_MM2
    assert share >= keyed_share
    assert share == pytest.approx(0.642, abs=1e-3)


def test_no_centre_hole_and_no_keyseat() -> None:
    """No tail centre (owner ruling): the #8-32 root's own radius is under
    rule 17's .060 floor; the round bore takes no key."""
    assert spec.THREAD_ROOT_MIN / 2.0 < WALL_FLOOR_MM
    names = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert not any("Centre" in name or "Keyseat" in name for name in names)
    assert not any("Centre" in name or "Keyseat" in name for name in spec.GLOBALS)
    # The seat's fit is note 1's: no band rides a model dimension.
    assert model_toleranced_dimensions(part) == {}


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
    assert spec.OVERALL_LENGTH == pytest.approx(2.33 * INCH)
    turned = sum(math.pi / 4.0 * dia**2 * length for dia, length in lengths)
    assert spec.TURNED_VOLUME == pytest.approx(turned, rel=1e-9)
    assert spec.FINISHED_VOLUME == spec.TURNED_VOLUME
    names = {name for name, *_rest in spec.SECTIONS}
    assert names == set(spec.SECTION_DIMENSIONS)


def test_every_printed_length_is_a_baseline_from_the_grip_end() -> None:
    """Rule 10/11: one datum, the grip's end face; the overall (a hidden
    reference sketch's one dimension) ties the thread's end; the thread's
    own length is left off the sheet."""
    printed = {
        name
        for names in spec.DRAWING_DIMENSIONS.values()
        for name in names
        if name in spec.LENGTH_DRIVES or name == "Overall"
    }
    assert printed == {*spec.SHEET_LENGTHS, "Overall"}
    assert spec.DRAWING_DIMENSIONS[spec.OVERALL_SKETCH] == {"Overall"}
    assert "ThreadLength" not in printed
    stations = {
        "GripLength": spec.GRIP_LENGTH,
        "Shoulder": spec.SHOULDER_Z,
        "SeatEnd": spec.SEAT_END_Z,
        "PilotEnd": spec.PILOT_END_Z,
        "ReliefEnd": spec.RELIEF_END_Z,
        "Overall": spec.OVERALL_LENGTH,
    }
    for name, value in stations.items():
        assert spec.DRAWING_VALUES_BY_NAME[name] == pytest.approx(value), name
        a, b, _tier = drawing.LENGTH_SPANS_Z[name]
        assert a == 0.0 and b == pytest.approx(value), name
    starts = {name: start for name, _dia, start, _end in spec.SECTIONS}
    assert all(starts[s] == 0.0 for s in ("Standoff", "Seat", "Pilot", "Relief"))


def test_every_marked_dimension_is_placed_with_places_and_value() -> None:
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DRAWING_VALUES_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    assert set(spec.DIMENSION_TEXT) <= marked
    placed = {*drawing.DIA_TEXT, *drawing.LENGTH_SPANS_Z, "ShoulderR"}
    assert placed == marked
    assert spec.SHEET_NOTES.startswith(f"{spec.SEAT_NOTE_NUMBER}. SEAT:")
    for callout in spec.CALLOUTS_BELOW.values():
        assert len(callout.splitlines()) <= 2


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "dt-cone-gear"])
    with pytest.raises(SystemExit):
        drawing._parse_args()

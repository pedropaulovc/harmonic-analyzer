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


def test_one_seat_fits_every_blank_inside_the_tir_share() -> None:
    """The seat is a matched sliding fit: line to line with the smallest bore
    (it prints the supply size at .XXX) and never more play than the share
    in the largest, so one seat serves every keyed bore."""
    low, high = spec.SEAT_CLEARANCE_MM
    assert low == 0.0
    assert high <= spec.PLAY_SHARE * spec.TOOTH_RUNOUT_TIR_MM + 1e-9
    assert spec.SEAT_DIA == spec.BORE_MIN_MM
    assert spec.SEAT_DIA_MIN <= spec.SEAT_DIA
    for blank in spec.KEYED_GEARS:
        assert blank.bore[0] - spec.SEAT_DIA >= low - 1e-9, blank.tag
        assert blank.bore[1] - spec.SEAT_DIA_MIN <= high + 1e-9, blank.tag
    assert spec.PLAY_SHARE < 1.0
    assert spec.SEAT_RUNOUT_ALLOWANCE_MM > 0.0
    assert spec.DRAWING_PRECISION_BY_NAME["SeatDia"] == 3
    assert ("SeatProfile", "SeatDia") not in spec.MODEL_BANDS_MM
    assert spec.CALLOUTS_BELOW["SeatDia"] == spec.SEAT_NOTE_FLAG
    assert (
        "MATCHED" in spec.SHEET_NOTES and ".0000-.0013 IN EACH BORE" in spec.SHEET_NOTES
    )


def test_the_note_names_every_mate_by_its_drawing_number() -> None:
    """Rule 4's matched pair: both mate drawings by name and full number in
    note 1 (no range, no pointer to the kit sheet's list): the cone gear's
    tabulated drawing, whose keyed members are every cone blank on the kit's
    setup table, and the crank drive gear; the key's bond named; rule 7's
    four lines, each inside the 72 characters before the title block."""
    import dt_cone_gear_spec as cone
    import dt_cone_gear_tl_arbor_assembly_spec as kit

    note = " ".join(spec.SHEET_NOTES.split())
    assert "LISTED ON" not in note and " TO MHA-" not in note
    assert (
        "MATCHED TO THE KEYED BORES OF CONE GEAR MHA-DT-03 AND CRANK DRIVE GEAR "
        "MHA-DT-07, CLEARANCE .0000-.0013 IN EACH BORE;"
    ) in note
    assert spec.CONE_NUMBER == _config.parts("dt-cone-gear")["number"] == "MHA-DT-03"
    assert spec.CRANK_NUMBER == _config.parts("dt-crank-drive-gear")["number"]
    assert set(cone.ROUND_BORE_TEETH).isdisjoint(cone.KEYED_TEETH)
    for blank in spec.KEYED_GEARS:
        assert blank.number.startswith(f"{spec.CONE_NUMBER}-T") or (
            blank.number == spec.CRANK_NUMBER
        ), blank.tag
        assert blank.number in (row[0] for row in kit.SETUP_TABLE_ROWS), blank.tag
    assert (
        f"KEY {spec.KEY_NUMBER} SLIDES IN, BONDED WITH {spec.KEY_BOND}, CLEARANCE .000-.004."
    ) in note
    assert f"COAT ITEM 5 WITH {spec.KEY_BOND}." in kit.ASSEMBLY_STEPS
    assert len(spec.SHEET_NOTES.splitlines()) <= 4
    assert max(map(len, spec.SHEET_NOTES.splitlines())) <= 72
    # The pilot only carries the loose collars: a clearance size at the title
    # block's .XXX band, never a fit name.
    pilot = spec.CALLOUTS_BELOW["PilotDia"]
    assert pilot == "CLEARS TL-04"
    assert "FIT" not in pilot
    assert spec.COLLAR_BORE - (spec.PILOT_DIA + XXX) > 0.0  # a clearance
    # The shoulder root prints the repo's MAX form and links the seat's note,
    # which names the bores that seat on the shoulder.
    assert spec.SHOULDER_R_TOL_TYPE == 0 and spec.SHOULDER_R_SUFFIX == " MAX"
    assert spec.CALLOUTS_BELOW["ShoulderR"] == spec.SEAT_NOTE_FLAG
    assert spec.THREAD_CALLOUT == "1/4-28 UNF"


def test_no_two_place_pilot_clears_the_collar_bore_and_backs_t030() -> None:
    """The pilot keeps .XXX: either .XX grid neighbour of Ø.275 fails at the
    title block's limits. Ø.28 meets the Ø.290 drilled bore line to line and
    its keyseat run-out cuts it; Ø.27 floats the Ø.50 collar over T030's root.
    """
    assert spec.DRAWING_PRECISION_BY_NAME["PilotDia"] == 3
    t030 = spec.KEYED_GEARS[0]
    assert t030.tag == "T030"
    for nominal in (0.27 * INCH, 0.28 * INCH):
        bore_clears = spec.COLLAR_BORE - (nominal + XX) > 1e-9
        under_floor = spec.KEYSEAT_FLOOR_MIN - (nominal + XX) / 2.0 > 0.0
        floating = (spec.COLLAR_BORE + spec._DRILL_PLUS - (nominal - XX)) / 2.0
        reach = spec.COLLAR_DIAS[0] / 2.0 + XX + floating
        backs_t030 = reach <= t030.root_min_dia / 2.0 - spec.AIR_MIN
        assert not (bore_clears and under_floor and backs_t030), nominal


def test_the_blank_stands_clear_of_the_jaws_and_the_seat_ends_inside_it() -> None:
    """Every station is from the grip's end face, so a length between two of
    them holds twice the .XX band."""
    assert spec.STANDOFF - 2.0 * XX >= 0.75 * INCH - 1e-9
    for blank in spec.KEYED_GEARS:
        assert spec.SEAT_LENGTH + 2.0 * XX < blank.face[0], blank.tag
        assert spec.PILOT_END - 2.0 * XX > blank.face[1], blank.tag


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
    past = (spec.ARBOR_END - 2.0 * XX) - (farthest_collar_face + spec.NUT_THICKNESS_MAX)
    assert past >= 1.5 * pitch
    assert nearest_collar_face - (spec.RELIEF_END + 2.0 * XX) > 2.0 * pitch
    assert spec.PILOT_END + 2.0 * XX < nearest_collar_face
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
    assert far_end <= spec.SEAT_LENGTH - 2.0 * XX + 1e-9
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


def test_every_printed_length_is_a_baseline_from_the_grip_end() -> None:
    """Rule 10/11: one datum, the grip's end face; the overall ties the
    thread's end; the thread's own length is left off the sheet."""
    printed = {
        name
        for names in spec.DRAWING_DIMENSIONS.values()
        for name in names
        if name in spec.LENGTH_DRIVES or name == "CentreOverall"
    }
    assert printed == {*spec.SHEET_LENGTHS, "CentreOverall"}
    assert "ThreadLength" not in printed
    stations = {
        "GripLength": spec.GRIP_LENGTH,
        "Shoulder": spec.SHOULDER_Z,
        "SeatEnd": spec.SEAT_END_Z,
        "PilotEnd": spec.PILOT_END_Z,
        "ReliefEnd": spec.RELIEF_END_Z,
        "CentreOverall": spec.OVERALL_LENGTH,
    }
    for name, value in stations.items():
        assert spec.DRAWING_VALUES_BY_NAME[name] == pytest.approx(value), name
        a, b, _tier = drawing.LENGTH_SPANS_Z[name]
        assert a == 0.0 and b == pytest.approx(value), name
    starts = {name: start for name, _dia, start, _end in spec.SECTIONS}
    assert all(starts[s] == 0.0 for s in ("Standoff", "Seat", "Pilot", "Relief"))


def test_the_tight_bands_live_on_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part)
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    for (feature, name), band in spec.MODEL_BANDS_MM.items():
        assert name in spec.DRAWING_DIMENSIONS[feature]
        assert band[1] < band[0]
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(spec.DRAWING_VALUES_BY_NAME) == marked
    assert set(spec.CALLOUTS_BELOW) <= marked
    # The keyseat width is a reference: no band on the model, parenthesized;
    # S keeps its band (necessity register N-02).
    assert set(spec.MODEL_BANDS_MM) == {(spec.KEYSEAT_SKETCH, "KeyseatS")}
    assert (
        spec.DIMENSION_PREFIXES["KeyseatWidth"],
        spec.DIMENSION_SUFFIXES["KeyseatWidth"],
    ) == ("(", ")")
    assert spec.SHEET_NOTES.startswith(f"{spec.SEAT_NOTE_NUMBER}. SEAT:")
    for callout in spec.CALLOUTS_BELOW.values():
        assert len(callout.splitlines()) <= 2


def test_the_cli_takes_its_own_stem(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["draw", spec.PART_NAME])
    assert drawing._parse_args().part == spec.PART_NAME
    monkeypatch.setattr(sys, "argv", ["draw", "dt-cone-gear"])
    with pytest.raises(SystemExit):
        drawing._parse_args()

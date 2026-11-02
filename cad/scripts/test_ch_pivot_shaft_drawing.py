"""Offline contracts for the pivot-shaft (MHA-CH-05) drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import _fit_deviations
import _fit_shaft_h
import build_ch_pivot_shaft as part
import draw_ch_pivot_shaft as drawing
import ch_pivot_bracket_spec
import ch_pivot_shaft_spec as spec
import rocker_bank_layout as bank
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-pivot-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["ch_pivot_shaft"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_lands_on_the_side_view_or_its_detail() -> None:
    """drawing-guidelines.md rule 11 (turned parts read like the lathe): a turned part's diameters and lengths sit on the side
    view (or DETAIL A, a 5:1 detail of it), and all of them are authored on
    Right-plane sketches: the half-profile, the flats' cut and the caps."""
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PROFILE_KEEP) | set(drawing.DETAIL_KEEP) == marked
    assert not set(drawing.PROFILE_KEEP) & set(drawing.DETAIL_KEEP)
    assert marked == {
        "ShaftDia",
        "DomeHeight",
        "Radius",
        "OverallLength",
        "FlatLength",
        "FlatAF",
        "FlatStation",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    # The profile, the flats and the caps.
    assert source.count('create_sketch("Right")') == 3
    assert "create_revolve(" in source


def test_only_the_running_fit_carries_a_size_band() -> None:
    assert spec.SHAFT_DIA_BAND is _fit_shaft_h.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_runs_in_the_bracket_bores() -> None:
    lower, upper = _fit_deviations.deviations(spec.SHAFT_DIA_BAND)
    clearance_min = ch_pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + upper)
    clearance_max = ch_pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + lower)
    assert round(clearance_min, 2) == 0.15
    assert clearance_max > clearance_min


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 4,
        "DomeHeight": 2,
        "Radius": 2,
        "OverallLength": 2,
        "FlatLength": 2,
        "FlatAF": 2,
        "FlatStation": 2,
    }
    assert "draw_ch_pivot_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    digits = spec.DRAWING_PRECISION_BY_NAME["ShaftDia"]
    printed = float(f"{spec.SHAFT_DIA:.{digits}f}")
    assert abs(printed - spec.SHAFT_DIA) <= math.ulp(spec.SHAFT_DIA)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "assert_imported_precision(" in source


def test_a_shaft_carries_no_gdt() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T): shafts carry no frames and no datums (and the old end
    faces are domes now)."""
    for attribute in (
        "PART_DATUMS",
        "GEOMETRIC_CONTROLS",
        "END_VIEW_NOTE",
        "LENGTH_TOLERANCE_MM",
        "SHAFT_LENGTH",
    ):
        assert not hasattr(spec, attribute)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" not in source


def test_the_overall_length_runs_tip_to_tip_and_nothing_is_cut_to_fit() -> None:
    """Baseline machinist review (rule 25): "SUPPLY 175 LONG, PLAIN END
    UNCUT" contradicted the domed ends. The part is finished on the print:
    the overall length runs tip to tip, from the faces the shop makes."""
    assert part.SHAFT_LENGTH == bank.PIVOT_SHAFT_LENGTH
    for gone in ("LENGTH_CALLOUT", "STOCK_LENGTH"):
        assert not hasattr(spec, gone)
    assert "UNCUT" not in spec.DRAWING_NOTES and "SUPPLY" not in spec.DRAWING_NOTES
    assert "OverallLength" in drawing.PROFILE_KEEP
    assert "OverallLength" in spec.DRAWING_DIMENSIONS["FlatProfile"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'dims.record("OverallLength", \'"ShaftLength" + 2 * "DomeHeight"\')' in source
    assert 'dims.record("NorthTip", \'"DomeHeight"\')' in source
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension" not in sheet


def test_both_ends_are_domed_and_the_height_is_model_owned() -> None:
    assert spec.DRAWING_DIMENSIONS["NorthCapProfile"] == {"DomeHeight", "Radius"}
    assert spec.DOME_CALLOUT == "BOTH ENDS"
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '_dome(adapter, "North", 0.0, -1.0)' in source
    assert '_dome(adapter, "South", SHAFT_LENGTH, 1.0)' in source
    assert spec.DOME_SPHERE_RADIUS > spec.SHAFT_DIA / 2


def test_notes_are_short_specific_facts_with_no_dimension_in_them() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 0 < len(lines) <= 4
    for line in lines:
        assert line == line.upper()
        assert not re.search(r"\d+\.\d|±|\+/-", line)
    assert "BOTH FLATS IN LINE, ONE SIDE." in lines
    assert "STEPS" not in spec.DRAWING_NOTES


def test_the_isometric_note_states_the_only_off_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    ratio = re.search(r"(\d+)\s*:\s*(\d+)", spec.ISOMETRIC_VIEW_NOTE)
    assert ratio is not None
    assert (int(ratio.group(1)), int(ratio.group(2))) == drawing.ISO_SCALE


def test_part_stamps_make_critical_properties() -> None:
    config = _config.parts("ch-pivot-shaft")
    assert config["number"] == "MHA-CH-05"
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_surface_finishes_name_the_running_face() -> None:
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"pivot_bearing"}
    face = by_key["pivot_bearing"].face
    assert by_key["pivot_bearing"].roughness_um == 1.6
    assert face.diameter_mm == spec.SHAFT_DIA
    # Part frame: the north end at z 0, the body toward -z. The probe station
    # is on the O.D., off both flats at their longest.
    z = -face.contains_z_mm
    assert 0.0 < z < bank.PIVOT_SHAFT_LENGTH
    half = spec.FLAT_LENGTH_RANGE[1] / 2.0
    for station in bank.PIVOT_SHAFT_FLAT_STATIONS:
        assert not station - half <= z <= station + half
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert 'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bearing")' in sheet_source
    assert "roughness_ra=" not in sheet_source


def test_the_flats_sit_at_the_layout_stations() -> None:
    """Each flat's centre is its ear's mid-plane (the layout's stations, from
    the north cylinder end), and each is DIMENSIONED from its own end's tip:
    the bar is the same either way round."""
    assert spec.NORTH_FLAT_STATION == ch_pivot_bracket_spec.EAR_T / 2.0
    assert spec.FLAT_TIP_STATION == spec.NORTH_FLAT_STATION + spec.DOME_HEIGHT
    assert part.FLAT_STATIONS == pytest.approx(bank.PIVOT_SHAFT_FLAT_STATIONS, abs=1e-9)
    assert part.FLAT_STATIONS[0] == pytest.approx(
        part.SHAFT_LENGTH - spec.NORTH_FLAT_STATION
    )
    # The south flat is as far from the south tip as the north one from the
    # north tip.
    assert bank.PIVOT_SHAFT_OVERALL_LENGTH - spec.DOME_HEIGHT - part.FLAT_STATIONS[0] == (
        pytest.approx(spec.FLAT_TIP_STATION)
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'tip = f"{axis}.start" if north else f"{axis}.end"' in source
    assert 'set_global(adapter, "FlatStation"' in source
    assert drawing.FLAT_STATION_CALLOUT == spec.FLAT_STATION_CALLOUT == "BOTH ENDS"


def test_the_cup_seats_on_the_flat_at_its_shallowest() -> None:
    assert spec.SET_SCREW_CUP_DIA == ch_pivot_bracket_spec.SET_SCREW_POINT_DIA
    assert spec.FLAT_AF == pytest.approx(spec.SHAFT_DIA - spec.FLAT_DEPTH)
    assert spec.FLAT_DEPTH_RANGE == pytest.approx(
        (spec.FLAT_DEPTH - spec.LINEAR_2PL, spec.FLAT_DEPTH + spec.LINEAR_2PL)
    )
    # The chord at the shallowest printed depth takes the cup with 0.5 each
    # side; the deepest flat still leaves most of the round.
    assert spec.flat_chord(spec.FLAT_DEPTH_RANGE[0]) >= spec.SET_SCREW_CUP_DIA + 1.0
    assert spec.FLAT_DEPTH_RANGE[1] < spec.SHAFT_DIA / 4.0


def test_the_layout_checks_the_flat_at_its_printed_limits() -> None:
    """rocker_bank_layout's worst cases read FLAT_LENGTH_RANGE,
    FLAT_STATION_BAND and LENGTH_BAND; they must be the limits the sheet
    prints (and the feature export carries), so a precision change cannot
    leave the layout proving a band the machinist never sees (Astra on
    #1344)."""
    from _printed_tolerance import printed_deviations

    def limits(model: float, places: int) -> tuple[float, float]:
        lower, upper = printed_deviations(model, places, unit=spec.UNIT)
        return model + lower, model + upper

    p = spec.DRAWING_PRECISION_BY_NAME
    assert list(spec.FLAT_LENGTH_RANGE) == pytest.approx(limits(spec.FLAT_LENGTH, p["FlatLength"]))
    low, high = limits(spec.FLAT_TIP_STATION, p["FlatStation"])
    assert (high - low) / 2 == pytest.approx(spec.FLAT_STATION_BAND)
    low, high = limits(bank.PIVOT_SHAFT_OVERALL_LENGTH, p["OverallLength"])
    assert (high - low) / 2 == pytest.approx(spec.LENGTH_BAND)
    low, high = limits(spec.FLAT_AF, p["FlatAF"])
    assert (high - low) / 2 == pytest.approx(spec.FLAT_DEPTH_RANGE[1] - spec.FLAT_DEPTH)


def test_each_flat_stays_inside_its_ear() -> None:
    """At its longest, each flat stays inside its ear's thickness, so no hub
    or the spring runs over a flat's edge."""
    ear = ch_pivot_bracket_spec.EAR_T
    half = spec.FLAT_LENGTH_RANGE[1] / 2.0
    south, north = bank.PIVOT_SHAFT_FLAT_STATIONS
    assert 0.0 < north - half and north + half < ear
    length = bank.PIVOT_SHAFT_LENGTH
    assert length - ear < south - half and south + half < length


def test_flat_volume_is_two_segments() -> None:
    radius = spec.SHAFT_DIA / 2.0
    half_angle = math.acos((radius - spec.FLAT_DEPTH) / radius)
    segment = radius**2 * (half_angle - math.sin(half_angle) * math.cos(half_angle))
    assert spec.segment_area(spec.FLAT_DEPTH) == pytest.approx(segment)
    assert spec.V_FLAT == pytest.approx(segment * spec.FLAT_LENGTH)
    source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "volume-2.0*V_FLAT" in source


def test_the_flats_print_once_as_two_places() -> None:
    assert drawing.FLATS_CALLOUT == "2X"
    source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert (
        '"FlatLength":FLATS_CALLOUT,"FlatAF":FLATS_CALLOUT,'
        '"FlatStation":FLAT_STATION_CALLOUT,"DomeHeight":DOME_CALLOUT'
    ) in source


def test_the_running_fit_names_its_mate_clear_of_its_witnesses() -> None:
    """Baseline machinist review: the Ø6.350 0/-0.02 band named no mate
    (rule 4), and inside its witness pair the lower extension line ran
    through its text (rule 14). The callout names the hubs it runs in, and
    the text stands under the bar's lower flank, right of the south tip."""
    arm = _config.parts("ch-rocker-arm")["number"]
    assert drawing.SHAFT_FIT_CALLOUT == f"RUNNING FIT IN\n{arm} HUBS"
    source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert '{"ShaftDia":SHAFT_FIT_CALLOUT}' in source
    x, y = drawing.PROFILE_KEEP["ShaftDia"]
    lower_flank = drawing.PROFILE_CENTER[1] - spec.SHAFT_DIA * drawing._MM / 2.0
    assert y < lower_flank - 0.005
    south_tip = drawing.SOUTH_END_X + spec.DOME_HEIGHT * drawing._MM
    assert x - PROFILE_DIA_CALLOUT_HALF_WIDTH > south_tip


def test_finishes_print_at_note_height() -> None:
    """r743-2R: at the template's default height the Ra symbols printed
    ~18 mm tall."""
    assert drawing.FINISH_CHAR_HEIGHT == 0.0025
    source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    assert source.count("char_height=FINISH_CHAR_HEIGHT") == len(spec.SURFACE_FINISHES)


# Measured on the r743-3 render: "BOTH ENDS" runs 24.5 mm, centred on its
# dimension text; the value above it is shorter.
DOME_CALLOUT_HALF_WIDTH = 0.01225
# Witness lines are hairlines; the text must clear them by a visible gap.
CALLOUT_WITNESS_CLEARANCE = 0.002


def _stands_outside(text_x: float, half_width: float, witnesses: tuple) -> bool:
    left, right = text_x - half_width, text_x + half_width
    return (
        right + CALLOUT_WITNESS_CLEARANCE <= min(witnesses)
        or left - CALLOUT_WITNESS_CLEARANCE >= max(witnesses)
    )


def test_dome_height_callout_stands_outside_its_witness_pair() -> None:
    """r743-3 eye pass: centred on its 1.5 mm span, "1.5 BOTH ENDS" was
    crossed by both witness lines. In DETAIL A it ends left of the dome tip
    (now ".06 BOTH ENDS")."""
    witnesses = (
        drawing._detail_x(spec.DOME_HEIGHT),  # dome tip
        drawing._detail_x(0.0),  # shaft end
    )
    text_x, _ = drawing.DETAIL_KEEP["DomeHeight"]
    assert _stands_outside(text_x, DOME_CALLOUT_HALF_WIDTH, witnesses)
    assert text_x < min(witnesses)


def test_the_dome_radius_prints_as_a_spherical_reference() -> None:
    """PR #1317 machinist review: the dome height alone left the crown's
    profile open. The model's sphere radius prints as (SR.16), read-only."""
    assert spec.DRAWING_PRECISION["NorthCapProfile"]["Radius"] == 2
    assert f"{spec.DOME_SPHERE_RADIUS / 25.4:.2f}" == "0.16"
    assert "Radius" in drawing.DETAIL_KEEP
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_set_spherical_reference(adapter, radius_annotations[0]" in source


# The ASME B inner border's right edge, and the half-width of the profile's
# diameter callout: its widest line is the mate's.
INNER_BORDER_RIGHT = 0.419
PROFILE_DIA_CALLOUT_HALF_WIDTH = len(
    f"{_config.parts('ch-rocker-arm')['number']} HUBS"
) * drawing.CALLOUT_CHAR_WIDTH / 2.0


def test_detail_a_takes_the_north_flat_and_dome_clear_of_the_profile() -> None:
    """PR #1317 eye pass: at 1:1 the flat's dimensions crammed the north end,
    text on the witnesses and against the dome. A 5:1 detail carries them."""
    assert drawing.DETAIL_SCALE == (5, 1)
    tip = drawing._detail_x(spec.DOME_HEIGHT)
    far = drawing._detail_x(-(spec.NORTH_FLAT_STATION + spec.FLAT_LENGTH / 2.0))
    left = drawing.DETAIL_CENTER[0] - drawing._DETAIL_FENCE_R
    right = drawing.DETAIL_CENTER[0] + drawing._DETAIL_FENCE_R
    assert left < tip < far < right
    radius_x, _ = drawing.DETAIL_KEEP["Radius"]
    dia_x, _ = drawing.PROFILE_KEEP["ShaftDia"]
    assert radius_x - 0.010 > dia_x + PROFILE_DIA_CALLOUT_HALF_WIDTH
    af_x, _ = drawing.DETAIL_KEEP["FlatAF"]
    assert right < af_x < INNER_BORDER_RIGHT - 0.015
    # The isometric moved under the profile to make room: right of the notes,
    # left of the title block.
    assert 0.105 < drawing.ISO_NOTE_XY[0] < drawing.ISO_CENTER[0] < 0.216


def test_detail_a_texts_stand_clear_of_their_witnesses() -> None:
    """cd4151166 render: centred on its span, the station sat on the flat's
    near witness, and the circle's letter sat on the bar. The station now
    runs from the dome tip, with its BOTH ENDS callout under the value."""
    tip = drawing._detail_x(spec.DOME_HEIGHT)
    station_x, _ = drawing.DETAIL_KEEP["FlatStation"]
    half = len(spec.FLAT_STATION_CALLOUT) * drawing.CALLOUT_CHAR_WIDTH / 2.0
    assert station_x + half + CALLOUT_WITNESS_CLEARANCE <= tip
    # The (SR4.1) callout is a row lower, so the two cannot meet.
    assert drawing.DETAIL_KEEP["Radius"][1] < drawing.DETAIL_KEEP["FlatStation"][1] - 0.010
    letter_x, letter_y = drawing.DETAIL_LETTER_XY
    circle_left = drawing.NORTH_END_X - (
        drawing.DETAIL_FENCE_Z_MM + drawing.DETAIL_RADIUS_MM
    ) * drawing._MM
    assert letter_x + 0.0065 < circle_left
    assert letter_y - 0.0065 > drawing.SHAFT_FLANK_Y

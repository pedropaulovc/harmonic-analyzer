"""Offline contracts for the pivot-shaft (MHA-CH-005) drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import _fit_limits
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


def test_every_marked_dimension_lands_on_the_side_view() -> None:
    """Policy rule 7: a turned part's diameters and lengths sit on the side
    view, and all of them are authored on Right-plane sketches: the
    half-profile, the flats' cut and the caps."""
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PROFILE_KEEP) == marked
    assert marked == {
        "ShaftDia",
        "ShaftLength",
        "DomeHeight",
        "FlatLength",
        "FlatAF",
        "NorthFlatStation",
        "SouthFlatStation",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    # The profile, the flats and the caps.
    assert source.count('create_sketch("Right")') == 3
    assert "create_revolve(" in source


def test_only_the_running_fit_carries_a_size_band() -> None:
    assert spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_runs_in_the_bracket_bores() -> None:
    lower, upper = _fit_limits.deviations(spec.SHAFT_DIA_BAND)
    clearance_min = ch_pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + upper)
    clearance_max = ch_pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + lower)
    assert round(clearance_min, 2) == 0.15
    assert clearance_max > clearance_min


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 3,
        "ShaftLength": 1,
        "DomeHeight": 1,
        "FlatLength": 1,
        "FlatAF": 3,
        "NorthFlatStation": 2,
        "SouthFlatStation": 2,
    }
    assert "draw_ch_pivot_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    digits = spec.DRAWING_PRECISION_BY_NAME["ShaftDia"]
    printed = float(f"{spec.SHAFT_DIA:.{digits}f}")
    assert abs(printed - spec.SHAFT_DIA) <= math.ulp(spec.SHAFT_DIA)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "assert_imported_precision(" in source


def test_a_shaft_carries_no_gdt() -> None:
    """Policy rule 3: shafts carry no frames and no datums (and the old end
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


def test_the_length_is_a_cut_to_fit_reference() -> None:
    assert part.SHAFT_LENGTH == bank.PIVOT_SHAFT_LENGTH
    assert spec.LENGTH_CALLOUT == "CUT TO FIT: SPAN OVER BOTH MHA-CH-008 EARS"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension(adapter, length_annotations[0]" in source
    assert '{"ShaftLength": LENGTH_CALLOUT}' in source
    assert spec.STOCK_LENGTH > bank.PIVOT_SHAFT_OVERALL_LENGTH + 10


def test_both_ends_are_domed_and_the_height_is_model_owned() -> None:
    assert spec.DRAWING_DIMENSIONS["NorthCapProfile"] == {"DomeHeight"}
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
    assert config["number"] == "MHA-CH-005"
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
    """Each flat's centre is its ear's mid-plane, from the north end: the
    north one by its own global, the south one driven off the length."""
    assert spec.NORTH_FLAT_STATION == ch_pivot_bracket_spec.EAR_T / 2.0
    assert part.FLAT_STATIONS == pytest.approx(bank.PIVOT_SHAFT_FLAT_STATIONS, abs=1e-9)
    assert part.FLAT_STATIONS[0] == pytest.approx(
        part.SHAFT_LENGTH - spec.NORTH_FLAT_STATION
    )
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '\'"ShaftLength" - "NorthFlatStation"\'' in source
    assert 'set_global(adapter, "NorthFlatStation"' in source


def test_the_cup_seats_on_the_flat_at_its_shallowest() -> None:
    assert spec.SET_SCREW_CUP_DIA == ch_pivot_bracket_spec.SET_SCREW_POINT_DIA
    assert spec.FLAT_AF == pytest.approx(spec.SHAFT_DIA - spec.FLAT_DEPTH)
    assert spec.FLAT_DEPTH_RANGE == pytest.approx(
        (spec.FLAT_DEPTH - spec.LINEAR_3PL, spec.FLAT_DEPTH + spec.LINEAR_3PL)
    )
    # The chord at the shallowest printed depth takes the cup with 0.5 each
    # side; the deepest flat still leaves most of the round.
    assert spec.flat_chord(spec.FLAT_DEPTH_RANGE[0]) >= spec.SET_SCREW_CUP_DIA + 1.0
    assert spec.FLAT_DEPTH_RANGE[1] < spec.SHAFT_DIA / 4.0


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
    assert '{"FlatLength":FLATS_CALLOUT,"FlatAF":FLATS_CALLOUT}' in source


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
    crossed by both witness lines. It now ends left of the dome tip, clear
    of the shaft-length witness there too."""
    witnesses = (
        drawing.NORTH_END_X - spec.DOME_HEIGHT * drawing._MM,  # dome tip
        drawing.NORTH_END_X,  # shaft end
    )
    text_x, _ = drawing.PROFILE_KEEP["DomeHeight"]
    assert _stands_outside(text_x, DOME_CALLOUT_HALF_WIDTH, witnesses)
    assert text_x < min(witnesses)
    # Still inside the sheet's left border.
    assert text_x - DOME_CALLOUT_HALF_WIDTH > 0.02

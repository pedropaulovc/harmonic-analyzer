"""Offline contracts for the pivot-shaft (MHA-065) drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import _config
import _fit_limits
import build_pivot_shaft as part
import draw_pivot_shaft as drawing
import pivot_bracket_spec
import pivot_shaft_spec as spec
import rocker_bank_layout as bank
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["pivot_shaft"].script == Path(drawing.__file__).resolve()


def test_every_marked_dimension_lands_on_the_side_view() -> None:
    """Policy rule 7: a turned part's diameters and lengths sit on the side
    view, and all of them are authored on its Right-plane half-profile."""
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PROFILE_KEEP) == marked
    assert marked == {
        "ShaftDia",
        "ShoulderDia",
        "ShaftLength",
        "ShoulderLength",
        "JournalLength",
        "DomeHeight",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count('create_sketch("Right")') == 2  # the profile + the caps
    assert "create_revolve(" in source


def test_only_the_running_fit_carries_a_size_band() -> None:
    assert spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_runs_in_the_bracket_bores() -> None:
    lower, upper = _fit_limits.deviations(spec.SHAFT_DIA_BAND)
    clearance_min = pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + upper)
    clearance_max = pivot_bracket_spec.BORE_DIA - (spec.SHAFT_DIA + lower)
    assert round(clearance_min, 2) == 0.15
    assert clearance_max > clearance_min


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 3,
        "ShoulderDia": 2,
        "ShaftLength": 1,
        "ShoulderLength": 2,
        "JournalLength": 1,
        "DomeHeight": 1,
    }
    assert "draw_pivot_shaft.py" in PRECISION_MIGRATED_DRAWINGS
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
    assert spec.LENGTH_CALLOUT == "CUT TO FIT: SPAN OVER BOTH MHA-123 EARS"
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
    assert "NO FLATS" in spec.DRAWING_NOTES
    assert "STEPS" not in spec.DRAWING_NOTES


def test_the_isometric_note_states_the_only_off_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    ratio = re.search(r"(\d+)\s*:\s*(\d+)", spec.ISOMETRIC_VIEW_NOTE)
    assert ratio is not None
    assert (int(ratio.group(1)), int(ratio.group(2))) == drawing.ISO_SCALE


def test_part_stamps_make_critical_properties() -> None:
    config = _config.parts("pivot-shaft")
    assert config["number"] == "MHA-065"
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_surface_finishes_name_the_body_and_the_journal() -> None:
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"pivot_bearing", "pivot_journal"}
    for control in by_key.values():
        assert control.roughness_um == 1.6
        assert control.face.diameter_mm == spec.SHAFT_DIA
    # Part frame: the north end at z 0, the body toward -z.
    body_z = by_key["pivot_bearing"].face.contains_z_mm
    journal_z = by_key["pivot_journal"].face.contains_z_mm
    assert -spec.JOURNAL_LENGTH < journal_z < 0.0
    assert (
        -bank.PIVOT_SHAFT_LENGTH
        < body_z
        < -(spec.JOURNAL_LENGTH + spec.SHOULDER_LENGTH)
    )
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    sheet_source = "".join(Path(drawing.__file__).read_text(encoding="utf-8").split())
    for key in by_key:
        assert (
            f'control=surface_finish_by_key(SURFACE_FINISHES,"{key}")' in sheet_source
        )
    assert "roughness_ra=" not in sheet_source

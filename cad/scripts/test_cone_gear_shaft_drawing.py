"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_cone_gear_shaft as part
import cone_gear_shaft_spec
import draw_cone_gear_shaft as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-gear-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-gear-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-gear-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_gear_shaft"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_gear_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_gear_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.SIDE_KEEP) | set(drawing.END_KEEP)
    assert kept == marked
    assert part.SECTIONS is cone_gear_shaft_spec.SECTIONS
    assert drawing.SHAFT_LENGTH == cone_gear_shaft_spec.SHAFT_LENGTH
    assert drawing.SECTION_DIAS == cone_gear_shaft_spec.SECTION_DIAS


def test_sections_are_a_monotonic_stepped_shaft() -> None:
    """The v2 journal and four legacy gear sections step down monotonically."""
    sections = cone_gear_shaft_spec.SECTIONS
    assert len(sections) == 5
    dias = cone_gear_shaft_spec.SECTION_DIAS
    ends = cone_gear_shaft_spec.SECTION_ENDS
    assert all(a > b for a, b in zip(dias, dias[1:]))
    assert all(a < b for a, b in zip(ends, ends[1:]))
    # The integral bearing journal fits the v2 post at 0.05 diametral
    # clearance; every downstream gear seat keeps its existing diameter.
    assert cone_gear_shaft_spec.JOURNAL_BORE_DIA == pytest.approx(12.2808)
    assert cone_gear_shaft_spec.JOURNAL_CLEARANCE == pytest.approx(0.05)
    assert cone_gear_shaft_spec.JOURNAL_DIA == pytest.approx(12.2308)
    assert cone_gear_shaft_spec.JOURNAL_END == pytest.approx(43.011)
    assert dias == pytest.approx((12.2308, 9.525, 6.35, 3.175, 0.79375))
    assert cone_gear_shaft_spec.FRONT_STUB == pytest.approx(61.9068609979)
    assert cone_gear_shaft_spec.SHAFT_LENGTH == cone_gear_shaft_spec.FRONT_STUB + 190.0
    # The fixed journal/tip endpoints stay put while the three gear-seat
    # shoulders follow the recentered stack along the shaft.
    stub_delta = cone_gear_shaft_spec.FRONT_STUB - 12.3
    assert ends[1:] == pytest.approx(
        tuple(
            old_end + stub_delta + cone_gear_shaft_spec.GEAR_AXIS_SHIFT
            for old_end in (154.2, 161.1, 168.0)
        )
        + (202.3 + stub_delta,)
    )
    # Every seat diameter gets a snug-fit callout and exact-conversion display.
    assert drawing.DIMENSION_CALLOUTS == {
        name: "+0.00/-0.02" for name in drawing.END_KEEP
    }
    assert drawing.DIMENSION_PRECISION == {
        name: 4 if name == "Sec0Dia" else 3 for name in drawing.END_KEEP
    }


def test_linked_notes_cover_the_remaining_shaft_operations() -> None:
    notes = cone_gear_shaft_spec.DRAWING_NOTES
    assert "NO CENTRE HOLE" in notes
    assert "LARGE-END FACE" in notes
    # The 0.79 mm tip journal is a documented, Phase-3-flagged design
    # characteristic -- the print warns the machinist instead of hiding it.
    assert "FRAGILE BY DESIGN" in notes
    assert "FOLLOWER-REST" in notes
    assert "12.2308 BEARING JOURNAL" in notes
    assert "12.2808 POST BORE" in notes
    assert "0.05 DIAMETRAL CLEARANCE" in notes
    assert "DIA 12.5 MIN ROUND BAR" in notes
    assert "X.XX" not in notes
    assert "BREAK EXTERNAL EDGES" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_shaft_form_coaxiality_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert source.count('characteristic="cylindricity"') == 1
    assert source.count('characteristic="circular_runout"') == 1
    assert source.count("add_surface_finish(") == 2


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1  # side silhouette at sheet scale
    assert source.count("scale=(4, 1)") == 1  # enlarged end view
    assert source.count("scale=(1, 2)") == 1  # reduced pictorial
    assert drawing.END_VIEW_SCALE == 4.0


def test_datum_symbol_requests_the_persisted_journal_boundary() -> None:
    expected = (
        drawing.SIDE_CENTER[0]
        + drawing.SHAFT_LENGTH / 2000.0
        - drawing.JOURNAL_END / 1000.0
    )
    assert math.isclose(expected, 0.237942430381, abs_tol=1e-12)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "symbol_xy=(big_end_x - JOURNAL_END / 1000.0, 0.252)" in source
    assert "symbol_xy=(0.255, 0.242)" in source
    assert cone_gear_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 4:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-gear-shaft")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

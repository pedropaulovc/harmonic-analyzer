"""Offline contracts for the cone-gear-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import _fit_limits
import build_cone_gear_shaft as part
import cone_gear_shaft_spec
import draw_cone_gear_shaft as drawing
import pytest
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_section_fits_are_toleranced_on_the_model() -> None:
    """All five turned lands ride ONE shared fit class, applied to the model.

    Spelled as callout text the band is frozen: SolidWorks prints it verbatim
    and never re-renders it, so the mm->inch flip in issue #290 would leave
    "+0.00/-0.02" reading as inches on every land. The identity assertion also
    stops a local retype from silently forking the shared class.
    """
    assert drawing.DIMENSION_CALLOUTS == {}
    assert cone_gear_shaft_spec.SECTION_DIA_BAND is _fit_limits.SHAFT_H
    # Applied in a loop over the five sections, so the AST reports the f-string
    # source rather than five literal keys.
    assert model_toleranced_dimensions(part) == {
        ("f'Sec{section}Profile'", "f'Sec{section}Dia'"): (
            "*deviations(SECTION_DIA_BAND)"
        )
    }
    assert "for section in range(5)" in Path(part.__file__).read_text(encoding="utf-8")


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
    kept = (
        set(drawing.SIDE_STATION_KEEP)
        | set(drawing.SIDE_DIAMETER_STATIONS_MM)
        | set(drawing.DETAIL_DIAMETER_STATIONS_MM)
    )
    assert kept == marked
    assert part.SECTIONS is cone_gear_shaft_spec.SECTIONS
    assert drawing.SECTION_DIAS == cone_gear_shaft_spec.SECTION_DIAS
    assert drawing.SECTION_ENDS == cone_gear_shaft_spec.SECTION_ENDS


def test_diameters_read_on_their_own_lands_not_an_end_view() -> None:
    # Policy rule 7 / machinist review 2026-09-02: a turned part's diameters
    # sit on the side view's cylindrical segments, never on an end view whose
    # circles occlude one another.  The journal and the 3/8 in seat read on
    # the 1:1 silhouette; the 1/4, 1/8 and 1/32 in tip lands in DETAIL A
    # (3:1), curated BEFORE the side view (one view per marked dimension).
    assert set(drawing.SIDE_DIAMETER_STATIONS_MM) == {"Sec0Dia", "Sec1Dia"}
    assert set(drawing.DETAIL_DIAMETER_STATIONS_MM) == {"Sec2Dia", "Sec3Dia", "Sec4Dia"}
    ends = cone_gear_shaft_spec.SECTION_ENDS
    assert 0.0 < drawing.SIDE_DIAMETER_STATIONS_MM["Sec0Dia"] < ends[0]
    assert ends[0] < drawing.SIDE_DIAMETER_STATIONS_MM["Sec1Dia"] < ends[1]
    assert ends[1] < drawing.DETAIL_DIAMETER_STATIONS_MM["Sec2Dia"][0] < ends[2]
    assert ends[2] < drawing.DETAIL_DIAMETER_STATIONS_MM["Sec3Dia"][0] < ends[3]
    assert ends[3] < drawing.DETAIL_DIAMETER_STATIONS_MM["Sec4Dia"][0] < ends[4]
    # Every detail land lies inside the detail boundary.
    for station, _above in drawing.DETAIL_DIAMETER_STATIONS_MM.values():
        assert abs(station - drawing.DETAIL_MODEL_CENTER_Z) < drawing.DETAIL_MODEL_RADIUS
    assert drawing.DETAIL_SCALE == (3, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'detail_label="A"' in source
    assert source.index('view_label="detail"') < source.index('view_label="side"')
    assert "model_point_in_view(" in source
    assert '"*Front"' not in source  # no end view
    assert "End View Note" not in source
    assert not hasattr(cone_gear_shaft_spec, "END_VIEW_NOTE")
    assert "End View Note" not in Path(part.__file__).read_text(encoding="utf-8")


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
    assert cone_gear_shaft_spec.SHAFT_LENGTH == (
        cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.T006_TIP_STATION
    )
    # The fixed journal/tip endpoints stay put while the three gear-seat
    # shoulders follow the recentered stack along the shaft.
    stub_delta = cone_gear_shaft_spec.FRONT_STUB - 12.3
    assert ends[1:] == pytest.approx(
        tuple(
            old_end + stub_delta + cone_gear_shaft_spec.GEAR_AXIS_SHIFT
            for old_end in (154.2, 161.1, 168.0)
        )
        + (cone_gear_shaft_spec.FRONT_STUB + cone_gear_shaft_spec.T006_TIP_STATION,)
    )
    # Every seat diameter carries the snug fit as a NATIVE model tolerance --
    # see test_section_fits_are_toleranced_on_the_model.  Every land is a
    # fitted diameter, so all five print three places (the journal's 12.2308
    # rounds to 12.231; the title block tolerances three places, not four).
    assert drawing.DIMENSION_PRECISION == {
        name: 3 for name in ("Sec0Dia", "Sec1Dia", "Sec2Dia", "Sec3Dia", "Sec4Dia")
    }


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_gear_shaft_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "NO CENTRE HOLE" in notes
    assert "12.5 MIN ROUND BAR" in notes
    # The 0.79 mm tip journal is a documented, Phase-3-flagged design
    # characteristic -- the print warns the machinist instead of hiding it.
    assert "FRAGILE BY DESIGN" in notes
    assert "FOLLOWER REST" in notes
    # Nothing the title block, a dimension or a deleted control used to say.
    for banned in ("+/-", "DATUM", "RUNOUT", "CLEARANCE", "POST BORE", "X.XX", "UOS"):
        assert banned not in notes, banned
    assert drawing.NOTES_XY == (0.225, 0.110)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_and_one_running_journal_ra() -> None:
    """A shaft is not on the GD&T allowlist; the typed PMI rows stay empty."""
    from cone_gear_shaft_spec import GEOMETRIC_CONTROLS, PART_DATUMS, SURFACE_FINISHES

    assert PART_DATUMS == ()
    assert GEOMETRIC_CONTROLS == ()
    assert not hasattr(cone_gear_shaft_spec, "GEOMETRIC_TOLERANCES_MM")
    # One roughness symbol: the bearing journal that turns in the pivot post.
    assert tuple(control.key for control in SURFACE_FINISHES) == ("pivot_journal",)
    assert SURFACE_FINISHES[0].face.diameter_mm == cone_gear_shaft_spec.JOURNAL_DIA

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "project_part_pmi(",
        "add_feature_control_frame(",
        "add_datum_feature(",
        "set_basic_dimension(",
    ):
        assert helper not in source, helper
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "pivot_journal")' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (side, detail):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1  # side silhouette at sheet scale
    assert source.count("scale=(4, 1)") == 0  # the enlarged end view is gone
    assert source.count("scale=(1, 2)") == 1  # reduced pictorial
    assert "scale=DETAIL_SCALE" in source
    assert drawing.DETAIL_CENTER == (0.110, 0.098)
    assert drawing.ISO_CENTER == (0.360, 0.200)


def test_journal_finish_symbol_is_placed_clear_of_the_journal_diameter() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The Ra symbol stands right of the journal's diameter dimension (which
    # crosses the journal at mid-land) and leads down to the OD near the end.
    assert drawing.JOURNAL_FINISH_SYMBOL_XY == (0.275, 0.245)
    assert drawing.JOURNAL_FINISH_ATTACH_INBOARD_MM < drawing.SIDE_DIAMETER_STATIONS_MM["Sec0Dia"]
    assert "leader_attach_xy=pivot_top" in source
    assert "symbol_xy=JOURNAL_FINISH_SYMBOL_XY" in source


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

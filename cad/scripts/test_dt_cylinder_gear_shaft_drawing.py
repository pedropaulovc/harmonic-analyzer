"""Offline contracts for the cylinder-gear-shaft drawing."""

from __future__ import annotations

import re
from pathlib import Path

import _config
import _fit_deviations
import _fit_shaft_h
import dt_arbor_pedestal_spec
import build_dt_cylinder_gear_shaft as part
import dt_cylinder_gear_shaft_spec as spec
import draw_dt_cylinder_gear_shaft as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions


def test_every_marked_dimension_lands_where_a_turner_reads_it() -> None:
    """drawing-guidelines.md rule 11 (turned parts read like the lathe): a turned part's diameters belong on the SIDE view.

    A circle sketch's diameter only imports into a view that faces the circle,
    so the sheet imports it in a donor view and moves it -- which means every
    donor name needs a side-view destination or the diameter would ship on a
    throwaway view (or, once the donor is deleted, not at all).
    """
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.DONOR_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert set(drawing.PROFILE_DIAMETERS) == set(drawing.DONOR_KEEP)
    assert not set(drawing.PROFILE_DIAMETERS) & set(drawing.PROFILE_KEEP)


def test_only_the_running_fit_carries_a_size_band() -> None:
    """The O.D. is the one critical feature; the length rides the title block."""
    assert spec.SHAFT_DIA_BAND == _fit_shaft_h.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_closes_the_configured_running_fit() -> None:
    lower, upper = _fit_deviations.deviations(spec.SHAFT_DIA_BAND)
    shaft_limits = (spec.SHAFT_DIA + lower, spec.SHAFT_DIA + upper)
    bore_lower, bore_upper = _fit_deviations.deviations(dt_arbor_pedestal_spec.BORE_DIA_BAND)
    bore_limits = (
        dt_arbor_pedestal_spec.BORE_DIA + bore_lower,
        dt_arbor_pedestal_spec.BORE_DIA + bore_upper,
    )
    clearances = [
        round(bore_limits[0] - shaft_limits[1], 5),
        round(bore_limits[1] - shaft_limits[0], 5),
    ]
    assert clearances == list(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 4,
        "Depth": 1,
        "DomeHeight": 2,
        "DomeRadius": 2,
    }
    assert "draw_dt_cylinder_gear_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    # 3/8 in prints exactly (.3750): the native bearing size every mating
    # bore is built from.
    digits = spec.DRAWING_PRECISION_BY_NAME["ShaftDia"]
    printed = round(spec.SHAFT_DIA / 25.4, digits) * 25.4
    assert abs(printed - spec.SHAFT_DIA) <= 1e-9


def test_a_plain_drive_train_shaft_carries_no_gdt_and_no_end_view() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T) keeps GD&T for the castings and gear blanks.

    Size limits plus the title-block general grade already state everything a
    lathe hand can hold on a plain rod, and the end view existed only to carry
    the diameter that now sits on the side view.
    """
    for attribute in (
        "PART_DATUMS",
        "GEOMETRIC_CONTROLS",
        "END_VIEW_NOTE",
        "LENGTH_TOLERANCE_MM",
    ):
        assert not hasattr(spec, attribute)


def test_notes_are_short_specific_facts_with_no_dimension_in_them() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 0 < len(lines) <= 4
    for line in lines:
        assert line == line.upper()
        assert not re.search(r"\d+\.\d|±|\+/-", line)


def test_the_isometric_note_states_the_only_off_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    ratio = re.search(r"(\d+)\s*:\s*(\d+)", spec.ISOMETRIC_VIEW_NOTE)
    assert ratio is not None, f"missing view scale in {spec.ISOMETRIC_VIEW_NOTE!r}"
    assert (int(ratio.group(1)), int(ratio.group(2))) == drawing.ISO_SCALE


def test_the_length_is_a_cut_to_fit_reference() -> None:
    """#743 (superseding U34b's "span less 6.0"): the arbor fills both strap
    bores, so its cylinder IS the span over both installed pedestals -- a REF
    value the callout under it governs -- and each end is domed proud."""
    import cylinder_bank_layout as bank

    outer_span = bank.STRAP_INNER_SPAN + 2 * dt_arbor_pedestal_spec.STRAP_T
    assert part.SHAFT_LENGTH == bank.ARBOR_LENGTH == outer_span
    assert part.DOME_HEIGHT == bank.ARBOR_DOME_HEIGHT
    assert not hasattr(spec, "FIT_SHORTFALL")
    assert spec.DRAWING_PRECISION_BY_NAME["Depth"] == 1
    assert spec.LENGTH_CALLOUT.startswith("CUT TO FIT")
    assert "MHA-DT-02" in spec.LENGTH_CALLOUT
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_reference_dimension(adapter, length_annotations[0]' in source
    assert '{"Depth": LENGTH_CALLOUT}' in source


def test_both_ends_are_domed_and_the_dome_form_is_model_owned() -> None:
    """The bright dome on each pedestal is the arbor end (#743, MHA-125
    deleted). InsertDome states no markable height or radius, so a hidden
    reference sketch owns both, as the pedestal's locations are owned; the
    radius prints as the spherical reference that says the end is a sphere."""
    assert spec.REFERENCE_SKETCHES == ("DomeReference",)
    assert spec.DRAWING_DIMENSIONS["DomeReference"] == {"DomeHeight", "DomeRadius"}
    # The printed .06 IS the modelled dome (#290 snap).
    places = spec.DRAWING_PRECISION_BY_NAME["DomeHeight"]
    assert abs(round(part.DOME_HEIGHT / 25.4, places) * 25.4 - part.DOME_HEIGHT) <= 1e-9
    assert spec.DOME_CALLOUT == "BOTH ENDS"
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_set_spherical_reference(adapter, radius_annotations[0]" in drawing_source
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '_dome_end(adapter, 0.0, "SouthDome")' in source
    assert '_dome_end(adapter, SHAFT_LENGTH, "NorthDome")' in source
    assert "_hide_reference_sketches(adapter)" in source
    assert part.DOME_SPHERE_RADIUS > part.SHAFT_RADIUS
    assert "NO FLATS" in spec.DRAWING_NOTES

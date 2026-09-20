"""Offline contracts for the cylinder-gear-shaft drawing."""

from __future__ import annotations

import math
import re

import _config
import _fit_limits
import arbor_pedestal_spec
import build_cylinder_gear_shaft as part
import cylinder_gear_shaft_spec as spec
import draw_cylinder_gear_shaft as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions


def test_every_marked_dimension_lands_where_a_turner_reads_it() -> None:
    """Policy rule 7: a turned part's diameters belong on the SIDE view.

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
    assert spec.SHAFT_DIA_BAND == _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_closes_the_configured_running_fit() -> None:
    lower, upper = _fit_limits.deviations(spec.SHAFT_DIA_BAND)
    shaft_limits = (spec.SHAFT_DIA + lower, spec.SHAFT_DIA + upper)
    bore_lower, bore_upper = _fit_limits.deviations(arbor_pedestal_spec.BORE_DIA_BAND)
    bore_limits = (
        arbor_pedestal_spec.BORE_DIA + bore_lower,
        arbor_pedestal_spec.BORE_DIA + bore_upper,
    )
    clearances = [
        round(bore_limits[0] - shaft_limits[1], 3),
        round(bore_limits[1] - shaft_limits[0], 3),
    ]
    assert clearances == list(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {"ShaftDia": 3, "Depth": 1}
    assert "draw_cylinder_gear_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    # 3/8 in = 9.525 exactly: rounding the O.D. to 9.53 would contradict the
    # native bearing size every mating bore is built from.
    digits = spec.DRAWING_PRECISION_BY_NAME["ShaftDia"]
    printed = float(f"{spec.SHAFT_DIA:.{digits}f}")
    assert abs(printed - spec.SHAFT_DIA) <= math.ulp(spec.SHAFT_DIA)
    # One place on the free length claims the title block's .X row, not the
    # tighter .XX band a trailing 187.00 would ask for.
    assert _config.title_block("linear_1pl")["display"] == "±0.8"


def test_a_plain_drive_train_shaft_carries_no_gdt_and_no_end_view() -> None:
    """Rule 3 keeps GD&T for the castings and gear blanks.

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

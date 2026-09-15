"""Offline contracts for the cylinder-gear-shaft drawing."""

from __future__ import annotations

import math
import re

import build_cylinder_gear_shaft as part
import cylinder_gear_shaft_spec
import draw_cylinder_gear_shaft as drawing
import _fit_limits
from _drawing_contract import model_toleranced_dimensions


def test_drawing_keeps_every_marked_model_dimension() -> None:
    marked = set().union(*cylinder_gear_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP)
    assert kept == marked


def test_arbor_bearing_fit_is_toleranced_in_model() -> None:
    assert cylinder_gear_shaft_spec.SHAFT_DIA_BAND == _fit_limits.SHAFT_H
    assert cylinder_gear_shaft_spec.LENGTH_TOLERANCE_MM == 0.25
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("Shaft", "Depth"): "LENGTH_TOLERANCE_MM",
    }


def test_display_precision_preserves_exact_bearing_diameter() -> None:
    # Rounding 3/8 inch to 9.53 mm would contradict the native bearing size.
    diameter = cylinder_gear_shaft_spec.SHAFT_DIA
    precision = drawing.DIMENSION_PRECISION["ShaftDia"]
    assert abs(float(f"{diameter:.{precision}f}") - diameter) <= math.ulp(diameter)


def test_scale_labels_agree_with_their_views() -> None:
    for note, scale in (
        (cylinder_gear_shaft_spec.END_VIEW_NOTE, (drawing.END_VIEW_SCALE, 1)),
        (cylinder_gear_shaft_spec.ISO_VIEW_NOTE, drawing.ISO_SCALE),
    ):
        ratio = re.search(r"(\d+)\s*:\s*(\d+)", note)
        assert ratio is not None, f"Missing view scale in {note!r}"
        numerator, denominator = map(int, ratio.groups())
        assert numerator > 0 and denominator > 0
        assert numerator * scale[1] == denominator * scale[0]


def test_native_gdt_controls_arbor_form_orientation_and_finish() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from cylinder_gear_shaft_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {
        "bearing_cylindricity",
        "y0_end_perpendicularity",
        "y187_end_perpendicularity",
    }
    assert by_key["bearing_cylindricity"].characteristic == "cylindricity"
    assert by_key["bearing_cylindricity"].tolerance == "0.01"
    for key in ("y0_end_perpendicularity", "y187_end_perpendicularity"):
        assert by_key[key].characteristic == "perpendicularity"
        assert by_key[key].tolerance == "0.05"
        assert by_key[key].datums == ("A",)
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A",)

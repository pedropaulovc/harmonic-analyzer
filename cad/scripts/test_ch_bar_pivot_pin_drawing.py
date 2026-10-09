"""Offline contracts for the bar pivot pin (MHA-CH-011) part and drawing.

The installed pressed pin under ``cad/docs/drawing-simplicity-policy.md``: two
native model dimensions whose places (and the diameter's grind band) the PART
owns, the installed length as REFERENCE, no GD&T, no roughness symbol, and at
most four note lines: the blank, the press, the flush ends, the running fit.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_bar_pivot_pin as part
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_notes as notes
import ch_bar_pivot_pin_spec as spec
import ch_channel_lever_spec as lever
import draw_ch_bar_pivot_pin as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-bar-pivot-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-bar-pivot-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-bar-pivot-pin_drawing.png")
    entry = DRAWINGS_BY_NAME["ch_bar_pivot_pin"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "ch_bar_pivot_pin"
    assert part.PART_NAME == entry.artifact_stem == "ch-bar-pivot-pin"


def test_installed_model_is_flush_with_the_bar() -> None:
    assert spec.PIN_INSTALLED_LENGTH == bar.BAR_WIDTH
    assert part.HALF_LEN == pytest.approx(bar.BAR_WIDTH / 2.0)
    assert part.V_PIN == pytest.approx(
        math.pi * (spec.PIN_DIA / 2.0) ** 2 * bar.BAR_WIDTH
    )


def test_pin_axis_and_mid_plane_contract() -> None:
    build = _build_source()
    # Axis1 = part X (Top x Front), centred on the origin: the Right Plane is
    # the pin's axial mid-plane, which the assembly lands on the bar's.
    assert 'name_bore_axis(adapter, "Top Plane", 0.0, "Front Plane", 0.0' in build
    assert 'create_sketch("Front")' in build
    assert '"pin centred on origin"' in build
    assert "RevolveParameters(angle=360.0)" in build
    assert "volume_check(" in build
    assert "create_configuration" not in build  # one INSTALLED configuration


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) == marked == {"PinDia", "PinLen"}
    assert spec.REFERENCE_DIMENSIONS == {"PinLen"}
    assert not hasattr(drawing, "RIGHT_KEEP")


def test_precision_and_band_are_authored_on_the_part() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {"PinDia": 3, "PinLen": 2}
    assert "draw_ch_bar_pivot_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert (
        "set_reference_dimensions(adapter, front_annotations, REFERENCE_DIMENSIONS)"
        in source
    )
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()
    assert model_toleranced_dimensions(part) == {
        ("PinProfile", "PinDia"): "PIN_DIA_TOLERANCE",
    }


def test_print_carries_no_gdt_roughness_or_callouts() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "add_native_hole_callout(",
        "set_dimension_callouts(",
    ):
        assert helper not in source, helper
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_notes_state_blank_press_flush_ends_and_running_fit() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4  # policy rule 6
    assert lines == [
        "1. CUT BLANK 6.60 \u00b10.13 LONG; INSTALLED STATE SHOWN.",
        "2. PRESS IN; REMOVABLE WITH PUNCH.",
        "3. PRESSED IN THE MHA-CH-001 REAMED TOP PIN HOLE;"
        " DRESS BOTH ENDS FLUSH, NEVER PROUD.",
        "4. RUNS FREE IN THE MHA-CH-002 #47 BAR-PIN HOLE.",
    ]
    assert "DRILL ROD" not in notes.DRAWING_NOTES  # the title block owns the stock
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_numbers_in_the_notes_are_live() -> None:
    assert _config.parts("ch-amplitude-bar")["number"] == "MHA-CH-001"
    assert _config.parts("ch-channel-lever")["number"] == "MHA-CH-002"
    assert str(lever.BAR_PIN_HOLE_SPEC.size).lstrip("#") == "47"


def test_sheet_runs_at_10_to_1_and_lands_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert drawing.VIEW_SCALE == (10, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    (dia_x, dia_y) = drawing.FRONT_KEEP["PinDia"]
    assert dia_y > drawing.FRONT_CENTER[1] + drawing.HALF_DIA
    assert dia_x < drawing.FRONT_CENTER[0] - 0.015  # off the centerline pick
    assert drawing.FRONT_KEEP["PinLen"][1] < drawing.FRONT_CENTER[1] - drawing.HALF_DIA
    for x, y in (*drawing.FRONT_KEEP.values(), drawing.NOTES_XY):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    # Third-angle: the end view projects right of the side view on its Y.
    assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
    assert (
        drawing.FRONT_CENTER[0] + drawing.HALF_LEN
        < drawing.RIGHT_CENTER[0] - drawing.HALF_DIA - 0.010
    )
    assert (
        drawing.RIGHT_CENTER[0] + drawing.HALF_DIA
        < drawing.ISO_CENTER[0] - drawing.HALF_LEN - 0.010
    )


def test_part_registry_row() -> None:
    config = _config.parts("ch-bar-pivot-pin")
    assert config["number"] == "MHA-CH-011"
    assert int(config["quantity"]) == 20
    assert config["tolerance_class"] == "machined_block"
    assert "fit_class" not in config
    assert config["process"] == (
        "cut from drill rod; pressed into the bar at assembly, ends dressed flush"
    )
    for field in ("material", "material_specification"):
        assert "drill rod" in str(config[field])
    assert "annealed" in str(config["material_specification"])
    assert len(str(config["material"])) <= 36

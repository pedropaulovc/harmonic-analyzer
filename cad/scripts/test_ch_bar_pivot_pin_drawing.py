"""Offline contracts for the bar pivot pin (MHA-CH-11) part and drawing.

The cut drill-rod pin under ``cad/docs/drawing-guidelines.md``: the part's
default configuration is the pin the shop makes and the sheet prints it on
two native model dimensions whose places the PART owns, the mates named at
the diameter, no GD&T, no roughness symbol and no note. The channel assembly
places the INSTALLED configuration, dressed flush with the bar.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_bar_pivot_pin as part
import build_ch_channel_assembly as channel
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_notes as notes
import ch_bar_pivot_pin_spec as spec
import ch_channel_assembly_sheet as channel_sheet
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


def test_default_is_the_cut_pin_and_installed_is_flush_with_the_bar() -> None:
    area = math.pi * (spec.PIN_DIA / 2.0) ** 2
    assert spec.PIN_INSTALLED_LENGTH == bar.BAR_WIDTH
    assert part.HALF_LEN == pytest.approx(spec.PIN_BLANK_LENGTH / 2.0)
    assert part.V_PIN == pytest.approx(area * spec.PIN_BLANK_LENGTH)
    assert part.V_INSTALLED == pytest.approx(area * bar.BAR_WIDTH)
    build = _build_source()
    assert 'set_global(adapter, "PinLen", f"{PIN_BLANK_LENGTH}mm")' in build
    assert "(default_config, PIN_BLANK_LENGTH)" in build
    assert "(INSTALLED_CONFIG, PIN_INSTALLED_LENGTH)" in build
    assert "require_material_in_every_configuration(" in build
    assert "apply_grouped_bom_properties(" in build
    assert "assert_saved_configurations_regenerate(adapter, PART_NAME)" in build


def test_channel_assembly_places_the_installed_configuration() -> None:
    assert spec.INSTALLED_CONFIG == "INSTALLED"
    assert channel.BAR_PIN_INSTALLED_CONFIG == spec.INSTALLED_CONFIG
    source = Path(channel.__file__).read_text(encoding="utf-8")
    assert "configuration=BAR_PIN_INSTALLED_CONFIG," in source


def test_pin_axis_and_mid_plane_contract() -> None:
    build = _build_source()
    # Axis1 = part X (Top x Front), centred on the origin: the Right Plane is
    # the pin's axial mid-plane, which the assembly lands on the bar's.
    assert 'name_bore_axis(adapter, "Top Plane", 0.0, "Front Plane", 0.0' in build
    assert 'create_sketch("Front")' in build
    assert '"pin centred on origin"' in build
    assert "RevolveParameters(angle=360.0)" in build
    assert "volume_check(" in build


def test_notes_module_is_the_single_source_of_the_marked_dimension_set() -> None:
    """The drawing contract lives in ch_bar_pivot_pin_notes, out of the spec
    the channel assembly and the fit test import."""
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is notes.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION"):
        assert not hasattr(spec, name), name
    assert notes.DRAWING_DIMENSIONS == {"PinProfile": {"PinDia", "PinLen"}}
    assert set(drawing.FRONT_KEEP) == {"PinDia", "PinLen"}
    assert not hasattr(drawing, "RIGHT_KEEP")


def test_cut_length_takes_the_title_block_band() -> None:
    """Machinist round 2 (#1305): the cut length's only job is to stand proud
    of both faces before dressing, so it takes the title block's band; on the
    inch sheet the .X band (+/-.1) would let it fall short of the bar, so it
    prints .30 under .XX. Rubric-sample review 2026-11-06: the sheet draws the
    cut pin itself in solid lines, not dashed ends past the installed one."""
    from _printed_tolerance import printed_band_mm

    places = notes.DRAWING_PRECISION["PinProfile"]["PinLen"]
    assert places == spec.PIN_BLANK_LENGTH_PLACES
    band = printed_band_mm(places, unit=spec.UNIT)
    assert spec.PIN_BLANK_LENGTH_BAND == (band, -band)
    assert spec.BUDGET["blank_excess_min"] > 0.0
    build = _build_source()
    assert "BlankReference" not in build and "blank_reference_sketches" not in build
    assert "hidden_sketches" not in _source()


def test_precision_and_band_are_authored_on_the_part() -> None:
    assert "draw_ch_bar_pivot_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()
    # The diameter is the as-bought drill rod: no model band (its stock
    # fraction prints as a REFERENCE; the supplier's grind governs).
    assert model_toleranced_dimensions(part) == {}


def test_print_carries_no_gdt_or_roughness() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_no_note_and_the_mates_at_the_diameter() -> None:
    """Rubric-sample review 2026-11-06 (rule 7): a callout carries at most two
    lines of words, and the installed length's flush wording was an assembly
    instruction (the channel assembly's step dresses the pin flush)."""
    lines = notes.DIAMETER_CALLOUT.splitlines()
    assert lines == [
        f"PRESS FIT IN {notes.BAR_NUMBER}",
        f"RUNS IN {notes.LEVER_NUMBER} #47 HOLE",
    ]
    # #2136 review: the bought rod's REF prints no band and no material (the
    # supplier's catalogue grind and the title-block MATERIAL own those).
    for row in lines:
        assert "\u00b1" not in row and "DRILL ROD" not in row
    assert not hasattr(notes, "DRAWING_NOTES")
    assert "Manufacturing Notes" not in _build_source()
    source = _source()
    assert "add_property_linked_note" not in source
    assert "set_dimension_callouts" not in source
    # r1: SOLIDWORKS printed nothing of a multi-line callout above a value.
    assert 'location="above"' not in source
    # The diameter's two-line callout hangs clear of the pin's outline.
    assert drawing.FRONT_KEEP["PinDia"][1] - 3 * 0.0045 > (
        drawing.FRONT_CENTER[1] + drawing.HALF_DIA + 0.002
    )


def test_mating_part_numbers_in_the_callouts_are_live() -> None:
    assert _config.parts("ch-amplitude-bar")["number"] == notes.BAR_NUMBER
    assert _config.parts("ch-channel-lever")["number"] == notes.LEVER_NUMBER
    assert str(lever.BAR_PIN_HOLE_SPEC.size).lstrip("#") == "47"


def test_sheet_runs_at_10_to_1_and_lands_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert drawing.VIEW_SCALE == (10, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    (dia_x, dia_y) = drawing.FRONT_KEEP["PinDia"]
    assert dia_y > drawing.FRONT_CENTER[1] + drawing.HALF_DIA
    assert dia_x < drawing.FRONT_CENTER[0] - 0.015  # off the centerline pick
    assert drawing.FRONT_KEEP["PinLen"][1] < drawing.FRONT_CENTER[1] - drawing.HALF_DIA
    for x, y in drawing.FRONT_KEEP.values():
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
    assert config["number"] == "MHA-CH-11"
    assert int(config["quantity"]) == 20
    assert config["tolerance_class"] == "machined_block"
    assert "fit_class" not in config
    assert config["process"] == (
        "cut from drill rod; pressed into the bar at assembly, ends dressed flush"
    )
    # Both configurations carry this BOM description; the channel BOM checks it.
    assert config["description"] == channel_sheet.BOM_DESCRIPTIONS["ch-bar-pivot-pin"]
    for field in ("material", "material_specification"):
        assert "drill rod" in str(config[field])
    assert "annealed" in str(config["material_specification"])
    assert len(str(config["material"])) <= 36

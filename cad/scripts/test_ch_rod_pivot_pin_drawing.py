"""Offline contracts for the rod pivot pin (MHA-CH-010) part and drawing.

The installed pressed pin under ``cad/docs/drawing-simplicity-policy.md``
(user ruling 2026-10-09, PR #1292 review F1): three native model dimensions
whose places and bands the PART owns -- the diameter with its grind band, the
installed length as REFERENCE, and the blank's cut length from a blanked
reference sketch with its band (rule 2; PR #1292 review N1: never note
text) -- no GD&T, no roughness symbol, and at most four note lines: cut the
blank, the press, the flush ends, the running fit.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_ch_rod_pivot_pin as part
import ch_connecting_rod_spec as rod
import ch_rod_pivot_pin_notes as notes
import ch_rod_pivot_pin_spec as spec
import draw_ch_rod_pivot_pin as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-rod-pivot-pin.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-rod-pivot-pin.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-rod-pivot-pin_drawing.png")
    entry = DRAWINGS_BY_NAME["ch_rod_pivot_pin"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.part == "ch_rod_pivot_pin"
    assert part.PART_NAME == entry.artifact_stem == "ch-rod-pivot-pin"


def test_installed_model_is_flush_with_the_fork() -> None:
    assert spec.PIN_INSTALLED_LENGTH == rod.FORK_THICKNESS
    assert spec.PIN_END_PROUD_MAX == 0.0
    assert part.HALF_LEN == pytest.approx(rod.FORK_THICKNESS / 2.0)
    assert part.V_PIN == pytest.approx(
        math.pi * (spec.PIN_DIA / 2.0) ** 2 * rod.FORK_THICKNESS
    )
    build = _build_source()
    assert "Csk" not in build


def test_pin_axis_and_mid_plane_contract() -> None:
    build = _build_source()
    # Axis1 = part Z (Right x Top); symmetric about the Front Plane.
    assert 'name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0' in build
    assert '"origin", axis_line, "midpoint"' in build
    assert 'create_sketch("Right")' in build
    assert "RevolveParameters(angle=360.0)" in build
    assert "volume_check(" in build


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    assert set(drawing.RIGHT_KEEP) == marked == {"PinDia", "PinLen", "BlankLen"}
    assert notes.REFERENCE_DIMENSIONS == {"PinLen"}
    # Drawing-only data stays out of the spec the channel assembly imports.
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "REFERENCE_DIMENSIONS"):
        assert not hasattr(spec, name), name
    assert not hasattr(drawing, "FRONT_KEEP")


def test_precision_and_band_are_authored_on_the_part() -> None:
    # The installed length is the fork's 3-place thickness, so it prints at
    # three places; the blank's band is written at two.
    assert notes.DRAWING_PRECISION_BY_NAME == {"PinDia": 3, "PinLen": 3, "BlankLen": 2}
    assert "draw_ch_rod_pivot_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    # A LINEAR reference: the plural helper forces a diameter glyph.
    assert "set_reference_dimensions(" not in source
    assert "set_reference_dimension(adapter, matches[0]" in source
    assert "hidden_sketches.curate_view_dimensions(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()
    assert "require_saved_drawing_properties(" in _build_source()
    assert model_toleranced_dimensions(part) == {
        ("PinProfile", "PinDia"): "PIN_DIA_TOLERANCE",
        ("BlankReference", "BlankLen"): "blank_upper",
    }


def test_blank_length_is_a_model_dimension_with_its_band() -> None:
    """PR #1292 review N1: the 6.40 +/-0.13 cut length prints from a blanked
    reference sketch on the pin axis with its native band at its native two
    places, never from note text (policy rules 2 and 6)."""
    assert spec.PIN_BLANK_LENGTH == 6.40
    assert spec.PIN_BLANK_LENGTH_BAND == (0.13, -0.13)
    assert notes.DRAWING_DIMENSIONS["BlankReference"] == {"BlankLen"}
    assert notes.DRAWING_PRECISION["BlankReference"] == {"BlankLen": 2}
    build = "".join(_build_source().split())
    assert 'set_global(adapter,"BlankLen",f"{PIN_BLANK_LENGTH}mm")' in build
    assert 'blank.record("BlankLen",\'"BlankLen"\')' in build
    assert 'name_last_feature(adapter,"BlankReference")' in build
    assert '"origin",blank_line,"midpoint"' in build
    assert "blank_lower,blank_upper=deviations(PIN_BLANK_LENGTH_BAND)" in build
    assert 'blank_reference_sketches(adapter,("BlankReference",))' in build
    source = _source()
    assert '{"BlankLen": "BLANK"}' in source
    # The blank is longer than the installed pin by the two ends' dressing.
    assert spec.PIN_BLANK_LENGTH > spec.PIN_INSTALLED_LENGTH


def test_print_carries_no_gdt_roughness_or_callouts() -> None:
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
    # The one dimension callout is the blank's descriptive word beneath its
    # native value and band.
    assert source.count("set_dimension_callouts(") == 1
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_notes_state_blank_press_flush_ends_and_running_fit() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4  # policy rule 6
    assert lines == [
        "1. CUT BLANK TO THE BLANK LENGTH SHOWN; INSTALLED STATE SHOWN.",
        "2. PRESS IN; REMOVABLE WITH PUNCH.",
        "3. PRESSED IN THE MHA-CH-003 REAMED FORK PIN HOLE;"
        " DRESS BOTH ENDS FLUSH, NEVER PROUD.",
        "4. RUNS FREE IN THE MHA-CH-006 #47 ROD HOLE.",
    ]
    text = notes.DRAWING_NOTES
    # Rules 2 and 6 (PR #1292 review N1): the blank's size and band are the
    # BlankLen model dimension's, so no limit may ride the note text.
    for limit in (
        f"{spec.PIN_BLANK_LENGTH:.2f}",
        f"{spec.PIN_BLANK_LENGTH_BAND[0]:.2f}",
        "\u00b1",
        "+/-",
    ):
        assert limit not in text, limit
    assert "PEEN" not in text and "#746" not in text
    assert "DRILL ROD" not in text  # the title-block MATERIAL owns the stock
    assert '"Manufacturing Notes": DRAWING_NOTES' in _build_source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_mating_part_numbers_in_the_notes_are_live() -> None:
    assert _config.parts("ch-connecting-rod")["number"] == "MHA-CH-003"
    assert _config.parts("ch-rocker-arm")["number"] == "MHA-CH-006"
    import ch_rocker_arm_spec as arm

    assert str(arm.ROD_HOLE_SPEC.size).lstrip("#") == "47"


def test_sheet_runs_at_10_to_1_and_lands_clear_of_the_title_block() -> None:
    assert drawing.SHEET_SCALE == (10.0, 1.0)
    assert drawing.VIEW_SCALE == (10, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    (dia_x, dia_y) = drawing.RIGHT_KEEP["PinDia"]
    assert dia_y > drawing.RIGHT_CENTER[1] + drawing.HALF_DIA
    assert dia_x < drawing.RIGHT_CENTER[0] - 0.015  # off the centerline pick
    assert drawing.RIGHT_KEEP["PinLen"][1] < drawing.RIGHT_CENTER[1] - drawing.HALF_DIA
    assert drawing.RIGHT_KEEP["BlankLen"][1] < drawing.RIGHT_KEEP["PinLen"][1] - 0.010
    for x, y in (*drawing.RIGHT_KEEP.values(), drawing.NOTES_XY):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    assert (
        drawing.FRONT_CENTER[0] + drawing.HALF_DIA
        < drawing.RIGHT_CENTER[0] - drawing.HALF_LEN - 0.010
    )
    assert (
        drawing.RIGHT_CENTER[0] + drawing.HALF_LEN
        < drawing.ISO_CENTER[0] - drawing.HALF_LEN - 0.010
    )


def test_part_registry_row() -> None:
    config = _config.parts("ch-rod-pivot-pin")
    assert config["number"] == "MHA-CH-010"
    assert int(config["quantity"]) == 20
    assert config["tolerance_class"] == "machined_block"
    assert "fit_class" not in config
    assert config["process"] == (
        "cut from drill rod; pressed into the rod fork at assembly, ends dressed flush"
    )
    for field in ("material", "material_specification"):
        assert "drill rod" in str(config[field])
    assert "annealed" in str(config["material_specification"])
    assert len(str(config["material"])) <= 36

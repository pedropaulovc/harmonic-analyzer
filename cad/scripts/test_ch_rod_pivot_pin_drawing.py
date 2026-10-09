"""Offline contracts for the rod pivot pin (MHA-CH-010) part and drawing.

The installed peened pin under ``cad/docs/drawing-simplicity-policy.md``: two
native model dimensions whose places (and the journal's grind band) the PART
owns, the installed length as REFERENCE, no GD&T, no roughness symbol, and at
most four note lines, one of which says peened retention is a reconstruction
choice (issue #746).
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


def test_installed_model_fills_the_fork_countersinks() -> None:
    # The model is the installed pin: flush with both tines, each end the
    # 90-degree countersink cone it was peened into.
    assert spec.PIN_INSTALLED_LENGTH == rod.FORK_THICKNESS
    assert spec.PIN_CSK_DIA == rod.PIN_HOLE_CSK_DIA
    assert part.HALF_LEN == pytest.approx(rod.FORK_THICKNESS / 2.0)
    assert part.CSK_DEPTH == pytest.approx((spec.PIN_CSK_DIA - spec.PIN_DIA) / 2.0)
    r, big, d = spec.PIN_DIA / 2.0, spec.PIN_CSK_DIA / 2.0, part.CSK_DEPTH
    expected = math.pi * r**2 * (spec.PIN_INSTALLED_LENGTH - 2.0 * d) + 2.0 * (
        math.pi * d / 3.0 * (big**2 + big * r + r**2)
    )
    assert part.V_PIN == pytest.approx(expected)


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
    assert set(drawing.RIGHT_KEEP) == marked == {"PinDia", "PinLen"}
    assert notes.REFERENCE_DIMENSIONS == {"PinLen"}
    # Drawing-only data stays out of the spec the channel assembly imports.
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "REFERENCE_DIMENSIONS"):
        assert not hasattr(spec, name), name
    assert not hasattr(drawing, "FRONT_KEEP")


def test_precision_and_band_are_authored_on_the_part() -> None:
    assert notes.DRAWING_PRECISION_BY_NAME == {"PinDia": 3, "PinLen": 3}
    assert "draw_ch_rod_pivot_pin.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "assert_imported_precision(" in source
    assert (
        "set_reference_dimensions(adapter, right_annotations, REFERENCE_DIMENSIONS)"
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
    ):
        assert helper not in source, helper
    assert "author_part_pmi" not in _build_source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "add_view_centerline(" in source


def test_notes_state_blank_peening_running_fit_and_reconstruction() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert len(lines) <= 4  # policy rule 6
    text = notes.DRAWING_NOTES
    assert "CUT BLANK 7.50 \u00b10.13 LONG" in text
    assert "PEEN BOTH ENDS INTO THE MHA-CH-003 FORK COUNTERSINKS AT ASSEMBLY" in text
    assert "DRESS TO 0.10 MAX PROUD" in text
    assert "RUNS FREE IN THE MHA-CH-006 #47 ROD HOLE" in text
    assert "RECONSTRUCTION CHOICE (#746)" in text
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
    assert dia_y > drawing.RIGHT_CENTER[1] + drawing.HALF_RIM
    assert dia_x < drawing.RIGHT_CENTER[0] - 0.015  # off the centerline pick
    assert drawing.RIGHT_KEEP["PinLen"][1] < drawing.RIGHT_CENTER[1] - drawing.HALF_RIM
    for x, y in (*drawing.RIGHT_KEEP.values(), drawing.NOTES_XY):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)
    assert (
        drawing.FRONT_CENTER[0] + drawing.HALF_RIM
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
    assert config["process"] == "cut from drill rod; both ends peened at assembly"
    for field in ("material", "material_specification"):
        assert "drill rod" in str(config[field])
    assert "annealed" in str(config["material_specification"])
    assert len(str(config["material"])) <= 36

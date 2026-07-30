"""Offline contracts for the pinion-arbor drawing."""

from __future__ import annotations

from pathlib import Path

import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_spec
import _fit_limits
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_arbor"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pinion_arbor_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_arbor_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LEN, drawing.CAP_SAG) == (
        pinion_arbor_spec.SHAFT_DIA,
        pinion_arbor_spec.SHAFT_LEN,
        pinion_arbor_spec.CAP_SAG,
    )


def test_crown_is_dimensioned_and_annotated() -> None:
    # The crown radius derives from the marked sagitta: R = (r^2 + s^2) / 2s.
    r, s = pinion_arbor_spec.SHAFT_DIA / 2.0, pinion_arbor_spec.CAP_SAG
    assert abs(pinion_arbor_spec.CAP_R - (r * r + s * s) / (2.0 * s)) < 1e-9
    assert "CapSagDim" in drawing.RIGHT_KEEP
    assert drawing.CAP_CALLOUTS["CapSagDim"] == "SR7.27 CROWN"
    assert "CROWN BACK END SR7.27" in pinion_arbor_spec.DRAWING_NOTES


def test_linked_notes_define_remaining_arbor_operations() -> None:
    notes = pinion_arbor_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS == {}
    assert pinion_arbor_spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)"
    }
    assert "CENTRE MARKS" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_arbor_form_orientation_and_finish() -> None:
    """GD&T identity lives in the spec's PMI rows; the sheet only imports it."""
    from pinion_arbor_spec import GEOMETRIC_CONTROLS, PART_DATUMS

    by_key = {control.key: control for control in GEOMETRIC_CONTROLS}
    assert set(by_key) == {"bearing_cylindricity", "flat_tip_perpendicularity"}
    assert by_key["bearing_cylindricity"].characteristic == "cylindricity"
    assert by_key["bearing_cylindricity"].tolerance == "0.01"
    # Only the flat front tip is squared to the axis -- the back end is the crown.
    assert by_key["flat_tip_perpendicularity"].characteristic == "perpendicularity"
    assert by_key["flat_tip_perpendicularity"].tolerance == "0.05"
    assert by_key["flat_tip_perpendicularity"].datums == ("A",)
    assert by_key["flat_tip_perpendicularity"].face.normal == (0, 0, -1)
    assert by_key["flat_tip_perpendicularity"].face.offset_mm == 0.0
    assert tuple(datum.letter for datum in PART_DATUMS) == ("A",)
    assert PART_DATUMS[0].face.diameter_mm == pinion_arbor_spec.SHAFT_DIA

    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "project_part_pmi(" in source
    assert "controls=GEOMETRIC_CONTROLS" in source
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert source.count("add_surface_finish(") == 1


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert source.count("scale=(1, 1)") == 1
    assert "scale=(1, 2)" in source  # 226-long arbor: half-scale isometric
    assert pinion_arbor_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pinion-arbor")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

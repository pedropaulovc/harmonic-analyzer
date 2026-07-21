"""Offline contracts for the pinion-return-leaf-spring drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_spring_spec
import draw_pinion_spring as drawing
import build_pinion_spring as spring
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-spring.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-spring.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-spring_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_spring"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert spring.DRAWING_DIMENSIONS is pinion_spring_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_spring_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The build re-imports its primitive nominals from the spec.
    assert (spring.FOOT_LEN, spring.THICK, spring.WIDTH) == (
        pinion_spring_spec.FOOT_LEN,
        pinion_spring_spec.THICK,
        pinion_spring_spec.WIDTH,
    )


def test_it_is_a_formed_leaf_not_a_coil_spring() -> None:
    # The mission's coil-spring spec sheet does NOT apply: this is a bent strip.
    notes = pinion_spring_spec.DRAWING_NOTES
    assert "0.80+/-0.05 THK X 4.00+/-0.05 WIDE STRIP" in notes
    assert "COIL" not in notes
    assert "FORM FROM" in notes


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.TOP_CENTER[0] >= 0.250
    assert drawing.TOP_CENTER[1] >= 0.090
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert pinion_spring_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert drawing.FRONT_BBOX_CX < 0.0


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_spring_spec.DRAWING_NOTES
    assert "TANGENT LENGTH 39.64" in notes
    assert "INSIDE-SURFACE PATH" in notes
    assert "MID-THICKNESS" not in notes
    assert "FROM EITHER" not in notes
    assert "FROM R1.50 KINK EXIT TO FREE TIP" in notes
    assert "0.80 STRIP END FACE" in notes
    assert "97.62+/-1 DEG CCW FROM FOOT INSIDE PATH" in drawing.DIMENSION_CALLOUTS[
        "FlatLen"
    ]
    assert "NEAR-VERTICAL" not in drawing.DIMENSION_CALLOUTS["FlatLen"]
    assert "2.00+/-0.10" not in notes
    assert "LINEAR +/-" not in notes
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_feature_requirements_use_inspectable_datum_controls() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert source.count("add_feature_control_frame(") == 1
    assert "characteristic=\"flatness\"" in source
    assert "parallelism" not in source
    assert "add_surface_finish(" not in source
    assert source.count('entity_type="FACE"') == 1
    assert "FORMED PROFILE - FRONT VIEW SCALE 2:1" in source
    assert "TOP VIEW - LOOKING AT SCREW-DOWN FOOT BROAD FACE - SCALE 2:1" in source
    assert "SIZE PER NATIVE CALLOUT" in pinion_spring_spec.DRAWING_NOTES
    assert source.count("add_native_hole_callout(") == 1
    assert "NO TWIST" not in pinion_spring_spec.DRAWING_NOTES
    assert 'quantity="FOOT BROAD FACE"' in source
    assert abs(spring._BLADE_LEN - pinion_spring_spec.BLADE_STRAIGHT_LEN) < 1e-9
    assert "INSIDE RADIUS" in drawing.DIMENSION_CALLOUTS["BendR"]
    assert "INSIDE RADIUS" in drawing.DIMENSION_CALLOUTS["KinkR"]
    assert "R2.00 AND R1.50" not in pinion_spring_spec.DRAWING_NOTES


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(spring.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-spring")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1

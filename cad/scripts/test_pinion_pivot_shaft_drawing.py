"""Offline contracts for the pinion-torque-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_pivot_shaft_spec
import draw_pinion_pivot_shaft as drawing
import build_pinion_pivot_shaft as shaft
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_surface_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = pinion_pivot_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_pivot_shaft_spec.SHAFT_DIA
    part_source = Path(shaft.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-pivot-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_pivot_shaft"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert shaft.DRAWING_DIMENSIONS is pinion_pivot_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert drawing.SHAFT_DIA == pinion_pivot_shaft_spec.SHAFT_DIA
    assert drawing.SHAFT_LEN == pinion_pivot_shaft_spec.SHAFT_LEN


def test_sheet_runs_at_1_to_1_with_2_to_1_end_view_and_1_to_2_iso() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_SCALE == (1, 2)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(4, 1)" in source  # the end-view override
    assert pinion_pivot_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_linked_notes_are_functional_and_carry_no_general_tolerance() -> None:
    notes = pinion_pivot_shaft_spec.DRAWING_NOTES
    assert "SPHERICAL CROWN" in notes
    assert "DERIVED AXIS" in notes
    assert "PROFILE 0.05, FORM ONLY (NO DATUM)" in notes
    assert "EXEMPT FROM TITLE-BLOCK EDGE-BREAK" in notes
    assert "(1.20) REF AXIAL HEIGHT" in notes
    assert "1.20+/-0.05" not in notes
    assert "194.40 OVERALL" not in notes
    assert drawing.DIMENSION_CALLOUTS["ShaftDia"] == "FINAL SIZE"
    assert model_toleranced_dimensions(shaft) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }
    # U27: the length reads the title-block .X band, not a tight tolerance.
    assert pinion_pivot_shaft_spec.DRAWING_PRECISION == {
        "Shaft": {"Depth": 1},
        "PinHoleProfile": {"PinHoleDia": 2},
    }
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_direct_limits_and_native_cylindricity_control_the_body() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert "edge_xy=end_top" in source
    assert "symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024)" in source
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="BOTH CROWNS"' in source
    assert 'entity_type="FACE"' in source
    assert 'entity_type="SILHOUETTE"' not in source
    assert "add_surface_finish(" in source
    assert "CYLINDRICITY" not in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    assert "Ra 1.6" not in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    assert "CROWN ROOT CIRCLES" in drawing.DIMENSION_CALLOUTS["Depth"]
    # Main eye pass on pc-ea2: under the end view the diameter's leader ran
    # back through its own stacked "-0.02".  Clear left of the end view the
    # leader rises right from the underline and crosses no tolerance text.
    text_x, text_y = drawing.FRONT_KEEP["ShaftDia"]
    end_view_left = (
        drawing.FRONT_CENTER[0]
        - drawing.END_VIEW_SCALE * pinion_pivot_shaft_spec.SHAFT_DIA / 2.0 / 1000.0
    )
    assert text_x < end_view_left
    assert text_y < drawing.FRONT_CENTER[1]


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(shaft.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("pinion-pivot-shaft")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert int(spec["quantity"]) == 1


def test_set_pin_holes_print_only_size_and_the_match_drill() -> None:
    # Option E-a: the strap sets the stations at assembly (back-flush, cluster
    # at the back stop), so the print carries the size and the match-drill
    # callout, never a station a floating length band would contradict.
    marked = set().union(*pinion_pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    assert {"PinHoleDia"} <= marked
    assert not any(name.startswith("PinHole") and name.endswith("Z") for name in marked)
    callout = drawing.DIMENSION_CALLOUTS["PinHoleDia"]
    assert callout is pinion_pivot_shaft_spec.PIN_HOLE_CALLOUT
    assert "MATCH-DRILL THRU AT ASSEMBLY" in callout
    assert "MHA-056" in callout
    assert "2 PL" in callout
    assert pinion_pivot_shaft_spec.PIN_HOLE_DIA == 25.4 / 16.0
    assert pinion_pivot_shaft_spec.PIN_HOLE_BAND == (0.06, 0.0)

"""Offline contracts for the pinion-torque-shaft drawing."""

from __future__ import annotations

from pathlib import Path

import pinion_pivot_shaft_spec
import draw_pinion_pivot_shaft as drawing
import build_pinion_pivot_shaft as shaft
from _drawing_registry import DRAWINGS_BY_NAME


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
    assert "PROFILE 0.05 TO DATUM A" in notes
    assert "EXEMPT FROM TITLE-BLOCK EDGE-BREAK" in notes
    assert "1.20 REF AXIAL HEIGHT" in notes
    assert "1.20+/-0.05" not in notes
    assert "194.40 OVERALL" not in notes
    assert "6.350 MAX / 6.330 MIN" in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    # General tolerances live in the title block ONLY.
    assert "LINEAR +/-" not in notes
    assert " BA " not in f" {notes} "
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_direct_limits_and_native_cylindricity_control_the_body() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 2
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="BOTH CROWNS"' in source
    assert 'entity_type="FACE"' in source
    assert 'entity_type="SILHOUETTE"' not in source
    assert "add_surface_finish(" in source
    assert "CYLINDRICITY" not in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    assert "Ra 1.6" not in drawing.DIMENSION_CALLOUTS["ShaftDia"]
    assert "CROWN ROOT CIRCLES" in drawing.DIMENSION_CALLOUTS["Depth"]
    assert drawing.FRONT_KEEP["ShaftDia"] == (0.055, 0.167)


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

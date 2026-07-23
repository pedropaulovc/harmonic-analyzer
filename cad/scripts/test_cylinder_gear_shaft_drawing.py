"""Offline contracts for the cylinder-gear-shaft drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_cylinder_gear_shaft as part
import cylinder_gear_shaft_spec
import draw_cylinder_gear_shaft as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cylinder-gear-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cylinder-gear-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cylinder-gear-shaft_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cylinder_gear_shaft"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cylinder_gear_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*cylinder_gear_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LENGTH) == (
        cylinder_gear_shaft_spec.SHAFT_DIA,
        cylinder_gear_shaft_spec.SHAFT_LENGTH,
    )


def test_linked_notes_define_remaining_arbor_operations() -> None:
    notes = cylinder_gear_shaft_spec.DRAWING_NOTES
    assert drawing.DIMENSION_CALLOUTS["ShaftDia"] == "+0.00/-0.02"
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "+/-0.25"
    # M6.2 keyway refutation: the 20 gears spin at different speeds and run
    # FREE on the fixed arbor, so the print must forbid the legacy keyseat.
    assert "KEYSEAT" in notes
    assert "RUN FREE" in notes
    assert "CENTRE MARKS" not in notes
    assert notes.splitlines() == [
        "TURN OR CENTRELESS-GRIND FULL LENGTH; NO FLATS, STEPS OR KEYSEAT.",
        "STATIONARY ARBOR: 20 CYLINDER GEARS RUN FREE ON THE FULL O.D.; "
        "CLAMPED IN PEDESTALS AT BOTH ENDS.",
    ]
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_profile_view_is_rotated_axis_horizontal() -> None:
    # The arbor is modelled axis-along-+Y, so the "*Front" profile must be
    # rotated a quarter turn to read axis-horizontal on the sheet.
    assert drawing.PROFILE_ROTATION == -math.pi / 2.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Top"' in source
    assert "_rotate_view(adapter, profile, PROFILE_ROTATION" in source


def test_native_gdt_controls_arbor_form_orientation_and_finish() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert "edge_xy=end_top" in source
    assert "symbol_xy=(END_CENTER[0], END_CENTER[1] + 0.024)" in source
    assert "position_tolerance_m=0.0001" in source
    assert source.count("add_feature_control_frame(") == 2
    assert source.count('characteristic="cylindricity"') == 1
    assert source.count('characteristic="perpendicularity"') == 1
    assert source.count("add_surface_finish(") == 1


def test_view_scales_and_precision_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 1)") == 1
    assert "scale=(2, 1)" in source
    assert cylinder_gear_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    # The pictorial is half-scale against a 1:1 title block, so it carries its
    # own scale label (codex machinist review).
    assert drawing.ISO_SCALE == (1, 2)
    assert cylinder_gear_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    # 3/8 in = 9.525 exactly: the diameter must display 3 decimals so the
    # view can never contradict the exact inch conversion.
    assert drawing.DIMENSION_PRECISION == {"ShaftDia": 3}
    assert "set_dimension_precision(adapter, end_annotations" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cylinder-gear-shaft")
    expected = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == expected
    assert config["material_specification"] == expected
    assert config["finish"]
    assert int(config["quantity"]) == 1

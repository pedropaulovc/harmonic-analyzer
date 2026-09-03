"""Offline contracts for the cylinder-gear-shaft drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a plain stationary
arbor carries no datums or frames; its running fit is the band on the model
diameter, plus one Ra on the OD the 20 cylinder gears run free on. Diameter,
length and Ra all read on the axis-horizontal profile view (rule 7).
"""

from __future__ import annotations

import math
from pathlib import Path

import build_cylinder_gear_shaft as part
import cylinder_gear_shaft_spec
import draw_cylinder_gear_shaft as drawing
import _fit_limits
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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


def test_diameter_length_and_finish_read_on_the_profile_view() -> None:
    # Machinist review 2026-09-02: the turned diameter was dimensioned on the
    # end view. Policy rule 7 puts it on the profile; the end view keeps
    # nothing and is never curated (SolidWorks inserts each marked dimension
    # into one view only).
    assert drawing.END_KEEP == {}
    assert set(drawing.PROFILE_KEEP) == {"ShaftDia", "Depth"}
    assert drawing.PROFILE_KEEP["ShaftDia"][0] < drawing.LEFT_END_X
    source = _source()
    assert "curate_view_dimensions(\n        adapter, end" not in source
    assert "set_dimension_precision(adapter, profile_annotations" in source
    # The Ra anchors on the profile's flank silhouette, not the end circle.
    assert "add_surface_finish(\n        adapter,\n        profile," in source
    assert 'entity_type="SILHOUETTE"' in source


def test_running_fit_and_length_band_ride_the_model_dimensions() -> None:
    assert drawing.DIMENSION_CALLOUTS == {}
    assert cylinder_gear_shaft_spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert cylinder_gear_shaft_spec.LENGTH_TOLERANCE_MM == 0.25
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("Shaft", "Depth"): "LENGTH_TOLERANCE_MM",
    }


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cylinder_gear_shaft_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # M6.2 keyway refutation: the 20 gears spin at different speeds and run
    # FREE on the fixed arbor, so the print must forbid the legacy keyseat.
    assert "NO KEYSEAT" in notes
    assert "CENTRES OK" in notes
    # The turned-or-ground finish and "no flats or steps" are the title block
    # and the views (review 2026-09-02); no design-intent narration either.
    assert "TURN OR GRIND" not in notes
    assert "NO FLATS" not in notes
    for banned in ("RUN FREE", "STATIONARY", "WITHIN", "+/-", "UOS", "DATUM", "MHA-"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_profile_view_is_rotated_axis_horizontal() -> None:
    # The arbor is modelled axis-along-+Y, so the "*Front" profile must be
    # rotated a quarter turn to read axis-horizontal on the sheet.
    assert drawing.PROFILE_ROTATION == -math.pi / 2.0
    source = _source()
    assert '"*Top"' in source
    assert "_rotate_view(adapter, profile, PROFILE_ROTATION" in source


def test_print_carries_no_gdt_and_one_running_finish() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert cylinder_gear_shaft_spec.PART_DATUMS == ()
    assert cylinder_gear_shaft_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(cylinder_gear_shaft_spec, "GEOMETRIC_TOLERANCES_MM")
    # The gears run free on the OD, so it alone carries a roughness symbol
    # (the row itself is pinned fleet-wide by test_surface_finish_ownership_a).
    (control,) = cylinder_gear_shaft_spec.SURFACE_FINISHES
    assert control.key == "arbor_bearing"
    assert control.roughness_um == 1.6
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "arbor_bearing")' in source
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (end, profile):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_and_precision_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert source.count("scale=(1, 1)") == 1
    assert "scale=(2, 1)" in source
    assert cylinder_gear_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    # The pictorial is half-scale against a 1:1 title block, so it carries its
    # own scale label (codex machinist review).
    assert drawing.ISO_SCALE == (1, 2)
    assert cylinder_gear_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    # Only the fitted diameter (3/8 in = 9.525, SHAFT_H band) prints three
    # decimals; everything else stays at the two-place block tolerance.
    assert drawing.DIMENSION_PRECISION == {"ShaftDia": 3}


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

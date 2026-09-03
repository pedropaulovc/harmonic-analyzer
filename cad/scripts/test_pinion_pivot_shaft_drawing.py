"""Offline contracts for the pinion-torque-shaft drawing.

A plain shaft is not on the GD&T allowlist
(cad/docs/drawing-simplicity-policy.md): no datums, no frames; one roughness
symbol on the journal the swing straps rock on; diameter, body length, the
overall reference and the crown callout all on the side view (rule 7); one
line of notes.
"""

from __future__ import annotations

from pathlib import Path

import pinion_pivot_shaft_spec
import draw_pinion_pivot_shaft as drawing
import build_pinion_pivot_shaft as shaft
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_surface_finish_is_on_the_journal_only() -> None:
    (control,) = pinion_pivot_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_pivot_shaft_spec.SHAFT_DIA
    part_source = Path(shaft.__file__).read_text(encoding="utf-8")
    source = _source()
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in source
    # Anchored on the flank silhouette like its sibling shafts, not a FACE
    # pick whose leader ran across the body (2026-09-02 render).
    assert 'entity_type="SILHOUETTE"' in source
    assert 'entity_type="FACE"' not in source
    assert "roughness_ra=" not in source


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
    assert pinion_pivot_shaft_spec.OVERALL_LEN == 194.4


def test_diameter_and_body_length_read_on_the_side_view() -> None:
    # Policy rule 7: the diameter stands at the side view's right end, not on
    # the end view; the end view keeps nothing and is never curated
    # (SolidWorks inserts each marked dimension into one view only).
    assert drawing.FRONT_KEEP == {}
    assert set(drawing.RIGHT_KEEP) == {"ShaftDia", "Depth"}
    assert drawing.RIGHT_KEEP["ShaftDia"][0] > drawing.RIGHT_END_X
    source = _source()
    assert "curate_view_dimensions(\n        adapter, front" not in source
    assert "set_dimension_precision(adapter, right_annotations" in source
    assert drawing.DIMENSION_PRECISION == {"ShaftDia": 3}


def test_overall_reference_and_crown_callout_are_on_the_view() -> None:
    # Review 2026-09-02: the overall had to be derived from both crowns, and
    # the SR4.80 geometry was buried in the note block.
    source = _source()
    assert 'label="overall length reference"' in source
    assert 'entity_types=("VERTEX", "VERTEX")' in source
    assert '_early_bound(overall, "IDisplayDimension").GetAnnotation()' in source
    assert "set_reference_dimension(" in source
    assert source.count("model_point_in_view(") == 2
    assert source.count("add_attached_note(") == 1
    assert "text=CROWN_NOTE," in source
    assert pinion_pivot_shaft_spec.CROWN_NOTE.split("\n") == [
        "2X SPHERICAL CROWN SR4.80",
        "(1.20) HIGH; ROOT CIRCLE SHARP, NO CHAMFER",
    ]


def test_sheet_runs_at_1_to_1_with_4_to_1_end_view_and_1_to_2_iso() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_SCALE == (1, 2)
    source = _source()
    assert "scale=(4, 1)" in source  # the end-view override
    assert pinion_pivot_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_pivot_shaft_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "SHAFTING OK AS RECEIVED" in notes
    # The crown geometry left the block for a leadered callout on the view.
    assert "CROWN" not in notes
    for banned in ("DATUM", "PROFILE", "EXEMPT", "TITLE-BLOCK", "+/-", "LINEAR", "X.XX"):
        assert banned not in notes, banned
    assert " BA " not in f" {notes} "
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_and_the_band_rides_the_model_diameter() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "WITHIN" not in source
    assert not hasattr(pinion_pivot_shaft_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_pivot_shaft_spec, "GEOMETRIC_CONTROLS")
    assert model_toleranced_dimensions(shaft) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("Shaft", "Depth"): "SHAFT_LENGTH_TOLERANCE_MM",
    }
    assert "ShaftDia" not in drawing.DIMENSION_CALLOUTS
    assert "CROWN ROOT" in drawing.DIMENSION_CALLOUTS["Depth"]


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

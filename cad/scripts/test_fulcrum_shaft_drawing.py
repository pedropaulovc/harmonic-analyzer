"""Offline contracts for the fulcrum-shaft drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a plain bearing shaft
carries no datums or frames; its running fit is the band on the model
diameter, plus one Ra on the OD the channel levers rock on. Diameter, length
and Ra all read on the side view (rule 7: a turned part as it sits in the
lathe).
"""

from __future__ import annotations

from pathlib import Path

import build_fulcrum_shaft as part
import draw_fulcrum_shaft as drawing
import fulcrum_shaft_spec
import _fit_limits
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/fulcrum-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/fulcrum-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/fulcrum-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["fulcrum_shaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is fulcrum_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*fulcrum_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LENGTH) == (
        fulcrum_shaft_spec.SHAFT_DIA,
        fulcrum_shaft_spec.SHAFT_LENGTH,
    )


def test_diameter_length_and_finish_read_on_the_side_view() -> None:
    # Machinist review 2026-09-02: the principal turned feature was only
    # called out on the end view. Policy rule 7 puts the diameter on the side
    # view; the end view keeps nothing and is never curated (SolidWorks
    # inserts each marked dimension into one view only).
    assert drawing.FRONT_KEEP == {}
    assert set(drawing.RIGHT_KEEP) == {"ShaftDia", "Depth"}
    assert drawing.RIGHT_KEEP["ShaftDia"][0] < drawing.LEFT_END_X
    source = _source()
    assert "curate_view_dimensions(\n        adapter, front" not in source
    assert "set_dimension_precision(adapter, right_annotations" in source
    assert drawing.DIMENSION_PRECISION == {"ShaftDia": 3}
    # The Ra anchors on the side view's flank silhouette, not the end circle.
    assert "add_surface_finish(\n        adapter,\n        right," in source
    assert 'entity_type="SILHOUETTE"' in source


def test_running_fit_is_the_band_on_the_model_diameter() -> None:
    assert drawing.DIMENSION_CALLOUTS == {}
    assert fulcrum_shaft_spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("SectionProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)"
    }
    clearance_min = 6.50 - fulcrum_shaft_spec.SHAFT_DIA
    clearance_max = clearance_min + 0.02 + 0.03
    assert round(clearance_min, 2) == 0.15
    assert round(clearance_max, 2) == 0.20


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = fulcrum_shaft_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "CENTRES OK" in notes  # a between-centres shaft (Harvey)
    # "Turn or grind full length; no flats or steps" restated the title-block
    # finish and the plain cylinder the views show (review 2026-09-02).
    assert "TURN OR GRIND" not in notes
    assert "NO FLATS" not in notes
    for banned in ("WITHIN", "+/-", "UOS", "DATUM", "MHA-", "X.XX", "DEEP MAX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_and_one_running_finish() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert fulcrum_shaft_spec.PART_DATUMS == ()
    assert fulcrum_shaft_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(fulcrum_shaft_spec, "GEOMETRIC_TOLERANCES_MM")
    # The levers rock on the OD, so it alone carries a roughness symbol.
    (control,) = fulcrum_shaft_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == fulcrum_shaft_spec.SHAFT_DIA
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in source
    assert "roughness_ra=" not in source
    # The source model deliberately does not persist a native finish symbol:
    # that symbol exported as a detached horizontal stroke beside the one
    # complete, view-owned Ra callout below.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=" not in part_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    # Only the side view is 1:1; the isometric renders at ISO_SCALE so its
    # outline stays inside the right zone border (see draw_fulcrum_shaft).
    assert source.count("scale=(1, 1)") == 1
    assert "scale=(2, 1)" in source
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert fulcrum_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source
    # An off-sheet-scale view needs its OWN scale label or the title block's 1:1
    # misstates it (codex #334).
    assert fulcrum_shaft_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("fulcrum-shaft")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

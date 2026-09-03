"""Offline contracts for the pivot-shaft drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a plain bearing shaft
carries no datums or frames; its running fit is the band on the model
diameter, plus one Ra on the OD the rocker arms swing on. Diameter and length
both read on the side view (rule 7: a turned part as it sits in the lathe).
"""

from __future__ import annotations

from pathlib import Path

import build_pivot_shaft as part
import draw_pivot_shaft as drawing
import pivot_shaft_spec
import _fit_limits
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-shaft.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-shaft.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-shaft_drawing.png")
    assert DRAWINGS_BY_NAME["pivot_shaft"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pivot_shaft_spec.DRAWING_DIMENSIONS
    marked = set().union(*pivot_shaft_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LENGTH) == (
        pivot_shaft_spec.SHAFT_DIA,
        pivot_shaft_spec.SHAFT_LENGTH,
    )


def test_diameter_and_length_read_on_the_side_view() -> None:
    # Policy rule 7: diameters on the side view, not leader-piled on the end
    # view. The end view keeps nothing and is never curated (SolidWorks
    # inserts each marked dimension into one view only).
    assert drawing.FRONT_KEEP == {}
    assert set(drawing.RIGHT_KEEP) == {"ShaftDia", "Depth"}
    assert drawing.RIGHT_KEEP["ShaftDia"][0] < drawing.LEFT_END_X
    source = _source()
    assert "curate_view_dimensions(\n        adapter, front" not in source
    assert "set_dimension_precision(adapter, right_annotations" in source
    assert drawing.DIMENSION_PRECISION == {"ShaftDia": 3}


def test_running_fit_and_length_band_ride_the_model_dimensions() -> None:
    assert drawing.DIMENSION_CALLOUTS == {}
    assert pivot_shaft_spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert pivot_shaft_spec.LENGTH_TOLERANCE_MM == 0.25
    assert model_toleranced_dimensions(part) == {
        ("SectionProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
        ("Shaft", "Depth"): "LENGTH_TOLERANCE_MM",
    }
    clearance_min = 6.50 - pivot_shaft_spec.SHAFT_DIA
    clearance_max = clearance_min + 0.02 + 0.03
    assert round(clearance_min, 2) == 0.15
    assert round(clearance_max, 2) == 0.20


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pivot_shaft_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "CENTRES OK" in notes  # a between-centres shaft (Harvey)
    # "Turn or grind full length; no flats or steps" restated the title-block
    # finish and the plain cylinder the views show (review 2026-09-02).
    assert "TURN OR GRIND" not in notes
    assert "NO FLATS" not in notes
    # The length tolerance rides the Depth dimension, never a detached note.
    for banned in ("LENGTH +/-", "WITHIN", "+/-", "UOS", "DATUM", "MHA-", "X.XX"):
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
    assert pivot_shaft_spec.PART_DATUMS == ()
    assert pivot_shaft_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(pivot_shaft_spec, "GEOMETRIC_TOLERANCES_MM")
    # The rockers swing on the OD, so it alone carries a roughness symbol, on
    # the side view's flank silhouette.
    (control,) = pivot_shaft_spec.SURFACE_FINISHES
    assert control.key == "pivot_bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pivot_shaft_spec.SHAFT_DIA
    assert source.count("add_surface_finish(") == 1
    sheet_source = "".join(source.split())
    assert (
        'control=surface_finish_by_key(SURFACE_FINISHES,"pivot_bearing")'
        in sheet_source
    )
    assert 'entity_type="SILHOUETTE"' in source
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = "".join(Path(part.__file__).read_text(encoding="utf-8").split())
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert source.count("scale=(1, 1)") == 2
    assert "scale=(2, 1)" in source
    assert pivot_shaft_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pivot-shaft")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

"""Offline contracts for the pinion-arbor drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a plain bearing arbor
carries no datums or frames; its running fit is the band on the model
diameter, plus one Ra on the OD that turns in the strap bores. Diameter, shank
length and Ra read on the side view; the crown is enlarged in DETAIL B; the
true overall is a conspicuous reference (rule 7).
"""

from __future__ import annotations

from pathlib import Path

import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_spec
import _fit_limits
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_arbor"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pinion_arbor_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_arbor_spec.DRAWING_DIMENSIONS.values())
    imported = set(drawing.RIGHT_KEEP)
    assert imported == marked - {"CapSagDim"}
    assert "CapSagDim" not in _source()
    assert (drawing.SHAFT_DIA, drawing.SHAFT_LEN, drawing.CAP_SAG) == (
        pinion_arbor_spec.SHAFT_DIA,
        pinion_arbor_spec.SHAFT_LEN,
        pinion_arbor_spec.CAP_SAG,
    )
    assert pinion_arbor_spec.OVERALL_LEN == 227.45


def test_diameter_and_shank_length_read_on_the_side_view() -> None:
    # Policy rule 7: the diameter stands at the flat right end of the side
    # view, not on the end view; the end view keeps nothing and is never
    # curated (SolidWorks inserts each marked dimension into one view only).
    assert set(drawing.RIGHT_KEEP) == {"ShaftDia", "Depth"}
    assert drawing.RIGHT_KEEP["ShaftDia"][0] > drawing.RIGHT_END_X
    source = _source()
    assert "curate_view_dimensions(\n        adapter, front" not in source
    assert "set_dimension_precision(adapter, right_annotations" in source
    assert drawing.DIMENSION_PRECISION == {"ShaftDia": 3}
    # 226.25 stops at the crown root, and says so (review 2026-09-02: it
    # visually read as the overall).
    assert drawing.DIMENSION_CALLOUTS == {"Depth": "TO CROWN ROOT"}


def test_crown_is_enlarged_and_its_unavailable_dimension_becomes_a_spec_note() -> None:
    # The crown radius derives from the sagitta: R = (r^2 + s^2) / 2s.
    r, s = pinion_arbor_spec.SHAFT_DIA / 2.0, pinion_arbor_spec.CAP_SAG
    assert abs(pinion_arbor_spec.CAP_R - (r * r + s * s) / (2.0 * s)) < 1e-9
    assert drawing.DETAIL_SCALE == (4, 1)
    assert drawing.CROWN_GEOMETRY_NOTE == (
        f"DETAIL B CROWN\nSR{pinion_arbor_spec.CAP_R:.2f}; "
        f"{pinion_arbor_spec.CAP_SAG:.2f} HIGH"
    )
    source = _source()
    assert source.count("create_detail_view(") == 1
    assert 'detail_label="B"' in source
    assert 'view_label="detail"' not in source
    assert "add_note(adapter, CROWN_GEOMETRY_NOTE" in source
    # The drawing note carries the geometry; manufacturing prose stays process-only.
    assert "SR7.27" not in pinion_arbor_spec.DRAWING_NOTES


def test_overall_length_is_a_conspicuous_reference() -> None:
    source = _source()
    assert 'label="overall length reference"' in source
    assert 'entity_types=("VERTEX", "EDGE")' in source
    assert '_early_bound(overall, "IDisplayDimension").GetAnnotation()' in source
    assert "set_reference_dimension(" in source
    assert "model_point_in_view(" in source


def test_running_fit_is_the_band_on_the_model_diameter() -> None:
    assert pinion_arbor_spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)"
    }


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_arbor_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "CENTRES OK" in notes
    assert "CROWN" in notes
    # "Turn or grind full length; no flats or steps" restated the title-block
    # finish and the continuous cylinder the view shows (review 2026-09-02).
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
    assert pinion_arbor_spec.PART_DATUMS == ()
    assert pinion_arbor_spec.GEOMETRIC_CONTROLS == ()
    assert not hasattr(pinion_arbor_spec, "GEOMETRIC_TOLERANCES_MM")
    # The arbor turns in the strap bores, so its OD alone carries a roughness
    # symbol, on the side view's flank silhouette.
    (control,) = pinion_arbor_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_arbor_spec.SHAFT_DIA
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in source
    assert 'entity_type="SILHOUETTE"' in source
    assert "roughness_ra=" not in source
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
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
    assert "scale=(2, 1)" in source
    assert source.count("scale=(1, 1)") == 1
    assert "scale=(1, 2)" in source  # 226-long arbor: half-scale isometric
    assert "scale=DETAIL_SCALE" in source
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

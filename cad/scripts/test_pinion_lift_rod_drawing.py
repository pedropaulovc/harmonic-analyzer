"""Offline contracts for the pinion-lift-rod drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a plain bearing rod
carries no datums or frames; its running fit is the band on the model
diameter, plus one Ra on the OD that spins in the pivot-block bores. Diameter,
shank length and Ra read on the side view; the crown is a note leadered to
the crowned end; the true overall is a conspicuous reference (rule 7).
"""

from __future__ import annotations

from pathlib import Path

import build_pinion_lift_rod as part
import draw_pinion_lift_rod as drawing
import pinion_lift_rod_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lift-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lift-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-lift-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_lift_rod"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pinion_lift_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_lift_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.ROD_DIA, drawing.ROD_LEN, drawing.CAP_SAG) == (
        pinion_lift_rod_spec.ROD_DIA,
        pinion_lift_rod_spec.ROD_LEN,
        pinion_lift_rod_spec.CAP_SAG,
    )
    assert pinion_lift_rod_spec.OVERALL_LEN == 203.2


def test_diameter_and_shank_length_read_on_the_side_view() -> None:
    # Policy rule 7: the diameter stands at the flat right end of the side
    # view, not on the end view; the end view keeps nothing and is never
    # curated (SolidWorks inserts each marked dimension into one view only).
    assert drawing.FRONT_KEEP == {}
    assert set(drawing.RIGHT_KEEP) == {"RodDia", "Depth"}
    assert drawing.RIGHT_KEEP["RodDia"][0] > drawing.RIGHT_END_X
    source = _source()
    assert "curate_view_dimensions(\n        adapter, front" not in source
    assert "set_dimension_precision(adapter, right_annotations" in source
    assert drawing.DIMENSION_PRECISION == {"RodDia": 3}
    # 202.00 stops at the crown root, and says so (review 2026-09-02: it
    # read like the overall).
    assert drawing.DIMENSION_CALLOUTS == {"Depth": "TO CROWN ROOT"}


def test_overall_length_is_a_conspicuous_reference() -> None:
    source = _source()
    assert 'label="overall length reference"' in source
    assert 'entity_types=("VERTEX", "EDGE")' in source
    assert '_early_bound(overall, "IDisplayDimension").GetAnnotation()' in source
    assert "set_reference_dimension(" in source
    assert "model_point_in_view(" in source


def test_crown_is_called_out_from_the_crowned_end() -> None:
    # The crown's sketch dims live on the Top plane, outside every placed
    # view, so it is conveyed as a note -- ATTACHED to the apex with a leader
    # (review 2026-09-02: "back end" in the block made the reader infer the
    # left end). Spherical radius consistent with the sagitta/diameter pair,
    # every number with a decimal, at the block tolerance.
    dome_radius = (
        pinion_lift_rod_spec.ROD_DIA**2 / 4.0 + pinion_lift_rod_spec.CAP_SAG**2
    ) / (2.0 * pinion_lift_rod_spec.CAP_SAG)
    assert round(dome_radius, 2) == pinion_lift_rod_spec.CAP_R == 4.8
    assert pinion_lift_rod_spec.CROWN_NOTE.split("\n") == [
        "CROWN SR4.80 X 1.20 HIGH",
        "BLEND SMOOTH, NO STEP",
    ]
    source = _source()
    assert source.count("add_attached_note(") == 1
    assert "text=CROWN_NOTE," in source
    assert 'entity_type="VERTEX"' in source
    assert "CROWN" not in pinion_lift_rod_spec.DRAWING_NOTES


def test_running_fit_and_length_band_ride_the_model_dimensions() -> None:
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "RodDia"): "*deviations(ROD_DIA_BAND)",
        ("Rod", "Depth"): "ROD_LENGTH_TOLERANCE_MM",
    }


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = pinion_lift_rod_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "SHAFTING OK AS RECEIVED" in notes
    # "Turn or grind the OD full length; no flats or steps" restated the
    # title-block finish and the plain cylinder the views show (review
    # 2026-09-02); the crown moved to a leadered callout on the view.
    assert "TURN OR GRIND" not in notes
    assert "NO FLATS" not in notes
    for banned in ("REF", "LENGTH +/-", "+/-", "WITHIN", "UOS", "DATUM", "X.XX"):
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
    assert not hasattr(pinion_lift_rod_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(pinion_lift_rod_spec, "GEOMETRIC_CONTROLS")
    # The rod spins in the pivot-block bores, so its OD alone carries a
    # roughness symbol, on the side view's flank silhouette.
    (control,) = pinion_lift_rod_spec.SURFACE_FINISHES
    assert control.key == "bearing"
    assert control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_lift_rod_spec.ROD_DIA
    assert source.count("add_surface_finish(") == 1
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bearing")' in source
    assert 'entity_type="SILHOUETTE"' in source
    assert "roughness_ra=" not in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = _source()
    assert "scale=(2, 1)" in source  # end view 2:1
    assert "scale=(1, 1)" in source  # side view true scale
    assert "scale=(1, 2)" in source  # iso reduced so the long rod clears
    assert pinion_lift_rod_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert 'add_property_linked_note(adapter, "End View Note"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pinion-lift-rod")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

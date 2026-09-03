"""Offline contracts for the lever-bushing drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a stationary spacer
carries no datums, frames or roughness symbols; the reamed bore keeps its fit
band on the model dimension and says REAM on the callout; OD, bore and length
all read on SECTION A-A (rule 7), the end view carries only the cutting line.
"""

from __future__ import annotations

from pathlib import Path

import build_lever_bushing as part
import draw_lever_bushing as drawing
import lever_bushing_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/lever-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/lever-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/lever-bushing_drawing.png")
    assert DRAWINGS_BY_NAME["lever_bushing"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is lever_bushing_spec.DRAWING_DIMENSIONS
    marked = set().union(*lever_bushing_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.SECTION_KEEP_OFFSETS)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert set(drawing.DIMENSION_PRECISION) <= kept
    assert (drawing.OUTER_DIA, drawing.LENGTH) == (
        lever_bushing_spec.OUTER_DIA,
        lever_bushing_spec.LENGTH,
    )


def test_every_dimension_reads_on_the_axial_section() -> None:
    # Machinist review 2026-09-02: both diameters sat on the end view and the
    # bore leader crossed the OD dimension line. The side view is now SECTION
    # A-A through the axis, carrying OD, bore and length; the end view keeps
    # nothing and is never curated (SolidWorks inserts each marked dimension
    # into one view only).
    assert drawing.END_KEEP == {}
    assert set(drawing.SECTION_KEEP_OFFSETS) == {"OuterDia", "BoreDia", "Depth"}
    # OD to the right, bore to the left (its REAM callout clear of the end
    # view), length above -- no two share a side.
    assert drawing.SECTION_KEEP_OFFSETS["OuterDia"][0] > 0.0
    assert drawing.SECTION_KEEP_OFFSETS["BoreDia"][0] < 0.0
    assert drawing.SECTION_KEEP_OFFSETS["Depth"][1] > drawing.END_RADIUS
    # The cutting line runs vertically through the end view's centre.
    (x0, y0), (x1, y1) = drawing.SECTION_LINE
    assert x0 == x1 == drawing.END_CENTER[0]
    assert y0 > drawing.END_CENTER[1] + drawing.END_RADIUS
    assert y1 < drawing.END_CENTER[1] - drawing.END_RADIUS
    source = _source()
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert "model_point_in_view(" in source
    assert "curate_view_dimensions(\n        adapter, end" not in source
    assert 'place_view(adapter, str(SOURCE), "*Right"' not in source


def test_bore_says_ream_and_keeps_its_model_fit_band() -> None:
    # Harvey #13: the callout says REAM; the band stays on the model dimension
    # and prints three decimals (policy rule 2).
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}
    assert drawing.DIMENSION_PRECISION == {"BoreDia": 3}
    assert lever_bushing_spec.BORE_DIA_BAND == (0.03, 0.00)
    # The length band is functional, not mundane: 19 stacked spacers set the
    # channel pitch, and the block's +/-0.51 would put ~10 mm on the stack.
    assert lever_bushing_spec.LENGTH_TOLERANCE_MM == 0.03
    assert model_toleranced_dimensions(part) == {
        ("AnnulusProfile", "BoreDia"): "*deviations(BORE_DIA_BAND)",
        ("Bushing", "Depth"): "LENGTH_TOLERANCE_MM",
    }
    clearance_min = lever_bushing_spec.BORE_DIA - 6.35
    clearance_max = clearance_min + 0.03 + 0.02
    assert round(clearance_min, 2) == 0.15
    assert round(clearance_max, 2) == 0.20


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = lever_bushing_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The one note says what the stack is for (a MATES WITH line); chucking
    # and batching are the shop's call (review 2026-09-02).
    assert notes.startswith("MATES WITH MHA-031")
    assert "19 STACKED" in notes
    assert "ONE SETTING" not in notes
    assert "TOGETHER" not in notes
    # The process rides the bore callout, not the notes; nothing the title
    # block or a dimension already says.
    for banned in ("REAM", "DRILL", "WITHIN", "+/-", "UOS", "DATUM", "X.XX"):
        assert banned not in notes, banned
    source = _source()
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_print_carries_no_gdt_or_finish_symbols() -> None:
    """A stationary spacer: no datums, no frames, no Ra (policy rules 3, 5)."""
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert lever_bushing_spec.PART_DATUMS == ()
    assert lever_bushing_spec.GEOMETRIC_CONTROLS == ()
    assert lever_bushing_spec.SURFACE_FINISHES == ()
    assert not hasattr(lever_bushing_spec, "GEOMETRIC_TOLERANCES_MM")
    # The part build keeps its author_part_pmi call shape on the empty tuples.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(" in part_source
    assert "datums=PART_DATUMS" in part_source
    assert "controls=GEOMETRIC_CONTROLS" in part_source
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert "roughness_ra=" not in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (end, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_sheet_and_views_pin_scale() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert _source().count("scale=(4, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lever-bushing")
    material = "UNS C36000 H02 per ASTM B16/B16M-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    assert config["finish"]
    assert int(config["quantity"]) == 19

"""Offline contracts for the cone-tip-adjuster drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_cone_tip_adjuster as part
import cone_tip_adjuster_spec
import draw_cone_tip_adjuster as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-adjuster.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-adjuster.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-adjuster_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_adjuster"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_adjuster_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_adjuster_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.END_KEEP)
        | set(drawing.CUP_KEEP)
        | set(drawing.SECTION_KEEP_MODEL_MM)
    )
    assert kept == marked
    assert marked == {
        "BodyDiaDim",
        "BodyLenDim",
        "CupDiaDim",
        "CupDepth",
        "SlotWDim",
        "SlotDepth",
    }
    # Both blind depths are dimensioned in the axial section, never to the
    # elevation's hidden floor line.
    assert set(drawing.SECTION_KEEP_MODEL_MM) == {"CupDepth", "SlotDepth"}
    assert "CupDepth" not in drawing.FRONT_KEEP
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "DriverSlot", ["SlotDepth"])' in part_source


def test_cup_and_slot_are_dimensioned_in_an_axial_section() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view(" in source
    assert 'section_label="A"' in source
    assert "line_start=(FRONT_CENTER[0], FRONT_CENTER[1] - half_len)" in source
    # The section claims its dimensions before the parent view is curated.
    assert source.index('view_label="section"') < source.index('view_label="front"')
    assert "model_point_in_view(" in source
    # The cut is the x = 0 plane (a vertical line in the front view), so the
    # sideways offset is along model Z, never X (which projects onto the axis).
    assert "(0.0, y_mm / 1000.0, z_mm / 1000.0)" in source
    assert drawing.SECTION_CENTER == (0.205, 0.210)
    assert drawing.SECTION_CENTER[1] - drawing.CUP_CENTER[1] >= 0.100
    assert drawing.SECTION_LINE_OVERSHOOT > 0.0
    assert "for view in (front, end, cup, section):\n        set_hidden_lines_visible" in source


def test_thread_callout_is_the_catalog_thread() -> None:
    assert cone_tip_adjuster_spec.THREAD == "5/16-18"
    assert drawing.DIMENSION_CALLOUTS["BodyDiaDim"] == "5/16-18 UNC"
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "InsertCosmeticThread3" in part_source
    assert "SPEC.thread" in part_source
    assert '"5/16-18"' not in part_source
    assert "IEntity" in part_source
    assert "import_cosmetic_threads" in drawing_source
    assert "set_reference_dimensions(adapter, front_annotations" in drawing_source
    assert cone_tip_adjuster_spec.BODY_DIA == 6.2
    assert part.CHAMFER == drawing.CHAMFER == 0.4
    assert 'name_last_feature(adapter, "ThreadStartChamfers")' in part_source
    assert "await adapter.add_chamfer(" in part_source


def test_chamfers_are_flagged_from_the_rim_not_the_note_block() -> None:
    assert cone_tip_adjuster_spec.CHAMFER_NOTE == "2X 0.40 X 45<MOD-DEG>"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "text=CHAMFER_NOTE" in source
    assert "entity=_chamfer_rim(adapter, front)" in source
    assert "center_y_mm = BODY_LEN - CHAMFER" in source


def test_slotted_south_rim_reduces_only_its_chamfer_arc() -> None:
    radius = part.BODY_DIA / 2.0
    full = math.pi * part.CHAMFER**2 * (radius - part.CHAMFER / 3.0)
    slotted = part._slotted_rim_chamfer_volume(
        radius, part.CHAMFER, part.SLOT_W
    )
    assert 0.80 * full < slotted < 0.90 * full


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = cone_tip_adjuster_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "5/16-18" not in notes  # rides the body-diameter callout
    assert "11.0 MIN" in notes  # the usable thread length, one place
    assert "11.00 MIN" not in notes
    assert "(6.20)" in notes  # why the reference diameter is not the thread OD
    # Chamfers, cup and slot ride the views; the thread class rides the block.
    for banned in (
        "CHAMFER", "CUP", "SLOT", "2A LIMITS", "+/-", "DATUM", "FCF", "UOS",
        "DIMENSIONS IN", "MATERIAL", "OXIDE", "X.XX",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rules 3-5: a set screw is not on the GD&T
    # allowlist and nothing runs on it.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(cone_tip_adjuster_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(cone_tip_adjuster_spec, "SURFACE_FINISHES")
    assert 'add_note(adapter, "SLOT END VIEW"' in source
    assert 'add_note(adapter, "CUP END VIEW"' in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, end, cup, section):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(4, 1)") == 4  # elevation + both end views + section
    assert source.count("scale=(2, 1)") == 1  # enlarged pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-tip-adjuster")
    assert "12L14" in str(config["material_specification"])
    assert "12L14" in str(config["material"])
    assert config["finish"]
    assert "fit_class" not in config
    assert int(config["quantity"]) == 1


def test_only_the_fitted_features_are_toleranced_on_the_model() -> None:
    """No fit or size band may reach the print as frozen callout text.

    ``set_dimension_callouts`` appends its string via ``SetText``; SolidWorks
    prints it verbatim beside a natively-rendered numeral and never re-renders
    it, so "+/-0.10" survives the mm->inch flip in issue #290 unchanged and
    reads as inches. Only NON-tolerance annotation is allowed to stay -- and
    only the two fitted features (slot width, cup bore) carry a band at all:
    the length and cup depth of a hand-adjusted screw ride the title block.
    """
    assert model_toleranced_dimensions(part) == {
        ("SlotProfile", "SlotWDim"): "GENERAL_TOL_MM",
        ("CupProfile", "CupDiaDim"): "*deviations(CUP_DIA_BAND)",
    }
    # What remains on the sheet is annotation, not specification: a thread
    # designation and the cup's process.
    assert set(drawing.DIMENSION_CALLOUTS) == {"BodyDiaDim", "CupDiaDim"}
    assert cone_tip_adjuster_spec.THREAD in drawing.DIMENSION_CALLOUTS["BodyDiaDim"]
    assert drawing.DIMENSION_CALLOUTS["CupDiaDim"] == "END MILL, FLAT FLOOR"

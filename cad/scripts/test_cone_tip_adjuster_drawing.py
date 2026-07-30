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
    kept = set(drawing.FRONT_KEEP) | set(drawing.END_KEEP) | set(drawing.CUP_KEEP)
    assert kept == marked
    assert marked == {
        "BodyDiaDim",
        "BodyLenDim",
        "CupDiaDim",
        "CupDepth",
        "SlotWDim",
    }
    # Blind depth is parallel to the screw axis, so its native model dimension
    # is visible in the elevation and cannot be imported into the axial end view.
    assert "CupDepth" in drawing.FRONT_KEEP
    assert "CupDepth" not in drawing.CUP_KEEP


def test_thread_callout_is_the_catalog_thread() -> None:
    assert cone_tip_adjuster_spec.THREAD == "5/16-18"
    assert drawing.DIMENSION_CALLOUTS["BodyDiaDim"] == "5/16-18 UNC-2A"
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


def test_slotted_south_rim_reduces_only_its_chamfer_arc() -> None:
    radius = part.BODY_DIA / 2.0
    full = math.pi * part.CHAMFER**2 * (radius - part.CHAMFER / 3.0)
    slotted = part._slotted_rim_chamfer_volume(
        radius, part.CHAMFER, part.SLOT_W
    )
    assert 0.80 * full < slotted < 0.90 * full


def test_notes_specify_thread_cup_and_slot_without_title_block_duplicates() -> None:
    notes = cone_tip_adjuster_spec.DRAWING_NOTES
    assert "5/16-18" not in notes
    assert "11.00 MIN USABLE FULL-FORM THREAD" in notes
    assert "CUP" in notes  # the shaft-tip seating cup
    assert "SLOT" in notes  # the driver slot
    assert "MATERIAL" not in notes
    assert "OXIDE" not in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    assert "OVERALL LENGTH" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "POSITION FCF APPLIES TO THE SLOT MEDIAN PLANE" in notes
    assert "REFERENCE THREAD ROOT ENVELOPE" in notes


def test_thread_axis_datum_and_slot_position_are_native_controls() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'label="thread pitch-cylinder axis"' in source
    assert 'entity_type="SILHOUETTE"' in source
    assert "BODY_DIA / 2.0" in source
    assert 'label="driver-slot median-plane position"' in source
    assert 'quantity="SLOT MEDIAN PLANE"' in source
    assert 'characteristic="position"' in source
    assert 'datums=("A",)' in source
    assert 'add_note(adapter, "SLOT END VIEW"' in source
    assert 'add_note(adapter, "CUP END VIEW"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(4, 1)") == 3  # elevation + both end views
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


def test_machining_bands_are_toleranced_on_the_model_not_the_sheet() -> None:
    """No fit or size band may reach the print as frozen callout text.

    ``set_dimension_callouts`` appends its string via ``SetText``; SolidWorks
    prints it verbatim beside a natively-rendered numeral and never re-renders
    it, so "+/-0.10" survives the mm->inch flip in issue #290 unchanged and
    reads as inches. Only NON-tolerance annotation is allowed to stay.
    """
    assert model_toleranced_dimensions(part) == {
        ("Body", "BodyLenDim"): "GENERAL_TOL_MM",
        ("SlotProfile", "SlotWDim"): "GENERAL_TOL_MM",
        ("CupProfile", "CupDiaDim"): "*deviations(CUP_DIA_BAND)",
        ("Cup", "CupDepth"): "GENERAL_TOL_MM",
    }
    # What remains on the sheet is annotation, not specification: a thread
    # designation and the blind-depth machining instruction.
    assert set(drawing.DIMENSION_CALLOUTS) == {"BodyDiaDim", "CupDepth"}
    assert cone_tip_adjuster_spec.THREAD in drawing.DIMENSION_CALLOUTS["BodyDiaDim"]
    assert drawing.DIMENSION_CALLOUTS["CupDepth"] == "DEEP"

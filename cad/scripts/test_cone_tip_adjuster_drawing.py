"""Offline contracts for the cone-tip-adjuster drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_adjuster as part
import cone_tip_adjuster_spec
import draw_cone_tip_adjuster as drawing
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
    assert marked == {"BodyDiaDim", "BodyLenDim", "CupDiaDim", "SlotWDim"}


def test_thread_callout_is_the_catalog_thread() -> None:
    assert cone_tip_adjuster_spec.THREAD == "5/16-18"
    assert drawing.DIMENSION_CALLOUTS["BodyDiaDim"] == "5/16-18 UNC-2A"
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "InsertCosmeticThread3" in part_source
    assert "IEntity" in part_source
    assert "import_cosmetic_threads" in drawing_source
    assert cone_tip_adjuster_spec.BODY_DIA == 7.9375
    assert part.CHAMFER == drawing.CHAMFER == 0.4
    assert 'name_last_feature(adapter, "ThreadStartChamfers")' in part_source
    assert "await adapter.add_chamfer(" in part_source


def test_notes_specify_thread_cup_and_slot_without_title_block_duplicates() -> None:
    notes = cone_tip_adjuster_spec.DRAWING_NOTES
    assert "5/16-18" in notes
    assert "CUP" in notes  # the shaft-tip seating cup
    assert "SLOT" in notes  # the driver slot
    assert "MATERIAL" not in notes
    assert "OXIDE" not in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    assert "OVERALL LENGTH" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


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
    assert int(config["quantity"]) == 1

"""Offline contracts for the cone-tip-block drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-block_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_block"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_block_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_block_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {"Width", "Depth", "BlockHt", "BoreZ", "BoreDiaDim", "SlitW"}
    assert part.BORE_DIA == cone_tip_block_spec.BORE_DIA == 0.819


def test_journal_bore_is_a_running_fit_at_matching_precision() -> None:
    # The reamed 1/32 in journal is dimensioned at 3 places (0.794) so the view
    # matches the note, and carries the running-fit callout.
    assert drawing.DIMENSION_CALLOUTS["BoreDiaDim"] == "+0.005/-0.005 THRU"
    assert drawing.DIMENSION_PRECISION["BoreDiaDim"] == 3
    assert "0.814-0.824" in cone_tip_block_spec.DRAWING_NOTES


def test_notes_specify_journal_adjuster_and_functional_pinch_joint() -> None:
    notes = cone_tip_block_spec.DRAWING_NOTES
    assert "JOURNAL" in notes
    assert "5/16-18" in notes  # the adjuster tapped hole
    assert "#3-48" in notes  # the pinch tapped hole
    assert "SLIT" in notes
    assert "CLEARANCE" in notes
    assert "FAR JAW" in notes
    assert "MATERIAL" not in notes
    assert "OXIDE" not in notes
    assert "DATUM A" in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name="PinchClearance"' in part_source
    assert 'HoleSpec("clearance", "#3", end="through_next")' in part_source


def test_datum_and_parallelism_frame_are_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'datum="A"' in source
    assert 'characteristic="parallelism"' in source
    assert 'roughness_ra="1.6"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 3  # elevation + plan + pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-tip-block")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

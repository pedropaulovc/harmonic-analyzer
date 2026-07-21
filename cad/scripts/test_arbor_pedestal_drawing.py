"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

from pathlib import Path

import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert (
        DRAWINGS_BY_NAME["arbor_pedestal"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {"Width", "Depth", "FootHt", "BoreHeight", "BoreDia", "DomeDia"}


def test_arbor_bore_is_a_clamp_fit_at_matching_precision() -> None:
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "THRU, ARBOR CLAMP FIT"
    assert drawing.DIMENSION_PRECISION["BoreDia"] == 3
    assert "9.525" in arbor_pedestal_spec.DRAWING_NOTES


def test_notes_specify_bore_screw_and_casting() -> None:
    notes = arbor_pedestal_spec.DRAWING_NOTES
    assert "ARBOR CLAMP BORE" in notes
    assert "#4" in notes  # the flange hold-down clearance hole
    assert "A48 CLASS 30" in notes  # cast-iron grade on the sheet
    assert "DATUM A" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


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

    config = _config.parts("arbor-pedestal")
    assert "A48" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 1

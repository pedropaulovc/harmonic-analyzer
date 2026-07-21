"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

from pathlib import Path

import build_harmonic_base as part
import draw_harmonic_base as drawing
import harmonic_base_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/harmonic-base.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/harmonic-base.pdf")
    assert drawing.PNG.as_posix().endswith("/png/harmonic-base_drawing.png")
    assert DRAWINGS_BY_NAME["harmonic_base"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is harmonic_base_spec.DRAWING_DIMENSIONS
    marked = set().union(*harmonic_base_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked
    assert (drawing.BOTTOM_LENGTH, drawing.BOTTOM_WIDTH) == (
        harmonic_base_spec.BOTTOM_LENGTH,
        harmonic_base_spec.BOTTOM_WIDTH,
    )


def test_plate_geometry_is_single_sourced() -> None:
    # The build imports its plate nominals from the spec, so the drawing's view
    # math and the part geometry cannot drift.
    assert part.BOTTOM_LENGTH is harmonic_base_spec.BOTTOM_LENGTH
    assert part.TOP_THICKNESS is harmonic_base_spec.TOP_THICKNESS
    assert harmonic_base_spec.BOTTOM_LENGTH == 18.0 * 25.4
    assert harmonic_base_spec.TOP_LENGTH == 17.5 * 25.4


def test_notes_cover_the_top_plate_reveal_and_seats() -> None:
    notes = harmonic_base_spec.DRAWING_NOTES
    assert "GRAY IRON" not in notes
    assert "ASTM A48" not in notes
    assert "GREEN ENAMEL" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "REVEAL" in notes
    assert "TAPPED AT THE MODELLED" in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "insert_hole_table(" in source


def test_hole_table_covers_the_four_mounting_holes() -> None:
    # The mounting-hole table reads the four counterbored lag-screw holes from
    # the model; the drawing supplies one rim pick per hole.
    assert len(part.HOLE_XZ) == 4
    assert len(drawing.TOP_KEEP) == 2


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("harmonic-base")
    assert config["material"] == "ASTM A48 Class 30 Gray Iron"
    assert "gray cast iron" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1

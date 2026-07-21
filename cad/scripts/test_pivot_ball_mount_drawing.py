"""Offline contracts for the pivot-ball-mount drawing."""

from __future__ import annotations

from pathlib import Path

import build_pivot_ball_mount as part
import draw_pivot_ball_mount as drawing
import pivot_ball_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-ball-mount.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-ball-mount.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-ball-mount_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pivot_ball_mount"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pivot_ball_mount_spec.DRAWING_DIMENSIONS
    marked = set().union(*pivot_ball_mount_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "BallRise",
        "BallRadius",
        "BaseRadius",
        "BaseHeight",
        "ShaftBoreDia",
    }


def test_callouts_clarify_ball_bore_and_pad() -> None:
    assert drawing.DIMENSION_CALLOUTS["ShaftBoreDia"] == "THRU, RUNNING FIT"
    assert drawing.DIMENSION_CALLOUTS["BallRadius"] == "SPHERICAL"
    assert "DIA 13" in drawing.DIMENSION_CALLOUTS["BaseRadius"]


def test_notes_specify_ball_bore_shaft_and_finish() -> None:
    notes = pivot_ball_mount_spec.DRAWING_NOTES
    assert "SPHERICAL" in notes
    assert "6.35" in notes  # the mating pivot shaft
    assert "NICKEL PLATED" in notes
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
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(3, 1)") == 2  # elevation + pictorial


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pivot-ball-mount")
    assert "1018" in str(config["material_specification"])
    assert config["finish"]
    assert int(config["quantity"]) == 4

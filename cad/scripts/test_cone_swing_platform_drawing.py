"""Offline contracts for the cone-swing-platform drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_swing_platform as part
import cone_swing_platform_spec
import draw_cone_swing_platform as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-swing-platform.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-swing-platform.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-swing-platform_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_swing_platform"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_swing_platform_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_swing_platform_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_describe_pivot_notch_and_wedge() -> None:
    notes = cone_swing_platform_spec.DRAWING_NOTES
    assert "STEEL PLATE" not in notes
    assert "BLACK OXIDE" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "PIVOT HOLE" in notes
    assert "LOCK NOTCH" in notes
    assert "6.35 PLATE" not in notes
    assert "6.756 THRU" in notes
    assert "24.5 WEST AND 190.1 SOUTH" in notes
    assert "7.35 DEG NORTH" in notes
    assert "NE R10, NW R8, SW R10, SE R12" in notes
    assert "AS MODELLED" not in notes
    assert "SEE PLAN" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert "scale=(1, 4)" in source
    assert cone_swing_platform_spec.PLAN_VIEW_NOTE == "PLAN VIEW SCALE 1:2"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-swing-platform")
    assert config["material"] == config["material_specification"]
    assert "steel" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1

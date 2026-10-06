"""Offline contracts for the measuring-stick drawing."""

from __future__ import annotations

from pathlib import Path

import build_ha_measuring_stick as part
import draw_ha_measuring_stick as drawing
import ha_measuring_stick_spec
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ha-measuring-stick.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ha-measuring-stick.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ha-measuring-stick_drawing.png")
    assert (
        DRAWINGS_BY_NAME["ha_measuring_stick"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is ha_measuring_stick_spec.DRAWING_DIMENSIONS
    marked = set().union(*ha_measuring_stick_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked



def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.FRONT_VIEW_NAME == "*Back"
    assert drawing.FRONT_VIEW_SCALE == (1, 1)
    assert drawing.ISOMETRIC_VIEW_SCALE == (1, 2)


def test_manufacturing_note_field_clears_template_keepouts() -> None:
    left, bottom, right, top = drawing.MANUFACTURING_NOTE_FIELD
    template = DRAWING_TEMPLATES[drawing.SPEC.layout]
    inner_border = 0.0127
    assert left >= inner_border + 0.004
    assert bottom >= inner_border + 0.004
    assert right + 0.002 <= template.title_block_left_m - 0.004
    assert top + 0.006 <= 0.184


def test_part_registry_keeps_critical_drawing_properties() -> None:
    import _config

    config = _config.parts("ha-measuring-stick")
    assert config["material"] == "C26000 brass, half-hard"
    assert config["material"] == config["material_specification"]
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1

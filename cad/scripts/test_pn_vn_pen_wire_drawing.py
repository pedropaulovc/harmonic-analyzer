"""Offline contracts for the pen-wire drawing."""

from __future__ import annotations

from pathlib import Path

import build_pn_vn_pen_wire as part
import draw_pn_vn_pen_wire as drawing
import sh_vn_music_wire_pen_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-vn-pen-wire.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-vn-pen-wire.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-vn-pen-wire_drawing.png")
    assert DRAWINGS_BY_NAME["pn_vn_pen_wire"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is sh_vn_music_wire_pen_spec.DRAWING_DIMENSIONS
    marked = set().union(*sh_vn_music_wire_pen_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP)
    assert kept == marked


def test_notes_name_the_registry_sku() -> None:
    import _config

    notes = sh_vn_music_wire_pen_spec.DRAWING_NOTES
    (sku,) = _config.parts("pn-vn-pen-wire")["supplier_skus"]
    assert sku in notes
    assert "NOT A CUT" in notes
    assert "DO NOT RELEASE" in notes
    assert "ASTM" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_view_scale_is_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source
    assert sh_vn_music_wire_pen_spec.ELEVATION_VIEW_NOTE == "ELEVATION SCALE 2:1"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pn-vn-pen-wire")
    assert config["process"] == "purchased"
    assert config["material"] == "ASTM A228 music wire"
    assert config["finish"]
    assert int(config["quantity"]) == 1

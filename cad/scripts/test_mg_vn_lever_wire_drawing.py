"""Offline contracts of the shared music-wire purchase drawing."""

from __future__ import annotations

import re


import _supplier_wire_stock_drawing as section
import build_sh_vn_music_wire as part
import draw_sh_vn_music_wire as drawing
import sh_vn_music_wire_lever_geom as geom

CONFIGURATION = "LeverWire"
STEM = "sh-vn-music-wire"
_DIMENSION_TEXT = re.compile(r"Ø|<MOD-DIAM>|\bIN\b|\bMM\b|\d\.\d")


def test_wire_registry_quantities_count_installed_members() -> None:
    import _config

    row = _config.parts(STEM)
    assert row["process"] == "purchased"
    assert row["supplier_skus"] == ["9666K142"]
    assert int(row["quantity"]) == sum(row["configuration_quantities"].values())
    assert int(row["configuration_quantities"][CONFIGURATION]) == 1


def test_balloon_station_is_midway_along_the_free_run() -> None:
    assert part.BALLOON_RING_STATION == geom.WIRE_LEN / 2.0


def test_package_notes_carry_no_dimension_text() -> None:
    # The diameter is the native supplier dimension; notes carry no sizes.
    assert part.DRAWING_NOTES == "PURCHASED WIRE: McMASTER-CARR 9666K142"
    for text in (part.DRAWING_NOTES, drawing.ASSEMBLY_NOTE, drawing.ISO_LABEL):
        assert not _DIMENSION_TEXT.search(text), text




def test_end_view_and_isometric_labels_sit_inside_their_fields() -> None:
    assert section.STOCK_SCALE == (75, 1)
    field = section.STOCK_FIELD
    for x, y in (section.STOCK_CENTER, section.STOCK_TEXT, section.STOCK_LABEL_XY):
        assert field[0] <= x <= field[2] and field[1] <= y <= field[3]
    # The label's top stays under the 75:1 circle's padded native outline
    # (radius 7.6 mm plus SolidWorks' ~5.6 mm outline padding).
    assert section.STOCK_LABEL_XY[1] < section.STOCK_CENTER[1] - 0.0136
    assert drawing.ISO_LABEL.startswith("ISOMETRIC SCALE 2:1\n")
    assert "NOT TO LENGTH" in drawing.ISO_LABEL
    assert drawing.ISO_SCALE == (2, 1)
    assert drawing.ISO_FIELD[0] >= section.STOCK_FIELD[2]
    assert drawing.ISO_FIELD[1] >= drawing._TITLE_BLOCK[3]
    assert drawing.ISO_FIELD[3] <= drawing._BORDER[3]

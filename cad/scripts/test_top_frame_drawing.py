"""Offline contracts for the top-frame drawing."""

from __future__ import annotations

from pathlib import Path

import build_top_frame as part
import draw_top_frame as drawing
import top_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-frame_drawing.png")
    assert DRAWINGS_BY_NAME["top_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is top_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*top_frame_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_carry_the_pitch_rail_and_boss() -> None:
    notes = top_frame_spec.DRAWING_NOTES
    assert "GRAY-IRON" not in notes
    assert "ASTM A48" not in notes
    assert "GREEN ENAMEL" not in notes
    assert "UOS" not in notes
    assert "MACHINE FROM SOLID STOCK" in notes
    assert "442.00 +/-0.25 X 272.00 +/-0.25" in notes
    assert "416.00 X 246.00" in notes
    assert "372.00 X 202.00 CLEAR OPENING" in notes
    assert "STRAIGHT INNER-RAIL-FACE SPACING ONLY" in notes
    assert "CORNER BOSSES INTRUDE" in notes
    assert "NO BLENDS OR" in notes
    assert "CHAMFERS AT BOSS/RAIL INTERSECTIONS" in notes
    assert "394.00 X 224.00" in notes
    assert "25.50 +0.05/0" in notes
    assert "POSITION <MOD-DIAM>0.20 A|B|C" in notes
    assert "MAX-MIN RADIAL WALL THICKNESS" in notes
    assert "SHALL NOT EXCEED 0.10" in notes
    assert "FIT LEAST-SQUARES CYLINDERS" in notes
    assert "AXIS OFFSET 0.05 MAX" in notes
    assert "8 EQUALLY SPACED AXIAL SECTIONS" in notes
    assert "GREATEST AXIS" in notes and "SEPARATION AT EITHER END PLANE" in notes
    assert "ALL 64 OD POINTS" in notes
    assert "ADDITIONAL" in notes and "NATIVE SIZE AND POSITION CONTROLS" in notes
    assert "DIMENSIONS/GD&T APPLY BEFORE COATING" in notes
    assert "TIR" not in notes
    assert "GOOSENECK BORE" in notes
    assert "LEFT COLUMN-BORE CENTRELINE" in notes
    assert "MIDWAY BETWEEN LEFT BORE AXES" in notes
    assert "ALL BORES Ra 1.6" in notes
    assert "MASK DATUM A/B/C FACES, ALL BORES" in notes
    assert "4X BOSS ANNULI" in notes
    assert "BOTH PLANAR END" in notes
    assert "4X CYLINDRICAL ODS OF THE BOSSES" in notes
    assert "EXEMPT FROM" in notes and "0.25 MAX ROOT RADIUS" in notes
    assert "CYLINDRICAL ODS" in notes
    assert "-0.00" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 3
    assert 'symbol_xy=(0.245, 0.105), datum="C"' in source
    assert 'quantity="4X COLUMN BORES"' in source
    assert 'quantity="4X BOSS ODS"' in source
    assert 'allow_coincident=True' in source
    assert "-COLUMN_Z" in source
    assert 'quantity="GOOSENECK BORE"' in source
    assert '{"Width": "+/-0.25", "Depth": "+/-0.25"}' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source
    assert '"*Front"' in source
    assert "scale=(1, 4)" in source
    assert top_frame_spec.TOP_VIEW_NOTE == "PLAN VIEW SCALE 1:2"
    assert '"Top View Note", 0.280, 0.200' in source
    assert top_frame_spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 1:4"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("top-frame")
    assert config["material"] == config["material_specification"]
    assert "gray cast iron" in str(config["material_specification"]).lower()
    finish = str(config["finish"]).lower()
    assert "sspc-sp3" in finish
    assert "alkyd primer/green enamel" in finish
    assert "75-125um dft" in finish
    assert "total" in finish
    assert "color noncritical" in finish
    assert "mask" not in finish
    assert config["process"] == "machined from solid stock"
    assert int(config["quantity"]) == 1

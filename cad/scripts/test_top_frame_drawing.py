"""Offline contracts for the top-frame drawing."""

from __future__ import annotations

from pathlib import Path

import build_top_frame as part
import draw_top_frame as drawing
import top_frame_spec
from cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-frame_drawing.png")
    assert DRAWINGS_BY_NAME["top_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is top_frame_spec.DRAWING_DIMENSIONS
    assert set(top_frame_spec.DRAWING_DIMENSIONS) == {"OuterProfile"}
    marked = set().union(*top_frame_spec.DRAWING_DIMENSIONS.values())
    assert marked == {"Width", "Depth"}
    kept = set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_carry_the_casting_rails_bosses_and_holes() -> None:
    notes = top_frame_spec.DRAWING_NOTES
    notes_flat = " ".join(notes.split())
    inspection = top_frame_spec.INSPECTION_NOTES
    inspection_flat = " ".join(inspection.split())
    assert "GREEN-PAINTED GRAY IRON CASTING" in notes
    assert "MACHINE DATUM FACES, BORES" in notes
    assert "1.5 MAX DRAFT, FILLETS R3 UNLESS NOTED" in notes
    assert "MACHINE FROM SOLID STOCK" not in notes
    assert "ASTM A48" not in notes
    assert "GREEN ENAMEL" not in notes
    assert "UOS" not in notes
    assert "CLEAR OPENING" not in notes
    assert "428.20 X 262.00 OUTER RAIL RING" in notes
    assert "SIDE RAILS 34.20 WIDE" in notes
    assert "FRONT/REAR RAILS 38.00 WIDE" in notes
    assert "CLEAR WINDOW 359.80 X 186.00" in notes
    assert "INTEGRAL CROSSBAR 22.00 WIDE AT X -26.00..-4.00" in notes
    assert "18X18 GUSSETS AT ALL FOUR" in notes
    assert "RING BAND 36.50 TALL" in notes
    assert "ENVELOPE 446.20 +/-0.25 X 276.20" in notes_flat
    assert "+/-0.25 X 47.30" in notes_flat
    assert "4X CORNER BOSSES DIA52.20, 47.30 TALL" in notes
    assert "PROUD 4.50 ABOVE / 6.30 BELOW" in notes
    assert "BORED DIA25.50 +0.05/0 THRU" in notes
    assert "POSITION <MOD-DIAM>0.20 A|B|C ON 394.00 X 224.00 BASIC PITCH" in notes_flat
    assert "DATUM A = RAIL BOTTOM FACE" in notes
    assert "B = EAST (-X) OUTER RAIL FACE; C = REAR OUTER RAIL FACE" in notes_flat
    assert "PANELS RECESSED 3.50" in notes
    assert "BETWEEN 8.00 TOP/BOTTOM FLANGES" in notes_flat
    assert "CAST FINISH INSIDE PANELS" in notes
    assert "GOOSENECK HUB, EAST RAIL AT Z +3.09" in notes
    assert "RIB 27.00 WIDE FULL HEIGHT" in notes
    assert "BORE <MOD-DIAM>17.00 +0.20/0 THRU" in notes
    assert "UNDERSIDE BOSS DIA30 X 8.00" in notes
    assert "DRILL + TAP 1/4-20 UNC-2B THRU RIB TO BORE" in notes_flat
    assert "16X16X2 SPOT POCKET" in notes
    assert "4X DRILL + TAP #10-24 UNC-2B X 14.00 DEEP" in notes
    assert "DIA9.00 X 0.90 SPOT-FACE EACH" in notes
    assert (
        "2X <MOD-DIAM>13.49 (1/2 CLOSE) HANGER-STUD HOLES THRU THE CROSSBAR AT"
        " Z -83.97 / +90.15; POSITION <MOD-DIAM>0.20 A|B|C" in notes_flat
    )
    assert "2X DRILL + TAP #10-24 UNC-2B X 10.00 DEEP INTO THE WEST RAIL TOP" in notes
    assert "FULCRUM-KEEPER FEET" in notes
    assert "ALL BORES Ra 1.6" in notes
    assert "MASK DATUMS, BORES, BOSS END LANDS AND TAPPED HOLES" in notes_flat
    assert "DIMENSIONS/GD&T APPLY BEFORE COATING" in notes
    assert "MAX-MIN RADIAL WALL THICKNESS" in inspection_flat
    assert "SHALL NOT EXCEED 0.10" in inspection_flat
    assert "FIT LEAST-SQUARES CYLINDERS" in inspection_flat
    assert "8 EQUALLY SPACED AXIAL SECTIONS OVER 47.30" in inspection_flat
    assert "AXIS OFFSET 0.05 MAX" in inspection_flat
    assert "GREATEST AXIS SEPARATION AT EITHER END PLANE" in inspection_flat
    assert "64 OD POINTS" in inspection_flat
    assert "ADDITIONAL TO NATIVE SIZE/POSITION CONTROLS" in inspection_flat
    assert "TIR" not in notes
    assert "-0.00" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert 'add_property_linked_note(adapter, "Inspection Notes", 0.270, 0.255)' in source
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 4
    assert 'symbol_xy=DATUM_C_SYMBOL_XY, datum="C"' in source
    assert 'label="rear outer rail-face datum", entity=datum_c_edge' in source
    assert 'label="east outer rail-face datum"' in source
    assert drawing.DATUM_C_SYMBOL_XY[0] < drawing.TOP_CENTER[0] + part.OUTER_X / 2000.0
    assert set(top_frame_spec.GEOMETRIC_TOLERANCES_MM) == {
        "column-bore true position",
        "column-boss true position",
        "gooseneck-bore true position",
        "hanger-stud-hole true position",
    }
    for key in top_frame_spec.GEOMETRIC_TOLERANCES_MM:
        assert f'GEOMETRIC_TOLERANCES_MM["{key}"]' in source
    assert 'quantity="4X COLUMN BORES"' in source
    assert 'quantity="4X BOSS ODS"' in source
    assert 'quantity="GOOSENECK BORE"' in source
    assert 'quantity="2X HANGER-STUD HOLES"' in source
    assert "allow_coincident=True" in source
    assert "FRONT_COLUMN_Z" in source
    assert "STUD_Z_REAR" in source and "STUD_HOLE_DIA" in source
    assert "set_dimension_callouts" not in source


def test_ring_envelope_and_hole_stations_are_single_sourced() -> None:
    assert part.FRONT_COLUMN_Z == FRAME_FRONT_COLUMN_Z == -112.0
    assert part.REAR_COLUMN_Z == FRAME_REAR_COLUMN_Z == 112.0
    assert part.GOOSENECK_Z == SUMMING_Z
    assert part.GOOSENECK_X == -part.COLUMN_X == -197.0
    assert part.RAIL_W_SIDE == 34.2
    assert part.RAIL_W_FR == 38.0
    assert abs(part.OUTER_X - 214.1) < 1e-9
    assert abs(part.INNER_X - 179.9) < 1e-9
    assert abs(part.OUTER_Z - 131.0) < 1e-9
    assert abs(part.INNER_Z - 93.0) < 1e-9
    assert part.RING_HEIGHT == 36.5
    assert part.BOSS_DIA == 52.2
    assert part.BORE_DIA == 25.5
    assert part.GOOSENECK_BORE_DIA == 17.0
    assert (part.BAR_X0, part.BAR_X1) == (-26.0, -4.0)
    assert drawing.STUD_X == -15.0
    # SUMMING_Z is the derived +3.08759 recentered residual, so the stud
    # stations land at the note-rounded -83.97 / +90.15 within half a micron.
    assert part.STUD_Z_FRONT == SUMMING_Z - part.HEX_Z_MID
    assert part.STUD_Z_REAR == SUMMING_Z + part.HEX_Z_MID
    assert part.HEX_Z_MID == 87.06
    assert abs(part.STUD_Z_FRONT - -83.972) < 5e-3
    assert abs(part.STUD_Z_REAR - 90.148) < 5e-3
    assert part.STUD_HOLE_DIA == 13.492
    assert abs(drawing.PLAN_HALF_X - 223.1) < 1e-9
    assert abs(drawing.PLAN_HALF_Z - 138.1) < 1e-9
    assert abs(2.0 * drawing.PLAN_HALF_X - 446.2) < 1e-9
    assert abs(2.0 * drawing.PLAN_HALF_Z - 276.2) < 1e-9
    assert abs(drawing.BOSS_BAND - 47.3) < 1e-9
    assert abs(part.BOSS_ABOVE - 4.5) < 1e-9
    assert abs(part.BOSS_BELOW - 6.3) < 1e-9


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
    assert config["process"] == "cast + machined"
    assert int(config["quantity"]) == 1

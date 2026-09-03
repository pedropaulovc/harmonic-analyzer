"""Offline contracts for the top-frame drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a casting carries
no datums or frames; its rail profile tolerance rides the model dimensions;
every hole size and station is native (plan hole table, Hole Wizard callout);
the profile, window, boss, gusset and spot-face sizes are marked model
dimensions; the rail widths, crossbar, boss stack heights and top flange are
drawing dimensions; the web thickness rides SECTION A-A; and the notes are
four lines of process fact that carry no feature dimension.
"""

from __future__ import annotations

from pathlib import Path
import re

import build_top_frame as part
import draw_top_frame as drawing
import top_frame_spec
from cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
    SUMMING_Z,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-frame_drawing.png")
    assert DRAWINGS_BY_NAME["top_frame"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map.
    assert part.DRAWING_DIMENSIONS is top_frame_spec.DRAWING_DIMENSIONS
    assert set(top_frame_spec.DRAWING_DIMENSIONS) == {
        "OuterProfile",
        "BossUpProfile",
        "SpotFaceFrontProfile",
        "BarProfile",
    }
    marked = set().union(*top_frame_spec.DRAWING_DIMENSIONS.values())
    assert marked == {
        "Width",
        "Depth",
        "WinWidth",
        "WinDepth",
        "C0Dia",
        "S0Dia",
        "GussetRunE",
        "GussetRiseE",
    }
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP)
    assert kept == marked
    assert set(drawing.TOP_KEEP) == marked - {"S0Dia"}
    assert set(drawing.FRONT_KEEP) == {"S0Dia"}
    assert set(drawing.DIMENSION_CALLOUTS) == {"C0Dia", "S0Dia", "GussetRunE"}
    assert drawing.DIMENSION_CALLOUTS["C0Dia"].startswith("4X")
    assert drawing.DIMENSION_CALLOUTS["GussetRunE"].startswith("4X")
    assert "SPOT-FACE" in drawing.DIMENSION_CALLOUTS["S0Dia"]
    # The marked names resolve on the features the build names.
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'names=(f"C{n}X", f"C{n}Z", f"C{n}Dia")' in build_source
    assert 'names=(f"S{k}X", None, f"S{k}Dia")' in build_source
    assert 'name_width="WinWidth"' in build_source
    assert 'name_depth="WinDepth"' in build_source
    assert '"GussetRunE",\n            "GussetRiseE",' in build_source
    assert 'name_last_feature(adapter, "BarProfile")' in build_source
    assert 'f"Boss{updown.capitalize()}Profile"' in build_source
    assert 'f"SpotFace{side.capitalize()}Profile"' in build_source


_DIMENSION_NUMBER = re.compile(r"\d+\.\d{2,}")


def test_notes_are_few_specific_and_never_a_dimension() -> None:
    notes = top_frame_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert all(len(line) <= 110 for line in lines)
    # Casting draft and rim breaks, which faces are MACHINED (Harvey #34), and
    # which face each hole family opens from: the facts the views cannot show.
    assert "GRAY IRON CASTING" in notes
    assert "MAX DRAFT" in notes
    assert "CAST FINISH INSIDE THE WEB PANELS" in notes
    assert "MACHINE THE RAIL BOTTOM FACE AND BOSS END LANDS" in notes
    assert "BORE COLUMN AND GOOSENECK HOLES" in notes
    assert "FRONT PAIR FROM THE FRONT, REAR PAIR FROM THE REAR" in notes
    assert "STUD HOLES DRILLED FROM THE UNDERSIDE" in notes
    assert "KEEPER TAPS FROM THE WEST RAIL TOP" in notes
    assert "MASK" in notes
    # Rule 6: a note never carries a dimension.  Every size and station that
    # used to ride here is native now (hole table, callout, marked dimension).
    assert _DIMENSION_NUMBER.findall(notes) == []
    for banned in (
        "25.5",
        "394",
        "224",
        "17.0",
        "13.49",
        "#10-24",
        "1/4-20",
        "52.2",
        "47.3",
        "36.5",
        "UNLESS NOTED",
        "UOS",
        "+/-",
        "DATUM",
        "POSITION",
        "BASIC",
        "A|B|C",
        "Ra ",
        "GD&T",
        "ASTM A48",
        "GREEN ENAMEL",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert not hasattr(top_frame_spec, "DRAWING_NOTES_B")
    assert not hasattr(top_frame_spec, "INSPECTION_NOTES")
    source = _source()
    assert (
        'add_property_linked_note(\n'
        '        adapter, "Manufacturing Notes", 0.016, 0.090, char_height=0.0025\n'
        "    )"
        in source
    )
    assert "Manufacturing Notes B" not in source
    assert "Inspection Notes" not in source
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes B" not in build_source
    assert "Inspection Notes" not in build_source


def test_set_screw_tap_is_flagged_from_the_bore_without_a_dimension() -> None:
    note = top_frame_spec.SET_SCREW_TAP_NOTE
    assert note.startswith("1/4-20 SET-SCREW TAP")
    assert "POCKET" in note and "BORE" in note
    assert _DIMENSION_NUMBER.findall(note) == []
    assert len(note.split("\n")) == 3
    source = _source()
    assert "add_attached_note(" in source
    assert "text=SET_SCREW_TAP_NOTE" in source
    assert "entity=gooseneck_edge" in source
    assert drawing.SET_SCREW_NOTE_XY == (0.056, 0.152)


def test_hole_table_is_native_and_anchored_on_the_virtual_rear_left_corner() -> None:
    source = _source()
    assert "insert_hole_table(" in source
    assert "_plan_hole_table_entities(" in source
    assert "datum_axes=(rear_edge, left_edge)" in source
    assert "hole_entities=hole_entities" in source
    assert "expected_locations_mm=tuple(" in source
    assert "basic_locations=False" in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*1\s*\)", source)
    assert drawing.HOLE_TABLE_ANCHOR == (0.256, 0.250)
    # 4X column bores, the gooseneck bore, 2X hanger studs, 2X keeper taps.
    assert len(drawing.ALL_HOLES) == 9
    assert [diameter for _x, _z, diameter in drawing.ALL_HOLES] == [
        part.BORE_DIA,
        part.BORE_DIA,
        part.BORE_DIA,
        part.BORE_DIA,
        part.GOOSENECK_BORE_DIA,
        part.STUD_HOLE_DIA,
        part.STUD_HOLE_DIA,
        drawing.KEEPER_TAP_DIA,
        drawing.KEEPER_TAP_DIA,
    ]
    assert drawing.KEEPER_TAP_DIA == TAP_DRILL_MM["#10-24"]
    assert drawing.SIDE_TAP_DIA == TAP_DRILL_MM["#10-24"]
    # Every station is measured from the rear-left outer rail corner.
    locations = [
        (x + part.OUTER_X, part.OUTER_Z - z) for x, z, _diameter in drawing.ALL_HOLES
    ]
    assert all(0.0 < x < 2 * part.OUTER_X for x, _y in locations)
    assert all(0.0 < y < 2 * part.OUTER_Z for _x, y in locations)
    assert abs(locations[0][0] - 17.1) < 1e-9 and abs(locations[0][1] - 243.0) < 1e-9
    assert abs(locations[3][0] - 411.1) < 1e-9 and abs(locations[3][1] - 19.0) < 1e-9
    # Remove only after all view annotations have materialized; an early pass
    # allowed the generated "#10-24 Tapped Hole" note to overprint A3/A4.
    remover = 'remove_notes_matching(adapter, "Tapped Hole")'
    assert remover in source
    assert source.index(remover) > source.index("insert_hole_table(")
    assert source.index(remover) > source.index("add_native_hole_callout(")


def test_side_taps_and_heights_ride_the_elevation() -> None:
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    assert 'label="side-screw taps"' in source
    assert "edge=side_tap" in source
    # A tapped callout carries thread + depth natively; no process prefix.
    assert "process=" not in source
    assert drawing.SIDE_TAP_CALLOUT_XY == (0.326, 0.114)
    # The smaller front caption occupies its own lane between the 262 depth
    # dimension and the side-tap callout.
    assert drawing.FRONT_VIEW_NOTE_XY == (0.264, 0.116)
    assert (
        'adapter, "Front View Note", *FRONT_VIEW_NOTE_XY, char_height=0.0025'
        in source
    )
    # drawing dimensions on topologically picked edges (the elevation's bbox
    # is asymmetric, so nothing is picked by sheet coordinate); front/rear
    # rail width and crossbar width the same way on the plan.
    assert source.count("_dimension_entities(") == 9  # definition + 8 calls
    for label in (
        'label="boss stack height"',
        'label="boss proud of the rail top"',
        'label="rail band height"',
        'label="top flange height"',
        'label="front/rear rail width"',
        'label="crossbar width"',
    ):
        assert label in source, label
    assert "SelectByID2" not in source
    assert "view.SelectEntity(entity, index > 0)" in source
    assert abs(drawing.FRONT_BBOX_MID_Y - -1.75) < 1e-9
    assert abs(drawing.BOSS_TOP_Y - 22.75) < 1e-9
    assert abs(drawing.BOSS_BOTTOM_Y - -24.55) < 1e-9
    assert abs(drawing.HUB_BOTTOM_Y - -26.25) < 1e-9
    assert drawing.STACK_TEXT_XY[0] == 0.264
    assert drawing.BOSS_ABOVE_TEXT_XY[0] == 0.278
    assert abs(drawing.RING_TEXT_XY[0] - 0.368) < 1e-9
    assert abs(drawing.FLANGE_TEXT_XY[0] - 0.380) < 1e-9
    assert abs(drawing.FLANGE_TEXT_XY[1] - 0.134) < 1e-9
    assert abs(drawing.STACK_TEXT_XY[1] - 0.1304375) < 1e-9
    assert abs(drawing.FR_RAIL_TEXT_XY[0] - 0.185) < 1e-9
    assert drawing.FR_RAIL_TEXT_XY[1] == 0.2475
    assert abs(drawing.BAR_TEXT_XY[1] - 0.160) < 1e-9
    assert drawing.BAR_TEXT_XY[0] == 0.150
    # Spot-face callout on the elevation's centreline (the sketch's negative
    # plane offset may mirror S0 to either boss).
    assert drawing.FRONT_KEEP["S0Dia"] == (0.345, 0.152)
    assert drawing.TOP_KEEP["C0Dia"] == (0.075, 0.2495)
    # Depth moved to the right flank (the section cut line runs off the left).
    assert drawing.TOP_KEEP["Depth"] == (0.2566, 0.120)
    assert drawing.TOP_KEEP["WinWidth"] == (0.170, 0.1255)
    assert drawing.TOP_KEEP["WinDepth"] == (0.205, 0.175)
    assert drawing.TOP_KEEP["GussetRunE"] == (0.160, 0.205)
    assert drawing.TOP_KEEP["GussetRiseE"] == (0.150, 0.217)
    assert drawing.FRONT_VIEW_NOTE_XY[0] > drawing.TOP_KEEP["Depth"][0]


def test_web_thickness_rides_section_a_a() -> None:
    # The web sits under the flange in the plan and behind the front rail in
    # the elevation, so the T-section is cut across the plan at z +36 (clear
    # of the hub, its gussets and every hole).  The two dimensions select four
    # distinct section-generated line entities through IView; neither a bbox
    # mapper nor coordinate-pick tolerance participates.
    source = _source()
    assert source.count("create_section_view(") == 1
    assert 'section_label="A"' in source
    assert "scale=(1, 4),\n        label=\"rail T-section\"" in source
    assert "add_edge_dimension(" not in source
    assert "_section_circles, section_lines = _view_edges(adapter, section)" in source
    assert "view.SelectEntity(entity, index > 0)" in source
    assert "model_point_in_view(" not in source
    assert "def _section_xy" not in source
    assert 'label="web thickness"' in source
    assert 'label="side rail width"' in source
    for anchor in (
        "section +X web inner edge",
        "section +X web outer edge",
        "section +X flange inner edge",
        "section +X flange outer edge",
    ):
        assert f'label="{anchor}"' in source, anchor
    assert drawing.SECTION_CUT_Z == 36.0
    assert drawing.SECTION_LINE == ((0.019, 0.157), (0.2485, 0.157))
    assert drawing.SECTION_LINE[0][1] > drawing.SET_SCREW_NOTE_XY[1]
    assert drawing.SECTION_CENTER == (0.345, 0.099)
    assert drawing.WEB_TEXT_XY == (0.39425, 0.0895)
    assert drawing.SIDE_RAIL_TEXT_XY == (0.39425, 0.0835)
    assert abs(drawing.WEB_IN_X - 190.65) < 1e-9
    assert abs(drawing.WEB_OUT_X - 203.35) < 1e-9
    assert abs(drawing.WEB_OUT_X - drawing.WEB_IN_X - part.WEB_T) < 1e-9
    assert abs(part.OUTER_X - part.INNER_X - 34.2) < 1e-9
    # The cut clears the hub gussets (z <= 33.1) and the nearest hole rim
    # (keeper tap at z 77.1, stud at 90.1 minus its radius).
    assert part.HUB_GUSSET_HALF_OUT + part.GOOSENECK_Z < drawing.SECTION_CUT_Z
    assert drawing.SECTION_CUT_Z < part.KEEPER_TAP_Z_REAR - part.KEEPER_TAP_SPEC.depth_mm


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-5: a frame casting is not on the
    # GD&T allowlist; the rail profile tolerance rides the model dimensions.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "_visible_plan_controls(" not in source
    assert "_visible_front_datum_a(" not in source
    assert "DATUM_C_SYMBOL_XY" not in source
    assert not hasattr(top_frame_spec, "GEOMETRIC_TOLERANCES_MM")
    assert top_frame_spec.OUTER_PROFILE_TOLERANCE_MM == 0.25
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert build_source.count("set_dimension_symmetric_tolerance(") == 2


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (top, front):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(" not in source


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
    assert drawing.STUD_X == part.BAR_X0 + 11.0  # the wizard placement station
    # SUMMING_Z is the derived +3.08759 recentered residual, so the stud
    # stations land at -83.97 / +90.15 within half a micron.
    assert part.STUD_Z_FRONT == SUMMING_Z - part.HEX_Z_MID
    assert part.STUD_Z_REAR == SUMMING_Z + part.HEX_Z_MID
    assert part.HEX_Z_MID == 87.06
    assert abs(part.STUD_Z_FRONT - -83.972) < 5e-3
    assert abs(part.STUD_Z_REAR - 90.148) < 5e-3
    assert part.STUD_HOLE_DIA == 13.492
    assert part.KEEPER_TAP_X == 199.9
    assert abs(drawing.PLAN_HALF_X - 223.1) < 1e-9
    assert abs(drawing.PLAN_HALF_Z - 138.1) < 1e-9
    assert abs(2.0 * drawing.PLAN_HALF_X - 446.2) < 1e-9
    assert abs(2.0 * drawing.PLAN_HALF_Z - 276.2) < 1e-9
    assert abs(drawing.BOSS_BAND - 47.3) < 1e-9
    assert abs(part.BOSS_ABOVE - 4.5) < 1e-9
    assert abs(part.BOSS_BELOW - 6.3) < 1e-9


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    source = _source()
    assert "scale=(1, 2)" in source
    assert '"*Front"' in source
    assert "scale=(1, 4)" in source
    assert top_frame_spec.TOP_VIEW_NOTE == "PLAN VIEW SCALE 1:2"
    # The plan-scale note moved above the hole table that now fills the
    # sheet's upper right.
    assert drawing.TOP_VIEW_NOTE_XY == (0.262, 0.259)
    assert 'add_property_linked_note(adapter, "Top View Note", *TOP_VIEW_NOTE_XY)' in source
    assert top_frame_spec.FRONT_VIEW_NOTE == "FRONT VIEW SCALE 1:4"
    assert (
        'adapter, "Front View Note", *FRONT_VIEW_NOTE_XY, char_height=0.0025'
        in source
    )


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

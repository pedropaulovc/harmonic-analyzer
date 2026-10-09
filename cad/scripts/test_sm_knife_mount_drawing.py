"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_sm_knife_mount as part
import draw_sm_knife_mount as drawing
import sm_knife_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_knife_seat_bore_finish_is_part_owned_and_consumed_by_key() -> None:
    # Policy rule 5: the knife SEAT carries MACHINED_UM (1.6); GROUND_UM (0.8)
    # is for the knife edge itself, which is the lever trunnion's ridge.
    (control,) = sm_knife_mount_spec.SURFACE_FINISHES
    assert control.key == "knife_bore"
    assert control.roughness_um == sm_knife_mount_spec.MACHINED_UM == 1.6
    assert control.face.diameter_mm == 2.0 * sm_knife_mount_spec.R_BORE
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "knife_bore")' in drawing_source
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/sm-knife-mount.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/sm-knife-mount.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sm-knife-mount_drawing.png")
    assert DRAWINGS_BY_NAME["sm_knife_mount"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is sm_knife_mount_spec.DRAWING_DIMENSIONS
    marked = set().union(*sm_knife_mount_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP)
        | set(drawing.SECTION_KEEP)
        | set(drawing.RIGHT_KEEP)
        | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # Every marked dowel-hole dimension carries part-authored places; the
    # pair's span is sheet-added between the two axes, its places the spec's.
    assert set(sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME) == {
        "PinHoleDia",
        "PinHoleDepth",
    }
    assert sm_knife_mount_spec.DRAWING_REFERENCE_PRECISION == {
        "dowel hole span": 3,
        "knife-bore centre from top seat": 3,
    }
    for feature, names in sm_knife_mount_spec.DRAWING_PRECISION.items():
        assert set(names) <= sm_knife_mount_spec.DRAWING_DIMENSIONS[feature]


def test_dowel_hole_depth_is_dimensioned_on_the_section_not_a_hidden_edge() -> None:
    # Policy rule 7: the blind dowel hole's floor is a hidden edge in the
    # front view, so its depth rides section A-A, cut on z = 0 through the
    # tap axis (the origin) and both dowel axes, and only there.
    assert set(drawing.SECTION_KEEP) == {"PinHoleDepth"}
    assert "PinHoleDepth" not in drawing.FRONT_KEEP
    assert "PinHoleDepth" not in drawing.TOP_KEEP
    (start, end) = drawing.SECTION_LINE_MODEL_MM
    assert start[2] == end[2] == 0.0
    assert start[0] < -sm_knife_mount_spec.BLK_HALF_X
    assert end[0] > sm_knife_mount_spec.BLK_HALF_X
    assert start[0] < -sm_knife_mount_spec.PIN_HOLE_X < 0.0 < sm_knife_mount_spec.PIN_HOLE_X < end[0]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("create_section_view(") == 1
    assert "_look_section_along_minus_z(adapter, section)" in source
    assert "set_hidden_lines_removed(adapter, section)" in source
    # Section before top: the MHA-PD-018 import order.
    assert source.index("keep=SECTION_KEEP") < source.index("keep=TOP_KEEP")
    # The depth text stands right of the cut block, level with the hole.
    x, y = drawing.SECTION_KEEP["PinHoleDepth"]
    scale = drawing.SHEET_SCALE[0] / 1000.0
    assert x > drawing.SECTION_CENTER[0] + sm_knife_mount_spec.BLK_HALF_X * scale
    top_y = drawing._section_y(sm_knife_mount_spec.BLK_TOP)
    floor_y = drawing._section_y(
        sm_knife_mount_spec.BLK_TOP - sm_knife_mount_spec.PIN_HOLE_DEPTH
    )
    assert floor_y < y < top_y


def test_dowel_callout_is_parked_clear_of_the_top_view() -> None:
    # Rule 8 (dda9a33a8 render): the three callout lines ran through both
    # holes and the leader shoulder crossed the view.  The block now hangs
    # wholly right of the block's +X face, and the shoulder's near end stands
    # below the hole centre so the leader climbs to the hole rim.
    x, y = drawing.TOP_KEEP["PinHoleDia"]
    face_x = drawing._sheet_x(sm_knife_mount_spec.BLK_HALF_X)
    shoulder_x, shoulder_y = drawing.PIN_CALLOUT_SHOULDER_START
    assert shoulder_x > face_x
    shoulder_start_x = (
        x - drawing.PIN_CALLOUT_HALF_WIDTH - drawing.PIN_CALLOUT_SHOULDER_OVERHANG
    )
    assert shoulder_start_x == pytest.approx(shoulder_x)
    assert y - drawing.PIN_CALLOUT_SHOULDER_DROP == pytest.approx(shoulder_y)
    assert shoulder_y < drawing.TOP_CENTER[1]
    # Right edge clear of the right view's column and on the sheet.
    right_edge = x + drawing.PIN_CALLOUT_HALF_WIDTH
    assert right_edge < drawing.ISO_CENTER[0] - 0.050
    # Above the right view's box (front row, 2:1 block height).
    assert shoulder_y > drawing.RIGHT_CENTER[1] + drawing.RIGHT_HALF_Y + 0.040


def test_the_tap_is_stated_once_on_its_hole_callout() -> None:
    # Rule 6: the tap rides one native Hole Wizard callout (thread, full
    # thread depth, drill and drill depth stay associative); SolidWorks' raw
    # "#6-32 Tapped Hole" note would restate it, so it is deleted and
    # finalize proves none is left at export.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 1
    assert "process=TAP_CALLOUT_PROCESS" in source
    assert drawing.TAP_CALLOUT_PROCESS == "BOTTOMING TAP\n"
    assert drawing.TAPPED_HOLE_NOTE == "Tapped Hole"
    assert "remove_notes_matching(adapter, TAPPED_HOLE_NOTE)" in source
    assert "redundant_note_substrings=(TAPPED_HOLE_NOTE,)" in source
    assert "expected_redundant_notes=0" in source
    assert source.index("remove_notes_matching(adapter, TAPPED_HOLE_NOTE)") > (
        source.index("keep=TOP_KEEP")
    )


def test_tap_callout_parks_between_the_top_view_and_the_datum_tag() -> None:
    # Rule 8: the three rows stand in the band under the top view and over
    # the front view's datum-A tag, left of the tag, so neither the text nor
    # its steep leader crosses a view, a dimension or the A-A cutting line.
    x, y = drawing.TAP_CALLOUT_XY
    top_view_bottom = drawing.TOP_CENTER[1] - drawing.TOP_HALF_Z
    datum_tag_top = drawing._front_y(sm_knife_mount_spec.BLK_TOP) + 0.018 + 0.0075
    assert y + drawing.TAP_CALLOUT_HALF_HEIGHT < top_view_bottom
    assert y - drawing.TAP_CALLOUT_HALF_HEIGHT > datum_tag_top
    assert x + drawing.TAP_CALLOUT_HALF_WIDTH < drawing.FRONT_CENTER[0] - 0.0035
    # Over the 29.62 height line's upper witness line (y at the block top),
    # not beside it.
    assert y - drawing.TAP_CALLOUT_HALF_HEIGHT > drawing._front_y(
        sm_knife_mount_spec.BLK_TOP
    )
    assert x - drawing.TAP_CALLOUT_HALF_WIDTH > 0.0


def test_bore_callout_stands_between_the_height_line_and_the_block() -> None:
    # 5ff8fba5d render: the 29.62 dimension line ran 3.62 mm through the
    # Ø12.00 THRU text, and the Ø line crossed the bore and the view to a
    # shoulder left of it.  The text now sits in the band between the height
    # line and the block's -X face, at least 5 mm clear of each, and the Ø
    # is drawn as one arrow on the near rim.
    height_x, _ = drawing.FRONT_KEEP["BlockHeight"]
    x, y = drawing.FRONT_KEEP["BoreDia"]
    face_x = drawing._sheet_x(-sm_knife_mount_spec.BLK_HALF_X)
    assert x - drawing.BORE_DIA_TEXT_HALF_WIDTH > height_x + 0.005
    assert x + drawing.BORE_DIA_TEXT_HALF_WIDTH < face_x - 0.005
    # Above the bore centre, so the leader descends to the upper-left rim.
    assert y > drawing._front_y(sm_knife_mount_spec.BORE_CY)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(bore_dia[0], "knife-bore diameter")' in source


def test_the_template_alone_centre_marks_the_bore() -> None:
    # #913 on this sheet: the template marks the bore as the front view is
    # placed, and an explicit auto-insert printed a second mark over it.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks" not in source
    assert "expected one knife-bore centre mark" in source


def test_spec_geometry_mirrors_the_build_source() -> None:
    # The drawing's view math reads the spec's mirrored nominals for placement
    # only (the marks carry the exact values); assert they track the build's
    # actual (assembly-derived) geometry to <0.05 mm so they cannot drift.
    assert sm_knife_mount_spec.R_BORE == part.R_BORE
    assert sm_knife_mount_spec.SUPPORT_Z_THICK == part.SUPPORT_Z_THICK
    assert abs(sm_knife_mount_spec.BLK_TOP - part.BLK_TOP) < 0.005
    assert abs(sm_knife_mount_spec.BLK_BOT - part.BLK_BOT) < 0.05
    assert abs(sm_knife_mount_spec.BORE_CY - part.BORE_CY) < 0.05
    # The seat is clamped to the casting underside by the #6-32 screw.
    assert part.MOUNT_GAP == 0.0
    assert abs(part.BLK_TOP - 14.866) < 1e-3
    assert sm_knife_mount_spec.BLK_TOP == 14.87
    # The build owns no tap constants: they are the spec's (consumers import
    # them there).
    assert not hasattr(part, "STUD_TAP_DEPTH")
    assert part.STUD_TAP_SPEC is sm_knife_mount_spec.STUD_TAP_SPEC
    assert part.STUD_TAP_DIA == sm_knife_mount_spec.STUD_TAP_DIA
    # Dowel holes: one each side of the tap at +/-6.350 (the printed span
    # 12.700 .XXX), printed places and the volume the build's gate expects.
    assert sm_knife_mount_spec.PIN_HOLE_X == 6.350
    assert sm_knife_mount_spec.PIN_HOLE_XS == (-6.350, 6.350)
    assert sm_knife_mount_spec.PIN_HOLE_SPAN == 12.700
    assert sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME == {
        "PinHoleDia": 3,
        "PinHoleDepth": 1,
    }
    import math

    assert abs(part.V_PIN - math.pi * (3.175 / 2.0) ** 2 * 9.5) < 1e-9
    assert part.V_PINS == 2 * part.V_PIN
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH)" in source
    assert 'for pin_dia_name in ("PinHoleDia", "PinHole2Dia"):' in source
    assert '"PinHoleProfile", pin_dia_name, *deviations(PIN_HOLE_DIA_BAND)' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_the_sheet_carries_no_notes_block() -> None:
    # Rule 6: every fact the notes held now rides a callout or a field --
    # the bore's location its BASICs and position frame, the tap its hole
    # callout, the heat treatment the Finish field -- and the design-intent
    # prose (knife-edge bearing, screw clamp, two blocks) is gone.
    assert not hasattr(sm_knife_mount_spec, "DRAWING_NOTES")
    assert not hasattr(sm_knife_mount_spec, "STUD_SCREW_NUMBER")
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in part_source
    assert "Manufacturing Notes" not in drawing_source
    assert drawing_source.count("add_property_linked_note(") == 1
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in drawing_source
    # The dowel holes' count rides above their Ø and the press below it
    # (MHA-PD-018 precedent); their position frame hangs under the callout.
    assert drawing.CALLOUTS_ABOVE == {"PinHoleDia": "2X"}
    assert sm_knife_mount_spec.PIN_HOLE_CALLOUT.splitlines() == [
        "BLIND FLAT-BOTTOM REAM",
        "PRESS MHA-VN-051 DOWEL TO FLOOR",
        "0.0025/0.0177 INTERFERENCE",
    ]


def test_native_gdt_and_bore_geometry() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # Datum A the top seat (a tag); datum B the dowel pair, named by its
    # position frame's datum identifier: a tag on the 2X Ø attaches to
    # nothing (farm run 20261009T155421516Z, count=0).
    assert source.count("add_datum_feature(") == 1
    assert "add_dimension_datum_feature" not in source
    assert 'datum="A"' in source and 'datum="B"' not in source
    assert source.count('datum_identifier="B"') == 1
    # The pair's frame to A, the bore's composite frame and the tap's frame
    # to A|B.
    assert source.count("add_feature_control_frame(") == 3
    assert source.count('characteristic="position"') == 3
    assert source.count('datums=("A",)') == 1
    assert source.count('datums=("A", "B")') == 2
    assert source.count("composite_lower=(") == 1
    assert 'GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"]' in source
    assert sm_knife_mount_spec.GEOMETRIC_TOLERANCES_MM == {
        "knife-bore position": "0.20",
        "knife-bore orientation refinement": "0.05",
        "knife-hanger tap position": "0.10",
        "dowel hole pattern position": "0.13",
    }
    # Sheet-added: the block depth, the dowel span and the bore centre's
    # height under A, both BASIC; the dowel holes' Ø and depth are marked
    # model dimensions (DRAWING_DIMENSIONS).
    assert source.count("add_edge_dimension(") == 3
    assert source.count("set_basic_dimension(") == 2
    assert 'set_basic_dimension(adapter, span, label="dowel hole span")' in source


@pytest.mark.parametrize(
    ("label", "basic"),
    (
        ("knife-bore centre from top seat", part.BORE_CENTRE_DEPTH),
        ("dowel hole span", sm_knife_mount_spec.PIN_HOLE_SPAN),
    ),
)
def test_each_basic_prints_the_modelled_value_unrounded(label: str, basic: float) -> None:
    # A BASIC is exact: the sheet measures it off the model (1e-5 gate) and
    # its places must print that value, not a rounding of it.  48ad988c6
    # checked the bore height against the spec's 14.87 mirror (20.62) at
    # .XX; the model measures 14.866 + 5.75 = 20.616, and the leaf failed.
    places = sm_knife_mount_spec.DRAWING_REFERENCE_PRECISION[label]
    assert abs(round(basic, places) - basic) < 1e-9
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from build_sm_knife_mount import BORE_CENTRE_DEPTH" in source
    assert not hasattr(sm_knife_mount_spec, "BORE_CENTRE_DEPTH")


def test_bore_basic_is_the_built_geometry() -> None:
    assert part.BORE_CENTRE_DEPTH == part.BLK_TOP - part.BORE_CY
    assert part.BORE_CENTRE_DEPTH == pytest.approx(20.616, abs=1e-9)
    assert f"{part.BORE_CENTRE_DEPTH:.3f}" == "20.616"
    # The spec's mirror would print a BASIC 0.004 off the part.
    mirror = sm_knife_mount_spec.BLK_TOP - sm_knife_mount_spec.BORE_CY
    assert abs(mirror - part.BORE_CENTRE_DEPTH) > 1e-5


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("sm-knife-mount")
    # ch18 p.42 (2026-09-02): unpainted heat-treated steel, not brass.
    assert part.MATERIAL == "Plain Carbon Steel"
    assert config["material"] == "Plain Carbon Steel"
    assert config["material_specification"] == "AISI O1 tool steel"
    # Rule 1: the heat treatment and the bare surface are the Finish field's,
    # stated once there (the sheet has no notes block).
    assert config["finish"] == "hardened and tempered 58-60 HRC, unpainted"
    assert "Brass" not in config["material_specification"]
    assert int(config["quantity"]) == 2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_color(adapter, HARDENED_STEEL)" in source
    assert part.HARDENED_STEEL == (0.30, 0.30, 0.31)


def test_close_bore_clears_the_hex_trunnion_only_at_the_ridge() -> None:
    import math

    from sm_summing_lever_spec import HEX_H, HEX_W

    assert part.R_BORE == 6.0
    assert abs(part.BLK_BOT - (-14.75)) < 1e-9
    assert abs(part.BORE_CY - (-5.75)) < 1e-9
    # Top vertex hangs TOP_CLEAR under the crown; the across-corners bottom
    # vertex and the two widest shoulders clear the bore wall.
    hex_centre_y = -HEX_H / 2.0
    assert abs((part.BORE_CY + part.R_BORE) - part.TOP_CLEAR) < 1e-9
    bottom_clear = part.R_BORE - abs(hex_centre_y - HEX_H / 2.0 - part.BORE_CY)
    assert bottom_clear > 0.5
    for sy in (hex_centre_y + HEX_H / 4.0, hex_centre_y - HEX_H / 4.0):
        d = math.hypot(HEX_W / 2.0, sy - part.BORE_CY)
        assert d < part.R_BORE - 0.5

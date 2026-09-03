"""Offline contracts for the knife-mount drawing.

The knife mount is on the GD&T allowlist (cad/docs/drawing-simplicity-policy.md
rule 3, knife-edge system): the print keeps exactly one position frame on the
bore to the top-seat datum, the ground finish on the bore, a native callout for
the hanger-stud tap, and four lines of process notes.
"""

from __future__ import annotations

from pathlib import Path

import build_knife_mount as part
import draw_knife_mount as drawing
import knife_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_ground_bore_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = knife_mount_spec.SURFACE_FINISHES
    assert control.key == "knife_bore"
    assert control.roughness_um == knife_mount_spec.GROUND_UM == 0.8
    assert control.face.diameter_mm == 2.0 * knife_mount_spec.R_BORE
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = _source()
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "knife_bore")' in drawing_source
    assert drawing_source.count("add_surface_finish(") == 1
    assert "roughness_ra=" not in drawing_source


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/knife-mount.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/knife-mount.pdf")
    assert drawing.PNG.as_posix().endswith("/png/knife-mount_drawing.png")
    assert DRAWINGS_BY_NAME["knife_mount"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is knife_mount_spec.DRAWING_DIMENSIONS
    marked = set().union(*knife_mount_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_spec_geometry_mirrors_the_build_source() -> None:
    # The drawing's view math reads the spec's mirrored nominals for placement
    # only (the marks carry the exact values); assert they track the build's
    # actual (assembly-derived) geometry to <0.05 mm so they cannot drift.
    assert knife_mount_spec.R_BORE == part.R_BORE
    assert knife_mount_spec.SUPPORT_Z_THICK == part.SUPPORT_Z_THICK
    assert abs(knife_mount_spec.BLK_TOP - part.BLK_TOP) < 0.05
    assert abs(knife_mount_spec.BLK_BOT - part.BLK_BOT) < 0.05
    assert abs(knife_mount_spec.BORE_CY - part.BORE_CY) < 0.05
    assert knife_mount_spec.STUD_TAP_DRILL_DIA == part.STUD_TAP_DIA
    assert knife_mount_spec.STUD_TAP_DRILL_DIA == TAP_DRILL_MM["1/2-13"]


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = knife_mount_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The bore height from the top seat is a BASIC sheet dimension now, not a
    # note line.
    assert "BELOW THE TOP SEAT" not in notes
    assert f"{knife_mount_spec.BLK_TOP - knife_mount_spec.BORE_CY:.2f}" not in notes
    assert "RIDES THE BORE'S UPPER WALL" in notes
    assert "TAP-DRILL POINT BREAKS INTO THE BORE CROWN" in notes
    assert "TWO BLOCKS USED" in notes
    # ch18 p.42 (pass 3): the block IS the hardened knife seat; the heat
    # treat is a process fact the machinist needs, the old release hold
    # is gone.
    assert "HARDEN AND TEMPER TO 58-60 HRC" in notes
    assert "LEAVE UNPAINTED" in notes
    # The tap rides its callout; the finish its symbol; release holds stay
    # off the print.
    for banned in (
        "1/2-13",
        "TAP 1/2",
        "Ra ",
        "DO NOT RELEASE",
        "DATUM",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "MHA-",
        "GRAY IRON",
        "PAINT BLACK",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
    ):
        assert banned not in notes, banned
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_only_the_allowlisted_knife_bore_frame_survives() -> None:
    # Policy rule 3: one position frame on the bore, referencing the one datum
    # (the top seat); nothing else.
    source = _source()
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="position"' in source
    assert 'label="knife-bore position"' in source
    assert 'datums=("A",)' in source
    assert "project_part_pmi(" not in source
    assert knife_mount_spec.GEOMETRIC_TOLERANCES_MM == {"knife-bore position": "0.20"}
    # Block depth across the right-view section + the basic bore height.
    assert source.count("add_edge_dimension(") == 2


def test_position_frame_is_fed_by_one_basic_bore_height() -> None:
    # Policy rule 4: the only boxed dimension is the one the surviving frame
    # needs -- bore centre to the datum-A top seat, vertical, arc endpoint
    # moved to the centre so it reads to the axis.
    source = _source()
    assert source.count('label="knife-bore height from datum A"') == 3
    assert source.count("set_basic_dimension(") == 1
    assert source.count("set_arc_endpoints_to_center(") == 1
    assert 'orientation="vertical"' in source
    assert "bore_height = add_edge_dimension(" in source
    # Stacked inside the block-height dimension on the block's left.
    assert drawing.BORE_HEIGHT_TEXT[0] < drawing.FRONT_CENTER[0]
    assert drawing.BORE_HEIGHT_TEXT[0] > drawing.FRONT_KEEP["BlockHeight"][0]


def test_hanger_stud_tap_is_a_native_hole_callout() -> None:
    source = _source()
    assert source.count("add_native_hole_callout(") == 1
    assert 'label="hanger-stud tap"' in source
    assert "STUD_TAP_DRILL_DIA * SHEET_SCALE[0] / 2000.0" in source
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("tapped", "1/2-13", end="blind"' in build_source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, right, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("knife-mount")
    # ch18 p.42 (2026-09-02): unpainted heat-treated steel, not brass.
    assert part.MATERIAL == "Plain Carbon Steel"
    assert config["material"] == "Plain Carbon Steel"
    assert "O1 tool steel" in config["material_specification"]
    assert "58-60 HRC" in config["material_specification"]
    assert "Brass" not in config["material_specification"]
    assert "unpainted" in str(config["finish"]).lower()
    assert int(config["quantity"]) == 2
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_color(adapter, HARDENED_STEEL)" in source
    assert part.HARDENED_STEEL == (0.30, 0.30, 0.31)


def test_close_bore_clears_the_hex_trunnion_only_at_the_ridge() -> None:
    import math

    from summing_lever_spec import HEX_H, HEX_W

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

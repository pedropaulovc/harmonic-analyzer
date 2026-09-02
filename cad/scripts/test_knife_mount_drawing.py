"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

from pathlib import Path

import build_knife_mount as part
import draw_knife_mount as drawing
import knife_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_ground_bore_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = knife_mount_spec.SURFACE_FINISHES
    assert control.key == "knife_bore"
    assert control.roughness_um == knife_mount_spec.GROUND_UM == 0.8
    assert control.face.diameter_mm == 2.0 * knife_mount_spec.R_BORE
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "surface_finishes=SURFACE_FINISHES" in part_source
    assert 'surface_finish_by_key(SURFACE_FINISHES, "knife_bore")' in drawing_source
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


def test_linked_notes_expose_the_stud_tap_and_hardened_knife_seat() -> None:
    notes = knife_mount_spec.DRAWING_NOTES
    assert f"BORE Ø{2.0 * knife_mount_spec.R_BORE:.1f} THRU, CENTRED IN THE {2.0 * knife_mount_spec.BLK_HALF_X:.2f} WIDTH" in notes
    assert "BORE Ø12.0 THRU" in notes
    assert "TAP 1/2-13 UNC-2B X 12.0 DEEP" in notes
    assert "KNIFE-HANGER STUD" in notes
    assert "TAP-DRILL POINT BREAKS INTO THE BORE CROWN" in notes
    # ch18 p.42 (2026-09-02): the block IS the hardened knife seat -- the old
    # "no hardened seat / do not release" hold is gone.
    assert "HARDEN AND TEMPER TO 58-60 HRC AFTER MACHINING" in notes
    assert "LEAVE UNPAINTED" in notes
    assert "NO HARDENED KNIFE SEAT" not in notes
    assert "DO NOT RELEASE" not in notes
    # Title block owns the alloy callout (test_magnifier_drawing_metadata).
    assert "MATERIAL:" not in notes
    assert "Ra 0.8" not in notes
    assert "GRAY IRON" not in notes and "PAINT BLACK" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    assert "LINEAR +/-" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_bore_geometry() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert 'characteristic="position"' in source
    assert source.count("add_edge_dimension(") == 1


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

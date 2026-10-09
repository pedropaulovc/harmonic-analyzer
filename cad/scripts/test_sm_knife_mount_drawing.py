"""Offline contracts for the knife-mount drawing."""

from __future__ import annotations

from pathlib import Path

import build_sm_knife_mount as part
import draw_sm_knife_mount as drawing
import sm_knife_mount_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_ground_bore_finish_is_part_owned_and_consumed_by_key() -> None:
    (control,) = sm_knife_mount_spec.SURFACE_FINISHES
    assert control.key == "knife_bore"
    assert control.roughness_um == sm_knife_mount_spec.GROUND_UM == 0.8
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
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # Every marked dowel-hole dimension carries part-authored places.
    assert set(sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME) == {
        "PinHoleDia",
        "PinHoleX",
        "PinHoleDepth",
    }
    for feature, names in sm_knife_mount_spec.DRAWING_PRECISION.items():
        assert set(names) <= sm_knife_mount_spec.DRAWING_DIMENSIONS[feature]


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
    # Dowel hole: printed places and the volume the build's gate expects.
    assert sm_knife_mount_spec.PIN_HOLE_X == 6.350
    assert sm_knife_mount_spec.DRAWING_PRECISION_BY_NAME == {
        "PinHoleDia": 3,
        "PinHoleX": 3,
        "PinHoleDepth": 1,
    }
    import math

    assert abs(part.V_PIN - math.pi * (3.175 / 2.0) ** 2 * 9.5) < 1e-9
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH)" in source
    assert '"PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_DIA_BAND)' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source


def test_linked_notes_expose_the_stud_tap_and_hardened_knife_seat() -> None:
    notes = sm_knife_mount_spec.DRAWING_NOTES
    assert f"BORE Ø{2.0 * sm_knife_mount_spec.R_BORE:.1f} THRU, CENTRED IN THE {2.0 * sm_knife_mount_spec.BLK_HALF_X:.2f} WIDTH" in notes
    assert "BORE Ø12.0 THRU" in notes
    notes_and_callouts = notes + "\n" + sm_knife_mount_spec.PIN_HOLE_CALLOUT
    # Redesign: a #6-32 bottoming tap (no 1/2-13 stud, no bore-crown break-in).
    assert "1/2-13" not in notes_and_callouts
    assert "BREAKS INTO" not in notes_and_callouts
    assert "TAP #6-32 UNC-2B BOTTOMING X 9.70 FULL THREAD" in notes
    assert "Ø2.71 X 10.90" in notes
    assert "MHA-VN-024 SCREW CLAMPS THE SEAT" in notes
    assert "CENTRE 20.62 BELOW THE TOP SEAT" in notes
    # Rule 6: the hanger text is at most four short lines.
    lines = notes.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith("TAP #6-32"))
    last = next(i for i, line in enumerate(lines) if "CROSSBAR UNDERSIDE" in line)
    assert last - first + 1 <= 4
    # The dowel hole's press rides the Ø callout (MHA-PD-018 precedent).
    assert sm_knife_mount_spec.PIN_HOLE_CALLOUT.splitlines() == [
        "BLIND FLAT-BOTTOM REAM",
        "PRESS MHA-VN-051 DOWEL TO FLOOR",
        "0.0025/0.0177 INTERFERENCE",
    ]
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
    # The block depth is the one sheet-added dimension; the dowel hole's Ø,
    # station and depth are marked model dimensions (DRAWING_DIMENSIONS).
    assert source.count("add_edge_dimension(") == 1


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("sm-knife-mount")
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

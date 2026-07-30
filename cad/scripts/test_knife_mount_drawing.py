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


def test_linked_notes_expose_the_unresolved_knife_seat_and_mounting_pattern() -> None:
    notes = knife_mount_spec.DRAWING_NOTES
    assert "BORE Ø25.4 THRU" in notes
    assert "NO HARDENED KNIFE SEAT" in notes
    assert "MOUNT-TO-CROSSBAR" in notes
    assert "DO NOT RELEASE" in notes
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
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 2

"""Offline contracts for the lever-wire drawing."""

from __future__ import annotations

from pathlib import Path

import build_mg_vn_lever_wire as part
import draw_sh_vn_music_wire as drawing
import sh_vn_music_wire_lever_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-vn-lever-wire.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-vn-lever-wire.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-vn-lever-wire_drawing.png")
    assert DRAWINGS_BY_NAME["mg_vn_lever_wire"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is sh_vn_music_wire_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*sh_vn_music_wire_lever_spec.DRAWING_DIMENSIONS.values()) if (
        sh_vn_music_wire_lever_spec.DRAWING_DIMENSIONS
    ) else set()
    kept = set(drawing.FRONT_KEEP)
    # Note-based wire: nothing is marked, nothing is kept.
    assert marked == set()
    assert kept == marked


def test_form_and_finish_are_note_based_on_the_unpickable_wire() -> None:
    # A Ø0.8 silhouette cylinder has no dependable pick, so the sheet carries no
    # datum / FCF / surface-finish symbol / coordinate-picked dimension -- only
    # the auto-imported (empty) set + property-linked notes.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 0
    assert source.count("add_feature_control_frame(") == 0
    assert source.count("add_surface_finish(") == 0
    assert source.count("add_edge_dimension(") == 0
    assert source.count("add_native_hole_callout(") == 0
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_do_not_misrepresent_the_rest_run_as_a_cut_length() -> None:
    import _config

    notes = sh_vn_music_wire_lever_spec.DRAWING_NOTES
    (sku,) = _config.parts("mg-vn-lever-wire")["supplier_skus"]
    assert sku in notes
    assert "ASTM A228" not in notes
    assert "X.XX" not in notes and "X.XXX" not in notes
    # The endpoint chord is computed in the build and labelled only as the
    # straight rest-run length; the unmodelled hook/wrap keep the sheet unreleased.
    assert "DO NOT RELEASE" in notes
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "STRAIGHT REST-RUN LENGTH {WIRE_LEN" in part_source
    assert "NOT A CUT LENGTH" in part_source


def test_wire_geom_split_keeps_notes_out_of_consumer_recipes() -> None:
    # The endpoint/yoke solver lives in the drawing-free lever_wire_geom module
    # (codex #360): the assembly and the wheel import the anchors from THERE --
    # never from build_lever_wire, whose lever_wire_spec import would drag the
    # sheet notes into their recipe closures and cache keys.
    assert Path(part.__file__).with_name("mg_vn_lever_wire_geom.py").exists()
    for consumer in ("build_mg_magnifier_assembly.py", "build_mg_magnifying_wheel.py"):
        source = Path(part.__file__).with_name(consumer).read_text(encoding="utf-8")
        assert "from mg_vn_lever_wire_geom import" in source
        assert "from build_mg_vn_lever_wire import" not in source

    verify_source = Path(part.__file__).with_name("verify.py").read_text(
        encoding="utf-8"
    )
    assert "import mg_vn_lever_wire_geom as _wire" in verify_source
    assert "import build_mg_vn_lever_wire as _hw" not in verify_source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-vn-lever-wire")
    assert config["process"] == "purchased"
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_the_balloon_ring_is_a_shape_neutral_mid_run_split() -> None:
    # MHA-MG-00 lands the wire's balloon on this ring; it must not change the
    # wire, so it is a split line (no added solid feature) at mid-run.
    assert part.BALLOON_RING_STATION == sh_vn_music_wire_lever_spec.BALLOON_RING_FRACTION * part.WIRE_LEN
    assert 0.0 < sh_vn_music_wire_lever_spec.BALLOON_RING_FRACTION < 1.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("InsertSplitLineProject(") == 1
    assert "create_extrusion(" in source and source.count("create_extrusion(") == 1
    assert 'blank_sketch(adapter, "BalloonRingReference")' in source

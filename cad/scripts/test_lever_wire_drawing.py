"""Offline contracts for the lever-wire drawing."""

from __future__ import annotations

from pathlib import Path

import build_lever_wire as part
import draw_lever_wire as drawing
import lever_wire_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/lever-wire.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/lever-wire.pdf")
    assert drawing.PNG.as_posix().endswith("/png/lever-wire_drawing.png")
    assert DRAWINGS_BY_NAME["lever_wire"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is lever_wire_spec.DRAWING_DIMENSIONS
    marked = set().union(*lever_wire_spec.DRAWING_DIMENSIONS.values()) if (
        lever_wire_spec.DRAWING_DIMENSIONS
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
    notes = lever_wire_spec.DRAWING_NOTES
    assert "Ø0.8" in notes
    assert "ASTM A228" not in notes
    assert "SPRING-STEEL" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "DO NOT RELEASE" in notes
    assert "DEVELOPED CUT LENGTH ARE NOT DEFINED" in notes
    assert "PER THE MAGNIFIER ASSEMBLY" not in notes
    assert "X.XX" not in notes and "X.XXX" not in notes
    # The endpoint chord is computed in the build and labelled only as the
    # straight rest-run length.  The unmodeled hook/wrap cannot be assigned a
    # fabricated cut length without inventing an allowance.
    assert lever_wire_spec.WIRE_DIA == part.WIRE_DIA == 0.8
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "STRAIGHT REST-RUN LENGTH {WIRE_LEN" in part_source
    assert "NOT A CUT LENGTH" in part_source


def test_wire_geom_split_keeps_notes_out_of_consumer_recipes() -> None:
    # The endpoint/yoke solver lives in the drawing-free lever_wire_geom module
    # (codex #360): the assembly and the wheel import the anchors from THERE --
    # never from build_lever_wire, whose lever_wire_spec import would drag the
    # sheet notes into their recipe closures and cache keys.
    assert Path(part.__file__).with_name("lever_wire_geom.py").exists()
    for consumer in (
        "build_magnifier_assembly.py",
        "build_magnifying_wheel.py",
        "verify.py",
    ):
        source = Path(part.__file__).with_name(consumer).read_text(encoding="utf-8")
        if consumer == "verify.py":
            assert "import lever_wire_geom as _wire" in source
            assert "_wire." in source
        else:
            assert "from lever_wire_geom import" in source
        assert "from build_lever_wire import" not in source
        assert "_hw." not in source

    verify_source = Path(part.__file__).with_name("verify.py").read_text(
        encoding="utf-8"
    )
    assert "import lever_wire_geom as _wire" in verify_source
    assert "import build_lever_wire as _hw" not in verify_source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lever-wire")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

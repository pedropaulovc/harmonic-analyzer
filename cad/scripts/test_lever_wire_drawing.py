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


def test_wire_keeps_no_geom_split_but_stays_assembly_coupled() -> None:
    # Unlike the four nominal-coupled magnifier parts, the wire's assembly
    # coupling is an endpoint SOLVER living in the build, so it keeps no _geom
    # split; the assembly still imports the computed endpoints from the build.
    assert not Path(part.__file__).with_name("lever_wire_geom.py").exists()
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from build_lever_wire import" in assembly


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("lever-wire")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

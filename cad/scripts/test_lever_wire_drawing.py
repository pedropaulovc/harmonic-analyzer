"""Offline contracts for the lever-wire drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a wire carries wire
data only (diameter, the forming instruction, and the build-stamped straight
rest-run length), no datum, frame, roughness or basic dimension.
"""

from __future__ import annotations

from pathlib import Path

import build_lever_wire as part
import draw_lever_wire as drawing
import lever_wire_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


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


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # A Ø0.8 silhouette cylinder has no dependable pick, and the policy wants
    # none of these on a wire anyway -- only the property-linked notes.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_edge_dimension(",
        "add_native_hole_callout(",
    ):
        assert helper not in source, helper
    assert not hasattr(lever_wire_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(lever_wire_spec, "SURFACE_FINISHES")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_notes_are_wire_data_and_the_stamped_rest_run_stays_honest() -> None:
    notes = lever_wire_spec.DRAWING_NOTES
    lines = notes.split("\n")
    # Two spec lines + the build-appended rest-run line = three on the sheet.
    assert len(lines) <= 3
    assert "Ø0.8 WIRE, ONE PIECE." in notes
    assert "END HOOK AND HUB WRAP FORMED AT ASSEMBLY" in notes
    for banned in (
        "DO NOT RELEASE",
        "NOT DEFINED",
        "SOURCE MODEL",
        "ASTM A228",
        "SPRING-STEEL",
        "PER THE MAGNIFIER ASSEMBLY",
        "UOS",
        "DIMENSIONS IN",
        "+/-",
        "DATUM",
        "MHA-",
        "DEBURR",
        "BREAK SHARP",
        "X.XX",
    ):
        assert banned not in notes, banned
    # The endpoint chord is computed in the build and labelled only as the
    # straight rest-run length.  The unmodeled hook/wrap cannot be assigned a
    # fabricated cut length without inventing an allowance.
    assert lever_wire_spec.WIRE_DIA == part.WIRE_DIA == 0.8
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "STRAIGHT REST-RUN LENGTH {WIRE_LEN" in part_source
    assert "NOT A CUT LENGTH" in part_source


def test_hidden_lines_stay_on_in_the_orthographic_view() -> None:
    source = _source()
    assert "set_hidden_lines_visible(adapter, front)" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert drawing.WIRE_SCALE == (1, 5)


def test_wire_geom_split_keeps_notes_out_of_consumer_recipes() -> None:
    # The endpoint/yoke solver lives in the drawing-free lever_wire_geom module
    # (codex #360): the assembly and the wheel import the anchors from THERE --
    # never from build_lever_wire, whose lever_wire_spec import would drag the
    # sheet notes into their recipe closures and cache keys.
    assert Path(part.__file__).with_name("lever_wire_geom.py").exists()
    for consumer in ("build_magnifier_assembly.py", "build_magnifying_wheel.py"):
        source = Path(part.__file__).with_name(consumer).read_text(encoding="utf-8")
        assert "from lever_wire_geom import" in source
        assert "from build_lever_wire import" not in source

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
    # The library material renders the model; the spec is what the shop buys
    # (the title block's MATERIAL cell shows the spec).
    assert config["material_specification"] == "ASTM A228 music-wire spring steel"
    assert config["material_specification"] != config["material"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

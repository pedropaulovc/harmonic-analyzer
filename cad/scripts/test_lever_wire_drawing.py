"""Offline contracts for the lever-wire drawing.

The print follows cad/docs/drawing-simplicity-policy.md: the sheet runs 1:5
(the scale of the front and isometric views), the wire diameter is a marked
model dimension read on a 10:1 end view with the bought-wire band on the
model, the straight rest-run is the marked extrusion depth shown as a
reference dimension, and the one note is the forming instruction.  No datum,
frame, roughness or basic dimension.
"""

from __future__ import annotations

from pathlib import Path

import build_lever_wire as part
import draw_lever_wire as drawing
import lever_wire_spec
from _drawing_contract import model_toleranced_dimensions
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
    marked = set().union(*lever_wire_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.END_KEEP)
    assert kept == marked == {"WireDiaDim", "Depth"}
    # The Ø reads on the enlarged end view, the rest-run on the front view.
    assert set(drawing.END_KEEP) == {"WireDiaDim"}
    assert set(drawing.FRONT_KEEP) == {"Depth"}
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert set(drawing.DIMENSION_PRECISION) <= kept
    assert set(drawing.REFERENCE_DIMENSIONS) <= kept
    # The extrusion depth is renamed Depth in the build (the shaft idiom) so
    # the mark resolves.
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_dimensions(adapter, "Wire", ["Depth"])' in part_source


def test_wire_diameter_band_rides_the_model_dimension() -> None:
    # Policy rule 2: neither title-block band (+/-0.8, +/-0.51) fits a 0.8
    # wire, so the bought-wire band is a native symmetric tolerance on
    # WireDiaDim, printed on the 10:1 end view at two places.
    assert lever_wire_spec.WIRE_DIA_TOLERANCE_MM == 0.02
    assert model_toleranced_dimensions(part) == {
        ("WireProfile", "WireDiaDim"): "WIRE_DIA_TOLERANCE_MM"
    }
    assert drawing.DIMENSION_PRECISION == {"WireDiaDim": 2}
    assert drawing.END_SCALE == (10, 1)
    source = _source()
    assert '"*Top"' in source
    # The end view is curated before the front view so it claims the circle.
    assert source.index("keep=END_KEEP") < source.index("keep=FRONT_KEEP")


def test_rest_run_is_a_reference_dimension_between_named_ends() -> None:
    # The straight rest-run is informational (the wire is cut long and formed
    # at assembly), so it prints parenthesised with both ends named -- never
    # as a cut length, never in a note.
    assert drawing.REFERENCE_DIMENSIONS == ("Depth",)
    assert drawing.DIMENSION_CALLOUTS == {
        "Depth": "STRAIGHT REST RUN, HUB END TO HOOK END"
    }
    source = _source()
    assert "set_reference_dimension(" in source
    assert "set_reference_dimensions(" not in source  # the plural adds a Ø
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert "STRAIGHT REST-RUN LENGTH" not in part_source
    assert "NOT A CUT LENGTH" not in part_source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
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


def test_notes_are_the_forming_instruction_only() -> None:
    notes = lever_wire_spec.DRAWING_NOTES
    assert notes.split("\n") == [
        "ONE PIECE. END HOOK AND HUB WRAP FORMED AT ASSEMBLY; CUT LONG AND TRIM."
    ]
    # Every number is on a view: no diameter, no length, no tolerance.
    assert not any(character.isdigit() for character in notes)
    for banned in (
        "Ø",
        "CUT LENGTH",
        "REST-RUN",
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
    assert lever_wire_spec.WIRE_DIA == part.WIRE_DIA == 0.8


def test_sheet_scale_matches_the_views() -> None:
    # Machinist review 2026-09-02: the title block said 1:1 while both views
    # said 1:5.  The sheet is 1:5 now; the captions of the views AT the sheet
    # scale do not repeat it, the enlarged end view states its own.
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert drawing.WIRE_SCALE == (1, 5)
    assert lever_wire_spec.FRONT_VIEW_NOTE == "FRONT VIEW"
    assert lever_wire_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW"
    assert lever_wire_spec.END_VIEW_NOTE == "END VIEW SCALE 10:1"
    source = _source()
    assert "scale=WIRE_SCALE" in source
    assert "scale=END_SCALE" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (front, end):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source
    assert source.count("set_hidden_lines_removed(") == 1


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
    # The band constant lives in the import-pure spec, never in the geom the
    # assembly reads.
    geom_source = Path(part.__file__).with_name("lever_wire_geom.py").read_text(
        encoding="utf-8"
    )
    assert "WIRE_DIA_TOLERANCE_MM" not in geom_source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert '"End View Note": END_VIEW_NOTE' in source
    import _config

    config = _config.parts("lever-wire")
    # The library material renders the model; the spec is what the shop buys
    # (the title block's MATERIAL cell shows the spec).
    assert config["material_specification"] == "ASTM A228 music-wire spring steel"
    assert config["material_specification"] != config["material"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

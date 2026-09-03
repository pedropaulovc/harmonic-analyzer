"""Offline contracts for the magnifying-bracket drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a bracket is not on
the GD&T allowlist and it is lock-mated to the lever rod in service, so it
carries no datum, frame, roughness or basic dimension; the notes are three
lines carrying the collar and thicknesses the marked set cannot, plus the
match-drill instruction for the unmodelled mounting pattern.
"""

from __future__ import annotations

from pathlib import Path

import build_magnifying_bracket as part
import draw_magnifying_bracket as drawing
import magnifying_bracket_spec
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-bracket.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-bracket.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-bracket_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_bracket"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_bracket_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_bracket_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert marked == {"ArmWidth", "ArmDepth", "FlangeWidth", "FlangeDepth"}


def test_arm_and_flange_dim_names_are_disambiguated() -> None:
    # Arm + flange are both extruded rectangles emitting bare "Width"/"Depth";
    # the build renames them per-feature so the top view's keep map is
    # unambiguous.  The collision would otherwise repoint the wrong dimension.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"ArmWidth", "ArmDepth"' in source
    assert '"FlangeWidth", "FlangeDepth"' in source


def test_bracket_is_uncoupled_from_the_assembly_nominals() -> None:
    # The magnifier assembly places the bracket BY NAME and mates it by named
    # references, so it imports no bracket Python constant -- hence one _spec
    # module is right (no _geom split).
    assert not Path(part.__file__).with_name("magnifying_bracket_geom.py").exists()
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from build_magnifying_bracket import" not in assembly


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = magnifying_bracket_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    # The collar and the thicknesses have no marked dimension: the note is
    # their only carrier.
    assert "COLLAR Ø12 OD X 10 LONG, BORE Ø6.2 DRILL THRU" in notes
    assert "ARM 7.5 THICK; FLANGE 5 THICK." in notes
    # The unmodelled mounting pattern is a process instruction, not a hold.
    assert "MATCH-DRILL TO THE SUMMING PLATE AT ASSEMBLY" in notes
    for banned in (
        "DO NOT RELEASE",
        "UNDRILLED BLANK",
        "NOT DEFINED",
        "AISI 1018",
        "BLACK-OXIDE",
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
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in _source()


def test_plan_dimensions_are_labelled() -> None:
    assert drawing.DIMENSION_CALLOUTS == {
        "ArmWidth": "ARM WIDTH",
        "ArmDepth": "ARM LENGTH",
        "FlangeWidth": "FLANGE WIDTH",
        "FlangeDepth": "FLANGE DEPTH",
    }


def test_collar_bore_takes_the_center_mark() -> None:
    source = _source()
    assert source.count("auto_center_marks(") == 1
    assert source.count("add_edge_dimension(") == 0


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(magnifying_bracket_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(magnifying_bracket_spec, "SURFACE_FINISHES")


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (top, front, right):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_unresolved_mounting_pattern_is_not_encoded_as_fake_geometry() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "SCREW_HOLE_DIA" not in source
    assert "SCREW_HOLE_X" not in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-bracket")
    # The library material renders the model; the spec is what the shop buys
    # (the title block's MATERIAL cell shows the spec).
    assert config["material_specification"] == "AISI 1018 cold-finished steel bar"
    assert config["material_specification"] != config["material"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

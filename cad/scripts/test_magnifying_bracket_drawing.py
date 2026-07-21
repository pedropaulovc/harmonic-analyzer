"""Offline contracts for the magnifying-bracket drawing."""

from __future__ import annotations

from pathlib import Path

import build_magnifying_bracket as part
import draw_magnifying_bracket as drawing
import magnifying_bracket_spec
from _drawing_registry import DRAWINGS_BY_NAME


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


def test_notes_carry_the_collar_and_fit_that_have_no_marked_dim() -> None:
    notes = magnifying_bracket_spec.DRAWING_NOTES
    assert "Ø12 OD" in notes
    assert "Ø6.2" in notes
    assert "AISI 1018" not in notes
    assert "BLACK-OXIDE" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes and "X.XXX" not in notes


def test_collar_bore_takes_the_center_mark() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("auto_center_marks(") == 1
    # First draft leans on marked plan dims + notes; no coordinate-picked GD&T.
    assert source.count("add_edge_dimension(") == 0


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-bracket")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

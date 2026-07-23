"""Offline contracts for the magnifying-wheel drawing."""

from __future__ import annotations

from pathlib import Path

import build_magnifying_wheel as part
import draw_magnifying_wheel as drawing
import magnifying_wheel_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/magnifying-wheel.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/magnifying-wheel.pdf")
    assert drawing.PNG.as_posix().endswith("/png/magnifying-wheel_drawing.png")
    assert (
        DRAWINGS_BY_NAME["magnifying_wheel"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is magnifying_wheel_spec.DRAWING_DIMENSIONS
    marked = set().union(*magnifying_wheel_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The hub diameter + spoke axial the assembly imports live in the drawing-
    # FREE geom module, so a print-note edit cannot enter the assembly recipe.
    import magnifying_wheel_geom as geom

    assert (geom.RIM_OUTER_DIA, geom.HUB_DIA, geom.SPOKE_COUNT) == (100.0, 20.0, 6)
    assembly = Path(part.__file__).with_name("build_magnifier_assembly.py").read_text(
        encoding="utf-8"
    )
    assert "from magnifying_wheel_geom import HUB_DIA, SPOKE_AXIAL" in assembly
    assert "from build_magnifying_wheel import" not in assembly


def test_linked_notes_specify_the_ratio_and_spokes() -> None:
    notes = magnifying_wheel_spec.DRAWING_NOTES
    assert "5X" in notes
    assert "6 STRAIGHT SPOKES" in notes
    assert "5 WIDE x 4 THICK" in notes
    assert "GROOVED BRASS HUB DRUM" in notes
    assert "CURRENT ONE-PIECE SOURCE MODEL" in notes
    assert "DO NOT" in notes and "RELEASE" in notes
    assert "GRAY-IRON" not in notes and "BLACK-PAINTED" not in notes
    assert "DEBURR" not in notes and "BREAK SHARP" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_native_gdt_and_axial_dims() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 1
    assert source.count("add_feature_control_frame(") == 1
    assert (
        "        symbol_xy=(FRONT_CENTER[0] + 0.0081, FRONT_CENTER[1] + 0.0130),\n"
        '        datum="A",\n'
        '        label="axle bore axis",\n'
        "        position_tolerance_m=0.0035,"
        in source
    )
    assert source.count("position_tolerance_m=0.0035") == 1
    assert 'characteristic="circular_runout"' in source
    assert source.count("add_surface_finish(") == 1
    # hub + rim axial widths added across the section.
    assert source.count("add_edge_dimension(") == 2


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("magnifying-wheel")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

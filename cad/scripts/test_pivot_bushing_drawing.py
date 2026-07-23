"""Offline contracts for the pivot-bushing drawing."""

from __future__ import annotations

from pathlib import Path

import build_pivot_bushing as part
import draw_pivot_bushing as drawing
import pivot_bushing_spec
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pivot-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pivot-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pivot-bushing_drawing.png")
    assert DRAWINGS_BY_NAME["pivot_bushing"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pivot_bushing_spec.DRAWING_DIMENSIONS
    marked = set().union(*pivot_bushing_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert (drawing.OUTER_DIA, drawing.BORE_DIA, drawing.LENGTH) == (
        pivot_bushing_spec.OUTER_DIA,
        pivot_bushing_spec.BORE_DIA,
        pivot_bushing_spec.LENGTH,
    )


def test_linked_notes_define_remaining_turned_part_operations() -> None:
    notes = pivot_bushing_spec.DRAWING_NOTES
    assert "REAM BORE THRU" in notes
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "+/-0.03"
    assert "+0.03/-0.00" in drawing.DIMENSION_CALLOUTS["BoreDia"]
    clearance_min = pivot_bushing_spec.BORE_DIA - 6.35
    clearance_max = clearance_min + 0.03 + 0.02
    assert round(clearance_min, 2) == 0.15
    assert round(clearance_max, 2) == 0.20
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_bushing_functional_surfaces() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 2
    assert (
        "        edge_xy=bore_top,\n"
        "        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.037),\n"
        '        datum="A",\n'
        '        label="bushing bore axis",\n'
        "        position_tolerance_m=0.00001,"
        in source
    )
    assert source.count("position_tolerance_m=0.00001") == 1
    assert "characteristic=\"circular_runout\"" in source
    assert "characteristic=\"parallelism\"" in source
    assert source.count("add_surface_finish(") == 1
    assert source.count("add_view_centerline(") == 1


def test_sheet_and_views_pin_scale() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(4, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("pivot-bushing")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 19

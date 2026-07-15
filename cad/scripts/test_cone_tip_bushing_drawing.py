"""Offline contracts for the cone-tip-bushing drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_bushing as part
import cone_tip_bushing_spec
import draw_cone_tip_bushing as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-bushing_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_tip_bushing"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_tip_bushing_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_tip_bushing_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.END_KEEP) | set(drawing.SIDE_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    assert set(drawing.DIMENSION_PRECISION) <= kept
    assert (drawing.OUTER_DIA, drawing.BORE_DIA, drawing.LENGTH) == (
        cone_tip_bushing_spec.OUTER_DIA,
        cone_tip_bushing_spec.BORE_DIA,
        cone_tip_bushing_spec.LENGTH,
    )


def test_linked_notes_define_remaining_turned_part_operations() -> None:
    notes = cone_tip_bushing_spec.DRAWING_NOTES
    assert "DRILL 1/32 IN (0.794) BORE THRU" in notes
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "+/-0.03"
    assert "+0.05/-0.00" in drawing.DIMENSION_CALLOUTS["BoreDiaDim"]
    # The bore rides the cone shaft's 1/32 in tip stub line-to-line at nominal;
    # the +0.05/-0.00 drilled callout keeps it a slip fit, never an interference.
    assert cone_tip_bushing_spec.BORE_DIA == 0.03125 * 25.4
    assert drawing.DIMENSION_PRECISION["BoreDiaDim"] == 3
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "def _manufacturing_notes" not in source


def test_native_gdt_controls_bushing_functional_surfaces() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"circular_runout\"" in source
    assert "characteristic=\"parallelism\"" in source
    assert source.count("add_surface_finish(") == 4
    assert source.count("add_view_centerline(") == 1


def test_sheet_and_views_pin_scale() -> None:
    assert drawing.SHEET_SCALE == (8.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(8, 1)") == 3


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-tip-bushing")
    assert "brass" in str(config["material_specification"]).lower()
    assert config["finish"]
    assert int(config["quantity"]) == 1

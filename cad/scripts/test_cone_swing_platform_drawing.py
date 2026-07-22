"""Offline contracts for the cone-swing-platform drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_swing_platform as part
import cone_swing_platform_spec
import draw_cone_swing_platform as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-swing-platform.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-swing-platform.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-swing-platform_drawing.png")
    assert (
        DRAWINGS_BY_NAME["cone_swing_platform"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is cone_swing_platform_spec.DRAWING_DIMENSIONS
    marked = set().union(*cone_swing_platform_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP)
    assert kept == marked


def test_notes_describe_pivot_notch_and_wedge() -> None:
    notes = cone_swing_platform_spec.DRAWING_NOTES
    assert "STEEL PLATE" not in notes
    assert "BLACK OXIDE" not in notes
    assert "DEBURR" not in notes
    assert "UOS" not in notes
    assert "PIVOT HOLE" in notes
    assert "LOCK NOTCH" in notes
    assert "6.756 +0.050/0 THRU" in notes
    assert "24.50 +/-0.10 WEST AND 190.10 +/-0.10 SOUTH" in notes
    assert "7.35 +/-0.10 DEG NORTH" in notes
    assert "FULL-R CLOSED END (R4.000 REF)" in notes
    assert "VIRTUAL-SHARP INTERSECTIONS" in notes
    assert "DATUM B IS THE" in notes
    assert "PIVOT-HOLE AXIS" in notes
    assert "DATUM C IS THE NORTH END PLANE" in notes
    assert "CENTRELINE THROUGH B NORMAL TO C" in notes
    assert "ALL-AROUND PLAN PROFILE IS CONTROLLED 0.25 TO A|B|C" in notes
    assert "OPEN THROUGH EDGE" in notes
    assert "NE R10.00, NW R8.00, SW R10.00, SE R12.00" in notes
    assert "FINISHED THICKNESS 6.35 +/-0.10" in notes
    assert "OPPOSITE-FACE PARALLELISM: SEE END VIEW" in notes
    assert "AS MODELLED" not in notes
    assert "SEE PLAN" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_add_cone_axis_centerline(adapter, top)" in source
    assert "view.ModelToViewTransform" in source
    assert "view.GetVisibleEntities2" in source
    assert "blind_cut_dia_mm(PIVOT_HOLE_SPEC)" in source
    assert "curve.CircleParams" in source
    assert "pivot_centers" in source
    assert "view.GetOutline()" in source
    assert "projected pivot center" in source
    assert "drawing.EditSheet()" in source
    assert "drawing.EditSketch()" not in source
    assert "_visible_broad_face_edges(adapter, end)" in source
    assert "_visible_plan_controls(adapter, top)" in source
    assert 'datum="B"' in source and "entity=pivot_edge" in source
    assert 'datum="C"' in source and "entity=north_edge" in source
    assert 'characteristic="profile_surface"' in source
    assert 'datums=("A", "B", "C")' in source
    assert 'quantity="ALL-AROUND PLAN PROFILE"' in source
    assert "all_around=True" in source
    assert 'characteristic="flatness"' in source
    assert 'characteristic="parallelism"' in source
    assert '{"PlateLenDim": "+/-0.25"}' in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 3.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(1, 2)") == 2
    assert source.count("scale=(1, 3)") == 1
    assert cone_swing_platform_spec.PLAN_VIEW_NOTE == "PLAN VIEW SCALE 1:2"
    assert (
        cone_swing_platform_spec.ISOMETRIC_VIEW_NOTE
        == "ISOMETRIC VIEW SCALE 1:3"
    )
    assert cone_swing_platform_spec.END_VIEW_NOTE == "END VIEW SCALE 1:2"


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("cone-swing-platform")
    assert config["material"] == config["material_specification"]
    assert "steel" in str(config["material_specification"]).lower()
    assert "5/16 in minimum stock" in str(config["material_specification"]).lower()
    finish = str(config["finish"]).lower()
    assert "mil-dtl-13924 class 1" in finish
    assert "oil seal" in finish
    assert int(config["quantity"]) == 1

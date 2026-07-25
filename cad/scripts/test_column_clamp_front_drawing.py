"""Offline contracts for the column-clamp-front drawing."""

from __future__ import annotations

from pathlib import Path

import column_clamp_front_spec as spec
import draw_column_clamp_front as drawing
import build_column_clamp_front as part
import _clamp_arc
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/column-clamp-front.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/column-clamp-front.pdf")
    assert drawing.PNG.as_posix().endswith("/png/column-clamp-front_drawing.png")
    assert (
        DRAWINGS_BY_NAME["column_clamp_front"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_spec_nominals_mirror_the_shared_arc_builder() -> None:
    # The geometry is cut by the SHARED _clamp_arc builder; the spec's nominals
    # are drawing-side mirrors, so each must equal its builder-side source.
    assert spec.ARC_DEPTH == part.DEPTH
    assert spec.ARC_WIDTH == _clamp_arc.ARC_WIDTH
    assert spec.ARC_HEIGHT == 2.0 * _clamp_arc.ARC_HALF_H
    assert spec.COLUMN_BORE == _clamp_arc.COLUMN_BORE
    assert spec.EAR_HOLE_Z == _clamp_arc.EAR_HOLE_Z
    assert spec.EAR_HOLE_DIA == blind_cut_dia_mm(part.HOLE_SPEC)
    assert spec.EAR_SPACING == 2.0 * spec.EAR_HOLE_Z
    assert spec.BORE_RADIUS == spec.COLUMN_BORE / 2.0


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_use_us_customary_fasteners_and_functional_tolerances() -> None:
    notes = spec.DRAWING_NOTES
    assert "#8 CLEARANCE" in notes
    assert "#8-32" in notes
    assert "MHA-106" in notes  # the mating back arc the pair is bored with
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series ("BACK ARC" is not a BA thread).
    assert "0BA" not in notes and "2BA" not in notes and "4BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["BoreDia"].startswith("THRU")
    assert "25.4" in callouts["BoreDia"]  # the column the relief slips on


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 2
    assert (
        "        edge_xy=(_plan_x(BORE_RADIUS), TOP_CENTER[1]),\n"
        "        symbol_xy=(0.150, TOP_CENTER[1]),\n"
        '        datum="B",\n'
        '        label="column-relief bore",\n'
        in source
    )
    assert source.count("add_feature_control_frame(") == 2
    assert "characteristic=\"parallelism\"" in source
    assert "characteristic=\"position\"" in source
    assert "quantity=\"2X\"" in source  # both ear holes under one FCF


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    # The ear holes are ONE native Hole Wizard feature: their size lives in an
    # associative hole callout, never a marked sketch dimension.
    assert "EarHoles" not in spec.DRAWING_DIMENSIONS
    part_source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("clearance", "#8")' in part_source
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_native_hole_callout(" in drawing_source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    row = _config.parts("column-clamp-front")
    assert row["material_specification"]
    assert row["finish"]
    # One clamp pair per front column: two on the paper-drive platen bar plus
    # one at the magnifier wheel bar.
    assert int(row["quantity"]) == 3

"""Offline contracts for the column-clamp-front drawing."""

from __future__ import annotations

from pathlib import Path

import sh_column_clamp_front_spec as spec
import draw_sh_column_clamp_front as drawing
import build_sh_column_clamp_front as part
import _clamp_arc
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/sh-column-clamp-front.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/sh-column-clamp-front.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sh-column-clamp-front_drawing.png")
    assert (
        DRAWINGS_BY_NAME["sh_column_clamp_front"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_sh_column_clamp_front.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    annotated = (
        set(drawing.DIMENSION_CALLOUTS)
        | set(drawing.ABOVE_CALLOUTS)
        | set(drawing.DIMENSION_PREFIXES)
        | set(drawing.REFERENCE_DIMENSIONS)
    )
    assert annotated <= kept


def test_geometry_and_hole_contracts_are_part_owned() -> None:
    assert spec.ARC_DEPTH == part.DEPTH
    assert spec.ARC_WIDTH == _clamp_arc.ARC_WIDTH
    assert spec.ARC_HEIGHT == 2.0 * _clamp_arc.ARC_HALF_H
    assert spec.COLUMN_BORE == _clamp_arc.COLUMN_BORE
    assert spec.EAR_HOLE_Z == _clamp_arc.EAR_HOLE_Z
    assert part.EAR_HOLE_SPEC is spec.EAR_HOLE_SPEC
    assert spec.EAR_HOLE_SPEC.kind == "clearance"
    assert spec.EAR_HOLE_SPEC.size == "#8"
    assert spec.EAR_HOLE_DIA == blind_cut_dia_mm(spec.EAR_HOLE_SPEC)
    assert spec.EAR_SPACING == 2.0 * spec.EAR_HOLE_Z
    assert spec.BORE_RADIUS == spec.COLUMN_BORE / 2.0


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert "for view in (right, iso):" in source
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_bore_prints_the_grip_budget_on_the_column() -> None:
    # #970: the bore is matched to the purchased column at the clearance the
    # pair's grip budget allows (sh_column_clamp_fit), not "bored as a pair".
    bore = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "DIAMETRAL" in bore and "MHA-FR-003" in bore
    assert f"{spec.BORE_DIAMETRAL_CLEARANCE[1]:.2f}" in bore
    assert spec.BORE_DIAMETRAL_CLEARANCE[1] <= 0.30
    assert "MHA-SH-002" in drawing.ABOVE_CALLOUTS["EarHole1Z"]
    assert "\n" not in drawing.ABOVE_CALLOUTS["EarHole1Z"]
    assert min(spec.WALLS_WORST.values()) >= spec.WALL_TARGET


def test_sheet_has_no_gdt_notes_or_drawing_precision() -> None:
    # Clamps are not on the drawing-simplicity GD&T allowlist; the ear holes
    # locate by +/- from the bore axis, authored on the part.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "set_basic_dimension(" not in source
    assert "set_dimension_precision" not in source
    assert '"Manufacturing Notes"' not in source
    assert not hasattr(spec, "DRAWING_NOTES")
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert "add_native_hole_callout(" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "EAR_STATION_BAND" in source
    import _config

    row = _config.parts("sh-column-clamp-front")
    assert row["material_specification"]
    assert "oiled" in row["finish"]
    # One clamp pair per front column: two on the paper-drive platen bar plus
    # one at the magnifier wheel bar.
    assert int(row["quantity"]) == 3

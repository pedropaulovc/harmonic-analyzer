"""Offline contracts for the column-clamp-back drawing (MHA-SH-002)."""

from __future__ import annotations

import math
from pathlib import Path

import _clamp_arc
import _column_clamp_drawing
import _drawing_hidden_sketches
import _config
import build_sh_column_clamp_back as part
import draw_sh_column_clamp_back as drawing
import sh_column_clamp_back_geom as geom
import sh_column_clamp_back_spec as spec
import sh_column_clamp_fit as fit
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from fr_tube_frame_spec import OUTER_DIA


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/sh-column-clamp-back.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/sh-column-clamp-back.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sh-column-clamp-back_drawing.png")
    assert (
        DRAWINGS_BY_NAME["sh_column_clamp_back"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_sh_column_clamp_back.py" in PRECISION_MIGRATED_DRAWINGS


def test_marked_dimensions_are_exactly_the_kept_set() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.TOP_KEEP) | set(drawing.FACE_KEEP)
    assert kept == marked
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    annotated = (
        set(drawing.DIMENSION_CALLOUTS)
        | set(drawing.DIMENSION_PREFIXES)
        | set(drawing.REFERENCE_DIMENSIONS)
    )
    assert annotated <= kept
    assert set(spec.EAR_STATION_DIMENSIONS) >= set(spec.DRAWING_DIMENSIONS["EarHoles"])


def test_both_ears_located_by_one_model_owned_height() -> None:
    # Both ear centres hold the bar's centre plane: each placement y is zero,
    # which wizard_holes ties to the origin by a relation, not a dimension.
    assert _clamp_arc.EAR_HOLE_Y == 0.0
    assert [y for _, y in _clamp_arc.EAR_PLACEMENT] == [(None, None)] * 2
    # The hidden reference line runs from the midplane block's bottom face up
    # to that shared height under ear 1 (Right-plane x is model -z), so its
    # one printed length is the height of both ears.
    (bottom_x, bottom_y), (top_x, top_y) = _clamp_arc.EAR_HEIGHT_LINE
    assert bottom_x == top_x == -spec.EAR_HOLE_Z
    assert bottom_y == -spec.ARC_HEIGHT / 2.0
    assert top_y == _clamp_arc.EAR_HOLE_Y
    assert top_y - bottom_y == spec.EAR_HOLE_HEIGHT
    # The part marks it and authors its places; the sheet imports it in the
    # split-face view (showing the hidden sketch there), reads those places
    # back and prefixes it for the pair -- no sheet-side edge dimension.
    feature = _clamp_arc.EAR_HEIGHT_REFERENCE
    name = _clamp_arc.EAR_HEIGHT_DIMENSION
    assert spec.DRAWING_DIMENSIONS[feature] == {name}
    assert spec.DRAWING_PRECISION[feature] == {name: 2}
    assert drawing.DRAWING_PRECISION_BY_NAME is spec.DRAWING_PRECISION_BY_NAME
    assert not hasattr(spec, "EAR_HOLE_HEIGHT_PLACES")
    assert name in drawing.FACE_KEEP
    assert drawing.DIMENSION_PREFIXES[name] == "2X "
    assert (
        drawing.curate_view_dimensions
        is _drawing_hidden_sketches.curate_view_dimensions
    )
    assert not hasattr(drawing, "add_edge_dimension")
    assert part.build_arc is _clamp_arc.build_arc


def test_split_face_helpers_are_shared_with_the_front_arc() -> None:
    assert (
        drawing.set_dimension_prefixes is _column_clamp_drawing.set_dimension_prefixes
    )
    assert (
        drawing.add_bore_axis_centerline
        is _column_clamp_drawing.add_bore_axis_centerline
    )
    assert not hasattr(drawing, "_set_dimension_prefixes")
    assert not hasattr(drawing, "_add_bore_axis_centerline")


def test_geometry_mirrors_the_shared_builder() -> None:
    assert spec.ARC_WIDTH == _clamp_arc.ARC_WIDTH
    assert spec.ARC_HEIGHT == 2.0 * _clamp_arc.ARC_HALF_H
    assert spec.COLUMN_BORE == _clamp_arc.COLUMN_BORE
    assert spec.EAR_HOLE_Z == _clamp_arc.EAR_HOLE_Z
    assert part.DEPTH == geom.DEPTH == 15.5
    assert part.GRIP_OFFSET == geom.GRIP_OFFSET == 0.5
    assert geom.BLOCK_DEPTH == geom.DEPTH - geom.GRIP_OFFSET
    assert part.HOLE_SPEC is geom.HOLE_SPEC
    assert (geom.HOLE_SPEC.kind, geom.HOLE_SPEC.size) == ("tapped", "#8-32")
    assert geom.TAP_DRILL_DIA == blind_cut_dia_mm(geom.HOLE_SPEC)


def test_fit_budget_closes_at_the_printed_limits() -> None:
    assert fit.COLUMN_DIA == OUTER_DIA == 25.4
    low, high = fit.BORE_DIAMETRAL_CLEARANCE
    assert low < spec.COLUMN_BORE - OUTER_DIA < high
    # Faces stay apart with both bores at their loosest and the offset least.
    assert math.isclose(fit.GRIP_GAP_MIN, 0.4 - 0.3)
    assert fit.GRIP_GAP_MIN > 0.0
    # The ear stations' worst mismatch leaves screw float for drill wander.
    assert fit.EAR_STATION_MISMATCH_MAX < fit.SCREW_FLOAT


def test_walls_hold_the_rule_17_target_at_the_printed_worst_case() -> None:
    assert min(spec.WALLS_WORST.values()) >= spec.WALL_TARGET
    # The back wall the deepened arc buys (user ruling 2026-10-14).
    assert math.isclose(spec.BACK_WALL_MIN, 0.4 + 14.49 - 12.85)


def test_tight_bands_name_their_mate() -> None:
    bore = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "DIAMETRAL" in bore and "MHA-FR-003" in bore
    assert f"{fit.BORE_DIAMETRAL_CLEARANCE[0]:.2f}" in bore
    assert "MHA-SH-001" in drawing.DIMENSION_CALLOUTS["GripOffset"]
    assert "MHA-SH-001" in drawing.DIMENSION_CALLOUTS["EarHole1Z"]
    # The grip offset says what it locates: the bore axis, off the split face.
    assert "BORE AXIS" in drawing.DIMENSION_CALLOUTS["GripOffset"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "GRIP_OFFSET_BAND" in source and "EAR_STATION_BAND" in source


def test_sheet_has_no_gdt_notes_or_drawing_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert "set_dimension_precision" not in source
    assert '"Manufacturing Notes"' not in source
    assert "add_native_hole_callout(" in source
    assert "assert_imported_precision(" in source


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source
    assert "for view in (top, face, iso):" in source


def test_split_face_view_projects_beside_the_plan() -> None:
    # Third-angle right-side projection of the plan: level with it, to its
    # right (the split face is the plan's right edge), the 48 running up both.
    assert drawing.FACE_CENTER[1] == drawing.TOP_CENTER[1]
    assert drawing.FACE_CENTER[0] > drawing.TOP_CENTER[0]
    ear_1 = drawing._face_xy(0.0, spec.EAR_HOLE_Z)
    assert ear_1[0] == drawing.FACE_CENTER[0]
    assert ear_1[1] < drawing.FACE_CENTER[1]  # +Z runs down, as in the plan
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"


def test_part_stamps_make_critical_drawing_properties() -> None:
    row = _config.parts("sh-column-clamp-back")
    assert row["material_specification"]
    assert "masked" in row["finish"] and "oiled" in row["finish"]
    # One clamp pair per front column on the paper-drive bar, one at the
    # magnifier wheel bar.
    assert int(row["quantity"]) == 3

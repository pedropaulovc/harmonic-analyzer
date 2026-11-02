"""Offline contracts for the column-clamp-back drawing (MHA-SH-02)."""

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
from _paths import CAD_ROOT
from machinist_exceptions import load_exceptions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from fr_tube_frame_spec import OUTER_DIA


def _in(value_in: float) -> float:
    """Millimetres of a printed inch value."""
    return value_in * 25.4


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
        | set(drawing.LINEAR_REFERENCE_DIMENSIONS)
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
    assert spec.DRAWING_PRECISION[feature] == {name: 3}
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
    assert part.DEPTH == geom.DEPTH == 15.494  # .610
    assert part.GRIP_OFFSET == geom.GRIP_OFFSET == 0.508  # .020
    assert geom.BLOCK_DEPTH == geom.DEPTH - geom.GRIP_OFFSET
    assert part.HOLE_SPEC is geom.HOLE_SPEC
    assert (geom.HOLE_SPEC.kind, geom.HOLE_SPEC.size) == ("tapped", "#8-32")
    assert geom.TAP_DRILL_DIA == blind_cut_dia_mm(geom.HOLE_SPEC)


def test_fit_budget_closes_at_the_printed_limits() -> None:
    assert fit.COLUMN_DIA == OUTER_DIA == 25.4
    low, high = fit.BORE_DIAMETRAL_CLEARANCE
    assert low < spec.COLUMN_BORE - OUTER_DIA < high
    # Faces stay apart with both bores at their loosest and the offset least:
    # (.020 - .004) - .012 = .004.
    assert math.isclose(fit.GRIP_GAP_MIN, _in(0.004))
    assert fit.GRIP_GAP_MIN > 0.0
    # The ear stations' worst mismatch alone never binds the screw.
    assert fit.EAR_STATION_MISMATCH_MAX < fit.SCREW_FLOAT
    # So does the ears' worst mismatch with height and station together: the
    # height takes the stations' band, so each tap's zone is the same both ways.
    assert fit.EAR_HEIGHT_BAND == fit.EAR_STATION_BAND
    assert math.isclose(fit.EAR_HEIGHT_MISMATCH_MAX, 2.0 * fit.EAR_HEIGHT_BAND)
    assert math.isclose(
        fit.EAR_SCREW_MISMATCH_MAX,
        math.hypot(fit.EAR_STATION_MISMATCH_MAX, fit.EAR_HEIGHT_MISMATCH_MAX),
    )
    assert fit.EAR_SCREW_MISMATCH_MAX < fit.SCREW_FLOAT


def test_column_limit_is_the_a513_dom_table_row() -> None:
    # The cited table applies only while MHA-FR-03 is bought as A513 Type 5
    # (DOM) 1 x .120 in tube: OD 0.500-1.699 in carries +0.005 / -0.000 in.
    tube = _config.parts("fr-tube-frame")
    assert tube["number"] == "MHA-FR-03"
    assert tube["material_specification"].startswith("ASTM A513 T5 ")
    assert "DOM 1x.120in" in tube["material_specification"]
    assert math.isclose(fit.COLUMN_OD_MAX, 25.4 + 0.127)
    assert math.isclose(fit.BORE_RADIUS_MAX, (25.527 + 0.3048) / 2.0)


def test_walls_at_the_largest_column_and_drill_wander() -> None:
    # Independent oracle from inch literals: the largest A513 column (1.005)
    # at the loosest .012 clearance, the printed .XX limits and the +/-.004
    # bands, and 0.3 deg of drill wander over the through tap's deepest
    # printed length (.59 + .01).
    r_bore = _in(1.005 + 0.012) / 2.0
    wander = _in(0.600) * math.tan(math.radians(0.3))
    reach = 4.166 / 2.0 + wander
    back_wall = _in(0.020 - 0.004) + _in(0.590 - 0.010) - r_bore
    assert math.isclose(spec.WALLS_WORST["back wall"], back_wall)  # 2.2225 (.0875)
    assert math.isclose(
        spec.WALLS_WORST["ear to bore"], _in(0.689 - 0.004) - reach - r_bore
    )  # 2.320 (.0914), the least ear wall
    # The .XX width (1.89 +/-.01) about the reference .945 centre, the side
    # faces each the .XX band off it.
    assert math.isclose(
        spec.WALLS_WORST["ear to far side"],
        _in(1.880) - _in(0.955) - _in(0.693) - reach,
    )
    # Every wall meets the .080 target, so the back wall's old shortfall
    # (sh-column-clamp-back RV-01) is retired and nothing is declared.
    assert min(spec.WALLS_WORST.values()) >= _in(0.080)
    assert not load_exceptions(CAD_ROOT / "config", "sh_column_clamp_back", "part")


def test_screw_line_shortfall_is_the_owner_ruled_one() -> None:
    # Independent oracle from inch literals: the printed Ø.196 front hole at
    # its least on the #8 screw major 4.1656, against the printed
    # station/height mismatch hypot(.008, .008) plus 0.3 deg of wander down
    # both through holes (front .685 + .005, back .590 + .005), in any
    # direction.
    float_ = (_in(0.196) - 4.1656) / 2.0  # 0.4064 (.016)
    drift = math.tan(math.radians(0.3))
    mismatch = math.hypot(_in(0.008), _in(0.008))
    demand = mismatch + (_in(0.690) + _in(0.600)) * drift  # 0.4589
    assert math.isclose(fit.SCREW_FLOAT, float_)
    assert math.isclose(fit.SCREW_LINE_DEMAND, demand)
    assert math.isclose(fit.SCREW_LINE_SHORTFALL, demand - float_)  # 0.0525
    # Owner-ruled (sh-column-clamp-front RV-02) as up to 0.053 mm; the +/-.004
    # ear bands keep it inside. The printed bands alone still leave the screw
    # float.
    assert fit.SCREW_LINE_SHORTFALL_RULED == 0.053
    assert round(demand - float_, 3) == 0.053
    assert mismatch < float_


def test_tight_bands_name_their_mate() -> None:
    bore = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "DIAMETRAL" in bore and "MHA-FR-03" in bore
    low, high = spec.BORE_DIAMETRAL_CLEARANCE
    assert math.isclose(low, _in(0.004)) and math.isclose(high, _in(0.012))
    assert "MHA-SH-01" in drawing.DIMENSION_CALLOUTS["GripOffset"]
    assert "MHA-SH-01" in drawing.DIMENSION_CALLOUTS["EarHole1Z"]
    assert "MHA-SH-01" in drawing.DIMENSION_CALLOUTS["EarHoleHeight"]
    # The grip offset says what it locates: the bore axis, off the split face.
    assert "BORE AXIS" in drawing.DIMENSION_CALLOUTS["GripOffset"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "GRIP_OFFSET_BAND" in source and "EAR_STATION_BAND" in source
    assert "EAR_HEIGHT_BAND" in source
    assert spec.EAR_HEIGHT_BAND is fit.EAR_HEIGHT_BAND


def test_sheet_has_no_gdt_notes_or_drawing_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert "set_dimension_precision" not in source
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


def test_ear_height_text_stands_outside_its_witnesses() -> None:
    # Farm round 20261015T1724 (audit + machinist review, rule 14): the 16 mm
    # between the ear-height witnesses cannot hold its callout block, so the
    # block stands past the bottom-face witness (shared with the height),
    # away from ear 1's witness and centreline, clear by at least 3 mm.
    # 3.5 mm Century Gothic measured ~2.65 mm per character on that sheet.
    bottom_x = drawing._face_xy(-spec.ARC_HEIGHT / 2.0, spec.EAR_HOLE_Z)[0]
    ear_x = drawing._face_xy(0.0, spec.EAR_HOLE_Z)[0]
    text_x = drawing.FACE_KEEP["EarHoleHeight"][0]
    outward = math.copysign(1.0, bottom_x - ear_x)
    lines = ["2X .315 ±.004", *drawing.DIMENSION_CALLOUTS["EarHoleHeight"].split("\n")]
    half_block = max(len(line) for line in lines) * 0.00265 / 2.0
    assert outward * (text_x - bottom_x) >= half_block + 0.003


def test_part_stamps_make_critical_drawing_properties() -> None:
    row = _config.parts("sh-column-clamp-back")
    assert row["material_specification"]
    assert "masked" in row["finish"] and "oiled" in row["finish"]
    # One clamp pair per front column on the paper-drive bar, one at the
    # magnifier wheel bar.
    assert int(row["quantity"]) == 3

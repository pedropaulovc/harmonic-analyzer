"""Offline contracts for the column-clamp-front drawing."""

from __future__ import annotations

import math
from pathlib import Path

import sh_column_clamp_front_spec as spec
import sh_column_clamp_fit as fit
import draw_sh_column_clamp_front as drawing
import build_sh_column_clamp_front as part
import _clamp_arc
import _column_clamp_drawing
import _drawing_hidden_sketches
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from machinist_exceptions import load_exceptions, render_anchor
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
    kept = set(drawing.TOP_KEEP) | set(drawing.FACE_KEEP)
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    annotated = (
        set(drawing.DIMENSION_CALLOUTS)
        | set(drawing.DIMENSION_PREFIXES)
        | set(drawing.REFERENCE_DIMENSIONS)
    )
    assert annotated <= kept


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
    assert spec.DRAWING_PRECISION[feature] == {name: 1}
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


def test_split_face_helpers_are_shared_with_the_back_arc() -> None:
    assert (
        drawing.set_dimension_prefixes is _column_clamp_drawing.set_dimension_prefixes
    )
    assert (
        drawing.add_bore_axis_centerline
        is _column_clamp_drawing.add_bore_axis_centerline
    )
    assert not hasattr(drawing, "_set_dimension_prefixes")
    assert not hasattr(drawing, "_add_bore_axis_centerline")


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
    assert "for view in (top, face, iso):" in source
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_split_face_view_projects_beside_the_plan() -> None:
    # Third-angle left-side projection of the plan: level with it, to its
    # left (the split face is the plan's left edge), the 48 running up both.
    assert drawing.FACE_CENTER[1] == drawing.TOP_CENTER[1]
    assert drawing.FACE_CENTER[0] < drawing.TOP_CENTER[0]
    ear_1 = drawing._face_xy(0.0, spec.EAR_HOLE_Z)
    assert ear_1[0] == drawing.FACE_CENTER[0]
    assert ear_1[1] < drawing.FACE_CENTER[1]  # +Z runs down, as in the plan


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
    lines = ["2X 8.0 ±0.1", *drawing.DIMENSION_CALLOUTS["EarHoleHeight"].split("\n")]
    half_block = max(len(line) for line in lines) * 0.00265 / 2.0
    assert outward * (text_x - bottom_x) >= half_block + 0.003


def test_bore_prints_the_grip_budget_on_the_column() -> None:
    # #970: the bore is matched to the purchased column at the clearance the
    # pair's grip budget allows (sh_column_clamp_fit), not "bored as a pair".
    bore = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert "DIAMETRAL" in bore and "MHA-FR-003" in bore
    assert f"{spec.BORE_DIAMETRAL_CLEARANCE[1]:.2f}" in bore
    assert spec.BORE_DIAMETRAL_CLEARANCE[1] <= 0.30
    assert "MHA-SH-002" in drawing.DIMENSION_CALLOUTS["EarHole1Z"]
    assert "MHA-SH-002" in drawing.DIMENSION_CALLOUTS["EarHoleHeight"]
    # The two-place depth says what it sets; the bore says where its axis is.
    assert spec.DRAWING_PRECISION["BlockProfile"]["Depth"] == 2
    assert "MHA-SH-002" in drawing.DIMENSION_CALLOUTS["Depth"]
    assert "AXIS ON SPLIT FACE" in bore


def test_walls_at_the_largest_column_and_drill_wander() -> None:
    # Independent oracle from literals: the largest A513 DOM column (25.4 +
    # 0.127) at the loosest 0.30 clearance, the printed Ø4.98 hole at its
    # DRILLED HOLES +0.10, the printed .XX/.X limits, and 0.3 deg of drill
    # wander over the through hole's deepest printed length (17.4 + 0.51; the
    # arc gave up 0.5 to the rearward-grown support bar).
    r_bore = (25.527 + 0.30) / 2.0
    reach = (4.98 + 0.10) / 2.0 + 17.91 * math.tan(math.radians(0.3))
    web = 17.4 - reach - r_bore
    assert math.isclose(spec.WALLS_WORST["ear to bore"], web)  # 1.853
    assert math.isclose(spec.WALLS_WORST["bar-face wall"], 16.89 - r_bore)
    assert math.isclose(spec.WALLS_WORST["ear to far side"], 47.2 - 24.8 - 17.6 - reach)
    assert min(spec.WALLS_WORST.values()) >= 1.5
    # The web reaches the 2.0 target only on a column under its own Ø25.4
    # nominal, so no column acceptance can lift it: the one owner-ruled
    # shortfall (sh-column-clamp-front RV-01), and the part's least wall.
    column_at_target = 2.0 * (17.4 - reach - 2.0) - 0.30
    assert column_at_target < 25.4
    short = {name for name, wall in spec.WALLS_WORST.items() if wall < 2.0}
    assert short == {"ear to bore"}
    assert min(spec.WALLS_WORST.values()) == spec.WALLS_WORST["ear to bore"]


def test_owner_ruled_shortfalls_are_declared_and_stated() -> None:
    # drawing-simplicity-policy.md "Named exceptions": each stated shortfall
    # matches a kind-minor declaration beside the draw script, anchored on
    # the printed note, at the value the spec computes.
    entries = {entry.id: entry for entry in load_exceptions("sh_column_clamp_front")}
    assert set(entries) == {"RV-01", "RV-02"}
    for entry in entries.values():
        assert entry.kind.value == "minor"
        assert entry.reason.endswith("(owner-ruled shortfall)")
    for id_, note in (("RV-01", spec.EAR_WALL_NOTE), ("RV-02", spec.SCREW_LINE_NOTE)):
        (anchor,) = entries[id_].anchors
        assert render_anchor(anchor, "sh_column_clamp_front") == f'note "{note}"'
    # The printed values, from the computed worst cases at the sheet's two
    # places, rounded never in the part's favour: the least wall down, the
    # screw line's excess up.
    assert spec.EAR_WALL_NOTE == "MIN EAR WALL 1.85"
    assert 1.85 <= spec.WALLS_WORST["ear to bore"] < 1.86
    assert spec.SCREW_LINE_NOTE == (
        "EAR TO MHA-SH-002 TAP OFFSET UP TO 0.06 OVER #8 SCREW CLEARANCE"
    )
    assert 0.05 < fit.SCREW_LINE_SHORTFALL <= 0.06
    assert spec.DRAWING_NOTES.split("\n") == [
        f"1. {spec.EAR_WALL_NOTE}.",
        f"2. {spec.SCREW_LINE_NOTE}.",
    ]
    assert part.DRAWING_NOTES is spec.DRAWING_NOTES


def test_shortfall_notes_stand_in_the_open_lower_left_field() -> None:
    # 3.5 mm Century Gothic: ~2.65 mm per character, ~5.5 mm per line.  The
    # block stays left of the title block (x 0.216, up to y 0.070), above the
    # border (0.012) and under every kept dimension by at least 10 mm.
    x, y = drawing.NOTES_XY
    lines = spec.DRAWING_NOTES.split("\n")
    assert x + max(len(line) for line in lines) * 0.00265 < 0.216 - 0.003
    assert y - len(lines) * 0.0055 > 0.012 + 0.003
    kept = (*drawing.TOP_KEEP.values(), *drawing.FACE_KEEP.values())
    assert y < min(text_y for _, text_y in kept) - 0.010
    assert drawing.HOLE_CALLOUT_XY[1] > y and drawing.ISO_NOTE_XY[0] > 0.216


def test_sheet_has_no_gdt_notes_or_drawing_precision() -> None:
    # Clamps are not on the drawing-simplicity GD&T allowlist; the ear holes
    # locate by +/- from the bore axis, authored on the part.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert "set_basic_dimension(" not in source
    assert "set_dimension_precision" not in source
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert "add_native_hole_callout(" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "EAR_STATION_BAND" in source
    assert "EAR_HEIGHT_BAND" in source
    import _config

    row = _config.parts("sh-column-clamp-front")
    assert row["material_specification"]
    assert "oiled" in row["finish"]
    # One clamp pair per front column: two on the paper-drive platen bar plus
    # one at the magnifier wheel bar.
    assert int(row["quantity"]) == 3

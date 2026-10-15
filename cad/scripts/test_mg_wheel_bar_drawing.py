"""Offline contracts for the wheel-bar drawing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import build_mg_wheel_bar as part
import draw_mg_wheel_bar as drawing
import mg_wheel_bar_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-wheel-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-wheel-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-wheel-bar_drawing.png")
    assert DRAWINGS_BY_NAME["mg_wheel_bar"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_wheel_bar_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_wheel_bar_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked
    assert (drawing.BAR_LENGTH, drawing.BAR_SIDE) == (
        mg_wheel_bar_spec.BAR_LENGTH,
        mg_wheel_bar_spec.BAR_SIDE,
    )


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The bar depth + clamp stations the assembly imports live in the drawing-
    # FREE geom module, so a print-note edit cannot enter the assembly recipe.
    import mg_wheel_bar_geom as geom

    assert (geom.BAR_SIDE, geom.BAR_DEPTH, geom.BAR_LENGTH) == (10.0, 9.5, 234.0)
    assert geom.CLAMP_HOLE_X == (70.5, 105.5)
    assembly = (
        Path(part.__file__)
        .with_name("build_mg_magnifier_assembly.py")
        .read_text(encoding="utf-8")
    )
    assert "from mg_wheel_bar_geom import" in assembly
    assert "from build_mg_wheel_bar import" not in assembly


def test_hanger_clearance_preserves_a_tolerance_safe_end_ligament() -> None:
    import mg_wheel_bar_geom as geom

    assert part.PEN_HANGER_HOLE_SPEC is geom.PEN_HANGER_HOLE_SPEC
    assert part.CLAMP_HOLE_SPEC is geom.CLAMP_HOLE_SPEC
    hole_dia = part.blind_cut_dia_mm(geom.PEN_HANGER_HOLE_SPEC)
    assert hole_dia == pytest.approx(4.572)
    assert part.PEN_HANGER_END_WALL == pytest.approx(2.714)
    minimum_wall = (
        part.PEN_HANGER_END_WALL
        - geom.PEN_HANGER_STATION_TOL
        - part.PEN_HANGER_HOLE_DIA_TOL / 2.0
    )
    assert minimum_wall == pytest.approx(2.154)
    assert minimum_wall >= geom.PEN_HANGER_MIN_END_WALL

    # The former station passed a >0 guard with only 0.214 mm of material.
    with pytest.raises(AssertionError):
        geom.require_hanger_end_wall(-114.5, hole_dia, part.PEN_HANGER_HOLE_DIA_TOL)
    # A nominal wall above 2 mm must still fail if tolerances consume the reserve.
    with pytest.raises(AssertionError):
        geom.require_hanger_end_wall(-112.664, hole_dia, part.PEN_HANGER_HOLE_DIA_TOL)


def test_screw_hole_stations_are_model_dimensions_from_the_left_end() -> None:
    import mg_wheel_bar_geom as geom

    row = mg_wheel_bar_spec.DRAWING_DIMENSIONS["BoreRowReference"]
    assert row == {"BoreRowHeight", "HangerStation", "ClampStation1", "ClampStation2"}
    assert row <= set(drawing.FRONT_KEEP)
    left_end = -geom.BAR_LENGTH / 2.0
    assert geom.HANGER_STATION == pytest.approx(geom.SCREW_HOLE_X - left_end) == 5.0
    assert geom.CLAMP_STATIONS == pytest.approx(
        tuple(x - left_end for x in geom.CLAMP_HOLE_X)
    )
    assert geom.CLAMP_STATIONS == (187.5, 222.5)


def test_station_rows_stack_shortest_nearest_under_the_bar() -> None:
    import mg_wheel_bar_geom as geom

    spans = {
        "HangerStation": geom.HANGER_STATION,
        "AxleBoreStation": mg_wheel_bar_spec.AXLE_BORE_STATION,
        "ClampStation1": geom.CLAMP_STATIONS[0],
        "ClampStation2": geom.CLAMP_STATIONS[1],
        "Length": geom.BAR_LENGTH,
    }
    rows = sorted(spans, key=spans.get)
    heights = [drawing.FRONT_KEEP[name][1] for name in rows]
    bar_bottom = drawing.FRONT_CENTER[1] - geom.BAR_SIDE / 2000.0
    assert all(y < bar_bottom for y in heights)
    assert all(a - b >= 0.008 - 1e-9 for a, b in zip(heights, heights[1:]))
    # The callouts' leaders come down from above, clear of every row.
    for _x, y in (drawing.HANGER_CALLOUT_XY, drawing.CLAMP_CALLOUT_XY):
        assert y > drawing.FRONT_CENTER[1] + geom.BAR_SIDE / 2000.0
    # A long row's text stays between its extension lines.
    for name in ("AxleBoreStation", "ClampStation1", "ClampStation2", "Length"):
        assert drawing.LEFT_END < drawing.FRONT_KEEP[name][0]
        assert drawing.FRONT_KEEP[name][0] < drawing.LEFT_END + spans[name] / 1000.0
    # Off the right end the row height nests inside the bar height (baseline
    # on the bottom face): its line nearer the bar, its text below, the
    # height's above, and the row's text off the length's extension line.
    row_x, row_y = drawing.FRONT_KEEP["BoreRowHeight"]
    side_x, side_y = drawing.FRONT_KEEP["Side"]
    assert drawing.RIGHT_END + 0.016 < row_x < side_x
    assert row_y < bar_bottom < bar_bottom + geom.BAR_SIDE / 1000.0 < side_y


def test_notes_carry_no_dimensions() -> None:
    notes = mg_wheel_bar_spec.DRAWING_NOTES
    assert re.findall(r"\d+\.\d+", notes) == []
    for token in ("Ø", "+/-", "±", "MID-HEIGHT", "STATION"):
        assert token not in notes


def test_callouts_state_the_needs_of_the_tight_bands() -> None:
    assert drawing.DIMENSION_CALLOUTS["HangerStation"] == "FOR 2.0 END WALL"
    assert drawing.DIMENSION_CALLOUTS["BoreRowHeight"] == "ALL BORES\nFOR 2.0 WALLS"
    assert drawing.DIMENSION_CALLOUTS["Side"] == "CLEARS WHEEL TIE\nFOR 2.0 BORE WALLS"
    for callout in drawing.DIMENSION_CALLOUTS.values():
        assert len(callout.splitlines()) <= 4


def test_every_bore_keeps_a_two_mm_wall_from_the_bottom_face_row() -> None:
    import mg_wheel_bar_geom as geom

    assert geom.AXLE_BORE_X == -56.0 == geom.WHEEL_X - geom.WHEEL_BAR_X0
    assert mg_wheel_bar_spec.AXLE_BORE_STATION == 61.0
    assert (
        mg_wheel_bar_spec.AXLE_BORE_STATION == geom.AXLE_BORE_X + geom.BAR_LENGTH / 2.0
    )
    side_min = geom.BAR_SIDE + geom.BAR_SIDE_BAND[1]
    height, tol = geom.BORE_ROW_HEIGHT, geom.BORE_ROW_HEIGHT_TOL
    assert height == geom.BAR_SIDE / 2.0
    near_face = min(height, side_min - height) - tol
    assert near_face == pytest.approx(geom.BORE_ROW_NEAR_FACE) == pytest.approx(4.6)
    radii = {
        "axle bore": (geom.AXLE_BORE_DIA + geom.AXLE_BORE_BAND[0]) / 2.0,
        "pen-hanger hole": (geom.PEN_HANGER_HOLE_DIA + geom.DRILLED_HOLE_PLUS) / 2.0,
        "clamp holes": (geom.CLAMP_HOLE_DIA + geom.DRILLED_HOLE_PLUS) / 2.0,
    }
    walls = {bore: near_face - radius for bore, radius in radii.items()}
    assert walls == pytest.approx(geom.BORE_ROW_WALLS)
    assert walls["clamp holes"] == pytest.approx(2.061)
    assert min(walls.values()) >= 2.0
    # The former -0.5 height band would leave the clamp holes' top wall short.
    old_top_wall = geom.BAR_SIDE - 0.5 - height - tol - radii["clamp holes"]
    assert old_top_wall == pytest.approx(1.861)


def test_axle_bore_is_a_marked_reamed_cut() -> None:
    assert mg_wheel_bar_spec.DRAWING_DIMENSIONS["AxleBoreProfile"] == {
        "AxleBoreDia",
        "AxleBoreStation",
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        "Length": 1,
        "Side": 1,
        "AxleBoreDia": 3,
        "AxleBoreStation": 2,
        "BarDepth": 2,
        "BoreRowHeight": 2,
        "HangerStation": 2,
        "ClampStation1": 1,
        "ClampStation2": 1,
    }
    assert drawing.DIMENSION_CALLOUTS["AxleBoreDia"] == (
        "REAM THRU\nPRESS FIT MG-WHEEL-AXLE\n0.010-0.030 INTERFERENCE"
    )
    assert drawing.DIMENSION_CALLOUTS["BarDepth"].endswith("0.35 PROUD TO 1.55 SUNK")
    assert model_toleranced_dimensions(part) == {
        ("BarProfile", "Side"): "*deviations(BAR_SIDE_BAND)",
        ("Bar", "BarDepth"): "*deviations(BAR_DEPTH_BAND)",
        ("AxleBoreProfile", "AxleBoreDia"): "*deviations(AXLE_BORE_BAND)",
        ("BoreRowReference", "BoreRowHeight"): "BORE_ROW_HEIGHT_TOL",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "AxleBoreProfile")' in source
    assert 'name_last_feature(adapter, "AxleBore")' in source
    assert "create_cut_extrude(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert 'name_dimensions(adapter, "Bar", ["BarDepth"])' in source
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)" in sheet


def test_hole_callouts_pick_both_screw_hole_features(monkeypatch) -> None:
    import mg_wheel_bar_geom as geom

    class _Edges:
        def __init__(self) -> None:
            self.picks = []

        def circle_at(self, center, radius, *, axis, label, radius_tol_mm):
            self.picks.append((center, radius, axis))

            class _Hit:
                edge = (center, radius)

            return _Hit()

    edges = _Edges()
    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, *, label: edges)
    rims = drawing._hole_rims(object())
    face = geom.BAR_DEPTH / 2.0
    assert edges.picks == [
        (
            (geom.SCREW_HOLE_X, 0.0, face),
            geom.PEN_HANGER_HOLE_DIA / 2.0,
            (0.0, 0.0, 1.0),
        ),
        ((geom.CLAMP_HOLE_X[0], 0.0, face), geom.CLAMP_HOLE_DIA / 2.0, (0.0, 0.0, 1.0)),
    ]
    assert len(rims) == 2


def test_notes_stay_short() -> None:
    lines = mg_wheel_bar_spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert all(len(line) <= 80 for line in lines)
    assert "DATUM" not in mg_wheel_bar_spec.DRAWING_NOTES


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-wheel-bar")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

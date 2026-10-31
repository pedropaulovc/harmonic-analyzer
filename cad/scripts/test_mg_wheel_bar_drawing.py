"""Offline contracts for the wheel-bar drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

from _column_clamp_interface import BAR_DEPTH
import build_mg_wheel_bar as part
import draw_mg_wheel_bar as drawing
import mg_wheel_bar_callouts as callouts
import mg_wheel_bar_spec
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _title_block_units import render_number

IN = 25.4


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

    assert (geom.BAR_SIDE, geom.BAR_LENGTH) == pytest.approx((0.43 * IN, 234.0))
    # The row stays 5.0 under the top face the strap and the top assembly
    # read; the extra height lies below it.
    assert geom.BAR_TOP_ABOVE_ROW == 5.0
    assert geom.BORE_ROW_HEIGHT == geom.BAR_SIDE - geom.BAR_TOP_ABOVE_ROW
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
    # The station prints .20 (+/-.01) for its 5.0: its least is 4.826.
    assert minimum_wall == pytest.approx(2.714 - (5.0 - 0.19 * IN) - 0.004 * IN / 2.0)
    assert minimum_wall >= geom.PEN_HANGER_MIN_END_WALL

    # The former station passed a >0 guard with only 0.214 mm of material.
    with pytest.raises(AssertionError):
        geom.require_hanger_end_wall(-114.5, hole_dia, part.PEN_HANGER_HOLE_DIA_TOL)
    # A nominal wall above .080 must still fail if tolerances consume the reserve.
    with pytest.raises(AssertionError):
        geom.require_hanger_end_wall(-112.664, hole_dia, part.PEN_HANGER_HOLE_DIA_TOL)


def test_screw_hole_stations_are_model_dimensions_from_the_left_end() -> None:
    import mg_wheel_bar_geom as geom

    row = mg_wheel_bar_spec.DRAWING_DIMENSIONS["BoreRowReference"]
    assert row == {
        "BoreRowFromTop",
        "ClampRowFromTop",
        "HangerStation",
        "ClampStation1",
        "ClampStation2",
    }
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
    bar_top = bar_bottom + geom.BAR_SIDE / 1000.0
    assert all(y < bar_bottom for y in heights)
    assert all(a - b >= 0.008 - 1e-9 for a, b in zip(heights, heights[1:]))
    # The callouts' leaders come down from above, clear of every row.
    for _x, y in (drawing.HANGER_CALLOUT_XY, drawing.CLAMP_CALLOUT_XY):
        assert y > bar_top
    # A long row's text stays between its extension lines.
    for name in ("AxleBoreStation", "ClampStation1", "ClampStation2", "Length"):
        assert drawing.LEFT_END < drawing.FRONT_KEEP[name][0]
        assert drawing.FRONT_KEEP[name][0] < drawing.LEFT_END + spans[name] / 1000.0
    # Off the right end the clamp row's drop nests inside the bar height
    # (baseline on the top face): its line nearer the bar, its text above the
    # bar, the height's below.
    row_x, row_y = drawing.FRONT_KEEP["ClampRowFromTop"]
    side_x, side_y = drawing.FRONT_KEEP["Side"]
    assert drawing.RIGHT_END + 0.016 < row_x < side_x
    assert side_y < bar_bottom < bar_top < row_y
    # The hanger and axle row's drop stands off the left end, above the top
    # face, its text left of the bar and inside the frame.
    left_x, left_y = drawing.FRONT_KEEP["BoreRowFromTop"]
    assert 0.020 < left_x < drawing.LEFT_END - 0.012
    assert bar_top < left_y < drawing.HANGER_CALLOUT_XY[1] - 0.015


def test_the_sheet_carries_no_general_notes() -> None:
    # Every hole callout says THRU; the holes' purposes were only polish.
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
    assert not hasattr(mg_wheel_bar_spec, "DRAWING_NOTES")


def test_part_authored_callouts_name_each_band_s_mate() -> None:
    import _config
    from mg_wheel_axle_spec import BACK_END_SUNK_MAX, BACK_END_SUNK_MIN
    from mg_wheel_group import BAR_PRESS

    assert callouts.authored_by_name() == {
        "AxleBoreDia": {callouts.CALLOUT_BELOW: callouts.AXLE_BORE_CALLOUT},
        "BarDepth": {callouts.CALLOUT_BELOW: callouts.BAR_DEPTH_CALLOUT},
        "ClampRowFromTop": {callouts.CALLOUT_BELOW: callouts.CLAMP_ROW_CALLOUT},
    }
    # The literals keep the wheel group and the axle out of the part recipe;
    # the mate is named by its number (rule 4).
    axle = _config.parts("mg-wheel-axle")["number"]
    press = "-".join(render_number(value / IN, "in", 4) for value in BAR_PRESS)
    assert callouts.AXLE_BORE_CALLOUT == (
        f"REAM THRU\nPRESS FIT {axle} AXLE\n"
        f"{press} DIAMETRAL\nINTERFERENCE\n"
        "WALL .074 MIN"
    )
    sunk = [
        render_number(v / IN, "in", 3) for v in (BACK_END_SUNK_MIN, BACK_END_SUNK_MAX)
    ]
    assert callouts.BAR_DEPTH_CALLOUT == (
        f"{axle} AXLE BACK END\n{sunk[0]} TO {sunk[1]} SUNK"
    )
    assert callouts.CLAMP_ROW_CALLOUT.startswith("2X CLAMP HOLES")
    assert "MHA-SH-02" in callouts.CLAMP_ROW_CALLOUT
    assert "DIAMETRAL INTERFERENCE" in callouts.AXLE_BORE_CALLOUT.replace("\n", " ")
    assert callouts.CLAMP_HOLE_CALLOUT == "LOCATE TO MHA-SH-02 TAPS\nWALL .068 MIN"
    assert callouts.HANGER_HOLE_CALLOUT == "WALL .076 MIN"
    texts = [*callouts.authored_by_name().values()]
    for lanes in texts:
        for text in lanes.values():
            assert len(text.splitlines()) <= 5
    # The part writes them; the sheet only reads them back (#1942).
    sheet = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts" not in sheet
    assert "_assert_part_authored_text(adapter, annotations)" in sheet
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_dimension_callouts(adapter)" in source


def test_clamp_position_band_is_the_mha_sh_02_tap_stack() -> None:
    import math

    import mg_wheel_bar_geom as geom
    from sh_column_clamp_fit import EAR_HEIGHT_BAND, EAR_STATION_BAND
    from sh_vn_clamp_screw_spec import SHANK_DIA

    band = mg_wheel_bar_spec.CLAMP_POSITION_BAND
    hole_float = geom.CLAMP_HOLE_DIA - SHANK_DIA
    assert hole_float == pytest.approx(0.812, abs=1e-3)
    tap_zone = 2.0 * math.hypot(EAR_STATION_BAND, EAR_HEIGHT_BAND)

    def bar_zone(b: float) -> float:
        return 2.0 * math.hypot(b, b)

    # The widest .XXX band whose zone, with the taps', stays inside the float.
    assert bar_zone(band) + tap_zone <= hole_float
    assert bar_zone(band + 0.001 * IN) + tap_zone > hole_float
    assert mg_wheel_bar_spec.CLAMP_POSITION_PLACES == 3
    assert round(band / IN, 3) * IN == pytest.approx(band)
    # The row and stations keep millimetre nominals: the band holds at the
    # limits their rounded values print.
    from _printed_tolerance import printed_deviations

    worst = max(
        abs(deviation)
        for nominal in (geom.BAR_TOP_ABOVE_ROW, *geom.CLAMP_STATIONS)
        for deviation in printed_deviations(nominal, 3, (-band, band), unit="in")
    )
    assert bar_zone(worst) + tap_zone <= hole_float


def test_every_wall_is_stated_at_the_full_worst_case() -> None:
    import math

    import mg_wheel_bar_geom as geom

    assert geom.AXLE_BORE_X == -56.0 == geom.WHEEL_X - geom.WHEEL_BAR_X0
    assert mg_wheel_bar_spec.AXLE_BORE_STATION == 61.0
    assert (
        mg_wheel_bar_spec.AXLE_BORE_STATION == geom.AXLE_BORE_X + geom.BAR_LENGTH / 2.0
    )
    # The height prints .43 (+/-.01). The hanger hole and the axle bore sit at
    # the title block's .XX from the top face: their 5.0 prints .20, so the
    # row lies 4.826-5.334; the clamp pair's prints .197 at the taps' +/-.007.
    # Each wall also loses 0.3 deg run-off over the deepest bar (.374 + .004;
    # the holes are drilled on the mill into faces cut earlier) and an R.010
    # break on each of its two exposed edges.
    side_min = (0.43 - 0.01) * IN
    row = ((0.20 - 0.01) * IN, (0.20 + 0.01) * IN)
    clamp_row = ((0.197 - 0.007) * IN, (0.197 + 0.007) * IN)
    assert mg_wheel_bar_spec.BORE_ROW_FROM_TOP == geom.BAR_TOP_ABOVE_ROW
    runoff = (0.374 + 0.004) * IN * math.tan(math.radians(0.3))
    losses = runoff + 2 * 0.010 * IN
    bores = {
        "axle bore": ((0.1865 + 0.0005) * IN / 2.0, row),
        "hanger hole": ((geom.PEN_HANGER_HOLE_DIA + 0.004 * IN) / 2.0, row),
        "clamp holes": ((geom.CLAMP_HOLE_DIA + 0.004 * IN) / 2.0, clamp_row),
    }
    walls = {
        **{f"{b} top": low - r - losses for b, (r, (low, _high)) in bores.items()},
        **{
            f"{b} bottom": side_min - high - r - losses
            for b, (r, (_low, high)) in bores.items()
        },
        "hanger hole end": (0.20 - 0.01) * IN - bores["hanger hole"][0] - losses,
    }
    assert walls == pytest.approx(mg_wheel_bar_spec.BORE_ROW_WALLS)
    # Every wall holds the .060 floor; the bottom walls meet the .080 target.
    # The top walls and the hanger end wall stay under it: owner ruling
    # 2026-10-26 (#1532) accepts those four as minors.
    assert all(wall >= 0.060 * IN for wall in walls.values())
    minors = {name for name, wall in walls.items() if wall < 0.080 * IN}
    assert minors == {
        "axle bore top",
        "hanger hole top",
        "clamp holes top",
        "hanger hole end",
    }
    assert set(mg_wheel_bar_spec.MINOR_WALLS) == minors
    assert mg_wheel_bar_spec.WALL_CALLOUT_MIN_IN == {
        "axle bore": 0.074,
        "hanger hole": 0.076,
        "clamp holes": 0.068,
    }
    # The photographed 10 mm bar would leave the walls under the bores under
    # the floor: the height grew rather than a band tightening.
    for b, (r, (_low, high)) in bores.items():
        assert 10.0 - 0.01 * IN - high - r - losses < 0.060 * IN, b


def test_every_wall_is_an_owner_declared_minor_stated_on_the_sheet() -> None:
    import math

    import _config
    from machinist_exceptions import load_exceptions

    declared = load_exceptions(_config.CONFIG_DIR, "mg_wheel_bar", "part")
    assert len(declared) == len(mg_wheel_bar_spec.MINOR_WALLS) == 4
    texts = {
        "axle bore": callouts.AXLE_BORE_CALLOUT,
        "hanger hole": callouts.HANGER_HOLE_CALLOUT,
        "clamp holes": callouts.CLAMP_HOLE_CALLOUT,
    }
    for wall, value in mg_wheel_bar_spec.MINOR_WALLS.items():
        matches = [entry for entry in declared if f"({wall} wall" in entry.where]
        assert len(matches) == 1, wall
        (entry,) = matches
        bore = next(b for b in texts if wall.startswith(b))
        row = callouts.callout_rows(texts[bore])[-1]
        assert entry.kind == "minor"
        assert row in entry.where
        floored = math.floor(value / IN * 1000 + 1e-9) / 1000
        assert render_number(floored, "in", 3) in entry.finding
        assert "rule 17" in entry.finding
        assert entry.reason.startswith("owner ruling 2026-10-26 (#1532)")


def test_axle_bore_is_a_marked_reamed_cut() -> None:
    assert mg_wheel_bar_spec.DRAWING_DIMENSIONS["AxleBoreProfile"] == {
        "AxleBoreDia",
        "AxleBoreStation",
    }
    assert drawing.DRAWING_PRECISION_BY_NAME == {
        "Length": 1,
        "Side": 2,
        "AxleBoreDia": 4,
        "AxleBoreStation": 2,
        "BarDepth": 3,
        "BoreRowFromTop": 2,
        "ClampRowFromTop": 3,
        "HangerStation": 2,
        "ClampStation1": 3,
        "ClampStation2": 3,
    }
    assert model_toleranced_dimensions(part) == {
        ("Bar", "BarDepth"): "*deviations(BAR_DEPTH_BAND)",
        ("AxleBoreProfile", "AxleBoreDia"): "*deviations(AXLE_BORE_BAND)",
        ("BoreRowReference", "ClampRowFromTop"): "CLAMP_POSITION_BAND",
        ("BoreRowReference", "ClampStation1"): "CLAMP_POSITION_BAND",
        ("BoreRowReference", "ClampStation2"): "CLAMP_POSITION_BAND",
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "AxleBoreProfile")' in source
    assert 'name_last_feature(adapter, "AxleBore")' in source
    assert "create_cut_extrude(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert 'name_dimensions(adapter, "Bar", ["BarDepth"])' in source


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
    face = BAR_DEPTH / 2.0
    assert edges.picks == [
        (
            (geom.SCREW_HOLE_X, 0.0, face),
            geom.PEN_HANGER_HOLE_DIA / 2.0,
            (0.0, 0.0, 1.0),
        ),
        ((geom.CLAMP_HOLE_X[0], 0.0, face), geom.CLAMP_HOLE_DIA / 2.0, (0.0, 0.0, 1.0)),
    ]
    assert len(rims) == 2


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-wheel-bar")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1

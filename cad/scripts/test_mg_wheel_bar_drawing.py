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

    assert (geom.BAR_SIDE, BAR_DEPTH, geom.BAR_LENGTH) == (11.0, 9.5, 234.0)
    # The row stays 5.0 under the top face the strap and the top assembly
    # read; the extra height lies below it.
    assert geom.BAR_TOP_ABOVE_ROW == 5.0
    assert geom.BORE_ROW_HEIGHT == geom.BAR_SIDE - geom.BAR_TOP_ABOVE_ROW == 6.0
    assert geom.CLAMP_HOLE_X == (70.4994, 105.5006)
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
    assert geom.CLAMP_STATIONS == pytest.approx((187.4994, 222.5006))


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
    from mg_wheel_axle_spec import BACK_END_PROUD_MAX, BACK_END_SUNK_MAX
    from mg_wheel_group import BAR_PRESS

    assert callouts.authored_by_name() == {
        "AxleBoreDia": {callouts.CALLOUT_BELOW: callouts.AXLE_BORE_CALLOUT},
        "BarDepth": {callouts.CALLOUT_BELOW: callouts.BAR_DEPTH_CALLOUT},
        "ClampRowFromTop": {callouts.CALLOUT_BELOW: callouts.CLAMP_ROW_CALLOUT},
    }
    # The literals keep the wheel group and the axle out of the part recipe;
    # the mate is named by its number (rule 4).
    axle = _config.parts("mg-wheel-axle")["number"]
    assert callouts.AXLE_BORE_CALLOUT == (
        f"REAM THRU\nPRESS FIT {axle} AXLE\n"
        f"{BAR_PRESS[0]:.3f}-{BAR_PRESS[1]:.3f} DIAMETRAL\nINTERFERENCE\n"
        "WALL 1.56 MIN"
    )
    assert callouts.BAR_DEPTH_CALLOUT == (
        f"{axle} AXLE BACK END\n"
        f"{BACK_END_PROUD_MAX:.2f} PROUD TO {BACK_END_SUNK_MAX:.2f} SUNK"
    )
    assert callouts.CLAMP_ROW_CALLOUT.startswith("2X CLAMP HOLES")
    assert "MHA-SH-02" in callouts.CLAMP_ROW_CALLOUT
    assert "DIAMETRAL INTERFERENCE" in callouts.AXLE_BORE_CALLOUT.replace("\n", " ")
    assert callouts.CLAMP_HOLE_CALLOUT == "LOCATE TO MHA-SH-02 TAPS\nWALL 1.73 MIN"
    assert callouts.HANGER_HOLE_CALLOUT == "WALL 1.60 MIN"
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

    # The widest .XX band whose zone, with the taps', stays inside the float.
    assert bar_zone(band) + tap_zone <= hole_float
    assert bar_zone(band + 0.01) + tap_zone > hole_float
    assert mg_wheel_bar_spec.CLAMP_POSITION_PLACES == 2
    assert round(band, 2) == band


def test_every_wall_is_stated_at_the_full_worst_case() -> None:
    import math

    import mg_wheel_bar_geom as geom
    from _column_clamp_interface import BAR_DEPTH

    assert geom.AXLE_BORE_X == -56.0 == geom.WHEEL_X - geom.WHEEL_BAR_X0
    assert mg_wheel_bar_spec.AXLE_BORE_STATION == 61.0
    assert (
        mg_wheel_bar_spec.AXLE_BORE_STATION == geom.AXLE_BORE_X + geom.BAR_LENGTH / 2.0
    )
    # The height has no band: the title block's .X (+/-0.8) governs it. The
    # hanger hole and the axle bore sit at the title block's .XX (+/-0.51)
    # from the top face, the clamp pair at the taps' +/-0.18. Each wall also
    # loses 0.3 deg run-off over the 9.6 deepest bar (the holes are drilled on
    # the mill into faces cut earlier) and a 0.25 break on each of its two
    # exposed edges.
    side_min = geom.BAR_SIDE - 0.8
    drop = mg_wheel_bar_spec.BORE_ROW_FROM_TOP
    assert drop == geom.BAR_TOP_ABOVE_ROW
    runoff = (BAR_DEPTH + 0.1) * math.tan(math.radians(0.3))
    assert runoff == pytest.approx(0.0503, abs=1e-4)
    losses = runoff + 2 * 0.25
    bores = {
        "axle bore": ((geom.AXLE_BORE_DIA + geom.AXLE_BORE_BAND[0]) / 2.0, 0.51),
        "hanger hole": (
            (geom.PEN_HANGER_HOLE_DIA + geom.DRILLED_HOLE_PLUS) / 2.0,
            0.51,
        ),
        "clamp holes": (
            (geom.CLAMP_HOLE_DIA + geom.DRILLED_HOLE_PLUS) / 2.0,
            mg_wheel_bar_spec.CLAMP_POSITION_BAND,
        ),
    }
    walls = {
        **{f"{b} top": drop - band - r - losses for b, (r, band) in bores.items()},
        **{
            f"{b} bottom": side_min - drop - band - r - losses
            for b, (r, band) in bores.items()
        },
        "hanger hole end": geom.HANGER_STATION
        - 0.51
        - bores["hanger hole"][0]
        - losses,
    }
    assert walls == pytest.approx(mg_wheel_bar_spec.BORE_ROW_WALLS)
    # Owner ruling 2026-10-26 (#1532): these seven, each under the 2.0 target
    # and over the 1.5 floor, are owner-accepted minors.
    assert walls == pytest.approx(
        {
            "axle bore top": 1.566,
            "hanger hole top": 1.604,
            "clamp holes top": 1.731,
            "axle bore bottom": 1.766,
            "hanger hole bottom": 1.804,
            "clamp holes bottom": 1.931,
            "hanger hole end": 1.604,
        },
        abs=1e-3,
    )
    assert all(1.5 <= wall < 2.0 for wall in walls.values())
    assert mg_wheel_bar_spec.WALL_CALLOUT_MIN == {
        "axle bore": 1.56,
        "hanger hole": 1.60,
        "clamp holes": 1.73,
    }
    # The photographed 10 bar leaves the walls under the bores under the
    # floor: the height grew rather than a band tightening.
    for b, (r, band) in bores.items():
        assert 10.0 - 0.8 - drop - band - r - losses < 1.5, b
    radius, band = bores["clamp holes"]
    assert 10.0 - 0.8 - drop - band - radius - losses == pytest.approx(0.931, abs=1e-3)


def test_every_wall_is_an_owner_declared_minor_stated_on_the_sheet() -> None:
    import math

    import _config
    from machinist_exceptions import load_exceptions

    declared = load_exceptions(_config.CONFIG_DIR, "mg_wheel_bar", "part")
    assert len(declared) == len(mg_wheel_bar_spec.BORE_ROW_WALLS) == 7
    texts = {
        "axle bore": callouts.AXLE_BORE_CALLOUT,
        "hanger hole": callouts.HANGER_HOLE_CALLOUT,
        "clamp holes": callouts.CLAMP_HOLE_CALLOUT,
    }
    for wall, value in mg_wheel_bar_spec.BORE_ROW_WALLS.items():
        matches = [entry for entry in declared if f"({wall} wall" in entry.where]
        assert len(matches) == 1, wall
        (entry,) = matches
        bore = next(b for b in texts if wall.startswith(b))
        row = callouts.callout_rows(texts[bore])[-1]
        assert entry.kind == "minor"
        assert row in entry.where
        assert f"{math.floor(value * 100) / 100:.2f}" in entry.finding
        assert "rule 17" in entry.finding
        assert entry.reason.startswith("owner ruling 2026-10-26 (#1532)")


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
        "BoreRowFromTop": 2,
        "ClampRowFromTop": 2,
        "HangerStation": 2,
        "ClampStation1": 2,
        "ClampStation2": 2,
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

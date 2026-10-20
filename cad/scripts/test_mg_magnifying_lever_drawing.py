"""Offline contracts for the magnifying-lever drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_mg_magnifying_lever as part
import draw_mg_magnifying_lever as drawing
import mg_magnifying_lever_spec
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-magnifying-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-magnifying-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-magnifying-lever_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_magnifying_lever"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert part.DRAWING_DIMENSIONS is mg_magnifying_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*mg_magnifying_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.REFERENCE_KEEP)
    assert kept == marked
    assert marked == {
        "OverallLength",
        "DomeRadius",
        "RodDia",
        "PressZoneStart",
        "PressZoneLen",
        "PressZoneDia",
    }
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= set(drawing.FRONT_KEEP)
    assert set(drawing.REFERENCE_CALLOUTS) <= set(drawing.REFERENCE_KEEP)
    assert drawing.ROD_LENGTH == mg_magnifying_lever_spec.ROD_LENGTH
    # The reference sketches' dims are the hidden-sketch path's, never the
    # entire-model import's (the part saves its reference sketches blanked).
    assert not set(drawing.REFERENCE_KEEP) & set(drawing.FRONT_KEEP)
    assert mg_magnifying_lever_spec.DRAWING_DIMENSIONS["RodStock"] == {"RodDia"}
    assert mg_magnifying_lever_spec.DRAWING_DIMENSIONS["PressZone"] == {
        "PressZoneStart",
        "PressZoneLen",
        "PressZoneDia",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "curate_hidden_dimensions(" in source
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in source
    assert "keep=REFERENCE_KEEP" in source


def test_stock_diameter_is_plain_stock_on_the_side_view() -> None:
    """Machinist review item 5: the Ø6 rod was a note only.  It prints once
    from the blanked RodStock reference sketch (the revolve profile's top line
    is already the dome radius's height, so a second diameter there
    over-defines the capsule), between two construction lines ON the top and
    bottom outlines, with the Ø prefix a linear dim needs (v41 sheet).  r1
    review blocker: it is plain bar stock at the title block's .X, no band,
    like MHA-MG-04's rod.  Owner ruling: the Ø prints bare -- no "STOCK OK"
    callout and no replacement note.  The bar's h9 band stays in the spec as
    the procurement contract the press zone is selected from."""
    import mg_lever_press_fit_geom as press
    from _fit_deviations import deviations

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "RodStock")' in source
    assert 'stock.record("RodDia", \'"RodDia"\')' in source
    assert (
        'stock.record("RodDiaStation", \'"RodLength" / 2 - "RodDia" / 2\')' in source
    )
    assert 'stock.record("RodStockSpan", \'"RodDia"\')' in source
    assert 'stock.record("RodStockTop", \'"RodDia" / 2\')' in source
    assert (
        'f"{stock_bottom}.start",\n        f"{stock_top}.start",\n'
        '        "vertical_distance",\n        ROD_DIA,\n        "rod stock RodDia",'
    ) in source
    assert 'set_dimension_prefix(adapter, "RodStock", "RodDia", "<MOD-DIAM>")' in source
    assert 'blank_reference_sketches(adapter, ("PressZone", "RodStock"))' in source
    assert "add_centerline(\n            ROD_DIA_STATION" not in source
    assert part.ROD_DIA_STATION == part.ROD_LENGTH / 2.0
    assert part.R == press.ROD_DIA / 2.0
    # Both lines span the station on the outlines, top first.
    assert part.ROD_STOCK_LINES == (
        ((part.ROD_DIA_STATION - part.R, part.R), (part.ROD_DIA_STATION + part.R, part.R)),
        ((part.ROD_DIA_STATION - part.R, -part.R), (part.ROD_DIA_STATION + part.R, -part.R)),
    )
    # Plain stock: .X, no band, no callout.
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["RodStock"] == {"RodDia": 1}
    assert '"RodStock", "RodDia"' not in source.replace(
        'set_dimension_prefix(adapter, "RodStock", "RodDia"', ""
    )
    assert "ROD_DIA_BAND" not in source
    assert not hasattr(mg_magnifying_lever_spec, "ROD_DIA_CALLOUT")
    assert "RodDia" not in drawing.REFERENCE_CALLOUTS
    assert "STOCK OK" not in Path(drawing.__file__).read_text(encoding="utf-8")
    # The procurement band contains the zone's tighter band on the same bar.
    assert mg_magnifying_lever_spec.ROD_DIA_BAND == (0.0, -0.03)
    stock_low, stock_high = deviations(mg_magnifying_lever_spec.ROD_DIA_BAND)
    zone_low, zone_high = deviations(press.PRESS_ZONE_DIA_BAND)
    assert stock_low <= zone_low <= zone_high <= stock_high
    assert "RodDiaStation" not in set().union(*part.DRAWING_DIMENSIONS.values())
    assert "RodStockSpan" not in set().union(*part.DRAWING_DIMENSIONS.values())
    assert "RodStockTop" not in set().union(*part.DRAWING_DIMENSIONS.values())
    # The dome radius is a reference now; its callout states the shape that
    # governs it, never the full radius or the rod diameter.
    assert drawing.DIMENSION_CALLOUTS["DomeRadius"] == "BOTH ENDS\nTANGENT HEMISPHERE"
    assert "FULL R" not in drawing.DIMENSION_CALLOUTS["DomeRadius"]
    assert "Ø6" not in drawing.DIMENSION_CALLOUTS["DomeRadius"]


def test_press_zone_is_a_native_band_from_the_config_free_press_contract() -> None:
    """The collar press (user rulings 2026-10-11/12): the STRAIGHT rod the
    collar grips carries its stock band natively on the blanked PressZone
    sketch; the rod diameter, zone length, bore nominal and band live in
    mg_lever_press_fit_geom so the bracket build, this build and the assembly's
    allowance read ONE source that pulls NO machine config; the worst-case
    budget is computed there, not typed anywhere. The lever geom keeps the
    configured station and asserts it is that zone, tip flush."""
    import ast

    import pytest

    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as geom

    press_source = Path(press.__file__).read_text(encoding="utf-8")
    imported = [
        node for node in ast.parse(press_source).body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    modules = {
        name
        for node in imported
        for name in (
            [node.module]
            if isinstance(node, ast.ImportFrom)
            else [alias.name for alias in node.names]
        )
    }
    assert modules == {"__future__", "math"}, (
        "the press contract must stay config-free (no _config/output.yaml closure)"
    )
    assert press.PRESS_ZONE_DIA == press.ROD_DIA == 6.0
    assert press.PRESS_ZONE_LENGTH == 10.0
    # Max-material model nominals (Main's 2026-10-12 press ruling).
    assert press.PRESS_ZONE_DIA_BAND == (0.0, -0.006)
    assert press.COLLAR_BORE_DIA == 5.986
    assert press.PRESS_INTERFERENCE_LIMITS == (0.007, 0.014)  # #1570 matched fit
    # The configured collar window is the zone, and the rod ends flush with it.
    assert geom.PRESS_ZONE_X == (
        geom.COLLAR_LOCAL_X - geom.COLLAR_HALF_LEN,
        geom.COLLAR_LOCAL_X + geom.COLLAR_HALF_LEN,
    )
    assert geom.PRESS_ZONE_X == (155.0, 165.0)
    assert geom.PRESS_ZONE_X[1] - geom.PRESS_ZONE_X[0] == press.PRESS_ZONE_LENGTH
    assert geom.PRESS_ZONE_X[1] == geom.ROD_LENGTH  # tip flush with the outer face
    assert not hasattr(geom, "COLLAR_BORE_DIA") and not hasattr(geom, "ROD_DIA")
    # Straight rod inside the collar: from its inner face to where the dome starts.
    assert press.COLLAR_ENGAGEMENT == press.PRESS_ZONE_LENGTH - press.ROD_DIA / 2.0
    assert press.COLLAR_ENGAGEMENT == pytest.approx(7.0)
    budget = press.press_fit_budget()
    for key in ("interference_nominal", "interference_min", "interference_max", "engagement"):
        assert budget[key] == press.PRESS_FIT_BUDGET[key]
    assert budget["interference_nominal"] == pytest.approx(0.014)
    assert budget["interference_min"] == pytest.approx(0.007)
    assert budget["interference_max"] == pytest.approx(0.014)
    assert budget["engagement"] == press.COLLAR_ENGAGEMENT_MAX
    # Whole-contact envelope with independent, deliberately conservative corners:
    # the longest collar less the smallest dome radius (the straight cylinder at
    # its longest), plus the part of the largest dome still outside the smallest
    # bore. Not one physical part (the coupled tight corner is 7.204819).
    collar_max, dome_min = 10.0 + 0.0, (6.0 - 0.006) / 2.0
    dome_max, bore_min = (6.0 + 0.0) / 2.0, (5.986 + 0.0) / 2.0
    assert budget["engagement"] == pytest.approx(
        collar_max - dome_min + math.sqrt(dome_max**2 - bore_min**2)
    )
    assert budget["engagement"] == pytest.approx(7.2078194326718075, abs=1e-9)
    assert press.COLLAR_ENGAGEMENT < budget["engagement"] < press.COLLAR_LENGTH
    assert 0.0 < budget["interference_min"] <= budget["interference_max"]
    # ANSI B4.1 FN2 for 0.12..0.24 in: 1.0 thou at the tightest.
    assert press.PRESS_INTERFERENCE_MAX_FN2 == pytest.approx(0.0254)
    assert budget["interference_max"] <= press.PRESS_INTERFERENCE_MAX_FN2
    assert part.PRESS_ZONE_DIA_BAND is press.PRESS_ZONE_DIA_BAND
    # Machinist review r2 over-specification: the zone's start from the tip is
    # a single native MIN limit (swTolMIN), never a band, here or in the geom.
    assert not hasattr(press, "PRESS_ZONE_LENGTH_BAND")
    assert not hasattr(part, "PRESS_ZONE_LENGTH_BAND")
    assert not hasattr(mg_magnifying_lever_spec, "PRESS_ZONE_LENGTH_BAND")
    assert not hasattr(mg_magnifying_lever_spec, "PRESS_ZONE_START_BAND")
    assert mg_magnifying_lever_spec.PRESS_ZONE_START_TOL_TYPE == 5  # swTolMIN
    assert part.PRESS_ZONE_START_TOL_TYPE is mg_magnifying_lever_spec.PRESS_ZONE_START_TOL_TYPE
    assert part.PRESS_ZONE_X is geom.PRESS_ZONE_X
    # Retry09 review: the zone is located from the rod TIP -- PRESS_ZONE_LENGTH
    # back to its start -- and runs to the dome tangent, so its banded
    # cylinder is ONLY the straight engagement, never the R3 dome.
    assert geom.ROD_LENGTH - part.PRESS_ZONE_X[0] == press.PRESS_ZONE_LENGTH
    assert part.PRESS_ZONE_END == geom.ROD_LENGTH - press.ROD_DIA / 2.0 == 162.0
    assert part.PRESS_ZONE_END - part.PRESS_ZONE_X[0] == press.COLLAR_ENGAGEMENT
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'name_last_feature(adapter, "PressZone")' in source
    assert '"PressZone", "PressZoneDia", *deviations(PRESS_ZONE_DIA_BAND)' in source
    # Linear dims across a side view print no Ø of their own (v41 sheet).
    assert 'set_dimension_prefix(adapter, "PressZone", "PressZoneDia", "<MOD-DIAM>")' in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "segment.ConstructionGeometry = True" in source
    # r1 review: the zone-start mark crosses the bar at the start (a solid
    # line, the print shows it); the witness rides the bottom outline from
    # the start to the tangent; the tip arc rides the dome's lower outline
    # from the tangent to the tip.  No centerline is left to print a dashed
    # fragment inside the rod.
    assert part.PRESS_ZONE_START_LINE == (
        (part.PRESS_ZONE_X[0], -part.R),
        (part.PRESS_ZONE_X[0], part.R),
    )
    assert part.PRESS_ZONE_WITNESS == (
        (part.PRESS_ZONE_X[0], -part.R),
        (part.PRESS_ZONE_END, -part.R),
    )
    assert part.PRESS_ZONE_TIP_ARC == (
        (part.PRESS_ZONE_END, 0.0),
        (part.PRESS_ZONE_END, -part.R),
        (geom.ROD_LENGTH, 0.0),
    )
    assert "add_centerline(PRESS_ZONE_X" not in source
    assert "_make_construction(adapter, zone_witness)" in source
    assert "_make_construction(adapter, zone_tip_arc)" in source
    assert "_make_construction(adapter, zone_mark)" not in source
    assert '(zone_witness, zone_tip_arc, "tangent"),' in source
    assert (
        'f"{zone_tip_arc}.end",\n        "origin",\n        "horizontal_distance",\n'
        '        ROD_LENGTH,\n        "press zone PressZoneTip",'
    ) in source
    assert (
        'f"{zone_witness}.start",\n        f"{zone_tip_arc}.end",\n'
        '        "horizontal_distance",\n        PRESS_ZONE_LENGTH,\n'
        '        "press zone PressZoneStart",'
    ) in source
    assert (
        'f"{zone_mark}.start",\n        f"{zone_mark}.end",\n'
        '        "vertical_distance",\n        PRESS_ZONE_DIA,\n'
        '        "press zone PressZoneDia",'
    ) in source
    assert (
        '"horizontal_distance",\n        COLLAR_ENGAGEMENT,\n        "press zone PressZoneLen",'
        in source
    )
    assert 'zone.record("PressZoneTip", \'"RodLength"\')' in source
    assert 'zone.record("PressZoneStart", \'"CollarLen"\')' in source
    assert 'zone.record("PressZoneLen", \'"CollarLen" - "RodDia" / 2\')' in source
    assert 'zone.record("PressZoneDia", \'"RodDia"\')' in source
    assert "PressZoneEnd" not in source
    assert 'set_global(adapter, "CollarLen", f"{PRESS_ZONE_LENGTH}mm")' in source
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["PressZone"] == {
        "PressZoneStart": 1,
        "PressZoneLen": 1,
        "PressZoneDia": 3,
    }
    # The MIN recipe (build_sm_vn_knife_hanger_stud's ThreadLengthMin) with the
    # bracket's readback: the model value is the limit, no deviations.
    assert "_press_zone_start_min_limit(adapter)" in source
    assert '_named_dimension(adapter, "PressZone", "PressZoneStart")' in source
    assert "math.isclose(value, PRESS_ZONE_LENGTH / 1000.0, abs_tol=1e-9)" in source
    assert "tolerance.Type = PRESS_ZONE_START_TOL_TYPE" in source
    assert "tolerance.SetValues(0.0, 0.0)" in source
    assert "int(tolerance.Type) != PRESS_ZONE_START_TOL_TYPE" in source
    assert "float(tolerance.GetMinValue()), 0.0" in source
    assert "float(tolerance.GetMaxValue()), 0.0" in source
    assert '"PressZone", "PressZoneStart", *deviations' not in source
    assert "PressZoneTip" not in set().union(*part.DRAWING_DIMENSIONS.values())
    # The cylinder's length (start less the dome radius) prints as a LINEAR
    # reference; the start from the tip is the toleranced value.
    assert mg_magnifying_lever_spec.REFERENCE_DIMENSIONS == {"PressZoneLen"}
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension(adapter, matches[0]" in sheet_source
    assert "set_reference_dimensions(" not in sheet_source
    assert "PressZoneLen" not in drawing.REFERENCE_CALLOUTS
    # r2 review: the MIN is the longest collar's length -- the tip is flush
    # with the collar's outer face, so the selected land covers every collar
    # -- and the callout names that mate, no number of its own.
    assert press.PRESS_ZONE_LENGTH == press.COLLAR_LENGTH + press.COLLAR_LENGTH_BAND[0]
    assert (
        drawing.REFERENCE_CALLOUTS["PressZoneStart"]
        is mg_magnifying_lever_spec.PRESS_ZONE_START_CALLOUT
        == "PRESS ZONE COVERS\nMHA-MG-01 COLLAR"
    )
    assert "MATCHES" not in mg_magnifying_lever_spec.PRESS_ZONE_START_CALLOUT
    # The sheet's stations come from the same constants as the model's.
    assert drawing._PRESS_ZONE_START_X == pytest.approx(
        drawing._ROD_TIP_X - press.PRESS_ZONE_LENGTH / 1000.0
    )
    assert drawing._DOME_TANGENT_X == pytest.approx(
        drawing._ROD_TIP_X - press.ROD_DIA / 2000.0
    )
    assert drawing._DOME_TANGENT_X - drawing._PRESS_ZONE_START_X == pytest.approx(
        press.COLLAR_ENGAGEMENT / 1000.0
    )


def test_overall_length_runs_tip_to_tip_on_the_profile() -> None:
    """Retry09 review: the far dome centre (162.00) cannot be picked up; the
    profile dimensions the rod between its two dome tips -- the axis line's
    ends, merged with the apexes (build_ch_fulcrum_shaft's idiom) -- at .X,
    and the right dome's centre is only placed on the axis, R back from the
    tip by the radial dim."""
    import mg_lever_press_fit_geom as press

    assert mg_magnifying_lever_spec.DRAWING_DIMENSIONS["RodProfile"] == {
        "OverallLength",
        "DomeRadius",
    }
    assert mg_magnifying_lever_spec.DRAWING_PRECISION["RodProfile"] == {
        "OverallLength": 1,
        "DomeRadius": 1,
    }
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        'f"{axis_line}.start",\n        f"{axis_line}.end",\n'
        '        "horizontal_distance",\n        ROD_LENGTH,\n'
        '        "rod OverallLength",'
    ) in source
    assert 'profile.record("OverallLength", \'"RodLength"\')' in source
    assert 'f"{cap_right}.center", "origin", "horizontal_points"' in source
    assert "RightDomeCentre" not in source
    assert part.R == press.ROD_DIA / 2.0
    assert "OverallLength" not in drawing.DIMENSION_CALLOUTS
    assert "TO FAR DOME CENTRE" not in drawing.DIMENSION_CALLOUTS.values()


def test_dome_radius_is_a_radial_reference_of_the_tangent_hemisphere() -> None:
    """Main's batch10 ruling: each dome is a full hemisphere tangent to the
    selected bar, so its radius follows the zone diameter (R2.997 at the
    smallest selected bar) and prints as a radial REFERENCE "(R3.0)": the
    display's own radius glyph is kept behind the "(" (the singular
    set_reference_dimension's bare "(" would replace it, the plural one would
    print a Ø)."""
    import mg_lever_press_fit_geom as press

    assert mg_magnifying_lever_spec.RADIAL_REFERENCE_DIMENSIONS == {"DomeRadius"}
    assert not (
        mg_magnifying_lever_spec.RADIAL_REFERENCE_DIMENSIONS
        & mg_magnifying_lever_spec.REFERENCE_DIMENSIONS
    )
    assert "DomeRadius" in drawing.FRONT_KEEP
    min_radius = (press.PRESS_ZONE_DIA + press.PRESS_ZONE_DIA_BAND[1]) / 2.0
    assert f"{min_radius:.1f}" == f"{part.R:.1f}" == "3.0"
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'profile.record("DomeRadius", \'"RodDia" / 2\')' in source
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_set_radial_reference(adapter, matches[0]" in sheet_source
    assert 'prefix = "(" + existing' in sheet_source
    assert "for name in sorted(RADIAL_REFERENCE_DIMENSIONS):" in sheet_source
    assert "<MOD-DIAM>" not in sheet_source


# Text geometry measured on the farm r4 sheet (20261017T025452884Z): a
# dimension's rows print centred on the requested (x, y), callout rows 5.56 mm
# apart, 3.5 mm caps, the dimension line at the lowest row's baseline (r4's
# five-row zone start, requested at y 126 mm, spanned 113.1..138.6 mm); a lone
# row's baseline sits 2.78 mm under the requested y (r4's (7.0) line at 135.2
# mm); the widest r4 row, "MATCHES MHA-MG-01", printed 52.3 mm over its 18
# characters.
_ROW_PITCH = 0.00556
_TEXT_HEIGHT = 0.0035
_LONE_ROW_DROP = 0.00278
_CHAR_WIDTH = 0.0523 / 18


def _block_half_extent(rows: list[str]) -> tuple[float, float]:
    """(half width, half height) of a dimension's centred block of rows."""
    return (
        _CHAR_WIDTH * max(len(row) for row in rows) / 2.0,
        (_TEXT_HEIGHT + (len(rows) - 1) * _ROW_PITCH) / 2.0,
    )


def test_press_zone_text_clears_its_lines_and_the_isometric() -> None:
    """Retry09 review: the zone diameter's rows sat on its own dimension
    line.  Its line now stands inside the zone and its rows hang above the
    rod, right of that line (layout doc: rows hang from a shoulder that starts
    at the line), above the dome radius; the zone's lengths print below the
    rod off the bottom witness, the reference innermost and left of its span,
    the start from the tip outside it and right of the tip, the overall length
    outermost.  Machinist review r2: r4's zone-start block (52 mm wide,
    centred 24 mm right of the tip) ran the tip's extension line through its
    'M', and its line was level with the 165.0's, so the overall read as
    ending at the zone start.  The block now sits wholly right of that line,
    under the (7.0) line, and the 165.0 runs on its own line well below."""
    import mg_lever_press_fit_geom as press

    rod_bottom_y = drawing.FRONT_CENTER[1] - drawing.ROD_DIA / 2000.0
    dia_x, dia_y = drawing.REFERENCE_KEEP["PressZoneDia"]
    assert drawing._PRESS_ZONE_START_X < dia_x < drawing._DOME_TANGENT_X
    assert dia_y > drawing.FRONT_KEEP["DomeRadius"][1] + 0.015
    assert drawing.FRONT_KEEP["DomeRadius"][0] > drawing._ROD_TIP_X
    assert drawing.FRONT_KEEP["DomeRadius"][1] > drawing._ROD_TOP_Y
    length_x, length_y = drawing.REFERENCE_KEEP["PressZoneLen"]
    start_x, start_y = drawing.REFERENCE_KEEP["PressZoneStart"]
    overall_y = drawing.FRONT_KEEP["OverallLength"][1]
    assert overall_y < start_y < length_y < rod_bottom_y
    assert length_x < drawing._PRESS_ZONE_START_X
    assert start_x > drawing._ROD_TIP_X
    # The zone start prints "10.0 MIN" over its two callout rows.
    places = mg_magnifying_lever_spec.DRAWING_PRECISION["PressZone"]["PressZoneStart"]
    start_rows = [
        f"{press.PRESS_ZONE_LENGTH:.{places}f} MIN",
        *mg_magnifying_lever_spec.PRESS_ZONE_START_CALLOUT.split("\n"),
    ]
    assert start_rows[0] == "10.0 MIN" and len(start_rows) == 3
    half_width, half_height = _block_half_extent(start_rows)
    assert half_width * 2.0 < 0.052  # narrower than r4's block
    # Wholly right of the tip's extension line, by an arrow's air (2 mm).
    assert start_x - half_width >= drawing._ROD_TIP_X + 0.002
    # Under the (7.0) reference's line, which runs on past the tip.
    assert start_y + half_height < length_y - _LONE_ROW_DROP
    # Clear below the dome radius's three-row block and short of the
    # isometric (its leftmost ink at x ~319 mm on r4).
    dome_y = drawing.FRONT_KEEP["DomeRadius"][1]
    dome_rows = ["(R3.0)", *drawing.DIMENSION_CALLOUTS["DomeRadius"].split("\n")]
    dome_half_height = _block_half_extent(dome_rows)[1]
    assert start_y + half_height + 0.010 < dome_y - dome_half_height
    assert start_x + half_width < 0.300
    # The 165.0 runs on its own line, >= 10 mm under the zone start's (the
    # lowest row's baseline), above the title block's top (y ~65 mm).
    start_line = start_y - half_height
    overall_line = overall_y - _LONE_ROW_DROP
    assert start_line - overall_line >= 0.010
    assert overall_line > 0.070
    # Two rows, so the mate callout stays short of the isometric.
    rows = mg_magnifying_lever_spec.PRESS_ZONE_DIA_CALLOUT.split("\n")
    assert len(rows) == 2
    assert max(len(row.replace("<MOD-DIAM>", "Ø")) for row in rows) <= 36
    assert drawing.ISO_CENTER == (0.350, 0.185)


def test_press_zone_callout_ties_the_zone_to_the_bracket_bore() -> None:
    """Review item 5 / code-review nit: the banded zone's callout names the
    mating MHA-MG-01 bore as the REFERENCE nominal that sheet prints and the
    matched-fit interference its callout states (rule 25: the sheets agree;
    the bore carries no absolute band), every number derived from
    mg_lever_press_fit_geom in the spec -- the sheet carries no
    manufacturing string of its own (_drawing_contract)."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_bracket_spec as bracket_spec
    from _drawing_contract import drawing_specification_violations

    callout = mg_magnifying_lever_spec.PRESS_ZONE_DIA_CALLOUT
    assert drawing.REFERENCE_CALLOUTS["PressZoneDia"] is callout
    assert callout == (
        "IN MHA-MG-01 (<MOD-DIAM>5.986) BORE:\n0.007-0.014 DIAMETRAL INTERFERENCE"
    )
    assert f"(<MOD-DIAM>{press.COLLAR_BORE_DIA:.3f})" in callout
    assert "/" not in callout and "+0.006" not in callout
    interference = (
        f"{press.PRESS_FIT_BUDGET['interference_min']:.3f}-"
        f"{press.PRESS_FIT_BUDGET['interference_max']:.3f}"
    )
    assert f"{interference} DIAMETRAL INTERFERENCE" in callout
    # The bracket sheet's bore callout states the same matched fit.
    assert interference in bracket_spec.COLLAR_BORE_CALLOUT
    assert "DIAMETRAL INTERFERENCE" in bracket_spec.COLLAR_BORE_CALLOUT
    script = Path(drawing.__file__)
    assert not drawing_specification_violations(
        script.read_text(encoding="utf-8"), filename=script.name
    )


def test_final_forced_volume_guard_follows_annotations_before_publication() -> None:
    """Source ordering only: after the last dimension/annotation mutation the
    build rebuilds, re-proves the rod's volume, then saves."""
    import ast

    source = Path(part.__file__).read_text(encoding="utf-8")
    build = next(
        node for node in ast.parse(source).body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    rebuild, guard, publish = build.body[-3:]
    assert isinstance(rebuild, ast.Expr) and isinstance(rebuild.value, ast.Await)
    assert rebuild.value.value.func.id == "force_rebuild"
    assert isinstance(guard, ast.Expr) and isinstance(guard.value, ast.Await)
    call = guard.value.value
    assert call.func.id == "volume_check"
    assert call.args[1].value == "final rod (annotations neutral)"
    assert call.args[2].id == "v_rod"
    assert isinstance(publish, ast.Return) and isinstance(publish.value, ast.Await)
    assert publish.value.value.func.id == "save_part_and_images"
    for mutation in (
        "set_dimension_bilateral_tolerance",
        "_press_zone_start_min_limit",
        "set_dimension_prefix",
        "apply_drawing_precision",
        "clear_dimensions_for_drawing",
        "mark_dimensions_for_drawing",
        "author_part_pmi",
        "apply_drawing_properties",
        "blank_reference_sketches",
    ):
        calls = [
            node for node in ast.walk(build)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == mutation
        ]
        assert calls, mutation
        assert all(node.lineno < rebuild.lineno for node in calls), mutation


def test_drawing_contract_is_split_from_the_assembly_nominals() -> None:
    # The knife-axis station the assembly imports lives in the drawing-FREE geom
    # module, so a print-note edit cannot enter the assembly's recipe closure.
    import mg_lever_press_fit_geom as press
    import mg_magnifying_lever_geom as geom

    assert (press.ROD_DIA, geom.ROD_LENGTH) == (6.0, 165.0)
    assert mg_magnifying_lever_spec.ROD_LENGTH is geom.ROD_LENGTH
    assert mg_magnifying_lever_spec.PRESS_ZONE_LENGTH is press.PRESS_ZONE_LENGTH
    assert hasattr(geom, "KNIFE_LOCAL_X") and hasattr(geom, "KNIFE_LOCAL_Y")
    assembly = (
        Path(part.__file__)
        .with_name("build_mg_magnifier_assembly.py")
        .read_text(encoding="utf-8")
    )
    assert "from mg_magnifying_lever_geom import (" in assembly
    assert "KNIFE_LOCAL_X," in assembly
    assert "KNIFE_LOCAL_Y," in assembly


def test_sheet_carries_no_note_block() -> None:
    """r1 review over-specification: the zone's selection, how to hold the
    rod and the press force are the MHA-MG-00 assembly's step, the stock is a
    plain Ø, the zone carries callouts at its features and the screw seat's
    reason stands at its Ra symbol -- so the sheet carries no note block
    (drawing-guidelines.md rule 7)."""
    assert not hasattr(mg_magnifying_lever_spec, "DRAWING_NOTES")
    for script in (part.__file__, drawing.__file__):
        assert "Manufacturing Notes" not in Path(script).read_text(encoding="utf-8")


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the front side view
    assert drawing.ISO_SCALE == (1, 2)
    assert "scale=ISO_SCALE" in source
    assert mg_magnifying_lever_spec.ISO_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Iso View Note"' in source
    # Retry09 review: the featureless end view is gone, with its scale note.
    assert '"*Right"' not in source and "End View Note" not in source
    assert "auto_center_marks" not in source
    assert not hasattr(drawing, "RIGHT_KEEP") and not hasattr(drawing, "RIGHT_CENTER")
    assert not hasattr(mg_magnifying_lever_spec, "END_VIEW_NOTE")
    assert "End View Note" not in Path(part.__file__).read_text(encoding="utf-8")


def test_rod_od_carries_one_clamp_screw_seat_finish() -> None:
    """Owner rulings 2026-10-17 (supersede r1's "no finish"): the MHA-MG-02
    clamp's thumb screw pinches the Ø6 body where the clamp is set, a static
    locating seat -- Ra 3.2 (drawing-guidelines.md rule 6), on the WHOLE Ø6
    face as on the MHA-MG-04 vertical rod, no seat-zone lengths.  The screw's
    reach over the block's travel, from the live output.yaml stations and the
    clamp geometry, lies on that one face; the part owns the one control, the
    sheet consumes it."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_clamp_geom as clamp
    import mg_magnifying_lever_geom as geom
    from sh_vn_thumb_screw_spec import SHANK_DIA
    from _surface_finish import SEAT_UM

    spec = mg_magnifying_lever_spec
    # Screw on the hex axis = the block's centre along the rod, which slides
    # from flush with the west tip to against the collar face.
    half_block = clamp.BLOCK_DEPTH / 2.0
    _r_min, _r_as_built, r_max = geom.clamp_radius_band(clamp.BLOCK_DEPTH)
    farthest = geom.KNIFE_LOCAL_X - r_max
    nearest = geom.COLLAR_LOCAL_X - geom.COLLAR_HALF_LEN - half_block
    assert farthest == pytest.approx(half_block)
    assert farthest <= geom.CLAMP_LOCAL_X <= nearest
    reach = (farthest - SHANK_DIA / 2.0, nearest + SHANK_DIA / 2.0)
    assert reach == pytest.approx((4.993, 150.007), abs=1e-3)  # the current stations
    # The reach lies on the body's one Ø6 face: the revolve's single top line
    # runs dome tangent to dome tangent, through the press zone.
    assert "await adapter.add_line(R, R, ROD_LENGTH - R, R)" in Path(
        part.__file__
    ).read_text(encoding="utf-8")
    assert part.R <= reach[0] < reach[1] <= part.ROD_LENGTH - part.R
    assert geom.PRESS_ZONE_X[0] < part.ROD_LENGTH - part.R
    assert [row.key for row in spec.SURFACE_FINISHES] == ["clamp_screw_seat", "press_land"]
    control = surface_finish_by_key(spec.SURFACE_FINISHES, "clamp_screw_seat")
    assert control.key == "clamp_screw_seat"
    assert control.roughness_um == SEAT_UM == 3.2
    assert control.production_method == ""
    assert control.face.diameter_mm == press.ROD_DIA
    # The whole face: no station narrows it to a zone.
    assert control.face.contains_x_mm is None
    assert control.face.contains_y_mm is None and control.face.contains_z_mm is None
    assert spec.SCREW_SEAT_CALLOUT == "MHA-MG-02 SCREW SEAT"
    # Clean cutover from the r15 seat zone: no sketch, dims or plumbing left.
    for name in (
        "SCREW_SEAT_X",
        "SCREW_SEAT_LENGTH",
        "SCREW_SEAT_STEP",
        "CLAMP_SCREW_TRAVEL",
    ):
        assert not hasattr(spec, name), name
    assert "ScrewSeat" not in spec.DRAWING_DIMENSIONS
    assert "ScrewSeat" not in spec.DRAWING_PRECISION
    assert not hasattr(part, "SCREW_SEAT_LINE")
    build_source = Path(part.__file__).read_text(encoding="utf-8")
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    for source in (build_source, sheet_source):
        assert "ScrewSeat" not in source and "SCREW_SEAT_X" not in source
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in build_source
    assert sheet_source.count("add_surface_finish(\n") == 2
    assert 'surface_finish_by_key(SURFACE_FINISHES, "clamp_screw_seat")' in sheet_source
    # Attached to the OD's face, not its top silhouette: the front view lies
    # in the revolve's profile plane, so that outline is the cylinder's seam
    # and a silhouette re-solved onto the other half-face (r12). A coordinate
    # face pick keeps the leader at the pick (r13) and one 0.4 mm inside the
    # outline selected nothing (r14), so pick == landing, midway in the OD.
    assert 'entity_type="FACE"' in sheet_source
    assert 'entity_type="SILHOUETTE"' not in sheet_source
    assert "edge_xy=SEAT_FINISH_PICK" in sheet_source
    assert "leader_attach_xy=SEAT_FINISH_PICK" in sheet_source
    # The leader lands on the OD's face, inside the screw's reach.
    pick_x, pick_y = drawing.SEAT_FINISH_PICK
    assert drawing.FRONT_CENTER[1] < pick_y < drawing._ROD_TOP_Y
    assert pick_y == pytest.approx((drawing.FRONT_CENTER[1] + drawing._ROD_TOP_Y) / 2)
    station = (pick_x - drawing._ROD_WEST_TIP_X) * 1000.0
    assert reach[0] < station < reach[1]
    # Clear of the stock diameter's points (mid-length +/- R).
    assert abs(station - part.ROD_DIA_STATION) > part.R + 5.0


def test_screw_seat_reason_stands_at_its_symbol() -> None:
    """Machinist review r4: the seat's reason, a callout on the old seat
    length 15 mm over the symbol, read as detached from it.  It is now one
    free row in the front view directly over the Ra 3.2 symbol, left-aligned
    with it, clear of the Ø6.0's row and west of the zone diameter's block;
    its text is the spec's, no dimension and no method."""
    spec = mg_magnifying_lever_spec
    text = spec.SCREW_SEAT_CALLOUT
    assert "\n" not in text
    assert not set("()±/").intersection(text) and "MIN" not in text
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "_add_finish_reason(\n        adapter, front, SCREW_SEAT_CALLOUT, SEAT_REASON_XY,"
        in sheet_source
    )
    # Placed after its symbol, in the front view.
    assert sheet_source.index("SCREW_SEAT_CALLOUT, SEAT_REASON_XY") > sheet_source.index(
        "add_surface_finish(\n"
    )
    assert "ActivateView(name)" in sheet_source
    assert text not in drawing.REFERENCE_CALLOUTS.values()
    # A note's position is its top-left corner.
    left, top = drawing.SEAT_REASON_XY
    right = left + _CHAR_WIDTH * len(text)
    bottom = top - _TEXT_HEIGHT
    sym_x, sym_y = drawing.SEAT_FINISH_SYMBOL
    # The symbol's ink reached 7.2 mm over its root on r15: the row stands
    # just over it (>= 1.5 mm air, <= 15 mm from the root) and starts within
    # 3 mm of the symbol's x.
    assert sym_y + 0.0072 + 0.0015 <= bottom
    assert top - sym_y <= 0.015
    assert abs(left - sym_x) <= 0.003
    # The symbol itself: above the rod, west of the stock diameter.
    dia_x, dia_y = drawing.REFERENCE_KEEP["RodDia"]
    assert drawing._ROD_TOP_Y + 0.008 < sym_y
    assert drawing._ROD_WEST_TIP_X + 0.010 < sym_x < dia_x - 0.030
    # Over the Ø6.0's lone row by >= 3 mm, on the sheet right of the west tip,
    # and west of the zone diameter's line (its block hangs right of it).
    assert bottom - (dia_y + _TEXT_HEIGHT / 2.0) >= 0.003
    assert left > drawing._ROD_WEST_TIP_X
    assert right + 0.020 < drawing.REFERENCE_KEEP["PressZoneDia"][0]


def test_reference_sketches_print_only_the_zone_start_inside_the_rod() -> None:
    """r1 review: the zone's limits were not drawn on the rod, and the
    centerlines/witnesses the reference sketches showed printed dashed
    fragments inside it.  Proved offline against the capsule's silhouette:
    the one solid line crosses the bar at the zone start, ends on the
    outline; every construction entity lies ON the outline; the zone's
    diameter lands between the start line and the dome's tangent edge."""

    def offset(x: float, y: float) -> float:
        r, length = part.R, part.ROD_LENGTH
        if r <= x <= length - r:
            return abs(abs(y) - r)
        centre = r if x < r else length - r
        return abs(math.hypot(x - centre, y) - r)

    (bottom, top) = part.PRESS_ZONE_START_LINE
    assert bottom[0] == top[0] == part.ROD_LENGTH - mg_magnifying_lever_spec.PRESS_ZONE_LENGTH
    assert part.R < bottom[0] < part.ROD_LENGTH - part.R
    assert offset(*bottom) == offset(*top) == 0.0
    assert bottom[1] == -part.R and top[1] == part.R
    for start, end in (part.PRESS_ZONE_WITNESS, *part.ROD_STOCK_LINES):
        assert start[1] == end[1]
        assert part.R <= start[0] < end[0] <= part.ROD_LENGTH - part.R
        assert offset(*start) == offset(*end) == 0.0
    centre, arc_start, arc_end = part.PRESS_ZONE_TIP_ARC
    assert centre == (part.ROD_LENGTH - part.R, 0.0)
    for point in (arc_start, arc_end):
        assert math.hypot(point[0] - centre[0], point[1] - centre[1]) == part.R
        assert offset(*point) == 0.0
    # Counter-clockwise from the tangent (straight below the centre) to the
    # tip (straight east of it): the dome's lower quarter, on its outline.
    assert arc_start == (centre[0], -part.R) and arc_end == (part.ROD_LENGTH, 0.0)
    # The helper the build's module-level proof uses agrees.
    for x, y in ((150.0, 3.0), (163.0, 0.0), (1.0, -1.0), (part.ROD_LENGTH, 0.0)):
        assert part.silhouette_offset(x, y) == pytest.approx(offset(x, y))
    # The banded diameter's line stands between the zone limits.
    dia_x, _dia_y = drawing.REFERENCE_KEEP["PressZoneDia"]
    assert drawing._PRESS_ZONE_START_X < dia_x < drawing._DOME_TANGENT_X
    assert drawing._PRESS_ZONE_START_X == pytest.approx(
        drawing.FRONT_CENTER[0] + (bottom[0] - part.ROD_LENGTH / 2.0) / 1000.0
    )


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("mg-magnifying-lever")
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1
    # The clamp block still slides along the rod; the tip end is pressed.
    assert config["fit_class"] == "shaft_in_bushing"
    assert "MHA-MG-01" in config["process"]


def test_machinist_exceptions_accept_the_owner_ruled_finishes() -> None:
    """Owner ruling 2026-10-17: the Ra 3.2 on the Ø6 body is the MHA-MG-02
    clamp screw's functional seat (rule 6), declared so the reviewer does not
    re-file it as a symbol on a clamp face.  #1570 (press only): the press
    land's Ra 0.8 is the retention proof's smoothing input, declared as the
    MHA-MG-01 bore's is, with the proof's own numbers."""
    import mg_lever_press_fit_geom as press
    from machinist_exceptions import load_exceptions
    from _surface_finish import SEAT_UM

    config_root = Path(part.__file__).resolve().parents[1] / "config"
    entry, land = load_exceptions(config_root, "mg_magnifying_lever", "part")
    assert (entry.id, entry.kind) == ("RV-01", "accept")
    assert "Ra 3.2" in entry.where and "Ø6 body" in entry.where
    assert "rule 6" in entry.finding and "rule 6" in entry.reason
    assert "owner ruling 2026-10-17" in entry.reason
    assert "MHA-MG-02" in entry.reason
    assert (land.id, land.kind) == ("RV-02", "accept")
    assert "Ra 0.8" in land.where and "press land" in land.where
    assert " ".join(mg_magnifying_lever_spec.PRESS_LAND_CALLOUT.split()) in land.where
    assert "rule 6" in land.finding
    assert land.reason.startswith("owner ruling #1570")
    assert land.reason.endswith("(owner-accepted)")
    floor = press.PRESS_INTERFERENCE_LIMITS[0]
    for land_ra in (press.ROD_LAND_RA_UM, SEAT_UM):
        smoothing = (
            press.SMOOTHING_FACTOR * press.RZ_PER_RA
            * (press.COLLAR_BORE_RA_UM + land_ra) / 1000.0
        )
        # The land's term first (both 0.8 for the printed grade).
        assert (
            f"{press.SMOOTHING_FACTOR:g} x {press.RZ_PER_RA:g} x "
            f"({land_ra:g} + {press.COLLAR_BORE_RA_UM:g}) um = {smoothing:.5f}"
        ) in land.reason
        assert f"effective minimum {floor - smoothing:.5f}" in land.reason
    assert f"{floor:g} minimum" in land.reason


def test_press_land_prints_the_roughness_the_retention_proof_takes() -> None:
    """C01 (#1570 press only): the retention proof's DIN 7190 smoothing takes
    the land at ROD_LAND_RA_UM, so the land prints that grade -- its own
    symbol on the Ø6 face, overriding the body's general Ra 3.2 -- and the
    bore prints COLLAR_BORE_RA_UM.  Smoothing recomputed from the two PRINTED
    symbols is the proof's, and at the loosest band corner (0.007) it still
    leaves interference that grips (press_holding); with the land left at the
    face's Ra 3.2 the same corner smooths to -0.0058 and the proof refuses."""
    import mg_lever_press_fit_geom as press
    import mg_magnifying_bracket_spec as bracket_spec
    from _surface_finish import GROUND_UM, SEAT_UM

    spec = mg_magnifying_lever_spec
    land = surface_finish_by_key(spec.SURFACE_FINISHES, "press_land")
    seat = surface_finish_by_key(spec.SURFACE_FINISHES, "clamp_screw_seat")
    bore = surface_finish_by_key(bracket_spec.SURFACE_FINISHES, "collar_bore")
    assert land.roughness_um == press.ROD_LAND_RA_UM == GROUND_UM
    assert bore.roughness_um == press.COLLAR_BORE_RA_UM
    assert land.production_method == ""
    # The land is the zone's Ø6 face; the stricter grade governs it.
    assert land.face == seat.face and land.face.diameter_mm == press.PRESS_ZONE_DIA
    assert land.roughness_um < seat.roughness_um == SEAT_UM

    def smoothing(bore_ra: float, land_ra: float) -> float:
        return press.SMOOTHING_FACTOR * press.RZ_PER_RA * (bore_ra + land_ra) / 1000.0

    loosest = press.PRESS_INTERFERENCE_LIMITS[0]
    printed = smoothing(bore.roughness_um, land.roughness_um)
    assert printed == pytest.approx(press.SMOOTHING, abs=1e-15)
    budget = press.PRESS_FIT_BUDGET
    assert budget["interference_effective_min"] == pytest.approx(loosest - printed)
    assert loosest - printed == pytest.approx(0.00188, abs=1e-12)
    press.check_press_fit_budget(budget)
    holding = press.press_holding(1.0, 1.0)
    assert holding["contact_pressure_min_mpa"] > 0.0 and holding["axial_hold_n"] > 0.0
    # The counterexample the finding names: the land at the body's Ra 3.2.
    rough = smoothing(bore.roughness_um, seat.roughness_um)
    assert rough == pytest.approx(0.0128, abs=1e-12)
    assert loosest - rough == pytest.approx(-0.0058, abs=1e-12)
    with pytest.raises(AssertionError, match="loosest band corner after smoothing"):
        press.check_press_fit_budget(
            {**budget, "interference_effective_min": loosest - rough}
        )


def test_press_land_symbol_lands_inside_the_land_with_its_reason() -> None:
    """The land's Ra 0.8 is attached to the Ø6 face inside the land, between
    the zone-start line and the zone diameter's dimension line; the symbol
    and its two-row reason stand above-left, clear of that line, the zone
    diameter's block and the stock diameter, and the leader's run (from the
    r15 seat's 6.4 mm shoulder) crosses the top outline east of the
    zone-start line, never across it."""
    sheet_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'surface_finish_by_key(SURFACE_FINISHES, "press_land")' in sheet_source
    assert "edge_xy=PRESS_LAND_FINISH_PICK" in sheet_source
    assert "leader_attach_xy=PRESS_LAND_FINISH_PICK" in sheet_source
    assert (
        "_add_finish_reason(\n        adapter, front, PRESS_LAND_CALLOUT, "
        "PRESS_LAND_REASON_XY," in sheet_source
    )
    assert sheet_source.index("PRESS_LAND_CALLOUT, PRESS_LAND_REASON_XY") > (
        sheet_source.index("edge_xy=PRESS_LAND_FINISH_PICK")
    )
    assert mg_magnifying_lever_spec.PRESS_LAND_CALLOUT == "MHA-MG-01\nPRESS LAND"

    start_x = drawing._PRESS_ZONE_START_X
    dim_line_x = drawing.REFERENCE_KEEP["PressZoneDia"][0]
    pick_x, pick_y = drawing.PRESS_LAND_FINISH_PICK
    # On the face (midway in the OD, as the seat's pick) inside the land,
    # >= 1 mm from the solid zone-start line and the diameter's line.
    assert pick_y == pytest.approx((drawing.FRONT_CENTER[1] + drawing._ROD_TOP_Y) / 2)
    assert start_x + 0.001 <= pick_x <= dim_line_x - 0.001
    assert pick_x < drawing._DOME_TANGENT_X
    # The symbol (root = its V's tip; r15 seat: shoulder 6.4 mm right, bar
    # 1.5 mm left, "Ra" text +5.1..+14.8 mm right and up to 7.1 mm high).
    sym_x, sym_y = drawing.PRESS_LAND_FINISH_SYMBOL
    shoulder_x = sym_x + 0.0064
    assert shoulder_x < pick_x and sym_y > drawing._ROD_TOP_Y
    crossing_x = pick_x - (pick_x - shoulder_x) * (drawing._ROD_TOP_Y - pick_y) / (
        sym_y - pick_y
    )
    assert crossing_x >= start_x + 0.0005
    # Its "Ra 0.8" ends >= 3 mm west of the diameter's line, whose shoulder
    # (y ~169.9 mm on r15) and block run east from it.
    assert sym_x + 0.0148 + 0.003 <= dim_line_x
    # The reason: a note's position is its top-left; its two rows straddle
    # the symbol's ink, ending >= 2 mm short of its bar.
    left, top = drawing.PRESS_LAND_REASON_XY
    rows = mg_magnifying_lever_spec.PRESS_LAND_CALLOUT.split("\n")
    right = left + 0.0301 / 10 * max(len(row) for row in rows)  # r15 "MHA-MG-02"
    bottom = top - (_TEXT_HEIGHT + (len(rows) - 1) * _ROW_PITCH)
    assert right + 0.002 <= sym_x - 0.0015
    assert bottom <= sym_y + 0.0071 / 2 <= top
    assert bottom > drawing._ROD_TOP_Y + 0.008
    # East of the stock diameter's "Ø6.0" row (it ends ~128 mm on r15).
    assert left > drawing.REFERENCE_KEEP["RodDia"][0] + 0.020

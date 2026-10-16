"""Offline contracts for the output fixture (MHA-MG-006): part, sheet, pose."""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_mg_output_fixture as part
import draw_mg_output_fixture as drawing
import mg_output_fixture_geom as geom
import mg_output_fixture_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_audit import LayoutAuditMode, audit_dump, audit_report
from _layout_geometry import Box, Segment as AuditSegment, segment_box_distance
from _printed_tolerance import printed_band_mm

SCRIPTS = Path(geom.__file__).resolve().parent


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/mg-output-fixture.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/mg-output-fixture.pdf")
    assert drawing.PNG.as_posix().endswith("/png/mg-output-fixture_drawing.png")
    assert (
        DRAWINGS_BY_NAME["mg_output_fixture"].script
        == Path(drawing.__file__).resolve()
    )


def test_sheet_prints_exactly_the_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked


def test_no_printed_dimension_carries_its_own_band() -> None:
    # r1 review: every explicit ±0.05 was a band the part's function never
    # asked for.  The places carry the title block's band (rule 3); the
    # groove's radius is a single MAX limit (rule 16); the drilled bore's
    # band is the DRILLED HOLES row.
    for retired in ("SYMMETRIC_BANDS", "ROD_BORE_DIA_BAND", "POSITION_TOLERANCE", "SIZE_TOLERANCE"):
        assert not hasattr(spec, retired), retired
    assert {
        name: places for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places != 2
    } == {"HexAf": 3, "GrooveRadius": 1, "RodBoreDia": 1}
    assert spec.SINGLE_LIMITS == {"GrooveRadius": ("GrooveProfile", 6)}
    assert part.SINGLE_LIMITS is spec.SINGLE_LIMITS
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "_single_limit(adapter, feature_name, dimension_name, tol_type)" in source
    assert "_drawing_tolerances" not in source and "_fit_deviations" not in source
    assert printed_band_mm(2) == 0.51
    assert 2.0 * spec.ROD_BORE_R_MAX == pytest.approx(5.3)
    assert spec.ROD_BORE_CALLOUT == "DRILL THRU"


def test_flats_and_overall_length_print_as_unbanded_references() -> None:
    # Machinist review: 9.525 at .XXX asked for a size the bar is bought at.
    # r1: the overall length closed a loop with the bore's two stations.
    assert spec.REFERENCE_DIMENSIONS == {"HexAf", "OverallLength"}
    assert spec.DRAWING_DIMENSIONS["HexProfile"] == {"HexAf"}
    assert spec.DRAWING_PRECISION_BY_NAME["HexAf"] == 3  # the exact 3/8 in
    assert geom.OVERALL_LENGTH == pytest.approx(geom.ROD_STATION + spec.BORE_STATION)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in source
    assert "set_reference_dimension(" in source
    assert "by_name = {**side_by_name, **end_by_name}" in source
    turned = ast.unparse(
        _function(ast.parse(Path(part.__file__).read_text(encoding="utf-8")), "_turned_profile")
    )
    # Driven in the part, so the sheet's (17.70) is the model's own sum.
    assert "_make_driven(adapter, overall, 'overall length')" in turned
    assert spec.STOCK_NOTE == "3/8 HEX BAR, FLATS AS SUPPLIED."


def _local_imports(module: Path) -> set[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module.split(".")[0])
    return names


def test_geometry_import_closure_carries_no_sheet_or_registry() -> None:
    """The assembly, the wire and the exporters import the shape: a sheet,
    a title-block or a registry edit must not re-key them."""
    seen: set[str] = set()
    pending = ["mg_output_fixture_geom"]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        path = SCRIPTS / f"{name}.py"
        if path.is_file():
            pending.extend(_local_imports(path))
    local = {name for name in seen if (SCRIPTS / f"{name}.py").is_file()}
    for name in local:
        assert not name.startswith(("_drawing", "_config", "draw_", "build_")), name
        # Private modelling contracts such as _hole_spec are not part sheets.
        assert not (name.endswith("_spec") and not name.startswith("_")), name
    assert not {"win32com", "pythoncom", "solidworks_mcp"} & seen


def _machine_offset(local: tuple[float, float, float], yaw_deg: float) -> tuple[float, float]:
    """(dx, dz) of a local point under the installed Ry(180 deg + yaw)."""
    theta = math.radians(180.0 + yaw_deg)
    x, _y, z = local
    return (
        x * math.cos(theta) + z * math.sin(theta),
        -x * math.sin(theta) + z * math.cos(theta),
    )


def test_installed_hook_sits_on_the_wire_start() -> None:
    dx, dz = _machine_offset(geom.HOOK_LOCAL, geom.FIXTURE_YAW_DEG)
    assert dz == pytest.approx(geom.HOOK_TARGET_Z - geom.VROD_Z, abs=1e-9)
    assert dx == pytest.approx(geom.HOOK_OFFSET_X, abs=1e-9)
    # The wire's centre in the groove root, on the +Z side, at the groove.
    x, y, z = geom.HOOK_LOCAL
    assert x == geom.GROOVE_X and y == 0.0 and z > 0.0
    assert math.hypot(y, z) == pytest.approx(
        geom.GROOVE_ROOT_DIA / 2.0 + geom.WIRE_DIA / 2.0 + geom.WIRE_CLEARANCE
    )
    # Option A1: the hook lies in the rod's own plane (dz = 0), on the bracket
    # side, and the run heads further from the rod, so the wire clears it.
    from mg_magnifying_vertical_rod_geom import ROD_DIA
    import vn_lever_wire_geom as wire

    assert geom.HOOK_TARGET_Z == geom.VROD_Z
    assert -geom.HOOK_OFFSET_X - ROD_DIA / 2.0 - geom.WIRE_DIA / 2.0 >= geom.WIRE_CLEARANCE
    assert wire.WIRE_END[0] < wire.WIRE_START[0]


def test_hook_point_is_authored_on_the_top_plane_where_the_geometry_puts_it() -> None:
    # Top-plane sketch (x, y) is model (X, -Z).
    x, y = part._hook_sketch_xy()
    assert (x, 0.0, -y) == geom.HOOK_LOCAL


def test_groove_runs_on_the_spigot_with_both_lips() -> None:
    low, high = geom.GROOVE_MOUTHS
    assert geom.SHOULDER_X < low < high < geom.SPIGOT_FACE_X
    assert geom.GROOVE_ROOT_DIA < geom.SPIGOT_DIA < geom.HEX_AF


def test_every_wall_holds_the_floor_and_each_under_the_target_is_stated() -> None:
    assert (spec.WALL_TARGET, spec.WALL_FLOOR) == (2.0, 1.5)
    for name, (nominal, worst) in spec.WALLS.items():
        assert worst <= nominal, name
        assert worst >= spec.WALL_FLOOR - 1e-9, (name, worst)
        if worst < spec.WALL_TARGET - 1e-9:
            stated = spec.STATED_WALL_MINS[name]
            assert spec.WALL_FLOOR <= stated <= spec.floor_2(worst), name
    assert {name: worst for name, (_n, worst) in spec.WALLS.items()} == pytest.approx({
        "rod bore to a flat": 2.0475,
        "rod bore to the free end": 1.7112,
        "rod bore to the shoulder": 2.2012,
        "groove lip to the spigot face": 1.64,
        "groove root over the thread major": 1.6710,
    }, abs=1e-4)
    assert spec.STATED_WALL_MINS == {
        "rod bore to a flat": 1.97,
        "rod bore to the free end": 1.71,
        "groove lip to the spigot face": 1.64,
        "groove root over the thread major": 1.67,
    }


def test_floor_2_never_rounds_a_min_up() -> None:
    assert spec.floor_2(2.0824999999999996) == 2.08
    assert spec.floor_2(2.0899999) == 2.08
    # The epsilon keeps a float a hair under an exact hundredth on it.
    assert spec.floor_2(1.97 - 1e-12) == 1.97
    assert spec.floor_2(1.9699) == 1.96


def test_bore_is_centred_and_the_stated_wall_is_the_named_shortfall() -> None:
    # Independent of the spec's arithmetic: the bore centred on the thinnest
    # stock (3/8 in less the 0.13 stock assumption) at its largest drilled Ø
    # (the title block's DRILLED HOLES +0.10/0).
    assert spec.HEX_STOCK_AF_BAND == 0.13
    smallest_af = 0.375 * 25.4 - 0.13
    largest_bore_r = (5.2 + 0.10) / 2.0
    worst = smallest_af / 2.0 - largest_bore_r
    assert worst == pytest.approx(2.0475, abs=1e-9)
    assert spec.WALLS[spec.BORE_WALL_NAME] == pytest.approx((2.1625, worst), abs=1e-9)
    # The 1.97 pending #1433 stays: under the target, over the floor, under
    # the centred worst wall by the centring it accepts.
    assert spec.BORE_WALL_STATED_MIN == 1.97
    assert spec.WALL_FLOOR <= spec.BORE_WALL_STATED_MIN < spec.WALL_TARGET
    assert spec.BORE_CENTRING_ACCEPTED == pytest.approx(worst - 1.97, abs=1e-9)
    # What it accepts off centre: the widest stock, the smallest bore.
    assert spec.BORE_OFFSET_MAX == pytest.approx(
        (0.375 * 25.4 + 0.13) / 2.0 - 2.6 - 1.97, abs=1e-9
    )
    assert spec.BORE_OFFSET_MAX == pytest.approx(0.2575, abs=1e-9)
    # The drill's run-off at the exit corner (0.10 start, 0.3 deg over the
    # corner radius) exceeds that centring: the MIN rejects such a part, for
    # the owner's ruling (#1433).
    wander = 0.10 + geom.HEX_CORNER_RADIUS * math.tan(math.radians(0.3))
    assert spec.BORE_WANDER == pytest.approx(wander, abs=1e-12)
    assert spec.BORE_WANDER > spec.BORE_CENTRING_ACCEPTED
    # The free-end wall: one .XX station, the drilled Ø, the run-off.
    assert spec.WALLS["rod bore to the free end"][1] == pytest.approx(
        5.00 - 0.51 - largest_bore_r - wander, abs=1e-9
    )
    assert spec.DRAWING_NOTES.splitlines() == [
        "3/8 HEX BAR, FLATS AS SUPPLIED.",
        "BORE TO FLAT WALL 1.97 MIN; BORE TO FREE END WALL 1.71 MIN.",
        "GROOVE TO FACE WALL 1.64 MIN; GROOVE ROOT TO THREAD WALL 1.67 MIN.",
        "FULL THREAD TO ROD BORE.",
    ]
    # Nothing locates the bore from a flat any longer: the hex sketch centres
    # it by equal flats.
    assert not hasattr(geom, "BORE_FROM_FLAT")
    for module in (part, drawing, spec):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "BoreFromFlat" not in source, module.__name__
    assert "await adapter.add_sketch_constraint(lines[1], lines[4], \"equal\")" in (
        Path(part.__file__).read_text(encoding="utf-8")
    )


def test_thumb_screw_tap_runs_axially_into_the_rod_bore() -> None:
    assert spec.TAP_SPEC is geom.TAP_SPEC
    assert geom.TAP_SPEC.kind == "tapped"
    assert geom.TAP_SPEC.size == "#4-40"
    # Blind, not up-to-next: the callout states both depths, never THRU.
    assert geom.TAP_SPEC.end == "blind"
    assert geom.TAP_SPEC.depth_mm == geom.TAP_DRILL_DEPTH == geom.SPIGOT_FACE_X
    assert geom.TAP_SPEC.overrides_mm == {"ThreadDepth": geom.TAP_LENGTH}
    # Full thread from the spigot face to where the tap's axis meets the bore.
    assert geom.TAP_LENGTH == pytest.approx(10.1, abs=1e-9)
    assert geom.TAP_LENGTH == pytest.approx(
        geom.OVERALL_LENGTH - geom.ROD_STATION - geom.ROD_BORE_DIA / 2.0, abs=1e-9
    )
    assert geom.TAP_DRILL_DIA < geom.ROD_BORE_DIA
    # Full thread from the face to the bore, well over 1.5D.
    assert geom.TAP_LENGTH >= 1.5 * geom.THREAD_MAJOR
    assert spec.TAP_PROCESS == "TAP INTO BORE"
    assert spec.TAP_DEPTH_PLACES == 1
    assert spec.TAP_CALLOUT_PRECISION == {"hw-tapdrldepth": 1, "hw-threaddepth": 1}


def test_a_bottoming_tap_reaches_full_thread_through_the_wall_and_stops_short() -> None:
    # Morse Cutting Tools #4-40 hand tap (catalogue 552474): usable length
    # LU 9/16 in on a 0.141 in shank (over the 0.112 in major, so the shank
    # stops at the spigot face and LU is the tap's whole reach); ICS gives
    # the bottoming chamfer as 1-2 threads.
    reach = 9.0 / 16.0 * 25.4
    pitch = 25.4 / 40.0
    assert spec.TAP_USABLE_LENGTH == pytest.approx(14.2875, abs=1e-9)
    assert spec.TAP_SHANK_DIA == pytest.approx(3.5814, abs=1e-9)
    assert spec.BOTTOMING_TAP_CHAMFER_THREADS == (1, 2)
    assert spec.BOTTOMING_TAP_LEAD == pytest.approx(2.0 * pitch, abs=1e-9)
    # Face to bore axis at the printed worst case: one .XX station, 12.70.
    face_to_axis_max, face_to_axis_min = 12.70 + 0.51, 12.70 - 0.51
    assert (spec.FACE_TO_BORE_AXIS_MAX, spec.FACE_TO_BORE_AXIS_MIN) == pytest.approx(
        (face_to_axis_max, face_to_axis_min), abs=1e-9
    )
    # The thread's widest reach off the bore axis: the library's metric basic
    # major Ø2.845, tap oversize and all the off-centre the stated wall accepts.
    assert spec.THREAD_MAJOR == 2.845
    reach_off_axis = 2.845 / 2.0 + 0.025 + 0.2575
    half_chord = math.sqrt(2.6**2 - reach_off_axis**2)
    deepest_wall = face_to_axis_max - half_chord
    assert spec.TAP_WALL_DEEPEST == pytest.approx(deepest_wall, abs=1e-9)
    assert spec.TAP_WALL_DEEPEST == pytest.approx(11.2471, abs=5e-4)
    assert spec.TAP_REACH_NEEDED == pytest.approx(deepest_wall + 2.0 * pitch, abs=1e-9)
    assert reach - spec.TAP_REACH_NEEDED == pytest.approx(1.7704, abs=5e-4)
    # On one part both walls move together: the tap stops anywhere in the
    # bore's chord less its lead.
    assert spec.FAR_WALL_NEAREST == pytest.approx(face_to_axis_min + half_chord, abs=1e-9)
    assert spec.TAP_STOP_WINDOW == pytest.approx(2.0 * half_chord - 2.0 * pitch, abs=1e-9)
    assert spec.TAP_STOP_WINDOW > 0.0
    # The plug tap the sheet asked for before (3-5 thread chamfer) cannot
    # reach full thread at the worst case: 11.247 + 3.175 = 14.42 > 14.29.
    assert deepest_wall + 5.0 * pitch > reach
    assert spec.TAP_EXTENT_NOTE in spec.DRAWING_NOTES.splitlines()
    for retired in ("PLUG_TAP_USABLE_LENGTH", "PLUG_TAP_LEAD", "TAP_TOOL_NOTE"):
        assert not hasattr(spec, retired), retired
    # The tap drill's full Ø clears the near wall; its point stops short of
    # the far one.
    assert spec.TAP_DRILL_NEAR_CLEAR > 0.0 and spec.TAP_DRILL_FAR_CLEAR > 0.0


def test_the_bore_datum_holds_the_screw_reach_and_the_rejected_datums_fail() -> None:
    from _mcmaster_91882a221 import PITCH, SHANK_DIA, SHANK_LEN
    from mg_magnifying_vertical_rod_geom import ROD_STOCK_DIA_LOW

    rod_min = geom.VROD_DIA - ROD_STOCK_DIA_LOW
    bore_r_max = (5.2 + 0.10) / 2.0
    # One .XX band from the spigot face to the bore axis.
    reach = (12.70 + 0.51) + bore_r_max - rod_min
    assert spec.SCREW_REACH_NEEDED == pytest.approx(reach, abs=1e-9)
    assert spec.SCREW_REACH_NEEDED == pytest.approx(10.91, abs=5e-3)
    assert SHANK_LEN == pytest.approx(7.0 / 16.0 * 25.4)
    assert spec.SCREW_REACH_MARGIN == pytest.approx(SHANK_LEN - reach, abs=1e-9)
    assert spec.SCREW_REACH_MARGIN > 0.0
    # r1's datums: the overall length from the free end less the rod station,
    # two .XX bands to the bore: the screw bottoms before it clamps the rod.
    stacked = (17.70 + 0.51) - (5.00 - 0.51) + bore_r_max - rod_min
    assert stacked == pytest.approx(11.42, abs=5e-3)
    assert stacked > SHANK_LEN
    # The bore from the face with the overall from the free end (the rod
    # station a reference) leaves the free-end wall under the floor.
    free_end_wall = (17.70 - 0.51) - (12.70 + 0.51) - bore_r_max
    assert free_end_wall == pytest.approx(1.33, abs=1e-9)
    assert free_end_wall < spec.WALL_FLOOR
    # Engagement at the shallowest bore: at least 1.5 D.
    engagement = (12.70 - 0.51) - bore_r_max - PITCH
    assert spec.ENGAGEMENT_WORST == pytest.approx(engagement, abs=1e-9)
    assert engagement >= 1.5 * SHANK_DIA


def test_the_groove_station_from_the_face_holds_the_face_lip() -> None:
    # One .XX band from the face to the groove centre, and the MAX radius.
    face_lip = (3.35 - 0.51) - 1.2
    assert spec.GROOVE_STATION == pytest.approx(3.35)
    assert spec.WALLS["groove lip to the spigot face"][1] == pytest.approx(face_lip, abs=1e-9)
    assert face_lip >= spec.WALL_FLOOR
    # From the free end instead (r1's 14.35) with the overall a reference:
    # three .XX bands to the face put the lip far under the floor.
    via_free_end = (12.70 - 0.51) + (5.00 - 0.51) - (14.35 + 0.51) - 1.2
    assert via_free_end < spec.WALL_FLOOR
    # The groove stays on the spigot: its shoulder-side mouth clears the hex
    # shoulder at the worst case (a step up to the hex, not a wall).
    clearance = (12.70 - 0.51) + (5.00 - 0.51) - (11.00 + 0.51) - (3.35 + 0.51 + 1.2)
    assert spec.GROOVE_SHOULDER_CLEARANCE == pytest.approx(clearance, abs=1e-9)
    assert clearance > 0.0
    # The wire stays in it at the smallest OD over the largest root.
    assert spec.GROOVE_DEPTH_MIN == pytest.approx(((9.00 - 0.51) - (7.00 + 0.51)) / 2.0)
    assert spec.GROOVE_DEPTH_MIN > geom.WIRE_DIA / 2.0


def test_the_groove_radius_is_a_max_and_the_title_block_x_row_would_thin_the_face_lip() -> None:
    assert spec.GROOVE_RADIUS_PLACES == 1 and spec.GROOVE_RADIUS_TOL_TYPE == 6
    assert spec.GROOVE_RADIUS_MAX == geom.GROOVE_RADIUS
    assert spec.GROOVE_HALF_OPENING_MAX == geom.GROOVE_RADIUS
    assert drawing.RADIUS_GLYPHS == len("R1.2 MAX")
    # A bare R1.2 at the title block's .X admits R2.0: across the printed
    # root and OD the mouth opens past 1.9 and the face lip falls under the
    # floor.
    r = 1.2 + printed_band_mm(1)
    half = max(
        spec.groove_half_opening(r, root, od)
        for root in (7.00 - 0.51, 7.00 + 0.51)
        for od in (9.00 - 0.51, 9.00 + 0.51)
    )
    assert (3.35 - 0.51) - half < spec.WALL_FLOOR
    assert (3.35 - 0.51) - r == pytest.approx(0.84)


def test_the_spigot_cleans_up_inside_the_thinnest_flats() -> None:
    # A route check, not a band: the shop turns Ø9.00 inside 9.395 flats.
    assert geom.SPIGOT_DIA < geom.HEX_AF - spec.HEX_STOCK_AF_BAND
    assert geom.HEX_AF - spec.HEX_STOCK_AF_BAND - geom.SPIGOT_DIA == pytest.approx(0.395)


def _code_strings(tree: ast.Module) -> list[str]:
    """Every string literal the module's code holds: docstrings are prose."""
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_the_rod_bore_ends_the_thread_and_its_depth_is_ref() -> None:
    # The native thread depth is the nominal wall on the tap's axis; the
    # callout brackets it as REF, so no .X band (10.1 +/-0.8 would admit 9.3)
    # governs the thread's extent: the rod bore does (the note).  Review09:
    # a bare 10.1 in the callout read as controlling while the note said REF.
    assert spec.TAP_EXTENT_NOTE == "FULL THREAD TO ROD BORE."
    assert "REF" not in spec.DRAWING_NOTES
    assert spec.TAP_EXTENT_NOTE in spec.DRAWING_NOTES.splitlines()
    assert geom.TAP_SPEC.overrides_mm["ThreadDepth"] == geom.TAP_LENGTH
    assert geom.TAP_LENGTH == pytest.approx(geom.SPIGOT_FACE_X - geom.ROD_BORE_DIA / 2.0)
    assert set(spec.TAP_CALLOUT_PRECISION) == {
        spec.TAP_DRILL_DEPTH_VARIABLE,
        spec.TAP_THREAD_DEPTH_VARIABLE,
    } == {"hw-tapdrldepth", "hw-threaddepth"}
    # The native depth stays model-owned: the brackets go round the variable
    # in the definition; no code string types the value.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hole_callout_precision(" in source
    printed = (f"{geom.TAP_LENGTH:.1f}", f"{geom.TAP_DRILL_DEPTH:.1f}")
    assert not [
        text for text in _code_strings(ast.parse(source)) if any(p in text for p in printed)
    ]


def _build_calls_in_order(names: set[str]) -> list[str]:
    """The named calls ``build`` makes, in source order."""
    build = _build_function(ast.parse(Path(drawing.__file__).read_text(encoding="utf-8")))
    calls = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and _call_name(node) in names
    ]
    return [_call_name(node) for node in sorted(calls, key=lambda n: (n.lineno, n.col_offset))]


def test_the_thread_depth_is_bracketed_between_the_callout_and_its_checks() -> None:
    # Bracketed before the precision write and the resolved-text proof, so
    # both run on the definition that prints.
    assert _build_calls_in_order(
        {
            "add_native_hole_callout",
            "_reference_thread_depth",
            "set_hole_callout_precision",
            "_check_tap_callout",
        }
    ) == [
        "add_native_hole_callout",
        "_reference_thread_depth",
        "set_hole_callout_precision",
        "_check_tap_callout",
    ]


# Retry09's definitions, as the resolved parts imply (prefix 5 carries the
# process and the thread row, callout-above 7 the drill row).
_RETRY09_DEFINITIONS = {
    5: "TAP INTO BORE <hw-thread> <HOLE-DEPTH> <hw-threaddepth>",
    6: "",
    7: "<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>",
    8: "",
}


def test_thread_depth_definition_gains_reference_brackets_only() -> None:
    updated = drawing.reference_thread_depth_definitions(dict(_RETRY09_DEFINITIONS))
    assert updated == {
        5: "TAP INTO BORE <hw-thread> <HOLE-DEPTH> (<hw-threaddepth>)",
        6: "",
        7: "<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>",
        8: "",
    }


@pytest.mark.parametrize(
    "definitions",
    [
        # Already bracketed: someone else's edit, not the native definition.
        {**_RETRY09_DEFINITIONS, 5: "TAP INTO BORE <hw-thread> <HOLE-DEPTH> (<hw-threaddepth>)"},
        # No thread depth to bracket.
        {**_RETRY09_DEFINITIONS, 5: "TAP INTO BORE <hw-thread>"},
        # Two thread depths: which one is the reference is a guess.
        {**_RETRY09_DEFINITIONS, 8: "<hw-threaddepth>"},
        # The controlling drill depth missing, or bracketed.
        {**_RETRY09_DEFINITIONS, 7: "<MOD-DIAM><hw-tapdrldia>"},
        {**_RETRY09_DEFINITIONS, 7: "<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH> (<hw-tapdrldepth>)"},
    ],
)
def test_thread_depth_definition_refuses_anything_but_one_bare_variable(
    definitions: dict[int, str],
) -> None:
    with pytest.raises(RuntimeError, match="expected one bare"):
        drawing.reference_thread_depth_definitions(definitions)


class _CalloutDisplay:
    """IDisplayDimension.GetText/SetText on a hole callout: definition part d
    (5-8) is written through part d - 4; ``persist`` False drops the write."""

    def __init__(self, definitions: dict[int, str], *, persist: bool = True) -> None:
        self.definitions = dict(definitions)
        self.persist = persist
        self.writes: list[tuple[int, str]] = []

    def GetText(self, part: int) -> str:
        return self.definitions[part]

    def SetText(self, part: int, text: str) -> None:
        self.writes.append((part, text))
        if self.persist:
            self.definitions[part + 4] = text


def test_reference_thread_depth_writes_one_definition_and_reads_all_back() -> None:
    display = _CalloutDisplay(_RETRY09_DEFINITIONS)
    drawing._reference_thread_depth(display)
    assert display.writes == [
        (1, "TAP INTO BORE <hw-thread> <HOLE-DEPTH> (<hw-threaddepth>)")
    ]
    assert display.definitions[7] == _RETRY09_DEFINITIONS[7]


def test_reference_thread_depth_fails_when_the_write_does_not_persist() -> None:
    with pytest.raises(RuntimeError, match="did not persist as REF"):
        drawing._reference_thread_depth(_CalloutDisplay(_RETRY09_DEFINITIONS, persist=False))


@pytest.mark.parametrize(
    ("resolved", "reads"),
    [
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> (10.1)",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            True,
        ),
        # Retry09's native reading (20261012T124257186Z), bracketed.
        (
            {
                1: "TAP INTO BORE 4-40 UNC - 2B <HOLE-DEPTH> (10.1)",
                2: "",
                3: "<MOD-DIAM> 2.26 <HOLE-DEPTH> 12.7",
                4: "",
            },
            True,
        ),
        # Retry09 as printed: a bare 10.1 reads as controlling (review09).
        (
            {
                1: "TAP INTO BORE 4-40 UNC - 2B <HOLE-DEPTH> 10.1",
                2: "",
                3: "<MOD-DIAM> 2.26 <HOLE-DEPTH> 12.7",
                4: "",
            },
            False,
        ),
        # The reference stated twice, once bare.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> (10.1) 10.1",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            False,
        ),
        # The controlling drill depth bracketed as if it were REF.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> (10.1)",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> (12.7)",
                3: "",
                4: "",
            },
            False,
        ),
        # The old ambiguous callout: THRU on both rows.
        (
            {
                1: "TAP TO BORE 4-40 UNC-2B THRU",
                2: "<MOD-DIAM>2.26 THRU",
                3: "",
                4: "",
            },
            False,
        ),
        # Two places on the thread depth asks for the .XX band.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> (10.10)",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            False,
        ),
        # The thread without its extent.
        (
            {
                1: "4-40 UNC-2B <HOLE-DEPTH> (10.1)",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            False,
        ),
        # The drill row without its depth.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> (10.1)",
                2: "<MOD-DIAM>2.26",
                3: "",
                4: "",
            },
            False,
        ),
        # A band on the REF thread depth.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> (10.1)<MOD-PM>0.8",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            False,
        ),
    ],
)
def test_tap_callout_states_its_depths_and_extent(
    resolved: dict[int, str], reads: bool
) -> None:
    assert drawing._tap_callout_resolved(resolved) is reads


def test_final_sheet_census_expects_no_tapped_hole_note_from_the_blind_tap() -> None:
    # Two passing runs of the up-to-next tap each swept one "#4-40 Tapped
    # Hole" note; retry08's blind tap, on the same views and imports, swept
    # none and failed the stale census of one.  The census is the tap's.
    assert drawing.AUTO_TAPPED_HOLE_NOTES == 0
    # The topology it was measured on: a blind tap no targeted import selects.
    assert geom.TAP_SPEC.end == "blind"
    assert set(spec.DRAWING_DIMENSIONS) == {
        "TurnedProfile",
        "GrooveProfile",
        "HexProfile",
        "RodBoreProfile",
    }
    build = _build_function(ast.parse(Path(drawing.__file__).read_text(encoding="utf-8")))
    finalizes = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and _call_name(node) == "finalize_drawing"
    ]
    assert len(finalizes) == 1
    keywords = {kw.arg: ast.unparse(kw.value) for kw in finalizes[0].keywords}
    # A literal count is what went stale: the call names the measured census,
    # and the sweep stays on so a note that comes back fails it.
    assert keywords["expected_redundant_notes"] == "AUTO_TAPPED_HOLE_NOTES"
    assert keywords["redundant_note_substrings"] == "(TAPPED_HOLE_NOTE,)"
    # The sweep (a case-blind substring) reaches the note SolidWorks pins and
    # never the native callout that states the tap.
    note = drawing.TAPPED_HOLE_NOTE.lower()
    assert note in f"{geom.TAP_SPEC.size} Tapped Hole".lower()
    native_callout = (
        "TAP INTO BORE 4-40 UNC - 2B <HOLE-DEPTH> (10.1)\n"
        "<MOD-DIAM> 2.26 <HOLE-DEPTH> 12.7"
    )
    assert note not in native_callout.lower()


def _slice_area(x: float) -> float:
    """The part's cross-section at axial station ``x``, from the shapes alone."""
    af, corner = geom.HEX_AF, geom.HEX_CORNER_RADIUS
    bore_r = geom.ROD_BORE_DIA / 2.0
    drill_r = geom.TAP_DRILL_DIA / 2.0
    if x < geom.SHOULDER_X:
        area = math.sqrt(3.0) / 2.0 * af**2
    else:
        spigot_r = geom.SPIGOT_DIA / 2.0
        area = math.pi * spigot_r**2
        dx = x - geom.GROOVE_X
        if abs(dx) < geom.GROOVE_RADIUS:
            cut_r = geom.GROOVE_CENTRE_R - math.sqrt(geom.GROOVE_RADIUS**2 - dx**2)
            if cut_r < spigot_r:
                area -= math.pi * (spigot_r**2 - cut_r**2)
    band = math.sqrt(bore_r**2 - x**2) if abs(x) < bore_r else 0.0
    if band:
        # The bore along Y cuts the band |z| <= band through the hex, whose
        # chord along Y at height z is 2(corner - |z|/sqrt(3)).
        area -= 2.0 * (2.0 * corner * band - band**2 / math.sqrt(3.0))
    if x > 0.0:
        # The tap drill, outside what the bore already took.
        if band >= drill_r:
            pass
        elif band:
            area -= 2.0 * (
                drill_r**2 * math.acos(band / drill_r)
                - band * math.sqrt(drill_r**2 - band**2)
            )
        else:
            area -= math.pi * drill_r**2
    return area


def test_analytic_volume_matches_the_part_sliced_along_its_axis() -> None:
    """The builder's volume guards assert ``part.V_TOTAL``; a part that lost
    a feature (the groove, the bore or the tap) misses it by far more than
    the guard's 0.5 %."""
    steps = 40000
    width = (geom.SPIGOT_FACE_X - geom.FREE_END_X) / steps
    sliced = sum(
        _slice_area(geom.FREE_END_X + (index + 0.5) * width) * width
        for index in range(steps)
    )
    assert part.V_TOTAL == pytest.approx(sliced, rel=2e-3)
    smallest_feature = min(part.V_GROOVE, part.V_BORE, part.V_TAP)
    assert smallest_feature > 0.005 * part.V_TOTAL


def test_sheet_reads_places_and_limits_from_the_part() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "assert_imported_precision" in source
    assert "set_dimension_precision" not in source
    # The sheet reads the part's single limit back; it never writes a band.
    for write in ("SetValues(", "Tolerance.Type =", "tolerance.Type =", "_drawing_tolerances"):
        assert write not in source, write
    for gdt in ("gtol", "datum"):
        assert gdt not in source.lower(), gdt


# A dimension's text centre sits ~2.8 mm over its line (2026-10-12 farm
# sheet: HexLength's text at 209.05 mm over its line at 206.27 mm).
_TEXT_OVER_LINE = 0.0028
_TEXT_HEIGHT = 0.0035


def _dia_text_box(name: str) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of a turned Ø text centred on its keep: retry09's
    Ø9.00 broke its line 2.8 mm either side of the keep's y."""
    x, y = drawing.SIDE_KEEP[name]
    half = drawing.TURNED_DIA_TEXT_HALF_WIDTH
    return (x - half, y - _TEXT_OVER_LINE, x + half, y + _TEXT_OVER_LINE)


# A dimension arrow's length on the sheet (retry09 audit: 3.556 mm).
_ARROW = 0.003556


def test_turned_diameters_stack_right_of_the_face_smaller_inside() -> None:
    # Review09 finding 8: the root Ø's text hung under the view, so its line
    # ran out of the groove into a shoulder that read as an axial length.
    face_x = drawing._side_x(geom.SPIGOT_FACE_X)
    root_x, root_y = drawing.SIDE_KEEP["GrooveRootDia"]
    spigot_x, spigot_y = drawing.SIDE_KEEP["SpigotDia"]
    root_box, spigot_box = _dia_text_box("GrooveRootDia"), _dia_text_box("SpigotDia")
    # Both clear the face's witnesses; the smaller stands inside, so its
    # extension lines end short of the larger's line.
    assert root_box[0] > face_x + 0.003
    assert face_x < root_x < spigot_x
    # Each text breaks its own dimension line between the arrows: the root's
    # inside the groove's roots, the spigot's inside its OD; neither hangs
    # off the view.
    low, high = drawing.GROOVE_ROOT_SHEET_YS
    assert (low, high) == pytest.approx(
        (drawing._side_y(-geom.GROOVE_ROOT_DIA / 2.0), drawing._side_y(geom.GROOVE_ROOT_DIA / 2.0))
    )
    assert low + _ARROW < root_box[1] and root_box[3] < high - _ARROW
    od_low = drawing._side_y(-geom.SPIGOT_DIA / 2.0)
    od_high = drawing._side_y(geom.SPIGOT_DIA / 2.0)
    assert od_low + _ARROW < spigot_box[1] and spigot_box[3] < od_high - _ARROW
    assert drawing._SIDE_BOTTOM < root_y < drawing._SIDE_TOP
    # Neither text crosses the other's dimension line, and the two stagger a
    # text height apart so they never read as one row.
    assert spigot_box[0] > root_x + 0.003
    assert root_box[2] < spigot_x - 0.003
    assert spigot_box[1] - root_box[3] >= _TEXT_HEIGHT
    # The spigot's text clears the rotated end view's left-standing AF line.
    assert spigot_box[2] < drawing.END_KEEP["HexAf"][0] - 0.005
    # Overall length stays under the view.  The radius text reads low, right
    # of the face, its shoulder under the spigot mouth.
    assert drawing.SIDE_KEEP["OverallLength"][1] < drawing._SIDE_BOTTOM
    assert drawing.SIDE_KEEP["GrooveRadius"] == drawing.RADIUS_TEXT_XY
    assert drawing.RADIUS_TEXT_XY[1] - drawing.RADIUS_SHOULDER_DROP < od_high


def _function(tree: ast.Module, name: str) -> ast.AST:
    (found,) = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    return found


def test_groove_root_dia_is_a_doubled_distance_to_the_root_point() -> None:
    # Finding 8 is presentation only: the part already dimensions the root as
    # a diametric linear dimension from the groove's axis to the root point,
    # the start of the face-side arc (GROOVE_X, root_v).
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    profile = _function(tree, "_groove_profile")
    calls = [
        node
        for node in ast.walk(profile)
        if isinstance(node, ast.Call) and _call_name(node) == "add_diametric_linear_dimension"
    ]
    assert [ast.unparse(node) for node in calls] == [
        "add_diametric_linear_dimension(adapter, axis, f'{toward_face}.start', "
        "(GROOVE_X, -GROOVE_CENTRE_R), 'GrooveRootDia')"
    ]
    source = ast.unparse(profile)
    assert "root_v = GROOVE_CENTRE_R - GROOVE_RADIUS" in source
    assert "add_arc(GROOVE_X, GROOVE_CENTRE_R, GROOVE_X, root_v, GROOVE_X, crown_v)" in source
    assert geom.GROOVE_CENTRE_R - geom.GROOVE_RADIUS == pytest.approx(geom.GROOVE_ROOT_DIA / 2.0)
    helper = (SCRIPTS / "_drawing_dimension_insert.py").read_text(encoding="utf-8")
    assert "15,  # swDimensionType_e.swDiametricLinearDimension" in helper
    # swDimensionType_e: the sheet's import read the part's diametric linear
    # dimension back as swDiameterDimension (6) with Diametric True (retry10,
    # farm 20261012T170144152Z); the authoring type (15) is the other doubled
    # distance.  Neither the single-distance radial linear (14) nor a plain
    # linear is one.
    assert drawing._DOUBLED_DISTANCE_TYPES == {
        6: "swDiameterDimension",
        15: "swDiametricLinearDimension",
    }
    assert drawing.GROOVE_ROOT_VALUE_SLOP_MM == 1e-5


def test_groove_root_dia_is_proved_after_the_side_view_settles() -> None:
    assert _build_calls_in_order(
        {"curate_view_dimensions", "_check_tap_callout", "_prove_groove_root_diameter"}
    ) == [
        "curate_view_dimensions",
        "curate_view_dimensions",
        "_check_tap_callout",
        "_prove_groove_root_diameter",
    ]


def _nested_root_ink() -> list:
    """The root Ø's ink as SolidWorks draws a nested doubled distance: an
    extension line from each root, 1 mm off the groove, 1 mm past the line;
    the line root to root, broken at the text."""
    line_x, text_y = drawing.SIDE_KEEP["GrooveRootDia"]
    low, high = drawing.GROOVE_ROOT_SHEET_YS
    start = drawing._side_x(geom.GROOVE_X) + 0.001
    return [
        ((start, low), (line_x + 0.001, low)),
        ((start, high), (line_x + 0.001, high)),
        ((line_x, low), (line_x, text_y - _TEXT_OVER_LINE)),
        ((line_x, high), (line_x, text_y + _TEXT_OVER_LINE)),
    ]


# Retry09's GrooveRootDia ink, verbatim from its layout audit
# (20261012T124257186Z): degenerate extensions at the roots, the line down
# the groove, its 20 mm leg out of it and the 30 mm shoulder under the text.
_RETRY09_ROOT_INK = [
    ((0.146, 0.166), (0.146, 0.166)),
    ((0.146, 0.194), (0.146, 0.194)),
    ((0.1171778, 0.1461451), (0.147, 0.1461451)),
    ((0.147, 0.1461451), (0.147, 0.166)),
    ((0.147, 0.166), (0.147, 0.194)),
]


def test_nested_root_ink_reads_across_the_groove() -> None:
    line_x = drawing.SIDE_KEEP["GrooveRootDia"][0]
    assert drawing._groove_root_ink_problem(_nested_root_ink(), line_x) is None


@pytest.mark.parametrize(
    ("case", "problem"),
    [
        # Retry09's line against its own keep, shoulder aside: the line
        # leaves the groove.
        ("retry09-leg", "not root to root"),
        # Retry09 whole against the nested keep: its shoulder is stray ink.
        ("retry09", "neither its dimension line"),
        # A shoulder hung off the nested line.
        ("shoulder", "neither its dimension line"),
        ("drop-extension", "no extension line from the root"),
        ("drop-line", "no dimension line"),
    ],
)
def test_groove_root_ink_off_the_groove_fails(case: str, problem: str) -> None:
    keep_x, text_y = drawing.SIDE_KEEP["GrooveRootDia"]
    nested = _nested_root_ink()
    segments, line_x = {
        "retry09-leg": ([s for i, s in enumerate(_RETRY09_ROOT_INK) if i != 2], 0.147),
        "retry09": (_RETRY09_ROOT_INK, keep_x),
        "shoulder": ([*nested, ((keep_x, text_y), (keep_x + 0.03, text_y))], keep_x),
        "drop-extension": (nested[1:], keep_x),
        "drop-line": (nested[:2], keep_x),
    }[case]
    found = drawing._groove_root_ink_problem(segments, line_x)
    assert found is not None and problem in found


class _RootDimension:
    """IDimension: SystemValue is metres."""

    def __init__(self, value_mm: float) -> None:
        self.SystemValue = value_mm / 1000.0


class _RootDisplay:
    """IDisplayDimension: Type2, Diametric and DisplayAsLinear are properties;
    GetDimension2 is a method taking the dimension index."""

    def __init__(self, kind: int, diametric: bool, value_mm: float) -> None:
        self.Type2 = kind
        self.Diametric = diametric
        self.DisplayAsLinear = False
        self.dimension = _RootDimension(value_mm)

    def GetDimension2(self, index: int) -> _RootDimension:
        assert index == 0
        return self.dimension


class _RootAnnotation:
    """IAnnotation.GetSpecificAnnotation: a method returning the display."""

    def __init__(self, display: _RootDisplay) -> None:
        self.display = display

    def GetSpecificAnnotation(self) -> _RootDisplay:
        return self.display


def _prove_root(
    monkeypatch: pytest.MonkeyPatch,
    kind: int,
    diametric: bool,
    segments: list,
    value_mm: float = geom.GROOVE_ROOT_DIA,
) -> list[str]:
    bound: list[str] = []

    def early_bound(obj: object, interface: str) -> object:
        bound.append(interface)
        return obj

    annotation = _RootAnnotation(_RootDisplay(kind, diametric, value_mm))
    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    monkeypatch.setattr(
        drawing, "dimension_segments", lambda read: segments if read is annotation else []
    )
    drawing._prove_groove_root_diameter(annotation)
    return bound


@pytest.mark.parametrize("kind", [6, 15])
def test_groove_root_proof_passes_a_nested_doubled_distance(
    monkeypatch: pytest.MonkeyPatch, kind: int
) -> None:
    # Type 6 is retry10's native readback; the type, then the model value,
    # then the ink are read, in that order.
    bound = _prove_root(monkeypatch, kind, True, _nested_root_ink())
    assert bound == ["IAnnotation", "IDisplayDimension", "IDimension"]


@pytest.mark.parametrize(
    ("kind", "diametric"),
    [(2, True), (11, True), (12, True), (5, True), (14, True), (6, False), (15, False)],
)
def test_groove_root_proof_refuses_a_plain_or_single_distance(
    monkeypatch: pytest.MonkeyPatch, kind: int, diametric: bool
) -> None:
    with pytest.raises(RuntimeError, match="not the part's doubled distance"):
        _prove_root(monkeypatch, kind, diametric, _nested_root_ink())


@pytest.mark.parametrize(
    "value_mm",
    [
        geom.GROOVE_ROOT_DIA / 2.0,  # the single distance, axis to root
        geom.GROOVE_RADIUS,  # the groove's radius
        geom.SPIGOT_DIA,  # the other turned Ø
        geom.GROOVE_ROOT_DIA + 2e-5,  # just outside the import's exactness
    ],
)
def test_groove_root_proof_refuses_another_value(
    monkeypatch: pytest.MonkeyPatch, value_mm: float
) -> None:
    # A circle's Ø reads the same type pair, so the model value is read too.
    with pytest.raises(RuntimeError, match="not the groove root Ø"):
        _prove_root(monkeypatch, 6, True, _nested_root_ink(), value_mm)


def test_groove_root_proof_refuses_retry09s_ink(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="does not print across the groove"):
        _prove_root(monkeypatch, 6, True, _RETRY09_ROOT_INK)


def test_bore_callout_reads_over_the_hex_between_its_witnesses() -> None:
    # The free end carries witnesses over its whole height, so the bore's Ø
    # reads over the hex, inside the hex length's span, under its line.
    x, y = drawing.SIDE_KEEP["RodBoreDia"]
    half_width = drawing.BORE_CALLOUT_HALF_WIDTH
    half_height = drawing.BORE_CALLOUT_HALF_HEIGHT
    assert x - half_width > drawing._side_x(geom.FREE_END_X) + 0.005
    assert x + half_width < drawing._side_x(geom.SHOULDER_X) - 0.005
    assert y - half_height > drawing._SIDE_TOP + 0.003
    hex_line = drawing.SIDE_KEEP["HexLength"][1] - _TEXT_OVER_LINE
    assert hex_line > y + half_height + _TEXT_HEIGHT
    # The groove's station, from the spigot face, reads over the spigot,
    # clear of the hex length's span; the bore's two stations share a row
    # under the view.
    station_x = drawing.SIDE_KEEP["GrooveStation"][0]
    assert station_x - 0.005 > drawing._side_x(geom.SHOULDER_X) + 0.003
    assert station_x == pytest.approx(
        drawing._side_x((geom.GROOVE_X + geom.SPIGOT_FACE_X) / 2.0)
    )
    assert drawing.SIDE_KEEP["RodStation"][1] == drawing.SIDE_KEEP["BoreStation"][1]
    assert drawing.SIDE_KEEP["OverallLength"][1] < drawing.SIDE_KEEP["BoreStation"][1] - 0.010


def test_end_view_flats_read_vertically_left_of_the_hex_clear_of_the_tap() -> None:
    assert drawing._END_HALF_HEIGHT == pytest.approx(geom.HEX_AF * drawing._S / 2000.0)
    assert drawing._END_HALF_WIDTH == pytest.approx(geom.HEX_CORNER_RADIUS * drawing._S / 1000.0)
    assert set(drawing.END_KEEP) == {"HexAf"}
    af_x, af_y = drawing.END_KEEP["HexAf"]
    assert af_x < drawing.END_CENTER[0] - drawing._END_HALF_WIDTH - 0.010
    assert af_y == drawing.END_CENTER[1]
    text_left = drawing.TAP_CALLOUT_XY[0] - drawing._TAP_CALLOUT_HALF_WIDTH
    assert text_left > drawing.END_CENTER[0] + drawing._END_HALF_WIDTH + 0.005
    assert drawing.TAP_CALLOUT_XY[1] - drawing._TAP_CALLOUT_SHOULDER_DROP > af_y


# Calls that add a centre mark; a comment naming one adds nothing.
_MARK_ADDING_CALLS = frozenset(
    {"auto_center_marks", "AutoInsertCenterMarks2", "InsertCenterMark3", "InsertCenterMark2"}
)


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else ""


def _arg_names(call: ast.Call) -> list[str]:
    return [arg.id if isinstance(arg, ast.Name) else "" for arg in call.args]


def _end_view_mark_calls(tree: ast.AST) -> list[tuple[str, list[str]]]:
    """Every call that would add a centre mark to the end view: the drawing
    document's inserts, which mark whatever view is active or selected, and
    ``auto_center_marks`` handed ``end``."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in _MARK_ADDING_CALLS:
            continue
        args = _arg_names(node)
        if name == "auto_center_marks" and "end" not in args:
            continue
        found.append((name, args))
    return found


def _build_function(tree: ast.Module) -> ast.AsyncFunctionDef:
    builds = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    ]
    assert len(builds) == 1
    return builds[0]


def test_end_view_tap_keeps_the_template_centre_mark_alone() -> None:
    # The template marks the tap as the view is placed: AutoInsertCenterMarks2
    # (2026-10-12 farm sheet, DetailItem347/350) and InsertCenterMark3 (run05)
    # each printed a second mark over it.
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    assert _end_view_mark_calls(tree) == []
    build = _build_function(tree)
    proofs = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and _call_name(node) == "_prove_tap_centre_mark"
    ]
    assert [_arg_names(call) for call in proofs] == [
        ["adapter", "end", "tap_drill"], ["adapter", "end", "tap_drill"]
    ]
    callouts = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call) and _call_name(node) == "add_native_hole_callout"
    ]
    assert len(callouts) == 1
    edges = [kw.value for kw in callouts[0].keywords if kw.arg == "edge"]
    assert len(edges) == 1
    assert isinstance(edges[0], ast.Name) and edges[0].id == "tap_drill"
    # The side view's bore still takes its mark (it has no template one).
    side_marks = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Call)
        and _call_name(node) == "auto_center_marks"
        and _arg_names(node)[:2] == ["adapter", "side"]
    ]
    assert len(side_marks) == 1


@pytest.mark.parametrize(
    ("source", "found"),
    [
        (
            "def f(ddoc):\n    ddoc.InsertCenterMark3(2, False, False)\n",
            [("InsertCenterMark3", ["", "", ""])],
        ),
        (
            "def f(ddoc):\n    ddoc.AutoInsertCenterMarks2(7, 11, True)\n",
            [("AutoInsertCenterMarks2", ["", "", ""])],
        ),
        (
            "def f(adapter, end):\n    auto_center_marks(adapter, end, holes=True)\n",
            [("auto_center_marks", ["adapter", "end"])],
        ),
        ("def f(adapter, side):\n    auto_center_marks(adapter, side)\n", []),
        ("# ddoc.InsertCenterMark3(2, False, False)\n'InsertCenterMark3'\n", []),
    ],
)
def test_end_view_mark_scanner_reads_calls_not_comments(
    source: str, found: list[tuple[str, list[str]]]
) -> None:
    assert _end_view_mark_calls(ast.parse(source)) == found


_AXIS_ON_SHEET = (0.262, 0.180)
_DRILL_CENTRE = (0.0, 0.0011, -0.0023)


class _MarkData:
    """IDisplayData: GetLineCount and GetLineAtIndex2 are methods, each line
    (colour, line type, unused, unused, start xyz, end xyz)."""

    def __init__(self, lines: list[tuple[float, float, float, float]]) -> None:
        self._lines = lines

    def GetLineCount(self) -> int:
        return len(self._lines)

    def GetLineAtIndex2(self, index: int) -> tuple[float, ...]:
        x0, y0, x1, y1 = self._lines[index]
        return (0.0, 0.0, 0.0, 0.0, x0, y0, 0.0, x1, y1, 0.0)


class _MarkAnnotation:
    """IAnnotation.GetDisplayData: a method returning a dispatch, or None."""

    def __init__(self, data: _MarkData | None) -> None:
        self._data = data

    def GetDisplayData(self) -> _MarkData | None:
        return self._data


def _single_mark(dx: float = 0.0, dy: float = 0.0) -> _MarkAnnotation:
    """A single mark's ink: 10 mm arms and extended lines 20..28 mm out."""
    x, y = _AXIS_ON_SHEET[0] + dx, _AXIS_ON_SHEET[1] + dy
    return _MarkAnnotation(
        _MarkData(
            [
                (x - 0.010, y, x + 0.010, y),
                (x, y - 0.010, x, y + 0.010),
                (x, y - 0.028, x, y - 0.020),
                (x, y + 0.020, x, y + 0.028),
                (x - 0.028, y, x - 0.020, y),
                (x + 0.020, y, x + 0.028, y),
            ]
        )
    )


class _MarkView:
    """IView.GetAnnotationsByType: a method returning a VARIANT array, or
    None when the view carries none of the type."""

    def __init__(self, marks: tuple | None) -> None:
        self._marks = marks
        self.types: list[int] = []

    def GetAnnotationsByType(self, annotation_type: int) -> tuple | None:
        self.types.append(annotation_type)
        return self._marks


class _DrillCurve:
    """ICurve.CircleParams: a property, (centre xyz, axis xyz, radius)."""

    def __init__(self, params: tuple | None) -> None:
        self.CircleParams = params


class _DrillEdge:
    """IEdge.GetCurve: a method returning a dispatch, or None."""

    def __init__(self, curve: _DrillCurve | None) -> None:
        self._curve = curve

    def GetCurve(self) -> _DrillCurve | None:
        return self._curve


class _NoInsertDrawing:
    """The drawing document: the sheet must never add a centre mark."""

    def InsertCenterMark3(self, *_args: object) -> object:
        raise AssertionError("the sheet added a centre mark")

    def AutoInsertCenterMarks2(self, *_args: object) -> object:
        raise AssertionError("the sheet added a centre mark")


_DRILL_CIRCLE = (*_DRILL_CENTRE, 1.0, 0.0, 0.0, 0.00113)


def _prove_mark(
    monkeypatch: pytest.MonkeyPatch,
    marks: tuple | None,
    *,
    edge: _DrillEdge | None = None,
) -> _MarkView:
    view = _MarkView(marks)
    bound: list[str] = []

    def early_bound(obj: object, interface: str) -> object:
        bound.append(interface)
        return obj

    def project(adapter, projected_view, xyz, *, label):
        assert projected_view is view
        assert tuple(xyz) == _DRILL_CENTRE, label
        return _AXIS_ON_SHEET

    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    drawing._prove_tap_centre_mark(
        SimpleNamespace(currentModel=_NoInsertDrawing()),
        view,
        edge or _DrillEdge(_DrillCurve(_DRILL_CIRCLE)),
    )
    assert {"IEdge", "ICurve", "IView"} <= set(bound)
    return view


@pytest.mark.parametrize(("dx", "dy"), [(0.0, 0.0), (0.0004, 0.0), (0.0, -0.0004)])
def test_tap_centre_mark_on_the_drill_axis_passes_untouched(
    monkeypatch: pytest.MonkeyPatch, dx: float, dy: float
) -> None:
    view = _prove_mark(monkeypatch, (_single_mark(dx, dy),))
    assert view.types == [13]


@pytest.mark.parametrize(
    ("marks", "found"),
    [(None, 0), ((), 0), ((_single_mark(), _single_mark()), 2)],
)
def test_tap_centre_mark_refuses_any_census_but_one(
    monkeypatch: pytest.MonkeyPatch, marks: tuple | None, found: int
) -> None:
    with pytest.raises(
        RuntimeError, match=f"expected one tap centre mark on the end view, found {found}"
    ):
        _prove_mark(monkeypatch, marks)


@pytest.mark.parametrize(("dx", "dy"), [(0.0008, 0.0), (0.0, 0.0006), (0.0045, 0.0)])
def test_tap_centre_mark_off_the_drill_axis_fails(
    monkeypatch: pytest.MonkeyPatch, dx: float, dy: float
) -> None:
    with pytest.raises(RuntimeError, match="mm off the tap axis"):
        _prove_mark(monkeypatch, (_single_mark(dx, dy),))


@pytest.mark.parametrize(
    ("marks", "edge", "message"),
    [
        ((_MarkAnnotation(None),), None, "has no display data"),
        ((_MarkAnnotation(_MarkData([])),), None, "draws no line"),
        ((_single_mark(),), _DrillEdge(None), "has no curve"),
        ((_single_mark(),), _DrillEdge(_DrillCurve(None)), "reports no circle centre"),
        ((_single_mark(),), _DrillEdge(_DrillCurve(())), "reports no circle centre"),
        (
            (_single_mark(),),
            _DrillEdge(_DrillCurve(_DRILL_CENTRE[:2])),
            "reports no circle centre",
        ),
    ],
)
def test_tap_centre_mark_unmeasured_fails(
    monkeypatch: pytest.MonkeyPatch,
    marks: tuple,
    edge: _DrillEdge | None,
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        _prove_mark(monkeypatch, marks, edge=edge)


def test_notes_are_short() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert len(lines) == 4
    assert max(map(len, lines)) <= 68
    assert spec.TAP_EXTENT_NOTE in lines
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "Manufacturing Notes" in part._SAVED_DRAWING_PROPERTIES
    import _config

    config = _config.parts("mg-output-fixture")
    assert config["material"] == "C36000 free-cutting brass"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_wall_notes_are_model_owned_and_state_each_min_as_a_fact() -> None:
    assert part.DRAWING_NOTES is spec.DRAWING_NOTES
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '{"Manufacturing Notes": DRAWING_NOTES}' in source
    assert spec.BORE_WALL_NOTE == (
        "BORE TO FLAT WALL 1.97 MIN; BORE TO FREE END WALL 1.71 MIN."
    )
    assert spec.GROOVE_WALL_NOTE == (
        "GROOVE TO FACE WALL 1.64 MIN; GROOVE ROOT TO THREAD WALL 1.67 MIN."
    )
    # r1: the corner-to-corner bore is drawn (the end view's centreline
    # through the corners), never noted; no note names a method.
    for word in ("CENTRED", "CORNER", "REAM", "DRILL", "HOLD ON", "PLUG"):
        assert word not in spec.DRAWING_NOTES, word
    for retired in ("BORE_TOOL_NOTE", "TAP_TOOL_NOTE"):
        assert not hasattr(spec, retired), retired


def test_projection_precedes_import_and_all_native_ink_proofs_follow_rebuild() -> None:
    assert _build_calls_in_order({
        "_project_end_view", "curate_view_dimensions", "_add_rod_bore_axis",
        "_place_groove_radius", "_prove_end_stock_reference", "_prove_rod_bore_axis",
        "_prove_groove_radius", "_prove_groove_root_diameter",
    }) == [
        "_project_end_view", "curate_view_dimensions", "curate_view_dimensions",
        "_add_rod_bore_axis", "_place_groove_radius", "_prove_end_stock_reference",
        "_prove_rod_bore_axis", "_prove_groove_radius", "_prove_groove_root_diameter",
    ]


class _ProjectedView:
    """IView.Angle/Position properties and BOOL SetViewPosition, no COM."""

    def __init__(
        self, kind: str, angle: float = 0.0, *, turn: bool = True,
        move: bool = True, move_result: object = True, handed: float = 1.0,
    ) -> None:
        self.kind = kind
        self._angle = angle
        self.turn = turn
        self.move = move
        self.move_result = move_result
        self.handed = handed
        self.Position = [0.260, 0.190]
        self.offset = (0.003, -0.002)
        self.writes: list[float] = []

    @property
    def Angle(self) -> float:
        return self._angle

    @Angle.setter
    def Angle(self, value: float) -> None:
        self.writes.append(value)
        if self.turn:
            self._angle = value

    def SetViewPosition(self, position: list[float], move_children: bool) -> object:
        assert move_children is False
        assert len(position) == 2
        if self.move:
            self.Position = list(position)
        return self.move_result

    def project(self, xyz: tuple[float, float, float]) -> tuple[float, float]:
        x, y, z = xyz
        u, v = (x, -z) if self.kind == "top" else (-z, self.handed * y)
        u, v = u * drawing._S + self.offset[0], v * drawing._S + self.offset[1]
        c, s = math.cos(self.Angle), math.sin(self.Angle)
        return self.Position[0] + u * c - v * s, self.Position[1] + u * s + v * c


def _projection_fakes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    rebuilds: list[str] = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: list(values))
    monkeypatch.setattr(
        drawing, "model_point_in_view",
        lambda adapter, view, xyz, *, label: view.project(xyz),
    )
    monkeypatch.setattr(
        drawing, "rebuild_drawing", lambda adapter, *, label: rebuilds.append(label)
    )
    return rebuilds


@pytest.mark.parametrize("initial", [0.0, math.pi / 2.0, -math.pi / 2.0, 0.37])
def test_end_turn_is_derived_from_axes_and_origin_is_pinned(
    monkeypatch: pytest.MonkeyPatch, initial: float
) -> None:
    rebuilds = _projection_fakes(monkeypatch)
    front, end = _ProjectedView("top"), _ProjectedView("right", initial)
    front.Position = list(drawing.SIDE_CENTER)
    drawing._project_end_view(object(), front, end)
    origin = end.project((0.0, 0.0, 0.0))
    assert origin == pytest.approx((drawing.END_CENTER[0], front.project((0.0, 0.0, 0.0))[1]))
    z = end.project((0.0, 0.0, 0.001))
    y = end.project((0.0, 0.001, 0.0))
    assert (z[0] - origin[0], z[1] - origin[1]) == pytest.approx((0.0, -0.004))
    assert (y[0] - origin[0], y[1] - origin[1]) == pytest.approx((-0.004, 0.0))
    assert rebuilds == ["turn fixture end view", "pin fixture end view"]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"turn": False}, "end \\+Z"),
        ({"handed": -1.0}, "end \\+Y"),
        ({"move": False}, "does not share front origin height"),
        ({"move_result": False}, "failed to pin"),
        ({"move_result": None}, "failed to pin"),
        ({"move_result": 1}, "failed to pin"),
    ],
)
def test_end_projection_refuses_ignored_turn_mirror_move_and_nonbool_success(
    monkeypatch: pytest.MonkeyPatch, options: dict, message: str
) -> None:
    _projection_fakes(monkeypatch)
    with pytest.raises(RuntimeError, match=message):
        drawing._project_end_view(object(), _ProjectedView("top"), _ProjectedView("right", **options))


def _end_flat_points() -> tuple[tuple[float, float], tuple[float, float]]:
    x, y = drawing.END_CENTER
    return (
        (x - drawing._END_HALF_WIDTH / 2.0, y + drawing._END_HALF_HEIGHT),
        (x + drawing._END_HALF_WIDTH / 2.0, y - drawing._END_HALF_HEIGHT),
    )


def _vertical_af_ink() -> list:
    x = drawing.END_KEEP["HexAf"][0]
    top, bottom = _end_flat_points()
    return [
        ((x, bottom[1]), (x, top[1])),
        ((top[0] - drawing.EXTENSION_START_GAP, top[1]), (x - 0.001, top[1])),
        ((bottom[0] - drawing.EXTENSION_START_GAP, bottom[1]), (x - 0.001, bottom[1])),
    ]


def test_rotated_end_stock_af_ink_stands_across_flats_not_corners() -> None:
    assert drawing._end_af_ink_problem(_vertical_af_ink(), _end_flat_points()) is None


@pytest.mark.parametrize("case", ["empty", "missing-flat", "ac-height", "horizontal", "short-witness"])
def test_rotated_end_stock_af_refuses_wrong_frame_or_unwitnessed_flats(case: str) -> None:
    ink = _vertical_af_ink()
    if case == "empty":
        ink = []
    elif case == "missing-flat":
        ink = ink[:-1]
    elif case == "ac-height":
        x = drawing.END_KEEP["HexAf"][0]
        y = drawing.END_CENTER[1]
        ink[0] = ((x, y - drawing._END_HALF_WIDTH), (x, y + drawing._END_HALF_WIDTH))
    elif case == "horizontal":
        x, y = drawing.END_CENTER
        ink[0] = ((x - drawing._END_HALF_HEIGHT, y), (x + drawing._END_HALF_HEIGHT, y))
    else:
        (x0, y0), p1 = ink[1]
        ink[1] = ((x0 - 0.004, y0), p1)
    assert drawing._end_af_ink_problem(ink, _end_flat_points()) is not None


class _NativeDisplay:
    """IDisplayDimension properties, methods and metre-valued IDimension."""

    def __init__(
        self, name: str, feature: str, value_mm: float, *, kind: int = 5,
        diametric: bool = False, arc_persists: bool = True,
        gap_results: dict[int, object] | None = None, tol_type: int = 6,
    ) -> None:
        self.dimension = SimpleNamespace(
            FullName=f"{name}@{feature}@mg-output-fixture.SLDPRT",
            SystemValue=value_mm / 1000.0,
            Tolerance=SimpleNamespace(Type=tol_type),
        )
        self.Type2 = kind
        self.Diametric = diametric
        self._arc = True
        self.arc_persists = arc_persists
        self.gap_results = {0: True, 1: True, **(gap_results or {})}
        self.gaps: list[tuple[int, bool, float]] = []
        self.data: object | None = None

    @property
    def ArcExtensionLineOrOppositeSide(self) -> bool:
        return self._arc

    @ArcExtensionLineOrOppositeSide.setter
    def ArcExtensionLineOrOppositeSide(self, value: bool) -> None:
        assert type(value) is bool
        if self.arc_persists:
            self._arc = value

    def GetDimension2(self, index: int) -> SimpleNamespace:
        assert index == 0
        return self.dimension

    def SetWitnessLineGap(self, index: int, use_doc: bool, gap: float) -> object:
        assert type(index) is int and index in (0, 1)
        assert use_doc is False
        assert type(gap) is float
        self.gaps.append((index, use_doc, gap))
        return self.gap_results[index]

    def GetDisplayData(self) -> object | None:
        return self.data


def _radial_display(**options) -> _NativeDisplay:
    return _NativeDisplay("GrooveRadius", "GrooveProfile", geom.GROOVE_RADIUS, **options)


def _station_display(**options) -> _NativeDisplay:
    return _NativeDisplay("GrooveStation", "GrooveProfile", spec.GROOVE_STATION, **options)


def _place(display: _NativeDisplay, station: _NativeDisplay | None = None) -> None:
    drawing._place_groove_radius(
        object(), _RootAnnotation(display), _RootAnnotation(station or _station_display())
    )


def test_native_radius_style_and_only_named_witness_gaps_are_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rebuilds = _projection_fakes(monkeypatch)
    radius, station = _radial_display(), _station_display()
    _place(radius, station)
    assert radius.ArcExtensionLineOrOppositeSide is False
    assert radius.gaps == []
    # The centre-side witness 3 mm off the arc centre; the face-side one
    # (dimensioned from the face's point on the axis) from 1 mm above the
    # face's top corner, so it never runs down the face.
    assert station.gaps == [
        (1, False, drawing.GROOVE_STATION_GAP),
        (0, False, drawing.GROOVE_STATION_FACE_GAP),
    ]
    assert drawing.GROOVE_STATION_FACE_GAP == pytest.approx(
        geom.SPIGOT_DIA / 2.0 * drawing._S / 1000.0 + drawing.EXTENSION_START_GAP
    )
    assert drawing.EXTENSION_START_GAP == 0.001
    assert rebuilds == ["place fixture material-arc radius"]


@pytest.mark.parametrize("result", [False, None, 1])
@pytest.mark.parametrize(("index", "side"), [(1, "centre-side"), (0, "face-side")])
def test_station_witness_gaps_require_native_bool_success(
    monkeypatch: pytest.MonkeyPatch, result: object, index: int, side: str
) -> None:
    _projection_fakes(monkeypatch)
    with pytest.raises(RuntimeError, match=f"refused its {side} witness gap"):
        _place(_radial_display(), _station_display(gap_results={index: result}))


@pytest.mark.parametrize("options", [{"kind": 6}, {"diametric": True}, {"arc_persists": False}])
def test_native_radius_style_refuses_nonradius_or_ignored_false_property(
    monkeypatch: pytest.MonkeyPatch, options: dict,
) -> None:
    _projection_fakes(monkeypatch)
    with pytest.raises(RuntimeError):
        _place(_radial_display(**options))


@pytest.mark.parametrize(
    ("name", "feature", "value"),
    [
        ("OtherRadius", "GrooveProfile", geom.GROOVE_RADIUS),
        ("GrooveRadius", "OtherSketch", geom.GROOVE_RADIUS),
        ("GrooveRadius", "GrooveProfile", geom.GROOVE_RADIUS + 2e-5),
    ],
)
def test_native_radius_identity_refuses_equal_ink_from_another_model_dimension(
    monkeypatch: pytest.MonkeyPatch, name: str, feature: str, value: float
) -> None:
    _projection_fakes(monkeypatch)
    annotation = _RootAnnotation(_NativeDisplay(name, feature, value))
    with pytest.raises(RuntimeError, match="wrong model dimension"):
        drawing._model_display(annotation, "GrooveRadius", "GrooveProfile", geom.GROOVE_RADIUS)


def test_station_witness_ids_follow_the_builders_reference_order() -> None:
    # Witness 0 is the dimension's first reference (the face on the axis),
    # witness 1 its second (the arc centre).
    profile = ast.unparse(
        _function(ast.parse(Path(part.__file__).read_text(encoding="utf-8")), "_groove_profile")
    )
    assert "dimension_between(adapter, f'{axis}.end', f'{toward_free_end}.center'" in profile


# Native15 audit (20261013T091530503Z): printed glyphs, not the wider COM row.
# "R1.20 ±0.05" (11 glyphs) printed 24.16 mm wide, centred on its keep, from
# 1.84 mm under to 1.72 mm over it; the full shoulder ran from 15.28 mm left
# of and 2.78 mm under the keep to 1.50 mm past the text's right end.
_NATIVE15_RADIUS_KEEP = (0.1724, 0.1988)
# What the part's single limit prints (the sheet only sizes it).
_RADIUS_TEXT = "R1.2 MAX"
_NATIVE15_RADIUS_TEXT_BOX = Box(0.1604289, 0.1969558, 0.1845905, 0.2005212)
_NATIVE15_SPIGOT_TOP_WITNESS = ((0.1614, 0.198), (0.2003, 0.198))
_NATIVE15_GLYPH = (_NATIVE15_RADIUS_TEXT_BOX.xmax - _NATIVE15_RADIUS_TEXT_BOX.xmin) / 11
_NATIVE15_SHOULDER_OVERRUN = 0.1860889 - _NATIVE15_RADIUS_TEXT_BOX.xmax
_GROOVE_CENTRE = (drawing._side_x(geom.GROOVE_X), drawing._side_y(geom.GROOVE_CENTRE_R))
_FACE_ON_AXIS = (drawing._side_x(geom.SPIGOT_FACE_X), drawing.SIDE_CENTER[1])
_SHEET_RADIUS = geom.GROOVE_RADIUS * drawing._S / 1000.0


def _proposed_radius_text_box() -> Box:
    """R1.2 MAX at native15's glyph pitch and height, centred on the keep."""
    x, y = drawing.RADIUS_TEXT_XY
    half = len(_RADIUS_TEXT) * _NATIVE15_GLYPH / 2.0
    old = _NATIVE15_RADIUS_TEXT_BOX
    return Box(
        x - half,
        y + old.ymin - _NATIVE15_RADIUS_KEEP[1],
        x + half,
        y + old.ymax - _NATIVE15_RADIUS_KEEP[1],
    )


def _audit_line(stroke: tuple) -> AuditSegment:
    (x0, y0), (x1, y1) = stroke
    return AuditSegment(x0, y0, x1, y1, "ext-line")


def _proposed_extension_lines() -> dict[str, list]:
    """Every extension line the proposed side view draws near the radius
    text, from the model and the keeps (1 mm start gaps, 1 mm overrun)."""
    face_x, axis_y = _FACE_ON_AXIS
    od_low, od_high = drawing._side_y(-geom.SPIGOT_DIA / 2.0), drawing._side_y(geom.SPIGOT_DIA / 2.0)
    root_low, root_high = drawing.GROOVE_ROOT_SHEET_YS
    root_x = drawing.SIDE_KEEP["GrooveRootDia"][0]
    spigot_x = drawing.SIDE_KEEP["SpigotDia"][0]
    station_y = drawing.SIDE_KEEP["GrooveStation"][1] - _TEXT_OVER_LINE + 0.001
    under_y = drawing.SIDE_KEEP["BoreStation"][1] - _TEXT_OVER_LINE - 0.001
    overall_y = drawing.SIDE_KEEP["OverallLength"][1] - _TEXT_OVER_LINE - 0.001
    gap = drawing.EXTENSION_START_GAP
    return {
        "SpigotDia": [
            ((face_x + gap, od_low), (spigot_x + gap, od_low)),
            ((face_x + gap, od_high), (spigot_x + gap, od_high)),
        ],
        "GrooveRootDia": [
            ((_GROOVE_CENTRE[0] + gap, root_low), (root_x + gap, root_low)),
            ((_GROOVE_CENTRE[0] + gap, root_high), (root_x + gap, root_high)),
        ],
        "GrooveStation": [
            ((face_x, axis_y + drawing.GROOVE_STATION_FACE_GAP), (face_x, station_y)),
            (
                (_GROOVE_CENTRE[0], _GROOVE_CENTRE[1] + drawing.GROOVE_STATION_GAP),
                (_GROOVE_CENTRE[0], station_y),
            ),
        ],
        "BoreStation": [((face_x, axis_y - gap), (face_x, under_y))],
        "OverallLength": [((face_x, axis_y - gap), (face_x, overall_y))],
    }


def test_radius_text_reads_low_in_open_air_between_the_face_and_the_root_dia() -> None:
    # r1 review: the shelf ran along the spigot Ø's extension at the OD.
    box = _proposed_radius_text_box()
    face_x, axis_y = _FACE_ON_AXIS
    assert drawing.RADIUS_GLYPHS == len(_RADIUS_TEXT)
    assert drawing.SIDE_KEEP["GrooveRadius"] == drawing.RADIUS_TEXT_XY
    # Right of the face, under the root Ø's upper extension, over the axis,
    # left of the root Ø's dimension line.
    assert box.xmin > face_x + 0.003
    assert box.ymax < drawing.GROOVE_ROOT_SHEET_YS[1] - 0.003
    assert box.ymin > axis_y + 0.005
    assert box.xmax < drawing.SIDE_KEEP["GrooveRootDia"][0] - 0.005
    # The estimate the layout used is the wider of the two glyph pitches.
    assert drawing.RADIUS_TEXT_HALF_WIDTH >= (box.xmax - box.xmin) / 2.0
    extensions = _proposed_extension_lines()
    distances = {
        name: min(segment_box_distance(_audit_line(stroke), box) for stroke in strokes)
        for name, strokes in extensions.items()
    }
    assert min(distances.values()) >= 0.003
    assert min(distances, key=distances.get) == "GrooveRootDia"


def _radius_ink(
    elbow: tuple[float, float], *, overrun: float = _NATIVE15_SHOULDER_OVERRUN
) -> tuple[list, tuple[float, float]]:
    """Native-style radius ink for an elbow: the radial line from the arc
    centre to the tip, on to the elbow, and the full shoulder from the elbow
    to past the text's right end."""
    run = math.dist(elbow, _GROOVE_CENTRE)
    tip = tuple(
        c + (e - c) * _SHEET_RADIUS / run for e, c in zip(elbow, _GROOVE_CENTRE)
    )
    box = _proposed_radius_text_box()
    shoulder = (elbow, (box.xmax + overrun, elbow[1]))
    return [(_GROOVE_CENTRE, tip), (tip, elbow), shoulder], tip


def _station_ink() -> list:
    top = drawing.SIDE_KEEP["GrooveStation"][1] - _TEXT_OVER_LINE + 0.001
    return [
        (
            (_GROOVE_CENTRE[0], _GROOVE_CENTRE[1] + drawing.GROOVE_STATION_GAP),
            (_GROOVE_CENTRE[0], top),
        ),
        (
            (_FACE_ON_AXIS[0], _FACE_ON_AXIS[1] + drawing.GROOVE_STATION_FACE_GAP),
            (_FACE_ON_AXIS[0], top),
        ),
        ((_FACE_ON_AXIS[0], top - 0.001), (_GROOVE_CENTRE[0], top - 0.001)),
    ]


def _material_radius_ink() -> tuple[list, tuple[float, float], list, tuple[float, float]]:
    ink, tip = _radius_ink(drawing.RADIUS_ELBOW_XY)
    return ink, tip, _station_ink(), _GROOVE_CENTRE


def _root_line_x() -> float:
    return drawing.SIDE_KEEP["GrooveRootDia"][0]


def test_predicted_radius_leader_lands_on_the_face_side_material_arc() -> None:
    ink, tip, station, centre = _material_radius_ink()
    assert tip == pytest.approx(drawing.RADIUS_PREDICTED_TIP_XY)
    assert math.dist(tip, centre) == pytest.approx(_SHEET_RADIUS)
    assert centre[0] < tip[0] < centre[0] + geom.GROOVE_HALF_OPENING * drawing._S / 1000.0
    assert drawing.GROOVE_ROOT_SHEET_YS[1] < tip[1] < drawing._side_y(geom.SPIGOT_DIA / 2.0)
    # The elbow is 2 mm right of the face, 5.5 mm over the axis; the shoulder
    # sits between the axis and the root Ø's upper extension line.
    assert drawing.RADIUS_ELBOW_XY == pytest.approx(
        (_FACE_ON_AXIS[0] + 0.002, _FACE_ON_AXIS[1] + 0.0055)
    )
    assert drawing._groove_radius_ink_problem(ink, tip, station, centre, _FACE_ON_AXIS) is None
    assert drawing._radius_leader_ink_problem(ink, tip, centre, _root_line_x()) is None
    assert drawing.GROOVE_STATION_GAP == 0.003
    assert drawing.RADIUS_STATION_CLEARANCE == 0.002
    assert drawing.RADIUS_INK_SLOP == 0.0004


@pytest.mark.parametrize("dx_mm", [-3.0, -1.4, 0.0, 3.4, 5.0])
def test_radius_leader_holds_wherever_solidworks_runs_the_elbow(dx_mm: float) -> None:
    # The run-in is an estimate for R1.2 MAX: at native15's 15.28 mm the
    # elbow lands 3.4 mm right of the prediction, and the leader still lands
    # on the material arc, radial, short of the root Ø's line.
    elbow = (drawing.RADIUS_ELBOW_XY[0] + dx_mm / 1000.0, drawing.RADIUS_ELBOW_XY[1])
    ink, tip = _radius_ink(elbow)
    centre = _GROOVE_CENTRE
    assert drawing._groove_radius_ink_problem(
        ink, tip, _station_ink(), centre, _FACE_ON_AXIS
    ) is None
    assert drawing._radius_leader_ink_problem(ink, tip, centre, _root_line_x()) is None


def test_radius_leader_accepts_a_leader_drawn_from_the_elbow_alone() -> None:
    ink, tip, _station, centre = _material_radius_ink()
    assert drawing._radius_leader_ink_problem(ink[1:], tip, centre, _root_line_x()) is None
    reversed_ink = [stroke[::-1] for stroke in reversed(ink)]
    assert drawing._radius_leader_ink_problem(reversed_ink, tip, centre, _root_line_x()) is None
    # Zero-length records print nothing.
    assert drawing._radius_leader_ink_problem(
        [*ink, ((0.0, 0.0), (0.0, 0.0))], tip, centre, _root_line_x()
    ) is None


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no-shoulder", "no unique horizontal shoulder"),
        ("two-shoulders", "no unique horizontal shoulder"),
        ("no-leader", "no radial leader"),
        ("jogged-leader", "not on the radial line"),
        ("detached-shoulder", "does not run right"),
        ("shoulder-runs-left", "does not run right"),
        # r1's shelf: along the spigot Ø's extension at the OD.
        ("shelf-at-the-od", "not between the axis and the root"),
        ("shoulder-on-the-axis", "not between the axis and the root"),
        ("into-the-root-dia-line", "reaches the root Ø's dimension line"),
    ],
)
def test_radius_leader_refuses_bent_detached_or_crowded_ink(case: str, message: str) -> None:
    ink, tip, _station, centre = _material_radius_ink()
    elbow = ink[1][1]
    if case == "no-shoulder":
        ink.pop()
    elif case == "two-shoulders":
        ink.append(((elbow[0], elbow[1] + 0.001), (elbow[0] + 0.01, elbow[1] + 0.001)))
    elif case == "no-leader":
        ink = ink[2:]
    elif case == "jogged-leader":
        joint = (elbow[0] - 0.0007, elbow[1])
        ink[1] = (tip, joint)
        ink.insert(2, (joint, (elbow[0], elbow[1] + 0.0007)))
    elif case == "detached-shoulder":
        ink[2] = ((elbow[0] + 0.001, elbow[1]), ink[2][1])
    elif case == "shoulder-runs-left":
        ink[2] = (elbow, (elbow[0] - 0.02, elbow[1]))
    elif case == "shelf-at-the-od":
        ink, tip = _radius_ink((elbow[0], drawing._side_y(geom.SPIGOT_DIA / 2.0)))
    elif case == "shoulder-on-the-axis":
        ink, tip = _radius_ink((elbow[0] + 0.004, _FACE_ON_AXIS[1] + 0.001))
    else:
        ink, tip = _radius_ink(elbow, overrun=0.008)
    problem = drawing._radius_leader_ink_problem(ink, tip, centre, _root_line_x())
    assert problem is not None and message in problem


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("retry12-arrow", "not on the face-side material arc"),
        ("opposite-arc", "not on the face-side material arc"),
        ("off-circle", "not on the face-side material arc"),
        ("empty", "no attached leader ink"),
        ("disconnected", "no attached leader ink"),
        ("missing-centre-witness", "no unique witness at the groove arc centre"),
        ("stale-centre-gap", "groove arc centre witness gap did not reach"),
        ("near-foot", "not clear of the station's groove arc centre witness"),
        ("crossing", "not clear of the station's groove arc centre witness"),
        ("missing-face-witness", "no unique witness at the spigot face"),
        ("face-witness-down-the-face", "spigot face witness gap did not reach"),
        ("crossing-face-witness", "not clear of the station's spigot face witness"),
    ],
)
def test_radius_ink_refuses_extension_air_detachment_and_station_ambiguity(
    case: str, message: str
) -> None:
    ink, tip, station, centre = _material_radius_ink()
    if case == "retry12-arrow":
        tip = (centre[0] + 0.00454, centre[1] + 0.00156)  # native12: past the mouth
    elif case == "opposite-arc":
        tip = (2.0 * centre[0] - tip[0], tip[1])
    elif case == "off-circle":
        tip = (tip[0] + 0.001, tip[1])
    elif case == "empty":
        ink = []
    elif case == "disconnected":
        ink = [((0.170, 0.185), (0.180, 0.185))]
    elif case == "missing-centre-witness":
        station.pop(0)
    elif case == "stale-centre-gap":
        station[0] = ((centre[0], centre[1] + 0.001), station[0][1])
    elif case == "near-foot":
        ink.append((centre, (centre[0], centre[1] + 0.0015)))
    elif case == "crossing":
        ink.append((centre, (centre[0], centre[1] + 0.004)))
    elif case == "missing-face-witness":
        station.pop(1)
    elif case == "face-witness-down-the-face":
        station[1] = (
            (_FACE_ON_AXIS[0], _FACE_ON_AXIS[1] + drawing.EXTENSION_START_GAP),
            station[1][1],
        )
    else:
        y = _FACE_ON_AXIS[1] + drawing.GROOVE_STATION_FACE_GAP + 0.003
        ink.append(((_FACE_ON_AXIS[0] - 0.002, y), (_FACE_ON_AXIS[0] + 0.002, y)))
    problem = drawing._groove_radius_ink_problem(ink, tip, station, centre, _FACE_ON_AXIS)
    assert problem is not None and message in problem


def _native15_radius_spigot_dump(*, proposed: bool = False) -> dict:
    """Replay native15's actual COM rows, PDF glyph boxes and both Ø9
    witnesses, or the proposed layout's, built from the model and keeps."""

    def line(stroke: tuple, *, z: float = 0.0004) -> list:
        (x0, y0), (x1, y1) = stroke
        return [0.0, 0.0, 0.0, 0.0, x0, y0, z, x1, y1, z]

    if proposed:
        keep = drawing.RADIUS_TEXT_XY
        radius_ink, tip, _station, centre = _material_radius_ink()
        box = _proposed_radius_text_box()
        radius_text, radius_glyphs = f" {_RADIUS_TEXT} ", _RADIUS_TEXT.replace(" ", "")
        spigot_x = drawing.SIDE_KEEP["SpigotDia"][0]
        spigot_y = drawing.SIDE_KEEP["SpigotDia"][1]
        spigot_extensions = _proposed_extension_lines()["SpigotDia"]
        spigot_value = " 9.00 "
    else:
        keep = _NATIVE15_RADIUS_KEEP
        centre = (0.147, 0.1988)
        tip = (0.1516289, 0.1975297)
        radius_ink = [
            (tip, (0.1571236, 0.1960219)),
            (centre, tip),
            ((0.1571236, 0.1960219), (0.1860889, 0.1960219)),
        ]
        box = _NATIVE15_RADIUS_TEXT_BOX
        radius_text, radius_glyphs = " R1.20 ±0.05 ", "R1.20±0.05"
        spigot_x, spigot_y = 0.1993, 0.185
        spigot_extensions = [((0.1614, 0.162), (0.2003, 0.162)), _NATIVE15_SPIGOT_TOP_WITNESS]
        spigot_value = "9.00 ±0.05 "
    od_low, od_high = spigot_extensions[0][0][1], spigot_extensions[1][0][1]
    direction = tuple((tip[i] - centre[i]) / math.dist(tip, centre) for i in range(2))
    radius = {
        "type": 4, "name": "GrooveRadius", "visible": 1, "owner_type": 0,
        "pos": [*keep, 0.0004],
        "display": {
            "lines": [line(stroke) for stroke in radius_ink],
            "arrows": [[*tip, 0.0004, *direction, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, -1.0]],
            "texts": [{
                "t": radius_text, "pos": [box.xmin - 0.0015, radius_ink[-1][0][1], 0.0004],
                "h": 0.0035, "ref": 1, "ang": 0.0, "w": box.xmax - box.xmin + 0.003,
            }],
        },
        "dim": {"hole_callout": False},
    }
    spigot = {
        "type": 4, "name": "SpigotDia", "visible": 1, "owner_type": 0,
        "pos": [spigot_x, spigot_y, -0.0004],
        "display": {
            "lines": [line(stroke, z=-0.0004) for stroke in [
                *spigot_extensions,
                ((spigot_x, od_low), (spigot_x, spigot_y - 0.0028)),
                ((spigot_x, od_high), (spigot_x, spigot_y + 0.0028)),
            ]],
            "arrows": [
                [spigot_x, od_low, -0.0004, 0.0, 1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
                [spigot_x, od_high, -0.0004, 0.0, -1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
            ],
            "texts": [
                {"t": " ", "pos": [spigot_x - 0.0149, spigot_y - 0.0027514, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0012931},
                {"t": "<MOD-DIAM>", "pos": [spigot_x - 0.013618, spigot_y - 0.0028049, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0052784},
                {"t": spigot_value, "pos": [spigot_x - 0.0083396, spigot_y - 0.0027514, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0232507},
            ],
        },
        "dim": {"hole_callout": False},
    }
    spigot_glyphs = (
        ["9.00", spigot_x - 0.0045, spigot_y - 0.0018175, spigot_x + 0.0045, spigot_y + 0.0017479]
        if proposed
        else ["9.00±0.05", 0.1911891, 0.1831825, 0.2127127, 0.1867479]
    )
    return {
        "schema": 1, "stem": drawing.PART_STEM, "sheet": "Sheet1",
        "width": 0.4318, "height": 0.2794,
        "zone": {"left": 0.0127, "right": 0.0127, "bottom": 0.0127, "top": 0.0127},
        "title_block": [0.216, 0.0, 0.4318, 0.066],
        "views": [{
            "name": "Drawing View1", "type": 7, "orientation": "*Top", "pictorial": False,
            "outline": [0.084012, 0.155362, 0.165988, 0.204638],
            "annotations": [radius, spigot],
        }],
        "sheet_annotations": [], "tables": [], "read_errors": {},
        "ink": {"spans": [
            [radius_glyphs, box.xmin, box.ymin, box.xmax, box.ymax],
            spigot_glyphs,
        ], "strokes": []},
    }


def _write_fixture_audit(tmp_path: Path, dump: dict) -> tuple[Path, dict]:
    content, _gating = audit_report(drawing.PART_STEM, LayoutAuditMode.REPORT, [dump])
    report = tmp_path / f"{drawing.PART_STEM}.json"
    report.write_text(json.dumps(content), encoding="utf-8")
    return report, content


def test_real_text_crossing_is_not_waived_by_a_report_severity_label(tmp_path: Path) -> None:
    report, content = _write_fixture_audit(tmp_path, _native15_radius_spigot_dump())
    (crossing,) = [finding for finding in content["findings"] if finding["kind"] == "text-on-line"]
    crossing["severity"] = "advisory"
    content["summary"]["gating"] -= 1
    report.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(RuntimeError, match="text-on-line"):
        drawing._enforce_fixture_text_on_line(report)


def test_native15_actual_radius_text_crossing_fails_the_local_report_gate(tmp_path: Path) -> None:
    dump = _native15_radius_spigot_dump()
    findings = audit_dump(dump)
    (crossing,) = [finding for finding in findings if finding.kind == "text-on-line"]
    assert crossing.a.startswith("dim GrooveRadius ")
    assert crossing.b.startswith("dim SpigotDia ")
    assert "'s ext-line (161.4,198.0)->(200.3,198.0)mm" in crossing.detail
    assert crossing.extra["overlap_mm"] == pytest.approx(23.1905)
    report, content = _write_fixture_audit(tmp_path, dump)
    assert content["mode"] == "report"
    with pytest.raises(RuntimeError, match="text-on-line.*\\n.*GrooveRadius.*SpigotDia"):
        drawing._enforce_fixture_text_on_line(report)


def test_proposed_layout_passes_the_same_gate_without_waiving_view_edge_false_positive(
    tmp_path: Path,
) -> None:
    report, content = _write_fixture_audit(tmp_path, _native15_radius_spigot_dump(proposed=True))
    assert not any(finding["kind"] == "text-on-line" for finding in content["findings"])
    assert any(finding["kind"] == "view-edges-missing" for finding in content["findings"])
    drawing._enforce_fixture_text_on_line(report)


@pytest.mark.parametrize("sheet", ["Sheet1", "AnotherSheet"])
def test_local_text_gate_refuses_unrelated_dimension_names_and_text_on_any_sheet(
    tmp_path: Path, sheet: str,
) -> None:
    dump = _native15_radius_spigot_dump()
    dump["sheet"] = sheet
    target, source = dump["views"][0]["annotations"]
    target["name"] = "UnrelatedWidth"
    target["display"]["texts"][0]["t"] = " 42.00 "
    dump["ink"]["spans"][0][0] = "42.00"
    source["name"] = "CounterboreDepth"
    report, content = _write_fixture_audit(tmp_path, dump)
    (crossing,) = [finding for finding in content["findings"] if finding["kind"] == "text-on-line"]
    assert crossing["sheet"] == sheet
    assert "UnrelatedWidth" in crossing["a"] and "CounterboreDepth" in crossing["b"]
    with pytest.raises(RuntimeError, match="UnrelatedWidth.*CounterboreDepth"):
        drawing._enforce_fixture_text_on_line(report)


@pytest.mark.parametrize("case", [
    "missing-file", "invalid-json", "not-object", "schema", "stem", "mode",
    "missing-findings", "findings-type", "finding-type", "kind-type", "detail-type",
    "finding-stem", "finding-sheet", "finding-severity", "sheets-type", "empty-sheets",
    "sheet-type", "sheet-stem", "sheet-name", "duplicate-sheet", "summary-type",
    "missing-counts", "counts-type", "counts-value", "count-mismatch", "sheet-count",
    "gating-count", "bool-schema", "bool-count", "bool-sheet-count", "bool-gating-count",
])
def test_local_text_gate_fails_loud_on_missing_malformed_or_incomplete_reports(
    tmp_path: Path, case: str,
) -> None:
    report, content = _write_fixture_audit(tmp_path, _native15_radius_spigot_dump())
    if case == "missing-file":
        report.unlink()
    elif case == "invalid-json":
        report.write_text("{", encoding="utf-8")
    else:
        if case == "not-object":
            content = []
        elif case in ("schema", "bool-schema"):
            content["schema"] = True if case == "bool-schema" else 99
        elif case in ("stem", "mode"):
            content[case] = "unrelated"
        elif case == "missing-findings":
            content.pop("findings")
        elif case == "findings-type":
            content["findings"] = {}
        elif case == "finding-type":
            content["findings"][0] = None
        elif case in ("kind-type", "detail-type"):
            content["findings"][0][case.removesuffix("-type")] = None
        elif case.startswith("finding-"):
            content["findings"][0][case.removeprefix("finding-")] = "unrelated"
        elif case == "sheets-type":
            content["sheets"] = {}
        elif case == "empty-sheets":
            content["sheets"] = []
        elif case == "sheet-type":
            content["sheets"][0] = None
        elif case == "sheet-stem":
            content["sheets"][0]["stem"] = "unrelated"
        elif case == "sheet-name":
            content["sheets"][0]["sheet"] = None
        elif case == "duplicate-sheet":
            content["sheets"].append(content["sheets"][0])
        elif case == "summary-type":
            content["summary"] = []
        elif case == "missing-counts":
            content["summary"].pop("findings")
        elif case == "counts-type":
            content["summary"]["findings"] = []
        elif case in ("counts-value", "bool-count"):
            content["summary"]["findings"]["text-on-line"] = True if case == "bool-count" else "1"
        elif case == "count-mismatch":
            content["findings"].pop(0)
        elif case in ("sheet-count", "bool-sheet-count"):
            content["summary"]["sheets"] = True if case == "bool-sheet-count" else 2
        elif case in ("gating-count", "bool-gating-count"):
            content["summary"]["gating"] = True if case == "bool-gating-count" else 0
        else:
            raise AssertionError(case)
        report.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises((RuntimeError, OSError, json.JSONDecodeError)):
        drawing._enforce_fixture_text_on_line(report)


def test_local_text_gate_consumes_the_completed_finalizer_report_once() -> None:
    assert _build_calls_in_order({"finalize_drawing", "_enforce_fixture_text_on_line"}) == [
        "finalize_drawing", "_enforce_fixture_text_on_line",
    ]
    tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    build = _function(tree, "build")
    assert isinstance(build.body[-1], ast.Return)
    assert ast.unparse(build.body[-1].value) == "artifacts"
    source = ast.unparse(_function(tree, "_enforce_fixture_text_on_line"))
    assert "audit_dump(" not in source and "collect_sheet_dumps(" not in source


class _ArrowData:
    """IDisplayData arrow count and 12-double GetArrowHeadAtIndex2 method."""

    def __init__(self, tip: tuple[float, float], *, count: int = 1, complete: bool = True) -> None:
        self.count = count
        self.arrow = (*tip, 0.0, 1.0, 0.0, 0.0, 0.003556, 0.001, 0.0, 0.0, 0.0, 1.0)
        if not complete:
            self.arrow = self.arrow[:2]

    def GetArrowHeadCount(self) -> int:
        return self.count

    def GetArrowHeadAtIndex2(self, index: int) -> tuple:
        assert index == 0
        return self.arrow


class _RadialAnnotation(_RootAnnotation):
    def __init__(self, display: _NativeDisplay) -> None:
        super().__init__(display)
        self.OwnerType = 0
        self.dangling = False

    def IsDangling(self) -> bool:
        return self.dangling


def _radius_readback_fakes(
    monkeypatch: pytest.MonkeyPatch, *, count: int = 1, complete: bool = True
) -> tuple[_RadialAnnotation, _RootAnnotation]:
    ink, tip, station_ink, centre = _material_radius_ink()
    display = _radial_display()
    display.ArcExtensionLineOrOppositeSide = False
    display.data = _ArrowData(tip, count=count, complete=complete)
    radius, station = _RadialAnnotation(display), _RootAnnotation(_station_display())
    radius.ink = ink
    station.ink = station_ink
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    points = {
        (geom.GROOVE_X / 1000.0, 0.0, -geom.GROOVE_CENTRE_R / 1000.0): centre,
        (geom.SPIGOT_FACE_X / 1000.0, 0.0, 0.0): _FACE_ON_AXIS,
    }
    monkeypatch.setattr(
        drawing, "model_point_in_view", lambda adapter, view, xyz, *, label: points[xyz]
    )

    def segments(annotation: _RootAnnotation) -> list:
        assert annotation is radius or annotation is station
        return annotation.ink

    monkeypatch.setattr(drawing, "dimension_segments", segments)
    return radius, station


def test_rebuilt_radius_proof_reads_native_arrow_tip_and_model_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    radius, station = _radius_readback_fakes(monkeypatch)
    drawing._prove_groove_radius(object(), object(), radius, station)


def test_rebuilt_radius_proof_refuses_a_lost_max_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    radius, station = _radius_readback_fakes(monkeypatch)
    radius.display.dimension.Tolerance.Type = 0  # swTolNONE: a bare R1.2
    with pytest.raises(RuntimeError, match="single MAX limit"):
        drawing._prove_groove_radius(object(), object(), radius, station)


def test_rebuilt_radius_proof_refuses_r1s_shelf_at_the_od(monkeypatch: pytest.MonkeyPatch) -> None:
    # r1: the shoulder ran level at the OD and the arrow sat at the mouth.
    # Its arrow is already off the material arc; its leader, put back on it,
    # still shelves at the OD.
    radius, station = _radius_readback_fakes(monkeypatch)
    elbow = (drawing.RADIUS_ELBOW_XY[0], drawing._side_y(geom.SPIGOT_DIA / 2.0))
    radius.ink, tip = _radius_ink(elbow)
    radius.display.data = _ArrowData(tip)
    with pytest.raises(RuntimeError, match="not on the face-side material arc"):
        drawing._prove_groove_radius(object(), object(), radius, station)
    radius.ink, _tip = _radius_ink((_FACE_ON_AXIS[0] + 0.004, drawing.GROOVE_ROOT_SHEET_YS[1] - 0.001))
    radius.display.data = _ArrowData(_tip)
    with pytest.raises(RuntimeError, match="does not read in open air.*not between"):
        drawing._prove_groove_radius(object(), object(), radius, station)


@pytest.mark.parametrize(
    ("name", "feature", "value"),
    [
        ("OtherLength", "GrooveProfile", spec.GROOVE_STATION),
        ("GrooveStation", "OtherSketch", spec.GROOVE_STATION),
        ("GrooveStation", "GrooveProfile", spec.GROOVE_STATION + 2e-5),
    ],
)
def test_station_witness_gaps_are_written_only_on_the_genuine_model_dimension(
    monkeypatch: pytest.MonkeyPatch, name: str, feature: str, value: float,
) -> None:
    _projection_fakes(monkeypatch)
    station = _NativeDisplay(name, feature, value, kind=2)
    with pytest.raises(RuntimeError, match="wrong model dimension"):
        _place(_radial_display(), station)
    assert station.gaps == []


@pytest.mark.parametrize(
    ("count", "complete", "message"),
    [(0, True, "exactly one"), (2, True, "exactly one"), (1, False, "incomplete arrow")],
)
def test_rebuilt_radius_proof_refuses_missing_extra_or_unreadable_arrow(
    monkeypatch: pytest.MonkeyPatch, count: int, complete: bool, message: str
) -> None:
    radius, station = _radius_readback_fakes(monkeypatch, count=count, complete=complete)
    with pytest.raises(RuntimeError, match=message):
        drawing._prove_groove_radius(object(), object(), radius, station)


_Y_BORE_CYLINDER = (0.0, 0.004, 0.0, 0.0, 1.0, 0.0, geom.ROD_BORE_DIA / 2000.0)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_rod_bore_cylinder_accepts_only_the_model_y_axis(sign: float) -> None:
    params = (*_Y_BORE_CYLINDER[:4], sign, *_Y_BORE_CYLINDER[5:])
    assert drawing._is_rod_bore_cylinder(params)


@pytest.mark.parametrize(
    "params",
    [
        (),
        _Y_BORE_CYLINDER[:6],
        (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, geom.TAP_DRILL_DIA / 2000.0),
        (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, geom.ROD_BORE_DIA / 2000.0),
        (0.0001, *_Y_BORE_CYLINDER[1:]),
        (*_Y_BORE_CYLINDER[:6], geom.SPIGOT_DIA / 2000.0),
        (*_Y_BORE_CYLINDER[:6], float("nan")),
    ],
)
def test_rod_bore_cylinder_refuses_the_axial_tap_wrong_radius_and_offset(params: tuple) -> None:
    assert not drawing._is_rod_bore_cylinder(params)


class _CylinderFace:
    def __init__(self, params: tuple, *, cylinder: bool = True) -> None:
        self.surface = SimpleNamespace(CylinderParams=params, IsCylinder=lambda: cylinder)

    def GetSurface(self) -> SimpleNamespace:
        return self.surface


def _bore_face_fakes(
    monkeypatch: pytest.MonkeyPatch, faces: tuple, *, mapped: bool = True,
    roundtrip: bool = True, equality: int = 1, wrong_source: bool = False,
    view_faces: tuple | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace, object]:
    source_face = faces[0] if faces else object()
    view_face = (
        view_faces[0] if view_faces else _CylinderFace(_Y_BORE_CYLINDER)
    )
    feature = SimpleNamespace(GetFaces=lambda: faces)
    view_feature = SimpleNamespace(
        GetFaces=lambda: (view_face,) if view_faces is None else view_faces
    )

    def feature_by_name(name: str) -> SimpleNamespace:
        assert name == "RodBore"
        return feature

    def corresponding_feature(input_object: object) -> SimpleNamespace | None:
        assert input_object is feature
        return view_feature if mapped else None

    def corresponding_source(entity: object) -> object | None:
        assert entity is view_face
        if not roundtrip:
            return None
        return object() if wrong_source else source_face

    extension = SimpleNamespace(GetCorrespondingEntity2=corresponding_source)
    model = SimpleNamespace(FeatureByName=feature_by_name, Extension=extension)
    view = SimpleNamespace(
        ReferencedDocument=model,
        GetCorresponding=corresponding_feature,
    )
    app = SimpleNamespace(IsSame=lambda first, second: equality if first is second else 0)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    return SimpleNamespace(swApp=app), view, view_face


def test_bore_axis_reacquires_the_views_cylinder_when_direct_face_mapping_is_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_face = _CylinderFace(_Y_BORE_CYLINDER)
    adapter, view, face = _bore_face_fakes(monkeypatch, (source_face,))
    direct_calls: list[object] = []

    def direct_face_mapping(entity: object) -> None:
        direct_calls.append(entity)
        return None

    view.GetCorrespondingEntity = direct_face_mapping
    assert drawing._rod_bore_face(adapter, view) is face
    assert face is not source_face
    assert direct_calls == []


@pytest.mark.parametrize(
    "case",
    [
        "no-face", "two-faces", "tap", "no-view", "no-source", "wrong-source",
        "different", "unknown",
    ],
)
def test_bore_axis_face_refuses_ambiguity_or_lost_source_correspondence(
    monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    faces = (_CylinderFace(_Y_BORE_CYLINDER),)
    options: dict = {}
    if case == "no-face":
        faces = ()
    elif case == "two-faces":
        faces = faces * 2
    elif case == "tap":
        faces = (_CylinderFace(_DRILL_CIRCLE),)
    elif case == "no-view":
        options["mapped"] = False
    elif case == "no-source":
        options["roundtrip"] = False
    elif case == "wrong-source":
        options["wrong_source"] = True
    else:
        options["equality"] = 0 if case == "different" else -1
    adapter, view, _face = _bore_face_fakes(monkeypatch, faces, **options)
    with pytest.raises(RuntimeError):
        drawing._rod_bore_face(adapter, view)


@pytest.mark.parametrize(
    "view_faces",
    [
        (),
        (_CylinderFace(_Y_BORE_CYLINDER),) * 2,
        (_CylinderFace(_Y_BORE_CYLINDER, cylinder=False),),
        (_CylinderFace((0.0, 0.0, 0.0, 1.0, 0.0, 0.0, geom.TAP_DRILL_DIA / 2000.0)),),
        (_CylinderFace((*_Y_BORE_CYLINDER[:6], geom.SPIGOT_DIA / 2000.0)),),
        (_CylinderFace((0.0001, *_Y_BORE_CYLINDER[1:])),),
    ],
)
def test_bore_axis_refuses_a_mapped_feature_without_one_true_y_bore(
    monkeypatch: pytest.MonkeyPatch, view_faces: tuple,
) -> None:
    adapter, view, _face = _bore_face_fakes(
        monkeypatch, (_CylinderFace(_Y_BORE_CYLINDER),), view_faces=view_faces
    )
    with pytest.raises(RuntimeError, match="one RodBore Y-axis cylindrical face in end view"):
        drawing._rod_bore_face(adapter, view)


def test_bore_axis_refuses_unmeasured_cylinder_status_in_the_mapped_feature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapped_face = _CylinderFace(_Y_BORE_CYLINDER)
    mapped_face.surface.IsCylinder = lambda: 1
    adapter, view, _face = _bore_face_fakes(
        monkeypatch, (_CylinderFace(_Y_BORE_CYLINDER),), view_faces=(mapped_face,)
    )
    with pytest.raises(RuntimeError, match="IsCylinder did not return a native BOOL"):
        drawing._rod_bore_face(adapter, view)


def _bore_axis_corners() -> tuple[tuple[float, float], tuple[float, float]]:
    x, y = drawing.END_CENTER
    return ((x - drawing._END_HALF_WIDTH, y), (x + drawing._END_HALF_WIDTH, y))


def test_bore_axis_ink_spans_both_corners_horizontally_in_the_rotated_frame() -> None:
    corners = _bore_axis_corners()
    assert drawing._bore_axis_ink_problem([corners], corners) is None


@pytest.mark.parametrize("case", ["empty", "tap-cross", "vertical", "offset", "overshoot"])
def test_bore_axis_ink_refuses_a_tap_mark_or_false_axis(case: str) -> None:
    corners = _bore_axis_corners()
    x, y = drawing.END_CENTER
    ink = {
        "empty": [],
        "tap-cross": [((x - 0.003, y), (x + 0.003, y))],
        "vertical": [((x, y - drawing._END_HALF_WIDTH), (x, y + drawing._END_HALF_WIDTH))],
        "offset": [((corners[0][0], y + 0.001), (corners[1][0], y + 0.001))],
        "overshoot": [((x - 0.04, y), (x + 0.04, y))],
    }[case]
    assert drawing._bore_axis_ink_problem(ink, corners) is not None


class _AttachedAxis(_MarkAnnotation):
    def __init__(self, face: object, *, owner: int = 0, dangling: bool = False, kind: int = 2) -> None:
        corners = _bore_axis_corners()
        super().__init__(_MarkData([(*corners[0], *corners[1])]))
        self.face = face
        self.OwnerType = owner
        self.dangling = dangling
        self.kind = kind

    def GetAttachedEntities3(self) -> tuple:
        return (self.face,)

    def GetAttachedEntityCount3(self) -> int:
        return 1

    def GetAttachedEntityTypes(self) -> tuple:
        return (self.kind,)

    def GetLeaderCount(self) -> int:
        return 0

    def IsDangling(self) -> bool:
        return self.dangling


class _TapCross(_MarkAnnotation):
    def __init__(self, *, extended: bool = False) -> None:
        x, y = drawing.END_CENTER
        reach = 0.028 if extended else 0.003
        super().__init__(_MarkData([(x - reach, y, x + reach, y), (x, y - reach, x, y + reach)]))
        self.mark = SimpleNamespace(UseDocDisplaySettings=False, ShowLines=False)

    def GetSpecificAnnotation(self) -> SimpleNamespace:
        return self.mark


def _axis_readback_fakes(
    monkeypatch: pytest.MonkeyPatch, *, wrong_face: bool = False, stale: bool = False,
    count: int = 1, owner: int = 0, dangling: bool = False, kind: int = 2,
    equality: int = 1, extended: bool = False,
) -> tuple:
    face = object()
    annotation = _AttachedAxis(object() if wrong_face else face, owner=owner, dangling=dangling, kind=kind)
    axis = SimpleNamespace(GetAnnotation=lambda: annotation)
    ink = _AttachedAxis(face) if stale else annotation

    def annotations_by_type(annotation_type: int) -> tuple:
        assert annotation_type == 15
        return (ink,) * count

    view = SimpleNamespace(GetAnnotationsByType=annotations_by_type)
    adapter = SimpleNamespace(
        swApp=SimpleNamespace(IsSame=lambda first, second: equality if first is second else 0)
    )

    def project(adapter, view, xyz, *, label):
        return drawing.END_CENTER[0] - xyz[1] * drawing._S, drawing.END_CENTER[1]

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "model_point_in_view", project)
    return adapter, view, axis, face, _TapCross(extended=extended)


def test_native_bore_axis_proof_requires_face_identity_owner_ink_and_small_tap_cross(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drawing._prove_rod_bore_axis(*_axis_readback_fakes(monkeypatch))


@pytest.mark.parametrize(
    "options",
    [
        {"wrong_face": True}, {"stale": True}, {"count": 0}, {"count": 2},
        {"owner": 1}, {"dangling": True}, {"kind": 1}, {"equality": -1},
        {"extended": True},
    ],
)
def test_native_bore_axis_refuses_unassociated_sheet_ink_duplicates_and_long_tap_arms(
    monkeypatch: pytest.MonkeyPatch, options: dict,
) -> None:
    with pytest.raises(RuntimeError):
        drawing._prove_rod_bore_axis(*_axis_readback_fakes(monkeypatch, **options))


def test_bore_axis_insertion_reuses_native_face_helper_and_shortens_existing_mark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    face, axis = object(), object()
    tap_mark = _TapCross()
    tap_mark.mark.UseDocDisplaySettings = True
    tap_mark.mark.ShowLines = True
    view = SimpleNamespace(GetAnnotationsByType=lambda kind: ())
    calls: list[tuple] = []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "_rod_bore_face", lambda adapter, native: face)

    def insert(adapter, native, *, entity, label):
        assert native is view
        calls.append((entity, label))
        return axis

    monkeypatch.setattr(drawing, "add_view_centerline", insert)
    assert drawing._add_rod_bore_axis(object(), view, tap_mark) == (axis, face)
    assert tap_mark.mark.UseDocDisplaySettings is False
    assert tap_mark.mark.ShowLines is False
    assert calls == [(face, "rod bore Y axis through hex corners")]


@pytest.mark.parametrize("case", ["dangling", "sheet-owned", "lost-style", "no-data"])
def test_radius_readback_refuses_floating_ink_and_lost_native_style(
    monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    radius, station = _radius_readback_fakes(monkeypatch)
    if case == "dangling":
        radius.dangling = True
    elif case == "sheet-owned":
        radius.OwnerType = 1
    elif case == "lost-style":
        radius.display.ArcExtensionLineOrOppositeSide = True
    else:
        radius.display.data = None
    with pytest.raises(RuntimeError):
        drawing._prove_groove_radius(object(), object(), radius, station)


@pytest.mark.parametrize("brackets", [("(", ")"), ("", ""), ("(<MOD-DIAM>", ")")])
def test_end_af_native_proof_preserves_linear_ref_brackets(
    monkeypatch: pytest.MonkeyPatch, brackets: tuple[str, str],
) -> None:
    display = _NativeDisplay("HexAf", "HexProfile", geom.HEX_AF, kind=2)
    display.GetText = lambda part: {1: brackets[0], 2: brackets[1]}[part]
    annotation = _RootAnnotation(display)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(drawing, "dimension_segments", lambda raw: _vertical_af_ink())

    def project(adapter, view, xyz, *, label):
        return (
            drawing.END_CENTER[0] - xyz[1] * drawing._S,
            drawing.END_CENTER[1] - xyz[2] * drawing._S,
        )

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    if brackets == ("(", ")"):
        drawing._prove_end_stock_reference(object(), object(), annotation)
    else:
        with pytest.raises(RuntimeError, match="linear stock-reference brackets"):
            drawing._prove_end_stock_reference(object(), object(), annotation)


def test_native_bore_axis_refuses_null_annotation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    with pytest.raises(RuntimeError, match="no annotation"):
        drawing._prove_rod_bore_axis(
            object(), object(), SimpleNamespace(GetAnnotation=lambda: None), object(), object()
        )


def test_bore_axis_insertion_refuses_an_existing_coincident_axis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    view = SimpleNamespace(GetAnnotationsByType=lambda kind: (object(),))
    with pytest.raises(RuntimeError, match="already has a centreline"):
        drawing._add_rod_bore_axis(object(), view, _TapCross())


class _FalseLikeReadback:
    """A non-BOOL object can be falsey without measuring native False."""

    def __bool__(self) -> bool:
        return False

    def member(self) -> bool:
        return False


_NON_BOOL_READBACKS = (
    None, 0, 1, _FalseLikeReadback(), _FalseLikeReadback().member, object(),
)


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
def test_radius_arc_property_requires_measured_bool_false_after_write(
    monkeypatch: pytest.MonkeyPatch, readback: object,
) -> None:
    _projection_fakes(monkeypatch)
    display = _radial_display(arc_persists=False)
    display._arc = readback
    with pytest.raises(RuntimeError, match="still attaches"):
        _place(display)


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
def test_radius_diametric_property_requires_measured_bool_false_before_write(
    monkeypatch: pytest.MonkeyPatch, readback: object,
) -> None:
    _projection_fakes(monkeypatch)
    display = _radial_display()
    display.Diametric = readback
    with pytest.raises(RuntimeError, match="genuine radial dimension"):
        _place(display)


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
@pytest.mark.parametrize("member", ["Diametric", "ArcExtensionLineOrOppositeSide", "IsDangling"])
def test_rebuilt_radius_bool_readbacks_refuse_none_integer_boundmethod_and_object(
    monkeypatch: pytest.MonkeyPatch, readback: object, member: str,
) -> None:
    radius, station = _radius_readback_fakes(monkeypatch)
    if member == "Diametric":
        radius.display.Diametric = readback
    elif member == "ArcExtensionLineOrOppositeSide":
        radius.display._arc = readback
    else:
        radius.dangling = readback
    with pytest.raises(RuntimeError):
        drawing._prove_groove_radius(object(), object(), radius, station)


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
def test_bore_surface_is_cylinder_requires_an_actual_native_bool(
    monkeypatch: pytest.MonkeyPatch, readback: object,
) -> None:
    face = _CylinderFace(_Y_BORE_CYLINDER)
    face.surface.IsCylinder = lambda: readback
    adapter, view, _face = _bore_face_fakes(monkeypatch, (face,))
    with pytest.raises(RuntimeError, match="IsCylinder did not return a native BOOL"):
        drawing._rod_bore_face(adapter, view)


def test_bore_surface_false_is_skipped_without_rejecting_the_true_cylinder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    faces = (
        _CylinderFace(_Y_BORE_CYLINDER),
        _CylinderFace(_Y_BORE_CYLINDER, cylinder=False),
    )
    adapter, view, face = _bore_face_fakes(monkeypatch, faces)
    assert drawing._rod_bore_face(adapter, view) is face


class _MarkFlagReadback:
    """ICenterMark BOOL properties with one deliberately ignored write."""

    def __init__(self, member: str, readback: object) -> None:
        self.member = member
        self.readback = readback
        self._doc = False
        self._lines = False

    @property
    def UseDocDisplaySettings(self) -> object:
        return self.readback if self.member == "UseDocDisplaySettings" else self._doc

    @UseDocDisplaySettings.setter
    def UseDocDisplaySettings(self, value: bool) -> None:
        assert type(value) is bool
        if self.member != "UseDocDisplaySettings":
            self._doc = value

    @property
    def ShowLines(self) -> object:
        return self.readback if self.member == "ShowLines" else self._lines

    @ShowLines.setter
    def ShowLines(self, value: bool) -> None:
        assert type(value) is bool
        if self.member != "ShowLines":
            self._lines = value


@pytest.mark.parametrize("readback", (*_NON_BOOL_READBACKS, True))
@pytest.mark.parametrize("member", ["UseDocDisplaySettings", "ShowLines"])
def test_tap_cross_false_properties_require_measured_false_after_native_write(
    monkeypatch: pytest.MonkeyPatch, readback: object, member: str,
) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    mark = _TapCross()
    mark.mark = _MarkFlagReadback(member, readback)
    view = SimpleNamespace(GetAnnotationsByType=lambda kind: ())
    with pytest.raises(RuntimeError, match="retained coincident"):
        drawing._add_rod_bore_axis(object(), view, mark)


@pytest.mark.parametrize("readback", (*_NON_BOOL_READBACKS, True))
@pytest.mark.parametrize("member", ["UseDocDisplaySettings", "ShowLines"])
def test_rebuilt_tap_cross_refuses_unmeasured_false_and_ignored_property_writes(
    monkeypatch: pytest.MonkeyPatch, readback: object, member: str,
) -> None:
    adapter, view, axis, face, tap_mark = _axis_readback_fakes(monkeypatch)
    tap_mark.mark = _MarkFlagReadback(member, readback)
    with pytest.raises(RuntimeError, match="regained its coincident"):
        drawing._prove_rod_bore_axis(adapter, view, axis, face, tap_mark)


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
def test_bore_axis_dangling_method_requires_measured_false(
    monkeypatch: pytest.MonkeyPatch, readback: object,
) -> None:
    adapter, view, axis, face, tap_mark = _axis_readback_fakes(monkeypatch)
    axis.GetAnnotation().dangling = readback
    with pytest.raises(RuntimeError, match="dangling state is not measured False"):
        drawing._prove_rod_bore_axis(adapter, view, axis, face, tap_mark)

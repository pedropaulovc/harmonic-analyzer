"""Offline contracts for the output fixture (MHA-MG-006): part, sheet, pose."""

from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_mg_output_fixture as part
import draw_mg_output_fixture as drawing
import mg_output_fixture_geom as geom
import mg_output_fixture_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _printed_tolerance import printed_band_mm

SCRIPTS = Path(geom.__file__).resolve().parent
POLICY = SCRIPTS.parent / "docs" / "drawing-simplicity-policy.md"


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


def test_every_explicit_band_is_on_a_printed_dimension() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.SYMMETRIC_BANDS) <= marked
    for name, (feature, _tolerance) in spec.SYMMETRIC_BANDS.items():
        assert name in spec.DRAWING_DIMENSIONS[feature], name
    upper, lower = spec.ROD_BORE_DIA_BAND
    assert upper > lower == 0.0  # a reamed slip bore never undersize


def test_flats_print_as_an_unbanded_stock_reference() -> None:
    # Machinist review: 9.525 at .XXX asked for a size the bar is bought at.
    assert spec.REFERENCE_DIMENSIONS == {"HexAf"}
    assert spec.DRAWING_DIMENSIONS["HexProfile"] == {"HexAf"}
    assert "HexAf" not in spec.SYMMETRIC_BANDS
    assert spec.DRAWING_PRECISION_BY_NAME["HexAf"] == 3  # the exact 3/8 in
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in source
    assert "set_reference_dimension(" in source
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
    # The hook leaves on the rod's front tangent, wire clear of the rod.
    from mg_magnifying_vertical_rod_geom import ROD_DIA

    assert geom.VROD_Z - geom.HOOK_TARGET_Z == pytest.approx(
        ROD_DIA / 2.0 + geom.WIRE_DIA / 2.0 + geom.WIRE_CLEARANCE
    )


def test_hook_point_is_authored_on_the_top_plane_where_the_geometry_puts_it() -> None:
    # Top-plane sketch (x, y) is model (X, -Z).
    x, y = part._hook_sketch_xy()
    assert (x, 0.0, -y) == geom.HOOK_LOCAL


def test_groove_runs_on_the_spigot_with_both_lips() -> None:
    low, high = geom.GROOVE_MOUTHS
    assert geom.SHOULDER_X < low < high < geom.SPIGOT_FACE_X
    assert geom.GROOVE_ROOT_DIA < geom.SPIGOT_DIA < geom.HEX_AF


def test_walls_hold_the_target_at_the_printed_worst_case() -> None:
    for name, (nominal, worst) in spec.WALLS.items():
        assert worst <= nominal, name
        assert worst >= spec.WALL_TARGET - 1e-9, (name, worst)


def test_floor_2_never_rounds_a_min_up() -> None:
    assert spec.floor_2(2.0824999999999996) == 2.08
    assert spec.floor_2(2.0899999) == 2.08
    # The epsilon keeps a float a hair under an exact hundredth on it.
    assert spec.floor_2(1.97 - 1e-12) == 1.97
    assert spec.floor_2(1.9699) == 1.96


def test_bore_is_centred_and_the_stated_wall_is_the_named_shortfall() -> None:
    # Independent of the spec's arithmetic: the bore centred on the thinnest
    # stock (3/8 in less the 0.13 stock assumption) at its largest reamed Ø.
    assert spec.HEX_STOCK_AF_BAND == 0.13
    smallest_af = 0.375 * 25.4 - 0.13
    largest_bore_r = (5.2 + 0.03) / 2.0
    worst = smallest_af / 2.0 - largest_bore_r
    assert worst == pytest.approx(2.0825, abs=1e-9)
    assert spec.WALLS[spec.BORE_WALL_NAME] == pytest.approx((2.1625, worst), abs=1e-9)
    assert spec.BORE_WALL_WORST_PRINTED == 2.08
    # The authorized 1.97 stays: under the target (the named shortfall), over
    # the floor, and never above the derived worst wall.
    assert spec.BORE_WALL_STATED_MIN == 1.97
    assert spec.WALL_FLOOR <= spec.BORE_WALL_STATED_MIN < spec.WALL_TARGET
    assert spec.BORE_WALL_STATED_MIN <= spec.BORE_WALL_WORST_PRINTED <= worst
    # What it accepts off centre: the widest stock, the smallest bore.
    assert spec.BORE_OFFSET_MAX == pytest.approx(
        (0.375 * 25.4 + 0.13) / 2.0 - 2.6 - 1.97, abs=1e-9
    )
    assert spec.BORE_OFFSET_MAX == pytest.approx(0.2575, abs=1e-9)
    stated = f"{spec.BORE_WALL_STATED_MIN:.2f}"
    assert spec.DRAWING_NOTES.splitlines() == [
        "3/8 HEX BAR, FLATS AS SUPPLIED.",
        f"ROD BORE CENTRED; BORE TO FLAT WALL {stated} MIN.",
        "4-40: PLUG TAP, 3-5 THREAD CHAMFER.",
        "THREAD ENDS AT ROD BORE; THREAD DEPTH REF.",
    ]
    policy = POLICY.read_text(encoding="utf-8").split("\n## Named exceptions", 1)[1]
    rows = [line for line in policy.splitlines() if line.startswith("| MHA-MG-006")]
    assert len(rows) == 1 and stated in rows[0]
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


def test_a_plug_tap_reaches_full_thread_through_the_wall_and_stops_short() -> None:
    # Morse Cutting Tools #4-40 plug tap (catalogue 552474, item 30000): a
    # 3-5 thread chamfer, usable length LU 9/16 in on a 0.141 in shank (over
    # the 0.112 in major, so the shank stops at the spigot face and LU is the
    # tap's whole reach).
    reach = 9.0 / 16.0 * 25.4
    assert spec.PLUG_TAP_USABLE_LENGTH == pytest.approx(14.2875, abs=1e-9)
    assert spec.PLUG_TAP_SHANK_DIA == pytest.approx(3.5814, abs=1e-9)
    assert spec.PLUG_TAP_CHAMFER_THREADS == (3, 5)
    pitch = 25.4 / 40.0
    # The longest chamfer the sheet allows is the lead to the first full thread.
    assert spec.PLUG_TAP_LEAD == pytest.approx(5.0 * pitch, abs=1e-9)
    # Face to bore axis at the printed worst case: 17.70 +0.05 less 5.00 -0.05.
    face_to_axis_max, face_to_axis_min = 12.8, 12.6
    # The thread's widest reach off the bore axis: the library's conservative
    # metric basic major Ø2.845 (rather than the vendor's exact 0.112 in),
    # tap oversize and all the off-centre the stated wall accepts.
    assert spec.THREAD_MAJOR == 2.845
    reach_off_axis = 2.845 / 2.0 + 0.025 + 0.2575
    half_chord = math.sqrt(2.6**2 - reach_off_axis**2)
    deepest_wall = face_to_axis_max - half_chord
    assert spec.TAP_WALL_DEEPEST == pytest.approx(deepest_wall, abs=1e-9)
    assert spec.TAP_WALL_DEEPEST == pytest.approx(10.837, abs=5e-4)
    assert spec.TAP_REACH_NEEDED == pytest.approx(deepest_wall + 5.0 * pitch, abs=1e-9)
    assert reach - spec.TAP_REACH_NEEDED == pytest.approx(0.2755, abs=5e-4)
    # The far wall's nearest point is past the shank stop: the tap's end
    # never reaches it.
    assert spec.FAR_WALL_NEAREST == pytest.approx(face_to_axis_min + half_chord, abs=1e-9)
    assert spec.FAR_WALL_NEAREST - reach == pytest.approx(0.2755, abs=5e-4)
    # A 6-thread plug chamfer (the long end of ICS's 3-6) would leave the
    # deepest flank under-cut at the worst case: hence the sheet's 3-5.
    assert deepest_wall + 6.0 * pitch > reach
    assert spec.TAP_TOOL_NOTE in spec.DRAWING_NOTES.splitlines()


def test_the_rod_bore_ends_the_thread_and_its_depth_is_ref() -> None:
    # The native thread depth is the nominal wall on the tap's axis; the
    # sheet makes it REF, so no .X band (10.1 +/-0.8 would admit 9.3) governs
    # the thread's extent: the rod bore does.
    assert spec.TAP_EXTENT_NOTE == "THREAD ENDS AT ROD BORE; THREAD DEPTH REF."
    assert spec.TAP_EXTENT_NOTE in spec.DRAWING_NOTES.splitlines()
    assert geom.TAP_SPEC.overrides_mm["ThreadDepth"] == geom.TAP_LENGTH
    assert geom.TAP_LENGTH == pytest.approx(geom.SPIGOT_FACE_X - geom.ROD_BORE_DIA / 2.0)
    # The native depth stays model-owned: no typed replacement on the sheet.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_hole_callout_precision(" in source
    assert "(10.1)" not in source and "10.1 REF" not in source


@pytest.mark.parametrize(
    ("resolved", "reads"),
    [
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> 10.1",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            True,
        ),
        # Retry08's native reading (20261012T111849499Z, swmaker000005).
        (
            {
                1: "TAP INTO BORE 4-40 UNC - 2B <HOLE-DEPTH> 10.1",
                2: "",
                3: "<MOD-DIAM> 2.26 <HOLE-DEPTH> 12.7",
                4: "",
            },
            True,
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
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> 10.10",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            False,
        ),
        # The thread without its extent.
        (
            {
                1: "4-40 UNC-2B <HOLE-DEPTH> 10.1",
                2: "<MOD-DIAM>2.26 <HOLE-DEPTH> 12.7",
                3: "",
                4: "",
            },
            False,
        ),
        # The drill row without its depth.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> 10.1",
                2: "<MOD-DIAM>2.26",
                3: "",
                4: "",
            },
            False,
        ),
        # A band on the REF thread depth.
        (
            {
                1: "TAP INTO BORE 4-40 UNC-2B <HOLE-DEPTH> 10.1<MOD-PM>0.8",
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
        "TAP INTO BORE 4-40 UNC - 2B <HOLE-DEPTH> 10.1\n"
        "<MOD-DIAM> 2.26 <HOLE-DEPTH> 12.7"
    )
    assert note not in native_callout.lower()


# The groove lips, the spigot's clean-up inside the thinnest flats and the
# tap's reach, with each band at its half-width: the kept +/-0.05 everywhere,
# or one dimension opened to the title block's .XX row it prints at.
_KEPT_BAND = 0.05


def _stacks(relaxed: str | None) -> dict[str, float]:
    band = {name: _KEPT_BAND for name in spec.SYMMETRIC_BANDS}
    if relaxed is not None:
        band[relaxed] = printed_band_mm(spec.DRAWING_PRECISION_BY_NAME[relaxed])
    radius = geom.GROOVE_RADIUS + band["GrooveRadius"]
    centre = (geom.GROOVE_ROOT_DIA - band["GrooveRootDia"]) / 2.0 + radius
    od_lo = (geom.SPIGOT_DIA - band["SpigotDia"]) / 2.0
    od_hi = (geom.SPIGOT_DIA + band["SpigotDia"]) / 2.0
    # The widest mouth: the radius itself once the arc's centre can sit on
    # the OD, else the OD nearest the centre.
    above = 0.0 if od_lo <= centre <= od_hi else min(abs(centre - od_lo), abs(centre - od_hi))
    half = math.sqrt(radius**2 - above**2)
    station = spec.GROOVE_STATION
    face_to_axis = (
        geom.OVERALL_LENGTH + band["OverallLength"] - (geom.ROD_STATION - band["RodStation"])
    )
    reach_off_axis = geom.THREAD_MAJOR / 2.0 + 0.025 + spec.BORE_OFFSET_MAX
    return {
        "shoulder lip": station - band["GrooveStation"] - half
        - (geom.HEX_LENGTH + band["HexLength"]),
        "face lip": geom.OVERALL_LENGTH - band["OverallLength"]
        - (station + band["GrooveStation"]) - half,
        "spigot clean-up": geom.HEX_AF - spec.HEX_STOCK_AF_BAND
        - (geom.SPIGOT_DIA + band["SpigotDia"]),
        "tap reach": spec.PLUG_TAP_USABLE_LENGTH
        - (face_to_axis - math.sqrt(2.6**2 - reach_off_axis**2) + spec.PLUG_TAP_LEAD),
    }


def _failures(stacks: dict[str, float]) -> set[str]:
    failed = {name for name in ("shoulder lip", "face lip") if stacks[name] < 2.0 - 1e-9}
    failed |= {name for name in ("spigot clean-up", "tap reach") if stacks[name] <= 0.0}
    return failed


def test_the_kept_bands_hold_every_stack() -> None:
    assert {name: tol for name, (_f, tol) in spec.SYMMETRIC_BANDS.items()} == {
        "RodStation": 0.05,
        "HexLength": 0.05,
        "GrooveStation": 0.05,
        "OverallLength": 0.05,
        "SpigotDia": 0.05,
        "GrooveRootDia": 0.05,
        "GrooveRadius": 0.05,
    }
    stacks = _stacks(None)
    assert not _failures(stacks)
    assert stacks["shoulder lip"] == pytest.approx(2.0161, abs=5e-5)
    assert stacks["face lip"] == pytest.approx(2.0161, abs=5e-5)
    assert stacks["spigot clean-up"] == pytest.approx(0.345, abs=1e-9)
    assert stacks["tap reach"] == pytest.approx(0.2755, abs=5e-4)
    # The spec's own walls agree.
    assert spec.WALLS["groove lip to the shoulder"][1] == pytest.approx(
        stacks["shoulder lip"], abs=1e-9
    )
    assert spec.WALLS["groove lip to the spigot face"][1] == pytest.approx(
        stacks["face lip"], abs=1e-9
    )


@pytest.mark.parametrize(
    ("relaxed", "fails", "evidence"),
    [
        # 17.70 at .XX (+/-0.51): face lip 1.556, tap reach short by 0.18.
        ("OverallLength", {"face lip", "tap reach"}, {"face lip": 1.5561, "tap reach": -0.1845}),
        # 11.00 at .XX: shoulder lip 1.556.
        ("HexLength", {"shoulder lip"}, {"shoulder lip": 1.5561}),
        # R1.20 at .XX: the mouth widens to 2 x 1.5775, both lips 1.6725.
        ("GrooveRadius", {"shoulder lip", "face lip"}, {"shoulder lip": 1.6725, "face lip": 1.6725}),
        # Ø9.00 at .XX: the lips hold at 2.000 (the mouth caps at the radius),
        # but a 9.51 spigot is past the 9.395 flats: it would not turn round.
        ("SpigotDia", {"spigot clean-up"}, {"shoulder lip": 2.0, "spigot clean-up": -0.115}),
    ],
)
def test_each_band_the_review_questioned_fails_when_opened(
    relaxed: str, fails: set[str], evidence: dict[str, float]
) -> None:
    stacks = _stacks(relaxed)
    assert _failures(stacks) == fails
    for name, value in evidence.items():
        assert stacks[name] == pytest.approx(value, abs=5e-4), name


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


def test_sheet_reads_places_and_bands_from_the_part() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "assert_imported_precision" in source
    assert "set_dimension_precision" not in source
    assert "tolerance" not in source.lower()
    for gdt in ("gtol", "datum"):
        assert gdt not in source.lower(), gdt


# A dimension's text centre sits ~2.8 mm over its line (2026-10-12 farm
# sheet: HexLength's text at 209.05 mm over its line at 206.27 mm).
_TEXT_OVER_LINE = 0.0028
_TEXT_HEIGHT = 0.0035


def test_spigot_dia_text_clears_the_overall_length_witness() -> None:
    # 2026-10-12 farm sheet: the overall length's witness hangs down the
    # spigot face and ran through the Ø9.00 text centred 12 mm off the face.
    face_x = drawing._side_x(geom.SPIGOT_FACE_X)
    x, _y = drawing.SIDE_KEEP["SpigotDia"]
    assert x - drawing.SPIGOT_DIA_TEXT_HALF_WIDTH > face_x + 0.003
    # The overall length stays under the view, the groove's radius over it.
    assert drawing.SIDE_KEEP["OverallLength"][1] < drawing._SIDE_BOTTOM
    assert drawing.SIDE_KEEP["GrooveRadius"][1] > drawing._SIDE_TOP


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
    hex_y = drawing.SIDE_KEEP["HexLength"][1]
    assert drawing.SIDE_KEEP["GrooveStation"][1] - hex_y > 0.0099


def test_end_view_flats_read_above_the_hex_clear_of_the_tap_leader() -> None:
    scale = drawing._S / 1000.0
    centre_x, centre_y = drawing.END_CENTER
    flat_top = centre_y + geom.HEX_CORNER_RADIUS / 2.0 * scale
    hex_top = centre_y + geom.HEX_CORNER_RADIUS * scale
    assert set(drawing.END_KEEP) == {"HexAf"}
    af_x, af_y = drawing.END_KEEP["HexAf"]
    # It witnesses the near flat from its top corner: above the hex, mid-span.
    assert hex_top < af_y - _TEXT_OVER_LINE
    assert af_x == centre_x
    # The tap's shoulder runs under the flat's top corner, where no witness
    # hangs.
    shoulder_y = drawing.TAP_CALLOUT_XY[1] - drawing._TAP_CALLOUT_SHOULDER_DROP
    assert shoulder_y < flat_top - 0.004


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
    assert [_arg_names(call) for call in proofs] == [["adapter", "end", "tap_drill"]]
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
    assert 1 <= len(lines) <= 4
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

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
        f"ROD BORE THROUGH CORNERS, CENTRED; BORE TO FLAT WALL {stated} MIN",
        "HOLD ON FLATS; CENTRE-DRILL ON CORNER BEFORE DRILL/REAM.",
        "4-40: PLUG TAP, 3-5 THREAD CHAMFER. THREAD ENDS AT ROD BORE.",
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
    assert f"{spec.TAP_TOOL_NOTE} {spec.TAP_EXTENT_NOTE}" in spec.DRAWING_NOTES.splitlines()


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
    assert spec.TAP_EXTENT_NOTE == "THREAD ENDS AT ROD BORE."
    assert "REF" not in spec.DRAWING_NOTES
    assert f"{spec.TAP_TOOL_NOTE} {spec.TAP_EXTENT_NOTE}" in spec.DRAWING_NOTES.splitlines()
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
    # Both clear the overall length's witness down the face; the smaller
    # stands inside, so its extension lines end short of the larger's line.
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
    # Overall length stays under the view.  The radius shoulder is below the
    # spigot mouth, but its text sits above the Ø's top witness.
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
    hex_y = drawing.SIDE_KEEP["HexLength"][1]
    assert drawing.SIDE_KEEP["GrooveStation"][1] - hex_y > 0.0099


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
    assert 1 <= len(lines) <= 4
    assert len(lines) == 4
    assert max(map(len, lines)) <= 68
    assert spec.BORE_TOOL_NOTE in lines
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


def test_corner_bore_notes_are_model_owned_and_preserve_the_tap_facts() -> None:
    assert part.DRAWING_NOTES is spec.DRAWING_NOTES
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '{"Manufacturing Notes": DRAWING_NOTES}' in source
    assert spec.BORE_WALL_NOTE == (
        f"ROD BORE THROUGH CORNERS, CENTRED; BORE TO FLAT WALL "
        f"{spec.BORE_WALL_STATED_MIN:.2f} MIN"
    )
    assert spec.BORE_TOOL_NOTE == (
        "HOLD ON FLATS; CENTRE-DRILL ON CORNER BEFORE DRILL/REAM."
    )


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
        diametric: bool = False, arc_persists: bool = True, gap_result: object = True,
    ) -> None:
        self.dimension = SimpleNamespace(
            FullName=f"{name}@{feature}@mg-output-fixture.SLDPRT",
            SystemValue=value_mm / 1000.0,
        )
        self.Type2 = kind
        self.Diametric = diametric
        self._arc = True
        self.arc_persists = arc_persists
        self.gap_result = gap_result
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
        assert type(index) is int and index == 1
        assert use_doc is False
        assert type(gap) is float
        self.gaps.append((index, use_doc, gap))
        return self.gap_result

    def GetDisplayData(self) -> object | None:
        return self.data


def _radial_display(**options) -> _NativeDisplay:
    return _NativeDisplay("GrooveRadius", "GrooveProfile", geom.GROOVE_RADIUS, **options)


def _station_display(**options) -> _NativeDisplay:
    return _NativeDisplay("GrooveStation", "GrooveProfile", spec.GROOVE_STATION, **options)


def _overall_display(**options) -> _NativeDisplay:
    return _NativeDisplay(
        "OverallLength", "TurnedProfile", geom.OVERALL_LENGTH, kind=2, **options
    )


def test_native_radius_style_and_only_named_witness_gaps_are_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rebuilds = _projection_fakes(monkeypatch)
    radius, station, overall = _radial_display(), _station_display(), _overall_display()
    drawing._place_groove_radius(
        object(), _RootAnnotation(radius), _RootAnnotation(station), _RootAnnotation(overall)
    )
    assert radius.ArcExtensionLineOrOppositeSide is False
    assert radius.gaps == []
    assert station.gaps == [(1, False, drawing.GROOVE_STATION_GAP)]
    assert overall.gaps == [(1, False, drawing.OVERALL_FACE_WITNESS_GAP)]
    assert drawing.EXTENSION_START_GAP == 0.001
    assert rebuilds == ["place fixture material-arc radius"]


@pytest.mark.parametrize("result", [False, None, 1])
def test_station_witness_gap_requires_native_bool_success(
    monkeypatch: pytest.MonkeyPatch, result: object
) -> None:
    _projection_fakes(monkeypatch)
    with pytest.raises(RuntimeError, match="refused its centre-side witness gap"):
        drawing._place_groove_radius(
            object(), _RootAnnotation(_radial_display()),
            _RootAnnotation(_station_display(gap_result=result)),
            _RootAnnotation(_overall_display()),
        )


@pytest.mark.parametrize("options", [{"kind": 6}, {"diametric": True}, {"arc_persists": False}])
def test_native_radius_style_refuses_nonradius_or_ignored_false_property(
    monkeypatch: pytest.MonkeyPatch, options: dict,
) -> None:
    _projection_fakes(monkeypatch)
    with pytest.raises(RuntimeError):
        drawing._place_groove_radius(
            object(), _RootAnnotation(_radial_display(**options)),
            _RootAnnotation(_station_display()), _RootAnnotation(_overall_display()),
        )


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


@pytest.mark.parametrize("result", [False, None, 1])
def test_overall_face_witness_gap_requires_native_bool_success(
    monkeypatch: pytest.MonkeyPatch, result: object,
) -> None:
    _projection_fakes(monkeypatch)
    with pytest.raises(RuntimeError, match="refused its face-side witness gap"):
        drawing._place_groove_radius(
            object(), _RootAnnotation(_radial_display()), _RootAnnotation(_station_display()),
            _RootAnnotation(_overall_display(gap_result=result)),
        )


# Actual native14 task.log: the full 29 mm shoulder, not the old test's
# 1.6 mm elbow stub, crosses the face witness at (160.4, 196.0) mm.
_NATIVE14_RADIUS_SHOULDER = ((0.1571, 0.1960), (0.1861, 0.1960))
_NATIVE14_OVERALL_FACE_WITNESS = ((0.1604, 0.1970), (0.1604, 0.1252))
_NATIVE14_RADIUS_TIP = (0.1516288709508015, 0.19752974314855273)


# Native15 audit (20261013T091530503Z): printed glyphs, not the wider COM row.
_NATIVE15_RADIUS_KEEP = (0.1724, 0.1988)
_NATIVE15_RADIUS_TEXT_BOX = Box(0.1604289, 0.1969558, 0.1845905, 0.2005212)
_NATIVE15_SPIGOT_TOP_WITNESS = ((0.1614, 0.198), (0.2003, 0.198))
# Every native extension line on the sheet.  The bore/tap radial leaders
# and radius shoulder are not extensions; no dimension's extension is omitted.
_NATIVE15_EXTENSION_LINES = {
    "RodStation": [
        ((0.0896, 0.179), (0.0896, 0.1471719)),
        ((0.1096, 0.179), (0.1096, 0.1471719)),
    ],
    "HexLength": [
        ((0.0896, 0.181), (0.0896, 0.2222719)),
        ((0.1336, 0.199), (0.1336, 0.2222719)),
    ],
    "OverallLength": [
        ((0.0896, 0.179), (0.0896, 0.1251719)),
        ((0.1604, 0.1936), (0.1604, 0.1251719)),
    ],
    "GrooveStation": [
        ((0.0896, 0.181), (0.0896, 0.2322719)),
        ((0.147, 0.2018), (0.147, 0.2322719)),
    ],
    "GrooveRootDia": [
        ((0.148, 0.166), (0.1803, 0.166)),
        ((0.148, 0.194), (0.1803, 0.194)),
    ],
    "SpigotDia": [
        ((0.1614, 0.162), (0.2003, 0.162)),
        _NATIVE15_SPIGOT_TOP_WITNESS,
    ],
    "HexAf": [
        ((0.2500015, 0.19905), (0.226003, 0.19905)),
        ((0.2719985, 0.16095), (0.226003, 0.16095)),
    ],
}


def _proposed_radius_text_box() -> Box:
    dx, dy = (drawing.RADIUS_TEXT_XY[i] - _NATIVE15_RADIUS_KEEP[i] for i in range(2))
    old = _NATIVE15_RADIUS_TEXT_BOX
    return Box(old.xmin + dx, old.ymin + dy, old.xmax + dx, old.ymax + dy)


def _audit_line(stroke: tuple) -> AuditSegment:
    (x0, y0), (x1, y1) = stroke
    return AuditSegment(x0, y0, x1, y1, "ext-line")


def test_radius_text_clears_every_native15_sheet_extension_at_the_new_keep() -> None:
    box = _proposed_radius_text_box()
    assert (box.xmin, box.ymin, box.xmax, box.ymax) == pytest.approx((
        0.154952880015449, 0.1985339, 0.179114480015449, 0.2020993,
    ))
    extensions = {name: list(strokes) for name, strokes in _NATIVE15_EXTENSION_LINES.items()}
    extensions["OverallLength"] = _overall_witness_ink()
    distances = {
        name: min(segment_box_distance(_audit_line(stroke), box) for stroke in strokes)
        for name, strokes in extensions.items()
    }
    assert sum(len(strokes) for strokes in extensions.values()) == 14
    assert all(distance > 0.0 for distance in distances.values())
    assert min(distances.values()) == pytest.approx(0.0005339)
    assert distances["SpigotDia"] == pytest.approx(0.0005339)
    assert distances["GrooveRootDia"] == pytest.approx(0.0045339)
    assert distances["GrooveStation"] == pytest.approx(0.007952880015449)
    assert distances["OverallLength"] == pytest.approx(0.0033339)
    # In this native shoulder convention, a material-arc elbow must stay
    # below the mouth.  Even at the mouth, the glyph-to-witness gap is under
    # 2 mm; the ≥2 mm requirement remains strict for the actual leader ink.
    glyph_above_shoulder = _NATIVE15_RADIUS_TEXT_BOX.ymin - 0.1960219
    assert glyph_above_shoulder == pytest.approx(0.0009339)
    assert glyph_above_shoulder < drawing.RADIUS_STATION_CLEARANCE


def _native15_radius_spigot_dump(*, proposed: bool = False) -> dict:
    """Replay the actual COM row, PDF glyph box and both Ø9 witnesses."""
    keep = drawing.RADIUS_TEXT_XY if proposed else _NATIVE15_RADIUS_KEEP
    dx, dy = (keep[i] - _NATIVE15_RADIUS_KEEP[i] for i in range(2))
    if proposed:
        radius_ink, tip, _station, centre = _material_radius_ink()
    else:
        centre = (0.147, 0.1988)
        tip = (0.1516289, 0.1975297)
        radius_ink = [
            (tip, (0.1571236, 0.1960219)),
            (centre, tip),
            ((0.1571236, 0.1960219), (0.1860889, 0.1960219)),
        ]

    def line(stroke: tuple, *, z: float = 0.0004) -> list:
        (x0, y0), (x1, y1) = stroke
        return [0.0, 0.0, 0.0, 0.0, x0, y0, z, x1, y1, z]

    direction = tuple((tip[i] - centre[i]) / math.dist(tip, centre) for i in range(2))
    radius = {
        "type": 4, "name": "GrooveRadius", "visible": 1, "owner_type": 0,
        "pos": [*keep, 0.0004],
        "display": {
            "lines": [line(stroke) for stroke in radius_ink],
            "arrows": [[*tip, 0.0004, *direction, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, -1.0]],
            "texts": [{
                "t": " R1.20 ±0.05 ", "pos": [0.1587111 + dx, 0.1960219 + dy, 0.0004],
                "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0273778,
            }],
        },
        "dim": {"hole_callout": False},
    }
    spigot = {
        "type": 4, "name": "SpigotDia", "visible": 1, "owner_type": 0,
        "pos": [0.1993, 0.185, -0.0004],
        "display": {
            "lines": [line(stroke, z=-0.0004) for stroke in [
                *_NATIVE15_EXTENSION_LINES["SpigotDia"],
                ((0.1993, 0.162), (0.1993, 0.1821951)),
                ((0.1993, 0.198), (0.1993, 0.1878049)),
            ]],
            "arrows": [
                [0.1993, 0.162, -0.0004, 0.0, 1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
                [0.1993, 0.198, -0.0004, 0.0, -1.0, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0],
            ],
            "texts": [
                {"t": " ", "pos": [0.1843889, 0.1822486, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0012931},
                {"t": "<MOD-DIAM>", "pos": [0.185682, 0.1821951, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0052784},
                {"t": "9.00 ±0.05 ", "pos": [0.1909604, 0.1822486, -0.0004], "h": 0.0035, "ref": 1, "ang": 0.0, "w": 0.0232507},
            ],
        },
        "dim": {"hole_callout": False},
    }
    old = _NATIVE15_RADIUS_TEXT_BOX
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
            ["R1.20±0.05", old.xmin + dx, old.ymin + dy, old.xmax + dx, old.ymax + dy],
            ["9.00±0.05", 0.1911891, 0.1831825, 0.2127127, 0.1867479],
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


def _material_radius_ink() -> tuple[list, tuple[float, float], list, tuple[float, float]]:
    """A complete 29 mm native-style shoulder at the new keep, not an elbow stub."""
    centre = (drawing._side_x(geom.GROOVE_X), drawing._side_y(geom.GROOVE_CENTRE_R))
    x, y = drawing.RADIUS_TEXT_XY
    elbow = (x - drawing.RADIUS_SHOULDER_RUN_IN, y - drawing.RADIUS_SHOULDER_DROP)
    radius = geom.GROOVE_RADIUS * drawing._S / 1000.0
    assert math.dist(centre, elbow) == pytest.approx(radius)
    tip = elbow
    assert tip == pytest.approx(drawing.RADIUS_MATERIAL_TIP_XY)
    shoulder = (elbow, (elbow[0] + math.dist(*_NATIVE14_RADIUS_SHOULDER), elbow[1]))
    ink = [(centre, tip), shoulder]
    station = [
        (
            (centre[0], centre[1] + drawing.GROOVE_STATION_GAP),
            (centre[0], drawing.SIDE_KEEP["GrooveStation"][1] - _TEXT_OVER_LINE),
        )
    ]
    return ink, tip, station, centre


def _overall_witness_ink() -> list:
    """Keep native14's lower endpoint; derive the two starts from the model."""
    end_y = _NATIVE14_OVERALL_FACE_WITNESS[1][1]
    free_x = drawing._side_x(geom.FREE_END_X)
    face_x = drawing._side_x(geom.SPIGOT_FACE_X)
    return [
        (
            (free_x, drawing.SIDE_CENTER[1] - drawing.EXTENSION_START_GAP),
            (free_x, end_y),
        ),
        (
            (
                face_x,
                drawing._side_y(geom.SPIGOT_DIA / 2.0) - drawing.OVERALL_FACE_WITNESS_GAP,
            ),
            (face_x, end_y),
        ),
    ]


def test_full_radius_shoulder_clears_both_overall_witnesses_at_the_new_keep() -> None:
    ink, tip, station, centre = _material_radius_ink()
    shoulder = ink[-1]
    old = _NATIVE14_OVERALL_FACE_WITNESS
    assert drawing.segments_cross(_NATIVE14_RADIUS_SHOULDER, old)
    assert not drawing.segments_cross(shoulder, old)
    assert shoulder[0][1] > max(point[1] for point in old)
    # Both endpoints are outside x160.4: an elbow-only assertion missed it.
    assert shoulder[0][0] < old[0][0] < shoulder[1][0]
    assert math.dist(*shoulder) == pytest.approx(0.029)
    assert shoulder[0][1] == pytest.approx(
        drawing.SIDE_KEEP["GrooveRadius"][1] - drawing.RADIUS_SHOULDER_DROP
    )
    assert old[0] == pytest.approx((
        drawing._side_x(geom.SPIGOT_FACE_X),
        drawing._side_y(geom.SPIGOT_DIA / 2.0) - drawing.EXTENSION_START_GAP,
    ))
    witnesses = _overall_witness_ink()
    face = witnesses[1]
    assert drawing.OVERALL_FACE_WITNESS_GAP == pytest.approx(0.0028)
    assert drawing.OVERALL_FACE_WITNESS_GAP >= drawing.EXTENSION_START_GAP >= 0.0
    assert face[0][1] == pytest.approx(0.1952)
    assert face[1] == pytest.approx(old[1])
    assert old[1][1] < face[0][1] < old[0][1]
    # New ink is a strict subset of the old witness, so this local gap
    # cannot add a collision with another dimension or text.
    for point in face:
        assert drawing.distance_to_point(old, point) == pytest.approx(0.0)
    assert math.dist(*face) == pytest.approx(0.0700)
    measured_clearance = drawing.distance_to_point(shoulder, face[0])
    assert measured_clearance == pytest.approx(
        drawing.RADIUS_STATION_CLEARANCE + drawing.RADIUS_INK_SLOP
    )
    assert measured_clearance >= drawing.RADIUS_STATION_CLEARANCE
    for witness in witnesses:
        assert not any(drawing.segments_cross(stroke, witness) for stroke in ink)
    assert drawing._radius_overall_witness_ink_problem(ink, witnesses) is None
    # The new ray is still on the genuine face-side material arc, not its
    # extension in air, and the station retains its exact 3 mm local gap.
    assert math.dist(tip, centre) == pytest.approx(geom.GROOVE_RADIUS * drawing._S / 1000.0)
    assert tip[0] > centre[0]
    assert drawing._side_y(geom.GROOVE_ROOT_DIA / 2.0) < tip[1] < drawing._side_y(geom.SPIGOT_DIA / 2.0)
    assert drawing.SIDE_KEEP["GrooveRadius"] == pytest.approx((0.166923980015449, 0.2003781))
    assert shoulder[0] == pytest.approx((0.151647580015449, 0.1976))
    assert shoulder[1] == pytest.approx((0.180647580015449, 0.1976))
    assert drawing._groove_radius_ink_problem(ink, tip, station, centre) is None
    assert drawing.GROOVE_STATION_GAP == 0.003
    assert drawing.RADIUS_STATION_CLEARANCE == 0.002
    assert drawing.RADIUS_INK_SLOP == 0.0004


def test_radius_material_arc_line_meets_the_full_shoulder_without_an_elbow_jog() -> None:
    ink, tip, station, centre = _material_radius_ink()
    assert len(ink) == 2
    assert ink[0] == (centre, tip)
    assert ink[1][0] == tip
    assert abs(ink[0][1][1] - ink[0][0][1]) > drawing.RADIUS_INK_SLOP
    assert math.dist(*ink[1]) == pytest.approx(0.029)
    assert drawing._groove_radius_ink_problem(ink, tip, station, centre) is None
    assert drawing._radius_overall_witness_ink_problem(ink, _overall_witness_ink()) is None


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing-shoulder", "no unique rebuilt horizontal shoulder"),
        ("missing-face", "no unique witness"),
        ("duplicate-free", "no unique witness"),
        ("short-witness", "does not reach its dimension line"),
        ("native14-gap", "gap did not reach the rebuilt ink"),
        ("cross-free", "not clear"),
    ],
)
def test_overall_witness_ink_requires_both_full_witnesses_and_clear_radius(
    case: str, message: str,
) -> None:
    ink, _tip, _station, _centre = _material_radius_ink()
    witnesses = _overall_witness_ink()
    if case == "missing-shoulder":
        ink.pop()
    elif case == "missing-face":
        witnesses.pop()
    elif case == "duplicate-free":
        witnesses.append(witnesses[0])
    elif case == "short-witness":
        witnesses[1] = (witnesses[1][0], (witnesses[1][1][0], drawing._SIDE_BOTTOM))
    elif case == "native14-gap":
        witnesses[1] = _NATIVE14_OVERALL_FACE_WITNESS
    else:
        elbow = (witnesses[0][0][0] - 0.002, drawing._SIDE_BOTTOM + 0.010)
        ink[-2] = (ink[-2][0], elbow)
        ink[-1] = (elbow, (ink[-1][1][0], elbow[1]))
        assert drawing.segments_cross(ink[-1], witnesses[0])
    problem = drawing._radius_overall_witness_ink_problem(ink, witnesses)
    assert problem is not None and message in problem


@pytest.mark.parametrize("clearance", [0.0019, 0.0021])
def test_overall_witness_measured_clearance_does_not_spend_the_ink_slop(
    clearance: float,
) -> None:
    ink, _tip, _station, _centre = _material_radius_ink()
    witnesses = _overall_witness_ink()
    y = witnesses[1][0][1] + clearance
    elbow = (ink[-1][0][0], y)
    ink[-2] = (ink[-2][0], elbow)
    ink[-1] = (elbow, (ink[-1][1][0], y))
    problem = drawing._radius_overall_witness_ink_problem(ink, witnesses)
    if clearance < drawing.RADIUS_STATION_CLEARANCE:
        assert problem is not None and "not clear" in problem
    else:
        assert problem is None


def test_material_radius_ink_and_separate_station_foot_pass() -> None:
    assert drawing._groove_radius_ink_problem(*_material_radius_ink()) is None


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("retry12-arrow", "not on the face-side material arc"),
        ("opposite-arc", "not on the face-side material arc"),
        ("off-circle", "not on the face-side material arc"),
        ("empty", "no attached leader ink"),
        ("disconnected", "no attached leader ink"),
        ("missing-witness", "no unique witness"),
        ("stale-gap", "did not reach the rebuilt ink"),
        ("near-foot", "not clear"),
        ("crossing", "not clear"),
    ],
)
def test_radius_ink_refuses_extension_air_detachment_and_station_ambiguity(
    case: str, message: str
) -> None:
    ink, tip, station, centre = _material_radius_ink()
    if case == "retry12-arrow":
        tip = (0.15154, 0.20036)  # scout's native12: v5.09, arc stops at v4.50
    elif case == "opposite-arc":
        tip = (2.0 * centre[0] - tip[0], tip[1])
    elif case == "off-circle":
        tip = (tip[0] + 0.001, tip[1])
    elif case == "empty":
        ink = []
    elif case == "disconnected":
        ink = [((0.170, 0.195), (0.180, 0.195))]
    elif case == "missing-witness":
        station = []
    elif case == "stale-gap":
        station[0] = ((centre[0], centre[1] + 0.001), station[0][1])
    elif case == "near-foot":
        ink.append((centre, (centre[0], centre[1] + 0.0015)))
    else:
        ink.append((centre, (centre[0], centre[1] + 0.004)))
    problem = drawing._groove_radius_ink_problem(ink, tip, station, centre)
    assert problem is not None and message in problem


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
) -> tuple[_RootAnnotation, _RootAnnotation, _RootAnnotation]:
    ink, tip, station_ink, centre = _material_radius_ink()
    display = _radial_display()
    display.ArcExtensionLineOrOppositeSide = False
    display.data = _ArrowData(tip, count=count, complete=complete)
    radius, station = _RadialAnnotation(display), _RootAnnotation(_station_display())
    radius.ink = ink
    overall = _RootAnnotation(_overall_display())
    overall.ink = _overall_witness_ink()
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, interface: obj)
    monkeypatch.setattr(
        drawing, "model_point_in_view", lambda adapter, view, xyz, *, label: centre
    )

    def segments(annotation: _RootAnnotation) -> list:
        if annotation is radius:
            return radius.ink
        if annotation is station:
            return station_ink
        assert annotation is overall
        return overall.ink

    monkeypatch.setattr(drawing, "dimension_segments", segments)
    return radius, station, overall


def test_rebuilt_radius_proof_reads_native_arrow_tip_and_model_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    drawing._prove_groove_radius(object(), object(), radius, station, overall)


@pytest.mark.parametrize("case", [
    "0.07mm-jog", "disconnected-shoulder", "other-centre", "missing-radial",
    "tilted-shoulder",
])
def test_native_direct_radius_junction_refuses_jogs_and_disconnected_or_wrong_ink(
    monkeypatch: pytest.MonkeyPatch, case: str,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    radial, shoulder = radius.ink
    tip = radial[1]
    if case == "0.07mm-jog":
        joint = (tip[0] + 0.00007, tip[1])
        radius.ink = [radial, (tip, joint), (joint, shoulder[1])]
    elif case == "disconnected-shoulder":
        radius.ink[1] = (
            (shoulder[0][0] + 0.00007, shoulder[0][1]),
            (shoulder[1][0] + 0.00007, shoulder[1][1]),
        )
    elif case == "other-centre":
        radius.ink[0] = ((radial[0][0] + 0.00007, radial[0][1]), tip)
    elif case == "missing-radial":
        radius.ink.pop(0)
    else:
        radius.ink[1] = (shoulder[0], (shoulder[1][0], shoulder[1][1] + 0.00007))
    assert drawing.RADIUS_JUNCTION_EPSILON == 1e-6
    # All existing material/station/overall proofs precede this stricter,
    # independent junction proof; none gets relaxed to accommodate a jog.
    with pytest.raises(RuntimeError, match="does not have a direct junction"):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


@pytest.mark.parametrize("reverse", [False, True])
def test_native_direct_junction_accepts_connected_ink_in_either_collection_order(
    monkeypatch: pytest.MonkeyPatch, reverse: bool,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    if reverse:
        radius.ink = [stroke[::-1] for stroke in reversed(radius.ink)]
    drawing._prove_groove_radius(object(), object(), radius, station, overall)


def test_native_direct_junction_accepts_exactly_zero_unprinted_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    radius.ink.append(((0.0, 0.0), (0.0, 0.0)))
    drawing._prove_groove_radius(object(), object(), radius, station, overall)


@pytest.mark.parametrize(
    ("residual_mm", "accepted"),
    [(0.0005, True), (0.000999, True), (0.001001, False), (0.07, False)],
)
def test_native_junction_normalizes_rounding_residuals_but_not_real_jogs(
    monkeypatch: pytest.MonkeyPatch, residual_mm: float, accepted: bool,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    radial, shoulder = radius.ink
    tip = radial[1]
    joint = (tip[0] + residual_mm / 1000.0, tip[1])
    radius.ink = [radial, (tip, joint), (joint, shoulder[1])]
    if accepted:
        drawing._prove_groove_radius(object(), object(), radius, station, overall)
    else:
        with pytest.raises(RuntimeError, match="does not have a direct junction"):
            drawing._prove_groove_radius(object(), object(), radius, station, overall)


@pytest.mark.parametrize("member", ["radial-centre", "shoulder-start", "shoulder-end-y"])
@pytest.mark.parametrize(("residual_mm", "accepted"), [(0.000999, True), (0.001001, False)])
def test_native_junction_endpoint_matches_use_the_same_calibration_boundary(
    monkeypatch: pytest.MonkeyPatch, member: str, residual_mm: float, accepted: bool,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    radial, shoulder = radius.ink
    delta = residual_mm / 1000.0
    if member == "radial-centre":
        radius.ink[0] = ((radial[0][0] + delta, radial[0][1]), radial[1])
    elif member == "shoulder-start":
        radius.ink[1] = ((shoulder[0][0] + delta, shoulder[0][1]), shoulder[1])
    else:
        radius.ink[1] = (shoulder[0], (shoulder[1][0], shoulder[1][1] + delta))
    if accepted:
        drawing._prove_groove_radius(object(), object(), radius, station, overall)
    else:
        with pytest.raises(RuntimeError, match="does not have a direct junction"):
            drawing._prove_groove_radius(object(), object(), radius, station, overall)


def test_numerically_zero_junction_residual_still_obeys_raw_overall_witness_clearance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    x, start_y = overall.ink[1][0]
    radius.ink.append(((x, start_y + 0.001), (x + 0.0000005, start_y + 0.001)))
    with pytest.raises(RuntimeError, match="does not clear the overall length.*not clear"):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


def test_rebuilt_radius_proof_refuses_native14_full_shoulder_crossing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    centre = (drawing._side_x(geom.GROOVE_X), drawing._side_y(geom.GROOVE_CENTRE_R))
    radius.ink = [
        (centre, _NATIVE14_RADIUS_TIP),
        (_NATIVE14_RADIUS_TIP, _NATIVE14_RADIUS_SHOULDER[0]),
        _NATIVE14_RADIUS_SHOULDER,
    ]
    radius.display.data = _ArrowData(_NATIVE14_RADIUS_TIP)
    overall.ink[1] = _NATIVE14_OVERALL_FACE_WITNESS
    with pytest.raises(RuntimeError, match="does not clear the overall length"):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


@pytest.mark.parametrize(
    ("name", "feature", "value"),
    [
        ("OtherLength", "TurnedProfile", geom.OVERALL_LENGTH),
        ("OverallLength", "OtherSketch", geom.OVERALL_LENGTH),
        ("OverallLength", "TurnedProfile", geom.OVERALL_LENGTH + 2e-5),
    ],
)
def test_rebuilt_overall_witness_proof_requires_the_genuine_model_dimension(
    monkeypatch: pytest.MonkeyPatch, name: str, feature: str, value: float,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    overall.display.dimension.FullName = f"{name}@{feature}@mg-output-fixture.SLDPRT"
    overall.display.dimension.SystemValue = value / 1000.0
    with pytest.raises(RuntimeError, match="wrong model dimension"):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


@pytest.mark.parametrize(
    ("count", "complete", "message"),
    [(0, True, "exactly one"), (2, True, "exactly one"), (1, False, "incomplete arrow")],
)
def test_rebuilt_radius_proof_refuses_missing_extra_or_unreadable_arrow(
    monkeypatch: pytest.MonkeyPatch, count: int, complete: bool, message: str
) -> None:
    radius, station, overall = _radius_readback_fakes(
        monkeypatch, count=count, complete=complete
    )
    with pytest.raises(RuntimeError, match=message):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


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
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    if case == "dangling":
        radius.dangling = True
    elif case == "sheet-owned":
        radius.OwnerType = 1
    elif case == "lost-style":
        radius.display.ArcExtensionLineOrOppositeSide = True
    else:
        radius.display.data = None
    with pytest.raises(RuntimeError):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


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
        drawing._place_groove_radius(
            object(), _RootAnnotation(display), _RootAnnotation(_station_display()),
            _RootAnnotation(_overall_display()),
        )


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
def test_radius_diametric_property_requires_measured_bool_false_before_write(
    monkeypatch: pytest.MonkeyPatch, readback: object,
) -> None:
    _projection_fakes(monkeypatch)
    display = _radial_display()
    display.Diametric = readback
    with pytest.raises(RuntimeError, match="genuine radial dimension"):
        drawing._place_groove_radius(
            object(), _RootAnnotation(display), _RootAnnotation(_station_display()),
            _RootAnnotation(_overall_display()),
        )


@pytest.mark.parametrize("readback", _NON_BOOL_READBACKS)
@pytest.mark.parametrize("member", ["Diametric", "ArcExtensionLineOrOppositeSide", "IsDangling"])
def test_rebuilt_radius_bool_readbacks_refuse_none_integer_boundmethod_and_object(
    monkeypatch: pytest.MonkeyPatch, readback: object, member: str,
) -> None:
    radius, station, overall = _radius_readback_fakes(monkeypatch)
    if member == "Diametric":
        radius.display.Diametric = readback
    elif member == "ArcExtensionLineOrOppositeSide":
        radius.display._arc = readback
    else:
        radius.dangling = readback
    with pytest.raises(RuntimeError):
        drawing._prove_groove_radius(object(), object(), radius, station, overall)


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

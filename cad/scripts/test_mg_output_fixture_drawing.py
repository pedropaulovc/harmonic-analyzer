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
        limit = spec.WALL_FLOOR if name == spec.BORE_WALL_NAME else spec.WALL_TARGET
        assert worst >= limit - 1e-9, (name, worst)


def test_bore_to_far_flat_is_the_named_shortfall_the_sheet_states() -> None:
    # Independent of the spec's arithmetic: the smallest flats the .XXX row
    # admits, the bore centre at its far limit from the near flat, the
    # largest reamed bore.
    smallest_af = round(geom.HEX_AF, 3) - printed_band_mm(3)
    farthest_centre = round(geom.BORE_FROM_FLAT, 2) + spec.POSITION_TOLERANCE
    largest_bore_r = (geom.ROD_BORE_DIA + spec.ROD_BORE_DIA_BAND[0]) / 2.0
    worst = smallest_af - farthest_centre - largest_bore_r
    assert spec.WALLS[spec.BORE_WALL_NAME][1] == pytest.approx(worst, abs=1e-9)
    assert spec.WALL_FLOOR <= worst < spec.WALL_TARGET
    stated = f"{spec.BORE_WALL_STATED_MIN:.2f}"
    assert float(stated) <= worst + 0.005
    assert stated in spec.DRAWING_NOTES
    policy = POLICY.read_text(encoding="utf-8").split("\n## Named exceptions", 1)[1]
    rows = [line for line in policy.splitlines() if line.startswith("| MHA-MG-006")]
    assert len(rows) == 1 and stated in rows[0]


def test_thumb_screw_tap_runs_axially_into_the_rod_bore() -> None:
    assert spec.TAP_SPEC is geom.TAP_SPEC
    assert geom.TAP_SPEC.kind == "tapped"
    assert geom.TAP_SPEC.end == "through_next"
    # It starts on the spigot face and reaches the bore within the part.
    assert 0.0 < geom.TAP_BREAKOUT_X < geom.SPIGOT_FACE_X
    assert geom.TAP_DRILL_DIA < geom.ROD_BORE_DIA
    # Full thread from the face to the bore, well over 1.5D.
    assert geom.TAP_LENGTH >= 1.5 * geom.THREAD_MAJOR


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


def test_end_view_dimensions_stack_above_the_hex_clear_of_the_tap_leader() -> None:
    scale = drawing._S / 1000.0
    centre_x, centre_y = drawing.END_CENTER
    flat_x = centre_x + geom.HEX_AF / 2.0 * scale
    flat_top = centre_y + geom.HEX_CORNER_RADIUS / 2.0 * scale
    hex_top = centre_y + geom.HEX_CORNER_RADIUS * scale
    bore_x, bore_y = drawing.END_KEEP["BoreFromFlat"]
    af_x, af_y = drawing.END_KEEP["HexAf"]
    # Both witness the near flat from its top corner: above the hex, the
    # bore's location inside the flats' line, so the bore axis' witness
    # stops short of the flats' text.
    assert hex_top < bore_y - _TEXT_OVER_LINE < af_y - _TEXT_OVER_LINE - 0.008
    assert af_x == centre_x
    # 2026-10-12 farm sheet: the 4.76 text centred on the bore axis carried
    # that witness through itself; it reads outside the span, right of the
    # flat.
    assert bore_x - drawing.STATION_TEXT_HALF_WIDTH > flat_x + 0.002
    # The tap's shoulder runs under the flat's top corner, where no witness
    # hangs any longer.
    shoulder_y = drawing.TAP_CALLOUT_XY[1] - drawing._TAP_CALLOUT_SHOULDER_DROP
    assert shoulder_y < flat_top - 0.004


def test_end_view_tap_takes_one_single_centre_mark() -> None:
    # 2026-10-12 farm sheet: AutoInsertCenterMarks2 marked the spigot's O.D.
    # and the concentric tap drill, one mark over the other.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "auto_center_marks(adapter, end" not in source
    assert drawing.CENTER_MARK_SINGLE == 2
    assert "CENTER_MARK_SINGLE, False, False" in source
    assert "expected one tap centre mark on the end view" in source
    assert "_mark_tap_axis(adapter, end, tap_drill)" in source
    assert "edge=tap_drill," in source


class _MarkDrawing:
    """IDrawingDoc as the mark sees it: InsertCenterMark3 is a dispatch-
    returning method, ClearSelection2 a void one."""

    def __init__(self, calls: list[tuple], mark: object | None) -> None:
        self._calls = calls
        self._mark = mark

    def InsertCenterMark3(self, style: int, propagate: bool, slot: bool) -> object | None:
        self._calls.append(("InsertCenterMark3", style, propagate, slot))
        return self._mark

    def ClearSelection2(self, all_selections: bool) -> None:
        self._calls.append(("ClearSelection2", all_selections))


class _MarkView:
    """IView's annotation census: a VARIANT array, or None when empty."""

    def __init__(self, calls: list[tuple], marks: tuple | None) -> None:
        self._calls = calls
        self._marks = marks

    def GetAnnotationsByType(self, annotation_type: int) -> tuple | None:
        self._calls.append(("GetAnnotationsByType", annotation_type))
        return self._marks


def _mark_tap(
    monkeypatch: pytest.MonkeyPatch, *, mark: object | None, marks: tuple | None
) -> list[tuple]:
    calls: list[tuple] = []
    drill = object()
    view = _MarkView(calls, marks)
    model = _MarkDrawing(calls, mark)

    def select(adapter, selected_view, entity_type, xy, *, label, entity):
        assert selected_view is view and entity is drill
        calls.append(("select", entity_type, xy))
        return entity

    def early_bound(obj, interface):
        calls.append(("bind", interface))
        return obj

    monkeypatch.setattr(drawing, "_select_view_entity", select)
    monkeypatch.setattr(drawing, "_early_bound", early_bound)
    drawing._mark_tap_axis(SimpleNamespace(currentModel=model), view, drill)
    return calls


def test_tap_mark_is_one_single_mark_on_the_selected_drill_circle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _mark_tap(monkeypatch, mark=object(), marks=(object(),))
    assert calls == [
        ("select", "EDGE", None),
        ("bind", "IDrawingDoc"),
        ("InsertCenterMark3", 2, False, False),
        ("ClearSelection2", True),
        ("bind", "IView"),
        ("GetAnnotationsByType", 13),
    ]


def test_tap_mark_refuses_a_refused_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError, match="failed to centre-mark the thumb-screw tap"):
        _mark_tap(monkeypatch, mark=None, marks=(object(),))


@pytest.mark.parametrize(
    ("marks", "found"), [(None, 0), ((), 0), ((object(), object()), 2)]
)
def test_tap_mark_refuses_any_census_but_one(
    monkeypatch: pytest.MonkeyPatch, marks: tuple | None, found: int
) -> None:
    with pytest.raises(
        RuntimeError, match=f"expected one tap centre mark on the end view, found {found}"
    ):
        _mark_tap(monkeypatch, mark=object(), marks=marks)


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

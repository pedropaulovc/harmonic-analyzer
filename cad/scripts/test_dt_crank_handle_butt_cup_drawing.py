"""Offline contracts for MHA-DT-35, the crank handle butt cup, and its drawing."""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import _config
import build_dt_crank_handle_butt_cup as part
import dt_crank_handle_butt_cup_notes as notes
import dt_crank_handle_butt_cup_spec as spec
import dt_crank_handle_pivot_screw_spec as screw
import draw_dt_crank_handle_butt_cup as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import (
    Box,
    Segment,
    point_segment_distance,
    segment_box_distance,
    segment_box_overlap_length,
)


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-handle-butt-cup.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-handle-butt-cup.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-handle-butt-cup_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_crank_handle_butt_cup"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_dt_crank_handle_butt_cup.py" in PRECISION_MIGRATED_DRAWINGS


def test_part_and_drawing_share_the_marked_dimension_contract() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SECTION_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.REFERENCE_DIMENSIONS == {"PocketDia"}
    # One symmetric band, plus the separate native radial MAX limit; the body
    # and pocket depth hold the title block's .XXX band.
    assert model_toleranced_dimensions(part) == {
        ("CupProfile", "BodyChamfer"): "BODY_CHAMFER_TOL",
    }
    assert spec.DRAWING_PRECISION_BY_NAME["BodyDia"] == 3
    assert spec.DRAWING_PRECISION_BY_NAME["PocketDepth"] == 3


def test_bottom_chamfer_clears_the_handle_counterbore_corner() -> None:
    # Owner ruling A on #1661: its smallest leg still clears the MHA-DT-08
    # counterbore floor's MAX corner radius.
    import dt_crank_handle_spec as handle

    assert spec.BODY_CHAMFER_MIN >= handle.INSIDE_CORNER_R_MAX
    assert notes.BODY_CHAMFER_CALLOUT.splitlines() == [
        "X 45 DEG",
        "CLEARS MHA-DT-08",
        "COUNTERBORE CORNER",
    ]


def test_floor_and_pocket_wall_hold_their_floors_at_the_printed_limits() -> None:
    # Owner ruling B on #1375 grows only the body around the unchanged pocket.
    assert not hasattr(spec, "FLANGE_DIA") and not hasattr(spec, "FLANGE_THICKNESS")
    # The floor is what the overall (.X) leaves after the banded pocket depth,
    # both from the face (re-review: one faced end).
    assert spec.FLOOR_THICKNESS_MIN >= spec.WALL_FLOOR_MM
    assert spec.POCKET_WALL_FLOOR_MM == spec.WALL_FLOOR_MM == WALL_FLOOR_MM
    assert spec.POCKET_WALL_MIN >= spec.POCKET_WALL_FLOOR_MM
    assert screw.CUP_POCKET_WALL_MIN == spec.POCKET_WALL_MIN
    assert screw.POCKET_MAX <= spec.POCKET_DIA_MAX
    assert spec.BODY_DIA - spec.BODY_DIA_TOL >= (
        spec.POCKET_DIA_MAX + 2.0 * spec.POCKET_WALL_FLOOR_MM - 1e-9
    )
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_ruling_b_keeps_the_head_pocket_and_axial_geometry() -> None:
    # The pocket is bored to suit the head with its diametral clearance.
    low, high = spec.POCKET_CLEARANCE
    assert spec.POCKET_DIA == pytest.approx(screw.HEAD_DIA + low / 2.0 + high / 2.0)
    assert spec.POCKET_DIA_MAX >= screw.HEAD_DIA + screw.HEAD_DIA_TOL + high
    assert spec.FLOOR_THICKNESS == pytest.approx(spec.OVERALL_LENGTH - spec.POCKET_DEPTH)
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_half_inch_stock_cleans_up_over_the_largest_body() -> None:
    # Owner ruling B on #1375 preserves both low-carbon steel alternatives.
    row = _config.parts("dt-crank-handle-butt-cup")
    for field in ("material", "material_specification"):
        for requirement in ("1/2 in", "12L14", "1018"):
            assert requirement in row[field]
    assert spec.STOCK_DIA == pytest.approx(0.5 * 25.4)
    assert spec.BODY_DIA + spec.BODY_DIA_TOL < spec.STOCK_DIA - 0.2


def test_head_sits_recessed_and_end_play_is_fitted() -> None:
    # Codex P2 on #1139 (user ruling 2026-09-30): the banded pocket depth over
    # the banded head keeps the head below the face with the handle pushed to
    # the arm at the widest end play.
    assert screw.HEAD_RECESS_WORST > 0.0
    assert screw.HEAD_RECESS_NOMINAL > screw.HEAD_RECESS_WORST
    assert screw.SHOULDER_LENGTH == pytest.approx(
        screw.HANDLE_STACK_NOMINAL + screw.END_PLAY_NOMINAL
    )


def test_pocket_and_floor_hole_read_on_a_section() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view(" in source
    assert "set_hidden_lines_visible" not in source
    assert "create_section_axis_centerline(" in source
    # R5's confirmed projection finding: the view at the left must show the
    # chamfered floor end, not the counterbore end.  Reversing the cut with
    # the parent view preserves the existing +X-right section and keeps.
    assert 'str(SOURCE), "*Left", *END_CENTER' in source
    assert drawing.END_CENTER[0] < drawing.SECTION_CENTER[0]
    assert drawing.CUT_START[0] == drawing.CUT_END[0] == drawing.END_CENTER[0]
    assert drawing.CUT_START[1] > drawing.CUT_END[1]


def test_floor_corner_retains_its_native_functional_limit() -> None:
    assert spec.POCKET_FLOOR_CORNER_R_MAX <= spec.POCKET_CLEARANCE[0] / 2
    assert spec.POCKET_FLOOR_CORNER_R_BAND == (0.0, -spec.POCKET_FLOOR_CORNER_R_MAX)
    assert spec.POCKET_FLOOR_CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert "PocketFloorRadius" in spec.DRAWING_DIMENSIONS["CupProfile"]
    assert "PocketFloorRadius" not in spec.REFERENCE_DIMENSIONS


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("dt-crank-handle-butt-cup")
    assert row["number"] == "MHA-DT-35"
    assert row["title"] == "Crank Handle Butt Cup"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        drawing.ISO_NOTE_POS,
        drawing.CAPTION_XY,
    ):
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070)
    assert drawing.END_CENTER[0] + drawing.BODY_R < drawing.SECTION_KEEP["FloorHoleDia"][0] - 0.005
    assert drawing.SECTION_KEEP["PocketDia"][0] + 0.020 < drawing.ISO_NOTE_POS[0]


def test_cup_is_one_configuration_the_oak_rounds_clear_of() -> None:
    # Local review of fbf82ad96 (recommended option taken when the question
    # timed out): with the cup's possible offset in the stack the end round
    # could skim only ~0.001 off the steel, so it is turned on the oak only
    # and the cup keeps its flat face.  No INSTALLED configuration remains.
    import build_dt_drive_train_assembly as drive_train
    import dt_crank_handle_spec as handle

    assert not hasattr(spec, "INSTALLED_CONFIG")
    assert not hasattr(drive_train, "HANDLE_CUP_INSTALLED_CONFIG")
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "create_configuration" not in source
    # The oak round the largest counterbore, the crest turned its .XX band
    # small and the bore's eccentricity both ways, holds the .080 target plus
    # the .002 owner-ruling-B margin (#1375).
    assert handle.BUTT_WALL_DESIGN_MIN_MM == pytest.approx(WALL_TARGET_MM + 0.0508)
    assert handle.BUTT_WALL_MIN >= handle.BUTT_WALL_DESIGN_MIN_MM
    assert _config.parts("dt-crank-handle-butt-cup")["description"] == "CRANK HANDLE BUTT CUP"


@pytest.fixture
def cup_build(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Capture the real profile recipe, not a replacement geometric model."""
    entities: dict[str, tuple[str, tuple[float, ...]]] = {}
    dimensions: list[tuple[object, ...]] = []

    def success(data: object = None) -> SimpleNamespace:
        return SimpleNamespace(is_success=True, data=data)

    def entity(kind: str, *coordinates: float) -> SimpleNamespace:
        assert adapter.currentSketchManager.AddToDB
        key = f"{kind}_{len(entities)}"
        entities[key] = (kind, coordinates)
        return success(key)

    def dimension(*args: object) -> SimpleNamespace:
        dimensions.append(args)
        return success(f"Dim_{len(dimensions)}")

    adapter = SimpleNamespace(
        currentSketchManager=SimpleNamespace(AddToDB=False),
        _attempt=lambda read, default=None: read(),
        create_part=AsyncMock(return_value=success()),
        create_sketch=AsyncMock(return_value=success()),
        add_centerline=AsyncMock(side_effect=lambda *p: entity("axis", *p)),
        add_line=AsyncMock(side_effect=lambda *p: entity("line", *p)),
        add_arc=AsyncMock(side_effect=lambda *p: entity("arc", *p)),
        add_sketch_constraint=AsyncMock(return_value=success("constraint")),
        add_sketch_dimension=AsyncMock(side_effect=dimension),
        check_sketch_fully_defined=AsyncMock(
            return_value=success({"definition_state": "fully_defined"})
        ),
        exit_sketch=AsyncMock(return_value=success()),
        create_revolve=AsyncMock(return_value=success()),
    )
    helpers = {}
    for name in (
        "set_global", "drive_dimension", "force_rebuild", "volume_check", "name_bore_axis",
        "apply_material", "apply_color", "report_mass_properties",
        "save_part_and_images",
    ):
        helpers[name] = AsyncMock()
        monkeypatch.setattr(part, name, helpers[name])
    for name in (
        "name_last_feature", "set_dimension_symmetric_tolerance",
        "apply_package_model_units",
        "clear_dimensions_for_drawing", "mark_dimensions_for_drawing",
        "apply_drawing_precision", "apply_drawing_properties", "_pocket_floor_max_limit",
    ):
        helpers[name] = MagicMock()
        monkeypatch.setattr(part, name, helpers[name])

    async def diameter(_adapter, axis, line, position, name):
        return dimension(line, axis, "diameter", getattr(spec, {
            "BodyDia": "BODY_DIA", "PocketDia": "POCKET_DIA",
            "FloorHoleDia": "FLOOR_HOLE_DIA",
        }[name]))

    monkeypatch.setattr(part, "add_diametric_linear_dimension", diameter)
    named = {}

    def apply(rows, _adapter, feature):
        assert feature == "CupProfile"
        assert len(rows._rows) == len(dimensions)
        for (name, equation), arguments in zip(rows._rows, dimensions, strict=True):
            named[name] = (arguments, equation)
        return [
            (f"{name}@{feature}", equation)
            for name, (_arguments, equation) in named.items()
        ]

    monkeypatch.setattr(part.SketchDims, "apply", apply)
    asyncio.run(part.build(adapter))
    return SimpleNamespace(
        adapter=adapter, helpers=helpers, entities=entities, dimensions=named
    )


def test_profile_has_a_driving_tangent_quarter_arc_and_true_floor_depth(cup_build) -> None:
    captured = cup_build
    radius = spec.POCKET_FLOOR_CORNER_R_MAX
    depth = spec.POCKET_DEPTH
    pocket_r = spec.POCKET_DIA / 2.0
    arcs = [(name, points) for name, (kind, points) in captured.entities.items()
            if kind == "arc"]
    assert len(arcs) == 1
    arc, (cx, cy, sx, sy, ex, ey) = arcs[0]
    assert (cx, cy) == pytest.approx((radius - depth, pocket_r - radius))
    assert (sx, sy) == pytest.approx((radius - depth, pocket_r))  # wall tangent
    assert (ex, ey) == pytest.approx((-depth, pocket_r - radius))  # floor tangent
    assert math.hypot(sx - cx, sy - cy) == pytest.approx(radius)
    assert math.hypot(ex - cx, ey - cy) == pytest.approx(radius)
    # add_arc is CCW; the 90-degree sweep, not its 270-degree complement.
    sweep = (math.atan2(ey - cy, ex - cx) - math.atan2(sy - cy, sx - cx)) % math.tau
    assert sweep == pytest.approx(math.pi / 2)
    lines = {name: points for name, (kind, points) in captured.entities.items()
             if kind == "line"}
    floor = next(name for name, p in lines.items()
                 if p == pytest.approx(
                     (-depth, spec.FLOOR_HOLE_DIA / 2.0, -depth, pocket_r - radius)
                 ))
    wall = next(name for name, p in lines.items()
                if p == pytest.approx((radius - depth, pocket_r, 0.0, pocket_r)))
    face = next(name for name, p in lines.items()
                if p == pytest.approx((0.0, pocket_r, 0.0, spec.BODY_DIA / 2.0)))
    constraints = [call.args for call in captured.adapter.add_sketch_constraint.call_args_list]
    assert (floor, arc, "tangent") in constraints
    assert (arc, wall, "tangent") in constraints
    assert (floor, None, "vertical") in constraints
    assert (wall, None, "horizontal") in constraints
    assert not any(relation == "fix" for _first, _second, relation in constraints)
    assert captured.dimensions["PocketDepth"] == (
        (f"{face}.start", f"{floor}.start", "horizontal_distance", depth),
        '"PocketDepth"',
    )
    assert lines[wall][2] - lines[wall][0] == pytest.approx(depth - radius)
    assert captured.dimensions["PocketFloorRadius"] == (
        (arc, None, "radial", radius), '"PocketFloorRadius"',
    )
    assert any(
        call.args[1:] == ("PocketFloorRadius", f"{radius}mm")
        for call in captured.helpers["set_global"].call_args_list
    )
    assert any(
        call.args[1:] == ("PocketFloorRadius@CupProfile", '"PocketFloorRadius"')
        for call in captured.helpers["drive_dimension"].call_args_list
    )
    captured.helpers["_pocket_floor_max_limit"].assert_called_once_with(captured.adapter)
    captured.helpers["apply_drawing_precision"].assert_called_once_with(
        captured.adapter, spec.DRAWING_PRECISION
    )
    captured.helpers["mark_dimensions_for_drawing"].assert_called_once_with(
        captured.adapter, "CupProfile", spec.DRAWING_DIMENSIONS["CupProfile"]
    )
    captured.adapter.check_sketch_fully_defined.assert_awaited_once()
    assert captured.adapter.currentSketchManager.AddToDB is False


def test_bottom_chamfer_has_real_legs_and_a_sound_root_at_the_new_body(cup_build) -> None:
    chamfer, = (
        points for kind, points in cup_build.entities.values()
        if kind == "line" and points[0] != points[2] and points[1] != points[3]
    )
    body_r = spec.BODY_DIA / 2.0
    assert chamfer == pytest.approx((
        spec.BODY_CHAMFER - spec.OVERALL_LENGTH, body_r,
        -spec.OVERALL_LENGTH, body_r - spec.BODY_CHAMFER,
    ))
    assert abs(chamfer[2] - chamfer[0]) == pytest.approx(spec.BODY_CHAMFER)
    assert abs(chamfer[3] - chamfer[1]) == pytest.approx(spec.BODY_CHAMFER)
    # Smallest body, longest radial leg and largest drilled floor hole.
    root_radial_min = (
        (spec.BODY_DIA - spec.BODY_DIA_TOL) / 2.0
        - spec.BODY_CHAMFER_MAX
        - (spec.FLOOR_HOLE_DIA + drilled_oversize_mm(unit=spec.UNIT)) / 2.0
    )
    assert root_radial_min >= spec.WALL_FLOOR_MM


def test_model_properties_need_no_general_manufacturing_note(cup_build) -> None:
    # Owner ruling B on #1375 resolves the wall in geometry, not a note; the
    # 2026-11-01 ruling accepts its .060 as minor exception RV-01.
    properties = cup_build.helpers["apply_drawing_properties"].call_args.args[2]
    assert properties == {"Isometric View Note": notes.ISOMETRIC_VIEW_NOTE}
    assert not hasattr(notes, "DRAWING_NOTES")


def test_concave_floor_round_adds_the_exact_revolved_corner_material() -> None:
    # Independently integrate disks over the quarter arc; the angle substitution
    # avoids the square-root endpoint singularity of direct axial integration.
    radius = spec.POCKET_FLOOR_CORNER_R_MAX
    pocket_r = spec.POCKET_DIA / 2.0
    n = 1000
    step = math.pi / (2.0 * n)

    def disk(theta: float) -> float:
        profile_r = pocket_r - radius + radius * math.sin(theta)
        return math.pi * (pocket_r**2 - profile_r**2) * radius * math.sin(theta)

    filled = step / 3.0 * sum(
        (1 if index in (0, n) else 4 if index % 2 else 2) * disk(index * step)
        for index in range(n + 1)
    )
    assert filled > 0
    assert part.V_POCKET_FLOOR_CORNER == pytest.approx(filled, abs=1e-10)
    sharp = math.pi * (
        (spec.BODY_DIA / 2) ** 2 * spec.OVERALL_LENGTH
        - pocket_r**2 * spec.POCKET_DEPTH
        - (spec.FLOOR_HOLE_DIA / 2) ** 2 * spec.FLOOR_THICKNESS
        - spec.BODY_CHAMFER**2 * (spec.BODY_DIA / 2 - spec.BODY_CHAMFER / 3)
    )
    assert part.V_CUP == pytest.approx(sharp + filled, abs=1e-10)


_R_M = spec.POCKET_FLOOR_CORNER_R_MAX / 1000.0


def _native_radius() -> SimpleNamespace:
    tolerance = SimpleNamespace(
        Type=0,
        GetMinValue=MagicMock(return_value=-_R_M),
        GetMaxValue=MagicMock(return_value=0.0),
    )
    tolerance.SetValues = MagicMock(return_value=True)
    # Equation-owned does NOT imply DrivenState 2: the native reference flag
    # is false even when the equation reports DrivenState 1.
    return SimpleNamespace(
        SystemValue=_R_M, DrivenState=1, IsReference=MagicMock(return_value=False),
        Tolerance=tolerance,
    )


def test_model_floor_radius_sets_and_reads_back_native_max(monkeypatch) -> None:
    dimension = _native_radius()
    named = MagicMock(return_value=(object(), dimension))
    monkeypatch.setattr(part, "_named_dimension", named)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    adapter = object()
    part._pocket_floor_max_limit(adapter)
    named.assert_called_once_with(adapter, "CupProfile", "PocketFloorRadius")
    assert dimension.Tolerance.Type == 6
    dimension.Tolerance.SetValues.assert_called_once_with(-_R_M, 0.0)
    dimension.Tolerance.GetMinValue.assert_called_once()
    dimension.Tolerance.GetMaxValue.assert_called_once()


@pytest.mark.parametrize("fault", ["nominal", "reference", "reject", "type", "lower", "upper"])
def test_model_floor_radius_refuses_false_native_limits(monkeypatch, fault: str) -> None:
    dimension = _native_radius()
    tolerance = dimension.Tolerance
    if fault == "nominal":
        dimension.SystemValue = 0.00005
    elif fault == "reference":
        dimension.IsReference.return_value = True
    elif fault == "reject":
        tolerance.SetValues.return_value = False
    elif fault == "type":
        tolerance.SetValues.side_effect = lambda *_args: setattr(tolerance, "Type", 0) or True
    elif fault == "lower":
        tolerance.GetMinValue.return_value = -0.00005
    else:
        tolerance.GetMaxValue.return_value = 0.00005
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (object(), dimension))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    with pytest.raises(RuntimeError, match="PocketFloorRadius@CupProfile"):
        part._pocket_floor_max_limit(object())


def _imported_radius() -> SimpleNamespace:
    dimension = _native_radius()
    dimension.Tolerance.Type = 6
    return SimpleNamespace(
        dimension=dimension, Diametric=False, Type2=5, ShowParenthesis=False,
        GetDimension2=lambda _index: dimension,
        GetText=MagicMock(return_value=""),
        ArcExtensionLineOrOppositeSide=True, ArrowSide=0, SolidLeader=True,
    )


def test_imported_floor_radius_keeps_its_controlling_max_and_actual_arc(monkeypatch) -> None:
    display = _imported_radius()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    drawing._dress_pocket_floor_radius(
        SimpleNamespace(GetSpecificAnnotation=lambda: display)
    )
    assert display.ArcExtensionLineOrOppositeSide is False
    assert display.ArrowSide == 1
    assert display.SolidLeader is False


@pytest.mark.parametrize(
    "fault", [
        "diameter", "linear", "nominal", "reference", "parentheses",
        "native_parentheses", "type", "lower", "upper",
    ]
)
def test_imported_floor_radius_refuses_changed_native_semantics(monkeypatch, fault) -> None:
    display = _imported_radius()
    if fault == "diameter":
        display.Diametric = True
    elif fault == "linear":
        display.Type2 = 2
    elif fault == "nominal":
        display.dimension.SystemValue = 0.00005
    elif fault == "reference":
        display.dimension.IsReference.return_value = True
    elif fault == "parentheses":
        display.GetText.return_value = "("
    elif fault == "native_parentheses":
        display.ShowParenthesis = True
    elif fault == "type":
        display.dimension.Tolerance.Type = 0
    elif fault == "lower":
        display.dimension.Tolerance.GetMinValue.return_value = -0.00005
    else:
        display.dimension.Tolerance.GetMaxValue.return_value = 0.00005
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    with pytest.raises(RuntimeError, match="MHA-DT-35 PocketFloorRadius"):
        drawing._dress_pocket_floor_radius(
            SimpleNamespace(GetSpecificAnnotation=lambda: display)
        )


# Native r2 at 22821a1d2, leaf 20261019T131953.462543Z-db20eea3ec6447c0b3aa1b2fa338062b.
# These are the actual finding footprints recovered from layout-finding DEBUG
# records, not the previous idealized 22 mm centred box.  The records round
# sheet mm to one decimal; expand glyph boxes by 0.05 mm and reserve another
# 0.05 mm when measuring them against a rounded line.  Translations below are
# placement contracts, NOT evidence that the next native solver preserved them.
_R2_KEEP = {
    "PocketFloorRadius": (0.21775, 0.19075),
    "OverallLength": (0.225, 0.1975),
    "PocketDepth": (0.27825, 0.1365),
    "BodyChamfer": (0.17525, 0.2016),
    "PocketDia": (0.28425, 0.166),
}
_R2_RADIUS_GLYPHS = Box(0.20725, 0.18885, 0.22835, 0.19255)
_R2_OVERALL_GLYPHS = Box(0.22185, 0.19565, 0.22725, 0.19925)
_R2_DEPTH_GLYPHS = Box(0.26875, 0.14015, 0.28695, 0.14385)
_R2_RADIUS_SHOULDER = Segment(0.2315, 0.188, 0.2056, 0.188)
_R2_CHAMFER_WITNESS = Segment(0.2068, 0.1865, 0.2068, 0.1915)
_R2_CHAMFER_TAIL = Segment(0.2068, 0.1905, 0.2131, 0.1905)
_R2_OVERALL_BARB = Segment(0.2083, 0.1951, 0.2083, 0.1943)
_R2_POCKET_DIA_TAIL = Segment(0.2842, 0.1492, 0.2842, 0.1429)


def _r2_delta(name: str) -> tuple[float, float]:
    x, y = drawing.SECTION_KEEP[name]
    old_x, old_y = _R2_KEEP[name]
    return x - old_x, y - old_y


def _moved_r2_box(name: str, box: Box) -> Box:
    dx, dy = _r2_delta(name)
    return Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)


def _moved_r2_segment(name: str, segment: Segment) -> Segment:
    dx, dy = _r2_delta(name)
    return Segment(
        segment.x0 + dx, segment.y0 + dy, segment.x1 + dx, segment.y1 + dy
    )


def test_measured_r2_footprints_reproduce_every_new_collision() -> None:
    # The old test overlooked both the shoulder's full width and the actual
    # glyph top.  Retain failing controls for both text strikes, the shoulder
    # crossing, the foreign arrow, and the insufficient block separation.
    assert _R2_RADIUS_SHOULDER.length == pytest.approx(0.0259)
    assert segment_box_overlap_length(_R2_CHAMFER_TAIL, _R2_RADIUS_GLYPHS) > 0.005
    crossing = (0.2068, 0.188)
    assert point_segment_distance(crossing, _R2_RADIUS_SHOULDER) == pytest.approx(0)
    assert point_segment_distance(crossing, _R2_CHAMFER_WITNESS) == pytest.approx(0)
    assert segment_box_distance(_R2_OVERALL_BARB, _R2_RADIUS_GLYPHS) < 0.002
    assert _R2_OVERALL_GLYPHS.gap(_R2_RADIUS_GLYPHS) < 0.00357
    assert segment_box_overlap_length(_R2_POCKET_DIA_TAIL, _R2_DEPTH_GLYPHS) > 0.0008


def test_radius_full_native_shoulder_and_glyphs_clear_chamfer_and_overall() -> None:
    radius = _moved_r2_box("PocketFloorRadius", _R2_RADIUS_GLYPHS)
    shoulder = _moved_r2_segment("PocketFloorRadius", _R2_RADIUS_SHOULDER)
    chamfer_witness = _moved_r2_segment("BodyChamfer", _R2_CHAMFER_WITNESS)
    chamfer_tail = _moved_r2_segment("BodyChamfer", _R2_CHAMFER_TAIL)
    overall_barb = _moved_r2_segment("OverallLength", _R2_OVERALL_BARB)
    overall = _moved_r2_box("OverallLength", _R2_OVERALL_GLYPHS)
    # Two rounded line coordinates cost 0.10 mm; the expanded glyph box has
    # already paid its 0.05 mm.  These are actual required gaps, not slack.
    assert shoulder.box().gap(chamfer_witness.box()) >= 0.0021
    assert segment_box_distance(chamfer_tail, radius) >= 0.00205
    assert segment_box_distance(overall_barb, radius) >= 0.00205
    assert overall.gap(radius) >= 0.00357
    # Overall is now below the section; its full witnesses end at the
    # silhouette rather than passing through the radius's functional reason.
    overall_line_y = drawing.SECTION_KEEP["OverallLength"][1] - 0.0027781
    assert drawing.SECTION_CENTER[1] - drawing.BODY_R - overall_line_y >= 0.020
    # Full three-row ink recovered from rejected 84f04d2b PDF.  Its old
    # keep was (217.75, 201) mm; font metrics include the entire mate/reason,
    # not just the numeric row measured in r2.  Native proof remains required.
    radius_y = drawing.SECTION_KEEP["PocketFloorRadius"][1]
    reason = Box(0.19842, radius_y - 0.00880, 0.23708, radius_y + 0.00879)
    chamfer_top = 0.216
    assert reason.ymin - chamfer_top >= 0.00357
    assert reason.ymax < 0.2667
    corner_r = spec.POCKET_FLOOR_CORNER_R_MAX
    center_x = drawing.FACE_X - (spec.POCKET_DEPTH - corner_r) * drawing._S
    center_y = drawing.SECTION_CENTER[1] + (spec.POCKET_DIA / 2 - corner_r) * drawing._S
    x, y = drawing.SECTION_KEEP["PocketFloorRadius"]
    bearing = math.degrees(math.atan2(y - center_y, x - center_x))
    assert 90 < bearing < 180


def test_depth_upper_native_row_clears_the_entire_pocket_diameter_arrow_tail() -> None:
    # The nominal/band is the highest of the three native rows.  Clearing
    # only the PocketDia witness at y149.25 misses its 6.35 mm outside tail.
    depth = _moved_r2_box("PocketDepth", _R2_DEPTH_GLYPHS)
    tail = _moved_r2_segment("PocketDia", _R2_POCKET_DIA_TAIL)
    assert depth.ymax < min(tail.y0, tail.y1)
    assert segment_box_distance(tail, depth) >= 0.00205


def test_floor_hole_native_hung_rows_nest_without_either_dimension_crossing() -> None:
    # 031202 native GetPosition (136.75,141): the full DRILL THRU width is
    # 24.0285 mm LEFT of the keep.  Its value's two glyph runs span
    # keep_x-17.8861..keep_x-6.1424, not a symmetric box around the column.
    # The r2 position changed only X; retain this exact below-witness flow.
    x, y = drawing.SECTION_KEEP["FloorHoleDia"]
    drill = Box(x - 0.0240285, y - 0.005583, x, y - 0.002083)
    value = Box(x - 0.0178861, y - 0.0000267, x - 0.0061424, y + 0.0035267)
    axis_y = drawing.SECTION_CENTER[1]
    hole_r = spec.FLOOR_HOLE_DIA * drawing._S / 2
    lower_y, upper_y = axis_y - hole_r, axis_y + hole_r
    assert y < lower_y  # no unproved switch to native inline/centred text
    floor_x = drawing.SECTION_CENTER[0] - drawing.HALF_LENGTH
    assert floor_x - max(drill.xmax, value.xmax) >= 0.002
    # r2 BodyDia's lower text-break boundary is y160.4 (rounded); the new
    # value top y156.0267 has >4.3 mm air even after its 0.05 mm uncertainty.
    assert 0.16035 - value.ymax >= 0.00357
    body_x = drawing.SECTION_KEEP["BodyDia"][0]
    hole_line = Segment(x, drill.ymin, x, upper_y)
    for body_y in (axis_y - drawing.BODY_R, axis_y + drawing.BODY_R):
        body_witness = Segment(floor_x - 0.001, body_y, body_x - 0.001, body_y)
        assert segment_box_distance(hole_line, body_witness.box()) >= 0.002
        assert all(
            segment_box_distance(body_witness, box) >= 0.002
            for box in (drill, value)
        )
    # Conversely, both hole witnesses end right of the outboard body column.
    # The old r2 span x216.8..127.8 crossed that column at y154.5.
    for hole_y in (lower_y, upper_y):
        hole_witness = Segment(
            drawing.FACE_X - spec.POCKET_DEPTH * drawing._S - 0.001,
            hole_y,
            x - 0.001,
            hole_y,
        )
        assert hole_witness.box().xmin - body_x >= 0.002


def test_measured_layout_preserves_generous_views_and_asme_alignment() -> None:
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    assert drawing.VIEW_SCALE == (5, 1)
    assert drawing.ISO_SCALE == (4, 1)
    assert drawing.END_CENTER == (0.074, 0.165)
    assert drawing.SECTION_CENTER == (0.225, 0.165)
    assert drawing.ISO_CENTER == (0.368, 0.215)
    assert drawing.END_CENTER[1] == drawing.SECTION_CENTER[1]

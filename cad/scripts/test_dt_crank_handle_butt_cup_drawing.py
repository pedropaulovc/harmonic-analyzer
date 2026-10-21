"""Offline contracts for MHA-DT-35, the crank handle butt cup, and its drawing."""

from __future__ import annotations

import asyncio
from copy import deepcopy
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
    assert set(drawing.ALL_KEEP) == marked
    assert set(drawing.SECTION_KEEP).isdisjoint(drawing.MOUTH_DETAIL_KEEP)
    assert set(drawing.MOUTH_DETAIL_KEEP) == {"FloorHoleMouthChamfer"}
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.REFERENCE_DIMENSIONS == {"PocketDia"}
    assert drawing.DIMENSION_CALLOUTS == {
        "BodyChamfer": notes.BODY_CHAMFER_CALLOUT,
        "BodyDia": notes.BODY_FIT_CALLOUT,
        "FloorHoleDia": "DRILL THRU",
        "FloorHoleMouthChamfer": notes.FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT,
        "PocketDepth": notes.POCKET_DEPTH_CALLOUT,
        "PocketDia": notes.POCKET_FIT_CALLOUT,
    }
    # Three unchanged symmetric bands, plus separate native radial MAX and
    # mouth LIMIT controls tested below.
    assert model_toleranced_dimensions(part) == {
        ("CupProfile", "BodyDia"): "BODY_DIA_TOL",
        ("CupProfile", "PocketDepth"): "POCKET_DEPTH_TOL",
        ("CupProfile", "BodyChamfer"): "BODY_CHAMFER_TOL",
    }
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 2
    } == {"BodyDia", "PocketDepth", "FloorHoleMouthChamfer"}


def test_bottom_chamfer_clears_the_handle_counterbore_corner() -> None:
    # Owner ruling A on #1661: 0.3-0.5 X 45 DEG, so its smallest leg still
    # clears the MHA-DT-08 counterbore floor's R0.3 MAX corner.
    assert (spec.BODY_CHAMFER_MIN, spec.BODY_CHAMFER_MAX) == (0.3, 0.5)
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
    assert spec.FLOOR_THICKNESS_MIN == pytest.approx(1.7)
    assert spec.FLOOR_THICKNESS_MIN >= spec.WALL_FLOOR_MM
    assert spec.POCKET_WALL_FLOOR_MM == spec.WALL_FLOOR_MM == 1.5
    assert spec.POCKET_WALL_MIN == pytest.approx(1.5)
    assert spec.POCKET_WALL_MIN >= spec.POCKET_WALL_FLOOR_MM
    assert screw.CUP_POCKET_WALL_MIN == spec.POCKET_WALL_MIN
    assert screw.POCKET_MAX <= spec.POCKET_DIA_MAX
    assert (spec.BODY_DIA, spec.BODY_DIA_TOL) == (9.6, 0.10)
    assert spec.BODY_DIA == pytest.approx(
        spec.POCKET_DIA_MAX + 2.0 * spec.POCKET_WALL_FLOOR_MM + spec.BODY_DIA_TOL
    )
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


def test_ruling_b_keeps_the_head_pocket_and_axial_geometry() -> None:
    assert (screw.HEAD_DIA, screw.HEAD_DIA_TOL) == (6.0, 0.10)
    assert (spec.POCKET_DIA, spec.POCKET_DIA_MAX) == (6.3, 6.5)
    assert spec.POCKET_CLEARANCE == (0.2, 0.4)
    assert spec.OVERALL_LENGTH == 8.1
    assert spec.FLOOR_THICKNESS == pytest.approx(2.6)
    assert spec.FLOOR_HOLE_DIA == 4.2


def test_half_inch_stock_cleans_up_over_the_largest_body() -> None:
    # Owner ruling B on #1375 preserves both low-carbon steel alternatives.
    row = _config.parts("dt-crank-handle-butt-cup")
    for field in ("material", "material_specification"):
        for requirement in ("1/2 in", "12L14", "1018"):
            assert requirement in row[field]
    assert spec.STOCK_DIA == pytest.approx(0.5 * 25.4)
    assert spec.BODY_DIA + spec.BODY_DIA_TOL < spec.STOCK_DIA - 0.2


def test_head_sits_recessed_and_end_play_is_fitted() -> None:
    assert screw.HEAD_RECESS_NOMINAL == pytest.approx(1.0)
    # Codex P2 on #1139 (user ruling 2026-09-30): pocket 5.5 +/-0.10 over a
    # 4.0 +/-0.10 head keeps the head 0.3 below the face with the handle
    # pushed to the arm at the widest 1.00 end play; at 5.0 .X over 4.0 .X
    # it stood 1.6 proud.
    assert (spec.POCKET_DEPTH, spec.POCKET_DEPTH_TOL) == (5.5, 0.10)
    assert (screw.HEAD_LENGTH, screw.HEAD_LENGTH_TOL) == (4.0, 0.10)
    assert screw.HEAD_RECESS_WORST == pytest.approx(0.3)
    assert screw.END_PLAY_NOMINAL == pytest.approx(0.5)
    assert screw.SHOULDER_LENGTH == pytest.approx(screw.HANDLE_STACK_NOMINAL + 0.5)


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


def test_feature_callouts_name_the_mates_and_their_fit_acceptance() -> None:
    assert notes.HANDLE_NUMBER == _config.parts("dt-crank-handle")["number"]
    assert notes.SCREW_NUMBER == _config.parts("dt-crank-handle-pivot-screw")["number"]
    assert notes.SCREW_NAME in _config.parts("dt-crank-handle-pivot-screw")["title"].upper()
    # Historical MHA-DT-035 machinist ENFORCE r1: each band names its mate
    # at the callout (rule 4); the matched pocket fit states name, number, diametral
    # clearance and its hard limit.  The floor corner's maximum is a separate
    # model-owned radial dimension, not an unrelated axial callout.
    assert notes.BODY_FIT_CALLOUT == "EPOXY FIT IN MHA-DT-08"
    assert notes.POCKET_FIT_CALLOUT.splitlines() == [
        "BORE TO SUIT MHA-DT-32",
        "PIVOT SCREW HEAD, 0.2-0.4",
        "DIAMETRAL CLEARANCE,",
        "<MOD-DIAM>6.5 MAX",
    ]
    assert notes.POCKET_DEPTH_CALLOUT.splitlines() == [
        "KEEPS MHA-DT-32 HEAD",
        "BELOW FACE",
    ]
    assert spec.POCKET_FLOOR_CORNER_R_MAX == pytest.approx(0.1)
    assert spec.POCKET_FLOOR_CORNER_R_MAX <= spec.POCKET_CLEARANCE[0] / 2
    assert spec.POCKET_FLOOR_CORNER_R_BAND == (0.0, -0.1)
    assert spec.POCKET_FLOOR_CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert "PocketFloorRadius" in spec.DRAWING_DIMENSIONS["CupProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["PocketFloorRadius"] == 1
    assert "PocketFloorRadius" not in spec.REFERENCE_DIMENSIONS
    assert "turned clear of it" in _config.parts("dt-crank-handle-butt-cup")["process"]
    # The DT-08 and DT-32 specs import the cup spec; its prose lives in the
    # notes module so a wording edit never re-keys those parts.
    for name in ("DRAWING_NOTES", "ISOMETRIC_VIEW_NOTE", "FLOOR_HOLE_CALLOUT"):
        assert not hasattr(spec, name)


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("dt-crank-handle-butt-cup")
    assert row["number"] == "MHA-DT-35"
    assert row["title"] == "Crank Handle Butt Cup"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        *drawing.MOUTH_DETAIL_KEEP.values(),
        drawing.MOUTH_DETAIL_CAPTION,
        drawing.MOUTH_DETAIL_LETTER,
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
    # The oak round the largest counterbore, the crest turned its .X band
    # small and the bore's eccentricity both ways, holds the 2.0 target plus
    # the 0.05 owner-ruling-B margin (#1375).
    assert handle.BUTT_WALL_DESIGN_MIN_MM == 2.05
    assert handle.BUTT_WALL_MIN >= handle.BUTT_WALL_DESIGN_MIN_MM
    assert (
        handle.END_ROUND_CY - handle.GENERAL_1PL_TOL_MM / 2.0
        - 2.0 * handle.BORE_ECCENTRICITY
    ) == pytest.approx(
        handle.COUNTERBORE_DIA_MAX / 2.0 + handle.BUTT_WALL_DESIGN_MIN_MM
    )
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
        "clear_dimensions_for_drawing", "mark_dimensions_for_drawing",
        "apply_drawing_precision", "apply_drawing_properties", "_pocket_floor_max_limit",
        "_floor_hole_mouth_chamfer_limit",
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
    arcs = [(name, points) for name, (kind, points) in captured.entities.items()
            if kind == "arc"]
    assert len(arcs) == 1
    arc, (cx, cy, sx, sy, ex, ey) = arcs[0]
    assert (cx, cy) == pytest.approx((-5.4, 3.05))
    assert (sx, sy) == pytest.approx((-5.4, 3.15))  # wall tangent
    assert (ex, ey) == pytest.approx((-5.5, 3.05))  # floor tangent
    assert math.hypot(sx - cx, sy - cy) == pytest.approx(0.1)
    assert math.hypot(ex - cx, ey - cy) == pytest.approx(0.1)
    # add_arc is CCW; the 90-degree sweep, not its 270-degree complement.
    sweep = (math.atan2(ey - cy, ex - cx) - math.atan2(sy - cy, sx - cx)) % math.tau
    assert sweep == pytest.approx(math.pi / 2)
    lines = {name: points for name, (kind, points) in captured.entities.items()
             if kind == "line"}
    floor = next(name for name, p in lines.items()
                 if p == pytest.approx((-5.5, 2.35, -5.5, 3.05)))
    wall = next(name for name, p in lines.items()
                if p == pytest.approx((-5.4, 3.15, 0.0, 3.15)))
    face = next(name for name, p in lines.items()
                if p == pytest.approx((0.0, 3.15, 0.0, 4.8)))
    constraints = [call.args for call in captured.adapter.add_sketch_constraint.call_args_list]
    assert (floor, arc, "tangent") in constraints
    assert (arc, wall, "tangent") in constraints
    assert (floor, None, "vertical") in constraints
    assert (wall, None, "horizontal") in constraints
    assert not any(relation == "fix" for _first, _second, relation in constraints)
    assert captured.dimensions["PocketDepth"] == (
        (f"{face}.start", f"{floor}.start", "horizontal_distance", 5.5),
        '"PocketDepth"',
    )
    assert lines[wall][2] - lines[wall][0] == pytest.approx(5.4)
    assert captured.dimensions["PocketFloorRadius"] == (
        (arc, None, "radial", 0.1), '"PocketFloorRadius"',
    )
    assert any(
        call.args[1:] == ("PocketFloorRadius", "0.1mm")
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
    # Owner ruling B on #1375 changes the OD, not the 0.4 +/-0.1 chamfer.
    chamfer, = (
        points for kind, points in cup_build.entities.values()
        if kind == "line" and points == pytest.approx((-7.7, 4.8, -8.1, 4.4))
    )
    assert chamfer == pytest.approx((-7.7, 4.8, -8.1, 4.4))
    assert abs(chamfer[2] - chamfer[0]) == pytest.approx(spec.BODY_CHAMFER)
    assert abs(chamfer[3] - chamfer[1]) == pytest.approx(spec.BODY_CHAMFER)
    assert spec.BODY_CHAMFER_MIN >= 0.3
    assert spec.BODY_CHAMFER_MAX == 0.5
    # Smallest body, longest radial leg and largest drilled floor hole.
    root_radial_min = (
        (spec.BODY_DIA - spec.BODY_DIA_TOL) / 2.0
        - spec.BODY_CHAMFER_MAX - (spec.FLOOR_HOLE_DIA + 0.10) / 2.0
    )
    assert root_radial_min == pytest.approx(2.1)
    assert root_radial_min >= spec.WALL_FLOOR_MM


def test_model_properties_need_no_general_manufacturing_note(cup_build) -> None:
    # Owner ruling B on #1375 resolves the wall in geometry, not a note or exception.
    properties = cup_build.helpers["apply_drawing_properties"].call_args.args[2]
    assert properties == {"Isometric View Note": notes.ISOMETRIC_VIEW_NOTE}
    assert not hasattr(notes, "DRAWING_NOTES")
    assert not _config.parts("dt-crank-handle-butt-cup").get("machinist_exceptions")


def test_concave_floor_round_adds_the_exact_revolved_corner_material() -> None:
    # Independently integrate disks over the quarter arc; the angle substitution
    # avoids the square-root endpoint singularity of direct axial integration.
    radius = 0.1
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
    assert part.V_CUP == pytest.approx(
        sharp + filled - part.V_FLOOR_HOLE_MOUTH_CHAMFER, abs=1e-10
    )


def _native_radius() -> SimpleNamespace:
    tolerance = SimpleNamespace(
        Type=0,
        GetMinValue=MagicMock(return_value=-0.0001),
        GetMaxValue=MagicMock(return_value=0.0),
    )
    tolerance.SetValues = MagicMock(return_value=True)
    # Equation-owned does NOT imply DrivenState 2: the native reference flag
    # is false even when the equation reports DrivenState 1.
    return SimpleNamespace(
        SystemValue=0.0001, DrivenState=1, IsReference=MagicMock(return_value=False),
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
    dimension.Tolerance.SetValues.assert_called_once_with(-0.0001, 0.0)
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
    # Overall's full left/right witnesses rise with its line, so the complete
    # shoulder must stay between them, not merely put its elbow on one side.
    floor_x = drawing.SECTION_CENTER[0] - drawing.HALF_LENGTH
    assert shoulder.box().xmin - floor_x > 0.0001
    assert drawing.FACE_X - shoulder.box().xmax > 0.0001
    overall_line_y = drawing.SECTION_KEEP["OverallLength"][1] - 0.0027781
    assert overall_line_y - radius.ymax >= 0.00205
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


def test_option2_mating_requirements_and_widest_printed_mouth_limits() -> None:
    assert spec.MATING_SCREW_UNDER_HEAD_FILLET_MAX == 0.1
    assert spec.MATING_SCREW_HEAD_DIA_MIN == 5.9
    assert spec.MATING_SCREW_SHOULDER_DIA_MIN == 3.92
    assert spec.MATING_SCREW_HEAD_EDGE_BREAK_MIN == 0.11
    assert spec.MATING_SCREW_HEAD_EDGE_BREAK_MAX == 0.26
    assert spec.MATING_SCREW_HEAD_BEARING_FLOOR == 0.1
    assert spec.FLOOR_HOLE_MOUTH_CHAMFER == 0.25
    assert spec.FLOOR_HOLE_MOUTH_CHAMFER_BAND == (0.0, -0.14)
    assert spec.FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE == 3
    assert (spec.FLOOR_HOLE_MOUTH_CHAMFER_MIN, spec.FLOOR_HOLE_MOUTH_CHAMFER_MAX) == (0.11, 0.25)
    # The immediately wider hundredth fails positive air; .25 is the retained
    # cup mouth maximum, not an undocumented tightening or precision rescue.
    assert spec.FLOOR_HOLE_MOUTH_CHAMFER_MIN - 0.01 == pytest.approx(0.1)
    assert notes.FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX == " X 45 DEG"
    assert notes.FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT.splitlines() == [
        "CLEARS MHA-DT-32", "UNDER-HEAD FILLET",
    ]
    for name in ("FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT", "FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX"):
        assert not hasattr(spec, name)
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "import dt_crank_handle_pivot_screw_spec" not in source
    assert "from dt_crank_handle_pivot_screw_spec" not in source


def test_both_zero_gap_corners_clear_in_a_correlated_eccentric_state() -> None:
    head, shaft, hole, pocket = 5.90, 3.92, 4.30, 6.28
    offset = min((pocket - head) / 2.0, (hole - shaft) / 2.0)
    assert offset == pytest.approx(0.19)
    assert spec.POCKET_CLEARANCE[0] <= pocket - head <= spec.POCKET_CLEARANCE[1]
    assert hole / 2 - offset == pytest.approx(shaft / 2)
    assert pocket / 2 - offset == pytest.approx(head / 2)
    assert spec.HEAD_RUNNING_OFFSET_MAX == pytest.approx(offset)
    for radius, chamfer_min, actual_air in (
        (spec.MATING_SCREW_UNDER_HEAD_FILLET_MAX, spec.FLOOR_HOLE_MOUTH_CHAMFER_MIN, spec.UNDER_HEAD_INNER_NORMAL_AIR_MIN),
        (spec.POCKET_FLOOR_CORNER_R_MAX, spec.MATING_SCREW_HEAD_EDGE_BREAK_MIN, spec.UNDER_HEAD_OUTER_NORMAL_AIR_MIN),
    ):
        # Independent quarter-circle envelope, in coordinates measured from
        # the sharp corner: each material point satisfies x+y <= R.
        normal_airs = []
        for index in range(1001):
            theta = index * math.pi / 2000
            x = radius * (1.0 - math.cos(theta))
            y = radius * (1.0 - math.sin(theta))
            normal_airs.append((chamfer_min - x - y) / math.sqrt(2))
        assert min(normal_airs) == pytest.approx(0.007071067811865, abs=1e-14)
        assert actual_air == pytest.approx(min(normal_airs))
        assert actual_air > 0.0
    # A smaller hole at this same .19 offset is incompatible with the shaft.
    assert spec.FLOOR_HOLE_DIA_MIN / 2 - offset < shaft / 2
    assert spec.UNDER_HEAD_INNER_SEATED_AXIAL_AIR_MIN == pytest.approx(0.15)
    assert spec.UNDER_HEAD_OUTER_SEATED_AXIAL_AIR_MIN == pytest.approx(0.15)


def test_flat_annulus_separately_uses_the_maximum_break_extrema() -> None:
    flat = 5.9 / 2 - 0.26 - 4.3 / 2 - 0.19 - 0.25
    assert flat == pytest.approx(0.10)
    assert spec.HEAD_BEARING_RADIAL_CONCENTRIC_MIN == pytest.approx(0.29)
    assert spec.HEAD_BEARING_RADIAL_MIN == pytest.approx(flat)
    assert flat >= spec.MATING_SCREW_HEAD_BEARING_FLOOR
    assert spec.FLOOR_HOLE_STRAIGHT_LENGTH_MIN == pytest.approx(1.45)
    assert spec.FLOOR_ROOT_RADIAL_MIN == pytest.approx(2.10)
    # The corner-air proof uses MIN breaks; the available flat uses MAX
    # breaks.  They are distinct tolerance extrema, not one manufactured set.
    assert spec.MATING_SCREW_HEAD_EDGE_BREAK_MIN + spec.FLOOR_HOLE_MOUTH_CHAMFER_MIN == pytest.approx(0.22)
    assert spec.MATING_SCREW_HEAD_EDGE_BREAK_MAX + spec.FLOOR_HOLE_MOUTH_CHAMFER_MAX == pytest.approx(0.51)


@pytest.mark.parametrize(
    ("before", "after", "message"),
    [
        ("FLOOR_HOLE_MOUTH_CHAMFER_BAND = (0.0, -0.14)", "FLOOR_HOLE_MOUTH_CHAMFER_BAND = (0.0, -0.15)", "inner corner"),
        ("MATING_SCREW_HEAD_EDGE_BREAK_MIN = 0.11", "MATING_SCREW_HEAD_EDGE_BREAK_MIN = 0.1", "outer corner"),
        ("MATING_SCREW_HEAD_EDGE_BREAK_MAX = 0.26", "MATING_SCREW_HEAD_EDGE_BREAK_MAX = 0.27", "flat bearing"),
        ("MATING_SCREW_HEAD_BEARING_FLOOR = 0.1", "MATING_SCREW_HEAD_BEARING_FLOOR = 0.100001", "flat bearing"),
        ("MATING_SCREW_SHOULDER_DIA_MIN = 3.92", "MATING_SCREW_SHOULDER_DIA_MIN = 3.90", "flat bearing"),
        ("FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE = 3", "FLOOR_HOLE_MOUTH_CHAMFER_TOL_TYPE = 6", "native floor-hole"),
        ("MATING_SCREW_SEATED_GAP_MIN = 0.25", "MATING_SCREW_SEATED_GAP_MIN = 0.1", "seated gap"),
    ],
)
def test_cup_import_guards_reject_nonconforming_mating_or_mouth_limits(before, after, message) -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert source.count(before) == 1
    with pytest.raises(AssertionError, match=message):
        exec(compile(source.replace(before, after), spec.__file__, "exec"), {})


def test_floor_hole_mouth_has_two_real_legs_and_one_separate_global(cup_build) -> None:
    captured = cup_build
    mouth, = [
        name for name, (kind, p) in captured.entities.items()
        if kind == "line" and p == pytest.approx((-5.75, 2.1, -5.5, 2.35))
    ]
    for name, kind in (
        ("FloorHoleMouthChamfer", "horizontal_distance"),
        ("FloorHoleMouthChamferRise", "vertical_distance"),
    ):
        assert captured.dimensions[name] == (
            (f"{mouth}.start", f"{mouth}.end", kind, 0.25),
            '"FloorHoleMouthChamfer"',
        )
        assert any(call.args[1:] == (f"{name}@CupProfile", '"FloorHoleMouthChamfer"')
                   for call in captured.helpers["drive_dimension"].call_args_list)
    assert "FloorHoleMouthChamfer" in spec.DRAWING_DIMENSIONS["CupProfile"]
    assert "FloorHoleMouthChamferRise" not in spec.DRAWING_DIMENSIONS["CupProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["FloorHoleMouthChamfer"] == 2
    assert any(call.args[1:] == ("FloorHoleMouthChamfer", "0.25mm")
               for call in captured.helpers["set_global"].call_args_list)
    captured.helpers["_floor_hole_mouth_chamfer_limit"].assert_called_once_with(captured.adapter)
    assert any(kind == "line" and p == pytest.approx((-8.1, 2.1, -5.75, 2.1))
               for kind, p in captured.entities.values())
    for call in captured.helpers["volume_check"].call_args_list:
        assert call.args[2] == pytest.approx(part.V_CUP)


def test_mouth_chamfer_removes_the_exact_independently_integrated_volume() -> None:
    r, c = spec.FLOOR_HOLE_DIA / 2, spec.FLOOR_HOLE_MOUTH_CHAMFER
    n = 1000
    step = c / n
    removed = step / 3 * sum(
        (1 if i in (0, n) else 4 if i % 2 else 2)
        * math.pi * ((r + i * step) ** 2 - r**2)
        for i in range(n + 1)
    )
    assert removed > 0
    assert part.V_FLOOR_HOLE_MOUTH_CHAMFER == pytest.approx(removed, abs=1e-12)
    sharp = math.pi * (
        (spec.BODY_DIA / 2) ** 2 * spec.OVERALL_LENGTH
        - (spec.POCKET_DIA / 2) ** 2 * spec.POCKET_DEPTH
        - r**2 * spec.FLOOR_THICKNESS
        - spec.BODY_CHAMFER**2 * (spec.BODY_DIA / 2 - spec.BODY_CHAMFER / 3)
    )
    assert part.V_CUP == pytest.approx(sharp + part.V_POCKET_FLOOR_CORNER - removed, abs=1e-10)


def _native_mouth() -> tuple[SimpleNamespace, SimpleNamespace]:
    tolerance = SimpleNamespace(
        Type=0, SetValues=MagicMock(return_value=True),
        GetMinValue=MagicMock(return_value=-0.00014),
        GetMaxValue=MagicMock(return_value=0.0),
    )
    dimension = SimpleNamespace(
        FullName="FloorHoleMouthChamfer@CupProfile@test",
        SystemValue=0.00025, IsReference=MagicMock(return_value=False),
        Tolerance=tolerance,
    )
    display = SimpleNamespace(
        Type2=11, Diametric=False, ShowParenthesis=False, ShowDimensionValue=True,
        GetOverride=MagicMock(return_value=False),
        GetText=MagicMock(return_value=""), SetPrecision3=MagicMock(),
        GetPrimaryPrecision2=MagicMock(return_value=2),
        GetPrimaryTolPrecision2=MagicMock(return_value=2),
        GetDimension2=lambda _index: dimension,
    )
    return display, dimension


def test_model_mouth_chamfer_sets_and_reads_native_two_place_limit(monkeypatch) -> None:
    display, dimension = _native_mouth()
    named = MagicMock(return_value=(display, dimension))
    monkeypatch.setattr(part, "_named_dimension", named)
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    adapter = object()
    part._floor_hole_mouth_chamfer_limit(adapter)
    named.assert_called_once_with(adapter, "CupProfile", "FloorHoleMouthChamfer")
    assert dimension.Tolerance.Type == 3
    dimension.Tolerance.SetValues.assert_called_once()
    assert dimension.Tolerance.SetValues.call_args.args == pytest.approx(
        (-0.00014, 0.0), rel=0.0, abs=1e-12
    )
    display.SetPrecision3.assert_called_once_with(-1, -1, 2, -1)


@pytest.mark.parametrize("fault", ["nominal", "reference", "override", "hidden_value", "prefix", "suffix", "reject", "type", "lower", "upper", "precision", "tol_precision"])
def test_model_mouth_refuses_changed_native_limits_or_value(monkeypatch, fault) -> None:
    display, dimension = _native_mouth()
    if fault == "nominal":
        dimension.SystemValue = 0.0002
    elif fault == "reference":
        dimension.IsReference.return_value = True
    elif fault == "override":
        display.GetOverride.return_value = True
    elif fault in ("prefix", "suffix"):
        display.GetText.side_effect = lambda i: "0.11" if i == (1 if fault == "prefix" else 2) else ""
    elif fault == "hidden_value":
        display.ShowDimensionValue = False
    elif fault == "reject":
        dimension.Tolerance.SetValues.return_value = False
    elif fault == "type":
        dimension.Tolerance.SetValues.side_effect = lambda *_: setattr(dimension.Tolerance, "Type", 6) or True
    elif fault == "lower":
        dimension.Tolerance.GetMinValue.return_value = -0.00015
    elif fault == "upper":
        dimension.Tolerance.GetMaxValue.return_value = 0.00001
    elif fault == "precision":
        display.GetPrimaryPrecision2.return_value = 1
    else:
        display.GetPrimaryTolPrecision2.return_value = 1
    monkeypatch.setattr(part, "_named_dimension", lambda *_: (display, dimension))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    with pytest.raises(RuntimeError, match="FloorHoleMouthChamfer@CupProfile"):
        part._floor_hole_mouth_chamfer_limit(object())


def _imported_mouth() -> tuple[SimpleNamespace, SimpleNamespace]:
    display, dimension = _native_mouth()
    dimension.Tolerance.Type = 3
    display.GetText.side_effect = lambda i: {
        2: notes.FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX,
        4: notes.FLOOR_HOLE_MOUTH_CHAMFER_CALLOUT.replace("\n", "\r\n"),
    }.get(i, "")
    return SimpleNamespace(GetSpecificAnnotation=lambda: display), dimension


def test_imported_mouth_keeps_native_feature_limits_precision_and_reason(monkeypatch) -> None:
    annotation, _ = _imported_mouth()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    drawing._assert_floor_hole_mouth_chamfer(annotation)


@pytest.mark.parametrize("fault", ["type", "diameter", "feature", "reference", "parentheses", "override", "hidden_value", "prefix", "suffix", "above", "reason", "nominal", "tol_type", "lower", "upper", "precision", "tol_precision"])
def test_imported_mouth_refuses_wrong_native_owner_print_or_bounds(monkeypatch, fault) -> None:
    annotation, dimension = _imported_mouth()
    display = annotation.GetSpecificAnnotation()
    if fault == "type":
        display.Type2 = 5
    elif fault == "diameter":
        display.Diametric = True
    elif fault == "hidden_value":
        display.ShowDimensionValue = False
    elif fault == "feature":
        dimension.FullName = "FloorHoleMouthChamfer@OtherProfile@test"
    elif fault == "reference":
        dimension.IsReference.return_value = True
    elif fault == "parentheses":
        display.ShowParenthesis = True
    elif fault == "override":
        display.GetOverride.return_value = True
    elif fault in ("prefix", "suffix", "above", "reason"):
        old = display.GetText.side_effect
        index = {"prefix": 1, "suffix": 2, "above": 3, "reason": 4}[fault]
        display.GetText.side_effect = lambda i: "wrong" if i == index else old(i)
    elif fault == "nominal":
        dimension.SystemValue = 0.0002
    elif fault == "tol_type":
        dimension.Tolerance.Type = 6
    elif fault == "lower":
        dimension.Tolerance.GetMinValue.return_value = -0.00015
    elif fault == "upper":
        dimension.Tolerance.GetMaxValue.return_value = 0.00001
    elif fault == "precision":
        display.GetPrimaryPrecision2.return_value = 1
    else:
        display.GetPrimaryTolPrecision2.return_value = 1
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    with pytest.raises(RuntimeError, match="MHA-DT-35 FloorHoleMouthChamfer"):
        drawing._assert_floor_hole_mouth_chamfer(annotation)


@pytest.fixture
def mouth_detail(monkeypatch) -> SimpleNamespace:
    section = SimpleNamespace(name="SECTION A-A", Type=2, GetSection=lambda: object())
    fence = SimpleNamespace(GetLabelPosition=lambda: drawing.MOUTH_DETAIL_LETTER)
    detail = SimpleNamespace(Type=3, GetDisplayMode2=lambda: 2, GetDetail=lambda: fence)
    readback = SimpleNamespace(
        label="B", parent=section, detail_ratio=(20.0, 1.0), parent_ratio=(5.0, 1.0),
        parent_centre=(0.217125, 0.176125), parent_radius=0.004,
        crop=(0.297, 0.095, 0.329, 0.127),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "read_circular_detail_crop", lambda *_args, **_kw: readback)
    monkeypatch.setattr(drawing, "_mouth_model_reference", lambda *_: (1.0, 2.0, 3.0))
    monkeypatch.setattr(drawing, "model_point_in_view", lambda *_args, **_kw: (0.217125, 0.176125))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.name)
    return SimpleNamespace(section=section, detail=detail, fence=fence, readback=readback)


def test_native_mouth_detail_retains_actual_cut_parent_scale_and_crop(mouth_detail) -> None:
    f = mouth_detail
    assert drawing.MOUTH_DETAIL_LABEL != "A"
    assert drawing._assert_mouth_detail(object(), f.section, f.detail) is f.readback


@pytest.mark.parametrize("fault", ["uncut_parent", "missing_cut", "unsectioned_view", "hidden_edges", "wrong_parent", "label", "scale", "parent_scale", "profile_centre", "radius", "crop_position", "blank_field", "letter"])
def test_native_mouth_detail_refuses_hidden_geometry_or_changed_crop(mouth_detail, fault) -> None:
    f = mouth_detail
    if fault == "uncut_parent":
        f.section.Type = 6
    elif fault == "missing_cut":
        f.section.GetSection = lambda: None
    elif fault == "unsectioned_view":
        f.detail.Type = 6
    elif fault == "hidden_edges":
        f.detail.GetDisplayMode2 = lambda: 1
    elif fault == "wrong_parent":
        f.readback.parent = SimpleNamespace(name="OTHER")
    elif fault == "label":
        f.readback.label = "A"
    elif fault == "scale":
        f.readback.detail_ratio = (10.0, 1.0)
    elif fault == "parent_scale":
        f.readback.parent_ratio = (4.0, 1.0)
    elif fault == "profile_centre":
        f.readback.parent_centre = (0.218, 0.176125)
    elif fault == "radius":
        f.readback.parent_radius = 0.003
    elif fault == "crop_position":
        f.readback.crop = (0.298, 0.095, 0.330, 0.127)
    elif fault == "blank_field":
        f.readback.crop = (0.297, 0.086, 0.329, 0.136)  # centred but too tall
    else:
        f.fence.GetLabelPosition = lambda: (0.230, 0.173)
    with pytest.raises(RuntimeError, match="mouth detail"):
        drawing._assert_mouth_detail(object(), f.section, f.detail)


def test_mouth_model_reference_uses_the_actual_profile_frame(monkeypatch) -> None:
    inverse = object()
    transform = SimpleNamespace(Inverse=MagicMock(return_value=inverse))
    sketch = SimpleNamespace(ModelToSketchTransform=transform)
    feature = SimpleNamespace(GetSpecificFeature2=lambda: sketch)
    class ModelDocument:
        __slots__ = ()  # IModelDoc2 does not declare FeatureByName.

    class PartDocument:
        __slots__ = ("FeatureByName",)

        def __init__(self):
            self.FeatureByName = MagicMock(return_value=feature)

    model_document, part_document = ModelDocument(), PartDocument()
    section = SimpleNamespace(ReferencedDocument=model_document)
    point = SimpleNamespace(MultiplyTransform=MagicMock(return_value=SimpleNamespace(ArrayData=(0.0, 0.002225, 0.005625))))
    utility = SimpleNamespace(CreatePoint=MagicMock(return_value=point))
    adapter = SimpleNamespace(swApp=SimpleNamespace(GetMathUtility=lambda: utility))
    bindings = []

    def bind(value, interface):
        bindings.append((value, interface))
        if value is model_document:
            if interface == "IPartDoc":
                return part_document
            if interface == "IModelDoc2":
                return model_document
            raise AssertionError(f"unexpected document interface {interface}")
        return value

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    assert drawing._mouth_model_reference(adapter, section) == (0.0, 0.002225, 0.005625)
    part_document.FeatureByName.assert_called_once_with("CupProfile")
    assert (model_document, "IPartDoc") in bindings
    assert (model_document, "IModelDoc2") not in bindings
    with pytest.raises(AttributeError):
        model_document.FeatureByName("CupProfile")
    assert utility.CreatePoint.call_args.args[0] == pytest.approx((-0.005625, 0.002225, 0.0))
    point.MultiplyTransform.assert_called_once_with(inverse)


def test_mouth_detail_creation_uses_native_section_circle_and_unique_label(monkeypatch) -> None:
    section = SimpleNamespace(name="SECTION A-A", GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=object()))
    selected = SimpleNamespace(Select4=MagicMock(return_value=True))
    manager = SimpleNamespace(AddToDB=False, CreateCircle=MagicMock(return_value=selected))
    fence = SimpleNamespace(SetLabelPosition=MagicMock(), GetLabelPosition=lambda: drawing.MOUTH_DETAIL_LETTER)
    detail = SimpleNamespace(
        Position=(0.313, 0.111), UpdateViewDisplayGeometry=MagicMock(),
        SetViewPosition=MagicMock(return_value=True), GetDetail=lambda: fence,
    )
    drawing_doc = SimpleNamespace(
        ActivateView=MagicMock(return_value=True),
        CreateDetailViewAt4=MagicMock(return_value=detail),
    )
    selection = SimpleNamespace()
    model = SimpleNamespace(
        ClearSelection2=MagicMock(), SketchManager=manager,
        SelectionManager=SimpleNamespace(CreateSelectData=lambda: selection),
    )

    def math_point(values):
        point = SimpleNamespace(ArrayData=tuple(values))
        point.MultiplyTransform = lambda _transform: point
        return point

    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=math_point)),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: drawing_doc if value is model and interface == "IDrawingDoc" else value)
    monkeypatch.setattr(drawing, "double_array", lambda values: tuple(values))
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, _view: "SECTION A-A")
    monkeypatch.setattr(drawing, "_mouth_model_reference", lambda *_: (1, 2, 3))
    monkeypatch.setattr(drawing, "model_point_in_view", lambda _a, view, *_args, **_kw: (0.217125, 0.176125) if view is section else drawing.MOUTH_DETAIL_CENTER)
    monkeypatch.setattr(drawing, "native_circle_geometry", lambda *_args, **_kw: ((0.217125, 0.176125, 0.0), 0.004))
    for name in ("rebuild_drawing", "settle_detail_projection", "position_section_caption", "set_hidden_lines_removed", "_assert_mouth_detail"):
        monkeypatch.setattr(drawing, name, MagicMock())
    assert drawing._create_mouth_detail(adapter, section) is detail
    assert manager.AddToDB is False
    assert manager.CreateCircle.call_args.args == pytest.approx((0.217125, 0.176125, 0.0, 0.221125, 0.176125, 0.0))
    assert selection.View is section
    selected.Select4.assert_called_once_with(False, selection)
    drawing_doc.CreateDetailViewAt4.assert_called_once_with(
        0.313, 0.111, 0.0, 0, 20.0, 1.0, "B", 1, False, False, True, 5,
    )
    drawing.set_hidden_lines_removed.assert_called_once_with(adapter, detail)
    drawing._assert_mouth_detail.assert_called_once_with(adapter, section, detail)


def _ink_line(x0, y0, x1, y1):
    return [0, 0, 0, 0, x0, y0, 0, x1, y1, 0]


def _ink_dimension(name: str, x: float, y: float) -> dict:
    # Synthetic collected-primitive fixture, not evidence of a native render.
    texts = [("0.25", y + 0.004), ("0.11 X 45 DEG", y + 0.009),
             ("CLEARS MHA-DT-32", y + 0.014), ("UNDER-HEAD FILLET", y + 0.019)] if name == "FloorHoleMouthChamfer" else [(name, y + 0.004)]
    return {
        "name": name, "dimension_name": name, "owner_type": 0, "type": 4,
        "visible": 1, "display": {
            "texts": [{"t": text, "pos": [x, row_y, 0], "h": 0.0035, "w": 0.035 if name == "FloorHoleMouthChamfer" else 0.012, "ang": 0, "ref": 1} for text, row_y in texts],
            "lines": [_ink_line(x, y, x + 0.012, y)],
            "arrows": [[x, y, 0, 1, 0, 0, 0.001, 0.0005]],
        },
    }


@pytest.fixture
def mouth_ink_dump() -> dict:
    rows = [_ink_dimension(name, 0.04 + i * 0.04, 0.22)
            for i, name in enumerate(drawing.SECTION_KEEP)]
    rows.append(_ink_dimension("FloorHoleMouthChamfer", 0.365, 0.12))
    return {"sheet": "SHEET1", "views": [{"annotations": rows}], "sheet_annotations": [], "layers": {}}


def test_actual_mouth_ink_requires_every_printed_native_dimension(mouth_ink_dump) -> None:
    drawing._assert_mouth_annotation_ink([mouth_ink_dump], mouth_crop=(0.297, 0.095, 0.329, 0.127))


@pytest.mark.parametrize("fault", ["missing", "duplicate", "hidden", "hidden_layer", "owner", "missing_width", "nonfinite", "missing_arrow", "missing_witness", "missing_limits", "missing_reason", "malformed_arrow", "malformed_line", "malformed_leader", "malformed_inventory", "unsupported_ink", "read_error"])
def test_actual_mouth_ink_refuses_missing_or_unreadable_evidence(mouth_ink_dump, fault) -> None:
    dump = deepcopy(mouth_ink_dump)
    rows = dump["views"][0]["annotations"]
    mouth = rows[-1]
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(deepcopy(mouth))
    elif fault == "hidden":
        mouth["visible"] = 3
    elif fault == "hidden_layer":
        mouth["layer"] = "HIDDEN"
        dump["layers"] = {"HIDDEN": {"visible": True, "printable": False}}
    elif fault == "owner":
        mouth["owner_type"] = 1
    elif fault == "missing_width":
        mouth["display"]["texts"][0].pop("w")
    elif fault == "nonfinite":
        mouth["display"]["texts"][0]["pos"][0] = math.nan
    elif fault == "missing_arrow":
        mouth["display"].pop("arrows")
    elif fault == "missing_witness":
        mouth["display"].pop("lines")
    elif fault == "missing_limits":
        mouth["display"]["texts"][1]["t"] = "0.10 X 45 DEG"
    elif fault == "missing_reason":
        mouth["display"]["texts"].pop()
    elif fault == "malformed_arrow":
        mouth["display"]["arrows"].append([0])
    elif fault == "malformed_line":
        mouth["display"]["lines"].append([0])
    elif fault == "malformed_leader":
        mouth["leaders"] = [[0, 1, 2]]
    elif fault == "malformed_inventory":
        mouth["display"]["lines"] = "not native line rows"
    elif fault == "unsupported_ink":
        mouth["display"]["ellipses"] = [[1, 2, 3]]
    else:
        dump["read_errors"] = {"GetDisplayData": 1}
    with pytest.raises(RuntimeError, match="mouth annotation ink violations"):
        drawing._assert_mouth_annotation_ink([dump])


@pytest.mark.parametrize("kind", ["text", "witness", "arrow", "registered_leader", "crossing", "collinear", "border", "title_block", "crop_text", "crop_line"])
def test_actual_mouth_ink_rejects_real_primitive_collisions(mouth_ink_dump, kind) -> None:
    dump = deepcopy(mouth_ink_dump)
    foreign = _ink_dimension("FOREIGN", 0.30, 0.18)
    mouth = dump["views"][0]["annotations"][-1]
    if kind == "text":
        foreign["display"]["texts"][0]["pos"] = [0.365, 0.125, 0]
    elif kind == "witness":
        foreign["display"]["lines"].append(_ink_line(0.36, 0.126, 0.41, 0.126))
    elif kind == "arrow":
        foreign["display"]["arrows"].append([0.375, 0.126, 0, 1, 0, 0, 0.004, 0.002])
    elif kind == "registered_leader":
        foreign["leaders"] = [[0.36, 0.126, 0, 0.41, 0.126, 0]]
    elif kind == "crossing":
        foreign["display"]["lines"].append(_ink_line(0.37, 0.115, 0.37, 0.122))
    elif kind == "collinear":
        foreign["display"]["lines"].append(_ink_line(0.368, 0.12, 0.38, 0.12))
    elif kind == "border":
        mouth["display"]["lines"].append(_ink_line(0.40, 0.12, 0.43, 0.12))
    elif kind == "title_block":
        mouth["display"]["triangles"] = [[0.25, 0.04, 0, 0.26, 0.04, 0, 0.26, 0.045, 0, 1, 0]]
    elif kind == "crop_text":
        foreign["display"]["texts"][0]["pos"] = [0.31, 0.11, 0]
    else:
        foreign["display"]["lines"].append(_ink_line(0.30, 0.11, 0.33, 0.11))
    dump["views"][0]["annotations"].append(foreign)
    with pytest.raises(RuntimeError, match="mouth annotation ink violations"):
        drawing._assert_mouth_annotation_ink([dump], mouth_crop=(0.297, 0.095, 0.329, 0.127))


def test_actual_mouth_ink_reports_all_faults_not_only_the_first(mouth_ink_dump) -> None:
    dump = deepcopy(mouth_ink_dump)
    mouth = dump["views"][0]["annotations"][-1]
    mouth["display"]["lines"].extend([
        [0], _ink_line(0.40, 0.12, 0.43, 0.12), _ink_line(0.25, 0.04, 0.26, 0.04),
    ])
    dump["views"][0]["annotations"].append(_ink_dimension("COLLIDING", 0.365, 0.12))
    with pytest.raises(RuntimeError) as failure:
        drawing._assert_mouth_annotation_ink([dump], collection_errors=("deliberate read refusal",))
    for message in ("deliberate read refusal", "unreadable actual lines", "outside inner border", "title block", "text blocks crowd", "foreign leader/witness/arrow crossing"):
        assert message in str(failure.value)


def test_drawing_transfers_only_the_new_model_leg_and_runs_settled_guards(monkeypatch) -> None:
    source = SimpleNamespace(is_file=lambda: True)
    section, detail, end, iso = (SimpleNamespace(name=name) for name in ("SECTION", "DETAIL B", "END", "ISO"))
    display = SimpleNamespace(SetText=MagicMock())
    imported = [SimpleNamespace(name=name) for name in drawing.ALL_KEEP]
    moved = SimpleNamespace(name="FloorHoleMouthChamfer", GetSpecificAnnotation=lambda: display)
    adapter = SimpleNamespace(
        currentModel=object(),
        open_model=AsyncMock(return_value=SimpleNamespace(is_success=True, data=None)),
    )
    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "place_view", MagicMock(side_effect=[end, iso]))
    monkeypatch.setattr(drawing, "create_section_view", MagicMock(return_value=section))
    monkeypatch.setattr(drawing, "_create_mouth_detail", MagicMock(return_value=detail))
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kw: (object(), object()))
    monkeypatch.setattr(drawing, "curate_view_dimensions", MagicMock(return_value=imported))
    monkeypatch.setattr(drawing, "move_model_dimension", MagicMock(return_value=moved))
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_args, **_kw: True)
    for name in (
        "read_required_properties", "stamp_drawing_summary", "position_section_caption",
        "set_hidden_lines_removed", "set_dimension_callouts", "assert_imported_precision",
        "set_reference_dimension", "_dress_pocket_floor_radius", "_assert_floor_hole_mouth_chamfer",
        "create_section_axis_centerline", "add_property_linked_note", "rebuild_drawing",
        "check_drawing_layout", "assert_final_mouth_detail",
    ):
        monkeypatch.setattr(drawing, name, MagicMock())

    async def finalize(*_args, **kwargs):
        assert len(kwargs["settled_checks"]) == 1
        kwargs["settled_checks"][0]()
        return {"slddrw": "captured"}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": "captured"}
    drawing.curate_view_dimensions.assert_called_once_with(
        adapter, section, keep=drawing.ALL_KEEP, view_label="longitudinal section",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    original_mouth, = [a for a in imported if a.name == "FloorHoleMouthChamfer"]
    drawing.move_model_dimension.assert_called_once_with(
        adapter, original_mouth, detail, drawing.MOUTH_DETAIL_KEEP["FloorHoleMouthChamfer"], source_view=section,
    )
    display.SetText.assert_called_once_with(2, notes.FLOOR_HOLE_MOUTH_CHAMFER_SUFFIX)
    drawing._assert_floor_hole_mouth_chamfer.assert_called_once_with(moved)
    drawing.assert_final_mouth_detail.assert_called_once_with(adapter, section, detail)
    assert [call.args[1] for call in drawing.set_hidden_lines_removed.call_args_list] == [end, section, iso]


@pytest.fixture
def collected_mouth(monkeypatch, mouth_ink_dump) -> SimpleNamespace:
    """Drive the production settled collector from fake native inventories."""
    old_rows = mouth_ink_dump["views"][0]["annotations"][:-1]
    mouth_row = mouth_ink_dump["views"][0]["annotations"][-1]

    def native(row):
        return SimpleNamespace(name=row["dimension_name"], record=deepcopy(row))

    section_rows = [native(row) for row in old_rows]
    detail_rows = [native(mouth_row)]
    section = SimpleNamespace(GetAnnotations=lambda: section_rows)
    detail = SimpleNamespace(GetAnnotations=lambda: detail_rows)
    sheet_view = SimpleNamespace(GetAnnotations=lambda: [])
    drawing_doc = SimpleNamespace(
        GetViews=lambda: ((sheet_view, section, detail),),
        GetSheetNames=lambda: ("SHEET1",),
    )
    adapter = SimpleNamespace(currentModel=drawing_doc)
    reader = SimpleNamespace(take_errors=lambda: {})
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, a: a.name)
    monkeypatch.setattr(drawing, "_assert_mouth_detail", MagicMock(return_value=SimpleNamespace(crop=(0.297, 0.095, 0.329, 0.127))))
    monkeypatch.setattr(drawing, "_assert_floor_hole_mouth_chamfer", MagicMock())
    monkeypatch.setattr(drawing._drawing_layout_audit, "_Reader", lambda _adapter: reader)
    dump_annotation = MagicMock(side_effect=lambda _reader, a: deepcopy(a.record))
    monkeypatch.setattr(drawing._drawing_layout_audit, "_dump_annotation", dump_annotation)
    monkeypatch.setattr(drawing._drawing_layout_audit, "_layer_states", lambda *_: {})
    return SimpleNamespace(
        adapter=adapter, section=section, detail=detail, section_rows=section_rows,
        detail_rows=detail_rows, reader=reader, dump_annotation=dump_annotation,
    )


def test_settled_collector_reads_all_native_annotations_and_the_real_leg(collected_mouth) -> None:
    f = collected_mouth
    drawing.assert_final_mouth_detail(f.adapter, f.section, f.detail)
    assert f.dump_annotation.call_count == len(spec.DRAWING_PRECISION_BY_NAME)
    drawing._assert_floor_hole_mouth_chamfer.assert_called_once_with(f.detail_rows[0])


@pytest.mark.parametrize("fault", ["foreign_dimension", "duplicate_source", "missing_width", "com_refusal"])
def test_settled_collector_refuses_wrong_ownership_and_unreadable_ink(collected_mouth, fault) -> None:
    f = collected_mouth
    if fault == "foreign_dimension":
        f.detail_rows.append(f.section_rows[0])
    elif fault == "duplicate_source":
        f.section_rows.append(f.detail_rows[0])
    elif fault == "missing_width":
        f.detail_rows[0].record["display"]["texts"][0].pop("w")
    else:
        f.reader.take_errors = lambda: {"GetDisplayData": 1}
    with pytest.raises(RuntimeError, match="mouth annotation ink violations"):
        drawing.assert_final_mouth_detail(f.adapter, f.section, f.detail)


def test_settled_collector_keeps_limit_and_ink_checks_after_crop_refusal(collected_mouth, monkeypatch) -> None:
    f = collected_mouth
    monkeypatch.setattr(drawing, "_assert_mouth_detail", MagicMock(side_effect=RuntimeError("crop changed")))
    f.detail_rows[0].record["display"]["texts"][0].pop("w")
    with pytest.raises(RuntimeError) as failure:
        drawing.assert_final_mouth_detail(f.adapter, f.section, f.detail)
    drawing._assert_floor_hole_mouth_chamfer.assert_called_once_with(f.detail_rows[0])
    assert "crop changed" in str(failure.value)
    assert "unreadable actual texts" in str(failure.value)


def test_drawing_build_capture_wrapper_passes_success_through(monkeypatch) -> None:
    adapter = object()
    result = {"slddrw": "native drawing", "png": "approved sheet"}
    inner = AsyncMock(return_value=result)
    capture = MagicMock()
    monkeypatch.setattr(drawing, "_build_drawing", inner)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    assert asyncio.run(drawing.build(adapter)) is result
    inner.assert_awaited_once_with(adapter)
    capture.assert_not_called()


@pytest.mark.parametrize("exception_type", [AttributeError, RuntimeError])
@pytest.mark.parametrize("capture_behavior", ["original", "secondary", "returns"])
@pytest.mark.parametrize("warning_refuses", [False, True])
def test_drawing_build_captures_before_seat_close_and_preserves_original(
    monkeypatch, exception_type, capture_behavior, warning_refuses,
) -> None:
    adapter = object()
    original = exception_type("native drawing operation refused")
    events, warnings = [], []

    async def refuse(_adapter):
        assert _adapter is adapter
        events.append("build-refusal")
        raise original

    def capture(captured_adapter, label, message, **context):
        events.append("capture")
        assert captured_adapter is adapter
        assert label == f"{drawing.PART_STEM}-drawing-build"
        assert message == str(original)
        assert context == {
            "api": "MHA-DT-35 drawing build",
            "exception": original,
            "sheet_png": True,
            "phase": "drawing-build",
        }
        if capture_behavior == "original":
            raise original  # the real capture helper's normal NoReturn contract
        if capture_behavior == "secondary":
            raise OSError("capture storage refused")

    def warn(message):
        warnings.append(message)
        if warning_refuses:
            raise OSError("warning transport refused")

    monkeypatch.setattr(drawing, "_build_drawing", refuse)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    monkeypatch.setattr(drawing._telemetry, "warn", warn)
    with pytest.raises(exception_type) as caught:
        try:
            asyncio.run(drawing.build(adapter))
        finally:
            events.append("seat-close")
    assert caught.value is original
    assert events == ["build-refusal", "capture", "seat-close"]
    assert len(warnings) == (1 if capture_behavior == "secondary" else 0)
    if warnings:
        assert "capture storage refused" in warnings[0]


def test_drawing_build_captures_source_refusal_before_any_native_operation(monkeypatch) -> None:
    adapter = SimpleNamespace(open_model=AsyncMock())
    source = SimpleNamespace(is_file=lambda: False)
    captured, events = [], []

    def capture(captured_adapter, _label, _message, **context):
        assert captured_adapter is adapter
        assert context["sheet_png"] is True
        captured.append(context["exception"])
        events.append("capture")
        raise context["exception"]

    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(FileNotFoundError) as caught:
        try:
            asyncio.run(drawing.build(adapter))
        finally:
            events.append("seat-close")
    assert captured == [caught.value]
    assert events == ["capture", "seat-close"]
    adapter.open_model.assert_not_awaited()

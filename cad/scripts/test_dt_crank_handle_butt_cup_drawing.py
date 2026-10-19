"""Offline contracts for MHA-DT-035, the crank handle butt cup, and its drawing."""

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
from _drawing_registry import DRAWINGS_BY_NAME


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
    assert drawing.DIMENSION_CALLOUTS == {
        "BodyChamfer": notes.BODY_CHAMFER_CALLOUT,
        "BodyDia": notes.BODY_FIT_CALLOUT,
        "FloorHoleDia": "DRILL THRU",
        "PocketDepth": notes.POCKET_DEPTH_CALLOUT,
        "PocketDia": notes.POCKET_FIT_CALLOUT,
    }
    # Three symmetric bands, plus the separate native radial MAX limit.
    assert model_toleranced_dimensions(part) == {
        ("CupProfile", "BodyDia"): "BODY_DIA_TOL",
        ("CupProfile", "PocketDepth"): "POCKET_DEPTH_TOL",
        ("CupProfile", "BodyChamfer"): "BODY_CHAMFER_TOL",
    }
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 2
    } == {"BodyDia", "PocketDepth"}


def test_bottom_chamfer_clears_the_handle_counterbore_corner() -> None:
    # Owner ruling A on #1661: 0.3-0.5 X 45 DEG, so its smallest leg still
    # clears the MHA-DT-008 counterbore floor's R0.3 MAX corner.
    assert (spec.BODY_CHAMFER_MIN, spec.BODY_CHAMFER_MAX) == (0.3, 0.5)
    assert notes.BODY_CHAMFER_CALLOUT.splitlines() == [
        "X 45 DEG",
        "CLEARS MHA-DT-008",
        "COUNTERBORE CORNER",
    ]


def test_the_floor_holds_1_5_and_the_wall_states_its_shortfall() -> None:
    # User rulings 2026-09-30 (ch30 eight-views-4, concept v4): a plain cup
    # sized to the photographed Ø6 head.  The pocket wall is 0.8, stated on
    # the sheet pending the owner's ruling (#1375); the floor keeps 1.5.
    assert not hasattr(spec, "FLANGE_DIA") and not hasattr(spec, "FLANGE_THICKNESS")
    # The floor is what the overall (.X) leaves after the banded pocket depth,
    # both from the face (re-review: one faced end).
    assert spec.FLOOR_THICKNESS_MIN == pytest.approx(1.7)
    assert spec.POCKET_WALL_FLOOR_MM == 0.8
    assert spec.POCKET_WALL_MIN == pytest.approx(0.8)
    assert screw.CUP_POCKET_WALL_MIN == pytest.approx(0.8)
    assert screw.POCKET_MAX <= spec.POCKET_DIA_MAX
    # 3/8-in stock clears the Ø8.20 body at its upper limit.
    assert "3/8 in" in _config.parts("dt-crank-handle-butt-cup")["material"]
    assert spec.BODY_DIA + spec.BODY_DIA_TOL < 0.375 * 25.4
    assert screw.HEAD_BEARING_RADIAL_MIN > 0.0
    assert spec.FLOOR_HOLE_DIA > screw.SHOULDER_DIA_MAX


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


def test_callouts_name_the_mates_and_the_note_states_the_shortfall() -> None:
    assert notes.HANDLE_NUMBER == _config.parts("dt-crank-handle")["number"]
    assert notes.SCREW_NUMBER == _config.parts("dt-crank-handle-pivot-screw")["number"]
    assert notes.SCREW_NAME in _config.parts("dt-crank-handle-pivot-screw")["title"].upper()
    # MHA-DT-035 machinist ENFORCE r1: each band names its mate at the callout
    # (rule 4), the matched pocket fit states name, number, diametral
    # clearance and its hard limit.  The floor corner's maximum is a separate
    # model-owned radial dimension, not an unrelated axial callout.
    assert notes.BODY_FIT_CALLOUT == "EPOXY FIT IN MHA-DT-008"
    assert notes.POCKET_FIT_CALLOUT.splitlines() == [
        "BORE TO SUIT MHA-DT-032",
        "PIVOT SCREW HEAD, 0.2-0.4",
        "DIAMETRAL CLEARANCE,",
        "<MOD-DIAM>6.5 MAX",
    ]
    assert notes.POCKET_DEPTH_CALLOUT.splitlines() == [
        "KEEPS MHA-DT-032 HEAD",
        "BELOW FACE",
    ]
    assert spec.POCKET_FLOOR_CORNER_R_MAX == pytest.approx(0.1)
    assert spec.POCKET_FLOOR_CORNER_R_MAX <= spec.POCKET_CLEARANCE[0] / 2
    assert spec.POCKET_FLOOR_CORNER_R_BAND == (0.0, -0.1)
    assert spec.POCKET_FLOOR_CORNER_R_TOL_TYPE == 6  # swTolMAX
    assert "PocketFloorRadius" in spec.DRAWING_DIMENSIONS["CupProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME["PocketFloorRadius"] == 1
    assert "PocketFloorRadius" not in spec.REFERENCE_DIMENSIONS
    # Rule 20: the one note states the pocket-wall shortfall as a plain fact,
    # never argues it, and the assembly method lives in MHA-DT-000 (r1
    # finding 1).
    assert notes.DRAWING_NOTES == "POCKET WALL 0.8 MIN"
    for word in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "EPOXY", "CORNERS"):
        assert word not in notes.DRAWING_NOTES
    assert "turned clear of it" in _config.parts("dt-crank-handle-butt-cup")["process"]
    # The DT-008 and DT-032 specs import the cup spec; its prose lives in the
    # notes module so a wording edit never re-keys those parts.
    for name in ("DRAWING_NOTES", "ISOMETRIC_VIEW_NOTE", "FLOOR_HOLE_CALLOUT"):
        assert not hasattr(spec, name)


def test_registry_row_is_the_title_block_source() -> None:
    row = _config.parts("dt-crank-handle-butt-cup")
    assert row["number"] == "MHA-DT-035"
    assert row["title"] == "Crank Handle Butt Cup"
    assert len(str(row["material"])) <= 36
    assert int(row["quantity"]) == 1


def test_sheet_layout_keeps_annotations_inside_the_field() -> None:
    for x, y in (
        *drawing.SECTION_KEEP.values(),
        drawing.MANUFACTURING_NOTES_POS,
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
    # small and the bore's eccentricity both ways, holds the 2.0 wall target
    # (MHA-DT-008 machinist review of 2026-10-18).
    assert handle.BUTT_WALL_MIN >= 2.0
    assert handle.END_ROUND_CY - 0.4 - 0.20 >= handle.COUNTERBORE_DIA_MAX / 2.0 + 2.0
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
                 if p == pytest.approx((-5.5, 2.1, -5.5, 3.05)))
    wall = next(name for name, p in lines.items()
                if p == pytest.approx((-5.4, 3.15, 0.0, 3.15)))
    face = next(name for name, p in lines.items()
                if p == pytest.approx((0.0, 3.15, 0.0, 4.1)))
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
    assert part.V_CUP == pytest.approx(sharp + filled, abs=1e-10)


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
    with pytest.raises(RuntimeError, match="MHA-DT-035 PocketFloorRadius"):
        drawing._dress_pocket_floor_radius(
            SimpleNamespace(GetSpecificAnnotation=lambda: display)
        )


def test_floor_radius_shelf_clears_baseline_ink_and_faces_the_real_quarter_arc() -> None:
    # Native baseline: section centre X215, overall witnesses X194.75/235.25,
    # line Y194.7219, body top Y185.5.  Translate X with the current section.
    shift = drawing.SECTION_CENTER[0] - 0.215
    x, y = drawing.SECTION_KEEP["PocketFloorRadius"]
    left, right = x - 0.011, x + 0.011  # conservative 22 mm native value width
    bottom, top = y - 0.0028, y + 0.0008  # 3.5 mm font plus baseline allowance
    assert left - (0.19475 + shift) == pytest.approx(0.002, abs=1e-12)
    assert (0.23525 + shift) - right > 0.002
    assert bottom - 0.1855 > 0.002
    assert 0.1947219 - top > 0.003
    # The new text/leader stays right of the entire chamfer callout, not only
    # its keep point, and never reaches the overall dimension's line.
    chamfer_right = drawing.SECTION_KEEP["BodyChamfer"][0] + 0.025
    assert left - chamfer_right > 0.005
    corner_r = spec.POCKET_FLOOR_CORNER_R_MAX
    center_x = drawing.FACE_X - (spec.POCKET_DEPTH - corner_r) * drawing._S
    center_y = drawing.SECTION_CENTER[1] + (spec.POCKET_DIA / 2 - corner_r) * drawing._S
    bearing = math.degrees(math.atan2(y - center_y, x - center_x))
    assert 90 < bearing < 180
    assert y < 0.1947219

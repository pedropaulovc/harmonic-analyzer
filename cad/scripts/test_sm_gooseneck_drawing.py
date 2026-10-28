"""Offline flush end piece, blind tap, counterbore and weldment-note contracts."""

from __future__ import annotations

import ast
import asyncio
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from _hole_spec import DRILL_POINT_H
import build_sm_gooseneck as part
import build_sm_gooseneck_spring_screw as screw_part
import draw_sm_gooseneck as drawing
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec
import sm_gooseneck_spring_joint as joint


def _calls(module, *, name: str | None = None, attr: str | None = None) -> list:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (name is not None and getattr(node.func, "id", None) == name)
            or (attr is not None and getattr(node.func, "attr", None) == attr)
        )
    ]


def test_end_piece_is_flush_and_the_tube_ends_on_its_head() -> None:
    # Owner ruling (#1951): flush with the tube OD, no step.
    assert geom.PLUG_DIA == geom.TUBE_DIA == 12.70
    assert part.PLUG_R == part.TUBE_R
    assert geom.TUBE_END_X - geom.ARM_END_X == pytest.approx(geom.PLUG_HEAD_LENGTH)
    assert geom.ARM_STRAIGHT == pytest.approx(
        geom.TUBE_STRAIGHT + geom.PLUG_HEAD_LENGTH
    )
    # The braze shank sits in the tube bore at its diametral clearance and
    # inside the straight, short of the bend tangent.
    clearance = geom.TUBE_BORE_DIA - joint.PLUG_SHANK_DIA
    assert joint.BRAZE_CLEARANCE_MIN <= clearance <= joint.BRAZE_CLEARANCE_MAX
    assert part.SHANK_R < part.TUBE_IR
    assert part.SHANK_END_X == pytest.approx(geom.TUBE_END_X + geom.PLUG_SHANK_LENGTH)
    assert part.SHANK_END_X < -geom.BEND_R
    assert geom.PLUG_LENGTH == geom.PLUG_HEAD_LENGTH + geom.PLUG_SHANK_LENGTH


def test_blind_tap_stays_inside_the_solid_end_piece() -> None:
    assert joint.TAP_SPEC.kind.startswith("tapped")
    assert joint.TAP_SPEC.size == "1/4-28"
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert part.TAP_DRILL_DIA == joint.TAP_DRILL_DIA
    assert joint.TAP_THREAD_DEPTH < joint.TAP_DRILL_DEPTH
    # The full drill Ø stays in the shortest head; the point stays in the end
    # piece, so the tube's bore never sees the drill.
    assert joint.TAP_DRILL_DEPTH_MAX <= joint.PLUG_HEAD_LENGTH_MIN
    tip = joint.TAP_DRILL_DEPTH_MAX + DRILL_POINT_H * joint.TAP_DRILL_DIA_MAX / 2.0
    assert tip < geom.PLUG_LENGTH
    taps = _calls(part, name="wizard_holes")
    assert len(taps) == 1
    # The end piece and its tap come first; the tube is swept onto them.
    sweeps = _calls(part, attr="create_sweep")
    assert sweeps
    assert taps[0].lineno < min(node.lineno for node in sweeps)


def test_tap_starts_on_the_counterbore_floor_before_the_tube() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    end_piece = source.index('name_last_feature(adapter, "EndPiece")')
    counterbore = source.index('name_last_feature(adapter, "Counterbore")')
    tap = source.index('name="ThreadBore"')
    sweep = source.index("create_sweep")
    assert end_piece < counterbore < tap < sweep
    assert "[[COUNTERBORE_FLOOR_X, ARM_Y, 0.0]]" in source
    assert joint.TAP_SPEC.depth_mm == joint.TAP_DRILL_DEPTH_FROM_FLOOR
    assert joint.TAP_SPEC.overrides_mm == {
        "ThreadDepth": joint.TAP_THREAD_DEPTH_FROM_FLOOR
    }
    assert joint.TAP_DRILL_DEPTH == pytest.approx(
        joint.COUNTERBORE_DEPTH + joint.TAP_DRILL_DEPTH_FROM_FLOOR
    )
    assert part.COUNTERBORE_R * 2.0 == joint.COUNTERBORE_DIA
    assert part.COUNTERBORE_FLOOR_X == pytest.approx(
        geom.ARM_END_X + joint.COUNTERBORE_DEPTH
    )


@pytest.mark.parametrize("builder", [part, screw_part], ids=lambda m: m.__name__)
def test_every_direct_db_block_restores_inference_in_finally(builder) -> None:
    # Sketch inference is session state on the persistent seat: each block
    # that turns it off must restore it even when a native segment is
    # rejected, so every True is followed at once by a try whose finally
    # restores it, and nothing restores it outside a finally.  Shared by the
    # MHA-SM-01 post and the MHA-SM-04 screw builders.
    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))

    def toggle(node: ast.AST) -> str | None:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "set_sketch_direct_db"
        ):
            return ast.unparse(node.value.args[1])
        return None

    on = restored = 0
    finally_offs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            finally_offs |= {
                id(stmt) for stmt in node.finalbody if toggle(stmt) == "False"
            }
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for index, stmt in enumerate(body):
            if toggle(stmt) == "True":
                on += 1
                following = body[index + 1]
                assert isinstance(following, ast.Try), ast.unparse(stmt)
                assert [toggle(s) for s in following.finalbody] == ["False"]
                restored += 1
    offs = [node for node in ast.walk(tree) if toggle(node) == "False"]
    assert {id(node) for node in offs} == finally_offs
    # The property, not the inventory: at least one block, each restored.
    assert on == restored == len(offs) >= 1


def test_counterbore_callouts_floor_the_wall_from_the_joint() -> None:
    # A stated minimum is rounded DOWN, so the print never promises more
    # wall than the joint's worst case leaves (drawing-guidelines rule 20).
    floored = math.floor(joint.COUNTERBORE_WALL_MIN * 100.0) / 100.0
    assert spec.COUNTERBORE_WALL_CALLOUT == f"C'BORE WALL {floored:.2f} MIN"
    assert floored <= joint.COUNTERBORE_WALL_MIN
    callouts = spec.DIMENSION_CALLOUTS_BY_NAME
    assert spec.COUNTERBORE_WALL_CALLOUT in callouts["CounterboreDia"].splitlines()
    # The floor corner's limit is its own native radial dimension, not text
    # under the depth (codjiflo P2 on #1997).
    assert "CounterboreDepth" not in callouts
    assert callouts["CounterboreFloorCornerR"] == spec.COUNTERBORE_FLOOR_CALLOUT
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(callouts) <= marked
    for feature, by_name in spec.DIMENSION_CALLOUTS.items():
        assert set(by_name) <= set(spec.DRAWING_DIMENSIONS[feature])


def test_notes_state_stock_process_and_intent_without_sizes() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    # Rule 7: four lines at most, each ending left of the title block
    # (x 0.216) from NOTES_XY at the sheet's ~2.42 mm a character (farm run
    # 20261028T005208028Z: the 80-character line ended at x 0.210).
    assert len(lines) <= 4
    assert all(re.match(r"\d\. ", line) for line in lines)
    assert drawing.NOTES_XY[0] + 0.00242 * max(map(len, lines)) < 0.214
    notes = " ".join(spec.DRAWING_NOTES.split())
    for phrase in (
        "1/2 OD X 0.065 WALL 4130-N SEAMLESS",
        "ONLINEMETALS 7322",
        "AS STOCK",
        "1/2 X 3 CLR DIE",
        "5/8 OD X 0.058 WALL",
        "ONLINEMETALS 7324",
        "SELECT-FIT AT SHANK CLEARANCE",
        "BOTH SLEEVE ENDS",
        "BAg-7",
    ):
        assert phrase in notes, phrase
    # Sizes and tolerances are native model dimensions, never note text.
    assert re.search(r"\b\d+\.\d{1,2}\b", notes) is None, notes
    assert "<MOD-DIAM>" not in notes and "Ø" not in notes
    assert "THRU" not in notes.upper()


def test_tap_callout_flags_the_braze_order_within_four_rows() -> None:
    # The native callout's two rows plus these stay within the layout
    # audit's four-row limit.
    rows = spec.TAP_CALLOUT_BELOW.splitlines()
    assert len(rows) == 2
    assert rows[-1].endswith("; TAP AFTER BRAZE")
    printed = " ".join((spec.DRAWING_NOTES, spec.TAP_CALLOUT_BELOW)).upper()
    assert "PURCHASED" not in printed and "INTEGRAL" not in printed
    assert "THREADLOCKER" not in printed  # spring-eye clamping belongs to the assembly


def test_sheet_places_every_marked_dimension_at_its_places() -> None:
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_DIMENSIONS["EndPieceProfile"]) | set(
        spec.DRAWING_DIMENSIONS["CounterboreProfile"]
    ) == set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 1
    } == spec.ONE_PLACE_DIMENSIONS
    # Section A-A keeps only the end piece: its crop runs past the shank,
    # short of the bend; its full cut's line runs past where the plane leaves
    # the bend's outer wall, short of the leg.
    start, end = drawing.SECTION_CROP_X_MM
    assert start < geom.ARM_END_X < part.SHANK_END_X < end < -geom.BEND_R
    bend_cut_end = -geom.BEND_R + math.sqrt(
        (geom.BEND_R + geom.TUBE_DIA / 2.0) ** 2 - geom.BEND_R**2
    )
    line_start, line_end = drawing.SECTION_LINE_X_MM
    assert line_start == start and bend_cut_end < line_end < 0.0


@pytest.fixture
def saved_tap(monkeypatch):
    """Read-only saved feature with independently specified native tap metadata."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="1/4-28",
        ThreadClass="2B",
        ThreadEndCondition=0,  # blind
        EndCondition=0,
        TapDrillDiameter=0.00541,  # native model length units are metres
        TapDrillDepth=0.01717,
        ThreadDepth=0.01477,
    )
    feature = SimpleNamespace(
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: definition,
    )
    model = SimpleNamespace(
        FeatureByName=lambda name: feature if name == "ThreadBore" else None,
    )
    return model, feature, definition


@pytest.mark.parametrize("offset_mm", [-0.004, 0.0, 0.004])
@pytest.mark.parametrize("field", ["TapDrillDiameter", "TapDrillDepth", "ThreadDepth"])
def test_saved_native_receiver_accepts_the_blind_tap(saved_tap, field, offset_mm):
    model, _feature, definition = saved_tap
    setattr(definition, field, getattr(definition, field) + offset_mm / 1000.0)
    drawing._require_saved_tap(model)


@pytest.mark.parametrize(
    ("field", "value", "diagnostic"),
    [
        ("FastenerSize", "1/4-20", "thread size"),
        ("ThreadClass", "", "ThreadClass"),
        ("ThreadClass", "3B", "ThreadClass"),
        ("ThreadEndCondition", 1, "ThreadEndCondition"),
        ("ThreadEndCondition", 2, "ThreadEndCondition"),
        ("EndCondition", 1, "EndCondition"),
        ("EndCondition", 2, "EndCondition"),
        ("TapDrillDiameter", 0.0, "tap drill"),
        ("TapDrillDiameter", 0.005404, "tap drill"),
        ("TapDrillDiameter", 0.005416, "tap drill"),
        ("TapDrillDiameter", math.nan, "tap drill"),
        ("TapDrillDepth", 0.0171, "tap drill depth"),
        ("TapDrillDepth", 0.0200, "tap drill depth"),
        ("ThreadDepth", 0.0147, "thread depth"),
        ("ThreadDepth", 0.0122, "thread depth"),
    ],
)
def test_saved_native_receiver_rejects_lost_thread_metadata(
    saved_tap, field, value, diagnostic
):
    model, _feature, definition = saved_tap
    setattr(definition, field, value)
    with pytest.raises(RuntimeError, match=diagnostic):
        drawing._require_saved_tap(model)


@pytest.mark.parametrize("fault", ["missing", "plain_cut", "no_definition"])
def test_saved_receiver_requires_a_native_hole_feature(saved_tap, fault):
    model, feature, _definition = saved_tap
    if fault == "missing":
        model.FeatureByName = lambda _name: None
    elif fault == "plain_cut":
        feature.GetTypeName2 = lambda: "Cut"
    else:
        feature.GetDefinition = lambda: None
    with pytest.raises(RuntimeError):
        drawing._require_saved_tap(model)


def _mass_adapter(volume: float):
    async def get_mass_properties():
        return SimpleNamespace(
            is_success=True, error=None, data=SimpleNamespace(volume=volume)
        )

    return SimpleNamespace(get_mass_properties=get_mass_properties)


@pytest.mark.parametrize("volume", [math.nan, math.inf, -math.inf])
def test_build_stops_on_a_non_finite_volume_read(volume):
    # NaN passes |vol - expected| > tol, the shared volume_check's included
    # (codjiflo rounds 5 and 6 on #1997).
    adapter = _mass_adapter(volume)
    with pytest.raises(RuntimeError, match="non-finite volume"):
        asyncio.run(part._volume(adapter))
    # The shared check already rejects an infinite read; NaN needs the guard.
    with pytest.raises(RuntimeError, match="non-finite volume|volume -?inf"):
        asyncio.run(part._volume_check(adapter, "end piece", 100.0, 1.0))
    assert asyncio.run(part._volume(_mass_adapter(100.0))) == 100.0

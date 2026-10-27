"""Offline native receiver, full-thread and legacy-weldment contracts."""

from __future__ import annotations

import ast
import asyncio
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import build_sm_gooseneck as part
import build_sm_gooseneck_spring_screw as screw_part
import draw_sm_gooseneck as drawing
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec
import sm_gooseneck_spring_joint as joint


def test_physical_plug_and_modelling_overlap_are_distinct() -> None:
    tube_id = geom.TUBE_DIA - 2.0 * geom.WALL_T

    assert part.PLUG_DIA == tube_id == 12.0
    assert tube_id < part.PLUG_OVERLAP_DIA < geom.TUBE_DIA
    assert part.PLUG_OVERLAP_DIA == geom.TUBE_DIA - geom.WALL_T == 14.0
    assert part.PLUG_LENGTH == 10.00


def test_native_receiver_is_through_tapped_before_the_tube() -> None:
    assert joint.TAP_SPEC.kind == "tapped"
    assert joint.TAP_SPEC.size == "#8-32"
    assert joint.TAP_SPEC.end == "through_all"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert part.TAP_DRILL_DIA == 3.454
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    taps = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "wizard_holes"
    ]
    assert len(taps) == 1
    # Through-all must be upstream of the curved tube: otherwise the drill
    # exits the straight bore and perforates the bend's far wall as well.
    sweeps = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "attr", None) == "create_sweep"
    ]
    assert sweeps
    assert taps[0].lineno < min(node.lineno for node in sweeps)


def test_counterbore_and_inner_break_follow_the_tap_before_the_tube() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    tap = source.index('name="ThreadBore"')
    cbore = source.index('name_last_feature(adapter, "Counterbore")')
    inner = source.index('name_last_feature(adapter, "InnerTapBreak")')
    sweep = source.index("create_sweep")
    assert tap < cbore < inner < sweep
    assert "TapEdgeBreaks" not in source and '"Mouth"' not in source
    assert (part.COUNTERBORE_DIA, part.COUNTERBORE_DEPTH) == (
        joint.COUNTERBORE_DIA,
        joint.COUNTERBORE_DEPTH,
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


def test_counterbore_and_breaks_reduce_the_printed_full_thread_length() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split())
    cbore = re.search(
        r"ARM END C'BORE <MOD-DIAM>([\d.]+)-([\d.]+) X ([\d.]+)-([\d.]+) DEEP"
        r" FROM PLUG FACE, ON TAP AXIS WITHIN ([\d.]+); FLOOR CORNER R([\d.]+) MAX;",
        notes,
    )
    edge = re.search(r"BREAK INNER TAP END\s+([\d.]+)\s+X\s+45\s+DEG", notes)
    full = re.search(r"FULL THREAD\s+([\d.]+)\s+NOMINAL;\s+([\d.]+)\s+MIN", notes)
    assert cbore is not None and edge is not None and full is not None
    dia_min, dia_max, depth_min, depth_max, axis, corner = map(float, cbore.groups())
    assert (dia_min, dia_max) == pytest.approx(
        (joint.COUNTERBORE_DIA, joint.COUNTERBORE_DIA_MAX)
    )
    assert (dia_min, dia_max, depth_min, depth_max) == pytest.approx(
        (4.90, 5.00, 2.59, 2.69)
    )
    assert axis == joint.COUNTERBORE_AXIS_OFFSET_MAX == 0.10
    assert corner == joint.COUNTERBORE_FLOOR_CORNER_R_MAX == 0.10
    assert "SETUP" not in notes  # a requirement, not a method
    edge_break = float(edge.group(1))
    nominal, minimum = map(float, full.groups())
    assert edge_break == 0.25
    # The title block's 0.25 break also takes the tap edge at the c'bore floor.
    depth = (depth_min + depth_max) / 2.0
    assert nominal == pytest.approx(part.PLUG_LENGTH - depth - 2.0 * edge_break)
    assert minimum == pytest.approx(
        part.PLUG_LENGTH - joint.PLUG_LENGTH_BAND - depth_max - 2.0 * edge_break
    )
    assert (nominal, minimum) == pytest.approx((6.86, 6.30))
    assert minimum >= 1.5 * (0.164 * 25.4)  # #8 basic major, not its tap drill
    assert "BREAK BOTH TAP ENDS" not in notes


def test_plug_print_uses_physical_size_and_shared_loose_bands() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split())
    plug = re.search(
        r"END PLUG:.*?<MOD-DIAM>([\d.]+)\s+\+/-([\d.]+)"
        r"\s+X\s+([\d.]+)\s+\+/-([\d.]+)",
        notes,
    )
    assert plug is not None
    assert tuple(map(float, plug.groups())) == (12.00, 0.51, 10.00, 0.51)
    assert re.search(
        r"THREAD AXIS TO TUBE AXIS\s+\+/-" + f"{joint.THREAD_AXIS_OFFSET_MAX:.2f}",
        notes,
    )
    assert re.search(
        r"DRILL WANDER\s+" + f"{joint.DRILL_WANDER_MAX:.2f}" + r"\s+MAX", notes
    )
    assert "#8-32 UNC-2B THRU PLUG" in notes
    assert "SILVER-BRAZE" in notes
    # drawing-guidelines.md rule 4 (tighten only for function, and name the mate): a matched fit names its mate and states the clearance.
    fit = re.search(
        r"FIT TO THE TUBE BORE AT\s+([\d.]+)-([\d.]+)\s+DIAMETRAL CLEARANCE", notes
    )
    assert fit is not None
    assert (
        tuple(map(float, fit.groups()))
        == (
            joint.BRAZE_CLEARANCE_MIN,
            joint.BRAZE_CLEARANCE_MAX,
        )
        == (0.05, 0.13)
    )
    assert "FLUSH WITH ARM END +/-0.10" in notes
    assert "NO OPEN GAP AT END FACE" in notes


def test_weldment_keeps_the_made_screw_in_the_assembly() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split()).upper()
    assert "MHA-SM-04" in notes and "MADE SEPARATELY" in notes
    assert "NOT INCLUDED IN THIS WELDMENT" in notes
    assert "PURCHASED" not in notes and "INTEGRAL" not in notes
    assert "SHANK EXPOSED" not in notes and "SLOT" not in notes
    assert "THREADLOCKER" not in notes  # spring-eye clamping belongs to the assembly


@pytest.fixture
def saved_tap(monkeypatch):
    """Read-only saved feature with independently specified native tap metadata."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="#8-32",
        ThreadClass="2B",
        ThreadEndCondition=1,  # through all, not blind or through next
        EndCondition=1,
        ThruTapDrillDiameter=0.003454,  # native model length units are metres
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
def test_saved_native_receiver_accepts_the_through_tap(saved_tap, offset_mm):
    model, _feature, definition = saved_tap
    definition.ThruTapDrillDiameter += offset_mm / 1000.0
    drawing._require_saved_tap(model)


@pytest.mark.parametrize(
    ("field", "value", "diagnostic"),
    [
        ("FastenerSize", "#6-32", "thread size"),
        ("ThreadClass", "", "ThreadClass"),
        ("ThreadClass", "3B", "ThreadClass"),
        ("ThreadEndCondition", 0, "ThreadEndCondition"),
        ("ThreadEndCondition", 2, "ThreadEndCondition"),
        ("EndCondition", 0, "EndCondition"),
        ("EndCondition", 2, "EndCondition"),
        ("ThruTapDrillDiameter", 0.0, "tap drill"),
        ("ThruTapDrillDiameter", 0.003448, "tap drill"),
        ("ThruTapDrillDiameter", 0.003460, "tap drill"),
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
def test_plug_build_stops_on_a_non_finite_volume_read(volume):
    # NaN passes |vol - expected| > tol, the shared volume_check's included
    # (codjiflo rounds 5 and 6 on #1997).
    adapter = _mass_adapter(volume)
    with pytest.raises(RuntimeError, match="non-finite volume"):
        asyncio.run(part._volume(adapter))
    # The shared check already rejects an infinite read; NaN needs the guard.
    with pytest.raises(RuntimeError, match="non-finite volume|volume -?inf"):
        asyncio.run(part._volume_check(adapter, "plug", 100.0, 1.0))
    assert asyncio.run(part._volume(_mass_adapter(100.0))) == 100.0

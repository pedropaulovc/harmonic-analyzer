"""Offline native receiver, full-thread and legacy-weldment contracts."""

from __future__ import annotations

import ast
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import build_sm_gooseneck as part
import draw_sm_gooseneck as drawing
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec
import sm_gooseneck_spring_joint as joint


def test_physical_plug_and_modelling_overlap_are_distinct() -> None:
    tube_id = geom.TUBE_DIA - 2.0 * geom.WALL_T

    assert part.PLUG_DIA == tube_id == 12.0
    assert tube_id < part.PLUG_OVERLAP_DIA < geom.TUBE_DIA
    assert part.PLUG_OVERLAP_DIA == geom.TUBE_DIA - geom.WALL_T == 14.0
    assert part.PLUG_LENGTH == 8.0


def test_native_receiver_is_through_tapped_before_the_tube() -> None:
    assert joint.TAP_SPEC.kind == "tapped"
    assert joint.TAP_SPEC.size == "#6-32"
    assert joint.TAP_SPEC.end == "through_all"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert part.TAP_DRILL_DIA == 2.705
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


def test_both_tap_breaks_reduce_the_printed_full_thread_length() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split())
    edge = re.search(r"BREAK BOTH TAP ENDS\s+([\d.]+)\s+X\s+45\s+DEG", notes)
    full = re.search(r"FULL THREAD\s+([\d.]+)\s+NOMINAL;\s+([\d.]+)\s+MIN", notes)
    assert edge is not None and full is not None
    edge_break = float(edge.group(1))
    nominal, minimum = map(float, full.groups())
    assert edge_break == 0.25
    assert nominal == pytest.approx(part.PLUG_LENGTH - 2.0 * edge_break)
    assert minimum == pytest.approx(nominal - joint.PLUG_LENGTH_BAND)
    assert (nominal, minimum) == pytest.approx((7.50, 6.99))
    assert minimum >= 1.5 * (0.138 * 25.4)  # #6 basic major, not its tap drill


def test_plug_print_uses_physical_size_and_shared_loose_bands() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split())
    plug = re.search(
        r"END PLUG:.*?<MOD-DIAM>([\d.]+)\s+\+/-([\d.]+)"
        r"\s+X\s+([\d.]+)\s+\+/-([\d.]+)",
        notes,
    )
    assert plug is not None
    assert tuple(map(float, plug.groups())) == (12.00, 0.51, 8.00, 0.51)
    assert re.search(
        r"THREAD AXIS TO TUBE AXIS\s+\+/-" + f"{joint.THREAD_AXIS_OFFSET_MAX:.2f}",
        notes,
    )
    assert re.search(
        r"DRILL WANDER\s+" + f"{joint.DRILL_WANDER_MAX:.2f}" + r"\s+MAX", notes
    )
    assert "#6-32 UNC-2B THRU PLUG" in notes
    assert "SILVER-BRAZE" in notes


def test_weldment_keeps_the_made_screw_in_the_assembly() -> None:
    notes = " ".join(spec.DRAWING_NOTES.split()).upper()
    assert "MHA-SM-004" in notes and "MADE SEPARATELY" in notes
    assert "NOT INCLUDED IN THIS WELDMENT" in notes
    assert "PURCHASED" not in notes and "INTEGRAL" not in notes
    assert "SHANK EXPOSED" not in notes and "SLOT" not in notes
    assert "THREADLOCKER" not in notes  # spring-eye clamping belongs to the assembly


@pytest.fixture
def saved_tap(monkeypatch):
    """Read-only saved feature with independently specified native tap metadata."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="#6-32",
        ThreadClass="2B",
        ThreadEndCondition=1,  # through all, not blind or through next
        EndCondition=1,
        ThruTapDrillDiameter=0.002705,  # native model length units are metres
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
        ("FastenerSize", "#8-32", "thread size"),
        ("ThreadClass", "", "ThreadClass"),
        ("ThreadClass", "3B", "ThreadClass"),
        ("ThreadEndCondition", 0, "ThreadEndCondition"),
        ("ThreadEndCondition", 2, "ThreadEndCondition"),
        ("EndCondition", 0, "EndCondition"),
        ("EndCondition", 2, "EndCondition"),
        ("ThruTapDrillDiameter", 0.0, "tap drill"),
        ("ThruTapDrillDiameter", 0.002699, "tap drill"),
        ("ThruTapDrillDiameter", 0.002711, "tap drill"),
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

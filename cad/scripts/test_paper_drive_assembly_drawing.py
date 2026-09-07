"""Offline contracts for the paper-drive assembly and its drawing."""

import ast
import inspect
from itertools import product
from pathlib import Path

import pytest

import _assembly
import build_paper_drive_assembly as assembly
import build_transgear_removable as sprocket
import draw_paper_drive_assembly as drawing
import harmonic_base_spec as base
import nameplate_spec as nameplate
from _drawing_registry import DRAWINGS_BY_NAME


def test_paper_drive_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["paper_drive_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "paper_drive"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 5.0)
    assert drawing.FRONT_CENTER == (0.080, 0.150)
    assert drawing.RIGHT_CENTER == (0.200, 0.150)
    assert drawing.ISO_CENTER == (0.320, 0.145)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "return await build_simple_three_view_drawing(" in source


def _spare_world_point(monkeypatch, local):
    """Exercise the production row-vector transform without a COM connection."""
    transform = [value for row in assembly.ROT_X_NEG90 for value in row]
    transform += [value / 1000.0 for value in assembly.SPARE_GEAR_POS]
    transform += [1.0, 0.0, 0.0, 0.0]
    adapter = object()

    def component_transform(actual_adapter, name):
        assert actual_adapter is adapter
        assert name == "transgear-removable-3"
        return transform

    monkeypatch.setattr(_assembly, "component_transform", component_transform)
    return _assembly.world_point(adapter, "transgear-removable-3", local)


def test_spare_sprocket_transformed_underside_contacts_base_deck(monkeypatch):
    # The builder's blank is Z=0..FACE_WIDTH, identical in all tooth configs.
    underside = _spare_world_point(monkeypatch, [0.0, 0.0, 0.0])
    top = _spare_world_point(monkeypatch, [0.0, 0.0, sprocket.FACE_WIDTH])
    assert underside[1] == pytest.approx(base.STACK_HEIGHT, rel=0, abs=1e-9)
    assert top[1] == pytest.approx(
        base.STACK_HEIGHT + sprocket.FACE_WIDTH, rel=0, abs=1e-9
    )
    assert (underside[0], underside[2]) == (160.0, -75.0)
    assert (top[0], top[2]) == (160.0, -75.0)


def test_spare_t18_footprint_is_on_flat_deck_not_raised_rim(monkeypatch):
    teeth = dict(sprocket.CONFIGS)["T18"]
    radius = sprocket.gear_facts(teeth, sprocket.DP_GEAR, sprocket.PA_DEG)["Ra"]
    radius *= sprocket.IN
    for x, y, z in product(
        (-radius, radius), (-radius, radius), (0.0, sprocket.FACE_WIDTH)
    ):
        world = _spare_world_point(monkeypatch, [x, y, z])
        assert abs(world[0]) < base.TOP_LENGTH / 2.0 - base.LIP_W
        assert abs(world[2]) < base.TOP_WIDTH / 2.0 - base.LIP_W


def test_spare_storage_clears_nameplate_envelope_by_five_mm(monkeypatch):
    # Native top gate rejected the first deck-seating candidate: retaining
    # X=160/Z=-15 intersected the brass nameplate by 605.55 mm^3.
    teeth = dict(sprocket.CONFIGS)["T18"]
    radius = (
        sprocket.gear_facts(teeth, sprocket.DP_GEAR, sprocket.PA_DEG)["Ra"]
        * sprocket.IN
    )
    plate_corners = [
        nameplate.mount_point(point)
        for point in product(
            (0.0, nameplate.PLATE_WIDTH),
            (0.0, nameplate.PLATE_HEIGHT),
            (-nameplate.PLATE_THICKNESS, 0.0),
        )
    ]
    spare_max_z = max(
        _spare_world_point(monkeypatch, [x, y, z])[2]
        for x, y, z in product(
            (-radius, radius), (-radius, radius), (0.0, sprocket.FACE_WIDTH)
        )
    )
    assert spare_max_z <= min(point[2] for point in plate_corners) - 5.0


def test_spare_remains_fixed_t18_sibling_with_original_rotation():
    tree = ast.parse(Path(assembly.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "place_component"
        and any(
            keyword.arg == "label"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == "transgear-removable (spare T18)"
            for keyword in node.keywords
        )
    ]
    assert len(calls) == 1
    call = calls[0]
    assert [ast.unparse(arg) for arg in call.args] == [
        "adapter",
        "'transgear-removable'",
        "list(SPARE_GEAR_POS)",
        "[-90.0, 0.0, 0.0]",
        "ROT_X_NEG90",
    ]
    assert {
        keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords
    } == {
        "configuration": "T18",
        "label": "transgear-removable (spare T18)",
    }
    assert (
        inspect.signature(_assembly.place_component).parameters["ground"].default
        is True
    )
    assert assembly.ROT_X_NEG90 == [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]

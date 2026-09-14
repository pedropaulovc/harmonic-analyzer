"""Offline behavioral regressions for native spring-contact classification."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _native_spring_contact as contact


_IDENTITY = [
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
    1.0,
    0.0,
    0.0,
    0.0,
]
_MICROSCOPIC_OVERLAP_MM3 = 1.5639222787051562e-9


class _IntersectionBody:
    def __init__(self, volume_mm3: float) -> None:
        self.volume_m3 = volume_mm3 / 1e9

    def GetType(self) -> int:
        return 0

    def GetMassProperties(self, density: float):
        return (
            0.0,
            0.0,
            0.0,
            self.volume_m3,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        )


class _TemporaryBody:
    def __init__(self, source: _NativeBody) -> None:
        self.source = source
        self.transforms = []
        self.state = "active"

    def ApplyTransform(self, transform) -> bool:
        assert self.state == "active"
        assert transform.ArrayData == self.source.owner.Transform2.ArrayData
        self.transforms.append(transform)
        return True

    def Operations2(self, operation: int, tool, error_code: int = 0):
        assert operation == 15901
        assert len(self.transforms) == len(tool.transforms) == 1
        self.state = tool.state = "consumed"
        return self.source.scene.intersection(self.source.name, tool.source.name)


class _NativeBody:
    def __init__(self, scene: _Scene, owner: _Component, name: str) -> None:
        self.scene = scene
        self.owner = owner
        self.name = name
        self.Check3 = SimpleNamespace(Count=0)

    def GetType(self) -> int:
        return 0

    def Copy(self):
        return _TemporaryBody(self)


class _Component:
    def __init__(self, name: str) -> None:
        self.Name2 = name
        self.Transform2 = SimpleNamespace(ArrayData=list(_IDENTITY))
        self.bodies = []

    def IsFixed(self) -> bool:
        return True

    def GetBodies3(self, body_type: int):
        assert body_type == 0
        return tuple(self.bodies), tuple(0 for _body in self.bodies)


class _Manager:
    def GetInterferences(self):
        return ()

    def Done(self) -> None:
        return None


class _Scene:
    def __init__(self) -> None:
        self.mode = "clear"
        self.manager = _Manager()
        self.spring = _Component("spring")
        self.seat = _Component("seat")
        self.components = {
            component.Name2: component for component in (self.spring, self.seat)
        }
        self.spring.bodies = [
            _NativeBody(self, self.spring, "spring-first"),
            _NativeBody(self, self.spring, "spring-second"),
        ]
        self.seat.bodies = [_NativeBody(self, self.seat, "seat-body")]
        self.Extension = SimpleNamespace(Rebuild=self.rebuild)
        self.currentModel = self
        self.swApp = self

    def bind(self, value, interface: str):
        return value

    def GetModeler(self):
        return self

    def CheckInterference3(self, targets, tools, options, faces1, faces2, bodies):
        assert not options & 2  # Coincident-only contact is not an overlap.
        target, tool = targets[0], tools[0]
        assert target.state == tool.state == "active"
        assert len(target.transforms) == len(tool.transforms) == 1
        detected = (
            self.mode in ("modeler-overlap", "clear-modeler-overlap")
            and target.source.name == "spring-second"
            and tool.source.name == "seat-body"
        )
        return detected, None, None, None

    def _attempt(self, operation, default=None):
        return operation()

    def GetComponents(self, top_level_only: bool):
        assert top_level_only is True
        return tuple(self.components.values())

    def GetComponentByName(self, name: str):
        return self.components.get(name)

    def ClearSelection2(self, clear_all: bool) -> None:
        assert clear_all is True

    def ToolsCheckInterference(self) -> None:
        return None

    def ClosestDistance(self, moving, fixed):
        return 0.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    def rebuild(self, option: int) -> bool:
        assert option == 4
        return True

    def put_pose(self, _adapter, name: str, values) -> None:
        self.components[name].Transform2 = SimpleNamespace(ArrayData=list(values))

    def intersection(self, target: str, tool: str):
        if target == "spring-first" and self.mode == "modeler-overlap":
            return (_IntersectionBody(_MICROSCOPIC_OVERLAP_MM3),), 0
        if target != "spring-second" or tool != "seat-body":
            return None, 0
        if self.mode == "overlap":
            return (_IntersectionBody(_MICROSCOPIC_OVERLAP_MM3),), 0
        if self.mode in ("boolean-fail", "modeler-overlap"):
            return None, 1058  # swBodyOperationBooleanFail
        return None, 0

    def pair(self):
        return contact._ActualContact(
            self,
            "spring",
            "seat",
            (1.0, 0.0, 0.0),
            1.0,
            "counter spring seat",
        )


@pytest.fixture
def scene(monkeypatch):
    value = _Scene()
    monkeypatch.setattr(contact, "_early_bound", value.bind)
    monkeypatch.setattr(contact, "dispatch_array", lambda values: values)
    monkeypatch.setattr(
        contact,
        "configured_interference_manager",
        lambda _adapter: value.manager,
    )
    monkeypatch.setattr(contact, "put_component_pose", value.put_pose)
    return value


def test_manager_omission_uses_every_actual_body_without_volume_threshold(
    scene,
) -> None:
    scene.mode = "overlap"
    pair = scene.pair()

    assert pair._interference_state(pair.originals) == "interfering"


def test_positive_native_predicate_rejects_unconstructible_intersection(scene) -> None:
    scene.mode = "modeler-overlap"
    pair = scene.pair()

    assert pair._interference_state(pair.originals) == "interfering"
    evidence = contact.native_component_interference(
        scene, "spring", "seat", label="unconstructible overlap"
    )
    assert evidence.volume_mm3 is None  # Never publish the measured partial sum.
    assert evidence.boolean_failure_status == 1058


def test_successful_zero_volume_is_not_overruled_by_another_kernel(scene) -> None:
    scene.mode = "clear-modeler-overlap"
    pair = scene.pair()

    assert pair._interference_state(pair.originals) == "clear"


def test_zero_result_native_boolean_preserves_clear_classification(scene) -> None:
    pair = scene.pair()

    assert pair._interference_state(pair.originals) == "clear"


def test_native_boolean_failure_is_loud_and_restores_evaluated_placement(scene) -> None:
    pair = scene.pair()
    original = list(scene.spring.Transform2.ArrayData)
    scene.mode = "boolean-fail"

    with pytest.raises(
        RuntimeError,
        match=r"\b1058\b",
    ):
        pair.evaluate(0.25)

    assert scene.spring.Transform2.ArrayData == original
    assert scene.seat.Transform2.ArrayData == _IDENTITY


def test_fixture_witness_rejects_omitted_overlap_despite_zero_distance(
    scene, monkeypatch
) -> None:
    from diagnostics import probe_stock_spring_seating as diagnostic

    monkeypatch.setattr(diagnostic, "_early_bound", scene.bind)
    monkeypatch.setattr(
        diagnostic, "configured_interference_manager", lambda _adapter: scene.manager
    )
    monkeypatch.setattr(diagnostic, "put_component_pose", scene.put_pose)
    scene.mode = "overlap"
    original = scene.pair().originals
    claimed_seat = contact.ContactSolution(
        0.0, None, 0.0, 0, "already_seated", "native_distance", 0.0
    )

    with pytest.raises(RuntimeError, match="interferes"):
        diagnostic.verify_witness(
            scene,
            "spring",
            "seat",
            (1.0, 0.0, 0.0),
            1.0,
            original,
            claimed_seat,
            {},
            "independent fixture witness",
        )
    assert scene.spring.Transform2.ArrayData == original["spring"]
    assert scene.seat.Transform2.ArrayData == original["seat"]

"""Offline behavioral regressions for static native spring contact."""

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
        assert self.state == tool.state == "active"
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

    def GetBodies3(self, body_type: int):
        assert body_type == 0
        return tuple(self.bodies), tuple(0 for _body in self.bodies)


class _Scene:
    def __init__(self) -> None:
        self.mode = "clear"
        self.distance_m = 0.0
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

    def GetComponentByName(self, name: str):
        return self.components.get(name)

    def ClosestDistance(self, first, second):
        assert first is self.spring
        assert second is self.seat
        return self.distance_m, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)

    def intersection(self, target: str, tool: str):
        if target != "spring-second" or tool != "seat-body":
            return None, 0
        if self.mode == "overlap":
            return (_IntersectionBody(_MICROSCOPIC_OVERLAP_MM3),), 0
        if self.mode in ("boolean-fail", "modeler-overlap"):
            return None, 1058  # swBodyOperationBooleanFail
        if self.mode == "unknown-fail":
            return None, 42
        return None, 0


@pytest.fixture
def scene(monkeypatch):
    value = _Scene()
    monkeypatch.setattr(contact, "_early_bound", value.bind)
    monkeypatch.setattr(contact, "dispatch_array", lambda values: values)
    return value


def test_later_body_overlap_cannot_pass_even_when_distance_is_zero(scene) -> None:
    scene.mode = "overlap"
    scene.distance_m = 0.0

    with pytest.raises(RuntimeError, match="components intersect"):
        contact.assert_native_contact(
            scene,
            "spring",
            "seat",
            maximum_distance_mm=0.01,
            label="microscopic later-body overlap",
        )


def test_positive_native_predicate_rejects_unconstructible_intersection(scene) -> None:
    scene.mode = "modeler-overlap"

    evidence = contact.native_component_interference(
        scene, "spring", "seat", label="unconstructible overlap"
    )

    assert evidence.state == "interfering"
    assert evidence.volume_mm3 is None
    assert evidence.boolean_failure_status == 1058


def test_negative_native_predicate_cannot_certify_boolean_failure_as_clear(
    scene,
) -> None:
    scene.mode = "boolean-fail"

    with pytest.raises(RuntimeError, match=r"\b1058\b"):
        contact.assert_native_contact(
            scene,
            "spring",
            "seat",
            maximum_distance_mm=0.01,
            label="uncertain Boolean witness",
        )


def test_unknown_native_boolean_status_is_fatal(scene) -> None:
    scene.mode = "unknown-fail"

    with pytest.raises(RuntimeError, match=r"\b42\b"):
        contact.assert_native_contact(
            scene,
            "spring",
            "seat",
            maximum_distance_mm=0.01,
            label="unknown Boolean result",
        )


def test_successful_zero_volume_is_not_overruled_by_another_kernel(scene) -> None:
    scene.mode = "clear-modeler-overlap"

    evidence = contact.native_component_interference(
        scene, "spring", "seat", label="measured native clear"
    )

    assert evidence.state == "clear"
    assert evidence.volume_mm3 == 0.0
    assert evidence.witness == "solid_intersection"


def test_native_zero_overlap_plus_bounded_distance_passes(scene) -> None:
    scene.distance_m = 4.25e-6

    measured = contact.assert_native_contact(
        scene,
        "spring",
        "seat",
        maximum_distance_mm=0.005,
        label="bounded static seat",
    )

    assert measured == pytest.approx(0.00425)


def test_excessive_native_distance_fails(scene) -> None:
    scene.distance_m = 5.01e-6

    with pytest.raises(RuntimeError, match="exceeds calibrated maximum"):
        contact.assert_native_contact(
            scene,
            "spring",
            "seat",
            maximum_distance_mm=0.005,
            label="open static seat",
        )


@pytest.mark.parametrize("distance_m", [-1e-9, float("nan"), float("inf")])
def test_invalid_native_distance_fails(scene, distance_m: float) -> None:
    scene.distance_m = distance_m

    with pytest.raises(RuntimeError, match="finite nonnegative"):
        contact.assert_native_contact(
            scene,
            "spring",
            "seat",
            maximum_distance_mm=0.005,
            label="invalid static distance",
        )


@pytest.mark.parametrize("maximum", [-1.0, float("nan"), float("inf")])
def test_invalid_calibrated_maximum_fails(scene, maximum: float) -> None:
    with pytest.raises(ValueError, match="finite and nonnegative"):
        contact.assert_native_contact(
            scene,
            "spring",
            "seat",
            maximum_distance_mm=maximum,
            label="invalid calibrated maximum",
        )

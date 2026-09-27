"""Regressions: a non-blind wizard tap commits its thread class and termination.

InitializeHole/CreateFeature discard pre-create thread metadata (016c990f8,
top-frame), so a through tap whose metadata is never written back saves as a
blind thread of depth 0 with no class. Its native callout then prints
``4-40 UNC <depth> 0.00``. The v37 arbor-pedestal apex tap did exactly that:
the planar ``wizard_holes`` path wrote the metadata back, the radial
``wizard_hole_on_cylinder`` path did not. These drive both paths through a fake
SolidWorks and read what the committed definition holds.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import _common
import _holes
from _hole_spec import HoleSpec

# swWzdHoleThreadEndCondition / swEndConditions_e values as the wizard stores them.
_BLIND = 0
_THROUGH_NEXT = _holes._ENDS["through_next"]
_TAPPED = 4


class _Result:
    is_success = True
    data = None
    error = None


class _Definition:
    """A wizard definition: writable until committed, then read back."""

    def __init__(self, owner: "_Feature") -> None:
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_oleobj_", self)
        object.__setattr__(self, "_values", dict(owner.committed))

    def __getattr__(self, name: str) -> Any:
        return self._values.get(name, 0.0)

    def __setattr__(self, name: str, value: Any) -> None:
        self._values[name] = value

    def AccessSelections(self, _model: Any, _component: Any) -> bool:
        self._owner.log.append("AccessSelections")
        return True

    def ReleaseSelectionAccess(self) -> None:
        self._owner.log.append("ReleaseSelectionAccess")


class _Feature:
    def __init__(self, sketch_feature: Any, committed: dict[str, Any]) -> None:
        self.committed = committed
        self.log: list[str] = []
        self.Name = "HoleWzd1"
        self._sketch_feature = sketch_feature

    def GetDefinition(self) -> _Definition:
        return _Definition(self)

    def ModifyDefinition(
        self, definition: _Definition, _model: Any, _callout: Any
    ) -> bool:
        self.log.append("ModifyDefinition")
        self.committed.update(definition._values)
        return True

    def GetFirstSubFeature(self) -> Any:
        return self._sketch_feature

    def GetFirstDisplayDimension(self) -> None:
        return None


class _SketchPoint:
    def SetCoords(self, *_coords: float) -> bool:
        return True


class _Sketch:
    def Is3D(self) -> bool:
        return True

    def GetSketchPoints2(self) -> list[_SketchPoint]:
        return [_SketchPoint()]


class _SketchFeature:
    Name = "3DSketch1"

    def GetTypeName2(self) -> str:
        return "ProfileFeature"

    def GetSpecificFeature2(self) -> _Sketch:
        return _Sketch()

    def GetNextSubFeature(self) -> None:
        return None


class _Cylinder:
    """The R11 crown about the bore axis (model Z), in meters."""

    def IsCylinder(self) -> bool:
        return True

    CylinderParams = (0.0, 0.039718, 0.0, 0.0, 0.0, 1.0, 0.011)


class _CrownFace:
    def GetSurface(self) -> _Cylinder:
        return _Cylinder()

    def GetBox(self) -> tuple[float, ...]:
        return (-0.011, 0.028, -0.002, 0.011, 0.051, 0.008)

    def Select2(self, _append: bool, _mark: int) -> bool:
        return True


class _FeatureManager:
    def __init__(self, feature: _Feature) -> None:
        self._feature = feature

    def CreateDefinition(self, _kind: int) -> Any:
        return SimpleNamespace(InitializeHole=lambda *args: None)

    def CreateFeature(self, _data: Any) -> _Feature:
        return self._feature


class _Model:
    def __init__(self, feature: _Feature) -> None:
        self.FeatureManager = _FeatureManager(feature)
        self.SketchManager = object()
        self.Extension = SimpleNamespace(SelectByID2=lambda *args: True)

    def GetBodies2(self, _kind: int, _visible_only: bool) -> list[Any]:
        return [SimpleNamespace(GetFaces=lambda: [_CrownFace()])]

    def FeatureByName(self, name: str) -> Any:
        return SimpleNamespace(Name=name)

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def EditSketch(self) -> None:
        pass

    def EditRebuild3(self) -> bool:
        return True


@pytest.fixture
def fake_seat(monkeypatch):
    """A seat whose wizard initializes a through-next tap the way SolidWorks
    does: the termination on the hole, but the THREAD blind with no class."""
    monkeypatch.setattr(_holes, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(_holes, "blank_sketch_feature", lambda *args: None)
    monkeypatch.setattr(_common, "check", lambda _label, result: result.data)
    from solidworks_mcp.adapters.solidworks import sketch

    monkeypatch.setattr(sketch, "_add_sketch_constraint_impl", lambda *args: _Result())
    feature = _Feature(
        _SketchFeature(),
        committed={
            "EndCondition": _THROUGH_NEXT,
            "ThreadEndCondition": _BLIND,
            "ThreadClass": "",
            "ThreadDepth": 0.0,
            "FastenerSize": "#4-40",
        },
    )
    model = _Model(feature)
    adapter = SimpleNamespace(
        currentModel=model,
        currentSketchManager=None,
        _register_sketch_entity=lambda kind, entity: f"{kind}:{id(entity)}",
    )
    return adapter, feature


def test_radial_through_next_tap_commits_thread_class_and_termination(
    fake_seat,
) -> None:
    adapter, feature = fake_seat
    spec = HoleSpec("tapped", "#4-40", end="through_next")

    _holes.wizard_hole_on_cylinder(
        adapter,
        spec,
        [0.0, 50.718, 3.0],
        "apex set-screw tap (#4-40)",
        name="SetScrewTap",
        point_planes=("SetScrewStationPlane", "Right Plane"),
    )

    assert feature.committed["ThreadClass"] == "2B"
    assert feature.committed["ThreadEndCondition"] == _THROUGH_NEXT
    assert "ModifyDefinition" in feature.log


def test_radial_tap_fails_loud_when_the_seat_drops_the_termination(
    fake_seat, monkeypatch
) -> None:
    """The readback, not the write, is the proof: a seat that accepts the edit
    but keeps the blind thread must stop the build, not ship a 0.00 callout."""
    adapter, feature = fake_seat

    def drop_termination(definition, _model, _callout) -> bool:
        feature.committed.update(
            {k: v for k, v in definition._values.items() if k != "ThreadEndCondition"}
        )
        return True

    monkeypatch.setattr(feature, "ModifyDefinition", drop_termination)
    with pytest.raises(RuntimeError, match="ThreadEndCondition"):
        _holes.wizard_hole_on_cylinder(
            adapter,
            HoleSpec("tapped", "#4-40", end="through_next"),
            [0.0, 50.718, 3.0],
            "apex set-screw tap (#4-40)",
            point_planes=("SetScrewStationPlane", "Right Plane"),
        )


def test_a_blind_radial_tap_is_refused_before_any_write_back(fake_seat) -> None:
    """The planar path writes thread metadata back to non-blind taps only.
    The radial path mirrors that gate, but a blind radial hole would need the
    HoleWizard5 path re-probed on a cylinder, so it is refused at the door:
    no feature, no write-back, no readback of a thread nobody asked for."""
    adapter, feature = fake_seat

    with pytest.raises(ValueError, match="through_all and through_next only"):
        _holes.wizard_hole_on_cylinder(
            adapter,
            HoleSpec("tapped", "#4-40", end="blind", depth_mm=4.0),
            [0.0, 50.718, 3.0],
            "blind radial tap",
            point_planes=("SetScrewStationPlane", "Right Plane"),
        )

    assert feature.log == []
    assert feature.committed["ThreadEndCondition"] == _BLIND


def test_radial_plain_hole_leaves_the_definition_alone(fake_seat) -> None:
    """Only taps carry thread metadata: a radial clearance or drilled hole must
    not pay a ModifyDefinition (a redundant write can corrupt the hole type,
    see _holes.DIAMETER_TOLERANCE_MM)."""
    adapter, feature = fake_seat

    _holes.wizard_hole_on_cylinder(
        adapter,
        HoleSpec("drilled_number", "#43", end="through_all"),
        [0.0, 50.718, 3.0],
        "radial drilled hole",
        point_planes=("SetScrewStationPlane", "Right Plane"),
    )

    assert "ModifyDefinition" not in feature.log

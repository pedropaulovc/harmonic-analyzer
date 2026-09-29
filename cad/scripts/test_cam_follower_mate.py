r"""SolidWorks-free contract for ``_assembly_couplings.cam_follower_mate``.

The cam-follower mate is the one live contact between the pinion rig's cam and
its follower pin, so it must bind exactly the cam OD and the pin shank, under
the ICamFollowerMateFeatureData role marks, and through ``CreateMate``.  A
stateful fake assembly (components -> part bodies -> faces, a selection
manager, ``CreateMateData``/``CreateMate`` and the persisted ``IMate2``) pins:

* each face is the component's only cylinder of its radius, mapped into the
  assembly and selected cam-first under marks 1 and 8, then built by
  ``CreateMateData(9)`` -> ``EntitiesToMate`` -> ``CreateMate`` + rebuild, never
  the obsolete ``AddMate5``;
* a missing or ambiguous face, a refused selection, a failed ``CreateMate`` or
  a hard feature error raises before or instead of a silent mate;
* a persisted mate that does not read back as the intended face pair raises.

Run: ``uv run python -m pytest cad/scripts/test_cam_follower_mate.py -q``
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _assembly_couplings import CylinderFace, cam_follower_mate  # noqa: E402

CAM = CylinderFace("pinion-cam-1", (4.08, 62.96, -75.34), (0.0, 0.0, 1.0), 7.3)
PIN = CylinderFace(
    "pinion-cam-pin-1", (-15.35, 69.74, -75.34), (0.9911, 0.1329, 0.0), 2.0
)


class Surface:
    def __init__(self, radius_mm):
        self.radius_mm = radius_mm

    def IsCylinder(self):  # noqa: N802
        return self.radius_mm is not None

    @property
    def CylinderParams(self):  # noqa: N802
        return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, self.radius_mm / 1000.0)


class PartFace:
    """A part-space face; ``radius_mm=None`` is a non-cylindrical face."""

    def __init__(self, radius_mm):
        self.surface = Surface(radius_mm)

    def GetSurface(self):  # noqa: N802
        return self.surface


class Body:
    def __init__(self, faces):
        self.faces = faces

    def GetFaces(self):  # noqa: N802
        return tuple(self.faces)


class Part:
    def __init__(self, faces):
        self.body = Body(faces)

    def GetBodies2(self, body_type, visible_only):  # noqa: N802
        assert (body_type, visible_only) == (0, False)
        return (self.body,)


class SelectData:
    Mark = 0


class SelectionManager:
    def __init__(self):
        self.items = []

    def CreateSelectData(self):  # noqa: N802
        return SelectData()

    def GetSelectedObjectCount2(self, mark):  # noqa: N802
        assert mark == -1
        return len(self.items)

    def GetSelectedObject6(self, index, mark):  # noqa: N802
        assert mark == -1
        return self.items[index - 1][0]


class AssemblyFace:
    """``IComponent2.GetCorrespondingEntity`` of a part face."""

    def __init__(self, component, part_face):
        self.component = component
        self.part_face = part_face

    def Select4(self, append, data):  # noqa: N802
        assembly = self.component.assembly
        if not assembly.selectable:
            return False
        if not append:
            assembly.SelectionManager.items.clear()
        assembly.SelectionManager.items.append((self, data.Mark))
        return True

    def entity_params(self):
        """``IMateEntity2.EntityParams`` of this face: metres, assembly frame."""
        face = self.component.face
        point = [value / 1000.0 for value in face.axis_point_mm]
        radius = self.part_face.surface.radius_mm / 1000.0
        return (*point, *face.axis, radius, 0.0)


class Component:
    def __init__(self, assembly, face, part_faces):
        self.assembly = assembly
        self.face = face
        self.Name2 = face.component
        self.part = Part(part_faces)

    def GetModelDoc2(self):  # noqa: N802
        return self.part

    def GetCorrespondingEntity(self, part_face):  # noqa: N802
        assert part_face in self.part.body.faces
        return AssemblyFace(self, part_face)


class MateEntity:
    def __init__(self, face):
        self.ReferenceComponent = face.component
        self.ReferenceType2 = 2  # swSelFACES
        self.EntityParams = face.entity_params()


class Mate:
    def __init__(self, entities):
        self.Type = 9  # swMateCAMFOLLOWER
        self.entities = entities

    def GetMateEntityCount(self):  # noqa: N802
        return len(self.entities)

    def MateEntity(self, index):  # noqa: N802
        return self.entities[index]


class MateFeature:
    def __init__(self, name, mate, error):
        self.Name = name
        self.mate = mate
        self.error = error

    def GetSpecificFeature2(self):  # noqa: N802
        return self.mate

    def GetErrorCode2(self):  # noqa: N802
        return self.error


class CamFollowerData:
    """ICamFollowerMateFeatureData with the generated indexed setter contract."""

    __slots__ = ("ErrorStatus", "MateAlignment", "_entities", "_calls")

    def __init__(self, calls):
        self.ErrorStatus = 4  # swAddMateError_IncorrectSelections, read on failure
        self.MateAlignment = -1
        self._entities = [None, None]
        self._calls = calls

    @property
    def entities(self):
        return self._entities

    def SetEntitiesToMate(self, index, entity):  # noqa: N802
        assert index in (0, 1)
        self._calls.append(("SetEntitiesToMate", index, entity))
        self._entities[index] = entity


class Assembly:
    """IModelDoc2 + IAssemblyDoc of a drive-train stand-in."""

    def __init__(self, cam_faces, pin_faces):
        self.SelectionManager = SelectionManager()
        self.calls = []
        self.selectable = True
        self.create_fails = False
        self.error = (0, False)
        self.persist = lambda mate: mate
        self.mates = {}
        self.created = None
        strap = CylinderFace("pinion-bracket-1", PIN.axis_point_mm, PIN.axis, 2.0)
        self.components = [
            Component(self, CAM, cam_faces),
            Component(self, PIN, pin_faces),
            # The strap seat bore is line-to-line with the pin shank.
            Component(self, strap, [PartFace(2.0), PartFace(None)]),
        ]

    def component(self, name):
        return next(c for c in self.components if c.Name2 == name)

    def ClearSelection2(self, all_):  # noqa: N802
        self.calls.append("ClearSelection2")
        self.SelectionManager.items.clear()
        return True

    def GetComponentByName(self, name):  # noqa: N802
        return next((c for c in self.components if c.Name2 == name), None)

    def CreateMateData(self, mate_type):  # noqa: N802
        self.calls.append(("CreateMateData", mate_type))
        return CamFollowerData(self.calls) if mate_type == 9 else None

    def CreateMate(self, data):  # noqa: N802
        entities = list(data.entities)
        self.created = {
            "selection": [
                (face.component.Name2, face.part_face, mark)
                for face, mark in self.SelectionManager.items
            ],
            "entities": entities,
            "alignment": data.MateAlignment,
        }
        self.calls.append("CreateMate")
        if self.create_fails:
            return None
        name = f"CamMateTangent{len(self.mates) + 1}"
        mate = self.persist(Mate([MateEntity(face) for face in entities]))
        self.mates[name] = MateFeature(name, mate, self.error)
        return self.mates[name]

    def AddMate5(self, *args):  # noqa: N802
        self.calls.append("AddMate5")
        return None

    def EditRebuild3(self):  # noqa: N802
        self.calls.append("EditRebuild3")
        return True

    def FeatureByName(self, name):  # noqa: N802
        return self.mates.get(name)


class Adapter:
    def __init__(self, model):
        self.currentModel = model

    def _attempt(self, callback, default=None):
        try:
            return callback()
        except Exception:
            return default


def _scene(cam_faces=None, pin_faces=None):
    cam_od, pin_shank = PartFace(7.3), PartFace(2.0)
    # Cam: OD, Ø6.40 rod bore, M2.5 tap drill, end faces.  Pin: shank, domed cap.
    cam_faces = cam_faces or [PartFace(None), cam_od, PartFace(3.2), PartFace(1.025)]
    pin_faces = pin_faces or [PartFace(None), pin_shank]
    assembly = Assembly(cam_faces, pin_faces)
    return Adapter(assembly), assembly, cam_od, pin_shank


def _mate(adapter):
    return asyncio.run(cam_follower_mate(adapter, CAM, PIN, label="cam on pin"))


def test_binds_the_unique_cylinders_under_role_marks_through_createmate():
    adapter, assembly, cam_od, pin_shank = _scene()

    result = _mate(adapter)

    assert result["name"] == "CamMateTangent1"
    assert assembly.created["selection"] == [
        ("pinion-cam-1", cam_od, 1),
        ("pinion-cam-pin-1", pin_shank, 8),
    ]
    entities = assembly.created["entities"]
    assert [(e.component.Name2, e.part_face) for e in entities] == [
        ("pinion-cam-1", cam_od),
        ("pinion-cam-pin-1", pin_shank),
    ]
    assert assembly.created["alignment"] == 2  # swMateAlignCLOSEST, as the SDK example
    assert assembly.calls == [
        "ClearSelection2",
        ("CreateMateData", 9),
        ("SetEntitiesToMate", 0, entities[0]),
        ("SetEntitiesToMate", 1, entities[1]),
        "CreateMate",
        "ClearSelection2",
        "EditRebuild3",
    ]
    assert assembly.SelectionManager.items == []


@pytest.mark.parametrize(
    "pin_faces",
    [
        pytest.param([PartFace(None), PartFace(2.5)], id="no-shank-radius"),
        pytest.param([PartFace(2.0), PartFace(2.0)], id="split-shank"),
    ],
)
def test_missing_or_ambiguous_face_refuses_before_selecting(pin_faces):
    adapter, assembly, _, _ = _scene(pin_faces=pin_faces)

    with pytest.raises(RuntimeError, match="pinion-cam-pin-1 has . cylinders"):
        _mate(adapter)

    assert assembly.calls == []


def test_same_component_for_both_roles_is_refused():
    adapter, assembly, _, _ = _scene()

    with pytest.raises(ValueError, match="both on 'pinion-cam-1'"):
        asyncio.run(cam_follower_mate(adapter, CAM, CAM, label="cam on pin"))

    assert assembly.calls == []


def test_refused_selection_raises_before_createmate():
    adapter, assembly, _, _ = _scene()
    assembly.selectable = False

    with pytest.raises(RuntimeError, match="cannot select the pinion-cam-1 face"):
        _mate(adapter)

    assert "CreateMate" not in assembly.calls


def test_failed_createmate_raises_without_a_fallback_mate():
    adapter, assembly, _, _ = _scene()
    assembly.create_fails = True

    with pytest.raises(Exception, match="CreateMate failed .*incorrect selections"):
        _mate(adapter)

    assert "AddMate5" not in assembly.calls
    assert "EditRebuild3" not in assembly.calls
    assert assembly.mates == {}


def test_hard_feature_error_on_the_created_mate_raises():
    adapter, assembly, _, _ = _scene()
    assembly.error = (47, False)

    with pytest.raises(RuntimeError, match="hard feature error 47"):
        _mate(adapter)


def _retype(mate):
    mate.Type = 0  # swMateCOINCIDENT
    return mate


def _single(mate):
    mate.entities = mate.entities[:1]
    return mate


def _both_on_cam(mate):
    mate.entities = [mate.entities[0], mate.entities[0]]
    return mate


def _on_strap(mate):
    pin = mate.entities[1].ReferenceComponent
    mate.entities[1].ReferenceComponent = pin.assembly.component("pinion-bracket-1")
    return mate


def _edge(mate):
    mate.entities[1].ReferenceType2 = 1  # swSelEDGES
    return mate


def _bore(mate):
    params = list(mate.entities[0].EntityParams)
    params[6] = 0.0032
    mate.entities[0].EntityParams = tuple(params)
    return mate


def _tilted(mate):
    params = list(mate.entities[0].EntityParams)
    params[3:6] = [0.1, 0.0, 0.995]
    mate.entities[0].EntityParams = tuple(params)
    return mate


def _eccentric(mate):
    params = list(mate.entities[0].EntityParams)
    params[1] += 0.002  # the cam BORE axis sits ECC = 2 mm off the OD axis
    mate.entities[0].EntityParams = tuple(params)
    return mate


@pytest.mark.parametrize(
    ("persist", "message"),
    [
        pytest.param(_retype, "not cam-follower", id="mate-type"),
        pytest.param(_single, "1 entities", id="entity-count"),
        pytest.param(_both_on_cam, "expected one each", id="same-component"),
        pytest.param(_on_strap, "expected one each", id="wrong-component"),
        pytest.param(_edge, "not FACE", id="entity-type"),
        pytest.param(_bore, "radius", id="radius"),
        pytest.param(_tilted, "axis", id="axis-direction"),
        pytest.param(_eccentric, "mm off its model", id="axis-position"),
    ],
)
def test_persisted_mate_must_read_back_as_the_intended_face_pair(persist, message):
    adapter, assembly, _, _ = _scene()
    assembly.persist = persist

    with pytest.raises(RuntimeError, match=message):
        _mate(adapter)

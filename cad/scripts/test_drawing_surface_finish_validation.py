"""Drawing surface-finish leaders must qualify their part-owned model face."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pytest

import _drawing_common
import _part_pmi
from _gtol_spec import ConeFace, CylinderFace, PlanarFace, SphereFace, TorusFace
from _part_pmi import _FaceGeometry
from _surface_finish import SurfaceFinishControl


@dataclass
class _Entity:
    faces: tuple[Any, ...] = ()
    face: Any | None = None

    def GetTwoAdjacentFaces2(self) -> tuple[Any, ...]:
        return self.faces

    def GetFace(self) -> Any | None:
        return self.face


def _control() -> SurfaceFinishControl:
    return SurfaceFinishControl("bore", 1.6, CylinderFace(10.0))


def _geometry(face: Any, diameter_mm: float) -> _FaceGeometry:
    return _FaceGeometry(
        face=face,
        identity=4002,
        parameters=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, diameter_mm / 2000.0),
        outward_normal=None,
        box=(),
    )


@pytest.mark.parametrize("entity_type", ("EDGE", "SILHOUETTE", "FACE"))
def test_surface_finish_accepts_controlled_face_for_every_entity_path(
    monkeypatch: pytest.MonkeyPatch, entity_type: str
) -> None:
    controlled_face = object()
    other_face = object()
    entity = _Entity(faces=(other_face, controlled_face), face=controlled_face)
    selected = controlled_face if entity_type == "FACE" else entity
    geometries = {
        id(controlled_face): _geometry(controlled_face, 10.0),
        id(other_face): _geometry(other_face, 6.0),
    }
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        "_part_pmi._face_geometry", lambda face: geometries[id(face)]
    )

    signatures = _drawing_common._validate_surface_finish_control_face(
        selected, entity_type=entity_type, control=_control(), label="bearing finish"
    )

    assert any(item["geometry"].face is controlled_face for item in signatures)


@pytest.mark.parametrize("entity_type", ("EDGE", "SILHOUETTE", "FACE"))
def test_surface_finish_rejects_entity_without_controlled_face(
    monkeypatch: pytest.MonkeyPatch, entity_type: str
) -> None:
    wrong_face = object()
    entity = _Entity(faces=(wrong_face,), face=wrong_face)
    selected = wrong_face if entity_type == "FACE" else entity
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        "_part_pmi._face_geometry", lambda face: _geometry(face, 6.0)
    )

    with pytest.raises(
        RuntimeError,
        match="selected .* does not touch controlled surface-finish face",
    ):
        _drawing_common._validate_surface_finish_control_face(
            selected,
            entity_type=entity_type,
            control=_control(),
            label="bearing finish",
        )


def test_surface_finish_rejects_unverifiable_entity_type() -> None:
    with pytest.raises(ValueError, match="expected EDGE, SILHOUETTE, or FACE"):
        _drawing_common._surface_finish_entity_faces(
            object(), entity_type="VERTEX", label="bearing finish"
        )


def test_add_surface_finish_validates_part_control_without_audit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = object()
    monkeypatch.delenv("HARMONIC_SURFACE_AUDIT", raising=False)
    monkeypatch.setattr(
        _drawing_common,
        "_select_annotation_entity",
        lambda *_args, **_kwargs: selected,
    )

    def reject(
        entity: Any,
        *,
        entity_type: str,
        control: SurfaceFinishControl,
        label: str,
    ) -> tuple[dict[str, Any], ...]:
        assert entity is selected
        assert entity_type == "EDGE"
        assert control is finish
        assert label == "bearing finish"
        raise RuntimeError("wrong controlled face")

    monkeypatch.setattr(
        _drawing_common, "_validate_surface_finish_control_face", reject
    )
    finish = _control()

    with pytest.raises(RuntimeError, match="wrong controlled face"):
        _drawing_common.add_surface_finish(
            object(),
            object(),
            edge_xy=(0.1, 0.1),
            symbol_xy=(0.2, 0.2),
            control=finish,
            label="bearing finish",
        )


class _Annotation:
    """The ``IAnnotation`` readbacks the surface-finish attachment guard sends."""

    def __init__(self, entities: tuple[Any, ...], types: tuple[int, ...]) -> None:
        self.entities, self.types = entities, types

    def GetAttachedEntities3(self) -> tuple[Any, ...]:  # noqa: N802
        return self.entities

    def GetAttachedEntityTypes(self) -> tuple[int, ...]:  # noqa: N802
        return self.types

    def GetLeaderCount(self) -> int:  # noqa: N802
        return 1

    def IsDangling(self) -> bool:  # noqa: N802
        return False


class _App:
    def IsSame(self, left: Any, right: Any) -> int:  # noqa: N802
        return int(left is right)


class _Adapter:
    swApp = _App()


def test_surface_finish_guard_accepts_the_inserted_entity() -> None:
    edge = object()
    _drawing_common._assert_surface_finish_attached(
        _Adapter(), _Annotation((edge,), (1,)), edge, entity_type="EDGE", label="bore"
    )


@pytest.mark.parametrize(
    ("entities", "types"),
    (
        # A moved leader on the sfprobe leaves: IsAttached True, no entity.
        ((), ()),
        # A landing that resolved to the neighbouring face.
        ((object(),), (1,)),
    ),
    ids=("detached", "neighbour"),
)
def test_surface_finish_guard_rejects_a_symbol_off_its_entity(
    entities: tuple[Any, ...], types: tuple[int, ...]
) -> None:
    with pytest.raises(RuntimeError, match=r"lost its attachment \(bore\)"):
        _drawing_common._assert_surface_finish_attached(
            _Adapter(), _Annotation(entities, types), object(), entity_type="EDGE",
            label="bore",
        )


@pytest.mark.parametrize(
    ("types", "attached"), (((46,), True), ((), False), ((1,), False))
)
def test_silhouette_finish_guard_requires_one_silhouette(
    types: tuple[int, ...], attached: bool
) -> None:
    # IsSame reads 0 for a silhouette finish even when unmoved, so the guard
    # reads the attached type instead of identity.
    annotation = _Annotation((object(),) * len(types), types)
    check = lambda: _drawing_common._assert_surface_finish_attached(  # noqa: E731
        _Adapter(), annotation, object(), entity_type="SILHOUETTE", label="journal"
    )
    if attached:
        check()
    else:
        with pytest.raises(RuntimeError, match="lost its silhouette attachment"):
            check()


def _signature(radius: float, box_x: float = 0.01) -> dict[str, Any]:
    return {
        "identity": 4002,
        "parameters": (0.197, 0.0254, -0.112, 0.0, 1.0, 0.0, radius),
        "normal": None,
        "box": (-box_x, 0.0, 0.0, box_x, 0.01, 0.01),
    }


@pytest.mark.parametrize(
    ("attached_signature", "accepted"),
    (
        # The section-view socket bore: IsSame 0, the selected face's surface.
        (_signature(0.01275), True),
        # A coaxial counterbore of another size.
        (_signature(0.015), False),
        # The same surface, split into another face with its own extent.
        (_signature(0.01275, box_x=0.02), False),
    ),
    ids=("same-face", "other-surface", "other-extent"),
)
def test_face_finish_guard_falls_back_to_the_face_surface_and_extent(
    monkeypatch: pytest.MonkeyPatch,
    attached_signature: dict[str, Any],
    accepted: bool,
) -> None:
    selected, attached = object(), object()
    signatures = {id(selected): _signature(0.01275), id(attached): attached_signature}
    monkeypatch.setattr(
        _drawing_common,
        "_surface_finish_face_signatures",
        lambda faces: tuple(signatures[id(face)] for face in faces),
    )
    check = lambda: _drawing_common._assert_surface_finish_attached(  # noqa: E731
        _Adapter(), _Annotation((attached,), (2,)), selected, entity_type="FACE",
        label="socket bore",
    )
    if accepted:
        check()
    else:
        with pytest.raises(RuntimeError, match=r"lost its attachment \(socket bore\)"):
            check()


# _part_pmi._resolve_faces: the one raw walk the surface-finish faces come from.
#
# The doubles are raw dispatches, as SolidWorks hands them to the walk: they
# answer ``InvokeTypes`` only and assert the whole (dispid, lcid, flags,
# return type, argument types) header of the SolidWorks 2026 type library
# (flags 1 = method, 2 = property get; 3 = int, 9 = IDispatch, 11 = bool,
# 12 = VARIANT).  A read of a member the walk should not send fails.

GET_FIRST_FACE = (1, 0, 1, (9, 0), ())
GET_NEXT_FACE = (2, 0, 1, (9, 0), ())
GET_SURFACE = (3, 0, 1, (9, 0), ())
GET_BOX = (55, 0, 1, (12, 0), ())
FACE_IN_SURFACE_SENSE = (10, 0, 1, (11, 0), ())
IDENTITY = (9, 0, 1, (3, 0), ())
PARAMETERS = {
    4001: (1, 0, 2, (12, 0), ()),  # PlaneParams
    4002: (2, 0, 2, (12, 0), ()),  # CylinderParams
    4003: (82, 0, 2, (12, 0), ()),  # ConeParams2
    4004: (4, 0, 2, (12, 0), ()),  # SphereParams
    4005: (5, 0, 2, (12, 0), ()),  # TorusParams
}


class _RawDispatch:
    """A bare ``PyIDispatch`` stand-in keyed by dispid; any other header fails."""

    def __init__(self, answers) -> None:
        self.answers = answers
        self.calls: list[tuple[Any, ...]] = []

    def InvokeTypes(self, dispid, lcid, flags, ret_type, arg_types, *args):  # noqa: N802
        header = (dispid, lcid, flags, ret_type, arg_types)
        self.calls.append(header)
        assert dispid in self.answers, f"unexpected dispid {dispid}"
        expected, answer = self.answers[dispid]
        assert header == expected
        return answer(*args) if callable(answer) else answer


_BOX = (-0.01, -0.01, -0.01, 0.01, 0.01, 0.01)


def _raw_face(identity: int, parameters, *, flipped: bool = False) -> _RawDispatch:
    surface = _RawDispatch(
        {
            IDENTITY[0]: (IDENTITY, identity),
            PARAMETERS[identity][0]: (PARAMETERS[identity], parameters),
        }
    )
    face = _RawDispatch(
        {
            GET_SURFACE[0]: (GET_SURFACE, surface),
            GET_BOX[0]: (GET_BOX, _BOX),
            FACE_IN_SURFACE_SENSE[0]: (FACE_IN_SURFACE_SENSE, flipped),
            GET_NEXT_FACE[0]: (GET_NEXT_FACE, lambda: face.following),
        }
    )
    face.surface = surface
    face.identity, face.parameters, face.flipped = identity, parameters, flipped
    face.following = None
    return face


class _Part:
    """The ``IPartDoc`` whose one body's raw face list the walk steps through."""

    def __init__(self, *faces: _RawDispatch) -> None:
        # A returned face is bound through the checked-in makepy wrapper.
        pytest.importorskip("win32com.client")
        for face, following in zip(faces, faces[1:]):
            face.following = following
        self.body = _RawDispatch({GET_FIRST_FACE[0]: (GET_FIRST_FACE, faces[0])})

    def GetBodies2(self, *_args):  # noqa: N802
        return [self.body]


def _faces() -> dict[str, _RawDispatch]:
    return {
        "bore": _raw_face(4002, (0, 0, 0, 0, 0, 1, 0.004)),
        "taper": _raw_face(4003, (0, 0, 0, 1, 0, 0, 0.005, math.radians(30.0), 0, 1, 0)),
        # PlaneParams: normal xyz, root point xyz.  The deck's surface sense
        # is flipped, so its OUTWARD normal is -Z and it sits at -10 mm on it.
        "deck": _raw_face(4001, (0, 0, 1, 0, 0, 0.01), flipped=True),
        "top": _raw_face(4001, (0, 0, 1, 0, 0, 0.02)),
        "rim": _raw_face(4001, (0, 0, 1, 0, 0, 0.02)),
        "ball": _raw_face(4004, (0, 0, 0, 0.003)),
        "torus": _raw_face(4005, (0, 0, 0, 0, 0, 1, 0.01, 0.002)),
    }


_SPECS = {
    "bore": CylinderFace(8.0),
    "taper": ConeFace(30.0),
    "deck": PlanarFace((0.0, 0.0, -1.0), -10.0),
    "ball": SphereFace(6.0),
    "torus": TorusFace(10.0, 2.0),
}


@pytest.mark.parametrize("label", sorted(_SPECS))
def test_each_spec_type_resolves_its_one_raw_face(label: str) -> None:
    faces = _faces()
    resolved = _part_pmi._resolve_faces(_Part(*faces.values()), {label: _SPECS[label]})
    assert resolved[label]._oleobj_ is faces[label]
    # A face of a surface type the spec does not name stops at its identity.
    for name, face in faces.items():
        if face.identity != faces[label].identity:
            assert face.surface.calls == [IDENTITY], name
            assert GET_BOX not in face.calls, name


def test_mixed_spec_types_resolve_in_one_walk() -> None:
    faces = _faces()
    part = _Part(*faces.values())
    resolved = _part_pmi._resolve_faces(part, dict(_SPECS))
    assert {label: face._oleobj_ for label, face in resolved.items()} == {
        label: faces[label] for label in _SPECS
    }
    assert part.body.calls == [GET_FIRST_FACE]
    assert all(face.calls.count(GET_SURFACE) == 1 for face in faces.values())


@pytest.mark.parametrize("label", sorted(_SPECS))
def test_a_twin_face_fails_the_exactly_one_contract(label: str) -> None:
    faces = _faces()
    face = faces[label]
    twin = _raw_face(face.identity, face.parameters, flipped=face.flipped)
    part = _Part(*faces.values(), twin)
    with pytest.raises(RuntimeError, match=f"^{label}: face spec .* matched 2 faces"):
        _part_pmi._resolve_faces(part, {label: _SPECS[label]})


def test_coplanar_faces_still_fail_the_exactly_one_contract() -> None:
    with pytest.raises(RuntimeError, match="matched 2 faces"):
        _part_pmi._resolve_faces(
            _Part(*_faces().values()), {"face": PlanarFace((0.0, 0.0, 1.0), 20.0)}
        )


def test_a_spec_no_face_matches_fails_the_exactly_one_contract() -> None:
    with pytest.raises(RuntimeError, match="matched 0 faces"):
        _part_pmi._resolve_faces(_Part(*_faces().values()), {"bore": CylinderFace(9.0)})

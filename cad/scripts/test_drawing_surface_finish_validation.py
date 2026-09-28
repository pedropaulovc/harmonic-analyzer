"""Drawing surface-finish leaders must qualify their part-owned model face."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import _drawing_common
import _part_pmi
from _gtol_spec import CylinderFace, PlanarFace
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


# _part_pmi._resolve_faces: the one raw walk the surface-finish faces come from.


class _Surface:
    def __init__(self, identity: int, parameters: tuple[float, ...]) -> None:
        self.Identity = identity
        self.CylinderParams = parameters
        self.PlaneParams = parameters


class _Face:
    def __init__(self, identity, parameters, box, *, flipped=False) -> None:
        self.surface = _Surface(identity, parameters)
        self.box = box
        self.flipped = flipped
        self.next = None
        self.parameter_reads = 0

    def GetSurface(self):
        return self.surface

    def GetBox(self):
        self.parameter_reads += 1
        return self.box

    def FaceInSurfaceSense(self):
        return self.flipped

    def GetNextFace(self):
        return self.next


class _Part:
    def __init__(self, *faces: _Face) -> None:
        for face, following in zip(faces, faces[1:]):
            face.next = following
        self.first = faces[0]

    def GetBodies2(self, *_args):
        part = self

        class _Body:
            def GetFirstFace(self):
                return part.first

        return [_Body()]


_BOX = (-0.01, -0.01, -0.01, 0.01, 0.01, 0.01)


def _faces():
    bore = _Face(4002, (0, 0, 0, 0, 0, 1, 0.004), _BOX)
    # PlaneParams: normal xyz, root point xyz.  The deck's surface sense is
    # flipped, so its OUTWARD normal is -Z and it sits at -10 mm along it.
    deck = _Face(4001, (0, 0, 1, 0, 0, 0.01), _BOX, flipped=True)
    top = _Face(4001, (0, 0, 1, 0, 0, 0.02), _BOX)
    rim = _Face(4001, (0, 0, 1, 0, 0, 0.02), _BOX)
    torus = _Face(4005, (0, 0, 0, 0, 0, 1, 0.01, 0.002), _BOX)
    return bore, deck, top, rim, torus


def test_mixed_spec_types_each_resolve_their_one_face() -> None:
    bore, deck, top, rim, torus = _faces()
    resolved = _part_pmi._resolve_faces(
        _Part(bore, deck, top, rim, torus),
        {"bore": CylinderFace(8.0), "deck": PlanarFace((0.0, 0.0, -1.0), -10.0)},
    )
    assert resolved == {"bore": bore, "deck": deck}
    assert torus.parameter_reads == 0, "a surface type no spec names is not read further"


def test_coplanar_faces_still_fail_the_exactly_one_contract() -> None:
    bore, deck, top, rim, torus = _faces()
    with pytest.raises(RuntimeError, match="matched 2 faces"):
        _part_pmi._resolve_faces(
            _Part(bore, deck, top, rim, torus),
            {"face": PlanarFace((0.0, 0.0, 1.0), 20.0)},
        )

"""``_part_pmi._resolve_faces``: one raw walk, mixed spec types, exact-one."""

from __future__ import annotations

import pytest

import _part_pmi
from _gtol_spec import CylinderFace, PlanarFace


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

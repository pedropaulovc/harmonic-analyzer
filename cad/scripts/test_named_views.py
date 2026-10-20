"""Octant named views: names, geometry and the readback contract (no COM)."""

from __future__ import annotations

import math

import pytest

from _named_views import (
    OCTANT_VIEW_NAMES,
    OCTANTS,
    name_octant_views,
    octant_axes,
    octant_key,
    octant_rotation,
    octant_view_name,
)

_ISOMETRIC_ROWS = (
    1 / math.sqrt(2), 0.0, -1 / math.sqrt(2),
    -1 / math.sqrt(6), 2 / math.sqrt(6), -1 / math.sqrt(6),
    1 / math.sqrt(3), 1 / math.sqrt(3), 1 / math.sqrt(3),
)


def test_octant_names_follow_asme_face_order():
    assert octant_key(1, 1, 1) == "FRONT-TOP-RIGHT"
    assert octant_key(-1, 1, 1) == "FRONT-TOP-LEFT"
    assert octant_key(1, -1, 1) == "FRONT-BOTTOM-RIGHT"
    assert octant_key(-1, -1, -1) == "REAR-BOTTOM-LEFT"
    assert octant_view_name(-1, 1, 1) == "ISO FRONT-TOP-LEFT"
    assert len(OCTANTS) == 8 and len(set(OCTANT_VIEW_NAMES.values())) == 8


def test_octant_rejects_non_signs():
    with pytest.raises(ValueError):
        octant_key(0, 1, 1)


def test_plus_plus_plus_octant_is_the_built_in_isometric():
    assert octant_rotation(1, 1, 1) == pytest.approx(_ISOMETRIC_ROWS, abs=1e-12)


@pytest.mark.parametrize("octant", list(OCTANTS.values()))
def test_every_octant_is_a_right_handed_isometric_with_model_y_up(octant):
    x, y, z = octant_axes(*octant)
    # z looks at the viewer's octant; every model axis is equally foreshortened.
    assert z == pytest.approx(tuple(s / math.sqrt(3) for s in octant), abs=1e-12)
    # model +Y projects UP the sheet, never down, in every octant.
    sx, sy, sz = octant
    assert y[1] > 0 and y == pytest.approx((-sx * sy / math.sqrt(6), 2 / math.sqrt(6), -sz * sy / math.sqrt(6)), abs=1e-12)
    # orthonormal, right-handed.
    for a, b in ((x, y), (y, z), (x, z)):
        assert sum(p * q for p, q in zip(a, b)) == pytest.approx(0.0, abs=1e-12)
    cross = (
        x[1] * y[2] - x[2] * y[1],
        x[2] * y[0] - x[0] * y[2],
        x[0] * y[1] - x[1] * y[0],
    )
    assert cross == pytest.approx(z, abs=1e-12)


class _Transform:
    def __init__(self, data):
        self.data = tuple(data)


class _Utility:
    def CreateTransform(self, data):
        return _Transform(list(data.value))


class _Extension:
    def __init__(self, model):
        self.model = model

    def GetNamedViewRotation(self, name):
        return self.model.named[name]


class _View:
    def __init__(self):
        self.Orientation3 = None


class _Model:
    """Stores what NameView captured: the rotation of the transform last set."""

    def __init__(self, isometric):
        self.isometric = isometric
        self.named = {}
        self.ActiveView = _View()
        self.Extension = _Extension(self)
        self.shown = None

    def GetStandardViewRotation(self, view_id):
        assert view_id == 7
        return self.isometric

    def NameView(self, name):
        self.named[name] = self.ActiveView.Orientation3.data[:9]

    def ShowNamedView2(self, name, view_id):
        self.shown = (name, view_id)


class _Adapter:
    def __init__(self, model):
        self.currentModel = model
        self.swApp = type("App", (), {"GetMathUtility": staticmethod(lambda: _Utility())})()


def _transpose(rotation):
    return tuple(rotation[column + 3 * row] for column in range(3) for row in range(3))


@pytest.mark.parametrize("stored", ["rows", "transposed"])
def test_name_octant_views_matches_the_seat_convention(monkeypatch, stored):
    import _named_views

    monkeypatch.setattr(_named_views, "_early_bound", lambda obj, _iface: obj)
    isometric = _ISOMETRIC_ROWS if stored == "rows" else _transpose(_ISOMETRIC_ROWS)
    model = _Model(isometric)
    named = name_octant_views(_Adapter(model), label="test")
    assert named == {key: f"ISO {key}" for key in OCTANTS}
    expected = octant_rotation(-1, 1, 1)
    if stored == "transposed":
        expected = _transpose(expected)
    assert model.named["ISO FRONT-TOP-LEFT"] == pytest.approx(expected, abs=1e-12)
    assert model.shown == ("*Isometric", 7)


def test_name_octant_views_refuses_an_unknown_convention(monkeypatch):
    import _named_views

    monkeypatch.setattr(_named_views, "_early_bound", lambda obj, _iface: obj)
    model = _Model(tuple(0.0 for _ in range(9)))
    with pytest.raises(RuntimeError, match="matches neither"):
        name_octant_views(_Adapter(model), label="test")

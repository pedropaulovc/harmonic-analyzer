"""Assembly inspection-view capture and rigid-camera turns (no COM)."""

from __future__ import annotations

import math

import pytest

from _assembly_named_views import name_standard_views

_ISOMETRIC_ROWS = (
    1 / math.sqrt(2), 0.0, -1 / math.sqrt(2),
    -1 / math.sqrt(6), 2 / math.sqrt(6), -1 / math.sqrt(6),
    1 / math.sqrt(3), 1 / math.sqrt(3), 1 / math.sqrt(3),
)


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


class _StandardModel(_Model):
    def __init__(self, *, transposed=False):
        super().__init__(_ISOMETRIC_ROWS)
        self.standard = {
            1: (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
            5: (1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0),
            # Retain the native approximation, not a synthesized isometric.
            7: tuple(value + 1e-5 for value in _ISOMETRIC_ROWS),
        }
        if transposed:
            self.standard = {key: _transpose(value) for key, value in self.standard.items()}

    def GetStandardViewRotation(self, view_id):
        return self.standard[view_id]

    def ShowNamedView2(self, name, view_id):
        super().ShowNamedView2(name, view_id)
        self.ActiveView.Orientation3 = _Transform(self.standard[view_id])


@pytest.mark.parametrize("transposed", [False, True])
def test_named_standard_views_preserve_exact_native_projections(monkeypatch, transposed):
    import _assembly_named_views

    monkeypatch.setattr(_assembly_named_views, "_early_bound", lambda obj, _iface: obj)
    model = _StandardModel(transposed=transposed)
    standard = dict(model.standard)
    name_standard_views(
        _Adapter(model), views={"MG BACK": 1, "MG BACK-TOP-LEFT": 7}, label="test"
    )
    assert model.named["MG BACK"] == standard[1]
    assert model.named["MG BACK-TOP-LEFT"] == standard[7]
    assert model.standard == standard


@pytest.mark.parametrize("transposed", [False, True])
def test_named_standard_views_follow_an_arbitrary_rigid_turn(monkeypatch, transposed):
    import _assembly_named_views

    monkeypatch.setattr(_assembly_named_views, "_early_bound", lambda obj, _iface: obj)
    model = _StandardModel(transposed=transposed)
    turn = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))
    views = {"TURNED TOP": 5, "TURNED ISOMETRIC": 7}
    name_standard_views(
        _Adapter(model), views=views, label="test", model_rotation=turn
    )
    point = (31.0, 12.0, -7.0)
    turned = tuple(sum(point[i] * turn[i][j] for i in range(3)) for j in range(3))
    for name, view_id in views.items():
        original = model.standard[view_id]
        named = model.named[name]
        if transposed:
            original, named = _transpose(original), _transpose(named)
        before = tuple(sum(point[i] * original[3 * axis + i] for i in range(3)) for axis in range(3))
        after = tuple(sum(turned[i] * named[3 * axis + i] for i in range(3)) for axis in range(3))
        assert after == pytest.approx(before, abs=1e-12)
    # The physical working model still opens in its standard +Y-up frame.
    assert model.standard[1] == (
        1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0
    )


def test_named_standard_view_rejects_a_wrong_off_diagonal_readback(monkeypatch):
    import _assembly_named_views

    monkeypatch.setattr(_assembly_named_views, "_early_bound", lambda obj, _iface: obj)
    model = _StandardModel()
    model.Extension.GetNamedViewRotation = lambda name: _transpose(model.named[name])
    with pytest.raises(RuntimeError, match="read back"):
        name_standard_views(_Adapter(model), views={"MG BACK-TOP-LEFT": 7}, label="test")

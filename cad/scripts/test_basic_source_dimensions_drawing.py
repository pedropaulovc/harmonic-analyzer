"""Source BASIC metadata is a part write, never a drawing-side repair."""

from types import SimpleNamespace

import pytest

import _basic_dimensions as basic


class Dimension:
    SystemValue = 0.169

    def __init__(self):
        self.Tolerance = SimpleNamespace(Type=0)

    def GetToleranceType(self):
        return self.Tolerance.Type


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(basic, "_early_bound", lambda obj, kind: obj)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GetType=lambda: 1))
    dimensions = {"Shoulder": Dimension(), "Radius": Dimension()}
    monkeypatch.setattr(
        basic,
        "_named_dimension",
        lambda adapter, feature, name: (None, dimensions[name]),
    )
    return adapter, dimensions


def test_author_changes_only_type(setup):
    adapter, dimensions = setup
    basic.author_basic_dimensions(adapter, {"Profile": ("Shoulder", "Radius")})
    assert [d.Tolerance.Type for d in dimensions.values()] == [1, 1]
    assert [d.SystemValue for d in dimensions.values()] == [0.169, 0.169]


def test_missing_manifest_member_fails_before_first_write(setup):
    adapter, dimensions = setup
    with pytest.raises(KeyError):
        basic.author_basic_dimensions(adapter, {"Profile": ("Radius", "Missing")})
    assert all(d.Tolerance.Type == 0 for d in dimensions.values())


@pytest.mark.parametrize(
    "manifest",
    [
        {},
        {"": ("Radius",)},
        {"Profile": ()},
        {"Profile": ("Radius", "Radius")},
        {"Profile": ("",)},
    ],
)
def test_invalid_manifest_fails_without_writing(setup, manifest):
    adapter, dimensions = setup
    with pytest.raises(ValueError):
        basic.author_basic_dimensions(adapter, manifest)
    assert all(d.Tolerance.Type == 0 for d in dimensions.values())


def test_nonfinite_value_fails_without_writing(setup):
    adapter, dimensions = setup
    dimensions["Radius"].SystemValue = float("nan")
    with pytest.raises(RuntimeError, match="nonfinite"):
        basic.author_basic_dimensions(adapter, {"Profile": ("Radius",)})
    assert dimensions["Radius"].Tolerance.Type == 0


def test_drawing_cannot_author_source_metadata(setup):
    adapter, dimensions = setup
    adapter.currentModel.GetType = lambda: 3
    with pytest.raises(ValueError, match="in a part"):
        basic.author_basic_dimensions(adapter, {"Profile": ("Radius",)})
    assert dimensions["Radius"].Tolerance.Type == 0


def test_imported_check_is_read_only_and_rejects_stale_source(setup):
    _, dimensions = setup
    dimension = dimensions["Radius"]
    display = SimpleNamespace(GetDimension2=lambda configuration: dimension)
    with pytest.raises(RuntimeError, match="rebuild its source part"):
        basic.require_basic_dimension(display, label="Radius")
    assert dimension.Tolerance.Type == 0
    dimension.Tolerance.Type = 1
    basic.require_basic_dimension(display, label="Radius")

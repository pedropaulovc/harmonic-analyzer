"""Offline state-isolation contracts; no SolidWorks process is started."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _dimensions
import _supplier_spring_reference as refs


class _Body:
    def __init__(self, value, faces=7):
        self.value = value
        self.faces = faces

    def GetMassProperties(self, density):
        return (0.0, 0.0, 0.0, self.value, self.value * 2, self.value * density,
                self.value / 10, self.value / 10, self.value / 10, 0.0, 0.0, 0.0)

    def GetFaces(self):
        return [object()] * self.faces

    def Copy2(self, preserve_ids):
        return _Body(self.value, self.faces)

    def Select2(self, append, selection):
        return True


class _Display:
    def __init__(self, full_name, marked=True):
        self.dimension = SimpleNamespace(FullName=full_name)
        self.MarkedForDrawing = marked

    def GetDimension2(self, index):
        return self.dimension


class _Feature:
    def __init__(self, model, kind, body=None):
        self.model, self.kind, self.body = model, kind, body
        self.Name = f"Feature{len(model.features)}"
        self.suppressed = {name: False for name in model.configurations}
        self.Visible = 1
        self.displays = []
        self.refuses = False
        model.features.append(self)

    def SetSuppression2(self, state, option, names):
        if self.refuses:
            return False
        for name in names:
            self.suppressed[name] = state == 0
        return True

    def IsSuppressed2(self, option, names):
        return tuple(self.suppressed[name] for name in names)

    def GetTypeName2(self):
        return "ProfileFeature" if self.kind == "sketch" else "Imported"

    def GetFirstDisplayDimension(self):
        return self.displays[0] if self.displays else None

    def GetNextDisplayDimension(self, display):
        index = self.displays.index(display) + 1
        return self.displays[index] if index < len(self.displays) else None


class _Model:
    def __init__(self, title, bodies, active="Default"):
        self.title = title
        self.initial = bodies
        self.features = []
        self.active = active
        self.configurations = {name: SimpleNamespace(AddRebuildSaveMark=False)
                               for name in ("Default", "Default Simplified")}
        self.ConfigurationManager = self
        self.FeatureManager = self
        self.SelectionManager = SimpleNamespace(CreateSelectData=lambda: object())

    def GetTitle(self):
        return self.title

    def GetConfigurationNames(self):
        return tuple(self.configurations)

    def GetConfigurationByName(self, name):
        return self.configurations.get(name)

    def AddConfiguration2(self, name, comment, alternate, options, parent, description, rebuild):
        # Options without swConfigOption_DontActivate activate the new configuration.
        assert not options & 0x80
        self.configurations[name] = SimpleNamespace(AddRebuildSaveMark=False)
        self.active = name
        return self.configurations[name]

    def ShowConfiguration2(self, name):
        # Native SolidWorks refuses to show the already-active configuration.
        if name not in self.configurations or name == self.active:
            return False
        self.active = name
        return True

    def GetBodies2(self, kind, visible_only):
        solids, sheets = list(self.initial), []
        for feature in self.features:
            # A feature older than a configuration starts unsuppressed in it.
            if feature.suppressed.get(self.active, False):
                continue
            if feature.kind == "delete":
                solids.clear()
            elif feature.kind == "body":
                solids.append(feature.body)
            elif feature.kind == "sheet":
                sheets.append(feature.body)
        return {0: solids, 1: sheets}[kind]

    def GetFeatures(self, top_level_only):
        return tuple(self.features)

    def ClearSelection2(self, all):
        pass

    def InsertDeleteBody2(self, keep):
        return _Feature(self, "delete")

    def CreateFeatureFromBody3(self, body, make_surface, options):
        return _Feature(self, "body", body)

    def FeatureByName(self, name):
        return next((feature for feature in self.features if feature.Name == name), None)

    def EditRebuild3(self):
        return True


def _invoke(target, interface, member, *args):
    value = getattr(target, member)
    return value(*args) if callable(value) else value


def _adapter(monkeypatch, active="Default"):
    installed = _Model("Installed.sldprt", [_Body(1.0), _Body(0.2, 5)], active)
    adapter = SimpleNamespace(currentModel=installed)
    adapter.closed = []
    adapter.swApp = SimpleNamespace(
        CloseDoc=lambda name: adapter.closed.append(name),
        ActivateDoc3=lambda name, preferences, option, errors: (installed, 0),
        IsSame=lambda a, b: int(a is b),
    )
    adapter._reset_sketch_entity_registry = lambda: None

    async def create_part():
        adapter.currentModel = _Model("Transient.sldprt", [])
        return True

    adapter.create_part = create_part
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(refs, "_com_invoke", _invoke)
    monkeypatch.setattr(_dimensions, "_com_invoke", _invoke)
    monkeypatch.setattr(refs, "bstr_array", list)
    monkeypatch.setattr(refs, "check", lambda label, result: result)
    monkeypatch.setattr(refs, "active_configuration_name", lambda adapter, model=None: (model or adapter.currentModel).active)
    return adapter, installed


def _sketch(model, name, *, owner=None, marked=True, visible=1):
    """A native reference sketch owning one display dimension."""
    feature = _Feature(model, "sketch")
    feature.Name = name
    feature.Visible = visible
    feature.displays.append(_Display(f"D1@{owner or name}@{model.title}", marked))
    return feature


def _bodies_in(model, name, kind=0):
    model.active = name
    return model.GetBodies2(kind, False)


def _run(adapter, *states, body_count=2):
    asyncio.run(refs.add_supplier_reference_configurations(adapter, states, body_count=body_count))


def _diagram(references):
    return refs.ReferenceState(
        refs.SUPPLIER_DIAGRAM_CONFIGURATION, author=None, references=references,
        body_count=0, kind="diagram",
    )


async def _author(target):
    pass


async def _references(target):
    return ()


def test_source_counts_are_independent_and_installed_topology_survives(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    original = refs._signature(installed.GetBodies2(0, False))
    free_bodies = [_Body(0.8)]
    maximum_bodies = [_Body(1.1), _Body(0.2, 5)]

    async def free(target):
        target.currentModel.initial = free_bodies

    async def maximum(target):
        target.currentModel.initial = maximum_bodies

    async def sketch(target):
        return (_sketch(target.currentModel, "NativeSupplierReference").Name,)

    # Starts on the active installed configuration, which the fake (like
    # SolidWorks) refuses to re-show.
    _run(adapter,
         refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, free, sketch, body_count=1),
         refs.ReferenceState(refs.SUPPLIER_MAX_CONFIGURATION, maximum, body_count=2))
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    assert len(adapter.closed) == 2
    expected = {
        "Default": original,
        "Default Simplified": original,
        refs.SUPPLIER_FREE_CONFIGURATION: refs._signature(free_bodies),
        refs.SUPPLIER_MAX_CONFIGURATION: refs._signature(maximum_bodies),
    }
    for name, signature in expected.items():
        assert refs._signature(_bodies_in(installed, name)) == signature


def test_single_state_from_last_installed_configuration_needs_no_same_active_switch(monkeypatch):
    # AddConfiguration2 leaves the only new state active and the installed
    # configuration is the last original one read: both switches are no-ops.
    adapter, installed = _adapter(monkeypatch, active="Default Simplified")
    original = refs._signature(installed.GetBodies2(0, False))

    async def free(target):
        target.currentModel.initial = [_Body(0.8)]

    _run(adapter, refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, free, body_count=1))
    assert adapter.currentModel is installed
    assert installed.active == "Default Simplified"
    assert refs._signature(_bodies_in(installed, "Default")) == original
    assert refs._signature(_bodies_in(installed, refs.SUPPLIER_FREE_CONFIGURATION)) == (
        refs._signature([_Body(0.8)])
    )


def test_switch_that_does_not_take_effect_is_rejected(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    show = installed.ShowConfiguration2

    def ignores_simplified(name):
        return True if name == "Default Simplified" else show(name)

    monkeypatch.setattr(installed, "ShowConfiguration2", ignores_simplified)
    with pytest.raises(RuntimeError, match="'Default' is active"):
        _run(adapter, _diagram(_references))
    assert installed.active == "Default"
    assert set(installed.configurations) == {"Default", "Default Simplified"}


def test_diagram_state_authors_references_in_installed_part_without_bodies(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    original = refs._signature(installed.GetBodies2(0, False))

    async def no_scratch():
        raise AssertionError("diagram states must not create a scratch part")

    adapter.create_part = no_scratch
    seen = []

    async def references(target):
        seen.append((target.currentModel, target.currentModel.active,
                     len(target.currentModel.GetBodies2(0, False))))
        return tuple(_sketch(target.currentModel, name).Name
                     for name in ("DiscSupplierPlan", "DiscSupplierHeight"))

    _run(adapter, _diagram(references), body_count=2)
    # The callback ran in the installed part, in the diagram state, after the
    # installed bodies were removed there.
    assert seen == [(installed, refs.SUPPLIER_DIAGRAM_CONFIGURATION, 0)]
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    assert adapter.closed == []
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(installed, name)) == original
    assert _bodies_in(installed, refs.SUPPLIER_DIAGRAM_CONFIGURATION, 0) == []
    assert _bodies_in(installed, refs.SUPPLIER_DIAGRAM_CONFIGURATION, 1) == []
    assert installed.features, "diagram state added no feature"
    for feature in installed.features:
        assert feature.suppressed == {
            "Default": True, "Default Simplified": True,
            refs.SUPPLIER_DIAGRAM_CONFIGURATION: False,
        }, feature.Name


@pytest.mark.parametrize(("kind", "noun"), [("body", "solid"), ("sheet", "sheet")])
def test_diagram_rejects_any_body_left_in_its_state(monkeypatch, kind, noun):
    adapter, installed = _adapter(monkeypatch)
    original = refs._signature(installed.GetBodies2(0, False))

    async def references(target):
        _Feature(target.currentModel, kind, _Body(0.5))
        return (_sketch(target.currentModel, "DiscSupplierPlan").Name,)

    with pytest.raises(RuntimeError, match=f"holds 1 {noun} bodies") as raised:
        _run(adapter, _diagram(references))
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    # The unreported stray is suppressed in the originals on the failure path.
    _assert_originals_restored(installed, original, raised.value)


def _assert_originals_restored(installed, original, error):
    assert not getattr(error, "__notes__", ())
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(installed, name)) == original
        assert all(feature.suppressed[name] for feature in installed.features), name
    installed.active = "Default"


def test_partial_reference_failure_is_suppressed_in_original_configurations(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    original = refs._signature(installed.GetBodies2(0, False))

    async def references(target):
        _sketch(target.currentModel, "DiscSupplierPlan")
        _Feature(target.currentModel, "body", _Body(0.5))
        raise RuntimeError("reference callback failed")

    with pytest.raises(RuntimeError, match="reference callback failed") as raised:
        _run(adapter, _diagram(references))
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    assert len(installed.features) == 3  # Body-Delete, sketch, stray body
    _assert_originals_restored(installed, original, raised.value)


def test_unrestorable_original_is_reported_without_hiding_the_failure(monkeypatch):
    adapter, installed = _adapter(monkeypatch)

    async def references(target):
        _Feature(target.currentModel, "body", _Body(0.5)).refuses = True
        raise RuntimeError("reference callback failed")

    with pytest.raises(RuntimeError, match="reference callback failed") as raised:
        _run(adapter, _diagram(references))
    notes = " ".join(getattr(raised.value, "__notes__", ()))
    assert "original configurations not restored" in notes
    assert "cannot isolate supplier feature in Default" in notes
    assert "Default: 3 solid bodies, expected 2" in notes
    assert installed.active == "Default"


def _shown(model):
    return (_sketch(model, "Shown", visible=2).Name,)  # swVisibilityStateShown


def _unmarked(model):
    return (_sketch(model, "Unmarked", marked=False).Name,)


def _plane_dimension(model):
    # A sketch on a reference plane also enumerates the plane's offset dim.
    return (_sketch(model, "OnPlane", owner="SupplierPlane").Name,)


def _undimensioned(model):
    feature = _sketch(model, "Bare")
    feature.displays.clear()
    return (feature.Name,)


def _not_sketch(model):
    return (_Feature(model, "body", _Body(0.5)).Name,)


def _duplicate(model):
    name = _sketch(model, "Twice").Name
    return (name, name)


def _empty(model):
    return ()


@pytest.mark.parametrize(("author", "message"), [
    (_shown, "must be hidden"),
    (_unmarked, "no drawing-marked dimension"),
    (_plane_dimension, "no drawing-marked dimension"),
    (_undimensioned, "no drawing-marked dimension"),
    (_not_sketch, "is not a sketch"),
    (_duplicate, "distinct reference sketches"),
    (_empty, "distinct reference sketches"),
])
def test_diagram_requires_new_hidden_dimensioned_sketches(monkeypatch, author, message):
    adapter, installed = _adapter(monkeypatch)

    async def references(target):
        return author(target.currentModel)

    with pytest.raises(RuntimeError, match=message):
        _run(adapter, _diagram(references))
    assert adapter.currentModel is installed
    assert installed.active == "Default"


def test_diagram_cannot_claim_a_sketch_that_already_existed(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    _sketch(installed, "InstalledSketch")

    async def references(target):
        return ("InstalledSketch",)

    with pytest.raises(RuntimeError, match="predates the diagram state"):
        _run(adapter, _diagram(references))
    assert installed.active == "Default"


@pytest.mark.parametrize(("author", "references", "body_count", "kind"), [
    (None, _references, None, "diagram"),
    (None, None, 0, "diagram"),
    (None, _references, 1, "diagram"),
    (_author, _references, 0, "diagram"),
    (None, _references, 0, "body"),   # the diagram shape without its declared kind
    (None, None, None, "body"),
    (_author, None, 0, "body"),
    (_author, None, -1, "body"),
    (_author, "sketch", None, "body"),
    (_author, None, None, "sketch"),  # unknown kind, whatever the annotation says
])
def test_state_constructor_rejects_undeclared_or_mixed_states(author, references, body_count, kind):
    with pytest.raises(ValueError):
        refs.ReferenceState(refs.SUPPLIER_DIAGRAM_CONFIGURATION, author, references, body_count, kind)


def test_four_positional_fields_still_declare_a_body_state():
    assert refs.ReferenceState("Supplier-Free", _author, _references, 1).kind == "body"


def test_solid_author_that_builds_nothing_is_not_a_diagram(monkeypatch):
    adapter, installed = _adapter(monkeypatch)

    async def empty(target):
        pass

    with pytest.raises(RuntimeError, match="0 solid bodies, expected 2"):
        _run(adapter, refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, empty))
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    assert adapter.closed == ["Transient.sldprt"]
    assert installed.features == []


def test_author_failure_closes_only_scratch_and_restores_installed_state(monkeypatch):
    adapter, installed = _adapter(monkeypatch)

    async def fails(target):
        raise RuntimeError("source author failed")

    with pytest.raises(RuntimeError, match="source author failed"):
        _run(adapter, refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, fails))
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    assert adapter.closed == ["Transient.sldprt"]
    assert installed.features == []


def test_restoration_failure_does_not_hide_author_failure(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    adapter.swApp.ActivateDoc3 = lambda name, preferences, option, errors: (None, 1)

    async def fails(target):
        raise RuntimeError("source author failed")

    with pytest.raises(RuntimeError, match="source author failed") as raised:
        _run(adapter, refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, fails))
    assert any("cannot restore installed part document" in note
               for note in getattr(raised.value, "__notes__", ()))
    assert adapter.closed == ["Transient.sldprt"]
    assert installed.active == "Default"


def test_native_topology_readback_is_strict():
    expected = refs._signature([_Body(1.0, 7)])
    with pytest.raises(RuntimeError, match="topology changed"):
        refs._same_bodies([_Body(1.0, 8)], expected, label="supplier")
    with pytest.raises(RuntimeError, match="topology changed"):
        refs._same_bodies([_Body(1.01, 7)], expected, label="supplier")


def test_same_count_source_corruption_during_insertion_is_rejected(monkeypatch):
    adapter, installed = _adapter(monkeypatch)
    original = refs._signature(installed.GetBodies2(0, False))
    insert = installed.CreateFeatureFromBody3

    def corrupt_insert(body, make_surface, options):
        return insert(_Body(body.value * 2, body.faces), make_surface, options)

    async def source(target):
        target.currentModel.initial = [_Body(0.8)]

    monkeypatch.setattr(installed, "CreateFeatureFromBody3", corrupt_insert)
    with pytest.raises(RuntimeError, match="native bodies/topology changed"):
        _run(adapter, refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, source, body_count=1))
    assert adapter.currentModel is installed
    assert installed.active == "Default"
    assert refs._signature(_bodies_in(installed, "Default")) == original

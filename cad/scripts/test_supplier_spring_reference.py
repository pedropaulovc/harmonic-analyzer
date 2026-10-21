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
        self.construction = True
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

    def GetSpecificFeature2(self):
        return SimpleNamespace(GetSketchSegments=lambda: [
            SimpleNamespace(ConstructionGeometry=self.construction),
        ])

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
        solids = list(getattr(self, "initial_by_configuration", {}).get(self.active, self.initial))
        sheets = []
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


def test_diagram_state_preserves_every_original_body_and_configuration(monkeypatch):
    adapter, model = _adapter(monkeypatch, active="Default Simplified")
    original_feature = _Feature(model, "installed")
    original_feature.suppressed["Default Simplified"] = True
    original_matrix = dict(original_feature.suppressed)
    model.initial_by_configuration = {
        "Default": [_Body(1.0, 7), _Body(0.2, 5)],
        "Default Simplified": [_Body(1.7, 9), _Body(0.3, 6)],
    }
    original = {name: refs._signature(bodies)
                for name, bodies in model.initial_by_configuration.items()}

    async def references(target):
        assert target.currentModel is model
        assert model.GetBodies2(0, False) == []
        return (_sketch(model, "NominalSupplierGauge").Name,)

    _run(adapter, _diagram(references))
    assert adapter.currentModel is model
    assert model.active == "Default Simplified"
    assert adapter.closed == []
    assert original_feature.suppressed == original_matrix
    assert {"Default", "Default Simplified", refs.SUPPLIER_DIAGRAM_CONFIGURATION} <= set(model.configurations)
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(model, name)) == original[name]
        assert all(feature.suppressed[name] for feature in model.features if feature is not original_feature)
    for kind in (0, 1):
        assert _bodies_in(model, refs.SUPPLIER_DIAGRAM_CONFIGURATION, kind) == []


def test_two_diagrams_have_no_scratch_or_body_copy_path(monkeypatch):
    adapter, model = _adapter(monkeypatch)

    async def no_scratch():
        raise AssertionError("diagram must not create a scratch document")

    adapter.create_part = no_scratch

    async def free(target):
        return (_sketch(model, "FreeGauge").Name,)

    async def maximum(target):
        return (_sketch(model, "MaximumGauge").Name,)

    states = (
        refs.ReferenceState(refs.SUPPLIER_FREE_CONFIGURATION, None, free, 0, "diagram"),
        refs.ReferenceState(refs.SUPPLIER_MAX_CONFIGURATION, None, maximum, 0, "diagram"),
    )
    _run(adapter, *states)
    assert model.active == "Default"
    for state, owner in zip(states, ("FreeGauge", "MaximumGauge"), strict=True):
        assert _bodies_in(model, state.name) == []
        assert _bodies_in(model, state.name, 1) == []
        assert not model.FeatureByName(owner).suppressed[state.name]
    assert model.FeatureByName("FreeGauge").suppressed[states[1].name]
    assert model.FeatureByName("MaximumGauge").suppressed[states[0].name]


@pytest.mark.parametrize("corruption", ["shown", "unmarked", "wrong_owner", "continuous", "duplicate", "empty"])
def test_diagrams_require_new_hidden_construction_dimension_owners(monkeypatch, corruption):
    adapter, model = _adapter(monkeypatch)

    async def references(target):
        feature = _sketch(model, "SupplierGauge", owner="Other" if corruption == "wrong_owner" else None)
        if corruption == "shown":
            feature.Visible = 2
        elif corruption == "unmarked":
            feature.displays[0].MarkedForDrawing = False
        elif corruption == "continuous":
            feature.construction = False
        if corruption == "empty":
            return ()
        return (feature.Name, feature.Name) if corruption == "duplicate" else (feature.Name,)

    with pytest.raises(RuntimeError):
        _run(adapter, _diagram(references))
    assert model.active == "Default"
    assert all(feature.suppressed[name] for feature in model.features
               for name in ("Default", "Default Simplified"))


@pytest.mark.parametrize("kind", ["body", "sheet"])
def test_undeclared_physical_feature_is_rejected_and_originals_restored(monkeypatch, kind):
    adapter, model = _adapter(monkeypatch)
    original = refs._signature(model.GetBodies2(0, False))

    async def references(target):
        _Feature(model, kind, _Body(0.5))
        return (_sketch(model, "SupplierGauge").Name,)

    with pytest.raises(RuntimeError, match="undeclared diagram features"):
        _run(adapter, _diagram(references))
    assert model.active == "Default"
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(model, name)) == original
        assert _bodies_in(model, name, 1) == []


def test_partial_callback_failure_preserves_originals_and_active_configuration(monkeypatch):
    adapter, model = _adapter(monkeypatch)

    async def references(target):
        _sketch(model, "PartialGauge")
        _Feature(model, "body", _Body(0.5))
        raise RuntimeError("source reference failed")

    with pytest.raises(RuntimeError, match="source reference failed") as failure:
        _run(adapter, _diagram(references))
    assert not getattr(failure.value, "__notes__", ())
    assert model.active == "Default"
    assert all(feature.suppressed[name] for feature in model.features
               for name in ("Default", "Default Simplified"))


def test_original_suppression_corruption_is_detected_without_geometry_change(monkeypatch):
    adapter, model = _adapter(monkeypatch)
    original = _Feature(model, "installed")

    async def references(target):
        original.suppressed["Default"] = True
        return (_sketch(model, "SupplierGauge").Name,)

    with pytest.raises(RuntimeError, match="original feature suppression changed"):
        _run(adapter, _diagram(references))
    assert model.active == "Default"


def test_native_topology_signature_detects_same_count_geometry_change():
    expected = refs._signature([_Body(1.0, 7)])
    with pytest.raises(RuntimeError, match="topology changed"):
        refs._same_bodies([_Body(1.0, 8)], expected, label="installed")
    with pytest.raises(RuntimeError, match="topology changed"):
        refs._same_bodies([_Body(1.01, 7)], expected, label="installed")


@pytest.mark.parametrize("kind,noun", [(0, "solid"), (1, "sheet")])
def test_zero_body_proof_covers_solid_and_sheet_bodies(monkeypatch, kind, noun):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    model = SimpleNamespace(GetBodies2=lambda requested, visible: [object()] if requested == kind else [])
    with pytest.raises(RuntimeError, match=f"holds 1 {noun} bodies"):
        refs._require_bodiless(model, label="diagram")


@pytest.mark.parametrize("name", ["Default", "Default Simplified", "InnerLink", "Supplier-Free", ""])
def test_no_original_or_export_identity_can_be_used_as_a_supplier_state(name):
    with pytest.raises(ValueError):
        refs.ReferenceState(name, None, lambda target: None, 0, "diagram")


@pytest.mark.parametrize("author,count,kind", [(lambda target: None, 0, "diagram"), (None, 1, "diagram"),
                                               (lambda target: None, 1, "body")])
def test_solid_authors_and_mixed_states_are_not_supported(author, count, kind):
    with pytest.raises(ValueError):
        refs.ReferenceState(refs.SUPPLIER_DIAGRAM_CONFIGURATION, author, lambda target: None, count, kind)

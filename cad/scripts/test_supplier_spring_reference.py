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


def _adapter(monkeypatch, active="Default", *, model_type=_Model):
    installed = model_type("Installed.sldprt", [_Body(1.0), _Body(0.2, 5)], active)
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


class _MassBody(_Body):
    """Explicit native mass-property records, independent of body enumeration order."""

    def __init__(self, x=0.0, y=0.0, z=0.0, *, faces=7):
        super().__init__(1.0, faces)
        self.mass_properties = (x, y, z, 1.0, 2.0, 1.0, .1, .1, .1, 0.0, 0.0, 0.0)

    def GetMassProperties(self, density):
        assert density == 1.0
        return self.mass_properties


def test_signature_retains_native_body_order_without_float_lexicographic_sort(monkeypatch):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    bodies = [_MassBody(z=.002), _MassBody(z=-.002)]
    assert refs._signature(bodies) == [
        (body.faces, body.mass_properties) for body in bodies
    ]


def test_symmetric_plate_xy_noise_may_swap_lexsort_but_not_physical_z(monkeypatch):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    epsilon = 2e-14  # Opposite X/Y perturbations remain below the existing 1e-13 absolute band.
    expected = refs._signature([
        _MassBody(-epsilon, epsilon, -.002), _MassBody(epsilon, -epsilon, .002),
    ])
    observed = [
        _MassBody(epsilon, -epsilon, -.002), _MassBody(-epsilon, epsilon, .002),
    ]
    # Establish the old failure mechanism, without depending on the new matcher.
    assert sorted(expected)[0][1][2] == -.002
    assert sorted(refs._signature(observed))[0][1][2] == .002
    refs._same_bodies(observed, expected, label="symmetric installed plates")
    refs._same_bodies(list(reversed(observed)), expected, label="reordered installed plates")


@pytest.mark.parametrize("corruption", ["outside_tolerance", "topology", "count", "duplicate_substitution"])
def test_body_mismatch_keeps_complete_expected_and_observed_records(monkeypatch, corruption):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    lower, upper = _MassBody(z=-.002), _MassBody(z=.002)
    expected = refs._signature([lower, upper])
    actual = [lower, upper]
    if corruption == "outside_tolerance":
        actual[0] = _MassBody(x=2e-13, z=-.002)
    elif corruption == "topology":
        actual[0] = _MassBody(z=-.002, faces=8)
    elif corruption == "count":
        actual.pop()
    else:
        actual[1] = _MassBody(z=-.002)
    observed = refs._signature(actual)
    with pytest.raises(RuntimeError) as failure:
        refs._same_bodies(actual, expected, label="original member")
    diagnostic = str(failure.value)
    assert "original member" in diagnostic
    assert f"expected_records={expected!r}" in diagnostic
    assert f"observed_records={observed!r}" in diagnostic
    assert "candidate_expected_indices=" in diagnostic
    assert ("body count" if corruption == "count"
            else "no tolerance-preserving body bijection") in diagnostic


def test_body_matching_finds_global_bijection_instead_of_greedy_first_match(monkeypatch):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    # X fits A or B, while Y fits only A. Greedy X->A strands Y; X->B,Y->A is unique.
    expected = refs._signature([_MassBody(x=0.0), _MassBody(x=1.5e-13)])
    refs._same_bodies(
        [_MassBody(x=.75e-13), _MassBody(x=-.75e-13)],
        expected, label="global correspondence",
    )


def test_body_matching_rejects_ambiguous_non_equivalent_perfect_maps(monkeypatch):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    # Both observations fit both expectations, but A and B are not equivalent to one another.
    expected = refs._signature([_MassBody(x=0.0), _MassBody(x=1.5e-13)])
    observed = [_MassBody(x=.6e-13), _MassBody(x=.9e-13)]
    with pytest.raises(RuntimeError, match="ambiguous non-equivalent body correspondence") as failure:
        refs._same_bodies(observed, expected, label="ambiguous originals")
    assert f"expected_records={expected!r}" in str(failure.value)
    assert f"observed_records={refs._signature(observed)!r}" in str(failure.value)


def test_interchangeable_equivalent_duplicate_bodies_are_not_false_ambiguity(monkeypatch):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    expected = refs._signature([_MassBody(z=.002), _MassBody(z=.002)])
    refs._same_bodies(
        [_MassBody(x=2e-14, z=.002), _MassBody(x=-2e-14, z=.002)],
        expected, label="equivalent duplicate plates",
    )


class _FeatureProxy:
    """A native feature dispatch becomes disconnected on the next model transition."""

    def __init__(self, model, feature):
        object.__setattr__(self, "_model", model)
        object.__setattr__(self, "_feature", feature)
        object.__setattr__(self, "_generation", model.generation)

    def _live(self):
        model = object.__getattribute__(self, "_model")
        feature = object.__getattribute__(self, "_feature")
        generation = object.__getattribute__(self, "_generation")
        if generation != model.generation:
            model.stale_proxy_reads.append((feature.Name, generation, model.generation))
            raise RuntimeError(f"disconnected IFeature proxy: {feature.Name}")
        return feature

    def __getattr__(self, name):
        value = getattr(self._live(), name)
        if not callable(value):
            return value

        def invoke(*args, **kwargs):
            return getattr(self._live(), name)(*args, **kwargs)

        return invoke

    def __setattr__(self, name, value):
        setattr(self._live(), name, value)


class _ConfigurationMetadata(_Feature):
    """Configuration-created metadata is not a supplier-owned suppressible feature."""

    def __init__(self, model, name):
        super().__init__(model, "metadata")
        self.Name = name
        self.suppression_writes = []

    def GetTypeName2(self):
        return "CommentsFolder"

    def SetSuppression2(self, state, option, names):
        self.suppression_writes.append((state, option, tuple(names)))
        raise RuntimeError("configuration metadata cannot be suppressed")


class _ProxyModel(_Model):
    def __init__(self, title, bodies, active="Default"):
        super().__init__(title, bodies, active)
        self.generation = 0
        self.stale_proxy_reads = []
        self.events = []
        self.census_fails = False
        self.metadata_name = "Configuration Comments"
        self.metadata = None
        self.pending_body_refresh = {}

    def ShowConfiguration2(self, name):
        result = super().ShowConfiguration2(name)
        self.generation += 1
        self.events.append(("show", name))
        return result

    def AddConfiguration2(self, *args):
        result = super().AddConfiguration2(*args)
        self.generation += 1
        self.events.append(("add", args[0]))
        if self.metadata is None:
            self.metadata = _ConfigurationMetadata(self, self.metadata_name)
        return result

    def EditRebuild3(self):
        self.generation += 1
        self.events.append(("rebuild", self.active))
        if self.active in self.pending_body_refresh:
            self.initial_by_configuration[self.active] = self.pending_body_refresh.pop(self.active)
        return True

    def GetBodies2(self, kind, visible_only):
        self.events.append(("bodies", self.active, kind))
        return super().GetBodies2(kind, visible_only)

    def GetFeatures(self, top_level_only):
        if self.census_fails:
            raise RuntimeError("native feature census failed")
        return tuple(_FeatureProxy(self, feature) for feature in self.features)

    def FeatureByName(self, name):
        raw = super().FeatureByName(name)
        return None if raw is None else _FeatureProxy(self, raw)

    def InsertDeleteBody2(self, keep):
        return _FeatureProxy(self, super().InsertDeleteBody2(keep))


def _proxy_originals(model):
    first = _Feature(model, "installed")
    first.Name = "InstalledMemberA"
    second = _Feature(model, "installed")
    second.Name = "InstalledMemberB"
    first.suppressed["Default Simplified"] = True
    second.suppressed["Default"] = True
    return first, second


def test_configuration_proofs_reacquire_feature_proxies_after_each_transition(monkeypatch):
    adapter, model = _adapter(monkeypatch, active="Default Simplified", model_type=_ProxyModel)
    originals = _proxy_originals(model)
    suppression = {feature.Name: dict(feature.suppressed) for feature in originals}
    model.initial_by_configuration = {
        "Default": [_Body(1.0, 7), _Body(.2, 5)],
        "Default Simplified": [_Body(1.7, 9), _Body(.3, 6)],
    }
    signatures = {name: refs._signature(bodies)
                  for name, bodies in model.initial_by_configuration.items()}

    async def references(target):
        return (_sketch(model, "ProxySafeSupplierGauge").Name,)

    _run(adapter, _diagram(references))
    assert model.active == "Default Simplified"
    assert model.stale_proxy_reads == []
    assert model.metadata.suppression_writes == []
    for feature in originals:
        assert feature.suppressed == suppression[feature.Name]
    for name, expected in signatures.items():
        assert refs._signature(_bodies_in(model, name)) == expected


def test_original_mass_baselines_are_rebuilt_before_lazy_body_readback(monkeypatch):
    adapter, model = _adapter(monkeypatch, active="Default Simplified", model_type=_ProxyModel)
    _proxy_originals(model)
    stale = [_Body(.4, 7), _Body(.1, 5)]
    refreshed = {
        "Default": [_Body(1.0, 7), _Body(.2, 5)],
        "Default Simplified": [_Body(1.7, 9), _Body(.3, 6)],
    }
    model.initial_by_configuration = {name: list(stale) for name in refreshed}
    model.pending_body_refresh = {name: list(bodies) for name, bodies in refreshed.items()}

    async def references(target):
        return (_sketch(model, "RebuiltBaselineGauge").Name,)

    _run(adapter, _diagram(references))
    assert model.active == "Default Simplified"
    assert not model.pending_body_refresh
    for name, bodies in refreshed.items():
        first_mass_read = model.events.index(("bodies", name, 0))
        first_rebuild = model.events.index(("rebuild", name))
        assert first_rebuild < first_mass_read
        assert refs._signature(_bodies_in(model, name)) == refs._signature(bodies)
    assert model.stale_proxy_reads == []


@pytest.mark.parametrize("corruption", ["duplicate", "missing", "type"])
def test_original_feature_identity_is_not_replaced_by_a_name_collision(monkeypatch, corruption):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    original, _other = _proxy_originals(model)

    async def references(target):
        if corruption == "duplicate":
            duplicate = _Feature(model, "installed")
            duplicate.Name = original.Name
        elif corruption == "missing":
            model.features.remove(original)
        else:
            original.kind = "sketch"
        return (_sketch(model, "IdentityCheckedGauge").Name,)

    with pytest.raises(RuntimeError) as failure:
        _run(adapter, _diagram(references))
    message = str(failure.value)
    assert original.Name in message
    assert ("duplicate" if corruption == "duplicate" else "feature identity changed") in message
    assert model.active == "Default"
    assert model.metadata.suppression_writes == []


@pytest.mark.parametrize("metadata_name", ["Configuration Comments", "Native Auto Metadata"])
def test_partial_callback_cleanup_never_suppresses_configuration_created_metadata(monkeypatch, metadata_name):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    originals = _proxy_originals(model)
    original_matrix = {feature.Name: dict(feature.suppressed) for feature in originals}
    original_bodies = refs._signature(model.initial)
    model.metadata_name = metadata_name
    primary = RuntimeError("supplier callback failed after partial authoring")

    async def references(target):
        _sketch(model, "PartialProxyGauge")
        _Feature(model, "body", _Body(.5))
        raise primary

    with pytest.raises(RuntimeError) as failure:
        _run(adapter, _diagram(references))
    assert failure.value is primary
    assert not getattr(primary, "__notes__", ())
    assert model.active == "Default"
    assert model.metadata.suppression_writes == []
    assert model.stale_proxy_reads == []
    for feature in originals:
        assert feature.suppressed == original_matrix[feature.Name]
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(model, name)) == original_bodies
        assert all(feature.suppressed[name] for feature in model.features
                   if feature not in (*originals, model.metadata))


def test_undeclared_callback_body_cleanup_uses_owned_window_not_configuration_metadata(monkeypatch):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    _proxy_originals(model)
    initial = refs._signature(model.initial)

    async def references(target):
        _Feature(model, "sheet", _Body(.5))
        return (_sketch(model, "ReportedSupplierGauge").Name,)

    with pytest.raises(RuntimeError, match="undeclared diagram features"):
        _run(adapter, _diagram(references))
    assert model.active == "Default"
    assert model.metadata.suppression_writes == []
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(model, name)) == initial
        assert _bodies_in(model, name, 1) == []


def test_callback_exception_survives_failed_post_callback_feature_census(monkeypatch):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    _proxy_originals(model)
    primary = RuntimeError("original callback failure")

    async def references(target):
        _sketch(model, "UncensusedPartialGauge")
        model.census_fails = True
        raise primary

    with pytest.raises(RuntimeError) as failure:
        _run(adapter, _diagram(references))
    assert failure.value is primary
    assert "native feature census failed" in " ".join(getattr(primary, "__notes__", ()))
    assert model.active == "Default"
    assert model.metadata.suppression_writes == []


def test_callback_exception_survives_failed_owned_feature_cleanup(monkeypatch):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    _proxy_originals(model)
    primary = RuntimeError("original callback failure")

    async def references(target):
        _sketch(model, "RefusingPartialGauge").refuses = True
        raise primary

    with pytest.raises(RuntimeError) as failure:
        _run(adapter, _diagram(references))
    assert failure.value is primary
    assert "RefusingPartialGauge" in " ".join(getattr(primary, "__notes__", ()))
    assert model.active == "Default"
    assert model.metadata.suppression_writes == []


def test_original_suppression_read_failure_names_configuration_feature_and_type(monkeypatch):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    original, _other = _proxy_originals(model)
    read = original.IsSuppressed2

    def disconnected_in_second_original(option, names):
        if tuple(names) == ("Default Simplified",):
            raise RuntimeError("native suppression dispatch disconnected")
        return read(option, names)

    original.IsSuppressed2 = disconnected_in_second_original

    async def references(target):
        raise AssertionError("a failed original baseline must stop before supplier authoring")

    with pytest.raises(RuntimeError) as failure:
        _run(adapter, _diagram(references))
    diagnostic = str(failure.value)
    assert "suppression read failed" in diagnostic
    assert "Default Simplified" in diagnostic
    assert original.Name in diagnostic
    assert original.GetTypeName2() in diagnostic
    assert model.active == "Default"


def test_body_delete_is_owned_before_its_first_suppression_read_can_fail(monkeypatch):
    adapter, model = _adapter(monkeypatch, model_type=_ProxyModel)
    _proxy_originals(model)
    originals = refs._signature(model.initial)
    insert = model.InsertDeleteBody2
    failed_reads = []
    callbacks = []

    def insert_with_one_read_failure(keep):
        proxy = insert(keep)
        raw = model.features[-1]
        read = raw.IsSuppressed2

        def fail_once(option, names):
            if not failed_reads:
                failed_reads.append((raw.Name, tuple(names)))
                raise RuntimeError("native Body-Delete suppression read failed")
            return read(option, names)

        raw.IsSuppressed2 = fail_once
        return proxy

    monkeypatch.setattr(model, "InsertDeleteBody2", insert_with_one_read_failure)

    async def references(target):
        callbacks.append(target)
        return (_sketch(model, "NeverReachedGauge").Name,)

    with pytest.raises(RuntimeError):
        _run(adapter, _diagram(references))
    assert failed_reads
    assert not callbacks
    assert model.active == "Default"
    assert model.metadata.suppression_writes == []
    for name in ("Default", "Default Simplified"):
        assert refs._signature(_bodies_in(model, name)) == originals


def test_nontransitive_tolerance_compares_all_feasible_candidates_not_only_baseline(monkeypatch):
    monkeypatch.setattr(refs, "_early_bound", lambda value, interface: value)
    # Put the midpoint first so the real matcher naturally selects it for row 0.
    # Midpoint~A and midpoint~C, but A!~C: tolerance equivalence is not transitive.
    expected = refs._signature([
        _MassBody(x=.75e-13), _MassBody(x=0.0), _MassBody(x=1.5e-13),
    ])
    observed = [
        _MassBody(x=.75e-13), _MassBody(x=0.0), _MassBody(x=1.5e-13),
    ]
    candidates = ((0, 1, 2), (0, 1), (0, 2))
    baseline = refs._body_bijection(candidates)
    assert baseline == (0, 1, 2)
    # Establish why a comparison against only the chosen baseline would accept.
    for row, matched in enumerate(baseline):
        assert all(
            refs._same_signature(expected[matched], expected[alternative])
            for alternative in candidates[row]
        )
    assert not refs._same_signature(expected[1], expected[2])
    assert refs._body_bijection(candidates, fixed=(0, 1)) is not None
    assert refs._body_bijection(candidates, fixed=(0, 2)) is not None
    with pytest.raises(RuntimeError, match="ambiguous non-equivalent body correspondence"):
        refs._same_bodies(observed, expected, label="nontransitive tolerance alternatives")


class _RenameFaultBodyDelete(_Feature):
    """One recoverable native Name failure, confined to an inserted Body-Delete."""

    def __init__(self, model, mode, primary):
        self._native_name = ""
        self._rename_fault_armed = False
        self._read_fault_pending = False
        self.mode = mode
        self.primary = primary
        self.rename_targets = []
        self.failed_name_reads = 0
        self.names_committed_before_failed_reads = []
        super().__init__(model, "delete")
        self.initial_name = self.Name
        self._rename_fault_armed = True

    @property
    def Name(self):
        if self._read_fault_pending:
            self._read_fault_pending = False
            self.failed_name_reads += 1
            self.names_committed_before_failed_reads.append(self._native_name)
            raise self.primary
        return self._native_name

    @Name.setter
    def Name(self, value):
        if not self._rename_fault_armed:
            self._native_name = value
            return
        self._rename_fault_armed = False
        self.rename_targets.append(value)
        if self.mode == "setter_refuses":
            return
        self._native_name = value
        if self.mode == "setter_raises_after_rename":
            raise self.primary
        self._read_fault_pending = True


@pytest.mark.parametrize(
    "mode", ["read_fails_after_rename", "setter_refuses", "setter_raises_after_rename"],
)
def test_body_delete_rename_fault_recovers_owned_identity_and_every_original(monkeypatch, mode):
    adapter, model = _adapter(monkeypatch, active="Default Simplified", model_type=_ProxyModel)
    originals = _proxy_originals(model)
    original_suppression = {feature.Name: dict(feature.suppressed) for feature in originals}
    model.initial_by_configuration = {
        "Default": [_Body(1.0, 7), _Body(.2, 5)],
        "Default Simplified": [_Body(1.7, 9), _Body(.3, 6)],
    }
    original_signatures = {
        name: refs._signature(bodies) for name, bodies in model.initial_by_configuration.items()
    }
    primary = RuntimeError(f"native Body-Delete Name fault: {mode}")
    inserted = []
    callbacks = []

    def insert_with_name_fault(keep):
        assert keep is False
        raw = _RenameFaultBodyDelete(model, mode, primary)
        inserted.append(raw)
        return _FeatureProxy(model, raw)

    monkeypatch.setattr(model, "InsertDeleteBody2", insert_with_name_fault)

    async def references(target):
        callbacks.append(target)
        return (_sketch(model, "NeverReachedRenameGauge").Name,)

    with pytest.raises(RuntimeError) as failure:
        _run(adapter, _diagram(references))
    assert len(inserted) == 1
    removed, = inserted
    assert removed.rename_targets == [f"{refs.SUPPLIER_DIAGRAM_CONFIGURATION}-RemoveInstalled"]
    if mode == "setter_refuses":
        assert removed.Name == removed.initial_name
        assert "rename" in str(failure.value).lower()
    else:
        assert failure.value is primary
        assert removed.Name == removed.rename_targets[0]
    assert removed.failed_name_reads == int(mode == "read_fails_after_rename")
    assert removed.names_committed_before_failed_reads == (
        removed.rename_targets if mode == "read_fails_after_rename" else []
    )
    assert removed._read_fault_pending is False
    assert not getattr(failure.value, "__notes__", ())
    assert not callbacks
    assert model.active == "Default Simplified"
    assert model.stale_proxy_reads == []
    assert model.metadata.suppression_writes == []
    for feature in originals:
        assert feature.suppressed == original_suppression[feature.Name]
    for name, signature in original_signatures.items():
        assert removed.suppressed[name] is True
        assert refs._signature(_bodies_in(model, name)) == signature
        assert _bodies_in(model, name, 1) == []

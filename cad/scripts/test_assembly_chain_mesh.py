"""Synthetic contracts for the generic mounted-chain interference pipeline.

These observations exercise check_no_interference, not a native SolidWorks seat.
The fake preserves the audited method/property shapes: GetTotalTransform(False)
is a method returning a nullable transform; ArrayData, Name2, configuration,
Components and Volume are properties. No fake result is native pose evidence.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

import _assembly
import _chain
import pd_transgear_removable_spec as removable
from _chain_mounts import mounted_wheels


def _check(adapter, **kwargs):
    """The gate as the chain-carrying assemblies call it: with the mounts read now."""
    return _assembly.check_no_interference(adapter, chain_mounts=mounted_wheels(), **kwargs)


class _MathTransform:
    def __init__(self, values) -> None:
        self._values = values
        self.reads = 0

    @property
    def ArrayData(self):
        self.reads += 1
        return self._values


class _Component:
    def __init__(
        self,
        name: str,
        configuration: str = "",
        *,
        total=None,
        relative=None,
        error: Exception | None = None,
    ) -> None:
        self._name = name
        self._configuration = configuration
        self.total = total
        self.relative = relative
        self.error = error
        self.total_requests: list[bool] = []
        self.relative_reads = 0

    @property
    def Name2(self) -> str:
        return self._name

    @property
    def ReferencedConfiguration(self) -> str:
        return self._configuration

    def GetTotalTransform(self, include_presentation: bool):
        assert include_presentation is False
        self.total_requests.append(include_presentation)
        if self.error is not None:
            raise self.error
        return self.total

    @property
    def Transform2(self):
        # A purported parent-relative answer must never substitute for the
        # active-root dispatch's unavailable or displaced total transform.
        self.relative_reads += 1
        return self.relative


class _Interference:
    def __init__(self, components, volume_mm3: float = 0.4) -> None:
        self._components = list(components)
        self._volume = volume_mm3 / 1e9

    @property
    def Components(self):
        return self._components

    @property
    def Volume(self) -> float:
        return self._volume


class _Manager:
    def __init__(self, interferences) -> None:
        self.interferences = list(interferences)
        self.computations = 0
        self.releases = 0

    def GetInterferences(self):
        self.computations += 1
        return self.interferences

    def Done(self) -> None:
        self.releases += 1


class _Assembly:
    def __init__(self, interferences) -> None:
        self.manager = _Manager(interferences)
        self.tool_checks = 0

    @property
    def InterferenceDetectionManager(self):
        return self.manager

    def ToolsCheckInterference(self) -> None:
        self.tool_checks += 1


class _Adapter:
    def __init__(self, *interferences: _Interference) -> None:
        self.currentModel = _Assembly(interferences)

    @staticmethod
    def _attempt(action, *, default=None):
        try:
            return action()
        except Exception:
            return default


class _Span:
    def __init__(self) -> None:
        self.attributes = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        pass

    def set_attribute(self, key, value) -> None:
        self.attributes[key] = value


@pytest.fixture
def observations(monkeypatch):
    result = SimpleNamespace(events=[], spans={}, bindings=[], debug=[])

    def bind(obj, interface):
        result.bindings.append((obj, interface))
        return obj

    def span(name):
        value = _Span()
        result.spans[name] = value
        return value

    monkeypatch.setattr(_assembly, "_early_bound", bind)
    monkeypatch.setattr(_assembly._telemetry, "span", span)
    monkeypatch.setattr(
        _assembly._telemetry,
        "event",
        lambda name, **attrs: result.events.append((name, attrs)),
    )
    monkeypatch.setattr(_assembly._telemetry, "debug", result.debug.append)
    return result


def _mount_values(role: str, *, angle: float = 0.0) -> list[float]:
    centre = {"crank": _chain.CRANK_CENTRE, "knob": _chain.KNOB_CENTRE}[role]
    c, s = math.cos(angle), math.sin(angle)
    return [
        c, s, 0.0,
        -s, c, 0.0,
        0.0, 0.0, 1.0,
        -centre[0] / 1000.0,
        centre[1] / 1000.0,
        removable.BAND_FRONT_Z / 1000.0,
        1.0, 0.0, 0.0, 0.0,
    ]


def _wheel(role: str, *, name: str = "pd-transgear-removable-17", values=None):
    configuration = {"crank": removable.CRANK_CONFIG, "knob": removable.KNOB_CONFIG}[role]
    return _Component(
        name,
        configuration,
        total=_MathTransform(_mount_values(role) if values is None else values),
    )


def _link(name: str = "vn-chain-inner-link-8") -> _Component:
    return _Component(name)


def _mesh_adapter(wheel, *, link=None, volume_mm3: float = 0.4) -> _Adapter:
    return _Adapter(_Interference([_link() if link is None else link, wheel], volume_mm3))


@pytest.mark.parametrize("role", ["crank", "knob"])
@pytest.mark.parametrize(
    ("crank_config", "knob_config"),
    [
        ("T12", "T24"),
        ("T18", "T24"),
        ("T12", "T18"),
        ("T18", "T18"),
        ("T12", "T12"),
        ("T24", "T24"),
    ],
)
@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("reverse_pair", [False, True])
def test_selected_mounts_allow_mesh_without_a_configuration_whitelist(
    monkeypatch, observations, role, crank_config, knob_config, nested, reverse_pair
) -> None:
    monkeypatch.setattr(removable, "CRANK_CONFIG", crank_config)
    monkeypatch.setattr(removable, "KNOB_CONFIG", knob_config)
    prefix = "pd-paper-drive-1/" if nested else ""
    # Suffix 17 proves that insertion order is not mistaken for role evidence.
    wheel = _wheel(
        role,
        name=f"{prefix}pd-transgear-removable-17",
        values=_mount_values(role, angle=0.37),
    )
    link = _link(f"{prefix}vn-chain-outer-link-9")
    # Keep the existing unbounded chain-mesh volume protocol unchanged.
    components = [wheel, link] if reverse_pair else [link, wheel]
    adapter = _Adapter(_Interference(components, volume_mm3=1000.0))
    _check(adapter)

    assert wheel.total_requests == [False]
    assert wheel.relative_reads == 0
    assert wheel.total.reads == 1
    assert (wheel, "IComponent2") in observations.bindings
    assert (wheel.total, "IMathTransform") in observations.bindings
    assert observations.spans["gate.interference"].attributes == {
        "hits": 0,
        "bounded_contacts": 0,
        "chain_contacts": 0,
        "chain_mesh_contacts": 1,
    }
    assert not observations.events
    assert adapter.currentModel.tool_checks == 1
    manager = adapter.currentModel.manager
    assert manager.computations == manager.releases == 1
    assert manager.UseTransform is False
    assert manager.TreatSubAssembliesAsComponents is True


@pytest.mark.parametrize("role", ["crank", "knob"])
@pytest.mark.parametrize("equal_config", ["T12", "T18", "T24"])
def test_stored_spare_with_the_active_configuration_remains_a_clash(
    monkeypatch, observations, role, equal_config
) -> None:
    monkeypatch.setattr(removable, "CRANK_CONFIG", equal_config)
    monkeypatch.setattr(removable, "KNOB_CONFIG", equal_config)
    # Synthetic stored-spare observation: off the mounted axes/band, Rx(-90).
    stored = [
        1.0, 0.0, 0.0,
        0.0, 0.0, -1.0,
        0.0, 1.0, 0.0,
        0.160, 0.0, -0.075,
        1.0, 0.0, 0.0, 0.0,
    ]
    mounted = _wheel(role)
    spare = _wheel(role, name="pd-transgear-removable-3", values=stored)
    adapter = _Adapter(
        _Interference([_link(), mounted]),
        _Interference([_link(), spare]),
    )
    with pytest.raises(RuntimeError, match="pd-transgear-removable-3"):
        _check(adapter)
    assert observations.spans["gate.interference"].attributes["chain_mesh_contacts"] == 1
    assert observations.spans["gate.interference"].attributes["hits"] == 1
    assert observations.events[0][1]["configurations"] == ["", equal_config]
    assert adapter.currentModel.manager.releases == 1


@pytest.mark.parametrize("role", ["crank", "knob"])
def test_role_selection_mismatch_is_not_intended_mesh(observations, role) -> None:
    wheel = _wheel(role)
    wheel._configuration = (
        removable.KNOB_CONFIG if role == "crank" else removable.CRANK_CONFIG
    )
    with pytest.raises(RuntimeError, match="pd-transgear-removable-17"):
        _check(_mesh_adapter(wheel))
    assert observations.spans["gate.interference"].attributes["chain_mesh_contacts"] == 0


@pytest.mark.parametrize("configuration", ["", "T18 ", "t18", "T018", "T99"])
def test_unregistered_selection_cannot_qualify_even_at_the_mount(
    monkeypatch, observations, configuration
) -> None:
    monkeypatch.setattr(removable, "CRANK_CONFIG", configuration)
    wheel = _wheel("crank")
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(wheel))
    assert wheel.total_requests == []


@pytest.mark.parametrize(
    ("wheel_name", "link_name"),
    [
        ("pd-transgear-removable-copy-2", "vn-chain-inner-link-1"),
        ("pd-transgear-removablex-2", "vn-chain-inner-link-1"),
        ("pd-transgear-removable-2/ordinary-part-1", "vn-chain-inner-link-1"),
        ("pd-transgear-removable-2", "vn-chain-inner-linkage-1"),
        ("pd-transgear-removable-2", "vn-chain-inner-link-copy-1"),
        ("pd-transgear-removable-2", "vn-chain-inner-link-1/ordinary-part-1"),
        ("pd-transgear-removable", "vn-chain-inner-link-1"),
        ("pd-transgear-removable-0", "vn-chain-inner-link-1"),
    ],
)
def test_prefix_false_friends_are_not_chain_mesh(observations, wheel_name, link_name):
    wheel = _wheel("crank", name=wheel_name)
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(wheel, link=_link(link_name)))
    assert wheel.total_requests == []


@pytest.mark.parametrize(
    ("index", "value"),
    [
        (0, math.nan),
        (9, math.nan),
        (10, math.inf),
        (11, -math.inf),
        (12, math.nan),
        (15, math.nan),
        (0, "not a double"),
        (12, 0.0),
        (12, 2.0),
        (0, 2.0),
        (0, -1.0),
        (1, 0.1),
        (8, 0.0),
    ],
)
def test_nonfinite_or_nonrigid_transform_is_never_allowed(observations, index, value):
    values = _mount_values("crank")
    values[index] = value
    wheel = _wheel("crank", values=values)
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(wheel))
    assert wheel.relative_reads == 0


@pytest.mark.parametrize("array_data", [None, 1.0, [], [1.0] * 12, [1.0] * 17])
def test_malformed_array_data_is_never_allowed(observations, array_data) -> None:
    wheel = _wheel("crank")
    wheel.total = _MathTransform(array_data)
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(wheel))


@pytest.mark.parametrize("failure", ["null", "exception", "no-method", "no-array"])
def test_unavailable_pose_has_no_relative_or_identity_fallback(observations, failure):
    mounted = _MathTransform(_mount_values("crank"))
    wheel = _Component(
        "pd-transgear-removable-2",
        removable.CRANK_CONFIG,
        total=None,
        relative=mounted,
    )
    if failure == "exception":
        wheel.error = RuntimeError("unavailable transform")
    elif failure == "no-array":
        wheel.total = SimpleNamespace()
    elif failure == "no-method":
        wheel = SimpleNamespace(
            Name2=wheel.Name2,
            ReferencedConfiguration=wheel.ReferencedConfiguration,
            Transform2=mounted,
        )
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(wheel))
    assert mounted.reads == 0
    if isinstance(wheel, _Component):
        assert wheel.relative_reads == 0


@pytest.mark.parametrize("change", ["x", "y", "front", "tilt", "reversal"])
def test_right_family_and_configuration_still_require_the_physical_mount(
    observations, change
) -> None:
    values = _mount_values("knob")
    if change in {"x", "y", "front"}:
        values[{"x": 9, "y": 10, "front": 11}[change]] += 0.001
    elif change == "tilt":
        values[:9] = [1.0, 0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 1.0, 0.0]
    else:
        # A rigid flipped plate does not have the authored front origin/+Z band.
        values[:9] = [1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, -1.0]
        values[11] = removable.SEAT_FACE_Z / 1000.0
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(_wheel("knob", values=values)))


def test_readback_tolerance_is_small_and_not_a_manufacturing_grade(observations):
    assert _assembly._CHAIN_MOUNT_READBACK_MM == 1e-5
    assert _assembly._CHAIN_MOUNT_READBACK_UNIT == 1e-8
    nominal = _mount_values("crank")
    near = nominal.copy()
    near[9] += _assembly._CHAIN_MOUNT_READBACK_MM * 0.5 / 1000.0
    _check(_mesh_adapter(_wheel("crank", values=near)))
    outside = nominal.copy()
    outside[9] += _assembly._CHAIN_MOUNT_READBACK_MM * 2.0 / 1000.0
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(_wheel("crank", values=outside)))


@pytest.mark.parametrize("world_is_mounted", [True, False])
def test_nested_pose_uses_active_root_without_fallback_or_double_composition(
    observations, world_is_mounted
) -> None:
    mounted = _mount_values("crank")
    displaced = mounted.copy()
    displaced[9] += 0.050
    wheel = _wheel(
        "crank",
        name="pd-paper-drive-1/pd-transgear-removable-2",
        values=mounted if world_is_mounted else displaced,
    )
    # Stand-in for a different parent frame, not another native getter claim.
    # Correct world data must not be composed again; an actually displaced PD
    # must not qualify just because its purported parent-relative mount agrees.
    wheel.relative = _MathTransform(displaced if world_is_mounted else mounted)
    adapter = _mesh_adapter(wheel, link=_link("pd-paper-drive-1/vn-chain-inner-link-1"))
    if world_is_mounted:
        _check(adapter)
    else:
        with pytest.raises(RuntimeError, match="pd-paper-drive-1/pd-transgear-removable-2"):
            _check(adapter)
    assert wheel.total_requests == [False]
    assert wheel.relative_reads == wheel.relative.reads == 0


@pytest.mark.parametrize("role", ["crank", "knob"])
def test_mounts_follow_shared_centre_band_and_selection_cells_lazily(
    monkeypatch, observations, role
) -> None:
    old_wheel = _wheel(role)
    centre_key = "CRANK_CENTRE" if role == "crank" else "KNOB_CENTRE"
    selection_key = "CRANK_CONFIG" if role == "crank" else "KNOB_CONFIG"
    old_centre = getattr(_chain, centre_key)
    monkeypatch.setattr(
        _chain, centre_key, (old_centre[0] + 2.0, old_centre[1] + 3.0)
    )
    monkeypatch.setattr(removable, selection_key, "T18")
    monkeypatch.setattr(removable, "BAND_FRONT_Z", removable.BAND_FRONT_Z - 1.0)
    monkeypatch.setattr(removable, "SEAT_FACE_Z", removable.SEAT_FACE_Z - 1.0)

    _check(_mesh_adapter(_wheel(role)))
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(old_wheel))


@pytest.mark.parametrize("equal_configs", [False, True])
def test_simultaneous_role_readback_windows_are_ambiguous(
    monkeypatch, observations, equal_configs
) -> None:
    crank = _chain.CRANK_CENTRE
    # Bounded synthetic source perturbation, rather than invoking the solver
    # at degenerate coincident centres: both role windows contain this mount.
    monkeypatch.setattr(
        _chain,
        "KNOB_CENTRE",
        (crank[0] + _assembly._CHAIN_MOUNT_READBACK_MM * 0.5, crank[1]),
    )
    if equal_configs:
        monkeypatch.setattr(removable, "KNOB_CONFIG", removable.CRANK_CONFIG)
    with pytest.raises(RuntimeError, match="interference"):
        _check(_mesh_adapter(_wheel("crank")))


@pytest.mark.parametrize("shape", ["three-components", "two-wheels", "one-wheel"])
def test_only_a_two_component_link_wheel_pair_can_be_mesh(observations, shape):
    wheel = _wheel("crank")
    components = {
        "three-components": [_link(), wheel, _Component("ordinary-part-1")],
        "two-wheels": [wheel, _wheel("knob")],
        "one-wheel": [wheel],
    }[shape]
    with pytest.raises(RuntimeError, match="interference"):
        _check(_Adapter(_Interference(components)))
    assert wheel.total_requests == []


@pytest.mark.parametrize("pair_total", [0.6, 1.2])
def test_link_contacts_and_allowed_pairs_keep_their_aggregate_behavior(
    observations, pair_total
) -> None:
    pair = (_Component("fit-hub-1"), _Component("fit-shaft-1"))
    names = [component.Name2 for component in pair]
    limit = {frozenset(names): 1.0}
    adapter = _Adapter(
        _Interference([_link(), _link("vn-chain-outer-link-2")], 20.0),
        _Interference([_link(), _wheel("crank")], 0.5),
        _Interference(pair, pair_total / 2.0),
        _Interference(tuple(reversed(pair)), pair_total / 2.0),
    )
    if pair_total > 1.0:
        with pytest.raises(RuntimeError, match=r"1.2 mm\^3 over 2 bodies"):
            _check(adapter, allowed_pairs=limit)
    else:
        _check(adapter, allowed_pairs=limit)
        [(name, attrs)] = observations.events
        assert name == "interference.bounded_pair"
        assert attrs["pair"] == names
        assert attrs["overlap_mm3"] == pytest.approx(pair_total)
        assert attrs["body_count"] == 2
    attributes = observations.spans["gate.interference"].attributes
    assert attributes["chain_contacts"] == 1
    assert attributes["chain_mesh_contacts"] == 1
    assert attributes["bounded_contacts"] == (1 if pair_total < 1.0 else 0)
    assert adapter.currentModel.manager.releases == 1


def test_soundness_interference_gates_get_the_chain_mounts(monkeypatch) -> None:
    """PD run 10: verify_soundness:pd_paper_drive read 34 link-on-sprocket mesh
    contacts as interference because verify.py's soundness gates never passed
    the mounts the assembly builds pass (541011de0)."""
    import inspect

    import verify

    seen: dict[str, object] = {}

    def fake_check(_adapter, *, allowed_pairs, chain_mounts=None):
        seen["mounts"] = chain_mounts

    class _Report:
        def __init__(self) -> None:
            self.gates: dict[str, object] = {}

        def gate(self, label, fn) -> None:
            self.gates[label] = fn

    monkeypatch.setattr(verify, "check_no_interference", fake_check)
    monkeypatch.setattr(verify, "_expected_free_dof", lambda _name: None)
    for name, expected in (
        ("pd-paper-drive", mounted_wheels()),
        ("ha-harmonic-analyzer", mounted_wheels()),
        ("ch-channel", None),
    ):
        report = _Report()
        verify._run_soundness_battery(object(), name, report, rebuilt=None)
        report.gates[f"{name}:interference-free"]()
        assert seen.pop("mounts") == expected
    # The static suite's own copy of the gate passes the same mounts.
    assert "chain_mounts=_soundness_chain_mounts(name)" in inspect.getsource(
        verify._verify_static_one
    )

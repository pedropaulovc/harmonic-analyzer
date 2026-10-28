"""Offline regressions for reopened shared-member consumers, not native proof."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _component_references as references
import verify


def _component(role, ordinal, *, scope="", index=91, configuration=None, stem=None):
    # Independent native fixtures: never generate observed identity from the
    # production selector table that the consumer is responsible for checking.
    if role in {"InnerLink", "OuterLink"}:
        native_stem, member = "sh-vn-chain-link", role
    elif role in {"LeverWire", "PenWire"}:
        native_stem, member = "sh-vn-music-wire", role
    elif role in {"HoldDownStud", "TNut", "FlangeNut"}:
        native_stem, member = "sh-vn-clamping-kit-hardware", role
    elif role in {"FootScrew", "SwingStopScrew"}:
        native_stem, member = "sh-vn-fillister-screw-90280a108", "Default"
    else:
        raise ValueError(f"unknown fixture role: {role}")
    prefix = f"{scope}/" if scope else ""
    return SimpleNamespace(
        Name2=f"{prefix}renamed-native-occurrence-{index}",
        ComponentReference=f"{role}:{ordinal}",
        ReferencedConfiguration=member if configuration is None else configuration,
        GetPathName=lambda: f"C:/native/{native_stem if stem is None else stem}.SLDPRT",
    )


def _adapter(components):
    def get_components(top_level):
        assert top_level is False
        return components

    return SimpleNamespace(currentModel=SimpleNamespace(GetComponents=get_components))


@pytest.fixture
def native_bindings(monkeypatch):
    monkeypatch.setattr(verify, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(references, "_early_bound", lambda obj, _interface: obj)


def _inventory(name):
    # Installed acceptance quantities, independent of the production census.
    counts = {
        "pd-paper-drive": {"InnerLink": 33, "OuterLink": 32},
        "ch-rocker-arm-tl-oblique-jig": {"HoldDownStud": 4, "TNut": 4, "FlangeNut": 4},
        "dt-drive-train": {"FootScrew": 1, "SwingStopScrew": 1},
        "mg-magnifier": {"LeverWire": 1},
        "pn-pen": {"PenWire": 1},
    }
    if name == "ha-harmonic-analyzer":
        components = []
        for child in ("dt-drive-train", "pd-paper-drive", "mg-magnifier", "pn-pen"):
            for component in _inventory(child):
                component.Name2 = f"{child}-1/{component.Name2}"
                components.append(component)
        return components
    return [
        _component(role, number, index=1000 + group * 100 + number)
        for group, (role, count) in enumerate(counts[name].items())
        for number in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    "name",
    [
        "pd-paper-drive",
        "ch-rocker-arm-tl-oblique-jig",
        "dt-drive-train",
        "mg-magnifier",
        "pn-pen",
        "ha-harmonic-analyzer",
    ],
)
def test_reopened_reference_census_uses_native_readback_not_name_indices(
    native_bindings, name
):
    components = _inventory(name)
    for component in components:
        component.ReferencedConfiguration += " Simplified"
    verify._assert_shared_component_references(_adapter(components), name)


@pytest.mark.parametrize(
    "corruption",
    [
        "missing",
        "duplicate",
        "wrong-member",
        "missing-member",
        "decorated-member",
        "wrong-file",
        "extra",
        "extra-no-reference",
        "wrong-scope",
    ],
)
def test_reopened_member_census_rejects_identity_or_quantity_drift(
    native_bindings, corruption
):
    components = _inventory("mg-magnifier")
    if corruption == "missing":
        components.clear()
    elif corruption == "duplicate":
        components.append(_component("LeverWire", 1, index=907))
    elif corruption == "wrong-member":
        components[0].ReferencedConfiguration = "PenWire"
    elif corruption == "missing-member":
        components[0].ReferencedConfiguration = ""
    elif corruption == "decorated-member":
        components[0].ReferencedConfiguration = "LeverWire Simplified extra"
    elif corruption == "wrong-file":
        components[0].GetPathName = lambda: "C:/native/false-friend.SLDPRT"
    elif corruption == "extra":
        components.append(_component("LeverWire", 2, index=908))
    elif corruption == "extra-no-reference":
        extra = _component("LeverWire", 2, index=908)
        extra.ComponentReference = ""
        components.append(extra)
    else:
        components[0].Name2 = "other-parent-1/renamed-native-occurrence-999"
    with pytest.raises(RuntimeError):
        verify._assert_shared_component_references(_adapter(components), "mg-magnifier")


@pytest.mark.parametrize(
    ("name", "role", "quantity"),
    [
        ("pd-paper-drive", "InnerLink", 33),
        ("pd-paper-drive", "OuterLink", 32),
        ("ch-rocker-arm-tl-oblique-jig", "HoldDownStud", 4),
        ("ch-rocker-arm-tl-oblique-jig", "TNut", 4),
        ("ch-rocker-arm-tl-oblique-jig", "FlangeNut", 4),
    ],
)
@pytest.mark.parametrize("extra", [False, True])
def test_configured_pattern_census_rejects_wrong_installed_quantity(
    native_bindings, name, role, quantity, extra
):
    components = _inventory(name)
    if extra:
        components.append(_component(role, quantity + 1, index=9090))
    else:
        components = [
            component
            for component in components
            if component.ComponentReference != f"{role}:{quantity}"
        ]
    with pytest.raises(RuntimeError):
        verify._assert_shared_component_references(_adapter(components), name)


def test_both_same_file_default_roles_remain_required(native_bindings):
    components = _inventory("dt-drive-train")
    components[1].ComponentReference = "FootScrew:1"
    with pytest.raises(RuntimeError):
        verify._assert_shared_component_references(
            _adapter(components), "dt-drive-train"
        )


def test_unrelated_native_component_does_not_enter_member_census(native_bindings):
    components = _inventory("pn-pen")
    components.append(
        SimpleNamespace(
            Name2="ordinary-part-1",
            ComponentReference="",
            ReferencedConfiguration="Default",
            GetPathName=lambda: "C:/native/ordinary-part.SLDPRT",
        )
    )
    verify._assert_shared_component_references(_adapter(components), "pn-pen")


def _gravity_adapter(events, *, failure=None):
    class Model:
        def __init__(self):
            self.active = "Default"
            self.rebuilt = None
            self.Extension = SimpleNamespace(CreateMassProperty2=self.mass_properties)

        def GetConfigurationByName(self, configuration):
            if failure == "missing-member" and configuration == "PenWire":
                return None
            return object() if configuration in {"LeverWire", "PenWire"} else None

        def EditRebuild3(self):
            events.append(("rebuild", self.active))
            self.rebuilt = self.active
            return True

        def ClearSelection2(self, clear_all):
            assert clear_all is True

        def GetTitle(self):
            return "sh-vn-music-wire.SLDPRT"

        def mass_properties(self):
            events.append(("mass", self.active))
            if failure == "mass" and self.active == "PenWire":
                raise RuntimeError("native mass unavailable")
            if self.rebuilt != self.active:
                raise RuntimeError("native member was not rebuilt")
            return SimpleNamespace(
                Mass=0.001 if self.active == "LeverWire" else 0.002,
                Density=7800.0,
                Volume=1e-6,
                SurfaceArea=1e-4,
                CenterOfMass=[0.0, 0.0, 0.0],
                Recalculate=lambda: True,
                GetOverrideOptions=lambda: SimpleNamespace(
                    OverrideMass=False, OverrideCenterOfMass=False
                ),
            )

    class Adapter:
        def __init__(self):
            self.currentModel = None
            self.swApp = SimpleNamespace(
                CloseDoc=lambda title: events.append(("close", title))
            )

        async def open_model(self, path):
            events.append(("open", path))
            self.currentModel = Model()
            return SimpleNamespace(is_success=True, data=True)

        async def set_active_configuration(self, configuration):
            events.append(("activate", configuration))
            self.currentModel.active = (
                "PenWire" if failure == "misdirect" else configuration
            )
            return SimpleNamespace(is_success=True, data=True)

    return Adapter()


@pytest.mark.parametrize("failure", [None, "misdirect", "missing-member", "mass"])
def test_gravity_reads_exact_wire_members_and_closes_after_success_or_failure(
    monkeypatch, failure
):
    from diagnostics import diag_stock_spring_gravity as gravity
    import _purchased_part_variants as variants

    # Limit this diagnostic to its real wire requests; do not replace their
    # production configurations with the expected answer.
    identities = {
        key: value
        for key, value in gravity.PART_IDENTITIES.items()
        if key.startswith("sh-vn-music-wire--")
    }
    monkeypatch.setattr(gravity, "PART_IDENTITIES", identities)
    monkeypatch.setattr(gravity, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(variants, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        variants,
        "active_configuration_name",
        lambda adapter, model=None: adapter.currentModel.active,
    )
    events = []
    adapter = _gravity_adapter(events, failure=failure)
    if failure is not None:
        with pytest.raises(RuntimeError):
            asyncio.run(gravity._native_masses(adapter))
        if failure == "misdirect":
            assert not any(event[0] == "mass" for event in events)
    else:
        parts = asyncio.run(gravity._native_masses(adapter))
        assert set(parts) == {
            "sh-vn-music-wire--LeverWire",
            "sh-vn-music-wire--PenWire",
        }
        assert parts["sh-vn-music-wire--LeverWire"]["mass_kg"] == 0.001
        assert parts["sh-vn-music-wire--PenWire"]["mass_kg"] == 0.002
        assert parts["sh-vn-music-wire--LeverWire"]["identity"] == {
            "stem": "sh-vn-music-wire",
            "configuration": "LeverWire",
        }
        assert parts["sh-vn-music-wire--PenWire"]["identity"] == {
            "stem": "sh-vn-music-wire",
            "configuration": "PenWire",
        }
        assert (
            parts["sh-vn-music-wire--LeverWire"]["path"]
            == parts["sh-vn-music-wire--PenWire"]["path"]
        )
    assert adapter.currentModel is None
    assert sum(event[0] == "close" for event in events) == sum(
        event[0] == "open" for event in events
    )


@pytest.mark.parametrize(
    ("first_role", "second_role"),
    [
        ("FootScrew", "SwingStopScrew"),
        ("HoldDownStud", "TNut"),
        ("HoldDownStud", "FlangeNut"),
    ],
)
@pytest.mark.parametrize("wrong_member", [False, True])
def test_semantic_fit_binding_requires_both_native_file_and_exact_member(
    monkeypatch, native_bindings, first_role, second_role, wrong_member
):
    import _assembly

    first = _component(first_role, 1, index=504)
    second = _component(second_role, 1, index=109)
    if wrong_member:
        second.ReferencedConfiguration = "unrelated-member"
    adapter = _adapter([first, second])
    adapter._attempt = lambda fn, default=None: fn()
    adapter.currentModel.ToolsCheckInterference = lambda: None
    manager = SimpleNamespace(
        GetInterferences=lambda: [
            SimpleNamespace(Components=[first, second], Volume=0.4 / 1e9)
        ],
        Done=lambda: None,
    )
    monkeypatch.setattr(_assembly, "_early_bound", lambda obj, _interface: obj)
    monkeypatch.setattr(
        _assembly, "configured_interference_manager", lambda _adapter: manager
    )
    pairs = {frozenset((f"@{first_role}:1", f"@{second_role}:1")): 1.0}
    if wrong_member:
        with pytest.raises(RuntimeError, match="expected"):
            _assembly.check_no_interference(adapter, allowed_pairs=pairs)
    else:
        _assembly.check_no_interference(adapter, allowed_pairs=pairs)

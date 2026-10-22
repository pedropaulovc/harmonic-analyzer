"""Behavioral member-boundary checks; these do not qualify SolidWorks natives."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _purchased_part_variants as variants
from _appearance import BAR_STEEL


class MemberPart:
    def __init__(self):
        self.active = "InnerLink"
        self.configurations = {
            name: SimpleNamespace(
                Name=name,
                BOMPartNoSource=8,
                AlternateName=f"sh-vn-chain-link--{name}",
                UseAlternateNameInBOM=True,
                Description=f"Chain {name}",
                UseDescriptionInBOM=True,
            )
            for name in ("InnerLink", "OuterLink")
        }
        self.features = {
            name: MemberFeature(self, name, owner)
            for name, owner in (("InnerBody", "InnerLink"), ("OuterBody", "OuterLink"))
        }
        self.properties = {
            name: {
                "Number": "MHA-SH-VN-50",
                "Description": f"Chain {name}",
                "Quantity": quantity,
            }
            for name, quantity in (("InnerLink", "34"), ("OuterLink", "33"))
        }

    @property
    def ConfigurationManager(self):
        return SimpleNamespace(ActiveConfiguration=self.configurations[self.active])

    def GetConfigurationByName(self, name):
        return self.configurations.get(name)

    def FeatureByName(self, name):
        return self.features.get(name)

    def GetCustomInfoValue(self, configuration, name):
        return self.properties[configuration].get(name, "")


class MemberFeature:
    def __init__(self, part, name, owner, parents=()):
        self.part = part
        self.Name = name
        self.parents = parents
        self.refuse_change = False
        self.persist_change = True
        self.states = {
            configuration: configuration != owner
            for configuration in part.configurations
        }

    def IsSuppressed2(self, _option, _names):
        return (self.states[self.part.active],)

    def SetSuppression2(self, action, _option, _names):
        if self.refuse_change:
            return False
        suppressed = action == 0
        active = self.part.active
        if suppressed:
            if any(
                self.Name in feature.parents and not feature.states[active]
                for feature in self.part.features.values()
            ):
                return False
        elif any(self.part.features[name].states[active] for name in self.parents):
            return False
        if self.persist_change:
            self.states[active] = suppressed
        return True


def _adapter(part):
    async def set_active_configuration(configuration):
        part.active = configuration
        return SimpleNamespace(is_success=True, data=None)

    return SimpleNamespace(
        currentModel=part, set_active_configuration=set_active_configuration
    )


class FreshConfiguration:
    def __init__(self, part, name):
        self.part = part
        self._name = name

    @property
    def Name(self):
        return self._name

    @Name.setter
    def Name(self, name):
        if not self.part.accept_rename:
            return
        previous = self._name
        del self.part.configurations[previous]
        self._name = name
        self.part.configurations[name] = self
        if self.part.active == previous:
            self.part.active = name


class FreshPart:
    def __init__(self, *, accept_rename=True):
        self.active = "Default"
        self.accept_rename = accept_rename
        self.configurations = {}
        self.add_configuration("Default")

    def add_configuration(self, name):
        self.configurations[name] = FreshConfiguration(self, name)

    @property
    def ConfigurationManager(self):
        return SimpleNamespace(ActiveConfiguration=self.configurations[self.active])

    def GetConfigurationByName(self, name):
        return self.configurations.get(name)

    def GetConfigurationNames(self):
        return tuple(self.configurations)


def _fresh_adapter(part, *, persist_creation=True, extra_configuration=None):
    adapter = _adapter(part)

    async def create_configuration(parameters):
        if persist_creation:
            part.add_configuration(parameters.name)
            part.active = parameters.name
        if extra_configuration is not None:
            part.add_configuration(extra_configuration)
        return SimpleNamespace(is_success=True, data=None)

    adapter.create_configuration = create_configuration
    return adapter


@pytest.fixture
def member_registry(monkeypatch):
    row = {
        "number": "MHA-SH-VN-50",
        "default_configuration": "InnerLink",
        "configuration_quantities": {"InnerLink": 34, "OuterLink": 33},
    }
    monkeypatch.setattr(variants._config, "parts", lambda _name: row)
    return row


def test_a_successful_switch_that_keeps_the_wrong_member_is_rejected():
    part = MemberPart()
    adapter = _adapter(part)

    async def refused_switch(_configuration):
        return SimpleNamespace(is_success=True, data=None)

    adapter.set_active_configuration = refused_switch
    with pytest.raises(RuntimeError, match="active member is 'InnerLink'"):
        asyncio.run(variants.activate_member(adapter, "OuterLink"))
    assert part.active == "InnerLink"


def test_a_requested_member_cannot_be_replaced_by_an_existing_different_one():
    part = MemberPart()
    with pytest.raises(RuntimeError, match="does not exist"):
        asyncio.run(variants.activate_member(_adapter(part), "PenWire"))
    assert part.active == "InnerLink"


def test_each_member_accepts_only_its_own_feature_set():
    part = MemberPart()
    members = {"InnerLink": ("InnerBody",), "OuterLink": ("OuterBody",)}
    for name in members:
        part.active = name
        variants.assert_member_suppression(_adapter(part), name, members)
    part.features["InnerBody"].states["OuterLink"] = False
    with pytest.raises(RuntimeError, match="InnerBody.*wrong member suppression"):
        variants.assert_member_suppression(_adapter(part), "OuterLink", members)


def test_suppressing_the_selected_members_own_body_is_not_a_valid_variant():
    part = MemberPart()
    part.features["InnerBody"].states["InnerLink"] = True
    with pytest.raises(RuntimeError, match="InnerBody.*wrong member suppression"):
        variants.assert_member_suppression(
            _adapter(part),
            "InnerLink",
            {"InnerLink": ("InnerBody",), "OuterLink": ("OuterBody",)},
        )


def test_missing_or_shared_feature_ownership_is_not_silently_accepted():
    part = MemberPart()
    with pytest.raises(RuntimeError, match="not found"):
        variants.assert_member_suppression(
            _adapter(part), "InnerLink", {"InnerLink": ("AbsentBody",)}
        )
    with pytest.raises(ValueError, match="ownership overlaps"):
        variants.assert_member_suppression(
            _adapter(part),
            "InnerLink",
            {"InnerLink": ("InnerBody",), "OuterLink": ("InnerBody",)},
        )


@pytest.mark.parametrize(
    "names",
    [
        ("OuterLink", "InnerLink"),
        ("InnerLink", "PenWire"),
        ("InnerLink",),
        ("InnerLink", "OuterLink", "OuterLink"),
        (),
    ],
)
def test_member_names_must_match_registry_order(member_registry, names):
    with pytest.raises(ValueError, match="differ from registry order"):
        variants.require_member_configurations("sh-vn-chain-link", names)


def test_registry_default_must_be_an_actual_member(member_registry):
    member_registry["default_configuration"] = "Default"
    with pytest.raises(
        ValueError, match="invalid configuration_quantities/default_configuration"
    ):
        variants.require_member_configurations(
            "sh-vn-chain-link", ("InnerLink", "OuterLink")
        )


def test_same_purchase_number_does_not_make_foreign_native_bom_member_valid(
    member_registry,
):
    part = MemberPart()
    variants.assert_member_properties(
        _adapter(part), "sh-vn-chain-link", "InnerLink", "Chain InnerLink", {}
    )
    part.configurations["InnerLink"].AlternateName = "sh-vn-chain-link--OuterLink"
    with pytest.raises(RuntimeError, match="native BOM identity"):
        variants.assert_member_properties(
            _adapter(part), "sh-vn-chain-link", "InnerLink", "Chain InnerLink", {}
        )


def test_configuration_quantity_cannot_inherit_the_family_total(member_registry):
    part = MemberPart()
    part.properties["InnerLink"]["Quantity"] = "67"
    with pytest.raises(RuntimeError, match="Quantity.*expected '34'"):
        variants.assert_member_properties(
            _adapter(part), "sh-vn-chain-link", "InnerLink", "Chain InnerLink", {}
        )


@pytest.mark.parametrize("suppressed", [False, True])
@pytest.mark.parametrize(
    ("failure", "message"),
    [
        ("refused", "native suppression change refused"),
        ("not-persisted", "did not persist"),
    ],
)
def test_native_suppression_refusal_or_nonpersistence_is_rejected(
    suppressed, failure, message
):
    part = MemberPart()
    feature = part.features["InnerBody"]
    feature.states["InnerLink"] = not suppressed
    feature.refuse_change = failure == "refused"
    feature.persist_change = failure != "not-persisted"
    before = dict(feature.states)

    with pytest.raises(RuntimeError, match=message):
        variants.set_member_suppression(
            _adapter(part), ("InnerBody",), suppressed=suppressed
        )

    assert feature.states == before


def test_member_suppression_respects_native_dependencies_and_other_configurations():
    part = MemberPart()
    part.features = {
        "PlateSketch": MemberFeature(part, "PlateSketch", "InnerLink"),
        "PlateBody": MemberFeature(
            part, "PlateBody", "InnerLink", parents=("PlateSketch",)
        ),
        "Bore": MemberFeature(part, "Bore", "InnerLink", parents=("PlateBody",)),
    }
    names = ("PlateSketch", "PlateBody", "Bore")
    foreign_states = {
        name: feature.states["OuterLink"] for name, feature in part.features.items()
    }

    variants.set_member_suppression(_adapter(part), names, suppressed=True)
    assert all(feature.states["InnerLink"] for feature in part.features.values())
    assert {
        name: feature.states["OuterLink"] for name, feature in part.features.items()
    } == foreign_states

    variants.set_member_suppression(_adapter(part), names, suppressed=False)
    assert all(not feature.states["InnerLink"] for feature in part.features.values())
    assert {
        name: feature.states["OuterLink"] for name, feature in part.features.items()
    } == foreign_states


def test_selecting_each_member_corrects_foreign_features_without_changing_the_other_member():
    part = MemberPart()
    adapter = _adapter(part)
    members = {"InnerLink": ("InnerBody",), "OuterLink": ("OuterBody",)}
    for feature in part.features.values():
        feature.states = {"InnerLink": False, "OuterLink": False}

    asyncio.run(variants.select_member_features(adapter, "OuterLink", members))
    assert part.active == "OuterLink"
    assert part.features["InnerBody"].states == {"InnerLink": False, "OuterLink": True}
    assert part.features["OuterBody"].states == {"InnerLink": False, "OuterLink": False}

    asyncio.run(variants.select_member_features(adapter, "InnerLink", members))
    assert part.active == "InnerLink"
    assert part.features["InnerBody"].states == {"InnerLink": False, "OuterLink": True}
    assert part.features["OuterBody"].states == {"InnerLink": True, "OuterLink": False}


@pytest.mark.parametrize(
    "states",
    [None, (), (False, True), (0,), (1,), ("False",), (None,), False, "False"],
)
def test_malformed_native_suppression_readback_is_rejected(states):
    feature = SimpleNamespace(Name="Body", IsSuppressed2=lambda _option, _names: states)
    with pytest.raises(RuntimeError, match="invalid native suppression state"):
        variants._suppressed(feature)


@pytest.mark.parametrize("default", ["InnerLink", "OuterLink"])
def test_new_part_uses_registry_default_as_a_real_member(member_registry, default):
    member_registry["default_configuration"] = default
    names = (
        default,
        *(
            name
            for name in member_registry["configuration_quantities"]
            if name != default
        ),
    )
    part = FreshPart()

    asyncio.run(
        variants.create_member_configurations(
            _fresh_adapter(part), "sh-vn-chain-link", names
        )
    )

    assert part.GetConfigurationNames() == names
    assert part.active == default
    assert part.GetConfigurationByName("Default") is None
    assert all(part.GetConfigurationByName(name).Name == name for name in names)


def test_bad_member_order_is_rejected_before_initial_native_rename(member_registry):
    part = FreshPart()
    with pytest.raises(ValueError, match="differ from registry order"):
        asyncio.run(
            variants.create_member_configurations(
                _fresh_adapter(part),
                "sh-vn-chain-link",
                ("OuterLink", "InnerLink"),
            )
        )
    assert part.GetConfigurationNames() == ("Default",)
    assert part.active == "Default"


def test_initial_native_configuration_rename_must_persist(member_registry):
    part = FreshPart(accept_rename=False)
    with pytest.raises(RuntimeError, match="initial configuration did not rename"):
        asyncio.run(
            variants.create_member_configurations(
                _fresh_adapter(part),
                "sh-vn-chain-link",
                ("InnerLink", "OuterLink"),
            )
        )
    assert part.GetConfigurationNames() == ("Default",)
    assert part.active == "Default"


@pytest.mark.parametrize(
    ("persist_creation", "extra_configuration", "remaining"),
    [
        (False, None, ("InnerLink",)),
        (True, "Unexpected", ("InnerLink", "OuterLink", "Unexpected")),
    ],
)
def test_successful_configuration_creation_must_leave_exact_native_inventory(
    member_registry,
    persist_creation,
    extra_configuration,
    remaining,
):
    part = FreshPart()
    adapter = _fresh_adapter(
        part,
        persist_creation=persist_creation,
        extra_configuration=extra_configuration,
    )
    with pytest.raises(RuntimeError, match="differ from requested"):
        asyncio.run(
            variants.create_member_configurations(
                adapter,
                "sh-vn-chain-link",
                ("InnerLink", "OuterLink"),
            )
        )
    assert part.GetConfigurationNames() == remaining


def test_member_authoring_refuses_a_nonfresh_native_without_renaming_it(
    member_registry,
):
    part = FreshPart()
    part.add_configuration("ExistingMember")
    with pytest.raises(RuntimeError, match="fresh single-configuration part"):
        asyncio.run(
            variants.create_member_configurations(
                _fresh_adapter(part),
                "sh-vn-chain-link",
                ("InnerLink", "OuterLink"),
            )
        )
    assert part.GetConfigurationNames() == ("Default", "ExistingMember")
    assert part.active == "Default"


@pytest.mark.parametrize("configuration", ["InnerLink", "OuterLink"])
@pytest.mark.parametrize(
    "observed",
    [
        (0.1, 0.2, 0.3),
        (float("nan"), BAR_STEEL[1], BAR_STEEL[2]),
        (BAR_STEEL[0], float("nan"), BAR_STEEL[2]),
        (BAR_STEEL[0], BAR_STEEL[1], float("nan")),
        (),
        None,
    ],
)
def test_wrong_or_nonfinite_member_rgb_is_rejected(configuration, observed):
    part = MemberPart()
    part.active = configuration
    part.MaterialPropertyValues = observed
    with pytest.raises(RuntimeError, match="native colour"):
        variants.require_member_colour(_adapter(part), configuration, BAR_STEEL)


@pytest.mark.parametrize("configuration", ["InnerLink", "OuterLink"])
def test_native_member_colour_accepts_solidworks_channel_quantization(configuration):
    part = MemberPart()
    part.active = configuration
    quantized = tuple(round(channel * 255) / 255 for channel in BAR_STEEL)
    part.MaterialPropertyValues = (*quantized, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0)
    variants.require_member_colour(_adapter(part), configuration, BAR_STEEL)


def test_matching_rgb_on_the_wrong_active_member_is_not_a_valid_colour_readback():
    part = MemberPart()
    part.MaterialPropertyValues = BAR_STEEL
    with pytest.raises(RuntimeError, match="active member is 'InnerLink'"):
        variants.require_member_colour(_adapter(part), "OuterLink", BAR_STEEL)

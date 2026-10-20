"""Behavioral member-boundary checks; these do not qualify SolidWorks natives."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import _purchased_part_variants as variants


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
            name: {"Number": "MHA-SH-VN-50", "Description": f"Chain {name}", "Quantity": quantity}
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
    def __init__(self, part, name, owner):
        self.part = part
        self.Name = name
        self.states = {configuration: configuration != owner for configuration in part.configurations}

    def IsSuppressed2(self, _option, _names):
        return (self.states[self.part.active],)


def _adapter(part):
    return SimpleNamespace(currentModel=part)


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
            _adapter(part), "InnerLink", {"InnerLink": ("InnerBody",), "OuterLink": ("OuterBody",)},
        )


def test_missing_or_shared_feature_ownership_is_not_silently_accepted():
    part = MemberPart()
    with pytest.raises(RuntimeError, match="not found"):
        variants.assert_member_suppression(_adapter(part), "InnerLink", {"InnerLink": ("AbsentBody",)})
    with pytest.raises(ValueError, match="ownership overlaps"):
        variants.assert_member_suppression(
            _adapter(part), "InnerLink", {"InnerLink": ("InnerBody",), "OuterLink": ("InnerBody",)},
        )


def test_default_selection_comes_from_the_exact_registry_members(member_registry):
    assert variants._registry_members("sh-vn-chain-link", ("OuterLink", "InnerLink")) == ("InnerLink", "OuterLink")
    with pytest.raises(ValueError, match="differ from registry"):
        variants._registry_members("sh-vn-chain-link", ("InnerLink", "PenWire"))
    member_registry["default_configuration"] = "Default"
    with pytest.raises(ValueError, match="not placeable"):
        variants._registry_members("sh-vn-chain-link", ("InnerLink", "OuterLink"))


def test_same_purchase_number_does_not_make_foreign_native_bom_member_valid(member_registry):
    part = MemberPart()
    variants.assert_member_properties(_adapter(part), "sh-vn-chain-link", "InnerLink", "Chain InnerLink", {})
    part.configurations["InnerLink"].AlternateName = "sh-vn-chain-link--OuterLink"
    with pytest.raises(RuntimeError, match="native BOM identity"):
        variants.assert_member_properties(_adapter(part), "sh-vn-chain-link", "InnerLink", "Chain InnerLink", {})


def test_configuration_quantity_cannot_inherit_the_family_total(member_registry):
    part = MemberPart()
    part.properties["InnerLink"]["Quantity"] = "67"
    with pytest.raises(RuntimeError, match="Quantity.*expected '34'"):
        variants.assert_member_properties(_adapter(part), "sh-vn-chain-link", "InnerLink", "Chain InnerLink", {})

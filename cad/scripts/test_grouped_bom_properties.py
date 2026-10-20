"""Current family identities stamped into native grouped BOM configurations."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _grouped_bom_properties as grouped


@pytest.fixture
def grouped_model(monkeypatch):
    configurations = {name: SimpleNamespace() for name in ("T006", "T120")}
    requested = []

    def configuration(name):
        requested.append(name)
        return configurations.get(name)

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetConfigurationByName=configuration),
    )
    monkeypatch.setattr(grouped, "_early_bound", lambda raw, _interface: raw)
    monkeypatch.setattr(grouped._telemetry, "success", lambda _message: None)
    return adapter, configurations, requested


@pytest.mark.parametrize(
    "number",
    (
        "MHA-DT-03",
        "MHA-DT-00",
        "MHA-CH-06-TL-20",
        "MHA-CH-06-TL-00",
        "MHA-SH-VN-50",
        "MHA-SH-VN-51",
        "MHA-SH-VN-56",
        "MHA-SH-VN-57",
        "MHA-PD-VN-99",
        "MHA-CH-06-TL-VN-50",
        "MHA-CH-06-TL-VN-99",
    ),
)
def test_current_family_numbers_are_stamped_on_every_configuration(
    grouped_model, number,
):
    adapter, configurations, requested = grouped_model
    grouped.apply_grouped_bom_properties(
        adapter,
        ("T006", "T120"),
        part_number=f" {number.lower()} ",
        description=" GROUPED FAMILY ",
    )
    assert requested == ["T006", "T120"]
    for configuration in configurations.values():
        assert configuration.BOMPartNoSource == 8
        assert configuration.AlternateName == number
        assert configuration.UseAlternateNameInBOM is True
        assert configuration.Description == "GROUPED FAMILY"
        assert configuration.UseDescriptionInBOM is True


@pytest.mark.parametrize(
    "number",
    (
        "MHA-DT-003",
        "MHA-DT-000",
        "MHA-CH-006-TL-20",
        "MHA-CH-06-TL-000",
        "MHA-CH-06-TL-VN-050",
        "MHA-FR-VN-050",
        "MHA-VN-050",
        "MHA-VN-50",
        "MHA-FR-VN-49",
        "MHA-FR-VN-00",
        "MHA-CH-06-TL-VN-49",
        "MHA-FR-VN-100",
        "MHA-SH-VN-49",
        "MHA-SH-VN-050",
        "MHA-SH-VN-100",
        "MHA-CH-6-TL-20",
        "MHA-CH-06-TL-2",
        "MHA-DT-03-T006",
        "MHA-CH-06-TL-VN-50-T006",
        "MHA-DT-０３",
        "MHA-CH-06-TL-VN-５0",
        "MHA-CH-06-TL-VN-50-extra",
    ),
)
def test_noncurrent_or_nonfamily_numbers_fail_before_native_access(
    grouped_model, number,
):
    adapter, configurations, requested = grouped_model
    with pytest.raises(ValueError, match="invalid grouped BOM part number"):
        grouped.apply_grouped_bom_properties(
            adapter,
            ("T006", "T120"),
            part_number=number,
            description="GROUPED FAMILY",
        )
    assert requested == []
    assert all(vars(configuration) == {} for configuration in configurations.values())


def test_bom_aliases_preserve_distinct_current_stock_identities():
    from _drawing_tables import _bom_identity_map

    families = (
        "sh-vn-brass-fillister-screw",
        "dt-vn-cone-lock-knob",
        "ch-rocker-arm-tl-vn-oblique-rail",
    )
    numbers = ("MHA-SH-VN-51", "MHA-DT-VN-51", "MHA-CH-06-TL-VN-50")
    aliases = dict(zip(numbers, families, strict=True))
    identities = _bom_identity_map(families, aliases)
    assert len(identities) == 2 * len(families)
    for number, family in aliases.items():
        assert identities[number.lower()] == family
        assert identities[family] == family
    assert "mha-vn-51" not in identities
    assert "vn-brass-fillister-screw" not in identities


def test_shared_purchase_number_alone_cannot_disambiguate_configured_rows():
    from _drawing_tables import _bom_identity_map

    with pytest.raises(ValueError, match="maps to both"):
        _bom_identity_map(
            ("sh-vn-chain-link--InnerLink", "sh-vn-chain-link--OuterLink"),
            {
                "MHA-SH-VN-50": "sh-vn-chain-link--InnerLink",
                " mha-sh-vn-50 ": "sh-vn-chain-link--OuterLink",
            },
        )

"""Offline part, recipe and fit contracts for sh-vn-pivot-pin.

Its purchase sheet retired for a HARDWARE.md row (#2886); these checks pin
the part the assemblies still build.
"""

from __future__ import annotations

import _config
import _dowel_dimensions
import _mcmaster_90145a299 as catalogue
import ch_channel_assembly_sheet as channel_sheet
import ch_channel_explode_spec as explode
import joint_retention
import pytest
import sh_vn_pivot_pin_bar_spec as bar_pin
import sh_vn_pivot_pin_rod_spec as rod_pin
import sh_vn_pivot_pin_spec as pin

ROW = _config.parts(pin.PART_STEM)
MEMBERS = (rod_pin, bar_pin)


def test_the_pin_is_one_purchased_sku_in_two_members() -> None:
    assert ROW["process"] == "purchased"
    assert ROW["supplier_skus"] == [catalogue.SKU] == ["90145A299"]
    assert ROW["default_configuration"] == pin.CONFIGURATIONS[0]
    quantities = ROW["configuration_quantities"]
    assert tuple(quantities) == pin.CONFIGURATIONS
    # One pin per joint: each channel's rod fork and bar notch.
    assert quantities == {spec.CONFIGURATION: 20 for spec in MEMBERS}
    assert sum(quantities.values()) == ROW["quantity"] == 40
    assert {spec.CONFIGURATION for spec in MEMBERS} == set(pin.CONFIGURATIONS)


def test_each_member_is_installed_flush_in_its_host() -> None:
    import ch_amplitude_bar_spec as bar
    import ch_connecting_rod_spec as rod

    assert rod_pin.PIN_INSTALLED_LENGTH == pytest.approx(rod.FORK_THICKNESS)
    assert bar_pin.PIN_INSTALLED_LENGTH == pytest.approx(bar.BAR_WIDTH)
    for spec in MEMBERS:
        # The catalogue length dresses down to the installed one at both ends.
        assert pin.PIN_LENGTH_LIMITS[0] > spec.PIN_INSTALLED_LENGTH
        assert spec.PIN_DIA_LIMITS == pin.PIN_DIA_LIMITS


def test_the_catalogue_band_is_not_the_generic_dowel_band() -> None:
    """90145A299 prints 0/+.0002 on 5/64; the shared dowel table's band is
    the hardened series', which would overstate the press."""
    assert catalogue.DIA_BAND_IN == (0.0, 0.0002)
    assert catalogue.DIA_BAND_IN != _dowel_dimensions.DIA_BAND_IN
    low, high = pin.PIN_DIA_LIMITS
    assert low == pin.PIN_DIA == pytest.approx(25.4 * 5 / 64)
    assert high - low == pytest.approx(0.0002 * 25.4)


def test_joint_retention_lists_the_pin_as_purchased_and_unthreaded() -> None:
    stem = pin.PART_STEM.replace("-", "_")
    assert stem in joint_retention.UNTHREADED_PARTS
    assert stem in joint_retention.UNTHREADED_STOCK


def test_the_channel_bom_rows_are_keyed_by_member() -> None:
    rows = {rod_pin: explode.ROD_PIN, bar_pin: explode.BAR_PIN}
    for spec, key in rows.items():
        assert key == f"{pin.PART_STEM}--{spec.CONFIGURATION}"
        assert explode.member_family(pin.PART_STEM, spec.CONFIGURATION) == key
        assert channel_sheet.BOM_DESCRIPTIONS[key] == spec.BOM_DESCRIPTION
    # Only the shared pin is keyed by member.
    assert explode.member_family("ch-connecting-rod", "Default") == "ch-connecting-rod"

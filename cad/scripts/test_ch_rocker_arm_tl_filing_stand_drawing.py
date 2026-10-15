"""Offline contracts for the rocker arm filing stand (MHA-CH-006-TL-12)."""

from __future__ import annotations

import re
import tomllib

from prechips.model import FixtureSolid

import _config
import _process_plans as plans
import ch_rocker_arm_spec as rocker
import ch_rocker_arm_tl_filing_stand_spec as spec
import draw_ch_rocker_arm_tl_filing_stand as drawing
import export_features

STEM = "ch_rocker_arm_tl_filing_stand"


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.PLAN_KEEP) | set(drawing.ELEVATION_KEEP) == marked
    assert not set(drawing.PLAN_KEEP) & set(drawing.ELEVATION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_pedestal_top_carries_the_lower_hub_face() -> None:
    """S1 op 10 leaves the upper hub face (raw + hub) / 2 over the raw
    underside, so the lower hub face stands (raw - hub) / 2 over the blocks."""
    top = _features()["pedestal_top"]
    lower_hub_face = (spec.RAW_THICKNESS - rocker.HUB_LENGTH) / 2.0
    assert abs(lower_hub_face - 0.4405) < 1e-9
    assert top["height"][0] <= lower_hub_face <= top["height"][1]
    assert top["height"][1] - top["height"][0] <= 2.0 * rocker.HUB_LENGTH_BAND[0] + 1e-9
    assert top["dia"][1] < rocker.HUB_DIA_MIN
    assert (
        f"{top['height'][0]:.2f}-{top['height'][1]:.2f}" in spec.PEDESTAL_LENGTH_CALLOUT
    )


def test_end_blocks_sit_under_the_blank_ends_clear_of_the_arm() -> None:
    for side in ("left", "right"):
        top = _features()[f"{side}_end_block_top"]
        assert spec.BLOCK_OUTER_X - top["length"][1] > rocker.ROD_TIP_X
    assert spec.BLOCK_OUTER_X == spec.RAW_LENGTH / 2.0


def test_prechips_solids_are_the_built_set_in_the_fixture_frame() -> None:
    solids = {solid["name"]: solid for solid in spec.PRECHIPS_SOLIDS}
    for solid in spec.PRECHIPS_SOLIDS:
        FixtureSolid.model_validate(solid)
    assert solids["bench top"]["supply"] == "existing"
    # Fixture frame Z0 = end-block tops: blocks and pedestal start a block
    # height down, and the pedestal top stands the step above Z0.
    for side, west_x in zip(("left", "right"), spec.BLOCK_WEST_X, strict=True):
        block = solids[f"{side} end block"]
        assert block["at_mm"] == [west_x, spec.BLOCK_SOUTH_Y, -spec.BLOCK_HEIGHT]
        assert block["at_mm"][2] + block["size_mm"][2] == 0.0
    pedestal = solids["hub pedestal"]
    assert abs(pedestal["at_mm"][2] + pedestal["length_mm"] - spec.STEP) < 1e-9
    assert (
        solids["bench top"]["at_mm"][2] + solids["bench top"]["size_mm"][2]
        == -spec.BLOCK_HEIGHT
    )


def test_inventory_record_binds_to_this_spec() -> None:
    inventory = tomllib.loads(
        (plans.PROCESS_ROOT / "shop" / "inventory.toml").read_bytes().decode()
    )
    record = inventory["fixtures"]["rocker-filing-stand"]
    assert record["cad"] == STEM
    assert "solids" not in record
    assert f"{STEM}_spec" in plans.shop_spec_modules()


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-filing-stand")["number"]
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(r"MILL|SAW|TURN|FACE TO", spec.DRAWING_NOTES.upper())


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """One fact: a band applied to an unrounded model nominal exports limits
    the sheet never prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked

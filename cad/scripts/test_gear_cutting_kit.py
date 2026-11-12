"""The gear-cutting kit records (#2356, #2465, #2467) cover what the gear
specs and the key module ask of them: every stock cutter a cut gear names, an
arbor for each cutter hole, a broach that cuts inside the printed keyway
width at the gears' faces, and a keyseat end mill inside the shaft's printed
width."""

from __future__ import annotations

import tomllib

import pytest

import build_dt_cone_gear_shaft as shaft
import cone_land_key
import dt_alignment_pinion_spec
import dt_cone_gear_spec
import dt_crank_drive_gear_spec
import dt_crank_pinion_spec
import dt_cylinder_gear_spec
import pd_rack_pinion_spec
import pd_transgear_feed_pinion_spec
import pd_transgear_knob_shaft_spec
from _paths import CAD_ROOT

MM_PER_IN = 25.4
TOOLS = tomllib.loads(
    (CAD_ROOT / "config" / "shop-equipment.toml").read_text(encoding="utf-8")
)["tools"]


def _stock_cutters() -> set[tuple[int, int, int]]:
    """(diametral pitch, cutter number, teeth) of every gear cut with a stock
    form cutter; T006's tool is shop-made and has no number."""
    cone_dp = round(dt_cone_gear_spec.DIAMETRAL_PITCH)
    cutters = {
        (cone_dp, dt_cone_gear_spec.cutter_template(teeth).cutter_number, teeth)
        for teeth in dt_cone_gear_spec.CONFIGURATION_TEETH
    }
    for spec, pitch, in_range in (
        (dt_cylinder_gear_spec, dt_cylinder_gear_spec.DIAMETRAL_PITCH, True),
        (dt_alignment_pinion_spec, dt_alignment_pinion_spec.DIAMETRAL_PITCH, True),
        (pd_rack_pinion_spec, pd_rack_pinion_spec.DIAMETRAL_PITCH, True),
        (
            pd_transgear_knob_shaft_spec,
            pd_transgear_knob_shaft_spec.DIAMETRAL_PITCH,
            True,
        ),
        (
            pd_transgear_feed_pinion_spec,
            pd_transgear_feed_pinion_spec.DIAMETRAL_PITCH,
            True,
        ),
        (dt_crank_pinion_spec, dt_crank_drive_gear_spec.CUTTER_DIAMETRAL_PITCH, True),
        # The 64T's cutter is chosen for its virtual tooth count, so its real
        # count is not checked against the cutter's range.
        (
            dt_crank_drive_gear_spec,
            dt_crank_drive_gear_spec.CUTTER_DIAMETRAL_PITCH,
            False,
        ),
    ):
        cutters.add((round(pitch), spec.CUTTER_NUMBER, spec.TEETH if in_range else 0))
    return cutters


def _cutter_sets() -> dict[int, dict]:
    sets = {
        record["diametral_pitch"]: record
        for record in TOOLS.values()
        if record.get("kind") == "involute_gear_cutter_set"
    }
    assert sets, "no involute cutter record"
    return sets


def test_every_stock_cutter_a_gear_names_is_recorded_with_its_range() -> None:
    sets = _cutter_sets()
    assert dt_cone_gear_spec.cutter_template(6).cutter_number is None
    needed = _stock_cutters()
    for pitch, number, teeth in sorted(needed):
        record = sets[pitch]
        assert record["pressure_angle_deg"] == 20.0
        member = record["members"][str(number)]
        low, high = member["teeth"]
        if teeth:
            assert low <= teeth <= high, (pitch, number, teeth)
        assert member["sku"] and member["price_usd"] > 0
    # No cutter is recorded that no gear uses.
    recorded = {
        (pitch, int(number))
        for pitch, record in sets.items()
        for number in record["members"]
    }
    assert recorded == {(pitch, number) for pitch, number, _ in needed}


def test_every_cutter_hole_has_an_arbor() -> None:
    arbors = {
        record["bore_in"]
        for record in TOOLS.values()
        if record.get("kind") == "cutter_arbor"
    }
    assert {record["bore_in"] for record in _cutter_sets().values()} <= arbors


def test_the_broach_cuts_the_printed_keyway_at_every_keyed_face() -> None:
    broach = TOOLS["keyway-broach-1-16-a"]
    width_min, width_max = cone_land_key.limits(
        cone_land_key.KEYWAY_WIDTH_MM, cone_land_key.KEYWAY_WIDTH_BAND
    )
    cut_min, cut_max = (value * MM_PER_IN for value in broach["width_in"])
    assert width_min - 1e-9 <= cut_min <= cut_max <= width_max + 1e-9
    shortest, longest = (value * MM_PER_IN for value in broach["length_of_cut_in"])
    for face in (dt_cone_gear_spec.FACE_WIDTH, dt_crank_drive_gear_spec.FACE_WIDTH):
        assert shortest < face < longest
    assert TOOLS["broach-bushing-3-8-a"]["bore_in"] * MM_PER_IN == pytest.approx(
        cone_land_key.LAND_DIA_MM
    )


def test_the_keyseat_end_mill_cuts_inside_the_printed_width() -> None:
    cutter = TOOLS["keyseat-endmill-1-16"]
    width_min, width_max = cone_land_key.limits(
        cone_land_key.KEYSEAT_WIDTH_MM, shaft.KEYSEAT_WIDTH_PRINT_BAND
    )
    low, high = (value * MM_PER_IN for value in cutter["dia_in"])
    assert width_min <= low <= high <= width_max + 1e-9
    assert cutter["flutes"] == 2

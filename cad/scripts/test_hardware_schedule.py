"""Every purchased part has a COTS tier, every tier-1 part has a schedule row
whose envelope resolves from its pure provider, and the release ships the
schedule (#2886)."""

from __future__ import annotations

import _config
import cut_release
import error_budget
import ha_harmonic_analyzer_assembly_steps as ha_steps
import hardware_schedule as schedule
import mg_magnifier_assembly_steps as mg_steps
from _assembly_contract import assembly_contract


def test_music_wire_row_cites_every_assembly_that_cuts_and_forms_it():
    # The wire is bought as coil and cut and formed in the assembly steps
    # (hardware.yaml beside the row), so its row names each assembly drawing
    # that does it: the two that use it, and MHA-HA-00, which ties the pen
    # wire to the wheel rim.
    assert {mg_steps.WIRE_HOOKED_KEY, mg_steps.WIRE_TIED_KEY} <= set(mg_steps.SEQUENCE)
    assert "pen-wire-tied" in ha_steps.SEQUENCE
    designation = schedule.SCHEDULE["sh-vn-music-wire"]["designation"]
    for assembly in schedule.used_in()["sh-vn-music-wire"]:
        assert assembly_contract(assembly).number in designation, assembly
    assert ha_steps.DRAWING_NUMBER in designation


def test_every_purchased_part_has_a_tier_and_every_tier_names_a_part():
    tiered = set(schedule.TIERS)
    assert schedule.purchased_parts() <= tiered
    assert tiered <= set(_config.parts())


def test_only_tier_one_rows_carry_a_designation():
    for stem, row in schedule.TIERS.items():
        assert row["tier"] in (1, 2, 3), stem
        assert row["why"], stem
        scheduled = {"designation", "standard"} <= set(row)
        assert scheduled == (row["tier"] == 1), stem


def test_release_ships_the_schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(error_budget, "build_report", lambda: None)
    monkeypatch.setattr(error_budget, "readout_procedure", lambda _report: "")
    staged = cut_release.stage_readout_procedure(tmp_path, "v0")
    assert schedule.DOCUMENT_NAME in staged
    text = (tmp_path / schedule.DOCUMENT_NAME).read_text(encoding="utf-8")
    for stem, row in schedule.SCHEDULE.items():
        part = _config.parts(stem)
        assert part["number"] in text
        assert row["designation"] in text
        for sku in part["supplier_skus"]:
            assert str(sku) in text

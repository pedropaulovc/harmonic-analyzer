"""Every purchased part has a COTS tier, every tier-1 part has a schedule row
whose envelope resolves from its pure provider, and the release ships the
schedule (#2886)."""

from __future__ import annotations

from pathlib import Path

import yaml

import _config
import cut_release
import error_budget
import hardware_schedule as schedule

ASSEMBLIES = Path(__file__).resolve().parents[1] / "config" / "assemblies"


def test_music_wire_row_cuts_and_forms_at_the_assemblies_that_fit_it():
    # Delegated ruling on #1459 (2026-11-17): the wire is bought as coil and
    # cut to length and formed at assembly; its purchase row says so and
    # names the assembly drawings whose steps hook, wrap and tie it.
    designation = schedule.SCHEDULE["sh-vn-music-wire"]["designation"]
    assert "cut to length and form at assembly" in designation
    for assembly in ("mg-magnifier", "pn-pen", "ha-harmonic-analyzer"):
        number = yaml.safe_load(
            (ASSEMBLIES / f"{assembly}.yaml").read_text(encoding="utf-8")
        )["number"]
        assert number in designation, assembly


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

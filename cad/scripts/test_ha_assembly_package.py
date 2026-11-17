"""The one assembly tool list covers every tool the assembly sheets name, each
row backed by a shop record, and ships in the release (#2392)."""

from __future__ import annotations

from pathlib import Path

import cut_release
import error_budget
import ha_assembly_package as package
import ha_build_sequence as build
from ha_harmonic_analyzer_assembly_spec import BAR_HEIGHT_MM


def test_every_tool_a_sheet_names_has_a_row():
    assert package.unlisted() == ()


def test_every_row_resolves_to_its_shop_records():
    for tool in package.TOOLS:
        for ref in tool.records:
            assert isinstance(package.shop_record(ref), dict), ref
        assert package.status(tool) in {"OWNED", "TO BUY", "TO MAKE"}


def test_a_new_tool_word_fails_the_guard(monkeypatch):
    stem = package.PACKAGES[0]
    texts = dict(package.package_texts())
    texts[stem] = (
        *texts[stem],
        package.Text("SET IT WITH A PROTRACTOR AND A MALLET.", False),
    )
    monkeypatch.setattr(package, "package_texts", lambda: texts)
    assert [word for _drawing, word, _context in package.unlisted()] == ["MALLET"]


def test_the_listed_rule_reads_the_bar_height():
    rule = package.shop_record("shop-equipment.toml:tools.steel-rule-48")
    assert rule["length_in"] * 25.4 >= BAR_HEIGHT_MM


def test_release_ships_the_sequence_and_tool_list(tmp_path, monkeypatch):
    # READOUT.md's own model is test_cut_release_version's; skip its solve here.
    monkeypatch.setattr(error_budget, "build_report", lambda: None)
    monkeypatch.setattr(error_budget, "readout_procedure", lambda _report: "")
    staged = cut_release.stage_readout_procedure(tmp_path, "v0")
    assert package.DOCUMENT_NAME in staged
    text = (tmp_path / package.DOCUMENT_NAME).read_text(encoding="utf-8")
    for phase in build.PHASES:
        assert phase.title in text
        for run in phase.runs:
            assert run.text in text
    for use in package.tool_uses():
        assert use.tool.name in text


def test_review_keys_on_the_sources_of_a_listed_packages_steps(monkeypatch):
    """Rule 22: the machinist review of a package whose steps print here is
    keyed on the modules they are generated from; an unlisted one on none."""
    assert package.fitup_sources("mg-magnifier") == ()
    monkeypatch.setattr(package, "STEPS_IN_DOCUMENT", ("mg-magnifier",))
    names = {Path(path).name for path in package.fitup_sources("mg-magnifier")}
    assert {"ha_assembly_package.py", "mg_magnifier_assembly_sheet.py"} <= names


def test_numbered_steps_and_checks_keep_their_printed_heads():
    """A numbered step or check prints its head in bold (never a nested
    ordered list); an unnumbered check is a plain row."""
    assert package._list_item("12A. TIGHTEN IT.") == "- **12A.** TIGHTEN IT."
    assert package._list_item("1. THE BAR IS LEVEL.") == "- **1.** THE BAR IS LEVEL."
    assert package._list_item("CHECK: IT TURNS.") == "- CHECK: IT TURNS."


def test_summing_lever_step_stops_before_its_final_assembly_step():
    import ha_harmonic_analyzer_assembly_sheet as ha_sheet
    import sm_summing_assembly_sheet as sm_sheet

    numbers = [step.split(". ", 1)[0] for step in sm_sheet.ASSEMBLY_STEPS]
    last = numbers.index(ha_sheet.SM_LAST_BENCH_STEP)
    assert "AT FINAL ASSEMBLY" in sm_sheet.ASSEMBLY_STEPS[last + 1]
    assert not any("FINAL ASSEMBLY" in step for step in sm_sheet.ASSEMBLY_STEPS[: last + 1])

"""The one assembly tool list covers every tool the assembly sheets name, each
row backed by a shop record, and ships in the release (#2392)."""

from __future__ import annotations

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
    rule = package.shop_record("shop-equipment.toml:tools.steel-rule-24")
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

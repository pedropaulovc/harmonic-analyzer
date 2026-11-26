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
    # Every live row's label comes from a recorded inventory status (or it is
    # made in the step): none prints UNRECORDED.
    for tool in package.TOOLS:
        for ref in tool.records:
            assert isinstance(package.shop_record(ref), dict), ref
        assert package.status(tool) in set(package.STATUS_LABELS.values()), tool.name


def test_the_label_is_the_inventory_status_alone(monkeypatch):
    records = {
        "shop": {"gauges": {"g": {}}},
        "shop-equipment": {
            "tools": {
                "owned": {"status": "on_hand", "supply": "shop_made"},
                "ordered": {"status": "not_received"},
                "buy": {"status": "to_order"},
                "make": {"status": "to_make"},
                "bare": {},
            }
        },
    }
    monkeypatch.setattr(package, "shop_records", lambda: records)

    def label(*refs: str) -> str:
        return package.status(package.Tool("t", "T", refs))

    # supply is provenance only.
    assert label("shop-equipment:tools.owned") == "OWNED"
    assert label("shop-equipment:tools.ordered") == "ORDERED"
    assert label("shop-equipment:tools.buy") == "TO BUY"
    assert label("shop-equipment:tools.make") == "TO MAKE"
    # No status, or only a prechips record: unrecorded, never OWNED.
    assert label("shop-equipment:tools.bare") == package.UNRECORDED
    assert label("shop:gauges.g") == package.UNRECORDED
    assert label("shop:gauges.g", "shop-equipment:tools.owned") == "OWNED"
    # Records that disagree print the worst.
    assert label("shop-equipment:tools.owned", "shop-equipment:tools.buy") == "TO BUY"
    assert label() == "TO MAKE"


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
    rule = package.shop_record("shop-equipment:tools.steel-rule-48")
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


def test_numbered_steps_and_checks_keep_their_printed_heads():
    """A numbered step or check prints its head in bold (never a nested
    ordered list); an unnumbered check is a plain row."""
    assert package._list_item("12A. TIGHTEN IT.") == "- **12A.** TIGHTEN IT."
    assert package._list_item("1. THE BAR IS LEVEL.") == "- **1.** THE BAR IS LEVEL."
    assert package._list_item("CHECK: IT TURNS.") == "- CHECK: IT TURNS."


def test_a_listed_package_prints_its_section_and_its_review_reads_it(monkeypatch):
    """Rule 22, end to end without mocking the generator: a package listed in
    STEPS_IN_DOCUMENT whose sheet module exposes STEP_SECTIONS and
    ASSEMBLY_CHECKS prints them in ASSEMBLY.md, and its review prompt carries
    the same section."""
    import machinist_review as mr
    import mg_magnifier_assembly_sheet as sheet

    monkeypatch.setattr(package, "STEPS_IN_DOCUMENT", ("mg-magnifier",))
    sections = (("FIT-UP", ("1. PRESS ITEM 2 HOME.", "1A. CHECK: ITEM 2 DOES NOT TURN.")),)
    monkeypatch.setattr(sheet, "STEP_SECTIONS", sections, raising=False)
    monkeypatch.setattr(sheet, "ASSEMBLY_CHECKS", ("2. ITEM 3 TURNS FREELY.",), raising=False)
    expected = (
        "## MHA-MG-00 fit-up steps",
        "### FIT-UP",
        "- **1A.** CHECK: ITEM 2 DOES NOT TURN.",
        "### Checks and notes",
        "- **2.** ITEM 3 TURNS FREELY.",
    )
    text = package.markdown()
    prompt = mr._review_prompt(mr.ReviewPackage("mg_magnifier_assembly", "assembly", ()), 1)
    for line in expected:
        assert f"{line}\n" in text and f"{line}\n" in prompt, line


def test_release_prints_the_steps_moved_off_their_sheets():
    import importlib

    import mg_magnifier_assembly_sheet as mg

    text = package.markdown()
    for stem in package.STEPS_IN_DOCUMENT:
        sheet = importlib.import_module(f"{stem.replace('-', '_')}_assembly_sheet")
        assert f"## {package.drawing_number(stem)} fit-up steps" in text
        for title, steps in sheet.STEP_SECTIONS:
            assert f"### {title}\n" in text
            for step in steps:
                assert f"{package._list_item(step)}\n" in text
        for line in sheet.ASSEMBLY_CHECKS:
            assert f"{package._list_item(line)}\n" in text
    # The printed values are the ones the spec derives, not pasted text.
    assert f"{mg.ENDSHAKE_GO_TEXT} ENTERS, {mg.ENDSHAKE_NO_GO_TEXT} DOES NOT." in text
    # A setting the sheets dimension is cited by its view, never valued.
    assert (
        f"STANDS PAST THE SECOND NUT AS {mg.ENDSHAKE_DETAIL_TITLE} SETS IT" in text
    )


def test_summing_lever_step_stops_before_its_final_assembly_step():
    import ha_harmonic_analyzer_assembly_sheet as ha_sheet
    import sm_summing_assembly_sheet as sm_sheet

    numbers = [step.split(". ", 1)[0] for step in sm_sheet.ASSEMBLY_STEPS]
    last = numbers.index(ha_sheet.SM_LAST_BENCH_STEP)
    assert "AT FINAL ASSEMBLY" in sm_sheet.ASSEMBLY_STEPS[last + 1]
    assert not any("FINAL ASSEMBLY" in step for step in sm_sheet.ASSEMBLY_STEPS[: last + 1])


def test_bar_zero_step_cites_the_measuring_stick_setting_steps():
    """#2434: HA-00 sets every bar to zero by MHA-MS-00's in-use steps, whose
    numbers HA-00 states; they must be that section's first and last, and
    the zero reading prints there (an HA-00 step prints no setting value)."""
    import ha_harmonic_analyzer_assembly_sheet as ha_sheet
    import ms_measuring_stick_assembly_sheet as ms_sheet
    import ms_stick_registration as registration

    heads = [step.split(". ", 1)[0] for step in ms_sheet.USE_STEPS]
    assert ha_sheet.MS_SETTING_STEPS == f"{heads[0]}-{heads[-1]}"
    assert ms_sheet.STEP_SECTIONS[-1][1] == ms_sheet.USE_STEPS
    lines = " ".join(ha_sheet.step_lines("summing-levelled"))
    assert f"WITH MHA-MS-00, PER ITS STEPS {ha_sheet.MS_SETTING_STEPS} (ASSEMBLY.MD)" in lines
    assert any(
        f"FOR A BAR AT ZERO, GRADUATION {registration.ZERO_TICK_TEXT}" in step
        for step in ms_sheet.USE_STEPS
    )

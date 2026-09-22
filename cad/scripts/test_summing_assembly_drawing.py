"""Behavioral boundary contract for the summing assembly package."""

import _config
import build_summing_assembly
import draw_summing_assembly
import knife_hanger_stud_spec
import summing_assembly_spec as assembly_spec
from _buildgraph import references_of


def test_bom_tracks_direct_assembly_sources_and_released_part_identities() -> None:
    direct = {stem.replace("_", "-") for stem in references_of("summing")}
    assert set(assembly_spec.BOM_QUANTITIES) == direct
    assert assembly_spec.BOM_QUANTITIES == {
        stem: int(_config.parts(stem)["quantity"]) for stem in direct
    }
    assert assembly_spec.BOM_PART_NUMBERS == {
        stem: str(_config.parts(stem)["number"]) for stem in direct
    }
    assert set(assembly_spec.BOM_DESCRIPTIONS) == direct


def test_frame_and_channel_interfaces_are_identified_without_duplication() -> None:
    direct = {stem.replace("_", "-") for stem in references_of("summing")}
    interfaces = assembly_spec.EXTERNAL_INTERFACES
    assert set(interfaces) == {
        "top-frame",
        "gooseneck-set-screw",
        "spring-hook",
        "channel-spring-installed",
    }
    assert direct.isdisjoint(interfaces)
    assert interfaces == {
        stem: (
            str(_config.parts(stem)["number"]),
            int(_config.parts(stem)["quantity"]),
        )
        for stem in interfaces
    }


def test_stud_trim_note_agrees_with_the_assembly_hanger_fit_reference() -> None:
    hanger_fit_sheet = draw_summing_assembly.SHEET_NAMES[3]
    expected_head = (
        f"TRIM/INSPECT TO {build_summing_assembly.DRAWING_NUMBER} "
        f"SHEET {draw_summing_assembly.SHEET_NAMES.index(hanger_fit_sheet) + 1}, "
        f"{hanger_fit_sheet}, DETAIL {draw_summing_assembly.HANGER_DETAIL_LABEL}."
    )
    assert knife_hanger_stud_spec.DRAWING_NOTES.splitlines()[0] == expected_head


def test_bom_rows_may_grow_to_the_native_minimum_but_never_shrink() -> None:
    requested = draw_summing_assembly.BOM_ROW_HEIGHT
    assert draw_summing_assembly.bom_row_fit(requested, requested) == "exact"
    assert draw_summing_assembly.bom_row_fit(requested, requested + 1e-7) == "exact"
    assert draw_summing_assembly.bom_row_fit(requested, 0.0085) == "grown"
    assert draw_summing_assembly.bom_row_fit(requested, 0.0) == "short"
    assert draw_summing_assembly.bom_row_fit(requested, requested - 1e-5) == "short"


def test_bom_budget_uses_measured_extents_against_sheet_and_title_block() -> None:
    anchor = draw_summing_assembly.BOM_ANCHOR
    width = sum(draw_summing_assembly.BOM_COLUMN_WIDTHS.values())
    rows = len(assembly_spec.BOM_COMPONENTS) + 1
    assert draw_summing_assembly.bom_extent_violations(
        anchor, width, rows * draw_summing_assembly.BOM_ROW_HEIGHT
    ) == []
    # A doubled header (two-line wrap) still fits.
    assert draw_summing_assembly.bom_extent_violations(
        anchor, width, (rows + 1) * draw_summing_assembly.BOM_ROW_HEIGHT
    ) == []
    # A table tall enough to reach the title block is refused by name.
    violations = draw_summing_assembly.bom_extent_violations(anchor, width, 0.190)
    assert len(violations) == 1
    assert "title block" in violations[0]
    wide = draw_summing_assembly.bom_extent_violations(anchor, 0.300, 0.050)
    assert any("right edge" in violation for violation in wide)

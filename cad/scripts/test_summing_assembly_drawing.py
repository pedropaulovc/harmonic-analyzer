"""Behavioral boundary contract for the summing assembly package."""

import _config
import pytest
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
    violations = draw_summing_assembly.bom_extent_violations(anchor, width, 0.080)
    assert len(violations) == 1
    assert "title block" in violations[0]
    wide = draw_summing_assembly.bom_extent_violations(anchor, 0.300, 0.050)
    assert any("right edge" in violation for violation in wide)


def test_built_hanger_engagement_is_judged_against_the_receiver_band() -> None:
    top = draw_summing_assembly.KNIFE_MOUNT_TOP_Y
    target = draw_summing_assembly.HANGER_ENGAGEMENT_TARGET_MM
    violations = draw_summing_assembly.hanger_engagement_violations
    # r7's B-rep reading: tip rim at 993.5765 under the 999.45 mount top.
    assert violations(top, 993.5765) == []
    assert violations(top, top - target) == []
    # A built tip off the stack target by more than the readback tolerance.
    drifted = violations(top, top - target - 0.01)
    assert len(drifted) == 1 and "stack target" in drifted[0]
    # A tip driven past the complete female thread and out of the print band.
    deep = violations(top, top - 7.0)
    assert any("complete female thread" in item for item in deep)
    assert any("printed band" in item for item in deep)
    # A mount whose built top is not where the stack says.
    assert any("knife-mount top" in item for item in violations(top + 0.5, 993.5765))


def test_package_appends_the_checks_sheet_after_the_pinned_hanger_sheet() -> None:
    # Sheet 4 must stay the hanger-fit sheet (the MHA-119 note cites it);
    # checks/setup/interfaces live on an appended fifth sheet.
    assert len(draw_summing_assembly.SHEET_NAMES) == 5
    assert draw_summing_assembly.SHEET_NAMES[3] == "HANGER FIT + INSPECTION"
    assert draw_summing_assembly.SHEET_NAMES[4] == "CHECKS + SETUP"
    assert set(draw_summing_assembly.SHEET_SCALES) == set(
        draw_summing_assembly.SHEET_NAMES
    )
    assert set(draw_summing_assembly.SHEET_LAYOUTS) == set(
        draw_summing_assembly.SHEET_NAMES
    )


def test_note_fields_name_every_escaping_edge() -> None:
    field = draw_summing_assembly.NOTE_FIELD_RIGHT
    violations = draw_summing_assembly.note_field_violations
    left, top, right, bottom = field
    assert violations((left, bottom, right, top), field) == []
    escaped = violations((left - 0.01, bottom - 0.01, right + 0.01, top + 0.01), field)
    assert [item.split()[0] for item in escaped] == ["left", "right", "top", "bottom"]
    # Both fields stay clear of the title block and of each other.
    title_top = 0.066
    assert draw_summing_assembly.NOTE_FIELD_RIGHT[3] > title_top
    assert draw_summing_assembly.NOTE_FIELD_LEFT[2] < draw_summing_assembly.NOTE_FIELD_RIGHT[0]


def test_balloon_ring_is_centred_in_its_region_or_refused() -> None:
    region = draw_summing_assembly.EXPLODED_RING_REGION
    shift, overflows = draw_summing_assembly.ring_fit_shift(
        (0.10, 0.10, 0.14, 0.20), region, grow=0.02
    )
    assert overflows == []
    ring = (0.08 + shift[0], 0.08 + shift[1], 0.16 + shift[0], 0.22 + shift[1])
    assert ring[0] - region[0] == pytest.approx(region[2] - ring[2])
    assert ring[1] - region[1] == pytest.approx(region[3] - ring[3])
    _shift, overflows = draw_summing_assembly.ring_fit_shift(
        (0.0, 0.0, 0.2, 0.3), region, grow=0.02
    )
    assert [item.split()[0] for item in overflows] == ["width", "height"]
    # The ring region stays left of the relocated BOM.
    assert region[2] < draw_summing_assembly.BOM_ANCHOR[0]


class _FakeAnnotation:
    def __init__(self, x: float, y: float) -> None:
        self.position = [x, y, 0.0]

    def GetPosition(self) -> tuple[float, float, float]:
        return tuple(self.position)

    def SetPosition(self, x: float, y: float, z: float) -> bool:
        self.position = [x, y, z]
        return True


class _FakeNote:
    """A note whose text box sits off its insertion point, as r10 measured."""

    def __init__(self, text: str, x: float, y: float) -> None:
        self.text = text
        self.annotation = _FakeAnnotation(x, y)
        lines = text.splitlines()
        self.size = (0.0027 * max(map(len, lines)), 0.0045 * len(lines))

    def GetText(self) -> str:
        return self.text

    def GetAnnotation(self) -> _FakeAnnotation:
        return self.annotation

    def GetExtent(self) -> tuple[float, ...]:
        x, y, _z = self.annotation.position
        x0, y1 = x - 0.00028, y + 0.00034
        return (x0, y1 - self.size[1], 0.0, x0 + self.size[0], y1, 0.0)


class _FakeAdapter:
    class currentModel:  # noqa: N801 - mirrors the adapter attribute
        @staticmethod
        def GraphicsRedraw2() -> None:
            return None


def test_note_blocks_anchor_their_rendered_corner_and_report_every_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        draw_summing_assembly,
        "add_note",
        lambda _adapter, text, x, y: _FakeNote(text, x, y),
    )
    field = draw_summing_assembly.NOTE_FIELD_LEFT
    findings = draw_summing_assembly._stack_note_field(
        _FakeAdapter(),
        (("first", "A\nB"), ("second", "C" * 10)),
        field,
        label="test field",
    )
    # r10's insertion-point offset no longer pushes the box out of the field.
    assert findings == []
    too_wide = draw_summing_assembly._stack_note_field(
        _FakeAdapter(),
        (("wide", "W" * 90), ("tall", "\n".join("T" * 50))),
        field,
        label="test field",
    )
    # Every escaping block is reported in one pass, not only the first.
    assert len(too_wide) == 2
    assert "wide leaves its note field: right" in too_wide[0]
    assert "tall leaves its note field: bottom" in too_wide[1]

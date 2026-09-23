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
    """A note whose text box sits off its insertion point and does not follow
    it 1:1 (r10: 0.28/0.34 mm offset; r11: 0.162 mm left after one exact move).
    """

    def __init__(
        self, text: str, x: float, y: float, *, offset: float = 0.0003, gain: float = 0.8
    ) -> None:
        self.text = text
        self.annotation = _FakeAnnotation(x, y)
        self.origin = (x, y)
        self.offset = offset
        self.gain = gain
        lines = text.splitlines()
        self.size = (0.0027 * max(map(len, lines)), 0.0045 * len(lines))

    def GetText(self) -> str:
        return self.text

    def GetAnnotation(self) -> _FakeAnnotation:
        return self.annotation

    def GetExtent(self) -> tuple[float, ...]:
        x, y, _z = self.annotation.position
        x0 = self.origin[0] + self.gain * (x - self.origin[0]) - self.offset
        y1 = self.origin[1] + self.gain * (y - self.origin[1]) + self.offset
        return (x0, y1 - self.size[1], 0.0, x0 + self.size[0], y1, 0.0)


class _FakeAdapter:
    class currentModel:  # noqa: N801 - mirrors the adapter attribute
        @staticmethod
        def GraphicsRedraw2() -> None:
            return None


@pytest.mark.parametrize("offset", (0.0002, 0.0003, 0.0004))
@pytest.mark.parametrize("gain", (1.0, 0.8, 0.5))
def test_note_blocks_stay_inside_their_field_however_the_box_tracks(
    monkeypatch: pytest.MonkeyPatch, offset: float, gain: float
) -> None:
    monkeypatch.setattr(
        draw_summing_assembly,
        "add_note",
        lambda _adapter, text, x, y: _FakeNote(text, x, y, offset=offset, gain=gain),
    )
    field = draw_summing_assembly.NOTE_FIELD_LEFT
    findings = draw_summing_assembly._stack_note_field(
        _FakeAdapter(),
        (("first", "A\nB"), ("second", "C" * 10)),
        field,
        label="test field",
    )
    # The anchor residual is never gated; containment is, and it holds.
    assert findings == []


def test_note_fields_report_every_escaping_block_in_one_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        draw_summing_assembly,
        "add_note",
        lambda _adapter, text, x, y: _FakeNote(text, x, y),
    )
    too_wide = draw_summing_assembly._stack_note_field(
        _FakeAdapter(),
        (("wide", "W" * 90), ("tall", "\n".join("T" * 50))),
        draw_summing_assembly.NOTE_FIELD_LEFT,
        label="test field",
    )
    assert len(too_wide) == 2
    assert "wide leaves its note field: right" in too_wide[0]
    assert "tall leaves its note field: bottom" in too_wide[1]


class _FakeBalloonAnnotation:
    def __init__(self, position: tuple[float, float], attach: tuple[float, float]) -> None:
        self.position = (*position, 0.0)
        self.attach = attach

    def GetPosition(self) -> tuple[float, float, float]:
        return self.position

    def SetPosition(self, x: float, y: float, z: float) -> bool:
        self.position = (x, y, z)
        return True

    def GetLeaderPointsAtIndex(self, _index: int) -> tuple[float, ...]:
        return (self.position[0], self.position[1], 0.0, *self.attach, 0.0)


class _FakeBalloon:
    def __init__(self, name: str, annotation: _FakeBalloonAnnotation) -> None:
        self.name = name
        self.annotation = annotation

    def GetName(self) -> str:
        return self.name

    def GetAnnotation(self) -> _FakeBalloonAnnotation:
        return self.annotation


class _FakeRebuildAdapter:
    class currentModel:  # noqa: N801 - mirrors the adapter attribute
        @staticmethod
        def EditRebuild3() -> bool:
            return True


def test_balloons_on_one_ray_swap_slots_until_their_leaders_clear() -> None:
    # summing-asm-r12: balloons 4 and 5 point at attachments on one vertical
    # ray under the view centre and crossed at (89.6, 94.3) mm.
    four = _FakeBalloonAnnotation((0.1041, 0.0474), (0.0886, 0.0976))
    five = _FakeBalloonAnnotation((0.0909, 0.0457), (0.0889, 0.1210))
    balloons = [_FakeBalloon("4", four), _FakeBalloon("5", five)]
    segments = [draw_summing_assembly._balloon_leader(b.annotation, b.name) for b in balloons]
    assert draw_summing_assembly.find_leader_leader_crossings(segments)
    draw_summing_assembly._uncross_balloon_leaders(
        _FakeRebuildAdapter(), balloons, label="test"
    )
    segments = [draw_summing_assembly._balloon_leader(b.annotation, b.name) for b in balloons]
    assert draw_summing_assembly.find_leader_leader_crossings(segments) == []
    assert four.position[:2] == (0.0909, 0.0457)


def test_balloon_attachment_gate_names_every_mismatch() -> None:
    expected = {"knife-mount": "1", "knife-hanger-washer": "2", "knife-hanger-stud": "3"}
    clean = [
        ("DetailItem1", "1", ("knife-mount",)),
        ("DetailItem2", "2", ("knife-hanger-washer",)),
        ("DetailItem3", "3", ("knife-hanger-stud",)),
    ]
    assert draw_summing_assembly.balloon_attachment_violations(clean, expected) == []
    # Main's r14 reading: item 2's leader ends on the knife block, not a washer.
    misread = [
        ("DetailItem1", "1", ("knife-mount",)),
        ("DetailItem2", "2", ("knife-mount",)),
        ("DetailItem3", "3", ("knife-hanger-stud", "knife-mount")),
    ]
    findings = draw_summing_assembly.balloon_attachment_violations(misread, expected)
    assert findings == [
        "DetailItem2 shows item 2 but attaches to knife-mount (item 1)",
        "DetailItem3 (item 3) attaches to ['knife-hanger-stud', 'knife-mount']",
        "knife-hanger-stud (item 3) carries 0 balloons, expected 1",
        "knife-hanger-washer (item 2) carries 0 balloons, expected 1",
        "knife-mount (item 1) carries 2 balloons, expected 1",
    ]


def test_hanger_section_crop_keeps_one_station_only() -> None:
    # The crop spans one station in z and must stop short of the other one,
    # which sits 2 x HEX_Z_MID away, with room for its own washer (~27 across).
    half = draw_summing_assembly.HANGER_SECTION_CROP_HALF_Z_MM
    assert half >= 27.0 / 2.0 + 5.0
    assert half + 27.0 / 2.0 < 2.0 * build_summing_assembly.HEX_Z_MID


def test_section_crop_gate_accepts_r16_padded_outline_and_refuses_misses() -> None:
    # r16: the crop worked (174 mm two-station section -> one station) but the
    # padded outline read 27.4 mm against the 25.0 mm crop.
    cropped = (0.16985, 0.17574, 0.19721, 0.23323)
    uncropped = (0.05, 0.17, 0.23, 0.235)
    station_x = 0.1835
    check = draw_summing_assembly.section_crop_violations
    assert check(uncropped, cropped, station_x) == []
    assert check(uncropped, uncropped, station_x) == [
        "cropped outline is 180.0 mm wide, not under 0.5 x the uncropped 180.0 mm",
        "cropped outline centre is -43.5 mm off the station",
    ]
    assert check(uncropped, cropped, station_x + 0.010) == [
        "cropped outline centre is -10.0 mm off the station"
    ]

"""Behavioral boundary contract for the summing assembly package."""

import math

import _config
import knife_hanger_interface as hanger
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


def test_stud_fit_note_agrees_with_the_assembly_hanger_fit_reference() -> None:
    hanger_fit_sheet = draw_summing_assembly.SHEET_NAMES[3]
    expected_head = (
        f"FIT SHOULDER TO STACK PER {build_summing_assembly.DRAWING_NUMBER} "
        f"SHEET {draw_summing_assembly.SHEET_NAMES.index(hanger_fit_sheet) + 1}, "
        f"{hanger_fit_sheet}, DETAIL {draw_summing_assembly.HANGER_DETAIL_LABEL}."
    )
    assert knife_hanger_stud_spec.DRAWING_NOTES.splitlines()[0] == expected_head


def test_sheet_four_fit_formula_recovers_the_stud_shoulder_length() -> None:
    # L = T + W + 14.87 - C at the nominal stack is the stud's own shoulder
    # length (the stud slice's SHOULDER_UNDERHEAD_MM), within the printed
    # rounding of the casting-to-knife-line height.
    import build_knife_hanger_washer
    import build_top_frame

    printed = assembly_spec.CASTING_TO_KNIFE_LINE_MM
    assert printed == round(hanger.CASTING_UNDERSIDE_Y - hanger.KNIFE_CONTACT_Y, 2)
    assert f"{printed:.2f} = CASTING UNDERSIDE TO KNIFE LINE." in (
        draw_summing_assembly.HANGER_FIT_CONSTRUCTION
    )
    shoulder = (
        build_top_frame.RING_HEIGHT
        + build_knife_hanger_washer.THICKNESS
        + printed
        - hanger.KNIFE_BORE_CROWN_DEPTH_MM
    )
    assert shoulder == pytest.approx(
        knife_hanger_stud_spec.SHOULDER_UNDERHEAD_MM, abs=0.005
    )


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


def _joint(
    *,
    seat_gap: float = 0.0,
    tip_length: float = hanger.STUD_TIP_LENGTH_MM,
    chamfer: float = hanger.STUD_TIP_CHAMFER_MAX_MM,
    mount_top: float = hanger.SHOULDER_SEAT_Y,
    boss_radius: float = hanger.BOSS_DIA_MM / 2.0,
    shank_radius: float = 6.35,
) -> build_summing_assembly.HangerJointReading:
    """A synthetic option-D joint's axis circles, read like the built B-rep.

    The turned tip models no runout: its thread-major circles are the shoulder
    junction and the chamfer start.
    """
    major = hanger.THREAD_MAJOR_DIA_MM / 2.0
    shoulder = mount_top + seat_gap
    tip = shoulder - tip_length
    stud = [
        (shoulder + 30.0, shank_radius),
        (shoulder, shank_radius),
        (shoulder, major),
        (tip + chamfer, major),
        (tip, major - chamfer),
    ]
    mount = [
        (mount_top, boss_radius),
        (mount_top - hanger.BOSS_HEIGHT_MM, boss_radius),
        (mount_top, hanger.TAP_DRILL_DIA_MM / 2.0 + hanger.TAP_MOUTH_EDGE_BREAK_MM),
        (mount_top - hanger.TAP_DRILL_DEPTH_MM, hanger.TAP_DRILL_DIA_MM / 2.0),
    ]
    return build_summing_assembly.read_hanger_joint(
        ("knife-mount-1", mount), ("knife-hanger-stud-1", stud), label="test"
    )


def test_built_hanger_joint_measures_full_thread_inside_the_full_tap() -> None:
    violations = build_summing_assembly.hanger_joint_violations
    nominal = _joint()
    assert nominal.shoulder_y == nominal.mount_top_y == hanger.SHOULDER_SEAT_Y
    assert nominal.boss_radius == hanger.BOSS_DIA_MM / 2.0
    assert nominal.shank_radius == 6.35
    # Die runout beside the shoulder and the tip chamfer are not engagement.
    assert nominal.engagement == pytest.approx(
        hanger.STUD_TIP_LENGTH_MM
        - hanger.STUD_TIP_CHAMFER_MAX_MM
        - hanger.STUD_THREAD_RELIEF_MAX_MM
    )
    assert violations(nominal) == []
    short = _joint(
        tip_length=hanger.REQUIRED_ENGAGEMENT_MM
        + hanger.STUD_TIP_CHAMFER_MAX_MM
        + hanger.STUD_THREAD_RELIEF_MAX_MM
        - 0.01
    )
    assert [item for item in violations(short) if "full-thread engagement" in item]


def test_built_hanger_joint_refuses_unseated_deep_or_misplaced_studs() -> None:
    violations = build_summing_assembly.hanger_joint_violations
    proud = violations(_joint(seat_gap=0.2))
    assert any("not seated" in item for item in proud)
    deep = violations(_joint(tip_length=hanger.TAP_THREAD_DEPTH_MIN_MM + 0.2))
    assert any("usable tap thread" in item for item in deep)
    low_mount = violations(_joint(mount_top=hanger.SHOULDER_SEAT_Y - 0.5))
    assert any("seat plane" in item for item in low_mount)


def test_built_hanger_joint_holds_the_boss_and_shank_clear_of_the_casting_hole() -> None:
    violations = build_summing_assembly.hanger_joint_violations
    hole = hanger.CASTING_STUD_HOLE_DIA_MM / 2.0
    # A boss 0.1 mm wider in radius than the interface's leaves < 1.5 mm at
    # its maximum size.
    fat_boss = violations(_joint(boss_radius=hanger.BOSS_DIA_MM / 2.0 + 0.1))
    assert any("clears the casting hole" in item for item in fat_boss)
    assert violations(_joint(shank_radius=hole)) and any(
        "does not clear" in item for item in violations(_joint(shank_radius=hole))
    )


def test_built_hanger_joint_names_the_circles_when_the_stud_is_unreadable() -> None:
    with pytest.raises(RuntimeError, match="thread-major circle"):
        build_summing_assembly.read_hanger_joint(
            ("knife-mount-1", [(1004.65, 4.75)]),
            ("knife-hanger-stud-1", [(1004.65, 6.35), (994.25, 1.9)]),
            label="test",
        )


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


# Each non-summing contract set, digested BEFORE summing took ownership of its
# own pairs (integration, 2026-09-23): sorted (pair, limit rounded to 1e-9).
_OTHER_CONTRACT_DIGESTS = {
    "drive-train": (8, "e6815d6a66052a05"),
    "frame": (17, "4677d25965fb6fd2"),
    "magnifier": (3, "4fdafd77e003d5c6"),
    "pen": (2, "c859c793ecd100ba"),
    "paper-drive": (29, "f47dafd2222d6d9d"),
    "harmonic-analyzer": (32, "516c3ab72f513a2d"),
}


def test_summing_owning_its_contract_leaves_the_other_assemblies_unchanged() -> None:
    import hashlib

    import _interference_contracts

    for name, (count, digest) in _OTHER_CONTRACT_DIGESTS.items():
        items = sorted(
            (tuple(sorted(pair)), round(limit, 9))
            for pair, limit in _interference_contracts.allowed_interference_pairs(
                name
            ).items()
        )
        assert (len(items), hashlib.sha256(repr(items).encode()).hexdigest()[:16]) == (
            count,
            digest,
        ), name


def test_summing_contract_is_loaded_by_name_and_kept_out_of_other_recipes() -> None:
    from pathlib import Path

    import _interference_contracts
    import summing_interference_contract
    from _buildgraph import module_deps_of

    # The gate and the soundness leaf read the same summing-owned pairs.
    assert (
        _interference_contracts.allowed_interference_pairs("summing")
        is summing_interference_contract.ALLOWED_PAIRS
    )
    assert (
        build_summing_assembly.ALLOWED_INTERFERENCE
        is summing_interference_contract.ALLOWED_PAIRS
    )
    limit = summing_interference_contract.HANGER_TIP_THREAD_LIMIT_MM3
    assert limit == pytest.approx(
        1.10 * math.pi * (hanger.THREAD_MAJOR_DIA_MM**2 - hanger.TAP_DRILL_DIA_MM**2)
        * hanger.STUD_TIP_LENGTH_MM / 4.0
    )
    scripts = Path(build_summing_assembly.__file__).parent
    owned = {"knife_hanger_interface.py", "summing_interference_contract.py"}
    for stem in (
        "drive_train",
        "frame",
        "harmonic_analyzer",
        "magnifier",
        "paper_drive",
        "pen",
    ):
        deps = {Path(dep).name for dep in module_deps_of(scripts / f"build_{stem}_assembly.py")}
        assert "_interference_contracts.py" in deps, stem
        assert not deps & owned, (stem, sorted(deps & owned))
    summing = {
        Path(dep).name for dep in module_deps_of(scripts / "build_summing_assembly.py")
    }
    assert owned <= summing


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


def test_detail_fence_is_found_by_the_view_it_owns(monkeypatch) -> None:
    # r17: cropping section A-A added its crop profile to GetDetailCircles.
    from types import SimpleNamespace

    monkeypatch.setattr(draw_summing_assembly, "_early_bound", lambda obj, _iface: obj)

    def view(name):
        return SimpleNamespace(GetName2=lambda: name)

    def circle(name, label, owned):
        return SimpleNamespace(
            GetName=lambda: name, GetLabel=lambda: label, GetDetailView=lambda: owned
        )

    detail = view("Drawing View9")
    fence = circle("Detail Circle1", "B", detail)
    crop = circle("Crop1", "", None)
    parent = SimpleNamespace(GetDetailCircles=lambda: (crop, fence))
    assert draw_summing_assembly._detail_fence_of(parent, detail) is fence
    with pytest.raises(RuntimeError, match="0 fences own detail 'Drawing View9'"):
        draw_summing_assembly._detail_fence_of(
            SimpleNamespace(GetDetailCircles=lambda: (crop,)), detail
        )


def test_seat_plane_edge_prefers_the_mount_then_falls_back_and_reports(monkeypatch) -> None:
    # summing-integration-b2: the front detail offered the stud no circle, so C
    # reads the seat plane from the MHA-037 boss rim first.
    tried = []

    def fake_circle(_view, *, component_stem, height_mm, radius_mm, target_z_mm, label):
        tried.append((component_stem, radius_mm))
        assert height_mm == hanger.SHOULDER_SEAT_Y
        if component_stem == "knife-hanger-stud" and radius_mm is None:
            return "stud-rim"
        raise RuntimeError(f"{label}: none")

    monkeypatch.setattr(draw_summing_assembly, "_visible_component_circle", fake_circle)
    monkeypatch.setattr(
        draw_summing_assembly, "_visible_edge_census", lambda _view, _stems: ["x line"]
    )
    assert draw_summing_assembly._seat_plane_edge(object(), 0.0) == "stud-rim"
    assert tried == [
        ("knife-mount", hanger.BOSS_DIA_MM / 2.0),
        ("knife-hanger-stud", draw_summing_assembly.STUD_SHANK_DIA / 2.0),
        ("knife-mount", None),
        ("knife-hanger-stud", None),
    ]

    monkeypatch.setattr(
        draw_summing_assembly,
        "_visible_component_circle",
        lambda *_a, **kw: (_ for _ in ()).throw(RuntimeError(kw["label"] + ": none")),
    )
    with pytest.raises(RuntimeError, match=r"census \(1 edges\): x line"):
        draw_summing_assembly._seat_plane_edge(object(), 0.0)


def test_hanger_engagement_is_measured_from_the_boss_top_seat_not_the_block() -> None:
    # knife CodeRabbit (2x major): under option D the tap mouth is the boss-top
    # seat, 6.0 above the block top. The static stack's E = seat - tip must be
    # the stud's 10.40 tip inside [1.5D, usable thread], and the built judge
    # must refuse a joint read from the block-top datum (negative control).
    engagement = build_summing_assembly.HANGER_SHOULDER_Y - build_summing_assembly.HANGER_TIP_Y
    assert build_summing_assembly.HANGER_SHOULDER_Y == pytest.approx(hanger.SHOULDER_SEAT_Y)
    assert engagement == pytest.approx(hanger.STUD_TIP_LENGTH_MM)
    assert hanger.REQUIRED_ENGAGEMENT_MM <= engagement <= hanger.TAP_THREAD_DEPTH_MIN_MM
    assert hanger.SHOULDER_SEAT_Y - hanger.MOUNT_BLOCK_TOP_Y == pytest.approx(
        hanger.BOSS_HEIGHT_MM
    )
    violations = build_summing_assembly.hanger_joint_violations
    assert violations(_joint()) == []
    block_datum = violations(_joint(mount_top=hanger.MOUNT_BLOCK_TOP_Y))
    assert any("is not the seat plane" in item for item in block_datum)


class _CensusFeature:
    def __init__(self, name: str, type_name: str, visible: int, following=None):
        self.Name = name
        self._type = type_name
        self.Visible = visible
        self._next = following

    def GetTypeName2(self) -> str:
        return self._type

    def GetNextFeature(self):
        return self._next


class _CensusAdapter:
    @staticmethod
    def _attempt(fn, default=None):
        try:
            return fn()
        except Exception:
            return default


def test_visible_reference_census_names_only_shown_sketches_and_reference_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Main ruling 2026-09-24: the lever's SummationArcReference point and
    # BossAxialReference line drew in the summing isometric. The census must
    # name exactly the shown sketch/reference rows, owner-qualified.
    monkeypatch.setattr(build_summing_assembly, "_early_bound", lambda obj, _iface: obj)
    chain = None
    for name, type_name, visible in reversed(
        (
            ("Front Plane", "RefPlane", 1),
            ("Boss", "Extrusion", 2),
            ("SummationArcReference", "ProfileFeature", 2),
            ("BossAxialReference", "ProfileFeature", 2),
            ("KnifeEnvelopeReference", "ProfileFeature", 1),
            ("knife axis", "RefAxis", 2),
        )
    ):
        chain = _CensusFeature(name, type_name, visible, chain)
    rows = build_summing_assembly._feature_rows(_CensusAdapter(), "summing-lever-1", chain)
    assert len(rows) == 6
    assert build_summing_assembly.visible_reference_names(rows) == [
        "SummationArcReference@summing-lever-1",
        "BossAxialReference@summing-lever-1",
        "knife axis@summing-lever-1",
    ]
    # Assembly-level rows carry no owner; a shown non-reference feature and an
    # unknown visibility state never count.
    assert build_summing_assembly.visible_reference_names(
        [("", "PatternAxisX", "RefAxis", 2), ("", "Mates", "MateGroup", 2),
         ("", "Plane1", "RefPlane", 3)]
    ) == ["PatternAxisX"]

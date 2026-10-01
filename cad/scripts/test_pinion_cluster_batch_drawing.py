"""Cross-sheet offline contracts for the pinion-cluster drawings."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path

import pytest

import _assembly
import _config
import _interference_contracts
import crank_handle_spec
import pinion_bracket_spec
import pinion_cam_pin_spec
import pinion_cam_spec
import pinion_handle_spec
import pinion_lever_pin_spec
import pinion_lever_spec
import pinion_pivot_shaft_spec
import pinion_spring_spec
import post_mount_screw_spec
from _buildgraph import module_deps_of


SHEETS = (
    ("crank-handle", crank_handle_spec),
    ("pinion-bracket", pinion_bracket_spec),
    ("pinion-cam", pinion_cam_spec),
    ("pinion-cam-pin", pinion_cam_pin_spec),
    ("pinion-handle", pinion_handle_spec),
    ("pinion-lever", pinion_lever_spec),
    ("pinion-lever-pin", pinion_lever_pin_spec),
    ("pinion-pivot-shaft", pinion_pivot_shaft_spec),
    ("pinion-spring", pinion_spring_spec),
)

TITLE_BLOCK_OWNED_NOTE_TEXT = (
    "ALL DIMENSIONS",
    "BREAK EDGES",
    "BREAK SHARP",
    "DEBUR",
    "EDGE BREAK",
    "FINISH:",
    "GENERAL TOLERANCE",
    "MATERIAL:",
    "REMOVE BURR",
    "SHARP EDGES",
    "U.O.S.",
    "UNLESS OTHERWISE SPECIFIED",
    " UOS",
)


def test_notes_do_not_repeat_title_block_metadata() -> None:
    for part_name, spec in SHEETS:
        # A sheet with no notes (MHA-135, rule 6) has nothing to repeat.
        notes = getattr(spec, "DRAWING_NOTES", "").upper()
        for duplicate in TITLE_BLOCK_OWNED_NOTE_TEXT:
            assert duplicate not in notes, f"{part_name}: {duplicate}"


def test_finish_field_does_not_repeat_generic_edge_break_instruction() -> None:
    for part_name, _spec in SHEETS:
        finish = str(_config.parts(part_name)["finish"]).upper()
        assert "DEBUR" not in finish, part_name
        assert "REMOVE BURR" not in finish, part_name
        assert "BREAK SHARP" not in finish, part_name


def test_part_numbers_are_unique_across_the_complete_registry() -> None:
    by_number: dict[str, list[str]] = {}
    for part_name, part in _config.parts().items():
        by_number.setdefault(str(part["number"]), []).append(part_name)

    duplicates = {
        number: names for number, names in by_number.items() if len(names) > 1
    }
    assert duplicates == {}


def test_complete_parts_registry_returns_independent_rows() -> None:
    registry = _config.parts()
    row = registry["arbor-pedestal"]
    row["_mutation_probe"] = True
    try:
        assert "_mutation_probe" not in _config.parts("arbor-pedestal")
    finally:
        row.pop("_mutation_probe", None)


def test_new_pin_and_spring_numbers_use_reserved_unique_allocations() -> None:
    assert _config.parts("pinion-cam-pin")["number"] == "MHA-116"
    assert _config.parts("pinion-spring")["number"] == "MHA-114"


def test_drawing_notes_do_not_change_the_drive_train_recipe() -> None:
    scripts = Path(__file__).resolve().parent
    deps = {
        Path(path).name
        for path in module_deps_of(scripts / "build_drive_train_assembly.py")
    }
    drawing_only = {
        "pinion_arbor_spec.py",
        "pinion_cam_spec.py",
        "pinion_cam_pin_spec.py",
        "pinion_handle_spec.py",
        "pinion_lever_spec.py",
        "pinion_spring_spec.py",
    }
    assert deps.isdisjoint(drawing_only)
    assert {
        "pinion_arbor_geometry.py",
        "pinion_cam_geometry.py",
        "pinion_cam_pin_geometry.py",
        "pinion_handle_geometry.py",
        "pinion_lever_geometry.py",
        "pinion_spring_geometry.py",
    } <= deps


class _InterferenceComponent:
    def __init__(self, name: str) -> None:
        self.Name2 = name
        self.ReferencedConfiguration = ""


class _Interference:
    def __init__(self, names: tuple[str, str], volume_mm3: float) -> None:
        self.Components = [_InterferenceComponent(name) for name in names]
        self.Volume = volume_mm3 / 1e9


class _InterferenceManager:
    def __init__(self, *interferences: _Interference) -> None:
        self._interferences = list(interferences)

    def GetInterferences(self) -> list[_Interference]:
        return self._interferences

    def Done(self) -> None:
        pass


class _InterferenceAssembly:
    def __init__(self, *interferences: _Interference) -> None:
        self.InterferenceDetectionManager = _InterferenceManager(*interferences)

    def ToolsCheckInterference(self) -> None:
        pass


class _InterferenceAdapter:
    def __init__(self, *interferences: _Interference) -> None:
        self.currentModel = _InterferenceAssembly(*interferences)

    @staticmethod
    def _attempt(action, *, default=None):
        try:
            return action()
        except Exception:
            return default


def test_intentional_fit_allowance_is_pair_and_volume_bounded(monkeypatch) -> None:
    pair = ("pinion-bracket-1", "pinion-cam-pin-1")
    monkeypatch.setattr(_assembly, "_early_bound", lambda obj, *_args: obj)

    events: list[tuple[str, dict]] = []
    infos: list[str] = []
    monkeypatch.setattr(
        _assembly._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    monkeypatch.setattr(_assembly._telemetry, "info", infos.append)
    adapter = _InterferenceAdapter(_Interference(pair, 0.37))
    _assembly.check_no_interference(
        adapter,
        allowed_pairs={frozenset(pair): 0.45},
    )
    # The reading reaches an info-level farm task.log and the trace: a bounded
    # limit is calibrated from it (#838: no leaf had ever recorded one).
    [(name, attrs)] = events
    assert name == "interference.bounded_pair"
    assert attrs["pair"] == list(pair)
    assert attrs["overlap_mm3"] == pytest.approx(0.37)
    assert attrs["body_count"] == 1
    assert attrs["limit_mm3"] == 0.45
    assert any(
        "overlap 0.3700 mm^3 over 1 bodies allowed (limit 0.4500 mm^3)" in line
        for line in infos
    )

    with pytest.raises(RuntimeError, match="0.46 mm\\^3"):
        _assembly.check_no_interference(
            _InterferenceAdapter(_Interference(pair, 0.46)),
            allowed_pairs={frozenset(pair): 0.45},
        )

    with pytest.raises(RuntimeError, match="pinion-cam-pin-2"):
        _assembly.check_no_interference(
            _InterferenceAdapter(
                _Interference(("pinion-bracket-1", "pinion-cam-pin-2"), 0.37)
            ),
            allowed_pairs={frozenset(pair): 0.45},
        )


def test_intentional_fit_allowance_bounds_the_pair_total(monkeypatch) -> None:
    """#853: a pair split into several bodies is bounded by its TOTAL overlap.

    662e4db1's adjuster/block thread annulus came back as 13 bodies, each
    compared alone against the pair limit; a split pair whose every body is
    under the limit but whose sum is over it passed.
    """
    pair = ("cone-tip-block-1", "cone-tip-adjuster-1")
    monkeypatch.setattr(_assembly, "_early_bound", lambda obj, *_args: obj)
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        _assembly._telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    limit = {frozenset(pair): 1.0}

    # Three bodies, each under the limit, 1.2 in total: a hard fault.
    over = [_Interference(pair, 0.4) for _ in range(3)]
    with pytest.raises(RuntimeError, match=r"1.2 mm\^3 over 3 bodies"):
        _assembly.check_no_interference(_InterferenceAdapter(*over), allowed_pairs=limit)

    # Under the limit both per body and in total: allowed, reported as one pair.
    events.clear()
    under = [_Interference(pair, 0.3), _Interference(tuple(reversed(pair)), 0.3)]
    _assembly.check_no_interference(_InterferenceAdapter(*under), allowed_pairs=limit)
    [(name, attrs)] = events
    assert name == "interference.bounded_pair"
    assert attrs["overlap_mm3"] == pytest.approx(0.6)
    assert attrs["body_count"] == 2


def _annulus_limit(major_d: float, tap_d: float, length: float) -> float:
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _press_fit_shell_limit(
    outer_d: float,
    bore_d: float,
    host_chord: float,
) -> float:
    return math.pi * (outer_d**2 - bore_d**2) * host_chord / 4.0


def _expected_numbered_pairs(
    first_stem: str,
    numbers: Iterable[int],
    second_stem: str,
    major_d: float,
    tap_d: float,
    length: float,
    *,
    second_number: int | None = 1,
) -> dict[frozenset[str], float]:
    limit = _annulus_limit(major_d, tap_d, length)
    return {
        frozenset(
            (
                f"{first_stem}-{number}",
                f"{second_stem}-{number if second_number is None else second_number}",
            )
        ): limit
        for number in numbers
    }


def test_cross_numbered_fit_pairs_use_fixed_runtime_oracles() -> None:
    paper_drive = _interference_contracts.allowed_interference_pairs("paper-drive")
    clamp_receivers = {1: 2, 2: 2, 3: 1, 4: 1}
    for screw_number, back_number in clamp_receivers.items():
        pair = frozenset(
            (f"clamp-screw-{screw_number}", f"column-clamp-back-{back_number}")
        )
        assert paper_drive[pair] == pytest.approx(42.217366426182714)

    guide_receivers_and_limits = {
        5: (1, 13.56562270743475),
        6: (2, 13.56562270743475),
        7: (1, 13.56562270743475),
        8: (2, 13.56562270743475),
        9: (1, 13.56562270743475),
        10: (2, 13.56562270743475),
        11: (1, 13.56562270743475),
        12: (2, 13.56562270743475),
        13: (1, 13.56562270743475),
        14: (2, 13.56562270743475),
    }
    for screw_number, (guide_number, limit) in guide_receivers_and_limits.items():
        pair = frozenset(
            (f"fillister-screw-{screw_number}", f"platen-guide-{guide_number}")
        )
        assert paper_drive[pair] == pytest.approx(limit)
    # R9-31: the lock-plate screws are MHA-176 button heads, not fillisters.
    lock_receivers = {1: 1, 2: 1, 3: 2, 4: 1, 5: 2, 6: 2, 7: 1, 8: 2}
    for screw_number, guide_number in lock_receivers.items():
        pair = frozenset(
            (f"guide-lock-screw-{screw_number}", f"platen-guide-{guide_number}")
        )
        assert paper_drive[pair] == pytest.approx(11.20210690940073)

    summing = _interference_contracts.allowed_interference_pairs("summing")
    assert summing == pytest.approx(
        {
            frozenset(("knife-hanger-stud-1", "knife-mount-1")): 456.48979768633853,
            frozenset(("knife-hanger-stud-2", "knife-mount-2")): 456.48979768633853,
            # 9490T1 #10-24 through the 0.75-in boss; #25 tap drill.
            frozenset(("boss-hook-1", "summing-lever-1")): _annulus_limit(
                4.826, 3.797, 19.05
            ),
        }
    )


def test_drive_train_interference_contracts_use_fixed_runtime_oracles() -> None:
    threaded_by_assembly = {
        "drive-train": {
            # mha092-r3-8b1b drive-train leaf: 16.4412 and 7.8008 observed,
            # plus ten percent.
            frozenset(("cone-tip-adjuster-1", "cone-tip-block-1")): 18.08532,
            frozenset(("cone-tip-pinch-screw-1", "cone-tip-block-1")): 8.58088,
            # First prism-block drive-train leaf: 5.6585 observed, plus ten
            # percent.
            frozenset(("cone-tip-block-screw-1", "cone-tip-block-1")): 6.22435,
            # 1/16 in tip land: 0.13 observed at Ø0.79, scaled by r^3 (x8).
            frozenset(("cone-tip-adjuster-1", "cone-gear-shaft-1")): 1.144,
            frozenset(("fillister-screw-1", "crank-arm-1")): _annulus_limit(
                2.8448, 2.261, 5.33
            ),
            # MHA-139 #4-40 major 2.845 in the #43 tap drill 2.261: 6.5 of
            # full thread past the 1.5 relief plus the lead cone, within 7.0.
            frozenset(("crank-handle-pivot-screw-1", "crank-arm-1")): _annulus_limit(
                2.845, 2.261, 7.0
            ),
            # U30 I22: each MHA-142 1/4-20 in its #7 MHA-091 tap, its cut
            # length past the post's grip deep.
            **_expected_numbered_pairs(
                "post-mount-screw",
                (1, 2),
                "cone-swing-platform",
                6.35,
                5.105,
                post_mount_screw_spec.CUT_LENGTH_MM - post_mount_screw_spec.GRIP_MM,
            ),
            # R1: MHA-058 is a bonded slip fit modelled line to line in the
            # MHA-102 cross-hole, so the pair needs no interference allowance.
            # #743 Q3: MHA-147 #4-40 x 1/4 in each pedestal crown tap (the
            # _hole_spec major 2.845 in the #43 tap drill, over its length).
            **_expected_numbered_pairs(
                "arbor-set-screw",
                range(1, 3),
                "arbor-pedestal",
                2.845,
                2.261,
                6.35,
                second_number=None,
            ),
            # CONTRACT-crank: 2x MHA-173 3/32 dowel (2.38125) pressed into
            # MHA-026's 2.38 reamed collar holes, 3.95 deep.
            **_expected_numbered_pairs(
                "crank-seat-drive-pin",
                range(1, 3),
                "crankshaft",
                2.38125,
                2.38,
                3.95,
            ),
        },
        "frame": {
            **_expected_numbered_pairs(
                "lag-screw",
                range(1, 5),
                "harmonic-base",
                6.35,
                5.105,
                12.4221875,
            ),
            # MHA-132 / 90280A837: #10-32 major 4.826, #21 drill 4.0386.
            # The 44.45-mm shank crosses a 25.5-mm socket. Its shortest
            # socket chord is 25.039163803929238 mm at the major envelope,
            # leaving at most 19.410836196070765 mm in both casting walls.
            **_expected_numbered_pairs(
                "frame-cross-screw",
                range(1, 5),
                "harmonic-base",
                4.826,
                4.0386,
                19.410836196070765,
            ),
            **_expected_numbered_pairs(
                "frame-cross-screw",
                range(5, 9),
                "top-frame",
                4.826,
                4.0386,
                19.410836196070765,
            ),
            frozenset(("gooseneck-set-screw-1", "top-frame-1")): _annulus_limit(
                6.35, 5.105, 6.95
            ),
            **_expected_numbered_pairs(
                "fillister-screw",
                range(1, 5),
                "harmonic-base",
                2.8448,
                2.261,
                4.85,
            ),
        },
        "magnifier": {
            **_expected_numbered_pairs(
                "clamp-screw",
                range(1, 3),
                "column-clamp-back",
                4.1656,
                3.454,
                4.85,
            ),
            frozenset(("thumb-screw-1", "magnifying-clamp-1")): _annulus_limit(
                2.8448, 2.261, 3.9
            ),
        },
        "summing": {
            **_expected_numbered_pairs(
                "knife-hanger-stud",
                range(1, 3),
                "knife-mount",
                12.7,
                10.716,
                11.3735,
                second_number=None,
            ),
            # Stock 9490T1: #10-24 major, #25 drill, 0.75-in boss engagement.
            frozenset(("boss-hook-1", "summing-lever-1")): _annulus_limit(
                4.826, 3.797, 19.05
            ),
        },
        "pen": {
            frozenset(("pen-set-screw-1", "pen-frame-1")): _annulus_limit(
                2.8448, 2.261, 5.0
            ),
            frozenset(("hanger-screw-1", "pen-hanger-1")): _annulus_limit(
                4.1656, 3.454, 3.0
            ),
        },
        "paper-drive": {
            **_expected_numbered_pairs(
                "clamp-screw",
                range(1, 3),
                "column-clamp-back",
                4.1656,
                3.454,
                9.0124,
                second_number=2,
            ),
            **_expected_numbered_pairs(
                "clamp-screw",
                range(3, 5),
                "column-clamp-back",
                4.1656,
                3.454,
                9.0124,
            ),
            **_expected_numbered_pairs(
                "fillister-screw",
                range(1, 5),
                "platen",
                2.8448,
                2.261,
                4.0,
            ),
            **_expected_numbered_pairs(
                "fillister-screw",
                range(5, 15, 2),
                "platen-guide",
                2.8448,
                2.261,
                5.2678,
            ),
            **_expected_numbered_pairs(
                "fillister-screw",
                range(6, 15, 2),
                "platen-guide",
                2.8448,
                2.261,
                5.2678,
                second_number=2,
            ),
            **_expected_numbered_pairs(
                "guide-lock-screw",
                (1, 2, 4, 7),
                "platen-guide",
                2.8448,
                2.261,
                4.35,
            ),
            **_expected_numbered_pairs(
                "guide-lock-screw",
                (3, 5, 6, 8),
                "platen-guide",
                2.8448,
                2.261,
                4.35,
                second_number=2,
            ),
            # Round 10 transgear: stock #8-32 / #4-40 / #0-80 screws, the
            # MHA-082 stud's #10-32 and #6-32, and the MHA-126 1/4-20 nut.
            **_expected_numbered_pairs(
                "transgear-arm-plate-screw",
                range(1, 3),
                "transgear-arm",
                4.1656,
                3.454,
                7.7,
            ),
            frozenset(("transgear-pivot-screw-1", "support-bar-1")): _annulus_limit(
                4.1656, 3.454, 3.5687
            ),
            **_expected_numbered_pairs(
                "latch-hook-bracket-screw",
                range(1, 3),
                "support-bar",
                2.8448,
                2.261,
                8.025,
            ),
            frozenset(("transgear-stub-1", "transgear-arm-1")): _annulus_limit(
                4.826, 4.0386, 7.9375
            ),
            frozenset(("transgear-hub-cap-1", "transgear-stub-1")): _annulus_limit(
                3.505, 2.705, 4.7
            ),
            **_expected_numbered_pairs(
                "transgear-disc-screw",
                range(1, 4),
                "rack-pinion",
                1.524,
                1.191,
                3.0,
            ),
            frozenset(
                ("transgear-knob-retaining-screw-1", "transgear-knob-shaft-1")
            ): _annulus_limit(4.1656, 3.454, 8.5125),
            # R9-35: flush-head seat slivers, observed + 10 %.
            frozenset(("transgear-arm-plate-screw-1", "transgear-arm-plate-1")): (
                1.10 * 0.00809042475
            ),
            frozenset(("transgear-arm-plate-screw-2", "transgear-arm-plate-1")): (
                1.10 * 0.00809042475
            ),
            frozenset(("transgear-knob-retaining-screw-1", "transgear-knob-cup-1")): (
                1.10 * 5.26003719e-05
            ),
            frozenset(
                ("transgear-thumbnut-1", "transgear-knob-shaft-1")
            ): _annulus_limit(6.35, 5.105, 14.9),
            # MHA-155 3/32 x 3/16 dowels pressed 2.3625 into MHA-152's 2.38 reams.
            **_expected_numbered_pairs(
                "transgear-knob-drive-pin",
                range(1, 3),
                "transgear-drive-collar",
                2.38125,
                2.38,
                2.3625,
            ),
        },
        "harmonic-analyzer": {
            # Twenty stock 9489T111 #6-32 anchors engage only the 0.2-in
            # summing-lever plate; #36 tap drill, not the full stock shank.
            **_expected_numbered_pairs(
                "channel-1/spring-hook",
                range(1, 21),
                "summing-1/summing-lever",
                3.5052,
                2.705,
                5.08,
            ),
            frozenset(
                (
                    "frame-1/harmonic-base-1",
                    "drive-train-1/cone-pivot-screw-1",
                )
            ): _annulus_limit(4.826, 3.797, 9.525),
            **_expected_numbered_pairs(
                "drive-train-1/cone-lock-knob",
                range(1, 2),
                "frame-1/harmonic-base",
                6.35,
                5.105,
                12.7,
            ),
            **_expected_numbered_pairs(
                "drive-train-1/swing-stop-screw",
                range(1, 2),
                "frame-1/harmonic-base",
                2.8448,  # the foot screw's #4-40 SKU, seated full length
                2.261,
                9.525,
            ),
            **_expected_numbered_pairs(
                "drive-train-1/slotted-screw",
                range(1, 5),
                "frame-1/harmonic-base",
                4.1656,
                3.454,
                11.25,  # rule 12 E10: #8-32 x 1-1/4 through the 20.5 block
            ),
            **_expected_numbered_pairs(
                "drive-train-1/foot-screw",
                range(1, 2),
                "frame-1/harmonic-base",
                2.8448,
                2.261,
                8.725,
            ),
            # U34c: MHA-143 #8-32 x 3/4 through the 5.0 pedestal ledge.
            **_expected_numbered_pairs(
                "drive-train-1/pedestal-hold-down-screw",
                range(1, 3),
                "frame-1/harmonic-base",
                4.1656,
                3.454,
                14.05,
            ),
            **_expected_numbered_pairs(
                "channel-1/frame-side-screw",
                range(1, 3),
                "frame-1/top-frame",
                4.1656,
                3.454,
                8.6624,
            ),
            # #743 PR2: MHA-143 #8-32 x 3/4 through the 6.0 rocker-bracket foot.
            **_expected_numbered_pairs(
                "channel-1/pedestal-hold-down-screw",
                range(1, 5),
                "frame-1/rocker-arm-support",
                4.1656,
                3.454,
                13.05,
            ),
        },
    }
    # U27 (Main, 2026-09-23): the follower studs slip line-to-line into
    # their H7 seats and are bonded, so the drive train allows them NO
    # overlap -- the former press allowance is gone.
    cam_pairs = {
        frozenset(("pinion-bracket-1", "pinion-cam-pin-1")),
        frozenset(("pinion-bracket-2", "pinion-cam-pin-2")),
    }
    crank_pairs = {
        frozenset(("crank-pin-1", "crank-hub-1")),
        frozenset(("crank-pin-1", "crankshaft-1")),
    }
    # MHA-154's tube pin across MHA-078's unmodelled cross hole.
    cross_pin_pair = frozenset(
        ("transgear-collar-cross-pin-1", "transgear-knob-shaft-1")
    )
    special_pairs = {
        "drive-train": crank_pairs,
        "paper-drive": {cross_pin_pair},
    }
    for name, expected_threaded in threaded_by_assembly.items():
        allowed = _interference_contracts.allowed_interference_pairs(name)
        # Exact pair equality also forbids tube/screw and cap/tube exemptions.
        assert set(allowed) == set(expected_threaded) | special_pairs.get(name, set())
        for pair, expected_limit in expected_threaded.items():
            assert allowed[pair] == pytest.approx(expected_limit)
        assert all(limit > 0.0 and math.isfinite(limit) for limit in allowed.values())

    drive_train_allowed = _interference_contracts.allowed_interference_pairs(
        "drive-train"
    )
    assert not cam_pairs & set(drive_train_allowed)
    crank_allowed = _interference_contracts.allowed_interference_pairs("drive-train")
    hub_pair = frozenset(("crank-pin-1", "crank-hub-1"))
    shaft_pair = frozenset(("crank-pin-1", "crankshaft-1"))
    # The CONTRACT-crank hub barrel (Ø22.25 since R9-38) sets the MHA-024
    # pilot spans: a longer hub chord, and the shaft crossing further down
    # the taper. #1140 stood the pin 0.6 further proud (PIN_PROUD 4.45,
    # keeper-ring hole at 3.7), so a thinner stretch of the taper sits in
    # both receivers.
    assert 111.2 < crank_allowed[hub_pair] < 111.8
    assert 55.1 < crank_allowed[shaft_pair] < 55.6
    # 1.10 x (12.470 - 4.755): the Ø1.5875 and Ø0.978 chords through Ø6.35.
    paper_allowed = _interference_contracts.allowed_interference_pairs("paper-drive")
    assert 8.4 < paper_allowed[cross_pin_pair] < 8.6
    assert _interference_contracts.allowed_interference_pairs("channel") == {}
    assert _interference_contracts.allowed_interference_pairs("unknown") == {}

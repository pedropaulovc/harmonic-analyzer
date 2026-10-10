"""Cross-sheet offline contracts for the pinion-cluster drawings."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path

import pytest

import _assembly
import _config
import _interference_contracts
import dt_crank_handle_spec
import dt_pinion_bracket_spec
import dt_pinion_cam_pin_spec
import dt_pinion_cam_spec
import dt_pinion_handle_spec
import dt_pinion_lever_pin_spec
import dt_pinion_lever_spec
import dt_pinion_pivot_shaft_spec
import dt_pinion_spring_spec
import vn_post_mount_screw_spec
from _buildgraph import module_deps_of


SHEETS = (
    ("dt-crank-handle", dt_crank_handle_spec),
    ("dt-pinion-bracket", dt_pinion_bracket_spec),
    ("dt-pinion-cam", dt_pinion_cam_spec),
    ("dt-pinion-cam-pin", dt_pinion_cam_pin_spec),
    ("dt-pinion-handle", dt_pinion_handle_spec),
    ("dt-pinion-lever", dt_pinion_lever_spec),
    ("dt-pinion-lever-pin", dt_pinion_lever_pin_spec),
    ("dt-pinion-pivot-shaft", dt_pinion_pivot_shaft_spec),
    ("dt-pinion-spring", dt_pinion_spring_spec),
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
        # A sheet with no notes (MHA-DT-030, rule 6) has nothing to repeat.
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
    row = registry["dt-arbor-pedestal"]
    row["_mutation_probe"] = True
    try:
        assert "_mutation_probe" not in _config.parts("dt-arbor-pedestal")
    finally:
        row.pop("_mutation_probe", None)


def test_new_pin_and_spring_numbers_use_reserved_unique_allocations() -> None:
    assert _config.parts("dt-pinion-cam-pin")["number"] == "MHA-DT-025"
    assert _config.parts("dt-pinion-spring")["number"] == "MHA-DT-024"


def test_drawing_notes_do_not_change_the_drive_train_recipe() -> None:
    scripts = Path(__file__).resolve().parent
    deps = {
        Path(path).name
        for path in module_deps_of(scripts / "build_dt_drive_train_assembly.py")
    }
    drawing_only = {
        "dt_pinion_arbor_spec.py",
        "dt_pinion_cam_spec.py",
        "dt_pinion_cam_pin_spec.py",
        "dt_pinion_handle_spec.py",
        "dt_pinion_lever_spec.py",
        "dt_pinion_spring_spec.py",
    }
    assert deps.isdisjoint(drawing_only)
    assert {
        "dt_pinion_arbor_geometry.py",
        "dt_pinion_cam_geometry.py",
        "dt_pinion_cam_pin_geometry.py",
        "dt_pinion_handle_geometry.py",
        "dt_pinion_lever_geometry.py",
        "dt_pinion_spring_geometry.py",
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
    pair = ("dt-pinion-bracket-1", "dt-pinion-cam-pin-1")
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

    with pytest.raises(RuntimeError, match="dt-pinion-cam-pin-2"):
        _assembly.check_no_interference(
            _InterferenceAdapter(
                _Interference(("dt-pinion-bracket-1", "dt-pinion-cam-pin-2"), 0.37)
            ),
            allowed_pairs={frozenset(pair): 0.45},
        )


def test_intentional_fit_allowance_bounds_the_pair_total(monkeypatch) -> None:
    """#853: a pair split into several bodies is bounded by its TOTAL overlap.

    662e4db1's adjuster/block thread annulus came back as 13 bodies, each
    compared alone against the pair limit; a split pair whose every body is
    under the limit but whose sum is over it passed.
    """
    pair = ("dt-cone-tip-block-1", "vn-cone-tip-adjuster-1")
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
    paper_drive = _interference_contracts.allowed_interference_pairs("pd-paper-drive")
    clamp_receivers = {1: 2, 2: 2, 3: 1, 4: 1}
    for screw_number, back_number in clamp_receivers.items():
        pair = frozenset(
            (f"vn-clamp-screw-{screw_number}", f"sh-column-clamp-back-{back_number}")
        )
        assert paper_drive[pair] == pytest.approx(42.217366426182714)

    guide_receivers_and_limits = {
        5: (1, 13.951902256034774),
        6: (2, 13.951902256034774),
        7: (1, 13.951902256034774),
        8: (2, 13.951902256034774),
        9: (1, 13.951902256034774),
        10: (2, 13.951902256034774),
        11: (1, 13.951902256034774),
        12: (2, 13.951902256034774),
        13: (1, 13.951902256034774),
        14: (2, 13.951902256034774),
    }
    for screw_number, (guide_number, limit) in guide_receivers_and_limits.items():
        pair = frozenset(
            (f"vn-fillister-screw-{screw_number}", f"pd-platen-guide-{guide_number}")
        )
        assert paper_drive[pair] == pytest.approx(limit)
    # R9-31: the lock-plate screws are MHA-VN-046 button heads, not fillisters;
    # R9-48: 3/8 long, 7.525 of each in the guide's through tap.
    lock_receivers = {1: 1, 2: 1, 3: 2, 4: 1, 5: 2, 6: 2, 7: 1, 8: 2}
    for screw_number, guide_number in lock_receivers.items():
        pair = frozenset(
            (f"vn-guide-lock-screw-{screw_number}", f"pd-platen-guide-{guide_number}")
        )
        assert paper_drive[pair] == pytest.approx(19.378357354767928)

    summing = _interference_contracts.allowed_interference_pairs("sm-summing")
    assert summing == pytest.approx(
        {
            # 91251A157 #6-32 in the #36 drill over its 8.10 nominal reach.
            frozenset(("vn-knife-hanger-stud-1", "sm-knife-mount-1")): _annulus_limit(
                3.505, 2.705, 8.10
            ),
            frozenset(("vn-knife-hanger-stud-2", "sm-knife-mount-2")): _annulus_limit(
                3.505, 2.705, 8.10
            ),
            # 98381A473 at its largest (3.18262) in the smallest Ø3.165 ream,
            # pressed 9.5 deep (the models are line to line); two per mount,
            # the front mount's pair first.
            frozenset(("vn-knife-mount-dowel-1", "sm-knife-mount-1")): _annulus_limit(
                3.18262, 3.165, 9.5
            ),
            frozenset(("vn-knife-mount-dowel-2", "sm-knife-mount-1")): _annulus_limit(
                3.18262, 3.165, 9.5
            ),
            frozenset(("vn-knife-mount-dowel-3", "sm-knife-mount-2")): _annulus_limit(
                3.18262, 3.165, 9.5
            ),
            frozenset(("vn-knife-mount-dowel-4", "sm-knife-mount-2")): _annulus_limit(
                3.18262, 3.165, 9.5
            ),
            # 9490T1 #10-24 through the 0.75-in boss; #25 tap drill.
            frozenset(("vn-boss-hook-1", "sm-summing-lever-1")): _annulus_limit(
                4.826, 3.797, 19.05
            ),
        }
    )


def test_drive_train_interference_contracts_use_fixed_runtime_oracles() -> None:
    threaded_by_assembly = {
        "dt-drive-train": {
            # mha092-r3-8b1b drive-train leaf: 16.4412 and 7.8008 observed,
            # plus ten percent.
            frozenset(("vn-cone-tip-adjuster-1", "dt-cone-tip-block-1")): 18.08532,
            frozenset(("vn-cone-tip-pinch-screw-1", "dt-cone-tip-block-1")): 8.58088,
            # First prism-block drive-train leaf: 5.6585 observed, plus ten
            # percent.
            frozenset(("vn-cone-tip-block-screw-1", "dt-cone-tip-block-1")): 6.22435,
            # 1/16 in tip land: 0.13 observed at Ø0.79, scaled by r^3 (x8).
            frozenset(("vn-cone-tip-adjuster-1", "dt-cone-gear-shaft-1")): 1.144,
            frozenset(("vn-fillister-screw-1", "dt-crank-arm-1")): _annulus_limit(
                2.8448, 2.261, 5.33
            ),
            # MHA-DT-032 #4-40 major 2.845 in the #43 tap drill 2.261: 6.5 of
            # full thread past the 1.5 relief plus the lead cone, within 7.0.
            frozenset(("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1")): _annulus_limit(
                2.845, 2.261, 7.0
            ),
            # U30 I22: each MHA-VN-031 1/4-20 in its #7 MHA-DT-020 tap, its cut
            # length past the post's grip deep.
            **_expected_numbered_pairs(
                "vn-post-mount-screw",
                (1, 2),
                "dt-cone-swing-platform",
                6.35,
                5.105,
                vn_post_mount_screw_spec.CUT_LENGTH_MM - vn_post_mount_screw_spec.GRIP_MM,
            ),
            # R1: MHA-DT-015 is a bonded slip fit modelled line to line in the
            # MHA-DT-022 cross-hole, so the pair needs no interference allowance.
            # #743 Q3: MHA-VN-034 #4-40 x 1/4 in each pedestal crown tap (the
            # _hole_spec major 2.845 in the #43 tap drill, over its length).
            **_expected_numbered_pairs(
                "vn-arbor-set-screw",
                range(1, 3),
                "dt-arbor-pedestal",
                2.845,
                2.261,
                6.35,
                second_number=None,
            ),
            # CONTRACT-crank: 2x MHA-VN-044 3/32 dowel (2.38125) pressed into
            # MHA-DT-011's 2.38 reamed collar holes, 3.95 deep.
            **_expected_numbered_pairs(
                "vn-crank-seat-drive-pin",
                range(1, 3),
                "dt-crankshaft",
                2.38125,
                2.38,
                3.95,
            ),
        },
        "fr-frame": {
            **_expected_numbered_pairs(
                "vn-lag-screw",
                range(1, 5),
                "fr-harmonic-base",
                6.35,
                5.105,
                12.4221875,
            ),
            # MHA-VN-027 / 90280A837: #10-32 major 4.826, #21 drill 4.0386.
            # The 44.45-mm shank crosses a 25.5-mm socket. Its shortest
            # socket chord is 25.039163803929238 mm at the major envelope,
            # leaving at most 19.410836196070765 mm in both casting walls.
            **_expected_numbered_pairs(
                "vn-frame-cross-screw",
                range(1, 5),
                "fr-harmonic-base",
                4.826,
                4.0386,
                19.410836196070765,
            ),
            **_expected_numbered_pairs(
                "vn-frame-cross-screw",
                range(5, 9),
                "fr-top-frame",
                4.826,
                4.0386,
                19.410836196070765,
            ),
            frozenset(("vn-gooseneck-set-screw-1", "fr-top-frame-1")): _annulus_limit(
                6.35, 5.105, 6.95
            ),
            **_expected_numbered_pairs(
                "vn-fillister-screw",
                range(1, 5),
                "fr-harmonic-base",
                2.8448,
                2.261,
                4.85,
            ),
        },
        "mg-magnifier": {
            **_expected_numbered_pairs(
                "vn-clamp-screw",
                range(1, 3),
                "sh-column-clamp-back",
                4.1656,
                3.454,
                4.85,
            ),
            frozenset(("vn-thumb-screw-1", "mg-magnifying-clamp-1")): _annulus_limit(
                2.8448, 2.261, 3.9
            ),
        },
        "sm-summing": {
            # Stock 91251A157: #6-32 major, #36 drill, 8.10 nominal reach.
            **_expected_numbered_pairs(
                "vn-knife-hanger-stud",
                range(1, 3),
                "sm-knife-mount",
                3.505,
                2.705,
                8.10,
                second_number=None,
            ),
            # Stock 98381A473 pressed 9.5 into the Ø3.175 +0/-0.010 ream,
            # two per knife mount.
            **_expected_numbered_pairs(
                "vn-knife-mount-dowel",
                range(1, 3),
                "sm-knife-mount",
                3.18262,
                3.165,
                9.5,
            ),
            **_expected_numbered_pairs(
                "vn-knife-mount-dowel",
                range(3, 5),
                "sm-knife-mount",
                3.18262,
                3.165,
                9.5,
                second_number=2,
            ),
            # Stock 9490T1: #10-24 major, #25 drill, 0.75-in boss engagement.
            frozenset(("vn-boss-hook-1", "sm-summing-lever-1")): _annulus_limit(
                4.826, 3.797, 19.05
            ),
        },
        "pn-pen": {
            frozenset(("vn-pen-set-screw-1", "pn-pen-frame-1")): _annulus_limit(
                2.8448, 2.261, 5.0
            ),
            frozenset(("vn-hanger-screw-1", "pn-pen-hanger-1")): _annulus_limit(
                4.1656, 3.454, 3.0
            ),
        },
        "pd-paper-drive": {
            **_expected_numbered_pairs(
                "vn-clamp-screw",
                range(1, 3),
                "sh-column-clamp-back",
                4.1656,
                3.454,
                9.0124,
                second_number=2,
            ),
            **_expected_numbered_pairs(
                "vn-clamp-screw",
                range(3, 5),
                "sh-column-clamp-back",
                4.1656,
                3.454,
                9.0124,
            ),
            **_expected_numbered_pairs(
                "vn-fillister-screw",
                range(1, 5),
                "pd-platen",
                2.8448,
                2.261,
                4.5,
            ),
            **_expected_numbered_pairs(
                "vn-fillister-screw",
                range(5, 15, 2),
                "pd-platen-guide",
                2.8448,
                2.261,
                5.4178,
            ),
            **_expected_numbered_pairs(
                "vn-fillister-screw",
                range(6, 15, 2),
                "pd-platen-guide",
                2.8448,
                2.261,
                5.4178,
                second_number=2,
            ),
            **_expected_numbered_pairs(
                "vn-guide-lock-screw",
                (1, 2, 4, 7),
                "pd-platen-guide",
                2.8448,
                2.261,
                7.525,
            ),
            **_expected_numbered_pairs(
                "vn-guide-lock-screw",
                (3, 5, 6, 8),
                "pd-platen-guide",
                2.8448,
                2.261,
                7.525,
                second_number=2,
            ),
            # Round 10 transgear: stock #8-32 / #4-40 / #0-80 screws, the
            # MHA-PD-023 pin's press in the arm, and the MHA-PD-013 1/4-20 nut.
            **_expected_numbered_pairs(
                "vn-transgear-arm-plate-screw",
                range(1, 3),
                "pd-transgear-arm",
                4.1656,
                3.454,
                7.9375,
            ),
            frozenset(("vn-transgear-pivot-screw-1", "pd-support-bar-1")): _annulus_limit(
                4.1656, 3.454, 3.5687
            ),
            **_expected_numbered_pairs(
                "vn-latch-hook-bracket-screw",
                range(1, 3),
                "pd-support-bar",
                2.8448,
                2.261,
                8.725,
            ),
            frozenset(("pd-transgear-pin-1", "pd-transgear-arm-1")): _annulus_limit(
                3.9, 3.874, 7.9375
            ),
            # R9-71: MHA-PD-020's Ø4.727 ream pressed on MHA-VN-041's Ø4.7625
            # shoulder over its 5.5 length.
            frozenset(("pd-transgear-pivot-spacer-1", "vn-transgear-pivot-screw-1")): (
                _annulus_limit(4.7625, 4.727, 5.5)
            ),
            # MHA-VN-047's three prong arcs, atan(3/4) of the turn each, at the
            # Ø2.8956 free diameter inside the MHA-PD-023 Ø2.9464 groove floor.
            frozenset(("vn-transgear-retaining-ring-1", "pd-transgear-pin-1")): (
                3.0 * math.atan(0.75) / (2.0 * math.pi)
            )
            * _annulus_limit(2.9464, 2.8956, 0.635),
            **_expected_numbered_pairs(
                "vn-transgear-disc-screw",
                range(1, 4),
                "pd-rack-pinion",
                1.524,
                1.191,
                2.9,
            ),
            # R9-35: flush-head seat slivers, observed + 10 %.
            frozenset(("vn-transgear-arm-plate-screw-1", "pd-transgear-arm-plate-1")): (
                1.10 * 0.00809042475
            ),
            frozenset(("vn-transgear-arm-plate-screw-2", "pd-transgear-arm-plate-1")): (
                1.10 * 0.00809042475
            ),
            # R9-70: the nut on the collar's faced pilot, 2.9 in front of the
            # seat face: 23.9 - 6.2 - 2.9 of the stud's thread blank.
            frozenset(
                ("pd-transgear-thumbnut-1", "pd-transgear-knob-shaft-1")
            ): _annulus_limit(6.22, 5.105, 14.8),
            # MHA-VN-038 3/32 x 3/16 dowels pressed 2.3625 into MHA-PD-022's 2.38 reams.
            **_expected_numbered_pairs(
                "vn-transgear-knob-drive-pin",
                range(1, 3),
                "pd-transgear-drive-collar",
                2.38125,
                2.38,
                2.3625,
            ),
        },
        "ha-harmonic-analyzer": {
            **_expected_numbered_pairs(
                "mg-magnifier-1/vn-magnifying-bracket-screw",
                range(1, 3),
                "sm-summing-1/sm-summing-lever",
                2.1844,
                1.778,
                4.725,
            ),
            # Twenty stock 9489T111 #6-32 anchors engage only the 0.2-in
            # summing-lever plate; #36 tap drill, not the full stock shank.
            **_expected_numbered_pairs(
                "ch-channel-1/vn-spring-hook",
                range(1, 21),
                "sm-summing-1/sm-summing-lever",
                3.5052,
                2.705,
                5.08,
            ),
            frozenset(
                (
                    "fr-frame-1/fr-harmonic-base-1",
                    "dt-drive-train-1/vn-cone-pivot-screw-1",
                )
            ): _annulus_limit(4.826, 3.797, 9.525),
            **_expected_numbered_pairs(
                "dt-drive-train-1/vn-cone-lock-knob",
                range(1, 2),
                "fr-frame-1/fr-harmonic-base",
                6.35,
                5.105,
                12.7,
            ),
            **_expected_numbered_pairs(
                "dt-drive-train-1/vn-swing-stop-screw",
                range(1, 2),
                "fr-frame-1/fr-harmonic-base",
                2.8448,  # the foot screw's #4-40 SKU, seated full length
                2.261,
                9.525,
            ),
            **_expected_numbered_pairs(
                "dt-drive-train-1/vn-slotted-screw",
                range(1, 5),
                "fr-frame-1/fr-harmonic-base",
                4.1656,
                3.454,
                11.25,  # rule 12 E10: #8-32 x 1-1/4 through the 20.5 block
            ),
            **_expected_numbered_pairs(
                "dt-drive-train-1/vn-foot-screw",
                range(1, 2),
                "fr-frame-1/fr-harmonic-base",
                2.8448,
                2.261,
                8.725,
            ),
            # U34c: MHA-VN-032 #8-32 x 3/4 through the 5.0 pedestal ledge.
            **_expected_numbered_pairs(
                "dt-drive-train-1/vn-pedestal-hold-down-screw",
                range(1, 3),
                "fr-frame-1/fr-harmonic-base",
                4.1656,
                3.454,
                14.05,
            ),
            **_expected_numbered_pairs(
                "ch-channel-1/vn-frame-side-screw",
                range(1, 3),
                "fr-frame-1/fr-top-frame",
                2.8448,
                2.261,
                7.4178,
            ),
            # #743 PR2: MHA-VN-032 #8-32 x 3/4 through the 6.0 rocker-bracket
            # foot, one per bracket since the 2026-10-09 flip.
            **_expected_numbered_pairs(
                "ch-channel-1/vn-pedestal-hold-down-screw",
                range(1, 3),
                "fr-frame-1/fr-rocker-arm-support",
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
        frozenset(("dt-pinion-bracket-1", "dt-pinion-cam-pin-1")),
        frozenset(("dt-pinion-bracket-2", "dt-pinion-cam-pin-2")),
    }
    crank_pairs = {
        frozenset(("dt-crank-pin-1", "dt-crank-hub-1")),
        frozenset(("dt-crank-pin-1", "dt-crankshaft-1")),
    }
    # MHA-VN-037's tube pin across MHA-PD-008's unmodelled cross hole, and MHA-VN-048's
    # across the hole match-drilled through MHA-PD-016 and the journal.
    cross_pin_pairs = {
        frozenset(("vn-transgear-collar-cross-pin-1", "pd-transgear-knob-shaft-1")),
        frozenset(("vn-transgear-knob-cup-pin-1", "pd-transgear-knob-shaft-1")),
        frozenset(("vn-transgear-knob-cup-pin-1", "pd-transgear-knob-cup-1")),
    }
    special_pairs = {
        "dt-drive-train": crank_pairs,
        "pd-paper-drive": cross_pin_pairs,
    }
    for name, expected_threaded in threaded_by_assembly.items():
        allowed = _interference_contracts.allowed_interference_pairs(name)
        # Exact pair equality also forbids tube/screw and cap/tube exemptions.
        assert set(allowed) == set(expected_threaded) | special_pairs.get(name, set())
        for pair, expected_limit in expected_threaded.items():
            assert allowed[pair] == pytest.approx(expected_limit)
        assert all(limit > 0.0 and math.isfinite(limit) for limit in allowed.values())

    drive_train_allowed = _interference_contracts.allowed_interference_pairs(
        "dt-drive-train"
    )
    assert not cam_pairs & set(drive_train_allowed)
    crank_allowed = _interference_contracts.allowed_interference_pairs("dt-drive-train")
    hub_pair = frozenset(("dt-crank-pin-1", "dt-crank-hub-1"))
    shaft_pair = frozenset(("dt-crank-pin-1", "dt-crankshaft-1"))
    # The CONTRACT-crank hub barrel (Ø22.25 since R9-38) sets the MHA-DT-009
    # pilot spans: a longer hub chord, and the shaft crossing further down
    # the taper. #1140 stood the pin 0.6 further proud (PIN_PROUD 4.45,
    # keeper-ring hole at 3.7), so a thinner stretch of the taper sits in
    # both receivers.
    assert 111.2 < crank_allowed[hub_pair] < 111.8
    assert 55.1 < crank_allowed[shaft_pair] < 55.6
    # 1.10 x (12.470 - 4.755): the Ø1.5875 and Ø0.978 chords through Ø6.35.
    paper_allowed = _interference_contracts.allowed_interference_pairs("pd-paper-drive")
    cross_pin_pair = frozenset(
        ("vn-transgear-collar-cross-pin-1", "pd-transgear-knob-shaft-1")
    )
    assert 8.4 < paper_allowed[cross_pin_pair] < 8.6
    # MHA-CH-011: each 5/64 bar pivot pin pressed into its bar's Ø1.968 ream
    # through both top-notch cheeks (6.35 bar less the 3.20 notch), and
    # MHA-CH-010: the same pin pressed into its rod's Ø1.968 fork ream through
    # both tines (6.075 fork less the 2.625 slot); channel j's pin with
    # channel j's bar or rod only. MHA-VN-034: each #4-40 apex set screw's
    # thread in its MHA-CH-008 ear's tap, over the R8 arch less the Ø6.5
    # bore's height at the Ø2.845 envelope's edge; screw n in bracket n.
    # MHA-VN-055: each #1-72 x 5/32 keeper set screw in its own keeper's
    # crown tap (#53 drill).
    channel_allowed = _interference_contracts.allowed_interference_pairs("ch-channel")
    assert channel_allowed == pytest.approx(
        {
            **{
                frozenset(
                    (f"ch-bar-pivot-pin-{n}", f"ch-amplitude-bar-{n}")
                ): _annulus_limit(1.984375, 1.968, 3.15)
                for n in range(1, 21)
            },
            **{
                frozenset(
                    (f"ch-rod-pivot-pin-{n}", f"ch-connecting-rod-{n}")
                ): _annulus_limit(1.984375, 1.968, 3.45)
                for n in range(1, 21)
            },
            **{
                frozenset(
                    (f"vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}")
                ): _annulus_limit(
                    2.845, 2.261, 8.0 - math.sqrt(3.25**2 - (2.845 / 2.0) ** 2)
                )
                for n in (1, 2)
            },
            **{
                frozenset(
                    (f"vn-fulcrum-set-screw-{n}", f"ch-fulcrum-keeper-{n}")
                ): _annulus_limit(1.854, 1.511, 3.96875)
                for n in range(1, 3)
            },
        }
    )
    assert _interference_contracts.allowed_interference_pairs("unknown") == {}

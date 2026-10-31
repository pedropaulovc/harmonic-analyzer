"""Cross-sheet offline contracts for the pinion-cluster drawings."""

from __future__ import annotations

import math
from collections.abc import Iterable
from pathlib import Path
from types import SimpleNamespace

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
import dt_pinion_pivot_block_geometry
import dt_pinion_spring_spec
import dt_vn_post_mount_screw_spec
import dt_vn_slotted_screw_spec
from _buildgraph import module_deps_of
from test_assembly_chain_mesh import (
    _Adapter as InterferenceAdapter,
    _Component as InterferenceComponent,
    _Interference as InterferenceBody,
    observations as observations,
)


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
        # A sheet with no notes (MHA-DT-30, drawing-guidelines.md rule 7 (notes: few, flagged, never a method)) has nothing to repeat.
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
    assert _config.parts("dt-pinion-cam-pin")["number"] == "MHA-DT-25"
    assert _config.parts("dt-pinion-spring")["number"] == "MHA-DT-24"


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
    pair = ("dt-cone-tip-block-1", "dt-vn-cone-tip-adjuster-1")
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


def _mg_clamp_thumb_limit() -> float:
    """Independent #4-40 annulus through the actual top-to-bore wall.

    The top grew from 28.95 to 29.50; the 19.95 bore station and Ø6.50
    bore stayed put. The former 5.75-mm wall is now 6.30 mm. Do not read
    the runtime allowance or its triple to construct this oracle.
    """
    return _annulus_limit(2.8448, 2.261, 29.50 - 19.95 - 6.50 / 2.0)


@pytest.mark.parametrize(
    ("assembly", "screw_number", "excess_mm3", "rejected"),
    (
        ("mg-magnifier", 1, -1e-6, False),
        ("mg-magnifier", 1, 1e-6, True),
        ("mg-magnifier", 2, -1e-6, True),
        ("ha-harmonic-analyzer", 1, -1e-6, True),
    ),
)
def test_clamp_thumb_allowance_bounds_the_actual_pair_and_total_volume(
    observations, assembly, screw_number, excess_mm3, rejected
) -> None:
    """Synthetic gate observations, not new native interference evidence."""
    import mg_magnifying_clamp_geom as clamp

    assert clamp.BLOCK_HEIGHT - clamp.LEVER_BORE_Y - clamp.LEVER_BORE_DIA / 2.0 == (
        pytest.approx(29.50 - 19.95 - 6.50 / 2.0)
    )
    prefix = "mg-magnifier-1/" if assembly == "ha-harmonic-analyzer" else ""
    components = (
        InterferenceComponent(f"{prefix}sh-vn-thumb-screw-{screw_number}"),
        InterferenceComponent(f"{prefix}mg-magnifying-clamp-1"),
    )
    # Each body is below the bound even in the excessive-total case. A
    # per-body gate, stale 5.75-mm bound, or wider exemption must fail here.
    body_volume = (_mg_clamp_thumb_limit() + excess_mm3) / 2.0
    adapter = InterferenceAdapter(
        InterferenceBody(components, body_volume),
        InterferenceBody(components, body_volume),
    )
    if assembly == "ha-harmonic-analyzer":
        # The root also contains DT's two independently referenced instances
        # of one shared SKU. Let the real selector binder read their native
        # parent paths, role references, file and Default member.
        roots = tuple(
            SimpleNamespace(
                Name2=f"{stem}-1",
                ComponentReference="",
                ReferencedConfiguration="Default",
                GetPathName=lambda stem=stem: f"C:/native/{stem}.SLDASM",
            )
            for stem in ("mg-magnifier", "dt-drive-train")
        )
        references = tuple(
            InterferenceComponent(
                f"dt-drive-train-1/sh-vn-fillister-screw-90280a108-{index}",
                "Default",
                native_stem="sh-vn-fillister-screw-90280a108",
                component_reference=f"{role}:1",
            )
            for index, role in enumerate(("FootScrew", "SwingStopScrew"), 1)
        )
        adapter.currentModel.GetComponents = lambda top_level_only: (
            roots if top_level_only else (*roots, *references, *components)
        )
    allowed = _interference_contracts.allowed_interference_pairs(assembly)
    if rejected:
        with pytest.raises(RuntimeError, match="interference"):
            _assembly.check_no_interference(adapter, allowed_pairs=allowed)
    else:
        _assembly.check_no_interference(adapter, allowed_pairs=allowed)
        event, = (
            attrs for name, attrs in observations.events
            if name == "interference.bounded_pair"
        )
        assert event["body_count"] == 2
        assert event["limit_mm3"] == pytest.approx(_mg_clamp_thumb_limit())
    assert adapter.currentModel.manager.releases == 1


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
                f"{first_stem}{'' if first_stem.endswith(':') else '-'}{number}",
                f"{second_stem}{'' if second_stem.endswith(':') else '-'}"
                f"{number if second_number is None else second_number}",
            )
        ): limit
        for number in numbers
    }


def test_cross_numbered_fit_pairs_use_fixed_runtime_oracles() -> None:
    paper_drive = _interference_contracts.allowed_interference_pairs("pd-paper-drive")
    clamp_receivers = {1: 2, 2: 2, 3: 1, 4: 1}
    for screw_number, back_number in clamp_receivers.items():
        pair = frozenset(
            (f"sh-vn-clamp-screw-{screw_number}", f"sh-column-clamp-back-{back_number}")
        )
        assert paper_drive[pair] == pytest.approx(39.87518418692443)

    # The MHA-PD-VN-52 guide screws alone: seed -1, then the grid -2..-10.
    guide_receivers_and_limits = {
        1: (1, 13.951902256034774),
        2: (2, 13.951902256034774),
        3: (1, 13.951902256034774),
        4: (2, 13.951902256034774),
        5: (1, 13.951902256034774),
        6: (2, 13.951902256034774),
        7: (1, 13.951902256034774),
        8: (2, 13.951902256034774),
        9: (1, 13.951902256034774),
        10: (2, 13.951902256034774),
    }
    for screw_number, (guide_number, limit) in guide_receivers_and_limits.items():
        pair = frozenset(
            (f"sh-vn-brass-fillister-screw-{screw_number}", f"pd-platen-guide-{guide_number}")
        )
        assert paper_drive[pair] == pytest.approx(limit)
    # R9-31: the lock-plate screws are MHA-PD-VN-60 slotted pan heads, not
    # fillisters; R9-48: 3/8 long through the 1/16 lock sheet, so 7.9375 of
    # each sits in the guide's through tap.
    lock_receivers = {1: 1, 2: 1, 3: 2, 4: 1, 5: 2, 6: 2, 7: 1, 8: 2}
    for screw_number, guide_number in lock_receivers.items():
        pair = frozenset(
            (f"pd-vn-guide-lock-screw-{screw_number}", f"pd-platen-guide-{guide_number}")
        )
        assert paper_drive[pair] == pytest.approx(20.440626113418)

    summing = _interference_contracts.allowed_interference_pairs("sm-summing")
    assert summing == pytest.approx(
        {
            # Cut 92314A253 #10-24 in the #25 drill over 8.9173 nominal reach.
            frozenset(("sm-vn-knife-hanger-stud-1", "sm-knife-mount-1")): _annulus_limit(
                4.826, 3.797, 8.9173
            ),
            frozenset(("sm-vn-knife-hanger-stud-2", "sm-knife-mount-2")): _annulus_limit(
                4.826, 3.797, 8.9173
            ),
            # Exact head-to-washer bearing contacts: no solid overlap allowed.
            frozenset(("sm-vn-knife-hanger-stud-1", "sm-vn-knife-hanger-washer-1")): 0.0,
            frozenset(("sm-vn-knife-hanger-stud-2", "sm-vn-knife-hanger-washer-2")): 0.0,
            # 9490T1 #10-24 through the 0.75-in boss; #25 tap drill.
            frozenset(("sm-vn-boss-hook-1", "sm-summing-lever-1")): _annulus_limit(
                4.826, 3.797, 19.05
            ),
            # MHA-SM-04 1/4-28 major in the #3 drill of the blind end-piece
            # tap: counterbore floor (2.78) to the free-gap tip (14.62).
            frozenset(("sm-gooseneck-spring-screw-1", "sm-gooseneck-1")): _annulus_limit(
                6.35, 5.41, 11.84
            ),
        }
    )
    # Owner ruling 2026-10-24 (T+H3): the four knife-mount dowels press into
    # the one MHA-FR-02 crossbar, so the back mount's pair (dowels 3-4) pairs
    # with fr-top-frame-1, not a second crossbar, and no dowel pairs with a
    # knife mount (each slips in its round hole or slot).
    top = _interference_contracts.allowed_interference_pairs("ha-harmonic-analyzer")
    for dowel_number in range(1, 5):
        pair = frozenset(
            (
                f"sm-summing-1/sm-vn-knife-mount-dowel-{dowel_number}",
                "fr-frame-1/fr-top-frame-1",
            )
        )
        assert top[pair] == pytest.approx(_annulus_limit(3.18262, 3.165, 12.0))
    assert not any(
        "sm-vn-knife-mount-dowel" in name for pair in summing for name in pair
    )


def test_drive_train_interference_contracts_use_fixed_runtime_oracles() -> None:
    threaded_by_assembly = {
        "dt-drive-train": {
            # mha092-r3-8b1b drive-train leaf: 16.4412 and 7.8008 observed,
            # plus ten percent.
            frozenset(("dt-vn-cone-tip-adjuster-1", "dt-cone-tip-block-1")): 18.08532,
            frozenset(("dt-vn-cone-tip-pinch-screw-1", "dt-cone-tip-block-1")): 8.58088,
            # First prism-block drive-train leaf: 5.6585 observed, plus ten
            # percent.
            frozenset(("dt-vn-cone-tip-block-screw-1", "dt-cone-tip-block-1")): 6.22435,
            # 1/16 in tip land: 0.13 observed at Ø0.79, scaled by r^3 (x8).
            frozenset(("dt-vn-cone-tip-adjuster-1", "dt-cone-gear-shaft-1")): 1.144,
            frozenset(("sh-vn-brass-fillister-screw-1", "dt-crank-arm-1")): _annulus_limit(
                2.8448, 2.261, 5.33
            ),
            # MHA-DT-32 #4-40 major 2.845 in the #43 tap drill 2.261: 6.5 of
            # full thread past the 1.5 relief plus the lead cone, within 7.0.
            frozenset(("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1")): _annulus_limit(
                2.845, 2.261, 7.0
            ),
            # U30 I22: each MHA-DT-VN-61 1/4-20 in its #7 MHA-DT-20 tap, its cut
            # length past the post's grip deep.
            **_expected_numbered_pairs(
                "dt-vn-post-mount-screw",
                (1, 2),
                "dt-cone-swing-platform",
                6.35,
                5.105,
                dt_vn_post_mount_screw_spec.CUT_LENGTH_MM - dt_vn_post_mount_screw_spec.GRIP_MM,
            ),
            # R1: MHA-DT-15 is a bonded slip fit modelled line to line in the
            # MHA-DT-22 cross-hole, so the pair needs no interference allowance.
            # #743 Q3: MHA-DT-VN-64 #4-40 x 1/4 in each pedestal crown tap (the
            # _hole_spec major 2.845 in the #43 tap drill, over its length).
            **_expected_numbered_pairs(
                "sh-vn-arbor-set-screw",
                range(1, 3),
                "dt-arbor-pedestal",
                2.845,
                2.261,
                6.35,
                second_number=None,
            ),
            # CONTRACT-crank: 2x MHA-DT-VN-67 3/32 dowel (2.38125) pressed into
            # MHA-DT-11's 2.38 reamed collar holes, 3.95 deep.
            **_expected_numbered_pairs(
                "dt-vn-crank-seat-drive-pin",
                range(1, 3),
                "dt-crankshaft",
                2.38125,
                2.38,
                3.95,
            ),
        },
        "fr-frame": {
            **_expected_numbered_pairs(
                "fr-vn-lag-screw",
                range(1, 5),
                "fr-harmonic-base",
                6.35,
                5.105,
                12.4221875,
            ),
            # MHA-FR-VN-53 / 90280A837: #10-32 major 4.826, #21 drill 4.0386.
            # The 44.45-mm shank crosses a 25.5-mm socket. Its shortest
            # socket chord is 25.039163803929238 mm at the major envelope,
            # leaving at most 19.410836196070765 mm in both casting walls.
            **_expected_numbered_pairs(
                "fr-vn-frame-cross-screw",
                range(1, 5),
                "fr-harmonic-base",
                4.826,
                4.0386,
                19.410836196070765,
            ),
            **_expected_numbered_pairs(
                "fr-vn-frame-cross-screw",
                range(5, 9),
                "fr-top-frame",
                4.826,
                4.0386,
                19.410836196070765,
            ),
            # MHA-FR-VN-52 / 91410A540: spot face 21.0 from the bore axis to the
            # cup tip 8.15 from it (12.5 to the O17 bore wall + 0.35).
            frozenset(("fr-vn-gooseneck-set-screw-1", "fr-top-frame-1")): _annulus_limit(
                6.35, 5.105, 12.85
            ),
            **_expected_numbered_pairs(
                "sh-vn-brass-fillister-screw",
                range(1, 5),
                "fr-harmonic-base",
                2.8448,
                2.261,
                4.85,
            ),
        },
        "mg-magnifier": {
            **_expected_numbered_pairs(
                "sh-vn-clamp-screw",
                range(1, 3),
                "sh-column-clamp-back",
                4.1656,
                3.454,
                4.35,
            ),
            frozenset(("sh-vn-thumb-screw-1", "mg-magnifying-clamp-1")): (
                _mg_clamp_thumb_limit()
            ),
            # #1559: the vertical rod's #4-40 end (2.845 major) in the clamp's
            # bottom tap drill, tip to relief.
            frozenset(
                ("mg-magnifying-vertical-rod-1", "mg-magnifying-clamp-1")
            ): _annulus_limit(2.845, 2.261, 6.0),
            # MHA-MG-07 3/16 drill-rod pin pressed through the wheel bar's
            # reamed .1865 bore, the bar's 9.0 depth.
            frozenset(("mg-wheel-axle-1", "mg-wheel-bar-1")): _annulus_limit(
                4.7625, 4.7371, 9.0
            ),
            frozenset(("sh-vn-thumb-screw-2", "mg-output-fixture-1")): _annulus_limit(
                2.8448, 2.261, 10.1
            ),
            frozenset(
                ("mg-magnifying-lever-1", "mg-magnifying-bracket-1")
            ): _annulus_limit(
                # Full-neck cosmetic 1/4-20 major/tap-drill overlap.
                6.35, 5.105, 12.5
            ),
        },
        "sm-summing": {
            # Cut 92314A253: #10-24 major, #25 drill, 8.9173 nominal reach.
            **_expected_numbered_pairs(
                "sm-vn-knife-hanger-stud",
                range(1, 3),
                "sm-knife-mount",
                4.826,
                3.797,
                8.9173,
                second_number=None,
            ),
            frozenset(("sm-vn-knife-hanger-stud-1", "sm-vn-knife-hanger-washer-1")): 0.0,
            frozenset(("sm-vn-knife-hanger-stud-2", "sm-vn-knife-hanger-washer-2")): 0.0,
            # Stock 9490T1: #10-24 major, #25 drill, 0.75-in boss engagement.
            frozenset(("sm-vn-boss-hook-1", "sm-summing-lever-1")): _annulus_limit(
                4.826, 3.797, 19.05
            ),
            # MHA-SM-04 1/4-28 major, #3 drill, 14.62 tip reach less 2.78 counterbore.
            frozenset(("sm-gooseneck-spring-screw-1", "sm-gooseneck-1")): _annulus_limit(
                6.35, 5.41, 11.84
            ),
        },
        "pn-pen": {
            # #4-40 thumb screw through the stirrup's 6.0 bottom rail.
            frozenset(("pn-vn-pen-set-screw-1", "pn-pen-frame-1")): _annulus_limit(
                2.8448, 2.261, 6.0
            ),
            # #4-40 x 3/16 rod set screw wholly in the v-block tap.
            frozenset(("pn-vn-pen-rod-set-screw-1", "pn-pen-v-block-1")): _annulus_limit(
                2.8448, 2.261, 4.7625
            ),
            # #0-80 adjuster stud 3.2 into the rod top (code review C05).
            frozenset(("pn-pen-adjust-screw-1", "pn-pen-rod-1")): _annulus_limit(
                1.524, 1.191, 3.2
            ),
        },
        "pd-paper-drive": {
            **_expected_numbered_pairs(
                "sh-vn-clamp-screw",
                range(1, 3),
                "sh-column-clamp-back",
                4.1656,
                3.454,
                8.5124,
                second_number=2,
            ),
            **_expected_numbered_pairs(
                "sh-vn-clamp-screw",
                range(3, 5),
                "sh-column-clamp-back",
                4.1656,
                3.454,
                8.5124,
            ),
            # MHA-PD-VN-65 #2-56 clip screws, 5.55 in the platen's through tap.
            **_expected_numbered_pairs(
                "pd-vn-platen-clip-screw",
                range(1, 5),
                "pd-platen",
                2.184,
                1.778,
                5.55,
            ),
            **_expected_numbered_pairs(
                "sh-vn-brass-fillister-screw",
                range(1, 11, 2),
                "pd-platen-guide",
                2.8448,
                2.261,
                5.4178,
            ),
            **_expected_numbered_pairs(
                "sh-vn-brass-fillister-screw",
                range(2, 11, 2),
                "pd-platen-guide",
                2.8448,
                2.261,
                5.4178,
                second_number=2,
            ),
            **_expected_numbered_pairs(
                "pd-vn-guide-lock-screw",
                (1, 2, 4, 7),
                "pd-platen-guide",
                2.8448,
                2.261,
                7.9375,
            ),
            **_expected_numbered_pairs(
                "pd-vn-guide-lock-screw",
                (3, 5, 6, 8),
                "pd-platen-guide",
                2.8448,
                2.261,
                7.9375,
                second_number=2,
            ),
            # Round 10 transgear: stock #8-32 / #4-40 / #0-80 screws, the
            # MHA-PD-23 pin's press in the arm, and the MHA-PD-13 1/4-20 nut.
            **_expected_numbered_pairs(
                "pd-vn-transgear-arm-plate-screw",
                range(1, 3),
                "pd-transgear-arm",
                4.1656,
                3.454,
                7.9375,
            ),
            # MHA-PD-VN-57 through the bar's through tap: the fitted 9.15 thread
            # less the 1.1938 neck flat.
            frozenset(("pd-vn-transgear-pivot-screw-1", "pd-support-bar-1")): _annulus_limit(
                4.1656, 3.454, 7.9562
            ),
            **_expected_numbered_pairs(
                "sh-vn-fillister-screw-90280a108",
                range(1, 3),
                "pd-support-bar",
                2.8448,
                2.261,
                8.725,
            ),
            frozenset(("pd-transgear-pin-1", "pd-transgear-arm-1")): _annulus_limit(
                3.9, 3.874, 7.9375
            ),
            # MHA-PD-VN-64 Ø2.0 dowels pressed into the arm's Ø1.995 through reams,
            # 6.0 long less 1.70 proud.
            **_expected_numbered_pairs(
                "pd-vn-transgear-arm-plate-locating-pin",
                range(1, 3),
                "pd-transgear-arm",
                2.0,
                1.995,
                6.0 - 1.70,
            ),
            # R9-71: MHA-PD-20's Ø4.727 ream pressed on MHA-PD-VN-57's Ø4.7625
            # shoulder over its 5.0 length.
            frozenset(("pd-transgear-pivot-spacer-1", "pd-vn-transgear-pivot-screw-1")): (
                _annulus_limit(4.7625, 4.727, 5.0)
            ),
            # MHA-PD-VN-61's three prong arcs, atan(3/4) of the turn each, at the
            # Ø2.8956 free diameter inside the MHA-PD-23 Ø2.9464 groove floor.
            frozenset(("pd-vn-transgear-retaining-ring-1", "pd-transgear-pin-1")): (
                3.0 * math.atan(0.75) / (2.0 * math.pi)
            )
            * _annulus_limit(2.9464, 2.8956, 0.635),
            **_expected_numbered_pairs(
                "pd-vn-transgear-disc-screw",
                range(1, 4),
                "pd-rack-pinion",
                1.524,
                1.191,
                2.9,
            ),
            # R9-35: flush-head seat slivers, observed + 10 %.
            frozenset(("pd-vn-transgear-arm-plate-screw-1", "pd-transgear-arm-plate-1")): (
                1.10 * 0.00809042475
            ),
            frozenset(("pd-vn-transgear-arm-plate-screw-2", "pd-transgear-arm-plate-1")): (
                1.10 * 0.00809042475
            ),
            # #8-32 nut on the collar's pilot, with its rear face on actual F:
            # 23.9 - 6.2 - 2.9 of the Ø4.070 stud's thread blank.
            frozenset(
                ("pd-transgear-thumbnut-1", "pd-transgear-knob-shaft-1")
            ): _annulus_limit(4.070, 3.454, 14.8),
            # MHA-PD-VN-54 3/32 x 3/16 dowels pressed 2.3625 into MHA-PD-22's 2.38 reams.
            **_expected_numbered_pairs(
                "pd-vn-transgear-knob-drive-pin",
                range(1, 3),
                "pd-transgear-drive-collar",
                2.38125,
                2.38,
                2.3625,
            ),
        },
        "ha-harmonic-analyzer": {
            # Exact nested bearing contacts, NOT manufactured interference.
            **{
                frozenset((
                    f"sm-summing-1/sm-vn-knife-hanger-stud-{number}",
                    f"sm-summing-1/sm-vn-knife-hanger-washer-{number}",
                )): 0.0
                for number in (1, 2)
            },
            **{
                frozenset((
                    f"sm-summing-1/sm-vn-knife-hanger-washer-{number}",
                    "fr-frame-1/fr-top-frame-1",
                )): 0.0
                for number in (1, 2)
            },
            # Owner ruling 2026-10-24 (T+H3): 98381A473 at its largest
            # (3.18262) pressed 12.0 up into the smallest Ø3.165 crossbar
            # ream (the models are line to line); four in the one crossbar.
            # In sm-summing each pin slips in its knife mount: no pair there.
            **_expected_numbered_pairs(
                "sm-summing-1/sm-vn-knife-mount-dowel",
                range(1, 5),
                "fr-frame-1/fr-top-frame",
                3.18262,
                3.165,
                12.0,
            ),
            **_expected_numbered_pairs(
                "mg-magnifier-1/mg-vn-magnifying-bracket-screw",
                range(1, 3),
                "sm-summing-1/sm-summing-lever",
                2.1844,
                1.778,
                4.7625,
            ),
            # Twenty stock 9489T111 #6-32 anchors engage the summing
            # lever's uniform 7.00 plate; #36 tap drill, not the full stock shank.
            **_expected_numbered_pairs(
                "ch-channel-1/ch-vn-spring-hook",
                range(1, 21),
                "sm-summing-1/sm-summing-lever",
                3.5052,
                2.705,
                7.0,
            ),
            frozenset(
                (
                    "fr-frame-1/fr-harmonic-base-1",
                    "dt-drive-train-1/dt-vn-cone-pivot-screw-1",
                )
            ): _annulus_limit(4.826, 3.797, 9.525),
            **_expected_numbered_pairs(
                "dt-drive-train-1/dt-vn-cone-lock-knob",
                range(1, 2),
                "fr-frame-1/fr-harmonic-base",
                6.35,
                5.105,
                12.7,
            ),
            **_expected_numbered_pairs(
                "dt-drive-train-1/@SwingStopScrew:",
                range(1, 2),
                "fr-frame-1/fr-harmonic-base",
                2.8448,  # the foot screw's #4-40 SKU, seated full length
                2.261,
                9.525,
            ),
            **_expected_numbered_pairs(
                "dt-drive-train-1/dt-vn-slotted-screw",
                range(1, 5),
                "fr-frame-1/fr-harmonic-base",
                4.1656,
                3.454,
                dt_vn_slotted_screw_spec.SHANK_LEN - dt_pinion_pivot_block_geometry.BLOCK_HEIGHT,
            ),
            **_expected_numbered_pairs(
                "dt-drive-train-1/@FootScrew:",
                range(1, 2),
                "fr-frame-1/fr-harmonic-base",
                2.8448,
                2.261,
                8.725,
            ),
            # The unchanged pedestal screw inserts14.05, but only13.0 of
            # retained skin overlaps; its tip protrudes into the pocket.
            **_expected_numbered_pairs(
                "dt-drive-train-1/dt-vn-pedestal-hold-down-screw",
                range(1, 3),
                "fr-frame-1/fr-harmonic-base",
                4.1656,
                3.454,
                13.0,
            ),
            **_expected_numbered_pairs(
                "ch-channel-1/ch-vn-frame-side-screw",
                range(1, 3),
                "fr-frame-1/fr-top-frame",
                2.1844,
                1.778,
                5.2207,
            ),
            # Owner Q13c: MHA-CH-VN-57 #8-32 x 5/8 through the .24 rocker-bracket
            # foot, one per bracket since the 2026-10-09 flip.
            **_expected_numbered_pairs(
                "ch-channel-1/ch-vn-bracket-hold-down-screw",
                range(1, 3),
                "fr-frame-1/fr-rocker-arm-support",
                4.1656,
                3.454,
                15.875 - 6.096,
            ),
        },
    }
    # The new magnifier joints are also checked across the top assembly.
    # Qualify the independent leaf oracles instead of duplicating their budgets.
    for pair in (
        frozenset(("sh-vn-thumb-screw-2", "mg-output-fixture-1")),
        frozenset(("mg-magnifying-lever-1", "mg-magnifying-bracket-1")),
        frozenset(("mg-magnifying-vertical-rod-1", "mg-magnifying-clamp-1")),
    ):
        qualified = frozenset(f"mg-magnifier-1/{part}" for part in pair)
        threaded_by_assembly["ha-harmonic-analyzer"][qualified] = (
            threaded_by_assembly["mg-magnifier"][pair]
        )
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
    # MHA-PD-VN-62's retained tube pin across the hole match-drilled through
    # MHA-PD-16 and the journal.
    cup_pin_pairs = {
        frozenset(("pd-vn-transgear-knob-cup-pin-1", "pd-transgear-knob-shaft-1")),
        frozenset(("pd-vn-transgear-knob-cup-pin-1", "pd-transgear-knob-cup-1")),
    }
    # MHA-PD-VN-66's chain mesh on the T24 at the closing station (#1457).
    connecting_link_pair = frozenset(
        ("pd-transgear-removable-1", "pd-vn-chain-connecting-link-1")
    )
    special_pairs = {
        "dt-drive-train": crank_pairs,
        "pd-paper-drive": cup_pin_pairs | {connecting_link_pair},
    }
    for name, expected_threaded in threaded_by_assembly.items():
        allowed = _interference_contracts.allowed_interference_pairs(name)
        # Exact pair equality also forbids tube/screw and cap/tube exemptions.
        assert set(allowed) == set(expected_threaded) | special_pairs.get(name, set())
        for pair, expected_limit in expected_threaded.items():
            assert allowed[pair] == pytest.approx(expected_limit), (
                name, sorted(pair), allowed[pair], expected_limit
            )
        assert all(limit >= 0.0 and math.isfinite(limit) for limit in allowed.values())

    drive_train_allowed = _interference_contracts.allowed_interference_pairs(
        "dt-drive-train"
    )
    assert not cam_pairs & set(drive_train_allowed)
    crank_allowed = _interference_contracts.allowed_interference_pairs("dt-drive-train")
    hub_pair = frozenset(("dt-crank-pin-1", "dt-crank-hub-1"))
    shaft_pair = frozenset(("dt-crank-pin-1", "dt-crankshaft-1"))
    # The CONTRACT-crank hub barrel (Ø22.25 since R9-38) sets the MHA-DT-09
    # pilot spans: a longer hub chord, and the shaft crossing further down
    # the taper. #1140 stood the pin 0.6 further proud (PIN_PROUD 4.45,
    # keeper-ring hole at 3.7), so a thinner stretch of the taper sits in
    # both receivers.
    assert 111.2 < crank_allowed[hub_pair] < 111.8
    assert 55.1 < crank_allowed[shaft_pair] < 55.6
    # MHA-CH-11: each 5/64 bar pivot pin pressed into its bar's Ø1.9558 ream
    # through both top-notch cheeks (6.35 bar less the 3.15 notch), and
    # MHA-CH-10: the same pin pressed into its rod's Ø1.9558 fork ream through
    # both tines (6.075 fork less the 2.675 slot); channel j's pin with
    # channel j's bar or rod only. MHA-CH-VN-53: each #4-40 apex set screw's
    # thread in its MHA-CH-08 ear's tap, over the 9.80 apex (R8 arch lifted
    # 1.80, #1371) less the Ø6.5 bore's height at the Ø2.845 envelope's edge;
    # screw n in bracket n.
    # MHA-CH-VN-55: each #1-72 x 5/32 keeper set screw in its own keeper's
    # crown tap (#53 drill). MHA-CH-VN-51: each #6-32 anchor's thread in its
    # MHA-CH-14 jam nut's #36 tap drill over the nut's thickness.
    channel_allowed = _interference_contracts.allowed_interference_pairs("ch-channel")
    assert channel_allowed == pytest.approx(
        {
            **{
                frozenset(
                    (f"ch-bar-pivot-pin-{n}", f"ch-amplitude-bar-{n}")
                ): _annulus_limit(1.984375, 1.9558, 3.20)
                for n in range(1, 21)
            },
            **{
                frozenset(
                    (f"ch-rod-pivot-pin-{n}", f"ch-connecting-rod-{n}")
                ): _annulus_limit(1.984375, 1.9558, 3.40)
                for n in range(1, 21)
            },
            **{
                frozenset(
                    (f"sh-vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}")
                ): _interference_contracts.PIVOT_EAR_SET_SCREW_LIMIT
                for n in (1, 2)
            },
            **{
                frozenset(
                    (f"ch-vn-fulcrum-set-screw-{n}", f"ch-fulcrum-keeper-{n}")
                ): _annulus_limit(1.854, 1.511, 3.96875)
                for n in range(1, 3)
            },
            **{
                frozenset(
                    (f"ch-vn-spring-hook-{n}", f"ch-anchor-jam-nut-{n}")
                ): _annulus_limit(*_interference_contracts.CHANNEL_ANCHOR_NUT_THREAD)
                for n in range(1, 21)
            },
        }
    )
    assert _interference_contracts.allowed_interference_pairs("unknown") == {}


def test_converged_stock_uses_distinct_semantic_base_joint_pairs() -> None:
    allowed = _interference_contracts.allowed_interference_pairs("ha-harmonic-analyzer")
    base = "fr-frame-1/fr-harmonic-base-1"
    foot = frozenset(("dt-drive-train-1/@FootScrew:1", base))
    stop = frozenset(("dt-drive-train-1/@SwingStopScrew:1", base))
    assert foot != stop
    assert allowed[foot] == pytest.approx(_annulus_limit(2.8448, 2.261, 8.725))
    assert stop in allowed
    assert not any(
        "sh-vn-fillister-screw-90280a108-" in name
        for pair in allowed
        for name in pair
    )


def test_kit_fit_pairs_keep_member_roles_and_four_physical_instances() -> None:
    allowed = _interference_contracts.allowed_interference_pairs(
        "ch-rocker-arm-tl-oblique-jig"
    )
    kit = {
        pair: limit
        for pair, limit in allowed.items()
        if any(name.startswith("@HoldDownStud:") for name in pair)
    }
    assert len(kit) == 8
    for number in range(1, 5):
        for role, triple in (
            ("TNut", _interference_contracts.JIG_T_NUT_THREAD),
            ("FlangeNut", _interference_contracts.JIG_FLANGE_NUT_THREAD),
        ):
            pair = frozenset((f"@HoldDownStud:{number}", f"@{role}:{number}"))
            assert kit[pair] == pytest.approx(_annulus_limit(*triple))

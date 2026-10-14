from __future__ import annotations

import ast
from collections import Counter
from itertools import product
from pathlib import Path

import pytest

import _interference_contracts
import build_sm_summing_assembly as asm
import fr_top_frame_spec as top_frame
import vn_knife_hanger_stud_spec as hanger_screw
import vn_knife_hanger_washer_spec as hanger_washer
from build_sm_knife_mount import CASTING_UNDERSIDE_Y
from build_sm_summing_assembly import _assert_hanger_axis_positive_y


def _transform(rotation_rows: list[list[float]]) -> list[float]:
    return [
        *(value for row in rotation_rows for value in row),
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def test_cut_hex_bolt_seats_on_the_new_washer_and_faced_crossbar_top() -> None:
    assert hanger_screw.CATALOG_LENGTH == pytest.approx(50.8)
    assert hanger_screw.LENGTH == hanger_screw.UNDERHEAD_LEN == pytest.approx(46.70)
    assert hanger_screw.LENGTH_BAND == pytest.approx((0.15, -0.15))
    assert hanger_screw.LENGTH_MIN == pytest.approx(46.55)
    assert hanger_screw.LENGTH_MAX == pytest.approx(46.85)
    assert hanger_washer.THICKNESS == pytest.approx(
        (hanger_washer.THICKNESS_MIN + hanger_washer.THICKNESS_MAX) / 2.0
    )
    assert not hasattr(asm, "HANGER_SPOTFACE_Y")
    assert asm.HANGER_WASHER_Y == pytest.approx(
        CASTING_UNDERSIDE_Y + top_frame.HANGER_GRIP
    )
    assert asm.HANGER_WASHER_Y == pytest.approx(asm.CROSSBAR_TOP_Y)
    assert top_frame.HANGER_GRIP == pytest.approx(top_frame.RING_HEIGHT)
    assert asm.HANGER_UNDERHEAD_Y == pytest.approx(
        asm.HANGER_WASHER_Y + hanger_washer.THICKNESS
    )
    assert asm.HANGER_STUD_Y + hanger_screw.UNDERHEAD_LEN == pytest.approx(
        asm.HANGER_UNDERHEAD_Y
    )
    assert asm.HANGER_WASHER_Y == pytest.approx(1036.2)
    assert asm.HANGER_UNDERHEAD_Y == pytest.approx(1037.4827)
    assert asm.HANGER_STUD_Y == pytest.approx(990.7827)


def test_reach_extrema_include_every_cut_length_grip_and_washer_corner() -> None:
    reaches = [
        length - grip - thickness
        for length, grip, thickness in product(
            (hanger_screw.LENGTH_MIN, hanger_screw.LENGTH_MAX),
            (
                top_frame.HANGER_GRIP - top_frame.HANGER_GRIP_TOL,
                top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL,
            ),
            (hanger_washer.THICKNESS_MIN, hanger_washer.THICKNESS_MAX),
        )
    ]
    assert min(reaches) == pytest.approx(asm.HANGER_REACH_MIN)
    assert max(reaches) == pytest.approx(asm.HANGER_REACH_MAX)
    assert min(reaches) == pytest.approx(8.349)
    assert max(reaches) == pytest.approx(9.4856)
    assert asm.HANGER_REACH == pytest.approx(8.9173)


@pytest.mark.parametrize(
    ("constant", "value", "message"),
    [
        ("HANGER_WASHER_Y", 1036.3, "washer lower face"),
        ("HANGER_STUD_Y", 990.8, "bolt under-head face"),
        ("HANGER_THREAD_SPARE", -0.01, "useful full-form tail"),
    ],
)
def test_stack_rejects_unseated_bearing_faces_or_insufficient_inspected_tail(
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    value: float,
    message: str,
) -> None:
    monkeypatch.setattr(asm, constant, value)
    with pytest.raises(RuntimeError, match=message):
        asm._assert_knife_hanger_stack()


def _placed_transform(y: float, z: float) -> list[float]:
    transform = _transform([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    transform[9:12] = [asm.KNIFE[0] / 1000.0, y / 1000.0, z / 1000.0]
    return transform


@pytest.mark.parametrize(
    "station_z", [asm.SUMMING_Z + asm.HEX_Z_MID, asm.SUMMING_Z - asm.HEX_Z_MID]
)
def test_instance_readback_seats_both_bearing_faces_at_each_station(
    station_z: float,
) -> None:
    origin = asm._assert_hanger_seat_placement(
        "vn-knife-hanger-stud-1",
        "vn-knife-hanger-washer-1",
        station_z,
        _placed_transform(asm.HANGER_STUD_Y, station_z),
        _placed_transform(asm.HANGER_WASHER_Y, station_z),
    )
    assert origin == pytest.approx([asm.KNIFE[0], asm.HANGER_STUD_Y, station_z])


@pytest.mark.parametrize(
    ("part", "axis", "message"),
    [
        ("screw", 0, "intended knife station"),
        ("screw", 2, "intended knife station"),
        ("washer", 0, "not coaxial"),
        ("washer", 2, "not coaxial"),
        ("washer", 1, "lower-face/faced-top gap"),
        ("screw", 1, "under-head/washer-upper-face gap"),
    ],
)
def test_instance_readback_rejects_drifted_hardware(
    part: str, axis: int, message: str
) -> None:
    station_z = asm.SUMMING_Z + asm.HEX_Z_MID
    screw_transform = _placed_transform(asm.HANGER_STUD_Y, station_z)
    washer_transform = _placed_transform(asm.HANGER_WASHER_Y, station_z)
    transforms = {"screw": screw_transform, "washer": washer_transform}
    transforms[part][9 + axis] += 0.0001  # 0.1 mm physical displacement
    with pytest.raises(RuntimeError, match=message):
        asm._assert_hanger_seat_placement(
            "vn-knife-hanger-stud-1",
            "vn-knife-hanger-washer-1",
            station_z,
            screw_transform,
            washer_transform,
        )


def test_new_washers_add_two_instances_to_the_thirteen_component_recipe() -> None:
    tree = ast.parse(Path(asm.__file__).read_text(encoding="utf-8"))
    builds = [
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    ]
    assert len(builds) == 1
    counts: Counter[str] = Counter()

    class Placements(ast.NodeVisitor):
        multiplier = 1

        def visit_For(self, node: ast.For) -> None:
            placement_calls = [
                call
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "place_component"
            ]
            if not placement_calls:
                return
            if isinstance(node.iter, ast.Tuple):
                length = len(node.iter.elts)
            else:
                assert isinstance(node.iter, ast.Name)
                assert node.iter.id == "KNIFE_DOWEL_X_OFFSETS"
                length = len(asm.KNIFE_DOWEL_X_OFFSETS)
            previous = self.multiplier
            self.multiplier *= length
            self.generic_visit(node)
            self.multiplier = previous

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == "place_component":
                assert isinstance(node.args[1], ast.Constant)
                counts[node.args[1].value] += self.multiplier
            self.generic_visit(node)

    Placements().visit(builds[0])
    assert counts == {
        "sm-knife-mount": 2,
        "vn-knife-hanger-stud": 2,
        "vn-knife-hanger-washer": 2,
        "vn-knife-mount-dowel": 4,
        "sm-summing-lever": 1,
        "vn-boss-hook": 1,
        "vn-counter-spring": 1,
        "sm-gooseneck": 1,
        "sm-gooseneck-spring-screw": 1,
    }
    assert sum(counts.values()) == 15
    assert sum(counts.values()) - counts["vn-knife-hanger-washer"] == 13


def test_washer_seat_pairs_allow_exact_contacts_but_no_solid_overlap() -> None:
    summing = _interference_contracts.allowed_interference_pairs("sm-summing")
    harmonic = _interference_contracts.allowed_interference_pairs(
        "ha-harmonic-analyzer"
    )
    for number in (1, 2):
        pair = frozenset(
            (f"vn-knife-hanger-stud-{number}", f"vn-knife-hanger-washer-{number}")
        )
        assert summing[pair] == 0.0
        assert harmonic[frozenset(f"sm-summing-1/{part}" for part in pair)] == 0.0
        seat_pair = frozenset(
            (
                f"sm-summing-1/vn-knife-hanger-washer-{number}",
                "fr-frame-1/fr-top-frame-1",
            )
        )
        assert harmonic[seat_pair] == 0.0


def test_hanger_axis_validation_accepts_authored_positive_y_axis() -> None:
    _assert_hanger_axis_positive_y(
        "vn-knife-hanger-stud-1",
        _transform([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
    )


@pytest.mark.parametrize(
    "rotation_rows",
    [
        [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
        [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]],
    ],
)
def test_hanger_axis_validation_rejects_transverse_or_reversed_axis(
    rotation_rows: list[list[float]],
) -> None:
    with pytest.raises(RuntimeError, match=r"local \+Y fastener axis.*assembly \+Y"):
        _assert_hanger_axis_positive_y(
            "vn-knife-mount-dowel-1",
            _transform(rotation_rows),
        )

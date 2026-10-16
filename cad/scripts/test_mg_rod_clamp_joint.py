"""Offline worst-case contract for the MHA-MG-004 rod's threaded seat in the
MHA-MG-002 hex clamp (#1559): engagement, tap depths, relief, floor wall,
shoulder land and the installed coaxial/coplanar pose."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_mg_magnifier_assembly as magnifier
import mg_magnifying_clamp_geom as clamp
import mg_magnifying_vertical_rod_geom as rod
import mg_rod_clamp_joint as joint
import vn_lever_wire_geom as wire
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, blind_cut_dia_mm
from _printed_tolerance import printed_band_mm

_IN = 25.4
_P = _IN / 40.0
_D = THREAD_MAJOR_MM["#4-40"]


def test_thread_is_the_thumb_screws_size_from_asme_b11() -> None:
    assert joint.THREAD == "#4-40"
    assert joint.THREAD_PITCH == pytest.approx(0.635)
    assert joint.THREAD_MAJOR == pytest.approx(2.845)
    assert joint.ENGAGEMENT_MIN == pytest.approx(1.5 * _D)
    # B1.1 #4-40 UNC-2A: PD min .0925 in, basic thread height 0.649519 P.
    assert joint.THREAD_ROOT_2A_MIN == pytest.approx((0.0925 - 0.649519 / 40) * _IN)
    assert joint.THREAD_BASIC_MINOR == pytest.approx(_D - 1.082532 * _P)


def test_full_thread_engagement_is_one_and_a_half_diameters_at_worst() -> None:
    shortest_thread = 7.50 - 0.25
    widest_relief = 1.40 + 0.20
    engaged = shortest_thread - widest_relief - _P
    assert joint.ENGAGEMENT_WORST == pytest.approx(engaged)
    assert engaged == pytest.approx(5.015)
    assert engaged >= 1.5 * _D


def test_relief_takes_the_die_run_out_under_the_2a_root() -> None:
    assert joint.RELIEF_WIDTH - 0.20 >= 1.5 * _P
    assert joint.RELIEF_DIA + 0.10 <= joint.THREAD_ROOT_2A_MIN
    assert joint.RELIEF_DIA + 0.10 < joint.THREAD_BASIC_MINOR


def test_tap_depths_follow_the_blind_seat_law_at_the_xx_band() -> None:
    band = printed_band_mm(joint.HOLE_DEPTH_PLACES)
    assert band == 0.51
    assert joint.HOLE_DEPTH_BAND == band
    assert joint.ROD_TAP_SPEC.kind == "tapped"
    assert joint.ROD_TAP_SPEC.end == "blind"
    assert joint.ROD_TAP_SPEC.size == "#4-40"
    thread = joint.ROD_TAP_SPEC.overrides_mm["ThreadDepth"]
    drill = joint.ROD_TAP_SPEC.depth_mm
    assert (thread, drill) == (8.55, 12.75)
    # The rod's longest thread stops 0.25 short of the shallowest full thread,
    # so the shoulder -- not the tip -- seats.
    assert (thread - band) - (7.50 + 0.25) >= 0.25 - 1e-9
    # A plug tap's five-pitch lead fits under the deepest thread.
    assert (drill - band) - (thread + band) >= 5.0 * _P - 1e-9
    assert blind_cut_dia_mm(joint.ROD_TAP_SPEC) == TAP_DRILL_MM["#4-40"]


def test_rod_tap_floor_leaves_two_millimetres_under_the_lever_bore() -> None:
    drill_r_max = (TAP_DRILL_MM["#4-40"] + 0.10) / 2.0
    point = drill_r_max / math.tan(math.radians(59.0))
    bore_r_max = (6.2 + 0.10) / 2.0
    floor = (clamp.LEVER_BORE_Y - 0.51) - bore_r_max - (12.75 + 0.51) - point
    assert clamp.ROD_TAP_FLOOR_WALL_WORST == pytest.approx(floor)
    assert floor >= 2.0
    assert clamp.LEVER_BORE_Y == 19.65
    assert clamp.BLOCK_HEIGHT == 28.65


def test_thumb_screw_thread_is_one_and_a_half_diameters_at_worst() -> None:
    top_to_bore_min = clamp.TOP_TO_BORE - 2.0 * 0.51
    thread = top_to_bore_min - (6.2 + 0.10) / 2.0 - 0.25
    assert clamp.THUMB_ENGAGEMENT_WORST == pytest.approx(thread)
    assert thread >= 1.5 * _D
    assert clamp.THUMB_TAP_SPEC.size == joint.ROD_TAP_SPEC.size
    assert clamp.THUMB_TAP_SPEC.overrides_mm["ThreadDepth"] == pytest.approx(5.9)


def test_hex_stock_and_extent_along_the_lever() -> None:
    assert clamp.HEX_AF == pytest.approx(7.0 / 16.0 * _IN)
    assert clamp.BLOCK_DEPTH == pytest.approx(clamp.HEX_AF * 2.0 / math.sqrt(3.0))
    worst_flat_wall = (clamp.HEX_AF - clamp.HEX_AF_BAND) / 2.0 - (6.2 + 0.10) / 2.0
    assert worst_flat_wall - 0.10 - 0.05 >= 2.0


def test_shoulder_land_seats_flat_all_round() -> None:
    land = ((5.0 - 0.05 - 0.5) - (_D + 0.05 + 0.5)) / 2.0
    assert rod.SEAT_LAND_WORST == pytest.approx(land)
    assert land >= 0.5


def test_part_geometries_share_only_the_joint_contract() -> None:
    clamp_src = Path(clamp.__file__).read_text(encoding="utf-8")
    rod_src = Path(rod.__file__).read_text(encoding="utf-8")
    assert "mg_magnifying_vertical_rod_geom" not in clamp_src
    assert "mg_magnifying_clamp_geom" not in rod_src
    assert "from mg_rod_clamp_joint import" in clamp_src
    assert "from mg_rod_clamp_joint import" in rod_src


def test_installed_rod_seats_coaxial_with_the_thumb_screw_in_the_wire_plane() -> None:
    clamp_face_y = magnifier.LEVER_ROD_Y - clamp.LEVER_BORE_Y
    assert magnifier.VROD_TOP_Y - rod.SHOULDER_X == pytest.approx(clamp_face_y)
    assert magnifier.VROD_Z == magnifier.LEVER_ROD_Z
    assert magnifier.LEVER_ROD_Z == pytest.approx(wire.DRUM_END_Z, abs=1e-9)
    assert wire.HOOK_Z == pytest.approx(magnifier.VROD_Z, abs=1e-9)


@pytest.mark.parametrize(
    ("replacement", "bad", "failure"),
    (
        ("ROD_THREAD_LEN = 7.50", "6.70", "1.5D"),
        ("RELIEF_WIDTH = 1.40", "1.10", "run-out"),
        ("RELIEF_DIA = 1.75", "1.90", "2A root"),
    ),
)
def test_joint_guards_reject_lost_margins(
    replacement: str, bad: str, failure: str
) -> None:
    source = Path(joint.__file__).read_text(encoding="utf-8")
    assert source.count(replacement) == 1
    changed = source.replace(replacement, f"{replacement.split(' = ')[0]} = {bad}")
    with pytest.raises(AssertionError, match=failure):
        exec(compile(changed, str(joint.__file__), "exec"), {})

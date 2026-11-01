"""Offline worst-case contract for the MHA-MG-04 rod's threaded seat in the
MHA-MG-02 hex clamp (#1559): engagement, tap depths, relief, floor wall,
shoulder land and the installed coaxial/coplanar pose."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import build_mg_magnifier_assembly as magnifier
import mg_magnifying_clamp_geom as clamp
import mg_magnifying_vertical_rod_geom as rod
import mg_rod_clamp_joint as joint
import sh_vn_music_wire_lever_geom as wire
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

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
    # The thread length keeps its 7.50 mm model and prints .30 at .XX.
    band = printed_band_mm(2, unit="in")
    shortest_thread = 0.30 * _IN - band
    widest_relief = 0.06 * _IN + band
    engaged = shortest_thread - widest_relief - _P
    assert joint.ENGAGEMENT_WORST == pytest.approx(engaged)
    assert engaged >= 1.5 * _D


def test_relief_takes_the_die_run_out_under_the_2a_root() -> None:
    # Width at the .XX band, its narrowest still over the die's 1.5P run-out.
    band = printed_band_mm(joint.RELIEF_WIDTH_PLACES, unit="in")
    assert joint.PRINTED_XX_BAND == pytest.approx(band)
    assert joint.RELIEF_WIDTH_MIN >= 1.5 * _P
    # Ø as the single limit MAX: the model value is the limit.
    assert joint.RELIEF_DIA_TOL_TYPE == 6  # swTolType_e.swTolMAX
    assert joint.RELIEF_DIA_MAX <= joint.THREAD_ROOT_2A_MIN
    assert joint.RELIEF_DIA_MAX < joint.THREAD_BASIC_MINOR


def test_tap_depths_follow_the_blind_seat_law_at_the_xx_band() -> None:
    band = printed_band_mm(joint.HOLE_DEPTH_PLACES, unit="in")
    assert joint.HOLE_DEPTH_BAND == pytest.approx(band)
    assert joint.ROD_TAP_SPEC.kind == "tapped"
    assert joint.ROD_TAP_SPEC.end == "blind"
    assert joint.ROD_TAP_SPEC.size == "#4-40"
    thread = joint.ROD_TAP_SPEC.overrides_mm["ThreadDepth"]
    drill = joint.ROD_TAP_SPEC.depth_mm
    longest_rod_thread = 0.30 * _IN + band
    # The rod's longest thread stops a reserve short of the shallowest full
    # thread, so the shoulder -- not the tip -- seats.
    assert (thread - band) - longest_rod_thread >= joint.SEAT_TIP_RESERVE - 1e-9
    # A plug tap's five-pitch lead fits under the deepest thread.
    assert (drill - band) - (thread + band) >= 5.0 * _P - 1e-9
    assert blind_cut_dia_mm(joint.ROD_TAP_SPEC) == TAP_DRILL_MM["#4-40"]


def test_rod_tap_floor_holds_the_wall_target_under_the_lever_bore() -> None:
    drilled = drilled_oversize_mm(unit="in")
    drill_r_max = (TAP_DRILL_MM["#4-40"] + drilled) / 2.0
    point = drill_r_max / math.tan(math.radians(59.0))
    bore_r_max = (clamp.LEVER_BORE_DIA + drilled) / 2.0
    slope = math.tan(math.radians(0.3))
    band = printed_band_mm(2, unit="in")
    # The exempt 19.95 bore height prints .79.
    bore_y_min = 0.79 * _IN - band
    floor = bore_y_min - bore_r_max - (joint.ROD_TAP_DRILL_DEPTH + band) - point - clamp.STOCK_ENVELOPE_MAX * slope
    assert clamp.ROD_TAP_FLOOR_WALL_WORST == pytest.approx(floor)
    assert floor >= WALL_TARGET_MM
    assert clamp.LEVER_BORE_Y == 19.95  # fixed approved hook/seat interface
    assert clamp.BLOCK_HEIGHT - clamp.LEVER_BORE_Y == pytest.approx(clamp.TOP_TO_BORE)


def test_thumb_screw_thread_is_one_and_a_half_diameters_at_worst() -> None:
    # Female wall alone is NOT installed FULL overlap: the stock screw's
    # chamfered male end starts above its contact with the lever.
    drilled = drilled_oversize_mm(unit="in")
    edge = printed_band_mm(2, unit="in")  # the .010 edge break
    female_wall = clamp.TOP_TO_BORE_MIN - (clamp.LEVER_BORE_DIA + drilled) / 2.0 - edge - clamp.BORE_FULL_ANGULAR
    assert clamp.THUMB_ENGAGEMENT_WORST < female_wall
    assert clamp.THUMB_ENGAGEMENT_WORST >= 1.5 * _D
    assert clamp.THUMB_TAP_SPEC.size == joint.ROD_TAP_SPEC.size
    assert clamp.THUMB_TAP_SPEC.overrides_mm["ThreadDepth"] == pytest.approx(clamp.TOP_TO_BORE - clamp.LEVER_BORE_DIA / 2.0)


def test_hex_stock_and_extent_along_the_lever() -> None:
    assert clamp.HEX_AF == pytest.approx(0.5 * _IN)
    assert clamp.BLOCK_DEPTH == pytest.approx(clamp.HEX_AF * 2.0 / math.sqrt(3.0))
    # The ordinary full-height size/angle profile, not nominal regular-hex
    # corners, owns the conservative complete-body run-off distance.
    wander = clamp.STOCK_ENVELOPE_MAX * math.tan(math.radians(0.3))
    assert wander == pytest.approx(clamp.BORE_FULL_ANGULAR)


def test_shoulder_land_seats_flat_all_round() -> None:
    # The 7/32 rod at its supplier minimum and the tap mouth at its largest,
    # each broken .010.
    edge = 0.254
    land = ((7.0 / 32.0 * _IN - 0.127 - 2.0 * edge) - (_D + 0.0508 + 2.0 * edge)) / 2.0
    assert rod.SEAT_LAND_WORST == pytest.approx(land)
    assert land >= rod.SEAT_LAND_MIN


def test_relief_roots_stand_inside_the_tap_mouth_off_the_seat_annulus() -> None:
    # r2: both relief corners carry a radius MAX (the model at the limit). At
    # the largest relief Ø and radius the shoulder-side root's outer edge stays
    # inside the tap's minor (its #43 drill), itself inside the broken mouth
    # where the shoulder's seat annulus starts.
    assert joint.RELIEF_ROOT_R_TOL_TYPE == 6
    outer = joint.RELIEF_DIA_MAX + 2.0 * joint.RELIEF_ROOT_R
    assert joint.RELIEF_ROOT_OUTER_DIA == pytest.approx(outer)
    assert joint.ROD_TAP_MINOR_DIA == TAP_DRILL_MM["#4-40"] == clamp.ROD_TAP_DRILL_DIA
    assert outer < joint.ROD_TAP_MINOR_DIA < _D
    assert outer < _D + 0.0508 + 2.0 * 0.254
    # Both roots fit the narrowest relief and sit inside it: full thread, the
    # worst engagement and the die's run-out are unchanged.
    assert 2.0 * joint.RELIEF_ROOT_R <= joint.RELIEF_WIDTH_MIN
    assert joint.DIE_RUNOUT <= joint.RELIEF_WIDTH_MIN


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
        ("RELIEF_WIDTH = 1.524", "0.762", "run-out"),
        ("RELIEF_DIA = 1.8288", "1.9558", "2A root"),
        ("RELIEF_ROOT_R = 0.2032", "0.762", "narrowest relief"),
        ("RELIEF_ROOT_R = 0.2032", "0.3048", "seat annulus"),
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

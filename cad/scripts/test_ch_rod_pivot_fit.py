"""Offline contract: the rod fork straddles its rocker arm in one plane, and
the MHA-CH-10 pin is pressed into the fork's reamed tines and runs in the
arm. The printed BASIC/profile controls and fork bands prove the crotch fit;
the pin spec's older radius-band budget is a separate regression, not the
current arc acceptance. Press fit, ends dressed flush: the user's ruling
(2026-10-09, PR #1292 review F1), the MHA-CH-11 bar pin's joint
(``test_ch_bar_pivot_fit``). Drawing-guidelines.md rule 17 (walls and webs)
governs the remaining fits.

``ch_rod_pivot_pin_spec`` reads only the two parts it joins; the restated
floors and the swing it designs for are pinned to their sources here.
"""

from __future__ import annotations

import ast
import itertools
import math
from pathlib import Path

import numpy as np
import pytest

import _config
import cam_plane
import ch_amplitude_bar_spec as bar
import ch_bar_pivot_pin_spec as bar_pin
import channel_frame_geom as frame
import channel_kinematics as ck
import ch_connecting_rod_notes as rod_notes
import ch_connecting_rod_spec as rod
import ch_rocker_arm_notes as arm_notes
import ch_rocker_arm_spec as arm
import _rocker_interface as rocker_interface
import ch_rod_pivot_pin_spec as pin
import dt_cylinder_gear_spec as gear
import draw_ch_rocker_arm as arm_drawing
import rocker_bank_layout as bank
from _drawing_hidden_sketches import curate_view_dimensions
from _hole_spec import NUMBER_DRILL_MM


def test_restated_floors_are_their_sources() -> None:
    drilled = _config.title_block("drilled_hole", unit=arm.UNIT)
    assert drilled["minus_in"] == 0.0
    assert drilled["plus_in"] * 25.4 == pytest.approx(pin.DRILLED_PLUS)
    assert pin.RUNNING_FLOOR == bank.RUNNING_FLOOR
    assert pin.MARGIN_SPARE == bank.MARGIN_SPARE
    assert pin.ROD_LINEAR_2PL == pytest.approx(
        _config.title_block("linear_2pl", unit=rod.UNIT)["band_in"] * 25.4
    )
    # The hubs set the pitch the neighbour stack is judged at.
    assert arm.HUB_LENGTH == bank.PITCH and arm.HUB_LENGTH_BAND[1] == 0.0
    # FN2's 0.85 thou cap, as the bar pin's press.
    assert pin.PRESS_INTERFERENCE_MAX == pytest.approx(0.0215900, abs=1e-9)
    assert pin.PRESS_INTERFERENCE_MAX == bar_pin.PRESS_INTERFERENCE_MAX


def test_the_rod_arm_and_cam_share_one_plane() -> None:
    assert bank.ARM_MID_DZ == cam_plane.CAM_MID_DZ
    assert cam_plane.CAM_MID_DZ == pytest.approx(
        -(gear.FACE_WIDTH + gear.CAM_THICKNESS) / 2.0
    )
    # The pin is centred on the fork, which is centred on the rod plane.
    assert pin.PIN_INSTALLED_LENGTH == rod.FORK_THICKNESS


def test_the_pin_is_pressed_in_the_fork_and_runs_in_the_arm() -> None:
    """The bar pin's joint: the same drill rod pressed into the same Ø1.9558
    +0.02286/+0.0127 ream, running in a drilled #47 in the moving member."""
    assert pin.PIN_DIA == bar_pin.PIN_DIA
    assert pin.PIN_DIA_TOLERANCE == bar_pin.PIN_DIA_TOLERANCE
    assert pin.ROD_HOLE_DIA == rod.PIN_HOLE_DIA == bar.TOP_PIN_HOLE_DIA
    assert pin.ROD_HOLE_BAND == rod.PIN_HOLE_BAND == bar.TOP_PIN_HOLE_BAND
    assert arm.ROD_HOLE_SPEC.kind == "drilled_number"
    assert arm.ROD_HOLE_SPEC.size == "#47"
    assert pin.PIN_END_PROUD_MAX == 0.0
    # Nothing is sunk into the tines and nothing is upset (the peened design).
    for gone in ("PIN_HOLE_SPEC", "PIN_HOLE_CSK_DIA", "PIN_HOLE_CSK_BAND"):
        assert not hasattr(rod, gone)
    for gone in ("PIN_CSK_DIA", "RETENTION_OVERLAP_MIN"):
        assert not hasattr(pin, gone)


def test_worst_case_joint_budget() -> None:
    b = pin.BUDGET
    # The press, at the pin's +/-0.00508 against the ream's +0.02286/+0.0127.
    assert b["interference_min"] == pytest.approx(0.000635, abs=1e-6)
    assert b["interference_max"] == pytest.approx(0.020955, abs=1e-6)
    assert 0.0 < b["interference_min"] <= b["interference_max"]
    assert b["interference_max"] <= pin.PRESS_INTERFERENCE_MAX
    # The run, in the arm's #47 (.0785 +.004/0).
    assert b["running_clearance_min"] == pytest.approx(0.004545, abs=1e-6)
    assert b["running_clearance_max"] == pytest.approx(0.116305, abs=1e-6)
    assert b["side_clearance_min"] == pytest.approx(0.127, abs=1e-6)
    assert b["side_clearance_max"] == pytest.approx(0.2794, abs=1e-6)
    assert b["neighbour_clearance_min"] == pytest.approx(0.4271, abs=1e-6)
    assert b["neighbour_clearance_min"] >= pin.NEIGHBOUR_CLEARANCE_MIN
    assert b["tine_min"] == pytest.approx(1.651, abs=1e-6)
    assert b["tine_bearing_land_min"] == b["tine_min"]
    assert b["tine_bearing_land_min"] >= pin.RULE12_WALL_FLOOR
    assert b["crown_wall_min"] >= pin.RULE12_WALL_TARGET
    assert b["crotch_clearance_min"] >= pin.CROTCH_CLEARANCE_MIN
    assert b["bridge_min"] == pytest.approx(2.794, abs=1e-6)
    assert b["bridge_min"] >= pin.BRIDGE_TARGET
    # Dressing stock: the shortest blank the .26 MIN limit allows still covers
    # the thickest .246 fork; a longer blank only dresses back further.
    assert b["blank_excess_min"] == pytest.approx(0.3556, abs=1e-6)
    assert "blank_excess_max" not in b
    assert not any(key.startswith(("upset", "retention")) for key in b)


def test_strap_running_clearance_uses_both_printed_size_bands() -> None:
    slot_places = rod_notes.DRAWING_PRECISION["ForkSlotProfile"]["SlotWidth"]
    strap_places = arm_notes.DRAWING_PRECISION["Strap"]["StrapThickness"]

    def printed(value: float, places: int) -> float:
        return round(value / 25.4, places) * 25.4

    slot_limits = tuple(
        printed(rod.FORK_SLOT_WIDTH, slot_places) + printed(band, slot_places)
        for band in rod.FORK_SLOT_BAND
    )
    strap_limits = tuple(
        printed(arm.ARM_THICKNESS, strap_places) + printed(band, strap_places)
        for band in arm.ARM_THICKNESS_BAND
    )
    minimum = slot_limits[1] - strap_limits[0]
    maximum = slot_limits[0] - strap_limits[1]
    assert minimum >= pin.RUNNING_FLOOR
    assert minimum == pytest.approx(pin.BUDGET["side_clearance_min"])
    assert maximum == pytest.approx(pin.BUDGET["side_clearance_max"])


def test_the_pin_bears_on_the_whole_tine() -> None:
    """PR #1292 review F1: the land the pin bears on in each tine is the
    thinnest tine itself, the tine's own printed band (#982), and it holds
    drawing-guidelines.md rule 17 (walls and webs)'s 1.5 floor. Positive
    control: the withdrawn 90-degree Ø3.2 countersink sunk into each tine
    mouth, on the #47's largest drill, left under that floor."""
    tine = rod.TINE_THICKNESS + rod.TINE_BAND[1]
    assert tine == rod.TINE_MIN
    assert pin.BUDGET["tine_bearing_land_min"] == pytest.approx(tine, abs=1e-12)
    assert tine >= pin.RULE12_WALL_FLOOR
    withdrawn_leg = (3.2 - NUMBER_DRILL_MM["#47"]) / 2.0
    assert tine - withdrawn_leg < pin.RULE12_WALL_FLOOR


def test_neighbour_stack_fills_the_inter_arm_gap_exactly() -> None:
    """The gap (pitch less the thickest arm) holds both side clearances,
    the thickest fork over its tines, the two straps' offsets from their hubs
    and the neighbour clearance: the stack closes with nothing left out. The
    dressed ends are flush, so no pin end stands in it."""
    b = pin.BUDGET
    w_max = rod.FORK_THICKNESS + rod.FORK_THICKNESS_BAND[0]
    # The fork over the tines is a reference: its limits are the tines' and
    # the slot's.
    assert w_max == pytest.approx(
        2.0 * (rod.TINE_THICKNESS + rod.TINE_BAND[0])
        + rod.FORK_SLOT_WIDTH
        + rod.FORK_SLOT_BAND[0]
    )
    float_total = b["side_clearance_max"]
    assert bank.PITCH - (
        w_max + float_total + arm.STRAP_HUB_SYMMETRY
    ) == pytest.approx(b["neighbour_clearance_min"])


def _corner_gap(proud: float, strap_offsets: tuple[float, ...]) -> float:
    """Least axial gap between rod j's north-most point and rod j + 1's
    south-most, over every corner of the bands both rods and both arms are
    printed to, built as positions: hub j's mid-plane at 0 and hub j + 1's
    half the two hub lengths north; each strap's mid-plane off its hub's
    by one of ``strap_offsets``; each fork's slot anywhere it still clears
    its strap; each fork's outer face a tine past its slot's wall; each
    dressed pin end ``proud`` of its fork face."""
    t_band = [arm.ARM_THICKNESS + d for d in arm.ARM_THICKNESS_BAND]
    tine_band = [rod.TINE_THICKNESS + d for d in rod.TINE_BAND]
    s_band = [rod.FORK_SLOT_WIDTH + d for d in rod.FORK_SLOT_BAND]
    hubs = [arm.HUB_LENGTH + d for d in arm.HUB_LENGTH_BAND]

    def reach(sign: int) -> list[float]:
        """Offsets of a rod's outer face (pin end included) from its own
        hub's mid-plane, toward the neighbour (+1 north, -1 south)."""
        out = []
        for e, t, tine, s, side in itertools.product(
            strap_offsets, t_band, tine_band, s_band, (-1.0, 1.0)
        ):
            slot_centre = e + side * (s - t) / 2.0
            out.append(sign * (slot_centre + sign * (s / 2.0 + tine + proud)))
        return out

    north_j = max(reach(+1))  # rod j's north-most point
    south_next = max(reach(-1))  # how far rod j + 1 reaches south
    pitch = min((a + b) / 2.0 for a, b in itertools.product(hubs, hubs))
    return pitch - north_j - south_next


def test_opposed_neighbour_forks_clear_at_every_band_corner() -> None:
    """PR #1292 review F2: an independent construction of the neighbour
    clearance, rod by rod from positions, not the spec's closed form. Rod j
    leans north on a strap set north of its hub, rod j + 1 south on one set
    south; the budget is exactly that corner."""
    half_zone = arm.STRAP_HUB_SYMMETRY / 2.0
    gap = _corner_gap(pin.PIN_END_PROUD_MAX, (-half_zone, half_zone))
    assert gap == pytest.approx(pin.BUDGET["neighbour_clearance_min"], abs=1e-9)
    assert gap == pytest.approx(0.4271, abs=1e-9)
    assert gap >= pin.NEIGHBOUR_CLEARANCE_MIN
    # Positive controls: the strap symmetry is in the corner (centred straps
    # gain its whole zone), and the withdrawn peened pin (0.10 proud each
    # end) on these straps would have broken the 0.35 floor the earlier
    # budget claimed it held.
    centred = _corner_gap(pin.PIN_END_PROUD_MAX, (0.0,))
    assert centred - gap == pytest.approx(arm.STRAP_HUB_SYMMETRY, abs=1e-9)
    assert _corner_gap(0.10, (-half_zone, half_zone)) < pin.NEIGHBOUR_CLEARANCE_MIN


def test_the_assembly_press_allowance_is_this_joint() -> None:
    """_interference_contracts restates the modelled press as literals (every
    assembly imports it); they must be the nominal pin, the fork's reamed
    hole and the two tines, and name channel j's pin with channel j's rod
    only. The channel's only other press pairs are the bar pins', and its
    thread pairs are the two apex set screws' in the bracket ears, the two
    fulcrum set screws' modelled thread in their keepers and each anchor's
    thread in its jam nut."""
    import _interference_contracts as ic

    pin_dia, hole_dia, engaged = ic.ROD_PIVOT_PIN_PRESS
    assert pin_dia == pytest.approx(pin.PIN_DIA, abs=1e-9)
    assert hole_dia == rod.PIN_HOLE_DIA
    assert engaged == pytest.approx(rod.FORK_THICKNESS - rod.FORK_SLOT_WIDTH, abs=1e-9)
    pairs = ic.allowed_interference_pairs("ch-channel")
    rod_pairs = {
        frozenset((f"ch-rod-pivot-pin-{n}", f"ch-connecting-rod-{n}"))
        for n in range(1, 21)
    }
    bar_pairs = {
        frozenset((f"ch-bar-pivot-pin-{n}", f"ch-amplitude-bar-{n}"))
        for n in range(1, 21)
    }
    set_screw_pairs = {
        frozenset((f"sh-vn-arbor-set-screw-{n}", f"ch-pivot-bracket-{n}")) for n in (1, 2)
    } | {
        frozenset((f"ch-vn-fulcrum-set-screw-{n}", f"ch-fulcrum-keeper-{n}"))
        for n in (1, 2)
    }
    anchor_nut_pairs = {
        frozenset((f"ch-vn-spring-hook-{n}", f"ch-anchor-jam-nut-{n}"))
        for n in range(1, 21)
    }
    assert set(pairs) == rod_pairs | bar_pairs | set_screw_pairs | anchor_nut_pairs
    nominal = math.pi / 4.0 * (pin_dia**2 - hole_dia**2) * engaged
    assert all(pairs[pair] == pytest.approx(1.10 * nominal) for pair in rod_pairs)
    # The arm the pin runs in is never a press pair.
    assert not any("rocker-arm" in name for pair in pairs for name in pair)


def _relative_swing_deg() -> list[float]:
    """Arm tilt less rod tilt at each half-degree of one cam turn (degrees)."""
    ox, oy = frame.ROCKER_PIVOT_XY
    lever, c2c = ck._ARM_ROD_LEVER, rod.CENTER_DISTANCE
    rel = []
    for k in range(720):
        phase = math.radians(k / 2.0)
        cx = frame.CAM_SHAFT_XY[0] + gear.ECCENTRICITY * math.sin(phase)
        cy = frame.CAM_SHAFT_XY[1] + gear.ECCENTRICITY * math.cos(phase)
        dx, dy = cx - ox, cy - oy
        d = math.hypot(dx, dy)
        a = (lever**2 - c2c**2 + d * d) / (2.0 * d)
        h = math.sqrt(lever**2 - a * a)
        px, py = ox + a * dx / d + h * dy / d, oy + a * dy / d - h * dx / d
        arm_tilt = math.degrees(math.atan2(py - oy, ox - px)) - ck._ARM_LEVER_BETA_DEG
        rod_tilt = math.degrees(math.atan2(px - cx, py - cy))
        rel.append(arm_tilt - rod_tilt)
    return rel


def test_restated_swing_brackets_the_solved_loop() -> None:
    rel = _relative_swing_deg()
    lo, hi = pin.RELATIVE_SWING_DEG
    assert lo <= min(rel) <= lo + 0.01
    assert hi - 0.01 <= max(rel) <= hi


def _profile_normal_limits(
    zone: float, outside: float
) -> tuple[float, float]:
    """Signed displacement along the outward material normal: [U-zone, U]."""
    assert 0.0 <= outside <= zone
    return outside - zone, outside


def _printed_profile_limits() -> tuple[tuple[float, float], tuple[float, float]]:
    zone = float(arm_drawing.ARC_PROFILE_ZONE_MM)
    return tuple(
        _profile_normal_limits(zone, float(arm_drawing.ARC_PROFILE_OUTSIDE_MM[name]))
        for name in ("TopRadius", "BottomRadius")
    )


def test_printed_profile_controls_are_their_sources() -> None:
    assert arm_notes.DRAWING_DIMENSIONS["StrapProfile"] == {
        "TopRadius", "BottomRadius", "RodTipLen", "TipLandAngle"
    }
    assert arm_notes.DRAWING_DIMENSIONS["TopEdgeReference"] == {"TopAbovePivot"}
    assert arm_drawing.BASIC_PROFILE_DIMENSIONS == {
        "TopRadius", "BottomRadius", "TopAbovePivot"
    }
    assert arm_drawing.BASIC_PROFILE_DIMENSIONS == arm_drawing.FRONT_KEEP.keys()
    assert set(arm_drawing.END_KEEP) == {"RodTipLen", "TipLandAngle"}
    assert "RodTipLen" not in arm_drawing.HUB_KEEP
    assert "RodTipLen" not in arm_drawing.RIGHT_KEEP
    assert arm_drawing._ALPHA_TOP == arm._ALPHA_TOP
    assert arm_drawing.DRAWING_DIMENSIONS is arm_notes.DRAWING_DIMENSIONS
    assert arm_drawing.curate_view_dimensions is curate_view_dimensions
    # A non-empty owner map alone does not prove the native dimension prints.
    # Require the strict targeted importer to consume it and its marked source.
    tree = ast.parse(Path(arm_drawing.__file__).read_text(encoding="utf-8"))
    end_imports = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "curate_view_dimensions"
        and any(
            keyword.arg == "keep" and ast.unparse(keyword.value) == "END_KEEP"
            for keyword in node.keywords
        )
    ]
    assert len(end_imports) == 1
    assert ast.unparse(end_imports[0].args[1]) == "end"
    keywords = {
        keyword.arg: ast.unparse(keyword.value) for keyword in end_imports[0].keywords
    }
    assert keywords["dimensions_by_feature"] == "DRAWING_DIMENSIONS"
    assert (arm_drawing.R_TOP, arm_drawing.R_BOTTOM, arm_drawing.CENTER_Y) == (
        arm.R_TOP, rocker_interface.R_BOTTOM, rocker_interface.CENTER_Y
    )
    assert arm_drawing.TOP_EDGE_BAND is arm.TOP_EDGE_BAND
    assert arm_drawing.ARC_PROFILE_ZONE_MM == f"{arm.TOP_EDGE_BAND[0]:g}"
    assert arm_drawing.ARC_PROFILE_OUTSIDE_MM == {
        "TopRadius": arm_drawing.ARC_PROFILE_ZONE_MM,
        "BottomRadius": f"{arm.TOP_EDGE_BAND[1]:g}",
    }
    top, bottom = _printed_profile_limits()
    assert top == (arm.TOP_EDGE_BAND[1], arm.TOP_EDGE_BAND[0])
    assert bottom == (-arm.TOP_EDGE_BAND[0], arm.TOP_EDGE_BAND[1])
    # At the mirror station n_top=+Y and n_bottom=-Y. Height is the SAME
    # normal zone evaluated here, not another independent centre translation.
    assert rocker_interface.CENTER_Y - arm.R_TOP - rocker_interface.PIVOT_MID_Y == arm.TOP_EDGE_ABOVE_PIVOT
    assert tuple(
        rocker_interface.CENTER_Y - (arm.R_TOP - d) - rocker_interface.PIVOT_MID_Y for d in top
    ) == pytest.approx(tuple(arm.TOP_EDGE_ABOVE_PIVOT + d for d in top))
    assert arm_notes.DEFAULT_DRAWING_PRECISION == 2
    assert "RodTipLen" not in arm_notes.DRAWING_PRECISION.get("StrapProfile", {})
    assert "SlotDepth" in rod_notes.DRAWING_DIMENSIONS["ForkSlotProfile"]
    assert "ForkWidthDim" in rod_notes.DRAWING_DIMENSIONS["ForkProfile"]


def _profile_endpoints(
    top_outward: float,
    bottom_outward: float,
    tip_x: float,
    land_length: float,
    land_angle: float,
    taper_x: float,
) -> np.ndarray:
    """Top/land/taper joins on normal-limit circles about the BASIC centre.

    The overall width sets tip_x; the printed land length/angle locate its
    upper endpoint. Taper intersection X locates the lower endpoint. Neither
    arc's nominal arc-length/radius ratio is recomputed after a normal offset.
    Only the arcs carry profile: the land and taper remain straight segments
    joining these endpoints, not independently profile-offset faces.
    """
    top_x = tip_x - land_length * math.sin(land_angle)
    top_y = rocker_interface.CENTER_Y - math.sqrt((arm.R_TOP - top_outward) ** 2 - top_x**2)
    bottom_y = rocker_interface.CENTER_Y - math.sqrt(
        (rocker_interface.R_BOTTOM + bottom_outward) ** 2 - taper_x**2
    )
    return np.array([
        (top_x, top_y),
        (tip_x, top_y - land_length * math.cos(land_angle)),
        (taper_x, bottom_y),
    ])


def test_profile_limits_move_independently_and_bound_only_the_arcs() -> None:
    top, bottom = _printed_profile_limits()
    angle = arm_drawing._ALPHA_TOP
    nominal_args = (arm.ROD_TIP_X, arm.TIP_FACE, angle, arm.BOT_END_X)
    nominal = _profile_endpoints(0.0, 0.0, *nominal_args)
    assert nominal == pytest.approx(np.array([
        (arm.TOP_END_X, arm.TOP_END_Y),
        (arm.ROD_TIP_X, arm.TOP_END_Y - arm.TIP_FACE * math.cos(angle)),
        (arm.BOT_END_X, rocker_interface.CENTER_Y - math.sqrt(rocker_interface.R_BOTTOM**2 - arm.BOT_END_X**2)),
    ]))
    top_only = _profile_endpoints(top[1], 0.0, *nominal_args)
    bottom_only = _profile_endpoints(0.0, bottom[0], *nominal_args)
    assert np.array_equal(top_only[2], nominal[2])
    assert np.array_equal(bottom_only[:2], nominal[:2])
    assert top_only[0, 1] > nominal[0, 1]
    assert bottom_only[2, 1] > nominal[2, 1]

    two_place = arm.LINEAR_2PL
    # Mirror symmetry splits the overall-width band between the two tips.
    # C clocking defines the nominal orientation in the A|B|C DRF: the land
    # angle is BASIC, not subject to the title block's general angular band.
    # The remaining independent corners are a superset: no correlation between
    # the printed outline controls is used to gain clearance.
    for top_d, bottom_d, tip_x, length, land_angle, taper_x in itertools.product(
        top,
        bottom,
        (arm.ROD_TIP_X - two_place / 2.0, arm.ROD_TIP_X + two_place / 2.0),
        (arm.TIP_FACE - two_place, arm.TIP_FACE + two_place),
        (angle,),
        (arm.BOT_END_X - two_place, arm.BOT_END_X + two_place),
    ):
        endpoints = _profile_endpoints(top_d, bottom_d, tip_x, length, land_angle, taper_x)
        radius = rocker_interface.R_BOTTOM + bottom_d
        # Triangle inequality bounds even intermediate lengths at the BASIC
        # land angle; disc convexity then bounds the whole straight taper.
        assert arm.R_TOP - top_d + length < radius
        assert np.all(np.linalg.norm(endpoints - (0.0, rocker_interface.CENTER_Y), axis=1) <= radius + 1e-9)
        assert np.all(endpoints[:, 1] < rocker_interface.CENTER_Y)
        assert endpoints[2, 0] < endpoints[0, 0] < endpoints[1, 0]


def _joint_translation_allowance() -> float:
    hole_wander = (
        float(rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"])
        + float(arm.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    ) / 2.0
    arm_hole_max = NUMBER_DRILL_MM[arm.ROD_HOLE_SPEC.size] + pin.DRILLED_PLUS
    pin_drop = (arm_hole_max - (pin.PIN_DIA - pin.PIN_DIA_TOLERANCE)) / 2.0
    # A square enclosing both position discs and the running-clearance disc:
    # expand the X window AND subtract the Y loss. This is conservative even
    # for lateral wander; a pressed pin has no additional drop in the tines.
    return hole_wander + pin_drop


def _continued_circle_clearance(
    radius: float, width: float, depth: float, centre_y: float
) -> float:
    """Exact continuous-swing lower bound, not a sampled outline minimum."""
    loss = _joint_translation_allowance()
    half_window = width / 2.0 + loss
    vx, vy = -rocker_interface.ROD_HOLE_X, centre_y - rocker_interface.ROD_HOLE_Y
    lo, hi = map(math.radians, pin.RELATIVE_SWING_DEG)
    assert -math.pi / 2.0 < lo <= hi < math.pi / 2.0
    cy_min = vy * min(math.cos(lo), math.cos(hi)) - abs(vx) * max(
        abs(math.sin(lo)), abs(math.sin(hi))
    )
    assert cy_min > 0.0
    # cx'=-cy<0, so the leftmost-window condition holds throughout the swing.
    assert vx * math.cos(lo) - vy * math.sin(lo) < -half_window
    cx = vx * math.cos(hi) - vy * math.sin(hi)
    cy = vx * math.sin(hi) + vy * math.cos(hi)
    assert half_window - cx < radius
    assert radius > math.hypot(vx, vy)
    # q=sqrt(R²-(h+cx)²)>cy since R>|c| and cx<-h.
    # low'=cx-(h+cx)*cy/q=[cx*(q-cy)-h*cy]/q<0.
    # Thus +hi is the true minimum for EVERY angle in the restated interval.
    low = cy - math.sqrt(radius**2 - (half_window + cx) ** 2)
    return low - (width / 2.0 - depth) - loss


def _profile_crotch_clearance(
    top: tuple[float, float], bottom: tuple[float, float]
) -> float:
    """Independent normal limits, plus all fork width/depth band corners.

    The largest bottom-limit circle encloses arbitrary, independently varying
    normal deviations, not only circular manufactured surfaces. The top and
    land also lie inside it (triangle inequality), hence so does every straight
    taper joining them to the bottom arc. Its continued lower arc is a proven
    conservative bound, NOT an assertion that the taper carries profile.
    """
    two_place = arm.LINEAR_2PL
    slot_depth = rod.FORK_TOP_Y - rod.FORK_CROTCH_Y
    worst = math.inf
    for top_d, bottom_d, width, depth in itertools.product(
        top,
        bottom,
        (rod.FORK_WIDTH - pin.ROD_LINEAR_2PL, rod.FORK_WIDTH + pin.ROD_LINEAR_2PL),
        (slot_depth - pin.ROD_LINEAR_2PL, slot_depth + pin.ROD_LINEAR_2PL),
    ):
        radius = rocker_interface.R_BOTTOM + bottom_d
        assert arm.R_TOP - top_d + arm.TIP_FACE + two_place < radius
        worst = min(worst, _continued_circle_clearance(radius, width, depth, rocker_interface.CENTER_Y))
    return worst


def test_crotch_clears_the_arm_through_the_whole_swing() -> None:
    """Printed BASIC centre/radii/height, independent top/bottom normal zones.

    No centre-height perturbation is added to top profile. The fixed centre is
    PIVOT_MID_Y+BASIC height+R_TOP. The top zone controls that height at the mirror
    station; the bottom U0 zone only removes material. Straight end faces are
    covered by endpoint/convex-disc containment using the printed land length,
    overall width, BASIC C-clocked land angle and taper-intersection X in the
    A|B|C DRF. This is a planar fit bound, not a new taper-form, datum-error,
    or channel-closure tolerance model.

    Legacy containment is geometric: its low-height/short-top-radius corner
    moves the centre down t=.508 and grows the lower radius by t. The current
    entire inside-zone outline lies in the BASIC R_BOTTOM disc, and
    distance(C,C_legacy)+R_BOTTOM = t+R_BOTTOM = R_legacy. Thus that continued
    legacy circle contains it at every rotation. This does NOT turn the old
    radius/height bands into printed controls or couple the two actual profiles.
    """
    top, bottom = _printed_profile_limits()
    assert bottom[1] == 0.0
    current_radius = rocker_interface.R_BOTTOM + max(bottom)
    legacy_centre = rocker_interface.PIVOT_MID_Y + arm.TOP_EDGE_ABOVE_PIVOT - arm.LINEAR_2PL + arm.R_TOP
    legacy_radius = rocker_interface.R_BOTTOM + arm.LINEAR_2PL
    assert abs(rocker_interface.CENTER_Y - legacy_centre) + current_radius <= legacy_radius + 1e-9
    assert _profile_crotch_clearance(top, bottom) >= pin.CROTCH_CLEARANCE_MIN


def test_inside_zone_widening_cannot_worsen_crotch_clearance() -> None:
    top, bottom = _printed_profile_limits()
    zone = float(arm_drawing.ARC_PROFILE_ZONE_MM)
    outside = float(arm_drawing.ARC_PROFILE_OUTSIDE_MM["BottomRadius"])
    assert outside == 0.0
    wider = _profile_normal_limits(2.0 * zone, outside)
    slot_depth = rod.FORK_TOP_Y - rod.FORK_CROTCH_Y
    width, depth = rod.FORK_WIDTH + pin.ROD_LINEAR_2PL, slot_depth - pin.ROD_LINEAR_2PL
    # At every normal station the added permitted deviations are inward.
    # The limiting inside circle improves; nominal offset zero remains allowed.
    original_inside = _continued_circle_clearance(
        rocker_interface.R_BOTTOM + bottom[0], width, depth, rocker_interface.CENTER_Y
    )
    wider_inside = _continued_circle_clearance(
        rocker_interface.R_BOTTOM + wider[0], width, depth, rocker_interface.CENTER_Y
    )
    assert wider_inside > original_inside
    assert _profile_crotch_clearance(top, wider) == pytest.approx(
        _profile_crotch_clearance(top, bottom), abs=1e-12
    )


def test_same_width_outside_allocation_fault_reduces_air_but_still_clears() -> None:
    """Named drawing fault: reverse bottom U0 to wholly OUTSIDE at printed width.

    This is not an interference negative control: the real 0.5-wide fault still
    clears. Do not enlarge it or reverse an unnamed normal just to force failure.
    It does exercise the physical material-adding sign and clearance sensitivity.
    """
    top, bottom = _printed_profile_limits()
    zone = float(arm_drawing.ARC_PROFILE_ZONE_MM)
    outside_fault = _profile_normal_limits(zone, zone)
    correct = _profile_crotch_clearance(top, bottom)
    fault = _profile_crotch_clearance(top, outside_fault)
    assert fault < correct
    assert fault >= pin.CROTCH_CLEARANCE_MIN


@pytest.mark.parametrize(
    "required_clearance",
    (0.0, pin.CROTCH_CLEARANCE_MIN),
    ids=("physical-nonstrike-bound", "required-clearance"),
)
def test_outside_fault_fit_predicate_rejects_a_raised_source_floor(
    monkeypatch: pytest.MonkeyPatch, required_clearance: float
) -> None:
    """Recompute the source-driven sweep on both sides of each real predicate.

    Zero tests the conservative physical nonstrike bound; CROTCH_CLEARANCE_MIN
    tests the required running air. Losing the former guarantee is not proof
    of an exact geometric strike: the bound encloses the position discs in a
    square. The 0.05 mm perturbation is test sensitivity, not a printed band.
    """
    top, _bottom = _printed_profile_limits()
    zone = float(arm_drawing.ARC_PROFILE_ZONE_MM)
    outside_fault = _profile_normal_limits(zone, zone)
    fault_clearance = _profile_crotch_clearance(top, outside_fault)
    assert fault_clearance >= required_clearance
    excess = fault_clearance - required_clearance
    sensitivity = 0.05
    original_floor = rod.FORK_CROTCH_Y

    # Raise the actual source floor, rather than subtracting a shift from the
    # previously computed result. Both calls must reread slot depth and sweep
    # all profile/fork corners with the modified geometry.
    monkeypatch.setattr(rod, "FORK_CROTCH_Y", original_floor + excess - sensitivity)
    passing_clearance = _profile_crotch_clearance(top, outside_fault)
    assert passing_clearance == pytest.approx(
        required_clearance + sensitivity, abs=1e-9
    )
    assert passing_clearance >= required_clearance

    monkeypatch.setattr(rod, "FORK_CROTCH_Y", original_floor + excess + sensitivity)
    with pytest.raises(AssertionError):
        assert _profile_crotch_clearance(top, outside_fault) >= required_clearance
    failing_clearance = _profile_crotch_clearance(top, outside_fault)
    assert failing_clearance == pytest.approx(
        required_clearance - sensitivity, abs=1e-9
    )


def _arm_bottom_silhouette(
    r_top: float, r_bottom: float, top_above_pivot: float
) -> np.ndarray:
    """Legacy lower-arc/straight-taper silhouette near the rod pin, in the
    arm frame, for the unchanged pin.BUDGET regression only."""
    cy = rocker_interface.PIVOT_MID_Y + top_above_pivot + r_top
    a_bot = arm.BOT_ARC_LEN / 2.0 / r_bottom
    a_top = arm.TOP_ARC_LEN / 2.0 / r_top
    bot_end = np.array([r_bottom * math.sin(a_bot), cy - r_bottom * math.cos(a_bot)])
    tip = np.array(
        [
            (r_top + arm.TIP_FACE) * math.sin(a_top),
            cy - (r_top + arm.TIP_FACE) * math.cos(a_top),
        ]
    )
    x = np.arange(rocker_interface.ROD_HOLE_X - 10.0, bot_end[0], 0.005)
    arc = np.stack([x, cy - np.sqrt(r_bottom**2 - x * x)], axis=1)
    t = np.linspace(0.0, 1.0, 2001)[:, None]
    return np.concatenate([arc, bot_end + t * (tip - bot_end)])


def test_legacy_radius_band_sweep_regresses_the_spec_budget() -> None:
    """The unchanged pin.BUDGET's legacy radius/height perturbation model.

    This sampled lower-outline construction independently regresses its closed
    form. R800/R816 +/-LINEAR_2PL and independently shifted top height are NOT
    the current drawing's BASIC/profile controls; the printed proof is above.
    """
    two_place = arm.LINEAR_2PL
    rad = np.radians(np.array(_relative_swing_deg()))
    cos, sin = np.cos(rad)[:, None], np.sin(rad)[:, None]
    hole = np.array([rocker_interface.ROD_HOLE_X, rocker_interface.ROD_HOLE_Y])
    slot_depth = rod.FORK_TOP_Y - rod.FORK_CROTCH_Y
    worst = math.inf
    for r_top, r_bottom, top_above_pivot in itertools.product(
        (arm.R_TOP - two_place, arm.R_TOP + two_place),
        (rocker_interface.R_BOTTOM - two_place, rocker_interface.R_BOTTOM + two_place),
        (
            arm.TOP_EDGE_ABOVE_PIVOT + arm.TOP_EDGE_BAND[1],
            arm.TOP_EDGE_ABOVE_PIVOT + arm.TOP_EDGE_BAND[0],
        ),
    ):
        local = _arm_bottom_silhouette(r_top, r_bottom, top_above_pivot) - hole
        # Rows are poses, columns outline points, in the rod frame (pin at
        # the origin): the arm turned CCW on the pin by the relative swing.
        x = cos * local[:, 0] - sin * local[:, 1]
        y = sin * local[:, 0] + cos * local[:, 1]
        for width in (rod.FORK_WIDTH - pin.ROD_LINEAR_2PL, rod.FORK_WIDTH + pin.ROD_LINEAR_2PL):
            low = np.where(np.abs(x) <= width / 2.0, y, np.inf).min()
            for depth in (slot_depth - pin.ROD_LINEAR_2PL, slot_depth + pin.ROD_LINEAR_2PL):
                worst = min(worst, low - (width / 2.0 - depth))
    b = pin.BUDGET
    hole_wander = (
        float(rod.GEOMETRIC_TOLERANCES_MM["rocker pin hole position"])
        + float(arm.GEOMETRIC_TOLERANCES_MM["rod-pin hole position"])
    ) / 2.0
    pin_drop = b["running_clearance_max"] / 2.0
    clearance = worst - hole_wander - pin_drop
    assert clearance >= pin.CROTCH_CLEARANCE_MIN
    # The legacy closed form uses the same old envelope on its restated swing.
    assert b["crotch_clearance_min"] == pytest.approx(clearance, abs=0.005)
    assert b["crotch_clearance_min"] <= clearance


def test_fork_bridge_below_the_slot_holds_the_rule_12_target() -> None:
    """The bridge joining the tines under the slot floor: ForkBossLength less
    SlotDepth, both measured at two places from the crown top."""
    two_place = pin.ROD_LINEAR_2PL
    boss_length = rod.FORK_TOP_Y - rod.FORK_BASE_Y
    slot_depth = rod.FORK_TOP_Y - rod.FORK_CROTCH_Y
    bridge = (boss_length - two_place) - (slot_depth + two_place)
    assert bridge == pytest.approx(pin.BUDGET["bridge_min"], abs=1e-9)
    assert bridge >= pin.BRIDGE_TARGET >= pin.RULE12_WALL_FLOOR


def test_fork_stays_clear_of_the_amplitude_bar_foot() -> None:
    """The bar foot slides along the arm's top edge up to the full amplitude
    either side of the pivot; the fork sits a lever's length out, below the
    top edge, so neither the foot nor its notch cheeks can reach it."""
    travel = _config.machine("amplitude", "max_travel_mm")
    foot_reach = math.hypot(travel + bar.BAR_WIDTH / 2.0, arm.TOP_EDGE_ABOVE_PIVOT)
    fork_reach = ck._ARM_ROD_LEVER - math.hypot(
        rod.FORK_WIDTH / 2.0, rod.FORK_BASE_BELOW_PIN
    )
    assert fork_reach - foot_reach > 25.0
    # The crown also stays under the foot cheeks' hang below the top edge.
    top_edge_above_pin = rocker_interface.ARM_DEPTH - rocker_interface.ROD_HOLE_ABOVE_BOTTOM
    assert top_edge_above_pin - rod.FORK_CROWN_RADIUS > bar.BOTTOM_NOTCH_HEIGHT

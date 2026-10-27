"""Offline run-out, full-thread, wall, tip and loop contracts for the upper clamp.

Owner ruling 2026-10-26 (#1951, option B): the loop sits on MHA-SM-04's plain
Ø3.50 shoulder and its #8-32 thread runs through MHA-SM-01's plug, retapped
#8-32 UNC-2B THRU.  The 2026-09-21 clamp rulings stand.  The plug's arm-end
counterbore clears the screw's die run-out with the loop clamped coil-bound
(codjiflo P1 on #1997).
"""

from __future__ import annotations

import math

import pytest

import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spec as gooseneck_spec
import sm_gooseneck_spring_joint as joint
import sm_gooseneck_spring_screw_geom as screw
import sm_gooseneck_spring_screw_spec as screw_spec
import sm_vn_counter_spring_stock_geom as spring

ONE_POINT_FIVE_D = 1.5 * screw.MAJOR_DIA


def test_clamp_preload_binds_the_loop_coil_bound() -> None:
    rise = spring.LOOP_TURNS * spring.WIRE_DIA_MM  # one wire per turn, bound
    assert joint.CLAMPED_GAP_MAX == pytest.approx(rise + spring.WIRE_DIA_MM)
    assert joint.CLAMPED_GAP_MAX == pytest.approx(4.40, abs=0.005)
    # Two stacked pull-side layers on the seat, inside both faces.
    assert joint.CLAMPED_GAP_MIN == pytest.approx(2.0 * spring.WIRE_DIA_MM)
    rate = 82_700.0 * 1.6002**4 / (8.0 * 11.0998**3 * 1.75)
    assert joint.LOOP_AXIAL_RATE == pytest.approx(rate)
    assert joint.LOOP_BIND_FORCE == pytest.approx(rate * (4.88061 - 4.40055))
    least_preload = min(
        screw_spec.clamp_preload_n(mu) for mu in screw_spec.CLAMP_FRICTIONS
    )
    assert least_preload == pytest.approx(231.0, abs=0.5)
    assert joint.LOOP_BIND_FORCE < 0.1 * least_preload


def _screw_play() -> float:
    # The screw in the 2B thread: tap major + root oversize against the 2A
    # major minimum (crest to root).
    return (screw.MAJOR_DIA + 0.025 - screw.THREAD_MAJOR_2A_MIN) / 2.0


def test_screw_tilts_by_its_play_over_the_shortest_engagement() -> None:
    # The play on opposite sides at the two ends of the 1.5D floor
    # (ENGAGEMENT_MIN is at least that).
    tilt = math.atan(2.0 * _screw_play() / ONE_POINT_FIVE_D)
    assert joint.SCREW_RADIAL_PLAY_MAX == pytest.approx(_screw_play())
    assert joint.SCREW_TILT_MAX == pytest.approx(tilt)
    assert math.degrees(tilt) == pytest.approx(1.84, abs=0.005)
    assert joint.ENGAGEMENT_MIN >= ONE_POINT_FIVE_D
    # At the plug face: the deepest floor and its 0.25 break past the
    # receiver's first full thread.
    face = _screw_play() + (joint.COUNTERBORE_DEPTH_MAX + 0.25) * math.tan(tilt)
    assert joint.SCREW_FACE_OFFSET_MAX == pytest.approx(face)
    assert face == pytest.approx(0.194, abs=5e-4)


def test_counterbore_depth_clears_the_deepest_runout_with_margin() -> None:
    # The tilted full-thread circle's low side dips past its axis station.
    dip = screw.MAJOR_DIA / 2.0 * math.sin(joint.SCREW_TILT_MAX)
    deepest = screw.FULL_THREAD_STATION_MAX - joint.CLAMPED_GAP_MIN + dip
    free = screw.FULL_THREAD_STATION_MAX - gooseneck.SPRING_EYE_GAP + dip
    assert joint.SCREW_RUNOUT_INTRUSION_MAX == pytest.approx(deepest)
    assert joint.SCREW_RUNOUT_INTRUSION_FREE_MAX == pytest.approx(free)
    assert (free, deepest) == pytest.approx((0.86, 2.54), abs=0.005)
    assert joint.COUNTERBORE_DEPTH_MIN - deepest >= joint.COUNTERBORE_RUNOUT_MARGIN_MIN
    assert (
        joint.COUNTERBORE_DEPTH_MIN,
        joint.COUNTERBORE_DEPTH,
        joint.COUNTERBORE_DEPTH_MAX,
    ) == pytest.approx((2.59, 2.64, 2.69))


def test_counterbore_clears_the_fat_runout_radially() -> None:
    clearance = (
        joint.COUNTERBORE_DIA / 2.0  # DRILLED HOLES minus is 0
        - screw.MAJOR_DIA / 2.0  # run-out crest, at or above the 2A major max
        - joint.COUNTERBORE_AXIS_OFFSET_MAX  # MHA-SM-01 note 4, to the tap
        - joint.SCREW_FACE_OFFSET_MAX  # the tilted screw, at the plug face
    )
    assert joint.RUNOUT_RADIAL_CLEARANCE_MIN == pytest.approx(clearance)
    assert clearance == pytest.approx(0.073, abs=5e-4)
    # Ø4.70 would rub once the tilt counts: the reason the counterbore is Ø4.90.
    assert (4.70 - screw.MAJOR_DIA) / 2.0 - joint.COUNTERBORE_AXIS_OFFSET_MAX - (
        joint.SCREW_FACE_OFFSET_MAX
    ) < 0.0


def test_counterbore_floor_corner_round_clears_the_runout() -> None:
    # The run-out's crest corner, u above the floor and v off the wall, inside
    # the R0.10 MAX round's square: its clearance is the round's radius less
    # the distance to the round's centre.
    rf = joint.COUNTERBORE_FLOOR_CORNER_R_MAX
    assert rf == 0.10
    u = joint.COUNTERBORE_DEPTH_MIN - joint.SCREW_RUNOUT_INTRUSION_MAX
    v = joint.RUNOUT_RADIAL_CLEARANCE_MIN
    assert 0.0 < u < rf and 0.0 < v < rf
    exact = rf - math.hypot(u - rf, v - rf)
    assert joint.RUNOUT_FLOOR_CORNER_CLEARANCE_MIN == pytest.approx(exact)
    assert exact == pytest.approx(0.046, abs=5e-4)
    # The title block's INSIDE CORNERS R1.0 MAX would stop the screw.
    assert joint._fillet_clearance(u, v, 1.0, 0.0) < 0.0
    notes = " ".join(line.strip() for line in gooseneck_spec.DRAWING_NOTES.splitlines())
    assert f"FLOOR CORNER R{rf:.2f} MAX" in notes


def test_receiver_full_thread_past_the_counterbore_is_1_5d() -> None:
    full_thread = (
        gooseneck.PLUG_LENGTH
        - joint.PLUG_LENGTH_BAND  # shortest plug
        - joint.COUNTERBORE_DEPTH_MAX  # deepest counterbore
        - 0.25  # title-block break on the tap edge at the counterbore floor
        - 0.25  # title-block break at the inner tap end
    )
    assert gooseneck.PLUG_LENGTH == 10.00
    assert joint.ENGAGEMENT_MIN == pytest.approx(full_thread)
    assert (joint.ENGAGEMENT_NOMINAL, joint.ENGAGEMENT_MIN) == pytest.approx(
        (6.86, 6.30)
    )
    assert full_thread >= ONE_POINT_FIVE_D == pytest.approx(6.25, abs=0.005)


def test_screw_full_thread_spans_the_receiver_so_mated_equals_receiver() -> None:
    # Full thread starts inside the counterbore at either gap ...
    assert joint.SCREW_RUNOUT_INTRUSION_FREE_MAX < joint.COUNTERBORE_DEPTH_MIN
    assert joint.SCREW_RUNOUT_INTRUSION_MAX < joint.COUNTERBORE_DEPTH_MIN
    assert not hasattr(joint, "MATED_ENGAGEMENT_MIN")
    # ... and even the shortest screw at the free gap carries it past the
    # longest plug's inner end.
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    full_tip_reach = (
        screw.LENGTH + screw.LENGTH_LOWER - gooseneck.SPRING_EYE_GAP - 1.5 * screw.PITCH
    )
    assert joint.FULL_THREAD_REACH_MIN == pytest.approx(full_tip_reach)
    assert full_tip_reach > longest_plug


def test_threaded_plug_wall_is_2_0_at_the_full_worst_case() -> None:
    smallest_plug_od = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND  # .XX lower limit
    largest_tap_major = screw.MAJOR_DIA + 0.025  # basic major + root oversize
    # Hole drilled after braze, plug OD turned before: different setups.
    runoff = (gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND) * math.tan(
        math.radians(0.3)
    )
    worst_wall = (
        smallest_plug_od / 2.0
        - largest_tap_major / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note 4
        - joint.DRILL_WANDER_MAX  # MHA-SM-01 note 4
        - runoff
        - 2.0 * 0.25  # tap edge + plug OD edge, title block
    )
    assert joint.EDGE_BREAK == 0.25
    assert joint.TAP_ROOT_OVERSIZE == 0.025
    assert joint.DRILL_RUNOFF_MAX == pytest.approx(runoff)
    assert joint.PLUG_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall == pytest.approx(2.845, abs=0.0005)
    assert worst_wall >= joint.PLUG_WALL_TARGET == 2.0


def test_counterbore_wall_is_2_0_at_the_full_worst_case() -> None:
    smallest_plug_od = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND  # .XX lower limit
    largest_cbore = joint.COUNTERBORE_DIA + 0.10  # DRILLED HOLES +0.10
    # Counterbore cut after braze, plug OD turned before: different setups.
    runoff = joint.COUNTERBORE_DEPTH_MAX * math.tan(math.radians(0.3))
    worst_wall = (
        smallest_plug_od / 2.0
        - largest_cbore / 2.0
        - joint.THREAD_AXIS_OFFSET_MAX  # MHA-SM-01 note 4, tap to tube
        - joint.COUNTERBORE_AXIS_OFFSET_MAX  # MHA-SM-01 note 4, to the tap
        - runoff
        - 2.0 * 0.25  # counterbore mouth + plug OD edge, title block
    )
    assert joint.COUNTERBORE_DIA_MAX == pytest.approx(largest_cbore)
    assert joint.COUNTERBORE_WALL_MIN == pytest.approx(worst_wall)
    assert worst_wall == pytest.approx(2.481, abs=0.0005)
    assert worst_wall >= joint.PLUG_WALL_TARGET


def test_screw_tip_exits_plug_without_reaching_tube_wall_or_bend() -> None:
    longest_plug = gooseneck.PLUG_LENGTH + joint.PLUG_LENGTH_BAND
    # Free gap: the screw sits shallowest.
    shortest_reach = screw.LENGTH + screw.LENGTH_LOWER - gooseneck.SPRING_EYE_GAP
    assert joint.TIP_PROTRUSION_MIN == pytest.approx(shortest_reach - longest_plug)
    assert joint.TIP_PROTRUSION_MIN == pytest.approx(1.60, abs=0.005)
    assert joint.PLUG_INNER_X < joint.SCREW_TIP_X < -gooseneck.BEND_R
    # Least clamped gap: the screw sits deepest.
    longest_reach = screw.LENGTH + screw.LENGTH_UPPER - joint.CLAMPED_GAP_MIN
    assert joint.TIP_TO_BEND_MIN == pytest.approx(gooseneck.ARM_RUN - longest_reach)
    assert joint.TIP_TO_BEND_MIN > 0.0
    smallest_bore = joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND
    radial = smallest_bore / 2.0 - (
        screw.MAJOR_DIA / 2.0
        + joint.THREAD_AXIS_OFFSET_MAX
        + joint.DRILL_WANDER_MAX
        + joint.DRILL_RUNOFF_MAX
    )
    assert joint.TIP_BORE_RADIAL_CLEARANCE_MIN == pytest.approx(radial)
    assert radial > 0.0


def test_clamped_eye_stays_at_existing_station_and_has_radial_capture() -> None:
    eye_x = gooseneck.ARM_END_X - spring.END_OCCUPIED_WIDTH_MM / 2.0
    assert eye_x == pytest.approx(-105.8)
    assert gooseneck.SPRING_EYE_GAP == spring.END_OCCUPIED_WIDTH_MM
    smallest_head = screw.HEAD_DIA + screw.HEAD_DIA_LOWER
    assert (smallest_head - spring.EYE_ID_MM) / 2.0 == pytest.approx(
        joint.HEAD_RETENTION_MIN
    )
    assert joint.HEAD_RETENTION_MIN >= 1.0
    assert screw.SEAT_DIA_MAX < screw.MAJOR_DIA < spring.EYE_ID_MM


def test_loop_passes_bear_on_the_plain_seat_free_and_clamped() -> None:
    head_pass, plug_pass = joint.LOOP_PASS_X
    assert 0.0 < head_pass < plug_pass < screw.SHOULDER_LENGTH_MIN
    assert (head_pass, plug_pass) == pytest.approx((1.2687, 3.1433), abs=5e-4)
    clamped_head, clamped_plug = joint.CLAMPED_LOOP_PASS_X
    assert 0.0 < clamped_head < clamped_plug < screw.SHOULDER_LENGTH_MIN
    assert (clamped_head, clamped_plug) == pytest.approx((1.2002, 2.8004), abs=5e-4)

    def lead_gap(station: float) -> float:
        return (screw.SHOULDER_LENGTH_MIN - station + joint.WIRE_R) / math.sqrt(
            2.0
        ) - joint.WIRE_R

    # Plug-side pass vs the lead: worst free (the clamped loop pulls it back).
    assert lead_gap(plug_pass) == pytest.approx(0.159, abs=5e-4)
    assert lead_gap(clamped_plug) > lead_gap(plug_pass)
    assert joint.LOOP_LEAD_CLEARANCE_MIN == pytest.approx(lead_gap(plug_pass))
    assert joint.LOOP_LEAD_CLEARANCE_MIN > 0.0


def test_wire_on_the_head_face_clears_the_underhead_fillet() -> None:
    r, fillet = joint.WIRE_R, screw.UNDERHEAD_CORNER_R
    assert fillet == 0.50
    # Wire touching head face and seat: its centre (r, r) from the corner, the
    # fillet circle centred (fillet, fillet).  With r > fillet the nearest
    # fillet material is a tangent point, (fillet, 0) or (0, fillet).
    floor = math.hypot(r - fillet, r) - r
    assert joint.LOOP_CORNER_CLEARANCE_MIN == pytest.approx(floor)
    assert floor == pytest.approx(0.054, abs=5e-4)
    # The floor is the least of every state: clearance grows with station.
    stations = [r + 0.01 * k for k in range(300)]
    gaps = [joint._fillet_clearance(station, r, fillet, r) for station in stations]
    assert gaps == sorted(gaps)
    # Exact on the far side of the tangent points too: the title block's
    # R1.0 would hold the wire off the seat, and a wire whose centre lies in
    # a deeper fillet's material overlaps by more than its radius.
    assert joint._fillet_clearance(r, r, 1.0, r) == pytest.approx(
        1.0 - math.hypot(r - 1.0, r - 1.0) - r
    )
    assert joint._fillet_clearance(r, r, 1.0, r) < 0.0
    assert joint._fillet_clearance(0.1, r, 2.0, r) < -r


def _helix_points(gap: float, rise: float, seat: float, n: int = 20_000):
    """Supplier loop wire centreline: (station from head, radius from screw)."""
    d = (spring.EYE_ID_MM - seat) / 2.0  # inner surface on the seat, pull side
    turns = spring.LOOP_TURNS
    for k in range(n + 1):
        t = k / n
        theta = math.pi / 2.0 + 2.0 * math.pi * turns * (t - 1.0 / (4.0 * turns))
        x = spring.COIL_MEAN_RADIUS_MM * math.cos(theta)
        y = -d + spring.COIL_MEAN_RADIUS_MM * math.sin(theta)
        yield gap / 2.0 - rise / 2.0 + rise * t, math.hypot(x, y)


def _rim_reach(radius, inner: float, outer: float):
    """Axial reach of the wire's section onto the annular face ``[inner, outer]``.

    A section whose centreline lies within the wire radius past either rim
    still bears on that rim (codjiflo round 5 on #1997); farther off, none.
    """
    import numpy as np

    reach = np.full_like(radius, -np.inf)
    reach[(radius >= inner) & (radius <= outer)] = joint.WIRE_R
    for off in (radius - outer, inner - radius):
        rim = (off > 0.0) & (off < joint.WIRE_R)
        reach[rim] = np.sqrt(joint.WIRE_R**2 - off[rim] ** 2)
    return reach


def _hull_gap(head, plug) -> float:
    """Distance between the convex hulls of two planar point sets."""
    import numpy as np
    from scipy.spatial import ConvexHull, QhullError

    diff = (head[:, None, :] - plug[None, :, :]).reshape(-1, 2)

    def segment(a, b) -> float:
        ab = b - a
        span = float(ab @ ab)
        s = 0.0 if span == 0.0 else min(1.0, max(0.0, -float(a @ ab) / span))
        return float(np.hypot(*(a + s * ab)))

    try:
        hull = ConvexHull(diff)
    except (QhullError, ValueError):  # under three points, or collinear
        far = diff[np.argmax(np.linalg.norm(diff - diff[0], axis=1))]
        if np.allclose(far, diff[0]):
            return float(np.hypot(*diff[0]))
        along = diff @ (far - diff[0])
        return segment(diff[np.argmin(along)], diff[np.argmax(along)])
    if np.all(hull.equations[:, 2] <= 0.0):
        return 0.0  # the origin is inside: the normal forces alone balance
    corners = diff[hull.vertices]
    return min(segment(corners[k - 1], corners[k]) for k in range(len(corners)))


def test_friction_held_loop_keeps_the_gap_floor_and_the_free_lead_station() -> None:
    # The coil-bound helix, rigid, rocked by a tilt vector over a grid.  Its
    # section bears on a face wherever it meets the face's SMALLEST footprint,
    # rims included (_rim_reach).  Head: from the R0.5 corner's tangent out to
    # its Ø lower limit less the title-block break.  Plug face: from the
    # counterbore mouth's reach out to the proud plug's Ø lower limit less its
    # break, the tube's, or without limit.
    #  * every width holds the floor CLAMPED_GAP_MIN, which is tight, and so
    #    does the gap on the screw axis with the head face tilted
    #    SCREW_TILT_MAX against the plug face in any direction;
    #  * friction holds the clamped loop only where its head- and plug-face
    #    contacts, on the face plane, lie within mu x gap of each other (the
    #    loop's moment balance; MHA-SM-00 step 8 clamps it before the spring
    #    is hooked, so the preload is its only load).  Swept at twice the
    #    clamp's highest friction, which also covers the head face's tilt,
    #    with each contact set taken CONTACT_BAND deep so that every state in
    #    a grid cell is represented, those states keep the gap within its
    #    bounds and both pull-side passes between the head face and the free
    #    state's plug-side station, where the lead clearance is taken.
    import numpy as np

    mu = 2.0 * max(screw_spec.CLAMP_FRICTIONS)
    step = 0.01
    # Twice the most one step moves the farthest wire (8.6 from the axis)
    # within its cell.
    contact_band = 0.12
    head_outer = (screw.HEAD_DIA + screw.HEAD_DIA_LOWER) / 2.0 - joint.EDGE_BREAK
    mouth_r = joint.COUNTERBORE_MOUTH_REACH
    footprints = {
        "proud": (joint.PLUG_DIA - joint.PLUG_DIAMETER_BAND) / 2.0 - joint.EDGE_BREAK,
        "tube": (gooseneck.TUBE_DIA - 0.10) / 2.0 - joint.EDGE_BREAK,
        "full": math.inf,
    }
    n = 240
    t = np.linspace(0.0, 1.0, n + 1)
    theta = math.pi / 2.0 + 2.0 * math.pi * spring.LOOP_TURNS * (
        t - 1.0 / (4.0 * spring.LOOP_TURNS)
    )
    passes = [round(fraction * n) for fraction in joint._PASS_T]
    window = n // 7
    grid = np.round(np.arange(-0.35, 0.3501, step), 6)
    face_tilts = math.tan(joint.SCREW_TILT_MAX) * np.array(
        [[math.cos(a), math.sin(a)] for a in np.linspace(0.0, 2.0 * math.pi, 17)[:-1]]
    )

    def rotation(tx: float, ty: float):
        angle = math.hypot(tx, ty)
        if angle == 0.0:
            return np.eye(3)
        ux, uy = tx / angle, ty / angle
        k = np.array([[0.0, 0.0, uy], [0.0, 0.0, -ux], [-uy, ux, 0.0]])
        return np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * k @ k

    rotations = [((tx, ty), rotation(tx, ty)) for tx in grid for ty in grid]
    cases = []
    for seat in (screw.SEAT_DIA_MIN, screw.SEAT_DIA_MAX):
        d = (spring.EYE_ID_MM - seat) / 2.0
        body = np.stack(
            [
                spring.COIL_MEAN_RADIUS_MM * np.cos(theta),
                -d + spring.COIL_MEAN_RADIUS_MM * np.sin(theta),
                joint.CLAMPED_LOOP_RISE * (t - 0.5),
            ],
            axis=1,
        )
        head_inner = seat / 2.0 + screw.UNDERHEAD_CORNER_R
        for name, plug_outer in footprints.items():
            least_width = least_axis_gap = math.inf
            held = []
            for (tx, ty), matrix in rotations:
                rocked = body @ matrix.T
                xy, z = rocked[:, :2], rocked[:, 2]
                radius = np.hypot(xy[:, 0], xy[:, 1])
                head_side = z - _rim_reach(radius, head_inner, head_outer)
                plug_side = z + _rim_reach(radius, mouth_r, plug_outer)
                head_face, plug_face = head_side.min(), plug_side.max()
                width = plug_face - head_face
                least_width = min(least_width, width)
                axis_gap = (plug_side - face_tilts @ xy.T).max(axis=1).min() - head_face
                least_axis_gap = min(least_axis_gap, axis_gap)
                # Contact points on the face plane: the centreline's own over
                # a footprint, the rim's past it.
                touch_h = head_side <= head_face + contact_band
                touch_p = plug_side >= plug_face - contact_band
                on_h = (
                    np.clip(radius[touch_h], head_inner, head_outer) / radius[touch_h]
                )
                on_p = np.clip(radius[touch_p], mouth_r, plug_outer) / radius[touch_p]
                head_pts = xy[touch_h] * on_h[:, None]
                plug_pts = xy[touch_p] * on_p[:, None]
                allowed = mu * width
                axis = plug_pts.mean(axis=0) - head_pts.mean(axis=0)
                length = float(np.hypot(*axis))
                if (
                    length > 0.0
                    and ((plug_pts @ axis).min() - (head_pts @ axis).max()) / length
                    > allowed
                ):
                    continue  # separated along one axis by more than allowed
                if _hull_gap(head_pts, plug_pts) > allowed:
                    continue
                # Each pull-side pass: the seat-bearing (least-radius) point
                # within a quarter turn of its untilted station.
                head_pass, plug_pass = (
                    z[k - window + int(np.argmin(radius[k - window : k + window + 1]))]
                    - head_face
                    for k in passes
                )
                held.append((width, head_pass, plug_pass, math.hypot(tx, ty)))
            cases.append((seat, name, least_width, least_axis_gap, held))
    print(
        "rocked loop: least width "
        f"{min(case[2] for case in cases):.4f}, on the tilted axis "
        f"{min(case[3] for case in cases):.4f}; friction-held (mu {mu:.2f}) "
        + ", ".join(
            f"{seat:.2f}/{name} gap {min(s[0] for s in held):.3f}-"
            f"{max(s[0] for s in held):.3f} passes {min(s[1] for s in held):.3f}/"
            f"{max(s[2] for s in held):.3f}"
            for seat, name, _, _, held in cases
        )
    )
    assert min(case[2] for case in cases) >= joint.CLAMPED_GAP_MIN
    assert min(case[3] for case in cases) >= joint.CLAMPED_GAP_MIN
    proud = min(case[2] for case in cases if case[1] == "proud")
    assert proud <= joint.CLAMPED_GAP_MIN + 0.10
    for _seat, _name, _, _, held in cases:
        assert held  # the width minimum at least
        for width, head_pass, plug_pass, tilt in held:
            assert joint.CLAMPED_GAP_MIN <= width <= joint.CLAMPED_GAP_MAX
            assert joint.WIRE_R <= head_pass < plug_pass <= joint.LOOP_PASS_X[1]
            assert tilt < grid[-1] - step  # inside the swept grid


def test_loop_wire_clears_the_counterbore_mouth_at_full_worst_case() -> None:
    reach = (
        joint.COUNTERBORE_DIA_MAX / 2.0  # largest counterbore
        + 0.25  # title-block break on its mouth
        + joint.COUNTERBORE_AXIS_OFFSET_MAX  # counterbore axis vs thread axis
        + joint.SCREW_FACE_OFFSET_MAX  # the tilted screw's axis at the plug face
    )
    assert joint.COUNTERBORE_MOUTH_REACH == pytest.approx(reach)
    r = joint.WIRE_R
    contact, standoff = [], []
    for gap, rise in (
        (gooseneck.SPRING_EYE_GAP, spring.LOOP_RISE_MM),
        (joint.CLAMPED_GAP_MAX, joint.CLAMPED_LOOP_RISE),
    ):
        for seat in (screw.SEAT_DIA_MIN, screw.SEAT_DIA_MAX):
            points = list(_helix_points(gap, rise, seat))
            # The plug-side tip is the wire that meets the plug face.
            tip_station, tip_radius = points[-1]
            assert tip_station + r == pytest.approx(gap)
            contact.append(tip_radius - r)
            inside = [s for s, rad in points if rad - r < reach]
            standoff.append(gap - (max(inside) + r))
    print(
        f"loop wire at the plug face: {min(contact):.3f} from the screw axis "
        f"vs mouth reach {reach:.3f}; wire inside the mouth stands "
        f"{min(standoff):.3f} off the face"
    )
    assert joint.LOOP_FACE_CONTACT_RADIUS_MIN == pytest.approx(min(contact))
    assert joint.LOOP_MOUTH_STANDOFF_MIN == pytest.approx(min(standoff), abs=1e-3)
    assert min(contact) > reach
    assert min(standoff) > 0.0


def test_shared_interference_contract_inputs_match_their_owners() -> None:
    # _interference_contracts keeps the plug pair's inputs narrow (shared
    # thread tables and a literal threaded length) so screw or gooseneck edits
    # do not re-key every assembly; pin them to their owners here.
    import _interference_contracts
    from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

    assert screw.THREAD.split()[0] == joint.TAP_SPEC.size == "#8-32"
    assert _interference_contracts._GOOSENECK_THREAD_LENGTH == pytest.approx(
        gooseneck.PLUG_LENGTH - joint.COUNTERBORE_DEPTH
    )
    assert TAP_DRILL_MM["#8-32"] == pytest.approx(joint.TAP_DRILL_DIA) == 3.454
    assert THREAD_MAJOR_MM["#8-32"] == pytest.approx(screw.MAJOR_DIA, abs=1e-3)
    assert THREAD_MAJOR_MM["#8-32"] < joint.COUNTERBORE_DIA


def test_bending_span_reaches_the_receiver_first_full_thread() -> None:
    # Inside the counterbore the screw is unsupported: the beam runs to the
    # plug's first full thread at its farthest (codjiflo round 3, #1997).
    receiver = joint.CLAMPED_GAP_MAX + joint.COUNTERBORE_DEPTH_MAX + joint.EDGE_BREAK
    assert screw_spec.RECEIVER_FULL_THREAD_STATION_MAX == pytest.approx(receiver)
    assert screw_spec.STRENGTH_SPAN == pytest.approx(
        max(screw.FULL_THREAD_STATION_MAX, receiver)
    )
    assert screw_spec.STRENGTH_SPAN == pytest.approx(7.34, abs=0.005)
    assert screw_spec._SECTIONS[-1][1] == screw_spec.STRENGTH_SPAN


def test_strength_sweeps_clamp_and_thread_friction_independently() -> None:
    spec = screw_spec
    pairs = {(c, t) for c in spec.CLAMP_FRICTIONS for t in spec.THREAD_FRICTIONS}
    assert set(spec.SERVICE_SF) == set(spec.TIGHTENING_SF) == pairs
    # The lowest clamp friction needs the most preload and the highest thread
    # friction converts the most of it to torsion: that pair governs both.
    worst = (min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS))
    assert min(spec.SERVICE_SF, key=spec.SERVICE_SF.get) == worst
    assert min(spec.TIGHTENING_SF, key=spec.TIGHTENING_SF.get) == worst
    assert spec.service_safety_factor(*worst) >= spec.STRENGTH_SF_TARGET
    assert spec.tightening_safety_factor(*worst) >= spec.STRENGTH_SF_TARGET
    # 12L14 CD is the grade the function needs: 1018 CD's 370 MPa would not
    # carry the counterbore's span at SF 2.
    assert spec.YIELD_MPA == 415.0
    assert spec.service_safety_factor(*worst) * 370.0 / spec.YIELD_MPA < 2.0


def test_service_peak_stations_bound_a_dense_sweep() -> None:
    spec = screw_spec
    mu_clamp, mu_thread = min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS)
    preload = spec.clamp_preload_n(mu_clamp)
    torsion = spec.RESIDUAL_TORSION_FACTOR * spec.thread_torque_n_mm(preload, mu_thread)
    dense = min(
        spec._von_mises_sf(preload, moment(x0 + (x1 - x0) * i / 2000), torsion, dia)
        for x0, x1, dia in spec._SECTIONS
        for i in range(2001)
        for moment in spec._MOMENT_CASES
    )
    exact = spec.service_safety_factor(mu_clamp, mu_thread)
    assert exact <= dense + 1e-12
    assert dense - exact < 1e-3


def test_tightening_sf_is_the_overtightening_margin() -> None:
    # Both tightening stresses are linear in the preload, so the tightening SF
    # is the multiple of the needed preload the root takes to nominal yield.
    spec = screw_spec
    worst = (min(spec.CLAMP_FRICTIONS), max(spec.THREAD_FRICTIONS))
    needed = spec.clamp_preload_n(worst[0])
    margin = spec.tightening_safety_factor(*worst)
    at_margin = needed * margin
    sf = spec._von_mises_sf(
        at_margin,
        0.0,
        spec.thread_torque_n_mm(at_margin, worst[1]),
        spec.THREAD_MINOR_2A_MIN_EST,
    )
    assert sf == pytest.approx(1.0)
    assert spec.OVERTIGHTEN_MARGIN == pytest.approx(margin)
    assert spec.OVERTIGHTEN_MARGIN >= spec.STRENGTH_SF_TARGET

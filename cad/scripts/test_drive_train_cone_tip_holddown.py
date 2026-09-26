"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-092), its MHA-141 shim pack, the MHA-142 post fillisters and
the hold-down hardware are separate parts whose agreement the drive-train
builder asserts when it is imported. These tests read those asserts and the
values they produce.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BUILDER = Path(__file__).with_name("build_drive_train_assembly.py")


def _compares_naming(tree: ast.AST, names: set[str]) -> list[ast.Compare]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        if used & names:
            found.append(node)
    return found


def test_shim_footprint_is_not_compared_with_exact_float_equality() -> None:
    """Main's I24 nit: the footprint check uses abs() tolerances per axis,
    like its neighbours, never == / != on floats."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    compares = _compares_naming(
        tree, {"TIP_SHIM_X", "TIP_SHIM_Z", "TIP_SHIM_NORTH_Z", "TIP_SHIM_SOUTH_Z"}
    )
    assert compares, "the shim footprint check disappeared"
    exact = [
        ast.unparse(node)
        for node in compares
        if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
    ]
    assert not exact, f"exact float comparison on the shim footprint: {exact}"


def test_heel_relief_is_sized_from_the_worst_case_head_stack() -> None:
    """I31: the nominal 0.2375 gap to the pivot-screw head hid a collision.

    The north face follows the shaft tip (Sec4End .X, 0.8), the head floats
    in the drilled pivot hole, and 0.20 air stays; the height runs from the
    lowest foot (thinnest plate, thinnest shim) to the head top.
    """
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.HEEL_NOMINAL_GAP == pytest.approx(0.2375, abs=1e-9)
    assert bdt.HEEL_TIP_TRAVEL == pytest.approx(0.8)
    assert bdt.HEEL_HEAD_FLOAT == pytest.approx((6.756 + 0.10 - 6.35) / 2.0, abs=1e-3)
    assert bdt.HEEL_DEPTH_REQUIRED == pytest.approx(1.0155, abs=1e-3)
    assert bdt.HEEL_HEIGHT_REQUIRED == pytest.approx(
        6.35 + 4.7625 - (6.35 - 0.13 + 0.05) + 0.20
    )
    # Without the relief the worst-case face runs into the head.
    assert bdt.HEEL_NOMINAL_GAP < bdt.HEEL_TIP_TRAVEL + bdt.HEEL_HEAD_FLOAT
    assert block.HEEL_RELIEF_DEPTH - 0.51 >= bdt.HEEL_DEPTH_REQUIRED
    assert block.HEEL_RELIEF_HEIGHT - 0.51 >= bdt.HEEL_HEIGHT_REQUIRED


def test_shim_covers_exactly_the_block_foot_face() -> None:
    """I24 as a derived relation: full width, from the I31 foot flange's
    south end to the heel relief, at the block's nominal pack."""
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.TIP_SHIM_T == pytest.approx(block.SHIM_NOMINAL)
    assert bdt.TIP_SHIM_X == pytest.approx(block.BLOCK_X)
    assert bdt.TIP_SHIM_SOUTH_Z == pytest.approx(
        -block.BLOCK_Z / 2.0 - block.FLANGE_LEN
    )
    assert bdt.TIP_SHIM_NORTH_Z == pytest.approx(
        block.BLOCK_Z / 2.0 - block.HEEL_RELIEF_DEPTH
    )


def test_post_fillisters_engage_the_plate_tap_at_least_090d() -> None:
    """I22: each MHA-142 seats on the post's counterbore floor and runs into
    the MHA-091 tap by its cut length past the post's grip -- never proud of
    the plate underside, and 0.90D of thread after the tap's edge break."""
    import build_drive_train_assembly as bdt
    import cone_swing_platform_spec as platform
    import post_mount_screw_spec as screw

    assert bdt.POST_SCREW_SEAT == pytest.approx(screw.GRIP_MM)
    assert bdt.POST_SCREW_INTO_PLATE == pytest.approx(
        screw.CUT_LENGTH_MM - screw.GRIP_MM
    )
    assert bdt.POST_SCREW_INTO_PLATE <= platform.PLATE_THICKNESS
    thread = bdt.POST_SCREW_INTO_PLATE - 2.0 * platform.POST_MOUNT_TAP_EDGE_BREAK
    assert thread >= 0.90 * platform.POST_MOUNT_THREAD_DIA
    assert platform.POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS >= 0.90


def test_tip_block_containment_runs_across_the_foot_flange() -> None:
    """I31: the block's foot runs FLANGE_LEN south of its body as the flange,
    so the rider containment spans the flange too, each end held
    PLATFORM_CONTAINMENT_FLOOR_MM inside the plate's narrower side."""
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    south, north, half = bdt.PLATFORM_RIDER_SPANS["tip block"]
    assert south == pytest.approx(
        bdt.TIP_BLOCK_STATION - block.BLOCK_Z / 2.0 - block.FLANGE_LEN
    )
    assert north == pytest.approx(bdt.TIP_BLOCK_STATION + block.BLOCK_Z / 2.0)
    assert half == pytest.approx(block.BLOCK_X / 2.0)
    for end in (south, north):
        assert bdt._plat_half_width(end) >= half + bdt.PLATFORM_CONTAINMENT_FLOOR_MM


def test_west_edge_is_proven_over_the_whole_swing() -> None:
    """Main, I31 item 8: the north-west edge keeps the arbor pedestals, the
    base lip and every other base seat clear from engaged to disengaged."""
    import build_drive_train_assembly as bdt

    assert bdt.SWING_ANGLES[0] == 0.0
    assert bdt.SWING_ANGLES[-1] == pytest.approx(bdt.DISENGAGE_DEG)
    sweep = bdt.SWING_SWEEP
    assert sweep["south arbor pedestal"] >= 2.0
    assert sweep["north arbor pedestal"] >= 0.25
    assert min(v for k, v in sweep.items() if k.endswith("inside the lip")) >= 0.0
    assert all(isinstance(value, float) for value in sweep.values())
    gap, occupant = bdt.SWING_NEAREST_OCCUPANT
    assert gap == min(clear for clear, _swing in bdt.SWING_OCCUPANT_CLEARANCE.values())
    assert gap >= bdt.SWING_SEAT_RUNNING_CLEARANCE
    assert bdt.SWING_OCCUPANT_CLEARANCE[occupant][0] == gap
    # The north pedestal gap closes as the plate swings out: the engaged pose
    # alone would not have found its minimum.
    engaged = bdt.west_edge_arbor_gaps(0.0)[1]
    assert sweep["north arbor pedestal"] < engaged


def test_swing_occupants_are_the_parts_standing_on_the_seats() -> None:
    """Main (review of 7240ae0de): the thing the swinging plate can hit is the
    part standing on a base seat -- the rocker-arm support, the pivot blocks,
    the pinion spring, the nameplate -- not the screw holding it, so those are
    checked by plan footprint; only the column tube, round in its socket, keeps
    a radius.  Every occupant clears the plate by SWING_SEAT_RUNNING_CLEARANCE
    over the whole swing, and each footprint covers the seats that hold it."""
    import build_drive_train_assembly as bdt

    assert not hasattr(bdt, "SWING_FEATURE_CLEARANCE")
    assert not hasattr(bdt, "SWING_SEAT_FLOORS")
    assert bdt.SWING_SEAT_RUNNING_CLEARANCE == 2.0
    assert set(bdt.SWING_FOOTPRINTS) == {
        "rocker-arm support",
        "front pivot block",
        "back pivot block",
        "pinion spring",
        "nameplate",
        "serial stamp",
    }
    assert set(bdt.SWING_ROUND_OCCUPANTS) == {f"column socket {i}" for i in range(4)}
    for occupant, seats in bdt.SWING_OCCUPANT_SEATS.items():
        for seat in seats:
            assert bdt._point_in_polygon(seat, bdt.SWING_FOOTPRINTS[occupant]), (
                occupant,
                seat,
            )
    clearances = bdt.SWING_OCCUPANT_CLEARANCE
    assert set(clearances) == set(bdt.SWING_FOOTPRINTS) | set(bdt.SWING_ROUND_OCCUPANTS)
    for occupant, (clear, _swing) in clearances.items():
        assert clear >= bdt.SWING_SEAT_RUNNING_CLEARANCE, occupant


def test_pruned_swing_sweep_finds_the_every_sample_minimum() -> None:
    """The occupant sweep skips samples its motion bound rules out; it must
    report exactly the minimum a sweep of every sample finds."""
    import build_drive_train_assembly as bdt

    for occupant, (clear, swing) in bdt.SWING_OCCUPANT_CLEARANCE.items():
        if occupant in bdt.SWING_FOOTPRINTS:
            gaps = [
                bdt._plan_gap_polygons(
                    bdt.plate_vertices_machine(angle), bdt.SWING_FOOTPRINTS[occupant]
                )
                for angle in bdt.SWING_ANGLES
            ]
        else:
            xz, radius = bdt.SWING_ROUND_OCCUPANTS[occupant]
            gaps = [bdt._plan_gap_to_plate(xz, angle) - radius for angle in bdt.SWING_ANGLES]
        assert clear == min(gaps), occupant
        assert swing == bdt.SWING_ANGLES[gaps.index(min(gaps))], occupant


def test_swing_sweep_catches_a_footprint_the_engaged_pose_misses() -> None:
    """Fail-first control: a synthetic footprint parked where the plate's
    corner arrives only at full disengage passes an engaged-only check and
    fails the swept one."""
    import build_drive_train_assembly as bdt

    engaged = bdt.plate_vertices_machine(0.0)
    swung = bdt.plate_vertices_machine(bdt.DISENGAGE_DEG)
    xs = [x for x, _z in swung]
    zs = [z for _x, z in swung]
    # The spot under the fully swung plate that lies farthest outside the
    # engaged one.
    cx, cz = max(
        (
            (x, z)
            for x in (min(xs) + (max(xs) - min(xs)) * i / 200 for i in range(201))
            for z in (min(zs) + (max(zs) - min(zs)) * j / 200 for j in range(201))
            if bdt._plan_gap_to_plate((x, z), bdt.DISENGAGE_DEG) < -1.0
        ),
        key=lambda xz: bdt._plan_gap_to_plate(xz, 0.0),
    )
    square = ((cx - 0.5, cz - 0.5), (cx + 0.5, cz - 0.5), (cx + 0.5, cz + 0.5), (cx - 0.5, cz + 0.5))
    assert bdt._plan_gap_polygons(engaged, square) > bdt.SWING_SEAT_RUNNING_CLEARANCE
    with pytest.raises(AssertionError, match="synthetic"):
        bdt.require_swing_clearance({"synthetic": square}, {})
    # And a round occupant is held off by its radius plus the clearance.
    with pytest.raises(AssertionError, match="synthetic post"):
        bdt.require_swing_clearance({}, {"synthetic post": ((cx, cz), 0.5)})


@pytest.mark.xfail(
    strict=True,
    reason=(
        "I31 hold-down not placed on #877: MHA-140 (93075A150) through the "
        "block's flange slot into the MHA-146 locknut needs #925's I31 plate "
        "slot under it; it lands in the placement lineage (b), "
        "swing/917-holddown on #917 S1"
    ),
)
def test_i31_hold_down_is_placed() -> None:
    """Placed, the hold-down screw stands at the flange slot's centre, over the
    plate's tip slot, with its nut on the flange; the builder then inserts
    both parts."""
    import build_drive_train_assembly as bdt
    import cone_swing_platform_spec as platform

    source = BUILDER.read_text(encoding="utf-8")
    assert '"cone-tip-block-screw"' in source
    assert '"cone-tip-block-nut"' in source
    assert bdt.TIP_HOLD_STATION - bdt.PIVOT_STATION == pytest.approx(
        platform.TIP_SCREW_LOCAL_Z
    )

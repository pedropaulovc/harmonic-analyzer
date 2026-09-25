"""Offline contracts for the harmonic-base drawing."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

import build_harmonic_base as part
import build_cone_swing_platform as platform
import harmonic_base_spec
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from build_cone_lock_knob import COLLAR_DIA as KNOB_COLLAR_DIA
from build_swing_stop_screw import SHANK_DIA as STOP_SHANK_DIA


@pytest.mark.parametrize(
    ("seat", "engagement", "kind", "lead_pitches"),
    (
        (
            part.HOLD_DOWN_SEAT_SPEC,
            part.HOLD_DOWN_ENGAGEMENT,
            "tapped",
            5,
        ),
        (part.PIVOT_SEAT_SPEC, part.PIVOT_THREAD_ENGAGEMENT, "tapped_bottoming", 2),
        (part.LOCK_SEAT_SPEC, part.LOCK_STUD_LEN, "tapped", 5),
        (part.STOP_SEAT_SPEC, part.STOP_ENGAGEMENT, "tapped", 5),
        (
            part.BLOCK_SEAT_SPEC,
            part.BLOCK_SCREW_LEN - part.BLOCK_HEIGHT,
            "tapped_bottoming",
            2,
        ),
        (
            part.FOOT_SEAT_SPEC,
            part.FOOT_SCREW_LEN - part.SPRING_THICKNESS,
            "tapped_bottoming",
            2,
        ),
        (
            part.PEDESTAL_SEAT_SPEC,
            part.PEDESTAL_SCREW_LEN - part.PEDESTAL_FLANGE_THICKNESS,
            "tapped_bottoming",
            2,
        ),
        (
            part.NAMEPLATE_SEAT_SPEC,
            part.NAMEPLATE_SCREW_LEN - part.nameplate_spec.PLATE_THICKNESS,
            "tapped_bottoming",
            2,
        ),
    ),
)
def test_blind_seats_keep_stock_in_full_threads_above_the_tap_lead(
    seat, engagement: float, kind: str, lead_pitches: int
) -> None:
    assert seat.kind == kind
    part.require_blind_seat_fit("stock fit", seat, engagement)
    thread_depth = seat.overrides_mm["ThreadDepth"]
    pitch = 25.4 / float(seat.size.rsplit("-", 1)[1])
    assert thread_depth - engagement >= 0.25 - 1e-9
    assert seat.depth_mm - thread_depth >= lead_pitches * pitch - 1e-9
    # A drill that loses just 0.01 mm of the required tooling lead is invalid
    # even though the unchanged stock screw still clears the full threads.
    short_lead = replace(seat, depth_mm=thread_depth + lead_pitches * pitch - 0.01)
    with pytest.raises(AssertionError, match="tap lead"):
        part.require_blind_seat_fit("short lead", short_lead, engagement)


def test_pivot_rejects_former_full_threads_to_drill_bottom() -> None:
    old_seat = replace(
        part.PIVOT_SEAT_SPEC, kind="tapped", depth_mm=11.525, overrides_mm={}
    )
    with pytest.raises(AssertionError, match="plug-tap lead"):
        part.require_blind_seat_fit(
            "former pivot", old_seat, part.PIVOT_THREAD_ENGAGEMENT
        )


def test_pivot_rejects_stock_bottoming_despite_ample_drill_depth() -> None:
    seat = replace(
        part.PIVOT_SEAT_SPEC,
        overrides_mm={"ThreadDepth": part.PIVOT_THREAD_ENGAGEMENT},
    )
    with pytest.raises(AssertionError, match="bottoms"):
        part.require_blind_seat_fit("pivot", seat, part.PIVOT_THREAD_ENGAGEMENT)


@pytest.mark.parametrize("tip_reserve", (0.0, -0.25, math.nan, math.inf))
def test_base_seat_rejects_nonphysical_tip_reserve(tip_reserve: float) -> None:
    with pytest.raises(AssertionError, match="tip reserve"):
        part.require_blind_seat_fit(
            "pivot",
            part.PIVOT_SEAT_SPEC,
            part.PIVOT_THREAD_ENGAGEMENT,
            tip_reserve=tip_reserve,
        )


def test_pivot_drill_keeps_its_point_inside_the_pad_and_clear_of_cavities() -> None:
    from _holes import DRILL_POINT_H, blind_hole_volume_mm3

    assert part.PIVOT_SEAT_SPEC.overrides_mm["ThreadDepth"] == pytest.approx(9.775)
    assert part.PIVOT_SEAT_SPEC.depth_mm == pytest.approx(12.0)
    radius = part.PIVOT_SCREW_HOLE_DIA / 2.0
    assert part.PIVOT_DRILL_BOTTOM_WALL == pytest.approx(
        part.TOP_THICKNESS - part.PIVOT_SEAT_SPEC.depth_mm - radius * DRILL_POINT_H
    )
    assert part.PIVOT_DRILL_BOTTOM_WALL >= 1.5 * part.PIVOT_SCREW_HOLE_DIA
    assert part.PIVOT_NEAREST_CAVITY_WALL >= part.PIVOT_SCREW_HOLE_DIA
    # Only the pivot cylinder grows: its same-diameter terminal point cancels.
    assert blind_hole_volume_mm3(
        part.PIVOT_SCREW_HOLE_DIA, part.PIVOT_SEAT_SPEC.depth_mm
    ) - blind_hole_volume_mm3(part.PIVOT_SCREW_HOLE_DIA, 11.525) == pytest.approx(
        math.pi * radius**2 * 0.475
    )


def test_cone_lock_seats_on_plate_and_bare_base_with_useful_threads() -> None:
    import build_cone_lock_knob as knob
    from _holes import DRILL_POINT_H, blind_hole_volume_mm3

    knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, knob.STUD_LEN)
    assert knob.STUD_LEN - platform.PLATE_T == pytest.approx(12.7)
    assert knob.STUD_LEN - platform.PLATE_T - knob.TIP_CHAMFER >= 1.5 * knob.STUD_DIA
    assert part.LOCK_SEAT_SPEC.overrides_mm["ThreadDepth"] - knob.STUD_LEN >= 0.25
    assert part.LOCK_SEAT_SPEC.depth_mm == pytest.approx(25.65)
    drill_tip_depth = (
        part.LOCK_SEAT_SPEC.depth_mm + part.LOCK_SCREW_HOLE_DIA / 2.0 * DRILL_POINT_H
    )
    assert part.TOP_THICKNESS - drill_tip_depth >= 1.5 * part.LOCK_SCREW_HOLE_DIA
    assert part.LOCK_NEAREST_CAVITY_WALL >= part.LOCK_SCREW_HOLE_DIA
    # Volume includes the added drilling length AND its terminal point.
    radius = part.LOCK_SCREW_HOLE_DIA / 2.0
    assert blind_hole_volume_mm3(
        part.LOCK_SCREW_HOLE_DIA, part.LOCK_SEAT_SPEC.depth_mm
    ) == pytest.approx(math.pi * radius**2 * (25.65 + radius * DRILL_POINT_H / 3.0))


def test_cone_lock_rejects_short_stock_even_in_a_deep_receiver() -> None:
    import build_cone_lock_knob as knob

    with pytest.raises(AssertionError, match="useful thread engagement"):
        knob.require_seat_fit(part.LOCK_SEAT_SPEC, platform.PLATE_T, 7.9375)


def test_cone_lock_rejects_a_receiver_that_only_clears_the_plate_pose() -> None:
    import build_cone_lock_knob as knob
    from dataclasses import replace

    seat = replace(
        part.LOCK_SEAT_SPEC,
        overrides_mm={"ThreadDepth": knob.STUD_LEN - platform.PLATE_T + 0.25},
    )
    with pytest.raises(AssertionError, match="collar seats"):
        knob.require_seat_fit(seat, platform.PLATE_T, knob.STUD_LEN)


def test_cone_lock_requires_plug_tap_lead_beyond_full_thread_depth() -> None:
    import build_cone_lock_knob as knob
    from dataclasses import replace

    seat = replace(
        part.LOCK_SEAT_SPEC,
        depth_mm=part.LOCK_SEAT_SPEC.overrides_mm["ThreadDepth"] + 0.25,
    )
    with pytest.raises(AssertionError, match="plug-tap lead"):
        knob.require_seat_fit(seat, platform.PLATE_T, knob.STUD_LEN)


def test_shared_stop_preserves_exposed_geometry_with_a_deeper_clear_seat() -> None:
    import build_swing_stop_screw as stop

    stop.require_seat_fit(part.STOP_SEAT_SPEC, platform.PLATE_T)
    assert stop.PROUD_LEN == pytest.approx(9.875)
    assert stop.EMBED_LEN - stop.TIP_CHAMFER >= stop.SHANK_DIA
    assert stop.PROUD_LEN - platform.PLATE_T - stop.UNDERHEAD_FILLET - 0.51 >= 1.0
    assert part.STOP_SEAT_SPEC.overrides_mm["ThreadDepth"] - stop.EMBED_LEN >= 0.25
    assert part.STOP_DRILL_BOTTOM_WALL >= 1.5 * part.STOP_SCREW_HOLE_DIA
    assert part.STOP_NEAREST_CAVITY_WALL >= part.STOP_SCREW_HOLE_DIA


def test_shared_stop_rejects_the_former_shallow_receiver() -> None:
    from dataclasses import replace
    import build_swing_stop_screw as stop

    seat = replace(part.STOP_SEAT_SPEC, depth_mm=9.0, overrides_mm={"ThreadDepth": 6.0})
    with pytest.raises(AssertionError, match="bottoms"):
        stop.require_seat_fit(seat, platform.PLATE_T)


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import nameplate_spec
    from build_fillister_screw import HEAD_DIA, SHANK_DIA, SHANK_LEN, THREAD
    from build_nameplate import SCREW_HOLE_DIA

    assert part.NAMEPLATE_SEAT_SPEC.kind == "tapped_bottoming"
    assert part.NAMEPLATE_SEAT_SPEC.size == THREAD == "#4-40"
    assert part.NAMEPLATE_SEAT_SPEC.end == "blind"
    assert part.NAMEPLATE_SEAT_SPEC.thread_class == "2B"
    assert part.NAMEPLATE_SCREW_HOLE_DIA == pytest.approx(2.261)
    # Stock external threads engage the tap; only the plate is a clearance fit.
    assert SHANK_DIA == pytest.approx(2.8448)
    assert part.NAMEPLATE_SCREW_HOLE_DIA < SHANK_DIA < SCREW_HOLE_DIA < HEAD_DIA
    # Plate back face ON the deck (gap 0) and cut from the deck's +Y face.
    assert nameplate_spec.MOUNT_BACK_Y == pytest.approx(harmonic_base_spec.STACK_HEIGHT)
    assert nameplate_spec.MOUNT_NORMAL == (0.0, 1.0, 0.0)
    assert part.NAMEPLATE_SCREW_XZ == nameplate_spec.MOUNT_HOLE_XZ
    assert set(part.NAMEPLATE_SCREW_XZ) == {
        (209.75, 45.5),
        (209.75, -45.5),
        (163.75, 45.5),
        (163.75, -45.5),
    }
    # No mechanism shift applies (the plate anchors to the pad edge): the
    # stations are the pure mount-transform image of the plate holes.
    assert part.NAMEPLATE_SCREW_XZ == tuple(
        (nameplate_spec.MOUNT_POS[0] - y, nameplate_spec.MOUNT_POS[2] - x)
        for x, y in nameplate_spec.SCREW_XY
    )
    # Inside the raised rim's inner wall by >= 1.0.
    assert part.NAMEPLATE_RIM_CLEARANCE == pytest.approx(1.0)
    # The purchased 1/4-inch screw passes through the plate without bottoming
    # in the usable thread, independently of the deeper tap-drill runout.
    engagement = SHANK_LEN - nameplate_spec.PLATE_THICKNESS
    assert engagement == pytest.approx(4.85)
    assert engagement >= SHANK_DIA
    thread_depth = part.NAMEPLATE_SEAT_SPEC.overrides_mm["ThreadDepth"]
    assert thread_depth - engagement >= 0.5
    assert part.NAMEPLATE_SEAT_SPEC.depth_mm - engagement >= 0.75


def test_v2_platform_swing_stop_coordinate_is_rederived() -> None:
    """Mirror the drive-train formula without importing its COM-heavy graph."""
    pivot_x, pivot_z = part.PIVOT_SCREW_XZ
    assert part.PIVOT_SCREW_XZ == (
        -89.16663981674521 + POST_X_SHIFT,
        60.60437088764276 + POST_Z_SHIFT,
    )
    assert part.STOP_SCREW_XZ == part.SWING_HARDWARE_GEOMETRY.stop_xz
    east_slope = (platform.EAST_HALF_S - platform.HALF_WIDTH_N) / platform.PLATE_LEN
    stop_local_z = -105.0
    stop_local_x = -(
        platform.HALF_WIDTH_N + east_slope * (platform.NORTH_OVERHANG - stop_local_z)
    )

    edge_x, edge_z = -1.0, east_slope
    edge_norm = math.hypot(edge_x, edge_z)
    edge_x, edge_z = edge_x / edge_norm, edge_z / edge_norm
    disengage_rad = (
        platform.NOTCH_EXIT_TRAVEL + KNOB_COLLAR_DIA / 2.0 + platform.DISENGAGE_COLLAR_MARGIN
    ) / platform.SLOT_R
    angle = math.radians(platform.INCLINE_DEG) + disengage_rad
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    contact_x = pivot_x + stop_local_x * cos_a + stop_local_z * sin_a
    contact_z = pivot_z - stop_local_x * sin_a + stop_local_z * cos_a
    normal_x = edge_x * cos_a + edge_z * sin_a
    normal_z = -edge_x * sin_a + edge_z * cos_a
    derived = (
        contact_x + normal_x * STOP_SHANK_DIA / 2.0,
        contact_z + normal_z * STOP_SHANK_DIA / 2.0,
    )

    assert math.isclose(
        math.degrees(disengage_rad), part.SWING_HARDWARE_GEOMETRY.disengage_deg
    )
    assert math.isclose(derived[0], part.STOP_SCREW_XZ[0], abs_tol=1e-12)
    assert math.isclose(derived[1], part.STOP_SCREW_XZ[1], abs_tol=1e-12)

    engaged = math.radians(platform.INCLINE_DEG)
    cos_e, sin_e = math.cos(engaged), math.sin(engaged)
    edge_point_x = pivot_x + stop_local_x * cos_e + stop_local_z * sin_e
    edge_point_z = pivot_z - stop_local_x * sin_e + stop_local_z * cos_e
    engaged_normal = (
        edge_x * cos_e + edge_z * sin_e,
        -edge_x * sin_e + edge_z * cos_e,
    )
    stop_delta = (
        derived[0] - edge_point_x,
        derived[1] - edge_point_z,
    )
    engaged_gap = (
        stop_delta[0] * engaged_normal[0]
        + stop_delta[1] * engaged_normal[1]
        - STOP_SHANK_DIA / 2.0
    )
    assert engaged_gap >= 2.0
    assert math.isclose(engaged_gap, part.SWING_HARDWARE_GEOMETRY.stop_engaged_gap)


def test_v2_structural_holes_follow_the_same_installation_delta() -> None:
    # The 32T coherent-placement cutover shifts the block screws and spring
    # foot with the pinion rig while the arbor-pedestal seats stay on the
    # unchanged cylinder-drum axis.  U28 (2026-09-23): 2.2425 park-out, screws
    # +-8.5 about the pivot bore, block mid-depth 5.125 in from each outer face.
    # Ruling (c) (user, 2026-09-24): the block and spring-foot z stations come
    # from pinion_rig_layout -- the back block keeps its released seat, the
    # front block stands one feeler off the front strap, the spring rides with
    # the back strap.  The spring foot's seat is 20.0 east of the pivot bore
    # (the 2026-09-24 re-derive: outboard of the back strap, not west of it).
    import pinion_rig_layout as rig

    former_block_x = (-17.226441649810653, -0.22644164981065273)
    former_pivot_x = former_block_x[0] + 8.5
    former_feet = ((former_pivot_x - 20.0, rig.SPRING_Z - MECHANISM_Z_SHIFT),)
    assert part.BLOCK_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z) for z in rig.BLOCK_SEAT_Z for x in former_block_x
    )
    assert rig.BLOCK_SEAT_Z[1] == pytest.approx(82.875 + MECHANISM_Z_SHIFT)
    assert part.FOOT_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_feet
    )
    # U34c: the arbor pedestals left the #4-40 foot group for their own #8-32
    # seats, 19.0 outboard of each strap inner face on the unshifted drum axis.
    expected = ((-54.7 + MECHANISM_X_SHIFT, -91.652), (-54.7 + MECHANISM_X_SHIFT, 94.202))
    for actual, wanted in zip(part.PEDESTAL_SCREW_XZ, expected, strict=True):
        assert actual == pytest.approx(wanted)


def _socket_bore_geometry(x_mm: float, z_mm: float):
    """The bore wall's COM geometry signature, as measured on the built part.

    Faces read back one Ø25.50 cylinder per station whose bounding box spans
    the bore's own radius in X and Z and the socket depth in Y, so the specs
    can be resolved offline without a SolidWorks session.
    """
    from _part_pmi import _SURFACE_CYLINDER, _FaceGeometry

    radius = part.COLUMN_SOCKET_DIAMETER / 2000.0
    return _FaceGeometry(
        face=None,
        identity=_SURFACE_CYLINDER,
        parameters=(x_mm / 1000.0, 0.0, z_mm / 1000.0, 0.0, 1.0, 0.0, radius),
        outward_normal=None,
        box=(
            x_mm / 1000.0 - radius,
            (part.STACK_HEIGHT - part.COLUMN_SOCKET_DEPTH) / 1000.0,
            z_mm / 1000.0 - radius,
            x_mm / 1000.0 + radius,
            part.STACK_HEIGHT / 1000.0,
            z_mm / 1000.0 + radius,
        ),
    )


def test_each_socket_bore_finish_qualifies_exactly_one_station() -> None:
    """The four sockets differ only in X and Z, so a bore control that names
    less than both would qualify two faces (or all four) and abort the part
    build after ten minutes of cutting -- or, worse, print the seat grade
    against the wrong bore. Require a 1:1 station/control match, and hold the
    ambiguity the Z station exists to resolve."""
    from _gtol_spec import CylinderFace
    from _part_pmi import _face_matches

    spec = harmonic_base_spec
    geometries = {
        station: _socket_bore_geometry(*station) for station in spec.COLUMN_SOCKET_XZ
    }
    assert len(spec.SOCKET_BORE_FINISHES) == len(spec.COLUMN_SOCKET_XZ)
    for control in spec.SOCKET_BORE_FINISHES:
        matched = [
            station
            for station, geometry in geometries.items()
            if _face_matches(geometry, control.face)
        ]
        assert matched == [
            station
            for station in spec.COLUMN_SOCKET_XZ
            if spec.socket_bore_finish_key(*station) == control.key
        ]
        assert control.roughness_um == spec.SEAT_UM
        assert control.production_method == spec.SOCKET_BORE_TARGET
    x_only = CylinderFace(part.COLUMN_SOCKET_DIAMETER, contains_x_mm=part.COLUMN_X)
    size_only = CylinderFace(part.COLUMN_SOCKET_DIAMETER)
    assert sum(_face_matches(g, x_only) for g in geometries.values()) == 2
    assert sum(_face_matches(g, size_only) for g in geometries.values()) == 4


def test_socket_bore_leader_lands_on_bore_clear_of_the_cross_tap() -> None:
    """The sheet's one socket symbol leads to the INNER wall of the socket that
    section A-A puts in the upper half of the sheet, at a height that keeps the
    arrowhead inside the bore and clear of both the window the cross tap opens
    through that wall and the deck outline -- the first placement sat 1 mm (on
    paper) from the cross tap's cosmetic thread and read as the tap's."""
    import draw_harmonic_base as sheet

    x_mm, y_mm, z_mm = sheet.SOCKET_LEADER_POINT_MM
    station_x, station_z = sheet.SECTION_SOCKET_XZ
    assert (station_x, station_z) in part.COLUMN_SOCKET_XZ
    assert station_x == part.COLUMN_X
    assert station_z == min(z for x, z in part.COLUMN_SOCKET_XZ if x > 0.0)
    assert x_mm == part.COLUMN_X
    assert math.isclose(
        abs(z_mm - station_z), part.COLUMN_SOCKET_DIAMETER / 2.0, abs_tol=1e-9
    )
    assert abs(z_mm) < abs(station_z)
    tap_clearance = abs(y_mm - part.BASE_SCREW_Y) - part.BASE_CROSS_TAP_DRILL_DIA / 2.0
    deck_clearance = part.STACK_HEIGHT - y_mm
    assert min(tap_clearance, deck_clearance) > 4.0
    assert y_mm > part.STACK_HEIGHT - part.COLUMN_SOCKET_DEPTH


def test_transferred_pinion_block_seats_print_no_station() -> None:
    # Codex #855 P1: BLOCK_SEAT_Z is a model-pose station, and the pose's two
    # STRAP_AIR gaps stand the front block 2 x STRAP_AIR south of its
    # manufactured station -- more than a #8 floats in its clearance hole.
    # That is harmless only because the print never carries the station: the
    # four block seats are spotted THROUGH MHA-061 at assembly (U28 corollary;
    # MHA-061's note "SPOT BASE SEATS THROUGH BLOCK HOLES AT ASSEMBLY."), so
    # they leave the hole table and their one callout names the transfer.
    import draw_harmonic_base as sheet
    import pinion_rig_layout as rig
    from pinion_pivot_block_geometry import BLOCK_DEPTH

    block_seats = {(x, z, part.BLOCK_SCREW_HOLE_DIA) for x, z in part.BLOCK_SCREW_XZ}
    assert set(sheet.TRANSFER_BLOCK_HOLES) == block_seats
    assert not block_seats & set(sheet.TABLE_HOLES)
    assert sheet.TRANSFER_BLOCK_CALLOUT.startswith("TRANSFER FROM MHA-061")
    assert "AT ASSEMBLY" in sheet.TRANSFER_BLOCK_CALLOUT
    # The front pair's pose-vs-hardware offset the transfer absorbs.
    physical_front_seat = rig.PHYSICAL_FRONT_BLOCK_OUTER_Z + BLOCK_DEPTH / 2.0
    assert physical_front_seat - rig.BLOCK_SEAT_Z[0] == pytest.approx(
        2.0 * rig.STRAP_AIR
    )


def test_transferred_pedestal_and_spring_seats_print_no_station() -> None:
    # U34c (I27): each arbor pedestal is stood on the base with the arbor in
    # both straps and its #8-32 seat is spotted through the MHA-004 ledge
    # hole, so the pair leaves the hole table like the pinion-block seats. The
    # spring-foot seat, now alone on its #4-40 feature, takes a native callout
    # instead of a note naming a table row that no longer exists.
    import draw_harmonic_base as sheet

    pedestal_seats = {
        (x, z, part.PEDESTAL_SCREW_HOLE_DIA) for x, z in part.PEDESTAL_SCREW_XZ
    }
    assert set(sheet.TRANSFER_PEDESTAL_HOLES) == pedestal_seats
    assert sheet.TRANSFER_SPRING_HOLE[:2] == part.FOOT_SCREW_XZ[0]
    assert not (pedestal_seats | {sheet.TRANSFER_SPRING_HOLE}) & set(sheet.TABLE_HOLES)
    assert sheet.TRANSFER_PEDESTAL_CALLOUT == "TRANSFER FROM MHA-004\nAT ASSEMBLY;\n"
    assert sheet.TRANSFER_SPRING_CALLOUT == "TRANSFER FROM MHA-114\nAT ASSEMBLY;"
    assert not any(tag.startswith("G") for tag in sheet.HOLE_TAG_POSITIONS)


def _deck_seat_features_in_build() -> dict[str, object]:
    """Each deck Hole Wizard seat feature build_harmonic_base cuts, name ->
    its stations: the named SupportHoldDownSeats call plus every row of the
    ``for tag, spec, xz, label in (...)`` seat-group loop."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    features: dict[str, object] = {"SupportHoldDownSeats": part.HOLE_XZ}
    named_cuts = {
        kw.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "wizard_holes"
        for kw in node.keywords
        if kw.arg == "name" and isinstance(kw.value, ast.Constant)
    }
    assert "SupportHoldDownSeats" in named_cuts
    loops = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.For, ast.AsyncFor))
        and isinstance(node.target, ast.Tuple)
        and [getattr(elt, "id", None) for elt in node.target.elts]
        == ["tag", "spec", "xz", "label"]
    ]
    assert len(loops) == 1
    for row in loops[0].iter.elts:
        tag, _spec, xz, _label = row.elts
        features[tag.value] = eval(ast.unparse(xz), vars(part))  # noqa: S307
    return features


def test_tapped_hole_note_count_is_derived_from_the_deck_seat_features() -> None:
    # warm-c486: the sheet removed 16 descriptive "Tapped Hole" notes against a
    # literal 14, because U34c split the two pedestal seats out of
    # FootScrewHoles into their own PedestalSeats feature. SolidWorks drops one
    # such note per deck seat FEATURE into each plan view, so the count is
    # derived from the same per-feature table that feeds the hole table.
    import ast
    from pathlib import Path

    import draw_harmonic_base as sheet

    build_features = _deck_seat_features_in_build()
    names = [name for name, _stations, _dia in sheet.DECK_TAPPED_SEAT_FEATURES]
    assert len(names) == len(set(names))
    assert {name for name, _stations, _dia in sheet.DECK_TAPPED_SEAT_FEATURES} == set(
        build_features
    )
    for name, stations, _dia in sheet.DECK_TAPPED_SEAT_FEATURES:
        assert tuple(stations) == tuple(build_features[name]), name

    source = Path(sheet.__file__).read_text(encoding="utf-8")
    calls = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call)]
    plan_views = [
        call
        for call in calls
        if getattr(call.func, "id", None) == "place_view"
        and any(isinstance(arg, ast.Constant) and arg.value == "*Top" for arg in call.args)
    ]
    assert len(plan_views) == len(sheet.PLAN_VIEWS)
    assert sheet.TAPPED_HOLE_NOTES == len(build_features) * len(sheet.PLAN_VIEWS)
    assert sheet.TAPPED_HOLE_NOTES == 16

    finalize = [call for call in calls if getattr(call.func, "id", None) == "finalize_drawing"]
    assert len(finalize) == 1
    keywords = {kw.arg: kw.value for kw in finalize[0].keywords}
    # A literal count is what went stale; the call must name the derivation.
    assert ast.unparse(keywords["expected_redundant_notes"]) == "TAPPED_HOLE_NOTES"
    assert ast.unparse(keywords["redundant_note_substrings"]) == "FINAL_SHEET_REMOVED_NOTES"
    assert sheet.FINAL_SHEET_REMOVED_NOTES == (sheet.TAPPED_HOLE_NOTE,)
    assert sheet.TAPPED_HOLE_NOTE == "Tapped Hole"


def test_spotface_band_reaches_the_setter_unchanged() -> None:
    # The band now reads (upper, lower) like every _fit_limits band and goes
    # through deviations(); the setter must still receive (lower, upper) =
    # (0.0, +0.5), so the printed limits cannot move.
    import ast
    from pathlib import Path

    from _fit_limits import deviations

    assert harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM == (0.5, 0.0)
    assert deviations(harmonic_base_spec.SPOTFACE_DEPTH_BAND_MM) == (0.0, 0.5)
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    setter_band_args = [
        ast.unparse(arg)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "set_dimension_bilateral_tolerance"
        for arg in node.args
        if isinstance(arg, ast.Starred)
    ]
    assert setter_band_args == ["*deviations(SPOTFACE_DEPTH_BAND_MM)"]


def test_isometric_render_hides_model_annotations_only_after_the_save(
    monkeypatch, tmp_path
) -> None:
    # warm-c486 eye pass: the part-owned surface-finish PMI rendered as
    # floating "A1-A4 BORES Ra 3.2" / "FLANGE EDGES, 4 SIDES" symbols. The
    # part must be saved (annotations shown) before the display toggle drops.
    import asyncio
    from types import SimpleNamespace

    events: list[tuple] = []

    async def fake_save(adapter, part_name, views=("isometric",)):
        events.append(("save", part_name, tuple(views)))
        return {"part": "p.SLDPRT", "stl": "p.STL"}

    class Extension:
        shown = True

        def SetUserPreferenceToggle(self, pref, option, value):
            events.append(("toggle", pref, option, value))
            self.shown = value
            return True

        def GetUserPreferenceToggle(self, pref, option):
            return self.shown

    extension = Extension()

    class Adapter:
        currentModel = SimpleNamespace(Extension=extension)

        async def export_image(self, request):
            events.append(("export", request["view_orientation"], extension.shown))
            return SimpleNamespace(is_success=True, data=None, error=None)

    monkeypatch.setattr(part, "save_part_and_images", fake_save)
    monkeypatch.setattr(part, "OUT_PNG", tmp_path)
    artefacts = asyncio.run(part._save_with_annotation_free_render(Adapter()))

    assert events == [
        ("save", part.PART_NAME, ()),
        ("toggle", 31, 0, False),  # swDisplayAnnotations, swDetailingNoOptionSpecified
        ("export", "isometric", False),
    ]
    assert artefacts["isometric"] == str(
        (tmp_path / part.PART_NAME / f"{part.PART_NAME}_isometric.png").resolve()
    )


def test_callout_clash_check_names_overlaps_and_crowding() -> None:
    import draw_harmonic_base as sheet

    callouts = {
        "left": (0.160, 0.245, 0.240, 0.265),
        "right": (0.228, 0.245, 0.310, 0.265),  # overlaps "left" by 12 mm
        "clear": (0.320, 0.100, 0.330, 0.110),
    }
    obstacles = {
        "view holes top": (0.225, 0.160, 0.345, 0.240),
        "table": (0.010, 0.130, 0.1595, 0.270),  # 0.5 mm from "left"
    }
    findings = sheet.find_callout_clashes(callouts, obstacles)
    assert findings == [
        "callout left vs callout right: clearance -12.0 mm",
        "callout left vs table: clearance 0.5 mm",
    ]
    assert sheet.box_gap((0.0, 0.0, 1.0, 1.0), (1.5, 0.0, 2.0, 1.0)) == pytest.approx(0.5)
    assert sheet.find_callout_clashes({"a": (0.0, 0.0, 0.01, 0.01)}, {"b": (0.0115, 0.0, 0.02, 0.01)}) == []


# The display data the hb-callout-cal leaf logged for e0e287c83's sheet 2:
# (anchor, [shoulder/leader lines], [(text, lower-left, height)]), sheet metres.
E0E287C83_CALLOUTS = {
    "MHA-061 block transfer": (
        [0.262, 0.252],
        [(0.278818, 0.216872, 0.304252, 0.243612), (0.278222, 0.216247, 0.278818, 0.216872),
         (0.304252, 0.243612, 0.221335, 0.243612)],
        [("4X ", [0.241215, 0.254832], 0.0035), ("<MOD-DIAM>", [0.247938, 0.254778], 0.0035),
         (" 3.45 ", [0.253216, 0.254832], 0.0035), ("<HOLE-DEPTH>", [0.264854, 0.254778], 0.0035),
         (" 15.00", [0.269854, 0.254832], 0.0035), ("TRANSFER FROM MHA-061", [0.233047, 0.249222], 0.0035),
         ("AT ASSEMBLY; 8-32 UNC - 2B ", [0.221335, 0.243666], 0.0035),
         ("<HOLE-DEPTH>", [0.284734, 0.243612], 0.0035), (" 12.75", [0.289734, 0.243666], 0.0035)],
    ),
    "MHA-004 pedestal transfer": (
        [0.2, 0.252],
        [(0.264616, 0.218237, 0.242252, 0.243612), (0.265187, 0.217589, 0.264616, 0.218237),
         (0.242252, 0.243612, 0.159335, 0.243612)],
        [("2X ", [0.179215, 0.254832], 0.0035), ("<MOD-DIAM>", [0.185938, 0.254778], 0.0035),
         (" 3.45 ", [0.191216, 0.254832], 0.0035), ("<HOLE-DEPTH>", [0.202854, 0.254778], 0.0035),
         (" 19.50", [0.207854, 0.254832], 0.0035), ("TRANSFER FROM MHA-004", [0.171047, 0.249222], 0.0035),
         ("AT ASSEMBLY; 8-32 UNC - 2B ", [0.159335, 0.243666], 0.0035),
         ("<HOLE-DEPTH>", [0.222734, 0.243612], 0.0035), (" 16.00", [0.227734, 0.243666], 0.0035)],
    ),
    "MHA-114 spring transfer": (
        [0.269, 0.1575],
        [(0.271627, 0.175879, 0.309959, 0.149112), (0.271163, 0.176202, 0.271627, 0.175879),
         (0.309959, 0.149112, 0.229628, 0.149112)],
        [("<MOD-DIAM>", [0.251576, 0.160278], 0.0035), (" 2.26 ", [0.256855, 0.160332], 0.0035),
         ("<HOLE-DEPTH>", [0.268492, 0.160278], 0.0035), (" 11.30", [0.273493, 0.160332], 0.0035),
         ("TRANSFER FROM MHA-114", [0.240047, 0.154722], 0.0035),
         ("AT ASSEMBLY; 4-40 UNC - 2B ", [0.229628, 0.149166], 0.0035),
         ("<HOLE-DEPTH>", [0.293027, 0.149112], 0.0035), (" 9.28", [0.298027, 0.149166], 0.0035)],
    ),
    "MHA-132 cross-tap": (
        [0.285, 0.13],
        [(0.329577, 0.098247, 0.342356, 0.113278), (0.328923, 0.097478, 0.329577, 0.098247),
         (0.342356, 0.113278, 0.229232, 0.113278)],
        [("4X ", [0.262404, 0.141166], 0.0035), ("<MOD-DIAM>", [0.269127, 0.141113], 0.0035),
         (" 4.04 ", [0.274406, 0.141166], 0.0035), ("<HOLE-DEPTH>", [0.286043, 0.141113], 0.0035),
         (" 48 MIN", [0.291044, 0.141166], 0.0035), ("MHA-132 TUBE CROSS-SCREWS", [0.250907, 0.135556], 0.0035),
         ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", [0.230711, 0.13], 0.0035),
         ("DEPTHS FROM SPOTFACE FLOOR", [0.248979, 0.124444], 0.0035),
         ("ON A1-A4 X CENTRES", [0.261375, 0.118888], 0.0035),
         ("2 EACH FRONT/REAR FACE 10-32 UNF - 2B ", [0.229232, 0.113331], 0.0035),
         ("<HOLE-DEPTH>", [0.322837, 0.113278], 0.0035), (" 46.00", [0.327838, 0.113331], 0.0035)],
    ),
}
E0E287C83_OBSTACLES = {
    "view holes top": (0.22285, 0.1591, 0.33715, 0.2309),
    "view holes front": (0.22285, 0.0883375, 0.33715, 0.1016625),
    "view section A-A": (0.3683375, 0.0991, 0.3816625, 0.1709),
    "label 'TOP VIEW SCALE 1:4'": (0.234753, 0.23265, 0.279474, 0.237034),
    "label 'FRONT CROSS-TAP VIEW SCALE 1:4'": (0.244837, 0.070864, 0.321565, 0.075249),
    "table DetailItem460": (0.018, 0.135058, 0.162763, 0.26),
}


def test_callout_box_rule_fails_e0e287c83_sheet_on_its_real_display_data() -> None:
    """Fail-first on real data: e0e287c83's two eye-pass defects, plus the
    pedestal underline touching the hole table. A box of shoulder plus anchor
    alone missed the spring text rising into the plan (hb-callout-cal)."""
    import draw_harmonic_base as sheet

    callouts = {
        label: sheet.callout_text_box(anchor, lines, texts, label)
        for label, (anchor, lines, texts) in E0E287C83_CALLOUTS.items()
    }
    # The block spans the shoulder and rises to the top row's lower-left plus height.
    assert callouts["MHA-114 spring transfer"] == pytest.approx((0.229628, 0.149112, 0.309959, 0.163832))
    assert sheet.find_callout_clashes(callouts, E0E287C83_OBSTACLES) == [
        "callout MHA-004 pedestal transfer vs callout MHA-061 block transfer: clearance -14.7 mm",
        "callout MHA-004 pedestal transfer vs table DetailItem460: clearance -3.4 mm",
        "callout MHA-114 spring transfer vs view holes top: clearance -4.7 mm",
    ]


def test_callout_check_treats_the_sheet_frame_and_title_block_as_obstacles() -> None:
    import inspect
    from types import SimpleNamespace

    import draw_harmonic_base as sheet
    from _drawing_layout_check import DrawableRegion
    from _drawing_registry import DRAWING_TEMPLATES

    template = DRAWING_TEMPLATES[sheet.SPEC.layout]
    margin = 0.0127  # the template's ISheet::GetZoneMargin, 0.5 in each side
    drawable = DrawableRegion.from_margins(
        template.width_m, template.height_m, left=margin, right=margin, bottom=margin, top=margin
    )
    frame = sheet.frame_obstacles(
        (template.width_m, template.height_m),
        drawable,
        (template.title_block_left_m, template.title_block_top_m),
    )
    assert frame["frame top"] == pytest.approx((0.0, 0.2667, 0.4318, 0.2794))
    assert frame["title block"] == pytest.approx((0.216, 0.0, 0.4318, 0.066))

    # The live path: the real sheet_drawable_region reads the zone margins off
    # the current sheet and hands back a real DrawableRegion (hb-render-1 died
    # on region.box, which a stubbed region never exercised).
    class Adapter:
        def _attempt(self, operation, default=None):
            return operation()

    live_sheet = SimpleNamespace(GetZoneMargin=lambda code: margin)
    ddoc = SimpleNamespace(GetCurrentSheet=lambda: live_sheet)
    assert sheet._sheet_frame_obstacles(Adapter(), ddoc) == frame

    callouts = {
        # A transfer block nudged up until its top row reaches 0.5 mm off the frame.
        "against the frame": (0.233, 0.2455, 0.293, 0.2662),
        # A cross-tap block dropped into the title block's top edge.
        "into the title block": (0.229, 0.060, 0.342, 0.090),
        "clear": (0.171, 0.2409, 0.2306, 0.2610),
    }
    assert sheet.find_callout_clashes(callouts, frame) == [
        "callout against the frame vs frame top: clearance 0.5 mm",
        "callout into the title block vs title block: clearance -6.0 mm",
    ]
    source = inspect.getsource(sheet._check_hole_sheet_callouts)
    assert "obstacles = _sheet_frame_obstacles(adapter, ddoc)" in source


# hb-render-2 (e533ef6fd) logged these, sheet metres: the MHA-004 and MHA-114
# callouts' display lines and boxes, and the plan's view label the MHA-004
# leader ran through.
E533EF6FD_PEDESTAL_LINES = [
    (0.264542, 0.218153, 0.230540, 0.240834),
    (0.265261, 0.217673, 0.264542, 0.218153),
    (0.230540, 0.240834, 0.171047, 0.240834),
]
E533EF6FD_PEDESTAL_BOX = (0.171047, 0.240834, 0.230540, 0.261110)
E533EF6FD_SPRING_LINES = [
    (0.271602, 0.175848, 0.309959, 0.140112),
    (0.271188, 0.176233, 0.271602, 0.175848),
    (0.309959, 0.140112, 0.229628, 0.140112),
]
E533EF6FD_SPRING_BOX = (0.229628, 0.140112, 0.309959, 0.154832)
E533EF6FD_TOP_VIEW_LABEL = (0.234753, 0.232650, 0.279474, 0.237034)


def test_leader_check_fails_e533ef6fd_leader_through_the_top_view_label() -> None:
    """Fail-first on e533ef6fd's layout: its MHA-004 leader struck through
    "TOP" of the plan's view label (hb-render-2 eye pass)."""
    import draw_harmonic_base as sheet

    leaders = {"MHA-004 pedestal transfer": sheet.leader_segments(E533EF6FD_PEDESTAL_LINES)}
    texts = {
        "callout MHA-004 pedestal transfer": E533EF6FD_PEDESTAL_BOX,
        "label 'TOP VIEW SCALE 1:4'": E533EF6FD_TOP_VIEW_LABEL,
    }
    assert sheet.find_leader_crossings(leaders, texts) == [
        "leader of callout MHA-004 pedestal transfer crosses label 'TOP VIEW SCALE 1:4'"
    ]
    # Beside the plan's top-left corner, the same label is off that leader.
    x, y = sheet.HOLES_TOP_LABEL_XY
    width = E533EF6FD_TOP_VIEW_LABEL[2] - E533EF6FD_TOP_VIEW_LABEL[0]
    height = E533EF6FD_TOP_VIEW_LABEL[3] - E533EF6FD_TOP_VIEW_LABEL[1]
    texts["label 'TOP VIEW SCALE 1:4'"] = (x, y - height, x + width, y)
    assert sheet.find_leader_crossings(leaders, texts) == []
    assert sheet.find_callout_clashes(
        {"MHA-004 pedestal transfer": E533EF6FD_PEDESTAL_BOX},
        {"label": texts["label 'TOP VIEW SCALE 1:4'"]},
    ) == []


def test_leader_check_skips_its_own_callout_box_among_foreign_texts() -> None:
    import draw_harmonic_base as sheet

    # Among foreign texts a callout's own whole box is skipped (its rows are
    # checked separately, below); a foreign note on the leader's path is not.
    leaders = {"MHA-114 spring transfer": sheet.leader_segments(E533EF6FD_SPRING_LINES)}
    texts = {
        "callout MHA-114 spring transfer": E533EF6FD_SPRING_BOX,
        "note on the path": (0.285, 0.160, 0.295, 0.165),
        "note beside it": (0.300, 0.170, 0.310, 0.175),
    }
    assert sheet.find_leader_crossings(leaders, texts) == [
        "leader of callout MHA-114 spring transfer crosses note on the path"
    ]


E533EF6FD_SPRING_TEXTS = [
    ("<MOD-DIAM>", [0.251576, 0.151278], 0.0035),
    (" 2.26 ", [0.256855, 0.151332], 0.0035),
    ("<HOLE-DEPTH>", [0.268492, 0.151278], 0.0035),
    (" 11.30", [0.273493, 0.151332], 0.0035),
    ("TRANSFER FROM MHA-114", [0.240047, 0.145722], 0.0035),
    ("AT ASSEMBLY; 4-40 UNC - 2B ", [0.229628, 0.140166], 0.0035),
    ("<HOLE-DEPTH>", [0.293027, 0.140112], 0.0035),
    (" 9.28", [0.298027, 0.140166], 0.0035),
]


def test_callout_text_rows_centre_each_row_on_the_shoulder() -> None:
    import draw_harmonic_base as sheet

    rows = sheet.callout_text_rows(E533EF6FD_SPRING_LINES, E533EF6FD_SPRING_TEXTS, "spring")
    centre = (0.229628 + 0.309959) / 2.0
    assert list(rows) == [
        "<MOD-DIAM> 2.26 <HOLE-DEPTH> 11.30",
        "TRANSFER FROM MHA-114",
        "AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28",
    ]
    assert rows["TRANSFER FROM MHA-114"] == pytest.approx(
        (0.240047, 0.145722, 2.0 * centre - 0.240047, 0.149222)
    )
    # The widest row spans the shoulder.
    assert rows["AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28"][2] == pytest.approx(0.309959)


def test_leader_check_flags_a_leader_through_its_own_rows() -> None:
    """e533ef6fd's spring leader left the shoulder's right end and rose
    through "9.28" of its own thread row (hb-render-2 eye pass)."""
    import draw_harmonic_base as sheet

    leaders = {"MHA-114 spring transfer": sheet.leader_segments(E533EF6FD_SPRING_LINES)}
    own = {
        "MHA-114 spring transfer": sheet.callout_text_rows(
            E533EF6FD_SPRING_LINES, E533EF6FD_SPRING_TEXTS, "spring"
        )
    }
    assert sheet.find_leader_crossings(leaders, {}, own) == [
        "leader of callout MHA-114 spring transfer crosses its own row "
        "'AT ASSEMBLY; 4-40 UNC - 2B <HOLE-DEPTH> 9.28'"
    ]
    # The same block right of the hole, its leader leaving the near (left)
    # end up and away from the text: the joint corner does not count.
    shift = 0.2712 + 0.002 - 0.229628
    moved_lines = [
        (0.271602, 0.175848, 0.229628 + shift, 0.140112),
        (0.271188, 0.176233, 0.271602, 0.175848),
        (0.309959 + shift, 0.140112, 0.229628 + shift, 0.140112),
    ]
    moved_texts = [(text, [x + shift, y], h) for text, (x, y), h in E533EF6FD_SPRING_TEXTS]
    leaders = {"MHA-114 spring transfer": sheet.leader_segments(moved_lines)}
    own = {"MHA-114 spring transfer": sheet.callout_text_rows(moved_lines, moved_texts, "spring")}
    assert sheet.find_leader_crossings(leaders, {}, own) == []
    # A transfer leader drops away from its rows: no finding.
    pedestal = {"MHA-004 pedestal transfer": sheet.leader_segments(E533EF6FD_PEDESTAL_LINES)}
    assert sheet.find_leader_crossings(pedestal, {}, {"MHA-004 pedestal transfer": {
        "8-32 UNC - 2B <HOLE-DEPTH> 16.00": (0.174589, 0.240888, 0.227000, 0.244388),
    }}) == []


# hb-render-3 (12259de3a) logged the spring at (0.286, 0.1485): box, and the
# hole its leader tip reaches. The block spans anchor -40.96/+39.37 mm in x.
HB_RENDER_3_SPRING_BOX = (0.245040, 0.140112, 0.325372, 0.154832)
HB_RENDER_3_SPRING_TIP_X = 0.271562


def test_spring_text_sits_wholly_right_of_its_hole() -> None:
    import draw_harmonic_base as sheet

    left = sheet.SPRING_CALLOUT_XY[0] - (0.286 - HB_RENDER_3_SPRING_BOX[0])
    right = sheet.SPRING_CALLOUT_XY[0] + (HB_RENDER_3_SPRING_BOX[2] - 0.286)
    assert HB_RENDER_3_SPRING_BOX[0] < HB_RENDER_3_SPRING_TIP_X  # 12259de3a: under the text
    assert left > HB_RENDER_3_SPRING_TIP_X + 0.002  # now clear of it, near end left
    assert right < 0.368340 - 0.010  # the section view's left edge


def test_only_notes_that_reach_the_final_sheet_are_obstacles() -> None:
    import draw_harmonic_base as sheet

    # hb-render-3 flagged leaders over these; finalize deletes them.
    assert not sheet.note_reaches_final_sheet("1/4-20 Tapped Hole")
    assert not sheet.note_reaches_final_sheet("#8-32 tapped hole")
    assert not sheet.note_reaches_final_sheet(" \r\n ")  # DetailItem420: no ink
    assert sheet.note_reaches_final_sheet("TOP VIEW SCALE 1:4")
    assert sheet.note_reaches_final_sheet("D1")
    assert sheet.FINAL_SHEET_REMOVED_NOTES == (sheet.TAPPED_HOLE_NOTE,)
    import ast
    import inspect
    from pathlib import Path

    tree = ast.parse(Path(sheet.__file__).read_text(encoding="utf-8"))
    finalize = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "finalize_drawing"
    )
    keywords = {kw.arg: ast.unparse(kw.value) for kw in finalize.keywords}
    assert keywords["redundant_note_substrings"] == "FINAL_SHEET_REMOVED_NOTES"
    assert "note_reaches_final_sheet(_note_text(adapter, annotation))" in inspect.getsource(
        sheet._check_hole_sheet_callouts
    )


def test_section_line_boxes_cover_arrows_and_labels_in_sheet_space() -> None:
    import draw_harmonic_base as sheet

    size = (0.4318, 0.2794)
    arrows = [0.3293, 0.1563, 0.0, 0.3411, 0.1563, 0.0, 0.3293, 0.2351, 0.0, 0.3411, 0.2351, 0.0]
    labels = [0.3433, 0.1596, 0.0, 0.3433, 0.2384, 0.0]
    boxes = sheet.section_line_boxes("A", arrows, labels, 0.005, "A", size)
    assert boxes["section A arrow 1"] == pytest.approx((0.3273, 0.1543, 0.3431, 0.1583))
    assert boxes["label section A 1"] == pytest.approx((0.3433, 0.1546, 0.3483, 0.1596))
    # A spring block right of its hole but at the old height runs into the "A".
    high = (0.274, 0.1400, 0.3544, 0.1548)
    low = (0.274, 0.1364, 0.3544, 0.1511)
    assert sheet.find_callout_clashes({"spring": high}, boxes) == [
        "callout spring vs label section A 1: clearance -0.2 mm",
        "callout spring vs section A arrow 1: clearance -0.5 mm",
    ]
    assert sheet.find_callout_clashes({"spring": low}, boxes) == []
    with pytest.raises(RuntimeError, match="not in sheet space"):
        sheet.section_line_boxes("A", [v * 10 for v in arrows], labels, 0.005, "A", size)
    with pytest.raises(RuntimeError, match="expected 12 arrow"):
        sheet.section_line_boxes("A", arrows[:9], labels, 0.005, "A", size)


def test_segment_crossing_covers_inside_through_and_near_misses() -> None:
    import draw_harmonic_base as sheet

    box = (0.0, 0.0, 1.0, 1.0)
    assert sheet.segment_crosses_box((-1.0, 0.5, 2.0, 0.5), box)  # straight through
    assert sheet.segment_crosses_box((0.2, 0.2, 0.3, 0.3), box)  # wholly inside
    assert sheet.segment_crosses_box((0.5, 0.5, 3.0, 3.0), box)  # leaves it
    assert not sheet.segment_crosses_box((1.1, -1.0, 1.1, 2.0), box)  # passes beside
    assert not sheet.segment_crosses_box((1.5, 0.0, 3.0, 1.0), box)  # diagonal miss
    assert not sheet.segment_crosses_box((-0.5, 1.2, 1.5, 1.2), box)  # parallel above


def test_leader_sides_name_the_attached_end_and_the_end_nearest_the_hole() -> None:
    import draw_harmonic_base as sheet

    # e533ef6fd: the leader left the right end, and the hole (x 0.2712) was
    # nearer that end (0.3100) than the left one (0.2296).
    assert sheet.leader_sides(E533EF6FD_SPRING_LINES, "spring") == (2, 2)
    assert sheet.leader_segments(E533EF6FD_SPRING_LINES) == E533EF6FD_SPRING_LINES[:2]
    # 0.017 further right, a right-end leader would leave the farther end.
    shifted = [
        (0.271602, 0.175848, 0.326959, 0.140112),
        (0.271188, 0.176233, 0.271602, 0.175848),
        (0.326959, 0.140112, 0.246628, 0.140112),
    ]
    assert sheet.leader_sides(shifted, "spring") == (2, 1)
    with pytest.raises(RuntimeError, match="no shoulder or no leader"):
        sheet.leader_sides(shifted[2:], "spring")


def test_datum_origin_boxes_pad_each_axis_for_its_labels() -> None:
    import draw_harmonic_base as sheet

    # Axis points read off hb-render-2's sheet PNG (the seat reads the real ones
    # from IDatumOrigin.GetAxisPoints2): X from the flange corner right, Y up.
    boxes = sheet.datum_origin_boxes([0.2224, 0.146, 0.2418, 0.146, 0.209, 0.159, 0.209, 0.174])
    assert boxes["origin X axis"] == pytest.approx((0.2189, 0.1425, 0.2453, 0.1495))
    assert boxes["origin Y axis"] == pytest.approx((0.2055, 0.1555, 0.2125, 0.1775))
    # e533ef6fd's spring callout sat on the X axis and its "X" label.
    assert sheet.find_callout_clashes({"MHA-114 spring transfer": E533EF6FD_SPRING_BOX}, boxes) == [
        "callout MHA-114 spring transfer vs origin X axis: clearance -9.4 mm"
    ]
    with pytest.raises(RuntimeError, match="not 4"):
        sheet.datum_origin_boxes([0.0] * 6)


def test_callout_box_rule_refuses_display_data_it_cannot_box() -> None:
    import draw_harmonic_base as sheet

    with pytest.raises(RuntimeError, match="no horizontal shoulder"):
        sheet.callout_text_box([0.0, 0.0], [(0.0, 0.0, 0.01, 0.01)], [("X", [0.0, 0.0], 0.0035)], "x")
    with pytest.raises(RuntimeError, match="no text rows"):
        sheet.callout_text_box([0.0, 0.0], [(0.0, 0.0, 0.01, 0.0)], [], "x")


def test_hole_sheet_callout_check_runs_on_every_callout_before_finalize() -> None:
    import ast
    from pathlib import Path

    import draw_harmonic_base as sheet

    tree = ast.parse(Path(sheet.__file__).read_text(encoding="utf-8"))
    build = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "build"
    )
    calls = [node for node in ast.walk(build) if isinstance(node, ast.Call)]
    check = [call for call in calls if getattr(call.func, "id", None) == "_check_hole_sheet_callouts"]
    assert len(check) == 1
    keywords = {kw.arg: kw.value for kw in check[0].keywords}
    assert ast.unparse(keywords["callouts"]) == "hole_sheet_callouts"
    assert ast.unparse(keywords["datum_origin"]) == "hole_feature.DatumOrigin"
    table = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["hole_sheet_callouts"]
    )
    callout_names = {ast.unparse(value) for value in table.value.values}
    # Every callout's leader is moved to its nearer shoulder end before the check.
    side_loop = next(
        node
        for node in ast.walk(build)
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "hole_sheet_callouts.items()"
    )
    assert "_attach_leader_nearest_hole(adapter, display, label)" in ast.unparse(side_loop)
    assert side_loop.lineno < check[0].lineno
    placed = {
        target.id
        for node in ast.walk(build)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) == "add_native_hole_callout"
        for target in node.targets
    }
    unassigned = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", None) == "add_native_hole_callout"
    ]
    assert not unassigned  # every callout is kept, so every one is checked
    assert callout_names == placed == {
        "block_callout", "pedestal_callout", "spring_callout", "tap_callout"
    }
    assert {ast.unparse(value) for value in keywords["views"].values} == {
        "hole_top", "hole_side", "section"
    }
    finalize = next(call for call in calls if getattr(call.func, "id", None) == "finalize_drawing")
    assert check[0].lineno < finalize.lineno


def test_transfer_thread_goes_on_its_own_line_in_the_shared_band() -> None:
    # Main's hb-notes-2 ruling (a): the block and pedestal callouts end their
    # process text with a newline so the 8-32 thread gets its own fourth line.
    # add_native_hole_callout strips that newline, so the sheet restores it
    # in the prefix DEFINITION (associative variables kept).
    import draw_harmonic_base as sheet

    assert sheet.TRANSFER_BLOCK_CALLOUT == "TRANSFER FROM MHA-061\nAT ASSEMBLY;\n"
    assert sheet.TRANSFER_SPRING_CALLOUT.endswith("AT ASSEMBLY;")

    class Display:
        def __init__(self, definition: str) -> None:
            self.definition = definition

        def GetText(self, part: int) -> str:
            assert part == 5
            return self.definition

        def SetText(self, part: int, text: str) -> None:
            assert part == 1
            self.definition = text

    native = "<hw-thread> <MOD-DEPTH> <hw-threaddepth>"
    display = Display(sheet.TRANSFER_PEDESTAL_CALLOUT.rstrip() + " " + native)
    sheet._keep_process_line_break(display, sheet.TRANSFER_PEDESTAL_CALLOUT, "pedestal")
    assert display.definition == "TRANSFER FROM MHA-004\nAT ASSEMBLY;\n" + native
    spring = Display(sheet.TRANSFER_SPRING_CALLOUT + " " + native)
    sheet._keep_process_line_break(spring, sheet.TRANSFER_SPRING_CALLOUT, "spring")
    assert spring.definition == sheet.TRANSFER_SPRING_CALLOUT + " " + native
    with pytest.raises(RuntimeError, match="does not start with its process text"):
        sheet._keep_process_line_break(Display(native), sheet.TRANSFER_BLOCK_CALLOUT, "block")


def test_hole_sheet_callouts_moved_clear_per_the_eye_pass() -> None:
    import draw_harmonic_base as sheet

    assert sheet.PEDESTAL_CALLOUT_XY == (0.200, 0.252)
    assert sheet.BLOCK_CALLOUT_XY == (0.262, 0.252)
    assert sheet.SPRING_CALLOUT_XY == (0.315, 0.1448)
    assert sheet.CROSS_TAP_CALLOUT_XY == (0.285, 0.120)
    assert sheet.HOLES_TOP_LABEL_XY == (0.170, 0.237)


# hb-render-4 (28d06157b) sheet-2 display data: the cross-tap block's six rows
# and the two callout boxes the eye pass read as one block.
HB_RENDER_4_CROSS_TAP = (
    [0.285, 0.12],
    [(0.329717, 0.098055, 0.342356, 0.103278), (0.328783, 0.097670, 0.329717, 0.098055),
     (0.342356, 0.103278, 0.229232, 0.103278)],
    [("4X ", [0.262404, 0.131166], 0.0035), ("<MOD-DIAM>", [0.269127, 0.131113], 0.0035),
     (" 4.04 ", [0.274406, 0.131166], 0.0035), ("<HOLE-DEPTH>", [0.286043, 0.131113], 0.0035),
     (" 48 MIN", [0.291044, 0.131166], 0.0035), ("MHA-132 TUBE CROSS-SCREWS", [0.250907, 0.125556], 0.0035),
     ("THRU BOTH WALLS, SINGLE CONTINUOUS THREAD", [0.230711, 0.12], 0.0035),
     ("DEPTHS FROM SPOTFACE FLOOR", [0.248979, 0.114444], 0.0035),
     ("ON A1-A4 X CENTRES", [0.261375, 0.108888], 0.0035),
     ("2 EACH FRONT/REAR FACE 10-32 UNF - 2B ", [0.229232, 0.103331], 0.0035),
     ("<HOLE-DEPTH>", [0.322837, 0.103278], 0.0035), (" 46.00", [0.327838, 0.103331], 0.0035)],
)
HB_RENDER_4_BOXES = {
    "MHA-061 block transfer": (0.233047, 0.240834, 0.292540, 0.261110),
    "MHA-004 pedestal transfer": (0.171047, 0.240834, 0.230540, 0.261110),
    "MHA-114 spring transfer": (0.274041, 0.136412, 0.354372, 0.151132),
    "MHA-132 cross-tap": (0.229232, 0.103278, 0.342356, 0.134666),
}


def test_callout_rules_fail_the_hb_render_4_cross_tap_block() -> None:
    """Fail-first on real data: Main's hb-render-4 eye pass read the spring
    block 1.7 mm over the cross-tap block as its fourth row, and the cross-tap
    ran six rows. The side-by-side transfer pair is not one column."""
    import draw_harmonic_base as sheet

    anchor, lines, texts = HB_RENDER_4_CROSS_TAP
    rows = sheet.callout_text_rows(lines, texts, "MHA-132 cross-tap")
    assert sheet.find_tall_callouts({"MHA-132 cross-tap": rows}) == [
        "callout MHA-132 cross-tap runs 6 rows, over the 4-row note rule"
    ]
    assert sheet.find_merged_blocks(HB_RENDER_4_BOXES) == [
        "callout MHA-114 spring transfer over callout MHA-132 cross-tap: "
        "1.7 mm apart, under the 5.6 mm row pitch"
    ]
    assert sheet.find_tall_callouts({"four rows": dict(list(rows.items())[:4])}) == []


def test_cross_tap_callout_carries_hole_facts_only() -> None:
    # hb-render-4 eye pass: count/drill/depth, the thru instruction and the
    # thread each on a row; the depth datum is the model's (the tap starts on
    # the spotface floor) and the X location is a dimension, not text.
    import ast
    import inspect

    import draw_harmonic_base as sheet

    assert sheet.CROSS_TAP_PROCESS == "THRU BOTH WALLS, SINGLE CONTINUOUS THREAD\n"
    source = inspect.getsource(sheet)
    for gone in ("DEPTHS FROM SPOTFACE FLOOR\n", "ON A1-A4 X CENTRES\n", "2 EACH FRONT/REAR FACE"):
        assert gone not in source
    calls = [
        node for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_keep_process_line_break"
        and ast.unparse(node.args[0]) == "tap_callout"
    ]
    assert [ast.unparse(call.args[1]) for call in calls] == ["CROSS_TAP_PROCESS"]
    # The Hole Wizard seats the taps on the spotface floor, so its depths
    # already run from there.
    assert part.BASE_SPOTFACE_PLANE_Z - part.BASE_SPOTFACE_DEPTH == part.BASE_SCREW_SEAT_Z


def test_cross_tap_x_is_a_chained_model_dimension_on_the_front_view() -> None:
    import draw_harmonic_base as sheet

    assert harmonic_base_spec.DRAWING_DIMENSIONS["CrossTapReference"] == {
        "CrossTapX", "CrossTapPitch"
    }
    assert harmonic_base_spec.DRAWING_PRECISION["CrossTapReference"] == {
        "CrossTapX": 1, "CrossTapPitch": 1
    }
    assert "CrossTapReference" in part.REFERENCE_SKETCHES
    assert {"CrossTapX", "CrossTapPitch"} <= set(sheet.HOLE_SIDE_KEEP)
    # 31.6 is also the table's A1/A2 X LOC from the same flange edge.
    assert part.BOTTOM_LENGTH / 2.0 - part.COLUMN_X == pytest.approx(31.6)


def test_deck_land_worst_case_is_proven_instead_of_noted() -> None:
    # hb-render-4 eye pass: the 1.0 MIN land note put a dimension in a note.
    assert not hasattr(harmonic_base_spec, "DRAWING_NOTES")
    for stack in part.COLUMN_SOCKET_LAND_STACKS.values():
        assert stack == pytest.approx({
            "nominal": 5.5,
            "flange length": -0.4,
            "pad length": -0.4,
            "rim width": -0.8,
            "bore location": -0.8,
            "matched bore": -0.25,
            "bore edge break": -0.25,
            "rim edge break": -0.25,
        })
        assert sum(stack.values()) == pytest.approx(2.35)
    # The same stack on the rejected 1.6 mm pad land would fail the 1.0 MIN.
    assert sum(part.column_socket_land_stack(1.6).values()) < part.COLUMN_SOCKET_LAND_MIN
    # Main's rider: the Ø26.0 ceiling is a functional judgement, so the
    # stack reports how much bore the land could still absorb.
    assert part.COLUMN_SOCKET_BREAK_EVEN_BORE == pytest.approx(28.7)
    rejected = part.column_socket_land_stack(1.6)
    assert part.column_socket_break_even_bore(rejected) < part.COLUMN_SOCKET_MATCH_BORE_MAX


def test_stamped_id_leader_clears_the_socket_bores() -> None:
    # 2026-09-25 Codex machinist review (hb-render-5, clarity): the stamped-ID
    # leader ran through the A3 socket bore. The leader starts where SolidWorks
    # put it on hb-render-5 (the last line's right end) and ends on the serial.
    import draw_harmonic_base as sheet

    def clearance(anchor: tuple[float, float]) -> float:
        start = (
            anchor[0] + sheet.SERIAL_LEADER_START_OFFSET_M[0],
            anchor[1] + sheet.SERIAL_LEADER_START_OFFSET_M[1],
        )
        tip = sheet._plan_xy(*part.SERIAL_XZ)
        dx, dy = tip[0] - start[0], tip[1] - start[1]
        gaps = []
        for x, z in part.COLUMN_SOCKET_XZ:
            cx, cy = sheet._plan_xy(x, z)
            t = ((cx - start[0]) * dx + (cy - start[1]) * dy) / (dx * dx + dy * dy)
            t = max(0.0, min(1.0, t))
            gaps.append(
                math.hypot(cx - start[0] - t * dx, cy - start[1] - t * dy)
                - part.COLUMN_SOCKET_DIAMETER * sheet.VIEW_SCALE / 2000.0
            )
        return min(gaps)

    assert clearance((0.125, 0.130)) < 0.0  # the reviewed sheet: through A3
    assert sheet.SERIAL_NOTE_XY == (0.080, 0.130)
    assert clearance(sheet.SERIAL_NOTE_XY) >= 0.004

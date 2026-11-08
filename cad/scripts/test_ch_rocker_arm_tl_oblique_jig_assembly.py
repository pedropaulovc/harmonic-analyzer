"""Offline contract for the oblique-trammel jig assembly (MHA-CH-06-TL-00).

The poses close on the calculator's rail and carrier geometry and the leadscrew
feed's layout, the builder places all made and bought families,
one free DOF slides the carriages and their shoulder-screw pivot stacks,
the interference contracts cover only in-situ receiver seats and threads, the jig stays
a shop fixture outside the machine tree, and both passes retain both carrier
ends while their full sweeps clear the table and column cover by pinned margins.
"""

from __future__ import annotations

import ast
import json
import math
import re
import types
from pathlib import Path

import pytest
import yaml

import _buildgraph as bg
import _config
import _ch_rocker_arm_tl_oblique_jig_interference as contracts
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_rail_kit_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as handwheel
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_leadscrew_kit_leadscrew_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as lever_washer
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_vn_oblique_pivot_shim_spec as pivot_shim
import ch_rocker_arm_tl_oblique_riser_spec as riser
import sh_vn_clamping_kit_t_nut_spec as t_nut
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_bracket_screw_spec as bracket_screw
import ch_rocker_arm_tl_vn_oblique_rail_kit_rail_spec as guide_rail
import draw_ch_rocker_arm_tl_oblique_jig_assembly as drawing


BUILDER = Path(__file__).with_name("build_ch_rocker_arm_tl_oblique_jig_assembly.py")
JIG = "ch_rocker_arm_tl_oblique_jig"
PART_STEMS = {
    physical.replace("-", "_")
    for physical, _configuration in spec.COMPONENT_IDENTITIES.values()
}
# Registry rows outside the jig's own MHA-CH-06-TL- series and the shop
# clamping kit are shared vendor inputs reused unchanged from the machine
# (R4: the loose 1/8 stop pins are MHA-SM-VN-53 stock); each keeps its
# global identity and machine quantity, and the jig only consumes its count.
JIG_PREFIX = spec.DRAWING_NUMBER.rsplit("-", 1)[0] + "-"
SHARED_VENDOR_FAMILIES = frozenset(
    family
    for family, (physical, _configuration) in spec.COMPONENT_IDENTITIES.items()
    if not _config.parts(physical)["number"].startswith((JIG_PREFIX, "MHA-SH-VN-"))
)
JIG_ONLY_PART_STEMS = PART_STEMS - {
    spec.COMPONENT_IDENTITIES[family][0].replace("-", "_")
    for family in SHARED_VENDOR_FAMILIES
}
PIVOT_FAMILIES = {spec.PIVOT_SCREW: 2, spec.PIVOT_SPACER: 2, spec.PIVOT_SHIM: 10}
# Each screw family and its fastener-table rows (count, callout, engagement):
# the riser screw's TL-VN-67 also holds the feed nut on (owner ruling
# 2026-11-04, option B); owner A″ groups both TL-28 joints in TL-VN-62.
# The common TL-VN-61 holds the rails and the strap at CL, CR and HUB (R4).
SCREW_ROWS = {
    spec.RAIL_SCREW: (
        fasteners.RAIL_TO_BAR, fasteners.END_CLAMP, fasteners.HUB_CLAMP,
    ),
    spec.CARRIAGE_SCREW: (fasteners.BLOCK_TO_CARRIAGE,),
    spec.PILLOW_BLOCK_SCREW: (fasteners.KP08_TO_BRACKET, fasteners.BRACKET_TO_BAR),
    spec.RISER_SCREW: (fasteners.RISER_TO_CARRIER, fasteners.NUT_TO_FEED_BLOCK),
    spec.LEVER_SCREW: (fasteners.LEVER_TO_CARRIER,),
}


def _image(rows, origin, point):
    """Machine coordinates of a part-frame ``point`` placed at ``origin``."""
    return tuple(
        origin[axis] + sum(point[k] * rows[k][axis] for k in range(3))
        for axis in range(3)
    )


def _inside_xy(polygon, point) -> bool:
    """Filled-polygon inclusion, accepting contact within roundoff."""
    x, y = point
    inside = False
    for a, b in zip(polygon, (*polygon[1:], polygon[0])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        cross = dx * (y - a[1]) - dy * (x - a[0])
        if (
            abs(cross) <= 1e-8 * max(1.0, math.hypot(dx, dy))
            and min(a[0], b[0]) - 1e-9 <= x <= max(a[0], b[0]) + 1e-9
            and min(a[1], b[1]) - 1e-9 <= y <= max(a[1], b[1]) + 1e-9
        ):
            return True
        if (a[1] > y) != (b[1] > y):
            crossing = a[0] + (y - a[1]) * dx / dy
            if x < crossing:
                inside = not inside
    return inside


def _all_rows():
    for placements in spec.PLACEMENTS.values():
        yield from (rows for _origin, rows in placements)


@pytest.fixture(scope="module")
def report() -> spec.ClearanceReport:
    return spec.clearance_report()


def test_every_rotation_is_proper() -> None:
    for rows in _all_rows():
        x, y, z = rows
        for a in rows:
            assert math.fsum(c * c for c in a) == pytest.approx(1.0)
        for a, b in ((x, y), (y, z), (z, x)):
            assert math.fsum(p * q for p, q in zip(a, b)) == pytest.approx(
                0.0, abs=1e-12
            )
        cross = (
            x[1] * y[2] - x[2] * y[1],
            x[2] * y[0] - x[0] * y[2],
            x[0] * y[1] - x[1] * y[0],
        )
        assert cross == pytest.approx(tuple(z))


def test_base_bars_carry_their_rails_onto_the_studs() -> None:
    """One base bar part, two members: Bar1 as saved under rail 1, Bar2
    turned over (180° about its long axis) under rail 2; each lies on the
    table, its slots on its studs and its tapped-through rail holes on its
    rail's axis."""
    studs = spec.stud_centres()
    assert spec.TURNED_OVER == {1: False, 2: True}
    assert base_bar.QUANTITY == len(spec.BASE_BAR_PLACEMENTS) == 2
    for rail, (origin, rows) in zip(spec.RAILS, spec.BASE_BAR_PLACEMENTS):
        flip = -1.0 if spec.TURNED_OVER[rail] else 1.0
        assert rows[0] == pytest.approx(spec.rail_rows(rail)[0])
        assert rows[1] == pytest.approx(
            tuple(flip * c for c in spec.rail_rows(rail)[1])
        )
        assert rows[2] == pytest.approx((0.0, 0.0, flip))
        zs = [_image(rows, origin, (0.0, 0.0, z))[2] for z in (0.0, base_bar.BAR_THICK)]
        assert sorted(zs) == pytest.approx([0.0, trammel.BASE_BAR_THICK])
        near = _image(rows, origin, (0.0, 0.0, 0.0))
        far = _image(rows, origin, (trammel.BASE_BAR_LENGTH, 0.0, 0.0))
        assert near[:2] == pytest.approx(trammel.rail_point(rail, trammel.RAIL_NEAR_S))
        # Datum-trimmed kit rail is flush at both bar ends.
        assert far[:2] == pytest.approx(trammel.rail_point(rail, trammel.BASE_BAR_FAR_S))
        assert trammel.RAIL_FAR_S == pytest.approx(trammel.BASE_BAR_FAR_S)
        assert trammel.RAIL_OVERHANG == pytest.approx(0.0)
        for which, slot in (
            ("near", (base_bar.NEAR_SLOT_X, base_bar.NEAR_SLOT_Y, 0.0)),
            ("far", (base_bar.FAR_SLOT_X, base_bar.FAR_SLOT_Y, 0.0)),
        ):
            stud = studs[f"{which} stud {rail}"]
            assert _image(rows, origin, slot)[:2] == pytest.approx(stud, abs=1e-9)
        for x in base_bar.RAIL_HOLE_X:
            hole = _image(rows, origin, (x, 0.0, 0.0))[:2]
            on_rail = trammel.rail_point(rail, trammel.RAIL_NEAR_S + x)
            assert hole == pytest.approx(on_rail, abs=1e-9)
        assert spec.bar_point(rail, (x, 0.0, 0.0)) == pytest.approx(
            _image(rows, origin, (x, 0.0, 0.0))
        )
    # Rail 1's bar on -X, rail 2's on +X: mirror images in X; the turned-over
    # bar's slots sit where the saved bar's mirror puts them.
    (o1, _rows1), (o2, _rows2) = spec.BASE_BAR_PLACEMENTS
    assert o1[0] < 0.0 < o2[0]
    assert (o1[0], o1[1]) == pytest.approx((-o2[0], o2[1]))
    for which, slot in (
        ("near", (base_bar.NEAR_SLOT_X, base_bar.NEAR_SLOT_Y, 0.0)),
        ("far", (base_bar.FAR_SLOT_X, base_bar.FAR_SLOT_Y, 0.0)),
    ):
        x1, y1, _z1 = spec.bar_point(1, slot)
        assert spec.bar_point(2, slot)[:2] == pytest.approx((-x1, y1), abs=1e-9)


def test_pivot_blocks_and_screws_sit_on_the_pin_stations() -> None:
    assert spec.PIN_STATION == pytest.approx(trammel.SYMMETRIC_PIN_STATION["inner"])
    for rail, (origin, rows), screw in zip(
        spec.RAILS, spec.BLOCK_PLACEMENTS, spec.PIVOT_SCREW_ORIGINS, strict=True,
    ):
        assert origin[2] == pytest.approx(trammel.CARRIAGE_TOP_Z)
        bore = _image(rows, origin, (pivot_block.BORE_X, 0.0, 0.0))
        assert bore[:2] == pytest.approx(trammel.rail_point(rail, spec.PIN_STATION))
        assert screw[:2] == pytest.approx(bore[:2])
        assert screw[2] == pytest.approx(origin[2] + pivot_block.BLOCK_HEIGHT - pivot_block.BORE_DEPTH)
    assert trammel.CARRIER_UNDERSIDE_Z == pytest.approx(
        trammel.PIVOT_BLOCK_TOP_Z + trammel.PIVOT_SHIM_PACK + trammel.PIVOT_SPACER_LENGTH
    )
    assert trammel.CARRIER_TOP_Z == pytest.approx(trammel.CARRIER_UNDERSIDE_Z + trammel.CARRIER_THICK)


def test_carrier_riser_strap_clamps_and_lever_close_on_the_carrier_frame() -> None:
    def on_carrier(point):
        return _image(
            spec.CARRIER_ROWS, spec.CARRIER_ORIGIN, (point[0], 0.0, -point[1])
        )

    assert spec.THETA == 0.0 and spec.POSE.rotation == 0.0
    assert spec.CARRIER_ROWS[1] == pytest.approx((0.0, 0.0, 1.0))
    for hole, pin_origin in zip(trammel.pin_pair("inner"), spec.PIVOT_SCREW_ORIGINS):
        machine = on_carrier(hole)
        assert machine[:2] == pytest.approx(pin_origin[:2])
        assert machine[2] == trammel.CARRIER_TOP_Z
    hub = spec.POSE.to_machine(trammel.HUB)
    riser_hub = _image(spec.RISER_ROWS, spec.RISER_ORIGIN, (*riser.HUB_HOLE, 0.0))
    assert riser_hub[:2] == pytest.approx(hub, rel=0.0, abs=1e-9)
    # CL, CR and HUB: each common screw over its carrier tap and riser hole.
    for role, (origin, rows) in zip(
        spec.STRAP_CLAMP_ROLES, spec.STRAP_CLAMP_SCREW_PLACEMENTS, strict=True
    ):
        assert origin[:2] == pytest.approx(
            spec.POSE.to_machine(spec.STRAP_CLAMP_POINTS[role]), rel=0.0, abs=1e-9
        )
        assert rows == spec.CARRIED_ROWS
    assert spec.STRAP_CLAMP_POINTS == {"CL": carrier.CL, "CR": carrier.CR, "HUB": carrier.HUB}
    for (origin, _rows), hole in zip(
        spec.STOP_PIN_PLACEMENTS, riser.STOP_PIN_HOLES, strict=True
    ):
        on_riser = _image(spec.RISER_ROWS, spec.RISER_ORIGIN, (*hole, 0.0))
        assert origin[:2] == pytest.approx(on_riser[:2], rel=0.0, abs=1e-9)
        assert origin[2] == pytest.approx(trammel.CARRIER_TOP_Z)
    for model_x, hole in zip(feed_lever.HOLE_X, carrier.LEVER_HOLES):
        lever = _image(
            spec.FEED_LEVER_ROWS,
            spec.FEED_LEVER_ORIGIN,
            (model_x, 0.0, -feed_lever.HOLE_Y),
        )
        assert lever == pytest.approx(on_carrier(hole))
    # The lever's grip end points at the operator (machine -Y), its top up.
    assert spec.FEED_LEVER_ROWS[0] == pytest.approx((0.0, -1.0, 0.0))
    assert spec.FEED_LEVER_ROWS[1] == pytest.approx((0.0, 0.0, 1.0))


@pytest.mark.parametrize("station", range(4))
def test_riser_holes_and_screws_are_coaxial_with_carrier_taps(station: int) -> None:
    x, y = riser.SCREW_HOLES[station]
    tap_x, tap_y = carrier.RISER_SCREWS[station]
    tap = _image(spec.CARRIER_ROWS, spec.CARRIER_ORIGIN, (tap_x, 0.0, -tap_y))
    screw_origin, screw_rows = spec.RISER_SCREW_PLACEMENTS[station]
    # Compare the physical axis lines, not just their different-height origins:
    # the riser is Z-up; the screw and carrier tap axes are local +Y.
    for z in (0.0, riser.THICKNESS):
        hole = _image(spec.RISER_ROWS, spec.RISER_ORIGIN, (x, y, z))
        for origin, axis in (
            (tap, spec.CARRIER_ROWS[1]),
            (screw_origin, screw_rows[1]),
        ):
            offset = tuple(hole[i] - origin[i] for i in range(3))
            along = math.fsum(offset[i] * axis[i] for i in range(3))
            radial = tuple(offset[i] - along * axis[i] for i in range(3))
            assert math.hypot(*radial) < 1e-9


def test_end_brackets_stand_on_bar_1_under_the_screw() -> None:
    """Each TL-28 stands on bar 1's top at its KP08 station: its two holes
    straddle the screw axis at the KP08's 42 mm pitch and land on the bar's
    two counterbored #8 holes (owner ruling Main 2026-11-06, option B)."""
    assert leadscrew.RAIL == 1 and not spec.TURNED_OVER[leadscrew.RAIL]
    bar_holes = sorted(
        tuple(round(c, 9) for c in spec.bar_point(1, (x, y, 0.0))[:2])
        for x, y in leadscrew.BASE_BAR_HOLES
    )
    bracket_holes = []
    assert len(spec.END_BRACKET_PLACEMENTS) == spec.QUANTITIES[spec.END_BRACKET]
    for s, (origin, rows) in zip(leadscrew.KP08_S, spec.END_BRACKET_PLACEMENTS):
        assert origin[2] == trammel.BASE_BAR_THICK
        # +X outward (rail 1's +lateral), +Y along the rail away from the spindle.
        outward = _image(rows, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
        assert outward[:2] == pytest.approx(
            tuple(
                b - a
                for a, b in zip(
                    leadscrew.point(s, 0.0), leadscrew.point(s, 1.0), strict=True
                )
            )
        )
        mid = sum(leadscrew.BRACKET_HOLES_X) / 2.0
        axis = _image(rows, origin, (mid, 0.0, leadscrew.BRACKET_THICK))
        assert axis[:2] == pytest.approx(leadscrew.point(s, leadscrew.SCREW_LATERAL))
        assert axis[2] == pytest.approx(leadscrew.KP08_BASE_Z)
        assert axis[2] + leadscrew.KP08_AXIS_HEIGHT == pytest.approx(
            leadscrew.SCREW_AXIS_Z
        )
        bracket_holes += [
            tuple(round(c, 9) for c in _image(rows, origin, (x, 0.0, 0.0))[:2])
            for x in leadscrew.BRACKET_HOLES_X
        ]
    assert [c for hole in sorted(bracket_holes) for c in hole] == pytest.approx(
        [c for hole in bar_holes for c in hole], abs=1e-6
    )


def test_feed_nut_closes_on_the_leadscrew_axis_over_the_lug_taps() -> None:
    origin, rows = spec.FEED_BLOCK_PLACEMENTS[0]
    bore = _image(rows, origin, (
        feed_block.NUT_FACE_X, feed_block.NUT_AXIS_Y, feed_block.NUT_AXIS_Z,
    ))
    assert bore[:2] == pytest.approx(leadscrew.point(
        spec.CARRIAGE_STATION + feed_block.NUT_FACE_X, leadscrew.SCREW_LATERAL,
    ))
    assert bore[2] == pytest.approx(leadscrew.SCREW_AXIS_Z)
    assert feed_block.NUT_FACE_X == feed_block.LUG_X1
    # The FeedNut seats on the lug's far face, its body away from the spindle.
    nut = spec.FEED_NUT_PLACEMENTS[0]
    assert spec.frame_point(nut, (0.0, 0.0, 0.0)) == pytest.approx(bore)
    body_end = _image(rows, origin, (
        feed_block.NUT_FACE_X + feed_nut.LENGTH, feed_block.NUT_AXIS_Y, feed_block.NUT_AXIS_Z,
    ))
    assert spec.frame_point(nut, (0.0, feed_nut.LENGTH, 0.0)) == pytest.approx(body_end)
    # Each flange hole sits over a lug tap on the lug's diagonals (option B:
    # 45° on the 16 PCD).
    taps = sorted(_image(rows, origin, (feed_block.NUT_FACE_X, y, z)) for y, z in feed_block.NUT_HOLES_YZ)
    holes = sorted(spec.frame_point(nut, (x, 0.0, z)) for x, z in feed_nut.HOLE_CENTRES)
    assert [c for p in holes for c in p] == pytest.approx([c for p in taps for c in p], abs=1e-9)
    assert len(feed_block.NUT_HOLES_YZ) == feed_nut.SCREW_COUNT == 4
    for y, z in feed_block.NUT_HOLES_YZ:
        dy, dz = y - feed_block.NUT_AXIS_Y, z - feed_block.NUT_AXIS_Z
        assert abs(dy) == pytest.approx(abs(dz))
        assert math.hypot(dy, dz) == pytest.approx(feed_nut.HOLE_PCD / 2.0)
    # Each flat head stands on its tap's axis, its top SCREW_GRIP off the lug
    # face (the flange plus the nominal head proud of it), shank into the lug.
    assert len(spec.NUT_SCREW_PLACEMENTS) == feed_nut.SCREW_COUNT
    for (screw_origin, screw_rows), (y, z) in zip(
        spec.NUT_SCREW_PLACEMENTS, feed_block.NUT_HOLES_YZ, strict=True
    ):
        assert screw_origin == pytest.approx(
            _image(rows, origin, (feed_block.NUT_FACE_X + feed_nut.SCREW_GRIP, y, z))
        )
        assert _image(screw_rows, (0.0, 0.0, 0.0), (0.0, -1.0, 0.0)) == pytest.approx(
            _image(rows, (0.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
        )


def test_explode_stands_every_layer_clear_and_in_sight() -> None:
    assert spec.EXPLODED_VIEW_NAME == "JIG_EXPLODED"
    instances = {
        family: {
            spec.instance_name(family, index)
            for index in range(spec.QUANTITIES[family])
        }
        for family in spec.BOM_ORDER
    }
    for _label, selectors, axis, distance in spec.EXPLODE_STEPS:
        assert set(selectors) <= set(spec.QUANTITIES) | set().union(*instances.values())
        assert axis in {"x", "y", "z"} and distance != 0.0
    moved = {
        name
        for _label, selectors, _axis, _d in spec.EXPLODE_STEPS
        for selector in selectors
        for name in instances.get(selector, {selector})
    }
    # The frame stays: the bars, the rails and end brackets screwed to
    # The feed block lifts as one integral component.
    assert set(spec.EXPLODE_STATIC) == {
        spec.BASE_BAR_1,
        spec.BASE_BAR_2,
        spec.END_BRACKET,
        spec.RAIL,
        spec.LEADSCREW,
        spec.PILLOW_BLOCK,
        spec.HOLD_DOWN_STUD,
    }
    static = {
        name for family in spec.EXPLODE_STATIC for name in instances[family]
    }
    assert not moved & static
    assert moved | static == set().union(*instances.values())
    assert all(
        spec.explode_shift(name, axis) == 0.0
        for name in static for axis in "xyz"
    )
    assert all(
        any(spec.explode_shift(name, axis) != 0.0 for axis in "xyz")
        for name in moved
    )


def test_occurrence_shift_sums_common_and_exact_steps_and_rejects_ambiguity() -> None:
    for family, count in spec.QUANTITIES.items():
        for axis in "xyz":
            expected = []
            for index in range(count):
                name = spec.instance_name(family, index)
                total = sum(
                    distance
                    for _label, selectors, direction, distance in spec.EXPLODE_STEPS
                    if direction == axis
                    and any(selector in (family, name) for selector in selectors)
                )
                assert spec.explode_shift(name, axis) == pytest.approx(total)
                if axis == "z":
                    assert spec.explode_lift(name) == pytest.approx(total)
                expected.append(total)
            if len(set(expected)) == 1:
                assert spec.explode_shift(family, axis) == pytest.approx(expected[0])
            else:
                with pytest.raises(ValueError, match="nonuniform"):
                    spec.explode_shift(family, axis)
                with pytest.raises(ValueError, match="nonuniform"):
                    spec.explode_lift(family)
    with pytest.raises(ValueError, match="unknown explode occurrence"):
        spec.explode_shift("nonexistent-occurrence-99", "z")


@pytest.mark.parametrize("family", tuple(spec.KIT_IDENTITIES))
def test_kit_occurrence_shift_uses_configured_role_local_references(
    monkeypatch, family: str,
) -> None:
    first = spec.instance_name(family, 0)
    common = spec.explode_shift(family, "z")
    monkeypatch.setattr(
        spec, "EXPLODE_STEPS",
        (*spec.EXPLODE_STEPS, ("one kit occurrence", (first,), "z", 1.0)),
    )
    assert spec.explode_shift(first, "z") == pytest.approx(common + 1.0)
    if spec.QUANTITIES[family] == 1:
        # LeadScrew and FeedNut: the one occurrence is the whole family.
        assert spec.explode_shift(family, "z") == pytest.approx(common + 1.0)
    else:
        second = spec.instance_name(family, 1)
        assert spec.explode_shift(second, "z") == pytest.approx(common)
        with pytest.raises(ValueError, match="nonuniform"):
            spec.explode_shift(family, "z")

    physical, configuration = spec.KIT_IDENTITIES[family]
    for selector in (
        f"@{configuration}:0",
        f"@{configuration}:{spec.QUANTITIES[family] + 1}",
        f"{configuration}:1",
        f"{physical}-1",
        f"{family}-1",
    ):
        with pytest.raises(ValueError, match="unknown explode occurrence"):
            spec.explode_shift(selector, "z")


def _assert_explode_source_guards(steps) -> None:
    """Exercise the production assertions with altered presentation data only."""
    path = Path(spec.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    start = next(
        node.lineno for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "explode_shift"
    )
    stop = next(
        node.lineno for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "PlanTag"
    )
    body = [node for node in tree.body if start <= node.lineno < stop]
    namespace = dict(vars(spec), EXPLODE_STEPS=steps)
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)


@pytest.mark.parametrize("failure", ("missing motion", "static rider"))
def test_explode_source_refuses_incomplete_or_static_motion_coverage(failure: str) -> None:
    if failure == "missing motion":
        steps = tuple(
            (label, tuple(s for s in selectors if s != spec.PIVOT_SHIM), axis, d)
            for label, selectors, axis, d in spec.EXPLODE_STEPS
        )
    else:
        steps = (*spec.EXPLODE_STEPS, (
            "table structure must not move", (spec.BASE_BAR_1,), "z", 1.0,
        ))
    with pytest.raises(AssertionError, match="every occurrence"):
        _assert_explode_source_guards(steps)


def test_explode_selectors_resolve_to_the_placed_occurrences() -> None:
    # The jig_explode leaf resolves every step's selectors against the placed
    # components: a family moves its identity group, an instance selector
    # (the riser and nut screws share TL-VN-67 but explode apart) its own
    # occurrence, a configured member occurrence (a kit member or a base
    # bar) through its persisted role reference.
    import build_ch_rocker_arm_tl_oblique_jig_assembly as builder

    member_names = {
        selector: f"member-{index}"
        for index, selector in enumerate(spec.MEMBER_COMPONENT_REFERENCES)
    }
    groups = {family: [] for family in spec.QUANTITIES}
    by_name = {}
    for family, quantity in spec.QUANTITIES.items():
        for index in range(quantity):
            selector = spec.instance_name(family, index)
            component = types.SimpleNamespace(Name2=member_names.get(selector, selector))
            groups[family].append(component)
            by_name[component.Name2] = component
    assert {member_names.get(name, name) for name in spec.INSTANCE_NAMES} == set(by_name)
    for label, selectors, _axis, _distance in spec.EXPLODE_STEPS:
        moved = [
            component.Name2
            for component in builder.explode_step_components(
                label, selectors, groups, by_name, member_names
            )
        ]
        expected = {
            member_names.get(occurrence, occurrence)
            for selector in selectors
            for occurrence in spec.explode_occurrences(selector)
        }
        assert len(moved) == len(set(moved)) and set(moved) == expected, label
    steps = {label: selectors for label, selectors, _axis, _distance in spec.EXPLODE_STEPS}

    def names(label: str) -> list[str]:
        return [
            component.Name2
            for component in builder.explode_step_components(
                label, steps[label], groups, by_name, member_names
            )
        ]

    assert names("riser screws lift out") == [f"{spec.RISER_SCREW}-{n}" for n in range(1, 5)]
    nut_screws = [f"{spec.RISER_SCREW}-{n}" for n in range(5, 9)]
    for key in "xy":
        assert names(f"nut screws back out along {key}") == nut_screws
        assert names(f"feed nut backs off along {key}") == [
            *(component.Name2 for component in groups[spec.FEED_NUT]),
            *nut_screws,
        ]
    # Rail screws lift; the bracket family's lower TL-28 screws drop.
    assert names("rail screws lift out") == [f"{spec.RAIL_SCREW}-{n}" for n in range(1, 17)]
    assert names("bar screws drop out") == [f"{spec.PILLOW_BLOCK_SCREW}-{n}" for n in range(5, 9)]
    # The common screw's strap clamps lift out of the carrier on their own steps.
    assert names("end clamp screws lift out") == [f"{spec.RAIL_SCREW}-{n}" for n in (17, 18)]
    assert names("hub clamp screw lifts out") == [f"{spec.RAIL_SCREW}-19"]
    assert names("stop pins lift out") == [f"{spec.STOP_PIN}-{n}" for n in (1, 2)]
    with pytest.raises(RuntimeError, match="unknown explode selector"):
        builder.explode_step_components(
            "past the family", (f"{spec.RISER_SCREW}-9",), groups, by_name, member_names
        )
    with pytest.raises(RuntimeError, match="has no component"):
        builder.explode_step_components(
            "not placed", spec.NUT_SCREW_INSTANCES[:1], groups, {}, member_names
        )


def test_feed_nut_and_its_screws_explode_along_their_axis_clear_of_the_lug() -> None:
    """TL-00 review ce83ac3b (sheet 5): the nut and its four flat heads
    explode off the lug's +X face along the screws' axis, away from the
    spindle, the screws past the nut's body end."""
    axis = spec.NUT_EXPLODE_AXIS

    def part_axis(placement, k):
        origin = spec.frame_point(placement, (0.0, 0.0, 0.0))
        tip = spec.frame_point(placement, tuple(float(i == k) for i in range(3)))
        return [t - o for t, o in zip(tip, origin)]

    # The pose proof: the nut's and every nut screw's part +Y (head up) is
    # the feed block's +X, horizontal, away from the spindle and off the
    # machine axes on the oblique rail, so each move is two native steps.
    for placement in (*spec.FEED_NUT_PLACEMENTS, *spec.NUT_SCREW_PLACEMENTS):
        assert part_axis(placement, 1) == pytest.approx(axis, abs=1e-12)
    assert part_axis(spec.FEED_BLOCK_PLACEMENTS[0], 0) == pytest.approx(axis, abs=1e-12)
    assert axis[2] == 0.0 and math.hypot(*axis) == pytest.approx(1.0)
    assert sum(a * r for a, r in zip(axis, spec.rail_direction(spec.leadscrew.RAIL))) > 0.0
    assert abs(axis[0]) > 1e-3 and abs(axis[1]) > 1e-3
    nut = spec.instance_name(spec.FEED_NUT, 0)
    lift = dict(zip("xyz", (0.0, 0.0, 90.0)))  # the blocks lift off with them
    for name, along in (
        (nut, spec.FEED_NUT_BACK_OFF),
        *((screw, spec.FEED_NUT_BACK_OFF + spec.NUT_SCREW_BACK_OUT)
          for screw in spec.NUT_SCREW_INSTANCES),
    ):
        for k, key in enumerate("xyz"):
            assert spec.explode_shift(name, key) == pytest.approx(
                along * axis[k] + lift[key], abs=1e-9
            )
    # Along the axis from the lug face: the nut's seat face stands off it,
    # its body end past that, and each screw's tip past the body end.
    seat = spec.FEED_NUT_BACK_OFF
    body_end = seat + spec.feed_nut.LENGTH_MAX
    tip = (
        spec.feed_nut.SCREW_GRIP - spec.riser_screw.DIMS.length
        + spec.FEED_NUT_BACK_OFF + spec.NUT_SCREW_BACK_OUT
    )
    assert seat > 0.0
    assert tip - body_end >= spec.NUT_SCREW_EXPLODED_CLEARANCE


def _assert_feed_nut_explode_guards(**overrides) -> None:
    """Exercise the feed nut's explode assertions with altered inputs only."""
    path = Path(spec.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def assigns(node, name):
        return isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        )

    start = next(node.lineno for node in tree.body if assigns(node, "NUT_EXPLODE_AXIS"))
    stop = next(node.lineno for node in tree.body if assigns(node, "_NUT_SCREW_MOVES"))
    body = [node for node in tree.body if start <= node.lineno < stop]
    exec(
        compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"),
        dict(vars(spec), **overrides),
    )


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        # A nut screw no longer on the nut's axis: here the block's +Y.
        ({"NUT_SCREW_PLACEMENTS": spec.FEED_BLOCK_PLACEMENTS}, "share one axis"),
        # A screw too long to stand past the nut's body end.
        (
            {"riser_screw": types.SimpleNamespace(DIMS=types.SimpleNamespace(
                length=spec.riser_screw.DIMS.length + 10.0
            ))},
            "stand clear",
        ),
    ),
)
def test_feed_nut_explode_guards_refuse_an_off_axis_or_buried_screw(overrides, message) -> None:
    _assert_feed_nut_explode_guards()
    with pytest.raises(AssertionError, match=message):
        _assert_feed_nut_explode_guards(**overrides)


def test_named_views_are_the_machine_frame() -> None:
    axes = spec.VIEW_AXES
    assert set(axes) == {spec.PLAN_VIEW, spec.ELEVATION_VIEW, spec.ISOMETRIC_VIEW}
    # Plan: +X right, +Y up the sheet. Elevation from the operator: +X right, +Z up.
    assert axes[spec.PLAN_VIEW][:2] == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert axes[spec.ELEVATION_VIEW][:2] == ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert axes[spec.ELEVATION_VIEW][2] == (0.0, -1.0, 0.0)
    # Isometric: +Z straight up the sheet, seen from the operator's front-right.
    right, up, sight = axes[spec.ISOMETRIC_VIEW]
    assert right[2] == 0.0 and up[2] == pytest.approx(math.sqrt(2.0 / 3.0))
    assert sight == pytest.approx(
        (1 / math.sqrt(3), -1 / math.sqrt(3), 1 / math.sqrt(3))
    )


def test_r4_holding_hardware_fits_loose() -> None:
    # Nothing in the strap holding is pressed: the top-hat washer's bore
    # clears its #8-32 screw and the stock stop pins slip in the riser.
    assert spec.hub_washer.BORE_LIMITS[0] > fasteners.HUB_CLAMP.major_mm
    assert riser.STOP_HOLE_DIA > riser.STOP_PIN_DIA_LIMITS[1]
    assert (spec.stop_pin.DIA, spec.stop_pin.LENGTH) == (riser.STOP_PIN_DIA, riser.STOP_PIN_LENGTH)


def test_plan_tags_name_the_pass_holes_rails_and_origin() -> None:
    tags = {tag.text.split("\n")[0]: tag for tag in spec.PLAN_TAGS}
    assert set(tags) == {
        "A1",
        "B1",
        "A2",
        "B2",
        "RAIL 1 (-X)",
        "RAIL 2 (+X)",
        "SPINDLE ORIGIN: X 0, Y 0",
    }
    # A1/B1 point at the pivot pins' axes; A2/B2 at the outer pair.
    for name, origin in zip(("A1", "B1"), spec.PIVOT_SCREW_ORIGINS):
        assert tags[name].tip[:2] == pytest.approx(origin[:2])
    for name in ("A2", "B2"):
        assert tags[name].tip[:2] == pytest.approx(
            spec.POSE.to_machine(trammel.PIN_HOLES[name])
        )
    # Rail 1 on -X, rail 2 on +X, each on its rail's axis.
    assert tags["RAIL 1 (-X)"].tip[0] < 0.0 < tags["RAIL 2 (+X)"].tip[0]
    for rail in (1, 2):
        tip = tags[f"RAIL {rail} ({'-+'[rail - 1]}X)"].tip
        assert tip[:2] == pytest.approx(trammel.rail_point(rail, spec.RAIL_TAG_S))
    assert tags["SPINDLE ORIGIN: X 0, Y 0"].tip[:2] == (0.0, 0.0)


def _builder_parts() -> tuple[tuple[str, str], ...]:
    """Literal (physical producer, logical family) rows, never derived filenames."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and [
            getattr(target, "id", None) for target in node.targets
        ] == ["_PARTS"]:
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("the jig builder has no literal _PARTS")


def test_builder_places_exactly_the_inventory() -> None:
    manifest = _builder_parts()
    assert tuple(family for _physical, family in manifest) == spec.BOM_ORDER
    assert tuple(physical for physical, _family in manifest) == tuple(
        spec.COMPONENT_IDENTITIES[family][0] for family in spec.BOM_ORDER
    )
    assert sorted(spec.BOM_ORDER) == sorted(spec.QUANTITIES) == sorted(spec.PLACEMENTS)
    assert {stem: len(spec.PLACEMENTS[stem]) for stem in spec.BOM_ORDER} == (
        spec.QUANTITIES
    )
    assert spec.QUANTITIES == {
        spec.BASE_BAR_1: 1,
        spec.BASE_BAR_2: 1,
        spec.CARRIER: 1,
        spec.PIVOT_BLOCK: 1,
        spec.FEED_BLOCK: 1,
        **PIVOT_FAMILIES,
        spec.RISER: 1,
        spec.HUB_WASHER: 1,
        spec.FEED_LEVER: 1,
        spec.END_BRACKET: 2,
        spec.RAIL: 2,
        spec.CARRIAGE: 2,
        spec.STOP_PIN: 2,
        spec.LEADSCREW: 1,
        spec.FEED_NUT: 1,
        spec.PILLOW_BLOCK: 2,
        spec.HANDWHEEL: 1,
        spec.HOLD_DOWN_STUD: 4,
        spec.T_NUT: 4,
        spec.FLANGE_NUT: 4,
        spec.RAIL_SCREW: 19,
        spec.CARRIAGE_SCREW: 8,
        spec.PILLOW_BLOCK_SCREW: 8,
        spec.RISER_SCREW: 8,
        spec.LEVER_SCREW: 2,
        spec.LEVER_LOCK_WASHER: 2,
    }
    assert sum(spec.QUANTITIES.values()) == 94
    assert spec.QUANTITIES[spec.END_BRACKET] == (leadscrew.END_BRACKET_QUANTITY)
    assert sum(spec.QUANTITIES[family] for family in spec.BASE_BARS) == base_bar.QUANTITY
    assert spec.QUANTITIES[spec.RAIL_SCREW] == fasteners.COMMON_SCREW_COUNT
    assert spec.QUANTITIES[spec.HOLD_DOWN_STUD] == fasteners.HOLD_DOWN_STUD_COUNT
    for stem, rows in SCREW_ROWS.items():
        assert spec.QUANTITIES[stem] == sum(row.count for row in rows), stem
    # TL-20's two members (PR2) and the heterogeneous kit members are explicit.
    assert spec.FABRICATED_MEMBER_IDENTITIES == {
        spec.BASE_BAR_1: (spec.BASE_BAR, "Bar1"),
        spec.BASE_BAR_2: (spec.BASE_BAR, "Bar2"),
    }
    assert spec.MEMBER_IDENTITIES == {**spec.FABRICATED_MEMBER_IDENTITIES, **spec.KIT_IDENTITIES}
    for family, identity in spec.FABRICATED_MEMBER_IDENTITIES.items():
        assert spec.COMPONENT_IDENTITIES[family] == identity
    assert spec.BASE_BAR not in spec.COMPONENT_IDENTITIES
    assert spec.KIT_IDENTITIES == {
        spec.RAIL: ("ch-rocker-arm-tl-vn-oblique-rail-kit", "Rail"),
        spec.CARRIAGE: ("ch-rocker-arm-tl-vn-oblique-rail-kit", "Carriage"),
        spec.LEADSCREW: ("ch-rocker-arm-tl-vn-oblique-leadscrew-kit", "LeadScrew"),
        spec.FEED_NUT: ("ch-rocker-arm-tl-vn-oblique-leadscrew-kit", "FeedNut"),
        spec.HOLD_DOWN_STUD: ("sh-vn-clamping-kit-hardware", "HoldDownStud"),
        spec.T_NUT: ("sh-vn-clamping-kit-hardware", "TNut"),
        spec.FLANGE_NUT: ("sh-vn-clamping-kit-hardware", "FlangeNut"),
    }
    assert set(bg.references_of(JIG)) == PART_STEMS
    # 28 logical rows from 23 native parts: the base bar's two members,
    # two kits of two members, one of three.
    assert len(manifest) == len(spec.BOM_ORDER) == 28
    assert len(PART_STEMS) == 23
    # Option B (2026-11-04): the bought nut takes the retired TL-27's row,
    # now as the TL-VN-84 FeedNut member.
    assert spec.KIT_IDENTITIES[spec.FEED_NUT] == (feed_nut.PART_NAME, feed_nut.CONFIGURATION)
    assert spec.ITEM_NUMBERS[spec.FEED_NUT] == "17"
    # R4: the loose stop pins reuse the MHA-SM-VN-53 native, no new identity.
    assert spec.COMPONENT_IDENTITIES[spec.STOP_PIN] == ("sm-vn-knife-mount-dowel", None)


@pytest.mark.parametrize("source_kind", ("all", "batch-only", "single-only"))
def test_actual_builder_sources_resolve_every_physical_producer(source_kind) -> None:
    """Exercise the real source analyzer, including each insertion path alone."""
    source = BUILDER.read_text(encoding="utf-8")
    expected = frozenset(physical for physical, _family in _builder_parts())
    if source_kind != "all":
        excluded = (
            "place_component" if source_kind == "batch-only"
            else "place_components_batch"
        )
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == excluded
            ):
                node.func.id = "_excluded_source_sink"
        source = ast.unparse(tree)
    assert bg._AssemblySources(source).collect() == expected
    assert len(expected) == 23


def test_member_selectors_are_role_local_not_native_instance_indices() -> None:
    assert spec.instance_name(spec.END_BRACKET, 0) == spec.END_BRACKET + "-1"
    assert spec.instance_name(spec.BASE_BAR_1, 0) == "@Bar1:1"
    assert spec.instance_name(spec.BASE_BAR_2, 0) == "@Bar2:1"
    assert spec.MEMBER_COMPONENT_REFERENCES == {
        f"@{configuration}:{index}": (physical, configuration)
        for family, (physical, configuration) in spec.MEMBER_IDENTITIES.items()
        for index in range(1, spec.QUANTITIES[family] + 1)
    }
    for family, (physical, configuration) in spec.MEMBER_IDENTITIES.items():
        assert spec.component_family(physical, configuration) == family
    # The base bar's unconfigured file name never counts as a member.
    with pytest.raises(ValueError, match="no unique family"):
        spec.component_family(spec.BASE_BAR, "Default")
    with pytest.raises(ValueError, match="no unique family"):
        spec.component_family(spec.CLAMPING_KIT, "Default")


def test_kit_member_quantities_are_the_registry_configuration_quantities() -> None:
    """Each kit's installed members, per configuration, are what the jig places;
    the default configuration is a member and the kit quantity is their sum."""
    kits: dict[str, dict[str, int]] = {}
    for family, (physical, configuration) in spec.KIT_IDENTITIES.items():
        kits.setdefault(physical, {})[configuration] = spec.QUANTITIES[family]
    assert kits == {
        "ch-rocker-arm-tl-vn-oblique-rail-kit": {"Rail": 2, "Carriage": 2},
        "ch-rocker-arm-tl-vn-oblique-leadscrew-kit": {"LeadScrew": 1, "FeedNut": 1},
        "sh-vn-clamping-kit-hardware": {"HoldDownStud": 4, "TNut": 4, "FlangeNut": 4},
    }
    for physical, members in kits.items():
        row = _config.parts(physical)
        assert {name: int(count) for name, count in row["configuration_quantities"].items()} == members
        assert int(row["quantity"]) == sum(members.values())
        assert row["default_configuration"] in members
    assert _config.parts(spec.RAIL_KIT)["default_configuration"] == "Rail"
    assert _config.parts(spec.LEADSCREW_KIT)["default_configuration"] == "LeadScrew"
    # Both rails and the two selected carriages, one per rail.
    assert spec.QUANTITIES[spec.RAIL] == spec.QUANTITIES[spec.CARRIAGE] == len(spec.RAILS)


@pytest.fixture
def kit_placement_scene(monkeypatch):
    import build_ch_rocker_arm_tl_oblique_jig_assembly as builder
    import _component_references as references

    components, batches, singles = [], [], []
    model = types.SimpleNamespace(GetComponents=lambda _top_only: tuple(reversed(components)))
    adapter = types.SimpleNamespace(currentModel=model)

    def insert(part, configuration, component_reference, name):
        components.append(types.SimpleNamespace(
            Name2=name,
            ComponentReference=component_reference,
            ReferencedConfiguration=configuration,
            GetPathName=lambda part=part: f"C:/native/{part}.SLDPRT",
        ))
        return name

    async def batch(_adapter, rows, *, label):
        assert _adapter is adapter
        batches.append((label, rows))
        return [
            insert(row["part"], row["configuration"], row["component_reference"],
                   f"{row['part']}-{suffix + 200 * len(batches)}")
            for suffix, row in zip((41, 7, 103, 28), rows, strict=True)
        ]

    async def individual(_adapter, part, origin, _euler, rows, *, ground,
                         configuration, component_reference, label):
        assert _adapter is adapter
        singles.append((label, {
            "part": part, "position": origin, "rows": rows, "ground": ground,
            "configuration": configuration, "component_reference": component_reference,
        }))
        # Native suffixes run across the shared file, not by member ordinal.
        return insert(part, configuration, component_reference, f"{part}-{900 - len(singles)}")

    monkeypatch.setattr(builder, "place_components_batch", batch)
    monkeypatch.setattr(builder, "place_component", individual)
    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    return builder, adapter, components, (batches, singles)


def _place_members(scene):
    """Place every configured member family: TL-20's two bars and the kits."""
    import asyncio

    builder, adapter, _components, _inserts = scene
    names = {}
    for family, (physical, _configuration) in spec.MEMBER_IDENTITIES.items():
        names.update(asyncio.run(builder._place_family(adapter, physical, family)))
    return names


def test_builder_places_each_member_with_explicit_native_identity(kit_placement_scene):
    builder, adapter, _components, (batches, singles) = kit_placement_scene
    names = _place_members(kit_placement_scene)
    assert len(names) == sum(spec.QUANTITIES[family] for family in spec.MEMBER_IDENTITIES) == 20
    # The clamping kit's members come four at a time and go in one batch each;
    # the base bars and the rail and leadscrew kits' members (1 or 2) go in
    # one at a time.
    assert [family for family, _rows in batches] == [
        spec.HOLD_DOWN_STUD, spec.T_NUT, spec.FLANGE_NUT,
    ]
    assert [label for label, _row in singles] == [
        spec.instance_name(family, index)
        for family in (
            spec.BASE_BAR_1, spec.BASE_BAR_2,
            spec.RAIL, spec.CARRIAGE, spec.LEADSCREW, spec.FEED_NUT,
        )
        for index in range(spec.QUANTITIES[family])
    ]
    assert singles[0][1]["configuration"] == "Bar1"
    assert singles[1][1]["configuration"] == "Bar2"
    inserted = [(family, rows) for family, rows in batches] + [
        (spec.component_family(row["part"], row["configuration"]), [row])
        for _label, row in singles
    ]
    for family, rows in inserted:
        physical, configuration = spec.MEMBER_IDENTITIES[family]
        for row in rows:
            index = int(row["component_reference"].rsplit(":", 1)[1]) - 1
            origin, rotation = spec.PLACEMENTS[family][index]
            assert row == {
                "part": physical,
                "position": list(origin),
                "rows": [list(axis) for axis in rotation],
                "ground": family not in spec.MOVING,
                "configuration": configuration,
                "component_reference": f"{configuration}:{index + 1}",
            }
    # The carriages and the feed nut ride the feed; rails and leadscrew stay put.
    assert {family for family in spec.KIT_IDENTITIES if family in spec.MOVING} == {
        spec.CARRIAGE, spec.FEED_NUT,
    }
    for offset, (family, _rows) in enumerate(batches, start=1):
        physical, configuration = spec.KIT_IDENTITIES[family]
        assert names[f"@{configuration}:1"] == f"{physical}-{41 + 200 * offset}"
        assert names[f"@{configuration}:4"] == f"{physical}-{28 + 200 * offset}"
    builder._verify_member_references(adapter, names)


@pytest.mark.parametrize("fault", ("missing", "wrong-member", "duplicate-reference", "renamed"))
def test_final_member_reference_readback_refuses_drift(kit_placement_scene, fault):
    builder, adapter, components, _batches = kit_placement_scene
    names = _place_members(kit_placement_scene)
    if fault == "missing":
        components.pop()
    elif fault == "wrong-member":
        components[-1].ReferencedConfiguration = "HoldDownStud"
    elif fault == "duplicate-reference":
        components[-1].ComponentReference = components[-2].ComponentReference
    else:
        components[-1].Name2 = "unexpected-new-name-901"
    with pytest.raises(RuntimeError):
        builder._verify_member_references(adapter, names)


def test_save_rechecks_member_references_after_its_final_solve():
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    [save] = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "save_assembly_and_images"
    ]
    [gate] = [keyword.value for keyword in save.keywords if keyword.arg == "solved_gates"]
    assert isinstance(gate, ast.Lambda)
    assert isinstance(gate.body, ast.Call)
    assert isinstance(gate.body.func, ast.Name)
    assert gate.body.func.id == "_verify_member_references"




@pytest.mark.parametrize("pass_name", ("inner", "outer"))
def test_both_pass_pairs_keep_both_complete_capture_stacks(pass_name: str) -> None:
    mates = spec.PIN_MATES[pass_name]
    assert len(mates) == 2
    assert {pin for _label, _hole, pin in mates} == {0, 1}
    assert {hole for _label, hole, _pin in mates} == (
        {"A1", "B1"} if pass_name == "inner" else {"A2", "B2"}
    )
    assert set(PIVOT_FAMILIES) <= set(spec.MOVING)
    sweep = trammel.SWEEP[pass_name]
    for theta in (-sweep, 0.0, sweep):
        pose = trammel.carrier_pose(pass_name, theta)
        stations = spec.carriage_stations(pass_name, theta)
        for rail, hole in zip(spec.RAILS, trammel.pin_pair(pass_name), strict=True):
            assert pose.to_machine(hole) == pytest.approx(
                trammel.rail_point(rail, stations[rail] + pivot_block.BORE_X)
            )


def test_one_free_dof_slides_the_carriages_and_what_rides_them() -> None:
    path = _config.CONFIG_DIR / "assemblies" / f"{spec.ASM_NAME}.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert contract["number"] == spec.DRAWING_NUMBER
    assert contract["free_dof"] == 1
    # The free-DOF gate reads native file stems: a moving kit member (Carriage,
    # FeedNut) lists its kit's physical stem, once.
    assert contract["allowed_free_stems"] == list(spec.MOVING_STEMS)
    assert contract["required_free_stems"] == list(spec.MOVING_STEMS)
    assert list(spec.MOVING_STEMS) == list(dict.fromkeys(
        spec.COMPONENT_IDENTITIES[stem][0] for stem in spec.MOVING
    ))
    assert {spec.RAIL_KIT, spec.LEADSCREW_KIT} <= set(spec.MOVING_STEMS)
    assert contract["flip_invert"] == []
    assert spec.SLIDE_KEY == "carriage_slide"
    assert set(spec.MOVING) == {spec.CARRIAGE, spec.CARRIER, *spec.LOCKED_TO}
    assert set(spec.MOVING) == {
        spec.CARRIER,
        spec.PIVOT_BLOCK,
        *PIVOT_FAMILIES,
        spec.RISER,
        spec.HUB_WASHER,
        spec.FEED_LEVER,
        spec.FEED_BLOCK,
        spec.CARRIAGE,
        spec.STOP_PIN,
        spec.FEED_NUT,
        spec.RAIL_SCREW,
        spec.CARRIAGE_SCREW,
        spec.RISER_SCREW,
        spec.LEVER_SCREW,
        spec.LEVER_LOCK_WASHER,
    }
    # Motion is per occurrence: the common screw's rail occurrences stay
    # fixed while its CL, CR and HUB strap clamps ride.
    moving_rail_screws = {
        spec.instance_name(spec.RAIL_SCREW, index)
        for index in range(spec.QUANTITIES[spec.RAIL_SCREW])
        if spec.is_moving(spec.RAIL_SCREW, index)
    }
    assert moving_rail_screws == set(spec.STRAP_CLAMP_SCREW_INSTANCES.values())
    assert spec.STRAP_CLAMP_SCREW_INDICES == {"CL": 16, "CR": 17, "HUB": 18}
    assert spec.STRAP_CLAMP_SCREW_INSTANCES == {
        role: f"{spec.RAIL_SCREW}-{index + 1}"
        for role, index in spec.STRAP_CLAMP_SCREW_INDICES.items()
    }
    assert not moving_rail_screws & set(spec.RAIL_SCREW_INSTANCES + spec.BAR_SCREW_INSTANCES)
    assert set(spec.MOVING_INSTANCES) == {
        spec.instance_name(stem, index)
        for stem in spec.BOM_ORDER
        for index in range(spec.QUANTITIES[stem])
        if spec.is_moving(stem, index)
    }
    # Nothing that moves stays put in the explode, and nothing fixed rides.
    assert not set(spec.MOVING) & set(spec.EXPLODE_STATIC)
    # The carrier carries its riders; everything else rides a carriage, the
    # chain locked parent first. Each rider locks to the nearest instance of
    # what carries it.
    locked = list(spec.LOCKED_TO)
    riders = {
        stem
        for stem, parents in spec.LOCKED_TO.items()
        if all(parent is None or parent[0] == spec.CARRIER for parent in parents)
    }
    assert riders == {
        spec.RISER,
        spec.HUB_WASHER,
        spec.FEED_LEVER,
        spec.STOP_PIN,
        spec.RAIL_SCREW,
        spec.LEVER_SCREW,
        spec.LEVER_LOCK_WASHER,
    }
    assert set(spec.CARRIER_RIDERS) == {
        spec.instance_name(stem, index)
        for stem, parents in spec.LOCKED_TO.items()
        for index, parent in enumerate(parents)
        if parent is not None and parent[0] == spec.CARRIER
    }
    assert spec.LOCKED_TO[spec.RAIL_SCREW] == (
        *(None,) * fasteners.RAIL_TO_BAR.count,
        *((spec.CARRIER, 0),) * len(spec.STRAP_CLAMP_ROLES),
    )
    # The riser screw family's first four hold the riser on the carrier, its
    # last four the feed nut on the feed block's lug.
    assert spec.LOCKED_TO[spec.RISER_SCREW] == (
        *((spec.CARRIER, 0),) * fasteners.RISER_TO_CARRIER.count,
        *((spec.FEED_BLOCK, 0),) * fasteners.NUT_TO_FEED_BLOCK.count,
    )
    assert spec.NUT_SCREW_INSTANCES == tuple(
        spec.instance_name(spec.RISER_SCREW, index)
        for index in range(fasteners.RISER_TO_CARRIER.count, spec.QUANTITIES[spec.RISER_SCREW])
    )
    for stem, parents in spec.LOCKED_TO.items():
        assert len(parents) == spec.QUANTITIES[stem]
        for index, entry in enumerate(parents):
            if entry is None:
                with pytest.raises(ValueError, match="is fixed"):
                    spec.lock_parent(stem, index)
                continue
            parent, parent_index = entry
            assert parent in {spec.CARRIAGE, spec.CARRIER} or locked.index(parent) < locked.index(stem)
            assert spec.lock_parent(stem, index) == spec.instance_name(parent, parent_index)
    # The carrier rides the inner pass's pins in the saved model: A1 on pin 1,
    # B1 on pin 2; verify re-mates A2/B2 for the outer pass.
    assert {
        pass_name: [(hole, pin) for _label, hole, pin in mates]
        for pass_name, mates in spec.PIN_MATES.items()
    } == {"inner": [("A1", 0), ("B1", 1)], "outer": [("A2", 0), ("B2", 1)]}


def _thread(row: fasteners.Fastener, tap_drill: float) -> tuple[float, float, float]:
    return (row.major_mm, tap_drill, row.engagement_mm)


def test_interference_contracts_are_physical_seats_and_threads() -> None:
    for envelope, expected in (
        (
            contracts.JIG_RAIL_SCREW_THREAD,
            _thread(fasteners.RAIL_TO_BAR, base_bar.TAP_DRILL),
        ),
        (
            contracts.JIG_BAR_SCREW_THREAD,
            _thread(fasteners.BRACKET_TO_BAR, end_bracket.TAP_DRILL),
        ),
        (
            contracts.JIG_CARRIAGE_SCREW_THREAD,
            _thread(fasteners.BLOCK_TO_CARRIAGE, carriage.BORE_DIA),
        ),
        (
            contracts.JIG_PILLOW_BLOCK_SCREW_THREAD,
            _thread(fasteners.KP08_TO_BRACKET, end_bracket.TAP_DRILL),
        ),
        (
            contracts.JIG_NUT_SCREW_THREAD,
            _thread(fasteners.NUT_TO_FEED_BLOCK, feed_block.NUT_TAP_DRILL),
        ),
        (
            contracts.JIG_RISER_SCREW_THREAD,
            _thread(fasteners.RISER_TO_CARRIER, carrier.RISER_TAP_DRILL),
        ),
        (
            contracts.JIG_END_CLAMP_THREAD,
            _thread(fasteners.END_CLAMP, carrier.CLAMP_TAP_DRILL),
        ),
        (
            contracts.JIG_HUB_CLAMP_THREAD,
            _thread(fasteners.HUB_CLAMP, carrier.CLAMP_TAP_DRILL),
        ),
        (
            contracts.JIG_LEVER_SCREW_THREAD,
            _thread(fasteners.LEVER_TO_CARRIER, carrier.LEVER_TAP_DRILL),
        ),
        (
            contracts.JIG_PIVOT_SCREW_THREAD,
            # The modeled thread envelope overlaps the tap drill over its whole
            # cut length, not just the full-form engagement.
            (pivot_screw.THREAD_DIA, pivot_block.PIVOT_TAP_DRILL, pivot_screw.THREAD_LENGTH),
        ),
        (
            contracts.JIG_T_NUT_THREAD,
            (spec.STUD_DIA, t_nut.TAP_DRILL_DIA, t_nut.FOOT_HEIGHT + t_nut.NECK_HEIGHT),
        ),
        (
            contracts.JIG_FLANGE_NUT_THREAD,
            (spec.STUD_DIA, flange_nut.TAP_DRILL_DIA, flange_nut.HEIGHT),
        ),
        (
            contracts.JIG_FEED_NUT_THREAD,
            (leadscrew_stock.MAJOR_DIA, feed_nut.BORE_DIA, feed_nut.LENGTH),
        ),
    ):
        # The literals carry the thread majors to 4 places, the specs to 3.
        assert envelope == pytest.approx(expected, abs=1e-3)
    pairs = contracts.ALLOWED_PAIRS
    names = {
        spec.instance_name(stem, index)
        for stem, count in spec.QUANTITIES.items()
        for index in range(count)
    }
    assert all(pair <= names for pair in pairs)
    assert len(pairs) == sum(spec.QUANTITIES[s] for s in SCREW_ROWS) + 8 + 1 + 2
    # R4 holding presses nothing: the loose stop pins and the top-hat washer
    # name no pair; only the strap clamps' threads meet the carrier.
    for loose in (spec.STOP_PIN, spec.HUB_WASHER):
        assert not any(
            spec.instance_name(loose, index) in pair
            for pair in pairs
            for index in range(spec.QUANTITIES[loose])
        )
    for role, name in spec.STRAP_CLAMP_SCREW_INSTANCES.items():
        envelope = contracts.JIG_HUB_CLAMP_THREAD if role == "HUB" else contracts.JIG_END_CLAMP_THREAD
        assert pairs[frozenset((name, f"{spec.CARRIER}-1"))] == pytest.approx(
            contracts.smooth_annulus_limit_mm3(*envelope)
        )
    # The nut screws pass the flange's Ø3.5 holes: only the lug's taps and
    # the leadscrew's thread name the nut's neighbours.
    assert feed_nut.HOLE_DIA_MIN > fasteners.NUT_TO_FEED_BLOCK.major_mm
    nut = spec.instance_name(spec.FEED_NUT, 0)
    assert nut == "@FeedNut:1"
    assert [pair for pair in pairs if nut in pair] == [
        frozenset((nut, spec.instance_name(spec.LEADSCREW, 0)))
    ]
    inserted = (*SCREW_ROWS, spec.HOLD_DOWN_STUD, spec.FEED_NUT, spec.PIVOT_SCREW)
    occurrences = {
        spec.instance_name(family, index): (family, index)
        for family, count in spec.QUANTITIES.items()
        for index in range(count)
    }
    for pair in pairs:
        (insert,) = [name for name in pair if occurrences[name][0] in inserted]
        (receiver,) = pair - {insert}
        stem, index = occurrences[insert]
        receiving, _receiver_index = occurrences[receiver]
        # Each pair names the receiving instance the insert actually sits in.
        origin = spec.PLACEMENTS[stem][index][0]
        reach = [math.dist(origin, placed) for placed, _r in spec.PLACEMENTS[receiving]]
        assert receiver == spec.instance_name(receiving, reach.index(min(reach)))
    counts: dict[str, int] = {}
    for pair in pairs:
        for name in pair:
            counts[name] = counts.get(name, 0) + 1
    for stem in SCREW_ROWS:
        for index in range(spec.QUANTITIES[stem]):
            assert counts[spec.instance_name(stem, index)] == 1
    for stem in (spec.HOLD_DOWN_STUD,):
        for index in range(spec.QUANTITIES[stem]):
            assert counts[spec.instance_name(stem, index)] == 2


def test_bom_rows_name_every_made_and_bought_item() -> None:
    assert set(spec.BOM_DESCRIPTIONS) == set(spec.QUANTITIES)
    assert spec.ITEM_NUMBERS == {
        stem: str(index) for index, stem in enumerate(spec.BOM_ORDER, 1)
    }


def test_kit_bom_descriptions_use_native_member_authority() -> None:
    members = {
        spec.RAIL: guide_rail,
        spec.CARRIAGE: carriage,
        spec.LEADSCREW: leadscrew_stock,
        spec.FEED_NUT: feed_nut,
        spec.HOLD_DOWN_STUD: hold_down_stud,
        spec.T_NUT: t_nut,
        spec.FLANGE_NUT: flange_nut,
    }
    assert set(members) == set(spec.KIT_IDENTITIES)
    for family, member in members.items():
        if family == spec.RAIL:
            continue
        assert spec.BOM_DESCRIPTIONS[family] == member.BOM_DESCRIPTION
    # The one exception (TL-00 review 62753c5e, Main 2026-11-07): the jig
    # prints the rail's native fitted length as a whole-mm reference, each
    # rail trimmed to its bar in step 1. The member keeps its own row.
    assert guide_rail.BOM_DESCRIPTION == f"{guide_rail.STYLE} RAIL, {guide_rail.LENGTH:.3f} MM, KIT, TRIMMED"
    assert spec.BOM_DESCRIPTIONS[spec.RAIL] == (
        f"{guide_rail.STYLE} RAIL, {round(guide_rail.LENGTH)} MM REF, TRIM TO BAR"
    )
    # The Amazon kits' members also carry their configuration names.
    for family in (spec.RAIL, spec.CARRIAGE, spec.LEADSCREW, spec.FEED_NUT):
        assert spec.KIT_IDENTITIES[family][1] == members[family].CONFIGURATION


def test_bom_follows_the_part_registry() -> None:
    assert SHARED_VENDOR_FAMILIES == {spec.STOP_PIN}
    rows = {
        family: _config.parts(physical)
        for family, (physical, _configuration) in spec.COMPONENT_IDENTITIES.items()
    }
    numbers = [rows[stem]["number"] for stem in spec.BOM_ORDER]
    for stem, number in zip(spec.BOM_ORDER, numbers, strict=True):
        row = rows[stem]
        _physical, configuration = spec.COMPONENT_IDENTITIES[stem]
        quantity = (
            row["configuration_quantities"][configuration]
            if configuration is not None else row["quantity"]
        )
        if stem in SHARED_VENDOR_FAMILIES:
            # The machine's registry row is untouched: its own number and
            # quantity (the knife mounts' four); the jig consumes the riser's
            # two stop holes' worth, bought as the same stock pin.
            assert configuration is None and row["process"] == "purchased", stem
            assert number == "MHA-SM-VN-53" and quantity == spec.stop_pin.QUANTITY == 4
            assert spec.QUANTITIES[stem] == len(riser.STOP_PIN_HOLES) == 2
            continue
        assert quantity == spec.QUANTITIES[stem], stem
        # VN records procurement, not absence of shop rework. Shared kit
        # registry properties stay common; HoldDownStud's native rework
        # properties are checked with its configured producer.
        assert (row["process"] == "purchased") == number.startswith(
            (JIG_PREFIX + "VN-", "MHA-SH-VN-")
        ), stem


def test_source_bom_and_drawing_clusters_partition_every_capture_family_once() -> None:
    clustered = [family for cluster in drawing.CLUSTERS for family in cluster.stems]
    assert sorted(clustered) == sorted(spec.BOM_ORDER)
    assert tuple(drawing.BOM_COMPONENTS) == spec.BOM_ORDER
    assert drawing.BOM_QUANTITIES == spec.QUANTITIES
    assert drawing.BOM_ITEM_NUMBERS == spec.ITEM_NUMBERS
    parts = _builder_parts()
    for family in spec.BOM_ORDER:
        assert spec.BOM_ORDER.count(family) == 1
        assert parts.count(
            (spec.COMPONENT_IDENTITIES[family][0], family)
        ) == 1
        assert clustered.count(family) == 1


def test_jig_is_a_shop_fixture_outside_the_machine_tree() -> None:
    assert bg.is_shop_fixture(JIG)
    shared_kit = _config.parts(spec.CLAMPING_KIT)
    assert shared_kit["usage_scope"] == "tooling"
    assert bg.is_shop_fixture(spec.CLAMPING_KIT.replace("-", "_"))
    assert JIG in bg.ASSEMBLY_ORDER and JIG not in bg.MACHINE_ASSEMBLIES
    assert bg.ASSEMBLY_ORDER[-1] == "ha_harmonic_analyzer"
    reachable, frontier = set(), ["ha_harmonic_analyzer"]
    while frontier:
        for ref in bg.references_of(frontier.pop()):
            if ref not in reachable:
                reachable.add(ref)
                if ref in bg.ASSEMBLY_ORDER:
                    frontier.append(ref)
    # Only the jig's own parts and the tooling kit stay out of the machine; a
    # shared vendor input is the machine's part, reused with no new identity.
    assert not ({JIG} | JIG_ONLY_PART_STEMS) & reachable
    assert PART_STEMS - JIG_ONLY_PART_STEMS <= reachable



def test_sweep_clears_the_column_cover(report) -> None:
    # The rail-bound items, computed independently here; every moving and
    # feed outline keeps the 100 mm floor to the cover below.
    expected = {}
    near = min(low for low, _high in trammel.END_STOPS.values())
    for rail in spec.RAILS:
        corners = [
            trammel.rail_point(rail, near + x, lateral)
            for x in (-carriage.LENGTH / 2.0 - carriage.PLUG_PROUD,
                      carriage.LENGTH / 2.0 + carriage.NIPPLE_PROUD)
            for lateral in (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0)
        ]
        expected[f"carriage {rail}"] = spec.COVER_Y - max(y for _x, y in corners)
    for which, station in zip(("near", "far"), leadscrew.KP08_S, strict=True):
        corners = [
            trammel.rail_point(leadscrew.RAIL, station + along, lateral)
            for along in (-end_bracket.BRACKET_WIDTH / 2.0, end_bracket.BRACKET_WIDTH / 2.0)
            for lateral in (leadscrew.BRACKET_INNER_LATERAL,
                            leadscrew.BRACKET_INNER_LATERAL + end_bracket.BRACKET_LENGTH)
        ]
        expected[f"end bracket {which}"] = spec.COVER_Y - max(y for _x, y in corners)
    assert {name: report.cover_clearance[name] for name in expected} == pytest.approx(expected, abs=0.01)
    assert min(report.cover_clearance.values()) > 100.0
    for pass_name in ("inner", "outer"):
        for theta in spec.sweep_thetas(pass_name, samples=21):
            outlines = spec.moving_outlines(pass_name, theta)
            assert all(spec.COVER_Y - y > 100.0 for polygon in outlines.values() for _x, y in polygon)
            assert {"feed block", "pivot block 2"} <= set(outlines)


def test_sweep_extents_and_rail_margins(report) -> None:
    far = max(high for _low, high in trammel.END_STOPS.values())
    carriage_corners = [
        trammel.rail_point(rail, far + along, lateral)
        for rail in spec.RAILS
        for along in (-carriage.LENGTH / 2.0 - carriage.PLUG_PROUD,
                      carriage.LENGTH / 2.0 + carriage.NIPPLE_PROUD)
        for lateral in (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0)
    ]
    # The reversed nut now reaches farther on rail 1 than its carriage.
    nut_pose = spec._swept_placement(spec.FEED_NUT, 0, "outer", trammel.SWEEP["outer"])
    radius = feed_nut.FLANGE_DIA_MAX / 2.0
    nut_corners = [
        spec.frame_point(nut_pose, (x, y, z))[:2]
        for x in (-radius, radius) for y in (0.0, feed_nut.LENGTH_MAX)
        for z in (-radius, radius)
    ]
    outer_corners = carriage_corners + nut_corners
    assert report.moving_x == pytest.approx((
        min(x for x, _y in outer_corners), max(x for x, _y in outer_corners),
    ))
    for pass_name in ("inner", "outer"):
        for theta in spec.sweep_thetas(pass_name, samples=21):
            pose = trammel.carrier_pose(pass_name, theta)
            # Source plate corners, independently transformed from the cutter
            # calculator, must be inside the reported complete moving envelope.
            for x in carrier.OUTLINE_X:
                for y in carrier.OUTLINE_Y:
                    px, py = pose.to_machine((x, y))
                    assert report.moving_x[0] <= px <= report.moving_x[1]
                    assert report.moving_y[0] <= py <= report.moving_y[1]
    # The 2026-10-17 widening (column-side edge at lateral +88.9), narrowed to
    # 5.50 wide on 2026-10-30: the far column-side corners set X, the near
    # column-side corners the top of Y, the operator-side corners the bottom.
    # The datum-trimmed rail shares both ends with its bar.
    assert report.fixed_x == pytest.approx((-462.96, 462.96), abs=0.01)
    assert report.fixed_y == pytest.approx((-115.33, 85.84), abs=0.01)
    assert report.bar_overhang == pytest.approx({1: 43.86, 2: 43.86}, abs=0.01)
    assert report.carriage_margin["inner"] == pytest.approx((29.52, 46.738), abs=0.01)
    assert report.carriage_margin["outer"] == pytest.approx((32.18, 34.858), abs=0.01)
    assert all(
        near > 0.0 and far > 0.0 for near, far in report.carriage_margin.values()
    )




def test_sweep_sidecar_drives_both_passes_to_their_end_stops() -> None:
    sidecar = spec.sweep_sidecar()
    assert json.loads(json.dumps(sidecar)) == sidecar
    assert sidecar["assembly"] == spec.ASM_NAME
    assert sidecar["drive_key"] == spec.SLIDE_KEY
    assert sidecar["pose_tolerance_mm"] == spec.SWEEP_POSE_TOLERANCE == 0.05
    passes = {entry["pass"]: entry for entry in sidecar["passes"]}
    assert list(passes) == ["inner", "outer"]
    # Out from the symmetric pose to -SWEEP, back through it to +SWEEP; the
    # gate checks each pose once (the return legs only re-walk the solver).
    assert [pose["check"] for pose in passes["inner"]["poses"]] == [
        True,
        True,
        True,
        False,
        False,
        True,
        True,
    ]
    drives = {
        "inner": (212.404, 136.485, 60.215, 136.485, 212.404, 287.798, 362.492),
        "outer": (219.703, 141.471, 62.878, 141.471, 219.703, 297.395, 374.366),
    }
    carriage_1, carriage_2 = (spec.instance_name(spec.CARRIAGE, i) for i in (0, 1))
    for pass_name, entry in passes.items():
        poses = entry["poses"]
        assert [pose["drive_mm"] for pose in poses] == pytest.approx(
            drives[pass_name], abs=1e-3
        )
        assert [pose["check"] for pose in poses] == [
            pose["check"] for pose in passes["inner"]["poses"]
        ]
        sweep = trammel.SWEEP[pass_name]
        assert [pose["theta_rad"] for pose in poses] == pytest.approx(
            [spec.SWEEP_FRACTIONS[i] * sweep for i in spec.SWEEP_VISIT]
        )
        for pose in poses:
            stations = spec.carriage_stations(pass_name, pose["theta_rad"])
            assert pose["drive_mm"] == pytest.approx(
                stations[spec.SLIDE_RAIL] - trammel.RAIL_NEAR_S
            )
            assert pose["origins"][carriage_1] == pytest.approx(list(spec.carriage_origin(1, stations[1])))
            assert pose["origins"][carriage_2] == pytest.approx(list(spec.carriage_origin(2, stations[2])))
            assert set(pose["origins"]) == set(spec.MOVING_INSTANCES)
            assert set(spec.RAIL_SCREW_INSTANCES + spec.BAR_SCREW_INSTANCES).isdisjoint(
                pose["origins"]
            )
            assert set(spec.STRAP_CLAMP_SCREW_INSTANCES.values()) <= set(pose["origins"])
            for family in (spec.FEED_BLOCK, spec.PIVOT_BLOCK, spec.FEED_NUT):
                assert pose["origins"][spec.instance_name(family, 0)] == pytest.approx(
                    spec._swept_placement(family, 0, pass_name, pose["theta_rad"])[0]
                )
        # The sweep's ends put the carriages on the calculator's end stops.
        low, high = trammel.END_STOPS[pass_name]
        ends = (poses[2]["origins"], poses[-1]["origins"])
        assert ends[0][carriage_1] == pytest.approx(list(spec.carriage_origin(1, low)))
        assert ends[1][carriage_1] == pytest.approx(list(spec.carriage_origin(1, high)))
    # The saved model is the inner pass at its symmetric pose.
    assert passes["inner"]["remate"] is None
    assert passes["inner"]["poses"][0]["drive_mm"] == pytest.approx(
        spec.slide_distance(spec.CARRIAGE_STATION)
    )
    # verify reads each carriage's component origin back against these.
    for index, (origin, _rows) in enumerate(spec.PLACEMENTS[spec.CARRIAGE]):
        name = spec.instance_name(spec.CARRIAGE, index)
        assert passes["inner"]["poses"][0]["origins"][name] == pytest.approx(
            list(origin)
        )
    remate = passes["outer"]["remate"]
    assert remate["suppress"] == [label for label, _h, _p in spec.PIN_MATES["inner"]]
    assert remate["coaxial"] == [
        {
            "label": "carrier A2 on pin 1",
            "hole": "PinAxisA2@ch-rocker-arm-tl-oblique-carrier-1",
            "pin": "PivotAxis@ch-rocker-arm-tl-vn-oblique-pivot-screw-1",
        },
        {
            "label": "carrier B2 on pin 2",
            "hole": "PinAxisB2@ch-rocker-arm-tl-oblique-carrier-1",
            "pin": "PivotAxis@ch-rocker-arm-tl-vn-oblique-pivot-screw-2",
        },
    ]




def test_sweep_table_edge_margins(report) -> None:
    edges = report.table_edge_margins
    # The symmetric sweep overhangs both table ends alike.
    assert edges["carrier"]["-X end"] == pytest.approx(edges["carrier"]["+X end"])
    for rail, outer, inner in ((1, "-X end", "+X end"), (2, "+X end", "-X end")):
        bar = edges[f"base bar {rail}"]
        assert bar[outer] == pytest.approx(-report.bar_overhang[rail])
        # The bar's operator-side edge stays on the table (its slots reach the
        # T-slots); its near column-side corner stands past the back edge,
        # toward the cover.
        assert bar["front"] > 0.0
        corner = trammel.rail_point(
            rail, trammel.RAIL_NEAR_S, trammel.BASE_BAR_COLUMN_EDGE
        )
        assert bar["back"] == pytest.approx(spec.TABLE_Y[1] - corner[1])
        assert bar["back"] < 0.0
        assert bar[inner] > 0.0
    # The wider bars still leave the two apart at their near ends: a
    # separating axis among the plan outlines' edge normals.
    bars = spec.fixed_outlines()
    one, two = bars["base bar 1"], bars["base bar 2"]

    def separated(polygon: list[tuple[float, float]]) -> bool:
        for p, q in zip(polygon, polygon[1:] + polygon[:1]):
            nx, ny = q[1] - p[1], p[0] - q[0]
            a = [nx * x + ny * y for x, y in one]
            b = [nx * x + ny * y for x, y in two]
            if max(a) <= min(b) or max(b) <= min(a):
                return True
        return False

    assert separated(one) or separated(two)
    # The feed overhangs like the bars, above the table top: the near KP08's
    # envelope and bracket pass the back edge, the handwheel the -X end.
    feed = {
        family: edges[family]
        for family in (
            "feed block",
            "end bracket near",
            "end bracket far",
            "KP08 near",
            "KP08 far",
            "screw",
            "handwheel",
        )
    }
    # The near KP08 and its bracket pass the back edge; the handwheel and the
    # screw's stub pass the -X end, all above the table top.
    assert feed["KP08 near"]["back"] < 0.0
    bracket_corners = [
        trammel.rail_point(leadscrew.RAIL, leadscrew.KP08_S[0] + along, lateral)
        for along in (-end_bracket.BRACKET_WIDTH / 2.0, end_bracket.BRACKET_WIDTH / 2.0)
        for lateral in (leadscrew.BRACKET_INNER_LATERAL,
                        leadscrew.BRACKET_INNER_LATERAL + end_bracket.BRACKET_LENGTH)
    ]
    assert feed["end bracket near"]["back"] == pytest.approx(
        spec.TABLE_Y[1] - max(y for _x, y in bracket_corners),
    )
    assert feed["handwheel"]["-X end"] < 0.0
    assert feed["screw"]["-X end"] < 0.0
    # The body is mirrored, but the column-side integral lug is not:
    # its +X/+lateral corner sets rail 1's outer table-edge margin. The lug
    # runs flush with the block's +X end (owner ruling 2026-11-07).
    lo, hi = trammel.CARRIAGE_TRAVEL
    outline = (
        (feed_block.BLOCK_X0, feed_block.LUG_Y1),
        (feed_block.LUG_X0, feed_block.LUG_Y1),
        (feed_block.LUG_X0, feed_block.LUG_Y0),
        (feed_block.BLOCK_X1, feed_block.LUG_Y0),
        (feed_block.BLOCK_X1, feed_block.BLOCK_WIDTH / 2.0),
        (feed_block.BLOCK_X0, feed_block.BLOCK_WIDTH / 2.0),
    )
    swept = [
        trammel.rail_point(1, station + x, -y)
        for station in (lo, hi) for x, y in outline
    ]
    assert feed["feed block"] == pytest.approx({
        "-X end": min(x for x, _y in swept) - spec.TABLE_X[0],
        "+X end": spec.TABLE_X[1] - max(x for x, _y in swept),
        "front": min(y for _x, y in swept) - spec.TABLE_Y[0],
        "back": spec.TABLE_Y[1] - max(y for _x, y in swept),
    })
    assert min(
        margin["front"] for family, margin in feed.items() if family != "feed block"
    ) > 90.0


# Fastener table: (callout, count, engagement, protrusion). Protrusion is the
# screw's length past the grip less the receiving thread's depth; below zero,
# the screw stops inside the part (THRU tap) or short of the full thread
# (blind tap). Engagement is never more than the receiving thread's depth.
FASTENER_TABLE = {
    "RAIL_TO_BAR": ("#8-32 X 3/4 SHCS", 16, 9.35, 9.35 - trammel.BASE_BAR_THICK),  # tip short of the faced bar's underside
    # A″ lower 5/8 screws enter the limited bottom full thread.
    "BRACKET_TO_BAR": (
        "#8-32 X 5/8 SHCS", 4,
        leadscrew.BAR_SCREW_ENGAGEMENT,
        leadscrew.BAR_SCREW_ENGAGEMENT - end_bracket.BAR_THREAD_LIMITS[0],
    ),
    "BLOCK_TO_CARRIAGE": (
        "M4 X 20 SHCS", 8,
        pivot_block.SCREW_REACH,
        pivot_block.SCREW_REACH - pivot_block.CARRIAGE_THREAD_DEPTH,
    ),
    # Upper 5/8 screws stop within the top full-thread guarantee.
    "KP08_TO_BRACKET": (
        "#8-32 X 5/8 SHCS", 4, 10.875, 10.875 - end_bracket.KP08_THREAD_LIMITS[0],
    ),
    # The 5/8 screw past the TL-VN-84 FeedNut flange (its head seated in the
    # countersink) into the lug's THRU tap, the tip stopping inside it.
    "NUT_TO_FEED_BLOCK": (
        "#4-40 X 5/8 B18.6.3 FLAT HEAD", 4,
        0.625 * 25.4 - feed_nut.SCREW_GRIP,
        0.625 * 25.4 - feed_nut.SCREW_GRIP - feed_block.LUG_WIDTH,
    ),
    # The 5/8 screw past the riser grip (its head seated in the countersink);
    # the tip stops inside the carrier's THRU tap.
    "RISER_TO_CARRIER": (
        "#4-40 X 5/8 B18.6.3 FLAT HEAD", 4,
        0.625 * 25.4 - fasteners.RISER_TO_CARRIER.grip_mm,
        0.625 * 25.4 - fasteners.RISER_TO_CARRIER.grip_mm - carrier.THICKNESS,
    ),
    # The common screw at CL and CR: through the strap and riser into the
    # carrier's THRU tap, the tip stopping inside it.
    "END_CLAMP": (
        "#8-32 X 3/4 SHCS", 2,
        0.75 * 25.4 - (riser.THICKNESS + trammel.STRAP_THICK),
        0.75 * 25.4 - (riser.THICKNESS + trammel.STRAP_THICK) - carrier.THICKNESS,
    ),
    # The same at HUB, its grip also the top-hat washer's flange.
    "HUB_CLAMP": (
        "#8-32 X 3/4 SHCS", 1,
        0.75 * 25.4 - (spec.hub_washer.THICK + trammel.STRAP_THICK + riser.THICKNESS),
        0.75 * 25.4 - (spec.hub_washer.THICK + trammel.STRAP_THICK + riser.THICKNESS)
        - carrier.THICKNESS,
    ),
    "LEVER_TO_CARRIER": ("5/16-18 X 1 SHCS", 2, 10.414, 10.414 - carrier.THICKNESS),
}


def test_fastener_table_engagement_and_protrusion() -> None:
    rows = {name: getattr(fasteners, name) for name in FASTENER_TABLE}
    assert tuple(rows.values()) == fasteners.FASTENERS
    for name, (callout, count, engagement, protrusion) in FASTENER_TABLE.items():
        row = rows[name]
        assert fasteners.callout(row) == callout, name
        assert row.count == count, name
        assert row.engagement_mm == pytest.approx(engagement, abs=1e-3), name
        assert row.protrusion_mm == pytest.approx(protrusion, abs=1e-3), name
    # Every tip stops inside its receiving thread (R4 retired the proud CR
    # 1/4-20 and the blind-tap left clamp).
    proud = [row for row in fasteners.FASTENERS if row.protrusion_mm > 0.0]
    assert proud == []
    # Counts follow the parts: 8 rail holes on each of 2 rails, a 4-hole
    # pattern on each carriage, 2 KP08 screws on each of 2 brackets.
    assert fasteners.RAIL_TO_BAR.count == trammel.RAIL_HOLE_COUNT * 2
    assert fasteners.BLOCK_TO_CARRIAGE.count == 4 * 2
    assert fasteners.KP08_TO_BRACKET.count == 2 * leadscrew.END_BRACKET_QUANTITY
    assert fasteners.LEVER_TO_CARRIER.count == len(carrier.LEVER_HOLES)
    # Metric only into the bought carriage's vendor-cut M4 holes; the rest UNC.
    assert {row.thread for row in fasteners.FASTENERS if row.metric} == {"M4"}
    # Under 1.5 D only where the carriage's or the carrier's thread limits it.
    short = {
        row.joint
        for row in fasteners.FASTENERS
        if row.engagement_mm < 1.5 * row.major_mm
    }
    assert short == {
        fasteners.BLOCK_TO_CARRIAGE.joint,
        fasteners.LEVER_TO_CARRIER.joint,
    }
    # Each M4 x 20 is cut to fit .189 past its own .570 counterbore floor
    # (owner ruling 2026-11-01): 1.2D nominal, short of the M4 x 5 thread end.
    assert fasteners.BLOCK_TO_CARRIAGE.cut_length_mm == pytest.approx(
        pivot_block.CBORE_FLOOR + pivot_block.SCREW_REACH
    )
    assert fasteners.BLOCK_TO_CARRIAGE.engagement_mm == pytest.approx(pivot_block.SCREW_REACH)
    assert 1.2 * 4.0 <= fasteners.BLOCK_TO_CARRIAGE.engagement_mm < pivot_block.CARRIAGE_THREAD_DEPTH
    assert [row for row in fasteners.FASTENERS if row.cut_length_mm is not None] == [
        fasteners.BLOCK_TO_CARRIAGE,
    ]
    # A 1-1/8 in lever screw would stand out of the carrier's underside.
    assert (
        fasteners.inch_mm("1-1/8") - fasteners.LEVER_TO_CARRIER.grip_mm
        > carrier.THICKNESS
    )
    # The bar screws' worst case at TL-20's bands stays inside 1.5 D .. TL-28.
    low, high = leadscrew.BAR_SCREW_ENGAGEMENT_RANGE
    assert low < leadscrew.BAR_SCREW_ENGAGEMENT < high
    assert 1.5 * fasteners.BRACKET_TO_BAR.major_mm < low < high < leadscrew.BRACKET_THICK
    assert leadscrew.KP08_FOOT_THICK == 5.0  # UNVERIFIED: verify on receipt
    assert fasteners.WASHERS == (fasteners.LEVER_LOCK_WASHER, fasteners.HUB_WASHER)
    assert fasteners.HUB_WASHER.count == fasteners.HUB_CLAMP.count == 1
    assert fasteners.HUB_WASHER.thickness_mm == spec.hub_washer.THICK
    # The nut screws' flat heads seat in the TL-VN-84 FeedNut's countersinks
    # (owner ruling 2026-11-04, option B; no washers): the grip is the flange
    # plus the head's nominal stand-proud above it.
    assert fasteners.NUT_TO_FEED_BLOCK.head == fasteners.RISER_TO_CARRIER.head
    assert fasteners.NUT_TO_FEED_BLOCK.grip_mm == pytest.approx(feed_nut.SCREW_GRIP)
    assert feed_nut.SCREW_GRIP == pytest.approx(
        feed_nut.FLANGE_THICK + feed_nut.HEAD_PROUD_NOMINAL
    )
    assert fasteners.LEVER_LOCK_WASHER.count == fasteners.LEVER_TO_CARRIER.count
    assert fasteners.LEVER_TO_CARRIER.grip_mm == pytest.approx(
        feed_lever.LEVER_THICK + fasteners.LEVER_LOCK_WASHER.thickness_mm
    )
    assert fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert fasteners.HOLD_DOWN_STUD_COUNT == 4


def test_one_common_screw_with_every_exception_reasoned() -> None:
    """PR2, R4 and A″: TL-VN-61 holds rails and CL/CR/HUB in one BOM row;
    every other screw or stud, including both TL-28 joints, is reasoned."""
    assert fasteners.COMMON_SCREW == ("#8-32", "3/4", fasteners.SHCS)
    assert fasteners.COMMON_SCREW_ROWS == (
        fasteners.RAIL_TO_BAR, fasteners.END_CLAMP, fasteners.HUB_CLAMP,
    )
    assert fasteners.COMMON_SCREW_COUNT == 16 + 2 + 1 == spec.QUANTITIES[spec.RAIL_SCREW]
    for row in fasteners.COMMON_SCREW_ROWS:
        assert (row.thread, row.length, row.head) == fasteners.COMMON_SCREW
    # No other row is the common screw.
    others = [row for row in fasteners.FASTENERS if row not in fasteners.COMMON_SCREW_ROWS]
    assert all((r.thread, r.length, r.head) != fasteners.COMMON_SCREW for r in others)
    assert set(fasteners.COMMON_SCREW_EXCEPTIONS) == {
        "M4 SHCS, carriage",
        "5/16-18 shoulder screw, pivot",
        "5/16-18 SHCS, feed lever",
        "#4-40 flat heads, riser and feed nut",
        "1/2-13 hold-down studs",
        "kit set screws, handwheel and KP08",
        "#8-32 x 5/8 SHCS, KP08 to TL-28",
        "#8-32 x 5/8 SHCS, TL-28 to bar",
    }
    assert all(reason.strip() for reason in fasteners.COMMON_SCREW_EXCEPTIONS.values())
    # The screw families on the BOM: the common one and the excepted ones.
    assert set(SCREW_ROWS) == {
        spec.RAIL_SCREW, spec.CARRIAGE_SCREW, spec.PILLOW_BLOCK_SCREW,
        spec.RISER_SCREW, spec.LEVER_SCREW,
    }
    # The strap clamps are the common screw's last three occurrences.
    assert spec.STRAP_CLAMP_SCREW_PLACEMENTS == spec.PLACEMENTS[spec.RAIL_SCREW][-3:]
    assert spec.QUANTITIES[spec.RAIL_SCREW] - 3 == len(spec.RAIL_SCREW_INSTANCES)
    # The retired 91255A150 #6-32 button head and its identity are gone.
    assert spec.PILLOW_BLOCK_SCREW == "ch-rocker-arm-tl-vn-oblique-bracket-screw"
    assert not hasattr(spec, "BRACKET_SCREW") and not hasattr(spec, "kp08_screw")
    root = Path(__file__).resolve().parents[2]
    assert not (root / "cad/config/parts/ch-rocker-arm-tl-vn-oblique-kp08-screw.yaml").exists()
    assert not (root / "cad/scripts/_mcmaster_91255a150.py").exists()

def test_a200_shares_the_short_sku_but_not_the_explode_direction() -> None:
    assert spec.PLACEMENTS[spec.RAIL_SCREW] == (
        spec.RAIL_SCREW_PLACEMENTS + spec.STRAP_CLAMP_SCREW_PLACEMENTS
    )
    assert spec.PLACEMENTS[spec.PILLOW_BLOCK_SCREW] == (
        spec.PILLOW_BLOCK_SCREW_PLACEMENTS + spec.BAR_SCREW_PLACEMENTS
    )
    assert spec.KP08_SCREW_INSTANCES == tuple(
        spec.instance_name(spec.PILLOW_BLOCK_SCREW, index) for index in range(4)
    )
    assert spec.BAR_SCREW_INSTANCES == tuple(
        spec.instance_name(spec.PILLOW_BLOCK_SCREW, index) for index in range(4, 8)
    )
    explode = {name: (members, axis, travel) for name, members, axis, travel in spec.EXPLODE_STEPS}
    assert explode["kp08 screws lift out"] == (spec.KP08_SCREW_INSTANCES, "z", 40.0)
    assert explode["bar screws drop out"] == (spec.BAR_SCREW_INSTANCES, "z", -40.0)
    fitting = next(step for step in spec.ASSEMBLY_STEPS if step.startswith("2. "))
    assert f"{spec._item(spec.PILLOW_BLOCK_SCREW)} FROM BELOW" in fitting
    assert spec._torque(leadscrew.BAR_SCREW_TORQUE_NM) in fitting
    assert fasteners.BRACKET_TO_BAR.thread_depth_mm == end_bracket.BAR_THREAD_LIMITS[0]
    assert fasteners.KP08_TO_BRACKET.thread_depth_mm == end_bracket.KP08_THREAD_LIMITS[0]


def test_carriage_screws_are_cut_to_fit_under_a_confirmed_owner_exception() -> None:
    """Owner ruling 2026-11-01 (option A): step 5 measures each counterbore
    floor and cuts each M4 x 20 to it; RV-05 accepts the 1.03D full thread."""
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    assert spec._item(spec.CARRIAGE_SCREW) in steps["5A"]
    # RV-05's where: the cut to floor + .189 and the .183-.195 engagement.
    assert "+ .189" in steps["5A"] and ".183-.195" in steps["5C"]
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "ch_rocker_arm_tl_oblique_jig_assembly", "assembly")
    }
    reach = entries["RV-05"]
    assert reach.kind == "accept"
    assert "+ .189" in reach.where and ".183-.195" in reach.where
    assert "1.03D" in reach.finding


def test_bar_2_is_the_plain_member_turned_over() -> None:
    # PR2: only Bar1 (rail 1, unturned) is drilled for the brackets; rail 2's
    # bar is the Bar2 member, plain, so nothing faces up on it to clear.
    assert spec.instance_name(spec.BASE_BAR_1, 0) == "@Bar1:1"
    assert spec.instance_name(spec.BASE_BAR_2, 0) == "@Bar2:1"
    assert spec.PLACEMENTS[spec.BASE_BAR_1] == (spec.BASE_BAR_PLACEMENTS[spec.RAILS.index(1)],)
    assert spec.PLACEMENTS[spec.BASE_BAR_2] == (spec.BASE_BAR_PLACEMENTS[spec.RAILS.index(2)],)
    assert not spec.TURNED_OVER[1] and spec.TURNED_OVER[2]
    assert base_bar.CONFIGURATION_FEATURES[base_bar.BAR2] == ()
    assert set(base_bar.CONFIGURATION_FEATURES[base_bar.BAR1]) == {
        "BracketHoles", "BracketRowReference",
    }
    # The bar screws come up through Bar1 into the brackets.
    assert spec.BAR_SCREW_PLACEMENTS[0][0][:2] == pytest.approx(
        spec.bar_point(1, (*leadscrew.BASE_BAR_HOLES[0], 0.0))[:2]
    )


def test_bracket_bar_screws_sit_on_the_kp08_pitch() -> None:
    # Owner ruling Main 2026-11-06 (option B): two holes a bracket, on the
    # KP08's 42 mm pitch about the screw axis; the stations print exact mm.
    laterals = leadscrew.BAR_SCREW_LATERALS
    axis = leadscrew.SCREW_LATERAL
    assert len(laterals) == 2 and laterals == tuple(sorted(laterals))
    assert laterals[0] + laterals[1] == pytest.approx(2.0 * axis)
    assert laterals[1] - laterals[0] == pytest.approx(leadscrew.KP08_BOLT_SPACING)
    assert leadscrew.BRACKET_HOLES_X == pytest.approx((13.925, 55.925))
    assert tuple(leadscrew.BRACKET_INNER_LATERAL + x for x in leadscrew.BRACKET_HOLES_X) == (
        pytest.approx(laterals)
    )
    assert leadscrew.BRACKET_LENGTH == pytest.approx(
        trammel.BASE_BAR_COLUMN_EDGE - leadscrew.BRACKET_INNER_LATERAL
    )
    length = leadscrew.BRACKET_LENGTH / 25.4
    assert length == pytest.approx(round(length, 2), abs=1e-9)


def test_bracket_slip_stop_and_lost_motion_follow_ruling_b() -> None:
    # Owner ruling Main 2026-11-06 (option B; replaces the 2026-10-27
    # slip-governs criterion for TL-28 on TL-20 only): A″ keeps the 5/8 screws at
    # 2.8 N·m, no washers. No slip under the normal cutting feed; above
    # ~1344 N (handwheel abuse) the bracket may slip onto its bar screws'
    # positive thread stop, which carries the abuse envelope in hole/thread
    # bearing and screw shear. Reversal lost motion: the owner's R4 ruling
    # (Main, via the coordinator after farm 84d5991d45) keeps option B and
    # accepts up to 1.06 mm (was ~.9); the #12 geometry is unchanged.
    assert leadscrew.BAR_SCREW_TORQUE_NM == 2.8
    assert leadscrew.BAR_SCREW_PRELOAD == pytest.approx(3360.9, abs=0.1)
    assert leadscrew.BAR_SCREW_THRUST_ECCENTRICITY == pytest.approx(0.0)
    assert leadscrew.BRACKET_SLIP_THRUST == pytest.approx(1344.3, abs=0.1)
    assert leadscrew.BRACKET_OPENING_THRUST == pytest.approx(352.2, abs=0.1)
    # The normal feed's thrust comes from the cutter load, not the crank.
    assert spec.NORMAL_FEED_CHIP_LOAD_MM == 0.0254
    kc = 1500.0 * 0.0254 ** -0.22
    tooth = kc * trammel.STRAP_THICK * 0.0254
    assert spec.NORMAL_CUT_FORCE_N == pytest.approx(2.0 * math.sqrt(2.0) * tooth)
    ratio = max(
        1.0 / math.cos((trammel.ALPHA + sign * trammel.SWEEP[name]) / 2.0)
        for name in trammel.PASS_RADIUS
        for sign in (-1.0, 1.0)
    )
    assert spec.NORMAL_FEED_RATIO == pytest.approx(ratio)
    assert spec.NORMAL_FEED_THRUST_N == pytest.approx(spec.NORMAL_CUT_FORCE_N * ratio)
    assert spec.NORMAL_FEED_THRUST_N == pytest.approx(619.5, abs=0.5)
    assert leadscrew.BRACKET_SLIP_THRUST >= leadscrew.SLIP_MARGIN_MIN * spec.NORMAL_FEED_THRUST_N
    # The crank envelope exceeds the slip load: the positive stop carries it.
    assert spec.FEED_THRUST_N > leadscrew.BRACKET_SLIP_THRUST
    assert spec.BRACKET_ABUSE_THRUST_N == max(spec.FEED_THRUST_N, leadscrew.HAND_ABUSE_THRUST)
    assert spec.BRACKET_ABUSE_STOP_MARGINS == leadscrew.bracket_stop_margins(
        spec.BRACKET_ABUSE_THRUST_N
    )
    assert set(spec.BRACKET_ABUSE_STOP_MARGINS) == {
        "TL-20 hole wall bearing", "TL-28 thread bearing", "screw shear",
    }
    assert min(spec.BRACKET_ABUSE_STOP_MARGINS.values()) >= leadscrew.STOP_MARGIN_MIN
    # Lost motion of this lower joint alone, at the true worst case (the
    # #12 hole's drilled maximum over the UNC-3A minimum major), with the
    # basic-major figure disclosed; the KP08 joint's float is separate.
    assert leadscrew.BRACKET_REVERSAL_LOST_MOTION == pytest.approx(0.876, abs=1e-3)
    assert leadscrew.BRACKET_REVERSAL_LOST_MOTION_BASIC == pytest.approx(0.737, abs=1e-3)
    assert leadscrew.BRACKET_REVERSAL_LOST_MOTION_ACCEPTED == 1.06
    assert (
        leadscrew.BRACKET_REVERSAL_LOST_MOTION
        <= leadscrew.BRACKET_REVERSAL_LOST_MOTION_ACCEPTED
    )
    assert leadscrew.KP08_SCREW_FLOAT_MAX == pytest.approx(0.487, abs=1e-3)
    # Cross-check the chip load against the shop's cutting data.
    import tomllib
    from _paths import CAD_ROOT

    rows = tomllib.loads(
        (CAD_ROOT / "process" / "shop" / "cutting-data.toml").read_text(encoding="utf-8")
    )["cut"]
    [row] = [
        r for r in rows
        if r["material_class"] == "low_carbon_steel" and r["tool_material"] == "HSS"
        and r["operation"] == "profile"
        and r["diameter_range"][0] <= trammel.PART_CUTTER_DIA <= r["diameter_range"][1]
    ]
    assert row["chip_load_mm_per_tooth"] == spec.NORMAL_FEED_CHIP_LOAD_MM


@pytest.mark.parametrize(
    ("nm", "printed"),
    (
        (0.4, "3.5 IN·LBF"),
        (2.8, "25 IN·LBF"),
        (4.0, "35 IN·LBF"),
        (16.5, "150 IN·LBF"),
    ),
)
def test_printed_torque_is_inch_rounded_to_two_significant_figures(nm, printed) -> None:
    """Rule 26 prints inch only; owner ruling 3 (2026-11-01) keeps the
    conversion rounded to the nearest two significant figures."""
    assert spec._torque(nm) == printed
    in_lbf = float(printed.split(" ", 1)[0])
    exact = nm / (4.4482216152605 * 0.0254)
    half_step = 0.5 * 10 ** (math.floor(math.log10(exact)) - 1)
    assert abs(in_lbf - exact) <= half_step


def _step_groups() -> dict[str, str]:
    """Each top-level step with its lettered sub-steps, joined."""
    groups: dict[str, list[str]] = {}
    for text in (*spec.ASSEMBLY_STEPS, *spec.OPERATION_STEPS):
        head = text.split(". ", 1)[0]
        groups.setdefault(re.match(r"\d+", head).group(0), []).append(text)
    return {number: " ".join(texts) for number, texts in groups.items()}


def test_rail_preparation_precedes_fastening_and_table_mounting() -> None:
    groups = _step_groups()
    preparation, fitting, mounting = groups["1"], groups["2"], groups["3"]
    # Use the actual component roles, not exact instruction prose.
    for family, step in (
        (spec.CARRIAGE, preparation),
        (spec.END_BRACKET, fitting),
        (spec.T_NUT, mounting),
    ):
        citation = spec._item(family)
        assert citation in step
        assert sum(citation in groups[number] for number in ("1", "2", "3")) == 1
    assert spec._item(spec.RAIL) in preparation
    assert spec._item(spec.RAIL_SCREW) in fitting
    assert spec._item(spec.HOLD_DOWN_STUD) in mounting


def test_step_10_taps_the_carrier_hub_in_situ_at_the_recorded_dro() -> None:
    """Owner ruling 3 (2026-11-07): the carrier's HUB #8-32 tap is made in
    situ at the step 10 DRO position, every strap's hub hole is drilled and
    reamed at the same setting, and there is no counterbore or precision bore.
    Q7: the setting is checked from the set position on both pivot heads."""
    steps = {text.split(". ", 1)[0]: text for text in (*spec.ASSEMBLY_STEPS, *spec.OPERATION_STEPS)}
    assert "X 0, Y .5125 ±.0005" in steps["10C"]
    assert steps["10D"].startswith("10D. CHECK THE A1 AND B1 HEADS")
    assert "-1.2801" in steps["10D"] and "FROM THIS SETTING" in steps["10D"]
    assert steps["10E"].startswith("10E. IF ONE FAILS")
    assert "RECORD" in steps["10G"] and "STEP 20" in steps["10G"]
    assert carrier.HUB_THREAD in steps["10H"] and "NO COUNTERBORE" in steps["10H"]
    assert "STEP 10G" in steps["20"]
    assert all("REAM" not in steps[head] for head in ("10C", "10D", "10G", "10H"))
    assert spec.carrier.HUB_RADIAL_STACK < 0.25


def test_head_check_band_covers_the_hub_band_and_the_rail_chain() -> None:
    """Q7: a head inside its rails' bands, read from a hub setting inside its
    band, passes step 10D: the hub band plus the chain's lateral error at the
    symmetric station (4.3 thou), rounded up to .001."""
    inch = spec.trammel.INCH
    assert spec.HEAD_CHECK_BAND == pytest.approx(0.006 * inch)
    assert spec.HEAD_CHECK_BAND > spec.carrier.HUB_OFFSET_BAND + 0.004 * inch


def test_rail_setting_chain_holds_the_6_in_row_and_closes_the_stack() -> None:
    """Q6: stations 4.00, 10.00 and 15.00, each link 6.0 in or less from the
    head set before, at the shop table's ±.002; the chain's computed radial
    error (0.082 mm) closes with the shoulder and printed play."""
    inch = spec.trammel.INCH
    assert spec.CHAIN_STATIONS == pytest.approx((4.0 * inch, 10.0 * inch, 15.0 * inch))
    assert spec.STATION_BAND == pytest.approx(0.002 * inch)
    assert spec.CHAIN_STATION_RADIUS == pytest.approx(0.0824, abs=0.0005)
    assert spec.CHAIN_RADIAL_STACK == pytest.approx(0.2454, abs=0.0005)
    assert spec.CHAIN_RADIAL_STACK <= spec.trammel.TOP_EDGE_HALF_BAND
    references = [row[1] for row in spec.RAIL_SETTING_ROWS]
    assert references == ["ORIGIN", "S 4.00", "S 10.00"]
    for (near, far), row in zip(spec._CHAIN_LINKS, spec.RAIL_SETTING_ROWS, strict=True):
        for rail, (x_cell, y_cell) in zip((1, 2), (row[2:4], row[4:6]), strict=True):
            fx, fy = spec.trammel.rail_point(rail, far)
            nx, ny = spec.trammel.rail_point(rail, near) if near else (0.0, 0.0)
            assert math.hypot(float(x_cell), float(y_cell)) <= 6.0 + 1e-4  # printed rounding
            assert float(x_cell) == pytest.approx((fx - nx) / inch, abs=5e-5)
            assert float(y_cell) == pytest.approx((fy - ny) / inch, abs=5e-5)
        assert row[6:] == ("±.002", "6G")
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    assert steps["6G"].startswith("6G. CHECK")
    assert "INCREMENTAL" in steps["6B"] and "INCREMENTAL" in steps["6D"]
    assert "ABSOLUTE" in steps["6M"]


def test_step_11_sets_the_stop_axes_before_spotting_the_riser() -> None:
    """Installed axes use the retained spindle-origin DRO at inner symmetry."""
    pose = trammel.carrier_pose("inner", 0.0)
    assert pose.to_machine((0.0, trammel.APEX_Y)) == pytest.approx((0.0, 0.0))
    for carrier_point, dro_point, (origin, _rows) in zip(
        riser.STOP_PIN_CARRIER_POINTS, spec.STOP_PIN_DRO_POINTS,
        spec.STOP_PIN_PLACEMENTS, strict=True,
    ):
        assert dro_point == pytest.approx(pose.to_machine(carrier_point), abs=1e-9)
        assert dro_point == pytest.approx(
            (carrier_point[0], carrier_point[1] - trammel.APEX_Y), abs=1e-9
        )
        assert dro_point == pytest.approx(origin[:2], abs=1e-9)
        assert dro_point[1] < 0.0 < carrier_point[1]
    assert spec._STOP_AXIS_BAND == pytest.approx(0.254)
    assert spec._STOP_DRO == "X -6.61 AND X 6.61, Y -.57 (±.01)"
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    assert spec._STOP_DRO in steps["11A"]
    assert spec._item(spec.STOP_PIN) in steps["11"]
    # The axes are set before the riser is spotted from the carrier.
    order = list(steps)
    assert order.index("11A") < order.index("11C")


def test_r4_operation_order_cites_the_plan_and_retains_all_clamps() -> None:
    steps = {text.split(". ", 1)[0]: text for text in spec.OPERATION_STEPS}
    numbers = list(dict.fromkeys(re.match(r"\d+", head).group(0) for head in steps))
    assert numbers == [str(n) for n in range(15, 22)]
    assert spec.PROCESS_PLAN == "MHA-CH-06 PLAN"
    # The riser is cut before the first strap; the strap is prepared, drilled
    # and reamed, then cut per the plan's sections.
    assert "BEFORE THE FIRST STRAP" in steps["18"]
    assert "PLAN S0-S1 AND S2 OP20" in steps["19"]
    assert "PLAN S2 OP30-OP40" in steps["20A"]
    assert "PLAN S3 OP10-OP20" in steps["21D"]
    assert spec._torque(spec.holding.HUB_TORQUE_NM) in steps["21A"]
    assert spec._item(spec.HUB_WASHER) in steps["21"]
    for text in steps.values():
        # The plan prints the blank, chords and the hub tool envelope.
        assert "350 MM" not in text and "REAMER" not in text
    assert f"{spec._CLAMP_SCREW} {spec._item(spec.RAIL_SCREW)}" in steps["19B"]
    assert "ALL 3 CLAMP SCREWS" in steps["21D"]


def test_r4_holding_hardware_placements_close_on_actual_seats() -> None:
    hub = spec.POSE.to_machine(trammel.HUB)
    (washer, _rows), = spec.HUB_WASHER_PLACEMENTS
    assert washer[:2] == pytest.approx(hub)
    assert washer[2] == pytest.approx(spec.PART_TOP_Z)
    cl, cr, hub_screw = (origin for origin, _rows in spec.STRAP_CLAMP_SCREW_PLACEMENTS)
    assert cl[2] == cr[2] == pytest.approx(spec.PART_TOP_Z)
    assert hub_screw[:2] == pytest.approx(hub)
    assert hub_screw[2] == pytest.approx(spec.PART_TOP_Z + spec.hub_washer.THICK)
    for role, (origin, _rows) in zip(
        spec.STRAP_CLAMP_ROLES, spec.STRAP_CLAMP_SCREW_PLACEMENTS, strict=True
    ):
        key = "hub" if role == "HUB" else role
        assert origin[2] + spec.rail_screw.DIMS.head_h == pytest.approx(spec.holding.CLAMP_TOP_Z[key])
    # The stop pins stand uncut, full height, on the carrier top.
    for origin, _rows in spec.STOP_PIN_PLACEMENTS:
        assert origin[2] == pytest.approx(trammel.CARRIER_TOP_Z)
    assert spec.LOCKED_TO[spec.HUB_WASHER] == ((spec.CARRIER, 0),)
    assert spec.LOCKED_TO[spec.STOP_PIN] == ((spec.CARRIER, 0),) * 2
    assert spec.PART_TOP_Z == spec.holding.PART_TOP_Z


def test_stud_steps_cut_to_the_kit_sheet_and_accept_directly() -> None:
    """Q3 (Delegated ruling 2026-11-07 (Main), no precedent; owner review
    #2144; pending owner confirmation): the studs are cut to the kit length,
    checked directly for clearance and projection, with a cut-shorter remedy."""
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    assert spec.STUD_REWORK_SHEET in steps["3"]
    assert spec._item(spec.HOLD_DOWN_STUD) in steps["3"]
    assert f"{spec._STUD_CLEARANCE} MIN" in steps["13A"]
    assert steps["13B"].startswith("13B. IF ")
    assert spec._STUD_PITCH in steps["13E"]
    assert steps["13F"].startswith("13F. IF ")
    assert spec.HOLD_DOWN_REFERENCE.endswith(
        f"STEPS {spec.HOLD_DOWN_STEPS_REFERENCE} (SHEET {spec.HOLD_DOWN_SHEET_NUMBER})"
    )
    assert not hasattr(spec, "HOLD_DOWN_STEPS") and not hasattr(spec, "_STUD_LIMITS")


def test_kp08_row_reads_by_item() -> None:
    assert spec.BOM_DESCRIPTIONS[spec.PILLOW_BLOCK] == "KP08 PILLOW BLOCK, 8 MM BORE"
    for text in (*spec.ASSEMBLY_STEPS, *spec.OPERATION_STEPS):
        assert "KP08" not in text


def test_general_torque_note_covers_every_fastener_no_step_torques() -> None:
    """Review jig-asm r1 (rule 24): one general note for the screws and nuts
    whose steps give no torque, with no invented figure."""
    steps = {
        text.split(". ", 1)[0]: text for text in (*spec.ASSEMBLY_STEPS, *spec.OPERATION_STEPS)
    }
    torqued = {
        spec.LEVER_SCREW: ("12", spec.LEVER_SCREW_TORQUE_NM),
        spec.PIVOT_SCREW: ("9M", spec.PIVOT_SCREW_TORQUE_NM),
        spec.PILLOW_BLOCK_SCREW: ("8C", spec.KP08_SCREW_TORQUE_NM),
    }
    for head, nm in torqued.values():
        assert spec._torque(nm) in steps[head]
    assert spec._item(spec.RAIL_SCREW) in steps["21A"]
    assert spec._torque(spec.holding.HUB_TORQUE_NM) in steps["21A"]
    # The common family's hub clamp takes 21A's torque; its rail/end-clamp
    # instances use the general snug note. Step 2B torques the bracket
    # family's lower screws separately from 8C's upper KP08 screws.
    assert spec._item(spec.RAIL_SCREW) in steps["2A"]
    assert spec._item(spec.PILLOW_BLOCK_SCREW) in steps["2B"]
    assert spec._torque(leadscrew.BAR_SCREW_TORQUE_NM) in steps["2B"]
    # The riser screw family's four feed-nut screws take 8S's torque; its
    # four riser screws, with no stated torque, stay on the general note.
    assert spec._item(spec.RISER_SCREW) in steps["8Q"]
    assert spec._torque(spec.NUT_SCREW_TORQUE_NM) in steps["8S"]
    threaded = {
        spec.RAIL_SCREW, spec.CARRIAGE_SCREW,
        spec.PILLOW_BLOCK_SCREW, spec.RISER_SCREW,
        spec.LEVER_SCREW, spec.PIVOT_SCREW, spec.FLANGE_NUT,
    }
    assert set(spec.SNUG_FASTENERS) == threaded - set(torqued)
    snug = sorted(int(spec.ITEM_NUMBERS[s]) for s in spec.SNUG_FASTENERS)
    # The note names exactly the snug items and states no torque figure.
    note = spec.GENERAL_TORQUE_NOTE
    assert sorted(int(n) for n in re.findall(r"\b\d+\b", note)) == snug
    assert "N·m" not in note and "IN·LBF" not in note


def test_sweep_limits_are_witness_marked_and_every_pass_runs_mark_to_mark() -> None:
    """Review jig-asm r2: each sweep limit is a pass-table row, set in X
    only and witness-marked (step 6N-6P); every complete pass runs mark to mark."""
    hundredth = spec.trammel.INCH / 100.0
    gap = spec.leadscrew.FEED_GAP
    for name, (lo, hi) in spec.SWEEP_LIMITS.items():
        exact_lo, exact_hi = spec.trammel.PIN_TRAVEL[name]
        assert exact_lo - hundredth < lo <= exact_lo
        assert exact_hi <= hi < exact_hi + hundredth
        for s in (lo, hi):
            centre = s - spec.trammel.PIN_OFFSET
            lo_s, hi_s = spec.trammel.CARRIAGE_S_RANGE
            assert lo_s <= centre <= hi_s
            travel = spec.trammel.CARRIAGE_TRAVEL
            assert travel[0] - gap < centre < travel[1] + gap
    limits = [row for row in spec.PASS_TABLE_ROWS if row[0].endswith(" LIMIT")]
    assert sorted(float(row[1]) for row in limits) == sorted(
        round(s / spec.trammel.INCH, 2) for pair in spec.SWEEP_LIMITS.values() for s in pair
    )
    # A pass row is set in X only at the long-travel row; its Y is REF.
    for row in spec.PASS_TABLE_ROWS:
        assert row[3].startswith("(") and row[5].startswith("(")
        assert row[6] == "X ±.004"
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    assert "LIMIT ROW" in steps["6N"] and "X ONLY" in steps["6N"]
    assert "WITNESS-MARK" in steps["6P"]
    assert "MARK TO MARK" in steps["9N"] and "MARK TO MARK" in steps["13A"]


def test_lever_screw_torque_is_capped_by_the_carrier_thread() -> None:
    # C3 r6 TL-00 review (rule 23): the wedge-lock pairs keep the lever
    # screws from backing off under the operator's reversing push and pull.
    # Their preload is a third of the TL-21 6061 tap's strip load over the
    # shortest engagement (the shortest 1 in screw through the thickest lever
    # and pair, inside the 12 plate's RV-01 full thread), T = 0.20 F d.
    engagement = lever_washer.ENGAGEMENT_MIN
    # Rule 18: at least 1 D of full thread at the worst case.
    assert engagement >= fasteners.LEVER_TO_CARRIER.major_mm
    assert engagement <= carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD]
    major = fasteners.LEVER_TO_CARRIER.major_mm
    assert major == pytest.approx(7.9375, abs=1e-3)
    assert spec._LEVER_THREAD_STRIP_N == pytest.approx(
        0.75 * math.pi * major * engagement * spec._AL_SHEAR_ULTIMATE_MPA
    )
    cap = 0.20 * (spec._LEVER_THREAD_STRIP_N / 3.0) * major / 1000.0
    assert cap - 0.1 < spec.LEVER_SCREW_TORQUE_NM <= cap
    assert round(spec.LEVER_SCREW_TORQUE_NM, 1) == spec.LEVER_SCREW_TORQUE_NM
    assert spec.LEVER_SCREW_PRELOAD_N <= spec._LEVER_THREAD_STRIP_N / 3.0
    assert spec.LEVER_PAIR_BEARING_MPA < 276.0
    assert spec.LEVER_SCREW_PRELOAD_N / (0.0524 * 25.4**2) < 0.5 * 1172.1


def test_feed_nut_screws_key_the_nut_and_hold_it_on() -> None:
    # Owner ruling 2026-11-04 (#2177, option B) under Main's 2026-11-03
    # ruling on #2112 (Codjiflo P1): the four flat heads, seated in the
    # nut's countersinks and threaded into the lug, are its positive stop; no
    # friction is counted on. The governing thrust is the firm 70 N crank
    # pull at the handwheel's grip offset, over the 1 kN hand abuse.
    d2 = leadscrew_stock.MAJOR_DIA - 0.5 * leadscrew_stock.PITCH
    lead = math.atan(leadscrew_stock.LEAD / (math.pi * d2))
    friction = math.atan(0.15 / math.cos(math.radians(15.0)))
    crank = 70.0 * leadscrew.HANDWHEEL_GRIP_OFFSET / 1000.0
    thrust = (
        2.0 * math.pi * crank * math.tan(lead) / math.tan(lead + friction)
        / (leadscrew_stock.LEAD / 1000.0)
    )
    assert spec.FEED_THRUST_N == pytest.approx(thrust)
    assert spec.NUT_THRUST_N == max(spec.FEED_THRUST_N, leadscrew.HAND_ABUSE_THRUST)
    assert spec.NUT_THRUST_N == pytest.approx(1361.3, abs=0.1)
    torque = thrust * d2 / 2000.0 * math.tan(lead + friction)
    assert spec.NUT_TORQUE_NM == pytest.approx(torque)
    assert spec.NUT_TORQUE_NM == pytest.approx(1.19, abs=0.005)
    # The four heads share it at the 16 PCD radius; each takes its share
    # across the #4-40 basic minor section at 0.6 x the 80 ksi tensile.
    count = fasteners.NUT_TO_FEED_BLOCK.count
    assert count == feed_nut.SCREW_COUNT == 4
    force = torque * 1000.0 / (count * feed_nut.HOLE_PCD / 2.0)
    assert spec.NUT_STOP_FORCE_N == pytest.approx(force)
    capacity = 0.6 * 80_000.0 * 0.006894757 * math.pi / 4.0 * (0.0813 * 25.4) ** 2
    assert spec.NUT_STOP_MARGIN == pytest.approx(capacity / force)
    assert spec.NUT_STOP_MARGIN >= leadscrew.SLIP_MARGIN_MIN
    assert round(spec.NUT_STOP_MARGIN) == 30
    # The screws: with no joint-stiffness credit their preload alone holds
    # the nut against that thrust, within what the lug's tap and the 360-H02
    # (17 ksi) under each head's cone carry.
    major = fasteners.NUT_TO_FEED_BLOCK.major_mm
    assert spec.NUT_SCREW_TORQUE_NM == 0.3
    preload = spec.NUT_SCREW_TORQUE_NM / (0.20 * major / 1000.0)
    assert spec.NUT_SCREW_PRELOAD_N == pytest.approx(preload)
    assert spec.NUT_SCREW_PRELOAD_N == pytest.approx(527.2, abs=0.1)
    assert spec.NUT_PULL_OFF_MARGIN == pytest.approx(count * preload / thrust)
    assert spec.NUT_PULL_OFF_MARGIN > 1.0
    # Rule 18: at least 2D of full thread in the 6061 lug at the worst case.
    assert feed_nut.SCREW_FULL_THREAD_MIN >= 2.0 * major
    strip = 0.75 * math.pi * major * feed_nut.SCREW_FULL_THREAD_MIN * 207.0
    assert spec._NUT_SCREW_STRIP_N == pytest.approx(strip)
    assert preload <= strip / 3.0
    assert spec._BRASS_YIELD_MPA == pytest.approx(117.2, abs=0.05)
    cone = math.pi / 4.0 * (feed_nut.CSK_DIA_MIN**2 - feed_nut.CSK_BEARING_INNER_DIA**2)
    assert feed_nut.CSK_BEARING_AREA_MIN == pytest.approx(cone)
    assert spec.NUT_SCREW_BEARING_MPA == pytest.approx(preload / cone)
    assert spec.NUT_SCREW_BEARING_MPA == pytest.approx(102.1, abs=0.1)
    assert spec.NUT_SCREW_BEARING_MPA < spec._BRASS_YIELD_MPA
    assert spec.NUT_SCREW_PRELOAD_N <= spec._NUT_SCREW_PRELOAD_CAP_N
    # The screw: under half its 80 ksi on the #4-40 stress area.
    assert preload / (0.00604 * 25.4**2) < 0.5 * 80_000 * 0.006894757


def test_nut_screw_heads_seat_in_the_countersinks_clear_of_the_body() -> None:
    # Option B: each flat head bears on its 82° countersink's cone and stands
    # proud of the flange even at F2's opened countersink, so it never
    # bottoms on the flat face; at the transfer's eccentricity (each tap
    # spotted through its hole with a #29 drill) it clears the nut's body.
    assert feed_nut.CSK_ANGLE == pytest.approx(82.0)
    assert feed_nut.HEAD_PROUD_MIN > 0.0
    assert feed_nut.HEAD_PROUD_MIN < feed_nut.HEAD_PROUD_NOMINAL < feed_nut.HEAD_PROUD_MAX
    e = feed_block.FIT_UP_RESIDUAL
    assert e == pytest.approx((feed_nut.HOLE_DIA_MAX - feed_block.TRANSFER_SPOT_DIA) / 2.0)
    assert feed_block.TRANSFER_SPOT_DIA < feed_nut.HOLE_DIA_MIN
    # A head held in its tap stands the residual off its hole, more than its
    # countersink's eccentricity; the catalogue head still clears the body.
    assert e > feed_nut.CSK_ECCENTRICITY_MAX
    assert feed_block.HEAD_TO_BODY_MIN == pytest.approx(
        feed_block.HEAD_TO_BODY_CENTRED - (e - feed_nut.CSK_ECCENTRICITY_MAX)
    )
    assert feed_block.HEAD_TO_BODY_MIN > 0.0
    # The countersink cutter, at its largest, stays off the body too, and the
    # sheet's mouth band never exceeds it.
    assert feed_nut.CSK_DIA_MAX <= feed_nut.CSK_CUTTER_DIA_MAX
    assert feed_nut.CSK_CUTTER_TO_BODY > 0.0


def _lens_area(r1: float, r2: float, d: float, steps: int = 200_000) -> float:
    """Area common to two circles ``d`` apart, by summing common chords."""
    low, high = max(-r1, d - r2), min(r1, d + r2)
    width = (high - low) / steps
    total = 0.0
    for i in range(steps):
        x = low + (i + 0.5) * width
        total += 2.0 * min(
            math.sqrt(max(r1 * r1 - x * x, 0.0)),
            math.sqrt(max(r2 * r2 - (x - d) ** 2, 0.0)),
        ) * width
    return total


def test_kp08_screws_torque_inside_the_foot_thread_and_screw_budgets() -> None:
    # F1B tightens each KP08's two #8-32 X 5/8 SHCS (TL-VN-62, 91251A196; the
    # owner-approved second length, ruling Main 2026-11-06 option B) to
    # 1.0 N·m: the foot taken as Zamak 3 (208 MPa), bearing under the socket
    # head's least flat bearing (ASME B18.3 Table 1 #8: A min .257 less the
    # K .008 edge break on each side, note (12): .241) round its Ø5 hole (UNVERIFIED, #2184)
    # with the block floated fully to one side; TL-28's top-face tap at its
    # worst-case full thread;
    # the screw under half its 170 ksi on the #8-32's 0.0140 in² stress area.
    row = fasteners.KP08_TO_BRACKET
    assert fasteners.callout(row) == "#8-32 X 5/8 SHCS"
    assert spec.KP08_SCREW_TORQUE_NM == 1.0
    preload = spec.KP08_SCREW_TORQUE_NM / (0.20 * row.major_mm / 1000.0)
    assert spec.KP08_SCREW_PRELOAD_N == pytest.approx(preload)
    r = bracket_screw.HEAD_BEARING_R
    assert bracket_screw.HEAD_DIA_MIN == pytest.approx(0.257 * 25.4)
    assert bracket_screw.HEAD_EDGE_BREAK_MAX == pytest.approx(0.008 * 25.4)
    assert bracket_screw.HEAD_BEARING_DIA_MIN == pytest.approx(
        bracket_screw.HEAD_DIA_MIN - 2.0 * bracket_screw.HEAD_EDGE_BREAK_MAX
    )
    assert bracket_screw.HEAD_BEARING_DIA_MIN == pytest.approx(0.241 * 25.4)
    assert r == bracket_screw.HEAD_BEARING_DIA_MIN / 2.0 < bracket_screw.HEAD_DIA_MIN / 2.0
    # The flat bearing still covers the hole at full float, 0.074 to spare.
    assert bracket_screw.HEAD_OVER_HOLE == pytest.approx(r - leadscrew.KP08_HOLE_DIA / 2.0)
    assert bracket_screw.HEAD_OVER_HOLE - bracket_screw.HOLE_FLOAT == pytest.approx(
        0.0736, abs=1e-3
    )
    assert bracket_screw.HOLE_FLOAT == pytest.approx(
        (leadscrew.KP08_HOLE_DIA - leadscrew.SHCS_8_MAJOR_MIN) / 2.0, abs=1e-3
    )
    area = math.pi * r * r - _lens_area(r, leadscrew.KP08_HOLE_DIA / 2.0, bracket_screw.HOLE_FLOAT)
    assert spec.KP08_FOOT_BEARING_MM2 == pytest.approx(area, rel=1e-4)
    assert spec.KP08_FOOT_BEARING_MPA == pytest.approx(preload / area, rel=1e-4)
    margins = spec.KP08_SCREW_MARGINS
    assert margins["foot bearing"] == pytest.approx(208.0 * area / preload, rel=1e-4)
    assert round(margins["foot bearing"], 2) == 1.70
    strip = 0.75 * math.pi * row.major_mm * spec.KP08_SCREW_ENGAGEMENT_MIN * 207.0
    assert margins["TL-28 thread strip"] == pytest.approx(strip / 3.0 / preload)
    assert margins["screw stress"] == pytest.approx(
        0.5 * bracket_screw.TENSILE_PSI * 0.006894757 / (preload / (0.0140 * 25.4**2))
    )
    assert min(margins.values()) > 1.0
    assert spec.KP08_SCREW_ENGAGEMENT_MIN >= 2.0 * row.major_mm
    # Step 7A fits them loose; 8C tightens them once the pillow blocks are aligned.
    assert spec.PILLOW_BLOCK_SCREW not in spec.SNUG_FASTENERS
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    assert spec._torque(spec.KP08_SCREW_TORQUE_NM) in steps["8C"]
    assert f"{spec._item(spec.PILLOW_BLOCK_SCREW)}, LOOSE" in steps["7A"]
    seven = steps["7"]
    # Both 5/8 screws stay outside the opposed hand-tap cuts and keep
    # 1.5 D of full thread: the KP08 foot under them is checked first
    # (#2184 leaves it UNVERIFIED) between the end bracket's least foot
    # rounded up and its thickest foot rounded down.
    assert seven.startswith("7. ")
    assert spec._item(spec.PILLOW_BLOCK) in seven
    least = spec._bound(end_bracket.KP08_FOOT_THICK_MIN, 3, up=True)
    most = spec._bound(end_bracket.KP08_FOOT_THICK_MAX, 3, up=False)
    assert (least, most) == (".196", ".292")
    assert f"FOOT IS {least} TO {most} THICK AT ITS 2 HOLES" in seven
    assert (
        end_bracket.KP08_FOOT_THICK_MIN
        < leadscrew.KP08_FOOT_THICK
        < end_bracket.KP08_FOOT_THICK_MAX
    )
    major = THREAD_MAJOR_MM[leadscrew.KP08_SCREW]
    full = leadscrew.full_thread_min(
        leadscrew.KP08_SCREW_LENGTH, end_bracket.KP08_FOOT_THICK_MAX, leadscrew.KP08_SCREW
    )
    assert full >= 1.5 * major
    # One .001 thicker leaves the 5/8 under 1.5 D: the bound is the criterion's.
    thicker = end_bracket.KP08_FOOT_THICK_MAX + 0.0254
    assert (
        leadscrew.full_thread_min(
            leadscrew.KP08_SCREW_LENGTH, thicker, leadscrew.KP08_SCREW
        )
        < 1.5 * major
    )


def test_kit_rails_and_carriages_carry_the_owner_note_and_the_play_check() -> None:
    # Owner decisions on #2177: one NUIBBYED kit (2 rails, 4 carriages) is
    # bought for its 2 rails and 2 of its carriages; Z0 preload and C
    # accuracy are not required, the fit-up play check replaces them.
    assert spec.QUANTITIES[spec.RAIL] == spec.QUANTITIES[spec.CARRIAGE] == 2
    # TL-00 review 62753c5e: the trimmed rail's length is a reference.
    assert spec.BOM_DESCRIPTIONS[spec.RAIL] == f"{guide_rail.STYLE} RAIL, 440 MM REF, TRIM TO BAR"
    assert trammel.RAIL_LENGTH == trammel.BASE_BAR_LENGTH == 439.928
    assert spec.BOM_DESCRIPTIONS[spec.CARRIAGE] == f"{carriage.STYLE} CARRIAGE, KIT"
    for description in spec.BOM_DESCRIPTIONS.values():
        assert "Z0" not in description and "PRELOAD" not in description

    rail_item, carriage_item = spec.ITEM_NUMBERS[spec.RAIL], spec.ITEM_NUMBERS[spec.CARRIAGE]
    assert int(carriage_item) == int(rail_item) + 1
    # The printed check reads the trammel's budgeted play (Q5, Delegated
    # ruling 2026-11-07 (Main), no precedent; owner review #2144; pending
    # owner confirmation): .002 TIR, its radius inside the shoulder allowance
    # and, with it, the half band.
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    check = steps["14C"]
    assert check.endswith(f"{spec._PLAY_TIR}.") and spec._PLAY_TIR == ".002 TIR MAX"
    assert "SHOULDER-SCREW HEAD" in check and "SIDEWAYS" in check
    play = trammel.CARRIAGE_PLAY_RADIUS_PER_PLAY * spec.CARRIAGE_PLAY_TIR_PRINTED
    assert play == pytest.approx(0.0508, abs=1e-9)
    assert play <= trammel.RADIUS_FROM_SHOULDER_CLEARANCE
    assert trammel.CARRIAGE_PLAY_RADIUS == pytest.approx(
        trammel.CARRIAGE_PLAY_RADIUS_PER_PLAY * trammel.CARRIAGE_PLAY_TIR_MAX
    )
    # Carriage selection is preparation step 1, ahead of rail fitting.
    assert spec._item(spec.CARRIAGE) in _step_groups()["1"]
    assert trammel.RAIL_HOLE_COUNT == 8


def test_rail_preparation_cites_numbered_documents_and_the_stated_wall() -> None:
    # TL-00 review 62753c5e: every document step 1 uses is cited by Number
    # and sheet; the trimmed rail's wall check cites its stated minimum.
    preparation = _step_groups()["1"]
    assert spec.BASE_BAR_NUMBER == "MHA-CH-06-TL-20"
    assert spec.RAIL_RECEIPT_REFERENCE == "MHA-CH-06-TL-VN-83 SHEET 2"
    assert f"{spec.BASE_BAR_NUMBER} PROCESS PLAN" in preparation
    assert f"{spec.RAIL_RECEIPT_REFERENCE} NOTE [A]" in preparation
    assert f"[A] WALL FROM EACH END COUNTERBORE TO RAIL END: {guide_rail.WALL_ACCEPTANCE_MM:.1f} MIN." in (
        guide_rail.DRAWING_NOTES
    )
    assert " MM MIN" not in preparation


def test_bom_note_names_the_base_bar_rows_as_two_configurations() -> None:
    # TL-00 review 62753c5e: items 1 and 2 share TL-20's Number; the note
    # names them as its two configurations, each on its own sheet.
    note = spec.BOM_NOTE.split("\n")
    line = (
        f"ITEMS {spec.ITEM_NUMBERS[spec.BASE_BAR_1]}-{spec.ITEM_NUMBERS[spec.BASE_BAR_2]}: "
        "ONE NUMBER, TWO CONFIGURATIONS (MHA-CH-06-TL-20 SHEETS 1, 2)."
    )
    assert note[-1] == line
    assert spec.base_bar.CONFIGURATIONS == (spec.base_bar.BAR1, spec.base_bar.BAR2)
    buy = next(text for text in note if text.startswith("SHIM-"))
    assert len(line) <= len(buy)


def test_feed_nut_is_reworked_seated_and_transferred_in_one_order() -> None:
    # Owner ruling 2026-11-04 (option B) and Main's tightening procedure: the
    # nut is measured and reworked before the leadscrew is threaded; the
    # pillow blocks are aligned and tightened, then the nut is clocked and
    # seated on the leadscrew, the taps transferred through it and it is
    # screwed down with the leadscrew still in it.
    steps = {text.split(". ", 1)[0]: text for text in spec.ASSEMBLY_STEPS}
    heads = list(steps)
    sequence = ("7B", "7C", "7D", "7E", "7F", "8A", "8B", "8C", "8D", "8E", "8F",
                "8G", "8H", "8J", "8K", "8L", "8M", "8N", "8P", "8Q", "8R", "8S",
                "8T", "8U", "8V", "8W")
    assert [head for head in heads if head in sequence] == list(sequence)
    assert spec._item(spec.FEED_NUT) in steps["7B"]
    assert feed_nut.REWORK_SHEET_REFERENCE in steps["7B"]
    assert feed_nut.REWORK_SHEET_REFERENCE == f"{feed_nut.NUMBER} SHEET {feed_nut.REWORK_SHEET}"
    assert steps["7C"].startswith("7C. IF ") and steps["7F"].startswith("7F. IF ")
    # Codjiflo P2 and 4475311251: every receipt and rework limit is the kit
    # sheet's native dimension, not TL-00 text.
    limits = {
        f"{round(nominal + deviation, 6):.{places}f}"
        for nominal, lower, upper, places in feed_nut.NATIVE_CONTROLS.values()
        for deviation in (lower, upper)
    }
    preparation = " ".join(steps[head] for head in ("7B", "7C", "7D", "7E", "7F"))
    for typed in (
        *limits,
        f"Ø{feed_nut.CSK_DIA:.1f}", feed_nut.CSK_CUTTER_TEXT,
        f"{feed_nut.CSK_ANGLE:.0f}°", "LATHE", "SPIGOT",
    ):
        assert typed not in preparation, typed
    # Rule 25: the faced length is checked once, after the rework.
    assert feed_nut.SUPPLIED_LENGTH > feed_nut.LENGTH_MAX
    assert "FACED LENGTH" in steps["7E"] and "FACE" in steps["7D"]
    # Codjiflo 4477879822/4477879826 on #2187: every hole is set within
    # TL-32's native NutClock, cited and never typed.
    assert feed_block.NUT_CLOCK_REFERENCE == f"{feed_block.NUMBER} SHEET 2 VIEW D"
    assert feed_block.NUT_CLOCK_REFERENCE in steps["8D"]
    clock = f"{feed_block.NUT_CLOCK_DEG:.0f}°"
    band = f"±{feed_block.NUT_CLOCK_TOL_DEG:.0f}°"
    assert all(clock not in steps[h] and band not in steps[h] for h in ("8D", "8E"))
    assert "NEVER" in steps["8G"] and "SLIDE" in steps["8G"]
    # The drills are TL-32's: the spot enters the least nut hole, the tap
    # drill is the lug's.
    assert spec.NUMBER_DRILL_MM[spec._SPOT_DRILL] == pytest.approx(feed_block.TRANSFER_SPOT_DIA, abs=1e-3)
    assert spec.NUMBER_DRILL_MM[spec._TAP_DRILL] == feed_block.NUT_TAP_DRILL
    assert spec._SPOT_DRILL in steps["8J"]
    # TL-32's blind taps (FoObFab): drilled and tapped to its depths from the
    # lug's nut face with the nut stood off, then the nut reseated at 8G.
    assert spec._TAP_DRILL in steps["8M"] and feed_block.NUT_TAP_DRILL_DEPTH_TEXT in steps["8M"]
    assert feed_nut.SCREW_THREAD in steps["8N"] and feed_block.NUT_TAP_THREAD_DEPTH_TEXT in steps["8N"]
    assert "THRU" not in steps["8M"] + steps["8N"]
    assert "STEP 8G" in steps["8P"]
    # Owner ruling 2026-11-04 (#2177 option 3): the nut screws' heads are
    # calipered to the limit TL-32's head-to-body stack-up is built on; an
    # oversize head is replaced, the nut body never cut.
    head_limit = spec._bound(feed_nut.SCREW_HEAD_DIA_MAX, 3, up=False)
    assert head_limit == ".212" and f"Ø{head_limit} MAX" in steps["8Q"]
    assert spec._item(spec.RISER_SCREW) in steps["8Q"]
    assert feed_block.HEAD_TO_BODY_SHARP_CENTRED < 0.0 < feed_block.HEAD_TO_BODY_MIN
    assert steps["8R"].startswith("8R. IF ") and "NEVER MACHINE THE NUT BODY" in steps["8R"]
    assert spec._torque(spec.NUT_SCREW_TORQUE_NM) == "2.7 IN·LBF"
    assert spec._torque(spec.NUT_SCREW_TORQUE_NM) in steps["8S"]
    # 4475311242: the countersink opening stays within the sheet's band,
    # typed nowhere in TL-00.
    remedy = steps["8V"]
    assert feed_nut.REWORK_SHEET_REFERENCE in remedy
    assert not re.search(r"\d\.\d", remedy.replace(feed_nut.REWORK_SHEET_REFERENCE, ""))
    assert spec._item(spec.HANDWHEEL) in steps["8W"]
    # The fit-up acts on what it finds; it never stops to report.
    for head in sequence:
        assert "REPORT" not in steps[head] and "STOP" not in steps[head]
    for text in spec.ASSEMBLY_STEPS:
        for stale in ("PRINT-DRILLED", "TRANSFER SPOTTING", "LOOSE HOLES", "DOWEL PIN"):
            assert stale not in text


def test_handwheel_set_screw_meets_the_leadscrew_flat() -> None:
    # Codex review: the saved handwheel's supplied set screw (its -X tap)
    # points at the screw's set-screw flats (the screw's local +X), down.
    wheel_rows = spec.HANDWHEEL_PLACEMENTS[0][1]
    screw_rows = spec.LEADSCREW_PLACEMENTS[0][1]
    tap_x, tap_z = handwheel.SET_SCREW_DIRECTIONS[0]
    tap = tuple(tap_x * wheel_rows[0][i] + tap_z * wheel_rows[2][i] for i in range(3))
    assert tap == pytest.approx(screw_rows[0])
    assert screw_rows[0] == pytest.approx((0.0, 0.0, -1.0))
    # The screw's axis is the handwheel's.
    assert screw_rows[1] == pytest.approx(wheel_rows[1])




def test_shoulder_pivot_axial_stack_and_thread_engagement() -> None:
    row = fasteners.PIVOT_SCREW_TO_BLOCK
    assert row.engagement_mm == pivot_block.PIVOT_THREAD_ENGAGEMENT
    assert row.engagement_mm == pytest.approx(pivot_screw.THREAD_LENGTH - 1.5 * pivot_screw.THREAD_PITCH)
    # Rule 18 at the worst case, with no exception.
    assert pivot_block.PIVOT_THREAD_ENGAGEMENT_MIN >= 1.5 * pivot_screw.THREAD_DIA
    assert spec.PIVOT_SCREW_PRELOAD_N * 3.0 < spec.PIVOT_THREAD_STRIP_N
    assert row.torque_nm == spec.PIVOT_SCREW_TORQUE_NM
    assert row.threadlocker == "Loctite 222"
    tip_min = 0.011 * trammel.INCH
    for index, ((block, _rows), (screw, screw_rows)) in enumerate(zip(
        spec.BLOCK_PLACEMENTS, spec.PIVOT_SCREW_PLACEMENTS, strict=True,
    )):
        top = block[2] + pivot_block.BLOCK_HEIGHT
        assert screw[2] == pytest.approx(top - pivot_block.BORE_DEPTH)
        assert screw[2] - pivot_screw.THREAD_LENGTH - block[2] >= tip_min - 1e-9
        assert screw_rows[2] == pytest.approx((0.0, 0.0, 1.0))
        shims = spec.PIVOT_SHIM_PLACEMENTS[
            index * pivot_shim.PER_SUPPORT:(index + 1) * pivot_shim.PER_SUPPORT
        ]
        spacer = spec.PIVOT_SPACER_PLACEMENTS[index][0]
        assert len(shims) == pivot_shim.PER_SUPPORT
        # The pack stacks face to face from the block top up to the spacer.
        for k, (shim, _shim_rows) in enumerate(shims):
            assert shim[:2] == pytest.approx(screw[:2])
            assert shim[2] == pytest.approx(top + k * pivot_shim.THICKNESS)
        assert spacer[:2] == pytest.approx(screw[:2])
        assert spacer[2] == pytest.approx(shims[-1][0][2] + pivot_shim.THICKNESS)
        assert spacer[2] + pivot_spacer.LENGTH == pytest.approx(trammel.CARRIER_UNDERSIDE_Z)
        head_bottom = screw[2] + pivot_screw.SHOULDER_LENGTH
        gap = head_bottom - trammel.CARRIER_TOP_Z
        assert spec.PIVOT_RUNNING_GAP[0] <= gap <= spec.PIVOT_RUNNING_GAP[1]
        assert pivot_screw.HEAD_DIA > carrier.PIN_HOLE_DIA
    assert spec.lock_parent(spec.FEED_BLOCK, 0) == spec.instance_name(spec.CARRIAGE, 0)
    assert spec.lock_parent(spec.PIVOT_BLOCK, 0) == spec.instance_name(spec.CARRIAGE, 1)


def test_unshimmed_gap_opens_at_every_band_and_stock_shims_fit_it() -> None:
    from itertools import combinations_with_replacement

    thou = trammel.INCH / 1000.0
    assert spec.PIVOT_RUNNING_GAP == pytest.approx((0.002 * trammel.INCH, 0.010 * trammel.INCH))
    low, high = spec.PIVOT_UNSHIMMED_GAP_RANGE
    assert low >= spec.PIVOT_RUNNING_GAP[0]  # no head clamps before shimming
    # Brute force over the stock (keyed in thou), independent of the spec's
    # step argument.
    stock = list(pivot_shim.FIT_SKUS)
    assert all(pivot_shim.FIT_SKUS[t] for t in stock)
    packs = {
        sum(combo)
        for count in range(spec.PIVOT_FIT_SHIMS_MAX + 1)
        for combo in combinations_with_replacement(stock, count)
    }
    window = [round(g / thou) for g in spec.PIVOT_RUNNING_GAP]
    for gap in range(round(low / thou), round(high / thou) + 1):
        assert any(window[0] <= gap - pack <= window[1] for pack in packs), gap
    assert spec.PIVOT_FIT_PACK_MAX >= high - spec.PIVOT_RUNNING_GAP[1] - 1e-9
    # Codjiflo P3 on #2112: the bound covers banded stock. At the .071 worst
    # gap with every shim at its lower limit, three .020 and one .004 leave
    # .0105 (outside the window); the four-shim fit three .020 + one .008
    # (.0643) is inside the printed bound.
    lower = {t: t * thou + pivot_shim.FIT_THICKNESS_BANDS[t][1] for t in stock}
    assert high - (3 * lower[20] + lower[4]) > spec.PIVOT_RUNNING_GAP[1]
    fit = 3 * lower[20] + lower[8]
    assert spec.PIVOT_RUNNING_GAP[0] <= high - fit <= spec.PIVOT_RUNNING_GAP[1]
    assert fit <= spec.PIVOT_FIT_PACK_MAX
    assert spec.PIVOT_FIT_SHIMS_MAX == 4
    # Each support's share of the buy builds the worst-case pack.
    share = {
        round(thickness / thou): count // 2 for thickness, count in spec.PIVOT_SHIM_BUY.values()
    }
    assert sum(share[t] * t for t in share) >= round(spec.PIVOT_FIT_PACK_MAX / thou)
    assert trammel.PIVOT_SHIM_PACK == pytest.approx(pivot_shim.PER_SUPPORT * pivot_shim.THICKNESS)


def test_plain_pivot_radial_fits_are_not_interference_allowances() -> None:
    shaft_low = pivot_screw.SHOULDER_DIA + pivot_screw.SHOULDER_DIA_BAND[1]
    shaft_high = pivot_screw.SHOULDER_DIA + pivot_screw.SHOULDER_DIA_BAND[0]
    for diameter, band in (
        (carrier.PIN_HOLE_DIA, carrier.PIN_HOLE_BAND),
        (pivot_block.BORE_DIA, pivot_block.BORE_BAND),
    ):
        assert 0.0 < diameter + min(band) - shaft_high < diameter + max(band) - shaft_low
    assert pivot_spacer.ID + pivot_spacer.ID_BAND[1] >= shaft_high
    assert pivot_shim.ID + pivot_shim.ID_BAND[1] > shaft_high
    allowed = contracts.ALLOWED_PAIRS
    for family in PIVOT_FAMILIES:
        for index in range(PIVOT_FAMILIES[family]):
            name = spec.instance_name(family, index)
            actual = {pair for pair in allowed if name in pair}
            if family == spec.PIVOT_SCREW:
                block = spec.FEED_BLOCK if index == 0 else spec.PIVOT_BLOCK
                assert actual == {frozenset((name, spec.instance_name(block, 0)))}
            else:
                assert not actual


def test_feed_lug_nut_and_drilled_threads_stay_in_real_material() -> None:
    assert feed_block.LUG_X1 - feed_block.LUG_X0 == pytest.approx(feed_block.LUG_WIDTH)
    assert feed_block.LUG_Y1 == pytest.approx(-pivot_block.BLOCK_WIDTH / 2.0)
    # The round flange seats on the lug face within it (owner ruling
    # 2026-11-04, option B): between the carriage seat and the block top,
    # inside the lug's ends, at the leadscrew's worst offset.
    assert 0.0 <= feed_block.NUT_Z[0] < feed_block.NUT_Z[1] <= pivot_block.BLOCK_HEIGHT
    assert feed_block.LUG_Y0 <= feed_block.NUT_Y[0] < feed_block.NUT_Y[1] < feed_block.LUG_Y1
    # Rule 17: every tap-to-face wall meets the .080 target; the tap-to-
    # clearance wall is the stated shortfall, over the .060 floor.
    walls = dict(feed_block.LUG_WALLS_MM)
    clearance_wall = walls.pop("taps to the leadscrew clearance")
    assert min(walls.values()) >= WALL_TARGET_MM
    assert WALL_FLOOR_MM <= clearance_wall < WALL_TARGET_MM
    assert fasteners.NUT_TO_FEED_BLOCK.thread_depth_mm == feed_block.LUG_WIDTH
    assert feed_nut.SCREW_TIP_REACH_MAX < feed_block.LUG_WIDTH
    block_origin, rows = spec.FEED_BLOCK_PLACEMENTS[0]
    for placement, (y, z) in zip(spec.NUT_SCREW_PLACEMENTS, feed_block.NUT_HOLES_YZ, strict=True):
        origin, screw_rows = placement
        expected = _image(rows, block_origin, (
            feed_block.NUT_FACE_X + feed_nut.SCREW_GRIP, y, z,
        ))
        assert origin == pytest.approx(expected)
        # Bought heads point out of the lug; their -Y threaded shanks enter it.
        assert screw_rows[1] == pytest.approx(rows[0])
    for station in trammel.CARRIAGE_TRAVEL:
        low = station + feed_block.NUT_REACH_X[0]
        high = station + feed_block.NUT_REACH_X[1]
        for box in leadscrew.KP08_BOXES.values():
            assert max(box[0] - high, low - box[1]) >= leadscrew.FEED_GAP


def test_feed_nut_and_its_screws_hit_nothing_over_the_travel() -> None:
    # Swept along rail 1 over the whole carriage travel, the nut and its four
    # flat heads clear every stationary item but the leadscrew they thread,
    # and the carrier branch above them; the interference contract names
    # only those threads.
    gaps = spec.feed_nut_travel_gaps()
    # Each flat head's envelope is its head's diameter, the widest part.
    head = feed_nut.SCREW_DIMS.head_dia
    assert head > feed_nut.SCREW_DIMS.major_dia
    assert spec._component_local_boxes()[spec.RISER_SCREW][0] == pytest.approx((-head / 2.0, head / 2.0))
    assert {"pillow block 1", "end bracket 1", "base bar 1", "carrier"} <= set(gaps)
    assert not any(label.startswith("screw") for label in gaps)
    assert min(gaps.values()) > 0.0
    # The carrier branch is separated vertically from the conservative box
    # around the 45-degree turned nut flange. R4 has no projecting CL dowel.
    nut_top = leadscrew.SCREW_AXIS_Z + math.sqrt(2.0) * feed_nut.FLANGE_DIA_MAX / 2.0
    assert gaps["carrier"] == pytest.approx(trammel.CARRIER_UNDERSIDE_Z - nut_top)
    assert "CL dowel" not in gaps
    allowed = [pair for pair in contracts.ALLOWED_PAIRS if "@FeedNut:1" in pair]
    assert allowed == [frozenset(("@FeedNut:1", "@LeadScrew:1"))]
    screws = [
        pair for pair in contracts.ALLOWED_PAIRS
        if any(name in spec.NUT_SCREW_INSTANCES for name in pair)
    ]
    assert sorted(screws, key=sorted) == sorted((
        frozenset((name, f"{contracts._JIG}-feed-block-1")) for name in spec.NUT_SCREW_INSTANCES
    ), key=sorted)


def test_centred_branches_have_continuous_separating_axes() -> None:
    assert trammel.PIN_OFFSET == pivot_block.BORE_X == 0.0
    assert min(spec.CARRIAGE_PAIR_GAPS.values()) > 369.0
    assert min(spec.CENTRED_BLOCK_CLEARANCES.values()) > 0.0
    assert min(feed_block.FEED_GAPS_WORST.values()) >= leadscrew.FEED_GAP
    assert leadscrew.KP08_STUD_CLEARANCE_WORST > 0.0
    assert leadscrew.KP08_STATION_ENVELOPE > (
        leadscrew.BRACKET_STOP_FLOAT_MAX + leadscrew.KP08_SCREW_FLOAT_MAX
    )
    # The axial station uses the bracket's inch Y-row tolerance, not its
    # metric X-station band. Keep this leaf-side derivation synchronized
    # without importing end_bracket back into leadscrew_spec.
    assert leadscrew.BRACKET_AXIAL_ROW_BAND == pytest.approx(end_bracket._ROW_DEVIATION)
    assert leadscrew.KP08_STATION_ENVELOPE == pytest.approx(
        base_bar.BRACKET_STATION_BAND + leadscrew._KP08_STATION_ROUNDING
        + end_bracket._ROW_DEVIATION
        + leadscrew.BRACKET_STOP_FLOAT_MAX + leadscrew.KP08_SCREW_FLOAT_MAX
    )


@pytest.mark.parametrize("pass_name", ("inner", "outer"))
def test_swept_block_outlines_cover_integral_lug_and_plain_pivot(pass_name) -> None:
    for theta in spec.sweep_thetas(pass_name, samples=21):
        outlines = spec.moving_outlines(pass_name, theta)
        for rail, module, key in ((1, feed_block, "feed block"), (2, pivot_block, "pivot block 2")):
            points = [(x, y) for x in (module.BLOCK_X0, module.BLOCK_X1)
                      for y in (-module.BLOCK_WIDTH / 2.0, module.BLOCK_WIDTH / 2.0)]
            if rail == 1:
                points.extend((x, y) for x in (feed_block.LUG_X0, feed_block.LUG_X1)
                              for y in (feed_block.LUG_Y0, feed_block.LUG_Y1))
            family = spec.FEED_BLOCK if rail == 1 else spec.PIVOT_BLOCK
            placement = spec._swept_placement(family, 0, pass_name, theta)
            for x, y in points:
                assert _inside_xy(outlines[key], spec.frame_point(placement, (x, y, 0.0))[:2])


def _leadscrew_with(**bought: float) -> types.ModuleType:
    """Replay purchased dimensions in source, without moving drilled stations."""
    path = Path(leadscrew.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    remaining = set(bought)
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in bought:
                assert target.id in remaining, f"duplicate purchased dimension {target.id}"
                node.value = ast.Constant(value=bought[target.id])
                remaining.remove(target.id)
    assert not remaining, f"missing purchased dimension assignments: {remaining}"
    module = types.ModuleType("purchased_leadscrew_variant")
    module.__file__ = str(path)
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), module.__dict__)
    return module


def test_handwheel_vendor_swap_preserves_the_drilled_station_contract() -> None:
    # A longer hub (its guaranteed bore with it) moves only the wheel.
    variant = _leadscrew_with(HANDWHEEL_HUB_LENGTH=20.0)
    assert (variant.KP08_S, variant.BASE_BAR_HOLES, variant.SCREW_LENGTH) == (
        leadscrew.KP08_S, leadscrew.BASE_BAR_HOLES, leadscrew.SCREW_LENGTH,
    )
    assert variant.HANDWHEEL_BORE_LENGTH == 20.0
    assert variant.WHEEL_S[1] == pytest.approx(leadscrew.WHEEL_S[1] + 6.0)
    assert variant.HANDWHEEL_S[1] == pytest.approx(leadscrew.HANDWHEEL_S[1] + 6.0)


@pytest.mark.parametrize("bought, message", (
    ({"HANDWHEEL_GRUB_FROM_HUB": 14.5}, "short of the handwheel's grub or its flat"),
    ({"HANDWHEEL_GRUB_FROM_HUB": 17.0}, "short of the handwheel's grub or its flat"),
    ({"HANDWHEEL_HUB_LENGTH": 12.0}, "reaches past the handwheel's guaranteed bore"),
    ({"HANDWHEEL_BORE_LENGTH": 30.0}, "bore is not through its hub, inside the wheel"),
    ({"HANDWHEEL_LENGTH": 50.0}, "hub, rim and grip miss its length"),
))
def test_invalid_bought_handwheel_geometry_still_refuses_the_fit(bought, message) -> None:
    with pytest.raises(AssertionError, match=message):
        _leadscrew_with(**bought)


def test_stop_pins_govern_the_tooling_top_and_the_holding_check_prints_it() -> None:
    """R4: the uncut stock stop pins stand tallest over the strap, at full
    height; no CR-tallest claim survives."""
    pin_top = trammel.CARRIER_TOP_Z + spec.holding.STOP_PIN_HEIGHT_MAX
    assert spec.holding.STOP_PIN_HEIGHT_MAX > riser.STOP_PIN_TOP_LIMITS[1]
    assert spec.TOOLING_TOP_Z_MAX == spec.holding.TOOLING_TOP_Z_MAX >= pin_top
    assert pin_top > max(spec.holding.CLAMP_TOP_Z.values())
    # The stop pin's envelope is the supplier's maximum, uncut, tilted in its
    # loose hole: the holding proof's height and top float.
    box = spec._component_local_boxes()[spec.STOP_PIN]
    assert box[1] == (0.0, spec.holding.STOP_PIN_HEIGHT_MAX)
    assert box[0][1] == pytest.approx(
        riser.STOP_PIN_DIA_LIMITS[1] / 2.0 + spec.holding.STOP_PIN_TOP_FLOAT_MAX
    )
    washer = spec._component_local_boxes()[spec.HUB_WASHER]
    assert washer[2] == (-spec.hub_washer.SPIGOT_LENGTH, spec.hub_washer.THICK)
    assert "THE STOP PIN TOPS STAND TALLEST" in spec.REFERENCE_HEIGHTS
    assert f"FIXTURE TOP {spec._length(spec.TOOLING_TOP_Z_MAX, 3)} MAX" in spec.REFERENCE_HEIGHTS
    steps = {text.split(". ", 1)[0]: text for text in spec.OPERATION_STEPS}
    assert "BOTH STOP PINS AT FULL HEIGHT" in steps["17A"]
    # Q5 (Delegated ruling 2026-11-07 (Main), no precedent; owner review
    # #2144; pending owner confirmation): the washer clearance prints inch,
    # rounded up from the holding proof's minimum, every designed gap above it.
    printed = f"{spec._length(spec.WASHER_CLEARANCE_PRINTED, 3)} MIN"
    assert printed == ".060 MIN" and printed in steps["21B"]
    assert spec.WASHER_CLEARANCE_PRINTED >= spec.holding.WASHER_CLEARANCE_MIN
    assert min(spec.holding.WASHER_GAPS_MIN.values()) >= spec.WASHER_CLEARANCE_PRINTED


def test_hold_down_clearance_prints_on_the_safe_side_of_the_kit() -> None:
    """13A gauges the kit's stud clearance rounded up, so a passing setup
    passes the kit's."""
    assert spec.CLAMPING_KIT_NUMBER == _config.parts(spec.CLAMPING_KIT)["number"]
    assert float(spec._STUD_CLEARANCE) * 25.4 >= hold_down_stud.CLEARANCE_MIN


def test_every_alignment_station_is_reachable_by_both_carriages() -> None:
    """Steps 6 and HD3 bring each pin to every station: the feed carriage by
    the handwheel within its travel, both carriages wholly on their rails."""
    for station in trammel.ALIGNMENT_STATIONS:
        centre = station - trammel.PIN_OFFSET
        assert trammel.CARRIAGE_TRAVEL[0] <= centre <= trammel.CARRIAGE_TRAVEL[1]
        assert trammel.CARRIAGE_S_RANGE[0] <= centre <= trammel.CARRIAGE_S_RANGE[1]

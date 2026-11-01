"""Offline contract for the oblique-trammel jig assembly (MHA-CH-06-TL-00).

The poses close on the calculator's rail and carrier geometry and the leadscrew
feed's layout, the builder places all made and bought families,
one free DOF slides the carriages and their shoulder-screw pivot stacks,
the interference contracts cover only physical bond seats and threads, the jig stays
a shop fixture outside the machine tree, and both passes retain both carrier
ends while their full sweeps clear the table and column cover by pinned margins.
"""

from __future__ import annotations

import ast
import json
import math
import types
from pathlib import Path

import pytest
import yaml

import _buildgraph as bg
import _config
import _interference_contracts as contracts
from _inch_wall_limits import WALL_TARGET_MM
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as cl_dowel
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as handwheel
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import ch_rocker_arm_tl_vn_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as leadscrew_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as lever_washer
import ch_rocker_arm_tl_oblique_feed_block_spec as feed_block
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
import ch_rocker_arm_tl_vn_oblique_pivot_spacer_spec as pivot_spacer
import ch_rocker_arm_tl_vn_oblique_pivot_shim_spec as pivot_shim
import ch_rocker_arm_tl_oblique_riser_spec as riser
import sh_vn_clamping_kit_t_nut_spec as t_nut
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_jig_assembly as drawing


BUILDER = Path(__file__).with_name("build_ch_rocker_arm_tl_oblique_jig_assembly.py")
JIG = "ch_rocker_arm_tl_oblique_jig"
PART_STEMS = {
    physical.replace("-", "_")
    for physical, _configuration in spec.COMPONENT_IDENTITIES.values()
}
PIVOT_FAMILIES = {spec.PIVOT_SCREW: 2, spec.PIVOT_SPACER: 2, spec.PIVOT_SHIM: 10}
# Each screw family and its fastener-table row (count, callout, engagement).
SCREW_ROWS = {
    spec.RAIL_SCREW: fasteners.RAIL_TO_BAR,
    spec.BRACKET_SCREW: fasteners.BRACKET_TO_BAR,
    spec.CARRIAGE_SCREW: fasteners.BLOCK_TO_CARRIAGE,
    spec.PILLOW_BLOCK_SCREW: fasteners.KP08_TO_BRACKET,
    spec.NUT_SCREW: fasteners.NUT_TO_FEED_BLOCK,
    spec.RISER_SCREW: fasteners.RISER_TO_CARRIER,
    spec.CLAMP_SCREW: fasteners.CR_CLAMP,
    spec.LEVER_SCREW: fasteners.LEVER_TO_CARRIER,
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
    """One base bar part, twice: as saved under rail 1, turned over (180°
    about its long axis) under rail 2; each lies on the table, its slots on
    its studs and its tapped-through rail holes on its rail's axis."""
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
        # #290: the bar's 17.32 ends flush with the 440 rail within its band.
        far_s = trammel.RAIL_NEAR_S + trammel.BASE_BAR_LENGTH
        assert far[:2] == pytest.approx(trammel.rail_point(rail, far_s))
        assert abs(trammel.RAIL_FAR_S - far_s) < trammel.BASE_BAR_THICK_BAND
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


def test_carrier_riser_hub_pin_and_lever_close_on_the_carrier_frame() -> None:
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
    assert spec.HUB_PIN_ORIGIN[:2] == pytest.approx(hub)
    assert spec.HUB_PIN_TOP_Z - (trammel.CARRIER_TOP_Z + riser.THICKNESS) == pytest.approx(
        hub_pin.TIP_SET
    )
    assert spec.HUB_PIN_BOTTOM_Z == pytest.approx(trammel.CARRIER_UNDERSIDE_Z)
    riser_hub = _image(spec.RISER_ROWS, spec.RISER_ORIGIN, (*riser.HUB_HOLE, 0.0))
    assert riser_hub[:2] == pytest.approx(hub, rel=0.0, abs=1e-9)
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
    """Each TL-28 stands on bar 1's top at its KP08 station: its #6-32 pair
    straddles the screw axis, its two tapped holes land on the bar's
    counterbored #8 holes."""
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
        mid = sum(leadscrew.BRACKET_KP08_HOLES_X) / 2.0
        axis = _image(rows, origin, (mid, 0.0, leadscrew.BRACKET_THICK))
        assert axis[:2] == pytest.approx(leadscrew.point(s, leadscrew.SCREW_LATERAL))
        assert axis[2] == pytest.approx(leadscrew.KP08_BASE_Z)
        assert axis[2] + leadscrew.KP08_AXIS_HEIGHT == pytest.approx(
            leadscrew.SCREW_AXIS_Z
        )
        bracket_holes += [
            tuple(round(c, 9) for c in _image(rows, origin, (x, 0.0, 0.0))[:2])
            for x in leadscrew.BRACKET_BAR_HOLES_X
        ]
    assert [c for hole in sorted(bracket_holes) for c in hole] == pytest.approx(
        [c for hole in bar_holes for c in hole], abs=1e-6
    )


def test_feed_block_nut_seat_closes_on_the_leadscrew_axis() -> None:
    origin, rows = spec.FEED_BLOCK_PLACEMENTS[0]
    bore = _image(rows, origin, (
        feed_block.NUT_FACE_X, feed_block.NUT_AXIS_Y, feed_block.NUT_AXIS_Z,
    ))
    assert bore[:2] == pytest.approx(leadscrew.point(
        spec.CARRIAGE_STATION + feed_block.NUT_FACE_X, leadscrew.SCREW_LATERAL,
    ))
    assert bore[2] == pytest.approx(leadscrew.SCREW_AXIS_Z)
    assert feed_block.NUT_FACE_X == feed_block.LUG_X0
    assert feed_block.NUT_RECESS_DEPTH > leadscrew_nut.SPIGOT_LENGTH
    assert feed_block.NUT_SEAT_DIA > leadscrew_nut.BODY_DIA
    assert feed_block.SCREW_TAP_DEPTH == leadscrew.NUT_SCREW_TAP_DEPTH
    assert len(feed_block.NUT_HOLES_YZ) == 4
    for y, z in feed_block.NUT_HOLES_YZ:
        assert math.hypot(y - feed_block.NUT_AXIS_Y, z - feed_block.NUT_AXIS_Z) == pytest.approx(
            leadscrew.NUT_HOLE_PCD / 2.0
        )
        assert 0.0 < z < pivot_block.BLOCK_HEIGHT


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
        spec.BASE_BAR,
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
    second = spec.instance_name(family, 1)
    common = spec.explode_shift(family, "z")
    monkeypatch.setattr(
        spec, "EXPLODE_STEPS",
        (*spec.EXPLODE_STEPS, ("one kit occurrence", (first,), "z", 1.0)),
    )
    assert spec.explode_shift(first, "z") == pytest.approx(common + 1.0)
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
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "PLAN_VIEW_LABEL"
                for target in node.targets)
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
            "table structure must not move", (spec.BASE_BAR,), "z", 1.0,
        ))
    with pytest.raises(AssertionError, match="every occurrence"):
        _assert_explode_source_guards(steps)



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


def test_finished_locator_hole_fits() -> None:
    # F16: the bonded HUB pin never presses, and its gap stays within the
    # .0006 Loctite 638 fills.
    assert 0.0 <= carrier.HUB_BOND_CLEARANCE_MIN <= carrier.HUB_BOND_CLEARANCE_MAX
    assert carrier.HUB_BOND_CLEARANCE_MAX <= 0.0006 * 25.4 + 1e-9
    # F19: the CL dowel always presses into the carrier.
    low, high = carrier.CL_DOWEL_INTERFERENCE
    assert 0.0 < low <= high
    assert (low, high) == pytest.approx((
        min(carrier.CL_DOWEL_BAND) - max(carrier.CL_HOLE_BAND),
        max(carrier.CL_DOWEL_BAND) - min(carrier.CL_HOLE_BAND),
    ))


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
        spec.BASE_BAR: 2,
        spec.CARRIER: 1,
        spec.PIVOT_BLOCK: 1,
        spec.FEED_BLOCK: 1,
        **PIVOT_FAMILIES,
        spec.RISER: 1,
        spec.HUB_PIN: 1,
        spec.FEED_LEVER: 1,
        spec.END_BRACKET: 2,
        spec.RAIL: 2,
        spec.CARRIAGE: 2,
        spec.CL_DOWEL: 1,
        spec.LEADSCREW: 1,
        spec.LEADSCREW_NUT: 1,
        spec.PILLOW_BLOCK: 2,
        spec.HANDWHEEL: 1,
        spec.HOLD_DOWN_STUD: 4,
        spec.T_NUT: 4,
        spec.FLANGE_NUT: 4,
        spec.RAIL_SCREW: 14,
        spec.BRACKET_SCREW: 8,
        spec.CARRIAGE_SCREW: 8,
        spec.PILLOW_BLOCK_SCREW: 4,
        spec.NUT_SCREW: 4,
        spec.RISER_SCREW: 4,
        spec.CLAMP_SCREW: 1,
        spec.LEVER_SCREW: 2,
        spec.LEVER_LOCK_WASHER: 2,
    }
    assert sum(spec.QUANTITIES.values()) == 93
    assert spec.QUANTITIES[spec.END_BRACKET] == (leadscrew.END_BRACKET_QUANTITY)
    assert spec.QUANTITIES[spec.BASE_BAR] == base_bar.QUANTITY
    assert spec.QUANTITIES[spec.HOLD_DOWN_STUD] == fasteners.HOLD_DOWN_STUD_COUNT
    for stem, row in SCREW_ROWS.items():
        assert spec.QUANTITIES[stem] == row.count, stem
    # TL-20 remains unconfigured; heterogeneous kit members must be explicit.
    assert spec.COMPONENT_IDENTITIES[spec.BASE_BAR] == (spec.BASE_BAR, None)
    assert spec.KIT_IDENTITIES == {
        spec.HOLD_DOWN_STUD: ("sh-vn-clamping-kit-hardware", "HoldDownStud"),
        spec.T_NUT: ("sh-vn-clamping-kit-hardware", "TNut"),
        spec.FLANGE_NUT: ("sh-vn-clamping-kit-hardware", "FlangeNut"),
    }
    assert set(bg.references_of(JIG)) == PART_STEMS
    assert len(manifest) == len(spec.BOM_ORDER) == 30
    assert len(PART_STEMS) == 28


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
    assert len(expected) == 28


def test_kit_selectors_are_role_local_not_native_instance_indices() -> None:
    assert spec.instance_name(spec.BASE_BAR, 0) == spec.BASE_BAR + "-1"
    assert spec.KIT_COMPONENT_REFERENCES == {
        f"@{configuration}:{index}": (physical, configuration)
        for physical, configuration in spec.KIT_IDENTITIES.values()
        for index in range(1, 5)
    }
    for family, (physical, configuration) in spec.KIT_IDENTITIES.items():
        assert spec.QUANTITIES[family] == 4
        assert spec.component_family(physical, configuration) == family
    with pytest.raises(ValueError, match="no unique family"):
        spec.component_family(spec.CLAMPING_KIT, "Default")


@pytest.fixture
def kit_placement_scene(monkeypatch):
    import build_ch_rocker_arm_tl_oblique_jig_assembly as builder
    import _component_references as references

    components, batches = [], []
    model = types.SimpleNamespace(GetComponents=lambda _top_only: tuple(reversed(components)))
    adapter = types.SimpleNamespace(currentModel=model)

    async def batch(_adapter, rows, *, label):
        assert _adapter is adapter
        batches.append((label, rows))
        names = []
        for suffix, row in zip((41, 7, 103, 28), rows, strict=True):
            name = f"{row['part']}-{suffix + 200 * len(batches)}"
            components.append(types.SimpleNamespace(
                Name2=name,
                ComponentReference=row["component_reference"],
                ReferencedConfiguration=row["configuration"],
                GetPathName=lambda part=row["part"]: f"C:/native/{part}.SLDPRT",
            ))
            names.append(name)
        return names

    async def individual(*_args, **_kwargs):
        raise AssertionError("each kit member's four occurrences must remain batched")

    monkeypatch.setattr(builder, "place_components_batch", batch)
    monkeypatch.setattr(builder, "place_component", individual)
    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    return builder, adapter, components, batches


def _place_kit(scene):
    import asyncio

    builder, adapter, _components, _batches = scene
    names = {}
    for family, (physical, _configuration) in spec.KIT_IDENTITIES.items():
        names.update(asyncio.run(builder._place_family(adapter, physical, family)))
    return names


def test_builder_batches_each_member_with_explicit_native_identity(kit_placement_scene):
    builder, adapter, _components, batches = kit_placement_scene
    names = _place_kit(kit_placement_scene)
    assert len(names) == 12
    for family, rows in batches:
        physical, configuration = spec.KIT_IDENTITIES[family]
        assert len(rows) == 4
        for index, row in enumerate(rows):
            origin, rotation = spec.PLACEMENTS[family][index]
            assert row == {
                "part": physical,
                "position": list(origin),
                "rows": [list(axis) for axis in rotation],
                "ground": True,
                "configuration": configuration,
                "component_reference": f"{configuration}:{index + 1}",
            }
        offset = 200 * (list(spec.KIT_IDENTITIES).index(family) + 1)
        assert names[f"@{configuration}:1"] == f"{physical}-{41 + offset}"
        assert names[f"@{configuration}:4"] == f"{physical}-{28 + offset}"
    builder._verify_kit_references(adapter, names)


@pytest.mark.parametrize("fault", ("missing", "wrong-member", "duplicate-reference", "renamed"))
def test_final_kit_reference_readback_refuses_drift(kit_placement_scene, fault):
    builder, adapter, components, _batches = kit_placement_scene
    names = _place_kit(kit_placement_scene)
    if fault == "missing":
        components.pop()
    elif fault == "wrong-member":
        components[-1].ReferencedConfiguration = "HoldDownStud"
    elif fault == "duplicate-reference":
        components[-1].ComponentReference = components[-2].ComponentReference
    else:
        components[-1].Name2 = "unexpected-new-name-901"
    with pytest.raises(RuntimeError):
        builder._verify_kit_references(adapter, names)


def test_save_rechecks_kit_references_after_its_final_solve():
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
    assert gate.body.func.id == "_verify_kit_references"




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
    assert contract["allowed_free_stems"] == list(spec.MOVING)
    assert contract["required_free_stems"] == list(spec.MOVING)
    assert contract["flip_invert"] == []
    assert spec.SLIDE_KEY == "carriage_slide"
    assert set(spec.MOVING) == {spec.CARRIAGE, spec.CARRIER, *spec.LOCKED_TO}
    assert set(spec.MOVING) == {
        spec.CARRIER,
        spec.PIVOT_BLOCK,
        *PIVOT_FAMILIES,
        spec.RISER,
        spec.HUB_PIN,
        spec.FEED_LEVER,
        spec.FEED_BLOCK,
        spec.CARRIAGE,
        spec.CL_DOWEL,
        spec.LEADSCREW_NUT,
        spec.CARRIAGE_SCREW,
        spec.NUT_SCREW,
        spec.RISER_SCREW,
        spec.CLAMP_SCREW,
        spec.LEVER_SCREW,
        spec.LEVER_LOCK_WASHER,
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
        if all(parent == spec.CARRIER for parent, _index in parents)
    }
    assert riders == {
        spec.RISER,
        spec.HUB_PIN,
        spec.FEED_LEVER,
        spec.CL_DOWEL,
        spec.RISER_SCREW,
        spec.CLAMP_SCREW,
        spec.LEVER_SCREW,
        spec.LEVER_LOCK_WASHER,
    }
    for stem, parents in spec.LOCKED_TO.items():
        assert len(parents) == spec.QUANTITIES[stem]
        for index, (parent, parent_index) in enumerate(parents):
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
    overlap = min(trammel.CARRIER_TOP_Z, spec.HUB_PIN_TOP_Z) - max(
        trammel.CARRIER_UNDERSIDE_Z, spec.HUB_PIN_ORIGIN[2],
    )
    assert contracts.JIG_HUB_PIN_SEAT == pytest.approx((hub_pin.DIA, overlap))
    # The bond runs the whole carrier: cut = carrier + riser + tip set.
    assert overlap == pytest.approx(carrier.THICKNESS)
    assert contracts.JIG_CL_DOWEL_PRESS == (cl_dowel.DIA, carrier.THICKNESS)
    for envelope, expected in (
        (
            contracts.JIG_RAIL_SCREW_THREAD,
            _thread(fasteners.RAIL_TO_BAR, base_bar.TAP_DRILL),
        ),
        (
            contracts.JIG_BRACKET_SCREW_THREAD,
            _thread(fasteners.BRACKET_TO_BAR, end_bracket.BAR_TAP_DRILL),
        ),
        (
            contracts.JIG_CARRIAGE_SCREW_THREAD,
            _thread(fasteners.BLOCK_TO_CARRIAGE, carriage.BORE_DIA),
        ),
        (
            contracts.JIG_PILLOW_BLOCK_SCREW_THREAD,
            _thread(fasteners.KP08_TO_BRACKET, end_bracket.KP08_TAP_DRILL),
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
            contracts.JIG_CLAMP_SCREW_THREAD,
            _thread(fasteners.CR_CLAMP, carrier.CR_TAP_DRILL),
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
            contracts.JIG_LEADSCREW_NUT_THREAD,
            (leadscrew_stock.MAJOR_DIA, leadscrew_nut.BORE_DIA, leadscrew_nut.LENGTH),
        ),
    ):
        # The literals carry the thread majors to 4 places, the specs to 3.
        assert envelope == pytest.approx(expected, abs=1e-3)
    pairs = contracts.allowed_interference_pairs(spec.ASM_NAME)
    names = {
        spec.instance_name(stem, index)
        for stem, count in spec.QUANTITIES.items()
        for index in range(count)
    }
    assert all(pair <= names for pair in pairs)
    assert len(pairs) == 2 + sum(spec.QUANTITIES[s] for s in SCREW_ROWS) + 8 + 1 + 2
    seat = math.pi * hub_pin.DIA**2 * overlap / 4.0
    hub = frozenset((f"{spec.HUB_PIN}-1", f"{spec.CARRIER}-1"))
    assert pairs[hub] == pytest.approx(1.10 * seat)
    dowel = math.pi * cl_dowel.DIA**2 * carrier.THICKNESS / 4.0
    assert pairs[frozenset((f"{spec.CL_DOWEL}-1", f"{spec.CARRIER}-1"))] == (
        pytest.approx(1.10 * dowel)
    )
    inserted = (*SCREW_ROWS, spec.HOLD_DOWN_STUD, spec.LEADSCREW_NUT, spec.PIVOT_SCREW)
    occurrences = {
        spec.instance_name(family, index): (family, index)
        for family, count in spec.QUANTITIES.items()
        for index in range(count)
    }
    for pair in pairs:
        if pair == hub or spec.CL_DOWEL + "-1" in pair:
            continue
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
    for family, member in (
        (spec.HOLD_DOWN_STUD, hold_down_stud),
        (spec.T_NUT, t_nut),
        (spec.FLANGE_NUT, flange_nut),
    ):
        assert spec.BOM_DESCRIPTIONS[family] == member.BOM_DESCRIPTION


def test_bom_follows_the_part_registry() -> None:
    prefix = spec.DRAWING_NUMBER.rsplit("-", 1)[0] + "-"
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
        assert quantity == spec.QUANTITIES[stem], stem
        # VN records procurement, not absence of shop rework. Shared kit
        # registry properties stay common; HoldDownStud's native rework
        # properties are checked with its configured producer.
        assert (row["process"] == "purchased") == number.startswith(
            (prefix + "VN-", "MHA-SH-VN-")
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
    assert not ({JIG} | PART_STEMS) & reachable



def test_sweep_clears_the_column_cover(report) -> None:
    # The rail-bound items, computed independently here; every moving and
    # feed outline keeps the 100 mm floor to the cover below.
    expected = {}
    near = min(low for low, _high in trammel.END_STOPS.values())
    for rail in spec.RAILS:
        corners = [
            trammel.rail_point(rail, near + x, lateral)
            for x in (-carriage.LENGTH / 2.0 - carriage.NIPPLE_PROUD,
                      carriage.LENGTH / 2.0 + carriage.PLUG_PROUD)
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
        for along in (-carriage.LENGTH / 2.0 - carriage.NIPPLE_PROUD,
                      carriage.LENGTH / 2.0 + carriage.PLUG_PROUD)
        for lateral in (-carriage.WIDTH / 2.0, carriage.WIDTH / 2.0)
    ]
    assert report.moving_x == pytest.approx((
        min(x for x, _y in carriage_corners), max(x for x, _y in carriage_corners),
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
    assert report.fixed_x == pytest.approx((-463.04, 463.04), abs=0.01)
    assert report.fixed_y == pytest.approx((-115.33, 85.84), abs=0.01)
    assert report.bar_overhang == pytest.approx({1: 43.94, 2: 43.94}, abs=0.01)
    assert report.carriage_margin["inner"] == pytest.approx((61.52, 14.81), abs=0.01)
    assert report.carriage_margin["outer"] == pytest.approx((64.18, 2.93), abs=0.01)
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
        "inner": (244.404, 168.485, 92.215, 168.485, 244.404, 319.798, 394.492),
        "outer": (251.703, 173.471, 94.878, 173.471, 251.703, 329.395, 406.366),
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
            assert pose["carriages"] == {
                carriage_1: pytest.approx(list(spec.carriage_origin(1, stations[1]))),
                carriage_2: pytest.approx(list(spec.carriage_origin(2, stations[2]))),
            }
        # The sweep's ends put the carriages on the calculator's end stops.
        low, high = trammel.END_STOPS[pass_name]
        ends = (poses[2]["carriages"], poses[-1]["carriages"])
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
        assert passes["inner"]["poses"][0]["carriages"][name] == pytest.approx(
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
    # The feed block's body rides on the rail like pivot block 2, mirrored.
    block = edges["pivot block 2"]
    assert feed["feed block"]["-X end"] == pytest.approx(block["+X end"])
    assert feed["feed block"]["+X end"] == pytest.approx(block["-X end"])
    assert feed["feed block"]["front"] == pytest.approx(edges["pivot block 2"]["front"])
    assert min(
        margin["front"] for family, margin in feed.items() if family != "feed block"
    ) > 90.0


# Fastener table: (callout, count, engagement, protrusion). Protrusion is the
# screw's length past the grip less the receiving thread's depth; below zero,
# the screw stops inside the part (THRU tap) or short of the full thread
# (blind tap). Engagement is never more than the receiving thread's depth.
FASTENER_TABLE = {
    "RAIL_TO_BAR": ("#8-32 X 3/4 SHCS", 14, 9.35, 9.35 - trammel.BASE_BAR_THICK),  # tip short of the faced bar's underside
    "BRACKET_TO_BAR": (
        f"{leadscrew.BAR_SCREW} X {leadscrew.BAR_SCREW_LENGTH} SHCS", 8,
        leadscrew.BAR_SCREW_ENGAGEMENT,
        leadscrew.BAR_SCREW_ENGAGEMENT - leadscrew.BRACKET_THICK,
    ),
    "BLOCK_TO_CARRIAGE": (
        "M4 X 20 SHCS", 8,
        pivot_block.SCREW_REACH,
        pivot_block.SCREW_REACH - pivot_block.CARRIAGE_THREAD_DEPTH,
    ),
    "KP08_TO_BRACKET": ("#6-32 X 5/8 SHCS", 4, 10.875, -14.525),
    "NUT_TO_FEED_BLOCK": ("#4-40 X 1/2 BHCS", 4, 9.2, 9.2 - feed_block.SCREW_TAP_DEPTH),
    # The 5/8 screw past the riser grip (its head seated in the countersink);
    # the tip stops inside the carrier's THRU tap.
    "RISER_TO_CARRIER": (
        "#4-40 X 5/8 B18.6.3 FLAT HEAD", 4,
        0.625 * 25.4 - fasteners.RISER_TO_CARRIER.grip_mm,
        0.625 * 25.4 - fasteners.RISER_TO_CARRIER.grip_mm - carrier.THICKNESS,
    ),
    # Through the whole carrier tap; the bought 7/8 tip stands below it.
    "CR_CLAMP": (
        "1/4-20 X 7/8 SHCS", 1, carrier.THICKNESS,
        0.875 * 25.4 - fasteners.CR_CLAMP.grip_mm - carrier.THICKNESS,
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
    # Only the CR clamp, installed full length as bought, stands past its
    # THRU tap: into the free space between the carrier and the rail top.
    proud = [row for row in fasteners.FASTENERS if row.protrusion_mm > 0.0]
    assert proud == [fasteners.CR_CLAMP]
    assert fasteners.CR_CLAMP.tip_clearance_mm == trammel.CARRIER_TO_RAIL_GAP
    assert 0.0 < fasteners.CR_CLAMP.protrusion_mm < fasteners.CR_CLAMP.tip_clearance_mm
    # Counts follow the parts: 7 rail holes on each of 2 rails, a 4-hole
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
        fasteners.BLOCK_TO_CARRIAGE
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
    assert fasteners.WASHERS == (fasteners.LEVER_LOCK_WASHER,)
    # The nut screws' button heads sit directly on the flange (owner ruling
    # 2026-10-20: no washers).
    assert fasteners.NUT_TO_FEED_BLOCK.head == fasteners.BHCS
    assert fasteners.NUT_TO_FEED_BLOCK.grip_mm == pytest.approx(
        leadscrew.NUT_FLANGE_THICK
    )
    assert fasteners.LEVER_LOCK_WASHER.count == fasteners.LEVER_TO_CARRIER.count
    assert fasteners.LEVER_TO_CARRIER.grip_mm == pytest.approx(
        feed_lever.LEVER_THICK + fasteners.LEVER_LOCK_WASHER.thickness_mm
    )
    assert fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert fasteners.HOLD_DOWN_STUD_COUNT == 4


def test_carriage_screws_are_cut_to_fit_under_a_pending_owner_exception() -> None:
    """Owner ruling 2026-11-01 (option A): step 5 measures each counterbore
    floor and cuts each M4 x 20 to it; RV-05 accepts the 1.16D reach."""
    from _paths import CAD_ROOT
    from machinist_exceptions import load_exceptions

    step = next(text for text in spec.ASSEMBLY_STEPS if text.startswith("5. "))
    assert (
        "MEASURE EACH BLOCK'S 4 COUNTERBORE FLOOR HEIGHTS ABOVE ITS BOTTOM TO .001. "
        f"CUT EACH M4 X 20 SHCS {spec._item(spec.CARRIAGE_SCREW)} TO ITS OWN FLOOR "
        "HEIGHT + .189 (+/-.005) UNDER THE HEAD;"
    ) in step
    assert "EACH TIP ENGAGES .183-.195 OF THE CARRIAGE'S M4 X 5 AND NEVER BOTTOMS." in step
    entries = {
        entry.id: entry
        for entry in load_exceptions(CAD_ROOT / "config", "ch_rocker_arm_tl_oblique_jig_assembly", "assembly")
    }
    reach = entries["RV-05"]
    assert reach.kind == "accept"
    assert "+ .189" in reach.where and ".183-.195" in reach.where
    assert "1.16D" in reach.finding
    assert "pending confirmation" in reach.reason



def test_turned_over_bar_counterbores_clear_the_flange_nuts() -> None:
    # Bar 2 goes on turned over, so its 8 bracket counterbores face up, empty.
    # No flange nut seats over one, and the rail's footprint misses them.
    reach = flange_nut.FLANGE_DIA / 2.0 + base_bar.BRACKET_CBORE_DIA / 2.0
    studs = [c for name, c in spec.stud_centres().items() if name.endswith("2")]
    gaps = []
    for hole in leadscrew.BASE_BAR_HOLES:
        x, y, _ = spec.bar_point(2, (*hole, 0.0))
        gaps.append(min(math.hypot(x - c[0], y - c[1]) for c in studs) - reach)
        assert (
            abs(hole[1]) - base_bar.BRACKET_CBORE_DIA / 2.0 > trammel.RAIL_WIDTH / 2.0
        )
    # Ruling A′'s 8 holes: every counterbore stays clear of every flange nut's
    # seat (the near rows the closest, about 17.5).
    assert min(gaps) > 0.0


def test_bracket_bar_screws_sit_in_their_rule_17_window() -> None:
    # Ruling A′ (2026-10-17): two pairs about the screw axis, the outer
    # half-span inside the window between TL-28's #8-to-#6 wall and TL-20's
    # counterbore-to-edge wall, both at the rule-17 target at worst case.
    # #290 (option B): every bracket station prints as modelled at .XXX.
    laterals = leadscrew.BAR_SCREW_LATERALS
    axis = leadscrew.SCREW_LATERAL
    assert laterals == tuple(sorted(laterals))
    assert laterals[0] + laterals[3] == pytest.approx(2.0 * axis)
    assert laterals[1] + laterals[2] == pytest.approx(2.0 * axis)
    outer = axis - laterals[0]
    assert (
        leadscrew.BAR_SCREW_OUTER_HALF_SPAN_MIN
        <= outer
        <= leadscrew.BAR_SCREW_OUTER_HALF_SPAN_MAX
    )
    for lateral in laterals:
        tap = (lateral - leadscrew.BRACKET_INNER_LATERAL) / 25.4
        assert tap == pytest.approx(round(tap, 3), abs=1e-9)
    assert leadscrew.BRACKET_LENGTH == pytest.approx(
        trammel.BASE_BAR_COLUMN_EDGE - leadscrew.BRACKET_INNER_LATERAL
    )
    length = leadscrew.BRACKET_LENGTH / 25.4
    assert length == pytest.approx(round(length, 2), abs=1e-9)


def test_bracket_load_cases_hold_the_hand_abuse_thrust() -> None:
    # LOAD_CASES: 4 x #8 at 25 in-lbf on the 12.7-wide on-edge bracket, the
    # thrust at the raised axis Z52.4. Slip holds 1.5 x both the 1 kN
    # hand-abuse thrust and the 70 N-pull feed thrust; the heel may lift
    # elastically above the opening onset (owner ruling 2026-10-27).
    assert leadscrew.BAR_SCREW_TORQUE_NM == 2.8
    assert leadscrew.BAR_SCREW_PRELOAD == pytest.approx(3360.9, abs=0.1)
    assert leadscrew.BAR_SCREW_THRUST_ECCENTRICITY == pytest.approx(0.0)
    assert leadscrew.BRACKET_SLIP_THRUST == pytest.approx(2688.7, abs=0.1)
    assert leadscrew.BRACKET_OPENING_THRUST == pytest.approx(704.3, abs=0.1)
    assert leadscrew.BRACKET_SLIP_THRUST >= 1.5 * leadscrew.HAND_ABUSE_THRUST
    assert leadscrew.BRACKET_SLIP_THRUST >= 1.5 * spec.FEED_THRUST_N


@pytest.mark.parametrize(
    ("nm", "printed"),
    (
        (0.4, "0.4 N·m (3.5 IN·LBF)"),
        (2.8, "2.8 N·m (25 IN·LBF)"),
        (4.0, "4.0 N·m (35 IN·LBF)"),
        (19.2, "19.2 N·m (170 IN·LBF)"),
    ),
)
def test_printed_torque_leads_with_n_m_and_rounds_in_lbf(nm, printed) -> None:
    """Owner ruling 3 (2026-11-01): the N·m source value first, its in·lbf
    conversion in parentheses rounded to the nearest two significant figures."""
    assert spec._torque(nm) == printed
    in_lbf = float(printed.split("(", 1)[1].split(" ", 1)[0])
    exact = nm / (4.4482216152605 * 0.0254)
    half_step = 0.5 * 10 ** (math.floor(math.log10(exact)) - 1)
    assert abs(in_lbf - exact) <= half_step


def test_step_10_states_the_in_situ_hub_fit_up() -> None:
    """Owner ruling 5 (option A, 2026-11-01): TL-21 carries no HUB; step 10
    sets it from the spindle origin (the apex) by the carrier's printed
    offset and band, then names its size, band and mating part (rule 19)."""
    step = next(text for text in spec.ASSEMBLY_STEPS if text.startswith("10. "))
    assert "THE DRO READS X 0, Y .5123 ±.0005" in step
    assert "MATCH-DRILL AND REAM THE HUB THERE" in step
    hub_pin = f"(ITEM {spec.ITEM_NUMBERS[spec.HUB_PIN]})"
    assert f"HUB Ø.4000-.4005 THRU, BONDED LOCATOR {hub_pin}" in step
    assert "THEIR SPOTS" not in step and "THE CL HOLE OFF ITS SPOT" in step
    assert spec.carrier.HUB_RADIAL_STACK < 0.25




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


def test_nut_flange_is_a_static_clamp() -> None:
    # The nut's flange carries the nut's torque by clamp friction with margin,
    # so its 4 #4-40 screws see no operating torque; step 8 prints their
    # torque. Each button head bears directly on the brass flange (owner
    # ruling 2026-10-20), the owner's 0.4 N·m within what the tap and brass
    # carry.
    assert spec.NUT_SCREW_TORQUE_NM == 0.4
    assert spec.NUT_SCREW_PRELOAD_N == pytest.approx(703.0, abs=0.5)
    assert spec.NUT_SCREW_PRELOAD_N <= spec._NUT_SCREW_STRIP_N / 3.0
    # Nominal purchased flange envelope, not an invented drilled-pattern band.
    assert nut_screw.HEAD_DIA_MIN < nut_screw.DIMS.head_dia
    offset = nut_screw.HEAD_RUNOUT_FIM / 2.0
    ring_od = nut_screw.HEAD_DIA_MIN - 2.0 * offset
    flange_area = math.pi / 4.0 * (ring_od**2 - leadscrew_nut.HOLE_DIA**2)
    assert spec.NUT_SCREW_FLANGE_BEARING_MPA == pytest.approx(
        spec.NUT_SCREW_PRELOAD_N / flange_area
    )
    assert spec.NUT_SCREW_FLANGE_BEARING_MPA < spec._BRASS_YIELD_MPA
    assert spec.NUT_SCREW_PRELOAD_N <= spec._NUT_SCREW_PRELOAD_CAP_N
    # The screw: under half its 120 ksi on the #4-40 stress area.
    assert spec.NUT_SCREW_PRELOAD_N / (0.00604 * 25.4**2) < 0.5 * 827.4
    assert spec.NUT_FLANGE_SLIP_MARGIN >= leadscrew.SLIP_MARGIN_MIN


def test_nut_screw_heads_seat_flat_on_the_flange() -> None:
    # Nominal bought geometry only; actual drill-to-print fit is checked at assembly.
    assert spec.NUT_SCREW_FILLET_MARGIN == pytest.approx(
        leadscrew_nut.HOLE_DIA / 2.0
        - nut_screw.FILLET_DIA_MAX / 2.0
    )
    head_reach = (
        nut_screw.DIMS.head_dia / 2.0
        + nut_screw.HEAD_RUNOUT_FIM / 2.0
    )
    assert head_reach + spec.NUT_SCREW_HEAD_TO_BODY == pytest.approx(
        (leadscrew_nut.HOLE_PCD - leadscrew_nut.BODY_DIA) / 2.0
    )


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
    assert round(spec.PIVOT_FIT_PACK_MAX / thou) in packs
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
    allowed = contracts.allowed_interference_pairs(spec.ASM_NAME)
    for family in PIVOT_FAMILIES:
        for index in range(PIVOT_FAMILIES[family]):
            name = spec.instance_name(family, index)
            actual = {pair for pair in allowed if name in pair}
            if family == spec.PIVOT_SCREW:
                block = spec.FEED_BLOCK if index == 0 else spec.PIVOT_BLOCK
                assert actual == {frozenset((name, spec.instance_name(block, 0)))}
            else:
                assert not actual


def test_feed_lug_flange_and_drilled_threads_stay_in_real_material() -> None:
    assert feed_block.LUG_X1 - feed_block.LUG_X0 == pytest.approx(feed_block.LUG_WIDTH)
    assert feed_block.LUG_Y1 == pytest.approx(-pivot_block.BLOCK_WIDTH / 2.0)
    radius = leadscrew_nut.FLANGE_DIA / 2.0
    # The flange lands wholly on the lug face: above the carriage seat, below
    # the block top and inside the lug's -Y end with a wall's margin.
    assert feed_block.NUT_AXIS_Z - radius > 0.0
    assert feed_block.NUT_AXIS_Z + radius < pivot_block.BLOCK_HEIGHT
    assert feed_block.NUT_AXIS_Y - radius - feed_block.LUG_Y0 >= WALL_TARGET_MM
    assert fasteners.NUT_TO_FEED_BLOCK.thread_depth_mm == feed_block.SCREW_TAP_DEPTH
    assert feed_block.NUT_FACE_X + feed_block.SCREW_TAP_DEPTH < feed_block.LUG_X1
    block_origin, rows = spec.FEED_BLOCK_PLACEMENTS[0]
    for placement, (y, z) in zip(spec.NUT_SCREW_PLACEMENTS, feed_block.NUT_HOLES_YZ, strict=True):
        origin, screw_rows = placement
        expected = _image(rows, block_origin, (
            feed_block.NUT_FACE_X - leadscrew_nut.FLANGE_THICK, y, z,
        ))
        assert origin == pytest.approx(expected)
        # Bought heads point out of the lug; their -Y threaded shanks enter it.
        assert screw_rows[1] == pytest.approx(tuple(-value for value in rows[0]))
    for station in trammel.CARRIAGE_TRAVEL:
        low = station + feed_block.NUT_REACH_X[0]
        high = station + feed_block.NUT_REACH_X[1]
        for box in leadscrew.KP08_BOXES.values():
            assert max(box[0] - high, low - box[1]) >= leadscrew.FEED_GAP


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
    variant = _leadscrew_with(
        HANDWHEEL_HUB_LENGTH=20.0, HANDWHEEL_BORE_LENGTH=32.0, HANDWHEEL_LENGTH=53.0,
    )
    assert (variant.KP08_S, variant.BASE_BAR_HOLES, variant.SCREW_LENGTH) == (
        leadscrew.KP08_S, leadscrew.BASE_BAR_HOLES, leadscrew.SCREW_LENGTH,
    )
    assert variant.WHEEL_S[1] == pytest.approx(leadscrew.WHEEL_S[1] + 7.0)
    assert variant.HANDWHEEL_S[1] == pytest.approx(leadscrew.HANDWHEEL_S[1] + 7.0)


@pytest.mark.parametrize("bought, message", (
    ({"HANDWHEEL_GRUB_FROM_HUB": 14.5}, "short of the handwheel's grub or its flat"),
    ({"HANDWHEEL_GRUB_FROM_HUB": 17.0}, "short of the handwheel's grub or its flat"),
    ({"HANDWHEEL_HUB_LENGTH": 2.0, "HANDWHEEL_BORE_LENGTH": 14.0, "HANDWHEEL_LENGTH": 35.0},
     "proud of the wheel's outer face"),
    ({"HANDWHEEL_GRIP_LENGTH": 20.0}, "hub, rim and grip miss its length"),
))
def test_invalid_bought_handwheel_geometry_still_refuses_the_fit(bought, message) -> None:
    with pytest.raises(AssertionError, match=message):
        _leadscrew_with(**bought)


def test_bonded_gauge_locator_uses_the_finished_hub_bore_and_actual_cut_overlap() -> None:
    # The .4000 NO-GO gauge in the carrier's .4000-.4005 reamed HUB hole.
    assert hub_pin.DIA + max(hub_pin.DIA_BAND) == pytest.approx(
        carrier.HUB_HOLE_LIMITS[0]
    )
    assert hub_pin.BOND == "Loctite 638"
    low, high = carrier.HUB_HOLE_LIMITS
    clearance = (low - (hub_pin.DIA + max(hub_pin.DIA_BAND)),
                 high - (hub_pin.DIA + min(hub_pin.DIA_BAND)))
    assert clearance == pytest.approx(
        (carrier.HUB_BOND_CLEARANCE_MIN, carrier.HUB_BOND_CLEARANCE_MAX)
    )
    assert spec.HUB_PIN_TOP_Z - (trammel.CARRIER_TOP_Z + trammel.RISER_THICK) == pytest.approx(hub_pin.TIP_SET)
    assert spec.HUB_PIN_TOP_Z - spec.HUB_PIN_ORIGIN[2] == pytest.approx(hub_pin.CUT_LENGTH)
    overlap = min(trammel.CARRIER_TOP_Z, spec.HUB_PIN_TOP_Z) - max(
        trammel.CARRIER_UNDERSIDE_Z, spec.HUB_PIN_ORIGIN[2],
    )
    assert overlap == pytest.approx(contracts.JIG_HUB_PIN_SEAT[1])


def test_hold_down_inch_limits_lie_on_the_safe_side_of_the_kit_limits() -> None:
    """HD2 checks with the kit's mm stud limits printed in inch: LMIN low,
    LMAX high and the clearance high, so a passing setup passes the kit's."""
    assert spec.CLAMPING_KIT_NUMBER == _config.parts(spec.CLAMPING_KIT)["number"]
    low, high = (float(text) * 25.4 for text in spec._STUD_LIMITS.split("/"))
    assert low <= hold_down_stud.LENGTH - hold_down_stud.LENGTH_BAND
    assert high >= hold_down_stud.LENGTH + hold_down_stud.LENGTH_BAND
    assert float(spec._STUD_CLEARANCE) * 25.4 >= hold_down_stud.CLEARANCE_MIN


def test_every_alignment_station_is_reachable_by_both_carriages() -> None:
    """Steps 6 and HD3 bring each pin to every station: the feed carriage by
    the handwheel within its travel, both carriages wholly on their rails."""
    for station in trammel.ALIGNMENT_STATIONS:
        centre = station - trammel.PIN_OFFSET
        assert trammel.CARRIAGE_TRAVEL[0] <= centre <= trammel.CARRIAGE_TRAVEL[1]
        assert trammel.CARRIAGE_S_RANGE[0] <= centre <= trammel.CARRIAGE_S_RANGE[1]

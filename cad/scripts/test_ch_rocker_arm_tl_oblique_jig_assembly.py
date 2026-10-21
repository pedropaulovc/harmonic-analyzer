"""Offline contract for the oblique-trammel jig assembly (MHA-CH-06-TL-00).

The poses close on the calculator's rail and carrier geometry and the leadscrew
feed's layout, the builder places all thirty-seven made and bought families,
one free DOF slides the carriages and their positively captured pivot stacks,
the interference contracts are the specs' press fits and threads, the jig stays
a shop fixture outside the machine tree, and both passes retain both carrier
ends while their full sweeps clear the table and column cover by pinned margins.
"""

from __future__ import annotations

import ast
import json
import math
import re
import types
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest
import yaml

import _buildgraph as bg
import _config
import _interference_contracts as contracts
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_vn_oblique_bearing_spec as bearing
import ch_rocker_arm_tl_vn_oblique_block_washer_spec as block_washer
import ch_rocker_arm_tl_vn_oblique_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_vn_oblique_cl_dowel_spec as cl_dowel
import ch_rocker_arm_tl_vn_oblique_clamp_screw_spec as clamp_screw
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as handwheel
import sh_vn_clamping_kit_hold_down_stud_spec as hold_down_stud
import ch_rocker_arm_tl_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as leadscrew_nut
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_vn_oblique_leadscrew_stock_spec as leadscrew_stock
import ch_rocker_arm_tl_vn_oblique_lever_washer_spec as lever_washer
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_vn_oblique_nut_screw_spec as nut_screw
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_pivot_retainer_spec as pivot_retainer
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_retention_hardware_spec as retention_hardware
import ch_rocker_arm_tl_oblique_tooling_clearance_spec as tooling
import ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec as pivot_cotter
import ch_rocker_arm_tl_vn_oblique_pivot_lock_wire_spec as pivot_wire
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
CAPTURE_FAMILIES = {
    spec.PIVOT_CAP: 2,
    spec.PIVOT_RETAINER: 2,
    spec.PIVOT_CAP_SCREW: 8,
    spec.PIVOT_CLEVIS_PIN: 2,
    spec.PIVOT_COTTER: 2,
    spec.PIVOT_LOCK_WIRE: 4,
}
# Each screw family and its fastener-table row (count, callout, engagement).
SCREW_ROWS = {
    spec.RAIL_SCREW: fasteners.RAIL_TO_BAR,
    spec.BRACKET_SCREW: fasteners.BRACKET_TO_BAR,
    spec.BLOCK_SCREW: fasteners.NUT_BRACKET_TO_BLOCK,
    spec.CARRIAGE_SCREW: fasteners.BLOCK_TO_CARRIAGE,
    spec.PILLOW_BLOCK_SCREW: fasteners.KP08_TO_BRACKET,
    spec.NUT_SCREW: fasteners.NUT_TO_NUT_BRACKET,
    spec.RISER_SCREW: fasteners.RISER_TO_CARRIER,
    spec.CLAMP_SCREW: fasteners.CR_CLAMP,
    spec.LEVER_SCREW: fasteners.LEVER_TO_CARRIER,
    spec.PIVOT_CAP_SCREW: fasteners.CAP_TO_BLOCK,
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
        assert far[:2] == pytest.approx(trammel.rail_point(rail, trammel.RAIL_FAR_S))
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


def test_pivot_blocks_and_pins_sit_on_the_pin_stations() -> None:
    assert spec.PIN_STATION == pytest.approx(trammel.SYMMETRIC_PIN_STATION["inner"])
    assert spec.CARRIAGE_STATION - spec.PIN_STATION == pytest.approx(
        -trammel.PIN_OFFSET
    )
    for rail, (origin, rows), pin_origin, pin in zip(
        spec.RAILS,
        spec.PIVOT_BLOCK_PLACEMENTS,
        spec.PIVOT_PIN_ORIGINS,
        trammel.pin_pair("inner"),
    ):
        assert origin[2] == trammel.CARRIAGE_TOP_Z
        bore = _image(rows, origin, (pivot_block.BORE_X, 0.0, 0.0))
        assert bore[:2] == pytest.approx(trammel.rail_point(rail, spec.PIN_STATION))
        assert bore[:2] == pytest.approx(pin_origin[:2])
        assert pin_origin[:2] == pytest.approx(spec.POSE.to_machine(pin))
        assert pin_origin[2] == trammel.CARRIAGE_TOP_Z + trammel.BEARING_RECESS
    assert spec.PIN_TOP_Z == pytest.approx(
        trammel.CARRIER_UNDERSIDE_Z + pivot_pin.CARRIER_LENGTH
    )
    assert trammel.CARRIER_UNDERSIDE_Z == pytest.approx(
        trammel.PIVOT_BLOCK_TOP_Z + trammel.PIN_COLLAR_PROUD
    )
    assert trammel.CARRIER_TOP_Z - trammel.CARRIER_UNDERSIDE_Z == pytest.approx(
        trammel.CARRIER_THICK
    )
    assert spec.PART_TOP_Z - trammel.CARRIER_TOP_Z == pytest.approx(
        trammel.RISER_THICK + trammel.STRAP_THICK
    )
    assert spec.PIN_TOP_Z - spec.PART_TOP_Z == pytest.approx(
        retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL
    )
    assert retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL == pytest.approx(4.0)


def test_carrier_riser_hub_pin_and_lever_close_on_the_carrier_frame() -> None:
    def on_carrier(point):
        return _image(
            spec.CARRIER_ROWS, spec.CARRIER_ORIGIN, (point[0], 0.0, -point[1])
        )

    assert spec.THETA == 0.0 and spec.POSE.rotation == 0.0
    assert spec.CARRIER_ROWS[1] == pytest.approx((0.0, 0.0, 1.0))
    for hole, pin_origin in zip(trammel.pin_pair("inner"), spec.PIVOT_PIN_ORIGINS):
        machine = on_carrier(hole)
        assert machine[:2] == pytest.approx(pin_origin[:2])
        assert machine[2] == trammel.CARRIER_TOP_Z
    hub = spec.POSE.to_machine(trammel.HUB)
    assert spec.HUB_PIN_ORIGIN[:2] == pytest.approx(hub)
    assert spec.HUB_HEAD_BOTTOM_Z + hub_pin.HEAD_LENGTH == trammel.CARRIER_UNDERSIDE_Z
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


def test_nut_bracket_hangs_on_pivot_block_1_round_the_screw() -> None:
    """TL-29 takes pivot block 1's axes, flat on the block's column-side (-Y)
    face: its tapped pair lands on the block's counterbored #8 pair and its nut
    bore on the screw axis at the carriage."""
    block_origin, block_rows = spec.PIVOT_BLOCK_PLACEMENTS[leadscrew.RAIL - 1]
    for row, block_row in zip(spec.NUT_BRACKET_ROWS, block_rows, strict=True):
        assert row == pytest.approx(block_row)
    face = -pivot_block.BLOCK_WIDTH / 2.0
    assert leadscrew.BLOCK_SIDE_LATERAL == -face
    for x, z in leadscrew.PIVOT_BLOCK_HOLES:
        on_block = _image(block_rows, block_origin, (x, face, z))
        on_bracket = _image(
            spec.NUT_BRACKET_ROWS,
            spec.NUT_BRACKET_ORIGIN,
            (x, 0.0, leadscrew.NUT_BRACKET_BLOCK_HOLES_Z),
        )
        assert on_bracket == pytest.approx(on_block)
    bore = _image(
        spec.NUT_BRACKET_ROWS, spec.NUT_BRACKET_ORIGIN, (0.0, *leadscrew.NUT_BORE_YZ)
    )
    assert bore[:2] == pytest.approx(
        leadscrew.point(spec.CARRIAGE_STATION, leadscrew.SCREW_LATERAL)
    )
    assert bore[2] == pytest.approx(leadscrew.SCREW_AXIS_Z)
    # The bore runs along the rail: the screw's direction.
    along = _image(spec.NUT_BRACKET_ROWS, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    assert along[:2] == pytest.approx(spec.rail_rows(leadscrew.RAIL)[0][:2])
    assert spec.NUT_BRACKET_ORIGIN[2] == leadscrew.NUT_BRACKET_BOTTOM_Z
    # The wider spindle-end wing changes the real -X datum, not the original
    # side-hole axes or nut-bracket location. Step 7C must follow that datum.
    centre = pivot_block.DATUM_X + nut_bracket.X_SET_MID
    assert centre == pytest.approx(sum(pivot_block.SIDE_SCREW_X) / 2.0)
    assert centre == pytest.approx(sum(leadscrew.NUT_BRACKET_X) / 2.0)
    spotting = next(step for step in spec.ASSEMBLY_STEPS if step.startswith("7C."))
    assert f"CENTRE {nut_bracket.X_SET_MID:.{nut_bracket.X_SET_PLACES}f}" in spotting


def test_explode_stands_every_layer_clear_and_in_sight() -> None:
    assert spec.EXPLODED_VIEW_NAME == "JIG_EXPLODED"
    for _label, families, axis, distance in spec.EXPLODE_STEPS:
        assert set(families) <= set(spec.QUANTITIES)
        assert axis in {"x", "y", "z"} and distance != 0.0
    moved = {
        family
        for _label, families, _axis, _d in spec.EXPLODE_STEPS
        for family in families
    }
    # The frame stays: the bars, the rails and end brackets screwed to
    # them, the screw in its KP08s and the studs; the nut bracket lifts with
    # pivot block 1, which it is bolted to.
    assert set(spec.EXPLODE_STATIC) == {
        spec.BASE_BAR,
        spec.END_BRACKET,
        spec.RAIL,
        spec.LEADSCREW,
        spec.PILLOW_BLOCK,
        spec.HOLD_DOWN_STUD,
    }
    assert moved == set(spec.QUANTITIES) - set(spec.EXPLODE_STATIC)
    lift = {family: spec.explode_shift(family, "z") for family in spec.QUANTITIES}
    assert lift == {
        **dict.fromkeys(spec.EXPLODE_STATIC, 0.0),
        spec.HANDWHEEL: 0.0,
        spec.T_NUT: -30.0,
        spec.BRACKET_SCREW: -40.0,
        spec.RAIL_SCREW: 35.0,
        spec.PILLOW_BLOCK_SCREW: 40.0,
        spec.CARRIAGE: 50.0,
        spec.BEARING: 55.0,
        spec.FLANGE_NUT: 60.0,
        spec.HUB_PIN: 80.0,
        # The CL dowel goes down through the riser (step 11), so it lifts out
        # above the lifted riser, as the clamp screw does.
        spec.CL_DOWEL: 330.0,
        spec.PIVOT_BLOCK: 90.0,
        spec.NUT_BRACKET: 90.0,
        spec.LEADSCREW_NUT: 90.0,
        spec.BLOCK_SCREW: 90.0,
        spec.NUT_SCREW: 90.0,
        spec.BLOCK_LOCK_WASHER: 90.0,
        spec.PIVOT_CAP: 220.0,
        spec.PIVOT_CAP_SCREW: 250.0,
        spec.PIVOT_LOCK_WIRE: 260.0,
        spec.PIVOT_RETAINER: 260.0,
        spec.PIVOT_CLEVIS_PIN: 260.0,
        spec.PIVOT_COTTER: 260.0,
        spec.PIVOT_PIN: 150.0,
        spec.CARRIAGE_SCREW: 150.0,
        spec.CARRIER: 230.0,
        spec.RISER: 290.0,
        spec.FEED_LEVER: 290.0,
        spec.LEVER_LOCK_WASHER: 310.0,
        spec.RISER_SCREW: 320.0,
        spec.CLAMP_SCREW: 330.0,
        spec.LEVER_SCREW: 330.0,
    }
    # Sideways only where a part leaves sideways: rail 1 runs along -X, so the
    # nut screws back out along +X and the handwheel slides off along -X; the
    # block screws back out of pivot block 1's -Y face; the wedge-lock pairs
    # halfway out to the heads.
    sideways = {
        (family, axis): spec.explode_shift(family, axis)
        for family in spec.QUANTITIES
        for axis in "xy"
        if spec.explode_shift(family, axis)
    }
    assert sideways == {
        (spec.NUT_SCREW, "x"): 30.0,
        (spec.BLOCK_SCREW, "y"): -40.0,
        (spec.BLOCK_LOCK_WASHER, "y"): -20.0,
        (spec.HANDWHEEL, "x"): -50.0,
        (spec.PIVOT_CLEVIS_PIN, "x"): 40.0,
        (spec.PIVOT_COTTER, "x"): 40.0,
        (spec.PIVOT_COTTER, "y"): 40.0,
        (spec.PIVOT_LOCK_WIRE, "y"): 40.0,
    }
    # The stack in fitting order, bottom up (machine Z, mm).
    block_top = trammel.PIVOT_BLOCK_TOP_Z + lift[spec.PIVOT_BLOCK]
    pin = (spec.PIN_BOTTOM_Z, spec.PIN_TOP_Z)
    pin = tuple(z + lift[spec.PIVOT_PIN] for z in pin)
    underside = trammel.CARRIER_UNDERSIDE_Z + lift[spec.CARRIER]
    hub_top = spec.HUB_PIN_TOP_Z + lift[spec.HUB_PIN]
    assert pin[0] > block_top  # each pin out of its block
    # In sight under the carrier: each gap beats the part's plan distance to
    # the carrier's -Y edge (the isometric's 45° sight line).
    assert underside - pin[1] > -carrier.OUTLINE_Y[0]
    assert underside - hub_top > trammel.HUB[1] - carrier.OUTLINE_Y[0]
    assert spec.HUB_HEAD_BOTTOM_Z + lift[spec.HUB_PIN] > trammel.BASE_BAR_THICK
    # Service removes the cap before pressing a pin upward from its lower end;
    # the HUB pin still leaves downward from the carrier.
    hub_steps = [d for _l, fams, _a, d in spec.EXPLODE_STEPS if fams == (spec.HUB_PIN,)]
    pin_steps = [
        d for _l, fams, _a, d in spec.EXPLODE_STEPS if fams == (spec.PIVOT_PIN,)
    ]
    assert hub_steps == [-150.0] and pin_steps == [60.0]


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


def test_finished_hole_fits_and_bracket_end_wall() -> None:
    assert hub_pin.SHOULDER_FILLET_RADIUS <= hub_pin.HUB_HOLE_UNDERSIDE_BREAK_MIN
    assert nut_bracket.X_SET_BAND == pytest.approx(0.13)
    assert nut_bracket.END_WALL_MIN == pytest.approx(1.544, abs=0.001)
    assert hub_pin.HUB_HOLE_BAND == (0.018, 0.0)
    assert (carrier.CL_HOLE_BAND, carrier.CL_DOWEL_BAND) == (
        (-0.004, -0.016),
        (0.012, 0.004),
    )


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
    for name, origin in zip(("A1", "B1"), spec.PIVOT_PIN_ORIGINS):
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
        spec.PIVOT_BLOCK: 2,
        spec.PIVOT_PIN: 2,
        spec.RISER: 1,
        spec.HUB_PIN: 1,
        spec.FEED_LEVER: 1,
        spec.END_BRACKET: 2,
        spec.NUT_BRACKET: 1,
        spec.PIVOT_CAP: 2,
        spec.PIVOT_RETAINER: 2,
        spec.RAIL: 2,
        spec.CARRIAGE: 2,
        spec.BEARING: 4,
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
        spec.BLOCK_SCREW: 2,
        spec.CARRIAGE_SCREW: 8,
        spec.PILLOW_BLOCK_SCREW: 4,
        spec.NUT_SCREW: 4,
        spec.RISER_SCREW: 4,
        spec.CLAMP_SCREW: 1,
        spec.LEVER_SCREW: 2,
        spec.BLOCK_LOCK_WASHER: 2,
        spec.LEVER_LOCK_WASHER: 2,
        spec.PIVOT_CAP_SCREW: 8,
        spec.PIVOT_CLEVIS_PIN: 2,
        spec.PIVOT_COTTER: 2,
        spec.PIVOT_LOCK_WIRE: 4,
    }
    assert sum(spec.QUANTITIES.values()) == 110
    assert spec.QUANTITIES[spec.END_BRACKET] == (leadscrew.END_BRACKET_QUANTITY)
    assert spec.QUANTITIES[spec.NUT_BRACKET] == leadscrew.NUT_BRACKET_QUANTITY
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
    assert len(manifest) == len(spec.BOM_ORDER) == 37
    assert len(PART_STEMS) == 35


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
    assert len(expected) == 35


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


def test_capture_inventory_has_native_parts_and_cartridge_lock_parents() -> None:
    parents = {
        spec.PIVOT_CAP: (spec.PIVOT_BLOCK, 1),
        spec.PIVOT_RETAINER: (spec.PIVOT_PIN, 1),
        spec.PIVOT_CAP_SCREW: (spec.PIVOT_CAP, 4),
        spec.PIVOT_CLEVIS_PIN: (spec.PIVOT_PIN, 1),
        spec.PIVOT_COTTER: (spec.PIVOT_CLEVIS_PIN, 1),
        spec.PIVOT_LOCK_WIRE: (spec.PIVOT_CAP, 2),
    }
    numbers = {
        spec.PIVOT_CAP: "MHA-CH-06-TL-30",
        spec.PIVOT_RETAINER: "MHA-CH-06-TL-31",
        spec.PIVOT_CAP_SCREW: "MHA-CH-06-TL-VN-73",
        spec.PIVOT_CLEVIS_PIN: "MHA-CH-06-TL-VN-74",
        spec.PIVOT_COTTER: "MHA-CH-06-TL-VN-75",
        spec.PIVOT_LOCK_WIRE: "MHA-CH-06-TL-VN-76",
    }
    parts = _builder_parts()
    for family, count in CAPTURE_FAMILIES.items():
        assert parts.count((family, family)) == 1
        assert spec.QUANTITIES[family] == len(spec.PLACEMENTS[family]) == count
        assert spec.LOCKED_TO[family] == parents[family]
        parent, per_parent = parents[family]
        assert count == spec.QUANTITIES[parent] * per_parent
        for index in range(count):
            assert spec.lock_parent(family, index) == spec.instance_name(
                parent, index // per_parent
            )
        row = _config.parts(family)
        assert row["number"] == numbers[family]
        assert row["quantity"] == count
    made_start = spec.BOM_ORDER.index(spec.NUT_BRACKET) + 1
    assert spec.BOM_ORDER[made_start:made_start + 3] == (
        spec.PIVOT_CAP, spec.PIVOT_RETAINER, spec.RAIL
    )
    assert spec.BOM_ORDER[-5:] == (
        spec.LEVER_LOCK_WASHER, spec.PIVOT_CAP_SCREW, spec.PIVOT_CLEVIS_PIN,
        spec.PIVOT_COTTER, spec.PIVOT_LOCK_WIRE,
    )


@pytest.mark.parametrize("pass_name", ("inner", "outer"))
def test_both_pass_pairs_keep_both_complete_capture_stacks(pass_name: str) -> None:
    mates = spec.PIN_MATES[pass_name]
    assert len(mates) == 2
    assert {pin for _label, _hole, pin in mates} == {0, 1}
    assert {hole for _label, hole, _pin in mates} == (
        {"A1", "B1"} if pass_name == "inner" else {"A2", "B2"}
    )
    for _label, _hole, pin in mates:
        for family, total in CAPTURE_FAMILIES.items():
            for index in range(pin * (total // 2), (pin + 1) * (total // 2)):
                ancestor = family
                instance = index
                while ancestor in spec.LOCKED_TO:
                    parent, per_parent = spec.LOCKED_TO[ancestor]
                    assert parent != spec.CARRIER
                    instance //= per_parent
                    ancestor = parent
                assert ancestor == spec.CARRIAGE
                assert instance == pin
    # Re-mating changes the carrier holes, never removes either cartridge's
    # retainer/clevis/cotter or safety-wired cap from the moving inventory.
    assert set(CAPTURE_FAMILIES) <= set(spec.MOVING)
    sweep = trammel.SWEEP[pass_name]
    for theta in (-sweep, 0.0, sweep):
        pose = trammel.carrier_pose(pass_name, theta)
        stations = spec.carriage_stations(pass_name, theta)
        for rail, hole in zip(spec.RAILS, trammel.pin_pair(pass_name), strict=True):
            assert pose.to_machine(hole) == pytest.approx(
                trammel.rail_point(rail, stations[rail] + pivot_block.BORE_X)
            )


def test_loaded_top_retainers_clear_the_native_crosspins_and_cotters() -> None:
    gap = sum(retention.TOP_RUNNING_GAP) / 2.0
    assert gap == pytest.approx(0.175)
    assert pivot_retainer.NOMINAL_RUNNING_GAP == pytest.approx(gap)
    allowed = contracts.allowed_interference_pairs(spec.ASM_NAME)
    for index, pin_origin in enumerate(spec.PIVOT_PIN_ORIGINS):
        washer_origin, washer_rows = spec.PLACEMENTS[spec.PIVOT_RETAINER][index]
        clevis_origin, clevis_rows = spec.PLACEMENTS[spec.PIVOT_CLEVIS_PIN][index]
        cotter_origin, cotter_rows = spec.PLACEMENTS[spec.PIVOT_COTTER][index]
        assert washer_origin == pytest.approx(
            (*pin_origin[:2], trammel.CARRIER_TOP_Z + gap)
        )
        for rows in (washer_rows, clevis_rows, cotter_rows):
            for actual, expected in zip(rows, spec.PIN_ROWS, strict=True):
                assert actual == pytest.approx(expected)
        hole_z = pin_origin[2] + pivot_pin.CROSS_HOLE_STATION
        clevis_radius = retention_hardware.CLEVIS_DIA / 2.0
        assert clevis_origin[2] + clevis_radius == pytest.approx(
            hole_z + retention.PIN_CROSS_HOLE_DIA / 2.0
        )
        washer_top = washer_origin[2] + pivot_retainer.THICKNESS
        assert clevis_origin[2] - clevis_radius == pytest.approx(washer_top)
        # Coaxial placement at the loose cross-hole centre would falsely cut
        # into the fitted washer; contact is at the UPPER loaded hole edge.
        assert clevis_origin[2] > hole_z
        assert hole_z - clevis_radius < washer_top
        assert clevis_origin == pytest.approx(_image(
            spec.PIN_ROWS, pin_origin,
            (spec.PIVOT_CLEVIS_HEAD_X, 0.0,
             pivot_pin.CARRIER_STATION + spec.PIVOT_CLEVIS_CENTRE_ABOVE_SEAT),
        ))
        assert cotter_origin == pytest.approx(_image(
            clevis_rows, clevis_origin,
            (retention_hardware.CLEVIS_HOLE_FROM_HEAD, 0.0, 0.0),
        ))
        # The headed end and cotter eye are wholly outside the Ø24 washer.
        # Spread prongs can overhang its plan, but only ABOVE its top face.
        washer_radius = pivot_retainer.OUTER_DIA / 2.0
        assert spec.PIVOT_CLEVIS_HEAD_X < -washer_radius
        cotter_x = spec.PIVOT_CLEVIS_HEAD_X + retention_hardware.CLEVIS_HOLE_FROM_HEAD
        assert cotter_x - pivot_cotter.EYE_OUTER_RADIUS > washer_radius
        assert cotter_x - pivot_cotter.COTTER_DIA / 2.0 > washer_radius
        assert cotter_origin[2] + pivot_cotter.PRONG_BEND > washer_top
        pin_name = spec.instance_name(spec.PIVOT_PIN, index)
        washer_name = spec.instance_name(spec.PIVOT_RETAINER, index)
        for family in (spec.PIVOT_CLEVIS_PIN, spec.PIVOT_COTTER):
            name = spec.instance_name(family, index)
            assert frozenset((name, washer_name)) not in allowed
            assert frozenset((name, pin_name)) not in allowed


def test_caps_screws_and_safety_wire_close_on_each_block_receiver_pattern() -> None:
    allowed = contracts.allowed_interference_pairs(spec.ASM_NAME)
    for index, (block_origin, block_rows) in enumerate(spec.PIVOT_BLOCK_PLACEMENTS):
        cap_origin, cap_rows = spec.PLACEMENTS[spec.PIVOT_CAP][index]
        assert cap_origin == pytest.approx(_image(
            block_rows, block_origin,
            (pivot_block.BORE_X, 0.0, pivot_block.BLOCK_HEIGHT),
        ))
        for actual, expected in zip(cap_rows, block_rows, strict=True):
            assert actual == pytest.approx(expected)
        # Both integral bosses enter their own receivers below the seating face.
        assert len(retention.CAP_REGISTER_CENTERS) == 2
        for x, y in retention.CAP_REGISTER_CENTERS:
            assert _image(cap_rows, cap_origin, (x, y, 0.0)) == pytest.approx(
                _image(block_rows, block_origin, (
                    pivot_block.BORE_X + x, y, pivot_block.BLOCK_HEIGHT,
                ))
            )
            assert _image(cap_rows, cap_origin, (
                x, y, -retention.CAP_REGISTER_PROJECTION,
            ))[2] > block_origin[2] + pivot_block.BLOCK_HEIGHT - retention.BLOCK_REGISTER_DEPTH
        for slot, (x, y) in enumerate(retention.CAP_BOLT_CENTERS):
            screw_index = index * 4 + slot
            screw_origin, screw_rows = spec.PLACEMENTS[spec.PIVOT_CAP_SCREW][screw_index]
            assert screw_origin == pytest.approx(_image(
                cap_rows, cap_origin,
                (x, y, retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH),
            ))
            receiver = _image(
                block_rows, block_origin,
                (pivot_block.BORE_X + x, y, pivot_block.BLOCK_HEIGHT),
            )
            assert screw_origin[:2] == pytest.approx(receiver[:2])
            assert screw_rows[2] == pytest.approx((0.0, 0.0, 1.0))
            screw = spec.instance_name(spec.PIVOT_CAP_SCREW, screw_index)
            block = spec.instance_name(spec.PIVOT_BLOCK, index)
            assert frozenset((screw, block)) in allowed
            assert {pair for pair in allowed if screw in pair} == {
                frozenset((screw, block))
            }
        for slot, y in enumerate(retention.CAP_BOLT_Y_OFFSETS):
            wire_origin, wire_rows = spec.PLACEMENTS[spec.PIVOT_LOCK_WIRE][index * 2 + slot]
            assert wire_origin == pytest.approx(_image(
                cap_rows, cap_origin,
                (0.0, y, retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH),
            ))
            for actual, expected in zip(wire_rows, cap_rows, strict=True):
                assert actual == pytest.approx(expected)


def test_wing_bracket_repair_removes_real_solid_overlap_without_moving_the_bracket() -> None:
    block_origin, rows = spec.PIVOT_BLOCK_PLACEMENTS[0]
    assert spec.NUT_BRACKET_ROWS == rows
    offset = tuple(
        sum((spec.NUT_BRACKET_ORIGIN[a] - block_origin[a]) * rows[k][a] for a in range(3))
        for k in range(3)
    )
    assert offset[:2] == pytest.approx((0.0, -pivot_block.BLOCK_WIDTH / 2.0))
    # Reconstruct the OLD intersection in the actual common rail frame.
    # The core's Y=-20 face is intentional mounting contact; only the wing
    # extended into this positive-volume bracket region.
    old_end = -9.0
    prism = (
        (offset[0] + nut_bracket.FACE_X, old_end),
        (max(-pivot_block.WING_WIDTH / 2.0, offset[1] - nut_bracket.BRACKET_DEPTH),
         min(-pivot_block.BLOCK_WIDTH / 2.0, offset[1])),
        (max(0.0, offset[2]), min(pivot_block.BLOCK_HEIGHT, offset[2] + nut_bracket.BRACKET_HEIGHT)),
    )
    # Use the old 66 mm wing, not the enlarged repair width, for the historic
    # negative control's exact material volume.
    old_prism = (prism[0], (max(-33.0, prism[1][0]), prism[1][1]), prism[2])
    assert math.prod(hi - lo for lo, hi in old_prism) == pytest.approx(78.0)

    def circle_gap(point, radius, axes):
        return math.hypot(*(
            max(old_prism[axis][0] - value, value - old_prism[axis][1], 0.0)
            for axis, value in zip(axes, point, strict=True)
        )) - radius

    # Every native cut misses the ENTIRE old prism, not only its corners:
    # hence 78 mm³ was actual solid/solid interference, not an AABB alarm.
    assert circle_gap((pivot_block.BORE_X, 0.0), pivot_block.BEARING_OD / 2.0, (0, 1)) > 0.0
    for point in pivot_block.BOLT_POINTS:
        assert circle_gap(point, pivot_block.CBORE_DIA / 2.0, (0, 1)) > 0.0
    for x in pivot_block.SIDE_SCREW_X:
        assert circle_gap((x, pivot_block.SIDE_SCREW_Z),
                          pivot_block.SIDE_CBORE_DIA / 2.0, (0, 2)) > 0.0
    for point in pivot_block.CAP_TAP_POINTS:
        assert circle_gap(point, retention_hardware.SCREW_MAJOR_DIA_MAX / 2.0, (0, 1)) > 0.0
    for point in pivot_block.REGISTER_POINTS:
        assert circle_gap(point, pivot_block.REGISTER_DIA / 2.0, (0, 1)) > 0.0
    for x, _y, z in nut_bracket.BLOCK_SCREW_POINTS:
        assert circle_gap((offset[0] + x, offset[2] + z),
                          pivot_block.SIDE_SCREW_MAJOR / 2.0, (0, 2)) > 0.0
    # The nut's transverse seat and #4 taps are all beyond the prism in Y,
    # even when their largest cut radius is used for every member.
    for y in (-nut_bracket.BORE_Y, *(point[1] for point in nut_bracket.NUT_HOLE_POINTS)):
        assert offset[1] + y + nut_bracket.CBORE_DIA / 2.0 < old_prism[1][0]

    assert pivot_block.WING_X1 < offset[0] + nut_bracket.FACE_X
    assert spec.require_wing_bracket_clearance() >= retention.WING_BRACKET_CLEARANCE_MIN
    with pytest.raises(ValueError, match="wing/nut bracket"):
        spec.require_wing_bracket_clearance(wing_axis_reach=old_end - pivot_block.BORE_X)


@pytest.mark.parametrize("fraction", (0.99, 1.01))
def test_wing_bracket_gap_rejects_the_actual_printed_boundary(fraction: float) -> None:
    margin = spec.require_wing_bracket_clearance() - retention.WING_BRACKET_CLEARANCE_MIN
    assert margin > 0.0
    reach = pivot_block.WING_AXIS_REACH + fraction * margin
    if fraction < 1.0:
        assert spec.require_wing_bracket_clearance(wing_axis_reach=reach) > retention.WING_BRACKET_CLEARANCE_MIN
    else:
        with pytest.raises(ValueError, match="wing/nut bracket"):
            spec.require_wing_bracket_clearance(wing_axis_reach=reach)



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
        spec.PIVOT_PIN,
        *CAPTURE_FAMILIES,
        spec.RISER,
        spec.HUB_PIN,
        spec.FEED_LEVER,
        spec.NUT_BRACKET,
        spec.CARRIAGE,
        spec.BEARING,
        spec.CL_DOWEL,
        spec.LEADSCREW_NUT,
        spec.BLOCK_SCREW,
        spec.CARRIAGE_SCREW,
        spec.NUT_SCREW,
        spec.RISER_SCREW,
        spec.CLAMP_SCREW,
        spec.LEVER_SCREW,
        spec.BLOCK_LOCK_WASHER,
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
        for stem, (parent, _per) in spec.LOCKED_TO.items()
        if parent == spec.CARRIER
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
    for stem, (parent, _per) in spec.LOCKED_TO.items():
        assert parent in {spec.CARRIAGE, spec.CARRIER} or (
            locked.index(parent) < locked.index(stem)
        ), stem
        for index, (origin, _rows) in enumerate(spec.PLACEMENTS[stem]):
            reach = [
                math.dist(origin, placed) for placed, _r in spec.PLACEMENTS[parent]
            ]
            nearest = spec.instance_name(parent, reach.index(min(reach)))
            assert spec.lock_parent(stem, index) == nearest, (stem, index)
    # The carrier rides the inner pass's pins in the saved model: A1 on pin 1,
    # B1 on pin 2; verify re-mates A2/B2 for the outer pass.
    assert {
        pass_name: [(hole, pin) for _label, hole, pin in mates]
        for pass_name, mates in spec.PIN_MATES.items()
    } == {"inner": [("A1", 0), ("B1", 1)], "outer": [("A2", 0), ("B2", 1)]}


def _thread(row: fasteners.Fastener, tap_drill: float) -> tuple[float, float, float]:
    return (row.major_mm, tap_drill, row.engagement_mm)


def test_interference_contracts_are_the_press_fits_and_threads() -> None:
    assert contracts.JIG_HUB_PIN_SEAT == (hub_pin.FIT_DIA, hub_pin.SEAT_LENGTH)
    assert hub_pin.SEAT_LENGTH == trammel.CARRIER_THICK
    assert contracts.JIG_CL_DOWEL_PRESS == (cl_dowel.DIA, carrier.THICKNESS)
    assert hub_pin.SHOULDER_FILLET_RADIUS <= hub_pin.HUB_HOLE_UNDERSIDE_BREAK_MIN
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
            contracts.JIG_BLOCK_SCREW_THREAD,
            _thread(fasteners.NUT_BRACKET_TO_BLOCK, nut_bracket.BLOCK_TAP_DRILL),
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
            _thread(fasteners.NUT_TO_NUT_BRACKET, nut_bracket.NUT_TAP_DRILL),
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
            contracts.JIG_PIVOT_CAP_SCREW_THREAD,
            _thread(fasteners.CAP_TO_BLOCK, pivot_block.CAP_TAP_DRILL_DIA),
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
        (
            contracts.JIG_BEARING_ON_PIN,
            (pivot_pin.BEARING_DIA, bearing.BORE, bearing.WIDTH),
        ),
        (
            contracts.JIG_BEARING_IN_BLOCK,
            (bearing.OD, pivot_block.BORE_DIA, bearing.WIDTH),
        ),
    ):
        # The literals carry the thread majors to 4 places, the specs to 3.
        assert envelope == pytest.approx(expected, abs=1e-3)
    assert bearing.SEAT_DIA == pivot_block.BORE_DIA
    pairs = contracts.allowed_interference_pairs(spec.ASM_NAME)
    names = {
        spec.instance_name(stem, index)
        for stem, count in spec.QUANTITIES.items()
        for index in range(count)
    }
    assert all(pair <= names for pair in pairs)
    # Two presses into the carrier, every screw once, each stud in its T-nut
    # and its flange nut, the screw in its nut, each bearing on its pin and in
    # its block.
    assert len(pairs) == 2 + sum(spec.QUANTITIES[s] for s in SCREW_ROWS) + 8 + 1 + 8
    seat = math.pi * hub_pin.FIT_DIA**2 * hub_pin.SEAT_LENGTH / 4.0
    hub = frozenset((f"{spec.HUB_PIN}-1", f"{spec.CARRIER}-1"))
    assert pairs[hub] == pytest.approx(1.10 * seat)
    dowel = math.pi * cl_dowel.DIA**2 * carrier.THICKNESS / 4.0
    assert pairs[frozenset((f"{spec.CL_DOWEL}-1", f"{spec.CARRIER}-1"))] == (
        pytest.approx(1.10 * dowel)
    )
    inserted = (*SCREW_ROWS, spec.HOLD_DOWN_STUD, spec.LEADSCREW_NUT, spec.BEARING)
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
    for stem in (spec.HOLD_DOWN_STUD, spec.BEARING):
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
        assert (row["process"] == "purchased") == number.startswith(
            (prefix + "VN-", "MHA-SH-VN-")
        ), stem
        # The registry owns each bought item's source: no supplier or SKU
        # leaks into the BOM text.
        description = spec.BOM_DESCRIPTIONS[stem].casefold()
        for source in (row.get("supplier"), *row.get("supplier_skus", ())):
            assert not source or str(source).casefold() not in description, stem


def test_source_bom_and_drawing_clusters_partition_every_capture_family_once() -> None:
    clustered = [family for cluster in drawing.CLUSTERS for family in cluster.stems]
    assert sorted(clustered) == sorted(spec.BOM_ORDER)
    assert tuple(drawing.BOM_COMPONENTS) == spec.BOM_ORDER
    assert drawing.BOM_QUANTITIES == spec.QUANTITIES
    assert drawing.BOM_ITEM_NUMBERS == spec.ITEM_NUMBERS
    capture, = [
        cluster for cluster in drawing.CLUSTERS
        if cluster.sheet == "PIVOTCAPTUREEXPLODED"
    ]
    assert set(capture.stems) == {
        spec.PIVOT_PIN, spec.BEARING, *CAPTURE_FAMILIES
    }
    parts = _builder_parts()
    for family in spec.BOM_ORDER:
        assert spec.BOM_ORDER.count(family) == 1
        assert parts.count(
            (spec.COMPONENT_IDENTITIES[family][0], family)
        ) == 1
        assert clustered.count(family) == 1
    assert drawing.CAPTURE_SHEET == "CAPTUREANDOPERATION"
    assert drawing.CAPTURE_SHEET in drawing.SHEET_NAMES
    assert drawing.CAPTURE_SHEET != drawing.STEPS_SHEET


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


def test_alignment_note_prints_the_calculator_targets() -> None:
    assert spec.ALIGNMENT_BAND == carrier.POSITION_BAND
    lines = spec.ALIGNMENT_NOTE_LINES[1:]
    assert len(lines) == len(trammel.ALIGNMENT_STATIONS)
    for line, station in zip(lines, trammel.ALIGNMENT_STATIONS):
        (x1, y1), (x2, y2) = (
            trammel.ALIGNMENT_TARGETS[station]["rail 1"],
            trammel.ALIGNMENT_TARGETS[station]["rail 2"],
        )
        for value in (x1, y1, x2, y2):
            assert f"{value:.3f}" in line
        assert (x2, y2) == pytest.approx((-x1, y1))
    assert trammel.ALIGNMENT_TARGETS[100.0]["rail 1"] == pytest.approx(
        (-98.973, -14.298), abs=5e-4
    )


def test_sweep_clears_the_column_cover(report) -> None:
    expected = {
        "carrier": 113.29,
        "riser": 150.80,
        "feed lever": 236.58,
        "HUB pin head": 169.49,
        "carriage 1": 184.61,
        "carriage 2": 184.61,
        "nut bracket": 135.28,
        # Ruling A′: bracket outer ends remain at lateral 88.9.
        "end bracket near": 111.45,
        "end bracket far": 164.49,
        "KP08 near": 114.81,
        "KP08 far": 167.86,
        "screw": 141.19,
        "handwheel": 179.91,
    }
    # The new wing changes the block's old 178.89 margin. Its column-most
    # corner occurs at the analytical near carriage stop, not mid-sweep.
    near = min(low for low, _high in trammel.END_STOPS.values())
    for rail in spec.RAILS:
        column_y = max(
            trammel.rail_point(
                rail, near + pivot_block.BLOCK_X0, lateral
            )[1]
            for lateral in (
                -retention.BLOCK_WING_HALF_WIDTH,
                retention.BLOCK_WING_HALF_WIDTH,
            )
        )
        expected[f"pivot block {rail}"] = spec.COVER_Y - column_y
    assert {name: report.cover_clearance[name] for name in expected} == pytest.approx(
        expected, abs=0.01
    )
    # Added hardware must enter the report, without dropping any older item.
    outlines = spec.moving_outlines("inner", 0.0)
    assert set(report.cover_clearance) == (
        set(outlines) | set(spec.feed_outlines()) | {"HUB pin head"}
    )
    for rail in spec.RAILS:
        assert {
            f"pivot cap {rail}", f"pivot retainer {rail}", f"pivot pin {rail}",
            f"pivot clevis {rail}", f"pivot cotter {rail}", f"pivot lock wire {rail}",
        } <= set(outlines)
    assert {f"pivot cap screw {index}" for index in range(1, 9)} <= set(outlines)
    assert min(report.cover_clearance.values()) > 100.0


def test_sweep_extents_and_rail_margins(report) -> None:
    assert report.moving_x == pytest.approx((-449.85, 449.85), abs=0.01)
    assert report.moving_y == pytest.approx((-373.26, 77.21), abs=0.01)
    # The 2026-10-17 widening (1/2 x 6, column-side edge at lateral +88.9):
    # the far column-side corners set X, the near column-side corners the
    # top of Y.
    assert report.fixed_x == pytest.approx((-463.04, 463.04), abs=0.01)
    assert report.fixed_y == pytest.approx((-127.90, 85.84), abs=0.01)
    assert report.bar_overhang == pytest.approx({1: 43.94, 2: 43.94}, abs=0.01)
    assert report.carriage_margin["inner"] == pytest.approx((61.52, 14.81), abs=0.01)
    assert report.carriage_margin["outer"] == pytest.approx((64.18, 2.93), abs=0.01)
    assert all(
        near > 0.0 and far > 0.0 for near, far in report.carriage_margin.values()
    )


def test_studs_stop_under_the_swinging_carrier() -> None:
    # The longest stud the carrier's underside clears; verify.py's native
    # sweep proves the modelled 3 in studs clear of everything that moves.
    assert spec.STUD_LENGTH_MAX == pytest.approx(
        trammel.CARRIER_UNDERSIDE_Z - clamp_screw.STAND_OUT_MAX - spec.STUD_BOTTOM_Z
    )
    # The 1/2-13 x 3 in stud is the only stud; step 2 states the limit,
    # rounded down to 1/8 in.
    assert spec.STUD_LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM
    assert spec.STUD_LENGTH == pytest.approx(3.0 * trammel.INCH)
    assert spec.STUD_LENGTH < spec.STUD_LENGTH_MAX


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
            "pin": "PinAxis@ch-rocker-arm-tl-oblique-pivot-pin-1",
        },
        {
            "label": "carrier B2 on pin 2",
            "hole": "PinAxisB2@ch-rocker-arm-tl-oblique-carrier-1",
            "pin": "PinAxis@ch-rocker-arm-tl-oblique-pivot-pin-2",
        },
    ]


def test_inch_eighths_down() -> None:
    assert spec.inch_eighths_down(89.7) == "3-1/2"
    assert spec.inch_eighths_down(3.0 * trammel.INCH) == "3"
    assert spec.inch_eighths_down(3.874 * trammel.INCH) == "3-3/4"
    assert spec.inch_eighths_down(0.25 * trammel.INCH) == "1/4"


def test_sweep_table_edge_margins(report) -> None:
    edges = report.table_edge_margins
    assert edges["carrier"] == pytest.approx(
        {"-X end": 0.35, "+X end": 0.35, "front": 8.81, "back": -3.95}, abs=0.01
    )
    assert edges["feed lever"]["front"] == pytest.approx(-236.96, abs=0.01)
    for rail, outer, inner in ((1, "-X end", "+X end"), (2, "+X end", "-X end")):
        bar = edges[f"base bar {rail}"]
        assert bar[outer] == pytest.approx(-43.94, abs=0.01)
        assert bar[outer] == pytest.approx(-report.bar_overhang[rail])
        assert bar["front"] == pytest.approx(8.39, abs=0.01)
        # The 2026-10-17 widening: each bar's near column-side corner (Y 85.84)
        # stands 12.59 past the table's back edge (Y 73.25), toward the cover.
        assert bar["back"] == pytest.approx(-12.59, abs=0.01)
        assert spec.TABLE_Y[1] == pytest.approx(73.25, abs=0.01)
        corner = trammel.rail_point(
            rail, trammel.RAIL_NEAR_S, trammel.BASE_BAR_COLUMN_EDGE
        )
        assert corner[1] == pytest.approx(85.84, abs=0.01)
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
            "nut bracket",
            "end bracket near",
            "end bracket far",
            "KP08 near",
            "KP08 far",
            "screw",
            "handwheel",
        )
    }
    assert feed["KP08 near"]["back"] == pytest.approx(-2.43, abs=0.01)
    # Ruling A′: flush with the bar's column-side edge, the bracket passes
    # the back edge by 5.80 (the bar's own corner by 12.59).
    assert feed["end bracket near"]["back"] == pytest.approx(-5.80, abs=0.01)
    assert feed["handwheel"]["-X end"] == pytest.approx(-88.19, abs=0.01)
    assert feed["handwheel"]["back"] == pytest.approx(62.67, abs=0.01)
    assert feed["screw"]["-X end"] == pytest.approx(-57.97, abs=0.01)
    assert feed["nut bracket"]["-X end"] == pytest.approx(-16.81, abs=0.01)
    assert min(margin["front"] for margin in feed.values()) > 90.0


# Fastener table: (callout, count, engagement, protrusion). Protrusion is the
# screw's length past the grip less the receiving thread's depth; below zero,
# the screw stops inside the part (THRU tap) or short of the full thread
# (blind tap). Engagement is never more than the receiving thread's depth.
FASTENER_TABLE = {
    "RAIL_TO_BAR": ("#8-32 X 3/4 SHCS", 14, 9.35, -3.35),
    "BRACKET_TO_BAR": ("#8-32 X 5/8 SHCS", 8, 7.975, -4.725),
    "NUT_BRACKET_TO_BLOCK": ("#8-32 X 1-7/8 SHCS", 2, 9.485, -2.515),
    "BLOCK_TO_CARRIAGE": ("M4 X 20 SHCS", 8, 4.4, -0.6),
    "KP08_TO_BRACKET": ("#6-32 X 5/8 SHCS", 4, 10.875, -1.825),
    "NUT_TO_NUT_BRACKET": ("#4-40 X 1/2 BHCS", 4, 9.2, -0.8),
    "RISER_TO_CARRIER": ("#4-40 X 5/8 B18.6.3 FLAT HEAD", 4, 10.4014, -1.5986),
    "CR_CLAMP": ("1/4-20 X 7/8 SHCS", 1, 12.0, 1.725),
    "LEVER_TO_CARRIER": ("5/16-18 X 1 SHCS", 2, 10.414, -1.586),
    "CAP_TO_BLOCK": (
        "5/16-18 X 3/4 SHCS", 8,
        retention_hardware.SCREW_LENGTH - (retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH),
        retention_hardware.SCREW_LENGTH - (retention.CAP_HEIGHT - retention.CAP_COUNTERBORE_DEPTH) - pivot_block.BLOCK_HEIGHT,
    ),
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
    assert fasteners.BLOCK_TO_CARRIAGE.engagement_mm == pytest.approx(
        pivot_block.CARRIAGE_THREAD_DEPTH - 0.6
    )
    # A 1-1/8 in lever screw would stand out of the carrier's underside.
    assert (
        fasteners.inch_mm("1-1/8") - fasteners.LEVER_TO_CARRIER.grip_mm
        > carrier.THICKNESS
    )
    # The bar screws' worst case at TL-20's bands stays inside 1.5 D .. TL-28.
    low, high = leadscrew.BAR_SCREW_ENGAGEMENT_RANGE
    assert (low, high) == pytest.approx((6.955, 8.995), abs=1e-3)
    assert 1.5 * leadscrew.SHCS_8_MAJOR < low and high < leadscrew.BRACKET_THICK
    assert leadscrew.KP08_FOOT_THICK == 5.0  # UNVERIFIED: verify on receipt
    # One wedge-lock pair under each block screw head and each lever screw
    # head (rule 23: those screws carry a reversing load), in the row's grip.
    assert fasteners.WASHERS == (
        fasteners.BLOCK_LOCK_WASHER,
        fasteners.LEVER_LOCK_WASHER,
    )
    # The nut screws' button heads sit directly on the flange (owner ruling
    # 2026-10-20: no washers).
    assert fasteners.NUT_TO_NUT_BRACKET.head == fasteners.BHCS
    assert fasteners.NUT_TO_NUT_BRACKET.grip_mm == pytest.approx(
        leadscrew.NUT_FLANGE_THICK
    )
    assert fasteners.BLOCK_LOCK_WASHER.count == fasteners.NUT_BRACKET_TO_BLOCK.count
    assert fasteners.NUT_BRACKET_TO_BLOCK.grip_mm == pytest.approx(
        leadscrew.BLOCK_SCREW_GRIP + fasteners.BLOCK_LOCK_WASHER.thickness_mm
    )
    assert fasteners.LEVER_LOCK_WASHER.count == fasteners.LEVER_TO_CARRIER.count
    assert fasteners.LEVER_TO_CARRIER.grip_mm == pytest.approx(
        feed_lever.LEVER_THICK + fasteners.LEVER_LOCK_WASHER.thickness_mm
    )
    assert fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert fasteners.HOLD_DOWN_STUD_COUNT == 4


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
    # Ruling A′'s 8 holes: the near 44 hole stays the closest (the new 27.5
    # one 19.47, the 66 and 82.5 ones farther out).
    assert min(gaps) == pytest.approx(18.69, abs=0.01)
    assert sorted(gaps)[1] == pytest.approx(19.47, abs=0.01)


def test_bracket_bar_screws_sit_in_their_rule_17_window() -> None:
    # Ruling A′ (2026-10-17): two pairs about the screw axis, the outer
    # half-span the round value between TL-28's #8-to-#6 wall and TL-20's
    # counterbore-to-edge wall, both at the 2.0 target at worst case.
    assert leadscrew.BAR_SCREW_LATERALS == (27.5, 44.0, 66.0, 82.5)
    assert leadscrew.BAR_SCREW_OUTER_HALF_SPAN_MIN == pytest.approx(27.096, abs=1e-3)
    assert leadscrew.BAR_SCREW_OUTER_HALF_SPAN_MAX == pytest.approx(27.545, abs=1e-3)
    assert leadscrew.BRACKET_LENGTH == pytest.approx(
        trammel.BASE_BAR_COLUMN_EDGE - leadscrew.BRACKET_INNER_LATERAL
    )
    assert leadscrew.BRACKET_LENGTH == pytest.approx(68.9)


def test_bracket_load_cases_hold_the_hand_abuse_thrust() -> None:
    # LOAD_CASES: 1 kN along the screw at its axis on 4 x #8 at 25 in-lbf.
    assert leadscrew.BAR_SCREW_TORQUE_NM == 2.8
    assert leadscrew.BAR_SCREW_PRELOAD == pytest.approx(3360.9, abs=0.1)
    assert leadscrew.BAR_SCREW_THRUST_ECCENTRICITY == pytest.approx(0.0)
    assert leadscrew.BRACKET_SLIP_THRUST == pytest.approx(2688.7, abs=0.1)
    assert leadscrew.BRACKET_OPENING_THRUST == pytest.approx(1540.9, abs=0.1)
    assert leadscrew.BRACKET_SLIP_THRUST >= 1.5 * leadscrew.HAND_ABUSE_THRUST
    # TL-00 step 1 prints the one torque where the bracket screws go in.
    assert (
        "STATION, 4 #8-32 X 5/8 SHCS (ITEM "
        f"{spec.ITEM_NUMBERS[spec.BRACKET_SCREW]}) PER BRACKET FROM BELOW, "
        "2.8 N·m (25 IN·LBF)."
    ) in spec.ASSEMBLY_STEPS[0]


def _leadscrew_with(**bought: float) -> types.ModuleType:
    """The leadscrew spec re-run with bought dims changed (a vendor swap).
    Every name must be assigned once inside the ``# --- Bought items`` block;
    the module's own self-checks run on the new numbers."""
    source = Path(leadscrew.__file__).read_text(encoding="utf-8")
    head, mark, tail = source.partition("# --- Bought items")
    block, layout, rest = tail.partition("# --- Layout")
    assert mark and layout
    for name, value in bought.items():
        block, count = re.subn(
            rf"^{name} = .*$", f"{name} = {value!r}", block, flags=re.MULTILINE
        )
        assert count == 1, name
    module = types.ModuleType("perturbed_leadscrew")
    module.__file__ = leadscrew.__file__
    code = compile(head + mark + block + layout + rest, leadscrew.__file__, "exec")
    exec(code, module.__dict__)
    return module


def _drilled(feed: types.ModuleType) -> tuple:
    """What the drilled parts fix: KP08 stations, bar holes, screw length."""
    return (feed.KP08_S, feed.BASE_BAR_HOLES, feed.SCREW_LENGTH)


def _nut_interface_follows(feed: types.ModuleType) -> None:
    """TL-29's nut interface follows the bought nut, whatever its numbers."""
    assert feed.NUT_X[0] == pytest.approx(
        feed.NUT_BRACKET_X[0] - feed.NUT_FLANGE_THICK - feed.NUT_BODY_LONG
    )
    assert feed.NUT_BORE_DIA == pytest.approx(feed.NUT_BODY_DIA + 0.3)
    target = 2.0 * feed.NUT_SCREW_MAJOR
    assert feed.NUT_SCREW_FULL_THREAD_MIN >= target
    selected = Fraction(feed.NUT_SCREW_LENGTH)
    assert all(
        feed.full_thread_min(length, feed.NUT_SCREW_GRIP, feed.NUT_SCREW) < target
        for length in feed.INCH_SCREW_LENGTHS
        if Fraction(length) < selected
    )
    assert feed.NUT_SCREW_TAP_DEPTH > feed.NUT_SCREW_ENGAGEMENT
    assert feed.NUT_BRACKET_DEPTH == pytest.approx(
        feed.SCREW_LATERAL
        + feed.NUT_FLANGE_DIA / 2.0
        + feed.NUT_FLANGE_MARGIN
        - feed.BLOCK_SIDE_LATERAL
    )


def test_vendor_swap_moves_no_drilled_part() -> None:
    # The stations and the screw length are fixed; the self-checks guard them
    # against the bought block. A swap changes TL-29's nut interface only, or
    # trips a self-check: a redesign decision, never a silent move.
    assert _drilled(leadscrew) == (
        (72.0, 443.0),
        tuple((x, -lateral) for x in (57.0, 428.0) for lateral in (27.5, 44, 66, 82.5)),
        410.0,
    )
    assert leadscrew.NEAR_STUB == pytest.approx(2.0)
    assert leadscrew.HANDWHEEL_ENGAGEMENT == pytest.approx(18.0)
    assert leadscrew.HANDWHEEL_STUB == pytest.approx(24.0)
    # The screw end stops 7 inside the wheel's outer face (THRU bore).
    assert leadscrew.WHEEL_S[1] - leadscrew.SCREW_FAR_END_S == pytest.approx(7.0)
    lo, hi = trammel.CARRIAGE_TRAVEL
    near = leadscrew.nut_bracket_box(lo)[0] - leadscrew.KP08_BOXES["KP08 near"][1]
    far = leadscrew.KP08_BOXES["KP08 far"][0] - leadscrew.nut_bracket_box(hi)[1]
    assert (near, far) == pytest.approx((2.97, 2.88), abs=0.01)
    _nut_interface_follows(leadscrew)
    assert leadscrew.NUT_BODY_LONG == pytest.approx(10.0)
    assert leadscrew.NUT_BORE_DIA == pytest.approx(10.5)
    # Swaps the layout absorbs: a shorter nut, a bigger flange, a longer hub.
    for bought in (
        {"NUT_LENGTH": 13.5, "NUT_BODY_DIA": 10.0, "NUT_HOLE_PCD": 16.1},
        {"NUT_FLANGE_DIA": 25.0, "NUT_FLANGE_THICK": 5.0, "NUT_HOLE_PCD": 19.0},
        _LONG_HUB,
    ):
        feed = _leadscrew_with(**bought)
        assert _drilled(feed) == _drilled(leadscrew), bought
        _nut_interface_follows(feed)
        for name, value in bought.items():
            assert getattr(feed, name) == value
    short_nut = _leadscrew_with(NUT_LENGTH=13.5, NUT_BODY_DIA=10.0)
    assert short_nut.NUT_BORE_DIA == pytest.approx(10.3)
    big_flange = _leadscrew_with(NUT_FLANGE_DIA=25.0, NUT_FLANGE_THICK=5.0)
    assert big_flange.NUT_BRACKET_DEPTH == pytest.approx(
        leadscrew.NUT_BRACKET_DEPTH + 1.5
    )
    long_hub = _leadscrew_with(**_LONG_HUB)
    assert long_hub.WHEEL_S[1] == pytest.approx(leadscrew.WHEEL_S[1] + 7.0)
    assert long_hub.HANDWHEEL_S[1] == pytest.approx(leadscrew.HANDWHEEL_S[1] + 7.0)
    # Swaps that trip a self-check. With the nut on -X no bought number moves
    # the bracket's +X end alone: a swap reaches the near KP08 first.
    for bought, message in (
        ({"NUT_LENGTH": 17.5}, "reaches the near KP08"),
        ({"KP08_WIDTH": 16.0}, "reaches the near KP08"),
        # The flat's far end (6.5 + 4) binds, not the grub's far flank: at
        # 14.5 the grub alone (17.0) would pass the screw's 18.
        (
            {"HANDWHEEL_GRUB_FROM_HUB": 14.5},
            "short of the handwheel's grub or its flat",
        ),
        (
            {"HANDWHEEL_GRUB_FROM_HUB": 17.0},
            "short of the handwheel's grub or its flat",
        ),
        (
            {
                "HANDWHEEL_HUB_LENGTH": 2.0,
                "HANDWHEEL_BORE_LENGTH": 14.0,
                "HANDWHEEL_LENGTH": 35.0,
            },
            "proud of the wheel's outer face",
        ),
        ({"HANDWHEEL_GRIP_OFFSET": 30.0}, "swept grip reaches the bar top"),
        ({"HANDWHEEL_GRIP_LENGTH": 20.0}, "hub, rim and grip miss its length"),
    ):
        with pytest.raises(AssertionError, match=message):
            _leadscrew_with(**bought)


# A handwheel with a hub 7 longer: bore and overall length grow with it.
_LONG_HUB = {
    "HANDWHEEL_HUB_LENGTH": 20.0,
    "HANDWHEEL_BORE_LENGTH": 32.0,
    "HANDWHEEL_LENGTH": 53.0,
}


def test_block_screw_torque_is_capped_by_the_bracket_thread() -> None:
    # Review bought-r6 (rule 23): the wedge-lock pairs keep the block screws
    # from backing off; their preload, capped at a third of the TL-29 thread's
    # strip load over the shortest engagement the bands and the pairs leave,
    # holds the feed thrust by friction with margin.
    engagement = block_washer.ENGAGEMENT_MIN
    assert engagement == pytest.approx(7.83, abs=0.01)
    assert spec.FEED_THRUST_N == pytest.approx(1161, abs=1)
    assert spec.BLOCK_SCREW_TORQUE_NM == 4.4
    assert spec.BLOCK_SCREW_PRELOAD_N <= spec._BLOCK_THREAD_STRIP_N / 3.0
    assert spec.BLOCK_JOINT_SLIP_N >= 1.25 * spec.FEED_THRUST_N


def test_lever_screw_torque_is_capped_by_the_carrier_thread() -> None:
    # C3 r6 TL-00 review (rule 23): the wedge-lock pairs keep the lever
    # screws from backing off under the operator's reversing push and pull.
    # Their preload is a third of the TL-21 6061 tap's strip load over the
    # shortest engagement (the shortest 1 in screw through the thickest lever
    # and pair, inside the 12 plate's RV-01 full thread), T = 0.20 F d.
    engagement = lever_washer.ENGAGEMENT_MIN
    assert engagement == pytest.approx(9.14, abs=0.01)
    assert engagement <= carrier.ENGAGEMENT_MM[carrier.LEVER_THREAD]
    major = fasteners.LEVER_TO_CARRIER.major_mm
    assert major == pytest.approx(7.9375, abs=1e-3)
    assert spec._LEVER_THREAD_STRIP_N == pytest.approx(
        0.75 * math.pi * major * engagement * spec._AL_SHEAR_ULTIMATE_MPA
    )
    assert spec.LEVER_SCREW_TORQUE_NM == 18.7
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
    # The ring on the brass: concentric with the hole inside the head's least
    # diameter (ASME B18.3), the head off the hole by half its runout and the
    # spot drill's float.
    assert nut_screw.HEAD_DIA_MIN < nut_screw.DIMS.head_dia
    offset = nut_screw.HEAD_RUNOUT_FIM / 2.0 + nut_bracket.NUT_SPOT_FLOAT
    ring_od = nut_screw.HEAD_DIA_MIN - 2.0 * offset
    assert ring_od == pytest.approx(4.857, abs=1e-3)
    flange_area = math.pi / 4.0 * (ring_od**2 - leadscrew_nut.HOLE_DIA**2)
    assert spec.NUT_SCREW_FLANGE_BEARING_MPA == pytest.approx(
        spec.NUT_SCREW_PRELOAD_N / flange_area
    )
    assert spec.NUT_SCREW_FLANGE_BEARING_MPA == pytest.approx(79.0, abs=0.5)
    assert spec.NUT_SCREW_FLANGE_BEARING_MPA < spec._BRASS_YIELD_MPA
    assert spec.NUT_SCREW_PRELOAD_N <= spec._NUT_SCREW_PRELOAD_CAP_N
    # The screw: under half its 120 ksi on the #4-40 stress area.
    assert spec.NUT_SCREW_PRELOAD_N / (0.00604 * 25.4**2) < 0.5 * 827.4
    assert spec.NUT_FLANGE_SLIP_MARGIN >= leadscrew.SLIP_MARGIN_MIN


def test_nut_screw_heads_seat_flat_on_the_flange() -> None:
    # The underhead fillet stays inside the flange's hole, the shank off it
    # by the spot's float; the head, off the hole by its runout and that
    # float, clears the nut's body. Both at the nut's nominal (its tolerances
    # are unpublished).
    assert spec.NUT_SCREW_FILLET_MARGIN == pytest.approx(
        leadscrew_nut.HOLE_DIA / 2.0
        - nut_screw.FILLET_DIA_MAX / 2.0
        - nut_bracket.NUT_SPOT_FLOAT
    )
    assert spec.NUT_SCREW_FILLET_MARGIN == pytest.approx(0.0508, abs=1e-4)
    head_reach = (
        nut_screw.DIMS.head_dia / 2.0
        + nut_screw.HEAD_RUNOUT_FIM / 2.0
        + nut_bracket.NUT_SPOT_FLOAT
    )
    assert head_reach + spec.NUT_SCREW_HEAD_TO_BODY == pytest.approx(
        (leadscrew_nut.HOLE_PCD - leadscrew_nut.BODY_DIA) / 2.0
    )
    assert spec.NUT_SCREW_HEAD_TO_BODY == pytest.approx(0.0705, abs=1e-4)


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


def test_absent_installed_tooling_authority_stays_unverified() -> None:
    report = spec.installed_tooling_clearance()
    assert report.status == "UNVERIFIED"
    assert report.min_clearance is None
    assert report.limiting_pair is None
    assert report.authority is None
    assert report == spec.installed_tooling_clearance(None)


def test_installed_tooling_report_uses_the_actual_full_fixture_census() -> None:
    fixtures = spec.captured_fixture_envelopes(samples=3)
    assert isinstance(fixtures, tuple) and fixtures
    assert all(isinstance(fixture, tooling.FixtureEnvelope) for fixture in fixtures)
    assert len({fixture.label for fixture in fixtures}) == len(fixtures)
    top = max(fixture.z_max for fixture in fixtures)
    bottom = min(fixture.z_min for fixture in fixtures)
    radius = max(math.hypot(x, y) for fixture in fixtures for x, y in fixture.xy) + 1.0
    clear = tooling.InstalledToolingEnvelope(
        source="SYNTHETIC TEST ONLY: tooling wholly above fixture",
        radial_uncertainty=0.0,
        axial_uncertainty=0.0,
        steps=(tooling.ToolingCylinder(top + 100.0, top + 110.0, radius),),
    )
    separated = spec.installed_tooling_clearance(clear, samples=3)
    assert separated == tooling.tooling_clearance_report(clear, fixtures)
    assert separated.status == "VERIFIED_GEOMETRY_ONLY"
    assert separated.min_clearance == pytest.approx(100.0)
    assert separated.authority == clear.source
    conflict = tooling.InstalledToolingEnvelope(
        source="SYNTHETIC TEST ONLY: deliberately enclosing tooling",
        radial_uncertainty=0.0,
        axial_uncertainty=0.0,
        steps=(tooling.ToolingCylinder(bottom - 1.0, top + 1.0, radius),),
    )
    overlapping = spec.installed_tooling_clearance(conflict, samples=3)
    assert overlapping == tooling.tooling_clearance_report(conflict, fixtures)
    assert overlapping.status == "POTENTIAL_CONFLICT"
    assert overlapping.min_clearance < 0.0
    assert overlapping.authority == conflict.source


def test_assembled_caption_warns_about_the_projecting_pin_and_installed_tooling() -> None:
    caption = spec.ASSEMBLED_CAPTION
    assert "TOP RETAINERS MUST BE LOCKED IN EITHER PASS" in caption
    assert "4.0 mm ABOVE THE WORK NOMINALLY" in caption
    assert "CAPTURE IS NOT COLLISION PROOF" in caption
    assert "ACCEPT THE INSTALLED TOOLHOLDER/SPINDLE ENVELOPE INCLUDING UPSET" in caption


@pytest.mark.parametrize("pass_name", ("inner", "outer"))
def test_swept_outlines_include_the_wings_caps_and_both_retainers(pass_name: str) -> None:
    for theta in spec.sweep_thetas(pass_name, samples=21):
        outlines = spec.moving_outlines(pass_name, theta)
        stations = spec.carriage_stations(pass_name, theta)
        for rail, station in stations.items():
            block = outlines[f"pivot block {rail}"]
            for x, y in (
                (pivot_block.BLOCK_X0, -retention.BLOCK_WING_HALF_WIDTH),
                (retention.BLOCK_WING_END, -retention.BLOCK_WING_HALF_WIDTH),
                (pivot_block.BLOCK_X0, retention.BLOCK_WING_HALF_WIDTH),
                (retention.BLOCK_WING_END, retention.BLOCK_WING_HALF_WIDTH),
                (pivot_block.BLOCK_X1, -pivot_block.BLOCK_WIDTH / 2.0),
                (pivot_block.BLOCK_X1, pivot_block.BLOCK_WIDTH / 2.0),
            ):
                assert _inside_xy(block, trammel.rail_point(rail, station + x, y))
            pin_station = station + pivot_block.BORE_X
            cap = outlines[f"pivot cap {rail}"]
            for x in (-retention.CAP_WIDTH / 2.0, retention.CAP_WIDTH / 2.0):
                for y in (-retention.CAP_LENGTH / 2.0, retention.CAP_LENGTH / 2.0):
                    assert _inside_xy(
                        cap, trammel.rail_point(rail, pin_station + x, y)
                    )
            px, py = trammel.rail_point(rail, pin_station)
            retainer = outlines[f"pivot retainer {rail}"]
            for angle in range(0, 360, 30):
                radians = math.radians(angle)
                radius = pivot_retainer.OUTER_DIA / 2.0
                assert _inside_xy(
                    retainer,
                    (px + radius * math.cos(radians), py + radius * math.sin(radians)),
                )


@pytest.mark.parametrize("pass_name", ("inner", "outer"))
def test_full_sweep_fixture_prisms_cover_interstitial_poses_and_rigid_upset(
    pass_name: str,
) -> None:
    fixtures = {
        fixture.label: fixture
        for fixture in spec.captured_fixture_envelopes(samples=3)
    }
    required = {
        f"{pass_name}: pivot {family} {rail}"
        for family in ("cap", "retainer", "pin", "clevis", "cotter", "lock wire")
        for rail in spec.RAILS
    } | {
        f"{pass_name}: pivot cap screw {index}" for index in range(1, 9)
    }
    required |= {
        f"{pass_name}: {name}" for name in (
            "carrier", "riser", "feed lever", "HUB pin head", "nut bracket",
            "CL dowel", "clamp screw", "leadscrew nut",
            "pivot block 1", "pivot block 2", "carriage 1", "carriage 2",
        )
    }
    for family, count in (
        ("bearing", 4), ("riser screw", 4), ("carriage screw", 8),
        ("block screw", 2), ("nut screw", 4), ("lever screw", 2),
        ("block lock washer", 2), ("lever lock washer", 2),
    ):
        required.update(
            f"{pass_name}: {family} {index}" for index in range(1, count + 1)
        )
    assert required <= set(fixtures)
    controls = [point for segment in pivot_wire.installed_wire_segments() for point in segment]
    wire_radius = pivot_wire.WIRE_DIA / 2.0
    wire_limits = tuple(
        (min(point[axis] for point in controls) - wire_radius,
         max(point[axis] for point in controls) + wire_radius)
        for axis in range(3)
    )
    # Three provider samples are intentionally coarse. This independent grid
    # includes points BETWEEN them, so a sampled-only, unexpanded box fails.
    for theta in spec.sweep_thetas(pass_name, samples=21):
        for label, outline in spec.moving_outlines(pass_name, theta).items():
            fixture = fixtures[f"{pass_name}: {label}"]
            assert all(_inside_xy(fixture.xy, point) for point in outline), (
                pass_name, theta, label
            )
        for index, (origin, rows) in enumerate(spec.PLACEMENTS[spec.PIVOT_LOCK_WIRE]):
            rail = spec.RAILS[index // 2]
            fixture = fixtures[f"{pass_name}: pivot lock wire {rail}"]
            travel = spec.carriage_stations(pass_name, theta)[rail] - spec.CARRIAGE_STATION
            dx, dy = spec.rail_direction(rail)
            shifted = (origin[0] + travel * dx, origin[1] + travel * dy, origin[2])
            # Bézier paths stay in their control hull; the explicit wire
            # radius expands it. Check both physical rows on both supports
            # between provider samples, not a nominal bridge centreline.
            for corner in product(*wire_limits):
                point = _image(rows, shifted, corner)
                assert _inside_xy(fixture.xy, point[:2])
                assert fixture.z_min <= point[2] <= fixture.z_max
    normal_z = {
        "carrier": (trammel.CARRIER_UNDERSIDE_Z, trammel.CARRIER_TOP_Z),
        "riser": (
            trammel.CARRIER_TOP_Z, trammel.CARRIER_TOP_Z + riser.THICKNESS
        ),
        "feed lever": (
            trammel.CARRIER_TOP_Z, trammel.CARRIER_TOP_Z + feed_lever.LEVER_THICK
        ),
    }
    bounds = retention.capture_bounds()
    for name, outline in spec.CARRIER_OUTLINES.items():
        fixture = fixtures[f"{pass_name}: {name}"]
        bottom, top = normal_z[name]
        rise = max(
            retention.point_lift_bound(point, pass_name, bounds) for point in outline
        )
        assert fixture.z_max >= top + rise - 1e-9
        assert fixture.z_min <= bottom - bounds.support_drop + 1e-9


@pytest.mark.parametrize("pass_name", ("inner", "outer"))
def test_cap_fixture_prisms_include_registered_yaw_and_vertical_release(pass_name: str) -> None:
    bounds = retention.capture_bounds()
    fixtures = {
        fixture.label: fixture
        for fixture in spec.captured_fixture_envelopes(samples=3)
    }
    for rail, (origin, _rows) in zip(spec.RAILS, spec.PLACEMENTS[spec.PIVOT_CAP], strict=True):
        fixture = fixtures[f"{pass_name}: pivot cap {rail}"]
        assert fixture.z_max >= origin[2] + retention.CAP_HEIGHT + bounds.cap_top_rise
        for theta in spec.sweep_thetas(pass_name, samples=21):
            station = spec.carriage_stations(pass_name, theta)[rail] + pivot_block.BORE_X
            for sign in (-1.0, 1.0):
                yaw = sign * bounds.cap_yaw
                for x in (-retention.CAP_WIDTH / 2.0, retention.CAP_WIDTH / 2.0):
                    for y in (-retention.CAP_LENGTH / 2.0, retention.CAP_LENGTH / 2.0):
                        turned = (
                            x * math.cos(yaw) - y * math.sin(yaw),
                            x * math.sin(yaw) + y * math.cos(yaw),
                        )
                        assert _inside_xy(fixture.xy, trammel.rail_point(
                            rail, station + turned[0], turned[1],
                        ))

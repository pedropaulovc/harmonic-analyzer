"""Offline contract for the oblique-trammel jig assembly (MHA-CH-006-TL-000).

The poses close on the calculator's rail and carrier geometry and the leadscrew
feed's layout, the builder places all twenty-nine made and bought families,
one free DOF slides the carriages and what rides them, the interference
contracts are the specs' press fits and threads, the jig stays a shop fixture
outside the machine tree, and the sweep of both passes clears the table and
the column cover by the pinned margins.
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
import _interference_contracts as contracts
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_bearing_spec as bearing
import ch_rocker_arm_tl_oblique_block_washer_spec as block_washer
import ch_rocker_arm_tl_oblique_carriage_spec as carriage
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_cl_dowel_spec as cl_dowel
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_oblique_flange_nut_spec as flange_nut
import ch_rocker_arm_tl_oblique_handwheel_spec as handwheel
import ch_rocker_arm_tl_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import ch_rocker_arm_tl_oblique_end_bracket_spec as end_bracket
import ch_rocker_arm_tl_oblique_leadscrew_nut_spec as leadscrew_nut
import ch_rocker_arm_tl_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_leadscrew_stock_spec as leadscrew_stock
import ch_rocker_arm_tl_oblique_nut_bracket_spec as nut_bracket
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_t_nut_spec as t_nut
import ch_rocker_arm_tl_oblique_trammel_spec as trammel


BUILDER = Path(__file__).with_name("build_ch_rocker_arm_tl_oblique_jig_assembly.py")
JIG = "ch_rocker_arm_tl_oblique_jig"
PART_STEMS = {stem.replace("-", "_") for stem in spec.BOM_ORDER}
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
}


def _image(rows, origin, point):
    """Machine coordinates of a part-frame ``point`` placed at ``origin``."""
    return tuple(
        origin[axis] + sum(point[k] * rows[k][axis] for k in range(3))
        for axis in range(3)
    )


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
        trammel.CARRIER_TOP_Z - pivot_pin.CARRIER_TOP_SHORTFALL
    )


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
    assert riser_hub[:2] == pytest.approx(hub, abs=5e-3)  # printed to 0.01
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


def test_end_brackets_stand_on_bar_1_under_the_screw() -> None:
    """Each TL-28 stands on bar 1's top at its KP08 station: its M4 pair
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
        spec.PIVOT_BLOCK: 90.0,
        spec.NUT_BRACKET: 90.0,
        spec.LEADSCREW_NUT: 90.0,
        spec.BLOCK_SCREW: 90.0,
        spec.NUT_SCREW: 90.0,
        spec.BLOCK_LOCK_WASHER: 90.0,
        spec.PIVOT_PIN: 150.0,
        spec.CARRIAGE_SCREW: 150.0,
        spec.CARRIER: 230.0,
        spec.CL_DOWEL: 260.0,
        spec.RISER: 290.0,
        spec.FEED_LEVER: 290.0,
        spec.RISER_SCREW: 320.0,
        spec.CLAMP_SCREW: 330.0,
        spec.LEVER_SCREW: 330.0,
    }
    # Sideways only where a part leaves sideways: rail 1 runs along -X, so the
    # nut screws back out along +X and the handwheel slides off along -X; the
    # block screws back out of pivot block 1's -Y face, their wedge-lock pairs
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
    # The HUB pin leaves downward, the way step 10 presses it in from below;
    # the pivot pins leave upward, the way step 4 presses them in from above.
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
    assert spec.ISOMETRIC_VIEW.startswith("ISO ")
    # The builder names them and leaves SolidWorks' standard views alone.
    source = BUILDER.read_text(encoding="utf-8")
    build = source[source.index("async def build(") :]
    assert "name_machine_views(adapter)" in build
    assert "UpdateStandardViews" not in source


def test_steps_state_the_pin_direction_and_the_finished_holes() -> None:
    steps = {line.split(". ", 1)[0]: line for line in spec.ASSEMBLY_STEPS}
    # Review bought-r15: each press loads only the ring it fits, the pin
    # still entering from the top face, collar up.
    step4 = steps["4"]
    for text in (
        "PIVOT PIN (ITEM 4), BEARING END FIRST, UNTIL ITS INNER RACE SEATS ON THE "
        "COLLAR, PUSHING ON THE INNER RACE ONLY.",
        "PRESS THE PIN DOWN FROM THE BLOCK'S TOP FACE, PUSHING ON THE OUTER RACE ONLY",
        "WITH A FLAT DRIVER ON BOTH RACES",
    ):
        assert text in step4
    # The DRO reads the table: the alignment step zeroes it on the spindle.
    assert "ZERO THE DRO X AND Y ON THE SPINDLE ORIGIN (SHEET 1)" in steps["6"]
    assert "A1 AND B1 (INNER PASS, TAGGED ON SHEET 1)" in steps["9"]
    step10 = steps["10"]
    assert "TRAVELER" not in " ".join(spec.ASSEMBLY_STEPS)
    assert "GAUGE" not in step10
    for text in (
        # c3-r7 (rule 4): the H7 names its press fit, item and interference;
        # c4-r10 (rule 25): the item is the sheet's, after the two brackets.
        "HUB Ø10.20 H7 (10.200/10.218) THRU, PRESS FIT ON THE HUB LOCATOR PIN, "
        "ITEM 8 (0.000-0.029 INTERFERENCE)",
        "CL Ø6 N7 (5.984/5.996) THRU",
        "Ø6 X 20 M6 DOWEL (6.004/6.012)",
        "LOCATED ON MHA-CH-006-TL-21 FROM THE A1-B1 PIN AXES",
        # close-c3-r3 review: squareness and position need an acceptance,
        # so the step names the setup that holds them.
        "DRILL AND REAM ITS HUB AND CL HOLES OFF THEIR SPOTS",
        "EACH IN ONE SETUP SQUARE TO THE CARRIER TOP:",
        # Codex (#1582): the title block sets no minimum break.
        "BREAK THE HUB HOLE BELOW 0.3 MIN X 45°.",
    ):
        assert text in step10
    assert hub_pin.SHOULDER_FILLET_RADIUS <= hub_pin.HUB_HOLE_UNDERSIDE_BREAK_MIN
    # Review r11 (TL-000): the change to the outer pass, the alignment it
    # keeps, and the pass the jig ships on; the handwheel holds carriage 1.
    # Review bought-r5: the block screws' as-shipped state (in, as the
    # handwheel needs them; the checks take them out for the lever).
    # Review bought-r6 (rule 23): at the torque their preload holds by.
    for text in (
        "RUN CARRIAGE 1 BY THE HANDWHEEL",
        "SLIDE CARRIAGE 2 UNTIL THE PINS MEET A2/B2",
        "THE STEP 6 READINGS STAND",
        "SHIP ON A1/B1, BLOCK SCREWS "
        f"(ITEM {spec.ITEM_NUMBERS[spec.BLOCK_SCREW]}) IN AT 4.4 N·m.",
    ):
        assert text in steps["13"]
    # Review bought-r6 (rule 23): the block screws seat on wedge-lock pairs
    # and are tightened, in the alignment order, to the derived torque.
    assert (
        "REFIT THE NUT BRACKET FROM THE BLOCK'S FAR FACE WITH 2 #8-32 X 1-7/8 SHCS "
        f"(ITEM {spec.ITEM_NUMBERS[spec.BLOCK_SCREW]}) ON WEDGE-LOCK PAIRS "
        f"(ITEM {spec.ITEM_NUMBERS[spec.BLOCK_LOCK_WASHER]}), SNUG."
    ) in steps["7E"]
    # Review bought-r15: step 7 is one operation a line; the taps go in the
    # nut bracket's spots, the pivot block stays on its carriage, its side
    # holes plain.
    assert [label for label in steps if label.startswith("7")] == [
        "7A",
        "7B",
        "7C",
        "7D",
        "7E",
    ]
    assert "RAIL 1'S PIVOT BLOCK (STILL ON ITS CARRIAGE)" in steps["7C"]
    spot = "SPOT THE NUT BRACKET THROUGH THE BLOCK'S 2 Ø4.98 SIDE HOLES"
    assert spot in steps["7C"]
    assert (
        "UNCLAMP THE NUT BRACKET, DRILL AND TAP ITS 2 SPOTS #8-32 PER "
        "MHA-CH-006-TL-29; THE BLOCK'S HOLES STAY PLAIN."
    ) in steps["7D"]
    assert "THEN THE BRACKET'S BLOCK SCREWS TO 4.4 N·m, THEN THE KP08" in steps["8"]
    # Review bought-r5: the turned-over bar is told by a feature its views
    # show; the lubricants are named; every set screw sits on a flat.
    assert "NEAR SLOT" not in steps["1"]
    assert "THE OTHER TURNED OVER FOR RAIL 2, ITS COUNTERBORES UP." in steps["1"]
    assert steps["3"].startswith("3. SLIDE A FACTORY-GREASED HGH15CA CARRIAGE")
    assert (
        f"THREAD THE LEADSCREW (ITEM {spec.ITEM_NUMBERS[spec.LEADSCREW]}), OILED "
        "WITH ISO VG 32 OIL, IN FROM THE BAR'S FAR END"
    ) in steps["7B"]
    assert "TIGHTEN ITS AND THE KP08 SET SCREWS ON THE SCREW'S FLATS." in steps["8"]
    # The limits are the parts' own fits: the HUB pin's p6 seat presses into
    # the H7, the dowel's m6 into the N7.
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


def _builder_parts() -> tuple[str, ...]:
    """The builder's literal ``_PARTS``: the build graph resolves the jig's
    part sources from these strings, so they must be the spec's families."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and [
            getattr(target, "id", None) for target in node.targets
        ] == ["_PARTS"]:
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("the jig builder has no literal _PARTS")


def test_builder_places_exactly_the_inventory() -> None:
    assert _builder_parts() == spec.BOM_ORDER
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
    }
    assert sum(spec.QUANTITIES.values()) == 88
    assert spec.QUANTITIES[spec.END_BRACKET] == (leadscrew.END_BRACKET_QUANTITY)
    assert spec.QUANTITIES[spec.NUT_BRACKET] == leadscrew.NUT_BRACKET_QUANTITY
    assert spec.QUANTITIES[spec.BASE_BAR] == base_bar.QUANTITY
    assert spec.QUANTITIES[spec.HOLD_DOWN_STUD] == fasteners.HOLD_DOWN_STUD_COUNT
    for stem, row in SCREW_ROWS.items():
        assert spec.QUANTITIES[stem] == row.count, stem
    # TL-20 is one part in one configuration: no placement names one.
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    assert not [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "place_component"
            and any(keyword.arg == "configuration" for keyword in node.keywords)
        )
        or (
            isinstance(node, ast.Dict)
            and any(
                isinstance(key, ast.Constant) and key.value == "configuration"
                for key in node.keys
            )
        )
    ]
    assert set(bg.references_of(JIG)) == PART_STEMS
    assert len(PART_STEMS) == 30


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
    for pair in pairs:
        if pair == hub or spec.CL_DOWEL + "-1" in pair:
            continue
        (insert,) = [n for n in pair if n.rsplit("-", 1)[0] in inserted]
        (receiver,) = pair - {insert}
        stem, number = insert.rsplit("-", 1)
        receiving, _number = receiver.rsplit("-", 1)
        # Each pair names the receiving instance the insert actually sits in.
        origin = spec.PLACEMENTS[stem][int(number) - 1][0]
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
    assert max(map(len, spec.BOM_DESCRIPTIONS.values())) <= spec.BOM_DESCRIPTION_CHARS
    assert spec.ITEM_NUMBERS == {
        stem: str(index) for index, stem in enumerate(spec.BOM_ORDER, 1)
    }
    assert spec.BOM_DESCRIPTIONS[spec.BASE_BAR] == "BASE BAR"
    assert spec.BOM_DESCRIPTIONS[spec.END_BRACKET] == "END BRACKET"
    assert spec.BOM_DESCRIPTIONS[spec.NUT_BRACKET] == "NUT BRACKET"
    assert spec.BOM_DESCRIPTIONS[spec.LEADSCREW] == "TR8X2 LEADSCREW, 410 LONG"
    assert "3 IN" in spec.BOM_DESCRIPTIONS[spec.HOLD_DOWN_STUD]
    for stem, row in SCREW_ROWS.items():
        assert spec.BOM_DESCRIPTIONS[stem].startswith(fasteners.callout(row)), stem
    # The fitter text cites every bought item by its BOM item number and names
    # each screw by its callout.
    steps = " ".join(spec.ASSEMBLY_STEPS)
    for stem in spec.BOM_ORDER[spec.BOM_ORDER.index(spec.RAIL) :]:
        assert f"(ITEM {spec.ITEM_NUMBERS[stem]})" in steps, stem
    for name in (
        "HGR15R",
        "HGH15CA",
        "6200-2RS",
        "CL DOWEL",
        "HOLD-DOWN",
        "KP08",
        "LEADSCREW",
        "FLANGED NUT",
        "HANDWHEEL",
        *(fasteners.callout(row) for row in fasteners.FASTENERS),
    ):
        assert name in steps
    assert "3 IN" in steps
    # The nut does not back-drive: the lever check runs with the block screws
    # out, the handwheel check with them in.
    checks = " ".join(spec.ASSEMBLY_CHECKS)
    assert "BLOCK SCREWS OUT" in checks and "HANDWHEEL" in checks


def test_bom_follows_the_part_registry() -> None:
    prefix = spec.DRAWING_NUMBER.rsplit("-", 1)[0] + "-"
    rows = {stem: _config.parts(stem) for stem in spec.BOM_ORDER}
    numbers = [
        int(rows[stem]["number"].removeprefix(prefix)) for stem in spec.BOM_ORDER
    ]
    # Registry order TL-20..50 (TL-27 is not a jig component).
    assert numbers == [20, 21, 22, 23, 24, 25, 26, 28, 29, *range(30, 51)]
    for stem, number in zip(spec.BOM_ORDER, numbers, strict=True):
        row = rows[stem]
        assert row["quantity"] == spec.QUANTITIES[stem], stem
        assert (row["process"] == "purchased") == (number >= 30), stem
        # The registry owns each bought item's source: no supplier or SKU
        # leaks into the BOM text.
        description = spec.BOM_DESCRIPTIONS[stem].casefold()
        for source in (row.get("supplier"), *row.get("supplier_skus", ())):
            assert not source or str(source).casefold() not in description, stem


def test_jig_is_a_shop_fixture_outside_the_machine_tree() -> None:
    assert bg.is_shop_fixture(JIG)
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
    assert report.cover_clearance == pytest.approx(
        {
            "carrier": 113.29,
            "riser": 150.80,
            "feed lever": 236.58,
            "HUB pin head": 169.49,
            "pivot block 1": 178.89,
            "pivot block 2": 178.89,
            "carriage 1": 184.61,
            "carriage 2": 184.61,
            "nut bracket": 135.28,
            # Ruling A′: each bracket's outer end moved 4.4 out to bar 1's
            # column-side edge (lateral 88.9).
            "end bracket near": 111.45,
            "end bracket far": 164.49,
            "KP08 near": 114.81,
            "KP08 far": 167.86,
            "screw": 141.19,
            "handwheel": 179.91,
        },
        abs=0.01,
    )
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
    assert spec.STUD_LENGTH_MAX == pytest.approx(89.7, abs=1e-6)
    # The 1/2-13 x 3 in stud is the only stud; step 2 states the limit,
    # rounded down to 1/8 in.
    assert spec.STUD_LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM
    assert spec.STUD_LENGTH == pytest.approx(3.0 * trammel.INCH)
    assert spec.STUD_LENGTH < spec.STUD_LENGTH_MAX
    step2 = spec.ASSEMBLY_STEPS[1]
    assert "1/2-13 X 3 IN STUDS ONLY" in step2
    assert "A STUD OVER 3-1/2 IN REACHES THE SWINGING CARRIER" in step2


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


def test_one_step_spots_the_riser_holes_before_screwing_it_down() -> None:
    # TL-24's hole-location note sends the shop to TL-000: exactly one step
    # spots the riser's holes through the carrier's before it is screwed down.
    spotting = [line for line in spec.ASSEMBLY_STEPS if "SPOT ITS 7 HOLES" in line]
    assert len(spotting) == 1
    step = spotting[0]
    assert (
        "SPOT ITS 7 HOLES (4 #4 COUNTERSUNK, HUB Ø12, CL DOWEL, CR SCREW Ø6.60) "
        "FROM BELOW "
        "THROUGH THE CARRIER'S FINISHED AND TAPPED HOLES"
    ) in step
    assert "MHA-CH-006-TL-24" in step
    # Codex (#1583): only the B18.6.3 machine-screw head fits the countersinks.
    assert (
        f"WITH 4 #4-40 X 1/2 B18.6.3 FLAT HEADS (ITEM {spec.ITEM_NUMBERS[spec.RISER_SCREW]})."
        in step
    )
    assert step.index("SPOT") < step.index("SCREW IT DOWN")
    # Codex (#1583): the pins would plug the holes the riser is spotted
    # through, so they press in only after the riser is screwed down.
    assert step.index("SCREW IT DOWN") < step.index("PRESS THE HUB PIN UP")
    assert not any("PRESS THE HUB PIN" in line for line in spec.ASSEMBLY_STEPS[:8])
    # Codex (#1582): the HUB pin's top is faced to fit once the riser is down
    # (rule 19), its lead chamfer cut again, no larger than the strap
    # engagement allows (Codex #1582).
    facing = (
        f"FACE THE HUB PIN'S TOP {hub_pin.LOCATOR_SET_MIN:.2f}-"
        f"{hub_pin.LOCATOR_SET_MAX:.2f} ABOVE THE RISER AND RECHAMFER IT "
        "0.5 X 45° MAX."
    )
    assert facing in step
    assert step.index("PRESS THE HUB PIN UP") < step.index(facing)
    # The CR screw clamps the workpiece, which is not part of the jig; the
    # in-use note rides on step 12, where the steps sheet has room.
    steps = {line.split(". ", 1)[0]: line for line in spec.ASSEMBLY_STEPS}
    assert "MHA-CH-013 STRAP BLANK (NOT SUPPLIED)" in steps["12"]


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
# engagement less the receiving thread's depth; below zero, the screw stops
# inside the part (THRU tap) or short of the full thread (blind tap).
FASTENER_TABLE = {
    "RAIL_TO_BAR": ("#8-32 X 3/4 SHCS", 14, 9.35, -3.35),
    "BRACKET_TO_BAR": ("#8-32 X 5/8 SHCS", 8, 7.975, -4.725),
    "NUT_BRACKET_TO_BLOCK": ("#8-32 X 1-7/8 SHCS", 2, 9.485, -2.515),
    "BLOCK_TO_CARRIAGE": ("M4 X 20 SHCS", 8, 4.4, -0.6),
    "KP08_TO_BRACKET": ("M4 X 12 SHCS", 4, 7.0, -5.7),
    "NUT_TO_NUT_BRACKET": ("M3 X 10 SHCS", 4, 6.5, -0.8),
    "RISER_TO_CARRIER": ("#4-40 X 1/2 B18.6.3 FLAT HEAD", 4, 6.7, -5.3),
    "CR_CLAMP": ("1/4-20 X 3/4 SHCS", 1, 10.55, -1.45),
    "LEVER_TO_CARRIER": ("5/16-18 X 7/8 SHCS", 2, 9.525, -2.475),
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
    # Counts follow the parts: 7 rail holes on each of 2 rails, a 4-hole
    # pattern on each carriage, 2 KP08 screws on each of 2 brackets.
    assert fasteners.RAIL_TO_BAR.count == trammel.RAIL_HOLE_COUNT * 2
    assert fasteners.BLOCK_TO_CARRIAGE.count == 4 * 2
    assert fasteners.KP08_TO_BRACKET.count == 2 * leadscrew.END_BRACKET_QUANTITY
    assert fasteners.LEVER_TO_CARRIER.count == len(carrier.LEVER_HOLES)
    # Metric only where the bought part is metric; the rest ANSI UNC.
    assert {row.thread for row in fasteners.FASTENERS if row.metric} == {"M3", "M4"}
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
    # A 1 in lever screw would stand out of the carrier's underside.
    assert fasteners.inch_mm("1") - feed_lever.LEVER_THICK > carrier.THICKNESS
    # The bar screws' worst case at TL-20's bands stays inside 1.5 D .. TL-28.
    low, high = leadscrew.BAR_SCREW_ENGAGEMENT_RANGE
    assert (low, high) == pytest.approx((6.955, 8.995), abs=1e-3)
    assert 1.5 * leadscrew.SHCS_8_MAJOR < low and high < leadscrew.BRACKET_THICK
    assert leadscrew.KP08_FOOT_THICK == 5.0  # UNVERIFIED: verify on receipt
    # One wedge-lock pair under each block screw head (rule 23: those screws
    # carry the leadscrew's reversing thrust), in the row's grip.
    assert fasteners.WASHERS == (fasteners.BLOCK_LOCK_WASHER,)
    assert fasteners.BLOCK_LOCK_WASHER.count == fasteners.NUT_BRACKET_TO_BLOCK.count
    assert fasteners.NUT_BRACKET_TO_BLOCK.grip_mm == pytest.approx(
        leadscrew.BLOCK_SCREW_GRIP + fasteners.BLOCK_LOCK_WASHER.thickness_mm
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
    # half-span the round value between TL-28's #8-to-M4 wall and TL-20's
    # counterbore-to-edge wall, both at the 2.0 target at worst case.
    assert leadscrew.BAR_SCREW_LATERALS == (27.5, 44.0, 66.0, 82.5)
    assert leadscrew.BAR_SCREW_OUTER_HALF_SPAN_MIN == pytest.approx(27.343, abs=1e-3)
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
    # TL-000 step 1 prints the one torque where the bracket screws go in.
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
    assert feed.NUT_BORE_DIA == pytest.approx(feed.NUT_BODY_DIA + 0.5)
    assert feed.NUT_SCREW_ENGAGEMENT >= 2.0 * feed.NUT_SCREW_MAJOR
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
    assert leadscrew.NUT_BORE_DIA == pytest.approx(10.7)
    assert (leadscrew.NUT_SCREW_LENGTH, leadscrew.NUT_SCREW_TAP_DEPTH) == (
        10.0,
        pytest.approx(7.3),
    )
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
    assert short_nut.NUT_BORE_DIA == pytest.approx(10.5)
    big_flange = _leadscrew_with(NUT_FLANGE_DIA=25.0, NUT_FLANGE_THICK=5.0)
    assert big_flange.NUT_SCREW_LENGTH == 12.0
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

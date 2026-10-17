"""Offline contract for the oblique-trammel jig assembly (MHA-CH-006-TL-000).

The poses close on the calculator's rail and carrier geometry and the leadscrew
feed's layout, the builder places exactly the nine made families, the jig
stays a shop fixture outside the machine tree, and the sweep of both passes
clears the table, the studs, the column cover and the feed's fixed hardware by
the pinned margins.
"""

from __future__ import annotations

import dataclasses
import ast
import math
import re
import tomllib
import types
from pathlib import Path

import pytest
import yaml

import _buildgraph as bg
import _config
import _interference_contracts as contracts
import ch_rocker_arm_tl_oblique_base_bar_spec as base_bar
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_fasteners_spec as fasteners
import ch_rocker_arm_tl_oblique_feed_lever_spec as feed_lever
import ch_rocker_arm_tl_oblique_hub_pin_spec as hub_pin
import ch_rocker_arm_tl_oblique_jig_assembly_spec as spec
import ch_rocker_arm_tl_oblique_leadscrew_spec as leadscrew
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot_block
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pivot_pin
import ch_rocker_arm_tl_oblique_riser_spec as riser
import ch_rocker_arm_tl_oblique_trammel_spec as trammel


BUILDER = Path(__file__).with_name("build_ch_rocker_arm_tl_oblique_jig_assembly.py")
JIG = "ch_rocker_arm_tl_oblique_jig"
# Read here only: the spec cites ids, never this file, so the inventory stays
# out of the jig's build keys.
INVENTORY = Path(__file__).resolve().parents[1] / "process" / "shop" / "inventory.toml"
PART_STEMS = {
    "ch_rocker_arm_tl_oblique_base_bar",
    "ch_rocker_arm_tl_oblique_pivot_block",
    "ch_rocker_arm_tl_oblique_pivot_pin",
    "ch_rocker_arm_tl_oblique_carrier",
    "ch_rocker_arm_tl_oblique_riser",
    "ch_rocker_arm_tl_oblique_hub_pin",
    "ch_rocker_arm_tl_oblique_feed_lever",
    "ch_rocker_arm_tl_oblique_end_bracket",
    "ch_rocker_arm_tl_oblique_nut_bracket",
}


def _image(rows, origin, point):
    """Machine coordinates of a part-frame ``point`` placed at ``origin``."""
    return tuple(
        origin[axis] + sum(point[k] * rows[k][axis] for k in range(3))
        for axis in range(3)
    )


def _all_rows():
    yield from (rows for _origin, rows in spec.BASE_BAR_PLACEMENTS)
    yield from (rows for _origin, rows in spec.PIVOT_BLOCK_PLACEMENTS)
    yield from (rows for _origin, rows in spec.END_BRACKET_PLACEMENTS)
    yield from (
        spec.PIN_ROWS,
        spec.CARRIER_ROWS,
        spec.RISER_ROWS,
        spec.HUB_PIN_ROWS,
        spec.FEED_LEVER_ROWS,
        spec.NUT_BRACKET_ROWS,
    )


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
        assert axis == "z" and distance != 0.0
    moved = {
        family
        for _label, families, _axis, _d in spec.EXPLODE_STEPS
        for family in families
    }
    # The end brackets stay screwed to bar 1; the nut bracket lifts with
    # pivot block 1, which it is bolted to.
    assert moved == set(spec.QUANTITIES) - {spec.BASE_BAR, spec.END_BRACKET}
    lift = {family: spec.explode_lift(family) for family in spec.QUANTITIES}
    assert lift == {
        spec.BASE_BAR: 0.0,
        spec.END_BRACKET: 0.0,
        spec.PIVOT_BLOCK: 60.0,
        spec.NUT_BRACKET: 60.0,
        spec.PIVOT_PIN: 120.0,
        spec.CARRIER: 190.0,
        spec.HUB_PIN: 40.0,
        spec.RISER: 250.0,
        spec.FEED_LEVER: 250.0,
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
    assert (
        "PRESS A PIVOT PIN DOWN FROM THE BLOCK'S TOP FACE, BEARING END FIRST, "
        "THROUGH BOTH INNER RACES UNTIL ITS COLLAR SEATS ON THE UPPER RACE."
    ) in steps["4"]
    assert "A1 AND B1 (INNER PASS, TAGGED ON SHEET 1)" in steps["9"]
    step10 = steps["10"]
    assert "TRAVELER" not in " ".join(spec.ASSEMBLY_STEPS)
    assert "GAUGE" not in step10
    for text in (
        "HUB Ø10.20 H7 (10.200/10.218) THRU",
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
    for text in (
        "RUN CARRIAGE 1 BY THE HANDWHEEL",
        "SLIDE CARRIAGE 2 UNTIL THE PINS MEET A2/B2",
        "THE STEP 6 READINGS STAND",
        "SHIP ON A1/B1.",
    ):
        assert text in steps["13"]
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


def _placed_stems() -> list[str]:
    """Literal part stems the builder hands its placement wrapper."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    return [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_place_fixed"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
    ]


def test_builder_places_exactly_the_inventory() -> None:
    assert sorted(set(_placed_stems())) == sorted(spec.QUANTITIES)
    assert sorted(spec.BOM_ORDER) == sorted(spec.QUANTITIES)
    assert spec.QUANTITIES == {
        spec.BASE_BAR: 2,
        spec.PIVOT_BLOCK: 2,
        spec.PIVOT_PIN: 2,
        spec.CARRIER: 1,
        spec.RISER: 1,
        spec.HUB_PIN: 1,
        spec.FEED_LEVER: 1,
        spec.END_BRACKET: 2,
        spec.NUT_BRACKET: 1,
    }
    assert spec.BOM_ORDER[-2:] == (spec.END_BRACKET, spec.NUT_BRACKET)
    assert spec.QUANTITIES[spec.END_BRACKET] == (leadscrew.END_BRACKET_QUANTITY)
    assert spec.QUANTITIES[spec.NUT_BRACKET] == leadscrew.NUT_BRACKET_QUANTITY
    assert spec.QUANTITIES[spec.BASE_BAR] == base_bar.QUANTITY
    # TL-20 is one part in one configuration: no placement names one.
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    assert not [
        keyword.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) in {"_place_fixed", "place_component"}
        for keyword in node.keywords
        if keyword.arg == "configuration"
    ]
    assert set(bg.references_of(JIG)) == PART_STEMS


def test_assembly_contract_is_fully_fixed() -> None:
    path = _config.CONFIG_DIR / "assemblies" / f"{spec.ASM_NAME}.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert contract["number"] == spec.DRAWING_NUMBER
    assert contract["free_dof"] == 0
    assert contract["allowed_free_stems"] == []
    assert contract["required_free_stems"] == []


def test_hub_pin_is_the_only_allowed_interference() -> None:
    assert contracts.JIG_HUB_PIN_SEAT == (hub_pin.FIT_DIA, hub_pin.SEAT_LENGTH)
    assert hub_pin.SEAT_LENGTH == trammel.CARRIER_THICK
    pairs = contracts.allowed_interference_pairs(spec.ASM_NAME)
    assert set(pairs) == {frozenset((f"{spec.HUB_PIN}-1", f"{spec.CARRIER}-1"))}
    seat = math.pi * hub_pin.FIT_DIA**2 * hub_pin.SEAT_LENGTH / 4.0
    assert next(iter(pairs.values())) == pytest.approx(1.10 * seat)


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


def test_bom_rows_name_every_made_and_bought_item() -> None:
    assert set(spec.BOM_DESCRIPTIONS) == set(spec.QUANTITIES)
    assert spec.BOM_DESCRIPTIONS[spec.BASE_BAR] == "BASE BAR"
    ids = [item.inventory_id for item in spec.BOUGHT_ITEMS]
    assert len(ids) == len(set(ids)) and all(i.startswith("fixtures.") for i in ids)
    quantities = {item.inventory_id: item.quantity for item in spec.BOUGHT_ITEMS}
    assert quantities == {
        "fixtures.trammel-hgr15-rails": 2,
        "fixtures.trammel-hgh15ca-carriages": 2,
        "fixtures.trammel-6200-2rs": 4,
        "fixtures.trammel-cl-dowel": 1,
        "fixtures.clamping-kit-pm-52pcck-14mm": 4,
        leadscrew.SCREW_ID: 1,
        leadscrew.NUT_ID: 1,
        leadscrew.KP08_ID: 2,
        leadscrew.HANDWHEEL_ID: 1,
    }
    assert spec.BOM_DESCRIPTIONS[spec.END_BRACKET] == "END BRACKET"
    assert spec.BOM_DESCRIPTIONS[spec.NUT_BRACKET] == "NUT BRACKET"
    descriptions = {item.inventory_id: item.description for item in spec.BOUGHT_ITEMS}
    assert descriptions[leadscrew.SCREW_ID] == "TR8X2 LEADSCREW, 410 LONG"
    # The fitter text names every bought item and the screws it consumes.
    steps = " ".join(spec.ASSEMBLY_STEPS)
    for name in (
        "HGR15R",
        "HGH15CA",
        "6200-2RS",
        "CL DOWEL",
        "HOLD-DOWN",
        "#8-32",
        "M4",
        "KP08",
        "LEADSCREW",
        "FLANGED NUT",
        "HANDWHEEL",
        *(
            fasteners.callout(row)
            for row in fasteners.FASTENERS
            if row is not fasteners.CR_CLAMP  # fitted per the traveler
        ),
        "#8-32 X 3/4 SHCS",
        "#8-32 X 5/8 SHCS",
        "#8-32 X 1-3/4 SHCS",
        "M4 X 20 SHCS",
        "M4 X 12 SHCS",
        "M3 X 10 SHCS",
        "#4-40 X 1/2 B18.6.3 FLAT HEAD",
        "5/16-18 X 7/8 SHCS",
    ):
        assert name in steps
    assert "3 IN" in steps
    assert "3 IN" in descriptions["fixtures.clamping-kit-pm-52pcck-14mm"]
    # The nut does not back-drive: the lever check runs with the block screws
    # out, the handwheel check with them in.
    checks = " ".join(spec.ASSEMBLY_CHECKS)
    assert "BLOCK SCREWS OUT" in checks and "HANDWHEEL" in checks


def _inventory_entry(inventory: dict, inventory_id: str) -> dict:
    entry = inventory
    for key in inventory_id.split("."):
        assert isinstance(entry, dict) and key in entry, inventory_id
        entry = entry[key]
    assert isinstance(entry, dict), inventory_id
    return entry


def test_bought_items_resolve_in_the_shop_inventory() -> None:
    inventory = tomllib.loads(INVENTORY.read_text(encoding="utf-8"))
    assert "sku" not in {field.name for field in dataclasses.fields(spec.BoughtItem)}
    for item in spec.BOUGHT_ITEMS:
        entry = _inventory_entry(inventory, item.inventory_id)
        # The inventory owns the source: no make or SKU leaks into the BOM text.
        description = item.description.casefold()
        for field in ("make", "sku"):
            if field in entry:
                assert str(entry[field]).casefold() not in description, (
                    item.inventory_id,
                    field,
                )
    # The spec never reads the inventory, so it stays out of the build keys.
    assert "tomllib" not in Path(spec.__file__).read_text(encoding="utf-8")


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


def _gap(gaps, a, b):
    """The pinned gap between two named families, whichever order holds it."""
    hits = [value for (p, q), value in gaps.items() if {p, q} == {a, b}]
    assert len(hits) == 1, (a, b, sorted(gaps))
    return hits[0]


def test_sweep_keeps_every_moving_item_off_the_fixed_ones(report) -> None:
    assert min(report.plan_gaps.values()) > 0.0
    assert min(report.height_gaps.values()) > 0.0
    for rail in spec.RAILS:
        # The tightest plan gaps: each carriage passes its far flange nut, each
        # pivot block its far stud, at the outer pass's far end.
        assert _gap(
            report.plan_gaps, f"carriage {rail}", f"far stud {rail} flange nut"
        ) == (pytest.approx(6.50, abs=0.01))
        assert _gap(report.plan_gaps, f"pivot block {rail}", f"far stud {rail}") == (
            pytest.approx(11.15, abs=0.01)
        )
        assert _gap(report.height_gaps, f"carriage {rail}", f"base bar {rail}") == (
            pytest.approx(4.30, abs=0.01)
        )
        assert _gap(report.height_gaps, f"pivot block {rail}", f"rail {rail}") == (
            pytest.approx(13.0, abs=0.01)
        )
        for which in ("near", "far"):
            # A 3 in stud stands 13.5 under the carrier.
            assert _gap(report.height_gaps, "carrier", f"{which} stud {rail}") == (
                pytest.approx(13.5, abs=0.01)
            )
    # The feed: the nut bracket (centred on the pivot block's side screws)
    # rides 2.88 past the far KP08's envelope (its 3 margin included) at the
    # travel's far end, its flipped nut 2.97 past the near one's at the near
    # end; carriage 1 passes 3 inside each leadscrew
    # bracket; the HUB pin head clears the near KP08's envelope by 6.3 and the
    # nut bracket stops 5 under the carrier.
    assert _gap(report.plan_gaps, "nut bracket", "KP08 far") == pytest.approx(
        2.88, abs=0.01
    )
    assert _gap(report.plan_gaps, "nut bracket", "KP08 near") == pytest.approx(
        2.97, abs=0.01
    )
    for which in ("near", "far"):
        assert _gap(
            report.plan_gaps, "carriage 1", f"end bracket {which}"
        ) == pytest.approx(3.0, abs=0.01)
        assert _gap(report.plan_gaps, "pivot block 1", f"KP08 {which}") == (
            pytest.approx(4.5, abs=0.01)
        )
    # The pivot pin's collar is the bar's own Ø12.70 (review r11, TL-23).
    assert _gap(report.plan_gaps, "pivot pin 1", "nut bracket") == pytest.approx(
        15.69, abs=0.01
    )
    assert _gap(report.plan_gaps, "carriage 1", "handwheel") == pytest.approx(
        16.85, abs=0.01
    )
    assert _gap(report.height_gaps, "HUB pin head", "KP08 near") == pytest.approx(
        6.3, abs=0.01
    )
    assert _gap(report.height_gaps, "nut bracket", "carrier") == pytest.approx(
        5.0, abs=0.01
    )
    assert _gap(report.height_gaps, "carrier", "KP08 near") == pytest.approx(
        10.3, abs=0.01
    )
    assert _gap(report.height_gaps, "nut bracket", "base bar 1") == pytest.approx(
        14.7, abs=0.01
    )
    assert min(report.plan_gaps.values()) == pytest.approx(2.88, abs=0.01)
    assert min(report.height_gaps.values()) == pytest.approx(4.30, abs=0.01)
    assert report.stud_length_max == pytest.approx(89.7, abs=1e-6)
    # The 1/2-13 x 3 in stud is the only stud; step 2 states the sweep's own
    # limit, rounded down to 1/8 in.
    assert spec.STUD_LENGTH == fasteners.HOLD_DOWN_STUD_LENGTH_MM
    assert spec.STUD_LENGTH == pytest.approx(3.0 * trammel.INCH)
    assert spec.STUD_LENGTH < report.stud_length_max
    assert spec.STUD_LENGTH_MAX == pytest.approx(report.stud_length_max)
    step2 = spec.ASSEMBLY_STEPS[1]
    assert "1/2-13 X 3 IN STUDS ONLY" in step2
    assert "ANY STUD LONGER THAN 3-1/2 IN REACHES THE SWINGING CARRIER" in step2


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
    assert "WITH 4 #4-40 X 1/2 B18.6.3 FLAT HEADS." in step
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
    # The wider bars still leave the two apart at their near ends.
    bars = spec.fixed_outlines()
    assert not spec._polygons_overlap(bars["base bar 1"], bars["base bar 2"])
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
    "NUT_BRACKET_TO_BLOCK": ("#8-32 X 1-3/4 SHCS", 2, 8.85, -3.15),
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
    assert fasteners.WASHERS == ()
    assert fasteners.HOLD_DOWN_STUD_THREAD == "1/2-13"
    assert fasteners.HOLD_DOWN_STUD_COUNT == 4


def test_turned_over_bar_counterbores_clear_the_flange_nuts() -> None:
    # Bar 2 goes on turned over, so its 8 bracket counterbores face up, empty.
    # No flange nut seats over one, and the rail's footprint misses them.
    reach = spec.FLANGE_NUT_DIA / 2.0 + base_bar.BRACKET_CBORE_DIA / 2.0
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
        "WITH 4 #8-32 X 5/8 SHCS UP FROM THE BAR'S UNDERSIDE, "
        "TORQUE 2.8 N-M (25 IN-LBF)."
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

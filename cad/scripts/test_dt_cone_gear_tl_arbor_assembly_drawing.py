"""Offline contract of the keyed arbor kit's fitter sheet (MHA-DT-03-TL-05)."""

from __future__ import annotations

import ast
import inspect
import re

import pytest

import _buildgraph as bg
import _config
import _dt_cone_gear_tl_arbor_interference as interference
import build_dt_cone_gear_tl_arbor_assembly as build
import draw_dt_cone_gear_tl_arbor_assembly as drawing
import dt_cone_gear_tl_arbor_assembly_spec as spec
import dt_cone_gear_tl_arbor_collar_spec as collar
import dt_cone_gear_tl_arbor_key_spec as key
import dt_cone_gear_tl_keyed_arbor_spec as arbor
import dt_cone_gear_tl_vn_arbor_nut_spec as nut
from _assembly_contract import assembly_contract
from _machinist_review_mode import MachinistReviewMode

KIT = "dt_cone_gear_tl_arbor"


def test_the_kit_sheet_is_a_reviewed_shop_fixture() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert assembly_contract(spec.ASM_NAME).number == "MHA-DT-03-TL-05"
    assert KIT in bg.ASSEMBLY_ORDER
    assert KIT not in bg.MACHINE_ASSEMBLIES
    assert bg.is_shop_fixture(KIT)
    for machine in bg.MACHINE_ASSEMBLIES:
        assert KIT not in bg.references_of(machine)


def test_the_bom_lists_every_kit_part_by_its_registered_number() -> None:
    families = {stem: spec.COMPONENT_IDENTITIES[stem][0] for stem in spec.BOM_ORDER}
    assert set(families.values()) == {spec.ARBOR, spec.COLLAR, spec.KEY, spec.NUT}
    for stem, family in families.items():
        assert spec.NUMBERS[stem] == _config.parts(family)["number"], stem
        assert spec.BOM_DESCRIPTIONS[stem], stem
    members = [spec.COMPONENT_IDENTITIES[s][1] for s in spec.BOM_ORDER]
    assert [m for m in members if m] == list(collar.CONFIGURATIONS)
    assert list(spec.BOM_ITEMS.values()) == [
        str(i + 1) for i in range(len(spec.BOM_ORDER))
    ]
    assert drawing.BOM_COMPONENTS == spec.BOM_ORDER
    assert nut.SKU in spec.BOM_DESCRIPTIONS[spec.NUT]


def test_the_build_inserts_the_parts_in_bom_order() -> None:
    """The steps cite item numbers, so insertion order is the BOM's."""
    tree = ast.parse(inspect.getsource(build))
    stems = [
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "place_component"
        and isinstance(node.args[1], ast.Constant)
    ]
    stems.sort(key=lambda s: inspect.getsource(build).index(f'"{s}"'))
    order = list(dict.fromkeys(spec.COMPONENT_IDENTITIES[s][0] for s in spec.BOM_ORDER))
    assert stems == order
    assert set(bg.references_of(KIT)) == {stem.replace("-", "_") for stem in order}


def test_the_kit_pose_is_the_64t_setup_on_the_arbor() -> None:
    crank_tag = arbor.KEYED_GEARS[-1].tag
    kit_collar = spec.member(spec.KIT_COLLAR)
    assert (
        collar.OD_BY_CONFIGURATION[spec.KIT_COLLAR]
        == arbor.COLLAR_DIAS[arbor.COLLAR_BY_GEAR[crank_tag]]
    )
    assert spec.POSITIONS[kit_collar][2] == pytest.approx(
        arbor.SHOULDER_Z + arbor.KIT_BLANK_FACE
    )
    assert spec.POSITIONS[spec.NUT][2] == pytest.approx(
        spec.POSITIONS[kit_collar][2] + collar.LENGTH
    )
    assert spec.POSITIONS[spec.NUT][2] + nut.THICKNESS <= arbor.ARBOR_END_Z
    x, y, z = spec.POSITIONS[spec.KEY]
    assert (x, y) == pytest.approx((key.FLOOR_OFFSET_MM, 0.0))
    assert arbor.SHOULDER_Z < z
    assert z + key.LENGTH <= arbor.SEAT_END_Z + 1e-9
    # The spare collars stand off the arbor's end, apart from each other.
    spares = sorted(
        spec.POSITIONS[spec.member(name)][2]
        for name in collar.CONFIGURATIONS
        if name != spec.KIT_COLLAR
    )
    assert spares[0] > arbor.ARBOR_END_Z
    assert spares[1] > spares[0] + collar.LENGTH


def test_the_settings_are_the_arbors_standoff_and_seat_length() -> None:
    standoff = spec.SETTINGS[spec.STANDOFF_DIMENSION]
    seat = spec.SETTINGS[spec.SEAT_DIMENSION]
    assert standoff[2] - standoff[1] == pytest.approx(arbor.STANDOFF)
    assert seat[2] - seat[1] == pytest.approx(arbor.SEAT_LENGTH)
    assert set(spec.DIMENSION_CALLOUTS) == spec.DRAWING_DIMENSIONS[spec.SETTINGS_SKETCH]
    assert set(drawing.SETTING_DROP) == set(spec.SETTINGS)


def test_three_fitting_steps_cite_real_items_and_end_on_the_clock() -> None:
    lines = spec.ASSEMBLY_STEPS.splitlines()
    steps = [line for line in lines if re.match(r"\d+\.", line)]
    assert len(steps) <= 3
    cited = set(re.findall(r"ITEM (\d+)", spec.ASSEMBLY_STEPS))
    assert cited <= set(spec.BOM_ITEMS.values())
    assert {spec.BOM_ITEMS[spec.member(name)] for name in collar.CONFIGURATIONS} <= (
        cited
    )
    last = spec.ASSEMBLY_STEPS[spec.ASSEMBLY_STEPS.index(steps[-1]) :]
    assert f"ITEM {spec.BOM_ITEMS[spec.KEY]}" in last
    assert "CENTRELINE" in last


def test_the_kit_allows_no_interference_and_has_no_free_parts() -> None:
    assert dict(interference.ALLOWED_PAIRS) == {}
    contract = assembly_contract(spec.ASM_NAME)
    assert contract.free_dof == 0

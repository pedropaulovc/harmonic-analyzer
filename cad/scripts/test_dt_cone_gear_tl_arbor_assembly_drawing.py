"""Offline contract of the keyed arbor kit's fitter sheet (MHA-DT-03-TL-05)."""

from __future__ import annotations

import ast
import inspect
import math
import re
from dataclasses import replace

import pytest

import _buildgraph as bg
import _config
import _dt_cone_gear_tl_arbor_interference as interference
import build_dt_cone_gear_tl_arbor_assembly as build
import draw_dt_cone_gear_tl_arbor_assembly as drawing
import dt_cone_gear_spec as cone
import dt_cone_gear_tl_arbor_assembly_spec as spec
import dt_cone_gear_tl_arbor_collar_spec as collar
import dt_cone_gear_tl_arbor_key_spec as key
import dt_cone_gear_tl_keyed_arbor_spec as arbor
import dt_cone_gear_tl_vn_arbor_nut_spec as nut
import dt_crank_drive_gear_spec as crank
from _assembly_contract import assembly_contract
from _cone_gear_native import native_gap_segments
from _machinist_review_mode import MachinistReviewMode
from dt_crank_drive_gear_notes import GEAR_DATA
from straight_gash import StraightGash

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


def _step(number: int) -> str:
    """Step ``number``'s printed text, its continuation lines joined."""
    lines = spec.ASSEMBLY_STEPS.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{number}. "))
    end = next(
        (i for i, line in enumerate(lines[start + 1 :], start + 1) if re.match(r"\d+\.", line)),
        len(lines),
    )
    return " ".join(line.strip() for line in lines[start:end])


def _cone_gap_span_rad(teeth: int) -> tuple[float, float]:
    """The azimuths a cone gear's modelled gap spans: its native gap equations
    (what the cone gear's model cuts), sampled along every segment."""
    angles = []
    for _name, x, y in native_gap_segments(teeth):
        for step in range(41):
            variables = {"t": step / 40.0, "cos": math.cos, "sin": math.sin}
            angles.append(
                math.atan2(
                    eval(y, {"__builtins__": {}}, variables),
                    eval(x, {"__builtins__": {}}, variables),
                )
            )
    return min(angles), max(angles)


def _off_pitches(angle: float, target: float, pitch: float) -> float:
    """How far ``angle`` stands from ``target`` modulo one pitch, radians."""
    turns = (angle - target) / pitch
    return abs(turns - round(turns)) * pitch


def test_step_3_indexes_a_cone_blank_so_a_tooth_centres_on_the_key() -> None:
    """Codjiflo P1 on #2664: with the key on the cutter centreline the first
    space is cut on the keyway (+X). Every keyed cone gear's modelled gap
    stands clear of +X, symmetric about half a pitch, so +X is a tooth; the
    step's index, either way, lands the first space on a modelled gap."""
    allowance = math.radians(arbor.KEY_SETTING_ALLOWANCE_DEG)
    for teeth in cone.KEYED_TEETH:
        pitch = 2.0 * math.pi / teeth
        low, high = _cone_gap_span_rad(teeth)
        assert 0.0 < low < high < pitch, teeth  # the keyway lies in a tooth
        bisector = (low + high) / 2.0
        for sense in (1.0, -1.0):
            first = sense * spec.CONE_FIRST_INDEX_PITCHES * pitch
            assert _off_pitches(first, bisector, pitch) < allowance, (teeth, sense)
        # No index at all would cut a space where the model has its tooth.
        assert _off_pitches(0.0, bisector, pitch) > allowance, teeth
    assert "THEN INDEX HALF A PITCH" in _step(3)


def _midface_gap_rad(space: StraightGash) -> float:
    """Where ``space``'s centre line meets the 64T's pitch circle at mid-face."""
    radius = crank.PITCH_DIA / 2.0
    z = crank.FACE_WIDTH / 2.0
    shift = space.transverse_offset_mm(0.0, z)
    x, y, _z = space.point(math.sqrt(radius**2 - shift**2), 0.0, z)
    return math.atan2(y, x)


def test_step_3_indexes_the_64t_so_its_mid_face_tooth_centres_on_the_key() -> None:
    """The 64T's space is straight and inclined: its cutter plane crosses the
    axis at TOOTH_SPACE_CROSSING from the chamfered (z = 0) face, and the
    model centres a tooth on the keyway at mid-face. The key on the cutter
    centreline sets the space's crossing radial on the key; the step's index
    then turns the blank so the cut space is the model's, inside the arbor's
    setting allowance, where half a pitch is not."""
    pitch = 2.0 * math.pi / crank.TEETH
    allowance = math.radians(arbor.KEY_SETTING_ALLOWANCE_DEG)
    model = _midface_gap_rad(crank.TOOTH_SPACE)
    assert model == pytest.approx(pitch / 2.0, abs=1e-9)  # a tooth on +X
    assert crank.TOOTH_SPACE.crossing_z_mm == crank.TOOTH_SPACE_CROSSING
    assert "FROM CHAMFERED BORE FACE" in GEAR_DATA
    # Turning the blank by a about its +z carries a cutter fixed in space to
    # gear azimuth -a; counter-clockwise seen from the z = 0 face (looking
    # along +z) is a negative turn about +z.
    sense = {
        "COUNTER-CLOCKWISE SEEN FROM ITS CHAMFERED FACE": 1.0,
        "CLOCKWISE SEEN FROM ITS CHAMFERED FACE": -1.0,
    }[spec.CRANK_FIRST_INDEX_SENSE]
    cut = replace(
        crank.TOOTH_SPACE, azimuth_rad=sense * math.radians(spec.CRANK_FIRST_INDEX_DEG)
    )
    assert _off_pitches(_midface_gap_rad(cut), model, pitch) < allowance
    half = replace(crank.TOOTH_SPACE, azimuth_rad=pitch / 2.0)
    assert _off_pitches(_midface_gap_rad(half), model, pitch) > allowance
    step = _step(3)
    assert f"({crank.TEETH}T: {spec.CRANK_FIRST_INDEX_DEG:.2f}°," in step
    assert spec.CRANK_FIRST_INDEX_SENSE in step
    assert sum(1 for line in spec.ASSEMBLY_STEPS.splitlines() if line) <= 1 + 3 * 6


def test_the_frozen_rims_stand_mid_line_on_their_own_edges() -> None:
    """Each frozen balloon lands on a real rim (its part's own edge), on the
    viewer's (+X) half, and its point stands at least 2 mm (sheet) from either
    end of the rim's edge-on line and from any other edge meeting that line,
    so SolidWorks cannot snap the leader to an end (farm 20261113T042822797Z:
    0.42 mm from the end snapped onto it)."""
    scale = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1]
    rims = {
        spec.ARBOR: (arbor.GRIP_DIA / 2.0, arbor.GRIP_LENGTH, arbor.STANDOFF_DIA / 2.0),
        spec.member(collar.CONFIGURATIONS[1]): (
            collar.OD_BY_CONFIGURATION[collar.CONFIGURATIONS[1]] / 2.0,
            collar.LENGTH,
            collar.BORE / 2.0,
        ),
    }
    for stem, (radius, z, inner) in rims.items():
        x, y, at = drawing.BALLOON_ANCHORS[stem].point_mm
        assert math.hypot(x, y) == pytest.approx(radius) and at == z, stem
        assert x > 0.0, stem
        assert (radius - y) * scale >= 2.0 and abs(y - inner) * scale >= 2.0, stem


def test_the_kit_allows_no_interference_and_has_no_free_parts() -> None:
    assert dict(interference.ALLOWED_PAIRS) == {}
    contract = assembly_contract(spec.ASM_NAME)
    assert contract.free_dof == 0

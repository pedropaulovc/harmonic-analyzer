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
    # The arbor's note 1 points at this sheet's setup table by its number.
    assert arbor.KIT_NUMBER == assembly_contract(spec.ASM_NAME).number
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


def test_each_collar_row_names_its_own_sheet_of_the_collar_drawing() -> None:
    """The three collars share TL-04, one sheet each: the row's description
    names its sheet, so a row identifies one part drawing."""
    for name in collar.CONFIGURATIONS:
        sheet = collar.SHEET_NAMES.index(f"COLLAR {name}") + 1
        description = spec.BOM_DESCRIPTIONS[spec.member(name)]
        assert description == (
            f"{collar.CONFIGURATION_DESCRIPTIONS[name]}, TL-04 SHEET {sheet}"
        )
    assert collar.PART_NUMBER == "MHA-DT-03-TL-04"


def _steps() -> list[str]:
    """Each numbered step with its continuation lines, as printed."""
    steps: list[str] = []
    for line in spec.ASSEMBLY_STEPS.splitlines()[1:]:
        if line[:1].isdigit():
            steps.append(line)
        else:
            assert line.startswith("   "), line
            steps[-1] += "\n" + line
    return steps


def _flat(step: str) -> str:
    return " ".join(step.split())


def _after(steps: list[str], words: str) -> list[str]:
    (index,) = (i for i, step in enumerate(steps) if words in _flat(step))
    return [_flat(step) for step in steps[index + 1 :]]


def test_the_steps_do_one_thing_each_and_check_every_joint_and_setting() -> None:
    """Rule 22: numbered, at most six printed lines, one action each; rule
    23: the bond's degrease, coat, cure and bench check, the nut's clamp and
    its check; the key's clock set on its own two side faces (an indicator
    zeroed on one, the head turned half a turn), checked with its band, its
    remedy a separate step; then the quarter turn to the cutter and the
    index last."""
    steps = _steps()
    assert [step.split(".", 1)[0] for step in steps] == [
        str(number) for number in range(1, len(steps) + 1)
    ]
    assert all(len(step.splitlines()) <= 6 for step in steps)
    assert all(
        len(line) <= spec.STEP_WIDTH for line in spec.ASSEMBLY_STEPS.splitlines()
    )
    for step in steps:
        body = _flat(step).split(". ", 1)[1]
        assert body.count(". ") == 0 and "; " not in body and " THEN " not in body
    cited = set(re.findall(r"ITEM (\d+)", spec.ASSEMBLY_STEPS))
    assert cited <= set(spec.BOM_ITEMS.values())
    k, a, n = (spec.BOM_ITEMS[s] for s in (spec.KEY, spec.ARBOR, spec.NUT))
    flat = [_flat(step) for step in steps]
    order = [
        f"DEGREASE ITEM {k}",
        f"COAT ITEM {k} WITH LOCTITE 638",
        f"PUSH ITEM {k} INTO ITEM {a}'S KEYSEAT AGAINST THE KEYSEAT'S END NEAREST "
        f"ITEM {a}'S SHOULDER",
        f"OFF ITEM {a}'S Ø.376 SEAT, LEAVING THE KEYSEAT FILLED",
        "CURE 24 H",
        f"CHECK: ITEM {k} DOES NOT MOVE BY HAND",
        "SLIDE THE BLANK ONTO",
        "COLLAR (SETUP TABLE)",
        f"TIGHTEN ITEM {n}",
        "CHECK: THE BLANK DOES NOT TURN OR SLIDE BY HAND",
        f"UNTIL ITEM {k}'S SIDE FACES ARE LEVEL",
        f"ZERO A TEST INDICATOR ON ITEM {k}'S UPPER SIDE FACE",
        "TURN THE HEAD 180°",
        f"CHECK: THE INDICATOR, AT THE SAME HEIGHT, READS ZERO WITHIN "
        f"{arbor.inch_text(spec.KEY_SIDE_READING, 3)} ON ITEM {k}'S OTHER SIDE FACE",
        f"IF STEP {spec.CHECK_STEP} FAILS",
        f"TURN THE HEAD 90° UNTIL ITEM {k} FACES THE CUTTER",
        "FIRST INDEX (SETUP TABLE)",
    ]
    positions = [
        next(i for i, step in enumerate(flat) if words in step) for words in order
    ]
    assert positions == sorted(positions)
    assert flat[-1].endswith("TURN THE HEAD BY THE BLANK'S FIRST INDEX (SETUP TABLE).")
    assert len(steps) == spec.INDEX_STEP
    # The step numbers the remedy cites are the zeroing and the check.
    assert "ZERO A TEST INDICATOR" in flat[spec.ZERO_STEP - 1]
    assert flat[spec.CHECK_STEP - 1].startswith(f"{spec.CHECK_STEP}. CHECK:")
    assert flat[spec.CHECK_STEP].endswith(f"REPEAT FROM STEP {spec.ZERO_STEP}.")
    assert "CENTRE PLANE" not in spec.ASSEMBLY_STEPS


def test_the_side_face_reading_holds_the_keys_clock() -> None:
    """Turned by a small angle, both side faces move the same way by their
    radius times it: the two readings part by twice that at the least lever
    a side face shows (the keyseat's edge), well inside the allowance."""
    lever = spec.KEY_SIDE_LEVER_MIN
    assert arbor.SEAT_DIA / 2.0 > lever > arbor.KEYSEAT_FLOOR_MAX
    half_width = arbor.KEYSEAT_WIDTH / 2.0
    assert lever <= math.sqrt((arbor.SEAT_DIA / 2.0) ** 2 - half_width**2)
    turned = math.radians(spec.KEY_CLOCK_FROM_READING_DEG)
    assert 2.0 * lever * turned == pytest.approx(spec.KEY_SIDE_READING)
    assert spec.KEY_CLOCK_FROM_READING_DEG < arbor.KEY_SETTING_ALLOWANCE_DEG / 2.0


def test_the_setup_table_names_every_blank_its_collar_and_index() -> None:
    """A ruled table, a row per keyed blank by drawing number and tooth
    count, the collar the arbor's backing rule gives it, and its first index;
    every cell inside its column, the table inside the right half over the
    title block."""
    rows = spec.SETUP_TABLE_ROWS
    assert spec.SETUP_TABLE_HEADER == (
        "BLANK",
        "TEETH",
        "COLLAR",
        "FIRST INDEX",
        "DIRECTION",
    )
    assert [row[0] for row in rows] == [blank.number for blank in arbor.KEYED_GEARS]
    by_dia = {
        spec.member(name): collar.OD_BY_CONFIGURATION[name]
        for name in collar.CONFIGURATIONS
    }
    for blank, row in zip(arbor.KEYED_GEARS, rows, strict=True):
        assert row[1] == str(spec.blank_teeth(blank.tag)), row
        item = row[2].removeprefix("ITEM ")
        (stem,) = (s for s, i in spec.BOM_ITEMS.items() if i == item)
        assert by_dia[stem] == pytest.approx(
            arbor.COLLAR_DIAS[arbor.COLLAR_BY_GEAR[blank.tag]]
        ), blank.tag
    assert "ITEM 5" in spec.SETUP_TABLE_TITLE.splitlines()[1]
    widths = drawing.table_column_widths(spec.SETUP_TABLE_HEADER, rows)
    for row in (spec.SETUP_TABLE_HEADER, *rows):
        for text, width in zip(row, widths, strict=True):
            assert len(text) * drawing.TABLE_CHAR_WIDTH < width, text
    x0, y0, x1, y1 = drawing.setup_table_box()
    assert x0 >= TITLE_BLOCK[0] and x1 < 0.4191 - drawing.SHEET_CLEARANCE
    assert y0 > TITLE_BLOCK[3] + drawing.SHEET_CLEARANCE
    title = drawing.label_box(spec.SETUP_TABLE_TITLE, drawing.TABLE_XY)
    assert title[2] < 0.4191 and title[1] > y1
    # Under the parts list (its six rows end by about y 0.189, farm
    # 20261113T071241685Z) and clear of the isometric's column.
    assert drawing.TABLE_XY[1] < 0.189 - 0.004
    assert x0 > drawing.ISO_CENTER[0] + 0.05
    assert "HALF A PITCH" not in spec.SETUP_TABLE_TITLE


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


def _printed_index_deg(teeth: int) -> tuple[float, str]:
    """A blank's printed first index (degrees) and its direction cell."""
    (row,) = (row for row in spec.SETUP_TABLE_ROWS if row[1] == str(teeth))
    angle, direction = row[3], row[4]
    assert re.fullmatch(r"\d+\.\d\d°", angle), angle
    return float(angle.removesuffix("°")), direction


def test_the_table_indexes_each_cone_blank_so_a_tooth_centres_on_the_key() -> None:
    """Codjiflo P1 on #2664: with the key on the cutter centreline the first
    space is cut on the keyway (+X). Every keyed cone gear's modelled gap
    stands clear of +X, symmetric about half a pitch, so +X is a tooth; the
    table's printed index, either way, lands the first space on a modelled
    gap."""
    allowance = math.radians(arbor.KEY_SETTING_ALLOWANCE_DEG)
    for teeth in cone.KEYED_TEETH:
        pitch = 2.0 * math.pi / teeth
        low, high = _cone_gap_span_rad(teeth)
        assert 0.0 < low < high < pitch, teeth  # the keyway lies in a tooth
        bisector = (low + high) / 2.0
        printed, words = _printed_index_deg(teeth)
        assert words == "EITHER WAY", teeth
        assert printed == pytest.approx(
            spec.CONE_FIRST_INDEX_PITCHES * 360.0 / teeth, abs=0.005
        )
        for sense in (1.0, -1.0):
            first = sense * math.radians(printed)
            assert _off_pitches(first, bisector, pitch) < allowance, (teeth, sense)
        # No index at all would cut a space where the model has its tooth.
        assert _off_pitches(0.0, bisector, pitch) > allowance, teeth


def _midface_gap_rad(space: StraightGash) -> float:
    """Where ``space``'s centre line meets the 64T's pitch circle at mid-face."""
    radius = crank.PITCH_DIA / 2.0
    z = crank.FACE_WIDTH / 2.0
    shift = space.transverse_offset_mm(0.0, z)
    x, y, _z = space.point(math.sqrt(radius**2 - shift**2), 0.0, z)
    return math.atan2(y, x)


def test_the_table_indexes_the_64t_so_its_mid_face_tooth_centres_on_the_key() -> None:
    """The 64T's space is straight and inclined: its cutter plane crosses the
    axis at TOOTH_SPACE_CROSSING from the chamfered (z = 0) face, and the
    model centres a tooth on the keyway at mid-face. The key on the cutter
    centreline sets the space's crossing radial on the key; the table's
    index then turns the blank so the cut space is the model's, inside the
    arbor's setting allowance, where half a pitch is not."""
    pitch = 2.0 * math.pi / crank.TEETH
    allowance = math.radians(arbor.KEY_SETTING_ALLOWANCE_DEG)
    model = _midface_gap_rad(crank.TOOTH_SPACE)
    assert model == pytest.approx(pitch / 2.0, abs=1e-9)  # a tooth on +X
    assert crank.TOOTH_SPACE.crossing_z_mm == crank.TOOTH_SPACE_CROSSING
    assert "FROM CHAMFERED BORE FACE" in GEAR_DATA
    printed, words = _printed_index_deg(crank.TEETH)
    assert printed == spec.CRANK_FIRST_INDEX_DEG
    # The phantoms' labels say which way the chamfered face goes: toward
    # item 2, the collar that covers its mouth.
    assert spec.CHAMFERED_FACE_TOWARD in spec.SHOWN_BLANK_LABEL
    # Turning the blank by a about its +z carries a cutter fixed in space to
    # gear azimuth -a; counter-clockwise seen from the z = 0 face (looking
    # along +z) is a negative turn about +z.
    sense = {
        "CCW FROM CHAMFERED BORE FACE": 1.0,
        "CW FROM CHAMFERED BORE FACE": -1.0,
    }[words]
    assert words == spec.CRANK_FIRST_INDEX_SENSE
    cut = replace(crank.TOOTH_SPACE, azimuth_rad=sense * math.radians(printed))
    assert _off_pitches(_midface_gap_rad(cut), model, pitch) < allowance
    half = replace(crank.TOOTH_SPACE, azimuth_rad=pitch / 2.0)
    assert _off_pitches(_midface_gap_rad(half), model, pitch) > allowance
    (row,) = (row for row in spec.SETUP_TABLE_ROWS if row[1] == str(crank.TEETH))
    assert row[0] == arbor.KEYED_GEARS[-1].number


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


SHEET_INNER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)
BALLOON_REACH = drawing.BALLOON_MARGIN + 0.004  # ring margin + balloon radius


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside(box) -> bool:
    left, bottom, right, top = SHEET_INNER
    return left < box[0] and box[2] < right and bottom < box[1] and box[3] < top


def _grown(box, by: float):
    return (box[0] - by, box[1] - by, box[2] + by, box[3] + by)


def test_sheet_one_shows_only_the_working_pose() -> None:
    """Rules 8 and 22: the side view and the isometric show item 1 with item
    5, item 2 and item 6 seated (the 64T setup); the spare collars show only
    on sheet 2. The side view and its balloon ring stand inside the border,
    left of the parts list; the setup table ends above the title block."""
    assert set(drawing.WORKING) == {
        spec.ARBOR,
        spec.member(spec.KIT_COLLAR),
        spec.KEY,
        spec.NUT,
    }
    assert set(drawing.SPARES).isdisjoint(drawing.WORKING)
    assert set(drawing.SPARES) | set(drawing.WORKING) == set(spec.BOM_ORDER)
    s = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1] / 1000.0
    x, y = drawing.SIDE_ORIGIN
    radius = collar.OD_BY_CONFIGURATION[spec.KIT_COLLAR] / 2.0
    side = (x - arbor.ARBOR_END_Z * s, y - radius * s, x, y + radius * s)
    ring = _grown(side, BALLOON_REACH)
    assert _inside(ring)
    assert ring[2] < drawing.BOM_ANCHOR[0]
    table = drawing.setup_table_box()
    assert table[1] > TITLE_BLOCK[3]
    assert _inside(table)
    assert drawing.SHEET_SCALES == {
        "ASSEMBLY": drawing.SHEET_SCALE,
        "EXPLODED VIEW": drawing.EXPLODED_SCALE,
    }


def _side_point(point_mm):
    s = drawing.SIDE_SCALE[0] / drawing.SIDE_SCALE[1] / 1000.0
    x, y = drawing.SIDE_ORIGIN
    return (x - point_mm[2] * s, y + point_mm[1] * s)


def test_sheet_one_shows_the_64t_blank_in_phantom_where_it_seats() -> None:
    """Rule 22's working pose: the blank the steps fit, not in the kit, in
    phantom from item 1's shoulder to item 2, its label naming it and the
    face its chamfer goes toward; all inside the border, left of the parts
    list and over the isometric."""
    lines = drawing.blank_outline(arbor.SHOULDER_Z)
    points = [_side_point(p) for ends in lines.values() for p in ends]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    outline = (min(xs), min(ys), max(xs), max(ys))
    assert _inside(outline) and outline[2] < drawing.BOM_ANCHOR[0]
    assert lines["far face"][0][2] == pytest.approx(spec.BLANK_FACE_Z)
    iso_top = drawing.ISO_CENTER[1] + 0.025
    assert outline[1] > iso_top
    assert drawing.PHANTOM_STYLE == 2
    tip = _side_point(drawing.blank_tip_mm("sheet 1", arbor.SHOULDER_Z))
    assert outline[1] < tip[1] < outline[3]
    label = drawing.label_box(
        spec.SHOWN_BLANK_LABEL, drawing.blank_label_position("sheet 1", tip)
    )
    assert _inside(label) and label[2] < drawing.BOM_ANCHOR[0]
    assert label[0] >= tip[0] + drawing.LABEL_RUN - 1e-9
    radius = collar.OD_BY_CONFIGURATION[spec.KIT_COLLAR] / 2.0
    assert label[1] > _side_point((0.0, radius, 0.0))[1]  # over item 2
    assert spec.SHOWN_BLANK.number in spec.SHOWN_BLANK_LABEL
    assert spec.CHAMFERED_FACE_TOWARD in spec.SHOWN_BLANK_LABEL


def test_the_64t_blank_seats_its_plain_face_on_the_shoulder() -> None:
    """The chamfer's mouth can pass the Ø.50 shoulder at the limits, so the
    chamfered face goes toward item 2, whose face covers the mouth."""
    assert spec.CHAMFER_MOUTH_MAX_DIA > arbor.STANDOFF_DIA - 0.01 * arbor.INCH
    assert spec.CHAMFER_MOUTH_MAX_DIA < collar.OD_BY_CONFIGURATION[spec.KIT_COLLAR]
    assert spec.CHAMFERED_FACE_TOWARD == (
        f"CHAMFERED BORE FACE TOWARD ITEM {spec.BOM_ITEMS[spec.member(spec.KIT_COLLAR)]}"
    )


def _box(a, b):
    (x0, y0), (x1, y1) = drawing.nominal_sheet_point(a), drawing.nominal_sheet_point(b)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _exploded_part_boxes() -> dict[str, tuple[float, float, float, float]]:
    """Each view's item outline on sheet 2, nominal, as exploded."""
    boxes = {
        spec.ARBOR: _box(
            (0.0, -arbor.GRIP_DIA / 2.0, 0.0),
            (0.0, arbor.GRIP_DIA / 2.0, arbor.ARBOR_END_Z),
        )
    }
    for stem, (_dx, dy, dz) in drawing.EXPLODE_OFFSETS_MM.items():
        if stem == spec.ARBOR:
            continue
        z = spec.POSITIONS[stem][2] + dz
        if stem == spec.NUT:
            half, length = nut.ACROSS_CORNERS / 2.0, nut.THICKNESS
        else:
            half, length = (
                collar.OD_BY_CONFIGURATION[stem.split("--")[1]] / 2.0,
                (collar.LENGTH),
            )
        boxes[stem] = _box((0.0, dy - half, z), (0.0, dy + half, z + length))
    near = drawing.EXPLODED_BLANK_Z
    r = spec.SHOWN_BLANK_OD / 2.0
    boxes["blank"] = _box((0.0, -r, near), (0.0, r, near + spec.SHOWN_BLANK_FACE))
    return boxes


def test_the_exploded_view_draws_one_setup_in_fitting_order() -> None:
    """Rule 22: items 1 and 5 seated (bonded first), the 64T blank's phantom,
    item 2 then item 6 off the thread end on the axis, each EXPLODE_GAP
    clear; items 3 and 4 under item 2, whose place either takes; every item
    shown once."""
    offsets = drawing.EXPLODE_OFFSETS_MM
    gap = drawing.EXPLODE_GAP
    item2 = spec.member(spec.KIT_COLLAR)
    assert offsets[spec.ARBOR] == (0.0, 0.0, 0.0)
    assert drawing.EXPLODED_VIEWS[spec.ARBOR] == {spec.ARBOR, spec.KEY}
    assert drawing.EXPLODED_BLANK_Z - arbor.ARBOR_END_Z == pytest.approx(gap)
    near2 = spec.POSITIONS[item2][2] + offsets[item2][2]
    blank_far = drawing.EXPLODED_BLANK_Z + spec.SHOWN_BLANK_FACE
    assert near2 - blank_far == pytest.approx(gap)
    near6 = spec.POSITIONS[spec.NUT][2] + offsets[spec.NUT][2]
    assert near6 - (near2 + collar.LENGTH) == pytest.approx(gap)
    for stem in (item2, spec.NUT):
        assert offsets[stem][:2] == (0.0, 0.0), stem
    mid2 = near2 + collar.LENGTH / 2.0
    spare_mids = [
        spec.POSITIONS[stem][2] + offsets[stem][2] + collar.LENGTH / 2.0
        for stem in drawing.SPARES
    ]
    assert spare_mids[0] == pytest.approx(mid2)
    assert spare_mids[1] == pytest.approx(mid2 + drawing.SPARE_SPREAD)
    boxes = _exploded_part_boxes()
    for stem in drawing.SPARES:
        assert boxes[stem][3] < boxes[item2][1] - drawing.SPARE_DROP / 1000.0 + 1e-9
    # The stack stands on one axis height; no owned centreline joins the
    # views (one in item 1's view grew its outline over items 2 and 6).
    for stem in (item2, spec.NUT, "blank"):
        assert (boxes[stem][1] + boxes[stem][3]) / 2.0 == pytest.approx(
            (boxes[spec.ARBOR][1] + boxes[spec.ARBOR][3]) / 2.0
        ), stem
    names = list(boxes)
    for i, name in enumerate(names):
        assert _inside(boxes[name]) and not _overlap(boxes[name], TITLE_BLOCK), name
        for other in names[i + 1 :]:
            assert not _overlap(boxes[name], boxes[other]), (name, other)


def test_the_exploded_labels_and_balloons_stand_clear_of_the_ink() -> None:
    """Items 3 and 4 carry their BOM balloons here (their only view); the
    stack's items carry leader labels. Every label and every spare's balloon
    ring stands inside the border, clear of the parts, of each other, of the
    caption, of the steps and of the title block."""
    assert set(drawing.EXPLODED_BALLOONED) == set(drawing.SPARES)
    assert set(drawing.EXPLODED_LABELS) == {
        spec.ARBOR,
        spec.KEY,
        spec.member(spec.KIT_COLLAR),
        spec.NUT,
    }
    for stem, text in drawing.EXPLODED_LABELS.items():
        assert text.startswith(f"ITEM {spec.BOM_ITEMS[stem]}")
    parts = _exploded_part_boxes()
    tips = {}
    for stem, point in drawing.LABEL_TIPS_MM.items():
        owner = drawing._view_stem(stem)
        offset = drawing.EXPLODE_OFFSETS_MM[owner]
        tips[stem] = drawing.nominal_sheet_point(
            tuple(p + o for p, o in zip(point, offset, strict=True))
        )
        x0, y0, x1, y1 = parts[owner]
        assert x0 < tips[stem][0] < x1 and y0 < tips[stem][1] < y1, stem
    key_z = (key.END_Z_MM, key.END_Z_MM + key.LENGTH)
    assert key_z[0] < drawing.LABEL_TIPS_MM[spec.KEY][2] < key_z[1]
    boxes = {
        stem: drawing.label_box(text, drawing.label_position(stem, tips[stem]))
        for stem, text in drawing.EXPLODED_LABELS.items()
    }
    boxes["caption"] = drawing.label_box(drawing.EXPLODED_CAPTION, drawing.CAPTION_XY)
    blank_tip = drawing.nominal_sheet_point(
        drawing.blank_tip_mm("sheet 2", drawing.EXPLODED_BLANK_Z)
    )
    x0, y0, x1, y1 = parts["blank"]
    assert x0 <= blank_tip[0] <= x1 and y0 < blank_tip[1] < y1
    boxes["blank label"] = drawing.label_box(
        spec.SHOWN_BLANK_LABEL, drawing.blank_label_position("sheet 2", blank_tip)
    )
    assert boxes["blank label"][0] >= blank_tip[0] + drawing.LABEL_RUN - 1e-9
    boxes["steps"] = drawing.label_box(spec.ASSEMBLY_STEPS, drawing.STEPS_XY)
    for stem in drawing.SPARES:
        boxes[f"ring {stem}"] = _grown(parts[stem], BALLOON_REACH)
    names = list(boxes)
    for i, name in enumerate(names):
        assert _inside(boxes[name]), name
        assert not _overlap(boxes[name], TITLE_BLOCK), name
        for other in names[i + 1 :]:
            assert not _overlap(boxes[name], boxes[other]), (name, other)
        for stem, part in parts.items():
            if name != f"ring {stem}":
                assert not _overlap(boxes[name], part), (name, stem)


def test_the_exploded_labels_never_read_as_one_block_or_start_on_their_text() -> None:
    """The layout audit's merged-blocks rule on the planned label boxes: two
    leadered notes sharing any column stand at least its row pitch apart
    (farm 20261113T090619426Z: items 5 and 2, 4.79 mm, under 5.53). Each
    label stands wholly beside its tip and above it, so its leader leaves
    the text's near end, never across the text."""
    from _layout_audit import ROW_PITCH_HEIGHTS

    text_height = 0.0035  # the default note height the audit measured
    tips = {}
    for stem, point in drawing.LABEL_TIPS_MM.items():
        offset = drawing.EXPLODE_OFFSETS_MM[drawing._view_stem(stem)]
        tips[stem] = drawing.nominal_sheet_point(
            tuple(p + o for p, o in zip(point, offset, strict=True))
        )
    boxes = {
        stem: drawing.label_box(text, drawing.label_position(stem, tips[stem]))
        for stem, text in drawing.EXPLODED_LABELS.items()
    }
    for stem, (x0, y0, x1, _y1) in boxes.items():
        tip_x, tip_y = tips[stem]
        assert x0 >= tip_x + drawing.LABEL_RUN - 1e-9 or (
            x1 <= tip_x - drawing.LABEL_RUN + 1e-9
        ), stem
        assert y0 > tip_y, stem
    stems = list(boxes)
    for i, a in enumerate(stems):
        for b in stems[i + 1 :]:
            ax0, ay0, ax1, ay1 = boxes[a]
            bx0, by0, bx1, by1 = boxes[b]
            if min(ax1, bx1) <= max(ax0, bx0):
                continue  # side by side
            gap = max(ay0 - by1, by0 - ay1)
            assert gap >= ROW_PITCH_HEIGHTS * text_height + 0.001, (a, b)

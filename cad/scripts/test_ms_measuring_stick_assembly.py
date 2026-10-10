"""Offline contracts for the ms-measuring-stick sub-assembly (MHA-MS-000).

The clamped pose, the park pose under the top assembly, the thread
allowances and the fitter package all derive from
``ms_measuring_stick_assembly_spec``; these tests pin the derivations to the
part and vendor specs so none of them can drift on its own.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

import _config
import _hole_spec
import _interference_contracts as contracts
import build_ha_harmonic_analyzer_assembly as top
import draw_ms_measuring_stick_assembly as drawing
import joint_retention
import ms_measuring_stick_assembly_spec as spec
import ms_stick_spec as stick
import ms_stop_spec as stop
import vn_ms_stop_plate_screw_spec as plate_screw
import vn_thumb_screw_spec as thumb
from _transforms import rows_from_euler
from diagnostics.diag_mcmaster_thumb import THUMB_SPECS

SCRIPTS = Path(__file__).resolve().parent
BUILDER = SCRIPTS / "build_ms_measuring_stick_assembly.py"


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _flat(rows) -> list[float]:
    return [float(value) for row in rows for value in row]


def _image(rows, origin, point):
    """Assembly-frame image of a part-local point (``rows[i]`` = image of axis i)."""
    return tuple(
        origin[axis] + sum(point[i] * rows[i][axis] for i in range(3)) for axis in range(3)
    )


def test_thumb_screw_spec_is_the_recipe_table_row() -> None:
    row = THUMB_SPECS[thumb.SKU]
    assert thumb.SHANK_DIA == pytest.approx(2.0 * row["major_r"])
    assert thumb.PITCH == pytest.approx(row["pitch"])
    assert thumb.SHANK_LEN == pytest.approx(row["length"])
    assert thumb.COLLAR_DIA == pytest.approx(2.0 * row["collar_r"])
    assert thumb.COLLAR_H == pytest.approx(row["collar_h"])
    assert thumb.HEAD_DIA == pytest.approx(2.0 * row["head_r"])
    assert thumb.HEAD_H == pytest.approx(row["head_h"])
    assert _config.parts("vn-thumb-screw")["supplier_skus"] == [thumb.SKU]


def test_every_rotation_is_proper() -> None:
    for rows in (spec.STICK_ROWS, spec.THUMB_ROWS, spec.PLATE_SCREW_ROWS, top.MS_ROWS):
        x, y, z = rows
        cross = (
            x[1] * y[2] - x[2] * y[1],
            x[2] * y[0] - x[0] * y[2],
            x[0] * y[1] - x[1] * y[0],
        )
        assert cross == pytest.approx(tuple(z))


def test_stick_rides_the_roof_graduations_up_centred_in_the_window() -> None:
    # Graduated face (part z=0) on the roof; the far face (part z=thickness) below.
    top_face = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, 0.0, 0.0))
    bottom = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, 0.0, stick.BODY_THICKNESS))
    assert top_face[1] == pytest.approx(stop.WINDOW_Y_MAX)
    assert bottom[1] == pytest.approx(spec.STICK_BOTTOM_Y)
    assert spec.STICK_FLOOR_GAP == pytest.approx(
        stop.WINDOW_HEIGHT - stick.BODY_THICKNESS
    )
    near = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, 0.0, 0.0))[2]
    far = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, stick.BODY_WIDTH, 0.0))[2]
    assert near - stop.WINDOW_Z_MIN == pytest.approx(stop.WINDOW_Z_MAX - far)
    assert near - stop.WINDOW_Z_MIN > 0.0


def test_stop_mark_division_sits_on_the_thumbscrew_axis() -> None:
    mark = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (spec.STICK_MARK_X, 0.0, 0.0))
    assert mark[0] == pytest.approx(stop.THUMB_AXIS_X)
    assert spec.STICK_MARK_X == pytest.approx(
        stick.SCALE_START_X + stop.STOP_MARK * stick.DIVISION_SPACING
    )
    assert spec.STICK_X_MIN < 0.0 and spec.STICK_X_MAX > stop.BLOCK_LENGTH


def test_thumbscrew_tip_clamps_the_stick_underside() -> None:
    tip = _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (thumb.OVERALL_LEN, 0.0, 0.0))
    collar = _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (thumb.HEAD_STACK_LEN, 0.0, 0.0))
    assert tip == pytest.approx((stop.THUMB_AXIS_X, spec.STICK_BOTTOM_Y, stop.THUMB_AXIS_Z))
    assert collar[1] < 0.0  # the collar hangs under the block, never bearing on it
    assert spec.THUMB_EXPOSED_THREAD == pytest.approx(
        thumb.SHANK_LEN - stop.FLOOR_THICKNESS - spec.STICK_FLOOR_GAP
    )
    # The stick's 8 width covers the tip within the window.
    assert spec.STICK_Z_MIN < stop.THUMB_AXIS_Z < spec.STICK_Z_MAX


def test_plate_screws_seat_on_the_cover_and_stop_short_of_the_tap_depth() -> None:
    assert len(spec.PLATE_SCREW_ORIGINS) == spec.QUANTITIES[spec.PLATE_SCREW]
    for origin in spec.PLATE_SCREW_ORIGINS:
        bearing = _image(spec.PLATE_SCREW_ROWS, origin, (0.0, 0.0, 0.0))
        tip = _image(spec.PLATE_SCREW_ROWS, origin, (0.0, -plate_screw.LENGTH, 0.0))
        head = _image(spec.PLATE_SCREW_ROWS, origin, (0.0, plate_screw.HEAD_H, 0.0))
        assert bearing[2] == pytest.approx(stop.PLATE_Z_MIN)
        assert tip[2] == pytest.approx(spec.PLATE_SCREW_TIP_Z)
        assert head[2] == pytest.approx(spec.PLATE_SCREW_HEAD_Z)
        assert (bearing[0], bearing[1]) in {
            (x, stop.PLATE_HOLE_Y) for x in stop.PLATE_HOLE_XS
        }
    assert spec.PLATE_SCREW_ENGAGED == pytest.approx(
        plate_screw.LENGTH - stop.PLATE_THICKNESS
    )
    assert 0.0 < spec.PLATE_SCREW_ENGAGED < stop.PLATE_TAP_THREAD_DEPTH


def test_thread_allowances_are_the_spec_values() -> None:
    assert contracts.MS_THUMB_SCREW_THREAD == pytest.approx(
        (thumb.SHANK_DIA, _hole_spec.TAP_DRILL_MM[thumb.THREAD], stop.FLOOR_THICKNESS)
    )
    assert contracts.MS_PLATE_SCREW_THREAD == pytest.approx(
        (
            plate_screw.MAJOR_DIA,
            stop.PLATE_TAP_DRILL_DIA,
            plate_screw.LENGTH - stop.PLATE_THICKNESS,
        )
    )
    pairs = contracts.allowed_interference_pairs(spec.ASM_NAME)
    assert set(pairs) == {
        frozenset(("vn-thumb-screw-1", "ms-stop-block-1")),
        frozenset(("vn-ms-stop-plate-screw-1", "ms-stop-block-1")),
        frozenset(("vn-ms-stop-plate-screw-2", "ms-stop-block-1")),
    }


def test_assembly_contract_is_fully_fixed() -> None:
    path = _config.CONFIG_DIR / "assemblies" / f"{spec.ASM_NAME}.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert contract["number"] == spec.DRAWING_NUMBER
    assert contract["free_dof"] == 0
    assert contract["allowed_free_stems"] == []
    assert contract["required_free_stems"] == []


def _placed_stems() -> list[str]:
    """Literal part stems the builder hands its placement wrapper."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    stems = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "_place_fixed"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
        ):
            stems.append(node.args[1].value)
    return stems


def test_builder_places_exactly_the_inventory() -> None:
    assert sorted(set(_placed_stems())) == sorted(spec.QUANTITIES)
    assert sorted(spec.BOM_ORDER) == sorted(spec.QUANTITIES)
    for _label, families, axis, distance in spec.EXPLODE_STEPS:
        assert set(families) <= set(spec.QUANTITIES)
        assert axis in {"x", "y", "z"} and distance != 0.0
    moved = {family for _label, families, _axis, _distance in spec.EXPLODE_STEPS for family in families}
    assert moved == set(spec.QUANTITIES) - {spec.BLOCK}


def test_park_pose_sits_on_the_deck_inside_the_park_band() -> None:
    assert top.MS_HEAD_BOTTOM_Y == pytest.approx(top.DECK_TOP_Y + top.STOP_DECK_GAP)
    assert top.MS_WEST_X == pytest.approx(top.PARK_WEST_LIMIT_X + top.PARK_WEST_CLEARANCE)
    assert top.MS_FRONT_Z > top.PARK_FRONT_LIMIT_Z
    # The 200 bar is centred on machine z = 0.
    assert top.MS_POS[2] + (spec.STICK_X_MIN + spec.STICK_X_MAX) / 2.0 == pytest.approx(0.0)
    assert _flat(rows_from_euler(top.MS_EULER)) == pytest.approx(_flat(top.MS_ROWS))


def test_stick_keeps_its_machine_orientation() -> None:
    """Composed through the sub-assembly, the bar still runs machine +Z with
    the graduated face up, as it did when the top assembly placed it."""
    composed = _matmul([list(row) for row in spec.STICK_ROWS], top.MS_ROWS)
    assert _flat(composed) == pytest.approx(
        _flat([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
    )


def test_joint_rows_name_printed_steps() -> None:
    joints = {
        joint.id: joint
        for joint in joint_retention.JOINTS
        if joint.assembly == "ms_measuring_stick"
    }
    assert set(joints) == {
        "ms-measuring-stick/stop-thumbscrew",
        "ms-measuring-stick/plate-screws",
    }
    printed = {line.split(". ", 1)[0]: line for line in spec.ASSEMBLY_STEPS}
    for joint, word in (
        (joints["ms-measuring-stick/stop-thumbscrew"], "THUMBSCREW"),
        (joints["ms-measuring-stick/plate-screws"], "FILLISTER SCREWS"),
    ):
        prefix = f"{spec.DRAWING_NUMBER} STEP "
        assert joint.installed_at.startswith(prefix)
        assert word in printed[joint.installed_at.removeprefix(prefix)]
    assert joints["ms-measuring-stick/plate-screws"].quantity == spec.QUANTITIES[spec.PLATE_SCREW]


def test_fitter_package_covers_rule_9() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED + CLAMPED SETUP",
        "EXPLODED VIEW + BOM",
        "ASSEMBLY STEPS",
    )
    assert drawing.BOM_COMPONENTS == spec.BOM_ORDER
    assert set(drawing.BOM_DESCRIPTIONS) == set(spec.QUANTITIES)
    assert set(drawing.BALLOON_ANCHORS) == set(spec.QUANTITIES)
    assert drawing.BOM_PART_NUMBERS[spec.PLATE_SCREW] == "MHA-VN-054"
    for stem in spec.QUANTITIES:
        assert drawing.BOM_PART_NUMBERS[stem] == _config.parts(stem)["number"]
    for text in (drawing.ASSEMBLY_STEPS, drawing.ASSEMBLY_CHECKS, drawing.SETUP_NOTE):
        assert all(len(line) <= drawing.STEPS_LINE_WIDTH for line in text.splitlines())
    assert drawing.ASSEMBLY_STEPS.count("\n") >= len(spec.ASSEMBLY_STEPS)
    assert f"{stop.STOP_MARK:.1f}" in drawing.SETUP_NOTE
    assert "FINISH" in drawing.FINISH_NOTE
    assert all(
        len(line) <= drawing.SETUP_NOTE_WIDTH for line in drawing.FINISH_NOTE.splitlines()
    )


def test_bom_prints_registry_material_and_vendor_sku() -> None:
    assert drawing.BOM_SKUS[spec.PLATE_SCREW] == plate_screw.SKU == "90114A124"
    assert drawing.BOM_SKUS[spec.THUMB_SCREW] == thumb.SKU == "91882A221"
    for stem in (spec.STICK, spec.BLOCK, spec.PLATE):
        assert drawing.BOM_SKUS[stem] == drawing.MADE_PART_SKU
    for stem in spec.QUANTITIES:
        row = _config.parts(stem)
        assert drawing.BOM_MATERIALS[stem] == str(row["material"]).upper()
        assert drawing.BOM_PART_NUMBERS[stem] == row["number"]
    assert set(drawing.BOM_COLUMN_WIDTHS) == {
        "item",
        "part",
        "description",
        "material",
        "sku",
        "quantity",
    }
    left, _bottom, right, _top = drawing.SHEET_INNER_BORDER
    assert left <= drawing.BOM_ANCHOR[0]
    assert drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values()) < right


def test_every_component_instance_carries_a_balloon() -> None:
    assert set(drawing.BALLOON_ANCHORS) == set(spec.QUANTITIES)
    pinned = {
        drawing.BALLOON_ANCHORS[spec.PLATE_SCREW].instance,
        drawing.SECOND_SCREW_BALLOON_ANCHORS[spec.PLATE_SCREW].instance,
    }
    assert pinned == {
        f"{spec.PLATE_SCREW}-{index}"
        for index in range(1, spec.QUANTITIES[spec.PLATE_SCREW] + 1)
    }
    singles = [stem for stem, count in spec.QUANTITIES.items() if count == 1]
    assert all(drawing.BALLOON_ANCHORS[stem].instance is None for stem in singles)
    assert len(singles) + len(pinned) == sum(spec.QUANTITIES.values()) == 6
    # The second pass rings outside the first, at least a balloon apart.
    assert drawing.SECOND_SCREW_BALLOON_MARGIN - drawing.BALLOON_MARGIN >= 0.010


def test_reference_dimensions_follow_the_spec() -> None:
    assert spec.REFERENCE_OVERALL_LENGTH == pytest.approx(stick.BODY_LENGTH)
    # The stop's near face sits half a block short of the STOP_MARK division.
    assert spec.REFERENCE_STOP_FACE == pytest.approx(
        stick.SCALE_START_X
        + stop.STOP_MARK * stick.DIVISION_SPACING
        - stop.BLOCK_LENGTH / 2.0
    )
    assert stop.THUMB_AXIS_X == pytest.approx(stop.BLOCK_LENGTH / 2.0)
    assert {label for label, _value, _callout in drawing.REFERENCE_DIMENSIONS} == {
        "overall length",
        "stop position",
    }
    values = {label: value for label, value, _callout in drawing.REFERENCE_DIMENSIONS}
    assert values["overall length"] == spec.REFERENCE_OVERALL_LENGTH
    assert values["stop position"] == spec.REFERENCE_STOP_FACE
    assert f"{stop.STOP_MARK:.1f}" in spec.STOP_POSITION_CALLOUT
    assert isinstance(spec.DRAWING_REFERENCE_PRECISION, int)
    assert spec.DRAWING_REFERENCE_PRECISION >= 1
    # Both texts sit between the front view and the top view above it.
    assert (
        drawing.FRONT_CENTER[1]
        < drawing.STOP_POSITION_TEXT_Y
        < drawing.OVERALL_LENGTH_TEXT_Y
        < drawing.TOP_CENTER[1]
    )


def _iso_hull(box) -> list[tuple[float, float]]:
    """The convex outline of an axis-aligned box in the standard isometric
    (viewer at +X+Y+Z, Y up)."""
    s2, s6 = 2.0**-0.5, 6.0**-0.5
    points = sorted(
        {
            (round(s2 * (x - z), 9), round(s6 * (2.0 * y - x - z), 9))
            for x in box[0]
            for y in box[1]
            for z in box[2]
        }
    )

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    upper: list[tuple[float, float]] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _hulls_overlap(a, b) -> bool:
    for polygon in (a, b):
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            normal = (end[1] - start[1], start[0] - end[0])
            pa = [normal[0] * p[0] + normal[1] * p[1] for p in a]
            pb = [normal[0] * p[0] + normal[1] * p[1] for p in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def test_exploded_isometric_shows_every_component() -> None:
    """MS_EXPLODED in the drawing's *Isometric: no component's box hides
    behind another's, except the long stick crossing the block."""
    head = plate_screw.HEAD_DIA / 2.0
    knurl = thumb.HEAD_DIA / 2.0
    boxes = {
        "block": ((0.0, stop.BLOCK_LENGTH), (0.0, stop.BLOCK_HEIGHT), (0.0, stop.BLOCK_DEPTH)),
        spec.PLATE: (
            (0.0, stop.BLOCK_LENGTH),
            (0.0, stop.BLOCK_HEIGHT),
            (stop.PLATE_Z_MIN, stop.PLATE_Z_MAX),
        ),
        spec.THUMB_SCREW: (
            (stop.THUMB_AXIS_X - knurl, stop.THUMB_AXIS_X + knurl),
            (spec.THUMB_HEAD_FACE_Y, spec.THUMB_TIP_Y),
            (stop.THUMB_AXIS_Z - knurl, stop.THUMB_AXIS_Z + knurl),
        ),
        spec.STICK: (
            (spec.STICK_X_MIN, spec.STICK_X_MAX),
            (spec.STICK_BOTTOM_Y, spec.STICK_TOP_Y),
            (spec.STICK_Z_MIN, spec.STICK_Z_MAX),
        ),
    }
    families = {"block": spec.BLOCK, spec.PLATE: spec.PLATE}
    families.update({spec.THUMB_SCREW: spec.THUMB_SCREW, spec.STICK: spec.STICK})
    for index, x in enumerate(stop.PLATE_HOLE_XS, start=1):
        name = f"{spec.PLATE_SCREW}-{index}"
        families[name] = spec.PLATE_SCREW
        boxes[name] = (
            (x - head, x + head),
            (stop.PLATE_HOLE_Y - head, stop.PLATE_HOLE_Y + head),
            (spec.PLATE_SCREW_HEAD_Z, spec.PLATE_SCREW_TIP_Z),
        )
    hulls = {}
    for name, box in boxes.items():
        shift = [0.0, 0.0, 0.0]
        for _label, moved, axis, distance in spec.EXPLODE_STEPS:
            if families[name] in moved:
                shift["xyz".index(axis)] += distance
        hulls[name] = _iso_hull(
            [(low + shift[i], high + shift[i]) for i, (low, high) in enumerate(box)]
        )
    names = sorted(hulls)
    overlapping = {
        frozenset((a, b))
        for i, a in enumerate(names)
        for b in names[i + 1 :]
        if _hulls_overlap(hulls[a], hulls[b])
    }
    assert overlapping == {frozenset(("block", spec.STICK))}

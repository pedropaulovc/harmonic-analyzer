"""Offline contracts for the ms-measuring-stick sub-assembly (MHA-MS-00).

The clamped pose, the park pose under the top assembly, the thread
allowances and the fitter package all derive from
``ms_measuring_stick_assembly_spec`` (builder data),
``ms_measuring_stick_explode_spec`` and ``ms_measuring_stick_assembly_sheet``
(drawing-only); these tests pin the derivations to the part and vendor specs
so none of them can drift on its own.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import _config
import _drawing_dimensions as drawing_dimensions
import _drawing_edge_dimensions as drawing_edge_dimensions
import _drawing_projection as drawing_projection
import _hole_spec
import _interference_contracts as contracts
import build_ha_harmonic_analyzer_assembly as top
import draw_ms_measuring_stick_assembly as drawing
import joint_retention
import ms_measuring_stick_assembly_sheet as sheet
import ms_measuring_stick_assembly_spec as spec
import ms_measuring_stick_explode_spec as explode
import ms_stick_spec as stick
import ms_stop_spec as stop
import _mcmaster_90114a124 as plate_screw
import sh_vn_thumb_screw_spec as thumb
from _transforms import rows_from_euler
from _named_views import octant_axes

SCRIPTS = Path(__file__).resolve().parent
BUILDER = SCRIPTS / "build_ms_measuring_stick_assembly.py"

def test_clamped_setting_authors_its_globals_and_drives(monkeypatch) -> None:
    """Run the builder's setting helper against fakes: every async authoring
    step must actually execute (an un-awaited coroutine silently drops the
    globals and equations), and the mm suffix is load-bearing in the equation
    manager, which reads bare numbers in document units."""
    import asyncio

    import build_ms_measuring_stick_assembly as builder

    ok = lambda data=None: SimpleNamespace(is_success=True, data=data, error=None)  # noqa: E731
    globals_authored: dict[str, str] = {}
    equations: dict[str, str] = {}
    reference_text: dict[int, str] = {}
    tolerance = SimpleNamespace(Type=4)
    display = SimpleNamespace(ShowParenthesis=True, SetText=reference_text.__setitem__)

    class Adapter:
        _sketch_entities = {"chord": object()}

        async def create_sketch(self, plane):
            return ok()

        async def add_line(self, *args):
            return ok("chord")

        async def add_sketch_constraint(self, *args):
            return ok()

        async def exit_sketch(self):
            return ok()

    class Dims:
        def __init__(self):
            self.rows = []

        def record(self, name, drive=None):
            self.rows.append((name, drive))

        def apply(self, adapter, feature):
            return [(f"{name}@{feature}", drive) for name, drive in self.rows if drive]

    async def set_global(adapter, name, expression):
        globals_authored[name] = expression

    async def drive_dimension(adapter, name, expression):
        equations[name] = expression

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(builder, "set_global", set_global)
    monkeypatch.setattr(builder, "drive_dimension", drive_dimension)
    monkeypatch.setattr(builder, "SketchDims", Dims)
    for name in ("anchor_point_to_origin", "dimension_between", "ensure_fully_defined"):
        monkeypatch.setattr(builder, name, noop)
    for name in ("set_sketch_direct_db", "name_last_feature",
                 "apply_drawing_precision", "mark_dimensions_for_drawing", "blank_sketch"):
        monkeypatch.setattr(builder, name, lambda *a, **kw: None)
    monkeypatch.setattr(builder, "_early_bound",
                        lambda entity, iface: entity if iface == "IDimensionTolerance"
                        else SimpleNamespace(ConstructionGeometry=False))
    monkeypatch.setattr(builder, "_named_dimension",
                        lambda adapter, feature, name:
                        (display, SimpleNamespace(Tolerance=tolerance)))

    asyncio.run(builder._author_clamped_setting(Adapter()))

    (left_x, contact_y), (face_x, _) = spec.SETTING_CHORD
    assert globals_authored == {
        "SettingStickLeft": f"{left_x}mm",
        "SettingBlockFace": f"{face_x}mm",
        "SettingContact": f"{contact_y}mm",
    }
    feature = spec.SETTING_FEATURE
    assert equations == {
        f"SettingLeftX@{feature}": '-"SettingStickLeft"',
        f"SettingContactY@{feature}": '-"SettingContact"',
        f"{spec.SETTING_DIMENSION}@{feature}": '"SettingBlockFace" - "SettingStickLeft"',
    }
    # A parenthesized, unbanded reference: "(2.923)", not "2.923 ±.004".
    assert tolerance.Type == 0
    assert reference_text == {1: "(", 2: ")"}
    assert display.ShowParenthesis is False


def test_setting_chord_spans_the_near_face_reference() -> None:
    assert spec.SETTING_CHORD[0] == (spec.STICK_X_MIN, spec.STICK_BOTTOM_Y)
    assert spec.SETTING_CHORD[1] == (spec.BLOCK_ORIGIN[0], spec.STICK_BOTTOM_Y)
    assert spec.SETTING_CHORD[1][0] - spec.SETTING_CHORD[0][0] == pytest.approx(spec.SETTING_NEAR_FACE_MM)
    assert spec.DRAWING_PRECISION == {
        spec.SETTING_FEATURE: {spec.SETTING_DIMENSION: spec.SETTING_PRECISION}
    }
    drawing_tree = ast.parse(Path(drawing.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(drawing_tree):
        if isinstance(node, ast.Call):
            assert getattr(node.func, "attr", "") not in {"SetValues", "SetValues2"}



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
    row = thumb.THUMB_SPEC
    assert thumb.SHANK_DIA == pytest.approx(2.0 * row["major_r"])
    assert thumb.PITCH == pytest.approx(row["pitch"])
    assert thumb.SHANK_LEN == pytest.approx(row["length"])
    assert thumb.COLLAR_DIA == pytest.approx(2.0 * row["collar_r"])
    assert thumb.COLLAR_H == pytest.approx(row["collar_h"])
    assert thumb.HEAD_DIA == pytest.approx(2.0 * row["head_r"])
    assert thumb.HEAD_H == pytest.approx(row["head_h"])
    assert _config.parts("sh-vn-thumb-screw")["supplier_skus"] == [thumb.SKU]


def test_every_rotation_is_proper() -> None:
    for rows in (spec.WORKING_ROWS, spec.BLOCK_ROWS, spec.PLATE_ROWS,
                 spec.STICK_ROWS, spec.THUMB_ROWS, spec.PLATE_SCREW_ROWS, top.MS_ROWS):
        x, y, z = rows
        cross = (
            x[1] * y[2] - x[2] * y[1],
            x[2] * y[0] - x[0] * y[2],
            x[0] * y[1] - x[1] * y[0],
        )
        assert cross == pytest.approx(tuple(z))


def test_stick_graduated_face_bears_on_the_window_wall_opposite_the_screw() -> None:
    graduated = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, 0.0, 0.0))
    plain = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, 0.0, stick.BODY_THICKNESS))
    window_contact = _image(spec.BLOCK_ROWS, spec.BLOCK_ORIGIN,
                            (0.0, stop.WINDOW_Y_MAX, 0.0))
    assert graduated[1] == pytest.approx(window_contact[1])
    assert graduated[1] == pytest.approx(spec.STICK_BOTTOM_Y)
    assert plain[1] == pytest.approx(spec.STICK_TOP_Y)
    assert plain[1] > graduated[1]
    assert tuple(-v for v in spec.STICK_ROWS[2]) == (0.0, -1.0, 0.0)
    assert spec.STICK_TAPPED_WALL_GAP == pytest.approx(
        stop.WINDOW_HEIGHT - stick.BODY_THICKNESS
    )
    near = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, 0.0, 0.0))[2]
    far = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (0.0, stick.BODY_WIDTH, 0.0))[2]
    assert -stop.WINDOW_Z_MIN - near == pytest.approx(far + stop.WINDOW_Z_MAX)
    assert -stop.WINDOW_Z_MIN - near > 0.0


def test_stop_mark_division_sits_on_the_thumbscrew_axis() -> None:
    mark = _image(spec.STICK_ROWS, spec.STICK_ORIGIN, (spec.STICK_MARK_X, 0.0, 0.0))
    assert mark[0] == pytest.approx(stop.THUMB_AXIS_X)
    assert spec.STICK_MARK_X == pytest.approx(
        stick.SCALE_START_X + stop.STOP_MARK * stick.DIVISION_SPACING
    )
    assert spec.STICK_MARK_X == pytest.approx(84.9)
    assert spec.STICK_ORIGIN[0] == pytest.approx(-74.232)
    assert spec.STICK_X_MIN == pytest.approx(-74.232)
    assert spec.SETTING_NEAR_FACE_MM == pytest.approx(74.232)
    # Printed at its three inch places as the "(2.923)" reference.
    assert f"{spec.SETTING_NEAR_FACE_MM / 25.4:.{spec.SETTING_PRECISION}f}" == "2.923"
    assert spec.STICK_X_MAX == pytest.approx(127.698)  # 7.95 bar, stations fixed
    assert spec.STICK_X_MIN < 0.0 and spec.STICK_X_MAX > stop.BLOCK_LENGTH


def test_thumbscrew_head_is_above_tip_which_clamps_the_plain_face() -> None:
    head = _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (0.0, 0.0, 0.0))
    tip = _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (thumb.OVERALL_LEN, 0.0, 0.0))
    collar = _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (thumb.HEAD_STACK_LEN, 0.0, 0.0))
    assert tip == pytest.approx((stop.THUMB_AXIS_X, spec.STICK_TOP_Y, -stop.THUMB_AXIS_Z))
    assert head[1] > collar[1] > 0.0 > tip[1]
    assert head[1] == pytest.approx(spec.THUMB_HEAD_FACE_Y)
    assert spec.THUMB_EXPOSED_THREAD == pytest.approx(
        thumb.SHANK_LEN - stop.FLOOR_THICKNESS - spec.STICK_TAPPED_WALL_GAP
    )
    assert spec.STICK_Z_MIN < -stop.THUMB_AXIS_Z < spec.STICK_Z_MAX


def test_plate_screws_seat_on_the_cover_and_stop_short_of_the_tap_depth() -> None:
    assert len(spec.PLATE_SCREW_ORIGINS) == spec.QUANTITIES[spec.PLATE_SCREW]
    for origin in spec.PLATE_SCREW_ORIGINS:
        bearing = _image(spec.PLATE_SCREW_ROWS, origin, (0.0, 0.0, 0.0))
        tip = _image(spec.PLATE_SCREW_ROWS, origin, (0.0, -plate_screw.LENGTH, 0.0))
        head = _image(spec.PLATE_SCREW_ROWS, origin, (0.0, plate_screw.HEAD_H, 0.0))
        assert bearing[2] == pytest.approx(-stop.PLATE_Z_MIN)
        assert tip[2] == pytest.approx(spec.PLATE_SCREW_TIP_Z)
        assert head[2] == pytest.approx(spec.PLATE_SCREW_HEAD_Z)
        assert (bearing[0], bearing[1]) in {
            (x, -stop.PLATE_HOLE_Y) for x in stop.PLATE_HOLE_XS
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
        frozenset(("sh-vn-thumb-screw-1", "ms-stop-block-1")),
        frozenset(("ms-vn-stop-plate-screw-1", "ms-stop-block-1")),
        frozenset(("ms-vn-stop-plate-screw-2", "ms-stop-block-1")),
    }


def test_assembly_contract_is_fully_fixed() -> None:
    path = _config.CONFIG_DIR / "assemblies" / f"{spec.ASM_NAME}.yaml"
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert contract["number"] == sheet.DRAWING_NUMBER
    assert contract["free_dof"] == 0
    assert contract["allowed_free_stems"] == []
    assert contract["required_free_stems"] == []
    assert contract["drawing_unit"] == "in"


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
    assert sorted(sheet.BOM_ORDER) == sorted(spec.QUANTITIES)
    for _label, families, axis, distance in explode.EXPLODE_STEPS:
        assert set(families) <= set(spec.QUANTITIES)
        assert axis in {"x", "y", "z"} and distance != 0.0
    moved = {family for _label, families, _axis, _distance in explode.EXPLODE_STEPS for family in families}
    assert moved == set(spec.QUANTITIES) - {spec.BLOCK}


def test_park_pose_sits_on_the_land_inside_the_corridor() -> None:
    from itertools import product

    corners = tuple(
        _image(top.MS_ROWS, top.MS_POS, point)
        for point in product(*zip(spec.EXTENT_MIN, spec.EXTENT_MAX, strict=True))
    )
    assert len(corners) == len(set(corners)) == 8
    assert len(top.MS_PARK_CORNERS) == 8
    for actual, expected in zip(top.MS_PARK_CORNERS, corners, strict=True):
        assert actual == pytest.approx(expected)
        x, y, z = actual
        assert top.PARK_WEST_LIMIT_X < x < top.PARK_EAST_LIMIT_X
        assert y >= top.LAND_TOP_Y + top.STOP_LAND_GAP - 1e-9
        assert top.PARK_FRONT_LIMIT_Z < z < -top.PARK_FRONT_LIMIT_Z
    assert min(p[1] for p in corners) == pytest.approx(top.MS_BLOCK_BOTTOM_Y)
    assert top.MS_BLOCK_BOTTOM_Y == pytest.approx(top.LAND_TOP_Y + top.STOP_LAND_GAP)
    assert top.MS_WEST_X == pytest.approx(min(p[0] for p in corners))
    assert top.MS_EAST_X == pytest.approx(max(p[0] for p in corners))
    assert top.MS_FRONT_Z == pytest.approx(min(p[2] for p in corners))
    assert top.MS_WEST_X + top.MS_EAST_X == pytest.approx(
        top.PARK_WEST_LIMIT_X + top.PARK_EAST_LIMIT_X
    )
    assert min(p[2] for p in corners) + max(p[2] for p in corners) == pytest.approx(0.0)
    # The unchanged longitudinal axis centres the 7.95 in bar on machine Z.
    assert top.MS_POS[2] == pytest.approx(-26.733)
    assert _image(top.MS_ROWS, top.MS_POS, (spec.STICK_X_MIN, 0, 0))[2] == pytest.approx(-100.965)
    assert _image(top.MS_ROWS, top.MS_POS, (spec.STICK_X_MAX, 0, 0))[2] == pytest.approx(100.965)
    assert _flat(rows_from_euler(top.MS_EULER)) == pytest.approx(_flat(top.MS_ROWS))


def test_stick_keeps_its_machine_orientation() -> None:
    """The bar keeps machine +Z; the approved physical flip faces graduations down."""
    composed = _matmul([list(row) for row in spec.STICK_ROWS], top.MS_ROWS)
    assert _flat(composed) == pytest.approx(
        _flat([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    )
    head = _image(top.MS_ROWS, top.MS_POS, spec.THUMB_ORIGIN)
    tip = _image(top.MS_ROWS, top.MS_POS,
                 _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (thumb.OVERALL_LEN, 0, 0)))
    assert head[1] == pytest.approx(top.MS_HEAD_TOP_Y)
    assert head[1] > tip[1]
    assert (head[0], head[2]) == pytest.approx((tip[0], tip[2]))


@pytest.mark.parametrize("axis", ((0.0, -1.0, 0.0), (0.0, 1.0, 0.0),
                                (0.6, -0.8, 0.0), (0.0, -0.8, 0.6)))
def test_native_standalone_final_guard_reads_solved_screw_transform(monkeypatch, axis) -> None:
    import build_ms_measuring_stick_assembly as builder

    adapter = object()

    def transform(_current, _instance):
        return (*axis, 1, 0, 0, 0, 0, 1, 100, 200, 300, 1)

    monkeypatch.setattr(builder, "component_transform", transform)
    if axis == (0.0, -1.0, 0.0):
        builder._assert_working_pose(adapter, "native-thumb-1")
    else:
        with pytest.raises(RuntimeError, match="thumbscrew head must be above"):
            builder._assert_working_pose(adapter, "native-thumb-1")


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
    printed = {line.split(". ", 1)[0]: line for line in sheet.ASSEMBLY_STEPS}
    for joint, word in (
        (joints["ms-measuring-stick/stop-thumbscrew"], "THUMBSCREW"),
        (joints["ms-measuring-stick/plate-screws"], "FILLISTER SCREWS"),
    ):
        prefix = f"{sheet.DRAWING_NUMBER} STEP "
        assert joint.installed_at.startswith(prefix)
        assert word in printed[joint.installed_at.removeprefix(prefix)]
    assert joints["ms-measuring-stick/plate-screws"].quantity == spec.QUANTITIES[spec.PLATE_SCREW]


def test_fitter_package_covers_rule_9() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED + CLAMPED SETUP",
        "EXPLODED VIEW + BOM",
        "ASSEMBLY STEPS",
    )
    assert drawing.SPEC.layout is drawing.DrawingLayout.LANDSCAPE
    assert tuple(drawing.SHEET_LAYOUTS[name] for name in drawing.SHEET_NAMES) == (
        drawing.DrawingLayout.LANDSCAPE,
        drawing.DrawingLayout.PORTRAIT,
        drawing.DrawingLayout.LANDSCAPE,
    )
    assert all(scale == (1.0, 1.0) for scale in drawing.SHEET_SCALES.values())
    assert drawing.BOM_COMPONENTS == sheet.BOM_ORDER
    assert set(drawing.BOM_DESCRIPTIONS) == set(spec.QUANTITIES)
    assert set(drawing.BALLOON_ANCHORS) == set(spec.QUANTITIES)
    assert drawing.BOM_PART_NUMBERS[spec.PLATE_SCREW] == "MHA-MS-VN-51"
    for stem in spec.QUANTITIES:
        assert drawing.BOM_PART_NUMBERS[stem] == _config.parts(stem)["number"]
    for text in (drawing.ASSEMBLY_STEPS, drawing.ASSEMBLY_CHECKS, drawing.SETUP_NOTE):
        assert all(len(line) <= drawing.STEPS_LINE_WIDTH for line in text.splitlines())
    assert drawing.ASSEMBLY_STEPS.count("\n") >= len(sheet.ASSEMBLY_STEPS)
    for instruction in (sheet.ASSEMBLY_STEPS[-1], sheet.CLAMPED_SETUP_NOTE):
        assert "NEAR-FACE REFERENCE DIMENSION" in instruction
        assert f"STICK GRADUATION {stop.STOP_MARK:.1f} ON THUMBSCREW AXIS" in instruction
        assert "±" not in instruction  # the reference carries no band
    assert drawing.EXPLODED_CAPTION == sheet.EXPLODED_CAPTION == (
        "EXPLODED VIEW - ASSEMBLY SEQUENCE ON SHEET 3"
    )
    # drawing-guidelines.md rule 2 (the title block is the general specification) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the component Finish fields, not fitter notes or steps, own finish.
    assert not any("BLACKEN" in step or "FINISH" in step for step in sheet.ASSEMBLY_STEPS)
    for obsolete in ("FINISH_NOTE", "FINISH_NOTE_TEXT", "FINISH_NOTE_XY", "_BLOCK_FINISH"):
        assert not hasattr(drawing, obsolete)


def test_bom_prints_registry_identity_and_vendor_sku_only() -> None:
    assert drawing.BOM_SKUS[spec.PLATE_SCREW] == plate_screw.SKU == "90114A124"
    assert drawing.BOM_SKUS[spec.THUMB_SCREW] == thumb.SKU == "91882A221"
    for stem in (spec.STICK, spec.BLOCK, spec.PLATE):
        assert drawing.BOM_SKUS[stem] == drawing.MADE_PART_SKU
    for stem in spec.QUANTITIES:
        row = _config.parts(stem)
        assert drawing.BOM_PART_NUMBERS[stem] == row["number"]
    assert set(drawing.BOM_COLUMN_WIDTHS) == {
        "item",
        "part",
        "description",
        "sku",
        "quantity",
    }
    assert drawing.BOM_COLUMN_WIDTHS["part"] > 0.026
    assert drawing.BOM_COLUMN_WIDTHS["sku"] > 0.024
    assert drawing.BOM_COLUMN_WIDTHS["description"] < 0.080
    template = drawing.DRAWING_TEMPLATES[drawing.SHEET_LAYOUTS[drawing.SHEET_NAMES[1]]]
    left, right = 0.0127, template.width_m - 0.0127
    assert left <= drawing.BOM_ANCHOR[0]
    assert drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values()) < right
    assert not hasattr(drawing, "BOM_MATERIALS")
    assert not hasattr(drawing, "BOM_MATERIAL_TITLE")
    assert drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values()) / 2 == (
        pytest.approx(template.width_m / 2)
    )


def test_portrait_group_translation_balances_visible_ink() -> None:
    template = drawing.DRAWING_TEMPLATES[drawing.DrawingLayout.PORTRAIT]
    shift = drawing.EXPLODED_GROUP_SHIFT_Y
    # Use the recorded full-page visible envelope, not GetOutline's blank air.
    bottom, top = (value + shift for value in drawing._EXPLODED_MEASURED_GROUP_Y)
    lower_air = bottom - template.title_block_top_m
    upper_air = template.height_m - 0.0127 - top
    assert lower_air == pytest.approx(upper_air)
    assert lower_air > 0.05
    assert drawing.EXPLODED_ISO_CENTER == pytest.approx((0.1397, 0.235 + shift))
    assert drawing.BOM_ANCHOR == pytest.approx((0.0627, 0.405 + shift))
    assert drawing.EXPLODED_CAPTION_XY == pytest.approx((0.0627, 0.415 + shift))


def test_bom_removes_material_without_changing_native_items(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    native_order = (spec.BLOCK, spec.PLATE, spec.STICK, spec.THUMB_SCREW, spec.PLATE_SCREW)

    class Table:
        def __init__(self):
            self.cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
            self.cells += [
                [str(item), stem, drawing.BOM_DESCRIPTIONS[stem], str(spec.QUANTITIES[stem])]
                for item, stem in enumerate(native_order, 1)
            ]

        @property
        def RowCount(self):
            return len(self.cells)

        @property
        def ColumnCount(self):
            return len(self.cells[0])

        def DisplayedText(self, row, column):
            return self.cells[row][column]

        def IsCellTextEditable(self, row, column):
            return True

        def SetText2(self, row, column, linked, text):
            assert linked is False
            self.cells[row][column] = text

        def InsertColumn2(self, where, after, title, width):
            assert where == drawing._INSERT_COLUMN_AFTER
            assert width == drawing._INSERT_COLUMN_DEFAULT_WIDTH
            assert after == 2 and title == "VENDOR SKU"
            for row in self.cells:
                row.insert(after + 1, "")
            return True

        def SetColumnTitle2(self, column, title, linked):
            assert linked is False
            self.cells[0][column] = title
            return True

        def SetColumnWidth(self, column, width, options):
            assert options == 0
            return width

        def SetRowHeight(self, row, height, options):
            assert height == drawing.BOM_ROW_HEIGHT and options == 0

    table = Table()
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    items = drawing._validate_bom(adapter, table)
    assert dict(items) == {stem: str(item) for item, stem in enumerate(native_order, 1)}
    assert table.cells[0] == ["ITEM NO.", "PART NUMBER", "DESCRIPTION", "VENDOR SKU", "QTY."]
    for row, stem in zip(table.cells[1:], native_order):
        assert row[1:] == [
            drawing.BOM_PART_NUMBERS[stem], drawing.BOM_DESCRIPTIONS[stem],
            drawing.BOM_SKUS[stem], str(spec.QUANTITIES[stem]),
        ]


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
    # Balloon 2 lands mid-way along the plate's screw-side bottom edge, the
    # edge farthest from the stick, not on the corner at the stick's edge.
    import ms_stop_spec as stop

    assert drawing.BALLOON_ANCHORS[spec.PLATE].point_mm == (
        stop.BLOCK_LENGTH / 2.0, 0.0, stop.PLATE_Z_MIN,
    )
    assert all(drawing.BALLOON_ANCHORS[stem].point_mm is None
               for stem in spec.QUANTITIES if stem != spec.PLATE)


@pytest.mark.parametrize("layout", tuple(drawing.DrawingLayout))
def test_view_regions_use_selected_template(monkeypatch, layout) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    template = drawing.DRAWING_TEMPLATES[layout]
    view = SimpleNamespace(GetOutline=lambda: (0.02, 0.12, 0.08, 0.18))
    drawing._assert_view_on_sheet(view, layout=layout, label="inside")
    view.GetOutline = lambda: (0.02, 0.12, template.width_m, 0.18)
    with pytest.raises(RuntimeError, match="inner border"):
        drawing._assert_view_on_sheet(view, layout=layout, label="outside")
    view.GetOutline = lambda: (
        template.title_block_left_m + 0.001, 0.02,
        template.width_m - 0.02, template.title_block_top_m - 0.001,
    )
    with pytest.raises(RuntimeError, match="title block"):
        drawing._assert_view_on_sheet(view, layout=layout, label="title")


def test_measured_exploded_outline_recenters_and_fits_only_portrait(monkeypatch) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "double_array", tuple)
    rebuilt = []

    class View:
        Position = (0.300, 0.145)
        original = Position

        def GetOutline(self):
            # Native observation, without the 24 mm balloon ring.
            x0, y0, x1, y1 = (0.2187158944414347, 0.0691861987846213,
                              0.4166394446178927, 0.22326010614945984)
            dx, dy = (self.Position[i] - self.original[i] for i in range(2))
            return x0 + dx, y0 + dy, x1 + dx, y1 + dy

        def SetViewPosition(self, position, children):
            assert children is False
            self.Position = tuple(position)
            return True

    view = View()
    before = view.GetOutline()
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: rebuilt.append(True)))
    drawing._center_view_outline(adapter, view, drawing.EXPLODED_ISO_CENTER, label="exploded")
    assert view.Position == pytest.approx((
        0.300 + drawing.EXPLODED_ISO_CENTER[0] - (before[0] + before[2]) / 2,
        0.145 + drawing.EXPLODED_ISO_CENTER[1] - (before[1] + before[3]) / 2,
    ))
    assert rebuilt == [True]
    drawing._assert_view_on_sheet(
        view, margin=0.024, layout=drawing.DrawingLayout.PORTRAIT, label="exploded"
    )
    with pytest.raises(RuntimeError, match="inner border"):
        drawing._assert_view_on_sheet(view, margin=0.024, label="exploded")


@pytest.mark.parametrize("defect", ("refused", "unapplied", "stale outline"))
def test_outline_recentering_refuses_failed_or_unapplied_move(monkeypatch, defect) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "double_array", tuple)
    view = SimpleNamespace(
        Position=(0.3, 0.145),
        GetOutline=lambda: (0.2, 0.07, 0.4, 0.22),
    )
    def move(position, _children):
        if defect == "stale outline":
            view.Position = tuple(position)
        return defect != "refused"

    view.SetViewPosition = move
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: None))
    with pytest.raises(RuntimeError, match="refused|view moved|measured outline"):
        drawing._center_view_outline(adapter, view, drawing.EXPLODED_ISO_CENTER, label="failed")


@pytest.mark.parametrize("defect", (None, "selection", "paste", "activation", "rename"))
def test_mixed_sheets_copy_real_templates_and_close_donors(monkeypatch, defect) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "null_callout", lambda: None)
    created, closed, clipboard = [], [], []
    documents = {}

    class Sheet:
        def __init__(self, layout):
            self.name, self.layout = "Sheet1", layout

        def SetName(self, name):
            if defect != "rename" or name == drawing.SHEET_NAMES[0]:
                self.name = name

        def GetName(self):
            return self.name

    class Document:
        def __init__(self, title, layout):
            self.title = title
            self.sheets = [Sheet(layout)]
            self.active = self.sheets[0]
            self.Extension = SimpleNamespace(
                SelectByID2=lambda *args: defect != "selection" and args[0] == self.active.name
            )

        def GetTitle(self):
            return self.title

        def ClearSelection2(self, _all):
            pass

        def EditCopy(self):
            clipboard[:] = [self.active.layout]

        def GetSheetNames(self):
            return [sheet.name for sheet in self.sheets]

        def PasteSheet(self, insertion, rename):
            assert (insertion, rename) == (2, 2)
            if defect == "paste":
                return False
            sheet = Sheet(clipboard[0])
            sheet.name = f"Sheet{len(self.sheets) + 1}"
            self.sheets.append(sheet)
            return True

        def ActivateSheet(self, name):
            if defect == "activation":
                return False
            self.active = next(sheet for sheet in self.sheets if sheet.name == name)
            return True

        def GetCurrentSheet(self):
            return self.active

    adapter = SimpleNamespace(currentModel=None)

    def activate(title, silent, rebuild, errors):
        assert (silent, rebuild, errors) == (False, 2, 0)
        adapter.currentModel = documents[title]
        return adapter.currentModel, 0

    adapter.swApp = SimpleNamespace(
        ActivateDoc3=activate, IsSame=lambda a, b: int(a is b),
        CloseDoc=lambda title: closed.append(documents.pop(title)),
    )

    def new_drawing(_adapter, *, layout, scale, unit):
        assert scale == (1.0, 1.0)
        assert unit == "in"  # target and donor sheets alike
        document = Document(f"Drawing{len(created)}", layout)
        documents[document.title] = document
        created.append(document)
        adapter.currentModel = document
        return document, document.active

    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    if defect is None:
        drawing._create_mixed_package_sheets(adapter)
        target = created[0]
        assert tuple(target.GetSheetNames()) == drawing.SHEET_NAMES
        assert tuple(sheet.layout for sheet in target.sheets) == (
            drawing.DrawingLayout.LANDSCAPE, drawing.DrawingLayout.PORTRAIT,
            drawing.DrawingLayout.LANDSCAPE,
        )
    else:
        message = {
            "selection": "select donor sheet", "paste": "sheet paste failed",
            "activation": "activate pasted sheet", "rename": "rename pasted sheet",
        }[defect]
        with pytest.raises(RuntimeError, match=message):
            drawing._create_mixed_package_sheets(adapter)
        target = created[0]
        assert len(created) == 2
    assert closed == created[1:]
    assert adapter.currentModel is target
    assert list(documents.values()) == [target]


def test_reference_dimensions_follow_the_spec() -> None:
    assert sheet.REFERENCE_OVERALL_LENGTH == pytest.approx(stick.BODY_LENGTH)
    # The stop's near face sits half a block short of the STOP_MARK division.
    assert spec.SETTING_NEAR_FACE_MM == pytest.approx(
        stick.SCALE_START_X
        + stop.STOP_MARK * stick.DIVISION_SPACING
        - stop.BLOCK_LENGTH / 2.0
    )
    assert stop.THUMB_AXIS_X == pytest.approx(stop.BLOCK_LENGTH / 2.0)
    assert {label for label, _value in drawing.ASSEMBLY_DIMENSIONS} == {
        "overall length",
        "stop position",
    }
    values = dict(drawing.ASSEMBLY_DIMENSIONS)
    assert values["overall length"] == sheet.REFERENCE_OVERALL_LENGTH
    assert values["stop position"] == spec.SETTING_NEAR_FACE_MM
    assert isinstance(sheet.DRAWING_REFERENCE_PRECISION, int)
    assert sheet.DRAWING_REFERENCE_PRECISION >= 1
    # The underside projects below Front; both dimension rows stay above Front.
    assert (
        drawing.UNDERSIDE_CENTER[1]
        < drawing.FRONT_CENTER[1]
        < drawing.STOP_POSITION_TEXT_Y
        < drawing.OVERALL_LENGTH_TEXT_Y
        < drawing.SHEET_INNER_BORDER[3]
    )


@pytest.mark.parametrize("defect", (None, "style-set", "style-readback", "alignment"))
def test_clamped_sheet_places_section_clear_of_setting(monkeypatch, defect) -> None:
    front, underside, section = object(), object(), object()
    views = iter((front, underside))
    projected = []
    cut = {}
    style = []

    def settled():
        pass

    class Extension:
        def SetUserPreferenceInteger(self, preference, option, value):
            style.append((preference, option, value))
            return defect != "style-set"

        def GetUserPreferenceInteger(self, preference, option):
            assert (preference, option) == (542, 0)
            return 0 if defect == "style-readback" else 1

    adapter = SimpleNamespace(currentModel=SimpleNamespace(Extension=Extension()))
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *a: None)
    monkeypatch.setattr(drawing, "place_view", lambda *a, **kw: next(views))
    for name in ("set_hidden_lines_removed", "apply_view_configuration",
                 "_assert_view_on_sheet", "_add_note_block"):
        monkeypatch.setattr(drawing, name, lambda *a, **kw: None)
    monkeypatch.setattr(
        drawing, "_view_outline",
        lambda *a, **kw: (0.029412, 0.1739245, 0.240588, 0.2060755),
    )

    def project(adapter, view, point, **kwargs):
        projected.append((view, point))
        x = 0.1199
        if defect == "alignment" and view is underside:
            x += 2e-6  # Just beyond the 1 micrometre alignment boundary.
        return (x, 0.190)

    def create(adapter, parent, **kwargs):
        assert parent is front
        cut.update(kwargs)
        return section

    monkeypatch.setattr(drawing, "model_point_in_view", project)
    monkeypatch.setattr(drawing, "create_section_view", create)
    monkeypatch.setattr(drawing, "_add_assembly_dimensions", lambda *a: settled)
    if defect is not None:
        message = {
            "style-set": "failed to set end-only",
            "style-readback": "style did not persist",
            "alignment": "thumbscrew axes are not aligned",
        }[defect]
        with pytest.raises(RuntimeError, match=message):
            drawing._place_clamped_sheet(adapter)
        assert not cut
        return
    assert drawing._place_clamped_sheet(adapter) is settled
    assert style == [(542, 0, 1)]
    axis_point = tuple(value / 1000.0 for value in spec.THUMB_ORIGIN)
    assert projected == [(front, axis_point), (underside, axis_point)]
    assert cut["line_start"] == pytest.approx((0.1199, 0.2240755))
    assert cut["line_end"] == pytest.approx((0.1199, 0.1699245))
    assert cut["view_xy"] == drawing.CLAMP_SECTION_CENTER
    assert cut["scale"] == drawing.CLAMP_SECTION_SCALE


@pytest.mark.parametrize(
    "mark,drill_depth,thread_depth,zero",
    ((2.5, ".320", ".260", 57.0), (1.5, ".290", ".240", 56.0)),
)
def test_fitter_text_tracks_mutated_setting_and_depth_specs(
    monkeypatch, mark, drill_depth, thread_depth, zero
) -> None:
    """Evaluate real spec and sheet expressions with changed shop values, not
    COM mocks: the mutated spec is the one the sheet module imports."""
    monkeypatch.setattr(stop, "STOP_MARK", mark)
    monkeypatch.setattr(stick, "SCALE_START_X", zero)
    monkeypatch.setattr(stop, "PLATE_TAP_DRILL_DEPTH", float(drill_depth) * 25.4)
    monkeypatch.setattr(stop, "PLATE_TAP_THREAD_DEPTH", float(thread_depth) * 25.4)
    monkeypatch.setattr(stop, "PLATE_TAP_DRILL_DIA", 0.070 * 25.4)
    monkeypatch.setattr(stop, "PLATE_CLEARANCE_DIA", 0.096 * 25.4)
    tree = ast.parse(Path(spec.__file__).read_text(encoding="utf-8"))
    namespace = {"__name__": "mutated_ms_assembly_spec"}
    exec(compile(ast.fix_missing_locations(tree), spec.__file__, "exec"), namespace)
    mutated_spec = SimpleNamespace(**namespace)
    monkeypatch.setitem(sys.modules, spec.__name__, mutated_spec)
    sheet_namespace = {"__name__": "mutated_ms_assembly_sheet"}
    exec(
        compile(Path(sheet.__file__).read_text(encoding="utf-8"), sheet.__file__, "exec"),
        sheet_namespace,
    )
    assert sheet_namespace["spec"] is mutated_spec
    changed = SimpleNamespace(**{**namespace, **sheet_namespace})
    assert changed.STICK_MARK_X == pytest.approx(
        stick.SCALE_START_X + mark * stick.DIVISION_SPACING
    )
    assert changed.STICK_ORIGIN[0] + changed.STICK_MARK_X == pytest.approx(
        stop.THUMB_AXIS_X
    )
    assert changed.SETTING_NEAR_FACE_MM == pytest.approx(
        changed.STICK_MARK_X - stop.THUMB_AXIS_X
    )
    for text in (changed.CLAMPED_SETUP_NOTE, changed.ASSEMBLY_STEPS[-1]):
        assert f"STICK GRADUATION {mark:.1f} ON THUMBSCREW AXIS" in text
        assert "±" not in text
    assert "PLATE IS MASTER" in changed.ASSEMBLY_STEPS[0]
    assert stop.MATCH_DRILL_DATUM_ALIGNMENT in changed.ASSEMBLY_STEPS[0]
    pilot = changed.ASSEMBLY_STEPS[0]
    assert "PILOT DIA .070 THROUGH PLATE" in pilot
    assert "OPEN ITS HOLES TO DIA .096" in pilot
    # The block's tapped-hole callout carries the depths; the step names it.
    assert drill_depth not in pilot and thread_depth not in pilot
    assert "DEPTH EXCLUDES PLATE" in pilot
    assert "BOTTOMING-TAP" in pilot
    assert changed.PLATE_SCREW_TAP_RESERVE == pytest.approx(
        float(thread_depth) * 25.4 - changed.PLATE_SCREW_ENGAGED
    )
    _assert_fitter_text_spacing(changed)


def _assert_fitter_text_spacing(fitter) -> None:
    """Conservative offline text envelopes; the parent owns native ink review."""
    line_pitch = 0.0035  # default note cap height plus interline allowance
    steps = drawing._wrapped(
        fitter.ASSEMBLY_STEPS, width=drawing.STEPS_LINE_WIDTH,
        heading="ASSEMBLY SEQUENCE",
    )
    setup = drawing._wrapped(
        (fitter.CLAMPED_SETUP_NOTE,), width=drawing.SETUP_NOTE_WIDTH
    )
    assert all(len(line) <= drawing.STEPS_LINE_WIDTH for line in steps.splitlines())
    assert all(len(line) <= drawing.SETUP_NOTE_WIDTH for line in setup.splitlines())
    assert (
        drawing.STEPS_XY[1] - len(steps.splitlines()) * line_pitch
        > drawing.CHECKS_XY[1] + line_pitch
    )
    assert (
        drawing.SETUP_NOTE_XY[1] - len(setup.splitlines()) * line_pitch
        > drawing.SHEET_INNER_BORDER[1] + line_pitch
    )
    assert drawing.SETUP_NOTE_XY[1] < drawing.UNDERSIDE_CENTER[1] - 0.020
    # Initial native outline top: 206.0755 mm. The old 4 mm cut overhang
    # left the upper arrow below the setting dimension line.
    # At text Y220 the native setting line is Y211.6656; its witness ends
    # 1 mm beyond it. The 18 mm overhang places the complete upper arrow
    # above that witness, with the overall reference still above the arrow.
    upper_arrow_y = 0.2060755 + drawing.CLAMP_SECTION_TOP_CLEARANCE
    setting_line_y = drawing.STOP_POSITION_TEXT_Y - 0.0083344
    assert upper_arrow_y > setting_line_y + 0.001 + 0.002
    assert upper_arrow_y + 0.00635 < drawing.OVERALL_LENGTH_TEXT_Y - 0.010
    # The reference nominal stays above Front; overall remains above it.
    assert drawing.STOP_POSITION_TEXT_Y - line_pitch > drawing.FRONT_CENTER[1] + 0.012
    assert drawing.OVERALL_LENGTH_TEXT_Y > drawing.STOP_POSITION_TEXT_Y + line_pitch
    assert drawing.OVERALL_LENGTH_TEXT_Y + line_pitch < drawing.SHEET_INNER_BORDER[3]


def test_fitter_text_has_room_for_setting_and_pilot_depths() -> None:
    _assert_fitter_text_spacing(SimpleNamespace(**{**vars(spec), **vars(sheet)}))


def _section_setting_geometry(upper_extension):
    """Native dimension arrays with a marker calibrated to b3's measured gap.

    Lines and arrows follow the retained 20261020T083921201Z native audit's
    NearFace display: witnesses extend 1 mm past the dimension line. The
    plain value rests on that line, as the same audit's native RD1 does.
    At 16 mm upper extension, b3 measured 0.354 mm clearance. Only that gap
    was retained, so this synthetic marker envelope reproduces the gap,
    not unknown b3 absolute bounds, glyph height or arrow dimensions.
    Translation from that measured baseline is an offline layout control;
    native acceptance and the upper overall-reference gap still need review.
    """
    upper_shift = upper_extension - 0.016
    marker_bottom = 0.2126656 + 0.000354 + upper_shift
    arrow_y = marker_bottom + 0.003
    marker_height = 0.0115739
    section = [
        1, 0, 1,
        0, 0.1199, arrow_y, 0, 0.1199, 0.1699245, 0,
        0.1199, arrow_y, 0, 0.1079, arrow_y, 0, 0.006, 0.003, 0,
        0.1199, 0.1699245, 0, 0.1079, 0.1699245, 0, 0.006, 0.003, 0,
        0.0999105, marker_bottom + marker_height, 0,
        0.0999105, 0.1776114, 0,
        marker_height,
    ]
    lines = [
        (0, 0, 0, 0, 0.035, 0.1993875, -0.0038495, 0.035, 0.2126656, -0.0038495),
        (0, 0, 0, 0, 0.1094, 0.1993875, -0.0038495, 0.1094, 0.2126656, -0.0038495),
        (0, 0, 0, 0, 0.035, 0.2116656, -0.0038495, 0.1094, 0.2116656, -0.0038495),
    ]
    arrows = [
        (0.035, 0.2116656, -0.0038495, 1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1),
        (0.1094, 0.2116656, -0.0038495, -1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1),
    ]
    text_position = [0.050, 0.2116656, -0.0038495]
    data = SimpleNamespace(
        GetLineCount=lambda: len(lines),
        GetLineAtIndex2=lambda index: lines[index],
        GetArrowHeadCount=lambda: len(arrows),
        GetArrowHeadAtIndex2=lambda index: arrows[index],
        GetTextCount=lambda: 1,
        GetTextAtIndex=lambda index: "74.4 ±0.10",
        GetTextPositionAtIndex=lambda index: text_position,
        GetTextHeightAtIndex=lambda index: 0.0035,
        GetTextAngleAtIndex=lambda index: 0.0,
        GetTextRefPositionAtIndex=lambda index: 1,
    )
    front = SimpleNamespace(GetSectionLineInfo2=lambda: section)
    display = SimpleNamespace(GetDisplayData=lambda: data)
    return front, display, section, lines, arrows


@pytest.mark.parametrize(
    "defect",
    (None, "old placement", "witness intrusion", "arrow intrusion", "truncated section",
     "missing section", "missing ink", "truncated line", "truncated arrow",
     "text below line", "missing text", "truncated text", "wrong reference",
     "rotated text", "nonfinite text", "zero text height"),
)
def test_section_marker_clears_native_setting_ink(monkeypatch, defect) -> None:
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    front, display, section, lines, arrows = _section_setting_geometry(
        drawing.CLAMP_SECTION_TOP_CLEARANCE
    )
    if defect == "old placement":
        front, display, section, lines, arrows = _section_setting_geometry(0.016)
    elif defect == "witness intrusion":
        lines.append((0, 0, 0, 0, 0.1094, 0.198, 0, 0.1094, 0.224, 0))
    elif defect == "arrow intrusion":
        arrows[0] = (0.1094, 0.217, 0, 0, 1, 0, 0.004, 0.000762, 0, 0, 0, 1)
    elif defect == "truncated section":
        section.pop()
    elif defect == "missing section":
        section[0] = 0
    elif defect == "missing ink":
        lines.clear()
        arrows.clear()
    elif defect == "truncated line":
        lines[0] = lines[0][:8]
    elif defect == "truncated arrow":
        arrows[0] = arrows[0][:8]
    elif defect == "text below line":
        display.GetDisplayData().GetTextPositionAtIndex = lambda index: (0.050, 0.210, 0.0)
    elif defect == "missing text":
        display.GetDisplayData().GetTextCount = lambda: 0
    elif defect == "truncated text":
        display.GetDisplayData().GetTextPositionAtIndex = lambda index: (0.050,)
    elif defect == "wrong reference":
        display.GetDisplayData().GetTextRefPositionAtIndex = lambda index: 2
    elif defect == "rotated text":
        display.GetDisplayData().GetTextAngleAtIndex = lambda index: 0.25
    elif defect == "nonfinite text":
        display.GetDisplayData().GetTextPositionAtIndex = lambda index: (0.050, float("nan"), 0.0)
    elif defect == "zero text height":
        display.GetDisplayData().GetTextHeightAtIndex = lambda index: 0.0
    if defect is None:
        drawing._assert_section_setting_clearance(front, display)
    else:
        with pytest.raises(RuntimeError, match="clamped setting:"):
            drawing._assert_section_setting_clearance(front, display)


def test_marker_deficit_translation_keeps_bounds_on_refusal(monkeypatch) -> None:
    """The applied production extension must recover b3's measured deficit.

    This checks the physical clearance after the recipe's actual extension
    change, not a separately hardcoded successful translation. Absolute
    marker bounds remain synthetic, as described by the calibrated fixture.
    """
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    measured_extension = 0.016
    measured_gap = 0.000354
    events = []
    monkeypatch.setattr(
        drawing._telemetry, "event",
        lambda name, **attributes: events.append((name, attributes)),
    )
    front, display, *_ = _section_setting_geometry(measured_extension)
    with pytest.raises(RuntimeError, match="marker bottom.*dimension ink top"):
        drawing._assert_section_setting_clearance(front, display)
    front, display, *_ = _section_setting_geometry(
        drawing.CLAMP_SECTION_TOP_CLEARANCE
    )
    drawing._assert_section_setting_clearance(front, display)
    before, after = [
        attributes for name, attributes in events
        if name.endswith(".section_setting_clearance")
    ]
    applied_shift = drawing.CLAMP_SECTION_TOP_CLEARANCE - measured_extension
    assert before["section_clearance_m"] == pytest.approx(measured_gap)
    assert before["section_clearance_m"] < drawing.SECTION_SETTING_CLEARANCE
    assert after["section_marker_bottom_m"] - before["section_marker_bottom_m"] == pytest.approx(
        applied_shift
    )
    assert after["section_ink_top_m"] == before["section_ink_top_m"]
    assert after["section_clearance_m"] == pytest.approx(measured_gap + applied_shift)
    assert after["section_clearance_m"] >= drawing.SECTION_SETTING_CLEARANCE
    assert after["required_clearance_m"] == drawing.SECTION_SETTING_CLEARANCE


@pytest.mark.parametrize("text_drop", (0.0, 2.0**-27, 2.0**-25, 0.0005))
def test_plain_native_value_rests_on_dimension_line(monkeypatch, text_drop) -> None:
    """Replay actual RD1 display data, not a value lifted above its witnesses.

    Captured in the 20261020T083921201Z stick layout audit: native text and
    horizontal dimension line share Y234.2219 mm; witnesses end 1 mm higher.
    The section marker is a separate translated offline control, placed well
    above this recorded overall dimension solely to isolate text clearance.
    """
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    front, display, _section, lines, arrows = _section_setting_geometry(0.050)
    lines[:] = [
        (0, 0, 0, 0, 0.035, 0.1993875, -0.0039495, 0.035, 0.2352219, -0.0039495),
        (0, 0, 0, 0, 0.235, 0.1993875, -0.0039495, 0.235, 0.2352219, -0.0039495),
        (0, 0, 0, 0, 0.035, 0.2342219, -0.0039495, 0.235, 0.2342219, -0.0039495),
    ]
    arrows[:] = [
        (0.035, 0.2342219, -0.0039495, 1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1),
        (0.235, 0.2342219, -0.0039495, -1, 0, 0, 0.003556, 0.000762, 0, 0, 0, 1),
    ]
    data = display.GetDisplayData()
    data.GetTextAtIndex = lambda index: " (202.0) "
    data.GetTextPositionAtIndex = lambda index: (
        0.1261674, 0.2342219 - text_drop, -0.0039495
    )
    # At this sheet coordinate one float32 ULP is 2^-26 m (~15 nm).
    # Half an ULP is display roundoff; two ULPs and 0.5 mm are real below-line
    # excursions and cannot be admitted as a placement tolerance.
    if text_drop <= 2.0**-26:
        drawing._assert_section_setting_clearance(front, display)
    else:
        with pytest.raises(RuntimeError, match="below its dimension line"):
            drawing._assert_section_setting_clearance(front, display)


@pytest.mark.parametrize(
    "dimension_types",
    (
        (2, 11), (11, 2),
        (3, 11), (11, 3),
        (0, 11), (11, 0),
        (12, 11), (11, 12),
        ("refused", 11), (11, "refused"),
    ),
)
@pytest.mark.parametrize(
    "defect",
    (None, "absent component", "duplicate component", "missing edge", "duplicate edge"),
)
def test_reference_dimensions_select_owned_visible_end_edges(
    monkeypatch, defect, dimension_types
) -> None:
    """Exercise the resolver and shared selection, never a sheet hit-test."""
    selected = []
    selections = []
    displays = []

    class Edge:
        def __init__(self, start, end, assembly_x):
            self.endpoints = tuple(v / 1000.0 for v in (*start, *end))
            self.assembly_x = assembly_x

        def GetCurve(self):
            return SimpleNamespace(IsLine=lambda: True)

        def GetCurveParams2(self):
            return self.endpoints

        def Select4(self, append, data):
            assert data.View is front
            if not append:
                selected.clear()
            assert self not in selected
            selected.append(self)
            selections.append((self, append, data.View))
            return True

    class Display:
        def __init__(self, value):
            self.value = value
            self.text = {}
            self.readbacks = []
            self.dimension_type = dimension_types[len(displays)]
            self.value_reads = 0

            self.Tolerance = SimpleNamespace(
                Type=0,
                SetValues=self.set_tolerance,
                GetMinValue=lambda: self.minimum,
                GetMaxValue=lambda: self.maximum,
            )

        def set_tolerance(self, minimum, maximum):
            self.minimum, self.maximum = minimum, maximum
            return True
        @property
        def Type2(self):
            if self.dimension_type == "refused":
                raise RuntimeError("native dimension type getter refused")
            return self.dimension_type

        @property
        def SystemValue(self):
            self.value_reads += 1
            return self.value

        def GetDimension2(self, index):
            assert index == 0
            return self

        def GetAnnotation(self):
            return SimpleNamespace(GetSpecificAnnotation=lambda: self)

        def SetText(self, index, text):
            self.text[index] = text

        def GetText(self, index):
            self.readbacks.append(index)
            return self.text.get(index, "")

        def SetPrecision3(self, precision, *rest):
            assert rest == (-1, -1, -1)
            self.precision = precision
            self.tolerance_precision = rest[1]

        def GetPrimaryTolPrecision2(self):
            return self.tolerance_precision

        def GetPrimaryPrecision2(self):
            return self.precision

        def GetDisplayData(self):
            return _section_setting_geometry(
                drawing.CLAMP_SECTION_TOP_CLEARANCE
            )[1].GetDisplayData()

    class Draw:
        Extension = SimpleNamespace(
            SelectByID2=lambda *args: pytest.fail("coordinate hit-test used")
        )
        SelectionManager = SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(View=None),
            GetSelectedObjectCount2=lambda mark: len(selected),
        )

        def ActivateView(self, name):
            assert name == "Front"
            return True

        def ClearSelection2(self, all_marks):
            selected.clear()

        def AddHorizontalDimension2(self, x, y, z):
            assert len(selected) == 2
            assert z == 0.0
            expected_y = (
                drawing.OVERALL_LENGTH_TEXT_Y if not displays
                else drawing.STOP_POSITION_TEXT_Y
            )
            assert y == expected_y
            assert x == pytest.approx(
                drawing.FRONT_CENTER[0]
                + sum(edge.assembly_x for edge in selected) / 2000.0
            )
            display = Display(
                abs(selected[1].assembly_x - selected[0].assembly_x) / 1000.0
            )
            displays.append(display)
            return display

    start = Edge(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, stick.BODY_THICKNESS),
        spec.STICK_X_MIN,
    )
    end = Edge(
        (stick.BODY_LENGTH, 0.0, 0.0),
        (stick.BODY_LENGTH, 0.0, stick.BODY_THICKNESS),
        spec.STICK_X_MAX,
    )
    distractor = Edge(
        (0.0, stick.BODY_WIDTH, 0.0),
        (stick.BODY_LENGTH, stick.BODY_WIDTH, 0.0),
        spec.STICK_X_MIN,
    )
    hidden_face = Edge(
        (0.0, stick.BODY_WIDTH, 0.0),
        (0.0, stick.BODY_WIDTH, stick.BODY_THICKNESS), spec.STICK_X_MIN
    )
    stick_component = SimpleNamespace(
        GetPathName=lambda: f"C:\\models\\{spec.STICK}.SLDPRT",
        edges=(distractor, hidden_face, end, start),
    )
    block_component = SimpleNamespace(
        GetPathName=lambda: f"C:\\models\\{spec.BLOCK}.SLDPRT", edges=()
    )
    front = SimpleNamespace(
        GetVisibleComponents=lambda: (block_component, stick_component),
        GetSectionLineInfo2=_section_setting_geometry(
            drawing.CLAMP_SECTION_TOP_CLEARANCE
        )[0].GetSectionLineInfo2,
    )
    adapter = SimpleNamespace(
        currentModel=Draw(), _attempt=lambda operation, **kwargs: operation()
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing_edge_dimensions, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(
        drawing_edge_dimensions._sw_type_info, "early_bound_or_flag",
        lambda value, *args: value,
    )
    monkeypatch.setattr(
        drawing, "visible_component_entities",
        lambda view, component, kind: component.edges,
    )
    monkeypatch.setattr(drawing_edge_dimensions, "view_name", lambda adapter, view: "Front")
    monkeypatch.setattr(drawing_dimensions, "rebuild_drawing", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        drawing_projection, "_projection_frame", lambda adapter, view: (None, None)
    )

    def project(utility, transform, xyz, **kwargs):
        assert xyz[2] == 0.0
        assert xyz[0] in (
            spec.STICK_X_MIN / 1000.0,
            spec.STICK_X_MAX / 1000.0,
            spec.BLOCK_ORIGIN[0] / 1000.0,
        )
        return drawing.FRONT_CENTER[0] + xyz[0], drawing.FRONT_CENTER[1] + xyz[1]

    monkeypatch.setattr(drawing_projection, "_project_through", project)
    monkeypatch.setattr(drawing, "_assert_dimension_ink_on_sheet", lambda *a, **kw: None)
    shown = []
    monkeypatch.setattr(
        drawing, "_show_base_view_sketches",
        lambda adapter, view, sketches, *, label: shown.append(tuple(sketches)),
    )

    def import_setting(*args, **kwargs):
        assert kwargs["dimensions_by_feature"] == sheet.DRAWING_DIMENSIONS
        assert set(kwargs["keep"]) == {spec.SETTING_DIMENSION}
        display = Display(spec.SETTING_NEAR_FACE_MM / 1000.0)
        displays.append(display)
        if display.dimension_type in (2, 11):
            display.text.update({1: "(", 2: ")"})
            display.precision = spec.SETTING_PRECISION
            display.Tolerance.Type = 0
        return [SimpleNamespace(GetSpecificAnnotation=lambda: display)]

    monkeypatch.setattr(drawing, "curate_view_dimensions", import_setting)
    if defect is not None:
        if defect == "absent component":
            front.GetVisibleComponents = lambda: (block_component,)
            message = "expected one visible.*found 0"
        elif defect == "duplicate component":
            duplicate_component = SimpleNamespace(
                GetPathName=stick_component.GetPathName, edges=stick_component.edges
            )
            front.GetVisibleComponents = lambda: (
                block_component, stick_component, duplicate_component
            )
            message = "expected one visible.*found 2"
        elif defect == "missing edge":
            stick_component.edges = (distractor, hidden_face, end)
            message = "expected one exact visible line.*found 0"
        else:
            duplicate_edge = Edge(
                (0.0, 0.0, 0.0),
                (0.0, 0.0, stick.BODY_THICKNESS),
                spec.STICK_X_MIN,
            )
            stick_component.edges = (*stick_component.edges, duplicate_edge)
            message = "expected one exact visible line.*found 2"
        with pytest.raises(RuntimeError, match=message):
            drawing._add_assembly_dimensions(adapter, front)
        assert selections == []
        assert displays == []
        return
    invalid_index = next(
        (index for index, kind in enumerate(dimension_types) if kind not in (2, 11)),
        None,
    )
    if invalid_index is not None:
        # Values deliberately match the requested lengths even for angular
        # dimensions: a value-only guard cannot detect this defect.
        label = drawing.ASSEMBLY_DIMENSIONS[invalid_index][0]
        kind = dimension_types[invalid_index]
        message = (
            "native dimension type getter refused"
            if kind == "refused"
            else f"measuring-stick {label}: expected a linear dimension, got type {kind}"
        )
        with pytest.raises(RuntimeError, match=message):
            drawing._add_assembly_dimensions(adapter, front)
        assert len(displays) == invalid_index + 1
        assert displays[-1].value_reads == 0
        assert displays[-1].text == {}
        assert not hasattr(displays[-1], "precision")
        return
    settled = drawing._add_assembly_dimensions(adapter, front)
    assert shown == [(spec.SETTING_FEATURE,)]
    assert [(edge, append) for edge, append, view in selections] == [
        (start, False), (end, True)
    ]
    assert [display.value * 1000.0 for display in displays] == pytest.approx(
        [201.93, spec.SETTING_NEAR_FACE_MM]
    )
    for index, display in enumerate(displays):
        assert display.value_reads == 1
        assert display.text[1] == "("
        assert display.text[2] == ")"
        if index == 0:
            assert {1, 2} <= set(display.readbacks)
        assert display.precision == (sheet.DRAWING_REFERENCE_PRECISION if index == 0 else spec.SETTING_PRECISION)
        if index == 1:
            assert display.Tolerance.Type == 0
            assert display.text[3] == display.text[4] == ""
            assert {3, 4} <= set(display.readbacks)
    settled()
    displays[1].Tolerance.Type = 4
    with pytest.raises(RuntimeError, match="settled assembly pose"):
        settled()
    displays[1].Tolerance.Type = 0
    displays[1].text[1] = ""
    with pytest.raises(RuntimeError, match="settled assembly pose"):
        settled()
    displays[1].text[1] = "("
    for field in (3, 4):
        displays[1].text[field] = "STALE CAPTION"
        with pytest.raises(RuntimeError, match="settled native caption"):
            settled()
        displays[1].text[field] = ""


def _exploded_projection(point) -> tuple[float, float]:
    octant = next(iter(spec.DRAWING_EXPLODED_OCTANTS.values()))
    x_axis, y_axis, _viewer = octant_axes(*octant)
    return tuple(sum(value * axis[i] for i, value in enumerate(point)) for axis in (x_axis, y_axis))


def test_exploded_camera_is_above_with_the_screw_head_projected_above_its_tip() -> None:
    octant = next(iter(spec.DRAWING_EXPLODED_OCTANTS.values()))
    _x_axis, y_axis, viewer = octant_axes(*octant)
    assert y_axis[1] > 0.0 and viewer[1] > 0.0
    offset = tuple(
        sum(distance for _label, families, key, distance in explode.EXPLODE_STEPS
            if spec.THUMB_SCREW in families and key == axis)
        for axis in "xyz"
    )
    head = tuple(spec.THUMB_ORIGIN[i] + offset[i] for i in range(3))
    tip = tuple(value + offset[i] for i, value in enumerate(
        _image(spec.THUMB_ROWS, spec.THUMB_ORIGIN, (thumb.OVERALL_LEN, 0.0, 0.0))
    ))
    assert _exploded_projection(head)[1] > _exploded_projection(tip)[1]


def _iso_hull(box) -> list[tuple[float, float]]:
    """Project physical working-frame boxes through the upright named camera."""
    points = sorted(
        {
            tuple(round(value, 9) for value in _exploded_projection((x, y, z)))
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
    """The upright named camera separates every exploded component box;
    only the long stick crosses the block."""
    head = plate_screw.HEAD_DIA / 2.0
    knurl = thumb.HEAD_DIA / 2.0
    boxes = {
        "block": ((0.0, stop.BLOCK_LENGTH), (-stop.BLOCK_HEIGHT, 0.0), (-stop.BLOCK_DEPTH, 0.0)),
        spec.PLATE: (
            (0.0, stop.BLOCK_LENGTH),
            (-stop.BLOCK_HEIGHT, 0.0),
            (-stop.PLATE_Z_MAX, -stop.PLATE_Z_MIN),
        ),
        spec.THUMB_SCREW: (
            (stop.THUMB_AXIS_X - knurl, stop.THUMB_AXIS_X + knurl),
            (spec.THUMB_HEAD_FACE_Y, spec.THUMB_TIP_Y),
            (-stop.THUMB_AXIS_Z - knurl, -stop.THUMB_AXIS_Z + knurl),
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
            (-stop.PLATE_HOLE_Y - head, -stop.PLATE_HOLE_Y + head),
            (spec.PLATE_SCREW_HEAD_Z, spec.PLATE_SCREW_TIP_Z),
        )
    hulls = {}
    for name, box in boxes.items():
        shift = [0.0, 0.0, 0.0]
        for _label, moved, axis, distance in explode.EXPLODE_STEPS:
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

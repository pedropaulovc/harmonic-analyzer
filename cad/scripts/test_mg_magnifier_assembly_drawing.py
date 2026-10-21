"""Offline contract for the magnifier assembly drawing and its stack settings."""

import asyncio
import math
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_balloons
import _transforms
import build_mg_magnifier_assembly as assembly
import draw_mg_magnifier_assembly as drawing
import joint_retention
import mg_magnifier_assembly_sheet as notes
import mg_magnifier_assembly_spec as stack
import mg_magnifier_assembly_steps as steps
import mg_magnifier_explode_spec as explode
import mg_wheel_axle_spacer_spec
import mg_wheel_axle_spec
import mg_wheel_group
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout

# The LANDSCAPE sheet's free field right of the isometric: inside the border
# (about 13 mm in from the trim) and above the title block (sheet metres).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
BORDER = 0.013
SHEET_RIGHT = _TEMPLATE.width_m - BORDER
SHEET_TOP = _TEMPLATE.height_m - BORDER
TITLE_BLOCK_TOP = _TEMPLATE.title_block_top_m
ISO_RIGHT = 0.255


def test_magnifier_keeps_registry_outputs_and_precomputed_placement() -> None:
    spec = DRAWINGS_BY_NAME["mg_magnifier_assembly"]
    assert spec.source_kind == "assembly"
    assert spec.part == "mg_magnifier"
    assert drawing.SOURCE == spec.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        spec.outputs["slddrw"], spec.outputs["pdf"], spec.outputs["png"]
    )
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    assert drawing.FRONT_CENTER == (0.070, 0.150)
    assert drawing.RIGHT_CENTER == (0.168, 0.150)
    assert drawing.ISO_CENTER == (0.225, 0.140)


def test_the_stack_settings_are_the_group_stations_with_their_bands() -> None:
    # The rev-10 19.5 plus the spacer that lands the wheel on the pen line.
    assert (
        stack.PRESS_GAUGE
        == mg_wheel_axle_spec.PRESS_GAUGE
        == pytest.approx(19.5 + mg_wheel_axle_spacer_spec.LENGTH)
    )
    assert stack.PRESS_GAUGE_TOL == mg_wheel_axle_spec.PRESS_GAUGE_TOL == 0.05
    # The printed endshake band is exactly the group's set window.
    assert stack.ENDSHAKE - stack.ENDSHAKE_TOL == pytest.approx(
        mg_wheel_group.ENDSHAKE_MIN
    )
    assert stack.ENDSHAKE + stack.ENDSHAKE_TOL == pytest.approx(
        mg_wheel_group.ENDSHAKE_MAX
    )
    # Chain stations: bar front face, shank step, spigot face, front washer.
    face, step, hub, washer = stack.CHAIN_D
    assert face == 0.0
    assert step == mg_wheel_axle_spec.STEP_Y
    assert washer - hub == pytest.approx(stack.ENDSHAKE)
    assert washer == mg_wheel_group.FRONT_WASHER_D
    assert step < hub < washer


def test_the_stack_dimensions_are_marked_banded_and_called_out() -> None:
    names = {stack.PRESS_GAUGE_DIMENSION, stack.ENDSHAKE_DIMENSION}
    assert notes.DRAWING_DIMENSIONS == {stack.FEATURE: names}
    assert set(stack.DRAWING_PRECISION[stack.FEATURE]) == names
    assert set(stack.DIMENSION_TOLERANCES) == names
    assert set(notes.DIMENSION_CALLOUTS) == names == set(drawing.CALLOUT_LOCATION)
    assert stack.DIMENSION_TOLERANCES[stack.PRESS_GAUGE_DIMENSION] == 0.05
    assert stack.DIMENSION_TOLERANCES[stack.ENDSHAKE_DIMENSION] == pytest.approx(0.05)
    # One detail imports each setting.
    assert set(drawing.PRESSED_KEEP) == {stack.PRESS_GAUGE_DIMENSION}
    assert set(drawing.ENDSHAKE_KEEP) == {stack.ENDSHAKE_DIMENSION}


def _circle_box(detail) -> tuple[float, float, float, float]:
    x, y = detail.centre
    r = detail.crop_radius
    return x - r, y - r, x + r, y + r


@pytest.mark.parametrize("detail", [drawing.PRESSED, drawing.ENDSHAKE])
def test_each_detail_sits_in_the_free_field_with_its_label_under_its_ink(
    detail,
) -> None:
    left, _bottom, right, top = _circle_box(detail)
    assert left > ISO_RIGHT
    assert right < SHEET_RIGHT
    assert top < SHEET_TOP
    label_x, label_top = detail.label_xy
    ink_bottom = detail.sheet_xy(detail.centre_d, -detail.ink_drop_mm)[1]
    # Just under the detail's lowest printed edge, not under its unprinted
    # crop circle.
    assert 0.002 <= ink_bottom - label_top <= 0.005
    # Its lines, about 4.5 mm each, clear the title block.
    lines = detail.label_text.splitlines()
    assert label_top - 0.0045 * len(lines) > TITLE_BLOCK_TOP
    assert left <= label_x


def test_the_pressed_detail_label_clears_the_endshake_crop() -> None:
    label = drawing.PRESSED.label_text
    # The pressed detail's three-line label still clears the endshake crop.
    lines = len(label.splitlines())
    assert (
        drawing.PRESSED.label_xy[1] - 0.0045 * lines > _circle_box(drawing.ENDSHAKE)[3]
    )


def test_each_detail_s_lowest_ink_is_its_geometry() -> None:
    import mg_magnifying_wheel_spec as wheel
    import mg_vn_wheel_axle_front_washer_spec as washer
    import mg_vn_wheel_axle_nut_spec as nut
    from mg_wheel_bar_geom import BAR_SIDE

    # The bar's underside: the axle runs mid-height through the bar.
    assert drawing.PRESSED.ink_drop_mm == pytest.approx(BAR_SIDE / 2.0)
    # The circle's chord at the spigot face: the spigot fills it there, and
    # the nuts and washer beside it stand higher.
    detail = drawing.ENDSHAKE
    offset = detail.centre_d - stack.HUB_FRONT_D
    assert detail.ink_drop_mm == pytest.approx(
        math.sqrt(detail.radius_mm**2 - offset**2)
    )
    assert detail.ink_drop_mm < wheel.SPIGOT_DIA / 2.0
    assert max(nut.ACROSS_CORNERS, washer.OD) / 2.0 < detail.ink_drop_mm


def test_the_details_and_labels_do_not_overlap() -> None:
    upper_label_bottom = drawing.PRESSED.label_xy[1] - 0.009
    assert _circle_box(drawing.ENDSHAKE)[3] < upper_label_bottom


def test_an_above_callout_with_a_line_break_is_refused(monkeypatch) -> None:
    assert drawing.CALLOUT_LOCATION[stack.PRESS_GAUGE_DIMENSION] == "above"
    assert drawing._printable_callouts() == notes.DIMENSION_CALLOUTS
    monkeypatch.setitem(
        notes.DIMENSION_CALLOUTS, stack.PRESS_GAUGE_DIMENSION, "PRESS GAUGE\nLOCKNUT"
    )
    with pytest.raises(RuntimeError, match="line break do not print"):
        drawing._printable_callouts()


class _Display:
    def __init__(self, parts: dict[int, str]) -> None:
        self.parts = parts

    def GetText(self, part: int) -> str:
        return self.parts.get(part, "")


def test_each_callout_reads_back_from_its_own_compartment() -> None:
    callouts = notes.DIMENSION_CALLOUTS
    gauge, endshake = stack.PRESS_GAUGE_DIMENSION, stack.ENDSHAKE_DIMENSION
    good = [
        (gauge, _Display({3: callouts[gauge]})),
        (endshake, _Display({4: callouts[endshake].replace("\n", "\r\n")})),
    ]
    drawing._assert_callouts(good, callouts)
    # The gauge's text in the below compartment is not its callout.
    wrong = [(gauge, _Display({4: callouts[gauge]})), good[1]]
    with pytest.raises(RuntimeError, match="above callout reads ''"):
        drawing._assert_callouts(wrong, callouts)


def test_each_detail_frames_both_ends_of_its_dimension() -> None:
    for detail, (start, end) in (
        (drawing.PRESSED, (0.0, stack.PRESS_GAUGE)),
        (drawing.ENDSHAKE, (stack.HUB_FRONT_D, stack.HUB_FRONT_D + stack.ENDSHAKE)),
    ):
        for d in (start, end):
            assert abs(d - detail.centre_d) < detail.radius_mm, (detail.title, d)


def test_the_gauge_line_clears_the_bar_inside_the_crop() -> None:
    from mg_wheel_bar_geom import BAR_SIDE

    assert BAR_SIDE / 2.0 + 5.0 <= drawing.GAUGE_RISE < drawing.PRESSED.radius_mm
    x, y = drawing.PRESSED_KEEP[stack.PRESS_GAUGE_DIMENSION]
    assert math.dist((x, y), drawing.PRESSED.centre) < drawing.PRESSED.crop_radius


def test_the_endshake_line_rides_above_the_nuts_and_text_stands_past_the_crop() -> None:
    import mg_vn_wheel_axle_front_washer_spec as washer
    import mg_vn_wheel_axle_nut_spec as nut

    assert max(nut.ACROSS_CORNERS, washer.OD) / 2.0 < drawing.ENDSHAKE_RISE
    x, _y = drawing.ENDSHAKE_KEEP[stack.ENDSHAKE_DIMENSION]
    assert x > _circle_box(drawing.ENDSHAKE)[2]
    assert x + 0.030 < SHEET_RIGHT


def test_the_gauge_detail_shows_only_the_bar_and_the_axle() -> None:
    assert drawing.PRESSED.stems == {"mg-wheel-bar", "mg-wheel-axle"}
    assert {
        "mg-vn-wheel-axle-front-washer",
        "mg-vn-wheel-axle-nut",
        "mg-magnifying-wheel",
    } <= (drawing.ENDSHAKE.stems)


def test_the_stack_chain_is_authored_on_the_axle_and_driven_from_globals(
    monkeypatch,
) -> None:
    """Run the builder's chain helper against fakes: every async step must
    execute, the chain must lie on the axle line through the four stations,
    and both printed settings must carry their bands."""
    import asyncio
    from types import SimpleNamespace

    import build_mg_magnifier_assembly as builder

    ok = lambda data=None: SimpleNamespace(is_success=True, data=data, error=None)  # noqa: E731
    lines: list[tuple[float, ...]] = []
    globals_authored: dict[str, str] = {}
    equations: dict[str, str] = {}
    toleranced: list[tuple] = []
    lengths: dict[str, float] = {}
    blanked: list[str] = []

    class Adapter:
        _sketch_entities: dict[str, object] = {}
        currentModel = object()

        async def create_sketch(self, plane):
            assert plane == "Right"
            return ok()

        async def add_line(self, *coords):
            name = f"leg{len(lines)}"
            lines.append(coords)
            self._sketch_entities[name] = object()
            return ok(name)

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

    def early_bound(entity, iface):
        if iface == "IAssemblyDoc":
            return SimpleNamespace(FeatureByName=lambda name: name)
        if iface == "IFeature":
            return SimpleNamespace(Visible=1 if entity in blanked else 2)
        return SimpleNamespace(ConstructionGeometry=False)

    async def set_global(adapter, name, expression):
        globals_authored[name] = expression

    async def drive_dimension(adapter, name, expression):
        equations[name] = expression

    async def dimension_between(adapter, a, b, kind, value, name):
        lengths[name] = value

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(builder, "set_global", set_global)
    monkeypatch.setattr(builder, "drive_dimension", drive_dimension)
    monkeypatch.setattr(builder, "dimension_between", dimension_between)
    monkeypatch.setattr(builder, "SketchDims", Dims)
    monkeypatch.setattr(builder, "_early_bound", early_bound)
    for name in ("anchor_point_to_origin", "ensure_fully_defined"):
        monkeypatch.setattr(builder, name, noop)
    for name in (
        "set_sketch_direct_db",
        "name_last_feature",
        "_set_tolerance_precision",
        "apply_drawing_precision",
        "mark_dimensions_for_drawing",
    ):
        monkeypatch.setattr(builder, name, lambda *a, **kw: None)
    monkeypatch.setattr(builder, "_named_dimension", lambda *a: (object(), None))
    monkeypatch.setattr(
        builder,
        "set_dimension_symmetric_tolerance",
        lambda adapter, feature, name, tol: toleranced.append((feature, name, tol)),
    )
    monkeypatch.setattr(
        builder, "blank_sketch", lambda adapter, feature: blanked.append(feature)
    )

    asyncio.run(builder._author_axle_stack_reference(Adapter()))

    # Right-plane sketch x is machine -z: the chain runs forward from the bar
    # front face along the axle's height.
    stations = [-stack.BAR_FRONT_Z + d for d in stack.CHAIN_D]
    assert lines == [
        (x0, stack.AXLE_Y, x1, stack.AXLE_Y) for x0, x1 in zip(stations, stations[1:])
    ]
    assert lengths[stack.PRESS_GAUGE_DIMENSION] == pytest.approx(stack.PRESS_GAUGE)
    assert lengths[stack.ENDSHAKE_DIMENSION] == pytest.approx(stack.ENDSHAKE)
    feature = stack.FEATURE
    assert equations == {
        f"StackFaceX@{feature}": '"AxleBarFrontFace"',
        f"StackAxisY@{feature}": '"AxleAxisY"',
        f"{stack.PRESS_GAUGE_DIMENSION}@{feature}": '"AxlePressGauge"',
        f"StepToHubFront@{feature}": '"HubFrontStation" - "AxlePressGauge"',
        f"{stack.ENDSHAKE_DIMENSION}@{feature}": '"WheelEndshake"',
    }
    assert globals_authored == {
        "AxleBarFrontFace": f"{-stack.BAR_FRONT_Z}mm",
        "AxleAxisY": f"{stack.AXLE_Y}mm",
        "AxlePressGauge": f"{stack.PRESS_GAUGE}mm",
        "HubFrontStation": f"{stack.HUB_FRONT_D}mm",
        "WheelEndshake": f"{stack.ENDSHAKE}mm",
    }
    assert toleranced == [
        (feature, name, band) for name, band in stack.DIMENSION_TOLERANCES.items()
    ]
    assert blanked == [feature]

def test_the_package_has_four_landscape_sheets_with_the_wire_steps_on_the_last() -> None:
    assert drawing.SHEET_NAMES[-1] == "ASSEMBLY STEPS"
    assert len(drawing.SHEET_NAMES) == 4
    assert set(drawing.SHEET_LAYOUTS.values()) == {DrawingLayout.LANDSCAPE}
    # MHA-HA-00 prints "LEVER WIRE PER MHA-MG-00 (SHEET 4)" and names these keys.
    assert steps.WIRE_HOOKED_KEY == "lever-wire-hooked"
    assert steps.WIRE_TIED_KEY == "lever-wire-tied"
    assert steps.SEQUENCE[-2:] == (steps.WIRE_HOOKED_KEY, steps.WIRE_TIED_KEY)


def test_the_drawing_key_reads_only_the_package_parts_config() -> None:
    # The builder's COM explode (_mg_magnifier_explode -> _assembly_patterns ->
    # _assembly) reads every parts/* and assemblies/* YAML, so importing it
    # re-keyed this sheet on any part edit. The drawing reads the pure spec.
    from pathlib import Path

    import _buildgraph

    script = Path(drawing.__file__)
    names = {Path(dep).name for dep in _buildgraph.module_deps_of(script)}
    assert not names & {
        "_assembly.py",
        "_assembly_patterns.py",
        "_mg_magnifier_explode.py",
    }
    assert not [token for token in _buildgraph.config_files_of(script) if "*" in token]


def test_the_sheet_text_is_on_the_drawing_recipe_only() -> None:
    # Code review C03: the BOM, callout and step text is drawing-only, so a
    # wording edit must re-key the MHA-MG-00 sheet and never the native
    # assembly:mg_magnifier recipe the builder's closure keys.
    import _buildgraph

    def closure(module) -> set[str]:
        return {
            Path(dep).name for dep in _buildgraph.module_deps_of(Path(module.__file__))
        }

    assert "mg_magnifier_assembly_sheet.py" in closure(drawing)
    assert "mg_magnifier_assembly_spec.py" in closure(assembly)
    assert "mg_magnifier_assembly_sheet.py" not in closure(assembly)
    # Nothing the sheet prints stays behind in the builder's spec.
    for name in (
        "BOM_ORDER",
        "BOM_DESCRIPTIONS",
        "STEP_TEXT",
        "ASSEMBLY_STEPS",
        "ASSEMBLY_CHECKS",
        "DIMENSION_CALLOUTS",
        "LEVER_CALLOUTS",
        "DRAWING_DIMENSIONS",
    ):
        assert not hasattr(stack, name), name


def test_the_wire_balloon_lands_on_the_mid_run_ring_facing_the_viewer() -> None:
    import math

    import build_mg_vn_lever_wire
    import mg_vn_lever_wire_geom as wire

    x, station, z = drawing.WIRE_BALLOON_POINT_MM
    # On the build's split ring, mid-run, on the wire's surface.
    assert station == pytest.approx(build_mg_vn_lever_wire.BALLOON_RING_STATION)
    assert station == pytest.approx(wire.WIRE_LEN / 2.0)
    assert math.hypot(x, z) == pytest.approx(wire.WIRE_DIA / 2.0)
    assert drawing.BALLOON_ANCHORS["mg-vn-lever-wire"].point_mm == drawing.WIRE_BALLOON_POINT_MM
    # Turned into the machine frame, the point's outward normal faces +X+Y+Z.
    delta = [h - d for h, d in zip(wire.WIRE_START, wire.WIRE_END)]
    axis = [v / math.hypot(*delta) for v in delta]
    n = math.hypot(axis[0], axis[1])
    ex = (axis[1] / n, -axis[0] / n, 0.0)
    ez = (
        ex[1] * axis[2] - ex[2] * axis[1],
        ex[2] * axis[0] - ex[0] * axis[2],
        ex[0] * axis[1] - ex[1] * axis[0],
    )
    normal = [x * a + z * b for a, b in zip(ex, ez)]
    viewer = [1.0 / math.sqrt(3.0)] * 3
    facing = sum(a * b for a, b in zip(normal, viewer)) / math.hypot(*normal)
    along = sum(a * b for a, b in zip(axis, viewer))
    # All of the viewer direction square to the axis points at the ring point.
    assert facing == pytest.approx(math.sqrt(1.0 - along**2))


def test_the_wire_wrap_has_the_required_geometric_margin() -> None:
    assert mg_wheel_group.LEVER_WIRE_WRAP_LEFT_DEG >= mg_wheel_group.WRAP_MARGIN_DEG


def test_the_assembled_views_name_their_direction_clear_of_their_neighbours() -> None:
    # r8's printed outlines (sheet metres): Front, Right, Isometric.
    front = (0.041, 0.091, 0.099, 0.204)
    right = (0.153, 0.091, 0.183, 0.204)
    iso_left = 0.194
    boxes = []
    for outline, name in ((front, "*Front"), (right, "*Right")):
        text = drawing.ASSEMBLED_VIEW_CAPTIONS[name]
        left, top = drawing.caption_under(outline, text)
        width = len(text) * drawing.CAPTION_CHAR_WIDTH
        assert left + width / 2.0 == pytest.approx((outline[0] + outline[2]) / 2.0)
        assert top < outline[1]
        assert top - drawing.NOTE_LINE_PITCH > drawing.TITLE_BLOCK[3]
        assert left > drawing.INNER_BORDER[0]
        boxes.append((left, left + width))
    assert boxes[0][1] < boxes[1][0]
    assert boxes[1][1] < iso_left


def test_every_step_is_numbered_in_sequence() -> None:
    assert tuple(notes.STEP_TEXT) == steps.SEQUENCE
    assert notes.ASSEMBLY_STEPS == tuple(
        f"{steps.step_number(key)}. {notes.STEP_TEXT[key]}" for key in steps.SEQUENCE
    )


def test_the_lever_settings_match_the_placed_lever_group() -> None:
    assert stack.LEVER_TIP_X == pytest.approx(assembly.LEVER_X0)
    assert stack.LEVER_AXIS_Y == pytest.approx(assembly.LEVER_ROD_Y)
    assert stack.CLAMP_CENTRE_X == pytest.approx(assembly.CLAMP_X)
    assert stack.FIXTURE_AXIS_Y == pytest.approx(assembly.FIXTURE_POSITION[1])
    assert stack.CLAMP_STATION > 0.0 and stack.FIXTURE_DROP > 0.0
    assert set(notes.LEVER_CALLOUTS) == set(drawing.LEVER_CALLOUT_LOCATION)
    assert stack.LEVER_DRAWING_DIMENSIONS == {
        stack.LEVER_FEATURE: {stack.CLAMP_STATION_DIMENSION, stack.FIXTURE_DROP_DIMENSION}
    }
    drawing._printable_lever_callouts()


def test_the_lever_chain_is_authored_on_the_front_plane_and_driven_from_globals(
    monkeypatch,
) -> None:
    ok = lambda data=None: SimpleNamespace(is_success=True, data=data, error=None)  # noqa: E731
    lines: list[tuple[float, ...]] = []
    relations: list[tuple] = []
    globals_authored: dict[str, str] = {}
    equations: dict[str, str] = {}
    lengths: dict[str, tuple[str, float]] = {}
    anchors: list[tuple] = []
    blanked: list[str] = []

    class Adapter:
        _sketch_entities: dict[str, object] = {}
        currentModel = object()

        async def create_sketch(self, plane):
            assert plane == "Front"
            return ok()

        async def add_line(self, *coords):
            name = f"leg{len(lines)}"
            lines.append(coords)
            self._sketch_entities[name] = SimpleNamespace(ConstructionGeometry=False)
            return ok(name)

        async def add_sketch_constraint(self, *args):
            relations.append(args)
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

    def early_bound(entity, iface):
        if iface == "IAssemblyDoc":
            return SimpleNamespace(FeatureByName=lambda name: name)
        if iface == "IFeature":
            return SimpleNamespace(Visible=1 if entity in blanked else 2)
        return entity

    async def set_global(adapter, name, expression):
        globals_authored[name] = expression

    async def drive_dimension(adapter, name, expression):
        equations[name] = expression

    async def dimension_between(adapter, a, b, kind, value, name):
        lengths[name] = (kind, value)

    async def anchor(adapter, ref, x, y, label):
        anchors.append((ref, x, y))

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(assembly, "set_global", set_global)
    monkeypatch.setattr(assembly, "drive_dimension", drive_dimension)
    monkeypatch.setattr(assembly, "dimension_between", dimension_between)
    monkeypatch.setattr(assembly, "SketchDims", Dims)
    monkeypatch.setattr(assembly, "_early_bound", early_bound)
    monkeypatch.setattr(assembly, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(assembly, "ensure_fully_defined", noop)
    for name in (
        "set_sketch_direct_db",
        "name_last_feature",
        "apply_drawing_precision",
        "mark_dimensions_for_drawing",
    ):
        monkeypatch.setattr(assembly, name, lambda *a, **kw: None)
    monkeypatch.setattr(
        assembly, "blank_sketch", lambda adapter, feature: blanked.append(feature)
    )

    asyncio.run(assembly._author_lever_setting_reference(Adapter()))

    tip = (stack.LEVER_TIP_X, stack.LEVER_AXIS_Y)
    clamp = (stack.CLAMP_CENTRE_X, stack.LEVER_AXIS_Y)
    fixture = (stack.CLAMP_CENTRE_X, stack.FIXTURE_AXIS_Y)
    assert lines == [(*tip, *clamp), (*clamp, *fixture)]
    assert ("leg0", None, "horizontal") in relations
    assert ("leg1", None, "vertical") in relations
    assert ("leg0.end", "leg1.start", "coincident") in relations
    assert anchors == [("leg0.start", *tip)]
    assert lengths == {
        stack.CLAMP_STATION_DIMENSION: ("horizontal_distance", stack.CLAMP_STATION),
        stack.FIXTURE_DROP_DIMENSION: ("vertical_distance", stack.FIXTURE_DROP),
    }
    feature = stack.LEVER_FEATURE
    assert equations == {
        f"LeverTipX@{feature}": '"LeverTipX"',
        f"LeverAxisY@{feature}": '"LeverAxisY"',
        f"{stack.CLAMP_STATION_DIMENSION}@{feature}": '"LeverClampStation"',
        f"{stack.FIXTURE_DROP_DIMENSION}@{feature}": '"LeverFixtureDrop"',
    }
    assert globals_authored == {
        "LeverTipX": f"{stack.LEVER_TIP_X}mm",
        "LeverAxisY": f"{stack.LEVER_AXIS_Y}mm",
        "LeverClampStation": f"{stack.CLAMP_STATION}mm",
        "LeverFixtureDrop": f"{stack.FIXTURE_DROP}mm",
    }
    assert all(entity.ConstructionGeometry for entity in Adapter._sketch_entities.values())
    assert blanked == [feature]


def test_the_explode_moves_every_shown_family_but_the_wire_in_one_group() -> None:
    moved = {
        explode.member_stem(member)
        for step in explode.EXPLODE_STEPS
        for member in step.members
    }
    # The bar with its pressed axle, and the lever with its clamp, stay put
    # as each group's base; everything else moves.
    assert moved == explode.SHOWN_STEMS - {
        explode.WIRE_STEM,
        "mg-wheel-bar",
        "mg-wheel-axle",
        "mg-magnifying-lever",
        "mg-magnifying-clamp",
    }
    assert explode.WHEEL_GROUP_STEMS.isdisjoint(explode.LEVER_GROUP_STEMS)
    assert explode.SHOWN_STEMS == set(notes.BOM_ORDER)


def test_plan_explode_resolves_instances_and_refuses_missing_ones() -> None:
    instances = [
        explode.Instance(f"{stem}-{number}", stem)
        for stem in notes.BOM_ORDER
        for number in range(1, notes.QUANTITIES[stem] + 1)
    ]
    plan = explode.plan_explode(instances)
    assert [step for step, _names in plan] == list(explode.EXPLODE_STEPS)
    for step, names in plan:
        assert names, step.label
        for name in names:
            assert explode.member_stem(name.rsplit("-", 1)[0]) in {
                explode.member_stem(member) for member in step.members
            }
    first_nut = next(
        names for step, names in plan if step.members == ("mg-vn-wheel-axle-nut:1",)
    )
    assert first_nut == ("mg-vn-wheel-axle-nut-1",)
    with pytest.raises(ValueError, match="absent"):
        explode.plan_explode([i for i in instances if i.stem != "mg-output-fixture"])
    with pytest.raises(ValueError, match="no instance"):
        explode.plan_explode([i for i in instances if i.name != "mg-vn-wheel-axle-nut-2"])


def test_the_bom_rows_are_the_registry_parts_with_their_skus() -> None:
    assert drawing.BOM_COMPONENTS == notes.BOM_ORDER
    assert set(notes.BOM_DESCRIPTIONS) == set(notes.BOM_ORDER)
    for stem, row in drawing.PART_ROWS.items():
        assert drawing.BOM_PART_NUMBERS[stem] == row["number"]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (" / ".join(skus) if skus else "-")
    assert drawing.BOM_SKUS["mg-vn-thumb-screw"] == "91882A221"
    assert drawing.BOM_SKUS["mg-magnifying-lever"] == "-"
    assert notes.QUANTITIES["mg-vn-thumb-screw"] == 2


def test_the_bom_screw_lengths_are_the_vendor_specs_fractions() -> None:
    import _mcmaster_90280a201 as clamp_screw
    import mg_vn_magnifying_bracket_screw_spec as bracket_screw
    from _mcmaster_91882a221 import SHANK_LEN as thumb_len

    for stem, length_mm, printed in (
        (notes.CLAMP_SCREW, clamp_screw.SHANK_LEN, "1-1/4"),
        (notes.BRACKET_SCREW, bracket_screw.LENGTH, "5/16"),
        (notes.THUMB_SCREW, thumb_len, "7/16"),
    ):
        assert f" X {printed} " in notes.BOM_DESCRIPTIONS[stem]
        assert float(sum(Fraction(p) for p in printed.split("-"))) == pytest.approx(
            length_mm / 25.4
        )


@pytest.mark.parametrize(
    ("length_mm", "printed"), ((1.5 * 25.4, "1-1/2"), (3.0 / 8.0 * 25.4, "3/8"))
)
def test_a_stock_screw_length_change_reprints_its_bom_fraction(
    monkeypatch, length_mm: float, printed: str
) -> None:
    # Code review C04: a canonical stock-length change must move the printed
    # fraction, not fail an import on a duplicated expected length.
    import importlib

    import _mcmaster_90280a201 as clamp_screw

    monkeypatch.setattr(clamp_screw, "SHANK_LEN", length_mm)
    try:
        importlib.reload(notes)
        assert (
            notes.BOM_DESCRIPTIONS[notes.CLAMP_SCREW]
            == f"#8-32 X {printed} FILLISTER SCREW"
        )
    finally:
        monkeypatch.undo()
        importlib.reload(notes)


def test_a_screw_length_off_the_sixty_fourths_refuses_the_bom(monkeypatch) -> None:
    # A metric 8 mm stock (0.31496 in, 0.0625 mm off 5/16) has no catalogue
    # fraction: the BOM refuses rather than print a rounded one.
    import importlib

    import mg_vn_magnifying_bracket_screw_spec as bracket_screw

    monkeypatch.setattr(bracket_screw, "LENGTH", 8.0)
    try:
        with pytest.raises(ValueError, match="mg-vn-magnifying-bracket-screw length.*1/64"):
            importlib.reload(notes)
    finally:
        monkeypatch.undo()
        importlib.reload(notes)


def _inside(inner, outer) -> bool:
    return (
        inner[0] >= outer[0] - 1e-9
        and inner[1] >= outer[1] - 1e-9
        and inner[2] <= outer[2] + 1e-9
        and inner[3] <= outer[3] + 1e-9
    )


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_the_package_fields_stay_inside_the_border_and_off_the_title_block() -> None:
    bom = (
        drawing.BOM_ANCHOR[0],
        drawing.BOM_BOTTOM,
        drawing.BOM_ANCHOR[0] + sum(drawing.BOM_COLUMN_WIDTHS.values()),
        drawing.BOM_ANCHOR[1],
    )
    for field in (
        drawing.WHEEL_FIELD,
        drawing.LEVER_FIELD,
        drawing.FINISHED_FIELD,
        drawing.BOM_REFERENCE_FIELD,
        bom,
    ):
        assert _inside(field, drawing.INNER_BORDER), field
    for field in (drawing.LEVER_FIELD, drawing.FINISHED_FIELD, drawing.BOM_REFERENCE_FIELD):
        assert not _overlap(field, drawing.TITLE_BLOCK), field
    assert not _overlap(drawing.WHEEL_FIELD, bom)
    assert not _overlap(drawing.WHEEL_FIELD, drawing.TITLE_BLOCK)
    assert not _overlap(drawing.BOM_REFERENCE_FIELD, bom)
    assert drawing.BOM_REFERENCE_FIELD[3] < drawing.BOM_BOTTOM
    assert drawing.FINISHED_FIELD[0] > drawing.STEPS_RIGHT


def test_the_finished_caption_centres_over_its_view() -> None:
    outline = (0.257, 0.080, 0.311, 0.214)
    text = "FINISHED ASSEMBLY (SCALE 1:4)"
    left, top = drawing.caption_over(outline, text)
    width = len(text) * drawing.CAPTION_CHAR_WIDTH
    assert left + width / 2.0 == pytest.approx((outline[0] + outline[2]) / 2.0)
    # r6 printed this caption 68.8 mm wide.
    assert width == pytest.approx(0.0688, abs=0.0005)
    assert left > drawing.STEPS_RIGHT
    assert top - drawing.NOTE_LINE_PITCH > outline[3]
    assert top < drawing.INNER_BORDER[3]


def test_the_wire_balloon_stands_right_of_the_view_on_its_rising_leader() -> None:
    import math

    landing = (0.282, 0.120)
    outline = (0.257, 0.080, 0.311, 0.214)
    x, y = drawing.wire_balloon_centre(
        landing,
        outline,
        rise_deg=drawing.FINISHED_WIRE_BALLOON_RISE_DEG,
        reach=drawing.BALLOON_MARGIN,
    )
    assert x == pytest.approx(outline[2] + drawing.BALLOON_MARGIN)
    assert math.degrees(math.atan2(y - landing[1], x - landing[0])) == pytest.approx(
        drawing.FINISHED_WIRE_BALLOON_RISE_DEG
    )
    assert x < drawing.INNER_BORDER[2] - drawing._PAD
    assert drawing.TITLE_BLOCK[3] < y < drawing.FINISHED_FIELD[3]


def test_the_steps_and_checks_fit_their_column() -> None:
    for block in (drawing.ASSEMBLY_STEPS, drawing.ASSEMBLY_CHECKS):
        assert max(len(line) for line in block.splitlines()) <= drawing.STEPS_LINE_WIDTH
    steps_bottom = drawing.STEPS_XY[1] - len(
        drawing.ASSEMBLY_STEPS.splitlines()
    ) * drawing.NOTE_LINE_PITCH
    checks_bottom = drawing.CHECKS_XY[1] - len(
        drawing.ASSEMBLY_CHECKS.splitlines()
    ) * drawing.NOTE_LINE_PITCH
    assert drawing.STEPS_XY[0] > drawing.INNER_BORDER[0]
    assert drawing.STEPS_XY[1] < drawing.INNER_BORDER[3]
    assert checks_bottom > drawing.INNER_BORDER[1] + drawing._PAD
    assert steps_bottom - drawing.CHECKS_XY[1] == pytest.approx(2 * drawing._PAD)
    assert drawing.STEPS_RIGHT + drawing._PAD <= drawing.FINISHED_FIELD[0]
    assert drawing.STEPS_RIGHT < drawing.TITLE_BLOCK[0]
    assert drawing.ASSEMBLY_STEPS.split() == " ".join(
        ("ASSEMBLY SEQUENCE", *notes.ASSEMBLY_STEPS)
    ).split()
    assert drawing.ASSEMBLY_CHECKS.split() == " ".join(notes.ASSEMBLY_CHECKS).split()
    for number in drawing.BOM_PART_NUMBERS.values():
        if any(number in step for step in notes.ASSEMBLY_STEPS):
            assert number in drawing.ASSEMBLY_STEPS


def test_the_exploded_ladders_keep_the_simplified_configuration() -> None:
    from _drawing_common import _SW_SHADED_EDGES
    from _drawing_view_configuration import (
        SIMPLIFIED_VIEW_CONFIGURATION,
        view_configuration,
    )

    for ladder in (
        drawing.EXPLODED_SCALE_LADDER,
        drawing.LEVER_SCALE_LADDER,
        drawing.FINISHED_SCALE_LADDER,
        drawing.BOM_REFERENCE_SCALE_LADDER,
    ):
        for scale in ladder:
            assert (
                view_configuration(scale, _SW_SHADED_EDGES)
                == SIMPLIFIED_VIEW_CONFIGURATION
            )
    assert drawing.exploded_caption("WHEEL GROUP", (1.0, 3.0)).endswith("(SCALE 1:3)")


def test_the_lever_group_takes_1_2_5_centred_with_its_caption_under_it() -> None:
    # Outlines measured 82.6 x 116.1 mm at 1:3 (r11) and 118.3 x 168.6 at 1:2
    # (r13): size = k / scale + fixed padding.
    def outline_size(denominator: float) -> tuple[float, float]:
        sizes = []
        for at_2, at_3 in ((0.1183, 0.0826), (0.1686, 0.1161)):
            k = (at_2 - at_3) * 6.0
            sizes.append(k / denominator + at_2 - k / 2.0)
        return sizes[0], sizes[1]

    field = drawing.LEVER_FIELD
    reach = 2.0 * drawing.BALLOON_RING_REACH

    def fits(denominator: float) -> bool:
        width, height = outline_size(denominator)
        return width + reach <= field[2] - field[0] and height + reach <= field[3] - field[1]

    assert not fits(2.0)
    assert fits(2.5)
    assert drawing.LEVER_SCALE_LADDER[0] == (1.0, 2.5)
    # Centred in the field, the caption sits under the view, above the title block.
    width, height = outline_size(2.5)
    centre = ((field[0] + field[2]) / 2.0, (field[1] + field[3]) / 2.0)
    outline = (
        centre[0] - width / 2.0,
        centre[1] - height / 2.0,
        centre[0] + width / 2.0,
        centre[1] + height / 2.0,
    )
    text = drawing.exploded_caption(drawing.LEVER_GROUP, (1.0, 2.5))
    left, top = drawing.lever_caption_xy(outline, text)
    assert top < outline[1]
    assert left + len(text) * drawing.CAPTION_CHAR_WIDTH / 2.0 == pytest.approx(centre[0])
    assert left > drawing.INNER_BORDER[0]
    assert left + len(text) * 0.00256 < drawing.INNER_BORDER[2]
    with pytest.raises(ValueError, match="reaches the title block"):
        drawing.lever_caption_xy((0.1, 0.075, 0.2, 0.2), text)


def test_the_setting_axis_picks_land_on_the_bare_cylinders_off_the_chain() -> None:
    # r14 (run 20261016T171305106Z), back view at 1:4: the picks stay 5 mm
    # off the clamp block, the 7/16 hex whose bottom face sits LEVER_BORE_Y
    # under the lever axis and whose corners sit HEX_AC/2 either side of the
    # rod axis along the lever (#1559), and off the fixture's top, 5.5 mm
    # over its axis.
    import mg_magnifying_clamp_geom as clamp

    picks = drawing.setting_axis_picks_m()
    rod_x, rod_y, rod_z = (value * 1000.0 for value in picks["vertical rod"])
    lever_x, lever_y, lever_z = (value * 1000.0 for value in picks["lever"])
    assert rod_z == lever_z == 0.0
    assert 0.0 < rod_x - stack.CLAMP_CENTRE_X < drawing._VROD_R
    assert stack.LEVER_AXIS_Y - rod_y > clamp.LEVER_BORE_Y + 5.0
    assert rod_y - stack.FIXTURE_AXIS_Y > 5.5 + 5.0
    assert 0.0 < lever_y - stack.LEVER_AXIS_Y < drawing._LEVER_R
    assert lever_x - stack.CLAMP_CENTRE_X > clamp.HEX_AC / 2.0 + 5.0
    assert stack.LEVER_TIP_X - lever_x > drawing._LEVER_R + 5.0


class _NativeWheelBalloon:
    """A returned native note with readable item, attachment and rendered circle."""

    def __init__(self, item: str, owner: str):
        self.item = item
        self.owner = owner
        self.annotation = self
        self.entities = (
            SimpleNamespace(GetComponent=lambda: SimpleNamespace(Name2=self.owner)),
        )
        self.kinds = (1,)  # swSelEDGES
        self.circle = (0.100, 0.150, 0.0047)

    def GetBomBalloonText(self, _upper):
        return self.item

    def GetAnnotation(self):
        return self.annotation

    def GetAttachedEntities3(self):
        return self.entities

    def GetAttachedEntityTypes(self):
        return self.kinds

    def GetDisplayData(self):
        return self

    def GetArcCount(self):
        return 1

    def GetArcAtIndex2(self, _index):
        x, y, radius = self.circle
        point = (x + radius, y, 0.0)
        return (0, 0, -1, -1, *point, *point, x, y, 0.0, 0.0, 0.0, 1.0, 1.0)


@pytest.fixture
def native_wheel_balloons(monkeypatch):
    items = drawing.balloon_items(
        {stem: str(index) for index, stem in enumerate(notes.BOM_ORDER, start=1)},
        explode.WHEEL_GROUP_STEMS,
    )
    owners = {stem: f"wheel-sub-1/{stem}-1" for stem, _item in items}
    native = [_NativeWheelBalloon(item, owners[stem]) for stem, item in items]

    def component(stem, path, *, visible=True):
        return SimpleNamespace(
            Name=f"mg-magnifier-1/{path}@Drawing View1",
            GetChildren=lambda: (),
            Visible=visible,
            Component=SimpleNamespace(
                Name2=path, GetPathName=lambda: f"C:/parts/{stem}.SLDPRT"
            ),
        )

    children = [component(stem, owners[stem]) for stem, _item in items] + [
        component("mg-vn-wheel-axle-nut", "wheel-sub-1/mg-vn-wheel-axle-nut-2"),
        component(
            "mg-vn-wheel-axle-nut",
            "wheel-sub-1/mg-vn-wheel-axle-nut-3",
            visible=False,
        ),
    ]
    root = SimpleNamespace(GetChildren=lambda: children)
    view = SimpleNamespace(RootDrawingComponent2=lambda _resolve: root)

    def attempt(callback, default=None):
        try:
            return callback()
        except Exception:
            return default

    model = SimpleNamespace(sheet=drawing.SHEET_NAMES[0], EditRebuild3=lambda: True)

    def activate_sheet(name):
        model.sheet = name
        return True

    model.ActivateSheet = activate_sheet
    model.GetCurrentSheet = lambda: SimpleNamespace(GetName=lambda: model.sheet)
    adapter = SimpleNamespace(_attempt=attempt, currentModel=model)
    # Only the native generation boundary is replaced; view-family resolution,
    # BOM text, EDGE types and full component ownership use production readers.
    monkeypatch.setattr(
        _drawing_balloons, "_create_auto_balloons", lambda *args, **kwargs: native
    )
    return SimpleNamespace(
        notes=native,
        owners=owners,
        create=lambda: drawing.add_auto_balloons(
            adapter, view, items=items, label="magnifier wheel BOM coverage"
        ),
        adapter=adapter,
    )


def test_native_wheel_balloons_cover_rows_and_keep_their_native_attachments(
    native_wheel_balloons,
) -> None:
    fixture = native_wheel_balloons
    nut = next(
        note for note in fixture.notes if note.owner.endswith("mg-vn-wheel-axle-nut-1")
    )
    # Native placement may choose any shown instance, not the old pinned locknut.
    nut.owner = "WHEEL-SUB-1\\MG-VN-WHEEL-AXLE-NUT-2"
    landings = fixture.create()
    assert len(landings) == len(explode.WHEEL_GROUP_STEMS)
    assert {landing.stem for landing in landings} == explode.WHEEL_GROUP_STEMS
    assert all(landing.sheet_xy is None for landing in landings)
    for landing in landings:
        assert landing.instance == landing.note.owner.replace("\\", "/")
    _drawing_balloons.assert_balloon_landings(fixture.adapter, landings)


def test_native_wheel_rejects_swapped_washer_owners_even_with_every_bom_row(
    native_wheel_balloons,
) -> None:
    fixture = native_wheel_balloons
    back = next(note for note in fixture.notes if "back-washer" in note.owner)
    front = next(note for note in fixture.notes if "front-washer" in note.owner)
    back.owner, front.owner = front.owner, back.owner
    assert len({note.item for note in fixture.notes}) == len(explode.WHEEL_GROUP_STEMS)
    with pytest.raises(RuntimeError, match="native EDGE owner.*not a shown instance"):
        fixture.create()


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("duplicate", "duplicate native BOM item"),
        ("missing", "missing native BOM items"),
        ("unexpected", "unexpected native BOM item"),
        ("unresolved", "unresolved item"),
    ],
)
def test_native_wheel_refuses_inexact_bom_coverage(
    native_wheel_balloons, fault, message
) -> None:
    fixture = native_wheel_balloons
    if fault == "duplicate":
        fixture.notes[-1].item = fixture.notes[0].item
    elif fault == "missing":
        fixture.notes.pop()
    elif fault == "unexpected":
        fixture.notes[-1].item = "999"
    else:
        fixture.notes[-1].item = "?"
    with pytest.raises(RuntimeError, match=message):
        fixture.create()


@pytest.mark.parametrize("kind", [0, 2, 3, 999])
def test_native_wheel_refuses_non_edge_and_unknown_native_attachment_types(
    native_wheel_balloons, kind
) -> None:
    fixture = native_wheel_balloons
    fixture.notes[0].kinds = (kind,)
    with pytest.raises(RuntimeError, match="must attach to one native EDGE"):
        fixture.create()


@pytest.mark.parametrize(
    "fault",
    [
        "annotation",
        "entities",
        "types",
        "dangling",
        "extra_entity",
        "unknown_entity",
        "unknown_owner",
    ],
)
def test_native_wheel_refuses_absent_or_unreadable_native_attachments(
    native_wheel_balloons, fault
) -> None:
    fixture = native_wheel_balloons
    note = fixture.notes[0]
    if fault == "annotation":
        note.annotation = None
    elif fault == "entities":
        note.entities = ()
    elif fault == "types":
        note.kinds = ()
    elif fault == "dangling":
        note.entities = (None,)
    elif fault == "extra_entity":
        note.entities *= 2
    elif fault == "unknown_entity":
        note.entities = (object(),)
    else:
        note.owner = ""
    with pytest.raises(RuntimeError, match="native annotation|native EDGE"):
        fixture.create()


@pytest.mark.parametrize(
    "owner",
    [
        "other-sub-1/mg-vn-wheel-axle-nut-1",
        "wheel-sub-1/mg-vn-wheel-axle-nut-3",
    ],
)
def test_native_wheel_rejects_same_family_wrong_full_path_and_hidden_owner(
    native_wheel_balloons, owner
) -> None:
    fixture = native_wheel_balloons
    nut = next(
        note for note in fixture.notes if note.owner.endswith("mg-vn-wheel-axle-nut-1")
    )
    nut.owner = owner
    with pytest.raises(RuntimeError, match="native EDGE owner.*not a shown instance"):
        fixture.create()


def test_native_wheel_attachments_remain_checked_after_the_final_rebuild(
    native_wheel_balloons,
) -> None:
    fixture = native_wheel_balloons
    landings = fixture.create()
    fixture.notes[0].owner = fixture.notes[1].owner
    with pytest.raises(RuntimeError, match="changed after the final rebuild"):
        _drawing_balloons.assert_balloon_landings(fixture.adapter, landings)


def test_native_wheel_circles_fit_without_changing_native_placement(
    native_wheel_balloons,
) -> None:
    fixture = native_wheel_balloons
    landings = fixture.create()
    before = [(note.circle, note.owner) for note in fixture.notes]
    drawing._assert_wheel_balloon_bounds(fixture.adapter, landings)
    assert [(note.circle, note.owner) for note in fixture.notes] == before
    assert fixture.adapter.currentModel.sheet == drawing.SHEET_NAMES[1]
    _drawing_balloons.assert_balloon_landings(fixture.adapter, landings)


@pytest.mark.parametrize("boundary", ["left", "bottom", "right", "top"])
def test_native_wheel_rejects_circle_crossing_field_with_its_centre_inside(
    native_wheel_balloons,
    boundary,
) -> None:
    fixture = native_wheel_balloons
    landings = fixture.create()
    landing = landings[-1]
    radius = 0.0047
    left, bottom, right, top = drawing.WHEEL_FIELD
    mid_x, mid_y = (left + right) / 2.0, (bottom + top) / 2.0
    x, y = {
        "left": (left + radius / 2.0, mid_y),
        "bottom": (mid_x, bottom + radius / 2.0),
        "right": (right - radius / 2.0, mid_y),
        "top": (mid_x, top - radius / 2.0),
    }[boundary]
    landing.note.circle = (x, y, radius)
    assert left < x < right and bottom < y < top
    bounds = (x - radius, y - radius, x + radius, y + radius)
    with pytest.raises(RuntimeError, match="rendered circle") as error:
        drawing._assert_wheel_balloon_bounds(fixture.adapter, landings)
    message = str(error.value)
    assert landing.stem in message
    assert f"item {landing.note.item}" in message
    assert repr(bounds) in message
    assert repr(drawing.WHEEL_FIELD) in message


def test_native_wheel_rejects_circle_in_bom_even_when_inside_the_sheet(
    native_wheel_balloons,
) -> None:
    fixture = native_wheel_balloons
    landings = fixture.create()
    landing = landings[-1]
    x = drawing.WHEEL_FIELD[2] - 0.001
    y = (drawing.BOM_BOTTOM + drawing.BOM_ANCHOR[1]) / 2.0
    radius = drawing.BOM_ANCHOR[0] - x + 0.001
    landing.note.circle = (x, y, radius)
    bounds = (x - radius, y - radius, x + radius, y + radius)
    assert _inside(bounds, drawing.INNER_BORDER)
    assert _overlap(
        bounds,
        (
            drawing.BOM_ANCHOR[0],
            drawing.BOM_BOTTOM,
            drawing.INNER_BORDER[2],
            drawing.BOM_ANCHOR[1],
        ),
    )
    assert drawing.WHEEL_FIELD[0] < x < drawing.WHEEL_FIELD[2]
    with pytest.raises(RuntimeError, match="leaves WHEEL_FIELD"):
        drawing._assert_wheel_balloon_bounds(fixture.adapter, landings)


def test_native_wheel_circle_bounds_are_reread_after_the_final_rebuild(
    native_wheel_balloons,
) -> None:
    fixture = native_wheel_balloons
    landings = fixture.create()
    drawing._assert_wheel_balloon_bounds(fixture.adapter, landings)
    note = landings[-1].note

    def final_rebuild():
        _x, y, radius = note.circle
        note.circle = (drawing.WHEEL_FIELD[2] - radius / 2.0, y, radius)
        return True

    fixture.adapter.currentModel.EditRebuild3 = final_rebuild
    drawing.rebuild_drawing(fixture.adapter, label="finalize_drawing")
    # The native edge owner is still correct: only the rendered circle moved.
    _drawing_balloons.assert_balloon_landings(fixture.adapter, landings)
    with pytest.raises(RuntimeError, match="after the final rebuild"):
        drawing._assert_wheel_balloon_bounds(fixture.adapter, landings)


def test_step_down_takes_the_largest_scale_whose_ring_fits() -> None:
    field = (0.0, 0.0, 0.200, 0.150)
    widths = {(1.0, 2.0): 0.250, (1.0, 3.0): 0.150, (1.0, 4.0): 0.110}

    def outline_at(scale):
        width = widths[scale]
        return (0.0, 0.0, width, width * 0.5)

    scale, outline = drawing.step_down_to_fit(
        outline_at, drawing.EXPLODED_SCALE_LADDER, field, name="t"
    )
    assert scale == (1.0, 3.0)
    with pytest.raises(ValueError, match="no t scale fits"):
        drawing.step_down_to_fit(
            outline_at, drawing.EXPLODED_SCALE_LADDER, (0.0, 0.0, 0.05, 0.05), name="t"
        )


def test_every_bom_family_is_ballooned_exactly_once_across_the_package() -> None:
    items = {stem: str(index) for index, stem in enumerate(notes.BOM_ORDER, start=1)}
    ballooned = [
        stem
        for stems in (
            explode.WHEEL_GROUP_STEMS,
            explode.LEVER_GROUP_STEMS,
            frozenset({explode.WIRE_STEM}),
        )
        for stem, _item in drawing.balloon_items(items, stems)
    ]
    assert sorted(ballooned) == sorted(notes.BOM_ORDER)


def test_the_joint_retention_rows_point_at_magnifier_steps() -> None:
    assert joint_retention.STEP_LISTS["mg_magnifier"] == steps.SEQUENCE
    assert DRAWINGS_BY_NAME["mg_magnifier_assembly"].part == "mg_magnifier"


@pytest.mark.parametrize(
    ("stem", "station", "radius", "rows"),
    [
        (
            "mg-magnifying-lever",
            assembly.LEVER_ROD_DIA / 2.0,
            assembly.LEVER_ROD_DIA / 2.0,
            _transforms.ROT_Y_180,
        ),
        (
            # The shoulder's Ø5 edge (#1559): the old x = R station now falls
            # on the turned-down thread, so a point at radius R is off the rod.
            "mg-magnifying-vertical-rod",
            assembly.VROD_SHOULDER_X,
            assembly.VROD_DIA / 2.0,
            _transforms.compose_rows(
                _transforms.rot_z_rows(-90.0), _transforms.ROT_Y_180
            ),
        ),
    ],
)
def test_rod_balloon_anchors_sit_on_a_drawn_circle_facing_the_isometric(
    stem: str, station: float, radius: float, rows: list[list[float]]
) -> None:
    x, y, z = drawing.BALLOON_ANCHORS[stem].point_mm
    assert x == pytest.approx(station)
    assert math.hypot(y, z) == pytest.approx(radius)
    normal = [
        sum((0.0, y / radius, z / radius)[i] * rows[i][j] for i in range(3))
        for j in range(3)
    ]
    assert sum(normal) > 0.0  # faces the +X+Y+Z viewer
    if stem == "mg-magnifying-lever":
        # Square to the rod axis, and straight at the viewer.
        assert sum(normal) == pytest.approx(math.sqrt(2.0))
    else:
        # Opposite the revolve seam (x, R, 0): a vertex of the drawn circle
        # for any even segment count (r12 missed mid-chord at 1:2).
        assert (y, z) == pytest.approx((-radius, 0.0))

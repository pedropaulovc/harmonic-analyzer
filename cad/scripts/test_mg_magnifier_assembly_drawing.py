"""Offline contract for the magnifier assembly drawing and its stack settings."""

import asyncio
import json
import math
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest

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
from _drawing_common import is_pictorial_orientation
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


@pytest.mark.parametrize(
    "orientation, pictorial",
    [
        (stack.DRAWING_ISOMETRIC_VIEW, True),
        (stack.DRAWING_BACK_VIEW, False),
        (stack.DRAWING_LEFT_VIEW, False),
    ],
)
def test_magnifier_named_views_receive_the_correct_display_rules(
    orientation, pictorial
) -> None:
    assert is_pictorial_orientation(orientation) is pictorial


@pytest.mark.parametrize("detail", [drawing.PRESSED, drawing.ENDSHAKE])
def test_stack_detail_station_increases_right(detail) -> None:
    assert detail.sheet_xy(detail.centre_d + 1.0) == pytest.approx(
        (detail.centre[0] + detail.mm, detail.centre[1])
    )


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


@pytest.mark.parametrize("feature", [stack.FEATURE, stack.LEVER_FEATURE])
def test_an_above_callout_with_a_line_break_is_refused_before_model_writes(
    monkeypatch, feature
) -> None:
    callouts = stack.SETTING_CALLOUTS[feature]
    above = next(name for name, (part, _text) in callouts.items() if part == 3)
    monkeypatch.setitem(callouts, above, (3, "ABOVE\nCALLOUT"))
    monkeypatch.setattr(
        assembly, "_named_dimension", lambda *_args: pytest.fail("no model writes")
    )
    with pytest.raises(RuntimeError, match="line break do not print"):
        assembly._author_setting_callouts(object(), feature)


class _Display:
    def __init__(self, parts: dict[int, str]) -> None:
        self.parts = parts

    def GetText(self, part: int) -> str:
        return self.parts.get(part, "")


@pytest.mark.parametrize("feature", [stack.FEATURE, stack.LEVER_FEATURE])
def test_each_callout_reads_back_from_its_own_compartment(feature) -> None:
    callouts = stack.SETTING_CALLOUTS[feature]
    good = [
        (name, _Display({part: text.replace("\n", "\r\n")}))
        for name, (part, text) in callouts.items()
    ]
    drawing._assert_callouts(good, callouts)
    # Text in the other compartment is not the inherited model callout.
    name, (part, text) = next(iter(callouts.items()))
    wrong = [(name, _Display({7 - part: text})), *good[1:]]
    with pytest.raises(RuntimeError, match="callout reads ''"):
        drawing._assert_callouts(wrong, callouts)


@pytest.mark.parametrize("feature", [stack.FEATURE, stack.LEVER_FEATURE])
@pytest.mark.parametrize("failed_readback", [False, True])
def test_native_setting_text_requires_void_setter_readback(
    monkeypatch, feature, failed_readback
) -> None:
    class Display:
        def __init__(self):
            self.text = {}

        def SetText(self, part, text):
            assert part in (3, 4)  # Never replace the live dimension value.
            if not failed_readback:
                self.text[part] = text
            # The native setter returns void, including when text is unchanged.

        def GetText(self, part):
            return self.text.get(part, "").replace("\n", "\r\n")

    displays = {name: Display() for name in stack.SETTING_CALLOUTS[feature]}
    monkeypatch.setattr(
        assembly,
        "_named_dimension",
        lambda _adapter, _owner, name: (displays[name], object()),
    )
    if failed_readback:
        with pytest.raises(RuntimeError, match="native setting callout reads"):
            assembly._author_setting_callouts(object(), feature)
    else:
        assembly._author_setting_callouts(object(), feature)


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
        "_author_setting_callouts",
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
    for outline, name in (
        (front, stack.DRAWING_BACK_VIEW), (right, stack.DRAWING_LEFT_VIEW)
    ):
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
    assert stack.LEVER_DRAWING_DIMENSIONS == {
        stack.LEVER_FEATURE: {stack.CLAMP_STATION_DIMENSION, stack.FIXTURE_DROP_DIMENSION}
    }


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
        "_author_setting_callouts",
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
    checks_bottom = drawing.CHECKS_XY[1] - len(
        drawing.ASSEMBLY_CHECKS.splitlines()
    ) * drawing.NOTE_LINE_PITCH
    assert drawing.STEPS_XY[0] > drawing.INNER_BORDER[0]
    assert drawing.STEPS_XY[1] < drawing.INNER_BORDER[3]
    assert checks_bottom > drawing.INNER_BORDER[1] + drawing._PAD
    # Combined 0fb89 native note extents, relative to their insertion points.
    # The estimated line pitch must not push CHECK back into the title block.
    sequence_bottom = drawing.STEPS_XY[1] - (0.258 - 0.0953983)
    checks_top = drawing.CHECKS_XY[1] + (0.0846455 - 0.0844)
    checks_native_bottom = drawing.CHECKS_XY[1] - (0.0844 - 0.0618495)
    sequence_top = drawing.STEPS_XY[1] + (0.2584113 - 0.258)
    assert sequence_bottom - checks_top >= drawing._PAD
    assert sequence_top <= drawing.INNER_BORDER[3] - drawing._PAD
    # Matched PDF ink sets the actual separation limit, not nominal font size.
    sequence_ink_bottom = drawing.STEPS_XY[1] - (0.258 - 0.0960089)
    checks_ink_top = drawing.CHECKS_XY[1] + (0.0843736 - 0.0844)
    assert sequence_ink_bottom - checks_ink_top >= min(0.0038733, 0.0038734)
    assert checks_native_bottom >= drawing.TITLE_BLOCK[3] + drawing._PAD
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


def test_the_axle_nut_balloons_land_square_to_the_axle_on_distinct_parts() -> None:
    import math

    import mg_vn_wheel_axle_front_washer_spec as washer
    import mg_vn_wheel_axle_nut_spec as nut

    def screen(point):
        # Ry(180) placement, then the preserved fitter (+X+Y+Z) projection.
        x, y, z = -point[0], point[1], -point[2]
        return ((x - z) / math.sqrt(2.0), (-x + 2.0 * y - z) / math.sqrt(6.0))

    wx, wy, wz = drawing.FRONT_WASHER_BALLOON_POINT_MM
    assert wz == 0.0 and math.hypot(wx, wy) == pytest.approx(washer.OD / 2.0)
    nx, ny, nz = drawing.LOCKNUT_BALLOON_POINT_MM
    # On the flat facing 240 deg (corners on the local +-Y meridian).
    normal = math.radians(240.0)
    assert nz == 0.0
    assert nx * math.cos(normal) + ny * math.sin(normal) == pytest.approx(
        nut.ACROSS_FLATS / 2.0
    )
    axle = screen((0.0, 0.0, 1.0))  # the stack's explode runs along local +z
    for point, side in (
        (drawing.FRONT_WASHER_BALLOON_POINT_MM, (-0.5, math.sqrt(3.0) / 2.0)),
        (drawing.LOCKNUT_BALLOON_POINT_MM, (0.5, -math.sqrt(3.0) / 2.0)),
    ):
        sx, sy = screen(point)
        length = math.hypot(sx, sy)
        assert (sx / length, sy / length) == pytest.approx(side)
        assert sx * axle[0] + sy * axle[1] == pytest.approx(0.0, abs=1e-9)
    anchors = drawing.BALLOON_ANCHORS
    assert anchors["mg-vn-wheel-axle-nut"].instance == "mg-vn-wheel-axle-nut-2"
    # Instance 2 is the locknut, exploded farthest out.
    farthest = min(
        (step for step in explode.EXPLODE_STEPS if step.axis == "z"),
        key=lambda step: step.distance_mm,
    )
    assert farthest.members == ("mg-vn-wheel-axle-nut:2",)


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


def _metadata_instances():
    return [
        explode.Instance(f"{stem}-{number}", stem)
        for stem in notes.BOM_ORDER
        for number in range(1, notes.QUANTITIES[stem] + 1)
    ]


def _metadata_offsets():
    """Aggregate the actual component plan, retaining stationary instances."""
    instances = _metadata_instances()
    offsets = {item.name.casefold(): [0.0, 0.0, 0.0] for item in instances}
    for step, names in explode.plan_explode(instances):
        for name in names:
            offsets[name.casefold()]["xyz".index(step.axis)] += step.distance_mm / 1000.0
    return {name: tuple(vector) for name, vector in offsets.items()}


@pytest.mark.parametrize("configuration", ["Default", "Default Simplified"])
def test_mg_builder_owned_offsets_roundtrip_actual_component_plan(configuration) -> None:
    offsets = _metadata_offsets()
    instances = [
        explode.Instance(item.name.upper(), item.stem) for item in _metadata_instances()
    ]
    encoded = explode.encode_explode_offsets(configuration, offsets, instances)
    payload = json.loads(encoded)
    assert set(payload) == {
        "configuration", "view", "steps", "contract_sha256", "offsets_m"
    }
    assert payload["contract_sha256"] == explode.explode_contract_fingerprint(instances)
    assert len(payload["contract_sha256"]) == 64
    assert all(character in "0123456789abcdef" for character in payload["contract_sha256"])
    decoded = explode.decode_explode_offsets(encoded, configuration, instances)
    assert decoded == offsets
    assert any(vector == (0.0, 0.0, 0.0) for vector in decoded.values())
    # The format preserves native aggregate world translations, not a single
    # nominal axis/step. Multiple native steps may move the same component.
    name = next(iter(offsets))
    cumulative = dict(offsets)
    cumulative[name] = (0.030 + 0.012, -0.025, 0.007)
    assert explode.decode_explode_offsets(
        explode.encode_explode_offsets(configuration, cumulative, instances),
        configuration,
        instances,
    )[name] == pytest.approx((0.042, -0.025, 0.007))
    assert explode.explode_offsets_property(configuration) != (
        explode.explode_offsets_property(
            "Default Simplified" if configuration == "Default" else "Default"
        )
    )


@pytest.mark.parametrize(
    "damage",
    [
        "missing configuration", "wrong configuration", "missing view", "wrong view",
        "missing steps", "wrong steps", "missing contract_sha256", "wrong contract_sha256",
        "missing offsets", "missing instance",
        "extra instance", "short vector", "long vector", "nonnumeric", "boolean",
        "nan", "infinity", "malformed", "empty",
    ],
)
def test_mg_builder_owned_offsets_refuse_invalid_metadata(damage) -> None:
    configuration = "Default Simplified"
    payload = json.loads(
        explode.encode_explode_offsets(
            configuration, _metadata_offsets(), _metadata_instances()
        )
    )
    name = next(iter(payload["offsets_m"]))
    field = damage.removeprefix("missing ")
    if field in {"configuration", "view", "steps", "contract_sha256", "offsets"}:
        payload.pop("offsets_m" if field == "offsets" else field)
    elif damage == "wrong configuration":
        payload["configuration"] = "Default"
    elif damage == "wrong view":
        payload["view"] = "unowned view"
    elif damage == "wrong steps":
        payload["steps"] = len(explode.EXPLODE_STEPS) + 1
    elif damage == "wrong contract_sha256":
        payload["contract_sha256"] = "0" * 64
    elif damage == "missing instance":
        payload["offsets_m"].pop(name)
    elif damage == "extra instance":
        payload["offsets_m"]["unexpected-1"] = [0.0, 0.0, 0.0]
    elif damage in {"short vector", "long vector"}:
        payload["offsets_m"][name] = [0.0] * (2 if damage == "short vector" else 4)
    elif damage in {"nonnumeric", "boolean", "nan", "infinity"}:
        value = {
            "nonnumeric": "0.1", "boolean": True,
            "nan": float("nan"), "infinity": float("inf"),
        }[damage]
        payload["offsets_m"][name] = [value, 0.0, 0.0]
    text = json.dumps(payload)
    if damage == "malformed":
        text = "{"
    elif damage == "empty":
        text = ""
    with pytest.raises(ValueError) as caught:
        explode.decode_explode_offsets(
            text, configuration, _metadata_instances()
        )
    assert "builder-owned explode offsets" in str(caught.value)
    assert "rebuild assembly:mg_magnifier" in str(caught.value)


@pytest.mark.parametrize("mutation", ["distance", "axis", "raw members", "resolved members"])
def test_mg_owned_offsets_refuse_same_count_contract_mutations(monkeypatch, mutation):
    configuration = "Default Simplified"
    instances = _metadata_instances()
    offsets = _metadata_offsets()
    encoded = explode.encode_explode_offsets(configuration, offsets, instances)
    old_plan = explode.plan_explode(instances)
    changed_steps = list(explode.EXPLODE_STEPS)
    if mutation == "distance":
        # A changed spec-derived distance must invalidate the readback even
        # when the native step count and every component identity still match.
        changed_steps[0] = replace(
            changed_steps[0], distance_mm=changed_steps[0].distance_mm - 1.0
        )
    elif mutation == "axis":
        changed_steps[0] = replace(changed_steps[0], axis="x")
    elif mutation == "raw members":
        # :02 resolves to exactly the same nut as :2, isolating raw recipe
        # membership from the separately fingerprinted resolved names.
        changed_steps[0] = replace(
            changed_steps[0], members=("mg-vn-wheel-axle-nut:02",)
        )
    else:
        swapped = {
            "mg-magnifying-wheel": "mg-wheel-drum",
            "mg-wheel-drum": "mg-magnifying-wheel",
        }
        instances = [
            replace(item, stem=swapped.get(item.stem, item.stem)) for item in instances
        ]
    monkeypatch.setattr(explode, "EXPLODE_STEPS", tuple(changed_steps))
    current_plan = explode.plan_explode(instances)
    assert len(current_plan) == len(old_plan) == json.loads(encoded)["steps"]
    assert {item.name.casefold() for item in instances} == set(offsets)
    if mutation == "raw members":
        assert [names for _step, names in current_plan] == [
            names for _step, names in old_plan
        ]
    elif mutation == "resolved members":
        assert [step for step, _names in current_plan] == [
            step for step, _names in old_plan
        ]
        assert [names for _step, names in current_plan] != [
            names for _step, names in old_plan
        ]
    with pytest.raises(ValueError, match="explode contract differs"):
        explode.decode_explode_offsets(encoded, configuration, instances)


def _native_mg_author(monkeypatch, configuration_name, mismatch=None):
    """Native readbacks are fixed independently of the recipe being authored."""
    import _mg_magnifier_explode as author
    from solidworks_mcp.adapters import com_variant

    monkeypatch.setattr(
        explode,
        "EXPLODE_STEPS",
        (
            explode.ExplodeStep("group out", ("slider",), "x", 30.0),
            explode.ExplodeStep("first farther", ("slider:1",), "x", 12.0),
            explode.ExplodeStep("first down", ("slider:1",), "y", -25.0),
            explode.ExplodeStep("first back", ("slider:1",), "z", 7.0),
        ),
    )
    monkeypatch.setattr(explode, "SHOWN_STEMS", frozenset({"slider", "stationary"}))
    # Absolute native positions, not recipe vectors or encoder output. All
    # three baseline translations are nonzero. The small final residuals are
    # deliberately inside the author's existing 1e-7 m verification tolerance.
    native_positions = {
        "slider-1": (
            (0.500, -0.250, 0.125),
            (0.53000002, -0.250, 0.125),
            (0.54200003, -0.250, 0.125),
            (0.54200003, -0.27500002, 0.125),
            (0.54200003, -0.27500002, 0.13200004),
        ),
        "slider-2": (
            (-0.200, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
            (-0.16999999, 0.350, -0.400),
        ),
        "stationary-1": ((0.100, 0.200, 0.300),) * 5,
    }
    requests = (
        (0.030, ("slider-1", "slider-2"), "X", False),
        (0.012, ("slider-1",), "X", False),
        (0.025, ("slider-1",), "Y", True),
        (0.007, ("slider-1",), "Z", False),
    )
    state = SimpleNamespace(
        stage=0, exploded=False, selected=[], axis=None, views=(),
        steps=[SimpleNamespace(Name="automatic seed")], show_calls=[], published=[],
    )

    def transform(name, stage):
        values = [
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            *native_positions[name][stage], 1.0, 0.0, 0.0, 0.0,
        ]
        if stage == 4:
            if mismatch == "translation" and name == "slider-1":
                values[9] += 0.001
            elif mismatch == "stationary follower" and name == "stationary-1":
                values[10] += 0.001
            elif mismatch == "rotation" and name == "slider-1":
                values[0] = 0.0
        return SimpleNamespace(ArrayData=tuple(values))

    def select_component(name, append, data, show_popup):
        assert append is True and data.Mark == 1 and show_popup is False
        state.selected.append(name)
        return True

    components = {
        name: SimpleNamespace(
            Name2=name,
            GetPathName=lambda name=name: f"C:/parts/{name.rsplit('-', 1)[0]}.SLDPRT",
            GetTotalTransform=lambda presentation, name=name: transform(
                name, state.stage if presentation and state.exploded else 0
            ),
            Transform2=transform(name, 0),
            Select4=lambda append, data, popup, name=name: select_component(
                name, append, data, popup
            ),
        )
        for name in native_positions
    }

    def clear_selection(all_selections):
        assert all_selections is True
        state.selected.clear()
        state.axis = None

    def select_axis(name, kind, x, y, z, append, mark, callout, options):
        assert (kind, x, y, z, append, mark, callout, options) == (
            "AXIS", 0.0, 0.0, 0.0, True, 2, None, 0
        )
        state.axis = name
        return True

    def add_step(distance, manipulator, reverse, angle, rotation_axis, *options):
        expected_distance, names, axis, expected_reverse = requests[state.stage]
        assert (distance, tuple(state.selected), state.axis, reverse) == (
            expected_distance, names, axis, expected_reverse
        )
        assert (manipulator, angle, rotation_axis, options) == (
            -1, 0.0, -1, (False, True, False)
        )
        state.stage += 1
        if state.stage == 4 and mismatch == "native members":
            names = ("stationary-1",)
        native = SimpleNamespace(
            Name="unnamed",
            ExplodeDistance=distance + (
                0.001 if state.stage == 4 and mismatch == "native distance" else 0.0
            ),
            GetComponents=lambda: tuple(components[name] for name in names),
        )
        state.steps.append(native)
        return native, 0

    def delete_seed(name):
        assert name == "automatic seed" and state.stage == 0
        state.steps.clear()
        return True

    def show_exploded(show, view_name):
        assert state.views == (view_name,)
        state.exploded = show
        state.show_calls.append(show)
        return True

    configuration = SimpleNamespace(
        Name=configuration_name,
        GetNumberOfExplodeSteps=lambda: len(state.steps),
        GetExplodeStep=lambda index: state.steps[index],
        DeleteExplodeStep=delete_seed,
        AddExplodeStep2=add_step,
    )
    model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=configuration),
        GetExplodedViewCount2=lambda owner: len(state.views),
        GetComponents=lambda top_level: tuple(components.values()),
        GetExplodedViewNames2=lambda owner: state.views,
        GetExplodedViewConfigurationName=lambda view: configuration_name,
        ShowExploded2=show_exploded,
        ClearSelection2=clear_selection,
        SelectionManager=SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(Mark=0)
        ),
        Extension=SimpleNamespace(SelectByID2=select_axis),
        EditRebuild3=lambda: True,
    )
    adapter = SimpleNamespace(currentModel=model)

    def create_named_view(actual_model, actual_assembly, owner, view_name):
        assert actual_model is model and actual_assembly is model
        assert owner == configuration_name
        state.views = (view_name,)

    def publish(actual_adapter, properties, *, model):
        assert actual_adapter is adapter and model is adapter.currentModel
        assert not state.exploded and state.show_calls == [True, False]
        assert state.stage == len(state.steps) == 4
        state.published.append(properties)

    monkeypatch.setattr(author, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(com_variant, "null_callout", lambda: None)
    monkeypatch.setattr(
        author, "_global_directions",
        lambda _adapter, _assembly: {
            "x": author._Direction("X", True, (1.0, 0.0, 0.0)),
            "y": author._Direction("Y", True, (0.0, 1.0, 0.0)),
            "z": author._Direction("Z", True, (0.0, 0.0, 1.0)),
        },
    )
    monkeypatch.setattr(author, "_create_named_view", create_named_view)
    monkeypatch.setattr(author, "apply_custom_properties", publish)
    return author, adapter, state


@pytest.mark.parametrize("configuration", ["Default", "Default Simplified"])
def test_actual_mg_author_publishes_final_measured_offsets(monkeypatch, configuration):
    author, adapter, state = _native_mg_author(monkeypatch, configuration)
    author.create_mg_magnifier_explode(adapter, configuration)
    assert len(state.published) == 1
    properties = state.published[0]
    assert set(properties) == {explode.explode_offsets_property(configuration)}
    payload = json.loads(properties[explode.explode_offsets_property(configuration)])
    assert payload["configuration"] == configuration
    assert payload["view"] == explode.exploded_view_name(configuration)
    assert payload["steps"] == 4
    # Tight absolute tolerance distinguishes native residuals from nominal
    # recipe sums, earlier steps, absolute positions, and post-collapse zeros.
    expected = {
        "slider-1": (0.04200003, -0.02500002, 0.00700004),
        "slider-2": (0.03000001, 0.0, 0.0),
        "stationary-1": (0.0, 0.0, 0.0),
    }
    assert set(payload["offsets_m"]) == set(expected)
    for name, vector in expected.items():
        assert payload["offsets_m"][name] == pytest.approx(vector, abs=1e-14, rel=0)
    instances = [
        explode.Instance(name, name.rsplit("-", 1)[0]) for name in expected
    ]
    decoded = explode.decode_explode_offsets(
        properties[explode.explode_offsets_property(configuration)],
        configuration,
        instances,
    )
    assert decoded["stationary-1"] == (0.0, 0.0, 0.0)
    assert [step.Name for step in state.steps] == [
        f"MG {label}" + (" Simplified" if configuration != "Default" else "")
        for label in ("GROUP OUT", "FIRST FARTHER", "FIRST DOWN", "FIRST BACK")
    ]
    assert state.show_calls == [True, False] and not state.exploded


@pytest.mark.parametrize(
    ("mismatch", "message"),
    [
        ("translation", "slider-1 moved"),
        ("stationary follower", "stationary-1 moved"),
        ("rotation", "presentation rotated or scaled"),
        ("native distance", "step component/distance readback mismatch"),
        ("native members", "step component/distance readback mismatch"),
    ],
)
def test_actual_mg_author_never_publishes_failed_readback(monkeypatch, mismatch, message):
    configuration = "Default Simplified"
    author, adapter, state = _native_mg_author(monkeypatch, configuration, mismatch)
    with pytest.raises(RuntimeError, match=message):
        author.create_mg_magnifier_explode(adapter, configuration)
    assert state.stage == 4
    assert state.show_calls == [True, False] and not state.exploded
    assert state.published == []


class _ExplodeSource:
    """Read-only API contract fake; not evidence of native/byte cleanliness."""

    def __init__(self) -> None:
        self.active = drawing.ASSEMBLY_VIEW_CONFIGURATION
        self.exploded = False
        self.dirty = False
        self.configuration_switches = []
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=self.active)
        )
        self.properties = {
            explode.explode_offsets_property(owner): explode.encode_explode_offsets(
                owner, _metadata_offsets(), _metadata_instances()
            )
            for owner in drawing.EXPLODED_VIEW_NAMES
        }
        transform = SimpleNamespace(
            ArrayData=(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
        )
        self.components = [
            SimpleNamespace(
                Name2=item.name,
                GetPathName=lambda stem=item.stem: f"C:/parts/{stem}.SLDPRT",
                GetTotalTransform=lambda _presentation: transform,
            )
            for item in _metadata_instances()
        ]
        self.Extension = SimpleNamespace(CustomPropertyManager=self._forbidden)

    def _forbidden(self, *_args, **_kwargs):
        pytest.fail("drawing must not mutate or reset its released source")

    ShowConfiguration2 = _forbidden
    ShowExploded2 = _forbidden
    SetSaveFlag = _forbidden
    ResetSaveFlag = _forbidden
    Save3 = _forbidden
    SaveAs3 = _forbidden
    AddCustomInfo3 = _forbidden
    SetCustomInfo2 = _forbidden
    DeleteCustomInfo2 = _forbidden

    def GetSaveFlag(self):
        return self.dirty

    def GetComponents(self, top_level):
        assert top_level is True
        return self.components

    def GetExplodedViewNames2(self, configuration):
        return (explode.exploded_view_name(configuration),)

    def GetCustomInfoValue(self, configuration, name):
        assert configuration == ""
        return self.properties.get(name, "")


def test_mg_validate_source_reads_both_metadata_maps_without_activation(monkeypatch):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _ExplodeSource()
    offsets = drawing._validate_source(source)
    assert offsets == {
        configuration: _metadata_offsets()
        for configuration in drawing.EXPLODED_VIEW_NAMES
    }
    assert source.active == "Default"
    assert not source.exploded
    assert not source.dirty


@pytest.mark.parametrize("configuration", ["Default", "Default Simplified"])
def test_mg_validate_source_refuses_missing_metadata(monkeypatch, configuration):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _ExplodeSource()
    source.properties.pop(explode.explode_offsets_property(configuration))
    with pytest.raises((ValueError, RuntimeError), match="builder-owned explode offsets"):
        drawing._validate_source(source)

@pytest.mark.parametrize("failure", ["active configuration", "displaced", "families"])
def test_mg_metadata_does_not_replace_current_source_safety(monkeypatch, failure):
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _ExplodeSource()
    if failure == "active configuration":
        source.ConfigurationManager.ActiveConfiguration.Name = "Default Simplified"
    elif failure == "families":
        source.components.pop()
    else:
        base = source.components[0].GetTotalTransform(False).ArrayData
        displaced = list(base)
        displaced[9] = 0.001
        source.components[0].GetTotalTransform = lambda presentation: SimpleNamespace(
            ArrayData=displaced if presentation else base
        )
    with pytest.raises(RuntimeError):
        drawing._validate_source(source)



@pytest.mark.parametrize("configuration", ["Default", "Default Simplified"])
def test_mg_exploded_view_uses_only_its_config_metadata(configuration):
    metadata = {
        "Default": {"part-1": (0.01, 0.02, 0.03)},
        "Default Simplified": {"part-1": (-0.04, 0.05, 0.06)},
    }
    view = SimpleNamespace(
        ReferencedConfiguration=configuration, IsExploded=lambda: True
    )
    assert drawing._view_source_explode_offsets(
        view, metadata, label="wheel"
    ) == metadata[configuration]


def test_mg_collapsed_view_needs_no_source_or_configuration():
    view = SimpleNamespace(IsExploded=lambda: False)
    assert drawing._view_source_explode_offsets(view, {}, label="finished") == {}


@pytest.mark.parametrize("configuration", ["unknown", "", None])
def test_mg_exploded_view_refuses_unknown_or_missing_configuration(configuration):
    view = SimpleNamespace(
        ReferencedConfiguration=configuration, IsExploded=lambda: True
    )
    with pytest.raises(RuntimeError):
        drawing._view_source_explode_offsets(view, {}, label="wheel")

def test_mg_source_sha256_streams_known_bytes(tmp_path):
    path = tmp_path / "source.SLDASM"
    path.write_bytes(b"abc")
    assert drawing._source_sha256(path) == (
        "ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )
    # Cross two 1 MiB block boundaries; a small fixture alone would not catch
    # hashing only the first chunk.
    path.write_bytes(b"\0" * (2 * 1024 * 1024 + 3))
    import hashlib

    assert drawing._source_sha256(path) == hashlib.sha256(
        b"\0" * (2 * 1024 * 1024 + 3)
    ).hexdigest()


@pytest.mark.parametrize("failure", [None, "bytes", "dirty"])
def test_mg_source_identity_requires_same_bytes_and_clean_flag(
    monkeypatch, tmp_path, failure
):
    path = tmp_path / "source.SLDASM"
    path.write_bytes(b"released assembly")
    monkeypatch.setattr(drawing, "SOURCE", path)
    source = _ExplodeSource()
    expected = drawing._source_sha256(path)
    if failure == "bytes":
        path.write_bytes(b"changed assembly")
        assert not source.GetSaveFlag()
    elif failure == "dirty":
        source.dirty = True
        assert drawing._source_sha256(path) == expected
    if failure is None:
        drawing._assert_source_identity(source, expected, phase="offline contract")
    else:
        with pytest.raises(RuntimeError):
            drawing._assert_source_identity(source, expected, phase="offline contract")
    assert path.read_bytes() == (
        b"changed assembly" if failure == "bytes" else b"released assembly"
    )
    assert source.dirty == (failure == "dirty")



def test_mg_source_dirty_trace_names_out_of_scope_transition_without_edits(
    monkeypatch,
) -> None:
    events = []
    warnings = []
    monkeypatch.setattr(
        drawing._telemetry,
        "event",
        lambda name, **fields: events.append((name, fields)),
    )
    monkeypatch.setattr(drawing._telemetry, "warn", warnings.append)
    source = _ExplodeSource()
    step = drawing._source_dirty_tracer(source)
    step("prepared views")
    source.dirty = True  # Outside the immutable metadata read.
    step("BOM insertion")
    step("wheel balloons")
    assert events == [
        ("magnifier.source_save_flag", {"step": "prepared views", "dirty": False}),
        ("magnifier.source_save_flag", {"step": "BOM insertion", "dirty": True}),
        ("magnifier.source_save_flag", {"step": "wheel balloons", "dirty": True}),
    ]
    assert warnings == ["magnifier source went DIRTY after BOM insertion"]
    assert source.dirty
    assert source.configuration_switches == []
    assert source.active == drawing.ASSEMBLY_VIEW_CONFIGURATION
    assert not source.exploded


@pytest.mark.parametrize("group", ["lever", "stack"])
@pytest.mark.parametrize("missing", [False, True])
def test_mg_settings_only_read_inherited_native_callouts(
    monkeypatch, group, missing
) -> None:
    import _drawing_dimensions as dimension_helpers

    feature = stack.LEVER_FEATURE if group == "lever" else stack.FEATURE
    callouts = stack.SETTING_CALLOUTS[feature]
    precision = (
        stack.LEVER_DRAWING_PRECISION if group == "lever" else stack.DRAWING_PRECISION
    )[feature]
    annotations = {}
    text_parts = {}

    def forbidden(*_args):
        pytest.fail("drawing settings must not write native callout text")

    for name, (part, text) in callouts.items():
        text_parts[name] = {part: text.replace("\n", "\r\n")}
        band_m = stack.DIMENSION_TOLERANCES.get(name, 0.0) / 1000.0
        tolerance = SimpleNamespace(
            Type=4,
            GetMaxValue=lambda band=band_m: band,
            GetMinValue=lambda band=band_m: -band,
        )
        display = SimpleNamespace(
            SetText=forbidden,
            GetText=lambda part, name=name: text_parts[name].get(part, ""),
            GetPrimaryPrecision2=lambda name=name: precision[name],
            GetPrimaryTolPrecision2=lambda: stack.TOLERANCE_PRECISION,
            GetDimension2=lambda _index, tol=tolerance: SimpleNamespace(Tolerance=tol),
        )
        annotations[name] = SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display: display
        )
    name, (part, _text) = next(iter(callouts.items()))
    if missing:
        text_parts[name][part] = ""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _iface: value)
    monkeypatch.setattr(
        dimension_helpers._sw_type_info,
        "early_bound_or_flag",
        lambda value, *_args: value,
    )
    for module in (drawing, dimension_helpers):
        monkeypatch.setattr(module, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(drawing, "_show_base_view_sketches", lambda *_a, **_k: None)
    monkeypatch.setattr(
        drawing,
        "curate_view_dimensions",
        lambda *_a, **_k: list(annotations.values()),
    )
    monkeypatch.setattr(
        drawing,
        "model_points_in_view",
        lambda *_a, **_k: ((0.0, 0.0),) * 3,
    )
    monkeypatch.setattr(drawing, "_add_setting_axes", lambda *_a: None)
    monkeypatch.setattr(
        drawing,
        "_dimensioned_detail",
        lambda _adapter, _detail, keep: [annotations[name] for name in keep],
    )
    adapter = SimpleNamespace(_attempt=lambda action: action())

    def import_settings():
        if group == "lever":
            return drawing._lever_settings(adapter, object(), lambda _phase: None)
        return drawing._stack_dimensions(adapter, lambda _phase: None)

    if missing:
        with pytest.raises(RuntimeError, match="callout reads ''"):
            import_settings()
        return
    settled = import_settings()
    settled()
    text_parts[name][part] = ""
    with pytest.raises(RuntimeError, match="callout reads ''"):
        settled()

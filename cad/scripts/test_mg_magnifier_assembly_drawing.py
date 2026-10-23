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


@pytest.mark.parametrize("feature", [stack.FEATURE, stack.LEVER_FEATURE, stack.THREAD_FEATURE])
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


@pytest.mark.parametrize("feature", [stack.FEATURE, stack.LEVER_FEATURE, stack.THREAD_FEATURE])
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

    import sh_vn_music_wire_lever_geom as wire

    x, station, z = drawing.WIRE_BALLOON_POINT_MM
    # On the build's split ring, mid-run, on the wire's surface.
    assert station == pytest.approx(
        drawing.sh_vn_music_wire_lever_spec.BALLOON_RING_FRACTION * wire.WIRE_LEN
    )
    assert station == pytest.approx(wire.WIRE_LEN / 2.0)
    assert math.hypot(x, z) == pytest.approx(wire.WIRE_DIA / 2.0)
    assert drawing.BALLOON_ANCHORS[drawing.WIRE_ROW].point_mm == drawing.WIRE_BALLOON_POINT_MM
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


@pytest.fixture
def projection_native(monkeypatch):
    """Synthetic native readbacks, not a claim about the repaired farm render.

    The primary value is inside the sheet while the full qualifier crosses
    its left border. Exercise the real extent/move/region helpers on one
    imported annotation, retaining its source and attachment identities.
    """
    import _drawing_annotation_extent as extent

    name = stack.THREAD_PROJECTION_DIMENSION
    events = []
    source = SimpleNamespace(
        FullName=f"{name}@{stack.THREAD_FEATURE}@mg-magnifier",
        SystemValue=stack.THREAD_PROJECTION / 1000.0,
        Tolerance=SimpleNamespace(Type=0),
    )
    endpoints = (object(), object())
    owner = object()
    rows = [
        {"text": "1.25", "position": (-0.002, 0.0, 0.0), "reference": 0,
         "height": 0.002, "angle": 0.0, "spacing": 1.0},
        *[
            {"text": line, "position": (0.0, -0.003 * (index + 1), 0.0),
             "reference": 5, "height": 0.002, "angle": 0.0, "spacing": 1.0}
            for index, line in enumerate(stack.SETTING_CALLOUTS[stack.THREAD_FEATURE][name][1].splitlines())
        ],
    ]

    class Data:
        def GetTextCount(self):
            return len(rows)

        def GetTextAtIndex(self, index):
            return rows[index]["text"]

        def GetTextPositionAtIndex(self, index):
            return tuple(a + b for a, b in zip(annotation.position, rows[index]["position"]))

        def GetTextHeightAtIndex(self, index):
            return rows[index]["height"]

        def GetTextRefPositionAtIndex(self, index):
            return rows[index]["reference"]

        def GetTextAngleAtIndex(self, index):
            return rows[index]["angle"]

        def GetTextLineSpacingAtIndex(self, index):
            return rows[index]["spacing"]

        def GetLineCount(self):
            return 1

        def GetLineAtIndex2(self, _index):
            x, y, z = annotation.position
            return (0, 0, 0, 0, x - 0.009, y - 0.012, z, x + 0.009, y - 0.012, z)

    class Display(_Display):
        def SetText(self, *_args):
            pytest.fail("drawing must inherit model-owned text without writing the source")

        def GetDisplayData(self):
            return data

        def GetDimension2(self, index):
            assert index == 0
            return source

    class Annotation:
        position = (0.017, 0.190, 0.0)
        move_result = True
        ignore_move = False

        def GetSpecificAnnotation(self):
            return display

        def GetType(self):
            return extent._ANNOT_DIM

        def GetPosition(self):
            return self.position

        def SetPosition2(self, x, y, z):
            events.append(("move", x, y, z))
            if not self.ignore_move:
                self.position = (x, y, z)
            return self.move_result

    annotation = Annotation()
    annotation.source = source
    annotation.endpoints = endpoints
    annotation.owner = owner
    part, qualifier = stack.SETTING_CALLOUTS[stack.THREAD_FEATURE][name]
    display = Display({part: qualifier})
    data = Data()
    margins = {0: 0.0127, 1: 0.0127, 2: 0.0127, 3: 0.0127}
    sheet = SimpleNamespace(
        GetProperties2=lambda: (0, 0, 1, 4, 0, _TEMPLATE.width_m, _TEMPLATE.height_m, 0),
        GetZoneMargin=lambda side: margins[side],
    )
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(GetCurrentSheet=lambda: sheet),
        _attempt=lambda call: call(),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(extent, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(extent._sw_type_info, "early_bound_or_flag", lambda obj, *_a: obj)

    def rebuild(_adapter, *, label):
        events.append(("rebuild", label))

    monkeypatch.setattr(drawing, "rebuild_drawing", rebuild)
    monkeypatch.setattr(extent, "rebuild_drawing", rebuild)
    return SimpleNamespace(
        adapter=adapter, annotation=annotation, display=display, data=data,
        rows=rows, margins=margins, source=source, endpoints=endpoints,
        owner=owner, events=events,
    )


def test_thread_projection_wrap_preserves_every_word_and_below_compartment(
    projection_native,
) -> None:
    native = projection_native
    name = stack.THREAD_PROJECTION_DIMENSION
    callouts = stack.SETTING_CALLOUTS[stack.THREAD_FEATURE]
    part, qualifier = callouts[name]
    assert part == 4
    drawing._assert_callouts([(name, native.display)], callouts)
    wrapped = drawing._thread_projection_text_box(native.adapter, native.annotation)
    native.rows[1]["text"] = " ".join(qualifier.split())
    del native.rows[2:]
    unwrapped = drawing._thread_projection_text_box(native.adapter, native.annotation)
    assert unwrapped[2] - unwrapped[0] > wrapped[2] - wrapped[0]


@pytest.mark.parametrize("left_margin", [0.0127, 0.024])
def test_thread_projection_fits_whole_qualifier_to_live_border_once(
    projection_native, left_margin,
) -> None:
    native = projection_native
    native.margins[3] = left_margin
    before = drawing._thread_projection_text_box(native.adapter, native.annotation)
    assert native.data.GetTextPositionAtIndex(0)[0] > 0.0127
    assert before[0] < left_margin
    original_y = native.annotation.position[1]
    drawing._fit_thread_projection(native.adapter, native.annotation)
    after = drawing._thread_projection_text_box(native.adapter, native.annotation)
    assert after[0] == pytest.approx(left_margin + drawing.CLEAR_GAP_M)
    assert after[1:] == pytest.approx(
        (before[1], before[2] + after[0] - before[0], before[3])
    )
    assert native.annotation.position[1] == original_y
    assert [event[0] for event in native.events] == ["rebuild", "move", "rebuild"]
    assert native.annotation.source is native.source
    assert native.annotation.endpoints is native.endpoints
    assert native.annotation.owner is native.owner
    assert native.display.GetDimension2(0) is native.source
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert native.source.Tolerance.Type == 0  # existing general .XX band, not rewritten
    # A dimension already comfortably inside its lane must not be moved.
    x, y, z = native.annotation.position
    native.annotation.position = (x + drawing.CLEAR_GAP_M, y, z)
    native.events.clear()
    drawing._fit_thread_projection(native.adapter, native.annotation)
    assert [event[0] for event in native.events] == ["rebuild"]


@pytest.mark.parametrize("failure", ["refused", "ignored"])
def test_thread_projection_refuses_failed_native_move_without_retry(
    projection_native, failure,
) -> None:
    native = projection_native
    native.annotation.move_result = failure != "refused"
    native.annotation.ignore_move = failure == "ignored"
    with pytest.raises(RuntimeError, match="failed to move|crosses the zone frame"):
        drawing._fit_thread_projection(native.adapter, native.annotation)
    assert sum(event[0] == "move" for event in native.events) == 1


@pytest.mark.parametrize("missing", ["all", "qualifier", "last-word"])
def test_thread_projection_rejects_stored_but_unrendered_qualifier(
    projection_native, missing,
) -> None:
    native = projection_native
    if missing == "all":
        native.rows.clear()
    elif missing == "qualifier":
        del native.rows[1:]
    else:
        native.rows[-1]["text"] = "BRACKET"
    # Stored below-text alone is insufficient evidence of printed ink.
    drawing._assert_callouts(
        [(stack.THREAD_PROJECTION_DIMENSION, native.display)],
        stack.SETTING_CALLOUTS[stack.THREAD_FEATURE],
    )
    with pytest.raises(RuntimeError, match="invalid native text count|missing rendered qualifier"):
        drawing._thread_projection_text_box(native.adapter, native.annotation)


@pytest.mark.parametrize(
    ("field", "bad"),
    [("position", (float("nan"), 0.0, 0.0)), ("position", (0.0, 0.0)),
     ("height", 0.0), ("height", float("inf")), ("reference", 6),
     ("angle", float("nan")), ("text", None)],
)
def test_thread_projection_refuses_malformed_native_qualifier_geometry(
    projection_native, field, bad,
) -> None:
    native = projection_native
    native.rows[1][field] = bad
    with pytest.raises(RuntimeError, match="invalid native text"):
        drawing._thread_projection_text_box(native.adapter, native.annotation)


def test_thread_projection_checks_multiline_fragment_height(projection_native) -> None:
    native = projection_native
    native.rows[1]["text"] = stack.SETTING_CALLOUTS[stack.THREAD_FEATURE][stack.THREAD_PROJECTION_DIMENSION][1]
    native.rows[1]["spacing"] = 2.0
    del native.rows[2:]
    # Put the block's anchor well below the native shoulder: its full bottom
    # must participate, not merely its first line's insertion point.
    native.rows[1]["position"] = (0.0, -0.020, 0.0)
    box = drawing._thread_projection_text_box(native.adapter, native.annotation)
    assert box[1] == pytest.approx(0.190 - 0.020 - 0.002 * 5)
    native.rows[1]["spacing"] = 0.0
    with pytest.raises(RuntimeError, match="invalid native text geometry"):
        drawing._thread_projection_text_box(native.adapter, native.annotation)


def test_base_lever_import_excludes_projection_and_preserves_other_settings(monkeypatch) -> None:
    annotations = {
        key: SimpleNamespace(GetSpecificAnnotation=lambda d=_Display({part: text}): d)
        for key, (part, text) in stack.SETTING_CALLOUTS[stack.LEVER_FEATURE].items()
    }
    by_id = {id(annotation): key for key, annotation in annotations.items()}
    imports, precision, shown = [], [], []
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "model_points_in_view", lambda *_a, **_k: (
        (0.04, 0.21), (0.06, 0.21), (0.06, 0.19),
    ))
    monkeypatch.setattr(drawing, "_add_setting_axes", lambda *_a: None)
    monkeypatch.setattr(
        drawing, "_show_base_view_sketches",
        lambda _a, _v, features, **_k: shown.append(features),
    )
    monkeypatch.setattr(drawing, "dimension_name", lambda _a, annotation: by_id[id(annotation)])
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_a: None)

    def curate(_adapter, view, **kwargs):
        imports.append((view, kwargs))
        return list(annotations.values())

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "assert_imported_precision", lambda *args: precision.append(args))
    view = object()
    source_steps = []
    settled = drawing._lever_settings(object(), view, source_steps.append)
    assert imports == [(view, {
        "keep": drawing.lever_keep((0.04, 0.21), (0.06, 0.21), (0.06, 0.19)),
        "view_label": drawing.LEVER_VIEW_LABEL,
        "dimensions_by_feature": stack.LEVER_DRAWING_DIMENSIONS,
    })]
    assert shown == [(stack.LEVER_FEATURE,)]
    assert stack.THREAD_PROJECTION_DIMENSION not in imports[0][1]["keep"]
    assert precision[0][2] == stack.LEVER_DRAWING_PRECISION[stack.LEVER_FEATURE]
    settled()
    assert source_steps == [
        "lever settings import and readback", "lever settings settled readback",
    ]
    annotations[stack.FIXTURE_DROP_DIMENSION].GetSpecificAnnotation().parts[4] = ""
    with pytest.raises(RuntimeError, match="below callout"):
        settled()


def _native_crop_fence(centre=(0.100, 0.053), radius=0.020):
    x, y = centre
    return [1, -1, x, y, 0, x + radius, y, 0, x + radius, y, 0, 3, 0, 0, 0, 0.0035, 0]


@pytest.fixture
def lever_tip_native(monkeypatch, projection_native):
    """Execute the real detail construction and guards with native boundary doubles."""
    import _drawing_dimensions as dimensions

    native = projection_native
    native.source_steps = []
    native.source_step = native.source_steps.append

    native.annotations = []
    native.imports = []
    native.shown = []
    native.precision = 2
    native.cropped = False
    native.drop_on_crop = False
    native.arrow_x = None
    native.line_x = None
    native.fence = _native_crop_fence()
    # Retained R24 padding is deliberately independent of the corrected fence.
    native.outline = [0.0649122, 0.020412, 0.130088, 0.085588]
    native.projected = []
    native.caption_extent = [0.0836475, 0.0151, 0.0, 0.132, 0.0293289, 0.0]
    native.view = SimpleNamespace(
        name="lever tip detail", GetAnnotations=lambda: native.annotations,
        ScaleRatio=(4, 1), IsCropped=lambda: native.cropped,
        UpdateViewDisplayGeometry=lambda: None,
        GetOutline=lambda: native.outline,
        GetDetailCircleInfo2=lambda: native.fence,
        GetOrientationName=lambda: drawing.LEVER_TIP.orientation,
        ReferencedConfiguration="Default",
        GetDisplayMode2=lambda: 2,
        GetFacettedHlrDisplay=lambda: False,
        Position=(0.100, 0.053),
        ModelToViewTransform=SimpleNamespace(ArrayData=tuple(float(i) for i in range(16))),
    )
    native.base = SimpleNamespace(name="base", GetAnnotations=lambda: [])
    native.sheet_view = SimpleNamespace(name="sheet", GetAnnotations=lambda: [])
    native.sheets = [[native.sheet_view, native.base, native.view]]
    native.adapter.currentModel.GetViews = lambda: native.sheets

    native.adapter.swApp = SimpleNamespace(IsSame=lambda a, b: int(a is b))
    native.drawing_components = []
    for stem in sorted(drawing.LEVER_TIP.stems):
        full = SimpleNamespace(
            Name2=f"{stem}-1", GetPathName=lambda stem=stem: f"C:/parts/{stem}.SLDPRT",
            ReferencedConfiguration="Default",
            source=SimpleNamespace(ConfigurationManager=SimpleNamespace(
                ActiveConfiguration=SimpleNamespace(Name="Default"),
            )),
        )
        full.GetModelDoc2 = lambda full=full: full.source
        native.drawing_components.append(SimpleNamespace(Component=full, Visible=True))
    native.view.GetVisibleDrawingComponents = lambda: native.drawing_components
    native.annotation.Owner = native.view
    native.annotation.OwnerType = 0
    native.annotation.GetAttachedEntities3 = lambda: native.annotation.endpoints
    native.annotation.GetAttachedEntityTypes = lambda: (11, 11)
    native.annotation.IsDangling = lambda: False
    native.display.GetPrimaryPrecision2 = lambda: native.precision
    native.caption = SimpleNamespace(
        GetText=lambda: drawing.LEVER_TIP.label_text,
        GetExtent=lambda: native.caption_extent,
    )
    native.neighbour = SimpleNamespace(GetOutline=lambda: (0.035, 0.085, 0.105, 0.215))
    native.back_extent = [0.0486244, 0.0767929, 0.0, 0.0972344, 0.0815586, 0.0]

    def move_back(x, y, z):
        dx, dy = x - native.back_extent[0], y - native.back_extent[4]
        native.events.append(("caption-move", dx, dy, z))
        for index in (0, 3):
            native.back_extent[index] += dx
        for index in (1, 4):
            native.back_extent[index] += dy
        return True

    native.back_annotation = SimpleNamespace(
        GetPosition=lambda: (native.back_extent[0], native.back_extent[4], 0.0),
        SetPosition2=move_back,
    )
    native.back_caption = SimpleNamespace(
        GetText=lambda: drawing.ASSEMBLED_VIEW_CAPTIONS[stack.DRAWING_BACK_VIEW],
        GetExtent=lambda: native.back_extent,
        GetAnnotation=lambda: native.back_annotation,
    )
    monkeypatch.setattr(drawing, "view_name", lambda _a, view: view.name)
    name = stack.THREAD_PROJECTION_DIMENSION
    def identify(_a, ann):
        return name if ann is native.annotation else ""

    monkeypatch.setattr(drawing, "dimension_name", identify)
    monkeypatch.setattr(dimensions, "dimension_name", identify)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_a: None)
    monkeypatch.setattr(drawing, "_activate", lambda *_a, **_k: native.events.append(("activate",)))
    monkeypatch.setattr(drawing, "_placed_detail", lambda _a, detail: native.view)
    monkeypatch.setattr(
        drawing, "_show_base_view_sketches",
        lambda _a, _v, features, **_k: native.shown.append(features),
    )

    def projected(_adapter, view, points, **_kwargs):
        assert view is native.view
        native.projected.append(tuple(points))
        cx, cy = drawing.LEVER_TIP.centre
        mx = (stack.THREADED_TIP_X + stack.THREAD_FAR_FACE_X) / 2000
        my = stack.LEVER_AXIS_Y / 1000
        # Current remapped Front reverses X and retains Y. This places the
        # source dimension; it is not offline evidence of solid visibility.
        return tuple((cx - 4 * (x - mx), cy + 4 * (y - my)) for x, y, _z in points)

    monkeypatch.setattr(drawing, "model_points_in_view", projected)

    def curate(_adapter, view, **kwargs):
        assert not native.cropped
        native.imports.append((view, kwargs))
        native.annotation.position = (*kwargs["keep"][name], 0.0)
        native.annotations.append(native.annotation)
        return [native.annotation]

    def crop(_adapter, view, detail):
        assert view is native.view and detail is drawing.LEVER_TIP
        assert native.annotations == [native.annotation]
        native.events.append(("crop",))
        native.cropped = True
        if native.drop_on_crop:
            native.annotations.clear()

    def label(_adapter, text, x, y):
        assert text == drawing.LEVER_TIP.label_text
        assert (x, y) == drawing.LEVER_TIP.label_xy
        native.events.append(("caption", text))
        return native.caption

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop", crop)
    monkeypatch.setattr(drawing, "add_note", label)
    native.data.GetLineCount = lambda: 3

    def line(index):
        x, y, _ = native.annotation.position
        tip, face = projected(native.adapter, native.view, (
            (stack.THREADED_TIP_X / 1000, stack.LEVER_AXIS_Y / 1000, 0.0),
            (stack.THREAD_FAR_FACE_X / 1000, stack.LEVER_AXIS_Y / 1000, 0.0),
        ))
        segments = [
            (x - 0.010, y - 0.012, face[0], y - 0.012),
            (tip[0], tip[1], tip[0], y - 0.014),
            (face[0], face[1], face[0], y - 0.014),
        ]
        x0, y0, x1, y1 = segments[index]
        if native.line_x is not None and index == 1:
            x0 = native.line_x
        return (0, 0, 0, 0, x0, y0, 0, x1, y1, 0)

    native.data.GetLineAtIndex2 = line
    native.data.GetArrowHeadCount = lambda: 2
    native.data.GetArrowHeadAtIndex2 = lambda index: (
        native.arrow_x if native.arrow_x is not None else (0.0975, 0.1025)[index],
        native.annotation.position[1] - 0.012, 0.0,
        (-1.0, 1.0)[index], 0.0, 0.0, 0.0035, 0.0007, 0.0, 0.0, 0.0, 1.0,
    )
    return native


def test_projection_detail_imports_once_before_crop_and_rechecks_settled_ink(lever_tip_native):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(
        native.adapter, (native.neighbour,), (native.back_caption,), native.source_step,
    )
    assert len(native.imports) == 1
    view, args = native.imports[0]
    assert view is native.view
    assert args["dimensions_by_feature"] == stack.THREAD_DRAWING_DIMENSIONS
    assert set(args["keep"]) == {stack.THREAD_PROJECTION_DIMENSION}
    assert native.shown == [(stack.THREAD_FEATURE,)]
    assert native.annotation.source is native.source
    assert native.annotation.endpoints is native.endpoints
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert native.source.Tolerance.Type == 0
    assert "VIEW FROM THE FRONT" in native.caption.GetText()
    assert native.caption.GetText().count("\n") == 2
    settled()
    native.rows[1]["position"] = (-0.100, -0.003, 0.0)
    moves = sum(event[0] == "move" for event in native.events)
    with pytest.raises(RuntimeError, match="crosses the zone frame"):
        settled()
    assert sum(event[0] == "move" for event in native.events) == moves


@pytest.mark.parametrize("failure", ["missing", "duplicate", "hidden", "configuration", "source"])
def test_projection_detail_keeps_real_component_configuration_after_rebuild(lever_tip_native, failure):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    component = native.drawing_components[0]
    if failure == "missing":
        native.drawing_components.pop()
    elif failure == "duplicate":
        native.drawing_components.append(component)
    elif failure == "hidden":
        component.Visible = False
    elif failure == "configuration":
        component.Component.ReferencedConfiguration = "Other"
    else:
        component.Component.source.ConfigurationManager.ActiveConfiguration.Name = "Other"
    with pytest.raises(RuntimeError, match="component selection|visible|configuration mismatch"):
        settled()
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert len(native.imports) == 1 and native.annotation.endpoints is native.endpoints


def test_detail_direction_exposes_the_nose_instead_of_the_occluding_flange():
    import magnifying_bracket_joint_layout as joint

    detail = drawing.LEVER_TIP
    radius_mm = detail.crop_radius * 1000 * detail.scale[1] / detail.scale[0]
    x = (stack.THREADED_TIP_X + stack.THREAD_FAR_FACE_X) / 2
    y = stack.LEVER_AXIS_Y
    # The entire former Front crop lies inside the nearer flange's footprint.
    assert joint.SIDE_PLATE_MACHINE_X[0] < x - radius_mm < x + radius_mm < joint.SIDE_PLATE_MACHINE_X[1]
    assert joint.BRACKET_ORIGIN[1] + joint.SIDE_PLATE_Y[0] < y - radius_mm
    assert y + radius_mm < joint.BRACKET_ORIGIN[1] + joint.SIDE_PLATE_Y[1]
    flange_near_z = joint.BRACKET_ORIGIN[2] + joint.SIDE_PLATE_Z[0]
    assert flange_near_z > assembly.LEVER_ROD_Z + drawing.LEVER_ROD_DIA / 2
    # Standard Front now captures old Back, without changing the installation.
    assert detail.orientation == "*Front"
    assert detail.scale == (4, 1)
    from mg_lever_thread_joint import NOSE_R
    assert assembly.LEVER_ROD_Z - NOSE_R < flange_near_z
    assert drawing.ASSEMBLED_VIEW_CAPTIONS[stack.DRAWING_BACK_VIEW] == "VIEW FROM THE BACK"


def test_back_caption_moves_once_using_whole_native_outline_not_crop(lever_tip_native):
    native = lever_tip_native
    before = tuple(native.back_extent)
    box = drawing._projection_note_box(native.back_caption)
    assert drawing.boxes_clear(box, drawing._crop_box(native.view, drawing.LEVER_TIP))
    assert not drawing.boxes_clear(box, tuple(native.outline))
    settled = drawing._thread_projection_detail(
        native.adapter, (native.neighbour,), (native.back_caption,), native.source_step,
    )
    assert drawing.boxes_clear(drawing._projection_note_box(native.back_caption), tuple(native.outline))
    assert native.back_extent[1] == before[1] and native.back_extent[4] == before[4]
    assert native.back_caption.GetText() == "VIEW FROM THE BACK"
    assert native.back_extent[3] == pytest.approx(
        native.outline[0] - drawing.CLEAR_GAP_M - drawing.PLACE_SETTLE_M
    )
    assert native.back_extent[0] >= native.margins[3]
    assert sum(event[0] == "caption-move" for event in native.events) == 1
    native.outline[0] -= 0.010
    with pytest.raises(RuntimeError, match="actual native view outline"):
        settled()
    assert sum(event[0] == "caption-move" for event in native.events) == 1


def test_moved_back_caption_must_still_clear_live_border_after_rebuild(lever_tip_native):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(
        native.adapter, (native.neighbour,), (native.back_caption,), native.source_step,
    )
    native.back_extent[0] -= 0.002
    native.back_extent[3] -= 0.002
    with pytest.raises(RuntimeError, match="assembled back caption.*zone frame"):
        settled()
    assert sum(event[0] == "caption-move" for event in native.events) == 1


def test_back_caption_fit_never_moves_from_an_invalid_native_outline(lever_tip_native):
    native = lever_tip_native
    native.outline[0] = float("nan")
    with pytest.raises(RuntimeError, match="non-finite native view outline"):
        drawing._fit_projection_back_caption(
            native.adapter, native.view, (native.neighbour,), (native.back_caption,),
        )
    assert not any(event[0] == "caption-move" for event in native.events)


@pytest.mark.parametrize("failure", ["refused-move", "ignored-move", "border"])
def test_back_caption_fit_requires_actual_native_readback(lever_tip_native, failure):
    native = lever_tip_native
    if failure == "refused-move":
        native.back_annotation.SetPosition2 = lambda *_args: False
    elif failure == "ignored-move":
        native.back_annotation.SetPosition2 = lambda *_args: True
    else:
        native.margins[3] = 0.020
    with pytest.raises(RuntimeError):
        drawing._fit_projection_back_caption(
            native.adapter, native.view, (native.neighbour,), (native.back_caption,),
        )


@pytest.mark.parametrize("fence", [
    [], _native_crop_fence((0.0975, 0.053), 0.0225),
    _native_crop_fence(radius=0), _native_crop_fence((float("nan"), 0.053)),
])
def test_native_crop_readback_refuses_nominal_only_or_shifted_fence(lever_tip_native, fence):
    native = lever_tip_native
    native.fence[:] = fence
    with pytest.raises(RuntimeError, match="native crop fence"):
        drawing._crop_box(native.view, drawing.LEVER_TIP)


@pytest.mark.parametrize("failure", [
    "source", "value", "nonfinite-value", "band", "precision", "owner",
    "dangling", "null-point", "entity-type", "replacement", "bool-identity",
    "missing", "duplicate",
])
def test_projection_detail_refuses_lost_authority_after_rebuild(lever_tip_native, failure):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    if failure == "source":
        native.source.FullName = f"ThreadProjection@OtherChain@{drawing.SOURCE.stem}"
    elif failure == "value":
        native.source.SystemValue += 0.0001
    elif failure == "nonfinite-value":
        native.source.SystemValue = float("nan")
    elif failure == "band":
        native.source.Tolerance.Type = 4
    elif failure == "precision":
        native.precision = 1
    elif failure == "owner":
        native.annotation.Owner = native.base
    elif failure == "dangling":
        native.annotation.IsDangling = lambda: True
    elif failure == "null-point":
        native.annotation.endpoints = (None, native.endpoints[1])
    elif failure == "entity-type":
        native.annotation.GetAttachedEntityTypes = lambda: (0, 11)
    elif failure == "replacement":
        native.annotation.endpoints = (object(), native.endpoints[1])
    elif failure == "bool-identity":
        native.adapter.swApp.IsSame = lambda a, b: a is b
    elif failure == "missing":
        native.annotations.clear()
    else:
        native.base.GetAnnotations = lambda: [native.annotation]
    with pytest.raises(RuntimeError):
        settled()


def test_projection_detail_refuses_import_lost_to_crop(lever_tip_native):
    native = lever_tip_native
    native.drop_on_crop = True
    with pytest.raises(RuntimeError, match="after crop.*expected one control"):
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)


@pytest.mark.parametrize("failed_reader", ["entities", "types", "owner", "display", "all"])
def test_projection_source_inventories_independent_reader_failures(
    monkeypatch, lever_tip_native, failed_reader,
):
    native = lever_tip_native
    events = []
    messages = []
    failed = {"entities", "types", "owner"} if failed_reader == "all" else {failed_reader}

    def reader(field, value):
        events.append(field)
        if field in failed:
            raise RuntimeError(f"{field} native failure")
        return value

    def log(message, **_kwargs):
        messages.append(message)
        events.append("log")

    monkeypatch.setattr(drawing._telemetry, "info", log)
    native.annotation.GetSpecificAnnotation = lambda: reader("display", native.display)
    native.annotation.GetAttachedEntities3 = lambda: reader("entities", native.endpoints)
    native.annotation.GetAttachedEntityTypes = lambda: reader("types", (11, 11))
    native.annotation.IsDangling = lambda: reader("dangling", False)
    monkeypatch.setattr(
        type(native.annotation), "Owner",
        property(lambda _self: reader("owner", native.view)), raising=False,
    )
    with pytest.raises(RuntimeError, match="inventory incomplete"):
        drawing._projection_source(
            native.adapter, native.view, native.annotation, stage="after crop diagnostic",
        )
    assert events[0] == "log"
    assert "after crop diagnostic" in messages[0]
    assert all(field in events for field in ("display", "entities", "types", "dangling", "owner"))
    inventory = messages[-1]
    assert "'dangling': False" in inventory
    assert "'owner_type': 0" in inventory
    for field in failed:
        assert f"{field} native failure" in inventory
    if failed_reader == "display":
        assert "'dimension': 'display'" in inventory
        assert "'types': (11, 11)" in inventory
        assert "'entity_count': 2" in inventory
    else:
        assert native.source.FullName in inventory
        assert f"'value': {native.source.SystemValue!r}" in inventory
        assert "'tolerance_type': 0" in inventory


def test_projection_source_collects_all_identity_codes_before_reader_failure(
    monkeypatch, lever_tip_native,
):
    native = lever_tip_native
    calls, messages = [], []

    def same(point, old):
        calls.append((point, old))
        if point is native.endpoints[0] and old is native.endpoints[0]:
            raise RuntimeError("first endpoint reader failed")
        return int(point is old)

    native.adapter.swApp.IsSame = same
    monkeypatch.setattr(drawing._telemetry, "info", lambda message, **_kw: messages.append(message))
    with pytest.raises(RuntimeError, match="endpoint identity readers failed"):
        drawing._projection_source(
            native.adapter, native.view, native.annotation,
            stage="settled diagnostic", original=native.endpoints,
        )
    assert calls == [(point, old) for point in native.endpoints for old in native.endpoints]
    assert "codes=((None, 0), (0, 1))" in messages[-1]
    assert "first endpoint reader failed" in messages[-1]


@pytest.mark.parametrize("failure", [
    "arrow-border", "witness-border", "caption-border", "caption-crop",
    "neighbour-caption", "neighbour-view", "scale", "uncropped", "missing-arrows",
    "nonfinite-witness", "direction-caption", "nonfinite-outline",
])
def test_projection_layout_guards_all_native_ink_and_neighbours(lever_tip_native, failure):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(
        native.adapter, (native.neighbour,), (native.back_caption,), native.source_step,
    )
    if failure == "arrow-border":
        native.arrow_x = 0.012
    elif failure == "witness-border":
        native.line_x = 0.012
    elif failure == "nonfinite-witness":
        native.line_x = float("nan")
    elif failure == "direction-caption":
        native.caption.GetText = lambda: drawing.LEVER_TIP.label_text.replace("FRONT", "BACK")
    elif failure == "nonfinite-outline":
        native.outline[0] = float("nan")
    elif failure == "caption-border":
        native.caption_extent[1] = 0.012
    elif failure == "caption-crop":
        native.caption_extent[4] = 0.036
    elif failure == "neighbour-caption":
        native.back_caption.GetExtent = lambda: (0.080, 0.070, 0, 0.130, 0.080, 0)
    elif failure == "neighbour-view":
        native.neighbour.GetOutline = lambda: (0.090, 0.070, 0.150, 0.120)
    elif failure == "scale":
        native.view.ScaleRatio = (1, 4)
    elif failure == "uncropped":
        native.cropped = False
    else:
        native.data.GetArrowHeadCount = lambda: 0
    with pytest.raises(RuntimeError):
        settled()


def test_step_seven_uses_the_actual_detail_and_attached_qualifier():
    step = notes.STEP_TEXT[steps.LEVER_THREADED_KEY]
    qualifier = " ".join(stack.SETTING_CALLOUTS[stack.THREAD_FEATURE][stack.THREAD_PROJECTION_DIMENSION][1].split())
    assert qualifier in step
    assert drawing.LEVER_TIP.title in step
    assert "THREAD PROJECTION" not in step
    assert "NO LOCKNUT, SET SCREW OR ADHESIVE" in step
    assert "THE PLAIN ROD HAS NO SHOULDER" in step
    assert "1.25" not in step


def test_lever_tip_placement_uses_opposite_native_view_and_isolation(monkeypatch):
    events = []
    detail = drawing.LEVER_TIP
    view = SimpleNamespace(Position=detail.centre)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(
        EditRebuild3=lambda: events.append(("rebuild",)) or True,
    ))
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "double_array", tuple)

    def place(_adapter, source, orientation, x, y, *, scale):
        events.append(("place", source, orientation, (x, y), scale))
        return view

    def projected(_adapter, actual_view, point, *, label):
        assert actual_view is view
        assert point == (
            (stack.THREADED_TIP_X + stack.THREAD_FAR_FACE_X) / 2000,
            stack.LEVER_AXIS_Y / 1000, 0.0,
        )
        return view.Position[0] + 0.040, view.Position[1] - 0.017

    def move(target, move_relative):
        assert move_relative is False
        view.Position = target
        events.append(("move", target))
        return True

    view.SetViewPosition = move
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "model_point_in_view", projected)
    monkeypatch.setattr(
        drawing, "apply_view_configuration",
        lambda _a, _v, **kwargs: events.append(("configuration", kwargs["role"])),
    )
    monkeypatch.setattr(
        drawing, "set_hidden_lines_removed", lambda _a, _v: events.append(("HLR",))
    )
    monkeypatch.setattr(
        drawing, "isolate_drawing_view_components",
        lambda _a, _v, **kwargs: events.append(("isolate", kwargs["visible_stems"])),
    )
    assert drawing._placed_detail(adapter, detail) is view
    assert events[0] == ("place", str(drawing.SOURCE), "*Front", detail.centre, (4, 1))
    assert view.Position == pytest.approx((0.060, 0.070))
    assert events[-2:] == [
        ("HLR",), ("isolate", frozenset({"mg-magnifying-lever", "mg-magnifying-bracket"})),
    ]
    assert drawing.PRESSED.orientation == drawing.ENDSHAKE.orientation == stack.DRAWING_LEFT_VIEW
    half_span_m = stack.THREAD_PROJECTION / 1000 * detail.scale[0] / detail.scale[1] / 2
    assert half_span_m < detail.crop_radius
    assert math.hypot(half_span_m, drawing._LEVER_R * 0.004) < detail.crop_radius


@pytest.mark.parametrize("detail", (drawing.LEVER_TIP, drawing.PRESSED, drawing.ENDSHAKE))
@pytest.mark.parametrize("previous_direct", [False, True])
@pytest.mark.parametrize("status,cropped", [(drawing.CROP_NO_ERROR, True), (0, False)])
def test_lever_tip_reuses_native_crop_sketch_transform(
    monkeypatch, status, cropped, previous_direct, detail,
):
    events = []
    transform = object()

    scale = detail.scale[0] / detail.scale[1]
    class Point:
        def __init__(self, values):
            self.ArrayData = values

        def MultiplyTransform(self, actual):
            assert actual is transform
            x, y, z = self.ArrayData
            return Point((x / scale, y / scale, z))

    manager = SimpleNamespace(AddToDB=previous_direct)
    fence = []
    authored = []

    def circle(*points):
        events.append(("circle", points, manager.AddToDB))
        cx, cy, _cz, rx, ry, _rz = (value * scale for value in points)
        if not manager.AddToDB:
            cx -= 0.0025  # R24's witness inference, not a native layout acceptance.
        fence[:] = _native_crop_fence((cx, cy), math.hypot(rx - cx, ry - cy))
        segment = SimpleNamespace(
            Select4=lambda append, data: events.append(("select", append, data)) or True
        )
        authored.append(segment)
        return segment

    manager.CreateCircle = circle
    sketch = SimpleNamespace(ModelToSketchTransform=transform)
    view = SimpleNamespace(
        GetSketch=lambda: sketch,
        Crop2=lambda *args: events.append(("Crop2", args)) or status,
        IsCropped=lambda: cropped,
        UpdateViewDisplayGeometry=lambda: events.append(("refresh",)),
        GetDetailCircleInfo2=lambda: fence,
    )
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(
            SketchManager=manager,
            ClearSelection2=lambda value: events.append(("clear", value)),
            EditRebuild3=lambda: events.append(("rebuild",)) or True,
        ),
        swApp=SimpleNamespace(GetMathUtility=lambda: SimpleNamespace(CreatePoint=Point)),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "null_callout", lambda: None)
    monkeypatch.setattr(drawing, "_activate", lambda *_a, **_k: None)
    if cropped:
        drawing._crop(adapter, view, detail)
    else:
        with pytest.raises(RuntimeError, match="not cropped"):
            drawing._crop(adapter, view, detail)
    cx, cy = detail.centre
    radius = detail.crop_radius
    assert events[0] == (
        "circle", (cx / scale, cy / scale, 0.0, (cx + radius) / scale, cy / scale, 0.0), True,
    )
    assert events[1:3] == [("select", False, None), ("Crop2", (False, False, 1))]
    assert events[-1] == ("refresh",)
    assert manager.AddToDB is previous_direct


@pytest.mark.parametrize("failure", ["creation", "selection"])
def test_deterministic_crop_restores_database_mode_on_native_refusal(monkeypatch, failure):
    manager = SimpleNamespace(AddToDB=False)
    calls = []

    def create(*_args):
        assert manager.AddToDB is True
        if failure == "creation":
            raise RuntimeError("native circle creation refused")
        return SimpleNamespace(Select4=lambda *_args: False)

    manager.CreateCircle = create
    view = SimpleNamespace(
        GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=object()),
        Crop2=lambda *_args: calls.append("crop"),
    )
    utility = SimpleNamespace(CreatePoint=lambda values: SimpleNamespace(
        MultiplyTransform=lambda _transform: SimpleNamespace(ArrayData=values),
    ))
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(SketchManager=manager),
        swApp=SimpleNamespace(GetMathUtility=lambda: utility),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "null_callout", lambda: None)
    monkeypatch.setattr(drawing, "_activate", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError, match="circle"):
        drawing._crop(adapter, view, drawing.LEVER_TIP)
    assert manager.AddToDB is False
    assert calls == []


def test_assembled_sheet_adds_one_projection_detail_with_existing_neighbours(monkeypatch):
    views, captions, projection_calls = [], [], []
    source_steps = []
    source_step = source_steps.append
    base_check, stack_check, projection_check = (lambda: None), (lambda: None), (lambda: None)
    sheet_view = object()
    adapter = SimpleNamespace(currentModel=SimpleNamespace(
        GetViews=lambda: [(sheet_view, *views), (object(),)],
    ))
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_a: None)
    monkeypatch.setattr(drawing, "apply_view_configuration", lambda *_a, **_k: None)

    def place(_adapter, source, orientation, x, y, *, scale):
        assert source == str(drawing.SOURCE) and scale == drawing.SHEET_SCALE
        view = SimpleNamespace(
            orientation=orientation, GetAnnotations=lambda: [],
            GetOutline=lambda: (x - 0.01, y - 0.02, x + 0.01, y + 0.02),
        )
        views.append(view)
        return view

    def stacks(_adapter, callback):
        assert callback is source_step
        callback("stack callback")
        for _ in range(2):
            label = object()
            annotation = SimpleNamespace(GetType=lambda: 6, GetSpecificAnnotation=lambda n=label: n)
            views.append(SimpleNamespace(GetAnnotations=lambda a=annotation: [a]))
        return stack_check

    def caption(*args, **kwargs):
        note = object()
        captions.append(note)
        return note

    def detail(_adapter, neighbours, notes, callback):
        assert callback is source_step
        callback("tip callback")
        projection_calls.append((neighbours, notes))
        return projection_check

    monkeypatch.setattr(drawing, "place_view", place)
    def lever(_adapter, view, callback):
        assert view is views[0] and callback is source_step
        callback("lever callback")
        return base_check

    monkeypatch.setattr(drawing, "_lever_settings", lever)
    monkeypatch.setattr(drawing, "_stack_dimensions", stacks)
    monkeypatch.setattr(drawing, "_add_note_block", caption)
    monkeypatch.setattr(drawing, "_thread_projection_detail", detail)
    assert drawing._place_assembled_sheet(adapter, source_step) == (base_check, stack_check, projection_check)
    assert [view.orientation for view in views[:3]] == [
        stack.DRAWING_BACK_VIEW, stack.DRAWING_LEFT_VIEW, stack.DRAWING_ISOMETRIC_VIEW,
    ]
    assert source_steps.index("lever callback") < source_steps.index("stack callback")
    assert source_steps.index("stack callback") < source_steps.index("tip callback")
    assert len(projection_calls) == 1
    neighbours, notes = projection_calls[0]
    assert neighbours == tuple(views) and len(neighbours) == 5
    assert notes[:2] == tuple(captions) and len(notes) == 4


@pytest.mark.parametrize(
    "box",
    [(0.0127 - 1e-10, 0.100, 0.020, 0.110),
     (0.020, 0.0127 - 1e-10, 0.030, 0.110),
     (0.020, 0.100, _TEMPLATE.width_m - 0.0127 + 1e-10, 0.110),
     (0.020, 0.100, 0.030, _TEMPLATE.height_m - 0.0127 + 1e-10)],
)
def test_projection_border_guard_has_no_outward_allowance(projection_native, box) -> None:
    native = projection_native
    with pytest.raises(RuntimeError, match="crosses the zone frame"):
        drawing.require_inside(
            stack.THREAD_PROJECTION_DIMENSION, box, drawing.sheet_region(native.adapter)
        )


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
    monkeypatch.setattr(assembly, "_physical_thread_projection", lambda *_a: (stack.THREADED_TIP_X, stack.THREAD_FAR_FACE_X))
    monkeypatch.setattr(assembly, "_assert_thread_projection_faces", lambda *_a: None)

    asyncio.run(assembly._author_lever_setting_reference(Adapter(), lever_name="lever-1", bracket_name="bracket-1"))

    tip = (stack.LEVER_TIP_X, stack.LEVER_AXIS_Y)
    clamp = (stack.CLAMP_CENTRE_X, stack.LEVER_AXIS_Y)
    fixture = (stack.CLAMP_CENTRE_X, stack.FIXTURE_AXIS_Y)
    threaded_tip = (stack.THREADED_TIP_X, stack.LEVER_AXIS_Y)
    far_face = (stack.THREAD_FAR_FACE_X, stack.LEVER_AXIS_Y)
    assert lines == [(*tip, *clamp), (*clamp, *fixture), (*threaded_tip, *far_face)]
    assert ("leg0", None, "horizontal") in relations
    assert ("leg1", None, "vertical") in relations
    assert ("leg0.end", "leg1.start", "coincident") in relations
    assert ("leg2", None, "horizontal") in relations
    assert anchors == [("leg0.start", *tip), ("leg2.start", *threaded_tip)]
    assert lengths == {
        stack.CLAMP_STATION_DIMENSION: ("horizontal_distance", stack.CLAMP_STATION),
        stack.FIXTURE_DROP_DIMENSION: ("vertical_distance", stack.FIXTURE_DROP),
        stack.THREAD_PROJECTION_DIMENSION: ("horizontal_distance", stack.THREAD_PROJECTION),
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
    assert blanked == [feature, stack.THREAD_FEATURE]


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
    assert drawing.BOM_COMPONENTS == tuple(
        drawing.BOM_ROW_KEYS[stem] for stem in notes.BOM_ORDER
    )
    assert set(notes.BOM_DESCRIPTIONS) == set(notes.BOM_ORDER)
    for stem, row in drawing.PART_ROWS.items():
        assert drawing.BOM_PART_NUMBERS[stem] == row["number"]
        skus = row.get("supplier_skus") or ()
        assert drawing.BOM_SKUS[stem] == (" / ".join(skus) if skus else "-")
    assert drawing.BOM_SKUS["sh-vn-thumb-screw"] == "91882A221"
    assert drawing.BOM_SKUS["mg-magnifying-lever"] == "-"
    assert notes.QUANTITIES["sh-vn-thumb-screw"] == 2


def test_the_bom_screw_lengths_are_the_vendor_specs_fractions() -> None:
    import sh_vn_clamp_screw_spec as clamp_screw
    import mg_vn_magnifying_bracket_screw_spec as bracket_screw
    from sh_vn_thumb_screw_spec import SHANK_LEN as thumb_len

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

    import sh_vn_clamp_screw_spec as clamp_screw

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


@pytest.fixture
def instruction_note_bounds(monkeypatch):
    # Sequence: actual b3 native GetExtent. The narrower checks box is only
    # an accepted-predicate control, not evidence of a native after-fix sheet.
    sequence_extent = [0.0176475, 0.0863243, 0.0, 0.2278142, 0.2583656, 0.0]
    checks_extent = [0.0176475, 0.0529645, 0.0, 0.201, 0.0753632, 0.0]
    adapter = SimpleNamespace(currentModel=SimpleNamespace(GraphicsRedraw2=lambda: None))
    sequence = SimpleNamespace(GetExtent=lambda: sequence_extent)
    checks = SimpleNamespace(GetExtent=lambda: checks_extent)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_activate_sheet", lambda _adapter, _name: None)
    return SimpleNamespace(
        sequence_extent=sequence_extent,
        checks_extent=checks_extent,
        readback=lambda: drawing._assert_instruction_clearance(adapter, sequence, checks),
    )


def test_instruction_native_bounds_accept_clear_boxes(instruction_note_bounds) -> None:
    instruction_note_bounds.readback()


def test_instruction_native_bounds_refuse_the_b3_title_block_overprint(
    instruction_note_bounds,
) -> None:
    # DetailItem377 from the b3 audit: the box reaches 8.4782 mm into the
    # title-block field. The note origin alone remains outside that field.
    instruction_note_bounds.checks_extent[:] = [
        0.0176475, 0.0529645, 0.0, 0.2244782, 0.0753632, 0.0,
    ]
    with pytest.raises(RuntimeError, match="assembly checks.*title-block clearance"):
        instruction_note_bounds.readback()


@pytest.mark.parametrize("gap_m", (0.0039, 0.0041))
def test_instruction_native_bounds_require_air_below_step_eleven(
    instruction_note_bounds, gap_m: float,
) -> None:
    instruction_note_bounds.checks_extent[4] = (
        instruction_note_bounds.sequence_extent[1] - gap_m
    )
    if gap_m < drawing._PAD:
        with pytest.raises(RuntimeError, match="native gap below the sequence"):
            instruction_note_bounds.readback()
    else:
        instruction_note_bounds.readback()


@pytest.mark.parametrize(
    ("index", "value"),
    (
        (0, drawing.INNER_BORDER[0] + drawing._PAD - 0.0001),
        (1, drawing.INNER_BORDER[1] + drawing._PAD - 0.0001),
        (3, drawing.INNER_BORDER[2] - drawing._PAD + 0.0001),
        (4, drawing.INNER_BORDER[3] - drawing._PAD + 0.0001),
    ),
)
def test_instruction_native_bounds_require_border_air(
    instruction_note_bounds, index: int, value: float,
) -> None:
    instruction_note_bounds.checks_extent[index] = value
    with pytest.raises(RuntimeError, match="assembly checks.*border clearance"):
        instruction_note_bounds.readback()


@pytest.mark.parametrize(
    "extent",
    (
        (),
        (0.018, 0.053, 0.0, 0.201, 0.075),
        (0.018, 0.053, 0.0, math.nan, 0.075, 0.0),
        (0.018, 0.053, 0.0, 0.201, math.inf, 0.0),
        (0.018, 0.053, 0.0, 0.018, 0.075, 0.0),
        (0.018, 0.075, 0.0, 0.201, 0.053, 0.0),
    ),
)
def test_instruction_native_bounds_refuse_unreadable_or_degenerate_boxes(
    instruction_note_bounds, extent: tuple[float, ...],
) -> None:
    instruction_note_bounds.checks_extent[:] = extent
    with pytest.raises(RuntimeError, match="assembly checks.*invalid native note extent"):
        instruction_note_bounds.readback()


def test_the_steps_and_checks_fit_their_column() -> None:
    for block, width in (
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.CHECKS_LINE_WIDTH),
    ):
        assert max(len(line) for line in block.splitlines()) <= width
    steps_bottom = drawing.STEPS_XY[1] - len(
        drawing.ASSEMBLY_STEPS.splitlines()
    ) * drawing.NOTE_LINE_PITCH
    checks_bottom = drawing.CHECKS_XY[1] - len(
        drawing.ASSEMBLY_CHECKS.splitlines()
    ) * drawing.NOTE_LINE_PITCH
    assert drawing.STEPS_XY[0] > drawing.INNER_BORDER[0]
    assert drawing.STEPS_XY[1] < drawing.INNER_BORDER[3]
    assert checks_bottom > drawing.INNER_BORDER[1] + drawing._PAD
    # Upstream native envelopes used shorter, non-threaded text. They cannot
    # certify these combined blocks. Check derived spacing here; final native
    # whole-note/layout checks must establish clearance for this exact text.
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


def test_whole_check_note_rewrap_clears_r22_aggregate_keepout(
    monkeypatch,
) -> None:
    from _drawing_annotation_extent import boxes_clear
    from _drawing_layout_check import DrawableRegion

    # Native R22 PDF/layout JSON, run 20261021T114849219Z-97170adcbc744b108a6c2f7a37ddaba5.
    # The actual five-row note extent overlaps the panel even though each
    # printed row clears it. Keep this aggregate-box positive control:
    # acceptance requires the WHOLE note box clear, not a per-row exception.
    native_extent = (0.0176475, 0.0572536, 0.2187594, 0.0801289)
    assert not boxes_clear(native_extent, drawing.TITLE_BLOCK, gap=0.0)
    # A left shift for the existing layout pad would breach the left border.
    required_shift = native_extent[2] - drawing.TITLE_BLOCK[0] + drawing._PAD
    assert native_extent[0] - required_shift < drawing.INNER_BORDER[0]
    # CenturyGothic 13.2286 pt, advances measured from R22 PDF char boxes.
    # Predict the extent delta using the same native font, not source-copy
    # wrapping code or a claim that the candidate has already rendered.
    advances = {
        " ": 3.664551, "'": 2.619415, ",": 3.664536, ".": 3.664551,
        "1": 7.329041, ":": 3.664330, "A": 9.789703, "B": 7.593231,
        "C": 10.754883, "D": 9.842621, "E": 7.090942, "F": 6.416260,
        "G": 11.535988, "H": 9.035645, "I": 2.989807, "K": 7.818115,
        "L": 6.111954, "M": 12.157776, "N": 9.789703, "O": 11.496277,
        "P": 7.831787, "R": 8.030212, "S": 6.588226, "T": 5.635681,
        "U": 8.665222, "V": 9.287003, "W": 12.700165, "X": 8.056381,
        "Y": 7.831787,
    }
    old_rows = [
        *drawing._wrapped(notes.ASSEMBLY_CHECKS[:-1], width=80).splitlines(),
        *drawing._wrapped(notes.ASSEMBLY_CHECKS[-1:], width=72).splitlines(),
    ]
    adapter = object()
    calls = []
    monkeypatch.setattr(
        drawing, "_activate_sheet",
        lambda actual_adapter, name: calls.append(("sheet", actual_adapter, name)),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)

    def add_note(actual_adapter, text, x, y):
        calls.append(("note", actual_adapter, x, y))
        return SimpleNamespace(GetText=lambda: text.replace("\n", "\r\n"))

    monkeypatch.setattr(drawing, "add_note", add_note)
    note = drawing._add_note_block(
        adapter, drawing.SHEET_NAMES[3], drawing.ASSEMBLY_CHECKS,
        drawing.CHECKS_XY, label="assembly checks",
    )
    assert calls == [
        ("sheet", adapter, drawing.SHEET_NAMES[3]),
        ("note", adapter, *drawing.CHECKS_XY),
    ]
    printed_rows = note.GetText().splitlines()
    assert " ".join(printed_rows).split() == " ".join(notes.ASSEMBLY_CHECKS).split()
    assert printed_rows[0] == notes.ASSEMBLY_CHECKS[0]
    # Keep all five CHECK rows and the original steps column. A changed step
    # may move the check block only through the existing line-count formula.
    assert len(printed_rows) == len(old_rows) == 5
    assert [i for i, row in enumerate(printed_rows) if row.startswith("CHECK:")] == [0, 1, 3]
    assert drawing.ASSEMBLY_STEPS == drawing._wrapped(
        notes.ASSEMBLY_STEPS, width=80, heading="ASSEMBLY SEQUENCE"
    )
    assert drawing.CHECKS_XY == (
        drawing.STEPS_XY[0],
        drawing.STEPS_XY[1]
        - len(drawing.ASSEMBLY_STEPS.splitlines()) * drawing.NOTE_LINE_PITCH
        - 2 * drawing._PAD,
    )
    points_per_m = 72 / 0.0254
    old_width = max(sum(advances[c] for c in row) for row in old_rows)
    new_width = max(sum(advances[c] for c in row) for row in printed_rows)
    vertical_shift = drawing.CHECKS_XY[1] - 0.0798  # R22 native insertion y
    predicted_extent = (
        native_extent[0], native_extent[1] + vertical_shift,
        native_extent[2] + (new_width - old_width) / points_per_m,
        native_extent[3] + vertical_shift,
    )
    drawing.require_inside(
        "assembly checks", predicted_extent, DrawableRegion(*drawing.INNER_BORDER)
    )
    assert boxes_clear(predicted_extent, drawing.TITLE_BLOCK, gap=drawing._PAD)
    assert predicted_extent[2] + drawing._PAD < drawing.FINISHED_FIELD[0]


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
    # off the clamp block, the 1/2 hex whose bottom face sits LEVER_BORE_Y
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


class _MagnifierBomTable:
    """Native readback with a real retained, hidden, zero-width column."""

    def __init__(self, cells, native_members):
        self.cells = cells
        self.native_members = native_members
        self.column_types = [
            (202, "", 0),
            (204, '$PRP:"Number"', 0),
            (204, "", 0),
            (203, "", 0),
            (201, "", 0),
        ]
        self.hidden = [False] * 4 + [True]
        self.widths = [0.02] * 4 + [0.0]
        self.heights = {}
        self.row_hidden = {}
        self.text_writes = []
        self.title_writes = []
        self.number_property = "Number"

    @property
    def RowCount(self):
        return len(self.cells)

    @property
    def TotalRowCount(self):
        return self.RowCount

    def RowHidden(self, row):
        if not 0 <= row < self.TotalRowCount:
            raise IndexError(row)
        return self.row_hidden.get(row, False)

    @property
    def ColumnCount(self):
        return self.hidden.count(False)

    @property
    def TotalColumnCount(self):
        return len(self.column_types)

    def _physical_column(self, column, include_hidden=True):
        columns = [
            index for index, hidden in enumerate(self.hidden)
            if include_hidden or not hidden
        ]
        return columns[column] if 0 <= column < len(columns) else None

    def GetColumnType3(self, column, include_hidden):
        physical = self._physical_column(column, include_hidden)
        return (-1, None, 0) if physical is None else self.column_types[physical]

    def ColumnHidden(self, column):
        # Visibility PROPERTY indices are 1-based; storage remains physical.
        return self.hidden[column - 1] if 1 <= column <= len(self.hidden) else False

    def GetColumnWidth(self, column):
        physical = self._physical_column(column, False)
        return self.widths[physical] if physical is not None else 0.0

    def GetColumnTitle2(self, column, include_hidden):
        return self.DisplayedText2(0, column, include_hidden)

    def DisplayedText2(self, row, column, include_hidden):
        physical = self._physical_column(column, include_hidden)
        if physical is None:
            return ""
        if physical < len(self.cells[row]):
            return self.cells[row][physical]
        return "PART NUMBER" if row == 0 else self.cells[row][1]

    def DisplayedText(self, row, column):
        return self.DisplayedText2(row, column, False)

    def GetColumnCustomProperty(self, column):
        if not 0 <= column < len(self.column_types):
            return ""
        if column == 1 and self.column_types[column][0] == 204:
            return self.number_property
        return ""

    def GetComponents2(self, row, _configuration):
        return self.native_members[row - 1]

    def InsertColumn2(self, where, after, title, _width):
        if where != 3 or not 0 <= after < len(self.column_types):
            return False
        column = after + 1
        for row, contents in enumerate(self.cells):
            contents.insert(column, title if row == 0 else "")
        self.column_types.insert(column, (204, "", 0))
        self.hidden.insert(column, False)
        self.widths.insert(column, 0.02)
        return True

    def SetColumnTitle2(self, column, title, include_hidden):
        self.title_writes.append((column, title, include_hidden))
        physical = self._physical_column(column, include_hidden)
        if physical is None or physical >= len(self.cells[0]):
            return False
        self.cells[0][physical] = title
        return True

    def IsCellTextEditable(self, row, column):
        return 0 < row < self.RowCount and (
            self.GetColumnTitle2(column, True) == drawing.BOM_SKU_TITLE
        )

    def SetText2(self, row, column, include_hidden, text):
        self.text_writes.append((row, column, include_hidden, text))
        physical = self._physical_column(column, include_hidden)
        if physical is None:
            raise IndexError(column)
        if not self.IsCellTextEditable(row, column):
            raise AssertionError("Number cells must stay natively property-linked")
        self.cells[row][physical] = text

    def SetColumnWidth(self, column, width, options):
        assert options == 0
        physical = self._physical_column(column, False)
        if physical is None:
            raise IndexError(column)
        self.widths[physical] = width
        return width

    def SetRowHeight(self, row, height, options):
        assert options == 0
        self.heights[row] = height
        return height


@pytest.mark.parametrize("hidden", (True, None, 0, 1, ""))
@pytest.mark.parametrize("row", (0, 1))
def test_bom_cells_requires_exact_visible_row_before_physical_text(hidden, row) -> None:
    reads = []
    table = SimpleNamespace(
        RowCount=2,
        ColumnCount=1,
        RowHidden=lambda index: hidden if index == row else False,
        DisplayedText2=lambda *args: reads.append(args) or "TEXT",
    )
    with pytest.raises(RuntimeError):
        drawing._bom_cells(table)
    assert reads == ([(0, 0, True)] if row == 1 else [])


@pytest.fixture
def magnifier_bom(monkeypatch):
    import _com
    import _component_references as references
    import _drawing_tables as tables

    monkeypatch.setattr(_com, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(
        tables._sw_type_info, "early_bound_or_flag", lambda value, *_members: value
    )
    cells = [["ITEM NO.", "PART NUMBER", "DESCRIPTION", "QTY."]]
    native_members = []
    expected_items = {}
    # Native row order need not match the package's balloon order. Keep the
    # configured wire expectation independent of the drawing's BOM_ROW_KEYS.
    native_order = tuple(reversed(notes.BOM_ORDER))
    for item, stem in enumerate(native_order, start=1):
        is_wire = stem == "sh-vn-music-wire"
        row_key = "sh-vn-music-wire--LeverWire" if is_wire else stem
        expected_items[row_key] = str(item)
        cells.append(
            [
                str(item),
                drawing.BOM_PART_NUMBERS[row_key],
                notes.BOM_DESCRIPTIONS[stem],
                str(notes.QUANTITIES[stem]),
            ]
        )
        native_members.append(
            tuple(
                SimpleNamespace(
                    Name2=f"{stem}-{index + 1}",
                    GetPathName=lambda stem=stem: f"C:/native/{stem}.SLDPRT",
                    ReferencedConfiguration=(
                        "LeverWire Simplified" if is_wire else "Default Simplified"
                    ),
                    GetModelDoc2=lambda row_key=row_key: SimpleNamespace(
                        GetCustomInfoValue=lambda _member, _property: (
                            drawing.BOM_PART_NUMBERS[row_key]
                        )
                    ),
                )
                for index in range(notes.QUANTITIES[stem])
            )
        )
    table = _MagnifierBomTable(cells, native_members)
    return SimpleNamespace(
        table=table,
        cells=cells,
        expected_items=expected_items,
        wire=native_members[native_order.index("sh-vn-music-wire")][0],
    )


@pytest.mark.parametrize(
    "fault", (None, "quantity", "native-count", "same-number-member", "number-property")
)
def test_bom_keeps_physical_quantity_and_refuses_rebuild_drift(
    magnifier_bom, fault
) -> None:
    table = magnifier_bom.table
    if fault == "number-property":
        table.number_property = "Description"
    rebuilds = []

    def rebuild():
        rebuilds.append(True)
        if fault == "quantity":
            table.cells[1][4] = str(int(table.cells[1][4]) + 1)
        elif fault == "native-count":
            row = int(magnifier_bom.expected_items["sh-vn-thumb-screw"]) - 1
            table.native_members[row] = table.native_members[row][:-1]
        elif fault == "same-number-member":
            magnifier_bom.wire.ReferencedConfiguration = "PenWire Simplified"
        return True

    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=rebuild))
    if fault is None:
        assert drawing._validate_bom(adapter, table) == magnifier_bom.expected_items
        assert table.DisplayedText2(0, 4, True) == "QTY."
        assert table.DisplayedText(0, 4) == "QTY."
        assert table.GetColumnType3(4, True)[0] == 203
        assert table.GetColumnType3(4, False)[0] == 203
        assert table.ColumnHidden(6) is True
        assert table.ColumnHidden(5) is False
        proof = drawing.validate_bom_number_property(
            table,
            configuration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
            label="magnifier",
            expected_rows=1 + len(drawing.BOM_COMPONENTS),
            occurrence_quantities=True,
        )
        assert [(row, number, quantity) for row, _members, number, quantity in proof] == [
            (int(item), drawing.BOM_PART_NUMBERS[stem], str(drawing.BOM_QUANTITIES[stem]))
            for stem, item in magnifier_bom.expected_items.items()
        ]
        for stem, item in magnifier_bom.expected_items.items():
            row = int(item)
            assert table.DisplayedText2(row, 4, True) == str(drawing.BOM_QUANTITIES[stem])
            assert table.DisplayedText2(row, 3, True) == drawing.BOM_SKUS[stem]
            assert table.DisplayedText2(row, 4, False) == str(
                drawing.BOM_QUANTITIES[stem]
            )
            assert table.DisplayedText2(row, 1, False) == drawing.BOM_PART_NUMBERS[stem]
        assert table.title_writes == [(3, drawing.BOM_SKU_TITLE, True)]
        assert table.text_writes == [
            (int(item), 3, True, drawing.BOM_SKUS[stem])
            for stem, item in magnifier_bom.expected_items.items()
        ]
    else:
        with pytest.raises(RuntimeError):
            drawing._validate_bom(adapter, table)
    assert rebuilds == ([] if fault == "number-property" else [True])
    assert table.cells[0].count(drawing.BOM_SKU_TITLE) == 1


@pytest.mark.parametrize(
    "fault",
    (
        "native-column",
        "number-column",
        "number-property",
        "visible-prefix",
        "displayed-number",
        "member",
        "quantity",
        "hidden-row",
        "unreadable-row",
    ),
)
def test_finalization_rereads_retained_bom_after_reference_hiding(
    monkeypatch, tmp_path, magnifier_bom, fault
) -> None:
    from unittest.mock import AsyncMock

    import _com
    import _component_references as references
    from _test_stubbed_build import stub_seat

    monkeypatch.setattr(_com, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    table = magnifier_bom.table
    for row in magnifier_bom.cells:
        row.insert(3, "VENDOR SKU" if row is magnifier_bom.cells[0] else "-")
    column_types = table.column_types
    column_types.insert(3, (204, "", 0))
    hidden = table.hidden
    hidden.insert(3, False)
    table.widths.insert(3, 0.02)
    native_reads = []
    get_components = table.GetComponents2

    def components(row, configuration):
        native_reads.append((row, configuration))
        return get_components(row, configuration)

    table.GetComponents2 = components
    source = tmp_path / "magnifier.SLDASM"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    seat = stub_seat(
        monkeypatch,
        drawing,
        keep=(
            "build", "validate_bom_number_property",
            "component_identity", "component_reference_names",
            "_validate_source", "_source_sha256",
            "_assert_source_identity", "_source_dirty_tracer",
        ),
    )
    seat._early_bound.side_effect = lambda value, _interface: value
    seat.read_required_properties.return_value = {"Number": notes.DRAWING_NUMBER}
    seat._place_assembled_sheet.return_value = ()
    reference = SimpleNamespace(ReferencedConfiguration="Default Simplified")
    seat._place_collapsed_view.return_value = reference
    seat._fit_ring.return_value = drawing.SHEET_SCALE
    seat._view_outline.return_value = drawing.LEVER_FIELD
    seat.insert_bom_table.return_value = table
    seat._validate_bom.return_value = magnifier_bom.expected_items
    seat.add_component_bom_balloons.side_effect = (
        lambda *_args, items, **_kwargs: [
            SimpleNamespace(stem=stem) for stem, _item in items
        ]
    )
    monkeypatch.setattr(
        drawing, "_bom_items", lambda _table: magnifier_bom.expected_items
    )
    monkeypatch.setattr(drawing, "lever_caption_xy", lambda *_args: (0.0, 0.0))
    # Page geometry is independent of the real settled native-column proof.
    monkeypatch.setattr(
        drawing, "_assert_bom_clears_reference_field", lambda _table: None
    )
    seat.finalize_drawing.return_value = {"drawing": "offline.SLDDRW"}
    source_model = _ExplodeSource()
    adapter = SimpleNamespace(
        open_model=AsyncMock(), currentModel=source_model
    )
    assert asyncio.run(drawing.build(adapter)) == {"drawing": "offline.SLDDRW"}
    checks = seat.finalize_drawing.call_args.kwargs["settled_checks"]
    expected_reads = [
        (row, reference.ReferencedConfiguration) for row in range(1, table.RowCount)
    ]
    assert native_reads == expected_reads
    native_reads.clear()
    for check in checks:
        check()
    assert native_reads == expected_reads

    if fault == "native-column":
        column_types[-1] = (204, "", 0)
    elif fault == "number-column":
        column_types[1] = (201, "", 0)
    elif fault == "number-property":
        table.number_property = "Description"
    elif fault == "visible-prefix":
        hidden[3] = True
    elif fault == "displayed-number":
        magnifier_bom.cells[1][1] = "UNLINKED"
    elif fault == "quantity":
        magnifier_bom.cells[1][4] = str(int(magnifier_bom.cells[1][4]) + 1)
    elif fault == "hidden-row":
        table.row_hidden[1] = True
    elif fault == "unreadable-row":
        table.row_hidden[1] = None
    else:
        magnifier_bom.wire.ReferencedConfiguration = "PenWire Simplified"
    with pytest.raises(RuntimeError):
        for check in checks:
            check()


@pytest.mark.parametrize("wire_member", ("LeverWire", "LeverWire Simplified"))
def test_every_bom_family_is_ballooned_exactly_once_across_the_package(
    magnifier_bom, wire_member
) -> None:
    magnifier_bom.wire.ReferencedConfiguration = wire_member
    items = drawing._bom_items(magnifier_bom.table)
    assert items == magnifier_bom.expected_items
    ballooned = [
        (row_key, item)
        for stems in (
            explode.WHEEL_GROUP_STEMS,
            explode.LEVER_GROUP_STEMS,
            frozenset({explode.WIRE_STEM}),
        )
        for row_key, item in drawing.balloon_items(items, stems)
    ]
    assert sorted(ballooned) == sorted(magnifier_bom.expected_items.items())
    assert drawing.balloon_items(items, frozenset({explode.WIRE_STEM})) == (
        (
            "sh-vn-music-wire--LeverWire",
            magnifier_bom.expected_items["sh-vn-music-wire--LeverWire"],
        ),
    )


@pytest.mark.parametrize("wrong_member", ("PenWire", "PenWire Simplified", "Default"))
def test_balloon_item_map_refuses_the_wrong_native_wire_member(
    magnifier_bom, wrong_member
) -> None:
    assert drawing._bom_items(magnifier_bom.table) == magnifier_bom.expected_items
    # The shared file and displayed Number are unchanged; only the installed
    # native member changes, so neither can stand in for its configured row.
    magnifier_bom.wire.ReferencedConfiguration = wrong_member
    with pytest.raises(RuntimeError, match="expected one logical member"):
        drawing._bom_items(magnifier_bom.table)


@pytest.mark.parametrize(
    "replacement_row", (None, "sh-vn-music-wire", "sh-vn-music-wire--PenWire")
)
def test_wire_balloon_requires_its_logical_bom_row(magnifier_bom, replacement_row) -> None:
    items = drawing._bom_items(magnifier_bom.table)
    item = items.pop("sh-vn-music-wire--LeverWire")
    if replacement_row is not None:
        items[replacement_row] = item
    with pytest.raises(KeyError) as error:
        drawing.balloon_items(items, frozenset({explode.WIRE_STEM}))
    assert error.value.args == ("sh-vn-music-wire--LeverWire",)


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
    import _component_references as references
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
        "sh-vn-music-wire-73": ((0.075, 0.200, 0.300),) * 5,
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
            ComponentReference=(
                "LeverWire:1" if name == "sh-vn-music-wire-73" else ""
            ),
            ReferencedConfiguration=(
                "LeverWire" if name == "sh-vn-music-wire-73" else "Default"
            ),
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
    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
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
        "sh-vn-music-wire-73": (0.0, 0.0, 0.0),
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
                ReferencedConfiguration="LeverWire" if item.stem == notes.WIRE else "Default",
                ComponentReference="LeverWire:1" if item.stem == notes.WIRE else "",
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

    def GetComponents(self, _top_level_only):
        # This MG source is flat: all immediate children are leaves, so the
        # recursive and top-level native inventories contain the same handles.
        return self.components

    def GetExplodedViewNames2(self, configuration):
        return (explode.exploded_view_name(configuration),)

    def GetCustomInfoValue(self, configuration, name):
        assert configuration == ""
        return self.properties.get(name, "")


def test_mg_validate_source_reads_both_metadata_maps_without_activation(monkeypatch):
    import _component_references as references

    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
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
    import _component_references as references

    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _ExplodeSource()
    source.properties.pop(explode.explode_offsets_property(configuration))
    with pytest.raises((ValueError, RuntimeError), match="builder-owned explode offsets"):
        drawing._validate_source(source)

@pytest.mark.parametrize("failure", ["active configuration", "displaced", "families", "foreign", "wire member"])
def test_mg_metadata_does_not_replace_current_source_safety(monkeypatch, failure):
    import _component_references as references

    monkeypatch.setattr(references, "_early_bound", lambda value, _interface: value)
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    source = _ExplodeSource()
    if failure == "active configuration":
        source.ConfigurationManager.ActiveConfiguration.Name = "Default Simplified"
    elif failure == "families":
        source.components.pop()
    elif failure == "foreign":
        source.components.append(SimpleNamespace(
            Name2="foreign-part-1",
            ComponentReference="",
            ReferencedConfiguration="Default",
            GetPathName=lambda: "C:/parts/foreign-part.SLDPRT",
            GetTotalTransform=source.components[0].GetTotalTransform,
        ))
    elif failure == "wire member":
        wire = next(component for component in source.components if component.ComponentReference == "LeverWire:1")
        wire.ReferencedConfiguration = "PenWire"
    else:
        base = source.components[0].GetTotalTransform(False).ArrayData
        displaced = list(base)
        displaced[9] = 0.001
        source.components[0].GetTotalTransform = lambda presentation: SimpleNamespace(
            ArrayData=displaced if presentation else base
        )
    with pytest.raises(RuntimeError):
        drawing._validate_source(source)
    assert not source.dirty
    assert source.configuration_switches == []



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
    monkeypatch.setattr(drawing, "_activate_sheet", lambda *_a: None)
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
    source_steps = []

    def import_settings():
        if group == "lever":
            return drawing._lever_settings(adapter, object(), source_steps.append)
        return drawing._stack_dimensions(adapter, source_steps.append)

    if missing:
        with pytest.raises(RuntimeError, match="callout reads ''"):
            import_settings()
        return
    settled = import_settings()
    settled()
    assert source_steps == [
        f"{group} settings import and readback", f"{group} settings settled readback",
    ]
    text_parts[name][part] = ""
    with pytest.raises(RuntimeError, match="callout reads ''"):
        settled()


def test_tip_camera_preserves_old_back_after_actual_standard_view_remap(monkeypatch):
    import _assembly
    import _assembly_named_views

    # Native standard camera rows, before the builder's remap. These are
    # independent of the drawing's chosen orientation string.
    old_front = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    old_back = (-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0)
    old_right = (0.0, 0.0, -1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0)
    old_iso = (
        1 / math.sqrt(2), 0.0, -1 / math.sqrt(2),
        -1 / math.sqrt(6), 2 / math.sqrt(6), -1 / math.sqrt(6),
        1 / math.sqrt(3), 1 / math.sqrt(3), 1 / math.sqrt(3),
    )

    class Model:
        def __init__(self):
            self.standard = {1: old_front, 2: old_back, 4: old_right, 7: old_iso}
            self.named = {}
            self.current = None
            self.Extension = SimpleNamespace(
                GetNamedViewRotation=lambda name: self.named[name],
                UpdateStandardViews=self.update,
            )

        def GetStandardViewRotation(self, view_id):
            return self.standard[view_id]

        def ShowNamedView2(self, name, view_id):
            self.current = self.named[name] if name else self.standard[view_id]

        def NameView(self, name):
            self.named[name] = self.current

        def update(self, name, view_id):
            assert name == "" and view_id == 1
            self.standard[1] = self.current
            self.standard[2] = tuple(
                value if index // 3 == 1 else -value
                for index, value in enumerate(self.current)
            )
            return True

    for module in (_assembly, _assembly_named_views):
        monkeypatch.setattr(module, "_early_bound", lambda value, _iface: value)
    model = Model()
    adapter = SimpleNamespace(currentModel=model, _zoom_to_fit=lambda _model: None)
    # Execute the actual two builder helpers in their canonical order.
    assembly.name_standard_views(adapter, views=stack.DRAWING_STANDARD_VIEWS, label="MG")
    assembly.remap_front_to_machine_front(adapter)
    cameras = {"*Front": model.standard[1], "*Back": model.standard[2], **model.named}
    tip_rows = cameras[drawing.LEVER_TIP.orientation]
    assert tip_rows == old_back
    assert model.current == old_back
    assert cameras[stack.DRAWING_BACK_VIEW] == old_front
    assert cameras[drawing.PRESSED.orientation] == old_right
    assert cameras[drawing.ENDSHAKE.orientation] == old_right
    assert cameras[stack.DRAWING_ISOMETRIC_VIEW] == old_iso
    assert is_pictorial_orientation(stack.DRAWING_ISOMETRIC_VIEW)
    point = (stack.THREADED_TIP_X, stack.LEVER_AXIS_Y, assembly.LEVER_ROD_Z)
    projected = tuple(
        sum(point[i] * tip_rows[3 * axis + i] for i in range(3))
        for axis in range(3)
    )
    assert projected == pytest.approx((-point[0], point[1], -point[2]))
    assert tip_rows[6:] == (0.0, 0.0, -1.0)  # Viewer on the unobstructed -Z side.
    assert cameras[stack.DRAWING_BACK_VIEW][6:] == (0.0, 0.0, 1.0)


@pytest.mark.parametrize("stage", ["import", "settled"])
@pytest.mark.parametrize("damage", ["missing", "wrong compartment", "changed text"])
def test_tip_inherited_callout_is_required_without_repair(lever_tip_native, stage, damage):
    native = lever_tip_native
    part, text = stack.SETTING_CALLOUTS[stack.THREAD_FEATURE][stack.THREAD_PROJECTION_DIMENSION]
    if stage == "settled":
        settled = drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    native.display.parts.clear()
    if damage == "wrong compartment":
        native.display.parts[3] = text
    elif damage == "changed text":
        native.display.parts[part] = text + "\nCHANGED"
    before = dict(native.display.parts)
    with pytest.raises(RuntimeError, match="below callout reads"):
        if stage == "import":
            drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
        else:
            settled()
    assert native.display.parts == before
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert native.annotation.endpoints is native.endpoints


@pytest.fixture
def immutable_tip_build(
    monkeypatch, tmp_path, lever_tip_native, magnifier_bom, instruction_note_bounds,
):
    """Run build's real source guards and Tip checks; fake only native I/O.

    No production source/configuration guard or source_step is replaced. The
    finalizer double runs its supplied settled callbacks before a save marker.
    """
    native = lever_tip_native
    path = tmp_path / drawing.SOURCE.name
    path.write_bytes(b"released MG source")
    monkeypatch.setattr(drawing, "SOURCE", path)
    source = _ExplodeSource()
    drawing_model = native.adapter.currentModel
    drawing_model.GraphicsRedraw2 = lambda: None
    state = SimpleNamespace(
        source=source, path=path, native=native, saved=False, finalized=False,
        hook=lambda _stage: None, metadata_reads=[], phases=[], balloon_calls=[],
        bom_items=dict(magnifier_bom.expected_items),
    )
    get_property = source.GetCustomInfoValue

    def property_value(configuration, name):
        state.metadata_reads.append((configuration, name))
        return get_property(configuration, name)

    source.GetCustomInfoValue = property_value

    async def open_model(actual_path):
        assert actual_path == str(path)
        native.adapter.currentModel = source
        return SimpleNamespace(is_success=True, data=None, error=None)

    native.adapter.open_model = open_model
    monkeypatch.setattr(
        drawing, "read_required_properties",
        lambda *_a, **_k: {"Number": notes.DRAWING_NUMBER},
    )
    monkeypatch.setattr(
        drawing, "_create_sheets",
        lambda adapter: setattr(adapter, "currentModel", drawing_model),
    )

    def assembled(adapter, source_step):
        return (drawing._thread_projection_detail(adapter, (), (), source_step),)

    monkeypatch.setattr(drawing, "_place_assembled_sheet", assembled)
    monkeypatch.setattr(
        drawing._telemetry, "event",
        lambda name, **fields: state.phases.append((name, fields)),
    )
    views = {}

    def place(_adapter, _sheet, _field, *_args, label):
        view = SimpleNamespace(
            GetOutline=lambda: (0.100, 0.120, 0.200, 0.230),
            IsExploded=lambda: label in (drawing.WHEEL_LABEL, drawing.LEVER_LABEL),
            ReferencedConfiguration=drawing.SIMPLIFIED_VIEW_CONFIGURATION,
        )
        views[label] = view
        return view

    monkeypatch.setattr(drawing, "_place_exploded_view", place)
    monkeypatch.setattr(drawing, "_place_collapsed_view", place)
    for name in (
        "assert_full_detail_view", "isolate_drawing_view_components",
        "_show_tangent_edges", "_assert_bom_clears_reference_field",
        "_link_view_to_bom", "_move_wire_balloon", "assert_balloon_landings",
    ):
        monkeypatch.setattr(drawing, name, lambda *_a, **_k: None)
    monkeypatch.setattr(drawing, "_fit_ring", lambda _a, _v, ladder, *_args, **_k: ladder[0])
    monkeypatch.setattr(drawing, "insert_bom_table", lambda *_a, **_k: magnifier_bom.table)
    items = state.bom_items
    monkeypatch.setattr(drawing, "_validate_bom", lambda *_a: items)

    def balloons(_adapter, view, **kwargs):
        state.balloon_calls.append((view, kwargs))
        return [SimpleNamespace(stem=stem) for stem, _item in kwargs["items"]]

    monkeypatch.setattr(drawing, "add_component_bom_balloons", balloons)
    monkeypatch.setattr(
        drawing, "_add_note_block",
        lambda *_a, label, **_k: SimpleNamespace(
            GetExtent=lambda: (
                instruction_note_bounds.sequence_extent if label == "assembly sequence"
                else instruction_note_bounds.checks_extent
            ),
        ),
    )
    monkeypatch.setattr(
        drawing, "_hide_bom_reference", lambda *_a: state.hook("before-finalizer"),
    )

    async def finalize(_adapter, _outputs, **kwargs):
        state.finalized = True
        state.hook("before-settled")
        for settled in kwargs["settled_checks"]:
            settled()
        state.saved = True
        state.hook("after-save")
        return {"drawing": "synthetic artifact"}

    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    state.views = views
    return state


def test_build_keeps_source_immutable_through_tip_and_finalization(immutable_tip_build):
    state = immutable_tip_build
    inherited = dict(state.native.display.parts)
    expected_sha = drawing._source_sha256(state.path)
    assert asyncio.run(drawing.build(state.native.adapter)) == {"drawing": "synthetic artifact"}
    assert state.saved and state.finalized
    assert state.native.display.parts == inherited
    assert drawing._source_sha256(state.path) == expected_sha
    assert not state.source.dirty
    assert state.source.configuration_switches == []
    assert state.source.ConfigurationManager.ActiveConfiguration.Name == "Default"
    owners = tuple(drawing.EXPLODED_VIEW_NAMES)
    assert state.metadata_reads == [
        ("", explode.explode_offsets_property(owner)) for owner in (*owners, *owners)
    ]
    phases = [fields for name, fields in state.phases if name == "magnifier.source_save_flag"]
    assert phases and all(not fields["dirty"] for fields in phases)
    tip_phases = [fields["step"] for fields in phases if fields["step"].startswith("lever tip")]
    assert tip_phases == [
        "lever tip view placement, configuration and isolation",
        "lever tip import, crop and inherited callout readback",
        "lever tip qualifier and caption placement",
        "lever tip settled source, callout and whole-ink readback",
        "lever tip settled source, callout and whole-ink readback",
    ]
    # Canonical #1842 restores all real BOM groups, with builder-owned
    # exploded metadata and the separately collapsed finished wire.
    assert len(state.balloon_calls) == 3
    seen = []
    for (view, kwargs), label, stems in zip(
        state.balloon_calls,
        (drawing.WHEEL_LABEL, drawing.LEVER_LABEL, drawing.FINISHED_LABEL),
        (explode.WHEEL_GROUP_STEMS, explode.LEVER_GROUP_STEMS, frozenset({explode.WIRE_STEM})),
        strict=True,
    ):
        assert view is state.views[label]
        assert {stem for stem, _item in kwargs["items"]} == {
            drawing.BOM_ROW_KEYS[stem] for stem in stems
        }
        assert kwargs["explode_offsets"] == (
            {} if label == drawing.FINISHED_LABEL else _metadata_offsets()
        )
        seen.extend(kwargs["items"])
    assert len(seen) == len(set(seen)) == len(notes.BOM_ORDER)
    assert dict(seen) == state.bom_items
    assert (drawing.WIRE_ROW, state.bom_items[drawing.WIRE_ROW]) in seen


@pytest.mark.parametrize("stage", ["before-finalizer", "before-settled", "after-save"])
@pytest.mark.parametrize("damage", ["dirty", "bytes"])
def test_build_refuses_source_changes_at_each_save_boundary(immutable_tip_build, stage, damage):
    state = immutable_tip_build

    def mutate(actual_stage):
        if actual_stage != stage:
            return
        if damage == "dirty":
            state.source.dirty = True
        else:
            state.path.write_bytes(b"externally changed source")

    state.hook = mutate
    with pytest.raises(RuntimeError, match="dirtied the source|changed the source"):
        asyncio.run(drawing.build(state.native.adapter))
    assert state.saved == (stage == "after-save")
    assert state.finalized == (stage != "before-finalizer")
    assert state.source.dirty == (damage == "dirty")
    assert state.path.read_bytes() == (
        b"externally changed source" if damage == "bytes" else b"released MG source"
    )


@pytest.mark.parametrize("damage", ["configuration", "displaced", "metadata"])
def test_build_rechecks_source_configuration_collapse_and_metadata_after_save(
    immutable_tip_build, damage,
):
    state = immutable_tip_build

    def mutate(stage):
        if stage != "after-save":
            return
        if damage == "configuration":
            state.source.ConfigurationManager.ActiveConfiguration.Name = "Default Simplified"
        elif damage == "metadata":
            state.source.properties.clear()
        else:
            base = state.source.components[0].GetTotalTransform(False).ArrayData
            displaced = (*base[:9], 0.01, *base[10:])
            state.source.components[0].GetTotalTransform = lambda presentation: SimpleNamespace(
                ArrayData=displaced if presentation else base,
            )

    state.hook = mutate
    with pytest.raises(RuntimeError, match="Default configuration|collapsed|rebuild"):
        asyncio.run(drawing.build(state.native.adapter))
    assert state.saved
    assert state.path.read_bytes() == b"released MG source"
    assert not state.source.dirty


def test_build_secondary_proof_and_logging_interrupts_preserve_primary(immutable_tip_build, monkeypatch):
    state = immutable_tip_build
    original = KeyboardInterrupt("primary native interruption")
    traces = []

    def fail_reader():
        raise SystemExit("secondary source proof")

    def fail_logger(*_args, **_kwargs):
        raise GeneratorExit("secondary logging")

    def interrupt(stage):
        if stage != "after-save":
            return
        state.source.GetSaveFlag = fail_reader
        monkeypatch.setattr(drawing._telemetry, "warn", fail_logger)
        try:
            raise original
        except BaseException as exc:
            traces.append(exc.__traceback__)
            raise

    state.hook = interrupt
    with pytest.raises(KeyboardInterrupt) as caught:
        asyncio.run(drawing.build(state.native.adapter))
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not traces[0]:
        trace = trace.tb_next
    assert trace is traces[0]


def test_tip_whole_ink_reads_the_current_model_callout_authority(projection_native, monkeypatch):
    native = projection_native
    name = stack.THREAD_PROJECTION_DIMENSION
    callouts = stack.SETTING_CALLOUTS[stack.THREAD_FEATURE]
    part, original = callouts[name]
    changed = original.replace(original.split()[0], "MODEL", 1)
    monkeypatch.setitem(callouts, name, (part, changed))
    with pytest.raises(RuntimeError, match="callout reads"):
        drawing._assert_callouts([(name, native.display)], callouts)
    native.display.parts[part] = changed
    drawing._assert_callouts([(name, native.display)], callouts)
    # A good GetText is insufficient while DisplayData still renders old ink.
    with pytest.raises(RuntimeError, match="missing rendered qualifier"):
        drawing._thread_projection_text_box(native.adapter, native.annotation)
    for row, text in zip(native.rows[1:], changed.splitlines(), strict=True):
        row["text"] = text
    box = drawing._thread_projection_text_box(native.adapter, native.annotation)
    assert box[0] < box[2] and box[1] < box[3]


def test_build_refuses_preexisting_dirty_source_before_tip_import(immutable_tip_build):
    state = immutable_tip_build
    state.source.dirty = True
    with pytest.raises(RuntimeError, match="already dirty"):
        asyncio.run(drawing.build(state.native.adapter))
    assert state.source.dirty
    assert state.native.imports == []
    assert not state.finalized and not state.saved
    assert state.path.read_bytes() == b"released MG source"


def test_build_tip_settled_ink_failure_prevents_save_and_still_proves_source(immutable_tip_build):
    state = immutable_tip_build

    def erase_qualifier(stage):
        if stage == "before-settled":
            del state.native.rows[1:]

    state.hook = erase_qualifier
    with pytest.raises(RuntimeError, match="missing rendered qualifier"):
        asyncio.run(drawing.build(state.native.adapter))
    assert state.finalized and not state.saved
    assert state.path.read_bytes() == b"released MG source"
    assert not state.source.dirty
    assert len(state.metadata_reads) == 2 * len(drawing.EXPLODED_VIEW_NAMES)



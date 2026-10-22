"""Offline contract for the magnifier assembly drawing and its stack settings."""

import asyncio
import json
import math
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
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
    import sys

    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(IID_IUnknown="IUnknown"))
    monkeypatch.setitem(sys.modules, "solidworks_mcp.adapters._generated.sldworks_2026", SimpleNamespace(
        IEdge=SimpleNamespace(CLSID="IEdge"), IEntity=SimpleNamespace(CLSID="IEntity"),
    ))

    class Dispatch:
        def QueryInterface(self, iid, fallback):
            assert iid in ("IEdge", "IEntity") and fallback == "IUnknown"
            return object()

    native = projection_native
    native.failure_captures = []
    native.source_steps = []
    native.source_step = native.source_steps.append

    def capture_failure(adapter, label, message, **kwargs):
        # Never let offline tests save production documents or capture the host.
        assert adapter is native.adapter
        native.failure_captures.append((label, message, kwargs))
        native.events.append(("capture-failure",))
        raise kwargs["exception"]

    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture_failure)
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
    native.transform_dx = 0.0
    native.boundary_paper_dy = 0.0
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

    class Point:
        def __init__(self, values):
            self.ArrayData = tuple(values)

        def MultiplyTransform(self, transform):
            native.events.append(("component-transform", self.ArrayData))
            return Point(transform(self.ArrayData))

    native.adapter.swApp = SimpleNamespace(
        IsSame=lambda a, b: int(a is b),
        GetMathUtility=lambda: SimpleNamespace(CreatePoint=Point),
        RevisionNumber=lambda: "34.4",
    )
    native.adapter.currentModel.ViewZoomtofit2 = lambda: native.events.append(("zoom",))
    monkeypatch.setattr(drawing, "double_array", tuple)
    native.drawing_components = []
    native.visible_components = []
    native.edges = []
    native.component_edges = {}
    native.controls = []
    for stem, x, radius in (
        ("mg-magnifying-lever", drawing.ROD_LENGTH / 1000,
         (drawing.LEVER_ROD_DIA / 2 - drawing.TIP_CHAMFER) / 1000),
        ("mg-magnifying-bracket", -drawing.NECK_HALF_X / 1000, drawing.NOSE_R / 1000),
    ):
        name = f"{stem}-1"
        curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=(x, 0, 0, 1, 0, 0, radius))
        edge = SimpleNamespace(
            GetCurve=lambda curve=curve: curve,
            GetClosestPointOn=lambda *point: (*point, 0.0, 0.0),
        )
        native.edges.append(edge)
        native.component_edges[name] = [edge]

        def transform(point, stem=stem):
            x, y, z = point
            if stem == "mg-magnifying-lever":
                return (
                    assembly.LEVER_X0 / 1000 - x + native.transform_dx,
                    assembly.LEVER_ROD_Y / 1000 + y, assembly.LEVER_ROD_Z / 1000 - z,
                )
            return (
                assembly.BRACKET_X / 1000 + x + native.transform_dx,
                assembly.LEVER_ROD_Y / 1000 + y, assembly.LEVER_ROD_Z / 1000 + z,
            )

        full = SimpleNamespace(
            Name2=name, GetPathName=lambda stem=stem: f"C:/parts/{stem}.SLDPRT",
            Transform2=transform,
        )
        control_x, control_radius = (
            (drawing.NECK_HALF_X / 1000, drawing.NOSE_R / 1000)
            if stem == "mg-magnifying-bracket" else
            ((drawing.ROD_LENGTH - drawing.TIP_CHAMFER) / 1000, drawing.LEVER_ROD_DIA / 2000)
        )
        control_curve = SimpleNamespace(
            IsCircle=lambda: True, CircleParams=(control_x, 0, 0, 1, 0, 0, control_radius),
        )
        control = SimpleNamespace(GetCurve=lambda curve=control_curve: curve)
        native.controls.append(control)
        native.component_edges[name].append(control)
        for candidate in (edge, control):
            candidate._oleobj_ = Dispatch()
            candidate.GetComponent = lambda full=full: full
            candidate.GetBody = lambda: SimpleNamespace(IsTemporaryBody=lambda: False)
        full.ReferencedConfiguration = "Default"
        full.source = SimpleNamespace(
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
            Extension=SimpleNamespace(GetCorrespondingEntity2=lambda candidate: candidate),
        )
        full.GetModelDoc2 = lambda full=full: full.source
        full.GetCorrespondingEntity = lambda candidate: candidate
        native.drawing_components.append(SimpleNamespace(Component=full, Visible=True))
        native.visible_components.append(SimpleNamespace(Name2=name))
    native.rendered_edges = [*native.edges, *native.controls]
    native.view.GetCorrespondingEntity = lambda candidate: candidate
    # SDK geometry/metadata/point payload. Coordinates are intentionally NOT sheet
    # coordinates; topology correspondence is the native ink positive control.
    native.polyline = (0, 0, 0, 0, 0, 0, -1, 0, 2, 100, 200, 300, 101, 200, 300)
    native.view.GetVisibleDrawingComponents = lambda: native.drawing_components
    native.view.GetVisibleComponents = lambda: native.visible_components
    native.view.GetPolylines7 = lambda cross: (
        tuple(native.rendered_edges), native.polyline * len(native.rendered_edges)
    )

    def entities(view, component, kind):
        assert view is native.view and kind == 1
        native.events.append(("visible-edges", component.Name2))
        return native.component_edges[component.Name2]

    monkeypatch.setattr(drawing, "visible_component_entities", entities)
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
        # Current remapped Front preserves old Back: reverse X, retain Y.
        # Component Z is real; the authored chain is in the assembly's Z=0 plane.
        return tuple(
            (cx - 4 * (x - mx), cy + 4 * (y - my)
             + (native.boundary_paper_dy if len(points) == 4 and index % 2 else 0))
            for index, (x, y, _z) in enumerate(points)
        )

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


@pytest.fixture
def r28_identity_native(lever_tip_native):
    """Actual G7/match data; new ownership/config/view guards are explicit doubles.

    R28 did NOT observe those new guards. A passing double tests the contract,
    not a claim that the saved native drawing already passed it.
    """
    import json

    native = lever_tip_native
    native.actual = json.loads(
        (Path(__file__).parent / "fixtures" / "mg_r28_projection_identity.json").read_text(encoding="utf-8")
    )
    native.contexts, native.sources = {}, {}
    native.mapping_calls, native.g7_calls = [], []
    native.roundtrip_code = 1
    native.negative_code = 0

    class NoEdgeInterface(Exception):
        hresult = -2147467262

    class Dispatch:
        def __init__(self, supported=True):
            self.supported = supported

        def QueryInterface(self, iid, fallback):
            assert iid in ("IEdge", "IEntity") and fallback == "IUnknown"
            if not self.supported:
                raise NoEdgeInterface("No such interface supported")
            return object()

    def edge(params, *, stem=None, role=None, context="g7", slot=None, supported=True, owner=None):
        curve = SimpleNamespace(IsCircle=lambda: params is not None, CircleParams=params)
        return SimpleNamespace(
            _oleobj_=Dispatch(supported), stem=stem, role=role, context=context, slot=slot,
            GetCurve=lambda: curve, GetBody=lambda: SimpleNamespace(IsTemporaryBody=lambda: False),
            GetComponent=lambda: owner, GetClosestPointOn=lambda *p: (*p, 0.0, 0.0),
        )

    native.raw_slots = [
        edge(row["circle"], slot=index, supported=row["qi_edge"]["status"] == "OBSERVED")
        for index, row in enumerate(native.actual["g7"]["slots"])
    ]
    native.raw_data = list(native.actual["g7"]["doubles"])
    for index, drawing_component in enumerate(native.drawing_components):
        component = drawing_component.Component
        stem = component.Name2.rsplit("-", 1)[0]
        actual = native.actual["components"][stem]
        for role, seed in actual["seeds"].items():
            for context in ("visible", "source", "component", "view"):
                native.contexts[stem, role, context] = edge(
                    tuple(seed["circle"]), stem=stem, role=role, context=context,
                    owner=component if context in ("visible", "view") else None,
                )
        native.edges[index] = native.contexts[stem, "target", "visible"]
        native.component_edges[component.Name2] = [
            native.contexts[stem, role, "visible"] for role in ("target", "control")
        ]

        def part(candidate, stem=stem):
            native.mapping_calls.append(("source", stem, candidate.role, candidate.context))
            if candidate.stem != stem or candidate.context not in ("visible", "component", "view"):
                return None
            return native.contexts[stem, candidate.role, "source"]

        def instance(candidate, stem=stem):
            native.mapping_calls.append(("component", stem, candidate.role, candidate.context))
            if candidate.stem != stem or candidate.context != "source":
                return None
            return native.contexts[stem, candidate.role, "component"]

        source = SimpleNamespace(
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
            Extension=SimpleNamespace(GetCorrespondingEntity2=part),
            GetPathName=component.GetPathName,
        )
        native.sources[stem] = source
        component.GetModelDoc2 = lambda source=source: source
        component.GetCorrespondingEntity = instance

    def in_view(candidate):
        native.mapping_calls.append(("view", candidate.stem, candidate.role, candidate.context))
        if candidate.context != "component":
            return None
        return native.contexts[candidate.stem, candidate.role, "view"]

    def same(left, right):
        if left is right:
            return 1
        lc, rc = getattr(left, "context", None), getattr(right, "context", None)
        if lc == "component" and rc == "g7":
            row = native.actual["components"][left.stem]["seeds"][left.role]["source_component_g7"][right.slot]
            return row["value"]["value"] if row["status"] == "OBSERVED" else -1
        if {lc, rc} == {"visible", "view"}:
            return native.roundtrip_code if (left.stem, left.role) == (right.stem, right.role) else 0
        if lc == rc and lc in ("visible", "source", "component") and left.stem == right.stem:
            return native.negative_code
        return 0

    def polylines(cross):
        native.g7_calls.append(cross)
        return tuple(native.raw_slots), tuple(native.raw_data)

    native.view.GetCorrespondingEntity = in_view
    native.view.GetPolylines7 = polylines
    native.adapter.swApp.IsSame = same
    return native


def test_r28_single_route_accepts_actual_matches_only_with_new_guards(r28_identity_native, monkeypatch):
    import struct

    native = r28_identity_native
    # Both representations of the retained numeric payload agree; neither is
    # replaced by a synthetic outline or by the nominal installation dimension.
    assert b"".join(struct.pack("<d", v) for v in native.raw_data).hex() == native.actual["g7"]["ieee754_le"]
    evidence = []
    observe = drawing._projection_component_identity

    def record(*args, **kwargs):
        result = observe(*args, **kwargs)
        evidence.append(args[5])
        return result

    monkeypatch.setattr(drawing, "_projection_component_identity", record)
    calibration = {}
    points = drawing._projection_model_ink(
        native.adapter, native.view, stage="uncropped physical boundaries", calibration=calibration,
    )
    assert points[0] == pytest.approx((0.1025, 0.053))
    assert points[1] == pytest.approx((0.0975, 0.053))
    assert [row["matched_decoded_indices"] for row in evidence] == [
        {"target": [30], "control": [28]}, {"target": [10], "control": [8]},
    ]
    for row in evidence:
        for key in ("negative.visible", "negative.source", "negative.component"):
            assert row["readers"][key]["value"]["value"] == 0
        for role in ("target", "control"):
            for key in ("owner_same", "view.same_seed", "view.owner_same", "source_back.same"):
                assert row["readers"][f"{role}.{key}"]["value"]["value"] == 1
    assert native.g7_calls == [1] and not native.failure_captures
    assert set(calibration) == set(native.actual["components"])
    assert native.imports == [] and not native.cropped


@pytest.mark.parametrize("fault", [
    "wrong-instance", "null-owner", "owner-bool", "wrong-config", "missing-config",
    "null-source", "null-part", "null-component", "null-view", "bad-view-roundtrip",
    "view-bool", "wrong-view-owner", "component-as-view", "bad-source-roundtrip",
    "negative-alias", "typeless-g7", "no-target-ink", "no-control-ink",
    "wrong-g7-geometry", "temporary-g7",
])
def test_r28_new_guard_refusals_capture_original_payload(r28_identity_native, fault):
    native = r28_identity_native
    stem = "mg-magnifying-lever"
    target = native.contexts[stem, "target", "visible"]
    full = native.drawing_components[0].Component
    source = native.sources[stem]
    if fault in ("wrong-instance", "null-owner"):
        # Same path/name deliberately do NOT make this the same component.
        other = SimpleNamespace(Name2=full.Name2, GetPathName=full.GetPathName)
        target.GetComponent = lambda: other if fault == "wrong-instance" else None
    elif fault == "owner-bool":
        same = native.adapter.swApp.IsSame
        native.adapter.swApp.IsSame = lambda a, b: True if a is full and b is full else same(a, b)
    elif fault == "wrong-config":
        source.ConfigurationManager.ActiveConfiguration.Name = "Other"
    elif fault == "missing-config":
        source.ConfigurationManager.ActiveConfiguration = None
    elif fault == "null-source":
        full.GetModelDoc2 = lambda: None
    elif fault == "null-part":
        source.Extension.GetCorrespondingEntity2 = lambda _edge: None
    elif fault == "null-component":
        full.GetCorrespondingEntity = lambda _edge: None
    elif fault == "null-view":
        native.view.GetCorrespondingEntity = lambda _edge: None
    elif fault in ("bad-view-roundtrip", "view-bool"):
        native.roundtrip_code = 0 if fault == "bad-view-roundtrip" else True
    elif fault == "wrong-view-owner":
        native.contexts[stem, "target", "view"].GetComponent = lambda: SimpleNamespace(Name2=full.Name2)
    elif fault == "component-as-view":
        native.view.GetCorrespondingEntity = lambda candidate: candidate
    elif fault == "bad-source-roundtrip":
        original = source.Extension.GetCorrespondingEntity2
        source.Extension.GetCorrespondingEntity2 = lambda candidate: (
            native.contexts[stem, "control", "source"] if candidate.context == "view" else original(candidate)
        )
    elif fault == "negative-alias":
        native.negative_code = 1
    elif fault == "typeless-g7":
        native.raw_slots[30]._oleobj_.supported = False
    elif fault in ("no-target-ink", "no-control-ink"):
        # Actual R28 arc30 (981:1020) / arc28 (903:942): collapse geometry
        # and every tessellation point; correspondence alone cannot supply ink.
        offset = 981 if fault == "no-target-ink" else 903
        center = native.raw_data[offset + 2:offset + 5]
        native.raw_data[offset + 5:offset + 11] = center * 2
        native.raw_data[offset + 21:offset + 39] = center * 6
    elif fault == "wrong-g7-geometry":
        curve = native.raw_slots[30].GetCurve()
        curve.CircleParams = (*curve.CircleParams[:6], 0.01)
    else:
        native.raw_slots[30].GetBody = lambda: SimpleNamespace(IsTemporaryBody=lambda: True)
    with pytest.raises(RuntimeError, match="physical model proof failed") as raised:
        drawing._projection_model_ink(native.adapter, native.view, stage="uncropped physical boundaries")
    assert native.g7_calls == [1]
    assert len(native.failure_captures) == 1
    packet = native.failure_captures[0][2]
    assert packet["exception"] is raised.value
    probe = packet["native_identity_probe"]
    assert probe["source_import_and_crop"] == "NOT_REACHED"
    raw = probe["readers"]["original_return"]["value"]["items"]
    assert raw[0]["length"] == len(native.raw_slots)
    assert raw[1]["length"] == len(native.raw_data)
    if fault in ("wrong-instance", "null-owner", "owner-bool", "wrong-config", "missing-config", "null-source"):
        proof = probe["physical_evidence"]["visible_components"][0]["identity_proof"]
        assert proof["readers"]["target.part"]["status"] == "NOT_REACHED"
    assert native.imports == [] and not native.cropped


def test_r28_cropped_proof_uses_uncropped_control_calibration_not_offcrop_ink(r28_identity_native):
    native = r28_identity_native
    calibration = {}
    drawing._projection_model_ink(
        native.adapter, native.view, stage="uncropped physical boundaries", calibration=calibration,
    )
    native.cropped = True
    # Simulate crop removing the independent controls, not either target. The
    # bracket control at paper X47.5mm is outside the 20mm-radius final fence.
    native.raw_slots[8] = native.raw_slots[28] = None
    for component in native.drawing_components:
        native.component_edges[component.Component.Name2] = [
            e for e in native.component_edges[component.Component.Name2] if e.role == "target"
        ]
    native.mapping_calls.clear()
    drawing._projection_model_ink(
        native.adapter, native.view, stage="settled drawing", calibration=calibration,
    )
    assert all(call[2] == "target" for call in native.mapping_calls)
    assert not native.failure_captures
    # The same calibration cannot excuse loss of the actual cropped target.
    native.raw_slots[30] = None
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._projection_model_ink(
            native.adapter, native.view, stage="settled drawing", calibration=calibration,
        )


@pytest.mark.parametrize("fault", ["missing", "view", "component", "source", "configuration", "target-owner"])
def test_r28_cropped_calibration_cannot_cross_namespace_or_configuration(r28_identity_native, fault):
    native = r28_identity_native
    calibration = {}
    drawing._projection_model_ink(
        native.adapter, native.view, stage="uncropped physical boundaries", calibration=calibration,
    )
    native.cropped = True
    stem = "mg-magnifying-lever"
    if fault == "missing":
        calibration.clear()
    elif fault in ("view", "component", "source"):
        original = calibration[stem][fault]
        calibration[stem][fault] = SimpleNamespace(
            name=getattr(original, "name", None),
            Name2=getattr(original, "Name2", None),
            GetPathName=getattr(original, "GetPathName", lambda: ""),
        )
    elif fault == "configuration":
        # Even matching current source/component configurations cannot reuse a
        # calibration collected from a different actual configuration.
        native.drawing_components[0].Component.ReferencedConfiguration = "Other"
        native.sources[stem].ConfigurationManager.ActiveConfiguration.Name = "Other"
    else:
        native.contexts[stem, "target", "visible"].GetComponent = lambda: None
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._projection_model_ink(
            native.adapter, native.view, stage="settled drawing", calibration=calibration,
        )
    assert native.failure_captures


@pytest.fixture
def projection_context_native(lever_tip_native, monkeypatch):
    """Synthetic diagnostic contexts with a deliberately unproved view roundtrip."""
    import sys

    native = lever_tip_native
    native.qi_calls = []
    native.pid_calls = []
    native.contexts = {}
    native.g7_calls = []
    monkeypatch.setitem(sys.modules, "pythoncom", SimpleNamespace(IID_IUnknown="IUnknown"))
    monkeypatch.setitem(sys.modules, "solidworks_mcp.adapters._generated.sldworks_2026", SimpleNamespace(
        IEdge=SimpleNamespace(CLSID="IEdge"), IEntity=SimpleNamespace(CLSID="IEntity"),
    ))

    class Dispatch:
        def QueryInterface(self, iid, fallback):
            native.qi_calls.append((iid, fallback))
            assert iid in ("IEdge", "IEntity") and fallback == "IUnknown"
            return object()

    class Extension:
        def __init__(self, stem, index):
            self.stem, self.index, self.serial = stem, index, 0

        def GetCorrespondingEntity2(self, edge):
            if edge.stem != self.stem or edge.context == "part":
                return None
            return native.contexts[self.stem, edge.role, "part"]

        def GetPersistReference3(self, edge):
            assert edge.stem == self.stem and edge.context == "part"
            self.serial += 1
            return (self.index, edge.role, self.serial)

        def IsSamePersistentID(self, left, right):
            assert left[0] == right[0] == self.index
            native.pid_calls.append((left, right))
            # Different returned bytes can refer to the same native object.
            return int(left[:2] == right[:2])

        def GetObjectByPersistReference3(self, reference):
            assert reference[0] == self.index
            return native.contexts[self.stem, reference[1], "part"], 0

    native.extensions = []
    g7 = []
    for index, (drawing_component, target) in enumerate(zip(native.drawing_components, native.edges, strict=True)):
        component = drawing_component.Component
        stem = component.Name2.rsplit("-", 1)[0]
        target_params = target.GetCurve().CircleParams
        control_params = (
            (drawing.NECK_HALF_X / 1000, 0, 0, 1, 0, 0, drawing.NOSE_R / 1000)
            if stem == "mg-magnifying-bracket" else
            ((drawing.ROD_LENGTH - drawing.TIP_CHAMFER) / 1000, 0, 0, -1, 0, 0, drawing.LEVER_ROD_DIA / 2000)
        )
        for role, params in enumerate((target_params, control_params)):
            curve = SimpleNamespace(IsCircle=lambda: True, CircleParams=params)
            for context in ("visible", "g7", "part", "component", "view"):
                edge = target if role == 0 and context == "visible" else SimpleNamespace()
                edge.stem, edge.role, edge.context = stem, role, context
                edge._oleobj_ = Dispatch()
                edge.GetCurve = lambda curve=curve: curve
                edge.GetBody = lambda: SimpleNamespace(IsTemporaryBody=lambda: False)
                edge.GetComponent = lambda component=component, context=context: None if context == "part" else component
                native.contexts[stem, role, context] = edge
            g7.append(native.contexts[stem, role, "g7"])
        native.component_edges[component.Name2] = [target, native.contexts[stem, 1, "visible"]]
        extension = Extension(stem, index)
        native.extensions.append(extension)
        source = SimpleNamespace(
            Extension=extension, GetPathName=component.GetPathName,
            ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default")),
        )
        component.GetModelDoc2 = lambda source=source: source
        component.ReferencedConfiguration = "Default"
        # Preserve the existing callable component transform while exposing its
        # independent, synthetic native matrix readback to the diagnostic.
        component.Transform2.ArrayData = tuple(float(index) for index in range(16))
        component.GetCorrespondingEntity = lambda edge, stem=stem: (
            native.contexts[stem, edge.role, "component"]
            if edge.stem == stem and edge.context == "part" else None
        )
    native.view.GetCorrespondingEntity = lambda edge: (
        native.contexts[edge.stem, edge.role, "view"]
        if edge.context in ("part", "component") else None
    )

    def same(left, right):
        if left is right:
            return 1
        # A component/G7 positive alone is insufficient: this fixture deliberately
        # lacks view/visible roundtrip identity, so production MUST still refuse.
        return int(
            {getattr(left, "context", None), getattr(right, "context", None)} == {"component", "g7"}
            and (left.stem, left.role) == (right.stem, right.role)
        )

    native.adapter.swApp.IsSame = same
    # Deliberately 37 original slots, 36 decoded entries, one null. R27's
    # original slot count/data were NOT captured and are not fabricated here.
    native.raw_slots = (g7[0], None, *g7[1:], *(g7[-1] for _ in range(32)))
    native.raw_result = native.raw_slots, native.polyline * len(native.raw_slots)

    def polylines(cross):
        native.g7_calls.append(cross)
        return native.raw_result

    native.view.GetPolylines7 = polylines
    return native


def test_identity_refusal_captures_mapped_positive_without_view_roundtrip(projection_context_native):
    import json

    native = projection_context_native
    with pytest.raises(RuntimeError, match="physical model proof failed") as raised:
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert native.g7_calls == [1]
    assert len(native.failure_captures) == 1
    label, _message, capture = native.failure_captures[0]
    assert label == "mg-magnifier-thread-projection-identity"
    assert capture["exception"] is raised.value and capture["sheet_png"] is True
    probe = capture["native_identity_probe"]
    assert probe["rendered_status"] == "DECODED"
    assert probe["decoded_model_edge_count"] == 36
    assert probe["source_import_and_crop"] == "NOT_REACHED"
    readers = probe["readers"]
    assert readers["original_slot_count"]["value"]["value"] == 37
    assert readers["original_return"]["value"]["items"][0]["length"] == 37
    assert readers["g7[1].raw"]["status"] == "RETURNED_NULL"
    assert readers["g7[36].qi.IEdge"]["status"] == "OBSERVED"
    assert readers["g7[36].owner"]["status"] == "OBSERVED"
    assert readers["view.transform"]["status"] == "OBSERVED"
    for component_index, component in enumerate(native.drawing_components):
        prefix = f"component[{component.Component.Name2}]"
        assert readers[f"{prefix}.control_candidates"]["value"]["length"] == 1
        assert readers[f"{prefix}.distinct_negative"]["value"]["value"] == 0
        assert readers[f"{prefix}.negative.part.part"]["value"]["value"] == 0
        slot = (0, 3)[component_index]
        assert readers[f"{prefix}.target.raw.g7[{slot}].same"]["value"]["value"] == 0
        assert readers[f"{prefix}.target.part.g7[{slot}].part.pid_same"]["value"]["value"] == 1
        assert readers[f"{prefix}.g7[{slot}].owner_same"]["value"]["value"] == 1
        control_slot = (2, 4)[component_index]
        assert readers[f"{prefix}.control.part.g7[{control_slot}].part.pid_same"]["value"]["value"] == 1
        assert readers[f"{prefix}.g7[{control_slot}].owner_same"]["value"]["value"] == 1
        for seed in ("target", "control"):
            roundtrip = f"{prefix}.{seed}.part.roundtrip"
            for field in ("owner_same", "same", "pid_same", "resolved_same", "resolved_pid_same"):
                assert readers[f"{roundtrip}.{field}"]["value"]["value"] == 1
            assert readers[f"{roundtrip}.state"]["value"]["value"] == 0
            matching_slot = slot if seed == "target" else control_slot
            assert readers[f"{roundtrip}.component.g7[{matching_slot}].same"]["value"]["value"] == 1
        assert readers[f"{prefix}.paper_points"]["status"] == "OBSERVED"
    assert any(left != right and left[:2] == right[:2] for left, right in native.pid_calls)
    assert set(native.qi_calls) == {("IEdge", "IUnknown"), ("IEntity", "IUnknown")}
    json.dumps(probe, allow_nan=False)
    assert native.imports == [] and not native.cropped
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert native.source.Tolerance.Type == 0
    assert native.annotation.endpoints is native.endpoints


@pytest.mark.parametrize("fault", ["curve", "edge_qi", "part_route", "source", "view_state", "persistent_id", "resolution"])
def test_identity_diagnostic_readers_fail_independently(projection_context_native, fault):
    native = projection_context_native

    class DiagnosticFailure(BaseException):
        hresult = -2147467262

    def fail(*_args):
        raise DiagnosticFailure(fault)

    if fault == "curve":
        native.raw_slots[0].GetCurve = fail
    elif fault == "edge_qi":
        query = native.raw_slots[0]._oleobj_.QueryInterface
        native.raw_slots[0]._oleobj_.QueryInterface = lambda iid, fallback: fail() if iid == "IEdge" else query(iid, fallback)
    elif fault == "part_route":
        native.extensions[0].GetCorrespondingEntity2 = fail
    elif fault == "source":
        native.drawing_components[0].Component.GetModelDoc2 = fail
    elif fault == "persistent_id":
        native.extensions[0].GetPersistReference3 = fail
    elif fault == "resolution":
        native.extensions[0].GetObjectByPersistReference3 = fail
    else:
        native.view.GetDisplayMode2 = fail
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    probe = native.failure_captures[0][2]["native_identity_probe"]
    readers = probe["readers"]
    assert "collector_error" not in probe
    assert readers["g7[0].owner"]["status"] == "OBSERVED"
    assert readers["g7[36].curve"]["status"] == "OBSERVED"
    assert readers["view.facetted_hlr"]["status"] == "OBSERVED"
    assert any(row["status"] == "ERROR" and row["error"] == f"DiagnosticFailure: {fault}" for row in readers.values())
    second = f"component[{native.drawing_components[1].Component.Name2}]"
    assert readers[f"{second}.control.part.roundtrip.pid_same"]["value"]["value"] == 1
    if fault in ("persistent_id", "resolution"):
        first = f"component[{native.drawing_components[0].Component.Name2}]"
        assert readers[f"{first}.control.part.roundtrip.same"]["value"]["value"] == 1
        assert readers[f"{first}.control.part.roundtrip.component.g7[2].same"]["status"] == "OBSERVED"
    if fault == "curve":
        assert readers["g7[0].body"]["status"] == "OBSERVED"
    if fault == "edge_qi":
        assert readers["g7[0].qi.IEdge"]["hresult"] == -2147467262
        assert readers["g7[0].qi.IEntity"]["status"] == "OBSERVED"
    assert native.g7_calls == [1]
    assert native.imports == [] and not native.cropped


@pytest.mark.parametrize("fault", ["snapshot", "formatter", "logging", "capture", "collector"])
def test_identity_capture_retains_original_baseexception_and_traceback(lever_tip_native, monkeypatch, fault):
    native = lever_tip_native
    captures = []

    class SecondaryFailure(BaseException):
        pass

    class OriginalFailure(BaseException):
        def __str__(self):
            raise SecondaryFailure("original formatter")

    def fail(*_args, **_kwargs):
        raise SecondaryFailure(fault)

    def capture(_adapter, _label, _message, **kwargs):
        captures.append(kwargs)
        if fault == "capture":
            fail()
        raise kwargs["exception"]

    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    if fault == "snapshot":
        monkeypatch.setattr(drawing, "_projection_polyline_snapshot", fail)
    elif fault == "formatter":
        monkeypatch.setattr(drawing, "_projection_error_text", fail)
    elif fault == "logging":
        monkeypatch.setattr(drawing._telemetry, "info", fail)
    try:
        raise OriginalFailure()
    except BaseException as original:
        traceback = original.__traceback__
        with pytest.raises(OriginalFailure) as raised:
            drawing._capture_projection_identity_failure(
                native.adapter, native.view, stage="uncropped physical boundaries",
                result=((), (0.0, -0.0, float("nan"))), exception=original,
                evidence={"rendered_model_edges": 0},
                components=SimpleNamespace(items=fail) if fault == "collector" else {},
                inventory={},
            )
        assert raised.value is original
        actual_traceback = raised.value.__traceback__
        while actual_traceback.tb_next is not None:
            actual_traceback = actual_traceback.tb_next
        assert actual_traceback is traceback
        assert len(captures) == 1 and captures[0]["exception"] is original
    probe = captures[0]["native_identity_probe"]
    assert probe["rendered_status"] == "DECODED"
    if fault == "collector":
        assert probe["collector_error"] == "SecondaryFailure: collector"
    if fault != "snapshot":
        import struct

        values = probe["readers"]["original_return"]["value"]["items"][1]["items"]
        assert [row["ieee754_le"] for row in values] == [
            struct.pack("<d", value).hex() for value in (0.0, -0.0, float("nan"))
        ]


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
    assert assembly.LEVER_ROD_Z - drawing.NOSE_R < flange_near_z
    assert drawing.ASSEMBLED_VIEW_CAPTIONS[stack.DRAWING_BACK_VIEW] == "VIEW FROM THE BACK"


def test_detail_proves_transformed_physical_edges_before_import_and_after_crop(lever_tip_native):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    physical = next(points for points in native.projected if len(points) == 4)
    assert physical[0] == pytest.approx((
        stack.THREADED_TIP_X / 1000, stack.LEVER_AXIS_Y / 1000, assembly.LEVER_ROD_Z / 1000,
    ))
    assert physical[2] == pytest.approx((
        stack.THREAD_FAR_FACE_X / 1000, stack.LEVER_AXIS_Y / 1000, assembly.LEVER_ROD_Z / 1000,
    ))
    assert physical[1][2] < physical[0][2]
    assert physical[3][2] == pytest.approx((assembly.LEVER_ROD_Z - drawing.NOSE_R) / 1000)
    assert native.events.index(("visible-edges", "mg-magnifying-lever-1")) < native.events.index(("crop",))
    previous = sum(event[0] == "component-transform" for event in native.events)
    settled()
    assert sum(event[0] == "component-transform" for event in native.events) == previous + 4
    assert native.annotation.source is native.source
    assert native.annotation.endpoints is native.endpoints


@pytest.mark.parametrize("failure", [
    "sketch-only", "hidden-component", "missing-component", "no-visible-edge",
    "wrong-boundary", "duplicate-boundary", "different-rendered-edge",
    "wrong-transform", "boundary-outside-crop", "inferred-crop", "nonfinite-projection",
])
def test_detail_refuses_missing_physical_interface_after_rebuild(lever_tip_native, failure):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    if failure == "sketch-only":
        native.rendered_edges.clear()
    elif failure == "hidden-component":
        native.drawing_components[0].Visible = False
    elif failure == "missing-component":
        native.visible_components.pop()
    elif failure == "no-visible-edge":
        native.component_edges["mg-magnifying-lever-1"].clear()
    elif failure == "wrong-boundary":
        curve = native.edges[1].GetCurve()
        curve.CircleParams = (*curve.CircleParams[:6], 0.003)  # not the outer far-face arc
    elif failure == "duplicate-boundary":
        native.component_edges["mg-magnifying-bracket-1"].append(native.edges[1])
    elif failure == "different-rendered-edge":
        native.rendered_edges[0] = object()
    elif failure == "wrong-transform":
        native.transform_dx = 0.001
    elif failure == "boundary-outside-crop":
        native.boundary_paper_dy = 0.030
    elif failure == "inferred-crop":
        native.fence[:] = _native_crop_fence((0.0975, 0.053), 0.0225)
    else:
        native.boundary_paper_dy = float("nan")
    moves = sum(event[0] in ("move", "caption-move") for event in native.events)
    with pytest.raises(RuntimeError):
        settled()
    assert sum(event[0] in ("move", "caption-move") for event in native.events) == moves
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert native.source.Tolerance.Type == 0
    assert native.annotation.endpoints is native.endpoints


def test_physical_reader_failure_still_collects_independent_visibility_and_ink(
    lever_tip_native, monkeypatch,
):
    native = lever_tip_native
    calls, messages = [], []
    monkeypatch.setattr(drawing._telemetry, "info", lambda text, **_kw: messages.append(text))

    def drawing_components():
        calls.append("drawing")
        raise RuntimeError("drawing component reader refused")

    def visible_components():
        calls.append("visible")
        return native.visible_components

    def polylines(cross):
        assert cross == 1
        calls.append("polylines")
        return native.rendered_edges, native.polyline * len(native.rendered_edges)

    native.view.GetVisibleDrawingComponents = drawing_components
    native.view.GetVisibleComponents = visible_components
    native.view.GetPolylines7 = polylines
    with pytest.raises(RuntimeError, match="drawing component reader refused") as caught:
        drawing._projection_model_ink(native.adapter, native.view, stage="independent reader regression")
    assert calls == ["polylines", "drawing", "visible"]
    packet = native.failure_captures[0][2]
    assert packet["exception"] is caught.value
    probe = packet["native_polyline_probe"]
    assert probe["component_readback"]["rendered_model_edges"] is None
    assert probe["component_readback"]["visible_component_count"] == 2
    assert probe["original_return"]["items"][0]["length"] == 4
    assert probe["numeric_records"]["numeric_record_count"] == 4


def test_back_caption_moves_once_using_whole_native_outline_not_crop(lever_tip_native):
    native = lever_tip_native
    before = tuple(native.back_extent)
    box = drawing._projection_note_box(native.back_caption)
    assert drawing.boxes_clear(box, drawing._projection_crop_box(native.view))
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


@pytest.mark.parametrize("code", [0, 2, True, None])
def test_physical_topology_identity_requires_native_integer_positive_control(
    lever_tip_native, monkeypatch, code,
):
    native = lever_tip_native
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda text, **_kw: messages.append(text))

    def identity(left, right):
        if left is native.edges[0] and right is native.edges[0]:
            return code
        return int(left is right)

    native.adapter.swApp.IsSame = identity
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._projection_model_ink(native.adapter, native.view, stage="identity control")
    assert f"'identity_self': {code!r}" in messages[-1]
    assert "'identity_rendered':" in messages[-1]
    assert "'assembly_points':" in messages[-1]


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
        drawing._projection_crop_box(native.view)


@pytest.fixture
def r26_native_polylines():
    """Real R26 numeric payload; opaque tokens stand in only for live COM slots."""
    import struct

    # Worker 9, SW 34.4.0, 2026-10-21T20:51:17Z, source bd160ae0f2994f5018c187279d41cd00f1fe7ab9.
    # capture.json SHA-256: 6f5f28a29ed45a89b8155b89bc6278990bea9c8bba6c4d8182bbcb74d2685ea5.
    # Exact IEEE-754 bytes from original_return.items[1], including all residual zeros.
    # Raw-byte SHA-256: db5e94d05e3503007f29ef3da528701d17f006c62f79fa9ecc61facdbc58eaef.
    # Original retval: 36 CDispatch slots. Their persisted reprs cannot recreate COM
    # identity: tokens test ordinal correspondence only, NEVER native IsSame proof.
    raw = bytes.fromhex(
        "000000000000f03f00000000000028409e6dc5feb27bb6bf24464b8638d6cb3fd4119ab9f3c5a73f9e6dc5feb27bb6bf"
        "505ee05a423ecc3fd4119ab9f3c5a73f9e6dc5feb27bb6bff82db6b12e6ecb3fd4119ab9f3c5a73f205d67cece72ffbc"
        "0000000000000000000000000000f03f00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf000000000000000000000000000024409e6dc5feb27bb6bf505ee05a423ecc3fd4119ab9f3c5a73f"
        "a2c7b19bddc2b6bfb02d7323fc37cc3fd4119ab9f3c5a73f807b9dc97201b7bfccc7ec38eb25cc3fd0119ab9f3c5a73f"
        "00e88424e62fb7bf38d295703d0acc3fd0119ab9f3c5a73f82d589669d48b7bf04acd17049e8cb3fd0119ab9f3c5a73f"
        "82d589669d48b7bf44e0c49b27c4cb3fd0119ab9f3c5a73ffee78424e62fb7bf0cba009c33a2cb3fd0119ab9f3c5a73f"
        "7e7b9dc97201b7bf78c4a9d38586cb3fd0119ab9f3c5a73fa0c7b19bddc2b6bf985e23e97474cb3fd4119ab9f3c5a73f"
        "9e6dc5feb27bb6bff82db6b12e6ecb3fd4119ab9f3c5a73f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "9e6dc5feb27bb6bff82db6b12e6ecb3fd4119ab9f3c5a73f10510e4e6210b03ff82db6b12e6ecb3fd8119ab9f3c5a73f"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000000040f8c4ca809543b33ff82db6b12e6ecb3fd8119ab9f3c5a73f"
        "d82555946588b33ff82db6b12e6ecb3fd8119ab9f3c5a73f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "d82555946588b33f505ee05a423ecc3fd8119ab9f3c5a73ff8c4ca809543b33f505ee05a423ecc3fd8119ab9f3c5a73f"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf0000000000000000000000000000004010510e4e6210b03f505ee05a423ecc3fd8119ab9f3c5a73f"
        "9e6dc5feb27bb6bf505ee05a423ecc3fd4119ab9f3c5a73f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "d82555946588b33ff82db6b12e6ecb3fdc119ab9f3c5a73f467341068195b33fb054ac6abc74cb3fd8119ab9f3c5a73f"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000000040467341068195b33f9837eaa1b437cc3fd8119ab9f3c5a73f"
        "d82555946588b33f505ee05a423ecc3fdc119ab9f3c5a73f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "0f510e4e6210b03f5cc5652eff21cb3fd4119ab9f3c5a73ff6c4ca809543b33f5cc5652eff21cb3fd4119ab9f3c5a73f"
        "000000000000f03f00000000000028400f510e4e6210b03f24464b8638d6cb3fd4119ab9f3c5a73f0f510e4e6210b03f"
        "5cc5652eff21cb3fd4119ab9f3c5a73f0f510e4e6210b03fecc630de718acc3fd4119ab9f3c5a73f000000000000f0bf"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000002a400f510e4e6210b03f5cc5652eff21cb3fd4119ab9f3c5a73f"
        "0f510e4e6210b03f885de9452328cb3fa00e1b9e8880a83f0f510e4e6210b03f0888c669243acb3f64136569662ea93f"
        "0f510e4e6210b03fbc9c097fc856cb3f70b7a0d6b3c3a93f0f510e4e6210b03fc08558da1b7ccb3f400aad2b4436aa3f"
        "0f510e4e6210b03ff0062b4d93a7cb3f3cb421bb487eaa3f0f510e4e6210b03f24464b8638d6cb3ff4143019d996aa3f"
        "0f510e4e6210b03f58856bbfdd04cc3f3cb421bb487eaa3f0f510e4e6210b03f88063e325530cc3f3c0aad2b4436aa3f"
        "0f510e4e6210b03f8cef8c8da855cc3f6cb7a0d6b3c3a93f0f510e4e6210b03f4004d0a24c72cc3f60136569662ea93f"
        "0f510e4e6210b03fc02eadc64d84cc3f9c0e1b9e8880a83f0f510e4e6210b03fecc630de718acc3fd4119ab9f3c5a73f"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf000000000000000000000000000000400f510e4e6210b03fecc630de718acc3fd4119ab9f3c5a73f"
        "f6c4ca809543b33fecc630de718acc3fd4119ab9f3c5a73f000000000000f03f0000000000002840f6c4ca809543b33f"
        "24464b8638d6cb3fd4119ab9f3c5a73ff6c4ca809543b33f5cc5652eff21cb3fd4119ab9f3c5a73ff6c4ca809543b33f"
        "ecc630de718acc3fd4119ab9f3c5a73f000000000000f0bf000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000002a40"
        "f6c4ca809543b33f5cc5652eff21cb3fd4119ab9f3c5a73ff6c4ca809543b33f885de9452328cb3fa00e1b9e8880a83f"
        "f6c4ca809543b33f0888c669243acb3f64136569662ea93ff6c4ca809543b33fbc9c097fc856cb3f70b7a0d6b3c3a93f"
        "f6c4ca809543b33fc08558da1b7ccb3f400aad2b4436aa3ff6c4ca809543b33ff0062b4d93a7cb3f3cb421bb487eaa3f"
        "f6c4ca809543b33f24464b8638d6cb3ff4143019d996aa3ff6c4ca809543b33f58856bbfdd04cc3f3cb421bb487eaa3f"
        "f6c4ca809543b33f88063e325530cc3f3c0aad2b4436aa3ff6c4ca809543b33f8cef8c8da855cc3f6cb7a0d6b3c3a93f"
        "f6c4ca809543b33f4004d0a24c72cc3f60136569662ea93ff6c4ca809543b33fc02eadc64d84cc3f9c0e1b9e8880a83f"
        "f6c4ca809543b33fecc630de718acc3fd4119ab9f3c5a73f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "69f1d24d6210b03fc03f1a05a392cc3fb4084cfc3401aabfa0b69dcef753b33fc03f1a05a392cc3fb4084cfc3401aabf"
        "0000000000000000000000000000314000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000002440f6c4ca809543b33fecc630de718acc3f6025a66070e0a9bf"
        "bad25739d543b33fcc4d77ba918acc3fb263450b21e6a9bfe7f058739244b33fe4dc7757f08acc3ff6675073a5eba9bf"
        "5c5ceb6ec745b33fa01241d58a8bcc3f0a1779aed2f0a9bf1090a8c86a47b33f78ac1f825c8ccc3f96aa877880f5a9bf"
        "06f4acc26f49b33f74de21ff5e8dcc3f8072906c8af9a9bfcb3db4a7c64bb33f5483a5718a8ecc3fe8d90a20d1fca9bf"
        "569548455d4eb33f1caf6fc0d58fcc3fd2b02f173bffa9bf77174e791f51b33f2c7072da3691cc3f2aed318bb500aabf"
        "a0b69dcef753b33fc03f1a05a392cc3fb4084cfc3401aabf000000000000f03f00000000000028400f510e4e6210b03f"
        "c03f1a05a392cc3f6025a66070e0a9bf0f510e4e6210b03fecc630de718acc3f6025a66070e0a9bf69f1d24d6210b03f"
        "c03f1a05a392cc3fb4084cfc3401aabf000000000000f03f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000002240"
        "0f510e4e6210b03fecc630de718acc3f6025a66070e0a9bf0f510e4e6210b03fccba032a9a8acc3f5ae8ece9d4e6a9bf"
        "0f510e4e6210b03fa02a0e81118bcc3fa0f70f8ffaeca9bf0f510e4e6210b03ff0e3404dd38bcc3f88c5a3d6a4f2a9bf"
        "0f510e4e6210b03ff43f0a1cd88ccc3f9424e6049cf7a9bf0f510e4e6210b03fb8d79ae7158ecc3f9a940b40affba9bf"
        "0f510e4e6210b03f30cb7f79808fcc3fe479d670b6fea9bf0f510e4e6210b03f008fc8e20991cc3f303900cd9300aabf"
        "69f1d24d6210b03fc03f1a05a392cc3fb4084cfc3401aabf000000000000000000000000000031400000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000002240"
        "f6c4ca809543b33f5cc5652eff21cb3f6025a66070e0a9bfb6ac7018e643b33f7cd192e2d621cb3f5ce8ece9d4e6a9bf"
        "5c8c85c6d444b33fac61888b5f21cb3fa2f70f8ffaeca9bf02ffea5e5846b33f58a855bf9d20cb3f8ac5a3d6a4f2a9bf"
        "04b77dfc6148b33f544c8cf0981fcb3f9824e6049cf7a9bf8be69e93dd4ab33f94b4fb245b1ecb3f9e940b40affba9bf"
        "7fcd68b7b24db33f18c11693f01ccb3fe879d670b6fea9bf2255fa89c550b33f48fdcd29671bcb3f343900cd9300aabf"
        "a0b69dcef753b33f884c7c07ce19cb3fb4084cfc3401aabf000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "a0b69dcef753b33f884c7c07ce19cb3fb4084cfc3401aabf69f1d24d6210b03f884c7c07ce19cb3fb4084cfc3401aabf"
        "000000000000f03f00000000000028400f510e4e6210b03f884c7c07ce19cb3f6025a66070e0a9bf69f1d24d6210b03f"
        "884c7c07ce19cb3fb4084cfc3401aabf0f510e4e6210b03f5cc5652eff21cb3f6025a66070e0a9bf000000000000f03f"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf0000000000000000000000000000224069f1d24d6210b03f884c7c07ce19cb3fb4084cfc3401aabf"
        "7815d44d6210b03f48fdcd29671bcb3f343900cd9300aabf6a76d74d6210b03f18c11693f01ccb3fe879d670b6fea9bf"
        "04f3dc4d6210b03f94b4fb245b1ecb3f9e940b40affba9bf4855e44d6210b03f544c8cf0981fcb3f9824e6049cf7a9bf"
        "9654ed4d6210b03f58a855bf9d20cb3f8ac5a3d6a4f2a9bf6898f74d6210b03fac61888b5f21cb3fa2f70f8ffaeca9bf"
        "c1bb024e6210b03f7cd192e2d621cb3f5ce8ece9d4e6a9bf0f510e4e6210b03f5cc5652eff21cb3f6025a66070e0a9bf"
        "000000000000f03f00000000000028408ef753e3a59bbc3fa4fd8b081b9ecc3fb4084cfc3401aabf38e9263108acbc3f"
        "a4fd8b081b9ecc3fb4084cfc3401aabf8cf753e3a59bbc3f7876752f4ca6cc3fb4084cfc3401aabf0000000000000000"
        "0000000000000000000000000000f03f00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf0000000000000000000000000000224038e9263108acbc3fa4fd8b081b9ecc3fb4084cfc3401aabf"
        "77018199b7abbc3f64aedd2ab49fcc3fb4084cfc3401aabfd2216cebc8aabc3f347226943da1cc3fb4084cfc3401aabf"
        "2caf065345a9bc3fb0650b26a8a2cc3fb4084cfc3401aabf29f773b53ba7bc3f70fd9bf1e5a3cc3fb4084cfc3401aabf"
        "a2c7521ec0a4bc3f745965c0eaa4cc3fb4084cfc3401aabfaee088faeaa1bc3fc812988caca5cc3fb4084cfc3401aabf"
        "0a59f727d89ebc3f9882a2e323a6cc3fb4084cfc3401aabf8cf753e3a59bbc3f7876752f4ca6cc3fb4084cfc3401aabf"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf0000000000000000000000000000004038e9263108acbc3fa4fd8b081b9ecc3fb4084cfc3401aabf"
        "38e9263108acbc3fa48e0a04560ecb3fb4084cfc3401aabf000000000000f03f00000000000028408ef753e3a59bbc3f"
        "a48e0a04560ecb3fb4084cfc3401aabf8cf753e3a59bbc3fd01521dd2406cb3fb4084cfc3401aabf38e9263108acbc3f"
        "a48e0a04560ecb3fb4084cfc3401aabf00000000000000000000000000000000000000000000f03f0000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000002240"
        "8cf753e3a59bbc3fd01521dd2406cb3fb4084cfc3401aabf0a59f727d89ebc3fb009f4284d06cb3fb4084cfc3401aabf"
        "ade088faeaa1bc3f8479fe7fc406cb3fb4084cfc3401aabfa1c7521ec0a4bc3fd432314c8607cb3fb4084cfc3401aabf"
        "27f773b53ba7bc3fd88efa1a8b08cb3fb4084cfc3401aabf2aaf065345a9bc3f9c268be6c809cb3fb4084cfc3401aabf"
        "d0216cebc8aabc3f141a7078330bcb3fb4084cfc3401aabf75018199b7abbc3fe4ddb8e1bc0ccb3fb4084cfc3401aabf"
        "38e9263108acbc3fa48e0a04560ecb3fb4084cfc3401aabf000000000000f03f00000000000028409b4603780b24b83f"
        "24464b8638d6cb3fb4084cfc3401aabf96e5a5acf078b83f24464b8638d6cb3fb4084cfc3401aabf96e5a5acf078b83f"
        "24464b8638d6cb3fb4084cfc3401aabf00000000000000000000000000000000000000000000f03f0000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000003140"
        "96e5a5acf078b83f24464b8638d6cb3fb4084cfc3401aabf439b27557a72b83fc86852fe76e6cb3fb4084cfc3401aabf"
        "0ae1752a1360b83f5c93845f3cf4cb3fb4084cfc3401aabfe68b11688844b83f7870ddf46ffdcb3fb4084cfc3401aabf"
        "9b4603780b24b83fa0959c20ab00cc3fb4084cfc3401aabf5001f5878e03b83f7870ddf46ffdcb3fb4084cfc3401aabf"
        "2cac90c503e8b73f5c93845f3cf4cb3fb4084cfc3401aabff3f1de9a9cd5b73fc86852fe76e6cb3fb4084cfc3401aabf"
        "a0a7604326cfb73f24464b8638d6cb3fb4084cfc3401aabff4f1de9a9cd5b73f8023440efac5cb3fb4084cfc3401aabf"
        "2dac90c503e8b73fecf811ad34b8cb3fb4084cfc3401aabf5101f5878e03b83fd01bb91701afcb3fb4084cfc3401aabf"
        "9c4603780b24b83fa8f6f9ebc5abcb3fb4084cfc3401aabfe88b11688844b83fd01bb91701afcb3fb4084cfc3401aabf"
        "0ae1752a1360b83fecf811ad34b8cb3fb4084cfc3401aabf449b27557a72b83f8023440efac5cb3fb4084cfc3401aabf"
        "96e5a5acf078b83f24464b8638d6cb3fb4084cfc3401aabf000000000000f03f000000000000284098cef753e3a5bb3f"
        "24464b8638d6cb3fb4084cfc3401aabf936d9a88c8fabb3f24464b8638d6cb3fb4084cfc3401aabf936d9a88c8fabb3f"
        "24464b8638d6cb3fb4084cfc3401aabf00000000000000000000000000000000000000000000f03f0000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000003140"
        "936d9a88c8fabb3f24464b8638d6cb3fb4084cfc3401aabf40231c3152f4bb3fc86852fe76e6cb3fb4084cfc3401aabf"
        "06696a06ebe1bb3f5c93845f3cf4cb3fb4084cfc3401aabfe313064460c6bb3f7870ddf46ffdcb3fb4084cfc3401aabf"
        "98cef753e3a5bb3fa0959c20ab00cc3fb4084cfc3401aabf4c89e9636685bb3f7870ddf46ffdcb3fb4084cfc3401aabf"
        "293485a1db69bb3f5c93845f3cf4cb3fb4084cfc3401aabff079d3767457bb3fc86852fe76e6cb3fb4084cfc3401aabf"
        "9d2f551ffe50bb3f24464b8638d6cb3fb4084cfc3401aabff079d3767457bb3f8023440efac5cb3fb4084cfc3401aabf"
        "2a3485a1db69bb3fecf811ad34b8cb3fb4084cfc3401aabf4e89e9636685bb3fd01bb91701afcb3fb4084cfc3401aabf"
        "99cef753e3a5bb3fa8f6f9ebc5abcb3fb4084cfc3401aabfe413064460c6bb3fd01bb91701afcb3fb4084cfc3401aabf"
        "07696a06ebe1bb3fecf811ad34b8cb3fb4084cfc3401aabf40231c3152f4bb3f8023440efac5cb3fb4084cfc3401aabf"
        "936d9a88c8fabb3f24464b8638d6cb3fb4084cfc3401aabf000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "b942e19bc420b03f7876752f4ca6cc3fb4084cfc3401aabf8cf753e3a59bbc3f7876752f4ca6cc3fb4084cfc3401aabf"
        "000000000000f03f0000000000002840b942e19bc420b03fa48e0a04560ecb3fb4084cfc3401aabf69f1d24d6210b03f"
        "a48e0a04560ecb3fb4084cfc3401aabfb942e19bc420b03fd01521dd2406cb3fb4084cfc3401aabf0000000000000000"
        "0000000000000000000000000000f03f00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf0000000000000000000000000000224069f1d24d6210b03fa48e0a04560ecb3fb4084cfc3401aabf"
        "38fd79e5b210b03f4013b3e1bc0ccb3fb4084cfc3401aabfd03d9293a111b03fc0bd6478330bcb3fb4084cfc3401aabf"
        "0e2dfd2b2513b03f5ca87ae6c809cb3fb4084cfc3401aabf574797c92e15b03ff490e51a8b08cb3fb4084cfc3401aabf"
        "2b76c160aa17b03fd083184c8607cb3fb4084cfc3401aabff0a095847f1ab03f300ce37fc406cb3fb4084cfc3401aabf"
        "ee4b3257921db03fe4ebd6284d06cb3fb4084cfc3401aabfb942e19bc420b03fd01521dd2406cb3fb4084cfc3401aabf"
        "000000000000f03f0000000000002840b942e19bc420b03fa4fd8b081b9ecc3fb4084cfc3401aabfb942e19bc420b03f"
        "7876752f4ca6cc3fb4084cfc3401aabf69f1d24d6210b03fa4fd8b081b9ecc3fb4084cfc3401aabf0000000000000000"
        "0000000000000000000000000000f03f00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000002240b942e19bc420b03f7876752f4ca6cc3fb4084cfc3401aabf"
        "3ce13d57921db03f9882a2e323a6cc3fb4084cfc3401aabf9859ac847f1ab03fc412988caca5cc3fb4084cfc3401aabf"
        "a572e260aa17b03f745965c0eaa4cc3fb4084cfc3401aabf1f43c1c92e15b03f70fd9bf1e5a3cc3fb4084cfc3401aabf"
        "1c8b2e2c2513b03fac650b26a8a2cc3fb4084cfc3401aabf7618c993a111b03f347226943da1cc3fb4084cfc3401aabf"
        "d138b4e5b210b03f64aedd2ab49fcc3fb4084cfc3401aabf69f1d24d6210b03fa4fd8b081b9ecc3fb4084cfc3401aabf"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000000040b942e19bc420b03fd01521dd2406cb3fb4084cfc3401aabf"
        "8cf753e3a59bbc3fd01521dd2406cb3fb4084cfc3401aabf000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "69f1d24d6210b03f884c7c07ce19cb3fb4084cfc3401aabf69f1d24d6210b03fa48e0a04560ecb3fb4084cfc3401aabf"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf0000000000000000000000000000004069f1d24d6210b03fa4fd8b081b9ecc3fb4084cfc3401aabf"
        "69f1d24d6210b03fc03f1a05a392cc3fb4084cfc3401aabf000000000000f03f0000000000002840d82555946588b33f"
        "24464b8638d6cb3fd8119ab9f3c5a73fd82555946588b33f24464b8638d6cb3f8072ee0b1b66a93fd82555946588b33f"
        "505ee05a423ecc3fd8119ab9f3c5a73f000000000000f0bf0000000000000000075c143326a6a1bc0000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000001840"
        "d82555946588b33f24464b8638d6cb3f8072ee0b1b66a93fd82555946588b33f2473c1d4cdf9cb3ffcaf392e024da93f"
        "d82555946588b33f144db76b1819cc3f78182084be04a93fd82555946588b33f54032b195230cc3f2c42c4620796a83f"
        "d82555946588b33f147a2dbaad3ccc3f58a9b363370ea83fd82555946588b33f505ee05a423ecc3fd8119ab9f3c5a73f"
        "000000000000f03f0000000000002840d82555946588b33f24464b8638d6cb3fd8119ab9f3c5a73fd82555946588b33f"
        "f82db6b12e6ecb3fd8119ab9f3c5a73fd82555946588b33f24464b8638d6cb3f8072ee0b1b66a93f000000000000f0bf"
        "0000000000000000075c143326a6a1bc00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000001840d82555946588b33ff82db6b12e6ecb3fd8119ab9f3c5a73f"
        "d82555946588b33f34126952c36fcb3f60a9b363370ea83fd82555946588b33ff4886bf31e7ccb3f3042c4620796a83f"
        "d82555946588b33f343fdfa05893cb3f7c182084be04a93fd82555946588b33f2419d537a3b2cb3ffcaf392e024da93f"
        "d82555946588b33f24464b8638d6cb3f8072ee0b1b66a93f000000000000f03f0000000000002840467341068195b33f"
        "24464b8638d6cb3fd8119ab9f3c5a73f467341068195b33f24464b8638d6cb3fa4d71528e44ba93f467341068195b33f"
        "9837eaa1b437cc3fd8119ab9f3c5a73f000000000000f0bf0000000000000000075c143326a6a1bc0000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000001840"
        "467341068195b33f24464b8638d6cb3fa4d71528e44ba93f467341068195b33fd8b0240490f7cb3fa047b9016034a93f"
        "467341068195b33f48086400e214cc3f8c1f15ada9f0a83f467341068195b33ff073e325a52acc3fbcf4d7f0eb88a83f"
        "467341068195b33ffc723d7e3936cc3fec393e0eaa09a83f467341068195b33f9837eaa1b437cc3fd8119ab9f3c5a73f"
        "000000000000f03f0000000000002840467341068195b33f24464b8638d6cb3fd8119ab9f3c5a73f467341068195b33f"
        "b054ac6abc74cb3fd8119ab9f3c5a73f467341068195b33f24464b8638d6cb3fa4d71528e44ba93f000000000000f0bf"
        "0000000000000000075c143326a6a1bc00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000001840467341068195b33fb054ac6abc74cb3fd8119ab9f3c5a73f"
        "467341068195b33f4c19598e3776cb3ff0393e0eaa09a83f467341068195b33f5818b3e6cb81cb3fc4f4d7f0eb88a83f"
        "467341068195b33f0084320c8f97cb3f901f15ada9f0a83f467341068195b33f74db7108e1b4cb3fa447b9016034a93f"
        "467341068195b33f24464b8638d6cb3fa4d71528e44ba93f000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000000040"
        "a0b69dcef753b33fc03f1a05a392cc3fb4084cfc3401aabfa0b69dcef753b33f505ee05a423ecc3fb4084cfc3401aabf"
        "0000000000000000000000000000000000000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf00000000000000000000000000000040a0b69dcef753b33ff82db6b12e6ecb3fb4084cfc3401aabf"
        "a0b69dcef753b33f884c7c07ce19cb3fb4084cfc3401aabf000000000000f03f00000000000028409e6dc5feb27bb6bf"
        "24464b8638d6cb3fd4119ab9f3c5a73f9e6dc5feb27bb6bf24464b8638d6cb3f8072ee0b1b66a93f9e6dc5feb27bb6bf"
        "505ee05a423ecc3fd4119ab9f3c5a73f000000000000f0bf0000000000000000075c143326a6a1bc0000000000000000"
        "0000000000000000000000000000f0bf0000000000000040000000000000f0bf00000000000000000000000000001840"
        "9e6dc5feb27bb6bf24464b8638d6cb3f8072ee0b1b66a93f9e6dc5feb27bb6bf2473c1d4cdf9cb3ffcaf392e024da93f"
        "9e6dc5feb27bb6bf144db76b1819cc3f78182084be04a93f9e6dc5feb27bb6bf54032b195230cc3f2842c4620796a83f"
        "9e6dc5feb27bb6bf147a2dbaad3ccc3f54a9b363370ea83f9e6dc5feb27bb6bf505ee05a423ecc3fd4119ab9f3c5a73f"
        "000000000000f03f00000000000028409e6dc5feb27bb6bf24464b8638d6cb3fd4119ab9f3c5a73f9e6dc5feb27bb6bf"
        "f82db6b12e6ecb3fd4119ab9f3c5a73f9e6dc5feb27bb6bf24464b8638d6cb3f8072ee0b1b66a93f000000000000f0bf"
        "0000000000000000075c143326a6a1bc00000000000000000000000000000000000000000000f0bf0000000000000040"
        "000000000000f0bf000000000000000000000000000018409e6dc5feb27bb6bff82db6b12e6ecb3fd4119ab9f3c5a73f"
        "9e6dc5feb27bb6bf34126952c36fcb3f5ca9b363370ea83f9e6dc5feb27bb6bff4886bf31e7ccb3f3042c4620796a83f"
        "9e6dc5feb27bb6bf343fdfa05893cb3f7c182084be04a93f9e6dc5feb27bb6bf2419d537a3b2cb3ffcaf392e024da93f"
        "9e6dc5feb27bb6bf24464b8638d6cb3f8072ee0b1b66a93f000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
        "0000000000000000"
    )
    return SimpleNamespace(
        data=struct.unpack("<1201d", raw),
        edges=tuple(object() for _ in range(36)),
        starts=(
            0, 51, 66, 81, 96, 111, 126, 141, 156, 216, 231, 291,
            306, 345, 393, 429, 444, 492, 540, 555, 603, 675, 747, 762,
            810, 858, 873, 888, 903, 942, 981, 1020, 1059, 1074, 1089, 1128,
        ),
        end=1167,
    )


def test_r26_native_payload_preserves_all_edge_slot_correspondence(r26_native_polylines):
    native = r26_native_polylines
    decoded = drawing._projection_rendered_edges((native.edges, native.data))
    assert len(decoded) == 36
    assert all(actual is expected for actual, expected in zip(decoded, native.edges, strict=True))


@pytest.mark.parametrize("ignored_size", [1.0, 7.0, 1024.0])
def test_type_zero_ignores_geometry_size_field_generally(r26_native_polylines, ignored_size):
    native = r26_native_polylines
    data = list(native.data)
    for start in native.starts:
        if data[start] == 0:
            data[start + 1] = ignored_size
    assert drawing._projection_rendered_edges((native.edges, data)) == native.edges


@pytest.mark.parametrize("size", [0.0, 11.0, 17.0, float("nan")])
def test_arc_geometry_still_requires_documented_twelve_doubles(r26_native_polylines, size):
    native = r26_native_polylines
    data = list(native.data)
    data[1] = size
    with pytest.raises(RuntimeError, match="invalid geometry header.*primitive 0, offset 0"):
        drawing._projection_rendered_edges((native.edges, data))


@pytest.mark.parametrize("value", [-1.0, 0.5, float("nan"), float("inf"), object()])
def test_ignored_geometry_size_still_requires_nonnegative_integer_field(r26_native_polylines, value):
    native = r26_native_polylines
    data = list(native.data)
    data[307] = value
    with pytest.raises(RuntimeError, match="primitive 12, offset 306"):
        drawing._projection_rendered_edges((native.edges, data))


@pytest.mark.parametrize("count", [0.0, 1.0, -1.0, 2.5, float("nan"), float("inf"), "unreadable"])
def test_type_zero_requires_an_integral_count_of_at_least_two_points(r26_native_polylines, count):
    native = r26_native_polylines
    data = list(native.data)
    data[314] = count
    with pytest.raises(RuntimeError, match="point count.*primitive 12, offset 306"):
        drawing._projection_rendered_edges((native.edges, data))


def test_r26_native_payload_rejects_every_incomplete_active_prefix(r26_native_polylines):
    native = r26_native_polylines
    ends = (*native.starts[1:], native.end)
    for cut in range(native.end):
        index = next(index for index, end in enumerate(ends) if cut < end)
        with pytest.raises(RuntimeError, match=rf"primitive {index}, offset {native.starts[index]}"):
            drawing._projection_rendered_edges((native.edges, native.data[:cut]))


@pytest.mark.parametrize("padding_length", [0, 1, 34, 128])
def test_zero_residual_data_never_becomes_another_primitive(r26_native_polylines, padding_length):
    native = r26_native_polylines
    data = (*native.data[:native.end], *((0.0,) * padding_length))
    assert drawing._projection_rendered_edges((native.edges, data)) == native.edges


@pytest.mark.parametrize("offset", [1167, 1184, 1200])
@pytest.mark.parametrize("value", [1.0, -1.0, float("nan"), float("inf"), "unreadable"])
def test_nonzero_or_unreadable_residual_data_is_not_silently_dropped(
    r26_native_polylines, offset, value,
):
    native = r26_native_polylines
    data = list(native.data)
    data[offset] = value
    with pytest.raises(RuntimeError, match="primitive 36, offset 1167"):
        drawing._projection_rendered_edges((native.edges, data))


def test_r26_native_payload_requires_every_edge_aligned_record(r26_native_polylines):
    native = r26_native_polylines
    with pytest.raises(RuntimeError, match="primitive 35, offset 1128"):
        drawing._projection_rendered_edges((native.edges[:-1], native.data))
    with pytest.raises(RuntimeError, match="primitive 36, offset 1167"):
        drawing._projection_rendered_edges(((*native.edges, object()), native.data[:native.end]))
    with pytest.raises(RuntimeError, match="primitive 36, offset 1167"):
        drawing._projection_rendered_edges(((*native.edges, object()), native.data))


@pytest.mark.parametrize("silhouette_index", [0, 12, 35])
def test_null_silhouette_slots_preserve_later_native_record_alignment(
    r26_native_polylines, silhouette_index,
):
    native = r26_native_polylines
    edges = list(native.edges)
    edges[silhouette_index] = None
    expected = tuple(edge for index, edge in enumerate(native.edges) if index != silhouette_index)
    assert drawing._projection_rendered_edges((edges, native.data)) == expected


def test_nonzero_ignored_field_does_not_make_degenerate_points_into_ink(r26_native_polylines):
    native = r26_native_polylines
    data = list(native.data)
    # Actual primitive 12: type 0, ignored field 17, ten XYZ triplets at 315:345.
    data[315:345] = data[315:318] * 10
    expected = (*native.edges[:12], *native.edges[13:])
    assert drawing._projection_rendered_edges((native.edges, data)) == expected


def test_real_numeric_payload_cannot_replace_native_physical_edge_identity(
    lever_tip_native, r26_native_polylines,
):
    native = lever_tip_native
    captured = r26_native_polylines
    calls = []

    def polylines(cross):
        calls.append(cross)
        # These offline ordinal tokens deliberately do NOT identify either live
        # physical target in lever_tip_native. Numeric success cannot prove it.
        return captured.edges, captured.data

    native.view.GetPolylines7 = polylines
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert calls == [1]
    assert len(native.failure_captures) == 1
    probe = native.failure_captures[0][2]["native_identity_probe"]
    assert probe["rendered_status"] == "DECODED"
    assert probe["decoded_model_edge_count"] == 36
    assert probe["source_import_and_crop"] == "NOT_REACHED"
    assert native.imports == [] and not native.cropped
    assert native.source.SystemValue == pytest.approx(0.00125)
    assert native.source.Tolerance.Type == 0
    assert native.annotation.endpoints is native.endpoints


def test_truncated_real_native_payload_keeps_original_failure_and_complete_snapshot(
    lever_tip_native, r26_native_polylines,
):
    import struct

    native = lever_tip_native
    captured = r26_native_polylines
    payload = captured.data[:captured.end - 1]
    calls = []

    def polylines(cross):
        calls.append(cross)
        return captured.edges, payload

    native.view.GetPolylines7 = polylines
    with pytest.raises(RuntimeError, match="primitive 35, offset 1128") as caught:
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert calls == [1]
    assert len(native.failure_captures) == 1
    _label, message, capture = native.failure_captures[0]
    assert capture["exception"] is caught.value and message == str(caught.value)
    assert capture["sheet_png"] is True
    probe = capture["native_polyline_probe"]
    assert probe["return_observed"] is True
    assert probe["rendered_status"] == "UNAVAILABLE"
    assert probe["component_readback"]["rendered_model_edges"] is None
    edge_slots, buffer = probe["original_return"]["items"]
    assert edge_slots["length"] == 36
    assert [slot["python_id"] for slot in edge_slots["items"]] == [id(edge) for edge in captured.edges]
    assert buffer["length"] == len(payload)
    assert [bytes.fromhex(item["ieee754_le"]) for item in buffer["items"]] == [
        struct.pack("<d", value) for value in payload
    ]
    assert probe["view_state"]["orientation"]["value"] == drawing.LEVER_TIP.orientation
    assert probe["reader_errors"] == {}
    assert native.imports == [] and not native.cropped


def test_native_arc_keeps_analytic_ink_without_tessellation_points(r26_native_polylines):
    native = r26_native_polylines
    # First captured arc: header, twelve geometric doubles, six style/layer
    # fields, then its point count. Retain actual centre/start/end/normal.
    arc = list(native.data[:21])
    arc[20] = 0.0
    assert drawing._projection_rendered_edges(((native.edges[0],), arc)) == (native.edges[0],)
    arc[5:8] = arc[2:5]
    assert drawing._projection_rendered_edges(((native.edges[0],), arc)) == ()


def test_real_native_late_record_still_rejects_nonfinite_geometry(r26_native_polylines):
    native = r26_native_polylines
    data = list(native.data)
    data[1149] = float("nan")
    with pytest.raises(RuntimeError, match="non-finite model ink.*primitive 35, offset 1128"):
        drawing._projection_rendered_edges((native.edges, data))


@pytest.mark.parametrize("failure", ["missing-out", "truncated", "cardinality", "nonfinite"])
def test_model_polyline_reader_refuses_unproven_ink(lever_tip_native, failure):
    native = lever_tip_native
    result = (native.rendered_edges, native.polyline * 2)
    if failure == "missing-out":
        result = (native.rendered_edges,)
    elif failure == "truncated":
        result = (native.rendered_edges, native.polyline[:-1])
    elif failure == "cardinality":
        result = (native.rendered_edges, native.polyline)
    else:
        data = list(native.polyline * 2)
        data[9] = float("nan")
        result = (native.rendered_edges, data)
    with pytest.raises(RuntimeError, match="GetPolylines7"):
        drawing._projection_rendered_edges(result)


def test_failure_only_polyline_readers_match_generated_view_abi():
    """Read wrapper source as data: never import a generated COM interface."""
    import ast
    import re

    wrapper = (
        Path(__file__).resolve().parents[2] / "SolidworksMCP-python" / "src"
        / "solidworks_mcp" / "adapters" / "_generated" / "sldworks_2026.py"
    ).read_text(encoding="utf-8")
    start = re.search(r"^class IView\(", wrapper, re.M)
    assert start is not None
    following = re.compile(r"^class ", re.M).search(wrapper, start.end())
    (view,) = ast.parse(wrapper[start.start():following.start() if following else None]).body
    methods = {node.name: node for node in view.body if isinstance(node, ast.FunctionDef)}
    expected = {
        "GetPolylines7": (329, 1, (12, 0), ((2, 1), (16396, 2))),
        "GetPolyLineCount5": (228, 1, (3, 0), ((2, 1), (16387, 2))),
        "GetXform": (4, 1, (12, 0), ()),
    }
    for name, header in expected.items():
        method = methods[name]
        calls = [
            node for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_ApplyTypes_"
        ]
        assert len(calls) == 1
        assert tuple(ast.literal_eval(node) for node in calls[0].args[:4]) == header
        if name == "GetXform":
            assert [arg.arg for arg in method.args.args] == ["self"]
        else:
            assert [arg.arg for arg in method.args.args] == [
                "self", "CrossHatchOption", "Polylines" if name == "GetPolylines7" else "PointCount",
            ]
            assert ast.unparse(method.args.defaults[-1]) == "pythoncom.Missing"


@pytest.fixture
def r29_polyline_capture():
    """Actual bytes/NULL placement only; cropped native identities were NOT read."""
    import json
    import struct

    actual = json.loads(
        (Path(__file__).parent / "fixtures" / "mg_r29_projection_polylines.json").read_text(encoding="utf-8")
    )
    probe = actual["native_polyline_probe"]
    slots, values = probe["original_return"]["items"]
    data = tuple(struct.unpack("<d", bytes.fromhex(row["ieee754_le"]))[0] for row in values["items"])
    return SimpleNamespace(actual=actual, probe=probe, slots=slots["items"], values=values["items"], data=data)


def test_r29_full_buffer_diagnostic_does_not_authorize_twelve_records_for_eleven_slots(r29_polyline_capture):
    import struct

    native = r29_polyline_capture
    assert len(native.data) == 2370 and len(native.slots) == 11
    assert [i for i, row in enumerate(native.slots) if row["type"] == "builtins.NoneType"] == [0, 1, 2, 3]
    assert all(struct.pack("<d", v).hex() == row["ieee754_le"] for v, row in zip(native.data, native.values, strict=True))
    assert native.probe["component_readback"]["rendered_model_edges"] is None
    assert native.probe["stage"] == "settled drawing"
    records = drawing._projection_diagnostic_records(native.data)
    assert records["association"] == "UNAVAILABLE"
    assert records["numeric_record_count"] == 12
    assert records["consumed_values"] == 2370 and records["zero_residual_values"] == 0
    assert [row["offset"] for row in records["records"]] == [
        0, 15, 30, 45, 60, 2190, 2232, 2259, 2286, 2313, 2340, 2355,
    ]
    assert [row["point_count"] for row in records["records"]] == [2, 2, 2, 2, 707, 11, 6, 6, 6, 6, 2, 2]
    assert all(row["type"] == 0 and row["geom_data_size"] == 0 for row in records["records"])
    # These sentinels test array cardinality, not actual native model identity.
    slots = tuple(None if row["type"] == "builtins.NoneType" else object() for row in native.slots)
    with pytest.raises(RuntimeError, match="nonzero residual data / unmatched primitive at primitive 11, offset 2355"):
        drawing._projection_rendered_edges((slots, native.data))


def test_full_buffer_diagnostic_preserves_r28_semantics(r28_identity_native):
    native = r28_identity_native
    records = drawing._projection_diagnostic_records(native.raw_data)
    assert records["numeric_record_count"] == 36
    assert records["consumed_values"] == 1167 and records["zero_residual_values"] == 34
    assert sum(row["type"] == 0 for row in records["records"]) == 19
    assert sum(row["type"] == 1 for row in records["records"]) == 17
    assert drawing._projection_rendered_edges((native.raw_slots, native.raw_data)) == tuple(native.raw_slots)


@pytest.mark.parametrize("cut", [1, 8, 14, 61, 2189, 2231, 2354, 2369])
def test_r29_diagnostic_rejects_truncated_records(r29_polyline_capture, cut):
    with pytest.raises(RuntimeError, match="diagnostic truncated"):
        drawing._projection_diagnostic_records(r29_polyline_capture.data[:cut])


@pytest.mark.parametrize("offset,value", [
    (0, 2.0), (1, -1.0), (1, float("inf")), (8, 1.0), (8, 2.5),
    (68, float("nan")), (69, float("inf")), (2368, float("nan")),
    (2368, "not-a-double"),
])
def test_r29_diagnostic_rejects_malformed_and_nonfinite_records(r29_polyline_capture, offset, value):
    data = list(r29_polyline_capture.data)
    data[offset] = value
    with pytest.raises(RuntimeError, match="diagnostic"):
        drawing._projection_diagnostic_records(data)


def test_r29_extra_record_is_observed_but_never_accepted(r29_polyline_capture):
    data = (*r29_polyline_capture.data, *r29_polyline_capture.data[-15:])
    records = drawing._projection_diagnostic_records(data)
    assert records["numeric_record_count"] == 13 and records["consumed_values"] == 2385
    with pytest.raises(RuntimeError, match="primitive 11, offset 2355"):
        drawing._projection_rendered_edges(((None,) * 11, data))


@pytest.fixture
def r29_refusal_native(lever_tip_native, r29_polyline_capture):
    """R29 numbers with explicitly SYNTHETIC capabilities, counts and mappings.

    The actual packet has no Count5/GetXform or cropped slot identity evidence.
    Values below exercise reader isolation, not an R29 native success claim.
    """
    native = lever_tip_native
    native.actual_r29 = r29_polyline_capture
    native.raw_slots = tuple(
        None if row["type"] == "builtins.NoneType" else native.rendered_edges[(index - 4) % 4]
        for index, row in enumerate(r29_polyline_capture.slots)
    )
    native.raw_data = list(r29_polyline_capture.data)
    native.g7_calls, native.count_calls = [], []
    native.cropped = True

    def polylines(option):
        native.g7_calls.append(option)
        return native.raw_slots, native.raw_data

    def count(option):
        native.count_calls.append(option)
        return 23, 4567  # Deliberately unlike the observed numeric record count.

    native.view.GetPolylines7 = polylines
    native.view.GetPolyLineCount5 = count
    native.view.GetXform = lambda: (0.25, -0.5, 2.0)
    return native


def test_r29_refusal_collects_all_raw_slots_without_prefix_association(r29_refusal_native):
    native = r29_refusal_native
    with pytest.raises(RuntimeError, match="primitive 11, offset 2355") as caught:
        drawing._projection_model_ink(native.adapter, native.view, stage="settled drawing")
    assert native.g7_calls == [1] and native.count_calls == [1]
    assert len(native.failure_captures) == 1
    packet = native.failure_captures[0][2]
    assert packet["exception"] is caught.value
    probe = packet["native_polyline_probe"]
    assert probe["slot_observation_scope"] == "RAW_SLOT_OBSERVATION"
    assert probe["rendered_status"] == "UNAVAILABLE"
    assert probe["component_readback"]["rendered_model_edges"] is None
    assert probe["numeric_records"]["numeric_record_count"] == 12
    assert probe["numeric_records"]["association"] == "UNAVAILABLE"
    assert probe["crop_contour_handle"]["status"] == "UNAVAILABLE"
    readers = probe["readers"]
    assert readers["native_polyline_count5.return"]["value"]["value"] == 23
    assert readers["native_polyline_count5.point_count"]["value"]["value"] == 4567
    assert readers["view.xform"]["value"]["length"] == 3
    for index in range(11):
        prefix = f"slot[{index}]"
        assert readers[f"{prefix}.raw"]["status"] == ("RETURNED_NULL" if index < 4 else "OBSERVED")
        assert readers[f"{prefix}.qi.IEdge"]["status"] == ("UNAVAILABLE" if index < 4 else "OBSERVED")
        assert readers[f"{prefix}.owner"]["status"] == ("UNAVAILABLE" if index < 4 else "OBSERVED")
        assert f"{prefix}.same.slot[10]" in readers
    for component in native.drawing_components:
        prefix = f"component[{component.Component.Name2}]"
        assert readers[f"{prefix}.slot[0].source"]["status"] == "UNAVAILABLE"
        assert readers[f"{prefix}.slot[10].instance"]["status"] == "OBSERVED"
        assert readers[f"{prefix}.visible_edge[0].instance_raw.same.slot[10]"]["status"] == "OBSERVED"
    assert native.imports == []
    assert native.source.SystemValue == pytest.approx(0.00125)


@pytest.mark.parametrize("failure", [
    "count", "xform", "qi", "curve", "body", "owner", "source", "mapping",
    "snapshot", "formatter", "collector", "capture",
])
def test_r29_refusal_preserves_raw_first_and_original_traceback(
    r29_refusal_native, monkeypatch, failure,
):
    native = r29_refusal_native
    originals, traces = [], []
    decode = drawing._projection_rendered_edges
    attempts = []
    raw_frozen = []
    freeze = drawing._projection_raw_snapshot

    class ReaderFailure(BaseException):
        def __str__(self):
            raise ValueError("unprintable diagnostic")

    def fail(*_args, **_kwargs):
        assert raw_frozen  # Raw bytes precede every optional failure.
        raise ReaderFailure()

    def frozen(value):
        result = freeze(value)
        raw_frozen.append(result)
        return result

    def refuse(result):
        assert raw_frozen  # The real strict decoder must run AFTER preservation.
        try:
            return decode(result)
        except RuntimeError as original:
            originals.append(original)
            traces.append(original.__traceback__)
            raise

    def capture(_adapter, _label, _message, **kwargs):
        attempts.append(kwargs)
        if failure == "capture":
            fail()

    monkeypatch.setattr(drawing, "_projection_raw_snapshot", frozen)
    monkeypatch.setattr(drawing, "_projection_rendered_edges", refuse)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    failed_key = None
    if failure == "count":
        native.view.GetPolyLineCount5 = fail
        failed_key = "native_polyline_count5"
    elif failure == "xform":
        native.view.GetXform = fail
        failed_key = "view.xform"
    elif failure in ("qi", "curve", "body", "owner"):
        edge = native.raw_slots[4]
        if failure == "qi":
            edge._oleobj_.QueryInterface = fail
            failed_key = "slot[4].qi.IEdge"
        else:
            setattr(edge, {"curve": "GetCurve", "body": "GetBody", "owner": "GetComponent"}[failure], fail)
            failed_key = f"slot[4].{failure}_return"
    elif failure in ("source", "mapping"):
        component = native.drawing_components[0].Component
        setattr(component, "GetModelDoc2" if failure == "source" else "GetCorrespondingEntity", fail)
        failed_key = f"component[{component.Name2}]." + ("source_return" if failure == "source" else "slot[4].instance")
    elif failure == "snapshot":
        monkeypatch.setattr(drawing, "_projection_polyline_snapshot", fail)
    elif failure == "formatter":
        monkeypatch.setattr(drawing, "_projection_error_text", fail)
    elif failure == "collector":
        monkeypatch.setattr(drawing, "_projection_refused_slot_observations", fail)
    with pytest.raises(RuntimeError) as caught:
        drawing._projection_model_ink(native.adapter, native.view, stage="settled drawing")
    original = originals[0]
    assert str(original) == "GetPolylines7 nonzero residual data / unmatched primitive at primitive 11, offset 2355"
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not traces[0]:
        trace = trace.tb_next
    assert trace is traces[0]
    assert len(attempts) == 1 and attempts[0]["exception"] is original
    probe = attempts[0]["native_polyline_probe"]
    slots, values = probe["original_return"]["items"]
    assert slots["length"] == 11 and values["length"] == 2370
    assert [row["value"] for row in slots["items"][:4]] == [None] * 4
    assert [row["ieee754_le"] for row in values["items"]] == [
        row["ieee754_le"] for row in native.actual_r29.values
    ]
    if failed_key is not None:
        assert probe["readers"][failed_key]["status"] == "ERROR"
        assert probe["readers"]["slot[10].raw"]["status"] == "OBSERVED"
    assert native.g7_calls == [1] and native.imports == []


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("site", [
    "drawing-getter", "visible-getter", "component-binding", "component-member", "decoder",
])
def test_r29_raw_return_precedes_component_and_decoder_interrupts(
    r29_refusal_native, monkeypatch, site, error_type,
):
    native = r29_refusal_native
    native.raw_slots = list(native.raw_slots)
    original = error_type(f"first native failure at {site}")
    traces, attempts = [], []

    def fail(*_args, **_kwargs):
        # Mutate the actual returned containers at the failing reader. A snapshot
        # taken on collector entry would lose the original NULL and IEEE bytes.
        native.raw_slots[0] = object()
        native.raw_data[0] = 99.0
        try:
            raise original
        except BaseException:
            if not traces:
                traces.append(original.__traceback__)
            raise

    if site == "drawing-getter":
        native.view.GetVisibleDrawingComponents = fail
    elif site == "visible-getter":
        native.view.GetVisibleComponents = fail
    elif site == "component-binding":
        bind = drawing._early_bound

        def binding(value, interface):
            if interface == "IDrawingComponent":
                return fail()
            return bind(value, interface)

        monkeypatch.setattr(drawing, "_early_bound", binding)
    elif site == "component-member":
        class InterruptedComponent:
            @property
            def Component(self):
                return fail()

        native.drawing_components[0] = InterruptedComponent()
    else:
        monkeypatch.setattr(drawing, "_projection_rendered_edges", fail)

    def formatter(_error):
        raise KeyboardInterrupt("secondary diagnostic formatter")

    def capture(_adapter, _label, _message, **kwargs):
        attempts.append(kwargs)
        raise SystemExit("secondary forensic observer")

    monkeypatch.setattr(drawing, "_projection_error_text", formatter)
    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture)
    with pytest.raises(error_type) as caught:
        drawing._projection_model_ink(native.adapter, native.view, stage="settled drawing")
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not traces[0]:
        trace = trace.tb_next
    assert trace is traces[0]
    assert len(attempts) == 1 and attempts[0]["exception"] is original
    probe = attempts[0]["native_polyline_probe"]
    slots, values = probe["original_return"]["items"]
    assert slots["length"] == 11 and values["length"] == 2370
    assert [row["value"] for row in slots["items"][:4]] == [None] * 4
    assert [row["ieee754_le"] for row in values["items"]] == [
        row["ieee754_le"] for row in native.actual_r29.values
    ]
    assert probe["rendered_status"] == "UNAVAILABLE"
    assert probe["component_readback"]["rendered_model_edges"] is None
    assert native.g7_calls == [1] and native.imports == []


@pytest.mark.parametrize("count", [None, 12, (), (12,), (12, 2370, 11)])
def test_r29_count_readback_never_infers_missing_out_parameter(r29_refusal_native, count):
    native = r29_refusal_native
    native.view.GetPolyLineCount5 = lambda _option: count
    with pytest.raises(RuntimeError, match="primitive 11, offset 2355"):
        drawing._projection_model_ink(native.adapter, native.view, stage="settled drawing")
    readers = native.failure_captures[0][2]["native_polyline_probe"]["readers"]
    assert readers["native_polyline_count5"]["status"] == ("RETURNED_NULL" if count is None else "OBSERVED")
    assert readers["native_polyline_count5.return"]["status"] == "UNAVAILABLE"
    assert readers["native_polyline_count5.point_count"]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("failure", [
    None, "wrong-view", "wrong-sketch", "stale-circle", "sketch-reader", "bool-identity",
])
def test_retained_crop_handle_is_diagnostic_only_and_requires_current_native_context(
    r29_refusal_native, failure,
):
    native = r29_refusal_native
    sketch = object()
    # Synthetic native equality is deliberate: the actual R29 capture has no
    # retained authored circle. Even a positive observation cannot accept G7.
    circle = native.raw_slots[4]
    context = (native.view, sketch, circle, circle)
    native.view.GetSketch = lambda: sketch
    if failure == "wrong-view":
        context = (object(), sketch, circle, circle)
    elif failure == "wrong-sketch":
        native.view.GetSketch = lambda: object()
    elif failure == "sketch-reader":
        def unavailable_sketch():
            raise RuntimeError("current sketch reader refused")
        native.view.GetSketch = unavailable_sketch
    elif failure in ("stale-circle", "bool-identity"):
        same = native.adapter.swApp.IsSame

        def identity(left, right):
            if left is circle or right is circle:
                if failure == "stale-circle":
                    raise RuntimeError("authored circle invalidated by Crop2")
                return True
            return same(left, right)

        native.adapter.swApp.IsSame = identity
    with pytest.raises(RuntimeError, match="primitive 11, offset 2355"):
        drawing._projection_model_ink(
            native.adapter, native.view, stage="settled drawing", crop_context=context,
        )
    probe = native.failure_captures[0][2]["native_polyline_probe"]
    assert probe["rendered_status"] == "UNAVAILABLE"
    assert probe["numeric_records"]["numeric_record_count"] == 12
    assert probe["crop_contour_handle"]["acceptance"] == "NOT_USED"
    assert probe["crop_contour_handle"]["record_association"] == "UNAVAILABLE"
    assert probe["crop_contour_handle"]["status"] == ("OBSERVED" if failure is None else "UNAVAILABLE")
    readers = probe["readers"]
    assert readers["crop.segment.same.slot[0]"]["status"] == "UNAVAILABLE"
    if failure is None:
        assert readers["crop.segment.same.slot[4]"]["value"]["value"] == 1
    else:
        assert readers["crop.segment.same.slot[4]"]["status"] == "UNAVAILABLE"
    assert readers["slot[10].raw"]["status"] == "OBSERVED"
    assert native.g7_calls == [1] and native.imports == []


def test_tip_settled_closure_retains_only_its_authored_crop_context(lever_tip_native, monkeypatch):
    native = lever_tip_native
    context = (native.view, object(), object(), object())
    crop = drawing._crop
    layout = drawing._projection_layout
    seen = []

    def retain(*args):
        crop(*args)
        return context

    def observe(*args, crop_context=None):
        seen.append(crop_context)
        return layout(*args, crop_context=crop_context)

    monkeypatch.setattr(drawing, "_crop", retain)
    monkeypatch.setattr(drawing, "_projection_layout", observe)
    settled = drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    settled()
    assert len(seen) == 2 and all(value is context for value in seen)
    assert not native.failure_captures


def test_bad_polyline_header_preserves_full_original_payload_and_terminal_failure(lever_tip_native):
    import struct

    native = lever_tip_native
    # Deliberately unsupported type; the arbitrary remainder tests complete
    # failure-payload preservation, not the format of native R26 records.
    nan_bits = bytes.fromhex("010000000000f87f")
    payload = (
        2.0, 0.0, *(float(i) / 7 for i in range(128)), -0.0,
        struct.unpack("<d", nan_bits)[0],
    )
    original_return = (tuple(native.edges), payload)
    calls = []

    def polylines(cross):
        calls.append(cross)
        return original_return

    native.view.GetPolylines7 = polylines
    with pytest.raises(RuntimeError, match=r"invalid geometry header \(2.0, 0.0\).*offset 0") as caught:
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert calls == [1]
    assert len(native.failure_captures) == 1
    _label, message, capture = native.failure_captures[0]
    assert capture["exception"] is caught.value
    assert message == str(caught.value)
    assert capture["sheet_png"] is True
    assert capture["api"] == "IView.GetPolylines7"
    probe = capture["native_polyline_probe"]
    assert probe["return_observed"] is True
    assert probe["rendered_status"] == "UNAVAILABLE"
    assert probe["component_readback"]["rendered_model_edges"] is None
    tree = probe["original_return"]
    assert tree["type"] == "builtins.tuple" and tree["length"] == 2
    edge_slots, buffer = tree["items"]
    assert edge_slots["length"] == 2
    assert [slot["python_id"] for slot in edge_slots["items"]] == [id(edge) for edge in native.edges]
    assert buffer["length"] == len(payload)
    assert [item["type"] for item in buffer["items"]] == ["builtins.float"] * len(payload)
    assert [bytes.fromhex(item["ieee754_le"]) for item in buffer["items"]] == [
        struct.pack("<d", value) for value in payload
    ]
    state = probe["view_state"]
    assert state["revision"]["value"] == "34.4"
    assert state["orientation"]["value"] == drawing.LEVER_TIP.orientation
    assert state["display_mode"]["value"] == 2
    assert state["facetted_hlr"]["value"] is False
    assert state["cropped"]["value"] is False
    assert state["model_to_view"]["length"] == 16
    assert probe["reader_errors"] == {}
    assert native.imports == [] and native.annotations == [] and not native.cropped
    assert not any(event[0] in ("move", "caption-move", "crop") for event in native.events)


def test_polyline_capture_retains_original_getter_exception_and_independent_view_reads(
    lever_tip_native,
):
    native = lever_tip_native
    original = OSError("native G7 OUT reader refused")
    calls = []

    def polylines(cross):
        calls.append(("polylines", cross))
        raise original

    def display_mode():
        calls.append(("display-mode",))
        raise RuntimeError("display-mode diagnostic refused")

    def quality():
        calls.append(("facetted-hlr",))
        return False

    def outline():
        calls.append(("outline",))
        raise RuntimeError("outline diagnostic refused")

    class Transform:
        @property
        def ArrayData(self):
            calls.append(("transform",))
            return tuple(float(i) for i in range(16))

    native.view.GetPolylines7 = polylines
    native.view.GetDisplayMode2 = display_mode
    native.view.GetFacettedHlrDisplay = quality
    native.view.GetOutline = outline
    native.view.ModelToViewTransform = Transform()
    with pytest.raises(OSError) as caught:
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert caught.value is original
    capture = native.failure_captures[0][2]
    assert capture["exception"] is original and capture["sheet_png"] is True
    probe = capture["native_polyline_probe"]
    assert probe["return_observed"] is False
    assert probe["original_return"] == {"type": "builtins.NoneType", "value": None}
    assert set(probe["reader_errors"]) == {"display_mode", "outline"}
    assert probe["view_state"]["facetted_hlr"]["value"] is False
    assert probe["view_state"]["model_to_view"]["length"] == 16
    assert calls == [
        ("polylines", 1), ("display-mode",), ("facetted-hlr",), ("outline",), ("transform",),
    ]
    assert native.imports == [] and not native.cropped


def test_polyline_snapshot_keeps_opaque_dispatch_identity_without_wrapper_repr():
    class NativeWrapper:
        def __init__(self):
            self._oleobj_ = object()

        def __repr__(self):
            raise AssertionError("must not dump the generated native wrapper")

    wrapper = NativeWrapper()
    tree = drawing._projection_polyline_snapshot(([wrapper, None, True, 17], (0.0, -0.0)))
    slots = tree["items"][0]
    assert slots["type"] == "builtins.list" and slots["length"] == 4
    assert slots["items"][0]["dispatch_repr"] == repr(wrapper._oleobj_)
    assert slots["items"][0]["python_id"] == id(wrapper)
    assert "repr_error" not in slots["items"][0]
    assert slots["items"][1:] == [
        {"type": "builtins.NoneType", "value": None},
        {"type": "builtins.bool", "value": True},
        {"type": "builtins.int", "value": 17},
    ]
    assert tree["items"][1]["items"][0]["ieee754_le"] != tree["items"][1]["items"][1]["ieee754_le"]


def test_unreadable_opaque_polyline_slot_does_not_discard_numeric_payload():
    class Unreadable:
        @property
        def __dict__(self):
            raise RuntimeError("opaque attributes refused")

        def __repr__(self):
            raise RuntimeError("opaque repr refused")

    tree = drawing._projection_polyline_snapshot(((Unreadable(),), (0.0, 17.0)))
    slot = tree["items"][0]["items"][0]
    assert "opaque attributes refused" in slot["attributes_error"]
    assert "opaque repr refused" in slot["repr_error"]
    assert tree["items"][1]["length"] == 2
    assert [item["repr"] for item in tree["items"][1]["items"]] == ["0.0", "17.0"]


def test_payload_snapshot_failure_cannot_mask_original_or_skip_view_readers(
    lever_tip_native, monkeypatch,
):
    native = lever_tip_native
    original = RuntimeError("original decoder failure")
    raw = object()
    snapshot = drawing._projection_polyline_snapshot

    def refuse_raw(value):
        if value is raw:
            raise RuntimeError("raw snapshot refused")
        return snapshot(value)

    monkeypatch.setattr(drawing, "_projection_polyline_snapshot", refuse_raw)
    with pytest.raises(RuntimeError) as caught:
        drawing._capture_projection_polyline_failure(
            native.adapter, native.view, stage="diagnostic isolation",
            result=raw, observed=True, exception=original, evidence={},
        )
    assert caught.value is original
    capture = native.failure_captures[0][2]
    assert capture["exception"] is original and capture["sheet_png"] is True
    probe = capture["native_polyline_probe"]
    assert "raw snapshot refused" in probe["reader_errors"]["original_return"]
    assert probe["view_state"]["revision"]["value"] == "34.4"
    assert probe["view_state"]["orientation"]["value"] == drawing.LEVER_TIP.orientation
    assert probe["view_state"]["model_to_view"]["length"] == 16


@pytest.mark.parametrize("result", [(None, None), (None, []), ([], None)])
def test_null_polyline_channels_are_unavailable_and_captured(lever_tip_native, result):
    native = lever_tip_native
    calls = []

    def polylines(cross):
        calls.append(cross)
        return result

    native.view.GetPolylines7 = polylines
    with pytest.raises(RuntimeError, match="channel is unavailable at primitive 0, offset 0") as caught:
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert calls == [1]
    capture = native.failure_captures[0][2]
    assert capture["exception"] is caught.value and capture["sheet_png"] is True
    probe = capture["native_polyline_probe"]
    assert probe["return_observed"] is True
    assert probe["rendered_status"] == "UNAVAILABLE"
    assert probe["component_readback"]["rendered_model_edges"] is None
    assert probe["original_return"] == drawing._projection_polyline_snapshot(result)


def test_actual_empty_polyline_arrays_remain_measured_empty(lever_tip_native, monkeypatch):
    native = lever_tip_native
    messages = []
    monkeypatch.setattr(drawing._telemetry, "info", lambda text, **_kw: messages.append(text))
    native.view.GetPolylines7 = lambda _cross: ([], [])
    assert drawing._projection_rendered_edges(([], [])) == ()
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert len(native.failure_captures) == 1
    probe = native.failure_captures[0][2]["native_identity_probe"]
    assert probe["rendered_status"] == "DECODED"
    assert probe["decoded_model_edge_count"] == 0
    assert "'rendered_model_edges': 0" in messages[-1]
    assert native.imports == [] and not native.cropped


@pytest.mark.parametrize("failure", [
    "truncated-primitive", "truncated-geometry", "negative-count", "fractional-count",
    "nan-count", "infinite-count", "unreadable-count", "short-points",
    "missing-edge", "unmatched-edge", "nonfinite-record", "unreadable-record", "header",
])
def test_every_later_polyline_refusal_names_primitive_and_buffer_position(lever_tip_native, failure):
    native = lever_tip_native
    first = tuple(native.polyline)
    second = list(first)
    edges = tuple(native.edges)
    if failure == "truncated-primitive":
        second = [0.0, 0.0]
    elif failure == "truncated-geometry":
        second = [1.0, 12.0, *([0.0] * 7)]
    elif failure in ("negative-count", "fractional-count", "nan-count", "infinite-count", "unreadable-count"):
        second[8] = {
            "negative-count": -1, "fractional-count": 1.5, "nan-count": float("nan"),
            "infinite-count": float("inf"), "unreadable-count": "not a count",
        }[failure]
    elif failure == "short-points":
        second.pop()
    elif failure == "missing-edge":
        edges = edges[:1]
    elif failure == "unmatched-edge":
        second = []
    elif failure == "nonfinite-record":
        second[9] = float("nan")
    elif failure == "unreadable-record":
        second[9] = object()
    else:
        second[0] = 2.0
    with pytest.raises(RuntimeError, match=rf"primitive 1, offset {len(first)}"):
        drawing._projection_rendered_edges((edges, (*first, *second)))


@pytest.mark.parametrize("result", [None, (), ([],), (object(), [])])
def test_initial_polyline_shape_refusals_name_start_position(result):
    with pytest.raises(RuntimeError, match="primitive 0, offset 0"):
        drawing._projection_rendered_edges(result)


@pytest.mark.parametrize("failure", ["snapshot", "reader", "binding"])
def test_unprintable_secondary_error_keeps_independent_readers_and_forensic_attempt(
    lever_tip_native, monkeypatch, failure,
):
    native = lever_tip_native
    original = RuntimeError("original decoder refusal")
    try:
        raise original
    except RuntimeError:
        original_traceback = original.__traceback__
    raw = object()
    snapshot = drawing._projection_polyline_snapshot

    class UnprintableError(Exception):
        def __str__(self):
            raise ValueError("secondary formatter failed")

    def snapshot_failure(value):
        if value is raw:
            raise UnprintableError()
        return snapshot(value)

    def reader_failure():
        raise UnprintableError()

    def binding_failure(obj, interface):
        if interface == "ISldWorks":
            raise UnprintableError()
        return obj

    if failure == "snapshot":
        monkeypatch.setattr(drawing, "_projection_polyline_snapshot", snapshot_failure)
        failed_field = "original_return"
    elif failure == "reader":
        native.view.GetDisplayMode2 = reader_failure
        failed_field = "display_mode"
    else:
        monkeypatch.setattr(drawing, "_early_bound", binding_failure)
        failed_field = "revision"
    with pytest.raises(RuntimeError) as caught:
        drawing._capture_projection_polyline_failure(
            native.adapter, native.view, stage="unprintable secondary",
            result=raw, observed=True, exception=original, evidence={},
        )
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not original_traceback:
        trace = trace.tb_next
    assert trace is original_traceback
    capture = native.failure_captures[0][2]
    assert capture["exception"] is original and capture["sheet_png"] is True
    probe = capture["native_polyline_probe"]
    assert probe["reader_errors"][failed_field] == "UnprintableError: <diagnostic text unavailable>"
    assert probe["view_state"]["orientation"]["value"] == drawing.LEVER_TIP.orientation
    assert probe["view_state"]["facetted_hlr"]["value"] is False
    assert probe["view_state"]["model_to_view"]["length"] == 16


@pytest.mark.parametrize("failure", ["capture", "logger", "capture-return"])
def test_entire_optional_capture_sequence_always_reraises_original_traceback(
    lever_tip_native, monkeypatch, failure,
):
    native = lever_tip_native
    original = RuntimeError("original decoder refusal")
    try:
        raise original
    except RuntimeError:
        original_traceback = original.__traceback__
    attempts = []

    def logger_failure(*_args, **_kwargs):
        raise ValueError("optional logger refused")

    def capture_failure(*_args, **kwargs):
        attempts.append(kwargs)
        if failure == "capture":
            raise ValueError("optional capture refused")
        if failure == "logger":
            drawing._telemetry.info("optional failure-only log")

    monkeypatch.setattr(drawing._seat_forensics, "capture_com_failure", capture_failure)
    monkeypatch.setattr(drawing._telemetry, "info", logger_failure)
    with pytest.raises(RuntimeError) as caught:
        drawing._capture_projection_polyline_failure(
            native.adapter, native.view, stage="optional capture refusal",
            result=(None, None), observed=True, exception=original, evidence={},
        )
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not original_traceback:
        trace = trace.tb_next
    assert trace is original_traceback
    assert len(attempts) == 1 and attempts[0]["exception"] is original
    assert attempts[0]["sheet_png"] is True


@pytest.mark.parametrize("failure", ["prelude-format", "capture-entry"])
def test_decoder_failure_is_preserved_before_optional_capture_entry(
    lever_tip_native, monkeypatch, failure,
):
    native = lever_tip_native
    original = RuntimeError("retained decoder refusal")
    tracebacks = []
    format_error = drawing._projection_error_text

    def refuse_decode(_result):
        try:
            raise original
        except RuntimeError:
            tracebacks.append(original.__traceback__)
            raise

    def refuse_format(error):
        if error is original:
            raise ValueError("pre-capture formatter refused")
        return format_error(error)

    def refuse_capture(*_args, **_kwargs):
        raise ValueError("capture entry refused")

    monkeypatch.setattr(drawing, "_projection_rendered_edges", refuse_decode)
    if failure == "prelude-format":
        monkeypatch.setattr(drawing, "_projection_error_text", refuse_format)
    else:
        monkeypatch.setattr(drawing, "_capture_projection_polyline_failure", refuse_capture)
    with pytest.raises(RuntimeError) as caught:
        drawing._thread_projection_detail(native.adapter, (), (), native.source_step)
    assert caught.value is original
    trace = caught.value.__traceback__
    while trace is not None and trace is not tracebacks[0]:
        trace = trace.tb_next
    assert trace is tracebacks[0]
    assert native.imports == [] and not native.cropped


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


@pytest.mark.parametrize("previous_direct", [False, True])
@pytest.mark.parametrize("status,cropped", [(drawing.CROP_NO_ERROR, True), (0, False)])
def test_lever_tip_reuses_native_crop_sketch_transform(
    monkeypatch, status, cropped, previous_direct,
):
    events = []
    transform = object()

    class Point:
        def __init__(self, values):
            self.ArrayData = values

        def MultiplyTransform(self, actual):
            assert actual is transform
            x, y, z = self.ArrayData
            return Point((x / 4, y / 4, z))

    manager = SimpleNamespace(AddToDB=previous_direct)
    fence = []
    authored = []

    def circle(*points):
        events.append(("circle", points, manager.AddToDB))
        cx, cy, _cz, rx, ry, _rz = (value * 4 for value in points)
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
        context = drawing._crop(adapter, view, drawing.LEVER_TIP)
        assert context[0] is view and context[1] is sketch
        assert context[2] is authored[0] and context[3] is authored[0]
    else:
        with pytest.raises(RuntimeError, match="not cropped"):
            drawing._crop(adapter, view, drawing.LEVER_TIP)
    cx, cy = drawing.LEVER_TIP.centre
    radius = drawing.LEVER_TIP.crop_radius
    assert events[0] == (
        "circle", (cx / 4, cy / 4, 0.0, (cx + radius) / 4, cy / 4, 0.0), True,
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

    asyncio.run(assembly._author_lever_setting_reference(Adapter()))

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
    monkeypatch.setattr(drawing._telemetry, "info", lambda _message: None)
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
    from _test_stubbed_build import stub_seat

    monkeypatch.setattr(_com, "_early_bound", lambda value, _interface: value)
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
    identity = (
        1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
        0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0,
    )
    source_components = []
    for stem in notes.BOM_ORDER:
        for index in range(notes.QUANTITIES[stem]):
            source_components.append(SimpleNamespace(
                Name2=f"{stem}-{index + 1}",
                GetPathName=lambda stem=stem: f"C:/native/{stem}.SLDPRT",
                ReferencedConfiguration=(
                    "LeverWire" if stem == notes.WIRE else "Default"
                ),
                ComponentReference="LeverWire:1" if stem == notes.WIRE else "",
                GetTotalTransform=lambda _presentation: SimpleNamespace(
                    ArrayData=identity
                ),
            ))
    source_model = SimpleNamespace(
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
        GetExplodedViewNames2=lambda configuration: (
            drawing.EXPLODED_VIEW_NAMES[configuration],
        ),
        GetComponents=lambda _top_level: tuple(source_components),
    )
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
def immutable_tip_build(monkeypatch, tmp_path, lever_tip_native):
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
    state = SimpleNamespace(
        source=source, path=path, native=native, saved=False, finalized=False,
        hook=lambda _stage: None, metadata_reads=[], phases=[], balloon_calls=[],
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
    monkeypatch.setattr(drawing, "insert_bom_table", lambda *_a, **_k: object())
    items = {stem: str(i) for i, stem in enumerate(notes.BOM_ORDER, 1)}
    monkeypatch.setattr(drawing, "_validate_bom", lambda *_a: items)
    monkeypatch.setattr(drawing, "_bom_items", lambda *_a: items)

    def balloons(_adapter, view, **kwargs):
        state.balloon_calls.append((view, kwargs))
        return [SimpleNamespace(stem=explode.WIRE_STEM)]

    monkeypatch.setattr(drawing, "add_component_bom_balloons", balloons)
    monkeypatch.setattr(drawing, "_add_note_block", lambda *_a, **_k: object())
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
    # PR1764 has not restored groups 1–18. Only wire19 is actually inserted,
    # with explicit collapsed metadata rather than reading/activating source.
    assert len(state.balloon_calls) == 1
    view, kwargs = state.balloon_calls[0]
    assert view is state.views[drawing.FINISHED_LABEL]
    assert kwargs["items"] == ((explode.WIRE_STEM, "19"),)
    assert notes.BOM_ORDER.index(explode.WIRE_STEM) + 1 == 19
    assert kwargs["explode_offsets"] == {}


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

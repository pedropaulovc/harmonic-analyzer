"""Offline contract for the magnifier assembly drawing and its stack settings."""

import asyncio
import math
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
            for index, line in enumerate(notes.LEVER_CALLOUTS[name].splitlines())
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
    display = Display({4: notes.LEVER_CALLOUTS[name]})
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
    callouts = drawing._printable_lever_callouts()
    assert " ".join(callouts[name].split()) == "FLAT LEVER TIP PROUD OF FAR BRACKET FACE"
    assert len(callouts[name].splitlines()) == 3
    assert drawing.LEVER_CALLOUT_LOCATION[name] == "below"
    drawing._assert_lever_callouts([(name, native.display)], callouts)
    wrapped = drawing._thread_projection_text_box(native.adapter, native.annotation)
    native.rows[1]["text"] = " ".join(callouts[name].split())
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
    drawing._assert_lever_callouts(
        [(stack.THREAD_PROJECTION_DIMENSION, native.display)],
        drawing._printable_lever_callouts(),
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
    native.rows[1]["text"] = notes.LEVER_CALLOUTS[stack.THREAD_PROJECTION_DIMENSION]
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
        key: SimpleNamespace(GetSpecificAnnotation=lambda d=_Display({}): d)
        for key in (stack.CLAMP_STATION_DIMENSION, stack.FIXTURE_DROP_DIMENSION)
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

    def callouts(_adapter, imported, values, *, location):
        assert imported == list(annotations.values())
        for key, value in values.items():
            annotations[key].GetSpecificAnnotation().parts[drawing.CALLOUT_TEXT_PART[location]] = value

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "set_dimension_callouts", callouts)
    monkeypatch.setattr(drawing, "assert_imported_precision", lambda *args: precision.append(args))
    view = object()
    settled = drawing._lever_settings(object(), view)
    assert imports == [(view, {
        "keep": drawing.lever_keep((0.04, 0.21), (0.06, 0.21), (0.06, 0.19)),
        "view_label": drawing.LEVER_VIEW_LABEL,
        "dimensions_by_feature": stack.LEVER_DRAWING_DIMENSIONS,
    })]
    assert shown == [(stack.LEVER_FEATURE,)]
    assert stack.THREAD_PROJECTION_DIMENSION not in imports[0][1]["keep"]
    assert precision[0][2] == stack.LEVER_DRAWING_PRECISION[stack.LEVER_FEATURE]
    settled()
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
    )
    native.adapter.currentModel.ViewZoomtofit2 = lambda: native.events.append(("zoom",))
    monkeypatch.setattr(drawing, "double_array", tuple)
    native.drawing_components = []
    native.visible_components = []
    native.edges = []
    native.component_edges = {}
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
        native.drawing_components.append(SimpleNamespace(Component=full, Visible=True))
        native.visible_components.append(SimpleNamespace(Name2=name))
    native.rendered_edges = list(native.edges)
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
        GetText=lambda: drawing.ASSEMBLED_VIEW_CAPTIONS["*Front"],
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
        # Actual *Back orientation: reverse X, retain Y; component Z is real,
        # whereas the authored dimension chain is in the assembly's Z=0 plane.
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

    def callouts(_adapter, annotations, texts, *, location):
        assert native.cropped and annotations == [native.annotation]
        native.display.parts[drawing.CALLOUT_TEXT_PART[location]] = texts[name]

    def label(_adapter, text, x, y):
        assert text == drawing.LEVER_TIP.label_text
        assert (x, y) == drawing.LEVER_TIP.label_xy
        native.events.append(("caption", text))
        return native.caption

    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop", crop)
    monkeypatch.setattr(drawing, "set_dimension_callouts", callouts)
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
        native.adapter, (native.neighbour,), (native.back_caption,)
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
    # Reverse only the detail's viewing direction, not the installation.
    assert detail.orientation == "*Back"
    assert detail.scale == (4, 1)
    assert assembly.LEVER_ROD_Z - drawing.NOSE_R < flange_near_z
    assert drawing.ASSEMBLED_VIEW_CAPTIONS["*Front"] == "VIEW FROM THE BACK"


def test_detail_proves_transformed_physical_edges_before_import_and_after_crop(lever_tip_native):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(native.adapter, (), ())
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
    settled = drawing._thread_projection_detail(native.adapter, (), ())
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
    with pytest.raises(RuntimeError, match="physical model proof failed"):
        drawing._projection_model_ink(native.adapter, native.view, stage="independent reader regression")
    assert calls == ["drawing", "visible", "polylines"]
    assert "drawing component reader refused" in messages[-1]
    assert "'rendered_model_edges': 2" in messages[-1]
    assert "mg-magnifying-lever-1" in messages[-1] and "mg-magnifying-bracket-1" in messages[-1]


def test_back_caption_moves_once_using_whole_native_outline_not_crop(lever_tip_native):
    native = lever_tip_native
    before = tuple(native.back_extent)
    box = drawing._projection_note_box(native.back_caption)
    assert drawing.boxes_clear(box, drawing._projection_crop_box(native.view))
    assert not drawing.boxes_clear(box, tuple(native.outline))
    settled = drawing._thread_projection_detail(
        native.adapter, (native.neighbour,), (native.back_caption,),
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
        native.adapter, (native.neighbour,), (native.back_caption,),
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


@pytest.mark.parametrize("failure", [
    "source", "value", "nonfinite-value", "band", "precision", "owner",
    "dangling", "null-point", "entity-type", "replacement", "bool-identity",
    "missing", "duplicate",
])
def test_projection_detail_refuses_lost_authority_after_rebuild(lever_tip_native, failure):
    native = lever_tip_native
    settled = drawing._thread_projection_detail(native.adapter, (), ())
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
        drawing._thread_projection_detail(native.adapter, (), ())


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
        native.adapter, (native.neighbour,), (native.back_caption,)
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
    qualifier = " ".join(notes.LEVER_CALLOUTS[stack.THREAD_PROJECTION_DIMENSION].split())
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
    assert events[0] == ("place", str(drawing.SOURCE), "*Back", detail.centre, (4, 1))
    assert view.Position == pytest.approx((0.060, 0.070))
    assert events[-2:] == [
        ("HLR",), ("isolate", frozenset({"mg-magnifying-lever", "mg-magnifying-bracket"})),
    ]
    assert drawing.PRESSED.orientation == drawing.ENDSHAKE.orientation == "*Right"
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

    def circle(*points):
        events.append(("circle", points, manager.AddToDB))
        cx, cy, _cz, rx, ry, _rz = (value * 4 for value in points)
        if not manager.AddToDB:
            cx -= 0.0025  # R24's witness inference, not a native layout acceptance.
        fence[:] = _native_crop_fence((cx, cy), math.hypot(rx - cx, ry - cy))
        return SimpleNamespace(
            Select4=lambda append, data: events.append(("select", append, data)) or True
        )

    manager.CreateCircle = circle
    view = SimpleNamespace(
        GetSketch=lambda: SimpleNamespace(ModelToSketchTransform=transform),
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
        drawing._crop(adapter, view, drawing.LEVER_TIP)
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

    def stacks(_adapter):
        for _ in range(2):
            label = object()
            annotation = SimpleNamespace(GetType=lambda: 6, GetSpecificAnnotation=lambda n=label: n)
            views.append(SimpleNamespace(GetAnnotations=lambda a=annotation: [a]))
        return stack_check

    def caption(*args, **kwargs):
        note = object()
        captions.append(note)
        return note

    def detail(_adapter, neighbours, notes):
        projection_calls.append((neighbours, notes))
        return projection_check

    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "_lever_settings", lambda _a, view: base_check)
    monkeypatch.setattr(drawing, "_stack_dimensions", stacks)
    monkeypatch.setattr(drawing, "_add_note_block", caption)
    monkeypatch.setattr(drawing, "_thread_projection_detail", detail)
    assert drawing._place_assembled_sheet(adapter) == (base_check, stack_check, projection_check)
    assert [view.orientation for view in views[:3]] == ["*Front", "*Right", "*Isometric"]
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
        # Ry(180) placement, then the *Isometric (+X+Y+Z) projection.
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

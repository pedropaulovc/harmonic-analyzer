"""Offline contract for the magnifier assembly drawing and its stack settings."""

import ast
import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_mg_magnifier_assembly as assembly
import draw_mg_magnifier_assembly as drawing
import mg_magnifier_assembly_spec as stack
import mg_wheel_axle_spacer_spec
import mg_wheel_axle_spec
import mg_wheel_group
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from mg_lever_press_fit_geom import PRESS_INSTALLATION_NOTES

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
    assert drawing.RIGHT_CENTER == (0.150, 0.150)
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
    assert stack.DRAWING_DIMENSIONS == {stack.FEATURE: names}
    assert set(stack.DRAWING_PRECISION[stack.FEATURE]) == names
    assert set(stack.DIMENSION_TOLERANCES) == names
    assert set(stack.DIMENSION_CALLOUTS) == names == set(drawing.CALLOUT_LOCATION)
    assert stack.DIMENSION_TOLERANCES[stack.PRESS_GAUGE_DIMENSION] == 0.05
    assert stack.DIMENSION_TOLERANCES[stack.ENDSHAKE_DIMENSION] == pytest.approx(0.05)
    assert (
        "LOCKNUT ON FULL THREAD"
        in stack.DIMENSION_CALLOUTS[stack.PRESS_GAUGE_DIMENSION]
    )
    # The endshake is set by one nut and held by the other.
    endshake = stack.DIMENSION_CALLOUTS[stack.ENDSHAKE_DIMENSION]
    assert "SET BY THE FIRST NUT" in endshake
    assert "LOCKED BY THE SECOND" in endshake
    for text in stack.DIMENSION_CALLOUTS.values():
        assert not re.search(r"\d", text), text
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
    assert lines[0] == detail.title
    assert lines[-1] == f"SCALE {detail.scale[0]} : {detail.scale[1]}"


def test_the_gauge_detail_names_what_it_presses_into_what() -> None:
    label = drawing.PRESSED.label_text
    assert "MG-WHEEL-AXLE" in label and "MG-WHEEL-BAR" in label
    # The pressed detail's three-line label still clears the endshake crop.
    lines = len(label.splitlines())
    assert (
        drawing.PRESSED.label_xy[1] - 0.0045 * lines > _circle_box(drawing.ENDSHAKE)[3]
    )


def test_each_detail_s_lowest_ink_is_its_geometry() -> None:
    import mg_magnifying_wheel_spec as wheel
    import vn_wheel_axle_front_washer_spec as washer
    import vn_wheel_axle_nut_spec as nut
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
    assert drawing._printable_callouts() == stack.DIMENSION_CALLOUTS
    monkeypatch.setitem(
        stack.DIMENSION_CALLOUTS, stack.PRESS_GAUGE_DIMENSION, "PRESS GAUGE\nLOCKNUT"
    )
    with pytest.raises(RuntimeError, match="line break do not print"):
        drawing._printable_callouts()


class _Display:
    def __init__(self, parts: dict[int, str]) -> None:
        self.parts = parts

    def GetText(self, part: int) -> str:
        return self.parts.get(part, "")


def test_each_callout_reads_back_from_its_own_compartment() -> None:
    callouts = stack.DIMENSION_CALLOUTS
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
    import vn_wheel_axle_front_washer_spec as washer
    import vn_wheel_axle_nut_spec as nut

    assert max(nut.ACROSS_CORNERS, washer.OD) / 2.0 < drawing.ENDSHAKE_RISE
    x, _y = drawing.ENDSHAKE_KEEP[stack.ENDSHAKE_DIMENSION]
    assert x > _circle_box(drawing.ENDSHAKE)[2]
    assert x + 0.030 < SHEET_RIGHT


def test_the_gauge_detail_shows_only_the_bar_and_the_axle() -> None:
    assert drawing.PRESSED.stems == {"mg-wheel-bar", "mg-wheel-axle"}
    assert {
        "vn-wheel-axle-front-washer",
        "vn-wheel-axle-nut",
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



def test_press_note_is_model_owned_and_inserted_before_native_finalization(
    monkeypatch, tmp_path
) -> None:
    # The assembly stamps the same drawing-free instruction as the bracket,
    # not a copied caption that can drift from the force or safe pressing setup.
    tree = ast.parse(Path(assembly.__file__).read_text(encoding="utf-8"))
    values = [
        value
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        for key, value in zip(node.keys, node.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == "Drawing Notes"
    ]
    assert len(values) == 1
    assert isinstance(values[0], ast.Name) and values[0].id == "PRESS_INSTALLATION_NOTES"
    assert "COLLAR ONTO LEVER; HOLD ROD NEAR END" in PRESS_INSTALLATION_NOTES
    assert "WITH OUTER FACE" in PRESS_INSTALLATION_NOTES
    # #1570: press only, no bond.
    assert "LOCTITE" not in PRESS_INSTALLATION_NOTES
    assert "SOLDER" not in PRESS_INSTALLATION_NOTES
    note_calls = []
    events = []
    source = tmp_path / "magnifier.SLDASM"
    source.write_bytes(b"source-presence fixture; native opening is faked")

    async def open_model(path):
        assert path == str(source)
        events.append("open")
        return SimpleNamespace(is_success=True, data=None, error=None)

    adapter = SimpleNamespace(currentModel=object(), open_model=open_model)

    def linked_note(actual_adapter, name, x, y, *, char_height):
        events.append("press-note")
        note_calls.append((actual_adapter, name, x, y, char_height))

    def stack_dimensions(actual_adapter):
        assert actual_adapter is adapter
        events.append("stack")
        return settled

    def settled():
        events.append("settled")

    async def finalize(actual_adapter, outputs, **kwargs):
        assert actual_adapter is adapter
        assert outputs is drawing.OUTPUTS
        assert kwargs["settled_checks"] == (settled,)
        events.append("finalize")
        return {"pdf": "finalized"}

    monkeypatch.setattr(drawing, "SOURCE", source)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "place_view", lambda *args, **kwargs: object())
    monkeypatch.setattr(drawing, "apply_view_configuration", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "assert_full_detail_view", lambda *args, **kwargs: None)
    monkeypatch.setattr(drawing, "_stack_dimensions", stack_dimensions)
    monkeypatch.setattr(drawing, "add_property_linked_note", linked_note)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"pdf": "finalized"}
    assert events == ["open", "stack", "press-note", "finalize"]
    assert note_calls == [
        (adapter, "Drawing Notes", *drawing.PRESS_NOTE_XY, drawing.PRESS_NOTE_CHAR_HEIGHT)
    ]

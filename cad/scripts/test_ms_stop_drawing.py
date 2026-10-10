"""Offline observable contracts for the separate brass stop block and cover."""

from __future__ import annotations

import asyncio
import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_common as drawing_common
import build_ms_stop_block as block
import build_ms_stop_plate as plate
import draw_ms_stop_block as block_drawing
import draw_ms_stop_plate as plate_drawing
import ms_stick_spec as stick
import ms_stop_spec as spec
import vn_ms_stop_plate_screw_spec as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import DRILL_POINT_H


def test_shared_frame_and_open_rebate_closure() -> None:
    assert (spec.BLOCK_LENGTH, spec.BLOCK_HEIGHT, spec.BLOCK_DEPTH) == (21.0, 14.1, 11.0)
    assert (spec.PLATE_Z_MIN, spec.PLATE_Z_MAX, spec.PLATE_THICKNESS) == (-1.0, 0.0, 1.0)
    assert spec.TOTAL_DEPTH == 12.0
    assert (spec.WINDOW_Z_MIN, spec.WINDOW_Z_MAX) == (0.0, 8.4)
    assert (spec.WINDOW_Y_MIN, spec.WINDOW_Y_MAX) == pytest.approx((8.6, 12.0))
    assert spec.WINDOW_Y_MAX + spec.ROOF_THICKNESS == spec.BLOCK_HEIGHT
    assert spec.ROOF_THICKNESS == 2.1
    assert spec.ROOF_THICKNESS - 0.51 >= 1.5
    assert "WindowFloor" not in set().union(*spec.BLOCK_DRAWING_DIMENSIONS.values())
    assert "RoofThickness" in spec.BLOCK_DRAWING_DIMENSIONS["RoofThicknessReference"]
    assert spec.BACK_WALL_THICKNESS == pytest.approx(2.6)
    assert spec.ROOF_END_CHAMFER == 1.0 and spec.ROOF_CHAMFER_ANGLE == 45.0
    assert spec.STOP_MARK == 2.0
    assert block.MATERIAL == plate.MATERIAL == "Brass"


def test_native_taps_and_plate_clearance_follow_stock_screws() -> None:
    assert screw.SKU == "90114A124"
    assert spec.PLATE_SCREW_THREAD == screw.THREAD
    assert spec.PLATE_SCREW_MAJOR_DIA == screw.MAJOR_DIA
    assert spec.PLATE_SCREW_LENGTH == screw.LENGTH
    assert spec.PLATE_TAP_SPEC.kind == "tapped_bottoming"
    assert spec.PLATE_TAP_SPEC.size == screw.THREAD
    assert spec.PLATE_TAP_SPEC.end == "blind"
    assert spec.PLATE_TAP_SPEC.depth_mm == spec.PLATE_TAP_DRILL_DEPTH == 7.8
    assert spec.PLATE_TAP_SPEC.overrides_mm["ThreadDepth"] == spec.PLATE_TAP_THREAD_DEPTH == 6.3
    assert spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"] == spec.PLATE_TAP_DRILL_DIA == 1.85
    assert spec.PLATE_CLEARANCE_SPEC.overrides_mm["HoleDiameter"] == spec.PLATE_CLEARANCE_DIA == 2.4
    assert spec.THUMB_TAP_SPEC.kind == "tapped" and spec.THUMB_TAP_SPEC.size == "#4-40"
    # Through-all would drill the opposite roof as well as the thick floor.
    assert spec.THUMB_TAP_SPEC.end == "through_next"
    assert (spec.THUMB_AXIS_X, spec.THUMB_AXIS_Z) == (10.5, 4.2)
    assert spec.THUMB_HOLE_POINTS == ((10.5, 0.0, 4.2),)
    assert spec.THUMB_HOLE_NORMAL == (0.0, -1.0, 0.0)
    assert spec.PLATE_HOLE_XS == (3.5, 17.5) and spec.PLATE_HOLE_Y == 4.0
    assert spec.PLATE_HOLE_PITCH == 14.0
    assert spec.PLATE_HOLE_NORMAL == (0.0, 0.0, -1.0)
    assert spec.BLOCK_PLATE_HOLE_POINTS == ((3.5, 4.0, 0.0), (17.5, 4.0, 0.0))
    assert spec.PLATE_HOLE_POINTS == ((3.5, 4.0, -1.0), (17.5, 4.0, -1.0))


def test_receiver_engagement_and_separation_are_real_geometry() -> None:
    assert spec.PLATE_SCREW_PENETRATION == pytest.approx(5.35)
    assert 1.5 * screw.MAJOR_DIA < spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_THREAD_DEPTH
    assert spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_DRILL_DEPTH
    tip = spec.PLATE_TAP_DRILL_DEPTH + spec.PLATE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
    assert spec.PLATE_TAP_TIP_Z == pytest.approx(tip)
    assert spec.BLOCK_DEPTH - tip > 2.0
    assert spec.PLATE_HOLE_Y + screw.MAJOR_DIA / 2.0 < spec.WINDOW_Y_MIN - 2.0
    for x in spec.PLATE_HOLE_XS:
        assert abs(x - spec.THUMB_AXIS_X) - (screw.MAJOR_DIA + spec.THUMB_MAJOR_DIA) / 2.0 > 2.0


def test_print_worst_joint_stack_preserves_bottoming_tap_and_ligaments() -> None:
    assert spec.PLATE_THICKNESS_MIN == pytest.approx(0.9)
    assert spec.PLATE_THICKNESS_MAX == pytest.approx(1.1)
    assert spec.PLATE_FULL_THREAD_MIN == pytest.approx(5.79)
    assert spec.PLATE_SCREW_PENETRATION_MAX == pytest.approx(5.704)
    assert spec.PLATE_SCREW_PENETRATION_MIN >= 1.5 * screw.MAJOR_DIA
    assert spec.PLATE_SCREW_PENETRATION_MAX < spec.PLATE_FULL_THREAD_MIN
    assert spec.PLATE_TAP_LEAD_MIN == pytest.approx(0.48)
    assert spec.PLATE_TAP_LEAD_MIN >= screw.PITCH
    assert spec.PLATE_TAP_BACK_WALL_MIN == pytest.approx(1.59416, abs=1e-5)
    assert spec.PLATE_TAP_BACK_WALL_MIN >= 1.5
    assert spec.ROOF_THICKNESS_MIN == pytest.approx(1.59)
    assert spec.PLATE_TAP_WINDOW_WEB_MIN == pytest.approx(2.2878)
    assert spec.PLATE_TAP_END_WEB_MIN == pytest.approx(1.7978)
    assert spec.PLATE_RADIAL_CLEARANCE_MIN == pytest.approx(0.1078)
    assert spec.ROOF_OPEN_END_EDGE == pytest.approx(1.1)


def test_matched_pair_uses_functional_positions_and_a_real_shop_sequence() -> None:
    assert spec.PLATE_HOLE_POSITION_TOLERANCE_MM == 0.1
    assert all(block_point[:2] == plate_point[:2] for block_point, plate_point
               in zip(spec.BLOCK_PLATE_HOLE_POINTS, spec.PLATE_HOLE_POINTS, strict=True))
    assert len(spec.BLOCK_DRAWING_NOTES.splitlines()) <= 4
    assert len(spec.PLATE_DRAWING_NOTES.splitlines()) <= 4
    assert "BLIND" not in spec.PLATE_DRAWING_NOTES
    assert "BOTTOMING" not in spec.PLATE_DRAWING_NOTES
    assert "PilotDrillDiameter" in spec.PLATE_DRAWING_DIMENSIONS["PilotDrillReference"]
    assert spec.PLATE_DRAWING_VALUES_BY_NAME["PilotDrillDiameter"] == (
        spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"]
    )

def test_window_keeps_functional_clearance_at_printed_size_limits() -> None:
    window_lower, _window_upper = spec.WINDOW_SIZE_TOLERANCE_MM
    assert spec.WINDOW_WIDTH + window_lower - (stick.BODY_WIDTH + stick.BODY_FIT_TOLERANCE_MM) >= 0.3 - 1e-9
    assert spec.WINDOW_HEIGHT + window_lower - (stick.BODY_THICKNESS + stick.BODY_FIT_TOLERANCE_MM) >= 0.3 - 1e-9
    assert spec.PLATE_CLEARANCE_DIA > screw.MAJOR_DIA


def test_analytic_volume_has_no_merged_thumbscrew_or_hidden_extra_wall() -> None:
    assert spec.BLOCK_CHAMFER_VOLUME == spec.ROOF_END_CHAMFER**2 * spec.BLOCK_DEPTH
    assert spec.THUMB_HOLE_VOLUME == pytest.approx(math.pi * (spec.THUMB_TAP_DRILL / 2.0)**2 * spec.FLOOR_THICKNESS)
    assert spec.BLOCK_FINISHED_VOLUME == pytest.approx(
        spec.BLOCK_VOLUME - spec.WINDOW_VOLUME - spec.BLOCK_CHAMFER_VOLUME - spec.THUMB_HOLE_VOLUME - spec.PLATE_TAP_VOLUME)
    assert spec.PLATE_FINISHED_VOLUME == pytest.approx(
        spec.PLATE_VOLUME - spec.PLATE_CHAMFER_VOLUME - spec.PLATE_HOLE_VOLUME)
    assert 0.0 < spec.BLOCK_FINISHED_VOLUME < spec.BLOCK_VOLUME
    assert 0.0 < spec.PLATE_FINISHED_VOLUME < spec.PLATE_VOLUME


@pytest.mark.parametrize("builder,drawing,dimensions,precision,values,stem", [
    (block, block_drawing, spec.BLOCK_DRAWING_DIMENSIONS, spec.BLOCK_DRAWING_PRECISION_BY_NAME, spec.BLOCK_DRAWING_VALUES_BY_NAME, "ms-stop-block"),
    (plate, plate_drawing, spec.PLATE_DRAWING_DIMENSIONS, spec.PLATE_DRAWING_PRECISION_BY_NAME, spec.PLATE_DRAWING_VALUES_BY_NAME, "ms-stop-plate"),
])
def test_each_sheet_imports_the_complete_model_contract(builder, drawing, dimensions, precision, values, stem) -> None:
    assert builder.PART_NAME == drawing.PART_STEM == stem
    assert DRAWINGS_BY_NAME[stem.replace("-", "_")].script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.name == f"{stem}.SLDDRW" and drawing.PDF.name == f"{stem}.pdf"
    assert builder.DRAWING_DIMENSIONS is dimensions
    marked = set().union(*dimensions.values())
    keeps = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    if hasattr(drawing, "BOTTOM_KEEP"):
        keeps |= set(drawing.BOTTOM_KEEP)
    assert marked == keeps == set(precision) == set(values)
    assert all(places == 2 for places in precision.values())
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]
    assert not any(character.isdigit() for character in spec.BLOCK_DRAWING_NOTES + spec.PLATE_DRAWING_NOTES)


@pytest.mark.parametrize("module", [spec, block_drawing, plate_drawing])
def test_no_com_in_spec_or_render_time_size_overrides(module) -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    if module is spec:
        imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(name.startswith(("build_", "solidworks", "_common", "_drawing")) for name in imports)
    else:
        calls = {node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
                 for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, (ast.Attribute, ast.Name))}
        assert not calls & {"SetPrecision3", "set_dimension_precision", "SetValues", "set_hole_callout_precision", "add_gdt_frame", "add_datum_tag"}


class _StopViewTransform:
    """4:1 orthographic affine map, centred on the part's bounding box."""

    def __init__(self, orientation, position, scale, model_center, angle=0.0):
        self.orientation = orientation
        self.position = position
        self.scale = scale[0] / scale[1]
        self.model_center = model_center
        self.angle = angle

    def apply(self, xyz):
        x, y, z = (value - center for value, center in zip(
            xyz, self.model_center, strict=True
        ))
        sx, sy = self.position
        if self.orientation == "*Back":
            horizontal, vertical, depth = -x, y, -z
        elif self.orientation == "*Bottom":
            horizontal, vertical, depth = x, z, -y
        elif self.orientation == "*Left":
            horizontal, vertical, depth = z, y, -x
        else:
            raise AssertionError(f"unexpected orthographic view: {self.orientation}")
        cosine, sine = math.cos(self.angle), math.sin(self.angle)
        return (
            sx + self.scale * (cosine * horizontal - sine * vertical),
            sy + self.scale * (sine * horizontal + cosine * vertical),
            self.scale * depth,
        )


class _StopView:
    """Expose the native IView properties; an Angle put has no success retval."""

    def __init__(self, orientation, position, scale, model_center, *, rotation_readback=None):
        self.orientation = orientation
        self.Position = position
        self.ScaleRatio = scale
        self.model_center = model_center
        self.rotation_readback = rotation_readback
        self.angle_puts = []
        self._angle = 0.0

    @property
    def Angle(self):  # noqa: N802 - COM property name
        return self._angle

    @Angle.setter
    def Angle(self, value):  # noqa: N802 - COM property name
        self.angle_puts.append(value)
        # Refusal is a recorded put whose authoritative readback stays wrong.
        self._angle = value if self.rotation_readback is None else self.rotation_readback

    @property
    def ModelToViewTransform(self):  # noqa: N802 - COM property name
        return _StopViewTransform(
            self.orientation, self.Position, self.ScaleRatio, self.model_center, self.Angle
        )


@pytest.mark.parametrize("readback", [math.pi, -math.pi, 3.0 * math.pi])
def test_bottom_rotation_accepts_equivalent_native_half_turns(readback) -> None:
    view = _StopView("*Bottom", block_drawing.BOTTOM_CENTER, (4.0, 1.0), (0.0, 0.0, 0.0),
                     rotation_readback=readback)
    rebuilds = []
    adapter = SimpleNamespace(currentModel=SimpleNamespace(
        EditRebuild3=lambda: rebuilds.append(True) or True
    ))
    block_drawing._orient_bottom_view(adapter, view)
    assert view.angle_puts == [math.pi]
    assert rebuilds == [True]
    origin = view.ModelToViewTransform.apply((0.0, 0.0, 0.0))
    east = view.ModelToViewTransform.apply((0.001, 0.0, 0.0))
    rear = view.ModelToViewTransform.apply((0.0, 0.0, 0.001))
    assert east[0] < origin[0] and east[1] == pytest.approx(origin[1])
    assert rear[1] < origin[1] and rear[0] == pytest.approx(origin[0])


@pytest.mark.parametrize("readback", [0.0, math.pi / 2.0, math.nan, math.inf])
def test_bottom_rotation_refuses_unapplied_or_invalid_native_readback(readback) -> None:
    view = _StopView("*Bottom", block_drawing.BOTTOM_CENTER, (4.0, 1.0), (0.0, 0.0, 0.0),
                     rotation_readback=readback)
    adapter = SimpleNamespace(currentModel=SimpleNamespace(EditRebuild3=lambda: True))
    with pytest.raises(RuntimeError, match="underside rotation did not take"):
        block_drawing._orient_bottom_view(adapter, view)
    assert view.angle_puts == [math.pi]


class _StopMathPoint:
    def __init__(self, xyz):
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):  # noqa: N802 - COM member name
        return _StopMathPoint(transform.apply(self.ArrayData))


class _StopMathUtility:
    def __init__(self):
        self.points = []

    def CreatePoint(self, values):  # noqa: N802 - COM member name
        # Keep the real double_array marshaling, including its no-pywin32
        # fallback. No COM server is instantiated by constructing a VARIANT.
        xyz = tuple(getattr(values, "value", values))
        self.points.append(xyz)
        return _StopMathPoint(xyz)


@pytest.mark.parametrize("drawing,cases", [
    (block_drawing, [
        ("two cover blind taps", "*Back", (0.018425, 0.004, 0.0), (0.1433, 0.1728)),
        ("thumbscrew tap through floor", "*Bottom",
         (0.0116305, 0.0, 0.0042), (0.170478, 0.0852)),
        ("cover mating face", "*Left", (0.0105, 0.01255, 0.0), (0.293, 0.207)),
    ]),
    (plate_drawing, [
        ("two cover clearance holes", "*Back", (0.0187, 0.004, -0.001), (0.1422, 0.1578)),
    ]),
], ids=["block-plate-and-subsequent-thumb", "plate-clearance"])
def test_build_projects_metre_hole_mouths_into_the_native_callout_view(
    monkeypatch, tmp_path, drawing, cases
) -> None:
    """Exercise both builds' real projection and callout handoff, not native
    edge selection. The fake seat supplies only known affine math and replaces
    unrelated drawing setup/import/export; it never launches SolidWorks."""
    source = tmp_path / f"{drawing.PART_STEM}.SLDPRT"
    source.write_bytes(b"offline source sentinel")
    monkeypatch.setattr(drawing, "SOURCE", source)
    utility = _StopMathUtility()

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=None)

    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(EditRebuild3=lambda: True), open_model=open_model,
        swApp=SimpleNamespace(GetMathUtility=lambda: utility),
    )
    model_center = (
        spec.BLOCK_LENGTH / 2000.0,
        spec.BLOCK_HEIGHT / 2000.0,
        (spec.PLATE_Z_MIN + spec.PLATE_Z_MAX) / 2000.0
        if drawing is plate_drawing else spec.BLOCK_DEPTH / 2000.0,
    )
    views = {}

    def place_view(adapter, path, orientation, x, y, *, scale):
        assert path == str(source)
        view = _StopView(orientation, (x, y), scale, model_center)
        views[orientation] = view
        return view

    def invoke(obj, _interface, member, *args):
        value = getattr(obj, member)
        return value(*args) if callable(value) else value

    # Leave model_point_in_view, _projection_frame and _project_through intact.
    # Only replace their raw dispatch boundary with the fake object's members.
    monkeypatch.setattr(drawing_common, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *a, **kw: (object(), object()))
    for name in (
        "read_required_properties", "stamp_drawing_summary",
        "set_hidden_lines_removed", "set_dimension_callouts",
        "assert_manufacturing_dimensions", "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *a, **kw: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *a, **kw: [])
    if drawing is block_drawing:
        monkeypatch.setattr(drawing, "_remove_general_thread_class", lambda *a: None)
    else:
        monkeypatch.setattr(drawing, "_style_pilot_diameter", lambda *a: None)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *a, **kw: True)
    callouts = []

    def add_callout(adapter, view, *, edge_xy, callout_xy, label, process=None):
        callouts.append((view, edge_xy, label))

    async def finalize(adapter, outputs, **kwargs):
        return {"slddrw": str(outputs.slddrw)}

    monkeypatch.setattr(drawing, "add_native_hole_callout", add_callout)
    if drawing is block_drawing:
        monkeypatch.setattr(
            drawing, "add_property_linked_callout",
            lambda adapter, view, *, edge_xy, **kw: callouts.append(
                (view, edge_xy, "cover mating face")
            ),
        )
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)
    assert asyncio.run(drawing.build(adapter)) == {"slddrw": str(drawing.OUTPUTS.slddrw)}
    # The displayed cover face is *Back: +X goes left, +Y goes up. Its
    # third-angle right view is unrotated *Left (+Z right, +Y up); its
    # third-angle underside must retain -X and send +Z down, not up.
    front, right = views["*Back"], views["*Left"]
    assert front.Position[1] == right.Position[1]
    center = model_center
    east = (center[0] + 0.001, center[1], center[2])
    high = (center[0], center[1] + 0.001, center[2])
    rear = (center[0], center[1], center[2] + 0.001)
    front_map, right_map = front.ModelToViewTransform, right.ModelToViewTransform
    assert front_map.apply(east)[0] < front_map.apply(center)[0]
    assert front_map.apply(high)[1] > front_map.apply(center)[1]
    assert right_map.apply(rear)[0] > right_map.apply(center)[0]
    assert right_map.apply(high)[1] == pytest.approx(front_map.apply(high)[1])
    if drawing is block_drawing:
        bottom = views["*Bottom"]
        bottom_map = bottom.ModelToViewTransform
        assert bottom.Position[0] == front.Position[0]
        assert bottom.Position[1] < front.Position[1]
        assert bottom_map.apply(east)[0] == pytest.approx(front_map.apply(east)[0])
        assert bottom_map.apply(rear)[1] < bottom_map.apply(center)[1]
        for x in (0.0, spec.BLOCK_LENGTH / 1000.0):
            point = (x, center[1], center[2])
            assert bottom_map.apply(point)[0] == pytest.approx(front_map.apply(point)[0])
    # Capture the entire block build before checking: the second (thumb) pick
    # must remain covered even when the preceding plate pick used wrong units.
    assert len(utility.points) == len(callouts) == len(cases)
    for xyz, (view, edge_xy, label), case in zip(
        utility.points, callouts, cases, strict=True
    ):
        expected_label, orientation, expected_xyz, expected_xy = case
        assert label == expected_label
        assert view is views[orientation]
        assert view.ScaleRatio == (4.0, 1.0)
        assert xyz == pytest.approx(expected_xyz)
        # These are the actual positive-X drill rims, on the visible mouth
        # face, not the hole centre or the opposite end of the drilled hole.
        if orientation == "*Left":
            mouth = (
                spec.BLOCK_LENGTH / 2.0,
                spec.WINDOW_Y_MAX + (spec.ROOF_THICKNESS - spec.ROOF_END_CHAMFER) / 2.0,
                spec.PLATE_Z_MAX,
            )
        elif orientation == "*Bottom":
            mouth = (spec.THUMB_AXIS_X + spec.THUMB_TAP_DRILL / 2.0,
                     spec.THUMB_HOLE_POINTS[0][1], spec.THUMB_AXIS_Z)
        else:
            holes, diameter = (
                (spec.PLATE_HOLE_POINTS, spec.PLATE_CLEARANCE_DIA)
                if drawing is plate_drawing
                else (spec.BLOCK_PLATE_HOLE_POINTS, spec.PLATE_TAP_DRILL_DIA)
            )
            mouth = (holes[1][0] + diameter / 2.0, holes[1][1], holes[1][2])
        assert xyz == pytest.approx(tuple(value / 1000.0 for value in mouth))
        assert edge_xy == pytest.approx(expected_xy)
        assert abs(edge_xy[0] - view.Position[0]) < 0.043
        assert abs(edge_xy[1] - view.Position[1]) < 0.029
        assert 0.0 < edge_xy[0] < 0.4318
        assert 0.0 < edge_xy[1] < 0.2794
        if orientation == "*Back":
            # The real failure was millimetres fed to metre math: at 4:1
            # Back reverses X around a shifted origin (~0.217), producing
            # -17.483 for the block or -18.583 for the cover, far off sheet.
            transform = view.ModelToViewTransform
            assert transform.apply((0.0, 0.0, 0.0))[0] == pytest.approx(0.217)
            wrong_units_x = transform.apply(mouth)[0]
            assert wrong_units_x < -70.0
            # The original failing caller picked the other rim. Preserve that
            # observed negative-X signature as well as the new left-sheet pick.
            original = (holes[0][0] + diameter / 2.0, holes[0][1], holes[0][2])
            assert transform.apply(original)[0] == pytest.approx(
                -18.583 if drawing is plate_drawing else -17.483
            )


def test_match_drilling_does_not_eliminate_absolute_end_ligament_limits() -> None:
    """Matched pair error cancels, but the source axes still locate drilled stock."""
    from _printed_tolerance import printed_band_mm

    length_band = printed_band_mm(spec.PLATE_DRAWING_PRECISION_BY_NAME["PlateLength"])
    maximum_drill = spec.PLATE_CLEARANCE_DIA + spec.DRILL_OVERSIZE_MM
    minimum_end_web = spec.BLOCK_LENGTH - length_band - (
        spec.PLATE_HOLE_XS[1] + spec.PLATE_HOLE_POSITION_TOLERANCE_MM + maximum_drill / 2.0
    )
    assert minimum_end_web >= 1.5
    assert spec.BLOCK_LENGTH - printed_band_mm(1) - (
        spec.PLATE_HOLE_XS[1] + spec.PLATE_HOLE_POSITION_TOLERANCE_MM + maximum_drill / 2.0
    ) < 1.5
    assert spec.BLOCK_LENGTH - spec.GENERAL_LINEAR_TOLERANCE_MM - (
        spec.PLATE_HOLE_XS[1] + spec.GENERAL_LINEAR_TOLERANCE_MM
        + spec.PLATE_SCREW_MAJOR_DIA / 2.0
    ) < 1.5


class _StopDisplay:
    def __init__(self, prefix, *, hole=True, kind=6, refusal=None):
        self.prefix = prefix
        self.hole = hole
        self.Type2 = kind
        self.refusal = refusal
        self._witness_visibility = 0
        self._leader_visibility = 0

    @property
    def WitnessVisibility(self):  # noqa: N802 - native property name
        return self._witness_visibility

    @WitnessVisibility.setter
    def WitnessVisibility(self, value):
        if self.refusal != "witness":
            self._witness_visibility = value

    @property
    def LeaderVisibility(self):  # noqa: N802 - native property name
        return self._leader_visibility

    @LeaderVisibility.setter
    def LeaderVisibility(self, value):
        if self.refusal != "leader":
            self._leader_visibility = value

    def IsHoleCallout(self):  # noqa: N802 - COM method name
        return self.hole

    def GetText(self, which):  # noqa: N802 - COM method name
        assert which == 5, "resolved prefix text would sever native variables"
        return self.prefix

    def SetText(self, which, text):  # noqa: N802 - COM method name
        assert which == 1
        if self.refusal != "prefix":
            self.prefix = text


@pytest.mark.parametrize("separator", ["-", " ", "", " - "])
def test_native_class_suppression_preserves_live_thread_drill_and_depth_variables(separator) -> None:
    definition = (
        "2X MATCH-DRILL WITH THE MATE\n"
        f"<hw-threaddesc>{separator}<hw-threadclass> <HOLE-DEPTH><hw-threaddepth>"
        "\n<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH><hw-holedpth>"
    )
    native = _StopDisplay(definition)
    block_drawing._remove_general_thread_class(native)
    assert "<hw-threadclass>" not in native.prefix
    for variable in ("hw-threaddesc", "hw-threaddepth", "hw-tapdrldia", "hw-holedpth"):
        assert f"<{variable}>" in native.prefix
    assert "MATCH-DRILL WITH THE MATE" in native.prefix
    assert native.prefix == definition.replace(f"{separator}<hw-threadclass>", "")


@pytest.mark.parametrize("native", [
    _StopDisplay("<hw-threadclass>", hole=False),
    _StopDisplay("2B"),
    _StopDisplay("<hw-threadclass><hw-threadclass>"),
    _StopDisplay("<hw-threadclass>", refusal="prefix"),
])
def test_native_class_suppression_refuses_non_native_unbound_or_rejected_text(native) -> None:
    with pytest.raises(RuntimeError):
        block_drawing._remove_general_thread_class(native)


@pytest.mark.parametrize("kind", [6, 2, 3, 5])
def test_pilot_callout_requires_model_diameter_and_hides_only_process_circle_ink(monkeypatch, kind) -> None:
    native = _StopDisplay("<MOD-DIAM>", hole=False, kind=kind)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: native)
    monkeypatch.setattr(plate_drawing, "dimension_name", lambda *a: "PilotDrillDiameter")
    if kind != 6:
        with pytest.raises(RuntimeError, match="native model diameter"):
            plate_drawing._style_pilot_diameter(object(), [annotation])
        assert native.prefix == "<MOD-DIAM>"
    else:
        plate_drawing._style_pilot_diameter(object(), [annotation])
        assert native.prefix == "2X <MOD-DIAM>"
        assert native.WitnessVisibility == native.LeaderVisibility == 3


@pytest.mark.parametrize("refusal", ["witness", "leader", "prefix"])
def test_pilot_callout_refuses_unapplied_native_style_or_prefix(monkeypatch, refusal) -> None:
    native = _StopDisplay("<MOD-DIAM>", hole=False, refusal=refusal)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: native)
    monkeypatch.setattr(plate_drawing, "dimension_name", lambda *a: "PilotDrillDiameter")
    with pytest.raises(RuntimeError, match="did not persist"):
        plate_drawing._style_pilot_diameter(object(), [annotation])


def test_match_drill_callouts_identify_the_current_mate_registry_rows() -> None:
    import _config

    assert "MS-STOP-PLATE" in block_drawing.COVER_HOLE_PROCESS
    assert _config.parts("ms-stop-plate")["number"] in block_drawing.COVER_HOLE_PROCESS
    pilot = plate_drawing.DIMENSION_CALLOUTS["PilotDrillDiameter"]
    assert "MS-STOP-BLOCK" in pilot
    assert _config.parts("ms-stop-block")["number"] in pilot
    assert spec.PLATE_DRAWING_VALUES_BY_NAME["PilotDrillDiameter"] == (
        spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"]
    )

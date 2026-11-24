"""Offline observable contracts for the separate brass stop block and cover."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import _drawing_projection as drawing_projection
import _dimensions as dimensions
import _sketch as sketch
import ms_stop_geom as stop_geom
import build_ms_stop_block as block
import build_ms_stop_plate as plate
import draw_ms_stop_block as block_drawing
import draw_ms_stop_plate as plate_drawing
import ms_stick_spec as stick
import ms_stop_spec as spec
import _mcmaster_90114a124 as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import DRILL_POINT_H
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import inside_corner_radius_mm, printed_band_mm


def _inch(value_in: float) -> float:
    return value_in * 25.4


def test_shared_frame_and_open_rebate_closure() -> None:
    # Issue #290: both parts print decimal inch; each nominal is the exact
    # millimetre decimal of its printed inch value.
    assert spec.UNIT == "in"
    for got, inch in (
        (spec.BLOCK_LENGTH, 0.84), (spec.BLOCK_HEIGHT, 0.56), (spec.BLOCK_DEPTH, 0.48),
        (spec.PLATE_THICKNESS, 0.040), (spec.WINDOW_WIDTH, 0.330), (spec.WINDOW_HEIGHT, 0.134),
        (spec.ROOF_THICKNESS, 0.09), (spec.ROOF_END_CHAMFER, 0.04), (spec.BACK_WALL_THICKNESS, 0.15),
        (spec.RELIEF_DEPTH, 0.05), (spec.RELIEF_HEIGHT, 0.06),
    ):
        assert got == pytest.approx(_inch(inch), rel=0.0, abs=1e-9)
    assert (spec.PLATE_Z_MIN, spec.PLATE_Z_MAX) == (-spec.PLATE_THICKNESS, 0.0)
    assert spec.TOTAL_DEPTH == pytest.approx(spec.BLOCK_DEPTH + spec.PLATE_THICKNESS)
    assert (spec.WINDOW_Z_MIN, spec.WINDOW_Z_MAX) == (0.0, spec.WINDOW_WIDTH)
    assert (spec.WINDOW_Y_MIN, spec.WINDOW_Y_MAX) == pytest.approx((8.5344, 11.938))
    assert spec.WINDOW_Y_MAX + spec.ROOF_THICKNESS == pytest.approx(spec.BLOCK_HEIGHT)
    assert "WindowFloor" not in set().union(*spec.BLOCK_DRAWING_DIMENSIONS.values())
    assert "RoofThickness" in spec.BLOCK_DRAWING_DIMENSIONS["RoofThicknessReference"]
    assert spec.ROOF_CHAMFER_ANGLE == 45.0
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
    assert spec.PLATE_TAP_SPEC.depth_mm == spec.PLATE_TAP_DRILL_DEPTH == pytest.approx(_inch(0.300))
    assert spec.PLATE_TAP_SPEC.overrides_mm["ThreadDepth"] == spec.PLATE_TAP_THREAD_DEPTH == pytest.approx(_inch(0.250))
    # #49 (.073) tap drill and #2 close (.094) clearance.
    assert spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"] == spec.PLATE_TAP_DRILL_DIA == pytest.approx(_inch(0.073))
    assert spec.PLATE_CLEARANCE_SPEC.overrides_mm["HoleDiameter"] == spec.PLATE_CLEARANCE_DIA == pytest.approx(_inch(0.094))
    assert spec.THUMB_TAP_SPEC.kind == "tapped" and spec.THUMB_TAP_SPEC.size == "#4-40"
    # Through-all would drill the opposite roof as well as the thick floor.
    assert spec.THUMB_TAP_SPEC.end == "through_next"
    assert (spec.THUMB_AXIS_X, spec.THUMB_AXIS_Z) == pytest.approx((_inch(0.42), _inch(0.17)))
    assert spec.WINDOW_Z_MIN < spec.THUMB_AXIS_Z < spec.WINDOW_Z_MAX
    assert spec.THUMB_HOLE_POINTS == ((spec.THUMB_AXIS_X, 0.0, spec.THUMB_AXIS_Z),)
    assert spec.THUMB_HOLE_NORMAL == (0.0, -1.0, 0.0)
    assert spec.PLATE_HOLE_XS == pytest.approx((_inch(0.150), _inch(0.690)))
    assert spec.PLATE_HOLE_Y == pytest.approx(_inch(0.160))
    assert spec.PLATE_HOLE_PITCH == pytest.approx(_inch(0.540))
    assert spec.PLATE_HOLE_NORMAL == (0.0, 0.0, -1.0)
    assert spec.BLOCK_PLATE_HOLE_POINTS == tuple((x, spec.PLATE_HOLE_Y, 0.0) for x in spec.PLATE_HOLE_XS)
    assert spec.PLATE_HOLE_POINTS == tuple((x, spec.PLATE_HOLE_Y, spec.PLATE_Z_MIN) for x in spec.PLATE_HOLE_XS)


def test_receiver_engagement_and_separation_are_real_geometry() -> None:
    assert spec.PLATE_SCREW_PENETRATION == pytest.approx(5.334)
    assert 1.5 * screw.MAJOR_DIA < spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_THREAD_DEPTH
    assert spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_DRILL_DEPTH
    tip = spec.PLATE_TAP_DRILL_DEPTH + spec.PLATE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
    assert spec.PLATE_TAP_TIP_Z == pytest.approx(tip)
    assert spec.BLOCK_DEPTH - tip > WALL_TARGET_MM
    assert spec.PLATE_HOLE_Y + screw.MAJOR_DIA / 2.0 < spec.WINDOW_Y_MIN - WALL_TARGET_MM
    for x in spec.PLATE_HOLE_XS:
        assert abs(x - spec.THUMB_AXIS_X) - (screw.MAJOR_DIA + spec.THUMB_MAJOR_DIA) / 2.0 > WALL_TARGET_MM


def test_print_worst_joint_stack_preserves_bottoming_tap_and_ligaments() -> None:
    # The sheet at the title block's .040 ±.005 (fit audit 2026-11-23,
    # MHA-MS-03.plate_thickness): reach .195-.225 against 1.5 D .129 and
    # the .245 full thread.
    assert spec.PLATE_THICKNESS_MIN == pytest.approx(0.889)
    assert spec.PLATE_THICKNESS_MAX == pytest.approx(1.143)
    assert spec.PLATE_FULL_THREAD_MIN == pytest.approx(6.223)
    assert spec.PLATE_SCREW_PENETRATION_MAX == pytest.approx(5.715)
    assert spec.PLATE_SCREW_PENETRATION_MIN >= 1.5 * screw.MAJOR_DIA
    assert spec.PLATE_SCREW_PENETRATION_MAX < spec.PLATE_FULL_THREAD_MIN
    assert spec.PLATE_TAP_LEAD_MIN == pytest.approx(1.016)
    assert spec.PLATE_TAP_LEAD_MIN >= screw.PITCH
    assert spec.PLATE_TAP_BACK_WALL_MIN == pytest.approx(3.60342, abs=1e-5)
    assert spec.ROOF_THICKNESS_MIN == pytest.approx(2.032)
    # The plate stations ride the title block's .XXX (L2): each web loses .001.
    # The rebate's +.010/0 (owner ruling 2026-11-21) leaves the window web
    # .0967 against the .080 target (.1027 at +.004/0).
    assert spec.PLATE_TAP_WINDOW_WEB_MIN == pytest.approx(2.45491)
    assert spec.PLATE_TAP_WINDOW_WEB_MIN >= WALL_TARGET_MM
    assert spec.PLATE_TAP_END_WEB_MIN == pytest.approx(2.30251)
    assert spec.PLATE_TAP_MAJOR_DIA_MAX == pytest.approx(0.0887 * 25.4)
    assert spec.PLATE_TAP_MAJOR_DIA_MAX > screw.MAJOR_DIA
    assert spec.WINDOW_BACK_WALL_MIN == pytest.approx(3.556)
    assert spec.BLOCK_DEPTH_MIN == pytest.approx(11.938)
    assert spec.PLATE_CLEARANCE_END_WEB_MIN == pytest.approx(2.1844)
    assert spec.PLATE_CLEARANCE_HEAD_WEB_MIN == pytest.approx(8.5344)
    assert spec.PLATE_RADIAL_CLEARANCE_MIN == pytest.approx(0.1016)
    assert spec.ROOF_OPEN_END_EDGE == pytest.approx(1.27)


def test_every_worst_case_wall_meets_the_inch_rule_17_target() -> None:
    """Rule 17 on the inch sheet: .080 target, .060 floor. Each wall and web
    at its printed bands meets the target, so no sheet states a shortfall."""
    assert (WALL_TARGET_MM, WALL_FLOOR_MM) == pytest.approx((_inch(0.080), _inch(0.060)))
    walls = (
        spec.ROOF_THICKNESS_MIN, spec.WINDOW_BACK_WALL_MIN, spec.PLATE_TAP_BACK_WALL_MIN,
        spec.PLATE_TAP_END_WEB_MIN, spec.PLATE_TAP_WINDOW_WEB_MIN,
        spec.PLATE_CLEARANCE_END_WEB_MIN, spec.PLATE_CLEARANCE_HEAD_WEB_MIN,
    )
    assert min(walls) == pytest.approx(WALL_TARGET_MM)  # the roof, exactly .080
    assert all(wall >= WALL_TARGET_MM - 1e-9 for wall in walls)
    for stem in ("ms-stop-block", "ms-stop-plate"):
        assert "machinist_exceptions" not in _config.parts(stem)
    assert "RoofThickness" not in block_drawing.DIMENSION_CALLOUTS
    for name in ("ROOF_WALL_CALLOUT", "PLATE_TAP_WEB_LINES", "PLATE_CLEARANCE_WEB_LINE"):
        assert not hasattr(spec, name)


def test_drilled_holes_are_plus_four_thou_and_the_rebate_plus_ten() -> None:
    assert spec.DRILL_OVERSIZE_MM == pytest.approx(_inch(0.004))
    # Owner ruling 2026-11-21: "MS-02 rebate opens to +.010/0 now".
    assert spec.WINDOW_SIZE_TOLERANCE_MM == pytest.approx((0.0, _inch(0.010)))


def test_hole_wizard_callouts_print_three_places_by_native_variable() -> None:
    # Run 1119 printed the #49 and #43 tap drills as .07/.09; every native
    # length variable of each callout prints .XXX (.073, .089, .094).
    assert block_drawing.COVER_TAP_PRECISION == {
        "hw-tapdrldia": 3, "hw-tapdrldepth": 3, "hw-threaddepth": 3,
    }
    assert block_drawing.THUMB_TAP_PRECISION == {"hw-tapdrldia": 3}
    assert plate_drawing.CLEARANCE_PRECISION == {"hw-diam": 3}
    assert spec.HOLE_LINEAR_TOLERANCE_MM == pytest.approx(printed_band_mm(3, unit="in"))
    for size_mm, printed in ((spec.PLATE_TAP_DRILL_DIA, ".073"), (spec.THUMB_TAP_DRILL, ".089"),
                             (spec.PLATE_CLEARANCE_DIA, ".094")):
        assert f"{size_mm / 25.4:.3f}".lstrip("0") == printed


def test_matched_pair_uses_functional_positions_and_a_real_shop_sequence() -> None:
    # Plain clearance stations ride the title block's .XXX (L2 ruling).
    assert spec.PLATE_HOLE_POSITION_TOLERANCE_MM == pytest.approx(_inch(0.005))
    assert spec.PLATE_THICKNESS_TOLERANCE_MM == pytest.approx(_inch(0.005))
    assert all(block_point[:2] == plate_point[:2] for block_point, plate_point
               in zip(spec.BLOCK_PLATE_HOLE_POINTS, spec.PLATE_HOLE_POINTS, strict=True))


def test_window_keeps_functional_clearance_at_printed_size_limits() -> None:
    # The window's own +.010/0 band and the stick's .XXX leave .010 of side
    # and .004 of face clearance at the tightest limits. Owner ruling
    # 2026-11-20 (#2441): "B", the stick keeps the 1/8 flat's .125 and the
    # .330 x .134 rebate stays. Owner ruling 2026-11-21 opened the band from
    # +.004/0 to +.010/0: the least clearances stay, the largest grow to
    # .030 side and .024 face; the thumb screw seats the stick on the roof.
    window_lower, window_upper = spec.WINDOW_SIZE_TOLERANCE_MM
    assert spec.WINDOW_WIDTH + window_lower - (stick.BODY_WIDTH + stick.BODY_FIT_TOLERANCE_MM) == pytest.approx(0.254)
    assert spec.WINDOW_HEIGHT + window_lower - (stick.BODY_THICKNESS + stick.BODY_FIT_TOLERANCE_MM) == pytest.approx(0.1016)
    assert spec.WINDOW_WIDTH + window_upper - (stick.BODY_WIDTH - stick.BODY_FIT_TOLERANCE_MM) == pytest.approx(_inch(0.030))
    assert spec.WINDOW_HEIGHT + window_upper - (stick.BODY_THICKNESS - stick.BODY_FIT_TOLERANCE_MM) == pytest.approx(_inch(0.024))
    assert spec.PLATE_CLEARANCE_DIA > screw.MAJOR_DIA


def test_analytic_volume_has_no_merged_thumbscrew_or_hidden_extra_wall() -> None:
    assert spec.BLOCK_CHAMFER_VOLUME == spec.ROOF_END_CHAMFER**2 * spec.BLOCK_DEPTH
    assert spec.THUMB_HOLE_VOLUME == pytest.approx(math.pi * (spec.THUMB_TAP_DRILL / 2.0)**2 * spec.FLOOR_THICKNESS)
    assert spec.BLOCK_FINISHED_VOLUME == pytest.approx(
        spec.BLOCK_VOLUME - spec.WINDOW_VOLUME - spec.RELIEF_VOLUME - spec.BLOCK_CHAMFER_VOLUME
        - spec.THUMB_HOLE_VOLUME - spec.PLATE_TAP_VOLUME)
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
    # .XXX for the rebate, the matched pair's stations and cover thickness;
    # whole-degree angles.
    three = ({"WindowWidth", "WindowHeight", *spec.PLATE_LOCATION_DIMENSIONS}
             if builder is block
             else {"PlateThickness", *spec.PLATE_LOCATION_DIMENSIONS})
    assert {name: places for name, places in precision.items() if places != 2} == {
        "RoofChamferAngle": 0, **dict.fromkeys(three, 3),
    }
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]


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
        ("two cover blind taps", "*Back", (0.0184531, 0.004064, 0.0), (0.1238596, 0.172808)),
        ("thumbscrew tap through floor", "*Bottom",
         (0.0117985, 0.0, 0.004318), (0.150478, 0.080112)),
        ("cover mating face", "*Left", (0.010668, 0.012573, 0.0), (0.290616, 0.206844)),
    ]),
    (plate_drawing, [
        ("two cover clearance holes", "*Back", (0.0183701441, 0.0032198559, -0.001016), (0.1441914, 0.1544314)),
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
    monkeypatch.setattr(drawing, "_add_rebate_slide_finish", lambda adapter, view: None, raising=False)
    utility = _StopMathUtility()

    def open_model(path):
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
    monkeypatch.setattr(drawing_projection, "_com_invoke", invoke)
    monkeypatch.setattr(drawing, "place_view", place_view)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *a, **kw: (object(), object()))
    for name in (
        "read_required_properties", "stamp_drawing_summary",
        "set_hidden_lines_removed", "set_dimension_callouts",
        "add_property_linked_note",
    ):
        # The plate prints no dimension callout (its thickness links no note).
        if hasattr(drawing, name):
            monkeypatch.setattr(drawing, name, lambda *a, **kw: None)
    notes = []
    monkeypatch.setattr(drawing, "add_note",
                        lambda adapter, text, x, y: notes.append((text, (x, y))) or object())
    native_contracts = []
    monkeypatch.setattr(
        drawing, "assert_manufacturing_dimensions",
        lambda *args, **kwargs: native_contracts.append(kwargs),
    )
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *a, **kw: [])
    precisions = {}
    monkeypatch.setattr(drawing, "set_hole_callout_precision",
                        lambda display, places, *, label: precisions.update({label: places}))
    if drawing is block_drawing:
        monkeypatch.setattr(drawing, "_remove_general_thread_class", lambda *a, **kw: None)
        monkeypatch.setattr(drawing, "_assert_reference_dimensions", lambda *a: None)
    else:
        monkeypatch.setattr(drawing, "_append_callout_lines", lambda *a: None)
        monkeypatch.setattr(drawing, "_style_plate_chamfer", lambda *a: None)
        monkeypatch.setattr(drawing, "_outside_arrow", lambda display: None)
    labelled = []
    monkeypatch.setattr(drawing, "_label_locating_edges", lambda adapter, view: labelled.append(view))
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *a, **kw: True)
    callouts = []

    callout_positions = {}

    def add_callout(adapter, view, *, edge_xy, callout_xy, label, process=None):
        callouts.append((view, edge_xy, label))
        callout_positions[label] = callout_xy

    def finalize(adapter, outputs, **kwargs):
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
    assert drawing.build(adapter) == {"slddrw": str(drawing.OUTPUTS.slddrw)}
    if drawing is block_drawing:
        assert notes == [(block_drawing.REBATE_NOTE, block_drawing.REBATE_NOTE_XY)]
    else:
        assert notes == [(plate_drawing.MATCHED_PAIR_NOTE, plate_drawing.MATCHED_PAIR_NOTE_XY)]
    assert len(native_contracts) == 1
    bands = native_contracts[0].get("bands") or {}
    if drawing is block_drawing:
        assert not set(bands) & (spec.PLATE_LOCATION_DIMENSIONS | spec.BLOCK_REFERENCE_DIMENSIONS)
        assert bands == {name: spec.WINDOW_SIZE_TOLERANCE_MM for name in ("WindowWidth", "WindowHeight")}
    else:
        # The plate carries no native band: its thickness takes the title block.
        assert bands == {}
    # The displayed cover face is *Back: +X goes left, +Y goes up. Its
    # third-angle right view is unrotated *Left (+Z right, +Y up); its
    # third-angle underside must retain -X and send +Z down, not up.
    front, right = views["*Back"], views["*Left"]
    assert labelled == [front]
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
        assert front.Position[0] == 0.155
        assert max(bottom_map.apply((x, 0.0, 0.0))[0] for x in (
            0.0, spec.BLOCK_LENGTH / 1000.0
        )) == pytest.approx(0.197672)
        assert block_drawing.BOTTOM_KEEP["ThumbFromEnd"][0] == 0.175
        assert block_drawing.BOTTOM_KEEP["ThumbFromEnd"][0] - bottom.Position[0] > 0.010
        assert callout_positions["thumbscrew tap through floor"] == (0.060, 0.056)
        assert callout_positions["two cover blind taps"] == (0.072, 0.127)
        assert precisions == {
            "two cover blind taps": drawing.COVER_TAP_PRECISION,
            "thumbscrew tap through floor": drawing.THUMB_TAP_PRECISION,
        }
    else:
        assert callout_positions["two cover clearance holes"] == drawing.CLEARANCE_CALLOUT_XY
        assert callout_positions["two cover clearance holes"][0] < front_map.apply(
            (spec.PLATE_HOLE_XS[1] / 1000.0, center[1], center[2])
        )[0]
        assert precisions == {"two cover clearance holes": drawing.CLEARANCE_PRECISION}
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
            hole = holes[1]
            mouth = (hole[0] + diameter / 2.0, hole[1], hole[2])
            if drawing is plate_drawing:
                # The clearance rim's lower outboard point, off the station witness.
                rim = diameter / 2.0 / math.sqrt(2.0)
                mouth = (hole[0] + rim, hole[1] - rim, hole[2])
        assert xyz == pytest.approx(tuple(value / 1000.0 for value in mouth))
        assert edge_xy == pytest.approx(expected_xy)
        assert abs(edge_xy[0] - view.Position[0]) < 0.043
        assert abs(edge_xy[1] - view.Position[1]) < 0.029
        assert 0.0 < edge_xy[0] < 0.4318
        assert 0.0 < edge_xy[1] < 0.2794
        if orientation == "*Back":
            # The real failure was millimetres fed to metre math: at 4:1
            # Back reverses X around the current finished-end origin. The
            # 20 mm block-column move keeps both real picks within the border.
            transform = view.ModelToViewTransform
            assert transform.apply((0.0, 0.0, 0.0))[0] == pytest.approx(
                0.217672 if drawing is plate_drawing else 0.197672
            )
            wrong_units_x = transform.apply(mouth)[0]
            assert wrong_units_x == pytest.approx(
                -73.262904 if drawing is plate_drawing else -73.614728
            )
            # Preserve the original failing other-rim negative-X signature.
            original = (holes[0][0] + diameter / 2.0, holes[0][1], holes[0][2])
            assert transform.apply(original)[0] == pytest.approx(
                -19.797528 if drawing is plate_drawing else -18.750728
            )


def test_match_drilling_does_not_eliminate_absolute_end_ligament_limits() -> None:
    """Matched pair error cancels, but the source axes still locate drilled stock."""
    length_band = printed_band_mm(spec.PLATE_DRAWING_PRECISION_BY_NAME["PlateLength"], unit="in")
    maximum_drill = spec.PLATE_CLEARANCE_DIA + spec.DRILL_OVERSIZE_MM
    minimum_end_web = spec.BLOCK_LENGTH - length_band - (
        spec.PLATE_HOLE_XS[1] + spec.PLATE_HOLE_POSITION_TOLERANCE_MM + maximum_drill / 2.0
    )
    assert minimum_end_web >= WALL_TARGET_MM
    # A .X length (+/-.1) would cut through that web: the .84 is .XX for it.
    assert spec.BLOCK_LENGTH - printed_band_mm(1, unit="in") - (
        spec.PLATE_HOLE_XS[1] + spec.PLATE_HOLE_POSITION_TOLERANCE_MM + maximum_drill / 2.0
    ) < WALL_FLOOR_MM
    assert spec.MATCH_DRILL_DATUM_ALIGNMENT == "LOCATING ENDS AND EDGES FLUSH"
    assert (spec.LOCATING_END_NOTE, spec.LOCATING_EDGE_NOTE) == ("LOCATING END", "LOCATING EDGE")


@pytest.mark.parametrize("master_band", [0.0, 0.1, 0.2, 0.51])
def test_reference_receiver_end_web_tracks_perturbed_plate_master_band(master_band) -> None:
    # These are absolute plate-master errors transferred from the same X=0
    # edge, not independent or floating block reference-dimension bands.
    expected = spec.BLOCK_LENGTH - spec.BLOCK_PRINTED_BANDS_MM["BlockLength"] - (
        spec.PLATE_HOLE_XS[1] + master_band + spec.PLATE_TAP_MAJOR_RADIUS_MAX
    )
    actual = spec.transferred_tap_end_web_min(master_band)
    assert actual == pytest.approx(expected)
    assert actual == pytest.approx(
        spec.PLATE_TAP_END_WEB_MIN + spec.PLATE_HOLE_POSITION_TOLERANCE_MM - master_band
    )
    if master_band <= spec.PLATE_HOLE_POSITION_TOLERANCE_MM:
        assert actual >= WALL_TARGET_MM


@pytest.mark.parametrize("refusal", [None, "prefix", "suffix", "tolerance", "value"])
def test_block_model_authors_native_reference_labels_without_independent_band(monkeypatch, refusal) -> None:
    class Tolerance:
        def __init__(self):
            self.value = 2

        @property
        def Type(self):  # noqa: N802 - native property
            return self.value

        @Type.setter
        def Type(self, value):
            if refusal != "tolerance":
                self.value = value

    class Display:
        def __init__(self):
            self.text = {1: "", 2: ""}
            self.ShowDimensionValue = refusal != "value"
            self.dimension = SimpleNamespace(Tolerance=Tolerance())

        def SetText(self, which, text):  # noqa: N802 - void native method
            if refusal != {1: "prefix", 2: "suffix"}[which]:
                self.text[which] = text

        def GetText(self, which):  # noqa: N802 - string native method
            return self.text[which]

        def GetDimension2(self, index):  # noqa: N802 - native dimension accessor
            assert index == 0
            return self.dimension

    owners = {name: "PlateLocationReference" for name in spec.PLATE_LOCATION_DIMENSIONS}
    owners.update({name: "Block" for name in spec.BLOCK_REFERENCE_DIMENSIONS})
    assert spec.BLOCK_REFERENCE_DIMENSIONS == {"BlockDepth"}
    displays = {name: Display() for name in owners}

    def named(_adapter, feature, name):
        assert feature == owners[name]
        return displays[name], displays[name].dimension

    monkeypatch.setattr(block, "_named_dimension", named)
    if refusal:
        with pytest.raises(RuntimeError, match="reference-only display did not persist"):
            block._author_reference_dimensions(object())
    else:
        block._author_reference_dimensions(object())
        for display in displays.values():
            assert display.text == {1: "(", 2: ")"}
            assert display.dimension.Tolerance.Type == 0
        monkeypatch.setattr(block_drawing, "dimension_name", lambda _adapter, item: item.name)
        annotations = [
            SimpleNamespace(name=name, GetSpecificAnnotation=lambda display=display: display)
            for name, display in displays.items()
        ]
        block_drawing._assert_reference_dimensions(object(), annotations)
        for display in displays.values():
            display.text[2] = ""
            with pytest.raises(RuntimeError, match="reference lost its source display"):
                block_drawing._assert_reference_dimensions(object(), annotations)
            display.text[2] = ")"


def test_match_drill_callouts_identify_the_current_mate_registry_rows() -> None:
    import _config

    plate, block = (_config.parts(stem)["number"] for stem in ("ms-stop-plate", "ms-stop-block"))
    # Rule 4: the matched pair names its mate by number and name.
    assert f"{plate} STOP PLATE" in block_drawing.COVER_HOLE_MATCH_DRILL
    assert "BOTTOMING TAP" not in block_drawing.COVER_HOLE_MATCH_DRILL
    assert f"{block} STOP BLOCK" in plate_drawing.MATCHED_PAIR_NOTE
    # The acceptance names the screws by drawing number.
    assert f"2X {_config.parts('ms-vn-stop-plate-screw')['number']} SCREWS" in plate_drawing.MATCHED_PAIR_NOTE
    # Rule 7: two lines of words under the block's native rows; the plate's
    # callout and thickness link the one note.
    assert len(block_drawing.COVER_HOLE_MATCH_DRILL.splitlines()) == 2
    assert plate_drawing.NOTE_LINK == f"SEE NOTE {plate_drawing.NOTE_NUMBER}"
    assert plate_drawing.MATCHED_PAIR_NOTE.startswith(f"{plate_drawing.NOTE_NUMBER}. ")
    # The thickness takes the title block and links no note.
    assert not hasattr(plate_drawing, "DIMENSION_CALLOUTS")


def test_stock_precision_and_worst_case_walls_use_each_printed_band() -> None:
    assert spec.BLOCK_PRINTED_BANDS_MM == {
        name: printed_band_mm(spec.BLOCK_DRAWING_PRECISION_BY_NAME[name], unit="in")
        for name in ("BlockLength", "BlockHeight", "RoofThickness", "BackWall", "ReliefDepth")
    }
    assert spec.PLATE_PRINTED_BANDS_MM == {
        name: printed_band_mm(spec.PLATE_DRAWING_PRECISION_BY_NAME[name], unit="in")
        for name in ("PlateLength", "PlateHeight")
    }
    assert spec.BLOCK_PRINTED_BANDS_MM == dict.fromkeys(
        ("BlockLength", "BlockHeight", "RoofThickness", "BackWall", "ReliefDepth"),
        pytest.approx(_inch(0.01)),
    )
    # The corner relief's .040 minimum depth clears the title block's R.040
    # MAX corner, and the back wall behind it keeps the .080 target.
    assert spec.RELIEF_DEPTH - spec.BLOCK_PRINTED_BANDS_MM["ReliefDepth"] == pytest.approx(
        inside_corner_radius_mm(unit="in"))
    assert spec.RELIEF_BACK_WALL_MIN == pytest.approx(WALL_TARGET_MM)
    assert spec.PLATE_PRINTED_BANDS_MM == dict.fromkeys(("PlateLength", "PlateHeight"), pytest.approx(_inch(0.01)))
    assert spec.WINDOW_FLOOR_MIN == pytest.approx(
        spec.BLOCK_HEIGHT - spec.BLOCK_PRINTED_BANDS_MM["BlockHeight"]
        - spec.ROOF_THICKNESS - spec.BLOCK_PRINTED_BANDS_MM["RoofThickness"]
        - spec.WINDOW_HEIGHT - spec.WINDOW_SIZE_TOLERANCE_MM[1]
    )
    # A .X band (+/-.1) on any of these would break its web.
    loosened = printed_band_mm(1, unit="in") - printed_band_mm(2, unit="in")
    assert spec.PLATE_TAP_BACK_WALL_MIN - loosened < WALL_FLOOR_MM
    assert spec.PLATE_CLEARANCE_END_WEB_MIN - loosened < WALL_FLOOR_MM
    assert spec.PLATE_TAP_WINDOW_WEB_MIN - (
        printed_band_mm(1, unit="in") - spec.PLATE_HOLE_POSITION_TOLERANCE_MM) < WALL_FLOOR_MM


def _window_reference_seat(monkeypatch, *, reject_construction=False):
    """Use the real location/anchor helpers over an offline sketch boundary."""
    features = {}

    def result(data=True):
        return SimpleNamespace(is_success=True, data=data)

    class Segment:
        def __init__(self):
            self.construction = False

        @property
        def ConstructionGeometry(self):  # noqa: N802 - COM property name
            return self.construction

        @ConstructionGeometry.setter
        def ConstructionGeometry(self, value):  # noqa: N802 - COM property name
            if not reject_construction:
                self.construction = value

    class Adapter:
        def __init__(self):
            self.currentSketchManager = SimpleNamespace(AddToDB=False)
            self._sketch_entities = {}
            self.dimensions = []
            self.lines = {}
            self.constraints = []
            self.planes = []

        def _attempt(self, fn, default=None):
            return fn()

        def create_sketch(self, plane):
            self.planes.append(plane)
            return result()

        def add_line(self, x1, y1, x2, y2):
            assert self.currentSketchManager.AddToDB
            name = "line" if not self.lines else f"line{len(self.lines) + 1}"
            self.lines[name] = ((x1, y1), (x2, y2))
            self._sketch_entities[name] = Segment()
            return result(name)

        def add_sketch_constraint(self, *args):
            self.constraints.append(args)
            return result()

        def add_sketch_dimension(self, first, second, kind, value):
            dimension = SimpleNamespace(first=first, second=second, kind=kind, value_mm=value)
            self.dimensions.append(dimension)
            return result(dimension)

        def exit_sketch(self):
            return result()

    def fully_defined(adapter, feature):
        adapter.defined = feature

    def name_feature(adapter, feature):
        features[feature] = adapter.dimensions

    def rename(dimensions, feature, names):
        for dimension, name in zip(dimensions, names, strict=True):
            dimension.Name = name
            dimension.FullName = f"{name}@{feature}"
        return [dimension.FullName for dimension in dimensions]

    monkeypatch.setattr(stop_geom, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(stop_geom, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(stop_geom, "name_last_feature", name_feature)
    monkeypatch.setattr(dimensions, "_feature_by_name", lambda adapter, name: features[name])
    monkeypatch.setattr(dimensions, "_display_dimensions", lambda feature, name: feature)
    monkeypatch.setattr(dimensions, "_rename_dimensions", rename)
    return Adapter()


def test_rebate_profile_owns_width_height_and_back_wall_on_its_consumed_sketch(monkeypatch) -> None:
    # Run 20261024T043544205Z-432c211c gated shown reference chords ghosting
    # over the rebate ceiling and the back wall. The consumed cut profile now
    # owns all three, so its dimensions import without any drawn sketch line.
    adapter = _window_reference_seat(monkeypatch)
    dims = sketch.SketchDims()
    stop_geom.rebate_profile(adapter, dims)
    assert adapter.planes == ["Right"]
    assert adapter.defined == "rebate profile"
    ceiling, back, floor, cover, wall = (adapter.lines[name] for name in (
        "line", "line2", "line3", "line4", "line5"))
    assert ceiling == ((0.0, spec.WINDOW_Y_MAX), (-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX))
    assert back == ((-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX), (-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MIN))
    assert floor[1] == cover[0] == (0.0, spec.WINDOW_Y_MIN)
    assert wall == ((-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX), (-spec.BLOCK_DEPTH, spec.WINDOW_Y_MAX))
    assert adapter._sketch_entities["line5"].ConstructionGeometry
    assert not any(adapter._sketch_entities[name].ConstructionGeometry
                   for name in ("line", "line2", "line3", "line4"))
    assert ("line5", None, "horizontal") in adapter.constraints
    assert ("line5.start", "line.end", "coincident") in adapter.constraints
    assert [(d.first, d.second, d.kind) for d in adapter.dimensions] == [
        ("line.start", "line.end", "horizontal_distance"),
        ("line2.start", "line2.end", "vertical_distance"),
        ("line.start", "origin", "vertical_distance"),
        ("line5.start", "line5.end", "horizontal_distance"),
    ]
    assert [d.value_mm for d in adapter.dimensions] == pytest.approx([
        spec.WINDOW_WIDTH, spec.WINDOW_HEIGHT, spec.WINDOW_Y_MAX, spec.BACK_WALL_THICKNESS,
    ])
    assert dims._rows == [
        ("WindowWidth", '"WindowWidth"'), ("WindowHeight", '"WindowHeight"'),
        ("WindowRoofStation", '"BlockHeight" - "RoofThickness"'),
        ("BackWall", '"BlockDepth" - "WindowWidth"'),
    ]
    assert spec.BLOCK_DRAWING_DIMENSIONS["WindowProfile"] == {"WindowWidth", "WindowHeight", "BackWall"}
    assert not {"ReferenceWindowWidth", "BackWallReference", "Window"} & set(spec.BLOCK_DRAWING_DIMENSIONS)


def test_rebate_profile_refuses_unapplied_back_wall_construction_flag(monkeypatch) -> None:
    adapter = _window_reference_seat(monkeypatch, reject_construction=True)
    with pytest.raises(RuntimeError, match="back wall construction flag rejected"):
        stop_geom.rebate_profile(adapter, sketch.SketchDims())
    assert all(d.kind != "horizontal_distance" or d.first != "line5.start" for d in adapter.dimensions)


def test_relief_profile_notches_the_back_wall_under_the_roof(monkeypatch) -> None:
    adapter = _window_reference_seat(monkeypatch)
    dims = sketch.SketchDims()
    stop_geom.relief_profile(adapter, dims)
    back = spec.WINDOW_Z_MAX + spec.RELIEF_DEPTH
    low = spec.WINDOW_Y_MAX - spec.RELIEF_HEIGHT
    assert adapter.planes == ["Right"]
    assert list(adapter.lines.values()) == [
        ((-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX), (-back, spec.WINDOW_Y_MAX)),
        ((-back, spec.WINDOW_Y_MAX), (-back, low)),
        ((-back, low), (-spec.WINDOW_Z_MAX, low)),
        ((-spec.WINDOW_Z_MAX, low), (-spec.WINDOW_Z_MAX, spec.WINDOW_Y_MAX)),
    ]
    assert [name for name, _ in dims._rows] == [
        "ReliefDepth", "ReliefHeight", "ReliefWindowStation", "ReliefRoofStation",
    ]
    assert spec.BLOCK_DRAWING_DIMENSIONS["ReliefProfile"] == {"ReliefDepth", "ReliefHeight"}


def test_roof_reference_lies_on_the_lip_face_not_through_the_lip(monkeypatch) -> None:
    adapter = _window_reference_seat(monkeypatch)
    monkeypatch.setattr(stop_geom, "ensure_fully_defined", lambda *a: None)
    equations = dict(stop_geom.roof_reference(adapter))
    assert adapter.lines == {"line": ((0.0, spec.WINDOW_Y_MAX), (0.0, spec.BLOCK_HEIGHT))}
    assert adapter._sketch_entities["line"].ConstructionGeometry
    thickness, station = adapter.dimensions
    assert (thickness.Name, thickness.value_mm) == ("RoofThickness", spec.ROOF_THICKNESS)
    assert (station.Name, station.kind, station.value_mm) == (
        "RoofWindowStation", "vertical_distance", spec.WINDOW_Y_MAX,
    )
    assert equations == {
        "RoofThickness@RoofThicknessReference": '"RoofThickness"',
        "RoofWindowStation@RoofThicknessReference": '"BlockHeight" - "RoofThickness"',
    }


def test_block_chamfer_keeps_its_routine_band_inside_the_roof() -> None:
    """The largest printed .XX chamfer stays inside the thinnest roof."""
    assert spec.BLOCK_DRAWING_PRECISION_BY_NAME["RoofChamferSize"] == 2
    chamfer_max = spec.ROOF_END_CHAMFER + printed_band_mm(2, unit="in")
    assert chamfer_max < spec.ROOF_THICKNESS_MIN


def test_tight_bands_name_their_mates_and_no_wall_states_a_shortfall() -> None:
    stick_number = _config.parts("ms-stick")["number"]
    callouts = block_drawing.DIMENSION_CALLOUTS
    # Rule 4: the rebate's two tight bands link one numbered note naming the stick.
    for name in ("WindowWidth", "WindowHeight"):
        assert callouts[name] == block_drawing.REBATE_NOTE_LINK
    assert block_drawing.REBATE_NOTE.startswith(f"{block_drawing.REBATE_NOTE_NUMBER}. ")
    assert block_drawing.REBATE_NOTE.endswith(f"{stick_number} MEASURING STICK")
    # Every wall meets the .080 target, so no callout states a MIN.
    assert not any("MIN" in text for text in callouts.values())
    assert "THICKNESS" not in plate_drawing.MATCHED_PAIR_NOTE
    assert spec.MATCH_DRILL_DATUM_ALIGNMENT in block_drawing.COVER_HOLE_MATCH_DRILL.replace("\n", " ")

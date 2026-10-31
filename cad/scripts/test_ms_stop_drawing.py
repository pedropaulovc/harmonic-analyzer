"""Offline observable contracts for the separate brass stop block and cover."""

from __future__ import annotations

import asyncio
import ast
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_projection as drawing_projection
import _dimensions as dimensions
import _ms_drawing_guards as guards
import _sketch as sketch
import ms_stop_geom as stop_geom
import build_ms_stop_block as block
import build_ms_stop_plate as plate
import draw_ms_stop_block as block_drawing
import draw_ms_stop_plate as plate_drawing
import ms_stick_spec as stick
import ms_stop_callouts as callouts
import ms_stop_spec as spec
import _mcmaster_90114a124 as screw
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import DRILL_POINT_H
from _inch_wall_limits import WALL_FLOOR_MM
from _printed_tolerance import printed_band_mm


def _inch(value_in: float) -> float:
    return value_in * 25.4


def test_shared_frame_and_open_rebate_closure() -> None:
    # Issue #290: both parts print decimal inch; every printed nominal is the
    # exact millimetre decimal of its inch value.
    assert spec.UNIT == spec.BLOCK_UNIT == spec.PLATE_UNIT == "in"
    for got, inch in (
        (spec.BLOCK_LENGTH, 0.84), (spec.BLOCK_HEIGHT, 0.56), (spec.BLOCK_DEPTH, 0.44),
        (spec.PLATE_THICKNESS, 0.040), (spec.WINDOW_WIDTH, 0.330), (spec.WINDOW_HEIGHT, 0.134),
        (spec.ROOF_THICKNESS, 0.09), (spec.ROOF_END_CHAMFER, 0.04), (spec.BACK_WALL_THICKNESS, 0.11),
    ):
        assert got == pytest.approx(_inch(inch), rel=0.0, abs=1e-9)
    assert (spec.PLATE_Z_MIN, spec.PLATE_Z_MAX) == (-spec.PLATE_THICKNESS, 0.0)
    assert spec.TOTAL_DEPTH == pytest.approx(spec.BLOCK_DEPTH + spec.PLATE_THICKNESS)
    assert (spec.WINDOW_Z_MIN, spec.WINDOW_Z_MAX) == (0.0, spec.WINDOW_WIDTH)
    assert (spec.WINDOW_Y_MIN, spec.WINDOW_Y_MAX) == pytest.approx((8.5344, 11.938))
    assert spec.WINDOW_Y_MAX + spec.ROOF_THICKNESS == pytest.approx(spec.BLOCK_HEIGHT)
    # Rule 17 on the inch sheet: .080 target at the roof's .XX low limit.
    assert spec.ROOF_THICKNESS - printed_band_mm(2, unit="in") >= spec.WALL_TARGET_MM - 1e-9
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
    assert spec.PLATE_TAP_SPEC.depth_mm == spec.PLATE_TAP_DRILL_DEPTH
    assert spec.PLATE_TAP_DRILL_DEPTH == pytest.approx(_inch(0.300), rel=0.0, abs=1e-9)
    assert spec.PLATE_TAP_SPEC.overrides_mm["ThreadDepth"] == spec.PLATE_TAP_THREAD_DEPTH
    assert spec.PLATE_TAP_THREAD_DEPTH == pytest.approx(_inch(0.250), rel=0.0, abs=1e-9)
    # #49 drill, .073: three places, the shop's drill.
    assert spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"] == spec.PLATE_TAP_DRILL_DIA == 1.8542
    # The cover clearance is the wizard's own #2 close size, .094, unedited.
    assert spec.PLATE_CLEARANCE_SPEC.kind == "clearance" and spec.PLATE_CLEARANCE_SPEC.fit == "close"
    assert not spec.PLATE_CLEARANCE_SPEC.overrides_mm
    assert spec.PLATE_CLEARANCE_DIA == 2.3876
    assert spec.THUMB_TAP_SPEC.kind == "tapped" and spec.THUMB_TAP_SPEC.size == "#4-40"
    # Through-all would drill the opposite roof as well as the thick floor.
    assert spec.THUMB_TAP_SPEC.end == "through_next"
    assert (spec.THUMB_AXIS_X, spec.THUMB_AXIS_Z) == pytest.approx((10.668, 4.191))
    assert spec.THUMB_HOLE_POINTS == ((spec.THUMB_AXIS_X, 0.0, spec.THUMB_AXIS_Z),)
    assert spec.THUMB_HOLE_NORMAL == (0.0, -1.0, 0.0)
    assert spec.PLATE_HOLE_XS == pytest.approx((_inch(0.150), _inch(0.690)))
    assert spec.PLATE_HOLE_Y == pytest.approx(_inch(0.160))
    assert spec.PLATE_HOLE_PITCH == pytest.approx(_inch(0.540))
    assert spec.PLATE_HOLE_NORMAL == (0.0, 0.0, -1.0)
    assert spec.BLOCK_PLATE_HOLE_POINTS == tuple((x, spec.PLATE_HOLE_Y, 0.0) for x in spec.PLATE_HOLE_XS)
    assert spec.PLATE_HOLE_POINTS == tuple(
        (x, spec.PLATE_HOLE_Y, -spec.PLATE_THICKNESS) for x in spec.PLATE_HOLE_XS)


def test_receiver_engagement_and_separation_are_real_geometry() -> None:
    assert spec.PLATE_SCREW_PENETRATION == pytest.approx(5.334)
    assert 1.5 * screw.MAJOR_DIA < spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_THREAD_DEPTH
    assert spec.PLATE_SCREW_PENETRATION < spec.PLATE_TAP_DRILL_DEPTH
    tip = spec.PLATE_TAP_DRILL_DEPTH + spec.PLATE_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
    assert spec.PLATE_TAP_TIP_Z == pytest.approx(tip)
    assert spec.BLOCK_DEPTH - tip > spec.WALL_TARGET_MM
    assert spec.PLATE_HOLE_Y + screw.MAJOR_DIA / 2.0 < spec.WINDOW_Y_MIN - spec.WALL_TARGET_MM
    for x in spec.PLATE_HOLE_XS:
        assert abs(x - spec.THUMB_AXIS_X) - (screw.MAJOR_DIA + spec.THUMB_MAJOR_DIA) / 2.0 > spec.WALL_TARGET_MM


def test_print_worst_joint_stack_preserves_bottoming_tap_and_ligaments() -> None:
    # Cover thickness at the title block's .XXX (+/-.005).
    assert spec.PLATE_THICKNESS_MIN == pytest.approx(0.889)
    assert spec.PLATE_THICKNESS_MAX == pytest.approx(1.143)
    assert spec.PLATE_FULL_THREAD_MIN == pytest.approx(6.223)
    assert spec.PLATE_SCREW_PENETRATION_MAX == pytest.approx(5.715)
    assert spec.PLATE_SCREW_PENETRATION_MIN == pytest.approx(4.953)
    assert spec.PLATE_SCREW_PENETRATION_MIN >= 1.5 * screw.MAJOR_DIA
    assert spec.PLATE_SCREW_PENETRATION_MAX < spec.PLATE_FULL_THREAD_MIN
    assert spec.PLATE_TAP_LEAD_MIN == pytest.approx(1.016)
    assert spec.PLATE_TAP_LEAD_MIN >= screw.PITCH
    assert spec.PLATE_TAP_BACK_WALL_MIN == pytest.approx(2.58742, abs=1e-5)
    assert spec.ROOF_THICKNESS_MIN == pytest.approx(2.032)
    assert spec.PLATE_TAP_WINDOW_WEB_MIN == pytest.approx(2.60731)
    assert spec.PLATE_TAP_END_WEB_MIN == pytest.approx(2.30251)
    assert spec.PLATE_TAP_MAJOR_DIA_MAX == pytest.approx(0.0887 * 25.4)
    assert spec.PLATE_TAP_MAJOR_DIA_MAX > screw.MAJOR_DIA
    assert spec.WINDOW_BACK_WALL_MIN == pytest.approx(2.54)
    assert spec.BLOCK_DEPTH_MIN == pytest.approx(10.922)
    assert spec.PLATE_CLEARANCE_END_WEB_MIN == pytest.approx(2.1844)
    assert spec.PLATE_CLEARANCE_HEAD_WEB_MIN == pytest.approx(8.5344)
    assert spec.PLATE_RADIAL_CLEARANCE_MIN == pytest.approx(0.1016)
    assert spec.ROOF_OPEN_END_EDGE == pytest.approx(1.27)


def test_every_worst_case_wall_meets_the_inch_rule_17_target() -> None:
    """Rule 17 on the inch sheet: .080 target, .060 floor; each wall and web
    is taken at its printed bands, so no sheet states a shortfall."""
    assert (spec.WALL_TARGET_MM, WALL_FLOOR_MM) == (2.032, 1.524)
    walls = spec.WORST_CASE_WALLS_MM
    assert walls == {
        "roof": spec.ROOF_THICKNESS_MIN,
        "rebate back wall": spec.WINDOW_BACK_WALL_MIN,
        "tap drill point to opposite face": spec.PLATE_TAP_BACK_WALL_MIN,
        "tap thread to end face": spec.PLATE_TAP_END_WEB_MIN,
        "tap thread to rebate floor": spec.PLATE_TAP_WINDOW_WEB_MIN,
        "clearance hole to end face": spec.PLATE_CLEARANCE_END_WEB_MIN,
        "clearance hole to head edge": spec.PLATE_CLEARANCE_HEAD_WEB_MIN,
    }
    assert min(walls.values()) >= spec.WALL_TARGET_MM - 1e-9
    assert not spec._SHORT


def test_matched_pair_uses_functional_positions_and_a_real_shop_sequence() -> None:
    # The master stations ride the title block's .XXX; no own band.
    assert spec.PLATE_HOLE_POSITION_TOLERANCE_MM == pytest.approx(printed_band_mm(3, unit="in"))
    assert all(block_point[:2] == plate_point[:2] for block_point, plate_point
               in zip(spec.BLOCK_PLATE_HOLE_POINTS, spec.PLATE_HOLE_POINTS, strict=True))
    # Rule 7: the pair is flagged at both match-drill callouts, not in a loose note.
    assert not hasattr(spec, "BLOCK_DRAWING_NOTES") and not hasattr(spec, "PLATE_DRAWING_NOTES")
    # Both match-drill callouts (feature-local) flag the pair as matched.
    # The block's blind depths are measured from its own mating face, not from
    # the clamped plate's exposed face.
    assert f"DEPTHS FROM {spec.BLOCK_MATING_FACE_NOTE}" in block_drawing.COVER_HOLE_PROCESS
    for callout in (block_drawing.COVER_HOLE_PROCESS,
                    callouts.PLATE_CALLOUTS["PilotDrillDiameter"]):
        assert spec.MATCHED_PAIR_NOTE in callout
    assert "NOT INTERCHANGEABLE" in spec.MATCHED_PAIR_NOTE
    assert "PilotDrillDiameter" in spec.PLATE_DRAWING_DIMENSIONS["PilotDrillReference"]
    assert spec.PLATE_DRAWING_VALUES_BY_NAME["PilotDrillDiameter"] == (
        spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"]
    )

def test_window_keeps_functional_clearance_at_printed_size_limits() -> None:
    # The window's own +.004/-0 band and the stick's title-block .XXX leave
    # .010 of side and .011 of face clearance at the tightest limits.
    window_lower, _window_upper = spec.WINDOW_SIZE_TOLERANCE_MM
    assert spec.WINDOW_SIZE_TOLERANCE_MM == pytest.approx((0.0, 0.1016))
    assert spec.WINDOW_WIDTH + window_lower - (stick.BODY_WIDTH + stick.BODY_FIT_TOLERANCE_MM) == pytest.approx(0.254)
    assert spec.WINDOW_HEIGHT + window_lower - (stick.BODY_THICKNESS + stick.BODY_FIT_TOLERANCE_MM) == pytest.approx(0.2794)
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
    # Decimal inch: no .X on either part (nothing here is nonfunctional);
    # .XXX for the rebate the stick slides in, the thumbscrew's station from
    # the cover, the matched-pair stations, cover thickness and pilot drill.
    three = ({"WindowWidth", "WindowHeight", "ThumbFromPlate", *spec.PLATE_LOCATION_DIMENSIONS}
             if builder is block
             else {"PlateThickness", "PilotDrillDiameter", *spec.PLATE_LOCATION_DIMENSIONS})
    assert {name: places for name, places in precision.items() if places != 2} == {
        "RoofChamferAngle": 0, **dict.fromkeys(three, 3),
    }
    assert drawing.FRONT_CENTER[1] == drawing.RIGHT_CENTER[1]


@pytest.mark.parametrize("module", [spec, block_drawing, plate_drawing])
def test_no_com_in_spec_or_render_time_size_overrides(module) -> None:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    if module is spec:
        imports = [
            name
            for node in ast.walk(tree)
            for name in (
                [node.module or ""] if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names] if isinstance(node, ast.Import)
                else []
            )
        ]
        # The one documented exception: _drawing_units is pure data (its own
        # docstring), read only to resolve the sheet unit from the literal
        # registry rows. Prove it stays pure: standard library only, no COM.
        pure_data = "_drawing_units"
        assert pure_data in imports
        assert not any(name.startswith((
            "build_", "solidworks", "_appearance", "_assembly", "_check", "_com",
            "_custom_properties", "_dimensions", "_drawing", "_feature_tree",
            "_holes", "_part_", "_rebuild", "_session", "_sketch", "_visibility",
        )) for name in imports if name != pure_data)
        helper = ast.parse((Path(module.__file__).parent / f"{pure_data}.py").read_text(encoding="utf-8"))
        helper_imports = {
            name
            for node in ast.walk(helper)
            for name in (
                [node.module or ""] if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names] if isinstance(node, ast.Import)
                else []
            )
        }
        assert helper_imports <= {"__future__", "collections.abc", "typing"}, helper_imports
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
        ("two cover blind taps", "*Back", (0.0184531, 0.004064, 0.0), (0.1238596, 0.172808)),
        ("thumbscrew tap through floor", "*Bottom",
         (0.0117985, 0.0, 0.004191), (0.150478, 0.078588)),
        ("cover mating face", "*Left", (0.010668, 0.012573, 0.0), (0.292648, 0.206844)),
    ]),
    (plate_drawing, [
        ("two cover clearance holes", "*Back", (0.0026162, 0.004064, -0.001016), (0.2072072, 0.157808)),
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
    fonts = []
    monkeypatch.setattr(drawing, "_construction_curve_font", fonts.append, raising=False)
    monkeypatch.setattr(drawing, "_add_rebate_slide_finish", lambda adapter, view: None, raising=False)
    utility = _StopMathUtility()

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=None)

    source_flags = {"dirty": False}
    adapter = SimpleNamespace(
        currentModel=SimpleNamespace(EditRebuild3=lambda: True,
                                     GetPathName=lambda: str(source),
                                     GetSaveFlag=lambda: source_flags["dirty"]),
        open_model=open_model,
        swApp=SimpleNamespace(GetMathUtility=lambda: utility),
    )
    # The real clean-source guard runs on the fake document's path and save
    # flag and the sentinel file's bytes.
    checkpoint_stages = []
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
    new_kwargs = {}

    def new_drawing(*args, **kwargs):
        new_kwargs.update(kwargs)
        kwargs["checkpoint"]("after_new_document")
        checkpoint_stages.append("after_new_document")
        return object(), object()

    monkeypatch.setattr(drawing, "new_project_drawing", new_drawing)
    for name in (
        "read_required_properties", "stamp_drawing_summary",
        "set_hidden_lines_removed", "assert_imported_text",
        "add_property_linked_note",
    ):
        monkeypatch.setattr(drawing, name, lambda *a, **kw: None)
    native_contracts = []
    monkeypatch.setattr(
        drawing, "assert_manufacturing_dimensions",
        lambda *args, **kwargs: native_contracts.append(kwargs),
    )
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *a, **kw: [])
    if drawing is block_drawing:
        monkeypatch.setattr(drawing, "_remove_general_thread_class", lambda *a, **kw: None)
        monkeypatch.setattr(drawing, "_assert_reference_dimensions", lambda *a: None)
    else:
        monkeypatch.setattr(drawing, "_assert_pilot_diameter", lambda *a: None)
    labelled = []
    monkeypatch.setattr(drawing, "_label_locating_edges", lambda adapter, view: labelled.append(view))
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *a, **kw: True)
    callouts = []

    callout_positions = {}

    def add_callout(adapter, view, *, edge_xy, callout_xy, label, process=None):
        callouts.append((view, edge_xy, label))
        callout_positions[label] = callout_xy

    async def finalize(adapter, outputs, **kwargs):
        assert kwargs["package_name"] == drawing.PACKAGE
        for stage in ("before_drawing_save", "after_drawing_save", "after_drawing_close"):
            kwargs["checkpoint"](stage)
            checkpoint_stages.append(stage)
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
    assert new_kwargs["package_name"] == drawing.PACKAGE == drawing.PART_STEM
    assert checkpoint_stages == [
        "after_new_document", "before_drawing_save", "after_drawing_save", "after_drawing_close",
    ]
    assert source.read_bytes() == b"offline source sentinel"
    assert len(native_contracts) == 1
    bands = native_contracts[0].get("bands", {})
    if drawing is block_drawing:
        assert not set(bands) & (spec.PLATE_LOCATION_DIMENSIONS | spec.BLOCK_REFERENCE_DIMENSIONS)
        assert bands == {name: spec.WINDOW_SIZE_TOLERANCE_MM for name in ("WindowWidth", "WindowHeight")}
    else:
        # Cover thickness and master stations ride the title block's .XXX.
        assert not bands
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
        assert callout_positions["two cover blind taps"] == (0.065, 0.127)
    else:
        # The native pilot's construction circle is at X=.150, the same
        # right-sheet hole selected for the opened clearance callout.
        assert callout_positions["two cover clearance holes"] == drawing.CLEARANCE_CALLOUT_XY
        assert drawing.FRONT_KEEP["PilotDrillDiameter"] == (0.285, 0.178)
        assert callout_positions["two cover clearance holes"][0] > front_map.apply(
            (0.0, center[1], center[2])
        )[0]
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
            hole = holes[0] if drawing is plate_drawing else holes[1]
            mouth = (hole[0] + (-diameter if drawing is plate_drawing else diameter) / 2.0,
                     hole[1], hole[2])
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
                -10.247128 if drawing is plate_drawing else -73.614728
            )
            # Preserve the original failing other-rim negative-X signature
            # as well as the plate's new concentric right-sheet pick.
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
    assert minimum_end_web == pytest.approx(spec.PLATE_CLEARANCE_END_WEB_MIN)
    assert minimum_end_web >= spec.WALL_TARGET_MM
    # A .X length (+/-.1) would break that web: the .84 is .XX for it.
    assert spec.BLOCK_LENGTH - printed_band_mm(1, unit="in") - (
        spec.PLATE_HOLE_XS[1] + spec.PLATE_HOLE_POSITION_TOLERANCE_MM + maximum_drill / 2.0
    ) < WALL_FLOOR_MM
    assert spec.MATCH_DRILL_MASTER == "MS-STOP-PLATE"
    assert spec.MATCH_DRILL_DATUM_ALIGNMENT == "LOCATING ENDS AND EDGES FLUSH"
    assert (spec.LOCATING_END_NOTE, spec.LOCATING_EDGE_NOTE) == ("LOCATING END", "LOCATING EDGE")


@pytest.mark.parametrize("master_band", [0.0, 0.0508, 0.127, 0.254])
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
        assert actual >= spec.WALL_TARGET_MM


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


def test_receiver_model_has_no_independent_location_tolerance_authoring() -> None:
    tree = ast.parse(Path(block.__file__).read_text(encoding="utf-8"))
    calls = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "set_dimension_symmetric_tolerance" not in calls
    assert "_author_reference_dimensions" in calls


class _StopDisplay:
    def __init__(self, prefix, *, hole=True, kind=6, refusal=None):
        self.prefix = prefix
        self.hole = hole
        self.Type2 = kind
        self.refusal = refusal

    def IsHoleCallout(self):  # noqa: N802 - COM method name
        return self.hole

    def GetText(self, which):  # noqa: N802 - COM method name
        assert which == 5, "resolved prefix text would sever native variables"
        return self.prefix

    def SetText(self, which, text):  # noqa: N802 - COM method name
        assert which == 1
        if self.refusal != "prefix":
            self.prefix = text


def test_rebate_ceiling_is_the_graded_sliding_face(monkeypatch) -> None:
    # Rule 6: the stick's graduated face slides on the roof underside.
    (control,) = spec.BLOCK_SURFACE_FINISHES
    assert (control.key, control.roughness_um) == ("rebate_slide", 1.6)
    # The inch sheet grades it in microinches, the physical value unchanged.
    assert control.display_unit == "in" and control.roughness_ra == "63"
    assert control.face.normal == (0, -1, 0)
    assert control.face.offset_mm == pytest.approx(-spec.WINDOW_Y_MAX)
    calls = []
    monkeypatch.setattr(block_drawing, "model_point_in_view", lambda adapter, view, xyz, label: (0.30, 0.19))
    monkeypatch.setattr(block_drawing, "add_surface_finish", lambda adapter, view, **kw: calls.append(kw))
    block_drawing._add_rebate_slide_finish(object(), object())
    (call,) = calls
    assert call["control"] is control
    assert call["leader_attach_xy"] == call["edge_xy"] == (0.30, 0.19)
    assert call["symbol_xy"] == pytest.approx((0.27, 0.178))


@pytest.mark.parametrize("refusal", [None, "set", "readback"])
def test_construction_curve_font_is_set_and_read_back(monkeypatch, refusal) -> None:
    # Only the plate restyles construction curves (a phantom pilot). The
    # block keeps the default: its location chords cross the views' interiors.
    drawing = plate_drawing
    assert not hasattr(block_drawing, "CONSTRUCTION_CURVE_FONT")
    assert drawing.CONSTRUCTION_CURVE_FONT == {
        "swLineFontConstructionCurvesStyle": 2,
        "swLineFontConstructionCurvesThickness": 0,
    }
    stored = {}

    def set_pref(pref, option, value):
        if refusal != "set":
            stored[pref] = value + (1 if refusal == "readback" else 0)
        return refusal != "set"

    extension = SimpleNamespace(
        SetUserPreferenceInteger=set_pref,
        GetUserPreferenceInteger=lambda pref, option: stored[pref],
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(drawing, "constant", lambda name: name)
    if refusal:
        with pytest.raises(RuntimeError, match="line font"):
            drawing._construction_curve_font(SimpleNamespace(Extension=extension))
    else:
        drawing._construction_curve_font(SimpleNamespace(Extension=extension))
        assert stored == drawing.CONSTRUCTION_CURVE_FONT


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


def test_thumb_tap_callout_states_where_its_thru_ends() -> None:
    definition = "<MOD-DIAM><hw-tapdrldia> THRU\n<hw-threaddesc>-<hw-threadclass> THRU"
    native = _StopDisplay(definition)
    block_drawing._remove_general_thread_class(native, last_line=block_drawing.THUMB_HOLE_END)
    rows = native.prefix.splitlines()
    assert rows[:2] == ["<MOD-DIAM><hw-tapdrldia> THRU", "<hw-threaddesc> THRU"]
    assert "REBATE" in rows[-1] and "ROOF" in rows[-1]


def test_no_stop_web_needs_a_stated_shortfall() -> None:
    # Issue #290: on the inch grid every web meets the .080 target at its
    # printed bands, so neither sheet states a web line and neither package
    # declares an owner exception any more.
    import _config
    from machinist_exceptions import load_exceptions

    for name in ("PLATE_TAP_WEB_LINES", "PLATE_CLEARANCE_WEB_LINE", "ROOF_WALL_CALLOUT"):
        assert not hasattr(spec, name)
    assert not hasattr(plate_drawing, "_append_callout_line")
    for stem in ("ms_stop_block", "ms_stop_plate"):
        assert load_exceptions(_config.CONFIG_DIR, stem, "part") == ()
    for package in ("ms-stop-block", "ms-stop-plate"):
        assert "machinist_exceptions" not in _config.parts(package)
    native = _StopDisplay("<hw-threaddesc>-<hw-threadclass> <HOLE-DEPTH><hw-threaddepth>")
    block_drawing._remove_general_thread_class(native)
    assert native.prefix == "<hw-threaddesc> <HOLE-DEPTH><hw-threaddepth>"


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
def test_pilot_callout_requires_model_diameter_and_writes_nothing(monkeypatch, kind) -> None:
    native = _StopDisplay("2X <MOD-DIAM>", hole=False, kind=kind)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: native)
    monkeypatch.setattr(plate_drawing, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(plate_drawing, "dimension_name", lambda *a: "PilotDrillDiameter")
    native.SetText = lambda *a: pytest.fail("the sheet must not write imported text")
    if kind != 6:
        with pytest.raises(RuntimeError, match="native model diameter"):
            plate_drawing._assert_pilot_diameter(object(), [annotation])
    else:
        plate_drawing._assert_pilot_diameter(object(), [annotation])
    assert native.prefix == "2X <MOD-DIAM>"


class _PartDisplay:
    """A model display dimension: prefix (1), callout below (4), prefix
    definition (5) -- the text parts the part build authors."""

    def __init__(self, definition="", *, refuse=None):
        self.text = {1: "", 4: "", 5: definition}
        self.refuse = refuse

    def SetText(self, which, text):  # noqa: N802 - void native method
        if which == self.refuse:
            return
        if which == 1:
            self.text[5] = text
        self.text[which] = text

    def GetText(self, which):  # noqa: N802 - string native method
        return self.text[which]


@pytest.mark.parametrize("refuse", [None, 1, 4])
def test_part_build_authors_dimension_text_and_reads_it_back(monkeypatch, refuse) -> None:
    displays = {name: _PartDisplay("<MOD-DIAM>" if name == "PilotDrillDiameter" else "",
                                   refuse=refuse)
                for name in callouts.PLATE_FEATURE_OF}

    def named(_adapter, feature, names):
        assert all(callouts.PLATE_FEATURE_OF[name] == feature for name in names)
        return {name: (displays[name], object()) for name in names}

    monkeypatch.setattr(stop_geom, "_named_dimensions", named)
    write = lambda: stop_geom.author_dimension_text(  # noqa: E731
        object(), callouts.PLATE_FEATURE_OF, callouts.PLATE_CALLOUTS, callouts.PLATE_PREFIXES)
    if refuse:
        with pytest.raises(RuntimeError, match="did not persist"):
            write()
        return
    write()
    for name, text in callouts.PLATE_CALLOUTS.items():
        assert callouts.callout_rows(displays[name].text[4]) == callouts.callout_rows(text)
    assert displays["PilotDrillDiameter"].text[5] == "2X <MOD-DIAM>"
    assert displays["RoofChamferSize"].text[5] == "2X "
    # The part, not the sheet, owns every text row the plate drawing reads.
    assert set(callouts.PLATE_FEATURE_OF) == {*callouts.PLATE_CALLOUTS, *callouts.PLATE_PREFIXES}
    assert callouts.BLOCK_FEATURE_OF == {
        "RoofChamferSize": "RoofChamfers", "WindowWidth": "WindowProfile",
        "WindowHeight": "WindowProfile",
    }


@pytest.mark.parametrize("fault", [None, "crlf", "missing", "text", "prefix"])
def test_sheet_reads_back_the_parts_imported_text_without_writing(monkeypatch, fault) -> None:
    names = {*callouts.PLATE_CALLOUTS, *callouts.PLATE_PREFIXES}
    displays = {}
    for name in names:
        display = _PartDisplay()
        display.text[4] = callouts.PLATE_CALLOUTS.get(name, "")
        display.text[5] = callouts.PLATE_PREFIXES.get(name, "") + "<MOD-DIAM>"
        display.SetText = lambda *a: pytest.fail("the sheet must not write imported text")
        displays[name] = display
    if fault == "crlf":
        # The sheet compares rows with the part's own normalizer: a native
        # CRLF readback of the authored text is the same text.
        displays["PlateThickness"].text[4] = callouts.PLATE_CALLOUTS["PlateThickness"].replace(
            "\n", "\r\n")
    elif fault == "text":
        displays["PlateThickness"].text[4] = "SETS SCREW REACH"
    elif fault == "prefix":
        displays["RoofChamferSize"].text[5] = ""
    annotations = [
        SimpleNamespace(name=name, GetSpecificAnnotation=lambda display=display: display)
        for name, display in displays.items()
        if not (fault == "missing" and name == "PilotDrillDiameter")
    ]
    monkeypatch.setattr(guards, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(guards, "dimension_name", lambda _adapter, item: item.name)
    check = lambda: guards.assert_imported_text(  # noqa: E731
        object(), annotations, callouts.PLATE_CALLOUTS, callouts.PLATE_PREFIXES)
    if fault in (None, "crlf"):
        check()
    else:
        with pytest.raises(RuntimeError, match="missing from the sheet" if fault == "missing"
                           else "differs from the part"):
            check()


def test_match_drill_callouts_identify_the_current_mate_registry_rows() -> None:
    import _config

    assert "MS-STOP-PLATE" in block_drawing.COVER_HOLE_PROCESS
    assert _config.parts("ms-stop-plate")["number"] in block_drawing.COVER_HOLE_PROCESS
    assert "BOTTOMING TAP" not in block_drawing.COVER_HOLE_PROCESS
    assert f"MATCH-DRILL FROM {spec.MATCH_DRILL_MASTER}" in block_drawing.COVER_HOLE_PROCESS
    assert spec.MATCH_DRILL_DATUM_ALIGNMENT in block_drawing.COVER_HOLE_PROCESS.replace("\n", " ")
    pilot = callouts.PLATE_CALLOUTS["PilotDrillDiameter"]
    assert "MS-STOP-BLOCK" in pilot
    assert _config.parts("ms-stop-block")["number"] in pilot
    # Fit-up requirements, not wording: the plate is the master, the pair is
    # clamped on its locating faces, and it is flagged as a matched pair.
    flat = " ".join(pilot.split())
    assert "PILOT" in flat and "LOCATING ENDS AND EDGES FLUSH" in flat
    assert spec.MATCHED_PAIR_NOTE in pilot
    for name in spec.PLATE_LOCATION_DIMENSIONS:
        station = callouts.PLATE_CALLOUTS[name]
        assert "MS-STOP-BLOCK" in station
        assert _config.parts("ms-stop-block")["number"] in station
    assert spec.PLATE_DRAWING_VALUES_BY_NAME["PilotDrillDiameter"] == (
        spec.PLATE_TAP_SPEC.overrides_mm["TapDrillDiameter"]
    )


@pytest.mark.parametrize("on_axis", [False, True])
def test_pilot_reference_emits_concentric_native_diameter_and_live_equation(monkeypatch, on_axis) -> None:
    """Exercise real define_circle/SketchDims over captured adapter geometry."""
    if on_axis:
        monkeypatch.setattr(spec, "PLATE_HOLE_XS", (0.0, spec.PLATE_HOLE_XS[1]))
    features = {}

    def result(data=True):
        return SimpleNamespace(is_success=True, data=data)

    class Adapter:
        def __init__(self):
            self.currentSketchManager = SimpleNamespace(AddToDB=False)
            self._sketch_entities = {}
            self.dimensions = []
            self.circles = {}

        async def create_sketch(self, plane):
            assert plane == "Front"
            return result()

        async def add_circle(self, x, y, radius):
            self.circles["circle"] = (x, y, radius)
            self._sketch_entities["circle"] = SimpleNamespace(ConstructionGeometry=False)
            return result("circle")

        async def add_sketch_constraint(self, *args):
            return result()

        async def add_sketch_dimension(self, first, second, kind, value):
            dimension = SimpleNamespace(
                first=first, second=second, kind=kind, value_mm=value,
                name=None,
            )
            self.dimensions.append(dimension)
            return result(dimension)

        async def exit_sketch(self):
            return result()

    async def fully_defined(adapter, feature):
        return None

    def name_feature(adapter, feature):
        features[feature] = adapter.dimensions

    def rename(dimensions, feature, names):
        for dimension, name in zip(dimensions, names, strict=True):
            dimension.name = name

    monkeypatch.setattr(stop_geom, "_early_bound", lambda value, interface: value)
    monkeypatch.setattr(stop_geom, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(stop_geom, "name_last_feature", name_feature)
    monkeypatch.setattr(sketch, "_feature_by_name", lambda adapter, name: features[name])
    monkeypatch.setattr(sketch, "_display_dimensions", lambda feature, name: feature)
    monkeypatch.setattr(sketch, "_rename_dimensions", rename)
    adapter = Adapter()
    equations = dict(asyncio.run(stop_geom.pilot_drill_reference(adapter)))
    x, y, radius = adapter.circles["circle"]
    assert (x, y) == (spec.PLATE_HOLE_XS[0], spec.PLATE_HOLE_Y)
    assert radius == pytest.approx(spec.PLATE_TAP_DRILL_DIA / 2.0)
    assert radius < spec.PLATE_CLEARANCE_DIA / 2.0
    assert adapter._sketch_entities["circle"].ConstructionGeometry
    diameter, = (dim for dim in adapter.dimensions if dim.name == "PilotDrillDiameter")
    assert diameter.first == "circle" and diameter.second is None
    assert diameter.kind == "diameter"
    assert diameter.value_mm == pytest.approx(2.0 * radius)
    assert equations == {"PilotDrillDiameter@PilotDrillReference": '"PilotDrillDiameter"'}
    anchors = [dim for dim in adapter.dimensions if dim is not diameter]
    assert {dim.kind: dim.value_mm for dim in anchors} == {
        kind: abs(coordinate) for kind, coordinate in (
            ("horizontal_distance", x), ("vertical_distance", y),
        ) if coordinate != 0.0
    }
    assert all(dim.first == "circle.center" and dim.second == "origin" for dim in anchors)
    assert all(dim.name is None for dim in anchors)
    assert set(spec.PLATE_DRAWING_DIMENSIONS["PilotDrillReference"]) == {"PilotDrillDiameter"}


def test_stock_precision_and_worst_case_walls_use_each_printed_band() -> None:
    assert spec.BLOCK_PRINTED_BANDS_MM == {
        name: printed_band_mm(spec.BLOCK_DRAWING_PRECISION_BY_NAME[name], unit="in")
        for name in ("BlockLength", "BlockHeight", "RoofThickness", "BackWall")
    }
    assert spec.PLATE_PRINTED_BANDS_MM == {
        name: printed_band_mm(spec.PLATE_DRAWING_PRECISION_BY_NAME[name], unit="in")
        for name in ("PlateLength", "PlateHeight")
    }
    # Every stack size is .XX (+/-.01); none is the nonfunctional .X.
    assert spec.BLOCK_PRINTED_BANDS_MM == pytest.approx({
        "BlockLength": 0.254, "BlockHeight": 0.254, "RoofThickness": 0.254, "BackWall": 0.254,
    })
    assert spec.PLATE_PRINTED_BANDS_MM == pytest.approx({"PlateLength": 0.254, "PlateHeight": 0.254})
    assert spec.WINDOW_FLOOR_MIN == pytest.approx(
        spec.BLOCK_HEIGHT - spec.BLOCK_PRINTED_BANDS_MM["BlockHeight"]
        - spec.ROOF_THICKNESS - spec.BLOCK_PRINTED_BANDS_MM["RoofThickness"]
        - spec.WINDOW_HEIGHT - spec.WINDOW_SIZE_TOLERANCE_MM[1]
    )
    loose, routine = printed_band_mm(1, unit="in"), printed_band_mm(2, unit="in")
    # Each web would break at a .X band where its sizes now hold .XX.
    assert spec.PLATE_TAP_BACK_WALL_MIN - (loose - routine) < WALL_FLOOR_MM
    assert spec.PLATE_CLEARANCE_END_WEB_MIN - (loose - routine) < WALL_FLOOR_MM
    # Absolute edge error remains after the matched pair's relative error
    # cancels: a .X master station would break both tapped-hole webs.
    assert spec.PLATE_TAP_END_WEB_MIN - (loose - spec.PLATE_HOLE_POSITION_TOLERANCE_MM) < WALL_FLOOR_MM
    assert spec.PLATE_TAP_WINDOW_WEB_MIN - (loose - spec.PLATE_HOLE_POSITION_TOLERANCE_MM) < WALL_FLOOR_MM


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

        async def create_sketch(self, plane):
            self.planes.append(plane)
            return result()

        async def add_line(self, x1, y1, x2, y2):
            assert self.currentSketchManager.AddToDB
            name = "line" if not self.lines else f"line{len(self.lines) + 1}"
            self.lines[name] = ((x1, y1), (x2, y2))
            self._sketch_entities[name] = Segment()
            return result(name)

        async def add_sketch_constraint(self, *args):
            self.constraints.append(args)
            return result()

        async def add_sketch_dimension(self, first, second, kind, value):
            dimension = SimpleNamespace(first=first, second=second, kind=kind, value_mm=value)
            self.dimensions.append(dimension)
            return result(dimension)

        async def exit_sketch(self):
            return result()

    async def fully_defined(adapter, feature):
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
    asyncio.run(stop_geom.rebate_profile(adapter, dims))
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
        asyncio.run(stop_geom.rebate_profile(adapter, sketch.SketchDims()))
    assert all(d.kind != "horizontal_distance" or d.first != "line5.start" for d in adapter.dimensions)


def test_block_build_cuts_rebate_from_its_profile_driven_marked_and_toleranced(monkeypatch) -> None:
    equations, globals_authored, bands, marks, hidden = {}, {}, [], [], []
    cuts, precisions, properties = [], [], []

    def result(data=True):
        return SimpleNamespace(is_success=True, data=data)

    async def no_op(*args, **kwargs):
        return None

    class Adapter:
        async def create_part(self):
            order.append("create_part")
            return result()

        async def create_sketch(self, plane):
            return result()

        async def exit_sketch(self):
            return result()

        async def create_extrusion(self, params):
            return result()

        async def create_cut_extrude(self, params):
            cuts.append((params.depth, params.both_directions))
            return result()

        async def add_chamfer(self, *args, **kwargs):
            return result()

    async def set_global(adapter, name, expression):
        order.append(name)
        globals_authored[name] = expression

    async def drive(adapter, name, expression):
        equations[name] = expression

    async def rebate(adapter, dims):
        assert "WindowWidth" in globals_authored
        assert cuts == []
        profiles.append(dims)

    async def roof_reference(adapter):
        return []

    async def save(adapter, part_name):
        return {"part": part_name}

    profiles = []
    # #290: the model's calculation units follow create_part, before any global.
    order = []
    units = []
    monkeypatch.setattr(
        block, "apply_package_model_units",
        lambda adapter, unit, *, label: (order.append("units"), units.append((unit, label))),
    )
    monkeypatch.setattr(block, "set_global", set_global)
    monkeypatch.setattr(block, "drive_dimension", drive)
    monkeypatch.setattr(block, "rebate_profile", rebate)
    monkeypatch.setattr(block, "roof_reference", roof_reference)
    monkeypatch.setattr(block, "save_part_and_images", save)
    monkeypatch.setattr(block, "SketchDims", lambda: SimpleNamespace(apply=lambda *a: []))
    for name in (
        "add_line_chain", "define_rectilinear_chain", "ensure_fully_defined",
        "volume_check", "location_reference", "force_rebuild", "apply_material",
        "apply_color", "report_mass_properties",
    ):
        monkeypatch.setattr(block, name, no_op)
    for name in (
        "name_last_feature", "name_dimensions", "wizard_holes", "author_hole_precision",
        "_author_reference_dimensions", "clear_dimensions_for_drawing",
    ):
        monkeypatch.setattr(block, name, lambda *a, **kw: None)
    monkeypatch.setattr(
        block, "set_dimension_bilateral_tolerance",
        lambda adapter, feature, name, low, high, **kw: bands.append((feature, name, low, high, kw)))
    texts = []
    monkeypatch.setattr(block, "author_dimension_text",
                        lambda adapter, feature_of, below, prefixes=None: texts.append(
                            (feature_of, below, prefixes)))
    monkeypatch.setattr(block, "mark_dimensions_for_drawing",
                        lambda adapter, feature, names: marks.append((feature, names)))
    monkeypatch.setattr(block, "hide_location_references", lambda adapter, names: hidden.extend(names))
    pmi = []
    monkeypatch.setattr(block, "author_part_pmi", lambda adapter, **kw: pmi.append(kw))
    monkeypatch.setattr(block, "apply_drawing_precision", lambda adapter, precision: precisions.append(precision))
    monkeypatch.setattr(block, "apply_drawing_properties",
                        lambda adapter, part_name, values: properties.append(values))
    assert asyncio.run(block.build(Adapter())) == {"part": "ms-stop-block"}
    assert order[:3] == ["create_part", "units", "BlockLength"]
    assert units == [("in", "ms-stop-block")]
    assert globals_authored["WindowWidth"] == f"{spec.WINDOW_WIDTH}mm"
    assert len(profiles) == 1
    assert cuts == [(2.0 * (spec.BLOCK_LENGTH + spec.CUT_OVERHANG), True)]
    assert equations["WindowCutDepth@Window"] == f'2 * ("BlockLength" + {spec.CUT_OVERHANG})'
    for name in ("WindowWidth", "WindowHeight"):
        assert ("WindowProfile", name, *spec.WINDOW_SIZE_TOLERANCE_MM, {"display_unit": "in"}) in bands
    # The part, not the sheet, writes the block's dimension text.
    assert texts == [(callouts.BLOCK_FEATURE_OF, callouts.BLOCK_CALLOUTS, None)]
    assert ("WindowProfile", {"WindowHeight", "WindowWidth", "BackWall"}) in marks
    assert all(feature != "Window" for feature, names in marks)
    assert hidden == ["ThumbLocationReference", "PlateLocationReference", "RoofThicknessReference"]
    assert precisions == [spec.BLOCK_DRAWING_PRECISION]
    assert properties[0]["Mating Face Note"] == "STOP-PLATE MATING FACE"
    assert "Manufacturing Notes" not in properties[0]
    assert pmi == [{"surface_finishes": spec.BLOCK_SURFACE_FINISHES}]


def test_roof_reference_lies_on_the_lip_face_not_through_the_lip(monkeypatch) -> None:
    adapter = _window_reference_seat(monkeypatch)
    monkeypatch.setattr(stop_geom, "ensure_fully_defined", lambda *a: asyncio.sleep(0))
    equations = dict(asyncio.run(stop_geom.roof_reference(adapter)))
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


def test_block_chamfer_keeps_the_routine_band_inside_the_roof() -> None:
    """The largest printed .04 chamfer stays inside the thinnest .09 roof."""
    assert spec.BLOCK_DRAWING_PRECISION_BY_NAME["RoofChamferSize"] == 2
    assert spec.PLATE_DRAWING_PRECISION_BY_NAME["RoofChamferSize"] == 2
    chamfer_max = spec.ROOF_END_CHAMFER + printed_band_mm(2, unit="in")
    assert chamfer_max < spec.ROOF_THICKNESS_MIN
    assert spec.ROOF_THICKNESS_MIN - chamfer_max == pytest.approx(0.762)


def test_tight_bands_name_their_mates_and_no_wall_states_a_shortfall() -> None:
    import _config

    stick_number = _config.parts("ms-stick")["number"]
    block_text = callouts.BLOCK_CALLOUTS
    for name in ("WindowWidth", "WindowHeight"):
        assert f"MS-STICK {stick_number}" in block_text[name]
    # The back wall and roof meet the .080 target at their .XX bands.
    assert "BackWall" not in block_text and "RoofThickness" not in block_text
    assert spec.WINDOW_BACK_WALL_MIN >= spec.WALL_TARGET_MM
    assert spec.ROOF_THICKNESS_MIN >= spec.WALL_TARGET_MM - 1e-9
    assert not any("MIN" in text for text in (*block_text.values(), *callouts.PLATE_CALLOUTS.values()))
    thickness = callouts.PLATE_CALLOUTS["PlateThickness"]
    assert "SCREW REACH" in thickness
    assert _config.parts("ms-stop-block")["number"] in thickness
    assert spec.MATCH_DRILL_DATUM_ALIGNMENT in block_drawing.COVER_HOLE_PROCESS
    # Neither sheet keeps its own copy of the parts' text.
    assert not hasattr(block_drawing, "DIMENSION_CALLOUTS")
    assert not hasattr(plate_drawing, "DIMENSION_CALLOUTS")

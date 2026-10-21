"""Offline definition/native-recipe contracts for MHA-CH-06-TL-30.

No SolidWorks connection or recipe execution. Native readback and sheet review
remain the integration owner's separate acceptance gates.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import math
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_pivot_cap as part
import ch_rocker_arm_tl_oblique_pivot_cap_spec as spec
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import draw_ch_rocker_arm_tl_oblique_pivot_cap as drawing
import export_features
from _machinist_review_mode import MachinistReviewMode
from _printed_tolerance import printed_band_mm
from test_pd_transgear_adapter_contract import _adapter_calls, _adapter_methods, _missing, _signature

STEM = "ch_rocker_arm_tl_oblique_pivot_cap"
DASHED = STEM.replace("_", "-")
RECIPE = Path(__file__).with_name(f"build_{STEM}.py")


def test_dimensions_and_assembly_references_have_one_shared_owner() -> None:
    assert (spec.WIDTH, spec.LENGTH, spec.HEIGHT) == (retention.CAP_WIDTH, retention.CAP_LENGTH, retention.CAP_HEIGHT)
    assert (spec.POCKET_DIA, spec.POCKET_DEPTH, spec.APERTURE_DIA) == (
        retention.CAP_POCKET_DIAMETER, retention.CAP_POCKET_DEPTH, retention.CAP_APERTURE_DIAMETER,
    )
    assert spec.BOLT_POINTS == retention.CAP_BOLT_CENTERS
    assert set(spec.BOLT_POINTS) == set(product(retention.CAP_BOLT_X_OFFSETS, retention.CAP_BOLT_Y_OFFSETS))
    assert spec.BOTTOM_PLANE == "Front Plane"
    assert spec.AXIS_NAME == "CaptureAxis"
    assert spec.BOLT_AXES == tuple(f"CapBoltAxis{i}" for i in range(1, 5))
    assert spec.HEIGHT_PLACES == retention.CAP_HEIGHT_PLACES
    assert spec.CENTER_LOCATION_PLACES == retention.CAP_CENTER_LOCATION_PLACES == 2
    assert spec.POSITION_PLACES == spec.COUNTERBORE_DEPTH_PLACES == 3
    assert spec.CHANNEL_PLACES == 2
    assert spec.COUNTERBORE_DIA == retention.CAP_COUNTERBORE_DIAMETER
    assert spec.COUNTERBORE_DIAMETER_PLACES == retention.CAP_COUNTERBORE_DIAMETER_PLACES == 2
    assert spec.DRAWING_PRECISION_BY_NAME["CounterboreDia"] == 2
    assert spec.CHANNEL_DEPTH == retention.CAP_WIRE_CHANNEL_DEPTH
    assert spec.TOTAL_HEIGHT == spec.HEIGHT + spec.REGISTER_PROJECTION
    assert spec.TOTAL_HEIGHT + spec.HEIGHT_TOLERANCE + printed_band_mm(spec.REGISTER_PROJECTION_PLACES) < spec.STOCK_THICKNESS
    assert spec.STOCK_WIDTH > spec.WIDTH + 2.0 * printed_band_mm(spec.OUTLINE_PLACES)
    assert spec.STOCK_LENGTH_MIN > spec.LENGTH + 2.0 * printed_band_mm(spec.OUTLINE_PLACES)


def test_integral_register_geometry_has_one_shared_owner() -> None:
    assert spec.REGISTER_POINTS == retention.CAP_REGISTER_CENTERS
    assert spec.REGISTER_DIA == retention.CAP_REGISTER_DIAMETER == 6.0
    assert spec.REGISTER_BAND == retention.CAP_REGISTER_DIAMETER_BAND == (0.10, -0.10)
    assert spec.REGISTER_PROJECTION == retention.CAP_REGISTER_PROJECTION == 1.0
    assert spec.REGISTER_LOCATION_PLACES == retention.CAP_REGISTER_LOCATION_PLACES == 3
    assert spec.REGISTER_PROJECTION_PLACES == retention.CAP_REGISTER_PROJECTION_PLACES == 3
    assert spec.REGISTER_END_CHAMFER_MAX == retention.CAP_REGISTER_END_CHAMFER_MAX == 0.20


@pytest.mark.parametrize("missing_chamfer", (False, True))
def test_native_chamfer_stays_on_its_visible_profile_through_finalization(monkeypatch, tmp_path, missing_chamfer) -> None:
    source = tmp_path / "cap.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    views, imports, precision_checks, callouts, finalized = [], [], [], [], []
    native = SimpleNamespace(
        FullName="RegisterEndChamfer@RegisterEndChamfers@cap",
        SystemValue=spec.REGISTER_END_CHAMFER_MAX / 1000.0,
        Tolerance=SimpleNamespace(Type=6, lower=-spec.REGISTER_END_CHAMFER_MAX / 1000.0, upper=0.0),
    )
    chamfer = SimpleNamespace(name="RegisterEndChamfer", dimension=native)

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=None, error=None)

    adapter = SimpleNamespace(currentModel=object(), open_model=open_model)

    def place(current, path, orientation, x, y, *, scale):
        assert current is adapter and path == str(source)
        view = SimpleNamespace(orientation=orientation, center=(x, y), scale=scale, annotations=[])
        views.append(view)
        return view

    def section(_adapter, _parent, **kwargs):
        view = SimpleNamespace(orientation=kwargs["section_label"], annotations=[])
        views.append(view)
        return view

    def curate(current, view, *, keep, view_label, dimensions_by_feature):
        assert current is adapter and dimensions_by_feature is spec.DRAWING_DIMENSIONS
        imports.append((view, keep))
        if "RegisterEndChamfer" in keep:
            assert view.orientation == "*Top"
            assert view.center == drawing.REGISTER_END_CENTER
            assert keep == drawing.REGISTER_END_KEEP
            if missing_chamfer:
                raise RuntimeError("missing model dimensions: ['RegisterEndChamfer']")
            view.annotations[:] = [chamfer]
        else:
            view.annotations[:] = [SimpleNamespace(name=name) for name in keep]
        return list(view.annotations)

    def precision(_adapter, annotations, expected):
        assert expected is spec.DRAWING_PRECISION_BY_NAME
        precision_checks.extend(annotations)

    def set_callouts(_adapter, annotations, expected, *, location):
        assert expected is spec.DIMENSION_CALLOUTS and location == "below"
        callouts.extend(annotations)

    async def finalize(_adapter, outputs, **_kwargs):
        finalized.append(outputs)
        return {"slddrw": "cap.SLDDRW"}

    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kwargs: (adapter.currentModel, object()))
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "create_section_view", section)
    monkeypatch.setattr(drawing, "_project", lambda *_args: (0.0, 0.0))
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda _adapter, view: setattr(view, "hidden_removed", True))
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "assert_imported_precision", precision)
    monkeypatch.setattr(drawing, "set_dimension_callouts", set_callouts)
    monkeypatch.setattr(drawing, "_assert_pocket_corner_callout", lambda *_args: None)
    monkeypatch.setattr(drawing, "auto_center_marks", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(drawing, "add_surface_finish", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "add_property_linked_note", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)

    if missing_chamfer:
        with pytest.raises(RuntimeError, match="RegisterEndChamfer"):
            asyncio.run(drawing.build(adapter))
        assert not finalized and not precision_checks and not callouts
    else:
        assert asyncio.run(drawing.build(adapter)) == {"slddrw": "cap.SLDDRW"}
        profile, = [view for view in views if view.orientation == "*Top"]
        assert profile.annotations == [chamfer] and profile.hidden_removed
        assert profile.scale == drawing.VIEW_SCALE
        assert sum(item is chamfer for item in precision_checks) == 1
        assert sum(item is chamfer for item in callouts) == 1
        assert {annotation.name for annotation in precision_checks} == set(spec.DRAWING_PRECISION_BY_NAME)
        assert len(precision_checks) == len(spec.DRAWING_PRECISION_BY_NAME)
        assert finalized == [drawing.OUTPUTS]
        assert len(views) == 7
    side, = [view for view in views if view.orientation == "*Right"]
    assert next(keep for view, keep in imports if view is side) == drawing.RIGHT_KEEP
    assert "RegisterEndChamfer" not in drawing.RIGHT_KEEP
    assert chamfer.dimension is native
    assert native.SystemValue == spec.REGISTER_END_CHAMFER_MAX / 1000.0
    assert (native.Tolerance.Type, native.Tolerance.lower, native.Tolerance.upper) == (
        6, -spec.REGISTER_END_CHAMFER_MAX / 1000.0, 0.0,
    )


@pytest.mark.parametrize("persisted", (True, False))
def test_local_corner_limit_is_read_back_on_the_native_chamber_size(
    monkeypatch: pytest.MonkeyPatch, persisted: bool,
) -> None:
    expected = spec.DIMENSION_CALLOUTS["PocketDia"]
    read_parts = []

    def get_text(part):
        read_parts.append(part)
        return expected.replace("\n", "\r\n") if persisted else "GENERAL CORNER LIMIT ONLY"

    display = SimpleNamespace(GetText=get_text)
    pocket = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    unrelated = object()
    adapter = SimpleNamespace(_attempt=lambda call: call())
    monkeypatch.setattr(drawing, "dimension_name",
                        lambda _adapter, annotation: "PocketDia" if annotation is pocket else "ApertureDia")
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    if persisted:
        drawing._assert_pocket_corner_callout(adapter, [unrelated, pocket])
    else:
        with pytest.raises(RuntimeError):
            drawing._assert_pocket_corner_callout(adapter, [unrelated, pocket])
    assert read_parts == [4]  # swDimensionTextCalloutBelow, not a free note or primary value


def test_local_corner_readback_requires_a_chamber_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, _annotation: "ApertureDia")
    with pytest.raises(RuntimeError):
        drawing._assert_pocket_corner_callout(object(), [object()])


def test_all_real_material_margins_survive_the_printed_limits() -> None:
    margins = spec.require_clearance_geometry()
    assert margins == spec.GEOMETRY_MARGINS
    assert set(margins) == {"counterbore_floor", "channel_floor", "chamber_roof", "counterbore_to_chamber", "hole_to_chamber", "mouth_to_chamber", "channel_to_chamber", "counterbore_to_y_edge", "pocket_to_x_edge"}
    assert min(margins.values()) >= 2.0
    assert margins["counterbore_floor"] == pytest.approx(
        spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.COUNTERBORE_DEPTH - spec.COUNTERBORE_DEPTH_TOLERANCE
    )
    assert margins["chamber_roof"] == pytest.approx(spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.FITTED_POCKET_DEPTH_MAX)
    assert margins["channel_floor"] == pytest.approx(spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.CHANNEL_DEPTH - printed_band_mm(spec.CHANNEL_PLACES))
    # Deliberate mouths are not counted as nonexistent outside-X material.
    assert not any("mouth_to_x_edge" in key for key in margins)


@pytest.mark.parametrize("change", [
    {"counterbore_depth": 9.0}, {"channel_depth": 9.0},
    {"pocket_dia": 49.0}, {"counterbore_dia": 23.0},
    {"fitted_pocket_depth_max": 9.0},
    {"points": tuple((x / 2.0, y / 2.0) for x, y in spec.BOLT_POINTS)},
])
def test_material_checks_reject_breakthrough_and_thin_wall_mutants(change) -> None:
    with pytest.raises(ValueError, match="material target"):
        spec.require_clearance_geometry(**change)


@pytest.mark.parametrize("change,margin", [
    ({"channel_depth": 9.0}, "channel_floor"),
    ({"counterbore_dia": spec.COUNTERBORE_DIA + 1.0}, "counterbore_to_y_edge"),
])
def test_void_enlargement_rejects_thin_land_floor_and_outer_wall(change, margin) -> None:
    assert spec.clearance_geometry(**change)[margin] < 2.0
    with pytest.raises(ValueError):
        spec.require_clearance_geometry(**change)


@pytest.mark.parametrize("width_delta", (-0.01, 0.01))
def test_channel_land_uses_actual_two_mm_boundary(width_delta: float) -> None:
    target = 2.0
    pocket_radius = (spec.POCKET_DIA + spec.POCKET_BAND[0]) / 2.0
    nearest_row = min(abs(y) for _x, y in spec.BOLT_POINTS) - spec.POSITION_TOLERANCE
    boundary_width = (
        2.0 * (nearest_row - pocket_radius - target)
        - printed_band_mm(spec.CHANNEL_PLACES)
    )
    width = boundary_width + width_delta
    margin = spec.clearance_geometry(channel_width=width)["channel_to_chamber"]
    assert margin == pytest.approx(target - width_delta / 2.0)
    if width_delta < 0.0:
        assert spec.require_clearance_geometry(channel_width=width)["channel_to_chamber"] > target
    else:
        with pytest.raises(ValueError, match="channel_to_chamber"):
            spec.require_clearance_geometry(channel_width=width)


@pytest.mark.parametrize("width,length", [(spec.WIDTH, spec.LENGTH), (62.0, 86.0)])
def test_outer_walls_use_the_common_edge_and_full_opposite_outline_error(width, length) -> None:
    outline_band = printed_band_mm(spec.OUTLINE_PLACES)
    center_band = printed_band_mm(spec.CENTER_LOCATION_PLACES)
    cb_radius = (spec.COUNTERBORE_DIA + printed_band_mm(spec.COUNTERBORE_DIAMETER_PLACES)) / 2.0
    pocket_radius = (spec.POCKET_DIA + spec.POCKET_BAND[0]) / 2.0
    y_walls, x_walls = [], []
    # Set the two actual common stock edges to zero. The opposite edge
    # varies by the FULL outline band, not half of a centred-stock band.
    for outline_error, center_error, bolt_error in product(
        (-outline_band, outline_band), (-center_band, center_band),
        (-spec.POSITION_TOLERANCE, spec.POSITION_TOLERANCE),
    ):
        pocket_x = width / 2.0 + center_error
        pocket_y = length / 2.0 + center_error
        x_walls.extend((pocket_x - pocket_radius, width + outline_error - pocket_x - pocket_radius))
        for _x, bolt_y in spec.BOLT_POINTS:
            head_y = pocket_y + bolt_y + bolt_error
            y_walls.extend((head_y - cb_radius, length + outline_error - head_y - cb_radius))
    margins = spec.clearance_geometry(width=width, length=length)
    assert margins["counterbore_to_y_edge"] == pytest.approx(min(y_walls))
    assert margins["pocket_to_x_edge"] == pytest.approx(min(x_walls))
    unchanged = set(margins) - {"counterbore_to_y_edge", "pocket_to_x_edge"}
    assert {name: margins[name] for name in unchanged} == {
        name: spec.GEOMETRY_MARGINS[name] for name in unchanged
    }


@pytest.mark.parametrize("axis,margin", [
    ("length", "counterbore_to_y_edge"), ("width", "pocket_to_x_edge"),
])
def test_common_edge_material_wall_boundary_is_not_masked(axis, margin) -> None:
    edge_errors = printed_band_mm(spec.OUTLINE_PLACES) + printed_band_mm(spec.CENTER_LOCATION_PLACES)
    if axis == "length":
        radius = (spec.COUNTERBORE_DIA + printed_band_mm(spec.COUNTERBORE_DIAMETER_PLACES)) / 2.0
        reach = max(abs(y) for _, y in spec.BOLT_POINTS) + spec.POSITION_TOLERANCE + radius
    else:
        reach = (spec.POCKET_DIA + spec.POCKET_BAND[0]) / 2.0
    boundary = 2.0 * (2.0 + edge_errors + reach)
    assert spec.require_clearance_geometry(**{axis: boundary + 1e-5})[margin] > 2.0
    assert spec.clearance_geometry(**{axis: boundary - 1e-5})[margin] < 2.0
    with pytest.raises(ValueError, match=margin):
        spec.require_clearance_geometry(**{axis: boundary - 1e-5})



def test_register_roots_keep_real_material_clear_of_all_void_families() -> None:
    margins = spec.require_register_geometry()
    assert margins == spec.REGISTER_GEOMETRY_MARGINS
    assert min(margins.values()) >= 2.0
    assert {
        "register_to_through_hole", "register_to_pocket", "register_to_aperture",
        "register_to_x_edge", "register_to_y_edge", "register_to_head_void_floor",
        "register_to_wire_void_floor",
    } == margins.keys()
    # A head recess and a boss may overlap in XY because a real floor
    # separates them in Z. Do not invent a planar no-overlap requirement.
    assert min(math.dist(register, bolt) for register in spec.REGISTER_POINTS for bolt in spec.BOLT_POINTS) < (
        spec.REGISTER_DIA + spec.COUNTERBORE_DIA
    ) / 2.0
    assert margins["register_to_head_void_floor"] == spec.GEOMETRY_MARGINS["counterbore_floor"]
    assert margins["register_to_wire_void_floor"] == spec.GEOMETRY_MARGINS["channel_floor"]


@pytest.mark.parametrize("change,margin", [
    ({"register_points": (spec.BOLT_POINTS[0], spec.REGISTER_POINTS[1])}, "register_to_through_hole"),
    ({"register_points": ((0.0, 0.0), spec.REGISTER_POINTS[1])}, "register_to_pocket"),
    ({"aperture_dia": 48.0}, "register_to_aperture"),
    ({"width": 15.0}, "register_to_x_edge"),
    ({"length": 54.0}, "register_to_y_edge"),
    ({"counterbore_depth": 9.0}, "register_to_head_void_floor"),
    ({"channel_depth": 9.0}, "register_to_wire_void_floor"),
])
def test_register_material_guards_reject_intersection_and_thin_wall_mutants(change, margin) -> None:
    assert spec.register_clearance_geometry(**change)[margin] < 2.0
    with pytest.raises(ValueError, match="material target"):
        spec.require_register_geometry(**change)


def test_register_to_hole_margin_spends_independent_xy_errors_but_not_shared_pocket_error() -> None:
    register_error = printed_band_mm(spec.REGISTER_LOCATION_PLACES)
    hole_error = printed_band_mm(spec.POSITION_PLACES)
    separations = []
    for (x, y), (bx, by) in product(spec.REGISTER_POINTS, spec.BOLT_POINTS):
        for ex, ey, hx, hy in product((-register_error, register_error), (-register_error, register_error), (-hole_error, hole_error), (-hole_error, hole_error)):
            separations.append(math.hypot(x + ex - bx - hx, y + ey - by - hy))
    radius_sum = (spec.REGISTER_DIA + spec.REGISTER_BAND[0] + spec.HOLE_DIA + spec.DRILLED_BAND[0]) / 2.0
    assert spec.register_clearance_geometry()["register_to_through_hole"] == pytest.approx(min(separations) - radius_sum)
    grown = spec.register_clearance_geometry(width=spec.WIDTH + 8.0, length=spec.LENGTH + 6.0)
    assert grown["register_to_through_hole"] == spec.REGISTER_GEOMETRY_MARGINS["register_to_through_hole"]
    assert grown["register_to_x_edge"] - spec.REGISTER_GEOMETRY_MARGINS["register_to_x_edge"] == pytest.approx(4.0)
    assert grown["register_to_y_edge"] - spec.REGISTER_GEOMETRY_MARGINS["register_to_y_edge"] == pytest.approx(3.0)


def test_register_volume_uses_the_real_free_end_frustum_and_preserves_body_height(monkeypatch) -> None:
    radius, chamfer = spec.REGISTER_DIA / 2.0, spec.REGISTER_END_CHAMFER_MAX
    frustum = math.pi * chamfer / 3.0 * (radius**2 + radius * (radius - chamfer) + (radius - chamfer)**2)
    one_boss = math.pi * radius**2 * (spec.REGISTER_PROJECTION - chamfer) + frustum
    assert spec.nominal_register_volume_mm3() == pytest.approx(len(spec.REGISTER_POINTS) * one_boss)
    original = spec.nominal_volume_mm3()
    with monkeypatch.context() as changed:
        changed.setattr(spec, "REGISTER_PROJECTION", spec.REGISTER_PROJECTION + 0.25)
        assert spec.nominal_volume_mm3() - original == pytest.approx(len(spec.REGISTER_POINTS) * math.pi * radius**2 * 0.25)
    with monkeypatch.context() as changed:
        changed.setattr(spec, "REGISTER_END_CHAMFER_MAX", 0.0)
        assert spec.nominal_volume_mm3() - original == pytest.approx(
            len(spec.REGISTER_POINTS) * (math.pi * radius**2 * chamfer - frustum)
        )
    assert spec.HEIGHT == retention.CAP_HEIGHT


def test_nominal_volume_accounts_for_stock_and_real_aperture_and_wire_voids(monkeypatch) -> None:
    original = spec.nominal_volume_mm3()
    assert original == spec.VOLUME_MM3
    assert 0.0 < original < spec.WIDTH * spec.LENGTH * spec.HEIGHT
    radius, half_channel = spec.COUNTERBORE_DIA / 2.0, spec.CHANNEL_WIDTH / 2.0
    circular_overlap = (
        half_channel * math.sqrt(radius**2 - half_channel**2)
        + radius**2 * math.asin(half_channel / radius)
    )
    channel_area = len({y for _, y in spec.BOLT_POINTS}) * (
        (max(x for x, _ in spec.BOLT_POINTS) - min(x for x, _ in spec.BOLT_POINTS)) * spec.CHANNEL_WIDTH
        - 2.0 * circular_overlap
    )
    changes = (
        ("LENGTH", spec.LENGTH + 2.0, 2.0 * spec.WIDTH * spec.HEIGHT),
        ("WIDTH", spec.WIDTH + 2.0, 2.0 * spec.LENGTH * spec.HEIGHT - len(spec.BOLT_POINTS) * spec.COUNTERBORE_DIA * spec.COUNTERBORE_DEPTH),
        ("APERTURE_DIA", spec.APERTURE_DIA + 1.0, -math.pi * ((spec.APERTURE_DIA + 1.0)**2 - spec.APERTURE_DIA**2) / 4.0 * (spec.HEIGHT - spec.POCKET_DEPTH)),
        ("CHANNEL_DEPTH", spec.CHANNEL_DEPTH + 1.0, -channel_area),
    )
    for name, value, volume_change in changes:
        with monkeypatch.context() as changed:
            changed.setattr(spec, name, value)
            assert spec.nominal_volume_mm3() - original == pytest.approx(volume_change)


def test_entry_relief_aliases_and_local_neck_do_not_claim_a_two_millimetre_wall() -> None:
    assert spec.ENTRY_RELIEF_DIA > spec.HOLE_DIA
    assert spec.ENTRY_RELIEF_DIA == retention.CAP_ENTRY_RELIEF_DIAMETER
    assert spec.ENTRY_RELIEF_BAND == retention.CAP_ENTRY_RELIEF_BAND
    assert spec.ENTRY_RELIEF_DEPTH == retention.CAP_ENTRY_RELIEF_DEPTH
    assert spec.ENTRY_RELIEF_DEPTH_PLACES == retention.CAP_ENTRY_RELIEF_DEPTH_PLACES
    assert spec.HEAD_BEARING_DIAMETER_MIN == retention.CAP_BOLT_HEAD_BEARING_DIAMETER_MIN
    margins = spec.require_entry_relief_geometry()
    assert margins == spec.ENTRY_RELIEF_MARGINS
    assert 0.0 < margins["entry_annular_neck"] < 2.0
    assert spec.GEOMETRY_MARGINS["counterbore_floor"] >= 2.0
    assert margins["entry_to_pocket"] >= 2.0
    assert margins["head_flat_concentric_land"] == pytest.approx(
        (spec.HEAD_BEARING_DIAMETER_MIN - spec.ENTRY_RELIEF_DIA - spec.ENTRY_RELIEF_BAND[0]) / 2.0
    )
    assert min(margins.values()) > 0.0


def test_entry_relief_depth_boundary_cannot_be_silently_cut_through() -> None:
    boundary = (
        spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.COUNTERBORE_DEPTH
        - spec.COUNTERBORE_DEPTH_TOLERANCE - printed_band_mm(spec.ENTRY_RELIEF_DEPTH_PLACES)
    )
    assert spec.require_entry_relief_geometry(entry_depth=boundary - 1e-5)["entry_annular_neck"] > 0.0
    with pytest.raises(ValueError, match="entry_annular_neck"):
        spec.require_entry_relief_geometry(entry_depth=boundary + 1e-5)


@pytest.mark.parametrize("change,margin", [
    ({"entry_dia": 24.0}, "entry_to_pocket"),
    ({"entry_dia": spec.HOLE_DIA}, "entry_expansion_over_through_hole"),
    ({"entry_depth": spec.HEIGHT}, "entry_annular_neck"),
    ({"head_bearing_dia_min": spec.ENTRY_RELIEF_DIA + spec.ENTRY_RELIEF_BAND[0]}, "head_flat_concentric_land"),
])
def test_entry_relief_guards_reject_invalid_flat_bottom_geometry(change, margin) -> None:
    assert spec.entry_relief_geometry(**change)[margin] <= 0.0
    with pytest.raises(ValueError):
        spec.require_entry_relief_geometry(**change)


def test_entry_relief_volume_removes_only_the_annulus_below_the_head_seat(monkeypatch) -> None:
    area = len(spec.BOLT_POINTS) * math.pi * (spec.ENTRY_RELIEF_DIA**2 - spec.HOLE_DIA**2) / 4.0
    assert spec.nominal_entry_relief_volume_mm3() == pytest.approx(area * spec.ENTRY_RELIEF_DEPTH)
    original = spec.nominal_volume_mm3()
    monkeypatch.setattr(spec, "ENTRY_RELIEF_DEPTH", spec.ENTRY_RELIEF_DEPTH + 0.2)
    assert spec.nominal_volume_mm3() - original == pytest.approx(-area * 0.2)


def test_clearance_tracks_shared_screw_geometry_without_claiming_a_thread_stop() -> None:
    assert spec.SCREW_MAJOR_LIMITS == (hardware.SCREW_MAJOR_DIA_MIN, hardware.SCREW_MAJOR_DIA_MAX)
    assert spec.SCREW_THREAD_SOURCE_URL == hardware.SCREW_THREAD_SOURCE_URL
    assert spec.HOLE_DIA == retention.CAP_BOLT_CLEARANCE_DIAMETER
    assert spec.HOLE_DIA > spec.SCREW_MAJOR_LIMITS[1]
    assert spec.DRILLED_BAND == retention.CAP_BOLT_CLEARANCE_BAND


def test_actual_formed_side_wire_and_head_fit_below_cap_and_above_channel_floor() -> None:
    wire_low, wire_high = spec.lock_wire.swept_wire_z_bounds(hardware_limits=True)
    margins = spec.require_wire_clearance_geometry()
    assert margins == spec.WIRE_GEOMETRY_MARGINS
    assert min(margins.values()) > 0.0
    minimum_cb_depth = spec.COUNTERBORE_DEPTH - spec.COUNTERBORE_DEPTH_TOLERANCE
    assert margins["head_below_cap"] == pytest.approx(minimum_cb_depth - spec.HEAD_HEIGHT_MAX)
    assert margins["formed_wire_below_cap"] == pytest.approx(minimum_cb_depth - wire_high)
    assert margins["formed_wire_above_channel_floor"] == pytest.approx(
        wire_low - spec.COUNTERBORE_DEPTH - spec.COUNTERBORE_DEPTH_TOLERANCE
        + spec.CHANNEL_DEPTH - printed_band_mm(spec.CHANNEL_PLACES)
    )
    minimum_cb_dia = spec.COUNTERBORE_DIA - printed_band_mm(spec.COUNTERBORE_DIAMETER_PLACES)
    assert (minimum_cb_dia - spec.HEAD_DIAMETER_MAX) / 2.0 > spec.WIRE_DIAMETER
    minimum_channel = spec.CHANNEL_WIDTH - printed_band_mm(spec.CHANNEL_PLACES)
    assert minimum_channel > 2.0 * spec.lock_wire.TWIST_RADIUS + spec.WIRE_DIAMETER
    # A valid side route must not acquire an invented over-head wire gap.
    close_head = minimum_cb_depth - spec.WIRE_DIAMETER / 2.0
    assert spec.require_wire_clearance_geometry(head_height_max=close_head)["head_below_cap"] == pytest.approx(spec.WIRE_DIAMETER / 2.0)


def test_actual_formed_wire_envelope_rejects_roof_and_channel_floor_breakthrough() -> None:
    low, high = spec.lock_wire.swept_wire_z_bounds(hardware_limits=True)
    cap_top = spec.COUNTERBORE_DEPTH - spec.COUNTERBORE_DEPTH_TOLERANCE
    channel_floor = spec.COUNTERBORE_DEPTH + spec.COUNTERBORE_DEPTH_TOLERANCE - spec.CHANNEL_DEPTH + printed_band_mm(spec.CHANNEL_PLACES)
    with pytest.raises(ValueError, match="formed_wire_below_cap"):
        spec.require_wire_clearance_geometry(wire_bounds=(low, cap_top + 0.01))
    with pytest.raises(ValueError, match="formed_wire_above_channel_floor"):
        spec.require_wire_clearance_geometry(wire_bounds=(channel_floor - 0.01, high))
    with pytest.raises(ValueError, match="head_below_cap"):
        spec.require_wire_clearance_geometry(head_height_max=cap_top + 0.01)


def test_pocket_depth_is_fitted_to_actual_flange_not_a_loose_fixed_band() -> None:
    assert spec.fitted_chamber_excess(3.25, 3.0) == pytest.approx(0.25)
    assert spec.fitted_chamber_excess(4.05, 3.8) == pytest.approx(0.25)
    for pocket, flange in ((3.1, 3.0), (3.5, 3.0), (3.3, 3.8)):
        with pytest.raises(ValueError, match="chamber excess"):
            spec.fitted_chamber_excess(pocket, flange)


def test_each_model_dimension_is_printed_once_with_authored_precision() -> None:
    keep_maps = (drawing.TOP_KEEP, drawing.BOTTOM_KEEP, drawing.RIGHT_KEEP, drawing.REGISTER_END_KEEP, drawing.SECTION_KEEP, drawing.BOLT_SECTION_KEEP)
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert sum(map(len, keep_maps)) == len(marked)
    assert set().union(*keep_maps) == marked == set(spec.DRAWING_PRECISION_BY_NAME)
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert all(spec.DRAWING_PRECISION_BY_NAME[f"Bolt{i}{axis}"] == 3 for i in range(1, 5) for axis in ("X", "Y"))
    assert all(spec.DRAWING_PRECISION_BY_NAME[f"{prefix}Center{axis}"] == 2 for prefix in ("Pocket", "Aperture") for axis in ("X", "Y"))
    assert {"PocketCenterX", "PocketCenterY"} <= drawing.BOTTOM_KEEP.keys()
    assert {"ApertureCenterX", "ApertureCenterY"} <= drawing.TOP_KEEP.keys()
    bolt_stations = {f"Bolt{i}{axis}" for i in range(1, 5) for axis in ("X", "Y")}
    assert bolt_stations <= drawing.BOTTOM_KEEP.keys()
    assert not bolt_stations & drawing.TOP_KEEP.keys()
    register_locations = {f"Register{i}{axis}" for i in range(1, 3) for axis in ("X", "Y")}
    assert register_locations <= drawing.BOTTOM_KEEP.keys()
    assert all(spec.DRAWING_PRECISION_BY_NAME[name] == spec.REGISTER_LOCATION_PLACES for name in register_locations)
    assert "RegisterProjection" in drawing.RIGHT_KEEP
    assert "RegisterEndChamfer" in drawing.REGISTER_END_KEEP
    assert spec.DRAWING_PRECISION_BY_NAME["RegisterProjection"] == spec.REGISTER_PROJECTION_PLACES
    assert "EntryReliefDia" in drawing.TOP_KEEP
    assert "EntryReliefDepth" in drawing.BOLT_SECTION_KEEP
    assert spec.DRAWING_PRECISION_BY_NAME["EntryReliefDepth"] == spec.ENTRY_RELIEF_DEPTH_PLACES
    assert {point[1] for point in drawing.BOLT_SECTION_LINE_MODEL} == {min(y for _, y in spec.BOLT_POINTS)}
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_requirement_manifest_keeps_actual_bolt_coordinates_and_fitted_acceptance() -> None:
    features = export_features.requirement_manifest(STEM)["features"]
    selectors = export_features.feature_selectors(STEM)
    assert [name for name in features if name.startswith("cap_bolt_")] == [
        f"cap_bolt_{index}" for index in range(1, len(spec.BOLT_POINTS) + 1)
    ]
    assert features["journal_aperture"]["dia"] == pytest.approx([
        spec.APERTURE_DIA + spec.APERTURE_BAND[1],
        spec.APERTURE_DIA + spec.APERTURE_BAND[0],
    ])
    for index, (x, y) in enumerate(spec.BOLT_POINTS, 1):
        name = f"cap_bolt_{index}"
        feature = features[name]
        assert feature["at"] == pytest.approx([x, y, 0.0])
        assert feature["axis"] == [0.0, 0.0, 1.0]
        assert feature["dia"] == pytest.approx([
            spec.HOLE_DIA + spec.DRILLED_BAND[1],
            spec.HOLE_DIA + spec.DRILLED_BAND[0],
        ])
        assert feature["station_nominal"] == x and feature["width_nominal"] == y
        assert feature["station"] == pytest.approx([x - 0.13, x + 0.13])
        assert feature["width"] == pytest.approx([y - 0.13, y + 0.13])
        assert feature["precision"]["station"] == feature["precision"]["width"] == spec.POSITION_PLACES
        assert {"dia", "station", "width"} <= set(feature["requirements"])
        for selector in selectors[name]:
            assert selector.diameter_mm == spec.HOLE_DIA
            assert (selector.contains_x_mm, selector.contains_y_mm) == (x, y)
        recess = features[f"head_recess_{index}"]
        recess_band = printed_band_mm(spec.COUNTERBORE_DEPTH_PLACES)
        assert recess["depth"] == pytest.approx([
            spec.COUNTERBORE_DEPTH - recess_band, spec.COUNTERBORE_DEPTH + recess_band,
        ])
        assert recess["precision"]["depth"] == spec.COUNTERBORE_DEPTH_PLACES
        entry = features[f"head_entry_relief_{index}"]
        entry_band = printed_band_mm(spec.ENTRY_RELIEF_DEPTH_PLACES)
        assert entry["at"] == [x, y, spec.HEIGHT - spec.COUNTERBORE_DEPTH]
        assert entry["axis"] == [0.0, 0.0, -1.0]
        assert entry["dia"] == pytest.approx([spec.ENTRY_RELIEF_DIA + spec.ENTRY_RELIEF_BAND[1], spec.ENTRY_RELIEF_DIA + spec.ENTRY_RELIEF_BAND[0]])
        assert entry["depth"] == pytest.approx([spec.ENTRY_RELIEF_DEPTH - entry_band, spec.ENTRY_RELIEF_DEPTH + entry_band])
        assert entry["precision"]["depth"] == spec.ENTRY_RELIEF_DEPTH_PLACES
        entry_face, = selectors[f"head_entry_relief_{index}"]
        assert (entry_face.diameter_mm, entry_face.contains_x_mm, entry_face.contains_y_mm) == (spec.ENTRY_RELIEF_DIA, x, y)
        assert entry_face.contains_z_mm == spec.HEIGHT - spec.COUNTERBORE_DEPTH - spec.ENTRY_RELIEF_DEPTH / 2.0
    channel_band = printed_band_mm(spec.CHANNEL_PLACES)
    assert features["wire_channel"]["depth"] == pytest.approx([
        spec.CHANNEL_DEPTH - channel_band, spec.CHANNEL_DEPTH + channel_band,
    ])
    assert features["wire_channel"]["precision"]["depth"] == spec.CHANNEL_PLACES
    for name in ("flange_chamber", "journal_aperture"):
        feature = features[name]
        assert feature["at"] == [0.0, 0.0, 0.0]
        assert feature["axis"] == [0.0, 0.0, 1.0]
        assert feature["station_nominal"] == spec.WIDTH / 2.0
        assert feature["width_nominal"] == spec.LENGTH / 2.0
        band = printed_band_mm(spec.CENTER_LOCATION_PLACES)
        assert feature["station"] == pytest.approx([spec.WIDTH / 2.0 - band, spec.WIDTH / 2.0 + band])
        assert feature["width"] == pytest.approx([spec.LENGTH / 2.0 - band, spec.LENGTH / 2.0 + band])
        assert feature["precision"]["station"] == feature["precision"]["width"] == spec.CENTER_LOCATION_PLACES
        assert {"dia", "station", "width"} <= set(feature["requirements"])
        assert spec.CENTER_LOCATION_NOTE in feature["note"]
    assert spec.DIMENSION_CALLOUTS["PocketDepth"] in features["flange_chamber"]["note"]


def test_requirement_manifest_binds_integral_cylinders_and_real_end_chamfers() -> None:
    manifest = export_features.requirement_manifest(STEM)
    features, selectors = manifest["features"], export_features.feature_selectors(STEM)
    assert manifest["construction"] == "one_piece"
    assert manifest["material"]["thickness"] == spec.TOTAL_HEIGHT
    assert manifest["volume_mm3"] == spec.VOLUME_MM3
    error = printed_band_mm(spec.REGISTER_LOCATION_PLACES)
    projection_error = printed_band_mm(spec.REGISTER_PROJECTION_PLACES)
    for index, (x, y) in enumerate(spec.REGISTER_POINTS, 1):
        name = f"integral_register_{index}"
        feature = features[name]
        assert feature["kind"] == "boss"
        assert feature["at"] == [x, y, 0.0]
        assert feature["axis"] == [0.0, 0.0, -1.0]
        assert feature["dia"] == pytest.approx([spec.REGISTER_DIA + spec.REGISTER_BAND[1], spec.REGISTER_DIA + spec.REGISTER_BAND[0]])
        assert feature["station"] == pytest.approx([x - error, x + error])
        assert feature["width"] == pytest.approx([y - error, y + error])
        assert feature["length"] == pytest.approx([spec.REGISTER_PROJECTION - projection_error, spec.REGISTER_PROJECTION + projection_error])
        cylinder, = selectors[name]
        assert (cylinder.diameter_mm, cylinder.contains_x_mm, cylinder.contains_y_mm) == (spec.REGISTER_DIA, x, y)
        assert cylinder.contains_z_mm == -spec.REGISTER_PROJECTION / 2.0
        chamfer = features[f"register_end_chamfer_{index}"]
        assert chamfer["kind"] == "chamfer"
        assert chamfer["length"] == [0.0, spec.REGISTER_END_CHAMFER_MAX]
        assert chamfer["at"] == [x, y, -spec.REGISTER_PROJECTION]
        cone, = selectors[f"register_end_chamfer_{index}"]
        assert cone.half_angle_degrees == 45.0 and cone.contains_x_mm == x
        assert feature["cite"]["length"] and chamfer["cite"]["length"]


class _CircleAdapter:
    def __init__(self, previous=False, failure=None):
        self.failure = failure
        self.raw_points = []
        self.points = {"origin": (0.0, 0.0)}
        self.circles = []
        self.dimensions = []
        adapter = self

        class Manager:
            AddToDB = previous

            def CreatePoint(self, x, y, z):
                assert self.AddToDB
                if adapter.failure == "point":
                    return None
                adapter.raw_points.append((x, y, z))
                return (x, y, z)

        self.currentSketchManager = Manager()

    def _register_sketch_entity(self, kind, raw):
        assert kind == "Point"
        assert raw in self.raw_points
        self.points["Point1"] = (raw[0] * 1000.0, raw[1] * 1000.0)
        return "Point1"

    async def add_circle(self, x, y, radius):
        assert self.currentSketchManager.AddToDB
        if self.failure == "circle":
            return SimpleNamespace(is_success=False, data=None, error="native circle failure")
        self.circles.append((x, y, radius))
        self.points["Circle1.center"] = (x, y)
        return SimpleNamespace(is_success=True, data="Circle1", error=None)

    async def add_sketch_dimension(self, first, second, kind, value):
        if kind == "diameter":
            assert (first, second) == ("Circle1", None)
            assert value == pytest.approx(2.0 * self.circles[0][2])
        else:
            axis = {"horizontal_distance": 0, "vertical_distance": 1}[kind]
            assert value == pytest.approx(abs(self.points[second][axis] - self.points[first][axis]))
        self.dimensions.append((first, second, kind, value))
        return SimpleNamespace(is_success=True, data=f"D{len(self.dimensions)}", error=None)


@pytest.mark.parametrize("prefix,dia", [("Pocket", spec.POCKET_DIA), ("Aperture", spec.APERTURE_DIA)])
@pytest.mark.parametrize("width,length", [(spec.WIDTH, spec.LENGTH), (62.0, 86.0)])
@pytest.mark.parametrize("previous", [False, True])
def test_native_circles_are_located_by_five_ordered_dimensions_from_one_real_corner(
    monkeypatch, prefix, dia, width, length, previous,
) -> None:
    monkeypatch.setattr(spec, "WIDTH", width)
    monkeypatch.setattr(spec, "LENGTH", length)
    adapter = _CircleAdapter(previous=previous)
    dims = part.SketchDims()
    asyncio.run(part._circle_from_stock_corner(adapter, dia, prefix, dims))
    assert adapter.raw_points == [(-width / 2000.0, -length / 2000.0, 0.0)]
    assert adapter.circles == [(0.0, 0.0, dia / 2.0)]
    assert adapter.dimensions == [
        ("Point1", "origin", "horizontal_distance", width / 2.0),
        ("Point1", "origin", "vertical_distance", length / 2.0),
        ("Point1", "Circle1.center", "horizontal_distance", width / 2.0),
        ("Point1", "Circle1.center", "vertical_distance", length / 2.0),
        ("Circle1", None, "diameter", dia),
    ]
    assert dims._rows == [
        (f"{prefix}CornerX", '"CapWidth"/2'),
        (f"{prefix}CornerY", '"CapLength"/2'),
        (f"{prefix}CenterX", '"CapWidth"/2'),
        (f"{prefix}CenterY", '"CapLength"/2'),
        (f"{prefix}Dia", f'"{prefix}Dia"'),
    ]
    assert adapter.currentSketchManager.AddToDB is previous
    marked = spec.DRAWING_DIMENSIONS[f"{prefix}Profile"]
    assert {f"{prefix}CornerX", f"{prefix}CornerY"}.isdisjoint(marked)


@pytest.mark.parametrize("failure", ["point", "circle"])
@pytest.mark.parametrize("previous", [False, True])
def test_native_circle_creation_failure_restores_inference_state(failure, previous) -> None:
    adapter = _CircleAdapter(previous=previous, failure=failure)
    with pytest.raises(RuntimeError):
        asyncio.run(part._circle_from_stock_corner(adapter, spec.POCKET_DIA, "Pocket", part.SketchDims()))
    assert adapter.currentSketchManager.AddToDB is previous
    assert not adapter.circles
    assert len(adapter.dimensions) == (0 if failure == "point" else 2)


class _RegisterAdapter:
    def __init__(self, *, previous=False, fail_circle=False):
        self.currentSketchManager = SimpleNamespace(AddToDB=previous)
        self.pocket_circle = object()
        self.fail_circle = fail_circle
        self.registrations = []
        self.circles = []
        self.dimensions = []
        self.points = {"ExternalPocket.center": (0.0, 0.0)}
        self.sketches = []
        self.extrusions = []
        self.chamfers = []
        self.names = []

    def _register_sketch_entity(self, kind, raw):
        assert kind == "Circle" and raw is self.pocket_circle
        self.registrations.append(raw)
        return "ExternalPocket"

    async def create_sketch(self, plane):
        self.sketches.append(plane)
        return SimpleNamespace(is_success=True, data="Sketch", error=None)

    async def exit_sketch(self):
        return SimpleNamespace(is_success=True, data=None, error=None)

    async def add_circle(self, x, y, radius):
        assert self.currentSketchManager.AddToDB
        if self.fail_circle:
            return SimpleNamespace(is_success=False, data=None, error="native circle failed")
        self.circles.append((x, y, radius))
        name = f"Circle{len(self.circles)}"
        self.points[f"{name}.center"] = (x, y)
        return SimpleNamespace(is_success=True, data=name, error=None)

    async def add_sketch_dimension(self, first, second, kind, value):
        if kind == "diameter":
            assert second is None
        else:
            axis = {"horizontal_distance": 0, "vertical_distance": 1}[kind]
            assert value == pytest.approx(abs(self.points[second][axis] - self.points[first][axis]))
        self.dimensions.append((first, second, kind, value))
        return SimpleNamespace(is_success=True, data=f"D{len(self.dimensions)}", error=None)

    async def create_extrusion(self, params):
        self.extrusions.append(params)
        return SimpleNamespace(is_success=True, data=None, error=None)

    async def add_chamfer(self, distance, edge_points, face_points=None, tangent_propagation=False):
        self.chamfers.append((distance, edge_points, face_points, tangent_propagation))
        return SimpleNamespace(is_success=True, data=None, error=None)


@pytest.mark.parametrize("previous", [False, True])
def test_register_native_coordinates_reference_the_original_pocket_circle_not_origin(previous) -> None:
    adapter = _RegisterAdapter(previous=previous)
    dims = part.SketchDims()
    asyncio.run(part._register_circles(adapter, adapter.pocket_circle, dims))
    assert adapter.registrations == [adapter.pocket_circle]
    assert adapter.circles == [(x, y, spec.REGISTER_DIA / 2.0) for x, y in spec.REGISTER_POINTS]
    expected = []
    for index, (x, y) in enumerate(spec.REGISTER_POINTS, 1):
        expected.extend((
            ("ExternalPocket.center", f"Circle{index}.center", "horizontal_distance", abs(x)),
            ("ExternalPocket.center", f"Circle{index}.center", "vertical_distance", abs(y)),
            (f"Circle{index}", None, "diameter", spec.REGISTER_DIA),
        ))
    assert adapter.dimensions == expected
    assert dims._rows == [
        ("Register1X", '"RegisterX"'), ("Register1Y", '"RegisterY"'), ("RegisterDia", '"RegisterDia"'),
        ("Register2X", '"RegisterX"'), ("Register2Y", '"RegisterY"'), ("RegisterDia2", '"RegisterDia"'),
    ]
    assert adapter.currentSketchManager.AddToDB is previous


@pytest.mark.parametrize("previous", [False, True])
def test_register_circle_failure_restores_native_inference_state(previous) -> None:
    adapter = _RegisterAdapter(previous=previous, fail_circle=True)
    with pytest.raises(RuntimeError, match="native circle failed"):
        asyncio.run(part._register_circles(adapter, adapter.pocket_circle, part.SketchDims()))
    assert adapter.currentSketchManager.AddToDB is previous
    assert not adapter.circles and not adapter.dimensions


def test_register_native_recipe_merges_below_seating_plane_and_chamfers_only_free_ends(monkeypatch) -> None:
    adapter = _RegisterAdapter()

    async def fully_defined(_adapter, _label):
        assert _adapter is adapter

    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(part, "name_last_feature", lambda current, name: current.names.append(name))
    monkeypatch.setattr(part, "name_dimensions", lambda _adapter, feature, names: [f"{name}@{feature}" for name in names])
    monkeypatch.setattr(part.SketchDims, "apply", lambda dims, _adapter, feature: [(f"{name}@{feature}", expression) for name, expression in dims._rows])
    jobs = asyncio.run(part._integral_registers(adapter, adapter.pocket_circle))
    assert adapter.sketches == ["Front"]
    assert adapter.names == ["RegisterProfile", "Registers", "RegisterEndChamfers"]
    extrusion, = adapter.extrusions
    assert extrusion.depth == spec.REGISTER_PROJECTION
    assert extrusion.reverse_direction and extrusion.merge_result
    assert not extrusion.both_directions and not extrusion.thin_feature
    assert adapter.chamfers == [(
        spec.REGISTER_END_CHAMFER_MAX,
        [[x + spec.REGISTER_DIA / 2.0, y, -spec.REGISTER_PROJECTION] for x, y in spec.REGISTER_POINTS],
        None, False,
    )]
    assert jobs[-2:] == [
        ("RegisterProjection@Registers", '"RegisterProjection"'),
        ("RegisterEndChamfer@RegisterEndChamfers", '"RegisterEndChamfer"'),
    ]


def test_entry_relief_native_recipe_cuts_from_head_seat_not_top_or_seating_face(monkeypatch) -> None:
    adapter = _RegisterAdapter()
    circles, cuts = [], []

    async def define_circle(_adapter, x, y, radius, label, *, dims, names, drives):
        assert _adapter is adapter
        circles.append((x, y, radius, names, drives))
        for name, expression in zip(names, drives, strict=True):
            dims.record(name, expression)

    async def fully_defined(_adapter, _label):
        assert _adapter is adapter

    async def cut(params):
        cuts.append(params)
        return SimpleNamespace(is_success=True, data=None, error=None)

    monkeypatch.setattr(part, "define_circle", define_circle)
    monkeypatch.setattr(part, "ensure_fully_defined", fully_defined)
    monkeypatch.setattr(adapter, "create_cut_extrude", cut, raising=False)
    monkeypatch.setattr(part, "name_last_feature", lambda current, name: current.names.append(name))
    monkeypatch.setattr(part, "name_dimensions", lambda _adapter, feature, names: [f"{name}@{feature}" for name in names])
    monkeypatch.setattr(part.SketchDims, "apply", lambda dims, _adapter, feature: [(f"{name}@{feature}", expression) for name, expression in dims._rows])
    jobs = asyncio.run(part._entry_reliefs(adapter))
    assert adapter.sketches == [spec.BOLT_SEAT_PLANE]
    assert adapter.names == ["EntryReliefProfile", "EntryReliefs"]
    assert [(x, y, radius) for x, y, radius, _, _ in circles] == [
        (x, y, spec.ENTRY_RELIEF_DIA / 2.0) for x, y in spec.BOLT_POINTS
    ]
    extrusion, = cuts
    assert extrusion.depth == spec.ENTRY_RELIEF_DEPTH
    assert not extrusion.reverse_direction and not extrusion.both_directions and not extrusion.thin_feature
    assert jobs[-1] == ("EntryReliefDepth@EntryReliefs", '"EntryReliefDepth"')


@pytest.mark.parametrize("failure", [None, "nominal", "reject", "readback"])
def test_register_chamfer_max_is_native_and_read_back(monkeypatch, failure) -> None:
    maximum = spec.REGISTER_END_CHAMFER_MAX / 1000.0

    class Tolerance:
        Type = 0
        values = None

        def SetValues(self, lower, upper):
            self.values = (lower, upper)
            return failure != "reject"

        def GetMinValue(self):
            return self.values[0]

        def GetMaxValue(self):
            return self.values[1] + (1e-5 if failure == "readback" else 0.0)

    tolerance = Tolerance()
    dimension = SimpleNamespace(SystemValue=maximum + (0.001 if failure == "nominal" else 0.0), Tolerance=tolerance)
    monkeypatch.setattr(part, "_named_dimension", lambda *_args: (None, dimension))
    monkeypatch.setattr(part, "_early_bound", lambda value, _interface: value)
    if failure is not None:
        with pytest.raises(RuntimeError):
            part._register_chamfer_maximum(object())
    else:
        part._register_chamfer_maximum(object())
        assert tolerance.Type == 6
        assert tolerance.values == (-maximum, 0.0)


def test_ordinary_center_dimensions_have_clear_lanes_within_the_paper_boundaries() -> None:
    # Landscape ASME B template's inner border and title-block keep-out.
    left, bottom, right, top = 0.0124, 0.0124, 0.4194, 0.267
    title_left, title_top = 0.216, 0.0652
    maps = (drawing.TOP_KEEP, drawing.BOTTOM_KEEP, drawing.RIGHT_KEEP, drawing.REGISTER_END_KEEP, drawing.SECTION_KEEP, drawing.BOLT_SECTION_KEEP)
    for keep in maps:
        for x, y in keep.values():
            assert left + 0.004 < x < right - 0.004
            assert bottom + 0.004 < y < top - 0.004
            assert x < title_left or y > title_top + 0.004
    top_left = drawing.TOP_CENTER[0] - spec.WIDTH / 2000.0
    top_bottom = drawing.TOP_CENTER[1] - spec.LENGTH / 2000.0
    assert drawing.TOP_KEEP["ApertureCenterY"][0] < top_left - 0.006
    assert drawing.TOP_KEEP["CapWidth"][1] + 0.006 < drawing.TOP_KEEP["ApertureCenterX"][1] < top_bottom - 0.006
    bottom_right = drawing.BOTTOM_CENTER[0] + spec.WIDTH / 2000.0
    right_view_left = drawing.RIGHT_CENTER[0] - spec.HEIGHT / 2000.0
    assert bottom_right + 0.006 < drawing.BOTTOM_KEEP["PocketCenterY"][0] < right_view_left - 0.006
    section_top = drawing.SECTION_CENTER[1] + spec.HEIGHT / 2000.0
    assert section_top + 0.008 < drawing.BOTTOM_KEEP["PocketCenterX"][1]
    assert drawing.BOTTOM_KEEP["PocketCenterX"][1] + 0.006 < drawing.BOTTOM_KEEP["Bolt3X"][1]
    # The permanent XZ projection is third-angle aligned above the face view.
    profile_half_width = spec.WIDTH / 2000.0
    profile_half_height = spec.TOTAL_HEIGHT / 2000.0
    profile_x, profile_y = drawing.REGISTER_END_CENTER
    assert profile_x == drawing.TOP_CENTER[0]
    assert profile_y - profile_half_height > drawing.TOP_KEEP["ApertureDia"][1] + 0.006
    # Leave the counterbore's two-line note above the added profile, while
    # the chamfer text sits wholly beyond its right-hand stock edge.
    assert drawing.TOP_KEEP["CounterboreDia"][1] - 0.010 > profile_y + profile_half_height
    assert drawing.REGISTER_END_KEEP["RegisterEndChamfer"][0] > profile_x + profile_half_width + 0.006


def test_native_recipe_adapter_calls_bind_to_the_real_interface() -> None:
    tree = ast.parse(RECIPE.read_text(encoding="utf-8"), filename=str(RECIPE))
    calls = _adapter_calls(tree)
    assert not _missing(tree)
    for call in calls:
        _, method = _adapter_methods()[call.func.attr]
        _signature(method).bind(call.func.value, *call.args, **{kw.arg: kw.value for kw in call.keywords})
    mutant = copy.deepcopy(tree)
    extrusion = next(call for call in _adapter_calls(mutant) if call.func.attr == "create_extrusion")
    extrusion.func.attr = "create_extrude"
    assert _missing(mutant) == {"create_extrude"}


def test_configuration_identity() -> None:
    row = _config.parts(DASHED)
    assert row["number"] == "MHA-CH-06-TL-30" and row["quantity"] == 2
    assert len(row["finish"]) <= 40 and "\n" not in row["finish"]

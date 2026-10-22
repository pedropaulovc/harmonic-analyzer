"""Offline definition/native-recipe contracts for MHA-CH-06-TL-30.

Geometry-only adapters exercise recipes without a SolidWorks connection.
Native readback and sheet review remain the integration owner's acceptance gates.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import math
from dataclasses import replace
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_ch_rocker_arm_tl_oblique_pivot_cap as part
import ch_rocker_arm_tl_oblique_pivot_cap_spec as spec
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import draw_ch_rocker_arm_tl_oblique_pivot_cap as drawing
import export_features
from _printed_tolerance import printed_band_mm
from test_pd_transgear_adapter_contract import _adapter_calls, _adapter_methods, _missing, _signature

STEM = "ch_rocker_arm_tl_oblique_pivot_cap"
RECIPE = Path(__file__).with_name(f"build_{STEM}.py")


def test_cap_and_integral_registers_fit_inside_the_available_stock() -> None:
    assert spec.TOTAL_HEIGHT + spec.HEIGHT_TOLERANCE + printed_band_mm(spec.REGISTER_PROJECTION_PLACES) < spec.STOCK_THICKNESS
    assert spec.STOCK_WIDTH > spec.WIDTH + 2.0 * printed_band_mm(spec.OUTLINE_PLACES)
    assert spec.STOCK_LENGTH_MIN > spec.LENGTH + 2.0 * printed_band_mm(spec.OUTLINE_PLACES)


def test_native_dimensions_keep_their_sheet_view_and_source_ownership(monkeypatch, tmp_path) -> None:
    source = tmp_path / "cap.SLDPRT"
    source.touch()
    monkeypatch.setattr(drawing, "SOURCE", source)
    views, imports, precision_checks, callouts, finalized = [], [], [], [], []
    sheets, activations, headings, centre_checks = [], [], [], []
    view_labels = []
    near_sides = []
    active_sheet = None

    async def open_model(path):
        assert path == str(source)
        return SimpleNamespace(is_success=True, data=None, error=None)

    def activate(name):
        nonlocal active_sheet
        assert name in sheets
        active_sheet = name
        activations.append(name)
        return True

    model = object()
    document = SimpleNamespace(ActivateSheet=activate)
    adapter = SimpleNamespace(currentModel=model, open_model=open_model)

    def bind(obj, interface):
        assert obj is model and interface == "IDrawingDoc"
        return document

    def create_sheets(current, names, *, label):
        nonlocal active_sheet
        assert current is adapter and not views and label
        sheets.extend(names)
        active_sheet = names[-1]

    def heading(current, text, x, y):
        assert current is adapter
        if (x, y) == drawing.SHEET_HEADING_XY:
            headings.append((active_sheet, text))
        else:
            view_labels.append((active_sheet, text))
        return object()

    def place(current, path, orientation, x, y, *, scale):
        assert current is adapter and path == str(source) and active_sheet in sheets
        view = SimpleNamespace(
            orientation=orientation, center=(x, y), scale=scale,
            sheet=active_sheet, annotations=[],
        )
        views.append(view)
        return view

    def section(_adapter, parent, **kwargs):
        assert parent.sheet == active_sheet and parent.orientation == "*Back"
        view = SimpleNamespace(
            orientation=kwargs["section_label"], sheet=active_sheet,
            scale=kwargs["scale"], parent=parent, annotations=[],
        )
        views.append(view)
        return view

    def curate(current, view, *, keep, view_label, dimensions_by_feature):
        assert current is adapter and dimensions_by_feature is spec.DRAWING_DIMENSIONS
        assert view.sheet == active_sheet and view_label
        imports.append((view, keep))
        view.annotations[:] = [SimpleNamespace(name=name) for name in keep]
        return list(view.annotations)

    def precision(_adapter, annotations, expected):
        assert expected == {item.name: spec.DRAWING_PRECISION_BY_NAME[item.name] for item in annotations}
        precision_checks.extend(annotations)

    def set_callouts(_adapter, annotations, expected, *, location):
        names = {item.name for item in annotations}
        assert expected == {name: text for name, text in spec.DIMENSION_CALLOUTS.items() if name in names}
        assert location == "below"
        callouts.extend(annotations)

    def centres(view, *, expected, label):
        assert view.sheet == active_sheet and label
        assert expected == (5 if view.orientation == "*Front" else 7)
        centre_checks.append(view)

    async def finalize(_adapter, outputs, **kwargs):
        assert kwargs["expected_sheet_names"] == drawing.SHEET_NAMES
        assert kwargs["sheet_scales"] == {name: drawing.SHEET_SCALE for name in drawing.SHEET_NAMES}
        finalized.append(outputs)
        return {"slddrw": "cap.SLDDRW"}

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "read_required_properties", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "new_project_drawing", lambda *_args, **_kwargs: (model, object()))
    monkeypatch.setattr(drawing, "create_blank_drawing_sheets", create_sheets)
    monkeypatch.setattr(drawing, "stamp_drawing_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "add_note", heading)
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "create_section_view", section)
    monkeypatch.setattr(drawing, "_project", lambda *_args: (0.0, 0.0))
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda _adapter, view: setattr(view, "hidden_removed", True))
    monkeypatch.setattr(drawing, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "assert_imported_precision", precision)
    monkeypatch.setattr(drawing, "set_dimension_callouts", set_callouts)
    monkeypatch.setattr(drawing, "offset_dimension_text", lambda *_args: None)
    monkeypatch.setattr(drawing, "_assert_pocket_corner_callout", lambda *_args: None)
    monkeypatch.setattr(drawing, "_assert_template_center_marks", centres)
    monkeypatch.setattr(drawing, "add_surface_finish", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "add_property_linked_note", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "set_near_side_diameter", lambda annotation, _label: near_sides.append(annotation))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "finalize_drawing", finalize)

    assert asyncio.run(drawing.build(adapter)) == {"slddrw": "cap.SLDDRW"}
    assert {annotation.name for annotation in precision_checks} == set(spec.DRAWING_PRECISION_BY_NAME)
    assert len(precision_checks) == len(spec.DRAWING_PRECISION_BY_NAME)
    assert finalized == [drawing.OUTPUTS]
    assert len(views) == 9 and all(view.hidden_removed for view in views)
    assert len(centre_checks) == 5
    assert all(sheet == drawing.SHEET_NAMES[3] for sheet, _text in view_labels)
    assert tuple(sheets) == drawing.SHEET_NAMES == tuple(activations)
    assert [sheet for sheet, _text in headings] == sheets
    owners = {name: view for view, keep in imports for name in keep}
    # Native d349's WireWidth shoulder crossed PocketDepth's witness. These
    # manufacturing groups now occupy different actual sheets, not a waiver.
    assert owners["WireWidth"].sheet == drawing.SHEET_NAMES[0]
    assert owners["PocketDepth"].sheet == drawing.SHEET_NAMES[1]
    assert all(owners[f"Bolt{i}{axis}"].sheet == drawing.SHEET_NAMES[2] for i in range(1, 5) for axis in ("X", "Y"))
    assert all(owners[f"Register{i}{axis}"].sheet == drawing.SHEET_NAMES[3] for i in range(1, 3) for axis in ("X", "Y"))
    assert owners["RegisterProjection"].orientation == "*Right"
    assert [annotation.name for annotation in near_sides] == ["CounterboreDia"]
    assert all(annotation in owners[annotation.name].annotations for annotation in near_sides)


@pytest.mark.parametrize("names", [
    ("CounterboreDia",),
    ("CounterboreDia", "CounterboreDia"),
    (),
])
def test_head_diameter_routing_requires_one_native_counterbore_annotation(monkeypatch, names) -> None:
    annotations = [SimpleNamespace(name=name) for name in names]
    routed = []
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "curate_view_dimensions", lambda *_args, **_kwargs: annotations)
    monkeypatch.setattr(drawing, "assert_imported_precision", lambda *_args: None)
    monkeypatch.setattr(drawing, "set_dimension_callouts", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "set_near_side_diameter", lambda annotation, _label: routed.append(annotation))
    monkeypatch.setattr(drawing, "rebuild_drawing", lambda *_args, **_kwargs: None)
    views = ((object(), {"CounterboreDia": drawing.TOP_KEEP["CounterboreDia"]}, "head access"),)
    if len(names) == 1:
        drawing._annotate_views(object(), views)
        assert routed == annotations
    else:
        with pytest.raises(RuntimeError, match="one native head diameter"):
            drawing._annotate_views(object(), views)
        assert routed == []


@pytest.mark.parametrize("expected", (5, 7))
@pytest.mark.parametrize("difference", (-1, 0, 1))
def test_template_centre_mark_census_refuses_missing_or_overdrawn_features(monkeypatch, expected, difference) -> None:
    requested_types = []

    def get_annotations(kind):
        requested_types.append(kind)
        return tuple(object() for _ in range(expected + difference))

    view = SimpleNamespace(GetAnnotationsByType=get_annotations)
    bindings = []

    def bind(obj, interface):
        bindings.append((obj, interface))
        return obj

    monkeypatch.setattr(drawing, "_early_bound", bind)
    if difference:
        with pytest.raises(RuntimeError, match="template centre marks"):
            drawing._assert_template_center_marks(view, expected=expected, label="cap view")
    else:
        drawing._assert_template_center_marks(view, expected=expected, label="cap view")
    assert bindings == [(view, "IView")] and requested_types == [13]


@pytest.mark.parametrize("unreadable", (None, False, "five", 5))
def test_template_centre_mark_census_does_not_treat_unreadable_arrays_as_empty(monkeypatch, unreadable) -> None:
    view = SimpleNamespace(GetAnnotationsByType=lambda _kind: unreadable)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _interface: obj)
    with pytest.raises(RuntimeError, match="template centre marks"):
        drawing._assert_template_center_marks(view, expected=5, label="cap view")


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
    assert margins["counterbore_floor"] == spec.COUNTERBORE_FLOOR_MIN
    fitted = spec.require_fitted_counterbore_geometry()
    assert fitted["nominal_floor"] >= margins["counterbore_floor"]
    assert fitted["parallel_cut_floor"] >= margins["counterbore_floor"]
    assert margins["chamber_roof"] == pytest.approx(spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.FITTED_POCKET_DEPTH_MAX)
    assert margins["channel_floor"] == pytest.approx(spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.CHANNEL_DEPTH - printed_band_mm(spec.CHANNEL_PLACES))
    # Deliberate mouths are not counted as nonexistent outside-X material.
    assert not any("mouth_to_x_edge" in key for key in margins)


@pytest.mark.parametrize("change", [
    {"channel_depth": 9.0},
    {"pocket_dia": 49.0}, {"counterbore_dia": 23.0},
    {"points": tuple((x / 2.0, y / 2.0) for x, y in spec.BOLT_POINTS)},
])
def test_material_checks_reject_breakthrough_and_thin_wall_mutants(change) -> None:
    with pytest.raises(ValueError, match="material target"):
        spec.require_clearance_geometry(**change)


@pytest.mark.parametrize("depth_delta", (-0.01, 0.01))
def test_fitted_pocket_depth_preserves_the_actual_two_mm_roof_boundary(
    depth_delta: float,
) -> None:
    target = 2.0
    boundary_depth = spec.HEIGHT - spec.HEIGHT_TOLERANCE - target
    depth = boundary_depth + depth_delta
    assert spec.clearance_geometry(fitted_pocket_depth_max=depth)["chamber_roof"] == pytest.approx(
        target - depth_delta
    )
    if depth_delta < 0.0:
        assert spec.require_clearance_geometry(fitted_pocket_depth_max=depth)["chamber_roof"] > target
    else:
        with pytest.raises(ValueError):
            spec.require_clearance_geometry(fitted_pocket_depth_max=depth)


@pytest.mark.parametrize("change,margin", [
    ({"channel_depth": 9.0}, "channel_floor"),
    ({"counterbore_dia": spec.COUNTERBORE_DIA + 2.0}, "counterbore_to_y_edge"),
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
    head_void_area = sum(
        math.pi * radius**2 / 2.0
        + spec.COUNTERBORE_DIA * (spec.WIDTH / 2.0 - abs(x))
        - math.pi * (spec.HOLE_DIA / 2.0)**2
        for x, _y in spec.BOLT_POINTS
    )
    changes = (
        ("LENGTH", spec.LENGTH + 2.0, 2.0 * spec.WIDTH * spec.HEIGHT),
        ("WIDTH", spec.WIDTH + 2.0, 2.0 * spec.LENGTH * spec.HEIGHT - len(spec.BOLT_POINTS) * spec.COUNTERBORE_DIA * spec.COUNTERBORE_DEPTH),
        ("APERTURE_DIA", spec.APERTURE_DIA + 1.0, -math.pi * ((spec.APERTURE_DIA + 1.0)**2 - spec.APERTURE_DIA**2) / 4.0 * (spec.HEIGHT - spec.POCKET_DEPTH)),
        ("CHANNEL_DEPTH", spec.CHANNEL_DEPTH + 1.0, -channel_area),
        ("COUNTERBORE_DEPTH", spec.COUNTERBORE_DEPTH + 0.02, -0.02 * head_void_area),
        ("HOLE_DIA", spec.HOLE_DIA + 0.2, -len(spec.BOLT_POINTS) * math.pi * ((spec.HOLE_DIA + 0.2)**2 - spec.HOLE_DIA**2) / 4.0 * (spec.HEIGHT - spec.COUNTERBORE_DEPTH)),
    )
    for name, value, volume_change in changes:
        with monkeypatch.context() as changed:
            changed.setattr(spec, name, value)
            assert spec.nominal_volume_mm3() - original == pytest.approx(volume_change)


def test_single_bore_clears_the_thread_and_actual_underhead_fillet_envelopes() -> None:
    minimum_bore = spec.HOLE_DIA + spec.DRILLED_BAND[1]
    assert minimum_bore > hardware.SCREW_MAJOR_DIA_MAX
    # Bound the complete sourced fillet cylinder, not only its thread major.
    # The cap floor and the permitted head-bearing face can tilt independently.
    angle = math.radians(
        retention.GENERAL_ANGULAR_BAND_DEGREES + hardware.SCREW_BEARING_ANGLE_MAX_DEGREES
    )
    projected_radius = (
        hardware.SCREW_FILLET_JUNCTION_DIA_MAX / (2.0 * math.cos(angle))
        + hardware.SCREW_FILLET_LENGTH_MAX * math.tan(angle)
    )
    assert minimum_bore / 2.0 > projected_radius
    assert (
        spec.HOLE_DIA + spec.DRILLED_BAND[0]
        < hardware.SCREW_HEAD_BEARING_DIA_MIN
    )


def test_representative_normal_side_wire_fits_the_nominal_cap_and_channel() -> None:
    wire_low, wire_high = spec.lock_wire.swept_wire_z_bounds(hardware_limits=True)
    margins = spec.require_wire_clearance_geometry()
    assert margins == spec.WIRE_GEOMETRY_MARGINS
    assert min(margins.values()) > 0.0
    head_gap = retention.CAP_HEAD_SEATING_GAP_MAX
    assert margins["formed_wire_below_cap"] == pytest.approx(spec.COUNTERBORE_DEPTH - wire_high - head_gap)
    assert margins["formed_wire_above_channel_floor"] == pytest.approx(
        wire_low - spec.COUNTERBORE_DEPTH + spec.CHANNEL_DEPTH - printed_band_mm(spec.CHANNEL_PLACES)
    )
    minimum_cb_dia = spec.COUNTERBORE_DIA - printed_band_mm(spec.COUNTERBORE_DIAMETER_PLACES)
    assert (minimum_cb_dia - spec.HEAD_DIAMETER_MAX) / 2.0 > spec.WIRE_DIAMETER
    minimum_channel = spec.CHANNEL_WIDTH - printed_band_mm(spec.CHANNEL_PLACES)
    assert minimum_channel > 2.0 * spec.lock_wire.TWIST_RADIUS + spec.WIRE_DIAMETER


def test_representative_normal_wire_route_rejects_roof_and_channel_breakthrough() -> None:
    low, high = spec.lock_wire.swept_wire_z_bounds(hardware_limits=True)
    cap_top = spec.COUNTERBORE_DEPTH - retention.CAP_HEAD_SEATING_GAP_MAX
    channel_floor = spec.COUNTERBORE_DEPTH - spec.CHANNEL_DEPTH + printed_band_mm(spec.CHANNEL_PLACES)
    with pytest.raises(ValueError, match="formed_wire_below_cap"):
        spec.require_wire_clearance_geometry(wire_bounds=(low, cap_top + 0.01))
    with pytest.raises(ValueError, match="formed_wire_above_channel_floor"):
        spec.require_wire_clearance_geometry(wire_bounds=(channel_floor - 0.01, high))


@pytest.mark.parametrize("fraction", (0.99, 1.01))
def test_normal_underhead_gap_consumes_wire_recess_not_channel_floor(fraction) -> None:
    seated = spec.require_wire_clearance_geometry(head_seating_gap_max=0.0)
    gap = fraction * seated["formed_wire_below_cap"]
    if fraction < 1.0:
        lifted = spec.require_wire_clearance_geometry(head_seating_gap_max=gap)
        assert lifted["formed_wire_below_cap"] == pytest.approx(seated["formed_wire_below_cap"] - gap)
        assert lifted["formed_wire_above_channel_floor"] == pytest.approx(
            seated["formed_wire_above_channel_floor"]
        )
    else:
        with pytest.raises(ValueError, match="formed_wire_below_cap"):
            spec.require_wire_clearance_geometry(head_seating_gap_max=gap)


def test_whole_fixed_head_wire_route_keeps_all_capture_surfaces_clear() -> None:
    bounds = spec.WIRE_CAPTURE_BOUNDS
    for name in (
        "lateral_clearance", "channel_floor_clearance", "top_clearance",
        "head_bearing_floor_clearance", "head_support_x_clearance",
    ):
        assert math.isfinite(getattr(bounds, name)) and getattr(bounds, name) > 0.0


@pytest.mark.parametrize("change", [
    {"channel_width": 2.50},
    {"channel_depth": 4.00},
    {"counterbore_diameter": 16.50},
])
def test_whole_wire_capture_rejects_solid_wall_and_floor_intersection_mutants(change) -> None:
    with pytest.raises(ValueError):
        spec.wire_capture.require_wire_capture_geometry(**change)


def test_whole_route_guard_includes_bridge_interior_not_only_endpoints() -> None:
    segments = list(spec.lock_wire.installed_wire_segments())
    index = min(range(len(segments)), key=lambda i: max(abs(point[0]) for point in segments[i]))
    original = segments[index]
    bend = list(original)
    x, y, z = bend[1]
    bend[1] = (x, y + 20.0, z)
    segments[index] = tuple(bend)
    # Both endpoints still fit; the changed interior bows into cap material.
    assert segments[index][0] == original[0] and segments[index][-1] == original[-1]
    with pytest.raises(ValueError):
        spec.wire_capture.require_wire_capture_geometry(segments=tuple(segments))


@pytest.mark.parametrize("head_recess", (0.50, 0.55, 0.60))
@pytest.mark.parametrize("floor", (2.00, 2.25))
def test_actual_fitted_counterbore_accepts_inclusive_recess_and_whole_floor_limits(head_recess, floor) -> None:
    accepted = spec.fitted_counterbore_acceptance(head_recess=head_recess, whole_floor_min=floor)
    assert accepted == {"head_recess": head_recess, "whole_floor_min": floor}


@pytest.mark.parametrize("change", [
    {"head_recess": 0.50 - 1e-6}, {"head_recess": 0.60 + 1e-6},
    {"whole_floor_min": 2.00 - 1e-6}, {"forced_fit": True},
])
def test_actual_fitted_counterbore_rejects_outside_limits_and_forced_fit(change) -> None:
    measured = {"head_recess": 0.55, "whole_floor_min": 2.00, **change}
    with pytest.raises(ValueError):
        spec.fitted_counterbore_acceptance(**measured)


@pytest.mark.parametrize("name", ("head_recess", "whole_floor_min"))
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_actual_fitted_counterbore_rejects_nonfinite_measurements(name, value) -> None:
    measured = {"head_recess": 0.55, "whole_floor_min": 2.00, name: value}
    with pytest.raises(ValueError, match="finite"):
        spec.fitted_counterbore_acceptance(**measured)


def test_representative_nominal_cut_meets_fitted_head_acceptance_and_constructive_window() -> None:
    nominal = spec.require_fitted_counterbore_geometry()
    assert nominal == spec.FITTED_COUNTERBORE_GEOMETRY
    assert spec.COUNTERBORE_DEPTH == 8.40
    assert nominal["nominal_head_recess"] == pytest.approx(0.5514)
    assert nominal["nominal_floor"] == pytest.approx(
        spec.HEIGHT - spec.HEIGHT_TOLERANCE - spec.COUNTERBORE_DEPTH
    )
    assert nominal["parallel_cut_floor"] >= 2.00
    # Reference depth remains representative geometry, not a manufactured band.
    for recess in (0.50, 0.60):
        fitted = spec.require_fitted_counterbore_geometry(
            counterbore_depth=hardware.SCREW_HEAD_HEIGHT + recess
        )
        assert fitted["nominal_head_recess"] == pytest.approx(recess)


@pytest.mark.parametrize("change", [
    {"counterbore_depth": 7.90}, {"counterbore_depth": 9.00},
    {"counterbore_depth": 0.0}, {"actual_floor_min": 1.99},
    {"height": spec.HEIGHT - 0.20},
])
def test_fitted_geometry_rejects_nominal_or_constructive_window_mutants(change) -> None:
    with pytest.raises(ValueError):
        spec.require_fitted_counterbore_geometry(**change)
    for guard in (spec.require_clearance_geometry, spec.require_register_geometry):
        with pytest.raises(ValueError):
            guard(**change)


@pytest.mark.parametrize("name", ("height", "counterbore_depth", "actual_floor_min"))
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_fitted_geometry_rejects_nonfinite_cut_and_floor_inputs(name, value) -> None:
    with pytest.raises(ValueError, match="finite"):
        spec.require_fitted_counterbore_geometry(**{name: value})


@pytest.mark.parametrize("margin,raw,guard", [
    ("counterbore_floor", spec.clearance_geometry, spec.require_clearance_geometry),
    ("register_to_head_void_floor", spec.register_clearance_geometry, spec.require_register_geometry),
])
def test_actual_floor_acceptance_does_not_mask_nominal_breakthrough(margin, raw, guard) -> None:
    assert raw(actual_floor_min=2.20)[margin] == pytest.approx(2.20)
    assert guard(actual_floor_min=2.20)[margin] == pytest.approx(2.20)
    assert raw(counterbore_depth=spec.HEIGHT)[margin] < 0.0
    with pytest.raises(ValueError):
        guard(counterbore_depth=spec.HEIGHT)


def test_fitted_head_capture_uses_the_captured_head_enclosure() -> None:
    bounds = retention.capture_bounds()
    assert spec.require_fitted_head_capture(bounds=bounds) == spec.FITTED_HEAD_RUNNING_CLEARANCE
    assert spec.FITTED_HEAD_RUNNING_CLEARANCE > 0.0
    for clearance in (0.0, -0.01, math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="fitted head"):
            spec.require_fitted_head_capture(bounds=replace(bounds, cap_head_running_clearance=clearance))


def test_pocket_depth_is_fitted_to_actual_flange_not_a_loose_fixed_band() -> None:
    assert spec.fitted_chamber_excess(3.25, 3.0) == pytest.approx(0.25)
    assert spec.fitted_chamber_excess(4.05, 3.8) == pytest.approx(0.25)
    for pocket, flange in ((3.1, 3.0), (3.5, 3.0), (3.3, 3.8)):
        with pytest.raises(ValueError, match="chamber excess"):
            spec.fitted_chamber_excess(pocket, flange)


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
        assert recess["depth_ref"] == 8.40
        assert "depth" not in recess and "depth" not in recess["requirements"]
        assert "depth" not in recess["precision"]
        assert recess["precision"]["depth_ref"] == spec.DRAWING_PRECISION_BY_NAME["CounterboreDepth"] == 2
        assert set(recess["requirements"]) == {"dia", "note"}
    channel_band = printed_band_mm(spec.CHANNEL_PLACES)
    channel = features["wire_channel"]
    assert set(channel["requirements"]) == {"width", "depth", "note"}
    assert "normal_installed_wire_recess_min" not in channel
    assert channel["width"] == pytest.approx([
        spec.CHANNEL_WIDTH - channel_band, spec.CHANNEL_WIDTH + channel_band,
    ])
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


def test_requirement_manifest_binds_integral_cylinders() -> None:
    manifest = export_features.requirement_manifest(STEM)
    features, selectors = manifest["features"], export_features.feature_selectors(STEM)
    assert manifest["construction"] == "one_piece"
    assert manifest["material"]["thickness"] == spec.TOTAL_HEIGHT
    assert manifest["volume_mm3"] == spec.VOLUME_MM3
    assert not any(name.startswith("register_end_chamfer_") for name in features)
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


def test_builder_machines_single_bolt_bores_and_full_depth_head_mouths(monkeypatch) -> None:
    class CutAdapter(_RegisterAdapter):
        def __init__(self):
            super().__init__()
            self.points["origin"] = (0.0, 0.0)
            self._sketch_entities = {}
            self.planes = {"Front": 0.0}
            self.profile = []
            self.z = 0.0
            self.cuts = []
            self.last_plane = None

        async def create_part(self):
            return SimpleNamespace(is_success=True, data=None, error=None)

        async def create_plane(self, params):
            self.last_plane = params.offset
            return SimpleNamespace(is_success=True, data=None, error=None)

        async def create_sketch(self, plane):
            self.z = self.planes[plane]
            self.profile = []
            return await super().create_sketch(plane)

        async def add_circle(self, x, y, radius):
            result = await super().add_circle(x, y, radius)
            circle = ("circle", x, y, radius)
            self.profile.append(circle)
            self._sketch_entities[result.data] = circle
            return result

        async def create_cut_extrude(self, params):
            low = self.z - (0.0 if params.reverse_direction else params.depth)
            high = self.z + (params.depth if params.reverse_direction or params.both_directions else 0.0)
            self.cuts.append((tuple(self.profile), low, high))
            return SimpleNamespace(is_success=True, data=None, error=None)

        def void_at(self, x, y, z):
            for profile, low, high in self.cuts:
                if not low < z < high:
                    continue
                for kind, *shape in profile:
                    if kind == "circle":
                        cx, cy, radius = shape
                        if math.hypot(x - cx, y - cy) < radius:
                            return True
                    else:
                        x0, y0, x1, y1 = shape
                        if x0 < x < x1 and y0 < y < y1:
                            return True
            return False

    adapter = CutAdapter()

    async def no_op(*_args, **_kwargs):
        pass

    async def stock_circle(current, diameter, prefix, dims):
        current.currentSketchManager.AddToDB = True
        try:
            circle = await current.add_circle(0.0, 0.0, diameter / 2.0)
        finally:
            current.currentSketchManager.AddToDB = False
        return circle.data

    async def rectangle(current, plane, _feature, bounds, _names, _drives):
        await current.create_sketch(plane)
        current.profile.append(("rectangle", *bounds))
        return []

    async def machining_complete(*_args):
        raise RuntimeError("machining complete")

    def feature_name(current, name):
        if current.last_plane is not None:
            current.planes[name] = current.last_plane
            current.last_plane = None

    monkeypatch.setattr(part, "set_global", no_op)
    monkeypatch.setattr(part, "define_centered_rectangle", no_op)
    monkeypatch.setattr(part, "ensure_fully_defined", no_op)
    monkeypatch.setattr(part, "volume_check", no_op)
    monkeypatch.setattr(part, "_circle_from_stock_corner", stock_circle)
    monkeypatch.setattr(part, "_rectangle", rectangle)
    monkeypatch.setattr(part, "_integral_registers", machining_complete)
    monkeypatch.setattr(part, "name_last_feature", feature_name)
    monkeypatch.setattr(part, "name_dimensions", lambda _adapter, _feature, names: names)
    monkeypatch.setattr(part.SketchDims, "apply", lambda *_args: [])
    with pytest.raises(RuntimeError, match="machining complete"):
        asyncio.run(part.build(adapter))

    floor = spec.HEIGHT - spec.COUNTERBORE_DEPTH
    for x, y in spec.BOLT_POINTS:
        cylinders = [
            (radius, low, high)
            for profile, low, high in adapter.cuts
            for kind, *shape in profile if kind == "circle"
            for cx, cy, radius in (shape,) if (cx, cy) == (x, y)
        ]
        assert len(cylinders) == 2
        through, head = sorted(cylinders)
        assert through[0] == spec.HOLE_DIA / 2.0
        assert through[1] < 0.0 and through[2] >= spec.HEIGHT
        assert head == (spec.COUNTERBORE_DIA / 2.0, floor, spec.HEIGHT)
        for z, angle in product((0.01, floor / 2.0, floor - 0.01), range(8)):
            ux, uy = math.cos(angle * math.pi / 4.0), math.sin(angle * math.pi / 4.0)
            for radius, is_void in ((through[0] - 0.01, True), (through[0] + 0.01, False)):
                assert adapter.void_at(x + radius * ux, y + radius * uy, z) is is_void
        # The opening beside each head is the complete recess width and depth,
        # not the shallower wire channel or an annular fillet shelf.
        outer_x = math.copysign(spec.WIDTH / 2.0 - 0.01, x)
        radius = spec.COUNTERBORE_DIA / 2.0
        for dy in (-radius + 0.01, -radius / 2.0, 0.0, radius / 2.0, radius - 0.01):
            # These edge points are OUTSIDE the circular CB. A closed recess
            # or an annular/sliver X wall cannot satisfy this actual section.
            assert math.hypot(outer_x - x, dy) > radius
            for fraction in (0.05, 0.50, 0.95, 1.0):
                section_x = x + fraction * (outer_x - x)
                for z in (floor + 0.01, (floor + spec.HEIGHT) / 2.0, spec.HEIGHT - 0.01):
                    assert adapter.void_at(section_x, y + dy, z)
                if math.hypot(section_x - x, dy) > spec.HOLE_DIA / 2.0:
                    assert not adapter.void_at(section_x, y + dy, floor - 0.01)
        # The surviving sides, unlike the open X edge, remain actual walls.
        for side in (-1.0, 1.0):
            side_y = y + side * (radius + 0.01)
            for fraction, z in product(
                (0.05, 0.50, 1.0), (floor + 0.01, spec.HEIGHT - 0.01),
            ):
                section_x = x + fraction * (outer_x - x)
                assert not adapter.void_at(section_x, side_y, z)


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
    maps = (
        drawing.TOP_KEEP, drawing.BOTTOM_KEEP, drawing.RIGHT_KEEP,
        drawing.SECTION_KEEP, drawing.BOLT_KEEP,
        drawing.REGISTER_KEEP, drawing.REGISTER_PROJECTION_KEEP,
    )
    for keep in maps:
        for x, y in keep.values():
            assert left + 0.004 < x < right - 0.004
            assert bottom + 0.004 < y < top - 0.004
            assert x < title_left or y > title_top + 0.004
    top_right = drawing.TOP_CENTER[0] + spec.WIDTH / 2000.0
    top_bottom = drawing.TOP_CENTER[1] - spec.LENGTH / 2000.0
    top_left = drawing.TOP_CENTER[0] - spec.WIDTH / 2000.0
    assert drawing.TOP_KEEP["CapLength"][0] + 0.006 < drawing.TOP_KEEP["ApertureCenterY"][0] < top_left - 0.006
    assert drawing.TOP_KEEP["WireWidth"][0] > top_right + 0.006
    assert drawing.TOP_KEEP["CapWidth"][1] + 0.006 < drawing.TOP_KEEP["ApertureCenterX"][1] < top_bottom - 0.006
    underside_left = drawing.BOTTOM_CENTER[0] - spec.WIDTH / 2000.0
    assert drawing.BOTTOM_KEEP["PocketCenterY"][0] < underside_left - 0.006
    assert drawing.RIGHT_CENTER[1] == drawing.TOP_CENTER[1]
    # The remaining YZ projection stays aligned to its front context.
    assert drawing.REGISTER_RIGHT_CENTER[1] == drawing.REGISTER_FRONT_CENTER[1]


def _cap_paper_box(box_mm, old_anchor_mm, new_anchor):
    """Translate measured pre-fix ink; this is not a native post-fix replay."""
    dx = new_anchor[0] * 1000.0 - old_anchor_mm[0]
    dy = new_anchor[1] * 1000.0 - old_anchor_mm[1]
    return (box_mm[0] + dx, box_mm[1] + dy, box_mm[2] + dx, box_mm[3] + dy)


def test_cap_isometric_and_caption_clear_the_measured_native_border_and_each_other() -> None:
    # Actual 20261021T192326153Z native outline and caption extent, in mm.
    # These translations allocate space; parent native export proves the ink.
    pictorial = _cap_paper_box(
        (52.2796, 5.524, 107.7204, 112.476), (80.0, 59.0), drawing.ISO_CENTER,
    )
    caption = _cap_paper_box(
        (24.796, 105.8636, 84.3671, 110.1527), (25.0, 110.0), drawing.ISO_NOTE_XY,
    )
    for box in (pictorial, caption):
        assert box[0] > 12.7 + 5.0
        assert box[1] > 12.7 + 5.0
        assert box[2] < 419.1 - 5.0
        assert box[3] < 266.7 - 5.0
    assert caption[1] - pictorial[3] > 5.0


def test_cap_head_acceptance_lane_clears_the_overall_and_native_depth_witnesses() -> None:
    # Reserve the whole folded block, not a translation of its obsolete text.
    x, y = (value * 1000.0 for value in drawing.RIGHT_KEEP["CounterboreDepth"])
    left, bottom, right, top = x - 40.0, y - 27.5, x + 40.0, y + 25.0
    overall_extension_end = max(
        drawing.TOP_CENTER[0] * 1000.0 - spec.WIDTH / 2.0 + 1.0,
        drawing.TOP_KEEP["CapLength"][0] * 1000.0 + 1.0,
    )
    assert left - overall_extension_end > 5.0
    assert 328.7 - right > 3.0  # actual native depth witness, not view padding
    assert left > 210.588 + 5.0  # actual access-view padded right edge
    assert bottom > 190.0 + 5.0
    assert top < 266.7 - 5.0
    # 7f's unchanged six-row Ø21 block moves as a whole into the right lane.
    # These measured text bounds allocate room, not a simulated COM landing.
    counterbore = _cap_paper_box(
        (22.2174, 158.3045, 107.7827, 189.6392),
        (65.0, 175.0), drawing.TOP_KEEP["CounterboreDia"],
    )
    assert counterbore[0] > 210.588 + 5.0  # padded access-view right edge
    assert 323.112 - counterbore[2] > 3.0  # padded depth-view left edge
    assert 199.9969 - counterbore[3] > 5.0  # native fitted-head block
    assert counterbore[0] - drawing.TOP_KEEP["WireWidth"][0] * 1000.0 > 5.0


def test_cap_upper_register_x_block_clears_both_native_extension_lines() -> None:
    block = _cap_paper_box(
        (277.9, 231.6, 342.1, 246.4), (310.0, 240.0), drawing.REGISTER_TEXT_POSITIONS["Register2X"],
    )
    assert block[0] - max(317.5, 320.0) > 5.0
    assert block[2] < 419.1 - 5.0
    assert block[3] < 255.05 - 5.0  # heading's lower ink edge


def test_cap_full_bolt_callouts_fit_paper_and_have_separate_rows() -> None:
    # Actual 20261021T085834832Z PDF/audit, sheet 3, mm from bottom-left.
    # The old anchors were on paper while both complete left Y blocks were not.
    left_lower = _cap_paper_box(
        (-0.9, 127.6, 60.3, 143.9), (60.0, 135.0), drawing.BOLT_KEEP["Bolt3Y"],
    )
    left_upper = _cap_paper_box(
        (-0.9, 237.6, 60.3, 253.9), (60.0, 245.0), drawing.BOLT_KEEP["Bolt4Y"],
    )
    for box in (left_lower, left_upper):
        assert box[0] > 12.7 + 5.0
        assert box[2] < 419.1 - 5.0
        assert box[3] < 255.05 - 5.0  # PDF heading's lower ink edge
    right_x = _cap_paper_box(
        (293.6, 112.6, 307.0, 128.74), (300.0, 120.0), drawing.BOLT_KEEP["Bolt1X"],
    )
    right_y = _cap_paper_box(
        (285.4, 127.6, 345.7, 143.9), (285.0, 135.0), drawing.BOLT_KEEP["Bolt1Y"],
    )
    assert right_y[1] - right_x[3] > 5.0
    # f0c's actual sheet 3 exposed a different collision: the X100 Y-line
    # crosses Bolt4X's last row [98.0,212.8]..[142.1,216.7] mm.
    upper_x_row = _cap_paper_box(
        (98.0, 212.8, 142.1, 216.7), (120.0, 215.0), drawing.BOLT_KEEP["Bolt4X"],
    )
    assert upper_x_row[0] - drawing.BOLT_KEEP["Bolt4Y"][0] * 1000.0 > 5.0


def test_cap_section_and_register_complete_blocks_clear_context_and_heading() -> None:
    # Native findings measured the entire multiline callout, not just the value.
    chamber = _cap_paper_box(
        (22.27, 231.72, 97.73, 258.0), (60.0, 245.0), drawing.BOTTOM_KEEP["PocketDia"],
    )
    assert 255.05 - chamber[3] > 5.0
    assert chamber[1] - (drawing.BOTTOM_CENTER[1] * 1000.0 + spec.LENGTH / 2.0) > 5.0
    # Do not translate PocketDepth's old text box: f0c proved the shoulder
    # flips from left to right when its anchor crosses the feature attachment.
    # This is a lane/route contract, not post-position native extent evidence.
    depth_x, depth_y = (value * 1000.0 for value in drawing.SECTION_KEEP["PocketDepth"])
    assert depth_x < 319.3 - 20.0  # actual native thickness attachment
    assert depth_x > 124.0215 + 12.7 + 5.0  # space for the full left shoulder
    assert depth_x < 269.5009 - 5.0  # actual finish-symbol leftmost stroke
    padded_underside_top = drawing.BOTTOM_CENTER[1] * 1000.0 + spec.LENGTH / 2.0 + 4.088
    assert depth_y - 17.09 > padded_underside_top + 5.0
    assert depth_y + 15.7 < 266.7 - 5.0
    register = _cap_paper_box(
        (153.0, 207.6, 213.1, 223.74), (215.0, 215.0), drawing.REGISTER_KEEP["Register2Y"],
    )
    assert register[1] > drawing.REGISTER_RIGHT_CENTER[1] * 1000.0 + spec.LENGTH / 2.0 + 5.0


@pytest.mark.parametrize(("keep", "name", "old", "row", "witness_x", "side"), [
    ("RIGHT_KEEP", "WireDepth", (370.0, 145.0), (342.4424, 131.1094, 397.5576, 134.6094), 335.25, "right"),
    ("REGISTER_PROJECTION_KEEP", "RegisterProjection", (175.0, 110.0), (138.1, 107.8, 211.7, 111.7), 210.25, "left"),
    ("REGISTER_KEEP", "RegisterDia", (295.0, 115.0), (248.2, 108.3, 341.7, 112.2), 320.0, "left"),
])
def test_cap_full_callout_rows_clear_native_vertical_witnesses(keep, name, old, row, witness_x, side) -> None:
    moved = _cap_paper_box(row, old, getattr(drawing, keep)[name])
    if side == "right":
        assert moved[0] - witness_x > 3.0
    else:
        assert witness_x - moved[2] > 3.0


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



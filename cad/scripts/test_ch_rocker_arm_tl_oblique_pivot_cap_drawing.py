"""Offline definition/native-recipe contracts for MHA-CH-06-TL-30.

No SolidWorks connection or recipe execution. Native readback and sheet review
remain the integration owner's separate acceptance gates.
"""

from __future__ import annotations

import ast
import copy
import inspect
from pathlib import Path

import pytest

import _config
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


def test_dimensions_and_frame_have_one_shared_owner() -> None:
    assert (spec.WIDTH, spec.LENGTH, spec.HEIGHT) == (50.0, 70.0, 10.5)
    assert (spec.POCKET_DIA, spec.POCKET_DEPTH, spec.APERTURE_DIA) == (36.6, 3.3, 15.0)
    assert spec.BOLT_POINTS == retention.CAP_BOLT_CENTERS
    assert set(spec.BOLT_POINTS) == {(-15.0, -25.0), (-15.0, 25.0), (15.0, -25.0), (15.0, 25.0)}
    assert spec.BOTTOM_PLANE == "Front Plane"
    assert spec.AXIS_NAME == "CaptureAxis"
    assert spec.BOLT_AXES == tuple(f"CapBoltAxis{i}" for i in range(1, 5))
    assert spec.HEIGHT_PLACES == 2
    assert spec.POSITION_PLACES == spec.COUNTERBORE_DEPTH_PLACES == 3
    assert spec.CHANNEL_PLACES == 2
    assert spec.COUNTERBORE_DIA == retention.CAP_COUNTERBORE_DIAMETER == 14.30
    assert spec.COUNTERBORE_DIAMETER_PLACES == retention.CAP_COUNTERBORE_DIAMETER_PLACES == 2
    assert spec.DRAWING_PRECISION_BY_NAME["CounterboreDia"] == 2
    assert spec.CHANNEL_DEPTH == retention.CAP_WIRE_CHANNEL_DEPTH == 5.50
    assert spec.HEIGHT + spec.HEIGHT_TOLERANCE < spec.STOCK_THICKNESS


def test_all_real_material_margins_survive_the_printed_limits() -> None:
    margins = spec.require_clearance_geometry()
    assert margins == spec.GEOMETRY_MARGINS
    assert set(margins) == {"counterbore_floor", "channel_floor", "chamber_roof", "counterbore_to_chamber", "hole_to_chamber", "mouth_to_chamber", "channel_to_chamber", "counterbore_to_y_edge", "pocket_to_x_edge"}
    assert min(margins.values()) >= 2.0
    assert margins["counterbore_floor"] == pytest.approx(2.36)
    assert margins["chamber_roof"] == pytest.approx(5.89)
    assert margins["channel_floor"] == pytest.approx(3.98)
    assert margins["channel_to_chamber"] == pytest.approx(5.015)
    assert margins["counterbore_to_y_edge"] == pytest.approx(2.065)
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
    ({"channel_width": 8.6}, "channel_to_chamber"),
    ({"channel_depth": 7.5}, "channel_floor"),
    ({"counterbore_dia": 14.5}, "counterbore_to_y_edge"),
])
def test_approved_void_enlargement_keeps_real_land_floor_and_outer_wall(change, margin) -> None:
    assert spec.clearance_geometry(**change)[margin] < 2.0
    with pytest.raises(ValueError, match=margin):
        spec.require_clearance_geometry(**change)


def test_sourced_thread_not_smooth_body_sets_the_bolt_stop() -> None:
    assert spec.SCREW_MAJOR_LIMITS == (hardware.SCREW_MAJOR_DIA_MIN, hardware.SCREW_MAJOR_DIA_MAX)
    assert spec.SCREW_MAJOR_LIMITS == pytest.approx((6.14426, 6.35))
    assert spec.SCREW_THREAD_SOURCE_URL == hardware.SCREW_THREAD_SOURCE_URL
    assert "unified-external-screw-threads" in spec.SCREW_THREAD_SOURCE_URL
    assert spec.HOLE_DIA == 6.8 > spec.SCREW_MAJOR_LIMITS[1]
    assert spec.DRILLED_BAND == (0.1, 0.0)


def test_single_wire_and_twists_have_separate_recesses() -> None:
    minimum_cb_depth = spec.COUNTERBORE_DEPTH - spec.COUNTERBORE_DEPTH_TOLERANCE
    assert minimum_cb_depth - spec.HEAD_HEIGHT_MAX > spec.WIRE_DIAMETER
    minimum_cb_dia = spec.COUNTERBORE_DIA - printed_band_mm(spec.COUNTERBORE_DIAMETER_PLACES)
    assert (minimum_cb_dia - spec.HEAD_DIAMETER_MAX) / 2.0 > spec.WIRE_DIAMETER
    minimum_channel = spec.CHANNEL_WIDTH - printed_band_mm(spec.CHANNEL_PLACES)
    assert minimum_channel > 2.0 * spec.WIRE_DIAMETER
    # A doubled twist is not silently placed in the single-wire roof gap.
    assert minimum_cb_depth - spec.HEAD_HEIGHT_MAX < 2.0 * spec.WIRE_DIAMETER
    assert spec.CHANNEL_DEPTH - printed_band_mm(spec.CHANNEL_PLACES) > 2.0 * spec.WIRE_DIAMETER


def test_pocket_depth_is_fitted_to_actual_flange_not_a_loose_fixed_band() -> None:
    assert spec.fitted_chamber_excess(3.25, 3.0) == pytest.approx(0.25)
    assert spec.fitted_chamber_excess(4.05, 3.8) == pytest.approx(0.25)
    for pocket, flange in ((3.1, 3.0), (3.5, 3.0), (3.3, 3.8)):
        with pytest.raises(ValueError, match="chamber excess"):
            spec.fitted_chamber_excess(pocket, flange)
    callout = spec.DIMENSION_CALLOUTS["PocketDepth"]
    assert "REF" in callout and "0.20-0.30" in callout
    assert "LOCAL FACE VARIATION" in callout and "SCREWS FULLY SEATED" in callout
    assert "NO BEARING PRELOAD" in callout


def test_each_model_dimension_is_printed_once_with_authored_precision() -> None:
    keep_maps = (drawing.TOP_KEEP, drawing.BOTTOM_KEEP, drawing.RIGHT_KEEP, drawing.SECTION_KEEP)
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert sum(map(len, keep_maps)) == len(marked)
    assert set().union(*keep_maps) == marked == set(spec.DRAWING_PRECISION_BY_NAME)
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert all(spec.DRAWING_PRECISION_BY_NAME[f"Bolt{i}{axis}"] == 3 for i in range(1, 5) for axis in ("X", "Y"))
    bolt_stations = {f"Bolt{i}{axis}" for i in range(1, 5) for axis in ("X", "Y")}
    assert bolt_stations <= drawing.BOTTOM_KEEP.keys()
    assert not bolt_stations & drawing.TOP_KEEP.keys()
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert spec.DRAWING_NOTES == ""


def test_one_axis_control_owns_aperture_coaxiality_to_actual_pocket() -> None:
    assert len(spec.PART_DATUMS) == len(spec.GEOMETRIC_CONTROLS) == 1
    assert spec.PART_DATUMS[0].face.diameter_mm == spec.POCKET_DIA
    control = spec.GEOMETRIC_CONTROLS[0]
    assert control.key == "aperture_position"
    assert float(control.tolerance) == retention.CAP_APERTURE_POSITION_DIAMETER == 0.02
    assert control.datums == ("A",)


def test_requirement_manifest_keeps_actual_bolt_coordinates_and_fitted_acceptance() -> None:
    features = export_features.requirement_manifest(STEM)["features"]
    assert {f"cap_bolt_{i}" for i in range(1, 5)} <= features.keys()
    assert features["journal_aperture"]["dia"] == pytest.approx([15.0, 15.1])
    for index, (x, y) in enumerate(spec.BOLT_POINTS, 1):
        feature = features[f"cap_bolt_{index}"]
        assert feature["dia"] == pytest.approx([6.8, 6.9])
        assert feature["x_nominal"] == x and feature["y_nominal"] == y
        assert feature["x"] == pytest.approx([x - 0.13, x + 0.13])
        assert feature["y"] == pytest.approx([y - 0.13, y + 0.13])
    assert features["flange_chamber"]["note"] == spec.DIMENSION_CALLOUTS["PocketDepth"]


def test_native_recipe_contains_real_cuts_and_every_call_binds() -> None:
    tree = ast.parse(RECIPE.read_text(encoding="utf-8"), filename=str(RECIPE))
    calls = _adapter_calls(tree)
    methods = {call.func.attr for call in calls}
    assert {"create_part", "create_sketch", "create_extrusion", "create_cut_extrude", "create_plane"} <= methods
    assert not _missing(tree)
    for call in calls:
        _, method = _adapter_methods()[call.func.attr]
        _signature(method).bind(call.func.value, *call.args, **{kw.arg: kw.value for kw in call.keywords})
    mutant = copy.deepcopy(tree)
    extrusion = next(call for call in _adapter_calls(mutant) if call.func.attr == "create_extrusion")
    extrusion.func.attr = "create_extrude"
    assert _missing(mutant) == {"create_extrude"}
    source = RECIPE.read_text(encoding="utf-8")
    assert "reverse_direction=reverse" in source
    assert '"HeadAccess{index}"' in source and '"WireChannels{index}"' in source
    assert "spec.VOLUME_MM3" in source and "GetBodies2" in source
    assert "datums=spec.PART_DATUMS" in source and "controls=spec.GEOMETRIC_CONTROLS" in source
    assert "create_section_view" in inspect.getsource(drawing)
    assert "set_hidden_lines_visible" not in inspect.getsource(drawing)


def test_configuration_identity_and_accepted_control() -> None:
    row = _config.parts(DASHED)
    assert row["number"] == "MHA-CH-06-TL-30" and row["quantity"] == 2
    assert "1/2" in row["material_specification"]
    assert len(row["finish"]) <= 40 and "\n" not in row["finish"]
    assert any(item["kind"] == "accept" for item in row["machinist_exceptions"])

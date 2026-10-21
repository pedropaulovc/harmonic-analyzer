"""Offline intact-rigid capture contracts, not a force or machine-clearance certificate.

Only pure dimensional specifications are imported. Native recipes/COM are not.
Actual spindle, holder, cutter, wire workmanship and manufactured fitted gaps still
need the installed-machine acceptance; a nominal Z stack is not that evidence.
"""

from __future__ import annotations

import math
from itertools import product

import pytest

from _printed_tolerance import printed_band_mm
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
import ch_rocker_arm_tl_oblique_pivot_block_spec as block
import ch_rocker_arm_tl_oblique_pivot_cap_spec as cap
import ch_rocker_arm_tl_oblique_pivot_pin_spec as pin
import ch_rocker_arm_tl_oblique_pivot_retainer_spec as retainer
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import ch_rocker_arm_tl_oblique_retention_spec as retention
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_oblique_tooling_clearance_spec as tooling


PASSES = (("inner", trammel.A1, trammel.B1), ("outer", trammel.A2, trammel.B2))
CONTACT_MARGINS = (
    "flange_contact_margin", "floor_inner_margin", "floor_counterbore_margin",
    "cap_pocket_margin", "cap_aperture_margin", "pin_aperture_clearance",
    "cap_running_clearance",
)


def test_capture_uses_actual_component_patterns_and_unchanged_functional_fits() -> None:
    receiver = tuple((x - block.BORE_X, y) for x, y in block.CAP_TAP_POINTS)
    assert receiver == cap.BOLT_POINTS == retention.CAP_BOLT_CENTERS
    actual = retention.capture_bounds(
        receiver_pattern=receiver,
        cap_pattern=cap.BOLT_POINTS,
        receiver_location_band=printed_band_mm(block.CAP_TAP_LOCATION_PLACES),
        cap_location_band=printed_band_mm(cap.POSITION_PLACES),
        cap_hole_diameter_max=cap.HOLE_DIA + cap.DRILLED_BAND[0],
        bearing_bore_diameter_max=block.BORE_DIA_MAX,
        carriage_counterbore_diameter_max=block.CBORE_DIA + printed_band_mm(2),
        carrier_clearance=carrier.PIN_CLEARANCE_MAX,
    )
    expected = retention.capture_bounds()
    for field in expected.__dataclass_fields__:
        assert getattr(actual, field) == pytest.approx(getattr(expected, field))
    assert carrier.PIN_HOLE_DIA == pin.FIT_DIA == 10.0
    assert carrier.PIN_HOLE_BAND == pin.PIN_HOLE_BAND == (0.015, 0.0)  # H7
    assert carrier.PIN_MATE_BAND == pin.CARRIER_BAND == (0.0, -0.009)  # h6
    assert carrier.PIN_CLEARANCE_MAX == pytest.approx(retention.CARRIER_DIAMETRAL_CLEARANCE_MAX)
    # The lower lead and ordinary top edge are not credited as engagement.
    engagement = (
        carrier.THICKNESS - carrier.THICKNESS_BAND
        - carrier.PIN_CHAMFER - carrier.PIN_CHAMFER_BAND[0] - retainer.EDGE_BREAK_MAX
    )
    assert retention.CARRIER_ENGAGEMENT_MIN <= engagement + 1e-12
    assert engagement > 0.0


def test_bolt_hole_and_thread_stops_bound_translation_without_clamp_friction() -> None:
    bounds = retention.capture_bounds()
    thread_float = (
        retention.CAP_TAP_THREAD_PITCH_DIAMETER_MAX
        - retention.CAP_BOLT_THREAD_PITCH_DIAMETER_MIN
    ) / 2.0
    hole_float = (
        cap.HOLE_DIA + cap.DRILLED_BAND[0] - hardware.SCREW_MAJOR_DIA_MIN
    ) / 2.0
    receiver_band = printed_band_mm(block.CAP_TAP_LOCATION_PLACES)
    cap_band = printed_band_mm(cap.POSITION_PLACES)
    assert thread_float > 0.0 and hole_float > 0.0
    assert retention.CAP_BOLT_THREAD_MAJOR_MIN == hardware.SCREW_MAJOR_DIA_MIN
    assert bounds.cap_lateral_shift == pytest.approx(
        math.hypot(receiver_band + cap_band + thread_float + hole_float,
                   receiver_band + cap_band + thread_float + hole_float)
    )
    # Removing either float gives a genuinely smaller, nonconservative answer.
    assert bounds.cap_lateral_shift > math.sqrt(2.0) * (receiver_band + cap_band + hole_float)
    assert bounds.cap_lateral_shift > math.sqrt(2.0) * (receiver_band + cap_band + thread_float)
    minimum_floor = (
        cap.HEIGHT - printed_band_mm(cap.HEIGHT_PLACES)
        - cap.COUNTERBORE_DEPTH - printed_band_mm(cap.COUNTERBORE_DEPTH_PLACES)
    )
    assert minimum_floor > retention.CAP_BOLT_PITCH  # a whole crest, not nominal shank OD
    under_head_max = (
        cap.HEIGHT + printed_band_mm(cap.HEIGHT_PLACES)
        - cap.COUNTERBORE_DEPTH + printed_band_mm(cap.COUNTERBORE_DEPTH_PLACES)
    )
    full_engagement = hardware.SCREW_LENGTH_MIN - under_head_max - retention.CAP_BOLT_PITCH
    assert bounds.screw_engagement == pytest.approx(full_engagement)
    assert full_engagement >= 1.5 * hardware.SCREW_MAJOR_DIA_MAX


def test_fixed_stop_circle_has_both_flange_faces_and_unbroken_block_floor() -> None:
    bounds = retention.capture_bounds()
    theta = math.atan(retention.CAP_CHAMBER_EXCESS[1] / retention.STOP_CONTACT_DIAMETER)
    assert bounds.flange_tilt == pytest.approx(theta)
    radius_min = (pin.FLANGE_DIA + pin.FLANGE_DIA_BAND[1]) / 2.0
    thick_max = pin.FLANGE_THICK + printed_band_mm(retention.PIN_FLANGE_THICK_PLACES)
    flange_float = (
        (cap.POCKET_DIA + cap.POCKET_BAND[0]) / 2.0
        - radius_min * math.cos(theta) + thick_max / 2.0 * math.sin(theta)
    )
    assert bounds.flange_lateral_shift == pytest.approx(flange_float)
    projected_face_radius = (
        (radius_min - pin.FLANGE_EDGE_BREAK_MAX) * math.cos(theta)
        - thick_max / 2.0 * math.sin(theta)
    )
    stop_radius = retention.STOP_CONTACT_DIAMETER / 2.0
    assert bounds.flange_contact_margin == pytest.approx(
        projected_face_radius - bounds.cap_lateral_shift - flange_float - stop_radius
    )
    assert bounds.floor_inner_margin == pytest.approx(
        stop_radius - block.BORE_DIA_MAX / 2.0 - retention.BLOCK_STOP_EDGE_BREAK_MAX
    )
    station_band = printed_band_mm(2) + printed_band_mm(3)
    nearest_carriage = min(
        math.hypot(abs(x - block.BORE_X) - station_band, abs(y) - station_band)
        for x, y in block.BOLT_POINTS
    )
    assert bounds.floor_counterbore_margin == pytest.approx(
        nearest_carriage - (block.CBORE_DIA + printed_band_mm(2)) / 2.0 - stop_radius
    )
    assert bounds.cap_pocket_margin == pytest.approx(
        (cap.POCKET_DIA + cap.POCKET_BAND[1]) / 2.0 - bounds.cap_lateral_shift - stop_radius
    )
    center_band = printed_band_mm(cap.CENTER_LOCATION_PLACES)
    center_offset = max(
        math.hypot(ax - px, ay - py)
        for ax, ay, px, py in product((-center_band, center_band), repeat=4)
    )
    assert bounds.cap_aperture_margin == pytest.approx(
        stop_radius - bounds.cap_lateral_shift - center_offset
        - (cap.APERTURE_DIA + retention.CAP_APERTURE_BAND[0]) / 2.0
    )
    assert all(getattr(bounds, field) > 0.0 for field in CONTACT_MARGINS)
    # The connected operating branch is limited by opposing faces, not fit friction.
    assert retention.STOP_CONTACT_DIAMETER * math.tan(theta) == pytest.approx(
        retention.CAP_CHAMBER_EXCESS[1]
    )


def test_pin_aperture_and_cap_remain_clear_at_full_pitch_without_a_skid() -> None:
    bounds = retention.capture_bounds()
    pin_tilt = bounds.flange_tilt + math.atan(
        retention.PIN_FLANGE_PERPENDICULARITY / retention.PIN_FLANGE_SQUARENESS_SPAN
    )
    expected_tilt = (
        pin_tilt
        + math.atan(retention.CARRIER_HOLE_PERPENDICULARITY / retention.CARRIER_ENGAGEMENT_MIN)
        + math.atan(carrier.PIN_CLEARANCE_MAX / retention.CARRIER_ENGAGEMENT_MIN)
    )
    assert bounds.carrier_tilt == pytest.approx(expected_tilt)
    boss_radius = (pin.COLLAR_DIA + printed_band_mm(pin.COLLAR_PLACES)) / 2.0
    cap_height_max = cap.HEIGHT + printed_band_mm(cap.HEIGHT_PLACES)
    center_offset = 2.0 * math.sqrt(2.0) * printed_band_mm(cap.CENTER_LOCATION_PLACES)
    assert bounds.pin_aperture_clearance == pytest.approx(
        cap.APERTURE_DIA / 2.0 - boss_radius / math.cos(pin_tilt)
        - bounds.flange_lateral_shift - cap_height_max * math.tan(pin_tilt)
        - center_offset
    )
    seat_min = (
        pin.FLANGE_THICK - printed_band_mm(retention.PIN_FLANGE_THICK_PLACES)
        + pin.UPPER_BOSS_HEIGHT - printed_band_mm(retention.PIN_UPPER_BOSS_PLACES)
    )
    outline_band = printed_band_mm(cap.OUTLINE_PLACES)
    center_band = printed_band_mm(cap.CENTER_LOCATION_PLACES)
    farthest_corner = max(
        math.hypot(cx - px, cy - py)
        for width, length, px, py in product(
            (cap.WIDTH - outline_band, cap.WIDTH + outline_band),
            (cap.LENGTH - outline_band, cap.LENGTH + outline_band),
            (cap.WIDTH / 2.0 - center_band, cap.WIDTH / 2.0 + center_band),
            (cap.LENGTH / 2.0 - center_band, cap.LENGTH / 2.0 + center_band),
        )
        for cx, cy in product((0.0, width), (0.0, length))
    ) + bounds.flange_lateral_shift
    assert bounds.cap_running_clearance == pytest.approx(
        seat_min - cap_height_max - farthest_corner * math.tan(expected_tilt)
    )
    assert bounds.pin_aperture_clearance > 0.0
    assert bounds.cap_running_clearance > 0.0


@pytest.mark.parametrize("pass_name,a,b", PASSES)
def test_lift_bounds_cover_interior_supports_and_extremal_end_width_pitch_points(
    pass_name: str, a: tuple[float, float], b: tuple[float, float],
) -> None:
    bounds = retention.capture_bounds()
    span = b[0] - a[0]
    angular_slope = math.tan(bounds.carrier_tilt)
    end_slope = min(angular_slope, (bounds.support_lift + bounds.support_drop) / span)
    # Include both actual support stations, midspan, both plate ends, both
    # width extremes, and the support line (A2/B2 is NOT Y=0).
    for x, y in product(
        (carrier.OUTLINE_X[0], a[0], (a[0] + b[0]) / 2.0, b[0], carrier.OUTLINE_X[1]),
        (carrier.OUTLINE_Y[0], a[1], carrier.OUTLINE_Y[1]),
    ):
        outboard = max(a[0] - x, x - b[0], 0.0)
        expected = bounds.support_lift + outboard * end_slope + abs(y - a[1]) * angular_slope
        actual = retention.point_lift_bound((x, y), pass_name, bounds)
        assert actual == pytest.approx(expected)
        # Feasible endpoint-height vertices plus either full width-pitch sign.
        # This independently checks interpolation and extrapolation direction.
        heights = (-bounds.support_drop, bounds.support_lift)
        for za, zb in product(heights, repeat=2):
            if abs(zb - za) / span > angular_slope:
                continue
            z_line = za + (x - a[0]) / span * (zb - za)
            for sign in (-1.0, 1.0):
                assert z_line + sign * (y - a[1]) * angular_slope <= actual + 1e-12
    for support in (a, b):
        assert retention.point_lift_bound(support, pass_name, bounds) == pytest.approx(bounds.support_lift)
    # Two support heights do not restrict pitch about their connecting line.
    far_y = max(carrier.OUTLINE_Y, key=lambda y: abs(y - a[1]))
    width_rise = retention.point_lift_bound((0.0, far_y), pass_name, bounds) - bounds.support_lift
    assert width_rise == pytest.approx(abs(far_y - a[1]) * angular_slope)
    assert width_rise > abs(far_y - a[1]) * (bounds.support_lift + bounds.support_drop) / span


def test_top_washer_is_fitted_to_upper_edge_loaded_gap_not_nominal_hole_center() -> None:
    gap = retainer.require_loaded_running_gap(retainer.THICKNESS)
    assert gap == pytest.approx(sum(retention.TOP_RUNNING_GAP) / 2.0)
    assert retainer.CLEVIS_DIA == hardware.CLEVIS_DIA
    assert gap == pytest.approx(
        pin.CROSS_HOLE_FROM_SEAT + pin.CROSS_HOLE_DIA / 2.0
        - hardware.CLEVIS_DIA - carrier.THICKNESS - retainer.THICKNESS
    )
    center_loaded = (
        pin.CROSS_HOLE_FROM_SEAT - hardware.CLEVIS_DIA / 2.0
        - carrier.THICKNESS - retainer.THICKNESS
    )
    assert gap - center_loaded == pytest.approx((pin.CROSS_HOLE_DIA - hardware.CLEVIS_DIA) / 2.0)
    assert 0.0 < retainer.THICKNESS < retainer.SUPPLY_MIN_THICKNESS < retainer.STOCK_THICKNESS
    assert retainer.OUTER_DIA > retainer.BORE_DIA > pin.FIT_DIA
    assert retention.capture_bounds().support_lift == pytest.approx(
        retention.CAP_CHAMBER_EXCESS[1] + retention.TOP_RUNNING_GAP[1]
    )


@pytest.mark.parametrize("gap", retention.TOP_RUNNING_GAP)
@pytest.mark.parametrize("clevis_dia", (hardware.CLEVIS_DIA_MIN, hardware.CLEVIS_DIA_MAX))
@pytest.mark.parametrize("hole_dia", (pin.CROSS_HOLE_DIA, pin.CROSS_HOLE_DIA + pin.CROSS_HOLE_BAND[0]))
def test_washer_is_fitted_to_actual_hardware_and_accepts_both_gap_limits(
    gap: float, clevis_dia: float, hole_dia: float,
) -> None:
    finished = (
        pin.CROSS_HOLE_FROM_SEAT + hole_dia / 2.0
        - clevis_dia - carrier.THICKNESS - gap
    )
    assert 0.0 < finished < retainer.SUPPLY_MIN_THICKNESS
    assert retainer.require_loaded_running_gap(
        finished, clevis_dia=clevis_dia, cross_hole_dia=hole_dia,
        carrier_thickness=carrier.THICKNESS,
    ) == pytest.approx(gap)


@pytest.mark.parametrize("thickness", (0.0, retainer.SUPPLY_MIN_THICKNESS))
def test_missing_or_unfaced_supply_washer_is_rejected(thickness: float) -> None:
    with pytest.raises(ValueError, match="loaded running gap"):
        retainer.require_loaded_running_gap(thickness)


@pytest.mark.parametrize("gap", (retention.TOP_RUNNING_GAP[0] - 0.01, retention.TOP_RUNNING_GAP[1] + 0.01))
def test_loaded_gap_rejects_both_preload_side_and_excess_lift_side(gap: float) -> None:
    finished = retainer.THICKNESS + sum(retention.TOP_RUNNING_GAP) / 2.0 - gap
    with pytest.raises(ValueError, match="loaded running gap"):
        retainer.require_loaded_running_gap(finished)


def test_cross_hole_retains_a_real_end_ligament_at_printed_limits() -> None:
    from_end_min = pin.CROSS_HOLE_FROM_END - printed_band_mm(pin.LENGTH_PLACES)
    drilled_radius_max = (pin.CROSS_HOLE_DIA + pin.CROSS_HOLE_BAND[0]) / 2.0
    lead_max = pin.LEAD_CHAMFER_MAX  # native MAX on the carrier end, not its general .X band
    assert pin.CARRIER_LENGTH == pin.CROSS_HOLE_FROM_SEAT + pin.CROSS_HOLE_FROM_END
    assert from_end_min - drilled_radius_max - lead_max >= 2.0
    assert pin.CROSS_HOLE_DIA > hardware.CLEVIS_DIA_MAX
    assert retainer.PIN_PROJECTION_ABOVE_WORK == pytest.approx(
        pin.CARRIER_LENGTH - carrier.THICKNESS - trammel.RISER_THICK - trammel.STRAP_THICK
    )


@pytest.mark.parametrize("excess", retention.CAP_CHAMBER_EXCESS)
def test_fitted_lower_and_upper_gaps_prevent_bearing_preload(excess: float) -> None:
    # Independent measured lower gap, not bearing width or interference pullout.
    assert 0.0 < retention.PIN_LOWER_GAP[0] <= retention.PIN_LOWER_GAP[1] < excess
    assert cap.fitted_chamber_excess(pin.FLANGE_THICK + excess, pin.FLANGE_THICK) == pytest.approx(excess)
    assert retention.capture_bounds(chamber_excess=excess).cap_running_clearance > 0.0


@pytest.mark.parametrize("excess", (retention.CAP_CHAMBER_EXCESS[0] - 0.01, retention.CAP_CHAMBER_EXCESS[1] + 0.01))
def test_fitted_chamber_rejects_both_tight_and_excessive_clearance(excess: float) -> None:
    with pytest.raises(ValueError, match="chamber excess"):
        cap.fitted_chamber_excess(pin.FLANGE_THICK + excess, pin.FLANGE_THICK)


@pytest.mark.parametrize("changes", (
    {"chamber_excess": 10.0},
    {"flange_diameter_min": 30.0},
    {"cap_hole_diameter_max": 12.0},
    {"cap_hole_diameter_max": 1.0},
    {"receiver_location_band": 3.0},
    {"cap_location_band": 3.0},
    {"pocket_diameter_max": 42.0},
    {"bearing_bore_diameter_max": 33.0},
    {"carriage_counterbore_diameter_max": 20.0},
    {"carrier_engagement": 0.1},
    {"carrier_clearance": 2.0},
))
def test_geometric_mutants_lose_capture_or_running_contact(changes: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        retention.capture_bounds(**changes)


@pytest.mark.parametrize("pattern_name", ("receiver_pattern", "cap_pattern"))
def test_relocated_pattern_cannot_hide_behind_nominal_symmetric_defaults(pattern_name: str) -> None:
    # Start with the ACTUAL block/cap pattern. Translate it without changing
    # its spacing: using only a nominal pattern would miss this loss of stop overlap.
    source = tuple((x - block.BORE_X, y) for x, y in block.CAP_TAP_POINTS) if pattern_name == "receiver_pattern" else cap.BOLT_POINTS
    relocated = tuple((x + 3.0, y + 3.0) for x, y in source)
    with pytest.raises(ValueError, match="contact|clearance"):
        retention.capture_bounds(**{pattern_name: relocated})
    with pytest.raises(ValueError, match="four"):
        retention.capture_bounds(**{pattern_name: source[:-1]})


def test_cap_material_acceptance_rejects_real_wall_and_floor_mutants() -> None:
    assert all(margin >= 2.0 for margin in cap.require_clearance_geometry().values())
    for changes in ({"counterbore_depth": cap.HEIGHT}, {"channel_depth": cap.HEIGHT}, {"pocket_dia": cap.WIDTH}, {"points": tuple((x, 19.0 if y > 0 else -19.0) for x, y in cap.BOLT_POINTS)}):
        with pytest.raises(ValueError, match="cap"):
            cap.require_clearance_geometry(**changes)


def test_unknown_pass_does_not_default_to_one_retained_pair() -> None:
    with pytest.raises(ValueError, match="unknown pass"):
        retention.point_lift_bound((0.0, 0.0), "unretained")


SYNTHETIC_AUTHORITY = "SYNTHETIC TEST ENVELOPE — NOT AN INSTALLED MACHINE MEASUREMENT"


def _synthetic_tooling(*, radius: float = 2.0, radial: float = 0.0, axial: float = 0.0) -> tooling.InstalledToolingEnvelope:
    return tooling.InstalledToolingEnvelope(
        SYNTHETIC_AUTHORITY, radial, axial, (tooling.ToolingCylinder(0.0, 5.0, radius),),
    )


def _fixture(
    *, x: float = 10.0, z_min: float = 0.0, z_max: float = 5.0, label: str = "synthetic prism",
) -> tooling.FixtureEnvelope:
    return tooling.FixtureEnvelope(label, ((x, -2.0), (x + 2.0, -2.0), (x + 2.0, 2.0), (x, 2.0)), z_min, z_max)


def test_absent_installed_envelope_stays_unverified_without_nominal_cutter_fallback() -> None:
    report = tooling.tooling_clearance_report(None, (_fixture(),))
    assert report.status == "UNVERIFIED"
    assert report.min_clearance is None
    assert report.limiting_pair is None
    assert report.authority is None
    assert tooling.tooling_clearance_report(None, ()).status == "UNVERIFIED"


def test_synthetic_radial_separation_uses_polygon_edges_not_vertex_distance() -> None:
    report = tooling.tooling_clearance_report(_synthetic_tooling(), (_fixture(),))
    assert report.status == "VERIFIED_GEOMETRY_ONLY"
    assert report.min_clearance == pytest.approx(8.0)
    assert report.min_clearance < math.hypot(10.0, 2.0) - 2.0
    assert report.limiting_pair == ("synthetic prism", 0)
    assert report.authority == SYNTHETIC_AUTHORITY


def test_synthetic_axial_separation_can_clear_a_radially_overlapping_step() -> None:
    report = tooling.tooling_clearance_report(_synthetic_tooling(radius=5.0), (_fixture(x=1.0, z_min=10.0, z_max=12.0),))
    assert report.status == "VERIFIED_GEOMETRY_ONLY"
    assert report.min_clearance == pytest.approx(5.0)
    diagonal = tooling.tooling_clearance_report(_synthetic_tooling(), (_fixture(z_min=10.0, z_max=12.0),))
    assert diagonal.min_clearance == pytest.approx(max(8.0, 5.0))
    assert diagonal.min_clearance < math.hypot(8.0, 5.0)  # deliberately conservative


@pytest.mark.parametrize("xy", (
    ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)),
    ((-1.0, 1.0), (1.0, 1.0), (1.0, -1.0), (-1.0, -1.0)),
))
def test_axis_inside_polygon_is_possible_overlap_even_if_all_vertices_are_outside_tool(xy: tuple) -> None:
    fixture = tooling.FixtureEnvelope("enclosing polygon", xy, 0.0, 5.0)
    report = tooling.tooling_clearance_report(_synthetic_tooling(radius=0.25), (fixture,))
    assert all(math.hypot(*point) > 0.25 for point in xy)
    assert report.status == "POTENTIAL_CONFLICT"
    assert report.min_clearance == pytest.approx(-0.25)


def test_concave_polygon_notch_is_not_replaced_by_its_axis_aligned_box() -> None:
    xy = ((-4.0, -4.0), (4.0, -4.0), (4.0, -2.0), (-2.0, -2.0), (-2.0, 4.0), (-4.0, 4.0))
    for polygon in (xy, tuple(reversed(xy))):
        fixture = tooling.FixtureEnvelope("concave synthetic", polygon, 0.0, 5.0)
        report = tooling.tooling_clearance_report(_synthetic_tooling(radius=1.0), (fixture,))
        assert report.status == "VERIFIED_GEOMETRY_ONLY"
        assert report.min_clearance == pytest.approx(1.0)


def test_synthetic_stepped_holder_uses_each_steps_real_z_interval() -> None:
    fixture = _fixture(x=4.0, z_min=10.0, z_max=12.0)
    stepped = tooling.InstalledToolingEnvelope(
        SYNTHETIC_AUTHORITY, 0.0, 0.0,
        (tooling.ToolingCylinder(0.0, 5.0, 10.0), tooling.ToolingCylinder(10.0, 15.0, 2.0)),
    )
    report = tooling.tooling_clearance_report(stepped, (fixture,))
    assert report.status == "VERIFIED_GEOMETRY_ONLY"
    assert report.min_clearance == pytest.approx(2.0)
    assert report.limiting_pair == (fixture.label, 1)
    mutant = tooling.InstalledToolingEnvelope(
        SYNTHETIC_AUTHORITY, 0.0, 0.0, (tooling.ToolingCylinder(0.0, 15.0, 10.0),),
    )
    assert tooling.tooling_clearance_report(mutant, (fixture,)).status == "POTENTIAL_CONFLICT"


@pytest.mark.parametrize("fixture,envelope", (
    (_fixture(x=2.0), _synthetic_tooling()),
    (_fixture(x=1.0, z_min=5.0, z_max=7.0), _synthetic_tooling(radius=5.0)),
    (_fixture(x=3.0), _synthetic_tooling(radial=1.0)),
    (_fixture(x=1.0, z_min=6.0, z_max=7.0), _synthetic_tooling(radius=5.0, axial=1.0)),
))
def test_touching_after_radial_or_axial_uncertainty_is_not_positive_clearance(
    fixture: tooling.FixtureEnvelope, envelope: tooling.InstalledToolingEnvelope,
) -> None:
    report = tooling.tooling_clearance_report(envelope, (fixture,))
    assert report.status == "POTENTIAL_CONFLICT"
    assert report.min_clearance == pytest.approx(0.0)


def test_limiting_fixture_and_step_are_reported_without_dropping_a_family() -> None:
    fixtures = (_fixture(x=20.0, label="far"), _fixture(x=1.0, label="near"))
    report = tooling.tooling_clearance_report(_synthetic_tooling(), fixtures)
    assert report.status == "POTENTIAL_CONFLICT"
    assert report.min_clearance == pytest.approx(-1.0)
    assert report.limiting_pair == ("near", 0)


@pytest.mark.parametrize("values", (
    (0.0, 0.0, 1.0), (5.0, 0.0, 1.0), (0.0, 5.0, 0.0),
    (0.0, 5.0, -1.0), (math.nan, 5.0, 1.0), (0.0, math.inf, 1.0),
    (0.0, 5.0, math.inf), (0.0, 5.0, True),
))
def test_invalid_measured_tooling_dimensions_are_rejected(values: tuple) -> None:
    with pytest.raises(ValueError):
        tooling.ToolingCylinder(*values)


@pytest.mark.parametrize("source,radial,axial,steps", (
    ("", 0.0, 0.0, (tooling.ToolingCylinder(0.0, 5.0, 2.0),)),
    ("  ", 0.0, 0.0, (tooling.ToolingCylinder(0.0, 5.0, 2.0),)),
    (SYNTHETIC_AUTHORITY, -0.1, 0.0, (tooling.ToolingCylinder(0.0, 5.0, 2.0),)),
    (SYNTHETIC_AUTHORITY, 0.0, -0.1, (tooling.ToolingCylinder(0.0, 5.0, 2.0),)),
    (SYNTHETIC_AUTHORITY, math.nan, 0.0, (tooling.ToolingCylinder(0.0, 5.0, 2.0),)),
    (SYNTHETIC_AUTHORITY, 0.0, math.inf, (tooling.ToolingCylinder(0.0, 5.0, 2.0),)),
    (SYNTHETIC_AUTHORITY, 0.0, 0.0, ()),
))
def test_missing_authority_uncertainty_or_empty_measurements_cannot_verify(
    source: str, radial: float, axial: float, steps: tuple,
) -> None:
    with pytest.raises(ValueError):
        tooling.InstalledToolingEnvelope(source, radial, axial, steps)


@pytest.mark.parametrize("xy", (
    ((0.0, 0.0), (1.0, 1.0)),
    ((0.0, 0.0), (1.0, 1.0), (2.0, 2.0)),
    ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)),
    ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 0.0)),
    ((0.0, 0.0), (math.inf, 0.0), (0.0, 2.0)),
))
def test_invalid_fixture_polygons_are_not_silently_treated_as_clear(xy: tuple) -> None:
    with pytest.raises(ValueError):
        tooling.FixtureEnvelope("invalid synthetic", xy, 0.0, 5.0)


def test_measured_authority_cannot_verify_an_empty_or_ambiguous_fixture_census() -> None:
    with pytest.raises(ValueError, match="census"):
        tooling.tooling_clearance_report(_synthetic_tooling(), ())
    with pytest.raises(ValueError, match="unique"):
        tooling.tooling_clearance_report(_synthetic_tooling(), (_fixture(), _fixture(x=20.0)))


def test_authority_geometry_and_report_are_frozen() -> None:
    from dataclasses import FrozenInstanceError

    envelope = _synthetic_tooling()
    fixture = _fixture()
    report = tooling.tooling_clearance_report(envelope, (fixture,))
    for value, attribute, replacement in (
        (envelope, "source", "not measured"),
        (envelope.steps[0], "radius", 0.1),
        (fixture, "z_max", 0.1),
        (report, "status", "machine certified"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(value, attribute, replacement)




@pytest.mark.parametrize("label,z_min,z_max", (("", 0.0, 5.0), ("  ", 0.0, 5.0), ("invalid", 5.0, 0.0), ("invalid", 0.0, math.inf)))
def test_invalid_fixture_identity_or_height_is_rejected(label: str, z_min: float, z_max: float) -> None:
    with pytest.raises(ValueError):
        _fixture(label=label, z_min=z_min, z_max=z_max)

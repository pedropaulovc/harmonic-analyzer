"""Independent mathematical controls; no CAD, config, solver or native imports."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from stock_form_cutter import (
    CutterTemplate,
    CustomSixCutter,
    StockFormProfile,
    template_for_teeth,
    translation_for_pitch_tooth_thickness,
    translation_for_tangent_span,
)


def _rotate(point, angle):
    x, y = point
    return x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)


def _profile(teeth, ref, *, dp=48.0, beta=0.0, T=None, radius=None):
    cutter = CutterTemplate(ref, dp, 20.0)
    pitch = teeth * cutter.module_mm / (2 * math.cos(math.radians(beta)))
    translation = pitch - cutter.pitch_radius_mm if T is None else T
    probe = StockFormProfile(teeth, cutter, pitch, translation, beta)
    return StockFormProfile(teeth, cutter, probe.support_radius_max_mm if radius is None else radius, translation, beta)


def _shoelace(points):
    return math.fsum(x * b - y * a for (x, y), (a, b) in zip(points, points[1:] + points[:1])) / 2


def _simpson(function, lo, hi, intervals=2000):
    step = (hi - lo) / intervals
    return step / 3 * math.fsum(
        function(lo + i * step) * (1 if i in (0, intervals) else 4 if i % 2 else 2)
        for i in range(intervals + 1)
    )


def _normal_screw_hand(profile, point):
    """Independent 3D rotate+z solve, not the core transverse equation."""
    xr, yr = point
    beta = math.radians(profile.helix_angle_deg)
    x, y, z = xr + profile.radial_translation_mm, yr * math.cos(beta), -yr * math.sin(beta)
    if beta:
        lead = profile.pitch_radius_mm / math.tan(beta)
        theta = -z / lead
        assert z + lead * theta == pytest.approx(0, abs=1e-15)
        x, y = _rotate((x, y), theta)
    return x, y


def _independent_gap_polygon(profile, samples=3000):
    """Dense reference geometry + 3D screw, independent of core descriptors.

    Intersections are solved against the blank independently. This is an
    area CONTROL, not an unbounded replacement for analytic membership.
    """
    c = profile.template
    m = 25.4 / c.diametral_pitch
    rp = c.reference_teeth * m / 2
    rb = rp * math.cos(math.radians(c.pressure_angle_deg))
    pa = math.radians(c.pressure_angle_deg)
    k = math.pi / c.reference_teeth - c.pitch_tooth_thickness_mm / (2 * rp) - math.tan(pa) + pa
    u0 = math.sqrt(max(0, (c.root_radius_mm / rb) ** 2 - 1))
    u1 = math.sqrt((c.tip_radius_mm / rb) ** 2 - 1)
    alpha = k + u0 - math.atan(u0)

    def flank(u):
        # Complex involute unrolling is algebraically independent of the
        # literal x/y equation and its Green primitive.
        phase = complex(math.cos(k + u), math.sin(k + u))
        z = rb * phase * complex(1, -u)
        return z.real, z.imag

    def radial(r):
        return r * math.cos(k), r * math.sin(k)

    below = c.root_radius_mm < rb
    base = math.hypot(*_normal_screw_hand(profile, radial(rb)))
    is_radial = below and profile.blank_radius_mm < base
    function = radial if is_radial else flank
    lo, hi = (c.root_radius_mm, rb) if is_radial else (u0, u1)
    for _ in range(64):
        mid = (lo + hi) / 2
        if math.hypot(*_normal_screw_hand(profile, function(mid))) < profile.blank_radius_mm:
            lo = mid
        else:
            hi = mid
    top = (lo + hi) / 2
    points = []
    for i in range(samples):
        theta = alpha - 2 * alpha * i / samples
        points.append(_normal_screw_hand(profile, (c.root_radius_mm * math.cos(theta), c.root_radius_mm * math.sin(theta))))
    for side, outward in ((-1, True), (1, False)):
        branch = []
        if below:
            upper = top if is_radial else rb
            branch += [radial(c.root_radius_mm + (upper-c.root_radius_mm) * i / samples) for i in range(samples)]
        if not is_radial:
            branch += [flank(u0 + (top-u0) * i / samples) for i in range(samples)]
        tip = _normal_screw_hand(profile, function(top))
        angle = math.atan2(tip[1], tip[0])
        if side == 1:
            points += [(profile.blank_radius_mm * math.cos(-angle + 2 * angle * i / samples),
                        profile.blank_radius_mm * math.sin(-angle + 2 * angle * i / samples)) for i in range(samples)]
            branch.append(function(top))
            branch.reverse()
        points += [_normal_screw_hand(profile, (x, side * y)) for x, y in branch]
    return points


@pytest.mark.parametrize("selection,number,reference", [
    (12, 8, 12), (13.999, 8, 12), (14, 7, 14), (16.9, 7, 14),
    (17, 6, 17), (21, 5, 21), (26, 4, 26), (35, 3, 35),
    (55, 2, 55), (69.185, 2, 55), (134.999, 2, 55), (135, 1, 135), (5000, 1, 135),
])
def test_finite_lowest_count_stock_selection(selection, number, reference):
    c = template_for_teeth(selection, 48, 20)
    assert c.cutter_number == number
    assert c.reference_teeth == reference
    assert c.teeth_range[0] == reference
    assert c.tip_radius_mm == pytest.approx((reference / 2 + 1) * 25.4 / 48)
    if number == 1:
        assert c.teeth_range == (135, None)


def test_immutable_explicit_forms_and_physical_count():
    c = CutterTemplate(55, 48, 20)
    with pytest.raises(FrozenInstanceError):
        c.reference_teeth = 120
    with pytest.raises(ValueError, match="physical"):
        StockFormProfile(69.185, c, 18, 3)
    for selection in (6, 11.999, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            template_for_teeth(selection, 48, 20)
    with pytest.raises(ValueError, match="lowest"):
        CutterTemplate(120, 48, 20)


@pytest.mark.parametrize("reference", [12, 14, 26, 55, 135])
def test_zero_translation_standard_control(reference):
    c = CutterTemplate(reference, 48, 20)
    p = StockFormProfile(reference, c, c.tip_radius_mm, 0)
    assert p.root_radius_min_mm == pytest.approx(c.root_radius_mm)
    assert p.root_radius_max_mm == pytest.approx(c.root_radius_mm)
    assert p.pitch_tooth_thickness_mm == pytest.approx(math.pi * c.module_mm / 2)
    assert p.plunge_mm == pytest.approx(2.25 * c.module_mm)
    # Independently integrate radial gap widths in the standard concentric
    # control. Above base change variable r=rb*sqrt(1+u^2), r*dr=rb^2*u*du.
    k, rb = c.half_space_base_angle_rad, c.base_radius_mm
    radial = k * max(0, rb * rb - c.root_radius_mm ** 2)
    polar = radial + _simpson(lambda u: 2 * rb * rb * u * (k + u - math.atan(u)), c.flank_parameter_min, c.flank_parameter_max)
    assert p.gap_area_mm2 == pytest.approx(polar, abs=2e-10)
    assert p.gap_area_error_bound_mm2 < 1e-8


@pytest.mark.parametrize("teeth,ref,beta", [(9, 12, 0), (16, 14, 0), (32, 26, 0), (120, 55, 0), (64, 55, 13.0011)])
def test_source_independent_green_polygon_area(teeth, ref, beta):
    p = _profile(teeth, ref, dp=24 if teeth in (16, 64) else 48, beta=beta)
    independent = _shoelace(_independent_gap_polygon(p))
    assert independent == pytest.approx(p.gap_area_mm2, abs=2e-6)
    polygon = p.gap_polygon(2000)
    eps = p.gap_polygon_error_bound_mm(2000)
    perimeter_bound = sum(s.speed_bound_mm for s in p.gap_segments())
    assert abs(_shoelace(list(polygon)) - p.gap_area_mm2) <= perimeter_bound * eps + math.pi * eps * eps + p.gap_area_error_bound_mm2


def test_support_probe_body_tip_and_no_upper_extrapolation():
    c = CutterTemplate(55, 48, 20)
    T = (120-55) * c.module_mm / 2
    pitch = 120 * c.module_mm / 2
    probe = StockFormProfile(120, c, pitch, T)
    assert probe.support_radius_max_mm < pitch + c.module_mm
    StockFormProfile(120, c, probe.support_radius_max_mm, T)
    with pytest.raises(ValueError, match="FINITE"):
        StockFormProfile(120, c, probe.support_radius_max_mm + .001, T)
    with pytest.raises(ValueError, match="finite reference"):
        probe.flank_point(c.flank_parameter_max + .001)
    with pytest.raises(ValueError, match="root envelope"):
        StockFormProfile(120, c, probe.root_radius_max_mm, T)
    for dp in (0, -1, float("nan")):
        with pytest.raises(ValueError):
            CutterTemplate(12, dp, 20)


def test_low_count_below_base_and_55_above_base_topology():
    below, above = _profile(16, 14, dp=24), _profile(120, 55)
    assert below.template.root_radius_mm < below.template.base_radius_mm
    assert above.template.root_radius_mm > above.template.base_radius_mm
    assert len(below.native_segments()) == 8
    assert len(above.native_segments()) == 6
    assert sum(s.kind == "radial" for s in below.native_segments()) == 2
    assert not any(s.kind == "radial" for s in above.native_segments())
    for p in (below, above):
        segments = p.native_segments()
        for a, b in zip(segments, segments[1:] + segments[:1]):
            assert a.end_mm == pytest.approx(b.start_mm, abs=p.geometry_error_bound_mm)
        root = segments[0]
        assert (root.name, root.kind) == ("RootArc", "root_arc")
        assert root.start_mm == pytest.approx(p.root_point(p.root_half_angle_rad))


def test_partial_below_base_blank_has_no_degenerate_flank():
    c = CutterTemplate(12, 48, 20)
    p = StockFormProfile(12, c, (c.root_radius_mm + c.base_radius_mm) / 2, 0)
    assert all(s.kind != "flank" for s in p.native_segments())
    assert len(p.native_segments()) == 6
    with pytest.raises(ValueError, match="supported involute"):
        p.tangent_span_mm(1)


@pytest.mark.parametrize("teeth,ref", [(9, 12), (32, 26), (120, 55)])
def test_actual_root_min_max_are_not_translation_plus_reference(teeth, ref):
    p = _profile(teeth, ref)
    endpoint = math.hypot(*p.root_point(p.root_half_angle_rad))
    bisector = p.radial_translation_mm + p.template.root_radius_mm
    assert p.root_radius_min_mm == pytest.approx(min(endpoint, bisector))
    assert p.root_radius_max_mm == pytest.approx(max(endpoint, bisector))
    assert endpoint != pytest.approx(bisector, abs=1e-8)
    if p.radial_translation_mm > 0:
        assert p.root_radius_min_mm < bisector
    else:
        assert p.root_radius_max_mm > bisector


@pytest.mark.parametrize("beta", [0, 13.0011])
def test_analytic_material_two_disjoint_root_strips_and_phase(beta):
    p = _profile(64 if beta else 120, 55, dp=24 if beta else 48, beta=beta)
    theta = .75 * p.root_half_angle_rad
    root = p.root_point(theta)
    delta = (p.root_radius_max_mm - math.hypot(*root)) / 4
    removed = p.normal_to_transverse((p.template.root_radius_mm + delta) * math.cos(theta),
                                     (p.template.root_radius_mm + delta) * math.sin(theta))
    radius = math.hypot(*removed)
    assert p.root_radius_min_mm < radius < p.root_radius_max_mm
    assert p.contains_material(radius, 0)  # solid middle between removed strips
    assert not p.contains_material(*removed)
    assert not p.contains_material(removed[0], -removed[1])
    assert p.contains_material(*root)  # closed material boundary
    assert p.contains_material(radius * math.cos(math.pi / p.teeth), radius * math.sin(math.pi / p.teeth))
    for phase in (-.714, .319):
        assert not p.contains_material(*_rotate(removed, phase), rotate_rad=phase)
        assert p.contains_material(*_rotate((radius, 0), phase), rotate_rad=phase)
    assert not p.contains_material(p.blank_radius_mm + .01, 0)


@pytest.mark.parametrize("beta", [13.0011, -13.0011])
def test_helix_independent_rotation_z_elimination_and_root(beta):
    p = _profile(64, 55, dp=24, beta=beta)
    c = p.template
    for u in (c.flank_parameter_min, (c.flank_parameter_min+c.flank_parameter_max)/2, c.flank_parameter_max):
        for side in (-1, 1):
            normal = c.flank_point(u, side)
            independent = _normal_screw_hand(p, normal)
            assert p.flank_point(u, side) == pytest.approx(independent, abs=2e-12)
            assert p.transverse_to_normal(*independent) == pytest.approx(normal, abs=2e-12)
    angles = [i * p.root_half_angle_rad / 1000 for i in range(1001)]
    radii = [math.hypot(*_normal_screw_hand(p, c.root_point(angle))) for angle in angles]
    assert min(radii) == pytest.approx(p.root_radius_min_mm, abs=1e-8)
    assert max(radii) == pytest.approx(p.root_radius_max_mm, abs=1e-8)


@pytest.mark.parametrize("teeth,ref,span,dp", [(16, 14, 2, 24), (32, 26, 3, 48), (120, 55, 8, 48)])
def test_actual_spur_span_independent_parallel_contacts(teeth, ref, span, dp):
    p = _profile(teeth, ref, dp=dp)
    h = math.pi * span / teeth
    u = h - p.template.half_space_base_angle_rad
    a = _rotate(p.flank_point(u, 1), -h)
    b = _rotate(p.flank_point(u, -1), h)
    ta = _rotate((math.cos(h), math.sin(h)), -h)
    tb = _rotate((math.cos(h), -math.sin(h)), h)
    assert ta[1] == pytest.approx(0, abs=1e-13)
    assert tb[1] == pytest.approx(0, abs=1e-13)
    assert b[1] - a[1] == pytest.approx(p.tangent_span_mm(span), abs=1e-12)
    ideal = 2 * p.pitch_radius_mm * math.cos(math.radians(20)) * (h - (math.pi/(2*teeth) - math.tan(math.radians(20)) + math.radians(20)))
    assert abs(ideal - p.tangent_span_mm(span)) > 1e-5


def test_helical_span_uses_actual_tangent_and_screw_normal():
    p = _profile(64, 55, dp=24, beta=13.0011)
    h = math.pi * 5 / 64
    lo, hi = p.flank_parameter_min, p.flank_parameter_max
    # Differentiate independent 3D construction by central differences.
    def contact_tangent(u):
        du = 1e-6
        a = _normal_screw_hand(p, p.template.flank_point(u-du))
        b = _normal_screw_hand(p, p.template.flank_point(u+du))
        return (b[0]-a[0])/(2*du), (b[1]-a[1])/(2*du)
    for _ in range(48):
        mid = (lo+hi)/2
        tangent = contact_tangent(mid)
        if math.atan2(tangent[1], tangent[0]) < h:
            lo = mid
        else:
            hi = mid
    u = (lo+hi)/2
    point = _normal_screw_hand(p, p.template.flank_point(u))
    tangent = contact_tangent(u)
    normal2 = tangent[1]/math.hypot(*tangent), -tangent[0]/math.hypot(*tangent)
    screw_tangent = -point[1]/p.lead_per_radian_mm, point[0]/p.lead_per_radian_mm
    nz = -(normal2[0]*screw_tangent[0]+normal2[1]*screw_tangent[1])
    transverse = -2 * _rotate(point, -h)[1]
    expected = transverse / math.sqrt(1+nz*nz)
    assert p.tangent_span_mm(5, normal_plane=False) == pytest.approx(transverse, abs=1e-7)
    assert p.tangent_span_mm(5) == pytest.approx(expected, abs=1e-7)
    assert abs(expected - transverse * math.cos(math.radians(p.helix_angle_deg))) > 1e-5


@pytest.mark.parametrize("beta", [0, 13.0011])
def test_native_equations_other_units_phase_and_bounded_derivatives(beta):
    p = _profile(64 if beta else 32, 55 if beta else 26, dp=24 if beta else 48, beta=beta)
    scale, phase = 1/1000, .327
    segments = p.material_sector_segments(unit_scale=scale, rotate_rad=phase)
    for s in segments:
        for t in (0, .13, .57, 1):
            context = {"t": t, "sin": math.sin, "cos": math.cos}
            literal = eval(s.x, {"__builtins__": {}}, context), eval(s.y, {"__builtins__": {}}, context)
            assert literal == pytest.approx(tuple(scale*z for z in s.point(t)), abs=2e-14)
            assert math.hypot(*s.derivative(t)) <= s.speed_bound_mm + 1e-10
        a, b = s.point(.31), s.point(.32)
        assert math.dist(a, b) <= .01*s.speed_bound_mm + 1e-10
        left, middle, right = s.point(.3), s.point(.5), s.point(.7)
        chord_mid = ((left[0]+right[0])/2, (left[1]+right[1])/2)
        assert math.dist(middle, chord_mid) <= s.second_derivative_bound_mm*.4*.4/8 + 1e-10
    for a, b in zip(segments, segments[1:] + segments[:1]):
        assert a.end_mm == pytest.approx(b.start_mm, abs=1e-11)


@pytest.mark.parametrize("beta", [0, 13.0011])
def test_complete_material_sector_preserves_root_lobes(beta):
    p = _profile(64 if beta else 120, 55, dp=24 if beta else 48, beta=beta)
    embed = p.root_radius_min_mm * .8
    segments = p.material_sector_segments(unit_scale=1, embed_radius_mm=embed)
    polygon = [s.point(i/2000) for s in segments for i in range(2000)]
    expected = math.pi * (p.blank_radius_mm**2-embed**2)/p.teeth - p.gap_area_mm2
    assert _shoelace(polygon) == pytest.approx(expected, abs=2e-6)
    assert [s.name for s in segments if s.kind == "root_arc"] == ["LeftHalfRootArc", "RightHalfRootArc"]
    exterior = p.external_boundary_segments()
    assert all(s.kind not in {"seam", "embed_arc"} for s in exterior)
    assert exterior[-1].end_mm == pytest.approx(_rotate(exterior[0].start_mm, p.angular_pitch_rad), abs=1e-11)
    with pytest.raises(ValueError, match="true root minimum"):
        p.material_sector_segments(embed_radius_mm=p.root_radius_min_mm)
    with pytest.raises(ValueError, match="caller minimum"):
        p.require_tip_land(p.tip_land_mm + .001)
    p.require_tip_land(p.tip_land_mm - .001)


def test_custom_six_is_named_finite_raised_root_not_stock():
    c = CustomSixCutter(48, 20, 1.173, 1.95, math.pi * (25.4/48)/2,
                        "DT6-FORM1", "Main-approved N6 PA20 derived finite ground form")
    p = StockFormProfile(6, c, 1.95, 0)
    assert c.reference_teeth == 6
    assert c.cutter_number is None
    assert c.name == "DT6-FORM1"
    assert p.root_radius_min_mm == pytest.approx(1.173)
    assert len(p.native_segments()) == 8
    assert 2*p.root_radius_min_mm == pytest.approx(2.346)
    assert p.gap_area_mm2 == pytest.approx(_shoelace(_independent_gap_polygon(p)), abs=2e-6)
    with pytest.raises(ValueError, match="name and source"):
        CustomSixCutter(48, 20, 1.173, 1.95, .8, "", "")
    with pytest.raises(ValueError, match="FINITE"):
        StockFormProfile(6, c, 1.951, 0)


def test_wrong_actual_count_material_oracle_is_discriminated():
    actual = _profile(120, 55)
    ideal = StockFormProfile(135, CutterTemplate(135, 48, 20), 135 * 25.4 / 96, 0)
    # Discriminate the real translated 55-master from ANY ideal actual-N
    # notch using its below-axis offcentre strip; compare same physical
    # radius/angle with an independently concentric hypothetical N120 gap.
    radius = (actual.root_radius_min_mm + actual.root_radius_max_mm) / 2
    assert actual.contains_material(radius, 0)
    concentric_root = actual.pitch_radius_mm - 1.25 * actual.template.module_mm
    assert radius < concentric_root
    theta = actual.root_half_angle_rad * .75
    floor = actual.root_point(theta)
    d = (actual.root_radius_max_mm-math.hypot(*floor))/4
    strip = actual.normal_to_transverse((actual.template.root_radius_mm+d)*math.cos(theta),
                                       (actual.template.root_radius_mm+d)*math.sin(theta))
    assert math.hypot(*strip) < concentric_root  # ideal N120 would call solid
    assert not actual.contains_material(*strip)
    assert ideal.contains_material(*strip)  # deliberately wrong physical geometry


@pytest.mark.parametrize("teeth,ref,beta,dp", [
    (16, 14, 0, 24), (32, 26, 0, 48), (120, 55, 0, 48),
    (64, 55, 13.0011, 24), (64, 55, -13.0011, 24),
])
def test_actual_pitch_thickness_translation_roundtrip(teeth, ref, beta, dp):
    c = CutterTemplate(ref, dp, 20)
    pitch = teeth * c.module_mm / (2 * math.cos(math.radians(beta)))
    nominal = pitch - c.pitch_radius_mm
    targets = []
    for T in (nominal-.01*c.module_mm, nominal, nominal+.01*c.module_mm):
        p = StockFormProfile(teeth, c, pitch, T, beta)
        target = p.pitch_tooth_thickness_mm
        solved = translation_for_pitch_tooth_thickness(teeth, c, target, beta)
        assert solved == pytest.approx(T, abs=2e-11)
        targets.append(target)
    assert targets[0] < targets[1] < targets[2]


def test_pitch_thickness_inversion_independent_contact_and_refusal():
    c = CutterTemplate(14, 24, 20)
    pitch, u = 16*c.module_mm/2, .35
    rb, k = c.base_radius_mm, c.half_space_base_angle_rad
    x = rb*(math.cos(k+u)+u*math.sin(k+u))
    y = rb*(math.sin(k+u)-u*math.cos(k+u))
    X = math.sqrt(pitch*pitch-y*y)
    target = pitch*(2*math.pi/16-2*math.atan2(y, X))
    assert translation_for_pitch_tooth_thickness(16, c, target) == pytest.approx(X-x, abs=2e-12)
    for bad in (0, -1, float("nan")):
        with pytest.raises(ValueError):
            translation_for_pitch_tooth_thickness(16, c, bad)
    with pytest.raises(ValueError, match="positive pitch gap"):
        translation_for_pitch_tooth_thickness(16, c, 2*math.pi*pitch/16+.001)
    with pytest.raises(ValueError, match="supported reference"):
        translation_for_pitch_tooth_thickness(16, c, .001)


@pytest.mark.parametrize("teeth,ref,beta,dp,count", [
    (16, 14, 0, 24, 2), (32, 26, 0, 48, 3), (120, 55, 0, 48, 8),
    (64, 55, 13.0011, 24, 5), (64, 55, -13.0011, 24, 5),
])
def test_actual_normal_span_translation_roundtrip(teeth, ref, beta, dp, count):
    c = CutterTemplate(ref, dp, 20)
    pitch = teeth*c.module_mm/(2*math.cos(math.radians(beta)))
    nominal = pitch-c.pitch_radius_mm
    lo, hi = nominal-.02*c.module_mm, nominal+.02*c.module_mm
    for T in (lo, nominal, hi):
        target = StockFormProfile(teeth, c, pitch, T, beta).tangent_span_mm(count)
        result = translation_for_tangent_span(
            teeth, c, target, count, beta, translation_bounds_mm=(lo, hi)
        )
        assert result == pytest.approx(T, abs=2e-11)


def test_span_inverse_independent_spur_control_and_bounds():
    c = CutterTemplate(14, 24, 20)
    pitch = 16*c.module_mm/2
    nominal = pitch-c.pitch_radius_mm
    h = 2*math.pi/16
    u = h-c.half_space_base_angle_rad
    T = nominal+.001
    target = 2*c.base_radius_mm*u+2*T*math.sin(h)
    bounds = nominal-.01, nominal+.01
    assert translation_for_tangent_span(
        16, c, target, 2, translation_bounds_mm=bounds
    ) == pytest.approx(T, abs=1e-12)
    with pytest.raises(ValueError, match="outside the caller"):
        translation_for_tangent_span(
            16, c, target+1, 2, translation_bounds_mm=bounds
        )
    with pytest.raises(ValueError, match="finite and ordered"):
        translation_for_tangent_span(
            16, c, target, 2, translation_bounds_mm=bounds[::-1]
        )
    with pytest.raises(ValueError, match="span count"):
        translation_for_tangent_span(
            16, c, target, 1.5, translation_bounds_mm=bounds
        )


@pytest.mark.parametrize("dp,T,radius", [
    (48.0, 0.0, 7.40/2), (48.0, .01, 7.40/2), (32.0, .21, 11.50/2),
])
def test_span_inverse_uses_finite_support_beyond_pitch(dp, T, radius):
    """Reported PD12 W2 contact is valid outside its physical pitch circle."""
    c = CutterTemplate(12, dp, 20)
    actual = StockFormProfile(12, c, radius, T)
    u = 2*math.pi/12-c.half_space_base_angle_rad
    assert u > math.tan(math.radians(20))
    assert u < actual.flank_parameter_max
    target = actual.tangent_span_mm(2)
    solved = translation_for_tangent_span(
        12, c, target, 2, translation_bounds_mm=(T-.001, T+.001)
    )
    assert solved == pytest.approx(T, abs=2e-12)
    assert StockFormProfile(12, c, radius, solved).tangent_span_mm(2) == pytest.approx(target, abs=2e-12)
    # The support-domain inverse never certifies an undersize manufactured
    # blank: the actual profile must still reject this same contact.
    undersize = StockFormProfile(12, c, c.pitch_radius_mm, 0)
    with pytest.raises(ValueError, match="finite flank"):
        undersize.tangent_span_mm(2)


def test_span_inverse_does_not_impose_a_pitch_radius_blank():
    c = CutterTemplate(12, 48, 20)
    T = .70
    actual = StockFormProfile(12, c, 4.25, T)
    assert actual.root_radius_min_mm > actual.pitch_radius_mm
    target = actual.tangent_span_mm(2)
    solved = translation_for_tangent_span(
        12, c, target, 2, translation_bounds_mm=(T-.001, T+.001)
    )
    assert solved == pytest.approx(T, abs=2e-12)
    assert StockFormProfile(12, c, 4.25, solved).tangent_span_mm(2) == pytest.approx(target, abs=2e-12)


@pytest.mark.parametrize("delta_T", [-.05, .05])
def test_translated_120_turned_blank_span_corner_roundtrip(delta_T, monkeypatch):
    """A finite-domain inverse is not a manufactured full-cap proxy."""
    c = CutterTemplate(55, 48, 20)
    h = 8*math.pi/120
    u = h-c.half_space_base_angle_rad
    corner_T = (120-55)*c.module_mm/2+delta_T
    raw_span = 2*c.base_radius_mm*u+2*corner_T*math.sin(h)
    printed_span = (math.floor(raw_span*1e4) if delta_T < 0 else math.ceil(raw_span*1e4))/1e4
    expected = (printed_span-2*c.base_radius_mm*u)/(2*math.sin(h))

    def forbid_manufactured_proxy(*args, **kwargs):
        raise AssertionError("span inverse must not construct any manufactured blank proxy")

    monkeypatch.setattr("stock_form_cutter.StockFormProfile", forbid_manufactured_proxy)
    T = translation_for_tangent_span(
        120, c, printed_span, 8,
        translation_bounds_mm=(expected-.01, expected+.01),
    )
    assert T == pytest.approx(expected, abs=2e-12)
    xref, yref = c.flank_point(u)
    contact_radius = math.hypot(xref+T, yref)
    xtip, ytip = c.flank_point(c.flank_parameter_max)
    support = math.hypot(xtip+T, ytip)
    # Choose a physical turned blank above the actual contact and below the
    # finite upper support. No fictitious cap-profile is used by the inverse.
    blank = (contact_radius+support)/2
    actual = StockFormProfile(120, c, blank, T)
    assert actual.tangent_span_mm(8) == pytest.approx(printed_span, abs=2e-12)
    actual.require_tip_land(.1)


def test_span_inverse_refuses_contact_past_finite_master_support():
    c = CutterTemplate(12, 48, 20)
    with pytest.raises(ValueError, match="finite flank"):
        translation_for_tangent_span(
            12, c, 10, 3, translation_bounds_mm=(0, .01)
        )

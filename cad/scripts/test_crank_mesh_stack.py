"""Behavioral proof for the restored fixed-centre crank mesh."""

import asyncio
import math
from types import SimpleNamespace

import pytest

import crank_mesh_stack as stack


def test_print_worst_closing_corner_cannot_bind() -> None:
    assert stack.TIGHT_BACKLASH_MM > 0.0
    assert stack.TIGHT_BACKLASH_MM < stack.NOMINAL_TIGHT_BACKLASH_MM

def test_gear_seat_runout_and_shortened_pinion_face_reach_the_stack() -> None:
    from gear_seat_fit import GEAR_SEAT_CLEARANCE

    terms = {term.name: term.tight for term in stack.TERMS}
    assert terms["gear bore runout"] == pytest.approx(
        -stack.KC
        * (stack.pinion.BORE_DIAMETRAL_CLEARANCE[1] + GEAR_SEAT_CLEARANCE[1])
        / 2.0
    )
    face_deviation = stack.pinion.printed_deviations(
        stack.pinion.FACE_WIDTH,
        stack.pinion.FACE_WIDTH_PLACES,
        stack.pinion.FACE_WIDTH_LIMITS,
    )[1]
    assert stack.pinion.FACE_WIDTH == 11.6
    assert stack.PINION_HALF_FACE_MAX == pytest.approx(
        (stack.pinion.FACE_WIDTH + face_deviation) / 2.0
    )
    assert stack.MESH_LEVER > stack.post.CRANK_BOSS_NORTH_FACE


def test_closing_bore_spacing_consumes_backlash() -> None:
    def tight(spacing: float) -> float:
        terms = stack.stack_terms(
            spacing_printed=spacing,
            plan_limit_deg=stack.POST_ANGLE_DEG,
            crank_angle_deg=stack.POST_ANGLE_DEG,
            crank_bearing_length=stack.CRANK_BEARING_LENGTH,
        )
        return stack.NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms)

    # A sufficiently misplaced fixed bore must not masquerade as a usable mesh.
    assert tight(stack.SPACING_PRINTED - 0.2) < 0.0
    assert tight(stack.SPACING_PRINTED + 0.2) > stack.TIGHT_BACKLASH_MM


def test_bore_angularity_matters_at_the_mesh() -> None:
    def loss(angle: float) -> float:
        return sum(t.tight for t in stack.stack_terms(
            spacing_printed=stack.SPACING_PRINTED,
            plan_limit_deg=angle,
            crank_angle_deg=angle,
            crank_bearing_length=stack.CRANK_BEARING_LENGTH,
        ))

    assert loss(0.0) > loss(stack.POST_ANGLE_DEG)
    assert loss(stack.POST_ANGLE_DEG) > loss(stack.POST_ANGLE_DEG * 2.0)


def test_pose_loss_checks_interior_quadratic_minimum() -> None:
    # y(t) = t² - t has its worst angle at +0.5, not at either limit.
    nominal = stack.NOMINAL_TIGHT_BACKLASH_MM
    assert stack._pose_loss({1.0: nominal, -1.0: nominal + 2.0}, 1.0) == pytest.approx(-0.25)


def test_resting_shaft_tilt_increases_with_overhang() -> None:
    near = stack._float_at_rest(0.05, 70.0, 0.0)
    far = stack._float_at_rest(0.05, 70.0, 10.0)
    assert near == pytest.approx(0.025)
    assert far > near
    assert stack._float_at_rest(0.05, 35.0, 10.0) > far


def test_platform_axis_maps_to_the_restored_crank_axis() -> None:
    import cone_line as line
    import dt_cone_swing_platform_crank_axis as platform

    x, z = platform.CRANK_SEAT_ANCHOR
    machine_x = line.PIVOT_XZ[0] + x * line.COS_I + z * line.SIN_I
    assert machine_x == pytest.approx(line.X_CRANK, abs=1e-6)
    assert line.Y_BASE_TOP + platform.CRANK_AXIS_Y == pytest.approx(line.Y_CRANK)
    assert math.hypot(x, z) == pytest.approx(platform.CRANK_AXIS_OFF)


def test_open_corner_carries_the_cone_stack_north_float() -> None:
    # Codex P2 on #1154: at the stack's north float the 64T slides up the
    # inclined cone axis and the centres open further; the printed worst-case
    # contact ratio must count it.
    import build_dt_drive_train_assembly as bdt
    from cone_line import COS_I, SIN_I
    from cone_stack_end_play import CONE_FLOAT_NORTH, SHAFT_END_PLAY, STACK_FLOAT

    assert CONE_FLOAT_NORTH == SHAFT_END_PLAY[1] + STACK_FLOAT[1]
    float_term = stack.OPEN_TERMS["cone stack north float"]
    assert float_term == pytest.approx(
        CONE_FLOAT_NORTH * SIN_I * COS_I * stack.DC_PER_DX
    )
    # The exact opening at the physical centres: the 64T's in-plane leg grows
    # by the float's projection; the booked linear term stays within 0.002.
    exact = (
        math.hypot(bdt._DX16 + CONE_FLOAT_NORTH * SIN_I * COS_I, bdt._DY16)
        - bdt.CRANK_ACTUAL_C2C
    )
    assert exact == pytest.approx(bdt.CRANK_MESH_FLOAT_OPENING_EXACT)
    assert 0.0 < exact - float_term < 0.002

    def worst(opening: float) -> float:
        return stack.contact_ratio(
            centre_distance=bdt.CRANK_ACTUAL_C2C + opening,
            tip_dia_16=stack.TIP_DIA_LOW_16,
            tip_dia_64=stack.TIP_DIA_LOW_64,
        )

    unfloated = worst(stack.OPEN_CENTRE_DISTANCE_MM - float_term)
    baseline_floor = bdt.CRANK_MESH_PRINTED_CONTACT_RATIO
    assert worst(stack.OPEN_CENTRE_DISTANCE_MM) == pytest.approx(
        bdt.CRANK_MESH_CONTACT_RATIO_WORST
    )
    # This experiment deliberately leaves drawings untouched. The relocated
    # normal-pitch pair must retain the accepted baseline worst-CR floor,
    # including exact north-float opening, rather than pin stale print text.
    assert unfloated > worst(stack.OPEN_CENTRE_DISTANCE_MM)
    assert bdt.CRANK_MESH_CONTACT_RATIO_WORST >= baseline_floor
    assert worst(stack.OPEN_CENTRE_DISTANCE_MM - float_term + exact) >= baseline_floor


class _GearProfileAdapter:
    """Bounded equation/path recorder: no COM and no geometric stand-in."""

    def __init__(self) -> None:
        self.curves = []
        self.planes = []
        self.active_plane = None
        self.constraints = []
        self.path_length = None
        self.path_name = None
        self.sweep = None

    @staticmethod
    def _result(data=None):
        return SimpleNamespace(is_success=True, data=data, error=None)

    async def create_sketch(self, plane):
        assert self.active_plane is None
        assert plane in ("Front", "Top")
        self.planes.append(plane)
        self.active_plane = plane
        return self._result()

    async def create_equation_driven_curve(self, params):
        assert self.active_plane == "Front"
        assert (params.range_start, params.range_end) == ("0", "1")
        assert not params.z_expression
        self.curves.append(params)
        return self._result(f"Curve{len(self.curves)}")

    async def check_sketch_fully_defined(self):
        assert self.active_plane is not None
        return self._result({"definition_state": "fully_defined"})

    async def exit_sketch(self):
        assert self.active_plane is not None
        self.active_plane = None
        return self._result()

    async def add_line(self, x1, y1, x2, y2):
        assert self.active_plane == "Top"
        assert (x1, y1, x2) == (0.0, 0.0, 0.0)
        assert y2 < 0.0
        self.path_length = -y2
        return self._result("Line1")

    async def add_sketch_constraint(self, entity, other, kind):
        assert self.active_plane == "Top"
        assert (entity, other, kind) in (
            ("Line1", None, "vertical"),
            ("Line1.start", "origin", "coincident"),
        )
        self.constraints.append((entity, other, kind))
        return self._result()

    async def add_sketch_dimension(self, first, second, kind, value):
        assert (first, second, kind) == (
            "Line1.start", "Line1.end", "vertical_distance"
        )
        assert value == self.path_length
        return self._result("D1@ToothPath")

    def name_last_feature(self, name):
        assert self.active_plane is None
        assert self.planes == ["Front", "Top"]
        assert name == "ToothPath"
        self.path_name = name
        return name

    async def create_sweep(self, params):
        assert self.active_plane is None
        assert len(self.curves) == 6
        assert len(self.constraints) == 2
        assert params.path == self.path_name == "ToothPath"
        assert params.twist_along_path and params.merge_result
        self.sweep = params
        return self._result(SimpleNamespace(name="ToothSweep"))

    async def create_cut_extrude(self, params):
        assert self.active_plane is None
        assert self.planes == ["Front"]
        assert params.depth > 0.0
        return self._result(SimpleNamespace(name="ToothGap"))


@pytest.fixture
def gear_profile_adapter(monkeypatch):
    import _gear

    adapter = _GearProfileAdapter()
    monkeypatch.setattr(
        _gear, "name_last_feature",
        lambda seat, name: seat.name_last_feature(name),
    )
    return adapter


def _curve_point(curve, t):
    # These are the actual numeric radian expressions handed to the adapter,
    # not a separately implemented or source-string-inspected tooth profile.
    scope = {"__builtins__": {}, "cos": math.cos, "sin": math.sin, "t": t}
    return (
        eval(curve.x_expression, scope),
        eval(curve.y_expression, scope),
    )


def _profile_points(curves, walk, *, samples=64, radial_clip=None):
    points = []
    for index, reverse in walk:
        segment = [
            _curve_point(curves[index], (samples - i if reverse else i) / samples)
            for i in range(samples + 1)
        ]
        if points:
            assert segment[0] == pytest.approx(points[-1], rel=0.0, abs=3e-11)
        points.extend(segment if not points else segment[1:])
    assert points[-1] == pytest.approx(points[0], rel=0.0, abs=3e-11)
    points[-1] = points[0]
    if radial_clip is not None:
        lo, hi = radial_clip
        points = [
            (
                x * min(hi, max(lo, math.hypot(x, y))) / math.hypot(x, y),
                y * min(hi, max(lo, math.hypot(x, y))) / math.hypot(x, y),
            )
            for x, y in points
        ]
    return points


def _polygon_area(points):
    return abs(sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:])
    )) / 2.0


def _assert_simple_profile(points):
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    edges = list(zip(points, points[1:]))
    for i, (a, b) in enumerate(edges):
        assert math.dist(a, b) > 1e-12
        for j in range(i + 2, len(edges)):
            if i == 0 and j == len(edges) - 1:
                continue
            c, d = edges[j]
            if (
                max(a[0], b[0]) < min(c[0], d[0])
                or max(c[0], d[0]) < min(a[0], b[0])
                or max(a[1], b[1]) < min(c[1], d[1])
                or max(c[1], d[1]) < min(a[1], b[1])
            ):
                continue
            assert not (
                cross(a, b, c) * cross(a, b, d) <= 0.0
                and cross(c, d, a) * cross(c, d, b) <= 0.0
            ), f"non-adjacent profile edges {i}, {j} intersect"


_TOOTH_WALK = ((0, False), (1, False), (2, True), (3, False), (4, False), (5, False))


def _crank_gear_profile():
    from dt_crank_drive_gear_spec import (
        BACKLASH_MM, CUTTER_DIAMETRAL_PITCH, DEDENDUM_FACTOR,
        DIAMETRAL_PITCH, FACE_WIDTH, HELIX_ANGLE_DEG, LONG_ADDENDUM_MM,
        PRESSURE_ANGLE_DEG, ROOT_DIA, TEETH,
    )
    from involute_gear import gear_facts

    assert TEETH == 64
    assert CUTTER_DIAMETRAL_PITCH == pytest.approx(25.4, abs=1e-10)
    assert DEDENDUM_FACTOR == 1.25
    assert LONG_ADDENDUM_MM == 0.0
    assert FACE_WIDTH == 7.2113
    normal_pa = math.degrees(math.atan(
        math.tan(math.radians(PRESSURE_ANGLE_DEG))
        * math.cos(math.radians(HELIX_ANGLE_DEG))
    ))
    assert normal_pa == pytest.approx(20.0, abs=1e-10)

    extra = 1.0 / CUTTER_DIAMETRAL_PITCH - 1.0 / DIAMETRAL_PITCH + LONG_ADDENDUM_MM / 25.4
    facts = gear_facts(
        TEETH, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG, addendum_extra_in=extra
    )
    pitch_r = TEETH / (2.0 * DIAMETRAL_PITCH)
    root = pitch_r - DEDENDUM_FACTOR / CUTTER_DIAMETRAL_PITCH
    assert root * 50.8 == pytest.approx(ROOT_DIA)
    eps = BACKLASH_MM / (2.0 * pitch_r * 25.4)
    twist = FACE_WIDTH * math.tan(math.radians(HELIX_ANGLE_DEG)) / (pitch_r * 25.4)
    return facts, root, eps, twist, FACE_WIDTH, extra, DIAMETRAL_PITCH, PRESSURE_ANGLE_DEG


def test_m1_pa20_swept_profile_starts_at_root_and_never_crosses(gear_profile_adapter):
    import _gear
    from involute_gear import involute_point

    facts, root, eps, twist, face, extra, dp, pa = _crank_gear_profile()
    assert root > facts["Rb"]
    assert root - _gear._TOOTH_EMBED_MM / 25.4 > facts["Rb"]
    rho = -twist / 2.0
    name = asyncio.run(_gear.boss_tooth_swept(
        gear_profile_adapter, facts, face, twist_deg=math.degrees(twist),
        rotate_rad=rho, widen_rad=eps, root_r_in=root,
    ))
    assert name == "ToothSweep"
    assert gear_profile_adapter.sweep.twist_angle == pytest.approx(math.degrees(twist))
    curves = gear_profile_adapter.curves
    points = _profile_points(curves, _TOOTH_WALK)
    _assert_simple_profile(points)

    u0 = math.sqrt((root / facts["Rb"])**2 - 1.0)
    assert _gear._root_start_parameter(facts["Rb"], root) == pytest.approx(u0)
    inv0 = u0 - math.atan(u0)
    foot_angles = (
        facts["Gamma"] - facts["Delta"] + eps + rho + inv0,
        facts["Gamma"] + facts["Delta"] - eps + rho - inv0,
    )
    # Reparameterising the same involute must not alter geometry outside
    # the root (including the diagnostic mesh domain).
    for i in range(17):
        t = i / 16.0
        u = u0 + (facts["Tmax"] - u0) * t
        for index, upper, rotation in (
            (0, True, eps + rho),
            (2, False, facts["Gamma"] - eps + rho),
        ):
            x, y = involute_point(facts, u, upper=upper)
            reference = (
                x * math.cos(rotation) - y * math.sin(rotation),
                x * math.sin(rotation) + y * math.cos(rotation),
            )
            assert _curve_point(curves[index], t) == pytest.approx(
                reference, rel=0.0, abs=3e-11
            )
    for index, angle in zip((0, 2), foot_angles):
        assert _curve_point(curves[index], 0.0) == pytest.approx(
            (root * math.cos(angle), root * math.sin(angle)), rel=0.0, abs=3e-11
        )
        radii = [math.hypot(*_curve_point(curves[index], i / 64.0)) for i in range(65)]
        assert all(a < b for a, b in zip(radii, radii[1:]))
        assert radii[-1] == pytest.approx(facts["Ra"], rel=0.0, abs=3e-11)
    embed = root - _gear._TOOTH_EMBED_MM / 25.4
    for index, reverse in ((3, False), (5, True)):
        radii = [
            math.hypot(*_curve_point(curves[index], (64 - i if reverse else i) / 64.0))
            for i in range(65)
        ]
        assert radii[0] == pytest.approx(root, rel=0.0, abs=3e-11)
        assert radii[-1] == pytest.approx(embed, rel=0.0, abs=3e-11)
        assert all(a > b for a, b in zip(radii, radii[1:]))

    # Clip only the embedded sliver to the physical blank radius: it adds no
    # material to the union. This checks build_fixed_gear's area complement.
    physical = _profile_points(
        curves, _TOOTH_WALK, samples=2000, radial_clip=(root, facts["Ra"])
    )
    gap = _gear.gap_area_in_disc_ext(
        64, dp, pa, eps, root, addendum_extra_in=extra
    )
    tooth = math.pi * (facts["Ra"]**2 - root**2) / 64.0 - gap
    assert _polygon_area(physical) == pytest.approx(tooth, rel=0.0, abs=2e-9)


def test_m1_pa20_gap_clips_to_same_root_and_volume_oracle(gear_profile_adapter):
    import _gear

    facts, root, eps, twist, face, extra, dp, pa = _crank_gear_profile()
    asyncio.run(_gear.cut_tooth_gap(
        gear_profile_adapter, facts, face + 1.0,
        rotate_rad=-twist / 2.0, widen_rad=eps, root_r_in=root,
    ))
    curves = gear_profile_adapter.curves
    assert len(curves) == 6  # no zero-length/outward base-to-root extensions
    walk = ((0, False), (2, False), (3, False), (4, False), (1, True), (5, False))
    _assert_simple_profile(_profile_points(curves, walk))
    for index in (0, 1):
        assert math.hypot(*_curve_point(curves[index], 0.0)) == pytest.approx(
            root, rel=0.0, abs=3e-11
        )
    clipped = _profile_points(
        curves, walk, samples=2000, radial_clip=(root, facts["Ra"])
    )
    expected = _gear.gap_area_in_disc_ext(
        64, dp, pa, eps, root, addendum_extra_in=extra
    )
    assert _polygon_area(clipped) == pytest.approx(expected, rel=0.0, abs=2e-10)
    u0 = math.sqrt((root / facts["Rb"])**2 - 1.0)
    inv0 = u0 - math.atan(u0)
    root_span = facts["Gamma"] - 2.0 * facts["Delta"] + 2.0 * eps + 2.0 * inv0
    tip_span = facts["ThetaU"] - facts["ThetaL"] + 2.0 * eps
    exact = (
        facts["Ra"]**2 * tip_span - root**2 * root_span
        - 2.0 * facts["Rb"]**2 * (facts["Tmax"]**3 - u0**3) / 3.0
    ) / 2.0
    assert expected == pytest.approx(exact, rel=0.0, abs=2e-9)


@pytest.mark.parametrize("teeth,dp,pa", ((16, 25.4, 20.0), (64, 24.74, 14.5), (12, 12.7, 14.5)))
def test_below_base_sweep_keeps_original_profile(gear_profile_adapter, teeth, dp, pa):
    import _gear
    from involute_gear import gear_facts

    facts = gear_facts(teeth, dp, pa)
    root = teeth / (2.0 * dp) - 1.157 / dp
    assert 0.0 < root < facts["Rb"]
    assert _gear._root_start_parameter(facts["Rb"], root) == 0.0
    eps, rho = 0.001, -0.012
    asyncio.run(_gear.boss_tooth_swept(
        gear_profile_adapter, facts, 7.2113, twist_deg=2.0,
        rotate_rad=rho, widen_rad=eps, root_r_in=root,
    ))
    rb, ra = facts["Rb"], facts["Ra"]
    embed = root - _gear._TOOTH_EMBED_MM / 25.4
    a_lo = facts["Gamma"] - facts["Delta"] + eps + rho
    a_hi = facts["Gamma"] + facts["Delta"] - eps + rho
    for i in range(17):
        t = i / 16.0
        u = facts["Tmax"] * t
        ph_a, ph_b = u + a_lo, u - a_hi
        tip = facts["ThetaU"] + eps + rho + t * (
            facts["Gamma"] + facts["ThetaL"] - facts["ThetaU"] - 2.0 * eps
        )
        arc = a_hi + t * (a_lo - a_hi)
        reference = (
            (rb * (math.cos(ph_a) + u * math.sin(ph_a)), rb * (math.sin(ph_a) - u * math.cos(ph_a))),
            (ra * math.cos(tip), ra * math.sin(tip)),
            (rb * (math.cos(ph_b) + u * math.sin(ph_b)), rb * (u * math.cos(ph_b) - math.sin(ph_b))),
            ((rb + t * (embed - rb)) * math.cos(a_hi), (rb + t * (embed - rb)) * math.sin(a_hi)),
            (embed * math.cos(arc), embed * math.sin(arc)),
            ((embed + t * (rb - embed)) * math.cos(a_lo), (embed + t * (rb - embed)) * math.sin(a_lo)),
        )
        for curve, point in zip(gear_profile_adapter.curves, reference, strict=True):
            assert _curve_point(curve, t) == pytest.approx(point, rel=0.0, abs=3e-11)


@pytest.mark.parametrize("root_kind", ("chord", "below", "base"))
def test_below_base_gap_keeps_floor_and_involute_endpoints(gear_profile_adapter, root_kind):
    import _gear
    from involute_gear import gap_area_in_disc, gear_facts, involute_point

    facts = gear_facts(16, 25.4, 20.0)
    root = {"chord": None, "below": 6.75 / 25.4, "base": facts["Rb"]}[root_kind]
    assert _gear._root_start_parameter(facts["Rb"], root) == 0.0
    asyncio.run(_gear.cut_tooth_gap(gear_profile_adapter, facts, 8.0, root_r_in=root))
    curves = gear_profile_adapter.curves
    assert len(curves) == (8 if root_kind == "below" else 6)
    for i in range(17):
        t = i / 16.0
        for index, upper in ((0, False), (1, True)):
            assert _curve_point(curves[index], t) == pytest.approx(
                involute_point(facts, facts["Tmax"] * t, upper=upper),
                rel=0.0, abs=3e-11,
            )
    floor_walk = ((5, False), (6, False), (7, False)) if root_kind == "below" else ((5, False),)
    walk = ((0, False), (2, False), (3, False), (4, False), (1, True), *floor_walk)
    _assert_simple_profile(_profile_points(curves, walk))
    area = _gear.gap_area_in_disc_ext(16, 25.4, 20.0, root_r_in=root)
    if root_kind == "chord":
        assert area == pytest.approx(gap_area_in_disc(16, dp=25.4, pa_deg=20.0), abs=1e-12)
    clipped = _profile_points(
        curves, walk, samples=2000, radial_clip=(0.0, facts["Ra"])
    )
    assert _polygon_area(clipped) == pytest.approx(area, rel=0.0, abs=2e-10)


@pytest.mark.parametrize("root_kind", ("negative", "zero", "tip", "above_tip", "embed_zero"))
def test_invalid_root_is_refused_before_sweep_profile(gear_profile_adapter, root_kind):
    import _gear

    facts, _, eps, twist, face, extra, dp, pa = _crank_gear_profile()
    root = {
        "negative": -1.0, "zero": 0.0, "tip": facts["Ra"],
        "above_tip": facts["Ra"] + 0.01, "embed_zero": _gear._TOOTH_EMBED_MM / 25.4,
    }[root_kind]
    with pytest.raises(ValueError, match="root"):
        asyncio.run(_gear.boss_tooth_swept(
            gear_profile_adapter, facts, face, twist_deg=math.degrees(twist),
            rotate_rad=0.0, widen_rad=eps, root_r_in=root,
        ))
    assert not gear_profile_adapter.curves
    assert not gear_profile_adapter.planes
    if root_kind != "embed_zero":
        with pytest.raises(ValueError, match="root"):
            asyncio.run(_gear.cut_tooth_gap(
                gear_profile_adapter, facts, face, root_r_in=root,
            ))
        with pytest.raises(ValueError, match="root"):
            _gear.gap_area_in_disc_ext(
                64, dp, pa, eps, root, addendum_extra_in=extra,
            )

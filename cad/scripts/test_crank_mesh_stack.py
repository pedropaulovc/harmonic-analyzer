"""Offline contracts for the crank-mesh fit-up stack (#906 R1)."""

from __future__ import annotations

import ast
import asyncio
import math
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_drive_train_assembly as drive
import cone_pivot_post_spec as post
import crank_boss_rim
import crank_drive_gear_spec as gear64
import gear64_post_measure
import crank_eccentric_bushing_spec as bushing
import crank_mesh_stack as stack
import crank_pinion_spec as pinion
from diagnostics import crossed_mesh_study as crossed
from diagnostics import probe_crank_post_phase, probe_live_crank_mesh


def _terms(**overrides: float) -> dict[str, stack.Term]:
    kwargs = {
        "spacing_printed": stack.SPACING_PRINTED,
        "plan_limit_deg": stack.POST_ANGLE_DEG,
        "crank_angle_deg": stack.CRANK_ANGLE_DEG,
        "crank_bearing_length": stack.CRANK_BEARING_LENGTH,
        **overrides,
    }
    return {t.name: t for t in stack.stack_terms(**kwargs)}


def test_linear_model_reads_every_measured_case_within_its_residual() -> None:
    """The exact-solid study, from -0.35 to +0.15 of centre distance, at
    both R1 fit-up states and at the nominal fit-up the bushing throws the
    axis sideways to, stays within LINEAR_RESIDUAL_MM of the model; the
    residual is the worst of them rounded out to 0.001."""
    residuals = [
        abs(measured - stack._linear_backlash(dc, thin64, thin16))
        for dc, thin64, thin16, measured in stack.STUDY_CASES.values()
    ]
    assert max(residuals) <= stack.LINEAR_RESIDUAL_MM
    assert stack.LINEAR_RESIDUAL_MM == pytest.approx(
        math.ceil(max(residuals) / 0.001) * 0.001
    )
    assert max(residuals) == pytest.approx(0.0054, abs=1e-4)
    assert stack.STUDY_CASES["R1-fitaxis-nominal"][0] == pytest.approx(
        stack.FITUP_DC_NOMINAL, abs=1e-5
    )
    assert stack.KC == pytest.approx(0.5846, abs=1e-4)


def test_the_throw_reaches_both_ends() -> None:
    print(stack.stack_text())
    assert stack.THROW_REACH == bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[1]
    assert stack.OPEN_MARGIN > 0.0
    assert stack.CLOSE_MARGIN > 0.0


def test_the_printed_drop_is_the_one_that_centres_the_reach() -> None:
    assert round(stack.IDEAL_DROP, 2) == post.CRANK_BORE_DROP
    assert abs(stack.OPEN_MARGIN - stack.CLOSE_MARGIN) < 0.02


def test_both_shafts_sag_at_rest_at_both_corners() -> None:
    terms = _terms()
    crank = terms["crank float at rest"]
    cone = terms["cone float at rest"]
    assert crank.tight < crank.loose < 0.0
    assert 0.0 < cone.tight < cone.loose


def test_every_angle_source_is_in_the_budget() -> None:
    assert stack.CRANK_ANGLE_DEG == pytest.approx(
        stack.POST_ANGLE_DEG + stack.BUSHING_ANGLE_DEG + stack.SEAT_COCK_DEG
    )
    assert stack.MESH_LEVER == pytest.approx(27.575, abs=1e-3)
    # The post frame's move at the mesh: the verifier's 0.038 over the
    # harvested 72.03 boss; the spot face's 2.5 retreat shortens the zone's
    # span to 69.53, so the same 0.10 zone lets it turn a little further.
    assert stack.POST_ANGLE_AT_MESH == pytest.approx(0.0397, abs=5e-4)


def test_the_angularity_frame_is_load_bearing() -> None:
    """At the title block's +/-1 deg in place of the frame, the stack no
    longer closes."""
    terms = _terms(plan_limit_deg=1.0, crank_angle_deg=1.0 + stack.BUSHING_ANGLE_DEG)
    tight = stack.NOMINAL_TIGHT_BACKLASH_MM + sum(t.tight for t in terms.values())
    assert stack.THROW_REACH - (stack.FITUP_BACKLASH_MM - tight) / stack.KC < 0.0


def test_no_worst_case_tip_reaches_a_root() -> None:
    """At the worst reading the fitter accepts (the bottom of the band), with
    both tips at the top of their printed band."""
    assert stack.WORST_ACCEPTED_BACKLASH_MM == pytest.approx(0.22)
    assert (
        stack.WORST_CLOSE_NEEDED <= bushing.ECCENTRICITY + bushing.ECCENTRICITY_BAND[0]
    )
    assert stack.TIP_ROOT_BAND_RADIAL == pytest.approx(
        max(pinion.OUTSIDE_DIA_TOLERANCE_MM, gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
    )
    assert stack.TIP_ROOT_AIR_WORST == pytest.approx(0.1804, abs=5e-4)


def test_the_tip_band_is_a_reach_term_measured_at_its_own_band() -> None:
    """Exact solids at +/-0.05 radial on both gears: the worst closing is the
    loose fit-up with large tips (-0.0043), the worst opening the worst
    accepted state with small ones (+0.0047); the term rounds each outward."""
    readings = stack._TIP_BAND_READINGS
    assert min(readings.values()) == pytest.approx(-0.00435, abs=1e-5)
    assert min(readings, key=readings.get) == ("loose fit-up", +1)
    assert max(readings.values()) == pytest.approx(+0.00474, abs=1e-5)
    assert max(readings, key=readings.get) == ("worst accepted", -1)
    term = {t.name: t for t in stack.TERMS}["tip diameter band"]
    assert term.tight == pytest.approx(-0.005)
    assert term.loose == pytest.approx(+0.005)
    assert term.tight <= min(readings.values())
    assert term.loose >= max(readings.values())
    assert stack.TIP_ROOT_BAND_RADIAL == stack._TIP_BAND_MEASURED_RADIAL


def test_r1_throw_margins_at_e_0625() -> None:
    assert bushing.ECCENTRICITY == 0.625
    assert stack.THROW_REACH == pytest.approx(0.600)
    # 0.0338 / 0.0269 before the spot face's 2.5 retreat: the shorter boss
    # loosens the angularity zone's angle and the 16T now overhangs the
    # bushing's end by the retreat more (crank_mesh_stack PINION_BEYOND_BUSHING).
    assert stack.OPEN_MARGIN == pytest.approx(0.0282, abs=5e-4)
    assert stack.CLOSE_MARGIN == pytest.approx(0.0219, abs=5e-4)
    assert stack.IDEAL_DROP == pytest.approx(0.2132, abs=5e-4)


def test_bonding_leaves_the_fitter_a_reading_allowance() -> None:
    assert stack.RESEAT_DC == stack.SEAT_AT_MESH
    assert stack.READING_ALLOWANCE > 0.015


def test_frame_matches_the_assembly_c2c() -> None:
    assert stack.FRAME_C2C == pytest.approx(39.735, abs=0.001)
    assert stack.FRAME_DY == pytest.approx(39.332, abs=1e-9)
    assert stack.SPACING_PRINTED == round(stack.FRAME_DY - post.CRANK_BORE_DROP, 2)


def test_the_platform_crank_axis_is_the_fitup_axis_and_prints_nothing() -> None:
    """User ruling R1 (a): the plate's hidden crank-axis reference moves to
    the nominal fit-up axis by the stack's derived offsets, and no printed
    platform dimension is taken off it."""
    import build_cone_swing_platform as plat
    import cone_swing_platform_crank_axis as axis

    assert axis.CRANK_AXIS_OFF == pytest.approx(
        axis._CRANK_AXIS_OFF_FRAME - stack.FITUP_AXIS_DX, abs=1e-12
    )
    assert axis.CRANK_AXIS_Y == pytest.approx(
        axis._CRANK_AXIS_Y_FRAME + stack.FITUP_AXIS_DY, abs=1e-12
    )
    # The builder authors the axis from those numbers, not copies of them.
    assert (plat.CRANK_AXIS_Y, plat.CRANK_SEAT_ANCHOR) == (
        axis.CRANK_AXIS_Y,
        axis.CRANK_SEAT_ANCHOR,
    )
    assert stack.FITUP_AXIS_DX == pytest.approx(0.6029, abs=5e-4)
    assert stack.FITUP_AXIS_DY == pytest.approx(-0.0454, abs=5e-4)
    assert plat._CRANK_AXIS_FEATURES.isdisjoint(plat.DRAWING_DIMENSIONS)
    # Each is a feature the build really names (once in the set, again where
    # it is created), so the guard cannot go stale on a rename.
    source = Path(plat.__file__).read_text(encoding="utf-8")
    for feature in plat._CRANK_AXIS_FEATURES:
        assert source.count(f'"{feature}"') >= 2, feature


# ---- the SolidWorks mesh probes place the pair where the assembly does ------
# ``diagnostics/probe_live_crank_mesh.py`` and ``probe_crank_post_phase.py``
# rebuild the 16T/64T pair in a throwaway assembly to read exact interference,
# so a probe that places either gear anywhere else measures a mesh the machine
# does not have.  Codex on #960 (T_LAU): R1 moved the 16T onto the fit-up axis
# while both probes still placed it on the frame crank axis (0.603 mm), and
# the live probe still placed the 64T at the unshifted GEAR64_STATION.  Each
# probe's ``build`` runs against a recording ``place_component`` that stops
# once both gears are placed; the assembly's placements come from its single
# ``place_component("crank-pinion", ...)`` and
# ``_place_on_shaft(adapter, "crank-drive-gear", ...)`` call sites.

ASSEMBLY = Path(drive.__file__)
PROBE_GEARS = ("crank-drive-gear", "crank-pinion")


class _BothGearsPlaced(Exception):
    """The rest of the probe needs a seat."""


class _ProbeAdapter:
    async def create_assembly(self):
        return SimpleNamespace(is_success=True, data=None, error=None)


def _placement_recorder(placed: dict[str, list[float]], stop_when_both: bool):
    async def place_component(adapter, part, position, *args, **kwargs):
        placed[part] = [float(value) for value in position]
        if stop_when_both and all(gear in placed for gear in PROBE_GEARS):
            raise _BothGearsPlaced
        return f"{part}-1"

    return place_component


def _probe_placements(probe, monkeypatch) -> dict[str, list[float]]:
    placed: dict[str, list[float]] = {}
    monkeypatch.setattr(probe, "place_component", _placement_recorder(placed, True))
    with pytest.raises(_BothGearsPlaced):
        asyncio.run(probe.build(_ProbeAdapter()))
    return placed


def _assembly_call(function: str, part: str) -> ast.Call:
    tree = ast.parse(ASSEMBLY.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == function
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == part
    ]
    assert len(calls) == 1, f"{part}: expected one {function} call site"
    return calls[0]


def _assembly_eval(expr: ast.expr):
    code = compile(ast.Expression(expr), str(ASSEMBLY), "eval")
    return eval(code, dict(vars(drive)))


def _assembly_placements(monkeypatch) -> dict[str, list[float]]:
    pinion_call = _assembly_call("place_component", "crank-pinion")
    placed = {"crank-pinion": [float(v) for v in _assembly_eval(pinion_call.args[2])]}
    gear_call = _assembly_call("_place_on_shaft", "crank-drive-gear")
    monkeypatch.setattr(drive, "place_component", _placement_recorder(placed, False))
    station, face = (_assembly_eval(arg) for arg in gear_call.args[2:4])
    asyncio.run(drive._place_on_shaft(None, "crank-drive-gear", station, face))
    return placed


def _max_delta(a: list[float], b: list[float]) -> float:
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


@pytest.mark.parametrize(
    "probe",
    [probe_live_crank_mesh, probe_crank_post_phase],
    ids=lambda probe: probe.__name__.rsplit(".", 1)[-1],
)
@pytest.mark.parametrize("gear", PROBE_GEARS)
def test_probe_places_the_gear_where_the_assembly_does(probe, gear, monkeypatch):
    expected = _assembly_placements(monkeypatch)[gear]
    monkeypatch.undo()
    placed = _probe_placements(probe, monkeypatch)[gear]
    delta = _max_delta(placed, expected)
    assert delta < 1e-9, (
        f"{probe.__name__} places {gear} at {placed}, {delta:.6f} mm off the "
        f"assembly's {expected}"
    )


def test_the_frame_crank_axis_is_not_the_fit_up_axis(monkeypatch):
    # Positive control: the pre-R1 pinion origin, on the frame crank axis,
    # sits measurably off the placement the probes are pinned to.
    stale = [
        drive.X_CRANK,
        drive.Y_CRANK,
        drive.PINION_TOOTH_Z - drive.PINION_FACE / 2.0,
    ]
    expected = _assembly_placements(monkeypatch)["crank-pinion"]
    assert _max_delta(stale, expected) > 1e-3


# ---- the crossed-mesh study checks the pose the assembly ships ---------------
# Codex on #960 (WjI8): diagnostics/crossed_mesh_study.py asserted the
# assembly's fit-up-derived PINION_SEED_DEG while still studying the pair on
# the frame crank axis.  Its axis is now explicit: SHIPPED_AXIS for the
# shipped pose, frame_axis(extra) for the frame-axis rederivation.


def test_the_crossed_mesh_study_ships_the_fit_up_pose() -> None:
    assert crossed.SHIPPED_AXIS == (drive.X_CRANK_FIT, drive.Y_CRANK_FIT)
    shipped = crossed.pose(crossed.SHIPPED_AXIS, drive.MESH_WINDOW_CENTRE_DEG)
    assert shipped["seed"] == pytest.approx(drive.PINION_SEED_DEG, abs=1e-9)
    assert shipped["c2c"] == pytest.approx(drive.CRANK_FIT_C2C, abs=1e-9)


def test_the_crossed_mesh_study_keeps_the_frame_axis_rederivation() -> None:
    # Lifting the frame axis to the frame slack lands on the casting's crank
    # axis at the engaged centre distance the assembly asserts.
    x_frame, y_frame = crossed.frame_axis(drive.MESH16_C2C_SLACK)
    assert x_frame == drive.X_CRANK
    assert y_frame == pytest.approx(drive.Y_CRANK, abs=0.05)
    assert crossed.pose((x_frame, y_frame))["c2c"] == pytest.approx(
        drive.MESH16_C2C, abs=1e-9
    )


def test_the_frame_axis_seed_is_not_the_shipped_seed() -> None:
    # Positive control: the pre-R1 study pose, the frame crank axis, reads a
    # seed the assembly no longer ships.
    frame = crossed.pose((drive.X_CRANK, drive.Y_CRANK), drive.MESH_WINDOW_CENTRE_DEG)
    assert abs(frame["seed"] - drive.PINION_SEED_DEG) > 1e-3


# --- The 64T against MHA-016's north side (crank_boss_rim) --------------------
# cg-fx2b's drive-train interference gate found the 64T's tip in the crank
# boss at the harvested spot-face station; the user ruled the face retreated
# 2.5 and run out as a flat.  The build asserts only the 0.25 floor; the
# minimality below records the derivation at ruling time, under U31's +/-0.5
# station band (#916's collar stack will widen every margin, not move sizes).


def _spot_face_sizes() -> tuple[float, float, float]:
    return (
        post.CRANK_SPOT_FACE_RETREAT,
        post.CRANK_SPOT_FACE_WIDTH,
        post.CRANK_SPOT_FACE_RUN_OUT,
    )


def test_the_harvested_spot_face_is_the_gate_s_clash() -> None:
    """Positive control: at the harvested station, with no run-out, the
    nominal 64T already reaches into the boss -- the overlap cg-fx2b's gate
    read -- and at print-worst into the collar too."""
    harvested = crank_boss_rim.SpotFace(post.CRANK_BOSS_HARVESTED_NORTH_FACE)
    nominal = crank_boss_rim.clearances(
        gear_offset=drive.GEAR64_POST_OFFSET, spot=harvested, worst=False
    )
    assert -0.25 < nominal["crank boss"] < 0.0
    worst = crank_boss_rim.worst_shortfalls(drive.GEAR64_POST_OFFSET, harvested)
    assert {"crank boss", "collar"} <= set(worst)


def test_the_floor_is_the_assembly_s_running_gap() -> None:
    """Cited, not invented: the 16T's seat feeler MHA-A03 step 4 sets, and it
    is taken with the 64T's station band counted."""
    assert crank_boss_rim.FLOOR_CLEARANCE_MM is pinion.SEAT_FEELER_MM
    assert crank_boss_rim.GEAR64_STATION_TOWARD_POST is post.GEAR64_STATION_BAND_MM


def test_the_printed_spot_face_holds_the_floor_on_all_five_surfaces() -> None:
    spot = crank_boss_rim.spot_face(*_spot_face_sizes())
    assert crank_boss_rim.worst_shortfalls(drive.GEAR64_POST_OFFSET, spot) == {}
    worst = crank_boss_rim.clearances(gear_offset=drive.GEAR64_POST_OFFSET, spot=spot)
    assert set(worst) == {"crank boss", "MHA-149 north end", "collar", "body", "cone boss end"}
    assert min(worst.values()) >= crank_boss_rim.FLOOR_CLEARANCE_MM
    # The untouched cone-boss end governs; the run-out holds the collar next.
    assert min(worst, key=worst.get) == "cone boss end"


@pytest.mark.parametrize(
    ("size", "short_by_more_than"),
    [
        ("retreat", 0.25 - 0.15),  # 2.0: collar +0.142
        ("width", 0.25 - 0.24),  # 22: collar +0.231
        ("run-out", 0.25 + 0.47),  # 16: collar -0.48
    ],
)
def test_each_size_a_step_smaller_misses_the_floor_under_today_s_band(
    size: str, short_by_more_than: float
) -> None:
    """Fail-first, at ruling time: under U31's +/-0.5 station band each size
    a step smaller leaves the collar under the floor, and only the collar."""
    assert crank_boss_rim.GEAR64_STATION_TOWARD_POST == 0.5
    smaller = crank_boss_rim.one_step_short(*_spot_face_sizes())[size]
    short = crank_boss_rim.worst_shortfalls(drive.GEAR64_POST_OFFSET, smaller)
    assert set(short) == {"collar"}
    assert short["collar"] > short_by_more_than
    assert _spot_face_sizes() == (2.5, 23.0, 17.0)


def test_the_build_asserts_the_floor_and_not_minimality() -> None:
    """Minimality in the build would move eye-passed geometry once #916's
    collar narrows the station band; only the floor belongs there."""
    source = Path(drive.__file__).read_text(encoding="utf-8")
    assert "crank_boss_rim.worst_shortfalls(" in source
    assert "one_step_short" not in source


def test_the_nominal_clearances_the_solidworks_cross_check_reads() -> None:
    """The analytic nominal the drive-train leaf's measured minimum distance is
    compared against (gear64_post_measure)."""
    spot = crank_boss_rim.spot_face(*_spot_face_sizes())
    nominal = crank_boss_rim.clearances(
        gear_offset=drive.GEAR64_POST_OFFSET, spot=spot, worst=False
    )
    assert nominal["crank boss"] == pytest.approx(2.377, abs=2e-3)
    assert min(nominal["collar"], nominal["body"], nominal["cone boss end"]) == pytest.approx(
        1.681, abs=2e-3
    )


def test_every_print_worst_term_reads_its_print() -> None:
    assert crank_boss_rim.SPOT_FACE_NORTH == 0.51  # CrankBossStartZ at .XX
    assert crank_boss_rim.GEAR_FACE_GROWTH == 0.4  # FaceWidth at .X, per side
    assert crank_boss_rim.GEAR_TIP_GROWTH == gear64.OUTSIDE_DIA_TOLERANCE_MM / 2.0
    assert crank_boss_rim.COLLAR_GROWTH == crank_boss_rim.BODY_GROWTH == 0.4
    assert crank_boss_rim.SPOT_FACE_WIDTH_SHORT == 0.8
    assert crank_boss_rim.BUSHING_RADIUS_MAX == (bushing.OUTER_DIA + bushing.OD_BAND[0]) / 2.0


def _measured(monkeypatch: pytest.MonkeyPatch, near_post_frame: tuple[float, float, float], distance_mm: float) -> dict:
    """Run gear64_post_measure against a fake ClosestDistance (makepy's
    convention: retval first, then the two [out] points, in metres)."""
    origin = tuple(drive._PPOST)
    post_point = tuple((c + o) / 1000.0 for c, o in zip(near_post_frame, origin, strict=True))

    class Model:
        def ClosestDistance(self, a, b):
            return (distance_mm / 1000.0, (0.0, 0.0, 0.0), post_point)

        def GetComponentByName(self, name):
            return name

    monkeypatch.setattr(gear64_post_measure, "_early_bound", lambda obj, iface: Model())
    return gear64_post_measure.measure(
        SimpleNamespace(currentModel=object()),
        post_origin=origin,
        gear_offset=drive.GEAR64_POST_OFFSET,
    )


def test_the_solidworks_cross_check_names_the_feature_it_lands_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    face = post.CRANK_BOSS_NORTH_FACE
    on_face = (3.0, crank_boss_rim.CRANK_AXIS_Y - 5.0, face)
    record = _measured(monkeypatch, on_face, 2.40)
    assert record["measured_feature"] == "crank boss"
    assert record["predicted_feature"] == "cone boss end"
    assert record["predicted_mm"] == pytest.approx(1.681, abs=2e-3)


def test_the_solidworks_cross_check_fails_when_the_gear_is_nearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured nearer than the envelope predicts: the analytic model misses
    material, so the build stops."""
    end = post.CONE_BOSS_LENGTH / 2.0
    on_pad = (end * crank_boss_rim.SIN_I, 0.0, end * crank_boss_rim.COS_I)
    assert gear64_post_measure.post_feature_at(on_pad, post.CRANK_BOSS_NORTH_FACE) == "cone boss end"
    with pytest.raises(RuntimeError, match="misses real material"):
        _measured(monkeypatch, on_pad, 1.681 - 0.2)
    assert _measured(monkeypatch, on_pad, 1.70)["delta_mm"] == pytest.approx(0.019, abs=2e-3)


def test_the_solidworks_cross_check_is_a_span_carrying_its_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The leaf's trace answers the cross-check without its console log."""
    spans: dict[str, dict] = {}

    @contextmanager
    def span(name: str, **attributes):
        recorded = spans.setdefault(name, dict(attributes))
        yield SimpleNamespace(set_attribute=recorded.__setitem__)

    monkeypatch.setattr(gear64_post_measure._telemetry, "span", span)
    on_face = (3.0, crank_boss_rim.CRANK_AXIS_Y - 5.0, post.CRANK_BOSS_NORTH_FACE)
    record = _measured(monkeypatch, on_face, 2.40)
    attributes = spans["verify.gear64_post_distance"]
    for key in ("measured_mm", "measured_feature", "predicted_mm", "predicted_feature", "delta_mm"):
        assert attributes[f"gear64_post.{key}"] == record[key]

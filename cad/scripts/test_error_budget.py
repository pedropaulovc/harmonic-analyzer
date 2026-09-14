"""check:budget -- the coefficient-error budget closes and stays tied to the CAD.

Pins the CONTRACT of cad/config/error_budget.yaml + error_budget.py rather than
its arithmetic: the linear sensitivities agree with the exact kinematics, the
readout procedure really cancels common-mode error, the second-harmonic
correction really removes the nominal-design residual, every toleranced nominal
still resolves to the spec constant the CAD builds from, the drawing limits
match the budget, and the Monte Carlo lands inside the targets. SolidWorks-free.
"""

from __future__ import annotations

import dataclasses
import importlib
import pathlib
import re
import math

import numpy as np
import pytest

import error_budget as eb

NOMINAL_FIELD = {
    "cam_eccentricity": "ecc",
    "rocker_rod_pin_radius": "pin_x",
    "lever_bar_pin_arm": "bar_pin_arm",
    "lever_spring_hook_arm": "hook_arm",
    "summing_hook_arm": "sum_hole_x",
    "spring_rate": "spring_rate",
    "spring_initial_tension": "spring_initial_tension",
}


@pytest.fixture(scope="module")
def budget():
    """The allocation config under test."""
    return eb.load_budget()


@pytest.fixture(scope="module")
def nom(budget):
    """The machine the report credits: the spec modules' inputs with the cam
    lobe vertical at crank home (the as-built 1.5 deg is waived, #749)."""
    return eb.credited_nominal(budget)


@pytest.fixture(scope="module")
def report(budget):
    """One full model run, shared across the module."""
    return eb.build_report(budget)


def negative(budget: dict, **reserved: dict) -> dict:
    """A deliberately-broken budget for a failure-routing test, at a REDUCED
    draw count: these tests assert WHICH gate trips, not the value, and a full
    4000-draw report each would multiply the required check:budget gate's
    runtime by the number of negative cases."""
    out = {
        **budget,
        "monte_carlo": {**budget["monte_carlo"], "draws": 500},
    }
    if reserved:
        out["reserved"] = {
            k: {**budget["reserved"][k], **reserved.get(k, {})}
            for k in budget["reserved"]
        }
    return out


def _resolve(dotted: str) -> float:
    """``module.ATTR`` -> its value, for the yaml's ``nominal`` references."""
    module, attr = dotted.rsplit(".", 1)
    return float(getattr(importlib.import_module(module), attr))


def test_every_toleranced_nominal_is_the_cad_constant(budget, nom):
    """A feature's `nominal` must be the spec symbol the build reads -- the
    budget cannot silently drift from the geometry it tolerances."""
    for key, feat in budget["critical_features"].items():
        if feat["nominal"] is None:
            assert key in ("cam_phase", "mesh_lag_spread", "station_setting"), key
            continue
        assert key in NOMINAL_FIELD, f"{key}: no Nominal field mapped"
        assert _resolve(feat["nominal"]) == pytest.approx(
            getattr(nom, NOMINAL_FIELD[key])
        )


def test_analytic_gain_sensitivities_match_exact_kinematics(report):
    """The closed-form (small-angle) gain sensitivities agree with central
    differences of the exact fundamental amplitude to within the mechanism's
    own gain curvature (~3 % across the range in the machine-hand geometry)."""
    for key, (analytic, numeric) in report["finite_difference_check"].items():
        assert numeric == pytest.approx(analytic, rel=0.035), key


def test_calibrated_readout_cancels_common_spring_force_scaling(nom):
    """Scaling every channel's rate and initial tension together scales its
    loaded lift response uniformly, which the trial's k=0 calibration removes."""
    fraction = 0.01
    response = eb.spring_force_model.channel_response(
        nom.sum_hole_x, nom.spring_rate, nom.spring_initial_tension
    )
    scaled_response = eb.spring_force_model.channel_response(
        nom.sum_hole_x,
        nom.spring_rate * (1.0 + fraction),
        nom.spring_initial_tension * (1.0 + fraction),
    )
    assert scaled_response.lift_torque_n == pytest.approx(
        response.lift_torque_n * (1.0 + fraction), rel=1e-12
    )

    sens = eb.gain_sensitivities(nom)
    rate_change_pct = 100.0 * fraction
    initial_tension_change_n = nom.spring_initial_tension * fraction
    assert (
        sens["spring_rate"] * rate_change_pct
        + sens["spring_initial_tension"] * initial_tension_change_n
    ) == pytest.approx(100.0 * fraction, rel=1e-12)

    x = eb.reference_inputs()["gaussian_a0p1"]
    dev = {
        "spring_rate": np.full((1, eb.N_ELEMENTS), rate_change_pct),
        "spring_initial_tension": np.full((1, eb.N_ELEMENTS), initial_tension_change_n),
    }
    error = eb._channel_model(x, nom, dev, sens)
    assert np.max(np.abs(error)) < 1e-9


def test_loaded_anchor_geometry_sets_pen_gain_and_hole_sensitivity(nom):
    """Independent force-distance finite differences include initial-tension
    stiffness and distinguish the manufactured hole X from the loaded arm."""
    import channel_kinematics
    import channel_spring_stock_geom as channel_stock
    import counter_spring_stock_geom as counter_stock
    import spring_mount_geom as mounts

    knife = (mounts.KNIFE[0], mounts.KNIFE_CONTACT_Y)
    channel_hook = channel_kinematics.spring_hole_xy(0.0)
    channel_lower_offset = math.dist(
        mounts.CHANNEL_ANCHOR_XY, mounts.CHANNEL_NOMINAL_POSE.lower_eye_xy
    )
    channel_upper_offset = math.dist(
        channel_hook, mounts.CHANNEL_NOMINAL_POSE.upper_eye_xy
    )
    counter_pose = mounts.COUNTER_REFERENCE_POSE
    counter_lower_offset = math.dist(
        mounts.COUNTER_ANCHOR_XY, counter_pose.lower_eye_xy
    )
    screw_y = counter_pose.upper_eye_xy[1] + mounts.counter_upper_support_offset(
        counter_pose.axis_xy
    )

    def rotate_anchor(point, angle):
        x, y = point[0] - knife[0], point[1] - knife[1]
        return (
            knife[0] + x * math.cos(angle) - y * math.sin(angle),
            knife[1] + x * math.sin(angle) + y * math.cos(angle),
        )

    def channel_torque(*, angle=0.0, lift=0.0, hole_dx=0.0):
        anchor = rotate_anchor(
            (mounts.CHANNEL_ANCHOR_XY[0] + hole_dx, mounts.CHANNEL_ANCHOR_XY[1]),
            angle,
        )
        hook = (channel_hook[0], channel_hook[1] + lift)
        dx, dy = hook[0] - anchor[0], hook[1] - anchor[1]
        span = math.hypot(dx, dy)
        ux, uy = dx / span, dy / span
        length = (
            span
            - channel_lower_offset
            - channel_upper_offset
            + channel_stock.COIL_ID_MM
        )
        force = nom.spring_initial_tension + nom.spring_rate * (
            length - channel_stock.FREE_LENGTH_MM
        )
        arm = (anchor[0] - knife[0]) * uy - (anchor[1] - knife[1]) * ux
        return force * arm

    def counter_torque(angle):
        anchor = rotate_anchor(mounts.COUNTER_ANCHOR_XY, angle)
        hook_x = mounts.COUNTER_UPPER_EYE_X
        hook_y = counter_pose.upper_eye_xy[1]
        for _ in range(12):
            dx, dy = hook_x - anchor[0], hook_y - anchor[1]
            span = math.hypot(dx, dy)
            axis = (dx / span, dy / span)
            hook_y = screw_y - mounts.counter_upper_support_offset(axis)
        dx, dy = hook_x - anchor[0], hook_y - anchor[1]
        span = math.hypot(dx, dy)
        ux, uy = dx / span, dy / span
        length = span - counter_lower_offset + counter_stock.EYE_ID_MM
        force = nom.counter_initial_tension + nom.counter_rate * (
            length - counter_stock.FREE_LENGTH_MM
        )
        arm = (anchor[0] - knife[0]) * uy - (anchor[1] - knife[1]) * ux
        return force * arm

    angle_step = 1e-5
    channel_stiffness = -(
        channel_torque(angle=angle_step) - channel_torque(angle=-angle_step)
    ) / (2.0 * angle_step)
    counter_stiffness = -(counter_torque(angle_step) - counter_torque(-angle_step)) / (
        2.0 * angle_step
    )
    total_stiffness = eb.N_ELEMENTS * channel_stiffness + counter_stiffness

    lift_step = 1e-5

    def lift_torque_gain(hole_dx=0.0):
        return (
            channel_torque(lift=lift_step, hole_dx=hole_dx)
            - channel_torque(lift=-lift_step, hole_dx=hole_dx)
        ) / (2.0 * lift_step)

    expected_gain_per_lever_mm = lift_torque_gain() / total_stiffness
    actual_gain_per_lever_mm = eb.pen_gain(nom, nom.lever_r_built) / (
        nom.lever_r_built * nom.wheel_ratio
    )
    assert actual_gain_per_lever_mm == pytest.approx(
        expected_gain_per_lever_mm, rel=2e-6
    )

    hole_step = 1e-3
    expected_hole_sensitivity = (
        100.0
        * (lift_torque_gain(hole_step) - lift_torque_gain(-hole_step))
        / (2.0 * hole_step)
        / lift_torque_gain()
    )
    assert eb.gain_sensitivities(nom)["summing_hook_arm"] == pytest.approx(
        expected_hole_sensitivity, rel=2e-5
    )


def test_second_harmonic_correction_removes_the_nominal_residual(report):
    """The slider-crank distortion is the largest nominal term (>1 % of a
    channel's amplitude) and the readout correction takes the broad-input
    residual below 0.05 % MAE -- the claim tolerance-policy.md rests on."""
    h = report["harmonics"]["+88"]
    assert 0.010 < h["c2"] / h["c1"] < 0.020
    nde = report["nominal_design_errors"]
    for name in ("all_ones", "rect_half", "gaussian_a0p1"):
        assert nde["uncorrected"][name]["max"] > 1.0
        assert nde["calibrated_stick_and_c2_corrected"][name]["mae"] < 0.05
        assert nde["calibrated_stick_and_c2_corrected"][name]["max"] < 0.12


def test_null_station_is_unreachable_and_handled_as_a_lift(report, nom):
    """The notch-roof contact sits contact_dx off the foot axis and the slide arc
    above the pivot centreline, so a bar at the pivot zero still moves; the null
    station lies below the pivot zero, on the side the CAD cannot build, so it
    is handled as a known common lift on every channel, never as a negative
    station."""
    d0 = report["null_station_mm"]
    assert -nom.contact_dx - 1.0 < d0 < 0.0
    assert report["null_lift_ordinate"] == pytest.approx(-d0 / nom.d_max)
    # the lift alone (no c2 correction) removes the idle-bar error on the pair input
    nde = report["nominal_design_errors"]
    assert nde["uncorrected"]["pair_1_20"]["max"] > 5.0
    assert nde["null_lift_corrected"]["pair_1_20"]["max"] < 4.0
    assert (
        abs(eb.harmonic_content(d0, nom)["c1"]) < 1e-3 * eb.linear_gain(nom) * nom.d_max
    )


def test_budget_closes(report):
    """The Monte Carlo lands inside its targets, every reserved term inside its
    allowance, the total inside the benchmark MAE, and the two-channel worst
    coefficient inside its own benchmark."""
    assert eb.budget_closes(report) == []
    assert set(report["closure"]) == {
        "nominal_residual_mae",
        "scatter_mae",
        "readout",
        "timebase",
        "knife",
        "total_mae",
        "nominal_residual_mae_as_built",
        "total_mae_as_built",
        "pair_worst",
        "pair_terms",
    }


def test_closure_fails_when_a_reserved_term_overruns(budget):
    """A reading uncertainty the CAD's pen stroke cannot carry must fail the
    gate through the readout allowance, not pass on scatter alone."""
    coarse = negative(budget, readout={"reading_uncertainty_mm": 0.3})
    bad = eb.budget_closes(eb.build_report(coarse))
    assert any(b.startswith("readout") for b in bad), bad


def test_sparse_pair_is_gated_on_the_jointly_drawn_worst_coefficient(budget, report):
    """The two-channel trial's 2 % criterion is a worst COEFFICIENT of one
    machine, so the model draws every source JOINTLY (scatter, both reads of
    each coefficient, the stall at each read, the crank index) on top of the
    machine's residual and gates the EXPECTED max over k -- the statistic the
    benchmark actually is. The quantiles and the fraction of machines over the
    benchmark are reported, and the RSS of each source's own worst coefficient
    is kept beside it as the conservative (double-counting) envelope."""
    cl = report["closure"]
    pt = cl["pair_terms"]
    pj = report["pair_joint"]
    assert (
        pt["knife"] > cl["knife"]
    )  # the pair pays more for the stall than any broad input
    assert cl["pair_worst"] == pj["expected_worst_coefficient"]
    assert cl["pair_worst"] < budget["targets"]["pair_consistency_max_fs_pct"]
    assert not any(b.startswith("pair") for b in eb.budget_closes(report))
    # every source contributes, none dominates to the point of hiding another
    assert set(pj["expected_worst_per_source"]) == {
        "scatter",
        "reading",
        "stall",
        "index",
    }
    assert min(pj["expected_worst_per_source"].values()) > 0.0
    # a percentile of an ensemble is NOT the benchmark's statistic: the p99 is
    # above the expected max, and the exceedance fraction is published rather
    # than the gate silently passing on a mixed comparison
    q = pj["quantiles"]
    assert q["p50"] < q["p90"] < q["p99"]
    assert q["p99"] > pj["expected_worst_coefficient"]
    assert 0.0 < pj["fraction_over_benchmark_max"] < 0.5
    assert pj["benchmark_max_fs_pct"] == report["benchmark"]["max_fs_pct"]
    # the envelope is the RSS of per-source worsts on top of the residual, and
    # it is conservative relative to the joint draw's own p90
    assert pt["envelope_rss_of_worst"] == pytest.approx(
        pt["nominal_residual_max"]
        + math.sqrt(
            pt["scatter_p99"] ** 2
            + pt["readout_worst_coefficient"] ** 2
            + pt["timebase"] ** 2
            + pt["knife"] ** 2
        )
    )
    assert pt["envelope_rss_of_worst"] > q["p90"]
    # the readout's reported worst coefficient is a real absolute bound
    # (delta(1 + |a_k|)), not an RSS of half-widths
    cf = report["closed_form"]["readout"]
    a = max(abs(v) for v in cf["normaliser_share_per_input"]["pair_1_20"][1:])
    assert pt["readout_worst_coefficient"] == pytest.approx(
        cf["one_reading_pct_fs_per_input"]["pair_1_20"] * (1.0 + a)
    )
    # and a duller knife still fails the pair gate
    sticky = negative(
        budget,
        knife={
            "rolling_resistance_mm": 3
            * budget["reserved"]["knife"]["rolling_resistance_mm"]
        },
    )
    bad = eb.budget_closes(eb.build_report(sticky))
    assert any(b.startswith("pair expected worst coefficient") for b in bad), bad


def test_magnifier_setup_fits_reference_inputs_to_reachable_stroke(report, nom):
    """Each reference input uses a reachable lever radius without exceeding the
    physical pen stroke. Broad inputs scale down at the minimum radius; the
    sparse pair stays full scale at the built-radius limit."""
    assert nom.lever_r_min < nom.lever_r_built <= nom.lever_r_max
    mag = report["closed_form"]["magnifier"]
    assert mag["ordinate_capacity_full_scale_bars"] > 0.0
    for name, setup in mag["per_input"].items():
        assert setup["k0_reading_mm"] == pytest.approx(
            nom.pen_half * setup["stroke_fill"], rel=1e-6
        )
        assert 0.0 < setup["stroke_fill"] <= 1.0
        assert nom.lever_r_min <= setup["lever_r"] <= nom.lever_r_built
        if name == "pair_1_20":
            assert setup["ordinate_scale"] == 1.0
            assert setup["lever_r"] == nom.lever_r_built
            assert setup["k0_reading_mm"] < nom.pen_half
        else:
            assert 0.0 < setup["ordinate_scale"] < 1.0
            assert setup["lever_r"] == nom.lever_r_min

    trial = eb.NominalTrial(nom)
    for name, setup in mag["per_input"].items():
        x = eb.reference_inputs()[name]
        stations = setup["ordinate_scale"] * x * nom.d_max
        physical_peak = eb.pen_gain(nom, setup["lever_r"]) * trial.k0_hook_mm(stations)
        assert physical_peak == pytest.approx(setup["k0_reading_mm"], rel=1e-3)
        assert trial.peak_bars(stations) == pytest.approx(
            trial.k0_hook_mm(stations) / abs(trial.f_full), rel=1e-3
        )


def test_scale_rule_solves_the_table_instead_of_scaling_by_proportion(report, nom):
    """The fitted scale is the greatest table scale that stays within capacity.
    A proportional estimate ignores the fixed idle-bar lift and overdrives the
    stroke."""
    cap = report["closed_form"]["magnifier"]["ordinate_capacity_full_scale_bars"]
    trial = eb.NominalTrial(nom)
    for name, setup in report["closed_form"]["magnifier"]["per_input"].items():
        x = eb.reference_inputs()[name]
        solved = trial.ordinate_scale_for(x, cap)
        assert solved == pytest.approx(setup["ordinate_scale"], abs=1e-9)
        if solved < 1.0:
            assert trial.peak_bars(solved * x * nom.d_max) == pytest.approx(
                cap, rel=1e-6
            )
            assert trial.peak_bars(min(1.0, 1.001 * solved) * x * nom.d_max) > cap

    ones = np.ones(eb.N_ELEMENTS)
    solved = trial.ordinate_scale_for(ones, cap)
    proportional = cap / trial.peak_bars(ones * nom.d_max)
    assert proportional > solved
    assert trial.peak_bars(proportional * ones * nom.d_max) > cap


def test_reduced_ordinate_scale_costs_setting_and_knife_proportionally(report, nom):
    """A fixed setting error and each case's fixed knife stall grow in ordinate
    units when the pen forces that input to a smaller physical station scale."""
    cf = report["closed_form"]
    mag, knife = cf["magnifier"], cf["knife"]
    cap = mag["ordinate_capacity_full_scale_bars"]
    trial = eb.NominalTrial(nom)
    for name, s in mag["per_input"].items():
        if s["ordinate_scale"] < 1.0:
            x = eb.reference_inputs()[name]
            read_sum = float(np.sum(trial.x_read(s["ordinate_scale"] * x * nom.d_max)))
            assert s["ordinate_scale"] * float(np.sum(x)) < read_sum
            assert read_sum == pytest.approx(cap, rel=0.03)  # C_2 rides the k=0 peak
            assert knife["pct_fs_per_input"][name] == pytest.approx(
                knife["stall_pct_of_one_channel_fs_per_input"][name]
                / (s["ordinate_scale"] * float(np.sum(x)))
            )
    # bars at 0.5 (interior: no one-sided fold at either end of the scale)
    x = np.full(eb.N_ELEMENTS, 0.5)
    sens = eb.gain_sensitivities(nom)
    rng = np.random.default_rng(1)
    dev = {"station_setting": rng.uniform(-0.25, 0.25, size=(400, eb.N_ELEMENTS))}
    full = eb._channel_model(x, nom, dev, sens, 0.25, 1.0)
    f = mag["per_input"]["all_ones"]["ordinate_scale"]
    capped = eb._channel_model(x, nom, dev, sens, 0.25, f)
    assert np.mean(np.abs(capped)) / np.mean(np.abs(full)) == pytest.approx(
        1.0 / f, rel=0.1
    )


def test_knife_load_cases_include_configured_and_scaled_reference_vectors(
    budget, report, nom
):
    """Every physical preload case is explicit and each scored stall uses its
    own station-dependent spring-bank load over the neutral transfer scale."""
    import spring_mount_geom as mounts

    knife = report["closed_form"]["knife"]
    cases = knife["load_cases"]

    inputs = eb.reference_inputs()
    loads = []
    for name in budget["reference_inputs"]:
        setup = report["closed_form"]["magnifier"]["per_input"][name]
        stations = setup["ordinate_scale"] * inputs[name] * nom.d_max
        case = cases[name]
        poses = [mounts.channel_pose(float(station)) for station in stations]
        forces = [
            nom.spring_initial_tension
            + nom.spring_rate
            * (pose.length_mm - eb.channel_spring_installed_spec.FREE_LENGTH_MM)
            for pose in poses
        ]
        assert case["channel_moment_N_mm"] == pytest.approx(
            sum(force * pose.moment_arm_mm for force, pose in zip(forces, poses))
        )
        assert case["conservative_knife_load_N"] >= case["knife_vertical_load_N"]
        loads.append(case["conservative_knife_load_N"])
        expected_stall = (
            100.0
            * case["conservative_knife_load_N"]
            * knife["assumed_rolling_resistance_mm"]
            / (
                knife["neutral_small_signal_lift_torque_N"]
                * knife["neutral_small_signal_hook_displacement_mm"]
            )
        )
        assert knife["stall_pct_of_one_channel_fs_per_input"][name] == pytest.approx(
            expected_stall
        )

    assert len(set(round(load_n, 9) for load_n in loads)) > 1
    assert knife["worst_required_counter_case"] == max(
        cases, key=lambda name: cases[name]["channel_moment_N_mm"]
    )


def test_lift_vector_is_what_the_procedure_subtracts():
    """A common lift l reads 20*l at k=0 and -l at every ODD k under the machine's
    own 20-element rule -- the vector the policy tells the operator to subtract.
    A k=0-only correction would leave l at every odd coefficient."""
    lift = 0.041
    lv = eb.ideal_coefficients(np.full(eb.N_ELEMENTS, lift))
    assert lv[0] == pytest.approx(eb.N_ELEMENTS * lift)
    assert np.allclose(lv[1::2], -lift)
    assert np.allclose(lv[2::2], 0.0, atol=1e-12)


def test_station_setting_scatter_never_goes_below_the_pivot(nom):
    """Setting error at a zero ordinate is one-sided (a bar cannot be set below
    the pivot): the symmetric draw is folded onto [0, +tol], so a draw at -tol
    reads exactly like one at +tol; at full scale it folds the other way onto
    [-tol, 0]. Each band's mean (+tol/2 at zero, -tol/2 at full) is the known
    lift the operator subtracts, so THAT draw reads as error-free."""
    x = eb.reference_inputs()["pair_1_20"]
    sens = eb.gain_sensitivities(nom)
    tol = 0.25
    idle = (x == 0.0)[None, :]
    full = (x == 1.0)[None, :]

    def read(offset: np.ndarray) -> np.ndarray:
        dev = {"station_setting": np.broadcast_to(offset, (1, eb.N_ELEMENTS))}
        return eb._channel_model(x, nom, dev, sens, tol)[0]

    zero = np.zeros((1, eb.N_ELEMENTS))
    assert np.allclose(
        read(np.where(idle, -tol, 0.0)), read(np.where(idle, tol, 0.0)), atol=1e-12
    )
    assert np.allclose(
        read(np.where(full, tol, 0.0)), read(np.where(full, -tol, 0.0)), atol=1e-12
    )
    mean = np.where(idle, tol / 2.0, 0.0) - np.where(full, tol / 2.0, 0.0)
    # each band's mean is the known lift: ordinate AND kappa from that row, so
    # only the 3rd harmonic and the table interpolation are left (< 0.005 % FS)
    assert np.max(np.abs(read(mean))) < 5e-3
    assert np.max(np.abs(read(zero))) > 0.5  # the residual scatter is real, at odd k


def test_counter_spring_catalog_range_gates_every_station_case(
    budget, report, nom, monkeypatch
):
    """A counter capacity between neutral and a high configured bank must fail.

    The former neutral*20 gate passed this boundary; the physical station gate
    rejects the configured case instead of extrapolating a counter pose beyond
    the catalog range.
    """
    import counter_spring_stock_geom as counter_stock
    import spring_mount_geom as mounts

    neutral_stations = np.zeros(eb.N_ELEMENTS)
    loaded_stations = np.full(eb.N_ELEMENTS, nom.d_max)
    neutral = mounts.solve_bank_balance(
        neutral_stations,
        channel_rate_n_per_mm=nom.spring_rate,
        channel_initial_tension_n=nom.spring_initial_tension,
        counter_rate_n_per_mm=nom.counter_rate,
        counter_initial_tension_n=nom.counter_initial_tension,
    )
    loaded = mounts.solve_bank_balance(
        loaded_stations,
        channel_rate_n_per_mm=nom.spring_rate,
        channel_initial_tension_n=nom.spring_initial_tension,
        counter_rate_n_per_mm=nom.counter_rate,
        counter_initial_tension_n=nom.counter_initial_tension,
    )
    assert loaded.channel_moment_n_mm > neutral.channel_moment_n_mm

    max_pose = mounts.counter_pose(counter_stock.MAX_LENGTH_MM)
    boundary_moment = (neutral.channel_moment_n_mm + loaded.channel_moment_n_mm) / 2.0
    boundary_force = boundary_moment / -max_pose.moment_arm_mm
    boundary_rate = (boundary_force - nom.counter_initial_tension) / (
        counter_stock.MAX_LENGTH_MM - counter_stock.FREE_LENGTH_MM
    )
    boundary_nom = dataclasses.replace(nom, counter_rate=boundary_rate)

    old_neutral_force = (
        eb.N_ELEMENTS
        * mounts.channel_force_n(mounts.channel_pose(0.0).length_mm)
        * mounts.channel_pose(0.0).moment_arm_mm
        / -mounts.COUNTER_REFERENCE_POSE.moment_arm_mm
    )
    old_available_force = min(
        mounts.COUNTER_MAXIMUM_LOAD_N,
        nom.counter_initial_tension
        + boundary_rate * (counter_stock.MAX_LENGTH_MM - counter_stock.FREE_LENGTH_MM),
    )
    assert nom.counter_initial_tension <= old_neutral_force <= old_available_force

    monkeypatch.setattr(eb._config, "amplitudes", lambda: loaded_stations.tolist())
    trial = eb.NominalTrial(boundary_nom)
    setups = {
        name: trial.magnifier_setup(eb.reference_inputs()[name])
        for name in budget["reference_inputs"]
    }
    closed_form = eb.closed_form_terms(boundary_nom, budget, setups)
    knife = closed_form["knife"]
    assert knife["load_cases"]["configured_cad"]["static_balance"] is False
    assert (
        knife["load_cases"]["configured_cad"]["counter_setting_inside_length_mm"]
        is None
    )
    assert knife["static_balance"] is False
    assert "configured_cad" in knife["unbalanced_cases"]

    failed_report = {**report, "closed_form": closed_form}
    bad = eb.budget_closes(failed_report)
    assert any("configured_cad" in failure for failure in bad), bad


def test_cam_home_phase_is_scored_as_built_and_fails_unless_waived(budget, report, nom):
    """The CAD locks every cylinder gear half a tooth pitch off vertical
    (tooth-in-gap), so at crank home every cam lobe -- a tooth crest -- sits
    1.5 deg off: a COMMON cam phase (channel i turns i x faster, so no crank
    index zeroes all 20) whose error h * sum x_i sin(i theta_k) no procedure
    step removes. The model reads it from the CAD (cam_home_deg), the as-built
    fundamental carries that phase while the lobe-up machine's does not, the
    residual it leaves is ~6x the allowance and the as-built total misses the
    benchmark, and the gate fails on it unless the yaml records the waiver
    (#749)."""
    import channel_frame_geom

    as_built = eb.nominal()
    assert as_built.cam_home_deg == channel_frame_geom.CYLINDER_LOCK_PHASE_DEG == 1.5
    assert nom == dataclasses.replace(as_built, cam_home_deg=0.0)
    th = np.arange(360) * 2.0 * math.pi / 360

    def phase_deg(n):
        u = eb.hook_displacement(th, n.d_max, n)
        c1, s1 = 2 * np.mean(u * np.cos(th)), 2 * np.mean(u * np.sin(th))
        return math.degrees(math.atan2(-s1, -c1))  # the hook reads -cos (crank side)

    assert phase_deg(as_built) == pytest.approx(1.5, abs=0.02)
    assert abs(phase_deg(nom)) < 0.02
    # the analytic size of the leak: h * sum x sin(i theta_k) on all-ones
    x = eb.reference_inputs()["all_ones"]
    leak = math.radians(1.5) * (np.sin(np.outer(eb.THETA_K, eb.HARMONICS)) @ x)
    home = report["cam_home_phase"]
    assert home["residual_as_built"]["all_ones"]["max"] == pytest.approx(
        100.0 * np.max(np.abs(leak)) / eb.N_ELEMENTS, rel=0.1
    )
    cl = report["closure"]
    assert (
        cl["nominal_residual_mae_as_built"]
        > 5 * report["reserved_allowance"]["nominal_residual_mae"]
    )
    assert cl["total_mae_as_built"] > report["benchmark"]["mae_fs_pct"]
    assert (
        cl["nominal_residual_mae"]
        < report["reserved_allowance"]["nominal_residual_mae"]
    )
    strict = negative(budget, nominal_residual_mae={"waive_cam_home_phase": False})
    bad = eb.budget_closes(eb.build_report(strict))
    assert any(b.startswith("cam home phase") for b in bad), bad
    # the shipped procedure says so, with the as-built numbers
    doc = eb.readout_procedure(report)
    assert "**As built, this CAD does not reach that residual.**" in doc
    assert f"{cl['total_mae_as_built']:.2f} % against" in doc
    assert "#749" in doc
    assert "note 5" not in doc  # the stick drawing has four notes
    # and it is rendered from the report's OWN machine (the credited one),
    # never a separately constructed Nominal: a report on a different machine
    # renders a different document (the tables are phase-invariant to 1e-5,
    # so the check is on the model identity the header prints)
    assert report["nominal"]["cam_home_deg"] == 0.0
    assert "cam home phase 0 deg" not in doc  # the header names the as-built 1.5
    shifted = {**report, "nominal": {**report["nominal"], "d_max": 79.3}}
    assert "|   79.3 |" in eb.readout_procedure(shifted)
    assert "|   79.3 |" not in doc


def test_cam_shaft_axis_is_fixed_by_the_frame_not_the_part(nom):
    """A cam or rod-pin deviation moves the part; the shaft axis stays where
    the frame holds it (CAD: X_DRUM / Y_DRIVE), so the rocker settles at a
    different rest angle instead of the axis following the part (Codex round
    28). As designed the rod hangs plumb onto the phased home centre, so the
    nominal rocker is level at home."""
    import channel_frame_geom

    assert (nom.axis_dx, nom.axis_dy) == pytest.approx(
        tuple(
            c - p
            for c, p in zip(
                channel_frame_geom.CAM_SHAFT_XY, channel_frame_geom.ROCKER_PIVOT_XY
            )
        )
    )
    zero = np.array([0.0])
    assert abs(eb.rocker_angle(zero, nom)[0]) < 1e-4
    longer = dataclasses.replace(nom, rod=nom.rod + 0.5)
    assert eb.rocker_angle(zero, longer)[0] == pytest.approx(-0.5 / nom.pin_x, rel=0.05)
    assert (longer.axis_dx, longer.axis_dy) == (nom.axis_dx, nom.axis_dy)


def test_ungated_minimum_pose_fails_unless_waived(budget, report, nom):
    """Every broad input is scored at the magnifier's minimum pose (clamp
    against the collar), which build_magnifier_assembly never builds: the
    report names those inputs, the gate fails on it unless the yaml records
    the waiver (#748), and the offline wire estimate that rides the waiver
    reproduces lever_wire_geom's own numbers at the as-built pose."""
    import lever_wire_geom

    mag = report["closed_form"]["magnifier"]
    assert mag["minimum_pose_cad_gated"] is False
    assert set(mag["inputs_at_minimum_pose"]) >= {"all_ones", "gaussian_a0p1"}
    strict = negative(budget, readout={"waive_minimum_pose": False})
    bad = eb.budget_closes(eb.build_report(strict))
    assert any(b.startswith("magnifier minimum pose is not CAD-gated") for b in bad), (
        bad
    )
    built = eb._minimum_pose_wire_estimate(
        dataclasses.replace(nom, lever_r_min=nom.lever_r_built)
    )
    assert built["hook_x_mm"] == pytest.approx(lever_wire_geom.CLAMP_X)
    assert built["wire_length_mm"] == pytest.approx(lever_wire_geom.WIRE_LEN, abs=1e-3)
    assert mag["minimum_pose_wire_estimate"]["hook_x_mm"] < lever_wire_geom.CLAMP_X


def test_shipped_procedure_caps_the_clamp_radius_at_the_built_pose(report, nom):
    """The R = 66 x 4.72 / P rule would ask for R > 165 mm on a small input;
    READOUT.md must cap it at the as-built radius and tell the operator the
    short-stroke cost (scale the input up) rather than promise a full stroke."""
    doc = eb.readout_procedure(report)
    mag = report["closed_form"]["magnifier"]
    p_min = (
        mag["ordinate_capacity_full_scale_bars"]
        * mag["lever_radius_min_mm"]
        / mag["lever_radius_built_mm"]
    )
    assert f"capped at the as-built {mag['lever_radius_built_mm']:.0f} mm" in doc
    assert f"$P < {p_min:.2f}$" in doc
    assert "scale such an\ninput UP" in doc
    assert "not CAD-gated" in doc


def test_rod_drive_is_on_the_crank_side(nom):
    """Machine hand: the rod pin sits at -X of the pivot (crank side) while the
    bars ride +X -- build_channel_assembly._arc_geometry's -X branch. A +X bar
    therefore reads NEGATIVE at the top of stroke (the lobe lifts the crank
    side), which the procedure absorbs as a sign convention."""
    h = eb.harmonic_content(nom.d_max, nom, null=eb.null_station(nom))
    assert h["c1_cos"] < 0
    assert -1.03 < h["gain_vs_linear"] < -1.0


def test_shipped_readout_procedure_carries_every_correction(report, nom):
    """The release bundle's READOUT.md must let a builder reproduce the credited
    residual: the station/ordinate/kappa table, the null lift vector, the
    second-harmonic formula and the crank-index readout."""
    doc = eb.readout_procedure(report)
    rows = eb.calibration_table(nom)
    assert rows[0][0] == 0.0 and rows[-1][0] == nom.d_max
    # and when full scale is not a multiple of the row step, the travel stop
    # is still the last row (the bias paragraph quotes rows[-1] as full scale)
    odd = eb.calibration_table(nom, step_mm=5.0)
    assert odd[-1][0] == nom.d_max and odd[-2][0] == 85.0
    assert odd[-1][1:] == pytest.approx(rows[-1][1:])
    assert (
        f"| {rows[0][0]:6.1f} | {rows[0][0] / eb.STICK_DIVISION_MM:6.3f} | {rows[0][1]:+.4f} |"
        in doc
    )
    assert f"{eb.STICK_DIVISION_MM:.2f} mm/division scale" in doc
    assert "Set bar $i$ to the **linear station**" in doc
    assert f"\\ell = {report['null_lift_ordinate']:.4f}" in doc
    assert "-c$ at every odd $k$" in doc
    # the c2 correction is scaled by the READ ordinate: an idle bar still moves
    assert "\\sum_i x^{read}_i\\,\\kappa_i \\cos(2 i \\theta_k)" in doc
    assert "\\sum_i x_i\\,\\kappa_i" not in doc
    assert f"\\kappa \\cdot x^{{read}} = {rows[0][2] * rows[0][1]:+.4f}" in doc
    assert "crank stopped on its index" in doc
    assert "ONE direction" in doc
    # the one-sided setting bias at the ends of the scale is published, so the
    # read-vs-set vector the operator subtracts is the one the Monte Carlo does
    tol = report["station_setting_tolerance_mm"]
    at_zero = eb.read_ordinate(tol / 2.0, nom)
    at_stop = eb.read_ordinate(nom.d_max - tol / 2.0, nom)
    assert at_zero != pytest.approx(rows[0][1], abs=1e-4)
    assert f"**{at_zero:+.4f}$/f$ for a bar at zero**" in doc
    assert f"**{at_stop:+.4f} for a bar at the stop**" in doc
    assert f"bar $x^{{read}} = {at_zero:+.4f}/f$ against $x^{{set}} = 0$" in doc
    assert "s = \\frac{r_0}{S + C_2}" in doc
    assert "O'_k = \\frac{r_k}{s}" in doc


def test_normalisation_uses_only_observable_units():
    """Step 3 of READOUT.md must be executable from what the operator has:
    pen readings in mm and the two ordinate-unit sums S and C2. A synthetic
    trial with a known pen scale, second harmonics and a lift must come back
    as the set ordinates exactly -- no internal trace unit enters."""
    rng = np.random.default_rng(7)
    x = rng.uniform(0.0, 1.0, eb.N_ELEMENTS)
    lift = 0.03
    x_read = x + lift
    kappa = rng.uniform(0.01, 0.06, eb.N_ELEMENTS)
    s = 3.7  # mm per ordinate unit, unknown to the procedure
    th = eb.THETA_K[:, None] * eb.HARMONICS[None, :]
    readings_mm = s * (np.cos(th) @ x_read + np.cos(2.0 * th) @ (x_read * kappa))
    measured = eb.read_coefficients(readings_mm, x_read, kappa)
    measured -= eb.ideal_coefficients(x_read - x)
    assert np.allclose(measured, eb.ideal_coefficients(x), atol=1e-12)


def test_scaled_trial_needs_the_division_to_keep_step_4_a_small_known_vector(
    report, nom
):
    """On a trial the pen forced to scale f < 1, the operator sets bars at
    f x_i d_max, reads the pen, and looks up TABLE ordinates at those stations.
    READOUT.md says: divide each by f and use the quotient everywhere. Executed
    literally on the nominal Gaussian trial that matches the model and recovers
    the unscaled coefficients. The raw table ordinates ALSO recover them on a
    perfect machine -- the read-vs-set vector absorbs (f - 1) x -- but that
    vector is then (1 - f) of the answer, computed from the answer (circular),
    and a real channel-gain error comes out understated by f. With the
    division the vector is the lift-sized known deviation the budget scores."""
    x = eb.reference_inputs()["gaussian_a0p1"]
    f = report["closed_form"]["magnifier"]["per_input"]["gaussian_a0p1"][
        "ordinate_scale"
    ]
    assert 0.0 < f < 1.0
    trial = eb.NominalTrial(nom)
    stations = f * x * nom.d_max
    table = trial.x_read(stations)  # what the operator looks up
    kappa = trial.kappa(stations)
    zero = float(np.mean(trial.trace(stations, eb.PERIOD)))
    readings = trial.trace(stations, eb.THETA_K) - zero  # the pen, any scale
    ideal = eb.ideal_coefficients(x)
    fs = np.max(np.abs(ideal))

    def procedure(r, x_read):
        return eb.read_coefficients(r, x_read, kappa) - eb.ideal_coefficients(
            x_read - x
        )

    divided = procedure(readings, table / f)
    assert np.allclose(divided, trial.readout(x, scale=f), atol=1e-12)
    assert np.max(np.abs(divided - ideal)) / fs < 1e-3
    raw = procedure(readings, table)
    assert np.max(np.abs(raw - ideal)) / fs < 1e-3  # perfect machine: no tell
    # the correction vector step 4 subtracts, as a share of the answer
    small = np.max(np.abs(eb.ideal_coefficients(table / f - x))) / fs
    big = np.max(np.abs(eb.ideal_coefficients(table - x))) / fs
    assert small < big
    # a +1 % gain error on channel 1: the divided procedure reports it in
    # full, the raw one at f of it
    err = np.zeros(eb.N_ELEMENTS)
    err[0] = 0.01
    perturbed = np.zeros_like(readings)
    for j, d, g in zip(eb.HARMONICS, stations, 1.0 + err):
        cyc = trial.one_cycle(float(d))
        perturbed += g * np.interp(
            (j * eb.THETA_K) % (2 * math.pi), trial.grid, cyc, period=2 * math.pi
        )
    perturbed -= float(np.mean(trial.trace(stations, eb.PERIOD)))
    e_div = procedure(perturbed, table / f) - divided
    e_raw = procedure(perturbed, table) - raw
    assert np.max(np.abs(e_div)) > 0.5 * 0.01 * x[0]
    assert np.max(np.abs(e_raw)) / np.max(np.abs(e_div)) == pytest.approx(f, rel=0.05)


def test_timebase_is_scored_on_the_physical_trace(report, nom):
    """Reading off the crank index samples the REAL trace (calibrated
    ordinates, live idle bars, the CAD's 2nd/3rd harmonics) while the
    corrections stay at theta_k. On the broad inputs -- now run at the reduced
    ordinate scale the pen forces, where the hook motion's 2nd/3rd harmonics
    are a larger share of the fundamental -- the physical term sits a little
    ABOVE the ideal-vector proxy; on the sparse pair the proxy fails outright
    (the 18 idle bars' harmonics), so the gate must score the physical one."""
    tb = report["closed_form"]["timebase"]
    phys, ideal = tb["pct_fs_physical_per_input"], tb["pct_fs_per_rad_rms_ideal_vector"]
    rad_index = math.radians(tb["assumed_crank_index_deg"]) / eb.CRANK_TURNS_PER_PERIOD
    for name in ("all_ones", "alternating"):
        proxy = ideal[name] * rad_index / math.sqrt(3.0)
        assert proxy <= phys[name] < 1.15 * proxy, name
    assert phys["pair_1_20"] > 1.3 * ideal["pair_1_20"] * rad_index / math.sqrt(3.0)
    assert tb["pct_fs"] == phys[tb["worst_input"]]
    # and the mechanism: an off-index read of the nominal trial moves every
    # coefficient by the trace's slope there, an on-index read by nothing
    trial = eb.NominalTrial(nom)
    x = eb.reference_inputs()["all_ones"]
    assert np.allclose(trial.readout(x, theta_error=0.0), trial.readout(x))
    assert (
        np.max(np.abs(trial.readout(x, theta_error=rad_index) - trial.readout(x)))
        > 0.01
    )


def test_monte_carlo_perturbs_the_physical_waveform_not_a_cosine(nom):
    """A gain error delta on channel i scales its second harmonic with its
    fundamental, and the operator's FIXED nominal kappa correction cannot
    remove that: delta * kappa_i * x_i * cos(2 i theta_k) must survive in the
    scatter (Codex round 21). Decompose the model's response to +1.25 % on
    channel 1 into the fundamental term, the normaliser share and that
    residual -- the three reproduce it to 1e-4 % FS, and without the residual
    the fit is 10x worse. A zero deviation scores exactly zero (the nominal
    residual is the closure's own term, not scatter)."""
    x = eb.reference_inputs()["all_ones"]
    trial = eb.NominalTrial(nom)
    f = trial.magnifier_setup(x).ordinate_scale
    t = eb.cycle_table(nom)
    st = f * x * nom.d_max
    kappa = np.interp(st, t.stations, t.kappa)
    xr = np.interp(st, t.stations, t.read) / f
    fs = np.max(np.abs(eb.ideal_coefficients(x)))
    sens = eb.gain_sensitivities(nom)
    delta = 0.0125
    dev = {"spring_rate": np.zeros((2, eb.N_ELEMENTS))}
    dev["spring_rate"][0, 0] = 100.0 * delta
    e = eb._channel_model(x, nom, dev, sens, 0.25, f)
    assert np.max(np.abs(e[1])) < 1e-9  # the zero-deviation row
    e = e[0]
    th = eb.THETA_K
    cos_2 = np.cos(2.0 * np.outer(th, eb.HARMONICS))
    fund = 100.0 * delta * xr[0] * np.cos(th) / fs
    share = (eb.ideal_coefficients(xr) + cos_2 @ (xr * kappa)) / fs
    norm = delta * xr[0] * (1.0 + kappa[0]) / (np.sum(xr) + np.sum(xr * kappa))
    second = 100.0 * delta * xr[0] * kappa[0] * np.cos(2.0 * th) / fs
    fit = fund - 100.0 * norm * share + second
    assert np.max(np.abs(e - fit)) < 2e-4
    assert np.max(np.abs(e - (fund - 100.0 * norm * share))) > 5 * np.max(
        np.abs(e - fit)
    )
    assert np.max(np.abs(second)) > 1e-3


def test_kinematic_deviations_reshape_the_waveform_not_just_its_gain(nom):
    """A cam-eccentricity deviation changes c2/c1 (~ e/L) as well as the
    fundamental, so the operator's nominal kappa row is wrong for that
    channel; the Monte Carlo must sample the DEVIATED cycle for kinematic
    features (Codex round 25). The linearised table reproduces the exact
    deviated kinematics to 1e-6 of the stroke; a pure force-balance feature
    (summing hook arm) leaves the shape alone."""
    grid = eb._READ_GRID
    t = eb.cycle_table(nom)
    dv = eb.cycle_derivatives(nom)
    tol = 0.025
    exact = eb.hook_displacement(
        grid, 44.0, dataclasses.replace(nom, ecc=nom.ecc + tol)
    )
    linear = t.sample(44.0, grid) + tol * dv["ecc"].sample(44.0, grid)
    assert np.max(np.abs(exact - linear)) < 1e-6 * np.max(np.abs(exact))

    def kappa(u):
        return float(np.mean(u * np.cos(2 * grid)) / np.mean(u * np.cos(grid)))

    assert kappa(exact) != pytest.approx(kappa(t.sample(44.0, grid)), rel=1e-4)
    assert "summing_hook_arm" not in eb.WAVEFORM_FIELDS
    assert "summing_hook_arm" not in eb.feature_axes(nom)
    # through the model: an eccentricity draw on channel 1 must leave a
    # second-harmonic residual the fixed kappa correction cannot remove
    x = eb.reference_inputs()["all_ones"]
    f = eb.NominalTrial(nom).magnifier_setup(x).ordinate_scale
    sens = eb.gain_sensitivities(nom)
    dev = {"cam_eccentricity": np.zeros((1, eb.N_ELEMENTS))}
    dev["cam_eccentricity"][0, 0] = tol
    e = eb._channel_model(x, nom, dev, sens, 0.25, f)[0]
    gain_only = {"spring_rate": np.zeros((1, eb.N_ELEMENTS))}
    gain_only["spring_rate"][0, 0] = 100.0 * (
        eb.hook_displacement(
            grid, f * nom.d_max, dataclasses.replace(nom, ecc=nom.ecc + tol)
        )
        @ np.cos(grid)
        / (eb.hook_displacement(grid, f * nom.d_max, nom) @ np.cos(grid))
        - 1.0
    )
    e_gain = eb._channel_model(x, nom, gain_only, sens, 0.25, f)[0]
    assert np.max(np.abs(e)) > 0.01  # ~0.29 % gain on one of 20 channels
    assert np.max(np.abs(e - e_gain)) > 1e-4  # the shape term is there
    assert np.max(np.abs(e - e_gain)) < 0.1 * np.max(np.abs(e))  # and second order


def test_position_zones_draw_both_axes_through_the_kinematics(budget, nom):
    """A hole held by a diametral position zone may sit off tangentially as
    well as radially, so the rod pin, bar pin and spring eye draw TWO axes
    (the zone's bounding square), each through the exact kinematics: the
    linearised tangential tables match the exact deviated cycle, the tangential
    response is real and below the radial one (with the shaft axis fixed by
    the frame a radial pin offset also re-leans the rod, so the two are within
    a factor of ~4, not 30), and the Monte Carlo actually samples the second
    column."""
    grid = eb._READ_GRID
    t = eb.cycle_table(nom)
    dv = eb.cycle_derivatives(nom)
    axes = eb.feature_axes(nom)
    assert [f for f, _ in axes["rocker_rod_pin_radius"]] == ["pin_x", "pin_y"]
    assert [f for f, _ in axes["lever_bar_pin_arm"]] == ["bar_pin_arm", "hook_skew"]
    assert [f for f, _ in axes["lever_spring_hook_arm"]] == ["hook_arm", "hook_skew"]
    assert axes["lever_bar_pin_arm"][1][1] == pytest.approx(-1.0 / nom.bar_pin_arm)
    for field, h in (("pin_y", 0.1), ("hook_skew", 0.1 / nom.hook_arm)):
        exact = eb.hook_displacement(
            grid, 44.0, dataclasses.replace(nom, **{field: getattr(nom, field) + h})
        )
        linear = t.sample(44.0, grid) + h * dv[field].sample(44.0, grid)
        assert np.max(np.abs(exact - linear)) < 1e-6 * np.max(np.abs(exact))
    nominal_ac = t.sample(44.0, grid)
    nominal_ac = np.max(np.abs(nominal_ac - nominal_ac.mean()))

    def ac_gain(field, h):
        u = eb.hook_displacement(
            grid, 44.0, dataclasses.replace(nom, **{field: getattr(nom, field) + h})
        )
        return np.max(np.abs(u - u.mean())) / nominal_ac - 1.0

    radial = abs(ac_gain("pin_x", 0.1))
    tangential = abs(ac_gain("pin_y", 0.1))
    assert 0.0 < tangential < radial  # ~0.25x with the shaft axis fixed by the frame
    # the sampler: a tangential-only draw moves the reading, by less than the radial one
    x = eb.reference_inputs()["all_ones"]
    f = eb.NominalTrial(nom).magnifier_setup(x).ordinate_scale
    sens = eb.gain_sensitivities(nom)
    both = np.zeros((2, eb.N_ELEMENTS, 2))
    both[0, 0, 0] = 0.1  # radial on channel 1, draw 0
    both[1, 0, 1] = 0.1  # tangential on channel 1, draw 1
    e = eb._channel_model(x, nom, {"rocker_rod_pin_radius": both}, sens, 0.25, f)
    assert np.max(np.abs(e[1])) > 1e-5
    assert np.max(np.abs(e[1])) < np.max(np.abs(e[0]))
    mc = eb.monte_carlo(
        {**budget, "monte_carlo": {**budget["monte_carlo"], "draws": 20}},
        nom,
        {
            n: eb.NominalTrial(nom).magnifier_setup(eb.reference_inputs()[n])
            for n in budget["reference_inputs"]
        },
    )
    assert mc["per_feature"]["rocker_rod_pin_radius"]["mae"] > 0


def test_cycle_table_always_ends_at_the_travel_stop(nom):
    """A full scale off the 0.25 mm grid gets the stop APPENDED (a short last
    interval), never overwritten onto the last grid row, and the lookup
    brackets stations from the array -- so a bar at the stop reads the exact
    full-scale cycle and one inside the short interval interpolates it."""
    odd = dataclasses.replace(nom, d_max=88.1)
    t = eb.cycle_table(odd)
    assert t.stations[-3:] == pytest.approx([87.75, 88.0, 88.1])
    # and a stop just short of the next grid line never gets that line
    # (88.25) generated past it: the grid stops at 88.0, then 88.2
    over = eb.cycle_table(dataclasses.replace(nom, d_max=88.2))
    assert over.stations[-3:] == pytest.approx([87.75, 88.0, 88.2])
    assert np.all(np.diff(over.stations) > 0)
    assert eb.cycle_table(nom).stations[-1] == nom.d_max  # on-grid: no duplicate row
    assert np.all(np.diff(eb.cycle_table(nom).stations) > 0)
    grid = eb._READ_GRID
    assert np.allclose(
        t.sample(88.1, grid), eb.hook_displacement(grid, 88.1, odd), atol=1e-12
    )
    mid = t.sample(88.05, grid)
    assert np.allclose(mid, 0.5 * (t.cycles[-2] + t.cycles[-1]), atol=1e-12)
    assert t.read[-1] == pytest.approx(1.0)
    # the cache is keyed on the STEP too: a coarse diagnostic grid must not be
    # handed back to a caller that asked for the budget's resolution
    coarse = eb.cycle_table(odd, 1.0)
    assert coarse is not eb.cycle_table(odd)
    assert len(coarse.stations) < len(t.stations)
    assert eb.read_table(odd, 1.0)[0].shape == coarse.stations.shape
    assert eb.read_table(odd)[0].shape == t.stations.shape


def test_idle_bars_are_physically_live_in_the_monte_carlo(nom):
    """A bar at the stick zero still moves (~0.028 of a full-scale bar), so a
    gain deviation on an IDLE channel must move the reading -- the nominal lift
    the operator subtracts does not know about that channel's own spring. On
    the two-channel input the 18 idle bars sum to ~0.5 of the 2.5 the machine
    reports at k=0, so a coherent +1.25 % on them rescales the two live bars
    through the normaliser by ~0.25 % FS -- as large as the same deviation on
    the live bars themselves; a model that idles them at zero scores 0."""
    x = eb.reference_inputs()["pair_1_20"]
    sens = eb.gain_sensitivities(nom)
    idle = (x == 0.0)[None, :]
    on_idle = eb._channel_model(
        x, nom, {"spring_rate": np.where(idle, 1.25, 0.0)}, sens
    )[0]
    on_live = eb._channel_model(
        x, nom, {"spring_rate": np.where(idle, 0.0, 1.25)}, sens
    )[0]
    assert np.max(np.abs(on_idle)) > 0.1
    assert np.max(np.abs(on_idle)) == pytest.approx(np.max(np.abs(on_live)), rel=0.05)


def test_readout_term_counts_the_normalising_read(report):
    """Every coefficient is divided by the pen-read k=0 value, so its error
    carries that read too, scaled by the PHYSICAL r_k/r_0: an input whose k=20
    term nearly equals its k=0 (the lifted square; the second harmonic riding
    r_0 keeps the ratio just under 1) pays for it, all-ones (r_k/r_0 <= 0.05)
    barely. The reported worst single coefficient is the ABSOLUTE bound
    delta(1 + |a_k|) -- both reads extreme and opposing -- since an RSS of the
    two half-widths is neither a bound nor a quantile of their difference."""
    ro = report["closed_form"]["readout"]
    one = ro["one_reading_pct_fs_per_input"]
    mae = ro["pct_fs_per_input"]
    bound = ro["pct_fs_worst_coefficient_abs_bound"]
    assert 0.8 < ro["normaliser_share_max_abs"]["alternating"] < 1.0
    a_max = ro["normaliser_share_max_abs"]["alternating"]
    assert bound["alternating"] / one["alternating"] == pytest.approx(
        1.0 + a_max, rel=1e-6
    )
    assert bound["all_ones"] / one["all_ones"] == pytest.approx(1.0, abs=0.06)
    # MAE of |own - a * normaliser| for uniform reads: delta/2 at a=0, 2 delta/3 at a=1
    assert mae["all_ones"] / one["all_ones"] == pytest.approx(0.5 * 20 / 21, rel=0.01)
    assert mae["alternating"] > mae["all_ones"]
    assert mae["alternating"] / one["alternating"] < 2.0 / 3.0
    # the bound is above the MAE and above the joint draw's own reading term
    for name in one:
        assert bound[name] > mae[name]


def test_stick_division_is_the_configured_scale_the_builder_engraves():
    """The engraved scale is CONFIG (amplitude.stick_*), and the procedure's
    station -> stick-reading conversion, the drawing notes and the builder's
    ticks all reach it through the one read point (measuring_stick_geom); none
    may copy it."""
    import measuring_stick_geom
    import measuring_stick_spec

    configured = float(eb._config.machine("amplitude", "stick_division_spacing_mm"))
    assert measuring_stick_geom.DIVISION_SPACING == configured
    assert measuring_stick_geom.DIVISION_COUNT == int(
        eb._config.machine("amplitude", "stick_division_count")
    )
    assert measuring_stick_geom.MINOR_SPACING == configured / int(
        eb._config.machine("amplitude", "stick_minor_per_division")
    )
    assert eb.STICK_DIVISION_MM == configured
    # the engraved span follows the configured COUNT, so the last tick keeps
    # its end margin instead of running off a longer/shorter scale
    import build_measuring_stick as stick

    assert stick.SCALE_SPAN == (measuring_stick_geom.DIVISION_COUNT - 1) * configured
    assert stick.SCALE_START_X == (
        stick.BODY_LENGTH - stick.SCALE_SPAN - stick.SCALE_END_MARGIN
    )
    # the NATIVE equation and the drawing NOTES carry the same counts, so a
    # config edit cannot leave the driven sketch or the sheet describing a
    # scale the part does not engrave
    src = (pathlib.Path(eb.__file__).with_name("build_measuring_stick.py")).read_text(
        encoding="utf-8"
    )
    assert '{DIVISION_COUNT - 1} * "DivisionSpacing"' in src
    notes = measuring_stick_spec.DRAWING_NOTES
    top = measuring_stick_geom.DIVISION_COUNT - 1
    assert (
        f"{measuring_stick_geom.DIVISION_COUNT} FULL TICKS (VALUES 0 THRU {top})"
        in notes
    )
    assert (
        f"{measuring_stick_geom.MINOR_PER_DIVISION - 1} MINOR" in notes
    )  # tenths between two full ticks
    assert f"NUMERALS 0 THRU {top}" in notes
    assert f"TICK N AT {configured:.2f} X N" in notes
    assert f"SPAN {top * configured:.2f} REF" in notes
    assert re.search(r"^from measuring_stick_geom import \($", src, re.M)
    for module in ("measuring_stick_geom.py", "measuring_stick_spec.py"):
        text = (pathlib.Path(eb.__file__).with_name(module)).read_text(encoding="utf-8")
        assert not re.search(r"^\s*\w*DIVISION\w*\s*[:=].*\d", text, re.M) or (
            "_config.machine" in text
        ), f"{module} assigns the scale instead of reading config"
        assert f"= {configured}" not in text, f"{module} hardcodes the division spacing"
    for name in (
        "DIVISION_SPACING",
        "DIVISION_COUNT",
        "MINOR_PER_DIVISION",
        "MINOR_SPACING",
    ):
        assert not re.search(rf"^{name}\s*=", src, re.M), (
            f"{name} is copied, not imported"
        )


def test_reserved_terms_are_scored_on_the_worst_broad_input(report):
    """The gated readout and knife values must be the worst BROAD input, not
    the all-ones one nor the sparse pair (reported, not gated). The readout
    term converts one reading through s = r_0/(S + C_2): its per-input value
    is proportional to (S + C_2)/sum x, so the pair -- whose 18 idle bars lift
    S well above sum x -- reads highest and is excluded."""
    cf = report["closed_form"]
    knife, ro = cf["knife"], cf["readout"]
    assert knife["pct_fs"] == pytest.approx(
        max(v for n, v in knife["pct_fs_per_input"].items() if n != "pair_1_20")
    )
    assert knife["pct_fs_per_input"]["pair_1_20"] > knife["pct_fs"]
    assert ro["pct_fs"] == pytest.approx(
        max(v for n, v in ro["pct_fs_per_input"].items() if n != "pair_1_20")
    )
    assert ro["pct_fs_per_input"]["pair_1_20"] > ro["pct_fs"]


def test_reference_inputs_stay_on_the_lifting_side():
    """build_channel_assembly rejects amplitude_mm < 0, so no reference input may
    put a bar at a negative station."""
    for name, x in eb.reference_inputs().items():
        assert np.all(x >= 0.0), name


def test_drawing_limits_agree_with_the_budget(budget):
    """Manufacturing tolerance values and derived fit limits agree with the budget."""
    import channel_lever_spec
    import cylinder_gear_spec
    import rocker_arm_spec
    import summing_lever_spec

    feats = budget["critical_features"]
    assert cylinder_gear_spec.ECCENTRICITY_TOLERANCE_MM == pytest.approx(
        feats["cam_eccentricity"]["tolerance"]
    ), "cylinder-gear drawing carries a different eccentricity tolerance"
    assert cylinder_gear_spec.CAM_PHASE_TOLERANCE_DEG == pytest.approx(
        feats["cam_phase"]["tolerance"]
    ), "cylinder-gear drawing carries a different cam-phase tolerance"
    # every +/- arm tolerance is held by a diametral position zone of twice it
    for feature, spec_module, key in (
        ("summing_hook_arm", summing_lever_spec, "spring-hole pattern position"),
        ("rocker_rod_pin_radius", rocker_arm_spec, "rod-pin hole position"),
        ("lever_bar_pin_arm", channel_lever_spec, "bar-pin hole position"),
        ("lever_spring_hook_arm", channel_lever_spec, "spring-eye hole position"),
    ):
        zone = float(spec_module.GEOMETRIC_TOLERANCES_MM[key])
        assert zone == pytest.approx(2.0 * feats[feature]["tolerance"]), (
            f"{spec_module.__name__} {key!r} zone {zone} is not twice the budget's "
            f"+/-{feats[feature]['tolerance']} on {feature}"
        )
    backlash_lo, backlash_hi = eb._config.fit("gear_mesh", "backlash_mm")
    pitch_r = (
        eb.cylinder_gear_spec.TEETH
        / (2.0 * eb.cylinder_gear_spec.DIAMETRAL_PITCH)
        * 25.4
    )
    spread_deg = math.degrees((backlash_hi - backlash_lo) / 2.0 / pitch_r)
    assert budget["critical_features"]["mesh_lag_spread"]["tolerance"] == pytest.approx(
        spread_deg, abs=0.01
    )


def test_unsupported_distribution_fails_loud(budget, nom):
    """A distribution the model does not implement raises instead of sampling uniform."""
    bad = {**budget, "monte_carlo": {**budget["monte_carlo"], "distribution": "normal"}}
    trial = eb.NominalTrial(nom)
    setups = {
        n: trial.magnifier_setup(eb.reference_inputs()[n])
        for n in budget["reference_inputs"]
    }
    with pytest.raises(ValueError, match="distribution"):
        eb.monte_carlo(bad, nom, setups)


def test_setup_class_deviations_are_redrawn_per_trial(budget, nom, monkeypatch):
    """`class: channel` is the machine's deviation -- one draw shared by every
    trial; `class: setup` (station setting) is re-introduced each time the
    operator resets the bars. Two trials of the SAME input must therefore see
    identical channel-class errors draw for draw, and different setup-class
    ones -- otherwise the pooled worst coefficient models one setting pattern
    reused across trials."""
    base = eb.reference_inputs()
    monkeypatch.setattr(
        eb, "reference_inputs", lambda: {**base, "twin": base["all_ones"]}
    )
    small = {
        **budget,
        "monte_carlo": {**budget["monte_carlo"], "draws": 50},
        "reference_inputs": ["all_ones", "twin", "pair_1_20"],
    }
    trial = eb.NominalTrial(nom)
    setups = {
        n: trial.magnifier_setup(eb.reference_inputs()[n])
        for n in small["reference_inputs"]
    }
    seen = {}

    real = eb._channel_model

    def spy(x, nom_, dev, sens, tol, scale):
        seen.setdefault(len(seen), {k: v.copy() for k, v in dev.items()})
        return real(x, nom_, dev, sens, tol, scale)

    monkeypatch.setattr(eb, "_channel_model", spy)
    eb.monte_carlo(small, nom, setups)
    channel = [
        k for k, f in small["critical_features"].items() if f["class"] == "channel"
    ][0]
    per_feature = [v for v in seen.values() if set(v) == {channel}]
    assert np.array_equal(
        per_feature[0][channel], per_feature[1][channel]
    )  # all_ones, twin
    setup = [v for v in seen.values() if set(v) == {"station_setting"}]
    assert not np.array_equal(setup[0]["station_setting"], setup[1]["station_setting"])
    bad = {
        **small,
        "critical_features": {
            **small["critical_features"],
            "station_setting": {
                **small["critical_features"]["station_setting"],
                "class": "operator",
            },
        },
    }
    with pytest.raises(ValueError, match="class"):
        eb.monte_carlo(bad, nom, setups)

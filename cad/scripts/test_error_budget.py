"""check:budget -- the coefficient-error budget closes and stays tied to the CAD.

Pins the CONTRACT of cad/config/error_budget.yaml + error_budget.py rather than
its arithmetic: the linear sensitivities agree with the exact kinematics, the
readout procedure really cancels common-mode error, the second-harmonic
correction really removes the nominal-design residual, every toleranced nominal
still resolves to the spec constant the CAD builds from, the drawing limits
match the budget, and the Monte Carlo lands inside the targets. SolidWorks-free.
"""

from __future__ import annotations

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
    "summing_hook_arm": "sum_arm",
    "spring_rate": "spring_rate",
}


@pytest.fixture(scope="module")
def budget():
    """The allocation config under test."""
    return eb.load_budget()


@pytest.fixture(scope="module")
def nom():
    """The as-designed inputs from the spec modules."""
    return eb.nominal()


@pytest.fixture(scope="module")
def report(budget):
    """One full model run, shared across the module."""
    return eb.build_report(budget)


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


def test_calibrated_readout_cancels_common_mode_gain(nom):
    """Every channel 1 % strong -> zero coefficient error after the trial's
    own k=0 normalisation; only channel-to-channel differences survive. The spring
    sensitivity is the numerator's 1 %/% -- the common denominator of the force
    balance is what this calibration removes, so it must not be pre-cancelled."""
    x = eb.reference_inputs()["gaussian_a0p1"]
    draws = 1
    sens = eb.gain_sensitivities(nom)
    assert sens["spring_rate"] == 1.0
    dev = {"spring_rate": np.full((draws, eb.N_ELEMENTS), 1.0)}
    e = eb._channel_model(x, nom, dev, sens)
    assert np.max(np.abs(e)) < 1e-9


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
    allowance, and the total inside the benchmark MAE."""
    assert eb.budget_closes(report) == []
    assert set(report["closure"]) == {
        "nominal_residual_mae",
        "scatter_mae",
        "readout",
        "timebase",
        "knife",
        "total_mae",
    }


def test_closure_fails_when_a_reserved_term_overruns(budget):
    """A reading uncertainty the CAD's pen stroke cannot carry must fail the
    gate through the readout allowance, not pass on scatter alone."""
    coarse = {
        **budget,
        "reserved": {
            **budget["reserved"],
            "readout": {
                **budget["reserved"]["readout"],
                "reading_uncertainty_mm": 0.3,
            },
        },
    }
    bad = eb.budget_closes(eb.build_report(coarse))
    assert any(b.startswith("readout") for b in bad), bad


def test_magnifier_setup_is_derived_from_the_cad_output_chain(report, nom):
    """The pen scale is not an assumption: the clamp's reachable radius band
    (collar face to rod tip) and the wheel ratio come from the geom modules the
    magnifier assembly builds from, and every reference input is fitted to the
    15 mm half-stroke by them. A broad input needs less magnification than the
    clamp can give, so it runs at a reduced ordinate scale with the clamp at
    the collar; the sparse pair fits at full scale inside the band."""
    import magnifying_clamp_geom
    import magnifying_lever_geom

    band = magnifying_lever_geom.clamp_radius_band(magnifying_clamp_geom.BLOCK_DEPTH)
    assert (nom.lever_r_min, nom.lever_r_built, nom.lever_r_max) == band
    assert nom.lever_r_min < nom.lever_r_built <= nom.lever_r_max
    mag = report["closed_form"]["magnifier"]
    assert 4.0 < mag["ordinate_capacity_full_scale_bars"] < 6.0
    for name, s in mag["per_input"].items():
        assert s["k0_reading_mm"] == pytest.approx(
            nom.pen_half * s["stroke_fill"], rel=1e-6
        )
        assert nom.lever_r_min <= s["lever_r"] <= nom.lever_r_built
        if name == "pair_1_20":
            assert s["ordinate_scale"] == 1.0 and s["lever_r"] > nom.lever_r_min
        else:
            assert s["ordinate_scale"] < 0.6 and s["lever_r"] == nom.lever_r_min
    # the k0 reading the setup credits is the PHYSICAL trace peak at the set
    # scale, and the table rule the procedure ships (P = sum x_read (1 + kappa))
    # reproduces it to 1e-3 (the 3rd harmonic is all that is left out)
    trial = eb.NominalTrial(nom)
    for name, s in mag["per_input"].items():
        x = eb.reference_inputs()[name]
        st = s["ordinate_scale"] * x * nom.d_max
        r0 = eb.pen_gain(nom, s["lever_r"]) * trial.k0_hook_mm(st)
        assert r0 == pytest.approx(s["k0_reading_mm"], rel=1e-3)
        assert trial.peak_bars(st) == pytest.approx(
            trial.k0_hook_mm(st) / abs(trial.f_full), rel=1e-3
        )


def test_shipped_scale_rule_is_the_table_solve_not_proportion(report, nom):
    """READOUT.md tells the operator to take the largest f with P(f) <= capacity
    from the station table. That must be exactly the scale the budget scores
    (ordinate_scale_for), and scaling by proportion P(1)/capacity must NOT be
    it: the idle bars keep a fixed read ordinate, so P is affine in f and the
    proportional scale overdrives the stroke (~12 % on all-ones)."""
    mag = report["closed_form"]["magnifier"]
    cap = mag["ordinate_capacity_full_scale_bars"]
    trial = eb.NominalTrial(nom)
    for name, s in mag["per_input"].items():
        x = eb.reference_inputs()[name]
        assert trial.ordinate_scale_for(x, cap) == pytest.approx(
            s["ordinate_scale"], abs=1e-9
        )
        f = s["ordinate_scale"]
        if f < 1.0:
            assert trial.peak_bars(f * x * nom.d_max) == pytest.approx(cap, rel=1e-6)
            assert trial.peak_bars(min(1.0, 1.001 * f) * x * nom.d_max) > cap
    ones = np.ones(eb.N_ELEMENTS)
    naive = cap / trial.peak_bars(ones * nom.d_max)
    assert naive > trial.ordinate_scale_for(ones, cap) * 1.05
    assert trial.peak_bars(naive * ones * nom.d_max) > 1.08 * cap
    doc = eb.readout_procedure(report, nom)
    assert "largest $f$ for which $P(f)" in doc
    assert "NOT by proportion" in doc


def test_reduced_ordinate_scale_costs_setting_and_knife_proportionally(report, nom):
    """A fixed 0.25 mm setting error and a fixed knife stall are a larger share
    of a trial the pen forced to a smaller scale: every capped broad input's
    scaled bars sum (read ordinates, which exceed the set ones by the idle
    lift) to the same capacity, the knife term is stall/(scale * sum x), and
    the station-setting Monte Carlo on all-ones at its 0.21 scale reads
    1/scale times the full-scale value."""
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
                knife["stall_pct_of_one_channel_fs"]
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
    assert np.max(np.abs(read(mean))) < 1e-9  # each band's mean is the known lift
    assert np.max(np.abs(read(zero))) > 0.5  # the residual scatter is real, at odd k


def test_unbalanced_counter_spring_fails_unless_waived(budget, report):
    """The CAD's counter spring cannot supply the reaction the channel
    preloads need; the report says so, and the gate fails on it unless the
    yaml records the waiver (the open design item)."""
    knife = report["closed_form"]["knife"]
    assert knife["static_balance"] is False
    assert knife["counter_spring_available_N"] < 0.1 * knife["counter_spring_needed_N"]
    strict = {
        **budget,
        "reserved": {
            **budget["reserved"],
            "knife": {**budget["reserved"]["knife"], "waive_static_balance": False},
        },
    }
    bad = eb.budget_closes(eb.build_report(strict))
    assert any(b.startswith("counter spring cannot balance") for b in bad), bad


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
    doc = eb.readout_procedure(report, nom)
    rows = eb.calibration_table(nom)
    assert rows[0][0] == 0.0 and rows[-1][0] == nom.d_max
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
    assert f"**{at_zero:+.4f} for a bar at zero**" in doc
    assert f"**{at_stop:+.4f} for a bar at the stop**" in doc
    assert f"bar $x^{{read}} = {at_zero:+.4f}$ against $x^{{set}} = 0$" in doc
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
    barely; the worst single coefficient is the sqrt(1 + a^2) RSS bound."""
    ro = report["closed_form"]["readout"]
    one = ro["one_reading_pct_fs_per_input"]
    mae = ro["pct_fs_per_input"]
    bound = ro["pct_fs_worst_coefficient_bound"]
    assert 0.8 < ro["normaliser_share_max_abs"]["alternating"] < 1.0
    a_max = ro["normaliser_share_max_abs"]["alternating"]
    assert bound["alternating"] / one["alternating"] == pytest.approx(
        math.sqrt(1.0 + a_max**2), rel=1e-6
    )
    assert bound["all_ones"] / one["all_ones"] == pytest.approx(1.0, rel=0.01)
    # MAE of |own - a * normaliser| for uniform reads: delta/2 at a=0, 2 delta/3 at a=1
    assert mae["all_ones"] / one["all_ones"] == pytest.approx(0.5 * 20 / 21, rel=0.01)
    assert mae["alternating"] > mae["all_ones"]
    assert mae["alternating"] / one["alternating"] < 2.0 / 3.0


def test_stick_division_is_the_spec_constant_the_builder_engraves():
    """The procedure's station -> stick-reading conversion, the drawing notes
    and the builder's engraved ticks all read measuring_stick_spec
    .DIVISION_SPACING; the builder must import it, not copy it."""
    import measuring_stick_spec

    assert eb.STICK_DIVISION_MM == measuring_stick_spec.DIVISION_SPACING
    assert (
        f"TICK N AT {measuring_stick_spec.DIVISION_SPACING:.2f} X N"
        in measuring_stick_spec.DRAWING_NOTES
    )
    assert (
        f"SCALE IS LINEAR IN STATION (1 DIVISION = {measuring_stick_spec.DIVISION_SPACING:.2f})"
        in measuring_stick_spec.DRAWING_NOTES
    )
    src = (pathlib.Path(eb.__file__).with_name("build_measuring_stick.py")).read_text(
        encoding="utf-8"
    )
    assert re.search(r"^\s*DIVISION_SPACING,\s*$", src, re.M)
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
    """Every budgeted limit that reaches a manufacturing output (native
    dimension tolerance, drawing note, GD&T zone, fit band) carries the SAME
    number as error_budget.yaml."""
    import channel_lever_spec
    import channel_spring_installed_notes
    import cylinder_gear_spec
    import draw_cylinder_gear
    import measuring_stick_spec
    import rocker_arm_spec
    import summing_lever_spec

    feats = budget["critical_features"]
    assert cylinder_gear_spec.ECCENTRICITY_TOLERANCE_MM == pytest.approx(
        feats["cam_eccentricity"]["tolerance"]
    ), "cylinder-gear drawing carries a different eccentricity tolerance"
    assert cylinder_gear_spec.CAM_PHASE_TOLERANCE_DEG == pytest.approx(
        feats["cam_phase"]["tolerance"]
    ), "cylinder-gear drawing carries a different cam-phase tolerance"
    # the cam phase rides a NATIVE angular dimension (drawing-simplicity rule
    # 2), not a note: the part build tolerances NotchPhase with the spec
    # constant and the front view shows it. build_cylinder_gear imports
    # SolidWorks, so its tolerance call is pinned at the source level.
    assert "NotchPhase" in cylinder_gear_spec.DRAWING_DIMENSIONS["NotchProfile"]
    assert "NotchPhase" in draw_cylinder_gear.FRONT_KEEP
    part_src = (
        pathlib.Path(eb.__file__).with_name("build_cylinder_gear.py")
    ).read_text(encoding="utf-8")
    assert re.search(
        r'set_dimension_symmetric_angular_tolerance\(\s*adapter,\s*"NotchProfile",'
        r'\s*"NotchPhase",\s*CAM_PHASE_TOLERANCE_DEG,',
        part_src,
    ), "cam-phase tolerance does not reach the NotchPhase model dimension"
    assert (
        f"ALL 20 WITHIN +/-{feats['spring_rate']['tolerance']:.2f}% OF THE SET MEAN"
        in channel_spring_installed_notes.DRAWING_NOTES
    ), "spring spec sheet carries a different matching requirement"
    assert (
        f"SETTING ERROR +/-{feats['station_setting']['tolerance']:.2f} MAX PER BAR"
        in measuring_stick_spec.DRAWING_NOTES
    ), "measuring-stick drawing carries a different setting allowance"
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


def test_assembly_imports_the_shared_stations_instead_of_copying():
    """build_channel_assembly imports SolidWorks, so it cannot be imported in
    this gate; pin at the SOURCE level that its PIVOT / FULCRUM / arc centre /
    slide radius come from the shared modules error_budget reads, never from a
    literal."""
    src = (pathlib.Path(eb.__file__).with_name("build_channel_assembly.py")).read_text(
        encoding="utf-8"
    )
    assert re.search(r"^\s*LEVER_FULCRUM_XY as FULCRUM,\s*$", src, re.M)
    assert re.search(r"^\s*ROCKER_PIVOT_XY as PIVOT,\s*$", src, re.M)
    assert re.search(
        r"^from rocker_arm_spec import CENTER_Y as ARM_ARC_CENTER_LOCAL_Y", src, re.M
    )
    assert re.search(
        r"^from rocker_arm_spec import CURVE_RADIUS as ARM_TOP_RADIUS", src, re.M
    )
    assert "disc = ARM_TOP_RADIUS**2" in src, (
        "solve_state no longer rides the imported radius"
    )
    for name in ("PIVOT", "FULCRUM", "ARM_ARC_CENTER_LOCAL_Y", "ARM_TOP_RADIUS"):
        assert not re.search(rf"^{name}\s*=", src, re.M), (
            f"{name} is copied, not imported"
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

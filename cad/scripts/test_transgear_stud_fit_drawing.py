"""R9-47, R9-65: the MHA-082 stud on its faced-to-fit MHA-178 shim, judged at
the printed worst case.

Each worst case is recomputed here from the owning modules' printed bands,
not from ``transgear_stud_fit``'s own sums, and each import-time guard is
shown to refuse a design that breaks it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

import build_paper_drive_assembly as assembly
import draw_paper_drive_assembly as a06
import draw_transgear_stud_shim as shim_drawing
import paper_drive_assembly_steps as steps
import platen_guide_spec
import rack_pinion_spec as disc
import transgear_arm_geometry as arm
import transgear_arm_plate_geometry as arm_plate
import transgear_arm_plate_spec as arm_plate_spec
import transgear_feed_pinion_spec as sleeve
import transgear_knob_shaft_spec as knob_shaft
import transgear_knob_thrust_ring_spec as ring
import transgear_stub_spec as stub
import transgear_stud_fit as fit
import transgear_stud_shim_spec as shim
from _hole_spec import THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm
from build_platen_guide import LOCK_STATION_X
from build_support_bar import BAR_LENGTH

_DOT_X = printed_band_mm(1)
_RUNOUT = 1.0  # R9-5: the screw-cutting run-out at 32 tpi


def _knob_chain() -> tuple[float, float]:
    """K, F to the disc's front face with the stud's thrust station left out:
    (nominal, band) from each owning module's printed row."""
    terms = (
        (-stub.JOURNAL_LENGTH, stub.JOURNAL_LENGTH_TOL),
        (sleeve.SLEEVE_LENGTH, sleeve.SLEEVE_LENGTH_TOL),
        (-sleeve.GEAR_FACE_STATION, sleeve.STATION_TOL),
        (-disc.FACE_WIDTH, disc.FACE_WIDTH_MAX - disc.FACE_WIDTH),
        (-arm.THICKNESS, arm.THICKNESS_BAND),
        (
            arm_plate.HUB_FACE_TO_MOUNTING,
            printed_band_mm(arm_plate_spec.HUB_STATION_PLACES),
        ),
        (ring.LENGTH, ring.LENGTH_TOL),
        (knob_shaft.FACE_WIDTH, printed_band_mm(knob_shaft.FACE_WIDTH_PLACES)),
    )
    return sum(value for value, _ in terms), sum(band for _, band in terms)


def _fitted_station() -> tuple[float, float]:
    """TS, the arm's front face to the stud's step face, as the fit-up sets
    it: K - m over the chain and the window."""
    k, band = _knob_chain()
    lo, hi = stub.STUD_FIT_WINDOW
    return k - band - hi, k + band - lo


def _stud_station() -> tuple[float, float]:
    """The stud's own seat-to-step size, made to its printed one place."""
    places = stub.DRAWING_PRECISION_BY_NAME["ThrustStation"]
    band = printed_band_mm(places)
    return stub.SLEEVE_THRUST_STATION - band, stub.SLEEVE_THRUST_STATION + band


def _disc_platen_air(lock_gap_max: float, window_max: float) -> float:
    """The disc's rear face to the platen's front face at the printed worst
    case: the platen forward by its fitted float magnified by its yaw about
    the bar's end at the near lock, every printed band in the chain against
    it, then the window's max, the cluster's rearward float, its tilt on the
    bore clearance at the disc rim and the disc face's squareness."""
    half_bar = BAR_LENGTH / 2.0
    yaw = half_bar / (half_bar - LOCK_STATION_X[0])
    nominal = assembly.PLATE_FRONT_Z - assembly.KNOB_SHAFT_Z0 - disc.FACE_WIDTH
    band = (
        assembly.HANGER.HEAD_PLAY_MAX
        - assembly.SPACER.LENGTH_BAND
        + arm.THICKNESS_BAND
        + printed_band_mm(arm_plate_spec.HUB_STATION_PLACES)
        + ring.LENGTH_TOL
        + printed_band_mm(knob_shaft.FACE_WIDTH_PLACES)
        + (disc.FACE_WIDTH_MAX - disc.FACE_WIDTH)
        + assembly.BAR.BAR_DEPTH_BAND
        + printed_band_mm(3)  # the 4.0 platen carries no drawing band
    )
    step_edge = (stub.STEP_DIA - _DOT_X) / 2.0
    tilt = (
        (disc.OUTSIDE_DIA / 2.0 - step_edge)
        * sleeve.BORE_DIAMETRAL_CLEARANCE[1]
        / (sleeve.SLEEVE_LENGTH - sleeve.SLEEVE_LENGTH_TOL)
    )
    squareness = float(disc.GEOMETRIC_TOLERANCES_MM["disc face squareness to bore"])
    return (
        nominal
        - band
        - lock_gap_max * yaw
        - window_max
        - sleeve.CLUSTER_FLOAT_RANGE[1]
        - tilt
        - squareness
    )


def _collar_rack_air(step_length: float) -> float:
    """The Ø12 collar's front face to the MHA-069 rack's back face: the arm
    forward on the shortest spacer, the bar thinnest, the rack thickest
    (6.0, no drawing band) and the shim and collar together the longest the
    fit-up leaves them."""
    nominal = assembly.STUB_Z0 - stub.COLLAR_LENGTH - assembly.RACK_BACK_Z
    model = stub.FITTED_THRUST_STATION - stub.STEP_LENGTH
    worst = _fitted_station()[1] - (step_length - _DOT_X)
    return (
        nominal
        - assembly.SPACER.LENGTH_BAND
        - assembly.BAR.BAR_DEPTH_BAND
        - printed_band_mm(3)
        - (worst - model)
    )


def test_the_knob_chain_sets_the_shim_band() -> None:
    k, band = _knob_chain()
    assert (k, band) == pytest.approx((10.9, 0.6154), abs=1e-6)
    assert (fit.KNOB_CHAIN_NOMINAL, fit.KNOB_CHAIN_BAND) == pytest.approx((k, band))
    # The model's stations close the same chain: m at the window's centre.
    model_m = assembly.DISC_Z0 - sleeve.CLUSTER_FLOAT - assembly.KNOB_SHAFT_Z0
    assert model_m + stub.FITTED_THRUST_STATION == pytest.approx(k, abs=1e-9)
    assert model_m == pytest.approx(sum(stub.STUD_FIT_WINDOW) / 2.0, abs=1e-9)
    lo, hi = _fitted_station()
    assert (lo, hi) == pytest.approx((10.0846, 11.4154), abs=1e-6)
    # The shim takes the fitted station less the stud as made (7.7 at .X).
    ts_lo, ts_hi = _stud_station()
    assert (ts_lo, ts_hi) == pytest.approx((6.9, 8.5), abs=1e-9)
    shim_band = (lo - ts_hi, hi - ts_lo)
    assert shim_band == pytest.approx((1.5846, 4.5154), abs=1e-6)
    assert shim_band == pytest.approx(
        (fit.SHIM_THICKNESS_FITTED_MIN, fit.SHIM_THICKNESS_FITTED_MAX), abs=1e-9
    )
    assert shim_band == pytest.approx((shim.GAP_MIN, shim.GAP_MAX), abs=1e-9)
    # The model's shim is the fit to nominal parts, and its blank always
    # leaves a cut to take at the thickest fit.
    assert shim.THICKNESS == pytest.approx(
        stub.FITTED_THRUST_STATION - stub.SLEEVE_THRUST_STATION
    )
    assert shim_band[0] < shim.THICKNESS < shim_band[1]
    assert shim.BLANK_THICKNESS_MIN > shim_band[1]
    # The machine stations: the shim on the arm, the stud's seat on the shim.
    assert assembly.SHIM_Z0 + shim.THICKNESS == pytest.approx(assembly.ARM_Z0)
    assert assembly.STUB_Z0 == pytest.approx(assembly.SHIM_Z0)
    assert assembly.FEED_Z0 == pytest.approx(-135.15, abs=1e-9)


def test_the_disc_rear_face_clears_the_platen_at_the_printed_worst_case() -> None:
    lock_gap_max = platen_guide_spec.LOCK_GAP_FIT[1]
    air = _disc_platen_air(lock_gap_max, stub.STUD_FIT_WINDOW[1])
    assert air >= 0.0
    assert air == pytest.approx(0.0531, abs=1e-4)
    assert air == pytest.approx(assembly.DISC_PLATEN_AIR_WORST, abs=1e-9)
    # Negative controls: the HEAD lock gap (0.31), a 0.35 window, and the
    # stud seated on the arm with no shim at all all strike the platen.
    assert _disc_platen_air(0.31, stub.STUD_FIT_WINDOW[1]) < 0.0
    assert _disc_platen_air(lock_gap_max, 0.35) < 0.0
    k, band = _knob_chain()
    no_shim_m_min = k - band - _stud_station()[1]
    assert _disc_platen_air(lock_gap_max, no_shim_m_min) < 0.0


def test_the_collar_clears_the_rack_at_the_printed_worst_case() -> None:
    air = _collar_rack_air(stub.STEP_LENGTH)
    assert air >= 0.0
    assert air == pytest.approx(0.1746, abs=1e-4)
    assert air == pytest.approx(assembly.COLLAR_RACK_AIR_WORST, abs=1e-9)
    # Negative control: on HEAD's 2.5 step, the collar enters the rack.
    assert _collar_rack_air(2.5) < -1.0


def test_the_relief_stays_in_the_shim_and_full_thread_engages_the_arm() -> None:
    """The thinnest fitted shim holds the widest rear relief with 0.3 of
    full thread to spare, so the arm's tap meets only full thread; the
    engagement is the thread out of the arm's front face or the arm, each
    less its 0.25 mouth break."""
    lo, hi = _fitted_station()
    shim_min = lo - _stud_station()[1]
    relief_max = stub.REAR_RELIEF_WIDTH + stub.REAR_RELIEF_WIDTH_TOL
    assert relief_max >= _RUNOUT
    assert shim_min - relief_max == pytest.approx(0.3846, abs=1e-6)
    assert shim_min - relief_max >= fit.RELIEF_COVER
    major = THREAD_MAJOR_MM["#10-32"]
    mouth = arm.STUD_TAP_MOUTH_LOSS_MAX
    arm_min = arm.THICKNESS - arm.THICKNESS_BAND
    thread_out_min = stub.REAR_THREAD_END_FROM_THRUST - _DOT_X - hi
    worst = min(thread_out_min, arm_min - mouth) - mouth
    assert worst == pytest.approx(7.4121, abs=1e-4)
    assert worst == pytest.approx(fit.REAR_ENGAGEMENT_WORST, abs=1e-6)
    assert worst / major >= 1.5
    # The shim's drilled bore passes the thread's major.
    assert shim.ID + min(shim.ID_BAND) > major
    # The sleeve's rear face bears on the step: (8.2 - 3.93) / 2.
    annulus = (stub.STEP_DIA - _DOT_X - (sleeve.BORE_DIA + sleeve.BORE_DIA_BAND[0])) / 2
    assert annulus == pytest.approx(fit.THRUST_ANNULUS_MIN, abs=1e-6)
    assert annulus >= 2.0
    # The rear dome's tip moves with the fit; nothing else at the stud's xy
    # stands behind the arm.
    assert fit.REAR_DOME_TIP_MACHINE_Z == pytest.approx(
        (-115.6154, -112.6846), abs=1e-4
    )


def _reload(module_name: str, alias: str) -> None:
    path = Path(sys.modules[module_name].__file__)
    probe = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(probe)
    probe.loader.exec_module(module)


@pytest.mark.parametrize(
    ("name", "value", "refusal"),
    [
        ("SLEEVE_THRUST_STATION_MAX", 8.7, r"does not hold"),
        ("REAR_RELIEF_WIDTH_MAX", 1.4, r"does not hold"),
        ("REAR_THREAD_END_MIN", 17.0, r"under 1\.5D"),
        ("FITTED_THRUST_STATION", 10.9, r"window centre"),
    ],
)
def test_the_fit_module_refuses_a_stud_that_breaks_at_the_worst_case(
    monkeypatch, name: str, value: float, refusal: str
) -> None:
    monkeypatch.setattr(stub, name, value)
    with pytest.raises(AssertionError, match=refusal):
        _reload("transgear_stud_fit", "_stud_fit_probe")


@pytest.mark.parametrize(
    ("owner", "name", "value", "refusal"),
    [
        (platen_guide_spec, "LOCK_GAP_FIT", (0.05, 0.31), r"strikes the platen"),
        (stub, "STUD_FIT_WINDOW", (0.10, 0.35), r"strikes the platen"),
        (stub, "STEP_LENGTH", 2.5, r"collar enters the MHA-069 rack"),
        (shim, "THICKNESS", 3.0, r"seat is off the shim"),
    ],
)
def test_the_assembly_refuses_a_fit_that_strikes_at_the_worst_case(
    monkeypatch, owner, name: str, value, refusal: str
) -> None:
    monkeypatch.setattr(owner, name, value)
    if name == "STEP_LENGTH":
        # The collar is the stud's station less the step (transgear_stub_spec).
        monkeypatch.setattr(stub, "COLLAR_LENGTH", stub.SLEEVE_THRUST_STATION - value)
        monkeypatch.setattr(stub, "STEP_LENGTH_MIN", value - _DOT_X)
        monkeypatch.setattr(
            fit,
            "COLLAR_FRONT_STATION_FITTED_MAX",
            fit.THRUST_STATION_FITTED_MAX - (value - _DOT_X),
        )
    with pytest.raises(AssertionError, match=refusal):
        _reload("build_paper_drive_assembly", "_paper_drive_probe")


def test_the_fit_up_faces_the_shim_and_its_sheet_points_at_the_step() -> None:
    sequence = list(steps.SEQUENCE)
    at = sequence.index("stud-faced-to-fit")
    assert sequence[at - 1 : at + 2] == [
        "fitup-pose-set",
        "stud-faced-to-fit",
        "collar-gap-measured",
    ]
    shim_number = a06.BOM_PART_NUMBERS["transgear-stud-shim"]
    assert shim_number == "MHA-178"
    text = a06._step_text()
    assert f"FACE THE {shim_number} SHIM" in text["stud-faced-to-fit"]
    assert stub.STUD_FIT_WINDOW_TEXT in text["stud-faced-to-fit"]
    assert "STOP AND REPORT" in text["stud-faced-to-fit"]
    assert f"THROUGH THE {shim_number} SHIM" in text["stud-fitted"]
    assert "ARM SEAT" not in " ".join(text.values())
    assert steps.COLLAR_DISC_AIR_MIN == stub.STUD_FIT_WINDOW[0]
    # The shim's thickness prints as a reference under its faced-to-fit
    # callout, which carries the fitted band and the step.
    assert shim.REFERENCE_DIMENSIONS == {"DiscThick"}
    callout = shim_drawing.DIMENSION_CALLOUTS["DiscThick"]
    assert callout.startswith(
        f"SET AT ASSEMBLY {fit.SHIM_THICKNESS_FITTED_MIN:.2f}-"
        f"{fit.SHIM_THICKNESS_FITTED_MAX:.2f}"
    )
    assert steps.step_ref("stud-faced-to-fit") in callout
    assert all(len(line) <= 70 for line in callout.splitlines())

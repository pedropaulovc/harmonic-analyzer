r"""Standalone validation harness -- the verify pass IS the test suite.

The build scripts already gate themselves (``_common`` raises on free DOF,
interference, rebuild errors). ``verify.py`` promotes those gates into one
runnable, re-runnable acceptance check that opens an *already-built* assembly
and proves it is sound, plus the assertions a build script cannot make about
itself: that the gear ratios in the live model equal the config, and that the
component count is the expected "N instances -> 1 part" envelope.

Suites (``--suite``):

  static   (default)  open the Default pose and run, collecting ALL failures:
                      DOF fully-defined, no over-constrained component, model
                      healthy (deep), interference-free, gear ratios == config,
                      BOM/part-count envelope.
  truth               analytic self-check of ``truth_model`` (no SolidWorks):
                      the synthesis math is symmetric / band-limited / correct.
  config              no-SolidWorks cross-checks: build config (machine/channels)
                      vs the cited DIMENSIONS rows, DIMENSIONS.md freshness, and
                      the tolerance/metadata audit (parts.yaml <-> build scripts;
                      emits cad/out/reports/tolerance_audit.csv).
  isolation           subsystem pass/fail runs (plan F1): open EACH built
                      (sub)assembly and prove it sound in isolation -- the
                      drive-train as the crank+gear test, the channel assembly as
                      the 20-way independence test, output/frame/top as
                      structural/smoke. Needs SolidWorks.
  motion              kinematic pen-driver fidelity (plan F5): open output.SLDASM,
                      sweep the CrankDeg global, and assert the pen-marker tip
                      traces truth_model.pen_y (mapped to the physical
                      half-stroke) with NO force solver -- the computed-not-
                      simulated summation realised through the equation-driven
                      pen-rod mate (pen_driver.py / docs/motion-policy.md). Needs
                      SolidWorks.
  all                 static + truth + config + motion.

Unlike the build gates (fail-fast), ``static``/``isolation`` run every gate and
report the full set of failures at the end, so one run tells you everything wrong.

Run (SolidWorks already open for any suite touching geometry)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\verify.py [name ...] [--suite static|truth|all]

``name`` defaults to every built assembly in ``cad/out/sldasm`` (drive-train,
harmonic-analyzer). ``truth``/``config`` need no SolidWorks and no assembly.

NOT YET WIRED (tracked, not silently skipped):
  * Stepped-crank interference across the full gear train (turning the real
    crank through the gear train) needs the Basic Motion solver -- the lock mates
    that key the cone cluster are outside the gear-mate graph, so a kinematic
    rotate desyncs the train (see docs/motion-policy.md). The pen-vs-truth_model
    output proof, by contrast, IS wired: ``--suite motion`` drives the pen
    kinematically off the CrankDeg global (no train rotation needed).
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import _config
import gen_dimensions
import pen_driver
import truth_model
from _common import (
    OUT_SLDASM,
    assert_components_fully_defined,
    assert_model_healthy,
    check,
    check_no_interference,
    component_names,
    component_transform,
    log,
    run_build,
)
from _common import _flag, _read_member  # component iteration helpers (read-only)

# solidworks_mcp internals reused read-only: the live gear-mate ratios are not
# exposed by any public tool (list_mates returns name/type/suppressed only), so
# the gear-ratio gate reads them through the same helper the kinematic driver
# uses. Read-only -- it walks the MateGroup and returns numerators/denominators.
from solidworks_mcp.adapters.solidworks.assembly import _gear_mate_links

REST = "Default"  # the deterministic, fully-defined, render/photo-gated pose
OVER_CONSTRAINED = 4  # swConstrainedStatus_e

# The gear mates live in this sub-assembly's MateGroup. The top assembly
# references it flexibly, so its own MateGroup has none -- they are verified
# when this sub is verified, not duplicated at the top.
GEAR_OWNER = "drive-train"
# The channel assembly carries the independent moving stations (CHANNELS of them).
# These four stems are mated instances (one per channel), NOT pattern slaves -- the
# isolation suite asserts CHANNELS of each, the structural precondition for the
# channels articulating at independent harmonics (only grounded spring/bushing
# structure is LocalLinearPattern'd; see build_channel_assembly.py).
CHANNEL_OWNER = "channel"
# Physically-built channels. TEMPORARY: machine.yaml channels.active_count caps
# the per-channel mechanism to the first N (3) for build performance; the gates
# below (instance independence, channel gear meshes, component bands) track that N
# so the reduced build stays fully verified. Recover by setting it back to 20.
CHANNELS = _config.active_count()
# The kinematic pen driver (plan F5) lives in this sub: its pen-rod travel mate
# is equation-linked to a CrankDeg global through the chained Fourier sum
# (pen_driver.install, run at build time). The motion suite sweeps CrankDeg here
# and proves the pen tip traces truth_model.pen_y -- the computed-not-simulated
# summation, with no force solver (docs/motion-policy.md).
MOTION_OWNER = "output"
PEN_MARKER_STEM = "pen-marker"  # the carriage tip whose Y traces the curve
# CrankDeg angles to sample; spans a full fundamental period (0..360) so both
# stroke extremes (the square-wave preset peaks at 0 and 180) are exercised.
_MOTION_SWEEP_DEG = [0.0, 30.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0, 360.0]
# Generous vs the 5.25e-05 mm the de-risk probe achieved -- this is a fidelity
# gate on the equation chain + doc-unit handling, not a numeric-precision race.
_MOTION_TOL_MM = 1e-2
_MOVING_CHANNEL_STEMS = ("rocker-arm", "connecting-rod", "amplitude-bar", "channel-lever")
_INSTANCE_SUFFIX = re.compile(r"-\d+$")
# Crank-drive gear mate: either side carries one of these in its component name.
_CRANK_GEAR_TOKENS = ("crank-pinion", "crank-drive-gear")
# Expected TOP-LEVEL component-count band per assembly: a tripwire for "a build
# dropped/duplicated a channel (or a whole subassembly)", not a tight count.
# component_names counts top-level components only (GetComponents(TopLevelOnly)),
# so harmonic-analyzer's count is its 4 child subassemblies -- NOT the ~340
# flattened parts. Bands measured live (verify.py --suite isolation) with margin.
# The channel + drive-train bands scale with the built channel count N (the
# TEMPORARY active_count): channel = 7N + 4 (N×{rocker,rod,bar,lever,spring} + 2
# shafts + 4 ball-mounts + 2 bushings per inter-channel gap), drive-train = 32 + N
# (full 20-gear cone stack + crank/structure ≈ 32, plus N cylinder gears). Both
# reproduce the measured N=20 bands (144, 52) and stay correct at N=3 (25, 35).
_N_CH = _config.active_count()
_COMPONENT_BAND = {
    "frame": (11, 16),          # measured 13
    "drive-train": (32 + _N_CH - 4, 32 + _N_CH + 4),  # N=20 -> (48,56), measured 52
    "channel": (7 * _N_CH + 4 - 6, 7 * _N_CH + 4 + 6),  # N=20 -> (138,150), measured 144
    "output": (117, 129),       # measured 123 (no per-channel parts here)
    "harmonic-analyzer": (3, 6),  # 4 subassemblies: frame, drive-train, channel, output
}

# Tolerance audit (Part D / handoff §14.2 Gate E): every built part must carry
# these custom-property-bearing fields, and the named classes must resolve.
SCRIPTS_DIR = Path(__file__).resolve().parent
REPORTS_DIR = SCRIPTS_DIR.parent / "out" / "reports"
_PART_NAME_RE = re.compile(r'^PART_NAME\s*=\s*["\']([a-z0-9-]+)["\']', re.MULTILINE)
_REQUIRED_PART_FIELDS = ("material", "tolerance_class", "process")
_AUDIT_COLUMNS = (
    "part", "number", "material", "tolerance_class", "fit_class",
    "process", "confidence", "status", "issues",
)


@dataclass
class Report:
    """Collects gate outcomes so one run reports every failure, not just the first."""

    passed: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def gate(self, label: str, fn: Callable[[], None]) -> None:
        """Run ``fn``; record pass or the exception text. Never propagates."""
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 -- a gate failure is data, not a crash
            self.failed.append((label, str(exc)))
            print(f"  XX  GATE FAILED [{label}]: {exc}", flush=True)
            return
        self.passed.append(label)
        print(f"  OK  GATE PASSED [{label}]", flush=True)

    def merge(self, other: "Report") -> None:
        self.passed += other.passed
        self.failed += other.failed


def _canon_ratio(num: int, den: int) -> tuple[int, int]:
    """Reduce to lowest terms AND sort the pair.

    A gear mesh ``a:b`` is the same physical coupling as ``b:a`` -- SolidWorks
    records the numerator/denominator in whichever entity order the mate was
    built with (here it stores cylinder:cone, the reciprocal of the config's
    cone:cylinder). Canonicalising to ``(min, max)`` makes the comparison about
    the tooth-count magnitudes, not the storage orientation.
    """
    g = math.gcd(num, den) or 1
    a, b = num // g, den // g
    return (a, b) if a <= b else (b, a)


def _expected_channel_ratios() -> list[tuple[int, int]]:
    """Cone:cylinder canonical ratios for the BUILT channels, sorted (a multiset).

    Only the first ``active_count`` channels get a cylinder gear (hence a
    cone↔cylinder gear mate), so the live model carries that many channel meshes —
    use the active rows, not the full 20-row table (TEMPORARY; recover at
    active_count=20). Cone gears active_count..19 stay keyed to the shaft and mesh
    nothing, so they contribute no gear mate to compare against.
    """
    cyl = int(_config.machine("gear_train", "fundamental_cone_teeth"))
    return sorted(_canon_ratio(ch["cone_teeth"], cyl) for ch in _config.active_channels())


def assert_no_over_constrained(adapter: Any) -> None:
    """Raise if any top-level component is over-constrained (redundant mates).

    ``assert_components_fully_defined`` already rejects status != 3, but lumps
    over-constrained (4) in with under-defined. This names the redundant-mate
    case explicitly -- the "zero over-defining mates" gate the plan calls for,
    at the assembly level (``get_over_defining_relations`` is sketch-scoped and
    does not apply to mates).
    """
    asm = adapter.currentModel
    adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
    components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
    over = []
    for comp in components:
        _flag(comp, "IComponent2")
        status = int(
            adapter._attempt(lambda c=comp: c.GetConstrainedStatus(), default=-1)
        )
        if status == OVER_CONSTRAINED:
            over.append(str(_read_member(comp, "Name2")))
    if over:
        raise RuntimeError("over-constrained (redundant mates): " + ", ".join(over))
    print("  OK  no over-constrained components (no redundant mates)", flush=True)


def assert_gear_ratios(adapter: Any, name: str) -> None:
    """Assert the live gear-mate ratios equal the config.

    Partitions the unsuppressed gear mates into the single crank drive (a side
    named ``crank-pinion``/``crank-drive-gear``) and the channel cone<->cylinder
    meshes. The crank ratio must reduce to the configured ``crank_drive_ratio``;
    the 20 channel ratios must equal, as a multiset, the configured
    ``[cone_teeth : fundamental]`` reductions. Multiset (not name) matching is
    used for the channels because two channels can share a reduced ratio with
    each other AND with the crank (e.g. 30:120 and 16:64 both reduce to 1:4) --
    the count and the value set are what must hold.
    """
    links = _gear_mate_links(adapter)
    if not links:
        if name == GEAR_OWNER:
            raise RuntimeError(f"{GEAR_OWNER} has no gear mates -- the drive train is broken")
        print(
            f"  ..  {name}: no gear mates at this level "
            f"(they live in the flexible {GEAR_OWNER} sub; verified there)",
            flush=True,
        )
        return

    crank_links: list[tuple[int, int]] = []
    channel_links: list[tuple[int, int]] = []
    for link in links:
        ratio = _canon_ratio(round(link["numerator"]), round(link["denominator"]))
        names = " ".join(side["component"] for side in link["sides"])
        bucket = crank_links if any(t in names for t in _CRANK_GEAR_TOKENS) else channel_links
        bucket.append(ratio)

    problems = []
    crank_num, crank_den = (int(v) for v in _config.machine("gear_train", "crank_drive_ratio"))
    crank_expected = _canon_ratio(crank_num, crank_den)
    if crank_links != [crank_expected]:
        problems.append(
            f"crank drive: live {crank_links} != expected [{crank_expected}]"
        )

    expected = _expected_channel_ratios()
    if sorted(channel_links) != expected:
        problems.append(
            f"channel meshes: live {sorted(channel_links)} != config {expected}"
        )
    if problems:
        raise RuntimeError("; ".join(problems))
    print(
        f"  OK  gear ratios == config (crank {crank_expected}, "
        f"{len(channel_links)} channel meshes)",
        flush=True,
    )


def assert_component_count(adapter: Any, name: str) -> None:
    """Assert the top-level instance count is within the expected band.

    The "N instances -> 1 part" property (no component patterns inflating the
    BOM into N part lines) is structural here -- channels are independent
    *instances of one part file*. This gate is the tripwire that a rebuild did
    not drop or duplicate a channel; the exact count band is in ``_COMPONENT_BAND``.
    """
    band = _COMPONENT_BAND.get(name)
    count = len(component_names(adapter))
    if band is None:
        print(f"  ..  {name}: {count} components (no band configured)", flush=True)
        return
    lo, hi = band
    if not (lo <= count <= hi):
        raise RuntimeError(f"{name}: {count} components outside expected band [{lo}, {hi}]")
    print(f"  OK  {name}: {count} components within [{lo}, {hi}]", flush=True)


def assert_channel_independence(adapter: Any) -> None:
    """Assert the channel assembly holds 20 INDEPENDENT instances of each moving stem.

    The decoherence test the docs ask for (each channel runs at its own harmonic)
    is a motion-solver run -- tracked, not wired here. But its structural
    precondition IS statically checkable: the four moving parts must be 20
    individually-mated instances, not pattern slaves (a pattern instance is a
    rigid, DOF-less copy and could never articulate independently). Counting 20 of
    each stem is the tripwire that a rebuild did not collapse the channels into a
    component pattern -- the single most important "no pattern for moving parts"
    invariant (spec §5 / handoff §8), checked at the level that owns them.
    """
    stems = [_INSTANCE_SUFFIX.sub("", n) for n in component_names(adapter)]
    counts = {stem: stems.count(stem) for stem in _MOVING_CHANNEL_STEMS}
    wrong = {s: c for s, c in counts.items() if c != CHANNELS}
    if wrong:
        raise RuntimeError(
            f"channel moving parts are not {CHANNELS} independent instances: {wrong} "
            f"(a count != {CHANNELS} means a channel was dropped/duplicated, or the "
            f"moving parts were collapsed into a component pattern)")
    print(f"  OK  {CHANNELS} independent instances of each moving stem "
          f"{_MOVING_CHANNEL_STEMS} (not pattern slaves)", flush=True)


async def _verify_isolation_one(adapter: Any, name: str, report: Report) -> None:
    """Subsystem isolation pass for one built (sub)assembly (plan F1).

    Runs the gates that prove a subsystem is sound in isolation -- it opens,
    rebuilds, fully constrains, carries no redundant mates, and is
    interference-free -- plus the gates specific to what that subsystem proves:
    the drive-train's gear ratios (crank reduction + channel meshes) and the
    channel assembly's 20-way instance independence. The motion-dependent rows of
    the F1 table (gear decoherence, cam-follower travel vs truth_model) need the
    Basic Motion solver and stay tracked in the module docstring, not silently
    skipped.
    """
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"{name}:open", f"not built: {sldasm}"))
        print(f"  XX  {sldasm.name} not built -- run doit", flush=True)
        return

    # Isolation means a FRESH session per subsystem: close any prior assembly
    # before opening this one. Accumulating open docs across a multi-assembly run
    # degrades the COM session (the InterferenceDetectionManager came back null on
    # the 5th open), and a subsystem test that depends on what ran before it is not
    # an isolation test.
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    check(f"open {name}", await adapter.open_model(str(sldasm)))
    configs = check("list configurations", await adapter.list_configurations())
    if REST in (configs or []):
        check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- isolation: {name} ({REST} pose) ---")

    report.gate(f"iso:{name}:dof-fully-defined", lambda: assert_components_fully_defined(adapter))
    report.gate(f"iso:{name}:no-over-constrained", lambda: assert_no_over_constrained(adapter))
    report.gate(f"iso:{name}:model-healthy", lambda: assert_model_healthy(adapter, label=name, deep=True))
    report.gate(f"iso:{name}:interference-free", lambda: check_no_interference(adapter))
    report.gate(f"iso:{name}:component-count", lambda: assert_component_count(adapter, name))
    if name == GEAR_OWNER:
        report.gate(f"iso:{name}:gear-ratios", lambda: assert_gear_ratios(adapter, name))
    if name == CHANNEL_OWNER:
        report.gate(f"iso:{name}:channel-independence", lambda: assert_channel_independence(adapter))


async def _verify_static_one(adapter: Any, name: str, report: Report) -> None:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"{name}:open", f"not built: {sldasm}"))
        print(f"  XX  {sldasm.name} not built -- run doit", flush=True)
        return

    # Fresh session per assembly: accumulating open docs across the multi-assembly
    # run degrades the COM session -- the InterferenceDetectionManager comes back
    # null on the 5th open (output, the last in the static set), failing its
    # interference gate spuriously. Reset first, exactly as the isolation and
    # motion suites do (see _verify_isolation_one / _verify_motion_one).
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    check(f"open {name}", await adapter.open_model(str(sldasm)))
    configs = check("list configurations", await adapter.list_configurations())
    if REST in (configs or []):
        check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- verifying {name} ({REST} pose) ---")

    report.gate(f"{name}:dof-fully-defined", lambda: assert_components_fully_defined(adapter))
    report.gate(f"{name}:no-over-constrained", lambda: assert_no_over_constrained(adapter))
    report.gate(f"{name}:model-healthy", lambda: assert_model_healthy(adapter, label=name, deep=True))
    report.gate(f"{name}:interference-free", lambda: check_no_interference(adapter))
    report.gate(f"{name}:gear-ratios", lambda: assert_gear_ratios(adapter, name))
    report.gate(f"{name}:component-count", lambda: assert_component_count(adapter, name))


def _rebuild(adapter: Any) -> None:
    """Re-solve after a CrankDeg change so the pen-driver equation re-evaluates
    the whole partial-sum chain and the mate-driven pose updates."""
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3(), default=None)


def _pen_marker_name(adapter: Any) -> str:
    for n in component_names(adapter):
        if _INSTANCE_SUFFIX.sub("", n) == PEN_MARKER_STEM:
            return n
    raise RuntimeError(f"{PEN_MARKER_STEM!r} instance not in this assembly")


def _tip_y_mm(adapter: Any, marker: str) -> float:
    """Pen-tip Y in the assembly frame (mm) -- the Transform2 translation Y."""
    return component_transform(adapter, marker)[10] * 1000.0


async def _verify_motion_one(adapter: Any, report: Report) -> None:
    """Kinematic pen-driver fidelity (plan F5): sweep CrankDeg, prove the tip traces truth_model.

    output.SLDASM's pen-rod travel mate is equation-linked to a CrankDeg global
    through the chained Fourier sum (installed by pen_driver.install at build).
    Setting CrankDeg and rebuilding must displace the pen-marker tip by exactly
    ``pen_driver.expected_tip_disp_mm(theta)`` from the rest pose -- the computed
    (not force-simulated) summation, mapped onto the physical half-stroke. The
    async sweep runs first (collecting the worst deviation + any stroke-extreme
    interference); the sync gates then assert on what it collected.
    """
    name = MOTION_OWNER
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"motion:{name}:open", f"not built: {sldasm}"))
        print(f"  XX  {sldasm.name} not built -- run doit", flush=True)
        return

    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    check(f"open {name}", await adapter.open_model(str(sldasm)))
    log(f"--- motion: {name} pen-driver sweep (rest {pen_driver.rest_crank_deg():g} deg, "
        f"stroke +-{pen_driver.stroke_half_mm():g} mm) ---")
    marker = _pen_marker_name(adapter)

    # Rest pose: at pen_rest_crank_deg the driver equation subtracts pen_y(rest),
    # so the mate sits at its build datum -- tip0 is the saved render pose.
    await pen_driver.set_crank_deg(adapter, pen_driver.rest_crank_deg())
    _rebuild(adapter)
    tip0 = _tip_y_mm(adapter, marker)

    sweep: list[tuple[float, float, float]] = []  # (theta_deg, got_mm, want_mm)
    for theta in _MOTION_SWEEP_DEG:
        await pen_driver.set_crank_deg(adapter, theta)
        _rebuild(adapter)
        got = _tip_y_mm(adapter, marker) - tip0
        want = pen_driver.expected_tip_disp_mm(math.radians(theta))
        sweep.append((theta, got, want))
        err = abs(got - want)
        flag = "OK " if err <= _MOTION_TOL_MM else "XX "
        print(f"  {flag} CrankDeg={theta:6.1f}  tipDisp={got:+8.4f}  "
              f"want={want:+8.4f}  |err|={err:.2e}", flush=True)
    worst = max((abs(g - w) for _, g, w in sweep), default=0.0)

    # Interference at the two poses furthest from the rest datum (the stroke
    # extremes the pen carriage is most likely to bind at).
    far = sorted(_MOTION_SWEEP_DEG,
                 key=lambda t: abs(pen_driver.expected_tip_disp_mm(math.radians(t))))[-2:]
    interference: list[tuple[float, str]] = []
    for theta in far:
        await pen_driver.set_crank_deg(adapter, theta)
        _rebuild(adapter)
        try:
            check_no_interference(adapter)
        except Exception as exc:  # noqa: BLE001 -- collect, gate below
            interference.append((theta, str(exc)))

    # Leave the doc at its deterministic rest datum (matches the saved pose).
    await pen_driver.set_crank_deg(adapter, pen_driver.rest_crank_deg())
    _rebuild(adapter)

    report.gate(
        f"motion:{name}:tip-traces-truth",
        lambda: _expect(
            worst <= _MOTION_TOL_MM,
            f"pen tip deviates from truth_model by {worst:.3e} mm "
            f"(> {_MOTION_TOL_MM} mm) over the CrankDeg sweep",
        ),
    )
    report.gate(
        f"motion:{name}:stroke-interference-free",
        lambda: _expect(
            not interference,
            f"interference at stroke extremes (CrankDeg deg): {interference}",
        ),
    )
    report.gate(
        f"motion:{name}:dof-fully-defined",
        lambda: assert_components_fully_defined(adapter),
    )


def verify_truth(report: Report) -> None:
    """Analytic self-check of the synthesis math (no SolidWorks).

    Proves ``truth_model`` is a correct band-limited Fourier synthesiser before
    any geometry is asked to reproduce it: harmonics are 1..20, the square-wave
    preset is the right odd-harmonic set and is antisymmetric, the fundamental
    is a pure scaled cosine, and a zero coefficient vector gives a flat pen.
    """
    js = truth_model.harmonics()
    report.gate(
        "truth:harmonics-1..20",
        lambda: _expect(sorted(js) == list(range(1, 21)), f"harmonics={sorted(js)}"),
    )
    sq = truth_model.coefficients("square")
    report.gate(
        "truth:square-odd-only",
        lambda: _expect(
            all((a != 0) == (j % 2 == 1) for a, j in zip(sq, js)),
            "square preset must populate exactly the odd harmonics",
        ),
    )

    def _antisymmetric() -> None:
        # f(x) = Σ (1/j) cos(j x), odd j -> f(x + π) == -f(x) for a square partial set.
        for i in range(1, 12):
            x = i * math.pi / 12.0
            a, b = truth_model.pen_y(x, sq), truth_model.pen_y(x + math.pi, sq)
            _expect(abs(a + b) < 1e-9, f"square not antisymmetric at x={x:.3f}: {a:+.4f} vs {b:+.4f}")

    report.gate("truth:square-antisymmetric", _antisymmetric)

    def _fundamental() -> None:
        fund = truth_model.coefficients("fundamental")
        mag = truth_model.magnify()
        for i in range(13):
            x = i * truth_model.TWO_PI / 13.0
            _expect(
                abs(truth_model.pen_y(x, fund) - mag * math.cos(x)) < 1e-9,
                f"fundamental != magnify·cos at x={x:.3f}",
            )

    report.gate("truth:fundamental-pure-cosine", _fundamental)
    report.gate(
        "truth:zeros-flat-pen",
        lambda: _expect(
            all(y == 0.0 for _, y in truth_model.pen_curve(truth_model.coefficients("zeros"))),
            "zero coefficients must give a flat (zero) pen trace",
        ),
    )

    def _single_channel_term() -> None:
        # The output proof, per channel: setting only a_k=1 must make the pen trace
        # the single term magnify·cos(j_k·x + φ_k) -- the geometry's per-channel
        # sinusoid that Basic Motion is later asked to reproduce (handoff §10).
        mag, js, ph = truth_model.magnify(), truth_model.harmonics(), truth_model.phases_rad()
        for k in range(len(js)):
            e_k = [1.0 if i == k else 0.0 for i in range(len(js))]
            for i in range(7):
                x = i * truth_model.TWO_PI / 7.0
                want = mag * math.cos(js[k] * x + ph[k])
                got = truth_model.pen_y(x, e_k)
                _expect(abs(got - want) < 1e-9,
                        f"channel {k} (j={js[k]}) term wrong at x={x:.3f}: {got:+.4f} vs {want:+.4f}")

    report.gate("truth:single-channel-term", _single_channel_term)

    def _superposition() -> None:
        # The summation IS the machine's job: the pen for an arbitrary coefficient
        # vector must equal the sum of the per-channel single-term traces. This is
        # the linearity the 21-spring force balance realises in hardware and the
        # truth model realises numerically (docs/motion-policy.md).
        js = truth_model.harmonics()
        coeffs = truth_model.coefficients("sawtooth")
        for i in range(11):
            x = i * truth_model.TWO_PI / 11.0
            whole = truth_model.pen_y(x, coeffs)
            parts = sum(
                truth_model.pen_y(x, [c if t == k else 0.0 for t, c in enumerate(coeffs)])
                for k in range(len(js))
            )
            _expect(abs(whole - parts) < 1e-9,
                    f"superposition broken at x={x:.3f}: whole {whole:+.5f} != Σ parts {parts:+.5f}")

    report.gate("truth:superposition", _superposition)

    def _sawtooth_band_limited() -> None:
        # The textbook target vector (all harmonics 1/j) must populate every one of
        # the 20 representable harmonics -- the machine's full bandwidth exercised.
        saw = truth_model.coefficients("sawtooth")
        _expect(all(a > 0 for a in saw) and len(saw) == 20,
                f"sawtooth must fill all 20 harmonics: {saw}")

    report.gate("truth:sawtooth-band-limited", _sawtooth_band_limited)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _num(pattern: str, text: str) -> float:
    """First regex group in ``text`` as a float (raises if the cell changed shape)."""
    m = re.search(pattern, text)
    if not m:
        raise RuntimeError(f"no {pattern!r} in dimension cell {text!r}")
    return float(m.group(1))


def verify_config_vs_dimensions(report: Report) -> None:
    """Cross-check the build config against the cited DIMENSIONS rows (no SolidWorks).

    This is the drift gate that a prose-only DIMENSIONS.md cannot give: the
    numbers the scripts actually build with (machine.yaml / channels.yaml) must
    equal the numbers the research record cites. Each check locates the row by
    chapter + dimension name and parses its value cell, so an edit to either side
    that breaks the agreement fails here.
    """
    doc = gen_dimensions.load_doc()

    def _check(label: str, heading: str, dim: str, fn: Callable[[list[str]], None]) -> None:
        def run() -> None:
            row = gen_dimensions.find_row(doc, heading, dim)
            if row is None:
                raise RuntimeError(f"dimension row not found: {heading} / {dim}")
            fn(row)
        report.gate(label, run)

    _check("dims:cone-DP", "Chapter 12", "Diametral pitch",
           lambda r: _expect(_num(r"DP\s*(\d+(?:\.\d+)?)", r[1]) == _config.machine("gear_train", "diametral_pitch"),
                             f"cone DP: dims {r[1]!r} != machine.yaml {_config.machine('gear_train','diametral_pitch')}"))
    _check("dims:cylinder-teeth", "Chapter 13", "Tooth count",
           lambda r: _expect(_num(r"(\d+)", r[1]) == _config.machine("gear_train", "cylinder_teeth"),
                             f"cylinder teeth: dims {r[1]!r} != machine.yaml"))
    _check("dims:pinion-teeth", "Chapter 25", "Tooth count",
           lambda r: _expect(_num(r"(\d+)", r[1]) == _config.machine("alignment_pinion", "teeth"),
                             f"alignment-pinion teeth: dims {r[1]!r} != machine.yaml"))
    _check("dims:crank-reduction", "Chapter 12", "Crank→cone reduction",
           lambda r: _expect(_num(r"(\d+):1", r[1]) == _crank_reduction(),
                             f"crank reduction: dims {r[1]!r} != crank_drive_ratio {_config.machine('gear_train','crank_drive_ratio')}"))
    _check("dims:cone-teeth-series", "Chapter 12", "Tooth counts",
           lambda r: _expect("120" in r[1] and "step 6" in r[1] and _cone_series_ok(),
                             f"cone tooth series: dims {r[1]!r} != channels.yaml 120-6*index"))
    _check("dims:cone-incline", "Chapter 13", "Cone plan incline",
           lambda r: _expect(abs(_num(r"(\d+\.\d+)", r[1]) - _config.machine("cone_incline", "derived_incline_deg")) < 1e-3,
                             f"cone incline: dims {r[1]!r} != machine.yaml {_config.machine('cone_incline','derived_incline_deg')}"))
    _check("dims:magnify", "Chapter 20", "Magnification",
           lambda r: _expect(_num(r"(\d+)×", r[1]) == _config.machine("output", "magnify_factor"),
                             f"magnify: dims {r[1]!r} != output.magnify_factor"))


def _crank_reduction() -> float:
    num, den = _config.machine("gear_train", "crank_drive_ratio")
    return max(num, den) / min(num, den)


def _cone_series_ok() -> bool:
    fund = int(_config.machine("gear_train", "fundamental_cone_teeth"))
    return all(ch["cone_teeth"] == fund - 6 * ch["index"] for ch in _config.channels())


def verify_dimensions_fresh(report: Report) -> None:
    """Gate that DIMENSIONS.md is not stale relative to dimensions.yaml."""
    def run() -> None:
        doc = gen_dimensions.load_doc()
        rendered = gen_dimensions.render_markdown(doc)
        current = gen_dimensions.DIMENSIONS_MD.read_text(encoding="utf-8")
        _expect(rendered == current, "DIMENSIONS.md is stale -- run gen_dimensions.py")
    report.gate("dims:not-stale", run)


def _declared_part_names() -> set[str]:
    """Every ``PART_NAME = "..."`` declared by a ``build_*.py`` script.

    This is the set of parts the build actually saves -- the ground truth the
    registry is audited against. Scanning the source (not ``cad/out``) keeps the
    audit runnable with no SolidWorks and no prior build.
    """
    names: set[str] = set()
    for script in SCRIPTS_DIR.glob("build_*.py"):
        names.update(_PART_NAME_RE.findall(script.read_text(encoding="utf-8")))
    return names


def _audit_rows() -> tuple[list[dict[str, str]], dict[str, list[str]]]:
    """Build the per-part audit rows plus the cross-cut problem buckets.

    A row is emitted for the union of declared build parts and registry parts,
    so drift in either direction is visible in the CSV. ``problems`` collects the
    hard-fail sets the gates assert on (missing required field, unregistered
    build, orphan registry entry, dangling class reference).
    """
    declared = _declared_part_names()
    registry = _config.parts()
    tol = _config._doc("tolerances")
    tol_classes = set(tol.get("general", {}))
    fit_classes = set(tol.get("fits", {}))

    problems: dict[str, list[str]] = {
        "missing_field": [], "unregistered_build": [], "orphan_registry": [],
        "bad_tolerance_class": [], "bad_fit_class": [],
    }
    rows: list[dict[str, str]] = []
    for part in sorted(declared | set(registry)):
        issues: list[str] = []
        rec = registry.get(part)
        if rec is None:
            issues.append("not in parts.yaml registry")
            problems["unregistered_build"].append(part)
            rows.append({"part": part, "status": "FAIL", "issues": "; ".join(issues),
                         **{c: "" for c in _AUDIT_COLUMNS if c not in ("part", "status", "issues")}})
            continue
        if part not in declared:
            issues.append("registry entry has no build_*.py PART_NAME")
            problems["orphan_registry"].append(part)
        merged = {**_config.parts().get(part, {}), **{k: rec[k] for k in rec}}
        confidence = merged.get("confidence", _config._doc("parts").get("defaults", {}).get("confidence", ""))
        for fieldname in _REQUIRED_PART_FIELDS:
            value = merged.get(fieldname)
            if value in (None, "", "None"):
                issues.append(f"missing {fieldname}")
                problems["missing_field"].append(f"{part}.{fieldname}")
        tclass = merged.get("tolerance_class")
        if tclass and tclass not in tol_classes:
            issues.append(f"unknown tolerance_class {tclass!r}")
            problems["bad_tolerance_class"].append(f"{part}:{tclass}")
        fclass = merged.get("fit_class")
        if fclass and fclass not in fit_classes:
            issues.append(f"unknown fit_class {fclass!r}")
            problems["bad_fit_class"].append(f"{part}:{fclass}")
        rows.append({
            "part": part,
            "number": str(merged.get("number", "")),
            "material": str(merged.get("material", "")),
            "tolerance_class": str(tclass or ""),
            "fit_class": str(fclass or ""),
            "process": str(merged.get("process", "")),
            "confidence": str(confidence or ""),
            "status": "FAIL" if issues else "OK",
            "issues": "; ".join(issues),
        })
    return rows, problems


def verify_tolerance_audit(report: Report) -> None:
    """Tolerance / metadata audit (handoff §14.2 Gate E), emits a CSV report.

    Reconciles the parts.yaml registry against the parts the build scripts
    actually save, and asserts every part carries the custom-property fields
    (material / tolerance class / process) with class names that resolve in
    tolerances.yaml. Writes ``cad/out/reports/tolerance_audit.csv`` whether or
    not the gates pass, so the artifact always reflects the current state.
    """
    rows, problems = _audit_rows()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / "tolerance_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    n_fit = sum(1 for r in rows if r.get("fit_class"))
    print(f"  ..  tolerance audit -> {csv_path} ({len(rows)} parts, "
          f"{n_fit} with a fit class)", flush=True)

    report.gate(
        "audit:registry-matches-builds",
        lambda: _expect(
            not problems["unregistered_build"] and not problems["orphan_registry"],
            "registry/build drift -- "
            f"built but unregistered: {problems['unregistered_build'] or 'none'}; "
            f"registered but never built: {problems['orphan_registry'] or 'none'}",
        ),
    )
    report.gate(
        "audit:required-fields",
        lambda: _expect(
            not problems["missing_field"],
            f"parts missing required metadata: {problems['missing_field']}",
        ),
    )
    report.gate(
        "audit:class-refs-resolve",
        lambda: _expect(
            not problems["bad_tolerance_class"] and not problems["bad_fit_class"],
            "dangling class refs -- "
            f"tolerance_class: {problems['bad_tolerance_class'] or 'none'}; "
            f"fit_class: {problems['bad_fit_class'] or 'none'}",
        ),
    )


def verify_amplitude_preset(report: Report) -> None:
    """The amplitude-bar stations in channels.yaml obey the machine.yaml preset law.

    machine.yaml ``amplitude:`` declares the waveform the bars encode and the
    fundamental station; channels.yaml ``amplitude_mm`` is the per-channel a_j the
    geometry is actually built to. This gate asserts the two cannot drift: for the
    ``square`` preset a_j = fundamental_station_mm / harmonic_n on the ODD harmonics
    and 0 on the even ones, every station is within the seesaw travel, and the
    vector matches what truth_model synthesises from the same file (so the computed
    pen curve always equals the as-built bar stations).
    """
    preset = _config.machine("amplitude", "preset")
    fundamental = float(_config.machine("amplitude", "fundamental_station_mm"))
    max_travel = float(_config.machine("amplitude", "max_travel_mm"))
    rows = _config.channels()

    def _law() -> None:
        # `neutral` (TEMPORARY): every bar reset to its neutral position, a_j = 0.
        if preset == "neutral":
            for ch in rows:
                got = float(ch["amplitude_mm"])
                _expect(abs(got) < 5e-4,
                        f"channel {ch['index']}: neutral preset requires amplitude_mm 0, got {got}")
            return
        _expect(preset == "square", f"amplitude preset is {preset!r}, not 'square'/'neutral' (update this gate)")
        for ch in rows:
            n = ch["harmonic_n"]
            want = fundamental / n if n % 2 == 1 else 0.0
            got = float(ch["amplitude_mm"])
            _expect(abs(got - want) < 5e-4,
                    f"channel {ch['index']} (n={n}): amplitude_mm {got} != 80/n law {want:.4f}")

    report.gate("amplitude:preset-law", _law)
    report.gate(
        "amplitude:within-travel",
        lambda: _expect(
            all(abs(float(ch["amplitude_mm"])) <= max_travel for ch in rows),
            f"a bar station exceeds the ±{max_travel} mm seesaw travel: "
            f"{[ch['amplitude_mm'] for ch in rows if abs(float(ch['amplitude_mm'])) > max_travel]}",
        ),
    )

    def _matches_truth() -> None:
        # truth_model.coefficients('config') reads the same amplitude_mm vector, so the
        # computed curve is guaranteed to be what the geometry is set to (F3 / handoff §10).
        a_yaml = _config.amplitudes()
        a_truth = truth_model.coefficients("config")
        _expect(a_yaml == a_truth,
                f"truth_model 'config' vector {a_truth} != channels.yaml {a_yaml}")

    report.gate("amplitude:truth-reads-same-vector", _matches_truth)


async def build(adapter: Any) -> dict[str, str]:
    """Entry for ``run_build``: dispatch to the requested suite(s)."""
    suite, names = _ARGS.suite, _ARGS.names
    report = Report()

    if suite in ("static", "all"):
        for name in names:
            await _verify_static_one(adapter, name, report)
    if suite == "isolation":
        for name in names:
            await _verify_isolation_one(adapter, name, report)
    if suite in ("motion", "all"):
        await _verify_motion_one(adapter, report)
    if suite in ("truth", "all"):
        verify_truth(report)
    if suite in ("config", "all"):
        verify_config_vs_dimensions(report)
        verify_dimensions_fresh(report)
        verify_tolerance_audit(report)
        verify_amplitude_preset(report)

    _print_summary(report)
    if report.failed:
        raise RuntimeError(f"{len(report.failed)} gate(s) failed")
    return {"verify": f"{len(report.passed)} gate(s) passed ({suite})"}


def _print_summary(report: Report) -> None:
    print("\n" + "=" * 64, flush=True)
    print(f"VERIFY SUMMARY: {len(report.passed)} passed, {len(report.failed)} failed", flush=True)
    for label, why in report.failed:
        print(f"  FAIL  {label}: {why}", flush=True)
    print("=" * 64, flush=True)


def _built_assemblies() -> list[str]:
    # Skip SolidWorks lock files (``~$<name>.SLDASM``), the transient temp file SW
    # creates while a doc is open -- it is not a built assembly and won't open.
    return sorted(p.stem for p in OUT_SLDASM.glob("*.SLDASM") if not p.name.startswith("~$"))


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="assembly stem(s); default = all built")
    ap.add_argument("--suite", default="static",
                    choices=["static", "truth", "config", "isolation", "motion",
                             "all"])
    args = ap.parse_args()
    if not args.names:
        # truth/config need no model; motion targets MOTION_OWNER (output);
        # static/isolation/all default to all built.
        if args.suite in ("truth", "config"):
            args.names = []
        elif args.suite == "motion":
            args.names = [MOTION_OWNER]
        else:
            args.names = _built_assemblies()
    return args


if __name__ == "__main__":
    _ARGS = _parse_args()
    if _ARGS.suite in ("truth", "config"):
        # No SolidWorks needed -- run directly without connecting.
        _report = Report()
        if _ARGS.suite == "truth":
            verify_truth(_report)
        else:
            verify_config_vs_dimensions(_report)
            verify_dimensions_fresh(_report)
            verify_tolerance_audit(_report)
            verify_amplitude_preset(_report)
        _print_summary(_report)
        sys.exit(1 if _report.failed else 0)
    sys.exit(run_build(build))

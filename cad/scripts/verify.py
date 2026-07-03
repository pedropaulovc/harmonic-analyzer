r"""Standalone validation harness -- the verify pass IS the test suite.

The build scripts already gate themselves (``_common`` raises on free DOF,
interference, rebuild errors). ``verify.py`` promotes those gates into one
runnable, re-runnable acceptance check that opens an *already-built* assembly
and proves it is sound, plus the assertions a build script cannot make about
itself: that the gear ratios in the live model equal the config, and that the
component count is the expected "N instances -> 1 part" envelope.

Suites (``--suite``). The doit wrapper groups them by SolidWorks-dependence:
the SW suites are ``verify:<suite>`` tasks (on the COM spine); the no-SW ones are
``check:<suite>`` tasks (parallel). There is no aggregate "all" -- ``doit build``
is the single fully-safe entry point that runs every gate.

  soundness (default) NEEDS SOLIDWORKS. Open the Default pose and run, collecting
                      ALL failures: DOF fully-defined, no over-constrained
                      component, model healthy (deep), interference-free, gear
                      ratios == config, BOM/part-count envelope.
  subsystems          NEEDS SOLIDWORKS. Subsystem-SPECIFIC structural gates (plan
                      F1) NOT already covered by soundness -- currently just the
                      channel assembly's 20-way moving-stem instance independence.
                      soundness already opens every (sub)assembly standalone and
                      runs the shared health battery (DOF / over-constrained /
                      model-healthy / interference / gear-ratios / component-count)
                      on each, so this pass no longer repeats it (that duplication
                      was the biggest COM-spine time sink; see release-perf memory).
  kinematics          NEEDS SOLIDWORKS. Kinematic pen-driver fidelity (plan F5):
                      open pen.SLDASM, sweep the CrankDeg global, and assert
                      the pen-marker tip traces truth_model.pen_y (mapped to the
                      physical half-stroke) with NO force solver -- the computed-
                      not-simulated summation realised through the equation-driven
                      pen-rod mate (pen_driver.py / docs/motion-policy.md).
  math                no-SolidWorks analytic self-check of ``truth_model``: the
                      synthesis math is symmetric / band-limited / correct.
  config              no-SolidWorks cross-checks: build config (machine/channels)
                      vs the cited DIMENSIONS rows, DIMENSIONS.md freshness, and
                      the tolerance/metadata audit (parts.yaml <-> build scripts;
                      emits cad/out/reports/tolerance_audit.csv).

Unlike the build gates (fail-fast), ``soundness``/``subsystems`` run every gate
and report the full set of failures at the end, so one run tells you everything
wrong.

Run (SolidWorks already open for any suite touching geometry)::

    uv run python cad\scripts\verify.py [name ...] [--suite soundness|math|...]

``name`` defaults to every built assembly in ``cad/out/sldasm`` (drive-train,
harmonic-analyzer). ``math``/``config`` need no SolidWorks and no assembly.

NOT YET WIRED (tracked, not silently skipped):
  * Stepped-crank interference across the full gear train (turning the real
    crank through the gear train) needs the Basic Motion solver -- the lock mates
    that key the cone cluster are outside the gear-mate graph, so a kinematic
    rotate desyncs the train (see docs/motion-policy.md). The pen-vs-truth_model
    output proof, by contrast, IS wired: ``--suite kinematics`` drives the pen
    kinematically off the CrankDeg global (no train rotation needed).
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import _config
import gen_dimensions
import pen_driver
import truth_model
import _telemetry
from _common import (
    OUT_SLDASM,
    check,
    log,
    run_build,
)
from _assembly import (
    assert_components_fully_defined,
    assert_expected_free_dof,
    assert_model_healthy,
    check_no_interference,
    component_names,
    component_transform,
    is_locked_build,
)
from _common import (  # component iteration helpers (read-only)
    _flag_only,
    _read_member,
)

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
MOTION_OWNER = "pen"
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
# so harmonic-analyzer's count is its 7 child subassemblies + 1 loose part (the
# measuring-stick; the spare gear rides inside paper-drive) -- NOT the ~340
# flattened parts. Bands measured live (verify.py --suite subsystems)
# with margin.
# The channel + drive-train bands scale with the built channel count N (the
# TEMPORARY active_count): channel = 7N + 4 (N×{rocker,rod,bar,lever,spring} + 2
# shafts + 4 ball-mounts + 2 bushings per inter-channel gap), drive-train = 40 + N
# (full 20-gear cone stack + crank/structure ≈ 32 + the restored ch25 pinion
# swing rig's 8: alignment-pinion, 2 brackets, 2 pivot blocks, pivot shaft,
# lift rod, handle -- ch30 GT re-anchor, plus N cylinder gears). Both
# reproduce the measured N=20 bands (164, 60) and stay correct at N=3.
_N_CH = _config.active_count()
_COMPONENT_BAND = {
    "frame": (11, 16),          # measured 13 (9 structure + 4 lag-screw hold-downs)
    "drive-train": (40 + _N_CH - 4, 40 + _N_CH + 4),  # N=20 -> (56,64), measured 60
    "channel": (8 * _N_CH + 4 - 6, 8 * _N_CH + 4 + 6),  # N=20 -> (158,170), measured 164
    # The former monolithic output split by function (no per-channel parts here);
    # bands tightened to the measured green-build counts (verify:subsystems).
    "summing": (7, 9),          # ch 18-19, measured 8 (knife-stay removed: never in the real device)
    "magnifier": (10, 12),      # ch 20-21, measured 11
    "pen": (6, 8),              # ch 24, measured 7
    "paper-drive": (85, 89),    # ch 22-23-25, measured 87 (27 placed + 60-link chain;
    # the ch30 GT re-anchor moved the crank to (122.8, 144.96) and the chain plane
    # to z -155 -- the shorter drop shrank the loop 70 -> 60 links at pitch 6.2559;
    # placed count unchanged, all moves were repositions)
    "harmonic-analyzer": (7, 9),  # measured 8: 7 subassemblies + 1 loose part (measuring-stick)
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
        """Run ``fn`` inside its own span; record pass or the exception text.

        Never propagates: a gate failure is recorded on the span (ERROR status +
        exception event) and captured as data, so the suite keeps running while
        the trace still attributes the failure to this gate — no silent gap.
        """
        with _telemetry.span("gate", label=label) as sp:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001 -- a gate failure is data, not a crash
                self.failed.append((label, str(exc)))
                sp.record_exception(exc)
                sp.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
                _telemetry.error(f"GATE FAILED [{label}]: {exc}")
                return
            self.passed.append(label)
            _telemetry.success(f"GATE PASSED [{label}]")

    async def agate(self, label: str, fn: Callable[[], Any]) -> None:
        """Async sibling of :meth:`gate`: ``await`` the coroutine ``fn()`` returns.

        Used by gates that drive async adapter mate-ops (suppress/unsuppress for the
        free-DOF closure check) rather than only sync COM reads. Same record-don't-
        propagate contract and span shape as :meth:`gate`.
        """
        with _telemetry.span("gate", label=label) as sp:
            try:
                await fn()
            except Exception as exc:  # noqa: BLE001 -- a gate failure is data, not a crash
                self.failed.append((label, str(exc)))
                sp.record_exception(exc)
                sp.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
                _telemetry.error(f"GATE FAILED [{label}]: {exc}")
                return
            self.passed.append(label)
            _telemetry.success(f"GATE PASSED [{label}]")

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
    # Span the gate as a tree of named sub-steps instead of one opaque ~90 s span
    # (this gate was a single unspanned 88 s gap for `channel`). The deep rebuild
    # and the per-component status scan are the two costs -- give each its own
    # child span so the wall-clock is attributable, mirroring gate.dof/gate.health.
    with _telemetry.span("gate.over_constrained") as gsp:
        with _telemetry.span("over.rebuild"):
            adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        with _telemetry.span("over.scan") as ssp:
            components = adapter._attempt(lambda: asm.GetComponents(True), default=None) or []
            over = []
            for comp in components:
                # Flag ONLY GetConstrainedStatus (zero-arg); Name2 is a property
                # read (issue #87 -- not the 165-method IComponent2 flag).
                _flag_only(comp, "GetConstrainedStatus")
                status = int(
                    adapter._attempt(lambda c=comp: c.GetConstrainedStatus(), default=-1)
                )
                if status == OVER_CONSTRAINED:
                    over.append(str(_read_member(comp, "Name2")))
            ssp.set_attribute("components", len(components))
            ssp.set_attribute("over_constrained", len(over))
        gsp.set_attribute("components", len(components))
        gsp.set_attribute("over_constrained", len(over))
        if over:
            raise RuntimeError("over-constrained (redundant mates): " + ", ".join(over))
    _telemetry.success("no over-constrained components (no redundant mates)")


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
    # Span the gate; reading the live gear mates walks the MateGroup over the COM
    # bridge and is the whole cost (~80 s for drive-train) -- it was a single
    # unspanned 82 s gap. Give the read its own child span so that wall-clock is
    # attributable, mirroring gate.dof/gate.health.
    with _telemetry.span("gate.gear_ratios") as gsp:
        with _telemetry.span("gear.read_links"):
            links = _gear_mate_links(adapter)
        gsp.set_attribute("gear_mates", len(links))
        if not links:
            if name == GEAR_OWNER:
                raise RuntimeError(f"{GEAR_OWNER} has no gear mates -- the drive train is broken")
            _telemetry.debug(
                f"{name}: no gear mates at this level "
                f"(they live in the flexible {GEAR_OWNER} sub; verified there)"
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
        gsp.set_attribute("crank_meshes", len(crank_links))
        gsp.set_attribute("channel_meshes", len(channel_links))
        if problems:
            raise RuntimeError("; ".join(problems))
    _telemetry.success(
        f"gear ratios == config (crank {crank_expected}, "
        f"{len(channel_links)} channel meshes)"
    )


def assert_component_count(adapter: Any, name: str) -> None:
    """Assert the top-level instance count is within the expected band.

    The "N instances -> 1 part" property (no component patterns inflating the
    BOM into N part lines) is structural here -- channels are independent
    *instances of one part file*. This gate is the tripwire that a rebuild did
    not drop or duplicate a channel; the exact count band is in ``_COMPONENT_BAND``.
    """
    # Span the gate; component_names() re-marshals the whole top-level component
    # list over the COM bridge (~85 s for `channel`) and was a single unspanned
    # gap. Give that read its own child span, mirroring gate.dof/gate.health.
    with _telemetry.span("gate.component_count") as gsp:
        band = _COMPONENT_BAND.get(name)
        with _telemetry.span("count.read"):
            count = len(component_names(adapter))
        gsp.set_attribute("count", count)
        if band is None:
            _telemetry.debug(f"{name}: {count} components (no band configured)")
            return
        lo, hi = band
        if not (lo <= count <= hi):
            raise RuntimeError(f"{name}: {count} components outside expected band [{lo}, {hi}]")
    _telemetry.success(f"{name}: {count} components within [{lo}, {hi}]")


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
    _telemetry.success(
        f"{CHANNELS} independent instances of each moving stem "
        f"{_MOVING_CHANNEL_STEMS} (not pattern slaves)"
    )


# --- Freshness guard ----------------------------------------------------------
# Run OUTSIDE the doit DAG (a bare ``python verify.py ...``), this harness opens
# whatever ``.SLDASM`` is on disk -- there is NO dependency edge forcing a rebuild
# first, so an artefact whose sources moved scores SILENTLY. That is exactly how a
# never-rebuilt pre-FootSeat ``frame`` (8 components, no lag-screws) sailed through
# every health/DOF/interference gate and only tripped component-count: the geometry
# was old, not wrong. The guard below reuses doit's OWN ledger
# (``cad/out/.doit.db``) and ``ContentChecker``, so a "stale" verdict here is
# precisely what ``doit`` would rebuild -- building through doit clears it. Set
# ``HARMONIC_VERIFY_ALLOW_STALE=1`` to verify a deliberately hand-built model.
def _import_dodo():
    """dodo.py lives at the repo root (off cad/scripts' path). Importing it gives us
    the SAME build-graph functions doit uses to derive each task's file_dep + target,
    plus doit's exact ContentChecker -- so the guard's verdict can never disagree with
    ``doit``'s own rebuild decision. verify.py always runs as its own process
    (standalone or a doit-spawned subprocess), so this never races the orchestrator."""
    repo_root = str(SCRIPTS_DIR.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    import dodo

    return dodo


def _producers(name: str) -> list[tuple[str, list[str], str]]:
    """``(task, current file_deps, target)`` for ``assembly:<name>`` plus every part /
    sub-assembly it references, transitively. The deps and target are recomputed from
    the build graph (NOT read back from the saved ledger), so a dep ADDED since the
    last build -- a new hold-down part, a post-assembly hook, a freshly-mapped config
    -- is still checked, exactly as ``doit`` would (Codex review). Dashed display name
    -> underscored task stems (``frame`` -> ``assembly:frame``)."""
    from _buildgraph import references_of  # local: keep top-level import light

    dodo = _import_dodo()

    def is_assembly(stem: str) -> bool:
        return (SCRIPTS_DIR / f"build_{stem}_assembly.py").exists()

    out: list[tuple[str, list[str], str]] = []
    visited: set[str] = set()
    stack = [name.replace("-", "_")]
    while stack:
        stem = stack.pop()
        if stem in visited:
            continue
        visited.add(stem)
        if is_assembly(stem):
            out.append((f"assembly:{stem}",
                        dodo._assembly_file_deps(stem), dodo._sldasm(stem)))
            stack.extend(references_of(stem))
        else:
            script = SCRIPTS_DIR / f"build_{stem}.py"
            out.append((f"part:{stem}",
                        dodo._part_file_deps(script, stem), dodo._sldprt(stem)))
    return out


def _stale_inputs(name: str) -> list[str]:
    """Producer tasks whose current ``file_dep`` set / content no longer matches the
    on-disk artefact built THROUGH doit (empty == current). Reuses doit's exact
    ``ContentChecker`` so it never disagrees with ``doit``'s rebuild decision; its
    mtime-changed path compares the CONTENT digest, so checkout/cache-restore mtime
    churn is not a false positive. Raises on a machinery failure (missing/corrupt
    db, import error) so the caller can downgrade to a warning -- never a silent pass."""
    import json

    db = json.loads((OUT_SLDASM.parent / ".doit.db").read_text(encoding="utf-8"))
    return _stale_in_db(db, _producers(name))


def _stale_in_db(db: dict, producers: list[tuple[str, list[str], str]]) -> list[str]:
    """Pure core of :func:`_stale_inputs` (I/O only to stat/digest the deps + targets):
    ``producers`` = ``[(task, current_file_deps, target)]``. Returns one message per
    task that ``doit`` would rebuild -- never built, target missing, a dep that
    disappeared, a NEW dep absent from the last build, or a dep whose content changed.
    Split out so it is unit-testable without a real ``.doit.db`` (test_verify_freshness)."""
    checker = _import_dodo().ContentChecker()
    stale: list[str] = []
    for task, deps, target in producers:
        entry = db.get(task)
        if entry is None:
            stale.append(f"{task} (never built through doit)")
            continue
        if not os.path.exists(target):  # doit rebuilds a task with a missing target
            stale.append(f"{task}: target {Path(target).name} missing")
            continue
        for dep in deps:  # CURRENT deps, so a dep added since last build is caught
            if not os.path.exists(dep):
                stale.append(f"{task}: missing dep {Path(dep).name}")
                break
            state = entry.get(dep)
            if state is None:
                stale.append(f"{task}: new dep {Path(dep).name} (not in last build)")
                break
            if checker.check_modified(dep, os.stat(dep), state):
                stale.append(f"{task}: {Path(dep).name} changed since build")
                break
    return stale


def _assert_fresh(name: str, report: Report) -> bool:
    """False (and a recorded failure) when ``name``'s on-disk artefacts are stale vs
    their sources. A guard-machinery failure WARNs and passes -- it must never break
    a working verify. ``HARMONIC_VERIFY_ALLOW_STALE=1`` bypasses entirely."""
    if os.environ.get("HARMONIC_VERIFY_ALLOW_STALE") == "1":
        return True
    try:
        stale = _stale_inputs(name)
    except Exception as exc:  # noqa: BLE001 -- guard must not break a working verify
        _telemetry.warn(f"{name}: freshness check skipped ({exc})")
        return True
    if not stale:
        return True
    report.failed.append((
        f"{name}:fresh-inputs",
        f"stale on-disk artefact -- run `doit assembly:{name.replace('-', '_')}` "
        f"(or HARMONIC_VERIFY_ALLOW_STALE=1): " + "; ".join(stale),
    ))
    _telemetry.error(f"{name}: STALE artefact, NOT verified -- {'; '.join(stale)}")
    return False


async def _verify_isolation_one(adapter: Any, name: str, report: Report) -> None:
    """Subsystem-SPECIFIC structural gates for one built (sub)assembly (plan F1).

    The ``soundness`` pass already opens EVERY built (sub)assembly standalone (a
    fresh session per assembly) and runs the shared health battery on each --
    DOF fully-defined, no redundant mates, model-healthy (deep), interference-free,
    gear-ratios, component-count. Re-running that whole battery here (the historical
    "isolation" suite) re-opened all eight assemblies and repeated the single most
    expensive COM work in the pipeline -- the deep model-healthy rebuild alone is
    ~140 s for the top assembly -- for ZERO added coverage (see the release-perf
    memory note). This pass now runs ONLY the gate ``soundness`` does not: the
    channel assembly's 20-way moving-stem instance independence (the "no component
    pattern for moving parts" invariant). ``soundness`` runs first on the COM spine,
    so the shared battery is always proven before this pass.

    The motion-dependent rows of the F1 table (gear decoherence, cam-follower
    travel vs truth_model) need the Basic Motion solver and stay tracked in the
    module docstring, not silently skipped.
    """
    if name != CHANNEL_OWNER:
        return  # soundness owns the shared battery; only `channel` has a unique gate

    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"iso:{name}:open", f"not built: {sldasm}"))
        _telemetry.error(f"{sldasm.name} not built -- run doit")
        return

    if not _assert_fresh(name, report):
        return  # stale on-disk artefact: fail loud rather than verify old geometry

    # Fresh session: close any prior assembly before opening this one (accumulating
    # open docs degrades the COM session -- the InterferenceDetectionManager came
    # back null on the 5th open).
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    # Span the open+activate (see _verify_static_one): the per-assembly load is
    # COM work that otherwise sits in an unspanned gap before the gates.
    async with _telemetry.aspan("verify.open", name=name):
        check(f"open {name}", await adapter.open_model(str(sldasm)))
        configs = check("list configurations", await adapter.list_configurations())
        if REST in (configs or []):
            check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- isolation: {name} ({REST} pose) ---")

    # Instance independence is read straight off the component tree (GetComponents),
    # populated on open -- no rebuild needed (soundness already rebuilt this assembly).
    report.gate(f"iso:{name}:channel-independence", lambda: assert_channel_independence(adapter))


def _expected_free_dof(name: str) -> int:
    """Free operational DOF expected in ``name``'s AS-SAVED model.

    drive-train frees the crank spin (1 DOF); channel frees 3 DOF per active
    channel (rocker swing + connecting-rod follow + amplitude-bar slide), each a
    suppressed PARK_* park driver, when built `free` (the default); a `locked`
    build re-engages them -> 0. Read straight from cad/config/machine/
    build_lock.yaml -- the same source of truth the build used, and the freshness
    guard (`_assert_fresh`) guarantees the saved model matches that config. Every
    other assembly stays fully defined (0). The literal accessor tokenises
    build_lock.yaml into this gate's recipe deps, so flipping the flag re-runs
    verify too.
    """
    if name == "drive-train":
        return 0 if is_locked_build(_config.machine("build_lock", "drive_train")) else 1
    if name == "channel":
        if is_locked_build(_config.machine("build_lock", "channel")):
            return 0
        return 3 * _config.active_count()
    return 0


async def _verify_static_one(adapter: Any, name: str, report: Report) -> None:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"{name}:open", f"not built: {sldasm}"))
        _telemetry.error(f"{sldasm.name} not built -- run doit")
        return

    if not _assert_fresh(name, report):
        return  # stale on-disk artefact: fail loud rather than verify old geometry

    # Fresh session per assembly: accumulating open docs across the multi-assembly
    # run degrades the COM session -- the InterferenceDetectionManager comes back
    # null after several opens, failing its interference gate spuriously. Reset
    # first, exactly as the isolation and
    # motion suites do (see _verify_isolation_one / _verify_motion_one).
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    # Span the open+activate: loading and re-posing the document is 8-27 s of COM
    # work per assembly that otherwise sits in an unspanned gap between gates.
    async with _telemetry.aspan("verify.open", name=name):
        check(f"open {name}", await adapter.open_model(str(sldasm)))
        configs = check("list configurations", await adapter.list_configurations())
        if REST in (configs or []):
            check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- verifying {name} ({REST} pose) ---")

    free_dof = _expected_free_dof(name)
    if free_dof:
        # Default-free build: assert EXACTLY the expected operational DOF are free
        # via the park-driver closure check (it re-engages then restores the free
        # pose, leaving the model as-shipped for the gates below).
        await report.agate(
            f"{name}:dof-expected-free",
            lambda: assert_expected_free_dof(adapter, free_dof),
        )
    else:
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

    pen.SLDASM's pen-rod travel mate is equation-linked to a CrankDeg global
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
        _telemetry.error(f"{sldasm.name} not built -- run doit")
        return

    if not _assert_fresh(name, report):
        return  # stale on-disk artefact: fail loud rather than verify old geometry

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
        emit = _telemetry.success if err <= _MOTION_TOL_MM else _telemetry.error
        emit(f"CrankDeg={theta:6.1f}  tipDisp={got:+8.4f}  "
             f"want={want:+8.4f}  |err|={err:.2e}")
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


def verify_spring_base(report: Report) -> None:
    """The canonical channel-spring-installed body must equal the neutral gap.

    At the neutral amplitude pose every channel's return spring spans the same
    lever-eye -> summing-plate gap, so the assembly should mate the ONE canonical
    ``channel-spring-installed`` body across all 20 channels with no generated
    ``stretchNN`` variant. That only holds if the part's built body
    (``SPRING_BASE_BODY``, from the static ``LEVER_EYE_Y``) matches the live
    neutral gap the kinematic solver computes. If the lever anchor drifts (e.g.
    another OD re-anchor), they diverge and the assembly silently spawns a
    stretch00 again -- this gate fails loud first (SolidWorks-free; pure trig).
    """

    def _matches_neutral_gap() -> None:
        import build_channel_assembly as channel  # local: keeps verify import light

        st = channel.solve_state(0.0)
        phi0 = math.radians(st["lever_tilt"])
        hole_x_0 = channel.FULCRUM[0] + channel.LEVER_SPRING_X * math.cos(phi0)
        neutral_body = channel._spring_spec(0.0, hole_x_0)["body"]
        base = channel.SPRING_BASE_BODY
        _expect(
            abs(neutral_body - base) < 0.05,
            f"channel-spring-installed body {base:.3f} != neutral gap body "
            f"{neutral_body:.3f} (>= 0.05 mm): neutral would mate a generated "
            f"stretch variant, not the canonical spring -- update LEVER_EYE_Y in "
            f"build_channel_spring_installed.py to the re-anchored neutral eye",
        )

    report.gate("spring:neutral-body-canonical", _matches_neutral_gap)


def verify_base_footprint(report: Report) -> None:
    """Every base-mounted drive-train component's plan footprint must sit fully
    on the base TOP plate (SolidWorks-free; pure module constants).

    This is the gate class the 2026-07-02 slab regression slipped through: the
    crank pedestal was re-placed with over half its foot past the base edge and
    all 48 gates stayed green -- nothing asserted "a mount bolted to the base
    stands ON the base". Interference can't see it (air interferes with
    nothing) and the DOF/health gates don't know where the base ends. Extend
    the mount list when a new base-standing component joins the drive train
    (frame components live in build_frame_assembly and centre themselves on the
    base datums, so they are not swept here).
    """

    def _mounts_on_plate() -> None:
        import build_arbor_pedestal as arbor_post
        import build_cone_pivot_post as pivot_post
        import build_crank_pedestal as pedestal
        import build_drive_train_assembly as train
        import build_harmonic_base as base

        half_len, half_wid = base.TOP_LENGTH / 2.0, base.TOP_WIDTH / 2.0
        ppost = train.cone_station(train.PIVOT_POST_STATION)
        # (label, centre x, centre z, plan half-x, plan half-z); circular feet
        # use the radius both ways, the rotated pivot post is circular so its
        # incline never changes the footprint.
        mounts = (
            ("crank-pedestal", train.X_CRANK, train.PEDESTAL_Z,
             pedestal.PEDESTAL_DIA / 2.0, pedestal.PEDESTAL_DIA / 2.0),
            ("cone-pivot-post", ppost[0], ppost[2],
             pivot_post.BLOCK_DIA / 2.0, pivot_post.BLOCK_DIA / 2.0),
            ("arbor-pedestal", train.X_DRUM, -train.ARBOR_PEDESTAL_Z,
             arbor_post.BLOCK_WIDTH / 2.0, arbor_post.BLOCK_DEPTH / 2.0),
        )
        for label, cx, cz, hx, hz in mounts:
            _expect(
                abs(cx) + hx <= half_len + 1e-9 and abs(cz) + hz <= half_wid + 1e-9,
                f"{label} foot hangs off the base top plate: plan centre "
                f"({cx:.2f}, {cz:.2f}) half-extents ({hx:.2f}, {hz:.2f}) vs "
                f"plate (+-{half_len:.2f}, +-{half_wid:.2f})",
            )

    report.gate("footprint:drive-train-mounts-on-base", _mounts_on_plate)


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


def _declared_part_names() -> set[str]:
    """Every ``PART_NAME = "..."`` declared by a machine part build script.

    This is the set of parts the build actually saves -- the ground truth the
    registry is audited against. Scanning the source (not ``cad/out``) keeps the
    audit runnable with no SolidWorks and no prior build. The script set is
    ``_buildgraph.part_scripts()`` -- the same canonical part-script list the
    DAG uses, so assemblies, post-hooks and off-graph standalone repros
    (``NON_PART_SCRIPTS``) are excluded here exactly as they are from the graph.
    """
    from _buildgraph import part_scripts

    names: set[str] = set()
    for script in part_scripts():
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
        writer.writerows(rows)  # type: ignore[arg-type]  # dict[str, str] is structurally compatible; DictWriter stubs use Literal key union
    n_fit = sum(1 for r in rows if r.get("fit_class"))
    _telemetry.debug(f"tolerance audit -> {csv_path} ({len(rows)} parts, "
                     f"{n_fit} with a fit class)")

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

    if suite == "soundness":
        for name in names:
            await _verify_static_one(adapter, name, report)
    if suite == "subsystems":
        for name in names:
            await _verify_isolation_one(adapter, name, report)
    if suite == "kinematics":
        await _verify_motion_one(adapter, report)
    if suite == "math":
        verify_truth(report)
        verify_spring_base(report)
        verify_base_footprint(report)
    if suite == "config":
        verify_config_vs_dimensions(report)
        verify_tolerance_audit(report)
        verify_amplitude_preset(report)

    _print_summary(report)
    if report.failed:
        raise RuntimeError(f"{len(report.failed)} gate(s) failed")
    return {"verify": f"{len(report.passed)} gate(s) passed ({suite})"}


def _print_summary(report: Report) -> None:
    emit = _telemetry.success if not report.failed else _telemetry.error
    emit(f"VERIFY SUMMARY: {len(report.passed)} passed, {len(report.failed)} failed")
    for label, why in report.failed:
        _telemetry.error(f"FAIL {label}: {why}")


def _built_assemblies() -> list[str]:
    # Skip SolidWorks lock files (``~$<name>.SLDASM``), the transient temp file SW
    # creates while a doc is open -- it is not a built assembly and won't open.
    return sorted(p.stem for p in OUT_SLDASM.glob("*.SLDASM") if not p.name.startswith("~$"))


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="assembly stem(s); default = all built")
    ap.add_argument("--suite", default="soundness",
                    choices=["soundness", "subsystems", "kinematics", "math",
                             "config"])
    args = ap.parse_args()
    if not args.names:
        # math/config need no model; kinematics targets MOTION_OWNER (pen);
        # soundness/subsystems default to all built. (There is no aggregate
        # "all" suite -- `doit build` is the one fully-safe entry point.)
        if args.suite in ("math", "config"):
            args.names = []
        elif args.suite == "kinematics":
            args.names = [MOTION_OWNER]
        else:
            args.names = _built_assemblies()
    return args


if __name__ == "__main__":
    _ARGS = _parse_args()
    # Advertise the verify SUITE as this process's telemetry resource so the Aspire
    # "resource" column reads e.g. "verify-kinematics" instead of the umbrella name.
    # Fallback-only: under the spine dodo already set the matching OTEL_SERVICE_NAME
    # (see _stage_name), so this is a no-op that keeps it; standalone it self-labels.
    _telemetry.set_service(f"verify-{_ARGS.suite}")
    if _ARGS.suite in ("math", "config"):
        # No SolidWorks needed -- run directly without connecting.
        _report = Report()
        if _ARGS.suite == "math":
            verify_truth(_report)
            verify_spring_base(_report)
            verify_base_footprint(_report)
        else:
            verify_config_vs_dimensions(_report)
            verify_tolerance_audit(_report)
            verify_amplitude_preset(_report)
        _print_summary(_report)
        sys.exit(1 if _report.failed else 0)
    sys.exit(run_build(build))

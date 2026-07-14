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

  soundness (default) NEEDS SOLIDWORKS. Open the Default pose on every built
                      (sub)assembly and run, collecting ALL failures: one shared
                      re-solve, then DOF fully-defined / no over-constrained
                      component / model healthy (deep) / interference-free, plus
                      the channel assembly's 20-way moving-stem instance
                      independence (folded in from the retired `subsystems` suite).
                      gear ratios == config is verified at the RELEASE preflight,
                      not on every build.
  kinematics          NEEDS SOLIDWORKS. Kinematic pen-driver fidelity (plan F5):
                      open pen.SLDASM (first author the travel drive mate
                      transiently from the recorded DOF manifest and install
                      the F5 equation -- the shipped model has neither, its
                      travel is a live free DOF; discarded unsaved), sweep the CrankDeg
                      global, and assert the pen-marker tip traces
                      truth_model.pen_y (mapped to the physical half-stroke)
                      with NO force solver -- the computed-not-simulated
                      summation realised through the equation-driven pen-rod
                      mate (pen_driver.py / docs/motion-policy.md).
  math                no-SolidWorks analytic self-check of ``truth_model``: the
                      synthesis math is symmetric / band-limited / correct.
  config              no-SolidWorks cross-checks: build config (machine/channels)
                      vs the cited DIMENSIONS rows, DIMENSIONS.md freshness, and
                      the tolerance/metadata audit (parts.yaml <-> build scripts;
                      emits cad/out/reports/tolerance_audit.csv).

Unlike the build gates (fail-fast), ``soundness`` runs every gate and reports the
full set of failures at the end, so one run tells you everything wrong.

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
    active_configuration_name,
    check,
    log,
    run_build,
)
from _assembly import (
    _ALLOWED_FREE_STEMS,
    _export_assembly_images,
    assert_components_fully_defined,
    assert_free_dof_necessity,
    assert_model_healthy,
    assert_saved_rebuild_clean,
    check_no_interference,
    component_names,
    component_transform,
    repair_dangling_mates,
    save_assembly_in_place,
    whats_wrong,
)
from _assembly_postbuild import (
    author_dof_drives,
    discard_open_documents,
    load_dof_manifest,
)
from _common import (  # component iteration helpers (read-only)
    _early_bound,
    _read_member,
)

# solidworks_mcp internals reused read-only: the live gear-mate ratios are not
# exposed by any public tool (list_mates returns name/type/suppressed only), so
# the gear-ratio gate reads them through the same helper the kinematic driver
# uses. Read-only -- it walks the MateGroup and returns numerators/denominators.
from solidworks_mcp.adapters.solidworks.assembly import _gear_mate_links

REST = "Default"  # the deterministic, fully-defined, render/photo-gated pose
OVER_CONSTRAINED = 4  # swConstrainedStatus_e
DANGLING_ENTITY_NOT_FOUND = 48  # What's Wrong: mate reference PID not found

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
# Physically-built channels. machine.yaml channels.active_count is a
# BUILD-SPEED KNOB: it caps the per-channel mechanism to the first N during
# debugging iterations (20 = the full machine, the default); the gates below
# (instance independence, channel gear meshes, component bands) track that N
# so a reduced build stays fully verified at its own scale.
CHANNELS = _config.active_count()
# The kinematic pen driver (plan F5) lives in this sub: its pen-rod travel mate
# is equation-linked to a CrankDeg global through the chained Fourier sum. The
# shipped model leaves the travel a live free DOF, so the motion suite authors
# the drive mate transiently from the recorded DOF manifest and installs the
# equation before the sweep (discarded unsaved). It sweeps CrankDeg and proves
# the pen tip traces truth_model.pen_y -- the computed-not-simulated summation,
# with no force solver (docs/motion-policy.md).
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
# Paper-feed reduction gear mate (paper-drive): the 12T third gear driving the
# 120T reducer disc (the disc part is named rack-pinion for historical reasons).
_FEED_GEAR_TOKENS = ("rack-pinion",)
_FEED_GEAR_RATIO = (1, 10)  # 12T third gear : 120T reducer disc
# Expected TOP-LEVEL component-count band per assembly. REFERENCE DATA ONLY -- the
# live component-count gate was removed (every failure it ever raised was a stale
# band or a gate bug, never a real regression). Kept because the counts document
# each assembly's structure and size the mock in test_verify_telemetry.
# component_names counts top-level components only (GetComponents(TopLevelOnly)),
# so harmonic-analyzer's count is its 7 child subassemblies + 1 loose part (the
# measuring-stick; the spare gear rides inside paper-drive) -- NOT the ~340
# flattened parts. Bands measured live on a green build, with margin.
# The channel + drive-train bands scale with the built channel count N (the
# active_count build-speed knob): channel = 7N + 4 (N×{rocker,rod,bar,lever,spring} + 2
# shafts + 4 ball-mounts + 2 bushings per inter-channel gap), drive-train = 61 + N
# (full 20-gear cone stack + crank/structure ≈ 33 -- including the cone swing
# platform + tip block that joined the pivot post in the p1 swing rework, and
# the NORTH arbor pedestal + its foot screw (PR8, ch12 img09) -- + the ch25
# pinion swing rig's 21: alignment-pinion, 2 brackets, 2 pivot
# blocks, pivot shaft, lift rod, lever, handle, return spring (PR4), 2
# cam-follower pins (PR5, edge studs since PR8), steel arbor, 4 block screws
# + 2 foot screws (PR7), 2 eccentric cam collars (PR8), + the PR2 cone-swing
# hardware 6: lock knob, pivot screw, swing-stop screw, tip
# bushing/adjuster/pinch screw, MINUS the crank-pedestal the merged column
# absorbed, plus N cylinder gears). Both reproduce the measured N=20 bands
# (164, 77 pre-PR8 -> 81) and stay correct at N=3.
_N_CH = _config.active_count()
_COMPONENT_BAND = {
    "frame": (11, 16),          # measured 13 (9 structure + 4 lag-screw hold-downs)
    "drive-train": (61 + _N_CH - 4, 61 + _N_CH + 4),  # N=20 -> (77,85), expected 81
    "channel": (8 * _N_CH + 4 - 6, 8 * _N_CH + 4 + 6),  # N=20 -> (158,170), measured 164
    # The former monolithic output split by function (no per-channel parts here);
    # bands tightened to the measured green-build counts (verify:subsystems).
    "summing": (7, 9),          # ch 18-19, measured 8 (knife-stay removed: never in the real device)
    "magnifier": (11, 13),      # ch 20-21, measured 12 (+lever-wire, 2026-07-04)
    "pen": (7, 9),              # ch 24, measured 8 (+pen-wire, 2026-07-04)
    "paper-drive": (118, 126),  # ch 22-23-25, expected 122 (54 placed + 68-link
    # chain; the paper-drive rework replaced the two rails + pinion-bar topology
    # with one bar + two-piece clamps + the hanging-platen furniture and its
    # 22 lock-mated fillister screws, and the lower knob centre lengthened the
    # loop 60 -> 68 links)
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
    use the active rows, not the full 20-row table (active_count is the
    build-speed knob; 20 = the full machine). Cone gears active_count..19 stay
    keyed to the shaft and mesh nothing, so they contribute no gear mate to
    compare against.
    """
    cyl = int(_config.machine("gear_train", "fundamental_cone_teeth"))
    return sorted(_canon_ratio(ch["cone_teeth"], cyl) for ch in _config.active_channels())


def assert_no_over_constrained(adapter: Any, *, resolve: bool = True) -> None:
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
        # ``resolve=False``: soundness already re-solved once after open and does
        # not mutate the model between gates, so this rebuild would be redundant.
        with _telemetry.span("over.rebuild"):
            if resolve:
                adapter._attempt(lambda: asm.ForceRebuild3(False), default=None)
        with _telemetry.span("over.scan") as ssp:
            asm_h = _early_bound(asm, "IAssemblyDoc")  # IAssemblyDoc for GetComponents; keep `asm` for ForceRebuild3
            components = adapter._attempt(lambda: asm_h.GetComponents(True), default=None) or []
            over = []
            for comp in components:
                # Wrap once as IComponent2 so GetConstrainedStatus invokes its
                # known DISPID; Name2 remains a property read.
                comp = _early_bound(comp, "IComponent2", "GetConstrainedStatus")
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
        # A rack-pinion mate comes back from _gear_mate_links as a gear-type mate
        # (SolidWorks stores it as one), but it couples LINEAR<->rotary motion, so
        # it carries no integer tooth ratio -- its stored GearRatio is a small
        # pitch fraction that rounds to 0/0. paper-drive has exactly one (the
        # platen rack-pinion, #189). Keep only true ROTATIONAL meshes (both tooth
        # counts round to > 0); those are the crank + channel gear meshes this
        # gate validates. Without this, paper-drive's lone rack-pinion is neither
        # crank nor channel and trips the comparison as a spurious (0,0) mesh.
        rotational = [
            link for link in links
            if round(link["numerator"]) > 0 and round(link["denominator"]) > 0
        ]
        gsp.set_attribute("gear_mates", len(rotational))
        if not rotational:
            if name == GEAR_OWNER:
                raise RuntimeError(f"{GEAR_OWNER} has no gear mates -- the drive train is broken")
            if name == "paper-drive":
                # A missing/suppressed 12T:120T feed mesh must fail loud, not
                # take the harmless no-gears path below (codex #196).
                raise RuntimeError(
                    "paper-drive has no gear mates -- the paper-feed train is broken"
                )
            _telemetry.debug(
                f"{name}: no rotational gear meshes at this level "
                f"(rack-pinion/none; the crank + channel meshes live in the "
                f"flexible {GEAR_OWNER} sub, verified there)"
            )
            return

        crank_links: list[tuple[int, int]] = []
        feed_links: list[tuple[int, int]] = []
        channel_links: list[tuple[int, int]] = []
        for link in rotational:
            ratio = _canon_ratio(round(link["numerator"]), round(link["denominator"]))
            names = " ".join(side["component"] for side in link["sides"])
            if any(t in names for t in _CRANK_GEAR_TOKENS):
                crank_links.append(ratio)
            elif any(t in names for t in _FEED_GEAR_TOKENS):
                feed_links.append(ratio)
            else:
                channel_links.append(ratio)

        problems = []
        crank_num, crank_den = (int(v) for v in _config.machine("gear_train", "crank_drive_ratio"))
        crank_expected = _canon_ratio(crank_num, crank_den)
        if name == "paper-drive":
            # The single paper-feed reduction mesh (12T third gear : 120T disc);
            # paper-drive carries no crank/channel gear mates.
            if feed_links != [_FEED_GEAR_RATIO]:
                problems.append(
                    f"paper feed mesh: live {feed_links} != expected [{_FEED_GEAR_RATIO}]"
                )
            if crank_links or channel_links:
                problems.append(
                    f"unexpected non-feed gear mates in paper-drive: "
                    f"crank {crank_links}, channel {channel_links}"
                )
        else:
            if crank_links != [crank_expected]:
                problems.append(
                    f"crank drive: live {crank_links} != expected [{crank_expected}]"
                )
            expected = _expected_channel_ratios()
            if sorted(channel_links) != expected:
                problems.append(
                    f"channel meshes: live {sorted(channel_links)} != config {expected}"
                )
            if feed_links:
                problems.append(
                    f"unexpected paper-feed gear mates in {name}: {feed_links}"
                )
        gsp.set_attribute("crank_meshes", len(crank_links))
        gsp.set_attribute("feed_meshes", len(feed_links))
        gsp.set_attribute("channel_meshes", len(channel_links))
        if problems:
            raise RuntimeError("; ".join(problems))
    _telemetry.success(
        f"gear ratios == config ({len(crank_links)} crank, {len(feed_links)} feed,"
        f" {len(channel_links)} channel meshes)"
    )


def assert_channel_independence(adapter: Any) -> None:
    """Assert ``channel.SLDASM`` is exactly one independently mated mechanism.

    Multiplicity now belongs to the top-level flexible-subassembly pattern. The
    child must therefore contain one occurrence of each moving family; finding
    20 here means the former flat bank was accidentally retained and the machine
    would duplicate it 20x again.
    """
    stems = [_INSTANCE_SUFFIX.sub("", n) for n in component_names(adapter)]
    counts = {stem: stems.count(stem) for stem in _MOVING_CHANNEL_STEMS}
    wrong = {s: c for s, c in counts.items() if c != 1}
    if wrong:
        raise RuntimeError(
            f"single-channel child does not contain one of each moving family: {wrong}"
        )
    _telemetry.success(
        f"one independently mated channel with moving stems {_MOVING_CHANNEL_STEMS}"
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


def _expected_free_dof(name: str) -> int:
    """Free operational DOF expected in ``name``'s AS-SAVED model.

    drive-train frees the crank spin, the cone-platform swing, the pinion
    engage swing and the lift-rod/cam spin (4 DOF, PR8); channel frees 3 DOF
    per active channel (rocker swing + connecting-rod follow + amplitude-bar
    slide). Each freed DOF's drive spec is recorded in the assembly's DOF
    manifest, never authored. Every other assembly stays fully defined (0).
    """
    if name == "drive-train":
        return 4
    if name == "channel":
        return 3
    if name == "magnifier":
        # The freed lever knife-rock + the articulated lever-wire's swing/spin;
        # the wheel is COUPLED by the WIRE-1 yoke (no DOF of its own).
        return 3
    if name == "paper-drive":
        # The freed crank (T12) spin; the knob T24 is belt-coupled and the platen
        # is rack-coupled (no DOF of their own).
        return 1
    if name == "summing":
        # The freed lever knife-edge rock; the boss-hook is lock-mated and rides it.
        return 1
    if name == "pen":
        # The freed carriage travel; the marker + pen-wire are lock-mated and
        # ride it. The F5 pen-driver equation is installed transiently by
        # verify:kinematics on the replayed drive mate.
        return 1
    return 0


# One component family per freed DOF that must ITSELF read under-constrained
# (assert_free_dof_necessity required_stems): the aggregate count check alone
# cannot distinguish which DOF is free.
_REQUIRED_FREE_STEMS = {
    "drive-train": ("crankshaft", "cone-swing-platform",
                    "pinion-bracket", "pinion-lift-rod"),
    # Rocker swing + rod follow + bar amplitude, plus the channel lever which
    # must read under-constrained WITH the chain (closed by the J5 foot-on-arc
    # coupling off the rocker -- a frozen lever means the coupling died).
    "channel": ("rocker-arm", "connecting-rod", "amplitude-bar", "channel-lever"),
    # Three freed DOF (lever knife-rock + wire swing/spin); the yoke-coupled
    # wheel must read under-constrained WITH them, else the coupling died --
    # and so must the lock-mated bracket (it AFFIXES the rod to the rocking
    # summing bar; a regression to grounded re-creates the collar clipping,
    # codex #201).
    "magnifier": ("magnifying-lever", "magnifying-wheel", "lever-wire",
                  "magnifying-bracket"),
    # One freed DOF (the crank T12 spin). paper-drive is handled by INSTANCE, not
    # this stem (see _required_free_instances) -- three transgear-removable siblings
    # share the stem, so a stem check passes even if T12 is pinned and T24/T18 is
    # loose (codex #189 :679). Kept as reference data only.
    "paper-drive": ("transgear-removable",),
    # One freed DOF (the lever knife-edge rock); the lock-mated boss-hook must
    # read under-constrained WITH it (a grounded/fixed regression would freeze
    # the counter-spring anchor while the lever still swings, codex #201).
    "summing": ("summing-lever", "boss-hook"),
    # One freed DOF (the carriage travel); the lock-mated marker + pen-wire
    # must ride it -- with the neutral preset the motion sweep reads
    # got == want == 0 even if the marker were disconnected (codex #201).
    "pen": ("pen-rod", "pen-marker", "pen-wire"),
}

def _required_free_instances(name: str) -> tuple[str, ...]:
    """Exact component instances that must read under-constrained, sourced from
    the DOF manifest (each freed-DOF drive's ``verify`` target). Used where a
    stem is shared by several instances and only a SPECIFIC one carries the freed
    DOF -- paper-drive's three ``transgear-removable`` siblings, of which only the
    T12 crank is the operational input (codex #189 :679). Empty when there is no
    manifest sidecar."""
    out: list[str] = []
    for spec in load_dof_manifest(name):
        target = spec.get("verify") or []
        if target and isinstance(target[0], str):
            out.append(target[0])
    return tuple(out)


def _fail(msg: str) -> None:
    """Raise inside a ``report.gate`` lambda (which cannot contain a statement)."""
    raise RuntimeError(msg)


def _dangling_faults(adapter: Any) -> list[str]:
    """Return active-assembly mate faults eligible for the opt-in repair.

    What's Wrong code 48 is the observed persistent-reference failure from a
    cache-restored assembly whose mates were authored against another seat's
    part PIDs.  Do not broaden this to arbitrary rebuild errors:
    ``AutoMateRepair`` is an operator-chosen escape hatch for that narrow case,
    not a general-purpose way to make a red model green.
    """
    return [
        f"{label}:{fault_name}"
        for label, _model, fault_name, code in _deep_mate_faults(adapter)
        if code == DANGLING_ENTITY_NOT_FOUND
    ]


def _fault_name(value: Any) -> str:
    """Normalize the real ``whats_wrong`` string contract and test doubles."""
    if isinstance(value, str):
        return value
    return str(_read_member(value, "Name") or "?")


def _deep_mate_faults(adapter: Any) -> list[tuple[str, Any, str, int]]:
    """Return non-warning faults from the active assembly and child assemblies."""
    top = adapter.currentModel
    top_asm = _early_bound(top, "IAssemblyDoc")  # IAssemblyDoc for GetComponents; keep `top` for the `model is top` identity compare
    targets: list[tuple[str, Any]] = [("top", top)]
    seen: set[str] = set()
    components = adapter._attempt(lambda: top_asm.GetComponents(False), default=None) or []
    for component in components:
        component = _early_bound(component, "IComponent2", "GetModelDoc2")
        instance = str(_read_member(component, "Name2") or "?")
        if "/" in instance:
            continue
        model = adapter._attempt(lambda c=component: c.GetModelDoc2(), default=None)
        if model is None or model is top:
            continue
        if int(adapter._attempt(lambda m=model: m.GetType(), default=0) or 0) != 2:
            continue  # swDocASSEMBLY only; parts cannot own a MateGroup
        key = str(adapter._attempt(lambda m=model: m.GetPathName(), default="") or instance)
        if key in seen:
            continue
        seen.add(key)
        targets.append((instance, model))

    faults: list[tuple[str, Any, str, int]] = []
    for label, model in targets:
        for feature, code, warning in whats_wrong(adapter, model):
            if not warning:
                faults.append((label, model, _fault_name(feature), int(code)))
    return faults


def _activate_document(adapter: Any, model: Any, label: str) -> Any:
    """Bring ``model`` to the foreground before any selection-based COM call."""
    title = str(_read_member(model, "GetTitle") or "")
    if not title:
        raise RuntimeError(f"{label}: cannot activate a document without a title")
    # Early-bound ISldWorks::ActivateDoc3 returns (model, errors): pass literal 0
    # for the [out] Errors and consume the tuple. The retval is a DYNAMIC dispatch
    # (no resultCLSID in the wrapper), so rebind it to IModelDoc2 before storing it
    # as currentModel -- else its .Extension.SelectByID2(..., None, ...) re-triggers
    # the VT_NULL callout failure on the dynamic path.
    result = adapter._attempt(
        lambda: adapter.swApp.ActivateDoc3(title, False, 2, 0), default=None
    )
    if not result:
        raise RuntimeError(f"{label}: ActivateDoc3({title!r}) failed")
    activated, errors = result
    if activated is None or int(errors) != 0:
        raise RuntimeError(
            f"{label}: ActivateDoc3({title!r}) failed (errors={errors})"
        )
    activated = _early_bound(activated, "IModelDoc2")
    adapter.currentModel = activated
    return activated


def _repair_cache_dangles(adapter: Any, name: str) -> Any:
    """Repair code-48 mate dangles, rebuild, and prove the active model clean.

    The caller still runs the complete DOF/interference/deep-health battery and
    saves only after every gate passes.  A successful repair remains local; it
    is deliberately not republished under the foreign remote-cache key.
    """
    faults = _deep_mate_faults(adapter)
    before = [fault for fault in faults if fault[3] == DANGLING_ENTITY_NOT_FOUND]
    if not before:
        return None
    ineligible = [f"{label}:{mate} [{code}]" for label, _doc, mate, code in faults if code != DANGLING_ENTITY_NOT_FOUND]
    if ineligible:
        raise RuntimeError(
            f"{name}: refusing AutoMateRepair because non-48 faults coexist: "
            + ", ".join(ineligible)
        )
    top = adapter.currentModel
    with _telemetry.span("verify.auto_repair", name=name, faults=len(before)) as sp:
        repaired = 0
        repaired_docs: dict[str, tuple[str, Any]] = {}
        try:
            for label, model, _mate, _code in before:
                key = str(
                    adapter._attempt(lambda m=model: m.GetPathName(), default="")
                    or label
                )
                if key in repaired_docs:
                    continue
                stem = name if model is top else Path(key).stem
                active = _activate_document(adapter, model, stem)
                repaired_docs[key] = (stem, active)
                repaired += repair_dangling_mates(adapter, active)
                adapter._attempt(
                    lambda m=active: m.ForceRebuild3(False), default=None
                )
        finally:
            _activate_document(adapter, top, name)
        rebuilt = adapter._attempt(
            lambda: top.ForceRebuild3(False), default=None
        )
        remaining = [
            f"{label}:{mate} [{code}]"
            for label, _doc, mate, code in _deep_mate_faults(adapter)
        ]
        sp.set_attribute("repaired", repaired)
        sp.set_attribute("remaining_faults", len(remaining))
        if repaired <= 0 or remaining:
            raise RuntimeError(
                f"{name}: AutoMateRepair did not produce a clean assembly "
                f"(reported repaired={repaired}, remaining={remaining})"
            )
        _telemetry.event(
            "verify.auto_repair.completed", asm=name, repaired=repaired
        )
        _telemetry.warn(
            f"{name}: opt-in AutoMateRepair re-bound {repaired} mate(s); "
            "running the full soundness battery before saving locally"
        )
        return {
            "rebuilt": rebuilt,
            "documents": tuple(repaired_docs.values()),
        }


def _assert_soundness_health(adapter: Any, name: str, rebuilt: Any) -> None:
    """Run deep health and give code-48 failures an actionable retry."""
    try:
        assert_model_healthy(adapter, label=name, deep=True, rebuilt=rebuilt)
    except RuntimeError as exc:
        if "[48]" in str(exc):
            raise RuntimeError(
                f"{exc}; cache/PID mate dangle detected — retry explicitly with "
                f"`uv run python cad/scripts/verify.py {name} --suite soundness "
                "--auto-repair` (the repair can re-bind wrong topology, so it "
                "is never automatic)"
            ) from exc
        raise


def _run_soundness_battery(
    adapter: Any, name: str, report: Report, rebuilt: Any
) -> None:
    """Run the complete per-document soundness battery on the active assembly."""
    free_dof = _expected_free_dof(name)
    if free_dof:
        insts = _required_free_instances(name) if name == "paper-drive" else ()
        if name == "paper-drive" and not insts:
            report.gate(
                f"{name}:dof-free-necessity",
                lambda: _fail(
                    "free paper-drive but .paper-drive.dof.json records no "
                    "crank_spin instance -- stale/missing DOF manifest; refusing "
                    "the weak stem fallback. Rebuild paper-drive to regenerate it."
                ),
            )
        else:
            stems = () if insts else _REQUIRED_FREE_STEMS.get(name, ())
            report.gate(
                f"{name}:dof-free-necessity",
                lambda: assert_free_dof_necessity(
                    adapter,
                    free_dof,
                    resolve=False,
                    required_stems=stems,
                    required_instances=insts,
                    allowed_stems=_ALLOWED_FREE_STEMS.get(name, ()),
                ),
            )
    else:
        report.gate(
            f"{name}:dof-fully-defined",
            lambda: assert_components_fully_defined(adapter, resolve=False),
        )
    report.gate(
        f"{name}:no-over-constrained",
        lambda: assert_no_over_constrained(adapter, resolve=False),
    )
    report.gate(
        f"{name}:model-healthy",
        lambda: _assert_soundness_health(adapter, name, rebuilt),
    )
    report.gate(f"{name}:interference-free", lambda: check_no_interference(adapter))
    if name == CHANNEL_OWNER:
        report.gate(
            f"{name}:channel-independence",
            lambda: assert_channel_independence(adapter),
        )


async def _verify_static_one(
    adapter: Any, name: str, report: Report, *, auto_repair: bool = False
) -> None:
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
        # Capture the persisted flag before configuration activation, whose adapter
        # path rebuilds and can clear the evidence in memory.
        report.gate(
            f"{name}:saved-rebuild-clean",
            lambda: assert_saved_rebuild_clean(adapter, name),
        )
        configs = check("list configurations", await adapter.list_configurations())
        if REST in (configs or []) and active_configuration_name(adapter) != REST:
            check(f"activate {REST}", await adapter.set_active_configuration(REST))
    log(f"--- verifying {name} ({REST} pose) ---")

    # Single shared re-solve for the whole static battery. The DOF, over-constrained
    # and model-healthy gates below EACH used to ForceRebuild3 this same model (three
    # deep rebuilds where one suffices -- ~50 s x3 on the top assembly). The static
    # suite never mutates the model between gates (they only READ GetComponents /
    # GetConstrainedStatus / GetWhatsWrong / interferences), so re-solve ONCE here and
    # let each gate read the resolved status (``resolve=False``). The rebuild result
    # (False => a hard health fault) is handed to model-healthy so its
    # ForceRebuild3-returned-False check is preserved.
    with _telemetry.span("verify.rebuild", name=name):
        rebuilt = adapter._attempt(
            lambda: adapter.currentModel.ForceRebuild3(False), default=None
        )

    repaired = False
    if auto_repair and _dangling_faults(adapter):
        state: dict[str, Any] = {}

        def _repair() -> None:
            state["rebuilt"] = _repair_cache_dangles(adapter, name)

        failures_before = len(report.failed)
        report.gate(f"{name}:auto-repair", _repair)
        if len(report.failed) != failures_before:
            return
        repair_result = state["rebuilt"]
        rebuilt = repair_result["rebuilt"]
        repaired_documents = repair_result["documents"]
        repaired = True

    assembly_failures_before = len(report.failed)

    free_dof = _expected_free_dof(name)
    if free_dof:
        # The freed operational DOF have no driver mates in the saved model
        # (see AGENTS.md "Default-free DOF"). Prove NECESSITY -- the DOF are
        # genuinely free, each freed DOF's component family itself reading
        # under-constrained (the aggregate count alone passes on the crank
        # chain even with the swing pinned -- codex 2026-07-04) -- and the
        # EXACT SET: no component outside the allowed coupled families may
        # read under-constrained (an unintended freedom fails here, the
        # replacement for the retired release park-closure proof).
        # paper-drive alone has a SHARED stem (three transgear-removable siblings),
        # so target the EXACT T12 crank instance from the recorded DOF manifest
        # (codex #189 :679); every other assembly keeps its unique stem families
        # (unchanged -- their DOF map to distinct part names).
        insts = _required_free_instances(name) if name == "paper-drive" else ()
        if name == "paper-drive" and not insts:
            # A free paper-drive MUST have recorded its crank_spin instance in
            # .paper-drive.dof.json. A missing/stale sidecar would silently fall
            # back to the weak shared-stem check (which :679 showed passes even with
            # T12 pinned and a T24/T18 sibling loose). Fail loud instead (codex #189).
            report.gate(
                f"{name}:dof-free-necessity",
                lambda: _fail(
                    "free paper-drive but .paper-drive.dof.json records no crank_spin "
                    "instance -- stale/missing DOF manifest; refusing the weak stem "
                    "fallback. Rebuild paper-drive to regenerate it."),
            )
        else:
            stems = () if insts else _REQUIRED_FREE_STEMS.get(name, ())
            report.gate(
                f"{name}:dof-free-necessity",
                lambda: assert_free_dof_necessity(
                    adapter, free_dof, resolve=False,
                    required_stems=stems, required_instances=insts,
                    allowed_stems=_ALLOWED_FREE_STEMS.get(name, ())),
            )
    else:
        report.gate(
            f"{name}:dof-fully-defined",
            lambda: assert_components_fully_defined(adapter, resolve=False),
        )
    report.gate(
        f"{name}:no-over-constrained",
        lambda: assert_no_over_constrained(adapter, resolve=False),
    )
    report.gate(
        f"{name}:model-healthy",
        lambda: _assert_soundness_health(adapter, name, rebuilt),
    )
    report.gate(f"{name}:interference-free", lambda: check_no_interference(adapter))
    # component-count REMOVED: every historical failure of that gate was a stale band
    # or a gate bug (never a real regression), so it cost more in false alarms than it
    # ever caught. The expected counts survive as reference data in `_COMPONENT_BAND`.
    # gear-ratios is DEMOTED to the release preflight (preflight_release.py): it is the
    # single most expensive gate and re-proves a property fixed by the tooth-count
    # config that check:math already validates analytically -- so it no longer runs on
    # every build, only against the shipped artefact at release.
    # channel-independence (the "no component pattern for moving parts" invariant) is
    # folded in here: soundness already opens `channel`, so the retired
    # verify:subsystems suite's one unique gate runs on this same open model.
    if name == CHANNEL_OWNER:
        report.gate(
            f"{name}:channel-independence",
            lambda: assert_channel_independence(adapter),
        )

    if repaired:
        if len(report.failed) != assembly_failures_before:
            _telemetry.warn(
                f"{name}: repaired mate state NOT saved because a soundness gate failed"
            )
            discard_open_documents(adapter)
            adapter.currentModel = None
            return
        else:
            # Persist each document whose own MateGroup was repaired. SaveReferenced
            # remains deliberately off: unrelated child artifacts still belong to
            # their producing tasks. Temporarily route the adapter to the explicit
            # document so both Save3 and image export target the child, not the parent.
            parent = adapter.currentModel
            rendered: set[str] = set()
            for repaired_name, model in repaired_documents:
                activated: dict[str, Any] = {}
                report.gate(
                    f"{repaired_name}:auto-repair-activate",
                    lambda n=repaired_name, m=model: activated.setdefault(
                        "model", _activate_document(adapter, m, n)
                    ),
                )
                if len(report.failed) != assembly_failures_before:
                    discard_open_documents(adapter)
                    adapter.currentModel = None
                    return
                active = activated["model"]
                if active is not parent:
                    rebuilt_child = adapter._attempt(
                        lambda m=active: m.ForceRebuild3(False), default=None
                    )
                    child_failures_before = len(report.failed)
                    _run_soundness_battery(
                        adapter, repaired_name, report, rebuilt_child
                    )
                    if len(report.failed) != child_failures_before:
                        _telemetry.warn(
                            f"{repaired_name}: repaired child NOT saved because "
                            "its standalone soundness battery failed"
                        )
                        discard_open_documents(adapter)
                        adapter.currentModel = None
                        return
                report.gate(
                    f"{repaired_name}:auto-repair-save",
                    lambda n=repaired_name, m=active: save_assembly_in_place(
                        adapter, n, geometry_changed=True, model=m
                    ),
                )
                if len(report.failed) != assembly_failures_before:
                    discard_open_documents(adapter)
                    adapter.currentModel = None
                    return
                await report.agate(
                    f"{repaired_name}:auto-repair-renders",
                    lambda n=repaired_name: _export_assembly_images(
                        adapter, n, ("front", "top", "isometric")
                    ),
                )
                rendered.add(repaired_name)
                if len(report.failed) != assembly_failures_before:
                    discard_open_documents(adapter)
                    adapter.currentModel = None
                    return
                if active is not parent:
                    _activate_document(adapter, parent, name)
            # A child repair can change the parent-level visual solution even when
            # the parent MateGroup itself was untouched, so refresh its renders too.
            if name not in rendered:
                await report.agate(
                    f"{name}:auto-repair-renders",
                    lambda: _export_assembly_images(
                        adapter, name, ("front", "top", "isometric")
                    ),
                )


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
    through the chained Fourier sum (authored + installed transiently here from
    the recorded DOF manifest; the shipped model leaves the travel a live free
    DOF).
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
    try:
        # The shipped pen.SLDASM has neither the travel mate nor the F5
        # equation (the carriage is a live free DOF). Author the drive mate
        # transiently from the recorded DOF manifest (DRIVE_pen_travel),
        # install the equation on it, then sweep as usual. The doc is mutated
        # in memory only -- verify never saves, and the ``finally`` below
        # discards it.
        travel = [s for s in load_dof_manifest(name) if s.get("key") == "pen_travel"]
        if len(travel) != 1:
            report.failed.append((
                f"motion:{name}:dof-manifest",
                f"expected exactly 1 recorded pen_travel drive spec, found "
                f"{len(travel)} -- rebuild pen",
            ))
            _telemetry.error(f"{name}: pen_travel drive spec missing/ambiguous")
            return
        (travel_mate,) = await author_dof_drives(adapter, travel)
        base_mm = abs(float(travel[0]["params"]["distance"]))
        param = adapter._attempt(
            lambda: adapter.currentModel.Parameter(f"D1@{travel_mate}"), default=None)
        if param is None:
            report.failed.append((
                f"motion:{name}:pen-driver-install",
                f"cannot read D1@{travel_mate} on the transient travel mate",
            ))
            _telemetry.error(f"{name}: cannot read D1@{travel_mate}")
            return
        base_doc = float(_read_member(param, "Value"))  # IPS doc -> inches
        info = await pen_driver.install(
            adapter, travel_mate, base_doc, base_doc / base_mm)
        log(f"pen driver (transient): {info['links']}-link chain, scale "
            f"{info['scale_mm_per_unit']:.4g} mm/unit, rest {info['rest_deg']:g} deg")
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
    finally:
        # The sweep leaves the doc DIRTY (CrankDeg edits + rebuilds, plus the
        # transient DRIVE_pen_travel mate + the F5 equations), and
        # a bare CloseAllDocuments(True) can still pop the save modal for a
        # dirty referenced child (the preflight/cut_release discard rationale).
        # Discard by title on EVERY exit -- including the early returns above --
        # so no later open/close hits the modal (codex #201). verify never saves.
        discard_open_documents(adapter)


# Magnifier live-chain sweep (WIRE 1). Small angles: the real machine's lever
# tip arc is ~6 mm at r~215 (~1.6 deg of knife rock, engineerguy video 4/4).
# POSITIVE offsets only: the rock rest angle sits at exactly 0 deg, and an angle
# dimension cannot go negative -- a signed sweep would flip branches at 0.
_CHAIN_SWEEP_DEG = (0.25, 0.5, 1.0)
_CHAIN_AXIS_TOL_MM = 0.05  # wire centreline must hold the tangency radius
_CHAIN_HOOK_TOL_MM = 0.02  # ball joint residual
_CHAIN_MIN_WHEEL_SPAN_DEG = 5.0  # coupling-alive floor over the 0..1 deg sweep
_CHAIN_REST_TOL = 0.02  # mm / deg drift allowed after restoring the rest pose


async def _verify_paper_feed_one(adapter: Any, report: Report) -> None:
    """Kinematic proof that the crank drives the WHOLE paper feed (codex #189).

    The belt/chain (T12->T24) and rack-pinion ratios are otherwise exercised only by
    the hand-run ``build_kinematic_probe.py``, so a paper-feed regression could ship
    with the standard gates green. This wires that proof into ``verify:kinematics``:
    open paper-drive, drive the crank, and assert T24 / knob shaft / third gear /
    the 120T disc / the feed pinion all turn and the platen feeds (the probe's own
    assertions). The driven (dirty) model is discarded without saving. The belt
    mate ratio is build-time-checked but the rack coefficient and the
    end-to-end train are only proven by driving (codex #189)."""
    name = "paper-drive"
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"motion:{name}:open", f"not built: {sldasm}"))
        _telemetry.error(f"{sldasm.name} not built -- run doit")
        return
    if not _assert_fresh(name, report):
        return  # stale on-disk artefact: fail loud rather than verify old geometry

    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    check(f"open {name}", await adapter.open_model(str(sldasm)))
    log(f"--- motion: {name} crank->feed kinematic proof (codex #189) ---")
    # _drive_and_measure authors a temporary crank driver, rebuilds, and asserts the
    # whole train follows -- raising on any broken coupling (belt / lock / rack-pinion).
    from build_kinematic_probe import _drive_and_measure  # noqa: E402
    try:
        await report.agate(f"{name}:crank-feed", lambda: _drive_and_measure(adapter))
    finally:
        discard_open_documents(adapter)


async def _verify_live_chain_one(adapter: Any, report: Report) -> None:
    """Magnifier live-chain physics sweep (WIRE 1 articulation).

    Catches the regression class the 2026-07-04 side-view screenshot exposed
    (a rigidly locked wire's hub tip swept laterally ~10 mm off the hub as the
    chain moved): author ONLY the lever's ``lever_rock`` drive from the DOF
    manifest (the wire's swing/spin stay free -- that freedom IS the
    articulation), sweep the knife rock over a realistic 0..1 deg, and at every
    pose assert the wire still behaves like a wire:

    * wire-rides-hub: the wire's centreline stays at the stand-off tangency
      radius of the wheel axis (hub r + wire r + clearance);
    * hook-ball-holds: the wire's hook end stays on the fixture's anchor;
    * coupling-alive: the wheel angle actually spans with the lever (the yoke
      transmits);
    * restores-to-rest: driving back to the recorded rest angle returns the
      wheel and wire to the authored pose.

    The transient drive mate is discarded by closing the doc UNSAVED, so the
    shipped free model is untouched.
    """
    import build_lever_wire as _hw
    import build_magnifier_assembly as _mag
    from build_output_fixture import HOOK_ANCHOR_LOCAL

    name = "magnifier"
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"chain:{name}:open", f"not built: {sldasm}"))
        _telemetry.error(f"{sldasm.name} not built -- run doit")
        return
    if not _assert_fresh(name, report):
        return

    specs = [s for s in load_dof_manifest(name) if s.get("key") == "lever_rock"]
    if len(specs) != 1:
        report.failed.append(
            (f"chain:{name}:dof-manifest",
             f"expected 1 lever_rock drive spec, got {len(specs)}"))
        return

    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    check(f"open {name}", await adapter.open_model(str(sldasm)))
    model = adapter.currentModel
    log("--- live chain: magnifier lever sweep (knife rock, WIRE 1) ---")

    # Machine anchors for the invariants (the magnifier is authored
    # machine-handed, #151 -- constants feed straight through).
    axis_xy = (_mag.WHEEL_X, _mag.WHEEL_BAR_Y)  # wheel axis, along Z
    r_expect = _hw.HUB_DIA / 2.0 + _hw.WIRE_DIA / 2.0 + _hw.CLEARANCE

    def _xform(comp: str) -> tuple[list[list[float]], list[float]]:
        a = component_transform(adapter, comp)
        rows = [list(a[0:3]), list(a[3:6]), list(a[6:9])]
        pos = [v * 1000.0 for v in a[9:12]]
        return rows, pos

    def _wheel_deg() -> float:
        rows, _ = _xform("magnifying-wheel-1")
        return math.degrees(math.atan2(rows[0][1], rows[0][0]))

    def _wire_state() -> tuple[float, float, list[float]]:
        """(centreline-to-axis distance, hook ball residual, hub-end pos)."""
        rows, pos = _xform("lever-wire-1")
        u = rows[1]  # wire axis (+Y local = hub -> hook)
        # line-line distance to the wheel axis (direction Z at axis_xy)
        n = [u[1], -u[0], 0.0]  # u x z-hat
        n_len = math.hypot(n[0], n[1])
        w = [pos[0] - axis_xy[0], pos[1] - axis_xy[1]]
        d_axis = abs(w[0] * n[0] + w[1] * n[1]) / n_len
        hook = [p + _hw.WIRE_LEN * ui for p, ui in zip(pos, u)]
        frows, fpos = _xform("output-fixture-1")
        anchor = [
            fpos[k]
            + HOOK_ANCHOR_LOCAL[0] * frows[0][k]
            + HOOK_ANCHOR_LOCAL[1] * frows[1][k]
            + HOOK_ANCHOR_LOCAL[2] * frows[2][k]
            for k in range(3)
        ]
        d_hook = math.dist(hook, anchor)
        return d_axis, d_hook, pos

    replayed = await author_dof_drives(adapter, specs)
    mate = replayed[0]
    param = adapter._attempt(lambda: model.Parameter(f"D1@{mate}"), default=None)
    if param is None:
        report.failed.append((f"chain:{name}:driver", f"cannot read D1@{mate}"))
        return
    rest_rad = float(_read_member(param, "SystemValue"))

    def _set_lever(rad: float) -> None:
        param.SystemValue = rad
        _rebuild(adapter)

    _rebuild(adapter)
    wheel0, (axis0, hook0, wire_pos0) = _wheel_deg(), _wire_state()
    worst_axis = abs(axis0 - r_expect)
    worst_hook = hook0
    wheel_angles: list[float] = []
    for delta in _CHAIN_SWEEP_DEG:
        _set_lever(rest_rad + math.radians(delta))
        d_axis, d_hook, _ = _wire_state()
        w = _wheel_deg()
        wheel_angles.append(w)
        worst_axis = max(worst_axis, abs(d_axis - r_expect))
        worst_hook = max(worst_hook, d_hook)
        emit = (_telemetry.success
                if abs(d_axis - r_expect) <= _CHAIN_AXIS_TOL_MM and d_hook <= _CHAIN_HOOK_TOL_MM
                else _telemetry.error)
        emit(f"lever {delta:+5.2f} deg  wheel {w - wheel0:+8.3f} deg  "
             f"wire-axis d={d_axis:7.4f} (want {r_expect:g})  hook res={d_hook:.4f}")
    wheel_span = max(wheel_angles) - min(wheel_angles)

    # Restore the recorded rest pose, measure the drift, then discard UNSAVED.
    _set_lever(rest_rad)
    wheel_back = abs(_wheel_deg() - wheel0)
    _, _, wire_back_pos = _wire_state()
    wire_back = math.dist(wire_back_pos, wire_pos0)
    title = str(_read_member(model, "GetTitle"))
    adapter._attempt(lambda: adapter.swApp.CloseDoc(title), default=None)
    adapter.currentModel = None

    report.gate(
        f"chain:{name}:wire-rides-hub",
        lambda: _expect(
            worst_axis <= _CHAIN_AXIS_TOL_MM,
            f"wire centreline strays {worst_axis:.3f} mm off the {r_expect:g} mm "
            f"hub tangency radius over the sweep (> {_CHAIN_AXIS_TOL_MM})",
        ),
    )
    report.gate(
        f"chain:{name}:hook-ball-holds",
        lambda: _expect(
            worst_hook <= _CHAIN_HOOK_TOL_MM,
            f"hook ball residual {worst_hook:.3f} mm (> {_CHAIN_HOOK_TOL_MM})",
        ),
    )
    report.gate(
        f"chain:{name}:coupling-alive",
        lambda: _expect(
            wheel_span >= _CHAIN_MIN_WHEEL_SPAN_DEG,
            f"wheel spans only {wheel_span:.2f} deg over the 0..1 deg lever sweep "
            f"(< {_CHAIN_MIN_WHEEL_SPAN_DEG}) -- WIRE-1 coupling dead?",
        ),
    )
    report.gate(
        f"chain:{name}:restores-to-rest",
        lambda: _expect(
            wheel_back <= _CHAIN_REST_TOL and wire_back <= _CHAIN_REST_TOL,
            f"rest pose drift after sweep: wheel {wheel_back:.4f} deg, "
            f"wire {wire_back:.4f} mm (> {_CHAIN_REST_TOL})",
        ),
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
        # The lever reaches machine -X from the fulcrum (#151 machine frame).
        hole_x_0 = channel.FULCRUM[0] - channel.LEVER_SPRING_X * math.cos(phi0)
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
        import build_cone_pivot_screw as pscrew
        import build_cone_swing_platform as platform
        import build_drive_train_assembly as train
        import build_harmonic_base as base
        import build_swing_stop_screw as sscrew

        half_len, half_wid = base.TOP_LENGTH / 2.0, base.TOP_WIDTH / 2.0
        pv = train.cone_station(train.PIVOT_STATION)
        # (label, centre x, centre z, plan half-x, plan half-z); circular feet
        # use the radius both ways. (The old crank-pedestal is GONE: the merged
        # cone-pivot-post rides the PLATE, so it is plate-contained at
        # drive-train import, not base-swept here.)
        mounts = (
            ("arbor-pedestal south", train.X_DRUM, -train.ARBOR_PEDESTAL_Z,
             arbor_post.FOOT_WIDTH / 2.0, arbor_post.FOOT_DEPTH / 2.0),
            ("arbor-pedestal north", train.X_DRUM, train.ARBOR_PEDESTAL_NORTH_Z,
             arbor_post.FOOT_WIDTH / 2.0, arbor_post.FOOT_DEPTH / 2.0),
            # base-bolted statics; head/washer is each one's widest plan extent
            ("cone-lock-knob", train.KNOB_X, train.KNOB_Z,
             train.KNOB_WASHER_DIA / 2.0, train.KNOB_WASHER_DIA / 2.0),
            ("cone-pivot-screw", pv[0], pv[2],
             pscrew.HEAD_DIA / 2.0, pscrew.HEAD_DIA / 2.0),
            ("swing-stop-screw", train.STOP_X, train.STOP_Z,
             sscrew.HEAD_DIA / 2.0, sscrew.HEAD_DIA / 2.0),
        )
        for label, cx, cz, hx, hz in mounts:
            _expect(
                abs(cx) + hx <= half_len + 1e-9 and abs(cz) + hz <= half_wid + 1e-9,
                f"{label} foot hangs off the base top plate: plan centre "
                f"({cx:.2f}, {cz:.2f}) half-extents ({hx:.2f}, {hz:.2f}) vs "
                f"plate (+-{half_len:.2f}, +-{half_wid:.2f})",
            )
        # The cone swing platform lies flat on the base rotated by the cone
        # incline about its pivot: sweep its (asymmetric) trapezoid corners.
        # The machine-handed platform's local +x tips machine WEST at the
        # engaged pose (train._plate_local_to_machine), so the WEST half-
        # widths sit at local +x and the EAST ones at local -x; the solid
        # west flare carries the notch (the old lock lobe is gone).
        # Corner fillets only pull the true extents INSIDE this sharp-corner
        # sweep, so it stays conservative. The lock notch is open-ended, so
        # the disengaged pose is the plate swung until its edge clears the
        # knob washer (train.DISENGAGE_DEG, derived from the notch geometry)
        # -- sweep every corner at BOTH poses. (The pivot post and tip block
        # ride the PLATE, not the base -- their plate containment is
        # asserted at drive-train import.)
        corners_local = (
            # The NW corner carries the PR8 trim (WEST_HALF_N 9.5), the NE
            # keeps HALF_WIDTH_N 12.
            ("plate", platform.WEST_HALF_N, platform.NORTH_OVERHANG),
            ("plate", -platform.HALF_WIDTH_N, platform.NORTH_OVERHANG),
            ("plate", -platform.EAST_HALF_S,
             platform.NORTH_OVERHANG - platform.PLATE_LEN),
            ("plate", platform.WEST_HALF_S,
             platform.NORTH_OVERHANG - platform.PLATE_LEN),
        )
        poses = (
            ("engaged", math.radians(train.INCLINE_DEG)),
            ("disengaged",
             math.radians(train.INCLINE_DEG + train.DISENGAGE_DEG)),
        )
        for pose, ang in poses:
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            # Ry(+ang) plate->machine plan map (the engaged-pose case is
            # train._plate_local_to_machine): local +x -> (+cos, -sin).
            for part, lx, lz in corners_local:
                cx = pv[0] + lx * cos_a + lz * sin_a
                cz = pv[2] - lx * sin_a + lz * cos_a
                _expect(
                    abs(cx) <= half_len + 1e-9 and abs(cz) <= half_wid + 1e-9,
                    f"cone-swing-platform {part} corner ({cx:.2f}, {cz:.2f}) "
                    f"hangs off the base top plate (+-{half_len:.2f}, "
                    f"+-{half_wid:.2f}) at the {pose} pose",
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
            await _verify_static_one(
                adapter, name, report, auto_repair=_ARGS.auto_repair
            )
    if suite == "kinematics":
        await _verify_motion_one(adapter, report)
        await _verify_live_chain_one(adapter, report)
        await _verify_paper_feed_one(adapter, report)
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
                    choices=["soundness", "kinematics", "math", "config"])
    ap.add_argument(
        "--auto-repair",
        action="store_true",
        help=(
            "opt in to AutoMateRepair for What's Wrong [48] cache/PID mate "
            "dangles; soundness only, saved locally only after every gate passes"
        ),
    )
    args = ap.parse_args()
    if args.auto_repair and args.suite != "soundness":
        ap.error("--auto-repair is valid only with --suite soundness")
    if not args.names:
        # math/config need no model; kinematics targets MOTION_OWNER (pen);
        # soundness defaults to all built. (There is no aggregate "all" suite --
        # `doit build` is the one fully-safe entry point. The channel-independence
        # gate that used to be `subsystems` now runs inside soundness on `channel`.)
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

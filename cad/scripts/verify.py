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
  all                 static + truth.

Unlike the build gates (fail-fast), ``static`` runs every gate and reports the
full set of failures at the end, so one run tells you everything that is wrong.

Run (SolidWorks already open for any suite touching geometry)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\verify.py [name ...] [--suite static|truth|all]

``name`` defaults to every built assembly in ``cad/out/sldasm`` (drive-train,
harmonic-analyzer). ``truth`` needs no SolidWorks and no assembly.

NOT YET WIRED (tracked, not silently skipped):
  * Stepped-crank interference across the operating config and the motion-study
    pen-vs-truth_model comparison both require turning the crank, which only the
    Basic Motion solver does correctly here (the lock mates that key the cone
    cluster are outside the gear-mate graph, so a kinematic rotate desyncs the
    train -- see docs/motion-policy.md). They land with the motion suite once the
    real per-channel amplitudes replace the channels.yaml placeholders.
  * ``--suite isolation`` (subsystem pass/fail targets) is plan Part F.
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import _config
import truth_model
from _common import (
    OUT_SLDASM,
    assert_components_fully_defined,
    assert_model_healthy,
    check,
    check_no_interference,
    component_names,
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
# Crank-drive gear mate: either side carries one of these in its component name.
_CRANK_GEAR_TOKENS = ("crank-pinion", "crank-drive-gear")
# Expected top-level component-count band per assembly (instances, not parts):
# a tripwire for "a build dropped/duplicated a channel", not a tight count.
_COMPONENT_BAND = {
    "drive-train": (55, 70),
    "harmonic-analyzer": (90, 130),
}


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
    """The 20 cone:cylinder canonical ratios from config, sorted (a multiset)."""
    cyl = int(_config.machine("gear_train", "fundamental_cone_teeth"))
    return sorted(_canon_ratio(ch["cone_teeth"], cyl) for ch in _config.channels())


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


async def _verify_static_one(adapter: Any, name: str, report: Report) -> None:
    sldasm = OUT_SLDASM / f"{name}.SLDASM"
    if not sldasm.exists():
        report.failed.append((f"{name}:open", f"not built: {sldasm}"))
        print(f"  XX  {sldasm.name} not built -- run build_all.py", flush=True)
        return

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


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def build(adapter: Any) -> dict[str, str]:
    """Entry for ``run_build``: dispatch to the requested suite(s)."""
    suite, names = _ARGS.suite, _ARGS.names
    report = Report()

    if suite in ("static", "all"):
        for name in names:
            await _verify_static_one(adapter, name, report)
    if suite in ("truth", "all"):
        verify_truth(report)

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
    return sorted(p.stem for p in OUT_SLDASM.glob("*.SLDASM"))


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="assembly stem(s); default = all built")
    ap.add_argument("--suite", default="static", choices=["static", "truth", "all"])
    args = ap.parse_args()
    if not args.names:
        # truth needs no model; static/all default to whatever has been built.
        args.names = [] if args.suite == "truth" else _built_assemblies()
    return args


if __name__ == "__main__":
    _ARGS = _parse_args()
    if _ARGS.suite == "truth":
        # No SolidWorks needed -- run directly without connecting.
        _report = Report()
        verify_truth(_report)
        _print_summary(_report)
        sys.exit(1 if _report.failed else 0)
    sys.exit(run_build(build))

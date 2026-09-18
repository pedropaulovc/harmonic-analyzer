"""Live regression for ``_holes.wizard_holes`` on a disposable native coupon.

Verifies (fail loud on each):
- ANSI-inch size tokens resolve in the wizard table (``#8-32``, ``#4-40``,
  ``9/16-12``, ``#8``, ``#47``, ``#4``, ...);
- ``HoleDiameter`` reads back a sane table value at DEFINITION time (the
  ``expect_dia_mm`` tripwire depends on this);
- multi-point placement lands N instances (volume drop = N x hole area);
- blind depth + counterbore overrides apply;
- expected cut diameters (tap drill for taps, fit dia for clearances) match
  the published ANSI tables within 0.06 mm;
- through-next and through-all taps retain their specified thread class and
  thread termination, rather than zero-depth blind thread metadata.

Run (SolidWorks open)::

    uv run python cad/scripts/diagnostics/diag_hole_wizard.py

Nothing is saved; the document is discarded.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))
sys.path.insert(0, str(ROOT))

import dodo  # noqa: E402
from _common import _early_bound, check, run_build  # noqa: E402
from _holes import HoleSpec, wizard_holes  # noqa: E402
import _telemetry  # noqa: E402

# 60 x 60 x 10 mm block, top face at y=10 (Top-plane sketch, extruded up).
BLOCK = 60.0
BLOCK_T = 10.0

# (label, spec, points, expected cut dia mm, expected removed depth mm)
# Cut diameters PINNED from this seat's wizard tables (_holes.TAP_DRILL_MM /
# CLEARANCE_MM / NUMBER_DRILL_MM -- diag_hole_wizard_tables.py dump). Round-5
# measurements: taps + number drills exact; clearance "#8" normal = 4.978.
CASES = [
    (
        "tap 8-32 thru x2",
        HoleSpec("tapped", "#8-32"),
        [[-20.0, BLOCK_T, -20.0], [-20.0, BLOCK_T, 20.0]],
        3.454,
        BLOCK_T,
    ),
    (
        "tap 4-40 blind 6mm",
        HoleSpec("tapped_bottoming", "#4-40", end="blind", depth_mm=6.0),
        [[-10.0, BLOCK_T, -20.0]],
        2.261,
        6.0,
    ),
    (
        "tap 10-32 blind readback",
        HoleSpec(
            "tapped_bottoming",
            "#10-32",
            end="blind",
            depth_mm=6.0,
            overrides_mm={"ThreadDepth": 4.0},
        ),
        [[-10.0, BLOCK_T, 0.0]],
        4.0386,
        6.0,
    ),
    (
        "clearance #8 normal x2",
        HoleSpec("clearance", "#8"),
        [[0.0, BLOCK_T, -20.0], [0.0, BLOCK_T, 20.0]],
        4.978,
        BLOCK_T,
    ),
    # A NON-normal fit: HoleFit is a no-op on a plain hole (API: cbore/csink
    # only), so wizard_holes forces the pinned CLOSE dia -- regressed to 7.137
    # (normal) before the 2026-07-11 HoleDiameter fix.
    (
        "clearance 1/4 close",
        HoleSpec("clearance", "1/4", fit="close"),
        [[-10.0, BLOCK_T, 10.0]],
        6.756,
        BLOCK_T,
    ),
    (
        "number drill #47 x2",
        HoleSpec("drilled_number", "#47"),
        [[10.0, BLOCK_T, -20.0], [10.0, BLOCK_T, 20.0]],
        1.994,
        BLOCK_T,
    ),
    (
        "tap 1/4-20 through next",
        HoleSpec("tapped", "1/4-20", end="through_next"),
        [[10.0, BLOCK_T, 0.0]],
        5.1054,
        BLOCK_T,
    ),
    (
        "cbore fillister #4 + overrides",
        HoleSpec(
            "counterbore_fillister",
            "#4",
            overrides_mm={
                "HoleDiameter": 3.0,
                "CounterBoreDiameter": 6.5,
                "CounterBoreDepth": 2.4,
            },
        ),
        [[20.0, BLOCK_T, -20.0]],
        3.0,
        BLOCK_T,
    ),
    (
        "tap 9/16-12 thru",
        HoleSpec("tapped", "9/16-12", thread_class="1B"),
        [[20.0, BLOCK_T, 15.0]],
        12.303,
        BLOCK_T,
    ),
]


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"mass props failed: {res.error}")
    return float(res.data.volume)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    check("create_sketch block", await adapter.create_sketch("Top"))
    check(
        "rect",
        await adapter.add_rectangle(-BLOCK / 2, -BLOCK / 2, BLOCK / 2, BLOCK / 2),
    )
    check("exit", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_T)),
    )

    vol = await _volume(adapter)
    _telemetry.info(f"block volume {vol:.1f} mm^3")

    failures: list[str] = []
    for label, spec, pts, want_dia, want_depth in CASES:
        try:
            res = wizard_holes(
                adapter, spec, pts, (0.0, 1.0, 0.0), label, expect_dia_mm=want_dia
            )
            if spec.kind in ("tapped", "tapped_bottoming") and spec.end != "blind":
                part = _early_bound(adapter.currentModel, "IPartDoc")
                feature = _early_bound(part.FeatureByName(res.name), "IFeature")
                definition = _early_bound(feature.GetDefinition(), "IWizardHoleFeatureData2")
                expected_end = {"through_all": 1, "through_next": 2}[spec.end]
                actual = (
                    definition.ThreadClass,
                    int(definition.ThreadEndCondition),
                    int(definition.EndCondition),
                )
                expected = (spec.thread_class, expected_end, expected_end)
                if actual != expected:
                    failures.append(f"{label}: native thread class/thread end/hole end {actual!r} != {expected!r}")
            after = await _volume(adapter)
            removed = vol - after
            # The native diameter readback and an independent removed-volume
            # check must both agree with the pinned standard-hole dimensions.
            expect = len(pts) * math.pi * (want_dia / 2.0) ** 2 * want_depth
            ov = spec.overrides_mm
            if "CounterBoreDiameter" in ov:
                expect += (
                    len(pts)
                    * math.pi
                    * ((ov["CounterBoreDiameter"] / 2.0) ** 2 - (want_dia / 2.0) ** 2)
                    * ov["CounterBoreDepth"]
                )
            derived = (
                math.sqrt(max(removed, 0.0) / (len(pts) * want_depth) / math.pi) * 2.0
            )
            _telemetry.info(
                f"{label}: removed {removed:.1f} (expect {expect:.1f}; "
                f"derived cyl dia {derived:.3f} vs pinned {want_dia:.3f}) "
                f"readback dia {res.hole_dia_mm:.3f} cbore "
                f"{res.cbore_dia_mm:.2f}x{res.cbore_depth_mm:.2f}"
            )
            # blind wizard holes end in a 118-degree drill point (a cone the
            # cylinder formula misses, ~0.3*d tall) -- widen just that gate
            tol = 0.10 * expect if spec.end == "blind" else max(0.03 * expect, 0.5)
            if abs(removed - expect) > tol:
                failures.append(f"{label}: removed {removed:.1f} != {expect:.1f}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{label}: {exc}")
            _telemetry.error(f"{label}: {exc}")
        finally:
            # re-measure unconditionally so a failed case cannot pollute the
            # next case's removal delta
            vol = await _volume(adapter)

    if failures:
        raise RuntimeError("hole wizard probe failures:\n  " + "\n  ".join(failures))
    _telemetry.success(f"all {len(CASES)} hole-wizard cases verified")
    return {}


if __name__ == "__main__":
    with dodo._com_seat("diagnostic:hole-wizard-regression"):
        sys.exit(run_build(build))

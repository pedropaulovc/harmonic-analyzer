r"""SEAT SPIKE: can the Belt/Chain EngageBelt coupling ratio be forced to the
PITCH diameters (12:24 = 0.500), or is it stuck on the wrapped tip faces
(28:52 = 0.538)?

Codex #189 round-5 rejected the belt feature claiming ``EngageBelt`` "silently
ignores PulleyDiameters". The official API example
(``Create_Belt_Chain_Feature_Example``) shows diameters being CHANGED after
creation -- ``GetDefinition`` -> ``AccessSelections`` -> set ``PulleyDiameters``
-> ``ModifyDefinition`` -- where the getters are reliable, so the claim is
testable. This spike proves it either way on a SCRATCH two-sprocket assembly
(fast; nothing saved):

1. T12 + T24 removables placed free, each pinned to a revolute (spin free).
2. ``insert_belt_chain`` (EngageBelt, pitch diameters 24/48 mm requested).
3. Drive T12 +30 deg (temp angle mate), measure T24: ratio AND sense.
4. Read back ``PulleyDiameters`` post-create; if not the pitch values, set them
   via ``AccessSelections``/``ModifyDefinition`` and read back again.
5. Re-drive and re-measure the ratio + sense.

A chain couples both sprockets the SAME direction (a gear mate would reverse),
so the SENSE is asserted too, not just the magnitude.

The scratch assembly is DISCARDED unsaved.

Run (SolidWorks already open)::

    uv run python cad/scripts/diagnostics/probe_belt_diameter.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import check, log, run_build  # noqa: E402
from _telemetry import info, success, warn  # noqa: E402
from _assembly import (  # noqa: E402
    angle_driver,
    component_transform,
    distance_driver,
    named_ref,
    place_component,
)
from _transforms import IDENTITY, rot_z_rows  # noqa: E402
from preflight_release import _discard_open_documents  # noqa: E402

# Scratch layout: T12 at x -60, T24 at x +60 (free tangent span), both spinning
# about Z. OFF the global Right Plane on purpose: a component whose Right Plane
# is COPLANAR with the assembly's makes the temp angle driver degenerate (hard
# error 1 in place, both flips -- seen live at x = 0). Pitch diameters
# (module 2): 24 / 48 mm; tip 28 / 52.
T12_POS = -60.0
T24_POS = 60.0
PITCH_DIAMS_MM = [24.0, 48.0]
TIP_RATIO = 28.0 / 52.0  # 0.538 -- what the wrapped tip faces would couple at
PITCH_RATIO = 0.5  # 12:24 -- what a roller chain enforces
DRIVE_DEG = 30.0


def _rot(adapter: Any, name: str) -> list[float]:
    return component_transform(adapter, name)[:9]


def _rel_z_angle_deg(after: list[float], before: list[float]) -> float:
    """SIGNED rotation about +Z of ``after @ before^T`` (deg)."""
    bt = [before[0], before[3], before[6],
          before[1], before[4], before[7],
          before[2], before[5], before[8]]
    m = [sum(after[r * 3 + k] * bt[k * 3 + c] for k in range(3))
         for r in range(3) for c in range(3)]
    # Z-rotation by theta: m = [[c,-s,.],[s,c,.],...] -> atan2(2s, 2c) = theta.
    return math.degrees(math.atan2(m[3] - m[1], m[0] + m[4]))


async def _revolute(adapter: Any, name: str, x: float, label: str) -> None:
    """Pin Axis1 in XY + the axial z, leaving the Z spin free (paper-drive's
    ``_sprocket_revolute`` pattern, standalone)."""
    await distance_driver(adapter, named_ref(f"Axis1@{name}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), 0.0,
                          label=f"{label} axis height", verify=(name, [x, 0.0, 0.0]))
    await distance_driver(adapter, named_ref(f"Axis1@{name}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), x,
                          label=f"{label} axis lateral", verify=(name, [x, 0.0, 0.0]))
    await distance_driver(adapter, named_ref(f"Front Plane@{name}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), 0.0,
                          label=f"{label} axial", verify=(name, [x, 0.0, 0.0]))


async def _drive_and_measure(adapter: Any, t12: str, t24: str, tag: str) -> tuple[float, float]:
    """Temp angle mate drives T12 +DRIVE_DEG; returns (signed dT12, signed dT24)."""
    from solidworks_mcp.adapters.base import MateRefParameters

    base12, base24 = _rot(adapter, t12), _rot(adapter, t24)
    a = component_transform(adapter, t12)
    rest = math.degrees(math.acos(max(-1.0, min(1.0, a[0]))))
    res = await angle_driver(adapter, named_ref(f"Right Plane@{t12}", "PLANE"),
                             named_ref("Right Plane", "PLANE"), rest + DRIVE_DEG,
                             label=f"[{tag}] drive T12 +{DRIVE_DEG:.0f}", verify=None)
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    d12 = _rel_z_angle_deg(_rot(adapter, t12), base12)
    d24 = _rel_z_angle_deg(_rot(adapter, t24), base24)
    check(f"[{tag}] delete temp driver",
          await adapter.delete_mate(MateRefParameters(name=res.get("name", ""))))
    ratio = (d24 / d12) if d12 else 0.0
    info(f"[{tag}] T12 {d12:+.2f} deg -> T24 {d24:+.2f} deg  ratio {ratio:+.4f}"
         f"  (pitch {PITCH_RATIO:+.3f}, tip {TIP_RATIO:.3f})")
    return d12, d24


def _read_and_fix_diameters(adapter: Any, feat_name: str) -> dict:
    """Post-create: read PulleyDiameters; force the pitch values via
    AccessSelections + ModifyDefinition; read back. Returns the three states."""
    from solidworks_mcp.adapters import sw_type_info
    from solidworks_mcp.adapters.com_variant import double_array

    def _op() -> dict:
        model = adapter.currentModel
        feat = adapter._attempt(lambda: model.FeatureByName(feat_name), default=None)
        if feat is None:
            raise Exception(f"belt feature {feat_name!r} not found")
        # EARLY-bound: ModifyDefinition mismarshals late-bound (returns False).
        feat_t = sw_type_info.early_bound(feat, "IFeature")

        def access(d: Any) -> Any:
            """The getters return NOTHING on an un-accessed definition (read []
            live), so every read goes through AccessSelections first."""
            t = sw_type_info.early_bound(d, "IBeltChainFeatureData")
            ok = adapter._attempt(lambda: t.AccessSelections(model, None), default=False)
            if not ok:
                raise Exception("AccessSelections failed")
            return t

        def diams_of(t: Any) -> list[float]:
            vals = adapter._attempt(lambda: t.PulleyDiameters, default=None)
            vals = getattr(vals, "value", vals)
            return [round(v * 1000.0, 3) for v in (vals or [])]

        data = adapter._attempt(lambda: feat_t.GetDefinition(), default=None)
        if data is None:
            raise Exception("GetDefinition returned null")
        typed = access(data)
        created_mm = diams_of(typed)
        adapter._attempt(
            lambda: setattr(typed, "PulleyDiameters",
                            double_array([d / 1000.0 for d in PITCH_DIAMS_MM])),
            default=None)
        set_mm = diams_of(typed)  # what the definition now holds, pre-commit
        ok_modify = adapter._attempt(
            lambda: feat_t.ModifyDefinition(data, model, None), default=False)

        data2 = adapter._attempt(lambda: feat_t.GetDefinition(), default=None)
        final_mm = []
        if data2 is not None:
            typed2 = access(data2)
            final_mm = diams_of(typed2)
            adapter._attempt(lambda: typed2.ReleaseSelectionAccess(), default=None)
        return {"created_mm": created_mm, "set_mm": set_mm,
                "modify": bool(ok_modify), "final_mm": final_mm}

    result = adapter._handle_com_operation("belt_diam_fix", _op)
    if not result or not result.data:
        raise RuntimeError(f"diameter fix failed: {getattr(result, 'error', '?')}")
    return result.data


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import BeltChainParameters

    check("create scratch assembly", await adapter.create_assembly())
    try:
        # Seed T12 at Rz(15): a plane-plane ANGLE mate has NO first-order
        # authority at the 0/180 apex (park-driver-singularities class 1), so a
        # temp driver authored FROM an exactly-parallel rest pose fails in place
        # with hard error 1, both flips -- seen live twice. 15 deg puts the rest
        # dihedral safely off the apex (a spur sprocket's spin pose is cosmetic).
        t12 = await place_component(adapter, "transgear-removable", [T12_POS, 0.0, 0.0],
                                    [0.0, 0.0, 15.0], rot_z_rows(15.0),
                                    ground=False, configuration="T12",
                                    label="probe T12")
        t24 = await place_component(adapter, "transgear-removable", [T24_POS, 0.0, 0.0],
                                    [0.0, 0.0, 0.0], IDENTITY,
                                    ground=False, configuration="T24",
                                    label="probe T24")
        await _revolute(adapter, t12, T12_POS, "T12")
        await _revolute(adapter, t24, T24_POS, "T24")

        belt = check("belt feature (EngageBelt, pitch diams requested)",
                     await adapter.insert_belt_chain(BeltChainParameters(
                         pulley_components=[t12, t24],
                         pulley_diameters=PITCH_DIAMS_MM,
                         location_plane="Front Plane",
                         engage_belt=True, create_belt_part=False)))
        feat_name = belt.name
        info(f"belt feature created: {feat_name!r}")
        mates = await adapter.list_mates()
        for m in (mates.data or []):
            info(f"  mate: {m}")

        d12_a, d24_a = await _drive_and_measure(adapter, t12, t24, "as-created")

        states = _read_and_fix_diameters(adapter, feat_name)
        info(f"PulleyDiameters mm: created={states['created_mm']}"
             f" set={states['set_mm']} final={states['final_mm']}"
             f" (access={states['access']} modify={states['modify']})")

        d12_b, d24_b = await _drive_and_measure(adapter, t12, t24, "post-modify")

        ratio_a = d24_a / d12_a if d12_a else 0.0
        ratio_b = d24_b / d12_b if d12_b else 0.0
        same_sense = d12_b * d24_b > 0.0
        verdicts = []
        verdicts.append(
            f"as-created ratio {ratio_a:+.4f} ({'PITCH' if abs(abs(ratio_a) - PITCH_RATIO) < 0.01 else 'TIP' if abs(abs(ratio_a) - TIP_RATIO) < 0.01 else 'OTHER'})")
        verdicts.append(
            f"post-modify ratio {ratio_b:+.4f} ({'PITCH' if abs(abs(ratio_b) - PITCH_RATIO) < 0.01 else 'TIP' if abs(abs(ratio_b) - TIP_RATIO) < 0.01 else 'OTHER'})")
        verdicts.append(f"sense {'SAME (chain-correct)' if same_sense else 'OPPOSITE'}")
        summary = "; ".join(verdicts)
        if abs(abs(ratio_b) - PITCH_RATIO) < 0.01 and same_sense:
            success(f"BELT DIAMETER OVERRIDE WORKS -- {summary}")
        else:
            warn(f"belt diameter override NOT proven -- {summary}")
        log(summary)
        return {"summary": summary}
    finally:
        _discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))

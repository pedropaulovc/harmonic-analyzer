r"""SEAT SPIKE: make the built Belt1 coupling ratio follow the PITCH diameters.

The fresh paper-drive build measured the crank->T24 coupling at 0.538 (tip
faces) even though the definition's ``PulleyDiameters`` READ BACK 24/48 -- the
pre-create property put STORES values on the definition object without SW ever
using them (so the adapter's "already right" short-circuit skipped
ModifyDefinition, and the belt mates kept the face-derived ratio).

This spike experiments on the built model in ONE session, never saving:

  A. FORCED ModifyDefinition with the pitch diameters -> rebuild -> drive the
     crank +30 and measure the true T24 ratio.
  B. If still ~0.538: toggle EngageBelt False (commit), then set diameters +
     EngageBelt True (commit) -> the belt mates re-author from the corrected
     definition -> drive + measure again.

Run (SolidWorks already open, paper-drive.SLDASM built)::

    uv run python cad/scripts/diagnostics/probe_belt_ratio_fix.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import OUT_SLDASM, check, log, run_build  # noqa: E402
from _telemetry import info, success, warn  # noqa: E402
from _assembly import angle_driver, component_transform, named_ref  # noqa: E402
from build_kinematic_probe import _removables_by_role, _rel_z_angle_deg  # noqa: E402
from preflight_release import _discard_open_documents  # noqa: E402

PITCH_DIAMS_M = [0.024, 0.048]  # T12 / T24 pitch diameters
DRIVE_DEG = 30.0


async def _measure_ratio(adapter: Any, t12: str, t24: str, tag: str) -> float:
    from solidworks_mcp.adapters.base import MateRefParameters

    base12 = component_transform(adapter, t12)[:9]
    base24 = component_transform(adapter, t24)[:9]
    a = component_transform(adapter, t12)
    rest = math.degrees(math.acos(max(-1.0, min(1.0, a[0]))))
    res = await angle_driver(adapter, named_ref(f"Right Plane@{t12}", "PLANE"),
                             named_ref("Right Plane", "PLANE"), rest + DRIVE_DEG,
                             label=f"[{tag}] drive crank +{DRIVE_DEG:.0f}", verify=None)
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    d12 = _rel_z_angle_deg(component_transform(adapter, t12)[:9], base12)
    d24 = _rel_z_angle_deg(component_transform(adapter, t24)[:9], base24)
    check(f"[{tag}] delete temp driver",
          await adapter.delete_mate(MateRefParameters(name=res.get("name", ""))))
    # Drive back to the rest pose so the next experiment starts clean.
    res2 = await angle_driver(adapter, named_ref(f"Right Plane@{t12}", "PLANE"),
                              named_ref("Right Plane", "PLANE"), rest,
                              label=f"[{tag}] restore rest", verify=None)
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
    check(f"[{tag}] delete restore driver",
          await adapter.delete_mate(MateRefParameters(name=res2.get("name", ""))))
    ratio = (d24 / d12) if d12 else 0.0
    info(f"[{tag}] T12 {d12:+.2f} -> T24 {d24:+.2f}  ratio {ratio:+.4f}")
    return ratio


def _belt_commit(adapter: Any, *, diameters: list[float] | None,
                 engage: bool | None, tag: str,
                 member_params: bool = False) -> None:
    """AccessSelections -> optional sets -> ModifyDefinition (ALWAYS commits).

    ``member_params=True`` routes the diameters through the DOCUMENTED
    per-pulley setter ``ModifyMemberParameters(PulleyCompObject, Diameter,
    Flip)`` instead of the ``PulleyDiameters`` array property (which commits
    but does NOT re-derive the EngageBelt coupling ratio -- measured live:
    0.5385 after both a forced ModifyDefinition and an EngageBelt re-author).
    Each member face is identified by its cylinder radius (T12 tip 0.014 ->
    pitch 0.024; T24 tip 0.026 -> pitch 0.048)."""
    from solidworks_mcp.adapters import sw_type_info
    from solidworks_mcp.adapters.com_variant import double_array

    def _op() -> dict:
        model = adapter.currentModel
        feat = adapter._attempt(lambda: model.FeatureByName("Belt1"), default=None)
        if feat is None:
            raise Exception("Belt1 not found")
        feat_t = sw_type_info.early_bound(feat, "IFeature")
        data = adapter._attempt(lambda: feat_t.GetDefinition(), default=None)
        if data is None:
            raise Exception("GetDefinition null")
        typed = sw_type_info.early_bound(data, "IBeltChainFeatureData")
        if not adapter._attempt(lambda: typed.AccessSelections(model, None), default=False):
            raise Exception("AccessSelections failed")
        member_log: list[str] = []
        if diameters is not None and member_params:
            comps = adapter._attempt(lambda: typed.PulleyComponents, default=None)
            comps = getattr(comps, "value", comps) or []
            if len(comps) != len(diameters):
                raise Exception(f"{len(comps)} pulley members != {len(diameters)}")
            for face in comps:
                surf = adapter._attempt(
                    lambda f=face: sw_type_info.flagged(f, "IFace2").GetSurface(),
                    default=None)
                p = adapter._attempt(
                    lambda s=surf: sw_type_info.flagged(s, "ISurface").CylinderParams,
                    default=None)
                r = p[6] if p else 0.0
                # tip radius -> which sprocket -> its pitch diameter
                dia = 0.024 if abs(r - 0.014) < 0.004 else 0.048
                idx = adapter._attempt(lambda f=face: typed.GetMemberIndex(f), default=-1)
                ok = adapter._attempt(
                    lambda f=face, d=dia: typed.ModifyMemberParameters(f, d, False),
                    default=False)
                member_log.append(f"member idx={idx} r={r:.4f} -> dia={dia} ok={ok}")
                if not ok:
                    raise Exception(f"ModifyMemberParameters failed (r={r:.4f})")
        elif diameters is not None:
            adapter._attempt(
                lambda: setattr(typed, "PulleyDiameters", double_array(diameters)),
                default=None)
        if engage is not None:
            adapter._attempt(lambda: setattr(typed, "EngageBelt", bool(engage)),
                             default=None)
        if not adapter._attempt(
            lambda: feat_t.ModifyDefinition(data, model, None), default=False
        ):
            raise Exception("ModifyDefinition returned False")
        # Read back through a fresh accessed definition.
        data2 = adapter._attempt(lambda: feat_t.GetDefinition(), default=None)
        typed2 = sw_type_info.early_bound(data2, "IBeltChainFeatureData")
        adapter._attempt(lambda: typed2.AccessSelections(model, None), default=False)
        vals = adapter._attempt(lambda: typed2.PulleyDiameters, default=None)
        vals = getattr(vals, "value", vals)
        eng = adapter._attempt(lambda: typed2.EngageBelt, default=None)
        adapter._attempt(lambda: typed2.ReleaseSelectionAccess(), default=None)
        return {"diams_mm": [round(v * 1000.0, 3) for v in (vals or [])],
                "engage": eng, "members": member_log}

    result = adapter._handle_com_operation(f"belt_commit_{tag}", _op)
    if not result or not result.data:
        raise RuntimeError(f"[{tag}] belt commit failed: {getattr(result, 'error', '?')}")
    for line in result.data.get("members", []):
        info(f"[{tag}] {line}")
    info(f"[{tag}] committed: diams={result.data['diams_mm']} engage={result.data['engage']}")


async def build(adapter: Any) -> dict[str, str]:
    asm = OUT_SLDASM / "paper-drive.SLDASM"
    check("open paper-drive", await adapter.open_model(str(asm)))
    try:
        roles = _removables_by_role(adapter)
        t12, t24 = roles["T12"], roles["T24"]
        log(f"sprockets: T12={t12} T24={t24}")

        r0 = await _measure_ratio(adapter, t12, t24, "baseline")

        # C: the DOCUMENTED per-pulley setter (ModifyMemberParameters). The
        # array-property routes were measured dead: a forced ModifyDefinition
        # with PulleyDiameters committed AND an EngageBelt re-author both left
        # the coupling at the tip 0.5385.
        _belt_commit(adapter, diameters=PITCH_DIAMS_M, engage=None,
                     tag="C-members", member_params=True)
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
        r1 = await _measure_ratio(adapter, t12, t24, "C-member-params")

        r2 = None
        if abs(r1 - 0.5) > 0.01:
            # C2: member params + EngageBelt re-author combined.
            _belt_commit(adapter, diameters=None, engage=False, tag="C2-disengage")
            _belt_commit(adapter, diameters=PITCH_DIAMS_M, engage=True,
                         tag="C2-reengage", member_params=True)
            adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
            r2 = await _measure_ratio(adapter, t12, t24, "C2-reengaged")

        verdict = (f"baseline {r0:+.4f}; member-params {r1:+.4f}"
                   + (f"; member+reengage {r2:+.4f}" if r2 is not None else ""))
        final = r2 if r2 is not None else r1
        if abs(abs(final) - 0.5) <= 0.01 and final > 0:
            success(f"RATIO FIXED -- {verdict}")
        else:
            warn(f"ratio NOT fixed -- {verdict}")
        return {"verdict": verdict}
    finally:
        _discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))

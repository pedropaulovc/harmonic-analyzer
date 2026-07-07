r"""SEAT SPIKE D: drive the Belt1 coupling ratio via the MATE's own dimensions.

The dump (probe_belt_mate_dims.py) found where the ratio actually lives: the
EngageBelt coupling mate ``BeltMate1`` (type ``MateBeltDim``) carries two plain
dimensions -- ``D1`` = 0.052 / ``D2`` = 0.028, the tip diameters of the two
picked faces, ratio 28:52 = 0.5385 -- baked at creation and NEVER re-derived
from the definition (PulleyDiameters / ModifyMemberParameters / EngageBelt
re-author all commit without touching them; measured live).

This spike writes the PITCH diameters straight onto those mate dimensions
(``IDimension.SystemValue``), rebuilds, and measures the true coupling ratio by
driving the crank. Read-only otherwise; never saves.

Run (SolidWorks already open, paper-drive.SLDASM built)::

    uv run python cad/scripts/diagnostics/probe_belt_mate_dim_write.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import OUT_SLDASM, check, log, run_build  # noqa: E402
from _telemetry import info, success, warn  # noqa: E402
from build_kinematic_probe import _removables_by_role  # noqa: E402
from probe_belt_ratio_fix import _measure_ratio  # noqa: E402
from preflight_release import _discard_open_documents  # noqa: E402

# The mate dims are the picked faces' TIP diameters; rewrite each to the pitch
# diameter of ITS sprocket, matched by the created value (T24 0.052 -> 0.048,
# T12 0.028 -> 0.024).
DIM_MAP = {0.052: 0.048, 0.028: 0.024}


def _write_mate_dims(adapter: Any) -> dict:
    from solidworks_mcp.adapters import sw_type_info

    def _op() -> dict:
        model = adapter.currentModel
        feat = adapter._attempt(lambda: model.FeatureByName("BeltMate1"), default=None)
        if feat is None:
            raise Exception("BeltMate1 not found")
        feat_t = sw_type_info.flagged(feat, "IFeature")
        out = {}
        for dname in ("D1", "D2"):
            param = adapter._attempt(lambda d=dname: feat_t.Parameter(d), default=None)
            if param is None:
                raise Exception(f"{dname}@BeltMate1 not found")
            p_t = sw_type_info.flagged(param, "IDimension")
            old = adapter._attempt(lambda: p_t.SystemValue, default=None)
            target = next(
                (v for k, v in DIM_MAP.items() if old is not None and abs(old - k) < 5e-4),
                None)
            if target is None:
                raise Exception(f"{dname} unexpected value {old}")
            adapter._attempt(lambda t=target: setattr(p_t, "SystemValue", t), default=None)
            new = adapter._attempt(lambda: p_t.SystemValue, default=None)
            out[dname] = (old, new)
            if new is None or abs(new - target) > 1e-9:
                raise Exception(f"{dname} write did not take: {old} -> {new} (wanted {target})")
        adapter._attempt(lambda: model.ForceRebuild3(False), default=None)
        return out

    result = adapter._handle_com_operation("belt_mate_dim_write", _op)
    if not result or not result.data:
        raise RuntimeError(f"mate dim write failed: {getattr(result, 'error', '?')}")
    return result.data


async def build(adapter: Any) -> dict[str, str]:
    asm = OUT_SLDASM / "paper-drive.SLDASM"
    check("open paper-drive", await adapter.open_model(str(asm)))
    try:
        roles = _removables_by_role(adapter)
        t12, t24 = roles["T12"], roles["T24"]
        log(f"sprockets: T12={t12} T24={t24}")

        dims = _write_mate_dims(adapter)
        info(f"mate dims written: {dims}")

        ratio = await _measure_ratio(adapter, t12, t24, "D-mate-dims")
        if abs(ratio - 0.5) <= 0.01:
            success(f"RATIO FIXED via mate dimensions -- {ratio:+.4f} (same-sense)"
                    if ratio > 0 else f"ratio magnitude OK but sense flipped: {ratio:+.4f}")
        else:
            warn(f"ratio still wrong after mate-dim write: {ratio:+.4f}")
        return {"ratio": f"{ratio:+.4f}"}
    finally:
        _discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))

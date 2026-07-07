r"""SEAT SPIKE: what actually drives the Belt1 coupling ratio?

Every definition-level route commits but leaves the EngageBelt coupling at the
tip-face 0.5385: PulleyDiameters (forced ModifyDefinition), EngageBelt
re-author, and the documented per-member ModifyMemberParameters (returns True!)
-- all measured live 2026-07-06. So the ratio must live somewhere else. This
spike DUMPS the candidates on the built model, read-only, never saving:

  * BeltMate1 (type MateBeltDim): its parameters D1..D6 and display dimensions.
  * Belt1's sub-feature chain (the generated belt-path sketch): names, types,
    and each sketch's display dimensions -- the path's pulley circles may carry
    the diameters as writable dims.

Run (SolidWorks already open, paper-drive.SLDASM built)::

    uv run python cad/scripts/diagnostics/probe_belt_mate_dims.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import OUT_SLDASM, check, run_build  # noqa: E402
from _telemetry import info, warn  # noqa: E402
from preflight_release import _discard_open_documents  # noqa: E402


def _dump(adapter: Any) -> None:
    from solidworks_mcp.adapters import sw_type_info

    model = adapter.currentModel

    def read_member(obj: Any, name: str) -> Any:
        return adapter._attempt(lambda: getattr(obj, name), default=None)

    def dump_feature_params(feat_name: str) -> None:
        feat = adapter._attempt(lambda: model.FeatureByName(feat_name), default=None)
        if feat is None:
            warn(f"{feat_name}: not found")
            return
        feat_t = sw_type_info.flagged(feat, "IFeature")
        type_name = adapter._attempt(lambda: feat_t.GetTypeName2(), default="?")
        info(f"{feat_name}: type={type_name}")
        for dname in ("D1", "D2", "D3", "D4", "D5", "D6"):
            param = adapter._attempt(lambda d=dname: feat_t.Parameter(d), default=None)
            if param is None:
                continue
            p_t = sw_type_info.flagged(param, "IDimension")
            val = adapter._attempt(lambda: p_t.SystemValue, default=None)
            full = read_member(param, "FullName")
            info(f"  param {dname}: FullName={full!r} SystemValue={val}")
        # Display-dimension walk on the feature (annotation chain).
        disp = adapter._attempt(lambda: feat_t.GetFirstDisplayDimension(), default=None)
        n = 0
        while disp is not None and n < 20:
            dim = adapter._attempt(
                lambda d=disp: sw_type_info.flagged(d, "IDisplayDimension").GetDimension2(0),
                default=None)
            if dim is not None:
                dim_t = sw_type_info.flagged(dim, "IDimension")
                info(f"  dispdim: name={read_member(dim, 'FullName')!r} "
                     f"value={adapter._attempt(lambda: dim_t.SystemValue, default=None)}")
            disp = adapter._attempt(
                lambda f=feat_t, d=disp: f.GetNextDisplayDimension(d), default=None)
            n += 1

    dump_feature_params("BeltMate1")

    # Belt1 sub-feature chain: find generated sketches, dump their dims.
    belt = adapter._attempt(lambda: model.FeatureByName("Belt1"), default=None)
    if belt is None:
        warn("Belt1 not found")
        return
    belt_t = sw_type_info.flagged(belt, "IFeature")
    sub = adapter._attempt(lambda: belt_t.GetFirstSubFeature(), default=None)
    while sub is not None:
        sub_t = sw_type_info.flagged(sub, "IFeature")
        s_name = read_member(sub, "Name")
        s_type = adapter._attempt(lambda: sub_t.GetTypeName2(), default="?")
        info(f"Belt1 sub-feature: {s_name!r} type={s_type}")
        dump_feature_params(str(s_name))
        sub = adapter._attempt(lambda: sub_t.GetNextSubFeature(), default=None)


async def build(adapter: Any) -> dict[str, str]:
    asm = OUT_SLDASM / "paper-drive.SLDASM"
    check("open paper-drive", await adapter.open_model(str(asm)))
    try:
        adapter._handle_com_operation("belt_mate_dump", lambda: _dump(adapter))
        return {}
    finally:
        _discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))

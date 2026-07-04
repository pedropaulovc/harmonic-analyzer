r"""Throwaway probe: why does cone-swing-platform-1 read FULLY DEFINED in the
saved drive-train even though its swing angle driver is deferred?

Opens drive-train.SLDASM read-only, ForceRebuild3s (stale-status pitfall),
prints every top-level component's GetConstrainedStatus, then dumps every mate
that references cone-swing-platform-1 (or any part whose status is fully
defined but should swing). Never saves.

    uv run python cad/scripts/diagnostics/probe_platform_pin.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import OUT_SLDASM, _flag, _read_member, log, run_build  # noqa: E402

_MATE_NAME = {
    0: "COINCIDENT", 1: "CONCENTRIC", 2: "PERPENDICULAR", 3: "PARALLEL",
    4: "TANGENT", 5: "DISTANCE", 6: "ANGLE", 9: "CAMFOLLOWER",
    10: "GEAR", 13: "RACKPINION", 16: "LOCK",
}

FOCUS = (
    "cone-swing-platform", "cone-pivot-post", "cone-tip-block",
    "cone-tip-bushing", "cone-tip-adjuster", "cone-tip-pinch-screw",
)


def _mate_value(adapter, mate, mtype):
    if mtype not in (5, 6):
        return None
    dd = adapter._attempt(lambda: mate.DisplayDimension2(0), default=None)
    if dd is None:
        return None
    _flag(dd, "IDisplayDimension")
    dim = adapter._attempt(lambda: dd.GetDimension2(0), default=None)
    if dim is None:
        dim = adapter._attempt(lambda: dd.GetDimension(), default=None)
    if dim is None:
        return None
    _flag(dim, "IDimension")
    return adapter._attempt(lambda: dim.Value, default=None)


async def build(adapter):
    path = str((OUT_SLDASM / "drive-train.SLDASM").resolve())
    res = await adapter.open_model(path)
    if not res.is_success:
        log(f"open failed: {res.error}")
        return {}
    model = adapter.currentModel
    _flag(model, "IModelDoc2")

    log("ForceRebuild3 (status is stale until re-solve) ...")
    adapter._attempt(lambda: model.ForceRebuild3(False), default=None)

    log("=== component constrained status ===")
    comps = adapter._attempt(
        lambda: model.GetComponents(True), default=None) or []
    for c in comps:
        _flag(c, "IComponent2")
        name = str(_read_member(c, "Name2"))
        fixed = bool(_read_member(c, "IsFixed"))
        status = int(adapter._attempt(lambda cc=c: cc.GetConstrainedStatus(),
                                      default=-99))
        tag = " FIXED" if fixed else ""
        log(f"  {name:32s} status={status}{tag}")

    log("=== mates touching the swing family ===")
    feat = _read_member(model, "FirstFeature")
    for _ in range(50000):
        if not feat:
            break
        _flag(feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "MateGroup":
            sub = _read_member(feat, "GetFirstSubFeature")
            for _ in range(50000):
                if not sub:
                    break
                _flag(sub, "IFeature")
                name = str(_read_member(sub, "Name"))
                mate = adapter._attempt(lambda s=sub: s.GetSpecificFeature2(),
                                        default=None)
                if mate is None:
                    sub = _read_member(sub, "GetNextSubFeature")
                    continue
                _flag(mate, "IMate2")
                mtype = int(adapter._attempt(lambda m=mate: m.Type, default=-1))
                n = int(adapter._attempt(lambda m=mate: m.GetMateEntityCount(),
                                         default=0))
                parts = []
                for i in range(n):
                    me = adapter._attempt(lambda m=mate, k=i: m.MateEntity(k),
                                          default=None)
                    if me is None:
                        continue
                    _flag(me, "IMateEntity2")
                    rc = adapter._attempt(lambda e=me: e.ReferenceComponent2,
                                          default=None)
                    if rc is None:
                        rc = adapter._attempt(lambda e=me: e.ReferenceComponent,
                                              default=None)
                    if rc is not None:
                        _flag(rc, "IComponent2")
                        parts.append(str(_read_member(rc, "Name2")))
                val = _mate_value(adapter, mate, mtype)
                vstr = f"  val={val:.5f}" if val is not None else ""
                sup = _read_member(sub, "IsSuppressed")
                sstr = "  SUPPRESSED" if sup else ""
                tname = _MATE_NAME.get(mtype, f"type{mtype}")
                log(f"  {name:26s} {tname:11s} parts={parts}{vstr}{sstr}")
                sub = _read_member(sub, "GetNextSubFeature")
        feat = _read_member(feat, "GetNextFeature")

    adapter._attempt(lambda: adapter.swApp.CloseDoc(
        _read_member(model, "GetTitle")), default=None)
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))

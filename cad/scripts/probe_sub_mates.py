r"""Throwaway probe: dump every mate in each saved subassembly so Phase F's
build_motion_study.py can suppress the right driver dims by an exact, stable
rule (mate type + referenced PARTS + driving value) instead of guessed names.

Opens channel/drive-train/output .SLDASM read-only, walks the MateGroup, and
prints per mate: name, type, the parts it references (ReferenceComponent of
each mate entity, planes/origins skipped), and -- for distance/angle mates --
the stored driving dimension value. Never saves.

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_sub_mates.py
"""

from __future__ import annotations

import sys

from _common import OUT_SLDASM, _flag, _read_member, log, run_build

# swMateType_e
_MATE_NAME = {
    0: "COINCIDENT", 1: "CONCENTRIC", 2: "PERPENDICULAR", 3: "PARALLEL",
    4: "TANGENT", 5: "DISTANCE", 6: "ANGLE", 9: "CAMFOLLOWER",
    10: "GEAR", 13: "RACKPINION", 16: "LOCK",
}

SUBS = ("channel", "drive-train", "output")


async def _open(adapter, name):
    path = str((OUT_SLDASM / f"{name}.SLDASM").resolve())
    res = await adapter.open_model(path)
    if not res.is_success:
        log(f"open_model {name} failed: {res.error}")
        return None
    return adapter.currentModel


def _mate_value(adapter, mate, mtype):
    """Driving dimension value of a distance(5)/angle(6) mate, else None."""
    if mtype not in (5, 6):
        return None
    # IMate2.DisplayDimension2(0) -> IDisplayDimension -> IDimension.Value
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
    val = adapter._attempt(lambda: dim.GetSystemValue3(2, "")[0]
                           if isinstance(dim.GetSystemValue3(2, ""), (list, tuple))
                           else dim.Value, default=None)
    if val is None:
        val = adapter._attempt(lambda: dim.Value, default=None)
    return val


def _dump(adapter, model, sub):
    _flag(model, "IModelDoc2")
    log(f"=== {sub} ===")
    feat = _read_member(model, "FirstFeature")
    count = 0
    for _ in range(50000):
        if not feat:
            break
        _flag(feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "MateGroup":
            sub_feat = _read_member(feat, "GetFirstSubFeature")
            for _ in range(50000):
                if not sub_feat:
                    break
                _flag(sub_feat, "IFeature")
                name = str(_read_member(sub_feat, "Name"))
                mate = adapter._attempt(lambda s=sub_feat: s.GetSpecificFeature2(),
                                        default=None)
                if mate is None:
                    sub_feat = _read_member(sub_feat, "GetNextSubFeature")
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
                vstr = f"  val={val * 1000.0:.2f}" if (
                    val is not None and mtype == 5) else (
                    f"  val={val:.3f}" if val is not None else "")
                tname = _MATE_NAME.get(mtype, f"type{mtype}")
                log(f"  {name:18s} {tname:11s} parts={parts}{vstr}")
                count += 1
                sub_feat = _read_member(sub_feat, "GetNextSubFeature")
        feat = _read_member(feat, "GetNextFeature")
    log(f"  ({count} mates in {sub})")


async def build(adapter):
    for sub in SUBS:
        model = await _open(adapter, sub)
        if model is None:
            log(f"FAILED to open {sub}")
            continue
        _dump(adapter, model, sub)
        adapter._attempt(lambda: adapter.swApp.CloseDoc(
            _read_member(model, "GetTitle")), default=None)
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))

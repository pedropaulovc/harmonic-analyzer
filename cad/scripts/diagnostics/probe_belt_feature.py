r"""SEAT SPIKE: validate the SW Belt/Chain assembly feature on paper-drive.

Two things in one seat run, so I do not burn multiple COM sessions:

1. **Topology dump** -- open the built ``paper-drive.SLDASM`` and log every
   top-level component (name + referenced configuration) and every mate. This
   is how the crank -> chain -> knob -> rack-pinion -> platen feed path is read
   (per [[verify-assumptions-live-sw]]: probe the live model, do not trust
   stale comments).

2. **Belt/Chain feasibility** -- attempt to create a Belt/Chain assembly feature
   coupling the T12 crank sprocket <-> T24 knob sprocket via
   ``IFeatureManager.CreateDefinition(swFmBeltAndChain)`` ->
   ``sw_type_info.early_bound(data, "IBeltChainFeatureData")`` (the null-fix
   recorded in memory ``chain-component-pattern``) -> set pulley members /
   diameters / location plane -> ``EngageBelt=True``, ``CreateBeltPart=False``
   -> ``CreateFeature``. Reports whether the feature and its belt mates appear.

The model is opened, probed, and **discarded without saving**
(``CloseAllDocuments(True)``) so the shipped ``.SLDASM`` is untouched.

Run (SolidWorks already open)::

    uv run python cad/scripts/diagnostics/probe_belt_feature.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # cad/scripts

from _common import OUT_SLDASM, run_build  # noqa: E402
from _telemetry import info, warn, error, success  # noqa: E402
from solidworks_mcp.adapters import sw_type_info  # noqa: E402
from solidworks_mcp.adapters.com_variant import (  # noqa: E402
    dispatch_array,
    double_array,
    null_callout,
)
from solidworks_mcp.adapters.solidworks.features import _flag_feature_methods  # noqa: E402

# swFeatureNameID_e.swFmBeltAndChain = 119. Verified via .NET reflection on
# SolidWorks.Interop.swconst.dll (swFmLocalChainPattern=112 cross-checked against
# memory). NOT 92 -- a wrong value makes CreateDefinition return null.
SW_FM_BELT_AND_CHAIN = 119


def _bool_array(values: list[bool]):
    try:
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, list(values))
    except Exception:
        return list(values)


async def build(adapter) -> dict[str, str]:
    asm = OUT_SLDASM / "paper-drive.SLDASM"
    if not asm.exists():
        error(f"not built: {asm}")
        return {}
    from _common import check  # noqa: E402

    check("open paper-drive", await adapter.open_model(str(asm)))

    # --- topology dump (before) ---------------------------------------------
    mates_before = await adapter.list_mates()
    n_mates_before = len(mates_before.data or []) if mates_before else 0
    info(f"mates before: {n_mates_before}")

    def _probe() -> dict:
        model = adapter.currentModel
        fm = model.FeatureManager
        _flag_feature_methods(fm, "IFeatureManager")

        comps = adapter._attempt(lambda: model.GetComponents(False), default=None) or []
        sprockets: dict[str, object] = {}
        rows = []
        for c in comps:
            name = adapter._attempt(lambda c=c: c.Name2, default="?")
            cfg = adapter._attempt(lambda c=c: c.ReferencedConfiguration, default="?")
            rows.append((str(name), str(cfg)))
            if name and "transgear-removable" in str(name) and str(cfg) in ("T12", "T24"):
                sprockets[str(cfg)] = c
        for name, cfg in rows:
            info(f"  comp {name!r:52}  cfg={cfg}")

        if "T12" not in sprockets or "T24" not in sprockets:
            warn(f"could not find both sprockets (found {sorted(sprockets)}); "
                 "belt spike skipped")
            return {"created": False, "reason": "sprockets-not-found",
                    "n_comps": len(rows)}

        # BeltLocationPlane: assembly Front Plane (normal to the Z sprocket axes).
        plane_feat = adapter._attempt(lambda: model.FeatureByName("Front Plane"), default=None)
        ref_plane = None
        if plane_feat is not None:
            ref_plane = adapter._attempt(
                lambda: sw_type_info.flagged(plane_feat, "IFeature").GetSpecificFeature2(),
                default=None,
            )
        info(f"Front Plane feature={plane_feat is not None} ref_plane={ref_plane is not None}")

        # PulleyComponents should be the pulley's cylindrical FACE (the C#/VB.NET
        # examples select pulley faces, not the component objects). Walk each
        # sprocket body's faces for a cylinder whose axis is ~Z (the rotation
        # axis); prefer the largest-radius such face.
        def cyl_face(comp):
            sw_type_info.flag_methods(comp, "IComponent2")
            body = adapter._attempt(lambda: comp.GetBody(), default=None)
            if body is None:
                return None, None
            sw_type_info.flag_methods(body, "IBody2")
            faces = adapter._attempt(lambda: body.GetFaces(), default=None) or []
            best = None
            for f in faces:
                surf = adapter._attempt(
                    lambda f=f: sw_type_info.flagged(f, "IFace2").GetSurface(), default=None)
                if surf is None:
                    continue
                sw_type_info.flag_methods(surf, "ISurface")
                if not adapter._attempt(lambda s=surf: s.IsCylinder(), default=False):
                    continue
                p = adapter._attempt(lambda s=surf: s.CylinderParams, default=None)
                if not p:
                    continue
                az, r = abs(p[5]), p[6]
                if az > 0.9 and (best is None or r > best[1]):
                    best = (f, r)
            return (best[0], best[1]) if best else (None, None)

        face_t12, r12 = cyl_face(sprockets["T12"])
        face_t24, r24 = cyl_face(sprockets["T24"])
        info(f"pulley faces: T12 r={r12} T24 r={r24}")
        if face_t12 is None or face_t24 is None:
            warn("could not find Z-axis cylindrical faces on both sprockets")
            return {"created": False, "reason": "no-cyl-face", "n_comps": len(rows)}

        # --- Belt/Chain feature: sweep create strategies (FACES as pulleys) -----
        # Each strategy gets a FRESH definition. Pulley members are the cylindrical
        # faces (per the docs' examples); also try the component objects as a
        # fallback comparison.
        pulleys = dispatch_array([face_t12, face_t24])
        diams = double_array([0.024, 0.048])  # T12/T24 pitch diameters, metres
        flips = _bool_array([False, False])
        fm_eb = sw_type_info.early_bound(fm, "IFeatureManager")

        def make_data():
            d = adapter._attempt(lambda: fm.CreateDefinition(SW_FM_BELT_AND_CHAIN), default=None)
            if d is None:
                return None, None
            t = sw_type_info.early_bound(d, "IBeltChainFeatureData")
            for attr, val in (
                ("PulleyComponents", pulleys), ("PulleyDiameters", diams),
                ("FlipSides", flips), ("BeltLocationPlane", ref_plane),
                ("UseBeltThickness", False), ("CreateBeltPart", False),
                ("EngageBelt", True),
            ):
                adapter._attempt(lambda t=t, a=attr, v=val: setattr(t, a, v), default=None)
            return d, t

        def preselect():
            ext = model.Extension  # the selection extension used by SelectByID2 below
            adapter._attempt(lambda: model.ClearSelection2(True), default=None)
            for i, cfg in enumerate(("T12", "T24")):
                nm = adapter._attempt(lambda c=sprockets[cfg]: c.Name2, default=None)
                adapter._attempt(
                    lambda nm=nm, i=i: ext.SelectByID2(nm, "COMPONENT", 0.0, 0.0, 0.0,
                                                       i > 0, 1, null_callout(), 0),
                    default=False,
                )

        strategies = [
            ("raw/late-fm", False, lambda d, t: fm.CreateFeature(d)),
            ("raw/eb-fm", False, lambda d, t: fm_eb.CreateFeature(d)),
            ("typed/eb-fm", False, lambda d, t: fm_eb.CreateFeature(t)),
            ("preselect+raw/late-fm", True, lambda d, t: fm.CreateFeature(d)),
        ]
        feat = None
        used = None
        for tag, pre, creator in strategies:
            if pre:
                preselect()
            d, t = make_data()
            if d is None:
                info(f"[{tag}] CreateDefinition null")
                continue
            feat = adapter._attempt(lambda d=d, t=t, creator=creator: creator(d, t), default=None)
            errs = adapter._attempt(lambda: fm.GetCreateFeatureErrors(), default="?")
            info(f"[{tag}] CreateFeature null={feat is None} errors={errs}")
            if feat is not None:
                used = tag
                break
        fname = adapter._attempt(lambda: feat.Name, default=None) if feat is not None else None
        info(f"RESULT created={feat is not None} strategy={used} name={fname!r}")
        return {"created": feat is not None, "feature_name": fname,
                "strategy": used, "n_comps": len(rows)}

    result = adapter._handle_com_operation("belt_spike", _probe)
    payload = result.data if result and result.data else {"created": False,
                                                          "reason": str(getattr(result, "error", "?"))}

    mates_after = await adapter.list_mates()
    n_mates_after = len(mates_after.data or []) if mates_after else 0
    new_mates = n_mates_after - n_mates_before
    info(f"mates after: {n_mates_after}  (+{new_mates} new)")

    if payload.get("created"):
        success(f"BELT FEATURE CREATED -- {new_mates} new mates "
                f"(EngageBelt coupling); feasible via pywin32 early_bound")
    else:
        error(f"belt feature NOT created: {payload.get('reason', payload)}")

    # Discard -- never persist the spike into the shipped .SLDASM.
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    return {}


if __name__ == "__main__":
    sys.exit(run_build(build))

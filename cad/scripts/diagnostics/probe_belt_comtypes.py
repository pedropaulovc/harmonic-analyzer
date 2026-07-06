r"""Probe: SW Belt/Chain assembly feature via comtypes (pywin32 CreateFeature nulls).

pywin32 late binding returns null from ``IFeatureManager.CreateFeature`` for the
belt/chain feature-data object -- confirmed across enum 119, early_bound(data),
early_bound(fm), raw/typed arg, and pre-selection (probe_belt_feature.py). The
feature is documented to work only early-bound (C#/VBA). comtypes generates real
early-bound wrappers from the typelib -- the same trick that fixed GetPackAndGo
(probe_packandgo_comtypes.py) -- so ``CreateFeature`` should return the feature.

This proves the FULL path end-to-end: attach to the running SW, open paper-drive,
find the T12/T24 sprocket components + Front Plane, CreateDefinition(swFmBeltAndChain)
-> set pulley members/diameters/plane -> EngageBelt=True, CreateBeltPart=False ->
CreateFeature. Reports whether the feature is created, then DISCARDS (no save).

    uv run python cad/scripts/diagnostics/probe_belt_comtypes.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402

import comtypes  # noqa: E402
import comtypes.client  # noqa: E402

SW_TYPELIB = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"  # SldWorks type library
SW_TYPELIB_VER = (34, 0)
ASSEMBLY = r"C:\src\harmonic-analyzer\cad\out\sldasm\paper-drive.SLDASM"

SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_FM_BELT_AND_CHAIN = 119  # swFeatureNameID_e.swFmBeltAndChain (.NET reflection)


def main() -> int:
    mod = comtypes.client.GetModule((comtypes.GUID(SW_TYPELIB), *SW_TYPELIB_VER))
    sw = comtypes.client.GetActiveObject("SldWorks.Application", interface=mod.ISldWorks)
    _telemetry.info(f"attached to SW; revision {sw.RevisionNumber()}")

    sw.OpenDoc6(ASSEMBLY, SW_DOC_ASSEMBLY, SW_OPEN_SILENT, "", 0, 0)
    doc = sw.IActiveDoc2
    title = doc.GetTitle()
    _telemetry.info(f"opened {Path(ASSEMBLY).name}: {title}")
    try:
        return _probe(mod, sw, doc)
    finally:
        # Discard the probe's doc BY TITLE -- never CloseAllDocuments, which would
        # nuke any OTHER model open on this interactive seat. CloseDoc drops the
        # unsaved belt edit silently, so the shipped .SLDASM is untouched and a
        # headless run never hangs on a save modal, even if the probe raises
        # mid-way (codex #189 round-5, matching the pywin32 probe's finally).
        try:
            sw.CloseDoc(title)
        except Exception as exc:  # noqa: BLE001
            _telemetry.warn(f"CloseDoc({title!r}) failed: {exc}")


def _probe(mod: Any, sw: Any, doc: Any) -> int:
    # comtypes chokes on GetComponents' SAFEARRAY(VT_DISPATCH) return
    # (KeyError 9). Sidestep it: select each sprocket by name (names known from
    # the pywin32 dump -- transgear-removable-1=T24 knob, -2=T12 crank) and pull
    # the single IComponent2 from the SelectionManager (no array marshaling).
    ext = doc.Extension
    selmgr = doc.SelectionManager
    sprockets: dict[str, object] = {}
    for cfg, cname in (("T12", "transgear-removable-2@paper-drive"),
                       ("T24", "transgear-removable-1@paper-drive")):
        doc.ClearSelection2(True)
        ok = ext.SelectByID2(cname, "COMPONENT", 0.0, 0.0, 0.0, False, 0, None, 0)
        comp = selmgr.GetSelectedObjectsComponent3(1, -1) if ok else None
        _telemetry.info(f"select {cname!r} -> ok={ok} comp={comp is not None}")
        if comp is not None:
            sprockets[cfg] = comp
    doc.ClearSelection2(True)
    if "T12" not in sprockets or "T24" not in sprockets:
        _telemetry.error(f"could not select both sprockets (got {sorted(sprockets)})")
        return 2

    # FeatureByName lives on IAssemblyDoc (not the IModelDoc2 comtypes typed
    # `doc` as); QI to it, then GetSpecificFeature2 yields the IRefPlane the belt
    # setter expects -- the exact route the pywin32 probe used to set
    # BeltLocationPlane. (GetSelectedObject6 on a "PLANE" pick returns a plane
    # object that does NOT support IRefPlane and the setter rejects it.)
    asm = doc.QueryInterface(mod.IAssemblyDoc)
    raw_pf = asm.FeatureByName("Front Plane")
    plane_feat = raw_pf.QueryInterface(mod.IFeature) if raw_pf is not None else None
    ref_plane = plane_feat.GetSpecificFeature2() if plane_feat is not None else None
    _telemetry.info(f"Front Plane feat={plane_feat is not None} ref_plane={ref_plane is not None}")

    fm = doc.FeatureManager
    raw = fm.CreateDefinition(SW_FM_BELT_AND_CHAIN)
    _telemetry.info(f"CreateDefinition({SW_FM_BELT_AND_CHAIN}) -> "
                    f"{type(raw).__name__} (null={raw is None})")
    if raw is None:
        return 3
    data = raw.QueryInterface(mod.IBeltChainFeatureData)

    # comtypes marshals typed SAFEARRAY properties from plain Python lists.
    def setp(attr, val):
        try:
            setattr(data, attr, val)
            return True
        except Exception as exc:  # noqa: BLE001
            _telemetry.warn(f"set {attr} failed: {exc}")
            return False

    try:
        plane_arg = ref_plane.QueryInterface(mod.IRefPlane)
    except Exception as exc:  # noqa: BLE001
        _telemetry.warn(f"QI IRefPlane failed ({exc}); passing generic dispatch")
        plane_arg = ref_plane

    sets = {
        "PulleyComponents": setp("PulleyComponents", [sprockets["T12"], sprockets["T24"]]),
        "PulleyDiameters": setp("PulleyDiameters", [0.024, 0.048]),  # T12/T24 pitch dia, m
        "FlipSides": setp("FlipSides", [False, False]),
        "BeltLocationPlane": setp("BeltLocationPlane", plane_arg),
        "UseBeltThickness": setp("UseBeltThickness", False),
        "CreateBeltPart": setp("CreateBeltPart", False),
        "EngageBelt": setp("EngageBelt", True),
    }
    _telemetry.info(f"property sets: {sets}")

    feat = fm.CreateFeature(data)
    if feat is None:
        errs = None
        try:
            errs = fm.GetCreateFeatureErrors()
        except Exception as exc:  # noqa: BLE001
            errs = f"<{exc}>"
        _telemetry.error(f"CreateFeature -> None (comtypes ALSO nulls); errors={errs}")
        return 4

    name = feat.Name
    _telemetry.success(f"BELT FEATURE CREATED via comtypes: {name!r} -- "
                       f"belt/chain feasible early-bound")
    return 0  # the probe's doc is discarded by title in main()'s finally


if __name__ == "__main__":
    sys.exit(main())

r"""SEAT SPIKE E: belt with AXIS pulley members -- do typed diameters become
authoritative when there is no face to derive from?

Every route into the FACE-member belt's ratio is inert (measured live, all
read-backs green): PulleyDiameters commit, ModifyMemberParameters, EngageBelt
re-author, and writing the MateBeltDim's own D1/D2 dimensions -- the coupling
stays at the picked faces' 28:52 = 0.5385. Hypothesis: the coupling is enforced
by the generated belt-path sketch (born from the face diameters), and nothing
downstream re-derives it.

Two probes in one session on the built paper-drive (never saved):

  1. Read the Belt1 path sketch's arc/circle radii (are they 14/26 = tip, and
     do they move after a PulleyDiameters commit?).
  2. DELETE Belt1 and re-create it with each sprocket's ``Axis1`` DATUM AXIS as
     the pulley member + explicit PulleyDiameters 24/48. If SW accepts axis
     members it cannot derive a diameter -- the typed values may finally drive.
     Then measure the true coupling ratio by driving the crank.

Run (SolidWorks already open, paper-drive.SLDASM built)::

    uv run python cad/scripts/diagnostics/probe_belt_axis_members.py
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

SW_FM_BELT_AND_CHAIN = 119
PITCH_DIAMS_M = [0.024, 0.048]


def _read_path_radii(adapter: Any) -> list[float]:
    """Radii (m) of every arc/circle in Belt1's generated path sketch."""
    from solidworks_mcp.adapters import sw_type_info

    def _op() -> list[float]:
        model = adapter.currentModel
        belt = adapter._attempt(lambda: model.FeatureByName("Belt1"), default=None)
        if belt is None:
            return []
        belt_t = sw_type_info.flagged(belt, "IFeature")
        radii: list[float] = []
        sub = adapter._attempt(lambda: belt_t.GetFirstSubFeature(), default=None)
        while sub is not None:
            sub_t = sw_type_info.flagged(sub, "IFeature")
            if adapter._attempt(lambda: sub_t.GetTypeName2(), default="") == "ProfileFeature":
                sk = adapter._attempt(lambda: sub_t.GetSpecificFeature2(), default=None)
                segs = adapter._attempt(
                    lambda s=sk: sw_type_info.flagged(s, "ISketch").GetSketchSegments(),
                    default=None) or []
                for seg in segs:
                    st = adapter._attempt(
                        lambda x=seg: sw_type_info.flagged(x, "ISketchSegment").GetType(),
                        default=-1)
                    if st in (1, 3):  # swSketchARC=1, swSketchELLIPSE no; circle=arc
                        curve = adapter._attempt(
                            lambda x=seg: sw_type_info.flagged(
                                x, "ISketchArc").GetRadius(), default=None)
                        if curve:
                            radii.append(round(float(curve), 5))
            sub = adapter._attempt(lambda: sub_t.GetNextSubFeature(), default=None)
        return radii

    result = adapter._handle_com_operation("belt_path_radii", _op)
    return result.data if result and result.data else []


def _recreate_belt_axis_members(adapter: Any, t12: str, t24: str) -> str | None:
    """Delete Belt1; create a belt whose pulley members are the sprockets'
    Axis1 datum-axis features, with explicit PulleyDiameters."""
    from solidworks_mcp.adapters import sw_type_info
    from solidworks_mcp.adapters.com_variant import (
        dispatch_array,
        double_array,
        null_callout,
    )

    def _bool_array(values: list[bool]):
        import pythoncom
        from win32com.client import VARIANT

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BOOL, list(values))

    def _op() -> str | None:
        model = adapter.currentModel
        ext = model.Extension
        # 1. delete the existing belt feature (session-only; never saved)
        belt = adapter._attempt(lambda: model.FeatureByName("Belt1"), default=None)
        if belt is not None:
            adapter._attempt(lambda: model.ClearSelection2(True), default=None)
            adapter._attempt(lambda: belt.Select2(False, 0), default=False)
            ok = adapter._attempt(lambda: ext.DeleteSelection2(0), default=False)
            info(f"deleted Belt1: {ok}")
        # 2. resolve each sprocket's Axis1 datum-axis entity
        axes = []
        for comp in (t12, t24):
            adapter._attempt(lambda: model.ClearSelection2(True), default=None)
            sel = adapter._attempt(
                lambda c=comp: ext.SelectByID2(f"Axis1@{c}@paper-drive", "AXIS",
                                               0.0, 0.0, 0.0, False, 0,
                                               null_callout(), 0),
                default=False)
            if not sel:
                raise Exception(f"could not select Axis1@{comp}")
            selmgr = model.SelectionManager
            ent = adapter._attempt(
                lambda: sw_type_info.flagged(
                    selmgr, "ISelectionMgr").GetSelectedObject6(1, -1),
                default=None)
            if ent is None:
                raise Exception(f"could not fetch Axis1@{comp} entity")
            axes.append(ent)
        adapter._attempt(lambda: model.ClearSelection2(True), default=None)
        # 3. belt-location plane
        plane_feat = adapter._attempt(lambda: model.FeatureByName("Front Plane"), default=None)
        ref_plane = adapter._attempt(
            lambda: sw_type_info.flagged(plane_feat, "IFeature").GetSpecificFeature2(),
            default=None)
        # 4. definition
        fm = model.FeatureManager
        data = adapter._attempt(lambda: fm.CreateDefinition(SW_FM_BELT_AND_CHAIN), default=None)
        if data is None:
            raise Exception("CreateDefinition null")
        typed = sw_type_info.early_bound(data, "IBeltChainFeatureData")
        for attr, val in (
            ("PulleyComponents", dispatch_array(axes)),
            ("PulleyDiameters", double_array(PITCH_DIAMS_M)),
            ("FlipSides", _bool_array([False, False])),
            ("BeltLocationPlane", ref_plane),
            ("UseBeltThickness", False),
            ("CreateBeltPart", False),
            ("EngageBelt", True),
        ):
            adapter._attempt(lambda t=typed, a=attr, v=val: setattr(t, a, v), default=None)
        feat = adapter._attempt(lambda: fm.CreateFeature(data), default=None)
        name = adapter._attempt(lambda: feat.Name, default=None) if feat is not None else None
        info(f"axis-member belt created: {name!r}")
        return name

    result = adapter._handle_com_operation("belt_axis_members", _op)
    if not result:
        return None
    return result.data


async def build(adapter: Any) -> dict[str, str]:
    asm = OUT_SLDASM / "paper-drive.SLDASM"
    check("open paper-drive", await adapter.open_model(str(asm)))
    try:
        roles = _removables_by_role(adapter)
        t12, t24 = roles["T12"], roles["T24"]
        log(f"sprockets: T12={t12} T24={t24}")

        radii = _read_path_radii(adapter)
        info(f"Belt1 path sketch radii (m): {radii}")

        name = _recreate_belt_axis_members(adapter, t12, t24)
        if not name:
            warn("axis-member belt NOT created (CreateFeature null) -- SW rejects "
                 "datum-axis pulley members")
            return {"axis_member_belt": "rejected"}

        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
        radii2 = _read_path_radii(adapter)
        info(f"new belt path sketch radii (m): {radii2}")
        ratio = await _measure_ratio(adapter, t12, t24, "E-axis-members")
        if abs(ratio - 0.5) <= 0.01:
            success(f"AXIS-MEMBER BELT COUPLES AT PITCH -- ratio {ratio:+.4f}")
        else:
            warn(f"axis-member belt ratio {ratio:+.4f} (still not pitch)")
        return {"ratio": f"{ratio:+.4f}"}
    finally:
        _discard_open_documents(adapter)


if __name__ == "__main__":
    sys.exit(run_build(build))

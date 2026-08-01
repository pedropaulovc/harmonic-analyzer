r"""Diagnostic: does a native CAM-FOLLOWER mate hold the bar station under drag?

PR #458 follow-up to probe_drag_station: the user asked to empirically test the
SolidWorks cam-follower mate before deciding the channel J5 scheme. This probe

  1. opens channel.SLDASM and DELETES ch00's J5 roof-tangent distance mate
     (the plane<->Axis3 coupling), leaving the two limit-angle stops;
  2. authors a CAM-FOLLOWER mate (swMateCAMFOLLOWER=9) between the rocker's
     R800 top-edge cylindrical face (cam, Mark=1) and the bar's foot-notch
     roof planar face (follower, Mark=8);
  3. ramps the bar to the right amplitude endpoint with a transient angle
     drive, deletes the drive;
  4. drags the rocker about its pivot (all three DragModes, down then up) and
     logs the rocker motion achieved and the bar's station drift.

If the cam mate held the station the drift would read ~0; the free-DOF
analysis predicts it slides exactly like the tangent-distance scheme.

Run (SolidWorks already open):

  uv run python cad/scripts/diagnostics/probe_cam_station.py

NEVER saves.
"""

from __future__ import annotations

import asyncio
import math

from _common import OUT_SLDASM, _early_bound, _read_member, check, log  # noqa: F401  (shim first)
import _telemetry
from _assembly import (
    angle_driver,
    delete_assembly_feature,
    named_ref,
    world_point,
)
from _cwm import mates_with_owners
from build_channel_assembly import (
    AMPLITUDE_ANGLE_LIMITS,
    _CWM_PREFIXES,
)
from probe_drag_station import (
    BAR,
    PIVOT_LOCAL,
    ROCKER,
    _rebuild,
    _rot,
    _vectors,
)

ARM_TOP_RADIUS_M = 0.800  # the R800 top-edge cylinder, metres
BAR_FOOT_NOTCH_M = 0.0023812  # roof plane local y, metres


def _component_faces(adapter, asm, name: str):
    from solidworks_mcp.adapters import sw_type_info

    comp = sw_type_info.early_bound_or_flag(
        asm.GetComponentByName(name), "IComponent2", "GetBody"
    )
    body = adapter._attempt(lambda: _read_member(comp, "GetBody"), default=None)
    if body is None:
        raise RuntimeError(f"no body for {name}")
    body = sw_type_info.early_bound_or_flag(body, "IBody2", "GetFaces")
    for face in adapter._attempt(lambda: _read_member(body, "GetFaces"), default=None) or []:
        face = sw_type_info.early_bound_or_flag(face, "IFace2", "GetSurface")
        surf = adapter._attempt(lambda f=face: _read_member(f, "GetSurface"), default=None)
        if surf is None:
            continue
        yield face, sw_type_info.early_bound_or_flag(surf, "ISurface", "IsCylinder")


def _find_arc_face(adapter, asm):
    """The rocker's R800 top-edge cylindrical face."""
    for face, surf in _component_faces(adapter, asm, ROCKER):
        if not adapter._attempt(lambda s=surf: _read_member(s, "IsCylinder"), default=False):
            continue
        cyl = adapter._attempt(lambda s=surf: _read_member(s, "CylinderParams"), default=None)
        if cyl and abs(float(cyl[6]) - ARM_TOP_RADIUS_M) < 1e-4:
            return face
    raise RuntimeError("rocker R800 top-edge face not found")


def _find_profile_loop(adapter, asm):
    """Every face of the rocker's OUTER front profile: the R800/R816 edge
    cylinders plus all extrude side planes (normal perpendicular to Z). Bore
    cylinders are excluded by radius; the big front/back faces by normal."""
    loop = []
    for face, surf in _component_faces(adapter, asm, ROCKER):
        if adapter._attempt(lambda s=surf: _read_member(s, "IsCylinder"), default=False):
            cyl = adapter._attempt(
                lambda s=surf: _read_member(s, "CylinderParams"), default=None)
            if cyl and float(cyl[6]) > 0.5:  # R800/R816, not a bore
                loop.append(face)
            continue
        if adapter._attempt(lambda s=surf: _read_member(s, "IsPlane"), default=False):
            p = adapter._attempt(
                lambda s=surf: _read_member(s, "PlaneParams"), default=None)
            if p and abs(float(p[2])) < 0.01:  # side face, not front/back
                loop.append(face)
    return loop


def _find_roof_face(adapter, asm):
    """The bar's foot-notch roof planar face (offset ~2.381 mm along the bar)."""
    candidates = []
    for face, surf in _component_faces(adapter, asm, BAR):
        if not adapter._attempt(lambda s=surf: _read_member(s, "IsPlane"), default=False):
            continue
        p = adapter._attempt(lambda s=surf: _read_member(s, "PlaneParams"), default=None)
        if not p:
            continue
        n = [float(v) for v in p[0:3]]
        root = [float(v) for v in p[3:6]]
        candidates.append((face, n, root))
    # Try both spaces: component-local (normal ~ +-Y, offset ~ notch height)
    # and assembly space (normal ~ bar axis).
    for face, n, root in candidates:
        if abs(n[1]) > 0.99 and abs(abs(root[1]) - BAR_FOOT_NOTCH_M) < 2e-4:
            return face
    bar0 = world_point(adapter, BAR, [0.0, 0.0, 0.0])
    bar1 = world_point(adapter, BAR, [0.0, 1.0, 0.0])
    mag = math.hypot(bar1[0] - bar0[0], bar1[1] - bar0[1], bar1[2] - bar0[2])
    u = [(b - a) / mag for a, b in zip(bar0, bar1)]
    for face, n, root in candidates:
        along = sum(a * b for a, b in zip(n, u))
        if abs(along) < 0.99:
            continue
        proj = sum((r - a / 1000.0) * b for r, a, b in zip(root, bar0, u))
        if abs(abs(proj) - BAR_FOOT_NOTCH_M) < 2e-4:
            return face
    for face, n, root in candidates:
        log(f"  plane candidate n={n} root={root}")
    raise RuntimeError("bar foot-notch roof face not found")


async def main() -> None:
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    adapter = PyWin32Adapter({})
    _telemetry.info("Connecting ...")
    await adapter.connect()
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    path = str((OUT_SLDASM / "channel.SLDASM").resolve())
    check("open channel", await adapter.open_model(path))
    model = adapter.currentModel
    try:
        rest_rocker, rest_bar = _vectors(adapter)

        def station() -> float:
            rocker_u, bar_u = _vectors(adapter)
            return 90.0 + _rot(rocker_u, rest_rocker) - _rot(bar_u, rest_bar)

        # 1. delete ch00's J5 roof-tangent distance mate
        slice_instances = {ROCKER, BAR}
        j5 = [
            r for r in mates_with_owners(adapter, _CWM_PREFIXES)
            if r["type"] == "MateDistanceDim"
            and slice_instances <= r["instances"]
        ]
        if len(j5) != 1:
            raise RuntimeError(f"expected 1 rocker<->bar distance mate, got {j5}")
        delete_assembly_feature(adapter, j5[0]["name"])
        _rebuild(adapter)
        log(f"deleted {j5[0]['name']}; station now {station():.3f} deg")

        # 2. author the cam-follower mate: single-arc cam first, then the
        # full closed outer-profile loop if SolidWorks rejects the open arc.
        from solidworks_mcp.adapters.com_variant import dispatch_array

        asm = _early_bound(model, "IAssemblyDoc")
        arc_face = _find_arc_face(adapter, asm)
        roof_face = _find_roof_face(adapter, asm)
        loop_faces = _find_profile_loop(adapter, asm)
        log(f"profile loop faces: {len(loop_faces)}")

        def _create(mate_data, tag: str, alignment: int = 2):
            try:
                mate_data.MateAlignment = alignment
            except Exception as e:  # noqa: BLE001 -- diagnostic probe
                log(f"  {tag}: MateAlignment={alignment} threw {e!r}")
            try:
                feat = asm.CreateMate(mate_data)
            except Exception as e:  # noqa: BLE001
                log(f"  {tag}: CreateMate threw {e!r}")
                return None
            if feat is None:
                log(f"  {tag}: CreateMate returned None")
                return None
            feat = _early_bound(feat, "IFeature")
            log(f"  {tag}: created {_read_member(feat, 'Name')} "
                f"type={_read_member(feat, 'GetTypeName2')}")
            return feat

        def _try_cam(cam_faces, tag: str):
            """Raw-Invoke PROPERTYPUT: the generated wrapper types the value
            slot (9,1) = a bare VT_DISPATCH, which refuses the required entity
            array. Raw IDispatch::Invoke passes the array VARIANT unmangled;
            SW object[] SAFEARRAYs marshal as VT_ARRAY|VT_VARIANT."""
            import pythoncom
            from win32com.client import VARIANT

            model.ClearSelection2(True)
            mate_data = _early_bound(
                asm.CreateMateData(9), "ICamFollowerMateFeatureData")
            for ent_type, faces in ((0, cam_faces), (1, [roof_face])):
                raw = [getattr(f, "_oleobj_", f) for f in faces]
                stored = False
                attempts = [
                    ("single-dispatch", faces[0]),
                    ("VT_VARIANT", VARIANT(
                        pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, raw)),
                    ("VT_DISPATCH", dispatch_array(raw)),
                ]
                for vt_tag, value in attempts:
                    try:
                        if vt_tag == "single-dispatch":
                            mate_data.SetEntitiesToMate(ent_type, value)
                        else:
                            mate_data._oleobj_.Invoke(
                                1, 0, pythoncom.DISPATCH_PROPERTYPUT, 0,
                                ent_type, value,
                            )
                    except Exception as e:  # noqa: BLE001
                        log(f"  {tag}: PROPERTYPUT({ent_type},{vt_tag}) "
                            f"threw {e!r}")
                        continue
                    back = adapter._attempt(
                        lambda t=ent_type: mate_data.EntitiesToMate(t),
                        default=None)
                    n = adapter._attempt(
                        lambda b=back: len(list(b)) if b else 0, default=0)
                    log(f"  {tag}: PROPERTYPUT({ent_type},{vt_tag}) ok, "
                        f"readback count={n}")
                    if n:
                        stored = True
                        break
                if not stored:
                    log(f"  {tag}: entities never stored for slot {ent_type}")
            return _create(mate_data, tag)

        def _try_cam_preselect(cam_faces, tag: str):
            """The documented alternative: pre-select with Mark=1 (cam faces)
            and Mark=8 (follower), then CreateMate on an entity-less data."""
            sel_mgr = _early_bound(model.SelectionManager, "ISelectionMgr")
            model.ClearSelection2(True)
            for face, mark in [(f, 1) for f in cam_faces] + [(roof_face, 8)]:
                data = _read_member(sel_mgr, "CreateSelectData")
                data.Mark = mark
                if not _early_bound(face, "IEntity").Select4(True, data):
                    log(f"  {tag}: face select failed (mark {mark})")
                    return None
            mate_data = _early_bound(
                asm.CreateMateData(9), "ICamFollowerMateFeatureData")
            return _create(mate_data, tag)

        # POSITIVE CONTROL: the same CreateMateData/CreateMate recipe with a
        # plain TANGENT mate (type 4) on the same two faces. If this creates
        # while the cam variants fail, the recipe is sound and the rejection
        # is cam-specific.
        def _try_tangent(tag: str):
            model.ClearSelection2(True)
            mate_data = _early_bound(asm.CreateMateData(4), "ITangentMateFeatureData")
            try:
                mate_data.EntitiesToMate = dispatch_array([arc_face, roof_face])
            except Exception as e:  # noqa: BLE001
                log(f"  {tag}: EntitiesToMate= threw {e!r}")
            return _create(mate_data, tag)

        control = _try_tangent("control-tangent")
        if control is not None:
            delete_assembly_feature(adapter, str(_read_member(control, "Name")))
            _rebuild(adapter)

        feat = _try_cam([arc_face], "cam-single-arc")
        if feat is None:
            feat = _try_cam(loop_faces, "cam-full-loop")
        if feat is None:
            # Re-find: the earlier failed CreateMate cycles can disconnect the
            # cached face dispatches.
            arc_face = _find_arc_face(adapter, asm)
            roof_face = _find_roof_face(adapter, asm)
            loop_faces = _find_profile_loop(adapter, asm)
            feat = _try_cam_preselect([arc_face], "cam-presel-single")
        if feat is None:
            feat = _try_cam_preselect(loop_faces, "cam-presel-loop")
        if feat is None and control is None:
            raise RuntimeError(
                "NO positive control: even the tangent mate failed via "
                "CreateMateData -- the recipe (not cam geometry) is broken"
            )
        contact_kind = "cam-follower"
        if feat is None:
            # Cam-follower unauthorable -- fall back to measuring the SAME
            # tangency-family contact with the plain face-tangent mate (the
            # positive control). A cam mate IS a tangency to the profile, so
            # its drag behaviour is represented by this measurement.
            log("cam-follower unauthorable; measuring the face-TANGENT mate "
                "drag behaviour instead (same constraint family)")
            contact_kind = "tangent-face"
            feat = _try_tangent("fallback-tangent")
            if feat is None:
                raise RuntimeError("tangent fallback failed to re-create")
        _rebuild(adapter)
        log(f"contact mate in force: {contact_kind}; "
            f"station {station():.3f} deg")

        # 3. ramp the bar to the right endpoint, delete the drive
        endpoint = max(AMPLITUDE_ANGLE_LIMITS)
        res = await angle_driver(
            adapter,
            named_ref(f"Right Plane@{ROCKER}", "PLANE"),
            named_ref(f"Top Plane@{BAR}", "PLANE"),
            90.0,
            label="PROBE cam station drive",
        )
        param = adapter._attempt(lambda: model.Parameter(f"D1@{res['name']}"), default=None)
        assert param is not None
        for step in range(9):
            requested = 90.0 + (endpoint - 90.0) * step / 8.0
            param.SystemValue = math.radians(requested)
            _rebuild(adapter)
        log(f"ramped to endpoint: station {station():.3f} deg (target {endpoint:.3f})")
        delete_assembly_feature(adapter, res["name"])
        _rebuild(adapter)
        log(f"after drive delete: station {station():.3f} deg")

        # 4. drag passes (same shape as probe_drag_station)
        from solidworks_mcp.adapters.solidworks.assembly import _create_math_transform
        from probe_drag_station import _rot_z_about

        comp = asm.GetComponentByName(ROCKER)
        drag = _early_bound(asm.GetDragOperator(), "IDragOperator")

        def drag_pass(mode: int, total_deg: float, steps: int) -> None:
            pivot = world_point(adapter, ROCKER, PIVOT_LOCAL)
            xform = _create_math_transform(
                adapter, _rot_z_about(pivot, total_deg / steps)
            )
            before_rocker, _ = _vectors(adapter)
            before_station = station()
            ok = drag.AddComponent(comp, False)
            drag.CollisionDetectionEnabled = False
            drag.DynamicClearanceEnabled = False
            drag.TransformType = 1
            drag.DragMode = mode
            began = drag.BeginDrag()
            moved = [bool(drag.Drag(xform)) for _ in range(steps)]
            ended = drag.EndDrag()
            after_rocker, _ = _vectors(adapter)
            motion = _rot(after_rocker, before_rocker)
            drift = station() - before_station
            log(
                f"  mode={mode} req={total_deg:+.1f} deg: add={ok} begin={began} "
                f"steps_ok={sum(moved)}/{steps} end={ended} "
                f"rocker_moved={motion:+.3f} deg station_drift={drift:+.3f} deg "
                f"station={station():.3f}"
            )

        for mode in (0, 1, 2):
            log(f"DragMode {mode}:")
            drag_pass(mode, -3.0, 6)
            drag_pass(mode, +3.0, 6)
        log(f"final station {station():.3f} deg")
    finally:
        adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)


if __name__ == "__main__":
    asyncio.run(main())

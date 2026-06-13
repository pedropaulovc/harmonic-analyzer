r"""Live probe: sketch-point addressability on SW 2026 (Phase A0).

Gates the fix-relation retirement plan. Exercises raw COM on handles pulled
from ``adapter._sketch_entities`` — no adapter changes required yet:

1.  GetCenterPoint2 / GetStartPoint2 / GetEndPoint2: method-call vs bare
    attribute resolution after ``sw_type_info.flag_methods``.
2.  Sketch-origin selection: ``SelectByID2`` name candidates, then dispatch
    recovery via ``ISelectionMgr.GetSelectedObject6(1, -1)``.
3.  Point-coincident circle-centre -> origin (the new define_circle scheme
    for (0,0) circles), incl. whether creation-time inference already
    anchored it.
4.  Horizontal/vertical point-to-point DRIVING dims on a circle at
    (-20, -15) + ForceRebuild3: does the unsigned dim keep the centre on
    the negative side, and is the sketch fully defined?
5.  Diameter dimension DrivenState on non-fixed geometry (expect 2 =
    driving) without over-defining.
6.  HORIZPOINTS(25) vs HORIZONTAL(4) between two sketch points.
7.  MERGEPOINTS(42) and ATMIDDLE(12) smoke.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\probe_point_anchoring.py

Results (2026-06-12, SW 2026 / 3DEXPERIENCE, 11/11 PASS):

* Point accessors resolve as METHOD CALLS after ``flag_methods`` (the
  bare-attribute pattern is not needed).
* Origin: ``SelectByID2("Point1@Origin", "EXTSKETCHPOINT", ...)`` works,
  but ONLY with the typed ``com_variant.null_callout()`` — a bare ``None``
  callout makes SelectByID2 return False for every name.
* Explicit coincident centre->origin is safe even when creation-time
  inference already anchored the point (no over-definition).
* Unsigned H/V point-to-point driving dims keep a (-20,-15) centre on the
  negative side through ForceRebuild3; sketch fully defined. No
  construction-line fallback needed.
* Diameter dims on non-fixed circles land DRIVING (DrivenState=2).
* Plain ``horizontal`` (enum 4) works directly between two points —
  HORIZPOINTS(25) not required.
* MERGEPOINTS(42) works but destroys the absorbed point's COM handle
  ("disconnected from its clients") — point refs must be re-resolved after
  a merge, which the lazy suffix-resolution adapter design does naturally.
* ATMIDDLE(12) works (point onto line).
"""

from __future__ import annotations

import sys
from typing import Any

from _common import check, run_build

RESULTS: list[tuple[str, bool, str]] = []


def record(step: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((step, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {step}{': ' + detail if detail else ''}", flush=True)


def _flag(adapter: Any, obj: Any, iface: str) -> None:
    from solidworks_mcp.adapters import sw_type_info

    adapter._attempt(lambda: sw_type_info.flag_methods(obj, iface), default=0)


def _xyz(adapter: Any, point_obj: Any) -> tuple[float, float, float] | None:
    """Point coordinates in mm (COM is metres)."""
    xyz = adapter._sketch_geometry.point_xyz(point_obj)
    if xyz is None:
        return None
    return (xyz[0] * 1000.0, xyz[1] * 1000.0, xyz[2] * 1000.0)


def _get_point(adapter: Any, entity: Any, iface: str, member: str) -> tuple[Any, str]:
    """Resolve a point accessor, reporting whether call or property worked."""
    _flag(adapter, entity, iface)
    point = adapter._attempt(lambda: getattr(entity, member)(), default=None)
    if point is not None and _xyz(adapter, point) is not None:
        return point, "method-call"
    raw = adapter._attempt(lambda: getattr(entity, member), default=None)
    if raw is not None and not callable(raw) and _xyz(adapter, raw) is not None:
        return raw, "bare-property"
    return None, "unresolved"


def _origin_feature_names(adapter: Any) -> list[str]:
    """Names of origin-typed features in the tree (locale-proof candidates)."""
    from _common import _read_member

    names: list[str] = []
    feat = _read_member(adapter.currentModel, "FirstFeature")
    for _ in range(200):
        if not feat:
            break
        _flag(adapter, feat, "IFeature")
        if _read_member(feat, "GetTypeName2") == "OriginProfileFeature":
            names.append(str(_read_member(feat, "Name")))
        feat = _read_member(feat, "GetNextFeature")
    return names


def _resolve_origin(adapter: Any) -> tuple[Any, str]:
    """Try SelectByID2 name candidates; recover the dispatch from the selmgr.

    Callout must be the typed null from ``com_variant.null_callout`` — a bare
    ``None`` makes SelectByID2 fail outright on this build.
    """
    from solidworks_mcp.adapters.com_variant import null_callout

    model = adapter.currentModel
    _flag(adapter, model, "IModelDoc2")
    ext = model.Extension
    _flag(adapter, ext, "IModelDocExtension")
    sel_mgr = model.SelectionManager
    _flag(adapter, sel_mgr, "ISelectionMgr")

    candidates = [("Point1@Origin", "EXTSKETCHPOINT")]
    for feature_name in _origin_feature_names(adapter):
        candidates.append((f"Point1@{feature_name}", "EXTSKETCHPOINT"))
    candidates.append(("", "EXTSKETCHPOINT"))  # select by location (0,0,0)

    attempts: list[str] = []
    for name, type_name in candidates:
        model.ClearSelection2(True)
        ok = adapter._attempt(
            lambda n=name, t=type_name: bool(
                ext.SelectByID2(n, t, 0.0, 0.0, 0.0, False, 0, null_callout(), 0)
            ),
            default=False,
        )
        if not ok:
            attempts.append(f"{name or '<empty>'}:select=False")
            continue
        obj = adapter._attempt(lambda: sel_mgr.GetSelectedObject6(1, -1), default=None)
        model.ClearSelection2(True)
        if obj is None:
            attempts.append(f"{name or '<empty>'}:no-dispatch")
            continue
        xyz = _xyz(adapter, obj)
        if xyz is not None and max(abs(c) for c in xyz) < 1e-6:
            return obj, f"SelectByID2({name or '<empty>'!r}, {type_name!r})"
        attempts.append(f"{name or '<empty>'}:xyz={xyz}")
    return None, "; ".join(attempts)


def _add_relation_raw(adapter: Any, objs: list[Any], enum_value: int) -> Any:
    """AddRelation with the VT_ARRAY|VT_DISPATCH marshalling from the adapter."""
    import pythoncom
    from win32com.client import VARIANT

    model = adapter.currentModel
    _flag(adapter, model, "IModelDoc2")
    sketch = model.GetActiveSketch2()
    if sketch is None:
        raise RuntimeError("no active sketch")
    _flag(adapter, sketch, "ISketch")
    relmgr = sketch.RelationManager
    _flag(adapter, relmgr, "ISketchRelationManager")
    variant = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, objs)
    return adapter._attempt(lambda: relmgr.AddRelation(variant, enum_value), default=None)


def _select_point(adapter: Any, point_obj: Any, append: bool) -> bool:
    selected = adapter._attempt(
        lambda: bool(point_obj.Select4(append, None)), default=False
    )
    if selected:
        return True
    return bool(
        adapter._attempt(lambda: bool(point_obj.Select2(append, 0)), default=False)
    )


def _add_point_pair_dim(
    adapter: Any, p1: Any, p2: Any, kind: str, value_mm: float, text_xyz_m: tuple
) -> Any:
    """Select two points, AddHorizontal/VerticalDimension2, set driving value."""
    model = adapter.currentModel
    # Modify-dialog suppression, mirroring _add_sketch_dimension_impl.
    sw = adapter.swApp
    for toggle in (10, 372, 520):
        adapter._attempt(lambda t=toggle: sw.SetUserPreferenceToggle(t, False))
    model.ClearSelection2(True)
    if not _select_point(adapter, p1, append=False):
        raise RuntimeError("select p1 failed")
    if not _select_point(adapter, p2, append=True):
        raise RuntimeError("select p2 failed")
    method = {
        "horizontal": "AddHorizontalDimension2",
        "vertical": "AddVerticalDimension2",
    }[kind]
    display_dim = adapter._attempt(
        lambda: getattr(model, method)(*text_xyz_m), default=None
    )
    model.ClearSelection2(True)
    if display_dim is None:
        raise RuntimeError(f"{method} returned None")
    dim_obj = (
        adapter._attempt(lambda: display_dim.GetDimension2(0), default=None)
        or adapter._attempt(lambda: display_dim.GetDimension(), default=None)
        or display_dim
    )
    value_m = value_mm / 1000.0
    if adapter._attempt(lambda: dim_obj.SetSystemValue3(value_m, 1, None), default=None) is None:
        if adapter._attempt(lambda: dim_obj.SetSystemValue2(value_m, 1), default=None) is None:
            dim_obj.SystemValue = value_m
    return display_dim


def _driven_state(adapter: Any, display_dim: Any) -> Any:
    dim_obj = (
        adapter._attempt(lambda: display_dim.GetDimension2(0), default=None)
        or adapter._attempt(lambda: display_dim.GetDimension(), default=None)
        or display_dim
    )
    _flag(adapter, dim_obj, "IDimension")
    state = adapter._attempt(lambda: dim_obj.DrivenState, default=None)
    if callable(state):
        state = adapter._attempt(lambda: state(), default=None)
    return state


async def _sketch_state(adapter: Any) -> str:
    res = await adapter.check_sketch_fully_defined()
    if res.is_success and res.data:
        return str(res.data.get("definition_state"))
    return f"probe-failed:{res.error}"


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # ---- Sketch 1: resolution, origin, coincident, driving dims ----------
    check("create_sketch probe-1", await adapter.create_sketch("Front"))

    circle_a = check("add_circle A @origin r8", await adapter.add_circle(0.0, 0.0, 8.0))
    circle_a_obj = adapter._sketch_entities[circle_a]

    # Step 1: accessor resolution on a circle (centre) and later on lines.
    center_a, how = _get_point(adapter, circle_a_obj, "ISketchArc", "GetCenterPoint2")
    if center_a is None:
        center_a, how = _get_point(adapter, circle_a_obj, "ISketchArc", "GetCenterPoint")
        how = f"GetCenterPoint {how}"
    else:
        how = f"GetCenterPoint2 {how}"
    record("1a circle centre accessor", center_a is not None, how)
    if center_a is not None:
        record("1a centre coords", _xyz(adapter, center_a) is not None, str(_xyz(adapter, center_a)))

    # Step 2: origin selection.
    origin, origin_how = _resolve_origin(adapter)
    record("2 origin selection", origin is not None, origin_how)

    # Step 3: coincident centre -> origin. Creation-time inference may have
    # anchored it already, so capture the state before and after.
    state_before = await _sketch_state(adapter)
    coincident_result = "skipped (no origin)"
    if center_a is not None and origin is not None:
        rel = _add_relation_raw(adapter, [center_a, origin], 9)
        coincident_result = "ok" if rel is not None else "None/failed"
    state_mid = await _sketch_state(adapter)
    dia_a = check(
        "diameter dim A (16)",
        await adapter.add_sketch_dimension(circle_a, None, "diameter", 16.0),
    )
    state_a = await _sketch_state(adapter)
    record(
        "3 coincident centre->origin",
        state_a == "fully_defined",
        f"AddRelation(9)={coincident_result}, state: created={state_before}, "
        f"+coincident={state_mid}, +dia={state_a}",
    )
    dia_a_driven = _driven_state(adapter, adapter._sketch_entities[dia_a])

    # Step 4: circle B at (-20,-15), H/V driving dims to origin, rebuild.
    circle_b = check("add_circle B @(-20,-15) r5", await adapter.add_circle(-20.0, -15.0, 5.0))
    circle_b_obj = adapter._sketch_entities[circle_b]
    center_b, how_b = _get_point(adapter, circle_b_obj, "ISketchArc", "GetCenterPoint2")
    record("4a circle B centre accessor", center_b is not None, how_b)

    step4_ok = False
    detail4 = ""
    if center_b is not None and origin is not None:
        try:
            _add_point_pair_dim(
                adapter, center_b, origin, "horizontal", 20.0, (-0.010, -0.030, 0.0)
            )
            _add_point_pair_dim(
                adapter, center_b, origin, "vertical", 15.0, (-0.035, -0.0075, 0.0)
            )
            dia_b = check(
                "diameter dim B (10)",
                await adapter.add_sketch_dimension(circle_b, None, "diameter", 10.0),
            )
            adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False))
            xyz_b = _xyz(adapter, center_b)
            state_b = await _sketch_state(adapter)
            side_kept = (
                xyz_b is not None
                and abs(xyz_b[0] - (-20.0)) < 1e-3
                and abs(xyz_b[1] - (-15.0)) < 1e-3
            )
            step4_ok = side_kept and state_b == "fully_defined"
            detail4 = f"centre after rebuild={xyz_b}, state={state_b}"

            # Step 5: DrivenState of the diameter dims (expect 2 = driving).
            driven_b = _driven_state(adapter, adapter._sketch_entities[dia_b])
            record(
                "5 diameter DrivenState",
                driven_b == 2,
                f"B dia={driven_b!r} (A dia={dia_a_driven!r}); 2=driving, 1=driven",
            )
        except Exception as exc:  # noqa: BLE001
            detail4 = f"{type(exc).__name__}: {exc}"
    record("4 H/V driving dims, negative quadrant", step4_ok, detail4)

    check("exit_sketch probe-1", await adapter.exit_sketch())

    # ---- Sketch 2: relation enums on points (scratch geometry) -----------
    check("create_sketch probe-2", await adapter.create_sketch("Front"))
    circle_c = check("add_circle C", await adapter.add_circle(30.0, 10.0, 4.0))
    circle_d = check("add_circle D", await adapter.add_circle(50.0, 10.0, 4.0))
    center_c, _ = _get_point(adapter, adapter._sketch_entities[circle_c], "ISketchArc", "GetCenterPoint2")
    center_d, _ = _get_point(adapter, adapter._sketch_entities[circle_d], "ISketchArc", "GetCenterPoint2")

    if center_c is not None and center_d is not None:
        rel4 = _add_relation_raw(adapter, [center_c, center_d], 4)
        rel25 = None
        if rel4 is None:
            rel25 = _add_relation_raw(adapter, [center_c, center_d], 25)
        record(
            "6 horizontal between points",
            rel4 is not None or rel25 is not None,
            f"enum4={'ok' if rel4 else 'failed'}, enum25={'ok' if rel25 else 'not-tried' if rel4 else 'failed'}",
        )
    else:
        record("6 horizontal between points", False, "centre resolution failed")

    line_1 = check("add_line L1", await adapter.add_line(0.0, -30.0, 20.0, -30.0))
    line_2 = check("add_line L2", await adapter.add_line(20.0, -25.0, 40.0, -25.0))
    l1_start, _ = _get_point(adapter, adapter._sketch_entities[line_1], "ISketchLine", "GetStartPoint2")
    l1_end, _ = _get_point(adapter, adapter._sketch_entities[line_1], "ISketchLine", "GetEndPoint2")
    l2_start, how_l2 = _get_point(adapter, adapter._sketch_entities[line_2], "ISketchLine", "GetStartPoint2")
    record("1b line endpoint accessor", l1_end is not None and l2_start is not None, how_l2)

    if l1_end is not None and l2_start is not None:
        rel42 = _add_relation_raw(adapter, [l1_end, l2_start], 42)
        # Merging destroys one of the point objects — the old handle throws
        # "disconnected from its clients". Re-resolve freshly (the lazy-ref
        # lesson the adapter design relies on).
        l2_start_fresh, _ = _get_point(
            adapter, adapter._sketch_entities[line_2], "ISketchLine", "GetStartPoint2"
        )
        xyz_l2 = _xyz(adapter, l2_start_fresh) if l2_start_fresh is not None else None
        merged = xyz_l2 is not None and abs(xyz_l2[0] - 20.0) < 1e-3 and abs(xyz_l2[1] - (-30.0)) < 1e-3
        record(
            "7a MERGEPOINTS(42)",
            rel42 is not None and merged,
            f"AddRelation={'ok' if rel42 else 'failed'}, L2.start re-resolved={xyz_l2} (expect (20,-30))",
        )
    else:
        record("7a MERGEPOINTS(42)", False, "endpoint resolution failed")

    if center_d is not None:
        rel12 = _add_relation_raw(
            adapter, [center_d, adapter._sketch_entities[line_1]], 12
        )
        record("7b ATMIDDLE(12)", rel12 is not None, "circle D centre onto L1")
    else:
        record("7b ATMIDDLE(12)", False, "centre resolution failed")

    check("exit_sketch probe-2", await adapter.exit_sketch())
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True))

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n==== PROBE SUMMARY ====", flush=True)
    for step, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {step}{': ' + detail if detail else ''}", flush=True)
    return {"probe": f"{passed}/{len(RESULTS)} PASS"}


if __name__ == "__main__":
    sys.exit(run_build(build))

"""MS first-pick/late-observer diagnostic; no native pre-pick observer.

The recipe owns packet authorization and the original first-pick result.
Collect only from the optional _hit_test_edge post-result callback while its
original zoom and first-attempt caller frames remain live. Observations are
AFTER the native result, never pre-pick or a historic-state reproduction.
The exact-edge comparison is allowed only after original-first-miss plus one
explicitly diagnostic same-point coordinate miss. It never heals either result.
"""

import math
import ntpath
import sys
import time
from collections.abc import Mapping


_EDGE_CAP = 64
_LIST_CAP = 64
_REF_CAP = 1024
_EDGE_TOL_M = 1e-7  # 0.1 micrometre; NOT an inferred pick-aperture radius.
_FRAME_TOL_M = 1e-12
_SHEET_BIND_TOL_M = 1e-9
_MISSING = object()


def _safe(value, depth=0):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"unsupported": "nonfinite double"}
    if isinstance(value, str):
        return value if len(value) <= 4096 else {"text": value[:4096], "truncated": True}
    if isinstance(value, (bytes, bytearray)):
        return {"hex": bytes(value[:_REF_CAP]).hex(), "length": len(value),
                "truncated": len(value) > _REF_CAP}
    if depth >= 8:
        return {"unsupported": "JSON nesting cap"}
    if isinstance(value, (tuple, list)):
        rows = [_safe(v, depth + 1) for v in value[:_LIST_CAP]]
        return rows if len(value) <= _LIST_CAP else {"items": rows, "count": len(value), "truncated": True}
    if isinstance(value, dict):
        return {str(k): _safe(v, depth + 1) for k, v in value.items()}
    # A Python proxy's repr/address is NOT a native entity identity.
    return {"unsupported": "non-JSON native value", "python_type": type(value).__name__}


def _numbers(value, length):
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise ValueError("expected native numeric array of length " + str(length))
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        raise ValueError("native numeric array has a nonnumeric element")
    result = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("native numeric array has a nonfinite element")
    return result


def _path(value):
    if not isinstance(value, str) or not value:
        raise ValueError("missing native path")
    return value.replace("\\", "/")


def _persistent(value):
    if not isinstance(value, (bytes, bytearray, tuple, list)) or not 0 < len(value) <= _REF_CAP:
        raise ValueError("persistent-reference byte array missing or exceeds 1024-byte cap")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255 for v in value):
        raise ValueError("persistent-reference result is not a byte array")
    return {"hex": bytes(value).hex(), "length": len(value),
            "scope": "only the explicitly named model document; not a file digest"}


def _distance(a, b):
    return math.dist(a, b)


def _frozen_context(balloons, view, leaf, point_mm, sheet_xy):
    """Read existing caller locals, never recompute explode by mutating a model."""
    frame = sys._getframe(1)
    pick_frame = {"status": "unsupported", "reason": "original _hit_test_edge frame not found"}
    try:
        for _ in range(32):
            if frame is None:
                break
            local = frame.f_locals
            if (frame.f_globals is vars(balloons)
                    and frame.f_code.co_name == "_hit_test_edge"):
                pick_frame = {"status": "ok", "source": frame.f_code.co_filename,
                              "line": frame.f_lineno,
                              "sheet_xy_matches": _numbers(local.get("sheet_xy"), 2) == sheet_xy,
                              "coordinate_return": local.get("selected", "not_yet_called"),
                              "redraw": local.get("redraw")}
            if (frame.f_globals is vars(balloons)
                    and frame.f_code.co_name == "_select_balloon_anchor"):
                candidates = local.get("candidates")
                if (not isinstance(candidates, (tuple, list)) or not candidates
                        or candidates[0] is not leaf or local.get("view") is not view
                        or tuple(local["anchor"].point_mm) != point_mm
                        or _numbers(local.get("sheet_xy"), 2) != sheet_xy):
                    raise ValueError("original frozen-anchor caller does not bind these exact arguments")
                offsets = local.get("offsets")
                if not isinstance(offsets, Mapping):
                    raise ValueError("original frozen-anchor offsets mapping is unavailable")
                prefixes = _path(leaf.path).split("/")
                if len(prefixes) > _LIST_CAP:
                    raise ValueError("component ancestry exceeds cap")
                copied, rows = {}, []
                for count in range(1, len(prefixes) + 1):
                    prefix = "/".join(prefixes[:count]).casefold()
                    present = prefix in offsets
                    value = _numbers(offsets[prefix], 3) if present else (0.0, 0.0, 0.0)
                    if present:
                        copied[prefix] = value
                    rows.append({"component_prefix": prefix, "present": present, "translation_m": value})
                return copied, {"status": "ok", "source": frame.f_code.co_filename,
                                "line": frame.f_lineno, "function": frame.f_code.co_name,
                                "offsets": rows,
                                "original_attempt": local.get("attempt"),
                                "prior_original_pick_outcomes": list(local.get("picks", ()))[:3],
                                "original_hit_frame": pick_frame,
                                "semantics": "original offsets mapping, own and enclosing prefixes, metres"}
            frame = frame.f_back
        raise ValueError("no matching live original _select_balloon_anchor frame within 32 frames")
    finally:
        del frame


class _Capture:
    def __init__(self, adapter, view, leaf, point_mm, sheet_xy, balloons, phase):
        self.adapter, self.view, self.leaf, self.balloons = adapter, view, leaf, balloons
        self.out = {"schema": "fixed-anchor-capture/1", "phase": phase,
                    "native_calls_tested": False, "queries": {},
                    "limits": {"visible_edges": _EDGE_CAP, "persistent_ref_bytes": _REF_CAP,
                               "list_items": _LIST_CAP, "caller_frames": 32},
                    "physical_tolerances_m": {"edge": _EDGE_TOL_M, "component_transform_agreement": _FRAME_TOL_M,
                                               "original_sheet_projection_agreement": _SHEET_BIND_TOL_M},
                    "input_authorization": "not established here: runner must bind actual restored worker inputs",
                    "limitations": ["Entity-only selection is not coordinate-pick success or an aperture measurement.",
                                    "A listed visible edge may be occluded at the particular anchor point.",
                                    "Source/module receipts cannot establish loaded native file byte identity."]}
        self.point_mm = _numbers(point_mm, 3)
        self.local_m = tuple(v / 1000.0 for v in self.point_mm)
        self.sheet = _numbers(sheet_xy, 2)
        self.out["input"] = {"point_component_mm": self.point_mm, "sheet_xy_m": self.sheet,
                             "leaf_path": _safe(leaf.path), "leaf_name": _safe(leaf.name),
                             "leaf_visible": _safe(leaf.visible)}
        self.draw = self.q("IModelDoc2.currentModel", lambda: self.bound(adapter.currentModel, "IModelDoc2"), obj=True)
        self.sw = self.q("ISldWorks.adapter.swApp", lambda: self.bound(adapter.swApp, "ISldWorks"), obj=True)
        self.v = self.q("IView.argument", lambda: self.bound(view, "IView"), obj=True)
        self.component = self.q("IComponent2.leaf.component", lambda: self.bound(leaf.component, "IComponent2"), obj=True)
        self.q("IModelDoc2.SelectionManager", lambda: self.manager, obj=True)

    def bound(self, obj, interface):
        if obj is None or obj is _MISSING:
            raise ValueError("null/unavailable " + interface)
        return self.balloons._early_bound(self.balloons._bind(obj, interface), interface)

    @property
    def manager(self):
        # IModelDoc2.SelectionManager documentation: pointers are transient
        # and invalid after another selection. Reacquire for each query.
        return self.bound(self.draw.SelectionManager, "ISelectionMgr")

    def q(self, key, fn, obj=False):
        try:
            value = fn()
            if value is _MISSING or (obj and value is None):
                raise ValueError("null/unavailable native result")
            self.out["queries"][key] = {"status": "ok", "value":
                {"native_object_returned": True, "identity": "not implied by this marker"} if obj else _safe(value)}
            return value
        except Exception as error:
            self.out["queries"][key] = {"status": "unsupported" if isinstance(error, (AttributeError, ValueError, TypeError)) else "error",
                                        "error_type": type(error).__name__, "message": str(error)[:4096]}
            return _MISSING

    def transform(self, key, getter):
        transform = self.q(key, lambda: self.bound(getter(), "IMathTransform"), obj=True)
        self.q(key + ".ArrayData", lambda: _numbers(transform.ArrayData, 16))
        return transform

    def multiply(self, xyz, transform):
        # Reuse the exact already-loaded SDK VT_ARRAY|VT_R8 helper; no imports.
        arg = self.balloons._sw_drawing.double_array(list(_numbers(xyz, 3)))
        if isinstance(arg, (tuple, list)):
            raise ValueError("SDK double_array degraded to a Python sequence; no native marshalling proof")
        point = self.balloons._com_invoke(self.utility, "IMathUtility", "CreatePoint", arg)
        if point is None:
            raise ValueError("IMathUtility.CreatePoint returned null")
        result = self.balloons._com_invoke(point, "IMathPoint", "MultiplyTransform", transform)
        if result is None:
            raise ValueError("IMathPoint.MultiplyTransform returned null")
        return _numbers(self.balloons._com_invoke(result, "IMathPoint", "ArrayData"), 3)

    def persist(self, key, model, entity):
        return self.q(key, lambda: _persistent(self.bound(model.Extension, "IModelDocExtension").GetPersistReference3(entity)))

    def owner(self, key, entity):
        owner = self.q(key + ".IEntity.GetComponent", lambda: self.bound(self.bound(entity, "IEntity").GetComponent(), "IComponent2"), obj=True)
        name = self.q(key + ".owner.Name2", lambda: _path(owner.Name2))
        self.q(key + ".owner.GetPathName", lambda: _path(owner.GetPathName()))
        self.q(key + ".owner.ReferencedConfiguration", lambda: owner.ReferencedConfiguration)
        same = self.q(key + ".owner.IsSameLeaf", lambda: self.sw.IsSame(owner, self.component))
        return same == 1 and name is not _MISSING and name.casefold() == _path(self.leaf.path).casefold()

    def snapshot(self):
        self.out["started_unix_ns"] = time.time_ns()
        draw_path = self.q("drawing.GetPathName", lambda: _path(self.draw.GetPathName()))
        doc_type = self.q("drawing.GetType", lambda: self.draw.GetType())
        name = self.q("view.GetName2", lambda: self.v.GetName2())
        actual_name = self.q("leaf.component.Name2", lambda: _path(self.component.Name2))
        model_path = self.q("leaf.component.GetPathName", lambda: _path(self.component.GetPathName()))
        configuration = self.q("leaf.component.ReferencedConfiguration", lambda: self.component.ReferencedConfiguration)
        self.model = self.q("leaf.component.GetModelDoc2", lambda: self.bound(self.component.GetModelDoc2(), "IModelDoc2"), obj=True)
        loaded_path = self.q("leaf.loaded_model.GetPathName", lambda: _path(self.model.GetPathName()))
        loaded_type = self.q("leaf.loaded_model.GetType", lambda: self.model.GetType())
        loaded_configuration = self.q("leaf.loaded_model.active_configuration", lambda:
            self.bound(self.bound(self.model.ConfigurationManager, "IConfigurationManager").ActiveConfiguration, "IConfiguration").Name)
        self.q("view.ReferencedConfiguration", lambda: self.v.ReferencedConfiguration)
        referenced = self.q("view.ReferencedDocument", lambda: self.bound(self.v.ReferencedDocument, "IModelDoc2"), obj=True)
        self.q("view.referenced_document.GetPathName", lambda: _path(referenced.GetPathName()))
        self.q("view.IsExploded", lambda: self.v.IsExploded())
        active_view = self.q("drawing.ActiveDrawingView", lambda: self.bound(self.bound(self.draw, "IDrawingDoc").ActiveDrawingView, "IView"), obj=True)
        active_same = self.q("drawing.active_view.IsSameTarget", lambda: self.sw.IsSame(active_view, self.v))
        self.q("selection.GetSelectedObjectCount2.before", lambda: self.manager.GetSelectedObjectCount2(-1))
        self.q("ISldWorks.GetSelectionFilters", lambda: self.sw.GetSelectionFilters())
        self.q("ISldWorks.GetApplySelectionFilter", lambda: self.sw.GetApplySelectionFilter())
        self.out["pick_aperture"] = {"status": "unsupported", "reason":
            "No documented native aperture-radius getter grounded in installed v3.12.1 docs/SDK. Scale2 and 5-8px observations are not aperture readbacks."}
        self.utility = self.q("ISldWorks.GetMathUtility", lambda: self.balloons._com_invoke(self.sw, "ISldWorks", "GetMathUtility"), obj=True)
        self.component_transform = self.transform("leaf.Transform2", lambda: self.component.Transform2)
        self.transform("leaf.GetTotalTransform.False", lambda: self.component.GetTotalTransform(False))
        self.transform("leaf.GetTotalTransform.True", lambda: self.component.GetTotalTransform(True))
        self.view_transform = self.transform("IView.ModelToViewTransform", lambda: self.v.ModelToViewTransform)
        model_view = self.q("drawing.ActiveView", lambda: self.bound(self.draw.ActiveView, "IModelView"), obj=True)
        self.q("IModelView.Scale2", lambda: model_view.Scale2)
        self.q("IModelView.GetVisibleBox", lambda: model_view.GetVisibleBox())
        perspective = self.q("IModelView.HasPerspective", lambda: model_view.HasPerspective())
        for member in ("FrameWidth", "FrameHeight"):
            self.q("IModelView." + member, lambda member=member: getattr(model_view, member))
        self.screen_transform = self.transform("IModelView.Transform", lambda: model_view.Transform)
        hwnd = self.q("IModelView.GetViewHWndx64", lambda: model_view.GetViewHWndx64())
        self.window(hwnd)
        pixel = self.q("sheet_to_current_view_pixel", lambda: self.multiply((*self.sheet, 0.0), self.screen_transform))
        self.out["viewport_projection"] = {"status": "ok" if pixel is not _MISSING and perspective is False else "unsupported",
            "native_current_view_pixel_xyz": _safe(pixel), "input_frame": "drawing-sheet metres, supplied sheet_xy and z=0 exactly as original SelectByID2",
            "output_frame": "IModelView.Transform pixels, current-view upper-left origin, x right, y down; NOT assembly metres",
            "desktop_projection": {"status": "unsupported", "reason":
                "ClientToScreen origin and DPI contexts are recorded, but no unchecked cross-process pixel/DPI equivalence is asserted. No guessed desktop coordinates."}}
        context = self.q("frozen_caller_offsets", lambda: _frozen_context(self.balloons, self.view, self.leaf, self.point_mm, self.sheet))
        self.offsets = context[0] if context is not _MISSING else _MISSING
        if context is not _MISSING:
            self.out["frozen_caller"] = context[1]
        native_component = self.q("anchor.native_component_to_root_m", lambda: self.multiply(self.local_m, self.component_transform))
        self.root_point = self.q("anchor.frozen_helper_root_with_explode_m", lambda:
            _numbers(self.balloons._anchor_model_points(self.adapter, self.leaf, [self.local_m], self.offsets,
                     stem="ms-stop-block", label="fixed-anchor diagnostic readback")[0], 3))
        delta = self.q("anchor.native_vs_frozen_component_distance_m", lambda:
            _distance(tuple(native_component[i] + self.explode()[i] for i in range(3)), self.root_point))
        projected = self.q("anchor.native_root_to_drawing_view_m", lambda: self.multiply(self.root_point, self.view_transform))
        sheet_delta = self.q("anchor.original_sheet_distance_m", lambda: _distance(projected[:2], self.sheet))
        self.out["projection_derivation"] = {
            "operations": ["point_mm / 1000 -> component-local metres",
                           "IMathPoint.MultiplyTransform(IComponent2.Transform2) -> root metres",
                           "add ORIGINAL own/enclosing explode translations in metres",
                           "IMathPoint.MultiplyTransform(IView.ModelToViewTransform) -> drawing view; original helper takes x/y as sheet metres",
                           "supplied sheet x/y with z=0, multiplied by drawing ActiveView.Transform -> current-view top-down pixels"],
            "matrix_order": "Native documented rotation, then scale, then translation; raw 16-double arrays retained, never interpreted as row-major OS matrices.",
            "status": "ok" if delta is not _MISSING and delta <= _FRAME_TOL_M and sheet_delta is not _MISSING and sheet_delta <= _SHEET_BIND_TOL_M else "unsupported"}
        target = (doc_type == 3 and name == "Drawing View4" and self.point_mm == (21.0, 4.3, 11.0)
                  and _path(self.leaf.path).casefold() == "ms-stop-block-1" and self.leaf.visible is True
                  and actual_name is not _MISSING and actual_name.casefold() == "ms-stop-block-1"
                  and self.balloons._HIT_ZOOM_HALF == 0.0025 and active_same == 1)
        loaded = (loaded_type == 1 and isinstance(configuration, str) and bool(configuration)
                  and configuration == loaded_configuration and isinstance(model_path, str) and isinstance(loaded_path, str)
                  and ntpath.normcase(ntpath.normpath(model_path)) == ntpath.normcase(ntpath.normpath(loaded_path)))
        first = (context is not _MISSING
                 and context[1]["original_attempt"] == 1
                 and context[1]["prior_original_pick_outcomes"] == []
                 and context[1]["original_hit_frame"].get("sheet_xy_matches") is True
                 and context[1]["original_hit_frame"].get("redraw") is False
                 and isinstance(context[1]["original_hit_frame"].get("coordinate_return"), bool))
        self.out["guards"] = {"exact_frozen_target_and_active_view": target,
                              "loaded_part_path_and_configuration_match": loaded,
                              "original_projection_bound": self.out["projection_derivation"]["status"] == "ok",
                              "native_viewport_projection_bound": self.out["viewport_projection"]["status"] == "ok",
                              "original_first_pick_context": first,
                              "original_first_miss_context": first and context[1]["original_hit_frame"]["coordinate_return"] is False,
                              "drawing_document_path": _safe(draw_path)}
        self.ready = (target and loaded and self.out["guards"]["original_projection_bound"]
                      and self.out["guards"]["native_viewport_projection_bound"]
                      and self.out["phase"] == "after_first_original_pick" and first)
        if first and context[1]["original_hit_frame"]["coordinate_return"]:
            self.selected_identity()

    def selected_identity(self):
        """Read the native coordinate hit's actual identity; never select here."""
        count = self.q("coordinate.selection.count", lambda: self.manager.GetSelectedObjectCount2(-1))
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            self.out["coordinate_hit_identity"] = {"status": "unsupported", "reason": "no selected entity"}
            return
        selected = self.q("coordinate.selection.entity", lambda:
            self.bound(self.manager.GetSelectedObject6(count, -1), "IEntity"), obj=True)
        selected_type = self.q("coordinate.selection.type", lambda: self.manager.GetSelectedObjectType3(count, -1))
        owner_ok = self.owner("coordinate.selection", selected)
        selected_view = self.q("coordinate.selection.view", lambda:
            self.manager.GetSelectedObjectsDrawingView2(count, -1), obj=True)
        same_view = self.q("coordinate.selection.IsSameTargetView", lambda: self.sw.IsSame(selected_view, self.v))
        self.persist("coordinate.selection.drawing_persistent_reference", self.draw, selected)
        self.out["coordinate_hit_identity"] = {
            "status": "bound" if selected_type == 1 and owner_ok and same_view == 1 else "unsupported",
            "selection_index": count, "edge_type": selected_type,
            "owner_is_exact_leaf": owner_ok, "drawing_view_is_exact_target": same_view == 1,
            "persistent_reference_scope": "current drawing only; not a file digest or local visibility proof"}

    def explode(self):
        if self.offsets is _MISSING:
            raise ValueError("original offsets unavailable; no mutating reconstruction permitted")
        return _numbers(self.balloons._explode_offset(self.offsets, self.leaf.path), 3)

    def root_with_explode(self, xyz):
        transformed, offset = self.multiply(xyz, self.component_transform), self.explode()
        return tuple(a + b for a, b in zip(transformed, offset))

    def window(self, hwnd):
        """DLL loading and every OS call are deferred until this explicit function."""
        try:
            import ctypes
            from ctypes import wintypes
            if not isinstance(hwnd, int) or isinstance(hwnd, bool) or hwnd == 0:
                raise ValueError("no valid 64-bit model-view HWND")
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            prototypes = {
                "GetClientRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
                "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
                "ClientToScreen": ([wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
                "GetDpiForWindow": ([wintypes.HWND], wintypes.UINT),
                "GetThreadDpiAwarenessContext": ([], ctypes.c_void_p),
                "GetWindowDpiAwarenessContext": ([wintypes.HWND], ctypes.c_void_p),
                "AreDpiAwarenessContextsEqual": ([ctypes.c_void_p, ctypes.c_void_p], wintypes.BOOL)}
            def call(name, *args):
                fn = getattr(user32, name)
                fn.argtypes, fn.restype = prototypes[name]
                ctypes.set_last_error(0)
                value = fn(*args)
                if not value and name != "AreDpiAwarenessContextsEqual":
                    raise OSError(ctypes.get_last_error(), name + " returned zero/null")
                return value
            def rect(name):
                value = wintypes.RECT()
                call(name, hwnd, ctypes.byref(value))
                return {"left": value.left, "top": value.top, "right_exclusive": value.right,
                        "bottom_exclusive": value.bottom, "width": value.right-value.left, "height": value.bottom-value.top}
            def origin():
                value = wintypes.POINT(0, 0)
                call("ClientToScreen", hwnd, ctypes.byref(value))
                return {"x": value.x, "y": value.y, "frame": "OS device screen coordinates of HWND client origin"}
            self.q("Win32.GetClientRect", lambda: rect("GetClientRect"))
            self.q("Win32.GetWindowRect", lambda: rect("GetWindowRect"))
            self.q("Win32.ClientToScreen.origin", origin)
            self.q("Win32.GetDpiForWindow", lambda: call("GetDpiForWindow", hwnd))
            thread = self.q("Win32.GetThreadDpiAwarenessContext", lambda: call("GetThreadDpiAwarenessContext"))
            window = self.q("Win32.GetWindowDpiAwarenessContext", lambda: call("GetWindowDpiAwarenessContext", hwnd))
            self.q("Win32.AreDpiAwarenessContextsEqual", lambda: bool(call("AreDpiAwarenessContextsEqual", thread, window)))
            self.out["window_geometry_note"] = "GetWindowRect is DPI-virtualized and may include invisible resize borders; raw visible box is separate, not assumed to share its origin. No DPI setter is called."
        except Exception as error:
            self.out["window_geometry"] = {"status": "unsupported", "error_type": type(error).__name__, "message": str(error)[:4096]}

    def edges(self):
        count = self.q("IView.GetVisibleEntityCount2.EDGE", lambda: self.v.GetVisibleEntityCount2(self.component, 1))
        result = self.out["exact_edge_comparison"] = {"status": "unsupported", "count": _safe(count), "edges": [],
            "selection_attempted": False, "rule": "ALL listed edges resolved, unique within 1e-7 m in component AND root space; owner IS actual leaf; part/view correspondence roundtrip IS listed edge"}
        if isinstance(count, bool) or not isinstance(count, int) or not 0 < count <= _EDGE_CAP:
            result["reason"] = "count is unavailable, zero, invalid, or greater than 64; NO enumeration"
            return
        raw = self.q("IView.GetVisibleEntities2.raw_once", lambda:
            self.balloons._sw_drawing.raw_visible_entities(self.view, self.leaf.component, 1), obj=True)
        if not isinstance(raw, (tuple, list)) or len(raw) != count or len(raw) > _EDGE_CAP:
            result["reason"] = "enumeration/count mismatch or unsupported array; no partial census can authorize selection"
            result["returned_count"] = len(raw) if isinstance(raw, (tuple, list)) else None
            return
        complete, candidates = True, []
        for index, raw_edge in enumerate(raw):
            key = "edge[" + str(index) + "]"
            row = {"index": index, "index_is_identity": False}
            result["edges"].append(row)
            edge = self.q(key + ".IEdge", lambda: self.bound(raw_edge, "IEdge"), obj=True)
            owner_ok = self.owner(key, edge)
            row["owner_matches_actual_leaf"] = owner_ok
            self.persist(key + ".drawing.GetPersistReference3", self.draw, edge)
            # This raw query is NOT used for exactness: its context frame is not
            # guessed from its numbers or from which input yields a small distance.
            self.q(key + ".visible.GetClosestPointOn.component_input.frame_unproven", lambda:
                _numbers(edge.GetClosestPointOn(*self.local_m), 5))
            part = self.q(key + ".part.GetCorrespondingEntity2", lambda:
                self.bound(self.bound(self.model.Extension, "IModelDocExtension").GetCorrespondingEntity2(edge), "IEdge"), obj=True)
            self.persist(key + ".part.GetPersistReference3", self.model, part)
            assembly = self.q(key + ".component.GetCorrespondingEntity", lambda:
                self.bound(self.component.GetCorrespondingEntity(part), "IEntity"), obj=True)
            roundtrip = self.q(key + ".view.GetCorrespondingEntity", lambda:
                self.bound(self.v.GetCorrespondingEntity(assembly), "IEntity"), obj=True)
            same = self.q(key + ".roundtrip.IsSameVisibleEdge", lambda: self.sw.IsSame(roundtrip, edge))
            closest = self.q(key + ".part.GetClosestPointOn.component_m", lambda:
                _numbers(part.GetClosestPointOn(*self.local_m), 5))
            local_distance = self.q(key + ".part.closest_distance_m", lambda: _distance(closest[:3], self.local_m))
            closest_root = self.q(key + ".closest_root_with_explode_m", lambda: self.root_with_explode(closest[:3]))
            root_distance = self.q(key + ".root.closest_distance_m", lambda: _distance(closest_root, self.root_point))
            closest_sheet = self.q(key + ".closest_drawing_view_m", lambda: self.multiply(closest_root, self.view_transform))
            sheet_distance = self.q(key + ".sheet.closest_distance_m", lambda: _distance(closest_sheet[:2], self.sheet))
            resolved = (owner_ok and same == 1 and local_distance is not _MISSING
                        and root_distance is not _MISSING and sheet_distance is not _MISSING)
            exact = resolved and local_distance <= _EDGE_TOL_M and root_distance <= _EDGE_TOL_M and sheet_distance <= _EDGE_TOL_M
            row.update({"frame_and_identity_resolved": resolved, "within_strict_physical_tolerance": exact,
                        "part_distance_m": _safe(local_distance), "root_distance_m": _safe(root_distance),
                        "sheet_distance_m": _safe(sheet_distance)})
            complete = complete and resolved
            if exact:
                candidates.append((index, edge))
        result["all_edges_resolved"] = complete
        result["exact_candidate_indices"] = [index for index, _ in candidates]
        distances = [row["part_distance_m"] for row in result["edges"] if isinstance(row.get("part_distance_m"), float)]
        result["nearest_part_distance_m"] = min(distances) if distances else None
        if not self.ready or not complete or len(candidates) != 1:
            result["reason"] = "unbound target/projection/frame, incomplete census, or not exactly one physically exact edge; no nearest-edge fallback"
            return
        result["unique_exact_index"] = candidates[0][0]
        self.q("selection.ClearSelection2.before", lambda: self.draw.ClearSelection2(True))
        if self.q("selection.GetSelectedObjectCount2.cleared", lambda: self.manager.GetSelectedObjectCount2(-1)) != 0:
            result["reason"] = "selection list was not read back empty"
            return
        data = self.q("ISelectionMgr.CreateSelectData", lambda: self.bound(self.manager.CreateSelectData(), "ISelectData"), obj=True)
        def set_view():
            # The only property put: transient SELECT-DATA context, not model,
            # viewport, preferences, zoom, document activation, or geometry.
            data.View = self.v
            return True
        if self.q("ISelectData.View.selection_context_only", set_view) is not True:
            result["reason"] = "cannot bind transient selection data to original view"
            return
        result["selection_attempted"] = True
        selected = self.q("IEntity.Select4.once", lambda: self.bound(candidates[0][1], "IEntity").Select4(False, data))
        selection_count = self.q("selection.GetSelectedObjectCount2.after", lambda: self.manager.GetSelectedObjectCount2(-1))
        if selected is not True or selection_count != 1:
            result["reason"] = "entity-only selection failed or did not read back exactly one entity"
            return
        readback = self.q("selection.GetSelectedObject6", lambda: self.bound(self.manager.GetSelectedObject6(1, -1), "IEntity"), obj=True)
        selected_type = self.q("selection.GetSelectedObjectType3", lambda: self.manager.GetSelectedObjectType3(1, -1))
        same = self.q("selection.IsSameExactCandidate", lambda: self.sw.IsSame(readback, candidates[0][1]))
        owner_ok = self.owner("selection.readback", readback)
        selected_view = self.q("selection.GetSelectedObjectsDrawingView2", lambda: self.manager.GetSelectedObjectsDrawingView2(1, -1), obj=True)
        same_view = self.q("selection.IsSameDrawingView", lambda: self.sw.IsSame(selected_view, self.v))
        self.q("selection.GetSelectionPoint2.raw_model_space_not_anchor_proof", lambda: self.manager.GetSelectionPoint2(1, -1))
        self.persist("selection.drawing.GetPersistReference3", self.draw, readback)
        result["status"] = "diagnostic_entity_selected_and_read_back" if selected_type == 1 and same == 1 and owner_ok and same_view == 1 else "unsupported"
        result["original_coordinate_pick_outcome"] = "unchanged: first original coordinate miss; no original redraw retries executed"


def collect_after_first_pick(adapter, view, leaf, point_mm, sheet_xy, balloons):
    """Post-result native readbacks at original first-pick zoom, hit or miss."""
    capture = None
    try:
        capture = _Capture(adapter, view, leaf, point_mm, sheet_xy, balloons, "after_first_original_pick")
        capture.snapshot()
        capture.out["status"] = "observed" if capture.ready else "unsupported"
        return _safe(capture.out)
    except Exception as error:
        result = capture.out if capture is not None else {"schema": "fixed-anchor-capture/1", "phase": "after_first_original_pick", "native_calls_tested": False}
        result.update(status="unsupported", collector_error={"type": type(error).__name__, "message": str(error)[:4096]})
        return _safe(result)


def collect_coordinate_identity(adapter, view, leaf, point_mm, sheet_xy, balloons):
    """Read back the diagnostic coordinate hit; no new selection or snapshot."""
    capture = None
    try:
        capture = _Capture(adapter, view, leaf, point_mm, sheet_xy, balloons, "after_first_original_pick")
        capture.selected_identity()
        return _safe(capture.out)
    except Exception as error:
        result = capture.out if capture is not None else {"phase": "after_first_original_pick"}
        result.update(status="unsupported", collector_error={"type": type(error).__name__, "message": str(error)[:4096]})
        return _safe(result)


def compare_exact_edge(adapter, view, leaf, point_mm, sheet_xy, balloons, diagnostic_selected):
    """Only after BOTH coordinate misses; bounded entity-only diagnostic."""
    capture = None
    result = {"schema": "fixed-anchor-capture/1", "phase": "after_first_original_pick", "native_calls_tested": False}
    try:
        if diagnostic_selected is not False:
            raise ValueError("exact-edge comparison requires diagnostic coordinate miss")
        capture = _Capture(adapter, view, leaf, point_mm, sheet_xy, balloons, "after_first_original_pick")
        result = capture.out
        capture.snapshot()
        capture.ready = capture.ready and capture.out["guards"]["original_first_miss_context"]
        if not capture.ready:
            raise ValueError("unbound original first-miss caller/target/projection; no edge census")
        zoom = capture.out["queries"].get("IModelView.Scale2", {}).get("value")
        if not isinstance(zoom, (int, float)) or abs(zoom - 86.36) > 1e-6:
            raise ValueError("original zoom changed after diagnostic coordinate miss; no edge census")
        capture.edges()
        result["status"] = result["exact_edge_comparison"]["status"]
    except Exception as error:
        result.update(status="unsupported", collector_error={"type": type(error).__name__, "message": str(error)[:4096]})
    finally:
        # Always attempt cleanup, including refused/failed comparisons. No
        # selection survives deliberately; cleanup failure is explicit evidence.
        try:
            draw = capture.draw if capture is not None and capture.draw is not _MISSING else adapter.currentModel
            draw.ClearSelection2(True)
            manager = balloons._early_bound(draw.SelectionManager, "ISelectionMgr")
            count = manager.GetSelectedObjectCount2(-1)
            result["selection_cleanup"] = {"status": "ok" if count == 0 else "error", "remaining_count": _safe(count)}
            if count != 0:
                result["status"] = "cleanup_failed"
        except Exception as error:
            result["selection_cleanup"] = {"status": "error", "error_type": type(error).__name__, "message": str(error)[:4096]}
            result["status"] = "cleanup_failed"
    return _safe(result)

"""SolidWorks-free contract for the drawing layout audit geometry.

Exercises the collision / sheet-overflow logic on plain boxes so a regression in
the audit is caught without a COM seat. The live element collection lives in
``_drawing_layout_collect``; native-math fakes exercise its detail-crop path here.

The ``*_real_boxes_*`` cases are positive controls: the element boxes measured
off the shipped, visually-inspected lever-bushing and platen-guide drawings must
audit clean, so the tolerances can never be tightened into flagging a known-good
print.
"""

from __future__ import annotations

import ast
import math as _math
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import solidworks_mcp.adapters

import _config
import _drawing_balloon_display
import _drawing_balloons
import _drawing_common
import _drawing_edges
import _drawing_layout_audit
import _drawing_detail_crop
from _drawing_layout_check import (
    DEFAULT_BOUNDARY_ALLOWANCE_M,
    DEFAULT_OVERLAP_TOL_M,
    CollisionScope,
    Crossing,
    DrawableRegion,
    LayoutElement,
    LeaderCrossing,
    LeaderSegment,
    Overlap,
    audit_layout,
    find_leader_crossings,
    find_leader_leader_crossings,
    find_overflows,
    find_overlaps,
    format_findings,
)
import _drawing_layout_collect
import _drawing_notes
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
import _drawing_scan
import _drawing_view_display
import _layout_audit
import _seat_forensics
import _telemetry


# ASME B sheet used by every project drawing (meters).
SHEET_W = 0.4318
SHEET_H = 0.2794

# The bound used by the pre-zone-border cases: the raw sheet rectangle, so each
# keeps asserting exactly what it did before the audit gained a zone frame.
WHOLE_SHEET = DrawableRegion.whole_sheet(SHEET_W, SHEET_H)
# The zone margins the project DRWDOT actually reports through
# ISheet::GetZoneMargin: a uniform 12.7 mm (0.5 in) on all four sides, read off
# a live sheet.
#
# The drawn frame USED to disagree with this metadata (left 15.9 / right 9.5 /
# bottom 13.3 / top 12.0 mm), which made the gate blind on the left by 3.2 mm --
# ink could clear the declared margin and still print on the drawn rule. The
# template was re-centred 2026-07-16 and the artwork now AGREES: measured on the
# rebuilt renders, the rules span left 0.0124..0.0128, right 0.4188..0.4192,
# bottom 0.0124..0.0128, top 0.2665..0.2669 -- centrelines within a 0.4 mm line
# width of 12.7 on all four sides.
#
# The gate still keys on the METADATA, and that is the point: it is queried from
# the live sheet, so it tracked the template edit without a code change. Do not
# replace these with measured drawn-frame constants -- that would freeze today's
# artwork into the test and go stale the next time the frame moves.
ZONE_MARGINS = {"left": 0.0127, "right": 0.0127, "bottom": 0.0127, "top": 0.0127}
ZONE_REGION = DrawableRegion.from_margins(SHEET_W, SHEET_H, **ZONE_MARGINS)


class _FakeAdapter:
    def __init__(self, model):
        self.currentModel = model

    @staticmethod
    def _attempt(callback, default=None):
        try:
            return callback()
        except Exception:
            return default

    @staticmethod
    def _attempt_with_error(callback):
        try:
            return callback(), None
        except Exception as exc:
            return None, exc

    @staticmethod
    def _get_attr_or_call(obj, name):
        member = getattr(obj, name, None)
        return member() if callable(member) else member


def _display_view(**overrides):
    readback = {
        "mode": 3,
        "use_parent": False,
        "faceted": False,
        "edges": True,
        "cosmetic_threads": True,
    }
    readback.update(overrides)
    return SimpleNamespace(
        SetDisplayMode4=lambda *_args: True,
        GetDisplayMode2=lambda: readback["mode"],
        GetUseParentDisplayMode=lambda: readback["use_parent"],
        GetFacettedHlrDisplay=lambda: readback["faceted"],
        GetDisplayEdgesInShadedMode=lambda: readback["edges"],
        GetCThreadQuality=lambda: readback["cosmetic_threads"],
    )


def test_high_quality_shaded_with_edges_uses_documented_com_shape():
    calls = []
    view = _display_view()
    view.SetDisplayMode4 = lambda *args: calls.append(args) or True

    _drawing_common.set_high_quality_shaded_with_edges(
        _FakeAdapter(None), view, label="Sheet1 Isometric"
    )

    assert calls == [(False, 3, False, True, True)]


def test_high_quality_shaded_with_edges_accepts_a_no_op_setter_on_a_correct_view():
    # SetDisplayMode4 returns False when the view already reads Shaded With
    # Edges (frame_assembly sets its exploded isometric before the BOM pass and
    # finalize re-applies it); the readback, not the setter's bool, is the proof.
    view = _display_view()
    view.SetDisplayMode4 = lambda *_args: False

    _drawing_common.set_high_quality_shaded_with_edges(
        _FakeAdapter(None), view, label="Sheet1 Isometric"
    )


def test_high_quality_shaded_with_edges_rejects_silent_write_failure():
    view = _display_view(mode=2)
    view.SetDisplayMode4 = lambda *_args: False

    with pytest.raises(RuntimeError, match="not precise Shaded With Edges"):
        _drawing_common.set_high_quality_shaded_with_edges(
            _FakeAdapter(None), view, label="Sheet1 Isometric"
        )


def test_high_quality_shaded_with_edges_surfaces_a_com_exception():
    view = _display_view()

    def boom(*_args):
        raise OSError("COM call rejected")

    view.SetDisplayMode4 = boom

    with pytest.raises(RuntimeError, match="SetDisplayMode4 raised"):
        _drawing_common.set_high_quality_shaded_with_edges(
            _FakeAdapter(None), view, label="Sheet1 Isometric"
        )


def test_hidden_lines_visible_forces_a_verified_hlr_transition(monkeypatch):
    mode = {"value": _drawing_view_display._SW_HLV}
    calls = []

    def set_mode(_use_parent, value, _faceted, _edges, _threads):
        calls.append(value)
        mode["value"] = value
        return True

    view = SimpleNamespace(
        SetDisplayMode4=set_mode,
        GetDisplayMode2=lambda: mode["value"],
    )
    monkeypatch.setattr(_drawing_view_display, "_early_bound", lambda value, _kind: value)

    _drawing_view_display.set_hidden_lines_visible(_FakeAdapter(None), view)

    assert calls == [_drawing_view_display._SW_HLR, _drawing_view_display._SW_HLV]


def test_hidden_lines_visible_rejects_a_stale_hlv_transition(monkeypatch):
    calls = []
    view = SimpleNamespace(
        SetDisplayMode4=lambda _parent, value, *_rest: calls.append(value) or False,
        GetDisplayMode2=lambda: _drawing_view_display._SW_HLV,
    )
    monkeypatch.setattr(_drawing_view_display, "_early_bound", lambda value, _kind: value)

    with pytest.raises(RuntimeError, match="transition drawing view through HLR"):
        _drawing_view_display.set_hidden_lines_visible(_FakeAdapter(None), view)

    assert calls == [_drawing_view_display._SW_HLR]


@pytest.mark.parametrize(
    ("defect", "value"),
    (
        ("mode", 2),
        ("use_parent", True),
        ("edges", False),
        ("cosmetic_threads", False),
    ),
)
def test_high_quality_shaded_with_edges_rejects_bad_readback(defect, value):
    view = _display_view(**{defect: value})

    with pytest.raises(RuntimeError, match="not precise Shaded With Edges"):
        _drawing_common.set_high_quality_shaded_with_edges(
            _FakeAdapter(None), view, label="Sheet1 Isometric"
        )


def test_high_quality_shaded_with_edges_ignores_transient_facet_flag():
    # A fresh view reads faceted=True until its first full compute (the export);
    # the pre-export setter must not fail on it.
    _drawing_common.set_high_quality_shaded_with_edges(
        _FakeAdapter(None), _display_view(faceted=True), label="Sheet1 Isometric"
    )


def _sheet_views(monkeypatch, views_by_sheet):
    active = {"sheet": None}
    ddoc = SimpleNamespace(
        ActivateSheet=lambda name: active.update(sheet=name) or name in views_by_sheet
    )
    monkeypatch.setattr(_drawing_common, "_early_bound", lambda value, _kind: ddoc)
    monkeypatch.setattr(
        _drawing_common, "iter_views", lambda _adapter: iter(views_by_sheet[active["sheet"]])
    )
    monkeypatch.setattr(
        _drawing_common, "view_name", lambda _adapter, view: view.GetName2()
    )


def _iso_view(name, faceted, orientation="*Isometric"):
    return SimpleNamespace(
        GetName2=lambda: name,
        GetOrientationName=lambda: orientation,
        GetFacettedHlrDisplay=lambda: faceted,
    )


def test_post_export_precision_proof_checks_every_isometric(monkeypatch):
    _sheet_views(
        monkeypatch,
        {
            "Sheet1": [_iso_view("Iso1", False), _iso_view("Front", True, "*Front")],
            "Sheet2": [_iso_view("Iso2", False)],
        },
    )

    checked = _drawing_common.assert_precise_isometric_views(
        _FakeAdapter(None), ("Sheet1", "Sheet2")
    )

    assert checked == 2


@pytest.mark.parametrize("faceted", (True, None))
def test_post_export_precision_proof_rejects_faceted_isometric(monkeypatch, faceted):
    _sheet_views(
        monkeypatch,
        {"Sheet1": [_iso_view("Iso1", False)], "Sheet2": [_iso_view("Iso2", faceted)]},
    )

    with pytest.raises(RuntimeError, match="'Iso2': exported isometric is not precision"):
        _drawing_common.assert_precise_isometric_views(
            _FakeAdapter(None), ("Sheet1", "Sheet2")
        )


def _el(label, x0, y0, x1, y1, kind="view", scope=CollisionScope.ALL, owner=""):
    return LayoutElement(label, kind, x0, y0, x1, y1, scope=scope, owner=owner)


# R18 run 20261013T031823504Z-e68aa7002ea54a59b5611f26fbb9465e,
# task.log at 42.7/51.5s (sketch geometry) and 48.5/59.9s (caption ink).
# Only the FIRST sketch -> parent SHEET hop was logged as a matrix. The later
# parent SHEET -> MODEL -> detail SHEET transforms below are SYNTHETIC, not
# recovered R18 matrices or claims of new native-seat execution.
_R18_SKETCH_MATRIX = (
    1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
    -0.36, -0.35, 0.0, 2.0, 0.0, 0.0, 0.0,
)
_R18_DETAIL = {
    "D": {
        "raw_centre": (0.0, -0.006647320062878381, 0.0),
        "raw_radius": 0.006724999999999981,
        "parent_centre": (0.18, 0.1716763399685608),
        "centre": (0.18, 0.095),
        "ratio": (4.0, 1.0),
        "outline": (0.1421321075479388, 0.05713200987360469,
                    0.21786799117225408, 0.1328679063850961),
        "crop": (0.15310000000000007, 0.06810000000000008,
                 0.20689999999999992, 0.12189999999999993),
        "caption": (0.1677665752508361, 0.05487079598662206,
                    0.19254814046822738, 0.06392559866220734),
    },
    "E": {
        "raw_centre": (0.13950591159423764, 0.005435871215965893, 0.0),
        "raw_radius": 0.011919069550251904,
        "parent_centre": (0.24975295579711881, 0.17771793560798294),
        "centre": (0.33, 0.11000000000000001),
        "ratio": (2.0, 1.0),
        "outline": (0.2958062990191663, 0.07580625403539039,
                    0.36419374578125124, 0.14419375332406856),
        "crop": (0.3061618608994962, 0.0861618608994962,
                 0.3538381391005038, 0.13383813910050382),
        "caption": (0.31788567224080266, 0.07298040133779266,
                    0.3421906688963211, 0.08203520401337794),
    },
}

# Closed surfaces from the generated SW2026 owners, not caller-requested members.
# One profile dispatch supports segment AND arc QI, but each binding exposes only
# its own surface. Bookkeeping on the underlying fixtures is never a COM member.
_OWNER_METHODS = {
    "IDrawingDoc": {"GetCurrentSheet", "GetFirstView"},
    "ISheet": {"GetProperties", "GetZoneMargin"},
    "IView": {
        "GetName2", "GetOrientationName", "GetOutline", "GetBaseView", "GetDetail",
        "UpdateViewDisplayGeometry", "GetAnnotations", "GetTableAnnotations", "GetNextView",
    },
    "IDetailCircle": {"GetLabel", "GetProfileItems"},
    "ISketchSegment": {"GetType", "GetSketch"},
    "ISketchArc": {"IsCircle", "GetCenterPoint2", "GetRadius"},
    "ISketchPoint": set(),
    "ISketch": set(),
    "IMathTransform": {"Inverse"},
    "ISldWorks": {"GetMathUtility"},
    "IMathUtility": {"CreatePoint"},
    "IMathPoint": {"MultiplyTransform"},
    "INote": {"GetAnnotation", "GetExtent", "GetText", "IsBomBalloon"},
    "IAnnotation": {
        "GetName", "GetType", "GetSpecificAnnotation", "GetPosition", "GetLeaderCount",
        "GetLeaderPointsAtIndex", "GetTextFormat", "SetTextFormat",
    },
    "ITextFormat": set(),
    "ITableAnnotation": {
        "GetAnnotation", "GetSplitInformation", "GetColumnWidth", "GetRowHeight",
    },
}
_OWNER_PROPERTIES = {
    "IView": {"Type", "ScaleRatio", "ModelToViewTransform"},
    "IDetailCircle": {"NoOutline"},
    "ISketchPoint": {"X", "Y", "Z"},
    "ISketch": {"ModelToSketchTransform"},
    "IMathTransform": {"ArrayData"},
    "IMathPoint": {"ArrayData"},
    "IAnnotation": {"OwnerType"},
    "ITextFormat": {"CharHeight"},
    "ITableAnnotation": {"RowCount", "ColumnCount"},
}


class _OwnerView:
    """A bound interface slice; it cannot borrow a sibling interface's member."""

    def __init__(self, target, interface):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_interface", interface)

    def __getattr__(self, name):
        methods = _OWNER_METHODS[self._interface]
        properties = _OWNER_PROPERTIES.get(self._interface, set())
        if name not in methods | properties:
            raise AttributeError(f"{self._interface} does not own {name}")
        value = getattr(self._target, name)
        if callable(value) != (name in methods):
            raise AssertionError(f"{self._interface}.{name} has the wrong native shape")
        self._target._native_reads.append((self._interface, name))
        return value

    def __setattr__(self, name, value):
        # The shared note writer's only native property assignment.
        if (self._interface, name) != ("ITextFormat", "CharHeight"):
            raise AttributeError(f"{self._interface} cannot write {name}")
        self._target._native_writes.append((self._interface, name, value))
        setattr(self._target, name, value)


def _owner_fake(interface, **members):
    return SimpleNamespace(
        _native_interfaces=(interface,), _native_reads=[], _native_writes=[], **members
    )


def _bind_owner(obj, interface, *_members, **_kwargs):
    if obj is None:
        return None
    if isinstance(obj, _OwnerView):
        if obj._interface == interface:
            return obj
        obj = obj._target
    owners = getattr(obj, "_native_interfaces", ())
    if interface not in owners:
        raise AssertionError(f"cannot bind {owners!r} as {interface}")
    if not hasattr(obj, "_native_reads"):
        obj._native_reads = []
        obj._native_writes = []
    return _OwnerView(obj, interface)



class _CropMathTransform:
    """Deterministic native-math shape; translation follows SW ArrayData."""
    _native_interfaces = ("IMathTransform",)

    def __init__(self, *, scale=1.0, translation=(0.0, 0.0, 0.0)):
        self.scale = scale
        self.translation = translation
        self.ArrayData = (
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            *translation, scale, 0.0, 0.0, 0.0,
        )
        self.inverse_calls = 0

    def Inverse(self):
        self.inverse_calls += 1
        return _CropMathTransform(
            scale=1.0 / self.scale,
            translation=tuple(-value / self.scale for value in self.translation),
        )

    def IInverse(self):
        raise AssertionError("native IInverse is not an automation call")

    def apply(self, xyz):
        return tuple(value * self.scale + offset
                     for value, offset in zip(xyz, self.translation))


class _CropMathPoint:
    _native_interfaces = ("IMathPoint",)

    def __init__(self, xyz):
        self.ArrayData = tuple(getattr(xyz, "value", xyz))

    def MultiplyTransform(self, transform):
        transform = _bind_owner(transform, "IMathTransform")
        return _CropMathPoint(transform._target.apply(self.ArrayData))


class _CropSketch:
    _native_interfaces = ("ISketch",)

    def __init__(self, transform):
        self.transform = transform
        self.views = []

    @property
    def ModelToSketchTransform(self):
        assert len(self.views) == 2 and all(view.refreshed for view in self.views), (
            "sketch transform read before both UpdateViewDisplayGeometry barriers"
        )
        return self.transform


class _CropView:
    _native_interfaces = ("IView",)

    # Official swDrawingViewTypes_e: detail=3, standard=6; not guessed 5.
    Type = 3

    def __init__(self, name, outline, parent, circle, transform, ratio):
        self.name, self.outline = name, outline
        self.parent, self.circle = parent, circle
        self.transform, self.ScaleRatio = transform, ratio
        self.annotations = []
        self.tables = []
        self.outline_reads = 0
        self.outline_refresh_states = []
        self.refreshed = False
        self.next_view = None
        self.defect = None
        self.refresh_events = []

    def GetName2(self):
        return self.name

    def GetOrientationName(self):
        return "*Front"

    def GetOutline(self):
        self.outline_reads += 1
        if self.defect == "outline-error":
            raise OSError("outline binding failed")
        if self.Type == 3:
            fresh = self.parent.refreshed and self.refreshed
            self.outline_refresh_states.append(fresh)
            if not fresh:
                # SYNTHETIC stale first-create extent, smaller than the crop.
                # Reading before BOTH barriers must make containment refuse.
                return (0.0, 0.0, 0.001, 0.001)
        return self.outline

    @property
    def ModelToViewTransform(self):
        assert self.refreshed, "transform read before UpdateViewDisplayGeometry"
        return self.transform

    def UpdateViewDisplayGeometry(self):
        self.refreshed = True
        self.refresh_events.append(self)
        # Native VT_VOID: returning None must not be mistaken for failure.

    def GetBaseView(self):
        return self.parent

    def GetDetail(self):
        if self.defect == "crop-binding-error":
            raise OSError("crop binding failed")
        return self.circle

    def GetAnnotations(self):
        return self.annotations

    def GetTableAnnotations(self):
        return self.tables

    def GetNextView(self):
        return self.next_view


def _crop_note(name, box, *, leader=()):
    x0, y0, x1, y1 = box
    return _owner_fake(
        "IAnnotation", GetName=lambda: name, GetType=lambda: 6, OwnerType=1,
        GetSpecificAnnotation=lambda: _owner_fake(
            "INote", GetExtent=lambda: (x0, y0, 0.0, x1, y1, 0.0),
            GetText=lambda: "", IsBomBalloon=lambda: False,
        ),
        GetLeaderCount=lambda: int(bool(leader)),
        GetLeaderPointsAtIndex=lambda _index: tuple(leader),
    )


def _crop_fixture(monkeypatch, label, *, centre=None):
    data = _R18_DETAIL[label]
    sketch_transform = _CropMathTransform(scale=2.0, translation=(-0.36, -0.35, 0.0))
    assert sketch_transform.ArrayData == _R18_SKETCH_MATRIX
    sketch = _CropSketch(sketch_transform)
    profile = _owner_fake(
        "ISketchSegment", GetType=lambda: 1, IsCircle=lambda: 1,
        GetCenterPoint2=lambda: _owner_fake(
            "ISketchPoint",
            X=data["raw_centre"][0], Y=data["raw_centre"][1], Z=data["raw_centre"][2],
        ),
        GetRadius=lambda: data["raw_radius"], GetSketch=lambda: sketch,
    )
    profile._native_interfaces = ("ISketchSegment", "ISketchArc")
    # No generic outline-flag probes are permitted: another production stem
    # uses NoOutline=True. HasFullOutline/GetDisplay/JaggedOutline are absent.
    circle = _owner_fake(
        "IDetailCircle",
        GetLabel=lambda: label, GetProfileItems=lambda: (profile,), NoOutline=True,
    )
    # SYNTHETIC affine view transforms: nonidentity parent inverse is essential.
    parent_transform = _CropMathTransform(scale=0.5, translation=(0.18, 0.175, 0.0))
    parent = _CropView("parent", (0.1, 0.15, 0.3, 0.25), None, None,
                       parent_transform, (1.0, 2.0))
    parent.Type = 6
    model_centre = parent_transform.Inverse().apply((*data["parent_centre"], 0.0))
    parent_transform.inverse_calls = 0
    scale = data["ratio"][0] / data["ratio"][1]
    target = centre or data["centre"]
    detail_transform = _CropMathTransform(
        scale=scale,
        translation=tuple(target[index] - model_centre[index] * scale
                          for index in range(2)) + (0.0,),
    )
    # Both objects are linked before the reader can fetch any transform.
    view = _CropView(label, data["outline"], parent, circle, detail_transform, data["ratio"])
    sketch.views = [parent, view]
    sheet_view = _owner_fake(
        "IView", GetNextView=lambda: view, GetAnnotations=lambda: [], GetTableAnnotations=lambda: [],
    )
    sheet = _bind_owner(_owner_fake(
        "ISheet",
        GetProperties=lambda: [0.0, 0.0, 1.0, 1.0, 0.0, SHEET_W, SHEET_H],
        GetZoneMargin=lambda _code: 0.0127,
    ), "ISheet")
    refreshed = []
    parent.refresh_events = view.refresh_events = refreshed

    model = _owner_fake(
        "IDrawingDoc", GetCurrentSheet=lambda: sheet, GetFirstView=lambda: sheet_view,
    )
    adapter = _FakeAdapter(model)
    utility = _owner_fake("IMathUtility", CreatePoint=_CropMathPoint)
    adapter.swApp = _bind_owner(
        _owner_fake("ISldWorks", GetMathUtility=lambda: utility), "ISldWorks"
    )
    monkeypatch.setattr(_drawing_detail_crop, "_early_bound", _bind_owner)
    monkeypatch.setattr(_drawing_layout_collect, "_early_bound", _bind_owner)
    monkeypatch.setattr(solidworks_mcp.adapters.sw_type_info, "early_bound", _bind_owner)
    monkeypatch.setattr(
        solidworks_mcp.adapters.sw_type_info, "early_bound_or_flag", _bind_owner
    )
    return adapter, view, profile, sketch_transform, refreshed


@pytest.mark.parametrize(
    ("producer", "required"),
    (
        ("input-view", "IView"),
        ("base-view", "IView"),
        ("detail-circle", "IDetailCircle"),
        ("profile-segment", "ISketchSegment"),
        ("profile-arc", "ISketchArc"),
        ("centre-point", "ISketchPoint"),
        ("profile-sketch", "ISketch"),
        ("sketch-transform", "IMathTransform"),
        ("sketch-inverse", "IMathTransform"),
        ("math-utility", "IMathUtility"),
        ("created-point", "IMathPoint"),
        ("transformed-point", "IMathPoint"),
        ("parent-transform", "IMathTransform"),
        ("detail-transform", "IMathTransform"),
        ("parent-inverse", "IMathTransform"),
    ),
)
def test_generic_crop_rejects_wrong_owner_at_each_native_producer(
    monkeypatch, producer, required
):
    adapter, view, profile, transform, _refreshed = _crop_fixture(monkeypatch, "D")
    wrong_calls = []

    def wrong_member(*_args):
        wrong_calls.append("borrowed member")
        raise AssertionError("wrong-owner member must never be invoked")

    # Decoy members exist on the wrong object: a pass-through cast would reach
    # them. The strict cast must refuse BEFORE the helper invokes any of them.
    wrong = _owner_fake(
        "INote", GetBaseView=wrong_member, GetLabel=wrong_member,
        GetType=wrong_member, IsCircle=wrong_member, GetCenterPoint2=wrong_member,
        GetSketch=wrong_member, Inverse=wrong_member, CreatePoint=wrong_member,
        MultiplyTransform=wrong_member, ArrayData=(0.0,) * 16,
        ModelToSketchTransform=transform, ModelToViewTransform=transform,
        X=0.0, Y=0.0, Z=0.0,
    )
    utility = adapter.swApp.GetMathUtility()
    input_view = view
    if producer == "input-view":
        input_view = wrong
    elif producer == "base-view":
        view.parent = wrong
    elif producer == "detail-circle":
        view.circle = wrong
    elif producer == "profile-segment":
        view.circle.GetProfileItems = lambda: (wrong,)
    elif producer == "profile-arc":
        wrong._native_interfaces = ("ISketchSegment",)
        wrong.GetType = lambda: 1  # The segment hop legitimately succeeds.
        view.circle.GetProfileItems = lambda: (wrong,)
    elif producer == "centre-point":
        profile.GetCenterPoint2 = lambda: wrong
    elif producer == "profile-sketch":
        profile.GetSketch = lambda: wrong
    elif producer == "sketch-transform":
        profile.GetSketch().transform = wrong
    elif producer == "sketch-inverse":
        transform.Inverse = lambda: wrong
    elif producer == "math-utility":
        adapter.swApp._target.GetMathUtility = lambda: wrong
    elif producer == "created-point":
        utility.CreatePoint = lambda _xyz: wrong
    elif producer == "transformed-point":
        point = _owner_fake("IMathPoint", MultiplyTransform=lambda _transform: wrong)
        utility.CreatePoint = lambda _xyz: point
    elif producer == "parent-transform":
        view.parent.transform = wrong
    elif producer == "detail-transform":
        view.transform = wrong
    else:
        assert producer == "parent-inverse"
        view.parent.transform.Inverse = lambda: wrong

    with pytest.raises(AssertionError, match=f"as {required}"):
        _drawing_detail_crop.read_circular_detail_crop(adapter, input_view, label="D")
    assert wrong_calls == []
    assert wrong._native_reads == (
        [("ISketchSegment", "GetType")] if producer == "profile-arc" else []
    )
    assert wrong._native_writes == []


def test_generic_crop_qi_keeps_segment_arc_point_and_math_surfaces_separate(monkeypatch):
    adapter, view, profile, transform, _refreshed = _crop_fixture(monkeypatch, "D")
    crop = _drawing_detail_crop.read_circular_detail_crop(adapter, view, label="D")
    assert crop.crop == pytest.approx(_R18_DETAIL["D"]["crop"], abs=1e-14)
    assert {"ISketchSegment", "ISketchArc"} == {
        interface for interface, _member in profile._native_reads
    }
    surfaces = (
        (_bind_owner(profile, "ISketchSegment"), "IsCircle"),
        (_bind_owner(profile, "ISketchSegment"), "GetRadius"),
        (_bind_owner(profile, "ISketchArc"), "GetType"),
        (_bind_owner(profile, "ISketchArc"), "GetSketch"),
        (_bind_owner(profile.GetCenterPoint2(), "ISketchPoint"), "ArrayData"),
        (_bind_owner(_CropMathPoint((0.0, 0.0, 0.0)), "IMathPoint"), "X"),
        (_bind_owner(transform, "IMathTransform"), "MultiplyTransform"),
        (_bind_owner(adapter.swApp.GetMathUtility(), "IMathUtility"), "ArrayData"),
        (_bind_owner(view, "IView"), "GetProfileItems"),
        (_bind_owner(view.circle, "IDetailCircle"), "GetOutline"),
        (_bind_owner(profile.GetSketch(), "ISketch"), "Inverse"),
    )
    for owner, borrowed_member in surfaces:
        with pytest.raises(AttributeError, match="does not own"):
            getattr(owner, borrowed_member)
    with pytest.raises(AttributeError, match="cannot write"):
        _bind_owner(view, "IView").Type = 3  # Native Type is get-only.
    with pytest.raises(AssertionError, match="cannot bind"):
        _bind_owner(SimpleNamespace(GetOutline=lambda: view.outline), "IView")
    assert _bind_owner(None, "IView") is None


def test_collector_reads_type_only_from_bound_view_and_keeps_crop_record(monkeypatch):
    adapter, view, *_rest = _crop_fixture(monkeypatch, "D")
    elements, _leaders, _region = _collect_crop(adapter)
    assert ("IView", "Type") in view._native_reads
    assert next(element for element in elements if element.label == "D").box == pytest.approx(
        _R18_DETAIL["D"]["crop"], abs=1e-14
    )
    assert ("IView", "GetOutline") in view._native_reads


def test_collector_wrong_view_owner_refuses_before_type_read(monkeypatch):
    adapter, view, *_rest = _crop_fixture(monkeypatch, "D")
    wrong = _owner_fake("IDetailCircle", Type=3)
    monkeypatch.setattr(_drawing_layout_collect, "iter_views", lambda _adapter: iter((wrong,)))
    monkeypatch.setattr(_drawing_layout_collect, "view_name", lambda _adapter, _view: "D")
    with pytest.raises(AssertionError, match="as IView"):
        _collect_crop(adapter)
    assert wrong._native_reads == []
    assert view.outline_reads == 0


@pytest.mark.parametrize("member", ("Type", "ScaleRatio", "ModelToViewTransform"))
def test_collector_rejects_method_shaped_view_properties(monkeypatch, member):
    adapter, view, *_rest = _crop_fixture(monkeypatch, "D")
    if member == "ModelToViewTransform":
        monkeypatch.setattr(_CropView, member, property(lambda self: lambda: self.transform))
    else:
        setattr(view, member, lambda: 3)
    with pytest.raises(RuntimeError, match="D:") as caught:
        _collect_crop(adapter)
    if member == "Type":
        assert str(caught.value) == "D: cannot read native IView.Type for layout"
    else:
        assert str(caught.value).startswith("D: circular detail crop readback refused:")
    assert isinstance(caught.value.__cause__, AssertionError)
    assert str(caught.value.__cause__) == f"IView.{member} has the wrong native shape"


def _linked_note_owner_fixture(monkeypatch):
    calls = []
    format_target = _owner_fake("ITextFormat", CharHeight=0.00635)
    text_format = _bind_owner(format_target, "ITextFormat")

    def get_format(index):
        calls.append(("get-format", index))
        return text_format

    def set_format(index, use_doc, value):
        assert _bind_owner(value, "ITextFormat").CharHeight == 0.0035
        calls.append(("set-format", index, use_doc, value))
        return True

    annotation = _owner_fake(
        "IAnnotation", GetTextFormat=get_format, SetTextFormat=set_format,
    )
    note = _owner_fake("INote", GetAnnotation=lambda: annotation)

    def insert_note(adapter, text, x, y):
        calls.append(("add-note", adapter, text, x, y))
        return note

    monkeypatch.setattr(_drawing_notes, "add_note", insert_note)
    monkeypatch.setattr(_drawing_notes, "_early_bound", _bind_owner)
    return note, annotation, format_target, text_format, calls


@pytest.mark.parametrize("height", (None, 0.0035))
def test_shared_linked_note_uses_note_annotation_and_format_owners(monkeypatch, height):
    note, annotation, format_target, text_format, calls = _linked_note_owner_fixture(monkeypatch)
    adapter = _FakeAdapter(None)
    result = _drawing_notes.add_property_linked_note(
        adapter, "Manufacturing Notes", 0.024, 0.182, char_height=height
    )
    assert calls[0] == ("add-note", adapter, '$PRPSHEET:"Manufacturing Notes"', 0.024, 0.182)
    if height is None:
        assert result is note
        assert len(calls) == 1
        assert note._native_reads == annotation._native_reads == format_target._native_writes == []
    else:
        assert result._target is note and result._interface == "INote"
        assert calls[1:] == [("get-format", 0), ("set-format", 0, False, text_format)]
        assert note._native_reads == [("INote", "GetAnnotation")]
        assert annotation._native_reads == [
            ("IAnnotation", "GetTextFormat"), ("IAnnotation", "SetTextFormat"),
        ]
        assert format_target._native_writes == [("ITextFormat", "CharHeight", 0.0035)]


@pytest.mark.parametrize(
    ("producer", "reason"),
    (("note", "as INote"), ("annotation", "as IAnnotation"), ("format", "INote cannot write CharHeight")),
)
def test_shared_linked_note_rejects_wrong_owner_before_format_access(
    monkeypatch, producer, reason
):
    note, annotation, _format_target, _text_format, calls = _linked_note_owner_fixture(monkeypatch)
    wrong_calls = []
    wrong = _owner_fake(
        "IAnnotation" if producer == "note" else "INote",
        GetAnnotation=lambda: wrong_calls.append("annotation"),
        GetTextFormat=lambda _index: wrong_calls.append("format"),
        CharHeight=0.00635,
    )
    if producer == "note":
        monkeypatch.setattr(_drawing_notes, "add_note", lambda *_args: wrong)
    elif producer == "annotation":
        note.GetAnnotation = lambda: wrong
    else:
        annotation.GetTextFormat = lambda _index: _bind_owner(wrong, "INote")

    with pytest.raises((AssertionError, AttributeError), match=reason):
        _drawing_notes.add_property_linked_note(
            _FakeAdapter(None), "Manufacturing Notes", 0.024, 0.182, char_height=0.0035
        )
    assert wrong_calls == []
    assert wrong._native_reads == wrong._native_writes == []
    assert wrong.CharHeight == 0.00635
    assert not any(call[0] == "set-format" for call in calls)


@pytest.mark.parametrize("result", (False, None, 1, "True"))
def test_shared_linked_note_requires_native_bool_format_setter(monkeypatch, result):
    _note, annotation, _format_target, _text_format, _calls = _linked_note_owner_fixture(monkeypatch)
    annotation.SetTextFormat = lambda *_args: result
    with pytest.raises(RuntimeError, match="failed to set linked drawing note"):
        _drawing_notes.add_property_linked_note(
            _FakeAdapter(None), "Manufacturing Notes", 0.024, 0.182, char_height=0.0035
        )


def _collect_crop(adapter):
    return _drawing_layout_collect.collect_layout_elements(
        adapter, layout=DrawingLayout.LANDSCAPE
    )


@pytest.mark.parametrize("label", ("D", "E"))
def test_generic_crop_r18_sketch_hop_and_synthetic_view_hops(monkeypatch, label):
    adapter, view, _profile, sketch_transform, refreshed = _crop_fixture(monkeypatch, label)
    data = _R18_DETAIL[label]
    crop = _drawing_detail_crop.read_circular_detail_crop(
        adapter, view, label=label
    )
    assert crop.label == label
    assert crop.parent._target is view.parent
    assert crop.parent_centre == pytest.approx(data["parent_centre"], abs=1e-14)
    assert crop.parent_radius == pytest.approx(data["raw_radius"] / 2.0, abs=1e-14)
    assert crop.parent_radius_y == pytest.approx(crop.parent_radius, abs=1e-14)
    assert crop.parent_ratio == (1.0, 2.0)
    assert crop.detail_ratio == data["ratio"]
    assert crop.crop == pytest.approx(data["crop"], abs=1e-14)
    assert crop.outline == data["outline"]
    assert view.parent in refreshed and view in refreshed
    assert view.circle.NoOutline is True
    assert sketch_transform.inverse_calls == 1
    assert view.parent.transform.inverse_calls == 1
    assert view.outline_reads == 1  # helper owns the single fresh native read
    assert view.outline_refresh_states == [True]
    with pytest.raises(AttributeError):
        crop.crop = data["outline"]


@pytest.mark.parametrize("label", ("D", "E"))
def test_collector_refreshes_before_reading_single_native_outline(monkeypatch, label):
    adapter, view, *_rest = _crop_fixture(monkeypatch, label)
    stale = view.GetOutline()
    assert stale != view.outline
    assert stale[2] < _R18_DETAIL[label]["crop"][0]
    view.outline_reads = 0
    view.outline_refresh_states.clear()
    elements, _leaders, _region = _collect_crop(adapter)
    assert next(element for element in elements if element.label == label).box == pytest.approx(
        _R18_DETAIL[label]["crop"], abs=1e-14
    )
    assert view.outline_reads == 1
    assert view.outline_refresh_states == [True]


def test_collector_r18_three_phantom_overlaps_become_zero(monkeypatch):
    adapter, d, *_rest = _crop_fixture(monkeypatch, "D")
    _e_adapter, e, *_rest = _crop_fixture(monkeypatch, "E")
    d.next_view = e
    for view in (d, e):
        view.annotations = [_crop_note(f"{view.name}-caption", _R18_DETAIL[view.name]["caption"])]
    elements, leaders, region = _collect_crop(adapter)
    old = [
        _el(element.label, *_R18_DETAIL[element.label]["outline"],
            kind=element.kind, scope=element.scope, owner=element.owner)
        if element.kind == "view" else element
        for element in elements
    ]
    overlaps, overflows, crossings = audit_layout(old, region, leaders=leaders)
    assert {frozenset((item.a.label, item.b.label)) for item in overlaps} == {
        frozenset(("D", "D-caption")), frozenset(("D", "title-block")),
        frozenset(("E", "E-caption")),
    }
    assert len(overlaps) == 3
    assert overflows == crossings == []
    assert audit_layout(elements, region, leaders=leaders) == ([], [], [])
    assert d.outline_reads == e.outline_reads == 1


@pytest.mark.parametrize("label", ("D", "E"))
@pytest.mark.parametrize("obstacle", ("caption", "title-block"))
def test_collector_actual_crop_encroachment_still_fails(monkeypatch, label, obstacle):
    data = _R18_DETAIL[label]
    radius = (data["crop"][2] - data["crop"][0]) / 2.0
    if obstacle == "caption":
        # Move only this SYNTHETIC detail transform: caption ink stays measured.
        centre = (data["centre"][0], data["caption"][3] + radius - 0.002)
    else:
        centre = (max(data["centre"][0], 0.216 + 0.002 - radius),
                  0.066 + radius - 0.002)
    adapter, view, *_rest = _crop_fixture(monkeypatch, label, centre=centre)
    # A moved native view still provides a legitimate containing outline.
    view.outline = (centre[0] - radius - 0.01, centre[1] - radius - 0.01,
                    centre[0] + radius + 0.01, centre[1] + radius + 0.01)
    view.annotations = [_crop_note(f"{label}-caption", data["caption"])]
    elements, leaders, region = _collect_crop(adapter)
    findings = audit_layout(elements, region, leaders=leaders)[0]
    finding = next(item for item in findings
                   if {item.a.label, item.b.label} == {label, f"{label}-caption" if obstacle == "caption" else obstacle})
    assert finding.depth_x > DEFAULT_OVERLAP_TOL_M
    assert finding.depth_y > DEFAULT_OVERLAP_TOL_M


@pytest.mark.parametrize(
    ("defect", "reason"),
    (
        ("missing-profile", "one persisted circle profile"),
        ("duplicate-profile", "one persisted circle profile"),
        ("noncircle", "not a complete circle"),
        ("nonarc", "not a sketch arc"),
        ("nonfinite", "invalid native circle"),
        ("zero-radius", "invalid native circle"),
        ("nonfinite-outline", "invalid native box"),
        ("inverted-outline", "invalid native box"),
        ("empty-outline", "invalid native box"),
        ("empty-crop", "invalid native box"),
        ("noncontained", "outside native outline"),
        ("type-error", "cannot read native IView.Type"),
        ("bool-type", "invalid native IView.Type"),
        ("outline-error", "cannot read current native outline after display geometry update"),
        ("crop-binding-error", "crop binding failed"),
    ),
)
def test_collector_detail_crop_failures_are_named_fatal(monkeypatch, defect, reason):
    adapter, view, profile, _transform, _refreshed = _crop_fixture(monkeypatch, "D")
    if defect == "missing-profile":
        view.circle.GetProfileItems = lambda: ()
    elif defect == "duplicate-profile":
        view.circle.GetProfileItems = lambda: (profile, profile)
    elif defect == "noncircle":
        profile.IsCircle = lambda: 0
    elif defect == "nonarc":
        profile.GetType = lambda: 0
    elif defect == "nonfinite":
        profile.GetRadius = lambda: float("nan")
    elif defect == "zero-radius":
        profile.GetRadius = lambda: 0.0
    elif defect == "nonfinite-outline":
        view.outline = (0.0, 0.0, float("nan"), 1.0)
    elif defect == "empty-crop":
        # Finite, positive scales can still collapse a crop below one ULP.
        view.ScaleRatio = (1e-300, 1.0)
    elif defect == "inverted-outline":
        view.outline = (0.3, 0.1, 0.2, 0.2)
    elif defect == "empty-outline":
        view.outline = ()
    elif defect == "noncontained":
        view.outline = (0.16, 0.08, 0.20, 0.12)
    elif defect == "type-error":
        class BrokenType(_CropView):
            @property
            def Type(self):
                raise OSError("Type binding failed")
        view.__class__ = BrokenType
    elif defect == "bool-type":
        view.Type = True
    else:
        view.defect = defect
    # A swallowed read would silently omit D (or use its padded outline).
    with pytest.raises(RuntimeError, match="D") as caught:
        _collect_crop(adapter)
    assert reason in str(caught.value)


@pytest.mark.parametrize("side", range(4))
def test_collector_crop_exact_containment_edges_and_one_ulp(monkeypatch, side):
    adapter, view, *_rest = _crop_fixture(monkeypatch, "D")
    crop = _drawing_detail_crop.read_circular_detail_crop(
        adapter, view, label="D"
    ).crop
    view.outline = crop
    elements, _leaders, _region = _collect_crop(adapter)
    assert next(element for element in elements if element.label == "D").box == crop
    outside = list(crop)
    outside[side] = _math.nextafter(crop[side], _math.inf if side < 2 else -_math.inf)
    view.outline = tuple(outside)
    with pytest.raises(RuntimeError, match="D"):
        _collect_crop(adapter)


def test_collector_crop_preserves_ordinary_elements_leaders_and_tag_boundary(monkeypatch):
    adapter, detail, *_rest = _crop_fixture(monkeypatch, "D")
    # Centre is outside the crop, ON the original native outline boundary.
    x = detail.outline[0]
    y = 0.095
    detail.annotations = [
        _crop_note("boundary-tag", (x - 0.002, y - 0.002, x + 0.002, y + 0.002)),
        _crop_note("foreign-leader", (0.02, 0.12, 0.025, 0.124),
                   leader=(0.02, 0.12, 0.0, 0.22, 0.12, 0.0)),
    ]
    ordinary = _CropView("ordinary", (0.02, 0.15, 0.06, 0.19),
                         None, None, None, (1.0, 1.0))
    ordinary.Type = 6
    ordinary.annotations = [_crop_note("free-note", (0.08, 0.15, 0.10, 0.17))]
    ordinary.annotations.append(_owner_fake(
        "IAnnotation", GetName=lambda: "surface-finish", GetType=lambda: 7,
        GetPosition=lambda: (0.04, 0.20, 0.0), GetLeaderCount=lambda: 0,
    ))
    ordinary.tables = [_owner_fake(
        "ITableAnnotation",
        GetAnnotation=lambda: _owner_fake(
            "IAnnotation", GetName=lambda: "table", GetPosition=lambda: (0.08, 0.20, 0.0),
        ),
        RowCount=1, ColumnCount=1, GetSplitInformation=lambda *_args: (),
        GetColumnWidth=lambda _index: 0.02, GetRowHeight=lambda _index: 0.01,
    )]
    detail.next_view = ordinary
    elements, leaders, region = _collect_crop(adapter)
    detail.Type = 6  # old collector occupancy, same annotation policy
    old_elements, old_leaders, old_region = _collect_crop(adapter)
    assert [element for element in elements if element.label != "D"] == [
        element for element in old_elements if element.label != "D"
    ]
    assert leaders == old_leaders and region == old_region
    assert {"view", "note", "gdt", "table", "titleblock"} == {
        element.kind for element in elements
    }
    assert next(element for element in elements if element.label == "ordinary").box == ordinary.outline
    assert next(element for element in elements if element.label == "boundary-tag").scope is CollisionScope.NON_VIEW
    new_view = next(element for element in elements if element.label == "D")
    old_view = next(element for element in old_elements if element.label == "D")
    assert (new_view.label, new_view.kind, new_view.scope, new_view.owner) == (
        old_view.label, old_view.kind, old_view.scope, old_view.owner,
    )


def test_collector_ordinary_outline_failure_keeps_old_behavior(monkeypatch):
    adapter, view, *_rest = _crop_fixture(monkeypatch, "D")
    view.Type = 6
    view.defect = "outline-error"
    view.annotations = [_crop_note("ordinary-note", (0.02, 0.15, 0.04, 0.16))]
    elements, leaders, _region = _collect_crop(adapter)
    assert [(element.label, element.kind) for element in elements] == [
        ("ordinary-note", "note"), ("title-block", "titleblock"),
    ]
    assert leaders == []


def _crop_finding_keys(elements, leaders, region):
    overlaps, overflows, crossings = audit_layout(elements, region, leaders=leaders)
    keys = {("overlap", *sorted((item.a.label, item.b.label))) for item in overlaps}
    keys.update(("overflow", item.element.label, side)
                for item in overflows for side, _depth in item.sides)
    for item in crossings:
        if isinstance(item, Crossing):
            keys.add(("foreign-leader", item.segment.label, item.view.label))
        else:
            keys.add(("leader-leader", *sorted((item.a.label, item.b.label))))
    return keys


@pytest.mark.parametrize("scope", tuple(CollisionScope))
@pytest.mark.parametrize("padding", (0.0, 0.002, 0.02))
def test_collector_contained_crop_finding_keys_are_subset(monkeypatch, scope, padding):
    adapter, detail, *_rest = _crop_fixture(monkeypatch, "D")
    crop = _R18_DETAIL["D"]["crop"]
    detail.outline = (crop[0] - padding - 1e-12, crop[1] - padding - 1e-12,
                      crop[2] + padding + 1e-12, crop[3] + padding + 1e-12)
    # Classification probes include crop-interior and outline-only tags.
    detail.annotations = [
        _crop_note("tag", (0.175, 0.09, 0.179, 0.094)),
        _crop_note("large-note", (0.145, 0.07, 0.205, 0.10)),
        _crop_note("leader-a", (0.03, 0.12, 0.035, 0.124),
                   leader=(0.02, 0.10, 0.0, 0.25, 0.10, 0.0)),
        _crop_note("leader-b", (0.08, 0.20, 0.085, 0.204),
                   leader=(0.12, 0.02, 0.0, 0.12, 0.22, 0.0)),
    ]
    foreign = _CropView("foreign", (0.10, 0.085, 0.13, 0.115),
                        None, None, None, (1.0, 1.0))
    foreign.Type = 6
    foreign.annotations = [_crop_note("foreign-note", (0.17, 0.09, 0.19, 0.11))]
    detail.next_view = foreign
    monkeypatch.setattr(
        _drawing_layout_collect, "_view_scope",
        lambda _adapter, view: scope if view._target is detail else CollisionScope.ALL,
    )
    elements, leaders, _region = _collect_crop(adapter)
    detail.Type = 6
    old_elements, old_leaders, _old_region = _collect_crop(adapter)
    assert leaders == old_leaders
    assert [element for element in elements if element.kind != "view"] == [
        element for element in old_elements if element.kind != "view"
    ]
    # A tight SYNTHETIC region ensures this property exercises overflow as well
    # as overlap and both leader policies; no random seed or hidden randomness.
    region = DrawableRegion(0.16, 0.08, 0.20, 0.12)
    before = _crop_finding_keys(old_elements, old_leaders, region)
    after = _crop_finding_keys(elements, leaders, region)
    assert after <= before
    assert any(key[0] == "overflow" for key in before)
    assert any(key[0] == "leader-leader" for key in before)
    if scope is not CollisionScope.NONE:
        assert any(key[0] == "overlap" for key in before)
    assert any(key[0] == "foreign-leader" for key in before)


def test_live_collector_never_flags_transient_dispatches(monkeypatch):
    """The audit must not pay whole-interface flagging for fresh COM wrappers."""

    def _unexpected_flag(*_args, **_kwargs):
        raise AssertionError("layout collection must not call flagged()")

    monkeypatch.setattr(solidworks_mcp.adapters.sw_type_info, "flagged", _unexpected_flag)

    note = SimpleNamespace(GetExtent=[0.01, 0.09, 0.0, 0.04, 0.10, 0.0])
    note_annotation = SimpleNamespace(
        GetLeaderCount=0,
        GetSpecificAnnotation=note,
        GetType=6,
        GetName="general-note",
    )
    dim_annotation = SimpleNamespace(
        GetPosition=[0.12, 0.22, 0.0],
        GetType=lambda: 4,
        GetName=lambda: "dimension",
    )
    table_annotation = SimpleNamespace(GetPosition=lambda: [0.18, 0.12, 0.0])
    table = SimpleNamespace(
        GetAnnotation=lambda: table_annotation,
        RowCount=2,
        ColumnCount=2,
        GetColumnWidth=lambda _index: 0.02,
        GetRowHeight=lambda _index: 0.01,
    )
    table_annotation.GetName = "hole-table"

    view = SimpleNamespace(
        GetName2="Front",
        Type=6,  # swDrawingViewTypes_e.swDrawingStandardView
        GetOrientationName=lambda: "*Front",
        GetOutline=[0.05, 0.15, 0.15, 0.25],
        GetAnnotations=lambda: [note_annotation, dim_annotation],
        GetTableAnnotations=[table],
        GetNextView=None,
    )
    sheet_view = SimpleNamespace(GetNextView=lambda: view, GetTableAnnotations=[])
    zone = {
        0: ZONE_MARGINS["top"],
        1: ZONE_MARGINS["bottom"],
        2: ZONE_MARGINS["right"],
        3: ZONE_MARGINS["left"],
    }
    sheet = SimpleNamespace(
        GetProperties=lambda: [0.0, 0.0, 1.0, 1.0, 0.0, SHEET_W, SHEET_H],
        GetZoneMargin=lambda code: zone[code],
    )
    model = SimpleNamespace(GetCurrentSheet=sheet, GetFirstView=lambda: sheet_view)

    elements, leaders, region = _drawing_layout_collect.collect_layout_elements(
        _FakeAdapter(model), layout=DrawingLayout.LANDSCAPE
    )

    # The drawable region is QUERIED from the sheet's zone margins, never a
    # constant: a template whose zone band moves moves the keep-out with it.
    assert region == ZONE_REGION
    assert leaders == []
    assert [(element.label, element.kind) for element in elements] == [
        ("Front", "view"),
        ("general-note", "note"),
        ("hole-table", "table"),
        ("title-block", "titleblock"),
    ]


def test_live_collector_includes_sheet_notes_but_excludes_template_notes():
    def annotation(name, owner_type, extent):
        note = SimpleNamespace(GetExtent=extent, IsBomBalloon=lambda: False)
        return SimpleNamespace(
            GetLeaderCount=0,
            GetSpecificAnnotation=note,
            GetType=_drawing_layout_collect._ANNOT_NOTE,
            GetName=name,
            OwnerType=owner_type,
        )

    drawing_note = annotation("setup-notes", 1, [0.02, 0.08, 0.0, 0.12, 0.20, 0.0])
    template_note = annotation("zone-label", 2, [0.00, 0.00, 0.0, 0.01, 0.01, 0.0])
    sheet_gdt = SimpleNamespace(
        GetLeaderCount=0,
        GetSpecificAnnotation=SimpleNamespace(GetPosition=[-0.02, 0.0, 0.0]),
        GetType=_drawing_layout_collect._ANNOT_GTOL,
        GetName="template-gdt",
        GetPosition=[-0.02, 0.0, 0.0],
        OwnerType=1,
    )
    sheet_view = SimpleNamespace(
        GetNextView=None,
        GetAnnotations=lambda: [drawing_note, template_note, sheet_gdt],
        GetTableAnnotations=[],
    )
    zone = {
        0: ZONE_MARGINS["top"],
        1: ZONE_MARGINS["bottom"],
        2: ZONE_MARGINS["right"],
        3: ZONE_MARGINS["left"],
    }
    sheet = SimpleNamespace(
        GetProperties=lambda: [0.0, 0.0, 1.0, 1.0, 0.0, SHEET_W, SHEET_H],
        GetZoneMargin=lambda code: zone[code],
    )
    model = SimpleNamespace(GetCurrentSheet=sheet, GetFirstView=lambda: sheet_view)

    elements, leaders, _region = _drawing_layout_collect.collect_layout_elements(
        _FakeAdapter(model), layout=DrawingLayout.LANDSCAPE
    )

    assert leaders == []
    assert [(element.label, element.kind) for element in elements] == [
        ("setup-notes", "note"),
        ("title-block", "titleblock"),
    ]


def test_portrait_collector_uses_mapped_keepout_and_physical_size():
    template = DRAWING_TEMPLATES[DrawingLayout.PORTRAIT]
    zone = {
        0: ZONE_MARGINS["top"],
        1: ZONE_MARGINS["bottom"],
        2: ZONE_MARGINS["right"],
        3: ZONE_MARGINS["left"],
    }
    sheet = SimpleNamespace(
        GetProperties=lambda: [
            0.0,
            0.0,
            1.0,
            1.0,
            0.0,
            template.width_m,
            template.height_m,
        ],
        GetZoneMargin=lambda code: zone[code],
    )
    sheet_view = SimpleNamespace(
        GetNextView=None,
        GetAnnotations=[],
        GetTableAnnotations=[],
    )
    model = SimpleNamespace(GetCurrentSheet=sheet, GetFirstView=lambda: sheet_view)

    elements, leaders, region = _drawing_layout_collect.collect_layout_elements(
        _FakeAdapter(model), layout=DrawingLayout.PORTRAIT
    )

    assert leaders == []
    assert region == DrawableRegion.from_margins(
        template.width_m, template.height_m, **ZONE_MARGINS
    )
    title_block = next(element for element in elements if element.kind == "titleblock")
    assert (
        title_block.xmin,
        title_block.ymin,
        title_block.xmax,
        title_block.ymax,
    ) == (
        template.title_block_left_m,
        0.0,
        template.width_m,
        template.title_block_top_m,
    )


def test_split_table_box_uses_only_the_rendered_row_range():
    annotation = SimpleNamespace(GetPosition=lambda: [0.020, 0.265, 0.0])
    table = SimpleNamespace(
        GetAnnotation=lambda: annotation,
        GetSplitInformation=lambda *_args: (1, 0, 3, 0, 11),
        RowCount=33,
        ColumnCount=4,
        GetColumnWidth=lambda _index: 0.025,
        GetRowHeight=lambda _index: 0.008,
    )

    element = _drawing_layout_collect._table_element(
        _FakeAdapter(SimpleNamespace()), table, "split-bom"
    )

    assert element is not None
    assert (element.label, element.kind) == ("split-bom", "table")
    assert (element.xmin, element.ymin, element.xmax, element.ymax) == pytest.approx(
        (0.020, 0.169, 0.120, 0.265)
    )


def test_later_split_table_piece_includes_the_repeated_header_height():
    annotation = SimpleNamespace(GetPosition=lambda: [0.145, 0.265, 0.0])
    table = SimpleNamespace(
        GetAnnotation=lambda: annotation,
        GetSplitInformation=lambda *_args: (1, 1, 3, 12, 23),
        RowCount=33,
        ColumnCount=4,
        GetColumnWidth=lambda _index: 0.025,
        GetRowHeight=lambda index: 0.010 if index == 0 else 0.008,
    )

    element = _drawing_layout_collect._table_element(
        _FakeAdapter(SimpleNamespace()), table, "split-bom-2"
    )

    assert element is not None
    assert (element.label, element.kind) == ("split-bom-2", "table")
    assert (element.xmin, element.ymin, element.xmax, element.ymax) == pytest.approx(
        (0.145, 0.159, 0.245, 0.265)
    )


def test_disjoint_layout_is_clean():
    elements = [
        _el("V1", 0.05, 0.18, 0.11, 0.23),
        _el("V2", 0.18, 0.18, 0.20, 0.23),
        _el("N1", 0.014, 0.089, 0.153, 0.112, kind="note"),
    ]
    overlaps, overflows, crossings = audit_layout(elements, WHOLE_SHEET)
    assert overlaps == []
    assert overflows == []


def test_two_views_that_overlap_are_flagged():
    a = _el("V1", 0.05, 0.05, 0.15, 0.15)
    b = _el("V2", 0.10, 0.10, 0.20, 0.20)  # 50 mm x 50 mm mutual penetration
    overlaps = find_overlaps([a, b])
    assert len(overlaps) == 1
    assert {overlaps[0].a.label, overlaps[0].b.label} == {"V1", "V2"}
    assert overlaps[0].depth_x > 0 and overlaps[0].depth_y > 0


def test_note_dropped_on_a_view_is_flagged():
    view = _el("V1", 0.05, 0.05, 0.15, 0.15)
    note = _el("N1", 0.09, 0.09, 0.13, 0.11, kind="note")
    overlaps = find_overlaps([view, note])
    assert len(overlaps) == 1


def test_adjacent_views_within_tolerance_are_not_flagged():
    # Two boxes sharing an edge but only overlapping by less than the tolerance
    # on one axis -- the GetOutline padding case -- must NOT be reported.
    tol = DEFAULT_OVERLAP_TOL_M
    a = _el("V1", 0.05, 0.05, 0.15, 0.15)
    b = _el("V2", 0.15 - tol / 2, 0.05, 0.25, 0.15)  # x-penetration = tol/2 < tol
    assert find_overlaps([a, b]) == []


def test_penetration_must_clear_tolerance_on_both_axes():
    # Deep on Y, shallow on X -> the min penetration is below tolerance -> clean.
    tol = DEFAULT_OVERLAP_TOL_M
    a = _el("A", 0.05, 0.05, 0.15, 0.20)
    b = _el("B", 0.15 - tol / 2, 0.05, 0.25, 0.20)
    assert find_overlaps([a, b]) == []


def test_pictorial_view_scope_none_never_collides():
    # An isometric view's box swallows a nearby label, but a NONE-scope element
    # is excluded from overlap detection so it does not false-positive.
    iso = _el("ISO", 0.17, 0.14, 0.40, 0.28, scope=CollisionScope.NONE)
    label = _el("LBL", 0.14, 0.14, 0.22, 0.145, kind="note")
    assert find_overlaps([iso, label]) == []
    # ... but the same box at ALL scope WOULD be flagged, proving the scope is
    # what suppresses it (not a tolerance fluke).
    solid = _el("ISO", 0.17, 0.14, 0.40, 0.28, scope=CollisionScope.ALL)
    assert len(find_overlaps([solid, label])) == 1


def test_scope_exempt_element_still_checked_for_overflow():
    # Codex #269: collision scope suppresses collisions only -- a pictorial view
    # or leadered note mis-placed OFF the sheet must still be flagged.
    iso_off = _el("ISO", 0.17, 0.14, 0.40, SHEET_H + 0.02, scope=CollisionScope.NONE)
    note_off = _el(
        "N", -0.03, 0.10, 0.05, 0.12, kind="note", scope=CollisionScope.NON_VIEW
    )
    overflows = find_overflows([iso_off, note_off], WHOLE_SHEET)
    flagged = {o.element.label: {side for side, _ in o.sides} for o in overflows}
    assert flagged == {"ISO": {"top"}, "N": {"left"}}


def test_overflow_off_each_sheet_edge():
    allow = DEFAULT_BOUNDARY_ALLOWANCE_M
    left = _el("L", -allow - 0.002, 0.10, 0.05, 0.15)
    right = _el("R", 0.40, 0.10, SHEET_W + allow + 0.002, 0.15)
    top = _el("T", 0.10, 0.20, 0.15, SHEET_H + allow + 0.002)
    bottom = _el("Bt", 0.10, -allow - 0.002, 0.15, 0.10)
    inside = _el("I", 0.10, 0.10, 0.15, 0.15)
    overflows = find_overflows([left, right, top, bottom, inside], WHOLE_SHEET)
    flagged = {o.element.label: {side for side, _ in o.sides} for o in overflows}
    assert flagged == {
        "L": {"left"},
        "R": {"right"},
        "T": {"top"},
        "Bt": {"bottom"},
    }


def test_view_padding_within_allowance_is_not_overflow():
    # A view whose padded outline pokes ~1.5 mm past the top edge (measured on
    # the platen-guide iso view) must NOT be flagged -- the outward allowance
    # absorbs GetOutline padding on a (kind == "view") pictorial box.
    view = _el("V", 0.05, 0.10, 0.15, SHEET_H + 0.0015, scope=CollisionScope.NONE)
    assert find_overflows([view], WHOLE_SHEET) == []


def test_exact_note_barely_off_sheet_is_flagged():
    # Codex #269 thread 7: the GetOutline padding allowance applies only to view
    # boxes; an exact note/table poking even 1 mm past the edge is a real clip in
    # the exported PDF/PNG and must be flagged.
    note = _el("N", 0.05, SHEET_H - 0.02, 0.15, SHEET_H + 0.001, kind="note")
    (overflow,) = find_overflows([note], WHOLE_SHEET)
    assert {side for side, _ in overflow.sides} == {"top"}
    # ... the same 1 mm overhang on a padded VIEW box is absorbed by the allowance.
    view = _el("V", 0.05, SHEET_H - 0.02, 0.15, SHEET_H + 0.001, kind="view")
    assert find_overflows([view], WHOLE_SHEET) == []


def test_leadered_callout_collides_with_notes_not_owner_view():
    # Codex #269 thread 6: a NON_VIEW leadered callout's overlap with the view
    # geometry it OWNS is intended and suppressed, but a collision with a free
    # note / table must still be reported.
    callout = _el(
        "C",
        0.10,
        0.18,
        0.13,
        0.20,
        kind="note",
        scope=CollisionScope.NON_VIEW,
        owner="V",
    )
    view = _el("V", 0.05, 0.15, 0.20, 0.23)
    assert find_overlaps([view, callout]) == []  # over its OWNER view: allowed
    notes_block = _el("N", 0.09, 0.17, 0.14, 0.21, kind="note")  # ALL scope
    assert len(find_overlaps([callout, notes_block])) == 1  # over a free note: flagged


def test_nonview_tag_collides_with_a_different_view():
    # Codex #269 thread 3: the view exemption is owner-scoped -- a tag owned by
    # V1 that strays onto a DIFFERENT view V2 is real drawing content overlapping
    # and must be flagged; only the overlap with its own V1 is suppressed.
    tag = _el(
        "tag",
        0.16,
        0.18,
        0.175,
        0.19,
        kind="note",
        scope=CollisionScope.NON_VIEW,
        owner="V1",
    )
    v1 = _el("V1", 0.05, 0.15, 0.18, 0.23)  # owner -- exempt
    v2 = _el("V2", 0.15, 0.15, 0.30, 0.23)  # different view -- audited
    assert find_overlaps([v1, tag]) == []
    assert len(find_overlaps([v2, tag])) == 1


def test_titleblock_is_a_hard_keepout_for_exempt_elements():
    # Codex #269 threads 1/2: NONE-scope elements (a pictorial view, a GD&T
    # symbol, a dimension) bypass every ordinary collision -- but the title block
    # is a hard keep-out that catches even them if they cover it.
    title = _el("title-block", 0.278, 0.0, SHEET_W, 0.080, kind="titleblock")
    iso = _el("iso", 0.30, 0.02, 0.40, 0.14, scope=CollisionScope.NONE)  # pictorial
    gdt = _el("G", 0.30, 0.02, 0.316, 0.036, kind="gdt", scope=CollisionScope.NONE)
    dim = _el("D", 0.30, 0.03, 0.308, 0.038, kind="dim", scope=CollisionScope.NONE)
    for cover in (iso, gdt, dim):
        assert len(find_overlaps([title, cover])) == 1


def test_two_keepout_boxes_never_collide():
    # Two keep-out boxes must never report a self-collision (today's template
    # reserves ONE box, but the invariant guards any future second keep-out).
    title = _el("title-block", 0.264, 0.0, SHEET_W, 0.064, kind="titleblock")
    other = _el("keepout-2", 0.242, 0.019, 0.281, 0.035, kind="titleblock")
    assert find_overlaps([title, other]) == []


def test_dimension_is_overflow_only():
    # Codex #269 thread 1: display dimensions / hole callouts sit on the geometry
    # they measure, so they are NONE-scope -- not overlap-checked against a view,
    # but an off-sheet callout is caught by the overflow audit.
    view = _el("V", 0.05, 0.15, 0.20, 0.23)
    dim_on_view = _el(
        "D", 0.10, 0.18, 0.108, 0.188, kind="dim", scope=CollisionScope.NONE
    )
    assert find_overlaps([view, dim_on_view]) == []
    dim_off = _el(
        "D2",
        SHEET_W - 0.002,
        0.15,
        SHEET_W + 0.006,
        0.16,
        kind="dim",
        scope=CollisionScope.NONE,
    )
    overflows = find_overflows([dim_off], WHOLE_SHEET)
    assert len(overflows) == 1 and "right" in {s for s, _ in overflows[0].sides}


def test_exact_boxes_get_near_zero_overlap_slack():
    # Codex #269: the 1.5 mm padding tolerance is for fuzzy GetOutline view
    # boxes; two EXACT boxes overlapping by ~1 mm is a real collision. A note
    # nudged 1 mm into a table (both exact) is flagged...
    note = _el("N", 0.05, 0.10, 0.15, 0.15, kind="note")
    table = _el("T", 0.149, 0.10, 0.25, 0.15, kind="table")  # 1 mm x-penetration
    assert len(find_overlaps([note, table])) == 1
    # ... and 1 mm into the title block too ...
    title = _el("title-block", 0.278, 0.0, SHEET_W, 0.080, kind="titleblock")
    stray = _el("N2", 0.20, 0.03, 0.279, 0.06, kind="note")  # 1 mm into the block
    assert len(find_overlaps([title, stray])) == 1
    # ... but two padded VIEW outlines overlapping by <1.5 mm stay clean (the
    # GetOutline whitespace case the tolerance exists for).
    v1 = _el("V1", 0.05, 0.05, 0.15, 0.15)
    v2 = _el("V2", 0.1490, 0.05, 0.25, 0.15)  # 1 mm x-penetration, both views
    assert find_overlaps([v1, v2]) == []


def test_content_overlapping_title_block_is_flagged():
    # A reserved title-block box (bottom-right) plus a note that strays into it:
    # the collision must be reported so content never lands on the title block.
    title = _el("title-block", 0.2785, 0.0, SHEET_W, 0.078, kind="titleblock")
    stray = _el("N", 0.30, 0.03, 0.36, 0.06, kind="note")
    clear = _el("N2", 0.05, 0.03, 0.20, 0.06, kind="note")
    assert len(find_overlaps([title, stray])) == 1
    assert find_overlaps([title, clear]) == []


def test_gdt_symbol_is_overflow_only():
    # GD&T symbols carry only a coarse NOMINAL box (no real bbox API), so they
    # are scoped NONE: never an overlap source (not vs a view, and not vs a note
    # -- two nominal boxes would false-collide), but an off-sheet symbol is still
    # caught by the overflow audit (Codex #269 thread 5).
    gdt = _el("G", 0.10, 0.18, 0.116, 0.196, kind="gdt", scope=CollisionScope.NONE)
    view = _el("V", 0.05, 0.15, 0.20, 0.23)  # gdt sits over its geometry
    assert find_overlaps([view, gdt]) == []
    note = _el("N", 0.10, 0.185, 0.14, 0.205, kind="note")  # gdt also overlaps a note
    assert find_overlaps([gdt, note]) == []  # nominal box is not overlap-checked
    gdt_off = _el("G2", 0.42, 0.15, 0.44, 0.17, kind="gdt", scope=CollisionScope.NONE)
    overflows = find_overflows([gdt_off], WHOLE_SHEET)
    assert len(overflows) == 1 and "right" in {s for s, _ in overflows[0].sides}


def test_large_note_on_its_own_view_is_still_flagged():
    # Codex #269: the tag exemption is size-gated, so a general-notes block
    # (large) centered inside its owning view is NOT exempt and the collision is
    # reported -- only a small tag centered inside its view is suppressed.
    view = _el("V1", 0.05, 0.05, 0.20, 0.20)
    big_note = _el("N", 0.08, 0.08, 0.18, 0.15, kind="note")  # 100 x 70 mm
    assert len(find_overlaps([view, big_note])) == 1


def test_lever_bushing_real_boxes_are_clean():
    # Measured element boxes from the shipped lever-bushing drawing (meters):
    # 3 views (V3 is the isometric -> NONE scope) + the 2 general-notes blocks.
    elements = [
        _el("V1", 0.05041, 0.17541, 0.10959, 0.23459),
        _el("V2", 0.17553, 0.17541, 0.20293, 0.23459),
        _el("V3", 0.28670, 0.16671, 0.34330, 0.24329, scope=CollisionScope.NONE),
        _el("N18", 0.01390, 0.08939, 0.15347, 0.11211, kind="note"),
        _el("N19", 0.16970, 0.06440, 0.32193, 0.10529, kind="note"),
    ]
    overlaps, overflows, crossings = audit_layout(elements, WHOLE_SHEET)
    assert overlaps == []
    assert overflows == []


def test_platen_guide_real_boxes_are_clean():
    # Measured off the shipped platen-guide drawing: 2 ortho views, the iso view
    # (NONE scope), the general-notes block, the "PLATEN-MATING FACE" label
    # (which bbox-overlaps the iso view), and the 10x4 hole table on the sheet.
    # The iso view's outline reaches ymax=280.9 mm on a 279.4 mm sheet -- within
    # the 3 mm overflow allowance for a padded view box, so it does not
    # false-positive despite now being overflow-checked.
    elements = [
        _el("V1", 0.03441, 0.10191, 0.34559, 0.11809),
        _el("V2", 0.35941, 0.10191, 0.38059, 0.11809),
        _el("V3", 0.16981, 0.13910, 0.40019, 0.28090, scope=CollisionScope.NONE),
        _el("N46", 0.01390, 0.02999, 0.17262, 0.07511, kind="note"),
        _el("N47", 0.14373, 0.14067, 0.22163, 0.14522, kind="note"),
        _el("T45", 0.01400, 0.16874, 0.15876, 0.25800, kind="table"),
    ]
    overlaps, overflows, crossings = audit_layout(elements, WHOLE_SHEET)
    assert overlaps == []
    assert overflows == []


# --- sheet zone border -------------------------------------------------------
#
# The border/zone band carries the frame and the A/B + 1..4 zone labels. Content
# may sit anywhere on the paper INSIDE that band and nowhere on it.


def test_zone_region_is_derived_from_the_sheet_margins():
    region = DrawableRegion.from_margins(
        SHEET_W, SHEET_H, left=0.02, right=0.01, bottom=0.015, top=0.005
    )
    assert region.xmin == 0.02
    assert region.ymin == 0.015
    assert region.xmax == SHEET_W - 0.01
    assert region.ymax == SHEET_H - 0.005


def test_zone_margins_that_swallow_the_sheet_raise():
    # A nonsense template must fail loud rather than silently audit nothing.
    try:
        DrawableRegion.from_margins(
            SHEET_W, SHEET_H, left=0.3, right=0.3, bottom=0.0, top=0.0
        )
    except ValueError as exc:
        assert "no drawable region" in str(exc)
    else:
        raise AssertionError("expected a ValueError for inverted zone margins")


def test_note_inside_the_paper_but_on_the_zone_band_is_flagged():
    # The shipped crank-arm notes block started LEFT of the frame line: on the
    # paper, on the zone band. The whole-sheet bound cannot see it; the zone
    # region must.
    note = _el("notes", 0.008, 0.05, 0.20, 0.09, kind="note")
    assert find_overflows([note], WHOLE_SHEET) == []
    (overflow,) = find_overflows([note], ZONE_REGION)
    assert overflow.sides[0][0] == "left"
    assert overflow.describe().startswith("note 'notes' crosses the sheet zone border")


def test_content_inside_the_zone_frame_is_clean():
    note = _el("notes", 0.02, 0.05, 0.20, 0.09, kind="note")
    assert find_overflows([note], ZONE_REGION) == []


def test_view_outline_padding_still_gets_slack_at_the_zone_border():
    # GetOutline pads whitespace, so a legitimately-placed view may poke a
    # millimetre past the frame; an exact-extent note at the same place may not.
    over = ZONE_REGION.xmin - 0.001
    view = _el("V", over, 0.05, 0.20, 0.09, kind="view")
    assert find_overflows([view], ZONE_REGION) == []
    note = _el("N", over, 0.05, 0.20, 0.09, kind="note")
    assert len(find_overflows([note], ZONE_REGION)) == 1


# --- leader crossings --------------------------------------------------------


def _views():
    return [
        _el("Front", 0.10, 0.10, 0.25, 0.18, kind="view"),
        _el("Top", 0.10, 0.20, 0.25, 0.26, kind="view"),
    ]


def test_leader_across_a_foreign_view_is_flagged():
    # The real crank-arm defect: the Ra symbol sat above the top view and its
    # straight leader ran down to the front view's bore, straight through Top.
    leader = LeaderSegment("Ra 1.6", "gdt", 0.14, 0.28, 0.16, 0.14, owner="Front")
    (crossing,) = find_leader_crossings([leader], _views())
    assert crossing.view.label == "Top"
    assert "runs its leader across view 'Top'" in crossing.describe()


def test_leader_landing_on_its_own_view_is_clean():
    leader = LeaderSegment("dia", "dim", 0.30, 0.14, 0.20, 0.14, owner="Front")
    assert find_leader_crossings([leader], _views()) == []


def test_leader_routed_clear_of_other_views_is_clean():
    # Same annotation, anchored so the leader approaches Front from the side it
    # sits on instead of driving through Top: the fix the gate should accept.
    leader = LeaderSegment("Ra 1.6", "gdt", 0.30, 0.08, 0.24, 0.13, owner="Front")
    assert find_leader_crossings([leader], _views()) == []


def _display_data(lines=(), triangles=(), texts=()):
    """IDisplayData as ``IAnnotation::GetDisplayData`` hands it back, sheet
    space: lines as ``GetLineAtIndex2`` ([color, lineType, style, weight,
    start[3], end[3]]), triangles as [v1[3], v2[3], v3[3], isFilled, lineType],
    texts as (text, (x, y), height[, width]) lower-left runs; a run with no
    width refuses ``GetTextInBoxWidthAtIndex``."""

    def width(i):
        if len(texts[i]) < 4:
            raise AttributeError("GetTextInBoxWidthAtIndex")
        return texts[i][3]

    return SimpleNamespace(
        GetLineCount=lambda: len(lines),
        GetLineAtIndex2=lambda i: [0.0, 0.0, 0.0, 0.0, *lines[i][0], 0.0, *lines[i][1], 0.0],
        GetArcCount=lambda: 0,
        GetArrowHeadCount=lambda: 0,
        GetPolyLineCount=lambda: 0,
        GetPolygonCount=lambda: 0,
        GetTriangleCount=lambda: len(triangles),
        GetTriangleAtIndex=lambda i: [c for v in triangles[i] for c in (*v, 0.0)] + [1.0, 0.0],
        GetEllipseCount=lambda: 0,
        GetTextCount=lambda: len(texts),
        GetTextAtIndex=lambda i: texts[i][0],
        GetTextPositionAtIndex=lambda i: [*texts[i][1], 0.0],
        GetTextHeightAtIndex=lambda i: texts[i][2],
        GetTextRefPositionAtIndex=lambda i: 1,
        GetTextAngleAtIndex=lambda i: 0.0,
        GetTextFontAtIndex=lambda i: "Century Gothic",
        GetTextLineSpacingAtIndex=lambda i: 0.0,
        GetTextInBoxWidthAtIndex=width,
    )


def _datum_tag(x, y, lines, label="A", *, primitives=()):
    """A datum tag whose display data draws ``lines``. ``primitives`` are what
    its IDatumTag reports, which the audit must NOT read."""
    spec = SimpleNamespace(
        GetLineCount=lambda: len(primitives),
        GetLineAtIndex=lambda i: [0.0, *primitives[i][0], 0.0, *primitives[i][1], 0.0],
    )
    return SimpleNamespace(
        GetPosition=[x, y, 0.0],
        GetType=lambda: _drawing_layout_collect._ANNOT_DATUM,
        GetName=lambda: label,
        GetLeaderCount=lambda: 0,  # the whole point: it registers none
        GetSpecificAnnotation=lambda: spec,
        GetDisplayData=lambda: _display_data(lines),
    )


def test_datum_tag_leader_is_collected_even_though_it_registers_none():
    """rocker-arm-support datum A as probed: 4 box lines + a 12.6mm leader.

    GetLeaderCount() is 0 for every swDatumTag (SetLeader3 never made a leader,
    and cannot for a datum FEATURE symbol), so _leader_segments_of returns
    nothing however badly the tag is routed. The leader is real and drawn --
    readable as the tag's display data.
    """
    ax, ay = 0.2100, 0.1436
    box = [
        ((0.2065, 0.1366), (0.2065, ay)),
        ((0.2065, ay), (0.2135, ay)),
        ((0.2135, ay), (0.2135, 0.1366)),
        ((0.2135, 0.1366), (0.2065, 0.1366)),
    ]
    leader = [((ax, 0.1562), (ax, ay))]
    ann = _datum_tag(ax, ay, box + leader)

    segs = _drawing_layout_collect._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Front"
    )

    # The BOX must be excluded -- it is not a leader, and a tag's box legitimately
    # abuts its own view. Only the leader run survives.
    assert len(segs) == 1
    assert (segs[0].x0, segs[0].y0) == pytest.approx((ax, 0.1562))
    assert (segs[0].x1, segs[0].y1) == pytest.approx((ax, ay))


def _hole_callout(lines, *, is_callout=True):
    """A fake native hole callout. ``lines`` are (start_xy, end_xy) SHEET-space
    leader segments, returned as IDisplayData.GetLineAtIndex2 does:
    ``[color, lineType, _, _, startPt[3], endPt[3]]``. GetLeaderCount()==0 (no
    SetLeader3 leader) -- the geometry is read from GetDisplayData instead.
    """

    def _line(index):
        (sx, sy), (ex, ey) = lines[index]
        return [0.0, 0.0, 0.0, 0.0, sx, sy, 0.0, ex, ey, 0.0]

    data = SimpleNamespace(
        GetLineCount=lambda: len(lines),
        GetLineAtIndex2=_line,
    )
    display = SimpleNamespace(
        IsHoleCallout=lambda: is_callout,
        GetDisplayData=lambda: data,
    )
    return SimpleNamespace(
        GetType=lambda: _drawing_layout_collect._ANNOT_DIM,
        GetName=lambda: "RD3",
        GetLeaderCount=lambda: 0,  # the whole point: registers none
        GetSpecificAnnotation=lambda: display,
    )


def test_hole_callout_leader_reads_the_true_bent_geometry():
    """pen-rod's RD3 as probed: IsHoleCallout, GetLeaderCount()==0.

    _leader_segments_of returns nothing (no registered leader). The leader is a
    BROKEN leader (swBrokenLeaderHorizontalText), so a straight attachment->text
    chord would miss the elbow (codex #3605558274). GetDisplayData hands back the
    real per-primitive ink in sheet space: stub, sloped run, horizontal shoulder.
    """
    lines = [
        ((0.0707, 0.20571), (0.08389, 0.2192)),  # sloped run up to the elbow
        ((0.0693, 0.20429), (0.0707, 0.20571)),  # stub at the hole
        ((0.08389, 0.2192), (0.12252, 0.2192)),  # horizontal shoulder past text
    ]
    ann = _hole_callout(lines)

    segs = _drawing_layout_collect._display_dimension_leader_segments(
        _FakeAdapter(None), ann, label="RD3", owner="Front"
    )

    assert len(segs) == 3
    assert all(s.kind == "dim" for s in segs)
    assert (segs[2].x0, segs[2].y0, segs[2].x1, segs[2].y1) == pytest.approx(
        (0.08389, 0.2192, 0.12252, 0.2192)
    )
    # The shoulder reaches x=0.12252, PAST the text at 0.104 -- ground a straight
    # attachment->text chord never covered, so the chord could miss a crossing.
    assert max(s.x1 for s in segs) == pytest.approx(0.12252)


def test_collector_boxes_no_dimension_but_keeps_hole_callout_leaders(monkeypatch):
    """A display dimension used to become an 8 mm nominal square with NONE
    scope, which nothing ever overlap-checked: MHA-DT-021's "20.8"/"8.42" and its
    callouts over the right view all passed. The shared layout audit boxes
    dimension text from display data now, so the element audit carries NO
    dimension box -- only the hole callout's leader ink for crossing checks."""
    monkeypatch.setattr(
        solidworks_mcp.adapters.sw_type_info, "early_bound_or_flag", lambda obj, *_a, **_k: obj
    )
    lines = [
        ((0.0707, 0.20571), (0.08389, 0.2192)),
        ((0.0693, 0.20429), (0.0707, 0.20571)),
        ((0.08389, 0.2192), (0.12252, 0.2192)),
    ]
    callout = _hole_callout(lines)
    callout.GetPosition = lambda: [0.104, 0.2192, 0.0]
    view = SimpleNamespace(
        GetName2="Front",
        Type=6,  # swDrawingViewTypes_e.swDrawingStandardView
        GetOrientationName=lambda: "*Front",
        GetOutline=[0.05, 0.15, 0.15, 0.25],
        GetAnnotations=lambda: [callout],
        GetTableAnnotations=[],
        GetNextView=None,
    )
    sheet_view = SimpleNamespace(
        GetNextView=lambda: view, GetTableAnnotations=[], GetAnnotations=lambda: []
    )
    sheet = SimpleNamespace(
        GetProperties=lambda: [0.0, 0.0, 1.0, 1.0, 0.0, SHEET_W, SHEET_H],
        GetZoneMargin=lambda _code: 0.0127,
    )
    model = SimpleNamespace(GetCurrentSheet=sheet, GetFirstView=lambda: sheet_view)

    elements, leaders, _region = _drawing_layout_collect.collect_layout_elements(
        _FakeAdapter(model), layout=DrawingLayout.LANDSCAPE
    )

    assert not [element for element in elements if element.kind == "dim"]
    assert [(s.label, s.owner) for s in leaders] == [("RD3", "Front")] * 3


def test_plain_dimension_contributes_no_leader():
    """A non-callout display dimension keeps its text on the dimension line, not
    at the end of a free leader -- so it must yield NO leader segment (else every
    linear/radius dimension would spray phantom leaders across the audit)."""
    ann = _hole_callout([((0.0, 0.0), (0.1, 0.1))], is_callout=False)
    segs = _drawing_layout_collect._display_dimension_leader_segments(
        _FakeAdapter(None), ann, label="Length", owner="Front"
    )
    assert segs == []


def test_datum_leader_across_a_foreign_view_now_flags():
    """The defect the eye pass found on the former tip bushing and crank-arm.

    A datum leader driven through a neighbouring view used to pass EVERY gate:
    the box is CollisionScope.NONE so it is never overlap-checked, and the tag
    contributes no leader segments so it was never crossing-checked either.
    """
    # Tag below the view, leader driven straight UP through it to a pick above.
    box = [
        ((0.14, 0.05), (0.14, 0.057)),
        ((0.14, 0.057), (0.147, 0.057)),
        ((0.147, 0.057), (0.147, 0.05)),
        ((0.147, 0.05), (0.14, 0.05)),
    ]
    leader = [((0.1435, 0.25), (0.1435, 0.057))]
    ann = _datum_tag(0.1435, 0.057, box + leader)
    segs = _drawing_layout_collect._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Front"
    )

    (crossing,) = find_leader_crossings(segs, _views())
    assert crossing.view.label == "Top"


def test_closed_rectangle_ignores_a_tag_with_no_box():
    """No rectangle found -> treat every line as leader, never crash.

    Conservative on purpose: an unrecognised tag shape yields MORE crossing
    checks, not fewer. Silently returning [] would restore the blind spot.
    """
    lines = [((0.10, 0.10), (0.15, 0.18))]  # a lone diagonal, no box
    assert _drawing_layout_collect._closed_rectangle(lines) == set()
    ann = _datum_tag(0.10, 0.10, lines)
    segs = _drawing_layout_collect._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Front"
    )
    assert len(segs) == 1


def test_leader_clipping_a_pictorial_view_is_not_a_crossing():
    """An isometric view's outline is mostly EMPTY diagonal space.

    _view_scope already exempts it from the overlap audit for this reason
    (CollisionScope.NONE); the leader audit must agree, or a leader clipping an
    empty corner fails a drawing that is correct (codex #334). Keying on
    kind == "view" alone was what let this in.
    """
    iso = _el(
        "Isometric", 0.10, 0.10, 0.30, 0.30, kind="view", scope=CollisionScope.NONE
    )
    leader = LeaderSegment("Ra 1.6", "gdt", 0.05, 0.12, 0.35, 0.12, owner="Front")
    assert find_leader_crossings([leader], [iso]) == []

    # Positive control: the SAME leader across an ORTHO view still flags, so the
    # skip is scoped to pictorials and has not disabled the gate.
    ortho = _el("Top", 0.10, 0.10, 0.30, 0.30, kind="view", scope=CollisionScope.ALL)
    (crossing,) = find_leader_crossings([leader], [ortho])
    assert crossing.view.label == "Top"


def test_leader_grazing_outline_padding_is_not_a_crossing():
    # Runs along Top's bottom edge, inside the GetOutline whitespace only.
    leader = LeaderSegment("n", "note", 0.05, 0.2005, 0.30, 0.2005, owner="Front")
    assert find_leader_crossings([leader], _views()) == []


def test_bent_leader_reports_each_segment_that_crosses():
    # A bent leader is two segments; only the one through Top is a crossing.
    elbow = LeaderSegment("Ra", "gdt", 0.05, 0.28, 0.14, 0.28, owner="Front")
    tail = LeaderSegment("Ra", "gdt", 0.14, 0.28, 0.16, 0.14, owner="Front")
    crossings = find_leader_crossings([elbow, tail], _views())
    assert [c.view.label for c in crossings] == ["Top"]


def test_audit_layout_reports_crossings_alongside_boxes():
    leader = LeaderSegment("Ra 1.6", "gdt", 0.14, 0.28, 0.16, 0.14, owner="Front")
    overlaps, overflows, crossings = audit_layout(
        _views(), ZONE_REGION, leaders=[leader]
    )
    assert overlaps == []
    assert overflows == []
    assert len(crossings) == 1
    assert "move the anchor or the text placement" in format_findings(
        overlaps, overflows, crossings
    )


def test_overlap_description_reports_both_measured_boxes():
    finding = Overlap(
        _el("notes", 0.010, 0.020, 0.080, 0.060, kind="note"),
        _el("section-label", 0.050, 0.040, 0.090, 0.070, kind="note"),
        depth_x=0.030,
        depth_y=0.020,
    )

    assert finding.describe() == (
        "note 'notes' [10.0, 20.0, 80.0, 60.0] mm overlaps note "
        "'section-label' [50.0, 40.0, 90.0, 70.0] mm by 30.0 x 20.0 mm"
    )


def test_titleblock_keepout_is_not_border_checked():
    # The keep-out is a reserved region defined to reach the sheet corner, not
    # content -- border-checking it would report its own definition forever.
    title = _el("title-block", 0.264, 0.0, SHEET_W, 0.064, kind="titleblock")
    assert find_overflows([title], ZONE_REGION) == []


def _gdt(x, y, kind, label):
    annotation = SimpleNamespace(
        GetPosition=[x, y, 0.0], GetType=lambda k=kind: k, GetName=lambda n=label: n
    )
    return _drawing_layout_collect._gdt_element(_FakeAdapter(None), annotation, label, kind)


def test_surface_finish_box_matches_the_measured_symbol_anatomy():
    """An Ra symbol's anchor is its BOTTOM VERTEX and its body draws UP-RIGHT.

    Measured on the shipped sheets by three agents independently. A symmetric box
    is the wrong SHAPE here, not merely the wrong size.
    """
    ax, ay = 0.100, 0.200
    element = _gdt(ax, ay, _drawing_layout_collect._ANNOT_SFSYM, "Ra")

    assert element.xmin == ax - _drawing_layout_collect._SF_BOX_LEFT_M
    assert element.xmax == ax + _drawing_layout_collect._SF_BOX_RIGHT_M
    assert element.ymin == ay  # the vertex IS the bottom edge
    assert element.ymax == ay + _drawing_layout_collect._SF_BOX_UP_M
    # The body is far wider than tall and sits entirely above its anchor.
    assert element.xmax - element.xmin > 2 * (element.ymax - element.ymin)


def _gdt_with_geometry(
    x, y, kind, label, lines=(), triangles=(), texts=(), *, primitives=None, attached_to=()
):
    """A GD&T annotation whose display data draws ``lines``/``triangles``/``texts``.

    ``primitives`` (IGtol/IDatumTag ``GetLineAtIndex`` rows, [lineType,
    startPt[3], endPt[3]]) is what its specific interface reports; ``None``
    means no display data at all, only those primitives. ``attached_to`` is
    ``GetAttachedEntityTypes`` (swSelectType_e codes).
    """
    spec = SimpleNamespace(
        GetLineCount=lambda: len(primitives or ()),
        GetLineAtIndex=lambda i: primitives[i],
        GetArcCount=lambda: 0,
        GetTriangleCount=lambda: 0,
    )
    annotation = SimpleNamespace(
        GetPosition=[x, y, 0.0],
        GetType=lambda k=kind: k,
        GetName=lambda n=label: n,
        GetSpecificAnnotation=lambda: spec,
        GetAttachedEntityTypes=lambda: list(attached_to),
    )
    if primitives is None:
        annotation.GetDisplayData = lambda: _display_data(lines, triangles, texts)
    return _drawing_layout_collect._gdt_element(_FakeAdapter(None), annotation, label, kind)


def test_control_frame_is_measured_from_its_rendered_lines():
    """An FCF's box is its real geometry, NOT a square around its anchor.

    The numbers are a position frame as the COM probe read it off the retired
    top-crossbar drawing (2026-07-16; the part is now merged into the top-frame
    casting): five 7.0mm-tall compartment rectangles spanning x
    0.1200..0.1616 off anchor (0.1200, 0.0900), plus a leader shoulder and a
    diagonal leader. Independently confirmed against the render, which measured
    the same frame at +41.6mm right / -7.1mm down of the anchor.
    """
    ax, ay = 0.1200, 0.0900
    frame = [
        ((ax, ay - 0.0070), (ax, ay)),  # first compartment
        ((ax, ay), (0.1616, ay)),  # frame top run
        ((0.1616, ay), (0.1616, ay - 0.0070)),
        ((0.1616, ay - 0.0070), (ax, ay - 0.0070)),
    ]
    leader = [
        ((0.1137, 0.0865), (ax, 0.0865)),  # shoulder
        ((0.1137, 0.0865), (0.1049, 0.1268)),
    ]  # diagonal
    el = _gdt_with_geometry(
        ax, ay, _drawing_layout_collect._ANNOT_GTOL, "pos", lines=frame + leader
    )

    # The FRAME hangs down-right of the anchor (its top-left corner), so the
    # box's bottom is the frame's bottom...
    assert el.ymin == pytest.approx(ay - 0.0070)
    # ...and it reaches the frame's full 41.6mm width. The old +-8mm square
    # stopped at 0.128 and left ~34mm of frame body unchecked.
    assert el.xmax == pytest.approx(0.1616)
    assert el.xmax - ax > 0.030
    # The box also spans the LEADER (left to 0.1049, up to 0.1268): that is ink
    # too, and it can cross a border on its own. So the element's ymax is the
    # leader's apex, NOT the frame's top edge at the anchor.
    assert el.xmin == pytest.approx(0.1049)
    assert el.ymax == pytest.approx(0.1268)
    assert el.ymax > ay


def test_datum_tag_box_spans_its_leader_and_triangle():
    """rocker-arm-support datum A as probed: 7x7mm box + a 12.6mm leader up."""
    ax, ay = 0.2100, 0.1436
    box = [
        ((0.2065, 0.1366), (0.2065, ay)),
        ((0.2065, ay), (0.2135, ay)),
        ((0.2135, ay), (0.2135, 0.1366)),
        ((0.2135, 0.1366), (0.2065, 0.1366)),
    ]
    leader = [((ax, 0.1562), (ax, ay))]
    tri = [((0.2086, 0.1537), (0.2114, 0.1537), (0.2100, 0.1562))]
    el = _gdt_with_geometry(
        ax, ay, _drawing_layout_collect._ANNOT_DATUM, "A", lines=box + leader, triangles=tri
    )

    assert el.ymin == pytest.approx(0.1366)  # box bottom
    assert el.ymax == pytest.approx(0.1562)  # triangle tip at the attachment
    assert (el.xmin, el.xmax) == pytest.approx((0.2065, 0.2135))


MM = 0.001

# MHA-DT-019 (pc-858x928b at bc942d25f) as pc-gdt-ink-diag a89a13a7a logged it:
# the cylindricity FCF in the 4:1 end view. GetPosition is its frame's
# top-left, (0.065, 0.232); the render prints the frame at about
# (0.0648..0.0853, 0.2250..0.2319). Its IGtol primitives are a crossed 7 mm
# placeholder square at GetTextPoint (the leader's far end) plus the leader's
# last run.
_MHA062_CYLINDRICITY_PRIMITIVES = [
    [0.0, 0.062883, 0.215112, 0.0, 0.062883, 0.208112, 0.0],
    [0.0, 0.062883, 0.208112, 0.0, 0.069883, 0.208112, 0.0],
    [0.0, 0.069883, 0.208112, 0.0, 0.069883, 0.215112, 0.0],
    [0.0, 0.069883, 0.215112, 0.0, 0.062883, 0.215112, 0.0],
    [0.0, 0.062883, 0.215112, 0.0, 0.069883, 0.208112, 0.0],
    [0.0, 0.062883, 0.208112, 0.0, 0.069883, 0.215112, 0.0],
    [0.0, 0.062883, 0.211612, 0.187, 0.062808, 0.215016, 0.374],
]
# Its datum A, same view: IDatumTag lines are a leader up from the triangle,
# a jog left to x 0.048635 and a box at x 0.041635..0.048635; the render
# prints the box centred on the leader (x ~0.0514..0.0585) with no jog.
_MHA062_DATUM_A_PRIMITIVES = [
    ((0.054991, 0.2177), (0.054985, 0.2277)),
    ((0.054985, 0.2277), (0.048635, 0.2277)),
    ((0.048635, 0.2242), (0.041635, 0.2242)),
    ((0.041635, 0.2242), (0.041635, 0.2312)),
    ((0.041635, 0.2312), (0.048635, 0.2312)),
    ((0.048635, 0.2312), (0.048635, 0.2242)),
]


def _recorded_events(monkeypatch):
    events = []
    monkeypatch.setattr(
        _telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return events


def test_a_leadered_frames_igtol_primitives_never_box_it(monkeypatch):
    """pc-858x928b: MHA-DT-019's cylindricity frame printed over "STRAPS" and
    "0.45" while the audit boxed it as the 7 mm placeholder its IGtol
    primitives draw at the leader's far end, 17 mm below the frame. Those
    primitives are no longer read: with no display data the symbol keeps the
    nominal square at its position, and says so in a trace event."""
    events = _recorded_events(monkeypatch)
    el = _gdt_with_geometry(
        0.065, 0.232, _drawing_layout_collect._ANNOT_GTOL, "cylindricity",
        primitives=_MHA062_CYLINDRICITY_PRIMITIVES,
    )
    placeholder = (0.062808, 0.208112, 0.069883, 0.215112)
    assert (el.xmin, el.ymin, el.xmax, el.ymax) != pytest.approx(placeholder)
    half = _drawing_layout_collect._NOMINAL_GDT_HALF_M
    assert (el.xmin, el.ymax) == pytest.approx((0.065 - half, 0.232 + half))
    assert [(name, attrs["symbol"]) for name, attrs in events] == [("gdt_box.fallback", "cylindricity")]


def test_a_datum_tags_primitive_jog_is_not_a_leader():
    """The same tag's IDatumTag jog (x 0.054985 -> 0.048635) is a leader run
    the sheet never prints; it would be crossing-checked as one. With no
    display data there is no leader to read."""
    ann = _datum_tag(0.055, 0.229, [], primitives=_MHA062_DATUM_A_PRIMITIVES)
    segs = _drawing_layout_collect._datum_leader_segments(
        _FakeAdapter(None), ann, label="A", owner="Drawing View1"
    )
    assert not [s for s in segs if 0.0486 < min(s.x0, s.x1) < 0.0487]


# knife-mount (layoutcal d09c2b9eb), 2:1: display data of datum A and its
# leadered three-compartment position frame, in mm. Their text runs land on
# the printed PDF glyphs within 0.15 mm, so this is where the ink is.
_KNIFE_FCF_LINES = [
    ((147.0, 161.63), (147.0, 168.63)),
    ((147.0, 168.63), (154.0, 168.63)),
    ((154.0, 168.63), (154.0, 161.63)),
    ((154.0, 161.63), (147.0, 161.63)),
    ((154.0, 161.63), (154.0, 168.63)),
    ((154.0, 168.63), (170.12, 168.63)),
    ((170.12, 168.63), (170.12, 161.63)),
    ((170.12, 161.63), (154.0, 161.63)),
    ((170.12, 161.63), (170.12, 168.63)),
    ((170.12, 168.63), (176.41, 168.63)),
    ((176.41, 168.63), (176.41, 161.63)),
    ((176.41, 161.63), (170.12, 161.63)),
    ((140.65, 165.13), (147.0, 165.13)),  # leader, from the frame's mid-height
    ((140.65, 165.13), (114.63, 140.63)),
]
_KNIFE_FCF_TEXTS = [
    ("<GTOL-POSI>", (147.88, 163.38), 2.8),
    ("<MOD-DIAM>", (155.42, 162.5), 2.8),
    ("0.20", (159.64, 162.35), 3.5),
    ("A", (171.54, 162.35), 3.5),
]
_KNIFE_DATUM_LINES = [
    ((115.0, 169.37), (115.0, 187.37)),  # leader
    ((118.5, 187.37), (111.5, 187.37)),
    ((111.5, 187.37), (111.5, 194.37)),
    ((111.5, 194.37), (118.5, 194.37)),
    ((118.5, 194.37), (118.5, 187.37)),
]


def _m(points):
    return [tuple(tuple(v * MM for v in point) for point in line) for line in points]


def test_a_frame_is_boxed_from_its_display_data():
    """knife-mount's position frame: the frame (147.0..176.41 x 161.63..168.63,
    top-left at GetPosition) plus its leader down to (114.63, 140.63)."""
    texts = [(t, (x * MM, y * MM), h * MM) for t, (x, y), h in _KNIFE_FCF_TEXTS]
    el = _gdt_with_geometry(
        0.147, 0.16863, _drawing_layout_collect._ANNOT_GTOL, "position",
        lines=_m(_KNIFE_FCF_LINES), texts=texts,
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx(
        (0.11463, 0.14063, 0.17641, 0.16863)
    )


def test_a_frame_attached_to_a_dimension_is_boxed_from_its_display_data():
    """Main's review: the dimension-attached fallback is a DATUM rule. A frame
    hung under a dimension reads its display data like any other; the nominal
    square is wrong for an FCF by construction."""
    dimension = _drawing_layout_collect._SEL_DIMENSION
    frame = _gdt_with_geometry(
        0.147, 0.16863, _drawing_layout_collect._ANNOT_GTOL, "position",
        lines=_m(_KNIFE_FCF_LINES), attached_to=(dimension,),
    )
    assert (frame.xmin, frame.xmax) == pytest.approx((0.11463, 0.17641))
    datum = _gdt_with_geometry(
        0.115, 0.18737, _drawing_layout_collect._ANNOT_DATUM, "A",
        lines=_m(_KNIFE_DATUM_LINES), attached_to=(dimension,),
    )
    half = _drawing_layout_collect._NOMINAL_GDT_HALF_M
    assert (datum.xmin, datum.xmax) == pytest.approx((0.115 - half, 0.115 + half))


def test_a_datum_tag_is_boxed_and_led_from_its_display_data():
    """knife-mount's datum A: box 111.5..118.5 x 187.37..194.37 over an 18 mm
    leader down to its triangle; the leader is the one run left once the box
    is set aside."""
    tri = [((0.1164, 0.16937), (0.1136, 0.16937), (0.1150, 0.17182))]
    el = _gdt_with_geometry(
        0.115, 0.18737, _drawing_layout_collect._ANNOT_DATUM, "A",
        lines=_m(_KNIFE_DATUM_LINES), triangles=tri,
        texts=[("A", (0.11327, 0.18809), 0.0035)],
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.1115, 0.16937, 0.1185, 0.19437))
    segs = _drawing_layout_collect._datum_leader_segments(
        _FakeAdapter(None), _datum_tag(0.115, 0.18737, _m(_KNIFE_DATUM_LINES)), label="A", owner="Drawing View1"
    )
    assert [(s.x0, s.y0, s.x1, s.y1) for s in segs] == [pytest.approx((0.115, 0.16937, 0.115, 0.18737))]


# MHA-DT-019 as gdtdiag2 (c7d835ede, run 20260926T100140395Z) logged its display
# data. Overlaid on the pc-858x928b render (mha062-gdt-overlay.png,
# mha062-crown-overlay.png) the frames and datum box sit exactly on the ink.
def _lines(*runs):
    return [((x0, y0), (x1, y1)) for x0, y0, x1, y1 in runs]


_MHA062_CYLINDRICITY = _lines(
    (0.065, 0.225, 0.065, 0.232), (0.065, 0.232, 0.0734, 0.232),
    (0.0734, 0.232, 0.0734, 0.225), (0.0734, 0.225, 0.065, 0.225),
    (0.0734, 0.225, 0.0734, 0.232), (0.0734, 0.232, 0.085295, 0.232),
    (0.085295, 0.232, 0.085295, 0.225), (0.085295, 0.225, 0.0734, 0.225),
    (0.05865, 0.2285, 0.065, 0.2285), (0.05865, 0.2285, 0.063047, 0.214826),
)
_MHA062_CROWN = _lines(
    (0.245, 0.221, 0.245, 0.228), (0.245, 0.228, 0.2534, 0.228),
    (0.2534, 0.228, 0.2534, 0.221), (0.2534, 0.221, 0.245, 0.221),
    (0.2534, 0.221, 0.2534, 0.228), (0.2534, 0.228, 0.265295, 0.228),
    (0.265295, 0.228, 0.265295, 0.221), (0.265295, 0.221, 0.2534, 0.221),
    (0.271645, 0.2245, 0.265295, 0.2245), (0.271645, 0.2245, 0.28745, 0.206399),
)
_MHA062_DATUM_A = _lines(
    (0.055, 0.2177, 0.055, 0.229), (0.0585, 0.229, 0.0515, 0.229),
    (0.0515, 0.229, 0.0515, 0.236), (0.0515, 0.236, 0.0585, 0.236),
    (0.0585, 0.236, 0.0585, 0.229),
)


def test_mha062_cylindricity_frame_is_boxed_where_it_prints():
    """The verification bar: rendered frame (0.0648..0.0853, 0.2250..0.2319).
    Its display lines put it at 0.0650..0.0853 x 0.2250..0.2320, over
    "STRAPS" and "0.45"; the box also carries the leader to (0.05865, 0.21483)."""
    texts = [
        ("<GTOL-CYL>", (0.0657, 0.22675), 0.0028, 0.007),
        ("0.01", (0.074822, 0.225722), 0.0035, 0.009051),
    ]
    el = _gdt_with_geometry(
        0.065, 0.232, _drawing_layout_collect._ANNOT_GTOL, "cylindricity",
        lines=_MHA062_CYLINDRICITY, texts=texts,
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.05865, 0.214826, 0.085295, 0.232))


def test_mha062_crown_frame_carries_its_below_frame_text_at_its_own_width(monkeypatch):
    """"BOTH CROWNS" prints 34.1 mm wide under the frame, reaching x 0.2791;
    SolidWorks reports that width, and no estimate is logged."""
    events = _recorded_events(monkeypatch)
    texts = [
        ("<GTOL-SPROF>", (0.2457, 0.22275), 0.0028, 0.007),
        ("0.05", (0.254822, 0.221722), 0.0035, 0.009051),
        ("BOTH CROWNS", (0.245, 0.215444), 0.0035, 0.034140),
    ]
    display = _drawing_layout_audit.annotation_display(
        _FakeAdapter(None), SimpleNamespace(GetDisplayData=lambda: _display_data(_MHA062_CROWN, (), texts))
    )[0]
    box = _layout_audit.display_box({**display, "lines": []})  # the text alone
    assert (box.xmin, box.xmax) == pytest.approx((0.245, 0.27914))
    el = _gdt_with_geometry(
        0.245, 0.228, _drawing_layout_collect._ANNOT_GTOL, "crown", lines=_MHA062_CROWN, texts=texts
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.245, 0.206399, 0.28745, 0.228))
    assert not [name for name, _attrs in events if name == "gdt_box.text_estimated"]


def test_a_run_without_a_reported_width_is_estimated_and_logged(monkeypatch):
    events = _recorded_events(monkeypatch)
    _gdt_with_geometry(
        0.245, 0.228, _drawing_layout_collect._ANNOT_GTOL, "crown", lines=_MHA062_CROWN,
        texts=[("BOTH CROWNS", (0.245, 0.215444), 0.0035)],
    )
    assert [(name, attrs) for name, attrs in events] == [
        ("gdt_box.text_estimated", {"symbol": "crown", "runs": 1})
    ]
    # A refused width is not a lost read: the layout audit must not gate on it.
    display, refused = _drawing_layout_audit.annotation_display(
        _FakeAdapter(None),
        SimpleNamespace(GetDisplayData=lambda: _display_data(texts=[("BOTH CROWNS", (0.245, 0.215444), 0.0035)])),
    )
    assert "w" not in display["texts"][0] and refused == {}


def test_mha062_datum_a_is_boxed_and_led_where_it_prints():
    """Rendered: box centred on its leader at x 0.055, 0.0514..0.0585 x
    0.2293..0.2360, no jog. The display data says exactly that."""
    el = _gdt_with_geometry(
        0.055, 0.229, _drawing_layout_collect._ANNOT_DATUM, "A", lines=_MHA062_DATUM_A,
        triangles=[((0.0564, 0.2177), (0.0536, 0.2177), (0.055, 0.22015))],
        texts=[("A", (0.053274, 0.229722), 0.0035, 0.003451)],
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.0515, 0.2177, 0.0585, 0.236))
    segs = _drawing_layout_collect._datum_leader_segments(
        _FakeAdapter(None), _datum_tag(0.055, 0.229, _MHA062_DATUM_A), label="A", owner="Drawing View1"
    )
    assert [(s.x0, s.y0, s.x1, s.y1) for s in segs] == [pytest.approx((0.055, 0.2177, 0.055, 0.229))]


def test_unmeasurable_gdt_falls_back_to_the_nominal_square():
    """No GetSpecificAnnotation (PMI-only) -> keep a coarse box, don't drop it.

    A dropped symbol is worse than a coarse one: it leaves the audit silent on a
    symbol placed clear off the sheet.
    """
    half = _drawing_layout_collect._NOMINAL_GDT_HALF_M
    for kind in (_drawing_layout_collect._ANNOT_DATUM, _drawing_layout_collect._ANNOT_GTOL):
        element = _gdt(0.100, 0.200, kind, "tag")
        assert (element.xmin, element.ymin) == (0.100 - half, 0.200 - half)
        assert (element.xmax, element.ymax) == (0.100 + half, 0.200 + half)


def test_surface_finish_over_the_top_border_is_now_caught():
    """Regression: wheel_axle's Ra printed over the zone label, audit silent.

    Its anchor sat at y=0.255 -- inside the 0.2667 top bound -- so the old
    +/-8 mm box topped out at 0.263 and reported clean, while the real body
    reached ay+0.018 = 0.273 and printed over the border.
    """
    ra = _gdt(0.030, 0.255, _drawing_layout_collect._ANNOT_SFSYM, "Ra")
    overflows = find_overflows([ra], ZONE_REGION)
    assert overflows, "the Ra body crosses the top zone bound and must be flagged"
    assert "top" in format_findings([], overflows).lower()

    # The old symmetric box is the negative control: it does NOT reach the bound.
    half = _drawing_layout_collect._NOMINAL_GDT_HALF_M
    old = _el(
        "Ra",
        0.030 - half,
        0.255 - half,
        0.030 + half,
        0.255 + half,
        kind="gdt",
        scope=CollisionScope.NONE,
    )
    assert not find_overflows([old], ZONE_REGION), (
        "negative control: the old box was blind here -- that is the bug"
    )


def test_surface_finish_clear_of_the_border_still_passes():
    """Positive control: draw-D's verified-safe bounds must audit clean."""
    for ax, ay in ((0.045, 0.1045), (0.133, 0.1992)):
        ra = _gdt(ax, ay, _drawing_layout_collect._ANNOT_SFSYM, "Ra")
        assert not find_overflows([ra], ZONE_REGION)


# --- leader-vs-leader crossings ----------------------------------------------


def test_two_leaders_crossing_each_other_are_flagged():
    # The pen-rod defect at its MEASURED sheet coordinates (2026-07-16 render).
    # The Ra rises from its symbol right of the rod to the slide face; the
    # squareness frame's leader descends from its box to the rod's bottom. X.
    #
    # The frame's leader is BENT, and the bend matters here: its box sits at
    # x=0.102 but the shoulder runs left to an elbow at (0.0956, 0.1044) before
    # the diagonal drops to the rod. Modelling it as one straight run from the
    # box moves the reported crossing 1.5 mm (0.0805 -> 0.0820), so the DIAGONAL
    # is what gets asserted -- the segment the sheet actually draws.
    ra = LeaderSegment("Ra 1.6", "gdt", 0.170, 0.068, 0.0675, 0.100, owner="Front")
    fcf = LeaderSegment("perp", "gdt", 0.0956, 0.1044, 0.070, 0.090, owner="Front")
    (crossing,) = find_leader_leader_crossings([ra, fcf])
    assert {crossing.a.label, crossing.b.label} == {"Ra 1.6", "perp"}
    # The real intersection, independently read off the render at (0.080, 0.096)
    # -- not merely "something was reported".
    assert crossing.x == pytest.approx(0.0805, abs=5e-4)
    assert crossing.y == pytest.approx(0.0959, abs=5e-4)
    assert "cross their leaders" in crossing.describe()


def test_the_fix_direction_clears_the_crossing():
    # Positive control for the test above: same two annotations, the frame moved
    # below the rod so its leader approaches from underneath. Without this, the
    # test above would pass just as happily against a function that flags every
    # pair it is handed.
    ra = LeaderSegment("Ra 1.6", "gdt", 0.170, 0.068, 0.0675, 0.100, owner="Front")
    fcf = LeaderSegment("perp", "gdt", 0.102, 0.0765, 0.070, 0.090, owner="Front")
    assert find_leader_leader_crossings([ra, fcf]) == []


def test_a_bent_leaders_own_elbow_and_tail_never_cross():
    # A bent leader is two segments sharing an elbow BY CONSTRUCTION. If the
    # touch tolerance were wrong, every bent leader on every sheet would report.
    elbow = LeaderSegment("Ra", "gdt", 0.10, 0.10, 0.14, 0.10, owner="Front")
    tail = LeaderSegment("Ra", "gdt", 0.14, 0.10, 0.18, 0.16, owner="Front")
    assert find_leader_leader_crossings([elbow, tail]) == []


def test_two_leaders_landing_on_one_point_touch_but_do_not_cross():
    # Two arrows converging on a shared edge point is a STACKING question the
    # overlap audit owns. Reporting it here would be a false positive.
    a = LeaderSegment("datum A", "gdt", 0.20, 0.05, 0.10, 0.10, owner="Front")
    b = LeaderSegment("Ra", "gdt", 0.20, 0.15, 0.10, 0.10, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_parallel_leaders_never_cross():
    a = LeaderSegment("one", "gdt", 0.10, 0.10, 0.20, 0.14, owner="Front")
    b = LeaderSegment("two", "gdt", 0.10, 0.12, 0.20, 0.16, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_leaders_whose_extensions_would_meet_off_segment_do_not_cross():
    # Crossing must be judged on the SEGMENTS, not their infinite lines: these
    # two only meet far outside both runs.
    a = LeaderSegment("one", "gdt", 0.10, 0.10, 0.12, 0.11, owner="Front")
    b = LeaderSegment("two", "gdt", 0.10, 0.20, 0.12, 0.19, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_leader_leader_crossings_reach_the_audit():
    # The gate is only real if audit_layout actually runs it.
    ra = LeaderSegment("Ra 1.6", "gdt", 0.170, 0.068, 0.0675, 0.100, owner="Front")
    fcf = LeaderSegment("perp", "gdt", 0.102, 0.1045, 0.070, 0.090, owner="Front")
    _, _, crossings = audit_layout(
        [_el("Front", 0.06, 0.09, 0.08, 0.21, kind="view")],
        DrawableRegion.whole_sheet(0.4318, 0.2794),
        leaders=[ra, fcf],
    )
    assert any("cross their leaders" in c.describe() for c in crossings)


def test_leaders_converging_on_one_point_are_stacked_not_crossed():
    # platen-guide's REAL segments (2026-07-16). Datum A arrives horizontally and
    # a second frame's leader arrives diagonally; both terminate at x=0.3650,
    # 0.2 mm apart in y. Their last 0.2 mm technically crosses -- underneath
    # ~2.4 mm arrowheads, so no reader can see it. The gate's first sweep DID
    # report this; it was the only false positive in 23 sheets.
    datum = LeaderSegment("datum A", "gdt", 0.3650, 0.1100, 0.3520, 0.1100, owner="Iso")
    other = LeaderSegment("frame", "gdt", 0.3389, 0.0885, 0.3650, 0.1102, owner="Iso")
    assert find_leader_leader_crossings([datum, other]) == []


def test_a_shared_terminus_does_not_mask_a_real_crossing_elsewhere():
    # Positive control for the exemption: pen-assembly's B4xB6 balloons end
    # 4.7 mm apart -- the tightest TRUE positive on the fleet, and it must still
    # report. Without this, widening _SHARED_TERMINUS_M would silently swallow
    # real findings and every test above would still pass.
    b4 = LeaderSegment("B4", "note", 0.2380, 0.1882, 0.2280, 0.1121, owner="Iso")
    b6 = LeaderSegment("B6", "note", 0.2546, 0.1508, 0.2238, 0.1099, owner="Iso")
    (crossing,) = find_leader_leader_crossings([b4, b6])
    assert crossing.x == pytest.approx(0.2285, abs=5e-4)
    assert crossing.y == pytest.approx(0.1161, abs=5e-4)


# --- every sheet is held to zero; there is no grandfathered case -------------


def _stub_layout(monkeypatch, leader_crossings):
    """Drive check_drawing_layout with a chosen number of leader crossings."""
    seg = LeaderSegment("a", "gdt", 0.0, 0.0, 0.1, 0.1, owner="Front")
    found = [LeaderCrossing(seg, seg, 0.05, 0.05) for _ in range(leader_crossings)]
    monkeypatch.setattr(
        _drawing_layout_collect,
        "collect_layout_elements",
        lambda _adapter, *, layout: ([], [], WHOLE_SHEET),
    )
    monkeypatch.setattr(
        _drawing_layout_collect,
        "audit_layout",
        lambda *_a, **_k: ([], [], found),
    )


def test_a_clean_sheet_passes(monkeypatch):
    _stub_layout(monkeypatch, 0)
    _drawing_layout_collect.check_drawing_layout(
        None, layout=DrawingLayout.LANDSCAPE, stem="pn-pen-assembly"
    )


@pytest.mark.parametrize("stem", ["pn-pen-assembly", "dt-crank-arm", ""])
def test_no_sheet_is_exempt_from_a_leader_crossing(monkeypatch, stem):
    """pn-pen-assembly USED to be grandfathered for 2 crossings while the fix was
    thought to need a design decision. It needed the balloon radius, which
    the rendered full-circle arc exposes. The exemption died with the defect, and no
    sheet -- named, unnamed, or formerly-grandfathered -- may reintroduce one."""
    _stub_layout(monkeypatch, 1)
    with pytest.raises(RuntimeError):
        _drawing_layout_collect.check_drawing_layout(
            None, layout=DrawingLayout.LANDSCAPE, stem=stem
        )


def test_the_grandfather_machinery_is_gone():
    """A tripwire on the retirement: re-adding an allowlist must be a deliberate
    act that trips a test, not a quiet way to make a red build green."""
    sources = sorted(Path(__file__).resolve().parent.glob("_drawing_*.py"))
    assert sources, "no drawing-helper sources found"
    assert {"_drawing_common.py", "_drawing_layout_collect.py"} <= {
        source.name for source in sources
    }
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        bindings = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        bindings.update(
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        bindings.update(
            node.asname or node.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.alias)
        )
        assert "_KNOWN_LEADER_CROSSINGS" not in bindings, source


# --- the shared-terminus exemption must not swallow real crossings -----------


def test_a_shared_terminus_does_not_excuse_a_crossing_ELSEWHERE():
    """Codex #3601319580's counterexample, pinned.

    Two segments whose starts are 0.9 mm apart -- INSIDE _SHARED_TERMINUS_M --
    still cross once, and here that crossing is at (5, 0): 5 mm from the shared
    end, mid-span, plainly visible in ink. The old endpoint-only test skipped the
    pair outright and threw it away. The exemption is for crossings buried under
    a shared arrowhead, so it must key on where the CROSSING is, not merely on
    whether two ends are near each other.
    """
    a = LeaderSegment("A", "gdt", 0.0, 0.0, 0.010, 0.0, owner="Front")
    b = LeaderSegment("B", "gdt", 0.0, 0.0009, 0.010, -0.0009, owner="Front")
    found = find_leader_leader_crossings([a, b])
    assert len(found) == 1, "a mid-span crossing must survive a nearby shared end"
    assert found[0].x == pytest.approx(0.005, abs=1e-4)
    assert found[0].y == pytest.approx(0.0, abs=1e-4)


def test_the_converging_arrowhead_artefact_is_still_exempt():
    """The positive control for the fix: the real platen-guide shape stays clean.

    Two leaders converging on ONE attachment meet AT that attachment, so the
    crossing sits under the ~2.4 mm arrowhead and prints as one arrow. Tightening
    the exemption must not start flagging this.
    """
    a = LeaderSegment("A", "dim", 0.3650, 0.1000, 0.3400, 0.1200, owner="Front")
    b = LeaderSegment("B", "dim", 0.3652, 0.1000, 0.3900, 0.1200, owner="Front")
    assert find_leader_leader_crossings([a, b]) == []


def test_the_ratchet_never_excuses_a_leader_across_a_VIEW():
    """Codex #3601319575, kept after the ratchet's retirement.

    The bug was an exemption swallowing a leader-through-VIEW crossing. The
    exemption is gone, but the class it endangered must stay fatal -- so this
    keeps proving a view crossing fails, whatever the surrounding policy.
    """
    seg = LeaderSegment("a", "gdt", 0.0, 0.0, 0.1, 0.1, owner="Front")
    view = _el("OtherView", 0.05, 0.05, 0.15, 0.15)
    mixed = [Crossing(seg, view)]  # a leader across a foreign view: always fatal

    class _Stub:
        pass

    import _drawing_layout_collect

    real_collect, real_audit = _drawing_layout_collect.collect_layout_elements, _drawing_layout_collect.audit_layout
    _drawing_layout_collect.collect_layout_elements = lambda _a, *, layout: ([], [], WHOLE_SHEET)
    _drawing_layout_collect.audit_layout = lambda *_a, **_k: ([], [], mixed)
    try:
        with pytest.raises(RuntimeError):
            _drawing_layout_collect.check_drawing_layout(
                None, layout=DrawingLayout.LANDSCAPE, stem="pn-pen-assembly"
            )
    finally:
        _drawing_layout_collect.collect_layout_elements, _drawing_layout_collect.audit_layout = real_collect, real_audit


# --- balloon ring separation (SolidWorks-free) -------------------------------


def test_push_apart_never_reorders_the_balloons():
    """The property the whole no-crossing argument rests on.

    Balloons placed about a shared centre IN their attachments' angular order
    cannot have crossing leaders. So a separation pass that reorders silently
    destroys the guarantee. The predecessor -- an iterative pairwise relaxation
    -- did exactly that: it measured gaps modulo 2*pi, so an inverted pair read
    as a ~6 rad gap and was never repaired. These are the REAL pen-assembly
    attachment angles it was probed with, and it returned them reordered.
    """
    angles = [-1.865, -1.661, -1.629, -1.407, -1.152, 1.684, 1.805, 1.838]
    out = _drawing_balloons._push_apart_on_ring(angles, min_gap=0.4211)
    assert out == sorted(out), f"push-apart reordered the balloons: {out}"


def test_push_apart_actually_separates_to_the_gap():
    angles = [-1.865, -1.661, -1.629, -1.407, -1.152, 1.684, 1.805, 1.838]
    gap = 0.4211
    out = _drawing_balloons._push_apart_on_ring(angles, min_gap=gap)
    for a, b in zip(out, out[1:]):
        assert b - a >= gap - 1e-9, f"gap {b - a} < {gap}"
    # and the wrap-around pair, which the linear chain cannot see
    assert (out[0] + 2.0 * _math.pi) - out[-1] >= gap - 1e-9


def _cyclic_order_preserved(inp, out):
    """``out`` traces the same cyclic order round the ring as ``inp``.

    Balloons cannot cross iff their ring order is a rotation of their
    attachments' angular order, so this -- not strict linear monotonicity -- is
    the property to check across the +-pi seam.
    """
    n = len(inp)
    in_order = sorted(range(n), key=lambda i: inp[i])
    out_order = sorted(range(n), key=lambda i: out[i])
    doubled = in_order + in_order
    return any(doubled[k : k + n] == out_order for k in range(n))


def test_push_apart_keeps_a_seam_straddling_cluster_at_the_seam():
    """Codex #3605056589: attachments straddling +-pi must stay near the seam.

    ``[-3.10, 3.10]`` are 0.083 rad apart THROUGH the seam (both left of the
    view), not 6.20 apart. The buggy predecessor solved them in raw-sorted
    linear space -- under-separated, then re-centred on the ORDINARY average of
    the endpoints (~0), flipping both to ``[-0.4, 0.0]`` on the RIGHT of the
    view and hauling their leaders across the model. The unwrap-around-the-
    largest-gap frame must instead separate them to the gap AT the seam.
    """
    angles = [-3.10, 3.10]
    gap = 0.4
    out = _drawing_balloons._push_apart_on_ring(angles, min_gap=gap)
    # Separated to the gap, measured cyclically (the pair spans the seam).
    cyclic = [(b - a) % (2.0 * _math.pi) for a, b in zip(out, out[1:])]
    cyclic.append((out[0] - out[-1]) % (2.0 * _math.pi))
    assert min(cyclic) >= gap - 1e-9, f"seam pair not separated: {out}"
    # Still near +-pi (left of the view), NOT flipped to angle ~0 (right).
    for angle in out:
        assert abs(abs(angle) - _math.pi) < 0.3, f"balloon flipped off the seam: {out}"
    assert _cyclic_order_preserved(angles, out)


def test_push_apart_never_reorders_across_the_seam():
    """The no-crossing property, checked cyclically for a left-clustered view.

    A run whose attachments sit on the left (values near +-pi with the empty gap
    on the RIGHT) must come back in the same cyclic order -- the unwrap frame
    must not shuffle indices when it rotates the run off the seam.
    """
    angles = sorted([-3.0, -2.8, -2.6, 2.7, 2.9, 3.05])
    out = _drawing_balloons._push_apart_on_ring(angles, min_gap=0.35)
    assert _cyclic_order_preserved(angles, out), f"seam run reordered: {out}"
    cyclic = [(b - a) % (2.0 * _math.pi) for a, b in zip(sorted(out), sorted(out)[1:])]
    cyclic.append((min(out) + 2.0 * _math.pi) - max(out))
    assert min(cyclic) >= 0.35 - 1e-9, f"seam run not separated: {out}"


def test_push_apart_leaves_already_separated_angles_alone():
    """Minimum movement: balloons that already clear must not be herded."""
    angles = [0.0, 1.0, 2.0, 3.0]
    out = _drawing_balloons._push_apart_on_ring(angles, min_gap=0.5)
    assert out == pytest.approx(angles)


def test_push_apart_falls_back_to_even_spacing_when_it_cannot_fit():
    # 20 balloons x 0.5 rad = 10 rad > 2*pi: packing tighter than their own
    # circles would trade crossings for overlaps, the trade radial already lost.
    angles = [i * 0.01 for i in range(20)]
    out = _drawing_balloons._push_apart_on_ring(angles, min_gap=0.5)
    spacing = [round(b - a, 6) for a, b in zip(out, out[1:])]
    assert len(set(spacing)) == 1, "fallback must space evenly"


def test_min_angular_gap_clears_the_audits_SQUARE_not_just_the_circle():
    """_note_element boxes the balloon's circumscribed square, so two balloons
    on a ring diagonal still collide after their circles part. The gap must be
    set against the model that grades it, or placement and audit disagree --
    measured as 9 overlaps when this used 2*r."""
    ring, balloon = 0.05, 0.00472
    gap = _drawing_balloons._min_angular_gap(ring, balloon, clearance=0.0)
    assert gap * ring == pytest.approx(2.0 * _math.sqrt(2.0) * balloon, rel=1e-9)


# --- Determinism of the picks that feed the ring order -----------------------
#
# The layout audit above is only worth running if the drawing it audits is
# reproducible. It was not: drive-train built clean on one fleet pass and failed
# with "1 leader crossing(s)" between items 5 and 27 on the next, same commit,
# same cached assembly. Every pick below sits upstream of the ring order, and
# each one used to resolve ties by COM enumeration position -- an order neither
# GetVisibleEntities2 nor the drawing-component tree documents.


class _FakeEdge:
    """A model edge whose GetCurveParams2 returns fixed endpoints."""

    def __init__(self, params):
        self._params = params
        self.curve_reads = 0

    def GetCurve(self):
        self.curve_reads += 1
        return object()

    def GetCurveParams2(self):
        return self._params


def test_edge_key_reads_the_endpoints_after_generating_the_curve():
    edge = _FakeEdge((1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 0.0, 1.0, 0, 0, 0))
    key = _drawing_edges._edge_endpoint_key(_FakeAdapter(None), edge)
    assert key == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    # GetCurveParams2 reads what GetCurve generated; SolidWorks keeps no curve
    # of its own, so skipping the call returns stale or empty parameters.
    assert edge.curve_reads == 1


def test_edge_key_is_none_when_the_geometry_cannot_be_read():
    """An unreadable edge drops out of the running; it must not fail the sheet."""

    class _Mute(_FakeEdge):
        def GetCurveParams2(self):
            raise RuntimeError("no curve data")

    assert _drawing_edges._edge_endpoint_key(_FakeAdapter(None), _Mute(())) is None
    assert (
        _drawing_edges._edge_endpoint_key(_FakeAdapter(None), _FakeEdge((1.0, 2.0)))
        is None
    )


class _FakeNote:
    """A BOM balloon whose anchor sits a constant offset off its circle.

    ``placed`` is the rendered CIRCLE centre. ``GetPosition``/``SetPosition``
    read and move the ANCHOR, which native balloons keep ~(+4.0, -1.7) mm off
    the centre (#866, MHA-DT-000 integ3 leaf, 40 balloons).
    """

    ANCHOR_OFFSET = (0.0040, -0.0017)

    def __init__(self, attach_x, attach_y, radius=0.0047, item="1"):
        self._attach = (attach_x, attach_y)
        self._radius = radius
        self._item = item
        self.placed = None

    def GetBomBalloonText(self, _upper):
        # The balloon-specific API. INote.GetText returns the note's generic
        # text, which for a BOM balloon need not be the item number at all.
        return self._item

    def GetBalloonInfo(self):
        return (0, 0, 0, 0, 0, 0, self._radius)

    def GetDisplayData(self):
        return self

    def GetArcCount(self):
        return 1

    def GetArcAtIndex2(self, _index):
        cx, cy = self.placed or (0.0, 0.0)
        point = (cx + self._radius, cy, 0.0)
        return (0, 0, -1, -1, *point, *point, cx, cy, 0.0, 0.0, 0.0, 1.0, 1.0)

    def GetAnnotation(self):
        return self

    def GetLeaderPointsAtIndex(self, _index):
        # Flat x,y,z stream: balloon end first, attachment LAST.
        return (0.0, 0.0, 0.0, self._attach[0], self._attach[1], 0.0)

    def GetPosition(self):
        cx, cy = self.placed or (0.0, 0.0)
        return (cx + self.ANCHOR_OFFSET[0], cy + self.ANCHOR_OFFSET[1], 0.0)

    def SetPosition(self, x, y, _z):
        self.placed = (x - self.ANCHOR_OFFSET[0], y - self.ANCHOR_OFFSET[1])
        return True


class _MovingBalloon(_FakeNote):
    """Native-like rendered ink moves while GetBalloonInfo remains cached."""
    def __init__(self, pixel_error_m=0.0):
        super().__init__(0.11, 0.19, radius=0.005, item="2")
        self.placed = (0.15, 0.25)
        self.LockPosition = False
        self._pixel_error_m = pixel_error_m
        self._offset = (0.004, -0.002)

    def GetBalloonInfo(self):
        return (0.20, 0.30, 0.0, 0.205, 0.30, 0.0, self._radius)

    def GetPosition(self):
        return (self.placed[0] - self._offset[0], self.placed[1] - self._offset[1], 0.042)

    def SetPosition(self, x, y, _z):
        self._offset = (0.004 + self._pixel_error_m, -0.002 + self._pixel_error_m)
        self.placed = (x + self._offset[0], y + self._offset[1])
        return True

    def GetSpecificAnnotation(self):
        return self

    def IsStackedBalloon(self):
        return False

    def IsStackedBalloonMaster(self):
        return False

    def IsBomBalloon(self):
        return True

    def GetText(self):
        return "2"

    def GetExtent(self):
        return (0.0, 0.0, 0.0, 1.0, 1.0, 0.0)


def test_position_and_layout_follow_rendered_circle_when_balloon_info_is_stale(monkeypatch):
    monkeypatch.setattr(_drawing_balloons, "_early_bound", lambda value, _kind: value)
    note = _MovingBalloon()
    model = SimpleNamespace(
        GetCurrentSheet=lambda: SimpleNamespace(GetMagneticLinesCount=lambda: 0),
        EditRebuild3=lambda: True,
        GraphicsRedraw2=lambda: None,
        ActiveView=SimpleNamespace(Transform=SimpleNamespace(
            ArrayData=(1, 0, 0, 0, -1, 0, 0, 0, 1, 0, 0, 0, 1000, 0, 0, 0)
        )),
    )
    adapter = _FakeAdapter(model)
    target = (0.10, 0.18)
    _drawing_balloons.position_bom_balloon(
        adapter, [note], item_number="2", position_xy=target, label="stale native cache"
    )
    assert note.placed == pytest.approx(target)
    box = _drawing_layout_collect._note_element(adapter, note, "B2")
    assert (box.xmin, box.ymin, box.xmax, box.ymax) == pytest.approx(
        (0.095, 0.175, 0.105, 0.185)
    )


@pytest.mark.parametrize("pixels_per_metre,accepted", ((1000.0, True), (2000.0, False)))
def test_balloon_placement_acceptance_tracks_current_viewport_resolution(monkeypatch, pixels_per_metre, accepted):
    monkeypatch.setattr(_drawing_balloons, "_early_bound", lambda value, _kind: value)
    note = _MovingBalloon(pixel_error_m=0.00075)
    model = SimpleNamespace(
        GetCurrentSheet=lambda: SimpleNamespace(GetMagneticLinesCount=lambda: 0),
        EditRebuild3=lambda: True,
        GraphicsRedraw2=lambda: None,
        ActiveView=SimpleNamespace(Transform=SimpleNamespace(
            ArrayData=(1, 0, 0, 0, -1, 0, 0, 0, 1, 0, 0, 0, pixels_per_metre, 0, 0, 0)
        )),
    )
    def place():
        _drawing_balloons.position_bom_balloon(
            _FakeAdapter(model), [note], item_number="2",
            position_xy=(0.10, 0.18), label="quantized native preview",
        )
    if accepted:
        place()
        assert note.placed == pytest.approx((0.10075, 0.18075))
    else:
        with pytest.raises(RuntimeError):
            place()


@pytest.mark.parametrize("geometry", ("missing", "partial", "ambiguous", "zero_radius", "nonfinite"))
def test_rendered_balloon_circle_rejects_unusable_ink(geometry):
    note = _FakeNote(0.1, 0.2, radius=0.0 if geometry == "zero_radius" else 0.005)
    arc = list(note.GetArcAtIndex2(0))
    if geometry == "partial":
        arc[7] += 0.001
    if geometry == "nonfinite":
        arc[10] = float("nan")
    count = 0 if geometry == "missing" else 2 if geometry == "ambiguous" else 1
    note.GetDisplayData = lambda: SimpleNamespace(
        GetArcCount=lambda: count, GetArcAtIndex2=lambda _index: arc
    )
    with pytest.raises(RuntimeError):
        _drawing_balloon_display.rendered_balloon_circle(note, label="invalid native circle")


def _ring_positions(notes):
    view = SimpleNamespace(GetOutline=lambda: (0.10, 0.10, 0.20, 0.20))
    adapter = _FakeAdapter(SimpleNamespace(EditRebuild3=lambda: None))
    _drawing_balloons._spread_balloons(adapter, view, list(notes))
    return [note.placed for note in notes]


def test_balloons_attached_at_one_angle_ring_in_a_fixed_order():
    """Coaxial attachments tie on theta; the tie must not fall to arrival order.

    Both attachments sit on the +45 deg ray from the view centre, so atan2
    returns the same theta for each. Sorting on theta alone left whatever
    relative order AutoBalloon5 happened to hand over, and that order decides
    which balloon gets which ring slot -- i.e. whether the leaders cross.
    """
    near, far = _FakeNote(0.1600, 0.1600), _FakeNote(0.1800, 0.1800)
    forward = dict(zip(("near", "far"), _ring_positions([near, far])))
    near2, far2 = _FakeNote(0.1600, 0.1600), _FakeNote(0.1800, 0.1800)
    reversed_ = dict(zip(("far", "near"), _ring_positions([far2, near2])))
    assert forward == reversed_
    assert forward["near"] != forward["far"]


def test_spread_balloons_land_their_circles_on_the_ring_not_their_anchors():
    """#866: the ring slot is a CIRCLE centre, and SetPosition moves the anchor.

    Placing the anchor on the slot left every circle ~(+4.0, -1.7) mm off the
    ring (MHA-DT-000 integ3). The spread must carry each balloon's anchor offset.
    """
    notes = [_FakeNote(0.12, 0.13), _FakeNote(0.18, 0.17), _FakeNote(0.15, 0.19)]
    margin = 0.014
    rx = ry = 0.05 + margin
    for x, y in _ring_positions(notes):
        assert ((x - 0.15) / rx) ** 2 + ((y - 0.15) / ry) ** 2 == pytest.approx(1.0)


def test_ring_order_survives_any_arrival_order():
    """Shuffling the input must not move a single balloon."""
    # (0.16, 0.16) and (0.18, 0.18) are collinear with the view centre, so the
    # set carries a theta tie -- without one a rotation test passes on the
    # theta-only sort it is meant to guard against.
    attachments = [
        (0.1153, 0.1370),
        (0.1600, 0.1600),
        (0.1800, 0.1800),
        (0.1200, 0.1800),
        (0.1600, 0.1200),
    ]
    baseline = dict(
        zip(attachments, _ring_positions([_FakeNote(x, y) for x, y in attachments]))
    )
    for rotation in range(1, len(attachments)):
        rotated = attachments[rotation:] + attachments[:rotation]
        got = dict(zip(rotated, _ring_positions([_FakeNote(x, y) for x, y in rotated])))
        assert got == baseline


class _FakeDrawingComponent:
    """``IDrawingComponent``: its ``Name`` carries the view's root prefix
    (``drive-train-8/sub-1/cone-gear-1@Drawing View9``); its model
    component's ``Name2`` is the path below the root (``sub-1/cone-gear-1``),
    as a farm probe read them."""

    def __init__(self, name, children=(), path="", visible=True, transform=None, body=None):
        self.Name = name
        self._children = tuple(children)
        self.Visible = visible
        segments = name.split("@", 1)[0].split("/")
        self.Component = SimpleNamespace(
            GetPathName=lambda p=path: p,
            Name2="/".join(segments[1:] or segments),
            Transform2=SimpleNamespace(
                ArrayData=transform or (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
            ),
            GetBody=lambda: body,
        )

    def GetChildren(self):
        return self._children


def _instances(*names, hidden=(), bodies=None):
    """Leaf drawing components, one per instance path, in the given walk order."""
    return [
        _FakeDrawingComponent(
            f"dt-drive-train-8/{name}@Drawing View9",
            path=f"C:/x/{name.rsplit('/', 1)[-1].rsplit('-', 1)[0]}.SLDPRT",
            visible=name not in hidden,
            body=(bodies or {}).get(name),
        )
        for name in names
    ]


def _leaves(children):
    root = _FakeDrawingComponent("dt-drive-train-8", children=children)
    view = SimpleNamespace(RootDrawingComponent2=lambda _resolve: root)
    return _drawing_balloons._view_component_leaves(_FakeAdapter(None), view, label="t")


class _IsolationComponent(_FakeDrawingComponent):
    def __init__(self, name, *, visible=True, children=(), events=None):
        self._recording = False
        self.visibility_writes = []
        self.visibility_reads = 0
        self.children_reads = 0
        self.write_error = None
        self.read_error = None
        self.ignore_writes = False
        self.events = events if events is not None else []
        super().__init__(
            name,
            children=children,
            path=f"C:/x/{name.rsplit('/', 1)[-1].rsplit('-', 1)[0]}.SLDPRT",
            visible=visible,
        )
        self._recording = True

    @property
    def Visible(self):
        self.visibility_reads += 1
        if self.read_error is not None:
            raise self.read_error
        return self._visible

    @Visible.setter
    def Visible(self, value):
        if self._recording:
            self.visibility_writes.append(value)
            self.events.append(("visibility", self.Name, value))
            if self.write_error is not None:
                raise self.write_error
            if self.ignore_writes:
                return
        self._visible = value

    def GetChildren(self):
        self.children_reads += 1
        return super().GetChildren()


class _IsolationView:
    def __init__(self, children, *, disabled=False, events=None):
        # The synthetic root's Visible flag does not control view geometry.
        self.root = _FakeDrawingComponent("root", children=children, visible=False)
        self.root_reads = 0
        self._disabled = disabled
        self.update_reads = 0
        self.update_writes = []
        self.update_errors = {}
        self.ignore_updates = set()
        self.events = events if events is not None else []

    def RootDrawingComponent2(self, resolve):
        assert resolve is False
        self.root_reads += 1
        return self.root

    @property
    def DisableAutoUpdate(self):
        self.update_reads += 1
        return self._disabled

    @DisableAutoUpdate.setter
    def DisableAutoUpdate(self, value):
        self.update_writes.append(value)
        self.events.append(("updates", value))
        if value not in self.ignore_updates:
            self._disabled = value
        # Native property puts can change state and then raise.
        if value in self.update_errors:
            raise self.update_errors[value]


def _isolation_scene(*children, disabled=False, events=None, on_rebuild=None):
    events = events if events is not None else []
    view = _IsolationView(children, disabled=disabled, events=events)

    def rebuild():
        events.append(("rebuild", view._disabled))
        if on_rebuild is not None:
            on_rebuild()
        return True

    return _FakeAdapter(SimpleNamespace(EditRebuild3=rebuild)), view


def test_isolation_batches_only_changed_leaf_flags_and_preserves_other_views():
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    drop = _IsolationComponent("drop-1", events=events)
    already_shown = _IsolationComponent("keep-2")
    already_hidden = _IsolationComponent("drop-2", visible=False)
    parent = _IsolationComponent("sub-1", children=[already_shown, already_hidden])
    other_view_leaf = _IsolationComponent("keep-1", visible=False)
    other_view_leaf.Component = keep.Component
    other_view = _IsolationView([other_view_leaf])
    source_state = vars(keep.Component).copy()
    adapter, view = _isolation_scene(parent, keep, drop, events=events)

    _drawing_balloons.isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({"keep"}), label="bank"
    )

    assert events == [
        ("updates", True),
        ("visibility", "drop-1", False),
        ("visibility", "keep-1", True),
        ("updates", False),
        ("rebuild", False),
    ]
    assert already_shown.visibility_writes == []
    assert already_hidden.visibility_writes == []
    assert parent.visibility_writes == []
    assert view.root_reads == 1
    for node in (keep, drop, already_shown, already_hidden, parent):
        assert node.children_reads == 1
        assert node.visibility_reads == 2
    assert other_view.root_reads == 0
    assert other_view.update_writes == []
    assert other_view_leaf.Visible is False
    assert other_view_leaf.visibility_writes == []
    assert vars(keep.Component) == source_state


@pytest.mark.parametrize("disabled", [False, True])
def test_isolation_unchanged_flags_never_touch_update_state_but_still_rebuild(disabled):
    events = []
    keep = _IsolationComponent("keep-1")
    drop = _IsolationComponent("drop-1", visible=False)
    adapter, view = _isolation_scene(keep, drop, disabled=disabled, events=events)

    _drawing_balloons.isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({"keep"}), label="bank"
    )

    assert keep.visibility_writes == drop.visibility_writes == []
    assert view.update_reads == 0
    assert view.update_writes == []
    assert events == [("rebuild", disabled)]
    assert view.DisableAutoUpdate is disabled


def test_isolation_preserves_already_disabled_updates_during_changed_writes():
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    adapter, view = _isolation_scene(keep, disabled=True, events=events)

    _drawing_balloons.isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({"keep"}), label="bank"
    )

    assert view.update_writes == []
    assert view.DisableAutoUpdate is True
    assert events == [("visibility", "keep-1", True), ("rebuild", True)]


def test_isolation_empty_selection_fails_without_enumeration_or_mutation():
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    adapter, view = _isolation_scene(keep, events=events)

    with pytest.raises(ValueError, match="visible component set must not be empty"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset(), label="bank"
        )

    assert view.root_reads == 0
    assert view.update_reads == 0
    assert keep.visibility_writes == []
    assert events == []


def test_isolation_missing_root_fails_without_mutation():
    events = []
    adapter, view = _isolation_scene(events=events)
    view.root = None

    with pytest.raises(RuntimeError, match="drawing view has no root component"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert view.root_reads == 1
    assert view.update_reads == 0
    assert events == []


def test_isolation_missing_family_fails_before_any_mutation():
    events = []
    drop = _IsolationComponent("drop-1", events=events)
    adapter, view = _isolation_scene(drop, events=events)

    with pytest.raises(RuntimeError, match="component families not found.*keep"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert drop.visibility_writes == []
    assert view.update_reads == 0
    assert view.update_writes == []
    assert events == []


def test_isolation_does_not_unhide_ancestors_to_satisfy_a_missing_visible_family():
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    parent = _IsolationComponent("sub-1", children=[keep], visible=False, events=events)
    adapter, view = _isolation_scene(parent, events=events)

    with pytest.raises(RuntimeError, match="only hidden ancestors.*keep"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert parent.Visible is False
    assert parent.visibility_writes == keep.visibility_writes == []
    assert view.update_reads == 0
    assert view.update_writes == []
    assert events == []


def test_isolation_accounts_for_hidden_ancestors_without_changing_their_flags():
    hidden_keep = _IsolationComponent("keep-1", visible=False)
    parent = _IsolationComponent("sub-1", children=[hidden_keep], visible=False)
    visible_keep = _IsolationComponent("keep-2")
    adapter, view = _isolation_scene(parent, visible_keep)

    _drawing_balloons.isolate_drawing_view_components(
        adapter, view, visible_stems=frozenset({"keep"}), label="bank"
    )

    assert hidden_keep.Visible is True
    assert hidden_keep.visibility_writes == [True]
    assert visible_keep.Visible is True
    assert parent.Visible is False
    assert parent.visibility_writes == []


@pytest.mark.parametrize("restore_fails", [False, True])
def test_isolation_write_failure_restores_updates_and_preserves_primary(restore_fails):
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    primary = RuntimeError("visibility write failed")
    keep.write_error = primary
    adapter, view = _isolation_scene(keep, events=events)
    if restore_fails:
        view.update_errors[False] = RuntimeError("restore failed")

    with pytest.raises(RuntimeError, match="visibility write failed") as caught:
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert caught.value is primary
    assert view.DisableAutoUpdate is False
    assert view.update_writes == [True, False]
    assert events[-1] == ("updates", False)
    if restore_fails:
        assert any("restore failed" in note for note in primary.__notes__)
    else:
        assert not getattr(primary, "__notes__", ())


@pytest.mark.parametrize("ignored", [False, True])
def test_isolation_failed_suspension_restores_a_partially_applied_put(ignored):
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    adapter, view = _isolation_scene(keep, events=events)
    if ignored:
        view.ignore_updates.add(True)
    else:
        view.update_errors[True] = RuntimeError("disabling updates failed after put")

    with pytest.raises(RuntimeError, match="disabling"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert keep.visibility_writes == []
    assert view.DisableAutoUpdate is False
    assert events == [("updates", True), ("updates", False)]


@pytest.mark.parametrize("ignored", [False, True])
def test_isolation_failed_restore_is_not_silently_accepted(ignored):
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    adapter, view = _isolation_scene(keep, events=events)
    if ignored:
        view.ignore_updates.add(False)
    else:
        view.update_errors[False] = RuntimeError("restoring updates failed")

    with pytest.raises(RuntimeError, match="restor"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert view.update_writes == [True, False]
    assert events[-1] == ("updates", False)
    assert keep.visibility_writes == [True]


def test_isolation_detects_ignored_leaf_writes_only_after_restoring_and_rebuilding():
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    keep.ignore_writes = True
    adapter, view = _isolation_scene(keep, events=events)

    with pytest.raises(RuntimeError, match="visibility readback failed.*keep-1"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert view.DisableAutoUpdate is False
    assert events[-2:] == [("updates", False), ("rebuild", False)]
    assert keep.visibility_reads == 2


@pytest.mark.parametrize("changed_node", ["leaf", "ancestor"])
def test_isolation_verifies_each_instance_and_ancestor_after_rebuild(changed_node):
    events = []
    first = _IsolationComponent("keep-1")
    second = _IsolationComponent("keep-2")
    parent = _IsolationComponent("sub-1", children=[first])
    target = first if changed_node == "leaf" else parent

    def change_during_rebuild():
        target._visible = False

    adapter, view = _isolation_scene(
        parent, second, events=events, on_rebuild=change_during_rebuild
    )
    with pytest.raises(RuntimeError, match=f"{changed_node} {target.Name!r}"):
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert second.Visible is True  # Family-level presence is not per-instance proof.
    assert events == [("rebuild", False)]
    assert view.update_writes == []


@pytest.mark.parametrize("after_rebuild", [False, True])
def test_isolation_read_errors_propagate_instead_of_assuming_visible(after_rebuild):
    events = []
    keep = _IsolationComponent("keep-1")
    primary = RuntimeError("visibility read failed")

    def fail_reads():
        keep.read_error = primary

    adapter, view = _isolation_scene(
        keep, events=events, on_rebuild=fail_reads if after_rebuild else None
    )
    if not after_rebuild:
        fail_reads()
    with pytest.raises(RuntimeError, match="visibility read failed") as caught:
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert caught.value is primary
    assert keep.visibility_writes == []
    assert view.update_writes == []
    assert events == ([("rebuild", False)] if after_rebuild else [])


def test_isolation_rebuild_failure_happens_with_original_update_state_restored():
    events = []
    keep = _IsolationComponent("keep-1", visible=False, events=events)
    primary = RuntimeError("drawing rebuild failed")

    def fail_rebuild():
        raise primary

    adapter, view = _isolation_scene(keep, events=events, on_rebuild=fail_rebuild)
    with pytest.raises(RuntimeError, match="drawing rebuild failed") as caught:
        _drawing_balloons.isolate_drawing_view_components(
            adapter, view, visible_stems=frozenset({"keep"}), label="bank"
        )

    assert caught.value is primary
    assert view.DisableAutoUpdate is False
    assert events[-2:] == [("updates", False), ("rebuild", False)]
    assert keep.visibility_reads == 1


_ANCHOR = _drawing_balloons.BalloonAnchor(point_mm=(1.0, 2.0, 3.0))


def _chosen(children, stem="dt-cone-gear", anchor=_ANCHOR):
    return _drawing_balloons._shown_instances(_leaves(children), stem, anchor, label="t")[0].path


def test_anchor_instance_is_the_lowest_natural_name_in_any_walk_order():
    """The component tree lists children in no stable order (#865: cone-gear 1
    vs 19 across runs); the name is the only order that cannot move, and 2
    sorts before 10 before 19 as a machinist reads them."""
    from itertools import permutations

    for order in permutations(("dt-cone-gear-19", "dt-cone-gear-2", "dt-cone-gear-10")):
        assert _chosen(_instances(*order)) == "dt-cone-gear-2"


def test_anchor_instance_skips_a_hidden_instance_and_a_hidden_parent():
    """Drive-train isolates one cluster per view: a hidden instance draws no
    edge to anchor on, nor does a shown part under a hidden sub-assembly."""
    assert _chosen(_instances("dt-cone-gear-1", "dt-cone-gear-2", hidden={"dt-cone-gear-1"})) == "dt-cone-gear-2"
    parent = _FakeDrawingComponent("sub-1", children=_instances("dt-cone-gear-1"), visible=False)
    assert _chosen([parent, *_instances("dt-cone-gear-3")]) == "dt-cone-gear-3"


def test_pinned_anchor_instance_must_be_shown():
    pinned = _drawing_balloons.BalloonAnchor(point_mm=(0.0, 0.0, 0.0), instance="dt-cone-gear-4")
    assert _chosen(_instances("dt-cone-gear-1", "dt-cone-gear-4"), anchor=pinned) == "dt-cone-gear-4"
    with pytest.raises(RuntimeError):
        _chosen(_instances("dt-cone-gear-1", "dt-cone-gear-4", hidden={"dt-cone-gear-4"}), anchor=pinned)


class _AnchorEdge:
    """A drawing-view edge: ``IEntity.GetComponent`` names its owner by path.

    Its curve runs straight between ``ends`` over parameters 0..1 unless
    ``at`` maps a parameter to a point (an arc). ``landing`` is the sheet
    point where SolidWorks ends a leader on the edge when no selection point
    says where: by default its start."""

    def __init__(self, owner, ends=(0.001, 0.002, 0.003, 0.004, 0.005, 0.006), at=None, landing=None):
        self._owner = SimpleNamespace(Name2=owner)
        self._ends = ends
        self._at = at or (
            lambda t: tuple(s + t * (e - s) for s, e in zip(ends[0:3], ends[3:6]))
        )
        self.landing = landing or (ends[0], ends[1])

    def GetComponent(self):
        return self._owner

    def GetCurve(self):
        return SimpleNamespace(Evaluate2=lambda t, _derivatives: self._at(t))

    def GetCurveParams2(self):
        return (*self._ends, 0.0, 1.0, 0.0, 0.0, 0.0)

    def Select4(self, _append, _data):
        self.sheet.selected = [self]
        self.sheet.selection_point = None
        return True


# A portrait sheet fit to the window, and a pick aperture of a few pixels.
_FIT_SPAN_M = 0.28
_PICK_PX = 8


class _AnchorSheet:
    """A drawing whose hit test returns the edge drawn at a sheet point.

    ``near`` maps a sheet point where nothing of interest is drawn to (distance,
    edge) of the closest drawn edge. Like SolidWorks' pick, the hit test takes
    it when it lies inside an aperture of :data:`_PICK_PX` pixels, so the
    aperture in sheet metres depends on the zoom and on ``window_px``, the
    graphics area's height. ``attach(edge)`` is what an inserted balloon
    reports through ``GetAttachedEntities3`` / ``GetAttachedEntityTypes``: by
    default the selected edge, typed swSelEDGES. Its leader ends at the
    selection point (a hit test's pick, or ``SetSelectionPoint2``'s), else at
    the edge's own ``landing``; ``honours_point=False`` always takes the
    latter. ``ink_after_redraw`` maps sheet points to edges the hit test
    finds only after ``GraphicsRedraw2`` (a seat that picked a window that
    had not drawn the zoom, #1667)."""

    def __init__(
        self,
        edges_at,
        attach=lambda edge: ((edge,), (1,)),
        near=None,
        window_px=640,
        honours_point=True,
        ink_after_redraw=None,
    ):
        self.edges_at = edges_at
        self.attach = attach
        self.near = near or {}
        self.window_px = window_px
        self.honours_point = honours_point
        self.ink_after_redraw = ink_after_redraw or {}
        self.redraws = 0
        self.span = _FIT_SPAN_M
        self.selected = []
        self.selection_point = None
        self.hits = []
        self.balloons = []
        for edge in (
            *edges_at.values(),
            *self.ink_after_redraw.values(),
            *(edge for _d, edge in self.near.values()),
        ):
            edge.sheet = self

        def set_point(index, _mark, x, y, _z):
            assert index == len(self.selected) == 1, "the point belongs to the one selected edge"
            self.selection_point = (x, y)
            return True

        manager = SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(),
            GetSelectedObjectCount2=lambda _mark: len(self.selected),
            GetSelectedObject6=lambda index, _mark: self.selected[index - 1],
            SetSelectionPoint2=set_point,
        )
        self.SelectionManager = manager
        self.Extension = SimpleNamespace(
            SelectByID2=self._select,
            CreateBalloonOptions=lambda: SimpleNamespace(),
            InsertBOMBalloon2=self._insert,
        )

    def ViewZoomTo2(self, x0, y0, _z0, x1, y1, _z1):
        self.span = max(x1 - x0, y1 - y0)

    def ViewZoomtofit2(self):
        self.span = _FIT_SPAN_M

    def GraphicsRedraw2(self):
        self.redraws += 1
        self.edges_at = {**self.edges_at, **self.ink_after_redraw}

    def _select(self, _name, kind, x, y, _z, _append, _mark, _callout, _option):
        assert kind == "EDGE"
        key = (round(x, 9), round(y, 9))
        self.hits.append(key)
        edge = self.edges_at.get(key)
        if edge is None and key in self.near:
            distance, closest = self.near[key]
            if distance <= _PICK_PX * self.span / self.window_px:
                edge = closest
        self.selected = [] if edge is None else ["the view", edge]
        self.selection_point = None if edge is None else (x, y)
        return edge is not None

    def _insert(self, _options):
        assert self.span == _FIT_SPAN_M, "balloons go in under the fit-to-sheet zoom"
        edge = self.selected[-1]
        entities, kinds = self.attach(edge)
        end = self.selection_point if self.honours_point and self.selection_point else edge.landing
        item = str(len(self.balloons) + 1)
        annotation = SimpleNamespace(
            GetAttachedEntities3=lambda: entities,
            GetAttachedEntityTypes=lambda: kinds,
            GetLeaderCount=lambda: 1,
            IsDangling=lambda: False,
            GetLeaderPointsAtIndex=lambda _index: (0.3, 0.3, 0.0, note.end[0], note.end[1], 0.0),
        )
        note = SimpleNamespace(item=item, GetAnnotation=lambda: annotation, end=end)
        self.balloons.append(note)
        return note

    def ClearSelection2(self, _all):
        self.selected = []
        self.selection_point = None

    def ActivateView(self, _name):
        return True


class _ExplodedModel:
    """The referenced assembly as a farm probe read it (2026-09-28) once
    ``Default`` and ``Default Simplified`` each own an explode: the ACTIVE
    configuration reads zero steps until its named explode is shown on the
    model, and a NON-active one reads every step but no step component
    (``GetComponent`` is None; ``GetComponentName`` is the ``Name2``)."""

    ACTIVE = "Default"

    def __init__(self, steps, instances, *, referenced, shown_only):
        self.referenced = referenced
        self.shown_only = shown_only
        self.shown = []
        self.exploded = False
        members = self.referenced != self.ACTIVE
        self.steps = [
            SimpleNamespace(
                Name=f"step {index}",
                GetComponentXform=lambda t=t: (1, 0, 0, 0, 1, 0, 0, 0, 1, *t, 1, 0, 0, 0),
                GetNumOfComponents=lambda names=names: len(names),
                GetComponent=lambda member, names=names: (
                    None if members else SimpleNamespace(Name2=names[member])
                ),
                GetComponentName=lambda member, names=names: names[member],
            )
            for index, (t, names) in enumerate(steps)
        ]
        root = SimpleNamespace(GetChildren=lambda: _model_tree(instances))
        self.configuration = SimpleNamespace(
            Name=referenced,
            GetNumberOfExplodeSteps=self._count,
            GetExplodeStep=lambda index: self.steps[index],
            GetRootComponent3=lambda resolve: root if resolve else None,
        )
        self.ConfigurationManager = SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name=self.ACTIVE)
        )

    def _count(self):
        if self.shown_only and not self.shown:
            return 0
        return len(self.steps)

    def GetConfigurationByName(self, name):
        return self.configuration if name == self.referenced else None

    def GetExplodedViewNames2(self, name):
        return (f"EXPLODED {name}",)

    def ShowExploded2(self, show, name):
        self.shown.append((show, name))
        self.exploded = show
        return True


def _model_tree(paths):
    """Model components for instance ``paths``: each sub-assembly segment is
    a parent whose ``Name2`` is its own path, as ``IComponent2`` reads."""
    nodes: dict[str, SimpleNamespace] = {}
    top = []
    for path in paths:
        parts = path.split("/")
        for depth in range(len(parts)):
            key = "/".join(parts[: depth + 1])
            if key not in nodes:
                node = SimpleNamespace(Name2=key, children=[])
                node.GetChildren = lambda node=node: tuple(node.children)
                nodes[key] = node
                if depth:
                    nodes["/".join(parts[:depth])].children.append(node)
                else:
                    top.append(node)
    return tuple(top)


def _exploded_view(
    children, steps, visible=None, *, referenced="Default", shown_only=False, instances=None
):
    """A view shown exploded; ``steps`` are (translation, moved component paths).

    ``visible`` maps an instance path to the edges ``GetVisibleEntities2``
    lists for it; ``SelectEntity`` selects one on its sheet with no selection
    point. ``referenced`` is the configuration the view shows (the model's active one
    is ``Default``); ``instances`` are that configuration's component paths
    (default: the view's leaves). No steps means a collapsed view."""
    root = _FakeDrawingComponent("dt-drive-train-8", children=children)
    model = _ExplodedModel(
        steps,
        instances if instances is not None else [child.Component.Name2 for child in children],
        referenced=referenced,
        shown_only=shown_only,
    )
    listed = visible or {}
    view = SimpleNamespace(
        RootDrawingComponent2=lambda _resolve: root,
        IsExploded=lambda: bool(steps),
        ReferencedConfiguration=referenced,
        ReferencedDocument=model,
        GetName2=lambda: "Drawing View9",
        UpdateViewDisplayGeometry=lambda: True,
        GetVisibleEntityCount2=lambda component, kind: len(listed.get(component.Name2, ())),
        GetVisibleEntities2=lambda component, kind: tuple(listed.get(component.Name2, ())),
    )

    def select_entity(entity, _append):
        entity.sheet.selected = [entity]
        entity.sheet.selection_point = None
        return True

    view.SelectEntity = select_entity
    return view


def _body(points):
    """``IBody2`` whose ``GetExtremePoint`` returns the first of ``points``
    farthest along the direction: a tie falls to list order, the stand-in for
    whatever order a real body would break it in."""
    vertices = [tuple(point) for point in points]

    def extreme(x, y, z):
        if not vertices:
            return (False, 0.0, 0.0, 0.0)
        return (True, *max(vertices, key=lambda p: p[0] * x + p[1] * y + p[2] * z))

    return SimpleNamespace(GetExtremePoint=extreme)


def _balloon(monkeypatch, sheet, view, anchors, items=(("dt-cone-gear", "1"),)):
    """Run the real balloon path with the sheet projection = model (x, y).

    A pick miss's screenshots are recorded on ``sheet.screens`` as (label,
    zoom span at the capture) instead of taken, the final miss's capture
    writes no file, and the span attributes land on ``sheet.span_attrs``."""
    projected = []

    def project(_adapter, _view, points, *, label, names=None):
        projected.append((tuple(points), tuple(names or ())))
        return [(round(p[0], 9), round(p[1], 9)) for p in points]

    def screens(adapter, label):
        sheet.screens.append((label, adapter.currentModel.span))
        return {"desktop_png": f"failures/{label}/desktop.png", "capture_ms": 0}

    events = []
    sheet.screens = []
    sheet.span_attrs = {}
    monkeypatch.setattr(_drawing_balloons, "model_points_in_view", project)
    monkeypatch.setattr(_drawing_balloons, "_spread_balloons", lambda *a, **k: None)
    monkeypatch.setattr(_drawing_balloons, "rebuild_drawing", lambda *a, **k: None)
    monkeypatch.setattr(
        _drawing_balloons, "_balloon_item_number", lambda _adapter, note, label: note.item
    )
    monkeypatch.setattr(_drawing_balloons, "_span_scan_attrs", sheet.span_attrs.update)
    monkeypatch.setattr(_seat_forensics, "capture_pick_screens", screens)
    monkeypatch.setattr(_seat_forensics, "_write_artefacts", lambda steps: {})
    monkeypatch.setattr(
        _telemetry, "event", lambda name, **kw: events.append((name, kw))
    )
    landings = _drawing_balloons.add_component_bom_balloons(
        _FakeAdapter(sheet), view, items=items, anchors=anchors, label="t"
    )
    sheet.landings = landings
    balloons = [landing.note for landing in landings]
    return balloons, projected, [kw for name, kw in events if name == "drawing.balloon_anchor"]


def test_frozen_anchor_selects_at_its_exploded_projection_and_records_it(monkeypatch):
    """Component transform, THEN the explode: a drawing view shows the model
    exploded while every component transform still reads the collapsed pose
    (farm probe: projecting without the explode hit the tube under each cap)."""
    children = _instances("dt-cone-gear-2", "dt-cone-gear-1")
    children[1].Component.Transform2.ArrayData = (1, 0, 0, 0, 1, 0, 0, 0, 1, 0.1, 0.2, 0.0, 1, 0, 0, 0)
    view = _exploded_view(children, [((0.0, 0.25, 0.0), ["dt-cone-gear-1"]), ((0.03, 0.0, 0.0), ["dt-cone-gear-1"])])
    # (1, 2) mm local -> +(100, 200) mm placed -> +(30, 250) mm exploded.
    sheet = _AnchorSheet({(0.131, 0.452): _AnchorEdge("dt-cone-gear-1")})
    balloons, projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR})
    assert len(balloons) == 1 and sheet.hits == [(0.131, 0.452)]
    assert projected[0][1] == ("dt-cone-gear",)
    assert anchors == [
        {
            "stem": "dt-cone-gear",
            "instance": "dt-cone-gear-1",
            "method": "frozen",
            "point_mm": "1.000,2.000,3.000",
            "sheet_mm": "131.000,452.000",
            "tried": 1,
            "picks": "hit",
        }
    ]
    assert sheet.redraws == 0 and sheet.screens == []


def test_frozen_anchor_that_hits_nothing_fails_after_redrawn_picks(monkeypatch):
    """Every pick misses: two more after a forced redraw, each miss
    screenshotted while still zoomed on the point, then the sheet fails."""
    view = _exploded_view(_instances("dt-cone-gear-1"), [])
    sheet = _AnchorSheet({})
    with pytest.raises(
        RuntimeError,
        match="cone-gear frozen balloon anchor .* selects no edge .* in 3 picks, 2 after a forced redraw",
    ):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR})
    assert sheet.balloons == []
    assert sheet.hits == [(0.001, 0.002)] * 3 and sheet.redraws == 2
    zoom = 2 * _drawing_scan._HIT_ZOOM_HALF
    assert sheet.screens == [
        (f"dt-cone-gear-frozen-anchor-pick{pick}", pytest.approx(zoom))
        for pick in (1, 2, 3)
    ]
    assert [sheet.span_attrs[f"pick{pick}"] for pick in (1, 2, 3)] == ["miss"] * 3
    assert sheet.span_attrs["pick3_desktop_png"] == (
        "failures/dt-cone-gear-frozen-anchor-pick3/desktop.png"
    )


def test_frozen_anchor_miss_healed_by_a_redraw_balloons_its_own_ink(monkeypatch):
    """A miss the redrawn pick heals is still screenshotted, and the span and
    event say which pick hit (#1667)."""
    view = _exploded_view(_instances("dt-cone-gear-1"), [])
    sheet = _AnchorSheet(
        {}, ink_after_redraw={(0.001, 0.002): _AnchorEdge("dt-cone-gear-1")}
    )
    balloons, _projected, anchors = _balloon(
        monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR}
    )
    assert len(balloons) == 1 and sheet.redraws == 1
    assert [label for label, _span in sheet.screens] == [
        "dt-cone-gear-frozen-anchor-pick1"
    ]
    assert anchors[0]["method"] == "frozen" and anchors[0]["picks"] == "miss,hit"
    assert (sheet.span_attrs["pick1"], sheet.span_attrs["pick2"]) == ("miss", "hit")
    assert sheet.span_attrs["pick1_desktop_png"] == (
        "failures/dt-cone-gear-frozen-anchor-pick1/desktop.png"
    )
    assert "pick2_desktop_png" not in sheet.span_attrs


def test_frozen_anchor_on_another_components_edge_fails(monkeypatch):
    """A part moved in front of the anchor must fail the sheet, not balloon the
    part in front with the wrong item's number."""
    view = _exploded_view(_instances("dt-cone-gear-1"), [])
    sheet = _AnchorSheet({(0.001, 0.002): _AnchorEdge("dt-crank-pinion-1")})
    with pytest.raises(RuntimeError):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR})
    assert sheet.balloons == []


def test_a_family_without_a_frozen_anchor_fails_before_any_balloon(monkeypatch):
    items = (("dt-cone-gear", "1"), ("dt-crank-pinion", "2"))
    view = _exploded_view(_instances("dt-cone-gear-1", "dt-crank-pinion-1"), [])
    anchors = {
        "dt-cone-gear": _ANCHOR,
        "dt-crank-pinion": _drawing_balloons.BalloonAnchor(point_mm=(4.0, 5.0, 6.0)),
    }

    def ready_sheet():
        return _AnchorSheet(
            {
                (0.001, 0.002): _AnchorEdge("dt-cone-gear-1"),
                (0.004, 0.005): _AnchorEdge(
                    "dt-crank-pinion-1", ends=(0.004, 0.005, 0.006, 0.007, 0.008, 0.009)
                ),
            }
        )

    valid = ready_sheet()
    _balloon(monkeypatch, valid, view, anchors, items=items)
    assert [
        (landing.instance, landing.sheet_xy) for landing in valid.landings
    ] == [
        ("dt-cone-gear-1", (0.001, 0.002)),
        ("dt-crank-pinion-1", (0.004, 0.005)),
    ]

    del anchors["dt-crank-pinion"]
    sheet = ready_sheet()
    with pytest.raises(ValueError):
        _balloon(monkeypatch, sheet, view, anchors, items=items)
    assert sheet.hits == [] and sheet.balloons == []


def test_a_rotating_explode_step_is_refused_not_summed(monkeypatch):
    view = _exploded_view(_instances("dt-cone-gear-1"), [((0.0, 0.1, 0.0), ["dt-cone-gear-1"])])
    configuration = view.ReferencedDocument.GetConfigurationByName("Default")
    step = configuration.GetExplodeStep(0)
    step.GetComponentXform = lambda: (0, -1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
    with pytest.raises(RuntimeError, match="not a pure translation"):
        _balloon(monkeypatch, _AnchorSheet({}), view, {"dt-cone-gear": _ANCHOR})


def _pair_of_subassemblies(**view_kwargs):
    """Two sub-assemblies, each holding a ``cone-gear-1``."""
    return _instances("sub-1/dt-cone-gear-1", "sub-2/dt-cone-gear-1", **view_kwargs)


_SUB_2 = _drawing_balloons.BalloonAnchor(point_mm=(1.0, 2.0, 3.0), instance="sub-2/dt-cone-gear-1")


def test_anchor_instance_is_the_full_path_not_its_last_segment():
    assert _chosen(_pair_of_subassemblies()) == "sub-1/dt-cone-gear-1"
    assert _chosen(_pair_of_subassemblies(), anchor=_SUB_2) == "sub-2/dt-cone-gear-1"


def test_frozen_hit_on_the_same_named_part_of_another_subassembly_fails(monkeypatch):
    view = _exploded_view(_pair_of_subassemblies(), [])
    sheet = _AnchorSheet({(0.001, 0.002): _AnchorEdge("sub-1/dt-cone-gear-1")})
    with pytest.raises(RuntimeError):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _SUB_2})
    assert sheet.balloons == []


_SUBASSEMBLY_EXPLODE = [((0.0, 0.25, 0.0), ["sub-1/dt-cone-gear-1"]), ((0.03, 0.0, 0.0), ["sub-2"])]


@pytest.mark.parametrize(
    ("referenced", "shown_only", "shown"),
    [
        ("Default", False, []),
        ("Default", True, [(True, "EXPLODED Default"), (False, "EXPLODED Default")]),
        ("Default Simplified", False, []),
    ],
    ids=["active", "active-reads-steps-once-shown", "non-active-reads-no-components"],
)
def test_explode_offsets_are_keyed_by_full_path_and_include_the_subassembly(
    monkeypatch, referenced, shown_only, shown
):
    """sub-1's cone-gear-1 moves +250 mm Y; sub-2 moves +30 mm X as a whole.
    Keyed by the last segment, sub-2's gear would take sub-1's move too.
    Whichever way the referenced configuration gives its steps up, the
    balloon lands on the exploded part, and the model is left collapsed."""
    view = _exploded_view(
        _pair_of_subassemblies(), _SUBASSEMBLY_EXPLODE, referenced=referenced, shown_only=shown_only
    )
    sheet = _AnchorSheet({(0.031, 0.002): _AnchorEdge("sub-2/dt-cone-gear-1")})
    balloons, _projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _SUB_2})
    assert len(balloons) == 1 and sheet.hits == [(0.031, 0.002)]
    assert anchors[0]["instance"] == "sub-2/dt-cone-gear-1"
    assert view.ReferencedDocument.shown == shown
    assert not view.ReferencedDocument.exploded


def test_a_non_active_explode_member_naming_no_instance_of_its_configuration_fails():
    """Resolution by name is exact: ``sub-2`` is not an instance of this
    configuration, so its explode cannot be placed and the view is refused."""
    view = _exploded_view(
        _pair_of_subassemblies(),
        _SUBASSEMBLY_EXPLODE,
        referenced="Default Simplified",
        instances=["sub-1/dt-cone-gear-1"],
    )
    with pytest.raises(
        RuntimeError, match=r"moves 'sub-2', which .* names no instance of 'Default Simplified'"
    ):
        _drawing_balloons._view_explode_offsets(_FakeAdapter(None), view, label="t")


@pytest.mark.parametrize(
    ("referenced", "why"),
    [
        ("Default", r"'Default' reads no explode steps"),
        ("Default Simplified", r"reads no explode steps and is not the model's active"),
    ],
)
def test_an_exploded_view_whose_configuration_reads_no_steps_is_refused(referenced, why):
    """Zero offsets would project every anchor at the collapsed pose."""
    view = _exploded_view(_pair_of_subassemblies(), _SUBASSEMBLY_EXPLODE, referenced=referenced)
    view.ReferencedDocument.configuration.GetNumberOfExplodeSteps = lambda: 0
    with pytest.raises(RuntimeError, match=why):
        _drawing_balloons._view_explode_offsets(_FakeAdapter(None), view, label="t")


@pytest.mark.parametrize(
    "attach",
    [
        lambda edge: ((edge, edge), (1, 1)),
        lambda edge: ((edge,), (46,)),
        lambda edge: ((None,), (0,)),
        lambda edge: ((_AnchorEdge("sub-1/dt-cone-gear-1"),), (1,)),
    ],
    ids=["two-entities", "silhouette", "dangling", "same-named-other-instance"],
)
def test_balloon_must_attach_to_exactly_one_edge_of_the_exact_instance(monkeypatch, attach):
    view = _exploded_view(_pair_of_subassemblies(), [])
    sheet = _AnchorSheet({(0.001, 0.002): _AnchorEdge("sub-2/dt-cone-gear-1")}, attach=attach)
    with pytest.raises(RuntimeError):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _SUB_2})


_WALK = _drawing_balloons.BalloonAnchor()

# An L-shaped outline's corners.
_L_POINTS = ((0.0, 0.0, 0.0), (0.004, 0.0, 0.0), (0.004, 0.006, 0.0), (0.0, 0.006, 0.0))


def _comb():
    """A 12-tooth comb extruded 3 mm: 96 corners, most sharing a face with
    another along x, y or z, as a gear or a screw thread does."""
    return [
        (tooth * 0.002 + dx, dy, z)
        for tooth in range(12)
        for dx, dy in ((0.0, 0.0), (0.0, 0.004), (0.001, 0.004), (0.001, 0.0))
        for z in (0.0, 0.003)
    ]


def test_walk_tries_the_same_points_however_the_body_breaks_ties(monkeypatch):
    """A body has faces square to x, y and z and far more of them than a walk
    can read: a probe direction normal to one would leave which of its
    corners comes back to the kernel. No probe direction is, so the comb
    anchors identically whatever order its corners are held in."""
    import random

    def run(points, sheet):
        view = _exploded_view(_instances("dt-cone-gear-1", bodies={"dt-cone-gear-1": _body(points)}), [])
        return _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})

    probe = _AnchorSheet({})
    with pytest.raises(RuntimeError, match="no verifiably visible edge"):
        run(_comb(), probe)
    claimed = probe.hits[2]
    shuffle = random.Random(865)
    runs = []
    for _ in range(12):
        points = _comb()
        shuffle.shuffle(points)
        sheet = _AnchorSheet({claimed: _AnchorEdge("dt-cone-gear-1")})
        balloons, _projected, anchors = run(points, sheet)
        assert len(balloons) == 1
        runs.append((tuple(sheet.hits), anchors[0]))
    assert all(run_ == runs[0] for run_ in runs)
    assert runs[0][0] == tuple(probe.hits[:3])
    assert (runs[0][1]["method"], runs[0][1]["tried"]) == ("walk", 3)


def test_walk_anchors_identically_on_a_640_and_an_820_pixel_seat_window(monkeypatch):
    """Fit to sheet, a few pixels of pick aperture are millimetres of sheet,
    more on a small window: the first walk point, whose own edge is not drawn
    there, borrows the gear's edge 3 mm away on a 640 px window but not on an
    820 px one (swmaker000008 against swmaker000004). Zoomed onto each point,
    both seats reject it and anchor on the next, drawn point."""

    def run(sheet):
        view = _exploded_view(
            _instances("dt-cone-gear-1", bodies={"dt-cone-gear-1": _body(_L_POINTS)}), []
        )
        return _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})

    probe = _AnchorSheet({})
    with pytest.raises(RuntimeError, match="no verifiably visible edge"):
        run(probe)
    first, second = probe.hits[:2]
    anchors = []
    for window_px in (640, 820):
        sheet = _AnchorSheet(
            {second: _AnchorEdge("dt-cone-gear-1")},
            near={first: (0.003, _AnchorEdge("dt-cone-gear-1"))},
            window_px=window_px,
        )
        _balloons, _projected, placed = run(sheet)
        assert sheet.span == _FIT_SPAN_M
        anchors.append(placed[0])
    assert anchors[0] == anchors[1]
    assert (anchors[0]["method"], anchors[0]["tried"]) == ("walk", 2)


class _ZoomWindow:
    """A drawing window whose zoom calls can fail after moving the view."""

    def __init__(self, fault: str | None):
        self.fault = fault
        self.span: float | None = None  # None: fit to the sheet

    def ViewZoomTo2(self, x1, _y1, _z1, x2, _y2, _z2):  # noqa: N802
        self.span = x2 - x1
        if self.fault == "zoom":
            raise RuntimeError("ViewZoomTo2 moved the view, then failed")

    def ViewZoomtofit2(self):  # noqa: N802
        if self.fault == "body-then-restore":
            raise RuntimeError("ViewZoomtofit2 failed")
        self.span = None


@pytest.mark.parametrize(
    ("fault", "raised"),
    [
        ("zoom", "ViewZoomTo2 moved the view"),
        ("body", "the pick failed"),
        ("body-then-restore", "the pick failed"),
    ],
)
def test_zoomed_on_restores_fit_and_raises_the_first_failure(fault, raised):
    """ViewZoomTo2 can change the view and then raise; the body can raise
    zoomed. The window goes back to fit either way, and when that restore
    fails too, the failure raised is still the first one, noting the second."""
    window = _ZoomWindow(fault)
    with pytest.raises(RuntimeError, match=raised) as failure:
        with _drawing_scan._zoomed_on(SimpleNamespace(currentModel=window), (0.1, 0.2), 0.012):
            raise RuntimeError("the pick failed")
    notes = getattr(failure.value, "__notes__", [])
    if fault == "body-then-restore":
        assert window.span == pytest.approx(0.024)
        assert notes == ["restoring the fit zoom also failed: RuntimeError('ViewZoomtofit2 failed')"]
    else:
        assert window.span is None and notes == []


def test_walk_hit_on_the_same_named_part_of_another_subassembly_is_not_claimed(monkeypatch):
    """sub-2's gear sits in front of sub-1's first walk point: that hit is
    sub-2's, not sub-1's, however alike their last path segments read, so
    sub-1 anchors on its next point."""
    bodies = {
        "sub-1/dt-cone-gear-1": _body([(0.0, 0.01, 0.0), (0.0, -0.01, 0.0)]),
        "sub-2/dt-cone-gear-1": _body([(0.0, 0.02, 0.0)]),
    }
    view = _exploded_view(_pair_of_subassemblies(bodies=bodies), [])
    sheet = _AnchorSheet(
        {
            (0.0, -0.01): _AnchorEdge("sub-2/dt-cone-gear-1"),
            (0.0, 0.01): _AnchorEdge("sub-1/dt-cone-gear-1"),
        }
    )
    _balloons, _projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})
    assert (anchors[0]["instance"], anchors[0]["sheet_mm"]) == ("sub-1/dt-cone-gear-1", "0.000,10.000")
    assert sheet.hits == [(0.0, -0.01), (0.0, 0.01)]


# Measured on run 20260928T194845954Z-44f5de00de924735961d14f4aad40337: where
# the walk's zoomed hit test claimed the part (drawing.balloon_anchor
# sheet_mm) and where SolidWorks ended the balloon's leader, the edge
# selected by entity alone (drawing.balloon_attachment attach_mm). Sheet m.
_MEASURED_LANDINGS = {
    # Frame sheet 2, item 8: 0.46 mm off a #4-40 head drawn 0.35 mm across
    # at 1:8, into the nameplate engraving.
    "fr-frame-8-fillister-screw": ((0.161847, 0.139315), (0.161438, 0.139110)),
    # Drive-train sheet 3, item 3: 10.3 mm round the thrust washer's rim,
    # into the cylinder gear's teeth.
    "dt-3-cylinder-end-disc": ((0.259833, 0.190494), (0.254346, 0.181734)),
}


def _walked_to(hit, landing, **sheet_kwargs):
    """dt-cone-gear-1 walks to ``hit``, the one point the hit test gives back
    to it; selected by entity alone, its edge ends a leader at ``landing``."""
    view = _exploded_view(
        _instances("dt-cone-gear-1", bodies={"dt-cone-gear-1": _body([(*hit, 0.0)])}), []
    )
    sheet = _AnchorSheet({hit: _AnchorEdge("dt-cone-gear-1", landing=landing)}, **sheet_kwargs)
    return view, sheet


@pytest.mark.parametrize("case", sorted(_MEASURED_LANDINGS))
def test_a_walked_balloon_leader_ends_where_the_hit_test_claimed_its_part(monkeypatch, case):
    """The hit test proves the part drawn at one point; elsewhere on the same
    edge a neighbour can be in front. The leader ends at that point, not
    where SolidWorks would put it on the edge."""
    hit, landing = _MEASURED_LANDINGS[case]
    view, sheet = _walked_to(hit, landing)
    balloons, _projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})
    assert [note.end for note in balloons] == [hit]
    assert anchors[0]["sheet_mm"] == f"{hit[0] * 1000:.3f},{hit[1] * 1000:.3f}"


@pytest.mark.parametrize("case", sorted(_MEASURED_LANDINGS))
def test_a_balloon_leader_that_ends_off_its_claimed_point_fails_the_sheet(monkeypatch, case):
    """A seat that ignores the selection point must not ship the measured
    landing: 0.46 mm is already the neighbouring part at 1:8."""
    hit, landing = _MEASURED_LANDINGS[case]
    view, sheet = _walked_to(hit, landing, honours_point=False)
    with pytest.raises(RuntimeError, match="cone-gear balloon leader attachment moved"):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})


@pytest.mark.parametrize("case", sorted(_MEASURED_LANDINGS))
def test_a_later_rebuild_that_moves_a_landed_leader_fails_the_final_proof(monkeypatch, case):
    """A balloon is proven where it is inserted, and every rebuild after that
    (the next balloons', later sheets', the finalizer's) re-solves it. One a
    later rebuild moves back to where SolidWorks would put it on the edge
    fails the drawing, named; one left in place passes."""
    hit, landing = _MEASURED_LANDINGS[case]
    view, sheet = _walked_to(hit, landing)
    _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})
    adapter = _FakeAdapter(sheet)
    _drawing_balloons.assert_balloon_landings(adapter, sheet.landings)
    sheet.balloons[0].end = landing
    with pytest.raises(
        RuntimeError,
        match=r"1 balloon\(s\) changed after the final rebuild: .*cone-gear balloon leader "
        r"attachment moved",
    ):
        _drawing_balloons.assert_balloon_landings(adapter, sheet.landings)


def _ring_point(t, centre=(0.1, 0.1), radius=0.00495):
    """A point on the crank-pin ring's 4.95 mm loop, whose one edge starts
    and ends at the same point (run 20260928T194845954Z, item 43)."""
    angle = 2.0 * _math.pi * t
    return (centre[0] + radius * _math.cos(angle), centre[1] + radius * _math.sin(angle), 0.0)


def test_a_ring_behind_a_pin_is_ballooned_where_its_listed_edge_is_drawn(monkeypatch):
    """Drive-train sheet 4, item 43: no extreme point of the crank-pin ring
    is claimed, so the fallback takes its listed visible edges. Listed is
    not drawn everywhere: the taper pin's shank crosses the loop where it
    starts, and there SolidWorks ended the leader. Points along each listed
    edge are hit-tested like the walk's, the leader ends on the first one
    the ring claims, and the array's order does not change which."""

    def key(t):
        return tuple(round(v, 9) for v in _ring_point(t)[:2])

    shank = _AnchorEdge("taper-pin-1")
    ring = _AnchorEdge("dt-crank-pin-ring-1", at=_ring_point, landing=key(0.0))
    bore = _AnchorEdge("dt-crank-pin-ring-1", at=lambda t: _ring_point(t, radius=0.002))
    results = []
    for listed in ((ring, bore), (bore, ring)):
        view = _exploded_view(
            _instances("dt-crank-pin-ring-1", bodies={"dt-crank-pin-ring-1": _body([(0.0, 0.05, 0.0)])}),
            [],
            visible={"dt-crank-pin-ring-1": listed},
        )
        sheet = _AnchorSheet({key(0.1): shank, key(0.9): shank, key(0.5): ring})
        balloons, _projected, anchors = _balloon(
            monkeypatch, sheet, view, {"dt-crank-pin-ring": _WALK}, items=(("dt-crank-pin-ring", "1"),)
        )
        assert [note.end for note in balloons] == [key(0.5)]
        assert (anchors[0]["method"], anchors[0]["visible"]) == ("visible-edge", "dt-crank-pin-ring-1=2")
        results.append((tuple(sheet.hits), anchors[0]))
    assert results[0] == results[1]


def test_a_bushing_sharing_its_bores_outline_is_ballooned_on_its_own_listed_edge(monkeypatch):
    """Drive-train sheet 4, item 10: the former tip bushing sat flush in the tip
    block's bore, and none of its 24 walk and listed-edge points hit any edge
    on runs 20260928T202401351Z and 20260928T203306681Z. Where a point of a
    listed rim hits the block's edge the ink is shared: the balloon attaches
    to the bushing's own listed edge, its leader ending at that point. With
    no ink at any point it still attaches to its own listed edge, where
    SolidWorks puts the leader, and never to the block."""

    def key(t):
        return tuple(round(v, 9) for v in _ring_point(t, radius=0.003)[:2])

    rim = _AnchorEdge("flush-part-1", at=lambda t: _ring_point(t, radius=0.003))
    bore = _AnchorEdge("dt-cone-tip-block-1")

    def run(sheet):
        rim.sheet = sheet
        view = _exploded_view(
            _instances("flush-part-1", bodies={"flush-part-1": _body([(0.0, 0.05, 0.0)])}),
            [],
            visible={"flush-part-1": [rim]},
        )
        return _balloon(
            monkeypatch, sheet, view, {"flush-part": _WALK}, items=(("flush-part", "1"),)
        )

    sheet = _AnchorSheet({key(0.3): bore})
    balloons, _projected, anchors = run(sheet)
    assert [note.end for note in balloons] == [key(0.3)]
    assert (anchors[0]["method"], anchors[0]["shared"]) == ("shared-edge", "dt-cone-tip-block-1")
    sheet = _AnchorSheet({})
    balloons, _projected, anchors = run(sheet)
    assert [note.end for note in balloons] == [rim.landing]
    assert anchors[0]["method"] == "listed-edge"
    assert balloons[0].GetAnnotation().GetAttachedEntities3() == (rim,)



@pytest.mark.parametrize(
    "listed",
    [0, _drawing_balloons._VISIBLE_EDGES_PER_INSTANCE + 1],
    ids=["none-listed", "over-the-cap"],
)
def test_walk_without_a_hit_or_a_listed_edge_fails_naming_what_it_tried(monkeypatch, listed):
    """No hit and nothing listed (or too much to fetch) for the first
    instance fails, even though the second's own walk point is drawn and
    lists a drawable edge: letting the second stand in makes a hit result, or
    how many edges a seat lists (lag-screw-1 listed 0 on swmaker000004 and 45
    elsewhere), choose the ballooned instance. The lag screw walked to
    lag-screw-2 that way on every 640 px seat; the instance is now a pin.
    Nor is it "attach to the first walked edge": that edge may be hidden."""
    bodies = {
        "dt-cone-gear-1": _body([(0.0, 0.05, 0.0)]),
        "dt-cone-gear-2": _body([(0.0, 0.06, 0.0)]),
    }
    spare = _AnchorEdge("dt-cone-gear-2")
    view = _exploded_view(
        _instances("dt-cone-gear-1", "dt-cone-gear-2", bodies=bodies),
        [],
        visible={"dt-cone-gear-1": [_AnchorEdge("dt-cone-gear-1")] * listed, "dt-cone-gear-2": [spare]},
    )

    def fetch(_component, _kind):
        raise AssertionError("only the first instance's count is read, and it is not fetched")

    view.GetVisibleEntities2 = fetch
    sheet = _AnchorSheet({(0.0, 0.06): spare})
    with pytest.raises(RuntimeError):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})
    assert sheet.balloons == []
    assert sheet.hits == [(0.0, 0.05)]


def test_coincident_attachments_break_on_the_bom_item_not_arrival_order():
    """The last geometric tie-break can itself tie.

    Overlapping or coaxial components project to ONE attachment point, so
    theta, x and y are all equal and the stable sort quietly re-emits
    AutoBalloon5's arrival order -- the same nondeterminism the sort exists to
    remove, one level down (Codex P2). The BOM item number is the only field
    tied to the component's row rather than to when its balloon was created.
    """
    same = (0.1700, 0.1700)
    two, ten = _FakeNote(*same, item="2"), _FakeNote(*same, item="10")
    forward = dict(zip(("2", "10"), _ring_positions([two, ten])))
    two2, ten2 = _FakeNote(*same, item="2"), _FakeNote(*same, item="10")
    reversed_ = dict(zip(("10", "2"), _ring_positions([ten2, two2])))
    assert forward == reversed_
    assert forward["2"] != forward["10"]


def test_bom_items_order_numerically_not_lexically():
    """ "10" must not sort between "1" and "2" -- a lexical key would reorder a
    ring whose items ran into double digits, which every assembly sheet does."""
    keys = [
        _drawing_balloons._balloon_item_key(_FakeAdapter(None), _FakeNote(0, 0, item=t))
        for t in ("10", "2", "3")
    ]
    assert [key[0] for key in sorted(keys)] == [2, 3, 10]


def test_an_unreadable_balloon_item_sorts_last_instead_of_failing():
    """This key is a TIE-BREAK. Losing it costs placement determinism, not
    correctness, so it must not take the drawing down with it."""

    class _Mute(_FakeNote):
        def GetBomBalloonText(self, _upper):
            raise RuntimeError("no text")

    key = _drawing_balloons._balloon_item_key(_FakeAdapter(None), _Mute(0, 0))
    assert key == (sys.maxsize, "")


def test_a_balloon_whose_item_reads_empty_does_not_tie_every_key():
    """The degenerate case the wrong API would have produced everywhere."""
    blank = _FakeNote(0.17, 0.17, item="")
    real = _FakeNote(0.17, 0.17, item="7")
    adapter = _FakeAdapter(None)
    assert _drawing_balloons._balloon_item_key(adapter, blank) == (sys.maxsize, "")
    assert _drawing_balloons._balloon_item_key(adapter, real) == (7, "7")


def test_drawing_revision_must_match_current_release():
    class Model:
        def __init__(self, revision):
            self.revision = revision

        def GetCustomInfoValue(self, _configuration, name):
            return self.revision if name == "Revision" else "present"

    expected = _config.release_revision()
    _drawing_common.read_required_properties(
        Model(expected),
        ("Revision",),
        required=("Revision",),
    )
    with pytest.raises(RuntimeError, match=r"Revision .* current release"):
        _drawing_common.read_required_properties(
            Model("v1"),
            ("Revision",),
            required=("Revision",),
        )


_ZERO_LINE = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
# cone_pivot_post's MainBodyHt, GetLineAtIndex3 verbatim from the probe leaf
# (diag/cone-pivot-origin-probe fc2212cd6, leaf run 20260926T205141966Z): two
# extension lines, the 15 zero-length records #906 brought, and the two
# dimension-line pieces either side of the text.
MAIN_BODY_HT_LINES = [
    [0.0, 0.0, 0.0, 0.0, 0.1180055, 0.069, -0.0140445, 0.039, 0.069, -0.0140445],
    [0.0, 0.0, 0.0, 0.0, 0.1180055, 0.155, -0.0140445, 0.039, 0.155, -0.0140445],
    *([_ZERO_LINE] * 15),
    [0.0, 0.0, 0.0, 0.0, 0.04, 0.069, -0.0140445, 0.04, 0.1092219, -0.0140445],
    [0.0, 0.0, 0.0, 0.0, 0.04, 0.155, -0.0140445, 0.04, 0.1147781, -0.0140445],
]


def test_a_zero_length_display_line_is_not_ink():
    """The diagnostics collector's line reader: a record whose ends coincide
    draws nothing, so it can't put a dimension's box at the sheet origin
    (the cone_pivot_post integ blocker). Each drop is reported, for
    collect_sheet's span."""
    from _layout_geometry import union_boxes
    from diagnostics.drawing_layout_audit import _display_lines

    class Data:
        def GetLineCount(self):
            return len(MAIN_BODY_HT_LINES)

        def GetLineAtIndex3(self, index):
            return MAIN_BODY_HT_LINES[index]

    dropped: list[int] = []
    segments = _display_lines(object(), Data(), dropped)
    assert len(segments) == 4
    box = union_boxes([segment.box() for segment in segments])
    assert (box.xmin, box.ymin) == pytest.approx((0.039, 0.069))
    assert dropped == list(range(2, 17))

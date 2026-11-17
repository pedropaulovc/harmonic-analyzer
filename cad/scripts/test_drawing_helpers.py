"""SolidWorks-free contracts for the shared drawing helpers.

Balloon placement and ordering, detail crops, linked notes, ray picks, view
display readbacks, GD&T boxes and leader-crossing geometry, exercised on fakes
so a regression is caught without a COM seat.
"""

from __future__ import annotations

import math as _math
import sys
from types import SimpleNamespace

import pytest
import solidworks_mcp.adapters

import _config
import _drawing_balloon_display
import _drawing_balloons
import _drawing_scan
import _drawing_common
import _drawing_edges
import _drawing_layout_audit
import _drawing_detail_crop
import _drawing_annotation_extent
import _drawing_notes
import _drawing_ray_pick
from _drawing_ray_pick import RayPick
from _layout_geometry import Box, DrawableRegion, LeaderSegment, find_leader_leader_crossings
import _drawing_view_display
import _layout_audit
import _telemetry


# ASME B sheet used by every project drawing (meters).
SHEET_W = 0.4318
SHEET_H = 0.2794


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


# --- leader crossings --------------------------------------------------------


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


def _gdt(x, y, kind, label):
    annotation = SimpleNamespace(
        GetPosition=lambda: [x, y, 0.0], GetType=lambda k=kind: k, GetName=lambda n=label: n
    )
    return Box(*_drawing_annotation_extent.gdt_box(_FakeAdapter(None), annotation, label=label))


def test_surface_finish_box_matches_the_measured_symbol_anatomy():
    """An Ra symbol's anchor is its BOTTOM VERTEX and its body draws UP-RIGHT.

    Measured on the shipped sheets by three agents independently. A symmetric box
    is the wrong SHAPE here, not merely the wrong size.
    """
    ax, ay = 0.100, 0.200
    element = _gdt(ax, ay, _drawing_annotation_extent._ANNOT_SFSYM, "Ra")

    assert element.xmin == ax - _drawing_annotation_extent._SF_BOX_LEFT_M
    assert element.xmax == ax + _drawing_annotation_extent._SF_BOX_RIGHT_M
    assert element.ymin == ay  # the vertex IS the bottom edge
    assert element.ymax == ay + _drawing_annotation_extent._SF_BOX_UP_M
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
        GetPosition=lambda: [x, y, 0.0],
        GetType=lambda k=kind: k,
        GetName=lambda n=label: n,
        GetSpecificAnnotation=lambda: spec,
        GetAttachedEntityTypes=lambda: list(attached_to),
    )
    if primitives is None:
        annotation.GetDisplayData = lambda: _display_data(lines, triangles, texts)
    return Box(*_drawing_annotation_extent.gdt_box(_FakeAdapter(None), annotation, label=label))


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
        ax, ay, _drawing_annotation_extent._ANNOT_GTOL, "pos", lines=frame + leader
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
        ax, ay, _drawing_annotation_extent._ANNOT_DATUM, "A", lines=box + leader, triangles=tri
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


def _recorded_events(monkeypatch):
    events = []
    monkeypatch.setattr(
        _telemetry, "event", lambda name, **attrs: events.append((name, attrs))
    )
    return events


def test_a_leadered_frames_igtol_primitives_never_box_it(monkeypatch):
    """pc-858x928b: MHA-DT-19's cylindricity frame printed over "STRAPS" and
    "0.45" while the audit boxed it as the 7 mm placeholder its IGtol
    primitives draw at the leader's far end, 17 mm below the frame. Those
    primitives are no longer read: with no display data the symbol keeps the
    nominal square at its position, and says so in a trace event."""
    events = _recorded_events(monkeypatch)
    el = _gdt_with_geometry(
        0.065, 0.232, _drawing_annotation_extent._ANNOT_GTOL, "cylindricity",
        primitives=_MHA062_CYLINDRICITY_PRIMITIVES,
    )
    placeholder = (0.062808, 0.208112, 0.069883, 0.215112)
    assert (el.xmin, el.ymin, el.xmax, el.ymax) != pytest.approx(placeholder)
    half = _drawing_annotation_extent._NOMINAL_GDT_HALF_M
    assert (el.xmin, el.ymax) == pytest.approx((0.065 - half, 0.232 + half))
    assert [(name, attrs["symbol"]) for name, attrs in events] == [("gdt_box.fallback", "cylindricity")]


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
        0.147, 0.16863, _drawing_annotation_extent._ANNOT_GTOL, "position",
        lines=_m(_KNIFE_FCF_LINES), texts=texts,
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx(
        (0.11463, 0.14063, 0.17641, 0.16863)
    )


def test_a_frame_attached_to_a_dimension_is_boxed_from_its_display_data():
    """Main's review: the dimension-attached fallback is a DATUM rule. A frame
    hung under a dimension reads its display data like any other; the nominal
    square is wrong for an FCF by construction."""
    dimension = _drawing_annotation_extent._SEL_DIMENSION
    frame = _gdt_with_geometry(
        0.147, 0.16863, _drawing_annotation_extent._ANNOT_GTOL, "position",
        lines=_m(_KNIFE_FCF_LINES), attached_to=(dimension,),
    )
    assert (frame.xmin, frame.xmax) == pytest.approx((0.11463, 0.17641))
    datum = _gdt_with_geometry(
        0.115, 0.18737, _drawing_annotation_extent._ANNOT_DATUM, "A",
        lines=_m(_KNIFE_DATUM_LINES), attached_to=(dimension,),
    )
    half = _drawing_annotation_extent._NOMINAL_GDT_HALF_M
    assert (datum.xmin, datum.xmax) == pytest.approx((0.115 - half, 0.115 + half))


def test_a_datum_tag_is_boxed_and_led_from_its_display_data():
    """knife-mount's datum A: box 111.5..118.5 x 187.37..194.37 over an 18 mm
    leader down to its triangle; the leader is the one run left once the box
    is set aside."""
    tri = [((0.1164, 0.16937), (0.1136, 0.16937), (0.1150, 0.17182))]
    el = _gdt_with_geometry(
        0.115, 0.18737, _drawing_annotation_extent._ANNOT_DATUM, "A",
        lines=_m(_KNIFE_DATUM_LINES), triangles=tri,
        texts=[("A", (0.11327, 0.18809), 0.0035)],
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.1115, 0.16937, 0.1185, 0.19437))


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
        0.065, 0.232, _drawing_annotation_extent._ANNOT_GTOL, "cylindricity",
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
        0.245, 0.228, _drawing_annotation_extent._ANNOT_GTOL, "crown", lines=_MHA062_CROWN, texts=texts
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.245, 0.206399, 0.28745, 0.228))
    assert not [name for name, _attrs in events if name == "gdt_box.text_estimated"]


def test_a_run_without_a_reported_width_is_estimated_and_logged(monkeypatch):
    events = _recorded_events(monkeypatch)
    _gdt_with_geometry(
        0.245, 0.228, _drawing_annotation_extent._ANNOT_GTOL, "crown", lines=_MHA062_CROWN,
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
        0.055, 0.229, _drawing_annotation_extent._ANNOT_DATUM, "A", lines=_MHA062_DATUM_A,
        triangles=[((0.0564, 0.2177), (0.0536, 0.2177), (0.055, 0.22015))],
        texts=[("A", (0.053274, 0.229722), 0.0035, 0.003451)],
    )
    assert (el.xmin, el.ymin, el.xmax, el.ymax) == pytest.approx((0.0515, 0.2177, 0.0585, 0.236))


def test_unmeasurable_gdt_falls_back_to_the_nominal_square():
    """No GetSpecificAnnotation (PMI-only) -> keep a coarse box, don't drop it.

    A dropped symbol is worse than a coarse one: it leaves the audit silent on a
    symbol placed clear off the sheet.
    """
    half = _drawing_annotation_extent._NOMINAL_GDT_HALF_M
    for kind in (_drawing_annotation_extent._ANNOT_DATUM, _drawing_annotation_extent._ANNOT_GTOL):
        element = _gdt(0.100, 0.200, kind, "tag")
        assert (element.xmin, element.ymin) == (0.100 - half, 0.200 - half)
        assert (element.xmax, element.ymax) == (0.100 + half, 0.200 + half)


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
    the centre (#866, MHA-DT-00 integ3 leaf, 40 balloons).
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
    ring (MHA-DT-00 integ3). The spread must carry each balloon's anchor offset.
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
            ReferencedConfiguration="Default",
            ComponentReference="",
            Transform2=SimpleNamespace(
                ArrayData=transform or (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
            ),
            GetBody=lambda: body,
            GetBodies3=lambda _kind: ((body,) if body is not None else (), ()),
            GetCorrespondingEntity=lambda entity: entity,
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


def _ray_key(path, point):
    return path, tuple(round(value, 9) for value in point)


class _AnchorSheet:
    """A drawing with geometric probe answers and native balloon readback.

    ``picks`` maps (full instance path, rounded model point) to ``RayPick``.
    The sheet has no screen-pick or zoom API: balloons select an entity and
    set its proven sheet point, or let SolidWorks choose an unproven landing
    on a listed edge. ``attach`` controls the resulting attachment readback.
    """

    def __init__(
        self,
        picks,
        attach=lambda edge: ((edge,), (1,)),
        *,
        honours_point=True,
    ):
        self.picks = picks
        self.attach = attach
        self.honours_point = honours_point
        self.selected = []
        self.selection_point = None
        self.probes = []
        self.probe_batches = []
        self.balloons = []
        for pick in picks.values():
            for edge in pick.edges:
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
            CreateBalloonOptions=lambda: SimpleNamespace(),
            InsertBOMBalloon2=self._insert,
        )

    def _insert(self, _options):
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
        self.ray_hits = {}
        self.ray_calls = []
        self.ray_points = ()
        self.ray_topology = ()
        self.Extension = SimpleNamespace(RayIntersections=self._rays)

    def _rays(self, bodies, starts, vectors, options, radius, offset, precise):
        assert len(bodies) == 1
        self.ray_calls.append((tuple(bodies), tuple(starts), tuple(vectors), options))
        records = self.ray_hits.get(id(bodies[0]), ())
        self.ray_points = tuple(
            value
            for ray, kind, point, _entity in records
            for value in (0.0, float(ray), float(kind), *point, 0.0, 0.0, 1.0)
        )
        self.ray_topology = tuple(entity for _ray, _kind, _point, entity in records)
        return len(records)

    def GetRayIntersectionsPoints(self):
        return self.ray_points

    def GetRayIntersectionsTopology(self):
        return self.ray_topology

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
        listed_edges=listed,
        ModelToViewTransform=SimpleNamespace(
            ArrayData=(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
        ),
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


def _native_ray_caster(monkeypatch, view):
    """Exercise real ray geometry with only SAFEARRAY marshalling replaced."""
    monkeypatch.setattr(_drawing_ray_pick, "dispatch_array", list)
    monkeypatch.setattr(_drawing_ray_pick, "double_array", list)
    adapter = _FakeAdapter(None)
    leaves = _drawing_balloons._view_component_leaves(adapter, view, label="rays")
    offsets = _drawing_balloons._view_explode_offsets(adapter, view, label="rays")
    return _drawing_ray_pick.ViewRayCaster(
        adapter,
        view,
        leaves,
        lambda leaf: _drawing_balloons._leaf_pose(adapter, leaf, offsets, label="rays"),
        label="rays",
    )


def test_ray_origins_are_in_front_of_every_shown_body_in_its_exploded_pose(monkeypatch):
    rotated = _body([(0.0, 0.0, 0.0), (0.004, 0.008, 0.002)])
    middle = _body([(0.0, 0.0, 0.0), (0.4, 0.0, 0.0)])
    front = _body([(0.0, 0.0, 0.0), (0.5, 0.0, 0.0)])
    children = _instances(
        "rotated-1", "multi-body-1", "hidden-1",
        hidden={"hidden-1"},
        bodies={
            "rotated-1": rotated,
            "multi-body-1": middle,
            "hidden-1": _body([(99.0, 99.0, 99.0)]),
        },
    )
    children[0].Component.Transform2.ArrayData = (
        0, 1, 0, -1, 0, 0, 0, 0, 1, 0.1, 0.2, 0.3, 2, 0, 0, 0
    )
    children[1].Component.Transform2.ArrayData = (
        1, 0, 0, 0, 1, 0, 0, 0, 1, -0.2, 0, 0, 1, 0, 0, 0
    )
    reads = []

    def bodies(kind):
        reads.append(kind)
        assert kind == 0, "only solid bodies cast shadows"
        return ((middle, front), (0, 0))

    def hidden_bodies(_kind):
        raise AssertionError("a hidden component casts no shadow")

    children[1].Component.GetBodies3 = bodies
    children[2].Component.GetBodies3 = hidden_bodies
    view = _exploded_view(children, [((0.03, 0.0, 0.0), ["rotated-1"])])
    view.ModelToViewTransform.ArrayData = (
        0, 0, 1, 0, 1, 0, -1, 0, 0, 0, 0, 0, 0.5, 0, 0, 0
    )
    caster = _native_ray_caster(monkeypatch, view)
    picks = caster.probe([
        ("rotated-1", (0.13, 0.2, 0.3)),
        ("multi-body-1", (0.2, 0.0, 0.0)),
    ], label="origins")
    assert caster.normal == (1.0, 0.0, 0.0)
    assert caster.bodies == 3 and reads == [0]
    assert picks == [RayPick((), ()), RayPick((), ())]
    calls = view.ReferencedDocument.ray_calls
    assert len(calls) == 3
    assert {id(call[0][0]) for call in calls} == {id(rotated), id(middle), id(front)}
    for (body,), starts, vectors, options in calls:
        assert options == 7
        assert len(starts) == len(vectors) == 6
        for i, expected_yz in ((0, (0.2, 0.3)), (3, (0.0, 0.0))):
            x, y, z = starts[i:i + 3]
            if body is rotated:
                origin = (0.13 - 2 * y, 0.2 + 2 * x, 0.3 + 2 * z)
                assert vectors[i:i + 3] == pytest.approx((0.0, 1.0, 0.0))
            else:
                origin = (x - 0.2, y, z)
                assert vectors[i:i + 3] == pytest.approx((-1.0, 0.0, 0.0))
            assert origin == pytest.approx((0.31, *expected_yz))


def test_ray_picks_classify_depth_and_map_only_own_instance_edge_topology(monkeypatch):
    paths = ("sub-1/part-1", "sub-2/part-1", "near-cover-1")
    bodies = {path: _body([(0.0, 0.0, 1.0)]) for path in paths}
    children = _instances(*paths, bodies=bodies)
    view = _exploded_view(children, [])
    model = view.ReferencedDocument
    tokens = [object() for _ in range(9)]
    own, face, behind, close, in_front, covered, foreign, far, near = tokens
    model.ray_hits = {
        id(bodies[paths[0]]): [
            (0, 4 | 16, (0.0, 0.0, 0.0), own),
            (1, 1, (0.01, 0.0, 0.0), face),
            (2, 4, (0.02, 0.0, -0.01), behind),
            (3, 4, (0.03, 0.0, 0.000005), close),
            (4, 4, (0.04, 0.0, 0.00002), in_front),
            (5, 4, (0.05, 0.0, 0.0), covered),
        ],
        id(bodies[paths[1]]): [
            (0, 4, (0.0, 0.0, 0.0), foreign),
            (5, 1, (0.05, 0.0, 0.01), far),
            (5, 1, (0.05, 0.0, 0.01), far),
        ],
        id(bodies[paths[2]]): [(5, 1, (0.05, 0.0, 0.03), near)],
    }
    edges = [_AnchorEdge(paths[0]) for _ in range(3)]
    mapped = dict(zip((own, close, covered), edges))
    corresponding = []
    foreign_corresponding = []

    def corresponding_entity(entity):
        corresponding.append(entity)
        return mapped[entity]

    children[0].Component.GetCorrespondingEntity = corresponding_entity
    for child in children[1:]:
        child.Component.GetCorrespondingEntity = foreign_corresponding.append
    caster = _native_ray_caster(monkeypatch, view)
    picks = caster.probe([
        (paths[0].upper(), (i * 0.01, 0.0, 0.0)) for i in range(6)
    ], label="depths")
    assert picks == [
        RayPick((), (edges[0],)),
        RayPick((), ()),
        RayPick((), ()),
        RayPick((), (edges[1],)),
        RayPick((paths[0],), ()),
        RayPick((paths[2], paths[1]), (edges[2],)),
    ]
    assert [pick.visible for pick in picks] == [True, False, False, True, False, False]
    assert corresponding == [own, close, covered]
    assert foreign_corresponding == []
    assert len(model.ray_calls) == 3


@pytest.mark.parametrize("unavailable", ("missing", "raises"))
def test_ray_pick_without_corresponding_topology_is_not_visible(monkeypatch, unavailable):
    body = _body([(0.0, 0.0, 0.0)])
    children = _instances("part-1", bodies={"part-1": body})
    view = _exploded_view(children, [])
    view.ReferencedDocument.ray_hits = {id(body): [(0, 4, (0.0, 0.0, 0.0), object())]}

    def corresponding(_entity):
        if unavailable == "raises":
            raise RuntimeError("the part edge has no instance correspondence")
        return None

    children[0].Component.GetCorrespondingEntity = corresponding
    caster = _native_ray_caster(monkeypatch, view)
    pick, = caster.probe([("part-1", (0.0, 0.0, 0.0))], label="no instance edge")
    assert pick == RayPick((), ())
    assert not pick.visible


@pytest.mark.parametrize(
    ("raw", "topology"),
    [
        ((0.0,) * 8, (object(),)),
        ((0.0,) * 9, ()),
        ((0.0,) * 9, (object(), object())),
    ],
    ids=["partial-hit", "missing-topology", "extra-topology"],
)
def test_ray_pick_refuses_malformed_hit_readback(monkeypatch, raw, topology):
    view = _exploded_view(
        _instances("part-1", bodies={"part-1": _body([(0.0, 0.0, 0.0)])}), []
    )
    caster = _native_ray_caster(monkeypatch, view)
    view.ReferencedDocument.GetRayIntersectionsPoints = lambda: raw
    view.ReferencedDocument.GetRayIntersectionsTopology = lambda: topology
    with pytest.raises(RuntimeError, match="malformed") as failure:
        caster.probe([("part-1", (0.0, 0.0, 0.0))], label="invalid readback")
    assert "part-1" in str(failure.value)


def test_ray_casting_refuses_a_shown_component_without_solid_bodies(monkeypatch):
    view = _exploded_view(_instances("part-1"), [])
    with pytest.raises(RuntimeError, match="part-1.*no solid body"):
        _native_ray_caster(monkeypatch, view)


def _balloon(
    monkeypatch, sheet, view, anchors, items=(("dt-cone-gear", "1"),), *,
    explode_offsets=None,
):
    """Run balloon selection with table-backed model rays and an XY projection."""
    projected = []

    def project(_adapter, _view, points, *, label, names=None):
        projected.append((tuple(points), tuple(names or ())))
        return [(round(p[0], 9), round(p[1], 9)) for p in points]

    class Caster:
        def __init__(self, adapter, _view, leaves, pose, *, label):
            sheet.poses = {leaf.path: pose(leaf) for leaf in leaves if leaf.visible}
            self.bodies = len(sheet.poses)
            self.normal = (0.0, 0.0, 1.0)

        def probe(self, candidates, *, label):
            keys = [_ray_key(path, point) for path, point in candidates]
            sheet.probe_batches.append(tuple(keys))
            sheet.probes.extend(keys)
            return [sheet.picks.get(key, RayPick((), ())) for key in keys]

    for edges in view.listed_edges.values():
        for edge in edges:
            edge.sheet = sheet
    events = []
    sheet.span_attrs = {}
    monkeypatch.setattr(_drawing_balloons, "ViewRayCaster", Caster)
    monkeypatch.setattr(_drawing_balloons, "model_points_in_view", project)
    monkeypatch.setattr(_drawing_balloons, "_spread_balloons", lambda *a, **k: None)
    monkeypatch.setattr(_drawing_balloons, "rebuild_drawing", lambda *a, **k: None)
    monkeypatch.setattr(
        _drawing_balloons, "_balloon_item_number", lambda _adapter, note, label: note.item
    )
    monkeypatch.setattr(_drawing_balloons, "_span_scan_attrs", sheet.span_attrs.update)
    monkeypatch.setattr(
        _telemetry, "event", lambda name, **kw: events.append((name, kw))
    )
    landings = _drawing_balloons.add_component_bom_balloons(
        _FakeAdapter(sheet), view, items=items, anchors=anchors, label="t",
        explode_offsets=explode_offsets,
    )
    sheet.landings = landings
    balloons = [landing.note for landing in landings]
    return balloons, projected, [kw for name, kw in events if name == "drawing.balloon_anchor"]


def test_frozen_anchor_selects_at_its_exploded_projection_and_records_it(monkeypatch):
    """Component transform, THEN the explode: a drawing view shows the model
    exploded while every component transform still reads the collapsed pose
    (farm probe: projecting without the explode hit the tube under each cap)."""
    children = _instances("dt-cone-gear-2", "dt-cone-gear-1")
    children[1].Component.Transform2.ArrayData = (0, 1, 0, -1, 0, 0, 0, 0, 1, 0.1, 0.2, 0.0, 1, 0, 0, 0)
    view = _exploded_view(children, [((0.0, 0.25, 0.0), ["dt-cone-gear-1"]), ((0.03, 0.0, 0.0), ["dt-cone-gear-1"])])
    # Rotate (1, 2, 3) mm to (-2, 1, 3), place, then add the explode.
    key = ("dt-cone-gear-1", (0.128, 0.451, 0.003))
    sheet = _AnchorSheet({key: RayPick((), (_AnchorEdge("dt-cone-gear-1"),))})
    balloons, projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR})
    assert len(balloons) == 1 and sheet.probes == [key]
    assert projected == [(((0.128, 0.451, 0.003),), ("dt-cone-gear frozen",))]
    assert sheet.poses["dt-cone-gear-1"][9:12] == pytest.approx((0.13, 0.45, 0.0))
    assert anchors == [
        {
            "stem": "dt-cone-gear",
            "instance": "dt-cone-gear-1",
            "method": "frozen",
            "point_mm": "1.000,2.000,3.000",
            "sheet_mm": "128.000,451.000",
            "tried": 1,
        }
    ]


@pytest.mark.parametrize("method", ("frozen", "walk"))
@pytest.mark.parametrize("provided", (None, {}, {"sub-2": (0.03, 0.25, 0.04)}))
def test_builder_offsets_bypass_native_reads_and_reach_anchor_projection(
    monkeypatch, method, provided
):
    """An explicit empty mapping is authoritative, not a native-read request."""
    path = "sub-2/dt-cone-gear-1"
    children = _instances(
        path, bodies={path: _body([(0.001, 0.002, 0.003)])}
    )
    view = _exploded_view(children, [])
    native_reads = []
    native_offsets = {"sub-2": (0.06, 0.07, 0.08)}

    def native_read(*args, **kwargs):
        native_reads.append(True)
        assert provided is None, "supplied offsets must bypass the native reader"
        return native_offsets

    monkeypatch.setattr(_drawing_balloons, "_view_explode_offsets", native_read)
    offsets = native_offsets if provided is None else provided
    dx, dy, dz = offsets.get("sub-2", (0.0, 0.0, 0.0))
    expected = (round(0.001 + dx, 9), round(0.002 + dy, 9))
    key = _ray_key(path, (0.001 + dx, 0.002 + dy, 0.003 + dz))
    sheet = _AnchorSheet({key: RayPick((), (_AnchorEdge(path),))})
    anchor = _drawing_balloons.BalloonAnchor(
        point_mm=(1.0, 2.0, 3.0) if method == "frozen" else None,
        instance=path,
    )
    balloons, projected, anchors = _balloon(
        monkeypatch, sheet, view, {"dt-cone-gear": anchor},
        explode_offsets=provided,
    )
    assert native_reads == ([True] if provided is None else [])
    assert len(balloons) == 1
    assert sheet.poses[path][9:12] == pytest.approx((dx, dy, dz))
    assert projected[0][0][0] == pytest.approx(
        (0.001 + dx, 0.002 + dy, 0.003 + dz)
    )
    assert sheet.probes == [key]
    assert anchors[0]["method"] == method
    assert sheet.landings[0].instance == path
    assert sheet.landings[0].sheet_xy == expected
    assert view.ReferencedDocument.shown == []


def test_frozen_anchor_on_another_components_edge_fails(monkeypatch):
    """A part moved in front of the anchor must fail the sheet, not balloon the
    part in front with the wrong item's number."""
    view = _exploded_view(_instances("dt-cone-gear-1"), [])
    key = ("dt-cone-gear-1", (0.001, 0.002, 0.003))
    own_edge = _AnchorEdge("dt-cone-gear-1")
    sheet = _AnchorSheet({key: RayPick(("dt-crank-pinion-1",), (own_edge,))})
    with pytest.raises(RuntimeError, match="covered by dt-crank-pinion-1"):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR})
    assert sheet.balloons == []
    assert sheet.probes == [key]


def test_frozen_anchor_not_on_an_edge_fails_without_falling_back(monkeypatch):
    view = _exploded_view(
        _instances("dt-cone-gear-1"),
        [],
        visible={"dt-cone-gear-1": [_AnchorEdge("dt-cone-gear-1")]},
    )
    sheet = _AnchorSheet({})
    with pytest.raises(RuntimeError, match="not on an edge"):
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _ANCHOR})
    assert sheet.balloons == []
    assert sheet.probes == [("dt-cone-gear-1", (0.001, 0.002, 0.003))]


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
                ("dt-cone-gear-1", (0.001, 0.002, 0.003)): RayPick(
                    (), (_AnchorEdge("dt-cone-gear-1"),)
                ),
                ("dt-crank-pinion-1", (0.004, 0.005, 0.006)): RayPick(
                    (), (_AnchorEdge("dt-crank-pinion-1"),)
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
    assert sheet.probes == [] and sheet.balloons == []


def test_a_family_without_a_shown_instance_fails_before_any_balloon(monkeypatch):
    items = (("dt-cone-gear", "1"), ("dt-crank-pinion", "2"))
    view = _exploded_view(
        _instances("dt-cone-gear-1", "dt-crank-pinion-1", hidden={"dt-crank-pinion-1"}),
        [],
    )
    sheet = _AnchorSheet({
        ("dt-cone-gear-1", (0.001, 0.002, 0.003)): RayPick(
            (), (_AnchorEdge("dt-cone-gear-1"),)
        ),
    })
    with pytest.raises(RuntimeError, match="dt-crank-pinion"):
        _balloon(
            monkeypatch,
            sheet,
            view,
            {"dt-cone-gear": _ANCHOR, "dt-crank-pinion": _ANCHOR},
            items=items,
        )
    assert sheet.probes == [] and sheet.balloons == []


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
    sheet = _AnchorSheet({
        ("sub-2/dt-cone-gear-1", (0.001, 0.002, 0.003)): RayPick(
            ("sub-1/dt-cone-gear-1",), ()
        ),
    })
    with pytest.raises(RuntimeError, match="covered by sub-1/dt-cone-gear-1"):
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
    key = ("sub-2/dt-cone-gear-1", (0.031, 0.002, 0.003))
    sheet = _AnchorSheet({key: RayPick((), (_AnchorEdge("sub-2/dt-cone-gear-1"),))})
    balloons, _projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _SUB_2})
    assert len(balloons) == 1 and sheet.probes == [key]
    assert sheet.poses["sub-1/dt-cone-gear-1"][9:12] == pytest.approx((0.0, 0.25, 0.0))
    assert sheet.poses["sub-2/dt-cone-gear-1"][9:12] == pytest.approx((0.03, 0.0, 0.0))
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
    sheet = _AnchorSheet({
        ("sub-2/dt-cone-gear-1", (0.001, 0.002, 0.003)): RayPick(
            (), (_AnchorEdge("sub-2/dt-cone-gear-1"),)
        ),
    }, attach=attach)
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
    claimed = probe.probes[2]
    shuffle = random.Random(865)
    runs = []
    for _ in range(12):
        points = _comb()
        shuffle.shuffle(points)
        sheet = _AnchorSheet({claimed: RayPick((), (_AnchorEdge("dt-cone-gear-1"),))})
        balloons, _projected, anchors = run(points, sheet)
        assert len(balloons) == 1
        runs.append((tuple(sheet.probes), anchors[0]))
    assert all(run_ == runs[0] for run_ in runs)
    assert runs[0][0] == tuple(probe.probes)
    assert runs[0][1]["method"] == "walk"
    assert runs[0][1]["tried"] == runs[0][1]["extremes"] == len(probe.probes)
    assert runs[0][1]["point_mm"] == ",".join(f"{v * 1000:.3f}" for v in claimed[1])


def test_walk_takes_the_first_visible_ranked_extreme_of_the_first_instance(monkeypatch):
    bodies = {
        "dt-cone-gear-1": _body(_L_POINTS),
        "dt-cone-gear-2": _body([(0.0, 0.05, 0.0)]),
    }
    view = _exploded_view(
        _instances("dt-cone-gear-2", "dt-cone-gear-1", bodies=bodies), []
    )
    edge = _AnchorEdge("dt-cone-gear-1")
    spare = _AnchorEdge("dt-cone-gear-2")
    sheet = _AnchorSheet({
        ("dt-cone-gear-1", (0.0, 0.0, 0.0)): RayPick(("cover-1",), (edge,)),
        ("dt-cone-gear-1", (0.004, 0.006, 0.0)): RayPick((), ()),
        ("dt-cone-gear-1", (0.0, 0.006, 0.0)): RayPick((), (edge,)),
        ("dt-cone-gear-1", (0.004, 0.0, 0.0)): RayPick((), (edge,)),
        ("dt-cone-gear-2", (0.0, 0.05, 0.0)): RayPick((), (spare,)),
    })
    balloons, projected, anchors = _balloon(
        monkeypatch, sheet, view, {"dt-cone-gear": _WALK}
    )
    assert len(balloons) == 1
    assert sheet.probes == [
        ("dt-cone-gear-1", point)
        for point in ((0.0, 0.0, 0.0), (0.004, 0.006, 0.0),
                      (0.0, 0.006, 0.0), (0.004, 0.0, 0.0))
    ]
    assert anchors[0]["instance"] == "dt-cone-gear-1"
    assert anchors[0]["method"] == "walk"
    assert sheet.landings[0].sheet_xy == (0.0, 0.006)
    assert projected == [(((0.0, 0.006, 0.0),), ("dt-cone-gear walk",))]


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
            ("sub-1/dt-cone-gear-1", (0.0, -0.01, 0.0)): RayPick(
                ("sub-2/dt-cone-gear-1",), ()
            ),
            ("sub-1/dt-cone-gear-1", (0.0, 0.01, 0.0)): RayPick(
                (), (_AnchorEdge("sub-1/dt-cone-gear-1"),)
            ),
        }
    )
    _balloons, _projected, anchors = _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})
    assert (anchors[0]["instance"], anchors[0]["sheet_mm"]) == ("sub-1/dt-cone-gear-1", "0.000,10.000")
    assert sheet.probes == [
        ("sub-1/dt-cone-gear-1", (0.0, -0.01, 0.0)),
        ("sub-1/dt-cone-gear-1", (0.0, 0.01, 0.0)),
    ]


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
    """Walk to a geometrically proven point, not the edge's default landing."""
    view = _exploded_view(
        _instances("dt-cone-gear-1", bodies={"dt-cone-gear-1": _body([(*hit, 0.0)])}), []
    )
    sheet = _AnchorSheet({
        _ray_key("dt-cone-gear-1", (*hit, 0.0)): RayPick(
            (), (_AnchorEdge("dt-cone-gear-1", landing=landing),)
        ),
    }, **sheet_kwargs)
    return view, sheet


@pytest.mark.parametrize("case", sorted(_MEASURED_LANDINGS))
def test_a_walked_balloon_leader_ends_at_the_geometrically_proven_point(monkeypatch, case):
    """A neighbour may cover the edge elsewhere: land at the proven point."""
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


@pytest.mark.parametrize("covered_extreme", (True, False), ids=["covered", "off-edge"])
def test_a_ring_behind_a_pin_is_ballooned_where_its_listed_edge_is_drawn(
    monkeypatch, covered_extreme
):
    """Unusable extremes yield to sampled edge points proving the visible rim.

    Hidden or off-edge samples cannot claim the ring, and listed edge order
    does not change its anchor.
    """

    def key(t):
        return tuple(round(v, 9) for v in _ring_point(t)[:2])

    ring = _AnchorEdge("dt-crank-pin-ring-1", at=_ring_point, landing=key(0.0))
    bore = _AnchorEdge("dt-crank-pin-ring-1", at=lambda t: _ring_point(t, radius=0.002))
    results = []
    for listed in ((ring, bore), (bore, ring)):
        view = _exploded_view(
            _instances("dt-crank-pin-ring-1", bodies={"dt-crank-pin-ring-1": _body([(0.0, 0.05, 0.0)])}),
            [],
            visible={"dt-crank-pin-ring-1": listed},
        )
        sheet = _AnchorSheet({
            ("dt-crank-pin-ring-1", (0.0, 0.05, 0.0)): RayPick(
                ("taper-pin-1",) if covered_extreme else (), ()
            ),
            _ray_key("dt-crank-pin-ring-1", _ring_point(0.1)): RayPick(("taper-pin-1",), ()),
            _ray_key("dt-crank-pin-ring-1", _ring_point(0.9)): RayPick(("taper-pin-1",), ()),
            _ray_key("dt-crank-pin-ring-1", _ring_point(0.5)): RayPick((), (ring,)),
        })
        balloons, _projected, anchors = _balloon(
            monkeypatch, sheet, view, {"dt-crank-pin-ring": _WALK}, items=(("dt-crank-pin-ring", "1"),)
        )
        assert [note.end for note in balloons] == [key(0.5)]
        assert (anchors[0]["method"], anchors[0]["visible"]) == ("visible-edge", "dt-crank-pin-ring-1=2")
        assert sheet.landings[0].sheet_xy == key(0.5)
        assert all(path == "dt-crank-pin-ring-1" for path, _point in sheet.probes)
        results.append((tuple(sheet.probes), anchors[0]))
    assert results[0] == results[1]


def test_no_visible_probe_uses_its_own_listed_edge_with_an_unproven_landing(monkeypatch):
    rim = _AnchorEdge("flush-part-1", at=lambda t: _ring_point(t, radius=0.003))
    view = _exploded_view(
        _instances("flush-part-1", bodies={"flush-part-1": _body([(0.0, 0.05, 0.0)])}),
        [],
        visible={"flush-part-1": [rim]},
    )
    sheet = _AnchorSheet({})
    balloons, _projected, anchors = _balloon(
        monkeypatch, sheet, view, {"flush-part": _WALK}, items=(("flush-part", "1"),)
    )
    assert [note.end for note in balloons] == [rim.landing]
    assert anchors[0]["method"] == "listed-edge"
    assert sheet.landings[0].sheet_xy is None
    assert balloons[0].GetAnnotation().GetAttachedEntities3() == (rim,)
    assert len(sheet.probes) == anchors[0]["tried"] == 6
    balloons[0].end = (0.5, 0.5)
    _drawing_balloons.assert_balloon_landings(_FakeAdapter(sheet), sheet.landings)


@pytest.mark.parametrize("honours_point", (True, False))
def test_landed_listed_edge_keeps_its_proven_landing(monkeypatch, honours_point):
    edge = _AnchorEdge("dt-cone-gear-1", landing=(0.02, 0.03))
    sheet = _AnchorSheet({}, honours_point=honours_point)
    edge.sheet = sheet
    view = _exploded_view(_instances("dt-cone-gear-1"), [])
    monkeypatch.setattr(
        _drawing_balloons, "_balloon_item_number", lambda _adapter, note, label: note.item
    )
    choice = _drawing_balloons._AnchorChoice(
        instance="dt-cone-gear-1",
        edge=edge,
        method="landed-listed-edge",
        sheet_xy=(0.001, 0.002),
    )

    def select_directly(*_args):
        raise AssertionError("a listed model edge must be selected through its view")

    edge.Select4 = select_directly

    def insert():
        return _drawing_balloons._create_component_bom_balloon(
            _FakeAdapter(sheet),
            view,
            stem="dt-cone-gear",
            choice=choice,
            expected_item="1",
            label="listed landing",
        )

    if honours_point:
        landing = insert()
        assert landing.sheet_xy == sheet.balloons[0].end == choice.sheet_xy
        assert sheet.balloons[0].GetAnnotation().GetAttachedEntities3() == (edge,)
        sheet.balloons[0].end = edge.landing
        with pytest.raises(RuntimeError, match="attachment moved"):
            _drawing_balloons.assert_balloon_landings(_FakeAdapter(sheet), [landing])
    else:
        with pytest.raises(RuntimeError, match="attachment moved"):
            insert()



@pytest.mark.parametrize(
    "listed",
    [0, _drawing_balloons._VISIBLE_EDGES_PER_INSTANCE + 1],
    ids=["none-listed", "over-the-cap"],
)
def test_walk_without_a_hit_or_a_listed_edge_fails_naming_what_it_tried(monkeypatch, listed):
    """Visibility never moves the balloon to a later family instance."""
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
    sheet = _AnchorSheet({
        ("dt-cone-gear-2", (0.0, 0.06, 0.0)): RayPick((), (spare,)),
    })
    with pytest.raises(RuntimeError) as failure:
        _balloon(monkeypatch, sheet, view, {"dt-cone-gear": _WALK})
    assert "1 body extreme points" in str(failure.value)
    assert f"0 points along its {listed} listed visible edges" in str(failure.value)
    assert "dt-cone-gear-1" in str(failure.value)
    assert sheet.balloons == []
    assert sheet.probes == [("dt-cone-gear-1", (0.0, 0.05, 0.0))]


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

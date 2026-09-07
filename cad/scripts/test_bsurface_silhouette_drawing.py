"""Documented B-surface readback shape; no native success inferred from doubles."""

from copy import deepcopy
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock, call

import pytest

from diagnostics import _silhouette_attachment_witness as witness
from diagnostics import _recipe_view_entity_acceptance as observer
from diagnostics._recipe_view_roles import VIEW_ROLES
from test_view_recipe_acceptance_drawing import bank as bank
from test_silhouette_attachment_witness_drawing import (
    fixture,
    early_bound as early_bound,
)


@pytest.fixture(autouse=True)
def bsurface_binding(monkeypatch):
    monkeypatch.setattr(witness.bsurface, "_early_bound", lambda obj, name: obj)


def bsurface_fixture():
    app, view, entity, face, surface, curve = fixture()
    parameterization = NS(
        UMin=0.0,
        UMax=1.0,
        VMin=0.0,
        VMax=1.0,
        UMinBoundType=13735,
        UMaxBoundType=13735,
        VMinBoundType=13735,
        VMaxBoundType=13735,
        UPropertyNumber=1,
        UProperties=(13737,),
        VPropertyNumber=1,
        VProperties=(13739,),
    )
    data = NS(
        UOrder=3,
        VOrder=2,
        ControlPointColumnCount=4,
        ControlPointRowCount=2,
        ControlPointDimension=3,
        UPeriodicity=False,
        VPeriodicity=False,
        UKnots=(0.0, 0.0, 0.0, 0.5, 1.0, 1.0, 1.0),
        VKnots=(0.0, 0.0, 1.0, 1.0),
        GetControlPoints=Mock(
            side_effect=lambda row, column: (row * 0.001, column * 0.002, -0.0)
        ),
    )
    surface.Identity = lambda: 4006
    surface.Parameterization2 = Mock(return_value=parameterization)
    surface.GetBSurfParams3 = Mock(return_value=(data, True))
    face.GetUVBounds = Mock(return_value=(0.0, 1.0, 0.0, 1.0))
    face.FaceInSurfaceSense = Mock(return_value=False)
    return NS(**locals())


@pytest.fixture
def bsurface():
    return bsurface_fixture()


@pytest.mark.parametrize("dimension", [3, 4])
@pytest.mark.parametrize("periodic", [False, True])
def test_complete_bsurface_is_read_without_changing_silhouette_contract(
    bsurface, dimension, periodic
):
    c = bsurface
    c.data.ControlPointDimension = dimension
    c.data.UPeriodicity = periodic
    c.data.GetControlPoints.side_effect = lambda r, col: (
        r * 0.001,
        col * 0.002,
        -0.0,
        2.0,
    )[:dimension]
    result, face = witness.snapshot(c.app, c.view, c.entity)
    assert face is c.face
    assert result["curve_kind"] == "line"
    assert result["curve_parameters"] == c.curve.LineParams
    row = result["face_surface"]
    assert row["identity"] == 4006
    assert row["read_request"] == {
        "conversion": "no_cubic_or_nonrational_request",
        "tolerance_m": 0.01,
    }
    assert row["parameterization"]["UProperties"] == (13737,)
    assert row["face_uv_bounds"] == (0.0, 1.0, 0.0, 1.0)
    assert row["face_sense"] == row["bspline_sense"] == "same"
    assert row["bspline"]["UPeriodicity"] == (
        "periodic" if periodic else "non_periodic"
    )
    assert row["bspline"]["UKnots"] == c.data.UKnots
    assert row["bspline"]["VKnots"] == c.data.VKnots
    assert len(row["bspline"]["control_points"]) == 2
    assert all(
        len(r) == 4 and all(len(p) == dimension for p in r)
        for r in row["bspline"]["control_points"]
    )
    assert row["bspline"]["control_points"][0][0][2].hex() == (-0.0).hex()
    c.surface.Parameterization2.assert_called_once_with()
    c.surface.GetBSurfParams3.assert_called_once_with(
        False, False, c.parameterization, 0.01
    )
    assert c.data.GetControlPoints.call_args_list == [
        call(r, col) for r in (1, 2) for col in (1, 2, 3, 4)
    ]


@pytest.mark.parametrize(
    "field,raw",
    [
        ("UOrder", True),
        ("VOrder", 0),
        ("ControlPointDimension", 2),
        ("ControlPointColumnCount", 4097),
        ("ControlPointRowCount", 0),
        ("UPeriodicity", 1),
        ("VPeriodicity", None),
        ("UKnots", (0.0,)),
        ("VKnots", (0.0, 1.0, 0.0, 1.0)),
        ("UKnots", (0.0, 0.0, 0.0, float("nan"), 1.0, 1.0, 1.0)),
    ],
)
def test_bsurface_refuses_bad_metadata_before_control_grid(bsurface, field, raw):
    c = bsurface
    setattr(c.data, field, raw)
    with pytest.raises(RuntimeError, match="BSURF"):
        witness.snapshot(c.app, c.view, c.entity)
    c.data.GetControlPoints.assert_not_called()


@pytest.mark.parametrize(
    "returned", [None, (), (None, True), (object(), 1), [object(), True]]
)
def test_bsurface_refuses_wrong_native_return_shape(bsurface, returned):
    c = bsurface
    c.surface.GetBSurfParams3.return_value = returned
    with pytest.raises(RuntimeError, match="BSURF"):
        witness.snapshot(c.app, c.view, c.entity)


@pytest.mark.parametrize(
    "raw",
    [None, (), (0.0, 0.0), (True, 0.0, 0.0), (0, 0.0, 0.0), (0.0, float("inf"), 0.0)],
)
def test_bsurface_refuses_incomplete_or_nonfinite_control_points(bsurface, raw):
    c = bsurface
    c.data.GetControlPoints.side_effect = None
    c.data.GetControlPoints.return_value = raw
    with pytest.raises(RuntimeError, match="BSURF"):
        witness.snapshot(c.app, c.view, c.entity)


@pytest.mark.parametrize(
    "change,reason",
    [
        ("coefficient", "raw geometry changed"),
        ("face", "silhouette face"),
        ("view", "silhouette owning view"),
        ("pid", "IsSamePersistentID"),
        ("face_uv", "raw geometry changed"),
    ],
)
def test_bsurface_does_not_replace_exact_identity_or_raw_equality(
    bsurface, change, reason
):
    c = bsurface
    other = NS(**vars(c.entity))
    if change == "coefficient":
        altered = deepcopy(c.data)
        altered.GetControlPoints.side_effect = lambda r, col: (
            r * 0.001 + 1e-16,
            col * 0.002,
            -0.0,
        )
        c.surface.GetBSurfParams3.side_effect = [(c.data, True), (altered, True)]
    if change == "face":
        other.GetFace = lambda: NS(**vars(c.face))
    if change == "view":
        other.GetView = lambda: object()
    if change == "pid":
        other.persistent_ref = (4, 5, 6)
    if change == "face_uv":
        c.face.GetUVBounds.side_effect = [
            (0.0, 1.0, 0.0, 1.0),
            (0.0, 0.9999999999999999, 0.0, 1.0),
        ]
    evidence = {}
    with pytest.raises(RuntimeError, match=reason):
        witness.require_same(
            c.app,
            c.view,
            c.entity,
            other,
            drawing=c.app.drawing,
            label="tooth tip",
            evidence=evidence,
        )
    assert evidence["expected"]["face_surface"]["identity"] == 4006
    if change in ("coefficient", "face_uv"):
        assert evidence["expected"] != evidence["actual"]
        assert evidence["persistent_identity"]["native_result"] == 1


@pytest.mark.parametrize(
    "field,raw",
    [
        ("UMin", 0),
        ("UMax", float("inf")),
        ("VMin", 1.0),
        ("UMinBoundType", True),
        ("VMaxBoundType", 999),
        ("UPropertyNumber", True),
        ("VPropertyNumber", 65),
        ("UProperties", None),
        ("VProperties", (13739.0,)),
        ("VProperties", (999,)),
        ("VProperties", ()),
    ],
)
def test_parameterization_refuses_malformed_fields_before_bsurface_call(
    bsurface, field, raw
):
    c = bsurface
    setattr(c.parameterization, field, raw)
    with pytest.raises(RuntimeError, match="BSURF"):
        witness.snapshot(c.app, c.view, c.entity)
    c.surface.GetBSurfParams3.assert_not_called()


@pytest.mark.parametrize(
    "fault",
    [
        "null_parameterization",
        "grid_budget",
        "face_bool",
        "face_range",
        "identity_type",
    ],
)
def test_bounded_read_refuses_null_bad_face_and_oversize_grid(bsurface, fault):
    c = bsurface
    if fault == "null_parameterization":
        c.surface.Parameterization2.return_value = None
    if fault == "grid_budget":
        c.data.ControlPointColumnCount = c.data.ControlPointRowCount = 65
    if fault == "face_bool":
        c.face.FaceInSurfaceSense.return_value = 1
    if fault == "face_range":
        c.face.GetUVBounds.return_value = (0.0, 0.0, 0.0, 1.0)
    if fault == "identity_type":
        c.surface.Identity = lambda: 4006.0
    with pytest.raises(RuntimeError, match="BSURF"):
        witness.snapshot(c.app, c.view, c.entity)
    c.data.GetControlPoints.assert_not_called()


def test_native_read_error_is_not_replaced_or_retried(bsurface):
    c = bsurface
    failure = OSError("native point read failed")
    c.data.GetControlPoints.side_effect = failure
    with pytest.raises(OSError) as raised:
        witness.snapshot(c.app, c.view, c.entity)
    assert raised.value is failure
    c.surface.GetBSurfParams3.assert_called_once()
    c.data.GetControlPoints.assert_called_once_with(1, 1)


def test_successful_bsurface_read_is_retained_when_later_curve_kind_rejects(bsurface):
    c = bsurface
    c.curve.IsLine = lambda: False
    evidence = {}
    with pytest.raises(
        RuntimeError, match="unsupported or contradictory silhouette curve"
    ):
        witness.require_same(
            c.app,
            c.view,
            c.entity,
            c.entity,
            drawing=c.app.drawing,
            label="tooth tip",
            evidence=evidence,
        )
    assert set(evidence) == {"expected"}
    assert set(evidence["expected"]) == {"face_surface", "curve_reads"}
    assert evidence["expected"]["face_surface"]["identity"] == 4006
    assert len(evidence["expected"]["face_surface"]["bspline"]["control_points"]) == 2
    c.surface.GetBSurfParams3.assert_called_once()


@pytest.mark.parametrize("failure", ["null", "native_error"])
def test_failed_sixth_point_preserves_metadata_indices_and_raw_results(bsurface, failure):
    c = bsurface
    c.data.ControlPointColumnCount = 8
    c.data.ControlPointDimension = 4
    c.data.UKnots = (0.0,) * 3 + (0.1, 0.2, 0.3, 0.4, 0.5) + (1.0,) * 3
    primary = OSError("native sixth point failed")

    def point(row, column):
        if (row, column) == (1, 6):
            if failure == "native_error":
                raise primary
            return None
        return (row * 0.001, column * 0.002, -0.0, 2.0)

    c.data.GetControlPoints.side_effect = point
    evidence = {}
    with pytest.raises((RuntimeError, OSError)) as raised:
        witness.require_same(
            c.app, c.view, c.entity, c.entity, drawing=c.app.drawing,
            label="tooth tip", evidence=evidence,
        )
    if failure == "native_error":
        assert raised.value is primary
    else:
        assert "GetControlPoints(1,6)" in str(raised.value)
    partial = evidence["expected"]["face_surface"]
    assert partial["read_request"]["tolerance_m"] == 0.01
    assert partial["parameterization"]["UProperties"] == (13737,)
    assert partial["bspline"]["UOrder"] == 3
    assert partial["bspline"]["ControlPointRowCount"] == 2
    assert partial["bspline"]["ControlPointColumnCount"] == 8
    assert partial["bspline"]["ControlPointDimension"] == 4
    assert partial["bspline"]["UKnots"] == c.data.UKnots
    assert partial["bspline"]["VKnots"] == c.data.VKnots
    assert partial["raw_bspline"]["ControlPointColumnCount"]["value"] == 8
    points = partial["control_point_reads"]
    assert [(row["row"], row["column"]) for row in points] == [(1, column) for column in range(1, 7)]
    assert [item["value"] for item in points[0]["returned"]["value"]] == [0.001, 0.002, -0.0, 2.0]
    if failure == "native_error":
        assert points[-1]["returned"]["error"] == repr(primary)
    else:
        assert points[-1]["returned"] == {"type": "builtins.NoneType", "value": None}
    assert "control_points" not in partial["bspline"]
    assert "actual" not in evidence
    assert c.data.GetControlPoints.call_args_list == [call(1, column) for column in range(1, 7)]
    c.surface.GetBSurfParams3.assert_called_once_with(False, False, c.parameterization, 0.01)
    json.dumps(evidence, allow_nan=False)


def test_invalid_raw_count_is_retained_before_integer_validation(bsurface):
    c = bsurface
    c.data.ControlPointColumnCount = True
    evidence = {}
    with pytest.raises(RuntimeError, match="ControlPointColumnCount"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    partial = evidence["face_surface"]
    assert partial["raw_bspline"]["ControlPointColumnCount"] == {"type": "builtins.bool", "value": True}
    assert partial["bspline"]["VOrder"] == 2
    assert "ControlPointColumnCount" not in partial["bspline"]
    c.data.GetControlPoints.assert_not_called()


def test_successful_journal_does_not_change_geometry_or_repeat_native_reads(bsurface):
    c = bsurface
    before = witness.bsurface.snapshot(c.face, c.surface)
    calls = c.data.GetControlPoints.call_args_list[:]
    c.data.GetControlPoints.reset_mock()
    c.surface.Parameterization2.reset_mock()
    c.surface.GetBSurfParams3.reset_mock()
    c.face.GetUVBounds.reset_mock()
    c.face.FaceInSurfaceSense.reset_mock()
    evidence = {}
    after = witness.bsurface.snapshot(c.face, c.surface, evidence=evidence)
    assert after == before
    assert evidence["bspline"] == before["bspline"]
    assert evidence["parameterization"] == before["parameterization"]
    assert len(evidence["control_point_reads"]) == 8
    assert c.data.GetControlPoints.call_args_list == calls
    c.surface.Parameterization2.assert_called_once_with()
    c.surface.GetBSurfParams3.assert_called_once_with(False, False, c.parameterization, 0.01)
    c.face.GetUVBounds.assert_called_once_with()
    c.face.FaceInSurfaceSense.assert_called_once_with()
    json.dumps(evidence, allow_nan=False)


def test_journal_encoder_error_does_not_replace_null_vector_rejection(bsurface, monkeypatch):
    c = bsurface
    c.data.GetControlPoints.return_value = None
    c.data.GetControlPoints.side_effect = None
    secondary = ValueError("raw encoder failed")
    monkeypatch.setattr(witness.bsurface, "_raw_return", Mock(side_effect=secondary))
    evidence = {}
    with pytest.raises(RuntimeError, match=r"GetControlPoints\(1,1\): expected 3 native doubles, got None"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    returned = evidence["face_surface"]["control_point_reads"][0]["returned"]
    assert returned == {
        "type": "builtins.NoneType", "observation_error": repr(secondary),
    }
    c.data.GetControlPoints.assert_called_once_with(1, 1)


def test_failed_parameter_array_retains_validated_prefix_and_actual_raw(bsurface):
    c = bsurface
    c.parameterization.UProperties = None
    evidence = {}
    with pytest.raises(RuntimeError, match="UProperties"):
        witness.snapshot(c.app, c.view, c.entity, evidence=evidence)
    partial = evidence["face_surface"]
    assert partial["parameterization"]["UPropertyNumber"] == 1
    assert partial["parameterization"]["UMaxBoundType"] == 13735
    assert partial["raw_parameterization"]["UProperties"] == {
        "type": "builtins.NoneType", "value": None,
    }
    assert "UProperties" not in partial["parameterization"]
    assert "bspline" not in partial
    c.surface.GetBSurfParams3.assert_not_called()
    c.data.GetControlPoints.assert_not_called()


def test_surface_and_face_sense_and_periodic_straddling_bounds_remain_distinct(
    bsurface,
):
    c = bsurface
    c.surface.GetBSurfParams3.return_value = (c.data, False)
    c.face.FaceInSurfaceSense.return_value = True
    c.data.VPeriodicity = True
    c.parameterization.VMinBoundType = c.parameterization.VMaxBoundType = 13701
    c.face.GetUVBounds.return_value = (0.0, 1.0, 0.75, 1.25)
    row = witness.snapshot(c.app, c.view, c.entity)[0]["face_surface"]
    assert row["face_sense"] == row["bspline_sense"] == "opposite"
    assert row["bspline"]["VPeriodicity"] == "periodic"
    assert row["face_uv_bounds"] == (0.0, 1.0, 0.75, 1.25)


@pytest.mark.parametrize("cold_change", [None, "coefficient", "pid"])
def test_real_view_fcf_observer_uses_bsurface_on_selection_built_and_fresh_cold(
    bsurface,
    bank,
    monkeypatch,
    cold_change,
):
    c = bsurface
    label = "gear tooth-tip circular runout"
    bank.manifest.view_roles.clear()
    bank.manifest.view_roles[label] = VIEW_ROLES["crank_drive_gear"][label]
    bank.module.OUTSIDE_DIA = 12.0
    resolver = Mock(side_effect=lambda adapter, view, diameter: view.entity)
    bank.module.visible_tooth_tip_silhouette = resolver
    bank.view.GetOrientationName = lambda: "*Right"
    bank.adapter.currentModel.GetType = lambda: 3
    bank.adapter.currentModel.Extension = c.app.drawing.Extension
    bank.entity = bank.view.entity = c.entity
    c.entity.GetView = lambda: bank.view
    bank.manager.GetSelectedObjectType3 = lambda *_: 46
    with bank.witness.observe(bank.adapter):
        bank.module.add_feature_control_frame(
            bank.adapter,
            bank.view,
            label=label,
            entity=c.entity,
            entity_type="SILHOUETTE",
        )
    built = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    assert built["explicit"][label]["geometry"]["face_surface"]["identity"] == 4006
    assert [row["stage"] for row in bank.witness.context_report["stages"]] == [
        "selected",
        "inserted",
        "built",
    ]

    cold = bsurface_fixture()
    view = NS(
        GetName2=bank.view.GetName2,
        GetOrientationName=lambda: "*Right",
        entity=cold.entity,
    )
    cold.entity.GetView = lambda: view
    attached = NS(**vars(cold.entity))
    annotation = NS(**vars(bank.annotations[label]))
    annotation.Owner = view
    annotation.GetAttachedEntities3 = lambda: (attached,)
    view.GetAnnotations = lambda: (annotation,)
    monkeypatch.setattr(observer.attachments, "views", lambda _: {"Sheet/View": view})
    old = bank.adapter.currentModel
    cold.app.drawing.GetCurrentSheet = old.GetCurrentSheet
    bank.adapter.currentModel = cold.app.drawing
    # Every old native handle used by this witness becomes unusable on reopen.
    old.Extension.GetPersistReference3 = Mock(
        side_effect=AssertionError("closed extension read")
    )
    bank.view.GetName2 = Mock(side_effect=AssertionError("closed view read"))
    c.entity.GetFace = Mock(side_effect=AssertionError("closed silhouette read"))
    c.surface.Parameterization2 = Mock(
        side_effect=AssertionError("closed surface read")
    )
    if cold_change == "pid":
        attached.persistent_ref = (8, 9, 10)
        with pytest.raises(RuntimeError, match="IsSamePersistentID"):
            bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
        return
    if cold_change == "coefficient":
        cold.data.GetControlPoints.side_effect = lambda r, col: (
            r * 0.001 + 1e-16,
            col * 0.002,
            -0.0,
        )
    reopened = bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
    compared = bank.witness.compare_cold(built, reopened)
    assert compared["status"] == ("failed" if cold_change else "passed")
    assert compared["curve_tag_observations"] == []
    if cold_change:
        assert len(compared["rejected"]) == 8
        assert all(
            "control_points" in change["path"] for change in compared["rejected"]
        )
    assert resolver.call_args_list == [
        call(bank.adapter, bank.view, 12.0),
        call(bank.adapter, view, 12.0),
    ]

"""Offline manufacturing boundaries for the modified purchased anchor."""

import json
import math
from types import SimpleNamespace

import pytest

import _stock_trim_drawing as trim_drawing
import _drawing_view_display as view_display
import sm_vn_boss_hook_spec as spec
import draw_sm_vn_boss_hook as drawing
from _hole_spec import TAP_DRILL_MM
from stock_anchor_geom import ANCHOR_9490T1 as anchor


def test_finished_overall_preserves_factory_thread_datum():
    cut_end = anchor.eye_od_mm / 2 - spec.FINISHED_OVERALL_MM
    assert cut_end == pytest.approx(spec.TRIM.shank_end_y_mm)
    # The full 19.05 boss plus the jam nut's thread above it (#1189).
    assert spec.TRIM.shank_length_mm == pytest.approx(22.886)
    assert spec.TRIM.shank_length_mm - 19.05 >= spec.JAM_NUT_THREAD_MM - 1e-3
    assert spec.FINISHED_OVERALL_MM == pytest.approx(40.4755)


def test_deburr_band_clears_receiver_and_retains_full_threads():
    minimum = spec.CHAMFER_WIDTH_MM - spec.CHAMFER_WIDTH_TOLERANCE_MM
    maximum = spec.CHAMFER_WIDTH_MM + spec.CHAMFER_WIDTH_TOLERANCE_MM
    assert anchor.thread_major_dia_mm - 2 * minimum < TAP_DRILL_MM[anchor.thread_size]
    # Include the adverse angular corner, not only the nominal 45-degree leg.
    maximum_axial = maximum / math.tan(
        math.radians(spec.CHAMFER_ANGLE_DEG - spec.CHAMFER_ANGLE_TOLERANCE_DEG)
    )
    short_shank = spec.SHANK_LENGTH_MM - spec.FINISHED_OVERALL_TOLERANCE_MM
    assert short_shank - maximum_axial > 17.0


@pytest.mark.parametrize(
    "fault", [None, "reference", "nominal", "tolerance", "precision", "missing"]
)
def test_drawing_accepts_general_controls_and_rejects_lost_control(monkeypatch, fault):
    """General is toleranced, unlike None; neither replaces a real driving size."""
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(
        trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name
    )
    annotations = []
    for name, nominal, band in (
        (
            "FinishedOverall",
            spec.FINISHED_OVERALL_MM / 1000,
            spec.FINISHED_OVERALL_TOLERANCE_MM / 1000,
        ),
        (
            "ChamferWidth",
            spec.CHAMFER_WIDTH_MM / 1000,
            spec.CHAMFER_WIDTH_TOLERANCE_MM / 1000,
        ),
        (
            "ChamferAngle",
            math.radians(spec.CHAMFER_ANGLE_DEG),
            math.radians(spec.CHAMFER_ANGLE_TOLERANCE_DEG),
        ),
    ):
        tolerance = SimpleNamespace(
            Type=spec.DIMENSION_TOLERANCE_TYPES[name],
            GetMinValue=lambda band=band: -band,
            GetMaxValue=lambda band=band: band,
        )
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal, Tolerance=tolerance
        )
        display = SimpleNamespace(
            GetDimension2=lambda _configuration, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda name=name: spec.DIMENSION_PRECISION[name],
        )
        annotations.append(
            SimpleNamespace(
                name=name,
                dimension=dimension,
                display=display,
                GetSpecificAnnotation=lambda display=display: display,
            )
        )
    if fault == "reference":
        annotations[0].dimension.DrivenState = 1
    elif fault == "nominal":
        annotations[0].dimension.SystemValue += 0.001
    elif fault == "tolerance":
        # swTolNONE must remain invalid; a no-tolerance spec is a regression.
        annotations[0].dimension.Tolerance.Type = 0
    elif fault == "precision":
        annotations[0].display.GetPrimaryPrecision2 = lambda: (
            spec.DIMENSION_PRECISION["FinishedOverall"] + 1
        )
    elif fault == "missing":
        annotations.pop()
    if fault is None:
        drawing._verify_controls(None, annotations)
    else:
        with pytest.raises(RuntimeError):
            drawing._verify_controls(None, annotations)


@pytest.mark.parametrize(
    "fault", (None, "missing", "outer", "bend", "foreign-visible", "wrong-path",
              "missing-curve", "noncircle", "wrong-radius", "stuck-hlv", "stuck-hlr"),
)
def test_supplier_eye_requires_real_mode_regeneration_and_preserves_controls(monkeypatch, fault):
    """An immediate repaint alone cannot restore post-annotation native ID edges."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(view_display, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", view_display.set_hidden_lines_removed)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    owner = object()
    source = SimpleNamespace(
        GetPathName=lambda: str(drawing.SOURCE.resolve()),
        FeatureByName=lambda name: owner if name == "Wire" else None,
    )
    surface = SimpleNamespace(
        IsTorus=lambda: True,
        TorusParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0,
                     anchor.eye_mean_radius_mm / 1000, anchor.wire_dia_mm / 2000),
    )
    face = SimpleNamespace(GetSurface=lambda: surface, GetFeature=lambda: owner)
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    controls, control_displays = [], []
    for name, (nominal, lower, upper) in drawing.EXPECTED_CONTROLS.items():
        dimension = SimpleNamespace(
            DrivenState=2, SystemValue=nominal,
            Tolerance=SimpleNamespace(
                Type=spec.DIMENSION_TOLERANCE_TYPES[name],
                GetMinValue=lambda lower=lower: lower,
                GetMaxValue=lambda upper=upper: upper,
            ),
        )
        display_control = SimpleNamespace(
            GetDimension2=lambda _index, dimension=dimension: dimension,
            GetText=lambda _index: "",
            GetPrimaryPrecision2=lambda name=name: spec.DIMENSION_PRECISION[name],
        )
        control_displays.append(display_control)
        controls.append(SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display_control: display,
        ))
    for index, display_control in enumerate(control_displays):
        following = control_displays[index + 1] if index + 1 < len(control_displays) else None
        display_control.GetNext5 = lambda following=following: following
    state = SimpleNamespace(mode=2, hlv_seen=False, regenerated=False, materialized=False)
    front = SimpleNamespace(Name="finished-front", ReferencedDocument=source)
    front.GetFirstDisplayDimension6 = lambda: control_displays[0]

    def set_mode(_parent, mode, *_args):
        if (fault == "stuck-hlv" and mode == 1) or (fault == "stuck-hlr" and mode == 2):
            return False
        previous = state.mode
        state.mode = mode
        if previous == 2 and mode == 1:
            state.hlv_seen = True
        if previous == 1 and mode == 2 and state.hlv_seen:
            state.regenerated = True
        state.materialized = False
        return previous != mode

    def refresh():
        state.materialized = state.regenerated and state.mode == 2

    front.SetDisplayMode4 = set_mode
    front.GetDisplayMode2 = lambda: state.mode
    front.UpdateViewDisplayGeometry = refresh

    def contour(diameter, attached_face=face, center=(0.0, 0.0, 0.0)):
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(*center, 0.0, 0.0, 1.0, diameter / 2000),
        )
        return SimpleNamespace(
            GetCurve=lambda: curve, GetFace=lambda: attached_face, GetView=lambda: front,
        )

    eye = contour(spec.SUPPLIER_EYE_ID_MM)
    outer = contour(anchor.eye_od_mm)
    bend = contour(0.9123785, center=(-0.002869189, -0.00879475, 0.0))
    visible = [outer, bend, eye]
    if fault in ("missing", "outer", "bend"):
        visible = {"missing": [], "outer": [outer], "bend": [bend]}[fault]
    elif fault == "foreign-visible":
        face.GetFeature = lambda: object()
    elif fault == "wrong-path":
        source.GetPathName = lambda: "D:/foreign.SLDPRT"
    elif fault == "missing-curve":
        eye.GetCurve = lambda: None
    elif fault == "noncircle":
        eye.GetCurve().IsCircle = lambda: False
    elif fault == "wrong-radius":
        values = list(eye.GetCurve().CircleParams)
        values[6] += 2e-8
        eye.GetCurve().CircleParams = tuple(values)

    def enumerate_visible(view, kind, **_kwargs):
        assert view is front
        assert kind == 4, "ID discovery must never fall back to edges"
        # Refresh alone does not regenerate edges after imported annotations.
        return visible if state.materialized else [outer, bend]

    monkeypatch.setattr(drawing, "visible_view_entities", enumerate_visible)
    selected = []
    monkeypatch.setattr(
        drawing, "_select_view_entity",
        lambda _adapter, _view, kind, _point, **kwargs: selected.append((kind, kwargs["entity"])),
    )
    display = SimpleNamespace(GetDimension2=lambda _index: SimpleNamespace(FullName="EyeID@native"))
    model = SimpleNamespace(
        AddDiameterDimension2=lambda *_args: display, ClearSelection2=lambda _all: None,
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda _adapter, value, **_kwargs: value)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    drawing._verify_controls(adapter, controls)
    if fault is None:
        refs = drawing._supplier_references(adapter, front)
        assert selected == [("SILHOUETTE", eye)]
        assert refs == [("EyeID@native", {
            "label": "EyeID", "expected_mm": spec.SUPPLIER_EYE_ID_MM, "units": "in",
            "precision": drawing.SUPPLIER_REFERENCE_PRECISION["EyeID"],
            "presentation": "diameter",
            "fraction_denominator": drawing.SUPPLIER_FRACTION_DENOMINATOR,
        })]
        assert state.mode == 2 and state.regenerated and state.materialized
    else:
        with pytest.raises(RuntimeError):
            drawing._supplier_references(adapter, front)
        assert selected == []
    surviving = []
    current = front.GetFirstDisplayDimension6()
    while current is not None:
        surviving.append(current)
        current = current.GetNext5()
    assert len(surviving) == len(drawing.FRONT_KEEP)
    assert all(actual is expected for actual, expected in zip(surviving, control_displays))
    drawing._verify_controls(adapter, controls)


@pytest.fixture
def supplier_eye_census_scene(monkeypatch, tmp_path):
    """Native-shaped behavior only; these fixtures do not establish COM support."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(view_display, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", view_display.set_hidden_lines_removed)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    source_path = tmp_path / "eye.SLDPRT"
    source_path.write_bytes(b"offline identity fixture")
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    actions, queries, observations = [], [], []
    state = SimpleNamespace(mode=2)
    owner = SimpleNamespace(Name="Wire", GetTypeName2=lambda: "Sweep", GetID=lambda: 81)
    foreign_owner = SimpleNamespace(Name="Bend", GetTypeName2=lambda: "Sweep", GetID=lambda: 82)
    surface = SimpleNamespace(
        Identity=lambda: 4007, IsTorus=lambda: True,
        TorusParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0,
                     anchor.eye_mean_radius_mm / 1000, anchor.wire_dia_mm / 2000),
    )
    source_face = SimpleNamespace(GetFeature=lambda: owner, GetSurface=lambda: surface)
    drawing_face = SimpleNamespace(GetFeature=lambda: owner, GetSurface=lambda: surface)
    owner.GetFaces = lambda: (source_face,)
    active_configuration = SimpleNamespace(Name="Default", GetID=lambda: 31)
    referenced_configuration = SimpleNamespace(Name="Finished", GetID=lambda: 32)
    source = SimpleNamespace(
        GetPathName=lambda: str(source_path.resolve()),
        GetType=lambda: observations.append("document-type") or 1,
        GetTitle=lambda: "eye.SLDPRT",
        FeatureByName=lambda name: owner if name == "Wire" else None,
        ConfigurationManager=SimpleNamespace(ActiveConfiguration=active_configuration),
        GetConfigurationByName=lambda name: referenced_configuration if name == "Finished" else None,
        Extension=SimpleNamespace(
            GetCorrespondingEntity2=lambda face: source_face if face is drawing_face else None,
        ),
    )
    front = SimpleNamespace(
        Name="finished-front", ReferencedDocument=source, ReferencedConfiguration="Finished",
        ModelToViewTransform=SimpleNamespace(ArrayData=(
            1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
            0.100, 0.175, 0.0, 4.0, 0.0, 0.0, 0.0,
        )),
        GetDisplayMode2=lambda: state.mode,
        GetCorresponding=lambda feature: owner if feature is owner else None,
        GetCorrespondingEntity=lambda face: drawing_face if face is source_face else None,
    )

    def set_mode(_parent, mode, *_args):
        actions.append(("mode", mode))
        previous, state.mode = state.mode, mode
        return previous != mode

    front.SetDisplayMode4 = set_mode
    front.UpdateViewDisplayGeometry = lambda: actions.append(("refresh",))

    def contour(diameter=spec.SUPPLIER_EYE_ID_MM, face=drawing_face):
        curve = SimpleNamespace(
            Identity=lambda: 3002, IsCircle=lambda: True,
            CircleParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, diameter / 2000),
        )
        return SimpleNamespace(GetCurve=lambda: curve, GetFace=lambda: face, GetView=lambda: front)

    eye, outer = contour(), contour(anchor.eye_od_mm)
    visible, edges = [outer], []

    def enumerate_visible(view, kind, **_kwargs):
        assert view is front
        queries.append(kind)
        assert kind in (4, 1)
        return visible if kind == 4 else edges

    monkeypatch.setattr(drawing, "visible_view_entities", enumerate_visible)
    monkeypatch.setattr(
        drawing, "_select_view_entity",
        lambda _adapter, _view, kind, _point, **kwargs: actions.append(("select", kind, kwargs["entity"])),
    )
    display = SimpleNamespace(GetDimension2=lambda _index: SimpleNamespace(FullName="EyeID@native"))
    model = SimpleNamespace(
        AddDiameterDimension2=lambda *_args: actions.append(("dimension",)) or display,
        ClearSelection2=lambda _all: actions.append(("clear",)),
    )
    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda _adapter, value, **_kwargs: value)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        drawing, "model_points_in_view",
        lambda _adapter, _view, points, **_kwargs: [(point[0] * 4 + 0.100, point[1] * 4 + 0.175) for point in points],
    )
    return SimpleNamespace(
        adapter=adapter, front=front, source=source, source_path=source_path,
        owner=owner, foreign_owner=foreign_owner, surface=surface,
        drawing_face=drawing_face, source_face=source_face,
        eye=eye, outer=outer, contour=contour, visible=visible, edges=edges,
        actions=actions, queries=queries, observations=observations,
    )


def _missing_eye_packet(scene):
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_references(scene.adapter, scene.front)
    assert type(caught.value) is RuntimeError
    assert str(caught.value) == "unchanged counter eye has no exact ID circular silhouette"
    assert len(caught.value.__notes__) == 1
    packet = json.loads(caught.value.__notes__[0])
    assert packet["observation_only"] is True
    assert scene.queries == [4, 1], "Reuse the original kind4 snapshot; kind1 is diagnostic only"
    assert scene.actions == [("mode", 1), ("mode", 2), ("refresh",)]
    return packet


@pytest.mark.parametrize(
    "fault,field",
    (
        ("owner", "owner"), ("view", "view_name_matches"),
        ("path", "source_lexical_path_matches"), ("torus-center", "torus_center_matches"),
        ("torus-z", "torus_z_normal_matches"), ("torus-major", "torus_major_matches"),
        ("torus-minor", "torus_minor_matches"),
    ),
)
def test_failure_census_distinguishes_raw_id_from_individual_predicate_rejection(
    supplier_eye_census_scene, fault, field,
):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    if fault == "owner":
        scene.drawing_face.GetFeature = lambda: scene.foreign_owner
    elif fault == "view":
        scene.eye.GetView = lambda: SimpleNamespace(Name="other-front")
    elif fault == "path":
        scene.source.GetPathName = lambda: str(scene.source_path.parent / "foreign.SLDPRT")
    else:
        values = list(scene.surface.TorusParams)
        values[{"torus-center": 0, "torus-z": 5, "torus-major": 6, "torus-minor": 7}[fault]] += 0.001
        scene.surface.TorusParams = tuple(values)
    packet = _missing_eye_packet(scene)
    assert packet["raw_exact_circle_count"] == 1
    assert packet["raw_origin_xy_id_circle_count"] == 1
    assert packet["accepted_id_count"] == 0
    row = packet["kind4"][0]
    assert row["circle_finite7"] is True
    assert row["circle_center_matches"] is True
    assert row["circle_z_normal_matches"] is True
    assert row["id_diameter_matches"] is True
    if fault == "owner":
        assert row["face"]["owner_same_as_expected"] == 0
        assert row["face"]["owner_matches_expected"] is False
        assert row["face"]["owner"]["id"] == 82
        # Mapping back to Wire is evidence, never a waiver of the direct rejection.
        assert row["mapped_source_face"]["owner_same_as_expected"] == 1
        assert row["roundtrip_same_as_drawing_face"] == 1
    elif fault.startswith("torus-"):
        assert row["face"][field] is False
    else:
        assert row[field] is False


@pytest.mark.parametrize("inventory", ("empty", "missing-curve", "noncircle", "outer"))
def test_failure_census_separates_raw_absence_and_wrong_contour(supplier_eye_census_scene, inventory):
    scene = supplier_eye_census_scene
    if inventory == "empty":
        scene.visible.clear()
    elif inventory == "missing-curve":
        scene.outer.GetCurve = lambda: None
    elif inventory == "noncircle":
        scene.outer.GetCurve().IsCircle = lambda: False
    packet = _missing_eye_packet(scene)
    assert packet["kind4_count"] == (0 if inventory == "empty" else 1)
    assert packet["raw_exact_circle_count"] == int(inventory == "outer")
    assert packet["raw_origin_xy_id_circle_count"] == 0
    assert packet["accepted_id_count"] == 0
    if inventory == "outer":
        assert packet["kind4"][0]["od_diameter_matches_observation_only"] is True
        assert packet["kind4"][0]["id_diameter_matches"] is False


def test_failure_census_keeps_independent_api_errors_and_negative_controls(supplier_eye_census_scene):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    scene.drawing_face.GetFeature = lambda: scene.foreign_owner

    def fail(message):
        raise OSError(message)

    scene.foreign_owner.GetID = lambda: fail("owner ID failed")
    scene.owner.GetTypeName2 = lambda: fail("expected type failed")
    scene.surface.Identity = lambda: fail("surface identity failed")
    scene.source.GetType = lambda: fail("document type failed")
    scene.source.GetConfigurationByName("Finished").GetID = lambda: fail("configuration ID failed")
    scene.adapter.swApp.IsSame = lambda _first, _second: -1
    packet = _missing_eye_packet(scene)
    row, source = packet["kind4"][0], packet["source"]
    assert row["face"]["owner"]["errors"]["id"]["message"] == "owner ID failed"
    assert source["expected_feature"]["errors"]["type"]["message"] == "expected type failed"
    assert row["face"]["errors"]["surface_identity"]["message"] == "surface identity failed"
    assert source["errors"]["document_type"]["message"] == "document type failed"
    assert source["referenced_configuration_object"]["errors"]["id"]["message"] == "configuration ID failed"
    assert source["expected_feature"]["self_is_same"] == -1
    assert row["face"]["owner"]["self_is_same"] == -1
    assert row["face"]["owner_same_as_expected"] == -1
    assert row["face"]["owner_matches_expected"] is False
    assert row["face"]["torus_major_matches"] is True
    assert row["face"]["torus_minor_matches"] is True
    assert row["circle_finite7"] is True
    assert row["roundtrip_same_as_drawing_face"] == -1


def test_failure_census_records_alias_identity_without_relaxing_lexical_path(
    supplier_eye_census_scene,
):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    alias = scene.source_path.parent / "alias"
    alias.mkdir()
    scene.source.GetPathName = lambda: str(alias / ".." / scene.source_path.name)
    packet = _missing_eye_packet(scene)
    source = packet["source"]
    assert source["lexical_path_matches"] is False
    assert source["physical_samefile"] is True
    assert source["native_canonical_path"] == source["source_canonical_path"]
    assert source["native_file_id"] == source["source_file_id"]
    assert source["document_type"] == 1
    assert source["document_title"] == "eye.SLDPRT"
    assert source["active_configuration"]["name"] == "Default"
    assert source["active_configuration"]["id"] == 31
    assert source["referenced_configuration_object"]["name"] == "Finished"
    assert source["referenced_configuration_object"]["id"] == 32
    assert packet["accepted_id_count"] == 0


def test_failure_census_exposes_source_torus_and_native_shaped_roundtrip(supplier_eye_census_scene):
    scene = supplier_eye_census_scene
    packet = _missing_eye_packet(scene)
    source, row = packet["source"], packet["kind4"][0]
    assert source["model_to_view_transform"] == list(scene.front.ModelToViewTransform.ArrayData)
    assert source["referenced_configuration"] == "Finished"
    assert source["display_mode"] == 2
    assert source["view_self_is_same"] == 1
    assert source["expected_feature"] == {
        "present": True, "name": "Wire", "type": "Sweep", "id": 81, "self_is_same": 1,
    }
    assert source["wire_face_count"] == 1
    source_torus = source["wire_faces"][0]
    assert source_torus["coordinate_context"] == "source_part"
    assert source_torus["owner_same_as_expected"] == 1
    assert source_torus["torus_params_m"][6:] == pytest.approx([
        anchor.eye_mean_radius_mm / 1000, anchor.wire_dia_mm / 2000,
    ])
    assert source_torus["center_sheet_xy_m"] == pytest.approx([0.100, 0.175])
    assert row["face"]["coordinate_context"] == "silhouette_GetFace_context_undocumented"
    assert row["mapped_source_face"]["coordinate_context"] == "source_part"
    assert row["mapped_source_face"]["owner_same_as_expected"] == 1
    assert row["same_as_source_wire_faces"] == [{"source_face_index": 0, "is_same": 0}]
    assert row["roundtrip_face_present"] is True
    assert row["roundtrip_self_is_same"] == 1
    assert row["roundtrip_same_as_drawing_face"] == 1
    assert source["view_corresponding_feature"]["self_is_same"] == 1
    assert source["view_feature_same_as_expected"] == 1


@pytest.mark.parametrize("mapping", ("null", "error"))
def test_failure_census_retains_null_or_failed_correspondence(supplier_eye_census_scene, mapping):
    scene = supplier_eye_census_scene

    def corresponding(_face):
        if mapping == "error":
            raise OSError("correspondence unavailable")
        return None

    scene.source.Extension.GetCorrespondingEntity2 = corresponding
    row = _missing_eye_packet(scene)["kind4"][0]
    assert row["mapped_source_face"]["face_present"] is False
    assert row["roundtrip_face_present"] is False
    assert row["roundtrip_same_as_drawing_face"] is None
    if mapping == "error":
        assert row["errors"]["mapped_source_face_present"]["message"] == "correspondence unavailable"
    else:
        assert row["mapped_source_face_present"] is False


def test_failure_census_keeps_all_candidates_and_failure_only_edge_inventory(supplier_eye_census_scene):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.outer] * 24 + [None]
    sampled = []
    spline = SimpleNamespace(
        Identity=lambda: 3005, IsCircle=lambda: False, IsLine=lambda: False,
        GetEndParams=lambda: (True, 2.0, 6.0, False, False),
        Evaluate2=lambda parameter, derivatives: sampled.append((parameter, derivatives)) or (parameter, 0.0, 0.0, 99.0),
    )
    line = SimpleNamespace(
        Identity=lambda: 3001, IsCircle=lambda: False, IsLine=lambda: True,
        LineParams=(0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        GetEndParams=lambda: (True, -1.7e308, 1.7e308, False, False),
        Evaluate2=lambda *_args: pytest.fail("Infinite line must not be sampled"),
    )
    scene.edges[:] = [
        SimpleNamespace(GetCurve=lambda: scene.eye.GetCurve(), GetTwoAdjacentFaces2=lambda: (scene.drawing_face, None)),
        SimpleNamespace(GetCurve=lambda: spline, GetTwoAdjacentFaces2=lambda: (scene.drawing_face, None)),
        SimpleNamespace(GetCurve=lambda: line, GetTwoAdjacentFaces2=lambda: (scene.drawing_face, None)),
    ]
    packet = _missing_eye_packet(scene)
    assert packet["kind4_count"] == 25
    assert len(packet["kind4"]) == 25
    assert packet["kind4"][-1]["raw_present"] is False
    assert packet["kind1_count"] == 3
    assert packet["kind1_curve_identity_counts"] == {"3002": 1, "3005": 1, "3001": 1}
    assert packet["kind1"][0]["id_diameter_matches"] is True
    assert packet["accepted_id_count"] == 0, "A type1 circle must not become a type46 fallback"
    assert sampled == [(2.0 + index * 0.5, 0) for index in range(9)]
    assert len(packet["kind1"][1]["samples"]) == 9
    assert packet["kind1"][1]["samples"][0]["xyz_m"] == [2.0, 0.0, 0.0]
    assert packet["kind1"][1]["adjacent_faces"][0]["torus_major_matches"] is True
    assert packet["kind1"][2]["sample_range_valid"] is False
    assert packet["kind1"][2]["samples"] == []


def test_success_does_not_run_census_or_add_observational_native_calls(
    supplier_eye_census_scene, monkeypatch,
):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    monkeypatch.setattr(
        drawing, "_supplier_eye_failure_readback",
        lambda *_args: pytest.fail("Successful discovery must not run a census"),
    )
    assert drawing._supplier_references(scene.adapter, scene.front)[0][0] == "EyeID@native"
    assert scene.queries == [4]
    assert scene.observations == []
    assert scene.actions == [
        ("mode", 1), ("mode", 2), ("refresh",),
        ("select", "SILHOUETTE", scene.eye), ("dimension",), ("clear",),
    ]


def test_failure_census_preserves_transient_original_rejection(supplier_eye_census_scene):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    calls = []

    def transient_owner():
        calls.append("owner")
        return scene.foreign_owner if len(calls) == 1 else scene.owner

    scene.drawing_face.GetFeature = transient_owner
    packet = _missing_eye_packet(scene)
    original = packet["predicate_time"][0]
    assert original["index"] == 0
    assert original["first_rejection"] == "owner_same_as_expected"
    assert original["owner_same_as_expected"] == 0
    assert original["circle_params_m"] == list(scene.eye.GetCurve().CircleParams)
    assert original["circle_finite7"] is True
    assert original["circle_center_matches"] is True
    assert original["circle_z_normal_matches"] is True
    assert original["surface_present"] == "unobserved"
    assert original["torus_params_m"] == "unobserved"
    assert packet["accepted_id_count"] == 1
    assert packet["kind4"][0]["face"]["owner_same_as_expected"] == 1
    assert packet["kind4"][0]["accepted_id_predicates"] is True


def test_predicate_native_exception_keeps_original_object_type_message_and_stage(
    supplier_eye_census_scene,
):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    curve = scene.eye.GetCurve()
    error = OSError("original disconnected native curve")
    calls = []

    def disconnected_once():
        calls.append("curve")
        if len(calls) == 1:
            raise error
        return curve

    scene.eye.GetCurve = disconnected_once
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front)
    assert caught.value is error
    assert type(caught.value) is OSError
    assert str(caught.value) == "original disconnected native curve"
    assert len(caught.value.__notes__) == 1
    packet = json.loads(caught.value.__notes__[0])
    original = packet["predicate_time"][0]
    assert original["stage"] == "GetCurve"
    assert original["first_rejection"] is None
    assert original["curve_present"] == "unobserved"
    assert original["error"] == {"type": "OSError", "message": "original disconnected native curve"}
    assert packet["raw_origin_xy_id_circle_count"] == 1
    assert scene.queries == [4, 1]
    assert scene.actions == [("mode", 1), ("mode", 2), ("refresh",)]


def test_optional_predicate_readback_does_not_change_native_getters_or_guard_result(
    supplier_eye_census_scene,
):
    scene = supplier_eye_census_scene
    calls = []

    class NativeSpy:
        def __init__(self, target, label):
            self.target = target
            self.label = label

        def __getattr__(self, name):
            value = getattr(self.target, name)
            if not callable(value):
                calls.append(f"{self.label}.{name}")
                return value

            def invoke(*args):
                calls.append(f"{self.label}.{name}")
                return value(*args)

            return invoke

    owner = scene.owner
    surface = NativeSpy(scene.surface, "surface")
    face = NativeSpy(SimpleNamespace(GetFeature=lambda: owner, GetSurface=lambda: surface), "face")
    source = NativeSpy(SimpleNamespace(
        GetPathName=lambda: str(scene.source_path.resolve()),
        FeatureByName=lambda _name: owner,
    ), "source")
    front = NativeSpy(SimpleNamespace(Name="finished-front", ReferencedDocument=source), "front")
    curve = NativeSpy(scene.eye.GetCurve(), "curve")
    silhouette = NativeSpy(SimpleNamespace(
        GetCurve=lambda: curve, GetView=lambda: front, GetFace=lambda: face,
    ), "silhouette")
    adapter = SimpleNamespace(swApp=NativeSpy(
        SimpleNamespace(IsSame=lambda first, second: int(first is second)), "app",
    ))
    expected_calls = [
        "silhouette.GetCurve", "curve.IsCircle", "curve.CircleParams", "silhouette.GetView",
        "front.Name", "front.Name", "front.ReferencedDocument", "source.GetPathName",
        "source.FeatureByName", "silhouette.GetFace", "face.GetFeature", "app.IsSame",
        "face.GetSurface", "surface.IsTorus", "surface.TorusParams",
    ]
    result = drawing._supplier_eye_circle(adapter, front, silhouette)
    assert calls == expected_calls
    calls.clear()
    readback = {}
    assert drawing._supplier_eye_circle(adapter, front, silhouette, readback=readback) == result
    assert calls == expected_calls
    assert readback["stage"] == "accepted_circle"
    assert readback["first_rejection"] is None
    assert readback["owner_same_as_expected"] == 1
    assert readback["torus_params_m"] == list(scene.surface.TorusParams)


def test_failure_census_serializes_nonfinite_values_without_changing_refusal(supplier_eye_census_scene):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    circle = list(scene.eye.GetCurve().CircleParams)
    circle[0] = float("nan")
    scene.eye.GetCurve().CircleParams = tuple(circle)
    packet = _missing_eye_packet(scene)
    assert packet["predicate_time"][0]["first_rejection"] == "circle_finite7"
    assert packet["predicate_time"][0]["circle_params_m"][0] == "nan"
    assert packet["predicate_time"][0]["circle_finite7"] is False
    assert packet["predicate_time"][0]["view_present"] == "unobserved"
    assert packet["kind4"][0]["circle_params_m"][0] == "nan"
    assert packet["kind4"][0]["circle_finite7"] is False
    json.dumps(packet, allow_nan=False)


def test_census_keeps_later_predicate_getter_errors_independent_of_original_refusal(
    supplier_eye_census_scene,
):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye]
    circle = list(scene.eye.GetCurve().CircleParams)
    circle[0] = 1e-8
    scene.eye.GetCurve().CircleParams = tuple(circle)

    def fail(message):
        raise OSError(message)

    scene.eye.GetView = lambda: fail("view getter failed")
    scene.eye.GetFace = lambda: fail("face getter failed")
    scene.source.GetPathName = lambda: fail("path getter failed")
    packet = _missing_eye_packet(scene)
    original, later = packet["predicate_time"][0], packet["kind4"][0]
    assert original["first_rejection"] == "circle_center_matches"
    assert original["circle_center_matches"] is False, "SM's threshold stays strict <1e-8"
    assert original["view_present"] == "unobserved"
    assert later["errors"]["view_present"]["message"] == "view getter failed"
    assert later["errors"]["face_present"]["message"] == "face getter failed"
    assert packet["source"]["errors"]["native_path"]["message"] == "path getter failed"
    assert later["circle_finite7"] is True
    assert packet["source"]["wire_faces"][0]["torus_major_matches"] is True


def test_negative_curve_parameter_control_is_not_sampled(supplier_eye_census_scene):
    scene = supplier_eye_census_scene
    scene.visible[:] = [scene.eye, None]
    curve = scene.eye.GetCurve()
    curve.Identity = lambda: 3005
    curve.IsCircle = lambda: False
    curve.IsLine = lambda: False
    curve.GetEndParams = lambda: (False, 0.0, 1.0, False, False)
    curve.Evaluate2 = lambda *_args: pytest.fail("Negative native parameter control cannot be sampled")
    packet = _missing_eye_packet(scene)
    assert packet["kind4"][0]["end_params"] == [False, 0.0, 1.0, False, False]
    assert packet["kind4"][0]["sample_range_valid"] is False
    assert packet["kind4"][0]["samples"] == []
    assert [row["index"] for row in packet["predicate_time"]] == [0, 1]
    assert [row["first_rejection"] for row in packet["predicate_time"]] == ["is_circle", "raw_present"]

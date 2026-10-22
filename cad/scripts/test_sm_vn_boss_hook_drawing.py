"""Offline manufacturing boundaries for the modified purchased anchor."""

import json
import math
from types import SimpleNamespace

import pytest

import _stock_trim_drawing as trim_drawing
import _drawing_selection as selection
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


@pytest.fixture
def supplier_eye_scene(monkeypatch, tmp_path):
    """Offline native-shaped contracts, not proof of a live SOLIDWORKS pick."""
    def bind(value, kind):
        supported = getattr(value, "_interfaces", None)
        if supported is not None and kind not in supported:
            raise TypeError(f"native object does not expose {kind}")
        return value

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(view_display, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(selection, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", view_display.set_hidden_lines_removed)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(selection, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(selection, "null_callout", lambda: None)
    source_path = tmp_path / "eye.SLDPRT"
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    state = SimpleNamespace(
        mode=2, selected=False, count=1, kind=46, hit=True, active_view=None,
        hlv_seen=False, hlr_seen=False, refreshed=False, sheet="FINISHED",
    )
    queries, projections, picks, dimensions, mappings, clears = [], [], [], [], [], []
    visible_queries, visible = [], []
    observation_calls, selection_reads = [], []
    owner = SimpleNamespace(
        Name="Wire",
        GetTypeName2=lambda: observation_calls.append("Wire.GetTypeName2") or "Sweep",
        GetID=lambda: observation_calls.append("Wire.GetID") or 17,
    )
    drawing_owner = SimpleNamespace(
        Name="Wire", GetTypeName2=lambda: "Sweep", GetID=lambda: 17,
    )
    surface = SimpleNamespace(
        IsTorus=lambda: True,
        TorusParams=(-4.4201138409138974e-11, -1.3548712585881306e-10, 0.0,
                     0.0, 0.0, 1.0, 0.006381749644849558, 0.002413),
    )
    source_face = SimpleNamespace(GetFeature=lambda: owner, GetSurface=lambda: surface)
    bend = SimpleNamespace(
        GetFeature=lambda: owner,
        GetSurface=lambda: SimpleNamespace(
            IsTorus=lambda: True,
            TorusParams=(0.003, -0.009, 0.0, 0.0, 0.0, 1.0, 0.0005, 0.002413),
        ),
    )
    shank = SimpleNamespace(
        GetFeature=lambda: owner,
        GetSurface=lambda: SimpleNamespace(IsTorus=lambda: False),
    )
    faces = [source_face, bend, shank]
    owner.GetFaces = lambda: queries.append("faces") or tuple(faces)
    mapped_faces = {}

    def corresponding(face):
        mappings.append(face)
        return mapped_faces.get(id(face))

    source = SimpleNamespace(
        GetPathName=lambda: queries.append("path") or str(source_path.resolve()),
        FeatureByName=lambda name: queries.append(("feature", name)) or (
            owner if name == "Wire" else None
        ),
        Extension=SimpleNamespace(GetCorrespondingEntity2=corresponding),
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Finished"),
        ),
    )
    front = SimpleNamespace(
        Name="finished-front", ReferencedDocument=source, ReferencedConfiguration="Finished",
        GetDisplayMode2=lambda: state.mode,
        GetVisibleEntities2=lambda *_args: visible_queries.append("visible") or tuple(visible),
        ModelToViewTransform=SimpleNamespace(
            ArrayData=(1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
                       0.100, 0.175, 0.0, 4.0, 0.0, 0.0, 0.0),
        ),
        GetCorrespondingEntity=lambda _face: pytest.fail("reverse mapping is not required"),
    )

    def set_mode(_parent, mode, *_args):
        previous, state.mode = state.mode, mode
        if previous == 2 and mode == 1:
            state.hlv_seen = True
        if previous == 1 and mode == 2 and state.hlv_seen:
            state.hlr_seen = True
        state.refreshed = False
        return previous != mode

    def refresh():
        state.refreshed = True

    front.SetDisplayMode4 = set_mode
    front.UpdateViewDisplayGeometry = refresh

    def contour(diameter=None, attached_source_face=source_face):
        torus = surface.TorusParams
        curve = SimpleNamespace(
            Identity=lambda: observation_calls.append("curve.Identity") or 3002,
            IsLine=lambda: observation_calls.append("curve.IsLine") or False,
            IsCircle=lambda: True,
            CircleParams=(*torus[:3], 0.0, 0.0, 1.0,
                          torus[6] - torus[7] if diameter is None else diameter / 2000),
        )
        face = SimpleNamespace(
            GetFeature=lambda: drawing_owner,
            GetSurface=lambda: observation_calls.append("drawing-face.GetSurface") or surface,
        )
        mapped_faces[id(face)] = attached_source_face
        return SimpleNamespace(
            _interfaces={"ISilhouetteEdge"}, GetCurve=lambda: curve,
            GetFace=lambda: face, GetView=lambda: front,
        )

    eye, outer = contour(), contour(anchor.eye_od_mm)
    state.pick = eye
    native_dimension = SimpleNamespace(FullName="EyeID@native")
    display = SimpleNamespace(GetDimension2=lambda _index: native_dimension)

    def select_by_id(*args):
        assert state.active_view == front.Name
        assert state.hlv_seen and state.hlr_seen and state.mode == 2 and state.refreshed
        assert args[0:2] == ("", "SILHOUETTE")
        assert args[4:] == (0.0, False, 0, None, 0)
        picks.append(args[2:4])
        state.selected = state.hit
        return state.hit

    def clear(_all):
        clears.append(state.selected)
        state.selected = False

    def add_diameter(*point):
        assert state.selected and state.count == 1 and state.kind == 46
        assert state.pick is not None
        dimensions.append((state.pick, point))
        return display

    def selected_count(_mark):
        selection_reads.append(("count", state.selected))
        return state.count if state.selected else 0

    def selected_type(index, _mark):
        selection_reads.append(("type", index, state.selected))
        entries = getattr(state, "entries", None)
        return entries[index - 1][0] if entries is not None else state.kind

    def selected_entity(index, _mark):
        selection_reads.append(("entity", index, state.selected))
        if not state.selected:
            return None
        entries = getattr(state, "entries", None)
        return entries[index - 1][1] if entries is not None else state.pick

    model = SimpleNamespace(
        ActivateView=lambda name: setattr(state, "active_view", name) or True,
        ClearSelection2=clear, AddDiameterDimension2=add_diameter,
        Extension=SimpleNamespace(SelectByID2=select_by_id),
        SelectionManager=SimpleNamespace(
            GetSelectedObjectCount2=selected_count,
            GetSelectedObjectType3=selected_type,
            GetSelectedObject6=selected_entity,
        ),
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second)),
    )

    def project(actual_adapter, view, points, *, label):
        assert actual_adapter is adapter and view is front and label == "EyeID"
        projections.extend(tuple(point) for point in points)
        return [(0.100 + 4.0 * point[0], 0.175 + 4.0 * point[1]) for point in points]

    monkeypatch.setattr(drawing, "model_points_in_view", project)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", lambda _adapter, value, **_kwargs: value)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", lambda *_args, **_kwargs: [])
    return SimpleNamespace(
        adapter=adapter, model=model, state=state, front=front, source=source,
        source_path=source_path, owner=owner, drawing_owner=drawing_owner, surface=surface,
        source_face=source_face, faces=faces, mapped_faces=mapped_faces, mappings=mappings,
        eye=eye, outer=outer, contour=contour, projections=projections, picks=picks,
        dimensions=dimensions, queries=queries, clears=clears,
        visible=visible, visible_queries=visible_queries,
        observation_calls=observation_calls, selection_reads=selection_reads,
    )


@pytest.mark.parametrize("inventory", ("empty", "omits-id"))
def test_primary_pick_projects_actual_source_torus_without_visible_enumeration(
    supplier_eye_scene, inventory,
):
    scene = supplier_eye_scene
    if inventory == "omits-id":
        scene.visible[:] = [scene.outer]
    assert len(scene.faces) == 3
    assert scene.adapter.swApp.IsSame(scene.eye.GetFace().GetFeature(), scene.owner) == 0
    refs = drawing._supplier_references(scene.adapter, scene.front, "Finished")
    cx, cy, cz, _nx, _ny, _nz, major, minor = scene.surface.TorusParams
    assert scene.projections == [(cx, cy + major - minor, cz)]
    assert scene.picks == [(0.100 + 4.0 * cx, 0.175 + 4.0 * (cy + major - minor))]
    assert scene.dimensions == [(scene.eye, (0.150, 0.241, 0.0))]
    assert scene.mappings == [scene.eye.GetFace()]
    assert scene.visible_queries == [], "Coordinate acquisition is primary, not an enumeration rescue"
    assert scene.observation_calls == [], "Failure-only native reads must stay off success"
    assert scene.state.hlv_seen and scene.state.hlr_seen and scene.state.mode == 2
    assert scene.state.selected is False and scene.clears[-1] is True
    assert refs == [("EyeID@native", {
        "label": "EyeID", "expected_mm": spec.SUPPLIER_EYE_ID_MM, "units": "in",
        "precision": drawing.SUPPLIER_REFERENCE_PRECISION["EyeID"], "presentation": "diameter",
        "fraction_denominator": drawing.SUPPLIER_FRACTION_DENOMINATOR,
    })]


@pytest.mark.parametrize("stuck_mode", (1, 2))
def test_existing_hlv_to_hlr_setup_must_succeed_before_querying_the_source(
    supplier_eye_scene, stuck_mode,
):
    scene = supplier_eye_scene
    set_mode = scene.front.SetDisplayMode4

    def refuse_mode(parent, mode, *args):
        return False if mode == stuck_mode else set_mode(parent, mode, *args)

    scene.front.SetDisplayMode4 = refuse_mode
    with pytest.raises(RuntimeError, match="failed to"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.queries == [] and scene.projections == [] and scene.dimensions == []


def test_physical_eye_creation_preserves_imported_machining_controls(supplier_eye_scene, monkeypatch):
    scene = supplier_eye_scene
    monkeypatch.setattr(trim_drawing, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(trim_drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    controls, displays = [], []
    for name, (nominal, lower, upper) in drawing.EXPECTED_CONTROLS.items():
        native = SimpleNamespace(
            DrivenState=2, SystemValue=nominal,
            Tolerance=SimpleNamespace(
                Type=spec.DIMENSION_TOLERANCE_TYPES[name],
                GetMinValue=lambda lower=lower: lower,
                GetMaxValue=lambda upper=upper: upper,
            ),
        )
        display = SimpleNamespace(
            GetDimension2=lambda _index, native=native: native, GetText=lambda _part: "",
            GetPrimaryPrecision2=lambda name=name: spec.DIMENSION_PRECISION[name],
        )
        displays.append(display)
        controls.append(SimpleNamespace(
            name=name, GetSpecificAnnotation=lambda display=display: display,
        ))
    for index, display in enumerate(displays):
        following = displays[index + 1] if index + 1 < len(displays) else None
        display.GetNext5 = lambda following=following: following
    scene.front.GetFirstDisplayDimension6 = lambda: displays[0]
    drawing._verify_controls(scene.adapter, controls)
    drawing._supplier_references(scene.adapter, scene.front, "Finished")
    surviving = []
    display = scene.front.GetFirstDisplayDimension6()
    while display is not None:
        surviving.append(display)
        display = display.GetNext5()
    assert len(surviving) == len(drawing.FRONT_KEEP)
    assert all(actual is expected for actual, expected in zip(surviving, displays))
    drawing._verify_controls(scene.adapter, controls)


@pytest.mark.parametrize("fault", ("wrong-configuration", "wrong-path", "alias-path", "missing-source", "missing-wire"))
def test_acquisition_refuses_wrong_finished_source_before_projection_or_creation(
    supplier_eye_scene, fault,
):
    scene = supplier_eye_scene
    if fault == "wrong-configuration":
        scene.front.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
        scene.source.GetPathName = lambda: pytest.fail("queried source before refusing wrong view configuration")
        scene.source.FeatureByName = lambda _name: pytest.fail("queried Wire in wrong view configuration")
    elif fault == "wrong-path":
        scene.source.GetPathName = lambda: str(scene.source_path.parent / "foreign.SLDPRT")
        scene.source.FeatureByName = lambda _name: pytest.fail("queried Wire in foreign source")
    elif fault == "alias-path":
        scene.source.GetPathName = lambda: str(scene.source_path.parent / "alias" / ".." / scene.source_path.name)
    elif fault == "missing-source":
        scene.front.ReferencedDocument = None
    elif fault == "missing-wire":
        scene.source.FeatureByName = lambda _name: None
    with pytest.raises(RuntimeError, match="unchanged counter eye has no exact ID circular silhouette"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert not scene.projections and not scene.picks and not scene.dimensions
    if fault == "wrong-configuration":
        assert scene.queries == []


@pytest.mark.parametrize("fault", ("missing", "duplicate", "foreign-owner", "missing-owner", "identity-error"))
def test_source_wire_requires_one_native_owned_eye_torus(supplier_eye_scene, fault):
    scene = supplier_eye_scene
    if fault == "missing":
        scene.faces.remove(scene.source_face)
    elif fault == "duplicate":
        scene.faces.append(SimpleNamespace(
            GetFeature=lambda: scene.owner, GetSurface=lambda: scene.surface,
        ))
    elif fault == "foreign-owner":
        scene.source_face.GetFeature = lambda: SimpleNamespace(Name="Wire")
    elif fault == "missing-owner":
        scene.source_face.GetFeature = lambda: None
    elif fault == "identity-error":
        scene.adapter.swApp.IsSame = lambda *_args: -1
    with pytest.raises(RuntimeError, match="requires one authoritative source Wire eye torus"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert not scene.projections and not scene.picks and not scene.dimensions


@pytest.mark.parametrize(
    "fault", ("missing-surface", "nontorus", "short", "long", "center-boundary",
              "wrong-normal", "wrong-major", "wrong-minor", "negative-major", "negative-minor"),
)
def test_invalid_native_source_torus_cannot_supply_a_pick_point(supplier_eye_scene, fault):
    scene = supplier_eye_scene
    if fault == "missing-surface":
        scene.source_face.GetSurface = lambda: None
    elif fault == "nontorus":
        scene.surface.IsTorus = lambda: False
    elif fault == "short":
        scene.surface.TorusParams = scene.surface.TorusParams[:-1]
    elif fault == "long":
        scene.surface.TorusParams += (0.0,)
    else:
        values = list(scene.surface.TorusParams)
        index, value = {
            "center-boundary": (0, 1e-8),
            "wrong-normal": (5, 1.0 - 2e-8),
            "wrong-major": (6, values[6] + 2e-8),
            "wrong-minor": (7, values[7] + 2e-8),
            "negative-major": (6, -values[6]),
            "negative-minor": (7, -values[7]),
        }[fault]
        values[index] = value
        scene.surface.TorusParams = tuple(values)
    with pytest.raises(RuntimeError, match="requires one authoritative source Wire eye torus"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert not scene.projections and not scene.dimensions


@pytest.mark.parametrize("index", range(8))
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_all_native_torus_parameters_must_be_finite(supplier_eye_scene, index, value):
    scene = supplier_eye_scene
    values = list(scene.surface.TorusParams)
    values[index] = value
    scene.surface.TorusParams = tuple(values)
    with pytest.raises(RuntimeError, match="requires one authoritative source Wire eye torus"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert not scene.projections and not scene.dimensions


def _selection_failure_packet(error):
    notes = getattr(error, "__notes__", ())
    assert len(notes) == 1

    def reject_constant(value):
        pytest.fail(f"Failure receipt is not strict JSON: {value}")

    packet = json.loads(notes[0], parse_constant=reject_constant)
    assert packet["kind"] == "sm_eye_id_selection_failure"
    assert "observation_error" not in packet
    return packet


@pytest.mark.parametrize(
    "count,kind,null_helper,stage,original_count,original_type,original_presence,message",
    (
        (0, 46, False, "selected_count", 0, "not_read", "not_read", "expected count=1; actual count=0"),
        (2, 46, False, "selected_count", 2, "not_read", "not_read", "expected count=1; actual count=2"),
        (1, 1, False, "selected_type", 1, 1, "not_read", "expected type=46; actual type=1"),
        (1, 2, False, "selected_type", 1, 2, "not_read", "expected type=46; actual type=2"),
        (1, 46, True, "entity_present", 1, 46, False, "expected entity_present=True; actual entity_present=False"),
    ),
)
def test_individual_predicate_receipts_keep_original_values_and_expected_contract(
    supplier_eye_scene, monkeypatch, count, kind, null_helper, stage,
    original_count, original_type, original_presence, message,
):
    scene = supplier_eye_scene
    scene.state.count, scene.state.kind = count, kind
    if null_helper:
        select = drawing._select_view_entity

        def selected_but_null(*args, **kwargs):
            select(*args, **kwargs)
            return None

        monkeypatch.setattr(drawing, "_select_view_entity", selected_but_null)
    with pytest.raises(RuntimeError, match=message) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    original = packet["original_predicate"]
    assert original["stage"] == stage
    assert original["selected_count"] == original_count
    assert original["selected_type"] == original_type
    assert original["entity_present"] == original_presence
    assert original["helper_return_present"] is not null_helper
    expected = packet["expected"]
    assert (expected["selected_count"], expected["selected_type"], expected["entity_present"]) == (1, 46, True)
    assert expected["physical_id_mm"] == 7.9375
    assert expected["absolute_center_limit_m_exclusive"] == 1e-8
    assert expected["axis_z_error_limit_exclusive"] == 1e-8
    assert expected["diameter_error_limit_mm_exclusive"] == 1e-5
    assert expected["source_owner_IsSame"] == 1
    assert scene.dimensions == [] and scene.state.selected is False
    assert all(read[-1] is True for read in scene.selection_reads)
    if null_helper:
        assert packet["later_readback"]["selection"]["entries"][0]["entity"]["present"] is True


def test_failure_receipt_retains_source_projection_transform_configuration_and_native_wire(
    supplier_eye_scene,
):
    scene = supplier_eye_scene
    scene.state.kind = 1
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    assert packet["acquisition"] == {
        "source_torus": list(scene.surface.TorusParams),
        "model_top_inner_point_m": list(scene.projections[0]),
        "projected_sheet_point_m": list(scene.picks[0]),
    }
    assert packet["expected"]["finished_configuration"] == "Finished"
    assert packet["expected"]["source_path"] == str(scene.source_path.resolve())
    later = packet["later_readback"]
    assert later["view"]["name"]["value"] == scene.front.Name
    assert later["view"]["GetDisplayMode2"]["value"] == 2
    assert later["view"]["ReferencedConfiguration"]["value"] == "Finished"
    assert later["view"]["ArrayData"]["value"]["values"] == list(scene.front.ModelToViewTransform.ArrayData)
    assert later["source"]["GetPathName"]["value"] == str(scene.source_path.resolve())
    assert later["source"]["current_view_source_path"]["value"] == str(scene.source_path.resolve())
    assert later["source"]["active_configuration_name"]["value"] == "Finished"
    assert later["source"]["IsSame_authoritative_document"]["value"] == 1
    assert later["source_Wire"]["Name"]["value"] == "Wire"
    assert later["source_Wire"]["GetTypeName2"]["value"] == "Sweep"
    assert later["source_Wire"]["GetID"]["value"] == 17
    assert later["source_Wire"]["IsSame_self"]["value"] == 1
    assert later["source_Wire"]["IsSame_source_Wire"]["value"] == 1
    geometry = later["selection"]["entries"][0]["entity"]["ISilhouetteEdge"]
    assert geometry["curve"]["CircleParams"]["value"]["values"] == list(scene.eye.GetCurve().CircleParams)
    face = geometry["face"]
    assert face["owner"]["IsSame_source_Wire"]["value"] == 0
    assert face["mapped_source_face"]["owner"]["IsSame_source_Wire"]["value"] == 1
    assert face["mapped_source_face"]["TorusParams"]["value"]["values"] == list(scene.surface.TorusParams)


def test_count_failure_observes_every_selected_entry_including_edge_and_view(supplier_eye_scene):
    scene = supplier_eye_scene
    edge_curve = SimpleNamespace(
        Identity=lambda: 3001, IsCircle=lambda: False, IsLine=lambda: True,
        LineParams=(0.0, 0.001, 0.0, 0.0, 1.0, 0.0),
    )
    first_face = scene.eye.GetFace()
    second_face = SimpleNamespace(GetFeature=lambda: scene.drawing_owner, GetSurface=lambda: scene.surface)
    foreign_owner = SimpleNamespace(Name="Wire", GetTypeName2=lambda: "Sweep", GetID=lambda: 44)
    scene.mapped_faces[id(second_face)] = SimpleNamespace(
        GetFeature=lambda: foreign_owner, GetSurface=lambda: scene.surface,
    )
    edge = SimpleNamespace(
        _interfaces={"IEdge"}, GetCurve=lambda: edge_curve,
        GetTwoAdjacentFaces2=lambda: (first_face, second_face),
    )
    scene.state.entries = [(46, scene.eye), (1, edge), (12, scene.front)]
    scene.state.count = 3
    with pytest.raises(RuntimeError, match="actual count=3") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    entries = packet["later_readback"]["selection"]["entries"]
    assert [entry["index"] for entry in entries] == [1, 2, 3]
    assert [entry["GetSelectedObjectType3"]["value"] for entry in entries] == [46, 1, 12]
    assert all(entry["GetSelectedObject6"]["present"] for entry in entries)
    native_edge = entries[1]["entity"]["IEdge"]
    assert entries[1]["entity"]["ISilhouetteEdge"]["ISilhouetteEdge"]["error"]["type"] == "TypeError"
    assert native_edge["curve"]["Identity"]["value"] == 3001
    assert native_edge["curve"]["IsCircle"]["value"] is False
    assert native_edge["curve"]["LineParams"]["value"]["values"] == list(edge_curve.LineParams)
    faces = native_edge["adjacent_faces"]
    assert len(faces) == 2
    assert faces[0]["mapped_source_face"]["owner"]["IsSame_source_Wire"]["value"] == 1
    assert faces[1]["mapped_source_face"]["owner"]["IsSame_source_Wire"]["value"] == 0
    assert faces[1]["mapped_source_face"]["owner"]["Name"]["value"] == "Wire"
    assert entries[2]["entity"]["drawing_view"]["name"]["value"] == scene.front.Name
    assert "ISilhouetteEdge" not in entries[2]["entity"]
    assert scene.dimensions == [] and scene.visible_queries == []


@pytest.mark.parametrize("predicate", ("count", "type"))
def test_later_successful_readback_cannot_overwrite_original_failed_predicate(supplier_eye_scene, predicate):
    scene = supplier_eye_scene
    if predicate == "count":
        values = iter((1, 2, 1))  # helper, original guard, independent later read
        scene.model.SelectionManager.GetSelectedObjectCount2 = lambda _mark: next(values)
    else:
        values = iter((1, 46))  # original guard, independent later read
        scene.model.SelectionManager.GetSelectedObjectType3 = lambda _index, _mark: next(values)
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    original, later = packet["original_predicate"], packet["later_readback"]["selection"]
    if predicate == "count":
        assert original["selected_count"] == 2 and original["selected_type"] == "not_read"
        assert later["GetSelectedObjectCount2"]["value"] == 1
    else:
        assert original["selected_type"] == 1 and original["entity_present"] == "not_read"
        assert later["entries"][0]["GetSelectedObjectType3"]["value"] == 46
    assert scene.dimensions == []


def test_wrong_kind_native_edge_curve_is_observed_without_accepting_it(supplier_eye_scene):
    scene = supplier_eye_scene
    scene.state.kind = 1
    scene.state.pick = SimpleNamespace(
        _interfaces={"IEdge"}, GetCurve=scene.eye.GetCurve,
        GetTwoAdjacentFaces2=lambda: (scene.eye.GetFace(), None),
    )
    with pytest.raises(RuntimeError, match="expected type=46; actual type=1") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    entity = packet["later_readback"]["selection"]["entries"][0]["entity"]
    assert entity["IEdge"]["curve"]["IsCircle"]["value"] is True
    assert entity["IEdge"]["curve"]["CircleParams"]["value"]["sample_all_finite"] is True
    assert entity["IEdge"]["adjacent_faces"][1]["IFace2"]["present"] is False
    assert entity["ISilhouetteEdge"]["ISilhouetteEdge"]["error"]["field"] == "ISilhouetteEdge"
    assert scene.dimensions == []


def test_exact_circle_refusal_gets_the_same_complete_packet(supplier_eye_scene):
    scene = supplier_eye_scene
    scene.state.pick = scene.outer
    with pytest.raises(RuntimeError, match="expected physical ID=7.9375 mm") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    original = packet["original_predicate"]
    assert (original["selected_count"], original["selected_type"], original["entity_present"]) == (1, 46, True)
    assert original["stage"] == "exact_source_circle"
    entry = packet["later_readback"]["selection"]["entries"][0]
    circle = entry["entity"]["ISilhouetteEdge"]["curve"]["CircleParams"]["value"]["values"]
    assert circle[6] * 2000 == pytest.approx(anchor.eye_od_mm)
    assert "mapped_source_face" in entry["entity"]["ISilhouetteEdge"]["face"]
    assert packet["acquisition"]["model_top_inner_point_m"] == list(scene.projections[0])
    assert scene.dimensions == []


def test_helper_native_failure_keeps_identity_and_known_model_sheet_context(supplier_eye_scene):
    scene = supplier_eye_scene
    error = OSError("native coordinate hit-test failed")

    def fail(*_args):
        raise error

    scene.model.Extension.SelectByID2 = fail
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error and str(caught.value) == "native coordinate hit-test failed"
    packet = _selection_failure_packet(error)
    original = packet["original_predicate"]
    assert original["stage"] == "select_view_entity"
    assert original["helper_return_present"] == "not_returned"
    assert original["selected_count"] == original["selected_type"] == original["entity_present"] == "not_read"
    model_point = scene.projections[0]
    assert packet["acquisition"]["model_top_inner_point_m"] == list(model_point)
    assert packet["acquisition"]["projected_sheet_point_m"] == [
        0.100 + 4.0 * model_point[0], 0.175 + 4.0 * model_point[1],
    ]
    assert packet["later_readback"]["selection"]["GetSelectedObjectCount2"]["value"] == 0
    assert packet["later_readback"]["view"]["ArrayData"]["value"]["length"] == 16
    assert scene.state.selected is False and scene.dimensions == []


def test_observation_field_errors_are_independent_and_do_not_mask_native_exception(supplier_eye_scene):
    scene = supplier_eye_scene
    error = OSError("native curve failed")

    def fail_curve():
        raise error

    def fail_owner():
        raise ValueError("owner unreadable")

    def fail_surface():
        raise LookupError("surface unreadable")

    scene.eye.GetCurve = fail_curve
    scene.eye.GetFace().GetFeature = fail_owner
    scene.eye.GetFace().GetSurface = fail_surface
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error and str(caught.value) == "native curve failed"
    packet = _selection_failure_packet(error)
    geometry = packet["later_readback"]["selection"]["entries"][0]["entity"]["ISilhouetteEdge"]
    assert geometry["GetCurve"]["error"] == {
        "field": "GetCurve", "type": "OSError", "message": "native curve failed",
    }
    assert geometry["face"]["GetFeature"]["error"]["type"] == "ValueError"
    assert geometry["face"]["GetSurface"]["error"]["type"] == "LookupError"
    assert geometry["face"]["mapped_source_face"]["owner"]["IsSame_source_Wire"]["value"] == 1
    assert geometry["view"]["name"]["value"] == scene.front.Name
    assert scene.state.selected is False and scene.dimensions == []


def test_selected_getters_remain_independent_when_later_type_read_fails(supplier_eye_scene):
    scene = supplier_eye_scene
    calls = []

    def type_read(_index, _mark):
        calls.append("type")
        if len(calls) == 1:
            return 1
        raise OSError("later type unavailable")

    scene.model.SelectionManager.GetSelectedObjectType3 = type_read
    with pytest.raises(RuntimeError, match="actual type=1") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    entry = packet["later_readback"]["selection"]["entries"][0]
    assert packet["original_predicate"]["selected_type"] == 1
    assert entry["GetSelectedObjectType3"]["error"]["message"] == "later type unavailable"
    assert entry["GetSelectedObject6"]["present"] is True
    assert entry["entity"]["ISilhouetteEdge"]["curve"]["IsCircle"]["value"] is True


@pytest.mark.parametrize("value,encoded", ((math.nan, "NaN"), (math.inf, "Infinity"), (-math.inf, "-Infinity")))
def test_failure_receipt_bounds_numeric_samples_and_strings_and_sanitizes_nonfinite(
    supplier_eye_scene, value, encoded,
):
    scene = supplier_eye_scene
    scene.eye.GetCurve().CircleParams = (value,) * 40
    scene.front.ModelToViewTransform.ArrayData = (value,) * 40
    scene.owner.Name = "W" * 2000
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    curve = packet["later_readback"]["selection"]["entries"][0]["entity"]["ISilhouetteEdge"]["curve"]
    for sample in (curve["CircleParams"]["value"], packet["later_readback"]["view"]["ArrayData"]["value"]):
        assert sample["length"] == 40
        assert sample["values"] == [encoded] * 16
        assert sample["sample_truncated"] is True and sample["sample_all_finite"] is False
    assert len(packet["later_readback"]["source_Wire"]["Name"]["value"]) == 512
    assert scene.dimensions == [] and scene.state.selected is False


def test_success_never_invokes_the_failure_observer(supplier_eye_scene, monkeypatch):
    scene = supplier_eye_scene

    def unexpected(*_args, **_kwargs):
        pytest.fail("Successful selection invoked the failure observer")

    monkeypatch.setattr(drawing, "_supplier_eye_selection_observation", unexpected)
    drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.selection_reads == [("count", True), ("entity", 1, True), ("count", True), ("type", 1, True)]
    assert scene.observation_calls == [] and len(scene.dimensions) == 1


@pytest.mark.parametrize(
    "member,stage", (
        ("GetSelectedObjectCount2", "selected_count"),
        ("GetSelectedObjectType3", "selected_type"),
        ("GetSelectedObject6", "select_view_entity"),
    ),
)
def test_native_selection_getter_errors_preserve_identity_and_record_unreadable_not_null(
    supplier_eye_scene, member, stage,
):
    scene = supplier_eye_scene
    error = OSError(f"native {member} failed")
    manager = scene.model.SelectionManager
    native = getattr(manager, member)
    calls = []

    def fail(*args):
        calls.append(args)
        if member == "GetSelectedObjectCount2" and len(calls) == 1:
            return native(*args)  # The helper completed; the original guard fails.
        raise error

    setattr(manager, member, fail)
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error and str(error) == f"native {member} failed"
    packet = _selection_failure_packet(error)
    assert packet["original_predicate"]["stage"] == stage
    later = packet["later_readback"]["selection"]
    if member == "GetSelectedObjectCount2":
        assert packet["original_predicate"]["selected_count"] == "not_read"
        assert later[member]["error"]["message"] == str(error)
        assert later["entries"] == []
    else:
        entry = later["entries"][0]
        assert entry[member]["error"]["message"] == str(error)
        if member == "GetSelectedObjectType3":
            assert packet["original_predicate"]["selected_type"] == "not_read"
            assert entry["GetSelectedObject6"]["present"] is True
        else:
            assert entry["GetSelectedObjectType3"]["value"] == 46
            assert entry["entity"] == {"presence": "unreadable"}
    assert scene.state.selected is False and scene.dimensions == []


def test_later_null_selection_is_explicit_without_changing_original_helper_failure(supplier_eye_scene):
    scene = supplier_eye_scene
    scene.state.pick = None
    with pytest.raises(RuntimeError, match="has no entity") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    assert packet["original_predicate"]["helper_return_present"] == "not_returned"
    entry = packet["later_readback"]["selection"]["entries"][0]
    assert entry["GetSelectedObject6"] == {"present": False}
    assert entry["entity"] == {"present": False}


def test_cleanup_failure_cannot_replace_the_original_native_failure(supplier_eye_scene):
    scene = supplier_eye_scene
    error, cleanup_error = OSError("native curve failed"), OSError("native clear failed")
    clear = scene.model.ClearSelection2

    def fail_curve():
        raise error

    def fail_final_clear(all_selected):
        if scene.state.selected:
            assert len(error.__notes__) == 1, "Receipt must be attached before clearing selection"
            raise cleanup_error
        clear(all_selected)  # The helper's pre-pick clear is unchanged.

    scene.eye.GetCurve = fail_curve
    scene.model.ClearSelection2 = fail_final_clear
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error and error.__cause__ is cleanup_error
    assert str(error) == "native curve failed"
    _selection_failure_packet(error)
    assert scene.dimensions == []


def test_selected_native_view_source_is_recorded_separately_from_authoritative_front(supplier_eye_scene):
    scene = supplier_eye_scene
    foreign_path = "D:/foreign/eye.SLDPRT"
    scene.source.ConfigurationManager.ActiveConfiguration.Name = "Other active source configuration"
    scene.eye.GetView = lambda: SimpleNamespace(
        Name="foreign-native-view", ReferencedConfiguration="Foreign configuration",
        ReferencedDocument=SimpleNamespace(GetPathName=lambda: foreign_path),
        GetDisplayMode2=lambda: 1, ModelToViewTransform=scene.front.ModelToViewTransform,
    )
    with pytest.raises(RuntimeError, match="no exact ID circular silhouette") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    assert packet["original_predicate"]["exact_source_circle"] is False
    assert packet["expected"]["finished_configuration"] == "Finished"
    later = packet["later_readback"]
    assert later["view"]["source_path"]["value"] == str(scene.source_path.resolve())
    assert later["view"]["ReferencedConfiguration"]["value"] == "Finished"
    assert later["source"]["active_configuration_name"]["value"] == "Other active source configuration"
    selected_view = later["selection"]["entries"][0]["entity"]["ISilhouetteEdge"]["view"]
    assert selected_view["name"]["value"] == "foreign-native-view"
    assert selected_view["GetDisplayMode2"]["value"] == 1
    assert selected_view["ReferencedConfiguration"]["value"] == "Foreign configuration"
    assert selected_view["source_path"]["value"] == foreign_path
    assert scene.dimensions == [] and scene.state.selected is False


@pytest.mark.parametrize("mapping_fault", ("null", "native-error"))
def test_failure_receipt_records_source_mapping_result_or_error_without_substituting_owner(
    supplier_eye_scene, mapping_fault,
):
    scene = supplier_eye_scene
    error = OSError("native drawing-to-source mapping failed")

    def mapping(_face):
        if mapping_fault == "native-error":
            raise error
        return None

    scene.source.Extension.GetCorrespondingEntity2 = mapping
    expected_error = OSError if mapping_fault == "native-error" else RuntimeError
    with pytest.raises(expected_error) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    if mapping_fault == "native-error":
        assert caught.value is error
    packet = _selection_failure_packet(caught.value)
    face = packet["later_readback"]["selection"]["entries"][0]["entity"]["ISilhouetteEdge"]["face"]
    if mapping_fault == "native-error":
        assert face["GetCorrespondingEntity2"]["error"] == {
            "field": "GetCorrespondingEntity2", "type": "OSError",
            "message": "native drawing-to-source mapping failed",
        }
    else:
        assert face["GetCorrespondingEntity2"] == {"present": False}
    assert face["mapped_source_face"]["IFace2"] == {"present": False}
    assert face["owner"]["Name"]["value"] == "Wire"
    assert face["owner"]["IsSame_source_Wire"]["value"] == 0
    assert scene.dimensions == [] and scene.state.selected is False


def test_adjacent_face_getter_error_does_not_hide_wrong_kind_curve(supplier_eye_scene):
    scene = supplier_eye_scene
    scene.state.kind = 1

    def fail_faces():
        raise OSError("native adjacent faces unavailable")

    scene.state.pick = SimpleNamespace(
        _interfaces={"IEdge"}, GetCurve=scene.eye.GetCurve,
        GetTwoAdjacentFaces2=fail_faces,
    )
    with pytest.raises(RuntimeError, match="actual type=1") as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    packet = _selection_failure_packet(caught.value)
    edge = packet["later_readback"]["selection"]["entries"][0]["entity"]["IEdge"]
    assert edge["curve"]["IsCircle"]["value"] is True
    assert edge["GetTwoAdjacentFaces2"]["error"] == {
        "field": "GetTwoAdjacentFaces2", "type": "OSError",
        "message": "native adjacent faces unavailable",
    }
    assert scene.dimensions == [] and scene.state.selected is False


@pytest.mark.parametrize("count,kind,pick", ((0, 46, "eye"), (2, 46, "eye"), (1, 1, "eye"), (1, 2, "eye"), (1, 46, "null")))
def test_coordinate_hit_must_leave_one_nonnull_type46_selection(
    supplier_eye_scene, count, kind, pick,
):
    scene = supplier_eye_scene
    scene.state.count, scene.state.kind = count, kind
    if pick == "null":
        scene.state.pick = None
    with pytest.raises(RuntimeError):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert len(scene.picks) == 1 and scene.dimensions == []
    assert scene.state.selected is False and scene.clears[-1] is True


@pytest.mark.parametrize(
    "fault", ("outer", "unrelated-circle", "missing-curve", "noncircle", "short-circle",
              "long-circle", "center-boundary", "wrong-normal", "wrong-radius",
              "missing-view", "wrong-view", "wrong-native-configuration",
              "missing-face", "missing-extension", "null-correspondence", "foreign-owner",
              "missing-owner", "not-same", "mapped-wrong-torus"),
)
def test_selected_contour_must_prove_exact_id_and_mapped_source_wire(supplier_eye_scene, fault):
    scene = supplier_eye_scene
    curve = scene.eye.GetCurve()
    if fault == "outer":
        scene.state.pick = scene.outer
    elif fault == "unrelated-circle":
        curve.CircleParams = (0.002, -0.009, 0.0, *curve.CircleParams[3:])
    elif fault == "missing-curve":
        scene.eye.GetCurve = lambda: None
    elif fault == "noncircle":
        curve.IsCircle = lambda: False
    elif fault == "short-circle":
        curve.CircleParams = curve.CircleParams[:-1]
    elif fault == "long-circle":
        curve.CircleParams += (0.0,)
    elif fault in ("center-boundary", "wrong-normal", "wrong-radius"):
        values = list(curve.CircleParams)
        index, value = {
            "center-boundary": (0, 1e-8),
            "wrong-normal": (5, 1.0 - 2e-8),
            "wrong-radius": (6, values[6] + 2e-8),
        }[fault]
        values[index] = value
        curve.CircleParams = tuple(values)
    elif fault == "missing-view":
        scene.eye.GetView = lambda: None
    elif fault == "wrong-view":
        scene.eye.GetView = lambda: SimpleNamespace(Name="other-front")
    elif fault == "wrong-native-configuration":
        scene.eye.GetView = lambda: SimpleNamespace(
            Name=scene.front.Name, ReferencedConfiguration="other",
        )
    elif fault == "missing-face":
        scene.eye.GetFace = lambda: None
    elif fault == "missing-extension":
        scene.source.Extension = None
    elif fault == "null-correspondence":
        scene.mapped_faces.clear()
    else:
        mapped_surface = SimpleNamespace(IsTorus=lambda: True, TorusParams=scene.surface.TorusParams)
        mapped_owner = scene.owner
        if fault == "foreign-owner":
            mapped_owner = SimpleNamespace(Name="Wire")
        elif fault == "missing-owner":
            mapped_owner = None
        elif fault == "not-same":
            original_same = scene.adapter.swApp.IsSame
            scene.adapter.swApp.IsSame = lambda first, second: (
                0 if first is mapped_owner else original_same(first, second)
            )
            # Keep source acquisition valid; this distinct owner is returned
            # only by the drawing-to-source correspondence.
            mapped_owner = SimpleNamespace(Name="Wire")
        elif fault == "mapped-wrong-torus":
            values = list(mapped_surface.TorusParams)
            values[6] += 0.001
            mapped_surface.TorusParams = tuple(values)
        scene.mapped_faces[id(scene.eye.GetFace())] = SimpleNamespace(
            GetFeature=lambda: mapped_owner, GetSurface=lambda: mapped_surface,
        )
    with pytest.raises(RuntimeError, match="unchanged counter eye has no exact ID circular silhouette"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.dimensions == [] and scene.state.selected is False
    assert scene.clears[-1] is True


@pytest.mark.parametrize("index", range(7))
@pytest.mark.parametrize("value", (math.nan, math.inf, -math.inf))
def test_all_selected_circle_parameters_must_be_finite(supplier_eye_scene, index, value):
    scene = supplier_eye_scene
    curve = scene.eye.GetCurve()
    values = list(curve.CircleParams)
    values[index] = value
    curve.CircleParams = tuple(values)
    with pytest.raises(RuntimeError, match="unchanged counter eye has no exact ID circular silhouette"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.dimensions == [] and scene.state.selected is False


@pytest.mark.parametrize("direct_owner", ("source", "drawing-proxy"))
def test_even_apparently_native_faces_require_source_correspondence(supplier_eye_scene, direct_owner):
    scene = supplier_eye_scene
    face = scene.eye.GetFace()
    if direct_owner == "source":
        face.GetFeature = lambda: scene.owner
    scene.source.Extension.GetCorrespondingEntity2 = lambda _face: None
    assert drawing._supplier_eye_circle(scene.adapter, scene.front, scene.eye, "Finished") is None


@pytest.mark.parametrize(
    "operation", ("GetFaces", "projection", "SelectByID2", "GetCurve", "GetCorrespondingEntity2", "AddDiameterDimension2"),
)
def test_native_failure_is_not_suppressed_retried_or_replaced(supplier_eye_scene, monkeypatch, operation):
    scene = supplier_eye_scene
    error = OSError(f"native {operation} failed")
    calls = []

    def fail(*_args, **_kwargs):
        calls.append(operation)
        raise error

    if operation == "GetFaces":
        scene.owner.GetFaces = fail
    elif operation == "projection":
        monkeypatch.setattr(drawing, "model_points_in_view", fail)
    elif operation == "SelectByID2":
        scene.model.Extension.SelectByID2 = fail
    elif operation == "GetCurve":
        scene.eye.GetCurve = fail
    elif operation == "GetCorrespondingEntity2":
        scene.source.Extension.GetCorrespondingEntity2 = fail
    elif operation == "AddDiameterDimension2":
        scene.model.AddDiameterDimension2 = fail
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error
    if operation in ("GetFaces", "projection"):
        assert calls == [operation] and not getattr(error, "__notes__", ())
    else:
        # The independent failure readback may revisit a failed getter, but
        # never retries acquisition or dimension creation as an acceptance path.
        assert calls == [operation] * (2 if operation in ("GetCurve", "GetCorrespondingEntity2") else 1)
        packet = _selection_failure_packet(error)
        assert packet["original_predicate"]["failure"] == {
            "type": "OSError", "message": f"native {operation} failed",
        }
    assert scene.state.selected is False and scene.visible_queries == []


def test_null_native_dimension_still_clears_the_verified_selection(supplier_eye_scene):
    scene = supplier_eye_scene
    scene.model.AddDiameterDimension2 = lambda *_args: None
    with pytest.raises(RuntimeError, match="cannot dimension the counter eye ID silhouette"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.mappings == [scene.eye.GetFace()]
    assert scene.state.selected is False and scene.clears[-1] is True


def _settled_supplier_scene(scene, monkeypatch):
    """Install complete per-sheet native dimensions with fresh attachment getters."""
    monkeypatch.setattr(drawing, "assert_supplier_reference_dimension", lambda *_args, **_kwargs: None)
    state = scene.state
    scene.model.ActivateSheet = lambda name: setattr(state, "sheet", name) or True
    iso = SimpleNamespace(Name="finished-iso", ReferencedConfiguration="Finished")
    stock = SimpleNamespace(
        Name="stock-front", ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
    )
    refs_by_sheet, contracts, displays_by_sheet = {}, {}, {}
    attachment = SimpleNamespace(entities=[scene.eye], kinds=[46], dangling=False, count=1)
    annotation = SimpleNamespace(
        GetAttachedEntities3=lambda: tuple(attachment.entities),
        GetAttachedEntityTypes=lambda: tuple(attachment.kinds),
        GetAttachedEntityCount3=lambda: attachment.count,
        IsDangling=lambda: attachment.dangling,
    )
    for sheet_name, view, names, configuration in (
        ("FINISHED", scene.front, ("EyeID", "SupplierThreadMajor"), "Finished"),
        ("SUPPLIER-STOCK", stock,
         ("SupplierNominalEyeOD", "SupplierNominalWire", "SupplierStockShank", "SupplierStockOverall"),
         drawing.SUPPLIER_STOCK_CONFIGURATION),
    ):
        displays, refs = [], []
        for name in names:
            feature = (
                "native" if name == "EyeID" else drawing.SUPPLIER_THREAD_FEATURE
                if name == "SupplierThreadMajor" else drawing.SUPPLIER_STOCK_FEATURE
            )
            key = f"{name}@{feature}@eye.SLDPRT"
            native = SimpleNamespace(FullName=key, Tolerance=SimpleNamespace(Type=0), DrivenState=1)
            display = SimpleNamespace(
                GetDimension2=lambda _index, native=native: native,
                GetAnnotation=lambda: annotation,
            )
            displays.append(display)
            refs.append((key, {"label": name}))
        if sheet_name == "FINISHED":
            for name in drawing.FRONT_KEEP:
                native = SimpleNamespace(FullName=f"{name}@machining@eye.SLDPRT")
                displays.append(SimpleNamespace(GetDimension2=lambda _index, native=native: native))
        for index, display in enumerate(displays):
            following = displays[index + 1] if index + 1 < len(displays) else None
            display.GetNext5 = lambda following=following: following
        view.GetFirstDisplayDimension6 = lambda displays=displays: displays[0]
        refs_by_sheet[sheet_name], displays_by_sheet[sheet_name] = refs, displays
        contracts[sheet_name] = (
            (scene.front.Name, iso.Name) if sheet_name == "FINISHED" else (stock.Name,),
            configuration,
        )

    def no_mutation(*_args):
        pytest.fail("settled geometry proof mutated a view, rebuilt, selected, or activated source configuration")

    scene.front.UpdateViewDisplayGeometry = no_mutation
    scene.model.EditRebuild3 = no_mutation
    scene.model.ForceRebuild3 = no_mutation
    scene.model.ActivateView = no_mutation
    scene.model.Extension.SelectByID2 = no_mutation
    scene.source.ShowConfiguration2 = no_mutation
    scene.source.EditRebuild3 = no_mutation
    scene.source.ForceRebuild3 = no_mutation
    monkeypatch.setattr(drawing, "model_points_in_view", no_mutation)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", no_mutation)
    monkeypatch.setattr(
        drawing, "iter_views",
        lambda _adapter: (scene.front, iso) if state.sheet == "FINISHED" else (stock,),
    )
    return SimpleNamespace(
        refs=refs_by_sheet, contracts=contracts, attachment=attachment,
        displays=displays_by_sheet, stock=stock, iso=iso,
    )


@pytest.mark.parametrize(
    "fault", (None, "missing", "null", "multiple", "wrong-kind", "wrong-count", "dangling",
              "outer", "unrelated-circle", "foreign-owner", "null-correspondence",
              "wrong-torus", "wrong-path", "wrong-configuration", "wrong-iso-configuration",
              "missing-dimension", "extra-dimension", "tolerance"),
)
def test_rebuild_and_native_save_reacquire_strict_attached_geometry_without_repairs(
    supplier_eye_scene, monkeypatch, fault,
):
    scene = supplier_eye_scene
    settled = _settled_supplier_scene(scene, monkeypatch)
    drawing._verify_supplier_references(scene.adapter, settled.refs, settled.contracts)
    for phase in ("after-rebuild", "after-native-save"):
        old_eye, old_face = settled.attachment.entities[0], scene.source_face
        fresh_surface = SimpleNamespace(IsTorus=lambda: True, TorusParams=scene.surface.TorusParams)
        fresh_face = SimpleNamespace(GetFeature=lambda: scene.owner, GetSurface=lambda: fresh_surface)
        fresh_eye = scene.contour(attached_source_face=fresh_face)
        settled.attachment.entities = [fresh_eye]
        scene.source_face = fresh_face
        old_eye.GetCurve = lambda: pytest.fail("read an obsolete attached silhouette")
        old_face.GetFeature = lambda: pytest.fail("read an obsolete source face")
        if phase == "after-native-save":
            if fault == "missing":
                settled.attachment.entities = []
                settled.attachment.count = 0
            elif fault == "null":
                settled.attachment.entities = [None]
            elif fault == "multiple":
                settled.attachment.entities *= 2
                settled.attachment.kinds *= 2
                settled.attachment.count = 2
            elif fault == "wrong-kind":
                settled.attachment.kinds = [1]
            elif fault == "wrong-count":
                settled.attachment.count = 2
            elif fault == "dangling":
                settled.attachment.dangling = True
            elif fault == "outer":
                settled.attachment.entities = [scene.contour(anchor.eye_od_mm, fresh_face)]
            elif fault == "unrelated-circle":
                values = list(fresh_eye.GetCurve().CircleParams)
                values[1] = -0.009
                fresh_eye.GetCurve().CircleParams = tuple(values)
            elif fault == "foreign-owner":
                fresh_face.GetFeature = lambda: SimpleNamespace(Name="Wire")
            elif fault == "null-correspondence":
                scene.mapped_faces.clear()
            elif fault == "wrong-torus":
                values = list(fresh_surface.TorusParams)
                values[7] += 0.001
                fresh_surface.TorusParams = tuple(values)
            elif fault == "wrong-path":
                scene.source.GetPathName = lambda: "D:/foreign.SLDPRT"
            elif fault == "wrong-configuration":
                scene.front.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
            elif fault == "wrong-iso-configuration":
                settled.iso.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
            elif fault == "missing-dimension":
                settled.displays["FINISHED"][0].GetDimension2(0).FullName = "lost@other"
            elif fault == "extra-dimension":
                previous = scene.front.GetFirstDisplayDimension6()
                extra = SimpleNamespace(
                    GetDimension2=lambda _index: SimpleNamespace(FullName="extra@other"),
                    GetNext5=lambda: previous,
                )
                scene.front.GetFirstDisplayDimension6 = lambda: extra
            elif fault == "tolerance":
                settled.displays["FINISHED"][0].GetDimension2(0).Tolerance.Type = 1
        if phase == "after-native-save" and fault is not None:
            with pytest.raises(RuntimeError):
                drawing._verify_supplier_references(scene.adapter, settled.refs, settled.contracts)
        else:
            before = len(scene.mappings)
            drawing._verify_supplier_references(scene.adapter, settled.refs, settled.contracts)
            assert len(scene.mappings) == before + 1 and scene.mappings[-1] is fresh_eye.GetFace()
    assert scene.picks == [] and scene.projections == [] and scene.visible_queries == []

"""Offline manufacturing boundaries for the modified purchased anchor."""

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
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
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
    owner = SimpleNamespace(Name="Wire")
    drawing_owner = SimpleNamespace(Name="Wire")
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
    )
    front = SimpleNamespace(
        Name="finished-front", ReferencedDocument=source, ReferencedConfiguration="Finished",
        GetDisplayMode2=lambda: state.mode,
        GetVisibleEntities2=lambda *_args: visible_queries.append("visible") or tuple(visible),
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
            IsCircle=lambda: True,
            CircleParams=(*torus[:3], 0.0, 0.0, 1.0,
                          torus[6] - torus[7] if diameter is None else diameter / 2000),
        )
        face = SimpleNamespace(
            GetFeature=lambda: drawing_owner,
            GetSurface=lambda: pytest.fail("read torus in drawing context instead of source"),
        )
        mapped_faces[id(face)] = attached_source_face
        return SimpleNamespace(GetCurve=lambda: curve, GetFace=lambda: face, GetView=lambda: front)

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

    model = SimpleNamespace(
        ActivateView=lambda name: setattr(state, "active_view", name) or True,
        ClearSelection2=clear, AddDiameterDimension2=add_diameter,
        Extension=SimpleNamespace(SelectByID2=select_by_id),
        SelectionManager=SimpleNamespace(
            GetSelectedObjectCount2=lambda _mark: state.count if state.selected else 0,
            GetSelectedObjectType3=lambda _index, _mark: state.kind,
            GetSelectedObject6=lambda _index, _mark: state.pick if state.selected else None,
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
    assert caught.value is error and calls == [operation]
    assert not getattr(error, "__notes__", ())
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

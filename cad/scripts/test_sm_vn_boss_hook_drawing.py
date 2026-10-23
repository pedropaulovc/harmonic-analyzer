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
    """Native-shaped coordinate pick and direct Select2, without real COM."""
    def bind(value, kind):
        supported = getattr(value, "_interfaces", None)
        if supported is not None and kind not in supported:
            raise TypeError(f"native object does not expose {kind}")
        return value

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(view_display, "_early_bound", bind)
    monkeypatch.setattr(selection, "_early_bound", bind)
    monkeypatch.setattr(
        selection._sw_type_info, "early_bound_or_flag",
        lambda value, kind, _member: bind(value, kind),
    )
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", view_display.set_hidden_lines_removed)
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(selection, "view_name", lambda _adapter, view: view.Name)
    monkeypatch.setattr(selection, "null_callout", lambda: None)
    source_path = tmp_path / "eye.SLDPRT"
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    state = SimpleNamespace(
        mode=2, selected=False, count=1, kind=46, hit=True, active_view=None,
        hlv_seen=False, hlr_seen=False, refreshed=False, sheet="FINISHED",
        single_reselected=False, after_reselect=None,
    )
    queries, projections, picks, reselections, dimensions, mappings, clears = (
        [], [], [], [], [], [], [],
    )
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
        face = SimpleNamespace(GetFeature=lambda: drawing_owner)
        mapped_faces[id(face)] = attached_source_face
        silhouette = SimpleNamespace(
            _interfaces={"ISilhouetteEdge"}, GetCurve=lambda: curve,
            GetFace=lambda: face, GetView=lambda: front,
        )

        def select(append, data):
            assert append is False and data.View is front
            assert state.active_view == front.Name and not state.selected
            reselections.append((silhouette, append, data.View))
            state.selected = state.single_reselected = True
            state.count, state.kind, state.pick, state.entries = 1, 46, silhouette, None
            if state.after_reselect is not None:
                state.after_reselect()
            return True

        silhouette.Select2 = select
        return silhouette

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
        assert state.selected and state.single_reselected
        assert state.count == 1 and state.kind == 46 and state.pick is not None
        dimensions.append((state.pick, point))
        return display

    def selected_count(_mark):
        return state.count if state.selected else 0

    def selected_type(index, _mark):
        entries = getattr(state, "entries", None)
        return entries[index - 1][0] if entries is not None else state.kind

    def selected_entity(index, _mark):
        if not state.selected or not 1 <= index <= state.count:
            return None
        entries = getattr(state, "entries", None)
        return entries[index - 1][1] if entries is not None else state.pick

    model = SimpleNamespace(
        ActivateView=lambda name: setattr(state, "active_view", name) or True,
        ClearSelection2=clear, AddDiameterDimension2=add_diameter,
        Extension=SimpleNamespace(SelectByID2=select_by_id),
        SelectionManager=SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(View=None),
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
        reselections=reselections, dimensions=dimensions, queries=queries, clears=clears,
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
    assert scene.mappings == [scene.eye.GetFace(), scene.eye.GetFace()]
    assert scene.visible_queries == [], "Coordinate acquisition is primary, not an enumeration rescue"
    assert scene.state.hlv_seen and scene.state.hlr_seen and scene.state.mode == 2
    assert scene.reselections == [(scene.eye, False, scene.front)]
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


@pytest.mark.parametrize("parent_position", (None, "first", "last"))
def test_coordinate_pick_always_reselects_only_the_proven_physical_silhouette(
    supplier_eye_scene, parent_position,
):
    scene = supplier_eye_scene
    if parent_position is not None:
        scene.state.entries = (
            [(12, scene.front), (46, scene.eye)]
            if parent_position == "first" else [(46, scene.eye), (12, scene.front)]
        )
        scene.state.count = 2
    drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert len(scene.picks) == 1
    assert scene.reselections == [(scene.eye, False, scene.front)]
    assert scene.dimensions == [(scene.eye, (0.150, 0.241, 0.0))]
    assert scene.mappings == [scene.eye.GetFace(), scene.eye.GetFace()]
    assert scene.state.count == 1 and scene.state.kind == 46
    assert not scene.state.selected and scene.visible_queries == []


@pytest.mark.parametrize(
    "fault,message", (
        ("none", "has no entity"),
        ("extra-geometry", "actual count=3"),
        ("extra-view", "actual count=3"),
        ("duplicate-silhouette", "duplicate silhouettes"),
        ("duplicate-view", "actual duplicate parent view at index=2"),
        ("attached-edge", "actual type=1"),
        ("foreign-same-name-view", "expected IsSame=1; actual IsSame=0 at index=1"),
        ("wrong-type", "actual type=1"),
        ("face", "actual type=2"),
        ("view-only", "no physical silhouette"),
        ("null-silhouette", "nonnull entity"),
        ("null-first-view", "nonnull entity"),
        ("null-view", "has no entity"),
    ),
)
def test_coordinate_selection_group_rejects_every_nonparent_extra_without_reselection(
    supplier_eye_scene, fault, message,
):
    scene = supplier_eye_scene
    foreign = SimpleNamespace(
        Name=scene.front.Name, ReferencedDocument=scene.source,
        ReferencedConfiguration="Finished",
    )
    scene.state.entries = {
        "none": [(46, scene.eye)],
        "extra-geometry": [(12, scene.front), (46, scene.eye), (1, scene.outer)],
        "attached-edge": [(46, scene.eye), (1, scene.outer)],
        "extra-view": [(12, scene.front), (12, scene.front), (46, scene.eye)],
        "duplicate-silhouette": [(46, scene.eye), (46, scene.eye)],
        "duplicate-view": [(12, scene.front), (12, scene.front)],
        "foreign-same-name-view": [(12, foreign), (46, scene.eye)],
        "wrong-type": [(1, scene.eye)],
        "face": [(2, scene.eye)],
        "view-only": [(12, scene.front)],
        "null-silhouette": [(46, None), (12, scene.front)],
        "null-first-view": [(12, None), (46, scene.eye)],
        "null-view": [(46, scene.eye), (12, None)],
    }[fault]
    scene.state.count = 0 if fault == "none" else len(scene.state.entries)
    with pytest.raises(RuntimeError, match=message):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert len(scene.picks) == 1 and scene.reselections == scene.dimensions == []
    assert scene.state.selected is False and scene.visible_queries == []


@pytest.mark.parametrize("same_result", (0, -1, 2))
def test_parent_view_requires_positive_native_identity_not_name_or_unknown(
    supplier_eye_scene, same_result,
):
    scene = supplier_eye_scene
    original_same = scene.adapter.swApp.IsSame
    parent_identity_reads = []

    def same(first, second):
        if first is scene.front:
            parent_identity_reads.append((first, second))
            return same_result
        return original_same(first, second)

    scene.adapter.swApp.IsSame = same
    scene.state.entries = [(12, scene.front), (46, scene.eye)]
    scene.state.count = 2
    with pytest.raises(
        RuntimeError,
        match=f"expected IsSame=1; actual IsSame={same_result} at index=1",
    ):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.reselections == scene.dimensions == []
    assert parent_identity_reads == [(scene.front, scene.front)]


def test_duplicate_parent_view_is_refused_without_a_second_native_identity_query(supplier_eye_scene):
    scene = supplier_eye_scene
    original_same = scene.adapter.swApp.IsSame
    parent_identity_reads = []

    def same(first, second):
        if first is scene.front:
            parent_identity_reads.append((first, second))
        return original_same(first, second)

    scene.adapter.swApp.IsSame = same
    scene.state.entries = [(12, scene.front), (12, scene.front)]
    scene.state.count = 2
    with pytest.raises(RuntimeError, match="actual duplicate parent view at index=2"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert parent_identity_reads == [(scene.front, scene.front)]
    assert scene.reselections == scene.dimensions == []


@pytest.mark.parametrize(
    "fault", (
        "count-zero", "count-two", "type-edge", "type-view", "null", "outer",
        "foreign-same-name-view", "wrong-path", "wrong-configuration",
        "nonfinite-circle", "wrong-center", "missing-face",
        "missing-source", "missing-wire", "null-mapping", "foreign-owner", "wrong-torus",
    ),
)
def test_direct_reselection_must_leave_one_current_exact_physical_source_contour(
    supplier_eye_scene, fault,
):
    scene = supplier_eye_scene

    def drift():
        if fault == "count-zero":
            scene.state.count = 0
        elif fault == "count-two":
            scene.state.count = 2
        elif fault == "type-edge":
            scene.state.kind = 1
        elif fault == "type-view":
            scene.state.kind = 12
            scene.state.pick = scene.front
        elif fault == "null":
            scene.state.pick = None
        elif fault == "outer":
            scene.state.pick = scene.outer
        elif fault == "foreign-same-name-view":
            scene.eye.GetView = lambda: SimpleNamespace(
                Name=scene.front.Name, ReferencedConfiguration="Finished",
                ReferencedDocument=scene.source,
            )
        elif fault == "nonfinite-circle":
            values = list(scene.eye.GetCurve().CircleParams)
            values[0] = math.nan
            scene.eye.GetCurve().CircleParams = tuple(values)
        elif fault == "wrong-center":
            values = list(scene.eye.GetCurve().CircleParams)
            values[1] = -0.009
            scene.eye.GetCurve().CircleParams = tuple(values)
        elif fault == "missing-face":
            scene.eye.GetFace = lambda: None
        elif fault == "wrong-path":
            scene.source.GetPathName = lambda: "D:/foreign.SLDPRT"
        elif fault == "wrong-configuration":
            scene.front.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
        elif fault == "missing-source":
            scene.front.ReferencedDocument = None
        elif fault == "missing-wire":
            scene.source.FeatureByName = lambda _name: None
        elif fault == "null-mapping":
            scene.mapped_faces.clear()
        elif fault == "foreign-owner":
            scene.mapped_faces[id(scene.eye.GetFace())] = SimpleNamespace(
                GetFeature=lambda: SimpleNamespace(Name="Wire"),
                GetSurface=lambda: scene.surface,
            )
        elif fault == "wrong-torus":
            values = list(scene.surface.TorusParams)
            values[7] += 0.001
            scene.surface.TorusParams = tuple(values)

    scene.state.after_reselect = drift
    with pytest.raises(RuntimeError):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert len(scene.picks) == len(scene.reselections) == 1
    assert scene.dimensions == [] and not scene.state.selected


@pytest.mark.parametrize("count", (0, 3))
def test_coordinate_group_count_is_rechecked_after_the_helper_read(supplier_eye_scene, count):
    scene = supplier_eye_scene
    reads = []

    def drift_count(_mark):
        reads.append(True)
        if len(reads) > 1:
            scene.state.count = count
        return scene.state.count

    scene.model.SelectionManager.GetSelectedObjectCount2 = drift_count
    with pytest.raises(RuntimeError, match=f"actual count={count}"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.reselections == scene.dimensions == []
    assert not scene.state.selected


def test_final_count_guard_is_independent_of_the_direct_helper_read(
    supplier_eye_scene,
):
    scene = supplier_eye_scene
    count = scene.model.SelectionManager.GetSelectedObjectCount2
    direct_reads = []

    def drift_count(mark):
        if scene.state.single_reselected:
            direct_reads.append(mark)
            return 1 if len(direct_reads) == 1 else 2
        return count(mark)

    scene.model.SelectionManager.GetSelectedObjectCount2 = drift_count
    with pytest.raises(RuntimeError, match="final selection expected count=1; actual count=2"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.dimensions == [] and not scene.state.selected


def test_final_entity_is_reacquired_instead_of_reusing_the_validated_handle(supplier_eye_scene):
    scene = supplier_eye_scene
    fresh = scene.contour()
    scene.state.after_reselect = lambda: setattr(scene.state, "pick", fresh)
    drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.reselections == [(scene.eye, False, scene.front)]
    assert scene.dimensions == [(fresh, (0.150, 0.241, 0.0))]
    assert scene.mappings == [scene.eye.GetFace(), fresh.GetFace()]


def test_final_entity_guard_refuses_null_after_helper_completed(supplier_eye_scene):
    scene = supplier_eye_scene
    entity = scene.model.SelectionManager.GetSelectedObject6
    direct_reads = []

    def disappear(*args):
        if scene.state.single_reselected:
            direct_reads.append(args)
            if len(direct_reads) > 1:
                return None
        return entity(*args)

    scene.model.SelectionManager.GetSelectedObject6 = disappear
    with pytest.raises(RuntimeError, match="final selection expected nonnull"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert len(scene.reselections) == 1 and scene.dimensions == []
    assert not scene.state.selected


def test_direct_selection_false_is_not_retried_or_replaced(supplier_eye_scene):
    scene = supplier_eye_scene
    calls = []
    scene.eye.Select2 = lambda *_args: calls.append("Select2") or False
    with pytest.raises(RuntimeError, match="failed to select EyeID silhouette by entity"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert calls == ["Select2"] and len(scene.picks) == 1
    assert scene.dimensions == [] and scene.visible_queries == []


@pytest.mark.parametrize("phase", ("coordinate", "direct"))
@pytest.mark.parametrize(
    "member", ("GetSelectedObjectCount2", "GetSelectedObjectType3", "GetSelectedObject6"),
)
def test_native_selection_getter_errors_propagate_without_retry(
    supplier_eye_scene, phase, member,
):
    scene = supplier_eye_scene
    error = OSError(f"native {phase} {member} failed")
    manager = scene.model.SelectionManager
    getter = getattr(manager, member)
    failures = []

    def read(*args):
        if (phase == "direct") == scene.state.single_reselected:
            failures.append(member)
            raise error
        return getter(*args)

    setattr(manager, member, read)
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error and failures == [member]
    assert scene.dimensions == [] and not scene.state.selected


def test_cleanup_failure_cannot_replace_the_original_native_failure(supplier_eye_scene):
    scene = supplier_eye_scene
    error, cleanup_error = OSError("native curve failed"), OSError("native clear failed")
    clear = scene.model.ClearSelection2

    def fail_curve():
        raise error

    def fail_final_clear(all_selected):
        if scene.state.selected:
            raise cleanup_error
        clear(all_selected)

    scene.eye.GetCurve = fail_curve
    scene.model.ClearSelection2 = fail_final_clear
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error and error.__cause__ is cleanup_error
    assert scene.dimensions == []


@pytest.mark.parametrize(
    "fault", ("outer", "unrelated-circle", "missing-curve", "noncircle", "short-circle",
              "long-circle", "center-boundary", "wrong-normal", "wrong-radius",
              "missing-view", "wrong-view", "foreign-same-name-view", "wrong-native-configuration",
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
    elif fault == "foreign-same-name-view":
        scene.eye.GetView = lambda: SimpleNamespace(
            Name=scene.front.Name, ReferencedConfiguration="Finished",
            ReferencedDocument=scene.source,
        )
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
    "operation", (
        "GetFaces", "projection", "SelectByID2", "Select2", "GetCurve",
        "GetCorrespondingEntity2", "current-GetCurve", "current-correspondence",
        "AddDiameterDimension2",
    ),
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
    elif operation == "Select2":
        scene.eye.Select2 = fail
    elif operation == "GetCurve":
        scene.eye.GetCurve = fail
    elif operation == "GetCorrespondingEntity2":
        scene.source.Extension.GetCorrespondingEntity2 = fail
    elif operation == "current-GetCurve":
        scene.state.after_reselect = lambda: setattr(scene.eye, "GetCurve", fail)
    elif operation == "current-correspondence":
        scene.state.after_reselect = lambda: setattr(
            scene.source.Extension, "GetCorrespondingEntity2", fail,
        )
    elif operation == "AddDiameterDimension2":
        scene.model.AddDiameterDimension2 = fail
    with pytest.raises(OSError) as caught:
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert caught.value is error
    assert calls == [operation] and not getattr(error, "__notes__", ())
    assert scene.state.selected is False and scene.visible_queries == []


def test_null_native_dimension_still_clears_the_verified_selection(supplier_eye_scene):
    scene = supplier_eye_scene
    scene.model.AddDiameterDimension2 = lambda *_args: None
    with pytest.raises(RuntimeError, match="cannot dimension the counter eye ID silhouette"):
        drawing._supplier_references(scene.adapter, scene.front, "Finished")
    assert scene.mappings == [scene.eye.GetFace(), scene.eye.GetFace()]
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


@pytest.fixture
def stock_profile_receipt_scene(monkeypatch, tmp_path):
    """One retained view/source/sketch; all mutation and foreign casts fail."""
    calls, bindings, queries = [], [], []

    def forbid(*_args, **_kwargs):
        pytest.fail("a stock coverage receipt must not mutate or refresh native state")

    def bind(value, kind):
        assert kind in value._interfaces
        if kind in ("ISketchLine", "ISketchArc"):
            assert ("type", value.index) in queries
        bindings.append((value, kind))
        return value

    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing, "bstr_array", lambda values: values)
    def point(xyz):
        return SimpleNamespace(_interfaces={"ISketchPoint"}, X=xyz[0], Y=xyz[1], Z=xyz[2])

    view_matrix = [0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0,
                   0.15, 0.175, 0.0, 2.0, 0.0, 0.0, 0.0]
    sketch_matrix = [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, -1.0, 0.0,
                     0.003, 0.004, 0.005, 1.0, 0.0, 0.0, 0.0]
    segments = []
    for index in range(9):
        kind = 1 if index < 3 else 0
        start = (index / 1000.0, -0.04, 0.0)
        end = (index / 1000.0 + 0.002, -0.06, 0.0)
        segment = SimpleNamespace(
            _interfaces={"ISketchSegment", "ISketchArc" if kind == 1 else "ISketchLine"},
            index=index, ConstructionGeometry=True, Select4=forbid,
            GetType=lambda index=index, kind=kind: queries.append(("type", index)) or kind,
            GetStartPoint2=lambda start=start: point(start),
            GetEndPoint2=lambda end=end: point(end),
        )
        if kind == 1:
            segment.IsCircle = lambda: 1
            segment.GetCenterPoint2 = lambda index=index: point((0.003 + index / 100.0, 0.004, 0.0))
            segment.GetRadius = lambda index=index: 0.009 + index / 1000.0
            segment.GetNormalVector = lambda: (0.0, 0.0, 1.0)
            segment.SetRadius = forbid
        segments.append(segment)
    sketch = SimpleNamespace(
        _interfaces={"ISketch"},
        ModelToSketchTransform=SimpleNamespace(_interfaces={"IMathTransform"}, ArrayData=sketch_matrix),
        GetSketchSegments=lambda: queries.append("segments") or tuple(segments),
    )
    values = {
        "SupplierNominalEyeOD": 0.018, "SupplierNominalWire": 0.0048,
        "SupplierStockShank": 0.058, "SupplierStockOverall": 0.076,
    }
    dimensions = {}

    def dimension_value(name, option, names):
        assert option == 3 and names == [drawing.SUPPLIER_STOCK_CONFIGURATION]
        queries.append(("dimension", name, option, tuple(names)))
        return (values[name],)

    for name in values:
        dimensions[name] = SimpleNamespace(
            _interfaces={"IDimension"}, FullName=f"{name}@{drawing.SUPPLIER_STOCK_FEATURE}",
            GetSystemValue3=lambda option, names, name=name: dimension_value(name, option, names),
        )

    def suppressed(option, names):
        assert option == 3 and names == [drawing.SUPPLIER_STOCK_CONFIGURATION]
        queries.append(("suppression", option, tuple(names)))
        return (False,)

    feature = SimpleNamespace(
        _interfaces={"IFeature"}, Name=drawing.SUPPLIER_STOCK_FEATURE, Visible=1,
        GetTypeName2=lambda: "ProfileFeature", IsSuppressed2=suppressed,
        Parameter=lambda name: dimensions[name], GetSpecificFeature2=lambda: sketch,
        Select2=forbid, SetSuppression2=forbid,
    )

    def by_name(name):
        assert name == drawing.SUPPLIER_STOCK_FEATURE
        queries.append(("feature", name))
        return feature

    source_path = tmp_path / "anchor.SLDPRT"
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    configuration = SimpleNamespace(
        _interfaces={"IConfiguration"}, Name=drawing.SUPPLIER_STOCK_CONFIGURATION,
        GetID=lambda: 23,
    )

    def named_configuration(name):
        assert name == drawing.SUPPLIER_STOCK_CONFIGURATION
        queries.append(("configuration", name))
        return configuration

    source = SimpleNamespace(
        _interfaces={"IModelDoc2", "IPartDoc"},
        GetPathName=lambda: str(source_path.resolve()).replace("/", "\\").upper(),
        GetConfigurationByName=named_configuration,
        FeatureByName=by_name, ShowConfiguration2=forbid, EditRebuild3=forbid,
        ForceRebuild3=forbid, ClearSelection2=forbid,
    )
    stock = SimpleNamespace(
        _interfaces={"IView"}, ReferencedConfiguration="Default", ReferencedDocument=source,
        GetName2=lambda: "original-stock-view", ScaleRatio=(2.0, 1.0), Position=drawing.STOCK_CENTER,
        GetDisplayMode2=lambda: 2, ScaleDecimal=2.0, UseSheetScale=0,
        ModelToViewTransform=SimpleNamespace(_interfaces={"IMathTransform"}, ArrayData=view_matrix),
        UpdateViewDisplayGeometry=lambda: calls.append("update"),
    )
    state = SimpleNamespace(outline=(0.10, 0.10, 0.11, 0.11))

    def outline():
        calls.append("outline")
        assert calls.count("outline") == 1, "never reacquire the failed outline"
        return state.outline

    stock.GetOutline = outline
    model = SimpleNamespace(EditRebuild3=lambda: calls.append("rebuild") or True)
    identity_reads = []

    def same(first, second):
        assert second is source
        identity_reads.append((first, second))
        return int(first is second)

    adapter = SimpleNamespace(
        currentModel=model,
        swApp=SimpleNamespace(IsSame=same, GetOpenDocumentByName=forbid, OpenDoc6=forbid),
    )

    def active_configuration(actual_adapter, actual_source):
        assert actual_adapter is adapter and actual_source is source
        return "Default"

    monkeypatch.setattr(drawing, "active_configuration_name", active_configuration)
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: calls.append("place") or stock)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: calls.append("mode"))
    monkeypatch.setattr(
        drawing, "_show_hidden_owners",
        lambda *_args, **_kwargs: calls.append("reveal") or [drawing.SUPPLIER_STOCK_FEATURE],
    )
    monkeypatch.setattr(drawing, "model_points_in_view", forbid)
    monkeypatch.setattr(drawing, "curate_stock_dimensions", forbid)
    return SimpleNamespace(
        adapter=adapter, stock=stock, source=source, feature=feature, sketch=sketch,
        segments=segments, dimensions=dimensions, values=values, state=state,
        calls=calls, bindings=bindings, queries=queries,
        view_matrix=view_matrix, sketch_matrix=sketch_matrix,
        identity_reads=identity_reads, configuration=configuration, source_path=source_path,
    )


def _failed_stock_receipt(scene):
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_stock_diagram(scene.adapter, scene.source)
    assert str(caught.value) == "revealed supplier diagram outline does not cover its source profile"
    assert len(caught.value.__notes__) == 1
    marker = "SM_STOCK_PROFILE_COVERAGE_RECEIPT "
    assert caught.value.__notes__[0].startswith(marker)
    return json.loads(caught.value.__notes__[0][len(marker):])


@pytest.mark.parametrize(
    "width,height,failed_index,status",
    (
        (0.080, 0.1524, 0, ("undersize", None)),
        (0.090, 0.1524, 0, ("oversize", None)),
        (0.082225, 0.150, 1, (None, "undersize")),
        (0.082225, 0.160, 1, (None, "oversize")),
        (0.080, 0.160, 0, ("undersize", "oversize")),
        (0.160, 0.160, 0, ("oversize", "oversize")),
    ),
)
def test_stock_failure_freezes_both_original_axis_predicates_before_native_reads(
    stock_profile_receipt_scene, monkeypatch, width, height, failed_index, status,
):
    scene = stock_profile_receipt_scene
    scene.state.outline = (0.0, 0.0, width, height)
    capture = drawing._supplier_stock_coverage_receipt

    def later_readback(adapter, stock, source_model, original):
        assert stock is scene.stock and source_model is scene.source
        assert scene.calls == ["place", "mode", "reveal", "rebuild", "update", "outline"]
        assert original["outline_m"] == scene.state.outline
        # Different later metadata cannot rewrite the original failed predicate.
        stock.ScaleRatio = (7.0, 1.0)
        stock.ReferencedConfiguration = "later-configuration"
        return capture(adapter, stock, source_model, original)

    monkeypatch.setattr(drawing, "_supplier_stock_coverage_receipt", later_readback)
    receipt = _failed_stock_receipt(scene)
    original = receipt["original_predicate"]
    assert original["failed_index"] == failed_index
    assert original["expected_spans_m"] == pytest.approx([0.082225, 0.1524])
    assert original["shown_owners"] == [drawing.SUPPLIER_STOCK_FEATURE]
    for row, wanted, actual, fault in zip(
        original["axes"], (0.082225, 0.1524), (width, height), status, strict=True,
    ):
        assert row["actual_m"] == actual and row["expected_m"] == pytest.approx(wanted)
        assert row["minimum_m"] == pytest.approx(wanted - 1e-7)
        assert row["maximum_m"] == pytest.approx(wanted + 0.006)
        assert row["undersize"] is (fault == "undersize")
        assert row["oversize"] is (fault == "oversize")
        assert row["passes"] is (fault is None)
        assert row["covers_source"] is (fault != "undersize")
        assert row["within_padding"] is (fault != "oversize")
    assert receipt["later_readback"]["view"]["ScaleRatio"]["value"] == [7.0, 1.0]
    assert scene.calls.count("rebuild") == scene.calls.count("update") == scene.calls.count("outline") == 1


def test_stock_receipt_records_actual_geometry_transforms_and_named_configuration_values(
    stock_profile_receipt_scene,
):
    scene = stock_profile_receipt_scene
    receipt = _failed_stock_receipt(scene)
    later = receipt["later_readback"]
    assert later["view"]["ModelToViewTransform"]["ArrayData"]["value"] == scene.view_matrix
    assert later["source"]["active_configuration"]["value"] == "Default"
    assert later["view"]["GetDisplayMode2"]["value"] == 2
    assert later["view"]["ScaleDecimal"]["value"] == 2.0
    assert later["view"]["UseSheetScale"]["value"] == 0
    assert later["source"]["expected_path"] == scene.source_path.resolve().as_posix()
    assert later["source"]["path_matches_expected"]["value"] is True
    assert later["source"]["source_model_self_IsSame"]["value"] == 1
    assert later["source"]["view_source_IsSame"]["value"] == 1
    assert len(scene.identity_reads) == 2
    assert all(first is scene.source and second is scene.source
               for first, second in scene.identity_reads)
    assert later["source"]["stock_configuration"] == {
        "present": True,
        "Name": {"value": drawing.SUPPLIER_STOCK_CONFIGURATION},
        "GetID": {"value": 23},
    }
    profile = later["source"]["profile"]
    assert profile["Visible_in_source"]["value"] == 1
    assert profile["suppressed_in_stock_configuration"]["value"] == [False]
    assert profile["ModelToSketchTransform"]["ArrayData"]["value"] == scene.sketch_matrix
    assert profile["GetSketchSegments"] == {
        "present": True, "count": 9, "expected_count": 9, "sample_truncated": False,
    }
    rows = profile["segments"]
    assert len(rows) == 9
    for index, row in enumerate(rows):
        assert row["GetType"]["value"] == (1 if index < 3 else 0)
        assert row["ConstructionGeometry"]["value"] is True
        assert row["start"]["coordinates_m"]["value"] == [index / 1000.0, -0.04, 0.0]
        assert row["end"]["coordinates_m"]["value"] == [index / 1000.0 + 0.002, -0.06, 0.0]
        if index < 3:
            assert row["IsCircle"]["value"] == 1
            assert row["centre"]["coordinates_m"]["value"] == [0.003 + index / 100.0, 0.004, 0.0]
            assert row["radius_m"]["value"] == 0.009 + index / 1000.0
            assert row["normal"]["value"] == [0.0, 0.0, 1.0]
    for name, actual in scene.values.items():
        assert profile["dimensions_in_stock_configuration"][name]["GetSystemValue3"]["value"] == [actual]
    assert len([query for query in scene.queries if isinstance(query, tuple) and query[0] == "dimension"]) == 4
    assert [value for value, kind in scene.bindings if kind == "IView"] == [scene.stock]
    assert [value for value, kind in scene.bindings if kind == "IFeature"] == [scene.feature]


@pytest.mark.parametrize("fault", ("type", "point", "radius", "dimension", "suppression", "transform"))
def test_stock_receipt_retains_per_field_native_errors_and_continues_other_reads(
    stock_profile_receipt_scene, fault,
):
    scene = stock_profile_receipt_scene

    def failed():
        raise RuntimeError("native field unavailable")

    if fault == "type":
        scene.segments[0].GetType = failed
    elif fault == "point":
        scene.segments[0].GetCenterPoint2 = failed
    elif fault == "radius":
        scene.segments[0].GetRadius = failed
    elif fault == "dimension":
        scene.dimensions["SupplierNominalWire"].GetSystemValue3 = lambda *_args: failed()
    elif fault == "suppression":
        scene.feature.IsSuppressed2 = lambda *_args: failed()
    else:
        scene.stock.ModelToViewTransform.ArrayData = (float("nan"),)
    receipt = _failed_stock_receipt(scene)
    profile = receipt["later_readback"]["source"]["profile"]
    field = {
        "type": profile["segments"][0].get("GetType"),
        "point": profile["segments"][0].get("centre"),
        "radius": profile["segments"][0].get("radius_m"),
        "dimension": profile["dimensions_in_stock_configuration"]["SupplierNominalWire"].get("GetSystemValue3"),
        "suppression": profile.get("suppressed_in_stock_configuration"),
        "transform": receipt["later_readback"]["view"]["ModelToViewTransform"].get("ArrayData"),
    }[fault]
    assert "error" in field
    assert len(profile["segments"]) == 9
    assert profile["segments"][-1]["end"]["coordinates_m"]["value"] == [0.010, -0.06, 0.0]
    if fault == "type":
        assert not any(value is scene.segments[0] and kind in ("ISketchArc", "ISketchLine")
                       for value, kind in scene.bindings)


def test_stock_receipt_never_dual_casts_unexpected_native_segment_type(stock_profile_receipt_scene):
    scene = stock_profile_receipt_scene
    scene.segments[0].GetType = lambda: 2  # swSketchELLIPSE, not an arc.
    receipt = _failed_stock_receipt(scene)
    row = receipt["later_readback"]["source"]["profile"]["segments"][0]
    assert row["unexpected_type"] == 2
    assert not any(value is scene.segments[0] and kind in ("ISketchArc", "ISketchLine")
                   for value, kind in scene.bindings)


@pytest.mark.parametrize("failure", ("capture", "serialization"))
def test_stock_guard_preserves_original_exception_when_receipt_capture_fails(
    stock_profile_receipt_scene, monkeypatch, failure,
):
    scene = stock_profile_receipt_scene

    def failed(*_args, **_kwargs):
        raise OSError("receipt capture unavailable")

    if failure == "capture":
        monkeypatch.setattr(drawing, "_supplier_stock_coverage_receipt", failed)
    else:
        monkeypatch.setattr(drawing.json, "dumps", failed)
    with pytest.raises(RuntimeError) as caught:
        drawing._supplier_stock_diagram(scene.adapter, scene.source)
    assert str(caught.value) == "revealed supplier diagram outline does not cover its source profile"
    assert caught.value.__notes__ == [
        "SM_STOCK_PROFILE_COVERAGE_RECEIPT capture failed: OSError: receipt capture unavailable",
    ]
    assert scene.calls == ["place", "mode", "reveal", "rebuild", "update", "outline"]


def test_passing_stock_coverage_never_runs_native_receipt(stock_profile_receipt_scene, monkeypatch):
    scene = stock_profile_receipt_scene
    scene.state.outline = (0.0, 0.0, 0.082225, 0.1524)

    def past_guard(*_args, **_kwargs):
        raise RuntimeError("reached original positioning sequence")

    monkeypatch.setattr(drawing, "model_points_in_view", past_guard)
    monkeypatch.setattr(
        drawing, "_supplier_stock_coverage_receipt",
        lambda *_args: pytest.fail("a passing coverage guard must not run the receipt"),
    )
    with pytest.raises(RuntimeError, match="reached original positioning sequence"):
        drawing._supplier_stock_diagram(scene.adapter, scene.source)
    assert scene.queries == []
    assert scene.calls == ["place", "mode", "reveal", "rebuild", "update", "outline"]


@pytest.mark.parametrize("fault", ("same-path-foreign-source", "wrong-path", "identity-read-error"))
def test_stock_receipt_separates_path_and_retained_native_source_identity(
    stock_profile_receipt_scene, fault,
):
    scene = stock_profile_receipt_scene
    if fault == "same-path-foreign-source":
        scene.stock.ReferencedDocument = SimpleNamespace(**vars(scene.source))
    elif fault == "wrong-path":
        scene.source.GetPathName = lambda: "D:/foreign/anchor.SLDPRT"
    else:
        def identity_error(first, second):
            assert second is scene.source
            if first is not second:
                raise RuntimeError("native identity unavailable")
            return 1

        scene.stock.ReferencedDocument = SimpleNamespace(**vars(scene.source))
        scene.adapter.swApp.IsSame = identity_error
    receipt = _failed_stock_receipt(scene)
    source = receipt["later_readback"]["source"]
    assert source["source_model_self_IsSame"]["value"] == 1
    assert source["path_matches_expected"]["value"] is (fault != "wrong-path")
    if fault == "identity-read-error":
        assert source["view_source_IsSame"]["error"] == {
            "type": "RuntimeError", "message": "native identity unavailable",
        }
    else:
        assert source["view_source_IsSame"]["value"] == (0 if fault == "same-path-foreign-source" else 1)
    assert len(source["profile"]["segments"]) == 9


@pytest.mark.parametrize("fault", ("missing", "wrong-name", "read-error"))
def test_stock_receipt_records_named_configuration_without_activation(
    stock_profile_receipt_scene, fault,
):
    scene = stock_profile_receipt_scene
    if fault == "missing":
        scene.source.GetConfigurationByName = lambda _name: None
    elif fault == "wrong-name":
        scene.configuration.Name = "different-configuration"
    else:
        def unavailable(_name):
            raise RuntimeError("named configuration unavailable")

        scene.source.GetConfigurationByName = unavailable
    source = _failed_stock_receipt(scene)["later_readback"]["source"]
    assert source["expected_stock_configuration"] == drawing.SUPPLIER_STOCK_CONFIGURATION
    configuration = source["stock_configuration"]
    if fault == "missing":
        assert configuration == {"present": False}
    elif fault == "wrong-name":
        assert configuration["Name"]["value"] == "different-configuration"
        assert configuration["GetID"]["value"] == 23
    else:
        assert configuration["error"] == {
            "type": "RuntimeError", "message": "named configuration unavailable",
        }
    assert len(source["profile"]["segments"]) == 9

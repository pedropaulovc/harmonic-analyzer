"""Offline manufacturing boundaries for the modified purchased anchor."""

from dataclasses import FrozenInstanceError, replace
import math
from types import SimpleNamespace

import pytest

import _stock_trim_drawing as trim_drawing
import _drawing_selection as selection
import _drawing_view_display as view_display
import sm_vn_boss_hook_spec as spec
import draw_sm_vn_boss_hook as drawing
import _drawing_projection as projection
import _supplier_dimensions as supplier_dimensions
import _supplier_reference_geometry as reference_geometry
import _purchased_fastener_drawing as purchased_drawing
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


class _StockTransform:
    """Offline native-shaped row transform, not native rendering evidence."""

    def __init__(self, scale=1.0, x=0.0, y=0.0, angle=0.0):
        self.scale, self.x, self.y, self.angle = scale, x, y, angle

    @property
    def ArrayData(self):
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0,
                self.x, self.y, 0.0, self.scale, 0.0, 0.0, 0.0)

    def Inverse(self):
        assert self.scale == 1.0 and self.angle == self.x == self.y == 0.0
        return self

    def apply(self, xyz):
        c, s = math.cos(self.angle), math.sin(self.angle)
        return (self.x + self.scale * (c * xyz[0] - s * xyz[1]),
                self.y + self.scale * (s * xyz[0] + c * xyz[1]),
                self.scale * xyz[2])


class _StockMathPoint:
    def __init__(self, xyz):
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):
        return _StockMathPoint(transform.apply(self.ArrayData))


class _StockView(SimpleNamespace):
    @property
    def ModelToViewTransform(self):
        return _StockTransform(self.projection_scale, *self.Position, self.angle)


@pytest.fixture
def stock_source_scene(monkeypatch, tmp_path):
    """Exercise real capture/analytic projection with offline COM boundaries."""
    calls, scalar_reads, body_reads, correspondences = [], [], [], []

    def bind(value, _kind):
        return value

    for module in (drawing, supplier_dimensions, reference_geometry, purchased_drawing):
        monkeypatch.setattr(module, "_early_bound", bind)
    monkeypatch.setattr(reference_geometry, "_bind", bind)
    monkeypatch.setattr(projection, "double_array", tuple)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "bstr_array", tuple)
    source_path = tmp_path / "anchor.SLDPRT"
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    state = SimpleNamespace(active="OriginalFinished", changed_visibility=False, target_seen=False)

    def point(xyz):
        return SimpleNamespace(X=xyz[0], Y=xyz[1], Z=xyz[2])

    circles = []
    for center, radius in (
        ((0.0, 0.0, 0.0), drawing.SUPPLIER_NOMINAL_EYE_OD_MM / 2000.0),
        ((0.0, 0.0, 0.0), drawing.SUPPLIER_EYE_ID_MM / 2000.0),
        ((0.03, 0.0, 0.0), drawing.SUPPLIER_NOMINAL_WIRE_MM / 2000.0),
    ):
        circle = SimpleNamespace(center=point(center), radius=radius, ConstructionGeometry=True)
        circle.GetType = lambda: 1
        circle.IsCircle = lambda: 1
        circle.GetCenterPoint2 = lambda circle=circle: circle.center
        circle.GetRadius = lambda circle=circle: circle.radius
        circles.append(circle)
    outline = drawing.SUPPLIER_STOCK_SHANK_OUTLINE_MM
    pairs = [
        (outline[index], outline[(index + 1) % len(outline)])
        for index in range(len(outline))
    ] + list(zip(drawing.SUPPLIER_STOCK_AXIS_MM, drawing.SUPPLIER_STOCK_AXIS_MM[1:]))
    lines = []
    for start, end in pairs:
        line = SimpleNamespace(
            start=point((start[0] / 1000.0, start[1] / 1000.0, 0.0)),
            end=point((end[0] / 1000.0, end[1] / 1000.0, 0.0)),
            ConstructionGeometry=True, GetType=lambda: 0,
        )
        line.GetStartPoint2 = lambda line=line: line.start
        line.GetEndPoint2 = lambda line=line: line.end
        lines.append(line)
    segments = circles + lines

    def source_segments():
        calls.append(("segments", state.active))
        assert state.active in ("OriginalFinished", drawing.SUPPLIER_STOCK_CONFIGURATION)
        return tuple(segments)

    sketch = SimpleNamespace(
        Is3D=lambda: False, GetSketchBlockInstanceCount=lambda: 0,
        GetSketchTextSegments=lambda: (), GetUserPointsCount=lambda: 0,
        ModelToSketchTransform=_StockTransform(), GetSketchSegments=source_segments,
    )
    expected = {
        "SupplierNominalEyeOD": drawing.SUPPLIER_NOMINAL_EYE_OD_MM,
        "SupplierNominalWire": drawing.SUPPLIER_NOMINAL_WIRE_MM,
        "SupplierStockShank": drawing.SUPPLIER_STOCK_SHANK_MM,
        "SupplierStockOverall": drawing.SUPPLIER_STOCK_OVERALL_MM,
    }
    values = {name: value / 1000.0 for name, value in expected.items()}
    dimensions, displays = {}, []

    def scalar(name, option, configuration):
        # Deliberately demand the established scalar BSTR binding, not an array.
        assert option == 3 and type(configuration) is str
        assert configuration == state.active == drawing.SUPPLIER_STOCK_CONFIGURATION
        scalar_reads.append((name, option, configuration))
        return (values[name],)

    for name in expected:
        native = SimpleNamespace(
            FullName=f"{name}@{drawing.SUPPLIER_STOCK_FEATURE}",
            GetSystemValue3=lambda option, configuration, name=name: scalar(name, option, configuration),
        )
        dimensions[name] = native
        displays.append(SimpleNamespace(
            Type2=6 if name.startswith("SupplierNominal") else 12,
            GetDimension2=lambda _index, native=native: native,
        ))
    feature = SimpleNamespace(
        Name=drawing.SUPPLIER_STOCK_FEATURE, Visible=1,
        GetTypeName2=lambda: "ProfileFeature", GetErrorCode2=lambda: (0, 999),
        IsSuppressed2=lambda option, names: (False,),
        Parameter=lambda name: dimensions[name], GetSpecificFeature2=lambda: sketch,
    )
    thread = SimpleNamespace(Visible=1)
    features = {drawing.SUPPLIER_STOCK_FEATURE: feature, drawing.SUPPLIER_THREAD_FEATURE: thread}
    monkeypatch.setattr(drawing, "_feature_display_dimensions", lambda actual: (
        tuple(displays) if actual is feature else pytest.fail("wrong dimension owner")
    ))
    configuration = SimpleNamespace(Name=drawing.SUPPLIER_STOCK_CONFIGURATION, GetID=lambda: 23)

    def show(name):
        calls.append(("show", name))
        state.active = name
        if name == drawing.SUPPLIER_STOCK_CONFIGURATION:
            state.target_seen = True
        return True

    def rebuild():
        calls.append(("source-rebuild", state.active))
        return True

    def bodies(kind, visible):
        assert state.active == drawing.SUPPLIER_STOCK_CONFIGURATION and visible is False
        body_reads.append((state.active, kind, visible))
        return ()

    def forbid(*_args, **_kwargs):
        pytest.fail("source capture/settled stock ink must never save the part")

    source = SimpleNamespace(
        GetType=lambda: 1, GetPathName=lambda: str(source_path.resolve()),
        GetConfigurationByName=lambda name: configuration if name == configuration.Name else None,
        FeatureByName=lambda name: features.get(name), GetBodies2=bodies,
        ShowConfiguration2=show, EditRebuild3=rebuild, Save3=forbid, SaveAs3=forbid,
    )
    monkeypatch.setattr(
        drawing, "active_configuration_name",
        lambda _adapter, actual: state.active if actual is source else pytest.fail("wrong active source"),
    )

    def blank(actual_adapter, names):
        assert actual_adapter.currentModel is source and state.active == "OriginalFinished"
        calls.append(("blank", names))
        for name in names:
            features[name].Visible = 1

    monkeypatch.setattr(drawing, "blank_reference_sketches", blank)
    stock = _StockView(
        Name="stock", ReferencedDocument=source,
        ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
        GetReferencedModelName=lambda: str(source_path.resolve()), Type=7,
        GetBaseView=lambda: None, IsCropped=lambda: False, IsBroken=lambda: False,
        IsPerspectiveView=lambda: False, GetBreakLines=lambda: (),
        GetBreakOutSectionCount=lambda: 0, UseSheetScale=0, ScaleRatio=drawing.STOCK_SCALE,
        ScaleDecimal=2.0, GetDisplayMode2=lambda: 2, Position=drawing.STOCK_CENTER,
        projection_scale=2.0, angle=0.0,
        GetSketch=lambda: SimpleNamespace(GetSketchSegments=lambda: ()),
        GetFirstDisplayDimension6=lambda: None, GetAnnotations=lambda: (),
        UpdateViewDisplayGeometry=lambda: calls.append("view-update"),
        GetCorresponding=lambda segment: correspondences.append(segment) or SimpleNamespace(),
        GetOutline=lambda: pytest.fail("stock geometry must not use a cached view outline"),
    )
    utility = SimpleNamespace(CreatePoint=lambda xyz: _StockMathPoint(xyz))
    model = SimpleNamespace(EditRebuild3=lambda: calls.append("drawing-rebuild") or True)
    adapter = SimpleNamespace(
        currentModel=source,
        swApp=SimpleNamespace(IsSame=lambda first, second: int(first is second), GetMathUtility=lambda: utility),
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    return SimpleNamespace(
        adapter=adapter, source=source, stock=stock, state=state, feature=feature,
        thread=thread, configuration=configuration, sketch=sketch, segments=segments,
        circles=circles, lines=lines, dimensions=dimensions, displays=displays,
        values=values, calls=calls, scalar_reads=scalar_reads, body_reads=body_reads,
        correspondences=correspondences, model=model, source_path=source_path,
    )


def _stock_capture(scene):
    return drawing._capture_supplier_stock(scene.adapter, scene.source, "OriginalFinished")


def test_stock_capture_reads_target_solved_geometry_and_four_scalar_values_then_restores(stock_source_scene):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    assert type(capture) is drawing.SupplierStockCapture
    assert type(capture.geometry) is drawing.NativeSketchGeometry
    assert (len(capture.geometry.circle_offsets), len(capture.geometry.line_offsets)) == (3, 6)
    assert len(capture.geometry.model_points) == 21
    assert capture.source_path == scene.source_path.resolve().as_posix()
    assert capture.configuration == drawing.SUPPLIER_STOCK_CONFIGURATION
    assert capture.configuration_id == 23
    assert scene.state.active == "OriginalFinished"
    assert [row[0] for row in scene.scalar_reads] == list(scene.values)
    assert scene.body_reads == [
        (drawing.SUPPLIER_STOCK_CONFIGURATION, 0, False),
        (drawing.SUPPLIER_STOCK_CONFIGURATION, 1, False),
    ]
    assert ("segments", drawing.SUPPLIER_STOCK_CONFIGURATION) in scene.calls
    assert [row for row in scene.calls if isinstance(row, tuple) and row[0] == "show"] == [
        ("show", drawing.SUPPLIER_STOCK_CONFIGURATION), ("show", "OriginalFinished"),
    ]
    with pytest.raises(FrozenInstanceError):
        capture.source_path = "changed"
    with pytest.raises(FrozenInstanceError):
        capture.geometry.model_points = ()


@pytest.mark.parametrize("kind", (0, 1))
def test_stock_capture_refuses_any_native_solid_or_sheet_body(stock_source_scene, kind):
    scene = stock_source_scene
    scene.source.GetBodies2 = lambda actual, _visible: (object(),) if actual == kind else ()
    with pytest.raises(RuntimeError, match="zero solid/sheet bodies"):
        _stock_capture(scene)
    assert scene.state.active == "OriginalFinished" and scene.scalar_reads == []


@pytest.mark.parametrize("fault", (
    "source-type", "source-path", "missing-configuration", "wrong-configuration-name",
    "missing-feature", "wrong-feature-name", "wrong-feature-type", "suppressed",
    "missing-suppression", "native-error", "unreadable-error", "shown-source",
))
def test_stock_capture_refuses_wrong_source_configuration_or_owner(stock_source_scene, fault):
    scene = stock_source_scene
    if fault == "source-type":
        scene.source.GetType = lambda: 2
    elif fault == "source-path":
        scene.source.GetPathName = lambda: "D:/foreign.SLDPRT"
    elif fault == "missing-configuration":
        scene.source.GetConfigurationByName = lambda _name: None
    elif fault == "wrong-configuration-name":
        scene.source.GetConfigurationByName = lambda _name: SimpleNamespace(Name="Wrong")
    elif fault == "missing-feature":
        by_name = scene.source.FeatureByName
        scene.source.FeatureByName = lambda name: (
            None if scene.state.target_seen and name == drawing.SUPPLIER_STOCK_FEATURE else by_name(name)
        )
    elif fault == "wrong-feature-name":
        scene.feature.Name = "Wrong"
    elif fault == "wrong-feature-type":
        scene.feature.GetTypeName2 = lambda: "3DProfileFeature"
    elif fault == "suppressed":
        scene.feature.IsSuppressed2 = lambda *_args: (True,)
    elif fault == "missing-suppression":
        scene.feature.IsSuppressed2 = lambda *_args: ()
    elif fault == "native-error":
        scene.feature.GetErrorCode2 = lambda: (1, 0)
    elif fault == "unreadable-error":
        scene.feature.GetErrorCode2 = lambda: (False, 0)
    else:
        scene.feature.Visible = 2
    with pytest.raises(RuntimeError):
        _stock_capture(scene)
    assert scene.state.active == "OriginalFinished"


@pytest.mark.parametrize("name", (
    "SupplierNominalEyeOD", "SupplierNominalWire", "SupplierStockShank", "SupplierStockOverall",
))
@pytest.mark.parametrize("value", (0.0, 0.001, math.nan, math.inf))
def test_each_stock_scalar_dimension_requires_its_exact_nonzero_value(stock_source_scene, name, value):
    scene = stock_source_scene
    scene.values[name] = value
    with pytest.raises(RuntimeError, match="native value"):
        _stock_capture(scene)
    assert scene.state.active == "OriginalFinished"


@pytest.mark.parametrize("fault", ("missing", "duplicate", "foreign-owner", "foreign-native", "wrong-type", "missing-value"))
def test_stock_dimension_inventory_and_native_identity_are_not_value_only(stock_source_scene, fault):
    scene = stock_source_scene
    if fault == "missing":
        scene.displays.pop()
    elif fault == "duplicate":
        scene.displays.append(scene.displays[0])
    elif fault == "foreign-owner":
        scene.dimensions["SupplierNominalEyeOD"].FullName = "SupplierNominalEyeOD@Foreign"
    elif fault == "foreign-native":
        scene.feature.Parameter = lambda _name: SimpleNamespace()
    elif fault == "wrong-type":
        scene.displays[0].Type2 = 3
    else:
        scene.dimensions["SupplierNominalEyeOD"].GetSystemValue3 = lambda *_args: ()
    with pytest.raises(RuntimeError):
        _stock_capture(scene)
    assert scene.state.active == "OriginalFinished"


@pytest.mark.parametrize("fault", (
    "missing-circle", "extra-circle", "missing-line", "extra-line", "wrong-type",
    "partial-arc", "nonconstruction", "wrong-radius", "wrong-centre",
    "wrong-inner-circle", "wrong-line", "nonfinite", "three-dimensional", "sketch-text",
    "user-point", "sketch-block", "wrong-inverse",
))
def test_stock_geometry_requires_the_complete_actual_three_circle_six_line_inventory(stock_source_scene, fault):
    scene = stock_source_scene
    if fault == "missing-circle":
        scene.segments.remove(scene.circles[0])
    elif fault == "extra-circle":
        scene.segments.append(scene.circles[0])
    elif fault == "missing-line":
        scene.segments.remove(scene.lines[0])
    elif fault == "extra-line":
        scene.segments.append(scene.lines[0])
    elif fault == "wrong-type":
        scene.circles[0].GetType = lambda: 2
    elif fault == "partial-arc":
        scene.circles[0].IsCircle = lambda: 0
    elif fault == "nonconstruction":
        scene.lines[0].ConstructionGeometry = False
    elif fault == "wrong-radius":
        scene.circles[0].radius += 0.001
    elif fault == "wrong-centre":
        scene.circles[2].center.X += 0.001
    elif fault == "wrong-inner-circle":
        # Interior ink changes without changing the outer envelope.
        scene.circles[1].radius += 0.001
    elif fault == "wrong-line":
        scene.lines[0].start.X += 0.001
    elif fault == "nonfinite":
        scene.lines[1].end.Z = math.nan
    elif fault == "three-dimensional":
        scene.sketch.Is3D = lambda: True
    elif fault == "sketch-text":
        scene.sketch.GetSketchTextSegments = lambda: (object(),)
    elif fault == "user-point":
        scene.sketch.GetUserPointsCount = lambda: 1
    elif fault == "sketch-block":
        scene.sketch.GetSketchBlockInstanceCount = lambda: 1
    else:
        inverse = _StockTransform(x=0.001)
        scene.sketch.ModelToSketchTransform.Inverse = lambda: inverse
    with pytest.raises(RuntimeError):
        _stock_capture(scene)
    assert scene.state.active == "OriginalFinished"


def test_only_target_configuration_geometry_is_captured(stock_source_scene):
    scene = stock_source_scene
    read = scene.sketch.GetSketchSegments

    def active_segments():
        assert scene.state.active == drawing.SUPPLIER_STOCK_CONFIGURATION
        return read()

    scene.sketch.GetSketchSegments = active_segments
    capture = _stock_capture(scene)
    # The source getter becomes unusable after restoration; projection must
    # consume the immutable target capture, not reopen/reactivate the source.
    scene.sketch.GetSketchSegments = lambda: pytest.fail("late live source geometry read")
    bounds = drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, capture)
    assert bounds == pytest.approx((0.1325375, 0.0400625, 0.2147625, 0.1924625))
    assert scene.state.active == "OriginalFinished"


@pytest.mark.parametrize("primary_failure", (False, True))
@pytest.mark.parametrize("cleanup_failure", ("activation", "rebuild", "visibility"))
def test_stock_restoration_failures_refuse_but_never_replace_primary(stock_source_scene, primary_failure, cleanup_failure):
    scene = stock_source_scene
    primary, cleanup = OSError("native source capture failed"), OSError("native source restore failed")

    def failed_capture():
        if primary_failure:
            raise primary
        return (0, 0)

    scene.feature.GetErrorCode2 = failed_capture
    if cleanup_failure == "activation":
        show = scene.source.ShowConfiguration2

        def restored(name):
            if name == "OriginalFinished":
                raise cleanup
            return show(name)

        scene.source.ShowConfiguration2 = restored
    elif cleanup_failure == "rebuild":
        rebuild = scene.source.EditRebuild3

        def rebuilt():
            if scene.state.target_seen and scene.state.active == "OriginalFinished":
                raise cleanup
            return rebuild()

        scene.source.EditRebuild3 = rebuilt
    else:
        original_by_name = scene.source.FeatureByName

        def visible_feature(name):
            feature = original_by_name(name)
            if scene.state.target_seen and scene.state.active == "OriginalFinished":
                raise cleanup
            return feature

        scene.source.FeatureByName = visible_feature
    with pytest.raises(OSError) as caught:
        _stock_capture(scene)
    assert caught.value is (primary if primary_failure else cleanup)
    if primary_failure:
        assert any("native source restore failed" in note for note in caught.value.__notes__)


def test_stock_capture_restores_saved_hidden_visibility_without_saving(stock_source_scene):
    scene = stock_source_scene
    show = scene.source.ShowConfiguration2

    def shown(name):
        result = show(name)
        if name == "OriginalFinished":
            scene.feature.Visible = scene.thread.Visible = 2
        return result

    scene.source.ShowConfiguration2 = shown
    _stock_capture(scene)
    assert scene.feature.Visible == scene.thread.Visible == 1
    assert ("blank", drawing.REFERENCE_SKETCHES) in scene.calls


@pytest.mark.parametrize("fault", (
    "foreign-source", "missing-source", "source-path", "view-path", "source-type",
    "configuration", "missing-configuration", "configuration-id", "view-type", "base-view",
    "cropped", "broken", "perspective", "break-lines", "breakout", "sheet-scale",
    "scale-ratio", "scale-decimal", "display-mode", "drawing-ink",
))
def test_projected_stock_ink_refuses_wrong_source_configuration_or_partial_view(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    stock = scene.stock
    if fault == "foreign-source":
        stock.ReferencedDocument = SimpleNamespace(**vars(scene.source))
    elif fault == "missing-source":
        stock.ReferencedDocument = None
    elif fault == "source-path":
        scene.source.GetPathName = lambda: "D:/foreign.SLDPRT"
    elif fault == "view-path":
        stock.GetReferencedModelName = lambda: "D:/foreign.SLDPRT"
    elif fault == "source-type":
        scene.source.GetType = lambda: 2
    elif fault == "configuration":
        stock.ReferencedConfiguration = "OriginalFinished"
    elif fault == "missing-configuration":
        scene.source.GetConfigurationByName = lambda _name: None
    elif fault == "configuration-id":
        scene.configuration.GetID = lambda: 24
    elif fault == "view-type":
        stock.Type = 3
    elif fault == "base-view":
        stock.GetBaseView = lambda: object()
    elif fault in ("cropped", "broken", "perspective"):
        setattr(stock, {"cropped": "IsCropped", "broken": "IsBroken", "perspective": "IsPerspectiveView"}[fault],
                lambda: True)
    elif fault == "break-lines":
        stock.GetBreakLines = lambda: (object(),)
    elif fault == "breakout":
        stock.GetBreakOutSectionCount = lambda: 1
    elif fault == "sheet-scale":
        stock.UseSheetScale = 1
    elif fault == "scale-ratio":
        stock.ScaleRatio = (1.0, 1.0)
    elif fault == "scale-decimal":
        stock.ScaleDecimal = 1.0
    elif fault == "display-mode":
        stock.GetDisplayMode2 = lambda: 1
    else:
        stock.GetSketch = lambda: SimpleNamespace(GetSketchSegments=lambda: (object(),))
    before = len(scene.calls)
    with pytest.raises(RuntimeError):
        drawing._supplier_stock_bounds(scene.adapter, stock, scene.source, capture)
    assert "view-update" not in scene.calls[before:]


@pytest.mark.parametrize("scale", (1.9, 2.1))
def test_actual_projected_spans_not_reported_scale_or_outline_prove_coverage(stock_source_scene, scale):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.stock.projection_scale = scale
    # Declared scale remains 2:1; the actual transform alone changes.
    with pytest.raises(RuntimeError, match="native ink does not cover"):
        drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, capture)


def test_actual_native_capture_and_current_frame_drive_diagram_centering(stock_source_scene, monkeypatch):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.adapter.currentModel = scene.model
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: scene.stock)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_show_hidden_owners", lambda *_args, **_kwargs: [drawing.SUPPLIER_STOCK_FEATURE])

    class Positioned(Exception):
        pass

    def positioned(*_args, **_kwargs):
        midpoint = (0.0, (drawing.SUPPLIER_STOCK_AXIS_MM[0][1]
                         + drawing.SUPPLIER_STOCK_AXIS_MM[-1][1]) / 2000.0, 0.0)
        actual = projection.model_points_in_view(scene.adapter, scene.stock, [midpoint], label="test center")[0]
        assert actual == pytest.approx(drawing.STOCK_CENTER)
        assert scene.stock.Position == pytest.approx((0.150, 0.2337375))
        raise Positioned

    monkeypatch.setattr(drawing, "curate_stock_dimensions", positioned)
    with pytest.raises(Positioned):
        drawing._supplier_stock_diagram(scene.adapter, scene.source, capture)
    assert scene.correspondences == scene.segments
    assert scene.state.active == "OriginalFinished"


@pytest.mark.parametrize("fault", ("missing", "extra", "no-correspondence", "not-shown"))
def test_source_inventory_and_showing_must_complete_before_stock_coverage(stock_source_scene, monkeypatch, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.adapter.currentModel = scene.model
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: scene.stock)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_show_hidden_owners", lambda *_args, **_kwargs: (
        [] if fault == "not-shown" else [drawing.SUPPLIER_STOCK_FEATURE]
    ))
    if fault == "missing":
        scene.segments.pop()
    elif fault == "extra":
        scene.segments.append(scene.lines[0])
    elif fault == "no-correspondence":
        scene.stock.GetCorresponding = lambda segment: None if segment is scene.lines[2] else object()
    with pytest.raises(RuntimeError):
        drawing._supplier_stock_diagram(scene.adapter, scene.source, capture)


def _stock_layout_scene(scene, monkeypatch):
    sheet = SimpleNamespace(GetProperties2=lambda: (0, 0, 0, 0, 0, 0.4318, 0.2794))
    draw = SimpleNamespace(ActivateSheet=lambda _name: True, GetCurrentSheet=lambda: sheet)
    scene.adapter.currentModel = draw
    monkeypatch.setattr(drawing, "iter_views", lambda _adapter: [scene.stock])
    monkeypatch.setattr(drawing, "sheet_drawable_region", lambda *_args, **_kwargs: SimpleNamespace(
        xmin=0.0127, ymin=0.0127, xmax=0.4191, ymax=0.2667,
    ))

    def note(text, extent):
        return SimpleNamespace(
            GetAnnotation=lambda: SimpleNamespace(OwnerType=1),
            PropertyLinkedText=text, GetText=lambda: text, GetExtent=lambda: extent,
        )

    notes = [
        (note("HEADER", (0.016, 0.259, 0.0, 0.100, 0.263, 0.0)), "HEADER", "HEADER"),
        (note("FOOTER", (0.016, 0.086, 0.0, 0.100, 0.090, 0.0)), "FOOTER", "FOOTER"),
    ]
    return {drawing.SHEET_NAMES[1]: (("stock",), drawing.SUPPLIER_STOCK_CONFIGURATION)}, {
        drawing.SHEET_NAMES[1]: notes,
    }


@pytest.mark.parametrize("fault", (None, "geometry-below", "geometry-above", "annotation"))
def test_settled_stock_layout_uses_actual_geometry_cell_and_native_annotation_ink(
    stock_source_scene, monkeypatch, fault,
):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.stock.Position = (0.150, 0.2337375)
    contracts, notes = _stock_layout_scene(scene, monkeypatch)
    if fault == "geometry-below":
        scene.stock.Position = (0.150, 0.224)
    elif fault == "geometry-above":
        scene.stock.Position = (0.150, 0.245)
    elif fault == "annotation":
        # Real shared annotation fit reads this view-owned note's actual ink.
        note = SimpleNamespace(
            GetExtent=lambda: (0.020, 0.090, 0.0, 0.040, 0.093, 0.0),
        )
        scene.stock.GetAnnotations = lambda: (SimpleNamespace(
            GetType=lambda: 6, GetSpecificAnnotation=lambda: note,
        ),)
    if fault is None:
        drawing._verify_supplier_layout(scene.adapter, contracts, notes, scene.source, capture)
    else:
        with pytest.raises(RuntimeError, match="leaves its cell"):
            drawing._verify_supplier_layout(scene.adapter, contracts, notes, scene.source, capture)
    assert scene.state.active == "OriginalFinished"


def test_finished_layout_keeps_the_original_getoutline_fit_operand(stock_source_scene, monkeypatch):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    contracts, notes = _stock_layout_scene(scene, monkeypatch)
    finished = drawing.SHEET_NAMES[0]
    contracts = {finished: contracts[drawing.SHEET_NAMES[1]]}
    notes = {finished: notes[drawing.SHEET_NAMES[1]] + notes[drawing.SHEET_NAMES[1]] + [notes[drawing.SHEET_NAMES[1]][0]]}
    outlines = []
    scene.stock.GetOutline = lambda: outlines.append("finished-outline") or (0.100, 0.100, 0.200, 0.200)
    drawing._verify_supplier_layout(scene.adapter, contracts, notes, scene.source, capture)
    assert outlines == ["finished-outline"]


@pytest.mark.parametrize("value", (None, object(), SimpleNamespace(geometry=())))
def test_stock_projection_rejects_non_capture_operands(stock_source_scene, value):
    scene = stock_source_scene
    with pytest.raises(RuntimeError, match="immutable source capture"):
        drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, value)


def test_stock_capture_rejects_live_or_mutable_geometry_operands(stock_source_scene):
    scene = stock_source_scene
    with pytest.raises(RuntimeError, match="immutable geometry"):
        drawing.SupplierStockCapture(scene.sketch, scene.source_path.as_posix(), drawing.SUPPLIER_STOCK_CONFIGURATION, 23)


@pytest.mark.parametrize("fault", ("source-path", "mutable-geometry", "configuration"))
def test_stock_capture_binding_is_not_a_nominal_geometry_escape_hatch(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    with pytest.raises(RuntimeError):
        if fault == "source-path":
            capture = replace(capture, source_path="D:/foreign.SLDPRT")
            drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, capture)
        elif fault == "mutable-geometry":
            replace(capture, geometry=list(capture.geometry.model_points))
        else:
            replace(capture, configuration="OriginalFinished")


@pytest.mark.parametrize("fault", ("activation-false", "activation-readback", "rebuild-false", "rebuild-drift"))
def test_stock_target_configuration_must_activate_and_settle_before_capture(stock_source_scene, fault):
    scene = stock_source_scene
    if fault == "activation-false":
        scene.source.ShowConfiguration2 = lambda _name: False
    elif fault == "activation-readback":
        scene.source.ShowConfiguration2 = lambda _name: True
    else:
        rebuild = scene.source.EditRebuild3

        def target_rebuild():
            if scene.state.active == drawing.SUPPLIER_STOCK_CONFIGURATION:
                if fault == "rebuild-false":
                    return False
                scene.state.active = "Wrong"
            return rebuild()

        scene.source.EditRebuild3 = target_rebuild
    with pytest.raises(RuntimeError):
        _stock_capture(scene)
    assert scene.state.active == "OriginalFinished"
    assert scene.scalar_reads == []


@pytest.mark.parametrize("value", (math.nan, math.inf, 0.0))
def test_stock_scale_decimal_must_be_finite_and_exact(stock_source_scene, value):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.stock.ScaleDecimal = value
    with pytest.raises(RuntimeError, match="native view/scale"):
        drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, capture)


@pytest.mark.parametrize("fault", ("source-read", "dimension-read", "geometry-read"))
def test_stock_capture_propagates_original_native_getter_failure_after_restoring(stock_source_scene, fault):
    scene = stock_source_scene
    error = OSError(f"native {fault} failed")

    def failed(*_args):
        raise error

    if fault == "source-read":
        scene.source.GetBodies2 = failed
    elif fault == "dimension-read":
        scene.dimensions["SupplierStockOverall"].GetSystemValue3 = failed
    else:
        scene.circles[0].GetRadius = failed
    with pytest.raises(OSError) as caught:
        _stock_capture(scene)
    assert caught.value is error and scene.state.active == "OriginalFinished"


@pytest.mark.parametrize("delta,passes", (
    (-0.5e-7, True), (-1.1e-7, False), (0.00599, True), (0.00601, False),
))
def test_actual_stock_span_keeps_the_original_lower_and_padding_upper_budgets(stock_source_scene, delta, passes):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.stock.projection_scale = 2.0 * (1.0 + delta / 0.1524)
    if passes:
        drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, capture)
    else:
        with pytest.raises(RuntimeError, match="native ink does not cover") as caught:
            drawing._supplier_stock_bounds(scene.adapter, scene.stock, scene.source, capture)
        assert "expected=[" in str(caught.value) and "actual=" in str(caught.value)


def test_stock_capture_matches_native_curves_without_relying_on_inventory_order(stock_source_scene):
    scene = stock_source_scene
    scene.segments.reverse()
    for line in scene.lines:
        line.start, line.end = line.end, line.start
    capture = _stock_capture(scene)
    assert len(capture.geometry.circle_offsets) == 3 and len(capture.geometry.line_offsets) == 6


def test_scalar_stock_refusal_identifies_configuration_name_actual_and_expected(stock_source_scene):
    scene = stock_source_scene
    scene.values["SupplierStockOverall"] = 0.0
    with pytest.raises(RuntimeError) as caught:
        _stock_capture(scene)
    message = str(caught.value)
    assert "SupplierStockOverall" in message and drawing.SUPPLIER_STOCK_CONFIGURATION in message
    assert "native value 0 mm" in message and "exact expected 76.2 mm" in message

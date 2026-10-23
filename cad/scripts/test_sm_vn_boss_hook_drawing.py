"""Offline manufacturing boundaries for the modified purchased anchor."""

from dataclasses import FrozenInstanceError, replace
from io import StringIO
import json
import logging
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
    document_state = SimpleNamespace(path="")
    scene.model.GetPathName = lambda: document_state.path
    iso = SimpleNamespace(
        Name="finished-iso", ReferencedConfiguration="Finished", ReferencedDocument=scene.source,
    )
    stock = SimpleNamespace(
        Name="stock-front", ReferencedConfiguration=drawing.SUPPLIER_STOCK_CONFIGURATION,
        ReferencedDocument=scene.source,
    )
    refs_by_sheet, contracts, displays_by_sheet, annotations_by_sheet = {}, {}, {}, {}
    attachment = SimpleNamespace(entities=[scene.eye], kinds=[46], dangling=False, count=1)
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
            display = SimpleNamespace(GetDimension2=lambda _index, native=native: native)
            displays.append(display)
            refs.append((key, {"label": name}))
        if sheet_name == "FINISHED":
            for name in drawing.FRONT_KEEP:
                native = SimpleNamespace(FullName=f"{name}@machining@eye.SLDPRT")
                displays.append(SimpleNamespace(GetDimension2=lambda _index, native=native: native))
        annotations = []
        for display in displays:
            annotation = SimpleNamespace(
                _interfaces={"IAnnotation"}, Owner=view, OwnerType=0, GetType=lambda: 4,
                GetSpecificAnnotation=lambda display=display: display,
                GetAttachedEntities3=lambda: tuple(attachment.entities),
                GetAttachedEntityTypes=lambda: tuple(attachment.kinds),
                GetAttachedEntityCount3=lambda: attachment.count,
                IsDangling=lambda: attachment.dangling,
            )
            display.GetAnnotation = lambda annotation=annotation: annotation
            annotations.append(annotation)
        annotations_by_sheet[sheet_name] = annotations
        view.GetAnnotations = lambda annotations=annotations: tuple(annotations)
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
        annotations=annotations_by_sheet, document_state=document_state,
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


class _StockSourceCurve(SimpleNamespace):
    def __getattr__(self, name):
        if name in ("Color", "Width", "Style", "Layer", "LayerOverride"):
            pytest.fail(f"queried undefined source/LayerOverride property {name}")
        raise AttributeError(name)


@pytest.fixture
def stock_source_scene(monkeypatch, tmp_path):
    """Exercise real capture/analytic projection with offline COM boundaries."""
    calls, scalar_reads, body_reads, correspondences = [], [], [], []

    def bind(value, kind):
        supported = getattr(value, "_interfaces", None)
        if supported is not None and kind not in supported:
            raise TypeError(f"native object does not expose {kind}")
        return value

    for module in (drawing, supplier_dimensions, reference_geometry, purchased_drawing):
        monkeypatch.setattr(module, "_early_bound", bind)
    monkeypatch.setattr(reference_geometry, "_bind", bind)
    monkeypatch.setattr(projection, "double_array", tuple)
    monkeypatch.setattr(drawing, "double_array", tuple)
    monkeypatch.setattr(drawing, "bstr_array", tuple)
    source_path = tmp_path / "anchor.SLDPRT"
    monkeypatch.setattr(drawing, "SOURCE", source_path)
    state = SimpleNamespace(
        active="OriginalFinished", changed_visibility=False, target_seen=False,
        selected=None, selected_count=1, selected_kind=24, select_result=True,
        after_select=None, after_color=None, after_drawing_rebuild=None,
    )

    def point(xyz):
        return SimpleNamespace(X=xyz[0], Y=xyz[1], Z=xyz[2])

    circles = []
    for center, radius in (
        ((0.0, 0.0, 0.0), drawing.SUPPLIER_NOMINAL_EYE_OD_MM / 2000.0),
        ((0.0, 0.0, 0.0), drawing.SUPPLIER_EYE_ID_MM / 2000.0),
        ((0.03, 0.0, 0.0), drawing.SUPPLIER_NOMINAL_WIRE_MM / 2000.0),
    ):
        circle = _StockSourceCurve(
            center=point(center), radius=radius, ConstructionGeometry=True,
            _interfaces={"ISketchSegment", "ISketchArc"},
        )
        circle.GetType = lambda: 1
        circle.IsCircle = lambda: 1
        circle.GetCenterPoint2 = lambda circle=circle: circle.center
        circle.GetRadius = lambda circle=circle: circle.radius
        circle.GetLength = lambda circle=circle: math.tau * circle.radius
        circles.append(circle)
    outline = drawing.SUPPLIER_STOCK_SHANK_OUTLINE_MM
    pairs = [
        (outline[index], outline[(index + 1) % len(outline)])
        for index in range(len(outline))
    ] + list(zip(drawing.SUPPLIER_STOCK_AXIS_MM, drawing.SUPPLIER_STOCK_AXIS_MM[1:]))
    lines = []
    for start, end in pairs:
        line = _StockSourceCurve(
            start=point((start[0] / 1000.0, start[1] / 1000.0, 0.0)),
            end=point((end[0] / 1000.0, end[1] / 1000.0, 0.0)),
            ConstructionGeometry=True, GetType=lambda: 0,
            _interfaces={"ISketchSegment", "ISketchLine"},
        )
        line.GetStartPoint2 = lambda line=line: line.start
        line.GetEndPoint2 = lambda line=line: line.end
        line.GetLength = lambda line=line: math.dist(
            (line.start.X, line.start.Y, line.start.Z), (line.end.X, line.end.Y, line.end.Z),
        )
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
    mapped, selections, colors = {}, [], []

    def make_instance(source, native_id=None):
        instance = _StockSourceCurve(
            _interfaces=set(source._interfaces), native_id=object() if native_id is None else native_id,
            ConstructionGeometry=source.ConstructionGeometry, GetType=source.GetType,
            Color=0x808080, Width=0, Style=2, Layer="",
        )
        if source.GetType() == 1:
            instance.center = point((source.center.X, source.center.Y, source.center.Z))
            instance.radius = source.radius
            instance.IsCircle = lambda: 1
            instance.GetCenterPoint2 = lambda: instance.center
            instance.GetRadius = lambda: instance.radius
            instance.GetLength = lambda: math.tau * instance.radius
        else:
            instance.start = point((source.start.X, source.start.Y, source.start.Z))
            instance.end = point((source.end.X, source.end.Y, source.end.Z))
            instance.GetStartPoint2 = lambda: instance.start
            instance.GetEndPoint2 = lambda: instance.end
            instance.GetLength = lambda: math.dist(
                (instance.start.X, instance.start.Y, instance.start.Z),
                (instance.end.X, instance.end.Y, instance.end.Z),
            )

        def select(append, data):
            assert append is False and data.View is stock
            assert model.ActiveDrawingView is stock and state.selected is None
            selections.append((instance, append, data.View))
            state.selected = instance
            if state.after_select is not None:
                state.after_select(instance)
            return state.select_result

        instance.Select4 = select
        return instance

    for source_curve in segments:
        mapped[id(source_curve)] = make_instance(source_curve)

    def corresponding(segment):
        correspondences.append(segment)
        return mapped.get(id(segment))

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
        GetCorresponding=corresponding,
        GetOutline=lambda: pytest.fail("stock geometry must not use a cached view outline"),
    )
    utility = SimpleNamespace(CreatePoint=lambda xyz: _StockMathPoint(xyz))
    def clear(all_selections):
        assert all_selections is True
        calls.append("clear")
        state.selected = None

    def activate(name):
        assert name in ("", stock.Name)
        model.ActiveDrawingView = stock if name else None
        calls.append(("activate-view", name))
        return name != ""

    def set_color(color):
        assert model.ActiveDrawingView is stock and color == 0
        assert state.selected is not None and state.selected_count == 1 and state.selected_kind == 24
        colors.append(state.selected)
        state.selected.Color = color
        if state.after_color is not None:
            state.after_color(state.selected)
        # IDrawingDoc.SetLineColor is VOID, deliberately return None.

    def drawing_rebuild():
        calls.append("drawing-rebuild")
        if state.after_drawing_rebuild is not None:
            state.after_drawing_rebuild()
        return True

    model = SimpleNamespace(
        EditRebuild3=drawing_rebuild, ClearSelection2=clear, ActivateView=activate,
        ActiveDrawingView=None, SetLineColor=set_color,
        SelectionManager=SimpleNamespace(
            CreateSelectData=lambda: SimpleNamespace(View=None),
            GetSelectedObjectCount2=lambda _mark: state.selected_count,
            GetSelectedObjectType3=lambda _index, _mark: state.selected_kind,
            GetSelectedObject6=lambda _index, _mark: state.selected,
        ),
        Extension=SimpleNamespace(SelectByID2=lambda *_args: pytest.fail("profile must never use a point fallback")),
    )
    adapter = SimpleNamespace(
        currentModel=source,
        swApp=SimpleNamespace(
            IsSame=lambda first, second: int(
                getattr(first, "native_id", first) is getattr(second, "native_id", second)
            ),
            GetMathUtility=lambda: utility,
        ),
    )
    monkeypatch.setattr(drawing, "view_name", lambda _adapter, view: view.Name)
    return SimpleNamespace(
        adapter=adapter, source=source, stock=stock, state=state, feature=feature,
        thread=thread, configuration=configuration, sketch=sketch, segments=segments,
        circles=circles, lines=lines, dimensions=dimensions, displays=displays,
        values=values, calls=calls, scalar_reads=scalar_reads, body_reads=body_reads,
        correspondences=correspondences, model=model, source_path=source_path,
        mapped=mapped, selections=selections, colors=colors, make_instance=make_instance,
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
        scene.mapped[id(scene.lines[2])] = None
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


def _saved_key_scene(scene, monkeypatch):
    """Exercise native-shaped identity capture, not proof of a real saved seat."""
    settled = _settled_supplier_scene(scene, monkeypatch)
    output = scene.source_path.parent / "sm-vn-boss-hook.SLDDRW"
    monkeypatch.setattr(drawing, "OUTPUTS", replace(drawing.OUTPUTS, slddrw=output))
    prior = drawing._verify_supplier_references(scene.adapter, settled.refs, settled.contracts)
    return SimpleNamespace(
        settled=settled, prior=prior, document_state=settled.document_state, output=output,
        annotations=settled.annotations, original=settled.annotations["FINISHED"][0],
        eye_display=settled.displays["FINISHED"][0],
    )


def _save_supplier_keys(saved):
    """Simulate native getters changing; production never transforms an old key."""
    saved.document_state.path = str(saved.output.resolve())
    for refs in saved.settled.displays.values():
        for display in refs:
            native = display.GetDimension2(0)
            native.FullName += "@actual-saved-container"
    # No common spelling or suffix grammar connects this fresh physical key to
    # its old key. Only the original native annotation can identify it.
    saved.eye_display.GetDimension2(0).FullName = "native-saved-physical-key"


def _capture_saved(scene, saved):
    return drawing._capture_saved_supplier_references(
        scene.adapter, saved.settled.refs, saved.settled.contracts, saved.prior,
    )


def test_saved_capture_accepts_only_current_exact_key_of_original_annotation(
    supplier_eye_scene, monkeypatch,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    old_refs = {sheet: list(refs) for sheet, refs in saved.settled.refs.items()}
    old_keys = tuple(item.expected_key for item in saved.prior)
    _save_supplier_keys(saved)
    note = SimpleNamespace(
        _interfaces={"IAnnotation"}, GetType=lambda: 6,
        GetSpecificAnnotation=lambda: pytest.fail("cast an unrelated note to IDisplayDimension"),
    )
    saved.annotations["FINISHED"].append(note)
    mappings = len(scene.mappings)
    captured = _capture_saved(scene, saved)
    assert len(scene.mappings) == mappings, "identity capture must not read stale geometry"
    assert captured is not saved.settled.refs and captured["FINISHED"] is not old_refs["FINISHED"]
    assert captured["FINISHED"][0][0] == "native-saved-physical-key"
    assert captured["FINISHED"][0][1] is saved.settled.refs["FINISHED"][0][1]
    assert saved.settled.refs == old_refs
    assert tuple(item.expected_key for item in saved.prior) == old_keys
    assert saved.prior[0].drawing_path == ""
    assert saved.prior[0].annotation is saved.original
    assert saved.prior[0].view is scene.front and saved.prior[0].drawing_document is scene.model
    assert saved.prior[0].source_document is scene.source
    with pytest.raises(FrozenInstanceError):
        saved.prior[0].expected_key = "changed"
    # The old strict keys remain strict even after a successful identity capture.
    with pytest.raises(RuntimeError, match="settled supplier dimension disappeared"):
        drawing._verify_supplier_references(scene.adapter, saved.settled.refs, saved.settled.contracts)
    current = drawing._verify_supplier_references(scene.adapter, captured, saved.settled.contracts)
    assert len(current) == 6 and current[0].expected_key == "native-saved-physical-key"
    assert len(scene.mappings) == mappings + 1
    assert scene.picks == scene.projections == scene.visible_queries == []


@pytest.mark.parametrize("equality", (0, -1, 2, True, "1", 1.0))
def test_saved_capture_refuses_wrong_or_unknown_original_annotation_identity(
    supplier_eye_scene, monkeypatch, equality,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    same = scene.adapter.swApp.IsSame
    scene.adapter.swApp.IsSame = lambda first, second: (
        equality if first is saved.original and second is saved.original else same(first, second)
    )
    with pytest.raises(RuntimeError):
        _capture_saved(scene, saved)


@pytest.mark.parametrize("fault", (
    "missing", "duplicate", "foreign-same-key", "non-dimension", "missing-display",
    "wrong-display-interface", "foreign-display-annotation", "missing-native", "empty-key", "duplicate-key",
))
def test_saved_capture_requires_one_typed_original_current_annotation(
    supplier_eye_scene, monkeypatch, fault,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    if fault == "missing":
        saved.annotations["FINISHED"].remove(saved.original)
    elif fault == "duplicate":
        saved.annotations["FINISHED"].append(saved.original)
    elif fault == "foreign-same-key":
        replacement = SimpleNamespace(
            _interfaces={"IAnnotation"}, Owner=scene.front, OwnerType=0, GetType=lambda: 4,
            GetSpecificAnnotation=lambda: saved.eye_display,
        )
        saved.annotations["FINISHED"][0] = replacement
    elif fault == "non-dimension":
        saved.original.GetType = lambda: 6
        saved.original.GetSpecificAnnotation = lambda: pytest.fail("cast a note to a dimension")
    elif fault == "missing-display":
        saved.original.GetSpecificAnnotation = lambda: None
    elif fault == "wrong-display-interface":
        saved.original.GetSpecificAnnotation = lambda: SimpleNamespace(_interfaces={"INote"})
    elif fault == "foreign-display-annotation":
        saved.eye_display.GetAnnotation = lambda: SimpleNamespace(_interfaces={"IAnnotation"})
    elif fault == "missing-native":
        saved.eye_display.GetDimension2 = lambda _index: None
    elif fault == "empty-key":
        saved.eye_display.GetDimension2(0).FullName = ""
    else:
        saved.eye_display.GetDimension2(0).FullName = saved.settled.displays["FINISHED"][1].GetDimension2(0).FullName
    with pytest.raises((RuntimeError, TypeError)):
        _capture_saved(scene, saved)


@pytest.mark.parametrize("owner_type", (1, 3, False, "0"))
def test_saved_capture_never_interprets_sheet_or_part_owner_as_view(
    supplier_eye_scene, monkeypatch, owner_type,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)

    class ForeignOwner:
        def __getattribute__(self, name):
            pytest.fail(f"foreign owner was accessed as a view: {name}")

    foreign = ForeignOwner()
    saved.original.OwnerType = owner_type
    saved.original.Owner = foreign
    bind = drawing._early_bound

    def typed(value, interface):
        assert value is not foreign, "foreign owner was bound as IView"
        return bind(value, interface)

    monkeypatch.setattr(drawing, "_early_bound", typed)
    with pytest.raises(RuntimeError, match="drawing-view owner 0"):
        _capture_saved(scene, saved)


@pytest.mark.parametrize("fault", (
    "wrong-output", "alias-output", "missing-output", "drawing-identity", "view-identity",
    "duplicate-view", "missing-view", "source-identity", "wrong-source-path", "alias-source-path",
    "missing-source", "wrong-configuration", "foreign-owner", "missing-owner", "unknown-owner",
    "unknown-drawing", "unknown-view", "unknown-source",
))
def test_saved_capture_refuses_foreign_binding_metadata_or_output(
    supplier_eye_scene, monkeypatch, fault,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    if fault == "wrong-output":
        saved.document_state.path = str(saved.output.with_name("foreign.SLDDRW"))
    elif fault == "alias-output":
        saved.document_state.path = str(saved.output.parent / "alias" / ".." / saved.output.name)
    elif fault == "missing-output":
        saved.document_state.path = ""
    elif fault == "drawing-identity":
        scene.adapter.currentModel = SimpleNamespace(
            GetPathName=lambda: saved.document_state.path, ActivateSheet=scene.model.ActivateSheet,
        )
    elif fault in ("view-identity", "duplicate-view", "missing-view"):
        foreign = SimpleNamespace(
            Name=scene.front.Name, ReferencedDocument=scene.source, ReferencedConfiguration="Finished",
            GetAnnotations=scene.front.GetAnnotations,
        )
        views = drawing.iter_views

        def current_views(adapter):
            if scene.state.sheet != "FINISHED":
                return views(adapter)
            return (
                (foreign, saved.settled.iso) if fault == "view-identity"
                else (scene.front, foreign, saved.settled.iso) if fault == "duplicate-view"
                else (saved.settled.iso,)
            )

        monkeypatch.setattr(drawing, "iter_views", current_views)
    elif fault == "source-identity":
        scene.front.ReferencedDocument = SimpleNamespace(GetPathName=scene.source.GetPathName)
    elif fault == "wrong-source-path":
        scene.source.GetPathName = lambda: str(scene.source_path.with_name("foreign.SLDPRT"))
    elif fault == "alias-source-path":
        scene.source.GetPathName = lambda: str(
            scene.source_path.parent / "alias" / ".." / scene.source_path.name
        )
    elif fault == "missing-source":
        scene.front.ReferencedDocument = None
    elif fault == "wrong-configuration":
        scene.front.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
    elif fault == "foreign-owner":
        saved.original.Owner = SimpleNamespace(
            Name=scene.front.Name, ReferencedDocument=scene.source, ReferencedConfiguration="Finished",
        )
    elif fault == "missing-owner":
        saved.original.Owner = None
    else:
        target = {
            "unknown-owner": scene.front, "unknown-drawing": scene.model,
            "unknown-view": scene.front, "unknown-source": scene.source,
        }[fault]
        same = scene.adapter.swApp.IsSame
        scene.adapter.swApp.IsSame = lambda first, second: (
            -1 if first is target and second is target else same(first, second)
        )
    with pytest.raises(RuntimeError):
        _capture_saved(scene, saved)


@pytest.mark.parametrize("stage", ("pre-save", "post-save"))
@pytest.mark.parametrize("getter", ("drawing-path", "source-path", "annotation-kind", "annotations", "identity"))
def test_native_identity_metadata_read_failures_refuse_instead_of_best_effort_acceptance(
    supplier_eye_scene, monkeypatch, stage, getter,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    error = OSError(f"{getter} unavailable")

    def failed(*_args):
        raise error

    if getter == "drawing-path":
        scene.model.GetPathName = failed
    elif getter == "source-path":
        scene.source.GetPathName = failed
    elif getter == "annotation-kind":
        saved.original.GetType = failed
    elif getter == "annotations":
        if stage == "pre-save":
            # Pre-save identity uses the exact strictly verified display, not
            # an independent annotation enumeration.
            saved.eye_display.GetAnnotation = failed
        else:
            scene.front.GetAnnotations = failed
    else:
        scene.adapter.swApp.IsSame = failed
    if stage == "post-save":
        _save_supplier_keys(saved)
    with pytest.raises(OSError) as caught:
        if stage == "pre-save":
            drawing._verify_supplier_references(scene.adapter, saved.settled.refs, saved.settled.contracts)
        else:
            _capture_saved(scene, saved)
    assert caught.value is error


def test_failed_capture_keeps_original_references_and_frozen_snapshot_unchanged(
    supplier_eye_scene, monkeypatch,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    refs = {sheet: tuple((key, dict(contract)) for key, contract in rows)
            for sheet, rows in saved.settled.refs.items()}
    before = tuple(vars(item).copy() for item in saved.prior)
    _save_supplier_keys(saved)
    # Fail on the final sheet after earlier current keys were already captured.
    saved.annotations["SUPPLIER-STOCK"].pop()
    with pytest.raises(RuntimeError, match="one current original supplier annotation"):
        _capture_saved(scene, saved)
    assert refs == {sheet: tuple(rows) for sheet, rows in saved.settled.refs.items()}
    for original, frozen in zip(saved.prior, before, strict=True):
        assert vars(original) == frozen


def test_original_snapshots_are_never_captured_before_complete_strict_geometry_checks(
    supplier_eye_scene, monkeypatch,
):
    scene = supplier_eye_scene
    settled = _settled_supplier_scene(scene, monkeypatch)
    settled.displays["SUPPLIER-STOCK"][-1].GetDimension2(0).Tolerance.Type = 1
    monkeypatch.setattr(
        drawing, "_capture_supplier_reference_identity",
        lambda *_args: pytest.fail("captured identities before complete strict supplier checks"),
    )
    with pytest.raises(RuntimeError, match="tolerance band"):
        drawing._verify_supplier_references(scene.adapter, settled.refs, settled.contracts)


def test_saved_identity_success_cannot_bypass_current_physical_geometry(
    supplier_eye_scene, monkeypatch,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    captured = _capture_saved(scene, saved)
    saved.settled.attachment.entities = [scene.outer]
    with pytest.raises(RuntimeError, match="exact physical source contour"):
        drawing._verify_supplier_references(scene.adapter, captured, saved.settled.contracts)


def test_identity_capture_cannot_advance_unsaved_drawing_to_new_key_contract(
    supplier_eye_scene, monkeypatch,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    with pytest.raises(RuntimeError, match="not the native output"):
        _capture_saved(scene, saved)
    current = drawing._verify_supplier_references(scene.adapter, saved.settled.refs, saved.settled.contracts)
    assert tuple(item.expected_key for item in current) == tuple(item.expected_key for item in saved.prior)


@pytest.mark.parametrize("duplicate", (False, True))
def test_current_annotation_matching_uses_native_identity_not_python_wrapper_identity(
    supplier_eye_scene, monkeypatch, duplicate,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    current = SimpleNamespace(**vars(saved.original))
    saved.eye_display.GetAnnotation = lambda: current
    saved.annotations["FINISHED"][0] = current
    if duplicate:
        saved.annotations["FINISHED"].append(SimpleNamespace(**vars(current)))
    native_matches = [saved.original, *saved.annotations["FINISHED"][:1]]
    if duplicate:
        native_matches.append(saved.annotations["FINISHED"][-1])
    same = scene.adapter.swApp.IsSame

    def native_same(first, second):
        if any(first is value for value in native_matches) and any(
            second is value for value in native_matches
        ):
            return 1
        return same(first, second)

    scene.adapter.swApp.IsSame = native_same
    assert current is not saved.original
    if duplicate:
        with pytest.raises(RuntimeError, match="one current original supplier annotation; actual=2"):
            _capture_saved(scene, saved)
    else:
        captured = _capture_saved(scene, saved)
        assert captured["FINISHED"][0][0] == "native-saved-physical-key"
        drawing._verify_supplier_references(scene.adapter, captured, saved.settled.contracts)


@pytest.mark.parametrize("fault", ("identity", "unknown", "configuration", "source-path", "source-identity"))
def test_native_owner_proof_rejects_foreign_or_inconsistent_same_name_view(
    supplier_eye_scene, monkeypatch, fault,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    owner = SimpleNamespace(
        Name=scene.front.Name, ReferencedConfiguration="Finished", ReferencedDocument=scene.source,
    )
    saved.original.Owner = owner
    same = scene.adapter.swApp.IsSame

    def native_same(first, second):
        if first is owner and second is scene.front:
            return 0 if fault == "identity" else -1 if fault == "unknown" else 1
        return same(first, second)

    scene.adapter.swApp.IsSame = native_same
    if fault == "configuration":
        owner.ReferencedConfiguration = drawing.SUPPLIER_STOCK_CONFIGURATION
    elif fault in ("source-path", "source-identity"):
        owner.ReferencedDocument = SimpleNamespace(
            GetPathName=(
                (lambda: str(scene.source_path.with_name("foreign.SLDPRT")))
                if fault == "source-path" else scene.source.GetPathName
            ),
        )
    with pytest.raises(RuntimeError):
        _capture_saved(scene, saved)


@pytest.mark.parametrize("fault", ("unpublished-original", "missing-original", "duplicate-original", "foreign-original-key", "foreign-label"))
def test_saved_capture_requires_complete_original_reference_contract(
    supplier_eye_scene, monkeypatch, fault,
):
    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    _save_supplier_keys(saved)
    if fault == "unpublished-original":
        saved.prior = None
    elif fault == "missing-original":
        saved.prior = saved.prior[:-1]
    elif fault == "duplicate-original":
        saved.prior = (*saved.prior[:-1], saved.prior[0])
    elif fault == "foreign-original-key":
        saved.prior = (replace(saved.prior[0], expected_key="foreign-original"), *saved.prior[1:])
    else:
        saved.prior = (replace(saved.prior[0], label="ForeignLabel"), *saved.prior[1:])
    with pytest.raises(RuntimeError):
        _capture_saved(scene, saved)


def test_failed_identity_capture_cannot_replace_original_native_save_error(
    supplier_eye_scene, monkeypatch,
):
    from _drawing_common import _drawing_checkpoint

    scene = supplier_eye_scene
    saved = _saved_key_scene(scene, monkeypatch)
    save_error = OSError("native SaveAs3 failed before output path changed")
    old_keys = tuple(item.expected_key for item in saved.prior)

    def observe(event):
        if event == "after_drawing_save":
            _capture_saved(scene, saved)

    with pytest.raises(OSError) as caught:
        with _drawing_checkpoint(observe, "drawing_save"):
            raise save_error
    assert caught.value is save_error
    assert any("after_drawing_save checkpoint also failed" in note for note in save_error.__notes__)
    assert any("not the native output" in note for note in save_error.__notes__)
    assert tuple(item.expected_key for item in saved.prior) == old_keys
    assert saved.document_state.path == ""


def test_pre_save_identity_snapshot_refuses_shared_native_annotation_for_two_references(
    supplier_eye_scene, monkeypatch,
):
    scene = supplier_eye_scene
    settled = _settled_supplier_scene(scene, monkeypatch)
    eye_annotation = settled.annotations["FINISHED"][0]
    settled.displays["FINISHED"][1].GetAnnotation = lambda: eye_annotation
    with pytest.raises(RuntimeError, match="distinct native annotations"):
        drawing._verify_supplier_references(scene.adapter, settled.refs, settled.contracts)


def _blacken_stock(scene, capture):
    scene.adapter.currentModel = scene.model
    return drawing._blacken_supplier_stock_profile(scene.adapter, scene.stock, scene.source, capture)


@pytest.fixture
def stock_identity_failure_scene(stock_source_scene, monkeypatch):
    """Existing stock scene with independently represented raw/typed selection."""
    scene = stock_source_scene
    capture = _stock_capture(scene)
    mapped_owner = SimpleNamespace(context="drawing profile")
    selected_owner = SimpleNamespace(context="selected drawing profile")
    active_configuration = SimpleNamespace(Name="OriginalFinished", GetID=lambda: 11)
    scene.source.ConfigurationManager = SimpleNamespace(ActiveConfiguration=active_configuration)
    scene.model.GetPathName = lambda: "D:/output/sm_vn_boss_hook.SLDDRW"
    scene.stock.GetName2 = lambda: scene.stock.Name
    reverse_reads, selected_view_reads, receipts, emitted_selected, none_binds = [], [], [], [], []
    for index, source in enumerate(scene.segments):
        source.GetID = lambda index=index: (101, index)
        source.GetSketch = lambda: scene.sketch
        mapped = scene.mapped[id(source)]
        # Deliberately different pairs across contexts: never assert preservation.
        mapped.GetID = lambda index=index: (201, index)
        mapped.GetSketch = lambda: mapped_owner
    typed = scene.make_instance(scene.circles[0])
    typed.GetID = lambda: (301, 0)
    typed.GetSketch = lambda: selected_owner
    raw = _StockSourceCurve(**vars(typed))

    def reverse(owner):
        reverse_reads.append(owner)
        assert owner is mapped_owner or owner is selected_owner
        return scene.sketch

    def selected_view(index, mark):
        selected_view_reads.append((index, mark, scene.state.selected))
        assert (index, mark) == (1, -1) and scene.state.selected is not None
        return scene.stock

    scene.model.Extension.GetCorresponding2 = reverse
    scene.model.SelectionManager.GetSelectedObjectsDrawingView2 = selected_view
    original_bind = drawing._early_bound

    def bind(value, interface):
        if value is None:
            none_binds.append(interface)
            raise AssertionError("never bind a null diagnostic prerequisite")
        if value is raw and interface == "ISketchSegment":
            return typed
        return original_bind(value, interface)

    def emit(message):
        prefix = "supplier stock selection identity REPORTING ONLY / NO MUTATING PROBES: "
        assert message.startswith(prefix)
        receipts.append(json.loads(message[len(prefix):]))
        emitted_selected.append(scene.state.selected)

    native_warn = drawing._telemetry.warn
    monkeypatch.setattr(drawing, "_early_bound", bind)
    monkeypatch.setattr(drawing._telemetry, "warn", emit)
    scene.state.after_select = lambda _mapped: setattr(scene.state, "selected", raw)
    return SimpleNamespace(
        scene=scene, capture=capture, raw=raw, typed=typed, mapped_owner=mapped_owner,
        selected_owner=selected_owner, active_configuration=active_configuration,
        reverse_reads=reverse_reads, selected_view_reads=selected_view_reads,
        receipts=receipts, emitted_selected=emitted_selected, none_binds=none_binds,
        native_warn=native_warn,
    )


def _stock_identity_receipt(diagnostic):
    context, = (entry["fields"] for entry in diagnostic.receipts if entry["section"] == "context")
    rows = [entry["fields"] for entry in diagnostic.receipts if entry["section"] == "row"]
    assert len(rows) == 9
    return context, rows


def test_selection_identity_receipt_reaches_default_warning_console(
    stock_identity_failure_scene, monkeypatch,
):
    diagnostic = stock_identity_failure_scene
    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    output = StringIO()
    console = logging.StreamHandler(output)
    console.setLevel(drawing._telemetry._console_level())
    logger = logging.Logger("hook-profile-selection-test", logging.DEBUG)
    logger.propagate = False
    logger.addHandler(console)
    monkeypatch.setattr(drawing._telemetry, "get_logger", lambda: logger)
    monkeypatch.setattr(drawing._telemetry, "warn", diagnostic.native_warn)
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(diagnostic.scene, diagnostic.capture)
    prefix = "supplier stock selection identity REPORTING ONLY / NO MUTATING PROBES: "
    lines = output.getvalue().splitlines()
    assert len(lines) == 10
    assert all(line.startswith(prefix) for line in lines)
    receipts = [json.loads(line[len(prefix):]) for line in lines]
    assert [entry["section"] for entry in receipts].count("context") == 1
    assert [entry["section"] for entry in receipts].count("row") == 9
    assert diagnostic.scene.colors == [] and diagnostic.scene.state.selected is None


def test_selection_identity_receipt_is_null_safe_and_still_refuses(stock_identity_failure_scene):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    scene.state.after_select = lambda _mapped: setattr(scene.state, "selected", None)
    same = scene.adapter.swApp.IsSame
    null_comparisons = []

    def no_null_same(first, second):
        if first is None or second is None:
            null_comparisons.append((first, second))
            raise AssertionError("null is not a native selected identity")
        return same(first, second)

    scene.adapter.swApp.IsSame = no_null_same
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(scene, diagnostic.capture)
    context, rows = _stock_identity_receipt(diagnostic)
    assert context["selectedNone"] == {"value": True, "python_type": "builtins.bool", "error": None}
    assert context["selected.typed"]["value"] is None
    assert context["selected.raw.GetType"]["error"] == "not queried: null or unavailable prerequisite"
    assert all(row["selected.raw_to_mapped.forward"]["value"] is None for row in rows)
    assert diagnostic.none_binds == diagnostic.selected_view_reads == null_comparisons == []
    assert scene.colors == [] and scene.state.selected is None


def test_selection_identity_refusal_reports_all_nine_exact_inputs_before_cleanup(stock_identity_failure_scene):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(scene, diagnostic.capture)
    context, rows = _stock_identity_receipt(diagnostic)
    assert context["selectedNone"]["value"] is False
    assert context["original_error"]["value"] == (
        "supplier nominal stock black profile: selection is not the exact mapped native curve"
    )
    assert (context["Select4"]["value"], context["selection_count"]["value"],
            context["selection_type"]["value"], context["expected_index"]["value"]) == (True, 1, 24, 0)
    assert [row["index"]["value"] for row in rows] == list(range(9))
    assert [row["index"]["value"] for row in rows if row["expected"]["value"]] == [0]
    for index, row in enumerate(rows):
        assert row["source.GetID"]["value"] == [101, index]
        assert row["mapped.GetID"]["value"] == [201, index]
        assert row["source.GetID"]["python_type"] == "builtins.tuple"
        assert row["source.GetID[0]"]["python_type"] == "builtins.int"
        assert row["source.GetType"]["value"] == row["mapped.GetType"]["value"] == (1 if index < 3 else 0)
        for name in ("source.self", "mapped.self", "source.owner.self",
                     "source.owner.to_authoritative.forward", "mapped.owner.reverse.self",
                     "mapped.owner.reverse.to_authoritative.forward"):
            assert row[name]["value"] == 1 and row[name]["error"] is None
        for name in ("source_to_mapped.forward", "source_to_mapped.reverse",
                     "selected.raw_to_mapped.forward", "selected.raw_to_mapped.reverse",
                     "selected.raw_to_source.forward", "selected.raw_to_source.reverse",
                     "mapped.owner.to_authoritative.forward"):
            assert row[name]["value"] == 0 and row[name]["error"] is None
    assert context["selected.raw.GetID"]["value"] == context["selected.typed.GetID"]["value"] == [301, 0]
    assert context["selected.raw_to_typed.forward"]["value"] == 1
    assert context["selected.raw.self"]["value"] == context["selected.typed.self"]["value"] == 1
    assert context["selected.raw.owner.reverse.to_authoritative.forward"]["value"] == 1
    assert context["drawing.GetPathName"]["value"] == "D:/output/sm_vn_boss_hook.SLDDRW"
    assert context["source.GetPathName"]["value"] == str(scene.source_path.resolve())
    assert context["capture.source_path"]["value"] == diagnostic.capture.source_path
    assert context["capture.configuration_id"]["value"] == 23
    assert context["source.active_configuration.Name"]["value"] == "OriginalFinished"
    assert context["source.active_configuration.GetID"]["value"] == 11
    assert context["source.expected_configuration.Name"]["value"] == drawing.SUPPLIER_STOCK_CONFIGURATION
    assert context["source.expected_configuration.GetID"]["value"] == 23
    assert context["source.active_to_expected_configuration.forward"]["value"] == 0
    for name in ("stock_view", "active_view", "data_view", "selected_view"):
        assert context[f"{name}.to_expected.forward"]["value"] == 1
        assert context[f"{name}.ReferencedDocument.to_source.forward"]["value"] == 1
        assert context[f"{name}.GetName2"]["value"] == scene.stock.Name
        assert context[f"{name}.GetReferencedModelName"]["value"] == str(scene.source_path.resolve())
        assert context[f"{name}.ReferencedConfiguration"]["value"] == drawing.SUPPLIER_STOCK_CONFIGURATION
    for name in ("source", "mapped", "selected.raw", "selected.typed"):
        assert context[f"candidate.{name}.GetLength.finite"]["value"] is True
        assert context[f"candidate.{name}.GetRadius.finite"]["value"] is True
        assert context[f"candidate.{name}.center.X"]["value"] == 0.0
    assert all(value is diagnostic.raw for value in diagnostic.emitted_selected)
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("raw_result", (0, 1, 2, 3))
def test_selection_identity_raw_controls_record_all_native_codes_without_accepting(
    stock_identity_failure_scene, raw_result,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    mapped = scene.mapped[id(scene.circles[0])]
    same = scene.adapter.swApp.IsSame

    def observed(first, second):
        if first is diagnostic.raw and (second is diagnostic.raw or second is scene.circles[0]):
            return raw_result
        if first is mapped and second is diagnostic.raw:
            return raw_result
        if first is diagnostic.typed and second is mapped:
            return 1  # Even a typed-interface match cannot rescue raw inequality.
        return same(first, second)

    scene.adapter.swApp.IsSame = observed
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(scene, diagnostic.capture)
    context, rows = _stock_identity_receipt(diagnostic)
    for field in (
        context["selected.raw.self"], rows[0]["selected.raw_to_source.forward"],
        rows[0]["selected.raw_to_mapped.reverse"],
    ):
        assert field == {"value": raw_result, "python_type": "builtins.int", "error": None}
    assert rows[0]["selected.raw_to_mapped.forward"]["value"] == 0
    assert rows[0]["selected.typed_to_mapped.forward"]["value"] == 1
    assert scene.colors == [] and scene.state.selected is None


def test_selection_identity_receipt_isolates_geometry_owner_and_view_getter_errors(
    stock_identity_failure_scene, monkeypatch,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene

    def fail(message):
        raise OSError(message)

    class PartialPoint:
        X = property(lambda _self: fail("selected X getter failed"))
        Y = float("nan")
        Z = 0.125

    class Data:
        def __init__(self):
            self.view = None

        @property
        def View(self):
            if scene.state.selected is not None:
                fail("data View getter failed")
            return self.view

        @View.setter
        def View(self, value):
            self.view = value

    class Drawing:
        def __getattr__(self, name):
            if name == "ActiveDrawingView" and scene.state.selected is not None:
                fail("active View getter failed")
            return getattr(scene.model, name)

    original_bind = drawing._early_bound
    document = Drawing()
    monkeypatch.setattr(drawing, "_early_bound", lambda value, interface: (
        document if value is scene.model and interface == "IDrawingDoc"
        else original_bind(value, interface)
    ))
    scene.model.SelectionManager.CreateSelectData = Data
    scene.model.SelectionManager.GetSelectedObjectsDrawingView2 = lambda *_args: fail("selected View getter failed")
    reverse = scene.model.Extension.GetCorresponding2
    scene.model.Extension.GetCorresponding2 = lambda owner: (
        fail("selected reverse owner failed") if owner is diagnostic.selected_owner else reverse(owner)
    )
    diagnostic.raw.GetType = lambda: fail("raw type getter failed")
    diagnostic.raw.GetID = lambda: fail("raw ID getter failed")
    diagnostic.raw.GetLength = lambda: fail("raw length getter failed")
    diagnostic.typed.center = PartialPoint()
    diagnostic.typed.radius = float("inf")
    scene.circles[0].GetSketch = lambda: fail("source owner getter failed")
    scene.mapped[id(scene.circles[1])].GetSketch = lambda: None
    scene.mapped[id(scene.circles[2])].GetID = lambda: fail("mapped ID getter failed")
    same = scene.adapter.swApp.IsSame

    def bad_control(first, second):
        if first is diagnostic.raw and second is scene.circles[1]:
            fail("raw comparison failed")
        return same(first, second)

    scene.adapter.swApp.IsSame = bad_control
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(scene, diagnostic.capture)
    context, rows = _stock_identity_receipt(diagnostic)
    for name, message in (
        ("selected.raw.GetType", "raw type getter failed"),
        ("selected.raw.GetID", "raw ID getter failed"),
        ("candidate.selected.raw.GetLength", "raw length getter failed"),
        ("candidate.selected.typed.center.X", "selected X getter failed"),
        ("selected.raw.owner.GetCorresponding2", "selected reverse owner failed"),
        ("active_view.raw", "active View getter failed"),
        ("data_view.raw", "data View getter failed"),
        ("selected_view.raw", "selected View getter failed"),
    ):
        assert context[name]["value"] is None
        assert context[name]["error"] == f"OSError: {message}"
    assert context["candidate.selected.typed.center.Y"]["value"] == "nan"
    assert context["candidate.selected.typed.center.Y"]["python_type"] == "builtins.float"
    assert context["candidate.selected.typed.center.Y.finite"]["value"] is False
    assert context["candidate.selected.typed.center.Z"]["value"] == 0.125
    assert context["candidate.selected.typed.GetRadius"]["value"] == "inf"
    assert context["candidate.selected.typed.GetRadius.finite"]["value"] is False
    assert context["selected.typed.GetType"]["value"] == 1
    assert rows[0]["source.GetSketch"]["error"] == "OSError: source owner getter failed"
    assert rows[1]["mapped.GetSketch"] == {"value": None, "python_type": "builtins.NoneType", "error": None}
    assert rows[1]["selected.raw_to_source.forward"]["error"] == "OSError: raw comparison failed"
    assert rows[1]["selected.raw_to_source.reverse"]["value"] == 0
    assert rows[2]["mapped.GetID"]["error"] == "OSError: mapped ID getter failed"
    assert rows[2]["mapped.GetType"]["value"] == 1
    assert rows[8]["mapped.owner.reverse.to_authoritative.forward"]["value"] == 1
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("guard_result", (0, 2, 3))
def test_selection_identity_reporter_failure_preserves_original_guard_error(
    stock_identity_failure_scene, monkeypatch, guard_result,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    mapped = scene.mapped[id(scene.circles[0])]
    same = scene.adapter.swApp.IsSame
    scene.adapter.swApp.IsSame = lambda first, second: (
        guard_result if first is diagnostic.raw and second is mapped else same(first, second)
    )

    def broken_reporter(*_args):
        raise KeyboardInterrupt("reporter failed")

    monkeypatch.setattr(drawing, "_report_supplier_selection_identity", broken_reporter)
    with pytest.raises(RuntimeError) as caught:
        _blacken_stock(scene, diagnostic.capture)
    expected = (
        "selection is not the exact mapped native curve" if guard_result == 0
        else f"unknown native IsSame={guard_result}"
    )
    assert str(caught.value) == f"supplier nominal stock black profile: {expected}"
    assert scene.colors == [] and scene.state.selected is None


def test_selection_identity_emitter_failure_preserves_original_exception_object(
    stock_identity_failure_scene, monkeypatch,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    mapped = scene.mapped[id(scene.circles[0])]
    same = scene.adapter.swApp.IsSame
    primary = OSError("native selected identity getter failed")
    attempts = []

    def selected_identity(first, second):
        if first is diagnostic.raw and second is mapped:
            raise primary
        return same(first, second)

    def broken_emitter(message):
        attempts.append(message)
        raise OSError("receipt log unavailable")

    scene.adapter.swApp.IsSame = selected_identity
    monkeypatch.setattr(drawing._telemetry, "warn", broken_emitter)
    with pytest.raises(OSError) as caught:
        _blacken_stock(scene, diagnostic.capture)
    assert caught.value is primary
    assert len(attempts) == 10  # Context plus every bounded row, despite log failures.
    assert scene.colors == [] and scene.state.selected is None


def test_selection_identity_receipt_never_reenumerates_repicks_styles_or_changes_configuration(
    stock_identity_failure_scene,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    before = [
        (drawing._supplier_profile_curve(source, "before"), drawing._supplier_profile_curve(mapped, "before"),
         mapped.Color, mapped.Width, mapped.Style, mapped.Layer)
        for source in scene.segments
        for mapped in (scene.mapped[id(source)],)
    ]
    calls_before = len(scene.calls)
    prohibited = []

    def forbid(name):
        def call(*_args, **_kwargs):
            prohibited.append(name)
            raise AssertionError(f"diagnostic must not call {name}")
        return call

    def selected(_mapped):
        scene.state.selected = diagnostic.raw
        scene.sketch.GetSketchSegments = forbid("GetSketchSegments")
        scene.stock.GetCorresponding = forbid("GetCorresponding")
        scene.source.ShowConfiguration2 = forbid("ShowConfiguration2")
        scene.source.Save3 = forbid("source.Save3")
        scene.source.SaveAs3 = forbid("source.SaveAs3")
        scene.model.Save3 = forbid("drawing.Save3")
        scene.model.SaveAs3 = forbid("drawing.SaveAs3")
        scene.model.SetLineColor = forbid("SetLineColor")
        scene.model.EditRebuild3 = forbid("EditRebuild3")
        scene.model.Extension.SelectByID2 = forbid("SelectByID2")

    scene.state.after_select = selected
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(scene, diagnostic.capture)
    _stock_identity_receipt(diagnostic)
    assert prohibited == []
    assert len(scene.selections) == 1 and scene.colors == []
    assert scene.correspondences == scene.segments
    assert scene.state.active == "OriginalFinished" and scene.state.selected is None
    assert scene.stock.ReferencedConfiguration == drawing.SUPPLIER_STOCK_CONFIGURATION
    assert scene.feature.Visible == scene.thread.Visible == 1
    assert not any(
        isinstance(call, tuple) and call[0] in ("show", "source-rebuild", "blank")
        for call in scene.calls[calls_before:]
    )
    assert [
        (drawing._supplier_profile_curve(source, "after"), drawing._supplier_profile_curve(mapped, "after"),
         mapped.Color, mapped.Width, mapped.Style, mapped.Layer)
        for source in scene.segments
        for mapped in (scene.mapped[id(source)],)
    ] == before


def test_successful_exact_stock_selection_never_reports_or_uses_diagnostic_getters(
    stock_identity_failure_scene, monkeypatch,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    scene.state.after_select = None
    reports = []

    def forbidden_report(*args):
        reports.append(args)
        raise AssertionError("the successful path must bypass reporting")

    monkeypatch.setattr(drawing, "_report_supplier_selection_identity", forbidden_report)
    assert _blacken_stock(scene, diagnostic.capture) is None
    assert reports == diagnostic.receipts == diagnostic.reverse_reads == diagnostic.selected_view_reads == []
    assert len(scene.selections) == len(scene.colors) == 9
    assert scene.state.active == "OriginalFinished" and scene.state.selected is None


@pytest.mark.parametrize("expected_index", (3, 8))
def test_selection_identity_receipt_marks_later_line_candidate_without_repairing_selection(
    stock_identity_failure_scene, expected_index,
):
    diagnostic = stock_identity_failure_scene
    scene = diagnostic.scene
    rejected = scene.mapped[id(scene.segments[expected_index])]

    def selected(mapped):
        if mapped is rejected:
            # Even the wrong primitive kind is merely reported, never repicked.
            scene.state.selected = diagnostic.raw

    scene.state.after_select = selected
    with pytest.raises(RuntimeError, match="selection is not the exact mapped native curve"):
        _blacken_stock(scene, diagnostic.capture)
    context, rows = _stock_identity_receipt(diagnostic)
    assert context["expected_index"]["value"] == expected_index
    assert [row["index"]["value"] for row in rows if row["expected"]["value"]] == [expected_index]
    source = scene.segments[expected_index]
    assert context["candidate.source.start.X"]["value"] == source.start.X
    assert context["candidate.source.end.Y"]["value"] == source.end.Y
    assert context["candidate.mapped.start.X.finite"]["value"] is True
    assert context["candidate.mapped.end.Y.finite"]["value"] is True
    assert context["candidate.selected.raw.ISketchLine"]["error"] == (
        "TypeError: native object does not expose ISketchLine"
    )
    assert len(scene.selections) == expected_index + 1
    assert len(scene.colors) == expected_index
    assert rejected.Color == diagnostic.raw.Color == diagnostic.typed.Color == 0x808080
    assert scene.state.selected is None and scene.state.active == "OriginalFinished"


def test_black_stock_profile_changes_only_all_nine_exact_drawing_instance_colors(stock_source_scene):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    before = {
        id(source): (
            source.ConstructionGeometry, source.GetType(), source.GetLength(),
            instance.Width, instance.Style, instance.Layer,
        )
        for source in scene.segments
        for instance in (scene.mapped[id(source)],)
    }
    spare = scene.make_instance(scene.circles[0])
    calls_before = len(scene.calls)
    assert _blacken_stock(scene, capture) is None
    instances = [scene.mapped[id(source)] for source in scene.segments]
    assert [entry[0] for entry in scene.selections] == instances
    assert scene.colors == instances
    assert sorted(segment.GetType() for segment in scene.colors) == [0] * 6 + [1] * 3
    assert all(append is False and view is scene.stock for _segment, append, view in scene.selections)
    for source, instance in zip(scene.segments, instances, strict=True):
        assert source is not instance
        assert instance.Color == 0 and type(instance.Color) is int
        assert (
            instance.ConstructionGeometry, instance.GetType(), instance.GetLength(),
            instance.Width, instance.Style, instance.Layer,
        ) == before[id(source)]
        assert source.ConstructionGeometry is True
    assert spare.Color == 0x808080
    assert scene.state.selected is None and scene.state.active == "OriginalFinished"
    assert scene.feature.Visible == scene.thread.Visible == 1
    assert not any(isinstance(call, tuple) and call[0] in ("show", "source-rebuild", "blank")
                   for call in scene.calls[calls_before:])
    assert scene.correspondences == scene.segments * 2


@pytest.mark.parametrize("fault", (
    "source-identity", "source-path", "view-path", "view-configuration",
    "configuration-id", "missing-configuration", "capture-path", "source-type",
))
def test_black_profile_requires_exact_source_view_configuration_before_any_setter(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    if fault == "source-identity":
        scene.stock.ReferencedDocument = SimpleNamespace(**vars(scene.source))
    elif fault == "source-path":
        scene.source.GetPathName = lambda: "D:/foreign.SLDPRT"
    elif fault == "view-path":
        scene.stock.GetReferencedModelName = lambda: "D:/foreign.SLDPRT"
    elif fault == "view-configuration":
        scene.stock.ReferencedConfiguration = "OriginalFinished"
    elif fault == "configuration-id":
        scene.configuration.GetID = lambda: 24
    elif fault == "missing-configuration":
        scene.source.GetConfigurationByName = lambda _name: None
    elif fault == "capture-path":
        capture = replace(capture, source_path="D:/foreign.SLDPRT")
    else:
        scene.source.GetType = lambda: 2
    with pytest.raises(RuntimeError):
        _blacken_stock(scene, capture)
    assert scene.selections == scene.colors == []


@pytest.mark.parametrize("fault", (
    "missing-circle", "missing-line", "extra", "duplicate-source", "missing-map",
    "duplicate-map", "source-as-map", "wrong-feature", "wrong-feature-type",
    "source-circle-drift", "source-line-drift", "mapped-circle-drift", "mapped-line-drift",
    "mapped-length-drift", "mapped-construction", "mapped-partial-circle",
    "mapped-circle-bool", "mapped-kind", "mapped-circle-interface",
))
def test_black_profile_refuses_incomplete_foreign_duplicate_or_changed_native_inventory(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    circle = scene.mapped[id(scene.circles[0])]
    line = scene.mapped[id(scene.lines[0])]
    if fault == "missing-circle":
        scene.segments.remove(scene.circles[0])
    elif fault == "missing-line":
        scene.segments.remove(scene.lines[0])
    elif fault == "extra":
        scene.segments.append(scene.lines[0])
    elif fault == "duplicate-source":
        scene.segments[-1] = scene.segments[-2]
    elif fault == "missing-map":
        scene.mapped[id(scene.circles[1])] = None
    elif fault == "duplicate-map":
        scene.mapped[id(scene.circles[1])] = circle
    elif fault == "source-as-map":
        scene.mapped[id(scene.circles[0])] = scene.circles[0]
    elif fault == "wrong-feature":
        scene.feature.Name = "ForeignProfile"
    elif fault == "wrong-feature-type":
        scene.feature.GetTypeName2 = lambda: "3DProfileFeature"
    elif fault == "source-circle-drift":
        scene.circles[0].center.X += 0.001
    elif fault == "source-line-drift":
        scene.lines[0].end.Y += 0.001
    elif fault == "mapped-circle-drift":
        circle.radius += 0.001
    elif fault == "mapped-line-drift":
        line.end.X += 0.001
    elif fault == "mapped-length-drift":
        line.GetLength = lambda: 0.001
    elif fault == "mapped-construction":
        circle.ConstructionGeometry = False
    elif fault == "mapped-partial-circle":
        circle.IsCircle = lambda: 0
    elif fault == "mapped-circle-bool":
        circle.IsCircle = lambda: True
    elif fault == "mapped-kind":
        circle.GetType = lambda: 3
    else:
        circle._interfaces.remove("ISketchSegment")
    with pytest.raises((RuntimeError, TypeError)):
        _blacken_stock(scene, capture)
    assert scene.selections == scene.colors == []


@pytest.mark.parametrize("count", (0, 2, True, 1.0))
def test_black_profile_requires_exact_native_selected_count_one(stock_source_scene, count):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.state.selected_count = count
    with pytest.raises(RuntimeError, match="one native EXTSKETCHSEGMENT"):
        _blacken_stock(scene, capture)
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("kind", (1, 12, 25, 46, True, 24.0))
def test_black_profile_requires_native_external_sketch_segment_not_other_kind(stock_source_scene, kind):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.state.selected_kind = kind
    with pytest.raises(RuntimeError, match="one native EXTSKETCHSEGMENT"):
        _blacken_stock(scene, capture)
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("fault", ("missing", "foreign-same-geometry", "selected-source"))
def test_black_profile_selected_object_must_be_exact_mapped_native_identity(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    foreign = scene.make_instance(scene.circles[0])

    def changed(_instance):
        scene.state.selected = (
            None if fault == "missing" else scene.circles[0] if fault == "selected-source" else foreign
        )

    scene.state.after_select = changed
    with pytest.raises(RuntimeError, match="exact mapped native curve"):
        _blacken_stock(scene, capture)
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("same", (True, False, -1, 2, 3, 1.0, "1", None))
def test_black_profile_never_coerces_native_issame_results(stock_source_scene, same):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    original_same = scene.adapter.swApp.IsSame

    def is_same(first, second):
        if scene.state.selected is not None and first is scene.state.selected and second is first:
            return same
        return original_same(first, second)

    scene.adapter.swApp.IsSame = is_same
    with pytest.raises(RuntimeError, match="unknown native IsSame"):
        _blacken_stock(scene, capture)
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("circle_index", (0, 1, 2))
@pytest.mark.parametrize("result", (False, None, 1))
def test_all_three_circles_require_typed_select4_without_fallback(stock_source_scene, circle_index, result):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    rejected = scene.mapped[id(scene.circles[circle_index])]
    scene.state.after_select = lambda segment: setattr(
        scene.state, "select_result", result if segment is rejected else True,
    )
    with pytest.raises(RuntimeError, match="Select4 refused"):
        _blacken_stock(scene, capture)
    assert len(scene.selections) == circle_index + 1
    assert scene.selections[-1][0] is rejected and rejected.GetType() == 1
    assert len(scene.colors) == circle_index and scene.state.selected is None


@pytest.mark.parametrize("field", ("radius", "length", "construction", "type", "Width", "Style", "Layer"))
def test_selected_native_geometry_and_appearance_are_rechecked_before_color(stock_source_scene, field):
    scene = stock_source_scene
    capture = _stock_capture(scene)

    def drift(segment):
        if field == "radius":
            segment.radius += 0.001
        elif field == "length":
            segment.GetLength = lambda: 0.001
        elif field == "construction":
            segment.ConstructionGeometry = False
        elif field == "type":
            segment.GetType = lambda: 3
        else:
            setattr(segment, field, "FOREIGN" if field == "Layer" else 99)

    scene.state.after_select = drift
    with pytest.raises(RuntimeError):
        _blacken_stock(scene, capture)
    assert scene.colors == [] and scene.state.selected is None


@pytest.mark.parametrize("color", (0x808080, -1, False, None))
def test_void_color_setter_must_read_back_integer_black(stock_source_scene, color):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.state.after_color = lambda segment: setattr(segment, "Color", color)
    with pytest.raises(RuntimeError, match="color expected=0"):
        _blacken_stock(scene, capture)
    assert len(scene.colors) == 1 and scene.state.selected is None


@pytest.mark.parametrize("field", ("radius", "length", "construction", "type", "Width", "Style", "Layer"))
def test_color_setter_must_not_change_curve_or_width_style_layer(stock_source_scene, field):
    scene = stock_source_scene
    capture = _stock_capture(scene)

    def drift(segment):
        if field == "radius":
            segment.radius += 0.001
        elif field == "length":
            segment.GetLength = lambda: 0.001
        elif field == "construction":
            segment.ConstructionGeometry = False
        elif field == "type":
            segment.GetType = lambda: 3
        else:
            setattr(segment, field, "FOREIGN" if field == "Layer" else 99)

    scene.state.after_color = drift
    with pytest.raises(RuntimeError):
        _blacken_stock(scene, capture)
    assert len(scene.colors) == 1 and scene.state.selected is None


def test_native_color_setter_failure_preserves_error_and_clears_selection(stock_source_scene):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    failure = OSError("native SetLineColor refused")

    def refused(_color):
        raise failure

    scene.model.SetLineColor = refused
    with pytest.raises(OSError) as caught:
        _blacken_stock(scene, capture)
    assert caught.value is failure
    assert scene.state.selected is None


def test_black_profile_reacquires_fresh_instances_after_drawing_rebuild(stock_source_scene):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    old = tuple(scene.mapped.values())

    def stale(*_args):
        pytest.fail("read stale native curve after drawing rebuild")

    def refresh():
        for source in scene.segments:
            previous = scene.mapped[id(source)]
            current = scene.make_instance(source, previous.native_id)
            current.Color = previous.Color
            scene.mapped[id(source)] = current
            previous.GetType = previous.GetLength = stale
        scene.segments.reverse()  # Native enumeration order is not identity.

    scene.state.after_drawing_rebuild = refresh
    _blacken_stock(scene, capture)
    assert all(current is not previous for current, previous in zip(scene.mapped.values(), old, strict=True))
    assert len(scene.colors) == 9 and all(instance.Color == 0 for instance in scene.mapped.values())


@pytest.mark.parametrize("fault", ("color", "Width", "Style", "Layer", "geometry", "identity", "rebuild"))
def test_black_profile_properties_must_survive_the_settling_rebuild(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)

    def changed():
        segment = scene.mapped[id(scene.circles[0])]
        if fault == "color":
            segment.Color = 0x808080
        elif fault in ("Width", "Style", "Layer"):
            setattr(segment, fault, "FOREIGN" if fault == "Layer" else 99)
        elif fault == "geometry":
            segment.radius += 0.001
        elif fault == "identity":
            replacement = scene.make_instance(scene.circles[0])
            replacement.Color = 0
            scene.mapped[id(scene.circles[0])] = replacement

    if fault == "rebuild":
        scene.model.EditRebuild3 = lambda: False
    else:
        scene.state.after_drawing_rebuild = changed
    with pytest.raises(RuntimeError):
        _blacken_stock(scene, capture)
    assert len(scene.colors) == 9 and scene.state.selected is None


@pytest.mark.parametrize("fault", ("activation-refused", "foreign-active-view", "foreign-selection-view"))
def test_black_profile_requires_exact_activated_and_selection_bound_stock_view(stock_source_scene, fault):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    if fault == "activation-refused":
        scene.model.ActivateView = lambda _name: False
    elif fault == "foreign-active-view":
        scene.model.ActivateView = lambda _name: setattr(scene.model, "ActiveDrawingView", object()) or True
    else:
        class ForeignSelectData:
            @property
            def View(self):
                return scene.source

            @View.setter
            def View(self, _view):
                pass

        scene.model.SelectionManager.CreateSelectData = ForeignSelectData
    with pytest.raises(RuntimeError):
        _blacken_stock(scene, capture)
    assert scene.colors == scene.selections == []


def test_black_profile_refuses_distinct_source_proxies_with_duplicate_native_identity(stock_source_scene):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.circles[0].native_id = scene.circles[1].native_id = object()
    with pytest.raises(RuntimeError, match="duplicate native source"):
        _blacken_stock(scene, capture)
    assert scene.colors == scene.selections == []


class _SupplierCalloutDisplay(SimpleNamespace):
    def __getattr__(self, name):
        if name == "OffsetText":
            pytest.fail("diametric callouts must not query unavailable OffsetText")
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == "OffsetText":
            pytest.fail("diametric callouts must not set unavailable OffsetText")
        super().__setattr__(name, value)


@pytest.fixture
def stock_diagram_scene(stock_source_scene, monkeypatch):
    """Real existing annotation curation, with native import/export boundaries mocked."""
    from solidworks_mcp.adapters.solidworks import drawing as native_drawing

    scene = stock_source_scene
    scene.capture = _stock_capture(scene)
    scene.adapter.currentModel = scene.model
    scene.adapter._attempt = lambda operation: operation()
    monkeypatch.setattr(drawing, "place_view", lambda *_args, **_kwargs: scene.stock)
    monkeypatch.setattr(drawing, "set_hidden_lines_removed", lambda *_args: None)
    monkeypatch.setattr(drawing, "_show_hidden_owners", lambda *_args, **_kwargs: [drawing.SUPPLIER_STOCK_FEATURE])
    monkeypatch.setattr(
        native_drawing._sw_type_info, "early_bound_or_flag",
        lambda value, _kind, *_members: value,
    )
    monkeypatch.setattr(native_drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, annotation: annotation.name)
    old_keep = {
        "SupplierNominalEyeOD": (0.180, 0.244),
        "SupplierNominalWire": (0.255, 0.235),
        "SupplierStockShank": (0.105, 0.160),
        "SupplierStockOverall": (0.065, 0.175),
    }
    annotations, placed, contracts, notes = [], [], [], []
    for name, old in old_keep.items():
        native = scene.dimensions[name]
        display = _SupplierCalloutDisplay(GetDimension2=lambda _index, native=native: native)
        annotation = SimpleNamespace(
            name=name, position=(*old, 0.0002),
            GetSpecificAnnotation=lambda display=display: display,
        )

        def set_position(x, y, _z, annotation=annotation):
            placed.append((annotation.name, (x, y)))
            annotation.position = (x, y, 0.0002)
            return True

        annotation.SetPosition = set_position
        annotation.GetPosition = lambda annotation=annotation: annotation.position
        display.GetAnnotation = lambda annotation=annotation: annotation
        annotations.append(annotation)

    def curate(actual_adapter, stock, *, keep, view_label, dimensions_by_feature):
        assert actual_adapter is scene.adapter and stock is scene.stock
        assert dimensions_by_feature is drawing.SUPPLIER_STOCK_DIMENSIONS
        assert view_label == "as-supplied nominal stock envelope and wire section"
        return native_drawing.curate_dimensions(actual_adapter, annotations, reposition=keep)

    def reference(_adapter, display, **contract):
        contracts.append(contract)
        return display

    def note(_adapter, text, x, y):
        assert scene.model.ActiveDrawingView is None
        notes.append((text, x, y))
        return SimpleNamespace()

    monkeypatch.setattr(drawing, "curate_stock_dimensions", curate)
    monkeypatch.setattr(drawing, "supplier_reference_dimension", reference)
    monkeypatch.setattr(drawing, "add_note", note)
    monkeypatch.setattr(drawing, "sheet_drawable_region", lambda *_args, **_kwargs: SimpleNamespace(
        xmin=0.0127, ymin=0.0127, xmax=0.4191, ymax=0.2667,
    ))
    scene.model.GetEditSheet = lambda: scene.model.ActiveDrawingView is None
    scene.model.GetCurrentSheet = lambda: SimpleNamespace(
        GetProperties2=lambda: (0, 0, 0, 0, 0, 0.4318, 0.2794),
    )
    scene.annotations, scene.placed, scene.contracts, scene.notes = annotations, placed, contracts, notes
    return scene


def test_supplier_diagram_uses_supported_complete_annotation_curation_without_changing_source(stock_diagram_scene):
    scene = stock_diagram_scene
    values = dict(scene.values)
    stock, refs, notes = drawing._supplier_stock_diagram(scene.adapter, scene.source, scene.capture)
    assert stock is scene.stock and len(refs) == 4 and len(notes) == 2
    assert dict(scene.placed) == {
        "SupplierNominalEyeOD": (0.200, 0.250),
        "SupplierNominalWire": (0.255, 0.235),
        "SupplierStockShank": (0.105, 0.159),
        "SupplierStockOverall": (0.065, 0.175),
    }
    assert len(scene.colors) == 9 and scene.model.ActiveDrawingView is None
    assert scene.values == values and scene.state.active == "OriginalFinished"
    assert scene.feature.Visible == scene.thread.Visible == 1
    eye = next(contract for contract in scene.contracts if contract["label"] == "SupplierNominalEyeOD")
    assert eye == {
        "label": "SupplierNominalEyeOD", "expected_mm": spec.SUPPLIER_NOMINAL_EYE_OD_MM,
        "units": "in", "precision": spec.SUPPLIER_REFERENCE_PRECISION["SupplierNominalEyeOD"],
        "presentation": "diameter", "fraction_denominator": spec.SUPPLIER_FRACTION_DENOMINATOR,
        "callout": "NOMINAL EYE ENVELOPE",
    }
    assert scene.notes[0][0] == "SUPPLIER NOMINAL STOCK ENVELOPE — AS SUPPLIED"
    assert scene.notes[0][1:] == pytest.approx((0.016, 0.2627))
    assert scene.notes[1] == (
        "NOMINAL PROFILE ONLY — INSTALLED VENDOR-CAD EYE UNCHANGED\n"
        "STOCK REFERENCES ONLY — FINISHED TRIM AND CHAMFER: SHEET 1",
        0.016, 0.089,
    )
    assert drawing.STOCK_SCALE == (2.0, 1.0)
    assert scene.stock.Position == pytest.approx((0.150, 0.2337375))


@pytest.mark.parametrize("name", ("SupplierNominalEyeOD", "SupplierStockShank"))
@pytest.mark.parametrize("position", (None, (), (0.180, 0.244, 0.0002), (math.nan, 0.250, 0.0002)))
def test_complete_supplier_annotation_placement_requires_finite_exact_readback(stock_diagram_scene, name, position):
    scene = stock_diagram_scene
    annotation = next(item for item in scene.annotations if item.name == name)
    annotation.GetPosition = lambda: position
    with pytest.raises(RuntimeError, match="did not retain its placement"):
        drawing._supplier_stock_diagram(scene.adapter, scene.source, scene.capture)


# Raw original native text rows from the recovered 9bb same-saved-attempt SM
# layout audit. These immutable measurements are offline translation regressions,
# not native proof that the new diameter leader takes a collision-free route.
_EYE_NATIVE_ROWS_MM = (
    ("(", 168.7712, 244.2722, 1.7208, 3.5),
    ("<MOD-DIAM>", 170.4920, 244.2187, 5.2784, 3.5),
    ("11", 176.7962, 246.8294, 5.1722, 3.5),
    ("16", 176.7962, 242.2011, 5.1722, 3.5),
    ('" in)', 182.9941, 244.2722, 8.2347, 3.5),
    ("NOMINAL EYE ENVELOPE", 152.2674, 236.6449, 55.4653, 3.5),
)


def _translated_eye_rows_mm(anchor):
    dx, dy = anchor[0] * 1000.0 - 180.0, anchor[1] * 1000.0 - 244.0
    return tuple(
        (text, (x + dx, y + dy, x + dx + width, y + dy + height))
        for text, x, y, width, height in _EYE_NATIVE_ROWS_MM
    )


def _boxes_clear(first, second, gap):
    return (
        first[2] + gap <= second[0] or second[2] + gap <= first[0]
        or first[3] + gap <= second[1] or second[3] + gap <= first[1]
    )


@pytest.mark.parametrize("anchor, clears", (
    ((0.180, 0.244), False),  # Original label crosses the large nominal eye.
    ((0.200, 0.244), False),  # Rejected shelf intersects the separate wire circle.
    (drawing.STOCK_KEEP["SupplierNominalEyeOD"], True),
))
def test_complete_eye_callout_translates_every_native_row_clear_of_all_three_circles(anchor, clears):
    rows = _translated_eye_rows_mm(anchor)
    # Actual PDF wire-circle ink bounds; eye circle extrema agree with the
    # proved immutable source profile projected at the retained 2:1 stock frame.
    circles = (
        (132.5375, 216.2750, 167.4625, 251.2000),
        (142.0625, 225.8000, 157.9375, 241.6750),
        (205.237494, 228.974999, 214.762494, 238.499999),
    )
    assert all(_boxes_clear(box, circle, 3.5) for _text, box in rows for circle in circles) is clears
    if clears:
        label = dict(rows)["NOMINAL EYE ENVELOPE"]
        assert label == pytest.approx((172.2674, 242.6449, 227.7327, 246.1449))
        assert label[0] - circles[0][2] == pytest.approx(4.8049)
        assert label[1] - circles[2][3] == pytest.approx(4.144901)


@pytest.mark.parametrize("anchor, fits", (
    (drawing.STOCK_KEEP["SupplierNominalEyeOD"], True),
    ((0.200, 0.252), False),  # Label alone fits, but the fraction numerator does not.
))
def test_complete_native_eye_fraction_and_label_rows_fit_unchanged_stock_cell(anchor, fits):
    rows = _translated_eye_rows_mm(anchor)
    cell = (12.7, 94.0, 419.1, 257.7)
    inside = all(
        cell[0] <= box[0] <= box[2] <= cell[2] and cell[1] <= box[1] <= box[3] <= cell[3]
        for _text, box in rows
    )
    assert inside is fits
    if fits:
        top = max(box[3] for _text, box in rows)
        assert top == pytest.approx(256.3294)
        assert cell[3] - top == pytest.approx(1.3706)
        assert min(box[0] for _text, box in rows) == pytest.approx(172.2674)


@pytest.mark.parametrize("anchor, clears", (
    ((0.105, 0.160), False),
    (drawing.STOCK_KEEP["SupplierStockShank"], True),
))
def test_shank_complete_printed_block_gap_to_overall_keeps_actual_height_threshold(anchor, clears):
    # Whole actual PDF glyph boxes, including numerator/denominator/qualifier.
    shank = (72.1415, 153.2055, 137.7278, 167.2446)
    overall = (40.5463, 170.3776, 89.4443, 179.5646)
    dx, dy = anchor[0] * 1000.0 - 105.0, anchor[1] * 1000.0 - 160.0
    translated = (shank[0] + dx, shank[1] + dy, shank[2] + dx, shank[3] + dy)
    actual_text_height = 3.9386
    assert _boxes_clear(translated, overall, actual_text_height) is clears
    if clears:
        gap = overall[1] - translated[3]
        assert gap == pytest.approx(4.1330)
        assert gap - actual_text_height == pytest.approx(0.1944)


@pytest.mark.parametrize("anchor, fits", (
    (drawing.STOCK_KEEP["SupplierNominalEyeOD"], True),
    ((0.200, 0.252), False),
))
def test_settled_layout_checks_complete_native_eye_rows_not_only_qualifier_box(
    stock_source_scene, monkeypatch, anchor, fits,
):
    scene = stock_source_scene
    capture = _stock_capture(scene)
    scene.stock.Position = (0.150, 0.2337375)
    contracts, notes = _stock_layout_scene(scene, monkeypatch)
    annotation = SimpleNamespace(
        OwnerType=0, Owner=scene.stock, Visible=1, IsDangling=lambda: False,
    )
    display = _SupplierCalloutDisplay(
        GetDimension2=lambda _index: scene.dimensions["SupplierNominalEyeOD"],
        GetAnnotation=lambda: annotation, GetOverride=lambda: False,
        ShowDimensionValue=True, GetNext5=lambda: None,
    )
    scene.stock.GetFirstDisplayDimension6 = lambda: display
    rows = _translated_eye_rows_mm(anchor)
    geometry = {
        "texts": [
            {
                "t": text, "pos": (box[0] / 1000.0, box[1] / 1000.0, 0.0002),
                "w": (box[2] - box[0]) / 1000.0, "h": (box[3] - box[1]) / 1000.0,
                "ang": 0.0, "ref": 1,
            }
            for text, box in rows
        ],
    }
    monkeypatch.setattr(purchased_drawing, "annotation_display", lambda *_args: (geometry, ()))
    if fits:
        drawing._verify_supplier_layout(scene.adapter, contracts, notes, scene.source, capture)
    else:
        # The qualifier is still below the cell top; only the complete row set,
        # including its numerator, exposes the real overflow.
        qualifier = dict(rows)["NOMINAL EYE ENVELOPE"]
        assert qualifier[3] < 257.7
        with pytest.raises(RuntimeError, match="supplier dimension leaves its cell"):
            drawing._verify_supplier_layout(scene.adapter, contracts, notes, scene.source, capture)


@pytest.mark.parametrize("anchor, clears", (
    (drawing.STOCK_KEEP["SupplierNominalEyeOD"], True),
    ((0.255, 0.250), False),  # Over the wire numeral/fraction, despite clearing its circle.
    ((0.140, 0.267), False),  # Into the actual stock header, not merely the sheet border.
))
def test_complete_eye_native_rows_clear_actual_header_and_entire_wire_callout(anchor, clears):
    rows = _translated_eye_rows_mm(anchor)
    # Original same-attempt native note extent, including its full title row.
    header = (15.7412, 258.3656, 133.4536, 263.1313)
    # Every original SupplierNominalWire text fragment: complete fractional
    # value, diameter symbol, units, parentheses and the full qualifier row.
    wire_rows = (
        (243.7712, 235.2722, 245.4920, 238.7722),
        (245.4920, 235.2187, 250.7704, 238.7187),
        (253.0892, 237.8294, 255.6753, 241.3294),
        (251.7962, 233.2011, 256.9684, 236.7011),
        (257.9941, 235.2722, 266.2288, 238.7722),
        (227.7340, 227.6449, 282.2659, 231.1449),
    )
    # All four native wire-callout line fragments, including its fraction bar
    # and whole shoulder. Pad by half the actual 0.13 mm PDF dimension stroke.
    wire_lines = (
        (251.2833 - 0.065, 238.1371 - 0.065, 257.4812 + 0.065, 238.1371 + 0.065),
        (214.4558 - 0.065, 227.6449 - 0.065, 226.1465 + 0.065, 232.0562 + 0.065),
        (205.5442 - 0.065, 232.0562 - 0.065, 214.4558 + 0.065, 235.4188 + 0.065),
        (226.1465 - 0.065, 227.6449 - 0.065, 282.2660 + 0.065, 227.6449 + 0.065),
    )
    # Enclose the existing native arrowhead conservatively around its actual
    # tip by its 3.556 mm length plus half its 0.762 mm width and half stroke.
    # This proves clearance without guessing the new eye leader's routing.
    reach = 3.556 + 0.762 / 2.0 + 0.065
    wire_arrow = (214.4558 - reach, 232.0562 - reach, 214.4558 + reach, 232.0562 + reach)
    neighbors = (header, *wire_rows, *wire_lines, wire_arrow)
    assert all(_boxes_clear(box, neighbor, 3.5) for _text, box in rows for neighbor in neighbors) is clears
    if clears:
        label = dict(rows)["NOMINAL EYE ENVELOPE"]
        assert label[0] - header[2] == pytest.approx(38.8138)
        assert label[1] - wire_rows[-1][3] == pytest.approx(11.5)

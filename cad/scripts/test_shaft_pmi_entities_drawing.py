"""Two shaft prints bind typed PMI to feature-owned topology, not sheet picks."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_common as drawing
import _drawing_entities as entities
import _part_pmi as part_pmi
import draw_fulcrum_shaft
import draw_pivot_shaft
from _gtol_spec import CylinderFace, GeometricControl, PartDatum, PlanarFace
from test_native_annotation_placement_drawing import native_context


@pytest.fixture(autouse=True)
def direct_bindings(monkeypatch):
    for module in (drawing, entities, part_pmi):
        monkeypatch.setattr(module, "_early_bound", lambda value, _interface: value)


def cylinder(diameter=6.35, half_length=91.0):
    radius = diameter / 2000
    surface = SimpleNamespace(Identity=4002, CylinderParams=(0, 0, 0, 0, 0, 1, radius))
    return SimpleNamespace(
        GetSurface=lambda: surface,
        GetBox=lambda: (
            -radius,
            -radius,
            -half_length / 1000,
            radius,
            radius,
            half_length / 1000,
        ),
    )


def plane(sign, station):
    surface = SimpleNamespace(
        Identity=4001, PlaneParams=(0, 0, sign, 0, 0, station / 1000)
    )
    return SimpleNamespace(
        GetSurface=lambda: surface,
        FaceInSurfaceSense=lambda: False,
        GetBox=lambda: (-0.004, -0.004, station / 1000, 0.004, 0.004, station / 1000),
    )


def rim(diameter, station, adjacent):
    curve = SimpleNamespace(
        IsCircle=lambda: True,
        IsLine=lambda: False,
        CircleParams=(0, 0, station / 1000, 0, 0, 1, diameter / 2000),
    )
    return SimpleNamespace(
        GetCurve=lambda: curve, GetTwoAdjacentFaces2=lambda: adjacent
    )


def native_annotation(view, entity, entity_type=2):
    annotation = SimpleNamespace(
        Owner=view,
        OwnerType=0,
        name="unnamed",
        GetAttachedEntities3=lambda: (entity,),
        GetAttachedEntityTypes=lambda: (entity_type,),
        GetAttachedEntityCount3=lambda: 1,
        GetPosition=lambda: (0.1, 0.2, 0),
    )

    def set_name(name):
        annotation.name = name
        return True

    annotation.SetName = set_name
    annotation.GetName = lambda: annotation.name
    return annotation


def projection(monkeypatch, *, face_spec=None, entity=None, attachment_type="FACE"):
    face_spec = face_spec or CylinderFace(6.35)
    entity = entity or cylinder()
    view = SimpleNamespace(GetName2=lambda: "Front")
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    datum = PartDatum("A", face_spec)
    control = GeometricControl("form", "cylindricity", ".01", face_spec)
    native_type = {"FACE": 2, "EDGE": 1}[attachment_type]
    annotations = [native_annotation(view, entity, native_type) for _ in range(2)]
    monkeypatch.setattr(
        drawing,
        "add_datum_feature",
        Mock(
            return_value=SimpleNamespace(
                GetAnnotation=lambda: annotations[0],
            )
        ),
    )
    monkeypatch.setattr(
        drawing,
        "add_feature_control_frame",
        Mock(
            return_value=SimpleNamespace(
                GetAnnotation=lambda: annotations[1],
                GetFrame=lambda _index: SimpleNamespace(
                    GetSymbolXml=lambda: control.frame_xml
                ),
            )
        ),
    )
    placement = drawing.PmiDrawingPlacement(
        view=view,
        entity=entity,
        attachment_type=attachment_type,
        position=(0.1, 0.2),
    )

    def run():
        return drawing.project_part_pmi(
            adapter,
            placements={datum.key: placement, control.key: placement},
            datums=(datum,),
            controls=(control,),
            label="shaft",
        )

    return run, annotations, adapter, entity, view


def test_projection_retains_typed_spec_and_exact_explicit_entities(monkeypatch):
    run, annotations, _, entity, _ = projection(monkeypatch)
    assert list(run().values()) == annotations
    assert drawing.add_datum_feature.call_args.kwargs["entity"] is entity
    assert drawing.add_feature_control_frame.call_args.kwargs["entity"] is entity
    assert drawing.add_feature_control_frame.call_args.kwargs["tolerance"] == ".01"


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "failure",
    [
        "same_diameter_other_face",
        "null",
        "count",
        "types",
        "wrong_view",
        "same_named_view",
        "part_owner",
        "unknown_identity",
    ],
)
def test_explicit_pmi_rejects_substituted_attachment_or_owner(
    monkeypatch, index, failure
):
    run, annotations, adapter, _, _ = projection(monkeypatch)
    annotation = annotations[index]
    if failure == "same_diameter_other_face":
        annotation.GetAttachedEntities3 = lambda: (cylinder(),)
    elif failure == "null":
        annotation.GetAttachedEntities3 = lambda: (None,)
    elif failure == "count":
        annotation.GetAttachedEntityCount3 = lambda: 2
    elif failure == "types":
        annotation.GetAttachedEntityTypes = lambda: (1,)
    elif failure in {"wrong_view", "same_named_view"}:
        annotation.Owner = SimpleNamespace(
            GetName2=lambda: "Front" if failure == "same_named_view" else "Right"
        )
    elif failure == "part_owner":
        annotation.OwnerType = 3
    else:
        adapter.swApp.IsSame = lambda *_args: -1
    with pytest.raises(RuntimeError, match="attachment|owner|view"):
        run()


@pytest.mark.parametrize("attachment_type", ["FACE", "EDGE"])
def test_pmi_wrong_end_rejected_before_insertion(monkeypatch, attachment_type):
    wrong = plane(-1, -91)
    entity = wrong if attachment_type == "FACE" else rim(6.35, -91, (wrong, cylinder()))
    run, *_ = projection(
        monkeypatch,
        face_spec=PlanarFace((0, 0, 1), 91),
        entity=entity,
        attachment_type=attachment_type,
    )
    with pytest.raises(RuntimeError, match="controlled.*face"):
        run()
    drawing.add_datum_feature.assert_not_called()
    drawing.add_feature_control_frame.assert_not_called()


def test_pmi_boundary_must_touch_controlled_face(monkeypatch):
    edge = rim(6.35, -91, (plane(-1, -91), cylinder()))
    run, *_ = projection(monkeypatch, entity=edge, attachment_type="EDGE")
    assert len(run()) == 2


def test_final_pmi_bank_detects_earlier_datum_changed_by_later_insertion(monkeypatch):
    run, annotations, *_ = projection(monkeypatch)
    gtol = drawing.add_feature_control_frame.return_value

    def insert(*_args, **_kwargs):
        annotations[0].GetAttachedEntities3 = lambda: (cylinder(),)
        return gtol

    drawing.add_feature_control_frame.side_effect = insert
    with pytest.raises(RuntimeError, match="datum:A.*attachment changed"):
        run()


@pytest.mark.parametrize("failure", ["none", "other_face", "other_view", "wrong_type"])
def test_explicit_surface_finish_checks_attachment_after_rebuild(monkeypatch, failure):
    adapter, view, entity, annotation = native_context(monkeypatch)
    annotation.Owner = view
    annotation.OwnerType = 0
    annotation.GetAttachedEntityTypes.return_value = (1,)

    def rebuild():
        if failure == "other_face":
            annotation.GetAttachedEntities3.return_value = (object(),)
        if failure == "other_view":
            annotation.Owner = object()
        if failure == "wrong_type":
            annotation.GetAttachedEntityTypes.return_value = (2,)
        return True

    adapter.currentModel.EditRebuild3.side_effect = rebuild

    def insert():
        return drawing.add_surface_finish(
            adapter,
            view,
            entity=entity,
            symbol_xy=(0.12, 0.18),
            roughness_ra="1.6",
            label="shaft finish",
        )

    if failure == "none":
        insert()
        annotation.SetPosition2.assert_called_once_with(0.12, 0.18, 0.0)
        view.SelectEntity.assert_called_once_with(entity, False)
        adapter.currentModel.Extension.SelectByID2.assert_not_called()
        return
    with pytest.raises(RuntimeError, match="attachment|view"):
        insert()


def shaft_model(recipe):
    half = recipe.SHAFT_LENGTH / 2
    bearing = cylinder(recipe.SHAFT_DIA, half)
    minus, plus = plane(-1, -half), plane(1, half)
    front = rim(recipe.SHAFT_DIA, -half, (bearing, minus))
    back = rim(recipe.SHAFT_DIA, half, (bearing, plus))
    bearing.GetEdges = Mock(return_value=(front, back))
    minus.GetEdges = Mock(return_value=(front,))
    plus.GetEdges = Mock(return_value=(back,))
    feature = SimpleNamespace(GetFaces=Mock(return_value=(bearing, minus, plus)))
    model = SimpleNamespace(FeatureByName=Mock(return_value=feature))
    return model, feature, bearing, front, back


@pytest.mark.parametrize("recipe", [draw_fulcrum_shaft, draw_pivot_shaft])
def test_shaft_roles_are_exact_feature_boundaries_and_spec_faces(recipe):
    model, feature, bearing, front, back = shaft_model(recipe)
    result = entities.ModelEntities(model).resolve(recipe.ENTITY_ROLES)
    assert result["datum:A"] is front
    assert result["plus_z_end_perpendicularity"] is back
    assert result["minus_z_end_perpendicularity"] is front
    expected_bearing = front if recipe is draw_fulcrum_shaft else bearing
    assert result["bearing_cylindricity"] is expected_bearing
    assert result["bearing_finish"] is expected_bearing
    model.FeatureByName.assert_called_once_with("Shaft")
    feature.GetFaces.assert_called_once_with()
    for row in (*recipe.PART_DATUMS, *recipe.GEOMETRIC_CONTROLS):
        role = recipe.ENTITY_ROLES[row.key]
        controlled = role.face if isinstance(role, entities.FaceBoundary) else role
        assert controlled.feature_name == "Shaft"
        assert controlled.face == row.face


@pytest.mark.parametrize(
    "failure",
    [
        "missing_feature",
        "missing_face",
        "wrong_diameter",
        "duplicate_face",
        "wrong_end",
        "duplicate_rim",
    ],
)
def test_shaft_roles_fail_without_global_or_nearest_fallback(failure):
    recipe = draw_fulcrum_shaft
    model, feature, bearing, front, back = shaft_model(recipe)
    if failure == "missing_feature":
        model.FeatureByName.return_value = None
    elif failure == "missing_face":
        feature.GetFaces.return_value = ()
    elif failure == "wrong_diameter":
        feature.GetFaces.return_value = (cylinder(7),)
    elif failure == "duplicate_face":
        feature.GetFaces.return_value = (
            *feature.GetFaces.return_value,
            cylinder(recipe.SHAFT_DIA, recipe.SHAFT_LENGTH / 2),
        )
    elif failure == "wrong_end":
        bearing.GetEdges.return_value = (back,)
    else:
        bearing.GetEdges.return_value = (front, front, back)
    with pytest.raises(RuntimeError, match="missing|matched"):
        entities.ModelEntities(model).resolve(recipe.ENTITY_ROLES)


@pytest.mark.parametrize("recipe", [draw_fulcrum_shaft, draw_pivot_shaft])
def test_two_shaft_attachment_calls_use_entities_and_keep_display_seeds(recipe):
    tree = ast.parse(Path(recipe.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"PmiDrawingPlacement", "add_surface_finish"}
    ]
    assert len(calls) == 5
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        assert "entity" in keywords
        assert not keywords & {"attachment_xy", "edge_xy", "edge_entity"}
        assert (
            "position" if call.func.id == "PmiDrawingPlacement" else "symbol_xy"
        ) in keywords
    projection_call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "project_part_pmi"
    )
    placements = next(
        kw.value for kw in projection_call.keywords if kw.arg == "placements"
    )
    for key, placement in zip(placements.keys, placements.values, strict=True):
        selected = next(kw.value for kw in placement.keywords if kw.arg == "entity")
        assert isinstance(selected, ast.Subscript)
        assert selected.value.id == "entities"
        assert selected.slice.value == key.value


def test_same_diameter_faces_outside_shaft_feature_are_never_candidates():
    model, feature, _, front, _ = shaft_model(draw_fulcrum_shaft)
    unrelated = SimpleNamespace(GetFaces=Mock(return_value=(cylinder(),)))
    model.FeatureByName.side_effect = lambda name: (
        feature if name == "Shaft" else unrelated
    )
    model.GetBodies2 = Mock(
        side_effect=AssertionError("body-wide fallback is forbidden")
    )
    result = entities.ModelEntities(model).resolve(draw_fulcrum_shaft.ENTITY_ROLES)
    assert result["datum:A"] is front
    model.GetBodies2.assert_not_called()
    unrelated.GetFaces.assert_not_called()

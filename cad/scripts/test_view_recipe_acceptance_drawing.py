"""VIEW inventory/identity/cold guards; no native seat or production writes."""

import ast
from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _recipe_view_entity_acceptance as observer
from diagnostics import _recipe_acceptance_targets as targets
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics._recipe_view_roles import VIEW_ROLES, ViewRole, ViewResolver


@pytest.fixture
def bank(monkeypatch):
    monkeypatch.setattr(observer, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(observer.drawing, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(
        observer.attachments, "geometry", lambda *_: ("line", ((0, 0, 0), (0, 0, 0.01)))
    )
    entity = object()
    view = NS(
        GetName2=lambda: "Drawing View1",
        GetOrientationName=lambda: "*Front",
        entity=entity,
    )
    annotations = {}
    view.GetAnnotations = lambda: tuple(annotations.values())
    manager = NS(
        GetSelectedObjectCount2=lambda _: 1,
        GetSelectedObjectType3=lambda *_: 1,
        GetSelectedObject6=lambda *_: view.entity,
    )
    model = NS(
        SelectionManager=manager,
        GetCurrentSheet=lambda: NS(GetProperties2=lambda: (0, 0, 1, 1, 0, 0.4, 0.3, 0)),
    )
    app = NS(IsSame=lambda left, right: int(left is right))
    adapter = NS(swApp=app, currentModel=model)
    module = NS(
        BORE_DIA=6,
        visible_circle_edge=lambda adapter, selected_view, diameter: (
            selected_view.entity
        ),
    )
    originals = {}

    def selected(adapter, view, **kwargs):
        # Mirrors legacy edge_entity helper: return the argument, even if the
        # actual manager selected another handle. The observer must catch it.
        result = kwargs.get("entity")
        return result if result is not None else kwargs.get("edge_entity")

    monkeypatch.setattr(observer.drawing, "_select_annotation_entity", selected)
    for name, annotation_kind in (
        ("add_datum_feature", 2),
        ("add_feature_control_frame", 5),
        ("add_surface_finish", 7),
    ):

        def original(adapter, selected_view, annotation_kind=annotation_kind, **kwargs):
            observer.drawing._select_annotation_entity(
                adapter,
                selected_view,
                label=kwargs["label"],
                entity_type=kwargs.get("entity_type", "EDGE"),
                entity=kwargs.get("entity"),
                edge_entity=kwargs.get("edge_entity"),
            )
            label = kwargs["label"]
            entity_kind = {"EDGE": 1, "FACE": 2, "SILHOUETTE": 46}[
                kwargs.get("entity_type", "EDGE")
            ]
            annotation = NS(
                GetName=lambda: label,
                GetType=lambda: annotation_kind,
                OwnerType=0,
                Owner=selected_view,
                GetAttachedEntityCount3=lambda: 1,
                GetAttachedEntityTypes=lambda: (entity_kind,),
                GetAttachedEntities3=lambda: (selected_view.entity,),
                Visible=1,
                IsDangling=lambda: False,
                GetPosition=lambda: (0.1, 0.2, 0),
            )
            annotations[label] = annotation
            return NS(GetAnnotation=lambda: annotation)

        originals[name] = original
        monkeypatch.setattr(observer.drawing, name, original)
        setattr(module, name, original)
    monkeypatch.setattr(observer.attachments, "views", lambda _: {"Sheet/View": view})
    manifest = NS(
        entity_labels={},
        view_roles={"finish": ViewRole("*Front", 7, "EDGE", ViewResolver.BORE)},
    )
    witness = observer.ViewEntityAcceptance(module, manifest)
    return NS(
        adapter=adapter,
        entity=entity,
        view=view,
        manager=manager,
        annotations=annotations,
        module=module,
        manifest=manifest,
        witness=witness,
        originals=originals,
        selected=selected,
    )


def build(bank, *, argument="entity"):
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter, bank.view, label="finish", **{argument: bank.entity}
        )


def test_direct_and_legacy_paths_observe_actual_selection_and_complete_bank(bank):
    build(bank, argument="edge_entity")
    result = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    assert set(result["explicit"]) == {"finish"}
    assert result["coordinate_picked"] == {}
    assert [row["stage"] for row in bank.witness.context_report["stages"]] == [
        "selected",
        "inserted",
        "built",
    ]
    assert all(row["seconds"] >= 0 for row in bank.witness.context_report["stages"])
    assert bank.module.add_surface_finish is bank.originals["add_surface_finish"]
    assert observer.drawing._select_annotation_entity is bank.selected


@pytest.mark.parametrize(
    "fault",
    [
        "actual_selection",
        "selected_kind",
        "count",
        "bool_kind",
        "null",
        "wrong_orientation",
        "unknown_identity",
    ],
)
def test_original_argument_does_not_certify_manager_selection(bank, fault):
    if fault == "actual_selection":
        bank.manager.GetSelectedObject6 = lambda *_: object()
    if fault == "selected_kind":
        bank.manager.GetSelectedObjectType3 = lambda *_: 2
    if fault == "bool_kind":
        bank.manager.GetSelectedObjectType3 = lambda *_: True
    if fault == "count":
        bank.manager.GetSelectedObjectCount2 = lambda _: 2
    if fault == "null":
        bank.manager.GetSelectedObject6 = lambda *_: None
    if fault == "wrong_orientation":
        bank.view.GetOrientationName = lambda: "*Right"
    if fault == "unknown_identity":
        bank.adapter.swApp.IsSame = lambda *_: -1
    with pytest.raises(RuntimeError):
        build(bank, argument="edge_entity")
    assert bank.witness.recorded == {}
    assert "error" in bank.witness.context_report["stages"][-1]
    assert observer.drawing._select_annotation_entity is bank.selected
    assert bank.module.add_surface_finish is bank.originals["add_surface_finish"]


@pytest.mark.parametrize(
    "fault",
    [
        "wrong_entity",
        "wrong_view",
        "wrong_kind",
        "missing",
        "replacement",
        "hidden",
        "dangling",
        "off_sheet",
        "bool_count",
        "short_arrays",
    ],
)
def test_later_mutation_rejects_even_equal_geometry(bank, fault):
    build(bank)
    annotation = bank.annotations["finish"]
    if fault == "wrong_entity":
        annotation.GetAttachedEntities3 = lambda: (object(),)
    if fault == "wrong_view":
        annotation.Owner = object()
    if fault == "wrong_kind":
        annotation.GetType = lambda: 5
    if fault == "missing":
        bank.annotations.clear()
    if fault == "replacement":
        bank.annotations["finish"] = NS(**vars(annotation))
    if fault == "hidden":
        annotation.Visible = 3
    if fault == "dangling":
        annotation.IsDangling = lambda: True
    if fault == "off_sheet":
        annotation.GetPosition = lambda: (1, 0.2, 0)
    if fault == "bool_count":
        annotation.GetAttachedEntityCount3 = lambda: True
    if fault == "short_arrays":
        annotation.GetAttachedEntityTypes = lambda: ()
    with pytest.raises(RuntimeError):
        bank.witness.drawing_snapshot(bank.adapter, phase="built")


@pytest.mark.parametrize(
    "fault",
    [None, "wrong_resolved", "missing_resolved", "wrong_owner", "missing_annotation"],
)
def test_cold_re_resolves_view_role_without_using_closed_handles(
    bank, monkeypatch, fault
):
    build(bank)
    built = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    cold_entity = object()
    cold = NS(
        GetName2=lambda: "Drawing View1",
        GetOrientationName=lambda: "*Front",
        entity=cold_entity,
    )
    annotation = NS(**vars(bank.annotations["finish"]))
    annotation.Owner = cold
    annotation.GetAttachedEntities3 = lambda: (cold_entity,)
    cold.GetAnnotations = lambda: (annotation,)
    monkeypatch.setattr(observer.attachments, "views", lambda _: {"Sheet/View": cold})
    bank.view.GetName2 = Mock(side_effect=AssertionError("closed view queried"))
    bank.annotations["finish"].GetName = Mock(
        side_effect=AssertionError("closed annotation queried")
    )
    if fault == "wrong_resolved":
        cold.entity = object()
    if fault == "missing_resolved":
        cold.entity = None
    if fault == "wrong_owner":
        annotation.Owner = object()
    if fault == "missing_annotation":
        cold.GetAnnotations = lambda: ()
    if fault:
        with pytest.raises(RuntimeError):
            bank.witness.drawing_snapshot(bank.adapter, phase="reopened")
        return
    assert bank.witness.drawing_snapshot(bank.adapter, phase="reopened") == built


def test_coordinate_annotation_not_claimed_explicit_or_migrated(bank):
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter, bank.view, label="finish", entity=bank.entity
        )
        bank.module.add_datum_feature(
            bank.adapter, bank.view, label="coordinate datum", edge_xy=(0.1, 0.2)
        )
    result = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    assert set(result["explicit"]) == {"finish"}
    assert (
        result["coordinate_picked"]["coordinate datum"]["origin"]
        == "coordinate_pick_not_migrated"
    )


def silhouette_bank(bank, monkeypatch):
    from test_silhouette_attachment_witness_drawing import fixture

    _, _, entity, *_ = fixture()
    monkeypatch.setattr(observer.silhouette, "_early_bound", lambda obj, _: obj)
    entity.GetView = lambda: bank.view
    bank.entity = bank.view.entity = entity
    bank.manager.GetSelectedObjectType3 = lambda *_: 46
    bank.manifest.view_roles["finish"] = ViewRole(
        "*Front", 7, "SILHOUETTE", ViewResolver.JOURNAL
    )
    bank.module._visible_journal_silhouette = lambda adapter, view: view.entity
    return entity


def test_silhouette_original_selected_attached_and_coordinate_rows_are_separate(
    bank, monkeypatch
):
    silhouette_bank(bank, monkeypatch)
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter,
            bank.view,
            label="finish",
            entity=bank.entity,
            entity_type="SILHOUETTE",
        )
        bank.module.add_feature_control_frame(
            bank.adapter,
            bank.view,
            label="coordinate silhouette",
            edge_xy=(0.1, 0.2),
            entity_type="SILHOUETTE",
        )
    result = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    assert result["explicit"]["finish"]["kind"] == 46
    assert (
        result["coordinate_picked"]["coordinate silhouette"]["origin"]
        == "coordinate_pick_not_migrated"
    )
    assert (
        result["explicit"]["finish"]["geometry"]
        == result["coordinate_picked"]["coordinate silhouette"]["geometry"]
    )
    assert (
        bank.witness.context_report["stages"][0]["silhouette"]["expected"]
        == bank.witness.context_report["stages"][0]["silhouette"]["actual"]
    )


def test_silhouette_face_substitution_after_insertion_rejects_with_raw_evidence(
    bank, monkeypatch
):
    entity = silhouette_bank(bank, monkeypatch)
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter,
            bank.view,
            label="finish",
            entity=entity,
            entity_type="SILHOUETTE",
        )
    face = entity.GetFace()
    alternate = NS(**vars(entity))
    alternate.GetFace = lambda: NS(**vars(face))
    bank.annotations["finish"].GetAttachedEntities3 = lambda: (alternate,)
    # Native silhouette identity itself is positive; exact face identity must
    # still reject this substitute with identical analytic surface parameters.
    bank.adapter.swApp.IsSame = lambda left, right: (
        1 if left is right or (left is entity and right is alternate) else 0
    )
    with pytest.raises(RuntimeError, match="silhouette face"):
        bank.witness.drawing_snapshot(bank.adapter, phase="built")
    row = bank.witness.context_report["stages"][-1]
    assert row["silhouette"]["expected"] == row["silhouette"]["actual"]
    assert "error" in row


@pytest.mark.parametrize(
    "fault", ["same_handle_face_replaced", "same_handle_geometry_changed"]
)
def test_initial_silhouette_witness_survives_later_native_mutation(
    bank, monkeypatch, fault
):
    entity = silhouette_bank(bank, monkeypatch)
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter,
            bank.view,
            label="finish",
            entity=entity,
            entity_type="SILHOUETTE",
        )
    if fault == "same_handle_face_replaced":
        changed_face = NS(**vars(entity.GetFace()))
        entity.GetFace = lambda: changed_face
    if fault == "same_handle_geometry_changed":
        entity.GetEndPoint = lambda: NS(ArrayData=(0.003, 0, 0.10000000000000002))
    with pytest.raises(
        RuntimeError, match=r"silhouette face|geometry changed since selection"
    ):
        bank.witness.drawing_snapshot(bank.adapter, phase="built")
    row = bank.witness.context_report["stages"][-1]
    assert "geometry" in row
    assert "error" in row


def test_cold_silhouette_has_fresh_owner_face_and_geometry(bank, monkeypatch):
    from test_silhouette_attachment_witness_drawing import fixture

    silhouette_bank(bank, monkeypatch)
    with bank.witness.observe(bank.adapter):
        bank.module.add_surface_finish(
            bank.adapter,
            bank.view,
            label="finish",
            entity=bank.entity,
            entity_type="SILHOUETTE",
        )
    built = bank.witness.drawing_snapshot(bank.adapter, phase="built")
    _, _, cold_entity, *_ = fixture()
    cold = NS(
        GetName2=lambda: "Drawing View1",
        GetOrientationName=lambda: "*Front",
        entity=cold_entity,
    )
    cold_entity.GetView = lambda: cold
    annotation = NS(**vars(bank.annotations["finish"]))
    annotation.Owner = cold
    annotation.GetAttachedEntities3 = lambda: (cold_entity,)
    cold.GetAnnotations = lambda: (annotation,)
    monkeypatch.setattr(observer.attachments, "views", lambda _: {"Sheet/View": cold})
    bank.view.GetName2 = Mock(side_effect=AssertionError("closed VIEW read"))
    bank.entity.GetFace = Mock(side_effect=AssertionError("closed face read"))
    assert bank.witness.drawing_snapshot(bank.adapter, phase="reopened") == built


def test_view_observer_rejects_model_contract_before_insertion(bank):
    with pytest.raises(RuntimeError, match="MODEL insertion context"):
        with bank.witness.observe(bank.adapter):
            bank.module.add_surface_finish(
                bank.adapter,
                bank.view,
                label="finish",
                entity=bank.entity,
                entity_context=observer.drawing.AnnotationEntityContext.MODEL,
            )
    assert bank.annotations == {}


def test_explicit_call_cannot_be_silently_omitted_from_manifest(bank):
    with pytest.raises(RuntimeError, match="unmanifested"):
        with bank.witness.observe(bank.adapter):
            bank.module.add_datum_feature(
                bank.adapter, bank.view, label="new datum", entity=bank.entity
            )
    assert observer.drawing._select_annotation_entity is bank.selected


def test_partial_alias_setup_failure_restores_all_wrappers(bank):
    bank.module.add_feature_control_frame = lambda *_: None
    with pytest.raises(RuntimeError, match=r"unexpected.*alias"):
        with bank.witness.observe(bank.adapter):
            raise AssertionError("must fail before entering")
    assert bank.module.add_datum_feature is bank.originals["add_datum_feature"]
    assert observer.drawing.add_surface_finish is bank.originals["add_surface_finish"]
    assert observer.drawing._select_annotation_entity is bank.selected


def test_typed_common_call_is_observed_even_without_recipe_alias(bank):
    del bank.module.add_surface_finish
    with bank.witness.observe(bank.adapter):
        observer.drawing.add_surface_finish(
            bank.adapter, bank.view, label="finish", entity=bank.entity
        )
    bank.witness.require_coverage()


@pytest.mark.parametrize(
    "shape",
    [
        ("circle", (0,) * 6, (0, 1), (0, 0, 0), (0, 0, 0)),
        ("line", ((0, 0), (0, 1))),
        ("face", 4002, (0,) * 6, (0,) * 6, None),
    ],
)
def test_malformed_supported_geometry_shape_rejects(monkeypatch, shape):
    monkeypatch.setattr(observer.attachments, "geometry", lambda *_: shape)
    with pytest.raises(RuntimeError, match="native"):
        observer.geometry(None, None, object(), 2 if shape[0] == "face" else 1)


@pytest.mark.parametrize("target", sorted(VIEW_ROLES))
def test_all_existing_explicit_recipe_calls_are_enrolled(target):
    path = pilot.ROOT / f"cad/scripts/draw_{target}.py"
    tree = ast.parse(path.read_text())
    labels = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords}
        if (
            node.func.id
            in {"add_datum_feature", "add_feature_control_frame", "add_surface_finish"}
            and {"entity", "edge_entity"} & kwargs.keys()
        ):
            labels.add(ast.literal_eval(kwargs["label"]))
        if node.func.id == "project_part_pmi":
            prefix = ast.literal_eval(kwargs["label"])
            placements = kwargs["placements"]
            for key, call in zip(placements.keys, placements.values, strict=True):
                if any(kw.arg in {"entity", "edge_entity"} for kw in call.keywords):
                    labels.add(f"{prefix} {ast.literal_eval(key)}")
    assert labels == VIEW_ROLES[target].keys()
    manifest = targets.TARGETS[target]
    assert manifest.entity_labels == {}
    assert manifest.view_roles == VIEW_ROLES[target]
    assert manifest.dimensions
    assert len(manifest.source_sha256) == 64
    assert pilot.target_order((target,)) == (target,)


def test_complete_explicit_scope_and_default_order():
    assert len(VIEW_ROLES) == 10
    rows = [row for roles in VIEW_ROLES.values() for row in roles.values()]
    assert len(rows) == 21
    assert sum(row.annotation_kind == 7 for row in rows) == 11
    assert sum(row.entity_kind == 46 for row in rows) == 4
    assert pilot.target_order() == ("rocker_arm", "channel_lever")


@pytest.mark.parametrize(
    "values", [[], [(0, object())], [(0, object()), (0, object())]]
)
def test_fresh_crank_end_roles_require_two_distinct_end_stations(values):
    role = VIEW_ROLES["crankshaft"]["crank-end datum face"]
    module = NS(_visible_shaft_end_edges=lambda *_: values)
    with pytest.raises(RuntimeError, match="missing or ambiguous"):
        role.resolve(module, None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "target",
    [
        "alignment_pinion", "crankshaft", "crank_drive_gear", "crank_pinion",
        "cylinder_gear", "rack_pinion", "transgear_feed_pinion", "transgear_pinion",
    ],
)
@pytest.mark.parametrize("mode", ["normal", "title_failure", "source_saved"])
async def test_view_enrollment_reuses_full_owned_pilot_without_model_reverse_mapping(
    tmp_path, monkeypatch, target, mode
):
    from test_benchmark_drawing_recipes import recipe
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources

    source_root, _ = fixture_sources(tmp_path, monkeypatch)
    path = source_root / f"{target.replace('_', '-')}.SLDPRT"
    path.write_bytes(target.encode())
    monkeypatch.setitem(
        pilot.EXPECTED_PART_HASHES, target, pilot.attachments.file_digest(path)
    )
    monkeypatch.setattr(pilot.benchmark, "recipe_source", lambda *_: recipe(path))
    handle = object()
    monkeypatch.setattr(
        pilot,
        "source_dimensions",
        lambda *_: (
            {
                "configuration": "Default",
                "dimensions": {
                    "Dia@Sketch": {"value_system": 0.01, "tolerance_type": 1}
                },
            },
            {"dimension": handle},
        ),
    )
    monkeypatch.setattr(
        pilot, "drawing_witness", lambda *_args, **_kwargs: {"unchanged": "native"}
    )
    monkeypatch.setattr(
        pilot,
        "compare_drawing_reopen",
        lambda *_: {
            "status": "failed" if mode == "title_failure" else "passed",
            "rejected": ["title moved"] if mode == "title_failure" else [],
        },
    )
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    phases = []

    class Witness:
        def __init__(self, module, manifest):
            self.context_report = {"context": "view"}

        @contextmanager
        def observe(self, adapter, source_entities):
            assert source_entities is None
            phases.append("observe")
            yield

        def drawing_snapshot(self, adapter, source_entities, *, phase):
            assert source_entities is None
            phases.append(phase)
            return {"view": "same", "geometry": "same"}

    monkeypatch.setattr(pilot, "ViewEntityAcceptance", Witness)
    monkeypatch.setattr(
        pilot,
        "EntityAcceptance",
        Mock(side_effect=AssertionError("VIEW must not use MODEL")),
    )
    adapter = Adapter("source_drift" if mode == "source_saved" else "normal")
    root = tmp_path / "reports"
    if mode == "normal":
        await pilot.pilot(
            adapter, "candidate", source_root, source_root, root, targets=(target,)
        )
    else:
        with pytest.raises(RuntimeError, match=r"source copy changed|annotation layout"):
            await pilot.pilot(
                adapter, "candidate", source_root, source_root, root, targets=(target,)
            )
    (receipt,) = root.glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    trial = report["trials"][0]
    assert report["sources_before"] == report["sources_after"]
    assert path not in map(Path, adapter.opened)
    assert trial["acceptance_manifest"]["entity_context"] == "view"
    assert "source_entities_before" not in trial
    assert "source_entities_after" not in trial
    assert "source_entities_reopened" not in trial
    if mode == "normal":
        assert phases == ["observe", "built", "reopened"]
        assert trial["explicit_entities_built"] == trial["explicit_entities_reopened"]
    if mode == "title_failure":
        assert phases == ["observe", "built"]
        assert trial["reopen_annotation_comparison"]["rejected"] == ["title moved"]
    if mode == "source_saved":
        assert phases == ["observe"]
        assert report["runtime_final_guard_errors"]

"""Two-shaft enrollment reuses the owned pilot without omitting its witnesses."""

from contextlib import contextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics import _recipe_acceptance_targets as targets
from diagnostics import _recipe_entity_acceptance as entities
from _drawing_entities import CircleEdge, FaceBoundary, FeatureFace
from _gtol_spec import CylinderFace


@pytest.mark.parametrize("target", ["fulcrum_shaft", "pivot_shaft"])
def test_shafts_are_explicit_targets_not_new_defaults(target):
    assert pilot.target_order((target,)) == (target,)
    assert pilot.target_order() == ("rocker_arm", "channel_lever")
    manifest = targets.TARGETS[target]
    assert manifest.source_sha256 == pilot.EXPECTED_PART_HASHES[target]
    assert manifest.dimensions == {"SectionProfile": {"ShaftDia"}, "Shaft": {"Depth"}}
    assert manifest.basic == {}
    assert len(manifest.entity_labels) == 5


@pytest.mark.parametrize("target", ["fulcrum_shaft", "pivot_shaft"])
def test_source_reader_uses_each_shaft_manifest(tmp_path, monkeypatch, target):
    path = tmp_path / f"{target}.SLDPRT"
    model = SimpleNamespace(
        GetType=lambda: 1,
        GetPathName=lambda: str(path),
        ConfigurationManager=SimpleNamespace(
            ActiveConfiguration=SimpleNamespace(Name="Default")
        ),
    )
    monkeypatch.setattr(pilot, "_early_bound", lambda value, _: value)
    reader = Mock(return_value=({"Depth@Shaft": {"value_system": 0.182}}, {}))
    monkeypatch.setattr(pilot, "part_dimensions", reader)
    result, _ = pilot.source_dimensions(model, target, path)
    assert result["configuration"] == "Default"
    assert reader.call_args.kwargs["targets"] is targets.TARGETS[target].dimensions


def test_one_exact_original_may_also_be_its_guard(tmp_path, monkeypatch):
    path = tmp_path / "fulcrum-shaft.SLDPRT"
    path.write_bytes(b"owned test input")
    digest = pilot.attachments.file_digest(path)
    monkeypatch.setattr(pilot, "EXPECTED_PART_HASHES", {"fulcrum_shaft": digest})
    assert pilot.require_sources({"fulcrum_shaft": path}, {"fulcrum_shaft": path}) == {
        str(path): digest
    }


def test_source_and_guard_target_multiplicity_must_match(tmp_path):
    with pytest.raises(ValueError, match="same target"):
        pilot.require_sources({"fulcrum_shaft": tmp_path / "part"}, {})


@pytest.fixture
def entity_bank(monkeypatch):
    monkeypatch.setattr(entities, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(entities.drawing, "_early_bound", lambda value, _: value)
    face = FeatureFace("Shaft", CylinderFace(6.35))
    boundary = FaceBoundary(face, CircleEdge(3.175, (0, 0, -91), (0, 0, 1)))
    roles = {"datum:A": boundary, "bearing_cylindricity": face, "bearing_finish": face}
    manifest = SimpleNamespace(entity_labels={f"label {key}": key for key in roles})
    witness = entities.EntityAcceptance(SimpleNamespace(ENTITY_ROLES=roles), manifest)
    source_entities = {key: object() for key in witness.requests}
    geometry = {id(value): f"geometry {key}" for key, value in source_entities.items()}
    monkeypatch.setattr(
        entities.attachments, "geometry", lambda value, kind: geometry[id(value)]
    )
    resolver = Mock(
        return_value=SimpleNamespace(resolve=lambda requests: dict(source_entities))
    )
    monkeypatch.setattr(entities, "ModelEntities", resolver)
    view = SimpleNamespace(GetName2=lambda: "Front")
    annotations = {}
    for role, entity in ((role, source_entities[role]) for role in roles):
        kind = {"datum:A": 2, "bearing_cylindricity": 5, "bearing_finish": 7}[role]
        annotations[role] = SimpleNamespace(
            GetName=lambda role=role: role,
            GetType=lambda kind=kind: kind,
            GetAttachedEntityCount3=lambda: 1,
            GetAttachedEntities3=lambda entity=entity: (entity,),
            GetAttachedEntityTypes=lambda role=role: (witness.kinds[role][1],),
            OwnerType=0,
            Owner=view,
            Visible=1,
            IsDangling=lambda: False,
            GetPosition=lambda: (0.1, 0.2, 0.0),
        )
    view.GetAnnotations = lambda: tuple(annotations.values())
    model = SimpleNamespace(
        GetCurrentSheet=lambda: SimpleNamespace(
            GetProperties2=lambda: (0, 0, 1, 1, 0, 0.4, 0.3, 0)
        )
    )
    adapter = SimpleNamespace(
        currentModel=model, swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b))
    )
    monkeypatch.setattr(entities.attachments, "views", lambda _: {"Sheet/Front": view})
    return SimpleNamespace(
        witness=witness,
        source=source_entities,
        geometry=geometry,
        adapter=adapter,
        view=view,
        annotations=annotations,
        resolver=resolver,
    )


def record_bank(bank):
    with bank.witness.observe(bank.adapter, bank.source):
        for role, annotation in bank.annotations.items():
            entities.drawing._validate_explicit_annotation_attachment(
                bank.adapter,
                annotation,
                bank.view,
                bank.source[role],
                entity_type=bank.witness.kinds[role][0],
                label=f"label {role}",
            )


def test_observer_calls_real_validator_then_rechecks_complete_bank(entity_bank):
    bank = entity_bank
    original = entities.drawing._validate_explicit_annotation_attachment
    before, handles = bank.witness.source_snapshot(object())
    record_bank(bank)
    assert entities.drawing._validate_explicit_annotation_attachment is original
    built = bank.witness.drawing_snapshot(bank.adapter, handles, phase="built")
    after, _ = bank.witness.source_snapshot(object())
    assert before == after
    assert bank.resolver.call_count == 2
    assert len(built) == 3
    assert built["bearing_finish"]["entity_kind"] == 2


@pytest.mark.parametrize(
    "fault", ["substitution", "wrong_owner", "unknown_identity", "missing_kind"]
)
def test_real_insertion_guard_is_not_bypassed(entity_bank, fault):
    bank = entity_bank
    annotation = bank.annotations["datum:A"]
    if fault == "substitution":
        annotation.GetAttachedEntities3 = lambda: (object(),)
    if fault == "wrong_owner":
        annotation.Owner = SimpleNamespace(GetName2=lambda: "Front")
    if fault == "unknown_identity":
        bank.adapter.swApp.IsSame = lambda *_: -1
    if fault == "missing_kind":
        annotation.GetAttachedEntityTypes = lambda: ()
    original = entities.drawing._validate_explicit_annotation_attachment
    with pytest.raises(RuntimeError):
        record_bank(bank)
    assert entities.drawing._validate_explicit_annotation_attachment is original


@pytest.mark.parametrize(
    "fault", ["missing", "replacement", "wrong_kind", "wrong_face", "wrong_view"]
)
def test_later_recipe_mutation_cannot_replace_initial_exact_guard(entity_bank, fault):
    bank = entity_bank
    record_bank(bank)
    original = bank.annotations["bearing_finish"]
    if fault == "missing":
        del bank.annotations["bearing_finish"]
    if fault == "replacement":
        bank.annotations["bearing_finish"] = SimpleNamespace(**vars(original))
    if fault == "wrong_kind":
        original.GetType = lambda: 2
    if fault == "wrong_face":
        original.GetAttachedEntities3 = lambda: (object(),)
    if fault == "wrong_view":
        original.Owner = object()
    with pytest.raises(RuntimeError):
        bank.witness.drawing_snapshot(bank.adapter, bank.source, phase="built")


def test_missing_observer_row_is_not_hidden_by_unrelated_geometry(entity_bank):
    bank = entity_bank
    record_bank(bank)
    del bank.witness.recorded["bearing_finish"]
    with pytest.raises(RuntimeError, match="coverage"):
        bank.witness.drawing_snapshot(bank.adapter, bank.source, phase="built")


@pytest.mark.parametrize("fault", ["hidden", "dangling", "off_sheet"])
def test_final_bank_checks_earlier_datum_after_finish_insertion(entity_bank, fault):
    bank = entity_bank
    record_bank(bank)
    datum = bank.annotations["datum:A"]
    if fault == "hidden":
        datum.Visible = 3
    if fault == "dangling":
        datum.IsDangling = lambda: True
    if fault == "off_sheet":
        datum.GetPosition = lambda: (0.5, 0.2, 0.0)
    with pytest.raises(RuntimeError, match="native PMI"):
        bank.witness.drawing_snapshot(bank.adapter, bank.source, phase="built")


@pytest.mark.parametrize("fault", [None, "wrong_entity", "wrong_view", "missing"])
def test_cold_witness_resolves_new_native_entities_without_old_handle_calls(
    entity_bank, monkeypatch, fault
):
    bank = entity_bank
    record_bank(bank)
    built = bank.witness.drawing_snapshot(bank.adapter, bank.source, phase="built")
    cold_view = SimpleNamespace(GetName2=lambda: "Front")
    cold_entities = {key: object() for key in bank.source}
    for key, value in cold_entities.items():
        bank.geometry[id(value)] = bank.geometry[id(bank.source[key])]
    cold_annotations = {}
    for role, original in bank.annotations.items():
        row = SimpleNamespace(**vars(original))
        row.Owner = cold_view
        row.GetAttachedEntities3 = lambda role=role: (cold_entities[role],)
        cold_annotations[role] = row
    if fault == "wrong_entity":
        cold_annotations["bearing_finish"].GetAttachedEntities3 = lambda: (object(),)
    if fault == "wrong_view":
        cold_annotations["bearing_finish"].Owner = object()
    if fault == "missing":
        del cold_annotations["bearing_finish"]
    cold_view.GetAnnotations = lambda: tuple(cold_annotations.values())
    monkeypatch.setattr(
        entities.attachments, "views", lambda _: {"Sheet/Front": cold_view}
    )
    bank.view.GetName2 = Mock(
        side_effect=AssertionError("closed view must not be queried")
    )
    if fault:
        with pytest.raises(RuntimeError):
            bank.witness.drawing_snapshot(bank.adapter, cold_entities, phase="reopened")
        return
    assert (
        bank.witness.drawing_snapshot(bank.adapter, cold_entities, phase="reopened")
        == built
    )


@pytest.mark.parametrize("fault", ["extra_role", "unsupported_selector"])
def test_manifest_does_not_assume_unrecognized_geometry(entity_bank, fault):
    roles = dict(entity_bank.witness.roles)
    if fault == "extra_role":
        roles["unreviewed"] = object()
    if fault == "unsupported_selector":
        roles["datum:A"] = object()
    with pytest.raises((RuntimeError, ValueError)):
        entities.EntityAcceptance(
            SimpleNamespace(ENTITY_ROLES=roles),
            SimpleNamespace(entity_labels=entity_bank.witness.labels),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["fulcrum_shaft", "pivot_shaft"])
@pytest.mark.parametrize("mode", ["normal", "title_failure", "source_saved"])
async def test_real_pilot_enrollment_keeps_owned_copy_and_cold_gates(
    tmp_path, monkeypatch, target, mode
):
    from test_benchmark_drawing_recipes import recipe
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources

    source_root, _ = fixture_sources(tmp_path, monkeypatch)
    source = source_root / f"{target.replace('_', '-')}.SLDPRT"
    source.write_bytes(target.encode())
    monkeypatch.setitem(
        pilot.EXPECTED_PART_HASHES, target, pilot.attachments.file_digest(source)
    )
    monkeypatch.setattr(
        pilot.benchmark,
        "recipe_source",
        lambda *_: recipe(Path("unopened/original.SLDPRT")),
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: {"helper": "same"})
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: {"actual": "same"})
    handle = object()
    monkeypatch.setattr(
        pilot,
        "source_dimensions",
        lambda *_: (
            {
                "configuration": "Default",
                "dimensions": {
                    "Depth@Shaft": {"value_system": 0.182, "tolerance_type": 2}
                },
            },
            {"dimension": handle},
        ),
    )
    monkeypatch.setattr(
        pilot, "drawing_witness", lambda *_args, **_kwargs: {"same": "native"}
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
            assert manifest is targets.TARGETS[target]

        def source_snapshot(self, model):
            phases.append("source")
            return {"face": "same"}, {"entity": handle}

        @contextmanager
        def observe(self, adapter, entities):
            phases.append("observe")
            yield
            phases.append("observed")

        def drawing_snapshot(self, adapter, entities, *, phase):
            phases.append(phase)
            return {"view": "same", "geometry": "same"}

    monkeypatch.setattr(pilot, "EntityAcceptance", Witness)
    adapter = Adapter("source_drift" if mode == "source_saved" else "normal")
    root = tmp_path / "reports"
    if mode == "normal":
        await pilot.pilot(
            adapter, "candidate", source_root, source_root, root, targets=(target,)
        )
    else:
        with pytest.raises(RuntimeError, match="source copy changed|annotation layout"):
            await pilot.pilot(
                adapter, "candidate", source_root, source_root, root, targets=(target,)
            )
    (receipt,) = root.glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    assert report["order"] == [target]
    assert report["protected_targets"] == [*pilot.ORDER, target]
    assert len(report["sources_before"]) == len(report["sources_after"]) == 3
    assert report["sources_before"] == report["sources_after"]
    assert source not in map(Path, adapter.opened)
    trial = report["trials"][0]
    assert len(trial["acceptance_manifest"]["code"]) == 2
    assert len(trial["acceptance_manifest"]["explicit_labels"]) == 5
    assert trial["recipe_seconds"] >= 0
    assert len(adapter.drawn) == 1
    if mode == "normal":
        assert report["status"] == "passed"
        assert phases == [
            "source",
            "observe",
            "observed",
            "source",
            "built",
            "source",
            "reopened",
        ]
        assert trial["explicit_entities_built"] == trial["explicit_entities_reopened"]
    if mode == "title_failure":
        assert report["status"] == "failed"
        assert trial["reopen_annotation_comparison"]["rejected"] == ["title moved"]
        assert "reopened" not in phases
    if mode == "source_saved":
        assert report["status"] == "failed"
        assert report["runtime_final_guard_errors"]
        assert "built" not in phases


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["helper", "adapter", "source"])
async def test_final_guards_capture_drift_without_masking_primary_recipe_failure(
    tmp_path, monkeypatch, drift
):
    from test_benchmark_drawing_recipes import recipe
    from test_datum_policy_recipes_drawing import Adapter, fixture_sources

    source_root, guard_root = fixture_sources(tmp_path, monkeypatch)
    monkeypatch.setattr(
        pilot.benchmark, "recipe_source", lambda *_: recipe(Path("original.SLDPRT"))
    )
    monkeypatch.setattr(pilot.benchmark, "revision", lambda _: "frozen")
    counts = {"helper": 0, "adapter": 0}

    def fingerprint(family):
        counts[family] += 1
        return {family: "changed" if drift == family and counts[family] > 1 else "same"}

    monkeypatch.setattr(pilot, "helper_fingerprints", lambda: fingerprint("helper"))
    monkeypatch.setattr(pilot, "adapter_fingerprints", lambda: fingerprint("adapter"))
    monkeypatch.setattr(
        pilot, "source_dimensions", lambda *_: ({"configuration": "Default"}, {})
    )
    monkeypatch.setattr(pilot, "retain_failed_drawing", Mock())
    adapter = Adapter("build_failure")
    original_draw = adapter.draw

    async def draw(*args):
        if drift == "source":
            (guard_root / "rocker-arm.SLDPRT").write_bytes(b"test fixture changed")
        return await original_draw(*args)

    adapter.draw = draw
    with pytest.raises(RuntimeError, match="real recipe gate failed") as caught:
        await pilot.pilot(
            adapter, "candidate", source_root, guard_root, tmp_path / "reports"
        )
    (receipt,) = (tmp_path / "reports").glob("*/pilot.json")
    report = json.loads(receipt.read_text())
    assert report["error"] == "RuntimeError('real recipe gate failed')"
    assert report["status"] == "failed"
    assert len(report["runtime_final_guard_errors"]) == 1
    assert "additional final guard failures" in caught.value.__notes__[0]
    assert counts == {"helper": 2, "adapter": 2}

"""Pure production/partial lifecycle input and annotation-state contracts."""

import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def probe(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "path", sys.path.copy())
    spec = importlib.util.spec_from_file_location(
        "vm2_lifecycle", Path(__file__).with_name("probe_vm2_datum_lifecycle.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path.resolve())
    monkeypatch.setitem(sys.modules, "_common", SimpleNamespace(_early_bound=lambda value, _kind: value))
    monkeypatch.setitem(sys.modules, "pinion_lift_rod_spec", SimpleNamespace(ROD_DIA=6.35, __file__=__file__))
    monkeypatch.setitem(sys.modules, "rack_pinion_spec", SimpleNamespace(BORE_DIA=5.0, __file__=__file__))
    for stem in ("pinion-lift-rod", "rack-pinion"):
        for folder, suffix in (("slddrw", "SLDDRW"), ("sldprt", "SLDPRT")):
            path = module.ROOT / f"cad/out/{folder}/{stem}.{suffix}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"offline input")
    return module


def inputs(probe, path, **overrides):
    options = {"mode": "production", "ink_refresh": "cold", "rack_dimension_location": "original"}
    options.update(overrides)
    return probe.lifecycle_inputs(path, **options)


@pytest.mark.parametrize("stem, radius, limit", [
    ("pinion-lift-rod", 0.003175, 0.00002), ("rack-pinion", 0.0025, 0.0001),
])
def test_production_pins_own_outputs_spec_radius_and_unchanged_limit(probe, stem, radius, limit):
    original = probe.ROOT / f"cad/out/slddrw/{stem}.SLDDRW"
    value = inputs(probe, original)
    assert value["original"] == original
    assert value["source"] == probe.ROOT / f"cad/out/sldprt/{stem}.SLDPRT"
    assert value["radius_m"] == radius
    assert value["position_tolerance_m"] == limit
    assert value["mode"] == "production"
    assert "witness" not in value
    assert "position_after_save" not in value
    assert value["specification_sha256"] == probe.digest(__file__)


@pytest.mark.parametrize("options, message", [
    ({"ink_refresh": "redraw"}, "requires --ink-refresh cold"),
    ({"rack_dimension_location": "above"}, "layout must already come from its recipe"),
])
def test_production_forbids_redraw_only_and_layout_changes(probe, options, message):
    path = probe.ROOT / "cad/out/slddrw/rack-pinion.SLDDRW"
    with pytest.raises(ValueError, match=message):
        inputs(probe, path, **options)


@pytest.mark.parametrize("relative", [
    "cad/out/reports/rack-pinion.SLDDRW", "cad/out/slddrw/another-part.SLDDRW",
    "cad/out/slddrw/rack-pinion.json", "other-checkout/cad/out/slddrw/rack-pinion.SLDDRW",
])
def test_production_rejects_nonexact_pipeline_drawing(probe, relative):
    path = probe.ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not an authorized production drawing")
    with pytest.raises(ValueError, match="two exact own pipeline drawings"):
        inputs(probe, path)


def partial_witness(probe):
    source = probe.ROOT / "cad/out/sldprt/rack-pinion.SLDPRT"
    directory = probe.ROOT / "cad/out/reports/partial"
    directory.mkdir(parents=True)
    original = directory / "partial.SLDDRW"
    original.write_bytes(b"partial drawing")
    witness = {
        "status": "observed_and_closed", "selection": "edge", "source": str(source),
        "exports": {"SLDDRW": {"path": str(original), "sha256": probe.digest(original)}},
        "source_sha256_after": probe.digest(source), "target_circle": [0, 0, 0, 0, 0, 1, 0.0025],
        "original_call": {"position_tolerance_m": 0.0001},
        "position_after_save": [0.22, 0.20, 0.0015],
    }
    path = directory / "receipt.json"
    path.write_text(json.dumps(witness), encoding="utf-8")
    return path, witness


def test_partial_mode_retains_insertion_witness_and_redraw_option(probe):
    path, witness = partial_witness(probe)
    value = inputs(probe, path, mode="partial", ink_refresh="redraw", rack_dimension_location="above")
    assert value["witness"] == witness
    assert value["position_tolerance_m"] == 0.0001
    assert value["radius_m"] == 0.0025


@pytest.mark.parametrize("target", ["source", "drawing"])
def test_partial_input_identity_guard_remains_enforced(probe, target):
    path, witness = partial_witness(probe)
    changed = Path(witness["source"] if target == "source" else witness["exports"]["SLDDRW"]["path"])
    changed.write_bytes(b"changed after witness")
    with pytest.raises(RuntimeError, match="input identity changed"):
        inputs(probe, path, mode="partial")


@pytest.mark.parametrize("field, value", [("status", "failed"), ("selection", "coordinate")])
def test_partial_requires_completed_semantic_edge_probe(probe, field, value):
    path, witness = partial_witness(probe)
    witness[field] = value
    path.write_text(json.dumps(witness), encoding="utf-8")
    with pytest.raises(RuntimeError, match="completed semantic-edge insertion witness"):
        inputs(probe, path, mode="partial")


def test_dangling_readback_rejected_without_baseline(probe):
    with pytest.raises(RuntimeError, match="annotation is dangling"):
        probe.assert_annotation_state({"is_dangling": True, "shoulder": True, "forced_shoulder": False})


@pytest.mark.parametrize("field", ["shoulder", "forced_shoulder"])
def test_shoulder_changes_rejected(probe, field):
    baseline = {"is_dangling": False, "shoulder": True, "forced_shoulder": False}
    current = dict(baseline)
    current[field] = not current[field]
    with pytest.raises(RuntimeError, match="shoulder state changed"):
        probe.assert_annotation_state(current, baseline)


def test_non_dangling_unchanged_shoulder_readbacks_pass(probe):
    state = {"is_dangling": False, "shoulder": True, "forced_shoulder": False}
    probe.assert_annotation_state(state)
    probe.assert_annotation_state(dict(state), state)


@pytest.mark.parametrize("faces", [[], [object()], [object(), None], [object(), object(), object()]])
def test_edge_requires_exactly_two_nonnull_adjacent_faces(probe, faces):
    body = object()
    app = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    edge = SimpleNamespace(GetBody=lambda: body, GetTwoAdjacentFaces2=lambda: faces)
    source = SimpleNamespace(GetBodies2=lambda *_args: [body])
    extension = SimpleNamespace(GetCorrespondingEntity2=lambda _edge: edge)
    view = SimpleNamespace(GetCorrespondingEntity=lambda _edge: edge)
    with pytest.raises(RuntimeError, match="exactly two nonnull adjacent faces"):
        probe.edge_ownership(app, edge, source, extension, view)


def test_same_radius_edge_from_different_body_is_rejected(probe):
    # Geometry could be numerically identical; native body identity must still match.
    body, other_body = object(), object()
    app = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    edge = SimpleNamespace(GetBody=lambda: other_body)
    source = SimpleNamespace(GetBodies2=lambda *_args: [body])
    extension = SimpleNamespace(GetCorrespondingEntity2=lambda _edge: edge)
    view = SimpleNamespace(GetCorrespondingEntity=lambda _edge: edge)
    with pytest.raises(RuntimeError, match="body identity mismatch"):
        probe.edge_ownership(app, edge, source, extension, view)


def test_edge_owning_body_positive_control_and_readbacks(probe):
    body, view_body = object(), object()
    faces = (object(), object())
    app = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    edge = SimpleNamespace(GetBody=lambda: view_body)
    model_edge = SimpleNamespace(GetBody=lambda: body, GetTwoAdjacentFaces2=lambda: faces)
    mapped_calls, roundtrip_calls = [], []

    def map_to_model(selected):
        mapped_calls.append(selected)
        return model_edge

    def map_to_view(canonical):
        roundtrip_calls.append(canonical)
        return edge

    extension = SimpleNamespace(GetCorrespondingEntity2=map_to_model)
    view = SimpleNamespace(GetCorrespondingEntity=map_to_view)
    calls = []

    def get_bodies(kind, visible_only):
        calls.append((kind, visible_only))
        return [body]

    canonical, actual_faces, state = probe.edge_ownership(
        app, edge, SimpleNamespace(GetBodies2=get_bodies), extension, view
    )
    assert canonical is model_edge
    assert actual_faces == faces
    assert calls == [(0, False)]
    assert mapped_calls == [edge]
    assert roundtrip_calls == [model_edge]
    assert state == {"source_solid_body_count": 1, "source_body_self_equality": 1,
                     "canonical_edge_body_same_as_source": 1, "adjacent_face_count": 2,
                     "mapped_model_edge": "present", "view_edge_self_equality": 1,
                     "roundtrip_edge_same": 1, "canonical_edge_vs_view_edge": 0,
                     "drawing_edge_body_vs_source_body": 0}


@pytest.mark.parametrize("count", [0, 2])
def test_ambiguous_source_solid_body_rejected(probe, count):
    source = SimpleNamespace(GetBodies2=lambda *_args: [object() for _ in range(count)])
    with pytest.raises(RuntimeError, match="expected one source solid body"):
        probe.edge_ownership(None, None, source, None, None)


@pytest.mark.parametrize("missing", ["canonical", "roundtrip"])
def test_missing_entity_correspondence_is_rejected_without_fallback(probe, missing):
    body, edge = object(), object()
    source = SimpleNamespace(GetBodies2=lambda *_args: [body])
    extension = SimpleNamespace(GetCorrespondingEntity2=lambda _edge: None if missing == "canonical" else edge)
    view = SimpleNamespace(GetCorrespondingEntity=lambda _edge: None)
    with pytest.raises(RuntimeError, match="corresponding"):
        probe.edge_ownership(None, edge, source, extension, view)


@pytest.mark.parametrize("equality", [0, -1])
def test_wrong_or_unknown_roundtrip_identity_is_rejected(probe, equality):
    body, edge, canonical, roundtrip = object(), object(), object(), object()
    source = SimpleNamespace(GetBodies2=lambda *_args: [body])
    extension = SimpleNamespace(GetCorrespondingEntity2=lambda _edge: canonical)
    view = SimpleNamespace(GetCorrespondingEntity=lambda _edge: roundtrip)
    app = SimpleNamespace(IsSame=lambda left, right: 1 if left is right else equality)
    with pytest.raises(RuntimeError, match="roundtrip mismatch"):
        probe.edge_ownership(app, edge, source, extension, view)


def test_unknown_canonical_body_identity_is_rejected(probe):
    body, canonical_body, edge = object(), object(), object()
    canonical = SimpleNamespace(GetBody=lambda: canonical_body)
    source = SimpleNamespace(GetBodies2=lambda *_args: [body])
    extension = SimpleNamespace(GetCorrespondingEntity2=lambda _edge: canonical)
    view = SimpleNamespace(GetCorrespondingEntity=lambda _edge: edge)
    app = SimpleNamespace(IsSame=lambda left, right: 1 if left is right else -1)
    with pytest.raises(RuntimeError, match="body identity mismatch"):
        probe.edge_ownership(app, edge, source, extension, view)


def test_translation_rejects_stale_triangle_even_with_current_lines(probe):
    initial = {
        "datum_lines": [[0, .1, .1, 0, .11, .1, 0]],
        "datum_triangles": [[.1, .1, 0, .11, .1, 0, .1, .11, 0, 1, 0]],
        "dimension_lines": [[0, 0, -1, -1, .2, .2, 0, .21, .2, 0]],
        "dimension_triangles": [],
    }
    shift = (.008, .005)
    moved = deepcopy(initial)
    for field, offsets in (("datum_lines", (1, 4)), ("datum_triangles", (0, 3, 6)),
                           ("dimension_lines", (4, 7))):
        for row in moved[field]:
            for offset in offsets:
                row[offset] += shift[0]
                row[offset + 1] += shift[1]
    assert probe.assert_translated_ink(initial, moved, shift) == 0
    moved["datum_triangles"] = initial["datum_triangles"]
    with pytest.raises(RuntimeError, match="ink remains stale"):
        probe.assert_translated_ink(initial, moved, shift)


@pytest.fixture
def finish_stage():
    return {
        "position": [0.1, 0.1, 0],
        "datum_lines": [[0, 0.1, 0.1, 0, 0.11, 0.1, 0]],
        "datum_triangles": [[0.11, 0.1, 0, 0.112, 0.1, 0, 0.11, 0.102, 0, 1, 0]],
        "projected_rim_center": [0.2, 0.2], "projected_rim_radius_m": 0.005,
        "finish_count": 1, "finish_position": [0.25, 0.15, 0],
        "finish_is_dangling": False, "finish_attachment_types": [1],
        "finish_attachment_count": 1, "finish_edge_same": [1],
        "finish_text_count": 1, "finish_roughness": "Ra 1.6",
        "finish_leaders": [[0.205, 0.2, 0, 0.25, 0.15, 0]],
        "finish_lines": [[0, 0, -1, -1, 0.25, 0.15, 0, 0.26, 0.155, 0]],
        "finish_triangles": [],
    }


def test_finish_positive_control_attachment_rim_and_clearance(probe, finish_stage):
    result = probe.assert_rack_finish(finish_stage)
    assert result["finish_rim_error_m"] < 1e-8
    assert result["finish_datum_line_triangle_clearance_m"] > 0.001


@pytest.mark.parametrize("field, value, message", [
    ("finish_count", 0, "intended bore edge"),
    ("finish_is_dangling", True, "intended bore edge"),
    ("finish_attachment_count", 2, "intended bore edge"),
    ("finish_attachment_types", [2], "intended bore edge"),
    ("finish_edge_same", [0], "intended bore edge"),
    ("finish_edge_same", [-1], "intended bore edge"),
    ("finish_edge_same", [None], "intended bore edge"),
    ("finish_roughness", "Ra 3.2", "Ra 1.6"),
    ("finish_text_count", 0, "Ra 1.6"),
    ("finish_position", [float("nan"), 0, 0], "finish position"),
    ("finish_leaders", [], "exactly one leader"),
    ("finish_leaders", [[0, 0]], "leader points"),
    ("finish_leaders", [[float("nan"), 0, 0, 0, 0, 0]], "leader points"),
    ("finish_leaders", [[0.21, 0.2, 0, 0.25, 0.15, 0]], "terminate on intended bore rim"),
    ("finish_lines", [], "display lines"),
    ("finish_lines", [[0, 0]], "primitive"),
    ("finish_triangles", None, "primitive collection"),
])
def test_finish_corrupt_or_missing_readbacks_reject(probe, finish_stage, field, value, message):
    finish_stage[field] = value
    with pytest.raises((RuntimeError, ValueError), match=message):
        probe.assert_rack_finish(finish_stage)


def test_finish_leader_crossing_datum_is_not_hidden_by_separate_display_lines(probe, finish_stage):
    finish_stage["finish_leaders"] = [[0.205, 0.2, 0, 0.1, 0.1, 0]]
    with pytest.raises(RuntimeError, match="ink clearance"):
        probe.assert_rack_finish(finish_stage)


def test_finish_reader_uses_annotation_display_data_and_exact_roughness_slot(probe, finish_stage):
    edge, calls = object(), []

    def text_count():
        calls.append("count")
        return 1

    def text(slot):
        calls.append(slot)
        return "Ra 1.6"

    symbol = SimpleNamespace(GetTextCount=text_count, GetText=text)
    data = SimpleNamespace(GetLineCount=lambda: 1, GetTriangleCount=lambda: 0,
                           GetLineAtIndex2=lambda _index: finish_stage["finish_lines"][0])
    annotation = SimpleNamespace(
        GetType=lambda: 7, GetSpecificAnnotation=lambda: symbol, GetDisplayData=lambda: data,
        GetPosition=lambda: finish_stage["finish_position"], IsDangling=lambda: False,
        GetAttachedEntities3=lambda: [edge], GetAttachedEntityTypes=lambda: [1],
        GetLeaderCount=lambda: 1, GetLeaderPointsAtIndex=lambda _index: finish_stage["finish_leaders"][0],
    )
    view = SimpleNamespace(GetAnnotations=lambda: [SimpleNamespace(GetType=lambda: 6), annotation])
    app = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    actual = probe.read_rack_finish(app, view, edge)
    assert calls == ["count", 8]
    assert actual == {key: value for key, value in finish_stage.items() if key.startswith("finish_")}
    finish_stage.update(actual)
    probe.assert_rack_finish(finish_stage)


@pytest.mark.parametrize("count", [0, 2])
def test_finish_reader_rejects_absent_or_multiple_symbols(probe, count):
    view = SimpleNamespace(GetAnnotations=lambda: [SimpleNamespace(GetType=lambda: 7) for _ in range(count)])
    with pytest.raises(RuntimeError, match="exactly one rack surface-finish"):
        probe.read_rack_finish(None, view, None)


@pytest.mark.parametrize("stale", ["finish_lines", "finish_triangles", "finish_leaders"])
def test_finish_primitive_translation_rejects_stale_arrays(probe, finish_stage, stale):
    initial = deepcopy(finish_stage)
    initial["dimension_lines"] = deepcopy(initial["finish_lines"])
    initial["dimension_triangles"] = []
    initial["finish_triangles"] = [[0.25, 0.15, 0, 0.251, 0.15, 0, 0.25, 0.151, 0, 1, 0]]
    moved, shift = deepcopy(initial), (0.008, 0.005)
    for field, offsets in (("datum_lines", (1, 4)), ("datum_triangles", (0, 3, 6)),
                           ("dimension_lines", (4, 7)), ("finish_lines", (4, 7)),
                           ("finish_triangles", (0, 3, 6)), ("finish_leaders", (0, 3))):
        for row in moved[field]:
            for offset in offsets:
                row[offset] += shift[0]
                row[offset + 1] += shift[1]
    assert probe.assert_translated_ink(initial, moved, shift) == 0
    moved[stale] = initial[stale]
    with pytest.raises(RuntimeError, match="ink remains stale"):
        probe.assert_translated_ink(initial, moved, shift)


EVIDENCE = Path(__file__).resolve().parents[2] / "docs/pipeline/evidence/vm2-datum-placement/probes"


def recorded_diameter_stage(folder, index=0):
    """Read archived native observations without altering their historical status."""
    receipt = json.loads((EVIDENCE / folder / "receipt.json").read_bytes())
    return receipt, deepcopy(receipt["stages"][index])


def test_production_diameter_gate_rejects_recorded_original_overlap(probe):
    receipt, stage = recorded_diameter_stage("rack-native-lifecycle-original")
    assert receipt["status"] == "passed"  # historical observation, not ink acceptance
    with pytest.raises(RuntimeError, match="ink clearance 0 m"):
        probe.assert_production_diameter_clearance(stage, "production")
    assert "datum_diameter_line_triangle_clearance_m" not in stage


@pytest.mark.parametrize("stem", ("rack", "rod"))
@pytest.mark.parametrize("index", range(5))
def test_production_diameter_gate_checks_each_recorded_cold_stage(probe, stem, index):
    _, stage = recorded_diameter_stage(f"{stem}-production-lifecycle-33696944", index)
    probe.assert_production_diameter_clearance(stage, "production")
    measured = stage["datum_diameter_line_triangle_clearance_m"]
    assert measured >= 0.001
    if stem == "rack":
        expected = 0.002521455399822 if stage["stage"] == "scaled" else 0.001947243456304
        assert measured == pytest.approx(expected, abs=1e-14)


@pytest.mark.parametrize("field", ("datum_lines", "datum_triangles", "dimension_lines"))
def test_production_diameter_gate_rejects_missing_recorded_ink(probe, field):
    _, stage = recorded_diameter_stage("rack-production-lifecycle-33696944")
    stage[field] = []
    with pytest.raises(ValueError, match="missing"):
        probe.assert_production_diameter_clearance(stage, "production")


def test_production_diameter_gate_rejects_actual_stale_moved_ink(probe):
    _, stage = recorded_diameter_stage("rack-native-lifecycle-above", 1)
    with pytest.raises(ValueError, match="annotation anchor"):
        probe.assert_production_diameter_clearance(stage, "production")


@pytest.mark.parametrize("folder,index", [
    ("rack-native-lifecycle-original", 0), ("rack-native-lifecycle-above", 1),
])
def test_partial_diameter_readbacks_remain_observations(probe, folder, index):
    receipt, stage = recorded_diameter_stage(folder, index)
    original = deepcopy(stage)
    probe.assert_production_diameter_clearance(stage, "partial")
    assert stage == original
    assert receipt["status"] == "passed"


def test_diameter_gate_rejects_unknown_mode(probe):
    with pytest.raises(ValueError, match="unknown lifecycle input mode"):
        probe.assert_production_diameter_clearance({}, "unknown")

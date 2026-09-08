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
    with pytest.raises(RuntimeError, match="exactly two nonnull adjacent faces"):
        probe.edge_ownership(app, edge, source)


def test_same_radius_edge_from_different_body_is_rejected(probe):
    # Geometry could be numerically identical; native body identity must still match.
    body, other_body = object(), object()
    app = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    edge = SimpleNamespace(GetBody=lambda: other_body)
    source = SimpleNamespace(GetBodies2=lambda *_args: [body])
    with pytest.raises(RuntimeError, match="body identity mismatch"):
        probe.edge_ownership(app, edge, source)


def test_edge_owning_body_positive_control_and_readbacks(probe):
    body = object()
    faces = (object(), object())
    app = SimpleNamespace(IsSame=lambda left, right: int(left is right))
    edge = SimpleNamespace(GetBody=lambda: body, GetTwoAdjacentFaces2=lambda: faces)
    calls = []

    def get_bodies(kind, visible_only):
        calls.append((kind, visible_only))
        return [body]

    actual_faces, state = probe.edge_ownership(app, edge, SimpleNamespace(GetBodies2=get_bodies))
    assert actual_faces == faces
    assert calls == [(0, False)]
    assert state == {"source_solid_body_count": 1, "source_body_self_equality": 1,
                     "edge_body_same_as_source": 1, "adjacent_face_count": 2}


@pytest.mark.parametrize("count", [0, 2])
def test_ambiguous_source_solid_body_rejected(probe, count):
    source = SimpleNamespace(GetBodies2=lambda *_args: [object() for _ in range(count)])
    with pytest.raises(RuntimeError, match="expected one source solid body"):
        probe.edge_ownership(None, None, source)


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

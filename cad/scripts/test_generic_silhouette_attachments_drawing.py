"""Supported type46 geometry closes a coverage gap, not an identity exemption."""

from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

from diagnostics import _silhouette_attachment_witness as silhouette
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics import probe_drawing_attachments as attachments
from test_probe_drawing_attachments import (
    Annotation,
    Model,
    View,
    dimension,
    display_dimension,
)
from test_silhouette_attachment_witness_drawing import fixture as native_silhouette


@pytest.fixture
def scene(tmp_path, monkeypatch):
    source = tmp_path / "spring-hook.SLDPRT"
    source.write_bytes(b"protected source")
    app, _, entity, face, surface, curve = native_silhouette()
    finish = Annotation("Finish", kind=7, entities=(entity,), kinds=(46,))
    dimensions = []
    for name, kinds, value in (
        ("Rise", (11, 11), 0.0076),
        ("ArmRun", (11, 11), 0.0025),
        ("RodDia", (10,), 0.0014),
    ):
        annotation = Annotation(
            name, entities=tuple(object() for _ in kinds), kinds=kinds
        )
        parameter = dimension(name, f"{name}@HookProfile@spring-hook.Part", value)
        annotation.display = display_dimension(parameter)
        dimensions.append(annotation)
    view = View("Front", source, (finish, *dimensions, Annotation("Center", kind=13)))
    entity.GetView = Mock(return_value=view)
    model = Model([view])
    adapter = NS(currentModel=model, swApp=app)
    monkeypatch.setattr(attachments, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(silhouette, "_early_bound", lambda obj, _: obj)
    observed = Mock(wraps=silhouette.snapshot)
    monkeypatch.setattr(silhouette, "snapshot", observed)
    return NS(
        source=source,
        app=app,
        entity=entity,
        face=face,
        surface=surface,
        curve=curve,
        finish=finish,
        dimensions=dimensions,
        view=view,
        model=model,
        adapter=adapter,
        observed=observed,
        key="Sheet1/Front/Finish/7",
    )


def read(scene):
    return attachments.snapshot(scene.model, app=scene.app)


def test_spring_shape_satisfies_real_coverage_with_one_raw_silhouette_read(scene):
    result = pilot._drawing_semantics(
        scene.adapter, source=scene.source, configuration="Default"
    )
    assert tuple(result["checked"]) == (scene.key,)
    tag, raw = result["checked"][scene.key][0]
    assert tag == "silhouette"
    assert raw["curve_parameters"] == scene.curve.LineParams
    assert raw["face_surface"]["parameters"] == scene.surface.CylinderParams
    assert raw["start"] == (0.003, 0, 0)
    assert raw["end"] == (0.003, 0, 0.1)
    assert len(result["dimensions"]) == 3
    assert len(result["excluded"]) == 4
    assert result["dimensions_excluded"] == {}
    assert scene.key not in result["excluded"]
    assert result["models"]["Sheet1/Front"] == {
        "path": str(scene.source),
        "configuration": "Default",
    }
    scene.observed.assert_called_once_with(scene.app, scene.view, scene.entity)
    scene.entity.GetView.assert_called_once_with()
    assert scene.source.read_bytes() == b"protected source"


@pytest.mark.parametrize(
    "shape", ["null", "wrong_view", "surface", "curve", "nonfinite"]
)
def test_invalid_type46_is_a_failure_not_an_exclusion(scene, shape):
    if shape == "null":
        scene.finish.entities = (None,)
    if shape == "wrong_view":
        scene.entity.GetView.return_value = object()
    if shape == "surface":
        scene.surface.Identity = lambda: 4003
    if shape == "curve":
        scene.curve.IsLine = lambda: False
    if shape == "nonfinite":
        scene.curve.LineParams = (float("nan"), 0, 0, 0, 0, 1)
    with pytest.raises(RuntimeError):
        read(scene)
    assert scene.observed.call_count == (0 if shape == "null" else 1)


@pytest.mark.parametrize("mutation", ["endpoint", "surface", "curve", "drop", "add"])
def test_exact_raw_silhouette_and_attachment_inventory_changes_still_fail(
    scene, mutation
):
    before = read(scene)
    if mutation == "endpoint":
        # Smaller than the legacy geometry() rounding quantum: never round46.
        scene.entity.GetEndPoint = lambda: NS(ArrayData=(0.003, 0, 0.100000000001))
    if mutation == "surface":
        values = list(scene.surface.CylinderParams)
        values[-1] += 1e-12
        scene.surface.CylinderParams = tuple(values)
    if mutation == "curve":
        values = list(scene.curve.LineParams)
        values[0] += 1e-12
        scene.curve.LineParams = tuple(values)
    if mutation == "drop":
        scene.finish.entities, scene.finish.kinds = (), ()
    if mutation == "add":
        scene.finish.entities, scene.finish.kinds = (scene.entity,) * 2, (46,) * 2
    after = read(scene)
    with pytest.raises(RuntimeError, match="attachment snapshot changed.*Finish"):
        attachments.compare(before, after, "cold reopen")


def test_mixed_supported_attachments_read_each_silhouette_once(scene):
    vertex = NS(GetPoint=lambda: (0.01, 0.02, 0.03))
    scene.finish.entities = (vertex, scene.entity)
    scene.finish.kinds = (3, 46)
    result = read(scene)
    assert result["checked"][scene.key][0] == ("vertex", (0.01, 0.02, 0.03))
    assert result["checked"][scene.key][1][0] == "silhouette"
    scene.observed.assert_called_once_with(scene.app, scene.view, scene.entity)


def test_null46_in_an_otherwise_unsupported_array_still_fails(scene):
    scene.finish.entities, scene.finish.kinds = (None, None), (0, 46)
    with pytest.raises(RuntimeError, match="supported attachment is null"):
        read(scene)
    scene.observed.assert_not_called()


def test_non_silhouette_snapshot_does_not_add_helper_reads(scene):
    scene.finish.entities = (NS(GetPoint=lambda: (0.01, 0.02, 0.03)),)
    scene.finish.kinds = (3,)
    assert read(scene)["checked"][scene.key] == (("vertex", (0.01, 0.02, 0.03)),)
    scene.observed.assert_not_called()


def test_fresh_cold_handles_compare_raw_geometry_without_using_closed_handles(scene):
    before = read(scene)
    _, _, fresh, *_ = native_silhouette()
    cold_finish = Annotation("Finish", kind=7, entities=(fresh,), kinds=(46,))
    cold_view = View("Front", scene.source, (cold_finish, *scene.view.annotations[1:]))
    fresh.GetView = lambda: cold_view
    scene.entity.GetView.side_effect = AssertionError("old native entity accessed")
    after = attachments.snapshot(Model([cold_view]), app=scene.app)
    attachments.compare(before, after, "fresh native cold handles")
    assert before == after
    assert scene.observed.call_count == 2


def test_dimension_semantics_and_empty_coverage_gate_are_not_weakened(scene):
    before = read(scene)
    after = deepcopy(before)
    key = next(iter(after["dimensions"]))
    after["dimensions"][key]["components"][0]["value_system"] += 1e-12
    with pytest.raises(RuntimeError, match="attachment snapshot changed.*dimensions"):
        attachments.compare(before, after, "dimension changed")
    scene.view.annotations = scene.view.annotations[1:]
    with pytest.raises(pilot.DrawingSemanticCoverageError) as raised:
        pilot._drawing_semantics(
            scene.adapter, source=scene.source, configuration="Default"
        )
    assert raised.value.validation["failed_conditions"] == ["checked_empty"]

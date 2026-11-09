"""Pure regression coverage of the deliberately closed experimental planner."""
from __future__ import annotations

import copy
import json

import pytest

from diagnostics._feature_reconcile import plan, recipe


def test_identical_serialized_recipe_is_noop():
    before = recipe()
    after = json.loads(json.dumps(before))
    result = plan(before, after)
    assert result.decision == "noop"
    assert result.edits == ()


def test_parameter_changes_have_stable_semantic_order_without_mutating_inputs():
    before = recipe()
    after = recipe(24, 15)
    snapshots = copy.deepcopy((before, after))
    result = plan(before, after)
    assert result.decision == "incremental"
    assert result.edits == (("diameter", 24.0), ("depth", 15.0))
    assert (before, after) == snapshots


@pytest.mark.parametrize("parameters, expected", [((21, 12), (("diameter", 21.0),)), ((20, 14), (("depth", 14.0),))])
def test_single_parameter_edit(parameters, expected):
    assert plan(recipe(), recipe(*parameters)).edits == expected


@pytest.mark.parametrize("change", [
    lambda value: value.update(schema=2),
    lambda value: value["features"].reverse(),
    lambda value: value["features"].pop(),
    lambda value: value["features"].append(copy.deepcopy(value["features"][0])),
    lambda value: value["features"][0].update(key="different_key"),
    lambda value: value["features"][0].update(name="DifferentNativeName"),
    lambda value: value["features"][0].update(type="Spline"),
    lambda value: value["features"][1].update(depends_on=[]),
    lambda value: value["features"][1].update(operation="through_all"),
    lambda value: value["dimensions"].update(depth="D1@OtherFeature"),
    lambda value: value["features"][0].update(unsupported_option=True),
])
def test_structural_change_refuses_entire_parameter_edit(change):
    before = recipe()
    after = recipe(24, 15)
    change(after)
    result = plan(before, after)
    assert result.decision == "full_build"
    assert result.edits == ()  # never leak partial edits from a refused plan


def test_matching_but_unsupported_structures_do_not_become_noop():
    unsupported = recipe()
    unsupported["features"][1]["operation"] = "through_all"
    result = plan(unsupported, copy.deepcopy(unsupported))
    assert result.decision == "full_build"
    assert result.edits == ()


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "24", None])
@pytest.mark.parametrize("key", ["diameter", "depth"])
def test_invalid_parameters_fail_before_any_edit_plan(key, value):
    after = recipe()
    after["parameters_mm"][key] = value
    with pytest.raises(ValueError, match="finite positive"):
        plan(recipe(), after)


def test_recipe_instances_do_not_share_structural_containers():
    first = recipe()
    first["features"][1]["depends_on"].clear()
    assert recipe()["features"][1]["depends_on"] == ["profile"]


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(unknown=True),
    lambda value: value.pop("features"),
    lambda value: value["parameters_mm"].update(extra=1),
    lambda value: value["parameters_mm"].pop("depth"),
])
def test_malformed_recipe_is_not_silently_treated_as_full_build(mutate):
    after = recipe()
    mutate(after)
    with pytest.raises(ValueError):
        plan(recipe(), after)


@pytest.mark.parametrize("background", ["flat", "gradient"])
def test_visual_evidence_rejects_blank_backgrounds(tmp_path, background):
    from PIL import Image
    from diagnostics.benchmark_feature_reconcile import image_content_evidence

    image = (Image.new("RGB", (400, 300), (180, 180, 180)) if background == "flat"
             else Image.linear_gradient("L").resize((400, 300)).convert("RGB"))
    path = tmp_path / "blank.png"
    image.save(path)
    with pytest.raises(RuntimeError, match="Blank or background-only"):
        image_content_evidence(path)


def test_visual_evidence_accepts_nontrivial_object_pixels(tmp_path):
    from PIL import Image, ImageDraw
    from diagnostics.benchmark_feature_reconcile import image_content_evidence

    image = Image.new("RGB", (400, 300), (180, 180, 180))
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 80, 300, 220), fill=(70, 70, 70))
    draw.ellipse((100, 40, 300, 120), fill=(120, 120, 120), outline=(20, 20, 20))
    path = tmp_path / "object.png"
    image.save(path)
    evidence = image_content_evidence(path)
    assert evidence["dimensions"] == [400, 300]
    assert evidence["luminance_range"] == 160
    assert evidence["strong_edge_pixels"] >= evidence["required_edge_pixels"]

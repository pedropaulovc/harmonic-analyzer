"""Synthetic sheet data tests; no claimed native slotted source identities."""

from copy import deepcopy

import pytest

from diagnostics import _slotted_screw_layout_witness as witness


def rectangle(xmin=0.05, ymin=0.10, xmax=0.08, ymax=0.15):
    return dict(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)


@pytest.fixture
def scene():
    # These arbitrary keys/values are synthetic. Native types/IDs come only from
    # the separately reviewed acceptance manifest, never from this fixture.
    dimensions, annotations = {}, {}
    for key, orientation in witness.DIMENSION_VIEWS.items():
        annotation_key = f"{orientation}/{key}"
        dimensions[key] = {
            "annotation_key": annotation_key,
            "orientation": orientation,
            "presentation": {"show_dimension_value": True},
            "native_text_values": [" 2.50 "],
        }
        annotations[annotation_key] = {
            "semantic": {"owner_type": 0, "kind": 4, "visible": 1, "dangling": False},
            "measurement": {
                "envelope": rectangle(), "body": rectangle(),
                "native_strokes": [{"start": [0.06, 0.1], "end": [0.06, 0.15], "width_m": 0.0}],
            },
        }
    views = {
        orientation: {"orientation": orientation, "scale": [6.0, 1.0], "outline": [0.05, 0.1, 0.08, 0.15]}
        for orientation in witness.VIEWS
    }
    return {"model_dimensions": {"dimensions": dimensions}, "annotations": annotations}, views


def test_candidate_requires_entire_native_stroke_envelope_inside_border(scene):
    bank, views = scene
    result = witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27])
    assert result["border_status"] == "inside"
    key = bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["annotation_key"]
    bank["annotations"][key]["measurement"]["envelope"]["ymax"] = 0.271
    result = witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27])
    assert result["border_status"] == "outside"
    assert result["head_height_top_clearance_m"] == pytest.approx(-0.001)
    witness.require_border(witness.LayoutObservation.BASELINE, result)
    with pytest.raises(RuntimeError, match="candidate.*border"):
        witness.require_border(witness.LayoutObservation.CANDIDATE, result)


@pytest.mark.parametrize("damage", ["hidden", "dangling", "excluded", "missing", "extra", "numeric_hidden", "wrong_view", "wrong_scale", "nonfinite", "missing_strokes"])
def test_geometry_rejects_incomplete_or_changed_contract(scene, damage):
    bank, views = scene
    key = bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["annotation_key"]
    row = bank["annotations"][key]
    if damage == "hidden":
        row["semantic"]["visible"] = 3
    if damage == "dangling":
        row["semantic"]["dangling"] = True
    if damage == "excluded":
        row["measurement_exclusion"] = "unsupported"
    if damage == "missing":
        del bank["annotations"][key]
    if damage == "extra":
        bank["model_dimensions"]["dimensions"]["Extra@Sketch"] = deepcopy(bank["model_dimensions"]["dimensions"]["HeadHt@Head"])
    if damage == "numeric_hidden":
        bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["presentation"]["show_dimension_value"] = False
    if damage == "wrong_view":
        bank["model_dimensions"]["dimensions"]["HeadHt@Head"]["orientation"] = "*Top"
    if damage == "wrong_scale":
        views["*Front"]["scale"] = [3.0, 1.0]
    if damage == "nonfinite":
        row["measurement"]["envelope"]["ymax"] = float("nan")
    if damage == "missing_strokes":
        row["measurement"]["native_strokes"] = []
    with pytest.raises((RuntimeError, ValueError), match="contract|dimension|measurement|stroke|scale|finite"):
        witness.layout_geometry(bank, views, [0.01, 0.01, 0.42, 0.27])


def test_no_existing_target_is_silently_opted_in():
    from diagnostics._recipe_acceptance_targets import TARGETS

    assert "slotted_screw" not in TARGETS  # Enrollment awaits real builder data.
    witness.require_selection(None, ("rocker_arm",), TARGETS)
    with pytest.raises(ValueError, match="slotted"):
        witness.require_selection(witness.LayoutObservation.CANDIDATE, ("rocker_arm",), TARGETS)
    with pytest.raises(ValueError, match="enrollment"):
        witness.require_selection(witness.LayoutObservation.CANDIDATE, ("slotted_screw",), TARGETS)

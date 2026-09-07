"""Whole-text import requires the full documented state, not a prefix match."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import _drawing_common as common
import _model_dimension_callouts as author
import test_model_reference_callouts_drawing as reference_tests

native = reference_tests.native
reference = reference_tests.reference
TEXT = "#4-40 UNC-2A"
EXPECTED = {1: TEXT, 2: "", 3: "", 4: "", 5: TEXT, 6: "", 7: "", 8: ""}


@pytest.fixture
def whole(reference):
    def set_text(slot, text):
        assert slot == 0
        reference.fields.update(
            {part: text if part in (1, 5) else "" for part in range(1, 9)}
        )
        reference.display.ShowDimensionValue = False

    reference.display.SetText.side_effect = set_text
    return reference


def author_whole(whole):
    author.author_model_callouts(
        whole.adapter, "ArborBoreProfile", {"ArborBoreDia": TEXT}, location="all"
    )


def verify_whole(whole):
    whole.model.GetType.return_value = 3
    common.verify_dimension_callouts(
        whole.adapter,
        [whole.annotation],
        {"ArborBoreDia": TEXT},
        feature_name="ArborBoreProfile",
        view=whole.view,
        source_model=whole.source_model,
        location="all",
    )


def test_whole_text_uses_native_void_all_then_exact_full_readback(whole):
    before_dimension = vars(whole.dimension).copy()
    author_whole(whole)
    assert whole.fields == EXPECTED
    assert whole.display.ShowDimensionValue is False
    assert vars(whole.dimension) == before_dimension
    whole.display.SetText.assert_called_once_with(0, TEXT)
    assert all(
        args.args[0] in range(1, 9) for args in whole.display.GetText.call_args_list
    )
    whole.model.GraphicsRedraw2.assert_called_once_with()


@pytest.mark.parametrize("visible", [True, False])
def test_whole_text_accepts_valid_visible_or_previously_hidden_initial_state(
    whole, visible
):
    whole.display.ShowDimensionValue = visible
    author_whole(whole)
    assert whole.fields == EXPECTED
    assert whole.display.ShowDimensionValue is False


def test_whole_text_cannot_replace_the_sibling_underhead_callout(whole):
    sibling = Mock(spec=["GetDimension2", "SetText"])
    sibling.GetDimension2.return_value = SimpleNamespace(
        Name="ShankLg", FullName="ShankLg@Shank@part.Part"
    )
    sibling.fields = {4: "UNDERHEAD LENGTH", 8: "UNDERHEAD LENGTH"}
    whole.feature.GetNextDisplayDimension.side_effect = [sibling, None]
    author_whole(whole)
    sibling.SetText.assert_not_called()
    assert sibling.fields == {4: "UNDERHEAD LENGTH", 8: "UNDERHEAD LENGTH"}


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate",
        "wrong_feature",
        "wrong_name",
        "hole",
        "drawing",
        "active",
        "current",
        "malformed_visibility",
    ],
)
def test_whole_text_rejects_bad_source_before_writing(whole, damage):
    if damage == "missing":
        whole.feature.GetFirstDisplayDimension.return_value = None
    if damage == "duplicate":
        whole.feature.GetNextDisplayDimension.side_effect = [whole.display, None]
    if damage == "wrong_feature":
        whole.dimension.FullName = "ArborBoreDia@WrongFeature@alignment-pinion.Part"
    if damage == "wrong_name":
        whole.dimension.Name = "OtherBore"
    if damage == "hole":
        whole.display.IsHoleCallout.return_value = True
    if damage == "drawing":
        whole.model.GetType.return_value = 3
    if damage == "active":
        whole.adapter.swApp.ActiveDoc = object()
    if damage == "current":
        whole.adapter.currentModel = None
    if damage == "malformed_visibility":
        whole.display.ShowDimensionValue = 1
    with pytest.raises(
        RuntimeError, match="exactly one|hole callouts|PART|identity|visibility"
    ):
        author_whole(whole)
    whole.display.SetText.assert_not_called()


@pytest.mark.parametrize("slot", range(1, 9))
@pytest.mark.parametrize("stage", ["setter", "redraw"])
def test_whole_text_rejects_every_wrong_compartment(whole, slot, stage):
    original = whole.display.SetText.side_effect

    def damage():
        whole.fields[slot] = "unexpected"

    if stage == "setter":

        def setter(part, text):
            original(part, text)
            damage()

        whole.display.SetText.side_effect = setter
    else:
        whole.model.GraphicsRedraw2.side_effect = damage
    with pytest.raises(RuntimeError, match="presentation"):
        author_whole(whole)


@pytest.mark.parametrize("visible", [True, 0, None, "False"])
def test_whole_text_prefix_only_or_malformed_visibility_is_not_success(whole, visible):
    original = whole.display.SetText.side_effect

    def setter(part, text):
        original(part, text)
        whole.display.ShowDimensionValue = visible

    whole.display.SetText.side_effect = setter
    with pytest.raises(RuntimeError, match="presentation|visibility"):
        author_whole(whole)


def test_whole_text_rejects_unsupported_initial_readback_before_writing(whole):
    whole.fields[3] = None
    with pytest.raises(RuntimeError, match="text"):
        author_whole(whole)
    whole.display.SetText.assert_not_called()


def test_whole_text_verifier_requires_source_and_imported_numeric_hidden(whole):
    whole.fields.update(EXPECTED)
    whole.display.ShowDimensionValue = False
    whole.source_display.ShowDimensionValue = False
    verify_whole(whole)
    whole.display.SetText.assert_not_called()
    whole.model.GraphicsRedraw2.assert_not_called()


@pytest.mark.parametrize(
    "damage",
    [
        "source_visible",
        "drawing_visible",
        "source_text",
        "drawing_text",
        "source_hole",
        "wrong_view",
        "wrong_parameter",
    ],
)
def test_whole_text_verifier_rejects_prefix_equivalent_but_incorrect_state(
    whole, damage
):
    whole.fields.update(EXPECTED)
    whole.display.ShowDimensionValue = False
    whole.source_display.ShowDimensionValue = False
    source_fields = dict(whole.fields)
    whole.source_display.GetText = source_fields.__getitem__
    if damage == "source_visible":
        whole.source_display.ShowDimensionValue = True
    if damage == "drawing_visible":
        whole.display.ShowDimensionValue = True
    if damage == "source_text":
        source_fields[8] = "extra"
    if damage == "drawing_text":
        whole.fields[2] = "extra"
    if damage == "source_hole":
        whole.source_display.IsHoleCallout = lambda: True
    if damage == "wrong_view":
        whole.annotation.Owner = object()
    if damage == "wrong_parameter":
        whole.display.GetDimension2.return_value = SimpleNamespace(
            **vars(whole.dimension)
        )
    with pytest.raises(RuntimeError, match="presentation|identity|hole"):
        verify_whole(whole)
    whole.display.SetText.assert_not_called()

"""Observed cone-tip reference fields are authored once, then verified read-only."""

from types import SimpleNamespace
from unittest.mock import call

import pytest

import _drawing_common as common
import _model_dimension_callouts as author
import test_model_dimension_callouts_drawing as callout_tests

native = callout_tests.native


@pytest.fixture
def reference(native):
    native.fields.update(
        {3: "5/16-18 UNC-2A", 5: "<MOD-DIAM>", 6: "", 7: "5/16-18 UNC-2A", 8: ""}
    )
    native.display.ShowDimensionValue = True
    native.adapter.swApp.ActiveDoc = native.model

    def set_text(slot, text):
        native.fields[slot] = native.fields[slot + 4] = text

    native.display.SetText.side_effect = set_text
    native.source_display.GetText = native.display.GetText
    native.source_display.ShowDimensionValue = True
    native.source_display.IsHoleCallout = lambda: False
    return native


def author_field(reference, location="prefix", text="(<MOD-DIAM>"):
    author.author_model_callouts(
        reference.adapter, "ArborBoreProfile", {"ArborBoreDia": text}, location=location
    )


def verify_field(reference, location="prefix", text="(<MOD-DIAM>"):
    reference.model.GetType.return_value = 3
    common.verify_dimension_callouts(
        reference.adapter,
        [reference.annotation],
        {"ArborBoreDia": text},
        feature_name="ArborBoreProfile",
        view=reference.view,
        source_model=reference.source_model,
        location=location,
    )


@pytest.mark.parametrize(
    "location,slot,text", [("prefix", 1, "(<MOD-DIAM>"), ("suffix", 2, ")")]
)
def test_reference_author_preserves_other_text_numeric_value_and_tolerances(
    reference, location, slot, text
):
    before = dict(reference.fields)
    dimension = vars(reference.dimension).copy()
    author_field(reference, location, text)
    assert reference.fields == {**before, slot: text, slot + 4: text}
    assert reference.display.ShowDimensionValue is True
    assert vars(reference.dimension) == dimension
    reference.display.SetText.assert_called_once_with(slot, text)
    reference.model.GraphicsRedraw2.assert_called_once_with()
    assert call(0) not in reference.display.GetText.call_args_list


@pytest.mark.parametrize("slot", [2, 3, 4, 6, 7, 8])
@pytest.mark.parametrize("boundary", ["setter", "redraw"])
def test_reference_author_rejects_any_other_compartment_change(
    reference, slot, boundary
):
    original = reference.display.SetText.side_effect

    def damage():
        reference.fields[slot] = "lost thread or other field"

    if boundary == "setter":

        def setter(part, text):
            original(part, text)
            damage()

        reference.display.SetText.side_effect = setter
    else:
        reference.model.GraphicsRedraw2.side_effect = damage
    with pytest.raises(RuntimeError, match="presentation"):
        author_field(reference)


@pytest.mark.parametrize("slot", [1, 5])
def test_reference_author_rejects_wrong_requested_field_or_definition(reference, slot):
    original = reference.display.SetText.side_effect

    def setter(part, text):
        original(part, text)
        reference.fields[slot] = "wrong"

    reference.display.SetText.side_effect = setter
    with pytest.raises(RuntimeError, match="presentation"):
        author_field(reference)


@pytest.mark.parametrize("value", [None, 1, False, b"text"])
def test_reference_author_rejects_non_string_text_before_write(reference, value):
    reference.fields[7] = value
    with pytest.raises(RuntimeError, match="text"):
        author_field(reference)
    reference.display.SetText.assert_not_called()


@pytest.mark.parametrize("value", [False, None, 1, "True"])
def test_reference_author_requires_native_visible_numeric_value(reference, value):
    reference.display.ShowDimensionValue = value
    with pytest.raises(RuntimeError, match="numeric"):
        author_field(reference)
    reference.display.SetText.assert_not_called()


@pytest.mark.parametrize("target", ["current", "active"])
def test_reference_author_refuses_changed_document_before_write(reference, target):
    original = reference.display.GetText.side_effect

    def getter(slot):
        if target == "current":
            reference.adapter.currentModel = object()
        else:
            reference.adapter.swApp.ActiveDoc = object()
        return original(slot)

    reference.display.GetText.side_effect = getter
    with pytest.raises(RuntimeError, match="identity"):
        author_field(reference)
    reference.display.SetText.assert_not_called()


def test_reference_author_rejects_substituted_source_dimension(reference):
    reference.model.GraphicsRedraw2.side_effect = lambda: setattr(
        reference.display.GetDimension2,
        "return_value",
        SimpleNamespace(**vars(reference.dimension)),
    )
    with pytest.raises(RuntimeError, match="identity"):
        author_field(reference)


@pytest.mark.parametrize("status", [0, -1, None, True, 1.0, "1"])
def test_reference_author_rejects_non_exact_native_identity(reference, status):
    reference.adapter.swApp.IsSame.side_effect = None
    reference.adapter.swApp.IsSame.return_value = status
    with pytest.raises(RuntimeError, match="identity"):
        author_field(reference)
    reference.display.SetText.assert_not_called()


def test_reference_author_resolves_every_requested_name_before_writing(reference):
    with pytest.raises(RuntimeError, match="exactly one"):
        author.author_model_callouts(
            reference.adapter,
            "ArborBoreProfile",
            {"ArborBoreDia": "(<MOD-DIAM>", "MissingDia": "("},
            location="prefix",
        )
    reference.display.SetText.assert_not_called()


@pytest.mark.parametrize("boundary", ["setter", "redraw"])
def test_reference_author_rejects_numeric_suppression_after_write(reference, boundary):
    original = reference.display.SetText.side_effect

    def suppress():
        reference.display.ShowDimensionValue = False

    if boundary == "setter":

        def setter(slot, text):
            original(slot, text)
            suppress()

        reference.display.SetText.side_effect = setter
    else:
        reference.model.GraphicsRedraw2.side_effect = suppress
    with pytest.raises(RuntimeError, match="numeric"):
        author_field(reference)


@pytest.mark.parametrize(
    "damage", ["missing", "duplicate", "wrong_feature", "wrong_name", "hole", "drawing"]
)
def test_reference_author_retains_exact_part_feature_name_guards(reference, damage):
    if damage == "missing":
        reference.feature.GetFirstDisplayDimension.return_value = None
    if damage == "duplicate":
        reference.feature.GetNextDisplayDimension.side_effect = [
            reference.display,
            None,
        ]
    if damage == "wrong_feature":
        reference.dimension.FullName = "ArborBoreDia@WrongFeature@alignment-pinion.Part"
    if damage == "wrong_name":
        reference.dimension.Name = "OtherBore"
    if damage == "hole":
        reference.display.IsHoleCallout.return_value = True
    if damage == "drawing":
        reference.model.GetType.return_value = 3
    with pytest.raises(RuntimeError, match="exactly one|hole callouts|PART"):
        author_field(reference)
    reference.display.SetText.assert_not_called()


@pytest.mark.parametrize(
    "location,slot,text", [("prefix", 1, "(<MOD-DIAM>"), ("suffix", 2, ")")]
)
def test_reference_verifies_full_source_presentation_read_only(
    reference, location, slot, text
):
    reference.fields[slot] = reference.fields[slot + 4] = text
    verify_field(reference, location, text)
    reference.display.SetText.assert_not_called()
    reference.model.GraphicsRedraw2.assert_not_called()


@pytest.mark.parametrize(
    "damage",
    ["definition", "thread", "source_prefix", "numeric", "wrong_source", "wrong_view"],
)
def test_reference_verifier_rejects_inherited_mismatch_without_repair(
    reference, damage
):
    reference.fields[1] = reference.fields[5] = "(<MOD-DIAM>"
    source_fields = dict(reference.fields)
    reference.source_display.GetText = source_fields.__getitem__
    if damage == "definition":
        reference.fields[5] = "wrong"
    if damage == "thread":
        reference.fields[3] = "wrong"
    if damage == "source_prefix":
        source_fields[1] = source_fields[5] = "<MOD-DIAM>"
    if damage == "numeric":
        reference.display.ShowDimensionValue = False
    if damage == "wrong_source":
        reference.display.GetDimension2.return_value = SimpleNamespace(
            **vars(reference.dimension)
        )
    if damage == "wrong_view":
        reference.annotation.Owner = object()
    with pytest.raises(RuntimeError, match="presentation|numeric|identity"):
        verify_field(reference)
    reference.display.SetText.assert_not_called()
    reference.model.GraphicsRedraw2.assert_not_called()

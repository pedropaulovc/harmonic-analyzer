"""Source-side callout authoring and drawing-side read-only import contract."""

from inspect import getsource
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import _drawing_common as common
import _drawing_marks as marks
import _model_dimension_callouts as author
from _buildgraph import module_deps_of, part_scripts
import alignment_pinion_spec as spec
import build_alignment_pinion as part
import draw_alignment_pinion as drawing


def test_alignment_callout_is_one_shared_literal_contract():
    assert (
        part.DIMENSION_CALLOUTS is drawing.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    )
    assert spec.DIMENSION_CALLOUTS == {"ArborBoreDia": "THRU - REAM\nPRESS FIT"}


def test_alignment_authors_after_marking_and_verifies_in_drawing():
    source = getsource(part.build)
    assert source.index("mark_dimensions_for_drawing(") < source.index(
        "author_model_callouts("
    )
    assert source.index("author_model_callouts(") < source.index(
        "save_part_and_images("
    )
    assert source.count("save_part_and_images(") == 1
    assert "set_dimension_callouts" not in vars(drawing)
    assert "verify_dimension_callouts(" in getsource(drawing.build)


@pytest.fixture
def native(monkeypatch):
    dimension = SimpleNamespace(
        Name="ArborBoreDia",
        FullName="ArborBoreDia@ArborBoreProfile@alignment-pinion.Part",
        SystemValue=0.008,
        tolerance=(2, -0.00002, -0.00004),
    )
    fields = {1: "<MOD-DIAM>", 2: "", 3: "", 4: ""}
    display = Mock(
        spec=["GetDimension2", "GetDimension", "IsHoleCallout", "SetText", "GetText"]
    )
    display.GetDimension2.return_value = dimension
    display.GetDimension.return_value = dimension
    display.IsHoleCallout.return_value = False

    def set_text(slot, text):
        fields[slot] = text  # Native void return: None.

    display.SetText.side_effect = set_text
    display.GetText.side_effect = fields.__getitem__
    feature = Mock(spec=["GetFirstDisplayDimension", "GetNextDisplayDimension"])
    feature.GetFirstDisplayDimension.return_value = display
    feature.GetNextDisplayDimension.return_value = None
    lookup = Mock(return_value=feature)
    monkeypatch.setattr(marks, "_feature_by_name", lookup)
    for module in (author, marks, common):
        monkeypatch.setattr(module, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag", lambda obj, *args: obj
    )
    model = Mock(spec=["GetType", "GraphicsRedraw2"])
    model.GetType.return_value = 1
    annotation = Mock(spec=["GetSpecificAnnotation"])
    annotation.GetSpecificAnnotation.return_value = display

    def read_member(obj, name):
        member = getattr(obj, name)
        return member() if callable(member) else member

    adapter = SimpleNamespace(
        currentModel=model,
        _get_attr_or_call=read_member,
        _attempt=lambda operation, default=None: operation(),
    )
    return SimpleNamespace(
        adapter=adapter,
        model=model,
        dimension=dimension,
        display=display,
        feature=feature,
        lookup=lookup,
        fields=fields,
        annotation=annotation,
    )


def author_call(native, **kwargs):
    author.author_model_callouts(
        native.adapter, "ArborBoreProfile", spec.DIMENSION_CALLOUTS, **kwargs
    )


def verify_call(native, **kwargs):
    common.verify_dimension_callouts(
        native.adapter,
        (native.annotation,),
        spec.DIMENSION_CALLOUTS,
        feature_name="ArborBoreProfile",
        **kwargs,
    )


@pytest.mark.parametrize("location,slot", [("above", 3), ("below", 4)])
def test_native_void_author_writes_only_selected_field_with_exact_readback(
    native, location, slot
):
    before_dimension = vars(native.dimension).copy()
    before_fields = dict(native.fields)
    author_call(native, location=location)
    text = spec.DIMENSION_CALLOUTS["ArborBoreDia"]
    native.lookup.assert_called_once_with(native.adapter, "ArborBoreProfile")
    native.display.SetText.assert_called_once_with(slot, text)
    native.display.GetText.assert_called_once_with(slot)
    assert native.fields == {**before_fields, slot: text}
    assert vars(native.dimension) == before_dimension
    assert native.model.mock_calls == [call.GetType(), call.GraphicsRedraw2()]


@pytest.mark.parametrize("kind", [0, 2, 3, 6])
def test_author_rejects_every_non_part_before_resolving_or_writing(native, kind):
    native.model.GetType.return_value = kind
    with pytest.raises(RuntimeError, match="PART"):
        author_call(native)
    native.lookup.assert_not_called()
    native.display.SetText.assert_not_called()


def test_author_requires_current_document(native):
    native.adapter.currentModel = None
    with pytest.raises(RuntimeError, match="PART"):
        author_call(native)


@pytest.mark.parametrize(
    "damage", ["missing", "duplicate", "wrong_feature", "wrong_name", "hole"]
)
def test_author_uses_exact_existing_name_resolver_and_rejects_unsupported(
    native, damage
):
    if damage == "missing":
        native.feature.GetFirstDisplayDimension.return_value = None
    if damage == "duplicate":
        native.feature.GetNextDisplayDimension.side_effect = [native.display, None]
    if damage == "wrong_feature":
        native.dimension.FullName = "ArborBoreDia@OtherFeature@alignment-pinion.Part"
    if damage == "wrong_name":
        native.dimension.Name = "OtherBore"
    if damage == "hole":
        native.display.IsHoleCallout.return_value = True
    with pytest.raises(RuntimeError, match="exactly one|hole callouts"):
        author_call(native)
    native.display.SetText.assert_not_called()
    native.model.GraphicsRedraw2.assert_not_called()


@pytest.mark.parametrize("actual", [None, "THRU", "THRU - REAM\r\nPRESS FIT"])
def test_author_rejects_wrong_native_text_without_redraw(native, actual):
    native.display.GetText.side_effect = None
    native.display.GetText.return_value = actual
    with pytest.raises(RuntimeError, match="did not persist"):
        author_call(native)
    native.model.GraphicsRedraw2.assert_not_called()


@pytest.mark.parametrize("method", ["SetText", "GetText"])
def test_author_propagates_native_failure(native, method):
    failure = RuntimeError(f"native {method} failed")
    getattr(native.display, method).side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        author_call(native)
    assert raised.value is failure
    native.model.GraphicsRedraw2.assert_not_called()


@pytest.mark.parametrize("location,slot", [("above", 3), ("below", 4)])
def test_exact_empty_field_is_supported_without_coercing_null(native, location, slot):
    native.fields[slot] = "previous text"
    author.author_model_callouts(
        native.adapter, "ArborBoreProfile", {"ArborBoreDia": ""}, location=location
    )
    native.display.SetText.assert_called_once_with(slot, "")
    native.model.GetType.return_value = 3
    common.verify_dimension_callouts(
        native.adapter,
        [native.annotation],
        {"ArborBoreDia": ""},
        feature_name="ArborBoreProfile",
        location=location,
    )
    native.display.GetText.side_effect = None
    native.display.GetText.return_value = None
    with pytest.raises(RuntimeError, match="differs"):
        common.verify_dimension_callouts(
            native.adapter,
            [native.annotation],
            {"ArborBoreDia": ""},
            feature_name="ArborBoreProfile",
            location=location,
        )


@pytest.mark.parametrize("function", [author_call, verify_call])
def test_invalid_location_is_never_redirected_to_another_slot(native, function):
    with pytest.raises(KeyError, match="invalid"):
        function(native, location="invalid")
    native.display.SetText.assert_not_called()
    native.display.GetText.assert_not_called()


@pytest.mark.parametrize("location,slot", [("above", 3), ("below", 4)])
def test_drawing_verifies_exact_import_read_only(native, location, slot):
    native.model.GetType.return_value = 3
    native.fields[slot] = spec.DIMENSION_CALLOUTS["ArborBoreDia"]
    before_fields = dict(native.fields)
    before_dimension = vars(native.dimension).copy()
    verify_call(native, location=location)
    native.display.GetText.assert_called_once_with(slot)
    native.display.SetText.assert_not_called()
    native.model.GraphicsRedraw2.assert_not_called()
    assert native.model.mock_calls == [call.GetType()]
    assert native.fields == before_fields
    assert vars(native.dimension) == before_dimension


@pytest.mark.parametrize(
    "damage", ["text", "missing", "duplicate", "feature", "hole", "part"]
)
def test_drawing_rejects_incorrect_import_without_repair(native, damage):
    native.model.GetType.return_value = 3
    native.fields[4] = spec.DIMENSION_CALLOUTS["ArborBoreDia"]
    annotations = [native.annotation]
    if damage == "text":
        native.fields[4] = ""
    if damage == "missing":
        annotations = []
    if damage == "duplicate":
        annotations *= 2
    if damage == "feature":
        native.dimension.FullName = "ArborBoreDia@OtherFeature@alignment-pinion.Part"
    if damage == "hole":
        native.display.IsHoleCallout.return_value = True
    if damage == "part":
        native.model.GetType.return_value = 1
    with pytest.raises(
        RuntimeError, match="differs|exactly one|belong|hole callouts|DRAWING"
    ):
        common.verify_dimension_callouts(
            native.adapter,
            annotations,
            spec.DIMENSION_CALLOUTS,
            feature_name="ArborBoreProfile",
        )
    native.display.SetText.assert_not_called()
    native.model.GraphicsRedraw2.assert_not_called()


def test_drawing_getter_exception_is_not_silently_accepted(native):
    native.model.GetType.return_value = 3
    failure = RuntimeError("native GetText failed")
    native.display.GetText.side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        verify_call(native)
    assert raised.value is failure
    native.display.SetText.assert_not_called()


def test_drawing_missing_source_parameter_is_not_accepted(native):
    native.model.GetType.return_value = 3
    native.display.GetDimension2.return_value = None
    with pytest.raises(RuntimeError, match="no source parameter"):
        verify_call(native)
    native.display.SetText.assert_not_called()


def test_callout_author_is_an_alignment_only_part_input():
    helper = Path(author.__file__).resolve()
    consumers = {
        path.stem for path in part_scripts() if str(helper) in module_deps_of(path)
    }
    assert consumers == {"build_alignment_pinion"}
    assert str(Path(common.__file__).resolve()) not in module_deps_of(helper)

"""Finalization skips only an exactly equal scale, never the sheet readback."""

from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

import _common
import _drawing_common as common


@pytest.fixture
def native(monkeypatch, tmp_path):
    properties = [0, 0, 2.0, 1.0, 0, 0.4318, 0.2794, 0]
    sheet = Mock()
    sheet.GetProperties2.side_effect = lambda: list(properties)

    def set_scale(numerator, denominator, positions, text_height):
        properties[2:4] = [numerator, denominator]
        return True

    def set_properties(*values):
        properties[:] = values

    sheet.SetScale.side_effect = set_scale
    sheet.SetProperties2.side_effect = set_properties
    draw = Mock()
    draw.GetSheetNames.return_value = ("Sheet1",)
    draw.ActivateSheet.return_value = True
    draw.GetCurrentSheet.return_value = sheet
    linked_model = object()
    view = SimpleNamespace(ReferencedDocument=linked_model)

    def read_member(obj, name):
        value = getattr(obj, name)
        return value() if callable(value) else value

    adapter = SimpleNamespace(currentModel=draw, _get_attr_or_call=read_member)
    monkeypatch.setattr(common, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(
        common._sw_type_info, "early_bound_or_flag", lambda obj, *args: obj
    )
    monkeypatch.setattr(common, "iter_views", lambda adapter: iter((view,)))
    monkeypatch.setattr(common, "view_name", lambda adapter, view: "Front")
    monkeypatch.setattr(common, "read_required_properties", Mock())
    monkeypatch.setattr(_common, "apply_custom_properties", Mock())
    outputs = SimpleNamespace(
        slddrw=tmp_path / "drawing.SLDDRW",
        pdf=tmp_path / "drawing.pdf",
        png=tmp_path / "drawing.png",
    )
    save = Mock(return_value={"drawing": str(outputs.slddrw), "pdf": str(outputs.pdf)})
    monkeypatch.setattr(common, "save_drawing", save)
    monkeypatch.setattr(common, "sanitize_pdf_metadata", Mock())
    monkeypatch.setattr(common, "render_pdf_png", Mock())
    validate = Mock(wraps=common.assert_asme_b_sheet)
    monkeypatch.setattr(common, "assert_asme_b_sheet", validate)
    return SimpleNamespace(
        adapter=adapter,
        sheet=sheet,
        properties=properties,
        outputs=outputs,
        save=save,
        validate=validate,
    )


async def finalize(native):
    return await common.finalize_drawing(
        native.adapter, native.outputs, pdf_title="scale control", scale=(2, 1)
    )


@pytest.mark.asyncio
async def test_equal_scale_skips_setter_but_keeps_fresh_full_validation(native):
    assert set(await finalize(native)) == {"drawing", "pdf", "png"}
    native.sheet.SetScale.assert_not_called()
    native.sheet.SetProperties2.assert_not_called()
    assert native.sheet.mock_calls == [call.GetProperties2(), call.GetProperties2()]
    native.validate.assert_called_once_with(
        native.adapter, native.sheet, phase="before save Sheet1", scale=(2, 1)
    )
    native.save.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_scale", [(1.0, 1.0), (4.0, 2.0), (2.0000000001, 1.0)])
async def test_different_exact_pair_sets_native_args_then_reads_back(
    native, initial_scale
):
    native.properties[2:4] = initial_scale
    await finalize(native)
    assert native.sheet.mock_calls == [
        call.GetProperties2(),
        call.SetScale(2.0, 1.0, False, False),
        call.GetProperties2(),
        call.GetProperties2(),
    ]
    assert native.properties[2:4] == [2.0, 1.0]
    native.save.assert_called_once()


@pytest.mark.asyncio
async def test_rejected_scale_set_stops_before_validation_or_export(native):
    native.properties[2:4] = [1.0, 1.0]
    native.sheet.SetScale.side_effect = None
    native.sheet.SetScale.return_value = False
    with pytest.raises(RuntimeError, match="failed to set final drawing sheet"):
        await finalize(native)
    native.sheet.SetScale.assert_called_once_with(2.0, 1.0, False, False)
    native.validate.assert_not_called()
    native.save.assert_not_called()


@pytest.mark.asyncio
async def test_successful_set_with_wrong_scale_readback_fails(native):
    native.properties[2:4] = [1.0, 1.0]
    native.sheet.SetScale.side_effect = None
    native.sheet.SetScale.return_value = True
    with pytest.raises(RuntimeError, match="drawing sheet scale is not 2:1"):
        await finalize(native)
    native.sheet.SetScale.assert_called_once_with(2.0, 1.0, False, False)
    native.save.assert_not_called()


@pytest.mark.asyncio
async def test_scale_com_exception_propagates_without_export(native):
    native.properties[2:4] = [1.0, 1.0]
    failure = RuntimeError("native SetScale failure")
    native.sheet.SetScale.side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        await finalize(native)
    assert raised.value is failure
    native.validate.assert_not_called()
    native.save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("after", [None, [], [0, 0, 2, 1, 0, 0.4318, 0.2794]])
async def test_incomplete_post_setter_properties_fail_before_correction(native, after):
    native.properties[2:4] = [1.0, 1.0]
    native.properties[7] = 1
    native.sheet.GetProperties2.side_effect = [list(native.properties), after]
    with pytest.raises(RuntimeError, match="incomplete.*properties"):
        await finalize(native)
    native.sheet.SetScale.assert_called_once_with(2.0, 1.0, False, False)
    native.sheet.SetProperties2.assert_not_called()
    native.save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["scale", "size"])
async def test_equal_initial_pair_cannot_bypass_later_full_readback(native, change):
    before = list(native.properties)
    after = list(before)
    after[2 if change == "scale" else 5] = 3.0
    native.sheet.GetProperties2.side_effect = [before, after]
    with pytest.raises(RuntimeError, match="drawing sheet scale|ASME B size"):
        await finalize(native)
    native.sheet.SetScale.assert_not_called()
    native.save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "properties", [None, [], [0] * 3, [0, 0, 2, 1, 0, 0.4318, 0.2794]]
)
async def test_incomplete_initial_properties_fail_before_set_or_export(
    native, properties
):
    native.sheet.GetProperties2.side_effect = None
    native.sheet.GetProperties2.return_value = properties
    with pytest.raises(RuntimeError, match="incomplete.*properties"):
        await finalize(native)
    native.sheet.SetScale.assert_not_called()
    native.sheet.SetProperties2.assert_not_called()
    native.save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_scale", [(2.0, 1.0), (1.0, 1.0)])
async def test_same_custom_property_correction_uses_current_ratio(
    native, initial_scale
):
    native.properties[2:4] = initial_scale
    native.properties[7] = 1
    await finalize(native)
    native.sheet.SetProperties2.assert_called_once_with(
        0, 0, 2.0, 1.0, False, 0.4318, 0.2794, False
    )
    assert native.properties[2:4] == [2.0, 1.0]
    assert native.properties[7] is False
    assert native.validate.call_count == 2
    if initial_scale == (2.0, 1.0):
        native.sheet.SetScale.assert_not_called()
    if initial_scale != (2.0, 1.0):
        native.sheet.SetScale.assert_called_once_with(2.0, 1.0, False, False)


@pytest.mark.asyncio
async def test_same_custom_property_rejection_remains_loud(native):
    native.properties[7] = 1
    native.sheet.SetProperties2.side_effect = None
    with pytest.raises(RuntimeError, match="failed to enable explicit property source"):
        await finalize(native)
    native.save.assert_not_called()

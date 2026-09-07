"""Author persistent model callout fields before the part's normal final save.

This part-safe helper imports no drawing implementation. SetText is void; its
GetText readback, not a truthy return, witnesses the exact literal field. Saving
and cold-reopen/print acceptance belong to the caller's build and drawing gates.
"""

from enum import StrEnum
from typing import Any, Literal, Mapping

from _common import _early_bound
from _drawing_marks import _named_dimension
import _telemetry


class NumericVisibility(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"


def _dimension_presentation(display: Any) -> tuple[tuple[str, ...], NumericVisibility]:
    """Validate the native Boolean locally; transmit explicit visibility state."""
    display = _early_bound(display, "IDisplayDimension")
    visible = display.ShowDimensionValue
    if type(visible) is not bool:
        raise RuntimeError(f"unsupported native numeric visibility: {visible!r}")
    fields = tuple(display.GetText(part) for part in range(1, 9))
    if any(type(text) is not str for text in fields):
        raise RuntimeError(f"dimension has unsupported native text: {fields!r}")
    visibility = NumericVisibility.VISIBLE if visible else NumericVisibility.HIDDEN
    return fields, visibility


def _whole_text_presentation(text: str) -> tuple[tuple[str, ...], NumericVisibility]:
    """The complete documented SetText(All) result, including definition fields."""
    return (text, "", "", "", text, "", "", ""), NumericVisibility.HIDDEN


def _require_presentation(actual, expected, label: str) -> None:
    if actual[1] is not expected[1]:
        raise RuntimeError(f"{label}: native numeric visibility differs")
    if actual != expected:
        raise RuntimeError(f"{label}: presentation differs: {actual!r} != {expected!r}")


def _require_model_identity(
    adapter: Any, model: Any, expected: Any, actual: Any
) -> None:
    application = _early_bound(adapter.swApp, "ISldWorks")
    for left, right in (
        (model, adapter.currentModel),
        (model, application.ActiveDoc),
        (expected, actual),
    ):
        status = (
            application.IsSame(left, right)
            if left is not None and right is not None
            else None
        )
        if type(status) is not int or status != 1:
            raise RuntimeError(
                "model callout document/parameter identity differs or is unknown"
            )


@_telemetry.traced("dim.model_callouts", label_param="feature_name")
def author_model_callouts(
    adapter: Any,
    feature_name: str,
    callout_text: Mapping[str, str],
    *,
    location: Literal["above", "below", "prefix", "suffix", "all"] = "below",
) -> None:
    """Set one feature's exact named non-hole dimensions, without save/rebuild."""
    text_part = {"above": 3, "below": 4, "prefix": 1, "suffix": 2, "all": 0}[location]
    # Prefix/suffix retain a numeric value and every other compartment. Their
    # definition companions are checked too. All explicitly replaces the entire
    # text and hides the numeric value; it is not a prefix-only approximation.
    full_presentation = location in ("prefix", "suffix", "all")
    model = adapter.currentModel
    if model is None or _early_bound(model, "IModelDoc2").GetType() != 1:  # swDocPART
        raise RuntimeError("model dimension callouts require a PART document")
    if full_presentation:
        _require_model_identity(adapter, model, model, model)
    resolved = []
    for name, text in callout_text.items():
        if not isinstance(name, str) or not name or not isinstance(text, str):
            raise ValueError(
                "model callouts require nonempty dimension names and literal text"
            )
        display, dimension = _named_dimension(adapter, feature_name, name)
        display = _early_bound(display, "IDisplayDimension")
        if display.IsHoleCallout() is not False:
            raise RuntimeError(
                f"{name}@{feature_name}: SetText does not support hole callouts"
            )
        expected = None
        if full_presentation:
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
            before_fields, before_visible = _dimension_presentation(display)
            expected = _whole_text_presentation(text)
            if location != "all":
                if before_visible is not NumericVisibility.VISIBLE:
                    raise RuntimeError(
                        "reference dimension requires its native numeric value visible"
                    )
                fields = list(before_fields)
                fields[text_part - 1] = fields[text_part + 3] = text
                expected = tuple(fields), NumericVisibility.VISIBLE
        resolved.append((name, display, dimension, text, expected))
    for name, display, dimension, text, expected in resolved:
        if full_presentation:
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
        display.SetText(text_part, text)
        if full_presentation:
            actual = _dimension_presentation(display)
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
            _require_presentation(actual, expected, f"{name}@{feature_name}")
            continue
        actual = display.GetText(text_part)
        if actual != text:
            raise RuntimeError(
                f"{name}@{feature_name}: model {location} callout did not persist: "
                f"{actual!r} != {text!r}"
            )
    if resolved:
        if full_presentation:
            _require_model_identity(adapter, model, model, model)
        # SetText documents this display refresh. It does not rebuild or save.
        _early_bound(model, "IModelDoc2").GraphicsRedraw2()
    if full_presentation:
        for name, display, dimension, _text, expected in resolved:
            actual = _dimension_presentation(display)
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
            _require_presentation(
                actual, expected, f"{name}@{feature_name} after redraw"
            )

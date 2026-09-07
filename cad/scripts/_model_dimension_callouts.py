"""Author persistent model callout fields before the part's normal final save.

This part-safe helper imports no drawing implementation. SetText is void; its
GetText readback, not a truthy return, witnesses the exact literal field. Saving
and cold-reopen/print acceptance belong to the caller's build and drawing gates.
"""

from typing import Any, Literal, Mapping

from _common import _early_bound
from _drawing_marks import _named_dimension
import _telemetry


def _reference_presentation(display: Any) -> tuple[str, ...]:
    """Read all native text/definition fields of a numeric reference dimension."""
    display = _early_bound(display, "IDisplayDimension")
    if display.ShowDimensionValue is not True:
        raise RuntimeError(
            "reference dimension requires its native numeric value visible"
        )
    fields = tuple(display.GetText(part) for part in range(1, 9))
    if any(type(text) is not str for text in fields):
        raise RuntimeError(
            f"reference dimension has unsupported native text: {fields!r}"
        )
    return fields


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
                "model reference callout document/parameter identity differs or is unknown"
            )


@_telemetry.traced("dim.model_callouts", label_param="feature_name")
def author_model_callouts(
    adapter: Any,
    feature_name: str,
    callout_text: Mapping[str, str],
    *,
    location: Literal["above", "below", "prefix", "suffix"] = "below",
) -> None:
    """Set one feature's exact named non-hole dimensions, without save/rebuild."""
    text_part = {"above": 3, "below": 4, "prefix": 1, "suffix": 2}[location]
    # Prefix/suffix retain a numeric value and every other compartment. Their
    # definition companions are checked too; these are literal fields, not All.
    reference_field = location in ("prefix", "suffix")
    model = adapter.currentModel
    if model is None or _early_bound(model, "IModelDoc2").GetType() != 1:  # swDocPART
        raise RuntimeError("model dimension callouts require a PART document")
    if reference_field:
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
        if reference_field:
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
            fields = list(_reference_presentation(display))
            fields[text_part - 1] = fields[text_part + 3] = text
            expected = tuple(fields)
        resolved.append((name, display, dimension, text, expected))
    for name, display, dimension, text, expected in resolved:
        if reference_field:
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
        display.SetText(text_part, text)
        if reference_field:
            actual = _reference_presentation(display)
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
            if actual != expected:
                raise RuntimeError(
                    f"{name}@{feature_name}: reference presentation differs: "
                    f"{actual!r} != {expected!r}"
                )
            continue
        actual = display.GetText(text_part)
        if actual != text:
            raise RuntimeError(
                f"{name}@{feature_name}: model {location} callout did not persist: "
                f"{actual!r} != {text!r}"
            )
    if resolved:
        if reference_field:
            _require_model_identity(adapter, model, model, model)
        # SetText documents this display refresh. It does not rebuild or save.
        _early_bound(model, "IModelDoc2").GraphicsRedraw2()
    if reference_field:
        for name, display, dimension, _text, expected in resolved:
            actual = _reference_presentation(display)
            _require_model_identity(adapter, model, dimension, display.GetDimension2(0))
            if actual != expected:
                raise RuntimeError(
                    f"{name}@{feature_name}: reference presentation changed after redraw: "
                    f"{actual!r} != {expected!r}"
                )

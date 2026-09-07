"""Author persistent model callout fields before the part's normal final save.

This part-safe helper imports no drawing implementation. SetText is void; its
GetText readback, not a truthy return, witnesses the exact literal field. Saving
and cold-reopen/print acceptance belong to the caller's build and drawing gates.
"""

from typing import Any, Literal, Mapping

from _common import _early_bound
from _drawing_marks import _named_dimension
import _telemetry


@_telemetry.traced("dim.model_callouts", label_param="feature_name")
def author_model_callouts(
    adapter: Any,
    feature_name: str,
    callout_text: Mapping[str, str],
    *,
    location: Literal["above", "below"] = "below",
) -> None:
    """Set one feature's exact named non-hole dimensions, without save/rebuild."""
    text_part = {"above": 3, "below": 4}[location]  # swDimensionTextParts_e
    model = adapter.currentModel
    if model is None or _early_bound(model, "IModelDoc2").GetType() != 1:  # swDocPART
        raise RuntimeError("model dimension callouts require a PART document")
    resolved = []
    for name, text in callout_text.items():
        if not isinstance(name, str) or not name or not isinstance(text, str):
            raise ValueError(
                "model callouts require nonempty dimension names and literal text"
            )
        display, _dimension = _named_dimension(adapter, feature_name, name)
        display = _early_bound(display, "IDisplayDimension")
        if display.IsHoleCallout() is not False:
            raise RuntimeError(
                f"{name}@{feature_name}: SetText does not support hole callouts"
            )
        resolved.append((name, display, text))
    for name, display, text in resolved:
        display.SetText(text_part, text)
        actual = display.GetText(text_part)
        if actual != text:
            raise RuntimeError(
                f"{name}@{feature_name}: model {location} callout did not persist: "
                f"{actual!r} != {text!r}"
            )
    if resolved:
        # SetText documents this display refresh. It does not rebuild or save.
        _early_bound(model, "IModelDoc2").GraphicsRedraw2()

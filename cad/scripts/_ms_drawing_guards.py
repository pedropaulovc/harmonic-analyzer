"""Native text and hole-callout formatting for the measuring-stick stop drawings
(MHA-MS-02, MHA-MS-03).

The drawings author no presentation on imported dimensions: the parts write
their own callout rows and quantity prefixes (#1942), which a drawing only
reads back here, with the text parts and row normalizer the part builds use
(``ms_stop_callouts``).  The clean-source guard is ``_drawing_source_guard``.
New drawing-owned Hole Wizard callouts instead require per-variable length
precision: source display precision does not determine their printed digits.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

import _telemetry
from _com import _early_bound
from ms_stop_callouts import CALLOUT_BELOW, PREFIX_DEFINITION, callout_rows
from _drawing_hole_callout import set_hole_callout_precision
import ms_stop_spec as spec
from solidworks_mcp.adapters.solidworks.drawing import dimension_name


@_telemetry.traced("drawing.ms_imported_text")
def assert_imported_text(
    adapter: Any,
    annotations: Iterable[Any],
    below: Mapping[str, str],
    prefixes: Mapping[str, str] | None = None,
) -> None:
    """Every named imported dimension prints the callout rows and quantity
    prefix its PART authored; the drawing never writes them."""
    prefixes = prefixes or {}
    seen: set[str] = set()
    wrong: dict[str, str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in below and name not in prefixes:
            continue
        seen.add(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if name in below:
            printed = str(display.GetText(CALLOUT_BELOW) or "")
            if callout_rows(printed) != callout_rows(below[name]):
                wrong[name] = printed
        if name in prefixes:
            definition = str(display.GetText(PREFIX_DEFINITION) or "")
            if not definition.startswith(prefixes[name]):
                wrong[f"{name} prefix"] = definition
    missing = sorted({*below, *prefixes} - seen)
    if missing:
        raise RuntimeError(f"imported dimensions missing from the sheet: {missing}")
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


@_telemetry.traced("drawing.ms_hole_precision", label_param="label")
def set_stop_hole_callout_precision(display: Any, *, label: str) -> Callable[[], None]:
    """Format native stop hole lengths at .XXX and return a settled readback.

    ``GetPrimaryPrecision3`` describes the display, not the rendered Hole
    Wizard variables. Use the documented ``ICalloutLengthVariable.Precision``
    for every length (drill diameter and any depths); leave angle/string
    variables, their native identities/names, raw values and all definition
    tokens untouched. Metadata uses the existing helper's dynamic dispatch
    pattern, then the concrete length/angle/string interface owns its value.
    The returned check reacquires the inventory after final rebuilding.
    """
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    display = _early_bound(display, "IDisplayDimension")
    if not display.IsHoleCallout():
        raise RuntimeError(f"{label}: stop drill is not a native hole callout")

    def definitions() -> tuple[str, ...]:
        return tuple(str(display.GetText(part) or "") for part in (5, 6, 7, 8))

    def inventory() -> tuple[dict[str, tuple[int, float | str]], dict[str, int]]:
        values: dict[str, tuple[int, float | str]] = {}
        places: dict[str, int] = {}
        for raw in display.GetHoleCalloutVariables() or ():
            metadata = dynamic_dispatch(raw._oleobj_)
            name, kind = str(metadata.VariableName), int(metadata.Type)
            if name in values:
                raise RuntimeError(f"{label}: duplicate native callout variable {name!r}")
            if kind == 1:  # swCalloutVariableType_Length
                length = _early_bound(raw, "ICalloutLengthVariable")
                value = float(length.Length)
                places[name] = int(length.Precision)
            elif kind == 2:  # swCalloutVariableType_Angle
                value = float(_early_bound(raw, "ICalloutAngleVariable").Angle)
            elif kind == 3:  # swCalloutVariableType_String
                value = str(_early_bound(raw, "ICalloutStringVariable").String)
            else:
                raise RuntimeError(f"{label}: unknown native variable type {kind} for {name}")
            values[name] = (kind, value)
        return values, places

    original_definitions = definitions()
    original_values, original_places = inventory()
    drill_names = set(original_places) & {"hw-diam", "hw-tapdrldia", "hw-thrutapdrldia"}
    if len(drill_names) != 1:
        raise RuntimeError(f"{label}: expected one native drill variable, got {sorted(drill_names)}")
    drill_name = next(iter(drill_names))
    if f"<{drill_name}>" not in "\n".join(original_definitions):
        raise RuntimeError(f"{label}: native drill token {drill_name} is absent from definitions")
    expected_places = dict.fromkeys(original_places, spec.HOLE_CALLOUT_PRECISION)
    set_hole_callout_precision(display, expected_places, label=label)

    def assert_precision() -> None:
        actual_values, actual_places = inventory()
        actual_definitions = definitions()
        if actual_values != original_values or actual_definitions != original_definitions:
            raise RuntimeError(
                f"{label}: native callout definitions/variables changed during precision: "
                f"expected={original_values!r}, actual={actual_values!r}, "
                f"expected_definitions={original_definitions!r}, "
                f"actual_definitions={actual_definitions!r}"
            )
        if actual_places != expected_places:
            raise RuntimeError(
                f"{label}: native length precision differs: "
                f"expected={expected_places!r}, actual={actual_places!r}"
            )

    assert_precision()
    return assert_precision

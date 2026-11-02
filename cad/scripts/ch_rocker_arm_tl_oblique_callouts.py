"""Three-place Hole Wizard callouts on the inch jig sheets (#290).

A THRU tap's callout does not carry the blind tap's ``hw-tapdrldia``
(farm run 20261031T200222206Z: "hole callout has no native variables"), so
the sheets set every native length variable the callout does carry instead of
naming them.
"""

from __future__ import annotations

from typing import Any

from _drawing_hole_callout import set_hole_callout_precision

CALLOUT_PLACES = 3  # every Hole Wizard length prints .XXX on an inch sheet

_LENGTH_VARIABLE = 1  # swCalloutVariableType_Length


def set_callout_lengths_to_three_places(display: Any, *, label: str) -> None:
    """Print every native length on ``display``'s hole callout at .XXX."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch  # noqa: PLC0415

    variables = [
        dynamic_dispatch(raw._oleobj_)
        for raw in display.GetHoleCalloutVariables() or ()
    ]
    lengths = {
        str(variable.VariableName)
        for variable in variables
        if int(variable.Type) == _LENGTH_VARIABLE
    }
    if not lengths:
        names = sorted(f"{v.VariableName}:{int(v.Type)}" for v in variables)
        raise RuntimeError(
            f"{label}: hole callout has no native length variable: {names}"
        )
    set_hole_callout_precision(
        display, dict.fromkeys(lengths, CALLOUT_PLACES), label=label
    )

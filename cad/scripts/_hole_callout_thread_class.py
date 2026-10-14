"""Drop the Hole Wizard thread-class token from a native tap callout.

The title block's THREADS row owns the general thread class (drawing-guidelines.md
rule 2), so a tap callout reads ``TAP 4-40 UNC THRU``, not ``TAP 4-40 UNC - 2B
THRU``. Only the ``<hw-threadclass>`` variable (and its leading dash) leaves the
callout's definition; the thread, drill and depth variables stay live.
"""

from __future__ import annotations

from typing import Any

from _com import _early_bound

_TOKEN = "<hw-threadclass>"


def omit_title_block_thread_class(display: Any, *, label: str) -> None:
    """Remove the one thread-class variable from a native hole callout."""
    native = _early_bound(display, "IDisplayDimension")
    if not native.IsHoleCallout():
        raise RuntimeError(f"{label}: thread-class removal needs a native hole callout")
    definition = str(native.GetText(5) or "")  # swDimensionTextPrefixDefinition
    if definition.count(_TOKEN) != 1:
        raise RuntimeError(
            f"{label}: tap callout lacks one thread-class variable: {definition!r}"
        )
    before, _token, after = definition.partition(_TOKEN)
    before = before.rstrip(" \t")
    if before.endswith("-"):
        before = before[:-1].rstrip(" \t")
    revised = before + after
    native.SetText(1, revised)  # swDimensionTextPrefix; void return
    if str(native.GetText(5) or "") != revised:
        raise RuntimeError(f"{label}: tap callout kept its thread class")

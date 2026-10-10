"""Custom-property writes shared by parts and assemblies.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

from _check import log
from _com import _early_bound, _read_member

_SW_CUSTOM_TEXT = 30  # swCustomInfoType_e.swCustomInfoText


_SW_PROP_REPLACE = 2  # swCustomPropertyAddOption_e.swCustomPropertyReplaceValue


def apply_custom_properties(
    adapter: Any, props: dict[str, str], *, model: Any | None = None
) -> None:
    """Write file-level custom properties via the CustomPropertyManager, verified.

    The PyWin32 adapter exposes no property writer, so this drives raw COM
    (``IModelDocExtension.CustomPropertyManager("").Add3`` with replace), then
    reads each value back through ``GetCustomInfoValue`` and raises on mismatch
    — same fail-fast posture as the build's other gates. Empty values are skipped.
    ``model`` defaults to the active document; callers that repair a specific
    assembly may pass the explicit target document.
    """
    model = adapter.currentModel if model is None else model
    ext = _read_member(model, "Extension")
    mgr = adapter._attempt(lambda: ext.CustomPropertyManager(""), default=None)
    if mgr is None:
        raise RuntimeError("CustomPropertyManager unavailable")
    mgr = _early_bound(mgr, "ICustomPropertyManager")
    written = []
    for name, value in props.items():
        if value in (None, ""):
            continue
        text = str(value)
        adapter._attempt(
            lambda n=name, v=text: mgr.Add3(n, _SW_CUSTOM_TEXT, v, _SW_PROP_REPLACE),
            default=None,
        )
        back = str(
            adapter._attempt(lambda n=name: model.GetCustomInfoValue("", n), default="")
        )
        if back != text:
            raise RuntimeError(
                f"custom property {name!r} readback {back!r} != {text!r}"
            )
        written.append(name)
    log(f"custom properties [{len(written)}]: {', '.join(written)}")

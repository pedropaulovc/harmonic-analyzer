r"""Label a fastener side view's schematic shank diameter with its thread.

The made screws model the thread as a plain cylinder at the minor diameter
(THREAD NOT MODELED), so the marked shank diameter inserted into the profile
view must not read as a turned size.  ``draw_fillister_screw`` swaps the
value for the catalog designation with ``set_dimension_text``; the
recipe-based sheets (``_fastener_drawing.FastenerSheet``) only hand their
``decorate`` hook the VIEW, so this helper re-reads the view's display
dimensions and applies the same swap, failing loud if a named dimension never
reached the view.
"""

from __future__ import annotations

from typing import Any, Mapping

import _telemetry
from _common import _early_bound
from _drawing_common import set_dimension_text
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.solidworks.drawing import dimension_name


def view_dimension_annotations(adapter: Any, view: Any) -> list[Any]:
    """Every display dimension currently on ``view``, as IAnnotation dispatches."""
    drawing_view = _early_bound(view, "IView")
    displays = drawing_view.GetDisplayDimensions() or []
    annotations: list[Any] = []
    for display in displays:
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "GetAnnotation"
        )
        annotation = display.GetAnnotation()
        if annotation is None:
            raise RuntimeError("a view display dimension has no annotation")
        annotations.append(
            _sw_type_info.early_bound_or_flag(
                annotation, "IAnnotation", "GetSpecificAnnotation"
            )
        )
    return annotations


@_telemetry.traced("drawing.shank_thread_text", label_param="view_label")
def label_shank_thread(
    adapter: Any,
    view: Any,
    *,
    dimensions: Mapping[str, str],
    view_label: str,
) -> None:
    """Replace the displayed text of the named dimensions on ``view``.

    ``dimensions`` maps a parametric dimension name (the marked shank
    diameter) to the text that replaces its value (the thread designation).
    A name absent from the view is an error: ``set_dimension_text`` itself
    skips unknown names silently, and a bare minor-diameter value left on the
    sheet is exactly the misleading print this helper exists to prevent.
    """
    annotations = view_dimension_annotations(adapter, view)
    present = {dimension_name(adapter, annotation) for annotation in annotations}
    missing = sorted(set(dimensions) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing dimensions {missing} for thread text; "
            f"available={sorted(name for name in present if name)}"
        )
    set_dimension_text(adapter, annotations, dict(dimensions))

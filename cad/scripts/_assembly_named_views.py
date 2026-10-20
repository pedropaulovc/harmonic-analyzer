"""Assembly inspection views captured before rebasing or rigidly turning a model.

Only assembly builders that need preserved drawing projections opt into this
mutable helper; the shared octant definitions stay in ``_named_views``.
"""

from __future__ import annotations

from typing import Any

import _telemetry
from _com import _early_bound
from _named_views import (
    Axis,
    _close,
    _CONVENTION_TOLERANCE,
    _SW_ISOMETRIC_VIEW,
    _transpose,
    octant_rotation,
)
from solidworks_mcp.adapters.com_variant import double_array


@_telemetry.traced("assembly.named_views", label_param="label")
def name_standard_views(
    adapter: Any,
    *,
    views: dict[str, int],
    label: str,
    model_rotation: tuple[Axis, Axis, Axis] | None = None,
) -> None:
    """Name exact standard projections, optionally following a rigid model turn.

    ``model_rotation`` contains the images of the old model axes in the new
    model frame (the component-placement row convention). Applying the same
    turn to the camera preserves the original drawing projection. Without a
    turn, capture the native view directly, including SolidWorks' slight
    deviation from an analytic isometric. Read back every stored rotation.

    Call before rebasing standard views; leaves the last named view active.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    transposed = False
    if model_rotation is not None:
        isometric = tuple(
            float(value) for value in model.GetStandardViewRotation(_SW_ISOMETRIC_VIEW)
        )
        row_form = octant_rotation(1, 1, 1)
        if _close(isometric, row_form, _CONVENTION_TOLERANCE):
            transposed = False
        elif _close(isometric, _transpose(row_form), _CONVENTION_TOLERANCE):
            transposed = True
        else:
            raise RuntimeError(f"{label}: unknown standard-view matrix convention {isometric}")
        utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
        view = _early_bound(model.ActiveView, "IModelView")
    for name, view_id in views.items():
        rotation = tuple(float(value) for value in (model.GetStandardViewRotation(view_id) or ()))
        if len(rotation) != 9:
            raise RuntimeError(f"{label}: standard view {view_id} has invalid rotation {rotation}")
        model.ShowNamedView2("", view_id)
        if model_rotation is not None:
            axes = _transpose(rotation) if transposed else rotation
            turned = tuple(
                sum(axes[3 * row + axis] * model_rotation[axis][column] for axis in range(3))
                for row in range(3)
                for column in range(3)
            )
            rotation = _transpose(turned) if transposed else turned
            transform = utility.CreateTransform(
                double_array([*rotation, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
            )
            if transform is None:
                raise RuntimeError(f"{label}: CreateTransform refused the {name!r} rotation")
            view.Orientation3 = transform
        model.NameView(name)
        readback = tuple(float(value) for value in (extension.GetNamedViewRotation(name) or ()))
        if not _close(readback, rotation):
            raise RuntimeError(
                f"{label}: named view {name!r} read back {readback}, expected {rotation}"
            )

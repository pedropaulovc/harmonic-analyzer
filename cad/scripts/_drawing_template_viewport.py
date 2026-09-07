"""Exact native viewport capture/restore for drawing-template measurements.

Scale2 alone changes pan on the measured SW2026 seat. Restore the original
native Translation3 vector after scale, never a guessed screen/sheet position.
This does not set orientation or relax a template/defaults comparison.
"""

import math

from _common import _early_bound
from solidworks_mcp.adapters.com_variant import double_array


def capture(model):
    # INote.GetExtent explicitly is invalid for invisible documents.
    if not bool(model.Visible):
        raise RuntimeError("viewport measurement requires a visible drawing")
    view = _early_bound(model.ActiveView, "IModelView")
    scale = view.Scale2
    transform = tuple(view.Transform.ArrayData)
    translation = tuple(_early_bound(view.Translation3, "IMathVector").ArrayData)
    orientation = tuple(_early_bound(view.Orientation3, "IMathTransform").ArrayData)
    pixels = tuple(view.GetVisibleBox())
    if (
        type(scale) not in (int, float)
        or not math.isfinite(scale)
        or scale <= 0
        or len(transform) != 16
        or len(translation) != 3
        or len(orientation) != 16
        or any(
            type(x) not in (int, float) or not math.isfinite(x)
            for x in (*transform, *translation, *orientation)
        )
        or len(pixels) != 4
        or any(type(x) is not int for x in pixels)
        or pixels[0] >= pixels[2]
        or pixels[1] >= pixels[3]
    ):
        raise RuntimeError("invalid native viewport scale/transform/pixel box")
    return {
        "scale2": scale,
        "transform": list(transform),
        "translation3": list(translation),
        "orientation3": list(orientation),
        "visible_box_pixels": list(pixels),
        "document_visibility": "visible",
    }


def assign_translation(app, view, values):
    """One fresh native three-double MathVector; no scale/orientation setter."""
    utility = app.GetMathUtility()
    if utility is None:
        raise RuntimeError("native GetMathUtility returned null")
    vector = _early_bound(utility, "IMathUtility").CreateVector(double_array(values))
    if vector is None:
        raise RuntimeError("native CreateVector returned null")
    vector = _early_bound(vector, "IMathVector")
    if list(vector.ArrayData) != values:
        raise RuntimeError("fresh native translation vector differs")
    view.Translation3 = vector


def _active(app, model):
    if int(model.GetType()) != 3 or int(app.IsSame(model, app.ActiveDoc)) != 1:
        raise RuntimeError("viewport restore requires the exact active drawing")


def restore(app, model, target, observation):
    """Record native evidence even on refusal; exact full viewport is required."""
    observation.update(target=target, status="running")
    try:
        model = _early_bound(model, "IModelDoc2")
        _active(app, model)
        observation["before"] = capture(model)
        if observation["before"]["orientation3"] != target["orientation3"]:
            raise RuntimeError(
                "new drawing viewport orientation differs; no orientation setter is authorized"
            )
        if observation["before"]["visible_box_pixels"] != target["visible_box_pixels"]:
            raise RuntimeError(
                "new drawing visible pixel box differs; no window resize is authorized"
            )
        view = _early_bound(model.ActiveView, "IModelView")
        view.Scale2 = target["scale2"]
        observation["after_scale"] = capture(model)
        if observation["after_scale"]["orientation3"] != target["orientation3"]:
            raise RuntimeError("native Scale2 changed the viewport orientation")
        assign_translation(app, view, target["translation3"])
        model.GraphicsRedraw2()
        observation["after"] = capture(model)
        _active(app, model)
        if int(app.IsSame(view, model.ActiveView)) != 1:
            raise RuntimeError("native viewport handle changed during restore")
        if observation["after"] != target:
            raise RuntimeError(
                "native full viewport readback differs from captured target"
            )
        observation["status"] = "passed"
    except Exception as error:
        observation.update(status="failed", error=repr(error))
        raise

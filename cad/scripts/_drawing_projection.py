"""Model-space to drawing-view projection.

Geometry-based annotations project model points through views here, separately
from entity selection and dimension import.
"""

from __future__ import annotations

from typing import Any, Sequence

from solidworks_mcp.adapters.com_variant import double_array

from _com import _com_invoke
import _telemetry


def _projection_frame(
    adapter: Any, view: Any, *, observed: dict[str, Any] | None = None
) -> tuple[Any, Any]:
    """The math utility and the view's CURRENT model-to-sheet transform, raw.

    Raw dispatches (``_com._com_invoke``): the generated wrapper would read
    type info and ``QueryInterface`` every object these calls return, which
    is most of what one projection used to cost (p50 71 ms, n=22,839 in 30 d)
    for five round trips of real work.  SolidWorks still does the product, so
    a projected point is the same number it always was.
    """
    utility = _com_invoke(adapter.swApp, "ISldWorks", "GetMathUtility")
    transform = _com_invoke(view, "IView", "ModelToViewTransform")
    if observed is not None:
        # Retain the object already fetched, without another native read.
        # Its ArrayData is deliberately NOT sampled here; copy/live semantics
        # of a deferred read are undocumented.
        observed["model_to_view_transform_handle"] = transform
    return utility, transform


def _project_through(
    utility: Any, transform: Any, xyz: Sequence[float], *, label: str
) -> tuple[float, float]:
    model_point = _com_invoke(
        utility, "IMathUtility", "CreatePoint", double_array([float(v) for v in xyz])
    )
    if model_point is None:
        raise RuntimeError(f"failed to create model point ({label})")
    view_point = _com_invoke(model_point, "IMathPoint", "MultiplyTransform", transform)
    if view_point is None:
        raise RuntimeError(f"failed to project model point into view ({label})")
    coordinates = list(_com_invoke(view_point, "IMathPoint", "ArrayData") or ())
    if len(coordinates) < 2:
        raise RuntimeError(f"projected model point has no sheet coordinates ({label})")
    return (float(coordinates[0]), float(coordinates[1]))


@_telemetry.traced("drawing.model_point_projection", label_param="label")
def model_point_in_view(
    adapter: Any,
    view: Any,
    xyz: tuple[float, float, float],
    *,
    label: str,
) -> tuple[float, float]:
    """Project a model-space point into drawing-sheet coordinates.

    Five raw round trips.  A loop over one view's points projects through
    :func:`model_points_in_view` instead: one transform read and one span for
    the whole batch rather than one per point (up to 422 per trace).
    """
    utility, transform = _projection_frame(adapter, view)
    return _project_through(utility, transform, xyz, label=label)


@_telemetry.traced("drawing.model_point_projection", label_param="label")
def model_points_in_view(
    adapter: Any,
    view: Any,
    points: Sequence[Sequence[float]],
    *,
    label: str,
    names: Sequence[str] | None = None,
    observed: dict[str, Any] | None = None,
) -> list[tuple[float, float]]:
    """:func:`model_point_in_view` for many points of one view at one moment.

    The transform is read once, so nothing may move ``view`` between the
    points; three round trips per point after that.  ``names`` (one per
    point) identify a failing point in the error; its index, model point and
    the count projected before it are raised and set on the span either way.
    """
    if names is not None and len(names) != len(points):
        raise ValueError(f"{label}: {len(names)} names for {len(points)} points")
    _telemetry.annotate(points=len(points))
    utility, transform = (
        _projection_frame(adapter, view)
        if observed is None
        else _projection_frame(adapter, view, observed=observed)
    )
    projected: list[tuple[float, float]] = []
    for index, xyz in enumerate(points):
        try:
            projected.append(_project_through(utility, transform, xyz, label=label))
        except Exception as exc:
            model = tuple(float(v) for v in xyz)
            point = names[index] if names is not None else f"point {index}"
            _telemetry.annotate(
                failed_index=index, failed_point=point, projected=len(projected)
            )
            raise RuntimeError(
                f"{label}: {point} (index {index} of {len(points)}) at model"
                f" {model} failed after {len(projected)} projected: {exc}"
            ) from exc
    _telemetry.annotate(projected=len(projected))
    return projected

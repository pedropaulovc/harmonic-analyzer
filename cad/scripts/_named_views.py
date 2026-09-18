"""Octant pictorial views: named on the part, placed on the print by name.

SolidWorks ships ONE pictorial orientation, ``*Isometric``: the viewer stands
in the +X+Y+Z octant and sees the Front, Top and Right faces. A print that
needs to prime its reader from the other side -- a feature on a -Z face, an
underside gusset -- has no built-in view for it. The standard practice is a
NAMED VIEW on the part (View Orientation > New View in the UI; ``NameView``
over COM), which a drawing then places exactly like ``*Front`` with
``CreateDrawViewFromModelView3``.

This module is the one place the eight octant views are defined:

* :data:`OCTANTS` -- the eight viewer octants, keyed by the ASME face names
  they show (``"FRONT-TOP-LEFT"``), in Front/Rear, Top/Bottom, Right/Left
  order. ``OCTANT_VIEW_NAMES`` are the model-view names, ``ISO FRONT-TOP-LEFT``.
* :func:`octant_axes` -- the pure geometry: the view's X/Y/Z axes in model
  coordinates for one octant, model +Y kept "up" on the sheet, which is what
  makes each of them an isometric rather than an arbitrary tilt. Offline
  testable; ``octant_axes(1, 1, 1)`` reproduces the built-in ``*Isometric``.
* :func:`name_octant_views` -- the COM entry point a PART BUILD calls before
  it saves: composes each orientation through ``IModelView::Orientation3``,
  names it, and reads it back through ``GetNamedViewRotation`` -- all nine
  values, not the diagonal (a transposed matrix shares its diagonal).

**Opt-in per part build, on purpose.** Calling this from
``_common.save_part_and_images`` would fold it into every part's recipe
closure and rebuild the whole fleet for a view most prints never place. A
part whose drawing wants an octant view imports this module and calls
:func:`name_octant_views` itself; that part rebuilds, nothing else does.

Two SolidWorks facts this rests on, both measured (PR #737, 2026-09-11):
``IModelView::RotateAboutAxis`` is display-only and ``NameView`` does NOT
persist it -- the view had to be composed through ``Orientation3``; and the
matrix convention (whether a row is a view axis in model coordinates or the
transpose) is not documented, so it is READ off ``GetStandardViewRotation``
for ``*Isometric`` at run time and every octant is built in whichever
convention reproduces the built-in view. A mismatch fails the part build.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _common import _early_bound
from solidworks_mcp.adapters.com_variant import double_array

Axis = tuple[float, float, float]
Octant = tuple[int, int, int]

# Indexed by model axis (x, y, z); each pair is (negative face, positive face).
_FACE_NAMES = (("LEFT", "RIGHT"), ("BOTTOM", "TOP"), ("REAR", "FRONT"))
# swStandardViews_e.swIsometricView, the positive control for the convention.
_SW_ISOMETRIC_VIEW = 7
_TOLERANCE = 1e-6
_CONVENTION_TOLERANCE = 1e-3


def octant_key(sx: int, sy: int, sz: int) -> str:
    """``"FRONT-TOP-LEFT"`` for the viewer octant ``(sx, sy, sz)``.

    SolidWorks axes: Right = +X, Top = +Y, Front = +Z. ASME face order
    (Front/Rear, Top/Bottom, Right/Left) so the name reads like the print.
    """
    if any(sign not in (-1, 1) for sign in (sx, sy, sz)):
        raise ValueError(f"an octant is three signs, got {(sx, sy, sz)!r}")
    return "-".join(
        _FACE_NAMES[axis][sign > 0]
        for axis, sign in ((2, sz), (1, sy), (0, sx))
    )


def octant_view_name(sx: int, sy: int, sz: int) -> str:
    """The model-view name a drawing passes to ``CreateDrawViewFromModelView3``."""
    return f"ISO {octant_key(sx, sy, sz)}"


OCTANTS: dict[str, Octant] = {
    octant_key(sx, sy, sz): (sx, sy, sz)
    for sz in (1, -1)
    for sy in (1, -1)
    for sx in (1, -1)
}
OCTANT_VIEW_NAMES: dict[str, str] = {
    key: octant_view_name(*octant) for key, octant in OCTANTS.items()
}


def _normalize(vector: Axis) -> Axis:
    length = math.sqrt(sum(value * value for value in vector))
    if length < 1e-12:
        raise ValueError("degenerate axis")
    return tuple(value / length for value in vector)


def _cross(a: Axis, b: Axis) -> Axis:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def octant_axes(sx: int, sy: int, sz: int) -> tuple[Axis, Axis, Axis]:
    """The view's ``(x, y, z)`` axes in model coordinates for one octant.

    ``z`` points at the viewer, ``(sx, sy, sz)/sqrt(3)``; ``y`` is model +Y
    with its component along ``z`` removed, so "up" on the sheet is the part's
    up in every octant (bottom octants look up from below, they do not turn
    the part over); ``x = y cross z`` closes a right-handed frame.
    """
    octant_key(sx, sy, sz)  # validates the signs
    z = _normalize((float(sx), float(sy), float(sz)))
    up = (0.0, 1.0, 0.0)
    y = _normalize(tuple(u - z[1] * zi for u, zi in zip(up, z)))
    x = _cross(y, z)
    return x, y, z


def octant_rotation(sx: int, sy: int, sz: int) -> tuple[float, ...]:
    """The nine-value rotation with each view axis as a ROW (x, then y, then z)."""
    return tuple(value for axis in octant_axes(sx, sy, sz) for value in axis)


def _transpose(rotation: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(rotation[column + 3 * row] for column in range(3) for row in range(3))


def _close(a: tuple[float, ...], b: tuple[float, ...], tolerance: float = _TOLERANCE) -> bool:
    return len(a) == len(b) and max(abs(x - y) for x, y in zip(a, b)) <= tolerance


@_telemetry.traced("part.named_views", label_param="label")
def name_octant_views(
    adapter: Any, *, octants: dict[str, Octant] | None = None, label: str
) -> dict[str, str]:
    """Create and prove the octant named views on the open part.

    Returns ``{octant key: view name}`` for what was named. Every view is
    read back with ``GetNamedViewRotation`` against the matrix it was built
    from; the convention is taken from the built-in ``*Isometric`` first, so
    the part build fails loud on a SolidWorks that stores the transpose.
    """
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    # Positive control: the built-in isometric is octant (+1, +1, +1). It is
    # matched loosely (1e-3): SolidWorks' own *Isometric is not exact -- it
    # reads 0.57738 where 1/sqrt(3) is 0.57735 (measured 2026-09-16) -- and
    # the control only decides the convention, never a view's numbers. Our
    # own views are read back at _TOLERANCE below.
    isometric = tuple(float(value) for value in model.GetStandardViewRotation(_SW_ISOMETRIC_VIEW))
    row_form = octant_rotation(1, 1, 1)
    if _close(isometric, row_form, _CONVENTION_TOLERANCE):
        stored = lambda rotation: rotation  # noqa: E731
    elif _close(isometric, _transpose(row_form), _CONVENTION_TOLERANCE):
        stored = _transpose
    else:
        raise RuntimeError(
            f"{label}: *Isometric rotation {isometric} matches neither the "
            f"view-axes-as-rows form {row_form} nor its transpose"
        )

    named: dict[str, str] = {}
    view = _early_bound(model.ActiveView, "IModelView")
    for key, octant in (octants or OCTANTS).items():
        name = octant_view_name(*octant)
        rotation = stored(octant_rotation(*octant))
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
        named[key] = name
        _telemetry.event("part.named_view", view=name, octant=str(octant))
    # Leave the model in the built-in isometric the part renders use.
    model.ShowNamedView2("*Isometric", _SW_ISOMETRIC_VIEW)
    return named

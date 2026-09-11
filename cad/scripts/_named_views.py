"""Part-side pictorial view orientations for manufacturing drawings.

SolidWorks ships ONE ``*Isometric`` (camera in the +X+Y+Z octant). A part whose
defining feature faces -Z is invisible from there, so its print's pictorial
would contradict the orthographic views (the arbor-pedestal hold-down hole sits
on the -Z flange behind the strap; blind review 2026-09-11). The part therefore
saves a NAMED model view -- the same isometric projection turned 180 deg about
model Y -- that the drawing recipe places like any standard one
(``IDrawingDoc::CreateDrawViewFromModelView3`` accepts user-defined names).

Imported ONLY by parts that need it: kept out of ``_drawing_marks`` so adding a
pictorial to one part never shifts the recipe digest of the other drawing parts.
"""

from __future__ import annotations

import math
from typing import Any

import _telemetry
from _common import _early_bound

_SW_ISOMETRIC_VIEW = 7  # swStandardViews_e.swIsometricView

# Diagonal of the view rotation matrix (model -> view axes) for an isometric
# whose camera sits in the -X+Y-Z octant: screen-right (-1,0,1)/sqrt2, screen-up
# (1,2,1)/sqrt6, toward-viewer (-1,1,-1)/sqrt3. A rotation matrix's diagonal is
# the same whichever way SolidWorks lays out the 9 doubles, so this check does
# not depend on the undocumented row/column convention.
_REAR_ISOMETRIC_DIAGONAL = (
    -1.0 / math.sqrt(2.0),
    math.sqrt(2.0 / 3.0),
    -1.0 / math.sqrt(3.0),
)


@_telemetry.traced("part.name_rear_isometric", label_param="name")
def name_rear_isometric(adapter: Any, name: str) -> None:
    """Save ``name``: the standard isometric turned 180 deg about model Y."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ShowNamedView2("*Isometric", _SW_ISOMETRIC_VIEW)
    view = _early_bound(model.ActiveView, "IModelView")
    view.RotateAboutAxis(math.pi, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    model.NameView(name)
    rotation = tuple(
        float(value) for value in (model.Extension.GetNamedViewRotation(name) or ())
    )
    if len(rotation) != 9:
        raise RuntimeError(f"named view {name!r} did not persist: {rotation!r}")
    diagonal = (rotation[0], rotation[4], rotation[8])
    if any(
        abs(actual - expected) > 1e-6
        for actual, expected in zip(diagonal, _REAR_ISOMETRIC_DIAGONAL)
    ):
        raise RuntimeError(
            f"named view {name!r} is not the rear isometric: diagonal "
            f"{diagonal!r}, expected {_REAR_ISOMETRIC_DIAGONAL!r}"
        )
    # Leave the model where every other part sits at save time.
    model.ShowNamedView2("*Isometric", _SW_ISOMETRIC_VIEW)
    _telemetry.success(f"named view {name}: rear isometric")

r"""Create the drawing for the oblique-trammel jig's feed lever (MHA-CH-06-TL-26).

An 11.8 x 1 x 1/2 in flat at 1:1: the top view carries the length, the stock
width, both bolt-hole stations from the inner end, their shared row from the
back side, the native 2X 5/16 clearance callout and the grip-end radius; the
front view carries the stock thickness; the shaded iso rides top-right at 1:4.
No datums (drawing-guidelines.md rule 5).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_feed_lever.py ch-rocker-arm-tl-oblique-feed-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)

# The front view imports the hidden LeverThickReference sketch's thickness.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_feed_lever_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _supplier_dimensions import supplier_reference_dimension
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_oblique_feed_lever_spec import (
    DIMENSION_PREFIXES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_CALLOUT_PRECISION,
    HOLE_CALLOUT_PROCESS,
    HOLE_DIA,
    HOLE_X,
    HOLE_Y,
    LEVER_LENGTH,
    LEVER_THICK,
    LEVER_WIDTH,
    STOCK_CALLOUTS,
    STOCK_FRACTION_DENOMINATORS,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_feed_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# The 11.8 lever at 1:1 spans sheet x 0.060..0.360 in the top view, leaving
# the inner end's two dimension lanes inside the border; the front view
# projects below it, the iso top-right clear of the title block.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 4)
TOP_CENTER = (0.210, 0.190)
FRONT_CENTER = (0.210, 0.120)
ISO_CENTER = (0.375, 0.235)
ISO_NOTE_XY = (0.345, 0.262)

# Every text position is a MODEL point (mm) off the part, mapped onto its
# view at run time (draw_ch_rocker_arm_tl_trammel_pivot_plate). In the top
# view model +Z (the front side) prints below the view.
_H = LEVER_THICK
_W = LEVER_WIDTH
_R = HOLE_DIA / 2.0
TOP_KEEP: dict[str, tuple[float, float, float]] = {
    # Stations and the length from the inner end, shortest nearest the part.
    # The inner station's text does not fit between its own extension lines
    # at X 0 and .28 (machinist review r2: both struck the 7.00), so it
    # stands outboard right, between hole 1's and hole 2's extension lines.
    # Outboard left would put it on the 2X .50 row dimension's line.
    "Hole1X": (15.0, _H, 8.0),
    "Hole2X": (11.5, _H, 16.0),
    "LeverLength": (LEVER_LENGTH / 2.0, _H, 24.0),
    # Left of the inner end, each on its own lane, the smaller nearer the
    # part: the row from the back side, then the stock width's reference
    # over STOCK. Farm run 20261017T015225029Z had the width at -22, its
    # "25.4 STOCK" over "2X 12.70".
    "Hole1Y": (-10.0, _H, -HOLE_Y / 2.0),
    "LeverWidth": (-34.0, _H, -_W / 2.0),
    # The grip radius off the front-side grip corner, its leader on the arc.
    "GripCornerR": (LEVER_LENGTH + 14.0, _H, 10.0),
}
# The 1/2 thickness's stacked "(1/2 in)" over "STOCK" is taller than its
# span: centred on its line, the numerator sat on the upper witness (layout
# audit e5a5f5c19, extension-through-own-text), and shelved beside the span
# its connector ended in open space (machinist review mr4) or, arrows held
# inside, the shelf lost its dimension line (round 8). So the text stands on
# the dimension line's own run past the lower witness: the line runs from the
# arrows down to the text, nothing crosses it, and STOCK hangs below. The
# value's centre sits 8.5 under the witness: clear of the outside arrow
# (3.6 long) by 2 for a text about 4.6 tall (the base bar's measured
# "(5-1/2 in)" row); the front view's lower right is otherwise empty.
FRONT_KEEP: dict[str, tuple[float, float, float]] = {
    "LeverThick": (LEVER_LENGTH + 14.0, -8.5, 0.0),
}
# The hole callout's leader picks hole 2's far edge; its text stands above
# the view over the lever's inner half.
HOLE_EDGE_MODEL = (HOLE_X[1] + 0.6 * _R, _H, -HOLE_Y - 0.8 * _R)
HOLE_CALLOUT_MODEL = (70.0, _H, -_W - 22.0)


part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_drawing_hole_callout", "add_native_hole_callout"),
    )
)

_UNIT = part_spec.UNIT
(_CALLOUT_PLACES,) = set(HOLE_CALLOUT_PRECISION.values())
_HOLE_DIA_PRINTED = round(round(part_spec.HOLE_DIA / 25.4, _CALLOUT_PLACES) * 25.4, 9)


def _limits(model: float, places: int) -> list[float]:
    """A general-band dimension's acceptance limits on the inch sheet: the
    title block's band about the value printed at ``places``."""
    return limits(model, places, unit=_UNIT)


def _stock_limits(model: float, band: float) -> list[float]:
    """An as-bought size's supplier band about its nominal."""
    return [round(model - band, 12), round(model + band, 12)]


requirement(
    "carrier_seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("thickness", "length", "width"),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "thickness": (
            _stock_limits(part_spec.LEVER_THICK, part_spec.THICK_STOCK_BAND),
            ("LEVER_THICK", "THICK_STOCK_BAND"),
        ),
        "thickness_nominal": (part_spec.LEVER_THICK, ("LEVER_THICK",)),
        "length": (
            _limits(part_spec.LEVER_LENGTH, part_spec.SIZE_PLACES),
            ("LEVER_LENGTH", "SIZE_PLACES"),
        ),
        "length_nominal": (part_spec.LEVER_LENGTH, ("LEVER_LENGTH",)),
        "width": (
            _stock_limits(part_spec.LEVER_WIDTH, part_spec.WIDTH_STOCK_BAND),
            ("LEVER_WIDTH", "WIDTH_STOCK_BAND"),
        ),
        "width_nominal": (part_spec.LEVER_WIDTH, ("LEVER_WIDTH",)),
    },
    precision={
        "thickness": part_spec.THICK_PLACES,
        "length": part_spec.SIZE_PLACES,
        "width": part_spec.STOCK_PLACES,
    },
)

for _index, _x in enumerate(part_spec.HOLE_X, start=1):
    requirement(
        f"bolt_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part_spec.HOLE_DIA, contains_x_mm=_x),),
        requirements=("dia", "station", "width", "thru"),
        fields={
            "at": (
                [_x, part_spec.LEVER_THICK, -part_spec.HOLE_Y],
                ("HOLE_X", "LEVER_THICK", "HOLE_Y"),
            ),
            "axis": ([0.0, -1.0, 0.0], ("__frame__",)),
            "drill": (part_spec.CLEARANCE_SPEC.size, ("CLEARANCE_SPEC",)),
            # The native callout prints the 5/16 normal-fit size to three
            # places (.344); the band and nominal are that printed value.
            "dia": (
                limits(_HOLE_DIA_PRINTED, _CALLOUT_PLACES, part_spec.DRILLED_BAND),
                ("HOLE_DIA", "DRILLED_BAND", "SCREW_THREAD"),
            ),
            "dia_nominal": (_HOLE_DIA_PRINTED, ("HOLE_DIA",)),
            "thru": (True, ("CLEARANCE_SPEC",)),
            # Model X from the inner end: the carrier's lever station.
            "station": (
                _limits(_x, part_spec.HOLE_X_PLACES),
                (
                    "HOLE_X",
                    "HOLE_X_PLACES",
                    ("ch_rocker_arm_tl_oblique_carrier_spec", "LEVER_HOLES"),
                    ("ch_rocker_arm_tl_oblique_carrier_spec", "LEVER_INNER_END_Y"),
                ),
            ),
            "station_nominal": (_x, ("HOLE_X",)),
            # Across the width from the back long side (the mid-width line).
            "width": (
                _limits(part_spec.HOLE_Y, part_spec.HOLE_Y_PLACES),
                ("HOLE_Y", "HOLE_Y_PLACES"),
            ),
            "width_nominal": (part_spec.HOLE_Y, ("HOLE_Y",)),
        },
        precision={
            "dia": _CALLOUT_PLACES,
            "station": part_spec.HOLE_X_PLACES,
            "width": part_spec.HOLE_Y_PLACES,
        },
    )


def _view_mapper(adapter: Any, view: Any):
    """Return model point (mm) -> sheet xy (m) through the view's transform."""
    transform = _early_bound(
        _early_bound(view, "IView").ModelToViewTransform, "IMathTransform"
    )
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")

    def to_sheet(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        point = _early_bound(
            math_utility.CreatePoint(double_array([c / 1000.0 for c in model_mm])),
            "IMathPoint",
        )
        data = _early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData
        return float(data[0]), float(data[1])

    return to_sheet


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


_STOCK_SIZES = {"LeverWidth": LEVER_WIDTH, "LeverThick": LEVER_THICK}


def _stock_references(adapter: Any, annotations: list[Any]) -> None:
    """The as-bought width and thickness print as REF stock fractions over
    STOCK (#290, draw_mg_magnifying_lever's rod stock)."""
    by_name: dict[str, list[Any]] = {}
    for item in annotations:
        by_name.setdefault(dimension_name(adapter, item), []).append(item)
    for name, size in _STOCK_SIZES.items():
        matches = by_name.get(name, [])
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        display = _early_bound(
            _early_bound(matches[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        supplier_reference_dimension(
            adapter,
            display,
            label=f"feed lever stock {name}",
            units="in",
            precision=DRAWING_PRECISION_BY_NAME[name],
            expected_mm=size,
            fraction_denominator=STOCK_FRACTION_DENOMINATORS[name],
            callout=STOCK_CALLOUTS[name],
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open feed lever source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Feed Lever Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel feed lever; 6061-T6 flat; MHA-CH-06-TL-26",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (top, front):
        set_hidden_lines_removed(adapter, view)

    on_top = _view_mapper(adapter, top)
    on_front = _view_mapper(adapter, front)
    annotations = [
        *curate_view_dimensions(
            adapter,
            top,
            keep={name: on_top(xyz) for name, xyz in TOP_KEEP.items()},
            view_label="feed lever top",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            front,
            keep={name: on_front(xyz) for name, xyz in FRONT_KEEP.items()},
            view_label="feed lever front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places are authored on the part; the sheet only proves the import kept
    # them, then writes the prefixes and the stock references.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    _stock_references(adapter, annotations)

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the feed lever")
    hole_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=on_top(HOLE_EDGE_MODEL),
        callout_xy=on_top(HOLE_CALLOUT_MODEL),
        label="feed lever bolt holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        hole_callout, HOLE_CALLOUT_PRECISION, label="feed lever bolt holes"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Feed Lever Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

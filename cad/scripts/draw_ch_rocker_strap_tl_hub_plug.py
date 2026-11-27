r"""Create the drawing for MHA-CH-13-TL-02, the rocker strap's hub plug.

Shop tooling (the rocker-strap sub-plate fixture MHA-CH-13-TL-00). The PART
owns the print (``ch_rocker_strap_tl_hub_plug_spec``): places and every
callout; this recipe places the marked dimensions and proves the import kept
them.

At 4:1 (the arbor collar's recipe, ``draw_dt_cone_gear_tl_arbor_collar``):

* the END VIEW (``*Front``, looking down on the pilot's top) keeps the bore
  with its DRILL THRU callout;
* the SIDE VIEW (``*Right``, model +Z to the left, so the pilot stands left
  of the body as on the lathe; rule 11) carries both diameters, moved from
  the end view where every diameter crosses the centre: the pilot's Ø above
  it with the hub hole it clears, the body's Ø right of it with the
  counterbore it drops into; the body and overall lengths under it and the
  pilot's chamfer below-left;
* the isometric at 2:1 with its scale note.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_strap_tl_hub_plug.py ch-rocker-strap-tl-hub-plug
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
import ch_rocker_strap_tl_hub_plug_spec as spec
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, move_model_dimension
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import drilled_limits, limits
from _session import run_build

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_strap_tl_hub_plug"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = spec.ISOMETRIC_VIEW_SCALE
if tuple(ISO_SCALE) == VIEW_SCALE:
    raise AssertionError("the isometric's label would repeat the sheet scale")
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
# Farm r1 (20261117T234245842Z, layout audit): the pilot's block owns the
# top-left corner alone, the side view right of it with room under it for
# the two lengths. Machinist review r9 (rule 15): the end view, a left view,
# stands level with the side view's axis, left of it.
SIDE_CENTER = (0.200, 0.170)
END_CENTER = (0.060, SIDE_CENTER[1])
ISO_CENTER = (0.370, 0.135)
ISO_NOTE_XY = (0.335, 0.095)
BODY_HALF = spec.BODY_DIA / 2.0 * _S
PILOT_HALF = spec.PILOT_DIA / 2.0 * _S
HALF_LENGTH = spec.OVERALL_LENGTH / 2.0 * _S


def side_x(model_z: float) -> float:
    """Sheet x of model z on the side view, which centres the plug's box
    (z 0..OVERALL_LENGTH) and lays model +Z to the left."""
    return SIDE_CENTER[0] - (model_z - spec.OVERALL_LENGTH / 2.0) * _S


BOTTOM_X = side_x(0.0)  # the body's bottom face, the view's right edge
TOP_X = side_x(spec.OVERALL_LENGTH)  # the pilot's top, its left edge
PILOT_MID_X = side_x((spec.BODY_LENGTH + spec.OVERALL_LENGTH) / 2.0)
BODY_MID_X = side_x(spec.BODY_LENGTH / 2.0)

# Measured on farm r1's layout audit (rows about 5.6 mm apart, ~3.6 mm tall):
# a block placed between or beside its dimension's extension lines centres
# on the keep point, rows from about 8 mm above to 7 mm below it; a diameter
# block placed off its dimension line hangs left of the line on a shelf.
# Row widths: the body's clearance row ~128 mm, the pilot's fit row ~87 mm,
# the shoulder row ~40 mm.
BODY_BLOCK_HALF_WIDTH = 0.065
PILOT_BLOCK_WIDTH = 0.088
LENGTH_BLOCK_HALF_WIDTH = 0.021
BLOCK_BELOW = 0.008
BLOCK_ABOVE = 0.009

# The end view keeps the bore, its rows down and right of the circles, under
# the pilot's block and left of the overall length's; the two diameters
# import there too and are parked further down until they move.
END_KEEP = {
    "BoreDia": (END_CENTER[0] + BODY_HALF + 0.020, END_CENTER[1] - BODY_HALF - 0.015),
    "BodyDia": (END_CENTER[0] - 0.020, END_CENTER[1] - BODY_HALF - 0.035),
    "PilotDia": (END_CENTER[0] + 0.010, END_CENTER[1] - BODY_HALF - 0.035),
}
# The side view (r1: the .170 block sat on the .272 and both extension lines
# ran through their own text). Each length's block stands OUTSIDE its
# extension lines with its dimension line carried out to it: the body length
# right of the body's bottom face, under the body Ø's lower extension line;
# the overall length further down, left of the pilot's top. The chamfer's
# leg stays below-left of the pilot's top corner, above the overall block.
SIDE_KEEP = {
    "BodyLength": (
        BOTTOM_X + LENGTH_BLOCK_HALF_WIDTH + 0.007,
        SIDE_CENTER[1] - BODY_HALF - 0.012,
    ),
    "OverallLength": (
        TOP_X - LENGTH_BLOCK_HALF_WIDTH - 0.007,
        SIDE_CENTER[1] - BODY_HALF - 0.034,
    ),
    "ChamferSize": (TOP_X - 0.018, SIDE_CENTER[1] - PILOT_HALF - 0.010),
}
# The moved diameters (r1: the body's block sat on the side view's outline;
# the pilot's stacked on the bore's). The pilot's dimension line runs just
# left of the pilot, up to its block in the top-left corner, which hangs left
# of the line clear above the bore's block. The body's block stands above the
# body's upper extension line, right of the body, so its dimension line runs
# up to the block instead of through it (draw_ch_rocker_hub's LAND_ON_SIDE).
PILOT_ON_SIDE = (TOP_X - 0.006, SIDE_CENTER[1] + BODY_HALF + 0.045)
BODY_ON_SIDE = (
    BOTTOM_X + BODY_BLOCK_HALF_WIDTH + 0.006,
    SIDE_CENTER[1] + BODY_HALF + 0.022,
)
MOVED = {"BodyDia": BODY_ON_SIDE, "PilotDia": PILOT_ON_SIDE}
if set(END_KEEP) | set(SIDE_KEEP) != set().union(*spec.DRAWING_DIMENSIONS.values()):
    raise AssertionError("the hub plug sheet does not place every marked dimension")
if set(MOVED) | set(SIDE_KEEP) | {"BoreDia"} != set(spec.DRAWING_PRECISION_BY_NAME):
    raise AssertionError("every hub plug dimension ends on exactly one view")

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_ch_rocker_strap_tl_hub_plug: axis +Z through the origin, z = 0 the
# body's bottom face, the shoulder at the body length, the pilot's top at the
# overall length). The bottom face is the datum end both lengths run from;
# each ``span`` is a diameter's model-Z extent. The body is a REF nominal
# whose matched clearance governs; the pilot prints its own band; the bore
# the DRILLED HOLES row. The declarations print nothing.
_P = spec.DRAWING_PRECISION_BY_NAME
_C = spec.DIMENSION_CALLOUTS_BY_NAME
_SELF = "draw_ch_rocker_strap_tl_hub_plug"
part_metadata(
    model_sources=("BODY_LENGTH", "OVERALL_LENGTH", "BODY_DIA", "PILOT_DIA"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("BODY_LENGTH",)),
        "outward": ([0.0, 0.0, -1.0], ("BODY_LENGTH",)),
    },
)
requirement(
    "shoulder",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), spec.BODY_LENGTH),),
    requirements=("station",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": spec.BODY_LENGTH},
            ("BODY_LENGTH",),
        ),
        "outward": ([0.0, 0.0, 1.0], ("BODY_LENGTH",)),
        "station": (
            limits(spec.BODY_LENGTH, _P["BodyLength"], unit=spec.UNIT),
            ("BODY_LENGTH", "UNIT", (_SELF, "SIDE_KEEP")),
        ),
        "station_nominal": (spec.BODY_LENGTH, ("BODY_LENGTH",)),
        "station_from": ("datum_end", ((_SELF, "SIDE_KEEP"),)),
        "callout": (_C["BodyLength"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"station": _P["BodyLength"]},
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), spec.OVERALL_LENGTH),),
    requirements=("length",),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": spec.OVERALL_LENGTH},
            ("OVERALL_LENGTH",),
        ),
        "outward": ([0.0, 0.0, 1.0], ("OVERALL_LENGTH",)),
        "length": (
            limits(spec.OVERALL_LENGTH, _P["OverallLength"], unit=spec.UNIT),
            ("OVERALL_LENGTH", "UNIT", (_SELF, "SIDE_KEEP")),
        ),
        "length_nominal": (spec.OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        "length_from": ("datum_end", ((_SELF, "SIDE_KEEP"),)),
        "callout": (_C["OverallLength"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"length": _P["OverallLength"]},
)
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(spec.BODY_DIA),),
    requirements=("dia",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("BODY_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("BODY_DIA",)),
        "span": ([0.0, spec.BODY_LENGTH], ("BODY_LENGTH",)),
        "dia": (
            limits(spec.BODY_DIA, _P["BodyDia"], unit=spec.UNIT),
            ("BODY_DIA", "UNIT", (_SELF, "BODY_ON_SIDE")),
        ),
        "dia_nominal": (spec.BODY_DIA, ("BODY_DIA",)),
        "callout": (_C["BodyDia"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"dia": _P["BodyDia"]},
)
requirement(
    "step",
    kind="diameter",
    faces=(CylinderFace(spec.PILOT_DIA),),
    requirements=("dia",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("PILOT_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("PILOT_DIA",)),
        "span": (
            [spec.BODY_LENGTH, spec.OVERALL_LENGTH],
            ("BODY_LENGTH", "OVERALL_LENGTH"),
        ),
        "dia": (
            limits(spec.PILOT_DIA, _P["PilotDia"], unit=spec.UNIT),
            ("PILOT_DIA", "UNIT", (_SELF, "PILOT_ON_SIDE")),
        ),
        "dia_nominal": (spec.PILOT_DIA, ("PILOT_DIA",)),
        "callout": (_C["PilotDia"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"dia": _P["PilotDia"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(spec.BORE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("BORE_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("BORE_DIA",)),
        "span": ([0.0, spec.OVERALL_LENGTH], ("OVERALL_LENGTH",)),
        "dia": (
            drilled_limits(spec.BORE_DIA, _P["BoreDia"], unit=spec.UNIT),
            ("BORE_DIA", "UNIT", (_SELF, "END_KEEP")),
        ),
        "nominal_dia": (spec.BORE_DIA, ("BORE_DIA",)),
        "thru": (True, ("DIMENSION_CALLOUTS",)),
        "process": ("drill", ("DIMENSION_CALLOUTS",)),
        "wall_min": (spec.WALL_MIN, ("WALL_MIN", "WALL_TEXT")),
        "callout": (_C["BoreDia"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"dia": _P["BoreDia"]},
)
requirement(
    "chamfer_far",
    kind="chamfer",
    faces=(ConeFace(45.0),),
    requirements=("leg",),
    fields={
        "leg": (
            limits(spec.CHAMFER, _P["ChamferSize"], unit=spec.UNIT),
            ("CHAMFER", "UNIT", (_SELF, "SIDE_KEEP")),
        ),
        "leg_nominal": (spec.CHAMFER, ("CHAMFER",)),
        "angle_deg": (45.0, ("DIMENSION_CALLOUTS",)),
        "edge_of": ("step", ("PILOT_CHAMFER",)),
        "at_end": ("far_end", ("PILOT_CHAMFER",)),
        "callout": (_C["ChamferSize"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"leg": _P["ChamferSize"]},
)


def _assert_part_text(adapter: Any, annotations: list[Any]) -> None:
    """The part authors every callout below its value; the import must carry
    each unchanged (the drawing never writes them, #1942)."""
    # swDimensionTextCalloutBelow 4.
    expected = {
        (4, name): text for name, text in spec.DIMENSION_CALLOUTS_BY_NAME.items()
    }
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        slots = [slot for slot, expected_name in expected if expected_name == name]
        if not slots:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in slots:
            found[(slot, name)] = str(display.GetText(slot) or "").replace("\r\n", "\n")
    if found != expected:
        raise RuntimeError(
            f"hub plug dimension text did not import: {found!r} != {expected!r}"
        )


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub plug source", adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity")
    read_required_properties(
        adapter.currentModel,
        ("Revision", "Title", *required, "Isometric View Note"),
        required=(*required, "Isometric View Note"),
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
            0: "Rocker Strap Hub Plug Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"rocker strap hub plug; turned; {spec.PART_NUMBER}",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A turned part needs no hidden lines (drawing-guidelines.md rule 9).
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    moved = []
    for name, text_xy in MOVED.items():
        donors = [a for a in end_annotations if dimension_name(adapter, a) == name]
        if len(donors) != 1:
            raise RuntimeError(f"expected one {name} donor dimension on the end view")
        moved.append(
            move_model_dimension(adapter, donors[0], side, text_xy, source_view=end)
        )
    annotations = [
        *(a for a in end_annotations if dimension_name(adapter, a) not in MOVED),
        *side_annotations,
        *moved,
    ]
    # Places (and so each dimension's title-block row) are the part's; the
    # sheet only proves the import kept them, and its text.
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    _assert_part_text(adapter, annotations)
    # The side view's axis (the template centre-marks the end view's circles
    # as the view is placed, draw_mg_wheel_drum).
    add_view_centerline(
        adapter,
        side,
        face_xy=(BODY_MID_X, SIDE_CENTER[1] + BODY_HALF / 2.0),
        label="hub plug axis centerline",
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Strap Hub Plug Drawing",
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

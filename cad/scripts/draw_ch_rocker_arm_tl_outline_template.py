r"""Create the drawing for the rocker arm's outline template (MHA-CH-006-TL-13).

The face view (``*Front``, 1:1) carries the whole outline from the pivot
hole: both apex heights on the mirror line, both radii, the arc-end stations
and the tip lands; the right-side edge view carries the plate thickness; a
shaded isometric at 1:4 sits above.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

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

# The part saves ApexReference hidden: this form shows it in the view that
# imports its dimensions.
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_outline_template_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_outline_template_spec import (
    ARC_CENTER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_CALLOUT,
    SHARP_EDGE_CALLOUT,
    THICK_CALLOUT,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_outline_template"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 292.5 x 29.3 plate: 1:1 is the template's own size and still fits the
# B sheet with every dimension lane outside the outline.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 4)
FRONT_CENTER = (0.200, 0.165)
RIGHT_CENTER = (0.400, 0.165)
# Notes start above the title block's top edge so both lines clear it.
NOTES_XY = (0.020, 0.088)
ISO_CENTER = (0.330, 0.240)
ISO_NOTE_XY = (0.250, 0.258)
# Radius text stays outside both circles (below the outline) and each radius
# keeps its arrow outside the arc with no solid leader, so its leader runs
# from the text to its arc and stops: never on to the off-sheet centre.  The
# radius blocks sit inboard of the 132.757 extension lines; the bottom apex
# block sits just left of the centreline so the R800 block clears it.
EXTERIOR_RADII = ("TopRadius", "BottomRadius")
FRONT_KEEP = {
    "TopRadius": (0.095, 0.140),
    "BottomRadius": (0.305, 0.140),
    "BottomBelowPivot": (0.188, 0.137),
    "PivotDia": (0.240, 0.140),
    "BottomTailX": (0.133, 0.118),
    "BottomRodX": (0.267, 0.118),
    "TopAbovePivot": (0.222, 0.190),
    "TopTailX": (0.128, 0.207),
    "TopRodX": (0.272, 0.207),
    "TailTipLen": (0.033, 0.197),
    "RodTipLen": (0.367, 0.197),
}
# Above the edge view so the stock callout clears the rod tip-land text and
# the sheet border.
RIGHT_KEEP = {"Thick": (0.392, 0.225)}
# Both arc centres lie on the bore's vertical centreline, off the sheet
# above; the apex heights land on each arc's low point there, and the tip
# lands run radially from those centres.  Each scribing edge carries its
# SHARP requirement and each apex height the rocker edge it sets.  SOLIDWORKS
# centres each apex block on its position, so the extra line grows it upward:
# the positions sit low enough that each +0.03 keeps its single-line height,
# clear of the bottom arc and the 145.240 line.
CALLOUTS_BELOW = {
    "TopRadius": f"{ARC_CENTER_CALLOUT}\n{SHARP_EDGE_CALLOUT}",
    "BottomRadius": f"{ARC_CENTER_CALLOUT}\n{SHARP_EDGE_CALLOUT}",
    "TopAbovePivot": "TO TOP ARC LOW POINT\nSETS ROCKER TOP EDGE",
    "BottomBelowPivot": "TO BOTTOM ARC LOW POINT\nSETS ROCKER BOTTOM EDGE",
    "PivotDia": PIVOT_CALLOUT,
    "Thick": THICK_CALLOUT,
}
CALLOUTS_ABOVE = {"TailTipLen": "RADIAL, SHARP", "RodTipLen": "RADIAL, SHARP"}

_Z = [0.0, 0.0, 1.0]
_PRECISION = DRAWING_PRECISION_BY_NAME

part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "top_edge",
    kind="profile",
    faces=(CylinderFace(2.0 * part_spec.R_TOP),),
    requirements=("height_above_pivot", "radius", "station"),
    fields={
        "height_above_pivot": (
            limits(
                part_spec.TOP_ABOVE_PIVOT,
                _PRECISION["TopAbovePivot"],
                part_spec.APEX_BAND,
            ),
            ("TOP_ABOVE_PIVOT", "APEX_BAND", ("ch_rocker_arm_spec", "TOP_EDGE_BAND")),
        ),
        "height_nominal": (part_spec.TOP_ABOVE_PIVOT, ("TOP_ABOVE_PIVOT",)),
        "height_from": (
            "pivot_hole",
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
        "radius": (limits(part_spec.R_TOP, _PRECISION["TopRadius"]), ("R_TOP",)),
        "radius_nominal": (part_spec.R_TOP, ("R_TOP",)),
        "arc_centre": ([0.0, part_spec.CENTER_Y, 0.0], ("CENTER_Y",)),
        "station": (
            limits(part_spec.TOP_END_X, _PRECISION["TopRodX"]),
            ("TOP_END_X", "END_PLACES"),
        ),
        "station_nominal": (part_spec.TOP_END_X, ("TOP_END_X",)),
        "end": (
            [part_spec.TOP_END_X, part_spec.TOP_END_Y, 0.0],
            ("TOP_END_X", "TOP_END_Y"),
        ),
        "mirror_symmetric": (
            True,
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
    },
    precision={
        "height_above_pivot": _PRECISION["TopAbovePivot"],
        "radius": _PRECISION["TopRadius"],
        "station": _PRECISION["TopRodX"],
    },
)

requirement(
    "bottom_edge",
    kind="profile",
    faces=(CylinderFace(2.0 * part_spec.R_BOTTOM),),
    requirements=("depth", "radius", "station"),
    fields={
        # The bottom apex's depth below the pivot, on the mirror line.
        "depth": (
            limits(
                part_spec.BOTTOM_BELOW_PIVOT,
                _PRECISION["BottomBelowPivot"],
                part_spec.APEX_BAND,
            ),
            (
                "BOTTOM_BELOW_PIVOT",
                "APEX_BAND",
                ("ch_rocker_arm_spec", "TOP_EDGE_BAND"),
            ),
        ),
        "height_from": (
            "pivot_hole",
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
        "radius": (
            limits(part_spec.R_BOTTOM, _PRECISION["BottomRadius"]),
            ("R_BOTTOM",),
        ),
        "radius_nominal": (part_spec.R_BOTTOM, ("R_BOTTOM",)),
        "arc_centre": ([0.0, part_spec.CENTER_Y, 0.0], ("CENTER_Y",)),
        "station": (
            limits(part_spec.BOT_END_X, _PRECISION["BottomRodX"]),
            ("BOT_END_X", "END_PLACES"),
        ),
        "station_nominal": (part_spec.BOT_END_X, ("BOT_END_X",)),
        "bottom_end": (
            [part_spec.BOT_END_X, part_spec.BOT_END_Y, 0.0],
            ("BOT_END_X", "BOT_END_Y"),
        ),
        "mirror_symmetric": (
            True,
            (("draw_ch_rocker_arm_tl_outline_template", "build"),),
        ),
    },
    precision={
        "depth": _PRECISION["BottomBelowPivot"],
        "radius": _PRECISION["BottomRadius"],
        "station": _PRECISION["BottomRodX"],
    },
)

requirement(
    "pivot_hole",
    kind="hole",
    faces=(CylinderFace(part_spec.PIVOT_HOLE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": (_Z, ("__frame__",)),
        "dia": (
            limits(
                part_spec.PIVOT_HOLE_DIA,
                _PRECISION["PivotDia"],
                part_spec.PIVOT_HOLE_BAND,
            ),
            ("PIVOT_HOLE_DIA", "PIVOT_HOLE_BAND", "PIN_GAUGE_MAX"),
        ),
        "dia_nominal": (part_spec.PIVOT_HOLE_DIA, ("PIVOT_HOLE_DIA",)),
        "thru": (True, (("draw_ch_rocker_arm_tl_outline_template", "build"),)),
        "process": ("ream", ("PIVOT_CALLOUT",)),
    },
    precision={"dia": _PRECISION["PivotDia"]},
)

for _side, _sign in (("rod", 1.0), ("tail", -1.0)):
    # A radial land: its plane holds the arcs' centre, its outward normal is
    # the top arc's tangent at that end.
    requirement(
        f"{_side}_tip_land",
        kind="face",
        faces=(
            PlanarFace(
                (
                    _sign * math.cos(part_spec.ALPHA_TOP),
                    math.sin(part_spec.ALPHA_TOP),
                    0.0,
                ),
                part_spec.CENTER_Y * math.sin(part_spec.ALPHA_TOP),
            ),
        ),
        requirements=("length",),
        fields={
            "length": (
                limits(part_spec.TIP_FACE, _PRECISION["RodTipLen"]),
                ("TIP_FACE", "END_PLACES"),
            ),
            "length_nominal": (part_spec.TIP_FACE, ("TIP_FACE",)),
            "top_edge_feature": ("top_edge", ("ALPHA_TOP", "CENTER_Y")),
            "end": (
                [_sign * part_spec.TIP_X, part_spec.TIP_Y, 0.0],
                ("TIP_X", "TIP_Y"),
            ),
        },
        precision={"length": _PRECISION["RodTipLen"]},
    )

for _name, _normal, _offset in (
    ("arm_face", (0.0, 0.0, -1.0), 0.0),
    ("top_face", (0.0, 0.0, 1.0), part_spec.THICK),
):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, _offset),),
        requirements=("thickness",),
        fields={
            "normal": (list(_normal), ("__frame__",)),
            "plane": ({"frame": "model", "axis": "z", "value": _offset}, ("THICK",)),
            "thickness": (
                limits(part_spec.THICK, _PRECISION["Thick"]),
                ("THICK", "THICK_PLACES"),
            ),
            "thickness_nominal": (part_spec.THICK, ("THICK",)),
        },
        precision={"thickness": _PRECISION["Thick"]},
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open outline-template source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Outline Template Drawing",
            1: "Harmonic Analyzer shop gauge drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm layout and profile template; annealed O1; MHA-CH-006-TL-13",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="face view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="edge view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    _radius_leaders_to_arc(adapter, annotations)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center mark to the template pivot hole")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Outline Template Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _radius_leaders_to_arc(adapter: Any, annotations: list[Any]) -> None:
    """The rocker's exterior-radius dress: text-to-arc leaders only."""
    remaining = set(EXTERIOR_RADII)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = False
        display.ArcExtensionLineOrOppositeSide = False
        display.ArrowSide = 1  # swDimArrowsOutside
        display.SolidLeader = False
        if (
            bool(display.ShortenedRadius)
            or bool(display.ArcExtensionLineOrOppositeSide)
            or int(display.ArrowSide) != 1
            or bool(display.SolidLeader)
        ):
            raise RuntimeError(f"{name} retained its centre-directed radius leader")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(f"exterior radii missing: {sorted(remaining)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

r"""Create the drawing for the cone pivot post's tall vise soft jaw (MHA-DT-005-TL-04).

A flat plate needs only the gripping-face view (front, which shows the
counterbores as circles), the plan above it (third angle: the thickness)
and the shaded isometric. The plate's length, height and both bolt stations
print from its bottom-left corner; the counterbored holes ship as the native
wizard callout. No frames and no datums (fixtures are off the rule-3
allowlist).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import dt_cone_pivot_post_tl_soft_jaw_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from dt_cone_pivot_post_tl_soft_jaw_spec import (
    BOLT_HEIGHT,
    BOLT_LEFT_X,
    BOLT_RIGHT_X,
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PLATE_HEIGHT,
    PLATE_LENGTH,
)

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_soft_jaw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 158.67 x 63.5 x 19.05 plate: 1:1 fits the face view and its plan on the
# B sheet; the isometric runs at 1:2 to clear the title block.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
FRONT_CENTER = (0.150, 0.150)
TOP_CENTER = (0.150, 0.215)
ISO_CENTER = (0.360, 0.190)
ISO_NOTE_XY = (0.315, 0.245)
NOTES_XY = (0.020, 0.070)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the face view (1:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - PLATE_LENGTH / 2.0) / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the face view (1:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) / 1000.0


# Every station measures from the bottom-left corner: the three horizontal
# sizes stack under the face view (shortest nearest), the two heights stand
# left of it (the shorter inboard); the thickness rides right of the plan.
FRONT_KEEP = {
    "BoltLeftX": (_sheet_x(BOLT_LEFT_X / 2.0), 0.106),
    "BoltRightX": (_sheet_x(BOLT_RIGHT_X / 2.0), 0.096),
    "PlateLength": (FRONT_CENTER[0], 0.086),
    "BoltY": (0.054, _sheet_y(BOLT_HEIGHT / 2.0)),
    "PlateHeight": (0.033, FRONT_CENTER[1]),
}


_JAW_TOP_SOURCES = (
    "PLATE_HEIGHT",
    "PARALLEL_HEIGHT",
    ("dt_cone_pivot_post_spec", "BORE_HEIGHT"),
    ("dt_cone_pivot_post_spec", "JOURNAL_AXIS_HEIGHT_TOLERANCE_MM"),
    ("dt_cone_pivot_post_spec", "CONE_BOSS_DIA"),
    ("dt_cone_pivot_post_spec", "HEAD_BASE_Y"),
    ("dt_cone_pivot_post_spec", "CRANK_BORE_HEIGHT"),
    ("dt_cone_pivot_post_spec", "CRANK_BOSS_DIA"),
)
_CBORE_FLOOR_Z = part_spec.PLATE_THICK - part_spec.CBORE_DEPTH


def _bolt_features(side: str, x: float, name: str) -> dict[str, dict]:
    hole = f"bolt_{side}"
    return {
        hole: {
            'kind': "hole",
            'faces': (CylinderFace(part_spec.BOLT_HOLE_DIA, contains_x_mm=x),),
            'requirements': ("dia", "thru", "station", "height"),
            'fields': {
                "at": ([x, part_spec.BOLT_HEIGHT, part_spec.PLATE_THICK], (name, "BOLT_HEIGHT", "PLATE_THICK")),
                "axis": ([0.0, 0.0, -1.0], ("__frame__",)),
                "dia": (
                    [part_spec.BOLT_HOLE_DIA, round(part_spec._HOLE_MAX, 12)],
                    ("BOLT_HOLE_DIA", "JAW_SCREW_MAJOR"),
                ),
                "nominal_dia": (part_spec.BOLT_HOLE_DIA, ("BOLT_HOLE_DIA",)),
                "thru": (True, ("BOLT_HOLE_SPEC",)),
                "station": (limits(x, part_spec.BOLT_PLACES), (name,)),
                "station_nominal": (x, (name,)),
                "height": (limits(part_spec.BOLT_HEIGHT, part_spec.BOLT_PLACES), ("BOLT_HEIGHT",)),
                "height_nominal": (part_spec.BOLT_HEIGHT, ("BOLT_HEIGHT",)),
            },
            'precision': {"dia": 2, "station": part_spec.BOLT_PLACES, "height": part_spec.BOLT_PLACES},
        },
        f"{hole}_counterbore": {
            'kind': "counterbore",
            'faces': (
                CylinderFace(part_spec.CBORE_DIA, contains_x_mm=x),
                PlanarFace((0.0, 0.0, 1.0), _CBORE_FLOOR_Z, contains_x_mm=x),
            ),
            'requirements': ("dia", "depth"),
            'fields': {
                "parent": (hole, ("BOLT_HOLE_SPEC", ("draw_dt_cone_pivot_post_tl_soft_jaw", "build"))),
                "dia": (limits(part_spec.CBORE_DIA, 2), ("CBORE_DIA", "JAW_SCREW_HEAD_DIA")),
                "nominal_dia": (part_spec.CBORE_DIA, ("CBORE_DIA",)),
                "depth": (limits(part_spec.CBORE_DEPTH, 2), ("CBORE_DEPTH", "JAW_SCREW_HEAD_HEIGHT")),
                "depth_ref": (part_spec.CBORE_DEPTH, ("CBORE_DEPTH",)),
            },
            'precision': {"dia": 2, "depth": 2},
        },
    }


# The bottom edge stands on the vise bed beside the parallels.
part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME", ("_drawing_hole_callout", "add_native_hole_callout")))

requirement("bed_face",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("height",),
    fields={
        "normal": ([0.0, -1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": 0.0}, ("__frame__",)),
        "height": (part_spec._HEIGHT_RANGE, ("PLATE_HEIGHT",)),
    },
    precision={"height": part_spec.HEIGHT_PLACES},
)

# The jaw top: over the cone caps, under the head shoulder and crank boss.
requirement("jaw_top",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part_spec.PLATE_HEIGHT),),
    requirements=("height", "length"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": part_spec.PLATE_HEIGHT}, ("PLATE_HEIGHT",)),
        "height": (part_spec._HEIGHT_RANGE, _JAW_TOP_SOURCES),
        "height_nominal": (part_spec.PLATE_HEIGHT, ("PLATE_HEIGHT",)),
        "length": (limits(part_spec.PLATE_LENGTH, part_spec.LENGTH_PLACES), ("PLATE_LENGTH",)),
    },
    precision={"height": part_spec.HEIGHT_PLACES, "length": part_spec.LENGTH_PLACES},
)

TOP_KEEP = {"PlateThick": (0.250, TOP_CENTER[1])}


# The gripping face carries a cap jaw button on each cone-boss cap.
requirement("grip_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.PLATE_THICK),),
    requirements=("thickness",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": part_spec.PLATE_THICK}, ("PLATE_THICK",)),
        "thickness": (part_spec._THICK_RANGE, ("PLATE_THICK",)),
        "thickness_nominal": (part_spec.PLATE_THICK, ("PLATE_THICK",)),
    },
    precision={"thickness": part_spec.THICK_PLACES},
)

# The back face seats on the vise jaw in place of the hardened plate.
requirement("jaw_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("thickness",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "thickness": (part_spec._THICK_RANGE, ("PLATE_THICK",)),
    },
    precision={"thickness": part_spec.THICK_PLACES},
)

# The leader leaves the right counterbore from its upper-right quadrant and the
# text stands right of the plate's upper half, above the length's extension
# line and below the plan's thickness, short of the isometric.
_CBORE_R = CBORE_DIA / 2.0
HOLE_CALLOUT_EDGE_XY = (
    _sheet_x(BOLT_RIGHT_X + 0.6 * _CBORE_R),
    _sheet_y(BOLT_HEIGHT + 0.8 * _CBORE_R),
)
HOLE_CALLOUT_XY = (0.272, 0.168)


for name, fields in _bolt_features("left", part_spec.BOLT_LEFT_X, "BOLT_LEFT_X").items():
    requirement(name, **fields)

for name, fields in _bolt_features("right", part_spec.BOLT_RIGHT_X, "BOLT_RIGHT_X").items():
    requirement(name, **fields)

HOLE_CALLOUT_PROCESS = "7/16 DRILL"


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open soft-jaw source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Post Vise Soft Jaw Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post vise soft jaw; 6061 plate; MHA-DT-005-TL-04",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The counterbores show as true circles on the face and are sized by
    # their callout; the plan needs no hidden bores.
    for view in (front, top):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="gripping face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center marks to the soft-jaw face view")
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=HOLE_CALLOUT_EDGE_XY,
        callout_xy=HOLE_CALLOUT_XY,
        label="soft-jaw bolt counterbores",
        process=HOLE_CALLOUT_PROCESS,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Vise Soft Jaw Drawing",
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

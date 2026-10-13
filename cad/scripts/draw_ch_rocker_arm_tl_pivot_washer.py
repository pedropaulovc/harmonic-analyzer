r"""Create the drawing for the rocker arm's pivot-screw washer (MHA-CH-006-TL-07).

A face view (``*Front``, looking down the axis) carries the two diameters and
the edge view (``*Bottom``, third-angle below it) the thickness.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_leaders import set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_pivot_washer_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_pivot_washer_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OUTER_CALLOUT,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_pivot_washer"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A Ø10 x 1.5 washer: 5:1 keeps the 1.5 edge legible.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
FACE_CENTER = (0.130, 0.185)
EDGE_CENTER = (0.130, 0.105)
ISO_CENTER = (0.300, 0.175)
ISO_NOTE_XY = (0.265, 0.235)
FACE_KEEP = {
    "OuterDia": (0.185, 0.225),
    # Near-side style below: one arrow each, on separate rays, nothing
    # drawn through the centre.
    "BoreDia": (0.075, 0.145),
}


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement("bore",
    kind="hole",
    faces=(CylinderFace(part_spec.BORE_DIA),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": ([0.0, 0.0, 1.0], ("__frame__",)),
        "dia": (
            limits(part_spec.BORE_DIA, part_spec.PLACES, part_spec.BORE_BAND),
            ("BORE_DIA", "BORE_BAND", ("ch_rocker_arm_tl_pivot_screw_spec", "SHOULDER_DIA")),
        ),
        "thru": (True, (("draw_ch_rocker_arm_tl_pivot_washer", "build"),)),
    },
    precision={"dia": part_spec.PLACES},
)

EDGE_KEEP = {
    "Thick": (0.175, 0.105),
}


requirement("hub_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("thickness", "dia"),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "thickness": (limits(part_spec.THICK, part_spec.THICK_PLACES), ("THICK", "THICK_PLACES")),
        "dia": (
            limits(part_spec.OUTER_DIA, part_spec.OUTER_PLACES, part_spec.OUTER_BAND),
            ("OUTER_DIA", "OUTER_BAND", ("ch_rocker_arm_spec", "HUB_DIA")),
        ),
        "process": ("face", (("draw_ch_rocker_arm_tl_pivot_washer", "build"),)),
    },
    precision={"thickness": part_spec.THICK_PLACES, "dia": part_spec.OUTER_PLACES},
)

requirement("head_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.THICK),),
    requirements=("thickness",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": part_spec.THICK}, ("THICK",)),
        "thickness": (limits(part_spec.THICK, part_spec.THICK_PLACES), ("THICK", "THICK_PLACES")),
        "process": ("face", (("draw_ch_rocker_arm_tl_pivot_washer", "build"),)),
    },
    precision={"thickness": part_spec.THICK_PLACES},
)



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-washer source", await adapter.open_model(str(SOURCE)))
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
            0: "Rocker Arm Pivot Washer Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm S4 pivot-screw washer; hardened lapped O1; MHA-CH-006-TL-07",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    edge = place_view(adapter, str(SOURCE), "*Bottom", *EDGE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, edge):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter, face, keep=FACE_KEEP, view_label="face view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter, edge, keep=EDGE_KEEP, view_label="edge view",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    for name in ("OuterDia", "BoreDia"):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
        set_near_side_diameter(matches[0], f"pivot-washer {name}")
    set_dimension_callouts(adapter, annotations, {"BoreDia": BORE_CALLOUT, "OuterDia": OUTER_CALLOUT}, location="below")
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, face, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center mark to the washer face view")
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Pivot Washer Drawing",
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

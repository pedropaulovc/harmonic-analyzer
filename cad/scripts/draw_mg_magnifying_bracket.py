r"""Create the curated machinist drawing for the magnifying-lever bracket.

The bracket is the black fitting that affixes the Ø6 magnifying-lever rod to the
summing plate: a revolved COLLAR tube (Ø12 OD, Ø6.2 bore, 10 long about local X)
that the rod slips through, a rectangular ARM cantilevering +Z, and a mounting
FLANGE that butts the summing-plate front face.  The two extruded plan
rectangles (arm, flange) carry the auto-imported marked dimensions on the TOP
view, including the flange thickness band. Native counterbore callouts and
banded coordinates face the -Z entries in the BACK view. Legacy collar
dimensions and fit remain in the notes. The collar axis is local +X, so the
RIGHT view shows the collar end as concentric circles (ASME centre mark).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_bracket.py mg-magnifying-bracket
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_native_hole_callout,
    scan_view_edges,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions

from magnifying_bracket_joint_layout import (
    BRACKET_HOLE_POINTS,
    COUNTERBORE_DIA,
    SIDE_PLATE_Z,
)

SPEC = DRAWINGS_BY_NAME["mg_magnifying_bracket"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
TOP_CENTER = (0.115, 0.180)
FRONT_CENTER = (0.115, 0.110)
# Supplemental entry view, not part of the aligned front/top/right group.
BACK_CENTER = (0.245, 0.095)
RIGHT_CENTER = (0.240, 0.180)
ISO_CENTER = (0.340, 0.130)

# The four plan dimensions ride the TOP view (both extruded rectangles lie on the
# part's Top plane).  Arm/flange dim names are disambiguated in the build
# (ArmWidth/ArmDepth vs FlangeWidth/FlangeDepth) so this keep map is unambiguous.
TOP_KEEP = {
    "ArmWidth": (0.088, 0.170),
    "ArmDepth": (0.142, 0.182),
    "FlangeWidth": (0.110, 0.216),
    "FlangeDepth": (0.089, 0.205),
}
BACK_KEEP = {
    "MountingX0": (0.205, 0.124),
    "MountingX1": (0.230, 0.132),
    "MountingY0": (0.203, 0.095),
}
FRONT_KEEP = {"FlangeHeight": (0.148, 0.110)}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
# Blind-review round 1: the four plan values read unattached at a glance --
# label each with the feature it controls.
DIMENSION_CALLOUTS = {
    "ArmWidth": "ARM WIDTH",
    "ArmDepth": "ARM LENGTH",
    "FlangeWidth": "FLANGE WIDTH",
    "FlangeDepth": "FLANGE DEPTH",
}


def _mounting_rims(back: Any) -> list[Any]:
    """Back looks from -Z onto the counterbore entries."""
    edges = scan_view_edges(back, label="bracket mounting face")
    return [
        edges.circle_at(
            (point[0], point[1], SIDE_PLATE_Z[0]),
            COUNTERBORE_DIA / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=f"bracket mounting hole {index}",
        )
        for index, point in enumerate(BRACKET_HOLE_POINTS)
    ]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-bracket source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying bracket; collar + arm + flange; steel fitting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # Top carries the collar bore and arm/flange hidden edges; the counterbore
    # shape is fully defined by its native callout on the clean entry view.
    set_hidden_lines_visible(adapter, top)
    set_hidden_lines_removed(adapter, back)
    set_hidden_lines_removed(adapter, front)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, back, keep={}, view_label="back")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, top_annotations, DIMENSION_CALLOUTS)
    rims = _mounting_rims(back)

    add_native_hole_callout(
        adapter,
        back,
        edge=rims[0].edge,
        # AddHoleCallout2 centres the ~120 mm-wide text on x and the leader
        # lands on the text end nearer the hole (263.6, 96.3 mm). Centred at
        # 330 mm the near end sits right of the hole, so the leader rises
        # almost vertically, clear of every back-view dimension text
        # (x <= 242 mm); the text sits above the isometric (y <= 142 mm) and
        # below the right view (y >= 173 mm). (0.205, 0.064) printed over
        # the title block; x = 0.150 and 0.270 both led through '17.70'.
        callout_xy=(0.330, 0.160),
        label="two bracket counterbores",
        process="DRILL / COUNTERBORE",
    )
    curate_hidden_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="bracket mounting coordinates",
        dimensions_by_feature={
            "MountingCoordinates": ("MountingX0", "MountingX1", "MountingY0"),
        },
    )

    # ASME centre mark on the collar bore (a real circular edge in the end view).
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the collar bore")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.095)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Bracket Manufacturing Drawing",
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

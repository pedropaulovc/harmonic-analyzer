r"""Create the curated manufacturing drawing for the cylinder gear (+ cam).

Sets the batch gear-drawing pattern: the toothed face view dimensions the
machinable BLANK (bore, cam disc and its offset from the bore), SECTION A-A
(cut face only, through the axis) shows the bore through the whole gear + cam
stack and states the cam thickness, DETAIL B enlarges the alignment kerf and
carries its saw specification, and the GEAR DATA note specifies the involute
tooth system with its over-pins acceptance. The involute OD is a scalloped
outline with no single circular edge to dimension.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
gear is not on the GD&T allowlist, so it carries no datums and no
feature-control frames. Two roughness symbols: the bore, which RUNS on the
cylinder-gear shaft, and the cam O.D., the follower track the connecting-rod
ring rides; the bore's fit band is native and the kerf's band is in its callout.

The cam sits at z 3..6.5, on the NEAR side of the ``*Front`` view (the viewer
looks from +Z), so it reads as a solid circle over the toothed face -- the
earlier "FAR FACE" note was the wrong way round (machinist review 2026-09-02).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    create_detail_view,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import show_only_cut_face, visible_circle_edge
from _surface_finish import surface_finish_by_key
from cylinder_gear_spec import (
    BORE_DIA,
    CAM_DIA,
    CAM_THICKNESS,
    KERF_CALLOUT,
    OUTSIDE_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cylinder_gear"]
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

# 1:1 whole sheet: OD 62.2 mm reads roomily and leaves the left column for the
# gear-data and manufacturing-notes blocks. The gear axis is Z, so *Front shows
# the toothed face (cam nearest the viewer) and the section the axial stack.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
SECTION_SCALE = (1, 2)
FRONT_CENTER = (0.225, 0.175)
ISO_CENTER = (0.385, 0.175)
GEAR_DATA_POS = (0.040, 0.262)

# SECTION A-A: a vertical cut through the gear axis (the +Y cam lobe side is
# then the top of the strip), placed where the projected side view used to
# sit. Cut face only -- the projected tooth ring behind the plane would
# otherwise bury the bore and the cam step under ~480 tooth edges.
SECTION_HALF_LINE = OUTSIDE_DIA / 2000.0 + 0.008
SECTION_LINE = (
    (FRONT_CENTER[0], FRONT_CENTER[1] - SECTION_HALF_LINE),
    (FRONT_CENTER[0], FRONT_CENTER[1] + SECTION_HALF_LINE),
)
SECTION_CENTER = (0.310, 0.245)
# The cut face makes the axial step visible. Its thickness is stated beside
# that view instead of depending on seat-specific derived-view edge picks.
CAM_THICKNESS_NOTE = f"CAM THICKNESS {CAM_THICKNESS:.2f}"
CAM_THICKNESS_NOTE_XY = (0.330, 0.230)

# DETAIL B (4:1) around the alignment kerf at +Y. The circle is centred 3 mm
# left of the kerf so it clears the A-A cut line at x = 0 while still taking
# in the saw cut and two neighbouring teeth.
DETAIL_MODEL_CENTER_MM = (-3.0, OUTSIDE_DIA / 2.0 - 1.5)
DETAIL_CENTER_ON_FRONT = (
    FRONT_CENTER[0] + DETAIL_MODEL_CENTER_MM[0] / 1000.0,
    FRONT_CENTER[1] + DETAIL_MODEL_CENTER_MM[1] / 1000.0,
)
DETAIL_RADIUS = 0.0029
DETAIL_CENTER = (0.300, 0.105)
DETAIL_SCALE = (4, 1)
KERF_DISPLAY_NOTE = KERF_CALLOUT.replace(", 3.0", "\n3.0").replace(
    ", FULL FACE", "; FULL FACE"
)
KERF_NOTE_XY = (0.325, 0.120)

# Front-view marked dimensions. The bore callout sits upper-left so its leader
# lands on the bore's upper-left; the two roughness symbols take the lower-left
# and left so every leader is radial and none crosses another (rule 8). The
# cam diameter and its 8.640 offset from the bore go to the right.
FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] + 0.042),
    "CamDia": (FRONT_CENTER[0] + 0.055, FRONT_CENTER[1] + 0.030),
    "CamOffset": (FRONT_CENTER[0] + 0.048, FRONT_CENTER[1] + 0.0043),
}
# A nominal 3/8 in reamer is inside the 9.525 +0.05/0.00 model band
# (build_cylinder_gear); the callout only names the process, while three
# decimals on the bore and cam offset say "hold it".
DIMENSION_CALLOUTS = {"BoreDia": "REAM THRU"}
DIMENSION_PRECISION = {"BoreDia": 3, "CamOffset": 3, "CamDia": 2}
BORE_FINISH_SYMBOL = (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1] - 0.055)
CAM_FINISH_SYMBOL = (FRONT_CENTER[0] - 0.052, FRONT_CENTER[1] - 0.012)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear; integral eccentric cam; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in the orthographic view (policy rule 7).
    set_hidden_lines_visible(adapter, front)

    # DETAIL B owns one complete adjacent saw specification; importing the
    # 0.40 model dimension exposed no marked dimensions, while selecting the
    # tiny derived-view kerf edge was also unreliable.
    create_detail_view(
        adapter,
        front,
        center=DETAIL_CENTER_ON_FRONT,
        radius=DETAIL_RADIUS,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="kerf detail",
    )
    if add_note(adapter, KERF_DISPLAY_NOTE, *KERF_NOTE_XY) is None:
        raise RuntimeError("failed to add kerf saw note")

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to gear bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)
    cam_edge = visible_circle_edge(adapter, front, CAM_DIA)

    # Both finishes attach by model identity (the batch contract) at each
    # circle edge's canonical vertex, its lower-left, invariant across runs.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "cylinder_gear_bore"),
        label="cylinder gear bore finish",
        entity=bore_edge,
    )
    add_surface_finish(
        adapter,
        front,
        symbol_xy=CAM_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "cam_track"),
        label="cam track finish",
        entity=cam_edge,
    )

    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="gear + cam stack",
    )
    show_only_cut_face(adapter, section, label="gear + cam stack")
    if add_note(adapter, CAM_THICKNESS_NOTE, *CAM_THICKNESS_NOTE_XY) is None:
        raise RuntimeError("failed to add cam thickness note")

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

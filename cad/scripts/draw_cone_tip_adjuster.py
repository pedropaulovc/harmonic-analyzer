r"""Create the curated machinist drawing for the cone tip adjuster set screw.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
slotted set screw carries no datums, no feature-control frames and no
roughness symbols -- every band rides its model dimension and the title
block's general tolerances govern the rest.
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
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_adjuster_spec import (
    CHAMFER as CHAMFER,
    THREAD,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_adjuster"]
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

SHEET_SCALE = (4.0, 1.0)

# The screw is 14 mm long x nominal Ø7.9375: at 4:1 the elevation is compact.
# Third angle: the slotted head and cup-end views sit below the elevation.
FRONT_CENTER = (0.095, 0.180)
END_CENTER = (0.095, 0.100)
CUP_CENTER = (0.190, 0.100)
ISO_CENTER = (0.300, 0.160)

FRONT_KEEP = {
    "BodyLenDim": (FRONT_CENTER[0] - 0.045, FRONT_CENTER[1]),
    "BodyDiaDim": (FRONT_CENTER[0] + 0.060, FRONT_CENTER[1] + 0.010),
    "CupDepth": (FRONT_CENTER[0] + 0.045, FRONT_CENTER[1] - 0.020),
}
END_KEEP = {
    "SlotWDim": (END_CENTER[0] + 0.055, END_CENTER[1] - 0.015),
}
CUP_KEEP = {
    "CupDiaDim": (CUP_CENTER[0] + 0.050, CUP_CENTER[1]),
}
# Only NON-tolerance annotation survives here. Every band moved onto the model
# dimension in build_cone_tip_adjuster (cone_tip_adjuster_spec.GENERAL_TOL_MM /
# CUP_DIA_BAND), where SolidWorks renders it natively.
#
# The two entries that remain are sheet annotation, not specification:
#   BodyDiaDim - the thread designation, already derived from the spec's THREAD.
#   CupDepth   - the machining instruction for the marked blind-hole depth.
DIMENSION_CALLOUTS = {
    "BodyDiaDim": f"{THREAD} UNC",
    "CupDepth": "DEEP",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-adjuster source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Cone Tip Adjuster Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"cone tip adjuster; {THREAD} slotted set screw; black oxide",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    cup = place_view(adapter, str(SOURCE), "*Top", *CUP_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # The elevation shows the blind cup as hidden lines; the head end view
    # exposes the driver slot across the OD.
    for view in (front, end, cup):
        set_hidden_lines_visible(adapter, view)
    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    if (thread_seeds, thread_instances) != (1, 1):
        raise RuntimeError(
            "expected one cosmetic external thread in front view, got "
            f"{thread_seeds} seeds / {thread_instances} instances"
        )

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    cup_annotations = curate_view_dimensions(
        adapter, cup, keep=CUP_KEEP, view_label="cup end"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *end_annotations, *cup_annotations],
        {
            name: text
            for name, text in DIMENSION_CALLOUTS.items()
            if name != "BodyDiaDim"
        },
    )
    set_dimension_callouts(
        adapter,
        front_annotations,
        {"BodyDiaDim": DIMENSION_CALLOUTS["BodyDiaDim"]},
        location="above",
    )
    set_reference_dimensions(adapter, front_annotations, ("BodyDiaDim",))
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the head end view")
    if not auto_center_marks(adapter, cup, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the cup-end view")

    if add_note(adapter, "SLOT END VIEW", 0.070, 0.132) is None:
        raise RuntimeError("failed to label slot end view")
    if add_note(adapter, "CUP END VIEW", 0.165, 0.132) is None:
        raise RuntimeError("failed to label cup end view")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Adjuster Manufacturing Drawing",
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

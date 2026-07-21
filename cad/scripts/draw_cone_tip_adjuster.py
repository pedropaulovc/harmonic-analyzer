r"""Create the curated machinist drawing for the cone tip adjuster set screw."""

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
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_reference_dimensions,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_adjuster_spec import THREAD
from solidworks_mcp.adapters.solidworks.drawing import (
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

# The screw is 14 mm long x Ø6.2: at 4:1 the elevation is 56 x 25 mm. Third
# angle: the head-end view (with the driver slot) sits BELOW the elevation; the
# notes block sits clear at the bottom.
FRONT_CENTER = (0.095, 0.180)
END_CENTER = (0.095, 0.100)
ISO_CENTER = (0.300, 0.160)

FRONT_KEEP = {
    "BodyLenDim": (FRONT_CENTER[0] - 0.045, FRONT_CENTER[1]),
}
END_KEEP = {
    "BodyDiaDim": (END_CENTER[0] + 0.055, END_CENTER[1] + 0.015),
    "SlotWDim": (END_CENTER[0] + 0.055, END_CENTER[1] - 0.015),
}
DIMENSION_CALLOUTS = {"BodyDiaDim": f"{THREAD} UNC-2A"}


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
            3: "cone tip adjuster; 5/16-18 slotted set screw; blued",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # The elevation shows the blind cup as hidden lines; the head end view
    # exposes the driver slot across the OD.
    for view in (front, end):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *end_annotations], DIMENSION_CALLOUTS
    )
    # The OD is the modeled thread MINOR diameter; the 5/16-18 callout governs.
    # Box it in parentheses so it reads as reference, not a controlling dim.
    set_reference_dimensions(adapter, end_annotations, {"BodyDiaDim"})
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the head end view")

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

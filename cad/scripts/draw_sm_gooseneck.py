r"""Create the curated machinist drawing for the gooseneck counter-spring post.

The SLDPRT remains authoritative.  This recipe supplies only the post's
elevation + isometric views, the bend-radius / arm-run dimensions, and the
manufacturing notes; every shared sheet/template, import, curation, and export
behavior lives in ``_drawing_common``.

The post is a polished chrome Ø16 x 2-wall tube with a tall vertical leg,
an R51 quarter bend and a horizontal arm. Its flush brazed Ø12 x 8 end plug
has an axial native #6-32 UNC-2B through tap; the made MHA-SM-004 spring screw
is NOT part of this weldment. The approximately 501 mm tall post keeps the
elevation at 1:3 and the isometric at 1:4.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck.py sm-gooseneck
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import DIAMETER_TOLERANCE_MM, _verify_tap_metadata
from sm_gooseneck_spring_joint import TAP_DRILL_DIA, TAP_SPEC
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["sm_gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 whole sheet (~501 mm tall post)

# Sheet layout (meters).  The elevation (front) shows the goose-neck profile
# (leg + bend + arm) right of centre so the notes clear it; the isometric (1:4)
# sits far right; the notes fill the lower-left.
FRONT_CENTER = (0.180, 0.150)
ISO_CENTER = (0.350, 0.150)
# No arm-end detail: this legacy sheet retains the model-stamped plug/tap
# schedule in its notes. The separate made screw appears only in the assembly
# package, so neither view needs an integral-head reference or detail fence.

# Per-view survivors of the marked-dimension import: the bend radius (R51) and
# the horizontal arm run, both on the Front-plane sweep path (so both project to
# the elevation).  Positions are near the bend/arm at the top of the view.
FRONT_KEEP = {
    "BendRadius": (0.225, 0.212),
    "ArmRun": (0.150, 0.250),
}


def _require_saved_tap(model: Any) -> None:
    """Require the saved native receiver's size, class, ends and drill diameter."""
    feature = _early_bound(model, "IPartDoc").FeatureByName("ThreadBore")
    if feature is None:
        raise RuntimeError("saved gooseneck has no native ThreadBore")
    feature = _early_bound(feature, "IFeature")
    if str(feature.GetTypeName2()) != "HoleWzd":
        raise RuntimeError("saved gooseneck ThreadBore is not a native Hole Wizard tap")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("saved gooseneck ThreadBore has no hole definition")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    if str(definition.FastenerSize).strip() != TAP_SPEC.size:
        raise RuntimeError("saved gooseneck ThreadBore has the wrong thread size")
    _verify_tap_metadata(definition, TAP_SPEC, "saved gooseneck ThreadBore")
    diameter = float(definition.ThruTapDrillDiameter) * 1000.0
    if abs(diameter - TAP_DRILL_DIA) > DIAMETER_TOLERANCE_MM:
        raise RuntimeError(
            f"saved gooseneck tap drill {diameter:.3f} != {TAP_DRILL_DIA:.3f} mm"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", await adapter.open_model(str(SOURCE)))
    _require_saved_tap(adapter.currentModel)
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
            "Elevation View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
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
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; chrome tube; 90-deg bend; spring post",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 3))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    # 0.114 (was 0.105): machinist round 2 grew the notes to 22 lines and the
    # block crossed the bottom zone border by 16.1 mm; the trim reclaims ~2
    # lines and the raise covers the rest (nothing sits above until the
    # elevation leg at x>0.16).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.114)
    add_property_linked_note(adapter, "Elevation View Note", 0.160, 0.022)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.077)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
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

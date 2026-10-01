r"""Create the manufacturing drawing for the latch hook (MHA-127).

One face view (``*Front``, the plane of the strip) carries everything the
maker needs: the forming template's inner-edge radii and their tangency run,
the free end's run, and the three drilled holes with their runs -- every run
measured from the square top cut, the sheet's datum edge.  The strip's width
and thickness are stock and print in the notes as a reference; the holes are
centred on the width by note.  An isometric view shows the flat strip.
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
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from latch_hook_geometry import LOCAL_X_MAX, LOCAL_X_MIN, LOCAL_Y_MAX, LOCAL_Y_MIN
from latch_hook_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_HOLE_CALLOUT,
    RIVET_HOLE_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["latch_hook"]
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

# A 105 x 17 strip with Ø1.65 holes 3.9 apart: 3:1 keeps the rivet pair's
# two .XXX dimensions legible and the whole strip on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.200, 0.170)
ISO_CENTER = (0.330, 0.100)
NOTES_XY = (0.020, 0.100)
# The view centre sits on the part's bounding-box centre (local X, Y, mm).
_MODEL_CENTER = ((LOCAL_X_MIN + LOCAL_X_MAX) / 2.0, (LOCAL_Y_MIN + LOCAL_Y_MAX) / 2.0)


def _sheet(model_x: float, model_y: float) -> tuple[float, float]:
    """Sheet XY (m) of a local model point (mm) on the face view."""
    return (
        FRONT_CENTER[0] + (model_x - _MODEL_CENTER[0]) * _S / 1000.0,
        FRONT_CENTER[1] + (model_y - _MODEL_CENTER[1]) * _S / 1000.0,
    )


DIMENSION_CALLOUTS = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "RivetHoleDia": RIVET_HOLE_CALLOUT,
}

# Text positions: the runs stacked above the strip, shortest nearest; the
# template radii below their edges; the rivet pair's dimensions right of the
# top cut.
FRONT_KEEP = {
    "JunctionRun": _sheet(-26.0, 10.0),
    "PinHoleRun": _sheet(-38.0, 16.0),
    "TipRun": _sheet(-50.0, 22.0),
    "InnerR1": _sheet(-25.0, -20.0),
    "InnerR2": _sheet(-95.0, -20.0),
    "PinHoleDia": _sheet(-70.0, -26.0),
    "RivetRun": _sheet(10.0, 7.0),
    "RivetPitch": _sheet(12.0, -1.0),
    "RivetHoleDia": _sheet(5.0, 17.0),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open latch-hook source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet_obj = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Latch Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "latch hook; edgewise-bent steel strip",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each dimension's title-block row) and the drilled-hole
    # bands are authored on the part; the sheet only proves the import kept
    # them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0015):
        raise RuntimeError(
            "failed to add ASME center marks to the latch-hook face view"
        )
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Latch Hook Manufacturing Drawing",
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

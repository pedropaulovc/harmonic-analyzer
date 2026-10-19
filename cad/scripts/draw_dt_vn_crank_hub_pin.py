r"""Create the curated manufacturing drawing for MHA-DT-VN-59.

The pin is a plain straight dowel with an extraction thread tapped through its
axis from the flush outer end. Its two native dimensions define the part;
the extraction-entry end view's associative Hole Wizard callout owns the thread
identity. That view looks from -Z at the Z=0 entry, not at the far drill exit.
The opened source's saved tap metadata and the rendered callout are read back
before the drawing can be published.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

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
from _drawing_dimensions import assert_imported_precision, set_reference_dimensions
from _drawing_edges import scan_view_edges
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _holes import _verify_tap_metadata
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_vn_crank_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_SUMMARY,
    DRAWING_TITLE,
    PIN_DIA,
    PULL_THREAD_HOLE,
    PULL_THREAD_TAP_DRILL,
    REFERENCE_DIMENSIONS,
    REDUNDANT_NOTE_SUBSTRINGS,
)


SPEC = DRAWINGS_BY_NAME["dt_vn_crank_hub_pin"]
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

SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
END_CENTER = (0.095, 0.180)
RIGHT_CENTER = (0.225, 0.180)
ISO_CENTER = (0.355, 0.180)
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + HALF_DIA + 0.016),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.016),
}
# The extraction entry is the -Z-facing end at local Z=0; *Front looks from
# +Z onto the opposite drill exit, whose native callout can omit the thread.
# Select the actual entry rim by its model geometry, not a screen-space hit.
# Text stays above the Ø40-sheet pin outline (top at y 0.200), left of PinDia.
THREAD_NOTE_XY = (END_CENTER[0] + 0.027, END_CENTER[1] + HALF_DIA + 0.016)


def _pull_thread_entry_edge(view: Any) -> Any:
    """The visible Ø1.6 rim at the Hole Wizard's Z=0 extraction entry."""
    return (
        scan_view_edges(view, label="MHA-VN-029 extraction entry")
        .circle_at(
            (0.0, 0.0, 0.0),
            PULL_THREAD_TAP_DRILL / 2.0,
            axis=(0.0, 0.0, 1.0),
            label="MHA-VN-029 pull thread entry",
        )
        .edge
    )


def _require_pull_thread_definition(definition: Any) -> None:
    """Validate actual feature data, including drill and thread termination."""
    _verify_tap_metadata(definition, PULL_THREAD_HOLE, "MHA-VN-029 saved pull thread")
    if str(definition.FastenerSize).strip() != PULL_THREAD_HOLE.size:
        raise RuntimeError("MHA-VN-029 saved extraction thread is not M2x0.4")
    if not math.isclose(
        float(definition.ThruTapDrillDiameter) * 1000.0,
        PULL_THREAD_TAP_DRILL,
        rel_tol=0.0,
        abs_tol=0.005,
    ):
        raise RuntimeError("MHA-VN-029 saved tap drill is not 1.6 mm")


def _require_saved_pull_thread(model: Any) -> None:
    """Read the feature from the SLDPRT opened by this drawing, not its recipe."""
    feature = _early_bound(model, "IPartDoc").FeatureByName("PullThread")
    if feature is None:
        raise RuntimeError("MHA-VN-029 saved PullThread feature is missing")
    feature = _early_bound(feature, "IFeature")
    if str(feature.GetTypeName2()) != "HoleWzd":
        raise RuntimeError("MHA-VN-029 saved PullThread is not a Hole Wizard feature")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("MHA-VN-029 saved pull-thread definition is missing")
    _require_pull_thread_definition(_early_bound(definition, "IWizardHoleFeatureData2"))


def _require_pull_thread_callout(display: Any) -> None:
    """Check rendered native text without replacing its associative variables."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    text = " ".join(
        str(data.GetTextAtIndex(index)) for index in range(int(data.GetTextCount()))
    )
    normalized = "".join(text.upper().split()).replace("×", "X")
    if (
        re.search(re.escape(PULL_THREAD_HOLE.size.upper()) + r"(?![\d.])", normalized)
        is None
        or re.search(r"\bTHRU(?:\s+ALL)?\b", text, re.IGNORECASE) is None
        or "<HOLE-DEPTH>" in normalized
    ):
        raise RuntimeError(
            f"MHA-VN-029 native callout lost M2x0.4 through semantics: {text!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-hub-pin source", await adapter.open_model(str(SOURCE)))
    _require_saved_pull_thread(adapter.currentModel)
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(adapter, drawing_model, DRAWING_SUMMARY)

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (end, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_reference_dimensions(adapter, annotations, REFERENCE_DIMENSIONS)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-DT-VN-59 end view")
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="MHA-DT-VN-59 axis centerline",
    )
    thread_callout = add_native_hole_callout(
        adapter,
        end,
        edge=_pull_thread_entry_edge(end),
        callout_xy=THREAD_NOTE_XY,
        label="MHA-VN-029 pull thread callout",
    )
    _require_pull_thread_callout(thread_callout)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.082)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title=DRAWING_TITLE,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # run956fee printed one native "Tapped Hole" label beside the callout;
        # its leader crossed the callout's. The real callout now owns the thread.
        redundant_note_substrings=REDUNDANT_NOTE_SUBSTRINGS,
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

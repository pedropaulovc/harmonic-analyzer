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
from _holes import _standard, _verify_tap_metadata
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_vn_crank_hub_pin_native import read_hole_wizard_metadata
from dt_vn_crank_hub_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
    PULL_THREAD_HOLE,
    PULL_THREAD_NATIVE_THROUGH_TAP_TYPES,
    PULL_THREAD_TAP_DRILL,
    PULL_THREAD_TAP_DRILL_DESIGNATION,
    PULL_THREAD_WALL_CALLOUT,
    REFERENCE_DIMENSIONS,
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
# Removal selector for the redundant automatic Hole Wizard label, not print text.
FINAL_SHEET_REMOVED_NOTES = ("Tapped Hole",)


def _pull_thread_entry_edge(view: Any) -> Any:
    """The visible tap-drill rim at the Hole Wizard's Z=0 extraction entry."""
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
    definition = read_hole_wizard_metadata(
        definition, label="MHA-VN-029 saved pull thread"
    )
    _verify_tap_metadata(definition, PULL_THREAD_HOLE, "MHA-VN-029 saved pull thread")
    # FastenerType2 reports -1 on this native #56 tap. Use the documented
    # saved-feature Type contract instead; do not accept an unknown type.
    native_type = definition.Type
    if native_type not in PULL_THREAD_NATIVE_THROUGH_TAP_TYPES:
        raise RuntimeError(
            f"MHA-VN-029 saved extraction Type {native_type!r} is not a through tap"
        )
    for member, expected in (
        ("Standard2", _standard(PULL_THREAD_HOLE.kind)),
        ("FastenerSize", PULL_THREAD_HOLE.size),
    ):
        actual = getattr(definition, member)
        if actual != expected:
            raise RuntimeError(
                f"MHA-VN-029 saved extraction {member} {actual!r} != {expected!r}"
            )
    if not math.isclose(
        float(definition.ThruTapDrillDiameter) * 1000.0,
        PULL_THREAD_TAP_DRILL,
        rel_tol=0.0,
        abs_tol=0.005,
    ):
        raise RuntimeError(
            f"MHA-VN-029 saved tap drill is not #56 ({PULL_THREAD_TAP_DRILL:.4f} mm)"
        )


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


def _name_pull_thread_drill(display: Any) -> None:
    """Name the native drill without replacing its diameter or either THRU."""
    display = _early_bound(display, "IDisplayDimension")
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    attributes = {
        **{f"definition_{part}": text for part, text in definitions.items()},
        **{f"resolved_{part}": text for part, text in resolved.items()},
    }
    _telemetry.info("MHA-VN-029 original native pull-thread callout", **attributes)
    _telemetry.event("drawing.pull_thread_callout", **attributes)
    drill_token = "<hw-thrutapdrldia>"
    drill_parts = [
        part for part, text in definitions.items() if drill_token in text.lower()
    ]
    if (
        len(drill_parts) != 1
        or sum(text.lower().count(drill_token) for text in definitions.values()) != 1
    ):
        raise RuntimeError("MHA-VN-029 native callout has no unique tap-drill row")
    definition_part = drill_parts[0]
    original = definitions[definition_part]
    if original.lower().count("<mod-diam>") != 1 or len(original.splitlines()) != 1:
        raise RuntimeError(
            "MHA-VN-029 native tap-drill row has no unique diameter token"
        )
    prefix = f"{PULL_THREAD_TAP_DRILL_DESIGNATION} DRILL "
    definitions[definition_part] = prefix + original
    resolved[definition_part - 4] = prefix + resolved[definition_part - 4]
    display.SetText(definition_part - 4, definitions[definition_part])
    # Check all eight fields exactly: even a successful setter can alter a
    # different row or flatten the associative definition into resolved text.
    actual_definitions = {
        part: str(display.GetText(part) or "") for part in definitions
    }
    actual_resolved = {part: str(display.GetText(part) or "") for part in resolved}
    if actual_definitions != definitions or actual_resolved != resolved:
        raise RuntimeError(
            "MHA-VN-029 native drill name or callout fields did not persist"
        )


def _require_pull_thread_callout(display: Any) -> None:
    """Check rendered native text without replacing its associative variables."""
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    text = " ".join(
        str(data.GetTextAtIndex(index)) for index in range(int(data.GetTextCount()))
    )
    normalized = "".join(text.upper().split()).replace("×", "X")
    # Preserve row boundaries: ALL 0-80 must not collapse into ALL0-80.
    thread_text = re.sub(r"\s*-\s*", "-", text)
    thread_token = re.escape(PULL_THREAD_HOLE.size.upper().lstrip("#"))
    if (
        re.search(r"(?<![\w#])#?" + thread_token + r"(?![\d.])", thread_text) is None
        or re.search(r"\bUNF\b", text, re.IGNORECASE) is None
        or re.search(r"\b" + PULL_THREAD_HOLE.thread_class + r"\b", text) is None
        or re.search(r"\bTHRU(?:\s+ALL)?\b", text, re.IGNORECASE) is None
        or "<HOLE-DEPTH>" in normalized
    ):
        raise RuntimeError(
            f"MHA-VN-029 native callout lost {PULL_THREAD_HOLE.size} through semantics: {text!r}"
        )


def _append_pull_thread_wall(display: Any) -> None:
    """Append a nominal fact, preserving every native Hole Wizard definition."""
    display = _early_bound(display, "IDisplayDimension")
    # As in draw_ch_channel_lever: read the below DEFINITION (8), not its
    # resolved text (4), so the existing drill row keeps its native variables.
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    below = definitions[8].replace("\r", "").rstrip()
    updated = (
        f"{below}\n{PULL_THREAD_WALL_CALLOUT}" if below else PULL_THREAD_WALL_CALLOUT
    )
    resolved_below = resolved[4].replace("\r", "").rstrip()
    expected_resolved = (
        f"{resolved_below}\n{PULL_THREAD_WALL_CALLOUT}"
        if resolved_below
        else PULL_THREAD_WALL_CALLOUT
    )
    display.SetText(4, updated)  # swDimensionTextCalloutBelow
    if (
        str(display.GetText(8) or "").replace("\r", "") != updated
        or str(display.GetText(4) or "").replace("\r", "") != expected_resolved
        or any(
            str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
        )
        or any(str(display.GetText(part) or "") != resolved[part] for part in (1, 2, 3))
    ):
        raise RuntimeError(
            "MHA-VN-029 wall fact or native callout definitions did not persist"
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
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Hub Axial Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank hub seam pin; axial key; straight gauge; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

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
    _name_pull_thread_drill(thread_callout)
    _require_pull_thread_callout(thread_callout)
    _append_pull_thread_wall(thread_callout)
    _require_pull_thread_callout(thread_callout)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.082)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Hub Axial Pin Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # run956fee printed one native "Tapped Hole" label beside the callout;
        # its leader crossed the callout's. The real callout now owns the thread.
        redundant_note_substrings=FINAL_SHEET_REMOVED_NOTES,
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

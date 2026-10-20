r"""Create the two-sheet reference package for shared McMaster 9666K56 wire.

LeverWire retains the note-based straight rest-run sheet at 1:5. PenWire retains
its associative Depth dimension and 2:1 views. Neither straight rest run is a
developed cut length: the source does not define the formed hook or drum wrap,
and both member notes retain the DO NOT RELEASE limitation.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view, view_name

import _telemetry
from _check import check
from _com import _early_bound
from _config import parts
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build

SPEC = DRAWINGS_BY_NAME["sh_vn_music_wire"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_NAMES = ("LeverWire", "PenWire")
SHEET_SCALES = {"LeverWire": (1, 1), "PenWire": (2, 1)}
WIRE_SCALES = {"LeverWire": (1, 5), "PenWire": (2, 1)}
FRONT_CENTERS = {"LeverWire": (0.135, 0.150), "PenWire": (0.110, 0.155)}
ISO_CENTERS = {"LeverWire": (0.320, 0.160), "PenWire": (0.300, 0.170)}
FRONT_KEEPS = {"LeverWire": {}, "PenWire": {"Depth": (0.078, 0.155)}}
_MEMBER_LABELS = {"LeverWire": "LEVER WIRE", "PenWire": "PEN WIRE"}
_NOTE_POSITIONS = {
    "LeverWire": (
        ("Manufacturing Notes", 0.020, 0.075),
        ("Front View Note", 0.100, 0.100),
        ("Isometric View Note", 0.300, 0.100),
    ),
    "PenWire": (
        ("Manufacturing Notes", 0.016, 0.086),
        ("Elevation View Note", 0.040, 0.036),
        ("Isometric View Note", 0.270, 0.100),
    ),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    row = parts(PART_STEM)
    quantities = row["configuration_quantities"]
    if set(quantities) != set(SHEET_NAMES):
        raise RuntimeError("music-wire sheets do not match the registry members")
    total = sum(int(quantity) for quantity in quantities.values())
    if total != int(row["quantity"]):
        raise RuntimeError("music-wire installed quantities do not match the family")
    note_keys = tuple(
        f"{configuration} {property_name}"
        for configuration in SHEET_NAMES
        for property_name, _, _ in _NOTE_POSITIONS[configuration]
    )
    check("open shared music-wire source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            *note_keys,
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            *note_keys,
        ),
    )
    drawing_model, _ = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALES[SHEET_NAMES[0]],
        layout=SPEC.layout,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Shared Music Wire Reference Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "music wire; lever wire; pen wire; straight rest runs",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="shared music-wire members"
    )
    draw = _early_bound(drawing_model, "IDrawingDoc")
    configured_views = []
    linked_notes = []
    for configuration in SHEET_NAMES:
        if not draw.ActivateSheet(configuration):
            raise RuntimeError(f"cannot activate music-wire sheet {configuration!r}")
        front = _early_bound(
            place_view(
                adapter,
                str(SOURCE),
                "*Front",
                *FRONT_CENTERS[configuration],
                scale=WIRE_SCALES[configuration],
            ),
            "IView",
        )
        iso = _early_bound(
            place_view(
                adapter,
                str(SOURCE),
                "*Isometric",
                *ISO_CENTERS[configuration],
                scale=WIRE_SCALES[configuration],
            ),
            "IView",
        )
        for view in (front, iso):
            view.ReferencedConfiguration = configuration
        rebuild_drawing(adapter, label=f"{configuration} wire views")
        for view in (front, iso):
            if str(view.ReferencedConfiguration) != configuration:
                raise RuntimeError(
                    f"{configuration}: view configuration did not persist"
                )
            view.UseSheetScale = 0
            view.ScaleRatio = double_array(WIRE_SCALES[configuration])
            set_hidden_lines_removed(adapter, view)
            configured_views.append((configuration, view))
        property_view = view_name(adapter, front)
        if not property_view:
            raise RuntimeError(f"{configuration}: missing property-source view")
        draw.GetCurrentSheet().CustomPropertyView = property_view
        curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEPS[configuration],
            view_label=f"{configuration} front",
        )
        for property_name, x, y in _NOTE_POSITIONS[configuration]:
            key = f"{configuration} {property_name}"
            note = add_property_linked_note(adapter, key, x, y)
            linked_notes.append((configuration, note, str(properties[key])))
        caption = (
            f"{_MEMBER_LABELS[configuration]}  "
            f"QTY {int(quantities[configuration])} INSTALLED RUN; "
            f"SHARED FAMILY: {total} RUNS, NOT COILS"
        )
        note = add_note(adapter, caption, 0.020, 0.255)
        if note is None:
            raise RuntimeError(f"{configuration}: cannot add installed-quantity note")
        linked_notes.append((configuration, note, caption))

    def assert_configured_sheets() -> None:
        for configuration, view in configured_views:
            if not draw.ActivateSheet(configuration):
                raise RuntimeError(f"cannot read back sheet {configuration!r}")
            if str(view.ReferencedConfiguration) != configuration:
                raise RuntimeError(
                    f"{configuration}: final view configuration changed"
                )
            source = str(view.GetReferencedModelName()).replace("\\", "/").casefold()
            if source != str(SOURCE).replace("\\", "/").casefold():
                raise RuntimeError(f"{configuration}: final view source changed")
        for configuration, note, expected in linked_notes:
            if not draw.ActivateSheet(configuration):
                raise RuntimeError(f"cannot read back notes on {configuration!r}")
            text = str(adapter._get_attr_or_call(note, "GetText") or "")
            if text.replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
                raise RuntimeError(
                    f"{configuration}: native linked note resolved to {text!r}, "
                    f"expected {expected!r}"
                )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Shared Music Wire Reference Drawing",
        scale=SHEET_SCALES[SHEET_NAMES[0]],
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_scales=SHEET_SCALES,
        settled_checks=(assert_configured_sheets,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

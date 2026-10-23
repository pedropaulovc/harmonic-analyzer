r"""Create the one-sheet purchase drawing for shared McMaster 9666K56 wire.

Replacement needs the supplier wire diameter and the purchase identity, not
the installed members' straight rest runs: the formed ends, wraps and cut
lengths are shop-made at assembly. The sheet shows the supplier circle from
the zero-body SUPPLIER_REFERENCE state with its native diameter, and one
property-linked note naming the SKU; the title block carries the material.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _paths import CAD_ROOT
from _session import run_build
from _supplier_wire_stock_drawing import STOCK_SCALE, add_wire_section

SPEC = DRAWINGS_BY_NAME["sh_vn_music_wire"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
_TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)
NOTES_XY = (0.020, 0.075)


def _assert_notes(note: Any, expected: str) -> None:
    text = str(_early_bound(note, "INote").GetText() or "").replace("\r\n", "\n")
    if text != expected.replace("\r\n", "\n"):
        raise RuntimeError(f"linked note resolved to {text!r}, expected {expected!r}")
    extent = tuple(float(value) for value in (_early_bound(note, "INote").GetExtent() or ()))
    if len(extent) != 6 or not all(map(math.isfinite, extent)) or (
        extent[3] <= extent[0] or extent[4] <= extent[1]
    ):
        raise RuntimeError(f"linked note has no resolved native extent: {extent!r}")
    box = (extent[0], extent[1], extent[3], extent[4])
    if not (
        _BORDER[0] <= box[0] and _BORDER[1] <= box[1]
        and box[2] <= _BORDER[2] and box[3] <= _BORDER[3]
    ) or (
        box[0] < _TITLE_BLOCK[2] and _TITLE_BLOCK[0] < box[2]
        and box[1] < _TITLE_BLOCK[3] and _TITLE_BLOCK[1] < box[3]
    ):
        raise RuntimeError(f"linked note leaves its printable field: {box!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open shared music-wire source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        adapter.currentModel,
        ("Number", "Revision", "Title", "Material Specification", "Finish",
         "Manufacturing Notes"),
        required=("Number", "Material Specification", "Finish", "Manufacturing Notes"),
    )
    drawing_model, _ = new_project_drawing(
        adapter, property_view=PART_STEM, scale=STOCK_SCALE, layout=SPEC.layout,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Shared Music Wire Purchase Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "music wire; McMaster-Carr 9666K56; supplier wire diameter",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    section = add_wire_section(adapter, SOURCE)
    note = add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    def settled() -> None:
        section()
        _assert_notes(note, str(properties["Manufacturing Notes"]))

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Shared Music Wire Purchase Drawing",
        scale=STOCK_SCALE,
        layout=SPEC.layout,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

r"""Create the curated machinist drawing for the platen guide.

The SLDPRT remains authoritative.  This recipe supplies only the platen-guide
views, dimensions, hole groups, and manufacturing notes; shared sheet/template,
leader, reopen, and artifact behavior lives in ``_drawing_common``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_platen_guide.py platen-guide
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    import_cosmetic_threads,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_platen_guide import HOLE_X as THROUGH_X
from build_platen_guide import SCREW_STATION_X as BLIND_X
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
)


SPEC = DRAWINGS_BY_NAME["platen_guide"]
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

# The 1:1 front view is 300 mm long and centred at sheet X=0.190 m, so its
# left end is X=0.040 m.  The circular-edge pick Y was measured and then
# read-validated against every expected attached entity in live SolidWorks.
FRONT_LEFT_X_M = 0.040
FRONT_VIEW_Y_M = 0.110
FRONT_HOLE_Y_M = 0.1111
FRONT_BOTTOM_Y_M = FRONT_HOLE_Y_M - 0.0025
# 0.020, not 0.014: the sheet's DRAWN frame rule is at x=0.0159, inboard of the
# 12.7 mm zone margin the audit checks, so a table left edge at 0.0143 passed the
# gate while printing 1.6 mm over the frame (measured). 0.020 clears the rule
# whether or not the DRWDOT is later re-centred onto its declared margins.
HOLE_TABLE_X_M = 0.020
HOLE_TABLE_Y_M = 0.258
THREAD_DESIGNATION = "#4-40 UNC-2B"
THREAD_MAJOR_DIA_MM = 2.845
THREAD_PITCH_MM = 25.4 / 40.0
THREAD_TAP_DRILL_MM = 2.261


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen-guide source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        source_model,
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
    drawing_model, sheet = new_project_drawing(adapter, property_view=PART_STEM)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Guide Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen guide; manufacturing drawing; #4-40 UNC",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(
        adapter, str(SOURCE), "*Front", 0.190, FRONT_VIEW_Y_M, scale=(1, 1)
    )
    right = place_view(adapter, str(SOURCE), "*Right", 0.370, 0.110, scale=(1, 1))
    # A 300 mm bar drawn isometrically at the 1:1 sheet scale spans ~237 x 133 mm,
    # so this view's outline nearly fills the sheet's upper half: at y=0.210 its
    # top ran 11.2 mm into the 12.7 mm zone band. Dropped to 0.196 (~2.8 mm of
    # top clearance). It cannot shrink instead -- a view at a scale other than
    # the sheet's must be labelled, and the only note helpers are property-linked
    # (this part declares no "Isometric View Note"); nor move left (the hole
    # table ends at x=0.159) or right (its box already reaches x~0.410 against
    # the 0.4191 margin).
    iso = place_view(adapter, str(SOURCE), "*Isometric", 0.285, 0.196, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    expected_thread_instances = len(BLIND_X)
    if thread_instances != expected_thread_instances:
        raise RuntimeError(
            f"front view has {thread_seeds} cosmetic-thread seed(s) / "
            f"{thread_instances} instance(s); expected {expected_thread_instances}"
        )
    removed_thread_notes = remove_notes_matching(adapter, "#4-40")
    _telemetry.info(
        f"front view imported {thread_seeds} cosmetic-thread seed(s) as "
        f"{thread_instances} instance(s); removed {removed_thread_notes} "
        "automatic callout note(s)"
    )

    # Keep only overall length; hole coordinates live in the native hole table.
    curate_view_dimensions(
        adapter, front, keep={"Length": (0.190, 0.135)}, view_label="front"
    )
    curate_view_dimensions(
        adapter,
        right,
        keep={"Depth": (0.370, 0.095), "Height": (0.385, 0.110)},
        view_label="right",
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    stations = tuple(sorted((*THROUGH_X, *BLIND_X)))
    insert_hole_table(
        adapter,
        front,
        datum_xy=(FRONT_LEFT_X_M, FRONT_BOTTOM_Y_M),
        hole_points=tuple(
            (FRONT_LEFT_X_M + station / 1000.0, FRONT_HOLE_Y_M)
            for station in stations
        ),
        anchor_xy=(HOLE_TABLE_X_M, HOLE_TABLE_Y_M),
        label="platen-guide",
    )

    # Native datum reference frame and feature controls replace former notes 5-7.
    # Right view shows the 10 mm depth: left edge is the blind-hole entry face A.
    datum_a_edge = (0.365, 0.110)
    datum_b_edge = (0.190, FRONT_BOTTOM_Y_M)
    datum_c_edge = (FRONT_LEFT_X_M, FRONT_HOLE_Y_M)
    add_datum_feature(
        adapter,
        right,
        edge_xy=datum_a_edge,
        # Level with the face it names, in the 25 mm gap between the front view's
        # end (x=0.340) and the right view (x=0.365), so the leader is short and
        # horizontal and its arrow lands ON the face. Below the view instead, the
        # arrow ran onto the 10.00 dimension's extension line ~22 mm down, where
        # a datum tag reads as the center plane rather than the surface. The box
        # top (y=0.118) still clears the isometric's outline at y=0.131.
        symbol_xy=(0.352, 0.110),
        datum="A",
        label="platen-mating face",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=datum_b_edge,
        symbol_xy=(0.190, 0.098),
        datum="B",
        label="guide bottom edge",
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=datum_c_edge,
        symbol_xy=(0.028, FRONT_HOLE_Y_M),
        datum="C",
        label="guide end edge",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=datum_a_edge,
        # Was (0.325, 0.145) -- under the isometric, so its leader ran across
        # that view. Below the view instead; the leader reaches the face at
        # y=0.110 while staying under the front view's lower edge (y=0.104).
        frame_xy=(0.312, 0.092),
        characteristic="flatness",
        tolerance="0.10",
        label="platen-mating face flatness",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(0.375, 0.110),
        # Below-right of the view (was (0.382, 0.145), under the isometric).
        # x=0.400 keeps the frame's 8 mm half-box inside the 0.4191 right margin
        # and clear of the 5.00 height dimension at (0.385, 0.110).
        frame_xy=(0.400, 0.086),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="guide opposite-face parallelism",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_LEFT_X_M + BLIND_X[0] / 1000.0, FRONT_HOLE_Y_M),
        frame_xy=(0.105, 0.155),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="9X",
        label="guide hole-pattern position",
    )
    # x=0.020: a note is left-aligned on its anchor, and the drawn frame rule is
    # at x=0.0159 -- 0.014 printed the first glyph through it (the audit's bound
    # is the 12.7 mm zone margin, so it cannot see this).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)

    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Platen Guide Manufacturing Drawing"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

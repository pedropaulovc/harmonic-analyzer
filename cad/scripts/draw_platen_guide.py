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
from _common import CAD_ROOT, _early_bound, check, run_build
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
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_platen_guide import GUIDE_LENGTH
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

# The 1:1 front view is centred at sheet X=0.190 m. Derive its left edge from
# the resized guide so hole-table and datum anchors follow the part geometry.
FRONT_VIEW_X_M = 0.190
FRONT_LEFT_X_M = FRONT_VIEW_X_M - GUIDE_LENGTH / 2000.0
FRONT_VIEW_Y_M = 0.110
FRONT_HOLE_Y_M = 0.1111
FRONT_BOTTOM_Y_M = FRONT_HOLE_Y_M - 0.0025
# Put datum B's symbol midway between the A3/A4 hole axes, clear of both.
DATUM_B_SYMBOL_X_M = FRONT_LEFT_X_M + (BLIND_X[2] + BLIND_X[3]) / 2000.0
# 0.020: the table's left edge lands ~0.3 mm right of its anchor (measured). The
# bound is the 12.7 mm zone margin (~0.0127) the audit checks, which the
# re-centred frame rule now matches (~0.0126); 0.020 keeps the edge clear of both.
HOLE_TABLE_X_M = 0.020
HOLE_TABLE_Y_M = 0.258
THREAD_DESIGNATION = "#4-40 UNC-2B"
THREAD_MAJOR_DIA_MM = 2.845
THREAD_PITCH_MM = 25.4 / 40.0
THREAD_TAP_DRILL_MM = 2.261


def _bottom_surface_edge(view: Any) -> Any:
    """Return the guide's full-length model edge on the bottom datum surface."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="platen-guide bottom edge"):
        edge = _early_bound(raw_edge, "IEdge", "GetStartVertex", "GetEndVertex")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex", "GetPoint")
        end = _early_bound(end, "IVertex", "GetPoint")
        p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        candidates.append((abs(p1[0] - p0[0]), edge))
    if not candidates:
        raise RuntimeError("front view has no model edge on the guide bottom surface")
    span_mm, edge = max(candidates, key=lambda item: item[0])
    if span_mm < GUIDE_LENGTH - 0.1:
        raise RuntimeError(f"guide bottom edge span is only {span_mm:.3f} mm")
    return edge


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
        adapter, str(SOURCE), "*Front", FRONT_VIEW_X_M, FRONT_VIEW_Y_M, scale=(1, 1)
    )
    right = place_view(adapter, str(SOURCE), "*Right", 0.370, 0.110, scale=(1, 1))
    # The guide drawn isometrically at the 1:1 sheet scale fills most of the
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
        adapter, front, keep={"Length": (FRONT_VIEW_X_M, 0.135)}, view_label="front"
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
    datum_b_entity = _bottom_surface_edge(front)
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
        entity=datum_b_entity,
        symbol_xy=(DATUM_B_SYMBOL_X_M, 0.098),
        datum="B",
        # SolidWorks normalizes this legal bottom-edge attachment 0.0507 mm
        # upward when the symbol is committed.  Accept that measured native
        # readback shift; this is an automation check, not a part tolerance.
        label="guide bottom edge",
        position_tolerance_m=0.0001,
    )
    # Dropped to y=0.098 from FRONT_HOLE_Y_M (0.1111): level with the edge, the
    # box is UNAVOIDABLY struck through. `insert_hole_table` gives no control over
    # where SolidWorks auto-places the hole table's origin indicator, and it does
    # NOT land on datum_xy -- measured, it sits ~13.5 mm left of the bar's end, as
    # a vertical Y-axis shaft at x=0.0265 spanning y 0.107..0.122, an origin circle
    # at (0.0266, 0.1076), and a "0" glyph at x 0.0250..0.0279 / y 0.1036..0.1059.
    # At y=0.1111 the tag's box (x 0.0210..0.0281) swallowed that shaft: it ran the
    # box's full height, 0.4 mm from the "C" glyph. So the indicator cannot move
    # and datum C must.
    #
    # LEFT is not available: the 7.1 mm box would now fit the ~12.3 mm corridor
    # between the frame bound (~0.0127) and the shaft, but any box left of the
    # shaft puts its horizontal leader ACROSS the shaft instead -- trading a
    # strikethrough for a crossing. UP hits the "Y" label and the 300.00
    # extension line.
    #
    # y=0.098 is the HIGHEST that clears: box y 0.0945..0.1015 leaves 2.1 mm under
    # the "0" glyph, ~8.3 mm off the re-centred frame rule, and 8 mm left of the
    # "0 -> X" row (x>=0.036, y 0.091..0.0955); the band x 0.017..0.039 is
    # otherwise empty (probed y=0.096/0.100/0.102 -- only the rule and the
    # x=0.0399 extension line).
    #
    # TRADEOFF, deliberate: a datum tag re-attaches at the point on its entity
    # NEAREST the symbol (draw_fulcrum_shaft.py; wheel-axle's datum A proves it for
    # straight edges too -- pick x=0.13125, symbol x=0.13725, triangle rendered at
    # 0.1376). The end edge spans only y 0.1086..0.1136, so a symbol below it slides
    # the triangle to the bottom corner (0.040, 0.1086) rather than mid-edge. The
    # triangle stays ON the end face and the symbol stays outboard of it
    # (dot((-0.012, -0.0106), (-1,0)) = +0.012 > 0), so it still reads as the end
    # datum -- but there is no placement that keeps it mid-edge, because the edge's
    # whole 5 mm lies inside the shaft's span.
    add_datum_feature(
        adapter,
        front,
        edge_xy=datum_c_edge,
        symbol_xy=(0.028, 0.098),
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
        # x=0.390, NOT 0.400: an FCF's anchor is its frame's TOP-LEFT corner and
        # the frame grows RIGHT from it by its full width -- it is not centred.
        # This one ("|//| 0.10 |A|") measures 25.2 mm wide, so x=0.400 put its
        # right edge at 0.4252, over the 0.4191 margin by 6.1 mm. The old comment
        # here reasoned from an "8 mm half-box" -- the audit's since-corrected
        # model, which had it stopping at 0.408 and passed it clean. 0.390 lands
        # the right edge at 0.4152, 3.9 mm inside the margin, and the frame sits
        # at y 0.079..0.086 so it stays clear of the 5.00 height dimension up at
        # (0.385, 0.110).
        frame_xy=(0.390, 0.086),
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
    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
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

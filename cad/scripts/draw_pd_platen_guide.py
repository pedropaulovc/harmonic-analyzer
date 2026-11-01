r"""Create the curated machinist drawing for the platen guide.

The SLDPRT remains authoritative.  This recipe supplies only the platen-guide
views, dimensions, hole groups, GD&T and surface symbol;
sheet/template and export behavior lives in ``_drawing_common``.
Leader behavior lives in ``_drawing_attachment``.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_platen_guide.py pd-platen-guide
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_edges import visible_view_entities
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_tables import insert_hole_table
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import THREAD_MAJOR_MM, blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_pd_platen_guide import (
    GUIDE_LENGTH,
    HOLE_X as REAR_X,
    SCREW_STATION_X as FRONT_X,
)
from pd_platen_guide_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GEOMETRIC_TOLERANCES_IN,
    GUIDE_DEPTH_CALLOUT,
    GUIDE_HEIGHT,
    SURFACE_FINISHES,
    TAPPED_HOLE_SPEC,
    TAP_Y,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_platen_guide"]
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
# The view centres on the rail's outline: its bottom edge (datum B) and the
# tap row stand from that centre by the model's height and TAP_Y.
FRONT_BOTTOM_Y_M = FRONT_VIEW_Y_M - GUIDE_HEIGHT / 2000.0
FRONT_HOLE_Y_M = FRONT_BOTTOM_Y_M + TAP_Y / 1000.0
# Every tap runs through the rail, so the front view shows all nine and one
# table locates them; no second (rear) face view.
HOLE_STATIONS_MM = tuple(sorted(FRONT_X + REAR_X))
# Each tag stands just under the bar, right of its hole, on a short leader to
# the rim: off the outline and the centre marks. A tag's text runs ~5.7 mm
# right of that, past the next hole of a 7.0 pitch pair, where the next tag's
# leader ran through it (farm layout audit after B2: A7 through A6). So in a
# close run every other tag stands above the bar instead.
HOLE_TAG_DX_M = 0.0015
HOLE_TAG_Y_M = FRONT_BOTTOM_Y_M - 0.0025
HOLE_TAG_ABOVE_Y_M = FRONT_BOTTOM_Y_M + GUIDE_HEIGHT / 1000.0 + 0.0061
HOLE_TAG_CLEAR_MM = 9.0


def _tags_above(stations: tuple[float, ...]) -> frozenset[float]:
    """The stations whose tag stands above the bar: in each run closer than
    HOLE_TAG_CLEAR_MM, every other tag after the first."""
    above: set[float] = set()
    for previous, station in zip(stations, stations[1:]):
        if station - previous < HOLE_TAG_CLEAR_MM and previous not in above:
            above.add(station)
    return frozenset(above)


HOLE_TAGS_ABOVE = _tags_above(HOLE_STATIONS_MM)
# Put datum B's symbol midway between the A3/A4 hole axes, clear of both.
DATUM_B_SYMBOL_X_M = FRONT_LEFT_X_M + (FRONT_X[2] + FRONT_X[3]) / 2000.0
# The bar-slide finish lands on the bottom edge (model y 0, front face z 0)
# midway between the A1 and A2 axes, clear of both centre marks. The landing
# is projected from the model at draw time. The symbol is anchored at its
# lower-left; its "SLIDES ON MHA-PD-07" line stands ~20 mm above that anchor
# and runs ~90 mm right (farm layout audit after B2: at y 0.086 it sat at
# y 105.8..112.3 mm, across the tags' leaders). At y 0.068 the line ends under
# the tags (box bottom ~100.2 mm) and left of datum B's tag, right of the
# hole-table origin's "0 -> X" row (ends ~0.078).
BAR_SLIDE_STATION_MM = (FRONT_X[0] + REAR_X[0]) / 2.0
BAR_SLIDE_FINISH_XY = (FRONT_LEFT_X_M + BAR_SLIDE_STATION_MM / 1000.0 - 0.006, 0.068)
# The table fits above the front view; 0.020 also clears the 12.7 mm zone
# margin enforced by the sheet audit.
HOLE_TABLE_X_M = 0.020
HOLE_TABLE_Y_M = 0.258
ISO_CENTER = (0.375, 0.150)
ISO_SCALE = (1, 4)
ISO_NOTE_XY = (0.342, 0.128)
THREAD_DESIGNATION = f"{TAPPED_HOLE_SPEC.size} UNC-{TAPPED_HOLE_SPEC.thread_class}"
THREAD_MAJOR_DIA_MM = THREAD_MAJOR_MM[TAPPED_HOLE_SPEC.size]
THREAD_PITCH_MM = 25.4 / int(TAPPED_HOLE_SPEC.size.rsplit("-", 1)[1])
THREAD_TAP_DRILL_MM = blind_cut_dia_mm(TAPPED_HOLE_SPEC)


def _bottom_surface_edge(view: Any) -> Any:
    """Return the guide's full-length model edge on the bottom datum surface."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="platen-guide bottom edge"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex")
        end = _early_bound(end, "IVertex")
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


def _hole_rim_entities(
    view: Any, stations: tuple[float, ...], *, label: str
) -> tuple[Any, ...]:
    """Return the visible tap-drill rims at the requested model-X stations."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        parameters = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((parameters[0], parameters[6], edge))

    rims: list[Any] = []
    target_radius = THREAD_TAP_DRILL_MM / 2.0
    for station in stations:
        matches = [
            edge
            for x, radius, edge in candidates
            if abs(x - station) <= 0.02 and abs(radius - target_radius) <= 0.02
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"{label} station {station:g} mm has {len(matches)} visible "
                f"tap-drill rims; expected 1"
            )
        rims.append(matches[0])
    return tuple(rims)


def _place_hole_tags(view: Any, table: Any) -> None:
    """Move each native hole tag beside its own hole, on a leader to its rim."""
    stations_by_tag: dict[str, float] = {}
    for row in range(1, int(table.RowCount)):
        tag = str(table.DisplayedText2(row, 0, False) or "").strip()
        x_mm = float(str(table.DisplayedText2(row, 1, False))) * 25.4
        station = min(HOLE_STATIONS_MM, key=lambda s: abs(s - x_mm))
        if abs(station - x_mm) > 0.02 or station in stations_by_tag.values():
            raise RuntimeError(
                f"hole-table row {tag!r} has no unique station: {x_mm:g}"
            )
        stations_by_tag[tag] = station
    moved: set[str] = set()
    for raw in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw, "IAnnotation")
        if int(annotation.GetType()) != 6:  # swNote
            continue
        note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
        tag = str(note.GetText()).strip()
        if tag not in stations_by_tag:
            continue
        if tag in moved:
            raise RuntimeError(f"duplicate native hole tag {tag}")
        station = stations_by_tag[tag]
        hole_x = FRONT_LEFT_X_M + station / 1000.0
        tag_y = HOLE_TAG_ABOVE_Y_M if station in HOLE_TAGS_ABOVE else HOLE_TAG_Y_M
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"failed to give native hole tag {tag} a leader")
        if not annotation.SetPosition2(hole_x + HOLE_TAG_DX_M, tag_y, 0.0):
            raise RuntimeError(f"failed to reposition native hole tag {tag}")
        points = tuple(float(v) for v in annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6 or math.dist(points[-3:-1], (hole_x, FRONT_HOLE_Y_M)) > (
            THREAD_MAJOR_DIA_MM / 2000.0 + 0.0005
        ):
            raise RuntimeError(
                f"native hole tag {tag} leader misses its hole: {points!r}"
            )
        moved.add(tag)
    if moved != set(stations_by_tag):
        raise RuntimeError(
            f"hole tags not found on the front view: {sorted(set(stations_by_tag) - moved)}"
        )
    _telemetry.info(f"hole tags placed beside their holes: {sorted(moved)}")


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
            "Isometric View Note",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    # Three places by default: the hole tables' basic stations sit on the
    # .001 grid (the platen's guide holes) and print in full.
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        layout=SPEC.layout,
        decimals=3,
        unit=part_drawing_unit(PART_STEM),
    )
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    thread_seeds, thread_instances = import_cosmetic_threads(adapter, front)
    expected_thread_instances = len(REAR_X) + len(FRONT_X)
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

    # Keep only the overall length and height; hole coordinates live in the
    # native hole table.
    # The bar's height sits off the front view's east end (the dimension
    # measures the x=Length edge's endpoints, sheet x 0.3248), not beside the
    # right view, where its extension lines would fence the section. At
    # x 0.338 the text clears the front view's box (0.3304) and datum A's tag
    # (0.3485). y 0.110 centres the 3.5 mm text in the 7.4 mm gap between the
    # extension lines (the rail's edges) so neither runs through it. Both
    # dimensions live in the
    # GuideProfile sketch (Front plane). Their places, and the depth's, are the
    # part's (platen_guide_spec.DRAWING_PRECISION); the sheet proves the import
    # kept them.
    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep={"Length": (FRONT_VIEW_X_M, 0.135), "Height": (0.338, 0.110)},
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep={"Depth": (0.370, 0.095)},
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The depth's one-sided band names what it protects (rule 4).
    set_dimension_callouts(adapter, annotations, {"Depth": GUIDE_DEPTH_CALLOUT})
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    hole_table = insert_hole_table(
        adapter,
        front,
        datum_xy=(FRONT_LEFT_X_M, FRONT_BOTTOM_Y_M),
        hole_points=tuple(
            (FRONT_LEFT_X_M + station / 1000.0, FRONT_HOLE_Y_M)
            for station in HOLE_STATIONS_MM
        ),
        hole_entities=_hole_rim_entities(
            front, HOLE_STATIONS_MM, label="platen-guide front"
        ),
        # X LOC = the station from the left face (datum C); Y LOC = the bar's
        # hole-line height above the bottom face, both at .XXX.
        expected_locations_mm=tuple((station, TAP_Y) for station in HOLE_STATIONS_MM),
        anchor_xy=(HOLE_TABLE_X_M, HOLE_TABLE_Y_M),
        label="platen-guide taps",
        unit="in",
        location_places=3,
    )
    _place_hole_tags(front, hole_table)

    # Datums A (platen-mating face), B (bottom edge) and C (left end) frame the
    # tap pattern's position; the right view shows A as its left edge.
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
        label="guide bottom edge",
        # The tag hangs only 10.6 mm below the bottom edge, so a snap-back onto
        # the attachment would pass the default bound; the live readback is
        # 0.0507 mm above the request.
        position_tolerance_m=0.005,
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
        front,
        edge_xy=(FRONT_LEFT_X_M + FRONT_X[0] / 1000.0, FRONT_HOLE_Y_M),
        # Was (0.105, 0.155), above the 269.64 dimension line, which its leader
        # to A1 crossed (leader-crosses-line). Now between the bar and that line,
        # right of the A1 tag: frame y 0.122..0.129 and "9X" down to 0.1174,
        # 3.2 mm under the dimension line and 3.6 mm clear of the A1 tag.
        frame_xy=(0.097, 0.129),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["guide hole-pattern position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="9X",
        label="guide hole-pattern position",
    )
    # The platen hangs by the top rail's bottom face (datum B) on the bar's top
    # edge and slides along it: the one running surface takes the part-owned
    # Ra symbol, landed on that face's edge in the front view.
    add_surface_finish(
        adapter,
        front,
        symbol_xy=BAR_SLIDE_FINISH_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "bar_slide"),
        label="bar-slide face finish",
        entity=datum_b_entity,
        leader_attach_xy=model_point_in_view(
            adapter,
            front,
            (BAR_SLIDE_STATION_MM / 1000.0, 0.0, 0.0),
            label="bar-slide face finish landing",
        ),
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Guide Manufacturing Drawing",
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

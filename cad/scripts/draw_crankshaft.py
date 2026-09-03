r"""Create the curated machinist drawing for the crankshaft.

The SLDPRT remains authoritative.  This recipe supplies only the crankshaft
views, dimension layout, the #9 cross-hole callout, and manufacturing notes;
every shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The model's shaft axis runs along +Y (outboard/crank end at the origin), so
the standard side views show the shaft VERTICAL: the crank-end face is the
``*Bottom`` orientation and the length view is ``*Right`` (outboard end at the
view bottom, the #9 cross-hole facing the viewer as a circle at station 4).

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
turned shaft carries no datums, frames or basic dimensions -- the journal's
running fit rides its model dimension and the one roughness symbol sits on
the bearing journal that runs in the pedestal bore.  Layout (machinist
review 2026-09-02): the journal length and the overall stack on the LEFT of
the length view, the journal start, the cross-hole station, the Ra symbol and
the shoulder-root callout on the RIGHT, so no leader crosses a dimension line.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crankshaft.py crankshaft
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    find_edge_near,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    add_view_centerline,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from crankshaft_spec import (
    JOURNAL_DIA,
    JOURNAL_END,
    JOURNAL_LENGTH,
    JOURNAL_ROOT_NOTE,
    JOURNAL_START,
    PIN_HOLE_DIA,
    PIN_HOLE_HEIGHT,
    SHAFT_DIA,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crankshaft"]
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

SHEET_SCALE = (1.0, 1.0)
END_VIEW_SCALE = 2.0
# Crank-end view (the *Bottom orientation: looking along +Y) at 2:1.
FRONT_CENTER = (0.060, 0.150)
# Side view (the *Right orientation: shaft vertical, outboard end at the view
# bottom) at 1:1 -- the 122 length spans sheet y 0.089..0.211.
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.345, 0.197)

# Derived sheet anchors (meters).
_SIDE_BOTTOM = RIGHT_CENTER[1] - SHAFT_LENGTH / 2000.0  # outboard end edge
# The #9 cross-hole faces the viewer in the side view: its centre sits at
# station PIN_HOLE_HEIGHT above the outboard (bottom) end.
_PIN_CENTER = (
    RIGHT_CENTER[0],
    _SIDE_BOTTOM + PIN_HOLE_HEIGHT / 1000.0,
)
# Journal stations on the sheet and its right-hand silhouette.
_JOURNAL_RIGHT_X = RIGHT_CENTER[0] + JOURNAL_DIA / 2000.0
_JOURNAL_BOTTOM_Y = _SIDE_BOTTOM + JOURNAL_START / 1000.0
_JOURNAL_TOP_Y = _SIDE_BOTTOM + JOURNAL_END / 1000.0
_JOURNAL_MID_Y = _SIDE_BOTTOM + (JOURNAL_START + JOURNAL_LENGTH / 2.0) / 1000.0

FRONT_KEEP = {
    "ShaftDiaDim": (
        max(
            0.030,
            FRONT_CENTER[0] - SHAFT_DIA * END_VIEW_SCALE / 1000.0 - 0.022,
        ),
        FRONT_CENTER[1] + 0.008,
    ),
    "JournalDiaDim": (0.102, FRONT_CENTER[1] + 0.020),
}
# Left of the length view: the journal length inboard, the overall outboard
# (the longer dimension outside the shorter, one baseline).  Right of it: the
# journal start from the crank-end face.
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1]),
    "JournalLength": (RIGHT_CENTER[0] - 0.018, _JOURNAL_MID_Y),
    "JournalStart": (RIGHT_CENTER[0] + 0.035, _SIDE_BOTTOM + 0.020),
}
# Cross-hole station text: right of the shaft, inboard of the JournalStart
# lane (same crank-end baseline, shorter dimension nearer the part), clear of
# the 122.00 line on the left.
PIN_STATION_TEXT_XY = (RIGHT_CENTER[0] + 0.020, _SIDE_BOTTOM + 0.010)
# Ra symbol right of the journal with a straight horizontal leader to the
# journal OD at midspan (the JournalStart lane ends well below it).
JOURNAL_FINISH_SYMBOL_XY = (RIGHT_CENTER[0] + 0.040, _JOURNAL_MID_Y)
JOURNAL_FINISH_ATTACH_XY = (_JOURNAL_RIGHT_X, _JOURNAL_MID_Y)
# Shoulder-root callout, leadered onto the upper shoulder's rim from above
# right (nothing else sits on that side above the Ra symbol).
JOURNAL_ROOT_PICK_XY = (RIGHT_CENTER[0] + 0.0052, _JOURNAL_TOP_Y)
JOURNAL_ROOT_NOTE_XY = (RIGHT_CENTER[0] + 0.022, _JOURNAL_TOP_Y + 0.016)
DIMENSION_CALLOUTS = {}


def _visible_cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the requested modeled OD face in the crankshaft side view."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 3
                ),  # swViewEntityType_Face
                default=(),
            )
            or ()
        )
        for face in faces:
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            parameters = surface.CylinderParams
            if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append((float(face.GetArea()), face))
    if not candidates:
        raise RuntimeError(
            f"crankshaft side view has no visible cylindrical face at "
            f"radius {expected_radius_m:g} m"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]


def _visible_journal_silhouette(adapter: Any, view: Any) -> Any:
    """Return the longest silhouette: the v2-post bearing journal OD."""
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        silhouettes = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 4),
                default=(),
            )
            or ()
        )
        for raw_silhouette in silhouettes:
            silhouette = _early_bound(raw_silhouette, "ISilhouetteEdge")
            start = adapter._attempt(lambda s=silhouette: s.GetStartPoint())
            end = adapter._attempt(lambda s=silhouette: s.GetEndPoint())
            if start is None or end is None:
                continue
            start_xyz = adapter._get_attr_or_call(start, "ArrayData")
            end_xyz = adapter._get_attr_or_call(end, "ArrayData")
            if not start_xyz or not end_xyz:
                continue
            length = (
                sum((float(a) - float(b)) ** 2 for a, b in zip(start_xyz, end_xyz))
                ** 0.5
            )
            candidates.append((length, silhouette))
    if not candidates:
        raise RuntimeError("crankshaft side view has no usable silhouette edges")
    length, silhouette = max(candidates, key=lambda candidate: candidate[0])
    if length < JOURNAL_LENGTH * 0.8 / 1000.0:
        raise RuntimeError(
            "could not identify the crankshaft journal silhouette: "
            f"longest visible silhouette is only {length * 1000:g} mm"
        )
    return silhouette


def _visible_cross_hole_edge(adapter: Any, view: Any) -> Any:
    """Return a visible rim edge adjacent to the modeled #9 cylindrical face."""
    expected_radius_m = PIN_HOLE_DIA / 2000.0
    candidates: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(
                    c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            adjacent_faces = edge.GetTwoAdjacentFaces2() or ()
            for face in adjacent_faces:
                if face is None:
                    continue
                face = _early_bound(face, "IFace2")
                surface = _early_bound(face.GetSurface(), "ISurface")
                if not surface.IsCylinder():
                    continue
                parameters = surface.CylinderParams
                if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                    continue
                candidates.append(edge)
                break
    if not candidates:
        raise RuntimeError(
            f"crankshaft side view has no visible edge adjacent to the "
            f"#9 cylindrical face at radius {expected_radius_m:g} m"
        )
    return candidates[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crankshaft source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Crank End Note",
            "Manufacturing Notes",
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Crank End Note",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crankshaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crankshaft; drive shaft; taper pin; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Bottom", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in every orthographic view: the side view shows the #9
    # cross-hole through the shaft.
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # The two seat diameters print three decimals: the journal carries its
    # running-fit band on the model dimension, and the 3/8 shaft is a gear /
    # arm seat held under the three-place block tolerance ("hold it", policy
    # rule 2).  The journal stations stay at the two-place block tolerance.
    set_dimension_precision(
        adapter,
        [*front_annotations, *right_annotations],
        {"ShaftDiaDim": 3, "JournalDiaDim": 3},
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; the end view gets the
    # ASME centre mark, the side view marks the #9 cross-hole circle.
    for view, label in ((front, "end"), (right, "side")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    journal_face = _visible_cylindrical_face(adapter, right, JOURNAL_DIA)
    journal_silhouette = _visible_journal_silhouette(adapter, right)
    add_view_centerline(
        adapter,
        right,
        label="crankshaft bearing axis",
        face=journal_face,
    )

    # The #9 tapered-pin cross-hole: the associative wizard callout carries the
    # Ø/THRU specification with the drill as its prefix; the axial station is a
    # drawing-native dimension from the crank-end face under the title-block
    # linear tolerance, placed on the RIGHT so it never crowds the 122.00 line.
    cross_hole_edge = _visible_cross_hole_edge(adapter, right)
    pin_station = add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0] - SHAFT_DIA / 2000.0, _SIDE_BOTTOM),
        p1=(RIGHT_CENTER[0], _PIN_CENTER[1] + PIN_HOLE_DIA / 2000.0),
        text_xy=PIN_STATION_TEXT_XY,
        label="cross-hole station",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(adapter, pin_station, label="cross-hole station")
    add_native_hole_callout(
        adapter,
        right,
        callout_xy=(0.095, 0.082),
        label="tapered-pin cross-hole",
        edge=cross_hole_edge,
        process="#9 DRILL",
    )
    add_property_linked_note(adapter, "Crank End Note", 0.250, 0.090)

    # Ra on the journal OD at midspan: the leader attachment is pinned there
    # explicitly (left to itself the symbol landed on the journal/shoulder
    # corner, which reads as the shoulder face -- review 2026-09-02).
    add_surface_finish(
        adapter,
        right,
        symbol_xy=JOURNAL_FINISH_SYMBOL_XY,
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing_journal"),
        label="crankshaft bearing-journal finish",
        edge_entity=journal_silhouette,
        entity_type="SILHOUETTE",
        leader_attach_xy=JOURNAL_FINISH_ATTACH_XY,
    )
    # Shoulder roots: the upper journal step's outer rim (the horizontal line
    # at JOURNAL_END; picked outboard of the 3/8 core so only the Ø11.388 rim
    # is under the cursor) carries the 2X root allowance for both steps.
    root_xy = find_edge_near(
        adapter,
        right,
        JOURNAL_ROOT_PICK_XY,
        axis="y",
        label="crankshaft upper journal shoulder",
    )
    add_attached_note(
        adapter,
        right,
        text=JOURNAL_ROOT_NOTE,
        entity_xy=root_xy,
        note_xy=JOURNAL_ROOT_NOTE_XY,
        label="journal shoulder roots",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.045)
    # Identify the enlarged circular projection without relying on its position.
    add_property_linked_note(adapter, "End View Note", 0.018, 0.112)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crankshaft Manufacturing Drawing",
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

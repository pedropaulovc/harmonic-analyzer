r"""Create the curated machinist drawing for the crankshaft.

The SLDPRT remains authoritative.  This recipe supplies only the crankshaft
views, dimension layout, the #9 cross-hole callout, and manufacturing notes;
every shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The model's shaft axis runs along +Y (outboard/crank end at the origin), so
the standard side views show the shaft VERTICAL: the crank-end face is the
``*Bottom`` orientation and the length view is ``*Front`` (outboard end at the
view bottom, the #9 cross-hole facing the viewer as a circle at station 12).

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
    add_datum_feature,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    offset_dimension_text,
    read_required_properties,
    set_basic_dimensions,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    add_view_centerline,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crankshaft_spec import (
    PIN_HOLE_DIA,
    PIN_HOLE_HEIGHT,
    SHAFT_DIA,
    SHAFT_LENGTH,
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
# Side view (the *Front orientation: shaft vertical, outboard end at the view
# bottom) at 1:1 -- the 145 length spans sheet y 0.0775..0.2225.
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.345, 0.200)

# Derived sheet anchors (meters).
_SIDE_BOTTOM = RIGHT_CENTER[1] - SHAFT_LENGTH / 2000.0  # outboard end edge
# The #9 cross-hole faces the viewer in the side view: its centre sits at
# station PIN_HOLE_HEIGHT above the outboard (bottom) end.
_PIN_CENTER = (
    RIGHT_CENTER[0],
    _SIDE_BOTTOM + PIN_HOLE_HEIGHT / 1000.0,
)

FRONT_KEEP = {
    "ShaftDiaDim": (
        max(
            0.030,
            FRONT_CENTER[0] - SHAFT_DIA * END_VIEW_SCALE / 1000.0 - 0.022,
        ),
        FRONT_CENTER[1] + 0.008,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1]),
    "PinHeight": (0.128, 0.090),
}
DIMENSION_CALLOUTS = {"ShaftDiaDim": "+0.00/-0.02"}


def _visible_shaft_face(adapter: Any, view: Any) -> Any:
    """Return the modeled OD face visible in the crankshaft side view."""
    expected_radius_m = SHAFT_DIA / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 3),  # swViewEntityType_Face
            default=(),
        ) or ()
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


def _visible_cross_hole_edge(adapter: Any, view: Any) -> Any:
    """Return a visible rim edge adjacent to the modeled #9 cylindrical face."""
    expected_radius_m = PIN_HOLE_DIA / 2000.0
    candidates: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1),  # swViewEntityType_Edge
            default=(),
        ) or ()
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


def _visible_shaft_end_edges(adapter: Any, view: Any) -> list[tuple[float, Any]]:
    """Return shaft end edges ordered from crank end to far end."""
    expected_radius_m = SHAFT_DIA / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = adapter._attempt(
            lambda c=component: view.GetVisibleEntities2(c, 1),
            default=(),
        ) or ()
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            parameters = curve.CircleParams
            if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append((float(parameters[1]), edge))
    if not candidates:
        raise RuntimeError(
            f"drawing view has no shaft end edge at radius {expected_radius_m:g} m"
        )
    return sorted(candidates, key=lambda candidate: candidate[0])


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
    right = place_view(adapter, str(SOURCE), "*Front", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # Ø9.525 is the exact 3/8 in conversion; two sheet decimals (9.53) would
    # contradict the crank-arm bore note, so keep three.
    set_dimension_precision(
        adapter, [*front_annotations, *right_annotations], {"ShaftDiaDim": 3}
    )
    set_basic_dimensions(adapter, right_annotations, ("PinHeight",))
    offset_dimension_text(
        adapter, right_annotations, {"PinHeight": (0.132, 0.105)}
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; the end view gets the
    # ASME centre mark, the side view marks the #9 cross-hole circle.
    for view, label in ((front, "end"), (right, "side")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    shaft_face = _visible_shaft_face(adapter, right)
    add_view_centerline(
        adapter,
        right,
        label="crankshaft bearing axis",
        face=shaft_face,
    )

    front_end_edge = _visible_shaft_end_edges(adapter, front)[0][1]
    right_end_edges = _visible_shaft_end_edges(adapter, right)
    crank_end_edge = right_end_edges[0][1]
    far_end_edge = right_end_edges[-1][1]
    add_datum_feature(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.027),
        datum="A",
        label="shaft OD datum axis",
        entity=front_end_edge,
    )
    add_datum_feature(
        adapter,
        right,
        symbol_xy=(RIGHT_CENTER[0] - SHAFT_DIA / 4000.0, 0.060),
        datum="B",
        label="crank-end datum face",
        entity=crank_end_edge,
    )
    add_feature_control_frame(
        adapter,
        right,
        frame_xy=(0.185, 0.235),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        quantity="2X END FACES",
        label="end-face perpendicularity",
        entity=far_end_edge,
    )

    # The #9 tapered-pin cross-hole: the associative wizard callout carries the
    # Ø/THRU specification. The axial station is the imported model-owned
    # PinHeight dimension above and takes the title-block linear tolerance.
    cross_hole_edge = _visible_cross_hole_edge(adapter, right)
    add_native_hole_callout(
        adapter,
        right,
        callout_xy=(0.205, 0.104),
        label="tapered-pin cross-hole",
        edge=cross_hole_edge,
    )
    add_feature_control_frame(
        adapter,
        right,
        frame_xy=(0.205, 0.128),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B"),
        diameter=True,
        label="cross-hole true position",
        entity=cross_hole_edge,
    )
    add_property_linked_note(adapter, "Crank End Note", 0.250, 0.090)

    add_surface_finish(
        adapter,
        right,
        symbol_xy=(0.210, 0.195),
        roughness_ra="1.6",
        label="crankshaft bearing finish",
        entity_type="FACE",
        edge_entity=shaft_face,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.056)
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

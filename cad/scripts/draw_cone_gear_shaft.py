r"""Create the cone-gear-shaft manufacturing drawing under the simplicity policy.

The turned shaft is shown horizontally at 1:1 with baseline lengths from the
large (faced) end below it and every diameter above it on that same side
view, each dimension line inside the land it measures.  The three short tip
lands are 6.9 mm apart, so their diameter texts climb in steps: the tip's
line rises highest and each text hangs to the RIGHT of its line above every
line it spans.  A standard isometric supplies pictorial clarity, and one
note names the gear seats the lands are fitted to.  Source geometry and
native model fits stay authoritative: the sheet types no tolerance and no
precision.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_gear_shaft.py cone-gear-shaft
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_gear_shaft_spec import (
    FILLET_CALLOUT,
    JOURNAL_DIA,
    SECTION_DIAS,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    iter_views,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_gear_shaft"]
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
SIDE_SCALE = (1, 1)
ISO_SCALE = (1, 2)


# Landscape sheet, 0.4318 x 0.2794 m, title block bottom right (x > ~0.216,
# y < ~0.066).  The 205.17 mm shaft at 1:1 spans 0.0474..0.2526 about
# SIDE_CENTER, leaving the right third for the pictorial; the group sits
# mid-height so the baseline stack below and the diameters above share the
# field evenly, with the note block in the lower left.
SIDE_CENTER = (0.150, 0.170)
ISO_CENTER = (0.345, 0.185)
NOTES_XY = (0.058, 0.060)
# Off-sheet-left donor: the five diameters are model dimensions of circular
# profile sketches, so they can only be IMPORTED into a view that faces those
# circles.  They are imported here, dragged onto the shoulder each one
# belongs to, and this view is then deleted.
DONOR_CENTER = (0.360, 0.090)

# Axial step stations (extrude depths Sec{i}End), all measured from the
# large-end datum face: baseline dimensioning below the shaft, shortest
# nearest the part.  The one radius rides above the journal shoulder it
# attaches to (the fillet feature's first edge), its leader dropping straight
# to that corner, right of the Ø9.525 text and left of the pivot finish.
SIDE_KEEP = {
    "Sec0End": (0.2311, 0.1555),
    "Sec1End": (0.1672, 0.1465),
    "Sec2End": (0.1638, 0.1375),
    "Sec3End": (0.1603, 0.1285),
    "Sec4End": (0.1499, 0.1195),
    "ShoulderR": (0.2000, 0.2120),
}
# Diameters, imported on the donor and dragged onto the side view.  A vertical
# linear dimension's line sits at its text x and the text hangs to the RIGHT
# of that line (~32 mm wide with its stacked band), so each x lies INSIDE the
# land it measures (the big end is at sheet x 0.2526; land 1 spans
# 0.0819..0.2096, land 2 0.0750..0.0819, land 3 0.0681..0.0750, land 4
# 0.0474..0.0681); Ø12.231 stands just off the faced end.  The three tip
# lands are only 6.9 mm apart, so a text spans its right-hand neighbours'
# lines: the tip's text sits highest and each neighbour to the right steps
# down, so no line rises through a text (codex, 18395f30).
SIDE_DIAMETERS = {
    "Sec0Dia": (0.2700, 0.1820),
    "Sec1Dia": (0.1400, 0.1930),
    "Sec2Dia": (0.0810, 0.1960),
    "Sec3Dia": (0.0690, 0.2080),
    "Sec4Dia": (0.0520, 0.2200),
}
# Sheet width of one diameter text with its stacked band, for the layout test.
DIAMETER_TEXT_WIDTH = 0.032
DONOR_KEEP = {
    name: (DONOR_CENTER[0], DONOR_CENTER[1] - 0.012 * index)
    for index, name in enumerate(SIDE_DIAMETERS)
}
# Four identical shoulder roots, one modelled fillet, one radius dimension.
DIMENSION_CALLOUTS = {"ShoulderR": FILLET_CALLOUT}


@_telemetry.traced("drawing.cylindrical_face_scan")
def _cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the visible cylindrical face for one shaft diameter."""
    candidates: list[tuple[float, Any]] = []
    for face in visible_view_entities(view, 3, label="gear-shaft side faces"):
        face = _early_bound(face, "IFace2")
        surface = face.GetSurface()
        if surface is None:
            continue
        surface = _early_bound(surface, "ISurface")
        if not surface.IsCylinder():
            continue
        radius_mm = float(surface.CylinderParams[6]) * 1000.0
        candidates.append((radius_mm, face))
    if not candidates:
        raise RuntimeError("side view has no visible cylindrical faces")
    target_radius = diameter_mm / 2.0
    radius_mm, face = min(candidates, key=lambda item: abs(item[0] - target_radius))
    if abs(radius_mm - target_radius) > 0.01:
        raise RuntimeError(
            f"no cylindrical face matches radius {target_radius:.4f} mm; "
            f"nearest is {radius_mm:.4f} mm"
        )
    return face


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear-shaft source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear shaft; stepped turned steel; gear seats",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=SIDE_SCALE)
    donor = place_view(adapter, str(SOURCE), "*Front", *DONOR_CENTER, scale=SIDE_SCALE)
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, donor):
        set_hidden_lines_removed(adapter, view)

    pivot_face = _cylindrical_face(adapter, side, JOURNAL_DIA)
    tip_face = _cylindrical_face(adapter, side, SECTION_DIAS[-1])
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] + 0.050, SIDE_CENTER[1]),
        label="shaft longitudinal axis",
        entity=pivot_face,
    )

    # The donor is curated FIRST so the diameters cannot be claimed (and then
    # deleted) by a view that cannot show them.
    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="side"
    )
    annotations = list(side_annotations)
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        annotations.append(
            _move_dimension(
                adapter, annotation, side, SIDE_DIAMETERS[name], source_view=donor
            )
        )
    # Every diameter is now native to the view that shows its shoulder; an
    # empty end view carries no manufacturing information.
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    # Leader anchors for the two lands that RUN (sheet metres).  The tip
    # symbol stands above the tip with its glyph LEFT of the Ø1.588 dimension
    # line and its text ABOVE the Ø1.588 text, well inside the left border
    # (x 0.012; a glyph at 0.016 poked through it, codex c4720c62); the
    # leader drops onto the tip's top flank inside the first 2 mm of the land.
    # No length extension line runs up there (they all hang from the bottom
    # flank) and no diameter line stands left of the Ø1.588 one.
    big_end_x = SIDE_CENTER[0] + SHAFT_LENGTH / 2000.0
    pivot_top = (big_end_x - 0.020, SIDE_CENTER[1] + SECTION_DIAS[0] / 2000.0)
    tip_top = (
        big_end_x - SHAFT_LENGTH / 1000.0 + 0.002,
        SIDE_CENTER[1] + SECTION_DIAS[-1] / 2000.0,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.2400, 0.2000),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
        entity_type="FACE",
        entity=pivot_face,
        leader_attach_xy=pivot_top,
    )
    add_surface_finish(
        adapter,
        side,
        symbol_xy=(0.0240, 0.2160),
        control=surface_finish_by_key(SURFACE_FINISHES, "tip_journal"),
        label="tip journal finish",
        entity_type="FACE",
        entity=tip_face,
        leader_attach_xy=tip_top,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Shaft Manufacturing Drawing",
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

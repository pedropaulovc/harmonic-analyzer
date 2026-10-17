r"""Create the curated machinist drawing for the magnifying lever rod.

The rod is a revolved Ø6 x 165 brass capsule with hemispherical ends -- a
smooth, tangent-continuous body with NO flat face and no end-face circle, so
the print rests on the auto-imported profile marks (the overall length tip to
tip and the dome radius, a radial reference "(R3.0)": each end is a tangent
full hemisphere on the selected bar) plus two blanked reference sketches the
FRONT view shows and dimensions: ``RodStock`` (the Ø6 as plain bar stock at
mid-length, at the title block's .X) and ``PressZone`` (the cylinder the
bracket collar grips -- its start back from the east tip a single MIN limit
covering the MHA-MG-001 collar, its length to the dome tangent as a
reference, and its banded diameter, tied to the MHA-MG-001 bore it enters).
The zone's start is a solid line across the bar, so the zone reads between it
and the dome's tangent edge; every other reference entity lies on the
silhouette.  The Ø6 body's one finish, the part-owned Ra 3.2 seat of the
MHA-MG-002 clamp's screw, is a native symbol with its reason standing at it.
The sheet carries no note block: pressing the collar on is the MHA-MG-000
assembly's step.  The rod axis is local +X, so the FRONT view is the long
side elevation; an end view of a plain round would show nothing the Ø does
not, so there is none.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_lever.py mg-magnifying-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
    view_name,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _surface_finish import surface_finish_by_key
from mg_lever_press_fit_geom import ROD_DIA
from mg_magnifying_lever_spec import (
    DRAWING_DIMENSIONS,
    PRESS_ZONE_DIA_CALLOUT,
    PRESS_ZONE_LENGTH,
    PRESS_ZONE_START_CALLOUT,
    RADIAL_REFERENCE_DIMENSIONS,
    REFERENCE_DIMENSIONS,
    ROD_LENGTH,
    SCREW_SEAT_CALLOUT,
    SURFACE_FINISHES,
)


SPEC = DRAWINGS_BY_NAME["mg_magnifying_lever"]
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
FRONT_CENTER = (0.115, 0.150)
ISO_CENTER = (0.350, 0.185)
ISO_SCALE = (1, 2)

# Sheet stations of the rod's ends, from the model's own constants: the west
# tip (the part origin), the east tip, the press zone's start
# (PRESS_ZONE_LENGTH back from the tip), the dome tangent (one radius back)
# and the zone cylinder's mid-length; the rod's top outline.
_ROD_WEST_TIP_X = FRONT_CENTER[0] - ROD_LENGTH * SHEET_SCALE[0] / 2000.0
_ROD_TIP_X = FRONT_CENTER[0] + ROD_LENGTH * SHEET_SCALE[0] / 2000.0
_PRESS_ZONE_START_X = _ROD_TIP_X - PRESS_ZONE_LENGTH * SHEET_SCALE[0] / 1000.0
_DOME_TANGENT_X = _ROD_TIP_X - ROD_DIA / 2.0 * SHEET_SCALE[0] / 1000.0
_PRESS_ZONE_MID_X = (_PRESS_ZONE_START_X + _DOME_TANGENT_X) / 2.0
_ROD_TOP_Y = FRONT_CENTER[1] + ROD_DIA / 2.0 * SHEET_SCALE[1] / 1000.0

# The two native profile dims the print keeps: the tip-to-tip length below the
# rod, outermost on a line of its own (its extension lines drop from both
# tips), and the dome radius reference right of the east tip, its three rows
# between the zone diameter's dimension line (left) and block (above).
# Machinist review r2: r4 printed the 165.0 line (y 113.5 mm) level with the
# zone start's (113.1 mm), so the two read as one chain ending at the zone
# start; it now runs ~13 mm under the zone start's line, the title block's
# top (y ~65 mm) far below.
FRONT_KEEP = {
    "OverallLength": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.042),
    "DomeRadius": (_ROD_TIP_X + 0.040, FRONT_CENTER[1] + 0.008),
}
# The reference sketches' dims.  The stock diameter above the rod at
# mid-length, its dimension line just right of its points on the outlines; a
# plain Ø, no callout.
# The press zone's lengths hang below the rod off the witness on its bottom
# outline and the tip (layout doc: a horizontal dim's rows centre on the
# requested x and y, its line at the lowest row's baseline): the cylinder's
# reference length innermost, its row left of the 7 mm span; the start from
# the tip outside it, its three rows wholly right of the tip's extension line
# (machinist review r2: r4's 52 mm block, centred 24 mm right of the tip, ran
# that line through its 'M') and under the reference length's line.
# The banded diameter's dimension line stands inside the zone, between the
# zone-start line and the dome's tangent edge, and its rows hang ABOVE the
# rod, right of that line: the line rises to the shoulder under the block,
# never alongside a row of text, and the two-row mate callout stays short of
# the isometric.
REFERENCE_KEEP = {
    "RodDia": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.020),
    "PressZoneLen": (_PRESS_ZONE_START_X - 0.010, FRONT_CENTER[1] - 0.012),
    "PressZoneStart": (_ROD_TIP_X + 0.030, FRONT_CENTER[1] - 0.024),
    "PressZoneDia": (_PRESS_ZONE_MID_X, FRONT_CENTER[1] + 0.030),
}
DIMENSION_CALLOUTS = {
    "DomeRadius": "BOTH ENDS\nTANGENT HEMISPHERE",
}
REFERENCE_CALLOUTS = {
    "PressZoneStart": PRESS_ZONE_START_CALLOUT,
    "PressZoneDia": PRESS_ZONE_DIA_CALLOUT,
}
# The seat's Ra 3.2 (SURFACE_FINISHES "clamp_screw_seat"): a native symbol
# whose leader lands on the Ø6 face 40 mm in from the west tip, inside the
# clamp screw's reach and clear of the stock diameter's station (82.5 mm);
# the symbol stands above-left of the landing, west of the stock diameter's
# row.
# The symbol is attached to the OD's FACE: the front view lies in the
# revolve's profile plane, so its top outline is the cylinder's seam, and a
# silhouette pick there re-solved onto the other half-face on rebuild (r12
# leaf 20261017T061433Z-1-6db3cfe0: types=(46,), same_entity=False). A face
# picked by coordinate keeps its leader at the pick, not at a separate
# landing (r13 leaf 20261017T065000Z-1-a58d0439), and a pick 0.4 mm inside
# the outline selected nothing (r14 leaf 20261017T070332Z-1-45a1d3b0), so the
# pick and the landing are one point midway between the axis and the top
# outline, where r13 selected and attached the face.
# add_surface_finish proves the symbol attached to that face (the part's
# control) and the leader landed where requested.
SEAT_FINISH_PICK = (_ROD_WEST_TIP_X + 0.040, (FRONT_CENTER[1] + _ROD_TOP_Y) / 2.0)
SEAT_FINISH_SYMBOL = (_ROD_WEST_TIP_X + 0.030, _ROD_TOP_Y + 0.014)
# The seat's reason, a free note at the symbol (machinist review r4 read the
# old reason, a callout on a seat-length dimension 15 mm above, as detached
# from it): one row whose top-left corner (a note's position) sits 13 mm over
# the symbol's root, left-aligned with the symbol's bar 2.5 mm west of it, so
# it stands just over the symbol (r15: its ink reached 7.2 mm over the root)
# and ~4 mm over the stock diameter's row (its top ~172 mm), well west of the
# zone diameter's block (x >= ~191 mm).
SEAT_REASON_XY = (SEAT_FINISH_SYMBOL[0] - 0.0025, SEAT_FINISH_SYMBOL[1] + 0.013)


def _add_seat_reason(adapter: Any, view: Any) -> None:
    """The seat's reason as a free note owned by ``view`` at SEAT_REASON_XY;
    a note that did not land in that view raises (the reason-note recipe of
    draw_mg_magnifying_vertical_rod)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the lever front view {name!r}")
    adapter.currentModel.ClearSelection2(True)
    if add_note(adapter, SCREW_SEAT_CALLOUT, *SEAT_REASON_XY) is None:
        raise RuntimeError("failed to add the lever screw-seat reason note")
    texts = [
        " ".join(str(_early_bound(found, "INote").GetText() or "").split())
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if texts.count(SCREW_SEAT_CALLOUT) != 1:
        raise RuntimeError(f"lever screw-seat reason missed its view: {texts!r}")


def _set_radial_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print a model radius as the ASME radial reference ``(R3.0)``.

    The radius is read-only: each dome is a full hemisphere tangent to the
    bar, so the selected press-zone diameter fixes it.  The singular
    ``set_reference_dimension`` writes a bare ``(`` prefix, which replaces the
    display's own radius glyph, so whatever prefix it carries is kept behind
    the ``(``; the readback proves it stuck (draw_ch_pivot_shaft's ``(SR4.1)``
    idiom, without the spherical S).
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "(" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(
        f"{label}: radial reference prefix {existing!r} -> {applied[0]!r}, "
        f"suffix {applied[1]!r}"
    )
    if applied != (prefix, ")"):
        raise RuntimeError(f"failed to mark {label} as a radial reference: {applied}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open magnifying-lever source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Lever Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying lever; turned brass rod; domed ends",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    for name in sorted(RADIAL_REFERENCE_DIMENSIONS):
        matches = [a for a in front_annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one lever {name} radial reference")
        _set_radial_reference(adapter, matches[0], label=f"lever {name}")
    # The part saves PressZone and RodStock blanked (they would print in every
    # assembly render); shown here per view, their dimensions import and stay.
    reference_annotations = curate_hidden_dimensions(
        adapter,
        front,
        keep=REFERENCE_KEEP,
        view_label="front reference sketches",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, reference_annotations, REFERENCE_CALLOUTS)
    # The zone cylinder's length is the start less the dome radius: a LINEAR
    # reference. The plural set_reference_dimensions forces a diameter glyph.
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            a for a in reference_annotations if dimension_name(adapter, a) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one lever {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"lever {name}")
    add_surface_finish(
        adapter,
        front,
        edge_xy=SEAT_FINISH_PICK,
        entity_type="FACE",
        symbol_xy=SEAT_FINISH_SYMBOL,
        leader_attach_xy=SEAT_FINISH_PICK,
        control=surface_finish_by_key(SURFACE_FINISHES, "clamp_screw_seat"),
        label="lever clamp screw seat finish",
        char_height=0.0025,
    )
    _add_seat_reason(adapter, front)
    add_property_linked_note(adapter, "Iso View Note", 0.320, 0.140)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Lever Rod Manufacturing Drawing",
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

r"""Create the curated machinist drawing for the magnifying lever rod.

The rod is a revolved Ø6 x 165 brass capsule with hemispherical ends -- a
smooth, tangent-continuous body with NO flat face and no end-face circle, so
the print rests on the auto-imported profile marks (the overall length tip to
tip and the dome radius, a radial reference "(R3.0)": each end is a tangent
full hemisphere on the selected bar) plus two blanked reference sketches the
FRONT view shows and dimensions: ``RodStock`` (the stock Ø6 and its
cold-drawn band at mid-length) and ``PressZone`` (the cylinder the bracket
collar grips -- its banded start back from the east tip, its length to the
dome tangent as a reference, and its banded diameter, tied to the MHA-MG-001
bore it enters).  The OD's finish is the part's native symbol on the rod's
one Ø6 cylinder face.  The rod axis is local +X, so the FRONT view is the
long side elevation; an end view of a plain round would show nothing the Ø
does not, so there is none.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_magnifying_lever.py mg-magnifying-lever
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
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
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_hidden_sketches import curate_view_dimensions as curate_hidden_dimensions
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gtol_face_resolve import resolve_faces
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from mg_lever_press_fit_geom import ROD_DIA
from mg_magnifying_lever_spec import (
    DRAWING_DIMENSIONS,
    PRESS_ZONE_DIA_CALLOUT,
    PRESS_ZONE_LENGTH,
    RADIAL_REFERENCE_DIMENSIONS,
    REFERENCE_DIMENSIONS,
    ROD_LENGTH,
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

# Sheet stations of the rod's east end, from the model's own constants: the
# tip, the press zone's start (PRESS_ZONE_LENGTH back from the tip), the dome
# tangent (one radius back) and the zone cylinder's mid-length; the rod's
# top outline.
_ROD_TIP_X = FRONT_CENTER[0] + ROD_LENGTH * SHEET_SCALE[0] / 2000.0
_PRESS_ZONE_START_X = _ROD_TIP_X - PRESS_ZONE_LENGTH * SHEET_SCALE[0] / 1000.0
_DOME_TANGENT_X = _ROD_TIP_X - ROD_DIA / 2.0 * SHEET_SCALE[0] / 1000.0
_PRESS_ZONE_MID_X = (_PRESS_ZONE_START_X + _DOME_TANGENT_X) / 2.0
_ROD_TOP_Y = FRONT_CENTER[1] + ROD_DIA / 2.0 * SHEET_SCALE[1] / 1000.0

# The two native profile dims the print keeps: the tip-to-tip length below the
# rod, outermost (its extension lines drop from both tips), and the dome
# radius reference right of the east tip, its three rows between the zone
# diameter's dimension line (left) and block (above).
FRONT_KEEP = {
    "OverallLength": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.034),
    "DomeRadius": (_ROD_TIP_X + 0.040, FRONT_CENTER[1] + 0.008),
}
# The reference sketches' dims.  The stock diameter above the rod at
# mid-length.  The press zone's lengths hang below the rod off the witness on
# its bottom outline and the tip (layout doc: a horizontal dim's rows centre
# on the requested x): the cylinder's reference length innermost, its row
# left of the 7 mm span; the start from the tip outside it, its rows right of
# the tip.  The banded diameter's dimension line stands inside the zone and
# its rows hang ABOVE the rod, right of that line: the line rises to the
# shoulder under the block, never alongside a row of text, and the two-row
# mate callout stays short of the isometric.
REFERENCE_KEEP = {
    "RodDia": (FRONT_CENTER[0], FRONT_CENTER[1] + 0.020),
    "PressZoneLen": (_PRESS_ZONE_START_X - 0.010, FRONT_CENTER[1] - 0.012),
    "PressZoneStart": (_ROD_TIP_X + 0.024, FRONT_CENTER[1] - 0.024),
    "PressZoneDia": (_PRESS_ZONE_MID_X, FRONT_CENTER[1] + 0.030),
}
DIMENSION_CALLOUTS = {
    "DomeRadius": "BOTH ENDS\nTANGENT HEMISPHERE",
}
REFERENCE_CALLOUTS = {
    "RodDia": "STOCK OD",
    "PressZoneStart": "PRESS ZONE START",
    "PressZoneDia": PRESS_ZONE_DIA_CALLOUT,
}
# The OD finish: the part-owned ``rod_od`` control's ONE Ø6 cylinder, resolved
# on the part the front view references and attached as that model FACE; its
# leader lands on the rod's top outline in the clamp block's travel, past the
# west dome and short of the press zone, and the symbol stands above it, left
# of the stock diameter.  Not a SILHOUETTE pick: on the source-644 native leaf
# the inserted symbol re-read one live type-46 attachment whose
# ISilhouetteEdge::GetFace failed IsSame against the picked silhouette's
# (same_entity=False, dangling=False), so nothing proved which surface it sat
# on.  ISldWorks::IsSame proves a model face itself, and the 1 mm leader
# landing pins the flank and station (draw_dt_pinion_arbor's journal finishes).
FINISH_STATION_MM = ROD_LENGTH / 2.0 - 50.0  # part X, from the west dome tip
FINISH_LANDING_MODEL = (FINISH_STATION_MM / 1000.0, ROD_DIA / 2000.0, 0.0)
FINISH_SYMBOL = (FRONT_CENTER[0] - 0.050, FRONT_CENTER[1] + 0.020)


def _rod_od_finish_pick(adapter: Any, view: Any) -> tuple[Any, tuple[float, float]]:
    """The OD finish's target: ``(controlled face, sheet landing)``.

    The face is the one the part's own Ra PMI names (``SURFACE_FINISHES``'
    ``rod_od`` spec), resolved on the view's referenced part with the
    exactly-one-match contract the part build's PMI pass used; the landing is
    the model point on the top outline at ``FINISH_STATION_MM``, projected
    through the view's current transform.
    """
    control = surface_finish_by_key(SURFACE_FINISHES, "rod_od")
    document = _early_bound(
        _early_bound(view, "IView").ReferencedDocument, "IModelDoc2"
    )
    face = resolve_faces(document, {control.key: control.face})[control.key]
    landing = model_point_in_view(
        adapter, view, FINISH_LANDING_MODEL, label="lever rod OD finish landing"
    )
    return face, landing


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
            "Manufacturing Notes",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
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
    # The clamp block slides on the OD: the part's own finish control, on the
    # cylinder's model face (the capsule has no model edge along it).
    od_face, od_landing = _rod_od_finish_pick(adapter, front)
    add_surface_finish(
        adapter,
        front,
        entity=od_face,
        leader_attach_xy=od_landing,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "rod_od"),
        label="lever rod OD finish",
        entity_type="FACE",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.100)
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

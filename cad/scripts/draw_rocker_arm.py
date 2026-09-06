r"""Create the curated machinist drawing for the rocker arm.

The SLDPRT remains authoritative.  This recipe supplies only the rocker-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The strap is a long thin curved seesaw (~292 mm tip to tip, 16 mm deep, 2.5 mm
thick).  A projected side view of the curved strap is a messy band, so the
16 x 2.5 section is carried in the notes and the print shows the profile (front)
plus a 1:2 isometric.  The sheet runs at 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm.py rocker-arm
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from _drawing_entities import CircleEdge, LineEdge, ModelEntities
from _gtol_spec import PlanarFace
from rocker_arm_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_entity_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    auto_arrange_view_dimensions,
    retain_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    repair_project_drawing_layout,
    set_basic_dimension,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from rocker_arm_spec import (
    ARM_THICKNESS,
    HUB_LENGTH,
    PIVOT_HOLE_DIA,
    R_TOP,
    ROD_HOLE_X,
    ROD_HOLE_Y,
    SURFACE_FINISHES,
    TIP_FACE,
    TOP_ARC_LEN,
    TOP_END_X,
    TOP_END_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm"]
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

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front-view model bbox: X symmetric about 0, Y from the centre bottom (0) up to
# the top-arc tip (TOP_END_Y).
_PIVOT_MID_Y = 8.0  # pivot bore centre = ArmDepth / 2
_ROD_HOLE_DIA = 1.994  # #47 drill
_BBOX_CY = TOP_END_Y / 2.0

FRONT_CENTER = (0.180, 0.175)
RIGHT_CENTER = (0.300, 0.165)
ISO_CENTER = (0.345, 0.205)

# Tip-face midpoint (model mm): the top-arc endpoint pushed half the tip face
# outward along the end radius -- where datum C (clocking) attaches.
_TIP_FACE_MID_X = TOP_END_X + (TIP_FACE / 2.0) * (TOP_END_X / R_TOP)
_TIP_FACE_MID_Y = TOP_END_Y - (TIP_FACE / 2.0) * math.cos(TOP_ARC_LEN / 2.0 / R_TOP)


def _sheet_xy(mx: float, my: float) -> tuple[float, float]:
    """Sheet (x, y) of a model point in the bbox-centred front view (1:2)."""
    return (
        FRONT_CENTER[0] + mx * _S / 1000.0,
        FRONT_CENTER[1] + (my - _BBOX_CY) * _S / 1000.0,
    )


# The large concentric radii are carried in the manufacturing note: imported
# radius dimensions retain off-sheet centre witnesses even in shortened-radius
# mode.  Keeping them as notes avoids clipped geometry without losing values.
FRONT_KEEP = ("PivotDia",)
NOTE_ONLY_DIMENSIONS = {"TopRadius", "BottomRadius"}
RIGHT_KEEP: tuple[str, ...] = ()
TOP_KEEP: tuple[str, ...] = ()


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm; tapered strap; seesaw pivot",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    # Explicit view scales establish the sheet layout, not attachment identity.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    # 1:1 right end view: the 2.50 x ~29 strap section -- shows the section the
    # profile notes describe, gives the through direction, and carries datum B
    # (the broad face) so the rod-pin position frame has an orientation datum.
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    retain_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    entities = ModelEntities(front.ReferencedDocument).resolve(
        {
            "pivot": CircleEdge(
                PIVOT_HOLE_DIA / 2.0, (0, _PIVOT_MID_Y, -HUB_LENGTH / 2.0), (0, 0, 1)
            ),
            "rod": CircleEdge(
                _ROD_HOLE_DIA / 2.0,
                (ROD_HOLE_X, ROD_HOLE_Y, -ARM_THICKNESS / 2.0),
                (0, 0, 1),
            ),
            "broad": PlanarFace((0, 0, 1), ARM_THICKNESS / 2.0),
            "tip": LineEdge(
                (_TIP_FACE_MID_X, _TIP_FACE_MID_Y, -ARM_THICKNESS / 2.0),
                (TOP_END_X / R_TOP, -math.cos(TOP_ARC_LEN / 2.0 / R_TOP), 0),
            ),
        }
    )

    # Rod-pin hole native callout (the #47 wizard hole near the +X tip).
    add_native_hole_callout(
        adapter,
        front,
        edge=entities["rod"],
        callout_xy=(0.300, 0.128),
        label="rod-pin hole",
    )

    # Locate the rod-pin hole from the pivot bore with X and Y BASIC coordinate
    # components.  The rod-pin centre is NOT collinear with the pivot (7.30 mm
    # above its mid-height), so a single slant centre distance would leave the
    # angular component uninspectable; two component dimensions fully define
    # the true position the FCF below controls.
    rod_location_x = add_entity_dimension(
        adapter,
        front,
        entities=(entities["pivot"], entities["rod"]),
        text_xy=(0.180, 0.138),
        label="rod-pin X location",
        orientation="horizontal",
    )
    set_basic_dimension(adapter, rod_location_x, label="rod-pin X location")
    rod_location_y = add_entity_dimension(
        adapter,
        front,
        entities=(entities["pivot"], entities["rod"]),
        text_xy=(0.267, 0.162),
        label="rod-pin Y location",
        orientation="vertical",
    )
    set_basic_dimension(adapter, rod_location_y, label="rod-pin Y location")

    # Datum A identifies the pivot bore's cylindrical surface; let the native
    # annotation choose its station on that known model rim.
    add_datum_feature(
        adapter,
        front,
        entity=entities["pivot"],
        datum="A",
        label="pivot bore cylindrical datum feature",
        shoulder=True,
    )
    # Reuse the resolved bore, including its hub-end station; the concentric
    # hub rim can never satisfy this role's centre/radius constraints.
    add_surface_finish(
        adapter,
        front,
        entity=entities["pivot"],
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bore"),
        label="pivot bore finish",
    )
    # Datum B (broad face, on the end view) orients the hole axes; datum C
    # (the +X tip face) clocks rotation about the pivot axis, so the X/Y BASIC
    # coordinates above have an inspectable direction.
    add_datum_feature(
        adapter,
        right,
        entity=entities["broad"],
        entity_type="FACE",
        datum="B",
        label="broad face",
    )
    add_datum_feature(
        adapter,
        front,
        entity=entities["tip"],
        datum="C",
        label="rod-side tip face",
    )
    add_feature_control_frame(
        adapter,
        front,
        entity=entities["rod"],
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["rod-pin hole position"],
        datums=("A", "B", "C"),
        diameter=True,
        label="rod-pin hole position",
    )

    manufacturing = add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.082
    )
    caption = add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.150)

    auto_arrange_view_dimensions(adapter, (front, right, iso))
    from _drawing_native_layout import LayoutNote
    from _drawing_view_packing import Axis, AxisOrder

    # The right profile is enlarged independently (1:1 versus 1:2 front).
    # Preserve its side of the elevation without inventing projected alignment.
    repair_project_drawing_layout(
        adapter,
        views={"front": front, "right": right, "iso": iso},
        orderings=(AxisOrder(Axis.X, "front", "right"),),
        notes=(
            LayoutNote("manufacturing", manufacturing.GetAnnotation()),
            LayoutNote("iso-caption", caption.GetAnnotation(), "iso"),
        ),
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Manufacturing Drawing",
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

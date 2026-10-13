r"""Create the curated machinist drawing for the pen hanger.

The SLDPRT remains authoritative.  This recipe supplies only the hanger's views,
the placement of its imported model dimensions, the hanger-screw callout, and
the property-linked notes; sheet/template and export behavior lives in
``_drawing_common``.  Dimension import and curation live in
``_drawing_dimension_import``; places and bands are authored on the part.

The pen hanger is a black tapered steel strap (3 thick, 16 -> 10 wide, 170
tall) with two open U guide plates brazed across its front face; the pen rod
hangs in both slots.  The front view (1:1, ``*Back``: looking at the strap's
front face and the plates from the machine front, as note 1 names it) carries
the strap outline, the tap station, the upper plate's drop and the plates'
thickness; section A-A (2:1) cuts across the upper plate and looks down on its
U, carrying the slot, its corner radius and the strap stock; the shaded
isometric sits right.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pn_pen_hanger.py pn-pen-hanger
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_detail_projection import settle_detail_projection
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_callout_thread_class import omit_title_block_thread_class
from _holes import TAP_DRILL_MM
from _paths import CAD_ROOT
from _section_axis import position_section_caption
from _session import run_build
import _telemetry
from pn_pen_hanger_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_PLATE_T,
    GUIDE_PLATE_WIDTH,
    GUIDE_PLATE_YS,
    PLATE_FRONT_Z,
    SCREW_HOLE_XY,
    SCREW_TAP_SPEC,
    SLOT_BOTTOM_Z,
    STRAP_BOT_X,
    STRAP_BOT_Y,
    STRAP_TOP_X,
    STRAP_Z,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_hanger"]
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

SHEET_SCALE = (1.0, 1.0)  # the 170-tall strap fits the sheet at full size
FRONT_SCALE = (1, 1)
SECTION_SCALE = (2, 1)  # the slot's 0.05 band and its corner radius need room
ISO_SCALE = (1, 2)
_FRONT_M_PER_MM = FRONT_SCALE[0] / FRONT_SCALE[1] / 1000.0
_SECTION_M_PER_MM = SECTION_SCALE[0] / SECTION_SCALE[1] / 1000.0

# Model extents (local mm) of the front (X-Y) silhouette.
_X = (min(STRAP_TOP_X[0], STRAP_BOT_X[0]), max(STRAP_TOP_X[1], GUIDE_PLATE_WIDTH / 2.0))
_Y = (STRAP_BOT_Y, 0.0)
_CX = (_X[0] + _X[1]) / 2.0
_CY = (_Y[0] + _Y[1]) / 2.0
_HALF_PLATE = GUIDE_PLATE_WIDTH / 2.0


def _strap_x_at(y_mm: float) -> tuple[float, float]:
    """The tapered strap's (left, right) edges (local x) at local height y."""
    t = y_mm / STRAP_BOT_Y
    return (
        STRAP_TOP_X[0] + (STRAP_BOT_X[0] - STRAP_TOP_X[0]) * t,
        STRAP_TOP_X[1] + (STRAP_BOT_X[1] - STRAP_TOP_X[1]) * t,
    )


# Section A-A: a horizontal cutting plane through the upper plate's
# mid-thickness, looking down (-y) on its U.  Shown cut faces only, its ink is
# the strap's section there plus the plate's U; the cutting line overruns
# that silhouette by SECTION_LINE_OVERRUN each side so the cut closes.
SECTION_Y = GUIDE_PLATE_YS[1] + GUIDE_PLATE_T / 2.0
_SECTION_X = (
    min(_strap_x_at(SECTION_Y)[0], -_HALF_PLATE),
    max(_strap_x_at(SECTION_Y)[1], _HALF_PLATE),
)
_SECTION_Z = (PLATE_FRONT_Z, STRAP_Z[1])
_SX = (_SECTION_X[0] + _SECTION_X[1]) / 2.0
_SZ = (_SECTION_Z[0] + _SECTION_Z[1]) / 2.0
SECTION_LINE_OVERRUN = 1.5
SECTION_LINE_MODEL_MM = (
    (_SECTION_X[1] + SECTION_LINE_OVERRUN, SECTION_Y, 0.0),
    (_SECTION_X[0] - SECTION_LINE_OVERRUN, SECTION_Y, 0.0),
)

# Sheet layout (meters).  The tall front view hugs the left margin (its
# stacked top dimensions under the border, its bottom pair over its label);
# the tap callout sits right of its top, in the gap before section A-A; the
# section stands right of the callout with its width rows, fit callout and
# native caption stacked below it, the notes under the caption clear of the
# title block; the isometric to the right.
FRONT_CENTER = (0.075, 0.150)
SECTION_CENTER = (0.230, 0.195)
ISO_CENTER = (0.370, 0.175)
ISO_NOTE_XY = (0.340, 0.104)
NOTES_XY = (0.110, 0.094)
# Text centre: the leader leaves the tap-drill rim on the sheet-right side and
# drops gently right, crossing only the strap's tapered edge and the
# StrapTaperDx extension line beside it -- no dimension line lies there.
CALLOUT_XY = (0.137, 0.215)
# Under the front view's StrapTaperDx row (its text at y 0.045).
FRONT_NOTE_XY = (0.030, 0.034)


def _fx(model_x_mm: float) -> float:
    # *Back looks along +z at the strap front: model +x prints to the LEFT.
    return FRONT_CENTER[0] - (model_x_mm - _CX) * _FRONT_M_PER_MM


def _fy(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - _CY) * _FRONT_M_PER_MM


def _ax(model_x_mm: float) -> float:
    # Section A-A looks down (-y) with the strap back face up: model +x prints
    # to the LEFT, as in the front view above it.
    return SECTION_CENTER[0] - (model_x_mm - _SX) * _SECTION_M_PER_MM


def _az(model_z_mm: float) -> float:
    # The strap back face (z 0) at the top, the plate front at the bottom.
    return SECTION_CENTER[1] + (model_z_mm - _SZ) * _SECTION_M_PER_MM


_UPPER_TOP_Y = GUIDE_PLATE_YS[1] + GUIDE_PLATE_T

# Front view: the tap station and the strap's top run stacked above it (the
# station's value left of the origin corner, outside the run's extension
# lines); the tap height, the upper plate's drop and the strap's rise stacked
# left, shortest nearest; the lower plate's thickness at the bottom left, its
# value under the plate, far from section A-A's cutting line through the
# upper plate; the strap's bottom width and its taper under the view, so the
# taper's long extension line drops from the top outer corner outside the
# tapered edge instead of running down through the strap.
FRONT_KEEP = {
    "ScrewX": (_fx(0.0) - 0.006, _fy(0.0) + 0.010),
    "StrapTopRun": (_fx(STRAP_TOP_X[0] / 2.0), _fy(0.0) + 0.020),
    "ScrewY": (_fx(_X[1]) - 0.008, _fy(SCREW_HOLE_XY[1] / 2.0)),
    "UpperPlateDrop": (_fx(_X[1]) - 0.018, _fy(_UPPER_TOP_Y / 2.0)),
    "StrapRise": (_fx(_X[1]) - 0.030, _fy(_CY)),
    "PlateThick": (_fx(_X[1]) - 0.008, _fy(STRAP_BOT_Y) - 0.006),
    "StrapBotWidth": (_fx(0.0), _fy(STRAP_BOT_Y) - 0.010),
    "StrapTaperDx": (
        _fx((STRAP_TOP_X[0] + STRAP_BOT_X[0]) / 2.0),
        _fy(STRAP_BOT_Y) - 0.020,
    ),
}
# Section A-A: the U's widths stacked under its plate front, the arm nearest
# (its value left of the U), the plate width next (its value right of the U,
# off the slot's extension lines), the slot width outermost and centred with
# its fit callout below, free of every other row; the plate reach and,
# outside it, the slot bottom from the strap back face, on the left; the
# strap stock thickness right of the strap end; the corner radius's text
# up-right of the -x corner it is attached to, so its leader leaves the arc
# outward through the arm and crosses no other ink.
SECTION_KEEP = {
    "ArmWidth": (_ax(_HALF_PLATE) - 0.006, _az(PLATE_FRONT_Z) - 0.008),
    "PlateWidth": (_ax(-_HALF_PLATE) + 0.008, _az(PLATE_FRONT_Z) - 0.016),
    "SlotWidth": (_ax(0.0), _az(PLATE_FRONT_Z) - 0.026),
    "PlateReach": (
        _ax(_HALF_PLATE) - 0.008,
        _az((PLATE_FRONT_Z + SLOT_BOTTOM_Z) / 2.0),
    ),
    "SlotBottom": (_ax(_HALF_PLATE) - 0.020, _az(SLOT_BOTTOM_Z / 2.0)),
    "StrapThick": (_ax(_SECTION_X[0]) + 0.008, _az((STRAP_Z[0] + STRAP_Z[1]) / 2.0)),
    "SlotCornerR": (_ax(-_HALF_PLATE) + 0.015, _az(SLOT_BOTTOM_Z) + 0.012),
}
# The native SECTION A-A / SCALE 2 : 1 caption's top centre, under the slot
# width's fit callout.
SECTION_CAPTION_XY = (SECTION_CENTER[0], _az(PLATE_FRONT_Z) - 0.049)


def _create_section(adapter: Any, front: Any) -> Any:
    """Section A-A across the upper plate, cut faces only, looking down."""
    line = [
        model_point_in_view(
            adapter,
            front,
            tuple(value / 1000.0 for value in point),
            label="section A-A cutting line",
        )
        for point in SECTION_LINE_MODEL_MM
    ]
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        label="upper guide plate section",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # Nothing below the plate (the lower plate, the strap's foot) prints over
    # the U.  R2026x declares the setter void; only the getter is tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="hanger section cut faces only")
    if not bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError("hanger section A-A retained geometry beyond the cut")
    ratio = tuple(float(value) for value in native.ScaleRatio)
    if not math.isclose(ratio[0] / ratio[1], SECTION_SCALE[0] / SECTION_SCALE[1]):
        raise RuntimeError(f"hanger section A-A scale did not persist: {ratio}")
    _orient_section(adapter, native, cut)
    # A section shows no hidden lines (rule 9); set before centring so the
    # display change cannot shift the placed ink.
    set_hidden_lines_removed(adapter, section)
    _centre_section(adapter, native)
    return section


def _section_axes(
    adapter: Any, native: Any
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Sheet directions of model -x and +z (1 mm each) in section A-A."""
    native.UpdateViewDisplayGeometry()
    origin, minus_x, plus_z = model_points_in_view(
        adapter,
        native,
        (
            (0.0, SECTION_Y / 1000.0, 0.0),
            (-0.001, SECTION_Y / 1000.0, 0.0),
            (0.0, SECTION_Y / 1000.0, 0.001),
        ),
        label="hanger section A-A axes",
        names=("origin", "minus x", "plus z"),
    )
    return (
        (minus_x[0] - origin[0], minus_x[1] - origin[1]),
        (plus_z[0] - origin[0], plus_z[1] - origin[1]),
    )


def _orient_section(adapter: Any, native: Any, cut: Any) -> None:
    """Look down on the U: model -x to sheet right, the strap back face up.

    Looking along -y with +z up puts -x on the right, a right-handed pair on
    the sheet; a left-handed pair is the cut looking UP, so the cut direction
    is reversed.  The view then turns until -x reads right (draw_fr_top_frame
    ``_orient_cut_section``).
    """
    right, up = _section_axes(adapter, native)
    if right[0] * up[1] - right[1] * up[0] < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="hanger section reversed")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("hanger section A-A cut direction did not persist")
        right, up = _section_axes(adapter, native)
    native.Angle = float(native.Angle) - math.atan2(right[1], right[0])
    rebuild_drawing(adapter, label="hanger section turned")
    right, up = _section_axes(adapter, native)
    tolerance = 1e-7
    if (
        right[0] <= 0.0
        or abs(right[1]) > tolerance
        or up[1] <= 0.0
        or abs(up[0]) > tolerance
    ):
        raise RuntimeError(
            f"hanger section A-A is not looking down on the U: {right=}, {up=}"
        )
    _telemetry.info(f"hanger section A-A angle={float(native.Angle):.6f} rad")


def _centre_section(adapter: Any, native: Any) -> None:
    """Land the section's silhouette centre on SECTION_CENTER.

    Placed by projection, not by outline: whatever the outline of a cut-only
    section boxes, every SECTION_KEEP position is computed from where the
    cut face's own centre projects.  ``SetViewPosition`` moves the ink by the
    difference from the Position it reads (draw_pd_transgear_thumbnut).
    """
    anchor = (_SX / 1000.0, SECTION_Y / 1000.0, _SZ / 1000.0)
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"hanger section A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre hanger section A-A")
        rebuild_drawing(adapter, label="hanger section re-centred")
    settle_detail_projection(
        adapter,
        native,
        anchor,
        ink_xy=SECTION_CENTER,
        tolerance_xy=(0.0005, 0.0005),
        label="hanger section A-A",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-hanger source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Hanger Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen hanger; tapered strap; two open U pen-rod guide plates",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # *Back looks at the strap's front face from the machine front: the plates
    # face the reader and note 1's FRONT FACE is the face the view shows.
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=FRONT_SCALE)
    set_hidden_lines_removed(adapter, front)
    section = _create_section(adapter, front)
    position_section_caption(
        adapter, section, SECTION_CAPTION_XY, label="hanger section A-A"
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The iso too: a new view already reads Shaded With Edges, so
    # finalize_drawing's SetDisplayMode4 is a no-op that leaves its cosmetic
    # threads at draft quality (farm c0b95549c readback cosmetic_threads=False).
    # From HLR the shading call really changes the mode and takes precision.
    set_hidden_lines_removed(adapter, iso)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="section A-A",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the hanger-screw hole")

    # Pick the tap-drill rim on its sheet-right side (model -x under *Back),
    # not the cosmetic thread or the hole centre: the leader leaves toward
    # CALLOUT_XY without crossing the dimensions stacked left of the strap.
    tap_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            _fx(SCREW_HOLE_XY[0] - TAP_DRILL_MM[SCREW_TAP_SPEC.size] / 2.0),
            _fy(SCREW_HOLE_XY[1]),
        ),
        callout_xy=CALLOUT_XY,
        label="hanger-screw through tap",
        process="TAP",
    )
    # The title block's THREADS row owns the general thread class (rule 2).
    omit_title_block_thread_class(tap_callout, label="hanger-screw through tap")

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Front View Note", *FRONT_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # Materialize the iso's cosmetic thread before the strict final note cleanup;
    # otherwise its descriptive label first appears during the native drawing save.
    import_cosmetic_threads(adapter, iso)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Hanger Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=("#8-32 Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

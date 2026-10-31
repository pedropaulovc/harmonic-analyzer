r"""Create the curated machinist drawing for the pinion lift cam.

An eccentric steel collar: the Ø.2510 reamed bore is offset .079 from the
Ø.575 OD axis (so the collar and bore are NOT concentric -- the drawing
dimensions that offset explicitly, per the cam-note precedent).  Decimal-inch
sheet (#290); the model keeps its millimetre nominals.  The collar/bore sketches live
on the Front plane (front view carries bore/eccentricity); the side profile
carries collar length/OD, while the set-screw end view owns the #2-56 tapped
hole and its station (U28: the raised boss is gone).

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_pinion_cam.py dt-pinion-cam
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
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_finish import add_surface_finish
from _drawing_source_guard import (
    SourceCheck,
    assert_source_closed,
    capture_clean_source,
    source_checkpoint,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _machinist_review_mode import MachinistReviewMode
from _named_views import octant_view_name
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_pinion_cam_spec import (
    BORE_CALLOUT,
    CAM_OD,
    COLLAR_OD_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    ECC,
    ECCENTRICITY_CALLOUT,
    SET_SCREW_STAKE_STEP_KEY,
    SURFACE_FINISHES,
    TAP_DRILL_CALLOUT,
    THIN_WALL_CALLOUT,
    THIN_WALL_MIN_MM,
    THIN_WALL_MIN_TOL_TYPE,
)
from dt_drive_train_steps import step_ref


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_pinion_cam"]
PART_STEM = SPEC.artifact_stem
# The drawing's own registry package: its drawing_unit (in) selects the
# sheet's document units and the finalizer's unit proof.
PACKAGE = "dt-pinion-cam"
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (3.0, 1.0)

# Front view (XY): the collar circle is centred ECC BELOW the origin and the
# bore is ON the origin, so the view's bbox is the collar circle itself.
FRONT_BBOX_CY = ((CAM_OD / 2.0 - ECC) + (-(ECC + CAM_OD / 2.0))) / 2.0
FRONT_CENTER = (0.105, 0.150)
# Third angle: the right-side profile projects to the right of the front
# view.  The rotated set-screw end view is deliberately offset from that
# projection.
SIDE_CENTER = (0.260, 0.150)
ISO_CENTER = (0.365, 0.165)
BOTTOM_CENTER = (0.320, 0.105)

def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


OD_R_SHEET = CAM_OD * SHEET_SCALE[0] / 2000.0
_SQRT_HALF = 0.5**0.5

# Diameters go on the view that shows them as a SOLID edge: the OD as the
# profile view's width, the tapped hole on its end view, and the bore on the
# circular view where it is the only diagonal (its and the OD's diagonals both
# pass through nearly the same centre, so the two cannot share a view without
# crossing -- machinist round 2).
# RV-01's accepted thin-side wall (rule 20): the part's native ".0797 MIN"
# reference, drawn up the wall over the bore, its text above the OD's top
# between the bore and eccentricity callouts.
FRONT_KEEP = {
    "BoreDia": (0.055, 0.180),
    "CollarCy": (0.150, 0.200),
    "ThinWallMin": (FRONT_CENTER[0], 0.195),
}
SIDE_KEEP = {
    "Depth": (SIDE_CENTER[0], SIDE_CENTER[1] + 0.055),
    # ENFORCE r2: at +0.035 the follower-pin line ran back over the right
    # face; +0.051 centres the 53-wide callout between the profile and the
    # isometric view boxes (~5.5 clear each side).
    "CollarOd": (SIDE_CENTER[0] + 0.051, SIDE_CENTER[1]),
}
# The tap-drill callout sits LEFT of the end view, under the profile view:
# placed right of it, its diameter line ran out past the view (render r1).
# ENFORCE r2: far enough left that its leader passes above the rotated
# view's title.
# The set-screw station stays on the view along the screw axis, where the
# hole is drawn solid with its centre mark (ENFORCE r3/r4: moved to the
# profile, its hole-axis witness either ran the full height of the plain
# cylinder or floated below it with nothing drawn where it ended).
BOTTOM_KEEP = {
    "TapDrillDia": (0.215, 0.100),
    "TapCz": (BOTTOM_CENTER[0] + 0.036, BOTTOM_CENTER[1] + 0.007),
}
DIMENSION_CALLOUTS = {
    "BoreDia": BORE_CALLOUT,
    "CollarOd": COLLAR_OD_CALLOUT,
    "CollarCy": ECCENTRICITY_CALLOUT,
    "TapDrillDia": f"{TAP_DRILL_CALLOUT}\n{step_ref(SET_SCREW_STAKE_STEP_KEY)}",
    "ThinWallMin": THIN_WALL_CALLOUT,
}
# Decimal places are the part's (dt_pinion_cam_spec.DRAWING_PRECISION, applied
# by build_dt_pinion_cam): inch places, four on the reamed bore, three on the
# OD, eccentricity and tap drill, two on the length and station, four on the
# single-limit wall minimum.
# The sheet only reads them back.


def _limit_witness_lines(
    adapter: Any, annotations: list[Any], names: set[str], length: float
) -> None:
    """Keep long axis witnesses from running through the circular profile."""
    remaining = set(names)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        native_annotation = _early_bound(annotation, "IAnnotation")
        display = _early_bound(
            native_annotation.GetSpecificAnnotation(), "IDisplayDimension"
        )
        display.MaxWitnessLineLength = float(length)
        if abs(float(display.MaxWitnessLineLength) - length) > 1e-9:
            raise RuntimeError(f"{name}: maximum witness-line length did not persist")
        remaining.remove(name)
    if remaining:
        raise RuntimeError(
            f"missing dimensions for witness-line limits: {sorted(remaining)!r}"
        )
    adapter.currentModel.GraphicsRedraw2()


def _require_thin_wall_min(adapter: Any, annotations: list[Any]) -> None:
    """Prove the front view prints the part's RV-01 wall minimum natively:
    one ThinWallMin, measuring the printed limit and carrying swTolMIN."""
    matches = [a for a in annotations if dimension_name(adapter, a) == "ThinWallMin"]
    if len(matches) != 1:
        raise RuntimeError(f"expected one ThinWallMin dimension, found {len(matches)}")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != THIN_WALL_MIN_TOL_TYPE:
        raise RuntimeError(f"ThinWallMin lost its MIN limit: type {int(tolerance.Type)}")
    if abs(float(dimension.SystemValue) - THIN_WALL_MIN_MM / 1000.0) > 1e-9:
        raise RuntimeError(f"ThinWallMin does not measure {THIN_WALL_MIN_MM:g} mm")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-cam source", await adapter.open_model(str(SOURCE)))
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
    # #290 native acceptance: the sheet never modifies its source part.  The
    # part's in-memory save flag after views exist is recorded, not refused --
    # a view's camera can set it without a write, and the bytes are the
    # persistence proof.
    source = capture_clean_source(
        SOURCE, adapter.currentModel, label=PART_STEM,
        check=SourceCheck.TRANSIENT_VIEW_STATE,
    )
    guard = source_checkpoint(source)
    drawing_model, sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        decimals=3,
        checkpoint=guard,
        package_name=PACKAGE,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Lift Cam Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion lift cam; eccentric collar; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(3, 1))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(3, 1))
    # The built-in isometric looks from +Y, which hides the set-screw hole --
    # the part's one additional feature -- behind the collar, because the hole
    # opens at -Y.  The FRONT-BOTTOM-RIGHT octant the PART names shows the
    # tapped opening (machinist round 2).
    iso = place_view(
        adapter, str(SOURCE), octant_view_name(1, -1, 1), *ISO_CENTER, scale=(2, 1)
    )
    # The front view keeps its hidden lines: they are the only place the tap
    # drill shows WHICH side of the eccentric it enters -- the heavy side,
    # opposite the bore offset (drawing-guidelines.md rule 9 (show internal shape in solid lines)'s cross-hole-through-a-wall case;
    # Fable review r4 blocker).
    set_hidden_lines_visible(adapter, front)
    for view in (side, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    # The construction-only tap reference is now unabsorbed and saved hidden;
    # opt into the established per-view import without changing its ownership.
    bottom_annotations = curate_view_dimensions(
        adapter,
        bottom,
        keep=BOTTOM_KEEP,
        view_label="set-screw end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*bottom_annotations, *front_annotations, *side_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _limit_witness_lines(
        adapter,
        front_annotations,
        {"CollarCy"},
        0.008,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _require_thin_wall_min(adapter, front_annotations)
    # No explicit centre marks: the template marks every hole as each view is
    # placed, and AutoInsertCenterMarks2 printed a second, identical mark on
    # the bore and the tap (layout audit duplicate-annotation, ENFORCE r2; as
    # draw_mg_wheel_drum, #913).

    # Cam-OD roughness (the follower's running surface): the lower-right OD
    # rim, clear of the bore callout's upper-left diagonal and of the tap
    # drill's hidden lines at the bottom, with a small routine callout below.
    od_center = (FRONT_CENTER[0], _front_y(-ECC))
    od_finish_edge = (
        od_center[0] + OD_R_SHEET * _SQRT_HALF,
        od_center[1] - OD_R_SHEET * _SQRT_HALF,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=od_finish_edge,
        symbol_xy=(0.150, 0.105),
        control=surface_finish_by_key(SURFACE_FINISHES, "cam_od"),
        label="cam OD finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    if add_note(
        adapter, "VIEW ALONG SET-SCREW AXIS - ROTATED 90 DEG", 0.255, 0.075
    ) is None:
        raise RuntimeError("failed to label rotated cam set-screw end view")
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.205)

    artifacts = await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lift Cam Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # One native tap adds one redundant automatic thread note; the
        # dimension's curated callout already releases the same thread.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
        checkpoint=guard,
        package_name=PACKAGE,
    )
    assert_source_closed(source, stage="after finalize")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

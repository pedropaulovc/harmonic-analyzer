r"""Create the curated machinist drawing for the pinion lift cam.

An eccentric steel collar: the Ø6.37 bore is offset 1.4 mm from the Ø10.32 OD
axis (so the collar and bore are NOT concentric -- the drawing dimensions that
offset explicitly, per the cam-note precedent).  The collar/bore sketches live
on the Front plane (front view carries bore/eccentricity); a true boss-profile
view carries collar length/OD while the visible boss end owns diameter/station.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_cam.py pinion-cam
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
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _named_views import octant_view_name
from _surface_finish import surface_finish_by_key
from pinion_cam_spec import (
    BORE,
    BOSS_PROUD,
    CAM_OD,
    DRAWING_PRECISION_BY_NAME,
    ECC,
    LIFT_ROD_NUMBER,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_cam"]
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

SHEET_SCALE = (3.0, 1.0)

# Front view (XY): the collar circle is centred ECC BELOW the origin, the bore
# is ON the origin, and the boss stub points down.  bbox spans the boss tip.
FRONT_BBOX_CY = ((CAM_OD / 2.0 - ECC) + (-(ECC + CAM_OD / 2.0 + BOSS_PROUD))) / 2.0
FRONT_CENTER = (0.105, 0.140)
# Third angle: the right-side boss profile projects to the right of the front
# view; its separated label makes it unambiguous when read away from that axis.
SIDE_CENTER = (0.220, 0.140)
ISO_CENTER = (0.350, 0.175)
BOTTOM_CENTER = (0.270, 0.185)

def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + model_x_mm * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * SHEET_SCALE[0] / 1000.0


BORE_R_SHEET = BORE * SHEET_SCALE[0] / 2000.0
_SQRT_HALF = 0.5**0.5

# Diameters go on the view that shows them as a SOLID edge: the OD as the
# boss-profile view's width, the boss on the boss end view, and the bore on the
# circular view where it is the only diagonal (its and the OD's diagonals both
# pass through nearly the same centre, so the two cannot share a view without
# crossing -- machinist round 2).
FRONT_KEEP = {
    "BoreDia": (0.055, 0.176),
    "CollarCy": (0.172, 0.190),
    "BossProjection": (0.180, 0.112),
}
SIDE_KEEP = {
    "Depth": (SIDE_CENTER[0], SIDE_CENTER[1] + 0.040),
    "CollarOd": (SIDE_CENTER[0] + 0.035, SIDE_CENTER[1]),
}
BOTTOM_KEEP = {
    "BossDia": (0.312, 0.218),
    "BossCz": (0.235, 0.225),
}
DIMENSION_CALLOUTS = {
    "BoreDia": (
        "REAM THRU\n"
        "0.010-0.045 DIAMETRAL CLEARANCE\n"
        f"ON LIFT ROD {LIFT_ROD_NUMBER}\n"
        "LOCK AFTER POSITIONING"
    ),
    "CollarCy": "ECCENTRICITY\nBORE AXIS TO OD AXIS",
    "BossProjection": "RAISED BOSS PROJECTION (REF)",
    "BossDia": (
        "M2.5 X 0.45-6H THRU TO BORE\n"
        "COSMETIC RAISED BOSS;\n"
        "SIZE/SHAPE NONCRITICAL"
    ),
    "BossCz": "BOSS AXIS STATION",
}
# Decimal places are the part's (pinion_cam_spec.DRAWING_PRECISION, applied
# by build_pinion_cam): two on the critical bore, OD and eccentricity, one
# everywhere else.  The sheet only reads them back.


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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
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
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(2, 1))
    # The built-in isometric looks from +Y, which hides the set-screw boss --
    # the part's one additional feature -- behind the collar, because the boss
    # points at -Y.  The FRONT-BOTTOM-RIGHT octant the PART names shows the
    # boss and its tapped opening (machinist round 2).
    iso = place_view(
        adapter, str(SOURCE), octant_view_name(1, -1, 1), *ISO_CENTER, scale=(2, 1)
    )
    for view in (front, side, bottom, iso):
        set_hidden_lines_removed(adapter, view)

    # The boss end view is curated first so its visible circle owns both the
    # cosmetic diameter and the 3.0 axial station; either dimension imported
    # into the opposite length view could attach only to hidden geometry.
    bottom_annotations = curate_view_dimensions(
        adapter, bottom, keep=BOTTOM_KEEP, view_label="boss end"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="boss profile"
    )
    annotations = [*bottom_annotations, *front_annotations, *side_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _limit_witness_lines(
        adapter,
        front_annotations,
        {"CollarCy", "BossProjection"},
        0.025,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The boss dome is cosmetic: its diameter and projection communicate
    # nominal shape, but neither controls the functional M2.5 thread, which
    # runs through the collar's thick wall.  Keep both model-owned nominals
    # explicitly reference-only while the 3.0 station remains controlling.
    reference_groups = {
        "BossProjection": front_annotations,
        "BossDia": bottom_annotations,
    }
    for name, group in reference_groups.items():
        matches = [
            annotation
            for annotation in group
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one cosmetic {name} reference dimension")
        set_reference_dimension(
            adapter,
            matches[0],
            label=f"cosmetic {name} reference",
        )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to boss end view")

    # Bore roughness: use the lower-left bore rim and a small, routine callout
    # below the circular view so it cannot dominate or cross the dimensions.
    bore_center = (FRONT_CENTER[0], _front_y(0.0))
    bore_finish_edge = (
        bore_center[0] - BORE_R_SHEET * _SQRT_HALF,
        bore_center[1] - BORE_R_SHEET * _SQRT_HALF,
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_finish_edge,
        symbol_xy=(0.055, 0.105),
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="cam bore finish",
        char_height=0.0025,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    if add_note(adapter, "RIGHT-SIDE VIEW", 0.185, 0.205) is None:
        raise RuntimeError("failed to label cam right-side view")
    if add_note(adapter, "BOSS END VIEW SCALE 2:1", 0.245, 0.164) is None:
        raise RuntimeError("failed to label cam boss end view")
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.135)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lift Cam Manufacturing Drawing",
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

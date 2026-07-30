r"""Create the curated machinist drawing for the cylinder-gear arbor."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cylinder_gear_shaft_spec import (
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    SHAFT_DIA,
    SHAFT_LENGTH,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cylinder_gear_shaft"]
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
# The arbor is modelled axis-along-+Y (its assembly pose), so no standard side
# view shows the shaft horizontal: the end circle comes from "*Top" and the
# long profile from "*Front" rotated -90 deg (IView.Angle) so the turned part
# reads axis-horizontal, machinist convention.
END_CENTER = (0.055, 0.205)
PROFILE_CENTER = (
    END_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    END_CENTER[1],
)
PROFILE_ROTATION = -math.pi / 2.0  # model +Y (arbor axis) -> sheet +x
# The 187 shaft's isometric silhouette is a mostly-VERTICAL slender bar
# (~0.076 m each side of center at 1:1 -- too tall for the band between the
# right-end Ra symbol and the title block's 0.064 top rule), so it renders at
# 1:2 in the empty band right of the notes block.
ISO_CENTER = (0.355, 0.140)
ISO_SCALE = (1, 2)

# Left of the end circle, ON its centre height so the diameter line runs
# horizontally through the centre rather than diagonally.  x=0.032, not the old
# bbox-derived 0.022: the callout is centred on its anchor and ~22 mm wide now
# that it renders horizontally, so it needs to start clear of the border rule
# at ~0.0126.
END_KEEP = {
    "ShaftDia": (0.032, END_CENTER[1]),
}
PROFILE_KEEP = {
    "Depth": (PROFILE_CENTER[0], PROFILE_CENTER[1] - 0.025),
}
# Size tolerances live on the source-model dimensions; the sheet renders them natively.
DIMENSION_CALLOUTS: dict[str, str] = {}
# 3/8 in = 9.525 exactly; the sheet default of 2 decimals would print 9.53,
# a false contradiction of the exact inch conversion the arbor's bore mates
# are built on.
DIMENSION_PRECISION = {"ShaftDia": 3}


def _rotate_view(adapter: Any, view: Any, angle: float, *, label: str) -> None:
    """Rotate a placed drawing view about its center and verify it took."""
    ok = adapter._attempt(lambda: setattr(view, "Angle", float(angle)), default=False)
    if ok is False:
        raise RuntimeError(f"failed to rotate {label} drawing view")
    adapter.currentModel.EditRebuild3()
    applied = float(adapter._get_attr_or_call(view, "Angle") or 0.0)
    if abs(math.remainder(applied - angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(
            f"{label} view rotation did not take: {applied:g} rad, expected {angle:g}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear-shaft source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear shaft; stationary arbor; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(2, 1))
    profile = place_view(adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # Rotate BEFORE dimension import so the Depth dim lands on the displayed
    # (horizontal) geometry.
    _rotate_view(adapter, profile, PROFILE_ROTATION, label="profile")
    for view in (end, profile, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    profile_annotations = curate_view_dimensions(
        adapter, profile, keep=PROFILE_KEEP, view_label="profile"
    )
    # Each call must consume every callout it is handed, so split by view.
    set_dimension_callouts(
        adapter,
        end_annotations,
        {n: t for n, t in DIMENSION_CALLOUTS.items() if n in END_KEEP},
    )
    set_dimension_callouts(
        adapter,
        profile_annotations,
        {n: t for n, t in DIMENSION_CALLOUTS.items() if n in PROFILE_KEEP},
    )
    set_dimension_precision(adapter, end_annotations, DIMENSION_PRECISION)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to arbor end view")

    end_radius = SHAFT_DIA * END_VIEW_SCALE / 2000.0
    end_circle = (
        END_CENTER[0] + end_radius,
        END_CENTER[1],
    )
    left_end = (PROFILE_CENTER[0] - SHAFT_LENGTH / 2000.0, PROFILE_CENTER[1])
    right_end = (PROFILE_CENTER[0] + SHAFT_LENGTH / 2000.0, PROFILE_CENTER[1])
    end_top = (END_CENTER[0], END_CENTER[1] + SHAFT_DIA * END_VIEW_SCALE / 2000.0)
    end_upper = (
        END_CENTER[0] + end_radius * math.cos(math.radians(55.0)),
        END_CENTER[1] + end_radius * math.sin(math.radians(55.0)),
    )
    # GD&T is model PMI (cylinder_gear_shaft_spec.PART_DATUMS/
    # GEOMETRIC_CONTROLS, authored by build_cylinder_gear_shaft) — project it
    # and place it where the hand-authored symbols used to sit (the profile
    # view is rotated -pi/2, so sheet-LEFT is model y=0 and the y0 squareness
    # frame takes the left-end spot). Which VIEW receives each annotation
    # depends on its attachment (a datum tag only lands in a view aligned
    # with its face), and the projection fails loud on any mismatch.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=end,
                position=(END_CENTER[0], END_CENTER[1] + 0.024),
                attachment_xy=end_top,
                position_tolerance_m=0.0001,
            ),
            "bearing_cylindricity": PmiDrawingPlacement(
                view=end, position=(0.068, 0.252), attachment_xy=end_upper
            ),
            "y0_end_perpendicularity": PmiDrawingPlacement(
                view=profile,
                position=(left_end[0] - 0.042, 0.180),
                attachment_xy=left_end,
            ),
            "y187_end_perpendicularity": PmiDrawingPlacement(
                view=profile,
                position=(right_end[0] + 0.014, 0.180),
                attachment_xy=right_end,
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="cylinder gear shaft PMI",
    )
    # Up-RIGHT of the end circle, on the same side as the `end_circle` pick
    # (the circle's RIGHTMOST point), so the leader comes in from the right and
    # never crosses the circle.  Two constraints forced this side:
    #   * it used to sit at PROFILE_CENTER[0] and drag a 130 mm diagonal leader
    #     back to this circle; and
    #   * placing it up-LEFT instead only traded that for a leader that raked
    #     across the circle and landed on the datum A tag -- which rests ON the
    #     circle at ~(0.051..0.058, 0.214..0.222) and cannot be moved away.
    #     IAnnotation::SetPosition2 on a DATUM FEATURE symbol sets the "point
    #     where the leader hits the symbol", so a tag that attaches straight to
    #     its edge ignores the requested Y and sits against the geometry.
    # The symbol's ARM extends left of the anchor and its TEXT renders ABOVE the
    # arm and to the RIGHT (ASME Y14.36): ~x=0.075..0.114 / y=0.222..0.237,
    # which clears the profile view (it tops out at y=0.210) and leaves the arm
    # at 0.075, right of the cylindricity frame's near-vertical leader above.
    add_surface_finish(
        adapter,
        end,
        edge_xy=end_circle,
        symbol_xy=(0.078, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bearing"),
        label="arbor bearing finish",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred border rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.092)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Shaft Manufacturing Drawing",
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

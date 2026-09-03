r"""Create the curated machinist drawing for the cylinder-gear arbor.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
plain stationary arbor carries no datums and no feature-control frames -- its
running fit is the band on the model diameter, plus one roughness symbol on
the OD the 20 cylinder gears run free on. The diameter, the length and the Ra
all read on the axis-horizontal profile view (policy rule 7: a turned part is
dimensioned as it sits in the lathe); the end view carries only its centre
mark.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cylinder_gear_shaft_spec import SHAFT_DIA, SHAFT_LENGTH, SURFACE_FINISHES
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
# 0.060 between the end circle and the profile's left end (was 0.045): the
# diameter callout now stands at that end, ~25 mm wide, and needs the room.
PROFILE_CENTER = (
    END_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.060,
    END_CENTER[1],
)
PROFILE_ROTATION = -math.pi / 2.0  # model +Y (arbor axis) -> sheet +x
# The 187 shaft's isometric silhouette is a mostly-VERTICAL slender bar
# (~0.076 m each side of center at 1:1 -- too tall for the band between the
# right-end Ra symbol and the title block's 0.064 top rule), so it renders at
# 1:2 in the empty band right of the notes block.
ISO_CENTER = (0.355, 0.140)
ISO_SCALE = (1, 2)

# Profile-view landmarks: the arbor's left end and its top flank (a 9.525-dia
# cylinder at 1:1, so the top silhouette runs ~4.8 mm above the view centre).
LEFT_END_X = PROFILE_CENTER[0] - SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0
SHAFT_FLANK_Y = PROFILE_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0

# Every marked dimension reads on the profile view: the diameter as a linear
# diameter between the flank silhouettes at the left end, the length below.
# The end view keeps nothing -- SolidWorks inserts each marked model
# dimension into ONE view, so the profile is curated first and the end view
# is never asked (draw_pinion_bracket, 2026-09-02 seat build).
END_KEEP: dict[str, tuple[float, float]] = {}
PROFILE_KEEP = {
    "ShaftDia": (LEFT_END_X - 0.024, PROFILE_CENTER[1]),
    "Depth": (PROFILE_CENTER[0], PROFILE_CENTER[1] - 0.025),
}
# Size tolerances live on the source-model dimensions; the sheet renders them natively.
DIMENSION_CALLOUTS: dict[str, str] = {}
# The diameter is the one fitted feature (3/8 in = 9.525 exactly, SHAFT_H band
# on the model dimension): three decimals say "hold it"; everything else stays
# at the two-place block tolerance.
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
    # Rotate BEFORE dimension import so the Depth and diameter dims land on
    # the displayed (horizontal) geometry.
    _rotate_view(adapter, profile, PROFILE_ROTATION, label="profile")
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton).
    for view in (end, profile):
        set_hidden_lines_visible(adapter, view)

    profile_annotations = curate_view_dimensions(
        adapter, profile, keep=PROFILE_KEEP, view_label="profile"
    )
    set_dimension_callouts(adapter, profile_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, profile_annotations, DIMENSION_PRECISION)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to arbor end view")

    # The arbor OD is the one running surface (the 20 cylinder gears run free
    # on it), so it alone carries a roughness symbol, anchored on the arbor's
    # flank in the profile view (a SILHOUETTE pick: a cylinder carries no
    # model edge along its side, as in draw_pivot_shaft). The Ra text renders
    # ABOVE the arm (ASME Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        profile,
        edge_xy=(PROFILE_CENTER[0] + 0.045, SHAFT_FLANK_Y),
        symbol_xy=(PROFILE_CENTER[0] + 0.045, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bearing"),
        label="arbor bearing finish",
        entity_type="SILHOUETTE",
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

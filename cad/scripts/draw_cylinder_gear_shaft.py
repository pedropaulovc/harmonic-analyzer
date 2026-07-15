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
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cylinder_gear_shaft_spec import SHAFT_DIA, SHAFT_LENGTH
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

END_KEEP = {
    "ShaftDia": (
        END_CENTER[0] - SHAFT_DIA * END_VIEW_SCALE / 1000.0 - 0.014,
        END_CENTER[1] + 0.008,
    ),
}
PROFILE_KEEP = {
    "Depth": (PROFILE_CENTER[0], PROFILE_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {"ShaftDia": "+0.00/-0.02", "Depth": "+/-0.25"}
# 3/8 in = 9.525 exactly; the sheet default of 2 decimals would print 9.53,
# a false contradiction of the exact inch conversion the arbor's bore mates
# are built on.
DIMENSION_PRECISION = {"ShaftDia": 3}


def _rotate_view(adapter: Any, view: Any, angle: float, *, label: str) -> None:
    """Rotate a placed drawing view about its center and verify it took."""
    ok = adapter._attempt(
        lambda: setattr(view, "Angle", float(angle)), default=False
    )
    if ok is False:
        raise RuntimeError(f"failed to rotate {label} drawing view")
    adapter.currentModel.EditRebuild3()
    applied = float(adapter._get_attr_or_call(view, "Angle") or 0.0)
    if abs(math.remainder(applied - angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(
            f"{label} view rotation did not take: {applied:g} rad, "
            f"expected {angle:g}"
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
    profile = place_view(
        adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=(1, 1)
    )
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

    end_circle = (
        END_CENTER[0] + SHAFT_DIA * END_VIEW_SCALE / 2000.0,
        END_CENTER[1],
    )
    left_end = (PROFILE_CENTER[0] - SHAFT_LENGTH / 2000.0, PROFILE_CENTER[1])
    right_end = (PROFILE_CENTER[0] + SHAFT_LENGTH / 2000.0, PROFILE_CENTER[1])
    add_datum_feature(
        adapter,
        end,
        edge_xy=end_circle,
        symbol_xy=(END_CENTER[0], END_CENTER[1] + 0.024),
        datum="A",
        label="arbor axis",
    )
    add_feature_control_frame(
        adapter,
        end,
        edge_xy=end_circle,
        frame_xy=(PROFILE_CENTER[0], 0.232),
        characteristic="cylindricity",
        tolerance="0.01",
        label="arbor bearing cylindricity",
    )
    # The frame extends ~0.027 m right of its anchor; 0.042 keeps the left
    # frame's far edge clear of the Depth extension line at the shaft's end.
    for edge, x, label in (
        (left_end, left_end[0] - 0.042, "left end perpendicularity"),
        (right_end, right_end[0] + 0.014, "right end perpendicularity"),
    ):
        add_feature_control_frame(
            adapter,
            profile,
            edge_xy=edge,
            frame_xy=(x, 0.180),
            characteristic="perpendicularity",
            tolerance="0.05",
            datums=("A",),
            label=label,
        )
    add_surface_finish(
        adapter,
        end,
        edge_xy=end_circle,
        symbol_xy=(PROFILE_CENTER[0], 0.245),
        roughness_ra="1.6",
        label="arbor bearing finish",
    )
    # The left-end symbol sits BELOW the view: at the above-the-view spot its
    # leader would cross the long Ra/cylindricity leaders converging on the
    # nearby end view (pivot-shaft machinist-review finding).
    for edge, xy, label in (
        (left_end, (left_end[0] - 0.018, 0.155), "left end finish"),
        (right_end, (right_end[0] + 0.020, 0.218), "right end finish"),
    ):
        add_surface_finish(
            adapter,
            profile,
            edge_xy=edge,
            symbol_xy=xy,
            roughness_ra="3.2",
            label=label,
        )

    # 0.020, not 0.014 -- the border rule sits at ~0.016, so a note anchored
    # at 0.014 starts its first character on the frame line.
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

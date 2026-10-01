r"""Create the manufacturing drawing for the transgear disc hub (MHA-159).

The edge view is the ``*Top`` orientation turned a quarter turn so the hub's
axis lies horizontal, as it sits in the lathe (policy rule 7): the hub front
face on the left, the flange on the right.  It carries the turned profile:
both diameters beside their steps and both lengths from the flange's rear
face.  Looking down on +Y it sees the radial oil hole end-on, so it also
carries the hole's size and its match-drill callout.  The face view is the
``*Back`` orientation (looking at the hub front) turned to match -- exactly
the third-angle LEFT view of that profile -- so it sits on the profile's axis
to its left and carries the bore and the screw holes on their printed bolt
circle.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from transgear_disc_hub_spec import (
    BORE_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HUB_LENGTH,
    OIL_HOLE_CALLOUT_BELOW,
    SCREW_HOLE_CALLOUT_ABOVE,
    SCREW_HOLE_CALLOUT_BELOW,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_disc_hub"]
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

# A Ø21 × 9.4 part: 4:1 keeps the #0-80 holes, the Ø1.2 oil hole and the
# thin flange legible on the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
# *Top turned +90 degrees: model -Z (the hub front) to paper-left, model +X
# up.  *Back turned -90 degrees: model +X up, model +Y (the oil hole) right,
# which is the third-angle left view of that profile.
SIDE_VIEW_ANGLE = math.pi / 2.0
END_VIEW_ANGLE = -math.pi / 2.0
SIDE_CENTER = (0.200, 0.170)
END_CENTER = (0.085, SIDE_CENTER[1])
ISO_CENTER = (0.330, 0.190)
NOTES_XY = (0.020, 0.075)


def _side_x(z_mm: float) -> float:
    """Sheet X of a model-Z station on the edge view (the view centres on the
    part's z span, -HUB_LENGTH..0)."""
    return SIDE_CENTER[0] + (z_mm + HUB_LENGTH / 2.0) * _S


HUB_FRONT_X = _side_x(-HUB_LENGTH)
FLANGE_REAR_X = _side_x(0.0)

# Every size and callout sits outside the silhouettes.
# - Face view: the bolt circle diameter above-left, the screw-hole size (3X,
#   drilled through the flange) right of it, the bore below with its press
#   callout under the bore's value.
# - Edge view: each turned diameter inline beside its own step (the hub's
#   left of the hub front face, the flange's right of the flange rear face);
#   the overall length on the row above, the flange's thickness right of the
#   flange, and the oil hole's size with its match-drill callout below-right,
#   under the flange.
END_KEEP = {
    "BoltCircleDia": (END_CENTER[0] - 0.030, 0.222),
    "BoreDia": (END_CENTER[0] + 0.020, 0.102),
    "ScrewHoleDia": (END_CENTER[0] + 0.062, 0.215),
}
SIDE_KEEP = {
    "HubDia": (HUB_FRONT_X - 0.016, SIDE_CENTER[1]),
    "FlangeDia": (FLANGE_REAR_X + 0.016, SIDE_CENTER[1]),
    "HubLength": ((HUB_FRONT_X + FLANGE_REAR_X) / 2.0, 0.232),
    "FlangeThick": (FLANGE_REAR_X + 0.018, 0.222),
    "OilHoleDia": (FLANGE_REAR_X + 0.030, 0.105),
}
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT_BELOW,
    "OilHoleDia": OIL_HOLE_CALLOUT_BELOW,
}
DIMENSION_CALLOUTS_ABOVE = {"ScrewHoleDia": SCREW_HOLE_CALLOUT_ABOVE}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open disc-hub source", await adapter.open_model(str(SOURCE)))
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
            0: "Transgear Disc Hub Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear disc hub; turned brass hub and flange",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    for view, angle, label in (
        (end, END_VIEW_ANGLE, "face view"),
        (side, SIDE_VIEW_ANGLE, "edge view"),
    ):
        native = _early_bound(view, "IView")
        native.Angle = angle
        if abs(math.remainder(float(native.Angle) - angle, 2.0 * math.pi)) > 1e-9:
            raise RuntimeError(f"failed to rotate the disc-hub {label}")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*end_annotations, *side_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS_BELOW)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    for view, label in ((end, "face"), (side, "edge")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(
                f"failed to add ASME center marks to the hub {label} view"
            )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Disc Hub Manufacturing Drawing",
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

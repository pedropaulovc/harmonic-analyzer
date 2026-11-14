"""Manufacturing sheets for the plain shoulder-screw pivot blocks.

Both sheets print decimal inch (each part's ``drawing_unit``). All sizes
import native model dimensions; no bearing/cartridge sheets survive.
Plan X locations run from the -X (left) edge and Y locations from the -Y
edge through the hidden ``PlanDatumReference`` sketch. Section B-B
shows the floor from the carriage seat, not a competing counterbore-depth
tolerance chain. TL-32's nut face is VIEW D on its own 2:1 sheet, its arrow on
the plan. The layout notes below give sheet millimetres.
"""
from __future__ import annotations
import argparse
import sys
from _drawing_common import DrawingOutputs
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _oblique_block_drawing import draw_block
from _oblique_block_features import (
    COLUMNS, ROWS, bore_fields, carriage_hole_fields, counterbore_fields, general, pivot_tap_fields, seat_fields,
)
from _paths import CAD_ROOT
from _session import run_build
import ch_rocker_arm_tl_oblique_pivot_block_spec as part

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_pivot_block']
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / 'out' / 'sldprt' / f'{PART_STEM}.SLDPRT'
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs['slddrw'],pdf=SPEC.outputs['pdf'],png=SPEC.outputs['png'])

# Feature requirements (cad/docs/pipeline/features-travelers.md): what this
# sheet prints, for the scoped features manifest. Registration does not feed
# the print path.
_PLACES = part.DRAWING_PRECISION_BY_NAME
part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        ("_oblique_block_drawing", "_pivot_stack_text"),
        ("_oblique_block_drawing", "BLOCK_CALLOUTS"),
    )
)

requirement(
    "carriage_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("length", "width", "height"),
    fields={
        **seat_fields(part, "BlockHeight"),
        "width": (general(part, "BlockWidth"), ("BLOCK_WIDTH", "DRAWING_PRECISION_BY_NAME")),
        "width_nominal": (part.BLOCK_WIDTH, ("BLOCK_WIDTH",)),
    },
    precision={"length": _PLACES["BlockLength"], "width": _PLACES["BlockWidth"], "height": _PLACES["BlockHeight"]},
)

requirement(
    "pivot_bore",
    kind="hole",
    faces=(CylinderFace(part.BORE_DIA, contains_x_mm=part.BORE_X, contains_y_mm=part.BORE_Y),),
    requirements=("dia", "depth", "station", "row"),
    fields=bore_fields(part),
    precision={"dia": part.BORE_PLACES, "depth": _PLACES["TopBoreDepth"], "station": _PLACES["PlanBoreX"],
               "row": _PLACES["BlockSideY"]},
)

requirement(
    "pivot_tap",
    kind="hole",
    faces=(CylinderFace(part.PIVOT_TAP_DRILL, contains_x_mm=part.BORE_X, contains_y_mm=part.BORE_Y),),
    requirements=("thread", "dia", "thru"),
    fields=pivot_tap_fields(part),
    precision={"dia": _PLACES["TapDrillDia"]},
)

for _index, (_x, _y) in enumerate(part.BOLT_POINTS, start=1):
    requirement(
        f"carriage_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part.HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "thru", "station", "row"),
        fields=carriage_hole_fields(part, _x, _y),
        precision={"dia": _PLACES["CarriageDrills1Dia"], "station": _PLACES[COLUMNS[1 if _x > 0 else -1]],
                   "row": _PLACES[ROWS[1 if _y > 0 else -1]]},
    )
    requirement(
        f"carriage_counterbore_{_index}",
        kind="counterbore",
        faces=(CylinderFace(part.CBORE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "floor"),
        fields=counterbore_fields(f"carriage_hole_{_index}"),
        precision={"dia": _PLACES["CarriageCounterbores3Dia"], "floor": _PLACES["CboreFloor"]},
    )


async def build(adapter):
    return await draw_block(adapter,SPEC,part)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))

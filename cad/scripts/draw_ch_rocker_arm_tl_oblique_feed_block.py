"""Manufacturing drawing for TL-32, integral feed block; no match drilling."""
from __future__ import annotations
import argparse
import sys
from _drawing_common import read_required_properties
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import drilled_limits, limits
from _session import run_build
from _oblique_block_drawing import draw_block
from _oblique_block_features import (
    COLUMNS, ROWS, bore_fields, carriage_hole_fields, counterbore_fields, general, pivot_tap_fields, printed,
    seat_fields,
)
import ch_rocker_arm_tl_oblique_feed_block_spec as part
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME['ch_rocker_arm_tl_oblique_feed_block']
PART_STEM = SPEC.artifact_stem
# VIEW D's printed text, drawing-side over the saved model's CALLOUTS_*
# (machinist review of the 957501d1 sheet 2). The clearance prints size,
# then process, on one row (rule 26) and names its mate once, by kit number
# in the same-parent short form, never a catalogue code (rule 4). The two
# location dimensions carry their value and band only (rule 7); the mm unit
# is RV-02's.
LEADSCREW_MATE = f"{part.feed_nut.NUMBER.removeprefix(part.NUMBER.rsplit('-TL-', 1)[0] + '-')} LEADSCREW"
# The Ø.375 is a plain hole under DRILLED HOLES at title-block stations (owner
# ruling 2026-11-13): no process word.
CALLOUTS = {
    'NutClearanceDia': {'suffix': ' THRU', 'above': '',
                        'below': f'FOR {LEADSCREW_MATE}\n{part.NUT_WALL_MIN_TEXT}'},
    'NutCentreY': {'above': '', 'below': ''},
    'NutCentreZ': {'above': '', 'below': ''},
}

# Feature requirements (cad/docs/pipeline/features-travelers.md): what these
# sheets print, for the scoped features manifest. Registration does not feed
# the print path. The pivot seat, tap and carriage pattern are TL-22's.
_PLACES = part.DRAWING_PRECISION_BY_NAME
part_metadata(
    precision_sources=(
        "DRAWING_PRECISION_BY_NAME",
        "METRIC_DIMENSIONS",
        ("_oblique_block_drawing", "BLOCK_CALLOUTS"),
        ("_drawing_hole_callout", "add_native_hole_callout"),
        ("ch_rocker_arm_tl_oblique_callouts", "set_callout_lengths_to_three_places"),
    )
)

# Sheet 1 prints no 1.58: the lug's -X face from the -X end, the overall
# across from the +Y side to the lug end and the lug's length from the step.
_PLAN = ("DRAWING_VALUES", "DRAWING_PRECISION_BY_NAME", "PLAN_DATUM_REFERENCE")
requirement(
    "carriage_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("length", "height", "lug_x", "overall_y", "lug_length"),
    fields={
        **seat_fields(part, "SectionBlockHeight"),
        "lug_x": (general(part, "PlanLugX"), _PLAN),
        "lug_x_nominal": (part.PLAN_LUG_X, ("PLAN_LUG_X",)),
        "overall_y": (general(part, "PlanOverallY"), _PLAN),
        "overall_y_nominal": (part.PLAN_OVERALL_Y, ("PLAN_OVERALL_Y",)),
        "lug_length": (general(part, "PlanLugLength"), _PLAN),
        "lug_length_nominal": (part.LUG_LENGTH, ("LUG_LENGTH",)),
    },
    precision={"length": _PLACES["BlockLength"], "height": _PLACES["SectionBlockHeight"],
               "lug_x": _PLACES["PlanLugX"], "overall_y": _PLACES["PlanOverallY"],
               "lug_length": _PLACES["PlanLugLength"]},
)

requirement(
    "pivot_bore",
    kind="hole",
    faces=(CylinderFace(part.pivot.BORE_DIA, contains_x_mm=part.pivot.BORE_X, contains_y_mm=part.pivot.BORE_Y),),
    requirements=("dia", "depth", "station", "row"),
    fields=bore_fields(part),
    precision={"dia": part.pivot.BORE_PLACES, "depth": _PLACES["TopBoreDepth"], "station": _PLACES["PlanBoreX"],
               "row": _PLACES["BlockSideY"]},
)

requirement(
    "pivot_tap",
    kind="hole",
    faces=(CylinderFace(part.pivot.PIVOT_TAP_DRILL, contains_x_mm=part.pivot.BORE_X,
                        contains_y_mm=part.pivot.BORE_Y),),
    requirements=("thread", "dia", "thru"),
    fields=pivot_tap_fields(part),
    precision={"dia": _PLACES["TapDrillDia"]},
)

for _index, (_x, _y) in enumerate(part.pivot.BOLT_POINTS, start=1):
    requirement(
        f"carriage_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part.pivot.HOLE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "thru", "station", "row"),
        fields=carriage_hole_fields(part, _x, _y),
        precision={"dia": _PLACES["CarriageDrills1Dia"], "station": _PLACES[COLUMNS[1 if _x > 0 else -1]],
                   "row": _PLACES[ROWS[1 if _y > 0 else -1]]},
    )
    requirement(
        f"carriage_counterbore_{_index}",
        kind="counterbore",
        faces=(CylinderFace(part.pivot.CBORE_DIA, contains_x_mm=_x, contains_y_mm=_y),),
        requirements=("dia", "floor"),
        fields=counterbore_fields(f"carriage_hole_{_index}"),
        precision={"dia": _PLACES["CarriageCounterbores3Dia"], "floor": _PLACES["CboreFloor"]},
    )

# VIEW D (sheet 2): the leadscrew clearance at title-block stations, Y from
# the lug end at .XXX and Z from the carriage face in exact millimetres (RV-02).
_FROM_NUT_FACE = ([-1.0, 0.0, 0.0], ("__frame__",))
requirement(
    "leadscrew_bore",
    kind="hole",
    faces=(CylinderFace(part.SCREW_CLEARANCE_DIA, contains_y_mm=part.NUT_AXIS_Y, contains_z_mm=part.NUT_AXIS_Z),),
    requirements=("dia", "thru", "row", "height"),
    fields={
        "at": ([part.NUT_FACE_X, part.NUT_AXIS_Y, part.NUT_AXIS_Z], ("NUT_FACE_X", "NUT_AXIS_Y", "NUT_AXIS_Z")),
        "axis": _FROM_NUT_FACE,
        "dia": (
            drilled_limits(part.SCREW_CLEARANCE_DIA, _PLACES["NutClearanceDia"], unit=part.UNIT),
            ("SCREW_CLEARANCE_DIA", ("draw_ch_rocker_arm_tl_oblique_feed_block", "CALLOUTS")),
        ),
        "dia_nominal": (part.SCREW_CLEARANCE_DIA, ("SCREW_CLEARANCE_DIA",)),
        "thru": (True, (("draw_ch_rocker_arm_tl_oblique_feed_block", "CALLOUTS"),)),
        "row": (
            limits(part.DRAWING_VALUES["NutCentreY"], _PLACES["NutCentreY"], unit=part.UNIT),
            ("NUT_AXIS_Y", "LUG_Y0", "DRAWING_PRECISION_BY_NAME"),
        ),
        "row_nominal": (part.DRAWING_VALUES["NutCentreY"], ("NUT_AXIS_Y", "LUG_Y0")),
        "row_from": ("lug_end", ("NUT_PATTERN_PRINTED",)),
        "height": (
            limits(part.NUT_AXIS_Z, _PLACES["NutCentreZ"], (part.NUT_CLEARANCE_BAND_Z, -part.NUT_CLEARANCE_BAND_Z)),
            ("NUT_AXIS_Z", "NUT_CLEARANCE_BAND_Z", "METRIC_DIMENSIONS"),
        ),
        "height_nominal": (part.NUT_AXIS_Z, ("NUT_AXIS_Z",)),
        "height_from": ("carriage_seat", ("NUT_PATTERN_PRINTED",)),
    },
    precision={"dia": _PLACES["NutClearanceDia"], "row": _PLACES["NutCentreY"], "height": _PLACES["NutCentreZ"]},
)

# The four #4-40 taps are transferred through the seated TL-VN-84 nut at
# TL-00 assembly; the native callout prints Ø.089 THRU ALL, every tap within
# VIEW D's 4X 45° ±5° clocking.
_TAP_PLACES = 3  # set_callout_lengths_to_three_places
_TAP_DRILL = printed(part.NUT_TAP_DRILL, _TAP_PLACES)
for _index, (_y, _z) in enumerate(part.NUT_HOLES_YZ, start=1):
    requirement(
        f"nut_tap_{_index}",
        kind="hole",
        faces=(CylinderFace(part.NUT_TAP_DRILL, contains_y_mm=_y, contains_z_mm=_z),),
        requirements=("thread", "dia", "thru", "clock_deg", "note"),
        fields={
            "at": ([part.NUT_FACE_X, _y, _z], ("NUT_FACE_X", "NUT_HOLES_YZ")),
            "axis": _FROM_NUT_FACE,
            "thread": (f"{part.feed_nut.SCREW_THREAD} UNC-2B", ("NUT_TAP_SPEC",)),
            "tap_drill_mm": (part.NUT_TAP_DRILL, ("NUT_TAP_DRILL",)),
            "dia": (drilled_limits(_TAP_DRILL, _TAP_PLACES, unit=part.UNIT), ("NUT_TAP_DRILL", "NUT_TAP_SPEC")),
            "dia_nominal": (_TAP_DRILL, ("NUT_TAP_DRILL",)),
            "thru": (True, ("NUT_TAP_SPEC",)),
            "clock_deg": (
                limits(part.NUT_CLOCK_DEG, _PLACES[part.NUT_CLOCK_DIMENSION],
                       (part.NUT_CLOCK_TOL_DEG, -part.NUT_CLOCK_TOL_DEG)),
                ("NUT_CLOCK_DEG", "NUT_CLOCK_TOL_DEG", "NUT_CLOCK_DIMENSION"),
            ),
            "clock_deg_nominal": (part.NUT_CLOCK_DEG, ("NUT_CLOCK_DEG",)),
            "at_assembly": (True, ("TRANSFER_PROCESS",)),
            "note": (" ".join(part.TRANSFER_PROCESS.split()), ("TRANSFER_PROCESS",)),
        },
        precision={"dia": _TAP_PLACES, "clock_deg": _PLACES[part.NUT_CLOCK_DIMENSION]},
    )

def _read_source_properties(adapter):
    read_required_properties(
        adapter.currentModel, ("Number", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )

async def build(adapter):
    return await draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties,callouts=CALLOUTS)
if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('part',choices=[PART_STEM])
    parser.parse_args()
    sys.exit(run_build(build))

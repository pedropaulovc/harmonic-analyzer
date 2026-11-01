"""Physical contracts for TL-32's integral, drill-to-print nut lug."""
from __future__ import annotations
import math
from pathlib import Path
import _config
import ch_rocker_arm_tl_oblique_feed_block_spec as spec
import ch_rocker_arm_tl_oblique_feed_nut_spec as feed_nut
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _hole_spec import TAP_DRILL_MM
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm

INCH = 25.4


def test_identity_stock_and_common_pivot_interface():
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-32'
    assert metadata['quantity']==spec.QUANTITY==1
    assert spec.UNIT=='in'
    # The metric KP08 axis height (owner ruling 4B) and the M4 carriage
    # engagement (the jig's RV-05) are the declared minors; the shop-made
    # TL-27 nut retired the tap-to-recess wall exception (RV-01).
    metric,engagement=metadata['machinist_exceptions']
    assert (engagement['id'],engagement['kind'])==('RV-03','minor')
    assert pivot.ENGAGEMENT_TEXT in engagement['where']
    assert 'Owner exception confirmed' in engagement['reason']
    assert (metric['id'],metric['kind'])==('RV-02','minor')
    assert 'ruling 4B' in metric['reason']
    assert metric['where']=='VIEW D: the KP08 leadscrew axis 12.400 ±.13 mm'
    assert 'WALL' not in str(metadata)
    assert spec.BLOCK_HEIGHT==pivot.BLOCK_HEIGHT
    assert (spec.BLOCK_X0,spec.BLOCK_X1,spec.BLOCK_WIDTH)==(pivot.BLOCK_X0,pivot.BLOCK_X1,pivot.BLOCK_WIDTH)
    assert math.isclose(spec.LUG_X0-spec.BLOCK_X0,spec.PLAN_LUG_X)
    assert math.isclose(spec.LUG_X1-spec.LUG_X0,spec.LUG_WIDTH)
    assert spec.BLOCK_X0<spec.LUG_X0<spec.LUG_X1<spec.BLOCK_X1
    assert math.isclose(spec.BLOCK_WIDTH/2-spec.LUG_Y0,spec.PLAN_OVERALL_Y)
    assert spec.PLAN_OVERALL_Y<pivot.STOCK_WIDTH
    assert spec.LUG_Y1==-spec.BLOCK_WIDTH/2


def test_nut_face_carries_only_the_screw_clearance_and_two_through_taps():
    assert spec.NUT_FACE_X==spec.LUG_X0
    assert math.isclose(spec.NUT_AXIS_Y,-lead.SCREW_LATERAL)
    assert math.isclose(trammel.CARRIAGE_TOP_Z+spec.NUT_AXIS_Z,lead.SCREW_AXIS_Z)
    assert math.isclose(spec.SCREW_CLEARANCE_DIA,.34*INCH)
    assert spec.SCREW_CLEARANCE_DIA-printed_band_mm(3,unit=spec.UNIT)>lead.SCREW_MAJOR_DIA
    assert set(spec.DRAWING_DIMENSIONS)>={'NutClearanceProfile','NutPatternReference','LugProfile'}
    assert not any('Seat' in feature for feature in spec.DRAWING_DIMENSIONS)
    assert spec.NUT_TAP_SPEC.kind=='tapped' and spec.NUT_TAP_SPEC.size=='#4-40'
    assert spec.NUT_TAP_SPEC.end=='through_all'
    assert spec.NUT_TAP_DRILL==TAP_DRILL_MM['#4-40']


def test_nut_taps_are_the_tl27_pair_on_the_axis_line():
    # Ruling B1: tap 1 .34 from the axis toward the lug end, tap 2 .680 on,
    # both on the axis's Z line, matching the nut's loose holes.
    (y1,z1),(y2,z2)=spec.NUT_HOLES_YZ
    assert z1==z2==spec.NUT_AXIS_Z
    assert math.isclose(spec.NUT_AXIS_Y-y1,.34*INCH)
    assert math.isclose(y2-y1,.680*INCH)
    assert math.isclose(y2-spec.NUT_AXIS_Y,spec.NUT_AXIS_Y-y1)
    assert (spec.NUT_TAP_OFFSET,spec.NUT_TAP_SPACING)==(feed_nut.HOLE_OFFSET,feed_nut.HOLE_SPACING)
    values=spec.DRAWING_VALUES
    assert math.isclose(values['NutTap1Y'],.34*INCH) and math.isclose(values['NutTapSpacing'],.680*INCH)
    assert math.isclose(values['NutCentreY'],spec.NUT_AXIS_Y-spec.LUG_Y0)
    assert spec.DRAWING_DIMENSIONS['NutPatternReference']==('NutCentreZ','NutCentreY','NutTap1Y','NutTapSpacing')
    assert {name:spec.DRAWING_PRECISION_BY_NAME[name] for name in spec.NUT_PATTERN_PRINTED}=={
        'NutCentreZ':3,'NutCentreY':3,'NutTap1Y':2,'NutTapSpacing':3}
    assert spec.CALLOUTS_BELOW['NutTapSpacing']=='MATCHES TL-27 FEED NUT'


def test_loose_nut_holes_absorb_both_printed_pairs():
    # The Ø.144 float (.016) covers the two parts' pair bands; the normal
    # Ø.129 (.008) would not.
    assert math.isclose(spec.FIT_UP_RESIDUAL,math.hypot(.005*INCH,.005*INCH+printed_band_mm(3,unit='mm')))
    assert feed_nut.NORMAL_HOLE_FLOAT<spec.FIT_UP_RESIDUAL<=feed_nut.HOLE_FLOAT


def test_lug_walls_meet_the_target_at_the_printed_worst_case():
    assert min(spec.LUG_WALLS_MM.values())>=WALL_TARGET_MM
    assert round(min(spec.LUG_WALLS_MM.values())/INCH,3)==.097


def test_nut_screws_stop_inside_the_through_tap():
    assert feed_nut.SCREW_TIP_REACH_MAX<spec.LUG_WIDTH


def test_nut_stays_within_the_lug_height_and_overhangs_its_end_by_105():
    assert 0.0<=spec.NUT_Z[0]<spec.NUT_Z[1]<=spec.BLOCK_HEIGHT
    assert spec.NUT_Y[1]<spec.LUG_Y1
    assert round(spec.NUT_OVERHANG/INCH,3)==.105


def test_plan_ordinates_start_on_the_left_edge():
    values=spec.DRAWING_VALUES
    assert math.isclose(values['PlanBoreX'],pivot.BORE_X-pivot.BLOCK_X0)
    for name,(x,_y) in zip(('PlanHole1X','PlanHole2X'),pivot.PLAN_DATUM_HOLES):
        assert math.isclose(values[name],x-pivot.BLOCK_X0)
    assert math.isclose(values['PlanLugX'],spec.LUG_X0-spec.BLOCK_X0)
    assert math.isclose(values['LugWidth'],spec.LUG_X1-spec.LUG_X0)
    assert math.isclose(values['PlanOverallY'],spec.BLOCK_WIDTH/2-spec.LUG_Y0)
    assert not {'BlockEndX','BoreX','LugEndX','LugEndY','LugLength'}&set(spec.DRAWING_PRECISION_BY_NAME)


def test_nut_and_lug_clear_both_end_blocks_at_both_travel_limits():
    assert math.isclose(spec.NUT_REACH_X[0],spec.NUT_FACE_X-feed_nut.REACH)
    for station in trammel.CARRIAGE_TRAVEL:
        lo,hi=(station+v for v in spec.NUT_REACH_X)
        for box in lead.KP08_BOXES.values():
            assert max(box[0]-hi,lo-box[1])>=lead.FEED_GAP
    # The -X gap to the near KP08 at the longest .41 nut (3.57 nominal).
    near=min(gap for (name,_station),gap in spec.FEED_GAPS.items() if name=='KP08 near')
    assert round(near,2)==3.32


def test_feed_entrypoints_use_the_native_shared_geometry_and_not_a_separate_bracket():
    folder=Path(__file__).parent
    builder=(folder/'build_ch_rocker_arm_tl_oblique_feed_block.py').read_text()
    assert 'build_block_model(adapter, spec)' in builder
    shared=(folder/'_oblique_pivot_block_model.py').read_text()
    assert 'NutTaps' in shared and 'NutClearance' in shared and 'LugProfile' in shared
    assert 'NutSeat' not in shared
    assert 'part.NUT_HOLES_YZ' in shared
    drawing=(folder/'draw_ch_rocker_arm_tl_oblique_feed_block.py').read_text()
    assert 'draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties)' in drawing


def test_only_the_kp08_axis_height_prints_exact_millimetres():
    # Owner ruling 4 (2026-11-01): the KP08 vendor line prints exact mm; the
    # TL-27 pair is shop-made, on the inch grid.
    assert spec.METRIC_DIMENSIONS=={('NutPatternReference','NutCentreZ'):(3,printed_band_mm(3,unit='mm'))}

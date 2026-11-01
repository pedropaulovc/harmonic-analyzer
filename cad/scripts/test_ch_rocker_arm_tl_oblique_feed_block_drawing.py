"""Physical contracts for TL-32's integral, drill-to-print nut lug."""
from __future__ import annotations
import math
from pathlib import Path
import _config
import ch_rocker_arm_tl_oblique_feed_block_spec as spec
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead
from _inch_wall_limits import WALL_FLOOR_MM
from _printed_tolerance import printed_band_mm


def test_identity_stock_and_common_pivot_interface():
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-32'
    assert metadata['quantity']==spec.QUANTITY==1
    assert spec.UNIT=='in'
    # The tap-to-recess wall shortfall is the one declared exception, a
    # minor naming the sheet's own WALL row (owner exception pending).
    (wall,)=metadata['machinist_exceptions']
    assert (wall['id'],wall['kind'])==('RV-01','minor')
    assert spec.NUT_SEAT_WALL_TEXT in wall['where']
    assert 'pending confirmation' in wall['reason']
    assert spec.BLOCK_HEIGHT==pivot.BLOCK_HEIGHT
    assert (spec.BLOCK_X0,spec.BLOCK_X1,spec.BLOCK_WIDTH)==(pivot.BLOCK_X0,pivot.BLOCK_X1,pivot.BLOCK_WIDTH)
    assert math.isclose(spec.LUG_X0-spec.BLOCK_X0,spec.PLAN_LUG_X)
    assert math.isclose(spec.LUG_X1-spec.LUG_X0,spec.LUG_WIDTH)
    assert spec.BLOCK_X0<spec.LUG_X0<spec.LUG_X1<spec.BLOCK_X1
    assert math.isclose(spec.BLOCK_WIDTH/2-spec.LUG_Y0,spec.PLAN_OVERALL_Y)
    assert spec.PLAN_OVERALL_Y<pivot.STOCK_WIDTH
    assert spec.LUG_Y1==-spec.BLOCK_WIDTH/2


def test_flipped_nut_face_and_spigot_seat_are_fully_inside_lug():
    assert spec.NUT_FACE_X==spec.LUG_X0
    assert spec.NUT_AXIS_Y==-lead.SCREW_LATERAL
    assert spec.NUT_RECESS_DEPTH-printed_band_mm(2,unit=spec.UNIT)>lead.NUT_BODY_SHORT
    assert spec.SCREW_CLEARANCE_DIA-printed_band_mm(2,unit=spec.UNIT)>lead.SCREW_MAJOR_DIA
    assert math.isclose(spec.NUT_MACHINE_Z,lead.SCREW_AXIS_Z,abs_tol=1e-9)
    # The flange lands wholly on the lug face, between bottom and top.
    assert spec.NUT_AXIS_Z-lead.NUT_FLANGE_DIA/2>0
    assert spec.NUT_AXIS_Z+lead.NUT_FLANGE_DIA/2<spec.BLOCK_HEIGHT
    assert spec.NUT_SEAT_DIA-printed_band_mm(2,unit=spec.UNIT)>lead.NUT_BODY_DIA


def test_nut_taps_are_drilled_to_print_on_the_nut_pcd_at_forty_five_degrees():
    assert len(set(spec.NUT_HOLES_YZ))==4
    for y,z in spec.NUT_HOLES_YZ:
        dy,dz=y-spec.NUT_AXIS_Y,z-spec.NUT_AXIS_Z
        assert math.isclose(math.hypot(dy,dz),lead.NUT_HOLE_PCD/2)
        assert math.isclose(abs(dy),abs(dz))
        assert spec.LUG_Y0<y<spec.LUG_Y1
        assert 0<z<spec.BLOCK_HEIGHT
    assert spec.NUT_TAP_SPEC.size=='#4-40'
    assert spec.NUT_TAP_SPEC.overrides_mm['ThreadDepth']==spec.SCREW_TAP_DEPTH==lead.NUT_SCREW_TAP_DEPTH
    # The drill runs past the thread and stops, point included, inside the lug.
    assert spec.SCREW_TAP_DEPTH<spec.NUT_TAP_DRILL_DEPTH
    assert spec.NUT_TAP_DRILL_DEPTH+spec.NUT_TAP_DRILL/2*.60086<spec.LUG_WIDTH
    # Printed from the nut axis: one Z per column on the +Y row, one Y per row
    # on the -Z column, plus the axis from the lug end and the bottom face.
    assert spec.DRAWING_DIMENSIONS['NutPatternReference']==(
        'NutCentreZ','NutCentreY','NutTap3Z','NutTap4Z','NutTap1Y','NutTap3Y')
    assert math.isclose(spec.DRAWING_VALUES['NutCentreY'],spec.NUT_AXIS_Y-spec.LUG_Y0)


def test_tap_to_recess_wall_shortfall_is_stated_at_its_worst_case():
    assert 0.0<spec.NUT_SEAT_WALL_MIN<spec.NUT_SEAT_WALL_NOMINAL<WALL_FLOOR_MM
    # The stated MIN never overstates the worst case.
    stated=float(spec.NUT_SEAT_WALL_TEXT.split()[1])*25.4
    assert stated<=spec.NUT_SEAT_WALL_MIN
    # No recess that still clears the bought spigot reaches the floor.
    assert spec.NUT_PCD/2-lead.NUT_BODY_DIA/2-spec.NUT_TAP_MAJOR/2<WALL_FLOOR_MM


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
    for station in trammel.CARRIAGE_TRAVEL:
        lo,hi=(station+v for v in spec.NUT_REACH_X)
        for box in lead.KP08_BOXES.values():
            assert max(box[0]-hi,lo-box[1])>=lead.FEED_GAP


def test_feed_entrypoints_use_the_native_shared_geometry_and_not_a_separate_bracket():
    folder=Path(__file__).parent
    builder=(folder/'build_ch_rocker_arm_tl_oblique_feed_block.py').read_text()
    assert 'build_block_model(adapter, spec)' in builder
    shared=(folder/'_oblique_pivot_block_model.py').read_text()
    assert 'NutTaps' in shared and 'NutSeat' in shared and 'LugProfile' in shared
    assert 'part.NUT_HOLES_YZ' in shared
    drawing=(folder/'draw_ch_rocker_arm_tl_oblique_feed_block.py').read_text()
    assert 'draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties)' in drawing


def test_nut_axis_height_and_flange_pattern_print_exact_millimetres():
    # Owner ruling 4 (2026-11-01): the Tr8/KP08 vendor line prints exact mm.
    names = {name for (feature, name) in spec.METRIC_DIMENSIONS}
    assert {feature for (feature, _name) in spec.METRIC_DIMENSIONS} == {'NutPatternReference'}
    assert names == {'NutCentreZ', 'NutTap3Z', 'NutTap4Z', 'NutTap1Y', 'NutTap3Y'}
    assert names < set(spec.NUT_PATTERN_PRINTED)
    assert 'NutCentreY' not in names  # the lug's own (fabricated) closure on the inch grid
    for places, band in spec.METRIC_DIMENSIONS.values():
        assert places == 3 and band == printed_band_mm(3, unit='mm')
    assert spec.NUT_SEAT_WALL_TEXT == 'WALL .036 MIN TO 4-40 TAPS'

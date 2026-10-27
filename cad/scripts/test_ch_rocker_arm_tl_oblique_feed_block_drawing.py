"""Physical contracts for TL-32's integral, drill-to-print nut lug."""
from __future__ import annotations
import ast
import math
from pathlib import Path
import _config
import ch_rocker_arm_tl_oblique_feed_block_spec as spec
import ch_rocker_arm_tl_oblique_pivot_block_spec as pivot
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as lead


def test_identity_stock_and_common_pivot_interface():
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-32'
    assert metadata['quantity']==spec.QUANTITY==1
    assert not metadata.get('machinist_exceptions')
    assert spec.BLOCK_HEIGHT==pivot.BLOCK_HEIGHT==24.3
    assert (spec.BLOCK_X0,spec.BLOCK_X1,spec.BLOCK_WIDTH)==(-42,20,40)
    assert (spec.LUG_X0,spec.LUG_X1,spec.LUG_Y0,spec.LUG_Y1)==(-9.25,9.25,-68,-20)
    assert spec.BLOCK_WIDTH/2-spec.LUG_Y0==88< pivot.STOCK_WIDTH
    assert spec.LUG_Y1==-spec.BLOCK_WIDTH/2


def test_flipped_nut_face_and_spigot_seat_are_fully_inside_lug():
    assert (spec.NUT_FACE_X,spec.NUT_AXIS_Y,spec.NUT_AXIS_Z)==(-9.25,-55,12.4)
    assert (spec.NUT_SEAT_DIA,spec.NUT_SPIGOT_DEPTH)==(10.5,1.5)
    assert spec.SCREW_CLEARANCE_DIA>lead.SCREW_MAJOR_DIA
    assert math.isclose(spec.NUT_MACHINE_Z,lead.SCREW_AXIS_Z,abs_tol=1e-9)
    assert math.isclose(spec.NUT_AXIS_Z-lead.NUT_FLANGE_DIA/2,1.4)
    assert math.isclose(spec.NUT_AXIS_Z+lead.NUT_FLANGE_DIA/2,23.4)
    assert spec.NUT_SEAT_DIA>lead.NUT_BODY_DIA


def test_nut_taps_are_drilled_to_print_on_sixteen_pcd_at_forty_five_degrees():
    assert len(set(spec.NUT_HOLES_YZ))==4
    for y,z in spec.NUT_HOLES_YZ:
        dy,dz=y-spec.NUT_AXIS_Y,z-spec.NUT_AXIS_Z
        assert math.isclose(math.hypot(dy,dz),8)
        assert math.isclose(abs(dy),abs(dz))
        assert spec.LUG_Y0<y<spec.LUG_Y1
        assert 0<z<spec.BLOCK_HEIGHT
    assert spec.NUT_TAP_SPEC.size=='#4-40'
    assert spec.NUT_TAP_SPEC.overrides_mm['ThreadDepth']==spec.SCREW_TAP_DEPTH==10
    assert spec.NUT_TAP_DRILL_DEPTH==12
    assert spec.NUT_TAP_DRILL_DEPTH+spec.NUT_TAP_DRILL/2*.60086<spec.LUG_WIDTH
    # Printed from the nut axis: one Z per column on the +Y row, one Y per row
    # on the -Z column, plus the axis from the lug end and the bottom face.
    assert spec.DRAWING_DIMENSIONS['NutPatternReference']==(
        'NutCentreZ','NutCentreY','NutTap3Z','NutTap4Z','NutTap1Y','NutTap3Y')
    assert spec.DRAWING_VALUES['NutCentreY']==spec.NUT_AXIS_Y-spec.LUG_Y0==13


def test_tap_to_recess_wall_shortfall_is_stated_at_its_worst_case():
    assert math.isclose(spec.NUT_SEAT_WALL_NOMINAL,1.3275)
    assert math.isclose(spec.NUT_SEAT_WALL_MIN,8-math.hypot(.13,.13)-(10.5+.51)/2-2.845/2)
    assert spec.NUT_SEAT_WALL_TEXT=='WALL 0.88 MIN TO 4-40 TAPS'
    assert spec.NUT_SEAT_WALL_TEXT in spec.CALLOUTS_BELOW['NutSeatDia']
    # No recess that still clears the bought spigot reaches the 1.5 floor.
    assert spec.NUT_PCD/2-lead.NUT_BODY_DIA/2-spec.NUT_TAP_MAJOR/2<1.5


def test_plan_ordinates_start_on_the_left_edge():
    values=spec.DRAWING_VALUES
    assert (values['PlanBoreX'],values['PlanHole1X'],values['PlanHole2X'])==(10,29,55)
    assert (values['PlanLugX'],values['LugWidth'],values['PlanOverallY'])==(32.75,18.5,88)
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
    tree=ast.parse(drawing)
    assert not any(isinstance(n,ast.Name) and n.id=='MACHINIST_REVIEW' for n in ast.walk(tree))
    assert 'draw_block(adapter,SPEC,part,read_source_properties=_read_source_properties)' in drawing

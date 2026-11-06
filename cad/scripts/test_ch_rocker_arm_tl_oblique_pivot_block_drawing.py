"""Offline physical contracts for the simplified TL-22 shoulder-screw block."""
from __future__ import annotations
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import pytest
import _config
import ch_rocker_arm_tl_oblique_pivot_block_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import ch_rocker_arm_tl_vn_oblique_pivot_screw_spec as pivot_screw
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm

INCH = 25.4


def test_rectangular_rail_two_block_and_new_stock():
    assert spec.UNIT == 'in'
    assert math.isclose(spec.BLOCK_X1-spec.BLOCK_X0,spec.BLOCK_LENGTH)
    assert math.isclose(spec.BORE_X-spec.BLOCK_X0,spec.PLAN_BORE_X)
    assert spec.BLOCK_HEIGHT == trammel.PIVOT_BLOCK_HEIGHT
    assert spec.BLOCK_HEIGHT<spec.STOCK_THICKNESS and spec.BLOCK_WIDTH<spec.STOCK_WIDTH
    metadata=_config.parts(spec.PART_NAME)
    assert metadata['number']=='MHA-CH-06-TL-22'
    assert metadata['quantity']==spec.QUANTITY==1
    # Every counterbore wall meets the inch target; the one exception is the
    # M4 engagement (test_engagement_shortfall_is_the_declared_minor).
    assert [row['id'] for row in metadata['machinist_exceptions']]==['RV-01']


def test_pivot_shoulder_bottoms_with_full_form_thread_engagement():
    assert (spec.BORE_X,spec.BORE_Y)==(trammel.PIN_OFFSET,0)
    assert spec.PIVOT_TAP==pivot_screw.THREAD
    assert spec.PIVOT_TAP_DRILL<spec.BORE_LIMITS[0]
    assert spec.PIVOT_THREAD_LENGTH==spec.BLOCK_HEIGHT-spec.BORE_DEPTH
    # Full-form thread: the shop-cut thread less 1.5 pitches, 1.5D at its worst.
    assert math.isclose(spec.PIVOT_THREAD_ENGAGEMENT,
                        pivot_screw.CUT_THREAD_LENGTH-1.5*pivot_screw.THREAD_PITCH)
    assert spec.PIVOT_THREAD_ENGAGEMENT_MIN>=1.5*pivot_screw.THREAD_DIA
    # The cut tip stays inside the block bottom by .011 at every band.
    assert spec.PIVOT_TIP_CLEARANCE_MIN>=0.011*INCH-1e-9
    assert spec.PIVOT_TIP_CLEARANCE>spec.PIVOT_TIP_CLEARANCE_MIN
    # The shoulder slides in the reamed seat: clearance at every band.
    assert 0.0<spec.PIVOT_LOCATING_CLEARANCE_MIN<spec.PIVOT_LOCATING_CLEARANCE_MAX
    assert spec.PIVOT_LOCATING_CLEARANCE_MAX<=0.0025*INCH+1e-9


def test_carriage_screws_cut_to_fit_from_the_lowered_floor():
    assert set(spec.BOLT_POINTS)=={(-13,-13),(-13,13),(13,-13),(13,13)}
    assert tuple(2*x for x in (spec.BOLT_X,spec.BOLT_Y))==trammel.CARRIAGE_BOLT_SPAN
    assert 4.0<spec.HOLE_DIA<spec.CBORE_DIA
    assert math.isclose(spec.CBORE_DEPTH,spec.BLOCK_HEIGHT-spec.CBORE_FLOOR)
    # Owner ruling 2026-11-01 (option A): floor .570, each M4 x 20 cut to its
    # floor plus .189 (±.005 cut, .001 reading): the tip reaches .183 MIN,
    # .162 MIN (1.03D) of it full thread past the 0.75P tip chamfer, never
    # bottoming in the M4 x 5, and every cut fits the shortest bought screw.
    assert math.isclose(spec.CBORE_FLOOR,.570*INCH)
    assert math.isclose(spec.SCREW_REACH,.189*INCH)
    assert math.isclose(spec.SCREW_CUT_LENGTH,(.570+.189)*INCH)
    assert math.isclose(spec.REACH_MIN,.183*INCH)
    assert math.isclose(spec.ENGAGEMENT_MIN,spec.REACH_MIN-.75*.7)
    assert spec.ENGAGEMENT_TEXT=='.162'
    assert spec.ENGAGEMENT_DIAMETERS=='1.03D'
    assert spec.REACH_MAX<=spec.CARRIAGE_THREAD_DEPTH-.045+1e-9
    assert spec.SCREW_CUT_LENGTH_MAX<spec.SCREW_LENGTH-spec.SCREW_LENGTH_TOL
    assert spec.CALLOUTS_BELOW['CboreFloor']=='FLOOR FOR M4 X 20 CUT\nENGAGES .162 MIN (1.03D)'
    assert spec.DRAWING_PRECISION[spec.CBORE_FLOOR_REFERENCE]['CboreFloor']==3
    assert spec.CBORE_FLOOR-printed_band_mm(3,unit=spec.UNIT)>0


def test_no_bearing_web_wing_cap_or_side_features_survive():
    assert min(spec.WALLS_MM.values())>=WALL_TARGET_MM
    for name in ('WING_WIDTH','SHOULDER_HOLE_DIA','CAP_TAP_POINTS','CAP_REGISTER_POINTS',
                 'SIDE_SCREW_HOLES','SEAT_POSITION_DIA','BEARING_OD'):
        assert not hasattr(spec,name)
    assert set(spec.CALLOUTS_BELOW)<=set(spec.DRAWING_PRECISION_BY_NAME)


def test_outline_bands_keep_the_counterbore_walls_at_target():
    places=spec.DRAWING_PRECISION_BY_NAME
    assert places['BlockLength']==places['BlockWidth']
    assert spec.CBORE_END_WALL_MIN>=WALL_TARGET_MM
    assert spec.CBORE_SIDE_WALL_MIN>=WALL_TARGET_MM
    assert spec.BORE_X == spec.BORE_Y == trammel.PIN_OFFSET == 0.0
    assert math.isclose(spec.BLOCK_LENGTH / INCH, 1.64)
    assert math.isclose(spec.PLAN_BORE_X / INCH, .82)
    assert spec.BLOCK_X0 == -spec.BLOCK_X1
    assert min(spec.CBORE_NEAR_END_WALL_MIN, spec.BORE_CBORE_WEB_MIN,
               spec.SHIM_CBORE_GAP_MIN, spec.BORE_END_WALL_MIN) >= WALL_TARGET_MM


def test_native_builder_owns_real_solids_dimensions_and_final_volume():
    source=Path(__file__).with_name('_oblique_pivot_block_model.py').read_text()
    tree=ast.parse(source)
    literals={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
    assert {'Block','TopBore','PivotTap','CarriageDrills','CarriageCounterbores'}<=literals
    assert 'finished block' in literals
    assert 'BoreDia' in literals
    assert 'TopBoreDepth' in literals
    assert 'SeatFillets' not in literals
    assert 'BottomBore' not in literals
    assert "require_block_geometry(adapter, part)" in source
    assert "geometry.parameters" in source and "dimension.SystemValue" in source


def test_drawing_has_only_pivot_and_carriage_sections_under_enforcement():
    source=Path(__file__).with_name('draw_ch_rocker_arm_tl_oblique_pivot_block.py').read_text()
    tree=ast.parse(source)
    # Machinist review ENFORCE (#1974) carries over to the simplified block.
    assert any(isinstance(n,ast.Assign) and [t.id for t in n.targets if isinstance(t,ast.Name)]==['MACHINIST_REVIEW'] and ast.unparse(n.value)=='MachinistReviewMode.ENFORCE' for n in tree.body)
    # The sheet's views come from the builder it shares with TL-32.
    builder=Path(__file__).with_name('_oblique_block_drawing.py').read_text()
    assert 'carriage counterbore floor' in builder
    assert 'pivot shoulder seat' in builder
    assert 'add_feature_control_frame' not in builder
    assert 'create_section_view' in builder


def test_block_height_prints_on_a_right_view_level_with_the_plan():
    import _oblique_block_drawing as drawing
    assert drawing.RIGHT_XY[1]==drawing.PLAN_XY[1]
    assert set(drawing.RIGHT_KEEP)=={'BlockHeight'}
    assert 'BlockHeight' in spec.DRAWING_DIMENSIONS['Block']
    assert 'BlockHeight' not in drawing.SIDE_KEEP


def test_engagement_shortfall_is_the_declared_minor():
    (engagement,)=_config.parts(spec.PART_NAME)['machinist_exceptions']
    assert (engagement['id'],engagement['kind'])==('RV-01','minor')
    assert spec.ENGAGEMENT_TEXT in engagement['where']
    assert 'Owner exception confirmed' in engagement['reason']


@pytest.mark.parametrize("feed", (False, True))
@pytest.mark.parametrize("fault", (None, "missing", "axis", "diameter", "dimension", "extra_body"))
def test_native_block_readback_refuses_moved_or_missing_geometry(monkeypatch, feed, fault):
    import _oblique_pivot_block_model as model
    import _drawing_precision
    import _gtol_face_read
    from _gtol_face import SURFACE_CYLINDER
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed_spec

    part = feed_spec if feed else spec
    cylinders = []

    def cylinder(axis, centre, diameter):
        direction = [0.0, 0.0, 0.0]
        direction[axis] = 1.0
        cylinders.append(SimpleNamespace(
            identity=SURFACE_CYLINDER,
            parameters=tuple(v / 1000.0 for v in centre) + tuple(direction) + (diameter / 2000.0,),
        ))

    cylinder(2, (0.0, 0.0, 0.0), spec.BORE_DIA)
    cylinder(2, (0.0, 0.0, 0.0), spec.PIVOT_TAP_DRILL)
    for x, y in spec.BOLT_POINTS:
        for diameter in (spec.HOLE_DIA, spec.CBORE_DIA):
            cylinder(2, (x, y, 0.0), diameter)
    if feed:
        cylinder(0, (0.0, part.NUT_AXIS_Y, part.NUT_AXIS_Z), part.SCREW_CLEARANCE_DIA)
        for y, z in part.NUT_HOLES_YZ:
            cylinder(0, (0.0, y, z), part.NUT_TAP_DRILL)
    if fault == "missing":
        cylinders.pop(0)
    if fault in ("axis", "diameter"):
        values = list(cylinders[0].parameters)
        values[0 if fault == "axis" else 6] += 0.001
        cylinders[0].parameters = tuple(values)
    body = SimpleNamespace(GetFaces=lambda: cylinders)
    document = SimpleNamespace(GetBodies2=lambda kind, visible: [body] * (2 if fault == "extra_body" else 1))
    adapter = SimpleNamespace(currentModel=document)
    monkeypatch.setattr(model, "_early_bound", lambda obj, kind: obj)
    monkeypatch.setattr(_gtol_face_read, "face_geometry", lambda face, **kwargs: face)

    def dimensions(adapter, feature, names):
        return {
            name: (None, SimpleNamespace(
                SystemValue=(part.DRAWING_VALUES[name] + (1.0 if fault == "dimension" else 0.0)) / 1000.0
            ))
            for name in names
        }

    monkeypatch.setattr(_drawing_precision, "_named_dimensions", dimensions)
    if fault is None:
        model.require_block_geometry(adapter, part)
    else:
        with pytest.raises(RuntimeError):
            model.require_block_geometry(adapter, part)

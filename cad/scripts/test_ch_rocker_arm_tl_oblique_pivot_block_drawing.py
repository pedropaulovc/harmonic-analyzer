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


@pytest.mark.parametrize("feed,fault", [
    (feed, fault)
    for feed in (False, True)
    for fault in (None, "missing", "axis", "diameter", "dimension", "extra_body")
] + [
    (True, fault)
    for fault in ("nut_missing", "nut_mirrored", "nut_rounded_body",
                  "nut_wrong_drill", "nut_unreadable_drill", "nut_no_definition")
])
def test_native_block_readback_refuses_moved_or_missing_geometry(monkeypatch, feed, fault):
    import _oblique_pivot_block_model as model
    import _drawing_precision
    import _gtol_face_read
    import _feature_tree
    from _gtol_face import SURFACE_CYLINDER, SURFACE_PLANE
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed_spec

    part = feed_spec if feed else spec
    cylinders = []
    # A through-tap Wizard can retain the exact inch drill conversion while
    # TAP_DRILL_MM stores three decimal mm. This is a binding fixture, not
    # a claim that worker10's unrecorded physical radius has been measured.
    native_drill_mm = .089 * INCH
    definition = SimpleNamespace(ThruTapDrillDiameter=native_drill_mm / 1000.0)
    if fault == "nut_wrong_drill":
        definition.ThruTapDrillDiameter = .0023
    if fault == "nut_unreadable_drill":
        definition.ThruTapDrillDiameter = float("nan")
    feature = SimpleNamespace(
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: None if fault == "nut_no_definition" else definition,
    )
    monkeypatch.setattr(_feature_tree, "_feature_by_name", lambda adapter, name: feature)

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
            cylinder(0, (0.0, y, z), native_drill_mm)
        # The merged +X end (owner ruling 2026-11-07), read by vertices.
        corners = [SimpleNamespace(GetPoint=lambda p=p: [v / 1000.0 for v in p])
                   for p in ((part.BLOCK_X1, part.LUG_Y0, 0.0),
                             (part.BLOCK_X1, part.BLOCK_WIDTH / 2, part.BLOCK_HEIGHT))]
        edge = SimpleNamespace(GetStartVertex=lambda: corners[0], GetEndVertex=lambda: corners[1])
        cylinders.append(SimpleNamespace(
            identity=SURFACE_PLANE, outward_normal=(1.0, 0.0, 0.0),
            parameters=(1.0, 0.0, 0.0, part.BLOCK_X1 / 1000.0, 0.0, 0.0), GetEdges=lambda: [edge],
        ))
    if fault == "missing":
        cylinders.pop(0)
    if fault in ("axis", "diameter"):
        values = list(cylinders[0].parameters)
        values[0 if fault == "axis" else 6] += 0.001
        cylinders[0].parameters = tuple(values)
    if fault == "nut_missing":
        cylinders.pop(11)
    if fault in ("nut_mirrored", "nut_rounded_body"):
        values = list(cylinders[11].parameters)
        if fault == "nut_mirrored":
            values[1] = -values[1]
        else:
            # Even the 0.0004 mm difference must fail if the solid disagrees
            # with its exact committed Wizard definition.
            values[6] = part.NUT_TAP_DRILL / 2000.0
        cylinders[11].parameters = tuple(values)
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
        with pytest.raises(RuntimeError) as error:
            model.require_block_geometry(adapter, part)
        if fault in ("nut_missing", "nut_mirrored", "nut_rounded_body"):
            assert "observed solid cylinders" in str(error.value)
            assert "diameter_mm" in str(error.value) and "origin_mm" in str(error.value)


@pytest.mark.parametrize("raw_result", [False, True])
def test_committed_nut_drill_binds_dispatch_before_property_read(monkeypatch, raw_result):
    import _com
    import _feature_tree
    import _oblique_pivot_block_model as model
    import ch_rocker_arm_tl_oblique_feed_block_spec as feed_spec

    # A bare PyIDispatch has InvokeTypes but no _oleobj_ or named property.
    raw = SimpleNamespace(InvokeTypes=lambda *args: pytest.fail("unbound dispatch access"))
    wrapper = SimpleNamespace(_oleobj_=object(), ThruTapDrillDiameter=.089 * INCH / 1000.0)
    bindings = []

    def bind(obj, interface):
        bindings.append((obj._oleobj_, interface))
        assert obj._oleobj_ is raw
        return wrapper

    monkeypatch.setattr(_com, "_early_bound", bind)
    feature = SimpleNamespace(GetTypeName2=lambda: "HoleWzd",
                              GetDefinition=lambda: raw if raw_result else wrapper)
    monkeypatch.setattr(_feature_tree, "_feature_by_name", lambda adapter, name: feature)
    assert model._native_nut_tap_diameter(None, feed_spec) == pytest.approx(.089 * INCH)
    assert bindings == ([(raw, "IWizardHoleFeatureData2")] if raw_result else [])


@pytest.mark.parametrize("feed", [False, True])
def test_x_dimension_lanes_leave_the_cutting_line_and_narrow_witness_span(feed):
    import _oblique_block_drawing as drawing

    keep = drawing.FEED_PLAN_KEEP if feed else drawing.PLAN_KEEP
    # Measured font rectangles from the retained 0c3ed359 pivot PDF, not
    # synthetic native readbacks. These protect the authored paper lanes;
    # the fresh native drawing/layout/machinist gates remain authoritative.
    cut_x = (drawing.PLAN_XY[0] * 1000) + spec.CBORE_SECTION_X
    bore_x = drawing.PLAN_XY[0] * 1000
    bore_text_x = keep["PlanBoreX"][0] * 1000
    assert bore_text_x - 4.5257 - cut_x - .175 >= 1.5
    assert bore_x - .065 - (bore_text_x + 4.5257) >= 1.5
    narrow_text_x = keep["PlanHole1X"][0] * 1000
    assert narrow_text_x - 5.8188 - (cut_x + 6.35) - .065 >= 1.5
    far_text_x = keep["PlanHole2X"][0] * 1000
    assert far_text_x - 7.1118 - cut_x - .175 >= 1.5
    tiers = [keep[name][1] * 1000 for name in ("PlanBoreX", "PlanHole1X", "PlanHole2X")]
    assert all(upper - 3.1975 - (lower + 3.1818) >= 1.5
               for lower, upper in zip(tiers, tiers[1:]))
    assert keep["BlockLength"][1] * 1000 - .065 - (tiers[-1] + 3.1818) >= 1.5


def test_b_letters_clear_upper_witnesses_border_and_lower_drill_leader():
    import _oblique_block_drawing as drawing

    # Translate the retained PDF's normal-size B rectangles with their
    # cutting-line endpoints. No font ladder or manufactured result is used.
    upper_move = drawing.FLOOR_CUT_TOP_Y * 1000 - 229.066
    upper_bottom, upper_top = 226.3757 + upper_move, 234.5777 + upper_move
    highest_witness = drawing.PLAN_KEEP["BlockLength"][1] * 1000 + 1.0
    assert upper_bottom - highest_witness - .065 >= 1.5
    assert 266.7 - upper_top >= 2.0
    lower_end = drawing.PLAN_XY[1] * 1000 - spec.BLOCK_WIDTH / 2 - drawing.FLOOR_CUT_BOTTOM_OVERRUN_MM
    lower_top = 186.4457 + lower_end - 180.934
    # Actual diagonal leader: underline elbow to the lower-left drill rim.
    x0, y0, x1, y1 = 136.2924, 159.6389, 155.7679, 190.0745
    leader_at_letter_left = y0 + (148.2252 - x0) * (y1 - y0) / (x1 - x0)
    assert leader_at_letter_left - lower_top - .065 >= 3.0
    # The lower arrow shaft/head is also below that leader, not just B.
    leader_at_arrow_left = y0 + (153.5 - x0) * (y1 - y0) / (x1 - x0)
    assert leader_at_arrow_left - (lower_end + 1.25) - .175 >= 3.0


def test_block_length_reason_rides_its_value_row_clear_of_the_dimension():
    """TL-22 printed the same top tier as TL-32 (c40296ac PDFs: the 1.64 over
    SETS COUNTERBORE END WALL centred at (240, 258.5) mm, its underline on
    the y253.5 dimension line), so its leader ran along the line too. Both
    sheets now print the reason on the value's row, over the span. Text
    metrics come from those PDFs: 2.74 mm a character, a 6.38 mm row box,
    and a centre-anchored block."""
    import _oblique_block_drawing as drawing

    reason = spec.CALLOUTS_BELOW['BlockLength']
    assert reason == 'SETS COUNTERBORE END WALL' and 'BlockLength' not in spec.CALLOUTS_SUFFIX
    char_mm, row_mm = (274.22 - 205.78) / len(reason), 258.90 - 252.52
    width = (len('1.64 ') + len(reason)) * char_mm
    x, y = (value * 1000 for value in drawing.BLOCK_LENGTH_TEXT_XY)
    left, right, bottom, top = x - width / 2, x + width / 2, y - row_mm / 2, y + row_mm / 2
    span_left = drawing.PLAN_XY[0] * 1000 - spec.BLOCK_LENGTH / 2
    span_right = span_left + spec.BLOCK_LENGTH
    cut_x = drawing.PLAN_XY[0] * 1000 + spec.CBORE_SECTION_X
    line_y = drawing.PLAN_KEEP['BlockLength'][1] * 1000
    assert left - cut_x >= 4.0
    assert span_left < left < (span_left + span_right) / 2 < right
    assert 266.7 - top >= 2.0
    # The underline (~0.7 under the box) clears the extension lines' 1 mm
    # overrun by 3 mm; the old block's underline was under it.
    assert bottom + .7 - (line_y + 1.0) >= 3.0
    assert 258.5 - (264.46 - 252.52) / 2 + .7 - (line_y + 1.0) < 0.0
    source = (Path(drawing.__file__)).read_text(encoding='utf-8')
    body = source[source.index('def draw_block'):]
    call = "\n    _inline_below_callout(adapter, plan_annotations, 'BlockLength', contract.CALLOUTS_BELOW['BlockLength'])\n"
    assert call in body and 'if is_feed:' + call not in body


@pytest.mark.parametrize('fault', (
    None, 'tap_outer', 'ream_inner', 'missing_inner', 'wrong_depth', 'wrong_radius',
    'wrong_axis', 'nan_arrow', 'short_arrow', 'zero_arrows', 'two_arrows',
    'source_name', 'source_identity', 'value', 'thread', 'definition', 'dangling',
    'body_outside', 'body_wings_outside', 'body_zero_width', 'body_zero_direction',
    'body_hidden', 'side_drift', 'ream_side', 'text_position',
))
def test_pivot_inside_arrow_proves_body_and_tip_without_changing_source(monkeypatch, fault):
    import _oblique_block_drawing as drawing
    from _drawing_edges import ViewEdge, ViewEdges

    origin = drawing.PLAN_XY
    mouth_z = spec.BLOCK_HEIGHT - spec.BORE_DEPTH
    names = ('TapDrillDia', 'BoreDia')
    radii = (spec.PIVOT_TAP_DRILL / 2, spec.BORE_DIA / 2)
    state = {}
    circles = []
    displays = {}
    for name, feature, radius, z in zip(
        names, ('PivotTapProfile', 'TopBoreProfile'), radii, (mouth_z, spec.BLOCK_HEIGHT)
    ):
        circles.append(ViewEdge(
            edge=object(), line=None, vertices=None,
            circle=(spec.BORE_X, spec.BORE_Y, z, 0.0, 0.0, 1.0, radius),
        ))
        row = state[name] = {
            'dimension': SimpleNamespace(FullName=f'{name}@{feature}@block.Part', SystemValue=radius / 500),
            'text': ('<MOD-DIAM>', '', spec.CALLOUTS_ABOVE[name], spec.CALLOUTS_BELOW[name],
                     '<MOD-DIAM>', '', spec.CALLOUTS_ABOVE[name], spec.CALLOUTS_BELOW[name]),
            # Correct inner tip, but outside body spans the outer ring.
            'arrow': (origin[0] - radius / 1000, origin[1], 0.0, -1.0, 0.0, 0.0,
                      .002, .001, 0.0, 0.0, 0.0, 1.0),
            'position': (*drawing.PLAN_KEEP[name], 0.0), 'count': 1, 'dangling': False,
        }
        annotation = SimpleNamespace(IsDangling=lambda row=row: row['dangling'],
                                     GetPosition=lambda row=row: row['position'])
        data = SimpleNamespace(GetArrowHeadCount=lambda row=row: row['count'],
                               GetArrowHeadAtIndex2=lambda index, row=row: row['arrow'])
        displays[name] = SimpleNamespace(
            ArrowSide=1,
            GetDimension2=lambda index, row=row: row['dimension'],
            GetText=lambda which, row=row: row['text'][which - 1],
            GetAnnotation=lambda annotation=annotation: annotation,
            GetDisplayData=lambda data=data: data,
        )
    # Same drill's opposite rim is identical in plan; keep the axial test.
    circles.insert(0, ViewEdge(
        edge=object(), line=None, vertices=None,
        circle=(spec.BORE_X, spec.BORE_Y, 0.0, 0.0, 0.0, 1.0, radii[0]),
    ))
    monkeypatch.setattr(drawing, '_early_bound', lambda obj, interface: obj)
    monkeypatch.setattr(drawing, '_displays',
                        lambda adapter, annotations, names: {name: displays[name] for name in names})
    monkeypatch.setattr(drawing, 'scan_view_edges',
                        lambda *args, **kwargs: ViewEdges('fixture', tuple(circles)))
    monkeypatch.setattr(drawing, '_project',
                        lambda adapter, view, point, label: (origin[0] + point[0] / 1000,
                                                           origin[1] + point[1] / 1000))
    rebuilds = []

    def rebuild(adapter, *, label):
        rebuilds.append(label)
        assert displays['TapDrillDia'].ArrowSide == drawing._ARROWS_INSIDE
        assert displays['BoreDia'].ArrowSide == 1
        arrow = state['TapDrillDia']['arrow']
        state['TapDrillDia']['arrow'] = (*arrow[:3], 1.0, *arrow[4:])

    monkeypatch.setattr(drawing, 'rebuild_drawing', rebuild)
    reports = []
    monkeypatch.setattr(drawing._telemetry, 'info', lambda message, **kwargs: reports.append(kwargs))
    adapter = SimpleNamespace(swApp=SimpleNamespace(IsSame=lambda a, b: int(a is b)))
    old_triangle = drawing.arrowhead_segments(state['TapDrillDia']['arrow'])
    assert max(math.dist((edge.x0, edge.y0), origin) for edge in old_triangle) > radii[1] / 1000
    settled = drawing._place_pivot_tap_arrow_inside(adapter, object(), [], spec)
    assert rebuilds == ['arrow side 0']
    assert reports[-1]['rims']['TapDrillDia']['mouth_circle_mm'][2] == mouth_z
    assert reports[-1]['rims']['BoreDia']['mouth_circle_mm'][2] == spec.BLOCK_HEIGHT
    tap = state['TapDrillDia']
    if fault in ('tap_outer', 'ream_inner'):
        name, radius = ('TapDrillDia', radii[1]) if fault == 'tap_outer' else ('BoreDia', radii[0])
        state[name]['arrow'] = (origin[0] - radius / 1000, *state[name]['arrow'][1:])
    elif fault == 'missing_inner':
        circles.pop(1)
    elif fault in ('wrong_depth', 'wrong_radius', 'wrong_axis'):
        circle = list(circles[1].circle)
        if fault == 'wrong_axis':
            circle[3:6] = (1.0, 0.0, 0.0)
        else:
            circle[2 if fault == 'wrong_depth' else 6] += .1
        circles[1] = ViewEdge(edge=object(), line=None, vertices=None, circle=tuple(circle))
    elif fault == 'nan_arrow':
        tap['arrow'] = (float('nan'), *tap['arrow'][1:])
    elif fault == 'short_arrow':
        tap['arrow'] = tap['arrow'][:6]
    elif fault in ('zero_arrows', 'two_arrows'):
        tap['count'] = 0 if fault == 'zero_arrows' else 2
    elif fault == 'source_name':
        tap['dimension'].FullName = 'TapDrillDia@TopBoreProfile@block.Part'
    elif fault == 'source_identity':
        tap['dimension'] = SimpleNamespace(**vars(tap['dimension']))
    elif fault == 'value':
        tap['dimension'].SystemValue = spec.BORE_DIA / 1000
    elif fault == 'thread':
        tap['text'] = (*tap['text'][:3], 'WRONG THREAD', *tap['text'][4:])
    elif fault == 'definition':
        tap['text'] = (*tap['text'][:4], 'DIAMETER', *tap['text'][5:])
    elif fault == 'dangling':
        tap['dangling'] = True
    elif fault in ('body_outside', 'body_wings_outside', 'body_zero_width', 'body_zero_direction', 'body_hidden'):
        arrow = list(tap['arrow'])
        if fault == 'body_outside':
            arrow[3] = -1.0
        elif fault == 'body_wings_outside':
            arrow[7] = .01
        elif fault == 'body_zero_width':
            arrow[6] = 0.0
        elif fault == 'body_hidden':
            arrow[8] = 10.0  # swNO_ARROWHEAD must not certify a synthetic triangle
        else:
            arrow[3:6] = (0.0, 0.0, 0.0)
        tap['arrow'] = tuple(arrow)
    elif fault == 'side_drift':
        displays['TapDrillDia'].ArrowSide = 1
    elif fault == 'ream_side':
        displays['BoreDia'].ArrowSide = 0
    elif fault == 'text_position':
        tap['position'] = (tap['position'][0] + .001, *tap['position'][1:])
    if fault is None:
        settled()
        assert len(reports) == 2 and rebuilds == ['arrow side 0']
    else:
        with pytest.raises(RuntimeError):
            settled()


def test_inside_arrow_setter_refuses_ignored_native_put(monkeypatch):
    import _oblique_block_drawing as drawing

    class RefusedDisplay:
        @property
        def ArrowSide(self):
            return 1

        @ArrowSide.setter
        def ArrowSide(self, side):
            assert side == drawing._ARROWS_INSIDE

    monkeypatch.setattr(drawing, '_displays', lambda *args: {'TapDrillDia': RefusedDisplay()})
    monkeypatch.setattr(drawing, 'rebuild_drawing', lambda *args, **kwargs: pytest.fail('put was ignored'))
    with pytest.raises(RuntimeError, match='arrows did not move'):
        drawing._set_arrow_side(None, [], ('TapDrillDia',), drawing._ARROWS_INSIDE)


@pytest.mark.parametrize('feed', (False, True))
def test_inside_tap_arrow_and_settled_proof_are_pivot_only(feed):
    source = Path(__file__).with_name('_oblique_block_drawing.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    build = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)
                 and node.name == 'draw_block')
    initial = next(node for node in build.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'settled_checks'
                           for target in node.targets))
    conditional = next(node for node in build.body if isinstance(node, ast.If)
                       and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                               and child.func.id == '_place_pivot_tap_arrow_inside'
                               for child in ast.walk(node)))
    calls = []
    proof = object()

    def place(*args):
        calls.append(args)
        return proof

    env = dict(is_feed=feed, adapter=object(), plan=object(), plan_annotations=[],
               contract=object(), _place_pivot_tap_arrow_inside=place)
    # Execute only the real routing statements: feed must not call the
    # placement helper or inject a pivot-only proof into its finalizer.
    exec(compile(ast.Module(body=[initial, conditional], type_ignores=[]), '<pivot-routing>', 'exec'), env)
    assert len(calls) == (0 if feed else 1)
    assert env['settled_checks'] == (() if feed else (proof,))
    finalizer = next(node for node in ast.walk(build) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'finalize_drawing')
    assert ast.unparse(next(keyword.value for keyword in finalizer.keywords
                           if keyword.arg == 'settled_checks')) == 'settled_checks'

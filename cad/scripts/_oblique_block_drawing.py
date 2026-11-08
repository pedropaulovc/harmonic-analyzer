"""Shared sheet builder for the oblique jig's pivot and feed blocks (TL-22, TL-32).

Each block's own ``draw_<stem>.py`` reads its own registry row and calls
:func:`draw_block`, so neither drawing's recipe folds the other's row.

Manufacturing sheets for the plain shoulder-screw pivot blocks.

Both sheets print decimal inch (each part's ``drawing_unit``). All sizes
import native model dimensions; no bearing/cartridge sheets survive.
Plan X locations run from the -X (left) edge and Y locations from the -Y
edge through the hidden ``PlanDatumReference`` sketch. Section B-B
shows the floor from the carriage seat, not a competing counterbore-depth
tolerance chain. TL-32's nut face is VIEW D on its own 2:1 sheet, its arrow on
the plan. The layout notes below give sheet millimetres.
"""
from __future__ import annotations
import json
import math
from typing import Any
from _check import check
from _com import _early_bound
from _drawing_attachment import _assert_attached_to, _assert_leader_lands
from _drawing_common import (DrawingOutputs, finalize_drawing, new_project_drawing, read_required_properties, rebuild_drawing,
                             remove_notes_matching)
from _drawing_dimensions import assert_imported_precision, dimension_name, offset_dimension_text
from _drawing_edges import _segment_distance, scan_view_edges
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_attached_note, add_leader_note
from _drawing_projection import model_point_in_view
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_types import layout_report_path
from _drawing_view_display import set_hidden_lines_removed
from _fit_deviations import deviations
from _hole_callout_thread_class import omit_title_block_thread_class
from _paths import CAD_ROOT
from _drawing_metric_vendor import print_imported_metric_dimensions
from _part_properties import part_drawing_unit
from _layout_audit import (arrowhead_segments, assign_sheet_text, audited_annotations,
                           group_rows, ink_key, ink_spans, printed_dump, span_box, text_items)
from _layout_geometry import Box, estimate_text_box
from _title_block_units import MM_PER_INCH, render_number
from _pdf_ink import page_ink, read_pdf_ink
import _telemetry
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
import ch_rocker_arm_tl_oblique_pivot_block_spec as part
from ch_rocker_arm_tl_oblique_callouts import set_callout_lengths_to_three_places

SHEET_SCALE = (1.0,1.0)
# SolidWorks' own descriptive note for TL-32's Hole Wizard nut taps; the native
# tap callout already states the thread.
TAPPED_HOLE_NOTE = '#4-40 Tapped Hole'
# Sheet metres. B-B still cuts the -X M4 column, avoiding the integral +X
# lug. Its upper arrow stands ABOVE all X-dimension tiers; its lower arrow
# stands below the clearance-hole leader. Do not shrink the existing fonts.
# The retained 0c3ed359 pivot PDF put B at x148.225..151.669 mm, directly on
# the x149.172 datum witnesses. At y259 its bottom is y256.310, above the
# highest witness (y254.500), and its top y264.512 clears the y266.7 border.
# Keep dimension text right of the x157 cutting line, not on that line.
# X ordinates remain native baseline dimensions from the finished -X edge;
# Y ordinates are a baseline from the -Y edge (rule 10, one origin: farm r3
# 20261108T014606685Z read the rows chained .512 through the seat axis).
# Native layout and machinist-review own fit.
PLAN_XY = (.170,.205)
# The Y baseline, right of the plan (block y 184.9..225.1, rows at 192.0 and
# 218.0, seat at 205.0 on both sheets: TL-32's plan centres the L, its block
# lands on the same band), shortest nearest: .278 (x 204.5), .79 (217.5),
# 1.302 (230.5), 1.58 (259.5), every witness leaving the +X/-Y corner. The
# .278's 7 mm span cannot hold its text between arrows: the text stands
# just over the span, under the A arrow (y 205 up), left of the .79 line,
# and above TL-32's counterbore leader (y ~180 at x 204.5). The others
# print inside their spans, clear of each other's witnesses.
PLAN_KEEP = {
    'BlockLength':(.170,.2535),'PlanHole2X':(.1665,.248),'PlanHole1X':(.171,.2395),
    'PlanBoreX':(.1635,.231),
    # .278's text under the -Y edge, outside its 7 mm span: beside its span
    # it read '.278.79' with the seat's text (farm r4 20261108T022716612Z).
    'PlanHole3Y':(.2045,.1795),'BlockSideY':(.2175,.199),'PlanHole2Y':(.2305,.2115),
    'BlockWidth':(.2595,.203),
    'BoreDia':(.078,.196),'CarriageDrills1Dia':(.085,.168),'CarriageCounterbores3Dia':(.245,.150),
    # TL-32 still prints this separate native tap dimension in its established
    # upper-left lane. TL-22 imports it at the same source position, then
    # hides only the display after the spec-generated note passes readback.
    'TapDrillDia':(.071,.2455),
}
# A-A remains below the plan, top face up. Its depth text stays outboard
# left of the dimension line; the baseline and actual section span come
# from the model, not the retired asymmetric block's sheet coordinates.
SIDE_XY = (.170,.080)
SIDE_KEEP = {'TopBoreDepth':(.120,.088)}
# TL-22 prints the block height (the Block extrusion's depth) on a standard
# Right view level with the plan: neither its B-B nor its A-A ever imported a
# full-height dimension (farm rounds 1 to 9), though TL-32's B-B does. Top
# face toward the plan (x 283), bottom at x 307, between the plan's 1.58
# (ends ~x 277) and the pictorial (from ~x 311); the height prints under it,
# clear of the 4X counterbore callout at y 150.
RIGHT_XY = (.300,PLAN_XY[1])
RIGHT_KEEP = {'BlockHeight':(.300,.176)}
SEAT_DEPTH_TEXT_XY = (.078,.104)
# B-B: Y up, its +Y face (Y 20) at y 142.5, Z across with the top face toward
# the plan (x 322.85) and the carriage seat at x 347.15; the caption ends
# above the title block (at y 122.5 TL-22's SCALE row met it, farm run
# 20261027T181901497Z). Under the view, the 24.30 met the SECTION B-B
# caption on TL-32 (farm run 20261027T171931429Z). Above it, the floor's
# value and its one-row note stand right of x 353, clear of the block
# height's extension lines (x 322.85, 347.15); the anchor stands 13.5 mm
# over the +Y face (at 8.5 mm, with a two-row note, the dimension line ran
# along the face, farm run 20261027T181901497Z).
FLOOR_XY = (.335,.1225)
FLOOR_KEEP = {'CboreFloor':(.380,.156)}
FEED_FLOOR_KEEP = FLOOR_KEEP | {'SectionBlockHeight':(.335,.172)}
# A-A retains its short overrun. B-B needs independent physical lanes:
# the top is a paper ordinate, the bottom is 16 mm past the block edge.
# The latter puts B's top at y174.446 on TL-22, below the drill leader's
# y178.287 at B's left edge. The -X cut never enters TL-32's +X lug.
FLOOR_CUT_TOP_Y = .259
FLOOR_CUT_BOTTOM_OVERRUN_MM = 16.0
# The section letters print smaller than the document default, and the
# cutting-line arrows shorter, so A's right letter, past the block's +X edge,
# ends under row 4Y's extension line (y 218): at the template's arrows its
# foot stood ~15.5 mm above the line whatever the letter height (farm run
# 20261027T175531766Z). swUserPreferenceDoubleValue_e (swconst.tlb R2026x),
# document scope: section arrowhead length, arrow width, arrow length.
SECTION_LETTER_HEIGHTS = (.005, .0045, .004, .0035, .003)
SECTION_LETTER_CLEARANCE = .001
_PREF_SECTION_ARROW = {27: .0025, 28: .001, 29: .0035}
_PREF_OPTION_NONE = 0
# The 1:1 pictorial's top vertex touched the border at y .235 (review of farm
# run 20261027T181901497Z); 7 mm lower it stays clear of B-B's 24.30 (y 175).
ISO_XY, ISO_SCALE = (.355,.228), SHEET_SCALE
# TL-32's plan drops to allow its column-side lug below the block. PlanLugX
# has its own baseline lane; the lug's +X side is the block's end (owner
# ruling 2026-11-07), so no lug width prints. B-B stops beyond the block
# because its -X column no longer crosses the lug. The taller pictorial
# retains its own 1:2 scale.
FEED_PLAN_XY = (.170,.181)
FEED_PLAN_KEEP = PLAN_KEEP | {
    'PlanLugX':(.1554,.1225),'PlanOverallY':(.285,.181),
    # 84d's counterbore leader crossed VIEW D at y160.934; its text also
    # met D's sheet reference. Raise only this callout: its bottom row starts
    # y165.219 and its top ends y182.765, below the y184.937 width witness.
    'CarriageCounterbores3Dia':(.245,.174),
}
FEED_SIDE_XY = (.170,.060)
FEED_SIDE_KEEP = {'TopBoreDepth':(.120,.068)}
FEED_SEAT_DEPTH_TEXT_XY = (.078,.084)
FEED_ISO_XY, FEED_ISO_SCALE = (.360,.225), (1,2)
# VIEW D looks at the lug's +X nut face; its arrow approaches from the right.
VIEW_LETTER = 'D'
VIEW_LETTER_HEIGHT = .005
VIEW_ARROW_RUN = .015
# VIEW D prints on sheet 2. Keep that reference centred under D, with a
# separate text row; it is not a face/sheet qualifier for the counterbores.
VIEW_SHEET_REF = '(SHEET 2)'
VIEW_SHEET_REF_OFFSET = (-.0075, -.011)
# VIEW D is the standard Right view at 2:1. Relative to the former Left
# view its Z direction reverses: mirror the annotation lanes about NUT_XY,
# not the model or its native dimensions. The lug end remains below the block.
NUT_XY, NUT_SCALE = (.190,.175), (2,1)
NUT_KEEP = {
    'NutCentreY':(.276,.100),'NutCentreZ':(.246,.0772),
    'NutClearanceDia':(.245,.133),'NutClock':(.1479,.0958),
}
NUT_CAPTION = 'VIEW D'
NUT_CAPTION_XY = (.178,.058)  # the note's left edge; centred under the view
# B-B hangs its caption 6 mm under its -Y face.
SECTION_CAPTION_GAP = .006
NUT_CALLOUT_XY = (.112,.165)
NUT_ISO_XY = (.380,.215)
_ARROWS_INSIDE = 0  # swDimArrowsInside
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


def _project(adapter,view,point,label):
    return model_point_in_view(adapter,view,tuple(v/1000 for v in point),label=label)


def _displays(adapter, annotations, names) -> dict[str, Any]:
    """The named imported dimensions' ``IDisplayDimension``s, every name found."""
    found = {}
    for annotation in annotations:
        annotation = _early_bound(annotation, 'IAnnotation')
        name = dimension_name(adapter, annotation)
        if name in names:
            found[name] = _early_bound(annotation.GetSpecificAnnotation(), 'IDisplayDimension')
    missing = sorted(set(names) - set(found))
    if missing:
        raise RuntimeError(f'block dimensions not imported: {missing}')
    return found


# One normal-height, four-line note replaces the two plan-diameter displays.
# Lower-right blank lane, below B-B's plan cutting line; see retained-389
# geometry in the focused regression. The 315-degree rim pick clears centre marks.
PIVOT_STACK_XY = (.190, .125)
PIVOT_NOTE_HEIGHT = .0035
PIVOT_STACK_LANE = (.185, .100, .312, .130)


def _pivot_stack_semantics(text):
    """Plain note rows: retain numbers, signs and precision; normalize whitespace/symbols."""
    text = text.replace('Ø', '<MOD-DIAM>').replace('↧', '<HOLE-DEPTH>')
    return tuple(' '.join(row.split()) for row in text.splitlines())


def _pivot_stack_text(contract):
    """Owner-approved compact text generated from spec values/bands, never copied sizes."""
    if contract.UNIT != 'in':
        raise RuntimeError('pivot stacked callout requires its inch drawing contract')
    places = contract.DRAWING_PRECISION_BY_NAME

    def size(name):
        return render_number(round(contract.DRAWING_VALUES[name] / MM_PER_INCH, places[name]), 'in', places[name])

    def signed(mm):
        magnitude = render_number(round(abs(mm) / MM_PER_INCH, contract.BORE_PLACES), 'in', contract.BORE_PLACES)
        return ('-' if mm < 0 else '+') + magnitude

    lower, upper = deviations(contract.BORE_BAND)
    return (
        f'REAM <MOD-DIAM>{size("BoreDia")} {signed(upper)}/{signed(lower)} <HOLE-DEPTH>{size("TopBoreDepth")}\n'
        '  LOCATING FIT, TL-VN-77 SHOULDER\n'
        f'DRILL <MOD-DIAM>{size("TapDrillDia")} THRU\n'
        f'{contract.PIVOT_TAP} UNC TAP THRU BELOW SEAT'
    )


def _pivot_stack_estimate(text):
    """Conservative offline bound, not a substitute for the exported PDF glyph gate.

    One full cap-height per glyph (versus the shared 0.62 average), 1.6-height
    row pitch and 1 mm all-round bearing/ink padding. Symbols count as one
    glyph. At the current spec: [189,103.7]..[306.5,126] mm, 3.7 mm minimum air.
    """
    glyphs = text.replace('<MOD-DIAM>', 'Ø').replace('<HOLE-DEPTH>', '↧')
    if len(glyphs.splitlines()) != 4:
        raise RuntimeError('pivot stacked callout must remain four short lines')
    box = estimate_text_box(glyphs, anchor=PIVOT_STACK_XY, height=PIVOT_NOTE_HEIGHT,
                            advance_ratio=1.0, line_spacing=1.6)
    if box is None:
        raise RuntimeError('pivot stacked callout has no estimated text extent')
    padded = Box(box.xmin - .001, box.ymin - .001, box.xmax + .001, box.ymax + .001)
    left, bottom, right, top = PIVOT_STACK_LANE
    if min(padded.xmin - left, padded.ymin - bottom, right - padded.xmax, top - padded.ymax) < .003:
        raise RuntimeError(f'pivot stacked callout estimate lacks 3 mm lane margin: {padded.mm()!r}')
    return padded


@_telemetry.traced("drawing.pivot_stacked_callout")
def _stack_pivot_callout(adapter, plan, annotations, contract):
    """One outer-rim note generated from spec, independently checked against native sources."""
    names = ('BoreDia', 'TopBoreDepth', 'TapDrillDia')
    displays = _displays(adapter, annotations, names)

    def source_state(display):
        dim = _early_bound(display.GetDimension2(0), 'IDimension')
        ann = _early_bound(display.GetAnnotation(), 'IAnnotation')
        tol = _early_bound(dim.Tolerance, 'IDimensionTolerance')
        return (
            str(dim.FullName), float(dim.SystemValue),
            tuple(str(display.GetText(which) or '') for which in range(1, 9)),
            int(display.GetPrimaryPrecision2()), int(display.GetPrimaryTolPrecision2()),
            (int(tol.Type), float(tol.GetMinValue()), float(tol.GetMaxValue())),
            tuple(float(v) for v in (ann.GetPosition() or ())),
        )

    sources = {}
    for name, feature in zip(names, ('TopBoreProfile', 'TopBore', 'PivotTapProfile')):
        display = displays[name]
        state = source_state(display)
        if (state[0].split('@')[:2] != [name, feature]
                or not math.isfinite(state[1])
                or not math.isclose(state[1] * 1000, contract.DRAWING_VALUES[name], rel_tol=0, abs_tol=1e-6)
                or state[3] != contract.DRAWING_PRECISION_BY_NAME[name]
                or state[2][2:4] != (contract.CALLOUTS_ABOVE.get(name, ''), contract.CALLOUTS_BELOW.get(name, ''))
                or len(state[6]) != 3 or not all(math.isfinite(v) for v in state[6])):
            raise RuntimeError(f'{name}: unreadable native stacked-callout source {state!r}')
        ann = _early_bound(display.GetAnnotation(), 'IAnnotation')
        if int(ann.OwnerType) != 0 or ann.IsDangling():
            raise RuntimeError(f'{name}: source is not a live drawing-view dimension')
        sources[name] = (_early_bound(display.GetDimension2(0), 'IDimension'), state)
    bore_state = sources['BoreDia'][1]
    tolerance_kind, lower, upper = bore_state[5]
    tolerance_places = bore_state[3] if bore_state[4] == -3 else bore_state[4]
    expected_lower, expected_upper = deviations(contract.BORE_BAND)
    if (tolerance_kind != 2 or not all(math.isfinite(v) for v in (lower, upper))
            or tolerance_places != contract.BORE_PLACES
            or not math.isclose(lower * 1000, expected_lower, rel_tol=0, abs_tol=1e-6)
            or not math.isclose(upper * 1000, expected_upper, rel_tol=0, abs_tol=1e-6)):
        raise RuntimeError('BoreDia: native locating-fit band disagrees with the generated spec band')
    if any(sources[name][1][5][0] != 0 for name in ('TopBoreDepth', 'TapDrillDia')):
        raise RuntimeError('pivot stacked callout: unexpected explicit depth/drill tolerance')

    text = _pivot_stack_text(contract)
    expected = _pivot_stack_semantics(text)
    estimate = _pivot_stack_estimate(text)
    edges = scan_view_edges(plan, label='pivot stacked callout rim')
    outer = edges.circle_at(
        (part.BORE_X, part.BORE_Y, contract.BLOCK_HEIGHT), part.BORE_DIA / 2,
        axis=(0.0, 0.0, 1.0), center_tol_mm=1e-6, radius_tol_mm=1e-6, label='pivot reamed mouth',
    )
    if not all(math.isfinite(v) for v in outer.circle):
        raise RuntimeError('pivot stacked callout outer rim is unreadable')
    centre = _project(adapter, plan, (part.BORE_X, part.BORE_Y, contract.BLOCK_HEIGHT), 'pivot centre')
    rim_offset = part.BORE_DIA / (2 * math.sqrt(2))
    landing = _project(adapter, plan,
                       (part.BORE_X + rim_offset, part.BORE_Y - rim_offset, contract.BLOCK_HEIGHT),
                       'pivot outer lower-right rim')
    radius = math.dist(centre, landing)
    obstacles = tuple(_project(adapter, plan, (x, y, contract.BLOCK_HEIGHT),
                               'carriage counterbore')
                      for x, y in part.BOLT_POINTS)
    x, y = part.BOLT_POINTS[0]
    obstacle_rim = _project(adapter, plan, (x + part.CBORE_DIA / 2, y, contract.BLOCK_HEIGHT),
                            'carriage counterbore radius')
    obstacle_radius = math.dist(obstacles[0], obstacle_rim)
    if (not all(math.isfinite(v) for point in (centre, landing, *obstacles, obstacle_rim) for v in point)
            or radius <= 0 or obstacle_radius <= 0):
        raise RuntimeError('pivot stacked callout projection is unreadable')
    note = _early_bound(add_attached_note(
        adapter, plan, text=text, entity=outer.edge, leader_attach_xy=landing,
        note_xy=PIVOT_STACK_XY, label='pivot stacked native callout',
    ), 'INote')
    _size_note(adapter, note, PIVOT_NOTE_HEIGHT, label='pivot generated callout note height')

    def resolved():
        text_format = _early_bound(note.GetAnnotation(), 'IAnnotation').GetTextFormat(0)
        if (_pivot_stack_semantics(str(note.GetText() or '')) != expected or text_format is None
                or not math.isclose(float(text_format.CharHeight), PIVOT_NOTE_HEIGHT, rel_tol=0, abs_tol=1e-9)):
            raise RuntimeError(f'generated pivot callout disagrees with spec text or note height: {note.GetText()!r}')

    resolved()  # Never hide source displays until generated text/height agrees with the spec.
    for name in ('BoreDia', 'TapDrillDia'):
        _early_bound(displays[name].GetAnnotation(), 'IAnnotation').Visible = 3  # swAnnotationHidden
    rebuild_drawing(adapter, label='hide replaced pivot diameter displays')

    @_telemetry.traced("drawing.pivot_stacked_callout_readback")
    def settled():
        resolved()
        for name, display in displays.items():
            dimension, state = sources[name]
            current = _early_bound(display.GetDimension2(0), 'IDimension')
            ann = _early_bound(display.GetAnnotation(), 'IAnnotation')
            read = source_state(display)
            if (int(adapter.swApp.IsSame(current, dimension)) != 1 or read[:6] != state[:6]
                    or len(read[6]) != 3 or not all(math.isfinite(v) for v in read[6])
                    or math.dist(read[6], state[6]) > 1e-5 or ann.IsDangling()
                    or int(ann.Visible) != (1 if name == 'TopBoreDepth' else 3)):
                raise RuntimeError(f'{name}: stacked callout lost its native source/precision/visibility')
        ann = _early_bound(note.GetAnnotation(), 'IAnnotation')
        if int(ann.OwnerType) != 0 or int(adapter.swApp.IsSame(ann.Owner, plan)) != 1 or int(ann.Visible) != 1:
            raise RuntimeError('pivot stacked callout is not visible in its plan view')
        position = tuple(float(v) for v in (ann.GetPosition() or ()))
        if (len(position) != 3 or not all(math.isfinite(v) for v in position)
                or math.dist(position[:2], PIVOT_STACK_XY) > 1e-5):
            raise RuntimeError('pivot stacked callout moved from its authored text position')
        _assert_attached_to(adapter, ann, outer.edge, entity_type='EDGE',
                            what='pivot stacked callout', label='outer reamed rim')
        _assert_leader_lands(ann, landing, what='pivot stacked callout', label='outer reamed rim', tolerance=1e-5)
        points = tuple(float(v) for v in (ann.GetLeaderPointsAtIndex(0) or ()))
        if len(points) not in (6, 9) or not all(math.isfinite(v) for v in points):
            raise RuntimeError('pivot stacked callout leader is unreadable')
        xy = [(points[i], points[i + 1]) for i in range(0, len(points), 3)]
        strokes = list(zip(xy, xy[1:]))
        data = _early_bound(ann.GetDisplayData(), 'IDisplayData')
        if data is None or int(data.GetArrowHeadCount()) != 1:
            raise RuntimeError('pivot stacked callout must have exactly one native arrow')
        arrow = tuple(float(v) for v in (data.GetArrowHeadAtIndex2(0) or ()))
        if (len(arrow) != 12 or not all(math.isfinite(v) for v in arrow)
                or math.dist(arrow[:2], landing) > 1e-5
                or arrow[8] not in (0, 1) or arrow[6] <= 0 or arrow[7] <= 0):
            raise RuntimeError('pivot stacked callout arrow is not on the outer rim')
        triangle = arrowhead_segments(arrow)
        if len(triangle) != 3:
            raise RuntimeError('pivot stacked callout arrow triangle is unreadable')
        strokes += [((edge.x0, edge.y0), (edge.x1, edge.y1)) for edge in triangle]
        if any(_segment_distance(centre, start, end) < radius - 1e-5 for start, end in strokes):
            raise RuntimeError('pivot stacked callout leader/arrow crosses the bore interior')
        if any(_segment_distance(obstacle, start, end) < obstacle_radius + .001
               for obstacle in obstacles for start, end in strokes):
            raise RuntimeError('pivot stacked callout leader/arrow crowds a carriage counterbore')
        _telemetry.info('pivot stacked native callout readback', generated=text, resolved=str(note.GetText()),
                        note_height_m=PIVOT_NOTE_HEIGHT, estimated_text_bounds_mm=estimate.mm(),
                        source_names=[state[0] for _, state in sources.values()],
                        leader_points_m=list(points), arrow_sheet_data=list(arrow))

    settled()
    return settled


@_telemetry.traced("drawing.pivot_callout_pdf_text")
def _assert_pivot_pdf_text(pdf, report_path, contract) -> None:
    """Reuse the finished sheet's text assignment; only PDF glyphs bound the note."""
    report = json.loads(report_path.read_text(encoding='utf-8'))
    pages = read_pdf_ink(pdf)
    if (len(pages) != 1 or len(report['sheets']) != 1
            or report['stem'] != pdf.stem or report['sheets'][0]['page'] != 0):
        raise RuntimeError('pivot callout PDF/report must describe its one finished sheet')
    dump = printed_dump({**report['sheets'][0], 'ink': page_ink(pages[0])})
    annotations = audited_annotations(dump)
    expected = _pivot_stack_text(contract)
    notes = [item for item in annotations if item.get('type') == 6
             and not (item.get('note') or {}).get('balloon')
             and _pivot_stack_semantics(str((item.get('note') or {}).get('text', '')))
             == _pivot_stack_semantics(expected)]
    if len(notes) != 1 or not notes[0].get('name'):
        raise RuntimeError('pivot callout PDF report lacks its unique four-line note')
    note = notes[0]
    items = text_items(note.get('display') or {})
    if ink_key(''.join(item.text for row in group_rows(items) for item in row)) != ink_key(expected):
        raise RuntimeError('pivot callout display rows are missing or changed')
    spans = ink_spans(dump)
    # Use the audit's one sheet-wide assignment, including competing
    # dimensions, notes, section letters and detail captions. No guessed
    # row positions, second matcher or estimated symbol bounds.
    matches = assign_sheet_text(dump, annotations, spans)
    boxes = []
    for index, item in enumerate(items):
        if not ink_key(item.text):
            continue
        key = (id(note), index)
        if key not in matches:
            raise RuntimeError('pivot callout text is missing from the exported PDF')
        boxes.append(span_box(spans, matches[key]))
    if not boxes:
        raise RuntimeError('pivot callout PDF has no measured text')
    left, bottom, right, top = PIVOT_STACK_LANE
    for box in boxes:
        if (not all(math.isfinite(v) for v in (box.xmin, box.ymin, box.xmax, box.ymax))
                or not (left <= box.xmin < box.xmax <= right
                        and bottom <= box.ymin < box.ymax <= top)):
            raise RuntimeError(f'pivot printed callout text left its reserved lane: {box!r}')
    # REPORT does not enforce these fleet-wide. Reuse its already-computed
    # findings for this note only, rather than inventing another collision audit.
    label = f"note {note['name']}"
    kinds = {'outside-border', 'keep-out', 'text-clearance', 'text-on-view', 'text-on-line'}
    failures = []
    for finding in report['findings']:
        labelled = any(str(finding.get(side, '')) == label
                       or str(finding.get(side, '')).startswith(label + ' ')
                       for side in ('a', 'b'))
        unmatched = (finding['kind'] == 'text-unmatched'
                     and finding.get('a') == note['name']
                     and finding.get('b') in {item.text for item in items})
        if (finding['kind'] in kinds and labelled) or unmatched:
            failures.append(finding)
    if failures:
        raise RuntimeError(f'pivot printed callout text audit failed: {failures!r}')
    _telemetry.info('pivot printed callout text readback',
                    rows=expected.splitlines(), text_bounds_mm=[box.mm() for box in boxes])


def _set_arrow_side(adapter, annotations, names, side) -> None:
    for name, display in _displays(adapter, annotations, names).items():
        display.ArrowSide = side
        if int(display.ArrowSide) != side:
            raise RuntimeError(f'{name}: arrows did not move to side {side}')
    rebuild_drawing(adapter, label=f'arrow side {side}')


# swDimensionTextParts_e (swconst.tlb, SOLIDWORKS 3DEXPERIENCE R2026x, read
# 2026-11-07): swDimensionTextPrefix = 1, swDimensionTextSuffix = 2,
# swDimensionTextCalloutAbove = 3, swDimensionTextCalloutBelow = 4.
TEXT_PARTS = {'prefix': 1, 'suffix': 2, 'above': 3, 'below': 4}
PIVOT_SCREW_NUMBER = 'MHA-CH-06-TL-VN-77'
CARRIAGE_NUMBER = 'MHA-CH-06-TL-VN-83'  # the rail kit's Carriage member


def _inch_ref(mm: float) -> str:
    """A three-place inch REF value, ``(.390)``."""
    return f"({f'{mm / 25.4:.3f}'.lstrip('0')})"


# The printed text of the callouts both blocks share, by dimension and text
# part. The sheet writes every part it prints: the saved models still carry
# the specs' older CALLOUTS_ABOVE/BELOW (a spec edit re-keys both blocks and
# every importer), so those constants are superseded here until the next
# re-key. Machinist review of 957501d1 (TL-22 and TL-32): size, then process,
# then depth (rule 26), the counterbore by its symbol with its depth as REF
# against B-B's controlling floor, never deferred to a view (rule 9); each
# mate once, by its MHA number (rule 4); no reason on an overall size and no
# second mate name on the seat depth or assembly instruction on the floor
# (rule 7). The floor keeps the RV-01 fact, worded as RV-01's ``where``.
_HOLES = f'{len(part.BOLT_POINTS)}X'
BLOCK_CALLOUTS = {
    'BoreDia': {'suffix': f' REAM <HOLE-DEPTH> {_inch_ref(part.BORE_DEPTH)}', 'above': '',
                'below': f'LOCATING FIT ON {PIVOT_SCREW_NUMBER} SHOULDER'},
    'TapDrillDia': {'suffix': ' DRILL THRU', 'above': '', 'below': f'{part.PIVOT_TAP} UNC THRU'},
    'CarriageDrills1Dia': {'prefix': f'{_HOLES} <MOD-DIAM>', 'suffix': ' DRILL THRU', 'above': '',
                           'below': f'MATCHES {CARRIAGE_NUMBER} CARRIAGE'},
    # Dimension text takes gtol.sym's HOLE-SPOT (Counterbore(Spotface)); the
    # Hole Wizard callout variable <HOLE-CBORE> printed literally here (r1).
    'CarriageCounterbores3Dia': {'prefix': f'{_HOLES} <HOLE-SPOT><MOD-DIAM>',
                                 'suffix': f' <HOLE-DEPTH> {_inch_ref(part.CBORE_DEPTH)}',
                                 'above': '', 'below': ''},
    'TopBoreDepth': {'below': ''},
    'CboreFloor': {'below': f'ENGAGES {part.ENGAGEMENT_TEXT} MIN ({part.ENGAGEMENT_DIAMETERS})'},
    'BlockLength': {'below': ''},
    'BlockWidth': {'below': ''},
}


def block_callouts(overrides=None) -> dict[str, dict[str, str]]:
    """``BLOCK_CALLOUTS`` with a sheet's own ``overrides`` merged per
    dimension: an override replaces only the parts it names."""
    merged = {name: dict(parts) for name, parts in BLOCK_CALLOUTS.items()}
    for name, parts in (overrides or {}).items():
        unknown = sorted(set(parts) - set(TEXT_PARTS))
        if unknown:
            raise ValueError(f'{name}: unknown dimension text parts {unknown}')
        merged.setdefault(name, {}).update(parts)
    return merged


@_telemetry.traced("drawing.block_callouts")
def _set_callouts(adapter, annotations, callouts: dict[str, dict[str, str]]) -> None:
    """Write each named dimension's printed text parts and read each back.

    COM contract (sldworks.tlb R2026x, IDisplayDimension, audited
    2026-11-07): ``GetText(WhichText: VT_I4) -> VT_BSTR`` and
    ``SetText(WhichText: VT_I4, Text: VT_BSTR) -> VT_VOID``. SetText reports
    nothing and replaces (never appends to) the part, so a part is accepted
    only when it reads back exactly."""
    for name, display in _displays(adapter, annotations, tuple(callouts)).items():
        for part_name, text in callouts[name].items():
            which = TEXT_PARTS[part_name]
            display.SetText(which, text)
            read = str(display.GetText(which) or '')
            if read != text:
                raise RuntimeError(f'{name}: {part_name} text reads {read!r}, expected {text!r}')
    rebuild_drawing(adapter, label='block callouts')


def _size_note(adapter, note, height: float, *, label: str) -> None:
    annotation = _early_bound(note.GetAnnotation(), 'IAnnotation')
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f'{label} has no text format')
    text_format.CharHeight = height
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f'failed to size {label}')
    rebuild_drawing(adapter, label=label)


def _section_letter_tops(dr_section) -> list[float]:
    """Sheet y of each cutting-line letter's top (GetTextInfo: x, y, z per
    letter at its top-left, draw_fr_harmonic_base.section_line_boxes)."""
    info = [float(v) for v in (dr_section.GetTextInfo() or ())]
    if len(info) < 6:
        raise RuntimeError(f'section {dr_section.GetLabel()!r}: unreadable letter positions {info!r}')
    return [info[1], info[4]]


def _section_with_material_beyond(adapter, view, letter: str, anchor: tuple[float, float, float],
                                  target: tuple[float, float], caption_top: tuple[float, float],
                                  sheet_scale: tuple[float, float]) -> None:
    """Print the cut and the material beyond it in solid lines (rule 9).
    B-B cuts both -X counterbored holes, each drilled through, so its cut
    face alone printed three hatched pieces with nothing joining them
    (machinist review of 957501d1, TL-22 and TL-32). The view looks -X from
    the -X hole column: beyond it stands only the block's -X end, the whole
    40 mm outline, and TL-32's lug (X from its .87 face) is behind the plane.
    R2026x declares the setter void; only its bool getter is truth-tested
    (draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit). The view keeps the
    place SolidWorks centred on the larger outline, and the centre mark of a
    hole off the plane (farm run 20261027T192802646Z), so the marks go and
    the view moves until the model point ``anchor`` (mm) lands on ``target``
    (sheet m)."""
    bound = _early_bound(view, 'IView')
    cut = _early_bound(bound.GetSection(), 'IDrSection')
    cut.SetDisplayOnlySurfaceCut(False)
    rebuild_drawing(adapter, label=f'section {letter} with material beyond')
    if bool(cut.GetDisplayOnlySurfaceCut()):
        raise RuntimeError(f'section {letter} still prints its cut face only')
    set_hidden_lines_removed(adapter, view)
    marks = tuple(bound.GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ())
    if marks:
        draw = adapter.currentModel
        draw.ClearSelection2(True)
        for index, mark in enumerate(marks):
            if not _early_bound(mark, 'IAnnotation').Select2(index > 0, 0):
                raise RuntimeError(f'cannot select section {letter} centre mark')
        draw.EditDelete()  # VT_VOID: the re-read below is the proof
        draw.ClearSelection2(True)
        rebuild_drawing(adapter, label=f'delete section {letter} centre marks')
        if bound.GetAnnotationsByType(_CENTER_MARK_ANNOTATION):
            raise RuntimeError(f'section {letter} centre marks survived deletion')
    landed = _project(adapter, view, anchor, f'section {letter} anchor')
    position = [float(v) for v in bound.Position]
    move = [position[i] + target[i] - landed[i] for i in range(2)]
    if bound.SetViewPosition(double_array(move), False) is not True:
        raise RuntimeError(f'section {letter}: position {move!r} refused')
    rebuild_drawing(adapter, label=f'section {letter} re-anchored')
    landed = _project(adapter, view, anchor, f'section {letter} anchor after move')
    _telemetry.info(f'section {letter}: {len(marks)} centre marks deleted; anchor at {landed!r}, '
                    f'target {target!r}')
    if math.dist(landed, target) > 5e-5:
        raise RuntimeError(f'section {letter}: anchor landed at {landed!r}, not {target!r}')
    _place_caption(adapter, view, caption_top, letter, sheet_scale)


def _pin_sheet_scale(adapter, sheet_scale) -> None:
    """Hold the active sheet at its printed scale and read it back. Inserting
    model views drifts the sheet scale, and a native section caption carries
    its scale field only when the view's scale differs from the sheet's AT
    CREATION (draw_fr_top_frame._pin_sheet_scale), so each section is cut on
    the pinned sheet: TL-22 and TL-32 printed SCALE 1 : 1 under both
    sections of a 1:1 sheet (machinist review of 957501d1, rule 9).
    ``ISheet.SetScale(Numerator, Denominator, FirstAngle, ...)`` -> VT_BOOL;
    ``GetProperties2`` -> doubles, the scale at [2] and [3]."""
    sheet = _early_bound(_early_bound(adapter.currentModel, 'IDrawingDoc').GetCurrentSheet(), 'ISheet')
    if not sheet.SetScale(*sheet_scale, False, False):
        raise RuntimeError(f'cannot pin the sheet at {sheet_scale!r}')
    properties = [float(v) for v in (sheet.GetProperties2() or ())]
    if len(properties) < 4 or (properties[2], properties[3]) != tuple(float(v) for v in sheet_scale):
        raise RuntimeError(f'sheet scale did not hold at {sheet_scale!r}: {properties!r}')


def _section_caption(view, letter: str):
    """The section's one native caption, refused if it prints a scale: every
    block section is drawn at the sheet's own scale, which the title block
    states (rule 9)."""
    label = f'section {letter} caption'
    notes = tuple(_early_bound(view, 'IView').GetNotes() or ())
    if len(notes) != 1:
        raise RuntimeError(f'expected one native {label}, found {len(notes)} notes')
    note = _early_bound(notes[0], 'INote')
    # GetText reads linked fields blank; the linked text keeps the fields.
    linked = str(note.PropertyLinkedText or '')
    _telemetry.info(f'{label}: linked text {linked!r}')
    if '<VLSCALEV>' in linked:
        raise RuntimeError(f'{label} {linked!r} prints the scale the title block states')
    return note


def _place_caption(adapter, view, target, letter: str, sheet_scale) -> None:
    """Move the section's native caption so its box's top centre lands on
    ``target``: it kept its place under the larger outline, on the title
    block (farm run 20261027T195248081Z). The sheet scale is pinned first so
    finalization cannot move it after (draw_ch_rocker_arm_tl_vn_oblique_leadscrew_kit
    ``_place_view_caption``)."""
    label = f'section {letter} caption'
    _pin_sheet_scale(adapter, sheet_scale)
    note = _section_caption(view, letter)
    annotation = _early_bound(note.GetAnnotation(), 'IAnnotation')
    # On the 2:1 sheet the caption steps ~0.48 mm at a time: a section
    # caption's top swung between 0.26 mm under and 0.21 mm over its target
    # for ten passes (farm run 20261027T200846410Z), so half a millimetre is
    # landed.
    for attempt in range(6):
        extent = [float(v) for v in note.GetExtent()]
        error = (target[0] - (extent[0] + extent[3]) / 2, target[1] - extent[4])
        _telemetry.info(f'{label} pass {attempt}: box {extent!r}, error {error!r}')
        if max(abs(error[0]), abs(error[1])) < 5e-4:
            break
        x, y, z = (float(v) for v in annotation.GetPosition())
        if not annotation.SetPosition2(x + error[0], y + error[1], z):
            raise RuntimeError(f'failed to move the {label}')
        rebuild_drawing(adapter, label=f'place {label}')
    else:
        raise RuntimeError(f'{label} stayed at {extent!r}, its top centre wanted at {target!r}')
    _telemetry.info(f'{label}: box {extent!r}')


def _set_section_arrows(adapter) -> None:
    """Set this document's cutting-line arrow sizes, read back, raise on
    mismatch (draw_dt_cone_gear_shaft._pin_witness_line_extension)."""
    extension = _early_bound(adapter.currentModel, 'IModelDoc2').Extension
    for key, value in _PREF_SECTION_ARROW.items():
        before = float(extension.GetUserPreferenceDouble(key, _PREF_OPTION_NONE))
        ok = extension.SetUserPreferenceDouble(key, _PREF_OPTION_NONE, value)
        applied = float(extension.GetUserPreferenceDouble(key, _PREF_OPTION_NONE))
        if not ok or abs(applied - value) > 1e-7:
            raise RuntimeError(f'section arrow preference {key}: set {value} returned {ok!r}, '
                               f'reads {applied}, was {before}')
        _telemetry.info(f'section arrow preference {key}: {before * 1000:.2f} -> {applied * 1000:.2f} mm')


def _set_section_letter_height(adapter, dr, height: float) -> None:
    text_format = _early_bound(dr.GetTextFormat(), 'ITextFormat')
    text_format.CharHeight = height
    if not dr.SetTextFormat(False, text_format):
        raise RuntimeError(f'section {dr.GetLabel()!r}: letter height {height} refused')
    rebuild_drawing(adapter, label='section letter height')


def _fit_section_letters(adapter, fitted, matched, *, below_y: float) -> None:
    """Shrink ``fitted``'s cutting-line letters until both tops stand
    ``SECTION_LETTER_CLEARANCE`` under ``below_y``, and print ``matched``'s at
    the same height. Every height tried is logged with the letter tops, so a
    seat that moves the letters differently reads off the leaf log."""
    fit = _early_bound(_early_bound(fitted, 'IView').GetSection(), 'IDrSection')
    tops: list[float] = []
    for height in SECTION_LETTER_HEIGHTS:
        _set_section_letter_height(adapter, fit, height)
        tops = _section_letter_tops(fit)
        _telemetry.info(f'section letters at {height * 1000:g} mm: tops {tops!r}, limit {below_y!r}')
        if max(tops) <= below_y - SECTION_LETTER_CLEARANCE:
            break
    else:
        _telemetry.warn(f'section letters still reach y {max(tops)!r} against {below_y!r} at '
                        f'{SECTION_LETTER_HEIGHTS[-1] * 1000:g} mm')
    for view in matched:
        _set_section_letter_height(adapter, _early_bound(_early_bound(view, 'IView').GetSection(), 'IDrSection'),
                                   height)


def _view_arrow(adapter, plan, contract) -> None:
    """The lettered viewing arrow onto the lug's +X nut face."""
    tip = _project(adapter, plan, (contract.NUT_FACE_X, (contract.LUG_Y0 + contract.LUG_Y1) / 2,
                                   contract.BLOCK_HEIGHT), 'view D arrow tip')
    text_xy = (tip[0] + VIEW_ARROW_RUN, tip[1] + VIEW_LETTER_HEIGHT / 2)
    note = add_leader_note(adapter, VIEW_LETTER, text_xy=text_xy, attach_xy=tip, view=plan,
                           label=f'view {VIEW_LETTER} viewing arrow')
    _size_note(adapter, note, VIEW_LETTER_HEIGHT, label=f'view {VIEW_LETTER} arrow letter')
    ref = add_note(adapter, VIEW_SHEET_REF, text_xy[0] + VIEW_SHEET_REF_OFFSET[0],
                   text_xy[1] + VIEW_SHEET_REF_OFFSET[1])
    if ref is None:
        raise RuntimeError(f'failed to insert the view {VIEW_LETTER} sheet reference')


async def draw_block(adapter, spec, contract, *, read_source_properties=None, callouts=None):
    """Draw one block's sheets. ``callouts`` holds the sheet's own printed
    text parts by dimension, merged over ``BLOCK_CALLOUTS``
    (:func:`block_callouts`)."""
    printed = block_callouts(callouts)
    source = CAD_ROOT/'out'/'sldprt'/f'{spec.artifact_stem}.SLDPRT'
    check('open block',await adapter.open_model(str(source)))
    if read_source_properties is None:
        read_required_properties(adapter.currentModel,('Number','Material Specification','Finish','Quantity'),
                                 required=('Number','Material Specification','Finish','Quantity'))
    else:
        read_source_properties(adapter)
    drawing,_ = new_project_drawing(adapter,property_view=spec.artifact_stem,scale=SHEET_SCALE,layout=spec.layout,
                                    unit=part_drawing_unit(spec.artifact_stem))
    is_feed = hasattr(contract,'NUT_FACE_X')
    sheets = ('Pivot and carriage','Nut interface') if is_feed else ('Pivot and carriage',)
    create_blank_drawing_sheets(adapter,sheets,label='block sheets')
    drawing = _early_bound(drawing,'IDrawingDoc')
    drawing.ActivateSheet(sheets[0])
    plan_xy, plan_keep, side_xy, side_keep, seat_text_xy, iso_xy, iso_scale, floor_keep = (
        (FEED_PLAN_XY, FEED_PLAN_KEEP, FEED_SIDE_XY, FEED_SIDE_KEEP, FEED_SEAT_DEPTH_TEXT_XY, FEED_ISO_XY, FEED_ISO_SCALE,
         FEED_FLOOR_KEEP)
        if is_feed else (PLAN_XY, PLAN_KEEP, SIDE_XY, SIDE_KEEP, SEAT_DEPTH_TEXT_XY, ISO_XY, ISO_SCALE, FLOOR_KEEP))
    plan = place_view(adapter,str(source),'*Front',*plan_xy,scale=SHEET_SCALE)
    # Each cutting line runs so its arrows point away from the section it
    # names (third-angle): A-A below the plan looks up, B-B right of it looks
    # left. A-A stays short; B-B's ends use the reserved annotation lanes.
    _set_section_arrows(adapter)
    _pin_sheet_scale(adapter, SHEET_SCALE)
    side = create_section_view(adapter,plan,
        line_start=_project(adapter,plan,(part.BLOCK_X1+4,0,contract.BLOCK_HEIGHT),'pivot cut start'),
        line_end=_project(adapter,plan,(part.BLOCK_X0-4,0,contract.BLOCK_HEIGHT),'pivot cut end'),
        view_xy=side_xy,section_label='A',scale=(1,1),partial=True,label='pivot shoulder seat')
    _section_caption(side, 'A')
    iso = place_view(adapter,str(source),'*Isometric',*iso_xy,scale=iso_scale)
    set_hidden_lines_removed(adapter,plan)
    plan_annotations = curate_view_dimensions(adapter,plan,keep=plan_keep,view_label='plan',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    settled_checks = ()
    if not is_feed:
        settled_checks = (_place_pivot_tap_arrow_inside(adapter, plan, plan_annotations, contract),)
    set_hidden_lines_removed(adapter,side)
    side_annotations = curate_view_dimensions(adapter,side,keep=side_keep,view_label='pivot section direction',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    _set_arrow_side(adapter, side_annotations, ('TopBoreDepth',), _ARROWS_INSIDE)
    offset_dimension_text(adapter, side_annotations, {'TopBoreDepth': seat_text_xy})
    annotations = plan_annotations + side_annotations
    x = part.CBORE_SECTION_X
    cut_axis = _project(adapter,plan,(x,part.BLOCK_WIDTH/2,contract.BLOCK_HEIGHT),'floor cut axis')
    if cut_axis[1] + .004 > FLOOR_CUT_TOP_Y:
        raise RuntimeError('B-B top arrow lane does not clear the block')
    start = (cut_axis[0], FLOOR_CUT_TOP_Y)
    end_y = -part.BLOCK_WIDTH/2-FLOOR_CUT_BOTTOM_OVERRUN_MM
    end = _project(adapter,plan,(x,end_y,contract.BLOCK_HEIGHT),'floor cut end')
    _pin_sheet_scale(adapter, SHEET_SCALE)
    floor = create_section_view(adapter,plan,line_start=start,line_end=end,view_xy=FLOOR_XY,
                                section_label='B',scale=(1,1),partial=True,
                                label='carriage counterbore floor')
    # Both blocks print B-B with the material beyond the cut, the top face's
    # +Y corner where the full B-B put it. TL-32's B-B also prints the block
    # height (CboreFloorReference's interior line); TL-22 prints it on the
    # Right view.
    _section_with_material_beyond(adapter, floor, 'B', (x, part.BLOCK_WIDTH/2, contract.BLOCK_HEIGHT),
                                  (FLOOR_XY[0]-contract.BLOCK_HEIGHT/2000, FLOOR_XY[1]+part.BLOCK_WIDTH/2000),
                                  (FLOOR_XY[0], FLOOR_XY[1]-part.BLOCK_WIDTH/2000-SECTION_CAPTION_GAP),
                                  SHEET_SCALE)
    row_4y = _project(adapter,plan,(part.BLOCK_X1,part.BOLT_Y,contract.BLOCK_HEIGHT),'row 4Y')
    _fit_section_letters(adapter, side, (floor,), below_y=row_4y[1])
    annotations += curate_view_dimensions(adapter,floor,keep=floor_keep,view_label='B-B floor',
                     dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    right_keep = {}
    if not is_feed:
        right = place_view(adapter,str(source),'*Right',*RIGHT_XY,scale=SHEET_SCALE)
        set_hidden_lines_removed(adapter,right)
        right_keep = RIGHT_KEEP
        annotations += curate_view_dimensions(adapter,right,keep=right_keep,view_label='right end',
                         dimensions_by_feature=contract.DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter,iso)
    sheet_scales = None
    if is_feed:
        _view_arrow(adapter, plan, contract)
        drawing.ActivateSheet(sheets[1])
        nut = place_view(adapter,str(source),'*Right',*NUT_XY,scale=NUT_SCALE)
        nut_iso = place_view(adapter,str(source),'*Isometric',*NUT_ISO_XY,scale=FEED_ISO_SCALE)
        set_hidden_lines_removed(adapter,nut)
        set_hidden_lines_removed(adapter,nut_iso)
        nut_annotations = curate_view_dimensions(adapter,nut,keep=NUT_KEEP,view_label='nut face',
                      dimensions_by_feature=contract.DRAWING_DIMENSIONS)
        print_imported_metric_dimensions(adapter, nut_annotations,
                                          {name: places for (_, name), (places, _) in contract.METRIC_DIMENSIONS.items()})
        caption = add_note(adapter, NUT_CAPTION, *NUT_CAPTION_XY)
        if caption is None:
            raise RuntimeError('failed to insert the VIEW D caption')
        _size_note(adapter, caption, VIEW_LETTER_HEIGHT, label='VIEW D caption')
        # The +Y/+Z tap is upper-left in this Right view. Its callout
        # approaches from the left; the title block owns the thread class.
        # row says where the taps come from (TL-00 says how).
        y,z = contract.NUT_HOLES_YZ[3]
        rim = contract.NUT_TAP_DRILL/2/math.sqrt(2)
        edge = _project(adapter,nut,(contract.NUT_FACE_X,y+rim,z+rim),'nut tap mouth')
        taps = add_native_hole_callout(adapter,nut,edge_xy=edge,callout_xy=NUT_CALLOUT_XY,
                                       label='feed nut screw taps',process=contract.TRANSFER_PROCESS)
        omit_title_block_thread_class(taps, label='feed nut screw taps')
        set_callout_lengths_to_three_places(taps, label='feed nut screw taps')
        rebuild_drawing(adapter, label='feed nut screw tap callout')
        annotations += nut_annotations
        sheet_scales = {sheets[0]: SHEET_SCALE, sheets[1]: NUT_SCALE}
    _set_callouts(adapter, annotations, printed)
    # Every printed dimension keeps its part-authored places; the repeated
    # row/column locations left off the sheet print nothing to check.
    kept = {*plan_keep, *side_keep, *floor_keep, *right_keep, *(NUT_KEEP if is_feed else ())}
    precision = {name:places for dims in contract.DRAWING_PRECISION.values()
                 for name,places in dims.items() if name in kept}
    assert_imported_precision(adapter,annotations,precision)
    if not is_feed:
        settled_checks = (_stack_pivot_callout(adapter, plan, annotations, contract),)
    if is_feed:
        # SolidWorks pins its own TAPPED_HOLE_NOTE once per view that picks up
        # the one NutTaps feature, and which views do is its choice: the same
        # recipe and model printed 1 on main 6d7f35476 and 2 on 1e2b7b540
        # (draw_fr_top_frame._auto_tapped_hole_notes). So the count is logged
        # by sheet, not gated, and finalize's sweep proves none reaches the print.
        removed = {}
        for sheet_name in sheets:
            drawing.ActivateSheet(sheet_name)
            removed[sheet_name] = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
        _telemetry.info(f'removed automatic {TAPPED_HOLE_NOTE!r} notes by sheet: {removed}')
    drawing.ActivateSheet(sheets[0])
    outputs = DrawingOutputs(slddrw=spec.outputs['slddrw'],pdf=spec.outputs['pdf'],png=spec.outputs['png'])
    artifacts = await finalize_drawing(adapter,outputs,pdf_title='Rocker Oblique Trammel Block Manufacturing Drawing',
                                       scale=SHEET_SCALE,layout=spec.layout,sheet_scales=sheet_scales,
                                       redundant_note_substrings=(TAPPED_HOLE_NOTE,) if is_feed else (),
                                       expected_redundant_notes=0, settled_checks=settled_checks)
    if not is_feed:
        _assert_pivot_pdf_text(outputs.pdf, layout_report_path(spec.artifact_stem), contract)
    return artifacts

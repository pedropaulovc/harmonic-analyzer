"""The cone tip gear (MHA-DT-37): T006's leaves with an integral spigot and
pivot, its sheet 1 and the DT6-FORM1 tooth-space sheet moved from the cone
gear family's drawing. Offline: no SolidWorks."""

from __future__ import annotations

import inspect
import math
import re
from dataclasses import replace
from pathlib import Path

import pytest

import _config
import build_dt_cone_tip_gear as build
import cone_tip_cluster as cluster
import draw_dt_cone_tip_gear as drawing
import dt_cone_gear_spec as family
import dt_cone_tip_gear_notes as notes
import dt_cone_tip_gear_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box, Segment, segment_box_distance

# 2.5 mm note text: 1.79 mm a character, 3.51 mm a line (the family's
# measured pitch); dimension text: 2.77 mm a character, 5.7 mm a row.
NOTE_CHAR, NOTE_LINE = 0.00179, 0.00351
DIM_CHAR, DIM_ROW = 0.00277, 0.0057
BORDER = (0.010, 0.010, 0.422, 0.267)
TITLE_BLOCK = (0.216, 0.0, 0.432, 0.064)


def test_the_part_is_the_family_t006_on_its_own_identity() -> None:
    row = _config.parts(spec.PART_NAME)
    assert row["number"] == spec.PART_NUMBER == "MHA-DT-37"
    assert (
        row["material_specification"] == spec.MATERIAL_SPEC == family.TIP_MATERIAL_SPEC
    )
    assert spec.TEETH == 6
    # The leaves are the family's T006 numbers, never a fork of them.
    assert spec.OUTSIDE_DIA == family.outside_dia_mm(6)
    assert spec.TOOTH_THICKNESS == family.tooth_thickness_mm(6)
    assert spec.FLOOR_LIMITS_MM == family.floor_limits_mm(6)
    assert spec.FACE_WIDTH == family.FACE_WIDTH
    assert spec.TEMPLATE.name == notes.CUTTER_DETAIL_SHEET == "DT6-FORM1"
    assert spec.TEMPLATE.cutter_number is None
    assert spec.TOOTH_FEATURES == family.tooth_features(6)
    assert spec.SIMPLIFIED_FEATURES == spec.TOOTH_FEATURES[1:]
    # T006 left the configured family (T012..T120).
    assert 6 not in family.CONFIGURATION_TEETH


def test_stems_are_the_clusters_and_clear_the_tooth_cutter() -> None:
    assert spec.STEM_DIA_MM == cluster.STEM_DIA_MM == pytest.approx(0.0625 * 25.4)
    assert spec.SPIGOT_DIA_BAND == cluster.SPIGOT_DIA_BAND
    assert spec.PIVOT_DIA_BAND == cluster.PIVOT_DIA_BAND
    assert spec.SPIGOT_LENGTH_MM == cluster.SPIGOT_LENGTH_MM
    assert spec.PIVOT_LENGTH_MM == cluster.PIVOT_LENGTH_MM
    # DT6-FORM1 runs off over both stems: every stem limit stands under the
    # smallest root envelope and under every actual cutter corner.
    assert spec.CUTTER_RUNOFF_MM / 25.4 == pytest.approx(0.01075, abs=1e-5)
    corners = family.manufacturing_corner_profiles(6)
    assert min(c.root_radius_min_mm for c in corners) > spec.STEM_MAX_DIA_MM / 2.0


def test_the_frame_is_the_family_frame_with_stems_either_side() -> None:
    """Origin on the axis at the leaves' south face (the Front Plane), +Z
    north: the drive train seats it as it seats a family configuration."""
    assert spec.SPIGOT_END_Z_MM == -spec.SPIGOT_LENGTH_MM
    assert spec.LEAVES_NORTH_Z_MM == spec.FACE_WIDTH
    assert spec.PIVOT_END_Z_MM == spec.FACE_WIDTH + spec.PIVOT_LENGTH_MM
    assert spec.OVERALL_LENGTH_MM == pytest.approx(
        spec.PIVOT_END_Z_MM - spec.SPIGOT_END_Z_MM
    )
    assert spec.PATTERN_AXIS == "Axis1"
    assert spec.LEAVES_NORTH_PLANE == "LeavesNorthPlane"
    source = inspect.getsource(build)
    assert "save_simplified_part(adapter, PART_NAME, SIMPLIFIED_FEATURES)" in source
    assert (
        'blank_reference_geometry(adapter, ((LEAVES_NORTH_PLANE, "PLANE"),))' in source
    )
    assert '"FaceWidth@Blank"' in source


def test_the_fits_the_stems_make() -> None:
    inch = 25.4
    # The spigot's bond: clearance at every limit, inside the compound's gap.
    low, high = spec.SPIGOT_BOND_CLEARANCE_MM
    assert 0.0 <= low < high <= cluster.RETAINING_COMPOUND_MAX_GAP_MM
    # The bushing's press on the pivot: interference at every limit.
    assert spec.PIVOT_PRESS_INTERFERENCE_MM[0] / inch == pytest.approx(0.0002, abs=5e-6)
    assert spec.PIVOT_PRESS_INTERFERENCE_MM[1] / inch == pytest.approx(0.0010, abs=5e-6)
    assert spec.inch_range(spec.PIVOT_PRESS_INTERFERENCE_MM) == ".0002-.0010"
    # The pivot runs in the end screw: clearance at every limit.
    assert 0.0 < spec.PIVOT_RUNNING_CLEARANCE_MM[0] < spec.PIVOT_RUNNING_CLEARANCE_MM[1]


def test_every_printed_dimension_has_the_parts_places() -> None:
    printed = drawing.sheet_dimension_names()
    assert printed == set(drawing.FRONT_KEEP) | set(drawing.SIDE_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == printed
    assert spec.DRAWING_PRECISION_BY_NAME["SpigotDia"] == 4
    assert spec.DRAWING_PRECISION_BY_NAME["PivotDia"] == 4
    assert spec.DRAWING_PRECISION_BY_NAME["SpigotLength"] == 2
    # The overall is a reference at the lengths' places, from the spec.
    assert spec.DRAWING_REFERENCE_PRECISION == 2
    assert set(notes.DIMENSION_CALLOUTS) <= printed
    assert set(notes.CALLOUTS_ABOVE) <= printed


def test_callouts_and_notes_name_every_mate_once() -> None:
    callouts = notes.DIMENSION_CALLOUTS
    assert all(len(text.splitlines()) <= 2 for text in callouts.values())
    spigot = callouts["SpigotDia"]
    for mate in ("MHA-DT-04", "MHA-DT-03-T012", "MHA-DT-03-T018"):
        assert mate in spigot
    assert spigot.startswith("BONDED FIT IN")
    pivot = callouts["PivotDia"]
    assert pivot == f"PRESS AND RUNNING FIT\n{notes.PIVOT_NOTE_FLAG}"
    sheet = notes.sheet_notes().splitlines()
    assert len(sheet) <= 6
    # One pivot diameter: pressed in the bushing, its end running in the end
    # screw's hole; both mates by number and name, both acceptances.
    pivot_note = " ".join(sheet[:2])
    assert sheet[0].startswith(
        f"{notes.PIVOT_NOTE_NUMBER}. PIVOT: PRESS FIT IN MHA-DT-38"
    )
    assert "MHA-DT-39 CONE TIP END SCREW" in pivot_note
    assert spec.inch_range(spec.PIVOT_PRESS_INTERFERENCE_MM) in pivot_note
    assert spec.inch_range(spec.PIVOT_RUNNING_CLEARANCE_MM) in pivot_note
    assert sheet[2].startswith(f"{notes.TEETH_NOTE_NUMBER}. TEETH MESH WITH MHA-DT-12")
    assert sheet[-2] == "3. CENTRES OK."
    # The width's mate in a flagged note: its callout block fits between the
    # extension lines the two stem lengths share.
    assert callouts["FaceWidth"] == notes.FACE_NOTE_FLAG == "SEE NOTE 4"
    assert sheet[-1] == "4. GEAR WIDTH: SETS THE CONE GEAR STACK ON MHA-DT-04."
    text = "\n".join((*sheet, *callouts.values()))
    # No retired part, no solder, no D-flat, no stale tip collar.
    for retired in ("MHA-DT-VN-54", "MHA-DT-VN-55", "SOLDER", "FLAT", "COLLAR"):
        assert retired not in text, retired
    gear_data = notes.gear_data()
    assert "MATE:  MHA-DT-12, 120T" in gear_data
    # The setup names the features the sheet draws, not private labels.
    assert "TIR MAX TO BOTH \u00d8.0625 ENDS" in gear_data
    assert "SPIGOT" not in gear_data and "PIVOT" not in gear_data
    minimum, maximum = family.over_pins_limits_mm(6)
    assert f"{spec.inch_text(minimum, 4)} TO {spec.inch_text(maximum, 4)}" in gear_data


def test_yaml_carries_the_t006_tooth_band_ruling_only() -> None:
    row = _config.parts(spec.PART_NAME)
    rows = row["machinist_exceptions"]
    assert [entry["id"] for entry in rows] == ["RV-01"]
    assert "2026-11-09" in str(rows[0]) and "pull/1992" in str(rows[0])


def test_custom_six_detail_reproduces_complete_finite_core_grinding_curves() -> None:
    installed = family.stock_form_profile(6)
    template = installed.template
    tool = replace(
        installed, blank_radius_mm=template.tip_radius_mm, radial_translation_mm=0.0
    )
    detail = notes.custom_cutter_detail()
    assert drawing.SHEET_NAMES[-1] == notes.CUTTER_DETAIL_SHEET
    assert "CUSTOM GROUND FORM" in detail
    assert "NO UPPER CONTINUATION" in detail
    assert "ROOT ARC; DRUM-TIP TROCHOID RELIEF TO TIF; N6 WORKING INVOLUTE" in detail
    normalized = re.sub(r"\s+", "", detail)
    required = []
    for segment in tool.native_segments(
        unit_scale=1.0, clearance_radius_mm=template.tip_radius_mm + 1.0
    ):
        if segment.kind in {"root_arc", "relief", "flank"}:
            required.append(segment.kind)
            assert re.sub(r"\s+", "", segment.x) in normalized
            assert re.sub(r"\s+", "", segment.y) in normalized
    assert sorted(required) == ["flank", "flank", "relief", "relief", "root_arc"]
    assert "closing_ray" not in detail and "clearance_arc" not in detail
    assert "STOCK #8" not in detail
    assert max(map(len, detail.splitlines())) <= notes.CUTTER_DETAIL_LINE_CHARS


def test_tooth_space_sheet_defines_the_space_point_by_point() -> None:
    """Sheet 2 defines the T006 tooth space (one-sided form tolerance), which
    is DT6-FORM1's edge; the gear is accepted by sheet 1's note 2."""
    profile = family.stock_form_profile(6)
    template = profile.template
    table = drawing.form_table_rows()
    assert table[0] == ("POINT", "R", "X", "Y")
    title = drawing.form_sheet_title()
    notes_text = drawing.form_sheet_notes()
    lines = [title, *notes_text.splitlines()]
    assert len(lines) <= 4
    assert title == "MHA-DT-37 TOOTH SPACE, INCH (CONTINUED FROM SHEET 1)"
    assert drawing.SHEET_NAMES == ("T006", "DT6-FORM1")
    assert notes_text.splitlines()[-1] == (
        f"{family.CUSTOM_SIX_FORM_TOLERANCE_NOTE}, SEE SHEET 1 NOTE {notes.TEETH_NOTE_NUMBER}."
    )
    data = "\n".join([*lines, *(" ".join(row) for row in table)])
    assert notes.CYLINDER_MATE_NUMBER not in data and "BACKLASH" not in data
    assert "TIF" not in data
    # Derived values read as reference: the R column and the station radii.
    assert notes_text.startswith("R (REF)")
    assert all(
        text.startswith("(R")
        for text, _xy in drawing.form_plot_labels()
        if text.lstrip("(").startswith("R.")
    )
    assert "INSPECT" not in data and "TOOL" not in data and "GRIND" not in data
    zones = [text for text, _xy, _tip in drawing.form_zone_labels()]
    assert zones == [
        "ROOT ARC R.0433, P1-P2",
        "STRAIGHT LINES P2-P12",
        "INVOLUTE, BASE R.0587, P12-P17",
    ]
    points = family.custom_six_form_points_mm()
    assert table[1:] == [
        (
            f"P{number}",
            spec.inch_text(r, drawing.FORM_PLACES),
            spec.inch_text(x, drawing.FORM_PLACES),
            spec.inch_text(y, drawing.FORM_PLACES),
        )
        for number, (r, x, y) in enumerate(points, 1)
    ]
    root = template.root_radius_mm
    assert points[0] == (root, 0.0, 0.0)
    assert points[-1][0] == profile.blank_radius_mm
    for number in re.findall(r"\d*\.\d+", data):
        assert len(number.split(".")[1]) == 4, number
    # Title over the table, the rows, then the notes, above the title block.
    assert drawing.FORM_TITLE_POS[1] - NOTE_LINE > drawing.FORM_TABLE_POS[1]
    table_bottom = (
        drawing.FORM_TABLE_POS[1] - len(table) * drawing.FORM_TABLE_ROW_HEIGHT
    )
    notes_x, notes_y = drawing.form_notes_pos()
    assert notes_x == drawing.FORM_TABLE_POS[0] and notes_y < table_bottom - 0.002
    assert notes_y - len(notes_text.splitlines()) * NOTE_LINE > 0.100
    for row in table:
        for text, width in zip(row, drawing.FORM_TABLE_COLUMN_WIDTHS, strict=True):
            assert len(text) * NOTE_CHAR + 0.002 < width, text


# A DETAIL B tag's native extent as the layout audit read it (round 7 of the
# cone family's fan-out): the text from 0.4 mm left of and 0.2 mm over its
# top-left point, 1.8 mm a character, down 3.4 mm, joined with the landing.
_TAG_LEFT, _TAG_TOP, _TAG_CHAR, _TAG_DEPTH = 0.0004, 0.0002, 0.0018, 0.0034
_TAG_CLEAR = 0.002


def _tag_text_box(
    text: str, xy: tuple[float, float]
) -> tuple[float, float, float, float]:
    left, top = xy
    return (
        left - _TAG_LEFT,
        top - _TAG_DEPTH,
        left + len(text) * _TAG_CHAR,
        top + _TAG_TOP,
    )


def _tag_native_box(
    text: str, xy: tuple[float, float], tip: tuple[float, float]
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = _tag_text_box(text, xy)
    return (min(x0, tip[0]), min(y0, tip[1]), max(x1, tip[0]), max(y1, tip[1]))


def _tag_overlaps(boxes, clear: float) -> set[frozenset[str]]:
    found = set()
    for index, (text, _box, native, _tip) in enumerate(boxes):
        for other, _other_box, other_native, _ in boxes[index + 1 :]:
            if not (
                native[2] + clear <= other_native[0]
                or other_native[2] + clear <= native[0]
                or native[3] + clear <= other_native[1]
                or other_native[3] + clear <= native[1]
            ):
                found.add(frozenset((text, other)))
    return found


def test_tag_box_model_reproduces_the_round_7_overlaps() -> None:
    """Positive control for the tag box model: the family's round-7 offsets
    give the audit's three overlaps."""
    round_7 = {
        1: ("P1 (X0 Y0)", (0.010, -0.012)),
        2: ("P2", (0.002, -0.0037)),
        12: ("P12", (-0.011, 0.005)),
        13: ("P13", (-0.010, 0.007)),
        14: ("P14", (-0.012, 0.007)),
        15: ("P15", (-0.012, 0.007)),
        16: ("P16", (-0.011, 0.007)),
        17: ("P17", (-0.011, 0.0075)),
    }
    points = family.custom_six_form_points_mm()
    boxes = []
    for number, (text, (dx, dy)) in round_7.items():
        _r, x, y = points[number - 1]
        tip = drawing.form_plot_xy(x, y)
        boxes.append(
            (text, None, _tag_native_box(text, (tip[0] + dx, tip[1] + dy), tip), tip)
        )
    assert _tag_overlaps(boxes, 0.0) == {
        frozenset(("P1 (X0 Y0)", "P2")),
        frozenset(("P12", "P13")),
        frozenset(("P15", "P16")),
    }


def test_tooth_space_plot_stands_beside_the_table() -> None:
    source = "".join(inspect.getsource(drawing.build).split())
    assert '"*Front",*CUTTER_SOURCE_VIEW_CENTER' in source
    assert "_hide_title_block_source(adapter,source_view)" in source
    assert "_draw_form_plot(adapter)" in source
    flank = drawing.form_plot_flank_mm()
    rows = family.custom_six_form_points_mm()
    junction = family.stock_form_profile(6).template.relief_junction_radius_mm
    relief = [(x, y) for radius, x, y in rows[1:] if radius <= junction + 1e-9]
    assert flank[: len(relief)] == relief
    assert flank[-1] == pytest.approx(rows[-1][1:], abs=1.5e-3)
    texts = [drawing.form_sheet_title(), *drawing.form_sheet_notes().splitlines()]
    table_right = max(
        drawing.FORM_TABLE_POS[0] + sum(drawing.FORM_TABLE_COLUMN_WIDTHS),
        drawing.FORM_TITLE_POS[0] + max(map(len, texts)) * NOTE_CHAR,
    )
    plotted = [drawing.form_plot_xy(side * x, y) for x, y in flank for side in (1, -1)]
    boxes = []
    for text, (left, top) in drawing.form_plot_labels():
        width = max(map(len, text.splitlines())) * 0.0026
        box = (left, top - 0.0046 * len(text.splitlines()), left + width, top)
        boxes.append((text, box, box, None))
    for text, xy, tip in (*drawing.form_point_tags(), *drawing.form_zone_labels()):
        boxes.append(
            (text, _tag_text_box(text, xy), _tag_native_box(text, xy, tip), tip)
        )
    for _text, _box, (x0, y0, x1, y1), _tip in boxes:
        plotted += [(x0, y0), (x1, y1)]
    xs, ys = zip(*plotted)
    assert min(xs) > table_right + 0.020
    assert max(xs) < 0.415
    assert min(ys) > 0.070 and max(ys) < 0.262
    assert not _tag_overlaps(boxes, _TAG_CLEAR)
    for text, (x0, y0, x1, y1), _native, tip in boxes:
        if tip is None:
            continue
        start = (min(max(tip[0], x0), x1), (y0 + y1) / 2.0)
        leader = Segment(*start, *tip)
        for other, other_box, _native_other, _ in boxes:
            if other != text:
                assert segment_box_distance(leader, Box(*other_box)) > 0.0005, (
                    text,
                    other,
                )
    tagged = {int(text[1:]) for text, _xy, _tip in drawing.form_point_tags()}
    root_end, junction_row = drawing.form_zones()
    assert {1, root_end, junction_row, len(rows)} <= tagged


# The lengths and the overall print at the title block's places with no
# band of their own (``.25``, ``(1.23)``); every other value carries a
# stacked band (``.0625 +.0000/-.0010``).
_UNBANDED = {"PivotLength", "SpigotLength", "overall"}


def _dimension_box(name: str, center: tuple[float, float]) -> Box:
    """A dimension's text block centred on its point: the value row (with a
    stacked band), its callout rows and its above-text row."""
    lines = notes.DIMENSION_CALLOUTS.get(name, "").splitlines()
    above = [notes.CALLOUTS_ABOVE[name]] if name in notes.CALLOUTS_ABOVE else []
    value = 6 if name in _UNBANDED else 14
    width = max([value, *map(len, (*lines, *above))]) * DIM_CHAR
    height = (1.0 if name in _UNBANDED else 1.5) * DIM_ROW
    height += (len(lines) + len(above)) * DIM_ROW
    return Box(
        center[0] - width / 2.0,
        center[1] - height / 2.0,
        center[0] + width / 2.0,
        center[1] + height / 2.0,
    )


def _overlaps(a: Box, b: Box, clear: float = 0.002) -> bool:
    return not (
        a.xmax + clear <= b.xmin
        or b.xmax + clear <= a.xmin
        or a.ymax + clear <= b.ymin
        or b.ymax + clear <= a.ymin
    )


def test_sheet_one_blocks_stand_apart_and_inside_the_border() -> None:
    """The lathe view runs pivot (left) to spigot (right), diameters above,
    lengths below; neither the dimension blocks nor the part reach the notes,
    Gear Data, the isometric, the front view's shelf or the title block."""
    assert drawing.PIVOT_END_X < drawing.LEAVES_NORTH_X < drawing.LEAVES_SOUTH_X
    assert drawing.LEAVES_SOUTH_X < drawing.SPIGOT_END_X
    assert drawing.SIDE_ORIGIN[1] == drawing.FRONT_CENTER[1] == drawing.AXIS_Y
    half = drawing.HALF_OD
    part = Box(
        drawing.PIVOT_END_X,
        drawing.AXIS_Y - half,
        drawing.SPIGOT_END_X,
        drawing.AXIS_Y + half,
    )
    front = Box(
        drawing.FRONT_CENTER[0] - half,
        drawing.AXIS_Y - half,
        drawing.FRONT_CENTER[0] + half,
        drawing.AXIS_Y + half,
    )
    shelf_x, shelf_y = drawing.tooth_thickness_shelf()
    shelf = Box(shelf_x, shelf_y, shelf_x + 0.065, shelf_y + 0.025)
    sheet_notes = notes.sheet_notes().splitlines()
    numbered = Box(
        drawing.NUMBERED_NOTES_POS[0],
        drawing.NUMBERED_NOTES_POS[1] - len(sheet_notes) * NOTE_LINE,
        drawing.NUMBERED_NOTES_POS[0] + max(map(len, sheet_notes)) * NOTE_CHAR,
        drawing.NUMBERED_NOTES_POS[1],
    )
    data = notes.gear_data().splitlines()
    gear_data = Box(
        drawing.GEAR_DATA_POS[0],
        drawing.GEAR_DATA_POS[1] - len(data) * NOTE_LINE,
        drawing.GEAR_DATA_POS[0] + max(map(len, data)) * NOTE_CHAR,
        drawing.GEAR_DATA_POS[1],
    )
    # The isometric at 2:1: the part's length and tip both foreshortened.
    iso_half = (
        spec.OVERALL_LENGTH_MM * drawing.ISO_SCALE[0] / 1000.0 * 0.82 / 2.0 + 0.0055
    )
    iso = Box(
        drawing.ISO_CENTER[0] - iso_half,
        drawing.ISO_CENTER[1] - iso_half * 0.6,
        drawing.ISO_CENTER[0] + iso_half,
        drawing.ISO_CENTER[1] + iso_half * 0.6,
    )
    blocks = {name: _dimension_box(name, xy) for name, xy in drawing.SIDE_KEEP.items()}
    blocks["overall"] = _dimension_box("overall", drawing.OVERALL_TEXT_XY)
    fixed = {
        "side view": part,
        "front view": front,
        "thickness shelf": shelf,
        "notes": numbered,
        "gear data": gear_data,
        "isometric": iso,
    }
    items = {**fixed, **blocks}
    names = list(items)
    for index, name in enumerate(names):
        box = items[name]
        assert BORDER[0] < box.xmin and box.xmax < BORDER[2], name
        assert BORDER[1] < box.ymin and box.ymax < BORDER[3], name
        if box.xmax > TITLE_BLOCK[0]:
            assert box.ymin > TITLE_BLOCK[3] + 0.002, name
        for other in names[index + 1 :]:
            assert not _overlaps(box, items[other]), (name, other)


def test_registered_as_a_landscape_part_drawing() -> None:
    row = DRAWINGS_BY_NAME["dt_cone_tip_gear"]
    assert row.part == "dt_cone_tip_gear"
    assert row.artifact_stem == spec.PART_NAME
    assert row.script_name == Path(drawing.__file__).name
    assert drawing.MACHINIST_REVIEW.name == "ENFORCE"
    assert drawing.SHEET_SCALES == {"T006": (6.0, 1.0), "DT6-FORM1": (1.0, 1.0)}
    # Sheet 2's DETAIL B is the 12 o'clock tooth space of sheet 1's front view.
    detail = drawing.form_detail()
    assert detail.centre_mm[0] == 0.0
    assert detail.radius_mm < spec.OUTSIDE_DIA / 2.0
    assert drawing.form_plot_label() == "DETAIL B (SHEET 1)\nSCALE 75 : 1"
    assert math.isclose(drawing.RATIO, 6.0)

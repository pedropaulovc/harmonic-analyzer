"""Offline contracts for the amplitude-bar drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import ch_amplitude_bar_notes
import ch_amplitude_bar_spec
import draw_ch_amplitude_bar as drawing
import build_ch_amplitude_bar as bar
from _drawing_registry import DRAWINGS_BY_NAME
from _config import parts
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _printed_tolerance import printed_deviations

OWNER_THIN_WALL_RULING = (
    "Owner ruling 2026-11-01: thin walls above the .060 floor but under the"
    " .080 target, with no geometry escape, are accepted as package-specific"
    " minor exceptions."
)


def _exception(rv: str) -> dict[str, str]:
    (row,) = [
        row
        for row in parts("ch-amplitude-bar")["machinist_exceptions"]
        if row["id"] == rv
    ]
    return row


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-amplitude-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-amplitude-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-amplitude-bar_drawing.png")
    assert DRAWINGS_BY_NAME["ch_amplitude_bar"].script == Path(drawing.__file__).resolve()


def test_notes_module_is_the_single_source_of_the_marked_dimension_set() -> None:
    """The drawing contract lives in ch_amplitude_bar_notes, out of the spec's
    import closure (the channel kinematics, rocker arm and both pins import
    the spec), so a sheet edit re-keys only the bar."""
    notes = ch_amplitude_bar_notes
    assert bar.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert bar.DRAWING_PRECISION is notes.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert drawing.DRAWING_PRECISION_BY_NAME is notes.DRAWING_PRECISION_BY_NAME
    for name in ("DRAWING_DIMENSIONS", "DRAWING_PRECISION", "DRAWING_NOTES"):
        assert not hasattr(ch_amplitude_bar_spec, name), name
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    keeps = (
        drawing.FRONT_KEEP,
        drawing.DETAIL_A_KEEP,
        drawing.DETAIL_B_KEEP,
        drawing.TOP_SIDE_KEEP,
    )
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(len(keep) for keep in keeps) == len(marked)  # one view each
    assert set(notes.DRAWING_PRECISION_BY_NAME) == marked


def test_part_geometry_matches_the_spec() -> None:
    assert ch_amplitude_bar_spec.BAR_LENGTH == bar.BAR_LENGTH
    assert ch_amplitude_bar_spec.BAR_WIDTH == bar.BAR_WIDTH
    assert bar.TOP_PIN_HOLE_DIA is ch_amplitude_bar_spec.TOP_PIN_HOLE_DIA
    assert bar.TOP_PIN_HOLE_BAND is ch_amplitude_bar_spec.TOP_PIN_HOLE_BAND
    assert bar.BAR_DEPTH == ch_amplitude_bar_spec.BAR_DEPTH


def test_top_pin_hole_is_the_reamed_press_hole_for_the_bar_pivot_pin() -> None:
    """User ruling 2026-10: the MHA-CH-11 pin is pressed into both top-notch
    cheeks (ch_bar_pivot_pin_spec holds the fit), so the hole is reamed to a
    band of its own, native on TopPinDia. Machinist round 1 (#1293): the hole
    was only words in a note; it now prints in the top end's right side view,
    its THRU / REAM / PRESS FIT callout at the diameter."""
    from _drawing_contract import model_toleranced_dimensions

    notes = ch_amplitude_bar_notes
    assert ch_amplitude_bar_spec.TOP_PIN_HOLE_DIA == 1.9558
    assert ch_amplitude_bar_spec.TOP_PIN_HOLE_BAND == (0.02286, 0.0127)
    assert model_toleranced_dimensions(bar)[("TopPinProfile", "TopPinDia")] == (
        "*deviations(TOP_PIN_HOLE_BAND)"
    )
    assert notes.TOP_PIN_NUMBER == parts("ch-bar-pivot-pin")["number"]
    assert notes.DRAWING_DIMENSIONS["TopPinProfile"] == {
        "BarSection",
        "TopPinX",
        "TopPinDrop",
        "TopPinDia",
    }
    assert set(drawing.TOP_SIDE_KEEP) == notes.DRAWING_DIMENSIONS["TopPinProfile"]
    assert notes.DIMENSION_CALLOUTS["TopPinDia"] == "THRU, REAM\nPRESS FIT MHA-CH-11"
    precision = notes.DRAWING_PRECISION["TopPinProfile"]
    assert precision == {"BarSection": 2, "TopPinX": 3, "TopPinDrop": 2, "TopPinDia": 4}
    # Machinist round 1: the three-place location states its function, the
    # hole's worst-case face wall, which the pin's joint budget holds too:
    # .125 +/-.005 on the narrowest stock leaves the far wall .079, over the
    # .060 floor and under the .080 target (RV-06).
    import ch_bar_pivot_pin_spec as pin

    assert notes.DIMENSION_CALLOUTS["TopPinX"] == "HOLE WALL .079 MIN"
    wall = pin.BUDGET["hole_face_wall_min"]
    assert notes.PIN_HOLE_WALL_MIN == pytest.approx(0.079 * 25.4)
    assert notes.PIN_HOLE_WALL_MIN <= wall < notes.PIN_HOLE_WALL_MIN + 0.0254
    assert WALL_FLOOR_MM <= wall < WALL_TARGET_MM
    row = _exception("RV-06")
    assert row["kind"] == "minor"
    assert row["reason"].startswith(OWNER_THIN_WALL_RULING)
    assert "HOLE WALL .079 MIN" in row["where"]
    assert "TopPinX location .125 under HOLE WALL .079 MIN" in _exception("RV-03")["where"]


def test_pin_hole_is_a_native_sketch_located_from_the_top_edge() -> None:
    """The hole's sketch carries a construction line along the bar's top edge:
    the hole is located from its back end, and its length is the section, all
    model dimensions (rule 21)."""
    source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "define_circle" not in source
    for record in (
        "pin_hole.record(\"TopEdgeY\", '\"BarLength\"')",
        "pin_hole.record(\"BarSection\", '\"BarDepth\"')",
        "pin_hole.record(\"TopPinX\", '\"BarDepth\" / 2')",
        "pin_hole.record(\"TopPinDrop\", '\"TopPinDrop\"')",
        "pin_hole.record(\"TopPinDia\", '\"TopPinDia\"')",
    ):
        assert record in source, record
    assert 'drive_jobs += pin_hole.apply(adapter, "TopPinProfile")' in source
    assert "TopEdgeY" not in ch_amplitude_bar_notes.DRAWING_PRECISION_BY_NAME


def test_square_section_prints_as_stock_reference() -> None:
    """Machinist round 1 (#1293): the 1/4 square lived only in a note. It
    prints in the top end's right side view as the stock's reference size."""
    notes = ch_amplitude_bar_notes
    assert notes.REFERENCE_DIMENSIONS == frozenset({"BarSection"})
    assert notes.DIMENSION_CALLOUTS["BarSection"] == "1/4 SQ STOCK"
    assert ch_amplitude_bar_spec.BAR_DEPTH == ch_amplitude_bar_spec.BAR_WIDTH == 6.35
    assert ch_amplitude_bar_notes.inch_text(ch_amplitude_bar_spec.BAR_DEPTH, 2) == ".25"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_reference_dimension(" in source
    config = parts("ch-amplitude-bar")
    assert "1/4 in sq" in config["material"]
    assert len(str(config["material"])) <= 36
    # Rule 2: nothing on the bar needs one grade, so the field names the
    # stock family (machinist review, 3de09b9).
    assert "1018" not in config["material"]


def test_views_are_the_full_length_and_enlarged_cropped_ends() -> None:
    """Machinist round 1 (#1293): the 1:8 isometric was an unreadable sliver
    labelled far away, and the 4:1 end view repeated the section. The sheet
    runs at 1:4; each end prints enlarged in cropped model views, each owning
    its label."""
    assert drawing.SHEET_SCALE == (1.0, 4.0)
    views = {view.name: view for view in drawing.CROPPED_VIEWS}
    assert {(v.orientation, v.scale) for v in views.values()} == {
        ("*Front", (4, 1)),
        ("*Right", (4, 1)),
        ("*Isometric", (3, 1)),
    }
    assert [v.letter for v in drawing.CROPPED_VIEWS if v.letter] == ["A", "B"]
    assert drawing.TOP_SIDE.centre[1] == drawing.DETAIL_B.centre[1]  # its row
    assert drawing.TOP_SIDE.fence_mm[1] == drawing.DETAIL_B.fence_mm[1]
    for view in drawing.CROPPED_VIEWS:
        assert view.label_text == (
            f"{view.title}\nSCALE {view.scale[0]} : {view.scale[1]}"
        )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"*Top"' not in source
    assert "View Note" not in source
    assert "View Note" not in Path(bar.__file__).read_text(encoding="utf-8")
    assert not hasattr(ch_amplitude_bar_notes, "ISOMETRIC_VIEW_NOTE")
    assert not hasattr(ch_amplitude_bar_notes, "END_VIEW_NOTE")


def test_callouts_name_each_mate_at_its_dimension() -> None:
    """Rule 4: each mating feature names its mate where it is dimensioned."""
    notes = ch_amplitude_bar_notes
    assert notes.LEVER_NUMBER == parts("ch-channel-lever")["number"]
    assert notes.ROCKER_ARM_NUMBER == parts("ch-rocker-arm")["number"]
    callouts = notes.DIMENSION_CALLOUTS
    assert callouts["TopNotchWidth"].startswith("STRADDLES MHA-CH-02\n")
    assert callouts["BottomNotchWidth"].startswith("RIDES MHA-CH-06\n")
    assert callouts["TopRightLedge"] == "CENTRES ON LEVER"
    assert callouts["BottomLeftLedge"] == "CENTRES ON ROCKER"
    assert callouts["TopNotchHeight"] == "ROOTS R.015 MAX"
    # Machinist r5: the foot depth's shallow-only band names its mate.
    assert callouts["BottomNotchHeight"] == "SITS ON MHA-CH-06"
    assert callouts["BottomNotchWidth"].endswith("\nROOTS R.015 MAX")
    assert drawing.CALLOUTS_ABOVE <= set(callouts)
    for text in callouts.values():
        assert all(len(line) <= 20 for line in text.splitlines()), text
    # r1 (64ebba372): SOLIDWORKS printed nothing of the two-line callout set
    # above TopNotchWidth; a callout over its value is one line.
    for name in drawing.CALLOUTS_ABOVE:
        assert "\n" not in callouts[name], name
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("set_dimension_callouts(") == 2


def test_cheek_walls_state_their_worst_case_at_each_width() -> None:
    """Rule 20 (#1038): the cheek opposite each printed ledge, on the
    narrowest stock beside the widest notch and ledge, falls short of the .060
    floor (RV-04, owner-approved 2026-10-15). The shortfall prints at the
    notch's width, at three inch places rounded down."""
    spec = ch_amplitude_bar_spec
    notes = ch_amplitude_bar_notes
    assert spec.BAR_STOCK_UNDERSIZE == pytest.approx(0.0508)
    for width, (upper, _lower), ledge, printed, name in (
        (
            spec.TOP_NOTCH_WIDTH,
            spec.TOP_NOTCH_WIDTH_BAND,
            spec.TOP_NOTCH_OFFSET,
            notes.TOP_CHEEK_WALL_MIN,
            "TopNotchWidth",
        ),
        (
            spec.BOTTOM_NOTCH_WIDTH,
            spec.BOTTOM_NOTCH_WIDTH_BAND,
            spec.BOTTOM_NOTCH_OFFSET,
            notes.BOTTOM_CHEEK_WALL_MIN,
            "BottomNotchWidth",
        ),
    ):
        wall = (
            spec.BAR_WIDTH
            - spec.BAR_STOCK_UNDERSIZE
            - (ledge + spec.NOTCH_OFFSET_TOLERANCE_MM)
            - (width + upper)
        )
        assert printed <= wall + 1e-9 < printed + 0.0254
        assert printed < WALL_FLOOR_MM
        text = notes.inch_text(printed, notes.WALL_PLACES)
        assert f"CHEEK WALL {text} MIN" in notes.DIMENSION_CALLOUTS[name].splitlines()
    # .124 notches beside .063 +/-.002 ledges in .250 -.002 stock: the top's
    # +.007 leaves .052, the foot's +.010 .049.
    assert (notes.TOP_CHEEK_WALL_MIN, notes.BOTTOM_CHEEK_WALL_MIN) == pytest.approx(
        (0.052 * 25.4, 0.049 * 25.4)
    )
    # Owner ruling 2026-10-15: approved exceptions at 1.17 mm (top), 1.21 mm
    # (foot); the inch walls stay at or above them.
    assert notes.CHEEK_WALL_APPROVED_MIN == {"top": 1.17, "bottom": 1.21}
    assert notes.TOP_CHEEK_WALL_MIN >= notes.CHEEK_WALL_APPROVED_MIN["top"]
    assert notes.BOTTOM_CHEEK_WALL_MIN >= notes.CHEEK_WALL_APPROVED_MIN["bottom"]
    assert "1.17 mm (.046)" in _exception("RV-04")["reason"]
    assert ".052 and .049" in _exception("RV-04")["reason"]


def test_ledge_cheeks_hold_the_floor_under_the_target() -> None:
    """The near cheek is the printed ledge: .063 +/-.002 leaves .061, over the
    .060 floor and under the .080 target (RV-05, owner ruling 2026-11-01)."""
    spec = ch_amplitude_bar_spec
    notes = ch_amplitude_bar_notes
    assert spec.TOP_NOTCH_OFFSET == pytest.approx(0.063 * 25.4)
    assert spec.BOTTOM_NOTCH_OFFSET == pytest.approx(0.063 * 25.4)
    assert notes.LEDGE_CHEEK_MIN == pytest.approx(0.061 * 25.4)
    assert WALL_FLOOR_MM <= notes.LEDGE_CHEEK_MIN < WALL_TARGET_MM
    row = _exception("RV-05")
    assert row["kind"] == "minor"
    assert row["reason"].startswith(OWNER_THIN_WALL_RULING)
    assert ".063 \u00b1.002" in row["where"] and ".061" in row["finding"]
    assert "\u00b1.002" in _exception("RV-02")["where"]


def test_bottom_notch_depth_band_is_native_on_its_dimension() -> None:
    """User ruling 2026-09-26: a deep notch drops the cheeks onto the rocker
    hub one for one, so the depth may only come out shallow. Codex #936
    PRRT_kwDOPHDy386mWF0L, drawing-simplicity-policy.md `How the repository implements the guidelines`: that band is the part's, native on
    BottomNotchHeight from the one constant the cheek-over-hub test reads,
    printed in DETAIL A -- and no note carries it or any notch size."""
    from _drawing_contract import model_toleranced_dimensions

    upper, lower = ch_amplitude_bar_spec.BOTTOM_NOTCH_DEPTH_BAND
    assert lower == pytest.approx(-0.020 * 25.4) and upper == 0.0
    assert not hasattr(ch_amplitude_bar_notes, "BOTTOM_NOTCH_DEPTH_BAND")
    assert model_toleranced_dimensions(bar)[("BarProfile", "BottomNotchHeight")] == (
        "*deviations(BOTTOM_NOTCH_DEPTH_BAND)"
    )
    assert "BottomNotchHeight" in drawing.DETAIL_A_KEEP
    assert not hasattr(ch_amplitude_bar_notes, "DRAWING_NOTES")


# Each printed dimension's two sketch references, in the part (x, y, z) mm: a
# crop drops any dimension whose reference lies outside its fence.
_W = ch_amplitude_bar_spec.BAR_WIDTH
_D = ch_amplitude_bar_spec.BAR_DEPTH
_O = (_W - ch_amplitude_bar_spec.BOTTOM_NOTCH_WIDTH) / 2.0  # bottom ledge
_OT = (_W - ch_amplitude_bar_spec.TOP_NOTCH_WIDTH) / 2.0  # top ledge
_L = ch_amplitude_bar_spec.BAR_LENGTH
_PIN = (_W, _L - ch_amplitude_bar_spec.TOP_PIN_DROP, _D / 2.0)  # on the x = W face
_HOLE_R = ch_amplitude_bar_spec.TOP_PIN_HOLE_DIA / 2.0
_DIMENSION_ENDS = {
    "BottomLeftLedge": ((0.0, 0.0, 0.0), (_O, 0.0, 0.0)),
    "BottomNotchHeight": (
        (_O, 0.0, 0.0),
        (_O, ch_amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT, 0.0),
    ),
    "BottomNotchWidth": (
        (_O, ch_amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT, 0.0),
        (_W - _O, ch_amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT, 0.0),
    ),
    "TopRightLedge": ((_W, _L, 0.0), (_W - _OT, _L, 0.0)),
    "TopNotchHeight": (
        (_W - _OT, _L, 0.0),
        (_W - _OT, _L - ch_amplitude_bar_spec.TOP_NOTCH_HEIGHT, 0.0),
    ),
    "TopNotchWidth": (
        (_W - _OT, _L - ch_amplitude_bar_spec.TOP_NOTCH_HEIGHT, 0.0),
        (_OT, _L - ch_amplitude_bar_spec.TOP_NOTCH_HEIGHT, 0.0),
    ),
    "BarSection": ((_W, _L, 0.0), (_W, _L, _D)),
    "TopPinX": ((_W, _L, 0.0), _PIN),
    "TopPinDrop": ((_W, _L, 0.0), _PIN),
    "TopPinDia": (
        (_W, _PIN[1] + _HOLE_R, _PIN[2]),
        (_W, _PIN[1] - _HOLE_R, _PIN[2]),
    ),
}
_KEEPS = (
    (drawing.DETAIL_A, drawing.DETAIL_A_KEEP),
    (drawing.DETAIL_B, drawing.DETAIL_B_KEEP),
    (drawing.TOP_SIDE, drawing.TOP_SIDE_KEEP),
)


def test_cropped_views_frame_their_ends_and_place_text_outside_the_bar() -> None:
    """Every printed dimension's references lie inside its view's fence; each
    depth's text stands outside the bar's side and each ledge/width row
    outside its open end, where the witnesses run through air."""
    spec = ch_amplitude_bar_spec
    a, b, side = drawing.DETAIL_A, drawing.DETAIL_B, drawing.TOP_SIDE
    for view, keep in _KEEPS:
        fx, fy, fz = view.fence_mm
        for name in keep:
            for x, y, z in _DIMENSION_ENDS[name]:
                across = x - fx if view.orientation == "*Front" else z - fz
                assert math.hypot(across, y - fy) < view.radius_mm - 0.5, name
    depth_x, depth_y = drawing.DETAIL_A_KEEP["BottomNotchHeight"]
    assert depth_x < a.centre[0] - a.radius_mm * a.mm  # left of the fence
    # Over the floor's witness, outside the span: r1 printed the ROOTS line
    # on that witness with the text inside it.
    floor_y = a.sheet_xy(0.0, spec.BOTTOM_NOTCH_HEIGHT)[1]
    assert depth_y - 1.5 * _LINE > floor_y
    # Its stack (band, value, mate line) stays under DETAIL B's label.
    assert depth_y + 3.0 * _LINE < b.label_xy[1] - 2 * _LINE - 0.004
    # r743-6b (64fedd3cc): a width with its +0.3/0.0 stack prints ~20 mm
    # wide; centred on the ~12.4 mm mouth it straddled both extension lines.
    # Each width's text stands west of the bar, clear of it.
    ledge_x, ledge_y = drawing.DETAIL_A_KEEP["BottomLeftLedge"]
    width_x, width_y = drawing.DETAIL_A_KEEP["BottomNotchWidth"]
    assert width_y < ledge_y < a.sheet_xy(0.0, 0.0)[1]
    # The ledge's stack half-height, its one-line callout under it, and the
    # width stack's half-height.
    assert ledge_y - width_y >= 0.014
    callouts = ch_amplitude_bar_notes.DIMENSION_CALLOUTS
    # Each west text block (its widest callout line) ends short of the bar's
    # edge, where the ledge's and the depth's witnesses stand (r1: both ran
    # through their own text). The depth's text, outside its vertical span,
    # hangs west of its dimension line (r2): that line stands short of the
    # bar and the block clears the front view's bar (r2: ROOTS printed on it).
    bar_left = a.sheet_xy(0.0, 0.0)[0]
    front_bar_right = drawing.FRONT_CENTER[0] + spec.BAR_WIDTH / 4000.0
    for name, (x, _y) in drawing.DETAIL_A_KEEP.items():
        width = max(map(len, callouts[name].splitlines())) * _CHAR
        if name == "BottomNotchHeight":
            assert x + 0.002 < bar_left, name
            assert x - width > front_bar_right + 0.004, name
        else:
            assert x + width / 2 + 0.002 < bar_left, name
    assert ledge_x < bar_left
    # The width's right witness runs down to its row; DETAIL A's label stands
    # east of it (r1: the centred label stood in its path).
    right_wall = a.sheet_xy(_W - _O, 0.0)[0]
    label_w = max(len(line) for line in a.label_text.splitlines()) * _CHAR
    assert a.label_xy[0] - label_w / 2 > right_wall + 0.002
    # The top depth's ~36 mm ROOTS callout hangs clear of the bar.
    assert (
        drawing.DETAIL_B_KEEP["TopNotchHeight"][0] - 0.019
        > b.sheet_xy(spec.BAR_WIDTH, 0.0)[0]
    )
    top_row = {drawing.DETAIL_B_KEEP[n][1] for n in ("TopRightLedge", "TopNotchWidth")}
    (row_y,) = top_row
    assert row_y > b.sheet_xy(0.0, spec.BAR_LENGTH)[1]
    half = max(map(len, callouts["TopNotchWidth"].splitlines())) * _CHAR / 2
    assert drawing.DETAIL_B_KEEP["TopNotchWidth"][0] + half + 0.002 < b.sheet_xy(0.0, 0.0)[0]
    # r6: the ledge's value and callout clear the bar's right-face witness.
    ledge_half = len(callouts["TopRightLedge"]) * _CHAR / 2
    assert (
        drawing.DETAIL_B_KEEP["TopRightLedge"][0] - ledge_half
        > b.sheet_xy(spec.BAR_WIDTH, 0.0)[0] + 0.0015
    )
    # The side view: +Z runs left, so the back face (z = 0) is its right edge.
    back_x = side.sheet_xy(0.0, 0.0, 0.0)[0]
    front_x = side.sheet_xy(0.0, 0.0, _D)[0]
    end_y = side.sheet_xy(0.0, _L, 0.0)[1]
    assert front_x < back_x
    pin_x, pin_y = side.sheet_xy(0.0, _PIN[1], _PIN[2])
    assert pin_x == pytest.approx(side.centre[0] + (side.fence_mm[2] - _PIN[2]) * side.mm)
    keep = drawing.TOP_SIDE_KEEP
    # Outside the back face's witness, which the section shares (r1: inside
    # the 12.7 mm span the text stood 0.7 mm from it).
    wall_half = len(ch_amplitude_bar_notes.DIMENSION_CALLOUTS["TopPinX"]) * _CHAR / 2
    assert keep["TopPinX"][0] - wall_half > back_x + 0.002
    assert pin_x < back_x
    # The section's arrows run 5.6 mm under its text point; the HOLE WALL
    # line tops 4.5 mm over TopPinX's. r2 left 2.0 mm between them.
    assert end_y < keep["TopPinX"][1] < keep["BarSection"][1] - 0.015
    assert keep["TopPinDrop"][0] > back_x and pin_y < keep["TopPinDrop"][1] < end_y
    assert keep["TopPinDia"][0] > back_x and keep["TopPinDia"][1] < pin_y


def _box(
    centre: tuple[float, float], half_w: float, top: float, bottom: float
) -> tuple[float, float, float, float]:
    return (centre[0] - half_w, bottom, centre[0] + half_w, top)


def _overlap(p: tuple[float, ...], q: tuple[float, ...]) -> bool:
    return p[0] < q[2] and q[0] < p[2] and p[1] < q[3] and q[1] < p[3]


# ~2.6 mm a character and ~5.2 mm a line at the sheet's text height, measured
# on the r1 PDF (CHEEK WALL 1.21 MIN 48.8 mm; the width block's rows 5.2 mm apart).
_CHAR = 0.0026
_LINE = 0.0052


def test_views_labels_and_notes_stay_on_the_sheet_and_apart() -> None:
    """Each crop circle with its label stands on the
    sheet (border 0.0127..0.419 x 0.0127..0.2667), clear of the title block
    (x >= 0.216 below y 0.065) and of one another."""
    boxes = {}
    for view in drawing.CROPPED_VIEWS:
        r = view.crop_radius
        label_w = max(len(line) for line in view.label_text.splitlines()) * _CHAR
        label_bottom = view.label_xy[1] - 2 * _LINE
        boxes[view.name] = (
            min(view.centre[0] - r, view.centre[0] - label_w / 2),
            label_bottom,
            max(view.centre[0] + r, view.centre[0] + label_w / 2),
            view.centre[1] + r,
        )
    title_block = (0.216, 0.0, 0.419, 0.065)
    for name, box in boxes.items():
        assert 0.0127 < box[0] and box[2] < 0.419, name
        assert 0.0127 < box[1] and box[3] < 0.2667, name
        assert not _overlap(box, title_block), name
    names = sorted(boxes)
    for i, p in enumerate(names):
        for q in names[i + 1 :]:
            assert not _overlap(boxes[p], boxes[q]), (p, q)
    # The front view's length text stands left of the bar, on the sheet.
    assert 0.0127 + 0.008 < drawing.FRONT_KEEP["BarLength"][0] < drawing.FRONT_CENTER[0]


def test_callouts_clear_the_bar_and_the_neighbouring_views() -> None:
    """Each callout block (value plus callout lines, centred on the value)
    stays off the bar in its view and off the other views' circles."""
    spec = ch_amplitude_bar_spec
    b, side = drawing.DETAIL_B, drawing.TOP_SIDE
    callouts = ch_amplitude_bar_notes.DIMENSION_CALLOUTS
    bar_b = (
        b.sheet_xy(0.0, 0.0)[0],
        b.sheet_xy(0.0, spec.BAR_LENGTH - 8.0)[1],
        b.sheet_xy(spec.BAR_WIDTH, 0.0)[0],
        b.sheet_xy(0.0, spec.BAR_LENGTH)[1],
    )
    blocks = {}
    for view, keep in _KEEPS:
        for name, (x, y) in keep.items():
            text = callouts.get(name, "")
            lines = text.splitlines()
            half_w = max([len(line) for line in lines] + [8]) * _CHAR / 2
            extra = len(lines) * _LINE
            if name in drawing.CALLOUTS_ABOVE:
                blocks[name] = _box((x, y), half_w, y + _LINE / 2 + extra, y - _LINE / 2)
            else:
                blocks[name] = _box((x, y), half_w, y + _LINE / 2, y - _LINE / 2 - extra)
    for name in ("TopNotchWidth", "TopRightLedge", "TopNotchHeight"):
        assert not _overlap(blocks[name], bar_b), name
    assert not _overlap(blocks["TopNotchWidth"], blocks["TopRightLedge"])
    names = sorted(blocks)
    for i, p in enumerate(names):
        for q in names[i + 1 :]:
            assert not _overlap(blocks[p], blocks[q]), (p, q)
    for name, block in blocks.items():
        assert block[3] < 0.2667 and block[0] > 0.0127, name
        for view in (drawing.TOP_ISO, drawing.FOOT_ISO):
            r = view.crop_radius
            circle = (view.centre[0] - r, view.centre[1] - r, view.centre[0] + r, view.centre[1] + r)
            assert not _overlap(block, circle), (name, view.name)
    side_r = side.crop_radius
    for name in ("TopNotchHeight", "TopRightLedge"):
        assert blocks[name][2] < side.centre[0] - side_r, name


def test_notch_centring_bands_ride_each_details_ledge_not_a_note() -> None:
    """Main ruling A(a) 2026-09-27 (Codex #936 PRRT_kwDOPHDy386mWF0L): the
    'CENTRED ON THE WIDTH WITHIN 0.10' note becomes a native +/-.002 on the
    NotchOffset ledge each detail prints."""
    from _drawing_contract import model_toleranced_dimensions

    assert ch_amplitude_bar_spec.NOTCH_OFFSET_TOLERANCE_MM == pytest.approx(0.002 * 25.4)
    assert ch_amplitude_bar_spec.BOTTOM_NOTCH_OFFSET == _O == bar.BOTTOM_NOTCH_OFFSET
    assert ch_amplitude_bar_spec.TOP_NOTCH_OFFSET == _OT == bar.TOP_NOTCH_OFFSET
    bands = model_toleranced_dimensions(bar)
    for name, keep in (
        ("BottomLeftLedge", drawing.DETAIL_A_KEEP),
        ("TopRightLedge", drawing.DETAIL_B_KEEP),
    ):
        assert bands[("BarProfile", name)] == "NOTCH_OFFSET_TOLERANCE_MM"
        assert name in keep
        assert ch_amplitude_bar_notes.DRAWING_PRECISION["BarProfile"][name] == 3


def test_sheet_carries_no_general_note() -> None:
    """Machinist round 1 (#1293): the section, the hole, the roots and the
    plating left the notes for their dimensions and the FINISH field. Round 2:
    the last line (both notches through, in one plane) repeated what the
    front view and the isometrics show, so the sheet has no note block."""
    assert not hasattr(ch_amplitude_bar_notes, "DRAWING_NOTES")
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    part_source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "add_property_linked_note" not in draw_source
    assert "Manufacturing Notes" not in draw_source
    assert "Manufacturing Notes" not in part_source
    assert "apply_drawing_properties(adapter, PART_NAME)" in part_source


def test_functional_notch_finish_is_a_native_symbol_on_the_floor() -> None:
    """Main ruling B 2026-09-27: the foot notch floor's finish is a native
    symbol on the floor in DETAIL A, authored on the part, not a note.
    Machinist round 1 (#1293) and drawing-simplicity-policy.md rule 6: the
    amplitude-bar slide grades machined 1.6 um (63 uin), not ground."""
    import ch_amplitude_bar_drawing_spec as finish_spec
    from _gtol_planar import PlanarFace
    from _surface_finish import MACHINED_UM, surface_finish_by_key

    control = surface_finish_by_key(finish_spec.SURFACE_FINISHES, "bottom_notch_floor")
    assert control.roughness_um == MACHINED_UM == 1.6
    assert control.display_unit == ch_amplitude_bar_spec.UNIT == "in"
    assert control.roughness_ra == "63"
    assert control.face == PlanarFace(
        (0, -1, 0), -ch_amplitude_bar_spec.BOTTOM_NOTCH_HEIGHT
    )
    assert len(finish_spec.SURFACE_FINISHES) == 1
    part_source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)" in part_source
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'surface_finish_by_key(SURFACE_FINISHES, "bottom_notch_floor")' in source
    assert "add_datum_feature(" not in source
    assert "add_feature_control_frame(" not in source
    assert drawing.FINISH_CHAR_HEIGHT == 0.0025
    # The channel/magnifier/summing closure imports amplitude_bar_spec; the
    # finish controls stay out of it.
    spec_source = Path(ch_amplitude_bar_spec.__file__).read_text(encoding="utf-8")
    assert "SurfaceFinishControl" not in spec_source


def test_floor_finish_leader_runs_through_the_mouth_crossing_only_a_witness() -> None:
    """The symbol (~17 mm wide) cannot stand in the 12.7 mm mouth; its bent
    leader climbs from under the right cheek through the mouth to the floor,
    crossing the right witness between the bar's end and the width row, never
    the width's dimension line, its text or the cheek. The width's text stands
    west of the bar, so its dimension line runs west from the right witness
    and the air east of that witness is the symbol's."""
    a = drawing.DETAIL_A
    spec = ch_amplitude_bar_spec
    ax, ay = drawing.FLOOR_FINISH_ATTACH
    vx, vy = drawing.FLOOR_FINISH_SYMBOL
    kx = vx - drawing.FINISH_SHOULDER  # the shoulder runs toward the attach
    end_y = a.sheet_xy(0.0, 0.0)[1]
    left_wall = a.sheet_xy(_O, 0.0)[0]
    right_wall = a.sheet_xy(_O + spec.BOTTOM_NOTCH_WIDTH, 0.0)[0]
    bar_right = a.sheet_xy(_W, 0.0)[0]
    row_y = drawing.DETAIL_A_KEEP["BottomNotchWidth"][1]

    assert ay == a.sheet_xy(0.0, spec.BOTTOM_NOTCH_HEIGHT)[1]  # on the floor
    assert left_wall < ax < right_wall

    def x_at(y: float) -> float:
        return kx + (ax - kx) * (y - vy) / (ay - vy)

    # Leaves the mouth clear of the cheek's corner.
    assert left_wall + 0.001 < x_at(end_y) < right_wall - 0.001
    # Crosses the right witness between the bar's end and the row...
    t = (kx - right_wall) / (kx - ax)
    witness_y = vy + t * (ay - vy)
    assert row_y + 0.002 < witness_y < end_y - 0.002
    # ...and stays east of that witness below it, above the width row: the
    # width's line and text lie west of the witness (r743-6b had the text on
    # the mouth, under the leader).
    assert drawing.DETAIL_A_KEEP["BottomNotchWidth"][0] < left_wall
    assert kx > right_wall + 0.001
    assert vy > row_y + 0.002
    # The symbol body (~2.5 mm left of the vertex to ~15 mm right, 5.4 mm up)
    # stands under the right cheek, clear of the bar, inside the fence.
    assert vx - 0.0025 > right_wall + 0.004
    assert vy + 0.0054 < end_y - 0.004
    for x, y in ((vx + 0.015, vy), (vx + 0.015, vy + 0.0054)):
        assert math.dist((x, y), a.centre) < a.radius_mm * a.mm
    assert vy + 0.0054 < end_y and vx + 0.015 > bar_right  # under, past the cheek


def test_part_stamps_make_critical_drawing_properties() -> None:
    """Machinist round 1 (#1293): the plating's effect on size and the masked
    reamed hole belong in the FINISH field, not a note."""
    source = Path(bar.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-amplitude-bar")
    assert spec["material_specification"] == "low-carbon cold-finished steel, 1/4 in sq"
    # One line in the FINISH field (r1 wrapped at 50 characters). Round 2:
    # the unplated press bore states its protection.
    assert spec["finish"] == "bright chrome, dims plated; pin hole bare, oiled"
    assert len(spec["finish"]) < 50
    assert int(spec["quantity"]) == 20


def test_each_notch_minimum_clears_its_plate_at_max_material() -> None:
    """User ruling 2026-09-27 (#1038): a notch is never narrower than the
    plate it straddles. Its minimum -- the modelled nominal -- is the plate at
    max material plus RUNNING_FLOOR, rounded up to an even thousandth so the
    centred ledge prints at three places; the band is one-sided, native on the
    width."""
    import ch_rocker_arm_spec as rocker
    import rocker_bank_layout as bank
    from _drawing_contract import model_toleranced_dimensions

    spec = ch_amplitude_bar_spec
    # The foot notch's restated strap envelope covers the rocker strap at
    # maximum material (#290: the strap prints .098 +/-.001).
    assert spec.STRAP_THICKNESS + spec.STRAP_THICKNESS_TOLERANCE >= (
        rocker.ARM_THICKNESS + rocker.ARM_THICKNESS_BAND[0]
    )
    assert spec.STRADDLE_RUNNING_FLOOR == bank.RUNNING_FLOOR

    # #1038 option 2 (owner ruling 2026-10-15): the top notch +.007/.000 (the
    # inch band that keeps the neighbour gap); the foot an interim +.010/.000.
    assert spec.TOP_NOTCH_WIDTH_BAND == pytest.approx((0.007 * 25.4, 0.0))
    assert spec.BOTTOM_NOTCH_WIDTH_BAND == pytest.approx((0.010 * 25.4, 0.0))
    for width, (_upper, lower), plate, tolerance in (
        (
            spec.TOP_NOTCH_WIDTH,
            spec.TOP_NOTCH_WIDTH_BAND,
            spec.LEVER_THICKNESS,
            spec.LEVER_THICKNESS_TOLERANCE,
        ),
        (
            spec.BOTTOM_NOTCH_WIDTH,
            spec.BOTTOM_NOTCH_WIDTH_BAND,
            spec.STRAP_THICKNESS,
            spec.STRAP_THICKNESS_TOLERANCE,
        ),
    ):
        least = width + lower
        assert least >= plate + tolerance + bank.RUNNING_FLOOR - 1e-9
        assert least - (plate + tolerance + bank.RUNNING_FLOOR) < 0.002 * 25.4
    assert spec.TOP_NOTCH_WIDTH == pytest.approx(0.124 * 25.4)
    assert spec.BOTTOM_NOTCH_WIDTH == pytest.approx(0.124 * 25.4)
    assert bar.TOP_NOTCH_WIDTH is spec.TOP_NOTCH_WIDTH
    assert bar.BOTTOM_NOTCH_WIDTH is spec.BOTTOM_NOTCH_WIDTH

    bands = model_toleranced_dimensions(bar)
    for name, band in (
        ("BottomNotchWidth", "BOTTOM_NOTCH_WIDTH_BAND"),
        ("TopNotchWidth", "TOP_NOTCH_WIDTH_BAND"),
    ):
        assert bands[("BarProfile", name)] == f"*deviations({band})"
        assert ch_amplitude_bar_notes.DRAWING_PRECISION["BarProfile"][name] == 3


def test_top_notch_keeps_the_running_gap_at_the_printed_worst_case() -> None:
    """#1038 option 2 (owner ruling 2026-10-15): the top notch's float on the
    .118 +/-.002 plate leaves the 0.7065 side gap its running floor; the full
    stack, with both ledges and plate offsets, is
    ch_bar_pivot_pin_spec.joint_budget's neighbour_clearance_min."""
    import ch_bar_pivot_pin_spec as pin
    import rocker_bank_layout as bank

    spec = ch_amplitude_bar_spec
    float_max = (spec.TOP_NOTCH_WIDTH + spec.TOP_NOTCH_WIDTH_BAND[0]) - (
        spec.LEVER_THICKNESS - spec.LEVER_THICKNESS_TOLERANCE
    )
    assert bank.PITCH - spec.BAR_WIDTH - float_max >= bank.RUNNING_FLOOR
    assert pin.BUDGET["neighbour_clearance_min"] >= bank.RUNNING_FLOOR


@pytest.mark.xfail(
    strict=True,
    reason="#1038: at the printed bands a bar's foot-notch float can close "
    "the 0.7065 side gap to its neighbour (user ruling 2026-09-27: ship as a "
    "known issue with interim bands)",
)
def test_neighbouring_bars_keep_a_running_gap_at_the_foot() -> None:
    """Bars 6.35 wide sit at the 7.0565 station pitch. Each floats on its
    straddled strap by (notch max - strap min); two neighbours floating toward
    each other close the side gap by that much."""
    import rocker_bank_layout as bank

    spec = ch_amplitude_bar_spec
    gap = bank.PITCH - spec.BAR_WIDTH
    float_max = (spec.BOTTOM_NOTCH_WIDTH + spec.BOTTOM_NOTCH_WIDTH_BAND[0]) - (
        spec.STRAP_THICKNESS - spec.STRAP_THICKNESS_TOLERANCE
    )
    assert gap - float_max >= bank.RUNNING_FLOOR


def test_cropped_views_are_model_views_dimensioned_before_the_crop() -> None:
    """r743-6 (d92938949, leaf 20260927T020523Z-1-e3f9f1f7): the front view's
    import took the notch dimensions and deleted them, then a native detail of
    it imported nothing (available=[]). Each enlarged view is a model view,
    dimensioned uncropped, then cropped (the pc-r15 kink-detail pattern,
    d6b8ed93f), and every one imports before the front view."""
    import ast
    import inspect

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "CreateDetailViewAt4" not in source
    tree = ast.parse(source)

    def calls(function: str) -> list[str]:
        node = next(
            item
            for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == function
        )
        found = []
        for call in ast.walk(node):
            if isinstance(call, ast.Call):
                name = getattr(call.func, "id", None) or getattr(call.func, "attr", "")
                found.append((call.lineno, call.col_offset, name))
        return [name for _line, _col, name in sorted(found)]

    order = calls("_dimension_then_crop")
    assert order.index("curate_view_dimensions") < order.index("_crop_view")
    assert order.count("_view_dimension_names") == 2
    build = calls("build")
    assert build.index("place_view") < build.index("_placed_cropped_view")
    assert build.index("_placed_cropped_view") < build.index("_dimension_then_crop")
    assert build.index("_dimension_then_crop") < build.index("curate_view_dimensions")
    assert build.index("curate_view_dimensions") < build.index("_mark_detail_on_front")
    assert "Crop2" in inspect.getsource(drawing._crop_view)
    for view in drawing.CROPPED_VIEWS:
        scale = view.scale[0] / view.scale[1]
        assert view.crop_radius == pytest.approx(view.radius_mm * scale / 1000)
        assert view.mark_radius == pytest.approx(view.radius_mm / 4 / 1000)


def _printed(model: float, places: int) -> float:
    """The inch value (as SOLIDWORKS rounds it) the sheet prints for ``model``."""
    lower, _upper = printed_deviations(
        model, places, (0.0, 0.0), unit=ch_amplitude_bar_spec.UNIT
    )
    return round((model + lower) / 25.4, places)


def test_every_printed_dimension_reads_its_inch_value() -> None:
    """#290: the sheet prints decimal inch. Every fabricated nominal is its
    printed value; the bar length and the foot notch's depth close the
    rocker-bar-lever chain and stay exact, so their prints round them."""
    spec = ch_amplitude_bar_spec
    notes = ch_amplitude_bar_notes
    assert spec.UNIT == "in" == parts("ch-amplitude-bar")["drawing_unit"]
    places = notes.DRAWING_PRECISION_BY_NAME
    printed = {
        "BarLength": (spec.BAR_LENGTH, 31.82),
        "BottomLeftLedge": (spec.BOTTOM_NOTCH_OFFSET, 0.063),
        "BottomNotchHeight": (spec.BOTTOM_NOTCH_HEIGHT, 0.094),
        "BottomNotchWidth": (spec.BOTTOM_NOTCH_WIDTH, 0.124),
        "TopNotchHeight": (spec.TOP_NOTCH_HEIGHT, 0.55),
        "TopNotchWidth": (spec.TOP_NOTCH_WIDTH, 0.124),
        "TopRightLedge": (spec.TOP_NOTCH_OFFSET, 0.063),
        "BarSection": (spec.BAR_DEPTH, 0.25),
        "TopPinX": (spec.BAR_DEPTH / 2.0, 0.125),
        "TopPinDrop": (spec.TOP_PIN_DROP, 0.25),
        "TopPinDia": (spec.TOP_PIN_HOLE_DIA, 0.077),
    }
    assert set(printed) == set(places)
    exact = {"BarLength", "BottomNotchHeight"}
    for name, (model, inch) in printed.items():
        assert _printed(model, places[name]) == pytest.approx(inch), name
        on_grid = math.isclose(model, inch * 25.4, abs_tol=1e-9)
        assert on_grid is (name not in exact), name
    # The foot depth prints .094 over the 3/32 (.09375) model: its deepest
    # accepted notch sits .00025 (0.00635) under the model, far inside the
    # cheeks' ~0.39 air over the rocker hub (test_rocker_bank_layout).
    upper, lower = spec.BOTTOM_NOTCH_DEPTH_BAND
    deepest = printed_deviations(
        spec.BOTTOM_NOTCH_HEIGHT, places["BottomNotchHeight"], (lower, upper), unit=spec.UNIT
    )[1]
    assert deepest == pytest.approx(0.00635, abs=1e-6)
    # The link length prints 31.82 at .XX: the model's 808.3 stays inside
    # +/-.01, tighter than the former 808.3 +/-0.8.
    link = printed_deviations(spec.BAR_LENGTH, places["BarLength"], unit=spec.UNIT)
    assert link[0] < 0.0 < link[1]
    assert max(map(abs, link)) < 0.8


def test_every_band_is_inch_native() -> None:
    """Each native band is a whole number of thousandths (ten-thousandths on
    the ream), printed in inch by the part's display unit."""
    spec = ch_amplitude_bar_spec
    tol = spec.NOTCH_OFFSET_TOLERANCE_MM
    for band, inch in (
        (spec.TOP_NOTCH_WIDTH_BAND, (0.007, 0.0)),
        (spec.BOTTOM_NOTCH_WIDTH_BAND, (0.010, 0.0)),
        (spec.BOTTOM_NOTCH_DEPTH_BAND, (0.0, -0.020)),
        ((tol, -tol), (0.002, -0.002)),
        (spec.TOP_PIN_HOLE_BAND, (0.0009, 0.0005)),
    ):
        assert tuple(value / 25.4 for value in band) == pytest.approx(inch, abs=1e-12)
    part_source = Path(bar.__file__).read_text(encoding="utf-8")
    assert part_source.count("display_unit=UNIT") == 6
    assert (
        "apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)"
        in part_source
    )
    draw_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'unit=part_drawing_unit("ch-amplitude-bar")' in draw_source

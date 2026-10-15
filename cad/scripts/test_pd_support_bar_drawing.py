"""Offline contracts for the support-bar drawing (MHA-PD-007)."""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import build_pd_support_bar as part
import draw_pd_support_bar as drawing
import pd_support_bar_drawing_spec as sheet_spec
import pd_support_bar_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME

_MATES = ("MHA-PD-011", "MHA-PD-012", "MHA-PD-014", "MHA-VN-041", "MHA-VN-043")


def test_registry_identity_and_paths() -> None:
    row = DRAWINGS_BY_NAME["pd_support_bar"]
    assert (row.part, row.artifact_stem) == ("pd_support_bar", "pd-support-bar")
    assert row.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-support-bar.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-support-bar.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-support-bar_drawing.png")
    assert "draw_pd_support_bar.py" in PRECISION_MIGRATED_DRAWINGS
    import _config

    config = _config.parts("pd-support-bar")
    assert config["number"] == "MHA-PD-007"
    assert config["material"] == config["material_specification"]
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_marked_dimensions_are_the_kept_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is sheet_spec.DRAWING_DIMENSIONS
    marked = set().union(*sheet_spec.DRAWING_DIMENSIONS.values())
    kept = [
        *drawing.FRONT_KEEP,
        *drawing.BACK_KEEP,
        *drawing.SECTION_KEEP_NAMES,
        *drawing.DETAIL_KEEP,
        *drawing.SLOT_SECTION_KEEP_NAMES,
    ]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_printed_bands_are_the_spec_bands() -> None:
    assert model_toleranced_dimensions(part) == {
        ("HangerRowReference", "name"): "HOLE_POSITION_BAND",
        ("ClampRowReference", "name"): "CLAMP_POSITION_BAND",
        ("ClampSlotProfile", "ClampSlotWidth"): "*CLAMP_SLOT_WIDTH_LIMITS",
    }
    assert part.HANGER_STATION_NAMES == sheet_spec.HANGER_STATION_NAMES
    assert part.CLAMP_STATION_NAMES == sheet_spec.CLAMP_STATION_NAMES
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'for name in ("HangerRowHeight", *HANGER_STATION_NAMES):' in source
    assert 'for name in ("ClampRowHeight", *CLAMP_STATION_NAMES):' in source
    assert spec.HOLE_POSITION_BAND == 0.065
    # The band's places print it whole: .XXX for ±0.065, .XX for the clamp
    # row's ±0.18. The bar bands ARE the title block's .XXX row, so their
    # three places alone carry them.
    from _printed_tolerance import printed_band_mm

    places = sheet_spec.DRAWING_PRECISION
    assert places["HangerRowReference"] == dict.fromkeys(
        ("HangerRowHeight", *sheet_spec.HANGER_STATION_NAMES), 3
    )
    assert places["ClampRowReference"] == dict.fromkeys(
        ("ClampRowHeight", *sheet_spec.CLAMP_STATION_NAMES), 2
    )
    assert round(part.CLAMP_POSITION_BAND, 2) == part.CLAMP_POSITION_BAND
    assert places["BarProfile"]["Height"] == places["Bar"]["Depth"] == 3
    assert spec.BAR_BAND_PLACES == 3
    assert (
        printed_band_mm(spec.BAR_BAND_PLACES)
        == spec.BAR_HEIGHT_BAND
        == spec.BAR_DEPTH_BAND
    )
    # The slots' width at the round holes' .XX under their drilled limits;
    # travels and the counterbore's width at .XXX; its depth as the round
    # counterbores' (test_west_slots_take_up_the_column_pitch and
    # test_slot_heads_bear_and_stay_inside_their_counterbores say why).
    import _config

    drilled = _config.title_block("drilled_hole")
    assert (float(drilled["minus_mm"]), float(drilled["plus_mm"])) == (0.0, 0.1)
    assert part.CLAMP_SLOT_WIDTH_LIMITS == (0.0, 0.1)
    assert places["ClampSlotProfile"] == {"ClampSlotWidth": 2, "ClampSlotTravel": 3}
    assert places["ClampSlotCboreProfile"] == {
        "ClampSlotCboreWidth": 3,
        "ClampSlotCboreTravel": 3,
    }
    assert places["ClampSlotCounterbores"] == {
        "ClampSlotCboreDepth": sheet_spec.CLAMP_CBORE_DEPTH_PLACES
    }


def test_clamp_holes_find_the_back_arc_taps_at_the_printed_worst_case() -> None:
    """Review of PR #1471: the clamp row printed .X (±0.8), whose 2.263
    position zone over-runs the 0.812 the #8 clearance holes float on the
    #8-32 shanks. Fixed fastener: each screw threads into an MHA-SH-002
    back-arc tap held ±0.1 along the bar and in height (sh_column_clamp_fit),
    so the bar's zone (2·√2·band) plus the tap's must stay inside the least
    hole's float; the band is the widest .XX that does. A drift in the band,
    the hole, the shank or the taps' bands breaks one of these."""
    import _config
    from _hole_spec import HoleSpec, blind_cut_dia_mm
    from _printed_tolerance import printed_band_mm
    from sh_column_clamp_back_geom import HOLE_SPEC as BACK_ARC_TAP
    from sh_column_clamp_fit import EAR_HEIGHT_BAND, EAR_STATION_BAND
    from vn_clamp_screw_spec import SHANK_DIA

    # The mate: #8-32 taps in the back arc, located ±0.1 on both axes.
    assert (BACK_ARC_TAP.kind, BACK_ARC_TAP.size) == ("tapped", "#8-32")
    assert _config.parts("sh-column-clamp-back")["number"] == "MHA-SH-002"
    assert EAR_STATION_BAND == EAR_HEIGHT_BAND == 0.1
    tap_zone = 2.0 * math.hypot(EAR_STATION_BAND, EAR_HEIGHT_BAND)
    # The float: the least drilled #8 clearance hole over the basic major.
    assert part.CLAMP_THROUGH_HOLE_SPEC == HoleSpec("clearance", "#8")
    assert _config.title_block("drilled_hole")["minus_mm"] == 0.0
    hole_min = blind_cut_dia_mm(part.CLAMP_THROUGH_HOLE_SPEC)
    assert (hole_min, SHANK_DIA) == pytest.approx((4.978, 4.1656))
    hole_float = hole_min - SHANK_DIA
    assert part.CLAMP_HOLE_FLOAT == pytest.approx(hole_float)

    def zone(band: float) -> float:
        return 2.0 * math.sqrt(2.0) * band

    # The printed nominals are exact at .XX, so the zone is the band's alone.
    for value in (*part.CLAMP_STATIONS, part.CLAMP_ROW_HEIGHT):
        assert round(value, 2) == value
    band = part.CLAMP_POSITION_BAND
    assert band == pytest.approx(0.18)
    assert part.clamp_position_zone(band) == pytest.approx(zone(band))
    assert part.BACK_ARC_TAP_ZONE == pytest.approx(tap_zone)
    assert zone(band) + tap_zone <= hole_float  # 0.792 <= 0.812
    assert zone(band + 0.01) + tap_zone > hole_float
    # The title block's .X row (the finding) would not close; the band is
    # tighter than the .XX row, so the callout names the taps (rule 4).
    assert zone(printed_band_mm(1)) + tap_zone > hole_float
    assert band < printed_band_mm(2)
    assert "MHA-SH-002" in sheet_spec.CLAMP_TAP_MATE
    assert sheet_spec.CLAMP_CBORE_CALLOUT.startswith(sheet_spec.CLAMP_TAP_MATE)


def test_single_limits_are_the_spec_limits() -> None:
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    calls = {
        tuple(ast.unparse(arg) for arg in node.args[1:])
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_single_limit"
    }
    assert calls == {
        ("'CountersinkReference'", "'PivotCskDia'", "PIVOT_TAP_CSK_DIA", "TOL_MAX"),
        (
            "'CountersinkReference'",
            "'BracketCskDia'",
            "BRACKET_TAP_CSK_DIA",
            "TOL_MAX",
        ),
    }
    assert (sheet_spec.TOL_MIN, sheet_spec.TOL_MAX) == (5, 6)
    assert (spec.PIVOT_TAP_CSK_DIA, spec.BRACKET_TAP_CSK_DIA) == (4.3, 3.1)


def test_pivot_tap_runs_through_countersunk_on_both_faces() -> None:
    """User ruling 2026-10-15: the MHA-VN-041 tap runs THROUGH the bar so the
    screw's faced tip sits below the front face and is staked at its mouth."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "ExtrusionParameters(depth=2.0 * BAR_DEPTH, both_directions=True)" in source
    assert "for z_face in (-BACK_FACE_Z, BACK_FACE_Z)" in source
    assert source.count("v_pivot_csk = 2 * math.pi") == 1
    for retired in ("PIVOT_TAP_DRILL_DEPTH", "PIVOT_TAP_FULL_THREAD_MIN"):
        assert not hasattr(spec, retired), retired
    assert "PivotThreadReference" not in source
    assert "PivotThreadReference" not in sheet_spec.DRAWING_DIMENSIONS
    assert "PivotTap" not in sheet_spec.DRAWING_DIMENSIONS


def test_row_nominals_are_the_built_holes() -> None:
    left = -part.BAR_LENGTH / 2.0
    assert part.HANGER_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0 - spec.HANGER_TAP_Y == 14.5
    assert part.HANGER_STATIONS == pytest.approx(
        tuple(x - left for x in (spec.PIVOT_TAP_X, *spec.BRACKET_TAP_X))
    )
    assert part.HANGER_STATIONS == (168.0, 291.0, 298.0)
    # Both rows read from the same (left, x = -226) end.
    assert part.CLAMP_ROW_START_X == left
    assert part.CLAMP_ROW_X == (-214.5, -179.5, 179.5, 214.5)
    assert sorted(part.CLAMP_ROW_X) == sorted(part.CLAMP_HOLE_X)
    assert part.CLAMP_STATIONS == (11.5, 46.5, 405.5, 440.5)
    # END A's (east, -X) pair are round and locate the bar; the west pair are
    # the slots (owner ruling 2026-10-15, option A).
    assert sorted(part.CLAMP_ROUND_X) == [-214.5, -179.5]
    assert sorted(part.CLAMP_SLOT_X) == [179.5, 214.5]
    assert sorted((*part.CLAMP_ROUND_X, *part.CLAMP_SLOT_X)) == list(part.CLAMP_ROW_X)
    assert part.CLAMP_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0


def _authored_row(monkeypatch, row) -> list[tuple[str, float, str | None]]:
    """Run the builder's row author against a recording stub: each dimension
    it creates as (name, built value, drive equation), in creation order."""
    import _sketch

    values: list[float] = []
    names: list[str] = []
    lines = iter(range(100))

    class _Adapter:
        async def create_sketch(self, plane):
            return plane

        async def add_line(self, *_points):
            return f"line{next(lines)}"

        async def add_sketch_constraint(self, *args):
            return args

        async def exit_sketch(self):
            return None

    async def anchor(_adapter, _point, x, y, _label):
        values.extend(abs(c) for c in (x, y) if c != 0.0)

    async def dimension(_adapter, _a, _b, _kind, value, _label):
        values.append(value)

    async def defined(_adapter, _label):
        return None

    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_args: None)
    monkeypatch.setattr(part, "_as_construction", lambda *_args: None)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(part, "dimension_between", dimension)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(_sketch, "_feature_by_name", lambda _adapter, name: name)
    monkeypatch.setattr(_sketch, "_display_dimensions", lambda _f, _n: list(values))
    monkeypatch.setattr(
        _sketch,
        "_rename_dimensions",
        lambda _dims, _f, recorded: names.extend(recorded),
    )
    jobs = dict(asyncio.run(part._author_row(_Adapter(), row)))
    return [
        (name, value, jobs.get(f"{name}@{row.feature}"))
        for name, value in zip(names, values, strict=True)
    ]


def _evaluate(equation: str, globals_mm: dict[str, float]) -> float:
    text = re.sub(r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), equation)
    text = re.sub(r"(\d)mm\b", r"\1", text)
    return float(eval(text, {"__builtins__": {}}))  # noqa: S307 - literal arithmetic


@pytest.mark.parametrize(
    "globals_mm",
    [
        {"BarLength": 452.0, "BarHeight": 28.0},
        {"BarLength": 500.0, "BarHeight": 30.0},
        {"BarLength": 440.0, "BarHeight": 26.0},
    ],
)
def test_reference_rows_follow_the_bar_globals_onto_the_holes(
    monkeypatch, globals_mm
) -> None:
    """Review of PR #1471 (round 3): the row heights and stations were built
    without equations, so a Tools > Equations edit of BarHeight or BarLength
    moved the top face and the left end but left the old values, and the
    reference rows' points drifted off the real holes. Every row dimension now
    carries an equation; evaluated at any bar size it must land on the holes
    the builder places, which stay put relative to the bar centre (the pivot
    circle at PIVOT_TAP_X/HANGER_TAP_Y, the Hole Wizard taps at
    BRACKET_TAP_X/HANGER_TAP_Y and the clamp counterbores at CLAMP_HOLE_X/0)."""
    assert (spec.BAR_HEIGHT, part.BAR_LENGTH) == (28.0, 452.0)
    built = {"BarLength": part.BAR_LENGTH, "BarHeight": spec.BAR_HEIGHT}
    rows = (
        (
            part.HANGER_ROW,
            sheet_spec.HANGER_STATION_NAMES,
            [(x, spec.HANGER_TAP_Y) for x in (spec.PIVOT_TAP_X, *spec.BRACKET_TAP_X)],
        ),
        (
            part.CLAMP_ROW,
            sheet_spec.CLAMP_STATION_NAMES,
            sorted((x, 0.0) for x in part.CLAMP_HOLE_X),
        ),
    )
    length, height = globals_mm["BarLength"], globals_mm["BarHeight"]
    for row, names, holes in rows:
        # The row's points are the placed holes, one station name each.
        assert list(row.holes) == [
            (name, x) for name, (x, _y) in zip(names, holes, strict=True)
        ]
        (row_y,) = {y for _x, y in holes}
        expected = {
            f"{row.prefix}RiseX": length / 2.0,
            f"{row.prefix}RiseY": height / 2.0,
            row.height_name: height / 2.0 - row_y,
            f"{row.prefix}StartX": length / 2.0,
            # Each station runs from the moved left end to its unmoved hole.
            **{name: x + length / 2.0 for name, (x, _y) in zip(names, holes)},
        }
        authored = _authored_row(monkeypatch, row)
        assert [name for name, _value, _drive in authored] == list(expected)
        for name, value, drive in authored:
            assert drive is not None, name
            # Neutral at the built size, tracking the holes at any other.
            assert _evaluate(drive, built) == pytest.approx(value), name
            assert _evaluate(drive, globals_mm) == pytest.approx(expected[name]), name


def test_rows_stack_shortest_nearest_the_bar() -> None:
    def heights(keep: dict, names: tuple[str, ...]) -> list[float]:
        return [keep[name][1] for name in names]

    face = heights(drawing.FRONT_KEEP, (*sheet_spec.HANGER_STATION_NAMES, "Length"))
    back = heights(drawing.BACK_KEEP, sheet_spec.CLAMP_STATION_NAMES)
    for rows, bar_bottom in (
        (face, drawing.FACE_BOTTOM),
        (back, drawing.BACK_BOTTOM),
    ):
        assert all(y < bar_bottom for y in rows)
        assert all(a - b >= 0.008 - 1e-9 for a, b in zip(rows, rows[1:]))
    # Long-row texts stay between their extension lines.
    for name, span in zip(
        (*sheet_spec.HANGER_STATION_NAMES[1:], "Length"),
        (*part.HANGER_STATIONS[1:], part.BAR_LENGTH),
    ):
        x = drawing.FRONT_KEEP[name][0]
        assert drawing.LEFT_END < x < drawing.LEFT_END + span * drawing._S
    # In the front-face view that end is on the sheet's right: the long clamp
    # rows' texts stand between it and their holes. The first two rows'
    # banded texts are wider than their spans, so they stand right of the
    # end's extension line and left of the isometric view (its r6 outline's
    # left edge), at a conservative 2.76 mm a character (2.3 measured).
    iso_left = 0.3216
    for name, station, hole_x in zip(
        sheet_spec.CLAMP_STATION_NAMES, part.CLAMP_STATIONS, part.CLAMP_ROW_X
    ):
        x = drawing.BACK_KEEP[name][0]
        text = f"{station:.2f} \u00b1{part.CLAMP_POSITION_BAND:.2f}"
        half = len(text) * 0.00276 / 2.0
        if (drawing.RIGHT_END - drawing._back_x(hole_x)) > 2.0 * half:
            assert drawing._back_x(hole_x) < x - half < x + half < drawing.RIGHT_END
        else:
            assert drawing.RIGHT_END < x - half < x + half < iso_left, name
    assert [
        drawing.BACK_KEEP[name][0] > drawing.RIGHT_END
        for name in sheet_spec.CLAMP_STATION_NAMES
    ] == [True, True, False, False]


def test_clamp_callout_stands_between_the_bar_and_the_length_line() -> None:
    """r7 audit: the 4-line counterbore callout's first line sat on the face
    view's 452.0 length line. Native callout metrics measured on the farm
    (r6/r7 layout audits): the text block centres 2.8 mm under the anchor,
    lines 5.6 mm apart, each line's box 0.9..4.5 mm above its position; the
    length line runs 2.8 mm under its text anchor."""
    pitch, below_anchor = 0.0056, 0.0028
    # The native size and DRILL, C'BORE lines, then the mate lines.
    lines = 2 + len(sheet_spec.CLAMP_CBORE_CALLOUT.splitlines())
    centre = drawing.CLAMP_CALLOUT_XY[1] - below_anchor
    first = centre + (lines - 1) * pitch / 2.0
    last = centre - (lines - 1) * pitch / 2.0
    length_line = drawing.FRONT_KEEP["Length"][1] - 0.0028  # 160.2 mm
    assert first + 0.0045 <= length_line - 0.003
    assert last + 0.0009 >= drawing.BACK_TOP + 0.005


def test_sheet_texts_carry_no_dimensions_and_stay_short() -> None:
    # No general note: each slide grade's reason sits by its symbol.
    assert not hasattr(sheet_spec, "DRAWING_NOTES")
    for module in (part, drawing):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "Manufacturing Notes" not in source
    for text in (
        sheet_spec.TOP_FINISH_REASON,
        sheet_spec.FRONT_FINISH_REASON,
        sheet_spec.FACE_VIEW_CAPTION,
        sheet_spec.BACK_VIEW_CAPTION,
        sheet_spec.STATION_END_LABEL,
    ):
        assert len(text.splitlines()) == 1
        assert re.search(r"\d", text) is None
        for token in ("Ø", "±", "+/-", "MIN", "MAX", "DATUM"):
            assert token not in text
    assert sheet_spec.ISOMETRIC_VIEW_NOTE.endswith(
        f"{drawing.ISO_SCALE[0]}:{drawing.ISO_SCALE[1]}"
    )
    # The station end is named in both mirrored face views.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("_place_caption(adapter, STATION_END_LABEL,") == 2


def test_callouts_name_the_mates() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    for name in ("Height", "Depth", "HangerRowHeight", "PivotCskDia"):
        assert any(mate in callouts[name] for mate in _MATES), name
    assert "MHA-PD-011" in callouts["Height"]
    assert "MHA-VN-041" in callouts["Depth"]
    assert "MHA-VN-043" in callouts["Depth"]
    assert "MHA-VN-041" in callouts["HangerRowHeight"]
    assert "MHA-PD-014" in callouts["HangerRowHeight"]
    # Each tight hanger station names the part it places.
    assert "MHA-VN-041" in callouts["PivotTapStation"]
    assert "MHA-PD-014" in callouts["BracketTapStation1"]
    assert "MHA-PD-014" in callouts["BracketTapStation2"]
    # The thread class is the title block's (rule 2), native callout too.
    assert callouts["PivotTapDrillDia"] == "TAP #8-32 UNC THRU"
    assert "2B" not in "".join(callouts.values())
    assert drawing._THREAD_CLASS_TOKEN == " <hw-threadclass>"
    # "2X" counts holes only: the one pivot hole is countersunk on both faces.
    assert callouts["PivotCskDia"].startswith("90\u00b0 CSK BOTH FACES")
    # The latch-hook taps' leader passes just right of the pivot's text.
    assert max(map(len, callouts["PivotCskDia"].splitlines())) <= 24
    assert callouts["BracketCskDia"].startswith("2X 90\u00b0 CSK")
    for text in callouts.values():
        assert len(text.splitlines()) <= 3
    # The banded clamp row names the back-arc taps it locates to, then the
    # screws whose heads the counterbores sink.
    assert sheet_spec.CLAMP_CBORE_CALLOUT.splitlines() == [
        "LOCATE TO MHA-SH-002 TAPS",
        "MHA-VN-021 HEADS BELOW SLIDE FACE",
    ]
    # The banded clamp row's height names those taps at the dimension too.
    assert "MHA-SH-002" in callouts["ClampRowHeight"]


def test_slide_faces_carry_the_slide_grade() -> None:
    from _surface_finish import MACHINED_UM

    controls = {control.key: control for control in sheet_spec.SURFACE_FINISHES}
    assert set(controls) == {"top_slide", "front_slide"}
    assert {control.roughness_um for control in controls.values()} == {MACHINED_UM}
    top, front = controls["top_slide"].face, controls["front_slide"].face
    assert (top.normal, top.offset_mm) == ((0, 1, 0), spec.BAR_HEIGHT / 2.0)
    assert (front.normal, front.offset_mm) == ((0, 0, -1), spec.BAR_DEPTH / 2.0)
    # The front-face leader lands on the face, clear of every hole.
    x, y = drawing.FRONT_FINISH_MODEL_XY
    assert abs(y) < spec.BAR_HEIGHT / 2.0
    assert all(
        abs(x - hole) > part.CLAMP_CBORE_DIA
        for hole in (*part.CLAMP_HOLE_X, *spec.BRACKET_TAP_X)
    )
    assert (
        drawing.LEFT_END
        < drawing._face_x(drawing.TOP_FINISH_MODEL_X)
        < drawing._face_x(spec.PIVOT_TAP_X)
    )


def test_build_authors_marks_properties_and_hides_references() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    for needle in (
        '"cut pivot tap drill (through)"',
        "apply_drawing_precision(adapter, SHEET_PRECISION)",
        "clear_dimensions_for_drawing(adapter)",
        "blank_reference_sketches(adapter, REFERENCE_SKETCHES)",
        '"Isometric View Note": ISOMETRIC_VIEW_NOTE',
        "author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)",
    ):
        assert source.count(needle) == 1, needle
    hidden = {
        name for name in sheet_spec.DRAWING_DIMENSIONS if name.endswith("Reference")
    }
    assert hidden == set(part.REFERENCE_SKETCHES)
    # Precision follows the bar bands' pinned literal, after the drive.
    pinned = source.index(
        '{"BarProfile": {"Height": BAR_BAND_PLACES}, "Bar": {"Depth": BAR_BAND_PLACES}}'
    )
    assert source.index("drive_dimension(") < pinned
    assert pinned < source.index("apply_drawing_precision(adapter, SHEET_PRECISION)")


def test_hole_callouts_pick_the_tap_and_counterbore_edges(monkeypatch) -> None:
    picks = []

    class _Edges:
        def circle_at(self, center, radius, *, axis, label, radius_tol_mm):
            picks.append((center, radius, axis))

            class _Hit:
                edge = label

            return _Hit()

    monkeypatch.setattr(drawing, "scan_view_edges", lambda view, *, label: _Edges())
    assert drawing._hole_rims(object(), object()) == (
        "latch-hook tap edge",
        "clamp counterbore rim",
    )
    tap_dia = part.blind_cut_dia_mm(spec.BRACKET_TAP_SPEC)
    csk_depth = (spec.BRACKET_TAP_CSK_DIA - tap_dia) / 2.0
    assert picks == [
        (
            (spec.BRACKET_TAP_X[0], spec.HANGER_TAP_Y, spec.BACK_FACE_Z - csk_depth),
            tap_dia / 2.0,
            (0.0, 0.0, 1.0),
        ),
        (
            (max(part.CLAMP_ROUND_X), 0.0, -spec.BAR_DEPTH / 2.0),
            part.CLAMP_CBORE_DIA / 2.0,
            (0.0, 0.0, 1.0),
        ),
    ]


def test_isometric_is_drawn_hidden_lines_removed() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (face, back, iso):" in source
    assert "set_hidden_lines_removed(adapter, view)" in source


def _printed_cbore_depth_limits() -> tuple[float, float]:
    from _printed_tolerance import printed_band_mm

    places = sheet_spec.CLAMP_CBORE_DEPTH_PLACES
    printed = round(part.CLAMP_CBORE_DEPTH, places)
    band = printed_band_mm(places)
    return printed - band, printed + band


def test_clamp_heads_stay_under_the_front_face_at_the_printed_worst_case() -> None:
    shallowest, deepest = _printed_cbore_depth_limits()
    # The depth is a clearance: .XX, its nominal deep enough for the band.
    assert sheet_spec.CLAMP_CBORE_DEPTH_PLACES == 2
    # The platen slides across the front face: the head never stands proud,
    # even at the depth's printed minimum.
    assert part.CLAMP_HEAD_H < shallowest
    # Rule 17: the floor under the deepest counterbore in the thinnest bar.
    assert (spec.BAR_DEPTH - spec.BAR_DEPTH_BAND) - deepest >= 2.0


def test_clamp_screws_engage_the_back_arc_and_stop_inside_it() -> None:
    # Head seat -> rest of the bar -> front arc -> the open grip gap (the back
    # arc's mating face stops GRIP_OFFSET short of the column axis) ->
    # threads into the back arc's through tap (build_pd_paper_drive_assembly's
    # clamp stack), over the printed depth and thickness bands; the arcs at
    # their nominals.
    from sh_column_clamp_back_geom import BLOCK_DEPTH as back_block
    from sh_column_clamp_back_geom import GRIP_OFFSET as grip_gap
    from sh_column_clamp_front_geom import ARC_DEPTH as front_arc
    from vn_clamp_screw_spec import SHANK_DIA, SHANK_LEN

    shallowest, deepest = _printed_cbore_depth_limits()
    thick = spec.BAR_DEPTH + spec.BAR_DEPTH_BAND
    thin = spec.BAR_DEPTH - spec.BAR_DEPTH_BAND
    least = SHANK_LEN - (thick - shallowest + front_arc + grip_gap)
    most = SHANK_LEN - (thin - deepest + front_arc + grip_gap)
    # Rule 18: 1.5D of thread at the least engagement.
    assert least >= 1.5 * SHANK_DIA
    # The tip never leaves the back arc's tapped block, so nothing behind it
    # is reached.
    assert most < back_block


def test_west_slots_take_up_the_column_pitch() -> None:
    """Owner ruling 2026-10-15, option A (PR #1471 round-3 review, finding 1):
    the column pitch is not the bar's, and the round holes' float did not take
    it up. Recomputed here from the mates' bands, not the builder's helpers:
    the east pair stay round and locate the bar; each west slot's least travel
    each way plus both shanks' slack along the bar must cover the pitch error
    and every band between an east and a west screw."""
    import fr_top_frame_spec
    from _printed_tolerance import printed_band_mm
    from sh_column_clamp_fit import (
        BORE_DIAMETRAL_CLEARANCE,
        EAR_HEIGHT_BAND,
        EAR_STATION_BAND,
    )
    from vn_clamp_screw_spec import SHANK_DIA

    # The pitch's sources: the top frame dimensions its socket pitch at .XX;
    # the base's hole table prints each socket's X at .XX, two bands apart.
    assert fr_top_frame_spec.DRAWING_REFERENCE_PRECISION["socket horizontal pitch"] == 2
    assert part.COLUMN_PITCH_PLACES == 2
    top, base = printed_band_mm(2), 2.0 * printed_band_mm(2)
    assert (top, base) == pytest.approx((0.51, 1.02))
    assert sorted(part.COLUMN_PITCH_DEVIATIONS.values()) == pytest.approx([top, base])
    # A shank's slack along the bar in the least #8 hole (the model's 4.978,
    # under the printed 4.98) at the worst height misalignment.
    radial = (4.978 - SHANK_DIA) / 2.0
    height = 0.18 + EAR_HEIGHT_BAND
    assert part.CLAMP_POSITION_BAND == 0.18
    slack = math.sqrt(radial**2 - height**2)
    assert slack == pytest.approx(0.2943, abs=1e-4)
    # Each slot's least travel each way: its 3.000 run at .XXX.
    assert part.CLAMP_SLOT_RUN == 2.0 * part.CLAMP_SLOT_TRAVEL == 3.0
    assert part.CLAMP_SLOT_WIDTH == part.CLAMP_HOLE_DIA == pytest.approx(4.978)
    travel = (3.0 - printed_band_mm(3)) / 2.0
    # Between an east and a west screw: both bar stations, both clamps' tap
    # stations and both clamps' shift on their columns.
    between = 2.0 * (0.18 + EAR_STATION_BAND + BORE_DIAMETRAL_CLEARANCE[1] / 2.0)
    assert between == pytest.approx(0.86)
    for pitch, margin in ((top, 0.6536), (base, 0.1436)):
        left = travel + 2.0 * slack - (pitch + between)
        assert left == pytest.approx(margin, abs=5e-4)
        assert part.clamp_slot_closure_margin(pitch) == pytest.approx(left)
    # Round west holes would not close even the top frame's pitch, and the
    # travel's .XXX matters: at .XX the base's pitch would not close.
    assert 2.0 * slack - (top + between) < 0.0
    assert (3.0 - printed_band_mm(2)) / 2.0 + 2.0 * slack - (base + between) < 0.0
    # The east pair share one clamp: only their stations and taps open it.
    east = 2.0 * slack - 2.0 * (0.18 + EAR_STATION_BAND)
    assert east == pytest.approx(0.0286, abs=1e-4)
    assert part.clamp_east_pair_margin() == pytest.approx(east)
    # The sheet names the clamp taps the slots take up (rule 4: the band's
    # mate) and says their limits and stations set that take-up, restating
    # no value beside part numbers.
    why = sheet_spec.DIMENSION_CALLOUTS["ClampSlotWidth"]
    assert "TAKE-UP" in why and "MHA-SH-002" in why
    assert "LIMITS" in why and "STATIONS" in why
    assert re.search(r"\d", re.sub(r"MHA-[A-Z]{2}-\d{3}", "", why)) is None


def test_slot_heads_bear_and_stay_inside_their_counterbores() -> None:
    """The stock MHA-VN-021 head over a slot: at the shank's full float across
    the widest slot it still overlaps the counterbore floor by the round
    holes' own least (the same Ø4.98 +0.10/-0), and anywhere the shank reaches
    in the longest slot it stays inside the narrowest, shortest counterbore."""
    from _printed_tolerance import printed_band_mm
    from vn_clamp_screw_spec import HEAD_DIA, SHANK_DIA

    head_r = HEAD_DIA / 2.0
    widest = 4.98 + 0.10
    shift = (widest - SHANK_DIA) / 2.0
    bearing = head_r - widest / 2.0 - shift
    assert bearing == pytest.approx(0.4318, abs=1e-4)
    assert part.CLAMP_HEAD_BEARING_MIN == pytest.approx(bearing)
    assert part.clamp_head_bearing(widest) == pytest.approx(bearing)
    band = printed_band_mm(3)
    overrun = ((3.0 + band) - (3.0 - band)) / 2.0
    reach = head_r + shift + overrun
    room = (8.5 - band) / 2.0
    assert room - reach == pytest.approx(0.1688, abs=1e-4)
    assert part.clamp_slot_head_clearance() == pytest.approx(room - reach)
    # At .XX the counterbore's width would not hold the head.
    assert (8.5 - printed_band_mm(2)) / 2.0 < reach
    # The slot counterbore is the round one's width, cut as deep.
    assert part.CLAMP_SLOT_CBORE_WIDTH == part.CLAMP_CBORE_DIA == 8.5
    assert part.CLAMP_SLOT_CBORE_RUN == part.CLAMP_SLOT_RUN
    # The .XXX counterbore names the screw whose head it holds.
    assert "MHA-VN-021" in sheet_spec.DIMENSION_CALLOUTS["ClampSlotCboreWidth"]


def test_slot_counterbores_leave_rule_17_walls() -> None:
    """Worst-case walls round the west counterbores: to the bar's west end
    (the .X length short, the outer station long), between the pair's
    counterbores, and to the top and bottom faces."""
    from _printed_tolerance import printed_band_mm

    assert sheet_spec.SHEET_PRECISION["BarProfile"]["Length"] == 1
    band = printed_band_mm(3)
    cbore_reach = (3.0 + band) / 2.0 + (8.5 + band) / 2.0
    end_wall = (452.0 - printed_band_mm(1)) - (440.5 + 0.18) - cbore_reach
    assert end_wall == pytest.approx(4.64, abs=5e-3)
    web = (440.5 - 405.5) - 2.0 * 0.18 - 2.0 * cbore_reach
    assert web == pytest.approx(22.88, abs=5e-3)
    side = (spec.BAR_HEIGHT - spec.BAR_HEIGHT_BAND) / 2.0 - 0.18 - (8.5 + band) / 2.0
    assert side == pytest.approx(9.44, abs=5e-3)
    for wall in (end_wall, web, side):
        assert wall >= 2.0
    # Nominally 5.75 to the end, 23.5 between.
    reach = part.CLAMP_SLOT_RUN / 2.0 + part.CLAMP_SLOT_CBORE_WIDTH / 2.0
    assert part.BAR_LENGTH / 2.0 - max(part.CLAMP_SLOT_X) - reach == 5.75
    assert max(part.CLAMP_SLOT_X) - min(part.CLAMP_SLOT_X) - 2.0 * reach == 23.5


def test_slot_widths_print_their_count() -> None:
    count = f"{len(part.CLAMP_SLOT_X)}X "
    assert sheet_spec.DIMENSION_PREFIXES == {
        ("ClampSlotProfile", "ClampSlotWidth"): count,
        ("ClampSlotCboreProfile", "ClampSlotCboreWidth"): count,
    }
    for feature, name in sheet_spec.DIMENSION_PREFIXES:
        assert name in sheet_spec.DRAWING_DIMENSIONS[feature]


def test_slot_views_frame_the_slots() -> None:
    # Detail C fences the outer slot's whole counterbore inside the bar's
    # height; section B-B cuts the inner slot, its caption under it.
    assert drawing.DETAIL_SLOT_X == max(part.CLAMP_SLOT_X)
    reach = part.CLAMP_SLOT_CBORE_RUN / 2.0 + part.CLAMP_SLOT_CBORE_WIDTH / 2.0
    assert reach < drawing.DETAIL_RADIUS_MM < spec.BAR_HEIGHT / 2.0
    assert drawing.SLOT_SECTION_X == min(part.CLAMP_SLOT_X)
    scale = drawing.SLOT_SECTION_SCALE[0] / drawing.SLOT_SECTION_SCALE[1]
    bottom = drawing.SLOT_SECTION_CENTER[1] - spec.BAR_HEIGHT * scale / 2000.0
    assert drawing.SLOT_SECTION_CAPTION_XY[1] < bottom
    # Detail C's slot-width text stands under the slot's lower edge, right of
    # the crop circle (inside its 4.98 span its own dimension line struck it,
    # r4 review), and the label right of that.
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_MM
    width_x, width_y = drawing.DETAIL_KEEP["ClampSlotWidth"]
    assert width_x > drawing.DETAIL_CENTER[0] + radius
    edge = drawing.DETAIL_CENTER[1] - part.CLAMP_SLOT_WIDTH * drawing.DETAIL_MM / 2.0
    assert width_y < edge
    assert drawing.DETAIL_LABEL_XY[0] > width_x
    # Its letter stands off the bar, past the end and under the clamp row's
    # extension line, right of the row height's dimension line: over the
    # outer slot it printed on section B-B's upper letter (r4 review).
    letter_x, letter_top = drawing.DETAIL_LETTER_TOP
    assert drawing.BACK_KEEP["ClampRowHeight"][0] < letter_x < drawing.LEFT_END
    assert letter_top < drawing.BACK_CENTER[1]
    # Detail C's counterbore-width text stands over the counterbore's upper
    # edge, left of the detail's crop (inside its span it met its own
    # extension line and arrow, r6 review). Its shoulder (28.5 mm on the r7
    # sheet) ends right of section B-B's back face, so the section rises
    # beside the text rather than under it.
    cbore_x, cbore_y = drawing.DETAIL_KEEP["ClampSlotCboreWidth"]
    assert cbore_x < drawing.DETAIL_CENTER[0] - radius
    cbore_edge = (
        drawing.DETAIL_CENTER[1] + part.CLAMP_SLOT_CBORE_WIDTH * drawing.DETAIL_MM / 2.0
    )
    assert cbore_y > cbore_edge
    back_face = drawing.SLOT_SECTION_CENTER[0] + spec.BAR_DEPTH * scale / 2000.0
    assert cbore_x - 0.0285 - back_face >= 0.0025


def test_section_letters_and_slot_caption_have_air() -> None:
    """Rules 13 and 14 (r7 review): the section letters stand off the bar's
    edges and section B-B's caption stands between its cut and the border.
    Offsets are the r7 sheet's: each letter from 1.28 mm under its arrow's
    line to 4.89 over it; the caption 14.6 tall, its top 0.05 under its
    anchor; the inner border's edge at y 12.9."""
    scale = drawing.FACE_SCALE[0] / drawing.FACE_SCALE[1]
    top_line = drawing.SECTION_OVERRUN_TOP * scale
    foot_line = drawing.SECTION_OVERRUN_FOOT * scale
    assert top_line - 1.28 >= 1.5  # upper letter's bottom over the top edge
    assert foot_line - 4.89 >= 1.5  # lower letter's top under the bottom edge
    slot_scale = drawing.SLOT_SECTION_SCALE[0] / drawing.SLOT_SECTION_SCALE[1]
    cut_bottom = (
        drawing.SLOT_SECTION_CENTER[1] - spec.BAR_HEIGHT * slot_scale / 2000.0
    ) * 1000.0
    caption_top = drawing.SLOT_SECTION_CAPTION_XY[1] * 1000.0 - 0.05
    assert cut_bottom - caption_top >= 2.5
    assert caption_top - 14.6 - 12.9 >= 2.5


def test_slot_section_depth_line_runs_through_the_open_slot(monkeypatch) -> None:
    """Section B-B's depth line runs where the counterbore's mouth and the
    through slot are open, so neither extension line crosses the hatch (r6:
    over the top face the floor's ran up through the cut), and its text
    stands outside the front face, whichever way the cut projects."""
    for flip in (1.0, -1.0):
        origin = (0.050, 0.045)

        def sheet(_adapter, _view, point, _label, flip=flip, origin=origin):
            _x, y, z = point
            return (origin[0] + flip * z / 1000.0, origin[1] + y / 1000.0)

        monkeypatch.setattr(drawing, "_sheet", sheet)
        text_x, text_y = drawing._slot_section_keep(None, None)["ClampSlotCboreDepth"]
        front = origin[0] - flip * spec.BAR_DEPTH / 2000.0
        line_y = text_y - drawing.SLOT_DEPTH_SHELF_DROP
        assert abs(line_y - origin[1]) < part.CLAMP_SLOT_WIDTH / 2000.0
        assert (text_x - front) * flip < 0.0
        assert abs(text_x - front) == pytest.approx(drawing.SLOT_DEPTH_TEXT_SIDE)


class _DetailView:
    """A placed model view: its Position moves by SetViewPosition, and a model
    point projects ``offset`` from it."""

    def __init__(self, position, scale, offset):
        self.Position = position
        self.ScaleRatio = scale
        self.offset = offset

    def SetViewPosition(self, xy, _redraw):  # noqa: N802
        self.Position = tuple(float(value) for value in xy)
        return True


def test_slot_detail_is_a_model_view_centred_on_the_outer_slot(monkeypatch) -> None:
    """Farm r3 (leaf 20261015T223907.571157Z, drawing:pd_support_bar): a
    native detail of the front-face view imported none of the slot profiles'
    dimensions (available=[]). Detail C is a 2:1 *Back model view moved so
    the outer slot lands on its centre; nothing creates a native detail."""
    placed = []

    def place(_adapter, source, orientation, x, y, *, scale):
        placed.append((source, orientation, scale))
        return _DetailView((x, y), tuple(float(v) for v in scale), (-0.31, 0.0))

    def sheet(_adapter, view, xyz, _label):
        assert xyz == (max(part.CLAMP_SLOT_X), 0.0, -spec.BAR_DEPTH / 2.0)
        return (
            view.Position[0] + view.offset[0],
            view.Position[1] + view.offset[1],
        )

    def native_detail(*_args):
        raise AssertionError("detail C must not be a native detail view")

    model = SimpleNamespace(
        EditRebuild3=lambda: True, CreateDetailViewAt4=native_detail
    )
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(drawing, "_sheet", sheet)
    monkeypatch.setattr(drawing, "double_array", tuple)
    view = drawing._slot_detail(SimpleNamespace(currentModel=model))
    assert placed == [(str(drawing.SOURCE), "*Back", drawing.DETAIL_SCALE)]
    assert sheet(None, view, drawing.DETAIL_FOCUS, "") == pytest.approx(
        drawing.DETAIL_CENTER
    )
    assert drawing.DETAIL_LABEL == "DETAIL C\nSCALE 2 : 1"


@pytest.mark.parametrize("dropped", [(), ("ClampSlotTravel",)])
def test_slot_detail_is_dimensioned_before_its_crop(monkeypatch, dropped) -> None:
    """The dimensions import into the uncropped view; a kept one the crop
    drops fails the sheet."""
    calls = []
    names = {"cropped": False}

    def curate(_adapter, _view, *, keep, view_label, dimensions_by_feature):
        calls.append("curate")
        assert keep is drawing.DETAIL_KEEP
        assert dimensions_by_feature is sheet_spec.DRAWING_DIMENSIONS
        return ["kept"]

    def crop(_adapter, _view):
        calls.append("crop")
        names["cropped"] = True

    def held(_adapter, _view):
        kept = sorted(drawing.DETAIL_KEEP)
        if names["cropped"]:
            return [name for name in kept if name not in dropped]
        return kept

    monkeypatch.setattr(drawing.hidden_sketches, "curate_view_dimensions", curate)
    monkeypatch.setattr(drawing, "_crop_slot_detail", crop)
    monkeypatch.setattr(drawing, "_view_dimension_names", held)
    if dropped:
        with pytest.raises(RuntimeError, match="lost"):
            drawing._dimension_then_crop(None, object())
    else:
        assert drawing._dimension_then_crop(None, object()) == ["kept"]
    assert calls == ["curate", "crop"]


def test_round_counterbore_callout_stands_over_the_east_pair() -> None:
    """The native counterbore callout points at a round (east) hole; its
    widest line (2.3 mm a character, measured) stands right of the front
    finish symbol and left of the bar height's text."""
    half = (
        max(len(line) for line in sheet_spec.CLAMP_CBORE_CALLOUT.splitlines())
        * 0.0023
        / 2.0
    )
    x = drawing.CLAMP_CALLOUT_XY[0]
    assert drawing.FRONT_FINISH_SYMBOL_XY[0] + 0.006 < x - half
    assert x + half < drawing.BACK_KEEP["Height"][0] - 0.002
    hole = drawing._back_x(max(part.CLAMP_ROUND_X))
    assert x - half < hole < x + half


_FRONT_Z = -spec.BAR_DEPTH / 2.0
# Sketch frames SOLIDWORKS may hand the front-face plane's sketch: model mm
# to (u, v, w), sketch (u, v) back to model (x, y), and whether the normal
# points out of the front face.
_FRAMES = {
    "u along +X, normal into the bar": (
        lambda p: (p[0], p[1], p[2] - _FRONT_Z),
        lambda u, v: (u, v),
        False,
    ),
    "u along -X, normal out": (
        lambda p: (-p[0], p[1], _FRONT_Z - p[2]),
        lambda u, v: (-u, v),
        True,
    ),
    "u along Y, normal out": (
        lambda p: (p[1], p[0], _FRONT_Z - p[2]),
        lambda u, v: (v, u),
        True,
    ),
}


@pytest.mark.parametrize("frame", list(_FRAMES))
@pytest.mark.parametrize(
    ("feature", "base", "width"),
    [
        ("ClampSlotProfile", "ClampSlot", part.CLAMP_SLOT_WIDTH),
        ("ClampSlotCboreProfile", "ClampSlotCbore", part.CLAMP_SLOT_CBORE_WIDTH),
    ],
)
def test_slot_profiles_run_along_the_bar_in_any_sketch_frame(
    monkeypatch, frame, feature, base, width
) -> None:
    """Whatever axes the front-face sketch gets, each west slot's stadium runs
    along the bar on its station at mid-height, its width and run carry the
    print's names (the outer slot's bare, the inner's numbered), and the cut
    direction follows the sketch normal."""
    import _sketch

    to_sketch, to_model, normal_out = _FRAMES[frame]
    run = part.CLAMP_SLOT_RUN
    values: list[float] = []
    names: list[str] = []
    lines: dict[str, tuple[float, float, float, float]] = {}
    arcs: dict[str, tuple[float, float]] = {}
    anchors: list[tuple[float, float]] = []

    class _Adapter:
        async def create_sketch(self, plane):
            assert plane == part.FRONT_FACE_PLANE
            return plane

        async def add_line(self, *points):
            key = f"line{len(lines)}"
            lines[key] = points
            return key

        async def add_arc(self, cu, cv, *_ends):
            key = f"arc{len(arcs)}"
            arcs[key] = (cu, cv)
            return key

        async def add_sketch_constraint(self, *args):
            return args

        async def exit_sketch(self):
            return None

    async def anchor(_adapter, _point, u, v, _label):
        anchors.append((u, v))
        values.extend(abs(c) for c in (u, v) if c != 0.0)

    async def dimension(_adapter, _a, _b, _kind, value, _label):
        values.append(value)

    async def defined(_adapter, _label):
        return None

    monkeypatch.setattr(part, "_sketch_uvw", lambda _adapter, p: to_sketch(p))
    monkeypatch.setattr(part, "check", lambda _label, result: result)
    monkeypatch.setattr(part, "set_sketch_direct_db", lambda *_args: None)
    monkeypatch.setattr(part, "anchor_point_to_origin", anchor)
    monkeypatch.setattr(part, "dimension_between", dimension)
    monkeypatch.setattr(part, "ensure_fully_defined", defined)
    monkeypatch.setattr(part, "name_last_feature", lambda *_args: None)
    monkeypatch.setattr(_sketch, "_feature_by_name", lambda _adapter, name: name)
    monkeypatch.setattr(_sketch, "_display_dimensions", lambda _f, _n: list(values))
    monkeypatch.setattr(
        _sketch,
        "_rename_dimensions",
        lambda _dims, _f, recorded: names.extend(recorded),
    )
    jobs, out = asyncio.run(
        part._author_clamp_slot_profile(_Adapter(), feature, base, width, run)
    )
    assert jobs == []
    assert out is normal_out
    end_axis = "V" if frame.startswith("u along Y") else "U"
    assert names == [
        f"{base}Width",
        f"{base}Travel",
        f"{base}End{end_axis}",
        f"{base}Width1",
        f"{base}Travel1",
        f"{base}End{end_axis}1",
    ]
    slots = sorted(part.CLAMP_SLOT_X, reverse=True)
    ends = [to_model(*anchor) for anchor in anchors]
    assert len(ends) == len(slots)
    # Each slot's width, its run, then its end's one off-axis station.
    assert values == pytest.approx(
        [value for x, _y in ends for value in (width, run, abs(x))]
    )
    # Two sides and two ends a slot, the outer slot first.
    assert len(lines) == len(arcs) == 2 * len(slots)
    for index, slot_x in enumerate(slots):
        sides = list(lines.values())[2 * index : 2 * index + 2]
        for u0, v0, u1, v1 in sides:
            (x0, y0), (x1, y1) = to_model(u0, v0), to_model(u1, v1)
            assert y0 == pytest.approx(y1)
            assert abs(y0) == pytest.approx(width / 2.0)
            assert sorted((x0, x1)) == pytest.approx(
                [slot_x - run / 2.0, slot_x + run / 2.0]
            )
        centres = sorted(
            to_model(*centre)
            for centre in list(arcs.values())[2 * index : 2 * index + 2]
        )
        assert centres == [
            pytest.approx((slot_x - run / 2.0, 0.0)),
            pytest.approx((slot_x + run / 2.0, 0.0)),
        ]
        assert ends[index][1] == pytest.approx(0.0)
        assert abs(ends[index][0] - slot_x) == pytest.approx(run / 2.0)

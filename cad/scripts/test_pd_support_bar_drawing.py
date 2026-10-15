"""Offline contracts for the support-bar drawing (MHA-PD-007)."""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

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
    kept = [*drawing.FRONT_KEEP, *drawing.BACK_KEEP, *drawing.SECTION_KEEP_NAMES]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert set(drawing.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.DIMENSION_CALLOUTS) <= marked


def test_printed_bands_are_the_spec_bands() -> None:
    assert model_toleranced_dimensions(part) == {
        ("HangerRowReference", "name"): "HOLE_POSITION_BAND",
        ("ClampRowReference", "name"): "CLAMP_POSITION_BAND",
        ("PivotTap", "DrillDepth"): "*PIVOT_TAP_DRILL_DEPTH_LIMITS",
    }
    assert part.HANGER_STATION_NAMES == sheet_spec.HANGER_STATION_NAMES
    assert part.CLAMP_STATION_NAMES == sheet_spec.CLAMP_STATION_NAMES
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'for name in ("HangerRowHeight", *HANGER_STATION_NAMES):' in source
    assert 'for name in ("ClampRowHeight", *CLAMP_STATION_NAMES):' in source
    assert spec.HOLE_POSITION_BAND == 0.065
    assert spec.PIVOT_TAP_DRILL_DEPTH_LIMITS == (-0.4, 0.0)
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
    assert places["PivotTap"]["DrillDepth"] == 1


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
        (
            "'PivotThreadReference'",
            "'ThreadMin'",
            "PIVOT_TAP_FULL_THREAD_MIN",
            "TOL_MIN",
        ),
        ("'CountersinkReference'", "'PivotCskDia'", "PIVOT_TAP_CSK_DIA", "TOL_MAX"),
        (
            "'CountersinkReference'",
            "'BracketCskDia'",
            "BRACKET_TAP_CSK_DIA",
            "TOL_MAX",
        ),
    }
    assert (sheet_spec.TOL_MIN, sheet_spec.TOL_MAX) == (5, 6)
    assert spec.PIVOT_TAP_FULL_THREAD_MIN == 5.2
    assert (spec.PIVOT_TAP_CSK_DIA, spec.BRACKET_TAP_CSK_DIA) == (4.3, 3.1)


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
    assert part.CLAMP_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0


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
    assert "MHA-VN-043" in callouts["Depth"]
    assert "MHA-VN-041" in callouts["HangerRowHeight"]
    assert "MHA-PD-014" in callouts["HangerRowHeight"]
    # Each tight hanger station names the part it places.
    assert "MHA-VN-041" in callouts["PivotTapStation"]
    assert "MHA-PD-014" in callouts["BracketTapStation1"]
    assert "MHA-PD-014" in callouts["BracketTapStation2"]
    # The thread class is the title block's (rule 2), native callout too.
    assert callouts["PivotTapDrillDia"] == "TAP #8-32 UNC"
    assert "2B" not in "".join(callouts.values())
    assert drawing._THREAD_CLASS_TOKEN == " <hw-threadclass>"
    assert callouts["DrillDepth"] == "FLAT BOTTOM"
    # Rule 20: the blind thread's shortfall against 1.5D, stated as a fact.
    assert callouts["ThreadMin"] == "FULL THREAD (1.25D)"
    assert spec.PIVOT_TAP_FULL_THREAD_MIN < 1.5 * spec.THREAD_MAJOR_MM["#8-32"]
    assert callouts["BracketCskDia"].startswith("2X 90\u00b0 CSK")
    for text in callouts.values():
        assert len(text.splitlines()) <= 3
    # The banded clamp row names the back-arc taps it locates to, then the
    # screws whose heads the counterbores sink.
    assert sheet_spec.CLAMP_CBORE_CALLOUT.splitlines() == [
        "LOCATE TO MHA-SH-002 TAPS",
        "MHA-VN-021 HEADS BELOW SLIDE FACE",
    ]


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
        'name_dimensions(adapter, "PivotTap", ["DrillDepth"])',
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
            (max(part.CLAMP_ROW_X), 0.0, -spec.BAR_DEPTH / 2.0),
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

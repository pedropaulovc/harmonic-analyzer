"""Offline contracts for the support-bar drawing (MHA-PD-07)."""

from __future__ import annotations

import math
import re

import pytest

import _config
from _column_clamp_interface import BAR_DEPTH
from _inch_wall_limits import WALL_TARGET_MM
from _surface_finish import surface_finish_by_key
import build_pd_support_bar as part
import draw_pd_support_bar as drawing
import pd_support_bar_drawing_spec as sheet_spec
import pd_support_bar_spec as spec


def test_printed_mating_numbers_resolve_to_the_registered_parts() -> None:
    registered = {row["number"] for row in _config.parts().values()}
    references = (
        (drawing.DIMENSION_CALLOUTS["ClampSlotWidth"], "sh-vn-clamp-screw"),
        (drawing.DIMENSION_CALLOUTS["Depth"], "pd-vn-transgear-pivot-screw"),
        (drawing.CLAMP_CBORE_CALLOUT, "sh-vn-clamp-screw"),
        (drawing.DIMENSION_CALLOUTS["PivotCskDia"], "pd-vn-transgear-pivot-screw"),
        (drawing.DIMENSION_CALLOUTS["BracketCskDia"], "pd-latch-hook"),
        (
            surface_finish_by_key(sheet_spec.SURFACE_FINISHES, "top_slide").production_method,
            "pd-platen-guide",
        ),
        (
            surface_finish_by_key(sheet_spec.SURFACE_FINISHES, "front_slide").production_method,
            "pd-platen",
        ),
    )
    for text, mate in references:
        printed = set(re.findall(r"\bMHA-[A-Z0-9]+(?:-[A-Z0-9]+)+\b", text))
        assert printed <= registered, printed - registered
        assert _config.parts(mate)["number"] in printed


def test_printed_bands_match_the_bar_and_drilled_slot_limits() -> None:
    from _drawing_contract import model_toleranced_dimensions
    from _printed_tolerance import drilled_oversize_mm, printed_deviations

    # The height's band is the printed .XX limit's furthest reach from the mm
    # nominal (both on their grid, #290; owner ruling 2026-11-20, #2421). The
    # thickness is the 3/8 CF flat as supplied, .374 +.001/-.003 at .XXX
    # (owner ruling 2026-11-21, #1563 option C), authored on the model.
    assert (spec.BAR_HEIGHT_PLACES, spec.BAR_DEPTH_PLACES) == (2, 3)
    lower, upper = printed_deviations(
        spec.BAR_HEIGHT, spec.BAR_HEIGHT_PLACES, unit="in"
    )
    assert spec.BAR_HEIGHT_BAND == max(-lower, upper)
    assert spec.BAR_HEIGHT == pytest.approx(1.00 * 25.4)
    assert spec.BAR_HEIGHT_BAND == pytest.approx(0.254)
    assert spec.BAR_DEPTH_LIMITS == pytest.approx((-0.003 * 25.4, 0.001 * 25.4))
    assert (spec.BAR_DEPTH_MIN, spec.BAR_DEPTH_MAX) == pytest.approx(
        (0.371 * 25.4, 0.375 * 25.4)
    )
    assert spec.BAR_DEPTH_REACH == pytest.approx(0.003 * 25.4)
    toleranced = model_toleranced_dimensions(part)
    assert toleranced[("Bar", "Depth")] == "*BAR_DEPTH_LIMITS"
    assert part.CLAMP_SLOT_WIDTH_LIMITS == (0.0, drilled_oversize_mm(unit="in"))


def test_slot_width_band_is_accepted_as_the_cutters_spread() -> None:
    """D52 (delegated ruling 2026-11-26): the slots keep .196 +.004/.000 on an
    accept exception, not a necessity entry (no failure at the looser size is
    shown). Its reason rests on the plan's programmed .199 cut by the 1/8 in
    end mill (-.002/0) inside the band, and the pins the plan names."""
    import tomllib

    import _process_plans
    from _printed_tolerance import drilled_oversize_mm

    entries = {
        entry["id"]: entry
        for entry in _config.parts("pd-support-bar")["machinist_exceptions"]
    }
    entry = entries["RV-04"]
    assert entry["kind"] == "accept"
    assert "2X .196 +.004/.000 THRU, CLEARANCE FOR MHA-SH-VN-53" in entry["where"]
    assert entry["reason"].startswith(
        "Delegated ruling 2026-11-26 (Main), no precedent; owner review #2144 (D52)."
    )
    plan = tomllib.loads(_process_plans.plan_path("pd_support_bar").read_text(encoding="utf-8"))
    programmed = plan["parameters"]["slot_width_mm"]
    low, high = 0.196 * 25.4, 0.196 * 25.4 + drilled_oversize_mm(unit="in")
    assert part.CLAMP_SLOT_WIDTH_LIMITS == (0.0, drilled_oversize_mm(unit="in"))
    assert programmed == pytest.approx(0.199 * 25.4, abs=1e-3)
    assert low <= programmed - 0.002 * 25.4 and programmed <= high
    assert ".196 pin slides" in str(plan) and ".200 does not enter" in str(plan)


def test_hook_tap_stations_are_reference_and_the_pivot_row_is_unbanded() -> None:
    """Round 3 machinist review (over-specification): SPOT THRU MHA-PD-14 AT
    ASSEMBLY sets the hook taps' stations, so they print REF with no band.
    The row height and the pivot's station print .XXX under the title block's
    ±.005 (owner ruling 2026-11-20, #2422; it was ±.002, RV-01)."""
    from _printed_tolerance import printed_band_mm

    reference = set(sheet_spec.HOOK_TAP_REFERENCE_NAMES)
    assert reference == {"BracketTapStation1", "BracketTapStation2"}
    assert not hasattr(sheet_spec, "BANDED_HANGER_NAMES")
    assert not hasattr(spec, "HOLE_POSITION_TOL")
    assert sheet_spec.SHEET_PRECISION["HangerRowReference"] == dict.fromkeys(
        ("HangerRowHeight", *sheet_spec.HANGER_STATION_NAMES), 3
    )
    # The stacks read the printed reach: the title block's band plus half a
    # .001 step, the stations being off the grid.
    assert spec.HOLE_POSITION_BAND == pytest.approx(
        printed_band_mm(3, unit="in") + 0.0005 * 25.4
    )
    ids = {
        entry["id"] for entry in _config.parts("pd-support-bar")["machinist_exceptions"]
    }
    assert "RV-01" not in ids
    assert "SPOT THRU MHA-PD-14" in sheet_spec.DIMENSION_CALLOUTS["BracketCskDia"]


def test_clamp_holes_find_the_back_arc_taps_at_the_printed_worst_case() -> None:
    """Review of PR #1471: the clamp row printed .X (±0.8), whose 2.263
    position zone over-runs the 0.812 the #8 clearance holes float on the
    #8-32 shanks. Fixed fastener: each screw threads into an MHA-SH-02
    back-arc tap held ±.004 along the bar and in height (sh_column_clamp_fit),
    so the bar's zone (2·√2·band, plus the print's rounding) plus the tap's
    must stay inside the least hole's float; the title block's .XXX ±.005
    does (delegated ruling 2026-11-07). A drift in the band, the hole, the
    shank or the taps' bands breaks one of these."""
    from _hole_spec import HoleSpec, blind_cut_dia_mm
    from _printed_tolerance import printed_band_mm
    from sh_column_clamp_back_geom import HOLE_SPEC as BACK_ARC_TAP
    from sh_column_clamp_fit import EAR_HEIGHT_BAND, EAR_STATION_BAND
    from sh_vn_clamp_screw_spec import SHANK_DIA

    # The mate: #8-32 taps in the back arc, located ±.004 on both axes.
    assert (BACK_ARC_TAP.kind, BACK_ARC_TAP.size) == ("tapped", "#8-32")
    assert EAR_STATION_BAND == EAR_HEIGHT_BAND == 0.1016
    tap_zone = 2.0 * math.hypot(EAR_STATION_BAND, EAR_HEIGHT_BAND)
    # The float: the least drilled #8 clearance hole over the basic major.
    assert part.CLAMP_THROUGH_HOLE_SPEC == HoleSpec("clearance", "#8")
    assert part.DRILLED_HOLE_LIMITS[0] == 0.0
    hole_min = blind_cut_dia_mm(part.CLAMP_THROUGH_HOLE_SPEC)
    assert (hole_min, SHANK_DIA) == pytest.approx((4.978, 4.1656))
    hole_float = hole_min - SHANK_DIA
    assert part.CLAMP_HOLE_FLOAT == pytest.approx(hole_float)

    def zone(band: float) -> float:
        return 2.0 * math.sqrt(2.0) * band

    # The .XXX print rounds the mm stations, so the zone carries that
    # rounding on top of the band's.
    band = part.CLAMP_POSITION_BAND
    assert band == pytest.approx(printed_band_mm(3, unit="in")) == pytest.approx(0.127)
    assert part.clamp_position_zone(band) >= zone(band)
    assert part.BACK_ARC_TAP_ZONE == pytest.approx(tap_zone)
    assert part.clamp_position_zone(band) + tap_zone <= hole_float  # .653 <= .812


def test_row_nominals_are_the_built_holes() -> None:
    left = -part.BAR_LENGTH / 2.0
    assert part.HANGER_ROW_HEIGHT == spec.BAR_HEIGHT / 2.0 - spec.HANGER_TAP_Y == 14.5
    assert part.HANGER_STATIONS == pytest.approx(
        tuple(x - left for x in (spec.PIVOT_TAP_X, *spec.BRACKET_TAP_X))
    )
    assert part.HANGER_STATIONS == pytest.approx((168.06, 291.06, 298.06))
    # Both rows read from the same (left, x = -226.06) end.
    assert part.CLAMP_ROW_START_X == left
    assert part.CLAMP_ROW_X == (-214.503, -179.5018, 179.5018, 214.503)
    assert sorted(part.CLAMP_ROW_X) == sorted(part.CLAMP_HOLE_X)
    assert part.CLAMP_STATIONS == pytest.approx((11.557, 46.5582, 405.5618, 440.563))
    # END A's (east, -X) pair are round and locate the bar; the west pair are
    # the slots (owner ruling 2026-10-15, option A).
    assert sorted(part.CLAMP_ROUND_X) == [-214.503, -179.5018]
    assert sorted(part.CLAMP_SLOT_X) == [179.5018, 214.503]
    assert sorted((*part.CLAMP_ROUND_X, *part.CLAMP_SLOT_X)) == list(part.CLAMP_ROW_X)
    # The clamp line keeps its machine height under the bar's top edge (the
    # SH column clamps), so it stands off the shortened bar's centre.
    assert part.CLAMP_ROW_HEIGHT == pytest.approx(14.0)
    assert part.CLAMP_ROW_HEIGHT == pytest.approx(spec.BAR_HEIGHT / 2.0 - spec.CLAMP_TAP_Y)


def test_each_row_draws_its_own_centreline() -> None:
    """Round 4 machinist review (rule 26): one drawn line ran through the
    .571 taps and the .551 clamp holes, .020 apart. Each row's sketch draws
    runs through its own holes only, no stretch of the bar under both rows'
    runs, every run clearing the other row's widest rings; the .551 reads off
    the clamp run at the +X end, the .571 off the tap run's end."""
    taps, clamps = part.HANGER_ROW, part.CLAMP_ROW
    assert part.ROW_CENTRELINES == (taps, clamps)
    for row in (taps, clamps):
        on_runs = [name for run in row.runs for name, _ in part._run_holes(row, run)]
        assert sorted(on_runs) == sorted(name for name, _ in row.holes)
    # The other row's rings: the slot counterbores reach 5.75 off their
    # centres, the round ones 3.97, the countersinks 2.15.
    slot_reach = part.CLAMP_SLOT_RUN / 2.0 + part.CLAMP_SLOT_CBORE_WIDTH / 2.0
    csk_reach = spec.PIVOT_TAP_CSK_DIA / 2.0
    for start, end in taps.runs:
        for x in part.CLAMP_ROW_X:
            assert x + slot_reach < start or end < x - slot_reach, x
    for start, end in clamps.runs:
        for _, x in taps.holes:
            assert x + csk_reach < start or end < x - csk_reach, x
    assert clamps.runs[-1][1] == part.BAR_LENGTH / 2.0
    assert taps.runs[-1][1] == sheet_spec.HANGER_HEIGHT_X
    line_x = drawing.FRONT_KEEP["HangerRowHeight"][0]
    assert line_x == pytest.approx(
        drawing._face_x(sheet_spec.HANGER_HEIGHT_X) + drawing.HANGER_ROW_LINE_SIDE
    )
    # The run's end stands clear past the hook taps' countersinks and short
    # of the west slots' counterbores, the text's lane over the top face.
    assert sheet_spec.HANGER_HEIGHT_X > spec.BRACKET_TAP_X[1] + 0.020 / drawing._S
    assert sheet_spec.HANGER_HEIGHT_X < min(part.CLAMP_SLOT_X) - slot_reach


def test_round_pair_run_reads_its_own_height_in_the_principal_view() -> None:
    """Round 7 review blocker: the round pair's east run carried no height,
    the .551 reading only off the west (slots') run. The east run reads its
    own .551 off its end in the principal view, the back face, which imports
    it (VIEW D's import deletes it as unrequested, as the principal view's
    deletes the bar height). Round 7's native layout: the .571 text sat on
    its line's shelf, 6.4 mm tall, 2.45 mm a character; the top slide
    symbol's leader drops at 0.0807 from its shelf at 0.2424."""
    name = sheet_spec.CLAMP_EAST_HEIGHT_NAME
    clamps = part.CLAMP_ROW
    assert clamps.run_heights == (name,)
    assert name in sheet_spec.DRAWING_DIMENSIONS["ClampRowReference"]
    assert name in drawing.FRONT_KEEP and name not in drawing.BACK_KEEP
    assert sheet_spec.SHEET_PRECISION["ClampRowReference"][name] == 3
    # It is a location: no band of its own, no words (title block ±.005).
    assert name not in drawing.DIMENSION_CALLOUTS
    line_x, text_y = drawing.FRONT_KEEP[name]
    assert line_x == pytest.approx(
        drawing._face_x(clamps.runs[0][1]) + drawing.HANGER_ROW_LINE_SIDE
    )
    assert text_y == drawing.FRONT_KEEP["HangerRowHeight"][1]
    text = f"{part.CLAMP_ROW_HEIGHT / 25.4:.3f}".lstrip("0")
    box = (line_x, text_y - 0.0032, line_x + len(text) * 0.00245, text_y + 0.0032)
    leader_x, shelf_y = 0.0807, 0.2424
    assert drawing._face_x(drawing.TOP_FINISH_MODEL_X) == pytest.approx(leader_x, abs=5e-4)
    assert box[0] - leader_x >= 0.005
    assert shelf_y - box[3] >= 0.003
    assert box[1] - drawing.FACE_TOP >= 0.002
    # Right of the run's end, past the inner round hole's ring.
    assert line_x - drawing._face_x(max(part.CLAMP_ROUND_X)) > 0.005
    # Well left of section A-A's letters (0.1208).
    assert 0.1208 - box[2] >= 0.015


def test_tap_row_height_text_clears_the_hook_leader_and_both_shoulders() -> None:
    """The .571 reads off the tap run's end with its one-row text over the top
    face. Round 2's native layout: each countersink callout's bottom shoulder
    stands 11.1 mm under its keep and runs from 41.9 mm left of it to 40.4
    right; the hook pair's leader runs from its right hole to that left end.
    Both callouts rise together, so the hook leader still passes under the
    pivot block's last row; the text (2.76 mm a character, 6.4 mm tall,
    starting 1.5 mm right of its line) stands right of that leader, under the
    shoulders and over the top face."""
    shoulder_drop, shoulder_left = 0.0111, 0.0419
    hook_x, hook_y = drawing.FRONT_KEEP["BracketCskDia"]
    pivot_x, pivot_y = drawing.FRONT_KEEP["PivotCskDia"]
    assert hook_y == pivot_y == drawing.FACE_TOP + drawing.CSK_CALLOUT_RISE
    shoulder_y = hook_y - shoulder_drop
    hole = (
        drawing._face_x(spec.BRACKET_TAP_X[1]),
        drawing.FACE_TOP - part.HANGER_ROW_HEIGHT * drawing._S,
    )
    knee = (hook_x - shoulder_left, shoulder_y)

    def leader_x(y: float) -> float:
        return hole[0] + (y - hole[1]) * (knee[0] - hole[0]) / (knee[1] - hole[1])

    line_x, text_y = drawing.FRONT_KEEP["HangerRowHeight"]
    text = f"{part.HANGER_ROW_HEIGHT / 25.4:.3f} \u00b1.002".lstrip("0")
    box = (line_x + 0.0015, text_y - 0.0032, line_x + 0.0015 + len(text) * 0.00276, text_y + 0.0032)
    assert box[1] - drawing.FACE_TOP >= 0.002
    assert shoulder_y - box[3] >= 0.002
    assert box[0] - leader_x(box[3]) >= 0.003
    # Its line, from the row up to the text, stays right of the leader too.
    assert line_x - leader_x(text_y) >= 0.003
    # The hook leader passes under the pivot block's bottom row's right end.
    pivot_row_right = pivot_x + len("LOCATES MHA-PD-VN-57") * 0.00264 / 2.0
    assert knee[0] > pivot_row_right
    assert (pivot_y - shoulder_drop) - (
        hole[1] + (pivot_row_right - hole[0]) * (knee[1] - hole[1]) / (knee[0] - hole[0])
    ) >= 0.0015
    # Under the border.
    assert hook_y + 0.0116 < 0.2667 - 0.002


def test_rows_stack_shortest_nearest_the_bar() -> None:
    def heights(keep: dict, names: tuple[str, ...]) -> list[float]:
        return [keep[name][1] for name in names]

    face = heights(drawing.FRONT_KEEP, (*sheet_spec.HANGER_STATION_NAMES, "Length"))
    back = heights(drawing.BACK_KEEP, sheet_spec.CLAMP_STATION_NAMES)
    # The front face's long rows step 6 and 7 mm so the 17.345 line clears
    # detail C's counterbore-width callout under it (machinist review).
    for rows, bar_bottom, step in (
        (face, drawing.FACE_BOTTOM, 0.008),
        (back, drawing.BACK_BOTTOM, 0.006),
    ):
        assert all(y < bar_bottom for y in rows)
        assert all(a - b >= step - 1e-9 for a, b in zip(rows, rows[1:]))
    # Long-row texts stay between their extension lines.
    for name, span in zip(
        (*sheet_spec.HANGER_STATION_NAMES[1:], "Length"),
        (*part.HANGER_STATIONS[1:], part.BAR_LENGTH),
    ):
        x = drawing.FRONT_KEEP[name][0]
        assert drawing.LEFT_END < x < drawing.LEFT_END + span * drawing._S
    # In the front-face view that end is on the sheet's right: the long clamp
    # rows' texts stand between it and their holes; the first two rows' stand
    # right of the end's extension line (the first's text is wider than its
    # span) and left of the isometric view (its r6 outline's left edge), at a
    # conservative 2.76 mm a character (2.3 measured).
    iso_left = 0.3216
    for name, station, hole_x in zip(
        sheet_spec.CLAMP_STATION_NAMES, part.CLAMP_STATIONS, part.CLAMP_ROW_X
    ):
        x = drawing.BACK_KEEP[name][0]
        text = f"{station / 25.4:.3f}".lstrip("0")
        half = len(text) * 0.00276 / 2.0
        if x < drawing.RIGHT_END:
            assert drawing._back_x(hole_x) < x - half < x + half < drawing.RIGHT_END
        else:
            assert drawing.RIGHT_END < x - half < x + half < iso_left, name
    first = drawing.RIGHT_END - drawing._back_x(part.CLAMP_ROW_X[0])
    assert drawing.BACK_KEEP["ClampStation1"][0] > drawing.RIGHT_END
    assert first < len(f"{part.CLAMP_STATIONS[0] / 25.4:.3f}".lstrip("0")) * 0.00276


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


def test_slide_faces_carry_the_slide_grade() -> None:
    from _surface_finish import MACHINED_UM

    controls = {control.key: control for control in sheet_spec.SURFACE_FINISHES}
    assert set(controls) == {"top_slide", "front_slide"}
    assert {control.roughness_um for control in controls.values()} == {MACHINED_UM}
    top, front = controls["top_slide"].face, controls["front_slide"].face
    assert (top.normal, top.offset_mm) == ((0, 1, 0), spec.BAR_HEIGHT / 2.0)
    assert (front.normal, front.offset_mm) == ((0, 0, -1), BAR_DEPTH / 2.0)
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


def _printed_cbore_depth_limits() -> tuple[float, float]:
    from _printed_tolerance import printed_deviations

    lower, upper = printed_deviations(
        part.CLAMP_CBORE_DEPTH, sheet_spec.CLAMP_CBORE_DEPTH_PLACES, unit="in"
    )
    return part.CLAMP_CBORE_DEPTH + lower, part.CLAMP_CBORE_DEPTH + upper


def test_clamp_heads_stay_under_the_front_face_at_the_printed_worst_case() -> None:
    shallowest, deepest = _printed_cbore_depth_limits()
    # The depth is a clearance: .XX, its nominal deep enough for the band.
    # The platen slides across the front face: the head never stands proud,
    # even at the depth's printed minimum.
    assert part.CLAMP_HEAD_H < shallowest
    # Rule 17: the floor under the deepest counterbore in the thinnest bar.
    assert spec.BAR_DEPTH_MIN - deepest >= WALL_TARGET_MM


def test_clamp_screws_engage_the_back_arc_and_stop_inside_it() -> None:
    # Head seat -> rest of the bar -> front arc -> the open grip gap (the back
    # arc's mating face stops GRIP_OFFSET short of the column axis) ->
    # threads into the back arc's through tap (build_pd_paper_drive_assembly's
    # clamp stack), over the printed depth and thickness bands; the arcs at
    # their nominals.
    from sh_column_clamp_back_geom import BLOCK_DEPTH as back_block
    from sh_column_clamp_back_geom import GRIP_OFFSET as grip_gap
    from _column_clamp_interface import ARC_DEPTH as front_arc
    from sh_vn_clamp_screw_spec import SHANK_DIA, SHANK_LEN

    shallowest, deepest = _printed_cbore_depth_limits()
    thick = spec.BAR_DEPTH_MAX
    thin = spec.BAR_DEPTH_MIN
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
    from _printed_tolerance import printed_band_mm
    from sh_column_clamp_fit import (
        BORE_DIAMETRAL_CLEARANCE,
        EAR_HEIGHT_BAND,
        EAR_STATION_BAND,
    )
    from sh_vn_clamp_screw_spec import SHANK_DIA

    # The pitch's sources (mm frame prints): the top frame dimensions its
    # socket pitch at .XX; the base's hole table prints each socket's X at
    # .XX, two bands apart.
    top, base = printed_band_mm(2), 2.0 * printed_band_mm(2)
    assert (top, base) == pytest.approx((0.51, 1.02))
    assert sorted(part.COLUMN_PITCH_DEVIATIONS.values()) == pytest.approx([top, base])
    # A shank's slack along the bar in the least #8 hole (the model's 4.978,
    # the printed .196) at the worst height misalignment.
    radial = (4.978 - SHANK_DIA) / 2.0
    station = part.CLAMP_POSITION_BAND
    assert station == pytest.approx(0.127)  # the title block's ±.005
    height = station + EAR_HEIGHT_BAND
    slack = math.sqrt(radial**2 - height**2)
    assert slack == pytest.approx(0.3358, abs=1e-4)
    # Each slot's least travel each way: its .118 run at .XXX.
    assert part.CLAMP_SLOT_RUN == 2.0 * part.CLAMP_SLOT_TRAVEL == 2.9972
    assert part.CLAMP_SLOT_WIDTH == part.CLAMP_HOLE_DIA == pytest.approx(4.978)
    travel = (part.CLAMP_SLOT_RUN - printed_band_mm(3, unit="in")) / 2.0
    # Between an east and a west screw: both bar stations, both clamps' tap
    # stations and both clamps' shift on their columns.
    between = 2.0 * (station + EAR_STATION_BAND + BORE_DIAMETRAL_CLEARANCE[1] / 2.0)
    assert between == pytest.approx(0.762)
    for pitch, margin in ((top, 0.8346), (base, 0.3246)):
        left = travel + 2.0 * slack - (pitch + between)
        assert left == pytest.approx(margin, abs=5e-4)
        assert part.clamp_slot_closure_margin(pitch) == pytest.approx(left)
    # Round west holes would not close even the top frame's pitch.
    assert 2.0 * slack - (top + between) < 0.0
    # The east pair share one clamp: only their stations and taps open it.
    east = 2.0 * slack - 2.0 * (station + EAR_STATION_BAND)
    assert east == pytest.approx(0.2143, abs=1e-4)
    assert part.clamp_east_pair_margin() == pytest.approx(east)


def test_slot_heads_bear_and_stay_inside_their_counterbores() -> None:
    """The stock MHA-SH-VN-53 head over a slot: at the shank's full float across
    the widest slot it still overlaps the counterbore floor by the round
    holes' own least (the same Ø.196 +.004/-0), and anywhere the shank reaches
    in the longest slot it stays inside the narrowest, shortest counterbore."""
    from _printed_tolerance import drilled_oversize_mm, printed_band_mm
    from sh_vn_clamp_screw_spec import HEAD_DIA, SHANK_DIA

    head_r = HEAD_DIA / 2.0
    widest = 0.196 * 25.4 + drilled_oversize_mm(unit="in")
    shift = (widest - SHANK_DIA) / 2.0
    bearing = head_r - widest / 2.0 - shift
    assert bearing == pytest.approx(0.4318, abs=1e-4)
    assert part.CLAMP_HEAD_BEARING_MIN == pytest.approx(bearing)
    assert part.clamp_head_bearing(widest) == pytest.approx(bearing)
    band = printed_band_mm(3, unit="in")
    run = part.CLAMP_SLOT_RUN
    overrun = ((run + band) - (run - band)) / 2.0
    reach = head_r + shift + overrun
    lower, upper = sheet_spec.CLAMP_SLOT_CBORE_WIDTH_LIMITS
    room = (part.CLAMP_SLOT_CBORE_WIDTH + lower) / 2.0  # .335 printed exactly
    assert room - reach == pytest.approx(0.1778, abs=1e-4)
    assert part.clamp_slot_head_clearance() == pytest.approx(room - reach)
    # The explicit minimum preserves the proven head envelope; the maximum
    # is relaxed on a clearance feature.
    assert lower == -band
    assert upper >= printed_band_mm(2, unit="in")
    # The slot counterbore stays .335, cut as deep as the round ones, which
    # are the 5/16 plunge (owner ruling 2026-11-20, #2422).
    assert part.CLAMP_SLOT_CBORE_WIDTH == 8.509
    assert part.CLAMP_CBORE_DIA == 5.0 / 16.0 * 25.4
    assert part.CLAMP_SLOT_CBORE_RUN == part.CLAMP_SLOT_RUN


def test_round_counterbores_are_the_5_16_plunge_and_clear_the_head() -> None:
    """Owner ruling 2026-11-20 (#2422): the round counterbores print Ø.3125
    +.010/0, a 5/16 end mill's plunge, in four places so the low limit is the
    cutter. The MHA-SH-VN-53 head, its shank floated across the widest Ø.196
    hole, still clears the narrowest counterbore; at the .XX row's -.01 it
    would not."""
    from _printed_tolerance import drilled_oversize_mm, printed_deviations
    from sh_vn_clamp_screw_spec import HEAD_DIA, SHANK_DIA

    assert sheet_spec.CLAMP_CBORE_DIA_LIMITS == pytest.approx((0.0, 0.010 * 25.4))
    assert sheet_spec.CLAMP_CBORE_DIA_PLACES == 4
    assert sheet_spec.CLAMP_CALLOUT_PRECISION["hw-cbdia"] == 4
    assert sheet_spec.CLAMP_CBORE_DIA_LIMIT_PLACES == 4
    assert (
        part.CLAMP_HOLE_SPEC.overrides_mm["CounterBoreDiameter"] == part.CLAMP_CBORE_DIA
    )
    widest = 0.196 * 25.4 + drilled_oversize_mm(unit="in")
    shift = (widest - SHANK_DIA) / 2.0
    clearance = 0.3125 * 25.4 / 2.0 - (HEAD_DIA / 2.0 + shift)
    assert clearance == pytest.approx(0.0826, abs=1e-4)
    assert part.clamp_round_head_clearance() == pytest.approx(clearance)
    lower, _ = printed_deviations(part.CLAMP_CBORE_DIA, 2, unit="in")
    assert (part.CLAMP_CBORE_DIA + lower) / 2.0 - (HEAD_DIA / 2.0 + shift) < 0.0


def test_clamp_screw_line_wander_shortfall_stays_the_owner_ruled_value() -> None:
    """Owner ruling 2026-11-20 (#1988): with drill wander charged (the
    MHA-SH-02 back-arc tap's and this bar's through hole's, 0.3 deg), the
    clamp screw stands up to 0.051 past its hole's radial float at the worst
    corner, as on the MHA-MG-08 wheel bar; the shortfall may not grow."""
    from sh_column_clamp_fit import BACK_EAR_WANDER

    wander = spec.BAR_DEPTH_MAX * math.tan(math.radians(0.3))
    assert part.CLAMP_BAR_HOLE_WANDER == pytest.approx(wander)
    demand = (
        part.clamp_position_zone(part.CLAMP_POSITION_BAND) / 2.0
        + part.BACK_ARC_TAP_ZONE / 2.0
        + BACK_EAR_WANDER
        + wander
    )
    assert part.CLAMP_SCREW_LINE_DEMAND == pytest.approx(demand)
    assert part.CLAMP_SCREW_LINE_SHORTFALL == pytest.approx(
        demand - part.CLAMP_HOLE_FLOAT / 2.0
    )
    assert part.CLAMP_SCREW_LINE_SHORTFALL == pytest.approx(0.0500, abs=1e-4)
    assert part.CLAMP_SCREW_LINE_SHORTFALL_RULED == 0.051
    # Rule 20: the sheet states it, rounded up, and RV-03 declares that note.
    from sh_column_clamp_fit import note_text, stated_max

    stated = note_text(stated_max(part.CLAMP_SCREW_LINE_SHORTFALL))
    assert stated == ".002"
    note = " ".join(drawing.SCREW_LINE_NOTE.split())
    assert note.startswith("1. ")
    assert f"OFFSET UP TO {stated} OVER #8" in note
    assert sheet_spec.CLAMP_CBORE_CALLOUT.endswith("SEE NOTE 1")
    entries = {
        entry["id"]: entry
        for entry in _config.parts("pd-support-bar")["machinist_exceptions"]
    }
    assert entries["RV-03"]["kind"] == "minor"
    assert note in entries["RV-03"]["where"]


def test_slot_counterbores_leave_rule_17_walls() -> None:
    """Worst-case walls round the west counterbores: to the bar's west end
    (the .X length short, the outer station long), between the pair's
    counterbores, and to the top and bottom faces."""
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(3, unit="in")
    station = part.CLAMP_POSITION_BAND
    cbore_max = part.CLAMP_SLOT_CBORE_WIDTH + sheet_spec.CLAMP_SLOT_CBORE_WIDTH_LIMITS[1]
    cbore_reach = (part.CLAMP_SLOT_CBORE_RUN + band) / 2.0 + cbore_max / 2.0
    inner, outer = sorted(part.CLAMP_STATIONS)[2:]
    shortest = part.BAR_LENGTH - printed_band_mm(1, unit="in")
    end_wall = shortest - (outer + station) - cbore_reach
    assert end_wall == pytest.approx(2.946, abs=5e-3)
    web = (outer - inner) - 2.0 * station - 2.0 * cbore_reach
    assert web == pytest.approx(22.860, abs=5e-3)
    # The clamp line stands CLAMP_ROW_HEIGHT under the top face, so the
    # bottom face (the height's printed minimum) is the nearer one.
    side = (
        spec.BAR_HEIGHT
        - spec.BAR_HEIGHT_BAND
        - part.CLAMP_ROW_HEIGHT
        - station
        - cbore_max / 2.0
    )
    assert side == pytest.approx(6.638, abs=5e-3)
    for wall in (end_wall, web, side):
        assert wall >= WALL_TARGET_MM
    # Nominally 5.806 to the end, 23.495 between.
    reach = part.CLAMP_SLOT_RUN / 2.0 + part.CLAMP_SLOT_CBORE_WIDTH / 2.0
    assert part.BAR_LENGTH / 2.0 - max(part.CLAMP_SLOT_X) - reach == pytest.approx(5.8039)
    assert max(part.CLAMP_SLOT_X) - min(part.CLAMP_SLOT_X) - 2.0 * reach == pytest.approx(
        23.4950
    )


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
    # r4 review); the label stands over the detail, centred on it (round 7:
    # right of the slot-width text it sat against the title block).
    radius = drawing.DETAIL_RADIUS_MM * drawing.DETAIL_MM
    width_x, width_y = drawing.DETAIL_KEEP["ClampSlotWidth"]
    assert width_x > drawing.DETAIL_CENTER[0] + radius
    edge = drawing.DETAIL_CENTER[1] - part.CLAMP_SLOT_WIDTH * drawing.DETAIL_MM / 2.0
    assert width_y < edge
    assert drawing.DETAIL_LABEL_XY[0] == drawing.DETAIL_CENTER[0]
    # Its letter stands off the bar, past the end and under the clamp row's
    # extension line, right of the row height's dimension line: over the
    # outer slot it printed on section B-B's upper letter (r4 review).
    letter_x, letter_top = drawing.DETAIL_LETTER_TOP
    assert drawing.BACK_KEEP["ClampRowHeight"][0] < letter_x < drawing.LEFT_END
    assert letter_top < drawing.BACK_CENTER[1]
    # Its counterbore-width callout stays outside the detail, over its upper
    # edge. The final native text/leader guard checks section B-B rather than
    # trusting the old shoulder-length estimate.
    cbore_x, cbore_y = drawing.DETAIL_KEEP["ClampSlotCboreWidth"]
    assert cbore_x < drawing.DETAIL_CENTER[0] - radius
    cbore_edge = (
        drawing.DETAIL_CENTER[1] + part.CLAMP_SLOT_CBORE_WIDTH * drawing.DETAIL_MM / 2.0
    )
    assert cbore_y > cbore_edge
    assert drawing.DETAIL_LABEL_XY[1] > drawing.DETAIL_CENTER[1] + radius


def _outer_clamp_station_lines():
    # Actual 63fad6340 native audit, sheet metres: both witnesses and the
    # 17.345 (was 440.50) dimension line. These are not rendered/PDF estimates.
    return [
        ((0.283, 0.121), (0.283, 0.0772219)),
        ((0.06275, 0.121), (0.06275, 0.0772219)),
        ((0.283, 0.0782219), (0.06275, 0.0782219)),
    ]


def test_front_caption_clears_detail_without_following_its_lower_callout() -> None:
    from _drawing_annotation_extent import boxes_clear

    # Native text positions/widths from the retained 63fad6340 audit. The
    # far-right slot-width text is BELOW the caption, not an x keep-out.
    details = {
        "upper travel": (0.1318882, 0.0662219, 0.1461118, 0.0697219),
        "counterbore width": (0.074008, 0.057918, 0.107, 0.0770563),
        "slot width": (0.150, 0.01614, 0.194076, 0.0408344),
    }
    caption = (0.1455456, 0.0680173, 0.1948421, 0.0715173)
    centre, top = drawing._front_caption_target(
        _outer_clamp_station_lines(), caption, details
    )
    half_width = (caption[2] - caption[0]) / 2.0
    box = (centre - half_width, top - (caption[3] - caption[1]), centre + half_width, top)
    assert top == pytest.approx(0.0772219 - drawing.FRONT_CAPTION_AIR_M)
    span_centre = (0.06275 + 0.283) / 2.0
    assert span_centre <= centre < span_centre + 0.005
    for detail in details.values():
        assert boxes_clear(box, detail, gap=drawing.FRONT_CAPTION_AIR_M - 1e-12)


def test_front_caption_refuses_a_missing_native_dimension_line() -> None:
    with pytest.raises(RuntimeError, match="native dimension line"):
        drawing._front_caption_target([], (0.1, 0.06, 0.15, 0.0635), {})


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


def test_section_a_a_caption_stands_directly_under_the_cut_bar() -> None:
    """r4 review: 35 mm under the cut bar, the caption read as the
    isometric's. Only the thickness is dimensioned on A-A, above the bar."""
    assert drawing.SECTION_DEPTH_RISE > 0.0
    scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    foot = drawing.SECTION_CENTER[1] - spec.BAR_HEIGHT * scale / 2000.0
    gap = foot - drawing.SECTION_CAPTION_TOP_Y
    assert 0.002 <= gap <= 0.006
    # Still above the isometric's centre, which stands under it.
    assert drawing.SECTION_CAPTION_TOP_Y > drawing.ISO_CENTER[1] + 0.040


def test_section_a_a_thickness_text_clears_both_extension_lines() -> None:
    """Round 7 of the fan-out: the 28-character 'SETS MHA-PD-VN-57
    ENGAGEMENT' row ran 11 mm across the left extension line, which ended
    inside its 'M'. Round 7's native layout: the keep is the block's centre,
    5.6 mm a row, 2.78 mm a character, the dimension line 0.4 mm over the
    block's foot and the extension lines 1 mm past it. The block stands left
    of the left extension line by 1.5 mm or more, right of the hook taps'
    callout shoulder (round 2's 0.3124 end, 0.2393), its foot (so its line)
    where round 7's was, and under the border."""
    scale = drawing.SECTION_SCALE[0] / drawing.SECTION_SCALE[1]
    left_face = drawing.SECTION_CENTER[0] - BAR_DEPTH * scale / 2000.0
    top = drawing.SECTION_CENTER[1] + spec.BAR_HEIGHT * scale / 2000.0
    x = left_face - drawing.SECTION_DEPTH_SIDE
    y = top + drawing.SECTION_DEPTH_RISE
    rows = [".374 +.001", *drawing.DIMENSION_CALLOUTS["Depth"].splitlines()]
    assert len(rows) - 1 <= 2
    half_width = max(map(len, rows)) * 0.00278 / 2.0
    half_height = len(rows) * 0.0056 / 2.0 + 0.0003
    box = (x - half_width, y - half_height, x + half_width, y + half_height)
    assert left_face - box[2] >= 0.0015 + 0.0025
    assert box[0] - 0.3124 >= 0.005
    assert box[1] == pytest.approx(0.2297, abs=5e-4)
    assert box[3] < 0.2667 - 0.005


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


def test_locations_and_overall_sizes_carry_no_words() -> None:
    """Rule 7 (screen 20261107T081227004Z): a location dimension carries its
    value and band alone, and an overall size with no band of its own no
    reason; the mates stand on the holes' size callouts. The .XXX height and
    thickness each name the stack they set (rule 4; round 4 machinist
    review)."""
    words = set(drawing.DIMENSION_CALLOUTS) | set(drawing.DIMENSION_CALLOUTS_ABOVE)
    locations = {
        "HangerRowHeight",
        "ClampRowHeight",
        *sheet_spec.HANGER_STATION_NAMES,
        *sheet_spec.CLAMP_STATION_NAMES,
    }
    # The 1.00 height prints .XX alone (owner ruling 2026-11-20, #2421), so it
    # carries no reason; the .XXX thickness names the stack it sets.
    assert not words & (locations | {"Length", "Height"})
    assert (
        _config.parts("pd-vn-transgear-pivot-screw")["number"]
        in drawing.DIMENSION_CALLOUTS["Depth"]
    )
    # The through slot names its screw in the standard clearance form; the
    # counterbore says whose centres it shares and the head their .XXX
    # serves, by the screw's number (v49 machinist review: the .118 had no
    # function, then "THE HEAD" no mate); the round holes name theirs once.
    callouts = [*drawing.DIMENSION_CALLOUTS.values(), sheet_spec.CLAMP_CBORE_CALLOUT]
    assert "ClampSlotCboreDepth" not in words
    cbore = drawing.DIMENSION_CALLOUTS["ClampSlotCboreWidth"]
    assert sheet_spec.SHEET_PRECISION["ClampSlotProfile"]["ClampSlotTravel"] == 3
    screw = _config.parts("sh-vn-clamp-screw")["number"]
    assert cbore.splitlines() == ["ON .118 CENTRES FOR", f"{screw} HEAD"]
    assert sum("CLEARANCE FOR MHA-SH-VN-53" in " ".join(text.split()) for text in callouts) == 2
    for text in callouts:
        assert not re.search(r"\b(LOCATE TO|SEATS|HEADS|SLIDING|TO SUIT)\b", text), text
    # At most two lines of words under each callout.
    assert all(
        len(text.splitlines()) <= 2 for text in drawing.DIMENSION_CALLOUTS.values()
    )
    assert len(sheet_spec.CLAMP_CBORE_CALLOUT.splitlines()) <= 2


_CBORE_NATIVE = {
    5: "<HOLE-SPOT><MOD-DIAM><hw-cbdia> <HOLE-DEPTH><hw-cbdepth>",
    6: "",
    7: "<NUM_INST>X <MOD-DIAM><hw-thruholedia> <hw-thru>",
    8: "",
}


@pytest.mark.parametrize("extent", ["<hw-thru>", "THRU ALL"])
def test_clamp_callout_reads_size_then_drill_then_thru(extent) -> None:
    native = {**_CBORE_NATIVE, 7: _CBORE_NATIVE[7].replace("<hw-thru>", extent)}
    updated = drawing.clamp_callout_definitions(native)
    row = updated[7]
    size = row.index("<hw-thruholedia>")
    process = row.index(f" {sheet_spec.CLAMP_HOLE_PROCESS} ")
    assert size < process < row.index(extent)
    assert row.replace(f" {sheet_spec.CLAMP_HOLE_PROCESS}", "", 1) == native[7]
    # The counterbore row keeps its symbol and variables; the mates go below.
    assert updated[5] == native[5]
    assert updated[8] == sheet_spec.CLAMP_CBORE_CALLOUT


@pytest.mark.parametrize(
    "native",
    [
        {**_CBORE_NATIVE, 8: "ALREADY BELOW"},
        {**_CBORE_NATIVE, 7: "<NUM_INST>X <MOD-DIAM><hw-thruholedia>"},
        {**_CBORE_NATIVE, 5: _CBORE_NATIVE[5] + " THRU"},
        {k: v for k, v in _CBORE_NATIVE.items() if k != 6},
    ],
)
def test_clamp_callout_refuses_an_unexpected_native_layout(native) -> None:
    with pytest.raises(RuntimeError, match="clamp callout"):
        drawing.clamp_callout_definitions(native)


def test_countersinks_print_their_angle_after_the_max_limit() -> None:
    assert drawing.COUNTERSINK_SUFFIX.startswith(part.MAX_SUFFIX)
    assert drawing.COUNTERSINK_SUFFIX.endswith(f"{spec.TAP_CSK_ANGLE_DEG:.0f}\u00b0")
    for name in drawing.COUNTERSINK_NAMES:
        prefix = sheet_spec.DIMENSION_PREFIXES[("CountersinkReference", name)]
        assert prefix.index("<HOLE-SINK>") < prefix.index("<MOD-DIAM>")


def test_front_face_view_is_lettered_without_the_sheet_scale() -> None:
    """Rules 9 and 26: the front face's removed rear view carries the letter
    of its viewing arrow and, at the sheet's scale, no scale."""
    assert drawing.FACE_SCALE == drawing.SHEET_SCALE
    assert drawing.BACK_VIEW_CAPTION == f"VIEW {drawing.FRONT_FACE_VIEW_LETTER}"
    taken = {"A", "B", drawing.DETAIL_LETTER}
    assert drawing.FRONT_FACE_VIEW_LETTER not in taken | {"I", "O", "Q"}


@pytest.mark.parametrize("side", [-1.0, 1.0])
def test_view_arrow_points_level_at_the_front_face_from_outside(side) -> None:
    front, back = (0.390 + side * 0.0095, 0.213), (0.390 - side * 0.0095, 0.213)
    (letter_x, letter_top), (tip_x, tip_y) = drawing._view_arrow_points(front, back)
    assert tip_y == front[1]
    assert letter_top - drawing.VIEW_LETTER_HEIGHT / 2.0 == pytest.approx(tip_y)
    assert side * (tip_x - front[0]) == pytest.approx(drawing.VIEW_ARROW_TIP_GAP)
    assert side * (letter_x - tip_x) == pytest.approx(drawing.VIEW_ARROW_LENGTH)


def _plane_face(normal: tuple[float, float, float], offset: float, box: tuple[float, ...] = ()):
    from _gtol_face import FaceGeometry

    point = tuple(value * offset / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, tuple(v / 1000 for v in box))


def _bore_face(dia: float, x: float, y: float):
    from _gtol_face import FaceGeometry

    r, z = dia / 2.0, BAR_DEPTH / 2.0
    box = tuple(v / 1000 for v in (x - r, y - r, -z, x + r, y + r, z))
    return FaceGeometry(None, 4002, (x / 1000, y / 1000, 0.0, 0.0, 0.0, 1.0, dia / 2000), None, box)


def test_the_bar_is_a_feature_export_part_with_one_owner_per_face() -> None:
    import export_features
    from _hole_spec import blind_cut_dia_mm

    manifest = export_features.requirement_manifest("pd_support_bar")
    features = manifest["features"]
    assert {name: feature["kind"] for name, feature in features.items()} == {
        **dict.fromkeys(
            ("end_a", "far_end", "top_face", "bottom_face", "front_face", "back_face"), "face"
        ),
        "pivot_tap": "threaded_hole",
        "hook_tap_1": "threaded_hole",
        "hook_tap_2": "threaded_hole",
        "clamp_hole_1": "hole",
        "clamp_hole_2": "hole",
        "clamp_slot_3": "slot",
        "clamp_slot_4": "slot",
    }
    assert manifest["notes"]["manufacturing"] == drawing.SCREW_LINE_NOTE.splitlines()
    half_length, half_height = part.BAR_LENGTH / 2.0, spec.BAR_HEIGHT / 2.0
    row, w = spec.CLAMP_TAP_Y, part.CLAMP_SLOT_WIDTH / 2.0
    expected = {
        "end_a": [_plane_face((-1.0, 0.0, 0.0), half_length)],
        "far_end": [_plane_face((1.0, 0.0, 0.0), half_length)],
        "top_face": [_plane_face((0.0, 1.0, 0.0), half_height)],
        "bottom_face": [_plane_face((0.0, -1.0, 0.0), half_height)],
        "front_face": [_plane_face((0.0, 0.0, -1.0), BAR_DEPTH / 2.0)],
        "back_face": [_plane_face((0.0, 0.0, 1.0), BAR_DEPTH / 2.0)],
        "pivot_tap": [_bore_face(spec.PIVOT_TAP_DRILL_DIA, spec.PIVOT_TAP_X, spec.HANGER_TAP_Y)],
        **{
            f"hook_tap_{index}": [
                _bore_face(blind_cut_dia_mm(spec.BRACKET_TAP_SPEC), x, spec.HANGER_TAP_Y)
            ]
            for index, x in enumerate(spec.BRACKET_TAP_X, 1)
        },
    }
    for index, x in enumerate(part.CLAMP_ROW_X, 1):
        if x in part.CLAMP_ROUND_X:
            expected[f"clamp_hole_{index}"] = [
                _bore_face(part.CLAMP_HOLE_DIA, x, row),
                _bore_face(part.CLAMP_CBORE_DIA, x, row),
            ]
            continue
        run = part.CLAMP_SLOT_TRAVEL
        expected[f"clamp_slot_{index}"] = [
            _plane_face((0.0, 1.0, 0.0), row - w, (x - run, row - w, 0.0, x + run, row - w, 4.0)),
            _plane_face((0.0, -1.0, 0.0), -(row + w), (x - run, row + w, 0.0, x + run, row + w, 4.0)),
        ]
    selectors = export_features.feature_selectors("pd_support_bar")
    assert set(selectors) == set(features)
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_bar_feature_bands_are_the_printed_ones() -> None:
    import export_features

    inch = 25.4
    features = export_features.requirement_manifest("pd_support_bar")["features"]
    assert features["far_end"]["length"] == pytest.approx([17.7 * inch, 17.9 * inch])
    assert features["bottom_face"]["height"] == pytest.approx([0.99 * inch, 1.01 * inch])
    # The thickness as supplied, .374 +.001/-.003 (#1563).
    assert features["back_face"]["depth"] == pytest.approx([0.371 * inch, 0.375 * inch], abs=1e-3)
    assert features["top_face"]["finish_ra"] == features["front_face"]["finish_ra"]
    pivot = features["pivot_tap"]
    assert pivot["thread"] == "#8-32 UNC-2B" and pivot["thru"] is True
    assert pivot["station"] == pytest.approx([6.612 * inch, 6.622 * inch], abs=1e-3)
    assert pivot["height"] == pytest.approx([0.566 * inch, 0.576 * inch], abs=1e-3)
    assert pivot["csk_dia_max"] == pytest.approx(0.169 * inch, abs=1e-3)
    for name in ("hook_tap_1", "hook_tap_2"):
        assert features[name]["made_at"] == "assembly"
        assert "station" not in features[name]
    for name, station in (
        ("clamp_hole_1", 0.455),
        ("clamp_hole_2", 1.833),
        ("clamp_slot_3", 15.967),
        ("clamp_slot_4", 17.345),
    ):
        clamp = features[name]
        assert clamp["station"] == pytest.approx(
            [(station - 0.005) * inch, (station + 0.005) * inch], abs=1e-3
        ), name
        assert clamp["height"] == pytest.approx([0.546 * inch, 0.556 * inch], abs=1e-3), name
        assert clamp["cbore_depth"] == pytest.approx([0.18 * inch, 0.20 * inch], abs=1e-3), name
    assert features["clamp_hole_1"]["cbore_dia"] == pytest.approx([0.3125 * inch, 0.3225 * inch], abs=1e-3)
    slot = features["clamp_slot_4"]
    assert slot["width"] == pytest.approx([0.196 * inch, 0.200 * inch], abs=1e-3)
    assert slot["run"] == pytest.approx([0.113 * inch, 0.123 * inch], abs=1e-3)
    assert slot["cbore_width"] == pytest.approx([0.330 * inch, 0.345 * inch], abs=1e-3)

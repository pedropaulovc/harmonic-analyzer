"""Offline manufacturing contracts for the cone-tip-block drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_dt_cone_tip_block as part
import dt_cone_tip_block_spec
import draw_dt_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _surface_finish import SEAT_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-tip-block_drawing.png")
    assert DRAWINGS_BY_NAME["dt_cone_tip_block"].script == Path(drawing.__file__).resolve()


def test_adjuster_thread_is_tapped_through_with_no_floor() -> None:
    """E11/W1: no floor to break out and no tap lead to deduct (Main, 2026-09-24)."""
    spec = dt_cone_tip_block_spec
    assert spec.ADJUSTER_THREAD == "#10-32"
    assert spec.ADJUSTER_BORE_SPEC.end == "through_all"
    assert spec.ADJUSTER_BORE_SPEC.depth_mm == 0.0
    assert "ThreadDepth" not in spec.ADJUSTER_BORE_SPEC.overrides_mm
    assert "PassageProfile" not in spec.DRAWING_DIMENSIONS
    # The tip passes the thread's minimum minor diameter, not a separate hole.
    assert spec.SHAFT_PASSAGE_DIA == pytest.approx(3.9624)
    assert spec.SHAFT_PASSAGE_DIA < spec.ADJUSTER_BORE_DIA


def test_adjuster_embed_band_stays_inside_its_engagement_window() -> None:
    """The window opens at 1.0D + countersink (the adjuster's user-ruled
    engagement exception, 2026-09-29) and closes a countersink short of the
    south face at the depth's .XXX-short limit: the cup sits on full thread.
    A 1.5D floor would leave no room for the tip's print-worst stack."""
    spec = dt_cone_tip_block_spec
    assert spec.ADJUSTER_CSK_DIA > 4.826
    assert spec.ADJUSTER_MIN_ENGAGEMENT_D == 1.0
    assert spec.ADJUSTER_EMBED_WINDOW == pytest.approx((5.3067, 9.1393))
    low, high = spec.ADJUSTER_EMBED_WINDOW
    assert low == pytest.approx(1.0 * 4.826 + spec.ADJUSTER_CSK, abs=1e-3)
    assert high == pytest.approx(spec.BLOCK_Z - 0.13 - spec.ADJUSTER_CSK)
    assert low < spec.ADJUSTER_EMBED < high
    assert drawing.ADJUSTER_CSK_QUALIFIER == "90° CSK Ø5.0 BOTH ENDS"


def test_adjuster_callout_names_both_countersinks_under_the_thread() -> None:
    native = {
        5: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
        6: "",
        7: "<hw-threaddesc> <hw-threadclass> <hw-thru>",
        8: "",
    }
    rewritten = drawing._adjuster_callout_definitions(native)
    assert rewritten[5] == native[5]
    assert rewritten[7] == (
        "<hw-threaddesc> <hw-threadclass> <hw-thru>\n90° CSK Ø5.0 BOTH ENDS"
    )
    with pytest.raises(RuntimeError):
        drawing._adjuster_callout_definitions({**native, 5: native[7]})


def test_pinch_joint_uses_entry_clearance_and_opposite_jaw_thread() -> None:
    """The screw must pass one jaw and engage the other, not bind in both."""
    tap = part.PINCH_BORE_SPEC
    clearance = part.PINCH_CLEARANCE_SPEC
    assert tap is dt_cone_tip_block_spec.PINCH_BORE_SPEC
    assert tap.kind == "tapped"
    assert tap.size == dt_cone_tip_block_spec.PINCH_THREAD
    assert tap.end == "through_all"
    assert clearance is dt_cone_tip_block_spec.PINCH_CLEARANCE_SPEC
    assert clearance.kind == "clearance"
    assert clearance.size == "#4"
    assert clearance.fit == "normal"
    assert clearance.end == "blind"
    assert clearance.depth_mm == (part.BLOCK_X - part.SLIT_W) / 2.0
    assert part.PINCH_BORE_DIA == blind_cut_dia_mm(tap)
    assert part.PINCH_CLEARANCE_DIA == blind_cut_dia_mm(clearance)
    assert part.PINCH_CLEARANCE_DIA > part.PINCH_BORE_DIA


def test_pinch_thread_callout_keeps_native_variables_but_limits_both_extents() -> None:
    """The print must describe the remaining threaded jaw, not the pre-clearance cut."""
    original = {
        5: "<hw-threaddesc> <hw-threadclass> <hw-thru>",
        6: "",
        7: "<MOD-DIAM> <hw-thrutapdrldia> <hw-thru>",
        8: "",
    }
    rewritten = drawing._pinch_thread_callout_definitions(original)
    text = "\n".join(rewritten.values())
    assert "THRU ALL" not in text
    assert text.count("TO SLOT") == 2
    assert drawing._PINCH_THREAD_QUALIFIER in text
    assert all(token in text for token in drawing._PINCH_THREAD_NATIVE_TOKENS)
    # Drill line, thread line, then the prose (Main eye-pass af561fa7).
    assert rewritten[5] == (
        "<hw-threaddesc> <hw-threadclass> TO SLOT\nCOAXIAL WITH CLEARANCE"
    )
    assert rewritten[7] == "<MOD-DIAM> <hw-thrutapdrldia> TO SLOT"
    assert "LEFT-JAW" not in text


def test_pinch_spacing_closes_every_print_tolerance_stack() -> None:
    """The user-approved relative axis control prevents both breakout and collision."""
    assert abs(part.PINCH_BORE_Y - part.ADJUSTER_AXIS_HEIGHT - part.PINCH_RISE) < 1e-12
    assert abs(
        dt_cone_tip_block_spec.BLOCK_HEIGHT
        - dt_cone_tip_block_spec.SLIT_DEPTH
        - dt_cone_tip_block_spec.SLIT_FLOOR
    ) < 1e-12
    spec = dt_cone_tip_block_spec
    assert spec.WORST_SCREW_ENVELOPE_GAP_MM > 0.0
    # U24b / U27: every web keeps 2.0 at the printed limits after edge breaks.
    # E11/W1's #10-32 root (ref Ø5.04 vs Ø8.28) adds ~1.6 to the adjuster webs.
    # r3: PinchHeight .XX from the foot, BlockHt .X, AxisHeight .XXX +/-0.10
    # (2026-09-29: the prism stands on the platform, so the axis height is
    # the block's own fit); the 17 block adds 1.0 to the adjuster's side wall,
    # and Width at .XXX (the hold-down containment) adds 0.67 more.
    assert spec.WORST_SLIT_MOUTH_WEB_MM == pytest.approx(3.566, abs=1e-3)
    assert spec.WORST_TOP_LIGAMENT_MM == pytest.approx(2.19, abs=1e-6)
    assert spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM == pytest.approx(5.720, abs=1e-3)
    for web in (
        spec.WORST_SLIT_MOUTH_WEB_MM,
        spec.WORST_TOP_LIGAMENT_MM,
        spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM,
        spec.WORST_PINCH_DEPTH_LIGAMENT_MM,
    ):
        assert round(web, 6) >= spec.MIN_WEB_MM
    tap_bottom = part.PINCH_BORE_Y - part.PINCH_BORE_DIA / 2.0
    assert dt_cone_tip_block_spec.SLIT_FLOOR <= tap_bottom


def test_foot_seat_is_the_only_locating_surface_finish() -> None:
    (finish,) = dt_cone_tip_block_spec.SURFACE_FINISHES
    assert finish.key == "foot_seat"
    assert finish.roughness_um == SEAT_UM
    assert finish.face.normal == (0, -1, 0)
    assert finish.face.offset_mm == 0.0


def test_part_config_preserves_manufacturing_metadata() -> None:
    import _config

    config = _config.parts("dt-cone-tip-block")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1


def test_block_stands_on_the_platform_and_keeps_every_axis_relation() -> None:
    """2026-09-29: the foot sits straight on the platform, so the adjuster
    axis is the cone axis's height above the platform top."""
    spec = dt_cone_tip_block_spec
    from dt_post_mount_stack import CONE_AXIS_HEIGHT_MM

    assert spec.ADJUSTER_AXIS_HEIGHT == CONE_AXIS_HEIGHT_MM
    assert abs(spec.SLIT_FLOOR - (spec.ADJUSTER_AXIS_HEIGHT - 0.65)) < 1e-12
    assert abs(spec.PINCH_HEIGHT - spec.ADJUSTER_AXIS_HEIGHT - spec.PINCH_RISE) < 1e-12
    assert spec.DRAWING_DIMENSIONS["AxisHeightReference"] == {"AxisHeight"}


def test_pinch_thread_readback_checks_the_thread_part_not_string_order() -> None:
    """c6981bac (run 244bc8bb) resolved exactly this and was wrongly refused."""
    resolved = {
        1: "4-40 UNC - 2B TO SLOT\nCOAXIAL WITH CLEARANCE",
        2: "",
        3: "<MOD-DIAM> 2.26 TO SLOT",
        4: "",
    }
    assert drawing._pinch_thread_callout_resolved(resolved)
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 1: "COAXIAL WITH CLEARANCE\n4-40 UNC - 2B TO SLOT"}
    )
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 3: "<MOD-DIAM> 2.26 THRU ALL"}
    )


def test_part_hides_every_model_reference_sketch() -> None:
    """f76387f5's iso and 8929d954's drive-train iso printed reference sketches.

    The part blanks every construction-only reference sketch it authors before
    save, so no drawing view or assembly instance renders one, and a new one
    cannot be authored unlisted.
    """

    source = Path(part.__file__).read_text(encoding="utf-8")
    authored = re.findall(r'feature_name="([A-Za-z]+Reference)"', source)
    assert authored and tuple(authored) == part.REFERENCE_SKETCHES
    build_body = source[source.index("async def build(") :]
    assert "_blank_reference_sketches(adapter, REFERENCE_SKETCHES)" in build_body
    assert build_body.index("_blank_reference_sketches(") < build_body.index(
        "save_part_and_images("
    )


def test_section_a_carries_no_dimension_so_shows_no_hidden_sketch() -> None:
    """A derived view keeps the part's sketch visibility from its creation.

    995a7c94 hides every reference sketch in the part.  Section A used to
    dimension PinchRise and was cut while the part showed that sketch; r3
    moved the pinch height to the right view, so the section keeps nothing
    and is cut with the part as saved.
    """
    assert drawing.SECTION_KEEP == {}
    assert not hasattr(drawing, "SECTION_SKETCHES")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "part_sketches_shown(" not in body


def test_only_views_dimensioning_hidden_sketches_opt_in() -> None:
    """The opt-in import goes where a kept dimension lives on a hidden sketch.

    Right (PinchDepthCenter, and r3's PinchHeight) and the bottom view (the
    hold-down tap's two stations) always do; the adjuster elevation
    (AxisHeight/PassageCenter) opts in at build time; the plan, left and the
    base front keep only solid-feature dimensions and stay on
    _drawing_common's import.
    """

    def hidden_owners(keep) -> set[str]:
        return {
            feature
            for feature, names in dt_cone_tip_block_spec.DRAWING_DIMENSIONS.items()
            if set(names) & set(keep)
        } & set(part.REFERENCE_SKETCHES)

    assert hidden_owners(drawing.RIGHT_KEEP) == {
        "PinchDepthReference",
        "PinchHeightReference",
    }
    assert hidden_owners(drawing.BOTTOM_KEEP) == {
        "FootTapXReference",
        "FootTapZReference",
    }
    assert hidden_owners({"AxisHeight": 0, "PassageCenter": 0}) == {
        "AxisHeightReference",
        "PassageCenterReference",
    }
    for keep in (drawing.TOP_KEEP, drawing.LEFT_KEEP, drawing.FRONT_KEEP):
        assert hidden_owners(keep) == set()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    for keep, call in (
        ("keep=TOP_KEEP", "top_annotations = curate_view_dimensions("),
        ("keep=BOTTOM_KEEP", "bottom_annotations = hidden_sketches.curate_view_dimensions("),
    ):
        before = body[: body.index(keep)].rstrip()
        assert before[: before.rindex("adapter,")].rstrip().endswith(call)


def test_every_marked_dimension_is_kept_in_exactly_one_view() -> None:
    """Every marked dimension lands on one view; the bottom view carries the
    hold-down tap's two stations (2026-09-29)."""
    adjuster_axis = {"AxisHeight", "PassageCenter", "SlitDepth"}
    kept = [
        *drawing.FRONT_KEEP,
        *drawing.TOP_KEEP,
        *drawing.RIGHT_KEEP,
        *drawing.LEFT_KEEP,
        *drawing.SECTION_KEEP,
        *drawing.BOTTOM_KEEP,
        *adjuster_axis,
    ]
    marked = {
        name
        for names in dt_cone_tip_block_spec.DRAWING_DIMENSIONS.values()
        for name in names
    }
    assert sorted(kept) == sorted(set(kept))
    assert set(kept) == marked
    assert set(drawing.TOP_KEEP) == {"Depth"}
    assert set(drawing.BOTTOM_KEEP) == {"FootTapX", "FootTapZ"}


def test_slot_width_text_stands_right_of_its_outside_arrows() -> None:
    """Main eye-pass 5637ac42: the 1.2 slot's extension lines ran through "1.20".
    r3: PassageCenter's span from the -X face takes the slit's left, so the
    value stands right of the right arrow's tail."""
    slot_x = drawing.FRONT_CENTER[0]
    text_x = drawing.FRONT_KEEP["SlitW"][0]
    right_wall = slot_x + part.SLIT_W * drawing._S / 2.0
    arrow_tail = right_wall + drawing.ARROW_LENGTH
    assert text_x - drawing.VALUE_TEXT_HALF_WIDTH >= arrow_tail + 0.001
    passage_x = drawing._adjuster_axis_keep(drawing.FRONT_CENTER)["PassageCenter"][0]
    assert passage_x < slot_x < text_x
    assert drawing.ARROWS_OUTSIDE == ("SlitW",)


def test_every_view_centres_on_the_prism_with_north_where_it_shows() -> None:
    """The prism's centre is the model origin; *Top shows north down the
    sheet, the right view on the left, the bottom view up (toward the front
    view, third angle)."""
    assert drawing.Z_NORTH - drawing.Z_SOUTH == pytest.approx(part.BLOCK_Z)
    assert drawing._plan_y(drawing.Z_NORTH) < drawing._plan_y(drawing.Z_SOUTH)
    assert drawing._right_x(drawing.Z_NORTH) < drawing._right_x(drawing.Z_SOUTH)
    assert drawing._bottom_y(drawing.Z_NORTH) > drawing._bottom_y(drawing.Z_SOUTH)
    assert (
        drawing._plan_y(drawing.Z_NORTH) + drawing._plan_y(drawing.Z_SOUTH)
    ) / 2.0 == pytest.approx(drawing.TOP_CENTER[1])
    assert (
        drawing._right_x(drawing.Z_NORTH) + drawing._right_x(drawing.Z_SOUTH)
    ) / 2.0 == pytest.approx(drawing.RIGHT_CENTER[0])
    assert (
        drawing._bottom_y(drawing.Z_NORTH) + drawing._bottom_y(drawing.Z_SOUTH)
    ) / 2.0 == pytest.approx(drawing.BOTTOM_CENTER[1])


def test_half_block_station_value_clears_both_witnesses() -> None:
    """Main eye-pass 5637ac42: the hole witness ended in the decimal point.

    PinchDepthCenter runs from the north face to the pinch-hole centre (the
    model origin), so the value sits between the two witness lines with room
    on both sides, not on either.  At 2:1 the span is 11.75 mm on the sheet,
    so each side keeps 1 mm rather than 5637ac42's 2.
    """
    text_x = drawing.RIGHT_KEEP["PinchDepthCenter"][0]
    half_width = 0.0065 / 2.0  # a three-character value, measured on 5637ac42
    north = drawing._right_x(drawing.Z_NORTH)
    hole = drawing._right_x(0.0)
    assert north + 0.001 <= text_x - half_width
    assert text_x + half_width <= hole - 0.001


def test_pinch_depth_dimension_line_stands_between_the_block_and_section_a() -> None:
    """At +0.003 the 6.0's dimension line printed on the block's top edge."""
    top = drawing._elevation_y(part.BLOCK_HEIGHT, drawing.RIGHT_CENTER)
    line_y = drawing.RIGHT_KEEP["PinchDepthCenter"][1]
    section_foot = drawing._elevation_y(0.0, drawing.SECTION_CENTER)
    assert line_y - top >= 0.005
    assert line_y + drawing.VALUE_TEXT_HALF_HEIGHT <= section_foot - 0.005



def _matches(finding: str, expected: str) -> bool:
    at = 0
    for fragment in expected.split(" ... "):
        at = finding.find(fragment, at)
        if at < 0:
            return False
        at += len(fragment)
    return True


def _findings_match(findings: list[str], expected: list[str]) -> bool:
    return len(findings) == len(expected) and all(
        _matches(finding, pattern) for finding, pattern in zip(findings, expected)
    )


def _sheet_findings(module) -> list[str]:
    return module.sheet_ink_collisions(
        module.sheet_text_boxes(),
        module.sheet_view_silhouettes(),
        module.sheet_dimension_ink(),
        module.sheet_leaders(),
    )


def test_sheet_ink_is_clear_and_the_build_places_what_it_audits() -> None:
    assert _sheet_findings(drawing) == []
    drawing.assert_sheet_ink_clear()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "assert_sheet_ink_clear(adjuster_center)" in body
    assert body.index("assert_sheet_ink_clear(") < body.index("curate(")
    for placed in (
        "callout_xy=_adjuster_callout_xy(adjuster_center)",
        "callout_xy=PINCH_CLEARANCE_CALLOUT_XY",
        "callout_xy=PINCH_THREAD_CALLOUT_XY",
        "callout_xy=FOOT_TAP_CALLOUT_XY",
        "for text, x, y in _sheet_notes(adjuster_center):",
        "adjuster_axis_keep = _adjuster_axis_keep(adjuster_center)",
        "[FOOT_FINISH_CENTER]",
        "foot_symbol, foot_right = _foot_finish_placement()",
        "symbol_xy=foot_symbol",
        "leader_attach_xy=foot_right",
        "_set_arrow_sides(",
        "for name in ARROWS_OUTSIDE",
        "for name in ARROWS_INSIDE",
    ):
        assert placed in body, placed
    assert body.count("add_note(adapter,") == 1
    # The foot's Ra 3.2 sits on VIEW C, where nothing is dimensioned under it.
    assert drawing.FOOT_FINISH_CENTER == drawing.BACK_CENTER
    assert drawing.ARROWS_INSIDE == (
        "SlitDepth",
        "PinchHeight",
        "PinchDepthCenter",
        "Depth",
        "FootTapX",
        "FootTapZ",
    )
    assert not set(drawing.ARROWS_INSIDE) & set(drawing.ARROWS_OUTSIDE)


def test_sheet_audit_uses_the_shared_leader_geometry() -> None:
    """Crossings and arrow-to-text gaps come from _drawing_leaders, the opt-in
    module the crank drawings gate on, not from a sheet-local copy."""
    import _drawing_leaders

    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_drawing_leaders.leader_crossings(" in source
    assert "_drawing_leaders.arrows_near_text(" in source
    assert drawing.ARROW_TEXT_CLEARANCE == _drawing_leaders.ARROW_TEXT_CLEARANCE == 0.002
    for local in ("def _segments_cross", "def _point_segment_distance"):
        assert local not in source, local


# #946's leader-over-part rule, on this sheet's own model: the run over the
# part from the leader's entry to its tip, minus the tip's shortest approach
# from outside (its distance to the nearest side of the view's outline).
# Swing's RD2 fix (4dda16fd5) left 3.8 mm; Main's brief for RD1 is ~4 mm.
LEADER_DETOUR_TARGET = 0.004


def _run_inside(segment, box) -> float:
    """Length of ``segment`` inside ``box`` (Liang-Barsky clip)."""
    (x0, y0), (x1, y1) = segment
    dx, dy = x1 - x0, y1 - y0
    low, high = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            low = max(low, t)
        else:
            high = min(high, t)
    return max(0.0, high - low) * math.hypot(dx, dy)


def _leader_detours(module) -> dict[str, tuple[float, float, float]]:
    """(over the part, shortest approach, detour) of every leader whose tip
    lands in a view outline, in sheet metres."""
    silhouettes = module.sheet_view_silhouettes()
    detours = {}
    for name, leader in module.sheet_leaders().items():
        tx, ty = leader.tip
        holding = sorted(
            (box for box in silhouettes.values() if box[0] <= tx <= box[2] and box[1] <= ty <= box[3]),
            key=lambda box: (box[2] - box[0]) * (box[3] - box[1]),
        )
        if not holding:
            continue
        box = holding[0]
        over = _run_inside(leader.segment(), box)
        approach = min(tx - box[0], box[2] - tx, ty - box[1], box[3] - ty)
        detours[name] = (over, approach, over - approach)
    return detours


def test_adjuster_callout_leader_takes_the_short_way_to_its_hole() -> None:
    """#946 / MHA-DT-021: RD1's callout stood below-right of the adjuster hole and
    its leader climbed ~28 mm over the front view to the rim, ~16 mm further
    than the hole's 11.5 mm approach from the right face, reading as an edge
    of the part.  The leader now enters by the hole's shortest approach."""
    detours = _leader_detours(drawing)
    over, approach, detour = detours["adjuster callout"]
    assert detour <= LEADER_DETOUR_TARGET, (over, approach, detour)
    # The shoulder stays off the part, so the leader is the only ink over it.
    start = drawing.sheet_leaders()["adjuster callout"].start
    front = drawing.sheet_view_silhouettes()["front"]
    assert start[0] > front[2]


# The ASME B landscape sheet's frame and title block, as the layout audit's
# dump reads them (ISheet::GetZoneMargin 12.7 mm each side; the title block's
# box, layoutcal2-a cone-tip-block.json).
SHEET_INNER_BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.216, 0.0, 0.4318, 0.066)


def _isometric_box(module) -> tuple[float, float, float, float]:
    """The isometric view's outer bound: the part's bounding box seen along
    (1, 1, 1), centred on the view's placement.  Across, (X + Z) / sqrt(2);
    up, Y * sqrt(2/3) + (X + Z) / sqrt(6)."""
    across = module.BLOCK_X + (module.Z_NORTH - module.Z_SOUTH)
    width = across / math.sqrt(2.0) * module._S
    height = (module.BLOCK_HEIGHT * math.sqrt(2.0 / 3.0) + across / math.sqrt(6.0)) * module._S
    x, y = module.ISO_CENTER
    return (x - width / 2.0, y - height / 2.0, x + width / 2.0, y + height / 2.0)


def test_the_slid_view_row_fits_the_sheet() -> None:
    """#946 slid the right view and the removed views B and C right to make
    room for the adjuster callout's short leader.  Every view outline, text
    block and dimension line stays inside the frame and off the title block,
    and no two views' outlines meet (the 2:1 bottom view and isometric too)."""
    views = {**drawing.sheet_view_silhouettes(), "isometric": _isometric_box(drawing)}
    ink = {
        **{f"view {name}": box for name, box in views.items()},
        **{f"text {name}": box for name, box in drawing.sheet_text_boxes().items()},
    }
    for owner, dimension in drawing.sheet_dimension_ink().items():
        for index, ((x0, y0), (x1, y1)) in enumerate(dimension.segments()):
            ink[f"{owner} line {index}"] = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    left, bottom, right, top = SHEET_INNER_BORDER
    outside = [
        name
        for name, box in ink.items()
        if box[0] < left or box[1] < bottom or box[2] > right or box[3] > top
    ]
    assert outside == []
    on_title = [
        name
        for name, box in ink.items()
        if box[0] < TITLE_BLOCK[2]
        and box[2] > TITLE_BLOCK[0]
        and box[1] < TITLE_BLOCK[3]
        and box[3] > TITLE_BLOCK[1]
    ]
    assert on_title == []
    names = sorted(views)
    touching = [
        (first, second)
        for index, first in enumerate(names)
        for second in names[index + 1 :]
        if drawing._box_gap(views[first], views[second]) < drawing.TEXT_CLEARANCE
    ]
    assert touching == []
    # The slide is what the callout needs: the right view's north face stands
    # one text clearance past the callout's right end.
    callout = drawing.sheet_text_boxes()["adjuster callout"]
    assert views["right"][0] - callout[2] == pytest.approx(
        drawing.TEXT_CLEARANCE + drawing.ROUND_OUT, abs=1e-9
    )


def test_no_leader_on_the_sheet_detours_over_the_part() -> None:
    detours = _leader_detours(drawing)
    assert {"adjuster callout", "pinch clearance callout", "pinch thread callout"} <= set(detours)
    long_way = {name: d for name, d in detours.items() if d[2] > LEADER_DETOUR_TARGET}
    assert long_way == {}



# --- r3: codex FIX review of 72ab (C:/src/dt-logs/mreview-i31/block-72ab) ----
# Every number below is recomputed from the print's own grades
# (DRAWING_PRECISION) and the title block's general bands, never read back
# from the spec's stack constants, so each test states the property itself.
# The three explicit bands are the user's rulings: AxisHeight +/-0.10, and
# the hold-down tap's two stations +/-0.10 (2026-09-29).
_GENERAL = {1: 0.8, 2: 0.51, 3: 0.13}
_EXPLICIT = {"AxisHeight": 0.10, "FootTapX": 0.10, "FootTapZ": 0.10}
_DRILLED_PLUS = 0.10


def _printed(name: str, nominal: float) -> tuple[float, float]:
    places = dt_cone_tip_block_spec.DRAWING_PRECISION_BY_NAME[name]
    band = _EXPLICIT.get(name, _GENERAL[places])
    return round(nominal, places) - band, round(nominal, places) + band


def _worst_near_jaw_wall() -> float:
    """Deepest the slit's near wall can stand from the +X (drill) face."""
    spec = dt_cone_tip_block_spec
    passage = _printed("PassageCenter", spec.BLOCK_X / 2.0)
    width = _printed("Width", spec.BLOCK_X)
    slit_half_min = _printed("SlitW", spec.SLIT_W)[0] / 2.0
    return max(passage[1] - slit_half_min, width[1] - passage[0] - slit_half_min)


def test_pinch_clearance_print_breaks_into_the_slit_at_the_worst_case() -> None:
    """Blocker: 72ab printed the Ø3.26 6.9 deep (.X, floor 6.1) into a near
    jaw the print lets run to 8.47 -- the screw could thread-lock short of the
    slit.  Whatever the print says must break into the slit at the worst
    case: a printed blind depth by its lower limit, 0.25 past the deepest
    near wall; DRILL TO SLOT by definition, provided drilling full diameter
    0.25 past that wall only meets the far jaw inside its tap drill."""
    spec = dt_cone_tip_block_spec
    near_wall = _worst_near_jaw_wall()
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    if '"hw-depth"' in source:
        depth = spec.PINCH_CLEARANCE_SPEC.depth_mm
        floor = round(depth, 1) - _GENERAL[1]
        assert floor >= near_wall + 0.25, (floor, near_wall)
        return
    assert drawing.PINCH_CLEARANCE_EXTENT_TEXT == "DRILL TO SLOT"
    clearance_max = round(spec.PINCH_CLEARANCE_DIA, 2) + _DRILLED_PLUS
    point = (clearance_max / 2.0) / math.tan(math.radians(118.0 / 2.0))
    slit_min = _printed("SlitW", spec.SLIT_W)[0]
    past_far_wall = 0.25 + point - slit_min
    assert clearance_max * max(past_far_wall, 0.0) / point <= spec.PINCH_BORE_DIA
    assert spec.WORST_PINCH_NEAR_WALL_MM == pytest.approx(near_wall)


def test_pinch_clearance_callout_rewrites_the_blind_depth_to_drill_to_slot() -> None:
    """The native blind depth pair becomes the instruction; the diameter
    stays its Hole Wizard variable, and any other shape fails loud."""
    native = {5: "<MOD-DIAM><hw-diam> <HOLE-DEPTH> <hw-depth>", 6: "", 7: "", 8: ""}
    rewritten = drawing._pinch_clearance_callout_definitions(native)
    assert rewritten == {5: "<MOD-DIAM><hw-diam> DRILL TO SLOT", 6: "", 7: "", 8: ""}
    with pytest.raises(RuntimeError):
        drawing._pinch_clearance_callout_definitions({**native, 5: "<MOD-DIAM><hw-diam>"})
    with pytest.raises(RuntimeError):
        drawing._pinch_clearance_callout_definitions({**native, 7: native[5]})
    assert drawing._pinch_clearance_callout_resolved(
        {1: "<MOD-DIAM> 3.26 DRILL TO SLOT", 2: "", 3: "", 4: ""}
    )
    assert not drawing._pinch_clearance_callout_resolved(
        {1: "<MOD-DIAM> 3.26 <HOLE-DEPTH> 6.9", 2: "", 3: "", 4: ""}
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "_set_pinch_clearance_callout_text(pinch_clearance_callout)" in body
    assert '"hw-depth"' not in source


def test_far_jaw_is_tapped_full_thread_through_to_the_slit() -> None:
    """The far jaw's thread runs through (TO SLOT), and the tap passes the
    near jaw's clearance, so its lead runs out in the slit, not the jaw."""
    spec = dt_cone_tip_block_spec
    assert spec.PINCH_BORE_SPEC.end == "through_all"
    assert spec.PINCH_CLEARANCE_DIA > 0.112 * 25.4  # #4-40 basic major


def test_r3_prints_no_two_place_dimension_it_does_not_need() -> None:
    """Over-specification: 46.83, 32.27, 8.42 and 8.85 printed .XX with no fit
    or asserted margin needing it.  The overall height drops to .X, the rise
    leaves the print (the pinch hole locates from the foot).  2026-09-29: the
    block's foot sits straight on the platform, so AxisHeight is the block's
    own fit, .XXX with an explicit +/-0.10."""
    grades = dt_cone_tip_block_spec.DRAWING_PRECISION_BY_NAME
    assert grades["Depth"] == 3
    assert grades["BlockHt"] == 1
    assert grades["AxisHeight"] == 3
    assert "PinchRise" not in grades
    # Kept .XX, each for a named stack (see the report's list).
    assert {name for name, places in grades.items() if places == 2} == {
        "PinchHeight",
        "SlitW",
        "FootTapX",
    }


def test_top_ligament_needs_the_pinch_height_at_two_places() -> None:
    """The one r3 .XX kept for a web: at .X the ligament over the pinch hole
    closes at 1.92, under the 2.0 target."""
    spec = dt_cone_tip_block_spec
    clearance_r = (round(spec.PINCH_CLEARANCE_DIA, 2) + _DRILLED_PLUS) / 2.0
    height_min = _printed("BlockHt", spec.BLOCK_HEIGHT)[0]

    def ligament(places: int) -> float:
        pinch_max = round(spec.PINCH_HEIGHT, places) + _GENERAL[places]
        return height_min - pinch_max - clearance_r - 2.0 * spec.EDGE_BREAK_MAX_MM

    assert ligament(2) == pytest.approx(spec.WORST_TOP_LIGAMENT_MM)
    assert round(ligament(2), 6) >= 2.0 > ligament(1)


def _reference_call(body: str, feature: str) -> str:
    """The build's one reference-dimension call that authors ``feature``."""
    at = body.index(f'feature_name="{feature}"')
    start = body.rindex("await _author_", 0, at)
    return body[start : body.index("\n    )\n", at)]


def test_pinch_hole_height_is_located_from_the_foot() -> None:
    """Clarity: the pinch hole prints its height straight from the foot in the
    right view, where it is drilled, not chained off the adjuster axis."""
    spec = dt_cone_tip_block_spec
    assert spec.DRAWING_DIMENSIONS["PinchHeightReference"] == {"PinchHeight"}
    assert "PinchHeight" in drawing.RIGHT_KEEP
    # Its value stands past the south face, short of VIEW B, at half height.
    text_x, text_y = drawing.RIGHT_KEEP["PinchHeight"]
    half = drawing.VALUE_TEXT_HALF_WIDTH
    silhouettes = drawing.sheet_view_silhouettes()
    assert silhouettes["right"][2] + drawing.ARROW_LENGTH <= text_x - half
    assert text_x + half <= silhouettes["view B"][0] - 0.005
    assert text_y == pytest.approx(
        drawing._elevation_y(spec.PINCH_HEIGHT / 2.0, drawing.RIGHT_CENTER)
    )


def test_slit_breaks_into_the_adjuster_thread_at_the_printed_limits() -> None:
    """With the heights at .X the slit floor (SlitDepth down from the top)
    must still open into the adjuster's tap drill (AxisHeight up from the
    foot) by 0.25, or the jaws never grip the thread."""
    spec = dt_cone_tip_block_spec
    floor_max = _printed("BlockHt", spec.BLOCK_HEIGHT)[1] - _printed(
        "SlitDepth", spec.SLIT_DEPTH
    )[0]
    crown_min = _printed("AxisHeight", spec.ADJUSTER_AXIS_HEIGHT)[0] + (
        spec.ADJUSTER_BORE_DIA / 2.0
    )
    assert crown_min - floor_max >= 0.25


# --- r3, round two: the 17 block, the 5/8 pinch screw, the -X datum ---------
# Main's ruling (option (a), 2026-09-25): a #4-40 x 5/8 18-8 stainless
# fillister (McMaster 91794A112) in a 17-wide block, PassageCenter printed
# from the -X face, and a print-worst containment contract.  As above, each
# number is recomputed from the print's grades.
_PINCH_MAJOR_MM = 0.112 * 25.4  # #4-40 basic major


def _datum_face_x(feature: str) -> float:
    """Sketch x of the face the model's ``feature`` reference measures from."""
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    start = re.search(r"start=\(([^,]+),", _reference_call(body, feature))
    assert start is not None, feature
    return float(eval(start.group(1), vars(part)))


def _worst_head_face_half() -> float:
    """Farthest the +X (screw-head) face can stand from the adjuster axis at
    the printed limits, PassageCenter taken from the face the model uses."""
    spec = dt_cone_tip_block_spec
    passage = _printed("PassageCenter", spec.BLOCK_X / 2.0)
    width = _printed("Width", spec.BLOCK_X)
    if _datum_face_x("PassageCenterReference") < 0.0:
        return width[1] - passage[0]
    return passage[1]


def _worst_far_wall_from_head() -> float:
    """The slit's far wall, where the far jaw's thread starts, from the head."""
    spec = dt_cone_tip_block_spec
    return _worst_head_face_half() + _printed("SlitW", spec.SLIT_W)[1] / 2.0


def test_far_jaw_keeps_1_5d_of_thread_past_the_slits_far_wall() -> None:
    """72ab asserted 1.5D to the NEAR wall, crediting the slit as thread: the
    1/2 screw kept 3.835 (1.35D) past the far wall.  The 5/8 screw keeps
    6.26 (2.20D) at the printed worst case, the width's band on the head's
    side under the -X datum, Width and PassageCenter at .XXX."""
    spec = dt_cone_tip_block_spec
    engagement = spec.PINCH_SCREW_LENGTH - _worst_far_wall_from_head()
    assert engagement >= 1.5 * _PINCH_MAJOR_MM, engagement
    assert spec.WORST_PINCH_ENGAGEMENT_MM == pytest.approx(engagement)
    assert engagement == pytest.approx(6.26)


def test_pinch_screw_tip_stays_inside_the_minus_x_face() -> None:
    """Regression pin (the 1/2 screw passed it too): at the width's lower
    limit the 5/8 screw's tip stays 0.25 inside the far face; Width at .XXX
    leaves 0.995."""
    spec = dt_cone_tip_block_spec
    recess = _printed("Width", spec.BLOCK_X)[0] - spec.PINCH_SCREW_LENGTH
    assert recess >= 0.25
    assert spec.WORST_PINCH_TIP_RECESS_MM == pytest.approx(recess)
    assert recess == pytest.approx(0.995)


def test_axis_and_hold_down_tap_locate_from_the_minus_x_face() -> None:
    """Main's datum: PassageCenter, and the hold-down tap's FootTapX with it,
    measure from the -X face, FootTapZ from the north face; the model, the
    spec and both prints agree."""
    spec = dt_cone_tip_block_spec
    for feature in ("PassageCenterReference", "FootTapXReference"):
        assert _datum_face_x(feature) == pytest.approx(-spec.BLOCK_X / 2.0), feature
    assert spec.PASSAGE_CENTER_DATUM == "-X"
    # Each print's extension lines rise from its datum face and the centre.
    ink = drawing.sheet_dimension_ink()
    half_x = spec.BLOCK_X * drawing._S / 2.0

    def witnesses(name: str, across: int) -> list[float]:
        return sorted({round(a[across], 9) for a, b in ink[name].lines if a[across] == b[across]})

    assert witnesses("PassageCenter", 0) == pytest.approx(
        [drawing.FRONT_CENTER[0] - half_x, drawing.FRONT_CENTER[0]]
    )
    tap_x, tap_y = drawing.FOOT_TAP_CENTER
    assert witnesses("FootTapX", 0) == pytest.approx([drawing._BOTTOM_LEFT, tap_x])
    assert witnesses("FootTapZ", 1) == pytest.approx(
        [tap_y, drawing._bottom_y(drawing.Z_NORTH)]
    )



def test_print_worst_containment_fails_off_the_plate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CodeRabbit (#838): the print-worst check read the plate's side edges by
    extrapolating them, so a block run off the plate's south end still found
    'plate' there, and the extrapolated edges widen southwards.  A station off
    the plate must fail loud, as the nominal loop's _plat_half_width does."""
    import build_dt_drive_train_assembly as drive_train

    south_end = (
        drive_train.PIVOT_STATION + drive_train.PLAT_OVERHANG - drive_train.PLAT_LEN
    )
    off_the_end = south_end + drive_train.TIP_BLOCK_Z / 2.0 - 1.0
    monkeypatch.setattr(drive_train, "TIP_BLOCK_STATION", off_the_end)
    with pytest.raises(AssertionError, match="overhang the swing platform"):
        drive_train.tip_block_print_worst_containment_mm({"+X": 1.0, "-X": 1.0})
    assert drive_train._plat_side_half_widths(south_end - 1.0) == {"+X": -1.0, "-X": -1.0}
    assert drive_train._plat_side_half_widths(
        drive_train.PIVOT_STATION + drive_train.PLAT_OVERHANG + 1.0
    ) == {"+X": -1.0, "-X": -1.0}


def test_drive_train_screw_keeps_1_5d_past_the_far_wall() -> None:
    """The drive train's own check read the NEAR jaw at nominal (12.7 -
    (15 - 1.2)/2 >= 1.5 mm).  The placed screw keeps 1.5D past the printed
    worst far wall, and is the screw the block was sized for."""
    import build_dt_drive_train_assembly as drive_train

    engagement = drive_train.PINCH_SHANK_LEN - _worst_far_wall_from_head()
    assert engagement >= 1.5 * _PINCH_MAJOR_MM, engagement
    source = Path(drive_train.__file__).read_text(encoding="utf-8")
    assert "_PINCH_NEAR_JAW" not in source
    assert "PINCH_SHANK_LEN - TIP_WORST_PINCH_FAR_WALL_MM" in source


def test_pinch_screw_is_the_5_8_stainless_fillister() -> None:
    """The hardware follows the ruling: 91794A112 everywhere and 15.875 under
    the head.  The stainless-over-steel (galvanic) choice is design
    rationale, not a machinist instruction: the material rides the title
    block and the purchased-part ID, so the installation note no longer
    restates it.  The sentence was deleted per the codex machinist review
    of MHA-VN-018 and Main's ruling (a)."""
    import _config
    from _fastener_catalog import fastener
    from diagnostics.diag_mcmaster_fillister import FILLISTER_SIZES

    config = _config.parts("vn-cone-tip-pinch-screw")
    assert config["supplier_skus"] == ["91794A112"]
    assert "18-8 stainless" in config["material"]
    notes = config["installation_notes"].upper()
    assert "STAINLESS" not in notes
    assert "18-8" not in notes
    assert " STEEL" not in notes
    assert fastener("vn-cone-tip-pinch-screw").skus == ("91794A112",)
    assert fastener("vn-cone-tip-pinch-screw").material == "AISI 304"
    assert FILLISTER_SIZES["91794A112"][1] == dt_cone_tip_block_spec.PINCH_SCREW_LENGTH
    assert dt_cone_tip_block_spec.PINCH_SCREW_SKU == "91794A112"
    assert "90280A110" not in FILLISTER_SIZES


# Run 1 (d09c2b9eb leaf dump, c2-dumps/cone-tip-block-d09c2b9eb.json.gz):
# section A's north arrow ran 0.072 -> 0.084 at y 0.209, and PassageCenter's
# 7.50 was centred at (0.0795, 0.205828).  layoutcheck's replay read the
# arrow 1.45 mm over the value (c5-near-crops/cone-tip-block-01).
_RUN1_SECTION_ARROW = ((0.072, 0.209), (0.084, 0.209))
_RUN1_PASSAGE_CENTER = (0.0795, 0.205828)


def test_sheet_audit_sees_section_arrows_run1_hid() -> None:
    """The sheet's own audit fed only dimension and leader arrows, so a
    cutting-plane arrow over a value passed it.  Planted from run 1, the
    same value is clear without the section arrow and flagged with it."""
    x, y = _RUN1_PASSAGE_CENTER
    half_w, half_h = drawing.VALUE_TEXT_HALF_WIDTH, drawing.VALUE_TEXT_HALF_HEIGHT
    texts = {"PassageCenter": (x - half_w, y - half_h, x + half_w, y + half_h)}
    assert drawing.sheet_ink_collisions(texts, {}, {}, {}) == []
    arrow = {"section A north": drawing.section_arrow_ink(*_RUN1_SECTION_ARROW)}
    # Its head, 3.2 across, reached into the value's box, as on the render.
    findings = drawing.sheet_ink_collisions(texts, {}, arrow, {})
    assert _findings_match(
        findings,
        [
            "text-on-line: section A north's dimension line crosses 'PassageCenter'",
            "arrow-near-text: section A north's arrow ... 'PassageCenter'",
        ],
    ), findings


def test_section_arrows_stand_clear_of_every_value() -> None:
    """Today both cutting-plane arrows keep ARROW_TEXT_CLEARANCE (2 mm) from
    every text: PassageCenter's value moved to the slit's left with its
    datum, 3.57 mm from the north arrow on the 9.75 prism (2.5 on the 11.75
    one, 3.5 until #955 dropped that end to clear its letter off the plan);
    VIEW C's letter is 2.65 mm from the south one.  The build cuts the
    section where the model draws it."""
    from _drawing_leaders import distance_to_box

    texts = drawing.sheet_text_boxes()
    ink = drawing.sheet_dimension_ink()
    gaps = {}
    for arrow in drawing.sheet_section_arrows():
        for name, box in texts.items():
            if name == arrow:
                continue
            nearest = min(distance_to_box(s, box) for s in ink[arrow].arrows)
            gaps[(arrow, name)] = nearest - drawing.ARROW_HALF_WIDTH
    assert min(gaps.values()) >= drawing.ARROW_TEXT_CLEARANCE
    assert gaps[("section A north", "PassageCenter")] == pytest.approx(0.00357, abs=5e-5)
    assert gaps[("section A south", "view C letter")] == pytest.approx(0.00265, abs=5e-5)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert "_plan_y(Z_NORTH) - SECTION_NORTH_OVERSHOOT)" in body
    assert "_plan_y(Z_SOUTH) + SECTION_LINE_OVERSHOOT)" in body


def _north_letter_ink_gap(overshoot: float) -> float:
    """Nearest ink between section A's north letter and the plan's outline,
    with the north end ``overshoot`` past the plan (the two boxes stand
    corner to corner, so this is their corners' distance)."""
    left, down, right, up = drawing.SECTION_LETTER_BOX
    tip_x = drawing.TOP_CENTER[0] + drawing.SECTION_ARROW_LENGTH
    tip_y = drawing._plan_y(drawing.Z_NORTH) - overshoot
    letter = (tip_x + left, tip_y + down, tip_x + right, tip_y + up)
    plan = drawing.sheet_view_silhouettes()["plan"]
    dx = max(plan[0] - letter[2], letter[0] - plan[2], 0.0)
    dy = max(plan[1] - letter[3], letter[1] - plan[3], 0.0)
    return math.hypot(dx, dy)


def test_section_a_north_letter_clears_the_plan() -> None:
    """#955: the north letter keeps TEXT_CLEARANCE from the plan's outline,
    the clearance every cutting-plane letter on the release sheets holds.
    The model's letter is the one the build prints."""
    assert drawing.sheet_text_boxes()["section A north"][3] == pytest.approx(
        drawing._plan_y(drawing.Z_NORTH) - drawing.SECTION_NORTH_OVERSHOOT
        + drawing.SECTION_LETTER_BOX[3]
    )
    assert _north_letter_ink_gap(drawing.SECTION_NORTH_OVERSHOOT) >= drawing.TEXT_CLEARANCE


def test_the_4mm_north_end_left_its_letter_on_the_plan() -> None:
    """Fail-first: at the 4 mm overshoot both ends had until #955, the letter
    stood 1.45 mm off the 3:2 plan's edge; at 2:1 it meets the plan."""
    assert _north_letter_ink_gap(0.004) < drawing.TEXT_CLEARANCE


# --- the hold-down tap (user ruling 2026-09-29) -------------------------------
# MHA-VN-030 rises from under the platform into a blind #4-40 tap in the foot.
# Each mutation below moves one spec input past a limit the spec guards at
# import; the unmutated module imports, so the guard is what fails.
_FOOT_TAP_MUTATIONS = {
    "screw engages under 1.5D": (
        "HOLDDOWN_LEDGE_RANGE_MM = (2.21, 3.49)",
        "HOLDDOWN_LEDGE_RANGE_MM = (2.21, 6.0)",
    ),
    "screw reaches the incomplete threads": (
        "FOOT_THREAD_DEPTH = 8.5",
        "FOOT_THREAD_DEPTH = 7.5",
    ),
    "drill leaves the tap no lead": (
        "FOOT_DEPTH = 11.1",
        "FOOT_DEPTH = 8.6",
    ),
    "tap station band eats a web": (
        "FOOT_TAP_STATION_TOL_MM = 0.10",
        "FOOT_TAP_STATION_TOL_MM = 4.0",
    ),
}


def _import_mutant(old: str, new: str) -> None:
    import types

    source = Path(dt_cone_tip_block_spec.__file__).read_text(encoding="utf-8")
    assert source.count(old) == 1, old
    mutant = types.ModuleType("cone_tip_block_spec_mutant")
    mutant.__file__ = dt_cone_tip_block_spec.__file__
    exec(compile(source.replace(old, new), dt_cone_tip_block_spec.__file__, "exec"), mutant.__dict__)


@pytest.mark.parametrize("mutation", sorted(_FOOT_TAP_MUTATIONS))
def test_spec_refuses_a_hold_down_tap_that_cannot_hold(mutation: str) -> None:
    with pytest.raises(AssertionError):
        _import_mutant(*_FOOT_TAP_MUTATIONS[mutation])


def test_hold_down_tap_keeps_every_limit_at_the_printed_extremes() -> None:
    """Recomputed from the print: the screw's longest reach from the
    platform's thinnest ledge stays 0.25 short of the full thread's shortest
    print, it engages 1.5D from the thickest ledge, and the thread stands
    2 mm inside every face at its explicit station bands."""
    spec = dt_cone_tip_block_spec
    ledge_min, ledge_max = spec.HOLDDOWN_LEDGE_RANGE_MM
    places = spec.FOOT_DEPTH_PLACES
    thread_min = round(spec.FOOT_THREAD_DEPTH, places) - _GENERAL[places]
    assert spec.HOLDDOWN_SCREW_LENGTH - ledge_min <= thread_min - 0.25
    assert spec.HOLDDOWN_SCREW_LENGTH_MIN - ledge_max >= 1.5 * _PINCH_MAJOR_MM
    thread_r = _PINCH_MAJOR_MM / 2.0  # the hold-down is #4-40 too
    x_low, x_high = _printed("FootTapX", spec.FOOT_TAP_X)
    z_low, z_high = _printed("FootTapZ", spec.FOOT_TAP_Z)
    width_min = _printed("Width", spec.BLOCK_X)[0]
    depth_min = _printed("Depth", spec.BLOCK_Z)[0]
    webs = {
        "west": x_low - thread_r,
        "east": width_min - x_high - thread_r,
        "north": z_low - thread_r,
        "south": depth_min - z_high - thread_r,
    }
    assert min(webs.values()) >= 2.0, webs


def test_foot_tap_callout_reads_as_a_blind_tap_with_both_depths() -> None:
    """Policy rule 7 on the resolved callout: the thread and its full-thread
    depth on one line, the tap drill's depth on another, no THRU."""
    spec = dt_cone_tip_block_spec
    places = spec.FOOT_DEPTH_PLACES
    thread = f"{spec.HOLDDOWN_THREAD.lstrip('#')} UNC-2B"
    full = f"{spec.FOOT_THREAD_DEPTH:.{places}f}"
    drill = f"{spec.FOOT_DEPTH:.{places}f}"
    good = {1: f"{thread} x {full}", 2: f"DRILL {spec.FOOT_BORE_DIA:.2f} x {drill}"}
    assert drawing._foot_tap_callout_resolved(good)
    assert not drawing._foot_tap_callout_resolved({**good, 2: f"DRILL {spec.FOOT_BORE_DIA:.2f} THRU"})
    assert not drawing._foot_tap_callout_resolved({**good, 1: thread})
    assert not drawing._foot_tap_callout_resolved({1: good[1], 2: ""})
    # The native two places would print 8.50 and 11.10; neither reads as .X.
    assert not drawing._foot_tap_callout_resolved(
        {1: f"{thread} x {spec.FOOT_THREAD_DEPTH:.2f}", 2: f"x {spec.FOOT_DEPTH:.2f}"}
    )

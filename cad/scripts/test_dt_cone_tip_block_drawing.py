"""Offline manufacturing contracts for the cone-tip-block drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_dt_cone_tip_block as part
import dt_cone_tip_block_spec
import draw_dt_cone_tip_block as drawing
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import drilled_oversize_mm, printed_band_mm
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
    assert spec.ADJUSTER_EMBED_WINDOW == pytest.approx((5.3086, 9.0424))
    low, high = spec.ADJUSTER_EMBED_WINDOW
    assert low == pytest.approx(1.0 * 4.826 + spec.ADJUSTER_CSK, abs=1e-3)
    assert high == pytest.approx(spec.BLOCK_Z - 0.127 - spec.ADJUSTER_CSK)
    assert low < spec.ADJUSTER_EMBED < high
    assert drawing.ADJUSTER_CSK_QUALIFIER == "90° CSK Ø.197 BOTH ENDS"


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
        "<hw-threaddesc> <hw-threadclass> <hw-thru>\n90° CSK Ø.197 BOTH ENDS"
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
    # Rule 12 (machinist review of 04848e25c): the tap drill says DRILL.
    assert rewritten[7] == "<MOD-DIAM> <hw-thrutapdrldia> DRILL TO SLOT"
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
    # U24b / U27: every web keeps the wall target at the printed limits after
    # edge breaks.  #290: the inch grades (.XX +/-.01, .XXX +/-.005) are
    # tighter than the mm ones they replace, so every web grows.
    assert spec.WORST_SLIT_MOUTH_WEB_MM == pytest.approx(3.723, abs=1e-3)
    assert spec.WORST_TOP_LIGAMENT_MM == pytest.approx(2.889, abs=1e-3)
    assert spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM == pytest.approx(5.354, abs=1e-3)
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
    from _cone_axis_constants import CONE_AXIS_HEIGHT_MM

    assert spec.ADJUSTER_AXIS_HEIGHT == CONE_AXIS_HEIGHT_MM
    assert abs(spec.SLIT_FLOOR - (spec.ADJUSTER_AXIS_HEIGHT - 0.65)) < 1e-12
    assert abs(spec.PINCH_HEIGHT - spec.ADJUSTER_AXIS_HEIGHT - spec.PINCH_RISE) < 1e-12
    assert spec.DRAWING_DIMENSIONS["AxisHeightReference"] == {"AxisHeight"}


def test_pinch_thread_readback_checks_the_thread_part_not_string_order() -> None:
    """c6981bac (run 244bc8bb) resolved exactly this and was wrongly refused."""
    resolved = {
        1: "4-40 UNC - 2B TO SLOT\nCOAXIAL WITH CLEARANCE",
        2: "",
        3: "<MOD-DIAM> 2.26 DRILL TO SLOT",
        4: "",
    }
    assert drawing._pinch_thread_callout_resolved(resolved)
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 1: "COAXIAL WITH CLEARANCE\n4-40 UNC - 2B TO SLOT"}
    )
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 3: "<MOD-DIAM> 2.26 THRU ALL"}
    )
    assert not drawing._pinch_thread_callout_resolved(
        {**resolved, 3: "<MOD-DIAM> 2.26 TO SLOT"}
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


def test_sheet_cuts_no_section() -> None:
    """Machinist review of f86ff6bf8 (gating, two of three runs): section
    A-A, cut down the slot at 8.500, clipped the Ø2.26 hold-down tap drill
    at 7.500 into an unexplained 1 mm sliver, and every hole it showed is
    fully defined by its callout (rule 1).  The sheet cuts no section, so no
    cutting-plane line, label or ROTATED note prints."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "create_section_view" not in source
    assert "ROTATED" not in source
    assert "section A-A" not in drawing.sheet_view_silhouettes()
    assert not any(name.startswith("section") for name in drawing.sheet_text_boxes())


def test_only_views_dimensioning_hidden_sketches_opt_in() -> None:
    """The opt-in import goes where a kept dimension lives on a hidden sketch.

    Right (PinchDepthCenter, and r3's PinchHeight) and the bottom view (the
    hold-down tap's two stations) always do; the adjuster elevation
    (AxisHeight/PassageCenter) opts in at build time; the plan, left and the
    base front keep only solid-feature dimensions and stay on
    _drawing_dimension_import's targeted import.
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
    hold-down tap's two stations (2026-09-29).  The slit's depth runs to a
    floor inside the bore that no view draws, so the part no longer marks it
    (machinist review of e04fd60ab)."""
    adjuster_axis = {"AxisHeight", "PassageCenter"}
    kept = [
        *drawing.FRONT_KEEP,
        *drawing.TOP_KEEP,
        *drawing.RIGHT_KEEP,
        *drawing.LEFT_KEEP,
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
    assert "SlitDepth" not in marked
    assert "SlitDepth" not in dt_cone_tip_block_spec.DRAWING_PRECISION_BY_NAME
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
    assert "SlitW" in drawing.ARROWS_OUTSIDE
    # Machinist review of e04fd60ab: the width states the slit's extent, and
    # that row clears the outside arrow tails over the slot (its own and
    # PassageCenter's, which runs from the slot centre).
    assert drawing.DIMENSION_CALLOUTS_ABOVE["SlitW"] == "SLOT INTO BORE"
    row_left = text_x - drawing._callout_half_width("SLOT INTO BORE")
    assert row_left >= right_wall + drawing.OUTSIDE_ARROW_RUN + drawing.TEXT_CLEARANCE


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


def test_pinch_depth_dimension_line_stands_clear_of_the_block() -> None:
    """At +0.003 the 6.0's dimension line printed on the block's top edge."""
    top = drawing._elevation_y(part.BLOCK_HEIGHT, drawing.RIGHT_CENTER)
    line_y = drawing.RIGHT_KEEP["PinchDepthCenter"][1]
    assert line_y - top >= 0.005


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
        "PinchHeight",
        "PinchDepthCenter",
        "Width",
        "FootTapX",
        "Depth",
    )
    # d84a42ca7: the 4.875's inside arrows struck its "5".  The plan depth's
    # text stands on its offset shelf, so its arrows stand inside and the
    # line between them meets the shelf's leader (machinist review, PR 2107).
    assert drawing.ARROWS_OUTSIDE == ("SlitW", "FootTapZ")
    depth = drawing.sheet_dimension_ink()["Depth"]
    depth_line = (
        (drawing.PLAN_DEPTH_LINE_X, drawing._plan_y(drawing.Z_NORTH)),
        (drawing.PLAN_DEPTH_LINE_X, drawing._plan_y(drawing.Z_SOUTH)),
    )
    assert depth_line in depth.lines
    leader_start = (drawing.PLAN_DEPTH_LINE_X, drawing._plan_y(0.0))
    assert any(segment[0] == leader_start for segment in depth.lines)
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
    """#946 / MHA-DT-21: RD1's callout stood below-right of the adjuster hole and
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
# The machinist review of d84a42ca7 dropped the explicit +/-0.10 bands: every
# dimension prints the title block's general band for its places, except the
# width, which prints its own one-sided band (machinist review of 83e3370f9).
_UNIT = dt_cone_tip_block_spec.UNIT
_GENERAL = {places: printed_band_mm(places, unit=_UNIT) for places in (1, 2, 3)}
_BANDED = {"Width": (0.0, -0.508)}  # (upper, lower) as the sheet prints it
_DRILLED_PLUS = drilled_oversize_mm(unit=_UNIT)


def _on_print(nominal: float, places: int) -> float:
    """The value the inch sheet states, back in millimetres."""
    return round(nominal / 25.4, places) * 25.4


def _printed(name: str, nominal: float) -> tuple[float, float]:
    if name in _BANDED:
        upper, lower = _BANDED[name]
        return nominal + lower, nominal + upper
    places = dt_cone_tip_block_spec.DRAWING_PRECISION_BY_NAME[name]
    band = _GENERAL[places]
    return _on_print(nominal, places) - band, _on_print(nominal, places) + band


def test_width_carries_a_one_sided_band_that_holds_containment() -> None:
    """Rules 4 and 19 (machinist review of 83e3370f9): the width only has to
    keep its +X face inside the plate's west edge, so it may only come in from
    17.0; the model carries that band natively on Width@BlockProfile."""
    spec = dt_cone_tip_block_spec
    assert spec.BLOCK_WIDTH_BAND == _BANDED["Width"]
    assert spec.BLOCK_WIDTH_LIMITS == pytest.approx(_printed("Width", spec.BLOCK_X))
    assert spec.DRAWING_PRECISION_BY_NAME["Width"] == 2
    assert model_toleranced_dimensions(part)[("BlockProfile", "Width")] == (
        "*deviations(BLOCK_WIDTH_BAND)"
    )


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
    clearance_max = spec.PINCH_CLEARANCE_DIA + _DRILLED_PLUS
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
        {1: "<MOD-DIAM> .129 DRILL TO SLOT", 2: "", 3: "", 4: ""}
    )
    assert not drawing._pinch_clearance_callout_resolved(
        {1: "<MOD-DIAM> .129 <HOLE-DEPTH> .272", 2: "", 3: "", 4: ""}
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
    """Over-specification: no size prints a place no fit or asserted margin
    needs.  The rise leaves the print (the pinch hole locates from the foot).
    2026-09-29: the block's foot sits straight on the platform, so AxisHeight
    is the block's own fit; the machinist review of d84a42ca7 printed it .XX,
    the cup capture's grade, with no band of its own."""
    grades = dt_cone_tip_block_spec.DRAWING_PRECISION_BY_NAME
    assert grades["Depth"] == 3
    assert grades["BlockHt"] == 2
    assert grades["AxisHeight"] == 2
    assert "PinchRise" not in grades
    # Nothing prints .X: on the inch sheet its +/-.1 fails every web.
    assert {name for name, places in grades.items() if places == 2} == {
        "Width",
        "BlockHt",
        "PinchHeight",
        "PinchDepthCenter",
        "SlitW",
        "AxisHeight",
    }


def test_every_three_place_size_names_its_mate_at_its_dimension() -> None:
    """Rules 3/4 (machinist review of d84a42ca7): a three-place size given a
    function is a tight band, and its dimension names the mate it serves.
    The tap's two stations locate one hole, named on that hole's callout."""
    grades = dt_cone_tip_block_spec.DRAWING_PRECISION_BY_NAME
    texts = {**drawing.DIMENSION_CALLOUTS, **drawing.DIMENSION_CALLOUTS_ABOVE}
    for name in ("FootTapX", "FootTapZ"):
        texts[name] = drawing.FOOT_TAP_QUALIFIER
    three_place = {name for name, places in grades.items() if places == 3}
    assert three_place == {"Depth", "PassageCenter", "FootTapX", "FootTapZ"}
    # The width's band is its own, one-sided; its reason still names the edge.
    assert "MHA-DT-20" in texts["Width"]
    for name in three_place:
        assert re.search(r"MHA-(?!VN-)[A-Z]{2}-(?:[0-9]{2}(?:-TL-(?:[0-9]{2}|VN-[5-9][0-9]))?|VN-[5-9][0-9])(?:-T[0-9]{3})?(?![A-Z0-9-])", texts[name]), name
    # SolidWorks drops multi-line text placed above a dimension.
    assert all("\n" not in text for text in drawing.DIMENSION_CALLOUTS_ABOVE.values())


def test_top_ligament_needs_the_pinch_height_at_two_places() -> None:
    """The ligament over the pinch hole closes at the wall target with the
    pinch height at .XX; at the inch .X it would not."""
    spec = dt_cone_tip_block_spec
    clearance_r = (spec.PINCH_CLEARANCE_DIA + _DRILLED_PLUS) / 2.0
    height_min = _printed("BlockHt", spec.BLOCK_HEIGHT)[0]

    def ligament(places: int) -> float:
        pinch_max = _on_print(spec.PINCH_HEIGHT, places) + _GENERAL[places]
        return height_min - pinch_max - clearance_r - 2.0 * spec.EDGE_BREAK_MAX_MM

    assert ligament(2) == pytest.approx(spec.WORST_TOP_LIGAMENT_MM)
    assert round(ligament(2), 6) >= WALL_TARGET_MM > ligament(1)


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


def test_slit_floor_stands_inside_the_adjuster_tap_drill() -> None:
    """The slit must open into the adjuster's tap drill or the jaws never grip
    the thread.  The print says SLOT INTO BORE instead of a depth because the
    modelled floor lies wholly inside the drill, leaving no face to measure."""
    spec = dt_cone_tip_block_spec
    radius = spec.ADJUSTER_BORE_DIA / 2.0
    below_axis = spec.ADJUSTER_AXIS_HEIGHT - spec.SLIT_FLOOR
    assert radius + below_axis >= 0.25
    assert math.hypot(below_axis, spec.SLIT_W / 2.0) < radius
    assert spec.WORST_SLIT_BREAKTHROUGH_MM == pytest.approx(radius + below_axis)
    assert drawing.DIMENSION_CALLOUTS_ABOVE["SlitW"] == "SLOT INTO BORE"


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
    2.25D at the printed worst case: the width's one-sided band tops out at
    its nominal on the head's side under the -X datum, PassageCenter .XXX."""
    spec = dt_cone_tip_block_spec
    engagement = spec.PINCH_SCREW_LENGTH - _worst_far_wall_from_head()
    assert engagement >= 1.5 * _PINCH_MAJOR_MM, engagement
    assert spec.WORST_PINCH_ENGAGEMENT_MM == pytest.approx(engagement)
    assert engagement == pytest.approx(6.477)


def test_pinch_screw_tip_stays_inside_the_minus_x_face() -> None:
    """Regression pin (the 1/2 screw passed it too): at the width's lower
    limit the 5/8 screw's tip stays 0.25 inside the far face; the one-sided
    band's lower limit leaves 0.635."""
    spec = dt_cone_tip_block_spec
    recess = _printed("Width", spec.BLOCK_X)[0] - spec.PINCH_SCREW_LENGTH
    assert recess >= 0.25
    assert spec.WORST_PINCH_TIP_RECESS_MM == pytest.approx(recess)
    assert recess == pytest.approx(0.635)


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
    of MHA-DT-VN-56 and Main's ruling (a)."""
    import _config
    from _fastener_catalog import fastener
    from _mcmaster_91794a112 import FILLISTER_SIZE

    config = _config.parts("dt-vn-cone-tip-pinch-screw")
    assert config["supplier_skus"] == ["91794A112"]
    assert "18-8 stainless" in config["material"]
    notes = config["installation_notes"].upper()
    assert "STAINLESS" not in notes
    assert "18-8" not in notes
    assert " STEEL" not in notes
    assert fastener("dt-vn-cone-tip-pinch-screw").skus == ("91794A112",)
    assert fastener("dt-vn-cone-tip-pinch-screw").material == "AISI 304"
    assert FILLISTER_SIZE[1] == dt_cone_tip_block_spec.PINCH_SCREW_LENGTH
    assert dt_cone_tip_block_spec.PINCH_SCREW_SKU == "91794A112"


# --- the hold-down tap (user ruling 2026-09-29) -------------------------------
# MHA-DT-VN-60 rises from under the platform into a blind #4-40 tap in the foot.
# Each mutation below moves one spec input past a limit the spec guards at
# import; the unmutated module imports, so the guard is what fails.
_FOOT_TAP_MUTATIONS = {
    "screw engages under 1.5D": (
        "HOLDDOWN_LEDGE_RANGE_MM = (2.5908, 3.0988)",
        "HOLDDOWN_LEDGE_RANGE_MM = (2.5908, 6.0)",
    ),
    "screw reaches the incomplete threads": (
        "FOOT_THREAD_DEPTH = 8.636",
        "FOOT_THREAD_DEPTH = 6.9",
    ),
    "drill leaves the tap no lead": (
        "FOOT_DEPTH = 11.176",
        "FOOT_DEPTH = 8.6",
    ),
    "tap station band eats a web": (
        "FOOT_TAP_STATION_TOL_MM = printed_band_mm(FOOT_TAP_X_PLACES)",
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
    thread_min = _on_print(spec.FOOT_THREAD_DEPTH, places) - _GENERAL[places]
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
    assert min(webs.values()) >= WALL_TARGET_MM, webs


def test_foot_tap_callout_reads_as_a_blind_tap_with_both_depths() -> None:
    """drawing-guidelines.md rule 12 (hole and slot callouts say what to do) on the resolved callout: the thread and its full-thread
    depth on one line, the tap drill's depth on another, no THRU; rule 4:
    the mate the stations locate on closes the thread's part."""
    spec = dt_cone_tip_block_spec
    places = spec.FOOT_DEPTH_PLACES
    thread = f"{spec.HOLDDOWN_THREAD.lstrip('#')} UNC-2B"
    full = spec.length_text(spec.FOOT_THREAD_DEPTH, places)
    drill = spec.length_text(spec.FOOT_DEPTH, places)
    mate = f"\n{drawing.FOOT_TAP_QUALIFIER}"
    good = {1: f"{thread} x {full}{mate}", 2: f"DRILL {spec.FOOT_BORE_DIA:.2f} x {drill}"}
    assert drawing._foot_tap_callout_resolved(good)
    assert not drawing._foot_tap_callout_resolved({**good, 1: f"{thread} x {full}"})
    assert not drawing._foot_tap_callout_resolved({**good, 2: f"DRILL {spec.FOOT_BORE_DIA:.2f} THRU"})
    assert not drawing._foot_tap_callout_resolved({**good, 1: f"{thread}{mate}"})
    assert not drawing._foot_tap_callout_resolved({1: good[1], 2: ""})


def test_foot_tap_mate_line_closes_the_native_thread_part() -> None:
    native = {
        5: "<MOD-DIAM><hw-tapdrldia> <HOLE-DEPTH> <hw-tapdrldepth>",
        6: "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>",
        7: "",
        8: "",
    }
    rewritten = drawing._foot_tap_callout_definitions(native)
    assert rewritten == {**native, 6: f"{native[6]}\n{drawing.FOOT_TAP_QUALIFIER}"}
    with pytest.raises(RuntimeError):
        drawing._foot_tap_callout_definitions({**native, 7: native[6]})

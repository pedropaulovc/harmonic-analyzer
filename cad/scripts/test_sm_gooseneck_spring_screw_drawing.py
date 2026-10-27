"""Offline release contracts for MHA-SM-04, the gooseneck spring screw."""

from __future__ import annotations

import ast
import inspect
import math
from pathlib import Path

import pytest

import _config
import build_sm_gooseneck_spring_screw as part
import draw_sm_gooseneck_spring_screw as drawing
import sm_gooseneck_spring_screw_geom as geom
import sm_gooseneck_spring_screw_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


def test_registry_paths_and_part_name() -> None:
    registered = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
    assert registered.script == Path(drawing.__file__).resolve()
    assert registered.layout is DrawingLayout.LANDSCAPE
    assert registered.source.as_posix().endswith(
        "/sldprt/sm-gooseneck-spring-screw.SLDPRT"
    )
    assert drawing.SLDDRW.as_posix().endswith(
        "/slddrw/sm-gooseneck-spring-screw.SLDDRW"
    )
    assert drawing.PDF.as_posix().endswith("/pdf/sm-gooseneck-spring-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/sm-gooseneck-spring-screw_drawing.png")
    assert part.PART_NAME == registered.artifact_stem


def test_part_registry_row_is_the_made_screw() -> None:
    row = _config.parts("sm-gooseneck-spring-screw")
    assert row["number"] == "MHA-SM-04"
    assert row["title"] == "Gooseneck Spring Screw"
    assert row["description"] == "GOOSENECK SPRING SCREW"
    # Not a critical grade (rule 2): the field names the acceptable steels.
    for grade in ("12L14", "1018", "1/2 in"):
        assert grade in row["material"]
        assert grade in row["material_specification"]
    assert int(row["quantity"]) == 1
    # A static clamp, not a running fit.
    assert "fit_class" not in row
    assert row["process"] != "purchased"
    assert row["process"] == (
        "turned slotted fillister shoulder screw: plain Ø3.50 loop seat, "
        "45-degree lead, die-cut #8-32 thread"
    )
    assert part.MATERIAL == "Plain Carbon Steel"


def test_printed_material_fits_one_title_block_line() -> None:
    row = _config.parts("sm-gooseneck-spring-screw")
    assert len(str(row["material"])) <= 36
    assert "cold-finished" in str(row["material_specification"])


def test_stock_turns_the_head() -> None:
    # 1/2-in round cleans up to the Ø12.50 head.
    assert geom.STOCK_DIA == pytest.approx(12.7)
    assert geom.HEAD_DIA < geom.STOCK_DIA


def test_spec_is_the_single_source_of_marked_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) | set(drawing.END_KEEP) == marked
    assert not set(drawing.SIDE_KEEP) & set(drawing.END_KEEP)
    # The thread is defined by its callout, not a Ø4.17 dimension.  The
    # crown's sphere prints on its arc as a reference radius, not in a note
    # (machinist FIX round 1).
    assert "ThreadDia" not in marked
    assert spec.DRAWING_DIMENSIONS["HeadProfile"] == {
        "HeadDia",
        "HeadHeight",
        "CrownRise",
        "CrownRadius",
    }
    assert spec.DRAWING_DIMENSIONS["StationReference"] == {
        "OverallLength",
        "FullThread",
    }
    # The slot width is only true-size in the head-end view.
    assert set(drawing.END_KEEP) == {"SlotWidth"}
    # The lead stays unprinted: the two diameters fix it, the shoulder
    # length's callout names it, and no reference sketch restates it.
    assert "StepLead" not in marked
    assert set(spec.DRAWING_DIMENSIONS) == {
        "HeadProfile",
        "ShankProfile",
        "SlotProfile",
        "DriverSlot",
        "StationReference",
    }
    assert spec.DRAWING_DIMENSIONS["ShankProfile"] == {
        "UnderHeadLength",
        "SeatDia",
        "ShoulderLength",
        "TipChamfer",
    }


def test_model_owns_places_and_bands() -> None:
    assert "draw_sm_gooseneck_spring_screw.py" in PRECISION_MIGRATED_DRAWINGS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    one_place = {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 1
    }
    # Chamfers never need extra places (rule 3); every other mark is .XX.
    assert one_place == {"TipChamfer"}
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1, 2}
    assert spec.REFERENCE_DIMENSIONS == {"OverallLength", "CrownRadius"}
    # No mark carries a shared-helper band: the seat Ø and the shoulder
    # length are native LIMIT bands and the full-thread station a native
    # single MAX, all set by the part (owner ruling 2026-10-26 (#1951,
    # option B); machinist FIX round 1); every other mark takes the title
    # block's band.
    assert model_toleranced_dimensions(part) == {}
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))

    def calls(helper: str) -> set[tuple[str, ...]]:
        return {
            tuple(ast.unparse(arg) for arg in node.args[1:])
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == helper
        }

    assert calls("_limit_band") == {
        (
            "'ShankProfile'",
            "'SeatDia'",
            "(SEAT_DIA_LOWER, SEAT_DIA_UPPER)",
            "SEAT_DIA_TOL_TYPE",
        ),
        (
            "'ShankProfile'",
            "'ShoulderLength'",
            "(SHOULDER_LENGTH_LOWER, SHOULDER_LENGTH_UPPER)",
            "SHOULDER_LENGTH_TOL_TYPE",
        ),
    }
    # "5.67 MAX": the model value IS the printed limit (the shared
    # _single_limit_tolerance setter), its band running down to the lead's top.
    (single,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "set_single_limit"
    ]
    assert [ast.unparse(arg) for arg in single.args[1:]] == [
        "'StationReference'",
        "'FullThread'",
    ]
    assert {kw.arg: ast.unparse(kw.value) for kw in single.keywords} == {
        "limit": "FULL_THREAD_STATION_MAX",
        "band": "FULL_THREAD_STATION_MAX_BAND",
        "tol_type": "FULL_THREAD_STATION_MAX_TOL_TYPE",
    }
    assert calls("_single_limit") == set()
    assert geom.FULL_THREAD_STATION_MAX_BAND == (
        0.0,
        -round(geom.FULL_THREAD_STATION_MAX - geom.FULL_THREAD_STATION_MIN, 6),
    )
    assert geom.FULL_THREAD_STATION_MIN == pytest.approx(
        geom.SHOULDER_LENGTH_MIN + (geom.MAJOR_DIA - geom.SEAT_DIA_MAX) / 2.0
    )
    assert geom.SEAT_DIA_TOL_TYPE == 3  # swTolLIMIT
    assert geom.SHOULDER_LENGTH_TOL_TYPE == 3  # swTolLIMIT
    assert geom.FULL_THREAD_STATION_MAX_TOL_TYPE == 6  # swTolMAX
    # The crown radius's "SR" is authored on the part, as build_dt_pinion_lever
    # authors its cap's.
    assert calls("set_dimension_prefix") == {
        ("'HeadProfile'", "'CrownRadius'", "CROWN_RADIUS_PREFIX")
    }
    assert spec.CROWN_RADIUS_PREFIX == "SR"


def test_policy_sheet_carries_no_gdt_or_render_time_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_feature_control_frame",
        "add_datum_feature",
        "set_basic_dimension",
        "set_dimension_precision",
        "SetPrecision3",
        "add_surface_finish",
    ):
        assert helper not in source
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "author_part_pmi" not in build


def test_geometry_matches_the_settled_design() -> None:
    assert geom.HEAD_DIA == 12.50
    assert geom.HEAD_H == 7.00
    assert geom.CROWN_RISE == 1.00
    assert geom.HEAD_CYL_H == pytest.approx(6.00)
    assert geom.SLOT_WIDTH == 1.60
    assert geom.SLOT_DEPTH == 3.00
    assert geom.SLOT_FLOOR_Z == pytest.approx(4.00)
    assert geom.LENGTH == 16.00
    assert geom.MAJOR_DIA == pytest.approx(0.164 * 25.4)
    assert geom.SEAT_DIA == 3.50
    assert geom.SHOULDER_LENGTH == 3.90
    assert geom.OVERALL_LENGTH == pytest.approx(23.0)
    assert geom.CROWN_RADIUS == pytest.approx((6.25**2 + 1.0) / 2.0)
    assert geom.CROWN_CENTER_Z == pytest.approx(7.0 - geom.CROWN_RADIUS)


def test_slot_leaves_the_rule_12_head_web() -> None:
    # Shortest head, deepest slot, full title-block edge break.
    assert spec.EDGE_BREAK_MAX == 0.25
    assert spec.SLOT_WEB_MIN == pytest.approx(7.00 - 0.51 - 3.51 - 0.25)
    assert spec.SLOT_WEB_MIN >= spec.SLOT_WEB_TARGET == 2.0


def test_controlling_crown_rise_keeps_a_fillister_head_across_its_band() -> None:
    # Head Ø and height leave the dome free; the rise alone fixes it, so it
    # is printed controlling and the head must work at both ends of .XX.
    assert "CrownRise" in spec.DRAWING_DIMENSIONS["HeadProfile"]
    assert "CrownRise" not in spec.REFERENCE_DIMENSIONS
    assert (spec.CROWN_RISE_MIN, spec.CROWN_RISE_MAX) == pytest.approx((0.49, 1.51))
    # Shallowest slot under the tallest crown still cuts the cylindrical rim.
    assert spec.SLOT_RIM_CUT_MIN == pytest.approx(3.00 - 0.51 - 1.51)
    assert spec.SLOT_RIM_CUT_MIN > 0.0
    # Tallest crown on the shortest head keeps a side after the edge break.
    assert spec.HEAD_SIDE_MIN == pytest.approx(7.00 - 0.51 - 1.51 - 0.25)
    assert spec.HEAD_SIDE_MIN > 0.0
    # A dome at both ends, never past a hemisphere of the Ø12.50 head.
    assert 0.0 < spec.CROWN_RISE_MIN < spec.CROWN_RISE_MAX < geom.HEAD_DIA / 2.0


def test_seat_sits_under_the_thread_major() -> None:
    # Owner ruling 2026-10-26 (#1951, option B): the Ø3.50 seat keeps the old
    # #6-32 crest height (0.1380 in = 3.5052) within 0.003 radial.
    assert abs(geom.SEAT_DIA - 0.138 * 25.4) / 2.0 < 0.003
    # Its LIMIT band 3.60/3.40: the upper limit stays under the #8-32 2A
    # major minimum, so the lead always steps UP into the thread blank.
    assert (geom.SEAT_DIA_LOWER, geom.SEAT_DIA_UPPER) == pytest.approx((-0.10, 0.10))
    assert (geom.SEAT_DIA_MIN, geom.SEAT_DIA_MAX) == pytest.approx((3.40, 3.60))
    assert geom.THREAD_MAJOR_2A_MIN == pytest.approx(3.990, abs=1e-3)
    assert geom.SEAT_DIA_MAX < geom.THREAD_MAJOR_2A_MIN
    # The shoulder length's LIMIT band 4.10/3.70, to the lead's foot.
    assert (
        geom.SHOULDER_LENGTH_LOWER,
        geom.SHOULDER_LENGTH_UPPER,
    ) == pytest.approx((-0.20, 0.20))
    assert (geom.SHOULDER_LENGTH_MIN, geom.SHOULDER_LENGTH_MAX) == pytest.approx(
        (3.70, 4.10)
    )
    # Each LIMIT band names what it serves (drawing-guidelines.md rule 4).
    callouts = spec.DIMENSION_CALLOUTS_BY_NAME
    assert callouts["SeatDia"].splitlines() == [
        "MHA-SM-VN-51 LOOP",
        "SEAT, UNDER",
        "THREAD MAJOR",
    ]
    assert callouts["ShoulderLength"].splitlines() == [
        "TO 45 DEG LEAD; LOOP",
        "CLEARS LEAD",
    ]
    assert spec.CHAMFER_CALLOUT == "X 45 DEG"


def test_full_thread_limit_prints_on_the_part_not_in_a_note() -> None:
    # Machinist FIX round 1: the full-thread limit is an associative model
    # dimension from the under-head face, the longest shoulder, the
    # steepest-legged lead and the die's run-out floored to two places.
    budget = geom.SHOULDER_LENGTH_MAX + geom.STEP_LEAD_MAX + 1.5 * geom.PITCH
    assert budget == pytest.approx(5.6734, abs=1e-4)
    assert geom.FULL_THREAD_STATION_MAX == math.floor(budget * 100.0) / 100.0 == 5.67
    # A die still has a pitch of blank behind the lead at the longest shoulder.
    die_room = geom.SHOULDER_LENGTH_MAX + geom.STEP_LEAD_MAX + geom.PITCH
    assert geom.FULL_THREAD_DIE_ROOM_MIN == pytest.approx(die_room)
    assert geom.FULL_THREAD_STATION_MAX >= die_room
    with pytest.raises(AssertionError, match="no room behind the lead"):
        geom.require_shoulder_form(full_thread_station_max=die_room - 0.01)
    # Its callout parallels the shoulder length's "TO 45 DEG LEAD"; note 1
    # names the mate, so the callout names none (farm run 20261027T053051351Z:
    # "FULL THREAD IN MHA-SM-01" read as a plug-engagement statement).  It
    # stands ABOVE the value, which alone takes the dimension line.
    assert spec.DIMENSION_CALLOUTS_ABOVE == {
        "StationReference": {"FullThread": "TO FULL THREAD"}
    }
    assert "StationReference" not in spec.DIMENSION_CALLOUTS
    assert "MHA-SM-01" in spec.DRAWING_NOTES
    # The station sketch's witnesses lie on the outline: the under-head face
    # (from the thread radius up, under the head's rim) and the thread's
    # major silhouette from the printed station toward the tip.
    thread_r = geom.MAJOR_DIA / 2.0
    (f0, f1), (t0, t1) = part.FACE_WITNESS_LINE, part.THREAD_WITNESS_LINE
    assert f0 == pytest.approx((0.0, thread_r))
    assert f1[0] == 0.0 and thread_r < f1[1] < geom.HEAD_DIA / 2.0
    assert t0 == pytest.approx((geom.FULL_THREAD_STATION_MAX, thread_r))
    lead_top = geom.SHOULDER_LENGTH_MAX + geom.STEP_LEAD_MAX
    assert lead_top < t0[0] < t1[0] < geom.LENGTH - geom.TIP_CHAMFER
    assert t1[1] == t0[1]
    build = Path(part.__file__).read_text(encoding="utf-8")
    for record in (
        """stations.record("FullThreadRadius", '"ThreadDia" / 2')""",
        """stations.record("FullThread", '"FullThread"')""",
        '("FullThread", FULL_THREAD_STATION_MAX)',
    ):
        assert record in build
    assert "DIE_RUNOUT" not in spec.DRAWING_NOTES
    assert "FULL THREAD" not in spec.DRAWING_NOTES


def _shank_profile_points() -> list[tuple[float, float]]:
    """The builder's ShankProfile chain, evaluated in the builder's names."""
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))
    (node,) = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and [ast.unparse(target) for target in node.targets] == ["points"]
    ]
    return eval(compile(ast.Expression(node.value), "<points>", "eval"), vars(part))


def test_shank_profile_is_seat_lead_thread_and_tip() -> None:
    seat_r, thread_r = geom.SEAT_DIA / 2.0, geom.MAJOR_DIA / 2.0
    expected = [
        (0.0, 0.0),
        (0.0, seat_r),
        (geom.SHOULDER_LENGTH, seat_r),
        (geom.SHOULDER_LENGTH + geom.STEP_LEAD, thread_r),
        (geom.LENGTH - geom.TIP_CHAMFER, thread_r),
        (geom.LENGTH, thread_r - geom.TIP_CHAMFER),
        (geom.LENGTH, 0.0),
    ]
    points = _shank_profile_points()
    assert len(points) == len(expected)
    for got, want in zip(points, expected):
        assert got == pytest.approx(want)
    # The lead is 45 degrees: its axial leg equals its radial leg, the two
    # diameters' half-difference.
    (u0, v0), (u1, v1) = points[2], points[3]
    assert u1 - u0 == pytest.approx(v1 - v0) == pytest.approx(geom.STEP_LEAD)
    assert geom.STEP_LEAD == pytest.approx((geom.MAJOR_DIA - geom.SEAT_DIA) / 2.0)
    # The model holds it by equation from the two diameter globals, so the
    # radial leg (set by the diameters) is never dimensioned a second time.
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert """shank.record("StepLead", '("ThreadDia" - "SeatDia") / 2')""" in build
    # The lead's radial leg is never dimensioned a second time: the only
    # vertical leg in the shank profile is the tip chamfer's rise.
    shank = build[
        build.index("create_sketch shank profile") : build.index(
            "exit_sketch shank profile"
        )
    ]
    assert shank.count('"vertical_distance"') == 1
    # No hidden reference sketch restates the lead: only StationReference.
    assert build.count("blank_sketch(adapter, ") == 1


def test_thread_callout_names_the_size_but_not_the_title_block_class() -> None:
    assert spec.THREAD_CALLOUT == "#8-32 UNC"
    assert "2A" not in spec.THREAD_CALLOUT
    assert drawing.THREAD_CALLOUT is spec.THREAD_CALLOUT


def test_notes_are_short_and_carry_no_dimension_or_method() -> None:
    # Machinist FIX round 1: the crown's form and the full-thread limit print
    # on their features, so one note is left, carrying no figure.
    assert spec.DRAWING_NOTES == "1. THREAD MATES THE TAPPED END PLUG OF MHA-SM-01."
    for line in spec.DRAWING_NOTES.splitlines():
        # Only the mating part's number is quoted.
        text = line.split(". ", 1)[-1].replace("MHA-SM-01", "")
        assert not any(ch.isdigit() for ch in text), line
        for word in ("TORQUE", "LOCTITE", "N-M", "IN-LB", "SPHERICAL"):
            assert word not in line
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW\nSCALE 2:1"


def test_part_sheet_carries_no_assembly_instruction() -> None:
    # The clamp step (user ruling 2026-09-21: no torque value, no
    # threadlocker) prints in full as MHA-SM-00 step 8.
    notes = " ".join(spec.DRAWING_NOTES.split())
    assert "ASSEMBLY" not in notes
    assert "TIGHTEN" not in notes
    import sm_summing_assembly_sheet as summing

    step = next(s for s in summing.ASSEMBLY_STEPS if s.startswith("8. "))
    assert "MHA-SM-04" in step
    assert "CANNOT SWIVEL" in step
    assert step.endswith("NO THREADLOCKER.")
    for word in ("TORQUE", "N-M", "IN-LB"):
        assert word not in step
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes": DRAWING_NOTES' in build


def test_modelled_volume_is_the_turned_body_less_the_slot() -> None:
    r_head, r_thread, r_seat = 6.25, 0.164 * 25.4 / 2.0, 1.75
    shoulder, lead = 3.9, r_thread - r_seat
    rc = geom.CROWN_RADIUS
    cap = math.pi * 1.0**2 * (3.0 * rc - 1.0) / 3.0
    assert part.V_HEAD == pytest.approx(math.pi * r_head**2 * 6.0 + cap)
    # The major cylinder less the annulus over the seat and, by Pappus, the
    # lead's corner triangle (legs `lead`, centroid r_seat + 2 lead/3) and
    # the tip chamfer's (legs 0.3, centroid r_thread - 0.1).
    over_seat = math.pi * (r_thread**2 - r_seat**2) * shoulder
    over_lead = 2.0 * math.pi * (r_seat + 2.0 * lead / 3.0) * lead**2 / 2.0
    tip = 2.0 * math.pi * (r_thread - 0.1) * 0.045
    assert part.V_SHANK == pytest.approx(
        math.pi * r_thread**2 * 16.0 - over_seat - over_lead - tip
    )
    assert part.V_BODY == pytest.approx(part.V_HEAD + part.V_SHANK)
    # Independent slot volume: a 3-D midpoint grid over the strip.
    steps_z, steps_y = 600, 200
    half = 0.8
    total = 0.0
    dz, dy = 3.0 / steps_z, 2.0 * half / steps_y
    for i in range(steps_z):
        z = 4.0 + (i + 0.5) * dz
        r = r_head if z <= 6.0 else math.sqrt(rc**2 - (z - (7.0 - rc)) ** 2)
        for j in range(steps_y):
            y = -half + (j + 0.5) * dy
            if abs(y) < r:
                total += 2.0 * math.sqrt(r**2 - y**2) * dy * dz
    assert part.V_SLOT == pytest.approx(total, rel=2e-3)
    assert part.V_FINAL == pytest.approx(part.V_BODY - part.V_SLOT)


def test_side_view_stations_follow_the_model() -> None:
    scale = drawing.SHEET_SCALE[0] / 1000.0
    assert drawing.TIP_X - drawing.APEX_X == pytest.approx(geom.OVERALL_LENGTH * scale)
    assert drawing.UNDERHEAD_X - drawing.APEX_X == pytest.approx(geom.HEAD_H * scale)
    assert drawing.LEAD_FOOT_X - drawing.UNDERHEAD_X == pytest.approx(
        geom.SHOULDER_LENGTH * scale
    )
    assert drawing.LEAD_TOP_X - drawing.LEAD_FOOT_X == pytest.approx(
        geom.STEP_LEAD * scale
    )
    # Model +Z runs paper-left in *Right: head left, tip right.
    assert (
        drawing.APEX_X
        < drawing.RIM_X
        < drawing.SLOT_FLOOR_X
        < drawing.UNDERHEAD_X
        < drawing.LEAD_FOOT_X
        < drawing.LEAD_TOP_X
        < drawing.THREAD_START_X
        < drawing.TIP_X
    )
    # The bounding-box centre is the view centre.
    assert (drawing.APEX_X + drawing.TIP_X) / 2.0 == pytest.approx(
        drawing.SIDE_CENTER[0]
    )


def test_head_end_view_is_the_third_angle_left_view() -> None:
    assert drawing.END_CENTER[1] == drawing.SIDE_CENTER[1]
    head_radius = geom.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.END_CENTER[0] + head_radius < drawing.APEX_X - 0.030
    head_dia_x = drawing.SIDE_KEEP["HeadDia"][0]
    assert drawing.END_CENTER[0] + head_radius + 0.010 < head_dia_x < drawing.APEX_X
    slot_x = drawing.END_KEEP["SlotWidth"][0]
    assert drawing.END_CENTER[0] + head_radius < slot_x < head_dia_x - 0.010


def test_sheet_placements_stay_inside_the_border() -> None:
    inner = (0.0127, 0.0127, 0.4191, 0.2667)  # ASME B landscape inner border
    title_block = (0.218, 0.065)  # x >= and y <=
    points = [
        drawing.SIDE_CENTER,
        drawing.END_CENTER,
        drawing.ISO_CENTER,
        drawing.THREAD_NOTE_XY,
        drawing.ISO_NOTE_XY,
        drawing.NOTES_XY,
        drawing.SEAT_DIA_TEXT_XY,
        (drawing.TIP_X, drawing.SIDE_CENTER[1]),
        *drawing.SIDE_KEEP.values(),
        *drawing.END_KEEP.values(),
    ]
    for x, y in points:
        assert inner[0] < x < inner[2] and inner[1] < y < inner[3]
        assert not (x >= title_block[0] and y <= title_block[1])
    # The thread callout's leader lands on the full thread, never the lead.
    assert drawing.THREAD_PICK[0] == drawing.THREAD_START_X
    assert drawing.THREAD_START_X - drawing.LEAD_TOP_X > 0.0
    thread_half = geom.MAJOR_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert abs(drawing.THREAD_PICK[1] - drawing.SIDE_CENTER[1]) < thread_half
    assert drawing.THREAD_NOTE_XY[0] - drawing.THREAD_PICK[0] > 0.010
    # Text blocks follow the farm run 20261027T034356887Z render: block
    # centred on its anchor, 5.56 mm per callout line (and value over its
    # callout), 4.53 mm between stacked limits, 4.50 mm of first-line ink.
    assert drawing.block_height(2, 3) == pytest.approx(0.2388337 - 0.2131399, abs=2e-4)
    assert drawing.SEAT_DIA_TEXT_HEIGHT == drawing.block_height(2, 3)
    assert drawing.SHOULDER_LENGTH_TEXT_HEIGHT == drawing.block_height(2, 2)
    # The seat Ø stands on the seat, its line clear of the under-head
    # extension line, and its text hangs right of its own dimension line (its
    # leader meets the text's left end, so the leader runs beside the text,
    # not through it), below the thread silhouette and short of the
    # tip-chamfer extension lines (layout audit, farm run 20261010T190631112Z).
    assert drawing.SIDE_KEEP["SeatDia"][0] == drawing.SEAT_DIA_X
    assert drawing.UNDERHEAD_X + 0.003 <= drawing.SEAT_DIA_X < drawing.LEAD_FOOT_X
    text_x, text_y = drawing.SEAT_DIA_TEXT_XY
    # Unchanged from the reviewed render (anchor 0.2273, 0.142).
    assert (text_x, text_y) == pytest.approx((0.2273, 0.142))
    left = text_x - drawing.SEAT_DIA_TEXT_WIDTH / 2.0
    right = text_x + drawing.SEAT_DIA_TEXT_WIDTH / 2.0
    assert left > drawing.SEAT_DIA_X + 0.002
    assert right <= drawing.THREAD_START_X - 0.002
    # The stacked upper limit's top stays clear of the shank's lower outline
    # (rendered 1.8 mm clear in farm run 20261027T034356887Z).
    assert drawing.THREAD_BOTTOM_Y < drawing.SEAT_BOTTOM_Y
    seat_top = text_y + drawing.SEAT_DIA_TEXT_HEIGHT / 2.0
    assert seat_top <= drawing.THREAD_BOTTOM_Y - 0.0015
    # Its callout ends well above row 0.
    block_bottom = text_y - drawing.SEAT_DIA_TEXT_HEIGHT / 2.0
    assert block_bottom - drawing.SIDE_KEEP["UnderHeadLength"][1] >= 0.015
    # Two rows over the shank from the under-head face, the longer outside.
    assert drawing.FULL_THREAD_X == pytest.approx(
        drawing.UNDERHEAD_X + geom.FULL_THREAD_STATION_MAX * drawing._S / 1000.0
    )
    assert drawing.LEAD_TOP_X < drawing.FULL_THREAD_X < drawing.THREAD_START_X
    sl_line, ft_line = drawing.SHOULDER_LENGTH_LINE_Y, drawing.FULL_THREAD_LINE_Y
    assert sl_line >= drawing.THREAD_NOTE_XY[1] + 0.008
    assert sl_line >= drawing.THREAD_TOP_Y + 0.004
    assert ft_line - sl_line >= 0.008
    # The full-thread block centres over its own span, above its line.  The
    # extension lines overshoot the line by 1.0 mm, to the ink of the line on
    # it, so that line is the value alone and fits between them with 0.5 mm
    # a side; its one-line callout stands a line above, over the overshoot.
    ft_x, ft_y = drawing.SIDE_KEEP["FullThread"]
    span_mid = (drawing.UNDERHEAD_X + drawing.FULL_THREAD_X) / 2.0
    assert ft_x == pytest.approx(span_mid)
    assert ft_y == pytest.approx(ft_line + drawing.FULL_THREAD_TEXT_HEIGHT / 2.0)
    assert drawing.FULL_THREAD_TEXT_HEIGHT == drawing.block_height(1, 1)
    span = drawing.FULL_THREAD_X - drawing.UNDERHEAD_X
    assert (span - drawing.FULL_THREAD_VALUE_WIDTH) / 2.0 >= 0.0005
    ft_left = ft_x - drawing.FULL_THREAD_TEXT_WIDTH / 2.0
    ft_right = ft_x + drawing.FULL_THREAD_TEXT_WIDTH / 2.0
    ft_top = ft_line + drawing.FULL_THREAD_TEXT_HEIGHT
    assert drawing.FULL_THREAD_VALUE_WIDTH < span < drawing.FULL_THREAD_TEXT_WIDTH
    # Clear of the head's slot-depth stack (its right extension line at the
    # slot floor) and inside the border.
    assert ft_left >= drawing.SLOT_FLOOR_X + 0.008
    assert ft_top <= inner[3] - 0.010
    # The shoulder length's lead-foot extension line ends 1 mm past its own
    # line, under the full-thread block, which inks 0.9 mm over its line.
    assert ft_left < drawing.LEAD_FOOT_X < ft_right
    assert (ft_line + 0.0009) - (sl_line + 0.001) >= 0.002
    # The shoulder length's block stands right of the 5.67 station's
    # extension line and of the full-thread block (it shares their height),
    # 3 mm clear of both, so no line strikes its text.
    sl_x, sl_y = drawing.SIDE_KEEP["ShoulderLength"]
    assert sl_y == pytest.approx(sl_line + drawing.SHOULDER_LENGTH_TEXT_HEIGHT / 2.0)
    sl_left = sl_x - drawing.SHOULDER_LENGTH_TEXT_WIDTH / 2.0
    sl_right = sl_x + drawing.SHOULDER_LENGTH_TEXT_WIDTH / 2.0
    assert sl_left >= drawing.FULL_THREAD_X + 0.003
    assert sl_left >= ft_right + 0.003 - 1e-12
    assert sl_line + drawing.SHOULDER_LENGTH_TEXT_HEIGHT <= inner[3] - 0.010
    assert drawing.ISO_CENTER[0] - sl_right > 0.040
    # Its block sits over the thread note's text (#8-32 UNC, 24.3 mm wide
    # from the note's anchor), never on it.
    assert sl_right > drawing.THREAD_NOTE_XY[0]
    assert sl_line - drawing.THREAD_NOTE_XY[1] >= 0.008
    # The crown radius: its leader runs along the radius, so it leaves the
    # arc inside the arc's +/-18.2 degrees, with a degree to spare.
    half_angle = math.degrees(math.asin(geom.HEAD_DIA / 2.0 / geom.CROWN_RADIUS))
    assert half_angle == pytest.approx(18.19, abs=0.01)
    assert 0.0 < drawing.CROWN_RADIUS_LEADER_DEG <= half_angle - 1.0
    scale = drawing._S / 1000.0
    assert drawing.CROWN_CENTER_X - drawing.APEX_X == pytest.approx(
        geom.CROWN_RADIUS * scale
    )
    arc_x, arc_y = drawing.CROWN_RADIUS_ARC_XY
    head_bottom = drawing.SIDE_CENTER[1] - geom.HEAD_DIA / 2.0 * scale
    assert drawing.APEX_X < arc_x < drawing.RIM_X
    assert head_bottom < arc_y < drawing.SIDE_CENTER[1]
    tan = math.tan(math.radians(drawing.CROWN_RADIUS_LEADER_DEG))
    bend_x, bend_y = drawing.CROWN_RADIUS_BEND_X, drawing.CROWN_RADIUS_BEND_Y
    for x, y in ((arc_x, arc_y), (bend_x, bend_y)):
        assert drawing.SIDE_CENTER[1] - y == pytest.approx(
            (drawing.CROWN_CENTER_X - x) * tan
        )
    # Its text stands at the leader's bend, left of the apex extension lines,
    # under the head Ø's lower end, over row 0 and right of the head-end view.
    cr_x, cr_y = drawing.SIDE_KEEP["CrownRadius"]
    cr_right = cr_x + drawing.CROWN_RADIUS_TEXT_WIDTH / 2.0
    cr_left = cr_x - drawing.CROWN_RADIUS_TEXT_WIDTH / 2.0
    assert cr_right == pytest.approx(bend_x - drawing.RADIAL_BEND_GAP)
    assert cr_y == pytest.approx(bend_y + drawing.RADIAL_SHOULDER_DROP)
    assert bend_x <= drawing.APEX_X - 0.010
    assert bend_y + 0.0045 <= head_bottom - 0.002
    assert bend_y - drawing.SIDE_KEEP["HeadHeight"][1] >= 0.025
    head_radius = geom.HEAD_DIA * drawing.SHEET_SCALE[0] / 2000.0
    assert cr_left > drawing.END_CENTER[0] + head_radius
    # The leader never meets the head Ø's dimension line: where it passes the
    # line's x it is already under the line's lower end.
    head_dia_x = drawing.SIDE_KEEP["HeadDia"][0]
    assert bend_x < head_dia_x < arc_x
    leader_y = bend_y + (head_dia_x - bend_x) * tan
    assert leader_y <= head_bottom - 0.004
    # The crown rise's text stands outside, left of the apex extension line
    # it shares with the slot depth.
    crown_x = drawing.SIDE_KEEP["CrownRise"][0]
    assert crown_x + drawing.CROWN_RISE_TEXT_WIDTH / 2.0 <= drawing.APEX_X - 0.002
    assert (
        crown_x - drawing.CROWN_RISE_TEXT_WIDTH / 2.0 > drawing.SIDE_KEEP["HeadDia"][0]
    )
    # Nothing over the shank shares the head's column.
    assert drawing.SIDE_KEEP["SlotDepth"][0] < drawing.UNDERHEAD_X
    # The two apex dimensions stack above the head, 12 mm apart.
    crown_y = drawing.SIDE_KEEP["CrownRise"][1]
    slot_y = drawing.SIDE_KEEP["SlotDepth"][1]
    assert drawing.HEAD_TOP_Y < crown_y < slot_y
    assert slot_y - crown_y >= 0.010
    # The centreline pick lands on the thread's face, past the lead.
    assert drawing.LEAD_TOP_X < drawing.CENTERLINE_PICK[0] < drawing.THREAD_START_X
    assert abs(drawing.CENTERLINE_PICK[1] - drawing.SIDE_CENTER[1]) < thread_half
    # The isometric stands clear of the thread note.
    assert drawing.ISO_CENTER[0] - drawing.THREAD_NOTE_XY[0] > 0.040


def test_every_direct_db_block_restores_inference_in_finally() -> None:
    # Sketch inference is session state on the persistent seat: each block
    # that turns it off must restore it even when a native segment is
    # rejected, so every True is followed at once by a try whose finally
    # restores it, and nothing restores it outside a finally.
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))

    def toggle(node: ast.AST) -> str | None:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "set_sketch_direct_db"
        ):
            return ast.unparse(node.value.args[1])
        return None

    on = restored = 0
    finally_offs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            finally_offs |= {
                id(stmt) for stmt in node.finalbody if toggle(stmt) == "False"
            }
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for index, stmt in enumerate(body):
            if toggle(stmt) == "True":
                on += 1
                following = body[index + 1]
                assert isinstance(following, ast.Try), ast.unparse(stmt)
                assert [toggle(s) for s in following.finalbody] == ["False"]
                restored += 1
    offs = [node for node in ast.walk(tree) if toggle(node) == "False"]
    assert {id(node) for node in offs} == finally_offs
    # The head profile, the shank profile and the station reference.
    assert on == restored == len(offs) == 3


def test_station_reference_is_saved_hidden_and_imported_per_view() -> None:
    build = Path(part.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "StationReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_part_and_images(adapter, PART_NAME)")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "StationReference" in spec.DRAWING_DIMENSIONS


def test_readback_contract_mirrors_every_printed_and_callout_control() -> None:
    printed = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(drawing.PRINTED_DIMENSIONS) == printed
    limits = {name: row for name, row in drawing.PRINTED_DIMENSIONS.items() if row[1]}
    # The builder's limits: the seat Ø's and the shoulder length's LIMIT
    # bands (owner ruling 2026-10-26 (#1951, option B)) and the full-thread
    # station's single MAX (machinist FIX round 1).
    assert limits == {
        "SeatDia": (geom.SEAT_DIA, 3),
        "ShoulderLength": (geom.SHOULDER_LENGTH, 3),
        "FullThread": (5.67, 6),
    }
    assert drawing.PRINTED_DIMENSIONS["CrownRadius"] == (
        pytest.approx(20.03125),
        0,
    )
    assert drawing.CROWN_RADIUS_PRINTED_PREFIX == "(SR"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The crown radius is dressed by its own recipe (keeping the part's SR),
    # never the plain parenthesis helper that would overwrite it.
    assert "_dress_crown_radius(adapter, side_annotations)" in source
    assert 'sorted(REFERENCE_DIMENSIONS - {"CrownRadius"})' in source
    dress = inspect.getsource(drawing._dress_crown_radius)
    for setting in (
        "display.ArrowSide = _ARROWS_OUTSIDE",
        "display.SolidLeader = False",
        "display.ShortenedRadius = False",
    ):
        assert setting in dress
    assert drawing.LIMIT_DEVIATIONS == {
        "SeatDia": (geom.SEAT_DIA_LOWER, geom.SEAT_DIA_UPPER),
        "ShoulderLength": (geom.SHOULDER_LENGTH_LOWER, geom.SHOULDER_LENGTH_UPPER),
    }
    assert drawing.PRINTED_DIMENSIONS["TipChamfer"] == (geom.TIP_CHAMFER, 0)
    assert drawing.PRINTED_DIMENSIONS["OverallLength"][0] == pytest.approx(23.0)
    # Unprinted controls: the lead's axial leg (45 degrees by equation) and
    # the thread major the callout defines.
    assert drawing.SOURCE_ONLY_DIMENSIONS == {
        "StepLead@ShankProfile": (geom.STEP_LEAD, 0),
        "ThreadDia@ShankProfile": (geom.MAJOR_DIA, 0),
    }
    # The part authors every callout on the dimension it marks; the drawing
    # writes none.  The full-thread callout alone stands above its value.
    callouts = spec.DIMENSION_CALLOUTS_BY_NAME
    assert set(callouts) == {"SeatDia", "ShoulderLength", "TipChamfer"}
    assert spec.DIMENSION_CALLOUTS_ABOVE_BY_NAME == {"FullThread": "TO FULL THREAD"}
    assert callouts["TipChamfer"] == spec.CHAMFER_CALLOUT
    for by_feature in (spec.DIMENSION_CALLOUTS, spec.DIMENSION_CALLOUTS_ABOVE):
        for feature, names in by_feature.items():
            assert set(names) <= spec.DRAWING_DIMENSIONS[feature]
    assert part.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert part.DIMENSION_CALLOUTS_ABOVE is spec.DIMENSION_CALLOUTS_ABOVE
    build = Path(part.__file__).read_text(encoding="utf-8")
    assert "((4, DIMENSION_CALLOUTS), (3, DIMENSION_CALLOUTS_ABOVE))" in build
    readback = inspect.getsource(drawing._verify_printed_dimensions)
    assert "(3, DIMENSION_CALLOUTS_ABOVE_BY_NAME)" in readback
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_callouts" not in source


def test_drawing_runs_the_readbacks_after_the_last_rebuild() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_verify_source_dimensions(adapter.currentModel)" in source
    assert "settled_checks=(lambda: _verify_printed_dimensions(" in source

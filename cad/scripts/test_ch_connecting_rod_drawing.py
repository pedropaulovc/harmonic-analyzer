"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _drawing_leaders
import ch_connecting_rod_notes
import ch_connecting_rod_spec
import draw_ch_connecting_rod as drawing
import export_features
import build_ch_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import FaceGeometry
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["ch_connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is ch_connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_connecting_rod_notes.DRAWING_DIMENSIONS.values())
    views = (drawing.FRONT_KEEP, drawing.LEFT_KEEP, drawing.DETAIL_KEEP)
    kept = set().union(*views)
    assert kept == marked
    assert sum(len(view) for view in views) == len(kept)


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.CENTER_DISTANCE, drawing.FORK_TOP_Y) == (
        ch_connecting_rod_spec.CENTER_DISTANCE,
        ch_connecting_rod_spec.FORK_TOP_Y,
    )
    assert drawing._BBOX_CY == pytest.approx(
        (ch_connecting_rod_spec.RING_BOTTOM_Y + ch_connecting_rod_spec.FORK_TOP_Y) / 2.0
    )
    assert ch_connecting_rod_spec.CENTER_DISTANCE == rod.CENTER_DISTANCE
    assert ch_connecting_rod_spec.RING_BORE_DIA == rod.RING_BORE_DIA
    assert ch_connecting_rod_spec.RING_BORE_DIA_BAND == rod.RING_BORE_DIA_BAND
    assert ch_connecting_rod_spec.SHANK_WIDTH == rod.SHANK_WIDTH
    assert ch_connecting_rod_spec.RING_THICKNESS == rod.RING_THICKNESS
    assert ch_connecting_rod_spec.SHANK_THICKNESS == rod.SHANK_THICKNESS
    assert ch_connecting_rod_spec.FORK_WIDTH == rod.FORK_WIDTH
    assert ch_connecting_rod_spec.FORK_THICKNESS == rod.FORK_THICKNESS
    assert ch_connecting_rod_spec.FORK_SLOT_WIDTH == rod.FORK_SLOT_WIDTH
    assert ch_connecting_rod_spec.FORK_BASE_Y == rod.FORK_BASE_Y
    assert ch_connecting_rod_spec.FORK_CROTCH_Y == rod.FORK_CROTCH_Y


def test_rod_length_closes_the_raised_cam_to_the_level_rocker() -> None:
    import math

    import channel_frame_geom as frame
    import _rocker_interface as rocker_interface
    import dt_cylinder_gear_spec as cylinder

    pin = (
        frame.ROCKER_PIVOT_XY[0] - rocker_interface.ROD_HOLE_X,
        frame.ROCKER_PIVOT_XY[1] + rocker_interface.ROD_HOLE_Y - rocker_interface.PIVOT_MID_Y,
    )
    phase = math.radians(frame.CAM_HOME_PHASE_DEG)
    cam = (
        frame.CAM_SHAFT_XY[0] + cylinder.ECCENTRICITY * math.sin(phase),
        frame.CAM_SHAFT_XY[1] + cylinder.ECCENTRICITY * math.cos(phase),
    )
    assert abs(rod.CENTER_DISTANCE - math.dist(pin, cam)) < 1e-9


def test_fork_reference_lengths_run_from_the_crown_top() -> None:
    # The side view prints the slot depth and the boss length from the tine
    # tops: crown radius (= half the fork width, on the pin) plus the spec's
    # below-pin spans.
    spec = ch_connecting_rod_spec
    assert spec.FORK_CROWN_RADIUS == spec.FORK_WIDTH / 2.0
    assert rod.SLOT_DEPTH == pytest.approx(spec.FORK_CROWN_RADIUS + spec.FORK_CROTCH_BELOW_PIN)
    assert rod.FORK_BOSS_LENGTH == pytest.approx(
        spec.FORK_CROWN_RADIUS + spec.FORK_BASE_BELOW_PIN
    )
    assert rod.SLOT_DEPTH == pytest.approx(14.732)  # .58
    assert rod.FORK_BOSS_LENGTH == pytest.approx(18.034)  # .71
    # The slot floor stands above the root step, so the bridge is solid.
    assert spec.FORK_BASE_Y < spec.FORK_CROTCH_Y < spec.CENTER_DISTANCE


def test_analytic_volumes_follow_the_fork_geometry() -> None:
    spec = ch_connecting_rod_spec
    hole = spec.PIN_HOLE_DIA
    crown = math.pi * spec.FORK_CROWN_RADIUS**2 / 2.0
    fork_area = spec.FORK_WIDTH * spec.FORK_BASE_BELOW_PIN + crown
    assert rod.fork_outline_area(spec.FORK_BASE_Y) == pytest.approx(fork_area)
    slot_area = spec.FORK_WIDTH * spec.FORK_CROTCH_BELOW_PIN + crown
    assert rod.slot_volume() == pytest.approx(slot_area * spec.FORK_SLOT_WIDTH)
    # The reamed hole crosses the slot: it cuts only the two tines.
    assert rod.pin_hole_volume() == pytest.approx(
        math.pi * (hole / 2.0) ** 2 * 2.0 * spec.TINE_THICKNESS
    )
    # #3114: the ring disc at its own thickness, and the shank's run from the
    # ring's OD to the fork root at the shank's (checked against the area
    # integrated under the root line and over the OD arc).
    assert rod.ring_volume() == pytest.approx(
        math.pi * spec.RING_OUTER_RADIUS**2 * spec.RING_THICKNESS
    )
    steps = 20000
    half = spec.SHANK_WIDTH / 2.0
    dx = spec.SHANK_WIDTH / steps
    shank_area = sum(
        (spec.FORK_BASE_Y - math.sqrt(spec.RING_OUTER_RADIUS**2 - x**2)) * dx
        for x in (-half + (k + 0.5) * dx for k in range(steps))
    )
    assert rod.shank_volume() == pytest.approx(
        shank_area * spec.SHANK_THICKNESS, rel=1e-8
    )
    assert rod.boss_volume() == pytest.approx(
        rod.ring_volume()
        + rod.shank_volume()
        + rod.fork_outline_area(spec.FORK_BASE_Y) * spec.FORK_THICKNESS
    )
    assert rod.strap_bore_volume() == pytest.approx(
        math.pi * (spec.RING_BORE_DIA / 2.0) ** 2 * spec.RING_THICKNESS
    )
    # The shank's foot is buried in the ring's wall: outside the bore, inside
    # the disc, and both shank faces lie inside the ring's, so the foot adds
    # no volume and leaves no edge on a ring face.
    assert spec.RING_BORE_DIA / 2.0 < rod.SHANK_FOOT_Y
    assert math.hypot(half, rod.SHANK_FOOT_Y) < spec.RING_OUTER_RADIUS
    assert min(rod.RING_STEPS) > 0.0
    assert rod.finished_volume() == pytest.approx(
        rod.boss_volume()
        - rod.slot_volume()
        + rod.inside_corner_volume()
        + rod.shank_corner_volume()
        + rod.step_corner_volume()
        - rod.strap_bore_volume()
        - rod.pin_hole_volume()
    )
    assert 0.0 < rod.finished_volume() < rod.boss_volume()


def test_inside_corner_volume_is_the_fillets_closed_form() -> None:
    spec = ch_connecting_rod_spec
    r = spec.INSIDE_CORNER_R
    square = r**2 * (1.0 - math.pi / 4.0)
    assert rod._fillet_area(r, math.pi / 2.0) == pytest.approx(square)
    # A straight wall adds nothing.
    assert rod._fillet_area(r, math.pi) == pytest.approx(0.0, abs=1e-12)
    # The slot floor's two corners across the fork, the two ledges where the
    # shank's faces meet the root step across the shank.
    edges = 2.0 * spec.FORK_WIDTH + 2.0 * spec.SHANK_WIDTH
    assert rod.inside_corner_volume() == pytest.approx(square * edges)
    # #3114: the flank fillets run through the shank's thickness, not the
    # ring's. The two corners where a shank face meets the ring's OD stay
    # sharp: the ring stands .015 over the shank's near face, less than the
    # radius, and .025 over its far face, which the printed bands take down
    # to .001.
    near_step, far_step = rod.RING_STEPS
    assert near_step == pytest.approx(spec.SHANK_FACE_NEAR - spec.RING_FACE_NEAR)
    assert near_step == pytest.approx(0.381)  # .015
    assert far_step == pytest.approx(
        spec.RING_FACE_NEAR
        + spec.RING_THICKNESS
        - spec.SHANK_FACE_NEAR
        - spec.SHANK_THICKNESS
    )
    assert far_step == pytest.approx(0.635)  # .025
    assert near_step < r
    assert spec.SHANK_INSIDE_RING_MIN[1] == pytest.approx(0.0254)
    assert spec.SHANK_INSIDE_RING_MIN[1] < r
    # The shank's two faces in the build's Right-plane sketch, the datum face
    # at +FORK_THICKNESS / 2.
    assert rod.SHANK_NEAR_X == pytest.approx(1.778)
    assert rod.SHANK_FAR_X == pytest.approx(-1.524)
    assert rod.SHANK_NEAR_X - rod.SHANK_FAR_X == pytest.approx(spec.SHANK_THICKNESS)


def _strip_area(lower, upper, x0: float, x1: float, steps: int = 20000) -> float:
    """Area between ``lower(x)`` and ``upper(x)`` for x in [x0, x1]."""
    dx = (x1 - x0) / steps
    return sum(
        (upper(x) - lower(x)) * dx for x in (x0 + (k + 0.5) * dx for k in range(steps))
    )


def test_q9_corner_volumes_are_the_cutters_sections() -> None:
    """Owner ruling 2026-11-23, tool audit Q9: the shank's two corners on the
    ring are R.065 fillets between the flank and the ring's OD, and its two
    corners on the fork's step the 1/8 in cutter's arc run from the flank
    onto the step's outer corner; each through the shank's thickness.
    Checked against the areas integrated between the edges and the arcs."""
    spec = ch_connecting_rod_spec
    r = ch_connecting_rod_notes.SHANK_CORNER_R
    half, big = spec.SHANK_WIDTH / 2.0, spec.RING_OUTER_RADIUS
    cx = half + r
    # Ring corner: over the OD, under the fillet's arc, out from the flank
    # to the fillet's tangent point on the ring.
    cy = math.sqrt((big + r) ** 2 - cx**2)
    ring = _strip_area(
        lambda x: math.sqrt(big**2 - x**2),
        lambda x: cy - math.sqrt(max(r**2 - (x - cx) ** 2, 0.0)),
        half,
        cx * big / (big + r),
    )
    assert rod.shank_corner_volume() == pytest.approx(
        2.0 * ring * spec.SHANK_THICKNESS, rel=1e-4
    )
    # Step corner: under the step, over the cutter's arc, from the flank out
    # to the step's outer corner.
    step, base = rod.FORK_STEP, spec.FORK_BASE_Y
    low = base - math.sqrt(r**2 - (r - step) ** 2)
    corner = _strip_area(
        lambda x: low + math.sqrt(max(r**2 - (x - cx) ** 2, 0.0)),
        lambda x: base,
        half,
        half + step,
    )
    assert rod.step_corner_volume() == pytest.approx(
        2.0 * corner * spec.SHANK_THICKNESS, rel=1e-4
    )


def test_q9_shank_corners_print_one_local_limit_with_its_reason() -> None:
    """Owner ruling 2026-11-23, tool audit Q9: "Print a local corner limit
    R.065 (.060-.070), cut with the 1/8 end mill; no 5/64 cutter". One
    native radius prints 4X R.065 at three places (the title block's .XXX
    is .060-.070) with its reason beneath it; one global drives the ring
    corners' fillet and the step corners' arcs, so it is all four's."""
    notes = ch_connecting_rod_notes
    assert notes.SHANK_CORNER_R == pytest.approx(_in(0.065))
    assert notes.DRAWING_DIMENSIONS["ShankCorners"] == {"ShankCornerR"}
    assert notes.DRAWING_PRECISION["ShankCorners"] == {"ShankCornerR": 3}
    assert notes.DIMENSION_PREFIXES == {("ShankCorners", "ShankCornerR"): "4X R"}
    assert drawing.FRONT_CALLOUTS["ShankCornerR"] == "NOTHING SEATS IN\nTHESE CORNERS"
    assert "ShankCornerR" in drawing.FRONT_KEEP
    assert rod.SHANK_CORNER_R_LIMITS == pytest.approx((_in(0.060), _in(0.070)))
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "(shank_corner_dim[0], '\"CornerR\"')" in source
    assert "step_sd.record(f\"StepCornerR{suffix}\", '\"CornerR\"')" in source
    assert 'name_last_feature(adapter, "StepCorners")' in source


def test_q9_corners_hold_every_margin_at_their_greatest_radius() -> None:
    """Owner ruling 2026-11-23, tool audit Q9, judged at the printed R.070.
    The corners add metal, so no wall thins: the shank's least section stays
    its width by its thickness, and the fork, its tines, the bridge and the
    pin hole's walls stand above the root step, where no corner reaches.
    Every corner lies inside the shank's two faces, so the cam slot's tooth
    discs (on the ring's faces) and the neighbouring rods (off the fork's
    faces) meet nothing new. The step corners stand at or below the root
    step and inside the fork's sides, under the arm by its least clearance
    over the slot floor plus the bridge."""
    import sh_vn_pivot_pin_rod_spec as pin
    from _milled_corner_limit import runout_rise
    from _printed_tolerance import inside_corner_radius_mm

    spec = ch_connecting_rod_spec
    least, greatest = rod.SHANK_CORNER_R_LIMITS
    assert inside_corner_radius_mm(unit=spec.UNIT) < least
    # The step (.035) is narrower than the least radius: the cutter's arc
    # runs onto its outer corner at every radius the print allows, leaving
    # the flank .0606 below the step at R.070.
    assert rod.FORK_STEP == pytest.approx(_in(0.035))
    assert rod.FORK_STEP < least
    assert rod.FORK_STEP + spec.SHANK_WIDTH / 2.0 == pytest.approx(spec.FORK_WIDTH / 2.0)
    rise = runout_rise(greatest, rod.FORK_STEP)
    assert rise == pytest.approx(_in(0.0606), abs=_in(0.0001))
    # The ring corner's metal on its bisector (the OD taken as its tangent):
    # .0204 at R.070, .0090 more than the 5/64 in end mill's R.039 left.
    half, big = spec.SHANK_WIDTH / 2.0, spec.RING_OUTER_RADIUS
    opening = math.pi / 2.0 + math.asin(half / big)
    assert math.degrees(opening) == pytest.approx(101.5, abs=0.05)

    def bisector(radius: float) -> float:
        return radius * (1.0 / math.sin(opening / 2.0) - 1.0)

    assert bisector(greatest) == pytest.approx(_in(0.0204), abs=_in(0.0001))
    assert bisector(greatest) - bisector(_in(0.039)) == pytest.approx(
        _in(0.0090), abs=_in(0.0001)
    )
    # The two corners on a flank stay apart along it.
    ring_tangent_y = math.sqrt((big + greatest) ** 2 - (half + greatest) ** 2)
    assert ring_tangent_y < spec.FORK_BASE_Y - rise
    # Inside the shank's faces: the corner features run the shank's
    # thickness on its own mid-plane, at least SHANK_INSIDE_RING_MIN (.001)
    # inside each ring face.
    assert rod.SHANK_MID_Z == pytest.approx(-(rod.SHANK_NEAR_X + rod.SHANK_FAR_X) / 2.0)
    assert min(spec.SHANK_INSIDE_RING_MIN) == pytest.approx(_in(0.001))
    # The arm: over the slot floor by its least clearance, the floor over the
    # root step by the least bridge: 4.800 mm over the step corners (the pin
    # hole off by half its Ø.014 position zone).
    arm_gap = pin.BUDGET["crotch_clearance_min"] + pin.BUDGET["bridge_min"]
    assert arm_gap == pytest.approx(4.800, abs=1e-3)
    assert arm_gap > pin.CROTCH_CLEARANCE_MIN


def test_pin_hole_is_the_reamed_press_hole_for_the_rod_pivot_pin() -> None:
    """User ruling 2026-10-09 (PR #1292 review F1): the RodPin member of
    MHA-SH-VN-58 is pressed into both tines as the bar pin is into the
    amplitude bar (sh_vn_pivot_pin_rod_spec holds the fit), so the hole is
    reamed, not a #47 drill. Owner ruling 2026-11-24, fit audit question 3:
    it prints the .0775 reamer's size with no band, the pin itself the
    gauge."""
    import _config

    spec = ch_connecting_rod_spec
    assert rod.PIN_HOLE_DIA is spec.PIN_HOLE_DIA
    assert drawing._PIN_HOLE_DIA is spec.PIN_HOLE_DIA
    # The .0775-.0779 band is the ANALYSIS band, what the reamer is modelled
    # to cut; the model and the print are the reamer's size.
    assert tuple(limit / 25.4 for limit in spec.PIN_HOLE_LIMITS) == pytest.approx(
        (0.0775, 0.0779), abs=1e-12
    )
    assert spec.PIN_HOLE_DIA == pytest.approx(0.0775 * 25.4)
    assert "RV-04" not in {
        row["id"] for row in _config.parts("ch-connecting-rod")["machinist_exceptions"]
    }
    assert not hasattr(spec, "PIN_HOLE_SPEC")
    assert not _set_limits_calls()
    assert ch_connecting_rod_notes.PIN_NUMBER == _config.parts("sh-vn-pivot-pin")["number"]
    assert ch_connecting_rod_notes.ARM_NUMBER == _config.parts("ch-rocker-arm")["number"]
    assert drawing.CAM_NUMBER == _config.parts("dt-cylinder-gear")["number"]


def test_the_pin_bears_on_the_whole_tine() -> None:
    """PR #1292 review F1 regression: a 90-degree Ø3.2 countersink sunk into
    each tine for a peened end left 0.92 of land under the pin, under rule
    12's 1.5 floor, while the budget only checked the tine. Built
    independently of the joint budget: the build removes nothing at the pin
    but one straight cylinder through both tines (no chamfer, no second cut
    sunk into a tine face), so the pin's land in each tine is the thinnest
    tine the tine's own band leaves (#982)."""
    spec = ch_connecting_rod_spec
    assert not [name for name in dir(rod) if "countersink" in name.lower()]
    assert not [name for name in dir(spec) if "CSK" in name]
    thinnest_tine = spec.TINE_THICKNESS + spec.TINE_BAND[1]
    assert thinnest_tine == pytest.approx(1.651)  # .065
    assert thinnest_tine == spec.TINE_MIN
    assert spec.FORK_THICKNESS == pytest.approx(
        2.0 * spec.TINE_THICKNESS + spec.FORK_SLOT_WIDTH
    )
    assert thinnest_tine >= WALL_FLOOR_MM  # drawing-guidelines.md rule 17 floor
    # Positive control: the countersink this replaced fails the same check.
    old_csk_depth = (3.2 + 0.127 - 1.994) / 2.0  # 90-degree: depth = radial step
    assert thinnest_tine - old_csk_depth < WALL_FLOOR_MM


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    # The left view stands level with the front (third-angle alignment) and
    # carries the fork detail's circle and the ring's two bands.
    assert drawing.LEFT_CENTER == (0.080, drawing.FRONT_CENTER[1])
    assert ch_connecting_rod_notes.DRAWING_NOTES.splitlines() == [
        "1. PRESS FIT ON ROD PIVOT PIN MHA-SH-VN-58:",
        "    THE PIN DOES NOT ENTER BY HAND.",
        "2. FORK SLOT: RUNNING FIT ON ARM MHA-CH-06.",
        "3. RING: SLIDING FIT IN MHA-DT-12 CAM SLOT; LOCATES ROD.",
    ]
    assert ch_connecting_rod_notes.CAM_NUMBER == drawing.CAM_NUMBER
    assert max(y for _, y in drawing.DETAIL_KEEP.values()) < 0.260
    assert ch_connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"


def test_the_tine_wall_shortfall_sits_between_the_floor_and_the_target() -> None:
    """The tines are pitch-bound: their printed lower limit is the known
    shortfall under the .080 target (MHA-CH-03 RV-02), above the .060 floor."""
    spec = ch_connecting_rod_spec
    assert WALL_FLOOR_MM <= spec.TINE_MIN < WALL_TARGET_MM


def test_every_tight_band_names_its_mate() -> None:
    """drawing-guidelines.md rule 7: the bore's, the reamed hole's, the
    slot's, the tine's and the ring faces' bands each name the part they fit,
    on their own callout, with the clearance or interference they hold."""
    spec = ch_connecting_rod_spec
    least, most = spec.STRAP_DIAMETRAL_CLEARANCE
    # The running bore's clearance on the cam stays in the 0.20-0.35 intent.
    assert 0.20 - 1e-9 <= least < most <= 0.35 + 1e-9
    bore = drawing.FRONT_CALLOUTS["StrapBoreDia"]
    assert bore.startswith("BORE")
    assert drawing.CAM_NUMBER in bore
    # Fan-out screen 2026-11-07: size, then process (rule 26), and the band
    # narrower than the reamer row links its matched press fit (note 1;
    # owner decision 2026-11-19, #3124 item 5).
    assert drawing.FRONT_CALLOUTS["PinHoleDia"] == (
        "REAM THRU\nSEE NOTE 1"
    )
    # Fan-out rounds 1-2 (rule 4): two tight bands serving one mate link one
    # note naming it, so the mate prints once and each band reaches it: the
    # slot and the tine walls that locate it (note 2, the arm), the ring's
    # thickness and its offset from the fork's datum face (note 3, the cam's
    # slot; #3114: the ring is the sliding fit, the shank fits nothing).
    assert drawing.DETAIL_CALLOUTS == {
        "TineNear": "2X TINE WALL\nSEE NOTE 2",
        "SlotWidth": "SEE NOTE 2",
    }
    assert drawing.LEFT_CALLOUTS == {
        "RingFaceNear": "SEE NOTE 3",
        "RingThick": "SEE NOTE 3",
    }
    callouts = {
        *drawing.FRONT_CALLOUTS,
        *drawing.LEFT_CALLOUTS,
        *drawing.DETAIL_CALLOUTS,
    }
    assert not callouts & {"ShankThick", "ShankFaceNear"}
    assert set(drawing.DETAIL_CALLOUTS) <= set(drawing.DETAIL_KEEP)
    assert set(drawing.LEFT_CALLOUTS) <= set(drawing.LEFT_KEEP)
    assert set(drawing.FRONT_CALLOUTS) <= set(drawing.FRONT_KEEP)
    for text in (
        *drawing.FRONT_CALLOUTS.values(),
        *drawing.LEFT_CALLOUTS.values(),
        *drawing.DETAIL_CALLOUTS.values(),
    ):
        assert max(len(line) for line in text.splitlines()) <= 26, text


def test_native_gdt_and_finish_present() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # A = strap bore axis, B = shank left flank (clocking); the pin-hole
    # position frame references both and the bore imports its model-owned fit.
    assert source.count("add_datum_feature(") == 2
    assert 'label="strap bore axis",' in source
    assert source.count("add_feature_control_frame(") == 1
    assert 'datums=("A", "B")' in source
    assert 'characteristic="position"' in source
    assert 'FRONT_CALLOUTS = {\n    "StrapBoreDia": (' in source
    assert "+0.10/0" not in source
    assert "add_surface_finish(" in source
    # The reamed hole prints its native Ø and band with descriptive text, not
    # a Hole Wizard callout; the position FCF anchors the hole's 3-o'clock rim.
    assert "add_native_hole_callout(" not in source
    assert source.count("edge_xy=pin_fcf_rim") == 1
    assert "SetText(4" not in source
    assert not hasattr(ch_connecting_rod_notes, "PIN_CSK_CALLOUT")


def test_datum_b_leader_clears_the_shank_width_text() -> None:
    """Datum B's leader runs level at the tag's height (the edge attachment
    re-solves square to the vertical flank). Farm audit at 71a6e3107: with the
    tag 10 mm under the pick, the fork-raised bbox centre put that leader at
    y 151.1 mm, 0.37 mm through the 8.00 text [148.2..151.7]."""
    keep_y = drawing.FRONT_KEEP["ShankWidthDim"][1]
    text_top = keep_y + 0.0017  # measured: 3.5 mm text on the y-0.150 keep
    leader_y = drawing.DATUM_B_SYMBOL[1]
    assert leader_y - text_top >= 0.0025
    # The leader meets the shank's left flank, between the ring and the fork.
    flank_x, _ = drawing._sheet_xy(-ch_connecting_rod_spec.SHANK_WIDTH / 2.0, 0.0)
    assert drawing.DATUM_B_EDGE[0] == pytest.approx(flank_x)
    ring_top = drawing._sheet_xy(0.0, ch_connecting_rod_spec.RING_OUTER_RADIUS)[1]
    fork_root = drawing._sheet_xy(0.0, ch_connecting_rod_spec.FORK_BASE_Y)[1]
    assert ring_top < leader_y < fork_root


def test_ring_and_shank_locate_from_the_fork_face_and_print_their_thickness() -> None:
    """#982: a face off the fork's plane prints as a native ordinate from the
    fork's datum face (its near face, where the near tine is measured) and
    its thickness as a size, one locator and one size. #3114 (owner ruling
    2026-11-18): the ring is the original's .170, centred on the fork, and
    the shank .13 with its near face .05 from the datum face, so each prints
    its own pair: the ring's at the ring with its +/-.002 bands, the shank's
    under the fork at the title block's .XX (machinist review: a third place
    there was over-specified)."""
    import _config

    spec = ch_connecting_rod_spec
    assert spec.RING_THICKNESS == pytest.approx(4.318)  # .170
    assert spec.SHANK_THICKNESS == pytest.approx(3.302)  # .13
    assert spec.RING_FACE_NEAR == pytest.approx(
        (spec.FORK_THICKNESS - spec.RING_THICKNESS) / 2.0
    )
    assert spec.RING_FACE_NEAR == pytest.approx(0.889)  # .035
    assert spec.SHANK_FACE_NEAR == pytest.approx(1.27)  # .05
    assert not hasattr(spec, "RING_FACE_FAR")
    # Three-place inch ordinates and sizes for the ring and tine, two-place
    # for the shank, as they print.
    precision = ch_connecting_rod_notes.DRAWING_PRECISION
    for value, places in (
        (spec.RING_FACE_NEAR, precision["RingFaceReference"]["RingFaceNear"]),
        (spec.RING_THICKNESS, precision["Ring"]["RingThick"]),
        (spec.TINE_THICKNESS, precision["ForkSlotProfile"]["TineNear"]),
        (spec.SHANK_FACE_NEAR, precision["ForkSlotProfile"]["ShankFaceNear"]),
        (spec.SHANK_THICKNESS, precision["ShankProfile"]["ShankThick"]),
    ):
        assert round(value / 25.4, places) == pytest.approx(value / 25.4, abs=1e-12)
    assert precision["ForkSlotProfile"]["ShankFaceNear"] == 2
    assert precision["ShankProfile"]["ShankThick"] == 2
    # The ring's two bands are model bands; the shank's two are the title
    # block's .XX and carry no model band.
    assert spec.RING_FACE_BAND == spec.RING_THICKNESS_BAND == (0.0508, -0.0508)
    two_place = _config.title_block("linear_2pl", unit=spec.UNIT)["band_in"] * 25.4
    for band in (spec.SHANK_FACE_BAND, spec.SHANK_THICKNESS_BAND):
        assert band == pytest.approx((two_place, -two_place))
    toleranced = model_toleranced_dimensions(rod)
    assert ("ShankProfile", "ShankThick") not in toleranced
    assert ("ForkSlotProfile", "ShankFaceNear") not in toleranced
    # At those bands neither shank face stands proud of its ring face, and
    # the thinnest shank holds the wall target.
    assert spec.SHANK_INSIDE_RING_MIN == pytest.approx((0.0762, 0.0254))
    assert spec.SHANK_THICKNESS + spec.SHANK_THICKNESS_BAND[1] >= WALL_TARGET_MM
    assert set(drawing.LEFT_KEEP) == {"RingFaceNear", "RingThick"}
    assert {"ShankFaceNear", "ShankThick"} <= set(drawing.DETAIL_KEEP)
    # Both ring bands stand below the ring, the offset nearer it, their texts
    # out to the left of the datum face's witness (which drops from the
    # fork's root down the shank).
    ring_bottom = drawing._left_xy(0.0, spec.RING_BOTTOM_Y)
    datum_x = drawing._left_xy(-spec.FORK_THICKNESS / 2.0, 0.0)[0]
    face_x, face_y = drawing.LEFT_KEEP["RingFaceNear"]
    thick_x, thick_y = drawing.LEFT_KEEP["RingThick"]
    assert thick_y < face_y < ring_bottom[1]
    # Centred on its keep at ~2.5 mm a character, a ten-character value and
    # its flag are 25 mm wide: the offset's block ends short of the datum
    # witness, the thickness's short of the offset's, and (r2: long lines ran
    # into the sheet border) 5 mm inside the border (x 0.013).
    half_block = 10 * 0.0025 / 2.0
    for text in drawing.LEFT_CALLOUTS.values():
        assert max(len(line) for line in text.splitlines()) <= 10
    assert face_x + half_block < datum_x - 0.002
    assert thick_x + half_block < face_x - half_block
    assert thick_x - half_block > 0.013 + 0.005
    # A value and its one flag line hang ~6.5 mm below the keep: the
    # thickness's dimension line passes under the offset's flag, and its own
    # flag stays above the border (y 0.013).
    assert face_y - thick_y >= 0.0065 + 0.003
    assert thick_y - 0.0065 > 0.013 + 0.005


def test_inside_corners_are_one_modelled_radius_under_the_title_block() -> None:
    """#982 review r1 (drawing-guidelines.md rule 16): the slot floor and the
    fork's root step had sharp inside corners. One fillet carries the slot
    floor's and the root step's ledges. The ENFORCE review found the
    printed all-corners R0.5 MAX a needless tightening of the title block's
    INSIDE CORNERS R.040 MAX, so the title block governs; that ceiling still
    stands under the arm's least clearance over the slot floor. The shank's
    four corners print their own R.065 (owner ruling 2026-11-23, tool audit
    Q9)."""
    import sh_vn_pivot_pin_rod_spec as pin
    from _printed_tolerance import inside_corner_radius_mm

    spec = ch_connecting_rod_spec
    ceiling = inside_corner_radius_mm(unit=spec.UNIT)
    assert spec.INSIDE_CORNER_R <= ceiling
    assert ceiling < pin.BUDGET["crotch_clearance_min"]
    assert 2.0 * ceiling < spec.FORK_SLOT_WIDTH + spec.FORK_SLOT_BAND[1]
    assert "InsideCorners" not in ch_connecting_rod_notes.DRAWING_DIMENSIONS
    assert "InsideCornerR" not in drawing.FRONT_KEEP
    assert "InsideCornerR" not in drawing.FRONT_CALLOUTS


def test_overall_length_is_a_side_view_reference() -> None:
    """#982 review r1: no overall length. The side view's ring-bottom and
    tine-top silhouettes give it as a plain distance, printed reference.
    Farm r2: a coordinate hit-test on the 2 mm ring bottom missed, so each
    end is named by its face and a projected model point."""
    spec = ch_connecting_rod_spec
    d = drawing
    assert d.OVERALL_LENGTH == pytest.approx(183.766, abs=1e-3)
    assert d.OVERALL_BOTTOM_MM == (0.0, -spec.RING_OUTER_RADIUS, 0.0)
    assert spec.RING_BOTTOM_Y == -spec.RING_OUTER_RADIUS
    # The top pick lands on the far tine's crown, between the slot and the
    # outer face; the crown is the fork's full round.
    x, y, z = d.OVERALL_TOP_MM
    assert (x, y) == (0.0, spec.FORK_TOP_Y)
    assert spec.FORK_SLOT_WIDTH / 2.0 < z < spec.FORK_THICKNESS / 2.0
    assert spec.FORK_TOP_Y == pytest.approx(spec.CENTER_DISTANCE + spec.FORK_WIDTH / 2.0)
    ring, crown = d.OVERALL_FACES.values()
    assert ring.diameter_mm == 2.0 * spec.RING_OUTER_RADIUS
    assert (crown.diameter_mm, crown.contains_z_mm) == (spec.FORK_WIDTH, z)
    # Right of the side view, left of the centre distance's text.
    tine_outer = d._left_xy(spec.FORK_THICKNESS / 2.0, 0.0)[0]
    assert tine_outer + 0.010 < d.OVERALL_TEXT_XY[0] < 0.125 - 0.015


def test_datum_a_tag_stands_clear_of_the_centre_distance_witness() -> None:
    """#982 review r1: at 9 o'clock datum A's leader lay on the 158.37's
    witness line; inside the bore (r2) its tag crowded both diameters'
    leaders. At 5 o'clock the tag stands below the ring on the pick's ray,
    clear of the outer diameter's leader (-55 deg) and the vertical centre
    line, above the border and left of the title block."""
    spec = ch_connecting_rod_spec
    centre = drawing._sheet_xy(0.0, 0.0)
    edge_x, edge_y = drawing.DATUM_A_EDGE
    assert math.dist((edge_x, edge_y), centre) == pytest.approx(spec.RING_BORE_DIA / 2000.0)
    symbol_x, symbol_y = drawing.DATUM_A_SYMBOL
    ray = math.degrees(math.atan2(symbol_y - centre[1], symbol_x - centre[0]))
    edge = math.degrees(math.atan2(edge_y - centre[1], edge_x - centre[0]))
    assert ray == pytest.approx(edge)
    assert -90.0 + 10.0 < ray < -55.0 - 10.0
    half_box = 0.0035
    assert symbol_y + half_box < drawing._sheet_xy(0.0, spec.RING_BOTTOM_Y)[1]
    assert symbol_y - half_box > 0.015
    assert symbol_x + half_box < 0.216


def test_pin_offset_basic_runs_on_the_shank_below_the_ream_callout() -> None:
    """#982 review r3: inside the head the 4.00 BASIC crowded the hole and
    the ream callout's leader crossed it; just below the fork root the
    leader still crossed its right-hand arrow (ENFORCE review). Below the
    callout's lowest line the leader, rising from that line to the hole,
    cannot reach it; its line meets the flank (datum B) above B's tag."""
    spec = ch_connecting_rod_spec
    text_x, text_y = drawing.PIN_OFFSET_TEXT_XY
    root_y = drawing._sheet_xy(0.0, spec.FORK_BASE_Y)[1]
    callout_x, callout_y = drawing.FRONT_KEEP["PinHoleDia"]
    # The callout's three lines under its two-row value hang ~14 mm below
    # its keep point (farm render).
    assert text_y < callout_y - 0.020 < root_y
    assert text_y > drawing.DATUM_B_SYMBOL[1] + 0.015
    pin_x, _pin_y = drawing._sheet_xy(0.0, spec.CENTER_DISTANCE)
    assert callout_x > pin_x
    assert text_x < drawing.DATUM_B_EDGE[0] - 0.015


def test_basic_centre_distance_prints_inside_the_pin_position_zone() -> None:
    places = drawing.CENTRE_DISTANCE_PLACES
    closure_in = ch_connecting_rod_spec.CENTER_DISTANCE / 25.4
    printed = round(closure_in, places)
    assert printed == 6.235
    zone_radius_in = (
        float(ch_connecting_rod_spec.GEOMETRIC_TOLERANCES_IN["rocker pin hole position"])
        / 2.0
    )
    assert abs(printed - closure_in) < zone_radius_in / 10.0


def test_datum_b_is_basic_from_datum_a() -> None:
    """ENFORCE review: nothing placed datum B (the shank's left flank)
    sideways from datum A (the bore axis), so the frame was incomplete. A
    4.00 BASIC from A's bore to B's flank, on the shank above the ring and
    clear over the Ø40.80 text, completes it."""
    spec = ch_connecting_rod_spec
    text_x, text_y = drawing.DATUM_B_FROM_A_TEXT_XY
    ring_top = drawing._sheet_xy(0.0, spec.RING_OUTER_RADIUS)[1]
    assert ring_top < text_y < drawing.DATUM_B_SYMBOL[1] - 0.015
    assert text_y > drawing.FRONT_KEEP["RingOuterDia"][1] + 0.012
    assert text_x < drawing.DATUM_B_EDGE[0] - 0.015


def test_ring_diameters_keep_one_arrow_on_the_near_rim() -> None:
    """#982 review r2: both diameters ran rim to rim through the bore's
    centre and crossed there."""
    assert drawing.set_near_side_diameter is _drawing_leaders.set_near_side_diameter
    assert drawing.NEAR_SIDE_DIAMETERS == ("RingOuterDia", "StrapBoreDia")
    assert set(drawing.NEAR_SIDE_DIAMETERS) <= set(drawing.FRONT_KEEP)


def test_fork_print_is_three_place_and_model_owned() -> None:
    marked = ch_connecting_rod_notes.DRAWING_DIMENSIONS
    assert marked["ForkBoss"] == {"ForkThick"}
    assert marked["ForkSlotProfile"] == {
        "TineNear",
        "SlotWidth",
        "ShankFaceNear",
        "SlotDepth",
        "ForkBossLength",
    }
    assert marked["RingFaceReference"] == {"RingFaceNear"}
    # #3114: ring and shank are two bosses, each owning its size.
    assert marked["RingProfile"] == {"RingOuterDia"}
    assert marked["Ring"] == {"RingThick"}
    assert marked["ShankProfile"] == {"ShankThick"}
    assert marked["Shank"] == {"ShankWidthDim"}
    assert marked["ForkProfile"] == {"ForkWidthDim"}
    assert rod.DRAWING_PRECISION is ch_connecting_rod_notes.DRAWING_PRECISION
    # Every marked dimension has part-authored places, and the build names
    # every marked feature and dimension.
    precision = ch_connecting_rod_notes.DRAWING_PRECISION
    assert {feature: set(names) for feature, names in precision.items()} == marked
    for name, places in (
        ("RingThick", 3),
        ("RingFaceNear", 3),
        ("ShankThick", 2),
        ("ShankFaceNear", 2),
    ):
        assert drawing._kept_precision({name: (0.0, 0.0)}) == {name: places}
    source = Path(rod.__file__).read_text(encoding="utf-8")
    for feature, names in marked.items():
        assert f'name_last_feature(adapter, "{feature}")' in source
        for name in names:
            assert f'"{name}"' in source


def test_each_view_imports_only_the_features_it_dimensions() -> None:
    """Codjiflo review P3 (#3114): a targeted import brings a whole feature's
    marked dimensions. With the ring's near face in the fork's slot sketch,
    the side view imported the fork's five other ordinates, deleted them and
    left the detail to import them again. Every feature's marked dimensions
    now print in one view: the ring's near face is a reference sketch of its
    own, which the part saves hidden (#880) and the side view shows."""
    marked = ch_connecting_rod_notes.DRAWING_DIMENSIONS
    views = {
        "front": set(drawing.FRONT_KEEP),
        "side": set(drawing.LEFT_KEEP),
        "detail": set(drawing.DETAIL_KEEP),
    }
    for feature, names in marked.items():
        owners = [label for label, keep in views.items() if names & keep]
        assert len(owners) == 1, (feature, owners)
        assert names <= views[owners[0]], feature
    assert marked["RingFaceReference"] <= views["side"]
    assert marked["ForkSlotProfile"] <= views["detail"]
    # The side view shows the hidden sketch through the hidden-sketch import.
    assert drawing.curate_view_dimensions.__module__ == "_drawing_hidden_sketches"
    source = Path(rod.__file__).read_text(encoding="utf-8")
    named = source.index('name_last_feature(adapter, "RingFaceReference")')
    blanked = source.index('blank_reference_sketches(adapter, ("RingFaceReference",))')
    assert named < blanked < source.index("save_part_and_images(adapter")
    # The datum line stays on the fork's datum face.
    spec = ch_connecting_rod_spec
    assert 0.0 < rod.DATUM_FACE_REF_RUN < spec.FORK_TOP_Y - spec.FORK_BASE_Y


def _set_limits_calls() -> list[ast.Call]:
    """The build's ``set_limits`` calls: none since the pin hole prints the
    reamer's size with no band."""
    tree = ast.parse(Path(rod.__file__).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "set_limits"
    ]


def test_reamed_pin_hole_is_a_native_four_place_dimension() -> None:
    """PR #1292 review N1 (drawing-simplicity-policy.md `How the repository implements the guidelines` and drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the press hole's
    size is the PinHoleDia model dimension's -- marked, printed at four places
    as the .0775 reamer's size with no band (owner ruling 2026-11-24, fit
    audit question 3) -- imported into the front view with the process
    beneath it, never general-note text."""
    spec = ch_connecting_rod_spec
    assert ch_connecting_rod_notes.DRAWING_DIMENSIONS["PinHoleProfile"] == {
        "PinHoleDia"
    }
    # The reamer's size is exact at four inch places.
    assert round(spec.PIN_HOLE_DIA / 25.4, 4) == pytest.approx(
        spec.PIN_HOLE_DIA / 25.4, abs=1e-12
    )
    assert ch_connecting_rod_notes.DRAWING_PRECISION["PinHoleProfile"] == {"PinHoleDia": 4}
    assert not _set_limits_calls()
    assert ("PinHoleProfile", "PinHoleDia") not in model_toleranced_dimensions(rod)
    assert "PinHoleDia" in drawing.FRONT_KEEP
    assert drawing.FRONT_CALLOUTS["PinHoleDia"].startswith("REAM THRU\n")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "set_dimension_callouts(adapter, front_annotations, FRONT_CALLOUTS)" in source
    )
    assert (
        "assert_imported_precision(\n"
        "        adapter,\n"
        "        front_annotations,\n"
        '        DRAWING_PRECISION["PinHoleProfile"],\n'
        "    )" in source
    )
    # The Ø text stands right of the fork, below the FCF's level leader (so
    # the two leaders cannot cross) and clear of the detail's tine text.
    hole_x, hole_y = drawing._sheet_xy(0.0, spec.CENTER_DISTANCE)
    text_x, text_y = drawing.FRONT_KEEP["PinHoleDia"]
    assert text_x > hole_x + 0.030 and text_y < hole_y - 0.020
    assert text_x < drawing.DETAIL_KEEP["TineNear"][0] - 0.040


def test_fork_detail_takes_in_the_crown_and_the_shank_faces() -> None:
    """#982: the side view's fork dimensions crowded a 6 mm fork at 1:1, so a
    native 3:1 detail carries them. Its fence takes in the crown top and the
    shank-face reference below the root step, and stands clear of the front
    view, the title block and the isometric."""
    d = drawing
    spec = ch_connecting_rod_spec
    assert d.DETAIL_SCALE == (3, 1)
    half = spec.FORK_THICKNESS / 2.0
    for z, y in (
        (half, spec.FORK_TOP_Y),
        (-half, spec.FORK_TOP_Y),
        (half, spec.FORK_BASE_Y - rod.SHANK_FACE_REF_RUN),
        (-half, spec.FORK_BASE_Y - rod.SHANK_FACE_REF_RUN),
    ):
        assert math.hypot(z, y - d.DETAIL_FENCE_Y_MM) < d.DETAIL_RADIUS_MM
    fence = d.DETAIL_RADIUS_MM * d.DETAIL_SCALE[0] / 1000.0
    # Right of the front view's ring and shank, inside the sheet's right
    # border, above the title block.
    front_right = d._sheet_xy(spec.RING_OUTER_RADIUS, 0.0)[0]
    assert d.DETAIL_CENTER[0] - fence > front_right + 0.040
    assert d.DETAIL_CENTER[1] - fence > 0.065
    for x, _ in d.DETAIL_KEEP.values():
        assert x < 0.400
    # The datum fork face (model -Z) stands on the detail's left.
    assert d._detail_xy(-half, 0.0)[0] < d.DETAIL_CENTER[0] < d._detail_xy(half, 0.0)[0]


def test_detail_texts_stand_outside_their_witness_lines() -> None:
    """The near tine's and the shank's near face's text stand left of the
    datum face's witness, the slot's right of the fork, the reference
    thickness over both tine texts; under the fork the shank's thickness
    stands a row below its near face's ordinate, text right of the shank."""
    d = drawing
    spec = ch_connecting_rod_spec
    face_x = d._detail_xy(-spec.FORK_THICKNESS / 2.0, 0.0)[0]
    far_x = d._detail_xy(spec.FORK_THICKNESS / 2.0, 0.0)[0]
    top = d._detail_xy(0.0, spec.FORK_TOP_Y)[1]
    root = d._detail_xy(0.0, spec.FORK_BASE_Y)[1]
    keep = d.DETAIL_KEEP
    assert keep["TineNear"][0] < face_x - 0.020
    assert keep["ShankFaceNear"][0] < face_x - 0.020
    assert keep["SlotWidth"][0] > far_x + 0.020
    assert top < keep["TineNear"][1] < keep["SlotWidth"][1] < keep["ForkThick"][1]
    assert keep["SlotDepth"][0] < keep["ForkBossLength"][0]
    # Both shank rows stand below the reference's lower end, outside the
    # fence, the smaller dimension nearer the fork and a full row apart.
    ref_end = d._detail_xy(0.0, spec.FORK_BASE_Y - rod.SHANK_FACE_REF_RUN)[1]
    fence_bottom = d.DETAIL_CENTER[1] - d.DETAIL_RADIUS_MM * d.DETAIL_SCALE[0] / 1000.0
    assert keep["ShankFaceNear"][1] < min(ref_end, fence_bottom) < root
    assert keep["ShankFaceNear"][1] - keep["ShankThick"][1] >= 0.007
    # The thickness's three characters end clear right of the far shank face.
    shank_far_x = d._detail_xy(-rod.SHANK_FAR_X, 0.0)[0]
    assert shank_far_x == pytest.approx(
        d._detail_xy(
            -spec.FORK_THICKNESS / 2.0 + spec.SHANK_FACE_NEAR + spec.SHANK_THICKNESS,
            0.0,
        )[0]
    )
    assert keep["ShankThick"][0] - 3 * 0.0025 / 2.0 > shank_far_x + 0.008
    # Above the title block.
    assert keep["ShankThick"][1] > 0.065 + 0.015


def test_model_bands_are_owned_by_named_model_dimensions() -> None:
    spec = ch_connecting_rod_spec
    assert spec.FORK_THICKNESS_BAND == pytest.approx(
        (2.0 * spec.TINE_BAND[0] + spec.FORK_SLOT_BAND[0],
         2.0 * spec.TINE_BAND[1] + spec.FORK_SLOT_BAND[1])
    )
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)",
        ("ForkSlotProfile", "TineNear"): "tine_upper",
        ("ForkSlotProfile", "SlotWidth"): "slot_upper",
        ("RingFaceReference", "RingFaceNear"): "face_upper",
        ("Ring", "RingThick"): "thick_upper",
    }
    # The reamed pin hole prints no band (owner ruling 2026-11-24, fit audit
    # question 3): no set_limits call.
    assert not _set_limits_calls()


def test_bore_finish_is_routed_clear_of_the_lower_dimension_stack() -> None:
    edge_x, edge_y = drawing.BORE_FINISH_EDGE
    symbol_x, symbol_y = drawing.BORE_FINISH_SYMBOL
    assert symbol_x > edge_x
    assert symbol_y > edge_y
    assert symbol_y > drawing.FRONT_KEEP["StrapBoreDia"][1] + 0.010
    assert symbol_x < 0.250
    # r1/r2: at the default 5 mm text the "Ra 1.6" ran into the detail's
    # plate-face callout; 2.5 mm text ends well left of it.
    assert drawing.BORE_FINISH_CHAR_HEIGHT == 0.0025
    ra_end = symbol_x + 0.006 + 6 * drawing.BORE_FINISH_CHAR_HEIGHT
    # The shank face's three-character value is the detail's lowest-left text.
    face_callout_left = drawing.DETAIL_KEEP["ShankFaceNear"][0] - 3 * 0.0025 / 2.0
    assert ra_end < face_callout_left - 0.005


def test_part_stamps_make_critical_drawing_properties() -> None:
    import _config

    spec = _config.parts("ch-connecting-rod")
    # Main ruling 2026-10: machined from 1018, black finish; #2173/#2340: the
    # stock is the bought cold-finished flat the route names. #2348 (owner
    # ruling 2026-11-20): black oxide and oil, as the channel lever.
    assert spec["material"] == rod.MATERIAL == "Plain Carbon Steel"
    assert "1018" in spec["material_specification"]
    assert "plate" not in spec["material_specification"].lower()
    assert spec["finish"] == _config.parts("ch-channel-lever")["finish"]
    assert "black oxide" in spec["finish"] and "oil" in spec["finish"]
    assert "ENAMEL" not in spec["finish"].upper()
    assert int(spec["quantity"]) == 20


def test_the_ring_and_shank_stay_flat_by_their_route_not_by_a_frame() -> None:
    """#2340: the ring's bow is bounded by its thickness and near-face bands
    (the fork's stand-off from the ring spends exactly those), so the sheet's one frame
    stays the pin hole's position (test_native_gdt_and_finish_present); the
    registry route takes equal stock off both faces of the bought 1/4 flat,
    and the figures it states are the model's."""
    import _config

    assert set(ch_connecting_rod_spec.GEOMETRIC_TOLERANCES_IN) == {
        "rocker pin hole position"
    }
    process = _config.parts("ch-connecting-rod")["process"]
    bar = 0.25 * 25.4
    for finished in (
        ch_connecting_rod_spec.FORK_THICKNESS,
        ch_connecting_rod_spec.RING_THICKNESS,
    ):
        per_face = (bar - finished) / 2.0 / 25.4
        assert f"{per_face:.3f}".lstrip("0") in process
    # The shank's faces are located from the fork's datum face, not centred:
    # the stock off its datum-face side and off the other.
    skim = (bar - ch_connecting_rod_spec.FORK_THICKNESS) / 2.0
    near = skim + ch_connecting_rod_spec.SHANK_FACE_NEAR
    far = bar - near - ch_connecting_rod_spec.SHANK_THICKNESS
    assert (near / 25.4, far / 25.4) == pytest.approx((0.055, 0.065))
    for per_face in (near, far):
        assert f"{per_face / 25.4:.3f}".lstrip("0") in process


_FEATURE_KINDS = {
    "datum_face": "face",
    "fork_far_face": "face",
    "ring_near_face": "face",
    "ring_far_face": "face",
    "shank_near_face": "face",
    "shank_far_face": "face",
    "shank_left_flank": "face",
    "shank_right_flank": "face",
    "ring": "boss",
    "fork": "profile",
    "fork_slot": "slot",
    "strap_bore": "hole",
    "pin_hole": "hole",
}


def _in(value_in: float) -> float:
    return value_in * 25.4


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(dia_mm: float, y_mm: float) -> FaceGeometry:
    r = dia_mm / 2
    box = tuple(v / 1000 for v in (-r, y_mm - r, -3.0, r, y_mm + r, 3.0))
    return FaceGeometry(None, 4002, (0.0, y_mm / 1000, 0.0, 0.0, 0.0, 1.0, r / 1000), None, box)


def test_the_rod_is_a_feature_export_part_with_one_owner_per_face() -> None:
    spec = ch_connecting_rod_spec
    assert "ch_connecting_rod" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("ch_connecting_rod")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    selectors = export_features.feature_selectors("ch_connecting_rod")
    datum = -spec.FORK_THICKNESS / 2
    ring_near = datum + spec.RING_FACE_NEAR
    shank_near = datum + spec.SHANK_FACE_NEAR
    slot = spec.FORK_SLOT_WIDTH / 2
    expected = {
        "datum_face": [_plane((0.0, 0.0, -1.0), -datum)],
        "fork_far_face": [_plane((0.0, 0.0, 1.0), -datum)],
        "ring_near_face": [_plane((0.0, 0.0, -1.0), -ring_near)],
        "ring_far_face": [_plane((0.0, 0.0, 1.0), ring_near + spec.RING_THICKNESS)],
        "shank_near_face": [_plane((0.0, 0.0, -1.0), -shank_near)],
        "shank_far_face": [
            _plane((0.0, 0.0, 1.0), shank_near + spec.SHANK_THICKNESS)
        ],
        "shank_left_flank": [_plane((-1.0, 0.0, 0.0), spec.SHANK_WIDTH / 2)],
        "shank_right_flank": [_plane((1.0, 0.0, 0.0), spec.SHANK_WIDTH / 2)],
        "ring": [_cylinder(spec.RING_OUTER_DIA, 0.0)],
        "fork": [
            _plane((1.0, 0.0, 0.0), spec.FORK_WIDTH / 2),
            _plane((-1.0, 0.0, 0.0), spec.FORK_WIDTH / 2),
            _cylinder(spec.FORK_WIDTH, spec.CENTER_DISTANCE),
            _plane((0.0, -1.0, 0.0), -spec.FORK_BASE_Y),
        ],
        "fork_slot": [
            _plane((0.0, 0.0, 1.0), -slot),
            _plane((0.0, 0.0, -1.0), -slot),
            _plane((0.0, 1.0, 0.0), spec.FORK_CROTCH_Y),
        ],
        "strap_bore": [_cylinder(spec.RING_BORE_DIA, 0.0)],
        "pin_hole": [_cylinder(spec.PIN_HOLE_DIA, spec.CENTER_DISTANCE)],
    }
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name
    # The model's R0.5 inside-corner fillets and its R.065 shank corners
    # belong to no feature.
    for radius in (spec.INSIDE_CORNER_R, ch_connecting_rod_notes.SHANK_CORNER_R):
        fillet = _cylinder(2 * radius, spec.FORK_CROTCH_Y)
        assert not any(
            selector.matches(fillet) for specs in selectors.values() for selector in specs
        )


def test_rod_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("ch_connecting_rod")["features"]
    assert features["ring_near_face"]["offset"] == pytest.approx(
        [_in(0.033), _in(0.037)]
    )
    assert features["ring_far_face"]["thickness"] == pytest.approx(
        [_in(0.168), _in(0.172)]
    )
    assert features["shank_near_face"]["offset"] == pytest.approx([_in(0.04), _in(0.06)])
    assert features["shank_far_face"]["thickness"] == pytest.approx(
        [_in(0.12), _in(0.14)]
    )
    assert features["fork_far_face"]["dimension_type"] == "reference"
    assert features["shank_right_flank"]["width"] == pytest.approx([_in(0.31), _in(0.33)])
    assert features["shank_left_flank"]["datum"] == "B"
    assert features["ring"]["dia"] == pytest.approx([_in(1.60), _in(1.62)])
    fork, slot = features["fork"], features["fork_slot"]
    assert fork["width"] == pytest.approx([_in(0.38), _in(0.40)])
    assert fork["boss_length"] == pytest.approx([_in(0.70), _in(0.72)])
    assert slot["width"] == pytest.approx([_in(0.104), _in(0.108)])
    for side in ("near_tine", "far_tine"):
        assert slot[side] == pytest.approx([_in(0.065), _in(0.069)])
    assert slot["depth"] == pytest.approx([_in(0.57), _in(0.59)])
    assert slot["corner_radius_max"] == pytest.approx(_in(0.040))
    flank = features["shank_right_flank"]
    assert flank["corner_r"] == pytest.approx([_in(0.060), _in(0.070)])
    assert flank["corner_count"] == 4
    assert flank["corner_callout"] == drawing.FRONT_CALLOUTS["ShankCornerR"]
    bore, pin = features["strap_bore"], features["pin_hole"]
    assert bore["dia"] == pytest.approx([_in(1.213), _in(1.216)])
    assert bore["datum"] == "A" and bore["finish_ra"] == pytest.approx(1.6)
    assert pin["dia"] == pytest.approx([_in(0.0775), _in(0.0779)])
    assert pin["position_dia"] == pytest.approx(_in(0.014))
    assert pin["callout"] == drawing.FRONT_CALLOUTS["PinHoleDia"]

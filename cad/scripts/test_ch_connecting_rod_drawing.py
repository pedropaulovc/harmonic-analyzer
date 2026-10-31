"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _drawing_leaders
import ch_connecting_rod_notes
import ch_connecting_rod_spec
import draw_ch_connecting_rod as drawing
import build_ch_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


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
    phase = math.radians(frame.CYLINDER_LOCK_PHASE_DEG)
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
    assert rod.SLOT_DEPTH == pytest.approx(14.75)
    assert rod.FORK_BOSS_LENGTH == pytest.approx(18.0)
    # The slot floor stands above the root step, so the bridge is solid.
    assert spec.FORK_BASE_Y < spec.FORK_CROTCH_Y < spec.CENTER_DISTANCE
    # Every drive in the slot sketch evaluates to its built value.
    source = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert "slot_sd.record(\"SlotDepth\",'\"ForkWidth\"/2+\"ForkCrotchBelowPin\"')" in source
    assert (
        "slot_sd.record(\"ForkBossLength\",'\"ForkWidth\"/2+\"ForkBaseBelowPin\"')"
        in source
    )
    # The side view locates from the fork's outer face (the reference line
    # stands on it), never from the mid-plane.
    assert "slot_sd.record(\"ForkFaceX\",'\"ForkThickness\"/2')" in source
    assert "slot_sd.record(\"TineNear\",'\"ForkTine\"')" in source
    assert 'set_global(adapter,"ForkThickness",\'2*"ForkTine"+"ForkSlotWidth"\')' in source
    assert "SlotHalfWidth" not in source


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
    assert rod.finished_volume() == pytest.approx(
        rod.boss_volume()
        - rod.slot_volume()
        + rod.inside_corner_volume()
        - rod.strap_bore_volume()
        - rod.pin_hole_volume()
    )
    assert 0.0 < rod.finished_volume() < rod.boss_volume()


def test_inside_corner_volume_is_the_fillets_closed_form() -> None:
    spec = ch_connecting_rod_spec
    r = spec.INSIDE_CORNER_R
    square = r**2 * (1.0 - math.pi / 4.0)
    assert rod._fillet_area(r, math.pi / 2.0) == pytest.approx(square)
    # A wider opening adds less; a straight wall adds nothing.
    assert rod._fillet_area(r, rod.SHANK_RING_OPENING) < square
    assert rod._fillet_area(r, math.pi) == pytest.approx(0.0, abs=1e-12)
    edges = 2.0 * spec.FORK_WIDTH + 2.0 * spec.SHANK_WIDTH + 2.0 * spec.SHANK_THICKNESS
    ring = rod._fillet_area(r, rod.SHANK_RING_OPENING) * 2.0 * spec.SHANK_THICKNESS
    assert rod.inside_corner_volume() == pytest.approx(square * edges + ring)


def test_pin_hole_is_the_reamed_press_hole_for_the_rod_pivot_pin() -> None:
    """User ruling 2026-10-09 (PR #1292 review F1): the MHA-CH-10 pin is
    pressed into both tines as the bar pin is into the amplitude bar
    (ch_rod_pivot_pin_spec holds the fit), so the hole is reamed to a band of
    its own, native on PinHoleDia, not a #47 drill."""
    import _config

    spec = ch_connecting_rod_spec
    assert rod.PIN_HOLE_DIA is spec.PIN_HOLE_DIA
    assert rod.PIN_HOLE_BAND is spec.PIN_HOLE_BAND
    assert drawing._PIN_HOLE_DIA is spec.PIN_HOLE_DIA
    assert spec.PIN_HOLE_DIA == 1.9558
    assert spec.PIN_HOLE_BAND == (0.02286, 0.0127)
    assert not hasattr(spec, "PIN_HOLE_SPEC")
    assert model_toleranced_dimensions(rod)[("PinHoleProfile", "PinHoleDia")] == (
        "*deviations(PIN_HOLE_BAND)"
    )
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'set_global(adapter,"PinHoleDia",f"{PIN_HOLE_DIA}mm")' in build
    assert 'names=(None,"PinHoleY","PinHoleDia")' in build
    assert "drives=(None,'\"CenterDistance\"','\"PinHoleDia\"')" in build
    assert 'name_last_feature(adapter,"PinHoleProfile")' in build
    assert 'name_last_feature(adapter,"PinHole")' in build
    assert drawing.PIN_NUMBER == _config.parts("ch-rod-pivot-pin")["number"]
    assert drawing.ARM_NUMBER == _config.parts("ch-rocker-arm")["number"]
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
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "add_chamfer(" not in source
    assert "wizard_holes(" not in source
    assert source.count("create_cut_extrude(") == 3  # slot, strap bore, pin hole
    assert not [name for name in dir(rod) if "countersink" in name.lower()]
    assert not [name for name in dir(spec) if "CSK" in name]
    thinnest_tine = spec.TINE_THICKNESS + spec.TINE_BAND[1]
    assert thinnest_tine == pytest.approx(1.65)
    assert thinnest_tine == spec.TINE_MIN
    assert spec.FORK_THICKNESS == pytest.approx(
        2.0 * spec.TINE_THICKNESS + spec.FORK_SLOT_WIDTH
    )
    assert thinnest_tine >= 1.5  # drawing-guidelines.md rule 17 (walls and webs) floor
    # Positive control: the countersink this replaced fails the same check.
    old_csk_depth = (3.2 + 0.127 - 1.994) / 2.0  # 90-degree: depth = radial step
    assert thinnest_tine - old_csk_depth < 1.5


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 2)" in source  # the isometric override
    # The left view stands level with the front (third-angle alignment) and
    # carries the fork detail's circle; every side-view dimension prints in
    # the detail.
    assert drawing.LEFT_CENTER == (0.080, drawing.FRONT_CENTER[1])
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)' in source
    # The note stands right of the shank's 8.00, below the pin annotations,
    # left of the detail's fence; the detail's dimensions stay inside the top
    # border.
    assert drawing.NOTES_XY[0] > drawing.FRONT_KEEP["ShankWidthDim"][0]
    assert drawing.NOTES_XY[1] < drawing.FRONT_KEEP["ShankWidthDim"][1] - 0.015
    assert drawing.NOTES_XY[0] + 0.065 < drawing.DETAIL_CENTER[0] - drawing._DETAIL_FENCE_R
    assert max(y for _, y in drawing.DETAIL_KEEP.values()) < 0.260
    assert ch_connecting_rod_notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_the_one_note_is_the_tine_wall_shortfall() -> None:
    """#982 baseline review: every size, location and band prints from its
    native model dimension and each tight band names its mate on its own
    callout, so the notes block shrank to the one rule-20 fact: the tines'
    printed minimum under the 2.0 wall target."""
    spec = ch_connecting_rod_spec
    notes = ch_connecting_rod_notes.DRAWING_NOTES
    assert notes == f"1. TINE WALL {spec.TINE_MIN:.2f} MIN."
    assert spec.TINE_MIN == pytest.approx(1.65)
    assert spec.TINE_MIN < 2.0
    for gone in ("FORK_TINE_MATCH", "RING_SLOT_SYMMETRY"):
        assert not hasattr(spec, gone)
    for word in ("MACHINED", "REAM", "PRESS", "SYMMETRIC", "CENTRED", "WITHIN"):
        assert word not in notes
    # Material and finish are title-block rows (drawing-guidelines.md rule 2
    # (the title block is the general specification)).
    for title_block_word in ("1018", "STEEL", "BLACK", "ENAMEL"):
        assert title_block_word not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_every_tight_band_names_its_mate() -> None:
    """drawing-guidelines.md rule 7: the bore's, the reamed hole's, the
    slot's, the tine's and the ring faces' bands each name the part they fit,
    on their own callout, with the clearance or interference they hold."""
    import ch_rod_pivot_pin_spec as pin

    spec = ch_connecting_rod_spec
    least, most = spec.STRAP_DIAMETRAL_CLEARANCE
    assert (least, most) == pytest.approx((0.193, 0.3438))
    bore = drawing.FRONT_CALLOUTS["StrapBoreDia"]
    assert bore.startswith("BORE")
    assert drawing.CAM_NUMBER in bore
    assert f"{least:.2f}-{most:.2f}" in bore
    ream = drawing.FRONT_CALLOUTS["PinHoleDia"]
    assert ream.startswith("THRU - REAM")
    assert drawing.PIN_NUMBER in ream
    assert (
        f"{pin.BUDGET['interference_min']:.3f}-{pin.BUDGET['interference_max']:.3f}"
        in ream
    )
    assert drawing.ARM_NUMBER in drawing.DETAIL_CALLOUTS["SlotWidth"]
    # The tine's band locates the slot from the datum face and holds the gap
    # to the next channel's rod, the same part (#982 review r2).
    assert drawing.ROD_NUMBER == "MHA-CH-03"
    assert drawing.ROD_NUMBER in drawing.DETAIL_CALLOUTS["TineNear"]
    assert drawing.DETAIL_CALLOUTS["TineNear"].startswith("2X; LOCATES SLOT;")
    assert drawing.CAM_NUMBER in drawing.DETAIL_CALLOUTS["RingFaceNear"]
    assert drawing.CAM_NUMBER in drawing.LEFT_CALLOUTS["RingThick"]
    assert drawing.LEFT_CALLOUTS["RingThick"].startswith("RING AND SHANK")
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


def test_plate_locates_from_the_fork_face_and_prints_its_thickness() -> None:
    """#982: the ring/shank plate's near face prints as a native ordinate
    from the fork's datum face (its near face, where the near tine is
    measured), and review r1 asked for the plate's thickness at the ring, not
    a second ordinate in a detail that does not show the ring: one locator,
    one size."""
    spec = ch_connecting_rod_spec
    assert spec.RING_FACE_NEAR == pytest.approx(
        (spec.FORK_THICKNESS - spec.RING_THICKNESS) / 2.0
    )
    assert spec.RING_FACE_NEAR == pytest.approx(1.950)
    assert not hasattr(spec, "RING_FACE_FAR")
    # Three-place ordinates and sizes, as the bands are written.
    for value in (spec.RING_FACE_NEAR, spec.RING_THICKNESS, spec.TINE_THICKNESS):
        assert round(value, 3) == pytest.approx(value, abs=1e-12)
    assert spec.SHANK_THICKNESS == spec.RING_THICKNESS
    assert spec.SHANK_THICKNESS_BAND == spec.RING_THICKNESS_BAND == (0.05, -0.05)
    assert spec.RING_THICKNESS + spec.RING_THICKNESS_BAND[1] >= 2.0  # rule 17
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'set_global(adapter,"RingFaceNear",\'("ForkThickness"-"RingThickness")/2\')' in build
    assert 'name_dimensions(adapter,"Plate",["RingThick"])' in build
    # #982 review r2: two coplanar bosses left the shank's flanks as seams
    # across the ring's faces; ring and shank are one outline, one extrusion.
    assert 'name_last_feature(adapter,"PlateProfile")' in build
    assert '"Shank"' not in build and "ShankProfile" not in build
    assert build.count("create_extrusion(") == 2  # plate, fork boss
    assert "(ring_thick_dim[0],'\"RingThickness\"')" in build
    assert "RingFaceFar" not in build
    assert set(drawing.LEFT_KEEP) == {"RingThick"}
    # The thickness stands below the ring, its text out to the left.
    ring_bottom = drawing._left_xy(0.0, spec.RING_BOTTOM_Y)
    text_x, text_y = drawing.LEFT_KEEP["RingThick"]
    assert text_y < ring_bottom[1] and text_x < ring_bottom[0] - 0.020
    # r2: two long lines ran into the sheet border; centred on the keep at
    # ~2.5 mm a character, the widest line stays 5 mm inside it (x 0.013).
    widest = max(len(line) for line in drawing.LEFT_CALLOUTS["RingThick"].splitlines())
    assert text_x - widest * 0.0025 / 2.0 > 0.013 + 0.005


def test_inside_corners_are_one_modelled_radius_under_the_title_block() -> None:
    """#982 review r1 (drawing-guidelines.md rule 16): the slot floor, the
    fork's root step and the shank's run onto the ring had sharp inside
    corners. One fillet carries them all. The ENFORCE review found the
    printed all-corners R0.5 MAX a needless tightening of the title block's
    INSIDE CORNERS R1.0 MAX, so the title block governs; that ceiling still
    stands under the arm's least clearance over the slot floor."""
    import _config
    import ch_rod_pivot_pin_spec as pin

    spec = ch_connecting_rod_spec
    ceiling = float(_config.title_block("inside_corner")["radius_mm"])
    assert spec.INSIDE_CORNER_R <= ceiling
    assert ceiling < pin.BUDGET["crotch_clearance_min"]
    assert 2.0 * ceiling < spec.FORK_SLOT_WIDTH + spec.FORK_SLOT_BAND[1]
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert source.count("add_fillet(") == 1
    assert 'name_last_feature(adapter, "InsideCorners")' in source
    assert "_inside_corner_max_limit" not in source
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
    assert d.OVERALL_LENGTH == pytest.approx(183.769, abs=1e-3)
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
    source = Path(d.__file__).read_text(encoding="utf-8")
    assert "face_silhouettes_through(" in source
    assert "entities=ends," in source
    assert (
        'set_reference_dimension(adapter, overall.GetAnnotation(), label="overall length")'
        in source
    )


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
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    # The A-to-B locator's own block: centre-anchored, value-checked at half
    # the shank width, then boxed (not satisfied by the B-to-pin check).
    start = source.index("datum_b_offset = add_edge_dimension(")
    end = source.index(
        'set_basic_dimension(adapter, datum_b_offset, label="datum B from datum A")'
    )
    block = source[start:end]
    assert "p1=ring_rim," in block
    assert 'set_arc_endpoints_to_center(adapter, datum_b_offset, label="datum B from datum A")' in block
    assert (
        "assert_dimension_measures(\n"
        "        adapter,\n"
        "        datum_b_offset,\n"
        "        expected_mm=SHANK_WIDTH / 2.0,\n"
    ) in block


def test_ring_diameters_keep_one_arrow_on_the_near_rim() -> None:
    """#982 review r2: both diameters ran rim to rim through the bore's
    centre and crossed there."""
    assert drawing.set_near_side_diameter is _drawing_leaders.set_near_side_diameter
    assert drawing.NEAR_SIDE_DIAMETERS == ("RingOuterDia", "StrapBoreDia")
    assert set(drawing.NEAR_SIDE_DIAMETERS) <= set(drawing.FRONT_KEEP)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(matches[0], f"ring {name}")' in source


def test_fork_print_is_three_place_and_model_owned() -> None:
    marked = ch_connecting_rod_notes.DRAWING_DIMENSIONS
    assert marked["ForkBoss"] == {"ForkThick"}
    assert marked["ForkSlotProfile"] == {
        "TineNear",
        "SlotWidth",
        "RingFaceNear",
        "SlotDepth",
        "ForkBossLength",
    }
    assert marked["Plate"] == {"RingThick"}
    assert marked["PlateProfile"] == {"RingOuterDia", "ShankWidthDim"}
    assert marked["ForkProfile"] == {"ForkWidthDim"}
    assert rod.DRAWING_PRECISION is ch_connecting_rod_notes.DRAWING_PRECISION
    assert ch_connecting_rod_notes.DRAWING_PRECISION == {
        "Plate": {"RingThick": 3},
        "ForkBoss": {"ForkThick": 3},
        "ForkSlotProfile": {
            "TineNear": 3,
            "SlotWidth": 3,
            "RingFaceNear": 3,
        },
        "PinHoleProfile": {"PinHoleDia": 4},
    }
    build = "".join(Path(rod.__file__).read_text(encoding="utf-8").split())
    assert 'name_dimensions(adapter,"ForkBoss",["ForkThick"])' in build
    assert "(fork_thickness_dim[0],'\"ForkThickness\"')" in build
    assert "apply_drawing_precision(adapter,DRAWING_PRECISION)" in build
    # The fork over the tines is a reference: two tines and the slot set it.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        'set_reference_dimension(adapter, fork_thick[0], label="fork over the tines")'
        in source
    )


def test_reamed_pin_hole_is_a_native_four_place_dimension() -> None:
    """PR #1292 review N1 (drawing-simplicity-policy.md `How the repository implements the guidelines` and drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the press hole's Ø1.9558
    +0.02286/+0.0127 is the PinHoleDia model dimension -- marked, authored at
    four places with its native band -- imported into the front view with the
    process beneath it, never general-note text."""
    spec = ch_connecting_rod_spec
    assert ch_connecting_rod_notes.DRAWING_DIMENSIONS["PinHoleProfile"] == {
        "PinHoleDia"
    }
    assert ch_connecting_rod_notes.DRAWING_PRECISION["PinHoleProfile"] == {
        "PinHoleDia": 4
    }
    # The band is exact at five places, as the shared setter prints it.
    assert all(round(d, 5) == d for d in spec.PIN_HOLE_BAND)
    assert model_toleranced_dimensions(rod)[("PinHoleProfile", "PinHoleDia")] == (
        "*deviations(PIN_HOLE_BAND)"
    )
    assert "PinHoleDia" in drawing.FRONT_KEEP
    assert drawing.FRONT_CALLOUTS["PinHoleDia"].startswith("THRU - REAM")
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
    assert text_y > drawing.NOTES_XY[1] + 0.040
    assert text_x < drawing.DETAIL_KEEP["TineNear"][0] - 0.040


def test_fork_detail_takes_in_the_crown_and_the_ring_faces() -> None:
    """#982: the side view's fork dimensions crowded a 6 mm fork at 1:1, so a
    native 3:1 detail carries them. Its fence takes in the crown top and the
    ring-face references below the root step, and stands clear of the front
    view, the title block and the isometric."""
    d = drawing
    spec = ch_connecting_rod_spec
    assert d.DETAIL_SCALE == (3, 1)
    half = spec.FORK_THICKNESS / 2.0
    for z, y in (
        (half, spec.FORK_TOP_Y),
        (-half, spec.FORK_TOP_Y),
        (half, spec.FORK_BASE_Y - rod.RING_FACE_REF_RUN),
        (-half, spec.FORK_BASE_Y - rod.RING_FACE_REF_RUN),
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
    source = Path(d.__file__).read_text(encoding="utf-8")
    assert "detail = _fork_detail(adapter, left)" in source
    assert "set_hidden_lines_visible" not in source
    # ENFORCE farm runs: the inferred fence snapped in screen space (12.4,
    # then 9.7 mm, off the rod axis); it is authored direct-to-DB and read
    # back, with AddToDB restored in a finally block.
    detail_source = source[source.index("def _fork_detail") : source.index("async def build")]
    assert "manager.AddToDB = True" in detail_source
    assert "finally:\n        manager.AddToDB = previous_add_to_db" in detail_source
    assert "the fork detail fence moved from where it was placed" in detail_source


def test_detail_texts_stand_outside_their_witness_lines() -> None:
    """The near tine's and the plate's near face's text stand left of the
    datum face's witness, the slot's right of the fork, the reference
    thickness over both tine texts."""
    d = drawing
    spec = ch_connecting_rod_spec
    face_x = d._detail_xy(-spec.FORK_THICKNESS / 2.0, 0.0)[0]
    far_x = d._detail_xy(spec.FORK_THICKNESS / 2.0, 0.0)[0]
    top = d._detail_xy(0.0, spec.FORK_TOP_Y)[1]
    root = d._detail_xy(0.0, spec.FORK_BASE_Y)[1]
    keep = d.DETAIL_KEEP
    assert keep["TineNear"][0] < face_x - 0.020
    assert keep["RingFaceNear"][0] < face_x - 0.020
    assert keep["SlotWidth"][0] > far_x + 0.020
    assert top < keep["TineNear"][1] < keep["SlotWidth"][1] < keep["ForkThick"][1]
    assert keep["RingFaceNear"][1] < root
    assert keep["SlotDepth"][0] < keep["ForkBossLength"][0]


def test_model_bands_are_owned_by_named_model_dimensions() -> None:
    spec = ch_connecting_rod_spec
    assert spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert spec.TINE_BAND == (0.05, -0.05)
    assert spec.FORK_SLOT_BAND == (0.05, -0.05)
    assert spec.RING_FACE_BAND == (0.05, -0.05)
    assert spec.RING_THICKNESS_BAND == (0.05, -0.05)
    assert spec.FORK_THICKNESS_BAND == pytest.approx((0.15, -0.15))
    assert model_toleranced_dimensions(rod) == {
        ("StrapBoreProfile", "StrapBoreDia"): "*deviations(RING_BORE_DIA_BAND)",
        ("ForkSlotProfile", "TineNear"): "tine_upper",
        ("ForkSlotProfile", "SlotWidth"): "slot_upper",
        ("ForkSlotProfile", "RingFaceNear"): "face_upper",
        ("Plate", "RingThick"): "thick_upper",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_BAND)",
    }


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
    face_callout_left = drawing.DETAIL_KEEP["RingFaceNear"][0] - 0.030
    assert ra_end < face_callout_left - 0.005
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "char_height=BORE_FINISH_CHAR_HEIGHT," in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("ch-connecting-rod")
    # Main ruling 2026-10: machined from 1018 plate, black finish.
    assert spec["material"] == rod.MATERIAL == "Plain Carbon Steel"
    assert spec["material_specification"] == "AISI 1018 low-carbon steel plate"
    assert spec["finish"] == (
        "BLACK ENAMEL; MASK BORE, PLATE FACES, PIN HOLE AND FORK SLOT; "
        "OIL BARE MACHINED SURFACES"
    )
    assert int(spec["quantity"]) == 20

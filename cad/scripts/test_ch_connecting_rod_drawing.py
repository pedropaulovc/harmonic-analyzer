"""Offline contracts for the connecting-rod drawing."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_leaders
import ch_connecting_rod_notes
import ch_connecting_rod_spec
import draw_ch_connecting_rod as drawing
import build_ch_connecting_rod as rod
from _drawing_contract import model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import Box, Segment, segment_box_distance


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-connecting-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-connecting-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-connecting-rod_drawing.png")
    assert DRAWINGS_BY_NAME["ch_connecting_rod"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert rod.DRAWING_DIMENSIONS is ch_connecting_rod_notes.DRAWING_DIMENSIONS
    marked = set().union(*ch_connecting_rod_notes.DRAWING_DIMENSIONS.values())
    views = (
        drawing.FRONT_KEEP, drawing.LEFT_KEEP, drawing.DETAIL_KEEP,
        drawing.ROOT_SECTION_KEEP,
    )
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
        - rod.root_relief_volume()
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
    assert spec.PIN_HOLE_DIA == 1.968
    assert spec.PIN_HOLE_BAND == (0.010, 0.0)
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
    assert (least, most) == pytest.approx((0.20, 0.35))
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
        *drawing.ROOT_SECTION_CALLOUTS.values(),
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


def test_inside_corners_are_one_modelled_radius_printed_max() -> None:
    """#982 review r1 (drawing-guidelines.md rule 16): the slot floor, the
    fork's root step and the shank's run onto the ring had sharp inside
    corners. One fillet carries them all, R MAX, the model value the printed
    maximum, and stands under the arm's least clearance over the slot floor."""
    import ch_rod_pivot_pin_spec as pin

    spec = ch_connecting_rod_spec
    assert spec.INSIDE_CORNER_R == 0.5
    assert spec.INSIDE_CORNER_BAND == (0.0, -spec.INSIDE_CORNER_R)
    assert spec.INSIDE_CORNER_TOL_TYPE == 6  # swTolMAX
    assert spec.INSIDE_CORNER_R < pin.BUDGET["crotch_clearance_min"]
    assert 2.0 * spec.INSIDE_CORNER_R < spec.FORK_SLOT_WIDTH + spec.FORK_SLOT_BAND[1]
    source = Path(rod.__file__).read_text(encoding="utf-8")
    assert source.count("add_fillet(") == 1
    assert 'name_last_feature(adapter, "InsideCorners")' in source
    assert "tolerance.Type = INSIDE_CORNER_TOL_TYPE" in source
    assert "_inside_corner_max_limit(adapter)" in source
    assert ch_connecting_rod_notes.DRAWING_DIMENSIONS["InsideCorners"] == {"InsideCornerR"}
    assert drawing.FRONT_CALLOUTS["InsideCornerR"] == "ALL INSIDE CORNERS"
    # The text stands up-right of the shank's +X flank onto the ring (the
    # fillet's first edge), below the note and left of the bore's finish.
    junction = drawing._sheet_xy(
        spec.SHANK_WIDTH / 2.0,
        math.sqrt(spec.RING_OUTER_RADIUS**2 - (spec.SHANK_WIDTH / 2.0) ** 2),
    )
    text_x, text_y = drawing.FRONT_KEEP["InsideCornerR"]
    assert text_x > junction[0] and text_y > junction[1]
    assert text_y < drawing.NOTES_XY[1] - 0.015
    assert text_y > drawing.BORE_FINISH_SYMBOL[1] + 0.015
    # Right of the shank's flank: the text never sits on the part.
    assert text_x - 0.025 > drawing._sheet_xy(spec.SHANK_WIDTH / 2.0, 0.0)[0]


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


def _native_pin_offset(monkeypatch):
    """The front view's native records round the 4.00 BASIC, as the shared
    collector dumps them (sheet metres): the press-fit callout parked up-right
    of the pin, the BASIC between the pin axis and the flank, datum B's tag on
    the flank below the fork root, and the shank width far down the shank.
    Only the COM reads are replaced; the shared geometry decoder is real."""

    def line(x0, y0, x1, y1):
        return [0, 0, 0, 0, x0, y0, 0.0, x1, y1, 0.0]

    def arrow(x, y, dx, dy):
        return [x, y, 0.0, dx, dy, 0.0, 0.003556, 0.000762, 0.0, 0.0, 0.0, 1.0]

    def text(t, x, y):
        return {"t": t, "pos": [x, y, 0.0], "h": 0.0035, "ref": 1}

    def dimension(name, lines, arrows, texts):
        return {
            "type": 4, "name": name, "visible": 1,
            "display": {"lines": lines, "arrows": arrows, "texts": texts},
            "dim": {"hole_callout": False},
        }

    def pin_callout(dy=0.0):
        # From the rim down-right to a shoulder under the parked text.
        return dimension(
            "PinHoleDia",
            [
                line(0.1507, 0.1993 + dy, 0.1582, 0.1893 + dy),
                line(0.1582, 0.1893 + dy, 0.1702, 0.1893 + dy),
            ],
            [arrow(0.1507, 0.1993 + dy, 0.6, -0.8)],
            [text("<MOD-DIAM>1.968 +0.010/0", 0.1592, 0.1896 + dy)],
        )

    def basic(dy=0.0):
        # Outside arrows on the flank and the pin axis; the extension lines
        # run up past the whole pin callout.
        y = 0.1790 + dy
        return dimension(
            "PinOffset",
            [
                line(0.146, 0.1770, 0.146, 0.2000),
                line(0.150, 0.1770, 0.150, 0.2000),
                line(0.13965, y, 0.146, y),
                line(0.146, y, 0.150, y),
                line(0.150, y, 0.15635, y),
            ],
            [arrow(0.146, y, -1.0, 0.0), arrow(0.150, y, 1.0, 0.0)],
            [text(" 4.00 ", 0.1575, y - 0.0015)],
        )

    def shank(line_y=0.1000):
        # Its extension lines run the flanks up through the BASIC's lane.
        return dimension(
            "ShankWidthDim",
            [
                line(0.146, 0.0990, 0.146, 0.1950),
                line(0.154, 0.0990, 0.154, 0.1950),
                line(0.146, line_y, 0.154, line_y),
            ],
            [arrow(0.146, line_y, 1.0, 0.0), arrow(0.154, line_y, -1.0, 0.0)],
            [text(" 8.00 ", 0.1475, line_y + 0.0008)],
        )

    datum = {
        "type": 2, "name": "B", "visible": 1,
        "display": {
            "lines": [
                line(0.138, 0.164, 0.144, 0.164), line(0.144, 0.164, 0.144, 0.170),
                line(0.144, 0.170, 0.138, 0.170), line(0.138, 0.170, 0.138, 0.164),
            ],
            "triangles": [
                [0.146, 0.167, 0.0, 0.144, 0.1685, 0.0, 0.144, 0.1655, 0.0, 1, 0]
            ],
            "texts": [text("B", 0.1395, 0.1655)],
        },
    }
    pin = SimpleNamespace(name="PinHoleDia", record=pin_callout())
    shank_item = SimpleNamespace(name="ShankWidthDim", record=shank())
    datum_b = SimpleNamespace(GetAnnotation=lambda: SimpleNamespace(record=datum))
    annotation = SimpleNamespace(
        record=basic(), IsDangling=lambda: False,
        GetAttachedEntities3=lambda: [object()],
    )
    display = SimpleNamespace(
        GetAnnotation=lambda: annotation,
        GetDimension2=lambda index: SimpleNamespace(SystemValue=0.004),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, name: value)
    monkeypatch.setattr(drawing, "dimension_name", lambda adapter, item: item.name)
    monkeypatch.setattr(
        drawing, "_Reader", lambda adapter: SimpleNamespace(take_errors=lambda: [])
    )
    monkeypatch.setattr(drawing, "_dump_annotation", lambda reader, raw: raw.record)
    return SimpleNamespace(
        adapter=object(), display=display, front=[pin, shank_item], datum_b=datum_b,
        pin=pin, shank=shank_item, annotation=annotation,
        pin_callout=pin_callout, basic=basic, shank_record=shank,
    )


def test_pin_offset_basic_sits_below_the_whole_pin_callout(monkeypatch) -> None:
    """#982 review r3 / baseline PNG: the BASIC's dimension line may not
    cross the press-fit callout. Its own and the shank's tall extension
    lines, which run through the callout and the lane, are allowed."""
    native = _native_pin_offset(monkeypatch)
    drawing._pin_offset_layout(native.adapter, native.display, native.front, native.datum_b)


@pytest.mark.parametrize("defect", ["basic-through-callout", "shank-line-in-lane"])
def test_pin_offset_basic_rejects_a_dimension_line_crossing(monkeypatch, defect) -> None:
    native = _native_pin_offset(monkeypatch)
    if defect == "basic-through-callout":
        native.annotation.record = native.basic(dy=0.012)
    else:
        # The shank's dimension line and text now reach into the BASIC's ink,
        # while its tall extension lines were already crossing the lane.
        native.shank.record = native.shank_record(line_y=0.1740)
    with pytest.raises(RuntimeError, match="leaves its native clear lane"):
        drawing._pin_offset_layout(
            native.adapter, native.display, native.front, native.datum_b
        )


def test_pin_offset_basic_refuses_a_lane_too_short_for_its_text(monkeypatch) -> None:
    native = _native_pin_offset(monkeypatch)
    native.pin.record = native.pin_callout(dy=-0.012)
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._pin_offset_layout(
            native.adapter, native.display, native.front, native.datum_b
        )


def test_ring_diameters_keep_one_arrow_on_the_near_rim() -> None:
    """#982 review r2: both diameters ran rim to rim through the bore's
    centre and crossed there."""
    assert drawing.set_near_side_diameter is _drawing_leaders.set_near_side_diameter
    assert drawing.NEAR_SIDE_DIAMETERS == ("RingOuterDia", "StrapBoreDia")
    assert set(drawing.NEAR_SIDE_DIAMETERS) <= set(drawing.FRONT_KEEP)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(matches[0], f"ring {name}")' in source


def test_reamed_pin_hole_is_a_native_three_place_dimension() -> None:
    """PR #1292 review N1 (drawing-simplicity-policy.md `How the repository implements the guidelines` and drawing-guidelines.md rule 7 (notes: few, flagged, never a method)): the press hole's Ø1.968
    +0.010/0 is the PinHoleDia model dimension -- marked, authored at three
    places with its native band -- imported into the front view with the
    process beneath it, never general-note text."""
    spec = ch_connecting_rod_spec
    assert ch_connecting_rod_notes.DRAWING_DIMENSIONS["PinHoleProfile"] == {
        "PinHoleDia"
    }
    assert ch_connecting_rod_notes.DRAWING_PRECISION["PinHoleProfile"] == {
        "PinHoleDia": 3
    }
    # The band is written at three places, as the precision prints it.
    assert all(round(d, 3) == d for d in spec.PIN_HOLE_BAND)
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
        '        {**DRAWING_PRECISION["PinHoleProfile"], '
        '**DRAWING_PRECISION["InsideCorners"]},\n'
        "    )" in source
    )
    # The Ø text stands right of the fork, below the FCF's level leader (so
    # the two leaders cannot cross) and clear of the detail's tine text.
    hole_x, hole_y = drawing._sheet_xy(0.0, spec.CENTER_DISTANCE)
    text_x, text_y = drawing.FRONT_KEEP["PinHoleDia"]
    assert text_x > hole_x + 0.030 and text_y < hole_y - 0.020
    assert text_y > drawing.NOTES_XY[1] + 0.040
    assert text_x < drawing.DETAIL_KEEP["TineNear"][0] - 0.040


def test_reamed_pin_hole_band_prints_at_the_value_s_places(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Farm render of 1b1f2f7fd printed "Ø1.968 +0.01/0.00": the shared
    setter prints a band at the fewest places that hold it (two, for 0.010),
    under a value authored at three.  The part build re-sets PinHoleDia's
    tolerance places from the same DRAWING_PRECISION entry as its value's,
    after both the band and the value places are authored."""
    import _drawing_tolerances
    import inspect

    from _fit_deviations import deviations

    spec = ch_connecting_rod_spec
    value_places = ch_connecting_rod_notes.DRAWING_PRECISION["PinHoleProfile"][
        "PinHoleDia"
    ]
    # The defect: left to the shared setter the band reads +0.01/0.00.
    assert _drawing_tolerances._tolerance_places(*deviations(spec.PIN_HOLE_BAND)) == 2
    assert value_places == 3

    calls: list[tuple[int, int, int, int]] = []

    class Display:
        tolerance_places = 2

        def SetPrecision3(
            self, primary: int, dual: int, primary_tol: int, dual_tol: int
        ) -> int:
            calls.append((primary, dual, primary_tol, dual_tol))
            self.tolerance_places = primary_tol
            return 0

        def GetPrimaryTolPrecision2(self) -> int:
            return self.tolerance_places

    display = Display()
    looked_up: list[tuple[str, str]] = []

    def named_dimension(_adapter, feature: str, name: str):
        looked_up.append((feature, name))
        return display, None

    monkeypatch.setattr(rod, "_named_dimension", named_dimension)
    monkeypatch.setattr(rod, "_early_bound", lambda value, _type: value)
    places = rod.tolerance_at_dimension_places(object(), "PinHoleProfile", "PinHoleDia")
    assert looked_up == [("PinHoleProfile", "PinHoleDia")]
    # Primary (value) places untouched; the tolerance takes the value's places.
    assert calls == [(-1, -1, value_places, -1)]
    assert places == display.tolerance_places == value_places

    build = inspect.getsource(rod.build)
    band = build.index('"PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_BAND)')
    value = build.index("apply_drawing_precision(adapter, DRAWING_PRECISION)")
    tolerance = build.index(
        'tolerance_at_dimension_places(adapter, "PinHoleProfile", "PinHoleDia")'
    )
    assert band < tolerance and value < tolerance


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
        "BLACK ENAMEL; MASK STRAP BORE, RING FACES, PIN HOLE AND FORK SLOT; "
        "OIL BARE MACHINED SURFACES"
    )
    assert int(spec["quantity"]) == 20


def test_root_relief_includes_angle_and_opposite_edge_in_its_land() -> None:
    spec = ch_connecting_rod_spec
    envelope = spec.ROOT_RELIEF_ENVELOPE
    assert envelope["leg_min"] == pytest.approx(1.1 * math.tan(math.radians(44.0)))
    assert envelope["leg_max"] == pytest.approx(1.3 * math.tan(math.radians(46.0)))
    assert envelope["straight_land_min"] == pytest.approx(0.5288105921)
    assert envelope["straight_land_min"] < 0.575  # exact 45° missed angle scatter
    assert spec.OPPOSITE_EDGE_BREAK_MAX == 0.25
    assert spec.RING_THICKNESS == 2.175
    assert spec.RING_THICKNESS_BAND == (0.05, -0.05)
    assert spec.RING_BORE_DIA == 30.8
    assert spec.RING_BORE_DIA_BAND == (0.10, 0.00)
    assert spec.STRAP_DIAMETRAL_CLEARANCE == pytest.approx((0.20, 0.35))


@pytest.mark.parametrize("width", [1.1, 1.3])
@pytest.mark.parametrize("angle", [44.0, 46.0])
def test_root_relief_clears_the_whole_R1_corner_at_contact(width, angle) -> None:
    # Local radial contact deliberately spends ALL bore clearance, and the
    # strap face has ZERO axial gap to the web. Neither clearance is credited.
    r = ch_connecting_rod_spec.CAM_ROOT_RADIUS_MAX
    first, second = width, width * math.tan(math.radians(angle))
    for radial, axial in ((first, second), (second, first)):
        for step in range(101):
            phase = math.pi / 2.0 * step / 100.0
            root_x = r * (1.0 - math.cos(phase))
            root_z = r * (1.0 - math.sin(phase))
            assert root_x / radial + root_z / axial < 1.0
    assert min(first, second) > r


def test_root_relief_rejects_root_overlap_and_only_nonpositive_land() -> None:
    spec = ch_connecting_rod_spec
    with pytest.raises(ValueError, match="cam root"):
        spec.root_relief_envelope(size=1.0)
    consumed = spec.ROOT_RELIEF_ENVELOPE["leg_max"] + spec.OPPOSITE_EDGE_BREAK_MAX
    with pytest.raises(ValueError, match="consume"):
        spec.root_relief_envelope(thickness_min=consumed)
    assert spec.root_relief_envelope(thickness_min=consumed + 1e-8)[
        "straight_land_min"
    ] == pytest.approx(1e-8)


def test_one_root_relief_has_the_annular_frustum_volume() -> None:
    spec = ch_connecting_rod_spec
    bore = spec.RING_BORE_DIA / 2.0
    mouth = bore + spec.ROOT_RELIEF_SIZE
    depth = spec.ROOT_RELIEF_SIZE
    frustum = math.pi * depth / 3.0 * (bore**2 + bore * mouth + mouth**2)
    original_bore = math.pi * bore**2 * depth
    assert rod.root_relief_volume() == pytest.approx(frustum - original_bore)
    assert rod.root_relief_volume() == pytest.approx(71.4775160533)


def _native_relief_boundary(monkeypatch):
    spec = ch_connecting_rod_spec
    radius, face_z = spec.RING_BORE_DIA / 2.0, -spec.RING_THICKNESS / 2.0

    def circle(r, z):
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            CircleParams=(0.0, 0.0, z / 1000.0, 0.0, 0.0, 1.0, r / 1000.0),
        )
        return SimpleNamespace(
            GetCurve=lambda: curve,
            GetCurveParams2=lambda: (
                r / 1000.0, 0.0, z / 1000.0, r / 1000.0, 0.0, z / 1000.0,
                0.0, math.tau, 0.0, 0.0, 0.0,
            ),
        )

    tolerance = SimpleNamespace(
        Type=4, GetMinValue=lambda: -0.0001, GetMaxValue=lambda: 0.0001
    )
    size = SimpleNamespace(
        Name="RootReliefSize", SystemValue=0.0012, Tolerance=tolerance,
        FullName="RootReliefSize@CamRootRelief@ch-connecting-rod",
    )
    angle = SimpleNamespace(
        Name="RootReliefAngle", SystemValue=math.pi / 4.0, Tolerance=SimpleNamespace(Type=0),
        FullName="RootReliefAngle@CamRootRelief@ch-connecting-rod",
    )
    display = SimpleNamespace(
        Type2=2, MarkedForDrawing=True, GetDimension2=lambda index: size,
        GetPrimaryPrecision2=lambda: 1, GetPrimaryTolPrecision2=lambda: 1,
    )
    angle_display = SimpleNamespace(
        Type2=3, MarkedForDrawing=True, GetDimension2=lambda index: angle,
        GetPrimaryPrecision2=lambda: 0,
    )
    displays = [display, angle_display]
    released = []
    definition = SimpleNamespace(
        Type=1, TangentPropagation=False, EdgeChamferAngle=math.pi / 4.0,
        GetEdgeChamferDistance=lambda side: 0.0012 if side == 0 else float("nan"),
        AccessSelections=lambda model, component: True,
        ReleaseSelectionAccess=lambda: released.append(True),
        Edges=[circle(radius, face_z)],
    )
    definition.GetEdgeCount = lambda: len(definition.Edges)
    definition.GetFaceCount = lambda: 0
    cone_edges = [
        circle(radius + spec.ROOT_RELIEF_SIZE, face_z),
        circle(radius, face_z + spec.ROOT_RELIEF_SIZE),
    ]
    land_edges = [
        circle(radius, face_z + spec.ROOT_RELIEF_SIZE),
        circle(radius, -face_z),
    ]
    cone = SimpleNamespace(
        GetEdges=lambda: cone_edges,
        GetSurface=lambda: SimpleNamespace(IsCone=lambda: True),
    )
    bore = SimpleNamespace(
        GetEdges=lambda: land_edges,
        GetSurface=lambda: SimpleNamespace(
            IsCylinder=lambda: True,
            CylinderParams=(0.0, 0.0, 0.0, 0.0, 0.0, 1.0, radius / 1000.0),
        ),
    )
    features = {
        "CamRootRelief": SimpleNamespace(
            GetDefinition=lambda: definition, GetFaces=lambda: [cone],
            displays=displays,
        ),
        "StrapBore": SimpleNamespace(GetFaces=lambda: [bore]),
    }
    monkeypatch.setattr(rod, "_early_bound", lambda value, name: value)
    monkeypatch.setattr(rod, "_feature_by_name", lambda adapter, name: features[name])
    monkeypatch.setattr(rod, "_feature_display_dimensions", lambda feature: iter(feature.displays))
    return SimpleNamespace(
        adapter=SimpleNamespace(currentModel=object()), circle=circle,
        definition=definition, display=display, size=size, angle=angle,
        angle_display=angle_display, displays=displays,
        cone_edges=cone_edges, land_edges=land_edges, released=released,
        radius=radius, face_z=face_z,
    )


@pytest.mark.parametrize("reversed_order", [False, True])
def test_relief_model_resolves_owned_scalar_drivers_independently_of_order(
    monkeypatch, reversed_order,
):
    native = _native_relief_boundary(monkeypatch)
    if reversed_order:
        native.displays.reverse()
    foreign = SimpleNamespace(
        Type2=3,
        GetDimension2=lambda index: SimpleNamespace(
            FullName="OtherAngle@UnrelatedFeature@ch-connecting-rod",
            SystemValue=math.pi / 4.0,
        ),
    )
    native.displays.append(foreign)
    width_display, size, angle_display, angle = rod._root_relief_dimensions(native.adapter)
    assert width_display is native.display
    assert size is native.size
    assert angle_display is native.angle_display
    assert angle is native.angle
    # A scalar display ignores Index=1; it must never become the other driver.
    assert native.display.GetDimension2(1) is size
    assert native.angle_display.GetDimension2(1) is angle


@pytest.mark.parametrize(
    "defect", ["missing-angle", "wrong-angle-type", "wrong-owner", "duplicate-angle", "wrong-width"],
)
def test_relief_model_refuses_unproved_or_ambiguous_angular_driver(monkeypatch, defect):
    native = _native_relief_boundary(monkeypatch)
    if defect == "missing-angle":
        native.displays.remove(native.angle_display)
    elif defect == "wrong-angle-type":
        native.angle_display.Type2 = 2
    elif defect == "wrong-owner":
        native.angle.FullName = "RootReliefAngle@OtherFeature@ch-connecting-rod"
    elif defect == "duplicate-angle":
        native.displays.append(native.angle_display)
    elif defect == "wrong-width":
        native.size.SystemValue = 0.0011
    with pytest.raises(RuntimeError, match="cam-root relief"):
        rod._root_relief_dimensions(native.adapter)


def test_native_relief_reads_one_mouth_both_legs_and_untouched_opposite_edge(monkeypatch):
    native = _native_relief_boundary(monkeypatch)
    rod._assert_cam_root_relief(native.adapter, marked=True)
    assert native.released == [True]


@pytest.mark.parametrize(
    "defect",
    [
        "wrong-mouth", "both-mouths", "cone-leg", "opposite-edge", "width",
        "angle", "band", "precision", "angle-precision", "unmarked",
    ],
)
def test_native_relief_refuses_wrong_geometry_or_lost_controls(monkeypatch, defect):
    native = _native_relief_boundary(monkeypatch)
    if defect == "wrong-mouth":
        native.definition.Edges = [native.circle(native.radius, -native.face_z)]
    elif defect == "both-mouths":
        native.definition.Edges.append(native.circle(native.radius, -native.face_z))
    elif defect == "cone-leg":
        native.cone_edges[1] = native.circle(native.radius, native.face_z + 1.19)
    elif defect == "opposite-edge":
        native.land_edges[1] = native.circle(native.radius, -native.face_z - 0.25)
    elif defect == "width":
        native.definition.GetEdgeChamferDistance = lambda side: 0.0011
    elif defect == "angle":
        native.angle.SystemValue = math.radians(44.0)
    elif defect == "band":
        native.size.Tolerance.GetMinValue = lambda: -0.0002
    elif defect == "precision":
        native.display.GetPrimaryPrecision2 = lambda: 2
    elif defect == "angle-precision":
        native.angle_display.GetPrimaryPrecision2 = lambda: 1
    elif defect == "unmarked":
        native.display.MarkedForDrawing = False
    with pytest.raises(RuntimeError, match="cam-root relief"):
        rod._assert_cam_root_relief(native.adapter, marked=True)
    if defect in {"wrong-mouth", "both-mouths"}:
        assert native.released == [True]  # a failed rollback inspection restores it


@pytest.mark.parametrize(
    "defect",
    [
        None, "dangling", "detached", "wrong-feature",
        "angle-dangling", "angle-detached", "angle-wrong-feature",
        "wrong-angle-type", "duplicate-angle",
    ],
)
def test_relief_print_requires_both_scalar_drivers_attached_to_the_correct_feature(
    monkeypatch, defect,
):
    native = _native_relief_boundary(monkeypatch)
    annotations = [
        SimpleNamespace(
            GetSpecificAnnotation=lambda: native.display,
            IsDangling=lambda: defect == "dangling",
            GetAttachedEntities3=lambda: [] if defect == "detached" else [object()],
        ),
        SimpleNamespace(
            GetSpecificAnnotation=lambda: native.angle_display,
            IsDangling=lambda: defect == "angle-dangling",
            GetAttachedEntities3=lambda: [] if defect == "angle-detached" else [object()],
        ),
    ]
    if defect == "wrong-feature":
        native.size.FullName = "RootReliefSize@OtherChamfer@ch-connecting-rod"
    elif defect == "angle-wrong-feature":
        native.angle.FullName = "RootReliefAngle@OtherChamfer@ch-connecting-rod"
    elif defect == "wrong-angle-type":
        native.angle_display.Type2 = 2
    elif defect == "duplicate-angle":
        annotations.append(annotations[1])
    cut = SimpleNamespace(
        GetPartialSection=lambda: True, GetDisplayOnlySurfaceCut=lambda: True,
    )
    view = SimpleNamespace(
        GetSection=lambda: cut, GetDisplayMode2=lambda: 2,
        GetUseParentDisplayMode=lambda: False, ScaleRatio=(3.0, 1.0),
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda value, name: value)
    monkeypatch.setattr(
        drawing, "_root_section_frame", lambda *args: ((0.003, 0.0), (0.0, 0.003))
    )
    monkeypatch.setattr(
        drawing, "dimension_name",
        lambda adapter, annotation: annotation.GetSpecificAnnotation().GetDimension2(0).Name,
    )
    monkeypatch.setattr(drawing, "assert_imported_precision", lambda *args: None)
    if defect is None:
        drawing._assert_root_section(native.adapter, view, annotations)
    else:
        with pytest.raises(RuntimeError, match="strap section"):
            drawing._assert_root_section(native.adapter, view, annotations)


def test_relief_authoring_selects_only_the_negative_Z_strap_mouth(monkeypatch):
    import asyncio

    from solidworks_mcp.adapters.solidworks import features

    calls = []

    async def add_chamfer(distance, points, *, tangent_propagation):
        calls.append((distance, points, tangent_propagation))
        return object()

    native = _native_relief_boundary(monkeypatch)
    native.adapter.add_chamfer = add_chamfer
    monkeypatch.setattr(features, "_select_edges_geometric", lambda *args, **kwargs: True)
    monkeypatch.setattr(rod, "check", lambda label, result: result)
    monkeypatch.setattr(rod, "name_last_feature", lambda *args: None)
    monkeypatch.setattr(rod, "name_dimensions", lambda *args: [])
    asyncio.run(rod._cam_root_relief(native.adapter))
    assert calls == [(1.2, [[15.4, 0.0, -1.0875]], False)]


def _shift(box: Box, dx: float, dy: float) -> Box:
    return Box(box.xmin + dx, box.ymin + dy, box.xmax + dx, box.ymax + dy)


def _measured_root_section_boxes() -> tuple[Box, ...]:
    # Farm v13: distinguish the native view allocation from its smaller solid
    # profile. These actual extents must not be replaced by nominal geometry.
    return (
        Box(0.387949500048, 0.066411999952115, 0.4056504999520001, 0.101588000047885),
        Box(0.4089102675585283, 0.0758398127090302, 0.4541842809364547, 0.0920431438127091),
    )


def test_measured_section_and_caption_translate_together_without_shrinking() -> None:
    boxes = _measured_root_section_boxes()
    band = Box(0.219, 0.069, 0.4161, 0.109)
    dx, dy = drawing._root_section_shift(boxes, band)
    moved = tuple(_shift(box, dx, dy) for box in boxes)
    assert dx < 0.0  # The caption initially extends beyond the right border.
    for before, after in zip(boxes, moved, strict=True):
        assert (after.width, after.height) == pytest.approx((before.width, before.height))
        assert band.xmin <= after.xmin <= after.xmax <= band.xmax
        assert band.ymin <= after.ymin <= after.ymax <= band.ymax
    assert moved[1].xmin - moved[0].xmax == pytest.approx(boxes[1].xmin - boxes[0].xmax)
    assert moved[0].union(moved[1]).center()[1] == pytest.approx(band.center()[1])
    # Placement is sheet-frame independent, rather than tied to an import seed.
    offset = (0.123, -0.040)
    assert drawing._root_section_shift(
        tuple(_shift(box, *offset) for box in boxes), _shift(band, *offset),
    ) == pytest.approx((dx, dy))


@pytest.mark.parametrize(
    "band",
    [
        Box(0.219, 0.069, 0.4161, 0.099),  # v13's actual 35.176 mm allocation > 30 mm
        Box(0.219, 0.069, 0.280, 0.109),  # enough height, insufficient width
    ],
)
def test_measured_section_refuses_a_band_that_requires_clipping_or_shrinking(band) -> None:
    with pytest.raises(RuntimeError, match="do not fit"):
        drawing._root_section_shift(_measured_root_section_boxes(), band)


def test_partial_strap_section_spans_the_whole_wall_and_one_chamfer() -> None:
    spec = ch_connecting_rod_spec
    start, end = drawing.ROOT_SECTION_START, drawing.ROOT_SECTION_END
    wall = [
        drawing._sheet_xy(0.0, y)
        for y in (
            spec.RING_BOTTOM_Y,
            -spec.RING_BORE_DIA / 2.0 - spec.ROOT_RELIEF_SIZE,
            -spec.RING_BORE_DIA / 2.0,
        )
    ]
    assert all(point[0] == pytest.approx(start[0]) for point in (*wall, end))
    assert all(start[1] < point[1] < end[1] for point in wall)
    # The span stops in the bore; it does not add the opposite strap wall.
    assert end[1] < drawing._sheet_xy(0.0, spec.RING_BORE_DIA / 2.0)[1]


def test_scalar_dimension_lane_clears_the_other_dimensions_native_line() -> None:
    band = Box(0.300, 0.040, 0.420, 0.059)
    text = Box(0.0, 0.0, 0.030, 0.008)
    line = Segment(0.300, 0.051, 0.420, 0.051)
    target = drawing._root_text_target(text, band, (), (line,))
    assert target.ymin == pytest.approx(band.ymin)
    assert segment_box_distance(line, target) == pytest.approx(0.003)
    assert (target.width, target.height) == pytest.approx((text.width, text.height))
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._root_text_target(
            text, band, (), (Segment(0.300, 0.0509, 0.420, 0.0509),),
        )


def _assert_clear_lane(target: Box, text: Box, band: Box, obstacles: tuple[Box, ...]) -> None:
    assert (target.width, target.height) == pytest.approx((text.width, text.height))
    assert band.xmin - 1e-9 <= target.xmin and target.xmax <= band.xmax + 1e-9
    assert band.ymin - 1e-9 <= target.ymin and target.ymax <= band.ymax + 1e-9
    for obstacle in obstacles:
        assert target.overlaps(obstacle, tol=0.0) is None
        assert target.gap(obstacle) >= 0.003 - 1e-9


def test_root_callout_lane_clears_every_obstacle_anywhere_on_the_sheet() -> None:
    band = Box(0.300, 0.040, 0.420, 0.100)
    text = Box(0.355, 0.070, 0.385, 0.078)  # 30 x 8 mm, seated inside the view
    obstacles = (
        Box(0.330, 0.058, 0.390, 0.095),  # the section view
        Box(0.350, 0.046, 0.370, 0.052),  # its caption
        Box(0.378, 0.040, 0.420, 0.050),  # a note in the band's lower right
    )
    target = drawing._root_text_target(text, band, obstacles)
    _assert_clear_lane(target, text, band, obstacles)
    assert target.gap(text) > 0.0  # moved out of the view, not seated in place
    dx, dy = 0.1234, 0.0567
    moved = drawing._root_text_target(
        _shift(text, dx, dy), _shift(band, dx, dy),
        tuple(_shift(box, dx, dy) for box in obstacles),
    )
    expected = _shift(target, dx, dy)
    assert (moved.xmin, moved.ymin, moved.xmax, moved.ymax) == pytest.approx(
        (expected.xmin, expected.ymin, expected.xmax, expected.ymax)
    )


def test_root_callout_lane_takes_an_exactly_clear_strip_or_refuses() -> None:
    band = Box(0.300, 0.040, 0.420, 0.100)
    text = Box(0.0, 0.0, 0.030, 0.008)
    # The view leaves exactly 3 mm plus the text's 8 mm under it, and the
    # strip above it is too short for the text.
    fits = (Box(0.300, 0.051, 0.420, 0.095),)
    target = drawing._root_text_target(text, band, fits)
    _assert_clear_lane(target, text, band, fits)
    assert target.ymax == pytest.approx(fits[0].ymin - 0.003)
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._root_text_target(text, band, (Box(0.300, 0.0509, 0.420, 0.095),))
    with pytest.raises(RuntimeError, match="cannot fit"):
        drawing._root_text_target(Box(0.0, 0.0, 0.130, 0.008), band, ())


def _native_pin_hole(monkeypatch, *, seams=True):
    """Native PinHole faces as SolidWorks reports them: one cylinder per tine,
    each bounded by its two full mouths (and, when the kernel keeps one, a
    straight seam joining them)."""
    spec = ch_connecting_rod_spec
    radius, cy = spec.PIN_HOLE_DIA / 2.0, spec.CENTER_DISTANCE
    wall, outer = spec.FORK_SLOT_WIDTH / 2.0, spec.FORK_THICKNESS / 2.0

    def circle(r, z, *, cx=0.0, cy=cy, sweep=math.tau, sense=1.0):
        curve = SimpleNamespace(
            IsCircle=lambda: True,
            IsLine=lambda: False,
            CircleParams=(
                cx / 1000.0, cy / 1000.0, z / 1000.0, 0.0, 0.0, sense, r / 1000.0
            ),
        )
        start, end = (0.0, sweep) if sense > 0 else (-sweep, 0.0)
        return SimpleNamespace(
            GetCurve=lambda: curve,
            GetCurveParams2=lambda: (
                (cx + r) / 1000.0, cy / 1000.0, z / 1000.0,
                (cx + r) / 1000.0, cy / 1000.0, z / 1000.0,
                start, end, 0.0, 0.0, 0.0,
            ),
        )

    def seam(z0, z1, *, r=radius, cx=0.0):
        curve = SimpleNamespace(IsCircle=lambda: False, IsLine=lambda: True)
        return SimpleNamespace(
            GetCurve=lambda: curve,
            GetCurveParams2=lambda: (
                (cx + r) / 1000.0, cy / 1000.0, z0 / 1000.0,
                (cx + r) / 1000.0, cy / 1000.0, z1 / 1000.0,
                0.0, abs(z1 - z0) / 1000.0, 0.0, 0.0, 0.0,
            ),
        )

    def cylinder(edges, *, r=radius, cx=0.0, axis=(0.0, 0.0, 1.0)):
        return SimpleNamespace(
            GetEdges=lambda: edges,
            GetSurface=lambda: SimpleNamespace(
                IsCylinder=lambda: True,
                CylinderParams=(cx / 1000.0, cy / 1000.0, 0.0, *axis, r / 1000.0),
            ),
        )

    near = [circle(radius, -outer), circle(radius, -wall)]
    far = [circle(radius, wall), circle(radius, outer)]
    if seams:
        near.append(seam(-outer, -wall))
        far.append(seam(wall, outer))
    faces = [cylinder(near), cylinder(far)]
    features = {"PinHole": SimpleNamespace(GetFaces=lambda: faces)}
    monkeypatch.setattr(rod, "_early_bound", lambda value, name: value)
    monkeypatch.setattr(rod, "_feature_by_name", lambda adapter, name: features[name])
    return SimpleNamespace(
        adapter=object(), circle=circle, seam=seam, cylinder=cylinder,
        faces=faces, near=near, far=far, radius=radius, wall=wall, outer=outer,
    )


@pytest.mark.parametrize("topology", ["seams", "seamless", "reversed", "trimmed-face"])
def test_native_pin_hole_reads_two_full_tine_lands(monkeypatch, topology):
    native = _native_pin_hole(monkeypatch, seams=topology != "seamless")
    if topology == "reversed":
        # The kernel may run a mouth's curve against its edge (-Z axis, the
        # parameter span on the negative side) and a seam top-down.
        native.far[0] = native.circle(native.radius, native.wall, sense=-1.0)
        native.far[2] = native.seam(native.outer, native.wall)
        native.faces[1] = native.cylinder(native.far, axis=(0.0, 0.0, -1.0))
    elif topology == "trimmed-face":
        # A tine face the cut trimmed may be credited to the cut as well; the
        # two lands alone carry the proof.
        native.faces.append(
            SimpleNamespace(GetSurface=lambda: SimpleNamespace(IsCylinder=lambda: False))
        )
    rod._assert_pin_hole_lands(native.adapter)


@pytest.mark.parametrize(
    "defect",
    [
        "cylinder-radius", "mouth-radius", "shifted-axis", "tilted-axis",
        "shifted-mouth", "partial-mouth", "outer-break", "wall-relief",
        "one-tine", "duplicated-tine", "unsplit", "three-mouths",
        "crossing-boundary", "seam-off-surface", "seam-past-mouth",
    ],
)
def test_native_pin_hole_refuses_any_land_short_of_a_full_tine(monkeypatch, defect):
    spec = ch_connecting_rod_spec
    native = _native_pin_hole(monkeypatch)
    radius, wall, outer = native.radius, native.wall, native.outer
    if defect == "cylinder-radius":
        native.faces[1] = native.cylinder(native.far, r=radius + 0.005)
    elif defect == "mouth-radius":
        native.far[1] = native.circle(radius + 0.005, outer)
    elif defect == "shifted-axis":
        native.faces[0] = native.cylinder(native.near, cx=0.001)
    elif defect == "tilted-axis":
        native.faces[0] = native.cylinder(native.near, axis=(1e-6, 0.0, 1.0))
    elif defect == "shifted-mouth":
        native.near[0] = native.circle(radius, -outer, cx=0.001)
    elif defect == "partial-mouth":
        native.near[1] = native.circle(radius, -wall, sweep=math.pi)
    elif defect == "outer-break":
        # A finite mouth break moves the outer mouth inward: the land is no
        # longer the whole tine, however small the break.
        native.near[0] = native.circle(radius, -outer + spec.OPPOSITE_EDGE_BREAK_MAX)
    elif defect == "wall-relief":
        native.far[0] = native.circle(radius, wall + spec.ROOT_RELIEF_SIZE)
    elif defect == "one-tine":
        del native.faces[1]
    elif defect == "duplicated-tine":
        native.faces[1] = native.faces[0]
    elif defect == "unsplit":
        native.faces[:] = [
            native.cylinder([native.circle(radius, -outer), native.circle(radius, outer)])
        ]
    elif defect == "three-mouths":
        native.far.append(native.circle(radius, outer))
    elif defect == "crossing-boundary":
        curve = SimpleNamespace(IsCircle=lambda: False, IsLine=lambda: False)
        native.far.append(SimpleNamespace(GetCurve=lambda: curve))
    elif defect == "seam-off-surface":
        native.near[2] = native.seam(-outer, -wall, r=radius + 0.005)
    elif defect == "seam-past-mouth":
        native.near[2] = native.seam(-outer - 0.5, -wall)
    with pytest.raises(RuntimeError, match="pin hole"):
        rod._assert_pin_hole_lands(native.adapter)

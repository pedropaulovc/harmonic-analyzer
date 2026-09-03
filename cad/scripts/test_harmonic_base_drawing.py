"""Offline contracts for the harmonic-base drawing.

The print follows cad/docs/drawing-simplicity-policy.md: a machined base
carries no datums, frames or basic dimensions; the native hole table gives
every station under the title-block tolerance; both plate footprints, the two
plate thicknesses, the rim width and pocket depth, the reveal and the three
concentric plan-corner radii ride the views; the notes are four lines of
process fact that carry no feature dimension.
"""

from __future__ import annotations

import math
from pathlib import Path
import re

import pytest

import build_harmonic_base as part
import build_cone_swing_platform as platform
import draw_harmonic_base as drawing
import harmonic_base_spec
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from cone_lock_knob_spec import WASHER_DIA as KNOB_WASHER_DIA
from _drawing_registry import DRAWINGS_BY_NAME
from swing_stop_screw_spec import SHANK_DIA as STOP_SHANK_DIA


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/harmonic-base.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/harmonic-base.pdf")
    assert drawing.PNG.as_posix().endswith("/png/harmonic-base_drawing.png")
    assert DRAWINGS_BY_NAME["harmonic_base"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map.
    assert part.DRAWING_DIMENSIONS is harmonic_base_spec.DRAWING_DIMENSIONS
    assert set(harmonic_base_spec.DRAWING_DIMENSIONS) == {
        "BottomProfile",
        "TopProfile",
        "BottomPlate",
        "TopPlate",
    }
    marked = set().union(*harmonic_base_spec.DRAWING_DIMENSIONS.values())
    assert marked == {"BottomLen", "BottomWid", "TopLen", "TopWid", "FlangeT", "PadT"}
    kept = set(drawing.TOP_KEEP) | set(drawing.SIDE_KEEP)
    assert kept == marked
    assert set(drawing.TOP_KEEP) == {"BottomLen", "BottomWid", "TopLen", "TopWid"}
    assert set(drawing.SIDE_KEEP) == {"FlangeT", "PadT"}
    assert (drawing.BOTTOM_LENGTH, drawing.BOTTOM_WIDTH) == (
        harmonic_base_spec.BOTTOM_LENGTH,
        harmonic_base_spec.BOTTOM_WIDTH,
    )


def test_plate_thicknesses_are_renamed_depth_dimensions() -> None:
    # The thicknesses are extrude depths (auto "D1" on two features), renamed
    # in the build so the drawing's name-keyed keep map can tell them apart;
    # the rename picks the depth by VALUE and reads it back by name.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "def _name_depth_dimension(" in source
    assert (
        '_name_depth_dimension(adapter, "BottomPlate", "FlangeT", BOTTOM_THICKNESS)'
        in source
    )
    assert '_name_depth_dimension(adapter, "TopPlate", "PadT", TOP_THICKNESS)' in source
    assert "_named_dimension(adapter, feature_name, name)" in source
    assert "_dim_value_mm(dimension) - depth_mm" in source
    assert harmonic_base_spec.BOTTOM_THICKNESS == 12.7
    assert math.isclose(harmonic_base_spec.TOP_THICKNESS, 38.1)
    assert math.isclose(harmonic_base_spec.STACK_HEIGHT, 50.8)
    assert math.isclose(harmonic_base_spec.RIM_TOP, 53.3)
    assert harmonic_base_spec.LIP_H == 2.5
    assert harmonic_base_spec.LIP_W == 7.0
    assert math.isclose(harmonic_base_spec.REVEAL, 6.35)


def test_plate_geometry_is_single_sourced() -> None:
    # The build imports its plate nominals from the spec, so the drawing's view
    # math and the part geometry cannot drift.
    assert part.BOTTOM_LENGTH is harmonic_base_spec.BOTTOM_LENGTH
    assert part.TOP_THICKNESS is harmonic_base_spec.TOP_THICKNESS
    assert harmonic_base_spec.BOTTOM_LENGTH == 18.0 * 25.4
    assert harmonic_base_spec.TOP_LENGTH == 17.5 * 25.4
    assert harmonic_base_spec.BOTTOM_FRONT_Z == -(11.0 * 25.4) / 2.0
    assert harmonic_base_spec.BOTTOM_REAR_Z == (11.0 * 25.4) / 2.0
    assert math.isclose(harmonic_base_spec.BOTTOM_WIDTH, 11.0 * 25.4)
    assert math.isclose(harmonic_base_spec.TOP_WIDTH, 10.5 * 25.4)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count("bbox_extent_check(") == 2
    assert "measure_check(" not in source


_DIMENSION_NUMBER = re.compile(r"\d+\.\d{2,}")
# The all-round rim chamfer and the pad root fillet cannot be drawn on a 1:4
# elevation (0.4 mm on paper) and exceed the title block's 0.25 edge break,
# so they stay as a general note -- the only sizes the notes carry.
_NOTE_SIZE_ALLOWLIST = ("1/16 X 45 DEG", "R0.50")


def test_notes_are_few_specific_and_never_a_dimension() -> None:
    notes = harmonic_base_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert all(len(line) <= 95 for line in lines)
    # Which faces are machined (Harvey #34), how the deck is made, which side
    # each hole opens from, and what to mask: facts the views cannot show.
    assert "ALL FACES MACHINED" in notes
    assert "NO DRAFT" in notes
    assert "CENTRED ON THE FLANGE" in notes
    assert "POCKET MILLED INSIDE THE RIM" in notes
    assert "BLACK ENAMEL" in notes
    assert "C'BORED FROM UNDERSIDE" in notes
    assert "BLIND TAPPED" in notes
    assert "MASK" in notes
    stripped = notes
    for allowed in _NOTE_SIZE_ALLOWLIST:
        assert allowed in notes, allowed
        stripped = stripped.replace(allowed, "")
    # Rule 6: every plate size, height, reveal, rim width, corner radius and
    # station rides the views now.
    assert _DIMENSION_NUMBER.findall(stripped) == []
    for banned in (
        "12.70",
        "50.80",
        "53.30",
        "444.50",
        "266.70",
        "6.35",
        "7.00",
        "2.50",
        "R22",
        "R15",
        "R8",
        "GRAY IRON",
        "ASTM A48",
        "GREEN ENAMEL",
        "DEBURR",
        "UOS",
        "+/-",
        "DATUM",
        "BASIC",
        "LEAST-SQUARES",
        "MAX",
        "X.XX",
    ):
        assert banned not in notes, banned
    source = _source()
    assert 'adapter, "Manufacturing Notes", 0.016, 0.075, char_height=0.0025' in source
    assert drawing.SIDE_VIEW_NOTE_XY == (0.260, 0.098)
    assert 'add_property_linked_note(adapter, "Side View Note", *SIDE_VIEW_NOTE_XY)' in source


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3-4: a base is not on the GD&T
    # allowlist; the hole table's LOC columns are ordinary, not basic.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert "_visible_side_datum_edges(" not in source
    assert "basic_locations=False" in source
    assert not hasattr(harmonic_base_spec, "GEOMETRIC_TOLERANCES_MM")


def test_hole_table_is_native_and_anchored_on_the_virtual_corner() -> None:
    source = _source()
    assert "insert_hole_table(" in source
    assert "_visible_hole_table_entities(" in source
    assert "datum_axes=(rear_edge, left_edge)" in source
    assert "hole_entities=hole_entities" in source
    assert "expected_locations_mm=tuple(" in source
    assert re.search(r"GetVisibleEntities2\(\s*c,\s*1\s*\)", source)
    assert not re.search(r"GetVisibleEntities2\(\s*c,\s*2\s*\)", source)
    # Hidden lines are shown in the plan, so underside counterbore rims are
    # reported legitimately: a debug fact, never a hard failure.
    assert "counterbore rims reported in the plan view" in source
    assert "underside-only counterbore rims are visible" not in source
    assert 'redundant_note_substrings=("Tapped Hole",)' in source
    assert "expected_redundant_notes=5" in source


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = _source()
    assert "for view in (top, side):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(" not in source


def test_hole_table_covers_mounting_holes_and_every_hardware_seat() -> None:
    assert len(part.HOLE_XZ) == 4
    # 4 lag c'bores + pivot + stop + 4 block + 3 foot + 4 nameplate seats
    assert len(drawing.ALL_HOLES) == 17
    assert drawing.ALL_HOLES[:4] == tuple(
        (x, z, part.HOLE_DIA) for x, z in part.HOLE_XZ
    )
    # Pass 3 appended the nameplate screw seats LAST in ALL_HOLES.
    assert drawing.ALL_HOLES[13:] == tuple(
        (x, z, part.NAMEPLATE_SCREW_HOLE_DIA) for x, z in part.NAMEPLATE_SCREW_XZ
    )
    source = _source()
    assert '"*Front"' in source
    assert len(drawing.TOP_KEEP) == 4
    assert drawing._plan_xy(0.0, 10.0)[1] < drawing.TOP_CENTER[1]
    assert drawing.HOLE_TABLE_ANCHOR[0] >= 0.274


def test_plan_view_clears_top_border_and_lower_notes() -> None:
    assert drawing.TOP_CENTER == (0.130, 0.163)
    # Pad outline nearest the plate, flange envelope outside it; the two
    # vertical dimensions' horizontal texts sit at different heights.
    assert drawing.TOP_KEEP["TopLen"] == (0.130, 0.2428)
    assert drawing.TOP_KEEP["BottomLen"] == (0.130, 0.2518)
    assert drawing.TOP_KEEP["TopWid"] == (0.2513, 0.150)
    assert drawing.TOP_KEEP["BottomWid"] == (0.2643, 0.178)
    assert drawing.TOP_KEEP["BottomWid"][0] < drawing.HOLE_TABLE_ANCHOR[0]


def test_rim_reveal_heights_and_radii_are_drawing_annotations() -> None:
    # The visible entities remain topologically dimensioned.  The hidden deck
    # edge is unreliable in the derived elevation, so its depth is stated
    # beside that view directly from the shared spec.
    source = _source()
    for label in (
        'label="rim width"',
        'label="flange corner radius"',
        'label="pad corner radius"',
        'label="rim inner corner radius"',
        'label="overall height reference"',
        'label="pad reveal reference"',
    ):
        assert label in source, label
    assert source.count("_dimension_entities(") == 7  # definition + 6 calls
    assert source.count("_reference(adapter, ") == 2
    assert drawing.DECK_DEPTH_NOTE == (
        f"DECK {harmonic_base_spec.RIM_TOP - harmonic_base_spec.STACK_HEIGHT:.2f} "
        "BELOW RIM TOP"
    )
    assert "add_note(adapter, DECK_DEPTH_NOTE, *DECK_DEPTH_NOTE_XY)" in source
    assert 'label="deck edge"' not in source
    assert "(deck, rim_top)" not in source
    assert "set_reference_dimension(" in source
    assert "SelectByID2" not in source
    assert "view.SelectEntity(entity, index > 0)" in source
    # The three corner arcs are concentric, so each radius text sits in its
    # own quadrant at a distinct angle: flange NE, pad and rim inner SE.
    assert math.isclose(drawing.CORNER_CENTER_X, 206.375)
    assert math.isclose(drawing.CORNER_CENTER_Z, 117.475)
    assert drawing.FLANGE_RADIUS_TEXT_XY == (0.2555, 0.2270)
    assert drawing.PAD_RADIUS_TEXT_XY == (0.2555, 0.0880)
    assert drawing.RIM_RADIUS_TEXT_XY == (0.2470, 0.0790)
    # Rim width and reveal chained on one line above the plan's NE corner.
    assert drawing.RIM_WIDTH_TEXT_XY == (0.229, 0.2360)
    assert drawing.REVEAL_TEXT_XY == (0.2515, 0.2360)
    assert drawing.OVERALL_TEXT_XY == (0.264, 0.0745)
    assert drawing.DECK_DEPTH_NOTE_XY == (
        drawing.SIDE_CENTER[0],
        drawing.SIDE_VIEW_NOTE_XY[1],
    )
    # No pick relies on a tangent edge: the reveal reads off the chamfers'
    # lower edges in the plan, not the end faces' fillet boundaries.
    assert 'label="flange right edge"' in source
    assert "flange left end" not in source
    # Elevation thickness stack on the left, thinnest nearest the view.
    assert drawing.SIDE_KEEP["FlangeT"][0] == 0.280
    assert drawing.SIDE_KEEP["PadT"][0] == 0.272
    assert abs(drawing.SIDE_KEEP["FlangeT"][1] - 0.069925) < 1e-9
    assert abs(drawing.SIDE_KEEP["PadT"][1] - 0.0790375) < 1e-9
    assert drawing.SIDE_BBOX_MID_Y == 26.65
    assert abs(drawing._side_xy(0.0, 0.0)[1] - 0.0683375) < 1e-9


def test_blind_taps_have_drill_and_tap_runout_clearance() -> None:
    for spec in (
        part.STOP_SEAT_SPEC,
        part.BLOCK_SEAT_SPEC,
        part.FOOT_SEAT_SPEC,
        part.NAMEPLATE_SEAT_SPEC,
    ):
        thread_depth = spec.overrides_mm["ThreadDepth"]
        assert spec.depth_mm - thread_depth >= 3.0


def test_nameplate_seats_are_derived_from_the_plate_mount() -> None:
    """The four #4-40 taps sit under the plate's corner holes carried through
    its mount transform (nameplate_spec), cut from the deck the plate lies on."""
    import nameplate_spec
    from fillister_screw_spec import SHANK_DIA, SHANK_LEN, THREAD

    assert part.NAMEPLATE_SEAT_SPEC.kind == "tapped"
    assert part.NAMEPLATE_SEAT_SPEC.size == THREAD == "#4-40"
    assert part.NAMEPLATE_SEAT_SPEC.end == "blind"
    assert part.NAMEPLATE_SCREW_HOLE_DIA == pytest.approx(2.261)
    # Ø2.0 modelled shank inside the Ø2.261 tap drill (foot-screw convention):
    # no interference pair to allow.
    assert SHANK_DIA < part.NAMEPLATE_SCREW_HOLE_DIA
    # Plate back face ON the deck (gap 0) and cut from the deck's +Y face.
    assert nameplate_spec.MOUNT_BACK_Y == pytest.approx(harmonic_base_spec.STACK_HEIGHT)
    assert nameplate_spec.MOUNT_NORMAL == (0.0, 1.0, 0.0)
    assert part.NAMEPLATE_SCREW_XZ == nameplate_spec.MOUNT_HOLE_XZ
    assert set(part.NAMEPLATE_SCREW_XZ) == {
        (209.75, 45.5), (209.75, -45.5), (163.75, 45.5), (163.75, -45.5),
    }
    # No mechanism shift applies (the plate anchors to the pad edge): the
    # stations are the pure mount-transform image of the plate holes.
    assert part.NAMEPLATE_SCREW_XZ == tuple(
        (nameplate_spec.MOUNT_POS[0] - y, nameplate_spec.MOUNT_POS[2] - x)
        for x, y in nameplate_spec.SCREW_XY
    )
    # Inside the raised rim's inner wall by >= 1.0.
    assert part.NAMEPLATE_RIM_CLEARANCE == pytest.approx(1.0)
    # Shank engagement: 4.0 shank through the 1.5 plate buries 2.5 in a 6.0
    # thread, with >= 0.5 spare before the thread bottom.
    plate_t = nameplate_spec.PLATE_THICKNESS
    assert SHANK_LEN >= plate_t + 2.0
    assert part.NAMEPLATE_SCREW_HOLE_DEPTH >= SHANK_LEN - plate_t + 0.5


def test_v2_platform_swing_stop_coordinate_is_rederived() -> None:
    """Mirror the drive-train formula without importing its COM-heavy graph."""
    pivot_x, pivot_z = part.PIVOT_SCREW_XZ
    assert part.PIVOT_SCREW_XZ == (
        -89.16663981674521 + POST_X_SHIFT,
        60.60437088764276 + POST_Z_SHIFT,
    )
    assert part.STOP_SCREW_XZ == (
        -141.14905420183916 + POST_X_SHIFT,
        -33.08089452405298 + POST_Z_SHIFT,
    )
    east_slope = (platform.EAST_HALF_S - platform.HALF_WIDTH_N) / platform.PLATE_LEN
    stop_local_z = -105.0
    stop_local_x = -(
        platform.HALF_WIDTH_N + east_slope * (platform.NORTH_OVERHANG - stop_local_z)
    )

    edge_x, edge_z = -1.0, east_slope
    edge_norm = math.hypot(edge_x, edge_z)
    edge_x, edge_z = edge_x / edge_norm, edge_z / edge_norm
    disengage_rad = (
        platform.NOTCH_EXIT_TRAVEL + KNOB_WASHER_DIA / 2.0 + 2.0
    ) / platform.SLOT_R
    angle = math.radians(platform.INCLINE_DEG) + disengage_rad
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    contact_x = pivot_x + stop_local_x * cos_a + stop_local_z * sin_a
    contact_z = pivot_z - stop_local_x * sin_a + stop_local_z * cos_a
    normal_x = edge_x * cos_a + edge_z * sin_a
    normal_z = -edge_x * sin_a + edge_z * cos_a
    derived = (
        contact_x + normal_x * STOP_SHANK_DIA / 2.0,
        contact_z + normal_z * STOP_SHANK_DIA / 2.0,
    )

    assert math.isclose(platform.NOTCH_EXIT_TRAVEL, 4.097712434428717)
    assert math.isclose(math.degrees(disengage_rad), 4.883134225775778)
    assert math.isclose(derived[0], part.STOP_SCREW_XZ[0], abs_tol=1e-12)
    assert math.isclose(derived[1], part.STOP_SCREW_XZ[1], abs_tol=1e-12)

    engaged = math.radians(platform.INCLINE_DEG)
    cos_e, sin_e = math.cos(engaged), math.sin(engaged)
    edge_point_x = pivot_x + stop_local_x * cos_e + stop_local_z * sin_e
    edge_point_z = pivot_z - stop_local_x * sin_e + stop_local_z * cos_e
    engaged_normal = (
        edge_x * cos_e + edge_z * sin_e,
        -edge_x * sin_e + edge_z * cos_e,
    )
    stop_delta = (
        derived[0] - edge_point_x,
        derived[1] - edge_point_z,
    )
    engaged_gap = (
        stop_delta[0] * engaged_normal[0]
        + stop_delta[1] * engaged_normal[1]
        - STOP_SHANK_DIA / 2.0
    )
    assert engaged_gap >= 2.0
    assert math.isclose(engaged_gap, 8.92856567081106)


def test_v2_structural_holes_follow_the_same_installation_delta() -> None:
    # 2026-09 short-strap pinion rig: blocks at machine x -5.863 +/- 13.5,
    # spring foot screw at 7.486 (build_drive_train_assembly derives both).
    former_blocks = (
        (-13.669764612476252, -98.0),
        (13.33023538752375, -98.0),
        (-13.669764612476252, 82.0),
        (13.33023538752375, 82.0),
    )
    former_feet = (
        (13.179270253802283, 70.95),
        (-54.7, -95.5),
        (-54.7, 102.5),
    )
    assert part.BLOCK_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_blocks
    )
    assert part.FOOT_SCREW_XZ == tuple(
        (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in former_feet
    )


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("harmonic-base")
    assert config["material"] == config["material_specification"]
    assert "gray cast iron" in str(config["material_specification"]).lower()
    finish = str(config["finish"]).lower()
    assert "sspc-sp3" in finish
    assert "alkyd primer 25-40um" in finish
    assert "ral6000 alkyd enamel 50-85um" in finish
    assert "75-125um total dft" in finish
    assert "mask" not in finish
    assert config["process"] == "machined from solid stock"
    assert int(config["quantity"]) == 1

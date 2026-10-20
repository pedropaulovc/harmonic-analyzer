"""Offline contracts for the rocker template trammel scriber block (MHA-CH-06-TL-15)."""

from __future__ import annotations

import inspect
import re

import _config
import ch_rocker_arm_tl_trammel_pivot_block_spec as block
import ch_rocker_arm_tl_trammel_scriber_block_spec as spec
import ch_rocker_arm_tl_trammel_spec as kit
import draw_ch_rocker_arm_tl_trammel_scriber_block as drawing
import export_features
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_trammel_scriber_block"
_KEEPS = (drawing.TOP_KEEP, drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.BACK_KEEP)


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*_KEEPS) == marked
    assert sum(len(keep) for keep in _KEEPS) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_pinch_tap_leader_starts_at_edge_a_rightmost_tap() -> None:
    """Farm r2: the leader from the L25 tap crossed the set-screw callout's
    text, whose right end sat at sheet x 390.2 mm; the pivot block's tap at
    391 mm cleared it. The pinned outer tap stands beyond both."""
    import draw_ch_rocker_arm_tl_trammel_pivot_block as pivot_drawing

    def sheet_x(sheet, x: float) -> float:
        return sheet.back(x, -block.PINCH_DEPTH)[0]

    leader_x = sheet_x(drawing.SHEET, drawing.PINCH_TAP_LEADER_X)
    assert drawing.PINCH_TAP_LEADER_X in spec.PINCH_X
    assert leader_x == max(sheet_x(drawing.SHEET, x) for x in spec.PINCH_X)
    assert leader_x > sheet_x(pivot_drawing.SHEET, block.PINCH_X[0]) > 0.3902
    assert drawing.PINCH_TAP_CALLOUT_XY == pivot_drawing.PINCH_TAP_CALLOUT_XY
    assert drawing.SET_SCREW_CALLOUT_XY == pivot_drawing.SET_SCREW_CALLOUT_XY
    assert "center_x_mm=PINCH_TAP_LEADER_X" in inspect.getsource(drawing.build)


def test_shares_the_pivot_block_section() -> None:
    """Only the holes, slit end and screw stations differ from the pivot block."""
    for feature in (
        "BlockProfile",
        "Block",
        "SlotProfile",
        "SlitProfile",
        "SlitReliefProfile",
        "SetScrewTaps",
    ):
        assert spec.DRAWING_DIMENSIONS[feature] == block.DRAWING_DIMENSIONS[feature]
        assert spec.DRAWING_PRECISION[feature] == block.DRAWING_PRECISION[feature]


def test_every_view_including_the_section_and_isometric_hides_hidden_lines() -> None:
    assert "for view in (top, front, right, back, section, iso):" in inspect.getsource(
        drawing.build
    )


def test_section_cuts_the_far_pinch_screw_axis() -> None:
    """Farm r4: cut at the near pinch, the section letters landed on the
    inner point-hole axis's extension lines."""
    source = inspect.getsource(drawing.build)
    assert "create_pinch_section(" in source
    assert "part_spec.PINCH_X[1]," in source
    assert spec.HOLE_X[0] < spec.PINCH_X[1] < spec.HOLE_X[1]


def test_pinch_stations_print_on_staggered_rows() -> None:
    """Farm r4: on one row each value sat inside the other's arrows."""
    assert drawing.FRONT_KEEP["PinchX1"][1] != drawing.FRONT_KEEP["PinchX2"][1]


def test_spacing_value_and_callout_stand_outside_its_extension_lines() -> None:
    """Farm r4: centred between the holes, the checked-on callout straddled
    both extension lines and the slit end's row."""
    spacing_x = drawing.TOP_KEEP["ScriberSpacing"][0]
    inner_x = drawing.SHEET.top(spec.HOLE_X[0], 0.0)[0]
    assert spacing_x < inner_x
    # The shorter row nearer the view (rows stack by span).
    assert drawing.TOP_KEEP["ScriberSpacing"][1] > drawing.TOP_KEEP["SlitEnd"][1]


def test_above_lane_callouts_are_single_lines() -> None:
    for text in drawing.CALLOUTS_ABOVE.values():
        assert "\n" not in text
    assert drawing.CALLOUTS_ABOVE == {"SlotWidth": block.SLOT_WIDTH_CALLOUT}
    assert "SlotDepth" not in drawing.CALLOUTS_BELOW
    for text in (*drawing.CALLOUTS_ABOVE.values(), *drawing.CALLOUTS_BELOW.values()):
        assert all(len(line) <= 33 for line in text.splitlines()), text


def test_tap_callouts_drop_the_title_block_thread_class() -> None:
    assert inspect.getsource(drawing.build).count("strip_thread_class(") == 2


def test_bar_contact_faces_carry_the_pivot_block_finishes() -> None:
    assert spec.SURFACE_FINISHES == block.SURFACE_FINISHES
    source = inspect.getsource(drawing.build)
    for finish in spec.SURFACE_FINISHES:
        assert f'surface_finish_by_key(SURFACE_FINISHES, "{finish.key}")' in source
    assert "text=block.SLOT_CORNER_CALLOUT," in source


def test_point_holes_are_the_reamed_fit_named_on_the_scriber_points() -> None:
    features = _features()
    for name in ("point_hole_inner", "point_hole_outer"):
        assert features[name]["dia"] == [6.375, 6.388]
    assert "MHA-CH-06-TL-16" in features["point_hole_inner"]["note"]
    assert spec.POINT_HOLE_CALLOUT.startswith("2X ")
    assert "MHA-CH-06-TL-16" in spec.POINT_HOLE_CALLOUT


def test_spacing_is_the_kit_band_and_names_its_check() -> None:
    outer = _features()["point_hole_outer"]
    # The spacing is the outer hole's station from the inner hole's axis.
    assert outer["station"] == [15.975, 16.025]
    assert "MHA-CH-06-TL-17" in outer["note"]
    assert "MHA-CH-06-TL-17" in spec.SCRIBER_SPACING_CALLOUT
    assert kit.TEMPLATE_RADII[1] - kit.TEMPLATE_RADII[0] == spec.SCRIBER_SPACING


def test_stations_agree_with_the_kit() -> None:
    assert [x + spec.HOLE_FROM_END for x in spec.HOLE_X] == list(kit.SCRIBER_HOLE_L)
    assert [x + spec.HOLE_FROM_END for x in spec.SET_SCREW_X] == list(kit.SET_SCREW_L)
    assert (
        spec.BLOCK_X0
        < spec.PINCH_X[0]
        < spec.HOLE_X[0]
        < spec.PINCH_X[1]
        < spec.HOLE_X[1]
    )
    assert spec.HOLE_X[1] < spec.SLIT_END_X < spec.BLOCK_X1


def test_slit_ends_in_the_pivot_block_relief() -> None:
    relief = _features()["slit_relief"]
    assert relief["dia"] == [3.0, 3.1]
    assert relief["station"] == [24.2, 25.8]
    assert drawing.CALLOUTS_BELOW["SlitReliefDia"] == block.SLIT_RELIEF_CALLOUT
    assert drawing.CALLOUTS_BELOW["BlockHeight"] == block.BLOCK_HEIGHT_CALLOUT


def test_the_outer_point_lands_in_the_h816_pilot() -> None:
    assert spec.H816_LATERAL_MISS < kit.CENTER_DRILL_PILOT_DIA / 2.0


def test_walls_and_threads_hold_at_the_worst_case() -> None:
    """Rules 17 and 18 at the printed bands; rule 20 names every wall
    between the 1.5 floor and the 2.0 target."""
    assert min(spec.WORST_WALLS.values()) >= block.WALL_FLOOR
    assert set(spec.RULE_20_SHORTFALLS) == {
        "pinch thread to slot floor",
        "pinch clearance to block bottom",
        "pinch thread to block bottom",
        "pinch clearance to point hole",
        "pinch thread to point hole",
    }
    assert block.PINCH_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[block.PINCH_THREAD]
    assert block.SET_SCREW_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[block.SET_SCREW_SIZE]


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-scriber-block")["number"]
    assert number == f"{parent}-TL-15"
    assert re.fullmatch(re.escape(parent) + r"-TL-\d{2}", number)


def test_notes_follow_the_simplicity_policy() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert not re.search(
        r"GROUND|LAPP|GRIND|DRILL|REAM|MILL|SAW", spec.DRAWING_NOTES.upper()
    )


def test_every_exported_band_endpoint_is_a_printed_value() -> None:
    """A band applied to an unrounded model nominal exports limits the sheet
    never prints."""
    checked = 0
    for name, feature in _features().items():
        for requirement in feature["requirements"]:
            band = feature.get(requirement)
            if not (isinstance(band, list) and len(band) == 2):
                continue
            places = feature["precision"][requirement]
            for end in band:
                assert abs(end - round(end, places)) < 1e-9, (
                    name,
                    requirement,
                    band,
                    places,
                )
            nominal = feature.get(f"{requirement}_nominal")
            if nominal is not None:
                assert band[0] <= nominal <= band[1], (name, requirement, nominal, band)
                assert abs(nominal - round(nominal, places)) < 1e-9, (
                    name,
                    requirement,
                    nominal,
                )
            checked += 1
    assert checked

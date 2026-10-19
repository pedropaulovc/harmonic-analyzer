"""Offline contracts for the rocker template trammel pivot block (MHA-CH-06-TL-14)."""

from __future__ import annotations

import inspect
import re

import _config
import _trammel_block
import _trammel_block_drawing
import ch_rocker_arm_tl_trammel_pivot_block_spec as spec
import ch_rocker_arm_tl_trammel_spec as kit
import draw_ch_rocker_arm_tl_trammel_pivot_block as drawing
import export_features
from _hole_spec import THREAD_MAJOR_MM

STEM = "ch_rocker_arm_tl_trammel_pivot_block"
_KEEPS = (drawing.TOP_KEEP, drawing.FRONT_KEEP, drawing.RIGHT_KEEP, drawing.BACK_KEEP)


def _features() -> dict:
    return export_features.requirement_manifest(STEM)["features"]


def test_every_marked_dimension_prints_once_at_its_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set().union(*_KEEPS) == marked
    assert sum(len(keep) for keep in _KEEPS) == len(marked)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert set(drawing.CALLOUTS_ABOVE) | set(drawing.CALLOUTS_BELOW) <= marked


def test_every_view_including_the_section_and_isometric_hides_hidden_lines() -> None:
    assert "for view in (top, front, right, back, section, iso):" in inspect.getsource(
        drawing.build
    )


def test_section_cuts_the_pinch_screw_axis() -> None:
    """Review r1: the clearance, the slit and the tapped jaw read together."""
    source = inspect.getsource(drawing.build)
    assert "create_pinch_section(" in source
    assert "part_spec.PINCH_X[0]," in source
    assert spec.BLOCK_X0 < spec.PINCH_X[0] < spec.BLOCK_X1


def test_above_lane_callouts_are_single_lines_and_slot_names_its_bar() -> None:
    for text in drawing.CALLOUTS_ABOVE.values():
        assert "\n" not in text
    assert drawing.CALLOUTS_ABOVE == {"SlotWidth": spec.SLOT_WIDTH_CALLOUT}
    assert "SlotDepth" not in drawing.CALLOUTS_BELOW
    for text in (*drawing.CALLOUTS_ABOVE.values(), *drawing.CALLOUTS_BELOW.values()):
        assert all(len(line) <= 33 for line in text.splitlines()), text


def test_tap_callouts_drop_the_title_block_thread_class() -> None:
    source = inspect.getsource(drawing.build)
    assert source.count("strip_thread_class(") == 2


def test_bar_contact_faces_carry_the_part_owned_finish() -> None:
    keys = {finish.key for finish in spec.SURFACE_FINISHES}
    assert keys == {"slot_floor", "slot_datum_wall"}
    source = inspect.getsource(drawing.build)
    for key in keys:
        assert f'surface_finish_by_key(SURFACE_FINISHES, "{key}")' in source
    assert (
        "author_part_pmi(adapter, surface_finishes=part.SURFACE_FINISHES)"
        in inspect.getsource(_trammel_block)
    )


def test_floor_corner_cap_rides_a_leader_on_the_section() -> None:
    source = inspect.getsource(drawing.build)
    assert "text=part_spec.SLOT_CORNER_CALLOUT," in source
    assert "entity=straight_edge(" in source


def test_thread_class_strip_keeps_every_hole_wizard_variable() -> None:
    native = {
        5: "",
        6: "<MOD-DIAM><hw-diameter> THRU",
        7: "#25 DRILL, THEN TAP <hw-thread> - <hw-threadclass> THRU",
        8: "",
    }
    updated = _trammel_block_drawing.thread_class_free_definitions(native)
    assert updated[7] == "#25 DRILL, THEN TAP <hw-thread> THRU"
    assert {part: updated[part] for part in (5, 6, 8)} == {
        part: native[part] for part in (5, 6, 8)
    }


def test_point_hole_is_the_reamed_fit_named_on_the_pivot_point() -> None:
    hole = _features()["point_hole"]
    assert hole["dia"] == [6.375, 6.388]
    assert "MHA-CH-06-TL-18" in hole["note"]
    assert "MHA-CH-06-TL-18" in spec.POINT_HOLE_CALLOUT
    # The shop's 0.251 in reamer (tools.reamers), three places.
    assert spec.POINT_HOLE_DIA == round(0.251 * kit.INCH, 3)
    assert spec.POINT_CLEARANCE_MIN > 0.0


def test_bar_slot_band_passes_the_bar_and_names_it() -> None:
    slot = _features()["bar_slot"]
    assert slot["width"] == [6.45, 6.5]
    assert slot["depth"] == [8.99, 10.01]
    assert spec.SLOT_CLEARANCE_MIN > 0.0
    assert "TRAMMEL BAR" in spec.SLOT_WIDTH_CALLOUT
    assert spec.SLOT_CORNER_CALLOUT.endswith("MAX")


def test_stations_agree_with_the_kit() -> None:
    assert spec.HOLE_FROM_END == kit.PIVOT_HOLE_L
    assert [x + spec.HOLE_FROM_END for x in spec.SET_SCREW_X] == list(kit.SET_SCREW_L)
    assert spec.SET_SCREW_DEPTH == -kit.SET_SCREW_Z
    assert (spec.SLOT_WIDTH, spec.SLOT_FROM_EDGE_A, spec.SLOT_DEPTH) == (
        kit.SLOT_WIDTH,
        kit.SLOT_FROM_EDGE_A,
        kit.SLOT_DEPTH,
    )
    assert spec.POINT_FROM_EDGE_A == kit.POINT_FROM_EDGE_A
    assert spec.BLOCK_X0 < spec.PINCH_X[0] < 0.0 < spec.SLIT_END_X < spec.BLOCK_X1


def test_slit_ends_in_a_drilled_relief_one_line_callout() -> None:
    """Round 5: the hacksaw cut runs into a drilled hole, located by the slit
    end's station alone; its callout is one line."""
    relief = _features()["slit_relief"]
    assert relief["dia"] == [3.0, 3.1]
    assert relief["station"] == [7.2, 8.8]
    assert spec.SLIT_WIDTH < spec.SLIT_RELIEF_DIA
    assert drawing.CALLOUTS_BELOW["SlitReliefDia"] == spec.SLIT_RELIEF_CALLOUT
    assert "\n" not in spec.SLIT_RELIEF_CALLOUT
    assert spec.DRAWING_DIMENSIONS["SlitReliefProfile"] == {"SlitEnd", "SlitReliefDia"}
    # The slit's end and its distance from edge A ride equations
    # (one SlitEnd and one 28.0 print).
    assert spec.DRAWING_DIMENSIONS["SlitProfile"] == {"SlitWidth"}
    source = inspect.getsource(_trammel_block.build_block)
    assert '"SlitEnd@SlitReliefProfile"' in source
    assert source.count('"PointFromEdgeA@PointHoleProfile"') == 2


def test_stock_height_reads_stock() -> None:
    assert drawing.CALLOUTS_BELOW["BlockHeight"] == spec.BLOCK_HEIGHT_CALLOUT == "STOCK"


def test_walls_and_threads_hold_at_the_worst_case() -> None:
    """Rules 17 and 18 at the printed bands; rule 20 names every wall
    between the 1.5 floor and the 2.0 target."""
    assert min(spec.WORST_WALLS.values()) >= spec.WALL_FLOOR
    assert set(spec.RULE_20_SHORTFALLS) == {
        "pinch thread to slot floor",
        "pinch clearance to block bottom",
        "pinch thread to block bottom",
    }
    assert spec.PINCH_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[spec.PINCH_THREAD]
    assert spec.SET_SCREW_FULL_THREAD >= 1.5 * THREAD_MAJOR_MM[spec.SET_SCREW_SIZE]
    assert spec.SET_SCREW_REACH_GAP < kit.SET_SCREW_LENGTH


def test_number_is_the_parent_number_plus_a_tool_suffix() -> None:
    parent = _config.parts("ch-rocker-arm")["number"]
    number = _config.parts("ch-rocker-arm-tl-trammel-pivot-block")["number"]
    assert number == f"{parent}-TL-14"
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

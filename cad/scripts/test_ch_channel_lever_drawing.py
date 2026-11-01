"""Offline contracts for the channel-lever drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_ch_channel_assembly as assembly
import build_ch_channel_lever as lever
import ch_amplitude_bar_spec
import ch_channel_lever_notes as notes
import ch_channel_lever_spec as spec
import draw_ch_channel_lever as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_deviations


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/ch-channel-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/ch-channel-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/ch-channel-lever_drawing.png")
    assert DRAWINGS_BY_NAME["ch_channel_lever"].script == Path(drawing.__file__).resolve()


def test_kept_dimensions_are_exactly_the_marked_set() -> None:
    assert lever.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.FRONT_KEEP).isdisjoint(drawing.TOP_KEEP)


def test_every_marked_dimension_states_its_places() -> None:
    assert lever.DRAWING_PRECISION is notes.DRAWING_PRECISION
    assert set(notes.DRAWING_PRECISION) == set(notes.DRAWING_DIMENSIONS)
    for feature, names in notes.DRAWING_DIMENSIONS.items():
        assert set(notes.DRAWING_PRECISION[feature]) == names


def test_drawing_is_precision_migrated() -> None:
    assert "draw_ch_channel_lever.py" in PRECISION_MIGRATED_DRAWINGS


def test_bands_are_native_on_the_model_from_named_constants() -> None:
    assert model_toleranced_dimensions(lever) == {
        ("FulcrumProfile", "FulcrumDia"): "*deviations(PIVOT_HOLE_BAND)",
        ("Hub", "HubLength"): "*deviations(HUB_LENGTH_BAND)",
        ("LeverBody", "LeverThick"): "LEVER_THICKNESS_TOLERANCE",
        ("PlateOffsetReference", "PlateOffset"): "PLATE_OFFSET_TOLERANCE",
        ("BarPinHole", "BarPinCx"): "BAR_PIN_X_TOLERANCE",
        ("SpringHole", "SpringCx"): "LEVER_SPRING_X_TOLERANCE",
    }


def test_every_tight_band_names_its_mate_or_function() -> None:
    callouts = {**drawing.FRONT_CALLOUTS, **drawing.TOP_CALLOUTS}
    for name in (
        "FulcrumDia",
        "LeverThick",
        "PlateOffset",
        "HubLength",
        "BarPinCx",
        "SpringCx",
    ):
        assert callouts[name]
    assert drawing.SHAFT_NUMBER in callouts["FulcrumDia"]
    assert "REAM" in callouts["FulcrumDia"]
    assert drawing.BAR_NUMBER in callouts["LeverThick"]
    assert drawing.BAR_NUMBER in callouts["PlateOffset"]
    # Machinist r5: each hole's mate rides its own hole callout.
    assert callouts["BarPinCx"] == callouts["SpringCx"] == "SETS LEVER RATIO"
    assert drawing.HOLE_MATES == {
        "bar-pin hole": f"RUNS ON PIN\n{drawing.PIN_NUMBER}",
        "spring-eye hole": f"HOOKS SPRING\n{drawing.SPRING_NUMBER}",
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for label in drawing.HOLE_MATES:
        assert f'_callout, label="{label}")' in source
    # .256 +.0010/.0000 on the .250 (.0000/-.0008) shaft: .0060-.0078 in.
    assert drawing._CLEARANCE_LEAST == pytest.approx(0.1524)
    assert drawing._CLEARANCE_MOST == pytest.approx(0.19812)


def test_walls_clear_the_floor_at_worst_case() -> None:
    assert spec.TIP_ARC_CX == spec.LEVER_SPRING_X
    assert spec.TIP_RADIUS == spec.BAR_TALL / 2.0
    for wall, value in spec.WALL_MIN.items():
        assert value >= WALL_TARGET_MM, wall
    # The concentric full round leaves the same nominal wall to the tip.
    nominal = spec.TIP_RADIUS - blind_cut_dia_mm(spec.SPRING_EYE_HOLE_SPEC) / 2.0
    assert nominal == pytest.approx(3.44, abs=0.01)


def test_twenty_long_hubs_still_float_between_the_keepers() -> None:
    stations = drawing.STATIONS
    # The pitch prints .278 (7.0612) +.001/.000: each hub may come out the
    # printed maximum, past the 7.0565 model.
    _lower, upper = printed_deviations(
        spec.HUB_LENGTH,
        notes.DRAWING_PRECISION["Hub"]["HubLength"],
        (spec.HUB_LENGTH_BAND[1], spec.HUB_LENGTH_BAND[0]),
        unit=spec.UNIT,
    )
    growth = stations * upper
    assert spec.HUB_LENGTH_BAND[1] == 0.0  # ch_bar_pivot_pin_spec's pitch minimum
    assert growth < sum(assembly.KEEPER_HUB_FLOAT)


def test_plate_band_is_the_notch_allowance() -> None:
    assert ch_amplitude_bar_spec.LEVER_THICKNESS_TOLERANCE == spec.LEVER_THICKNESS_TOLERANCE


def test_plate_is_located_from_one_hub_face() -> None:
    assert spec.PLATE_OFFSET == pytest.approx((spec.HUB_LENGTH - spec.LEVER_THICKNESS) / 2.0)
    assert notes.DRAWING_PRECISION["PlateOffsetReference"] == {"PlateOffset": 3}
    assert lever.PLATE_OFFSET_SKETCH == "PlateOffsetReference"
    # The line runs from the hub face to the plate face on the hub silhouette.
    start, end = lever._PLATE_OFFSET_START, lever._PLATE_OFFSET_END
    assert start[0] == end[0] == spec.HUB_DIA / 2.0
    assert start[1] - end[1] == pytest.approx(spec.PLATE_OFFSET)


def test_draw_view_math_matches_the_spec() -> None:
    assert drawing._BAR_PIN_DIA == blind_cut_dia_mm(spec.BAR_PIN_HOLE_SPEC)
    assert drawing._SPRING_HOLE_DIA == blind_cut_dia_mm(spec.SPRING_EYE_HOLE_SPEC)
    assert spec.TIP_END_X == pytest.approx(180.511)


def test_sheet_runs_at_1_to_1_with_1_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.ISO_SCALE == (1, 2)
    assert notes.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source
    assert "Manufacturing Notes" not in source


def test_sheet_carries_no_gdt_and_drill_callouts() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame(" not in source
    assert "add_datum_feature(" not in source
    assert "set_basic_dimension(" not in source
    assert source.count("add_native_hole_callout(") == 2
    assert source.count("process=drill_process(") == 2


def test_hub_diameter_lands_on_its_near_rim() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_near_side_diameter(hub_dia[0], "hub diameter")' in source
    assert source.index("set_near_side_diameter(") < source.index(
        "set_dimension_callouts(adapter, front_annotations"
    )


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    part = _config.parts("ch-channel-lever")
    # Owner ruling 2026-10-15: gray cast iron is the material, and its
    # build-up-free conversion coat is the cast-iron class of black oxide.
    assert part["material_specification"] == "GRAY CAST IRON, ASTM A48 CLASS 30"
    assert part["material"] == "GRAY CAST IRON"
    assert "material_family" not in part
    assert lever.MATERIAL == "Gray Cast Iron"
    # A conversion coat, not paint: the hub faces, plate faces and bores
    # keep their bands with nothing masked (as the rocker arms, MHA-CH-06).
    assert part["finish"] == "matte black oxide per MIL-DTL-13924 Class 1, oil sealed"
    assert int(part["quantity"]) == 20

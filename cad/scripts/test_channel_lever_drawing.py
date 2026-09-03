"""Offline contracts for the channel-lever drawing."""

from __future__ import annotations

from pathlib import Path

import channel_lever_spec
import draw_channel_lever as drawing
import build_channel_lever as lever
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/channel-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/channel-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/channel-lever_drawing.png")
    assert DRAWINGS_BY_NAME["channel_lever"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is channel_lever_spec.DRAWING_DIMENSIONS
    marked = set().union(*channel_lever_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert "TipCentreX" in marked


def test_draw_view_math_matches_the_spec() -> None:
    assert (drawing.LEVER_SPRING_X, drawing.BAR_PIN_X) == (
        channel_lever_spec.LEVER_SPRING_X,
        channel_lever_spec.BAR_PIN_X,
    )
    assert channel_lever_spec.LEVER_SPRING_X == lever.LEVER_SPRING_X
    assert channel_lever_spec.BAR_PIN_X == lever.BAR_PIN_X
    assert channel_lever_spec.PIVOT_HOLE_DIA == lever.PIVOT_HOLE_DIA
    # The tip R3 CENTRE is 182.80 from the fulcrum (TipCentreX); the tip
    # extreme is 185.80 and the nose extreme -4.75, so the true end-to-end
    # overall is 190.55.
    assert channel_lever_spec.TIP_ARC_CX == 182.8
    assert channel_lever_spec.TIP_END_X == 185.8
    assert abs(channel_lever_spec.OVERALL_LENGTH - 190.55) < 1e-9
    assert drawing._NOSE_R == channel_lever_spec.NOSE_RADIUS


def test_sheet_runs_at_1_to_1_with_1_to_4_isometric() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 4)" in source  # the isometric override
    assert channel_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_notes_are_few_specific_and_never_the_title_block() -> None:
    notes = channel_lever_spec.DRAWING_NOTES
    lines = notes.split("\n")
    assert len(lines) <= 4
    assert "CONTINUOUS-CAST FLAT STOCK" in notes
    assert "INTEGRAL HUB DIA 12.00 X 7.06" in notes
    assert "SETS STATION PITCH" in notes
    assert "NO SPACERS" in notes
    # The tip R3 centre is a sheet dimension (182.80 from the fulcrum), so the
    # note that used to narrate the spring-hole/tip offset is gone.
    assert "CONCENTRIC" not in notes
    # Stations ride sheet dimensions, drills ride the hole callouts.
    for sheet_owned in ("127.00", "169.00", "177.80", "182.80", "190.55", "4.75", "DRILL"):
        assert sheet_owned not in notes, sheet_owned
    # Nothing the title block or a dimension already says, no GD&T prose.
    for banned in (
        "UOS", "DIMENSIONS IN", "LINEAR +/-", "+/-", "+0.03", "DATUM", "BASIC",
        "FCF", "WITHIN", "Ra ", "MHA-", "GRAY-IRON", "GREEN ENAMEL", "IRON",
    ):
        assert banned not in notes, banned
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # drawing-simplicity-policy.md rule 3: a coordinate +/- from the fulcrum
    # bore holds every hole identically on all 20 levers, so the channel
    # lever uses none of its one-control allowance; nothing runs on a
    # surface a roughness symbol would name.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "_force_dimension_black(",
    ):
        assert helper not in source, helper
    assert not hasattr(channel_lever_spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(channel_lever_spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(channel_lever_spec, "SURFACE_FINISHES")


def test_reamed_fulcrum_bore_band_rides_the_model_dimension() -> None:
    # drawing-simplicity-policy.md rule 2: the reamed bore's +0.03/0 band is
    # a native tolerance on the MODEL dimension (same band as the rocker arm's
    # pivot bore on the same 6.35 shaft), and the sheet prints it at three
    # decimals; no note and no frame carry it.
    assert channel_lever_spec.PIVOT_HOLE_BAND == (0.03, 0.00)
    build_source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "from _fit_limits import deviations" in build_source
    assert (
        'set_dimension_bilateral_tolerance(\n'
        '        adapter, "FulcrumProfile", "FulcrumDia", *deviations(PIVOT_HOLE_BAND)\n'
        "    )"
    ) in build_source
    assert drawing.DIMENSION_PRECISION == {"FulcrumDia": 3}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert (
        "set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)"
        in source
    )


def test_stations_and_section_are_ordinary_sheet_dimensions() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for label in (
        "fulcrum-to-bar-pin c2c",
        "fulcrum-to-spring c2c",
        "overall length",
        "lever thickness",
        "bar height",
    ):
        assert f'label="{label}"' in source, label
    assert source.count("add_edge_dimension(") == 5
    assert "InsertCenterMark3(2, False, False)" in source
    assert "tip_edge = _sheet_xy(TIP_END_X, 0.0)" in source


def test_overall_is_the_true_end_to_end_reference_and_outermost() -> None:
    # The stack shares one origin (the fulcrum bore); the end-to-end overall
    # runs arc extreme to arc extreme (NOT centre to centre, which would
    # repeat the 182.80 tip-centre station), is parenthesised as reference,
    # and sits in the outermost lane so it is the conspicuous one.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_arc_endpoints_to_max(adapter, overall, label="overall length")' in source
    assert "set_reference_dimension(" in source
    assert "nose_extreme = _sheet_xy(-_NOSE_R, 0.0)" in source
    assert "tip_extreme = _sheet_xy(TIP_END_X, 0.0)" in source
    lanes = drawing.STACK_Y
    assert min(lanes, key=lanes.get) == "overall"
    ordered = ["bar_pin", "bar_length", "spring", "tip_centre", "overall"]
    assert [lanes[k] for k in ordered] == sorted(lanes.values(), reverse=True)
    assert drawing.FRONT_KEEP["BarLength"][1] == lanes["bar_length"]
    assert drawing.FRONT_KEEP["TipCentreX"][1] == lanes["tip_centre"]


def test_hole_callouts_state_size_and_process_and_stay_apart() -> None:
    assert drawing.DIMENSION_CALLOUTS == {"FulcrumDia": "REAM THRU"}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 2
    assert 'label="bar-pin hole"' in source
    assert 'label="spring-eye hole"' in source
    assert 'process="#47 DRILL"' in source
    assert 'process="#21 DRILL"' in source
    assert "set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)" in source
    # Two callouts on two lanes: separated in X (> 20 mm between their text
    # centres' nearest edges) AND in Y, so they never read as one line.
    bar_pin, spring = drawing.BAR_PIN_CALLOUT_XY, drawing.SPRING_CALLOUT_XY
    assert spring[0] - bar_pin[0] > 0.080
    assert bar_pin[1] != spring[1]
    # The tip-radius text sits right of the spring-eye callout lane, so the
    # callout leader never crosses it.
    assert drawing.FRONT_KEEP["TipRadius"][0] > spring[0] + 0.020


def test_hidden_lines_stay_on_in_every_orthographic_view() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "for view in (front, right, top):\n        set_hidden_lines_visible" in source
    assert "set_hidden_lines_removed(adapter, iso)" in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("channel-lever")
    assert spec["material_specification"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["material"] == "ASTM A48 Class 30 gray cast iron"
    assert spec["finish"] == (
        "RAL 6005 alkyd enamel, SSPC-SP3, 40-60 um DFT; mask all bores"
    )
    assert int(spec["quantity"]) == 20

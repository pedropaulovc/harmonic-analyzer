"""Offline contracts for the cylinder-gear-shaft drawing."""

from __future__ import annotations

import re
from pathlib import Path

import _config
import _fit_deviations
import _fit_shaft_h
import dt_arbor_pedestal_spec
import build_dt_cylinder_gear_shaft as part
import dt_cylinder_gear_shaft_notes as notes
import dt_cylinder_gear_shaft_spec as spec
import draw_dt_cylinder_gear_shaft as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _hole_spec import blind_cut_dia_mm


def test_every_marked_dimension_lands_where_a_turner_reads_it() -> None:
    """drawing-guidelines.md rule 11 (turned parts read like the lathe): a turned part's diameters belong on the SIDE view.

    A circle sketch's diameter only imports into a view that faces the circle,
    so the sheet imports it in a donor view and moves it -- which means every
    donor name needs a side-view destination or the diameter would ship on a
    throwaway view (or, once the donor is deleted, not at all).
    """
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.DONOR_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert set(drawing.PROFILE_DIAMETERS) == set(drawing.DONOR_KEEP)
    assert not set(drawing.PROFILE_DIAMETERS) & set(drawing.PROFILE_KEEP)


def test_only_the_running_fit_carries_a_size_band() -> None:
    """The O.D. is the one critical feature; the length rides the title block."""
    assert spec.SHAFT_DIA_BAND == _fit_shaft_h.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)",
    }


def test_shaft_band_closes_the_configured_running_fit() -> None:
    lower, upper = _fit_deviations.deviations(spec.SHAFT_DIA_BAND)
    shaft_limits = (spec.SHAFT_DIA + lower, spec.SHAFT_DIA + upper)
    bore_lower, bore_upper = _fit_deviations.deviations(dt_arbor_pedestal_spec.BORE_DIA_BAND)
    bore_limits = (
        dt_arbor_pedestal_spec.BORE_DIA + bore_lower,
        dt_arbor_pedestal_spec.BORE_DIA + bore_upper,
    )
    clearances = [
        round(bore_limits[0] - shaft_limits[1], 5),
        round(bore_limits[1] - shaft_limits[0], 5),
    ]
    assert clearances == list(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))


def test_the_part_owns_display_precision_and_the_sheet_only_asserts_it() -> None:
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 4,
        "Depth": 1,
        "DomeHeight": 2,
        "DomeRadius": 2,
    }
    assert "draw_dt_cylinder_gear_shaft.py" in PRECISION_MIGRATED_DRAWINGS
    # 3/8 in prints exactly (.3750): the native bearing size every mating
    # bore is built from.
    digits = spec.DRAWING_PRECISION_BY_NAME["ShaftDia"]
    printed = round(spec.SHAFT_DIA / 25.4, digits) * 25.4
    assert abs(printed - spec.SHAFT_DIA) <= 1e-9


def test_a_plain_drive_train_shaft_carries_no_gdt_and_no_end_view() -> None:
    """drawing-guidelines.md rule 5 (avoid excessive GD&T) keeps GD&T for the castings and gear blanks.

    Size limits plus the title-block general grade already state everything a
    lathe hand can hold on a plain rod, and the end view existed only to carry
    the diameter that now sits on the side view.
    """
    for attribute in (
        "PART_DATUMS",
        "GEOMETRIC_CONTROLS",
        "END_VIEW_NOTE",
        "LENGTH_TOLERANCE_MM",
    ):
        assert not hasattr(spec, attribute)


def test_notes_are_short_specific_facts_with_no_dimension_in_them() -> None:
    lines = notes.DRAWING_NOTES.splitlines()
    assert 0 < len(lines) <= 4
    for line in lines:
        assert line == line.upper()
        assert not re.search(r"\d+\.\d|±|\+/-", line)


def test_the_od_names_its_mates_and_its_stock_route_at_the_callout() -> None:
    """Fan-out screen 20261107T081227004Z: the .0008 band's only fit route,
    ground stock, sat in an unlinked general note; the set-screw spots named
    no mate."""
    assert notes.SHAFT_DIA_CALLOUT == (
        "RUNNING FIT IN MHA-DT-12 AND MHA-DT-02 BORES; 3/8 GROUND STOCK OK"
    )
    assert "GROUND STOCK" not in notes.DRAWING_NOTES
    # The spots print at a leader on the bar, not in the unflagged block
    # (fan-out local repeat of e308920ca9, 3 of 3 runs).
    assert "SPOTS" not in notes.DRAWING_NOTES
    flat = " ".join(notes.SPOT_NOTE.splitlines())
    assert flat == (
        "NO FLATS; MHA-SH-VN-54 SPOTS: Ø.089 (#43) DRILL "
        "POINT ONLY, AT ASSEMBLY THROUGH MHA-DT-02 TAPS"
    )
    # Farm r5 (3 of 3): the spot carries its size, the pedestal tap's drill.
    tap_drill_in = blind_cut_dia_mm(dt_arbor_pedestal_spec.SET_SCREW_HOLE_SPEC) / 25.4
    assert notes.SPOT_DRILL.startswith(f"Ø{tap_drill_in:.3f}".replace("Ø0.", "Ø."))
    assert "#43" in notes.SPOT_DRILL
    assert drawing.SPOT_NOTE is notes.SPOT_NOTE
    # The leader lands on the bar inside the south strap's width, right of the
    # length's witness, and the text stands between the bar and that length.
    assert drawing.SHAFT_LEFT_X < drawing.SPOT_EDGE[0] < drawing.SPOT_NOTE_XY[0]
    assert drawing.SPOT_EDGE[0] - drawing.SHAFT_LEFT_X < dt_arbor_pedestal_spec.STRAP_T / 1000.0
    assert drawing.PROFILE_KEEP["Depth"][1] < drawing.SPOT_NOTE_XY[1] < drawing.SPOT_EDGE[1]
    assert _config.parts("sh-vn-arbor-set-screw")["number"] == notes.SET_SCREW_NUMBER
    assert _config.parts("dt-arbor-pedestal")["number"] == notes.PEDESTAL_NUMBER
    # The part stamps the notes module's text, and the sheet prints its callout.
    assert part.DRAWING_NOTES is notes.DRAWING_NOTES
    assert drawing.SHAFT_DIA_CALLOUT is notes.SHAFT_DIA_CALLOUT


def test_the_isometric_note_states_the_only_off_sheet_scale() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    ratio = re.search(r"(\d+)\s*:\s*(\d+)", spec.ISOMETRIC_VIEW_NOTE)
    assert ratio is not None, f"missing view scale in {spec.ISOMETRIC_VIEW_NOTE!r}"
    assert (int(ratio.group(1)), int(ratio.group(2))) == drawing.ISO_SCALE


def test_the_length_is_a_cut_to_fit_reference() -> None:
    """#743 (superseding U34b's "span less 6.0"): the arbor fills both strap
    bores, so its cylinder IS the span over both installed pedestals -- a REF
    value the callout under it governs -- and each end is domed proud."""
    import cylinder_bank_layout as bank

    outer_span = bank.STRAP_INNER_SPAN + 2 * dt_arbor_pedestal_spec.STRAP_T
    assert part.SHAFT_LENGTH == bank.ARBOR_LENGTH == outer_span
    assert part.DOME_HEIGHT == bank.ARBOR_DOME_HEIGHT
    assert not hasattr(spec, "FIT_SHORTFALL")
    assert spec.DRAWING_PRECISION_BY_NAME["Depth"] == 1
    assert spec.LENGTH_CALLOUT.startswith("CUT TO FIT")
    assert "MHA-DT-02" in spec.LENGTH_CALLOUT
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'set_reference_dimension(adapter, length_annotations[0]' in source
    assert '{"Depth": LENGTH_CALLOUT}' in source


def test_the_supplied_bar_covers_the_longest_fitted_arbor() -> None:
    """The bar is supplied long and cut at assembly, so the SUPPLY note must
    cover the overall (span plus both domes) at the accepted long stack, with
    a .020 facing cut at each end (the shop's ch_rocker_hub_spec.FACE_STOCK).
    #1038 re-pitch: the 176.464 span leaves 7-1/2 in about 11 mm spare."""
    import cylinder_bank_layout as bank

    for text in (notes.DRAWING_NOTES, spec.DRAWING_NOTES):
        supply = re.search(r"SUPPLY (\d+)-(\d+)/(\d+) LONG", text)
        assert supply is not None, text
        whole, numerator, denominator = (int(group) for group in supply.groups())
        supply_mm = (whole + numerator / denominator) * 25.4
        longest = bank.ARBOR_OVERALL_LENGTH + bank.STACK_L20_ACCEPT_BAND[0]
        assert supply_mm - longest >= 2 * 0.508, (supply_mm, longest)


def test_both_ends_are_domed_and_the_dome_form_is_model_owned() -> None:
    """The bright dome on each pedestal is the arbor end (#743, MHA-125
    deleted). InsertDome states no markable height or radius, so a hidden
    reference sketch owns both, as the pedestal's locations are owned; the
    radius prints as the spherical reference that says the end is a sphere."""
    assert spec.REFERENCE_SKETCHES == ("DomeReference",)
    assert spec.DRAWING_DIMENSIONS["DomeReference"] == {"DomeHeight", "DomeRadius"}
    # The printed .06 IS the modelled dome (#290 snap).
    places = spec.DRAWING_PRECISION_BY_NAME["DomeHeight"]
    assert abs(round(part.DOME_HEIGHT / 25.4, places) * 25.4 - part.DOME_HEIGHT) <= 1e-9
    assert spec.DOME_CALLOUT == "BOTH ENDS"
    drawing_source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "_set_spherical_reference(adapter, radius_annotations[0]" in drawing_source
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '_dome_end(adapter, 0.0, "SouthDome")' in source
    assert '_dome_end(adapter, SHAFT_LENGTH, "NorthDome")' in source
    assert "_hide_reference_sketches(adapter)" in source
    assert part.DOME_SPHERE_RADIUS > part.SHAFT_RADIUS
    assert notes.SPOT_NOTE.startswith("NO FLATS")

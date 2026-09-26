"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _common

import _drawing_marks
import _fit_limits
import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_geometry as geometry
import pinion_arbor_spec as spec
import pinion_handle_geometry as rod_geometry
import pinion_handle_spec as crossrod
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_arbor"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_every_printed_dimension() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    # The donor carries the head diameter only; the neck's imports straight
    # into detail A.
    assert {"HeadDia"} == set(drawing.DONOR_KEEP)
    assert "NeckDia" in drawing.DETAIL_KEEP
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_integral_arbor_keeps_the_released_stations_around_a_longer_head() -> None:
    # Rule 12 (audit W6) grew the head 9.0 -> 10.5, and the machinist review of
    # 7f7fc1717 (Main's option 2) to 11.5, each time about the released
    # crossrod station; the shaft and back crown stay put.  The neck shoulder
    # moves 0.25 forward so every length but the drum station prints at .X.
    assert spec.HEAD_CENTER_Z == pytest.approx(-6.5)
    assert spec.HEAD_LEN == pytest.approx(11.5)
    assert spec.HEAD_FRONT_Z == pytest.approx(spec.HEAD_CENTER_Z - spec.HEAD_LEN / 2.0)
    assert spec.HEAD_REAR_Z == pytest.approx(spec.HEAD_CENTER_Z + spec.HEAD_LEN / 2.0)
    assert spec.NECK_END_Z == pytest.approx(9.75)
    assert spec.SHAFT_LEN == pytest.approx(226.25)
    assert spec.SHAFT_LEN + spec.BACK_CAP_SAG == pytest.approx(227.45)
    assert spec.OVERALL_LEN == pytest.approx(
        spec.SHAFT_LEN + spec.BACK_CAP_SAG - (spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG)
    )
    assert spec.EXPOSED_SHAFT_LEN == pytest.approx(spec.SHAFT_LEN - spec.NECK_END_Z)
    assert spec.BACK_RIM_FROM_HEAD_REAR == pytest.approx(spec.SHAFT_LEN - spec.HEAD_REAR_Z)


def test_only_the_drum_station_prints_two_places() -> None:
    """Machinist review of 7f7fc1717: NeckLen printed 11.25 at .XX.  Every
    station runs from the head rear face, so the head and neck shoulder are
    chosen so every turned length lands on .X; the drum station, an assembly
    station, is the one .XX length (as at 61.55)."""
    lengths = {
        "HeadLen": spec.HEAD_LEN,
        "NeckLen": spec.NECK_LEN,
        "BackRimFromHeadRear": spec.BACK_RIM_FROM_HEAD_REAR,
        "OverallLen": spec.OVERALL_LEN,
        "FrontJournalFromHeadRear": spec.FRONT_JOURNAL_FROM_HEAD_REAR,
        "BackJournalFromHeadRear": spec.BACK_JOURNAL_FROM_HEAD_REAR,
        "FrontJournalLen": spec.JOURNAL_LEN,
        "BackJournalLen": spec.JOURNAL_LEN,
        "DrumStationFromHeadRear": spec.DRUM_STATION,
    }
    two_places = {
        name for name in lengths if spec.DRAWING_PRECISION_BY_NAME[name] == 2
    }
    assert two_places == {"DrumStationFromHeadRear"}
    for name, value in lengths.items():
        if name in two_places:
            assert value != pytest.approx(round(value, 1), abs=1e-9), name


def test_crossrod_hole_is_centred_with_a_rule_12_web() -> None:
    # Printed centred on the Ø15 cylinder's length: only HeadLen's .X band
    # reaches the web, never a separate station band.  The machinist review of
    # 7f7fc1717 holds the web to the novice-machinist 2.0 target.
    assert "CrossHoleReference" not in spec.DRAWING_DIMENSIONS
    assert f"CENTRED ON<MOD-DIAM>{spec.HEAD_DIA:.0f} CYLINDER LENGTH" in (
        spec.CROSS_HOLE_CALLOUT
    )
    assert spec.CROSS_HOLE_WEB_WORST == pytest.approx(
        (spec.HEAD_LEN - spec.HEAD_LEN_BAND) / 2.0
        - (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[0]) / 2.0
    )
    assert spec.CROSS_HOLE_WEB_TARGET == 2.0
    assert spec.CROSS_HOLE_WEB_WORST >= spec.CROSS_HOLE_WEB_TARGET


def test_cross_hole_callout_names_the_cylinder_not_the_crowned_head() -> None:
    """Machinist review of 7f7fc1717 (blocker): "CENTRED ON HEAD LENGTH" could
    mean the straight Ø15 cylinder or the whole crowned head.  The callout
    names the cylinder, its Ø read from the spec rather than typed."""
    assert "HEAD LENGTH" not in spec.CROSS_HOLE_CALLOUT
    assert f"<MOD-DIAM>{spec.HEAD_DIA:.0f} CYLINDER" in spec.CROSS_HOLE_CALLOUT
    assert "15" not in spec.CROSS_HOLE_CALLOUT.replace(f"{spec.HEAD_DIA:.0f}", "", 1)


def test_integral_head_owns_the_crossrod_interface() -> None:
    assert spec.HEAD_DIA == pytest.approx(15.0)
    assert spec.NECK_DIA == pytest.approx(10.5)
    assert spec.NECK_LEN == pytest.approx(spec.NECK_END_Z - spec.HEAD_REAR_Z)
    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is spec.CROSS_HOLE_CALLOUT
    assert callout == "REAM THRU,\nCENTRED ON<MOD-DIAM>15 CYLINDER LENGTH"
    # Fable r-delta (Main ruling B): MHA-058's bond and acceptance are
    # instructions for a part not on this print; MHA-058 carries both.
    assert "MHA-058" not in spec.DRAWING_NOTES
    assert "SHALL NOT TURN OR SLIDE BY HAND" in crossrod.ASSEMBLY_STEP


def test_crossrod_is_a_bonded_slip_fit_not_a_press() -> None:
    """R1 (U27 precedent): a novice's stock reamer and as-received bar give
    clearance, so the hole is banded Ø6.00 +0.10/0 and the rod is bonded."""
    assert spec.CROSS_HOLE_DIA == pytest.approx(6.0)
    assert spec.CROSS_HOLE_DIA_BAND == (0.10, 0.0)
    assert crossrod.ROD_DIA == pytest.approx(spec.CROSS_HOLE_DIA)  # line to line
    assert (
        model_toleranced_dimensions(part)[("CrossHoleProfile", "CrossHoleDia")]
        == "*deviations(CROSS_HOLE_DIA_BAND)"
    )
    assert spec.DRAWING_PRECISION_BY_NAME["CrossHoleDia"] == 2
    tightest = (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[1]) - (
        crossrod.ROD_DIA + rod_geometry.ROD_DIA_BAND[0]
    )
    loosest = (spec.CROSS_HOLE_DIA + spec.CROSS_HOLE_DIA_BAND[0]) - (
        crossrod.ROD_DIA + rod_geometry.ROD_DIA_BAND[1]
    )
    assert spec.CROSSROD_MIN_CLEARANCE == pytest.approx(tightest)
    assert spec.CROSSROD_MAX_CLEARANCE == pytest.approx(loosest)
    assert tightest >= 0.0
    assert loosest <= spec.RETAINING_COMPOUND_MAX_GAP_MM
    assert "INTO MHA-102 HEAD WITH LOCTITE 638" in crossrod.ASSEMBLY_STEP
    for retired in ("MATCH-REAM", "PRESS", "INTERNAL SHOULDERS SHARP"):
        assert retired not in spec.DRAWING_NOTES
        assert retired not in spec.CROSS_HOLE_CALLOUT


def test_only_the_two_journal_lands_carry_the_running_band_and_finish() -> None:
    assert spec.JOURNAL_DIA_BAND == (-0.01, -0.03)
    # Both stacked bands print at 2 places: "-0.01/-0.03" and "-0.01/-0.10".
    for band in (spec.JOURNAL_DIA_BAND, spec.SHAFT_DIA_BAND):
        assert _drawing_marks._tolerance_precision_mm(*_fit_limits.deviations(band)) == 2
    assert _fit_limits.band_text(spec.JOURNAL_DIA_BAND) == "-0.01/-0.03"
    assert spec.SHAFT_DIA_BAND == (-0.01, -0.10)
    assert model_toleranced_dimensions(part) == {
        ("BondZoneReference", "BondZoneDia"): "*deviations(SHAFT_DIA_BAND)",
        ("DrumStationReference", "DrumStationFromHeadRear"): "DRUM_STATION_BAND",
        ("CrossHoleProfile", "CrossHoleDia"): "*deviations(CROSS_HOLE_DIA_BAND)",
        ("PinHoleProfile", "PinHoleDia"): "*deviations(PIN_HOLE_DIA_BAND)",
        ("FrontJournalReference", "FrontJournalDia"): "*deviations(JOURNAL_DIA_BAND)",
        ("BackJournalReference", "BackJournalDia"): "*deviations(JOURNAL_DIA_BAND)",
    }
    lands = {
        "front_journal": spec.FRONT_JOURNAL_Z,
        "back_journal": spec.BACK_JOURNAL_Z,
    }
    assert {finish.key for finish in spec.SURFACE_FINISHES} == set(lands)
    for finish in spec.SURFACE_FINISHES:
        assert finish.roughness_um == 1.6
        assert finish.face.diameter_mm == spec.SHAFT_DIA
        station = lands[finish.key]
        assert station < finish.face.contains_z_mm < station + spec.JOURNAL_LEN
    assert set(drawing.JOURNAL_FINISHES) == set(lands)
    for key, (station_z, _symbol_xy, _flank) in drawing.JOURNAL_FINISHES.items():
        assert lands[key] < station_z < lands[key] + spec.JOURNAL_LEN
    assert "MHA-056" in spec.DRAWING_NOTES
    assert "PRESSES INTO" not in spec.DRAWING_NOTES
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_each_journal_land_covers_its_strap_with_axial_margin() -> None:
    """The lands must cover the MHA-056 straps where the assembly puts them."""
    import build_drive_train_assembly as assembly

    front_face = assembly.RIG.STRAP_Z_INNER[0] - assembly.ARBOR_Z0
    back_face = assembly.RIG.STRAP_Z_INNER[1] - assembly.ARBOR_Z0
    # 9 mm is the thicker strap the pinion-cluster slice carries.
    for strap_t in {assembly.STRAP_T, 9.0}:
        for strap_lo, strap_hi, land_lo in (
            (front_face - strap_t, front_face, spec.FRONT_JOURNAL_Z),
            (back_face, back_face + strap_t, spec.BACK_JOURNAL_Z),
        ):
            assert strap_lo - land_lo >= 1.0
            assert land_lo + spec.JOURNAL_LEN - strap_hi >= 1.0


def test_journal_and_bond_zone_bands_leave_the_intended_fits() -> None:
    import alignment_pinion_spec as drum
    import pinion_bracket_spec as strap

    journal_upper, journal_lower = spec.JOURNAL_DIA_BAND
    strap_upper, strap_lower = strap.ARBOR_BORE_BAND
    # Running fit of each land in its MHA-056 REAM_SLIDE bore.
    assert strap.ARBOR_BORE_BAND is _fit_limits.REAM_SLIDE
    assert strap_lower - journal_upper == pytest.approx(0.020)
    assert strap_upper - journal_lower == pytest.approx(0.055)
    # Every bore slides on from the back crown, so no zone may exceed 8.00.
    # The drum keeps its stock-H7 bore, so the bond zone sits 0.01 under it
    # for a guaranteed slide, and the worst gap stays inside Loctite 638's 0.25.
    shaft_upper, shaft_lower = spec.SHAFT_DIA_BAND
    assert shaft_upper == pytest.approx(-0.010)
    drum_upper, drum_lower = drum.ARBOR_BORE_BAND
    assert drum_lower - shaft_upper == pytest.approx(0.010)
    assert drum_upper - shaft_lower <= 0.20 + 1e-9
    # The drum passes over the back land on its way on, so "SLIDES BY HAND"
    # must hold there too: every Ø8 zone it crosses stays 0.010 under its bore.
    assert drum_lower - journal_upper == pytest.approx(0.010)
    assert min(drum_lower - journal_upper, drum_lower - shaft_upper) >= 0.010 - 1e-9


def test_retired_socket_and_retention_pin_are_not_exported() -> None:
    retired = {
        "RETENTION_HOLE_DIA",
        "RETENTION_PIN_STATION",
        "TUBE_ID",
        "TUBE_OD",
        "TUBE_LEN",
        "WALL_T",
    }
    assert retired.isdisjoint(vars(spec))
    assert "RETENTION PIN" not in spec.CROSS_HOLE_CALLOUT


def test_every_post_import_name_is_carried_by_a_kept_or_moved_dimension() -> None:
    """Offline audit of the names the sheet looks up after the model import."""
    carried = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= carried
    assert set(spec.DRAWING_PRECISION_BY_NAME) == carried
    assert set(drawing.DIAMETER_POSITIONS) <= carried
    # Every donor diameter moves to the profile, and nothing else moves.
    assert set(drawing.DIAMETER_POSITIONS) == set(drawing.DONOR_KEEP)
    assert not hasattr(drawing, "DETAIL_DIAMETER_POSITIONS")
    assert {"CrossHoleDia", "HeadCapSagDim", "BackCapSagDim", "OverallLen"} <= carried


def test_back_crown_radius_is_the_model_dimension_not_typed_text() -> None:
    assert spec.DRAWING_DIMENSIONS["BackCapProfile"] == {"BackCapR", "BackCapSagDim"}
    assert spec.DRAWING_PRECISION_BY_NAME["BackCapR"] == 1
    assert "BackCapR" in drawing.PRINCIPAL_KEEP
    assert drawing.DIMENSION_CALLOUTS["BackCapSagDim"] == "BACK CROWN"
    assert not any("SR" in text for text in drawing.DIMENSION_CALLOUTS.values())


def test_every_printed_length_is_exact_at_its_authored_places() -> None:
    """A one-place print of 11.25 reads 11.3: the sheet would not state the model."""
    nominal = {
        "HeadLen": spec.HEAD_LEN,
        "NeckLen": spec.NECK_LEN,
        "BackRimFromHeadRear": spec.BACK_RIM_FROM_HEAD_REAR,
        "OverallLen": spec.OVERALL_LEN,
        "FrontJournalFromHeadRear": spec.FRONT_JOURNAL_FROM_HEAD_REAR,
        "BackJournalFromHeadRear": spec.BACK_JOURNAL_FROM_HEAD_REAR,
        "FrontJournalLen": spec.JOURNAL_LEN,
        "BackJournalLen": spec.JOURNAL_LEN,
        "DrumStationFromHeadRear": spec.DRUM_STATION,
    }
    for name, value in nominal.items():
        places = spec.DRAWING_PRECISION_BY_NAME[name]
        assert value == pytest.approx(round(value, places), abs=1e-9), name


def test_each_land_diameter_is_measured_a_short_extension_from_its_line() -> None:
    """Main (aab2b98b): the land diameters were measured at the land's
    head-side end, so their extensions ran 18-25 mm along the flank to the
    text.  Each is now measured at a witness just inside the crown-side end
    and its line stands 1 mm from it, so the extension cannot grow back."""
    assert part.JOURNAL_DIA_POINT_FROM_CROWN_END == drawing.JOURNAL_DIA_POINT_FROM_CROWN_END
    assert 0.0 < part.JOURNAL_DIA_POINT_FROM_CROWN_END <= 3.0
    for key, land_z in (("Front", spec.FRONT_JOURNAL_Z), ("Back", spec.BACK_JOURNAL_Z)):
        point_x = drawing._sheet_x(
            land_z + spec.JOURNAL_LEN - part.JOURNAL_DIA_POINT_FROM_CROWN_END
        )
        line_x = drawing.PRINCIPAL_KEEP[f"{key}JournalDia"][0]
        assert abs(line_x - point_x) <= 0.0015, key
        crown_end = drawing._sheet_x(land_z + spec.JOURNAL_LEN)
        head_end = drawing._sheet_x(land_z)
        assert min(crown_end, head_end) < line_x < max(crown_end, head_end), key


def test_back_journal_diameter_hangs_above_clear_of_the_crown_witnesses() -> None:
    """Below the shaft the back land is boxed in: the back-crown/overall
    witnesses (x 0.079-0.081) on its crown side ran through its text at
    30620a85, and the 199.9 witness and Ra leader sit on its head side.  Its
    diameter hangs above, text right of the line; its 19.0 goes below."""
    width, height = drawing.DIAMETER_BLOCK_SIZE
    x, y = drawing.PRINCIPAL_KEEP["BackJournalDia"]
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    # 12 -> 15 mm: the back Ra symbol now sits between block and shaft.
    assert 0.003 <= (y - height / 2.0) - shaft_top <= 0.015
    assert x - 0.081 >= 0.010  # clear of the crown witnesses rising to the sag
    detail_left = drawing.DETAIL_LABEL_XY[0] - drawing.DETAIL_LABEL_HALF_WIDTH
    assert detail_left - (x + width) >= 0.010
    # The 19.0 sits below, clear of the land's crown-side end.
    len_x, _len_y = drawing.PRINCIPAL_KEEP["BackJournalLen"]
    crown_end = drawing._sheet_x(spec.BACK_JOURNAL_Z + spec.JOURNAL_LEN)
    assert len_x - 0.0055 > crown_end


def test_back_ra_symbol_hangs_above_the_shaft_clear_of_every_witness() -> None:
    """c6eb7f6f: the back Ra leader's shoulder crossed the 199.9 / 19.0
    witness below the shaft, a line through the symbol (Main).  Above the
    shaft nothing rises from the back land, so the symbol hangs there."""
    edge_z, (symbol_x, symbol_y), flank = drawing.JOURNAL_FINISHES["back_journal"]
    assert flank == "upper"
    assert drawing.JOURNAL_FINISHES["front_journal"][2] == "lower"
    head_end = drawing._sheet_x(spec.BACK_JOURNAL_Z)
    crown_end = drawing._sheet_x(spec.BACK_JOURNAL_Z + spec.JOURNAL_LEN)
    arrow_x = drawing._sheet_x(edge_z)
    assert crown_end < arrow_x < head_end  # the arrow lands on the land
    left, right, top = drawing.RA_SYMBOL_EXTENT
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    # A leader rise long enough to carry its arrowhead.
    assert symbol_y - shaft_top >= 0.004
    # The shoulder runs head side from the arrow, right of the diameter line.
    dia_line_x = drawing.BACK_JOURNAL_DIA_POINT_X
    assert dia_line_x + 0.010 < arrow_x < symbol_x
    assert symbol_x + left - dia_line_x >= 0.010
    # Under the back JOURNAL block, with a gap.
    _width, height = drawing.DIAMETER_BLOCK_SIZE
    dia_bottom = drawing.PRINCIPAL_KEEP["BackJournalDia"][1] - height / 2.0
    assert dia_bottom - (symbol_y + top) >= 0.002
    # Clear of the DETAIL A label to its right.
    assert (drawing.DETAIL_LABEL_XY[0] - drawing.DETAIL_LABEL_HALF_WIDTH) - (
        symbol_x + right
    ) >= 0.005
    assert "leader-crosses-leader" in drawing.BLOCKING_LAYOUT_FINDINGS


def test_bond_zone_callout_sits_above_the_shaft_clear_of_its_neighbours() -> None:
    """At 63468ee9 the BOND ZONE shelf ended 1 mm short of the front JOURNAL
    shelf below the shaft, so a novice could read -0.01/-0.10 as the
    journal's (Main, Fable).  It now hangs above the shaft, where no other
    diameter is, clear of detail A, its label and the front land's 19.0."""
    width, height = drawing.DIAMETER_BLOCK_SIZE
    x, y = drawing.PRINCIPAL_KEEP["BondZoneDia"]
    left, right, bottom, top = x, x + width, y - height / 2.0, y + height / 2.0
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    # Short witnesses: the block starts a few mm off the silhouette.
    assert 0.003 <= bottom - shaft_top <= 0.012
    # Right of the DETAIL A label and the detail circle.
    detail_x, detail_y = drawing.DETAIL_CENTER
    detail_r = drawing.DETAIL_CROP_RADIUS
    near_x = max(left - detail_x, 0.0, detail_x - right)
    near_y = max(bottom - detail_y, 0.0, detail_y - top)
    assert (near_x**2 + near_y**2) ** 0.5 - detail_r >= 0.010
    assert (
        left - (drawing.DETAIL_LABEL_XY[0] + drawing.DETAIL_LABEL_HALF_WIDTH) >= 0.010
    )
    # Short of the front land's 19.0 witness and its outside arrow tail.
    front_land_end = drawing._sheet_x(spec.FRONT_JOURNAL_Z + spec.JOURNAL_LEN)
    assert front_land_end - 0.006 - right >= 0.005
    # Under detail A's "(3.0)" line (sheet y ~0.207).
    assert top <= 0.200


FENCE = {"center": (0.3132, 0.171), "radius": 0.015, "axis": (-1.0, 0.0)}


def _fence_dim(label: str, *segments):
    from _layout_geometry import AnnotationGeometry

    return AnnotationGeometry(label=label, kind="dim", owner="p", segments=segments)


def test_fence_lets_a_vertical_diameter_line_out_but_not_its_extension_lines() -> None:
    """Run 492a7be5: HeadDia's own vertical line runs up out of the fence to
    its text (allowed, a line crossing a line); a horizontal run off a
    vertical diameter is an extension line and may not leave (Main ruling)."""
    from _layout_geometry import Segment

    to_text = Segment(0.3238, 0.1775, 0.3238, 0.1892)  # the flagged run
    tail = Segment(0.3238, 0.1625, 0.3238, 0.1562)  # the outside-arrow tail
    inside = Segment(0.3190, 0.1785, 0.3250, 0.1785)  # extension, in the fence
    arrows = {"HeadDia": ((0.3238, 0.1775), (0.0, -1.0))}
    head = _fence_dim("HeadDia", to_text, tail, inside)
    drawing._assert_witnesses_clear_of_detail_fence([head], arrows=arrows, **FENCE)
    assert drawing._segment_kind(to_text, arrows["HeadDia"][1]) == "dimension-line"
    assert drawing._segment_kind(inside, arrows["HeadDia"][1]) == "extension-line"

    outward = Segment(0.3190, 0.1785, 0.3420, 0.1785)  # the old Ø15 witness
    with pytest.raises(RuntimeError, match="HeadDia' extension-line"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("HeadDia", to_text, outward)], arrows=arrows, **FENCE
        )


def test_fence_lets_a_horizontal_station_out_on_its_witnesses_and_line() -> None:
    """A station from the head shoulder measures along the turning axis: its
    vertical extension lines drop to the stack and its horizontal dimension
    line may cross, while a run oblique to it may not."""
    from _layout_geometry import Segment

    witness = Segment(0.3080, 0.1650, 0.3080, 0.1280)  # drops to the stack
    upward = Segment(0.3080, 0.1750, 0.3080, 0.2000)  # still a station witness
    line = Segment(0.2600, 0.1600, 0.3100, 0.1600)  # its own dimension line
    arrows = {"FrontJournalFromHeadRear": ((0.3080, 0.1600), (1.0, 0.0))}
    station = _fence_dim("FrontJournalFromHeadRear", witness, upward, line)
    drawing._assert_witnesses_clear_of_detail_fence([station], arrows=arrows, **FENCE)
    assert drawing._segment_kind(witness, (1.0, 0.0)) == "extension-line"
    assert drawing._segment_kind(line, (1.0, 0.0)) == "dimension-line"

    oblique = Segment(0.3080, 0.1650, 0.3300, 0.1400)
    with pytest.raises(RuntimeError, match="oblique"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("FrontJournalFromHeadRear", line, oblique)],
            arrows=arrows,
            **FENCE,
        )


def test_fence_judges_an_unread_or_misread_dimension_as_all_extension_lines() -> None:
    from _layout_geometry import Segment

    run = Segment(0.3080, 0.1650, 0.3080, 0.1280)
    with pytest.raises(RuntimeError, match="extension-line"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("NoArrow", run)], arrows={}, **FENCE
        )
    # A run that stops at the arrow's base still carries the arrow's tip.
    short = Segment(0.3238, 0.1805, 0.3238, 0.1892)
    base = {"Base": ((0.3238, 0.1775), (0.0, -1.0))}
    drawing._assert_witnesses_clear_of_detail_fence(
        [_fence_dim("Base", short)], arrows=base, **FENCE
    )
    # An arrowhead off every one of its own parallel runs is a misread.
    stray = {"Stray": ((0.2000, 0.2000), (0.0, 1.0))}
    with pytest.raises(RuntimeError, match="unreadable"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [_fence_dim("Stray", run)], arrows=stray, **FENCE
        )
    # Leaders are the audit's, not the fence's.
    leader = Segment(0.3238, 0.1650, 0.3238, 0.1920, "leader")
    drawing._assert_witnesses_clear_of_detail_fence(
        [_fence_dim("Led", leader)], arrows={}, **FENCE
    )


def test_bond_zone_diameter_is_a_flank_dimension_on_the_drum() -> None:
    """The end-on Ø8 circle sat in the neck face, so its witnesses crossed the
    neck and the detail fence (run 492a7be5).  The bond zone now carries its
    own Top-plane diameter, printed over its witness, clear of the fence."""
    assert "ShaftProfile" not in spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_DIMENSIONS["BondZoneReference"] == {"BondZoneDia"}
    assert drawing.DIMENSION_CALLOUTS["BondZoneDia"] == "BOND ZONE"
    station = spec.BOND_ZONE_DIA_FROM_HEAD_REAR
    clear = spec.BOND_ZONE_LAND_CLEARANCE
    assert spec.FRONT_JOURNAL_FROM_HEAD_REAR + spec.JOURNAL_LEN + clear <= station
    assert station <= spec.BACK_JOURNAL_FROM_HEAD_REAR - clear
    assert spec.DRUM_STATION < station < spec.DRUM_STATION + geometry.DRUM_LEN
    text_x, _ = drawing.PRINCIPAL_KEEP["BondZoneDia"]
    assert text_x == pytest.approx(drawing._sheet_x(spec.BOND_ZONE_DIA_Z))
    fence_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    assert fence_x - text_x > drawing.DETAIL_RADIUS_MM / 1000.0 + 0.050


def test_head_diameter_line_stands_between_crown_apex_and_fence() -> None:
    x = drawing.DIAMETER_POSITIONS["HeadDia"][0]
    to_x = lambda z: drawing.PRINCIPAL_CENTER[0] - (z - 106.725) / 1000.0  # noqa: E731
    apex = to_x(spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG)
    center = to_x(spec.HEAD_CENTER_Z)
    half = spec.HEAD_DIA / 2000.0
    fence = center + (drawing.DETAIL_RADIUS_MM**2 / 1e6 - half**2) ** 0.5
    assert apex + 0.0015 < x < fence - 0.0020


def test_layout_audit_gates_text_on_line_and_logs_the_rest() -> None:
    from _layout_geometry import Finding

    advisory = Finding(kind="leader-crosses-view", sheet="Sheet1", detail="x")
    drawing._assert_no_text_on_line([advisory])
    for kind in ("text-on-line", "text-on-text", "leader-crosses-leader"):
        blocking = Finding(kind=kind, sheet="Sheet1", detail="journal")
        with pytest.raises(RuntimeError, match="blocking finding"):
            drawing._assert_no_text_on_line([advisory, blocking])


def test_drum_station_stack_derives_the_land_length_and_station_band() -> None:
    """Ruling A on the user's located cluster (option c): with the drum station
    at the general .X band, the lands are the smallest whole-mm length that
    keeps every land end over its strap by 0.5 at the worst band corner, at
    BOTH stops of the fit-up end play; no band is tightened (U27)."""
    import alignment_pinion_spec as drum
    import build_drive_train_assembly as assembly
    import pinion_bracket_geometry as strap
    import pinion_bracket_spec

    # The stack's inputs are the parts' and the assembly's own values.
    assert geometry.DRUM_LEN == drum.FACE_WIDTH == assembly.APINION_DRUM_LEN
    assert geometry.STRAP_T == strap.THICKNESS == assembly.STRAP_T
    assert geometry.STRAP_T_BAND == pinion_bracket_spec.THICKNESS_BAND
    assert spec.STRAP_AXIAL_LOCATION == "pinned-shim-set"
    assert spec.DRUM_STATION == pytest.approx(
        spec.DRUM_STATION_AS_BUILT + spec.DRUM_AFT_SHIFT
    )

    # 20, not 19: the 0.45 drum shim widened the drum's play, and the lands
    # keep RIG_MARGIN_SPARE over their 0.5 floor (Main, #858).
    assert spec.JOURNAL_LEN == pytest.approx(20.0)
    assert spec.LAND_OVER_STRAP_REQUIRED == pytest.approx(0.75)
    # The drum's world station is fixed; the printed station is that position
    # from the head rear face, so it follows the face (61.55 at the 10.5 head).
    assert spec.DRUM_STATION_AS_BUILT == pytest.approx(
        spec.DRUM_FRONT_Z_AS_BUILT - spec.HEAD_REAR_Z
    )
    assert spec.DRUM_STATION == pytest.approx(61.05)
    assert spec.DRUM_STATION_BAND == spec.LINEAR_X_BAND == pytest.approx(0.8)
    assert spec.END_PLAY == 0.45 and spec.END_PLAY_SET_ERROR == 0.10
    # Codex #854 review (Main): no copies of values the rig and the title block
    # own -- the spec reads them, so a feeler or row change reaches the lands.
    import inspect

    import pinion_rig_layout as rig
    from _printed_tolerance import printed_band_mm

    assert (spec.END_PLAY, spec.END_PLAY_SET_ERROR) == (
        rig.DRUM_END_SHIM,
        rig.DRUM_END_SHIM_SET_ERROR,
    )
    assert spec.LINEAR_X_BAND == spec.HEAD_LEN_BAND == printed_band_mm(1)
    assert geometry.DRUM_LEN == rig.DRUM_LEN
    assert geometry.STRAP_T_BAND == strap.THICKNESS_BAND
    spec_source = inspect.getsource(spec)
    for literal in (
        "LINEAR_X_BAND = 0.8",
        "HEAD_LEN_BAND = 0.8",
        "END_PLAY = 0.25",
        "END_PLAY_SET_ERROR = 0.10",
        "DRUM_LEN = 143.2",
    ):
        assert literal not in spec_source, literal
    assert (spec.FRONT_JOURNAL_FROM_HEAD_REAR, spec.BACK_JOURNAL_FROM_HEAD_REAR) == (
        pytest.approx(46.3),
        pytest.approx(199.0),
    )
    # The lands did not move in the world when the head grew: 46.8 / 199.5
    # from the old -1.25 rear face.
    assert (spec.FRONT_JOURNAL_Z, spec.BACK_JOURNAL_Z) == (
        pytest.approx(46.8 - 1.25),
        pytest.approx(199.5 - 1.25),
    )
    assert set(spec.LAND_MARGINS_AT_STOPS) == {"drum forward", "drum aft"}
    for margins in spec.LAND_MARGINS_AT_STOPS.values():
        assert set(margins) == set(spec.LAND_ENDS)
        assert min(margins.values()) >= 0.5 - 1e-9
    # One millimetre shorter fails: the derivation picked the smallest length.
    assert spec.land_margin_slack(spec.JOURNAL_LEN - 1.0) < 0.0
    # The drum never binds between the straps.
    assert spec.END_PLAY - spec.END_PLAY_SET_ERROR >= 0.1
    # The drum-end airs are the shim the pinned straps were drilled on.
    assert spec.drum_total_air() == (
        pytest.approx(spec.END_PLAY - spec.END_PLAY_SET_ERROR),
        pytest.approx(spec.END_PLAY + spec.END_PLAY_SET_ERROR),
    )
    # The lands are centred on their straps (to the printed place) with the
    # drum mid-way through its play.
    air = spec.END_PLAY / 2.0
    front_mid = spec.FRONT_JOURNAL_FROM_HEAD_REAR + spec.JOURNAL_LEN / 2.0
    back_mid = spec.BACK_JOURNAL_FROM_HEAD_REAR + spec.JOURNAL_LEN / 2.0
    front_strap_mid = spec.DRUM_STATION - air - geometry.STRAP_T / 2.0
    back_strap_mid = spec.DRUM_STATION + geometry.DRUM_LEN + air + geometry.STRAP_T / 2.0
    assert abs(front_mid - front_strap_mid) <= 0.05 + 1e-9
    assert abs(back_mid - back_strap_mid) <= 0.05 + 1e-9


def test_drum_station_is_a_model_dimension_the_fitup_step_names() -> None:
    """Codex P1 on #814: notes never carry dimensions.  The drum station is
    the model's own reference dimension from the Ø15 head rear face, printed
    at .X with the "DRUM STATION" callout.  Rule 6 (Main's eye pass): the
    drum bond is the pinion fit-up step, so the part note keeps only the
    journal fact."""
    assert spec.DRAWING_NOTES == "JOURNALS RUN IN MHA-056 REAMED BORES."
    assert spec.ASSEMBLY_STEP == (
        "SLIDE MHA-102 INTO MHA-002 AND BOND WITH LOCTITE 638, DRUM FRONT "
        "END AT MHA-102 DRUM STATION; WIPE SQUEEZE-OUT OFF JOURNAL LANDS."
    )
    for text in (spec.DRAWING_NOTES, spec.ASSEMBLY_STEP):
        assert f"{spec.DRUM_STATION:.2f}" not in text
        assert f"{spec.DRUM_STATION_BAND:.1f}" not in text
    assert spec.DRAWING_DIMENSIONS["DrumStationReference"] == {"DrumStationFromHeadRear"}
    assert spec.DRAWING_PRECISION_BY_NAME["DrumStationFromHeadRear"] == 2
    assert drawing.DIMENSION_CALLOUTS["DrumStationFromHeadRear"] == "DRUM STATION"
    assert "DRUM STATION" in spec.ASSEMBLY_STEP
    assert spec.DRUM_STATION_BAND == spec.LINEAR_X_BAND


def test_every_station_names_the_same_head_rear_face() -> None:
    """Fable m1: the head end has two shoulders, so "HEAD SHOULDER" was
    ambiguous for the datum every station runs from."""
    assert "HEAD SHOULDER" not in spec.DRAWING_NOTES
    assert not any("HEAD SHOULDER" in text for text in drawing.DIMENSION_CALLOUTS.values())
    # c3419623 printed "TO  Ø15": <MOD-DIAM> brings its own leading gap.
    assert drawing.DIMENSION_CALLOUTS["BackRimFromHeadRear"] == (
        "FROM BACK CROWN ROOT TO<MOD-DIAM>15 HEAD REAR FACE"
    )


def test_front_journal_diameter_text_clears_the_drum_station_witness() -> None:
    """Run 059b5b0f: the drum station's witness (x 246.0) ran through the
    front land's "Ø8.00 -0.01/-0.03 JOURNAL", whose text hangs left of its
    line.  The line now stands on the land just inside its crown end."""
    x, _ = drawing.PRINCIPAL_KEEP["FrontJournalDia"]
    land_crown_end = drawing._sheet_x(spec.FRONT_JOURNAL_Z + spec.JOURNAL_LEN)
    land_head_end = drawing._sheet_x(spec.FRONT_JOURNAL_Z)
    assert land_crown_end + 0.0008 <= x < land_head_end  # on the land
    right = x + drawing.JOURNAL_DIA_TEXT_OVERHANG
    left = x - 0.026
    assert drawing.DRUM_STATION_WITNESS_X - right >= 0.0025
    # Clear of the bond-zone diameter's line (above the shaft, tail below).
    assert left - drawing.PRINCIPAL_KEEP["BondZoneDia"][0] >= 0.010


def test_drum_station_witness_starts_on_the_flank_not_the_axis() -> None:
    """c3419623: from an axis point the drum station's sheet witness drew a
    4 mm stub inside the Ø8 silhouette that read as a step (Main)."""
    import inspect

    assert part.DRUM_STATION_POINT_X == pytest.approx(spec.SHAFT_DIA / 2.0)
    source = inspect.getsource(part.build)
    call = source[source.index('feature_name="DrumStationReference"') :]
    call = call[: call.index("\n    )")]
    assert "end_on_flank=DRUM_STATION_POINT_X" in call
    helper = inspect.getsource(part._add_axial_reference)
    assert 'far_end = f"{line}.end" if flank is None else f"{flank}.start"' in helper


def test_reference_witnesses_are_drawn_in_the_outline_black() -> None:
    """5471a6ef: both standalone reference sketches' flank witnesses printed in
    the default construction grey over the black Ø8 outline, a break a
    machinist reads as a groove (Main)."""
    import inspect

    assert set(drawing.REFERENCE_WITNESSES) == {"DrumStationReference", "BondZoneReference"}
    assert drawing.REFERENCE_WITNESS_COLOR == 0
    assert drawing.DRUM_STATION_POINT_LEN == part.DRUM_STATION_POINT_LEN
    assert drawing.BOND_ZONE_WITNESS_LEN == part.BOND_ZONE_WITNESS_LEN
    drum = drawing.REFERENCE_WITNESSES["DrumStationReference"]
    assert drum[1] == pytest.approx(spec.HEAD_REAR_Z + spec.DRUM_STATION)
    assert drum[1] - drum[0] == pytest.approx(part.DRUM_STATION_POINT_LEN)
    bond = drawing.REFERENCE_WITNESSES["BondZoneReference"]
    assert bond[0] == pytest.approx(spec.BOND_ZONE_DIA_Z)
    assert bond[1] - bond[0] == pytest.approx(part.BOND_ZONE_WITNESS_LEN)
    helper = inspect.getsource(drawing._blacken_reference_witnesses)
    assert "drawing.SetLineColor(REFERENCE_WITNESS_COLOR)" in helper
    assert "SW_SEL_EXT_SKETCH_SEGS" in helper and "ConstructionGeometry" in helper
    # 7885c0d9: rebinding the ISketch as IFeature read a matrix for Name.
    assert '"IFeature"' not in helper and "segment.GetLength()" in helper
    # w8 (437c56d4c) and w7 (7f7fc1717): the point pick landed on the 227.5
    # BackRimReference line.  The witness is chosen on the model and mapped.
    assert "SelectByID2" not in helper
    assert "_reference_witness_in_view(view, sketch_name, expected)" in helper
    source = inspect.getsource(drawing.build)
    blacken = source.index("_blacken_reference_witnesses(adapter, principal)")
    finalize = source.index("await finalize_drawing(")
    gate = source.index("_assert_outline_unbroken(PNG, witness_spans, sheet_size)")
    assert blacken < finalize < gate


class _FakeSegment:
    def __init__(self, length_mm: float, construction: bool) -> None:
        self.length_mm = length_mm
        self.ConstructionGeometry = construction

    def GetLength(self) -> float:
        return self.length_mm / 1000.0


class _FakeSketch:
    def __init__(self, segments: list[_FakeSegment]) -> None:
        self.segments = segments

    def GetSketchSegments(self) -> tuple[_FakeSegment, ...]:
        return tuple(self.segments)


class _FakeFeature:
    def __init__(self, sketch: _FakeSketch) -> None:
        self.sketch = sketch

    def GetSpecificFeature2(self) -> _FakeSketch:
        return self.sketch


class _FakePart:
    def __init__(self, features: dict[str, _FakeFeature]) -> None:
        self.features = features

    def FeatureByName(self, name: str) -> _FakeFeature | None:
        return self.features.get(name)


class _FakeView:
    def __init__(self, part: _FakePart) -> None:
        self.ReferencedDocument = part
        self.mapped: list[_FakeSegment] = []

    def GetCorresponding(self, segment: _FakeSegment) -> tuple[str, _FakeSegment]:
        self.mapped.append(segment)
        return ("in view", segment)


def test_reference_witness_is_chosen_on_the_model_not_by_a_point_pick() -> None:
    """The user's ruling on the w8/w7 mis-picks: the DrumStationReference
    witness is its sketch's one 1 mm construction segment, mapped into the
    view; the 227.5 BackRimReference line (the old pick's victim) and the
    sketch's own axis centerline can never be chosen."""
    witness = _FakeSegment(part.DRUM_STATION_POINT_LEN, True)
    sketch = _FakeSketch(
        [
            _FakeSegment(spec.DRUM_STATION, True),  # the station's centerline
            witness,
            _FakeSegment(part.DRUM_STATION_POINT_LEN, False),  # not construction
        ]
    )
    back_rim = _FakeSketch([_FakeSegment(spec.BACK_RIM_FROM_HEAD_REAR, True)])
    view = _FakeView(
        _FakePart(
            {
                "DrumStationReference": _FakeFeature(sketch),
                "BackRimReference": _FakeFeature(back_rim),
            }
        )
    )
    chosen = drawing._reference_witness_in_view(
        view, "DrumStationReference", part.DRUM_STATION_POINT_LEN
    )
    assert chosen == ("in view", witness)
    assert view.mapped == [witness]
    with pytest.raises(RuntimeError, match="must be exactly one"):
        drawing._reference_witness_in_view(
            view, "BackRimReference", part.DRUM_STATION_POINT_LEN
        )
    sketch.segments.append(_FakeSegment(part.DRUM_STATION_POINT_LEN, True))
    with pytest.raises(RuntimeError, match="2 construction segments"):
        drawing._reference_witness_in_view(
            view, "DrumStationReference", part.DRUM_STATION_POINT_LEN
        )


def _outline_raster(core: int):
    from PIL import Image, ImageDraw

    # 1 px per mm on a 100 x 50 mm sheet; the outline runs along sheet y = 20.
    raster = Image.new("L", (100, 50), 255)
    pen = ImageDraw.Draw(raster)
    pen.line([(0, 29), (99, 29)], fill=0)
    pen.line([(0, 30), (99, 30)], fill=0)
    pen.line([(40, 29), (44, 29)], fill=core)
    pen.line([(40, 30), (44, 30)], fill=core)
    return raster


def test_outline_raster_check_flags_a_grey_witness_and_passes_black() -> None:
    spans = {"DrumStationReference": ((0.039, 0.020), (0.045, 0.020))}
    grey = drawing._broken_outline_columns(_outline_raster(128), spans, (0.100, 0.050))
    assert grey == {"DrumStationReference": [40, 41, 42, 43, 44]}
    assert drawing._broken_outline_columns(_outline_raster(0), spans, (0.100, 0.050)) == {}


def test_drum_station_text_clears_the_station_stack() -> None:
    """The drum station's text sits left of its drum-end witness: between
    that witness and the head face, the neck-end witness drops through."""
    x, y = drawing.PRINCIPAL_KEEP["DrumStationFromHeadRear"]
    half = drawing.DRUM_STATION_TEXT_WIDTH / 2.0
    drum_end = drawing._sheet_x(spec.HEAD_REAR_Z + spec.DRUM_STATION)
    assert x + half <= drum_end - 0.003
    # Between the 47.4 (above) and 199.9 (below) station lines.
    assert drawing.PRINCIPAL_KEEP["BackJournalFromHeadRear"][1] < y
    assert y < drawing.PRINCIPAL_KEEP["FrontJournalFromHeadRear"][1]
    # The 199.9 text (about 18 mm wide) stays clear of it horizontally.
    back_x = drawing.PRINCIPAL_KEEP["BackJournalFromHeadRear"][0]
    assert back_x + 0.009 + 0.010 <= x - half


def test_drum_station_matches_the_assembled_drum_on_the_arbor() -> None:
    """The drum is bonded at the printed station, so BDT derives ARBOR_Z0 from
    the fit-up stack's drum station (Codex #854/#858 P1) and the assembly
    carries the printed station."""
    import build_drive_train_assembly as assembly

    shoulder_z = assembly.ARBOR_Z0 + spec.HEAD_REAR_Z
    assert assembly.APINION_Z_FRONT - shoulder_z == pytest.approx(spec.DRUM_STATION)


def test_journal_lands_cover_their_straps_in_the_pose() -> None:
    # Codex #854 review (Main): the released "arbor back end at 91.25"
    # landmark became a nominal check ~13.75 clear that could never fire.
    # What matters is that each land covers its strap past both faces in the
    # saved pose; BDT asserts it at import and this pins the pose margins.
    import inspect

    import build_drive_train_assembly as assembly
    import pinion_rig_layout as rig

    faces = (
        (rig.STRAP_Z_OUTER[0], rig.STRAP_Z_INNER[0]),
        (rig.STRAP_Z_INNER[1], rig.STRAP_Z_OUTER[1]),
    )
    margins = []
    for land_z, (lo, hi) in zip((spec.FRONT_JOURNAL_Z, spec.BACK_JOURNAL_Z), faces):
        start = assembly.ARBOR_Z0 + land_z
        margins += [lo - start, start + spec.JOURNAL_LEN - hi]
    assert min(margins) >= spec.MIN_LAND_OVER_STRAP
    # The pose is the drilling set-up: the drum hard on the back strap and
    # the front strap one shim ahead of the drum (Main, #858 ruling 3).
    assert margins == pytest.approx([5.3, 5.7, 5.25, 5.75], abs=5e-3)
    source = inspect.getsource(assembly)
    assert "falls short of the back strap" not in source
    assert "journal land misses its strap" in source


def test_drum_runs_in_the_shim_the_straps_were_drilled_on() -> None:
    # Main (#858, ruling 3): the E-a pins freeze the strap spacing where the
    # shaft is match-drilled, so the drum's running clearance is whatever the
    # drilling set-up leaves.  It is set with the rig's one feeler as a shim at
    # the drum's front end, which MHA-A03's SHAFT DRILL SET prints; the drum
    # then runs in 0.25 +/- 0.10 of end play and never binds.  Before the
    # ruling the straps closed line to line on the drum, and drum_total_air
    # still read the block-stop model (0.0 up to the whole feeler).  The shim
    # is a 0.45 blade, not the rig's 0.25 feeler: the drum keeps its 0.1
    # floor with RIG_MARGIN_SPARE to spare (Main, #858).
    import pinion_rig_layout as rig

    assert spec.drum_total_air() == pytest.approx((0.35, 0.55))
    assert spec.drum_total_air()[0] >= spec.MIN_END_PLAY
    assert rig.STRAP_Z_INNER[1] - rig.STRAP_Z_INNER[0] == pytest.approx(
        rig.DRUM_LEN + 0.45, abs=1e-9
    )
    assert rig.DRUM_BACK_Z == rig.STRAP_Z_INNER[1]
    assert (rig.DRUM_END_SHIM, rig.DRUM_END_SHIM_SET_ERROR) == (
        0.45,
        rig.FRONT_BLOCK_FEELER_BAND,
    )
    assert spec.drum_total_air()[0] - spec.MIN_END_PLAY >= rig.RIG_MARGIN_SPARE - 1e-9
    assert rig.DRUM_FRONT_Z - rig.STRAP_Z_INNER[0] == pytest.approx(rig.DRUM_END_SHIM)
    # The drilling pose is printed where the fitter drills: MHA-A03's
    # SHAFT DRILL SET (Main's re-ruling, 2026-09-26).
    import pinion_rig_fitup as fitup

    assert fitup.SHAFT_DRILL_STEP.split("\n") == [
        "SHAFT DRILL SET: MATCH-DRILL MHA-062 THRU MHA-056 CROSS HOLES, 2 PL,",
        "MHA-062 REAR END FLUSH WITH MHA-061 REAR FACE +/-0.10,",
        "STRAPS ON BACK STOP, MHA-002 ON BACK STRAP,",
        "0.45 FEELER AT MHA-002 FRONT END; DRIVE MHA-145 PINS.",
    ]
    # Both bearing stacks carry the flush setting, and the front one the
    # shim's set error, by name.
    assert rig.TORQUE_SHAFT_BEARING_STACK["MHA-062 rear end flush set"] == -0.10
    assert rig.TORQUE_SHAFT_BACK_BEARING_STACK["MHA-062 rear end flush set"] == -0.10
    assert rig.TORQUE_SHAFT_BEARING_STACK["MHA-062 drum end shim set error"] == -0.10
    assert rig.LIFT_ROD_SEAT_STACK["MHA-062 drum end shim set error"] == -0.10


class _SketchFeature:
    def __init__(self) -> None:
        self.Visible = 2  # swVisibilityState_e: shown


class _PartDoc:
    def __init__(self, names) -> None:
        self.features = {name: _SketchFeature() for name in names}

    def FeatureByName(self, name):  # noqa: N802 - the COM member name
        return self.features.get(name)


def _run_blank(monkeypatch, module, sketches, *, blanks: bool) -> list[str]:
    doc = _PartDoc(sketches)
    blanked: list[str] = []

    def fake_blank(_adapter, name) -> None:
        blanked.append(name)
        if blanks:
            doc.features[name].Visible = 1  # swVisibilityState_e: hidden

    monkeypatch.setattr(module, "blank_sketch", fake_blank)
    monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)
    module.blank_reference_sketches(SimpleNamespace(currentModel=doc), sketches)
    return blanked


def test_every_dimension_carrying_reference_sketch_is_saved_hidden() -> None:
    # #880 (Main, via dtrefactor): the arbor's reference sketches rendered as
    # grey dots and lines in the drive-train; the part saves them hidden.
    expected = {
        "FrontJournalReference",
        "BackJournalReference",
        "BackRimReference",
        "BondZoneReference",
        "DrumStationReference",
        "PinStationReference",
        "OverallReference",
    }
    assert set(spec.REFERENCE_SKETCHES) == expected
    assert len(spec.REFERENCE_SKETCHES) == len(expected)
    assert expected == {name for name in spec.DRAWING_DIMENSIONS if name.endswith("Reference")}
    source = Path(part.__file__).read_text(encoding="utf-8")
    authored = set(re.findall(r'"(\w+Reference)"', source)) | {
        f"{prefix}Reference" for prefix in re.findall(r'prefix="(\w+)"', source)
    }
    assert authored == expected
    blank = "blank_reference_sketches(adapter, REFERENCE_SKETCHES)"
    # One shared helper in _common (restricted review), no local copy.
    assert "def _blank_reference_sketches" not in source
    assert source.count(blank) == 1
    assert source.index(blank) < source.rindex("save_part_and_images(adapter, PART_NAME)")


def test_reference_sketch_blank_reads_every_sketch_back_hidden(monkeypatch) -> None:
    blanked = _run_blank(monkeypatch, _common, spec.REFERENCE_SKETCHES, blanks=True)
    assert blanked == list(spec.REFERENCE_SKETCHES)
    with pytest.raises(RuntimeError, match="FrontJournalReference still visible"):
        _run_blank(monkeypatch, _common, spec.REFERENCE_SKETCHES, blanks=False)


def test_profile_imports_the_hidden_reference_dimensions_per_view() -> None:
    # The profile is a projected view: _drawing_hidden_sketches shows each
    # childless part-hidden owner in that view before its targeted import.
    source = Path(drawing.__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert (
        "from _drawing_hidden_sketches import (\n"
        "    curate_view_dimensions as curate_hidden_owner_dimensions,\n)"
    ) in source
    call = re.search(
        r"(\w+)\(\s*adapter,\s*principal,\s*keep=PRINCIPAL_KEEP,([^)]*)\)", source
    )
    assert call is not None
    assert call.group(1) == "curate_hidden_owner_dimensions"
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in call.group(2)
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    # Every reference sketch prints on the profile, so each one the view shows
    # keeps a dimension there; the donor and detail A dimension none of them,
    # so neither needs the part to show them (no part_sketches_shown).
    reference_dims = set().union(
        *(spec.DRAWING_DIMENSIONS[name] for name in spec.REFERENCE_SKETCHES)
    )
    assert reference_dims <= set(drawing.PRINCIPAL_KEEP)
    assert not reference_dims & (set(drawing.DONOR_KEEP) | set(drawing.DETAIL_KEEP))
    assert "part_sketches_shown" not in source


def test_head_neighbours_are_each_proved_by_a_named_assembly_assert() -> None:
    """Main's ruling on the 11.5 head: every assembly body around the arbor
    head keeps a named clearance assert.  Forward, the crank-arm sweep;
    radially, the T12 chain wheel; aft, the lever throw plane; and the
    swing-rig bodies (lever hub, front pivot block, lift rod, pivot shaft,
    front strap) against the head's own band, which only the crossrod band
    was checked against before."""
    import build_drive_train_assembly as assembly

    source = Path(assembly.__file__).read_text(encoding="utf-8")
    for message in (
        "integral grip-head band reaches the crank arm sweep",
        "integral grip head reaches the T12 chain wheel",
        "lever throw plane reaches the integral grip head",
        'f"integral grip-head band reaches the {_what}"',
        "grip crossrod is not centred in the integral head",
    ):
        assert message in source, message
    head_lo, head_hi = assembly._GRIP_HEAD_Z
    assert head_lo == pytest.approx(
        assembly.ARBOR_Z0 + spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG
    )
    assert head_hi == pytest.approx(assembly.ARBOR_Z0 + spec.NECK_END_Z)
    crank = head_lo - (assembly.CRANK_ARM_Z0 + assembly.ARM_THICKNESS)
    lever_plane = assembly._LEV_Z[0] - head_hi
    names = {what for _lo, _hi, what in assembly._SWING_RIG_BANDS}
    assert names == {
        "lever hub",
        "front pivot block",
        "lift rod",
        "pivot shaft",
        "front strap",
    }
    rig = min(lo - head_hi for lo, _hi, _what in assembly._SWING_RIG_BANDS)
    for margin in (crank, lever_plane, rig):
        assert margin >= 0.25
def test_collar_pin_hole_is_a_drilled_spring_pin_hole_clear_of_the_front_land() -> None:
    """R1a (user, 2026-09-24): the MHA-144 collar's 1/16 in spring-pin hole.

    It prints the rig's functional band (not the title block's drilled-hole
    band), stands at a .X station from the head rear face, never enters the
    front land or its Ra 1.6 run-out at the worst corner, and leaves the U27
    2.0 web target of steel beside it.
    """
    import pinion_arbor_pin_spec as pin_hole
    import pinion_strap_pin_spec as strap_pin

    # One pin family and one drill for the whole rig (pinioncluster's E-a).
    assert pin_hole.PIN_HOLE_DIA == strap_pin.HOLE_DIA == pytest.approx(25.4 / 16.0)
    assert pin_hole.PIN_HOLE_DIA_BAND == strap_pin.HOLE_BAND == (0.06, 0.0)
    assert pin_hole.PIN_HOLE_CALLOUT == strap_pin.DRILL_THRU_CALLOUT
    assert spec.PIN_STATION_FROM_HEAD_REAR == 38.0
    assert spec.PIN_STATION_BAND == spec.LINEAR_X_BAND
    assert spec.PIN_Z == pytest.approx(spec.HEAD_REAR_Z + 38.0)
    assert pin_hole.PIN_HOLE_LAND_CLEARANCE >= 2.0
    assert pin_hole.PIN_HOLE_NECK_CLEARANCE >= 2.0
    assert pin_hole.PIN_HOLE_LIGAMENT_WORST == pytest.approx(3.126, abs=1e-3)
    assert pin_hole.PIN_HOLE_LIGAMENT_WORST >= 2.0
    assert spec.DRAWING_DIMENSIONS["PinHoleProfile"] == {"PinHoleDia"}
    assert spec.DRAWING_DIMENSIONS["PinStationReference"] == {"PinStationFromHeadRear"}
    assert spec.DRAWING_PRECISION_BY_NAME["PinHoleDia"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["PinStationFromHeadRear"] == 1
    assert drawing.DIMENSION_CALLOUTS["PinHoleDia"] == "1/16 DRILL THRU"
    assert drawing.DIMENSION_CALLOUTS["PinStationFromHeadRear"] == "COLLAR PIN"
    assert part.V_PIN_HOLE > 0.0


def test_collar_pin_dimensions_stand_above_the_shaft_clear_of_the_front_ra() -> None:
    """Below the shaft at x 0.269 is the front land's Ra symbol, so the pin
    hole's station and diameter both stand above it: the station over the
    Ø15's text row, the diameter's leader left of the station witness and
    above the 19.0 land length."""
    pin_x = drawing._sheet_x(spec.PIN_Z)
    head_rear_x = drawing._sheet_x(spec.HEAD_REAR_Z)
    axis_y = drawing.PRINCIPAL_CENTER[1]
    station_x, station_y = drawing.PRINCIPAL_KEEP["PinStationFromHeadRear"]
    dia_x, dia_y = drawing.PRINCIPAL_KEEP["PinHoleDia"]
    assert pin_x < station_x < head_rear_x
    assert station_y > drawing.DIAMETER_POSITIONS["HeadDia"][1] + 0.010
    assert dia_x < pin_x
    assert dia_y > station_y + 0.010
    assert dia_y > drawing.PRINCIPAL_KEEP["FrontJournalLen"][1] + 0.030
    assert min(station_y, dia_y) > axis_y


# Measured witness overshoot past a dimension line: c486b6e1's NeckDia line
# at x 294.5 had its witnesses end at 293.5.
WITNESS_OVERSHOOT_M = 0.001


def _neck_text_box(xy: tuple[float, float]) -> tuple[float, float, float, float]:
    left, right, bottom, top = drawing.NECK_DIA_TEXT_BOX_FROM_POSITION
    return xy[0] + left, xy[0] + right, xy[1] + bottom, xy[1] + top


def test_neck_text_box_is_the_audit_box_stacktop_dbe47ae3_measured() -> None:
    # Text at (0.300, 0.194) audited as [284.4,191.2]..[311.5,194.7] mm.
    box = _neck_text_box((0.300, 0.194))
    assert box == pytest.approx((0.2844, 0.3115, 0.1912, 0.1947))


def test_every_profile_diameter_keeps_its_witnesses_inside_the_detail_fence() -> None:
    """A diameter on the 1:1 profile whose part lies inside detail A must
    stand its line on that part, inside the fence: its witnesses run from the
    part to the line and 1 mm past it, and the build's fence gate fails any
    that leaves the circle (c486b6e1: NeckDia's line at x 0.2945, ahead of
    the neck's front shoulder, ran both witnesses out through the fence)."""
    center_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    reach = drawing.DETAIL_RADIUS_MM / 1000.0 + drawing.FENCE_TOL_M
    half = {"HeadDia": spec.HEAD_DIA / 2000.0, "NeckDia": spec.NECK_DIA / 2000.0}
    for name, (x, _) in drawing.DIAMETER_POSITIONS.items():
        far = math.hypot(abs(x - center_x) + WITNESS_OVERSHOOT_M, half[name])
        assert far <= reach, f"{name} witnesses leave the fence ({far * 1000:.2f} mm)"


def test_no_profile_placement_clears_both_the_fence_and_the_collar_pin_witness() -> None:
    """Why the neck left the profile: the fence wants its line at x >= 0.300,
    and the audit box (11.5 mm right of the line) must end short of the
    collar-pin station's head-rear-face witness, which wants x < 0.296."""
    center_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    reach = drawing.DETAIL_RADIUS_MM / 1000.0 + drawing.FENCE_TOL_M
    half = spec.NECK_DIA / 2000.0
    fence_min_x = center_x - (reach**2 - half**2) ** 0.5 + WITNESS_OVERSHOOT_M
    witness_x = drawing._sheet_x(spec.HEAD_REAR_Z)
    witness_max_x = witness_x - drawing.NECK_DIA_TEXT_BOX_FROM_POSITION[1]
    assert fence_min_x > witness_max_x
    assert "NeckDia" not in drawing.DIAMETER_POSITIONS


def test_neck_diameter_is_dimensioned_on_the_neck_inside_detail_a() -> None:
    """Detail A (2:1) holds the neck from the fence to the head rear face.
    The line stands on that stretch, fence side of the end-on circle its
    witnesses start from (Front plane, model z 0), with both witnesses and
    their overshoot inside the crop circle."""
    x, y = drawing.DETAIL_KEEP["NeckDia"]
    assert (x, y) == drawing.NECK_DIA_XY
    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_CROP_RADIUS
    half = drawing.DETAIL_RATIO * spec.NECK_DIA / 2000.0
    # The head centre sits at the detail's centre.
    assert drawing._detail_x(spec.HEAD_CENTER_Z) == pytest.approx(cx)
    head_rear_x = drawing._detail_x(spec.HEAD_REAR_Z)
    neck_sketch_x = drawing._detail_x(0.0)
    assert neck_sketch_x < head_rear_x
    # On the neck, fence side of its end-on circle, with room for the arrows.
    assert x < neck_sketch_x - 0.005
    assert (cx - x) ** 2 + half**2 < radius**2
    # Both witnesses and their overshoot inside the circle, 1 mm to spare.
    far = math.hypot(cx - x + WITNESS_OVERSHOOT_M, half)
    assert far <= radius - 0.001
    # In profile terms the line stands on the neck, inside the 1:1 fence.
    profile_x = drawing._sheet_x(spec.HEAD_CENTER_Z) + (x - cx) / drawing.DETAIL_RATIO
    assert drawing._sheet_x(spec.NECK_END_Z) < profile_x < drawing._sheet_x(spec.HEAD_REAR_Z)
    assert cy + half < y


def test_neck_diameter_text_rides_clear_of_detail_a_and_its_callouts() -> None:
    """The neck's text hangs above-left of the crop circle like the detail's
    other callouts: its audit box stays above the head's top edge, left of
    the SR10.9 leader (which leaves the head's top front corner) and inside
    the sheet border, and the rendered text, left of its line, clears the
    circle.  The collar-pin station witness (stacktop-dbe47ae3) is on the
    profile, not here."""
    xy = drawing.DETAIL_KEEP["NeckDia"]
    left, right, bottom, top = _neck_text_box(xy)
    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_CROP_RADIUS
    head_top = cy + drawing.DETAIL_RATIO * spec.HEAD_DIA / 2000.0
    assert bottom > head_top + 0.003
    assert right < drawing._detail_x(spec.HEAD_FRONT_Z) - 0.010
    # Inner border at y 266.75 mm on this ASME B sheet (a1a694a6 render).
    assert top < 0.265
    # Rendered text: left of its line, ending ~1.3 mm short of it, in the rows
    # the a1a694a6 profile showed (1.9 mm below to 2.0 mm above the position).
    glyph_right, glyph_bottom = xy[0] - 0.0013, xy[1] - 0.0019
    assert math.hypot(cx - glyph_right, glyph_bottom - cy) > radius + 0.002
    # The line leaves the circle square: at its x the circle's top is below
    # the text row, so the jog to the text sits outside the crop.
    circle_top = cy + (radius**2 - (cx - xy[0]) ** 2) ** 0.5
    assert xy[1] - 0.003 > circle_top + 0.002
    # The detail's own callouts sit right of and below the neck text.
    for name in ("HeadCapR", "CrossHoleDia"):
        assert drawing.DETAIL_KEEP[name][0] > right + 0.030
    for name in ("HeadLen", "HeadCapSagDim"):
        assert drawing.DETAIL_KEEP[name][1] < bottom - 0.030


# ---------------------------------------------------------------------------
# Detail A is a cropped 2:1 MODEL view.  On this arbor's native detail view no
# dimension could be moved in under any variant tried (neckbisect-ecef,
# neckref-84e5, and leaf 20260926T141154Z-1-b0f89771, which failed "NeckDia:
# native dimension did not move into target view" on f0faedc51).


def _detail_sheet_point(z_mm: float, r_mm: float) -> tuple[float, float]:
    """Sheet position of the model point at axial station ``z_mm``, ``r_mm``
    off the axis (upwards), inside detail A."""
    return (
        drawing._detail_x(z_mm),
        drawing.DETAIL_CENTER[1] + drawing.DETAIL_RATIO * r_mm / 1000.0,
    )


def test_detail_a_crop_circle_holds_the_neck_and_every_head_reference() -> None:
    """A cropped view drops a dimension whose reference lies outside the crop
    (tipslot-2762), so the crop circle, the 15 mm fence at 2:1 round the head
    centre, holds both ends of the neck's end-on Front-plane circle and every
    head point the detail's dimensions measure, with 2 mm to spare."""
    assert drawing.DETAIL_CROP_RADIUS == pytest.approx(
        drawing.DETAIL_RATIO * drawing.DETAIL_RADIUS_MM / 1000.0
    )
    assert drawing.DETAIL_CROP_RADIUS == pytest.approx(0.030)
    apex_z = spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG
    references = {
        # NeckDia: both ends of the Front-plane circle (model z 0).
        "neck edge upper": (0.0, spec.NECK_DIA / 2.0),
        "neck edge lower": (0.0, -spec.NECK_DIA / 2.0),
        # HeadLen: the Ø15 cylinder's two faces, at the rim.
        "head front rim": (spec.HEAD_FRONT_Z, spec.HEAD_DIA / 2.0),
        "head rear rim": (spec.HEAD_REAR_Z, -spec.HEAD_DIA / 2.0),
        # HeadCapR / HeadCapSagDim: the crown's arc from rim to apex.
        "crown apex": (apex_z, 0.0),
        # CrossHoleDia: the true-circle hole at the head centre.
        "cross-hole edge": (
            spec.HEAD_CENTER_Z - spec.CROSS_HOLE_DIA / 2.0,
            spec.CROSS_HOLE_DIA / 2.0,
        ),
    }
    for name, (z, r) in references.items():
        point = _detail_sheet_point(z, r)
        reach = math.dist(point, drawing.DETAIL_CENTER)
        assert reach <= drawing.DETAIL_CROP_RADIUS - 0.002, (name, reach)
    # The crop shows the neck between the fence and the head rear face.
    fence_x = drawing.DETAIL_CENTER[0] - drawing.DETAIL_CROP_RADIUS
    assert fence_x < _detail_sheet_point(0.0, 0.0)[0]


def test_detail_a_imports_its_dimensions_by_feature_before_any_other_view() -> None:
    """Detail A takes all five of its dimensions by targeted import, from the
    features that own them, before the donor's whole-model import can take
    NeckDia or CrossHoleDia (a dimension on the sheet is not imported again,
    memory model-annotations-import-once)."""
    import _drawing_common as dc

    assert set(drawing.DETAIL_KEEP) == {
        "HeadLen",
        "HeadCapR",
        "HeadCapSagDim",
        "CrossHoleDia",
        "NeckDia",
    }
    owners = dc._features_owning(
        spec.DRAWING_DIMENSIONS, drawing.DETAIL_KEEP, view_label="detail A"
    )
    assert owners == ("CrossHoleProfile", "FrontCapProfile", "Head", "NeckProfile")
    # None is a part-hidden reference sketch, so the plain import needs no
    # per-view show.
    assert not set(owners) & set(spec.REFERENCE_SKETCHES)
    source = inspect.getsource(drawing.build)
    detail = re.search(
        r"curate_view_dimensions\(\s*adapter,\s*detail,\s*keep=DETAIL_KEEP,([^)]*)\)",
        source,
    )
    assert detail is not None
    assert "dimensions_by_feature=DRAWING_DIMENSIONS" in detail.group(1)
    crop = source.index("_cropped_head_view(adapter, principal)")
    assert crop < detail.start() < source.index("keep=DONOR_KEEP")
    assert detail.start() < source.index("keep=PRINCIPAL_KEEP")


def test_no_dimension_is_dragged_into_a_detail_view() -> None:
    """DragModelDimension into this arbor's detail view is dead under every
    variant tried, so the script builds no native detail and its one drag
    helper only ever moves the donor's diameters onto the 1:1 profile."""
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "CreateDetailView" not in source
    assert source.count("DragModelDimension(") == 1
    helper = inspect.getsource(drawing._move_dimension)
    assert "DragModelDimension(" in helper
    build = inspect.getsource(drawing.build)
    targets = re.findall(r"_move_dimension\(\s*adapter,\s*annotation,\s*(\w+),", build)
    assert targets == ["principal"]
    assert set(drawing.DIAMETER_POSITIONS) == set(drawing.DONOR_KEEP) == {"HeadDia"}


def test_detail_a_label_and_letter_read_like_the_native_detail() -> None:
    """A model view has no native label, so the view owns a note in the
    native label's words, centred under its crop circle; the profile's mark
    carries the letter where the native detail put it (pc-p1 render)."""
    assert drawing.DETAIL_LABEL_TEXT == "DETAIL A\nSCALE 2 : 1"
    assert drawing.DETAIL_LETTER == "A"
    cx, cy = drawing.DETAIL_CENTER
    label_x, label_top = drawing.DETAIL_LABEL_XY
    assert label_x == cx
    # Below the crop circle, and below the HeadLen text that rides its edge.
    assert label_top < cy - drawing.DETAIL_CROP_RADIUS - 0.010
    assert drawing.DETAIL_KEEP["HeadLen"][1] - 0.002 - label_top >= 0.004
    # Two text lines (about 12 mm) stay above the profile's bond-zone callout
    # row and the shaft's top edge.
    shaft_top = drawing.PRINCIPAL_CENTER[1] + spec.SHAFT_DIA / 2000.0
    assert label_top - 0.012 > shaft_top + 0.005
    # The letter rides the axis right of the mark circle, clear of the axis
    # end, the Ø15 witnesses' overshoot and the Ø15 text row, inside the sheet.
    fence_x = drawing._sheet_x(spec.HEAD_CENTER_Z)
    letter_x = fence_x + drawing.DETAIL_LETTER_OFFSET[0]
    letter_y = drawing.PRINCIPAL_CENTER[1] + drawing.DETAIL_LETTER_OFFSET[1]
    letter_half = 0.002
    assert letter_x - letter_half > fence_x + drawing.DETAIL_RADIUS_MM / 1000.0 + 0.002
    axis_end = drawing._sheet_x(
        spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG - drawing.AXIS_OVERSHOOT_MM
    )
    assert letter_x - letter_half > axis_end + 0.003
    head_dia_x, head_dia_y = drawing.DIAMETER_POSITIONS["HeadDia"]
    assert letter_x - letter_half > head_dia_x + WITNESS_OVERSHOOT_M + 0.003
    assert letter_y + 0.003 < head_dia_y - 0.010
    assert letter_x + letter_half < 0.410


def test_detail_a_fence_gate_judges_every_detail_dimension_on_its_crop() -> None:
    """The detail's own gate: a diameter across the axis keeps both witnesses
    inside the crop circle, a station along the axis may drop its witnesses
    out to its text, and a dimension line may leave for its text."""
    from _layout_geometry import Segment

    cx, cy = drawing.DETAIL_CENTER
    radius = drawing.DETAIL_CROP_RADIUS
    fence = {"center": (cx, cy), "radius": radius, "axis": (-1.0, 0.0)}
    x, text_y = drawing.DETAIL_KEEP["NeckDia"]
    upper, lower = (
        _detail_sheet_point(0.0, s * spec.NECK_DIA / 2.0)[1] for s in (1, -1)
    )
    start = drawing._detail_x(0.0) - 0.0015
    neck = _fence_dim(
        "NeckDia",
        Segment(start, upper, x - WITNESS_OVERSHOOT_M, upper),
        Segment(start, lower, x - WITNESS_OVERSHOOT_M, lower),
        Segment(x, upper, x, text_y),  # the line, up out of the circle
    )
    neck_arrows = {"NeckDia": ((x, upper), (0.0, -1.0))}
    drawing._assert_witnesses_clear_of_detail_fence([neck], arrows=neck_arrows, **fence)

    front, rear = (
        drawing._detail_x(spec.HEAD_FRONT_Z),
        drawing._detail_x(spec.HEAD_REAR_Z),
    )
    rim = _detail_sheet_point(spec.HEAD_FRONT_Z, -spec.HEAD_DIA / 2.0)[1]
    head_len_y = drawing.DETAIL_KEEP["HeadLen"][1]
    station = _fence_dim(
        "HeadLen",
        Segment(front, rim, front, head_len_y - 0.001),
        Segment(rear, rim, rear, head_len_y - 0.001),
        Segment(rear, head_len_y, front, head_len_y),
    )
    station_arrows = {"HeadLen": ((rear, head_len_y), (1.0, 0.0))}
    drawing._assert_witnesses_clear_of_detail_fence(
        [station], arrows=station_arrows, **fence
    )

    # f0faedc51's neck line on the 1:1 profile, replayed at 2:1: the line
    # ahead of the neck runs both witnesses out through the circle.
    outside = cx - radius - 0.004
    stray = _fence_dim(
        "NeckDia",
        Segment(start, upper, outside - WITNESS_OVERSHOOT_M, upper),
        Segment(start, lower, outside - WITNESS_OVERSHOOT_M, lower),
        Segment(outside, upper, outside, text_y),
    )
    with pytest.raises(RuntimeError, match="NeckDia' extension-line"):
        drawing._assert_witnesses_clear_of_detail_fence(
            [stray], arrows={"NeckDia": ((outside, upper), (0.0, -1.0))}, **fence
        )


def test_view_dimensions_reads_only_one_views_dimensions() -> None:
    from _layout_geometry import AnnotationGeometry

    owned = AnnotationGeometry(label="NeckDia", kind="dim", owner="Drawing View4")
    other = AnnotationGeometry(label="HeadDia", kind="dim", owner="Drawing View2")
    note = AnnotationGeometry(label="DETAIL A", kind="note", owner="Drawing View4")
    sheets = [SimpleNamespace(annotations=[owned, other, note])]
    assert drawing._view_dimensions(sheets, "Drawing View4") == [owned]


# --- seat fakes: the cropped view, the profile mark and the notes -----------


class _DoubleArray(tuple):
    """What the fake double_array hands COM: a bare list must never reach
    CreatePoint or SetViewPosition (a real seat reads it as zeros)."""


def _require_double_array(values, what: str) -> None:
    if not isinstance(values, _DoubleArray):
        raise TypeError(f"{what} got {type(values).__name__}, not a double_array")


class _Point:
    def __init__(self, xyz) -> None:
        self.ArrayData = tuple(xyz)

    def MultiplyTransform(self, transform):  # noqa: N802 - the COM member name
        return _Point(transform(self.ArrayData))


class _Utility:
    def CreatePoint(self, xyz):  # noqa: N802 - the COM member name
        _require_double_array(xyz, "CreatePoint")
        return _Point(xyz)


class _ViewSketch:
    # A sheet point maps to its view-sketch point x1000 (any affine map works).
    ModelToSketchTransform = staticmethod(lambda xyz: tuple(v * 1000.0 for v in xyz))


class _Segment:
    def __init__(self, seat: "_ArborSeat", keep_colour: bool = True) -> None:
        self.seat = seat
        self.keep_colour = keep_colour
        self._color = 0x0000FF

    @property
    def Color(self):  # noqa: N802 - the COM member name
        return self._color

    @Color.setter
    def Color(self, value):  # noqa: N802 - the COM member name
        if self.keep_colour:
            self._color = value


class _ArborView:
    """IView stand-in: model z maps to sheet x leftwards at ``scale`` when the
    view is turned -90 deg like the profile, upwards when it is not."""

    def __init__(self, name: str, seat: "_ArborSeat", scale: float, **kw) -> None:
        self.name = name
        self.seat = seat
        self.ScaleRatio = (scale, 1.0)
        self.Angle = kw.get("angle", 0.0)
        self.Position = kw.get("position", (0.2, 0.17))
        self.cropped = kw.get("cropped", True)
        self.turns = kw.get("turns", True)
        self.status = kw.get("status", 1)

    def __setattr__(self, name, value):
        if name == "Angle" and not getattr(self, "turns", True):
            return
        super().__setattr__(name, value)

    def sheet_point(self, xyz) -> tuple[float, float]:
        along = -self.ScaleRatio[0] * xyz[2]
        # 0.05 m between the view's Position and the model origin.
        if abs(math.remainder(self.Angle + math.pi / 2.0, 2.0 * math.pi)) < 1e-9:
            return (self.Position[0] + along + 0.05, self.Position[1])
        return (self.Position[0], self.Position[1] - along + 0.05)

    def SetViewPosition(self, position, move_children):  # noqa: N802
        _require_double_array(position, "SetViewPosition")
        self.seat.log.append(("move", self.name, tuple(position), move_children))
        self.Position = tuple(position)
        return True

    def GetSketch(self):  # noqa: N802
        return _ViewSketch()

    def Crop2(self, jagged, no_outline, intensity):  # noqa: N802
        self.seat.log.append(("crop2", self.name, jagged, no_outline, intensity))
        return self.status

    def IsCropped(self):  # noqa: N802
        return self.cropped

    def UpdateViewDisplayGeometry(self):  # noqa: N802
        return True

    def GetOutline(self):  # noqa: N802
        cx, cy = drawing.DETAIL_CENTER
        r = drawing.DETAIL_CROP_RADIUS
        if not self.cropped:
            return (-0.2, cy - r, 0.5, cy + r)
        return (cx - r, cy - r, cx + r, cy + r)

    def GetNotes(self):  # noqa: N802
        return tuple(note for note in self.seat.notes if note.owner == self.name)


class _NoteAnnotation:
    def __init__(self, note: "_ArborNote") -> None:
        self.note = note

    def GetPosition(self):  # noqa: N802
        return (*self.note.anchor, 0.0)

    def SetPosition2(self, x, y, z):  # noqa: N802
        if self.note.moves:
            self.note.anchor = (x, y)
        return True


class _ArborNote:
    """A note whose rendered box hangs from its anchor, like a top-left
    attached note: 2.5 mm per character wide, 4 mm per line tall."""

    def __init__(self, text: str, owner: str, x: float, y: float, moves: bool) -> None:
        self.text = text
        self.owner = owner
        self.anchor = (x, y)
        self.moves = moves

    def GetText(self):  # noqa: N802
        return self.text

    def GetAnnotation(self):  # noqa: N802
        return _NoteAnnotation(self)

    def GetExtent(self):  # noqa: N802
        lines = self.text.split("\n")
        width = 0.0025 * max(len(line) for line in lines)
        x, y = self.anchor
        return (x, y - 0.004 * len(lines), 0.0, x + width, y, 0.0)


class _ArborSeat:
    """IModelDoc2 + IDrawingDoc + ISketchManager + ISheet + adapter, recorded."""

    def __init__(self, *, notes_move: bool = True, keep_colour: bool = True) -> None:
        self.log: list[tuple] = []
        self.notes: list[_ArborNote] = []
        self.active = ""
        self.notes_move = notes_move
        self.keep_colour = keep_colour
        self.AddToDB = False
        self.currentModel = self
        self.SketchManager = self
        self.swApp = self

    def GetMathUtility(self):  # noqa: N802
        return _Utility()

    def ActivateView(self, name):  # noqa: N802
        self.log.append(("activate", name))
        self.active = name
        return True

    def ClearSelection2(self, _all):  # noqa: N802
        return True

    def EditRebuild3(self):  # noqa: N802
        return True

    def CreateCircle(self, *xyz):  # noqa: N802
        self.log.append(
            ("circle", self.active, tuple(v / 1000.0 for v in xyz), self.AddToDB)
        )
        return _Segment(self, self.keep_colour)

    def CreateDetailViewAt4(self, *args):  # noqa: N802
        raise AssertionError("detail A must not be a native detail view")

    def GetCurrentSheet(self):  # noqa: N802
        return self

    def SetScale(self, *args):  # noqa: N802
        return True


def _arbor_seat(monkeypatch, **kw):
    seat = _ArborSeat(
        notes_move=kw.pop("notes_move", True), keep_colour=kw.pop("keep_colour", True)
    )
    principal = _ArborView(
        "Drawing View2", seat, 1.0, angle=-math.pi / 2.0, position=(0.2, 0.17)
    )
    detail = _ArborView(
        "Drawing View4", seat, 2.0, position=drawing.DETAIL_CENTER, **kw
    )
    placed: list[tuple] = []

    def place(adapter, source, orientation, x, y, *, scale=None):
        placed.append((orientation, x, y, scale))
        return detail

    def note(adapter, text, x, y, **_kwargs):
        made = _ArborNote(text, seat.active, x, y, seat.notes_move)
        seat.notes.append(made)
        seat.log.append(("note", seat.active, text))
        return made

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _name: obj)
    monkeypatch.setattr(drawing, "double_array", lambda values: _DoubleArray(values))
    monkeypatch.setattr(drawing, "place_view", place)
    monkeypatch.setattr(
        drawing,
        "model_point_in_view",
        lambda adapter, view, xyz, *, label: view.sheet_point(xyz),
    )
    monkeypatch.setattr(drawing, "view_name", lambda adapter, view: view.name)
    monkeypatch.setattr(drawing, "add_note", note)
    return seat, principal, detail, placed


def test_detail_a_is_a_cropped_2_to_1_model_view_turned_like_the_profile(
    monkeypatch,
) -> None:
    seat, principal, detail, placed = _arbor_seat(monkeypatch)
    assert drawing._cropped_head_view(seat, principal) is detail
    assert placed == [("*Top", *drawing.DETAIL_CENTER, drawing.DETAIL_SCALE)]
    assert detail.Angle == principal.Angle == -math.pi / 2.0
    # Moved once, so the head centre lands where detail A sits.
    moves = [entry for entry in seat.log if entry[0] == "move"]
    assert len(moves) == 1 and moves[0][3] is False
    head = detail.sheet_point((0.0, 0.0, spec.HEAD_CENTER_Z / 1000.0))
    assert head == pytest.approx(drawing.DETAIL_CENTER)
    # The crop circle is sketched in detail A itself, centred on the head at
    # the fence's 2:1 radius, still selected (not direct-to-database), and
    # Crop2 runs straight after it.
    kinds = [entry[0] for entry in seat.log]
    assert kinds[-3:] == ["activate", "circle", "crop2"]
    assert seat.log[-3] == ("activate", "Drawing View4")
    _, owner, xyz, add_to_db = seat.log[-2]
    assert owner == "Drawing View4" and add_to_db is False
    cx, cy, _, px, py, _ = xyz
    assert (cx, cy) == pytest.approx(drawing.DETAIL_CENTER)
    assert math.dist((cx, cy), (px, py)) == pytest.approx(drawing.DETAIL_CROP_RADIUS)
    assert seat.log[-1] == ("crop2", "Drawing View4", False, False, 5)
    assert seat.AddToDB is False


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        ({"cropped": False}, "not cropped"),
        ({"status": 2}, "not cropped"),
        ({"turns": False}, "turn detail A"),
    ],
)
def test_detail_a_fails_loud_when_the_crop_or_the_turn_did_not_take(
    monkeypatch, kw, match
) -> None:
    seat, principal, _detail, _placed = _arbor_seat(monkeypatch, **kw)
    with pytest.raises(RuntimeError, match=match):
        drawing._cropped_head_view(seat, principal)


def test_profile_marks_detail_a_with_a_black_fence_circle(monkeypatch) -> None:
    seat, principal, _detail, _placed = _arbor_seat(monkeypatch)
    center = drawing._mark_detail_on_profile(seat, principal)
    head = principal.sheet_point((0.0, 0.0, spec.HEAD_CENTER_Z / 1000.0))
    assert center == pytest.approx(head)
    circles = [entry for entry in seat.log if entry[0] == "circle"]
    assert len(circles) == 1
    _, owner, xyz, add_to_db = circles[0]
    assert owner == "Drawing View2" and add_to_db is True
    cx, cy, _, px, py, _ = xyz
    assert (cx, cy) == pytest.approx(head)
    assert math.dist((cx, cy), (px, py)) == pytest.approx(
        drawing.DETAIL_RADIUS_MM / 1000.0
    )
    assert seat.AddToDB is False  # restored
    seat_grey, principal_grey, _d, _p = _arbor_seat(monkeypatch, keep_colour=False)
    with pytest.raises(RuntimeError, match="colour did not persist"):
        drawing._mark_detail_on_profile(seat_grey, principal_grey)


def test_detail_a_label_and_letter_are_owned_and_centred(monkeypatch) -> None:
    seat, principal, detail, _placed = _arbor_seat(monkeypatch)
    mark = (0.3132, 0.170)
    drawing._label_detail(seat, detail, principal, mark)
    owned = [(note.owner, note.text) for note in seat.notes]
    assert owned == [
        ("Drawing View4", drawing.DETAIL_LABEL_TEXT),
        ("Drawing View2", drawing.DETAIL_LETTER),
    ]
    label, letter = (drawing._note_box(note, label="t") for note in seat.notes)
    assert (label[0] + label[2]) / 2.0 == pytest.approx(drawing.DETAIL_LABEL_XY[0])
    assert label[3] == pytest.approx(drawing.DETAIL_LABEL_XY[1])
    assert (letter[0] + letter[2]) / 2.0 == pytest.approx(
        mark[0] + drawing.DETAIL_LETTER_OFFSET[0]
    )
    assert (letter[1] + letter[3]) / 2.0 == pytest.approx(
        mark[1] + drawing.DETAIL_LETTER_OFFSET[1]
    )


def test_detail_a_label_fails_loud_when_it_does_not_move(monkeypatch) -> None:
    seat, principal, detail, _placed = _arbor_seat(monkeypatch, notes_move=False)
    with pytest.raises(RuntimeError, match="did not centre"):
        drawing._label_detail(seat, detail, principal, (0.3132, 0.170))


def test_detail_a_label_fails_loud_when_it_lands_in_another_view(monkeypatch) -> None:
    seat, principal, detail, _placed = _arbor_seat(monkeypatch)
    monkeypatch.setattr(seat, "ActivateView", lambda name: True)  # stays inactive
    with pytest.raises(RuntimeError, match="did not land in its view"):
        drawing._label_detail(seat, detail, principal, (0.3132, 0.170))

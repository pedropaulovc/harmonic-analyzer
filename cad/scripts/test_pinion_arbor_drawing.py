"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

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
    assert {"HeadDia", "NeckDia"} == set(drawing.DONOR_KEEP)
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_integral_arbor_keeps_the_released_stations_around_a_longer_head() -> None:
    # Rule 12 (audit W6): the head grows 9.0 -> 10.5 about the released
    # crossrod station; the neck shoulder, shaft and back crown stay put.
    assert spec.HEAD_CENTER_Z == pytest.approx(-6.5)
    assert spec.HEAD_FRONT_Z == pytest.approx(-11.75)
    assert spec.HEAD_REAR_Z == pytest.approx(-1.25)
    assert spec.NECK_END_Z == pytest.approx(10.0)
    assert spec.SHAFT_LEN == pytest.approx(226.25)
    assert spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG == pytest.approx(-14.75)
    assert spec.SHAFT_LEN + spec.BACK_CAP_SAG == pytest.approx(227.45)
    assert spec.OVERALL_LEN == pytest.approx(242.2)
    assert spec.EXPOSED_SHAFT_LEN == pytest.approx(216.25)
    assert spec.BACK_RIM_FROM_HEAD_REAR == pytest.approx(227.5)


def test_crossrod_hole_is_centred_with_a_rule_12_web() -> None:
    # Printed centred on the head length: only HeadLen's .X band reaches the
    # web, never a separate station band.
    assert "CrossHoleReference" not in spec.DRAWING_DIMENSIONS
    assert "CENTRED ON HEAD LENGTH" in spec.CROSS_HOLE_CALLOUT
    assert spec.CROSS_HOLE_WEB_WORST == pytest.approx(1.80)
    assert spec.CROSS_HOLE_WEB_WORST >= 1.5


def test_integral_head_owns_the_crossrod_interface() -> None:
    assert spec.HEAD_DIA == pytest.approx(15.0)
    assert spec.HEAD_LEN == pytest.approx(10.5)
    assert spec.NECK_DIA == pytest.approx(10.5)
    assert spec.NECK_LEN == pytest.approx(11.25)
    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is spec.CROSS_HOLE_CALLOUT
    assert callout == "REAM THRU,\nCENTRED ON HEAD LENGTH"
    # Fable r-delta (Main ruling B): MHA-058's bond and acceptance are
    # instructions for a part not on this print; MHA-058 carries both.
    assert "MHA-058" not in spec.DRAWING_NOTES
    assert "SHALL NOT TURN OR SLIDE BY HAND" in crossrod.DRAWING_NOTES


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
    assert "BOND INTO MHA-102 HEAD WITH LOCTITE 638." in crossrod.DRAWING_NOTES
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
    detail_left = drawing.DETAIL_LABEL_XY[0] - 0.017
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
    assert (drawing.DETAIL_LABEL_XY[0] - 0.017) - (symbol_x + right) >= 0.005
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
    detail_r = drawing.DETAIL_RADIUS_MM * 2 / 1000.0
    near_x = max(left - detail_x, 0.0, detail_x - right)
    near_y = max(bottom - detail_y, 0.0, detail_y - top)
    assert (near_x**2 + near_y**2) ** 0.5 - detail_r >= 0.010
    assert left - (drawing.DETAIL_LABEL_XY[0] + 0.017) >= 0.010
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
    assert spec.DRUM_STATION == pytest.approx(61.55)
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
        pytest.approx(46.8),
        pytest.approx(199.5),
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


def test_drum_station_is_a_model_dimension_the_note_only_names() -> None:
    """Codex P1 on #814: notes never carry dimensions.  The drum station is
    the model's own reference dimension from the Ø15 head rear face, printed
    at .X with the "DRUM STATION" callout the note points to."""
    assert spec.DRAWING_NOTES.splitlines() == [
        "JOURNALS RUN IN MHA-056 REAMED BORES.",
        "SHAFT SLIPS INTO MHA-002; BOND WITH LOCTITE 638, DRUM FRONT END",
        "  AT DRUM STATION. WIPE SQUEEZE-OUT OFF JOURNAL LANDS.",
    ]
    assert f"{spec.DRUM_STATION:.2f}" not in spec.DRAWING_NOTES
    assert f"{spec.DRUM_STATION_BAND:.1f}" not in spec.DRAWING_NOTES
    assert spec.DRAWING_DIMENSIONS["DrumStationReference"] == {"DrumStationFromHeadRear"}
    assert spec.DRAWING_PRECISION_BY_NAME["DrumStationFromHeadRear"] == 2
    assert drawing.DIMENSION_CALLOUTS["DrumStationFromHeadRear"] == "DRUM STATION"
    assert "DRUM STATION" in spec.DRAWING_NOTES
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
    assert "_select_reference_witness(" in helper
    select = inspect.getsource(drawing._select_reference_witness)
    assert "SW_SEL_EXT_SKETCH_SEGS" in select and "ConstructionGeometry" in select
    # 7885c0d9: rebinding the ISketch as IFeature read a matrix for Name.
    assert '"IFeature"' not in select and "segment.GetLength()" in select
    # pc-p1s: a coordinate pick is seat-dependent; witnesses select by name.
    assert 'SelectByID2(\n            ""' not in helper + select
    source = inspect.getsource(drawing.build)
    blacken = source.index("_blacken_reference_witnesses(adapter, principal)")
    finalize = source.index("await finalize_drawing(")
    gate = source.index("_assert_outline_unbroken(PNG, witness_spans, sheet_size)")
    assert blacken < finalize < gate


class _WitnessSegment:
    def __init__(self, length_mm: float, construction: bool = True) -> None:
        self._length = length_mm / 1000.0
        self.ConstructionGeometry = construction

    def GetLength(self) -> float:
        return self._length


class _WitnessDrawing:
    """Resolves only NAMED sketch-segment selections, as a name-first
    SelectByID2 does; an unnamed coordinate pick selects nothing."""

    def __init__(self, segments: dict) -> None:
        self.segments = segments
        self.selected = None
        self.names = []
        self.Extension = self
        self.SelectionManager = self

    def ClearSelection2(self, _all) -> None:
        self.selected = None

    def SelectByID2(self, name, kind, x, y, z, append, mark, callout, option) -> bool:
        self.names.append(name)
        self.selected = self.segments.get(name) if kind == "EXTSKETCHSEGMENT" else None
        return self.selected is not None

    def GetSelectedObjectType3(self, index, mark) -> int:
        return drawing.SW_SEL_EXT_SKETCH_SEGS

    def GetSelectedObject6(self, index, mark):
        return self.selected


def _witness_seat(monkeypatch, segments: dict):
    monkeypatch.setattr(
        drawing, "_model_item_paths", lambda adapter, view: (("pinion-arbor-1", "Drawing View2"),)
    )
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    draw = _WitnessDrawing(segments)
    return SimpleNamespace(currentModel=draw), draw


def test_a_witness_is_selected_by_name_and_identified_by_its_length(monkeypatch) -> None:
    """pc-p1s: the coordinate pick resolved the drum station's 227.5 mm axial
    line; the named walk skips it and keeps the 1 mm construction witness."""
    qualifier = "DrumStationReference@pinion-arbor-1@Drawing View2"
    adapter, draw = _witness_seat(
        monkeypatch,
        {
            f"Line1@{qualifier}": _WitnessSegment(227.5),
            f"Line2@{qualifier}": _WitnessSegment(1.0),
        },
    )
    picked = drawing._select_reference_witness(adapter, None, "DrumStationReference", 1.0)
    assert picked == f"Line2@{qualifier}"
    assert draw.selected is draw.segments[picked]


def test_a_witness_no_name_resolves_fails_naming_what_was_tried(monkeypatch) -> None:
    qualifier = "DrumStationReference@pinion-arbor-1@Drawing View2"
    adapter, draw = _witness_seat(
        monkeypatch,
        {
            f"Line1@{qualifier}": _WitnessSegment(227.5),
            f"Line2@{qualifier}": _WitnessSegment(1.0, construction=False),
        },
    )
    with pytest.raises(RuntimeError, match=r"Line1@.*227\.500 mm.*Line2@.*construction=False"):
        drawing._select_reference_witness(adapter, None, "DrumStationReference", 1.0)
    assert draw.selected is None
    assert len(draw.names) == drawing.REFERENCE_WITNESS_CANDIDATES


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
    # the drum's front end, which MHA-062's drilling note prints; the drum
    # then runs in 0.25 +/- 0.10 of end play and never binds.  Before the
    # ruling the straps closed line to line on the drum, and drum_total_air
    # still read the block-stop model (0.0 up to the whole feeler).  The shim
    # is a 0.45 blade, not the rig's 0.25 feeler: the drum keeps its 0.1
    # floor with RIG_MARGIN_SPARE to spare (Main, #858).
    import pinion_pivot_shaft_spec as shaft
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
    # The drilling pose is printed on the part that is drilled.
    callout = shaft.PIN_HOLE_CALLOUT.split("\n")
    assert callout == [
        "MATCH-DRILL THRU AT ASSEMBLY",
        "IN MHA-056 CROSS HOLES, 2 PL:",
        "REAR END FLUSH WITH MHA-061 REAR FACE +/-0.10,",
        "STRAPS ON BACK STOP, MHA-002 ON BACK STRAP,",
        "0.45 FEELER AT MHA-002 FRONT END",
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

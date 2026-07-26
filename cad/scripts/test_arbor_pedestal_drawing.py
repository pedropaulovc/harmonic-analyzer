"""Offline contracts for the arbor-pedestal drawing."""

from __future__ import annotations

import re
from pathlib import Path

import arbor_pedestal_spec
import build_arbor_pedestal as part
import draw_arbor_pedestal as drawing
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/arbor-pedestal.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/arbor-pedestal.pdf")
    assert drawing.PNG.as_posix().endswith("/png/arbor-pedestal_drawing.png")
    assert (
        DRAWINGS_BY_NAME["arbor_pedestal"].script
        == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is arbor_pedestal_spec.DRAWING_DIMENSIONS
    marked = set().union(*arbor_pedestal_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert marked == {
        "Width", "Depth", "FootHt", "BoreDia", "DomeDia"
    }


def test_arbor_bore_closes_the_configured_running_fit() -> None:
    import _config

    assert round(arbor_pedestal_spec.BORE_DIA, 3) == 9.525
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == "+0.055/+0.025 THRU"
    assert "BoreHeight" not in drawing.DIMENSION_CALLOUTS
    assert "Depth" not in drawing.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_PRECISION["BoreDia"] == 3
    assert "ARBOR BORE LIMITS" not in arbor_pedestal_spec.DRAWING_NOTES
    shaft_limits = (9.505, 9.525)
    bore_limits = (9.550, 9.580)
    clearances = (
        bore_limits[0] - shaft_limits[1],
        bore_limits[1] - shaft_limits[0],
    )
    expected = tuple(_config.fit("shaft_in_bushing", "diametral_clearance_mm"))
    assert tuple(round(value, 3) for value in clearances) == expected


def test_screw_clearance_tracks_the_hole_resolver() -> None:
    """The hand-pinned diameter must equal what the hole resolver would give.

    ``arbor_pedestal_spec`` keeps ``SCREW_CLEARANCE_DIA`` as a LITERAL on
    purpose -- it is a pure-data module, and importing ``_holes`` would pull
    ``_common``/``_telemetry`` into its dependency closure and re-key both the
    part and the drawing. The cost of that choice is a duplicated constant, and
    this duplicate has now drifted twice (3.2512 <-> 3.264), each time only
    surfacing when a real rebuild replaced a remote-cache restore.

    A test can import both without touching the part's closure, so the drift is
    pinned here instead: the literal, ``_holes.CLEARANCE_MM``, and the seat's
    own wizard table (``#4`` normal = 0.1285 in) must all agree.
    """
    import _holes

    assert arbor_pedestal_spec.SCREW_CLEARANCE_DIA == _holes.CLEARANCE_MM[("#4", "normal")]
    # 0.1285 in is the seat's Screw Clearances row, read via
    # diagnostics/diag_hole_wizard_tables.py -- the authority the build asserts
    # against. Rounded to the resolver's 3 dp.
    assert round(0.1285 * 25.4, 3) == arbor_pedestal_spec.SCREW_CLEARANCE_DIA


def test_no_dead_band_between_wizard_correction_and_the_builder_assert() -> None:
    """What the wizard will FORCE must cover what the builder will ACCEPT.

    These were two different literals -- `_holes` only corrected a drift over
    0.05 mm, while `build_arbor_pedestal` rejected anything over 0.005. A #4
    clearance initialized at 3.2512 instead of 3.264 drifts 0.0128 and lands in
    the gap: the wizard leaves it, the builder refuses it, and NO value of the
    spec pin can satisfy both. It read as the seat's table "moving" and cost
    three flip-flops of the pin before Codex spotted the real mechanism on #422.

    Both now read one constant. This test fails if they are ever separated
    again, including by someone tightening only the builder's side.
    """
    import _holes

    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "DIAMETER_TOLERANCE_MM" in source, "builder must use the shared tolerance"
    # Any numeric literal compared against the cut diameter re-opens the band.
    # Regex rather than a fixed string so `>0.005`, `> 0.0050` and friends are
    # caught too -- a whitespace variant slipping through would defeat the gate.
    assert not re.search(r"[<>]=?\s*0\.0*5\b|[<>]=?\s*0\.005\d*", source), (
        "builder compares the cut diameter against a numeric literal; use "
        "_holes.DIAMETER_TOLERANCE_MM so the wizard's correction threshold and "
        "this acceptance threshold cannot separate into a dead band again"
    )

    holes_source = Path(_holes.__file__).read_text(encoding="utf-8")
    assert "abs(initialized_dia_mm - pinned_dia_mm) > DIAMETER_TOLERANCE_MM" in holes_source

    # The tolerance must sit strictly between the benign rounding gap (the
    # 0.0001 between CLEARANCE_MM's 3.264 and the live 3.2639 -- writing there
    # would corrupt swHoleThru 25 into 26) and the wrong-row drift it must
    # catch (3.264 vs ("#3","loose") 3.251 = 0.0128).
    rounding_gap = abs(3.2639 - _holes.CLEARANCE_MM[("#4", "normal")])
    wrong_row_drift = abs(
        _holes.CLEARANCE_MM[("#4", "normal")] - _holes.CLEARANCE_MM[("#3", "loose")]
    )
    assert rounding_gap < _holes.DIAMETER_TOLERANCE_MM < wrong_row_drift


def test_notes_specify_part_requirements_without_title_block_duplicates() -> None:
    notes = arbor_pedestal_spec.DRAWING_NOTES
    assert "MATING ARBOR LIMITS DIA 9.505-9.525 (REF)" in notes
    assert "STRAP NEAR/FAR FACES" in notes
    assert "RESULTING STRAP THICKNESS 10.00 REF" in notes
    assert "MATERIAL" not in notes
    assert "JAPANNED" not in notes
    assert "DATUM A" in notes
    assert "X.XX" not in notes
    assert "BREAK EDGES" not in notes
    assert "MACHINE FROM CONTINUOUS-CAST STOCK" in notes
    assert "DATUM B IS LEFT FOOT SIDE FACE SHOWN" in notes
    assert "2X STRAIGHT FLANKS JOIN BOXED 24.00 X 5.00 FOOT TOP CORNERS" in notes
    assert "NO TANGENCY" in notes
    assert "BOXED 12.00 LOCATES BOTH BORE AND FLANGE-HOLE AXES" in notes
    assert "BOXED 6.00/16.00 LOCATE STRAP NEAR/FAR FACES FROM D" in notes
    assert "DIMENSIONS AND GD&T APPLY BEFORE COATING" in notes
    assert "MASK ARBOR BORE" in notes
    # 3.26: the seat's wizard-table value for #4 NORMAL (0.1285 in = 3.2639),
    # which the sheet's native hole callout also prints -- so masking note and
    # callout agree. See the spec's pin rationale for why the 3.25 reading was
    # a wrong-row artefact rather than a different seat.
    assert "DIA 3.26\nHOLE" in notes
    assert "FOOT SEAT A, LEFT SIDE B" in notes
    assert "PROFILE-CONTROLLED SURFACES" in notes
    assert "25-50 um" not in notes
    assert "TWO COATS" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)' in source
    assert "add_native_hole_callout(" in source
    assert 'label="flange-hole location from datum D"' in source


def test_bore_dome_and_mounting_hole_have_inspectable_gdt() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'datum="A"' in source
    assert 'datum="B"' in source
    assert 'datum="D"' in source
    assert 'characteristic="position"' in source
    assert 'characteristic="profile_surface"' in source
    assert 'quantity="CROWN + 2 FLANKS + FOOT TOP + RIGHT SIDE"' in source
    assert 'quantity="DATUM D FACE"' in source
    assert 'datums=("A", "B", "D")' in source
    assert "leader_attach_xy=" in source
    assert 'characteristic="flatness"' in source
    assert 'characteristic="perpendicularity"' in source
    assert source.count("_add_circle_basic(") == 4  # helper plus three calls
    assert 'orientation="horizontal"' in source
    assert 'orientation="vertical"' in source
    assert "set_arc_endpoints_to_center(" in source
    assert 'label="flange-hole true position"' in source
    assert 'roughness_ra="1.6"' in source
    assert 'for name in ("Width", "FootHt"):' in source
    assert 'label="far-face depth coordinate"' in source
    assert 'label="strap near-face profile"' in source
    assert 'label="coplanar far-face profile"' in source
    assert "flank_rise = BORE_HEIGHT - FOOT_HEIGHT" in source
    assert "(FOOT_WIDTH / 2.0 - TOP_RADIUS) * flank_rise / BORE_HEIGHT" in source
    common_source = Path(drawing.__file__).with_name("_drawing_common.py").read_text(
        encoding="utf-8"
    )
    assert 'display.SetText(_DIMENSION_TEXT_CALLOUT_BELOW, "")' in common_source
    assert "BASIC dimension retained below-text" in common_source
    notes = arbor_pedestal_spec.DRAWING_NOTES
    assert "CYLINDRICAL ZONE" not in notes
    assert "FINISH RA" not in notes


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert drawing.FRONT_CENTER == (0.100, 0.150)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("scale=(2, 1)") == 3  # elevation + plan + pictorial
    assert "frame_xy=(0.185, 0.080)" in source
    assert "frame_xy=(0.020, 0.105)" in source


def test_part_stamps_make_critical_properties() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    config = _config.parts("arbor-pedestal")
    assert "A48" in str(config["material_specification"])
    assert "A48" in str(config["material"])
    finish = str(config["finish"]).lower()
    assert "sspc-sp3" in finish
    assert "black japan varnish" in finish
    assert "2 coats" in finish
    assert "25-50um dft" in finish
    assert "mask" not in finish
    # Two identical castings: the south pedestal plus the north one rotated
    # 180 about Y (build_drive_train_assembly places both).
    assert int(config["quantity"]) == 2

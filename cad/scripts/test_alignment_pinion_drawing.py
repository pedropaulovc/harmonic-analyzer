"""Offline contracts for retained alignment-pinion manufacturing data."""

from __future__ import annotations

import math

import pytest

import _config
import alignment_pinion_spec as spec
import pinion_arbor_spec as arbor


def test_gear_data_block_preserves_the_actual_base_chord_profile() -> None:
    data = spec.GEAR_DATA
    assert spec.TEETH == 32
    assert spec.TEETH == int(_config.machine("alignment_pinion", "teeth"))
    assert "NUMBER OF TEETH:  32" in data
    for field in (
        "DIAMETRAL PITCH",
        "MODULE",
        "PRESSURE ANGLE",
        "PITCH DIAMETER",
        "MIN CHORD-FLOOR DIAMETER (mm, REF):  15.780",
        "AS-CUT RADIAL TOOTH DEPTH (mm, REF):  0.777",
        f"TOOTH FORM:  {spec.BASE_CHORD_ROOT_FORM}",
    ):
        assert field in data, field
    assert "FULL DEPTH" not in data
    assert "WHOLE DEPTH" not in data
    assert "X.XX" not in data


def test_bore_has_the_single_machined_finish_contract() -> None:
    assert len(spec.SURFACE_FINISHES) == 1
    (finish,) = spec.SURFACE_FINISHES
    assert finish.key == "drum_bore"
    assert finish.roughness_um == 1.6
    assert finish.face.diameter_mm == 8.0


def test_bonded_slip_fit_clears_the_mha102_journal_within_the_bond_gap() -> None:
    shaft_limits = (
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1],
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[1],
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[0],
    )
    # The drum bonds onto MHA-102's bond zone, not its journal lands (U39).
    assert arbor.SHAFT_DIA_BAND != arbor.JOURNAL_DIA_BAND
    assert bore_limits == pytest.approx((8.00, 8.10))
    # A stock 8 mm H7 reamer (8.000-8.015) lands inside the band.
    assert bore_limits[0] <= 8.000 and 8.015 <= bore_limits[1]
    minimum_clearance = bore_limits[0] - shaft_limits[1]
    maximum_clearance = bore_limits[1] - shaft_limits[0]
    assert minimum_clearance == pytest.approx(
        spec.ARBOR_BORE_BAND[1] - arbor.SHAFT_DIA_BAND[0]
    )
    assert minimum_clearance >= 0.0  # the drum still slides on by hand
    assert maximum_clearance == pytest.approx(
        spec.ARBOR_BORE_BAND[0] - arbor.SHAFT_DIA_BAND[1]
    )
    assert maximum_clearance < spec.RETAINING_COMPOUND_MAX_GAP_MM
    assert spec.BORE_DIA == arbor.SHAFT_DIA  # the CAD models line-to-line


def test_notes_bond_the_drum_and_locate_it_from_the_back_end() -> None:
    notes = spec.DRAWING_NOTES
    # Rule 6 (R3): three notes -- the bond and its axial location merged, the
    # MHA-102 journal size left to MHA-102's own sheet -- plus the generated
    # MHA-102 bond-zone line (#814) as the fourth.
    assert sum(not line.startswith("  ") for line in notes.splitlines()) == 4
    assert "MHA-102 BOND ZONE: DIA 8.00 +0.00/-0.10 (REF)." in notes
    assert "ARBOR JOURNAL" not in notes
    assert (
        "ON ASSEMBLY: BOND TO MHA-102 WITH LOCTITE 638, LOCATED FROM\n"
        "  THE END AT THE LAST MHA-027 GEAR (j=19)." in notes
    )
    assert "MATES WITH CYLINDER-GEAR BANK" not in notes
    for retired in ("INTERFERENCE", "MATCHED FIT", "ENSURES FULL ENGAGEMENT", "+/-0.5"):
        assert retired not in notes, retired


def test_part_metadata_preserves_material_finish_quantity() -> None:
    config = _config.parts("alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "end faces polished; bore as reamed; teeth as cut"
    assert int(config["quantity"]) == 1


class _FakeNote:
    def __init__(self, linked: str, resolved: str) -> None:
        self.PropertyLinkedText = linked
        self._resolved = resolved

    def GetText(self) -> str:
        return self._resolved


class _FakeDrawing:
    def __init__(self) -> None:
        self.rebuilds = 0

    def ForceRebuild3(self, top_only: bool) -> bool:
        self.rebuilds += 1
        return True


def test_material_readback_rebuilds_before_comparing_resolved_text() -> None:
    import draw_alignment_pinion as draw

    linked = 'MATERIAL: $PRPSHEET:"Material Specification"'
    resolved = "MATERIAL: C36000 free-machining brass"
    drawing = _FakeDrawing()
    draw._verify_title_material_specification(
        drawing, (_FakeNote(linked, resolved), linked, resolved)
    )
    assert drawing.rebuilds == 1


def test_material_readback_names_the_unresolved_text() -> None:
    import draw_alignment_pinion as draw

    linked = 'MATERIAL: $PRPSHEET:"Material Specification"'
    with pytest.raises(RuntimeError, match="got 'MATERIAL: '"):
        draw._verify_title_material_specification(
            _FakeDrawing(),
            (
                _FakeNote(linked, "MATERIAL: "),
                linked,
                "MATERIAL: C36000 free-machining brass",
            ),
        )


def test_tooth_thickness_is_controlled_by_the_model_base_tangent_span() -> None:
    k = spec.BASE_TANGENT_SPAN_TEETH
    # Unroll the model's own base-circle tooth: k tooth arcs plus k-1 pitches.
    unrolled = spec._BASE_RADIUS * (
        2.0 * spec._BASE_TOOTH_HALF_ANGLE + (k - 1) * 2.0 * math.pi / spec.TEETH
    )
    assert spec.BASE_TANGENT_SPAN == pytest.approx(unrolled, abs=1e-9)
    contact_r = math.hypot(spec._BASE_RADIUS, spec.BASE_TANGENT_SPAN / 2.0)
    assert spec._BASE_RADIUS < contact_r < spec.OUTSIDE_DIA / 2.0
    assert abs(contact_r - spec.PITCH_DIA / 2.0) < 0.05
    assert spec.BASE_TANGENT_SPAN_BAND == (0.0, -0.100)
    assert "BASE-TANGENT SPAN, OVER 3 TEETH (mm):  3.964 +0.000/-0.100" in spec.GEAR_DATA


def test_fit_bore_callout_names_its_process() -> None:
    import draw_alignment_pinion as draw

    assert draw.DIMENSION_CALLOUTS["ArborBoreDia"] == "REAM THRU"


def test_od_at_the_general_band_keeps_tip_clearance_and_contact() -> None:
    """The .XX (+/-0.51) OD band is functionally enough for the 120T mesh."""
    import cylinder_gear_spec as gear

    general = 0.51
    alpha = math.radians(spec.PRESSURE_ANGLE_DEG)
    inv = math.tan(alpha) - alpha
    engaged_c2c = float(_config.machine("alignment_pinion", "engaged_center_distance_mm"))
    gear_base_r = gear.TEETH * spec.MODULE_MM * math.cos(alpha) / 2.0
    gear_floor_r = gear_base_r * math.cos(
        math.pi / gear.TEETH - (math.pi / (2.0 * gear.TEETH) + inv)
    )
    gear_tip_r = gear.OUTSIDE_DIA / 2.0
    # The base-chord gap floor stops the 120T tips 0.24 short of standard depth;
    # U28 (user, 2026-09-23) parks the drum 0.2425 further out so the swing
    # lands exactly there -- the configured engaged centre distance IS the
    # seated one.
    seated_c2c = gear_tip_r + spec.MIN_CHORD_FLOOR_DIA / 2.0
    assert seated_c2c - engaged_c2c == pytest.approx(0.0, abs=1e-5)

    def contact_ratio(c2c: float, tip_r: float) -> float:
        working = math.acos((spec._BASE_RADIUS + gear_base_r) / c2c)
        path = (
            math.sqrt(tip_r**2 - spec._BASE_RADIUS**2)
            + math.sqrt(gear_tip_r**2 - gear_base_r**2)
            - c2c * math.sin(working)
        )
        return path / (math.pi * spec.MODULE_MM * math.cos(alpha))

    for c2c in (engaged_c2c, seated_c2c):
        largest_tip_r = (spec.OUTSIDE_DIA + general) / 2.0
        smallest_tip_r = (spec.OUTSIDE_DIA - general) / 2.0
        assert c2c - largest_tip_r - gear_floor_r > 0.20
        assert contact_ratio(c2c, smallest_tip_r) > 1.1

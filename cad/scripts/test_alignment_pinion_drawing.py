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


def test_mha102_fit_band_has_a_valid_intersection_at_both_shaft_limits() -> None:
    shaft_limits = (
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[1],
        arbor.SHAFT_DIA + arbor.SHAFT_DIA_BAND[0],
    )
    bore_limits = (
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[1],
        spec.BORE_DIA + spec.ARBOR_BORE_BAND[0],
    )
    assert shaft_limits == pytest.approx((7.98, 8.00))
    assert bore_limits == pytest.approx((7.96, 7.98))

    minimum_interference, maximum_interference = (
        spec.ARBOR_DIAMETRAL_INTERFERENCE_MM
    )
    assert (minimum_interference, maximum_interference) == pytest.approx(
        (0.010, 0.030)
    )
    assert 0.0 < minimum_interference < maximum_interference

    for shaft_dia in shaft_limits:
        bore_for_max_interference = shaft_dia - maximum_interference
        bore_for_min_interference = shaft_dia - minimum_interference
        overlap_low = max(bore_limits[0], bore_for_max_interference)
        overlap_high = min(bore_limits[1], bore_for_min_interference)
        assert overlap_low < overlap_high


def test_part_metadata_preserves_material_finish_quantity() -> None:
    config = _config.parts("alignment-pinion")
    assert config["material_specification"] == "C36000 free-machining brass"
    assert config["finish"] == "polished brass; tooth surfaces as cut"
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

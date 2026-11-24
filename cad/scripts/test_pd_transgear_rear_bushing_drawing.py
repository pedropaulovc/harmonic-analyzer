"""Offline contracts for the transgear rear bushing (MHA-PD-24) and its drawing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import build_pd_transgear_rear_bushing as part
import draw_pd_transgear_rear_bushing as drawing
import transgear_cluster_fit as fit
import pd_transgear_pin_spec as pin
import pd_transgear_rear_bushing_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
from _inch_wall_limits import WALL_TARGET_MM
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pd-transgear-rear-bushing.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pd-transgear-rear-bushing.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pd-transgear-rear-bushing_drawing.png")
    row = DRAWINGS_BY_NAME["pd_transgear_rear_bushing"]
    assert row.script == Path(drawing.__file__).resolve()
    assert row.layout is DrawingLayout.LANDSCAPE
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.END_KEEP) | set(drawing.PROFILE_KEEP) == marked
    assert not set(drawing.END_KEEP) & set(drawing.PROFILE_KEEP)
    assert spec.REFERENCE_DIMENSIONS == frozenset()
    assert set(drawing.PROFILE_KEEP) == {"RingLength"}


def test_the_bore_prints_no_band_and_the_length_the_title_block() -> None:
    """Fit audit 2026-11-23: the reamed bore prints the reamer's size with
    no band (the pin is turned last to it); the length only feeds the
    shimmed end float (#2124)."""
    assert model_toleranced_dimensions(part) == {}
    assert spec.BORE_PLACES == 3


def test_the_bore_runs_on_the_pin_and_names_it() -> None:
    """drawing-guidelines.md rule 4 (fit audit 2026-11-23): a reamed bore
    prints size, REAM, the mate, the acceptance by the mate and one line
    saying what the fit protects; no band, no clearance.
    drawing-guidelines.md rule 12 (hole and slot callouts say what to do): the fit bore's process is REAM."""
    low, high = fit.BORE_DIAMETRAL_CLEARANCE
    assert 0.0 < low < high
    assert spec.BORE_DIA == fit.BORE_DIA == pytest.approx(0.1260 * 25.4)
    assert spec.BORE_DIA_BAND == fit.BORE_DIA_BAND
    callout = drawing.DIMENSION_CALLOUTS["BoreDia"]
    assert callout.splitlines() == [
        "REAM THRU, RUNNING FIT",
        f"{pin.PIN_NUMBER} PIN ENTERS, NO SHAKE",
        "KEEPS MHA-PD-10 END FLOAT OPEN",
    ]
    assert not re.search(r"\d*\.\d", callout)
    # What the necessity answer states: cocked on the pin at the modelled
    # fit, the bushing takes up less than the sleeve's least end float; a
    # drilled #30's clearance (.1285 +.004/0 on the smallest pin) would not.
    assert spec.BORE_COCK_TAKE_UP < fit.RING_FLOAT_RANGE[0]
    drilled = (0.1285 + 0.004) * 25.4 - pin.DIA_MIN
    assert spec.BORE_COCK_TAKE_UP * drilled / high > fit.RING_FLOAT_RANGE[0]


def test_wall_holds_the_target_at_the_printed_worst_case() -> None:
    worst = (
        spec.OD
        - printed_band_mm(spec.OD_PLACES, unit=spec.UNIT)
        - (spec.BORE_DIA + spec.BORE_DIA_BAND[0])
    ) / 2.0
    assert worst >= WALL_TARGET_MM


def test_the_title_block_length_leaves_the_float_open_for_the_shims() -> None:
    """#2124: at the title block's .XXX the shortest bushing leaves the
    unshimmed float over the floor and the longest gap takes the most shims
    the fit-up allows."""
    assert spec.LENGTH == fit.REAR_BUSHING_LENGTH
    assert fit.REAR_BUSHING_LENGTH_BAND == printed_band_mm(3, unit=spec.UNIT)
    assert spec.DRAWING_PRECISION_BY_NAME["RingLength"] == fit.LENGTH_PLACES == 3
    assert fit.UNSHIMMED_FLOAT_RANGE[0] >= fit.END_FLOAT_MIN
    assert fit.SHIM_COUNT_RANGE[1] <= fit.SHIM_COUNT_MAX
    assert drawing.DIMENSION_CALLOUTS["RingLength"] == spec.LENGTH_CALLOUT


def test_only_the_sleeve_thrust_face_carries_a_finish() -> None:
    """The MHA-PD-10 sleeve turns on the front face; the arm face seats on
    the shims at the title block's finish."""
    (control,) = spec.SURFACE_FINISHES
    assert control.key == "sleeve_face"
    assert control.roughness_um == MACHINED_UM
    assert (tuple(control.face.normal), control.face.offset_mm) == (
        (0.0, 0.0, 1.0),
        spec.LENGTH,
    )
    assert set(drawing.FACE_FINISHES) == {"sleeve_face"}
    assert _config.parts("pd-transgear-feed-pinion")["number"] in (
        spec.THRUST_FACE_CAPTION
    )


def test_face_symbols_attach_to_their_own_end_of_the_lathe_profile() -> None:
    """The profile turns *Top a quarter turn, so model +Z runs LEFT: the arm
    face (z 0) is the right end, the sleeve face the left end."""
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    centre_x = drawing.PROFILE_CENTER[0]

    def sheet_x(z_mm: float) -> float:
        return centre_x - (z_mm - spec.LENGTH / 2.0) * scale

    assert drawing.PROFILE_ANGLE == pytest.approx(-0.5 * 3.141592653589793)
    faces = {control.key: control.face for control in spec.SURFACE_FINISHES}
    for key, (pick, _symbol) in drawing.FACE_FINISHES.items():
        assert pick[0] == pytest.approx(sheet_x(faces[key].offset_mm))
        radius = abs(pick[1] - drawing.PROFILE_CENTER[1]) / scale
        assert spec.BORE_DIA / 2.0 < radius < spec.OD / 2.0


def test_sheet_text_stays_short() -> None:
    for text in drawing.DIMENSION_CALLOUTS.values():
        lines = text.splitlines()
        assert len(lines) <= 4
        assert all(len(line) <= 70 for line in lines)


def test_registry_row_is_the_turned_brass_mha_180() -> None:
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PD-24"
    assert int(row["quantity"]) == 1
    assert "C36000" in row["material_specification"]
    assert row["material"] == part.MATERIAL
    assert row["tolerance_class"] == "machined_block"

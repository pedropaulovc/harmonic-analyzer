"""MISUMI HOK40-HC8 feed handwheel (MHA-CH-06-TL-VN-57) contracts, SolidWorks-free."""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_vn_oblique_handwheel as part
import ch_rocker_arm_tl_vn_oblique_handwheel_spec as spec
import ch_rocker_arm_tl_vn_oblique_leadscrew_spec as feed
import draw_ch_rocker_arm_tl_vn_oblique_handwheel as draw
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from _holes import cross_hole_volume_mm3

STEM = "ch-rocker-arm-tl-vn-oblique-handwheel"
NAME = "ch_rocker_arm_tl_vn_oblique_handwheel"
ROW = _config.parts(STEM)


def _numeric_revolve(profile, n: int = 4000) -> float:
    """Revolve a closed (r, y) polygon by slicing each edge into frusta."""
    volume = 0.0
    for (r0, y0), (r1, y1) in zip(profile, profile[1:] + profile[:1]):
        for i in range(n):
            t0, t1 = i / n, (i + 1) / n
            ra, rb = r0 + t0 * (r1 - r0), r0 + t1 * (r1 - r0)
            dy = (y1 - y0) / n
            volume += math.pi * dy * (ra * ra + ra * rb + rb * rb) / 3.0
    return abs(volume)


def _numeric_corner_round(
    corner_r: float, rho: float, outward: bool, n: int = 4000
) -> float:
    """The ring a round sweeps, by integrating the spandrel over its width."""
    volume = 0.0
    for i in range(n):
        s = (i + 0.5) / n * rho  # distance in from the corner along one leg
        height = rho - math.sqrt(rho * rho - (rho - s) ** 2)
        radius = corner_r - s if outward else corner_r + s
        volume += 2.0 * math.pi * radius * height * rho / n
    return volume


def test_registry_row_is_the_purchased_misumi_handwheel() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-57"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "MISUMI"
    assert ROW["supplier_skus"] == [spec.SKU] == ["HOK40-HC8"]
    assert ROW["material"] == spec.MATERIAL
    assert int(ROW["quantity"]) == spec.QUANTITY == 1
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    assert spec.SKU in (spec.__doc__ or "")
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert spec.INVENTORY_ID == "fixtures.trammel-handwheel"


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.HUB_DIA == feed.HANDWHEEL_HUB_DIA
    assert spec.HUB_LENGTH == feed.HANDWHEEL_HUB_LENGTH
    assert spec.WHEEL_DIA == feed.HANDWHEEL_WHEEL_DIA
    assert spec.WHEEL_LENGTH == feed.HANDWHEEL_WHEEL_LENGTH
    assert spec.BODY_LENGTH == feed.HANDWHEEL_BORE_LENGTH == spec.WHEEL_FACE_Y
    assert spec.BORE_DIA == feed.SCREW_MAJOR_DIA
    assert spec.GRIP_OFFSET == feed.HANDWHEEL_GRIP_OFFSET
    assert spec.SET_SCREW_THREAD == feed.HANDWHEEL_GRUB
    assert spec.SET_SCREW_STATION == feed.HANDWHEEL_GRUB_FROM_HUB
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in ("HUB_DIA", "HUB_LENGTH", "WHEEL_DIA", "WHEEL_LENGTH", "GRIP_OFFSET"):
        assert re.search(rf"^{name} = feed\.", source, re.MULTILINE), name


def test_vendor_grip_encloses_the_catalogue_grip() -> None:
    # The vendor STEP's grip (Ø14 max, 21 proud) against C4's catalogue
    # values (Ø13, 18.8, 43.8 overall): reported to C4, modelled as the STEP.
    assert spec.CATALOGUE_GRIP_DIA == feed.HANDWHEEL_GRIP_DIA
    assert spec.CATALOGUE_LENGTH == feed.HANDWHEEL_LENGTH
    assert spec.GRIP_DIA >= spec.CATALOGUE_GRIP_DIA
    assert spec.GRIP_LENGTH >= spec.CATALOGUE_GRIP_LENGTH
    assert spec.LENGTH == spec.WHEEL_FACE_Y + spec.GRIP_LENGTH >= spec.CATALOGUE_LENGTH
    assert spec.SWEEP_R >= feed.HANDWHEEL_SWEEP_R


def test_set_screw_taps_are_plain_minor_bores() -> None:
    import _hole_spec

    assert (
        f"{spec.SET_SCREW_THREAD}x{spec.SET_SCREW_PITCH:g}"
        not in _hole_spec.TAP_DRILL_MM
    )
    assert spec.SET_SCREW_MINOR_DIA == pytest.approx(4.134, abs=5e-4)  # the vendor hole
    assert spec.SET_SCREW_COUNT == len(spec.SET_SCREW_DIRECTIONS) == len(part.TAPS) == 2
    # Front sketches u = x, Right sketches u = -z; the profile runs along -u.
    planes = {
        direction: plane
        for (_, plane), direction in zip(part.TAPS, spec.SET_SCREW_DIRECTIONS)
    }
    assert planes == {(-1.0, 0.0): "Front", (0.0, 1.0): "Right"}
    assert all(u <= 0.0 for u, _ in spec.TAP_PROFILE)
    assert min(u for u, _ in spec.TAP_PROFILE) < -spec.HUB_DIA / 2.0
    # The closing edge lies on the tap's axis (the revolve centerline).
    assert spec.TAP_PROFILE[-1][1] == spec.TAP_PROFILE[0][1] == spec.SET_SCREW_STATION


def test_volume_matches_numeric_integration() -> None:
    d = spec.SET_SCREW_MINOR_DIA
    tap = (
        cross_hole_volume_mm3(d, spec.HUB_DIA) - cross_hole_volume_mm3(d, spec.BORE_DIA)
    ) / 2.0
    assert spec.TAP_VOLUME_MM3 == pytest.approx(tap, rel=1e-5)
    assert spec.WHEEL_VOLUME_MM3 == pytest.approx(
        _numeric_revolve(spec.WHEEL_PROFILE), rel=1e-6
    )
    assert spec.GRIP_VOLUME_MM3 == pytest.approx(
        _numeric_revolve(spec.GRIP_PROFILE), rel=1e-6
    )
    hub_r = spec.HUB_DIA / 2.0
    assert spec.HUB_END_FILLET_MM3 == pytest.approx(
        _numeric_corner_round(hub_r, spec.HUB_FILLET, True), rel=1e-4
    )
    assert spec.HUB_CORNER_FILLET_MM3 == pytest.approx(
        _numeric_corner_round(hub_r, spec.HUB_FILLET, False), rel=1e-4
    )
    assert spec.GRIP_END_ROUND_MM3 == pytest.approx(
        _numeric_corner_round(spec.GRIP_DIA / 2.0, spec.GRIP_END_ROUND, True), rel=1e-4
    )


def test_volume_matches_the_vendor_step_less_the_explained_detail() -> None:
    # Native minus the vendor's omitted detail (collar flats, grip-socket
    # void) is the vendor wheel-plus-grip volume; the residual is the STEP's
    # rounded socket/shank diameters.
    explained = spec.GRIP_FLATS_MM3 + spec.GRIP_SOCKET_VOID_MM3
    assert spec.GRIP_FLATS_MM3 == pytest.approx(32.70, abs=0.01)
    assert spec.GRIP_SOCKET_VOID_MM3 == pytest.approx(7.73, abs=0.01)
    assert spec.VOLUME_MM3 - explained == pytest.approx(spec.VENDOR_VOLUME_MM3, abs=0.5)
    assert spec.VENDOR_STEP_SHA256 in (spec.__doc__ or "")


def test_mass_agrees_with_the_catalogue_weight() -> None:
    grip = spec.GRIP_VOLUME_MM3 - spec.GRIP_END_ROUND_MM3
    wheel = spec.VOLUME_MM3 - grip
    grams = (wheel * spec.WHEEL_DENSITY + grip * spec.GRIP_DENSITY) / 1000.0
    assert grams == pytest.approx(spec.MASS_G, rel=0.05)


def test_build_sketches_the_spec_profiles() -> None:
    assert part.wheel_points() == list(spec.WHEEL_PROFILE)
    assert part.grip_points()[0] == (spec.GRIP_OFFSET, spec.WHEEL_FACE_Y)
    assert part.grip_points()[-1] == (spec.GRIP_OFFSET, spec.LENGTH)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'volume_check(adapter, "handwheel", VOLUME_MM3' in source
    assert "publish_screw_axis(adapter)" in source


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
    assert set(imports) <= {
        "__future__",
        "_config",
        "math",
        "ch_rocker_arm_tl_vn_oblique_leadscrew_spec",
    }


def test_sheet_is_the_registered_purchased_part_reference(monkeypatch) -> None:
    sheet = DRAWINGS_BY_NAME[NAME]
    assert (sheet.part, sheet.artifact_stem, sheet.script_name) == (
        NAME,
        STEM,
        f"draw_{NAME}.py",
    )
    assert sheet.layout is DrawingLayout.LANDSCAPE
    assert sheet.artifact_stem == part.PART_NAME
    calls = []

    async def fake(adapter, drawn, *, item, cut_to_suit=False, number_fit=None):
        calls.append((adapter, drawn, item, cut_to_suit, number_fit))
        return {"pdf": "x"}

    monkeypatch.setattr(draw, "build_purchased_part_drawing", fake)
    adapter = object()
    assert asyncio.run(draw.build(adapter)) == {"pdf": "x"}
    # The 18-character number is fitted to its DWG. NO. cell, clear of REV.
    assert calls == [(adapter, sheet, draw.ITEM, False, draw.NumberFit.SHRINK_TO_CELL)]
    assert "HANDWHEEL" in draw.ITEM


def test_note_is_one_short_line_naming_the_leadscrew_by_its_drawing_number() -> None:
    note = spec.DRAWING_NOTES
    number = _config.parts("ch-rocker-arm-tl-vn-oblique-leadscrew")["number"]
    assert spec.LEADSCREW_NUMBER == number
    assert "\n" not in note and len(note) <= 80
    assert f"LEADSCREW {number}" in note
    # The number is the only digits the note carries.
    assert not re.search(r"\d", note.replace(number, ""))

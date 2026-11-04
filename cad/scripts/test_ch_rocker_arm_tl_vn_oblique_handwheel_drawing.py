"""HARFINGTON 50 mm feed handwheel (MHA-CH-06-TL-VN-57) contracts, SolidWorks-free."""

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
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DrawingLayout
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


def test_registry_row_is_the_purchased_amazon_handwheel() -> None:
    assert ROW["number"] == "MHA-CH-06-TL-VN-57"
    assert ROW["process"] == "purchased"
    assert ROW["supplier"] == spec.SUPPLIER == "Amazon (sold by HARFINGTON)"
    assert ROW["supplier_skus"] == [spec.SKU] == ["B0DJ3DZT86"]
    assert ROW["material"] == spec.MATERIAL
    assert int(ROW["quantity"]) == spec.QUANTITY == 1
    # One line in the title block's MATERIAL cell; the provenance is the spec's.
    assert len(ROW["material_specification"]) <= 36
    doc = spec.__doc__ or ""
    assert f"https://www.amazon.com/dp/{spec.SKU}" in doc
    assert part.STOCK_PROPERTIES == {
        "Stock Name": ROW["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }
    assert spec.INVENTORY_ID == "fixtures.trammel-handwheel"


def test_c4_values_are_imported_not_retyped() -> None:
    assert spec.HUB_DIA == feed.HANDWHEEL_HUB_DIA == 26.0
    assert spec.HUB_LENGTH == feed.HANDWHEEL_HUB_LENGTH == 14.0
    assert spec.WHEEL_DIA == feed.HANDWHEEL_WHEEL_DIA == 50.0
    assert spec.WHEEL_LENGTH == feed.HANDWHEEL_WHEEL_LENGTH == 13.0
    assert spec.BORE_LENGTH == feed.HANDWHEEL_BORE_LENGTH
    assert spec.BORE_DIA == feed.SCREW_MAJOR_DIA
    assert spec.GRIP_OFFSET == feed.HANDWHEEL_GRIP_OFFSET
    assert spec.GRIP_DIA == feed.HANDWHEEL_GRIP_DIA
    assert spec.GRIP_LENGTH == feed.HANDWHEEL_GRIP_LENGTH
    assert spec.LENGTH == feed.HANDWHEEL_LENGTH
    assert spec.SET_SCREW_THREAD == feed.HANDWHEEL_GRUB
    assert spec.SET_SCREW_STATION == feed.HANDWHEEL_GRUB_FROM_HUB
    source = Path(spec.__file__).read_text(encoding="utf-8")
    for name in (
        "HUB_DIA",
        "HUB_LENGTH",
        "WHEEL_DIA",
        "WHEEL_LENGTH",
        "BORE_LENGTH",
        "GRIP_OFFSET",
        "GRIP_DIA",
        "GRIP_LENGTH",
        "LENGTH",
        "SET_SCREW_STATION",
    ):
        assert re.search(rf"^{name} = feed\.", source, re.MULTILINE), name


def test_listing_envelope_hub_rim_and_overall() -> None:
    # The listing: OD 50, "Height: 27mm", "Step Overall Dimension: 26 x 14mm".
    assert spec.WHEEL_FACE_Y == spec.HUB_LENGTH + spec.WHEEL_LENGTH == 27.0
    radii = [r for r, _ in spec.WHEEL_PROFILE]
    stations = [y for _, y in spec.WHEEL_PROFILE]
    assert max(radii) == spec.WHEEL_DIA / 2.0
    assert (min(stations), max(stations)) == (0.0, spec.WHEEL_FACE_Y)
    # The hub's OD runs from the hub end to the rim, nowhere past it.
    hub = [(r, y) for r, y in spec.WHEEL_PROFILE if r == spec.HUB_DIA / 2.0]
    assert sorted(y for _, y in hub) == [0.0, spec.HUB_LENGTH]
    # The handle envelope: 52 overall, sweeping inside the rim's radius 25.
    assert spec.LENGTH == spec.WHEEL_FACE_Y + spec.GRIP_LENGTH == 52.0
    assert spec.GRIP_OFFSET + spec.GRIP_DIA / 2.0 <= spec.WHEEL_DIA / 2.0
    assert spec.SWEEP_R == feed.HANDWHEEL_SWEEP_R == spec.WHEEL_DIA / 2.0


def test_bore_is_blind_to_the_guaranteed_hub_depth() -> None:
    """The listing's photos show no hole in the rim's outer face: the bore
    stops at the hub's 14, and the leadscrew's engagement stays short of it."""
    assert spec.BORE_LENGTH == spec.HUB_LENGTH
    r_bore = spec.BORE_DIA / 2.0
    bore = [(r, y) for r, y in spec.WHEEL_PROFILE if r == r_bore]
    assert sorted(y for _, y in bore) == [0.0, spec.BORE_LENGTH]
    # The revolve's closing edge lies on the axis, behind the bore's bottom.
    (r0, y0), (r1, y1) = spec.WHEEL_PROFILE[-1], spec.WHEEL_PROFILE[0]
    assert (r0, r1) == (0.0, 0.0)
    assert (y0, y1) == (spec.BORE_LENGTH, spec.WHEEL_FACE_Y)
    assert feed.HANDWHEEL_ENGAGEMENT_MIN <= feed.HANDWHEEL_ENGAGEMENT < spec.BORE_LENGTH


def test_set_screw_taps_are_plain_minor_bores_in_the_hub() -> None:
    import _hole_spec

    assert (
        f"{spec.SET_SCREW_THREAD}x{spec.SET_SCREW_PITCH:g}"
        not in _hole_spec.TAP_DRILL_MM
    )
    assert spec.SET_SCREW_MINOR_DIA == pytest.approx(4.134, abs=5e-4)
    # "Comes with two screws to secure the shaft": one tap each.
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
    # The whole tap lies inside the hub and over the bore.
    half = spec.SET_SCREW_MINOR_DIA / 2.0
    assert 0.0 < spec.SET_SCREW_STATION - half
    assert spec.SET_SCREW_STATION + half < spec.BORE_LENGTH <= spec.HUB_LENGTH


def test_volume_matches_closed_form_and_numeric_integration() -> None:
    d = spec.SET_SCREW_MINOR_DIA
    tap = (
        cross_hole_volume_mm3(d, spec.HUB_DIA) - cross_hole_volume_mm3(d, spec.BORE_DIA)
    ) / 2.0
    assert spec.TAP_VOLUME_MM3 == pytest.approx(tap, rel=1e-5)
    assert spec.WHEEL_VOLUME_MM3 == pytest.approx(
        _numeric_revolve(spec.WHEEL_PROFILE), rel=1e-6
    )
    hub = math.pi * ((spec.HUB_DIA / 2.0) ** 2 - (spec.BORE_DIA / 2.0) ** 2)
    rim = math.pi * (spec.WHEEL_DIA / 2.0) ** 2
    assert spec.WHEEL_VOLUME_MM3 == pytest.approx(
        hub * spec.HUB_LENGTH + rim * spec.WHEEL_LENGTH, rel=1e-12
    )
    assert spec.GRIP_VOLUME_MM3 == pytest.approx(
        math.pi * (spec.GRIP_DIA / 2.0) ** 2 * spec.GRIP_LENGTH, rel=1e-12
    )
    assert spec.VOLUME_MM3 == pytest.approx(
        spec.WHEEL_VOLUME_MM3 + spec.GRIP_VOLUME_MM3 - 2.0 * tap, rel=1e-5
    )


def test_build_sketches_the_spec_profiles() -> None:
    assert part.wheel_points() == list(spec.WHEEL_PROFILE)
    assert part.grip_points()[0] == (spec.GRIP_OFFSET, spec.WHEEL_FACE_Y)
    assert part.grip_points()[-1] == (spec.GRIP_OFFSET, spec.LENGTH)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert 'volume_check(adapter, "handwheel", VOLUME_MM3' in source
    assert "publish_screw_axis(adapter)" in source
    # No edge break is published, so none is modelled.
    assert "fillet" not in source and "chamfer" not in source.lower()


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
    assert draw.MACHINIST_REVIEW is draw.MachinistReviewMode.ENFORCE
    # The ITEM row names the listing's wheel size and bore, as the model has them.
    assert f"{spec.WHEEL_DIA:.0f} MM" in draw.ITEM and "HANDWHEEL" in draw.ITEM
    assert f"{spec.BORE_DIA:.0f} MM BORE" in draw.ITEM


def test_note_is_one_short_line_naming_the_leadscrew_by_its_drawing_number() -> None:
    note = spec.DRAWING_NOTES
    number = _config.parts("ch-rocker-arm-tl-vn-oblique-leadscrew")["number"]
    assert spec.LEADSCREW_NUMBER == number
    assert "\n" not in note and len(note) <= 80
    assert f"LEADSCREW {number}" in note
    # The number is the only digits the note carries.
    assert not re.search(r"\d", note.replace(number, ""))

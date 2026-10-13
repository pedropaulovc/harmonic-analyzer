"""Sharpie Mini pen marker (MHA-VN-060) contracts, SolidWorks-free."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import build_vn_pen_marker as part
import draw_vn_pen_marker as drawing
import vn_pen_marker_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME

STEM = "vn-pen-marker"
IN = 25.4


def test_registry_row_is_the_purchased_sharpie_mini() -> None:
    row = _config.parts(STEM)
    assert row["number"] == "MHA-VN-060"
    assert row["process"] == "purchased"
    assert row["supplier"] == spec.SUPPLIER
    assert row["supplier_skus"] == [spec.SKU] == ["35111"]
    assert row["material"] == spec.MATERIAL == part.MATERIAL
    assert int(row["quantity"]) == 1
    assert part.STOCK_PROPERTIES == {
        "Stock Name": row["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }


def test_sourced_lengths_and_seat() -> None:
    # sharpie.com: 3-1/2 in long, capped and over the key ring.
    assert spec.CAPPED_LENGTH == pytest.approx(3.5 * IN)
    # The uncapped marker is shorter than the capped one by the cap's overhang.
    assert 60.0 < spec.OVERALL_LENGTH < spec.CAPPED_LENGTH
    # The v-block seat is the regular Sharpie's Ø10.6 grip (jetpens.com).
    assert spec.BARREL_DIA == 10.6
    assert spec.BARREL_START_Y < spec.BARREL_END_Y


def test_profile_runs_nib_to_back_end_on_the_axis() -> None:
    stations = [y for y, _ in spec.PROFILE]
    assert spec.PROFILE[0] == (0.0, 0.0)
    assert spec.PROFILE[-1] == (spec.OVERALL_LENGTH, 0.0)
    assert stations == sorted(stations)
    assert all(r > 0.0 for _, r in spec.PROFILE[1:-1])
    assert 2.0 * max(r for _, r in spec.PROFILE) == spec.MAX_DIA
    # The seat is a cylinder of BARREL_DIA over BARREL_START_Y..BARREL_END_Y.
    seat = [r for y, r in spec.PROFILE if spec.BARREL_START_Y <= y <= spec.BARREL_END_Y]
    assert spec.BARREL_DIA / 2.0 in seat
    assert (spec.BARREL_START_Y, spec.BARREL_DIA / 2.0) in spec.PROFILE
    assert (spec.BARREL_END_Y, spec.BARREL_DIA / 2.0) in spec.PROFILE
    # The body shoulder stands proud of the seat: it is what stops the marker.
    assert spec.BODY_FRONT_DIA > spec.BARREL_DIA


def test_volume_and_centroid_match_a_numeric_revolve() -> None:
    n = 20000
    volume = moment = 0.0
    for (y0, r0), (y1, r1) in zip(spec.PROFILE, spec.PROFILE[1:]):
        if y1 == y0:
            continue
        for i in range(n):
            t = (i + 0.5) / n
            y = y0 + t * (y1 - y0)
            r = r0 + t * (r1 - r0)
            dv = math.pi * r * r * (y1 - y0) / n
            volume += dv
            moment += dv * y
    assert spec.VOLUME_MM3 == pytest.approx(volume, rel=1e-6)
    assert spec.CG_Y == pytest.approx(moment / volume, rel=1e-6)
    assert spec.MASS_G == pytest.approx(spec.VOLUME_MM3 * spec.DENSITY_G_PER_MM3)
    # A few grams, as a pocket marker is (brief: about 6 g capped).
    assert 3.0 < spec.MASS_G < 7.0


def test_build_sketches_radius_over_station() -> None:
    points = part.profile_points()
    assert points == [(r, y) for y, r in spec.PROFILE]
    assert points[0] == (0.0, 0.0)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "RevolveParameters(angle=360.0)" in source
    assert 'volume_check(adapter, "marker", VOLUME_MM3' in source


def test_spec_is_pure_data() -> None:
    source = Path(spec.__file__).read_text(encoding="utf-8")
    imports = re.findall(r"^(?:from|import) (\S+)", source, re.MULTILINE)
    assert set(imports) <= {"__future__", "math"}


def test_drawing_is_the_purchased_reference_sheet() -> None:
    sheet = DRAWINGS_BY_NAME["vn_pen_marker"]
    assert drawing.SPEC is sheet
    assert sheet.artifact_stem == part.PART_NAME == STEM
    assert sheet.source_kind == "part"
    assert drawing.build.__code__.co_names.count("build_purchased_part_drawing") == 1
    # The sheet note carries no numbers; the model and the SKU carry them.
    assert not re.search(r"\d", spec.DRAWING_NOTES)
    assert len(spec.DRAWING_NOTES) <= 70


def test_retired_turned_marker_is_gone() -> None:
    scripts = Path(part.__file__).resolve().parent
    for name in (
        "build_pn_pen_marker.py",
        "draw_pn_pen_marker.py",
        "pn_pen_marker_spec.py",
        "test_pn_pen_marker_drawing.py",
    ):
        assert not (scripts / name).exists()
    assert "pn_pen_marker" not in DRAWINGS_BY_NAME
    with pytest.raises(KeyError):
        _config.parts("pn-pen-marker")

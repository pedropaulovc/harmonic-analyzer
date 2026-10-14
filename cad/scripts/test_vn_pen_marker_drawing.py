"""Sharpie Fine Point pen marker (MHA-VN-065) contracts, SolidWorks-free."""

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


def test_registry_row_is_the_purchased_sharpie_fine_point() -> None:
    row = _config.parts(STEM)
    assert row["number"] == "MHA-VN-065"
    assert row["process"] == "purchased"
    assert row["supplier"] == spec.SUPPLIER
    assert row["supplier_skus"] == [spec.SKU] == ["30051"]
    assert row["material"] == spec.MATERIAL == part.MATERIAL
    assert int(row["quantity"]) == 1
    assert part.STOCK_PROPERTIES == {
        "Stock Name": row["stock_name"],
        "Supplier": spec.SUPPLIER,
        "Supplier SKUs": spec.SKU,
    }


def test_sourced_lengths_and_seat() -> None:
    # jetpens.com, Sharpie Fine Point 30051: 123 long uncapped, as used.
    assert spec.OVERALL_LENGTH == 123.0
    # The v-block seat is the regular Sharpie's Ø10.6 grip (jetpens.com).
    assert spec.BARREL_DIA == 10.6
    assert spec.BARREL_START_Y < spec.BARREL_END_Y
    # The dome carries on from the taper's end to the back end.
    assert spec.BARREL_END_Y < spec.BODY_TAPER_END_Y < spec.OVERALL_LENGTH


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
    # jetpens.com: the barrel with its ink weighs 7 g; the balance takes it
    # at the envelope's centroid (uniform density assumed).
    assert spec.MASS_G == 7.0
    assert 0.4 * spec.OVERALL_LENGTH < spec.CG_Y < 0.6 * spec.OVERALL_LENGTH


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
    # The sheet note carries no numbers; the model and the SKU carry them.
    assert not re.search(r"\d", spec.DRAWING_NOTES)


def _overlaps(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ASME B landscape: the border 12.7 mm in, the title block and the purchased
# footer's notes in the lower corners (farm run e31912e0's PNG).
BORDER = (0.0127, 0.0127, 0.4191, 0.2667)
TITLE_BLOCK = (0.2159, 0.0127, 0.4191, 0.0651)
FOOTER = (0.0127, 0.0127, 0.2600, 0.0730)


def _cells() -> dict[str, tuple[float, float, float, float]]:
    return {
        name: drawing.view_cell(center, half) for name, center, half in drawing.VIEWS
    }


def test_views_are_one_sheet_scale_in_third_angle_alignment() -> None:
    assert drawing.SHEET_SCALE == (1, 1)
    centers = {name: center for name, center, _ in drawing.VIEWS}
    assert set(centers) == {"*Front", "*Top", "*Right", "*Isometric"}
    front, top, right = centers["*Front"], centers["*Top"], centers["*Right"]
    assert top[0] == front[0] and top[1] > front[1]
    assert right[1] == front[1] and right[0] > front[0]
    # The side views are the marker at full size: nib to back end, Ø over the shoulder.
    assert drawing._SIDE_HALF == pytest.approx(
        (spec.MAX_DIA / 2000.0, spec.OVERALL_LENGTH / 2000.0)
    )


def test_view_cells_and_notes_clear_each_other_and_the_sheet_furniture() -> None:
    boxes = dict(_cells())
    for label, x, y in drawing.CAPTIONS:
        half = drawing._CAPTION_HALF_WIDTH
        boxes[f"caption {label}"] = (x - half, y - 0.006, x + half, y + 0.001)
    boxes["grip note"] = drawing.GRIP_NOTE_BOX
    names = sorted(boxes)
    for i, a in enumerate(names):
        box = boxes[a]
        assert BORDER[0] <= box[0] and box[2] <= BORDER[2], a
        assert BORDER[1] <= box[1] and box[3] <= BORDER[3], a
        assert not _overlaps(box, TITLE_BLOCK), a
        assert not _overlaps(box, FOOTER), a
        for b in names[i + 1 :]:
            assert not _overlaps(box, boxes[b]), (a, b)


def test_grip_note_is_the_part_note_on_a_leader_to_the_grip_band() -> None:
    text = drawing.grip_note(spec.DRAWING_NOTES)
    # Every word of the part's note, printed once, on short lines.
    assert " ".join(text.split("\n")) == spec.DRAWING_NOTES
    lines = text.split("\n")
    assert len(lines) == 3
    assert all(len(line) <= drawing.GRIP_NOTE_WIDTH for line in lines)
    # The tip sits on the grip's silhouette in FRONT, inside the band.
    front, half = drawing.FRONT_CENTER, drawing._SIDE_HALF
    nib_y = front[1] - half[1]
    tip = drawing.GRIP_TIP
    assert tip[0] == pytest.approx(front[0] - spec.BARREL_DIA / 2000.0)
    assert (
        nib_y + spec.BARREL_START_Y / 1000.0
        < tip[1]
        < nib_y + spec.BARREL_END_Y / 1000.0
    )
    # The text box (top-left at GRIP_NOTE_XY) reaches toward the tip from its left.
    box = drawing.GRIP_NOTE_BOX
    assert box[0] < drawing.GRIP_NOTE_XY[0] and drawing.GRIP_NOTE_XY[1] <= box[3]
    assert box[2] < tip[0]
    # GetExtent spans the leader too (farm r14): the native extent box is the
    # text box run out just past the tip, and it holds r14's readback.
    extent = drawing.GRIP_NOTE_EXTENT
    r14 = (0.05958551, 0.12778579, 0.17443854, 0.15018451)
    assert extent[0] <= r14[0] and extent[1] <= r14[1]
    assert r14[2] <= extent[2] and r14[3] <= extent[3]
    assert extent[2] - tip[0] == pytest.approx(0.001)
    assert tip[1] - extent[1] == pytest.approx(0.001)
    assert extent[3] == box[3] and extent[0] == box[0]
    # The note prints only on the leader: no general installation note.
    names = drawing.build.__code__.co_names
    assert names.count("add_leader_note") == 1
    assert "build_purchased_part_drawing" not in names
    assert "Installation Notes" not in drawing.build.__code__.co_consts


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

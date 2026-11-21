"""SolidWorks-free integrity guards for the photo-traced nameplate contours.

The 2026-10-09 ruling makes the original outer ribbon's OUTER edge the plate
outline, scaled to 3.95 x 1.79 in. That edge is imported for the slab. Owner
ruling 2026-11-20 (Pedro), #2313 ("A") etches the field and leaves the border
and the filled letters proud: the field DXF is the pinstripe's notched INNER
edge (cut), the letters DXF every letter and counter (bossed back, even-odd),
and the resist DXF is the outline plus the etched field eroded by the etch
depth (the resist widened by the depth per edge). Screw holes sit at the
traced corners and the whole head must bear on the raised border, not the
etched field.

Reuse the repo's ASCII DXF/polygon helpers: no ezdxf or CAD kernel is needed.
These tests run in check:nameplate and guard units, closed contours, exact
extents/areas, mount geometry and all three vendored recipe inputs.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

import _dxf_text as dxf
import build_fr_nameplate as part
import fr_nameplate_drawing_spec as print_spec
import fr_nameplate_spec as spec
from _inch_wall_limits import WALL_TARGET_MM
from _paths import REFERENCES_DIR
from fr_harmonic_base_spec import DECK_LENGTH
from sh_vn_brass_fillister_screw_spec import HEAD_DIA

RESIST_DXF = REFERENCES_DIR / print_spec.RESIST_DXF_NAME


def _etched_field() -> list[dxf.Ring]:
    """The finished etched field, even-odd: its edge, the letters, counters."""
    return _rings(part.FIELD_DXF) + _rings(part.LETTERS_DXF)


def _read(path: Path) -> str:
    return path.read_text(encoding="ascii")


def _entities_section(text: str) -> str:
    start = text.find("\nENTITIES\n")
    end = text.find("\nENDSEC\n", start)
    assert start >= 0 and end > start, "missing ENTITIES section"
    return text[start:end]


def _rings(path: Path) -> list[dxf.Ring]:
    return [ring for ring, _ in dxf.read_lwpolylines(_entities_section(_read(path)))]


def _segments(rings: list[dxf.Ring]) -> tuple[np.ndarray, np.ndarray]:
    starts = np.concatenate([np.asarray(ring) for ring in rings])
    ends = np.concatenate([np.roll(np.asarray(ring), -1, axis=0) for ring in rings])
    return starts, ends


def _distances(points: np.ndarray, rings: list[dxf.Ring]) -> np.ndarray:
    """Least distance from each point to the rings' edges."""
    a, b = _segments(rings)
    ab = b - a
    length2 = np.maximum((ab**2).sum(axis=1), 1e-30)
    best = np.full(len(points), np.inf)
    for chunk in range(0, len(points), 256):
        p = points[chunk : chunk + 256, None, :]
        t = np.clip(((p - a) * ab).sum(axis=2) / length2, 0.0, 1.0)
        gap = np.hypot(*np.moveaxis(p - a - t[..., None] * ab, 2, 0))
        best[chunk : chunk + 256] = gap.min(axis=1)
    return best


@pytest.mark.parametrize(
    ("path", "count"),
    [
        (part.FIELD_DXF, 1),
        (part.LETTERS_DXF, 43),
        (part.OUTLINE_DXF, 1),
        (RESIST_DXF, 43),
    ],
    ids=["field", "letters", "outline", "resist"],
)
def test_vendored_dxf_has_only_closed_millimetre_contours(path: Path, count: int):
    assert path.is_file(), path
    text = _read(path)
    assert dxf.header_int(text, "INSUNITS") == 4
    assert "AC1024" in text  # retain the source R2010 header/units
    assert text.endswith("  0\nEOF\n")
    section = _entities_section(text)
    counts = Counter(re.findall(r"\n  0\n(\w+)\n", section))
    assert counts == {"LWPOLYLINE": count}, counts
    entities = dxf.read_lwpolylines(section)
    assert len(entities) == count
    assert all(closed and len(ring) >= 3 for ring, closed in entities)
    # Every contour is a planar line loop, not an unparsed arc/width/extrusion.
    assert not re.search(r"\n (?:38|39|40|41|42)\n(?!0(?:\.0)?\n)", section)


def test_plate_outline_is_the_scaled_dxf_outer_edge():
    outline = _rings(part.OUTLINE_DXF)[0]
    bounds = dxf.bbox([outline])
    assert bounds == pytest.approx(
        (0.0, 0.0, spec.PLATE_WIDTH, spec.PLATE_HEIGHT), abs=1e-9
    )
    # Rebaked per axis so both edges land on the .001 inch grid.
    assert spec.PLATE_WIDTH == spec.DXF_OUTER_WIDTH * spec.DXF_SCALE_X
    assert spec.PLATE_HEIGHT == spec.DXF_OUTER_HEIGHT * spec.DXF_SCALE_Y
    assert abs(dxf.signed_area(outline)) == pytest.approx(
        part.OUTLINE_AREA_MM2, abs=1e-8
    )
    # The trace is retained, not replaced by a four-sided rectangle or fitted
    # rounded rectangle; the outer contour has its original 117 vertices.
    assert len(outline) == 117
    assert abs(dxf.signed_area(outline)) < spec.PLATE_WIDTH * spec.PLATE_HEIGHT


def test_corner_radius_matches_the_traced_outer_corner():
    outline = np.asarray(_rings(part.OUTLINE_DXF)[0])
    corner = outline[(outline[:, 0] < 4.1) & (outline[:, 1] < 4.1)]
    assert len(corner) >= 20
    matrix = np.column_stack(
        (2.0 * corner[:, 0], 2.0 * corner[:, 1], np.ones(len(corner)))
    )
    cx, cy, constant = np.linalg.lstsq(matrix, np.sum(corner**2, axis=1), rcond=None)[0]
    radius = math.sqrt(constant + cx**2 + cy**2)
    assert radius == pytest.approx(part.CORNER_R, abs=1e-9)
    assert np.max(abs(np.hypot(corner[:, 0] - cx, corner[:, 1] - cy) - radius)) < 0.001


def test_etched_field_is_the_pinstripe_inner_edge_less_the_letters():
    field = _rings(part.FIELD_DXF)[0]
    # The traced notches, not a BorderW rectangle: the pinstripe's inner edge.
    assert len(field) == 173
    assert abs(dxf.signed_area(field)) == pytest.approx(part.FIELD_AREA_MM2, abs=1e-6)
    letters = _rings(part.LETTERS_DXF)
    depths = [dxf.nesting_depth(letters, i) for i in range(len(letters))]
    # 34 letters and ornament standing proud (0), and the nine counters etched
    # inside them (1).
    assert Counter(depths) == {0: 34, 1: 9}
    assert dxf.net_area(letters) == pytest.approx(part.LETTERS_AREA_MM2, abs=1e-6)
    outline = _rings(part.OUTLINE_DXF)[0]
    assert all(dxf.point_in_ring(outline, point) for point in field)
    assert all(dxf.point_in_ring(field, point) for ring in letters for point in ring)


def test_resist_is_the_outline_plus_the_field_set_back_by_the_etch_depth():
    resist = _rings(RESIST_DXF)
    field = _etched_field()
    # The shop's one artwork file carries the plate outline as its outer loop.
    assert resist[0] == _rings(part.OUTLINE_DXF)[0]
    assert [dxf.nesting_depth(resist, i) for i in range(len(resist))][0] == 0
    # Every resist edge inside the outline stands the etch depth off the
    # finished field's edges (the field eroded by FIELD_DEPTH, simplified to
    # .002 mm), so the 1:1 undercut brings each edge back to its finished line.
    inner = np.concatenate([np.asarray(ring) for ring in resist[1:]])
    gaps = _distances(inner, field)
    assert gaps.min() == pytest.approx(print_spec.FIELD_DEPTH, abs=0.005)
    assert np.median(gaps) == pytest.approx(print_spec.FIELD_DEPTH, abs=0.002)
    # And every one lies in the etched field (an odd number of field loops
    # holds it): the resist only grows.
    for x, y in inner[:: max(1, len(inner) // 400)]:
        held = sum(dxf.point_in_ring(ring, (x, y)) for ring in field)
        assert held % 2 == 1, (x, y)
    # The widened resist covers more than the finished border and letters.
    finished = dxf.net_area(_rings(part.OUTLINE_DXF)) - dxf.net_area(field)
    assert dxf.net_area(resist) > finished


def test_screw_holes_and_heads_stay_on_the_raised_plate_border():
    outline = _rings(part.OUTLINE_DXF)[0]
    field = _rings(part.FIELD_DXF)[0]
    for hx, hy in spec.SCREW_XY:
        for diameter in (part.SCREW_HOLE_DIA, HEAD_DIA):
            for degrees in range(360):
                angle = math.radians(degrees)
                point = (
                    hx + diameter / 2.0 * math.cos(angle),
                    hy + diameter / 2.0 * math.sin(angle),
                )
                assert dxf.point_in_ring(outline, point), (hx, hy, diameter, point)
                assert not dxf.point_in_ring(field, point), (hx, hy, diameter, point)
        # The through-hole has a real ligament, including toward the nearest edge.
        ligament = (
            min(hx, spec.PLATE_WIDTH - hx, hy, spec.PLATE_HEIGHT - hy)
            - part.SCREW_HOLE_DIA / 2.0
        )
        assert ligament >= WALL_TARGET_MM, (hx, hy, ligament)


def test_mount_contract_puts_the_plate_flat_on_the_west_deck():
    from _transforms import rows_from_euler

    assert np.asarray(spec.MOUNT_ROWS) == pytest.approx(
        np.asarray(rows_from_euler(spec.MOUNT_EULER)), abs=1e-12
    )
    assert spec.MOUNT_NORMAL == (0.0, 1.0, 0.0)
    assert spec.MOUNT_FRONT_Y - spec.MOUNT_BACK_Y == pytest.approx(spec.PLATE_THICKNESS)
    assert spec.MOUNT_BACK_Y == pytest.approx(50.8)  # shared base STACK_HEIGHT
    corners = [
        spec.mount_point((x, y, 0.0))
        for x in (0.0, spec.PLATE_WIDTH)
        for y in (0.0, spec.PLATE_HEIGHT)
    ]
    # .160 in from the deck's west end (DECK_LENGTH / 2).
    assert max(point[0] for point in corners) == pytest.approx(
        DECK_LENGTH / 2.0 - 4.064
    )
    assert min(point[0] for point in corners) > 104.65  # rocker-arm support's west edge
    assert min(point[2] for point in corners) == pytest.approx(
        -max(point[2] for point in corners)
    )
    mapped = [spec.mount_point((x, y, 0.0)) for x, y in spec.SCREW_XY]
    assert all(point[1] == pytest.approx(spec.MOUNT_FRONT_Y) for point in mapped)
    assert spec.MOUNT_HOLE_XZ == tuple((point[0], point[2]) for point in mapped)


def test_all_nameplate_dxf_assets_are_part_recipe_dependencies():
    from _buildgraph import data_deps_of

    dependencies = data_deps_of(Path(part.__file__))
    for asset in (part.OUTLINE_DXF, part.FIELD_DXF, part.LETTERS_DXF, RESIST_DXF):
        assert str(asset.resolve()) in dependencies, dependencies

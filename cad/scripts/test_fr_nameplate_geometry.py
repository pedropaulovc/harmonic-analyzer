"""SolidWorks-free integrity guards for the photo-traced nameplate contours.

The 2026-10-09 ruling makes the original outer ribbon's OUTER edge the plate
outline, uniformly scaled to 100 mm wide. That edge is imported for the slab;
the ribbon itself is omitted from the engraving so it cannot nick the plate.
The recessed field follows the notched pinstripe INNER edge, copied into its
own single-loop DXF. Screw holes must coincide with the traced head marks and
the whole head must bear on the raised border, not the sunken field.

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
import fr_nameplate_spec as spec
from vn_fillister_screw_spec import HEAD_DIA


def _read(path: Path) -> str:
    return path.read_text(encoding="ascii")


def _entities_section(text: str) -> str:
    start = text.find("\nENTITIES\n")
    end = text.find("\nENDSEC\n", start)
    assert start >= 0 and end > start, "missing ENTITIES section"
    return text[start:end]


def _rings(path: Path) -> list[dxf.Ring]:
    return [ring for ring, _ in dxf.read_lwpolylines(_entities_section(_read(path)))]


@pytest.mark.parametrize(
    ("path", "count"),
    [(part.ENGRAVING_DXF, 110), (part.OUTLINE_DXF, 1), (part.FIELD_DXF, 1)],
    ids=["engraving", "outline", "field"],
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


def test_engraving_extent_matches_the_baked_import_constants():
    bounds = dxf.bbox(_rings(part.ENGRAVING_DXF))
    assert bounds == pytest.approx(part.ENGRAVING_RAW_BBOX, abs=1e-9)
    width = bounds[2] - bounds[0]
    centre = ((bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0)
    assert width == pytest.approx(part.ENGRAVING_TARGET_WIDTH, abs=1e-9)
    assert centre == pytest.approx(part.ENGRAVING_CENTER, abs=1e-9)
    assert part.ENGRAVING_SCALE == pytest.approx(1.0, abs=1e-12)
    assert part.ENGRAVING_POSITION == (0.0, 0.0)
    # The dropped edge ribbon is not imported as a cut: all remaining vertices
    # are strictly inside the plate's outer contour.
    outline = _rings(part.OUTLINE_DXF)[0]
    assert all(
        dxf.point_in_ring(outline, point)
        for ring in _rings(part.ENGRAVING_DXF)
        for point in ring
    )


def test_plate_outline_is_the_scaled_dxf_outer_edge():
    outline = _rings(part.OUTLINE_DXF)[0]
    bounds = dxf.bbox([outline])
    assert bounds == pytest.approx(
        (0.0, 0.0, spec.PLATE_WIDTH, spec.PLATE_HEIGHT), abs=1e-9
    )
    assert spec.PLATE_WIDTH == spec.DXF_OUTER_WIDTH * spec.DXF_SCALE
    assert spec.PLATE_HEIGHT == spec.DXF_OUTER_HEIGHT * spec.DXF_SCALE
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


def test_field_is_exactly_the_pinstripe_inner_edge_and_has_pinned_area():
    field = _rings(part.FIELD_DXF)[0]
    assert field in _rings(part.ENGRAVING_DXF), (
        "field must be the actual frame inner loop"
    )
    assert len(field) == 173  # preserve the traced notches, not a BorderW rectangle
    assert abs(dxf.signed_area(field)) == pytest.approx(part.FIELD_AREA_MM2, abs=1e-8)
    x0, y0, x1, y1 = dxf.bbox([field])
    assert abs(dxf.signed_area(field)) < (x1 - x0) * (y1 - y0)
    outline = _rings(part.OUTLINE_DXF)[0]
    assert all(dxf.point_in_ring(outline, point) for point in field)


def test_screw_stations_coincide_with_the_dxf_head_marks():
    rings = _rings(part.ENGRAVING_DXF)
    assert len(spec.SCREW_XY) == 4
    for station in spec.SCREW_XY:
        # Each slotted head is two ribbon halves, each with an inner counter.
        # Identify by geometry, not DXF ordering/handles, to tolerate a re-export.
        mark = []
        for ring in rings:
            x0, y0, x1, y1 = dxf.bbox([ring])
            centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
            if x1 - x0 < 5.0 and y1 - y0 < 5.0 and math.dist(centre, station) < 1.0:
                mark.append(ring)
        assert len(mark) == 4, (station, len(mark))
        x0, y0, x1, y1 = dxf.bbox(mark)
        centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        assert math.dist(centre, station) < 0.01, (station, centre)


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
        assert ligament >= 1.5, (hx, hy, ligament)


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
    assert max(point[0] for point in corners) == pytest.approx(167.0 - 4.0)
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
    for asset in (part.ENGRAVING_DXF, part.OUTLINE_DXF, part.FIELD_DXF):
        assert str(asset.resolve()) in dependencies, dependencies

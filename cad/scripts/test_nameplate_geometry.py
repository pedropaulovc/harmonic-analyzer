"""Integrity guard for the nameplate's vendored engraving DXF.

``build_nameplate`` no longer draws the engraving from hard-coded coordinate
loops -- it **imports** the vendored DXF (``cad/references/nameplate-engraving.dxf``)
onto the decorated face and cuts the whole artwork (lettering + scroll cartouche
+ pinstripe frame) as one feature (``adapter.import_dxf_dwg`` ->
``IFeatureManager::InsertDwgOrDxfFile2``). The DXF is now the source of truth.

That vendored DXF is a CLOSED-REGION rendering of the traced artwork: the raw
photo trace is outline line-art (open strokes, hollow letters) that a cut-extrude
cannot turn into a feature, so each stroke was buffered into a thin closed ribbon
and the ribbons unioned into closed modelspace polylines that cut as grooves (see
``build_nameplate`` docstring). So the file is a flat set of **closed LWPOLYLINEs**
in the ENTITIES section -- no blocks, no open contours.

This test is the kernel-free, dependency-free guard on that file: it confirms the
DXF is present, is a millimetre-unit DXF (``$INSUNITS = 4`` -- the build imports it
as mm), carries the expected population of CLOSED polyline regions (not an empty,
open, or wrong export), and that its artwork extent matches what the build's import
scale (``ENGRAVING_RAW_WIDTH``) assumes. A DXF that is swapped, re-exported at a
different unit, truncated, or left with open contours fails here rather than
silently producing a mis-scaled or uncuttable engraving on the live SolidWorks seat
(where ``build_nameplate`` itself bounds-checks the removed volume).

Parsed with a tiny regex reader over the ASCII DXF group-code pairs -- no ezdxf,
no CAD kernel -- so it runs in the SolidWorks-free ``check:nameplate`` gate.

Run directly for a full report::

    python cad/scripts/test_nameplate_geometry.py
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import _telemetry

ENGRAVING_DXF = Path(__file__).resolve().parents[1] / "references" / "nameplate-engraving.dxf"

# Golden facts about the closed-region artwork, captured from the vendored DXF. The
# build imports it as millimetres and uniform-scales its outer frame
# (ENGRAVING_RAW_WIDTH in build_nameplate) to the plate footprint, so both the unit
# and the extent are load-bearing for a correctly-placed engraving.
GOLDEN_INSUNITS = 4  # 4 = millimetres (build imports as mm)
# Artwork bounding box in the modelspace ENTITIES. The file is authored at FINAL
# plate-mm (the Makers seat ignores the import scale), so the outer frame spans the
# 88 mm plate footprint exactly. Guards against truncation / a wrong-unit re-export.
GOLDEN_COORD_WIDTH = 88.000  # artwork bbox width (mm, +/- 1%)
GOLDEN_COORD_HEIGHT = 39.892  # artwork bbox height (mm, +/- 1%)
# The buffered-ribbon union yields many closed polyline regions (letter strokes,
# frame, scroll, screws). An empty or under-populated export is not the engraving.
MIN_CLOSED_REGIONS = 90  # closed LWPOLYLINE rings (112 as vendored)


def _read() -> str:
    return ENGRAVING_DXF.read_text(encoding="utf-8", errors="replace")


def _header_int(txt: str, var: str) -> int | None:
    """Read an integer ``$VAR`` from the DXF HEADER section (group code 70)."""
    m = re.search(rf"\${var}\n\s*70\n\s*(-?\d+)", txt)
    return int(m.group(1)) if m else None


def _entities_section(txt: str) -> str:
    start = txt.find("\nENTITIES\n")
    end = txt.find("\nENDSEC\n", start)
    return txt[start:end] if start >= 0 and end > start else ""


def _entity_counts(seg: str) -> Counter:
    return Counter(re.findall(r"\n  0\n(\w+)\n", seg))


def _closed_flags(seg: str) -> list[int]:
    """Per-LWPOLYLINE closed flag (group 70 after the AcDbPolyline vertex count 90)."""
    return [int(f) for f in re.findall(r"AcDbPolyline\n\s*90\n\s*\d+\n\s*70\n\s*(\d+)", seg)]


def _artwork_bbox(seg: str) -> tuple[float, float]:
    """Width/height of the modelspace geometry from its (10, 20) vertex coordinates."""
    xs = [float(v) for v in re.findall(r"\n 10\n([-0-9.eE+]+)\n", seg)]
    ys = [float(v) for v in re.findall(r"\n 20\n([-0-9.eE+]+)\n", seg)]
    return (max(xs) - min(xs), max(ys) - min(ys))


def _pct(got: float, ref: float) -> float:
    return 100.0 * (1.0 - abs(got - ref) / abs(ref))


def test_engraving_dxf_present():
    """The vendored engraving DXF the build imports exists and is non-trivial."""
    assert ENGRAVING_DXF.is_file(), ENGRAVING_DXF
    assert ENGRAVING_DXF.stat().st_size > 10_000, ENGRAVING_DXF.stat().st_size


def test_engraving_dxf_is_millimetre_unit():
    """$INSUNITS = 4 -- the build imports the DXF as millimetres."""
    assert _header_int(_read(), "INSUNITS") == GOLDEN_INSUNITS


def test_engraving_dxf_has_closed_regions():
    """The artwork is a population of CLOSED polyline regions (cuttable profiles)."""
    seg = _entities_section(_read())
    counts = _entity_counts(seg)
    assert counts.get("LWPOLYLINE", 0) >= MIN_CLOSED_REGIONS, counts
    flags = _closed_flags(seg)
    assert len(flags) >= MIN_CLOSED_REGIONS, len(flags)
    # Every ribbon must be closed -- an open contour would not cut as a region.
    assert all(f & 1 for f in flags), flags


def test_engraving_dxf_coordinate_extent():
    """The artwork's coordinate extent is intact (not truncated/rescaled)."""
    w, h = _artwork_bbox(_entities_section(_read()))
    assert _pct(w, GOLDEN_COORD_WIDTH) >= 99.0, w
    assert _pct(h, GOLDEN_COORD_HEIGHT) >= 99.0, h


def test_mount_contract_puts_the_plate_flat_on_the_deck():
    """nameplate_spec (pure data): the four corner screw stations, the mount
    transform, and their machine-frame image -- the base's tapped seats and the
    frame's screw drops derive from these, so pin them (2026-09-02 ch26 p.71
    re-derive: four corner screws)."""
    import nameplate_spec as spec

    assert (spec.PLATE_WIDTH, spec.PLATE_HEIGHT, spec.PLATE_THICKNESS) == (100.0, 55.0, 1.5)
    assert len(spec.SCREW_XY) == 4
    inset = spec.SCREW_INSET
    assert set(spec.SCREW_XY) == {
        (inset, inset),
        (100.0 - inset, inset),
        (inset, 55.0 - inset),
        (100.0 - inset, 55.0 - inset),
    }
    # Rows: local +X -> -Z (text runs front-back), +Y -> -X, +Z (decorated
    # front) -> +Y (face up).
    assert spec.MOUNT_ROWS == [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert spec.MOUNT_NORMAL == (0.0, 1.0, 0.0)
    assert spec.MOUNT_FRONT_Y == 52.3
    assert abs(spec.MOUNT_BACK_Y - 50.8) < 1e-12  # the base deck (STACK_HEIGHT)
    # Plate-local (x, y) -> machine (214.25 - y, 50 - x).
    assert spec.mount_point((0.0, 0.0, 0.0)) == (214.25, 52.3, 50.0)
    assert spec.mount_point((100.0, 55.0, -1.5)) == (159.25, 50.8, -50.0)
    assert set(spec.MOUNT_HOLE_XZ) == {
        (209.75, 45.5), (209.75, -45.5), (163.75, 45.5), (163.75, -45.5),
    }
    assert len(spec.MOUNT_HOLE_XZ) == 4


if __name__ == "__main__":
    txt = _read()
    seg = _entities_section(txt)
    counts = _entity_counts(seg)
    flags = _closed_flags(seg)
    w, h = _artwork_bbox(seg)
    _telemetry.info("nameplate engraving DXF integrity")
    _telemetry.info(f"file           : {ENGRAVING_DXF}")
    _telemetry.info(f"$INSUNITS      : {_header_int(txt, 'INSUNITS')}  golden {GOLDEN_INSUNITS}")
    _telemetry.info(f"entities       : {dict(counts)}")
    _telemetry.info(f"closed regions : {sum(f & 1 for f in flags)} / {len(flags)}  (min {MIN_CLOSED_REGIONS})")
    _telemetry.info(f"coord width    : {w:9.3f}  golden {GOLDEN_COORD_WIDTH:9.3f}  -> {_pct(w, GOLDEN_COORD_WIDTH):7.3f}%")
    _telemetry.info(f"coord height   : {h:9.3f}  golden {GOLDEN_COORD_HEIGHT:9.3f}  -> {_pct(h, GOLDEN_COORD_HEIGHT):7.3f}%")


def test_corner_screw_holes_stay_inside_the_rounded_plate_outline():
    """Each #4 clearance hole must be fully enclosed by the plate outline,
    rounded corners included (CodeRabbit #652: a hole that breaks out of a
    corner arc would leave an open slot the screw head cannot clamp)."""
    import math

    import build_nameplate as bn
    import nameplate_spec as spec

    w, h, rc = spec.PLATE_WIDTH, spec.PLATE_HEIGHT, bn.CORNER_R
    r = bn.SCREW_HOLE_DIA / 2.0

    def inside(x: float, y: float) -> bool:
        if not (0.0 <= x <= w and 0.0 <= y <= h):
            return False
        # corner squares beyond each arc centre: the point must lie within the arc
        corners = (
            (x < rc and y < rc, rc, rc),
            (x > w - rc and y < rc, w - rc, rc),
            (x < rc and y > h - rc, rc, h - rc),
            (x > w - rc and y > h - rc, w - rc, h - rc),
        )
        for in_square, cx, cy in corners:
            if in_square and (x - cx) ** 2 + (y - cy) ** 2 > rc**2 + 1e-9:
                return False
        return True

    for hx, hy in spec.SCREW_XY:
        for i in range(360):
            a = math.radians(i)
            px, py = hx + r * math.cos(a), hy + r * math.sin(a)
            assert inside(px, py), f"hole at ({hx}, {hy}) breaks the outline at ({px:.3f}, {py:.3f})"
        # and a real ligament to the nearest straight edge
        lig = min(hx, w - hx, hy, h - hy) - r
        assert lig >= 1.0, f"ligament {lig:.2f} at ({hx}, {hy})"

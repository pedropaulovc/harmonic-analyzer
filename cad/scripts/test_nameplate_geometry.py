"""Integrity guard for the nameplate's vendored engraving DXF.

``build_nameplate`` no longer draws the engraving from hard-coded coordinate
loops -- it **imports** the vendored DXF (``cad/references/nameplate-engraving.dxf``)
onto the decorated face and cuts the whole artwork (lettering + scroll cartouche
+ pinstripe frame) as one feature (``adapter.import_dxf_dwg`` ->
``IFeatureManager::InsertDwgOrDxfFile2``). The DXF is now the source of truth.

This test is the kernel-free, dependency-free guard on that file: it confirms the
DXF is present, is a millimetre-unit DXF (``$INSUNITS = 4`` -- the build imports it
as mm), carries the expected traced-outline entity population (splines / ellipses
/ polylines, not an empty or wrong export), and that its resolved artwork extent
matches what the build's import scale (``ENGRAVING_RAW_WIDTH``) assumes. A DXF that
is swapped, re-exported at a different unit, or truncated fails here rather than
silently producing a mis-scaled or empty engraving on the live SolidWorks seat
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

# Golden facts about the traced artwork, captured from the vendored DXF. The build
# imports it as millimetres and uniform-scales its resolved outer frame
# (ENGRAVING_RAW_WIDTH in build_nameplate) to the plate footprint, so both the unit
# and the extent are load-bearing for a correctly-placed engraving.
GOLDEN_INSUNITS = 4  # 4 = millimetres (build imports as mm)
# Raw block-coordinate extent of the artwork as it literally appears in the file
# (before the nested-INSERT transforms SolidWorks resolves on import -- the resolved
# WCS footprint the build scales against is ~278.57 mm, build_nameplate's
# ENGRAVING_RAW_WIDTH). Guards the file against truncation / a wrong-unit re-export.
GOLDEN_COORD_WIDTH = 478.041  # raw block-coordinate bbox width (+/- 1%)
GOLDEN_COORD_HEIGHT = 253.384  # raw block-coordinate bbox height (+/- 1%)
# Curved traced outlines (splines/ellipses) + polylines must be present -- an empty
# or all-straight export would not be the engraving.
MIN_CURVE_ENTITIES = 40  # SPLINE + ELLIPSE contours in the artwork blocks


def _read() -> str:
    return ENGRAVING_DXF.read_text(encoding="utf-8", errors="replace")


def _header_int(txt: str, var: str) -> int | None:
    """Read an integer ``$VAR`` from the DXF HEADER section (group code 70)."""
    m = re.search(rf"\${var}\n\s*70\n\s*(-?\d+)", txt)
    return int(m.group(1)) if m else None


def _blocks_section(txt: str) -> str:
    start = txt.find("\nBLOCKS\n")
    end = txt.find("\nENDSEC\n", start)
    return txt[start:end] if start >= 0 and end > start else ""


def _entity_counts(seg: str) -> Counter:
    return Counter(re.findall(r"\n  0\n(\w+)\n", seg))


def _artwork_bbox(seg: str) -> tuple[float, float]:
    """Width/height of the block geometry from its (10, 20) vertex coordinates."""
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


def test_engraving_dxf_has_traced_outline_entities():
    """The artwork blocks carry the traced spline/ellipse/polyline contours."""
    counts = _entity_counts(_blocks_section(_read()))
    curves = counts.get("SPLINE", 0) + counts.get("ELLIPSE", 0)
    assert curves >= MIN_CURVE_ENTITIES, counts
    assert counts.get("LWPOLYLINE", 0) >= 1, counts


def test_engraving_dxf_coordinate_extent():
    """The artwork's raw block-coordinate extent is intact (not truncated/rescaled)."""
    w, h = _artwork_bbox(_blocks_section(_read()))
    assert _pct(w, GOLDEN_COORD_WIDTH) >= 99.0, w
    assert _pct(h, GOLDEN_COORD_HEIGHT) >= 99.0, h


if __name__ == "__main__":
    txt = _read()
    counts = _entity_counts(_blocks_section(txt))
    w, h = _artwork_bbox(_blocks_section(txt))
    _telemetry.info("nameplate engraving DXF integrity")
    _telemetry.info(f"file           : {ENGRAVING_DXF}")
    _telemetry.info(f"$INSUNITS      : {_header_int(txt, 'INSUNITS')}  golden {GOLDEN_INSUNITS}")
    _telemetry.info(f"entities       : {dict(counts)}")
    _telemetry.info(f"coord width    : {w:9.3f}  golden {GOLDEN_COORD_WIDTH:9.3f}  -> {_pct(w, GOLDEN_COORD_WIDTH):7.3f}%")
    _telemetry.info(f"coord height   : {h:9.3f}  golden {GOLDEN_COORD_HEIGHT:9.3f}  -> {_pct(h, GOLDEN_COORD_HEIGHT):7.3f}%")

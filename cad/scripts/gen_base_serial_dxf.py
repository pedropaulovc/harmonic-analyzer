r"""Generate the base's stamped serial-number artwork (ch26 p.70, page001_img02/03).

The museum machine carries a hand-stamped "2" on the bright machined top of the
base rim beside the nameplate. The build imports this DXF onto a plane at the
rim top (build_harmonic_base.SERIAL_*) and cuts it SERIAL_DEPTH deep, the same
closed-region import the nameplate engraving and the measuring-stick numerals
use. Coordinates are ABSOLUTE part mm in the rim-top sketch frame (sketch x =
part X, sketch y = part Z; the Makers seat ignores SetPosition), so the file is
regenerated whenever a SERIAL_* constant moves::

    uv run python cad/scripts/gen_base_serial_dxf.py

Idempotent (no timestamps): the offline test proves the tracked file matches.
"""

from __future__ import annotations

import sys

import _dxf_text as dxf
from build_harmonic_base import (
    SERIAL_DXF,
    SERIAL_HEIGHT_MM,
    SERIAL_MIRROR_Y,
    SERIAL_TEXT,
    SERIAL_XZ,
)


def rings() -> list[dxf.Ring]:
    """The glyph rings centred on SERIAL_XZ, height SERIAL_HEIGHT_MM, glyph up = +Z."""
    raw = dxf.glyph_polylines(SERIAL_TEXT, SERIAL_HEIGHT_MM)
    x0, y0, x1, y1 = dxf.bbox(raw)
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    sy = -1.0 if SERIAL_MIRROR_Y else 1.0
    return [[(SERIAL_XZ[0] + (x - cx), SERIAL_XZ[1] + sy * (y - cy)) for x, y in ring] for ring in raw]


def render() -> bytes:
    return dxf.render_dxf(rings()).encode("ascii")


def summary() -> dict[str, float | int]:
    r = rings()
    x0, y0, x1, y1 = dxf.bbox(r)
    return {"loops": len(r), "area_mm2": dxf.net_area(r), "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def main() -> int:
    data = render()
    SERIAL_DXF.write_bytes(data)
    s = summary()
    print(f"wrote {SERIAL_DXF} ({len(data)} bytes); loops {s['loops']}; net area {s['area_mm2']:.4f} mm^2;"
          f" bbox x {s['x0']:.3f}..{s['x1']:.3f} z {s['y0']:.3f}..{s['y1']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

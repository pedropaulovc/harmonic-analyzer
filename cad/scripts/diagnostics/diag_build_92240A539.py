r"""McMaster 92240A539 -- 18-8 stainless hex head screw, 1/4"-20 x 5/8".

This diagnostic is a clean geometric replay of the harvested vendor part; it
never imports a production fastener specification.  Catalog dimensions are in
millimetres and are exposed below.  The vendor frame puts the under-head plane
at axial coordinate 0, the tip at -L, and the head top at +HH.  SolidWorks'
Top plane is that under-head plane.  The diagnostic adapter builds the screw
axis along model +Y, so a Front-plane profile uses sketch X for radius and
sketch Y for the vendor axial coordinate.  At the end, ``_mcm_com_map`` cycles
model XYZ to vendor XYZ (model Y becomes vendor Z) for centre-of-mass gating.

Geometry laws recovered from the harvest:

* The shank is a D/2 cylinder from 0 to -L.  Its 45-degree tip chamfer has
  equal axial and radial setback ``P*.75`` (the vendor Chamfer1 equation).
* The head is a regular hexagon of width HW across flats, hence circumradius
  ``HW/sqrt(3)``, extruded from 0 to +HH.  A Through-All outside-circle cut at
  the top uses the inscribed radius HW/2 and a 60-degree draft from the axis;
  this is the vendor's six rounded/trimmed corner faces.
* The under-head washer face is a circular boss of radius
  ``HW/2 - D*.01`` and thickness ``HW*.025`` below the under-head plane.
  Only its annulus outside the shank adds volume.
* The shank is fully threaded.  The sharp 60-degree thread height is
  ``P*sqrt(3)/2``; the root is ``D/2 - 3/4`` of that height, the root flat is
  P/8, and the crest cutter overtravels by 1/16 of the sharp height.  The
  tip-seeded helix spans ``L+P`` (13.5 turns) and starts at 90 degrees.  The
  cutter is centred 7P/16 beyond the tip, with crest endpoints at +/-15P/32
  and root endpoints at +/-P/16.  Splitting prevents the sweep from touching
  the head; a union restores the vendor's single body.  A final face-owned
  washer-radius boss extruded up to the hex underside reproduces the vendor
  washer transition and its merged face topology.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92240A539.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _mcmaster_92240a539 import HEX_SCREW_SIZE  # noqa: E402
from diagnostics.diag_mcmaster_hex_screw import build_hex_screw  # noqa: E402
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402


async def build_92240A539(adapter, truth=None):
    """Build the harvested 92240A539 geometry in the vendor coordinate frame."""
    await build_hex_screw(adapter, sku="92240A539", size=HEX_SCREW_SIZE)




if __name__ == "__main__":
    sys.exit(replica_main("92240A539", build_92240A539))

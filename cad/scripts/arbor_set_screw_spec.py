r"""Pure-data contract for the cylinder-arbor apex set screw (MHA-147, #743).

One #4-40 x 1/4 in hex socket cup-point set screw in each arbor pedestal's
crown apex (user ruling on #743, Q3: "set screw located at apex of straps").
The back pedestal's screw fixes the arbor; the front one is tightened once the
bank's end-play leaf is set (cylinder_bank_layout).

PURCHASED: McMaster-Carr 91375A106, alloy steel cup-tip set screw, black
oxide, Class 3A, Rockwell C45, 0.050 in hex drive (ASME B18.3 / ASTM F912).
The C45 cup bites the spotted steel arbor where an 18-8 (B80) cup would not.

The part is the vendor replica (diagnostics/diag_build_91375A106). These are
the few of its dimensions the layout reads, restated here so the pedestal
parts never import a SolidWorks recipe; test_arbor_set_screw pins the two in
lockstep.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM
from arbor_pedestal_spec import SET_SCREW_THREAD

MM_PER_IN = 25.4

THREAD = SET_SCREW_THREAD  # #4-40 UNC-2A
MAJOR_DIA = THREAD_MAJOR_MM[THREAD]  # 0.112 in
LENGTH = 0.250 * MM_PER_IN  # nominal length, cup end to socket face
HEX_AF = 0.050 * MM_PER_IN
# The vendor's cup-end chamfer, 45 deg x one pitch: the plain point below the
# first full thread, which must span the arbor's running clearance.
POINT_LENGTH = MM_PER_IN / 40.0

if POINT_LENGTH >= LENGTH:
    raise AssertionError("set-screw point overruns its length")

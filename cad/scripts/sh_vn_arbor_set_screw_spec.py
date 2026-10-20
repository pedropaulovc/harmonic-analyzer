r"""Pure McMaster 91375A106 apex set-screw dimensions for CH and DT.

PURCHASED: #4-40 x 1/4 in alloy steel cup-tip set screw, black oxide,
Class 3A, Rockwell C45, 0.050 in hex drive (ASME B18.3 / ASTM F912).
The C45 cup bites the spotted steel arbor where an 18-8 (B80) cup would not.

One screw in each DT arbor pedestal's crown apex fixes the arbor after the
bank's end-play leaf is set (#743, Q3: "set screw located at apex of straps").
The same SKU, one per MHA-CH-08 ear, drops through the ear's arch apex onto
a flat on the rocker pivot shaft (user, 2026-10-10).

The native parts retain separate parent identities. These layout nominals
come from the vendor replica (diagnostics/diag_build_91375A106), without
importing its SolidWorks recipe or either parent's mechanical specs. The
thread-table major diameter is the existing fit nominal, not the replica's
more precise harvested diameter; test_ch_vn_arbor_set_screw keeps the shared
dimensions in step with that recipe.
"""

from __future__ import annotations

from _hole_spec import THREAD_MAJOR_MM

MM_PER_IN = 25.4

THREAD = "#4-40"
MAJOR_DIA = THREAD_MAJOR_MM[THREAD]  # 0.112 in, rounded thread-table nominal
LENGTH = 0.250 * MM_PER_IN  # nominal length, cup end to socket face
HEX_AF = 0.050 * MM_PER_IN
# The vendor's cup-end chamfer, 45 deg x one pitch: the plain point below the
# first full thread, which must span the arbor's running clearance.
POINT_LENGTH = MM_PER_IN / 40.0

if POINT_LENGTH >= LENGTH:
    raise AssertionError("set-screw point overruns its length")

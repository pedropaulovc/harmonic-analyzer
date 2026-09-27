r"""Platen plate nominals (book ch. 22, pp. 54-55).

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure: the plate envelope, the clip-screw receivers and the guide-screw
counterbored through-holes. ``build_platen`` authors the part from these; the
clip, the guide rails and the paper-drive assembly read them here instead of
importing the builder, whose sketch recipe would otherwise ride their cache
keys (#880).
"""

from __future__ import annotations

from _hole_spec import HoleSpec
from fillister_screw_spec import HEAD_H as FILLISTER_HEAD_H

PLATE_WIDTH = 269.64  # ch30-p002 Pose Studio: 300 * 0.8988 (user fit)
PLATE_HEIGHT = PLATE_WIDTH / 2.0  # user-confirmed front-face H:W = 1:2
PLATE_THICKNESS = 4.0  # DIMENSIONS.md ch22: p.55 edge-on photo (low)

# Clip-screw receivers: the stock 90114A511 shank reaches through the clip's
# integral seat and uses the platen's full 4-mm thickness as #4-40 engagement.
# These must be through taps: no blind receiver in this plate can accept the
# exact 6.35-mm under-head length without bottoming.
SOCKET_SPEC = HoleSpec("tapped", "#4-40")
SOCKET_THREAD_ENGAGEMENT = PLATE_THICKNESS
SOCKET_XY = (
    (5.3928, 58.5104), (5.3928, 127.6296),
    (264.2472, 58.5104), (264.2472, 127.6296),
)

# Guide-screw through-holes: 2 rows of 5 (heads on the front face, shanks
# into the guide rails on the back). ONE counterbored #4 fillister Hole
# Wizard feature; the artefact through/cbore dims are preserved as overrides.
GUIDE_HOLE_DIA = 3.0  # artefact through Ø (override); #4 fillister shank passes
GUIDE_HOLE_X = (26.964, 80.892, 134.82, 188.748, 242.676)
GUIDE_HOLE_Y = (13.0, 47.0)  # bottom / top rail centrelines (machine 318 / 352)
GUIDE_HOLE_XY = tuple((x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X)

# Front-face counterbores recess the stock 4.6482 x 2.7178 fillister heads
# exactly 0.2 below the front face so the recording paper lies flat.
# The Ø6.5 artefact override remains ample for the smaller stock head.
HEAD_RECESS = 0.2
CBORE_DIA = 6.5
CBORE_DEPTH = FILLISTER_HEAD_H + HEAD_RECESS

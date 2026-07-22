r"""Geometry-only contract for the pinion swing bracket.

This module contains the nominal inputs consumed by both the part and the
drive-train assembly.  It deliberately owns no drawing notes or annotation
metadata: importing it from ``build_drive_train_assembly`` therefore makes a
real geometry edit a full assembly-recipe change without treating drawing-only
wording as assembly build logic.
"""

from __future__ import annotations

# cad/config/dimensions.yaml "Chapter 25", photo-scaled.  The pivot bore is at
# the origin, the arbor bore at (0, C2C), and the blind follower-pin seat enters
# the west (-X) edge.
WIDTH = 18.0
C2C = 43.0
THICKNESS = 5.0
PIVOT_BORE = 6.35
ARBOR_BORE = 8.0
PIN_BORE = 4.0
PIN_DROP = 2.0
PIN_SEAT = 4.0

R_END = WIDTH / 2.0
HALF_WIDTH = R_END
OVERALL_LENGTH = C2C + 2.0 * R_END

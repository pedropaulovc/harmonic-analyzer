"""Column/socket interface stations shared by the frame castings.

PURE DATA with no imports, deliberately: ``harmonic_base_spec`` authors the
four socket-bore surface-finish controls (they are part-owned specification,
which the drawing purity gate requires it to read from a ``*_spec`` module),
and those controls need both the column X station and the socket bore size.
``frame_attachment_spec`` already derives the column and cross-screw heights
from ``harmonic_base_spec.STACK_HEIGHT``, so it cannot also be the home of the
bore size without a cycle. These three numbers are the interface both sides
share; ``frame_attachment_spec`` re-exports the socket pair for its existing
importers.
"""

from __future__ import annotations

# Frame column line (frame.SLDASM); the four columns sit at (+/-COLUMN_X, +/-Z).
COLUMN_X = 197.0

# Blind socket the column tube enters in the base casting. Bore diameters are
# nominal CAD geometry only: production sockets are match-fit to their assigned
# actual MHA-083 tubes, not to a fixed diameter band.
COLUMN_SOCKET_DEPTH = 25.4
COLUMN_SOCKET_DIAMETER = 25.5

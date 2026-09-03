r"""Channel-spring (installed) drawing prose -- the spec-sheet data table the
part build stamps into the SLDPRT, the isometric-view label, and the (empty)
marked-dimension contract.

Split OUT of ``channel_spring_installed_spec`` (codex #354, same treatment as
``connecting_rod_notes``): ``_spring`` (imported by ``build_channel_assembly``
for the spring geometry helpers) imports the spec's geometry constants, so
table prose living in that import closure made every table edit full-rebuild
``assembly:channel``.  Imported ONLY by ``build_channel_spring_installed`` and
the offline drawing test.
"""

from __future__ import annotations

from channel_spring_installed_spec import (
    COIL_COUNT,
    COIL_OD,
    FREE_EYE_C2C,
    HOOK_CL_RADIUS,
    HOOK_LEAD,
    INSTALLED_EYE_C2C,
    WIRE_DIA,
)

# No graphical marked dimensions -- the data table governs (see counter_spring).
DRAWING_DIMENSIONS: dict[str, set[str]] = {}

# Compact purchase/manufacturing data.  The free eye-centre length is the
# supply condition; the installed eye-centre length identifies the stretched
# state shown by the views without turning the block into a derived-data dump.
# The title-block QTY cell owns the 20-off count.
DRAWING_NOTES = "\n".join(
    (
        "EXTENSION SPRING DATA",
        f"  WIRE Ø{WIRE_DIA:.2f}    OD {COIL_OD:.2f}",
        f"  FREE LENGTH {FREE_EYE_C2C:.2f} EYE C-C",
        f"  ACTIVE COILS {COIL_COUNT}    RIGHT HAND",
        f"  ENDS 270.0 DEG LOOPS, R{HOOK_CL_RADIUS:.2f} C/L",
        f"  LEADS {HOOK_LEAD:.2f} EACH; EYES COPLANAR",
        f"  VIEW LENGTH {INSTALLED_EYE_C2C:.2f} EYE C-C (STRETCHED)",
        "  SUPPLY RELAXED",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

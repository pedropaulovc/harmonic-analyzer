"""The paper-drive disc cluster's printed length band (#2038, option A).

Owner ruling 2026-10-28: no length in the disc cluster's axial stack is faced
to fit at assembly.  Every shop-made length in it prints at
``PRINTED_LENGTH_BAND`` (``cad/config/tolerances/pd_cluster_stack.yaml``) and
names the stack it serves at its callout (drawing-guidelines.md rule 4):
``STACK_NAME``.  ``transgear_cluster_fit`` owns the closed-form stack; the
specs that own the terms read the band here, so none of them imports the
stack.

Pure data, one config read; no SolidWorks.
"""

from __future__ import annotations

import _config

PRINTED_LENGTH_BAND = float(_config.fit("pd_cluster_stack", "printed_length_band_mm"))
# The inch members' band, +/-.0007 in (+/-.0008 would exceed the stack's
# band). The mm knob-stack members keep PRINTED_LENGTH_BAND until the #290
# knob-stack PR converts them and the stack goes back to one band.
PRINTED_LENGTH_BAND_IN = 0.01778
# The stack a tight band names (rule 4), and the sheet that carries it.
STACK_NAME = "DISC CLUSTER STACK"
STACK_SHEET = "MHA-PD-00"

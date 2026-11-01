"""The paper-drive disc cluster's length bands and the stack its callouts name.

The knob train's printed lengths ahead of the cluster print at
``PRINTED_LENGTH_BAND`` (``cad/config/tolerances/pd_cluster_stack.yaml``).
The cluster's own end float is shimmed at assembly (owner ruling 2026-11-01,
#2124): the lengths that also set the collar-to-disc air and keep the hub off
the sleeve's nose print at ``FIT_LENGTH_BAND_IN``, and each names the stack
it serves at its callout (drawing-guidelines.md rule 4): ``STACK_NAME``.
``transgear_cluster_fit`` owns the closed-form stack; the specs that own the
terms read the bands here, so none of them imports the stack.

Pure data, one config read; no SolidWorks.
"""

from __future__ import annotations

import _config

PRINTED_LENGTH_BAND = float(_config.fit("pd_cluster_stack", "printed_length_band_mm"))
# +/-.001 in: the statistical collar air and the hub's recess need it.
FIT_LENGTH_BAND_IN = 0.0254
# The stack a tight band names (rule 4), and the sheet that carries it.
STACK_NAME = "DISC CLUSTER STACK"
STACK_SHEET = "MHA-PD-00"

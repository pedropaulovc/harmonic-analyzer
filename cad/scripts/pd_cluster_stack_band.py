"""The paper-drive disc cluster's length band and the stack its callouts name.

The cluster's end float is shimmed at assembly (owner ruling 2026-11-01,
#2124).  Every length that also sets the collar-to-disc air or keeps the hub
off the sleeve's nose, the knob train's three included, prints at
``FIT_LENGTH_BAND_IN``, and each names the stack it serves at its callout
(drawing-guidelines.md rule 4): ``STACK_NAME``.  ``transgear_cluster_fit``
owns the closed-form stack; the specs that own the terms read the band here,
so none of them imports the stack.

Pure data; no SolidWorks.
"""

from __future__ import annotations

# +/-.001 in: the statistical collar air and the hub's recess need it.
FIT_LENGTH_BAND_IN = 0.0254
# The stack a tight band names (rule 4), and the sheet that carries it.
STACK_NAME = "DISC CLUSTER STACK"
STACK_SHEET = "MHA-PD-00"

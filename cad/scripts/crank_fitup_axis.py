"""The crank train's nominal fit-up axis, in machine coordinates (#906 R1).

cone_line's X_CRANK / Y_CRANK is the FRAME's crank axis, where the post is laid
out.  The MHA-149 eccentric bushing throws the crank off the post bore to set
the 16T:64T backlash; the crank train (drive-train) and the chain's crank T12
(paper-drive, _chain) sit at the nominal fit-up that crank_mesh_stack solves.

Pure data, like cone_line, so paper-drive reads it without the drive-train
builder's recipe.  The base never imports it: the stack reads fit classes, and
tolerances.yaml stays out of the frame's recipe.
"""

from __future__ import annotations

from cone_line import X_CRANK, Y_CRANK
from crank_mesh_stack import FITUP_AXIS_DX, FITUP_AXIS_DY

X_CRANK_FIT = X_CRANK + FITUP_AXIS_DX
Y_CRANK_FIT = Y_CRANK + FITUP_AXIS_DY

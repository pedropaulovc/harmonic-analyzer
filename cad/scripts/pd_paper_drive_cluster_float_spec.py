"""The disc cluster's shimmed ring gap as a model dimension (MHA-PD-00 VIEW E).

Owner ruling 2026-11-01 (#2124): the cluster's float is set at assembly with
MHA-PD-VN-68 shims under the MHA-PD-24 rear bushing, read on a feeler between
the MHA-PD-25 front bushing and the MHA-PD-VN-61 ring with the cluster pushed
rearward (``transgear_cluster_fit.RING_FLOAT_RANGE``).  The window is an
assembly setting, so it is an associative model dimension, never a note.

``build_pd_paper_drive_assembly`` authors it as one hidden construction
sketch on the assembly's Right plane (sketch u, v = machine -Z, Y): a line
from the ring's rear face rearward along the pin, its length the floor
(``END_FLOAT_MIN``, from the global ``GLOBAL``) toleranced +x/-0 up to the
window's top, rounded up to the hundredth so every shimmed cluster passes.
MHA-PD-00's VIEW E prints it and the shimming step cites it; the step
prints no value of its own.  No solid or pose changes.
"""

from __future__ import annotations

import math

import _paper_drive_placement as placement
import pd_transgear_pin_spec as pin
import pd_vn_transgear_retaining_ring_spec as ring
import transgear_cluster_fit as cluster

FEATURE = "ClusterFloatSetting"
DIMENSION = "ShimmedRingGap"
GLOBAL = "ClusterRingGap"
DRAWING_DIMENSIONS = {FEATURE: {DIMENSION}}
PLACES = 2
DRAWING_PRECISION = {FEATURE: {DIMENSION: PLACES}}
VIEW_NAME = "VIEW E"

# The printed window: the floor, and the shim's thickest step above it
# rounded up to the hundredth.
NOMINAL_MM = cluster.RING_FLOAT_RANGE[0]
TOLERANCE_MM = (
    0.0,
    math.ceil((cluster.RING_FLOAT_RANGE[1] - NOMINAL_MM) * 100.0 - 1e-9) / 100.0,
)

# The line on the pin's axis plane, at mid-height of the ring's face: from
# the ring's rear face rearward (machine +Z, sketch -u).
AXIS_XY = placement.STUD_XY
LINE_Y = AXIS_XY[1] + (pin.DIA / 2.0 + ring.OD / 2.0) / 2.0
START_UV = (-cluster.RING_REAR_Z, LINE_Y)
END_UV = (START_UV[0] - NOMINAL_MM, LINE_Y)
# The dimension's text point (machine mm): forward of the ring and above it,
# on the dimension line extended past the front extension line, where only
# the pin's shank runs below it.  Over the gap the extension lines, the
# bushing's outline and its chamfer struck the text (round 10 review).
TEXT_POINT = (
    AXIS_XY[0],
    AXIS_XY[1] + ring.OD / 2.0 + 1.0,
    cluster.RING_FRONT_Z - 3.0,
)

if abs(AXIS_XY[0]) > 1e-9:
    raise AssertionError("the cluster setting's Right-plane sketch needs S on x = 0")
if not NOMINAL_MM + TOLERANCE_MM[1] >= cluster.RING_FLOAT_RANGE[1]:
    raise AssertionError("the printed ring-gap window refuses a shimmed cluster")

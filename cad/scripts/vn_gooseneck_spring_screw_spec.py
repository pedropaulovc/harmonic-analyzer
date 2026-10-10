"""Pure purchased-stock specification for the MHA-VN-054 spring screw.

McMaster 90280A583 is a zinc-plated steel, fully threaded 5/16-18 x 1 inch
slotted fillister screw. Catalog sizes were read live on 2026-10-10; derived
fillister family geometry is not vendor-equivalence verified. A supplied
native model is available; its SolidWorks diagnostic comparison is pending.
The stock frame is head +Y, shank -Y, under-head plane Y=0. Installation
belongs to the receiver and assembly, not this stock specification.
"""

from __future__ import annotations

SKU = "90280A583"
THREAD = "5/16-18 UNC"
MAJOR_DIA = 7.9375
LENGTH = 25.4
HEAD_H = 7.493
HEAD_DIA = 13.1572
PITCH = 25.4 / 18.0

# Conservative installation-stack allowance, not a published supplier tolerance.
LENGTH_MINUS = 0.76
# Shared fillister-family law; native vendor comparison is pending.
TIP_CHAMFER = 0.7 * PITCH

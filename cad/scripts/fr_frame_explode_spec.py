"""Base-deck distances of the frame assembly's builder-owned named explode
(FRAME_EXPLODED), shared by ``build_fr_frame_assembly._create_frame_explode``
and the package drawing's enlarged base-deck details. Signed millimetres along
the assembly's global axes. No SolidWorks imports.
"""

from __future__ import annotations

# The rocker-arm support (MHA-FR-05) and its four hold-down screws lift off the
# deck together and move beside the base's -X end; the screws then withdraw up
# out of the support's feet.
SUPPORT_LIFT = 35.0
SUPPORT_ASIDE_X = -320.0
SUPPORT_SCREW_WITHDRAW = 50.0
# The nameplate (MHA-FR-04) and its four screws lift together and move past the
# deck's +X end; the screws then withdraw up off the plate. At 1:8 a 25 mm lift
# printed the plate as if it were still seated in its deck pocket.
NAMEPLATE_LIFT = 75.0
NAMEPLATE_ASIDE_X = 80.0
NAMEPLATE_SCREW_WITHDRAW = 50.0

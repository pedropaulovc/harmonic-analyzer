"""Source-owned locating-seat finish, separate from the shared joint's inputs.

The joint imports the dimensional spec, so its derived seat plane cannot be
imported back there. Both the part and drawing consume this typed requirement.
"""

from _gtol_planar import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from magnifying_bracket_joint_layout import SIDE_PLATE_Z
from mg_magnifying_bracket_spec import UNIT

SURFACE_FINISHES = (
    SurfaceFinishControl(
        "foot_seat",
        SEAT_UM,
        PlanarFace((0.0, 0.0, 1.0), SIDE_PLATE_Z[1]),
        display_unit=UNIT,
    ),
)

"""Standard closed-form check of the 32T alignment pinion against the drum.

At its configured engaged centre plus/minus its configured radial stack, with
both parts' printed tip and tooth-thickness corners (``standard_mesh_checks``).
Kept apart from ``dt_mesh_checks`` so the cone gear sheets, which print the cone
checks, do not read the alignment pinion's configuration.
"""
from __future__ import annotations

import functools

import dt_alignment_pinion_spec as alignment
import dt_cylinder_gear_spec as drum
from standard_mesh_checks import MeshCheck, check_mesh, plane_gear


@functools.cache
def alignment_check() -> MeshCheck:
    nominal = alignment.ENGAGED_CENTER_DISTANCE_MM
    stack = alignment.ENGAGED_CENTER_RADIAL_STACK_MM
    return check_mesh(
        "alignment 32T/drum",
        (plane_gear(alignment.STOCK_FORM, alignment.MODULE_MM),
         plane_gear(drum.STOCK_FORM, drum.MODULE_MM), nominal),
        [plane_gear(p, alignment.MODULE_MM) for p in alignment.manufacturing_corner_profiles()],
        [plane_gear(p, drum.MODULE_MM) for p in drum.manufacturing_corner_profiles()],
        (nominal - stack, nominal + stack),
        alignment.PRESSURE_ANGLE_DEG,
        alignment.MODULE_MM,
    )

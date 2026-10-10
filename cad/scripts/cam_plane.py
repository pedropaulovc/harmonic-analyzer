r"""The channel cam plane: the rocker bank's datum (PR #1292 review F3).

Each MHA-DT-012 gear's integral cam spans FACE_WIDTH/2 .. FACE_WIDTH/2 +
CAM_THICKNESS south of its gear's station, and each connecting rod is flat
-- its ring rides the cam and its fork straddles the arm in that one plane --
so the arm plane IS the cam plane. A leaf over ``dt_cylinder_gear_spec``:
``rocker_bank_layout`` imports it, so the rocker bank reads the cam plane
without the cylinder bank's pedestals, arbor, washers, spring and gear-train
pitch. ``cylinder_bank_layout`` does not import it: it reads the gear faces
directly from ``dt_cylinder_gear_spec``.
"""

from __future__ import annotations

from dt_cylinder_gear_spec import CAM_THICKNESS, FACE_WIDTH

# Cam / connecting-rod ring mid-plane relative to its gear's station (machine z).
CAM_MID_DZ = -(FACE_WIDTH + CAM_THICKNESS) / 2.0

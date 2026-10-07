"""Gear-free cam/channel dimensions shared by the cylinder part and channel.

These are the cylinder's authored blank/cam scalars, not tooth-system
calculations. Channel placement and kinematics read this leaf directly; the
cylinder builder, drawing and bank layout use the same values. Tooth geometry
and manufacturing bands remain in ``dt_cylinder_gear_spec``.

The machine-frame drum axis and home phase remain configuration-owned through
``channel_frame_geom``; this leaf does not replace that placement authority.
"""

from __future__ import annotations

FACE_WIDTH = 3.0
# Face width controls mesh engagement across the mating cone-gear family.

# Solid stack (#743): the overall thickness, cam face to back face, IS the
# channel station pitch (machine channels.station_pitch_mm, pinned by
# test_cylinder_bank_layout), so neighbouring gears bear cam face on back face
# and set the stations the way the rocker hubs do (ch_rocker_arm_spec.HUB_LENGTH).
OVERALL_THICKNESS = 7.0565
CAM_THICKNESS = OVERALL_THICKNESS - FACE_WIDTH  # reference: the closed rod slot
ECCENTRICITY = 8.64  # cam axis offset from the bore axis

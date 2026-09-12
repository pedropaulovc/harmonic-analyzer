"""Common working-channel plane relative to the cylinder-gear station.

Pure geometry: the end-for-end gear places its integral cam on the negative-Z
side. Rod ring, fork, rocker, lever, bar mid-width and spring holes share the
cam midpoint; structural frame and fulcrum-shaft datums do not move with it.
"""

from cylinder_gear_spec import CAM_THICKNESS, FACE_WIDTH

CHANNEL_MID_DZ = -(FACE_WIDTH + CAM_THICKNESS) / 2.0

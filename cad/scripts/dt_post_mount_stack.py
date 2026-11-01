"""Nominal post/platform screw stack shared by its part owners.

The frame's interference exception reads only the screw's nominal penetration
into the platform. It must not acquire cone-line/channel dependencies merely
to subtract the screw's grip from its cut length. Physical printed-band and
cut-to-fit acceptance guards remain with the owning part specifications.
"""

import math

import _cone_axis_constants as cone_axis

POST_BODY_HEIGHT_MM = 90.0 + cone_axis.AXIS_RAISE_MM
POST_MOUNT_COUNTERBORE_DEPTH_MM = 6.0198
# .005 in: with the screw's cut end at the title block's .010 edge break, the
# thinnest plate still holds 0.90D (dt_vn_post_mount_screw_spec).
CUT_TO_FIT_SHORT_MM = 0.127  # .005 in
# MHA-DT-VN-61 prints its reference cut length in inches at these places (#290).
CUT_LENGTH_PLACES = 2

GRIP_MM = POST_BODY_HEIGHT_MM - POST_MOUNT_COUNTERBORE_DEPTH_MM
FLUSH_LENGTH_MM = GRIP_MM + cone_axis.PLATFORM_THICKNESS_MM
CUT_LENGTH_MM = round(
    math.floor((FLUSH_LENGTH_MM - CUT_TO_FIT_SHORT_MM / 2.0) / 25.4 * 10**CUT_LENGTH_PLACES + 0.5)
    / 10**CUT_LENGTH_PLACES
    * 25.4,
    9,
)
POST_SCREW_ENGAGEMENT_NOMINAL = CUT_LENGTH_MM - GRIP_MM

"""Import-free nominal post/platform screw stack shared by its part owners.

The frame's interference exception reads only the screw's nominal penetration
into the platform. It must not acquire cone-line/channel dependencies merely
to subtract the screw's grip from its cut length. Physical printed-band and
cut-to-fit acceptance guards remain with the owning part specifications.
"""

# Common raised station law: both journals translate rigidly in Y, keeping
# the crossed mesh's centre, plan, phase and support lengths unchanged.
# The unrelieved-plate printed/service budget lives in the platform spec.
CONE_AXIS_HEIGHT_MM = 1.5 * 25.4
AXIS_RAISE_MM = CONE_AXIS_HEIGHT_MM - 33.368
POST_BODY_HEIGHT_MM = 90.0 + AXIS_RAISE_MM
POST_MOUNT_COUNTERBORE_DEPTH_MM = 6.0198
PLATFORM_THICKNESS_MM = 6.35
CUT_TO_FIT_SHORT_MM = 0.3
CUT_LENGTH_PLACES = 1

GRIP_MM = POST_BODY_HEIGHT_MM - POST_MOUNT_COUNTERBORE_DEPTH_MM
FLUSH_LENGTH_MM = GRIP_MM + PLATFORM_THICKNESS_MM
CUT_LENGTH_MM = round(FLUSH_LENGTH_MM - CUT_TO_FIT_SHORT_MM / 2.0, CUT_LENGTH_PLACES)
POST_SCREW_ENGAGEMENT_NOMINAL = CUT_LENGTH_MM - GRIP_MM

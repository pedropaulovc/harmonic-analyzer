"""Machine-level anchors around the rederived cone-pivot-post-v2.

The ch30 p004 fit applies to the post and its swing carrier, not to the whole
mechanism.  The working gear/channel family is recentered independently while
remaining collinear with the post's rederived inclined journal.
"""

from __future__ import annotations


POST_ROTATION_Y_DEG = 180.0

POST_X_SHIFT = 1.484
POST_Z_SHIFT = 35.415

# Move the working gear stack toward the fixed post.  Axially the stack now
# stands on the cone shaft's integral thrust collar (#914): the collar's south
# face bears on the post's north cone-boss end face, and the 64T abuts the
# collar's north face.  The world projections follow the unchanged
# 12.5182-degree journal and recenter the channel/cylinder bank.
GEAR_AXIS_SHIFT = -33.114642580298394
MECHANISM_X_SHIFT = -5.69360213488344
MECHANISM_Z_SHIFT = 3.0875877804265315

FORMER_DRUM_X = -54.7
DRUM_X = FORMER_DRUM_X + MECHANISM_X_SHIFT

FORMER_CHANNEL_Z0 = -67.1
CHANNEL_Z0 = FORMER_CHANNEL_Z0 + MECHANISM_Z_SHIFT

# The rocker support and frame columns retain their pre-cascade locations.
FRAME_FRONT_COLUMN_Z = -112.0
FRAME_REAR_COLUMN_Z = 112.0
FRAME_COLUMN_Z_CENTER = (
    FRAME_FRONT_COLUMN_Z + FRAME_REAR_COLUMN_Z
) / 2.0
FRAME_COLUMN_Z_SPAN = FRAME_REAR_COLUMN_Z - FRAME_FRONT_COLUMN_Z

ROCKER_SUPPORT_Z = 0.0
SUMMING_Z = MECHANISM_Z_SHIFT

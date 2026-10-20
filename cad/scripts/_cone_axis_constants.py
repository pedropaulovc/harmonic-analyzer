"""Import-free installation datums shared across the cone, channels and frame.

These are geometric inputs, not post, tip-block or mounting-screw checks. The
post body outline belongs to ``dt_cone_post_envelope``, not these axis datums.
The world-axis calculation in ``cone_line`` and shaft-local ``cone_stations``
read the same anchors as the parts that locate the surrounding mechanism.
"""

# Move the working gear stack toward the fixed post.  Axially the stack now
# stands on the cone shaft's integral thrust collar (#914): the collar's south
# face bears on the post's north cone-boss end face, and the 64T abuts the
# collar's north face.  The cone line projects these fixed installation
# anchors along the configured journal incline to recenter the channel/bank.
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
FRAME_COLUMN_Z_CENTER = (FRAME_FRONT_COLUMN_Z + FRAME_REAR_COLUMN_Z) / 2.0
FRAME_COLUMN_Z_SPAN = FRAME_REAR_COLUMN_Z - FRAME_FRONT_COLUMN_Z

ROCKER_SUPPORT_Z = 0.0
SUMMING_Z = MECHANISM_Z_SHIFT

# Common raised station law: both journals translate rigidly in Y, keeping
# the crossed mesh's centre, plan, phase and support lengths unchanged.
# The unrelieved-plate printed/service budget lives in the platform spec.
CONE_AXIS_HEIGHT_MM = 1.5 * 25.4
AXIS_RAISE_MM = CONE_AXIS_HEIGHT_MM - 33.368
PLATFORM_THICKNESS_MM = 6.35

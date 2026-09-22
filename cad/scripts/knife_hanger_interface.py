r"""Knife-hanger joint interface: the stepped stud's tip in the knife-mount tap.

The single source for the joint that three slices share: the knife mount
(tap), the knife-hanger stud (turned tip and shoulder) and the summing
assembly (seat plane and engagement gates). PURE DATA plus import-time
consistency checks, with no SolidWorks/COM imports, so every consumer can
import it without pulling another slice's build script.

User ruling (2026-09-22): the joint meets the blind-thread rule in
``cad/docs/machining-dfm.md:73``, installed engagement >= 1.5 x the major
diameter of the thread that engages. A 1/2-13 thread would need 19.05 mm, but
the mount's knife bore crown is only 14.616 mm below its top face. So the
stud is a stepped, turned part: the Ø12.7 shank still passes the Ø13.49
casting holes under the visible hex head, and a shoulder SEATS on the mount's
top face above a #10-24 tip in a blind bottoming tap. The seated shoulder
preloads the joint and fixes the mount height by a turned length.
"""

from __future__ import annotations

from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

# --- the engaging thread -----------------------------------------------------
THREAD = "#10-24"
THREAD_CLASS_INTERNAL = "2B"
THREAD_PITCH_MM = 25.4 / 24.0
THREAD_MAJOR_DIA_MM = THREAD_MAJOR_MM[THREAD]  # 4.826
TAP_DRILL_DIA_MM = TAP_DRILL_MM[THREAD]  # 3.797

# machining-dfm.md:73 + user ruling: 1.5 x the engaging thread's major diameter.
REQUIRED_ENGAGEMENT_MM = 1.5 * THREAD_MAJOR_DIA_MM  # 7.239

# --- seat plane: the stud shoulder bears on the knife-mount top face ---------
# Machine y. The casting underside is the top frame's integral-crossbar lower
# face (build_top_frame: rail band 999.7..1036.2); the mount top hangs
# MOUNT_GAP below it.
CASTING_UNDERSIDE_Y = 999.7
MOUNT_GAP = 0.25
SHOULDER_SEAT_Y = CASTING_UNDERSIDE_Y - MOUNT_GAP  # 999.45

# --- stud tip (turned; knife-hanger stud) ------------------------------------
# Measured from the shoulder face to the tip end. The tip chamfer is allowed
# for and is NOT counted as engagement.
STUD_TIP_LENGTH_MM = 7.9
STUD_TIP_LENGTH_DEVIATIONS_MM = (-0.10, 0.10)
STUD_TIP_CHAMFER_MAX_MM = 0.5

# --- mount tap (knife mount) --------------------------------------------------
# Usable full thread, then the bottoming tap's two-pitch lead, then the
# 118-degree drill point below the cylindrical drill depth.
TAP_THREAD_DEPTH_MM = 8.0
TAP_THREAD_DEPTH_DEVIATIONS_MM = (0.0, 0.10)
TAP_DRILL_DEPTH_MM = 10.35
TAP_DRILL_DEPTH_DEVIATIONS_MM = (-0.10, 0.0)

# --- derived limits, checked at import ----------------------------------------
MIN_ENGAGEMENT_MM = (
    STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[0] - STUD_TIP_CHAMFER_MAX_MM
)
STUD_TIP_LENGTH_MAX_MM = STUD_TIP_LENGTH_MM + STUD_TIP_LENGTH_DEVIATIONS_MM[1]
TAP_THREAD_DEPTH_MIN_MM = TAP_THREAD_DEPTH_MM + TAP_THREAD_DEPTH_DEVIATIONS_MM[0]
TAP_RUNOUT_MIN_MM = (
    TAP_DRILL_DEPTH_MM
    + TAP_DRILL_DEPTH_DEVIATIONS_MM[0]
    - TAP_THREAD_DEPTH_MM
    - TAP_THREAD_DEPTH_DEVIATIONS_MM[1]
)

if MIN_ENGAGEMENT_MM < REQUIRED_ENGAGEMENT_MM:
    raise AssertionError(
        f"knife-hanger engagement {MIN_ENGAGEMENT_MM:.3f} mm at limits is below "
        f"1.5D = {REQUIRED_ENGAGEMENT_MM:.3f} mm"
    )
if STUD_TIP_LENGTH_MAX_MM > TAP_THREAD_DEPTH_MIN_MM:
    raise AssertionError(
        "knife-hanger stud tip can run past the usable thread before its "
        "shoulder seats"
    )
if TAP_RUNOUT_MIN_MM < 2.0 * THREAD_PITCH_MM:
    raise AssertionError("knife-mount tap leaves less than a two-pitch tap lead")

r"""MHA-MG-004 rod to MHA-MG-002 clamp threaded joint (#1559) -- PURE DATA.

The vertical rod's top end is a #4-40 UNC-2A thread turned down from the Ø5
bar; it screws into a blind #4-40 UNC-2B tap in the clamp's bottom face, on
the hex axis, until the rod's shoulder seats on that face. The shoulder is
the joint's datum: the seated shoulder carries the rod square to the block,
and the thread only holds it there. No set screw, bonding or lock (owner
ruling, #1559).

Both parts read this ONE contract: ``mg_magnifying_vertical_rod_geom`` (the
threaded end) and ``mg_magnifying_clamp_geom`` (the tapped seat). Neither
geometry module imports the other, so a rod-length edit never re-keys the
clamp and a block edit never re-keys the rod.

Every check below is at the printed worst case (drawing-guidelines.md rule 18
(thread engagement): full thread only, >= 1.5D; machining-dfm.md "Blind-thread
DFM rule"):

* full-thread engagement: the rod's shortest thread less its longest relief and
  the tip's incomplete pitch;
* the tap's full thread reaches past the rod's longest thread by the seat
  tip reserve, at the shallowest printed thread depth (the shoulder seats on
  the face, never the rod tip on incomplete thread);
* the plug tap's five-pitch lead fits between the deepest printed thread and
  the shallowest printed drill depth;
* the die run-out ends in the relief and the relief stays under the 2A root.
"""

from __future__ import annotations

import math

from _hole_spec import THREAD_MAJOR_MM, HoleSpec

MM_PER_IN = 25.4

# --- the thread ---------------------------------------------------------------
THREAD = "#4-40"
THREAD_CALLOUT = "#4-40 UNC"
THREADS_PER_IN = 40
THREAD_PITCH = MM_PER_IN / THREADS_PER_IN  # 0.635
THREAD_MAJOR = THREAD_MAJOR_MM[THREAD]  # 2.845, modelled at the basic major
# ASME B1.1 basic minor (D1 = D - 1.082532 P): the tip chamfer runs to it.
THREAD_BASIC_MINOR = THREAD_MAJOR - 1.082532 * THREAD_PITCH
# drawing-guidelines.md rule 18 (thread engagement): 1.5D of FULL thread.
ENGAGEMENT_MIN = 1.5 * THREAD_MAJOR  # 4.2675
# #4-40 UNC-2A ASME B1.1 limits as tabled by Engineers Edge (2026-10-16):
# https://www.engineersedge.com/screw_threads_chart.htm -- major
# 0.1061..0.1112 in, pitch diameter minimum 0.0925 in.
THREAD_MAJOR_2A = (0.1061 * MM_PER_IN, 0.1112 * MM_PER_IN)
THREAD_PD_2A_MIN_IN = 0.0925
# Conservative die root: a full basic half-depth below the minimum 2A pitch
# diameter (the pd_transgear_knob_shaft_spec convention).
THREAD_ROOT_2A_MIN = (THREAD_PD_2A_MIN_IN - 0.649519 / THREADS_PER_IN) * MM_PER_IN
# A die's chamfered lead leaves 1.5 pitches of incomplete thread where it
# stops; the tip chamfer to the minor takes the last pitch.
DIE_RUNOUT = 1.5 * THREAD_PITCH  # 0.9525
TIP_INCOMPLETE = THREAD_PITCH  # 0.635

# --- the rod's threaded end, read from the shoulder (the seating face) -------
# Length from the shoulder to the thread tip, with its own printed band.
ROD_THREAD_LEN = 7.50
ROD_THREAD_LEN_BAND = (0.25, -0.25)
# The relief groove at the shoulder: wide enough to take the die's run-out at
# its narrowest, its diameter under the die's root at its largest, so the die
# cuts full thread right up to the relief and nothing past it.
RELIEF_WIDTH = 1.40
RELIEF_WIDTH_BAND = (0.20, -0.20)
RELIEF_DIA = 1.75
RELIEF_DIA_BAND = (0.10, -0.10)

ROD_THREAD_LEN_MIN = ROD_THREAD_LEN + ROD_THREAD_LEN_BAND[1]
ROD_THREAD_LEN_MAX = ROD_THREAD_LEN + ROD_THREAD_LEN_BAND[0]
RELIEF_WIDTH_MIN = RELIEF_WIDTH + RELIEF_WIDTH_BAND[1]
RELIEF_WIDTH_MAX = RELIEF_WIDTH + RELIEF_WIDTH_BAND[0]
RELIEF_DIA_MAX = RELIEF_DIA + RELIEF_DIA_BAND[0]
RELIEF_DIA_MIN = RELIEF_DIA + RELIEF_DIA_BAND[1]

# Full thread on the rod: from the relief's far edge to a pitch short of the
# tip. All of it lies inside the tap's full thread (checked below), so this is
# the joint's engaged length.
ROD_FULL_THREAD_MIN = ROD_THREAD_LEN_MIN - RELIEF_WIDTH_MAX - TIP_INCOMPLETE
ENGAGEMENT_WORST = ROD_FULL_THREAD_MIN

# --- the clamp's tapped seat (blind, from the block's bottom face) -----------
# Both depths print at two places (the Hole Wizard callout's thread and drill
# depth), so each is sized at the title block's .XX band, the
# fr_harmonic_base_fasteners seat law: full thread reaches SEAT_TIP_RESERVE
# past the rod's longest thread at its shallowest print, and the plug tap's
# five-pitch lead fits under its deepest print above the shallowest drill.
HOLE_DEPTH_PLACES = 2
# The title block's .XX band as a literal (pinned to _printed_tolerance by
# test_mg_rod_clamp_joint): the rod and output-fixture geometry import this
# module, and a title-block edit must not re-key them.
HOLE_DEPTH_BAND = 0.51
SEAT_TIP_RESERVE = 0.25
PLUG_TAP_LEAD = 5.0 * THREAD_PITCH  # 3.175
_DEPTH_STEP = 0.05  # derived depths round UP to a shop-friendly step


def _ceil_step(value: float) -> float:
    return round(math.ceil(value / _DEPTH_STEP - 1e-9) * _DEPTH_STEP, 2)


ROD_TAP_THREAD_DEPTH = _ceil_step(
    ROD_THREAD_LEN_MAX + SEAT_TIP_RESERVE + HOLE_DEPTH_BAND
)
ROD_TAP_DRILL_DEPTH = _ceil_step(
    ROD_TAP_THREAD_DEPTH + 2.0 * HOLE_DEPTH_BAND + PLUG_TAP_LEAD
)
ROD_TAP_SPEC = HoleSpec(
    "tapped",
    THREAD,
    end="blind",
    depth_mm=ROD_TAP_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": ROD_TAP_THREAD_DEPTH},
)
ROD_TAP_THREAD_DEPTH_MIN = ROD_TAP_THREAD_DEPTH - HOLE_DEPTH_BAND
ROD_TAP_THREAD_DEPTH_MAX = ROD_TAP_THREAD_DEPTH + HOLE_DEPTH_BAND
ROD_TAP_DRILL_DEPTH_MIN = ROD_TAP_DRILL_DEPTH - HOLE_DEPTH_BAND
ROD_TAP_DRILL_DEPTH_MAX = ROD_TAP_DRILL_DEPTH + HOLE_DEPTH_BAND

# --- import-time worst-case guards -------------------------------------------
if ENGAGEMENT_WORST < ENGAGEMENT_MIN - 1e-9:
    raise AssertionError(
        f"MHA-MG-004 rod thread engages {ENGAGEMENT_WORST:.3f} of full thread at "
        f"worst, under 1.5D = {ENGAGEMENT_MIN:.3f}"
    )
if ROD_TAP_THREAD_DEPTH_MIN - ROD_THREAD_LEN_MAX < SEAT_TIP_RESERVE - 1e-9:
    raise AssertionError(
        "MHA-MG-002 rod tap's full thread does not clear the rod tip: the tip "
        "would bottom on incomplete thread before the shoulder seats"
    )
if ROD_TAP_DRILL_DEPTH_MIN - ROD_TAP_THREAD_DEPTH_MAX < PLUG_TAP_LEAD - 1e-9:
    raise AssertionError("MHA-MG-002 rod tap drill loses the plug tap's lead")
if RELIEF_WIDTH_MIN < DIE_RUNOUT - 1e-9:
    raise AssertionError("MHA-MG-004 relief is narrower than the die's run-out")
if RELIEF_DIA_MAX > THREAD_ROOT_2A_MIN + 1e-9:
    raise AssertionError(
        f"MHA-MG-004 relief Ø{RELIEF_DIA_MAX:.3f} max leaves thread at the 2A root "
        f"Ø{THREAD_ROOT_2A_MIN:.3f}"
    )
if not THREAD_BASIC_MINOR > RELIEF_DIA_MAX:
    raise AssertionError("MHA-MG-004 tip chamfer runs below the relief")

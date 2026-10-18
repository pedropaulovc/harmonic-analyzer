"""Pure contract for the summing assembly's builder-owned named explode
(SM_EXPLODED), shared by ``_sm_summing_explode`` and the package drawing.

The sheet's ASSEMBLY_STEPS read back to front: the gooseneck and its screw
lift off the spring, the screw backs out of the plug, the spring lifts off
the boss hook and the hook unscrews from the lever boss, leaving the jam nut
on the hook's axis between the boss and the hook's cut end, where step 2
spins it on before the hook enters the boss; then each knife-mount station
(mount, its two dowels, its washer and bolt) slides off its hex trunnion
along Z, the bolts and washers lift, the bolts clear their washers and the
dowels leave their mounts. No SolidWorks imports.
"""

from __future__ import annotations

import math

import sm_summing_lever_spec as lever
import vn_boss_hook_jam_nut_spec as jam_nut
from sm_summing_assembly_spec import (
    BOSS_HOOK,
    BOSS_JAM_NUT,
    COUNTER_SPRING,
    DOWEL,
    GOOSENECK,
    HANGER_BOLT,
    HANGER_WASHER,
    KNIFE_MOUNT,
    SPRING_SCREW,
)
from stock_anchor_geom import ANCHOR_9490T1

EXPLODED_VIEW_NAME = "SM_EXPLODED"
SOURCE_CONFIGURATION = "Default"
STATIONS = ("front", "back")
_STATION_FAMILIES = (KNIFE_MOUNT, DOWEL, HANGER_WASHER, HANGER_BOLT)
# The nut and hook rises are sized for the drawing's *Isometric at the sheet's
# 1:EXPLODED_SHEET_SCALE (the drawing's EXPLODED_SCALE reads it). There a rise
# h draws h*sqrt(2/3) tall, and a level circle of radius r draws r/sqrt(3)
# above and below its centre. So the nut's hex (corner radius
# ACROSS_CORNERS/2) draws clear of the boss top face (ANCHOR_R) once raised by
# (ANCHOR_R + corner)/sqrt(2), and clear of the hook's cut end (the wire
# radius) once the gap above it is (wire radius + corner)/sqrt(2). Each gap
# then gets PAPER_GAP_MM of paper, about the drawn hook-to-spring gap. The cut
# end starts flush with the boss underside, so the hook rises ANCHOR_H, the
# nut's rise, the nut's thickness and the gap above the nut. Both round up to
# whole mm (nut 20, hook 57). The spring and the gooseneck keep their 20 and
# 25 mm gaps above the hook and the spring (77 and 102).
# Raised 6 under a 35 mm hook (a gap of only 35 - ANCHOR_H = 15.95 under the
# cut end), the nut drew on the boss top face, crowding balloons 6 and 7
# (machinist review 20261018T153536833Z r2/r3). Now it stands on the hook's
# axis under the cut end, the order step 2 spins it on in.
PAPER_GAP_MM = 2.0
EXPLODED_SHEET_SCALE = 4.0
_MODEL_GAP_MM = PAPER_GAP_MM * EXPLODED_SHEET_SCALE / math.sqrt(2.0 / 3.0)
_NUT_CORNER_R = jam_nut.ACROSS_CORNERS / 2.0
JAM_NUT_RISE = float(
    math.ceil((lever.ANCHOR_R + _NUT_CORNER_R) / math.sqrt(2.0) + _MODEL_GAP_MM)
)
BOSS_HOOK_RISE = float(
    math.ceil(
        lever.ANCHOR_H
        + JAM_NUT_RISE
        + jam_nut.THICKNESS
        + (ANCHOR_9490T1.wire_dia_mm / 2.0 + _NUT_CORNER_R) / math.sqrt(2.0)
        + _MODEL_GAP_MM
    )
)
COUNTER_SPRING_RISE = BOSS_HOOK_RISE + 20.0
GOOSENECK_RISE = COUNTER_SPRING_RISE + 25.0
# (label, families, station, axis, signed mm): ``station`` "front"/"back"
# moves only the instances at +Z/-Z of the lever centre plane, None every
# instance; all along the assembly's global axes. Sized for the drawing's
# *Isometric (it looks from +X+Y+Z): each mount clears its trunnion end (17.9
# of slide) with room for the dowels to stand between mount and washer.
EXPLODE_STEPS: tuple[tuple[str, tuple[str, ...], str | None, str, float], ...] = (
    ("gooseneck lifts", (GOOSENECK, SPRING_SCREW), None, "y", GOOSENECK_RISE),
    ("spring screw backs out", (SPRING_SCREW,), None, "x", 35.0),
    ("counter spring lifts off hook", (COUNTER_SPRING,), None, "y", COUNTER_SPRING_RISE),
    ("boss hook unscrews", (BOSS_HOOK,), None, "y", BOSS_HOOK_RISE),
    ("jam nut lifts off boss", (BOSS_JAM_NUT,), None, "y", JAM_NUT_RISE),
    ("front station slides off", _STATION_FAMILIES, "front", "z", 45.0),
    ("back station slides off", _STATION_FAMILIES, "back", "z", -45.0),
    ("hanger bolts and washers lift", (HANGER_WASHER, HANGER_BOLT), None, "y", 40.0),
    ("hanger bolts clear washers", (HANGER_BOLT,), None, "y", 55.0),
    ("dowels leave mounts", (DOWEL,), None, "y", 20.0),
)

"""Pure contract for the summing assembly's builder-owned named explode
(SM_EXPLODED), shared by ``_sm_summing_explode`` and the package drawing.

The sheet's ASSEMBLY_STEPS read back to front: the gooseneck and its screw
lift off the spring, the screw backs out of the plug, the spring lifts off
the boss hook and the hook unscrews from the lever boss, its jam nut still
threaded on the shank between the cut end and the boss (step 2 spins the
nut on from the cut end before the hook enters the boss); then the dowels,
pressed into the crossbar's underside reams (owner ruling 2026-10-24, T+H3),
rise with the crossbar out of the mounts' round holes and slots (step 5 lifts
the mounts onto them), each knife-mount station (mount, its washer and bolt)
slides off its hex trunnion along Z, the bolts and washers lift and the
bolts clear their washers.  No SolidWorks imports.
"""

from __future__ import annotations

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

EXPLODED_VIEW_NAME = "SM_EXPLODED"
SOURCE_CONFIGURATION = "Default"
STATIONS = ("front", "back")
# The dowels are pressed into the crossbar, not carried by the mounts: they
# leave the mounts first and stay out of the station slides.
_STATION_FAMILIES = (KNIFE_MOUNT, HANGER_WASHER, HANGER_BOLT)
# (label, families, station, axis, signed mm): ``station`` "front"/"back"
# moves only the instances at +Z/-Z of the lever centre plane, None every
# instance; all along the assembly's global axes. Sized for the drawing's
# *Isometric (it looks from +X+Y+Z): each mount clears its trunnion end (17.9
# of slide).  The dowels rise DOWEL_LIFT, clear of the mounts' 7.05 slip
# engagement, their tops still under the seated washers (1036.2): 992.65
# lower end to 1012.65, top 1011.7 to 1031.7.
DOWEL_LIFT = 20.0
# The jam nut lifts less than the hook it is threaded on, so it explodes down
# the shank, off its seat on the boss top face: machinist review (main and
# #1945) read a nut left on the boss as fitted to the boss, not the eyebolt.
BOSS_HOOK_LIFT = 35.0
BOSS_JAM_NUT_LIFT = 23.0
EXPLODE_STEPS: tuple[tuple[str, tuple[str, ...], str | None, str, float], ...] = (
    ("gooseneck lifts", (GOOSENECK, SPRING_SCREW), None, "y", 80.0),
    ("spring screw backs out", (SPRING_SCREW,), None, "x", 35.0),
    ("counter spring lifts off hook", (COUNTER_SPRING,), None, "y", 55.0),
    ("boss hook unscrews", (BOSS_HOOK,), None, "y", BOSS_HOOK_LIFT),
    ("jam nut rides the shank", (BOSS_JAM_NUT,), None, "y", BOSS_JAM_NUT_LIFT),
    ("dowels rise with the crossbar", (DOWEL,), None, "y", DOWEL_LIFT),
    ("front station slides off", _STATION_FAMILIES, "front", "z", 45.0),
    ("back station slides off", _STATION_FAMILIES, "back", "z", -45.0),
    ("hanger bolts and washers lift", (HANGER_WASHER, HANGER_BOLT), None, "y", 40.0),
    ("hanger bolts clear washers", (HANGER_BOLT,), None, "y", 55.0),
)

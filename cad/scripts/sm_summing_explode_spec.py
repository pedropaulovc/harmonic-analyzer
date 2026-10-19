"""Pure contract for the summing assembly's builder-owned named explode
(SM_EXPLODED), shared by ``_sm_summing_explode`` and the package drawing.

The sheet's ASSEMBLY_STEPS read back to front: the gooseneck and its screw
lift off the spring, the screw backs out of the plug, the spring lifts off
the boss hook and the hook unscrews from the lever boss, its jam nut left
standing between the cut end and the boss (the nut goes on from the cut end
before the hook enters the boss); then each knife-mount station (mount, its
two dowels, its washer and bolt) slides off its hex trunnion along Z, the
bolts and washers lift, the bolts clear their washers and the dowels leave
their mounts. No SolidWorks imports.
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
_STATION_FAMILIES = (KNIFE_MOUNT, DOWEL, HANGER_WASHER, HANGER_BOLT)
# (label, families, station, axis, signed mm): ``station`` "front"/"back"
# moves only the instances at +Z/-Z of the lever centre plane, None every
# instance; all along the assembly's global axes. Sized for the drawing's
# *Isometric (it looks from +X+Y+Z): each mount clears its trunnion end (17.9
# of slide) with room for the dowels to stand between mount and washer.
EXPLODE_STEPS: tuple[tuple[str, tuple[str, ...], str | None, str, float], ...] = (
    ("gooseneck lifts", (GOOSENECK, SPRING_SCREW), None, "y", 80.0),
    ("spring screw backs out", (SPRING_SCREW,), None, "x", 35.0),
    ("counter spring lifts off hook", (COUNTER_SPRING,), None, "y", 55.0),
    ("boss hook unscrews", (BOSS_HOOK,), None, "y", 35.0),
    ("jam nut lifts off boss", (BOSS_JAM_NUT,), None, "y", 6.0),
    ("front station slides off", _STATION_FAMILIES, "front", "z", 45.0),
    ("back station slides off", _STATION_FAMILIES, "back", "z", -45.0),
    ("hanger bolts and washers lift", (HANGER_WASHER, HANGER_BOLT), None, "y", 40.0),
    ("hanger bolts clear washers", (HANGER_BOLT,), None, "y", 55.0),
    ("dowels leave mounts", (DOWEL,), None, "y", 20.0),
)

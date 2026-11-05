"""Native MHA-DT-00 drum-station setting, shared by build and print.

MHA-DT-22 prints the drum station as a reference: it ends on no feature of
the arbor (machinist review of farm run 20261103T022858451Z), so the setting
band belongs to the assembly that sets it.  One hidden Right-plane
construction leg runs on the arbor axis in the parked pose the assembly is
built in, from the Ø.59 head rear face to the MHA-DT-01 drum's front end.
The arbor and the drum both lie along machine Z, so the leg is true length in
a *Right view.  The model owns the native below-callout text, as for the
cylinder-bank settings (dt_cylinder_bank_setting_spec): writing it through
an imported display dimension can dirty the source.
"""

from __future__ import annotations

import _config
import pinion_rig_layout as rig
from dt_pinion_arbor_geometry import DRUM_STATION, DRUM_STATION_BAND
from pinion_rig_park_geometry import APINION_Y

FEATURE = "DrumStationSettingReference"
DIMENSION = "DrumStationSetting"

# The fit-up stack places the drum (pinion_rig_layout); the arbor rides it
# with its head rear face one DRUM_STATION in front of the drum's front end
# (build_dt_drive_train_assembly ARBOR_Z0).  Machine millimetres.
DRUM_FRONT_END_Z = rig.DRUM_FRONT_Z
HEAD_REAR_FACE_Z = DRUM_FRONT_END_Z - DRUM_STATION
# (feature, dimension, south face z, north face z), as the bank's LEGS.
LEGS = ((FEATURE, DIMENSION, HEAD_REAR_FACE_Z, DRUM_FRONT_END_Z),)
AXIS_Y = APINION_Y
DRAWING_DIMENSIONS = {feature: {name} for feature, name, _south, _north in LEGS}
# The package prints decimal inch (#290): the setting and its ±.010 band at
# three places, the band's own (drawing-guidelines rule 3).
PLACES = 3
DRAWING_PRECISION = {feature: {name: PLACES} for feature, name, _south, _north in LEGS}
# The one band every drum-station stack reads (land cover, drum ends on the
# journals, collar gap, rig advance/retreat): ±.010 in, printed exactly.
DIMENSION_BANDS = {DIMENSION: (DRUM_STATION_BAND, -DRUM_STATION_BAND)}
TOLERANCE_PRECISION = PLACES
ARBOR_NUMBER = _config.parts("dt-pinion-arbor")["number"]
DRUM_NUMBER = _config.parts("dt-alignment-pinion")["number"]
# What is set (the drum's front end), from where (the arbor head's rear face)
# and when (the bond); widest line on top, clear of the extension lines.
DIMENSION_CALLOUTS = {
    DIMENSION: (
        "DRUM STATION, SET AT BOND:\n"
        f"{ARBOR_NUMBER} HEAD REAR FACE\n"
        f"TO {DRUM_NUMBER} FRONT END"
    ),
}

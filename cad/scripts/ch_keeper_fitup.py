"""MHA-CH-00 keeper fit-up on the top frame: where the two lug inner faces end
up (owner ruling 2026-11-24, fit audit part 2, C10: "Yes: rear keeper set to
the stack over a .020 leaf.").

The front (right, -Z) lug inner face is set by DRO off the line of the upper
socket centres at the title block's band. The twenty bare MHA-CH-02 levers
go on the fulcrum shaft with the keepers, close against the front lug, and
the rear keeper is pushed up to the last hub over a REAR_KEEPER_LEAF_MM leaf.
So the rear face follows the hub stack, and the bank's end play is the leaf.

The faces' deviations from the model's nominals (ch_fulcrum_keeper_spec
KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM) feed the shaft's flat-station window
(ch_fulcrum_shaft_spec), the keeper feet's margins to the frame bosses
(build_fr_top_frame) and the levers' offsets from their stations
(test_channel_axial_budget's bar lean). The lever count and hub length are
literals here, so those part recipes do not read the channel kinematics;
ch_channel_assembly_spec checks them against rocker_bank_layout and
ch_channel_lever_spec.
"""

from __future__ import annotations

from _printed_tolerance import printed_band_mm
from ch_fulcrum_keeper_spec import KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM

MM_PER_IN = 25.4
# MHA-CH-00 prints decimal inch (#290; ch_channel_assembly_spec asserts it).
UNIT = "in"
FRONT_FACE_PLACES = 3
FRONT_FACE_BAND_MM = printed_band_mm(FRONT_FACE_PLACES, unit=UNIT)  # +/-.005
# The DRO is set to the printed value (1.370), not the model's 1.3702.
FRONT_FACE_SET_MM = (
    round(KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0] / MM_PER_IN, FRONT_FACE_PLACES)
    * MM_PER_IN
)
REAR_KEEPER_LEAF_MM = 0.020 * MM_PER_IN
# How far the pushed keeper may stand off the leaf once clamped: a stated
# allowance for the leaf's give and the clamp's nudge, not a measurement.
REAR_KEEPER_PUSH_SETTLE_MM = 0.001 * MM_PER_IN
# rocker_bank_layout.COUNT and ch_channel_lever_spec's hub, .300 +.001/0.
LEVER_COUNT = 20
LEVER_HUB_LENGTH_MM = (7.62, 7.6454)
LEVER_STACK_MM = tuple(LEVER_COUNT * hub for hub in LEVER_HUB_LENGTH_MM)
_FRONT = (FRONT_FACE_SET_MM - FRONT_FACE_BAND_MM, FRONT_FACE_SET_MM + FRONT_FACE_BAND_MM)
_REAR = (
    _FRONT[0] + LEVER_STACK_MM[0] + REAR_KEEPER_LEAF_MM - REAR_KEEPER_PUSH_SETTLE_MM,
    _FRONT[1] + LEVER_STACK_MM[1] + REAR_KEEPER_LEAF_MM + REAR_KEEPER_PUSH_SETTLE_MM,
)
# (lower, upper) deviation of each inner face from the model's nominal.
FACE_DEVIATIONS_MM = {
    "front": tuple(z - KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0] for z in _FRONT),
    "rear": tuple(z - KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1] for z in _REAR),
}  # front (-.0052, +.0048), rear (-.0262, +.0058) in
# The bank's end play: the leaf, less or plus the settle.
END_PLAY_MM = (
    REAR_KEEPER_LEAF_MM - REAR_KEEPER_PUSH_SETTLE_MM,
    REAR_KEEPER_LEAF_MM + REAR_KEEPER_PUSH_SETTLE_MM,
)
# Each lever floats on the shaft between its neighbours and the lugs. The
# model stands the bank midway between the nominal lugs, its front hub face
# half the nominal play off the front face; a lever stands furthest from its
# station with every hub closed on one lug.
_PITCH = LEVER_HUB_LENGTH_MM[0]
_BANK_FRONT_NOMINAL = KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0] + (
    KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[1]
    - KEEPER_INNER_FACE_FROM_FRONT_SOCKET_MM[0]
    - LEVER_COUNT * _PITCH
) / 2.0
LEVER_STATION_OFFSET_MM = (
    min(
        front + j * hub - (_BANK_FRONT_NOMINAL + j * _PITCH)
        for j in range(LEVER_COUNT)
        for front in _FRONT
        for hub in LEVER_HUB_LENGTH_MM
    ),
    max(
        front
        + LEVER_COUNT * hub
        + REAR_KEEPER_LEAF_MM
        + REAR_KEEPER_PUSH_SETTLE_MM
        - (LEVER_COUNT - j) * hub
        - (_BANK_FRONT_NOMINAL + j * _PITCH)
        for j in range(LEVER_COUNT)
        for front in _FRONT
        for hub in LEVER_HUB_LENGTH_MM
    ),
)  # (-.0252, +.0248) in

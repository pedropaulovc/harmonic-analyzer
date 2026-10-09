"""Signed actual crank phase data from the single committed calibration packet.

Call require_qualified() before reading numeric data. It admits the full
physical source, six-source capture, same-pose continuous proofs, selected
native degree datum and fresh actual 21 read queries. No missing observation
is a zero, and no nominal point hull is a whole-period lag certificate.
"""
from __future__ import annotations

from crank_mesh_calibration import CALIBRATION,PACKET_SHA256

QUALIFIED = CALIBRATION.get("qualified") is True
REFUSAL = CALIBRATION.get("refusal") or "Current actual crank source/phase packet is not qualified."
_PHASE = CALIBRATION.get("phase_qualification") if QUALIFIED else None
if QUALIFIED and (not isinstance(_PHASE,dict) or _PHASE.get("qualified") is not True):
    raise ValueError("qualified crank packet lacks its actual phase qualification")

try:
    CONE_SHAFT_SENSE = _PHASE["CONE_SHAFT_SENSE"] if QUALIFIED else None
    CERTIFIED_PHASE_OFFSET_DEG = _PHASE["CERTIFIED_PHASE_OFFSET_DEG"] if QUALIFIED else None
    STALL_DRIVER_RAD = tuple(_PHASE["STALL_DRIVER_RAD"]) if QUALIFIED else ()
    CONE_SHAFT_LAG_RAD = tuple(_PHASE["CONE_SHAFT_LAG_RAD"]) if QUALIFIED else ()
    BOUND_RAD = tuple(_PHASE["BOUND_RAD"]) if QUALIFIED else ()
    # Actual signed running cone-shaft radians, all source/profile cells and
    # the WHOLE joint tooth period. Off-stall minus stall uses hi-lo once.
    CONE_SHAFT_LAG_INTERVAL_RAD = tuple(_PHASE["CONE_SHAFT_LAG_INTERVAL_RAD"]) if QUALIFIED else None
    GEOMETRY_SHA256 = CALIBRATION["geometry_sha256"] if QUALIFIED else None
    MEASUREMENT_ENGINE_SHA256 = CALIBRATION["measurement_engine_sha256"] if QUALIFIED else None
    MEASUREMENT_ENGINE_SOURCES_SHA256 = CALIBRATION["measurement_engine_sources_sha256"] if QUALIFIED else None
except (KeyError,TypeError) as exc:
    raise ValueError("qualified crank packet has missing or malformed signed phase fields") from exc


def require_qualified() -> dict:
    """Return the fully admitted packet; never just inspect a green flag."""
    from crank_mesh_stack import require_qualified as admit
    packet = admit()
    from crank_mesh_calibration import PACKET_SHA256 as current_packet_sha256
    from stock_form_contact_certificate import same_numeric_tree
    if packet is not CALIBRATION or PACKET_SHA256 != current_packet_sha256:
        raise ValueError("phase provider and fully admitted crank packet have different frozen byte identities")
    phase = packet["phase_qualification"]
    for name in ("CONE_SHAFT_SENSE","CERTIFIED_PHASE_OFFSET_DEG","STALL_DRIVER_RAD",
                 "CONE_SHAFT_LAG_RAD","BOUND_RAD","CONE_SHAFT_LAG_INTERVAL_RAD"):
        if not same_numeric_tree(globals()[name],phase[name]):
            raise ValueError(f"frozen crank phase provider field differs from admitted packet: {name}")
    for name,field in (("GEOMETRY_SHA256","geometry_sha256"),
                       ("MEASUREMENT_ENGINE_SHA256","measurement_engine_sha256"),
                       ("MEASUREMENT_ENGINE_SOURCES_SHA256","measurement_engine_sources_sha256")):
        if globals()[name] != packet[field]:
            raise ValueError(f"frozen crank phase identity differs from admitted packet: {name}")
    return packet

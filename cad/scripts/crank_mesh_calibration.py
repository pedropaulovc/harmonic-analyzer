"""Actual source-captured finite stock16/64 calibration packet.

The ordinary committed JSON is produced by the real continuous study, not by a
native task. Missing evidence remains an explicit refusal; the earlier finite
surface-budget exhaustion is neither zero error nor physical infeasibility.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

_PACKET_PATH = Path(__file__).resolve().parents[1] / "calibration/dt-crank-stock-form.json"


def _canonical_sha(packet):
    return hashlib.sha256(json.dumps(packet,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _read_packet() -> tuple[dict,str | None]:
    try:
        raw = _PACKET_PATH.read_bytes()
    except FileNotFoundError:
        return {
            "qualified":False,"geometry_sha256":None,"native_certificate":False,"cases":{},
            "refusal":(
                "No current-source all-corner whole-period crank qualification packet is published. "
                "The recorded nominal C+0.4 phase-zero study exhausted 500000 surface boxes "
                "with residual 0.849669 mm, source_unchanged=true; no physical infeasibility was proved."),
        },None
    def nonfinite(value):
        raise ValueError(f"nonfinite number in actual crank calibration packet: {value}")
    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            nonfinite(value)
        return number
    try:
        packet = json.loads(raw.decode("utf-8"),parse_constant=nonfinite,parse_float=finite_float)
    except (ValueError,TypeError) as exc:
        raise ValueError("malformed committed actual crank calibration packet") from exc
    if (not isinstance(packet,dict) or packet.get("family") != "dt_crank_stock_form"
            or type(packet.get("schema_version")) is not int or packet["schema_version"] != 1
            or type(packet.get("qualified")) is not bool or packet.get("native_certificate") is not False):
        raise ValueError("committed crank packet lacks its actual family/schema/qualification identity")
    return packet,hashlib.sha256(raw).hexdigest()


CALIBRATION,PACKET_SHA256 = _read_packet()
_CONTENT_SHA256 = _canonical_sha(CALIBRATION)


def require_current_packet_bytes() -> dict:
    """Refuse disappeared/replaced bytes or mutated parsed data after import."""
    if PACKET_SHA256 is None:
        raise ValueError(CALIBRATION["refusal"])
    try:
        current = hashlib.sha256(_PACKET_PATH.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("actual committed crank calibration packet is unavailable") from exc
    if current != PACKET_SHA256 or _canonical_sha(CALIBRATION) != _CONTENT_SHA256:
        raise ValueError("actual crank calibration packet bytes/data changed after phase fields were frozen")
    return CALIBRATION

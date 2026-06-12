r"""Reproduction script: drive chain (book ch. 23/30; M6.8 photo-tuning).

The bead chain looping the two CHAIN-WRAPPED removable gears (crank
shaft T12 -> knob shaft T24; ch. 23: the chain rides the removables'
m2 teeth -- swapping them is what changes the platen ratio). Every
chain-side ch30 plate (p002/p005/p006) shows it: a taut run on the
pinion-bar side and a visibly drooping slack run on the other. For
photo fidelity it is modeled as a rigid closed band in its working
pose -- a flat extrusion, not linked/beaded.

Geometry (local frame: knob wrap centre at the origin, machine xy
pre-mirror; crank centre from build_drive_train_assembly X_CRANK /
Y_DRIVE minus build_output_assembly KNOB_SHAFT_XY): two UNEQUAL wrap
arcs whose band floats 0.41 clear OUTSIDE the gear tooth tips (a real
chain wraps at the teeth; a solid band there would intersect them), the
common external tangent taut line on the +n side (the pinion-bar side),
and a slack arc sagging SAG below the straight external tangent on the
-n side, tangent-continuous at all four junctions (internal tangency:
|C - A| = R_slack - WRAP_R_A, |C - B| = R_slack - WRAP_R_B; R_slack is
solved numerically for the SAG droop).

The band is drawn as nested offset loops (centreline +-BAND_W/2) and
extruded BAND_T; offsets of tangent-continuous arc/line chains stay
tangent-continuous, and the band area is exactly BAND_W x centreline
length, giving an analytic volume gate.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_drive_chain.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    BAR_STEEL,
    apply_color,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "drive-chain"
MATERIAL = "Plain Carbon Steel"  # bead chain reads mid-grey in the plates

# Chain-wheel centres, machine xy pre-mirror.
KNOB_CENTRE = (65.0, 241.78)  # build_output_assembly KNOB_SHAFT_XY (ch30
# rest state: latch C2C 66.05 from the stud, y clamped under the pinion bar)
CRANK_CENTRE = (118.0, 126.8)  # build_drive_train_assembly X_CRANK, Y_DRIVE

TIP_R_T24 = 26.0  # mounted removables, module 2: tip r = (T + 2) * 2 / 2
TIP_R_T12 = 14.0
BAND_W = 5.0  # band width (radial)
BAND_T = 4.5  # band thickness (z)
TIP_AIR = 0.41  # band inner edge floats this clear of the tooth tips
WRAP_R_A = TIP_R_T24 + TIP_AIR + BAND_W / 2.0  # 28.91 (knob T24)
WRAP_R_B = TIP_R_T12 + TIP_AIR + BAND_W / 2.0  # 16.91 (crank T12)
SAG = 18.0  # slack-run droop below the straight tangent (p006 crop)

# --- centreline geometry (A = knob = origin, B = crank) ----------------------
_BX = CRANK_CENTRE[0] - KNOB_CENTRE[0]
_BY = CRANK_CENTRE[1] - KNOB_CENTRE[1]
_D = math.hypot(_BX, _BY)  # 126.61
_UX, _UY = _BX / _D, _BY / _D
_NX, _NY = -_UY, _UX  # taut-side normal (local upper-right)

# Common external tangents of the unequal wrap circles: unit normal
# m = u * (rA - rB) / D +- n * k touches A at A + rA*m and B at B + rB*m.
_DR = (WRAP_R_A - WRAP_R_B) / _D
_K = math.sqrt(1.0 - _DR * _DR)
# taut side (+n):
_TNX = _UX * _DR + _NX * _K
_TNY = _UY * _DR + _NY * _K
TAUT_LEN = _D * _K
# slack side (-n) straight tangent, the droop reference line:
_SNX = _UX * _DR - _NX * _K
_SNY = _UY * _DR - _NY * _K
_SC0 = WRAP_R_A  # line constant: (A + rA*m) . m with A at the origin


def _unit(px: float, py: float) -> tuple[float, float]:
    n = math.hypot(px, py)
    return px / n, py / n


def _slack_centre(rs: float) -> tuple[float, float]:
    """Centre of the slack arc, internally tangent to both wraps, +n side."""
    p = (_D * _D + (WRAP_R_B - WRAP_R_A) * (2.0 * rs - WRAP_R_A - WRAP_R_B)) / (
        2.0 * _D
    )
    q2 = (rs - WRAP_R_A) ** 2 - p * p
    if q2 < 0.0:
        raise ValueError(f"slack radius {rs} too small")
    q = math.sqrt(q2)
    return _UX * p + _NX * q, _UY * p + _NY * q


def _droop(rs: float) -> float:
    """Bulge of the slack arc beyond the straight -n tangent line."""
    cx, cy = _slack_centre(rs)
    return cx * _SNX + cy * _SNY + rs - _SC0


# Solve droop(SLACK_R) = SAG (droop decreases monotonically with rs).
_LO = max(WRAP_R_A, WRAP_R_B) + _D / 2.0  # safely past the q2 > 0 floor
while _droop(_LO) < SAG:  # pragma: no cover - geometry sanity
    _LO *= 0.9
_HI = 10000.0
assert _droop(_LO) > SAG > _droop(_HI)
for _ in range(80):
    _MID = 0.5 * (_LO + _HI)
    if _droop(_MID) > SAG:
        _LO = _MID
    else:
        _HI = _MID
SLACK_R = 0.5 * (_LO + _HI)
_CX, _CY = _slack_centre(SLACK_R)

_GAX, _GAY = _unit(-_CX, -_CY)  # C -> A radial (slack tangent at knob)
_GBX, _GBY = _unit(_BX - _CX, _BY - _CY)  # C -> B radial (slack tangent at crank)

# Loop traversal is CCW throughout (add_arc draws CCW start -> end):
# wrap A from the taut normal to gA, slack arc from gA to gB about C,
# wrap B from gB to the taut normal, taut line back. The three arc spans
# must close the full turn.
_ANG_N = math.atan2(_TNY, _TNX)
_ANG_GA = math.atan2(_GAY, _GAX)
_ANG_GB = math.atan2(_GBY, _GBX)


def _ccw(a_from: float, a_to: float) -> float:
    return (a_to - a_from) % (2.0 * math.pi)


SPAN_A = _ccw(_ANG_N, _ANG_GA)
SPAN_SLACK = _ccw(_ANG_GA, _ANG_GB)
SPAN_B = _ccw(_ANG_GB, _ANG_N)
assert abs(SPAN_A + SPAN_SLACK + SPAN_B - 2.0 * math.pi) < 1e-9

CENTRELINE_LEN = (
    WRAP_R_A * SPAN_A + WRAP_R_B * SPAN_B + SLACK_R * SPAN_SLACK + TAUT_LEN
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Both offset loops in one sketch -> band ring on extrude. Inference
    # OFF: arc endpoints sit near the origin-centred wrap circle and snap.
    check("create_sketch chain band", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = []
    for off in (BAND_W / 2.0, -BAND_W / 2.0):
        ra = WRAP_R_A + off
        rb = WRAP_R_B + off
        rs = SLACK_R + off
        ents = [
            await adapter.add_arc(  # wrap at the knob T24
                0.0, 0.0, ra * _TNX, ra * _TNY, ra * _GAX, ra * _GAY
            ),
            await adapter.add_arc(  # slack run, sagging on the -n side
                _CX, _CY,
                _CX + rs * _GAX, _CY + rs * _GAY,
                _CX + rs * _GBX, _CY + rs * _GBY,
            ),
            await adapter.add_arc(  # wrap at the crank T12
                _BX, _BY,
                _BX + rb * _GBX, _BY + rb * _GBY,
                _BX + rb * _TNX, _BY + rb * _TNY,
            ),
            await adapter.add_line(  # taut run on the +n side
                _BX + rb * _TNX, _BY + rb * _TNY, ra * _TNX, ra * _TNY
            ),
        ]
        for label, res in zip(("wrap-knob", "slack", "wrap-crank", "taut"), ents):
            entities.append(check(f"add {label} (off {off:+.1f})", res))
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "chain band sketch", fix_entities=entities)
    check("exit_sketch chain band", await adapter.exit_sketch())
    check(
        "extrude chain band",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAND_T)),
    )

    res = await adapter.get_mass_properties()
    vol = res.data.volume
    expected = CENTRELINE_LEN * BAND_W * BAND_T
    print(f"  volume: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"chain volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, BAR_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: drive chain (book ch. 23/30; M6.8 photo-tuning).

The bead chain looping the two chain-sprockets (crank shaft -> knob
shaft). Every chain-side ch30 plate (p002/p005/p006) shows it: a taut
run on the pinion-bar side and a visibly drooping slack run on the
other. build_chain_sprocket.py left the chain out ("flexible element,
out of scope"); for photo fidelity it is modeled as a rigid closed band
in its working pose -- a flat extrusion, not linked/beaded.

Geometry (local frame: knob sprocket centre at the origin, machine xy
pre-mirror; crank centre from build_drive_train_assembly X_CRANK /
Y_DRIVE minus build_output_assembly KNOB_SHAFT_XY): two wrap arcs whose
band floats 0.41 clear OUTSIDE the sprocket tooth tips (a real chain
meshes at pitch radius 25.92, but a solid band there would intersect
the teeth; +5.3 mm is sub-pixel at render scale), an outer-tangent taut
line on the +n side (the pinion-bar side), and a slack arc sagging SAG
below the straight tangent on the -n side, tangent-continuous at all
four junctions (internal tangency: |C - A| = R_slack - WRAP_R).

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

# Sprocket centres, machine xy pre-mirror.
KNOB_CENTRE = (32.1939, 241.7824)  # build_output_assembly KNOB_SHAFT_XY:
# PINION_AXIS (0, 253.5) + C2C 34.26 at -20 deg
CRANK_CENTRE = (118.0, 126.8)  # build_drive_train_assembly X_CRANK, Y_DRIVE

SPROCKET_TIP_R = 28.34  # build_chain_sprocket OUTER_RADIUS
BAND_W = 5.0  # band width (radial)
BAND_T = 4.5  # band thickness (z) = sprocket face width
WRAP_R = 31.25  # wrap centreline: inner edge 28.75 keeps the 0.25+ margin
# over the tooth tips (28.34)
SAG = 18.0  # slack-run droop below the straight tangent (p006 crop)

# --- centreline geometry (A = knob = origin, B = crank) ----------------------
_BX = CRANK_CENTRE[0] - KNOB_CENTRE[0]
_BY = CRANK_CENTRE[1] - KNOB_CENTRE[1]
_D = math.hypot(_BX, _BY)  # 143.47
_UX, _UY = _BX / _D, _BY / _D
_NX, _NY = -_UY, _UX  # taut-side normal (local upper-right)

# Slack arc: centre C on the +n side of the AB midpoint, internally
# tangent to both wrap circles (|C - A| = R - WRAP_R), passing SAG below
# the straight -n tangent at mid-span.
_H = ((_D / 2.0) ** 2 - SAG**2) / (2.0 * SAG)
SLACK_R = _H + WRAP_R + SAG
_CX = _BX / 2.0 + _NX * _H
_CY = _BY / 2.0 + _NY * _H


def _unit(px: float, py: float) -> tuple[float, float]:
    n = math.hypot(px, py)
    return px / n, py / n


_GAX, _GAY = _unit(-_CX, -_CY)  # C -> A radial (slack tangent at knob)
_GBX, _GBY = _unit(_BX - _CX, _BY - _CY)  # C -> B radial (slack tangent at crank)

# Loop traversal is CCW throughout (add_arc draws CCW start -> end):
# wrap A from n to gA, slack arc from gA to gB about C, wrap B from gB
# to n, taut line back. The three arc spans must close the full turn.
_ANG_N = math.atan2(_NY, _NX)
_ANG_GA = math.atan2(_GAY, _GAX)
_ANG_GB = math.atan2(_GBY, _GBX)


def _ccw(a_from: float, a_to: float) -> float:
    return (a_to - a_from) % (2.0 * math.pi)


SPAN_A = _ccw(_ANG_N, _ANG_GA)
SPAN_SLACK = _ccw(_ANG_GA, _ANG_GB)
SPAN_B = _ccw(_ANG_GB, _ANG_N)
assert abs(SPAN_A + SPAN_SLACK + SPAN_B - 2.0 * math.pi) < 1e-9

CENTRELINE_LEN = WRAP_R * (SPAN_A + SPAN_B) + SLACK_R * SPAN_SLACK + _D


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Both offset loops in one sketch -> band ring on extrude. Inference
    # OFF: arc endpoints sit near the origin-centred wrap circle and snap.
    check("create_sketch chain band", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = []
    for off in (BAND_W / 2.0, -BAND_W / 2.0):
        rw = WRAP_R + off
        rs = SLACK_R + off
        ents = [
            await adapter.add_arc(  # wrap at the knob sprocket
                0.0, 0.0, rw * _NX, rw * _NY, rw * _GAX, rw * _GAY
            ),
            await adapter.add_arc(  # slack run, sagging on the -n side
                _CX, _CY,
                _CX + rs * _GAX, _CY + rs * _GAY,
                _CX + rs * _GBX, _CY + rs * _GBY,
            ),
            await adapter.add_arc(  # wrap at the crank sprocket
                _BX, _BY,
                _BX + rw * _GBX, _BY + rw * _GBY,
                _BX + rw * _NX, _BY + rw * _NY,
            ),
            await adapter.add_line(  # taut run on the +n side
                _BX + rw * _NX, _BY + rw * _NY, rw * _NX, rw * _NY
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

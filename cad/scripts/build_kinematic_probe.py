r"""Kinematic probe: prove the crank drives the paper feed (codex #189 kinematic test).

Turning the crank T12 sprocket must propagate through the WHOLE feed train:

    T12 (crank) --Belt/Chain 24:48--> T24 (knob wheel) --Lock--> knob shaft + fine pinion
    T24 --rack-pinion--> platen (the paper feed)

and the roller chain rides both sprockets. This probe opens the saved default-`free`
paper-drive model, DRIVES the crank by a known angle (authors a temporary angle mate
on the T12 Right-plane dihedral, then ForceRebuild3), and asserts each downstream
component moved by the coupled amount. Cluster rotations are compared by MAGNITUDE
(axis-angle angle), never by projection onto a shared axis: the knob shaft is modeled
on a spin axis PERPENDICULAR to the sprockets' (verified live -- it turns about
global Y while T24 turns about Z), so a shared-axis projection would read a false
zero for it. The two SPROCKETS, though, share the global Z axis, so their SIGNED
Z rotations are also compared -- ratio AND sense:

  * the Belt/Chain feature (EngageBelt, PulleyDiameters forced to the pitch values
    24/48 post-create -- the picked tip faces would couple 28:52 = 0.538) drives T24
    at the EXACT 12:24 = 0.500 reduction off the crank, asserted tightly,
  * T24 turns the SAME direction as T12 (signed Z angles) -- a chain couples both
    sprockets the same way; an external gear mate would REVERSE (the bug class the
    magnitude-only probe could not see),
  * knob shaft and fine 24T pinion turn by the SAME magnitude as T24 (Lock-mated
    cluster -- the whole feed train follows; codex #189 :592),
  * the platen translates by ``NET_RACK_TRAVEL_PER_KNOB_REV * (dTheta_T24 / 360)``,
    checked against the MEASURED T24 rotation (exact downstream of T24).

The roller-chain COMPONENT PATTERN has NO native coupling to sprocket rotation --
SolidWorks chain-pattern instances cannot be mated to other components. So link
travel is not automatic; the probe ATTEMPTS it by advancing the Dynamic pattern's
seed link along the loop by the matching arc and reports whether the links moved --
a best-effort demonstration, not a hard gate.

The doc is NEVER saved (this probe only drives + reads), so the on-disk free model is
untouched.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_kinematic_probe.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _chain import PITCH_R_T12, loop_point_tangent
from _common import OUT_SLDASM, check, log, run_build
from _assembly import (
    angle_driver,
    component_names,
    component_origin,
    component_transform,
    named_ref,
)

import _telemetry
from preflight_release import _discard_open_documents

# Coupled ratios (from the paper-drive build): gear mate T12:T24 = 12:24, so the
# knob side turns at half the crank; the platen feeds NET mm per knob revolution.
from build_paper_drive_assembly import (
    CHAIN_CRANK_CENTRE,
    KNOB_SHAFT_XY,
    NET_RACK_TRAVEL_PER_KNOB_REV,
    PINION_PD_R,
    SPARE_GEAR_POS,
)

DRIVE_DEG = 30.0    # crank test rotation
CRANK_TOL = 2.0     # deg: the temporary driver must hit DRIVE_DEG on BOTH sides
# The crank T12 -> knob T24 tie is the Belt/Chain feature with PulleyDiameters
# FORCED to the pitch values (24/48) post-create -- the picked tooth-tip faces
# would otherwise couple at 28:52 = 0.538, a ~7.7% feed error. The probe
# asserts the true 0.500 TIGHTLY, and the same-sense rotation a chain enforces.
CHAIN_RATIO = 0.5   # T12:T24 = 12:24 exact (belt/chain coupling, pitch diams)
RATIO_TOL = 0.03    # measured T24/crank vs CHAIN_RATIO (pose/numeric slack)
ANG_TOL = 1.2       # deg: locked cluster parts turn by equal magnitude (near-exact)
LIN_TOL = 0.35      # mm: platen feed vs NET * measured-T24 / 360


def _rot(adapter: Any, name: str) -> list[float]:
    """A component's rotation as a row-major 3x3 (the first 9 Transform2 entries)."""
    return component_transform(adapter, name)[:9]


def _rot_angle_deg(after: list[float], before: list[float]) -> float:
    """Magnitude (deg) of the relative rotation ``after @ before^T`` -- the angle of
    its axis-angle form, via ``acos((trace - 1) / 2)`` (valid 0..180 deg).

    Axis-AGNOSTIC on purpose: each cluster part is modeled on its OWN axis (the knob
    shaft's spin axis is perpendicular to the sprockets' -- verified live, its rel.
    rotation is about global Y while T24's is about Z), so a shared-axis projection
    reads a FALSE zero for the shaft. Locked parts turn by equal MAGNITUDE, so that
    is what we compare."""
    bt = [before[0], before[3], before[6],
          before[1], before[4], before[7],
          before[2], before[5], before[8]]          # before^T
    m = [sum(after[r * 3 + k] * bt[k * 3 + c] for k in range(3))
         for r in range(3) for c in range(3)]        # after @ before^T
    trace = m[0] + m[4] + m[8]
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def _rel_z_angle_deg(after: list[float], before: list[float]) -> float:
    """SIGNED rotation about +Z (deg) of ``after @ before^T``.

    For the two SPROCKETS only: both spin about global Z (verified live), so the
    sign is meaningful -- Z-rotation by theta has ``m = [[c,-s,.],[s,c,.],...]``,
    hence ``atan2(m[1][0] - m[0][1], m[0][0] + m[1][1]) = theta``. (The knob
    shaft/cluster parts spin about OTHER axes; they keep the axis-agnostic
    magnitude compare above.)"""
    bt = [before[0], before[3], before[6],
          before[1], before[4], before[7],
          before[2], before[5], before[8]]          # before^T
    m = [sum(after[r * 3 + k] * bt[k * 3 + c] for k in range(3))
         for r in range(3) for c in range(3)]        # after @ before^T
    return math.degrees(math.atan2(m[3] - m[1], m[0] + m[4]))


def _origin_xy(adapter: Any, name: str) -> tuple[float, float]:
    o = component_origin(adapter, name)
    return (o[0], o[1])


def _removables_by_role(adapter: Any) -> dict[str, str]:
    """Map T12/T24/T18 -> the instance name, matched by |origin - known centre|.
    The three ``transgear-removable`` instances share a stem, so identify them by
    position: T12 at the crank centre, T24 at the knob shaft, T18 the loose spare."""
    known = {
        "T12": CHAIN_CRANK_CENTRE,
        "T24": KNOB_SHAFT_XY,
        "T18": SPARE_GEAR_POS[:2],
    }
    insts = [n for n in component_names(adapter) if n.startswith("transgear-removable")]
    out: dict[str, str] = {}
    for role, (kx, ky) in known.items():
        best, bestd = None, 1e9
        for n in insts:
            x, y = _origin_xy(adapter, n)
            # match on |x| (the default mirror flips the X sign) and y.
            d = math.hypot(abs(x) - abs(kx), y - ky)
            if d < bestd:
                best, bestd = n, d
        if bestd > 8.0:
            raise RuntimeError(f"could not locate the {role} removable "
                               f"(nearest {best} at {bestd:.1f} mm)")
        out[role] = best
    if len(set(out.values())) != 3:
        raise RuntimeError(f"removable role match collided: {out}")
    return out


def _one(adapter: Any, stem: str) -> str:
    hits = [n for n in component_names(adapter) if n.startswith(stem)]
    if not hits:
        raise RuntimeError(f"no component named like {stem!r}")
    return hits[0]


async def _drive_and_measure(adapter: Any) -> dict[str, str]:
    roles = _removables_by_role(adapter)
    t12, t24 = roles["T12"], roles["T24"]
    knob_shaft = _one(adapter, "transgear-knob-shaft")
    fine_pinion = _one(adapter, "transgear-pinion")
    disc = _one(adapter, "rack-pinion")
    # The platen BODY exactly (platen-<n>), not a "platen-rack"/"platen-clip" sibling.
    platen = next((n for n in component_names(adapter)
                   if n.rsplit("-", 1)[0] == "platen"), "")
    if not platen:
        raise RuntimeError("no platen-<n> body component found")
    log(f"parts: crank T12={t12}, knob T24={t24}, shaft={knob_shaft}, "
        f"pinion={fine_pinion}, disc={disc}, platen={platen}")

    # --- baseline -----------------------------------------------------------
    parts = (t12, t24, knob_shaft, fine_pinion, disc)
    base_R = {n: _rot(adapter, n) for n in parts}
    base_platen_x = component_origin(adapter, platen)[0]

    # --- drive the crank ----------------------------------------------------
    # Author a temporary angle mate on the T12 Right-plane dihedral at rest + DRIVE_DEG
    # (the freed crank_spin driver is deferred/absent in the free model, so this is the
    # sole spin constraint); the gear + rack relations propagate it to the whole train.
    a = component_transform(adapter, t12)
    rest_dihedral = math.degrees(math.acos(max(-1.0, min(1.0, a[0]))))
    target = rest_dihedral + DRIVE_DEG
    # angle_driver returns a mate-result dict (raises on hard failure); do NOT wrap
    # it in check() -- that expects an AdapterResult with .is_success.
    await angle_driver(adapter, named_ref(f"Right Plane@{t12}", "PLANE"),
                       named_ref("Right Plane", "PLANE"), target,
                       label=f"KINEMATIC drive crank +{DRIVE_DEG:.0f}",
                       verify=None)
    log(f"drove crank to {target:.1f} deg dihedral")
    adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)

    # --- read the driven state ---------------------------------------------
    # Rotation MAGNITUDE of each part (axis-agnostic -- see _rot_angle_deg). All
    # locked cluster parts turn by the same angle; the gear mate gives T24 a fraction of
    # the crank; the platen translates in X.
    d_crank = _rot_angle_deg(_rot(adapter, t12), base_R[t12])
    d_t24 = _rot_angle_deg(_rot(adapter, t24), base_R[t24])
    # Signed Z rotations of the two sprockets (both spin about global Z): the
    # SENSE of the coupling, invisible to the magnitude compares below.
    z_crank = _rel_z_angle_deg(_rot(adapter, t12), base_R[t12])
    z_t24 = _rel_z_angle_deg(_rot(adapter, t24), base_R[t24])
    d_shaft = _rot_angle_deg(_rot(adapter, knob_shaft), base_R[knob_shaft])
    d_pinion = _rot_angle_deg(_rot(adapter, fine_pinion), base_R[fine_pinion])
    d_disc = _rot_angle_deg(_rot(adapter, disc), base_R[disc])
    d_platen = component_origin(adapter, platen)[0] - base_platen_x
    chain_ratio = d_t24 / d_crank if d_crank else 0.0
    log(f"crank spun {d_crank:.2f} deg (Z {z_crank:+.2f}) -> T24 {d_t24:.2f} "
        f"(Z {z_t24:+.2f}, ratio {chain_ratio:.3f}), "
        f"shaft {d_shaft:.2f}, pinion {d_pinion:.2f}, disc {d_disc:.2f} deg; "
        f"platen {d_platen:+.3f} mm")

    # --- assert the coupled motion (magnitudes) ----------------------------
    # (0) The temporary driver must actually hit DRIVE_DEG -- bound it on BOTH
    # sides, so an OVER-driven crank (a runaway/mis-solved mate) fails too, not
    # just an under-driven one (codex #189 round-5).
    if abs(d_crank - DRIVE_DEG) > CRANK_TOL:
        raise RuntimeError(
            f"crank moved {d_crank:.2f} deg, expected {DRIVE_DEG:.0f} "
            f"(+/-{CRANK_TOL:.0f}) -- drive did not seat at the target angle")
    # (1) Gear mate couples crank T12 -> knob T24 at the EXACT 12:24 = 0.500
    # tooth/pitch ratio (a roller chain enforces one link per tooth). Assert it
    # TIGHTLY -- a wrong ratio (e.g. the belt feature's 0.538 tip-cylinder
    # coupling, or a flipped/dropped mate) now FAILS instead of passing a broad
    # band (codex #189 round-5).
    if abs(chain_ratio - CHAIN_RATIO) > RATIO_TOL:
        raise RuntimeError(
            f"T24 turned {d_t24:.2f} deg for crank {d_crank:.2f} (ratio {chain_ratio:.3f}); "
            f"expected the 12:24 chain ratio {CHAIN_RATIO:.3f} +/-{RATIO_TOL:.2f} "
            "-- belt coupling wrong (tip-face 0.538 = the PulleyDiameters enforce "
            "failed, or a dropped belt mate?)")
    # (1b) SENSE: a chain turns both sprockets the SAME direction. An external
    # gear mate (or a flipped belt side) REVERSES -- the failure mode the
    # magnitude-only compares cannot see (codex #189 round-5 left it unasserted).
    if z_crank * z_t24 <= 0.0:
        raise RuntimeError(
            f"coupling sense REVERSED: crank Z {z_crank:+.2f} deg vs T24 Z "
            f"{z_t24:+.2f} deg -- a roller chain turns both sprockets the same "
            "way (gear-mate-style external mesh, or FlipSides on the belt?)")
    # (2) CORE :592 check -- the Lock-mated knob cluster (knob shaft + fine 24T pinion)
    # turns by the SAME angle as the driven T24, i.e. the whole feed train follows.
    for nm, dv in (("knob shaft", d_shaft), ("fine pinion", d_pinion)):
        if abs(dv - d_t24) > ANG_TOL:
            raise RuntimeError(
                f"{nm} turned {dv:.2f} deg, expected {d_t24:.2f} (Lock-mated to T24) "
                "-- the knob cluster did not follow the feed (codex #189 :592)")
    # (3) Rack-pinion feeds the platen off the knob axis at the NET through-train
    # travel; check against the MEASURED T24 rotation (exact downstream of T24).
    exp_platen = NET_RACK_TRAVEL_PER_KNOB_REV * d_t24 / 360.0
    if abs(abs(d_platen) - abs(exp_platen)) > LIN_TOL:
        raise RuntimeError(
            f"platen fed {d_platen:+.3f} mm, expected |{exp_platen:.3f}| "
            f"(NET {NET_RACK_TRAVEL_PER_KNOB_REV:.2f} x {d_t24:.2f}/360) -- rack broken")
    # (4) The visible 96T rack-pinion disc rolls on the platen rack: it turns
    # |platen| / (2*pi*PINION_PD_R) revolutions (codex #189). Proves it is no longer
    # a static gear while the rack slides past it.
    exp_disc = abs(d_platen) / (2.0 * math.pi * PINION_PD_R) * 360.0
    if abs(d_disc - exp_disc) > ANG_TOL:
        raise RuntimeError(
            f"rack-pinion disc turned {d_disc:.2f} deg, expected {exp_disc:.2f} "
            f"(|platen| {abs(d_platen):.3f} / 2*pi*{PINION_PD_R:.2f}) -- the visible "
            "disc did not follow the feed (codex #189)")
    _telemetry.success(
        f"crank->feed coupling OK: crank {d_crank:.1f} deg -> T24/shaft/pinion "
        f"{d_t24:.1f} deg (chain ratio {chain_ratio:.3f} = 12:24, same-sense) "
        f"-> platen {d_platen:+.3f} mm, disc {d_disc:.2f} deg")

    # --- chain-link travel (best-effort attempt; no native coupling) -------
    chain_moved = await _attempt_chain_advance(adapter, d_crank)

    _telemetry.info(
        "KINEMATIC PROBE -- crank drives the paper feed (rotation magnitudes):\n"
        f"  crank T12   {d_crank:6.2f} deg  (driver)\n"
        f"  knob  T24   {d_t24:6.2f} deg  (belt/chain, ratio {chain_ratio:.3f} = 12:24, same-sense)\n"
        f"  knob shaft  {d_shaft:6.2f} deg  (Lock to T24)\n"
        f"  fine pinion {d_pinion:6.2f} deg  (Lock to T24)\n"
        f"  96T disc    {d_disc:6.2f} deg  (rack-pinion, rolls on the platen rack)\n"
        f"  platen      {d_platen:+7.3f} mm  (rack, NET {NET_RACK_TRAVEL_PER_KNOB_REV:.2f}/rev)\n"
        f"  roller chain {'links advanced (Dynamic seed drive)' if chain_moved else 'static visual -- SW has no sprocket->link coupling'}")
    return {"crank_deg": f"{d_crank:.2f}", "platen_mm": f"{d_platen:.3f}",
            "chain_moved": str(chain_moved)}


async def build(adapter: Any) -> dict[str, str]:
    check("open paper-drive",
          await adapter.open_model(str(OUT_SLDASM / "paper-drive.SLDASM")))
    try:
        return await _drive_and_measure(adapter)
    finally:
        # Discard the driven (dirty) model WITHOUT a save prompt, even if a motion
        # assertion raised -- a failed probe must not leave paper-drive.SLDASM open,
        # dirty, or hang the COM session on a save modal (codex #189). Never saves.
        _discard_open_documents(adapter)


async def _attempt_chain_advance(adapter: Any, d_crank_deg: float) -> bool:
    """Best-effort: advance the Dynamic chain pattern by dragging its seed link one
    arc-step along the loop (the arc the crank swept, ``dTheta_rad * R_pitch_T12``) via
    ``move_component``, ForceRebuild3, and report whether a DIFFERENT link moved (the
    Dynamic linkage flowing the loop). SolidWorks has no sprocket->chain coupling
    (researched), so this is a scripted demonstration of the Dynamic pattern's own
    mobility -- failure is reported, not raised."""
    from solidworks_mcp.adapters.base import MoveComponentParameters
    try:
        links = sorted(n for n in component_names(adapter)
                       if n.startswith(("chain-inner-link", "chain-outer-link")))
        if len(links) < 3:
            return False
        seed = links[0]                       # the pattern's seed link
        probe = links[len(links) // 2]        # a link far around the loop
        before = component_origin(adapter, probe)
        arc = math.radians(abs(d_crank_deg)) * PITCH_R_T12   # chain surface travel
        # Delta along the loop tangent at the seed's station (0 -> arc).
        x0, y0, _ = loop_point_tangent(0.0, dx=KNOB_SHAFT_XY[0], dy=KNOB_SHAFT_XY[1],
                                       mirror_x=True)
        x1, y1, _ = loop_point_tangent(arc, dx=KNOB_SHAFT_XY[0], dy=KNOB_SHAFT_XY[1],
                                       mirror_x=True)
        await adapter.move_component(MoveComponentParameters(
            name=seed, position=[x1 - x0, y1 - y0, 0.0], relative=True))
        adapter._attempt(lambda: adapter.currentModel.ForceRebuild3(False), default=None)
        after = component_origin(adapter, probe)
        moved = math.hypot(after[0] - before[0], after[1] - before[1])
        log(f"chain advance: dragged seed +{arc:.1f} mm arc -> a link {arc:.0f}mm away "
            f"moved {moved:.2f} mm")
        return moved > 0.5
    except Exception as exc:  # noqa: BLE001 -- best-effort, never fail the probe
        log(f"chain advance attempt failed (SW chain-coupling limitation): {exc}")
        return False


if __name__ == "__main__":
    sys.exit(run_build(build))

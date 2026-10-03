r"""Kinematic probe: prove the crank drives the paper feed (codex #189 kinematic test).

Turning the crank T12 sprocket must propagate through the WHOLE six-gear feed
train (paper-drive rework E8 -- every stage a real mate):

    T12 (crank) --Belt/Chain 12:24 teeth--> T24 (knob wheel)
      --mated--> drive collar --Lock--> knob shaft (its integral 12T gear)
      --GEAR 12:120--> 120T reducer disc --Lock--> 12T feed pinion
      --rack-pinion (pi * 10.16 / rev)--> platen (the paper feed)

and the roller chain rides both sprockets. This probe opens the saved default-`free`
paper-drive model, DRIVES the crank by a known angle (authors a temporary angle mate
on the T12 Right-plane dihedral, then ForceRebuild3), and asserts each downstream
component moved by the coupled amount. Every rotating part of the train -- both
sprockets, the drive collar, the knob shaft, the disc and the feed pinion -- spins
about the global Z axis, so their SIGNED Z rotations are compared -- ratio AND sense:

  * the Belt/Chain feature (EngageBelt, PulleyDiameters forced to the per-tooth
    values N * pitch / pi -- the picked tip faces would couple at the #25 OD ratio
    0.529) drives T24
    at the EXACT 12:24 = 0.500 reduction off the crank, asserted tightly,
  * T24 turns the SAME direction as T12 (signed Z angles) -- a chain couples both
    sprockets the same way; an external gear mate would REVERSE,
  * the drive collar and the knob shaft (with its integral 12T) turn by the SAME
    signed Z angle as T24 (the collar is mated to T24, the shaft Lock-mated to the
    collar -- the whole feed train follows; codex #189 :592),
  * the GEAR mate turns the disc at 12:120 of the knob shaft spin, reversed (external
    mesh; ``GEAR_SENSE`` pins the authored alignment),
  * the feed pinion turns WITH the disc (Lock, same axis -- signed compare),
  * the platen translates by ``pi * FEED_PD * (dTheta_feed / 360)``, checked
    SIGNED against the MEASURED feed-pinion rotation (``FEED_SIGN`` states the
    physical tooth-contact sense -- flip the MATE, not the constant), and
    end-to-end the feed must equal ``NET_RACK_TRAVEL_PER_CRANK_REV`` per crank
    revolution, SIGNED through the whole train.

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

# Coupled ratios (from the paper-drive build): chain T12:T24 = 12:24, gear
# 12:120, rack-pinion pi*FEED_PD per feed-pinion revolution.
from build_paper_drive_assembly import (
    CHAIN_CRANK_CENTRE,
    DISC_TEETH,
    FEED_PD,
    KNOB_SHAFT_XY,
    NET_RACK_TRAVEL_PER_CRANK_REV,
    SPARE_GEAR_POS,
    THIRD_TEETH,
)

DRIVE_DEG = 30.0    # crank test rotation
CRANK_TOL = 2.0     # deg: the temporary driver must hit DRIVE_DEG on BOTH sides
# The crank T12 -> knob T24 tie is the Belt/Chain feature with PulleyDiameters
# FORCED to the chain's per-tooth values (N * pitch / pi, the exact 12:24 tooth
# law) -- the picked tooth-tip faces would otherwise couple at the OD ratio.
# The probe asserts the true 0.500 TIGHTLY, and the same-sense rotation a
# chain enforces.
from paper_drive_geom import CHAIN_RATIO  # noqa: E402  (12:24 tooth ratio, exact)

GEAR_RATIO = THIRD_TEETH / DISC_TEETH  # 12:120 = 0.1 (the reduction gear mate)
# Chain-stage ratio tolerance, derived from what the probe measures. The ratio
# is d_t24 / d_crank, two axis-angle magnitudes (acos((trace - 1) / 2), well
# conditioned at 15 and 30 deg) read from Transform2 doubles after ONE solve of
# a LINEAR belt coupling -- no sampling, no iteration in the probe, so the only
# error is the solved pose. Live it read T12 +30.00 -> T24 +15.00 deg, ratio
# +0.5000 (memory/belt-chain-feature-com-binding.md): each angle within the
# 2-dp readback's +/-0.005 deg. Budget 4x that per reading, READ_SLACK_DEG;
# worst case the two readings err oppositely on the smallest crank the
# CRANK_TOL gate admits, so |ratio - 0.5| <= READ_SLACK_DEG * (1 + CHAIN_RATIO)
# / (DRIVE_DEG - CRANK_TOL) = 0.02 * 1.5 / 28 = 0.00107. That is ~21x the live
# error bound (5e-5) yet under HALF the nearest wrong coupling's offset: the
# #25 pitch-circle ratio p/sin(180/N) (0.5043, +0.0043 -- what typing the
# pitch diameters instead of N*p/pi would give) and far under the OD/tip ratio
# (0.5286, +0.0286 -- the old 0.03 band accepted it).
READ_SLACK_DEG = 0.02  # deg per sprocket angle reading (4x the live 2-dp bound)
CHAIN_RATIO_TOL = READ_SLACK_DEG * (1.0 + CHAIN_RATIO) / (DRIVE_DEG - CRANK_TOL)
ANG_TOL = 1.2  # deg: the collar and knob shaft turn with T24 (near-exact)
LIN_TOL = 0.05      # mm: the 30-deg drive feeds only ~0.133 mm through the 1:20
# net reduction, so the linear tolerance is tight enough that a dropped rack
# mate (0 feed) or a wrong-stage ratio cannot hide inside it
# SIGNED senses (codex #189: magnitude-only checks would pass a mate that
# solved to the reversed alignment and fed the paper BACKWARD). The gear and
# rack-pinion mates store their alignment in the authored model, so the sense
# is deterministic per build script; these constants pin it (precedent:
# 29f1282). They live HERE (not in the build script) so a calibration flip
# re-runs only verify:kinematics, not the assembly build.
GEAR_SENSE = -1.0  # sign of (disc Z) / (knob shaft Z): external 12:120 mesh
# FEED_SIGN is PINNED by the physical tooth contact observed in live SW
# (2026-07-07 drag test: the original platen-axis-referenced mate fed the
# paper BACKWARD at this constant's old -1 value, every magnitude passing).
# Do NOT re-calibrate this constant to whatever the model does -- it states
# the physics; flip the MATE (build_paper_drive_assembly, rack_pinion_mate
# flip=) until this assert holds.
FEED_SIGN = +1.0    # sign of (platen dX) / (feed-pinion signed-Z deg)


def measured_chain_ratio(d_t24: float, d_crank: float) -> float:
    """Crank T12 -> knob T24 ratio of two measured spins (0 for an unmoved crank)."""
    return d_t24 / d_crank if d_crank else 0.0


def check_chain_ratio(d_t24: float, d_crank: float) -> None:
    """Raise unless ``d_t24 / d_crank`` is the EXACT 12:24 tooth ratio within
    ``CHAIN_RATIO_TOL``.

    A roller chain enforces one link per tooth, so any other ratio -- the OD/tip
    coupling a face-member belt bakes in, the #25 pitch-circle ratio, or a
    dropped mate (T24 still) -- is a broken coupling (codex #189 round-5).
    """
    chain_ratio = measured_chain_ratio(d_t24, d_crank)
    if abs(chain_ratio - CHAIN_RATIO) > CHAIN_RATIO_TOL:
        raise RuntimeError(
            f"T24 turned {d_t24:.3f} deg for crank {d_crank:.3f} (ratio "
            f"{chain_ratio:.4f}); expected the 12:24 chain ratio {CHAIN_RATIO:.4f} "
            f"+/-{CHAIN_RATIO_TOL:.4f} -- belt coupling wrong (tip/OD or pitch-"
            "circle diameters instead of N*p/pi, or a dropped belt mate?)"
        )


def _rot(adapter: Any, name: str) -> list[float]:
    """A component's rotation as a row-major 3x3 (the first 9 Transform2 entries)."""
    return component_transform(adapter, name)[:9]


def _rot_angle_deg(after: list[float], before: list[float]) -> float:
    """Magnitude (deg) of the relative rotation ``after @ before^T`` -- the angle of
    its axis-angle form, via ``acos((trace - 1) / 2)`` (valid 0..180 deg).

    Axis-AGNOSTIC on purpose: it reads the crank's driven spin without assuming
    which axis the temporary driver turned it about, so an off-axis or runaway
    solve still reads its true magnitude against DRIVE_DEG and the chain ratio."""
    bt = [before[0], before[3], before[6],
          before[1], before[4], before[7],
          before[2], before[5], before[8]]          # before^T
    m = [sum(after[r * 3 + k] * bt[k * 3 + c] for k in range(3))
         for r in range(3) for c in range(3)]        # after @ before^T
    trace = m[0] + m[4] + m[8]
    return math.degrees(math.acos(max(-1.0, min(1.0, (trace - 1.0) / 2.0))))


def _rel_z_angle_deg(after: list[float], before: list[float]) -> float:
    """SIGNED rotation about Z (deg) between two ``Transform2`` rotations.

    Every rotating part of the feed train (sprockets, drive collar, knob shaft,
    disc, feed pinion) spins about global Z, so the sign is meaningful.
    ``Transform2.ArrayData`` stores the rotation with the part's axes as its
    ROWS (R = M^T for the column-vector matrix M), so the global spin
    ``M_after @ M_before^T`` is ``after^T @ before``.  The old
    ``after @ before^T`` read ``M_after^T @ M_before``, the spin in the
    part's OWN frame: the global spin's transpose for a part inserted with
    its Z along +Z, its reverse for one inserted Ry180 -- the Ry180 feed
    sleeve Lock-mated to the identity disc read +1.50 against the disc's
    -1.50 (run 20261001T051043622Z).  This returns ``before^T @ after``, the
    global spin's transpose for EVERY insertion frame, so a part with its Z
    along +Z reads exactly what it did before (the sign GEAR_SENSE and
    FEED_SIGN were calibrated against).

    Z-rotation by theta has ``m = [[c,-s,.],[s,c,.],...]``, hence
    ``atan2(m[1][0] - m[0][1], m[0][0] + m[1][1]) = theta``."""
    bt = [before[0], before[3], before[6],
          before[1], before[4], before[7],
          before[2], before[5], before[8]]          # before^T
    m = [sum(bt[r * 3 + k] * after[k * 3 + c] for k in range(3))
         for r in range(3) for c in range(3)]        # before^T @ after
    return math.degrees(math.atan2(m[3] - m[1], m[0] + m[4]))


def _origin_xy(adapter: Any, name: str) -> tuple[float, float]:
    o = component_origin(adapter, name)
    return (o[0], o[1])


def _removables_by_role(adapter: Any) -> dict[str, str]:
    """Map T12/T24/T18 -> the instance name, matched by |origin - known centre|.
    The three ``transgear-removable`` instances share a stem, so identify them by
    position: T12 at the crank centre, T24 at the knob shaft, T18 the loose spare."""
    known = {
        # Machine-handed anchors (#151): the T12 rides the crank at machine -X
        # (_chain's CHAIN_CRANK_CENTRE is its own pre-mirror +X anchor).
        "T12": (-CHAIN_CRANK_CENTRE[0], CHAIN_CRANK_CENTRE[1]),
        "T24": KNOB_SHAFT_XY,
        "T18": SPARE_GEAR_POS[:2],
    }
    insts = [n for n in component_names(adapter) if n.startswith("transgear-removable")]
    out: dict[str, str] = {}
    for role, (kx, ky) in known.items():
        best, bestd = None, 1e9
        for n in insts:
            x, y = _origin_xy(adapter, n)
            d = math.hypot(x - kx, y - ky)
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
    collar = _one(adapter, "transgear-drive-collar")
    knob_shaft = _one(adapter, "transgear-knob-shaft")
    feed_pinion = _one(adapter, "transgear-feed-pinion")
    disc = _one(adapter, "rack-pinion")
    # The platen BODY exactly (platen-<n>), not a "platen-rack"/"platen-clip" sibling.
    platen = next((n for n in component_names(adapter)
                   if n.rsplit("-", 1)[0] == "platen"), "")
    if not platen:
        raise RuntimeError("no platen-<n> body component found")
    log(
        f"parts: crank T12={t12}, knob T24={t24}, collar={collar}, "
        f"shaft={knob_shaft}, disc={disc}, feed={feed_pinion}, platen={platen}"
    )

    # --- baseline -----------------------------------------------------------
    parts = (t12, t24, collar, knob_shaft, disc, feed_pinion)
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
    # Rotation MAGNITUDE of the crank and T24 (axis-agnostic -- see
    # _rot_angle_deg) for the driver gate and the chain ratio; the gear mate
    # reduces into the disc; the platen translates in X.
    d_crank = _rot_angle_deg(_rot(adapter, t12), base_R[t12])
    d_t24 = _rot_angle_deg(_rot(adapter, t24), base_R[t24])
    # Signed Z rotations of the two sprockets (both spin about global Z): the
    # SENSE of the coupling, invisible to the magnitude compares.
    z_crank = _rel_z_angle_deg(_rot(adapter, t12), base_R[t12])
    z_t24 = _rel_z_angle_deg(_rot(adapter, t24), base_R[t24])
    # The collar, the knob shaft (integral 12T), the disc and the feed pinion
    # also spin about global Z -> their SIGNED rotations are meaningful (the
    # senses the collar, gear and rack-pinion mates enforce), like the sprockets'.
    z_collar = _rel_z_angle_deg(_rot(adapter, collar), base_R[collar])
    z_shaft = _rel_z_angle_deg(_rot(adapter, knob_shaft), base_R[knob_shaft])
    z_disc = _rel_z_angle_deg(_rot(adapter, disc), base_R[disc])
    z_feed = _rel_z_angle_deg(_rot(adapter, feed_pinion), base_R[feed_pinion])
    d_platen = component_origin(adapter, platen)[0] - base_platen_x
    chain_ratio = measured_chain_ratio(d_t24, d_crank)
    log(
        f"crank spun {d_crank:.2f} deg (Z {z_crank:+.2f}) -> T24 {d_t24:.2f} "
        f"(Z {z_t24:+.2f}, ratio {chain_ratio:.4f}), "
        f"collar Z {z_collar:+.2f}, shaft Z {z_shaft:+.2f}, disc Z {z_disc:+.2f}, "
        f"feed Z {z_feed:+.2f} deg; platen {d_platen:+.3f} mm"
    )

    # --- assert the coupled motion (magnitudes) ----------------------------
    # (0) The temporary driver must actually hit DRIVE_DEG -- bound it on BOTH
    # sides, so an OVER-driven crank (a runaway/mis-solved mate) fails too, not
    # just an under-driven one (codex #189 round-5).
    if abs(d_crank - DRIVE_DEG) > CRANK_TOL:
        raise RuntimeError(
            f"crank moved {d_crank:.2f} deg, expected {DRIVE_DEG:.0f} "
            f"(+/-{CRANK_TOL:.0f}) -- drive did not seat at the target angle")
    # (1) The Belt/Chain feature couples crank T12 -> knob T24 at the EXACT
    # 12:24 = 0.500 tooth ratio (a roller chain enforces one link per tooth),
    # asserted to CHAIN_RATIO_TOL -- see check_chain_ratio.
    check_chain_ratio(d_t24, d_crank)
    # (1b) SENSE: a chain turns both sprockets the SAME direction. An external
    # gear mate (or a flipped belt side) REVERSES -- the failure mode the
    # magnitude-only compares cannot see (codex #189 round-5 left it unasserted).
    if z_crank * z_t24 <= 0.0:
        raise RuntimeError(
            f"coupling sense REVERSED: crank Z {z_crank:+.2f} deg vs T24 Z "
            f"{z_t24:+.2f} deg -- a roller chain turns both sprockets the same "
            "way (gear-mate-style external mesh, or FlipSides on the belt?)")
    # (2) CORE :592 check -- the drive collar (mated to T24) and the knob shaft
    # (Lock-mated to the collar, integral 12T) turn by the SAME signed Z angle
    # as the driven T24: the knob stack follows, in the same sense.
    for nm, zv in (("drive collar", z_collar), ("knob shaft", z_shaft)):
        if abs(zv - z_t24) > ANG_TOL:
            raise RuntimeError(
                f"{nm} turned Z {zv:+.2f} deg, expected {z_t24:+.2f} (T24) "
                "-- the knob stack did not follow the feed (codex #189 :592)"
            )
    # (3) The GEAR mate reduces the cluster spin 12:120 into the disc, SIGNED
    # (an external mesh reverses; GEAR_SENSE pins the authored alignment). The
    # expected disc angle is small (1.5 deg for a 30-deg crank), so the
    # tolerance is proportionally tight -- a dropped/mis-ratioed mate fails.
    exp_disc = GEAR_SENSE * GEAR_RATIO * z_shaft
    if abs(z_disc - exp_disc) > 0.25:
        raise RuntimeError(
            f"disc turned Z {z_disc:+.2f} deg, expected {exp_disc:+.2f} "
            f"(GEAR_SENSE {GEAR_SENSE:+.0f} x {THIRD_TEETH}:{DISC_TEETH} x knob "
            f"shaft Z {z_shaft:+.2f}) -- gear mate broken, mis-ratioed or flipped"
        )
    # (4) The feed pinion is Lock-mated coaxially to the disc: identical SIGNED
    # spin (both on the stud's Z axis).
    if abs(z_feed - z_disc) > 0.2:
        raise RuntimeError(
            f"feed pinion turned Z {z_feed:+.2f} deg, disc {z_disc:+.2f} "
            "-- the disc/feed-pinion Lock did not hold")
    # (5) The rack-pinion mate feeds the platen at the feed pinion's own pitch
    # circumference, SIGNED against the MEASURED pinion rotation (exact
    # downstream). A reversed mate alignment feeds the paper BACKWARD at the
    # right magnitude -- abs() would pass it (codex #189).
    exp_platen = FEED_SIGN * math.pi * FEED_PD * z_feed / 360.0
    if abs(d_platen - exp_platen) > LIN_TOL:
        raise RuntimeError(
            f"platen fed {d_platen:+.3f} mm, expected {exp_platen:+.3f} "
            f"(FEED_SIGN {FEED_SIGN:+.0f} x pi*{FEED_PD:.2f} x feed Z "
            f"{z_feed:+.2f}/360) -- rack broken or feed direction REVERSED")
    # (6) End-to-end cross-check: the whole train must feed at the documented
    # NET law (1.596 mm per crank rev with T12/T24 mounted), SIGNED through the
    # full chain (same-sense chain -> reversing 12:120 mesh -> pinned rack
    # sense): d_platen = FEED_SIGN * GEAR_SENSE * NET * z_crank / 360. Any
    # single reversal anywhere in the train flips the sign and fails HERE even
    # if a pairwise constant above were miscalibrated to match it (2026-07-07
    # field report: the rack mate fed backward while every magnitude passed).
    exp_net = (FEED_SIGN * GEAR_SENSE
               * NET_RACK_TRAVEL_PER_CRANK_REV * z_crank / 360.0)
    if abs(d_platen - exp_net) > LIN_TOL:
        raise RuntimeError(
            f"net feed {d_platen:+.3f} mm != {exp_net:+.3f} "
            f"(FEED_SIGN {FEED_SIGN:+.0f} x GEAR_SENSE {GEAR_SENSE:+.0f} x NET "
            f"{NET_RACK_TRAVEL_PER_CRANK_REV:.3f}/crank-rev x crank Z {z_crank:+.1f}/360)")
    _telemetry.success(
        f"crank->feed coupling OK: crank {d_crank:.1f} deg -> T24/collar/shaft "
        f"{d_t24:.1f} deg (chain ratio {chain_ratio:.3f} = 12:24, same-sense) "
        f"-> disc/feed Z {z_disc:+.2f} deg (12:120) -> platen {d_platen:+.3f} mm")

    # --- chain-link travel (best-effort attempt; no native coupling) -------
    chain_moved = await _attempt_chain_advance(adapter, d_crank)

    _telemetry.info(
        "KINEMATIC PROBE -- crank drives the paper feed:\n"
        f"  crank T12   {d_crank:6.2f} deg  (driver)\n"
        f"  knob  T24   {d_t24:6.2f} deg  (belt/chain, ratio {chain_ratio:.3f} = 12:24, same-sense)\n"
        f"  collar      {z_collar:+6.2f} deg  (mated to T24, signed)\n"
        f"  knob shaft  {z_shaft:+6.2f} deg  (Lock to collar, integral 12T, signed)\n"
        f"  120T disc   {z_disc:+6.2f} deg  (gear mate 12:120, signed)\n"
        f"  feed pinion {z_feed:+6.2f} deg  (Lock to disc, signed)\n"
        f"  platen      {d_platen:+7.3f} mm  (rack-pinion, pi*{FEED_PD:.2f}/rev;"
        f" NET {NET_RACK_TRAVEL_PER_CRANK_REV:.3f}/crank-rev)\n"
        f"  roller chain {'links advanced (Dynamic seed drive)' if chain_moved else 'static visual -- SW has no sprocket->link coupling'}")
    return {"crank_deg": f"{d_crank:.2f}", "platen_mm": f"{d_platen:.3f}",
            "chain_moved": str(chain_moved)}


async def build(adapter: Any) -> dict[str, str]:
    check("open paper-drive",
          await adapter.open_model(str(OUT_SLDASM / "paper-drive.SLDASM")))
    try:
        result = await _drive_and_measure(adapter)
        # Standalone-only (the verify:kinematics gate calls _drive_and_measure
        # directly): render the DRIVEN pose for a visual proof of the moved
        # train -- crank +30 deg, everything downstream displaced. The model
        # still discards unsaved below; only PNGs are written.
        from _common import OUT_PNG
        png_dir = OUT_PNG / "paper-drive"
        png_dir.mkdir(parents=True, exist_ok=True)
        for view in ("front", "isometric"):
            img = (png_dir / f"paper-drive_driven_{view}.png").resolve()
            check(f"export driven {view}", await adapter.export_image({
                "file_path": str(img), "format_type": "png",
                "width": 1600, "height": 1000, "view_orientation": view}))
            result[f"driven_{view}"] = str(img)
        return result
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
        # Chain surface travel on the crank T12 pitch circle (_chain reads the
        # #25 pitch radius from transgear_removable_spec).
        arc = math.radians(abs(d_crank_deg)) * PITCH_R_T12
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

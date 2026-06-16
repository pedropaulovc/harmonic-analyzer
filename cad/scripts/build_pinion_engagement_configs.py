r"""The ``pinion_engaged`` configuration of the drive train (plan F4, the second
engagement enum).

``build_engagement_configs.py`` added ``cone_disengaged`` (the 21 gear meshes cut,
cone train decoupled) and ``build_operating_config.py`` added ``operating`` (the
crank park driver freed). This adds the alignment-pinion engage state, the
clutchable mechanism the book shows on ch.25 (p.66): the 42T alignment-pinion
drum swings on its two straps into mesh with the cylinder-gear set to ZERO all
channels. The drive-train build already left this as a designed-in hook -- the
swing group is a rigid body grounded by ONE revolute about the pivot shaft plus a
suppressible PARK DRIVER pinning it at the disengaged rest pose ("pinion swing
park driver", ``build_drive_train_assembly.py`` line ~776, whose comment says
"suppress the driver (motion study / a pinion_engaged config) to articulate the
engage swing"). So this state is just that suppression, config-scoped:

    Default (= disengaged)   pinion swing driver active -> the drum is parked with
                             the book's 2 mm tip gap, 0 DOF, fully defined,
                             bit-exact: the saved/rendered/photo-gated pose.
                             UNTOUCHED here.
    pinion_engaged           pinion swing driver suppressed -> exactly ONE free
                             DOF: the swing about the torque shaft. Hand-drag (or
                             a Basic Motion motor on the turning handle) swings the
                             drum into mesh with the cylinder train; the book's
                             zeroing articulation. The tooth coupling itself is the
                             "approximate engaged mesh" -- realised by swinging in
                             this config, and reproduced numerically in
                             truth_model.py (compute-don't-simulate, see
                             docs/motion-policy.md), not by a redundant gear mate
                             that would over-define the already cone-driven
                             cylinders.

Why this is the clean place for it (same reasoning as build_operating_config):
drive-train.SLDASM grounds ONE base internally, so suppressing the pinion swing
driver frees ONLY the swing group -- nothing structural drifts. The swing group is
the rigid trio {alignment-pinion, the two pinion-brackets}; the pivot blocks,
shaft, lift rod, lever and handle stay grounded (the handle coincides at rest, its
float+lock is deferred). EXACTLY those three may go under-defined; anything else
leaking in is a bug -- that is what ``_verify_pinion_engaged`` asserts.

The pinion swing driver is the single-real-part DISTANCE/ANGLE mate on
``alignment-pinion`` that ``spin_driver`` created (SW auto-named the mate, so it is
found by its entities, not its label -- exactly as build_operating_config's crank
driver suppressor does). It is suppressed CONFIG-SCOPED (swSpecifyConfiguration),
so Default keeps it live and renders exactly as before.

Idempotent: a re-run (or a build_all that opens an already-configured doc) skips
the create + suppress and just re-verifies both states.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_engagement_configs.py
"""

from __future__ import annotations

import sys
from typing import Any

from _common import (
    OUT_SLDASM,
    assert_components_fully_defined,
    assert_model_healthy,
    check,
    check_no_interference,
    log,
    run_build,
)
from build_engagement_configs import _save_assembly_in_place
from build_mobility_probe import _component_status, _under
from build_motion_study import ANGLE, DISTANCE, _family, _iter_mates, _lone_real
from build_operating_config import _verify_rest

ASM_NAME = "drive-train"
REST = "Default"  # the model's default config IS the disengaged 0-DOF pose
PINION_ENGAGED = "pinion_engaged"  # swing driver freed -> the engage DOF is live

# The pinion swing park driver: the single-real-part DISTANCE/ANGLE mate whose
# lone real part is the alignment-pinion (spin_driver pins the pinion Axis1's
# in-plane coord to a root plane). Found by entities -- the mate carries SW's auto
# name, not the label. The keyed-chain locks are LOCK (two real parts) and the
# swing axial driver is lone-``pinion-bracket``, so neither collides.
PINION_DRIVER_FAMILY = "alignment-pinion"

# Suppressing the pinion swing driver frees the rigid swing group's one DOF
# (the swing about the torque shaft). EXACTLY these families may go under-defined;
# anything structural leaking in is a bug. The trio is the alignment-pinion drum
# plus its two straps (the front bracket carries the revolute; the back bracket +
# pinion are locked to it, so all three lose definition together).
SWING_FAMILIES = frozenset({"alignment-pinion", "pinion-bracket"})
EXPECTED_FREED = 3  # alignment-pinion-1 + pinion-bracket-1 + pinion-bracket-2


def _find_pinion_driver(adapter: Any) -> str:
    """Name of the lone single-``alignment-pinion`` DISTANCE/ANGLE mate (driver).

    Walks the open drive-train.SLDASM mate group (NOT flexible here -> fast) and
    matches the same signature build_operating_config uses for the crank driver: a
    DISTANCE or ANGLE mate referencing exactly one real part whose family is the
    alignment-pinion. There must be exactly one -- the keyed-chain lock mates are
    LOCK (two real parts) and the swing axial driver is lone-``pinion-bracket``, so
    neither collides.
    """
    hits = []
    for _f, _m, name, mtype, parts, _v in _iter_mates(
            adapter, adapter.currentModel, read_values=False):
        if mtype not in (DISTANCE, ANGLE):
            continue
        lone = _lone_real(parts, ASM_NAME)
        if lone is not None and _family(lone) == PINION_DRIVER_FAMILY:
            hits.append(name)
    if len(hits) != 1:
        raise RuntimeError(
            f"expected exactly 1 pinion swing driver (single-{PINION_DRIVER_FAMILY} "
            f"DISTANCE/ANGLE mate), found {hits}")
    log(f"pinion swing park driver mate = {hits[0]!r}")
    return hits[0]


async def _verify_pinion_engaged(adapter: Any) -> None:
    """pinion_engaged: the freed set is EXACTLY the swing group (one swing DOF).

    Suppressing the swing driver frees the rigid {alignment-pinion, both brackets}
    trio so it can swing the drum into mesh. The invariant: ONLY swing-group
    families go free (no structural leak), the pinion drum itself is among them
    (proving the driver was actually suppressed), and the pose is still
    interference-free. (This is a free DOF on purpose -- the config exists to be
    hand-dragged / motor-driven into the engaged mesh -- so it is NOT a 0-DOF pose,
    by design.)
    """
    check(f"activate {PINION_ENGAGED}", await adapter.set_active_configuration(
        PINION_ENGAGED))
    log(f"--- verifying configuration {PINION_ENGAGED} (swing DOF live) ---")
    freed = sorted(_under(_component_status(adapter)))
    log(f"{PINION_ENGAGED}: {len(freed)} under-defined (swing-group) components")

    leaked = [n for n in freed if _family(n) not in SWING_FAMILIES]
    if leaked:
        raise RuntimeError(
            f"{PINION_ENGAGED}: structural components leaked into the freed set "
            f"(only the pinion swing group may go free): {leaked}")
    if not any(_family(n) == "alignment-pinion" for n in freed):
        raise RuntimeError(
            f"{PINION_ENGAGED}: the alignment-pinion is not free -- the swing "
            f"driver was not actually suppressed in this config: {freed}")
    if len(freed) != EXPECTED_FREED:
        raise RuntimeError(
            f"{PINION_ENGAGED}: expected exactly {EXPECTED_FREED} swing-group "
            f"members free, got {len(freed)}: {freed}")
    log(f"{PINION_ENGAGED}: freed set is exactly the {EXPECTED_FREED}-member swing "
        f"group -- the drum swings into the cylinder mesh here (book ch.25 zeroing)")
    check_no_interference(adapter)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateConfigurationParameters,
        SuppressMateParameters,
    )

    path = str(OUT_SLDASM / f"{ASM_NAME}.SLDASM")
    check(f"open {ASM_NAME}", await adapter.open_model(path))

    # rest stays the Default config; assert it is the clean 0-DOF baseline first
    # (also leaves Default active so the driver lookup sees the live mate).
    await _verify_rest(adapter)
    driver = _find_pinion_driver(adapter)

    # Idempotent: skip create + suppress if pinion_engaged already exists.
    configs = check("list configurations", await adapter.list_configurations())
    if PINION_ENGAGED in configs:
        log(f"{PINION_ENGAGED} already present ({configs}) -- re-verifying only")
    else:
        # pinion_engaged: derived from rest, then config-scoped-suppress the pinion
        # swing driver so the engage articulation is free. AddConfiguration2
        # activates the new config, so the suppress readback sees it active with no
        # switch.
        check(f"create {PINION_ENGAGED}", await adapter.create_configuration(
            CreateConfigurationParameters(
                name=PINION_ENGAGED, parent=REST,
                comment="pinion swing driver suppressed: the alignment-pinion drum "
                "swings into the cylinder-gear mesh to zero the channels (ch.25)",
                description="Alignment pinion engageable: the swing DOF is free "
                "(hand-drag / Basic Motion motor on the turning handle).")))
        check(f"suppress {driver}@{PINION_ENGAGED}", await adapter.suppress_mate(
            SuppressMateParameters(
                name=driver, suppress=True, configuration=PINION_ENGAGED)))

    await _verify_pinion_engaged(adapter)

    # Back to rest and re-verify: the pinion swing driver must be LIVE again here
    # (the suppression was scoped to pinion_engaged only) and the pose unchanged.
    await _verify_rest(adapter)
    live = check("list mates (rest)", await adapter.list_mates())
    if any(m["name"] == driver and m.get("suppressed") for m in live):
        raise RuntimeError(
            f"rest leaked suppression from {PINION_ENGAGED}: {driver} is suppressed "
            f"in Default -- the rest pose is no longer deterministic")
    log(f"rest: pinion swing driver {driver!r} live (suppression stayed scoped)")

    assert_model_healthy(adapter, label=ASM_NAME, deep=True)
    _save_assembly_in_place(adapter)
    return {"assembly": str(OUT_SLDASM / f"{ASM_NAME}.SLDASM"),
            "configs": f"{REST},{PINION_ENGAGED}"}


if __name__ == "__main__":
    sys.exit(run_build(build))

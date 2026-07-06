r"""Reproduction script: paper-drive subassembly (book ch. 22-23, 25).

The orthogonal time-base of the plotter: the platen carries the recording paper
across the pen as the operator turns the crank, driven through the translational
gearing, in machine coordinates (assembly origin = base origin; base top
y = 50.8; the output side is -Z). 21 placed components + the roller drive chain,
built as a native connected-linkage chain component pattern along the loop.

Operational kinematics (default `free` build): the crank-end T12 sprocket spin is
a FREE operational DOF -- drag it and the whole feed train follows. The coupling
is authored as SolidWorks mates, NOT re-posed geometry (the ch30 rest pose below
is preserved exactly, faithful to the plates): a native **Belt/Chain feature**
(``adapter.insert_belt_chain``, EngageBelt) couples T12 <-> T24 at the 12:24 chain
ratio, and a single **rack-pinion mate** feeds the platen off the knob (T24) axis
at the NET through-train travel (fine-pinion 24T -> disc 96T -> rack, see
``NET_RACK_TRAVEL_PER_KNOB_REV``). The intermediate transgear gears stay in their
faithful rest pose; the fine-pinion/disc coupling is the modeled ENGAGED operation
expressed kinematically ACROSS the documented 13.1 rest gap (the single latch arm
cannot serve both the 66.05 rest and 51.0 engaged centre distances -- DIMENSIONS.md
Appendix C #8's open kinematic riddle -- so the engage is coupled, not geometrically
meshed). `locked` authors the crank-spin park engaged for a 0-DOF snapshot. Mode:
cad/config/machine/build_lock.yaml (``paper_drive``).

* Support rails (front of the columns, centres z -133.9): platen top rail
  (y 440) + bottom rail (y 334), each clamped by a column-clamp pair at
  x +-197.
* Platen group: platen (prismatic slider along X, the paper feed) face-flush on
  the rails, platen-rack on its back (teeth down, meshing the rack pinion with
  0.3 backlash and tooth-on-gap phasing), two platen-clips on the paper face,
  platen-paper riding as a rigid sheet.
* Transgear group (ch. 23 topology, M6.8): pinion-bar, transgear-stub carrying
  rack-pinion (96T disc) + latch big hub; the latch (c2c 66.05, ch30 rest
  state) carries the knob shaft with the mounted T24 removable CHAIN-WRAPPED at
  the drive-train chain plane (the roller chain rides the removable's m2 teeth --
  that is how gear swaps change the platen ratio), the fine 24T DP30
  transgear-pinion near the front, and the roller chain looping both removables.
* Fasteners (M6.10): four fillister screws holding the platen clips (into the
  platen's blind sockets), four pinch screws in the platen-rail column clamps
  (backed out).
* Spare transgear-removable (T18 chain wheel) stored loose on the base top
  (y 50.8): the swap gear for changing the platen ratio (ch. 23). A spare for
  THIS subsystem -- so it lives here (flat sibling of the mounted T24, exactly as
  the book's single output group held both) rather than floating at the top level
  where its leaf name would collide with the T12/T24 instances nested in the
  drive-train / this sub.

Cross-subassembly fits (checked at the top level): the column-clamps ride the
O25.4 columns (frame.SLDASM); the roller chain spans this sub's knob shaft and
the drive-train crankshaft (drive-train.SLDASM) -- both share the z -155 chain
plane.

Default-state notes / documented simplifications (Appendix C):
* The transgear is modeled in the ch30 REST (disengaged) state: the latch parks
  the knob shaft at c2c 66.05 from the stud, so the fine 24T pinion sits 13.1
  clear of the disc tips. The mounted removables are CHAIN wheels (m2 teeth carry
  the roller chain, ch. 23), so they never mesh another gear; the T24's tips
  overlap the disc rim in XY projection only (chain plane z -157.5..-152.5 vs disc
  -137.5..-134.5, 15.0 clear in z), exactly as the ch30 plates show. The ENGAGED pose and the
  swing path between the two are not modeled.
* The four column-clamp pinch screws are modeled backed-out (tips 0.2 inside
  their back-wall holes, 0.3 off the columns).
* Wires are flexible elements, not modeled; the drive chain is a real roller
  chain (alternating chain-inner-link / chain-outer-link), built as a native
  SolidWorks connected-linkage chain component pattern along the loop centreline
  spline, see _insert_roller_chain; the recording paper rides the platen as a
  rigid sheet (platen-paper).
* Both pinion-bar ends float: in the real machine the west end is carried by the
  ball-mount housing at the A-frame clevis and the east end by a column bracket;
  neither fitting is modeled.

Fix-all strategy (M6.2): every structural component inserted at its exact final
transform and fixed; the platen + rack + clips + paper are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 22-23, 25.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_paper_drive_assembly.py
"""

from __future__ import annotations

import math
import sys

import _config
from _chain import (
    CENTRELINE_LEN,
    CRANK_CENTRE as CHAIN_CRANK_CENTRE,
    KNOB_CENTRE as CHAIN_KNOB_CENTRE,
    LINK_COUNT,
    LINK_PITCH,
    PITCH_R_T12,
    PITCH_R_T24,
    TIP_R_T12,
    TIP_R_T24,
    centreline_distance,
    loop_point_tangent,
)
from _common import (
    IN,
    check,
    log,
    run_build,
)
from _assembly import (
    angle_driver,
    assert_expected_free_dof,
    assert_free_dof_necessity,
    check_no_interference,
    component_names,
    component_origin,
    component_transform,
    distance_driver,
    is_locked_build,
    lock_mate,
    named_ref,
    place_component,
    rack_pinion_mate,
    reledger_to_solved,
    save_assembly_and_images,
    set_park_defer,
    write_park_specs,
)
from _transforms import (  # noqa: E402
    IDENTITY,
    ROT_X_NEG90,
    ROT_X_POS90,
    ROT_Y_POS90,
    rot_z_rows,
)

ASM_NAME = "paper-drive"

# Build mode (cad/config/machine/build_lock.yaml). `free` (default) leaves the
# crank spin a FREE operational DOF (drag the crank sprocket and the belt-coupled
# knob + the platen feed follow); `locked` authors the spin-park engaged for a
# byte-reproducible 0-DOF snapshot. Read as a STRING-LITERAL so the accessor
# tokenises to machine/build_lock.yaml in the doit/cache digest (flipping the
# mode rebuilds ONLY paper-drive). `is_locked_build` rejects any value other than
# `free`/`locked`.
LOCK = is_locked_build(_config.machine("build_lock", "paper_drive"))

# --- machine anchors ---------------------------------------------------------
BAR_Z = -133.9  # support-bar centres: column line -112 - clamp offset 21.9
BAR_FRONT_Z = BAR_Z - 5.0  # -138.9: bar front face = platen back face
TOP_RAIL_Y = 440.0  # touches the platen back near its top edge (445)
BOT_RAIL_Y = 334.0  # above the rack band (top 323.6); clamp bottom 326
COLUMN_X = 197.0
COLUMN_Z = -112.0

# --- platen ------------------------------------------------------------------
from build_platen import PLATE_THICKNESS  # noqa: E402
from build_platen_rack import (  # noqa: E402
    PITCH as RACK_PITCH,
    PITCH_LINE_Y as RACK_PITCH_LINE_Y,
)
from build_rack_pinion import TEETH as RACK_PINION_TEETH  # noqa: E402
from build_transgear_pinion import TEETH as FINE_PINION_TEETH  # noqa: E402  # 24T

PLATE_X0 = -258.0  # right edge +42 (photo position)
PLATE_Y0 = 305.0
PLATE_FRONT_Z = BAR_FRONT_Z - PLATE_THICKNESS  # -142.9
PINION_AXIS = (0.0, 253.5)  # transgear stud on the pinion bar
PINION_PD_R = RACK_PINION_TEETH / 30.0 * IN / 2.0  # 40.64 (DP 30)
# Net platen feed per knob (T24) revolution through the engaged train: the knob
# and the fine 24T pinion are coaxial (one spin), the fine pinion reduces
# 24/96 into the 96T rack-pinion disc, and the disc feeds the rack pi*PD per
# rev. So one knob turn advances the platen 2*pi*PINION_PD_R * (24/96).
# Authored as a single rack-pinion mate onto the knob axis at this NET travel:
# a documented KINEMATIC coupling that leaves the intermediate transgear gears
# in their faithful ch30 rest pose (the fine-pinion/disc gap is preserved --
# the coupling is the engaged operation, the geometry stays as photographed).
NET_RACK_TRAVEL_PER_KNOB_REV = (
    2.0 * math.pi * PINION_PD_R * FINE_PINION_TEETH / RACK_PINION_TEETH
)  # 63.84 mm
RACK_BACKLASH = _config.fit("gear_mesh", "rack_backlash_mm")  # cad/config/tolerances.yaml
# Rz(180) placement: machine x = RACK_X0 - x_local, y = RACK_Y0 - y_local.
# Tooth centres sit at x_local = k * PITCH. The gear's seed gap is centred
# at +gamma/2 (the _gear.py flanks cross the pitch circle at +pi/(2N) and
# gamma - pi/(2N)), so a TOOTH -- not a gap -- sits at bottom dead centre
# and the gaps flank it at x = +-PITCH/2. RACK_X0 = 15.5 * PITCH puts rack
# teeth onto those gaps (the original 15 * PITCH was tip-to-tip: one max
# overlap dead centre decaying by the tip-circle sagitta at +-1..3 teeth).
RACK_X0 = 15.5 * RACK_PITCH  # 41.23 (right edge 0.77 west of the plate's)
RACK_Y0 = PINION_AXIS[1] + PINION_PD_R + RACK_BACKLASH + RACK_PITCH_LINE_Y

CLIP_Y0 = 312.0
CLIP_FRONT_DX = (18.0, 290.0)  # clip x bands (p - 10 .. p) inside the plate;
# the right clip sits east of the pen v-block's x band (-24..8)

# --- transgear ---------------------------------------------------------------
from build_transgear_latch import C2C as LATCH_C2C  # noqa: E402

# Ch30 rest state (M6.8): the plates show the knob-shaft cluster parked at
# post-mirror (-65, ~248 +- 3, chain-plane parallax); y is clamped to 241.78
# so the shaft top (246.5) keeps clearing the pinion bar's underside (247.5).
KNOB_SHAFT_XY = (65.0, 241.78)
LATCH_ANGLE_DEG = math.degrees(
    math.atan2(KNOB_SHAFT_XY[1] - PINION_AXIS[1], KNOB_SHAFT_XY[0] - PINION_AXIS[0])
)  # -10.22: small hub swung low toward the crank
REMOVABLE_Z0 = -157.5  # mounted T24 band -157.5..-152.5, mid -155 = the FRONT
# chain plane (book ch30 p005/p002: chain a flat loop on the front face, cone
# behind; plane moved -146 -> -155 with the ch30 GT crank re-anchor). South of
# the stub disc (-134.5..-137.5) by 15.0 and of the fine pinion (-134..-128):
# the knob shaft is reversed (knob to the north, see its placement) so its
# plain south length hosts the wheel clear of the disc. The crank-end T12
# is COPLANAR at -155 (drive-train REMOVABLE_Z0 -157.5) -- the chain runs flat.
T24_MID_Z = REMOVABLE_Z0 + 2.5  # -155.0 (face 5.0)
T12_MID_Z = -155.0  # drive-train REMOVABLE_Z0 -157.5 + face 5.0 / 2
CHAIN_MID_Z = (T24_MID_Z + T12_MID_Z) / 2.0  # -155.0: both wheels coplanar now,
# so the link pin0 stations ride a single flat front plane (was -81.05, north of
# the pedestal in the cone-post Z-band -- that collided); the chain floats
# radially outside the tooth tips so the z overlap with either wheel cannot interfere
REMOVABLE_TIP_R = {"T12": 14.0, "T18": 20.0, "T24": 26.0}  # m2: OD (T+2)*2

# Spare T18 removable: the swap chain wheel, stored flat on the base top
# (y 50.8 + the part's 5.0 half-thickness about the z -15 mid-plane), well west
# of the platen, axis +Z laid flat -> Rx(-90). A spare for this subsystem, so it
# rides here as a flat sibling of the mounted T24 (the book's single output group
# held both); placing it loose at the TOP level would clash on leaf name with the
# T12/T24 instances nested in drive-train / this sub.
SPARE_GEAR_POS = (-160.0, 55.8, -15.0)

# --- M6.10 fasteners ---------------------------------------------------------
# Platen-clip screws: each clip's own O3.0 end holes land at pre-mirror
# (clip_pos_x - 5, 320/429) after its Rz(+90); under-head face on the clip
# front (-144.1), O2.9 shank through the 1.2 strip and 2.8 into the
# platen's 3.5-deep sockets.
CLIP_SCREW_XY = ((-245.0, 320.0), (-245.0, 429.0), (27.0, 320.0), (27.0, 429.0))
# Column-clamp pinch screws on each platen-rail clamp's back face (z -88),
# backed out: the shank tip (-94.2) stays 0.2 inside the back-wall hole (inner
# end -94.4) and 0.3 off the column surface (-94.5). The wheel-bar clamp's
# pinch screw lives in magnifier.SLDASM.
PINCH_SCREW_Z = -88.0
PINCH_SCREW_XY = (
    (COLUMN_X, TOP_RAIL_Y),
    (-COLUMN_X, TOP_RAIL_Y),
    (COLUMN_X, BOT_RAIL_Y),
    (-COLUMN_X, BOT_RAIL_Y),
)


def _assert_rack_mesh() -> None:
    """Pitch-line backlash and tooth-on-gap phasing at x = 0."""
    rack_pitch_y = RACK_Y0 - RACK_PITCH_LINE_Y
    backlash = rack_pitch_y - (PINION_AXIS[1] + PINION_PD_R)
    if abs(backlash - RACK_BACKLASH) > 1e-9:
        raise RuntimeError(f"rack backlash {backlash:.3f} != {RACK_BACKLASH}")
    phase = math.remainder(RACK_X0, RACK_PITCH)  # tooth centres at +-p/2
    if abs(abs(phase) - RACK_PITCH / 2.0) > 1e-9:
        raise RuntimeError(
            f"rack tooth phase {phase:.4f} != +-p/2: the gear gaps sit at"
            f" +-PITCH/2 about bottom dead centre (tooth at the bottom)"
        )
    if RACK_PINION_TEETH % 4:
        raise RuntimeError("96T bottom-tooth alignment needs a multiple of 4")
    log(f"rack mesh: pitch line y {rack_pitch_y:.2f}, backlash {backlash:.2f},"
        f" rack teeth on the gaps flanking the gear's bottom tooth")


def _assert_knob_shaft_clearance() -> None:
    """The knob shaft must run under the pinion bar (z -105..-117 band),
    on the latch arm's exact c2c, with the rest-state air gaps intact."""
    arm = math.hypot(
        KNOB_SHAFT_XY[0] - PINION_AXIS[0], KNOB_SHAFT_XY[1] - PINION_AXIS[1]
    )
    if abs(arm - LATCH_C2C) > 1e-3:
        raise RuntimeError(f"knob shaft sits {arm:.4f} from the stud, latch c2c"
                           f" is {LATCH_C2C}")
    shaft_top = KNOB_SHAFT_XY[1] + 0.375 * IN / 2.0
    bar_bottom = PINION_AXIS[1] - 6.0
    if shaft_top >= bar_bottom - 0.5:
        raise RuntimeError(
            f"knob shaft top {shaft_top:.2f} too close to the pinion bar"
            f" underside {bar_bottom:.2f}"
        )
    # Rest state: the fine pinion (tip r 11) stays clear of the disc tips,
    # and the chain-plane T24 clears the STUB shaft (O14) it floats past.
    pinion_gap = arm - (41.49 + 11.0)  # disc tip r + pinion tip r
    if pinion_gap < 5.0:
        raise RuntimeError(f"rest-state pinion/disc tip gap {pinion_gap:.2f} < 5")
    t24_stub_gap = arm - (26.0 + 7.0)  # T24 tip r + stub shaft r
    if t24_stub_gap < 0.5:
        raise RuntimeError(f"mounted T24 to stub-shaft gap {t24_stub_gap:.2f} < 0.5")
    log(f"knob shaft at ({KNOB_SHAFT_XY[0]:.2f}, {KNOB_SHAFT_XY[1]:.2f}),"
        f" {bar_bottom - shaft_top:.2f} under the bar; rest-state gaps:"
        f" pinion/disc {pinion_gap:.1f}, T24/stub {t24_stub_gap:.1f}")


def _assert_chain_layout() -> None:
    """_chain.py derives the loop from OUR anchors -- pin them together."""
    if CHAIN_KNOB_CENTRE != KNOB_SHAFT_XY:
        raise RuntimeError(
            f"_chain KNOB_CENTRE {CHAIN_KNOB_CENTRE} != KNOB_SHAFT_XY {KNOB_SHAFT_XY}"
        )
    from build_drive_train_assembly import X_CRANK, Y_CRANK
    if CHAIN_CRANK_CENTRE != (X_CRANK, Y_CRANK):
        raise RuntimeError(
            f"_chain CRANK_CENTRE {CHAIN_CRANK_CENTRE} != drive-train crank"
            f" ({X_CRANK}, {Y_CRANK})"
        )
    if (TIP_R_T24, TIP_R_T12) != (REMOVABLE_TIP_R["T24"], REMOVABLE_TIP_R["T12"]):
        raise RuntimeError("_chain tip radii diverged from REMOVABLE_TIP_R")
    log(
        f"roller chain layout: loop {CENTRELINE_LEN:.2f}, {LINK_COUNT} links at"
        f" {LINK_PITCH:.4f}, seated on pitch circles ({PITCH_R_T24}/{PITCH_R_T12}),"
        f" plane z {CHAIN_MID_Z}"
    )


async def _place_chain_seed(adapter, part: str, station: int) -> str:
    """Seat ONE chain-pattern seed link at path ``station``, oriented along the
    forward CHORD (pin0->pin1) so both pin axes sit ~on the loop -- the connected
    -linkage chain pattern then fills the rest of the loop. Authored directly in
    post-mirror machine coordinates (``mirror_x=True``); the achiral link's
    local-z symmetry makes that a pure-Z rotation, keeping the plates flat in the
    chain plane. Returns the instance name."""
    x0, y0, _ = loop_point_tangent(
        station * LINK_PITCH, dx=KNOB_SHAFT_XY[0], dy=KNOB_SHAFT_XY[1], mirror_x=True
    )
    x1, y1, _ = loop_point_tangent(
        (station + 1) * LINK_PITCH, dx=KNOB_SHAFT_XY[0], dy=KNOB_SHAFT_XY[1], mirror_x=True
    )
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    return await place_component(
        adapter, part, [x0, y0, CHAIN_MID_Z], [0.0, 0.0, ang], rot_z_rows(ang),
        mirror=False, ground=True, label=f"{part} seed @ station {station}",
    )


async def _insert_roller_chain(adapter) -> None:
    """The drive chain: a native CHAIN COMPONENT PATTERN (connected linkage) of
    alternating inner/outer links along the _chain.py loop.

    Ch. 23: the chain rides the two mounted removables' m2 teeth (T24 knob shaft,
    T12 crank shaft). The loop centreline is authored as a single CLOSED SPLINE
    (one sketch segment) on an offset plane at the chain plane (z = CHAIN_MID_Z);
    two seed links (chain-inner-link @ station 0, chain-outer-link @ station 1)
    are placed tangent; SolidWorks' native ``FeatureChainPattern`` (connected
    linkage, via ``adapter.pattern_components_chain``) fills the loop with the
    alternating INNER (plates + bushings) / OUTER (plates + pins) links. Each
    link's two pin axes (Axis1/Axis2) are the group's path-links, so the pattern
    keeps every plate flat in the chain plane and tangent to the loop.

    The path MUST be one connected segment: SolidWorks never treats the 3-arc +
    taut-line contour as connected (the segments share coordinates but carry no
    coincidence relations, so MakeSketchChain forms 0 paths), hence the spline
    through dense loop samples. The dedicated ``FeatureChainPattern`` one-call API
    is used because the documented CreateDefinition/CreateFeature route returns
    null under pywin32 late binding. See memory/chain-pattern-not-createable-
    late-bound.md.

    Gates: the pattern produced EXACTLY LINK_COUNT links (the loop is sized
    CENTRELINE_LEN = LINK_COUNT * LINK_PITCH with LINK_COUNT even, so the two
    interleaved groups close it seamlessly), every instance sits on the chain
    plane, and its origin (pin0) reads back onto the loop centreline.
    """
    from solidworks_mcp.adapters.base import (
        ComponentChainPatternParameters,
        CreatePlaneParameters,
        RenameFeatureParameters,
    )

    # 1. Path: a single CLOSED SPLINE on an offset plane at the chain plane.
    plane = check(
        f"chain path plane @ z={CHAIN_MID_Z}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane",
                                  offset=CHAIN_MID_Z)))
    plane_name = getattr(plane, "name", plane)
    sk = check("chain path sketch", await adapter.create_sketch(plane_name))
    sketch_name = getattr(sk, "data", sk) if not isinstance(sk, str) else sk
    n_samples = 96
    pts = []
    for i in range(n_samples):
        s = i * CENTRELINE_LEN / n_samples
        x, y, _ = loop_point_tangent(
            s, dx=KNOB_SHAFT_XY[0], dy=KNOB_SHAFT_XY[1], mirror_x=True)
        pts.append({"x": x, "y": y})
    pts.append(pts[0])  # close the loop
    check("chain path spline", await adapter.add_spline(pts))
    check("chain path exit", await adapter.exit_sketch())
    # Give the auto-named path sketch a stable, human-readable name so the
    # pattern selects "Spline1@chain-path" independent of feature order.
    check("rename chain path sketch",
          await adapter.rename_feature(
              RenameFeatureParameters(old_name=sketch_name, new_name="chain-path")))
    sketch_name = "chain-path"

    # 2. Two seed links, tangent at the first two stations.
    inner = await _place_chain_seed(adapter, "chain-inner-link", 0)
    outer = await _place_chain_seed(adapter, "chain-outer-link", 1)

    # 3. Native connected-linkage chain pattern fills the loop.
    pattern = check(
        "roller chain (native chain component pattern)",
        await adapter.pattern_components_chain(
            ComponentChainPatternParameters(
                path_segment=f"Spline1@{sketch_name}",
                group1_component=inner,
                group1_link1=f"Axis1@{inner}", group1_link2=f"Axis2@{inner}",
                group1_plane=f"Front Plane@{inner}",
                group2_component=outer,
                group2_link1=f"Axis1@{outer}", group2_link2=f"Axis2@{outer}",
                group2_plane=f"Front Plane@{outer}",
                # Explicit count (NOT fill_path): _chain sizes CENTRELINE_LEN =
                # LINK_COUNT * LINK_PITCH with LINK_COUNT even, so LINK_COUNT links
                # close the loop seamlessly; fill_path undershoots (leaves a ~2-link
                # seam) because it reserves clearance. For connected linkage the
                # count is PER GROUP and the two groups interleave, so each group
                # gets LINK_COUNT // 2 (30 inner + 30 outer = 60 links).
                pitch_method="connected_linkage", fill_path=False,
                count=LINK_COUNT // 2, spacing=LINK_PITCH,
                align_method="tangent", options="dynamic")))
    # Rename the auto-named pattern feature (e.g. "LocalChainPattern1") to a
    # stable, human-readable name in the tree.
    pat_name = getattr(pattern, "name", None)
    if pat_name:
        check("rename chain pattern",
              await adapter.rename_feature(
                  RenameFeatureParameters(old_name=pat_name, new_name="roller-chain")))

    # The pattern OWNS the seed links' tangent alignment: it re-solves each off
    # the provisional authored chord angle (chord < arc on the wrap, so the two
    # pin axes pull the seed straight -- a fraction of a degree on the tight
    # pitch-circle wrap). Re-anchor the two seeds' pose-ledger entries to that
    # solved pose so the save-time gate checks the intended persistent pose.
    reledger_to_solved(adapter, inner)
    reledger_to_solved(adapter, outer)

    # Hide the path spline: it is construction scaffolding for the pattern, not a
    # rendered feature.
    check("blank chain path sketch", await adapter.blank_sketch("chain-path"))

    # 4. Gates: enough links, on the chain plane, on the loop centreline.
    links = [
        n
        for n in component_names(adapter)
        if n.startswith(("chain-inner-link", "chain-outer-link"))
    ]
    # EXACT closure: _chain sizes CENTRELINE_LEN = LINK_COUNT * LINK_PITCH with
    # LINK_COUNT even, so the connected-linkage pattern (LINK_COUNT // 2 per group)
    # fills the loop with EXACTLY LINK_COUNT links -- no seam, no band.
    if len(links) != LINK_COUNT:
        raise RuntimeError(
            f"chain pattern produced {len(links)} links, expected exactly {LINK_COUNT}")
    worst = 0.0
    for name in links:
        array = component_transform(adapter, name)
        x, y, z = (array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0)
        if abs(z - CHAIN_MID_Z) > 0.5:
            raise RuntimeError(f"{name}: link z {z:.3f} off the chain plane {CHAIN_MID_Z}")
        dist = centreline_distance(
            x, y, dx=KNOB_SHAFT_XY[0], dy=KNOB_SHAFT_XY[1], mirror_x=True)
        worst = max(worst, dist)
    if worst > 2.0:
        raise RuntimeError(f"chain links sit up to {worst:.2f} mm off the loop centreline")
    log(f"roller chain: native connected-linkage chain pattern, {len(links)} links"
        f" (worst off-loop {worst:.2f} mm)")


async def _sprocket_revolute(adapter, name: str, label: str) -> None:
    """Constrain a free-spinning sprocket to a fixed Z spin-axis, leaving the
    spin free (the operational/coupled DOF).

    Two axis-to-plane distances pin the central Axis1 (a Z line) in XY -- height
    (Top plane = y) and lateral (Right plane = x) -- and keep it parallel to Z;
    a Front-plane distance pins the axial z. The sprocket is a symmetric spur
    wheel, so its origin is spin-invariant and the origin ``verify`` passes at
    any spin angle (the spin is pinned separately, or left free + coupled)."""
    o = component_origin(adapter, name)
    await distance_driver(adapter, named_ref(f"Axis1@{name}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), o[1],
                          label=f"{label} axis height", verify=(name, o))
    await distance_driver(adapter, named_ref(f"Axis1@{name}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), o[0],
                          label=f"{label} axis lateral", verify=(name, o))
    await distance_driver(adapter, named_ref(f"Front Plane@{name}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), o[2],
                          label=f"{label} axial", verify=(name, o))


async def build(adapter) -> dict[str, str]:
    _assert_rack_mesh()
    _assert_knob_shaft_clearance()
    _assert_chain_layout()

    # `free` (default) DEFERS the freed crank-spin park driver (records, does not
    # author); `locked` authors it engaged. Set before any *_driver(free_dof_key=).
    set_park_defer(not LOCK)
    check("create_assembly", await adapter.create_assembly())

    # --- support rails + clamps ----------------------------------------------
    # The top-rail support-bar is FIRST so the auto-fixed seed is structure,
    # not the mated platen.
    for label, bar_y in (("top-rail", TOP_RAIL_Y), ("bot-rail", BOT_RAIL_Y)):
        await place_component(adapter, "support-bar", [0.0, bar_y, BAR_Z],
                              [0.0, 0.0, 0.0], IDENTITY, label=f"support-bar ({label})")
        for sx in (-1.0, 1.0):
            # Ry(+90): the clamp's front channel (local +X) faces -Z.
            await place_component(adapter, "column-clamp", [sx * COLUMN_X, bar_y, COLUMN_Z],
                                  [0.0, 90.0, 0.0], ROT_Y_POS90,
                                  label=f"column-clamp ({label} x{sx * COLUMN_X:+.0f})")

    # --- platen group ---------------------------------------------------------
    # The platen runs as a prismatic slider along X (the paper feed): its local
    # slide axis is held parallel to the Top + Front planes at the slide-line
    # offsets (axis-to-plane distance, no rotational redundancy) and an angle
    # snapshot kills the residual spin. Probed FULLY(3), probe_platen.py. The
    # rack, clips and paper ride it via Lock mates. The feed position (its X
    # slide) is NOT snapshot-pinned any more: it is COUPLED to the knob (T24)
    # rotation by the rack-pinion mate below, so in the default `free` build the
    # platen feed follows the free crank spin (one operational DOF); a `locked`
    # build pins it through the authored crank-spin park + the coupling chain.
    platen = await place_component(adapter, "platen",
                                   [PLATE_X0, PLATE_Y0, PLATE_FRONT_Z],
                                   [0.0, 0.0, 0.0], IDENTITY, ground=False)
    pl_o = component_origin(adapter, platen)
    await distance_driver(adapter, named_ref(f"Axis1@{platen}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), pl_o[1],
                          label="platen slide height", verify=(platen, pl_o))
    await distance_driver(adapter, named_ref(f"Axis1@{platen}", "AXIS"),
                          named_ref("Front Plane", "PLANE"), pl_o[2],
                          label="platen slide depth", verify=(platen, pl_o))
    await angle_driver(adapter, named_ref(f"Top Plane@{platen}", "PLANE"),
                       named_ref("Top Plane", "PLANE"), 0.0,
                       label="platen spin snapshot", verify=(platen, pl_o))
    # Rz(180): teeth point down at the rack pinion below.
    rack = await place_component(adapter, "platen-rack",
                                 [RACK_X0, RACK_Y0, BAR_FRONT_Z],
                                 [0.0, 0.0, 180.0], rot_z_rows(180.0), ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{rack}", "PLANE"),
                    named_ref(f"Front Plane@{platen}", "PLANE"),
                    label="platen-rack locked to platen")
    for dx in CLIP_FRONT_DX:
        # Rz(+90): the clip strip stands vertical on the paper face.
        clip = await place_component(adapter, "platen-clip",
                                     [PLATE_X0 + dx, CLIP_Y0, PLATE_FRONT_Z - 1.2],
                                     [0.0, 0.0, 90.0], rot_z_rows(90.0), ground=False,
                                     label=f"platen-clip x{PLATE_X0 + dx:+.0f}")
        await lock_mate(adapter, named_ref(f"Front Plane@{clip}", "PLANE"),
                        named_ref(f"Front Plane@{platen}", "PLANE"),
                        label=f"platen-clip x{PLATE_X0 + dx:+.0f} locked to platen")
    # Recording paper on the platen front face (ch30 p002/p003/p009): 0.5
    # proud of the platen, 2.25 clear of each clip band, 6 top/bottom margin.
    paper = await place_component(adapter, "platen-paper",
                                  [PLATE_X0 + 20.25, PLATE_Y0 + 6.0, PLATE_FRONT_Z - 0.5],
                                  [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{paper}", "PLANE"),
                    named_ref(f"Front Plane@{platen}", "PLANE"),
                    label="platen-paper locked to platen")

    # --- transgear group ------------------------------------------------------
    # (The rocker-support A-frame that used to stand here is now part of the
    # single rocker-arm-support casting in frame.SLDASM; the pinion-bar west end
    # floats and was never mated to it, so it is simply gone from this assembly.)
    await place_component(adapter, "pinion-bar", [PINION_AXIS[0], PINION_AXIS[1], -111.0],
                          [0.0, 0.0, 0.0], IDENTITY)
    # Rx(-90): stud +Y -> -Z; shaft z -101.5..-137.5, collar to -141.5.
    await place_component(adapter, "transgear-stub", [PINION_AXIS[0], PINION_AXIS[1], -101.5],
                          [-90.0, 0.0, 0.0], ROT_X_NEG90)
    await place_component(adapter, "rack-pinion", [PINION_AXIS[0], PINION_AXIS[1], -137.5],
                          [0.0, 0.0, 0.0], IDENTITY)
    await place_component(adapter, "transgear-latch", [PINION_AXIS[0], PINION_AXIS[1], -122.5],
                          [0.0, 0.0, LATCH_ANGLE_DEG], rot_z_rows(LATCH_ANGLE_DEG))
    # Reversed (Rx +90, origin at the south end z -158.0): the plain shaft now
    # runs -158.0..-100.0 with the grab-knob tucked NORTH (-100.0..-93.5),
    # freeing the south of the shaft for the chain wheel on the front -155
    # plane (shaft followed the chain plane -146 -> -155). The fine pinion
    # below stays at -134..-128 (parked clear of the disc, unchanged); the
    # knob sits north of the T24/chain band and clear of the pinion bar's
    # z band (-105..-117) by 5 in z (and the shaft passes under the bar in y
    # anyway, see _assert_knob_shaft_clearance).
    await place_component(adapter, "transgear-knob-shaft",
                          [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], -158.0],
                          [90.0, 0.0, 0.0], ROT_X_POS90)
    # Fine 24T DP30 pinion on the knob shaft, just behind the knob face
    # (z -134..-128): engageable on the disc, parked clear in the rest state.
    await place_component(adapter, "transgear-pinion",
                          [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], -134.0],
                          [0.0, 0.0, 0.0], IDENTITY)
    # Mounted T24 removable = the knob-end chain wheel (ch. 23: the roller
    # chain rides the removable's teeth; swapping removables changes the
    # platen ratio). Band -157.5..-152.5 on the front -155 plane, south of the
    # stub disc and fine pinion, coplanar with the crank-end T12. FREE to spin
    # (ground=False): the belt feature below couples it to the crank T12.
    t24 = await place_component(adapter, "transgear-removable",
                          [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], REMOVABLE_Z0],
                          [0.0, 0.0, 0.0], IDENTITY, configuration="T24", ground=False,
                          label="transgear-removable (mounted T24)")
    await _sprocket_revolute(adapter, t24, "T24 knob wheel")
    # Crank-end T12 removable = the crank-shaft chain wheel, brought over from
    # drive-train so the chain seats on BOTH sprockets locally. Placed at the
    # PRE-mirror crank centre (_chain CRANK_CENTRE == drive-train X_CRANK,Y_CRANK,
    # the same anchor _assert_chain_layout pins) and reflected by the default
    # mirror path, exactly like the T24 above -- so it lands on the crank wrap
    # centre the chain loops. Coplanar with the T24 on the -155 front plane; a
    # spur gear is symmetric so identity rotation. FREE to spin -- this is the
    # crank input, the single operational DOF.
    t12 = await place_component(adapter, "transgear-removable",
                          [CHAIN_CRANK_CENTRE[0], CHAIN_CRANK_CENTRE[1], REMOVABLE_Z0],
                          [0.0, 0.0, 0.0], IDENTITY, configuration="T12", ground=False,
                          label="transgear-removable (crank chain wheel T12)")
    await _sprocket_revolute(adapter, t12, "T12 crank wheel")
    # The roller chain looping both removables (_assert_chain_layout pins the
    # _chain.py anchors to KNOB_SHAFT_XY / the drive-train crank).
    await _insert_roller_chain(adapter)

    # --- operational coupling -------------------------------------------------
    # (1) Belt/Chain feature couples the crank T12 <-> knob T24 at the 12:24
    # chain ratio (the roller-chain visual is the physical realization; this is
    # the kinematic tie). Both pulleys are FREE, so EngageBelt's belt mates
    # actually constrain rotation. Diameters = pitch diameters (module 2).
    from solidworks_mcp.adapters.base import BeltChainParameters  # noqa: E402
    check(
        "belt/chain coupling T12<->T24",
        await adapter.insert_belt_chain(
            BeltChainParameters(
                pulley_components=[t12, t24],
                pulley_diameters=[2.0 * PITCH_R_T12, 2.0 * PITCH_R_T24],  # 24, 48 mm
                location_plane="Front Plane", pulley_axis="z",
                engage_belt=True, create_belt_part=False, blank_sketch=True)))
    # (2) Rack-pinion mate feeds the platen off the knob (T24) axis at the NET
    # through-train travel (fine-pinion 24T -> disc 96T -> rack). The intermediate
    # transgear gears stay in their faithful rest pose; this is the engaged
    # operation expressed kinematically across the documented 13.1 rest gap
    # (Appendix C #8). The rack linear reference is the platen's own slide Axis1
    # (along the feed X -- the rack is locked to the platen); the pinion reference
    # is the knob axis.
    await rack_pinion_mate(
        adapter,
        named_ref(f"Axis1@{platen}", "AXIS"),
        named_ref(f"Axis1@{t24}", "AXIS"),
        rack_travel_per_revolution=NET_RACK_TRAVEL_PER_KNOB_REV,
        label="platen feed (crank->knob->rack, net)")
    # (3) The crank spin is the FREED operational-DOF park driver. Deferred in the
    # default `free` build (recorded, not authored) -> T12 spins free and drives
    # the whole belt+rack train; authored + PARK_crank_spin in a `locked` build.
    # A spur sprocket is symmetric so the spin pose is cosmetic; pin the local
    # Right-plane dihedral (read live) like drive-train's crank_angle.
    t12_o = component_origin(adapter, t12)
    a_t12 = component_transform(adapter, t12)
    crank_dihedral = math.degrees(math.acos(max(-1.0, min(1.0, a_t12[0]))))
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{t12}", "PLANE"), named_ref("Right Plane", "PLANE"),
        crank_dihedral,
        label=f"crank spin PARK driver (freed in default build; a={crank_dihedral:.2f})",
        verify=(t12, t12_o), free_dof_key="crank_spin")

    # --- fasteners (M6.10) ----------------------------------------------------
    for x, y in CLIP_SCREW_XY:
        await place_component(adapter, "fillister-screw", [x, y, PLATE_FRONT_Z - 1.2],
                              [0.0, 0.0, 0.0], IDENTITY,
                              label=f"fillister-screw (clip x{x:+.0f} y{y:.0f})")
    for x, y in PINCH_SCREW_XY:
        await place_component(adapter, "pinch-screw", [x, y, PINCH_SCREW_Z],
                              [0.0, 0.0, 0.0], IDENTITY,
                              label=f"pinch-screw (clamp x{x:+.0f} y{y:.0f})")

    # Spare T18 removable: the swap chain wheel resting loose on the base, west
    # of the platen (a flat sibling of the mounted T24 above).
    await place_component(adapter, "transgear-removable", list(SPARE_GEAR_POS),
                          [-90.0, 0.0, 0.0], ROT_X_NEG90, configuration="T18",
                          label="transgear-removable (spare T18)")

    # Certify the AS-BUILT model. `free` -> necessity only (the crank spin is
    # genuinely free; the exact-count 0-DOF closure runs in the release preflight,
    # where the recorded spec is replayed). `locked` -> strict 0-DOF. All other
    # checks run on the as-built model unchanged.
    if LOCK:
        await assert_expected_free_dof(adapter, 0)
    else:
        # ONE freed operational DOF: the crank spin (the deferred PARK driver
        # above), which drives the belt-coupled knob + the rack-fed platen.
        assert_free_dof_necessity(
            adapter, 1, required_stems=("transgear-removable",))
        write_park_specs(ASM_NAME)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

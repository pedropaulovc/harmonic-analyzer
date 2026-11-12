"""The MHA-PD-00 paper-drive (transgear) assembly sequence, numbered in one place.

The drive_train_steps pattern (MHA-DT-00): a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text
(draw_pd_paper_drive_assembly); this module holds the order and the few fit-up
values no part spec owns, because they belong to the assembly procedure, not
to a part. The current feed reference comes from ``paper_drive_geom``'s
selected sprocket and gear ratios, not a historical pitch or tip-based
rolling diameter. The collar rear-face fit, wheel/pilot float and stud cut
come from MHA-PD-22 (its sheet shares the fit phrases, R9-30). Its actual
loaded overlap inspection precedes final platen installation and does not
turn the static F-to-disc setting into a clearance certificate.
The feed rack's datum setup band and its closed-form gates live in
``paper_drive_rack_setup`` (the builder gates on them) as design proofs; the
sheet sets and accepts that mesh by function, not on the band (#2416).
Drawing-only: no assembly builder imports it. No SolidWorks or live proof.
"""

from __future__ import annotations

import math

from pd_rack_pinion_spec import inch_ceil_mm, inch_floor_mm, inch_text

import dt_drive_train_steps
import pd_transgear_drive_collar_spec as collar
import paper_drive_mesh_check as mesh_check
import pd_transgear_feed_pinion_spec as feed_pinion
import _gear_quality as gear_quality
import paper_drive_geom as paper_geometry
import _paper_drive_placement as paper_placement

DRAWING_NUMBER = "MHA-PD-00"

# The chain fit-up starts from the crank side complete per its own fit-up
# (CONTRACT-paper-drive.md §13.2 procedure (1)): the 16T set on its feeler and
# the seat washer faced (MHA-DT-00 "crank-mesh-checked"), then the selected chain
# wheel on the crankshaft (MHA-DT-00 "paper-drive-wheel"). Cited by key so the
# pointer follows any renumbering of MHA-DT-00; both print on its crank
# sequence sheet (draw_dt_drive_train_assembly.CRANK_SHEET, sheet 8 since #2470
# added it).
CRANK_SIDE_KEYS = ("crank-mesh-checked", "paper-drive-wheel")
CRANK_SIDE_SHEET = 8
CRANK_SIDE_REF = (
    f"{dt_drive_train_steps.DRAWING_NUMBER} SHEET {CRANK_SIDE_SHEET}, STEPS "
    + " AND ".join(str(dt_drive_train_steps.step_number(key)) for key in CRANK_SIDE_KEYS)
)

SEQUENCE: tuple[str, ...] = (
    # Platen and support, on the exploded sheet: the bar on the columns at its
    # height, the platen built up on the bench, then hung with its locks.
    "bar-clamped",
    "rack-soldered",
    "guides-screwed",
    "clips-fitted",
    "platen-hung",
    # Platen on the bar (R9-49: the locks set clear of the hanger; R9-47: the
    # seats faced to the platen's float, pd_platen_guide_spec.LOCK_GAP_FIT).
    "guide-locks-set",
    "lock-seats-faced",
    # Disc cluster, on the bench, before anything is fixed on the arm, so the
    # reducer's trial mesh can run on it (R9-68: the disc on the sleeve's seat
    # shoulder, the hub's D-bore on its D-flat; R9-8, R9-9). Hub and bushings
    # are printed lengths (transgear_cluster_fit); nothing is faced: the float
    # is shimmed at assembly (owner ruling 2026-11-01, #2124).
    # Centre and seat the disc to the sleeve's actual running-bore datum
    # before transfer-spotting; lock, re-indicate every space, then match-mark.
    # Ahead of the arm's steps, so an arm remedy that repeats from
    # "latch-pin-pressed" never repeats the cluster's one-time transfer.
    "disc-cluster-assembled",
    "disc-taps-transferred",
    # Hanger, on the bench, then hung (R9-6: the spacer is fitted as made).
    "latch-pin-pressed",
    # R9-68: the plain pin pressed into the arm's reamed hole, head on the
    # arm's rear face (pd_transgear_pin_spec), before the plate is set: the
    # pressed shank is the cluster's running axis, so the setting indicates
    # it (not the head, which no drawing control holds to the shank: codjiflo
    # P2 on 8e8d5d5) and the trial mesh runs the cluster on it (#2417).
    "pin-pressed",
    # The plate's knob bore K is set on the mill DRO from the pressed pin's
    # shank S at MHA-PD-00 DETAIL K's model dimensions, the arm front up, and
    # held by clamps while the reducer is trial-meshed on its real seats (the
    # cluster on the pin, the knob shaft in the plate bore) and read with the
    # indicator; the trial only reads the setting (the S to N band stays its
    # limit, so the plate is not moved to chase a reading), and
    # only then are the two locating holes drilled and given their separate
    # final press/slip reams (#2417: doweled before any trial, a bad mesh was
    # found only at the chain fit-up and rebuilt twelve parts). The doweled
    # plate is read again before anything irreversible is done on the arm.
    "arm-plate-located",
    "arm-plate-fitted",
    "arm-plate-screws-cut",
    "hanger-pivoted",
    # R9-47: tips flush to 0.20 below the disc's rear face, cut ends broken
    # (pd_vn_transgear_disc_screw_spec.TIP_BELOW_REAR_FACE, CUT_END_BREAK_MAX).
    "disc-screws-cut",
    "oil-hole-drilled",
    # R9-68: on the pin between the two bushings, as made, the ring last.
    "disc-cluster-hung",
    # #2124: the ring gap read on a feeler, cluster rearward, and closed into
    # DETAIL E's window with MHA-PD-VN-68 shims under the rear bushing.
    "disc-cluster-shimmed",
    # Knob stack, front to rear (contract §1). R9-70 (N-A): the collar's pilot
    # faced on the bench to stand proud of every removable wheel, the
    # thumbnut's seat (pd_transgear_drive_collar_spec.PILOT_PROUD_RANGE); R9-70
    # (K-1): the cup set on a feeler at the plate's rear boss and cross-pinned
    # to the journal.
    "collar-pins-pressed",
    "pilot-faced-to-fit",
    "knob-stack-fitted",
    # Latch (R9-15, R9-24). The hanger is meshed in the rack and run over the
    # platen's travel first; the hook's pin hole is then match-drilled from
    # the pin to hold that mesh, and the hook hardened and refitted.
    "latch-hook-fitted",
    "hanger-meshed",
    "hook-pin-hole-match-drilled",
    # Preserve one positively loaded tooth-centred setup while inspecting the
    # entire located recording stroke, with the physical supports seated.
    "loaded-rack-geometry-checked",
    # Chain fit-up (contract §13.2 procedure (2)-(8)).
    "fitup-pose-set",
    # The reducer's confirmation remedies, one action each, take more
    # sub-steps than one step's letters (machinist review, #2417).
    "fitup-mesh-remedied",
    # The D-collar's rear face is fitted on the actual gear front F; the
    # thumbnut reacts through pilot, collar and F.
    "collar-rear-faced-to-fit",
    "collar-shoulder-seated",
    "stud-end-cut",
    # Inspect the actual loaded overlap with the trial platen off the bar,
    # without changing the arm's operating latch pose; refit and re-check.
    "collar-disc-air-inspected",
    "fitup-accepted",
    # The chain closed over both wheels and run (contract §13.2, ch. 23).
    "chain-closed",
    "chain-run-accepted",
)

_NUMBER = {key: index for index, key in enumerate(SEQUENCE, start=1)}
if len(_NUMBER) != len(SEQUENCE):
    raise ValueError("pd_paper_drive_assembly_steps.SEQUENCE repeats a key")


def step_number(key: str) -> int:
    """The printed number of ``key``; a KeyError names an unknown step."""
    return _NUMBER[key]


def step_ref(key: str) -> str:
    """A pointer another sheet prints, e.g. ``MHA-PD-00 STEP 4``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"


# The assembly sheet's enlargements of sheet 1's detail circles K and E
# (rule 9: a detail is labelled DETAIL, not VIEW; integration review at
# 8fb7fb46f7): K, the reducer's S-K setting, at which the arm and plate are
# match-drilled (pd_paper_drive_knob_setting_spec); E, the cluster's shimmed
# ring gap (pd_paper_drive_cluster_float_spec, whose own VIEW_NAME no sheet
# reads any more: #2323).
KNOB_SETTING_VIEW_NAME = "DETAIL K"
CLUSTER_FLOAT_VIEW_NAME = "DETAIL E"


def knob_setting_ref() -> str:
    """The pointer the arm and plate sheets print: ``MHA-PD-00 DETAIL K``."""
    return f"{DRAWING_NUMBER} {KNOB_SETTING_VIEW_NAME}"


def inch_window(limits_mm: tuple[float, float], places: int, joiner: str = "-") -> str:
    """A (min, max) window in this inch sheet's units, rounded inward so the
    printed window never admits a value the part spec refuses."""
    low = inch_ceil_mm(limits_mm[0], places)
    high = inch_floor_mm(limits_mm[1], places)
    return f"{inch_text(low, places)}{joiner}{inch_text(high, places)}"


def inch_max_text(limit_mm: float, places: int) -> str:
    """A maximum in inches, rounded down so the printed limit never admits a
    value the part spec refuses."""
    return f"{inch_text(inch_floor_mm(limit_mm, places), places)} MAX"


def inch_min_text(limit_mm: float, places: int) -> str:
    """A minimum in inches, rounded up for the same reason."""
    return f"{inch_text(inch_ceil_mm(limit_mm, places), places)} MIN"


# --- Values the procedure owns (CONTRACT-paper-drive.md §13.2) --------------
# A reference operating quantity, not a second gear-data block. The current
# travel law uses the reference pitch circle. A finite cutter's setting
# changes the tooth boundary, not the feed per revolution. A reference value
# prints to four inch places (machinist review: six read as a demanded precision).
PAPER_FEED_REFERENCE_PLACES = 4
PAPER_TRAVEL_PER_CRANK_TEXT = inch_text(
    paper_geometry.NET_RACK_TRAVEL_PER_CRANK_REV, PAPER_FEED_REFERENCE_PLACES
)

# The bar's top above the base deck: the builder's BAR_TOP_Y less the deck's
# BASE_DECK_Y. Its height affects the chain's centre distance, not the feed
# ratio; the fixed-centre loop's slack is solved by _chain from the current
# knob and crank axes. The title block's .XX band holds the height
# (Main, 2026-10-01), printed rounded from the builder's model value.
BAR_TOP_ABOVE_DECK = 266.934
BAR_TOP_ABOVE_DECK_TEXT = inch_text(BAR_TOP_ABOVE_DECK, 2)
# The rack's crests below the platen's bottom edge (the builder's PLATE_Y0
# less RACK_TIP_Y). The hook's pin hole is match-drilled wherever the meshed
# hanger puts the pin, but a rack set off this band swings the latched hanger
# and moves the pin along the hook's straight run, so the band is held at the
# solder joint. The feed mesh's datum pitch-line distance sets the crest drop.
RACK_CREST_DROP = paper_placement.RACK_CREST_DROP
RACK_CREST_TOL = 0.0508  # .002
# The feed rack's datum setup band and its gates are the builder's design
# proofs (paper_drive_rack_setup). The sheet prints no number for that mesh:
# the fitter sets it by feel and accepts it on function, no tight spot, no
# skipped tooth, a steady feed (owner direction 2026-11-11, #2416: the mesh
# must not bind, must not come loose and must feed at constant speed;
# backlash is not a function). As on the original, the arm is swung up until
# the teeth are fully engaged without binding and latched there; a tight spot
# is cleared by easing the arm off at it. No feeler, gauge or stop is used.
# What the feel set guarantees is the floor: the arm sits at the first bind,
# the flanks wedging at zero tooth-centred backlash or, at the corners where it
# comes first, a rack crest on the pinion's flank below its base circle (the
# interference point). The run's tight spot sets it, so every other station
# runs looser by at most the rack's relative index error and the feed's
# lateral terms (along the rack) and the pinion's toothspace runout over a
# turn (radial). The loosest feel set books those from the later of the two
# binds. Easing past the bind is not booked: the remedy eases the arm only
# until the teeth just turn free at the tight spot, which keeps the set at that
# spot's bind (draw_pd_paper_drive_assembly, "hanger-meshed"); the no-skip
# check before the hook is drilled only guards against the mesh coming loose.


def _feed_first_bind_backlash_mm() -> float:
    """The datum backlash at which the last printed corner clears interference."""
    low, high = 0.0, feed_pinion.RACK_BACKLASH_RANGE[1]
    if mesh_check.feed_rack_mesh((high, high)).interference_margin_min_mm < 0.0:
        raise AssertionError(
            "the feed mesh's design band reaches the interference point"
        )
    if mesh_check.feed_rack_mesh((low, low)).interference_margin_min_mm >= 0.0:
        return low
    for _ in range(60):
        middle = (low + high) / 2.0
        if mesh_check.feed_rack_mesh((middle, middle)).interference_margin_min_mm < 0.0:
            low = middle
        else:
            high = middle
    return high


FEED_FIRST_BIND_BACKLASH_MM = _feed_first_bind_backlash_mm()
# At the bind every printed corner keeps the rack's root clearance, positive
# backlash and its crests clear of the interference point.
mesh_check.feed_rack_mesh((FEED_FIRST_BIND_BACKLASH_MM,) * 2).require()
FEED_LOOSEST_BACKLASH_MM = (
    FEED_FIRST_BIND_BACKLASH_MM
    + gear_quality.rack_pitch_index_deviation_mm()
    + paper_geometry.feed_lateral_deviation_mm()
    + 2.0
    * feed_pinion.TOOTH_SPACE_RUNOUT_TIR_MM
    * math.tan(math.radians(feed_pinion.PRESSURE_ANGLE_DEG))
)
# Against coming loose and for a feed at constant speed: a contact ratio of at
# least 1.0 at the loosest feel set, at every printed corner, keeps one tooth
# pair in conjugate contact through every handover. Delegated ruling (Main,
# 2026-11-11, under the owner direction on #2416; owner review #2144): no
# precedent; it departs from the owner's 1.1 continuous-action floors at a
# loose extreme (the reducer's runout extreme, 2026-10-11, and option C's 1.1
# for the removed .003 leaf fallback), which only a gauged set could hold here.
# Residual accepted under the same ruling: the floor holds at the pinion/rack
# phase felt in step 24. A later re-latch enters at another tooth offset, and
# the pinion's toothspace runout can bring its high tooth to the tightest
# station, up to one TIR (0.051 mm) radial past the felt bind, about 0.037 mm
# of backlash. A bind there is felt in service and cured by re-setting the arm
# (step 25's remedy), as on the original.
FEED_CONTACT_RATIO_FLOOR = 1.0
FEED_LOOSEST_MESH = mesh_check.feed_rack_mesh(
    (FEED_FIRST_BIND_BACKLASH_MM, FEED_LOOSEST_BACKLASH_MM)
)
if not FEED_LOOSEST_MESH.contact_ratio_min >= FEED_CONTACT_RATIO_FLOOR:
    raise AssertionError(
        f"the loosest feel set leaves the feed mesh: {FEED_LOOSEST_MESH.summary}"
    )

# The collar is set to pd_transgear_drive_collar_spec.FIT_UP_OFFSET_SET_TEXT and
# accepted within OFFSET_ACCEPT_TOL of the same target at the re-check
# (procedure (8), in machine z, forward is -z).  Both readings
# take the knob wheel held back on its collar seat ("fitup-pose-set"): it floats
# KNOB_FLOAT_RANGE forward under the nut; reading it floated forward
# would set and accept the pair up to that float off.
# The re-check takes the largest .001 band the chain plane's ±1 mm leaves at
# the forward end, where every float adds (#2420), in mm: 1 - 0.0508 target
# - 0.05 half plate - 0.25 crank end play - 0.254 knob end float - 0.1524
# wheel float = 0.2428 (.0096), so .009.
OFFSET_ACCEPT_TOL = 0.2286  # .009
# What the acceptance passes, in service: the seated front faces within the
# accepted band, the mid-planes a half plate band either way (both chain
# wheels are MHA-PD-09 plates); then the crank's end play, the knob's end
# float and the knob wheel's own float under the nut forward. Nothing moves the
# crank wheel rearward: MHA-PD-VN-63 holds the arm on a spacer pressed on the
# MHA-PD-VN-57 shoulder, so its tilt is fixed in the bar and read here as made
# (pd_transgear_drive_collar_spec's in-service terms, one helper for the
# setting and this re-check):
ACCEPTED_CHAIN_OFFSET_IN_SERVICE = collar.chain_offset_in_service(OFFSET_ACCEPT_TOL)
if max(map(abs, ACCEPTED_CHAIN_OFFSET_IN_SERVICE)) > collar.CHAIN_OFFSET_LIMIT:
    raise AssertionError(
        f"an accepted chain pair runs {ACCEPTED_CHAIN_OFFSET_IN_SERVICE[0]:+.3f}.."
        f"{ACCEPTED_CHAIN_OFFSET_IN_SERVICE[1]:+.3f} in service, past "
        f"±{collar.CHAIN_OFFSET_LIMIT}"
    )
# R9-47/R9-68's F-to-disc fit window is a static axial setting, not a
# certificate of clearance at the actual collar/disc overlap. The independent
# physical criterion is inspected through a whole disc turn with all play
# biased closing, as the collar's current assembly contract requires.
COLLAR_DISC_AIR_MIN = collar.COLLAR_DISC_AIR_MIN

# The printed forms of those bands: a drawing script only places them.
OFFSET_ACCEPT_TEXT = (
    f"{inch_text(collar.FIT_UP_OFFSET_TARGET, 3)} \u00b1{inch_text(OFFSET_ACCEPT_TOL, 3)}"
)
COLLAR_DISC_AIR_TEXT = inch_min_text(COLLAR_DISC_AIR_MIN, 3)
RACK_CREST_TEXT = f"{inch_text(RACK_CREST_DROP, 3)} \u00b1{inch_text(RACK_CREST_TOL, 3)}"

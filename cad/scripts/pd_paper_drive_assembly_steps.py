"""The MHA-PD-000 paper-drive (transgear) assembly sequence, numbered in one place.

The drive_train_steps pattern (MHA-DT-000): a step's number is its position in
SEQUENCE, so inserting a step renumbers every later one and every pointer that
cites a step by key follows. The sheet prints the step text
(draw_pd_paper_drive_assembly); this module holds the order and the few fit-up
values no part spec owns, because they belong to the assembly procedure, not
to a part. The current feed reference comes from ``paper_drive_geom``'s
selected sprocket and gear ratios, not a historical pitch or tip-based
rolling diameter. The collar rear-face fit, wheel/pilot float and stud cut
come from MHA-PD-022 (its sheet shares the fit phrases, R9-30). Its actual
loaded overlap inspection precedes final platen installation and does not
turn the static F-to-disc setting into a clearance certificate.
The frozen finite-rack reader requires the exact source-derived measured-datum
physical stack. Its configured operating-domain wrapper additionally guards
the actual cut ends and the entire located, graded recording-paper sweep;
no hardware stop or reduced paper stroke is implied. No SolidWorks or live proof.
"""

from __future__ import annotations

import math

import dt_drive_train_steps
import pd_transgear_drive_collar_spec as collar
import pd_transgear_feed_pinion_spec as feed_pinion
import paper_drive_mesh_check as mesh_check
import paper_drive_rack_travel as rack_travel
import transgear_hanger_joints as joints
import pd_transgear_removable_spec as removable
import paper_drive_geom as paper_geometry

DRAWING_NUMBER = "MHA-PD-000"

# The chain fit-up starts from the crank side complete per its own fit-up
# (CONTRACT-paper-drive.md §13.2 procedure (1)): the 16T set on its feeler and
# the seat washer faced (MHA-DT-000 "crank-mesh-checked"), then the selected chain
# wheel on the crankshaft (MHA-DT-000 "paper-drive-wheel"). Cited by key so the
# pointer follows any renumbering of MHA-DT-000; both print on its cone-and-crank
# sequence sheet (draw_dt_drive_train_assembly.SEQUENCE_SHEET).
CRANK_SIDE_KEYS = ("crank-mesh-checked", "paper-drive-wheel")
CRANK_SIDE_SHEET = 6
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
    # Hanger, on the bench, then hung (R9-6: the spacer is fitted as made).
    "latch-pin-pressed",
    # R9-68: the plain pin pressed into the arm's reamed hole, head on the
    # arm's rear face (pd_transgear_pin_spec).
    "pin-pressed",
    # The critical gear-plane S-K pose is held in the matched jig before the
    # two locating holes receive their separate final press/slip reams.
    "arm-plate-located",
    "arm-plate-fitted",
    "arm-plate-screws-cut",
    "hanger-pivoted",
    # Disc cluster, on the bench (R9-68: the disc on the sleeve's seat
    # shoulder, the hub's D-bore on its D-flat; R9-8, R9-9). The hub is then
    # faced to stand inside transgear_cluster_fit.HUB_NOSE_WINDOW behind the
    # sleeve nose, so the front bushing bears on the steel nose and traps the
    # hub and disc against the shoulder.
    # Centre and seat the disc to the sleeve's actual running-bore datum
    # before transfer-spotting; lock, re-indicate every space, then match-mark.
    "disc-cluster-assembled",
    "hub-faced-to-nose",
    "disc-taps-transferred",
    # R9-47: tips flush to 0.20 below the disc's rear face, cut ends broken
    # (vn_transgear_disc_screw_spec.TIP_BELOW_REAR_FACE, CUT_END_BREAK_MAX).
    "disc-screws-cut",
    "oil-hole-drilled",
    # R9-68: on the pin between the two bushing blanks, the ring last.
    "disc-cluster-hung",
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
    # R9-68: in that pose, the MHA-PD-025 front bushing faced to m (the F-to-disc
    # window, cluster forward), then the MHA-PD-024 rear bushing faced to the
    # cluster's float (transgear_cluster_fit).
    "front-bushing-faced-to-fit",
    "rear-bushing-faced-to-fit",
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
    """A pointer another sheet prints, e.g. ``MHA-PD-000 STEP 4``."""
    return f"{DRAWING_NUMBER} STEP {step_number(key)}"


# --- Values the procedure owns (CONTRACT-paper-drive.md §13.2) --------------
# A reference operating quantity, not a second gear-data block. The current
# travel law uses the reference pitch circle. A finite cutter's setting
# changes the tooth boundary, not the feed per revolution.
PAPER_FEED_REFERENCE_PLACES = 6
PAPER_TRAVEL_PER_CRANK_TEXT = format(
    paper_geometry.NET_RACK_TRAVEL_PER_CRANK_REV,
    f".{PAPER_FEED_REFERENCE_PLACES}f",
)
PAPER_FEED_REFERENCE_TEXT = (
    f"FEED SETUP: {removable.CRANK_CONFIG} CRANK / "
    f"{removable.KNOB_CONFIG} KNOB.\n"
    f"PLATEN TRAVEL {PAPER_TRAVEL_PER_CRANK_TEXT} PER CRANK REV (REF)."
)

# The bar's top above the base deck: the builder's BAR_TOP_Y less the deck's
# BASE_DECK_Y. Its height affects the chain's centre distance, not the feed
# ratio; the fixed-centre loop's slack is solved by _chain from the current
# knob and crank axes. The title block's .X band holds the height
# (Main, 2026-10-01).
BAR_TOP_ABOVE_DECK = 266.934
# The rack's crests below the platen's bottom edge (the builder's PLATE_Y0
# less RACK_TIP_Y). The hook's pin hole is match-drilled wherever the meshed
# hanger puts the pin, but a rack set off this band swings the latched hanger
# and moves the pin along the hook's straight run, so the band is held at the
# solder joint. The feed mesh's datum pitch-line distance sets the crest drop.
RACK_CREST_DROP = paper_geometry.RACK_CREST_DROP
RACK_CREST_TOL = 0.05
# The feed owner's range is a tooth-centred rack-normal DATUM setup. The
# platen's endpoint-to-endpoint shake equals this band only with a feed tooth
# bisector directly below a rack-space bisector.
RACK_DATUM_BACKLASH_RANGE = feed_pinion.RACK_BACKLASH_RANGE
RACK_ROOT_CLEARANCE_FLOOR = mesh_check.RACK_ROOT_CLEARANCE_FLOOR_MM
# The model's pitch-line distance at the nominal translation, across the
# datum band (pd_transgear_feed_pinion_spec's backlash law).
RACK_DATUM_MODEL_AXIS_DISTANCE_RANGE = tuple(
    mesh_check.feed_rack_axis_distance_mm(backlash, feed_pinion.RADIAL_SETTING)
    for backlash in RACK_DATUM_BACKLASH_RANGE
)

# Codex P1 on b2eb9a0e1: the hook's Ø3.3 pin hole is match-drilled from the
# MHA-VN-042 pin with the largest pin on its lower edge
# ("hook-pin-hole-match-drilled"), so the unclamped arm cannot fall through
# the hole. With no slack the latch adds no opening to the rack mesh's loose
# datum end.
LATCH_SLACK_ALONG = 0.0


def require_feed_rack_datum_axis_distance(
    axis_distance_mm: float,
    datum_backlash_band: tuple[float, float] = RACK_DATUM_BACKLASH_RANGE,
) -> None:
    """The model's pitch-line distance must give a datum backlash in band."""
    low, high = datum_backlash_band
    specified_low, specified_high = RACK_DATUM_BACKLASH_RANGE
    if not specified_low <= low <= high <= specified_high:
        raise ValueError("rack datum setup band leaves its specified limits")
    near = mesh_check.feed_rack_axis_distance_mm(low, feed_pinion.RADIAL_SETTING)
    far = mesh_check.feed_rack_axis_distance_mm(high, feed_pinion.RADIAL_SETTING)
    # 1e-6 mm absorbs the native model's length round trip only.
    if not near - 1e-6 <= axis_distance_mm <= far + 1e-6:
        raise ValueError(
            f"rack pitch line {axis_distance_mm:.6f} mm from the feed axis is "
            f"outside the datum band {near:.6f}..{far:.6f} mm"
        )


def require_feed_rack_mesh(
    datum_backlash_band: tuple[float, float] = RACK_DATUM_BACKLASH_RANGE,
    latch_slack_along: float = LATCH_SLACK_ALONG,
) -> mesh_check.MeshCheck:
    """Closed-form gates for the set rack mesh over the printed corners.

    The latch pin's drop with ``latch_slack_along`` of travel left opens the
    loose end of the datum band.
    """
    low, high = datum_backlash_band
    specified_low, specified_high = RACK_DATUM_BACKLASH_RANGE
    if not specified_low <= low <= high <= specified_high:
        raise ValueError("rack datum setup band leaves its specified limits")
    if not math.isfinite(latch_slack_along) or latch_slack_along < 0.0:
        raise ValueError("latch opening must be finite and nonnegative")
    return mesh_check.feed_rack_mesh(
        datum_backlash_band, joints.latch_pinion_drop(latch_slack_along)
    ).require()


def feed_rack_operating_domain() -> rack_travel.RackOperatingDomain:
    """The engaged-feed window, checked against the located paper sweep."""
    domain = rack_travel.rack_operating_domain_mm(
        contact_half_width_mm=mesh_check.feed_rack_contact_half_width_mm(
            RACK_DATUM_BACKLASH_RANGE
        ),
        lateral_deviation_mm=paper_geometry.feed_lateral_deviation_mm(),
        profilecentre_x_offset_band_mm=(
            paper_geometry.feed_profilecentre_x_offset_band_mm()
        ),
        cut_end_section_maxima_mm=(
            paper_geometry.feed_rack_cut_end_section_maxima_mm()
        ),
    )
    domain.require_recording_paper_sweep_mm(
        **paper_geometry.recording_paper_sweep_bands_mm()
    )
    return domain


# The collar is set to pd_transgear_drive_collar_spec.FIT_UP_OFFSET_SET_TEXT and
# accepted within OFFSET_ACCEPT_TOL of the same target at the re-check
# (procedure (8): "-0.05 ±0.10" in machine z, forward is -z).  Both readings
# take the knob wheel held back on its collar seat ("fitup-pose-set"): it floats
# KNOB_FLOAT_RANGE forward under the nut; reading it floated forward
# would set and accept the pair up to that float off.
OFFSET_ACCEPT_TOL = 0.10
# What the acceptance passes, in service: the seated front faces within the
# accepted band, the mid-planes a half plate band either way (both chain
# wheels are MHA-PD-009 plates); then the crank's end play, the knob's end
# float and the knob wheel's own float under the nut forward. Nothing moves the
# crank wheel rearward: MHA-VN-049 holds the arm on a spacer pressed on the
# MHA-VN-041 shoulder, so its tilt is fixed in the bar and read here as made
# (pd_transgear_drive_collar_spec's in-service terms):
_HALF_PLATE_SPREAD = (max(removable.PLATE_BAND) - min(removable.PLATE_BAND)) / 2.0
ACCEPTED_CHAIN_OFFSET_IN_SERVICE = (
    -(collar.FIT_UP_OFFSET_TARGET + OFFSET_ACCEPT_TOL)
    - _HALF_PLATE_SPREAD
    - collar.CRANK_END_PLAY_MAX
    - collar.KNOB_END_FLOAT_MAX
    - max(collar.KNOB_FLOAT_RANGE),
    OFFSET_ACCEPT_TOL
    - collar.FIT_UP_OFFSET_TARGET
    + _HALF_PLATE_SPREAD
    + collar.HANGER_AXIAL_PLAY_MAX,
)
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
OFFSET_ACCEPT_TEXT = f"{collar.FIT_UP_OFFSET_TARGET:.2f} \u00b1{OFFSET_ACCEPT_TOL:.2f}"
# The knob wheel floats collar.KNOB_FLOAT_RANGE forward of its seat (the collar's
# front face) under the thumbnut; the setting and its acceptance read it
# held back on that seat, the pose ACCEPTED_CHAIN_OFFSET_IN_SERVICE assumes.
KNOB_HELD_BACK_TEXT = f"{removable.KNOB_CONFIG} HELD BACK ON ITS SEAT"
COLLAR_DISC_AIR_TEXT = f"{COLLAR_DISC_AIR_MIN:.2f} MIN"
RACK_CREST_TEXT = f"{RACK_CREST_DROP:.2f} \u00b1{RACK_CREST_TOL:.2f}"
RACK_DATUM_BACKLASH_TEXT = (
    f"{RACK_DATUM_BACKLASH_RANGE[0]:.2f} TO {RACK_DATUM_BACKLASH_RANGE[1]:.2f}"
)

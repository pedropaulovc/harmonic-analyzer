"""The machine's master build order: which sub-assembly steps run where, where
the frame comes apart for the mill and where it goes back up (#2391, #850).

MHA-DT-00 locates the cylinder bank, the north pivot bracket and the pinion
rig on the bare base on the mill and drills their seats into it; MHA-CH-00
transfers the south bracket's foot into the base's MHA-FR-05 rail there, and
its fulcrum keepers' feet into the top frame's rail with MHA-FR-02 alone on
the mill. MHA-FR-00 already lifts its columns and top frame off the base to
drill the upper tube holes, so the frame stays apart from that step until
those mill steps are done, and goes back up on its match marks before
anything is hung from the top frame.

Each sub-assembly sheet numbers its own steps (fr_frame_assembly_steps,
dt_drive_train_steps, ch_channel_assembly_steps); this module only cuts each
of those sequences into runs at step KEYS, so a run prints the numbers its
sheet prints and follows any renumbering, and every step of the three cut
sequences lies in exactly one run (test_ha_build_sequence). MHA-HA-00 prints
the runs as its integration steps 1, 2 and 4 (ha_harmonic_analyzer_assembly_
sheet); the release's ASSEMBLY.md prints the whole table (ha_assembly_package).
Pure data: no SolidWorks, no config reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType

import ch_channel_assembly_steps as ch_steps
import dt_drive_train_steps as dt_steps
import fr_frame_assembly_steps as fr_steps
import ha_harmonic_analyzer_assembly_steps as ha_steps


@dataclass(frozen=True)
class Run:
    """Consecutive steps of one sheet: from ``first`` up to, not including,
    ``stop`` (``None``: to the sheet's last step)."""

    steps: ModuleType
    first: str
    stop: str | None = None

    @property
    def numbers(self) -> range:
        start = self.steps.step_number(self.first)
        end = (
            self.steps.step_number(self.stop)
            if self.stop is not None
            else len(self.steps.SEQUENCE) + 1
        )
        if end <= start:
            raise ValueError(f"{self.steps.DRAWING_NUMBER} run {self.first}: empty")
        return range(start, end)

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self.steps.SEQUENCE[n - 1] for n in self.numbers)

    @property
    def text(self) -> str:
        """``MHA-FR-00 STEPS 1-25`` (or ``STEP 7`` for one step)."""
        first, last = self.numbers[0], self.numbers[-1]
        span = f"STEP {first}" if first == last else f"STEPS {first}-{last}"
        return f"{self.steps.DRAWING_NUMBER} {span}"


# --- The cuts ---------------------------------------------------------------
# MHA-FR-00: fitted, match-marked, cut and drilled; it lifts the columns and
# MHA-FR-02 off MHA-FR-01 at FRAME_LIFTED_KEY and reseats them at
# "frame-reassembled". The deck parts (support, nameplate) and the gooseneck
# set screw go on the loose castings; the final frame checks follow the
# re-erection.
FRAME_LIFTED_KEY = "frame-lifted-for-drill"
FRAME_FITTED = Run(fr_steps, fr_steps.SEQUENCE[0], "frame-reassembled")
LOOSE_CASTINGS = Run(fr_steps, "support-seated", "columns-seated-checked")
FRAME_ERECTED = Run(fr_steps, "frame-reassembled", "support-seated")
FRAME_CHECKED = Run(fr_steps, "columns-seated-checked")
# MHA-DT-00: cone set and crank at the bench; from the cylinder stack on, the
# base is on the mill (its step 8 puts it there).
DT_BENCH = Run(dt_steps, dt_steps.SEQUENCE[0], ch_steps.CYLINDER_STACK_KEY)
DT_BASE_ON_MILL = Run(dt_steps, ch_steps.CYLINDER_STACK_KEY)
# MHA-CH-00: the rocker stack and rod pins at the bench (before MHA-DT-00
# step 8 sets the rods on the cams); the rocker bank on the base, still on the
# mill; the fulcrum keeper pair, bored together once the base is off the mill;
# the keepers on MHA-FR-02 on the mill; the lever bank once the frame is up
# (its bars' feet straddle the rocker arms below).
CH_BENCH = Run(ch_steps, ch_steps.SEQUENCE[0], "north-bracket-held")
CH_BASE_ON_MILL = Run(ch_steps, "north-bracket-held", "keepers-clamped")
CH_KEEPER_PAIR = Run(ch_steps, "keepers-clamped", "keepers-on-frame")
CH_TOP_FRAME_ON_MILL = Run(ch_steps, "keepers-on-frame", "bar-notches-set")
CH_ON_FRAME = Run(ch_steps, "bar-notches-set")
# MHA-HA-00 from the summing lever on: everything hangs on the erected frame.
HA_ON_FRAME = Run(ha_steps, "summing-hung")


@dataclass(frozen=True)
class Phase:
    """One row of the master sequence: what runs, where, with the frame so."""

    title: str
    where: str
    frame: str
    runs: tuple[Run, ...]


PHASES: tuple[Phase, ...] = (
    Phase(
        "FRAME FITTED",
        "FLAT BENCH",
        f"APART FROM {fr_steps.step_ref(FRAME_LIFTED_KEY)}",
        (FRAME_FITTED,),
    ),
    Phase("DECK PARTS AND SET SCREW", "BENCH", "APART", (LOOSE_CASTINGS,)),
    Phase("CONE SET, CRANK, ROCKER PAIRS", "BENCH", "APART", (DT_BENCH, CH_BENCH)),
    Phase(
        "CYLINDER BANK, PINION RIG, ROCKER BANK",
        "MHA-FR-01 ON THE MILL",
        "APART",
        (DT_BASE_ON_MILL, CH_BASE_ON_MILL),
    ),
    Phase("FULCRUM KEEPER PAIR", "BENCH AND MILL", "APART", (CH_KEEPER_PAIR,)),
    Phase(
        "KEEPERS ON MHA-FR-02",
        "MHA-FR-02 ON THE MILL",
        "APART",
        (CH_TOP_FRAME_ON_MILL,),
    ),
    Phase(
        "FRAME RE-ERECTED",
        "ON MHA-FR-01",
        "RE-ERECTED ON ITS MATCH MARKS",
        (FRAME_ERECTED, FRAME_CHECKED),
    ),
    Phase("INTEGRATION", "ERECTED FRAME", "UP", (HA_ON_FRAME, CH_ON_FRAME)),
)

# Every step that drills, reams, taps or spots a hole through or from a part
# already located on another (match-drilled, match-reamed or transferred), by
# sheet and key: the master table names them so the shop sees which belong on
# the mill. Printed numbers follow the keys.
MATCH_LOCATED: tuple[tuple[ModuleType, str], ...] = (
    (fr_steps, fr_steps.LOWER_HOLES_PILOTED_KEY),
    (fr_steps, "upper-holes-piloted"),
    (fr_steps, fr_steps.NAMEPLATE_SPOTTED_KEY),
    (dt_steps, "post-and-tip-block"),
    (dt_steps, "crank-hub-fitted"),
    (dt_steps, "crank-handle-fitted"),
    (dt_steps, ch_steps.CYLINDER_STACK_KEY),
    (dt_steps, "cylinder-bank-located"),
    (dt_steps, ch_steps.NORTH_BRACKET_SET_KEY),
    (dt_steps, "straps-pinned-to-torque-shaft"),
    (dt_steps, "rig-seats-transferred"),
    (dt_steps, "lever-pin-set"),
    (dt_steps, "other-base-mounting"),
    (ch_steps, "south-foot-transferred"),
    (ch_steps, ch_steps.KEEPERS_PAIR_REAMED_KEY),
    (ch_steps, "keeper-feet-transferred"),
)


def match_located(phase: Phase) -> tuple[str, ...]:
    """``MHA-DT-00 STEP 10``-style pointers to the phase's match-located steps."""
    return tuple(
        steps.step_ref(key)
        for steps, key in MATCH_LOCATED
        if any(run.steps is steps and key in run.keys for run in phase.runs)
    )

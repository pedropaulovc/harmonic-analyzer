"""Pure explode contract of pn-pen.SLDASM (MHA-PN-000): the builder's named
``PN_EXPLODED`` presentation and the ordered native steps that open it.

Only ``_pn_pen_explode`` (through the builder's canonical
``author_in_drawing_configurations`` call) and the drawing read this module,
so an explode-only edit takes the EXPLODE refresh tier (``_refresh_tier``):
the saved model is reopened and its named explodes are re-authored, with no
insert/mate loop. Distances are presentation offsets, not dimensions;
directions come from the carriage's own axes (``pn_pen_carriage_geom``) or
the assembly's global axes. No SolidWorks imports.

The disassembly order, the sheet's ASSEMBLY_STEPS read back to front: the
hanger's loose fastening off, the wire off the eye, the carriage out of the
U guides' open front ends, the stud and its jam nut up off the rod top, the
carriage down off the rod's pivot, the rod set screw back out along its tap,
the marker back out along its own axis, the thumb screw down out of the
stirrup's bottom-rail tap, and the stirrup, its thumb screw on that tap's
axis, off the block's paper end along the neck it slides on. Only after
withdrawal do the stirrup and screw turn together about the detached window's
vertical centreline, revealing its opening without implying an in-place hinge.
Translations along the yawed block's axes use paired global X/Z steps.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import pn_pen_carriage_geom as carriage
import pn_pen_frame_spec as frame
import pn_pen_v_block_spec as v_block
from _explode_transforms import RigidTransform
from _simplified_names import simplified_name
from pn_pen_assembly_spec import (
    BOM_ORDER,
    FRAME,
    HANGER,
    HANGER_JAM_NUT,
    HANGER_NUT,
    HANGER_SCREW,
    MARKER,
    ROD,
    ROD_SET_SCREW,
    STUD,
    STUD_NUT,
    THUMB_SCREW,
    V_BLOCK,
    WIRE,
)

EXPLODED_VIEW_NAME = "PN_EXPLODED"
SOURCE_CONFIGURATION = "Default"


@dataclass(frozen=True)
class TranslationStep:
    label: str
    stems: tuple[str, ...]
    axis: str
    distance_mm: float

    @property
    def transform(self) -> RigidTransform:
        return RigidTransform.translation(
            tuple(self.distance_mm if key == self.axis else 0.0 for key in "xyz")
        )


@dataclass(frozen=True)
class RotationStep:
    label: str
    stems: tuple[str, ...]
    axis: str
    angle_rad: float
    pivot_mm: tuple[float, float, float]

    @property
    def transform(self) -> RigidTransform:
        return RigidTransform.rotation(
            tuple(float(key == self.axis) for key in "xyz"), self.angle_rad, self.pivot_mm
        )


ExplodeStep = TranslationStep | RotationStep

# The block's axes in machine coordinates (pn_pen_carriage_geom's rows): X
# along the block from its paper end, Y up, Z out of its back face; -Z is the
# front face's outward normal.
BLOCK_X, BLOCK_Y, BLOCK_Z = (tuple(row) for row in carriage.BLOCK_ROWS)


def exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns: exploded-view names are unique
    per document, so ``Default Simplified``'s copy carries the suffix too."""
    if configuration == SOURCE_CONFIGURATION:
        return EXPLODED_VIEW_NAME
    if configuration == simplified_name(SOURCE_CONFIGURATION):
        return simplified_name(EXPLODED_VIEW_NAME)
    raise ValueError(f"{EXPLODED_VIEW_NAME}: no explode is authored in {configuration!r}")


def _along(
    label: str,
    stems: tuple[str, ...],
    direction: tuple[float, ...],
    distance: float,
) -> tuple[TranslationStep, ...]:
    """``distance`` mm along the unit ``direction``, one native step per global
    axis it has a component on (suffixed with that axis when it has two)."""
    if not math.isclose(math.hypot(*direction), 1.0, abs_tol=1e-12):
        raise ValueError(f"{label}: {direction!r} is not a unit direction")
    parts = [
        (key, distance * component)
        for key, component in zip("xyz", direction)
        if abs(component) > 1e-12
    ]
    if len(parts) == 1:
        return (TranslationStep(label, stems, parts[0][0], parts[0][1]),)
    return tuple(TranslationStep(f"{label} {key}", stems, key, value) for key, value in parts)


def _negated(direction: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(-value for value in direction)


_CARRIAGE = (V_BLOCK, ROD_SET_SCREW, FRAME, THUMB_SCREW, MARKER)
# The wire's sideways explode, each of X and -Z: 35 mm on the sheet at 1:2.
WIRE_ASIDE = 50.0
# Out of the front-face tap along its axis (block -Z): far enough that the
# screw stands clear below the block's front face in the octant view, with a
# trail from its cup back to the tap's mouth the reader can follow.
ROD_SET_SCREW_OUT = 55.0
# Back along the marker's own axis (block +X), 36 on each of X and -Z.
MARKER_BACK = 36.0 * math.sqrt(2.0)
# The thumb screw's tip rests on the marker grip's underside, inside the
# stirrup window; down its tap axis (block -Y) it clears the bottom rail's
# underside by THUMB_SCREW_TRAIL_GAP, the length of its trail to the tap.
THUMB_SCREW_TRAIL_GAP = 10.0
THUMB_SCREW_DOWN = (
    carriage.MARKER_BOTTOM_LOCAL_Y - carriage.FRAME_ORIGIN_LOCAL[1]
) + THUMB_SCREW_TRAIL_GAP
# Off the neck along the slide-on axis (block -X): the stirrup's rod-side face
# clears the paper-end face by STIRRUP_CLEAR, the length of its trail.
STIRRUP_CLEAR = 32.0
STIRRUP_OFF = carriage.FRAME_ORIGIN_LOCAL[0] + STIRRUP_CLEAR

_WITHDRAWAL_STEPS: tuple[TranslationStep, ...] = (
    TranslationStep("hanger jam nut off", (HANGER_JAM_NUT,), "z", -26.0),
    TranslationStep("hanger nut off", (HANGER_NUT,), "z", -14.0),
    TranslationStep("hanger screw out behind", (HANGER_SCREW,), "z", 22.0),
    # Up off the eye, then an equal +X/-Z pair: straight to the reader's left
    # in the REAR-TOP-LEFT view, clear of the rod and stud.
    # Left in place, its run read through hanger nut 13 (machinist review r3);
    # lifted 60 instead, its balloons crossed the sheet's top border and its
    # leader lay on the stud's ray and crossed balloon 8's.
    TranslationStep("wire off the stud eye", (WIRE,), "y", 26.0),
    TranslationStep("wire aside x", (WIRE,), "x", WIRE_ASIDE),
    TranslationStep("wire aside z", (WIRE,), "z", -WIRE_ASIDE),
    TranslationStep("rod out of the guides", (ROD, STUD, STUD_NUT, *_CARRIAGE), "z", -48.0),
    TranslationStep("stud out of the rod", (STUD, STUD_NUT), "y", 12.0),
    TranslationStep("jam nut off the stud", (STUD,), "y", 10.0),
    TranslationStep("carriage off the pivot", _CARRIAGE, "y", -24.0),
    *_along("rod set screw out", (ROD_SET_SCREW,), _negated(BLOCK_Z), ROD_SET_SCREW_OUT),
    *_along("marker back", (MARKER,), BLOCK_X, MARKER_BACK),
    *_along("thumb screw down", (THUMB_SCREW,), _negated(BLOCK_Y), THUMB_SCREW_DOWN),
    # The withdrawn thumb screw stays on the stirrup's tap axis during slide-off.
    *_along("stirrup off", (FRAME, THUMB_SCREW), _negated(BLOCK_X), STIRRUP_OFF),
)

# The axis passes through the detached window, not through the world origin
# or each part's own origin. The +90-degree Y turn makes the formerly edge-on
# window face the exploded octant while keeping the screw vertical/on its tap.
_pivot = carriage.block_to_machine(
    (
        carriage.FRAME_X_CENTER_LOCAL,
        carriage.FRAME_ORIGIN_LOCAL[1] + frame.OUTER_HEIGHT / 2.0,
        v_block.DEPTH_MID_Z,
    )
)
for _step in _WITHDRAWAL_STEPS:
    if FRAME in _step.stems:
        _pivot = _step.transform.point(_pivot)
STIRRUP_TURN = RotationStep(
    "stirrup window turns", (FRAME, THUMB_SCREW), "y", math.pi / 2.0, _pivot
)
EXPLODE_STEPS: tuple[ExplodeStep, ...] = (*_WITHDRAWAL_STEPS, STIRRUP_TURN)


# --- contract asserts ---------------------------------------------------------
assert {stem for step in EXPLODE_STEPS for stem in step.stems} == set(
    BOM_ORDER
) - {HANGER}, "every family but the ground hanger moves in the explode"
assert all(step.axis in "xyz" and step.distance_mm != 0.0 for step in _WITHDRAWAL_STEPS)
assert len({step.label for step in EXPLODE_STEPS}) == len(EXPLODE_STEPS)
assert THUMB_SCREW_DOWN > 0.0 and STIRRUP_CLEAR > 0.0

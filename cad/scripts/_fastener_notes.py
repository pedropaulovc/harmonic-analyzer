r"""Pure-data manufacturing-note builders for made fasteners.

The title block owns units, material, finish, surface texture and the blanket
tolerances; a tighter band rides the model dimension in the build script; the
thread designation is a leader on the shank (``_fastener_annotations``).
These helpers return only the few part-specific facts a machinist cannot
read off the views (cad/docs/drawing-simplicity-policy.md rule 6): how far
the thread runs, where a slot sits, what a reeded grip is -- never a size,
which belongs on a dimension.  They deliberately have no SolidWorks imports
so part builders and drawing recipes share the exact same product definition.
"""

from __future__ import annotations

import re


_TPI_RE = re.compile(r"-(?P<tpi>[1-9][0-9]*)$")


def _thread_pitch_mm(thread: str) -> float:
    match = _TPI_RE.search(thread)
    if match is None:
        raise ValueError(f"unrecognized Unified thread designation: {thread!r}")
    return 25.4 / int(match.group("tpi"))


def thread_length_note(
    *,
    thread: str,
    underhead_length_mm: float,
    head_name: str = "HEAD",
) -> tuple[str, ...]:
    """Return the thread-extent line for a shank threaded up to its head.

    The designation itself is leadered to the shank on the view, and every
    sheet dimensions its under-head length, so the line carries neither;
    ``underhead_length_mm`` only feeds the full-form sanity check.
    """
    pitch = _thread_pitch_mm(thread)
    if underhead_length_mm - 4.0 * pitch <= 0.0:
        raise ValueError(
            f"{thread} length {underhead_length_mm:g} leaves no full-form "
            "thread after two-pitch runout at each end"
        )
    return (f"THREADED TO THE {head_name}; LAST 2 PITCHES MAY BE INCOMPLETE.",)


def slotted_head_notes() -> tuple[str, ...]:
    """Return the driver-slot line for a slotted cylindrical head.

    The slot width and depth are dimensions on the slot-profile view; the
    one fact the views only imply is that the slot is centred on the axis.
    """
    return ("SLOT CENTERED ON THE HEAD AXIS, FULL WIDTH OF HEAD.",)


def square_head_notes(*, point: str) -> tuple[str, ...]:
    """Return the head-style line for a square-head set screw.

    The across-flats and height ride the sheet's dimensions; only the head
    form and the point form need saying.
    """
    return (f"SQUARE HEAD; {point} POINT.",)


def reeded_head_notes(
    *, head_name: str, groove_count: int, groove_dia_mm: float = 1.0
) -> tuple[str, ...]:
    """Return the reeding lines for a knurled thumb head.

    The head diameter and length ride the sheet's dimensions.  The grooves
    are a ball-nose cut centred on the OD (``_features.add_reeded_head_and_
    thread``), so radius and depth are both half the cutter diameter; they
    are a grip, not a gauged size -- the second line says so, because the
    title block's .XX band would otherwise put a negative lower limit on
    a 0.50 groove.
    """
    half = groove_dia_mm / 2.0
    return (
        f"{head_name} REEDED: {groove_count}X EQUALLY SPACED AXIAL GROOVES, "
        f"R{half:.2f} BALL NOSE {half:.2f} DEEP.",
        "GROOVES ARE A GRIP; RADIUS AND DEPTH NOT GAUGED.",
    )

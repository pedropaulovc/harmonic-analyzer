"""Shared surface-finish grades for released drawing callouts.

PURE DATA, no SolidWorks/COM imports — the sibling of :mod:`_fit_deviations`, and
importable from BOTH the part tier and the drawing tier without tripping
``check:partiso``.

Every ``add_surface_finish(roughness_ra=...)`` callout must name a grade here
rather than typing a number.  A literal in a drawing script is a defect for the
same reason a literal fit limit is: the roughness a part is machined to is
product definition that belongs beside the nominal it qualifies, not beside the
sheet coordinate that positions its leader.  Before this module the fleet
carried 42 such literals across 39 sheets — expressing a **two-value**
vocabulary.

.. warning::

   **The number is unit-bearing and the symbol text is FROZEN.**
   ``_drawing_finish.add_surface_finish`` writes ``Ra <value>`` into the symbol
   via ``SetText``; SolidWorks never re-renders it when the document's unit
   system changes.  These values are **micrometres** (the ISO/metric
   convention).  Under inch (ips) display the machinist convention is
   **microinches** — ``Ra 1.6`` on an inch print reads as 1.6 µin, a ~40x finer
   surface than intended and one no shop process produces.

   The title block carries no roughness number at all (its surface row is the
   process statement ``CAST/MACHINED``), so these callouts are the
   ONLY roughness ink on a sheet.  Issue #290 converts packages to inch
   display in batches, so the grade stays a physical micrometre value and
   :func:`ra` renders it per sheet: ``unit="mm"`` prints micrometres exactly as
   before, ``unit="in"`` prints the project grade's preferred microinch value
   (``1.6`` -> ``63``, ``0.8`` -> ``32``, ``3.2`` -> ``125``).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal

from _gtol_face import FaceSpec
from _gtol_identity import pmi_annotation_name

# Roughness average (Ra) in MICROMETRES.
#
# GROUND — a ground or lapped bearing/register surface: a pivot-screw shoulder
# running in its bore, a knife-edge ridge, a ball seat.  The finest grade the
# project specifies.
GROUND_UM = 0.8
# MACHINED — the general turned/milled finish for a located or bearing surface
# that is not ground: reamed bores, gear seats, journal diameters, register
# faces.  The project's default whenever a running surface is called out.
MACHINED_UM = 1.6
# SEAT — a static mating face that locates the part against its neighbour: a
# pedestal foot on the base, a bolted register.  Nothing runs on it, so the
# commercial machine finish is enough; it is called out at all only because
# the title block names no grade ("CAST/MACHINED"), so a seat that MUST be cut
# on a part that may otherwise be left as-cast has to say so on the face.
SEAT_UM = 3.2

# A drawing's display unit, as the package's ``drawing_unit`` selects it.
DisplayUnit = Literal["mm", "in"]
DISPLAY_UNITS: tuple[DisplayUnit, ...] = ("mm", "in")

# The project grades' ISO 1302 / ASME Y14.36 preferred microinch values.  An
# inch print takes these rounded preferred values, never the arithmetic
# conversion (0.8 um is 31.5 uin and 3.2 um is 126.0 uin, yet the series
# prints 32 and 125).  A new grade must add its preferred value here.
_PREFERRED_RA_UIN: tuple[tuple[float, int], ...] = (
    (GROUND_UM, 32),
    (MACHINED_UM, 63),
    (SEAT_UM, 125),
)


def ra(grade_um: float, *, unit: DisplayUnit = "mm") -> str:
    """Render a grade as the ``roughness_ra`` string a drawing callout takes.

    ``grade_um`` is always the physical Ra in micrometres; ``unit`` is the
    sheet's display unit.  ``"mm"`` prints one decimal, matching the ISO
    preferred-series spelling (``0.8``, ``1.6``) that every shipped sheet
    already prints — so adopting this module is a pure refactor with no ink
    change.  ``"in"`` prints the preferred microinch value of a project grade
    and refuses any other grade rather than ink a non-standard number.
    """
    if unit not in DISPLAY_UNITS:
        raise ValueError(
            f"surface roughness display unit must be 'mm' or 'in', got {unit!r}"
        )
    if not math.isfinite(grade_um) or grade_um <= 0.0:
        raise ValueError(f"surface roughness must be positive and finite: {grade_um!r}")
    if unit == "mm":
        return f"{grade_um:.1f}"
    for preferred_um, preferred_uin in _PREFERRED_RA_UIN:
        if math.isclose(grade_um, preferred_um, rel_tol=1e-9):
            return str(preferred_uin)
    raise ValueError(
        f"surface roughness {grade_um!r} um has no preferred microinch grade"
    )


# The strings the sheets pass. Derived, never typed: a grade retune moves the
# printed callout with it.
GROUND = ra(GROUND_UM)
MACHINED = ra(MACHINED_UM)
SEAT = ra(SEAT_UM)
# The same grades as an inch sheet prints them (microinches).
GROUND_INCH = ra(GROUND_UM, unit="in")
MACHINED_INCH = ra(MACHINED_UM, unit="in")
SEAT_INCH = ra(SEAT_UM, unit="in")


@dataclass(frozen=True)
class SurfaceFinishControl:
    """Part-owned surface requirement qualified by one exact model face.

    ``native_attachment`` controls only how the native symbol is stored in the
    ``.SLDPRT``.  Most parts attach it directly to the qualified face.  A
    configuration-driven part whose topology changes between configurations
    uses ``"model"`` so one configuration's transient face identity cannot
    make every other configuration rebuild with a dangling annotation.  The
    typed ``face`` remains mandatory and is still resolved live by the part
    build and used to place the drawing leader.

    ``roughness_um`` is the physical requirement and stays in micrometres;
    ``display_unit`` only selects how :attr:`roughness_ra` renders it.
    """

    key: str
    roughness_um: float
    face: FaceSpec
    production_method: str = ""
    native_attachment: Literal["face", "model"] = "face"
    display_unit: DisplayUnit = "mm"

    def __post_init__(self) -> None:
        if not self.key:
            raise ValueError("surface-finish key cannot be blank")
        if self.display_unit not in DISPLAY_UNITS:
            raise ValueError(
                "surface-finish display_unit must be 'mm' or 'in', "
                f"got {self.display_unit!r}"
            )
        ra(self.roughness_um, unit=self.display_unit)
        if self.native_attachment not in {"face", "model"}:
            raise ValueError(
                "surface-finish native_attachment must be 'face' or 'model', "
                f"got {self.native_attachment!r}"
            )

    @property
    def roughness_ra(self) -> str:
        return ra(self.roughness_um, unit=self.display_unit)

    @property
    def annotation_name(self) -> str:
        return pmi_annotation_name(f"surface:{self.key}")


def surface_finish_by_key(
    controls: tuple[SurfaceFinishControl, ...], key: str
) -> SurfaceFinishControl:
    """Resolve one stable surface-finish row by semantic key."""
    matches = [control for control in controls if control.key == key]
    if len(matches) != 1:
        raise ValueError(f"surface-finish key {key!r} resolved {len(matches)} controls")
    return matches[0]

"""Shared surface-finish grades for released drawing callouts.

PURE DATA, no SolidWorks/COM imports — the sibling of :mod:`_fit_limits`, and
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
   ``_drawing_common.add_surface_finish`` writes ``Ra <value>`` into the symbol
   via ``SetText``; SolidWorks never re-renders it when the document's unit
   system changes.  These values are **micrometres** (the ISO/metric
   convention).  Under inch (ips) display the machinist convention is
   **microinches** — ``Ra 1.6`` on an inch print reads as 1.6 µin, a ~40x finer
   surface than intended and one no shop process produces.

   The repo already holds both conventions: ``cad/config/title_block.yaml``
   carries ``value_uin: 125`` alongside the display string ``Ra 3.2``.  Nothing
   reconciles them today.  When issue #290 flips the generated drawings to inch
   display, this module is the ONE place that has to grow a µin rendering —
   which is the whole point of collapsing the literals here first.
"""

from __future__ import annotations

# Roughness average (Ra) in MICROMETRES.
#
# GROUND — a ground or lapped bearing/register surface: a pivot-screw shoulder
# running in its bore, a knife-edge ridge, a ball seat.  The finest grade the
# project specifies.
GROUND_UM = 0.8
# MACHINED — the general turned/milled finish for a located or bearing surface
# that is not ground: reamed bores, gear seats, journal diameters, register
# faces.  The project's default whenever a surface is called out at all.
MACHINED_UM = 1.6


def ra(grade_um: float) -> str:
    """Render a grade as the ``roughness_ra`` string a drawing callout takes.

    One decimal, matching the ISO preferred-series spelling (``0.8``, ``1.6``)
    that every shipped sheet already prints — so adopting this module is a pure
    refactor with no ink change.
    """
    if grade_um <= 0.0:
        raise ValueError(f"surface roughness must be positive: {grade_um!r}")
    return f"{grade_um:.1f}"


# The two strings the sheets pass. Derived, never typed: a grade retune moves
# the printed callout with it.
GROUND = ra(GROUND_UM)
MACHINED = ra(MACHINED_UM)

r"""Geometry-only contract for the pinion-handle retention pin."""

from __future__ import annotations

# AISI 1018 cold-finished stock is the registry material for this part.  The
# stock is a simple straight cylinder, with flat ends, local +Z from z=0 to
# PIN_LEN.  The match-reamed assembly hole establishes the functional fit; no
# independent fit band belongs on this pin.
PIN_DIA = 2.0
PIN_LEN = 10.5

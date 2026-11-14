"""Allowed-interference contract for the keyed cutting arbor kit (MHA-DT-03-TL-05).

Its builder runs no interference gate; its reopened soundness gate reads this
empty table, so every overlap in the kit fails: the key bears line to line on
its keyseat, the nut's plain major bore on the arbor's schematic thread, the
collars stand clear of the pilot and of each other.
"""

from __future__ import annotations

from collections.abc import Mapping

# No intended interference fit: every overlap in this fixture is a defect.
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {}

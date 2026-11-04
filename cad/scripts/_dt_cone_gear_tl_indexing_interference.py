"""Allowed-interference contract for the cone-gear indexing fixture.

Its builder runs no interference gate; its reopened soundness gate reads this
empty table, so every overlap in the fixture fails (it has no intended fit).
"""

from __future__ import annotations

from collections.abc import Mapping

# No intended interference fit: every overlap in this fixture is a defect.
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {}

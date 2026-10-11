"""Assembly component fingerprints for simplified-configuration refreshes.

Kept separate from naming and part derivation so changes to assembly refresh
identity do not re-key part recipes or load part-saving machinery in drawings.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable


def components_identity(rows: Iterable[tuple[str, str, str]]) -> str:
    """Order-free fingerprint of an assembly's simplified components.

    One row per top-level component: its name, the configuration it references
    in ``Default Simplified`` and that configuration's own comment.
    """
    digest = hashlib.sha256(repr(sorted(rows)).encode("utf-8")).hexdigest()
    return f"components {digest[:16]}"

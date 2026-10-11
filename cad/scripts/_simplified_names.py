"""Pure simplified-configuration naming shared across part and drawing tiers.

Naming stays separate so drawing and assembly recipes do not fold part
configuration derivation or saving machinery into their cache keys.
"""

from __future__ import annotations

SIMPLIFIED_SUFFIX = " Simplified"
SIMPLIFIED_COMMENT = "drawing views: modeled gear teeth and screw threads suppressed"


def simplified_name(configuration: str) -> str:
    """The derived drawing configuration of ``configuration``."""
    if is_simplified(configuration):
        raise ValueError(f"{configuration!r} is already a simplified configuration")
    return configuration + SIMPLIFIED_SUFFIX


def is_simplified(configuration: str) -> bool:
    return configuration.endswith(SIMPLIFIED_SUFFIX)


def simplified_comment(identity: str) -> str:
    """A derived configuration's comment: the policy plus what it suppresses."""
    return f"{SIMPLIFIED_COMMENT} [{identity}]"

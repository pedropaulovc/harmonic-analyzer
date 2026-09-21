r"""Geometry-only contract for the separate MHA-058 pinion grip crossrod."""

from __future__ import annotations

# Preserve the released crossrod geometry and its local origin.  The installed
# rod axis passes through the component origin and spans local Y -32..+33; the
# integral head and cross-hole now belong to MHA-102.
ROD_DIA = 6.0175
ROD_DOWN = 32.0
ROD_UP = 33.0
ROD_SPAN = ROD_DOWN + ROD_UP

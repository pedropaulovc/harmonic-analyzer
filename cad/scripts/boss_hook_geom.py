r"""Boss-hook geometry nominals -- the prose-free import surface for assemblies.

``build_summing_assembly`` needs the hook's rod diameter and elbow geometry to
place the counter-spring chain, but importing ``build_boss_hook`` for them
folded the whole part build -- including ``boss_hook_spec``'s DRAWING_NOTES
prose -- into the summing assembly recipe (codex #361, same closure leak the
channel batch fixed with its ``<part>_notes`` split): a text-only note edit
escalated to a full COM re-insert of the assembly.  Assemblies import THIS
module; ``build_boss_hook`` re-imports the same constants so the two can never
drift.
"""

from __future__ import annotations

ROD_DIA = 3.0  # DIMENSIONS.md ch18: hook rod (low)
SHANK_RISE = 12.0  # straight rise before the elbow (derived)
ELBOW_R = 3.0  # centreline bend radius (low)

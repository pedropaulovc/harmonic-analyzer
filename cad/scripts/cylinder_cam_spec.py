r"""Cam-lobe throw shared by the cylinder gear and the channel assembly.

PURE DATA: this one scalar lives in a leaf module (no gear imports) so the
channel assembly's recipe stays free of the gear helper closure. The doit
recipe follows imports transitively (``_buildgraph.module_deps_of``, honored
by ``_recipe_files`` in dodo.py), so ``build_channel_assembly`` importing the
throw straight from ``build_cylinder_gear`` dragged ``_gear`` /
``build_cone_gear`` / ``machine/gear_train.yaml`` into channel's recipe --
and every gear-geometry edit forced a ~500-950 s FULL channel re-mate even
though channel contains no gears. Both importers now share this leaf, so a
throw rescale still rebuilds both (imported, NOT copied), while a
tooth-profile edit leaves channel cached.
"""

from __future__ import annotations


ECCENTRICITY = 8.64  # DIMENSIONS.md ch13: cam throw MEASURED from the ch14 end-view ROM
# fit (2026-07-02): tip half-amplitude 9.458 mm over the 20-tip least-squares cos fit at
# the channel-pitch scale, x r_pin/r_tipface = 127.37/139.5. Supersedes the scaled-0.6022
# legacy 3.06 (the lobe also flips to +Y -- see build_cylinder_gear's module
# docstring). (med)

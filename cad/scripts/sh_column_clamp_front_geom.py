r"""Column-clamp-front nominal bore and ear geometry.

PURE DATA, no SolidWorks/COM and no drawing imports. Kept separate from
``sh_column_clamp_front_spec`` so the fit checks and hole contract do not
depend on drawing notes or marked-dimension maps.

The shared builder and drawings consume the exact part-owned hole contract
below; the shared bar and seating depths live in ``_column_clamp_interface``.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm

# --- Nominal geometry (book ch. 21/22, ch30 p005; layout memory/paper-drive-
# rework.md E2), each the exact millimetres of its printed .XXX inch value. ---
ARC_WIDTH = 48.006  # 1.890: lateral span, ear tip to ear tip
ARC_HEIGHT = 16.002  # .630: along the column (2 * _clamp_arc.ARC_HALF_H)
COLUMN_BORE = 25.6032  # 1.008: half-cylinder relief, slides on the Ø1.000 column
EAR_HOLE_Z = 17.5006  # .689: ear screw line flanks the column
EAR_HOLE_SPEC = HoleSpec("clearance", "#8")
EAR_HOLE_DIA = blind_cut_dia_mm(EAR_HOLE_SPEC)

# Derived spans (equations of the primitives above).
EAR_SPACING = 2.0 * EAR_HOLE_Z  # 1.378: ear-hole centre to centre
BORE_RADIUS = COLUMN_BORE / 2.0  # .504

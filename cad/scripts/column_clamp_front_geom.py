r"""Column-clamp-front nominal geometry -- the drawing-FREE constant block shared
by the part build, its ``_spec`` (drawing contract) and the two assemblies that
anchor off the clamp depth (``build_magnifier_assembly`` /
``build_paper_drive_assembly``).

PURE DATA, no SolidWorks/COM and no drawing imports.  Kept SEPARATE from
``column_clamp_front_spec`` on purpose: the assemblies depend (via
``_buildgraph.module_deps_of``) on whatever module they import a constant from,
so the drawing contract (notes/marked-dimension map) must NOT live here -- else a
print-note edit would move the assemblies' recipe digest and force a needless
full rebuild.  ``_spec`` re-exports these for its drawing-side consumers and adds
only the drawing data.

The shared builder and drawings consume the exact part-owned hole contract
below; only the arc-envelope constants mirror ``_clamp_arc``.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, blind_cut_dia_mm

# --- Nominal geometry (book ch. 21/22, ch30 p005; layout memory/paper-drive-
# rework.md E2). ---
ARC_DEPTH = 17.9  # bar back face to the column-axis plane
ARC_WIDTH = 48.0  # lateral span, ear tip to ear tip
ARC_HEIGHT = 16.0  # along the column (2 * _clamp_arc.ARC_HALF_H)
COLUMN_BORE = 25.6  # half-cylinder relief: slides on the O25.4 column
EAR_HOLE_Z = 17.5  # ear screw line flanks the column
EAR_HOLE_SPEC = HoleSpec("clearance", "#8")
EAR_HOLE_DIA = blind_cut_dia_mm(EAR_HOLE_SPEC)

# Derived spans (equations of the primitives above).
EAR_SPACING = 2.0 * EAR_HOLE_Z  # 35.0: ear-hole centre to centre
BORE_RADIUS = COLUMN_BORE / 2.0  # 12.8

# Diagnostics archive

One-off investigation scripts (`probe_*`, `diag_*`, `poc_*`, `fix_*`) kept for
their hard-won findings, moved here to declutter `cad/scripts/`. They are **not**
part of the build (`doit`/`dodo.py` ignores this directory) and are not maintained.

Exception: [`collect_dt_swing_gravity.py`](collect_dt_swing_gravity.py) is a
maintained, COM-free calibration collector; its pure regressions run in
`check:recipe`. See [the method and command](../../../DEVELOPING.md#swing-cluster-gravity-calibration).

The stock-form studies are also maintained pure engineering tools:
`crossed_mesh_study.py` supplies actual source-owned material geometry,
`stock_form_contact_3d.py` bounds finite screw-swept surfaces on explicit 3D
axes, and `crank_mesh_backlash_study.py` enumerates the crank manufacturing
cases. They import no native CAD, COM or CadQuery. Their **STOCK-FORM
COVERAGE** counts distinct continuously supported first/paid carrying teeth,
not every stationary root or an ideal involute contact ratio. Continuous
carrying, real driven-pitch handover, positive backlash, finite normal contact
and actual supported row are separate gates.
Run functional design studies only against complete source-owned profiles,
write their JSON outside the checkout, and retain numerical error payments
and every required manufactured case. A sampled point cloud is not a native
certificate. Native recipes consume only pure geometry/configuration and
the frozen, source-identified qualified calibration through
`crank_mesh_stack.require_qualified()`; an incomplete or geometrically
refused study must remain an explicit publication refusal, never old fitted
constants or a zero-error fallback.
The physical geometry identity includes the actual profiles, source pose
domains and pure geometry/core bytes. A separate measurement-engine manifest
pins the collector, 3D engine, adapter, both root helpers and continuous
common-normal proof helper at collection (six sources).
Central publication compares that manifest with the deployed implementation;
native consumers check its integrity without importing or reading diagnostics.
Every counted branch retains a genuine finite common-normal contact proof.
Root arcs and root junctions remain noncarrying, including when a neighbouring
radial working segment lies between the true root minimum and maximum.
The surface search separates its lower-envelope model from guaranteed
physical witnesses. Expanded pose domains bound possible contact; eroded
domains admit witnesses that survive every paid displacement. Their gap is
irreducible manufacturing uncertainty, not a subdivision target. Each phase
row retains both extremum edges, the relaxed incumbent, achieved numerical
residual and terminal-leaf minima/counts, separately from the requested
numerical tolerance. An unresolved achieved residual cannot qualify a
window or loaded solve.
An empty robust witness domain is not proof that the physical pair cannot
mesh. End-cap culling refines exact-perimeter chord bounds rather than
retaining a fixed polygon-error strip as fictitious material.
The finite working inverse records the real native radial/flank parameter
domains. Its endpoint slope bound evaluates those parameters directly, never
roots a rounded endpoint radius. Interior inverse queries use true brackets;
an endpoint discrepancy is accepted only inside a separately booked
floating-point radius allowance, paid into the angular enclosure. Larger
support gaps refuse, and projected endpoints disable the Taylor shortcut.
The table retains its original material-tooth angular frame.

The maintained `stock_form_contact_continuation.py` interval adapter follows
actual finite NativeSegment/physical screw equations, including Placement
shoulder and turned-cylinder cut-law edges. Closed phase/source cells use
parametric common-normal/KKT charts with strict finite support, actual normal
cones and root-free INNER components; point reserves do not prove persistence.
Stored frames are not assumed exact isometries: integration must use the
bounded true inverse, inverse-transpose local-mm constraint covectors, and
each body's positive determinant and actual cap radius in cone multipliers.
Complete physical competitors, root/floor/cap interiors, genuinely free
reference air, full two-coordinate constrained minima and signed whole-approach
transversality are separate first-contact requirements. Numeric minimum,
boundary and outside-union bounds bind the same cell, chart neighbourhoods
and complete approach. Material beta*=physical beta+body-fixed driven clock
removes that geometric clock column exactly while retaining physical roots
and uncertainty; disconnected components remain separately mapped.
Handovers and retained near-first teeth pay recomputable SAME-source root
differences and actual geometry error, not independent-source sums or declared
zero jumps. Supported row uses continuous same-contact INNER station images;
an OUTER root-box width or a jump between teeth is not a traversed row.
Unresolved modes, manufacturing families or periodic source-relabel seams
remain explicit refusal, never physical infeasibility or native success.
The permanent sixth measurement source is authenticated when continuation
is actually collected; stationary-only DESIGN is not a production certificate.

The retained physical crank phase has one configuration cell,
`gear_train.crank_mesh_phase_offset_deg`. Until qualified it is null.
The shaft builder requests the retention-hole angle only after the current
calibration and that cell agree; no ideal-profile phase alias is retained.

They still import shared helpers with bare `from _common import ...` /
`from _chain import ...`; the `_common.py` / `_chain.py` shims in this directory
re-export the real modules one level up so the scripts keep running:

```
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_motion.py
```

Reusable knowledge from the archived investigations has been distilled into the
build scripts, `cad/DIMENSIONS.md`, and project memory; treat those as historical.

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
Collectors compile their captured entry bytes using explicit runtime bindings.
The continuation module is imported explicitly, so the undefined-name gate
also covers the entry shims and continuation type annotations.
The physical geometry identity includes the actual profiles, source pose
domains and pure geometry/core bytes. A separate measurement-engine manifest
pins the collector, 3D engine, adapter, both root helpers and continuous
common-normal proof helper at collection (six sources).
Central publication compares that manifest with the deployed implementation;
native consumers check its integrity without importing or reading diagnostics.
Every counted branch retains a genuine finite common-normal contact proof.
Root arcs and root junctions remain noncarrying, including when a neighbouring
radial working segment lies between the true root minimum and maximum.
`stock_form_root_sweep.root_free_intervals` defaults to actual driver ROOT
material. Its explicit `root_only=False` selector reuses the same traversal
for complete cutter-gapped driver material; receipts and witnesses name that
different scope and retain every physical driven tooth and cap. A complete-
material query is not a root-MAX disk or a substitute for directed root
ownership. Accepted nearly orthogonal stored frames use precomputed true
inverses for containment and sampled world points, with directional clearance,
primitive-error and parameter-radius metric payments. A legacy point adapter's
transpose-local result cannot become root evidence. These are source-only
numerical enclosures, not evidence that manufactured stock has passed.
Known squared norms preserve the nonnegative domain of the complete sum,
including three uncertain components straddling zero. Eccentricity and frame
norms are accumulated as whole vectors rather than re-summing scalar norm
intervals. Generic square roots still reject genuinely negative domains;
neither an absolute value nor an arbitrary square-root clamp supplies proof.

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

Physical neighbourhoods retain each patch's own native coordinates: t/z on
sides and incidents, t/rho on finite face caps. A main-chart rectangle cannot
stand in for a differently parameterised incident or cap. Constrained minima,
one-sided boundary derivatives and complete outside-union surface receipts bind
these actual domains and branch root coordinates; missing or point domains refuse.

Periodic closure requires actual same-source centred eccentricity disks, an
all-stratum endpoint bijection, fresh endpoint/centre roots and an all-tooth/cap
material-root receipt. Driver and driven root-air floors remain separate.
Finite-pitch and rotation-product discrepancies are paid through the joint
`lcm(Ndriver,Ndriven)` tooth period, with geometry-plus-arc padding on the actual
minimum neighbourhoods. Rotated rectangle corners, sampled flags and proclaimed
zero jumps are not closure certificates. Handover proofs retain and exclude
every physical competitor, not just the two candidate roots.
The same explicitly supplied `additional_geometry_error_mm` is required on
first-contact covers, branch ordering/coverage and same-source handovers, not
only on the final seam/root receipts. The converter pays profile geometry and
joint-period displacement once; a dropped payment or a second TE payment is
not a valid replay. Endpoint square-root certificates compare exact dyadic
integer squares, so nonzero underflowing norm squares cannot trigger an
astronomical outward-rounded-product correction walk. Exact-zero identities,
finite ordered endpoints and genuinely negative-domain refusal are unchanged.

`stock_form_contact_certificate.py` is the pure shared native reader, not a
seventh measuring source. Its lower/upper labels refer to physical driven-angle
endpoints (closing senses -1/+1), not to inverse-offset window labels. Mechanical
cam-notch/cone-lock zeros must be supplied from their independent manufactured
datums; neither a loaded home value nor an arbitrary tooth clock is a TE tare.
Nonrigid face-width families must be covered as material-cap motion, not silently
relabelled as a rigid translation.

Cone native geometry remains below world placement: `cone_pitch.py` supplies
the part-local seat pitch, while `dt_cone_gear_spec.py` binds current geometry
sources/config, reconstructs every actual manufactured profile and replays the
authentic recorded ALL20/ALL17 certificates. Its drawing references are labelled
as recorded SOURCE receipts, not current installed-mesh authority. The explicit
`dt_cone_mesh_domain.require_qualified_stock_family` publication/assembly gate
and `stock_form_mesh_data` budget API additionally rebind every actual producer
config read, full pure-source byte identity, current continuous physical SOURCE
domain and world-positive placement on every call. A stale placement receipt
cannot qualify an installed mesh even when its native part geometry is unchanged.
Shared finite process-grade getters and their UNKNOWN exception live in the
existing narrow `_fit_limits.py` tier, so the drum's grade API does not pull
world placement into either native part recipe.

The retained physical crank phase has one configuration cell,
`gear_train.crank_mesh_phase_offset_deg`. Until qualified it is null.
The shaft builder requests the retention-hole angle only after the current
calibration and that cell agree; no ideal-profile phase alias is retained.

The crank collector calls `analyse_3d_mesh` with the required
`continuous_source_domain`, covering the nominal profile and all 16 profile
corners. There is no scalar pose-ball or sampled-window fallback. The actual
post, each journal's own clearance/contact span, both gear TIR disks, all
retained-band/face states and independent real tooth-clock sources belong to
that domain. An unbound lateral-origin or clock grade is UNKNOWN. Explicit
conditional DESIGN assumptions are captured inputs, never installed stock
acceptance or a publishable source qualification.

`crank_mesh_geometry.geometry_sha256()` is the pure physical INPUT identity.
It excludes diagnostic bytes, calibration JSON and the selected phase OUTPUT;
the exact six-source measuring manifest and before/compiled/after captures
remain separate. The collector must publish a real admitted
`calibration/dt-crank-stock-form.json` before the native build. A missing,
replaced, malformed or mutated packet refuses; neither a synthetic test
fixture nor a historical stationary result can fill it. Native readers bind
current physical bytes and parameters, while central publication also binds
the actual deployed measuring sources.

Selection keeps the raw unselected certificate identity. The selected driver
placement uses the native degree-valued datum arithmetic and has a separate
identity/transport receipt, actual effective clock displacement, same-q
mapping and proved disk-only joint-period relabelling. Fresh selected-placement
21-point face/root/first-contact queries are required. Their reference is a
separate declared nominal q0/profile/face/band query, not the midpoint of an
asymmetric manufacturing source. The full-source envelopes compare to that
same physical nominal scalar, and the whole-period signed cone-shaft lag
interval retains all source cells, numerical payment and seam authority.
`crank_drive_phase.require_qualified()` returns the actual admitted full packet;
native and budget callers require exact finite configuration/packet/provider
phase equality and frozen provider fields from those same packet bytes.

The recorded historical crank C+0.4/phase-zero stationary refusal used
500000 boxes and retained 0.849669 mm residual with unchanged source bytes.
It is not a numerical candidate qualification or evidence that physical
manufacture is impossible. Source APIs and static review readiness are
separate from a new source-captured design run and full native qualification.

They still import shared helpers with bare `from _common import ...` /
`from _chain import ...`; the `_common.py` / `_chain.py` shims in this directory
re-export the real modules one level up so the scripts keep running:

```
C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\diagnostics\probe_motion.py
```

Reusable knowledge from the archived investigations has been distilled into the
build scripts, `cad/DIMENSIONS.md`, and project memory; treat those as historical.

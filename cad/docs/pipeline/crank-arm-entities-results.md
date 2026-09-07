# Crank-arm entity selection validation

Work in progress. This document records the bounded migration requested in
`second-vm-crank-arm-entities.md`; it is not native acceptance or merge readiness.

## Frozen inputs and scope

- Root baseline: `bc593d784fba08fc6552224767a460338f51b664`.
- Adapter: `25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2`.
- Independent seed clone: `C:/src/ha-crank-arm-vm-seed`.
- Worktree: `C:/src/ha-crank-arm-semantic-entities`.
- Branch: `perf/crank-arm-semantic-entities`.
- Initial `git fetch origin main` found no commits in `HEAD..origin/main`.
- Own uv environment, CPython 3.14.5; no borrowed output, cache, DB or tokens.
- Attach-only SolidWorks PID 18748, revision 34.3.0. Initial locked native
  inventory was empty. Cache is disabled for native baseline production.

The part, spec, configuration, adapter and shared drawing helpers remain outside
this patch. Assembly PRs #676, #677 and #678 and their artifacts remain unchanged.

## Deliberate test conflicts reported before edits

`test_shaft_axis_datum_pick_is_radial_with_its_symbol` requires `DATUM_B_RIM`
radius/collinearity and literal coordinate selection. Three location tests require
`add_edge_dimension`; cross-hole station additionally requires `find_edge_near`
and its sheet-search axis. These implementation expectations conflict with the
requested migration. Their replacements must preserve the actual shaft-axis
datum, center-versus-tangent measurements, pivot/cross-hole BASIC assignments,
non-BASIC dimple transverse dimension, and all manufacturing requirements.

## Validation status

The unmodified part and drawing baselines must be retained before recipe edits.
Entity positive controls, production migration, cold attachment/render checks,
offline tests and review are pending. No performance improvement is claimed.

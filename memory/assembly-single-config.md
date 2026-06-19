---
name: assembly-single-config
description: "all assembly non-Default configurations (the engagement enum cone_disengaged/operating) were removed 2026-06-19 — assemblies carry only Default; PART-level multi-configs stay"
metadata:
  node_type: memory
  type: project
---

2026-06-19: user directive "remove all assembly non default configurations." The
drive-train and top harmonic-analyzer assemblies each carried an engagement enum
as assembly CONFIGURATIONS (`Default` / `cone_disengaged` / `operating`;
`pinion_engaged` was already retired with the alignment-pinion). All non-Default
ASSEMBLY configs are gone — every assembly now carries only `Default`.

What was removed (branch `remove-assembly-configs`):
- Deleted scripts: `build_engagement_configs.py` (cone_disengaged), `build_operating_config.py`
  (operating), `build_top_engagement_configs.py` (top child-refs), `reset_pose.py`
  (its job was snapping back from the crank-free `operating` pose).
- `_buildgraph.py`: `POST_ASSEMBLY` emptied (`{}`) — those three were the only
  post-assembly hooks; `dodo.py` docstrings de-referenced.
- `verify.py`: the whole `engagement` suite removed (`_verify_engagement`,
  `_open_isolated`, `Report.agate`, `TOP_OWNER`, the CLI `engagement` choice).
  Surviving suites: static / truth / config / isolation / motion / all.
- `cut_release.py`: discard-guard comments generalized (no longer cites the
  operating/pinion_engaged dirty-child case).
- `_gear_mate_names` (was imported from build_engagement_configs by
  `build_motion_setup_drives.py`) inlined into that file.

KEY distinctions:
- **PART-level multi-configs are KEPT** — cone-gear `T006..T120` (20) and
  transgear-removable `T12/T18/T24` (3) are distinct GEOMETRY the scene graph /
  release STLs reference simultaneously. Only ASSEMBLY engagement configs were the target.
- Drive-train grounding reverts to its NATIVE `fix_component` (build_harmonic_analyzer_assembly.py:99).
  The 3 principal-plane grounding mates existed ONLY to let `operating` go flexible
  at the top; with operating gone there is nothing to float, so no grounding
  conversion is needed.
- The `.SLDASM` artifacts are gitignored, so nothing committed needs regenerating;
  the next `doit` FULL build of drive_train + harmonic_analyzer produces
  single-Default assemblies. NOT YET SW-REBUILT on this seat.

Supersedes the dropped [[config-dirty-on-activate]] note (under-defined configs
dirtying the doc — moot now). Relates to [[professionalize-plan-status]] (F4
engagement suite removed), [[parametric-springs]] (its config-restore GOTCHA is
obsolete), [[od-62mm-reanchor]] (where pinion_engaged was first retired).

---
name: direct-script-build-stale-parts
description: Running a build_*.py assembly script directly uses whatever parts are on disk; stale parts fail mate-entity selection on named datums
metadata:
  type: feedback
---

Running an assembly `build_*.py` **directly** (e.g. `uv run python cad/scripts/build_frame_assembly.py`, to exercise a mate change live without the doit spine) uses whatever part `.SLDPRT` files are already on disk — it does NOT rebuild stale parts first. `doit assembly:<stem>` would, because parts are its `file_dep`.

**Symptom:** the assembly build fails at a mate with `Failed to select mate entity N (AXIS/PLANE at '<Datum>@<part>-1')` — e.g. `ScrewAxis@lag-screw-1`, `HoleAxis0@harmonic-base-1`, `RingTop@top-frame-1`, `Underside@nameplate-1`. Looks like a mate-code bug; it is actually a **stale part** on disk built before that named datum (`create_axis`/`create_plane` + `name_last_feature`) was added to the part's build script. A part can be *partially* stale (base had `DeckTop` but not `HoleAxis0..3`).

**Fix:** rebuild the offending part(s) directly (`build_harmonic_base.py`, `build_tube_frame.py`, `build_top_frame.py`, `build_lag_screw.py`, `build_nameplate.py` for the frame), confirming the datum feature is created (`create_axis <Name> OK` → `feature 'AxisN' -> '<Name>'`), then re-run the assembly. Iterate per referenced datum, or just rebuild all of the assembly's parts up front.

**To isolate "is this MY change or the environment?":** temporarily `git checkout <old-commit> -- <file>` in the submodule (e.g. revert `assembly.py` to the pre-migration AddMate5 version) and re-run — if the identical failure reproduces, the change is exonerated and it is a stale-part / env issue. This is how I confirmed the AddMate5→CreateMate migration did not cause the lag-screw failure.

**Verify freshness guard:** `verify.py --suite soundness <stem>` refuses a directly-built artefact with `STALE artefact, NOT verified ... changed since build` because the doit `.doit.db` ledger wasn't updated by the direct script. Bypass with `HARMONIC_VERIFY_ALLOW_STALE=1` when you know the artefact is genuinely fresh (you just built it). See [[single-assembly-fast-verify]].

**The INVERSE trap — direct build + script revert = permanently stale artefact
(v0.15.0 rocker-arm-support lug, 2026-07-05).** Direct-building a PART writes a
fresh artefact the ledger doesn't know about; if you then `git checkout --` the
script edit, the recorded digest MATCHES the reverted script again and doit
reads the task up-to-date FOREVER -- the out-of-band artefact (here: the
abandoned clamp-boss lug) ships through every "full" build. No CAD gate sees an
additive cosmetic change (no interference, DOF/pose clean); the RELEASE DIFF
render caught it (v0.15.0 shipped the lug; user's eye on diff_summary).
**Rule: after reverting a script whose part you built out-of-band, DELETE the
artefact** (SLDPRT+STL+PNGs, and its consuming .SLDASMs per
[[cache-partial-mix-dangle-remedy]]) so doit full-rebuilds. The remote cache is
NOT poisoned by this (a direct build never stores; the pre-edit clean artefact
stays cached under the unchanged recipe key), so a cache-on rebuild heals
instantly. Localize a suspect diff with vertex-nearest sampling on the two STLs
(added vs removed regions) -- see the v0.15.1 session.

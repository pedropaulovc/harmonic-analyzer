---
name: export-staleness-digest
description: Why the export task re-exported everything each release, and the digest-based fix + downstream mtime bridge
metadata:
  type: project
---

`export_models.py` (the `export` doit task, which runs `uptodate: [False]` and
self-checks) used to re-export ALL ~119 parts on every release. Two causes:

- **(A) dominant, deterministic:** `part_stl_stale` required a `<stem>.STEP` to
  exist, but referenced-only parts get NO per-part STEP — only *manifest* parts
  and assemblies do. Since `comparisons/manifest.json` now lists a single model
  (`harmonic_analyzer`, the top assembly), NO part is ever a manifest part, so
  every referenced part was stale forever regardless of mtimes.
- **(B) latent:** staleness compared source `.SLDPRT` mtime vs the exported STL
  mtime. SolidWorks' save-cascade and the remote-cache restore utime-bump
  (`_artifact_cache._restore` sets restored natives to `now`) advance source
  mtimes, so on cache-restore releases every part looked stale.

**Fix:** export staleness now keys on the SAME churn-immune recipe digest the rest
of the pipeline uses — `dodo._stable_artefact_digest` (see [[two-tier-submodule-digest]]),
imported the way `verify.py`'s freshness guard imports dodo. Per-output source
digests are recorded in `cad/out/stl/export-src.json`; a re-export fires iff an
output is missing/colour-uncached OR the source's recipe digest changed.
`manifest_part_stale` keeps the STEP requirement only for real manifest parts.

**Downstream bridge (don't remove):** `render_offline._stale` and
`cut_release` (SCENE_JSON vs top `.SLDASM`, a hard `SystemExit`) still assert
"render-cache output not older than source BY MTIME". A correct digest-based SKIP
would leave a fresh output looking older than a bumped source → false failure. So
after a successful export, `stamp_render_cache_current()` re-stamps all
STL/STEP/boxes outputs to `now` — a truthful post-condition ("cache is current"),
letting the mtime guards keep working unchanged. The `_artifact_cache` restore
utime-bump also stays (those same downstream guards rely on it).

First run after the change does one full export to populate `export-src.json`
(gitignored, not in the remote cache), then no-ops on unchanged recipes.

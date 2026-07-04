---
name: cache-partial-mix-dangle-remedy
description: Remote-cache partial mix (local part rebuild + foreign cached assembly) dangles mates; delete alone RE-RESTORES the broken artifact — rebuild with HARMONIC_CACHE_MODE=off
metadata:
  type: project
---

**Symptom** (fresh seat bootstrap, 2026-07-03): full `doit` fails at
`assembly:harmonic_analyzer`'s deep-health gate with mate errors `[48]`
(dangling) INSIDE cache-restored subassembly instances, e.g.
`summing-1:Coincident1; magnifier-1:Coincident2`.

**Cause** — the AGENTS.md "recipe ≠ PID identity" limitation, triggered by a
*partial cache mix*: some `part:*` MISSED (rebuilt locally → fresh SolidWorks
persistent IDs) while assemblies containing them HIT stale entries another
seat published (whose mates bind that seat's part PIDs). `summing` ⊃
summing-lever, `magnifier` ⊃ thumb-screw — exactly the hit assemblies holding
locally rebuilt parts dangled; `pen` (no rebuilt parts) stayed healthy.
Root cause (pinned in issue #149, 2026-07-03): a TWO-SEAT PUBLISH RACE, not a
lost store — the keys never disagreed; the blob's contents moved underneath a
multi-hour build. Seat A's parts phase missed (nothing published yet) and
rebuilt locally; seat B then published the same recipe state's parts AND
assemblies mid-window; seat A's assembly phase hit the just-published entries,
PID-incompatible with its own parts. Any two seats building overlapping recipe
states concurrently reproduce this. `doit cache_status` shows the mix plus
`DRIFT(last published …)` on the foreign entries.

**Why:** the obvious fix (delete the `.SLDASM`, re-run doit) silently
RE-RESTORES the same broken artifact — the cache key still hits; restore
doesn't know the entry is PID-incompatible with local parts.

**How to apply:**
1. Close SW docs first (a failed run leaves ~90 open; files are locked):
   `uv run python -c "import win32com.client; win32com.client.GetActiveObject('SldWorks.Application').CloseAllDocuments(True)"`
2. Delete each foreign `.SLDASM` + its `.<stem>.massprops.sha` /
   `.<stem>.recipe.md5` sidecars (and `.<stem>.park.json` if present).
3. Rebuild those assemblies with the cache OFF so the stale key can't restore:
   `$env:HARMONIC_CACHE_MODE='off'; uv run python -m doit assembly:<a> assembly:<b>`
   (mode=off also skips store — the foreign entries stay in the blob; a future
   fresh seat on the same recipe state can hit this again until someone
   republishes.)
4. Also delete the half-built DOWNSTREAM assembly the failed run left (its
   mates were created against the foreign copies — a refresh would reopen it
   and dangle again): delete its `.SLDASM` + sidecars → forces a clean FULL.
5. Resume the normal `doit -n 4` (default rw).

Related: [[solidworks-modeling-pitfalls]], the AGENTS.md incremental-rebuilds
section, and the `restore_hit_drift` WARN in `cad/out/reports/cache.jsonl`.

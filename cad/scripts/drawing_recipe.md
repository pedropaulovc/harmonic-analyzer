# Adding a curated manufacturing drawing (and fanning out agents to do it)

Every drawn part/assembly is a **slice** of coupled pieces. To add a new drawing,
clone the slice of the closest existing reference and adapt it. This file is both a
human how-to and the source of the **agent prompt template** at the bottom, so
fanning out N drawings later is fill-in-the-blanks.

## The slice — 6 pieces (part drawing)

| # | file | what it holds | reference (shaft / bushing) |
|---|------|---------------|------------------------------|
| 1 | `cad/scripts/<part>_spec.py` | pure data: nominal dims, `DRAWING_DIMENSIONS` (feature → marked-dim names), `DRAWING_NOTES`, optional `END_VIEW_NOTE` | `fulcrum_shaft_spec.py` / `lever_bushing_spec.py` |
| 2 | `cad/config/parts/<part>.yaml` | manufacturing metadata: `number` (keep the existing one), `material_specification`, `finish`, `quantity`, `tolerance_class`, `process` | `fulcrum-shaft.yaml` / `lever-bushing.yaml` |
| 3 | `cad/scripts/build_<part>.py` | import dims from the spec; at the end of `build()` (after `report_mass_properties`, before `save_part_and_images`): `clear_dimensions_for_drawing` → loop `mark_dimensions_for_drawing` over `DRAWING_DIMENSIONS` → `apply_drawing_properties(...)` | `build_fulcrum_shaft.py` |
| 4 | `cad/scripts/draw_<part>.py` | the recipe: `place_view` per view, `curate_view_dimensions` (its `keep` keys must equal the marked dims), callouts, GD&T, `add_property_linked_note`, `finalize_drawing` | `draw_fulcrum_shaft.py` |
| 5 | `cad/scripts/test_<part>_drawing.py` | offline pytest contract: output paths, spec-is-single-source-of-dims, `kept == marked`, annotation counts, config fields | `test_fulcrum_shaft_drawing.py` |
| 6 | `cad/scripts/_drawing_registry.py` | one `DrawingSpec(name=, part=, artifact_stem=, script_name=)` row | — |

Invariant the test pins: the spec module is the **single source** of the marked
dims (`build.DRAWING_DIMENSIONS is <part>_spec.DRAWING_DIMENSIONS`) and the draw
script keeps exactly that set (`FRONT_KEEP ∪ RIGHT_KEEP == marked`).

### If an ASSEMBLY imports any of the part's nominals, split them out (piece 1b)

`_buildgraph.module_deps_of` makes a task depend on **whatever module it imports a
constant from** — the whole module, not the constant. So the moment an assembly
imports one nominal from `<part>_spec.py`, that spec's *drawing* contract
(`DRAWING_NOTES`, `DRAWING_DIMENSIONS`) enters the assembly's recipe digest, and
editing a print note forces a full assembly rebuild that cannot change its
geometry. Minutes of COM seat, per note edit.

Fix, and the shipped precedent is `column_clamp_front`:

| file | holds | imported by |
|---|---|---|
| `<part>_geom.py` | pure nominals, **no drawing data** | the part build, the spec, **and the assemblies** |
| `<part>_spec.py` | re-exports the geom nominals, adds `DRAWING_DIMENSIONS` / `DRAWING_NOTES` | the part build + the draw script only |

`build_magnifier_assembly` / `build_paper_drive_assembly` anchor off the clamp
depth and import `column_clamp_front_geom` alone, so the assemblies never see the
drawing contract. Only do this when an assembly actually imports a nominal — for a
part nothing else consumes, one `<part>_spec.py` is right and the extra module is
dead weight.

## Pick the reference by shape

- turned shaft / pin / dowel → **`fulcrum_shaft`**
- turned bushing / sleeve / spacer (has a bore) → **`lever_bushing`**
- prismatic machined block / bracket / arm → **`crank_arm`** or **`top_crossbar`**
- (assembly drawing → see `drawing_recipe_assembly.md` once the assembly infra lands)

## Build + iterate (SolidWorks open; COM serialized on the machine-global seat)

```
uv run python -m doit part:<part>       # rebuild the part with marks + props (COM task, takes the seat)
uv run python -m doit drawing:<part>    # build the drawing (COM task) -> cad/out/png/<artifact-stem>_drawing.png
# LOOK at the PNG (Read the image), adjust coordinates in draw_<part>.py, re-run drawing:<part>. Repeat.
uv run python -m pytest cad/scripts/test_<part>_drawing.py -q
```

## Independent machinist review (codex)

Once the PNG looks correct and before committing, get an independent review: send
**only the image** (no part context, so the review is unbiased) to a machinist
persona via the codex CLI, using `gpt-5.6-sol` at high reasoning.

Three gotchas the command below works around: (1) codex's `-i` takes multiple
values and will **swallow a positional prompt** placed after it — pipe the prompt
on **stdin** instead; (2) run from a **neutral dir outside the repo** with
`--skip-git-repo-check` so codex does not read `AGENTS.md` and start exploring the
repo (which would make the review non-blind); (3) `cad/out/reports/` is gitignored
and a fresh worktree may not have it — a drawing task has no stamp target there —
so `mkdir -p` it or the `tee` fails and the gate leaves no review file behind.

Do NOT use `$TMPDIR` as the neutral dir. It is **unset on this machine**, and the
two ways that breaks are both silent-looking: bash rejects `cd ""` with "null
directory", so `cd "$TMPDIR" && codex …` short-circuits and codex NEVER RUNS while
`tee` still writes a plausible-looking review file containing only the shell error;
and in a POSIX `sh` that accepts `cd ""` as a no-op, codex instead runs **inside
the repo**, where `--skip-git-repo-check` only skips the safety check — it does not
stop codex reading `AGENTS.md`, so the review is no longer blind. `mktemp -d` has
neither failure mode, and `set -e` turns a missing temp dir into a loud stop.

**Do NOT add `--sandbox danger-full-access`, and do not "fix" the sandbox errors
in the transcript.** They are what makes this gate work. On this Windows seat the
default sandbox fails every shell command
(`orchestrator_helper_launch_failed: failed to launch setup helper`), so the
SessionStart hook's memory lookup cannot run and codex never reaches the
filesystem — the review is genuinely blind. `danger-full-access` (correct for a
codex task that must read/write, per `memory/codex-windows-sandbox.md`) would
un-break exactly the exploration this gate exists to prevent. Verified 2026-07-16
by running the real command on `pivot-shaft_drawing.png` under the default
sandbox: a complete machinist verdict came back, image-only, and volunteered
"without the other views, it resembles a rectangular bar" — a reviewer that had
read the repo could not have written that sentence.

So the tee'd transcript legitimately contains tool-call errors AND a real review.
That is the healthy state. The failure to watch for is the *absence* of a verdict.

```
mkdir -p "{WORKTREE}/cad/out/reports"
NEUTRAL=$(mktemp -d) || exit 1
( cd "$NEUTRAL" && echo "You are an experienced machinist. Review this manufacturing drawing for accuracy, clarity, and standards conformance. List any problems and say whether the part can be made as drawn." \
  | codex exec -m gpt-5.6-sol -c model_reasoning_effort="high" --skip-git-repo-check \
      -i "{WORKTREE}/cad/out/png/<artifact-stem>_drawing.png" ) \
  2>&1 | tee "{WORKTREE}/cad/out/reports/codex_machinist_review.txt"
rmdir "$NEUTRAL"
```

Then **read the review file before believing the gate ran.** A transcript with no
verdict in it — only a shell error, because the `cd` aborted the command — is the
failure to catch.

Naming the part is NOT a tell: the title block is in the image, so a blind
reviewer reads it there. The tell is a review citing something the drawing cannot
show — a repo file, a spec constant, the machine's design intent, a sibling part.

Address clearly valid accuracy/clarity/standards findings (bounded: 1–2 layout
iterations); leave repo-wide house-style/template items (title-block tolerance
block, edge-break note, general Ra, material short-name) for a follow-up across
the whole drawing set. Keep the review text for the record.

## Committing — stage explicit paths, never `git add -A`

`cad/out/` is only *partially* gitignored (its subdirs, not its root), so the
codex review file at `cad/out/reports/…` is safe but a stray `git add -A` can
still catch other root-level `cad/out` artifacts. Stage the slice files by name
and verify:

Mind the two spellings: the **script** stem is underscored (`draw_fulcrum_shaft.py`,
`doit part:fulcrum_shaft`) but the **config** file is dashed
(`cad/config/parts/fulcrum-shaft.yaml`, the `artifact_stem`). Feeding the
underscored stem to the config path either fails with a bad pathspec or — worse —
silently leaves the metadata change unstaged.

```
git status --short                    # FIRST: see everything you actually touched
git add cad/scripts/<part>_spec.py cad/scripts/draw_<part>.py cad/scripts/test_<part>_drawing.py \
        cad/scripts/build_<part>.py cad/scripts/_drawing_registry.py \
        cad/config/parts/<artifact-stem>.yaml          # dashed, NOT <part>
# AND, each only if you actually added/changed it:
git add cad/scripts/<part>_geom.py         # if you did the piece-1b split (NEW FILE -- easy to miss)
git add cad/scripts/_drawing_common.py     # if your draw script needed a shared helper
git commit -m "Add the <part> curated manufacturing drawing slice"
git show --stat HEAD    # confirm ONLY the intended files are in the commit
```

The two conditional adds are the ones that bite, and both fail the same way: a NEW or
CHANGED module that the committed files IMPORT, left out of the commit. The slice looks
complete, and the build dies in a fresh checkout on an import of something that is not in
the tree. `<part>_geom.py` is the sneakier of the two because it is untracked — `git status`
lists it under "Untracked files", not "Changes not staged", so it is easy to skim past.

**If your slice needed a shared helper, it MUST ride in the same commit.** Some
legitimately do — a revolve has no model edges on its flanks, so its GD&T needs
`entity_type="SILHOUETTE"` on `add_datum_feature`/`add_feature_control_frame`/
`add_surface_finish`. Committing the six slice files while leaving
`_drawing_common.py` dirty breaks the build for everyone: your draw script imports
a helper that is not in the tree. This is why the `git status --short` comes first
— the six-file list is a floor, not a ceiling. (Conversely: do not "tidy" a helper
you did not need. A shared-file edit is a merge point for every other open drawing
PR.)

## Slice-ready checklist (all four)

This is what makes a slice ready to hand to the lead — it is **not** the merge
gate. AGENTS.md owns that, and it is repo-wide: a full `uv run python -m doit -n 4`
green on the PR head, a clean Codex auto-review of the **latest** push, and an eye
pass over every touched render. These four checks are drawing-local and cannot see
a repo-wide regression, so clearing them is necessary and not sufficient.

1. `uv run python -m doit drawing:<part>` exits 0.
2. `uv run python -m pytest cad/scripts/test_<part>_drawing.py -q` passes.
3. The PNG is visually correct: views + dimensions + GD&T not overlapping each
   other or the title block; every key dimension present; title block populated.
   A build that passes checks can still *look* wrong — trust your eyes.
4. The codex machinist review ran and its clearly-valid findings were addressed.

## Fan-out (parallel agents)

Each agent gets its **own git worktree** (isolated `.doit.db`; the COM tasks
serialize on the machine-global seat lock — see `memory/com-seat-lock.md`). Two
`doit` invocations in the *same* worktree clobber each other's state, so never
share a worktree. Setup per worktree: `git worktree add -b draw-<part> <path> <base>`
then `git submodule update --init SolidworksMCP-python && uv sync`.

Instantiate this template once per part and spawn one agent each:

```
Create the manufacturing drawing slice for part **{PART}** by cloning the
**{REFERENCE_PART}** slice (cad/scripts/drawing_recipe.md lists the 6 pieces).
Work ONLY in worktree: {WORKTREE}. Invoke /developing-solidworks FIRST.

Geometry facts (from build_{PART}.py): {GEOMETRY_FACTS}
DRAWING_DIMENSIONS = {DIM_MAP}          # feature -> {marked dim names}
artifact_stem = {ARTIFACT_STEM}          # dashed; outputs land at cad/out/{slddrw,pdf,png}/{ARTIFACT_STEM}*

Do all 6 pieces, then BUILD + ITERATE (always via uv — bare doit/pytest may be missing
or a stale global install on a machine where only `uv sync` ran):
  uv run python -m doit part:{PART}  ->  uv run python -m doit drawing:{PART}
  ->  Read the PNG  ->  adjust  ->  repeat
  ->  uv run python -m pytest cad/scripts/test_{PART}_drawing.py -q
The seat is shared; "[com.seat] ... waiting for the SolidWorks seat" is EXPECTED — let it wait.
Run this whole build -> iterate -> review -> commit sequence to completion WITHIN your working
turns; do NOT end your turn between steps (e.g. after building the part, or while the seat is
busy) — wait for the seat and continue. Only stop and report when the slice is COMMITTED, or when
you hit a hard error you cannot resolve (paste the exact error). Going idle with the drawing
unbuilt just stalls the fan-out until the lead re-nudges you.
When the PNG looks right, run the independent machinist review (image only, no context;
pipe prompt on stdin so -i doesn't swallow it; run from a neutral dir with --skip-git-repo-check).
Use mktemp -d, NOT $TMPDIR — it is unset here, and `cd ""` either aborts the whole command
(codex never runs, tee writes only the shell error) or drops codex INSIDE the repo, where it
reads AGENTS.md and the review stops being blind. mkdir the report dir first or tee fails:
  mkdir -p "{WORKTREE}/cad/out/reports"
  NEUTRAL=$(mktemp -d) || exit 1
  ( cd "$NEUTRAL" && echo "You are an experienced machinist. Review this manufacturing drawing for accuracy, clarity, and standards conformance. List any problems and say whether the part can be made as drawn." | codex exec -m gpt-5.6-sol -c model_reasoning_effort="high" --skip-git-repo-check -i "{WORKTREE}/cad/out/png/{ARTIFACT_STEM}_drawing.png" ) 2>&1 | tee "{WORKTREE}/cad/out/reports/codex_machinist_review.txt"
  rmdir "$NEUTRAL"
  READ the review file back before trusting it. The failure is a transcript with NO verdict
  (only a shell error, because the cd aborted the command). Naming the part is NOT a tell --
  the title block is in the image. The tell is a review citing what the drawing cannot show:
  a repo file, a spec constant, design intent, a sibling part.
  Address clearly valid findings (1–2 iterations); leave repo-wide house-style items for a follow-up. Keep the review text, include it in your report.
Slice-ready (NOT the merge gate — AGENTS.md owns that, and it is repo-wide): drawing builds
clean + test passes + PNG visually correct + codex review addressed. The lead runs the full
`uv run python -m doit -n 4` and the Codex PR review; do not claim those.
No CadQuery. Stage explicit slice paths (NOT git add -A; the config file is DASHED,
cad/config/parts/{ARTIFACT_STEM}.yaml) and commit on branch draw-{PART}; do not push/PR.
Report SHA, files, PNG path, gate status, and the codex review verbatim.
```

Fill `{PART}` `{REFERENCE_PART}` `{WORKTREE}` `{GEOMETRY_FACTS}` `{DIM_MAP}`
`{ARTIFACT_STEM}` from the part's `build_<part>.py` (feature + dimension names) and
its shape. Everything else is identical across parts.

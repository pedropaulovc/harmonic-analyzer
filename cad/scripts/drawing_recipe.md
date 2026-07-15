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

Two gotchas the command below works around: (1) codex's `-i` takes multiple
values and will **swallow a positional prompt** placed after it — pipe the prompt
on **stdin** instead; (2) run from a **neutral dir outside the repo** with
`--skip-git-repo-check` so codex does not read `AGENTS.md` and start exploring the
repo (which would make the review non-blind). Write the output to
`cad/out/reports/` (that subdir *is* gitignored; the `cad/out/` root is not).

```
( cd "$TMPDIR" && echo "You are an experienced machinist. Review this manufacturing drawing for accuracy, clarity, and standards conformance. List any problems and say whether the part can be made as drawn." \
  | codex exec -m gpt-5.6-sol -c model_reasoning_effort="high" --skip-git-repo-check \
      -i "<ABS>/cad/out/png/<artifact-stem>_drawing.png" ) \
  2>&1 | tee "<ABS>/cad/out/reports/codex_machinist_review.txt"
```

Address clearly valid accuracy/clarity/standards findings (bounded: 1–2 layout
iterations); leave repo-wide house-style/template items (title-block tolerance
block, edge-break note, general Ra, material short-name) for a follow-up across
the whole drawing set. Keep the review text for the record.

## Committing — stage explicit paths, never `git add -A`

`cad/out/` is only *partially* gitignored (its subdirs, not its root), so the
codex review file at `cad/out/reports/…` is safe but a stray `git add -A` can
still catch other root-level `cad/out` artifacts. Stage the slice files by name
and verify:

```
git add cad/scripts/<part>_spec.py cad/scripts/draw_<part>.py cad/scripts/test_<part>_drawing.py \
        cad/scripts/build_<part>.py cad/scripts/_drawing_registry.py cad/config/parts/<part>.yaml
git commit -m "Add the <part> curated manufacturing drawing slice"
git show --stat HEAD    # confirm ONLY the intended files are in the commit
```

## Merge gate (all four)

1. `doit drawing:<part>` exits 0.
2. `test_<part>_drawing.py` passes.
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

Do all 6 pieces, then BUILD + ITERATE:
  doit part:{PART}  ->  doit drawing:{PART}  ->  Read the PNG  ->  adjust  ->  repeat
  ->  pytest cad/scripts/test_{PART}_drawing.py -q
The seat is shared; "[com.seat] ... waiting for the SolidWorks seat" is EXPECTED — let it wait.
Run this whole build -> iterate -> review -> commit sequence to completion WITHIN your working
turns; do NOT end your turn between steps (e.g. after building the part, or while the seat is
busy) — wait for the seat and continue. Only stop and report when the slice is COMMITTED, or when
you hit a hard error you cannot resolve (paste the exact error). Going idle with the drawing
unbuilt just stalls the fan-out until the lead re-nudges you.
When the PNG looks right, run the independent machinist review (image only, no context;
pipe prompt on stdin so -i doesn't swallow it; run from a neutral dir with --skip-git-repo-check):
  ( cd "$TMPDIR" && echo "You are an experienced machinist. Review this manufacturing drawing for accuracy, clarity, and standards conformance. List any problems and say whether the part can be made as drawn." | codex exec -m gpt-5.6-sol -c model_reasoning_effort="high" --skip-git-repo-check -i "<ABS>/cad/out/png/{ARTIFACT_STEM}_drawing.png" ) 2>&1 | tee "<ABS>/cad/out/reports/codex_machinist_review.txt"
  Address clearly valid findings (1–2 iterations); leave repo-wide house-style items for a follow-up. Keep the review text, include it in your report.
Merge gate: drawing builds clean + test passes + PNG visually correct + codex review addressed.
No CadQuery. Stage explicit slice paths (NOT git add -A) and commit on branch draw-{PART}; do not push/PR.
Report SHA, files, PNG path, gate status, and the codex review verbatim.
```

Fill `{PART}` `{REFERENCE_PART}` `{WORKTREE}` `{GEOMETRY_FACTS}` `{DIM_MAP}`
`{ARTIFACT_STEM}` from the part's `build_<part>.py` (feature + dimension names) and
its shape. Everything else is identical across parts.

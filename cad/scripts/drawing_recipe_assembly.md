# Recipe: adding an ASSEMBLY drawing

The assembly analog of the part-drawing recipe. Reference implementation:
`draw_pen_assembly.py` (views + BOM + balloons of `cad/out/sldasm/pen.SLDASM`),
landed with the shared infrastructure on branch `draw-assembly-infra`.

## The pieces an assembly drawing needs

1. **A registry row** in `_drawing_registry.py` with `source_kind="assembly"`:

   ```python
   DrawingSpec(
       name="<stem>_assembly",          # doit task: drawing:<stem>_assembly
       part="<asm_stem>",               # the ASSEMBLY build stem (build_<asm_stem>_assembly.py)
       artifact_stem="<asm-stem>-assembly",
       script_name="draw_<asm_stem>_assembly.py",
       source_kind="assembly",
   )
   ```

   `spec.source` then resolves to `cad/out/sldasm/<asm-stem>.SLDASM`; the six
   part rows keep `source_kind="part"` (the default) and are untouched.

2. **Title-block custom properties on the assembly.** `finalize_drawing`
   hard-requires the `TOL_*` general-tolerance cells on the linked model; the
   template's PART cell resolves the document summary **Title**, the MATERIAL
   cell links the custom property **`Material`** (not `Material
   Specification`), and DWG. NO. fits ~7 characters (use the `MHA-A##`
   assembly range — anything longer overlaps the REV cell). Assemblies stamp
   none of these by default — add this at the end of the assembly's
   `build_<asm_stem>_assembly.py`, before `save_assembly_and_images` (see
   `build_pen_assembly.py`):

   ```python
   apply_custom_properties(adapter, {
       **assembly_title_properties(ASM_NAME), # Title/Generator + required TOL_* cells
       "Number": "MHA-A##",                  # next free assembly-drawing id
       "Revision": "A",
       "Revision Description": "Initial release",
       "Material": "SEE PARTS LIST",
       "Material Specification": "SEE PARTS LIST",
       "Finish": "SEE PARTS LIST",
       "Quantity": "1",
       "Drawn By": DRAWN_BY,                 # from _drawing_marks
   })
   apply_summary_info(adapter, title=ASM_NAME)   # feeds the PART title cell
   ```

   This edit shifts ONLY that assembly's recipe digest, so exactly it rebuilds
   (plus a fingerprint-no-op refresh of its parents on the next full build).

3. **The drawing script** `draw_<asm_stem>_assembly.py`, modeled on
   `draw_pen_assembly.py`:
   - `SOURCE = SPEC.source`; open it, `read_required_properties` for the
     stamped fields.
   - `new_project_drawing(adapter, scale=SHEET_SCALE)` — pick ONE sheet scale
     that fits the whole assembly on ASME B (0.4318 x 0.2794 m) and pass the
     same `scale=` explicitly to every `place_view` (an unpinned view silently
     auto-scales and breaks coordinate picks — see
     `memory/drawing-recipe-com-pitfalls.md`).
   - Standard views via `place_view(adapter, str(SOURCE), "*Front"/"*Right"/
     "*Isometric", x, y, scale=...)` — `CreateDrawViewFromModelView3` takes the
     `.SLDASM` path directly.
   - **BOM**: `insert_bom_table(adapter, view, anchor_xy=(x, y),
     expected_components=(...), label=...)` (`_drawing_common`). Top-left
     anchored, top-level-only BOM from the install's `bom-standard.sldbomtbt`;
     it validates one row per expected component and every part number present.
     List every top-level component of the assembly build in
     `BOM_COMPONENTS` — the offline test cross-checks it against the build
     script's `place_component` calls.
   - **Balloons**: `add_auto_balloons(adapter, view, expected=N, label=...)` —
     square layout of circular item-number balloons around the chosen view,
     numbering owned by the BOM (never resequenced).
   - `stamp_drawing_summary` + `finalize_drawing(...)` — the shared layout
     audit (overlaps / overflow / title-block keep-out) runs before the first
     save; the BOM table and balloons are audited like any table/leadered note.

4. **The doit task comes for free.** `dodo._drawing_file_deps` keys an
   assembly-sourced drawing on the `.SLDASM` recipe (script + helper closure +
   full submodule digest + template) plus the assembly execution token. The
   recipe digest remains byte-churn-immune, while the token invalidates the
   drawing after a same-recipe from-scratch assembly rebuild with new PIDs.

5. **An offline contract test** `test_pen_assembly_drawing.py`-style:
   registry row, output paths, `_drawing_file_deps` shape (SLDASM + exact
   `.execution` token in), task targets, BOM list vs the build script.

## Build / iterate loop

```
cd <your worktree>
uv run python -m doit drawing:<stem>_assembly    # first run also rebuilds assembly:<stem>
                                                 #   (the property-stamp edit changed its recipe)
# -> cad/out/png/<asm-stem>-assembly_drawing.png
```

SolidWorks must be open; `[com.seat] ... waiting for the SolidWorks seat` is
normal cross-worktree serialization — let it wait. Read the PNG, adjust the
view centers / BOM anchor constants, re-run until the layout audit passes and
the sheet reads clean. The audit fails loud on element collisions, sheet
overflow, and anything touching the title-block keep-out (x ≥ 0.264 m,
y ≤ 0.064 m).

Layout budget notes (ASME B, sheet meters, origin bottom-left):
- Pick the sheet scale from the assembly bounding box; the pen (44 x 197 x
  34 mm) uses 1:2.
- Balloons extend ~0.02 m beyond the ballooned view's outline on every side —
  leave that margin before the next view.
- `bom-standard.sldbomtbt` is 4 columns (ITEM NO. / PART NUMBER / DESCRIPTION /
  QTY.); anchor it top-left with enough width to the right border.

## Independent machinist review (codex) — after the PNG looks correct, before commit

Send ONLY the rendered image, with no repo context, to an independent
machinist review. Run from a NEUTRAL directory (outside the repo, so codex
does not pick up AGENTS.md and explore the codebase), pipe the prompt on
stdin (codex's multi-value `-i` swallows a positional prompt), and tee the
review to the gitignored `cad/out/reports/`.

**Every safeguard in `drawing_recipe.md`'s review section applies here verbatim
— read it, this block is only the assembly-flavoured command.** In particular:
`mktemp -d` (never a fixed temp path: a shell that rejects `cd ""` makes `&&`
short-circuit, and `tee` then writes a plausible-looking review file containing
only a shell error); `mkdir -p` the report dir; `--ignore-user-config
--ignore-rules` so the seat's hooks/rules cannot bias the verdict; and NEVER
`--sandbox danger-full-access`, which un-blinds the reviewer.

```
mkdir -p "<worktree>/cad/out/reports"
NEUTRAL=$(mktemp -d) || exit 1
( cd "$NEUTRAL" && echo "You are an experienced machinist. Review this manufacturing drawing for accuracy, clarity, and standards conformance. List any problems and say whether the assembly can be built as drawn." \
  | codex exec -m gpt-5.6-sol -c model_reasoning_effort="high" \
      --skip-git-repo-check --ignore-user-config --ignore-rules \
      -i "<worktree>/cad/out/png/<asm-stem>-assembly_drawing.png" ) \
  2>&1 | tee "<worktree>/cad/out/reports/codex_machinist_review.txt"
rmdir "$NEUTRAL"
```

Then **read the review file before believing the gate ran** — a transcript with
no verdict is the failure to catch.

If codex flags clearly valid problems, fix and re-render (bounded: 1-2
iterations), and include the full review verbatim in your report.

## Merge gate (same three-part gate as every PR, plus)

- `uv run python -m doit drawing:<stem>_assembly` exits 0.
- `uv run python -m pytest cad/scripts/test_*_drawing.py -q` — the new
  contract file AND the six existing part-drawing contracts stay green.
- Eye pass on `cad/out/png/<asm-stem>-assembly_drawing.png`: views not
  overlapping, components visible, BOM rows legible and complete, balloons
  numbered, title block populated (no blank Number/Revision/tolerance cells).
- The codex machinist review above ran, and its clearly-valid findings were
  addressed.

## Fan-out prompt template (one agent per assembly, own worktree)

> You are adding the **<ASM_STEM>** assembly drawing to the harmonic-analyzer
> repo, following `cad/scripts/drawing_recipe_assembly.md` (read it first) with
> `draw_pen_assembly.py` as the reference. Work only in your worktree
> `<WORKTREE>` on branch `draw-<asm-stem>-assembly`.
>
> 0. Invoke the `/developing-solidworks` skill before any COM work.
> 1. Stamp title-block properties in `build_<ASM_STEM>_assembly.py`
>    (recipe §2; Number `HA-ASM-<STEM>`).
> 2. Add the registry row (recipe §1) and `draw_<ASM_STEM>_assembly.py`
>    (recipe §3). The assembly has <N> top-level components:
>    <COMPONENT_LIST>. Its bounding box is <W x H x D> mm — pick the sheet
>    scale accordingly.
> 3. Iterate `uv run python -m doit drawing:<ASM_STEM>_assembly` until green,
>    reading the PNG between runs ("waiting for the SolidWorks seat" is
>    expected — let it wait).
> 4. Add `test_<ASM_STEM>_assembly_drawing.py` (offline contracts) and run
>    `uv run python -m pytest cad/scripts/test_*_drawing.py -q`.
> 5. Run the codex machinist review (recipe section above — exact command;
>    image-only, from a neutral dir) and address clearly-valid findings
>    (1-2 re-render iterations max).
> 6. Commit on your branch — stage files explicitly, never `git add -A`, and
>    verify with `git show --stat HEAD` that no `cad/out` artifact or review
>    txt landed. Report the PNG path, layout-audit status, BOM row count, and
>    the codex review verbatim.

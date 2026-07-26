---
name: drawing-recipe-com-pitfalls
description: "SolidWorks drawing recipes: always pin view scale (auto-scale silently breaks coordinate picks), pick hole RIMS not centers, GetOutline pads a margin, hole-table origin lands on the chamfer-trimmed vertex"
metadata:
  type: project
---

Learned building the crank-arm and rocker-arm-support prints (2026-07-11, PRs #243/#246 stacked on #225):

1. **Always pass an explicit `scale=` to `place_view`.** A view placed without one can silently auto-scale (the rocker-arm-support bottom view came in at 1:2 on a 1:1 sheet), which shifts every coordinate-based `SelectByID2` pick on that view. Symptom: "failed to select … vertex/edge" with coordinates that look right.
2. **Hole-table edge picks must land ON the circle's rim**, not the hole center — offset the pick by the hole radius (tap-drill radius for wizard holes).
3. **`IView.GetOutline` pads the geometry with a whitespace margin** — never derive edge-pick coordinates from it (the submodule's `add_overall_dimension` does, and misses). Use `_drawing_common.add_edge_dimension` with explicit sheet points computed from the known layout.
4. **A chamfer that touches the datum corner moves the hole-table origin.** The rocker support's 1.27 rim chamfer trims the foot seat to 175.26×60.96, so X/Y LOCs measure from the trimmed corner — self-consistent with the physical part, but state it in a note or the pattern reads asymmetric.
5. **A through-tapped Hole Wizard hole renders "⤓ 0.000" thread depth in the native hole table** — add a note ("DEPTH 0.000 MEANS TAPPED THRU") rather than fighting the callout.
6. **Sheet-size budget:** a 178 mm part with four views does NOT fit ASME B at 1:1 (notes collide, table clips the border) — pick sheet scale for the whole sheet (1:2) instead of per-view overrides, so the title-block `$PRP:"SW-Sheet Scale"` stays honest. ~5.3 mm per note line, ~2.3 mm per character at the default template font.

Learned building the drawing **layout audit** (`_drawing_layout_check.py` + `_drawing_common.collect_layout_elements`, PR #269, 2026-07-12) — how drawing elements are actually laid out in COM:

7. **Hole tables anchor to the SHEET view, not the drawing view they tabulate.** `IView.GetAnnotations()` does NOT return tables — use `IView.GetTableAnnotations()`, and scan the sheet view (`GetFirstView`) for them, not just the real views (`InsertHoleTable3` on a view still parents the table to the sheet). Table box (TopLeft anchor): position from the table's `GetAnnotation().GetPosition()` is the top-left corner; width = Σ`GetColumnWidth(i)`, height = Σ`GetRowHeight(i)`, box grows right and DOWN.
8. **Free notes are OWNED by whatever view was active when `add_note`/`InsertNote` ran** — the general-notes block lands on a drawing view but is positioned far away in the sheet margin, so it is NOT inside that view's `GetOutline`. Enumerate notes per real view via `GetAnnotations()` (type 6 = swNote), box each with `INote.GetExtent()` (6 doubles, LL/UR in sheet meters).
9. **Sheet-view annotations = the checked-in sheet-format frame + title block** (zone letters at the edges, title-block field text bottom-right) — exclude them from any layout scan; they live at the sheet edges by design.
10. **An isometric view's axis-aligned `GetOutline` bbox is mostly EMPTY diagonal space**, so nearby labels bbox-overlap it without touching geometry (false collision). Detect pictorial views via `IView.GetOrientationName()` (`*Isometric`/`*Dimetric`/`*Trimetric`; ortho views return `*Front` etc., projected/section return `""`) and exclude them from the OVERLAP check only — they are STILL overflow-checked (a gross off-sheet iso view must be caught; Codex #269 thread 1). See [[oblique-views-break-on-axis-occlusion]].
11. **Hole-table tag labels (`A1`,`B2`…) are non-leadered notes sitting ON the view** — a note whose center is inside its owning view is detail, not a free element. But the exemption is SIZE-GATED (≤15 mm span) so a large general-notes block dropped on its own view is still flagged; and the tag is exempted from its own view only, not from other notes/tables.
12. `GetOutline` padding (#3) also means a legitimately on-sheet iso view reports ~1.5 mm past the top edge — so BOTH slacks are fuzzy-box-only. The OVERFLOW outward allowance applies only to `view` (padded) boxes; the OVERLAP penetration tolerance applies only to pairs involving a fuzzy box (padded view OR nominal GD&T/dim). Two EXACT boxes (note/table/titleblock, from `GetExtent`/column-widths/reserved constants) get near-zero slack on both — a 1 mm note-into-table/title-block or a 1–3 mm off-sheet clip is a real defect (Codex #269 threads 7 + exact-slack). This strictness caught a genuine 0.6 mm overlap: rocker-arm-support's hole table bottom rule sat on the title-block top rule (fixed by nudging `HOLE_TABLE_ANCHOR` up ~4 mm) — so a shipped "visually-inspected" drawing CAN carry a sub-mm overlap the eye misses.

**Collision-scope model (the audit's core abstraction).** Cross-file element state is a `CollisionScope` enum (`ALL`/`NON_VIEW`/`NONE`), not a bool — repo style. `ALL` = ortho views, free notes, tables; `NON_VIEW` = leadered callouts + on-view tags (exempt from colliding with the ONE view they own/point at — via a per-element `owner`=view-label — but a collision with a note/table or a DIFFERENT view is audited); `NONE` = pictorial views + GD&T + display dimensions (overflow-only, never an ordinary overlap source). A pair is overlap-audited only if `_may_collide` admits BOTH. **The title block is a HARD keep-out** (`kind=="titleblock"`): every element is checked against it regardless of scope (so an otherwise-exempt pictorial view / GD&T / dim covering it is still caught); two keep-out boxes never collide with each other.

13. **GD&T symbols AND display dimensions have NO real bounding box.** `IAnnotation.GetDisplayData`→`IDisplayData` is a DEAD END for a sheet-space box: its line primitives include the **leader line** (so the extent balloons to the pointed-at geometry) and the coordinates are in a **non-sheet space** — an SFSymbol at `GetPosition (191,245)` reported a display box `[0,61,91,228]` (doesn't contain its own anchor); a datum tag reported `xmax=1000 mm` on a 431 mm sheet. Don't re-probe it. Only `IAnnotation.GetPosition()` (sheet-space anchor) is reliable → box these as a small nominal square (GD&T ±8 mm, dims ±4 mm). Fine for OVERFLOW (catches an off-sheet symbol/callout) but too coarse for OVERLAP — a datum tag beside its own control frame self-collides — so both are scoped `NONE` (overflow + title-block-keep-out only). Types (`swAnnotationType_e`): note=6, datum=2, gtol=5, sfsym=7, **displayDimension=4**. A native **hole callout** (`annotate_holes_thru`/`add_native_hole_callout`) is a swDisplayDimension (a diameter dim with "/ THRU" text), NOT a note — so it is caught by the type-4 branch, not type-6. Follow-up if a real box is found: issue #275.
14. **The checked-in ASME B sheet format (`asme-b-book.slddrt`) bakes its title block in as lines/notes, NOT a queryable `ITitleBlock`** — `sheet.TitleBlock` is None and `ITitleBlock.GetExtents` is unavailable. Reserve its occupied region as fixed keep-out boxes that MUST track `create_drawing_standards.py`: (a) the title block proper `TITLE_X0=0.278 .. TITLE_Y1=0.080` extended to the sheet right/bottom (`_TITLE_BLOCK_LEFT_M`/`_TITLE_BLOCK_TOP_M`), and (b) a SEPARATE box for the third-angle projection symbol at `(0.252,0.027) size 0.007` (`_PROJ_SYMBOL_BOX_M`) — it sits LEFT of the title block, and a combined leftward-extended box would clip top-crossbar's notes block (reaches x~253 mm at y72-90). Don't eyeball these constants (an earlier 0.2785/0.078 left a 0.5 mm/2 mm strip and the whole projection symbol unreserved — Codex). Follow-up to add a real ITitleBlock: issue #273.

Learned building the first ASSEMBLY drawing (pen, `draw_pen_assembly.py`, 2026-07-14 —
BOM + auto-balloons):

15. **A COM-inserted top-level BOM starts with NO configuration bound.**
    `IView.InsertBomTable6` (`InsertBomTable4` is obsolete) with
    `swBomType_TopLevelOnly` returns a header-only table — no data rows and no
    QTY column (QTY columns are per-configuration on top-level BOMs). Bind the
    view's configuration explicitly afterwards:
    `IBomFeature.SetConfigurations(True, bool_array([True]), bstr_array([cfg]))`
    (the documented path for top-level tables), then rebuild — 8 rows + QTY
    appear. `_drawing_common.insert_bom_table` owns this.
16. **`AutoBalloon5` drops balloons for components with no visible geometry in
    the view.** On the HLR front view only 7 of the pen's 8 components
    ballooned (the hanger screw is fully occluded behind the strap). Balloon
    the ISOMETRIC view, where every component keeps visible edges.
17. **A BOM balloon note's `GetExtent` box includes its LEADER** — it spans
    from the balloon circle to the pointed-at component (same
    leader-polluted-box dead end as #13's `IDisplayData`), so neighboring
    balloons' extent boxes always intersect near the view. Never place or box
    balloons by extent: place them by their `IAnnotation.GetPosition` anchor
    (`_drawing_common._spread_balloons` re-rings them evenly on an ellipse just
    outside the view outline, slots assigned by landed angle so leaders don't
    cross), and the layout audit boxes a `IsBomBalloon` note as a ±6 mm nominal
    square around that anchor (`_NOMINAL_BALLOON_HALF_M`), scope `NON_VIEW`.
18. **Assembly title block needs properties parts get for free.** The template's
    PART cell resolves the document summary **Title** (`apply_summary_info`,
    which only `save_part_and_images` stamps) and the MATERIAL cell links the
    custom property **`Material`** — not `Material Specification`. An assembly
    build must stamp both (plus Number/Revision/TOL_* — see
    `build_pen_assembly.py`), or the print ships blank cells that
    `finalize_drawing`'s TOL-only validation does not catch. The DWG. NO. cell
    fits ~7 characters (`MHA-###` / `MHA-A##`); a longer id overlaps the REV
    cell.

19. **A named part entity beats a coordinate pick — UNPROVEN here, but the API
    path is documented (2026-07-26, Pedro's suggestion).** Every attached
    annotation ultimately needs a SELECTION: `IModelDoc2::InsertDatumTag2()`
    takes **no arguments** and acts on whatever is selected, and SolidWorks' own
    example does exactly what this repo does — coordinate `SelectByID2("",
    "EDGE", x, y, ...)` then `InsertDatumTag2()` (it does not even check the
    selection's return). So the coordinate idiom is CANONICAL, not a shortcut,
    and it is safe here only because item 1 pins every view scale.

    The failure mode is what argues against it: a pick that lands slightly off
    does not necessarily FAIL — it can silently select a NEIGHBOURING edge and
    attach datum A to the wrong face, which passes every gate and looks
    plausible on the render. A name cannot do that.

    The documented alternative, per the *Select Entity in Drawing View* example:
    `IView::SelectEntity` accepts a **MODEL** entity (the example passes one
    straight from the part's `GetSelectedObject6`) and selects its projection in
    that view. Pair it with `IPartDoc::SetEntityName` / `GetEntityByName` in the
    part build and the sheet coordinate disappears entirely.

    Verify before adopting: `SetEntityName` REFUSES when the entity is already
    named or the name is not unique (SolidWorks auto-names faces used by
    assembly mates), so read the existing name first; the example warns a
    dimension "is not guaranteed to be created if a face is selected" and that
    `SelectEntity` can select an entity NOT VISIBLE in the view, so face-vs-edge
    datum attachment needs a live probe. ~218 `edge_xy=` call sites exist —
    migrate the datum/GD&T attachments first, where a silent wrong-edge pick
    does the most damage.

    Independent of that: `place_view` never reads back `IView.Position` after
    `CreateDrawViewFromModelView3`, so if SolidWorks ever snaps or nudges a
    view, EVERY computed pick on it shifts and nothing notices. Asserting
    requested-vs-actual position is a few lines and would confirm or kill that
    class outright. Open symptom that motivated this: `drawing:top_crossbar`
    failed its datum pick once inside a `doit -n 4` run and passed standalone
    against the SAME .SLDPRT, with view scales pinned — so neither geometry nor
    auto-scale explains it, and it remains UNDIAGNOSED (do not repeat the
    earlier mistake of asserting seat contention from one failure and one pass).

Related: [[codex-drawing-image-review]], [[no-untested-failure-assumptions]].

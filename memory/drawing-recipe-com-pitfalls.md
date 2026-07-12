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
10. **An isometric view's axis-aligned `GetOutline` bbox is mostly EMPTY diagonal space**, so nearby labels bbox-overlap it without touching geometry (false collision). Detect pictorial views via `IView.GetOrientationName()` (`*Isometric`/`*Dimetric`/`*Trimetric`; ortho views return `*Front` etc., projected/section return `""`) and exclude them from collision/overflow checks. See [[oblique-views-break-on-axis-occlusion]].
11. **Hole-table tag labels (`A1`,`B2`…) are non-leadered notes sitting ON the view** — a note whose center is inside its owning view is detail, not a free element. Combined with #10, this is what keeps the layout audit false-positive-free on the shipped prints.
12. `GetOutline` padding (#3) also means a legitimately on-sheet iso view reports ~1.5 mm past the top edge — the overflow check needs an OUTWARD allowance, not an inward margin.

Related: [[codex-drawing-image-review]].

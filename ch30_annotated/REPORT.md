# ch30 view annotation — Claude vs Codex comparison report

2026-07-01. Eight photos of the harmonic analyzer (ch. 30 views,
`references/albert-michelsons-harmonic-analyzer/ch30_images`) were annotated twice,
independently — 8 Claude subagents (one per image) and Codex CLI (GPT-5.x, two 4-image
runs) — from the identical spec (`SPEC.md`: zoom/crop + vision only, no CV edge
detection, every dot verified on a post-draw zoomed crop). 8 adjudicator agents then
cropped the originals around every disputed point and judged each feature blind.

## Directories

| dir | contents |
|-----|----------|
| `claude/` | Claude's 8 annotated PNGs + JSONs |
| `codex/`  | Codex's 8 annotated PNGs + JSONs |
| `verdicts/` | per-image adjudication JSONs (feature-level winner + true point) |
| `final/` | **consensus set** — verdict-corrected dots + spec-consistent names; use these |

Colors: red = pinion (chain sprocket by the brass drive gear), orange = cylinder
gear(s), magenta = cone gear, yellow = rocker-arm corners, cyan = machine corners.
Occluded features are listed in each image's legend and JSON instead of getting a dot.

## Verdict tally (115 adjudicated features)

| verdict | count |
|---------|-------|
| Claude's point/call better | 60 |
| tie (both right, incl. agreed occlusions) | 36 |
| Codex's point/call better | 12 |
| same corner, mirrored naming (label_mismatch) | 7 |

## Systematic findings

**Claude — placement wins, two identity losses.**
- Base-slab and top-frame corners: Claude sat on the true bottom/outer corners in
  every view; this drove most of its 60 wins.
- page003 + page009: Claude mislabeled the CONE gear as cylinder gears (and called
  the cone occluded). page009: Claude misread the orientation as front-LEFT and
  mirrored every corner name (it flagged the ambiguity itself).

**Codex — decent gear IDs in front views, systematic corner offset.**
- Base corners placed 100–250 px too high (slab top edge / body-slab junction) or
  floating in black background, in 5 of 8 views; several corner names mirrored
  (006/007/009 back/three-quarter views).
- Identity errors in the back views: called the crank-axle sprocket "pinion" (006),
  the cone body "cylinder gears" (004, 005), a cylinder gear "cone" (006).
- Wins: cone-gear identification in 003/009, orientation call in 009, rocker tip
  (one corner) in 007, the occluded gear-window calls in 008.
- Codex also finished ~3× faster (≈10 min vs ≈35 min for the Claude fan-out) with
  visibly shallower verification loops — consistent with its lower placement accuracy.

**Genuinely hard/occluded across views** (no dot, noted in legends): cone gear from
the front (002) and back-right (007); pinion from the back (005/006/007) and — per
adjudication — 004's chain sprocket IS visible (Claude marked it); rocker-arm butt
corners everywhere (buried in the pivot linkage — only tip corners are resolvable,
best in 005/007); far-side machine corners in every non-frontal view.

**Rocker arms:** only the topmost/front-most arm of the ~20-arm fan is resolvable, and
only in 005 and 007 (tips; butts always occluded). In 002/003/004/008/009 the fan is
edge-on or hidden — adjudicators confirmed no corner is markable to ~5 px there. 006
was ruled unresolvable too (overlapping nubs).

## Ops note

The `codex` plugin's `--write` path (workspace-write sandbox) blocks ALL commands on
Windows; both plugin-mediated runs failed before doing any work. The comparison runs
used `codex exec --sandbox danger-full-access` directly. See
`memory/codex-windows-sandbox.md`.

---
name: drawing-text-leader-style
description: Bent leaders + horizontal dimension text — swDetailingDimensionTextAndLeaderStyle=372 needs a DIMENSION scope (NoOptionSpecified silently rejects) and the umbrella does NOT propagate to per-type scopes; enum ints must be read from swconst.tlb because the API docs publish none
metadata:
  type: reference
---

Making SolidWorks drawing dimensions render **bent leader + horizontal text**
(2026-07-16, PR #334). Four facts, none documented; all cost a probe to learn.

**Dimensions do NOT take `IAnnotation::SetLeader3`.** Its documented support list
is notes / GTols / surface-finish / weld / datum-target / block instances only.
A dimension's leader+text style comes from the DOCUMENT preference
`swDetailingDimensionTextAndLeaderStyle`; `IDisplayDimension::SetBrokenLeader2`
is the per-dimension override (return `1` = "invalid, silently fell back to doc
default", so only `0` is success). GD&T frames / Ra symbols DO take
`SetLeader3(swBENT=2, swLS_SMART=0, ...)` and return an int status (0 = OK).

`swDisplayDimensionLeaderText_e.swBrokenLeaderHorizontalText` (= **2**) delivers
BOTH requirements in one value: leader broken AND text always horizontal instead
of rotated to follow the leader. The default is `swSolidLeaderAlignedText` (= 1)
— that is what renders the rotated vertical `Ø9.525 THRU - REAM 3/8 IN` text.

**The ints are NOT in the published API docs.** Every
`swUserPreferenceIntegerValue_e` / `swUserPreferenceOption_e` member prints "See
System Options and Document Properties" instead of a value, and that page
documents none of them. Read them off the installed type library instead — and
note `LoadRegTypeLib`/`EnsureModule` by CLSID FAILS on this seat ("Library not
registered"); load by PATH:

```python
import pythoncom
tlb = pythoncom.LoadTypeLib(
    r"C:\Program Files\Dassault Systemes\SOLIDWORKS 3DEXPERIENCE R2026x"
    r"\SOLIDWORKS\swconst.tlb")
# walk GetTypeInfo(i) where TypeAttr.typekind == pythoncom.TKIND_ENUM
```
`swDetailingDimensionTextAndLeaderStyle` is **372** (a from-memory guess of 268
looked plausible and would have written to an unrelated preference).

**TRAP 1 — the preference REQUIRES a dimension scope.** Written under
`swDetailingNoOptionSpecified` (0) the set returns **False** and the document
stays on `swSolidLeaderAlignedText`. It only takes under a
`swUserPreferenceOption_e` dimension scope (200..209).

**TRAP 2 — the umbrella `swDetailingDimension` (200) does NOT propagate.** After
setting it, every per-type scope still reads 1. All ten (200..209) must be set
explicitly and read back, or linear/radius/diameter dimensions keep rotated text
while the umbrella reports success. See `_pin_dimension_text_and_leader_style` /
`_DIM_DETAILING_SCOPES` in `_drawing_common.py`.

Always read the preference back: both traps fail SILENTLY (a False return and a
stale value), never by raising.

**Consequence for layout:** horizontal text is far WIDER than the rotated text
old annotation coordinates were tuned for, so switching collides text across
every sheet — and it cannot be gated, because dimensions/GD&T expose no
`GetExtent` (only `INote`/`IBomTable` do), which is why they carry
`CollisionScope.NONE`. Re-layout is an eye pass. See
[[drawing-sheet-zone-border]] and [[solidworks-modeling-pitfalls]].

**EVERY annotation's anchor means something DIFFERENT, and none of them is "the
centre".** `SetPosition2`'s Remarks carry the authoritative table; any gate that
boxes an annotation symmetrically around `GetPosition` is the wrong SHAPE for all
but a coincidence:

| annotation | XYZ origin IS | so the body draws |
|---|---|---|
| Surface finish | "Lower-left point of symbol" | UP + RIGHT |
| Geometric tolerance (FCF) | "Upper-left corner of the symbol" | DOWN + RIGHT |
| Datum feature | "Point where leader hits symbol" | away from the leader |
| Note | "Upper-left corner of the text box" | DOWN + RIGHT |
| Display dimension | "Point of leader attachment centered on a text box border / center point of bottom border of text box" | — |

This table independently CONFIRMS the Ra anatomy measured below ("lower-left
point" ⇒ up-right body), and it confirms draw-A's measurement that a datum tag's
requested y lands on the box's BOTTOM edge ("point where leader hits").

**FCF anatomy — MEASURED 2026-07-16, and no fixed box can be right.** Both of
top-crossbar's frames, read off the render against their requested `frame_xy`:

| frame | left | right | up | down |
|---|---|---|---|---|
| `⊕ Ø0.20 A B C` @ (0.112, 0.235) | −2.6 | **+41.6** | +0.1 | −7.1 |
| `⊥ 0.10 A B` @ (0.115, 0.175) | −2.6 | **+32.2** | +0.1 | −7.1 |

(mm, relative to the anchor.) So the doc is exactly right — **anchor = the box's
TOP-LEFT corner** (up = +0.1, i.e. the anchor's y IS the top edge), the height is
a CONSTANT 7.1 mm (the same as a datum tag's box), the −2.6 mm on the left is the
leader's horizontal entry stub, and **the width VARIES with compartment count**
(+9.4 mm for the third datum + the Ø prefix).

That kills the `_NOMINAL_GDT_HALF_M` symmetric ±8 mm box for GTOLs the same way
the Ra box died: it wastes 8 mm above and 5.4 mm left on empty sheet while
**missing ~34 mm of frame body to the right** — a border crossing or overflow in
an FCF's right half is invisible to the audit. And because the width is
content-dependent, the Ra fix's trick (a per-kind constant box) does NOT
transfer.

**STOP MODELLING THE BOX — MEASURE IT. `GetLineAtIndex` hands you the real
rendered geometry** (probed 2026-07-16 on rocker-arm-support). Three findings,
each of which kills an approach that looked reasonable:

- **`GetExtent` is a dead end, and the inherited claim was RIGHT**: the type
  library declares it on **`IBomTable` and `INote` ONLY**. Verified with a
  positive control in the same run — `INote.GetExtent()` returns a real 6-tuple
  `(x0,y0,z0,x1,y1,z1)`, so the API works and the call shape is right; GTOLs and
  datum tags genuinely lack it.
- **But `IGtol`/`IDatumTag` expose the geometry directly.**
  `GetLineAtIndex(i)` → `[lineType, startPt[3], endPt[3]]`,
  `GetTriangleAtIndex(i)` → `[vtx1[3], vtx2[3], vtx3[3], isFilled, lineType]`,
  plus `GetArcAtIndex`/`GetArrowHeadAtIndex`. **This is better than `GetExtent`
  would have been** — it is the actual ink, per primitive.
- **The line list is [leader..., then the frame/box rectangles]** — or for a
  GTOL, `[compartment rects..., shoulder, diagonal leader]`. A GTOL's frame is N
  abutting 7.0 mm-tall rectangles (one per compartment); a datum tag's box is
  **always the LAST 4 lines**, a 7.0 × 7.0 rectangle.

COM geometry and the render agree to 0.1 mm on the position frame (COM: anchor
+0.0 left / +41.6 right / +0.0 up / −7.0 down; render: −2.6 / +41.6 / +0.1 /
−7.1). The render's −2.6 mm on the left is the **leader shoulder**, which COM
separates out as its own line — two independent methods, same answer, and the
disagreement explained rather than averaged.

**For an OVERFLOW gate, box a GTOL/datum by the bbox of ALL its lines** (frame +
leader): GD&T carries `CollisionScope.NONE`, so the only question asked of it is
"does this ink cross the border", and the leader is ink. Do NOT bother separating
frame from leader for that. Separation matters only for the collapse gate below.

**Ra symbol anatomy — `symbol_xy` is the leader's attachment point, NOT the
centre.** Measured across three sheets, and matching the doc's "lower-left point of
symbol" exactly. Relative to `symbol_xy` = (ax, ay), the
whole body draws UP and RIGHT of the triangle's bottom vertex, which sits exactly
at (ax, ay): triangle x [ax-0.006, ax+0.006] y [ay, ay+0.011]; "Ra 1.6" text
x [ax+0.013, ax+0.039] y [ay+0.010, ay+0.017]; arm y ≈ ay+0.018. Footprint
≈ 46 x 19 mm over [ax-0.007, ax+0.039] x [ay, ay+0.018]. Two consequences the
gates cannot see: a target ABOVE the anchor draws the leader THROUGH the
triangle unless it escapes sideways faster than the ~1.8 flank slope, and a
target UP-RIGHT strikes the leader through the symbol's own text (needs slope
> ~1.3). So aim for slope in (1.3, 1.8), or simply put the target BELOW the
anchor — always clean. The pick height, not the symbol position, is the cheap
knob.

**A Ø dimension OCCUPIES TWO clock positions on the circle, not one.** SolidWorks
renders a diametral dimension as a LINE ACROSS THE FULL CIRCLE with an arrowhead
at each end (the leader continues out of the far side to the text). That line
through the bore is CORRECT ASME rendering, NOT a leader striking through the
feature — it looks exactly like the defect and nearly cost a "fix" to correct
geometry. Consequence when placing anything else on that circle: two antipodal
points are already taken (e.g. 49 deg and 229 deg), so the free quadrants are
what is left. Budget them before adding a datum tag or Ra symbol.

**A datum feature symbol is not freely placeable — the ATTACHED ENTITY decides.**
**READ THE RESTRICTION'S SCOPE — it is the whole ballgame.** `SetPosition2`'s
Remarks say: "One example of a restriction is a surface-finish symbol that is
inserted directly on a face **(that is, no leaders)**. It can only be moved within
the borders of that face. If it is inserted directly on an edge, it can only be
moved along that edge or extensions of that edge. Datum feature symbols have
similar restrictions."

The **"(that is, no leaders)"** qualifier scopes the entire thing. A LEADERED datum
tag — which is what `add_datum_feature` produces — is NOT subject to the
along-the-edge restriction at all. An earlier version of this note quoted the
restriction with that qualifier dropped, and then two successive false theories got
built on the mis-paraphrase ("trapped on the circumference regardless of size", then
"on a straight edge, y is honoured and x is projected back onto the line"). Both are
FALSE. `draw_pivot_bushing`'s datum B is the disproof of the second: perpendicular
x −18 mm off a VERTICAL edge, honoured in full, with a long clean leader. If x were
projected onto the line its box would sit on the edge with no leader.

**What actually governs (draw-A's controlled experiment, 2026-07-16).** Decompose
the displacement from the PICK to the SYMBOL along the entity's outward normal at
the pick:

| case | normal component | tangent | result |
|---|---|---|---|
| cylinder_gear pick @ 3 o'clock | **−0.0095** | +0.0239 | STUCK |
| cylinder_gear pick @ 12 o'clock | **+0.0145** | 0.0000 | FREE |
| cone_lock_knob pick @ 45° | **+0.0321** | −0.0233 | FREE |

Rows 1–2 are a controlled experiment: same circle, same `symbol_xy`, ONLY the pick
moved. **The rule: `dot(symbol_xy − edge_xy, outward_normal_at(edge_xy))` must be
POSITIVE.** Otherwise the tag has no room to stand off and slides along the entity.
A straight edge's normal is fixed → "offset perpendicular, not along". A circle's
normal rotates with clock position → the pick's clock position is the knob. Same
rule, two faces. And the along-edge component is not wasted: it SLIDES the
attachment point along the edge (draw-C's `pinion_pivot_block` datum C — perp
x +16 AND along y +20, both honoured).

cone-lock-knob's 57 mm was never what saved it: its normal component is simply the
largest of the three. **Distance was a red herring in every version of this note.**

**On a CIRCLE the rule that fits all six measured samples is: the tag always
re-attaches at the circle point NEAREST the symbol, but the requested STANDOFF
survives only when `edge_xy`'s clock position AGREES with the direction the symbol
sits in.** Disagree, and the symbol is dragged down onto the circumference and
`symbol_xy` goes inert.

- pick 3 o'clock + symbol at 12 → **collapses**: pivot-shaft asked 17.6 mm, got
  1.05 mm; cone-tip-bushing rendered 0.227 and 0.150 pixel-identically.
- pick 12 + symbol at 12 → **honoured exactly**: cone-tip-bushing's box bottom
  lands ON the requested y (0.227 → 0.227, 0.245 → 0.2442), confirming the anchor
  is the box's bottom edge, i.e. the documented "point where the leader hits".
- pick 45° + symbol up-right (already agreeing) → cone-lock-knob's tag sits ~57 mm
  from a radius-19.5 mm circle with a real leader, and never looked broken.

An earlier version of this note said a circle "traps the tag on the circumference
regardless of SIZE". That is wrong — cone-lock-knob disproves it, and the size
framing it replaced was wrong too. It is neither size nor trapping: it is whether
the pick and the symbol agree on direction (draw-A, from 6 samples).

Fix a stuck tag by picking the circle at the clock position the symbol sits at
(`edge_xy=bore_top` with the symbol above — the `draw_pivot_bushing.py` spelling).
**The "attach to a straight flank in a side view instead" escape does NOT exist
for a bore seen end-on**: the bore's hidden inner line is unpickable as BOTH
`EDGE` and `SILHOUETTE` (two hard `RuntimeError`s, no render, at two different x).
A shaft's OD flank IS pickable as `SILHOUETTE` — a true outer silhouette is a
different animal from a bore's hidden inner line. So for an end-on bore the
clock-position fix is the only lever. Two signatures of a mis-picked clock
position, both measured 2026-07-16 and both INVISIBLE to every gate (a datum
symbol exposes no `GetExtent`, so it is `CollisionScope.NONE`):
- **inert `symbol_xy`** — picked at 3 o'clock with the symbol at 12, the tag
  collapses onto the circle and the requested standoff is discarded (pivot-shaft:
  17.6 mm requested, 1.05 mm rendered — too little for the ~3 mm attachment
  triangle, which then overlapped its own box and struck through the "A").
- **stacked arrowheads** — a symbol placed toward a Ø dimension's arrow resolves
  to that same circle point (pinion-pivot-block: datum B at 49.4 deg vs the
  diameter arrow at 49.3 deg, 0.90 mm apart), so two arrowheads print on one
  spot and the box straddles the diameter line.
A near-miss gap of ~1 mm is the tell. There is no `add_datum_feature` lever:
datum FEATURE symbols are absent from `SetLeader3`'s support list (only datum
TARGET symbols are), `IDatumTag::LeaderOrientation` is round-tags-only, and
`SetDisplayStyle` sets shape, not attachment.

**A LEADER-LENGTH gate on a datum tag is IMPOSSIBLE — measured, not assumed.**
`IAnnotation::GetLeaderCount()` returns **0** for every `swDatumTag` (three
tags, rocker-arm-support, 2026-07-16), while a `swGtol` on the same sheet
returns **1**. So GTOLs expose leaders and datum tags do not — consistent with
`IDatumTag` having no `GetLeaderCount` member in the type library at all. There
is no leader to measure, so the proposed "fail a tag whose leader is shorter
than X" gate cannot be built, and draw-D's ink-measured (1.05, 4.1) mm window
can never be read back through COM.

**The mechanism, and it is NOT "COM hides it" — a leader is only REGISTERED if
`SetLeader3` created it** (draw-D, verified in source). `add_datum_feature`
never calls `SetLeader3`; the only callers are `add_feature_control_frame`,
`add_surface_finish` and `add_property_linked_callout`. `_leader_segments_of`
gates on `GetLeaderCount()`, so **exactly the `SetLeader3`'d annotations report
leaders — precisely FCF + Ra**. And `add_datum_feature` cannot start calling it:
datum FEATURE symbols are absent from `SetLeader3`'s support list (only datum
TARGET symbols are, see above). So this is closed, not a missing call.

The subtlety worth keeping: **a datum tag's leader IS DRAWN and IS readable —
just not as a "leader".** It comes back as ordinary geometry in
`GetLineAtIndex` (rocker datum A: `line[0]`, a 12.6 mm vertical). So "the tag
has no leader" is false; "the tag has no *registered annotation leader*" is
true. Two independent confirmations: draw-D's arithmetic `segments = 2 × (FCF +
Ra)` fits all five of their sheets exactly (datum counts vary 1..3 across them
and never register), and rocker's datums B and C have visibly drawn leaders yet
still contribute nothing — which rules out "the leader exists but measures
zero". The ×2 is because one bent leader = 3 points = 2 `zip(pts, pts[1:])`
segments, reconciling their segment count with the `swGtol -> 1` COM reading.

Ink and COM agree to ~0.1 mm on this class (tag box 7.11 ink / 7.0 COM; datum B
leader 4.1 ink / 4.2 COM), so an ink measurement is a legitimate way to pin a
COM constant while the seat is busy. **I asserted this gate was "strictly better"
and let a threshold get bounded for it before ever checking the premise** — the
[[load-bearing-claims-need-a-repro]] failure, committed by the person who wrote
that note down.

**The replacement is better anyway: gate the DEFECT, not a proxy for it.**
`IDatumTag::GetTriangleAtIndex` gives the attachment triangle's three vertices
and the last 4 `GetLineAtIndex` lines give the box rectangle, so the actual
defect — *the triangle is drawn inside its own box* — is a direct geometric
test with **no threshold to calibrate**. Measured on the three rocker tags after
the 93a7a29 fix, every triangle sits clear of its box (datum A's is 10 mm above
it; datum B, the tightest correct tag, is 1.7 mm to the right of its box on a
4.2 mm leader — matching draw-D's 4.1 mm ink reading). TRAP: do NOT test the
triangle against the bbox of ALL the tag's lines — that bbox spans the leader,
which by definition runs to the triangle, so it reports "inside" for a
perfectly clean tag. The first cut of the probe did exactly this and called
every tag defective.

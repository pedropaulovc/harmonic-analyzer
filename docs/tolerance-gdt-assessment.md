# Tolerance & GD&T assessment

> Companion to [`tolerance-policy.md`](./tolerance-policy.md). The policy previously placed GD&T,
> surface finish, and drawing callouts out of scope; this assessment resolves each of them — *what*
> to add, *where*, and *how much* — calibrated to the actual audience: **a hobby machinist building
> from the book supplement on a manual mill + lathe with DROs.** The manufacturing-output scoping
> (drawings / DXF / CAM) is decided in §11 and reflected back into the policy.

Sources mined for this assessment: the book chapters 10–19
(`references/albert-michelsons-harmonic-analyzer/`), every `build_*.py` interface in
`cad/scripts/`, the hobby-machining + gear-cutting references
(`references/machining-for-hobbyists-getting-started/`, `references/gears-and-gear-cutting/`,
`references/machinerys-handbook/`), and three GD&T / engineering-drawing primers:
[*Understanding GD&T*](https://www.youtube.com/watch?v=G7wnGeR_69k) and
[*Understanding Engineering Drawings*](https://www.youtube.com/watch?v=ht9GwXQMgpo) (The Efficient
Engineer), and [*Tolerances Didn't Make Sense Until I Learned This*](https://www.youtube.com/watch?v=zhW1RXr-Wgk)
(Engineering Gone Wild). Those three establish that the **full** GD&T vocabulary — feature-control
frames, datum reference frames, true position, profile, runout, and the MMC/LMC modifiers with bonus
tolerance — is fair game here, applied functionally (see the §1 verdict).

---

## 1. The audience calibrates the values, not the vocabulary

The two reference books this supplement sits beside teach **`±` limits and fits only — zero
GD&T.** No feature-control frames, datums, true position, flatness/perpendicularity symbols, or
MMC modifiers appear anywhere in the measuring, lathe, mill, or drill chapters; the one
engineering drawing shown is dimensioned nominal-only. The gear book's governing maxim is
literally *"if it looks right it most likely is all right."* That the *books* omit GD&T is a fact
about the books — **not** a reason to omit it from the supplement. The supplement's job is to add
what the books lack; the three video primers in the sources above are exactly the "how to read a
feature-control frame" education a reader needs, so the deliverable **supplies** GD&T rather than
ducking it.

What the audience already owns and reads:

| Instrument | Resolution | Realistic repeatability |
|---|---|---|
| Steel rule | 1/64″ | ~0.4 mm |
| Caliper (dial/digital) | 0.0005″ / 0.01 mm | ~0.001″ (0.025 mm) |
| Micrometer | 0.0001″ / 0.01 mm | measurement uncertainty ~0.0005″ (0.013 mm) |
| Dial indicator on stand | 0.0005″ | the workflow used for "indicating" concentricity/parallelism |

Achievable **on the part**, careful work with a DRO:

| Regime | Band | Basis |
|---|---|---|
| Routine | **±0.05–0.13 mm** (±.002–.005″) | trial-cut to a mic; 3-jaw "within a few thou" |
| Best case, taking pains | **±0.013–0.025 mm** (±.0005–.001″) | 4-jaw indicated; finish cuts on the compound dial |
| Holes to size | drill **then ream/bore** | a drilled hole "is not precise"; ream for size + finish, bore for concentric/located |

In this audience's own words: **±.001″ is "tight," ±.005″ is "comfortable," ±1/16″ is "loose."**

**Verdict (drives everything below): use the full GD&T vocabulary (governing standard
ASME Y14.5-2018 — see §5.5), applied *functionally* — a geometric control appears only where the
part's function demands it, exactly as the error model in §2 allocates the budget.** This
**supersedes** an earlier "lite" verdict that capped the drawings at dial-indicator runout on the
theory that the audience couldn't parse feature-control frames. That cap is now retired: the
supplement ships a GD&T primer (the video sources are that primer), so the vocabulary is no longer
the constraint — *function* is. The audience data above is not a ceiling on the vocabulary, it
calibrates two things:

- **The tolerance *values*.** Stay near the routine **±0.05–0.13 mm** band and reserve the
  best-case **±0.013–0.025 mm** for genuinely fitted features; a callout the shop can't hold to is
  worse than none. The video's rule is this machine's rule: *"as accurate as necessary, not as
  accurate as possible."*
- **What the primer must teach.** How to read a feature-control frame, datums and datum
  precedence, true position with basic dimensions, the MMC bonus, and TIR on a dial indicator —
  so a reader who has only ever seen `±` prints can still build to the drawing.

So GD&T is used where it buys function — the summing **knife edge**, the 20 **cams**, and
**channel-to-channel consistency** (§2) — a **general tolerance block governs everything
unspecified** (an ASME decimal-place title-block table; ISO 2768 if drawing to ISO — §5.1/§11), and
the geometric controls stay few *because the error
model says so*, not because the reader is assumed unable to read them.

---

## 2. The error model sets where the tolerance budget goes

The output is a **static force balance summed through a knife-edge first-class lever**, with
total output travel "on the order of only a few millimetres" (ch. 18). Two consequences fix the
whole allocation:

- **A bias common to all 20 channels largely cancels** at the summing lever (and what survives is
  absorbed by the counter-spring tare and the amplitude-bar zero). Shared, systematic error is
  cheap.
- **A per-channel *inconsistency* injects straight into the sum** as harmonic error: one stiff
  pivot, one off-phase cam, one mismatched spring. Per-channel scatter is expensive.
- Because output travel is a few mm, **any friction / lost motion / play at the summing knife edge
  is a large fraction of the signal** — which is exactly why the original used a knife edge there.

> **Allocation principle.** Spend the tolerance budget on (a) the summing **knife edge**, (b) the
> 20 **cams**, and (c) **channel-to-channel consistency**. Relax everywhere the book itself shows
> wear, hand-work, or a designed-in adjustment.

The book is unusually explicit about where it is *forgiving*, and those are direct licences to
loosen: the cone↔cylinder mesh runs at an oblique angle with "distinct wear patterns" (partial
engagement is tolerated and the centre distance is deliberately adjustable); the connecting rods
are "rough-finished"; the measuring stick's graduations are "hand stamped … unevenly spaced"; the
counter-spring post is gouged by its own set screw. None of these need a tight number.

---

## 3. What's already covered, and the three gaps

**Covered today** (`tolerances.yaml` + Gate-E audit + analytic asserts in the build scripts):

- Three general linear grades — `machined_block` ±0.10, `plate_profile` ±0.20,
  `visual_noncritical` ±0.50.
- Named fit classes with clearance/backlash bands — `shaft_in_bushing`, `gear_mesh`,
  `cone_drum_oblique_mesh`, `cam_follower_contact`, `sliding_amplitude_bar_on_rocker`,
  `spring_eye_threading`, `fastener_clearance`.
- Every part carries `material` / `tolerance_class` / `process` (audited), `fit_class` where it
  moves. Build scripts assert clearance margins and raise on violation.

**Gap 1 — no precision linear grade.** The tightest class (`machined_block` ±0.10 ≈ ±.004″) is
**too loose to deliver the fits the policy itself specifies** (see §4). There is nothing for the
"thou" features.

**Gap 2 — no geometric controls.** Runout, the rocker form radius, knife-edge straightness/
squareness, and the channel-stack coplanarity are entirely unexpressed. These are the places
geometry — not size — is the functional requirement; §5.2 now expresses them as proper
feature-control frames (runout, profile, perpendicularity, position) over the full GD&T vocabulary,
not as prose.

**Gap 3 — no surface finish.** Sliding/running surfaces (journals, bores, the knife edge and its
seat, the rocker slide) have no finish spec; a rough bore runs untrue and wears.

---

## 4. Findings — the numbers don't currently close

These are concrete inconsistencies to reconcile, surfaced by cross-checking the fit classes
against the modeled geometry. **They are pre-existing; flag and fix before publishing any
tolerance.**

1. **Fit class vs. linear grade.** `shaft_in_bushing` wants **0.025–0.075 mm** diametral
   clearance, but a bore and a shaft both held to `machined_block` ±0.10 stack to **±0.20 mm** of
   clearance variation — the tolerance swamps the fit ~3–8×. A fit is only real if the part
   tolerances are tight enough to deliver it. → fitted features need the new **precision** grade
   (§5.1), and the audit should *enforce* that any `fit_class` part carries it on the fitted
   feature.

2. **Modeled clearance vs. fit class.** The CAD pivot/fulcrum bushings are **Ø6.5 bore on a Ø6.35
   shaft = 0.15 mm** diametral clearance (`build_pivot_bushing.py`, `build_lever_bushing.py`) —
   itself **2× the top** of the `shaft_in_bushing` band (0.075). The 0.15 mm reads as a deliberate
   render-friendly visible gap, not a machining fit. → decide one story: either tighten the model
   to the fit class, or widen the class to the "beginner-safe generous slip fit" the policy
   describes (a ~0.10–0.15 mm running fit on Ø6.35 is RC6-ish and perfectly fine for a
   hand-cranked machine) — but the config and the geometry must then agree.

3. **Publish a DP/PA table per *meshing domain* — do not unify.** The machine has **several
   independent gear systems at different pitches**, each internally consistent — they do not mesh
   across domains, so they must *not* be collapsed to one DP:
   - **cone↔cylinder train — DP 49.82 / 14.5° PA** (`machine/gear_train.yaml diametral_pitch:
     49.82`; `build_cylinder_gear.py` imports the train `DP` from `build_cone_gear`, so the whole
     20-pair train shares it by construction);
   - **crank-drive pair — DP 26.57** (`gear_train.yaml crank_drive_diametral_pitch`);
   - **paper-drive rack↔pinion — DP 30** (`build_rack_pinion.py`, which carries a hard note that it
     must *not* couple to the train DP or the rack silently interferes).

   The gear book's "**never mix pressure angle / pitch**" rule applies **within a meshing pair**, not
   across the machine. → publish one authoritative `module/DP + PA + tooth-count` row **per domain**;
   a single unified DP would force distinct non-meshing systems to the wrong pitch. (My earlier draft
   had the cone/cylinder train at DP 30 — that was backwards; the rack is the DP-30 system.)

4. **The Ø6-tooth gear is marginal by construction.** `build_cone_gear.py` leaves a **0.49 mm wall**
   between the T006 root and its bore (root r 0.89). That is a real machining hazard, not a CAD
   artifact — call it out as the hardest part to make, and note the period-correct mitigation: the
   four tip gears were a **harder yellow metal** (Muntz/manganese bronze), which is why they show
   the most wear yet survived.

5. **Rocker radius vs. bar length disagree in the model.** The book states the rocker's concave
   radius *equals* the amplitude-bar length (ch. 14), but the CAD implements **R = 800 mm**
   (`build_rocker_arm.py`) against a **812.8 mm** bar (`build_amplitude_bar.py`, 32″) — a **12.8 mm**
   gap, and the rocker docstring already flags the book relationship. → spec the rocker radius as the
   **current 800 mm nominal explicitly** (not "= bar length"), and reconcile the 12.8 mm before it
   becomes a toleranced callout — otherwise a "R = bar length ±0.5" rule puts the existing model
   instantly out of tolerance and a generated drawing would force an unintended geometry change.

---

## 5. Recommended additions

### 5.1 Add a `precision` linear grade

| New grade | Tolerance | Applies to |
|---|---|---|
| `precision` | **±0.025 mm** (±.001″) | any fitted feature: bearing bores, shaft journals, the knife-edge seat, cam-bore/OD, gear bores |

Keep the three existing grades for everything else. The rule becomes: **the feature that carries a
fit gets `precision`; the rest of the part stays at its block grade.** A part can therefore carry a
default `tolerance_class` *and* a tighter grade on its critical feature (encode as
`critical_features`, §8).

### 5.2 The GD&T controls to add — full vocabulary, applied by function

Each control below is a real **feature-control frame** authored onto the model (§8) and imported
onto the drawing — *and* paired with the shop procedure that holds and inspects it, so a reader who
builds by feel still knows what the frame demands. Organised by the five GD&T categories; a row
appears only where the error model (§2) says geometry matters. A **feature of size** (bore,
journal, opposed faces) takes a Ø tolerance zone on its axis / median plane; a **surface feature**
takes a zone between two offsets of the surface — the distinction changes what the same symbol
means, so it is called out per row.

**Form** (single feature, no datum)

| Control | Where it applies | Target | Hold / inspect |
|---|---|---|---|
| **Flatness** | knife-mount seat face; pedestal + base mating faces; top-frame cross-rib seat | ≤0.02–0.05 mm | surface-grind or single-setup face; dial-indicator sweep on 3 jacks, or CMM |
| **Straightness** (axis, Ø zone) | `pivot-shaft`, `fulcrum-shaft`, `cone-gear-shaft` tip, `crank-pin` axes | ≤0.02–0.05 mm over length | between-centres turn + steady; indicate on Vee-blocks. Rule #1 (below) already bounds it at MMC |
| **Circularity / Cylindricity** | gear + cam blanks, running journals, bearing bores | folds into runout, below | 4-jaw indicate true; rotate-and-probe, polar plot |

**Orientation** (feature to datum)

| Control | Where it applies | Target | Hold / inspect |
|---|---|---|---|
| **Perpendicularity** | pivot-bore axis ⟂ mount face (`rocker-arm`, `summing-lever`, `knife-mount`, pedestals); **knife edge ⟂ motion plane** | ≤0.02–0.05 mm | bore the hole **in the setup that faces the mount**; indicate off a square |
| **Parallelism** | the two `knife-mount` seats coplanar / equal-height; amplitude-bar slide face to base | parallel, ≤0.05 mm | shim to a common height at assembly; indicate |
| **Angularity** | *available* for the oblique cone↔cylinder mesh seat, but that mesh is adjustable / loose (§2) — **not required** | — | sine bar, if ever toleranced |

**Location** (feature-of-size position from a datum reference frame)

| Control | Where it applies | Target | Hold / inspect |
|---|---|---|---|
| **Position (true position)** — cylindrical zone about a **basic-dimension** location; **M** where a clearance hole benefits from bonus | `rocker-arm-support` 4× foot holes; `summing-lever` 20 spring holes at 7.0565 pitch; channel pivot / lever bores; `knife-mount` fastener holes (once modeled); crank + frame bolt patterns | Ø0.1–0.2 mm at MMC, loosening with bonus | drill from a common fixture / jig; CMM the hole centres against the basic grid |

Position replaces a `±`-boxed hole location with a **round** zone evenly distributed about the true
position (a square `±` zone is both too tight on the diagonal and too loose on the axes), and it
names the datum precedence explicitly — for a hole the primary datum is normally the face the axis
must be ⟂ to.

**Profile** (form + orientation + location of a shaped feature at once)

| Control | Where it applies | Target | Hold / inspect |
|---|---|---|---|
| **Profile of a surface** | `rocker-arm` **R800 concave** form (the book's one stated geometric req — profile is its natural control); `cylinder-gear` cam eccentric profile; involute **gear-tooth flanks** | 0.05–0.1 mm zone following the true profile | form-cut / CNC profile; CMM scan against the nominal curve. Profile-without-datum on a nominally flat face ≡ flatness |

**Runout** (rotating features about a datum axis)

| Control | Where it applies | Target | Hold / inspect |
|---|---|---|---|
| **Circular runout** | gear OD / pitch to bore axis; cam OD to bore; all journals; magnifying wheel | ≤0.025–0.05 mm TIR (.001–.002″) | mandrel or bore-and-cut one setup; rotate + dial gauge per cross-section |
| **Total runout** | full-length control where a whole cylindrical face must run true (long journals, gear bodies, wheel rim) | ≤0.05 mm TIR | dial gauge traversed **along** the axis |

Bore-to-pitch concentricity on a cut gear (the gear book's *"imperative … no eccentricity"*) is now
just runout to the bore-axis datum — no separate control. Datums for every framed feature follow the
per-class rule in §5.4, listed in **precedence order**: the sequence is load-bearing because it
fixes how the part is immobilised (3-2-1: primary datum ≥3 contacts, secondary ≥2, tertiary ≥1), so
inspection is repeatable.

**Modifiers & Rule #1 (why the fits actually close).**

- **MMC / LMC / RFS + bonus tolerance.** A position tolerance defaults to **RFS** (the zone is
  fixed). Adding **M (MMC)** grows the zone by the actual feature's departure from maximum material
  — a clearance hole cut oversize may sit less accurately and still assemble, exactly the bonus a
  hand-built machine wants on its bolt / foot / pin patterns. **L (LMC)** is the mirror, for a hole
  near an edge where minimum material (thin wall) is the risk. The modifier is encoded on the frame
  (§8); the worked bonus arithmetic is in the *Understanding GD&T* / *Tolerances* primers.
- **Rule #1 / the Envelope Principle** (ASME default, §5.5): the MMC size of a feature of size is a
  perfect-form envelope its surface may not cross, so **size limits already bound form** — a pin at
  Ø-max must be straight; a smaller pin may bow within the envelope. This is why a size-only pin
  still drops into its mating hole, and it is the right default for this machine's slip fits. Add a
  separate straightness/flatness only where a feature must stay straight *below* MMC.

**Still omitted — by function, not by audience:** composite position frames, symmetry, MMC applied
to *datums*, and profile on the frame castings. Each is dropped because **no feature here needs it**
(no pattern-to-pattern datum shift, no symmetric slot that must be centred, no cast face carrying a
fit), not because a reader can't parse it — add any of them the moment a part earns it.

### 5.3 Add a `surface_finish:` block

| Class | Ra | Where |
|---|---|---|
| `bearing` | **0.8–1.6 µm** (32–63 µin) — reamed/finish-bored | shaft journals, running bores, knife edge + seat, rocker slide, amplitude-bar foot |
| `finish` (default machined) | **3.2 µm** (125 µin) — sharp-tool finish pass | general machined surfaces, gear bores |
| `none` | — (no callout) | non-contacting faces, gear flanks (form-cut HSS is "good enough"), cosmetic / rough parts |

Most surfaces get **no callout** — that matches the books' silence and the book's "rough-finished"
connecting rods. Spec finish only where a surface bears or slides. (Handbook rule of thumb if a
reader wants one: roughness ≤ 1/8 of the dimensional tolerance.)

### 5.4 Datum reference frames (per part class)

A datum reference frame is stated per part class in **precedence order** (primary → secondary →
tertiary) — the order fixes how the part is immobilised (3-2-1) and therefore how every framed
tolerance in §5.2 is inspected, so it must be identical across the run to stay repeatable:

- **Rotating parts** (gears, wheels, pinions, shafts): primary = the **bore / journal axis**,
  secondary = a **faced end**. Cut features off the bore in one setup → runout falls out for free.
- **Pivoting parts** (rockers, levers, knife mounts): primary = the **mounting face**, secondary =
  the **pivot bore** located square to it in the same setup; tertiary = an edge or second hole.
- **Frame / mounting parts** (base, pedestals, crossbars, portals): primary = the **mating face**,
  secondary/tertiary = the **bolt pattern**; everything else is reference.

### 5.5 Governing standard — ASME Y14.5-2018 (Rule #1); ISO noted

Pick **ASME Y14.5-2018** as the drawing standard, for two reasons the primers make explicit: its
default **Rule #1 (Envelope Principle)** ties form to the MMC size limit, so a size-only feature is
still guaranteed to assemble — the right default for a hand-built machine full of slip fits — and
it drops the fragile concentricity/symmetry controls (removed in the 2018 edition) that this machine
never needed anyway (runout and position cover their intent). Note the alternative for a reader
working to **ISO**: ISO defaults to the **Independency Principle** (size and form independent, so a
within-size part may still be bent), and needs an explicit **Ⓔ** to invoke the envelope — the mirror
of ASME's **Ⓘ** for independency. State the chosen standard in the drawing title block (§11) so the
default rule is unambiguous.

Y14.5-2018 governs the **dimensioning & tolerancing** (GD&T, the FCFs, Rule #1); the multiview
**projection** and sheet **format** follow its companion ASME standards (Y14.3 and Y14.100), so
"draw to ASME Y14.5" below is shorthand for the Y14 family with Y14.5-2018 as the tolerancing rule.

---

## 6. Per-subsystem recommendations (parts)

Tier: **T1** = spend the budget here · **T2** = moderate · **T3** = leave loose / cosmetic.
"Add" lists only what is *new* beyond the existing `material/tolerance_class/process/fit_class`.

> This section tiers the parts by **tolerance/fit** effort. The **machinability** pass for the same
> T1 parts — stock, setups, thin walls, internal corners, CNC-vs-manual routing, per feature — lives
> in the companion [`machining-dfm.md`](./machining-dfm.md).

| Subsystem · part(s) | Tier | Add |
|---|---|---|
| **Summing lever** `summing-lever`, `knife-mount` | **T1** | knife-edge **straightness + ⟂ to motion plane**; **parallelism/equal height** of the two mounts; `precision` on the seat; `bearing` finish on edge + seat. **Material:** the lever is gray cast iron and the mount brass — neither hardens to a durable edge, so the hardness callout needs a **hardened tool-steel knife-edge insert** (e.g. O1/W1, pinned/screwed into the lever) riding a **hardened-steel seat** set into the mount; spec the insert + seat as separate hardened parts (add to `materials.yaml`), *not* "harden the casting." *Least forgiving interface in the machine.* |
| **Cylinder gears + cams** `cylinder-gear`, `connecting-rod` | **T1** | cam **eccentricity = amplitude** (hold it), **runout of cam OD to gear bore** ≤0.05 mm; **angular phasing to the ~3 mm alignment notch** (per-channel phase datum — set at assembly); `precision` on bore; cam OD `bearing` finish; **rod cam-bore (the `cam_follower_contact` surface) `bearing`; rod *body* `none`** (book: rough — the exemption is the visible body, not the bearing bore). *The 20 cams are the function generators.* |
| **Cone gears** `cone-gear`, `cone-gear-shaft` | **T1** | **bore-to-pitch runout** ≤0.05 mm; **DP 49.82 / 14.5° PA shared across the whole cone↔cylinder train** (its own domain — Finding 3); flag **T006 0.49 mm wall** + harder tip metal (Finding 4); `precision` on bore. Mesh itself stays **loose** (oblique, adjustable centre distance). |
| **Pivots & bushings** `pivot-shaft`, `fulcrum-shaft`, `pivot-bushing`, `lever-bushing` | **T1** | reconcile the **0.15 vs 0.025–0.075 mm** fit (Finding 2); `precision` on bore + journal; `bearing` finish; **all 19 spacers one length, one setup** (channel pitch 7.0565 mm); shaft straightness. |
| **Rocker arms** `rocker-arm`, `rocker-arm-support` | **T1** | **concave radius R800 nominal** (form, ±0.5 mm; book ch.14 says "= bar length" = 812.8 mm — **reconcile, Finding 5**; stamp the model's R800, never the bar length). Pivot bore **square** to face; slide surface `bearing` finish. |
| **Amplitude bars** `amplitude-bar` | **T2** | preserve **length** (~80 cm — it linearizes the transfer; don't shorten); notch fit snug-sliding (`sliding_amplitude_bar_on_rocker`); straightness mild; **notch foot (the sliding-contact surface) `bearing`; bar *body* `none`**. Precision here is **position repeatability**, not part geometry. |
| **Drive train** `crankshaft`, `crank-pin`, `crank-drive-gear`, `crank-pinion`, `crank-arm`, `crank-handle` | **T2** | **taper-pin** crank-to-shaft index (repeatable, zero-backlash angular registration) — ream matching taper; gear bores `precision` + runout; handle/arm loose. |
| **Paper drive** `rack-pinion`, `platen-rack`, `pinion-bar`, transgear set, chain | **T2/T3** | rack/pinion **DP 30 / 14.5°** (Finding 3); backlash 0.30 mm is fine; chain clearances **loose** (link-to-link contact tolerated). Paper transport is the *time axis*, not the summed signal — moderate. |
| **Magnifier & pen** `magnifying-wheel`, `magnifying-lever`, `magnifying-bracket/clamp`, `magnifying-vertical-rod`, pen parts | **T2** | wheel/lever bores `precision` + runout on the wheel; linkage pivots squareness. Amplifies output, so play here is visible — but downstream of the sum. |
| **Frame** `harmonic-base`, `top-frame`, pedestals, clamps, columns, `gooseneck*` | **T3** | mating-face flatness "as-machined" + bolt-pattern location; column slip fits (Ø25.4 in 25.5–25.6) already fine. Cast-iron castings stay forgiving. |
| **Springs** `channel-spring-installed`, `counter-spring` | **T2** | **match rate + free length across the 20 channels** (consistency, not absolute rate); counter spring is the **coarse tare** — leave loose. |
| **Measuring stick** `measuring-stick` | **T3** | leave loose — original was hand-stamped & uneven; what matters is **one stick sets all 20 bars**. |
| **Fasteners / misc** `hex-bolt`, `lag-screw`, `hanger-screw`, `fillister-screw`, `thumb-screw`, `nameplate`, knobs | **T3** | `fastener_clearance` close/normal as-is; no additions. |

---

## 7. Assembly-level tolerances

Express these as **consistency + fit-at-assembly**, not absolute position — that matches both the
error model and how the machine was actually built and trimmed.

- **Channel pitch & coplanarity (the real assembly precision):** the 7.0565 mm channel spacing and
  the coplanarity of the 20 rockers / 20 levers are set by the **spacer-bushing lengths** and the
  **pivot-shaft straightness**, not by 20 independently located holes. → machine the spacers
  together; ream the pivot bores through a common fixture/stack. This is where "channel-to-channel
  consistency" is won or lost.
- **Gear mesh centre distances:** **set at assembly by feel** for light backlash; the cone set
  *pivots out of engagement* by design, so spec nominal + "adjust for a little backlash, never
  zero" rather than a tight centre distance.
- **Knife-edge supports:** shim the two mounts to a **common height + parallel** so the lever rocks
  true.
- **Summing-lever spring holes:** the 20 attachment points at a consistent pitch give each spring a
  consistent moment arm — drill them from one fixture.
- **Counter-spring height:** the designed-in **tare** — explicitly loose; it exists to absorb the
  residual imbalance of the 20-spring bank.

---

## 8. How to encode it — config → SLDPRT PMI → drawings (the automation backbone)

The repo's philosophy is "tolerance is design source, lives in config, flows to custom properties +
gets asserted." Keep that, and **extend it one critical step: the tolerance data must be embedded
into the SLDPRT *as PMI during the build*, read from YAML — so a drawing consumes it automatically
instead of anyone re-typing it.** A custom-property *string* (`tolerance_class: machined_block`)
is metadata; a drawing cannot dimension from it. A driving-dimension tolerance or a DimXpert
geometric tolerance *is* model geometry a drawing imports for free. So the source of truth stays the
YAML, but the build script writes it onto the model, three layers deep (all API-verified, bundle
v3.3.0; **DimXpert is included with every SOLIDWORKS license — confirmed for the Makers seat**, see
§11):

1. **Size ± tolerances on the driving dimensions.** Where a build script already sets a feature's
   driving dimension (bore Ø, journal Ø, length), additionally stamp its grade's tolerance:
   `IDimension.SetToleranceType` (e.g. bilateral) + **`IDimension.SetToleranceValues(max, min)`** for
   the numeric ± (read from `tolerances.yaml`). **Not `SetToleranceFitValues`** — that one is marked
   *obsolete* in the API and takes fit-class *strings* (`"H7"`), not numeric values, so it won't
   stamp `±0.025`; the modern numeric path is `SetToleranceValues` / `IDimensionTolerance`. These are
   exactly the dimensions a drawing pulls via
   `IDrawingDoc.InsertModelDimensions` / `InsertModelAnnotations3` — the print inherits every ± with
   no re-authoring, fully associative.
2. **Geometric tolerances + datums as DimXpert PMI.** For the full `geometric:` set (§5.2) —
   flatness, straightness, perpendicularity, parallelism, **position**, **profile**, circular/total
   **runout** — plus datums and their precedence, author them during the build via
   `IDimXpertManager.DimXpertPart` → `IDimXpertPart.InsertDatum` / `InsertSizeDimension` /
   `InsertLocationDimension` / `InsertGtol` (+ typed interfaces `IDimXpertConcentricityTolerance`,
   `IDimXpertOrientationTolerance` for perp/parallel, `IDimXpertFlatnessTolerance`…). **DimXpert
   authors circular & total runout natively** — `IDimXpertPart.InsertGtol` takes a
   `swDimXpertGtolType_e`, and the online 2026 API reference confirms the members
   `swDimXpertGtolType_CircularRunout` (12) and `swDimXpertGtolType_TotalRunout` (13) — alongside
   Perpendicularity (7), Parallelism (8), Position (9), Concentricity (11), etc. (On read-back these
   share the base `IDimXpertTolerance`, type-discriminated via `IDimXpertAnnotation::Type` — there is
   no dedicated named *subclass*, which is what misled an earlier draft.) Note: this enum is **absent
   from offline bundle v3.3.0**; the values above are from help.solidworks.com/2026. Classic
   `IModelDoc2.InsertGtol` + `swGcsCIRCRUNOUT` / `swGcsTOTALRUNOUT` (`swGtolGeomCharSymbol_e`) remains
   a fallback. (Concentricity/symmetry are available in the enum but unused — ASME Y14.5-2018 dropped
   them and §5.2 covers their intent with runout/position.)
   - **True position needs basic dimensions.** The located dimensions a position frame references
     must be stamped **basic** (boxed, no ± ) — `IDimension.SetToleranceType(swTolBASIC)` on the
     driving locating dims — otherwise the general `±` block also applies and double-tolerances the
     hole. **Material-condition modifiers** (MMC/LMC) ride the GTol, set on the DimXpert position
     tolerance (`IDimXpert*Tolerance` material-condition property) / passed to the classic
     `InsertGtol` frame; RFS is the default when omitted.
3. **Surface-finish symbols** from `surface_finish:` → `IModelDoc2.InsertSurfaceFinishSymbol2` on the
   bearing/sliding faces.

The PMI lives in **annotation views** on the model; a drawing built from that model imports all of
it automatically (`InsertModelAnnotations3`) — the drawing script *places views + imports model
items + arranges*, it does not re-author tolerances. **Edit the YAML → rebuild → the SLDPRT PMI and
every drawing update together.** The **guaranteed, add-in-free** consumption path is the **2D
drawing** (drawings are core SOLIDWORKS): `InsertModelAnnotations3` pulls the embedded PMI with no
MBD license. **STEP AP242 *with PMI* is not add-in-free** — SOLIDWORKS' "Publish to STEP 242" is an
MBD feature ("The SOLIDWORKS MBD add-in is not part of any role. You need a stand-alone license",
[SW Help 2025](https://help.solidworks.com/2025/english/solidworks/sldworks/t_share_models_step242.htm)),
so `PublishSTEP242File` carrying PMI must be **gated behind the same runtime MBD probe** as 3D-PDF
(§11) — not offered as a guaranteed fallback. (Geometry-only STEP export via the normal Save-As path
is always available; it just won't carry the tolerances.)

Home it next to the existing per-part stamping: an `apply_pmi(part, features)` in `_common.py`
alongside `apply_custom_properties` / `apply_material`, driven by the new `critical_features` rows.

Concretely:

**`tolerances.yaml`** — add three blocks:

```yaml
general:
  precision: { tolerance: "+/-0.025", applies_to: "fitted features: bearing bores, journals, knife seat, cam/gear bores" }
  # NB (Finding 1/2): ±0.025 on BOTH mating parts = 0.10 spread — only valid where the fit band ≥0.10.
  # The shaft_in_bushing band (0.05 wide) needs each feature at ≤±0.012, or the band widened. Reconcile
  # before enabling Gate-E rule 2; pick ONE — tighter grade OR wider band — and record it here.
  # ...existing machined_block / plate_profile / visual_noncritical...

surface_finish:
  bearing: { ra_um: [0.8, 1.6], applies_to: "journals, running bores, knife edge+seat, slide surfaces" }
  finish:  { ra_um: 3.2,        applies_to: "general machined (default)" }
  none:    { applies_to: "non-contacting, gear flanks, cosmetic/rough" }

geometric:            # keyed by GD&T characteristic (§5.2); each = tolerance zone + how to hold it
  flatness:         { tol_mm: 0.05, applies_to: "knife-mount seat, pedestal/base mating faces", how: "single-setup face/grind; indicate on 3 jacks or CMM" }
  straightness:     { tol_mm: 0.05, applies_to: "pivot/fulcrum/cone-gear-shaft + crank-pin axes", how: "between-centres + steady; Rule #1 already bounds it at MMC" }
  perpendicularity: { tol_mm: 0.05, applies_to: "pivot-bore axis to mount face; knife edge to motion plane", how: "bore in the setup that faces the mount" }
  parallelism:      { tol_mm: 0.05, applies_to: "the two knife-mount seats; amplitude-bar slide", how: "shim coplanar/equal-height at assembly" }
  position:         { tol_mm: 0.15, modifier: MMC, applies_to: "support foot holes, 20 spring holes @7.0565, channel bores, bolt patterns", how: "drill from a common jig; basic dims locate the true position" }
  profile_surface:  { tol_mm: 0.1, applies_to: "rocker R800 concave form, cam eccentric profile, gear-tooth flanks", how: "form-cut/CNC; CMM scan vs the nominal curve" }
  runout:           { tir_mm: [0.025, 0.05], types: [circular, total], applies_to: "gear bore->pitch, cam->bore, journals, wheel", how: "mandrel / bore-and-cut one setup; dial gauge" }
  # feature notes that resolve to the characteristics above:
  knife_edge:       { chars: [straightness, perpendicularity, parallelism], applies_to: "summing-lever edge + seat", how: "straight, sharp; hardened tool-steel insert + hardened-steel seat (separate parts, not the cast/brass parent); seat parallel/equal-height" }
  rocker_radius:    { char: profile_surface, value: 800, tol_mm: 0.5, applies_to: "rocker-arm top", note: "book says = bar length 812.8 — reconcile (Finding 5)" }
```

**`parts/*.yaml`** — add optional fields, required only for the ~10 T1 parts. **Each
`critical_features` row needs an API-stable *selector*, not just a human label** — `apply_pmi` and
the write-back audit (Gate-E rule 4) have to resolve the exact model item to attach/query PMI, and a
free-text `feature:` string can't drive `SelectByID2` / DimXpert. So the build script must give the
target a **stable handle** the row references — the cleanest is a **named dimension / named feature**
the build script already creates (`doc.Parameter("knife_seat_dia@Sketch3")`, or rename the feature),
which is also exactly what a drawing imports by name. (`select:` below is that handle; `feature:` is
kept only as a human comment.)

```yaml
summing-lever:
  # ...existing...
  surface_finish: bearing
  critical_features:
    # select: API-stable model item (named dim / feature) the build script creates and PMI attaches to.
    # A row is a feature-control frame: characteristic + tolerance + datum precedence (+ modifier).
    - { select: "knife_seat_dia@Sketch3", feature: "knife edge", grade: precision, geometric: knife_edge, datums: [A, B], finish: bearing }
    # position example — the 4 support foot holes, MMC bonus, located by basic dims off datums A|B|C:
    - { select: "foot_hole_pattern@Sketch2", feature: "4x foot holes", geometric: position, modifier: MMC, datums: [A, B, C] }
```

The build script owns the contract: it must **name** that dimension/feature (not rely on
auto-generated `D1@Sketch3` names, which churn) so the `select:` key stays valid across rebuilds.

**Gate-E audit (`verify.py`)** — evolve the existing tolerance audit to *enforce the new
invariant*, not just presence of fields:

1. Any part with a running/locating `fit_class` (`shaft_in_bushing`, `gear_mesh`,
   `cam_follower_contact`, `sliding_*`) **must** name a `precision` feature + a `surface_finish`
   on the fitted feature — closes Gap 1 / Finding 1.
2. **Tolerance-stack check:** for each fit, assert the worst-case feature-tolerance stack stays
   **inside** the fit's clearance band — i.e. `tol(bore) + tol(shaft) ≤ band_width`. **This is the
   crux of Finding 1/2 and the current numbers do NOT satisfy it:** the `precision` grade (±0.025 ⇒
   0.05 total per feature) on *both* mating parts gives a 0.10 mm worst-case clearance spread, which
   cannot fit the 0.05 mm-wide `shaft_in_bushing` band (0.025–0.075) for *any* nominal. So this rule
   is **unsatisfiable as written** and must not be enabled until the grade/band are co-designed —
   either **widen the band to ≥ 0.10** or **add a tighter grade** (each fitted feature ≤ ±0.0125 to
   live inside a 0.05-wide band). **Gate this check on the Finding 1/2 reconciliation** (one decision,
   recorded in `tolerances.yaml`); enabling it before then fails every otherwise-compliant pair.
3. Geometric/finish class names must resolve in the new blocks (same pattern as the existing
   `tolerance_class` / `fit_class` resolution).

4. **PMI write-back check:** for each `critical_features` row, read the model back and assert the
   tolerance/GTol/finish was actually applied (DimXpert + annotations are queryable) — so the audit
   verifies the data reached the SLDPRT, not merely that the YAML named it.

**Build scripts** — they already assert clearances; have them additionally (a) assert the chosen
tolerance grade is **compatible with** the modeled clearance (the stack check above, at the source),
and (b) call `apply_pmi(...)` so the embedding happens on every build, not as a later pass. This
catches a future edit that loosens a grade below its fit, and keeps the model and the drawings in
lockstep with the config.

---

## 9. Priority roadmap

- **Tier 1 (do first, ~10 parts):** knife-edge trio · cylinder-gear cams + connecting-rod ·
  cone/cylinder gear bores · pivot/fulcrum shafts + bushings · rocker-arm radius. Plus the three
  **Findings fixes** (precision grade, reconcile pivot clearance, publish the single DP/PA table).
- **Tier 2:** rack-pinion + transgear, magnifier/pen linkage, crank taper-pin index, spring matching.
- **Tier 3 (leave loose / document as forgiving):** frame castings, measuring stick, counter-spring
  post, chain, fasteners, nameplate, handle.

## 10. What the supplement actually ships

- **Generated 2D PDF shop drawings (Tier-1 first) that auto-consume the PMI embedded in each
  SLDPRT** (§8) — the tolerance/fit/finish/GD&T data is authored onto the model from the YAML at
  build time, so the drawing imports it rather than re-typing it. Draw to **ASME Y14.5-2018** (§5.5)
  and stamp the standard + projection-angle symbol in the title block (§11). Pair with a **GD&T
  primer sidebar** (the video sources are that primer): how to read a feature-control frame, datums
  and datum precedence, **true position + basic dimensions**, the **MMC bonus**, circular/total
  **runout (TIR)**, what "slip / transition / press fit" mean in thou, and "bore don't drill, single
  setup, indicate true." The GD&T is **full** — the vocabulary is not the limit, *function* is: a
  frame appears only where the error model (§2) rewards it, and a general tolerance block governs
  the rest.
- **The single authoritative gear table** (DP/module, 14.5° PA, the 20 cone tooth counts 6→120, the
  120-tooth cylinders, the rack/pinion) — the one place precision *and* internal consistency both
  matter.
- Update `tolerance-policy.md` §"Scope": GD&T (full ASME Y14.5), surface finish, and critical-feature
  callouts are **in scope**; the drawings/DXF/CAM question is decided in §11 (not deferred).

---

## 11. Manufacturing outputs (drawings / STEP→CAM / DXF) — decided, not deferred

The original policy deferred "2D drawings with tolerance callouts, DXF/CAM outputs." Reassessed
against the actual audience and the toolchain, each is now a decision, not a defer.

**Toolchain (corrected).** The build is **manual-primary by deliberate choice** — manual mill +
lathe with DROs, chosen for fidelity to a hand-built 1898 machine — **with a PM-30MV CNC available
for the repetitive, high-count parts**: the **20 cams**, the **19+19 spacer bushings** (the
`pivot-bushing` and `lever-bushing` banks — different OD and length, both 19-off), and the
**cone/cylinder gear train**. That is exactly where channel-to-channel *consistency* (§2's expensive
error mode) is hardest to hold by hand, so CNC is the right tool there even though manual remains the
main path for one-off parts. An earlier draft of this section wrongly called the toolchain
manual-only (and the PM-30MV a "manual mill") and scoped CAM/DXF out on that basis; the DXF and CAM
decisions below are re-derived from the corrected toolchain.

### 2D shop drawings — IN SCOPE (the vehicle that makes everything above real)

A hobby machinist works from a **dimensioned, toleranced print at the mill/lathe** — not a 3D
model, a STEP file, or a YAML registry. Every tolerance, fit, runout, and finish spec in §§5–7 only
reaches the bench on a drawing; custom properties + the Gate-E audit are the metadata/BOM layer, not
something a person cuts metal from. The book (Hammack) is a *photo* book with **no** shop drawings,
so supplying them is the single highest-value contribution this supplement makes.

- **Feasible on this seat — API verified (offline bundle v3.3.0).** The repo already drives
  `SaveAs3` for STEP/STL (`export_models.py`, `cut_release.py`), so PDF export of a drawing is the
  same mechanism; the COM API creates drawing docs + views (`IDrawingDoc.CreateDrawViewFromModelView3`)
  and — the key point — **imports the PMI the build already embedded in the SLDPRT (§8)** via
  `InsertModelAnnotations3` / `InsertModelDimensions`. The drawing script *places views, imports
  model items, and arranges* — it does **not** re-author tolerances. (The `InsertGtol` /
  `InsertSurfaceFinishSymbol2` / `InsertDatumTag2` calls live in the **build** per §8, on the model,
  not on the drawing.)
- **Consistent with the repo philosophy + single source of truth.** Drawings become **generated
  artifacts** (`cad/out/drawings/<dashed>.PDF`), scripted from the config — not hand-drawn — exactly
  like the renders/STL/STEP. Because the tolerances are embedded in the model from the YAML,
  editing a fit in `tolerances.yaml` and rebuilding updates the SLDPRT PMI **and** every drawing in
  one pass; nothing dead-ends in metadata.
- **Scope by tier.** Generate drawings for the **Tier-1 precision-critical parts first** (the ~10
  in §6/§9), which carry the `precision` grade, runout, finish, and critical-feature notes; then
  expand to all parts. New doit task `drawing:<stem>` **takes the COM seat lock** (it needs
  SolidWorks — wrap its subprocess in `_com_seat`), feeding a `release` PDF set.
- **Caveat.** Programmatic drawing layout is brittle; expect to hand-finish view placement / leader
  routing on the first pass and capture the working recipe — the repo already hand-tunes render
  cameras the same way.
- **Drawing conventions the generator must honour** (from the *Understanding Engineering Drawings*
  primer, so the print is standard-legible):
  - **Title block** (bottom-right): part name/number, scale, material + finish, author, and — because
    it fixes how the views read — the **projection-angle symbol** and the governing **standard
    (ASME Y14.5-2018)**. Use **third-angle** projection (North-American default); note the choice
    explicitly since first- vs third-angle swaps left/right and top/bottom view placement.
  - **View set:** one front view carrying the most information, only as many orthographic views as
    fully define the part (drop redundant ones), plus an **isometric** for clarity; a **section view**
    (hatched cut) wherever internal geometry (bores, the knife-mount bearing bore) would otherwise be
    dimensioned off hidden lines; a **detail view** at larger scale for small features (the cam notch,
    a sub-mm gear root); **centre-lines** on every circular feature.
  - **Dimensioning:** prefer **datum (baseline) dimensioning** off the part's primary datum over
    **chain** dimensioning, so tolerances don't accumulate down a chain — chain only where the
    *relative* spacing of a hole group matters (e.g. the 20 spring holes). Dimensions outside the
    part, never off hidden lines, don't dimension 90° corners, reference-only dims in **( )**.
    Hole callouts carry Ø + depth (⌴ counterbore / ⌵ countersink symbols where used). Thread callouts
    match each thread's **own** standard, not a blanket one: **Unified inch** as *size–TPI–series–
    class* — the `rocker-arm-support` **9⁄16-12 UNC-2B** tapped feet (the machine's one real threaded
    feature) are inch, so they take the Unified form, **not** metric — and **ISO metric** as
    **M d×pitch** (class 6H/6g) for any metric fastener. Don't force the M form onto an inch thread.
  - **General tolerance block** governs every unspecified dimension. On an ASME print this is the
    native **decimal-place title-block table** (e.g. `.X ±0.5`, `.XX ±0.1`, `.XXX ±0.025` — each
    place *defines* its tolerance, so it is specified, not assumed); an **ISO 2768** table is the
    equivalent when drawing to ISO. Map the repo's `machined_block`/`plate_profile`/
    `visual_noncritical` grades into whichever block the chosen standard uses, so only
    critical-to-function features carry an explicit `±` or a feature-control frame.

### CAM (STEP → CAM → G-code) — IN SCOPE, deferred until the nominal model is validated

**Corrected from a prior "OUT."** With the **PM-30MV CNC** in the toolchain for the repetitive parts
(20 cams, 19+19 spacer bushings, cone/cylinder gear train), CAM has a real consumer. The **primary feed
is the 3D solid via STEP**, not DXF: `SW → STEP → CAM (SOLIDWORKS CAM / HSMWorks / external) → select
faces & pockets, define stock + tools + operations → post G-code`. For a **3-axis mill cutting a real
solid**, STEP is the mainstream, robust path — it preserves the true form (bores, hubs, varying
depth) a 2D profile cannot. DXF is a **narrow special case**, handled in its own subsection below.

- **The STEP feed mostly exists — with one gap for multi-config parts.** The repo drives `SaveAs3`
  for STEP/STL today (`export_models.py`, `cut_release.py`), so for a **single-config** part the CAM
  input is a free byproduct of the existing neutral export. **But** the neutral exporters write only
  **one `<stem>.STEP` per SLDPRT** (the active config) while emitting the per-config geometry as
  **STL only** (`export_part_stls` iterates configs for STL; STEP is one-per-stem). So the 20-config
  **`cone-gear`** (and any other multi-config part) currently exports just **one** cone-gear config as
  STEP — Fusion would see a single gear, not all 20. **A per-config STEP export path must be added**
  (iterate configs like the STL path does) before CAM can be fed from STEP for the whole cone train;
  until then the per-config STLs are the only complete neutral geometry, and STL is a poor CAM input
  (mesh, not solid). Tracked as a gap, not "already done."
- **Sequencing.** Author toolpaths only **after the nominal geometry is frozen and validated** —
  there is no point cutting paths against moving geometry, and the §4 Findings (fit/grade/geometry
  reconciliation) must close first so the CNC parts are cut to fits that actually hold.
- **CAM cuts NOMINAL — tolerances do not travel in the STEP.** A plain STEP (normal SaveAs) carries
  *geometry only*; the CAM tool generates paths to nominal, and the tolerance/fit/finish is held by
  **machining process + inspection against the 2D print (§8)**, not by anything in the STEP. (STEP
  **AP242-with-PMI** *can* carry the tolerances into a PMI-aware CAM tool, but that publish path is
  **MBD-add-in-gated** on this seat — see below — so the 2D drawing stays the guaranteed carrier.)
- **Scope boundary — CNC does the repeats, manual does the rest.** CAM is *not* a whole-machine
  deliverable: one-off frame/pedestal/linkage parts stay on the manual mill + lathe (fidelity, and
  not worth CNC fixturing). CAM targets only the high-count families where CNC repeatability buys the
  consistency the error model rewards.
- **CAM tool = Fusion 360** (Autodesk **Makers / personal SKU**, which bundles CAM). CAM therefore
  lives in an **external** tool fed the neutral **STEP** the repo already exports — which makes it
  **moot** whether SOLIDWORKS CAM is enabled on this seat (the earlier "probe SOLIDWORKS CAM
  Standard" caveat is dropped). Fusion imports STEP for the 3-axis solids and also takes a **DXF
  sketch** for the 2.5D/flat parts (§DXF), covering both routes. Watch the Makers-SKU limits (e.g.
  rapids/positioning moves, available posts) at CAM-planning time — not a blocker for the repeat-part
  contour/pocket work here.
- **Not a doit task — CAM stays in Fusion.** Because CAM is external and each part needs
  fixture/stock/tool decisions plus hand-verification (Fusion simulation, a first-article cut), CAM
  is a **semi-manual downstream step keyed off the frozen STEP exports**, not a scripted spine task.
  The repo's job ends at emitting a validated STEP per repeat part; toolpaths + G-code are authored
  and owned in Fusion.

### DXF — narrow role: flat parts, 2.5D profiles, inspection reference (NOT the primary CAM feed)

DXF is **2D** (a flat set of curves, no solid), so it is *not* the general CNC feed — STEP is
(above). DXF earns its keep only where a part **is** essentially a 2D profile at a single depth:

- **Genuinely flat parts** — nameplate, clips, platen outline — trivially cut from a DXF profile.
- **2.5D contour/engrave or indexed profiles** — cam eccentric profiles and gear/rack **tooth
  flanks**, *if* cut via a 2.5D contour flow or a rotary indexed from the flank curve rather than
  3-axis milled from the solid. Which route per part is a CAM-planning call (§CAM), not fixed here.
- **Inspection reference** — overlay a cut gear on its nominal flank.

DXF would also be the feed for a purely-2D cutter (laser / waterjet / plasma / wire-EDM) — but the
toolchain has **none** of those, so that path is moot. Export via `IPartDoc.ExportToDWG2` (a
dedicated face/sketch→DXF call, verified in the bundle; or a drawing `SaveAs` to `.dxf`). Like a
plain STEP, DXF carries **geometry, not tolerances** — the toleranced print (§8) stays the authority
for size/fit/finish. Net: DXF is a **convenience for the flat/2.5D subset and an inspection aid**,
subordinate to the STEP→CAM path, not a build deliverable of its own.

### DimXpert / MBD — DimXpert IS available on the Makers seat (the backbone); 3D-PDF + STEP242-PMI publish are optional

Corrected after checking online — an earlier draft wrongly assumed DimXpert was add-in-gated.
**DimXpert (authoring PMI — size + geometric tolerances and datums on the model) is included with
*every* SOLIDWORKS license**, so it runs on the 3DEXPERIENCE **for Makers** seat:

- Hawk Ridge Systems (SOLIDWORKS reseller): *"DimXpert and MBD Dimensions are the exact same
  toolset. **Both are included with every license of SOLIDWORKS** …"*
- SOLIDWORKS Help: *"SOLIDWORKS MBD offers 3D PMI definition capabilities using DimXpert …"* — and
  GoEngineer: the **MBD add-in** is what *publishes* DimXpert models to **3D PDF / eDrawings /
  STEP242**.

So the split is: **DimXpert authoring = included → embed PMI during the build (§8), this is the
recommended backbone.** What the **MBD add-in** gates is *publishing* that PMI into a 3D-consumable
neutral format — **both 3D-PDF *and* STEP 242-with-PMI** ("Publish to STEP 242" is documented as an
MBD feature needing a stand-alone license,
[SW Help 2025](https://help.solidworks.com/2025/english/solidworks/sldworks/t_share_models_step242.htm)).
That is fine, because the bench deliverable is a **2D PDF print**, and the 2D drawing path is **core
SOLIDWORKS** — `InsertModelAnnotations3` imports the embedded PMI with no add-in. Net: **author PMI
with DimXpert on every build; ship 2D PDF drawings (the add-in-free vehicle); treat *both* 3D-PDF and
STEP242-PMI publish as nice-to-haves to be probed at runtime on the seat.** (The probe: try
`PublishTo3DPDF` / `PublishSTEP242File` once; if either fails for lack of the add-in, the 2D drawing
path is unaffected — and a geometry-only STEP for the repo's neutral export is always available, it
simply won't carry the tolerances.)
```

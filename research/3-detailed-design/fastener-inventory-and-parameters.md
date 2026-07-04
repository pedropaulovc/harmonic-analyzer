# Fastener Inventory & Period-Accurate Parameters — Michelson Harmonic Analyzer

Hand-off document for the CAD fastener-detailing pass. Cross-derives **every**
fastener in the machine from three independent sources and assigns the most
plausible period-correct parameters (thread system, pitch, length, head, drive,
angle) for later SolidWorks implementation.

**Sources fused here**

1. **Book imagery** — every hardware-bearing illustration in
   `references/albert-michelsons-harmonic-analyzer/ch11–ch31_images` was
   close-inspected (crank → cone/cylinder gears → rockers → amplitude bars →
   measuring stick → springs/levers → summing lever → counter spring →
   magnifying lever/wheel → platen → translational gearing → pen → pinion rig →
   eight machine views → design notes → provenance).
2. **Static CAD model code** — the `build_*_screw.py` / `build_hex_bolt.py` /
   `build_lag_screw.py` … reproduction scripts in `cad/scripts/` (dimensions,
   quantities, locations, thread/slot-modeling status) plus their
   `cad/config/parts/*.yaml` registry rows, and the instance counts actually
   placed by the `build_*_assembly.py` scripts.
3. **`cad/config/dimensions.yaml`** — the narrative dimension source-of-truth
   (annotated / stated / scaled / legacy / derived rows, with confidence).
4. **The key**: `research/3-detailed-design/period-accurate-fastener-parameters.md`
   (Whitworth / BA / Sellers thread forms, hex & cheese-head proportions, the
   anachronism chronology).

> [!WARNING]
> **All CAD hole diameters and fastener sizes are LOW FIDELITY** (most rows in
> `dimensions.yaml` are `scaled/low` or `derived/low`, and the scripts state
> "sized to the hole… low", "thread not modeled", "slot below render
> resolution"). The CAD numbers below are recorded **only as a rough scale cue**
> for picking a nominal size — they are not authoritative and must not be trusted
> for the period rederivation. The **Nominal / Thread / Pitch / Head / Length**
> columns are the deliverable; the CAD-mm columns are provenance, not truth.

---

## 0. Thread-system decision (read first)

The repo key defaults to **Whitworth (BSW, 55°)** for fasteners ≥ ¼″ and
**British Association (BA, 47.5°)** for instrument screws < ¼″, and lists
**US Standard / Sellers (60°)** only as an "if desired" alternative.

**But the provenance chapter (ch26) settles the maker:** the surviving machine's
brass plate reads **"WM GAERTNER & CO — CHICAGO — U.S.A."** (William Gaertner,
Chicago scientific-instrument maker; the 20-element machine is dated **1898**).
A US-built 1898 instrument is far more likely to carry **American threads**:

| Class | Repo-key default | Historically-defensible for a Gaertner/Chicago 1898 build |
|---|---|---|
| Bolts/screws ≥ ¼″ | Whitworth BSW (55°, rounded crest/root) | **US Standard / Sellers (60°, flat crest/root)** |
| Instrument screws < ¼″ | BA (47.5°) | **US fractional/gauge machine screws (60°)**; BA still plausible (international instrument norm, proposed 1884) |

**Recommendation for the CAD pass.** Threads on this machine are almost all
*cosmetic or unmodeled* (only `thumb-screw` and `pen-set-screw` carry an
annotation-only M3; only three screws cut a real driver slot). So the thread
*form* barely shows at model scale. Adopt **one** convention for consistency:

- **Primary (period + provenance correct): US Standard / Sellers, 60° included
  angle, flat crest & root**, American fractional sizes (⅛, ³⁄₁₆, ¼, ⁵⁄₁₆, ½″) and
  the pre-1900 coarse pitches below.
- **Acceptable fallback (matches the existing repo key doc): Whitworth 55°** with
  rounded crest/root at the same nominal sizes.
- **Either way, obey the anachronism bans**: slotted or knurled drives only —
  **no** hex-socket (1910), Phillips (1930s), Torx, circlips, or Nyloc. Use the
  **large / old hex across-flats** (the WWII-reduced hex looks too dainty).
  Countersinks at **~82–90°** (US 82°, British 90° — both period-plausible).

The tables below quote **nominal inch sizes common to both systems** and give the
**Sellers/BSW coarse TPI** (they differ by ≤ 2 TPI in this range, negligible for a
cosmetic thread). Where a screw is < ¼″ and you prefer BA, the nearest BA number
is noted.

Pre-1900 coarse pitches used below (Sellers ≈ BSW in this range):

| Nominal | TPI | Pitch (mm) | Nearest BA |
|---|---|---|---|
| ⅛″ (0.125) | 40 | 0.635 | 3–4 BA |
| ⁵⁄₃₂″ (0.156) | 32 | 0.794 | 2–3 BA |
| ³⁄₁₆″ (0.188) | 24 | 1.058 | 2 BA |
| ¼″ (0.250) | 20 | 1.270 | 0 BA |
| ⁵⁄₁₆″ (0.313) | 18 | 1.411 | — |
| ⅜″ (0.375) | 16 | 1.588 | — |
| ½″ (0.500) | 12–13 | 1.95–2.12 | — |

Head/nut proportions applied from the key: cheese/fillister head **dₖ≈1.5 D,
k≈0.7 D**, slot **n≈0.16 D, t≈0.45 k**; round/dome head **≈1.8 D × 0.7 D**;
countersunk **≈2 D** at 82–90°; hex **old A/F** per key table, head thickness
**≈0.7 D**, full nut **≈1.0 D**, lock nut **≈0.6 D**, across-corners **1.1547×A/F**.

---

## 1. Fasteners currently IN the CAD model

Qty columns: **book/real** = quantity the actual machine needs (from imagery +
dimensions.yaml); **CAD** = instances actually `place_component`-ed in the
assemblies. "In model" ✓ = built part placed, ◐ = built but under-placed / a
simplification, ✗ = built part not placed anywhere.

CAD-mm columns are **low-fi scale cues only** (see warning above).

| # | Part (MHA #) | Head / drive (as built) | CAD head Ø×h / AF (mm) | CAD shank Ø×L (mm) | Qty book / CAD | Location & function | In model | → **Nominal** | **Thread (Sellers/BSW · BA)** | **Pitch / TPI** | **Angle** | **Length** | **Head (period)** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **fillister-screw** (MHA-030) | fillister/cheese, slotted (slot omitted) | 5.5 × 2.2 | 2.9 × 4 | 6 / 4 | Platen paper-clip strips (4) + magnifying-lever bracket flange into summing plate (2, *not placed*) | ◐ | **⅛″** | ⅛″-40 · 4 BA | 0.64 mm / 40 | 60° (55°) | ¼–⅜″ (6–10) | brass cheese dₖ≈4.8, k≈2.2, slot 0.5×1.0 |
| 2 | **hex-bolt** (MHA-036) | hex head (external) | AF 12.7 × 5.5 | 7.8 × 32 | 2 / **0** | Rocker-support portal frame foot-rail hold-down; also the ch23 A-frame south-upright bolts | ✗ | **⁵⁄₁₆″** | ⁵⁄₁₆″-18 · — | 1.41 mm / 18 | 60° (55°) | 1¼″ (32) | **old A/F 0.600″ (15.2)**, thick ≈0.7 D (0.22″/5.6) |
| 3 | **lag-screw** (MHA-039) | round/dome head, slotted (omitted) | 22 × 6 | 12 × 63 | 4 / 4 | Up through base into rocker-arm-support "9/16-12" tapped feet | ✓ | **⁹⁄₁₆″** | ⁹⁄₁₆″-12 · — | 2.12 mm / 12 | 60° (55°) | 2½″ (63) | dome ≈1.8 D; C-bored in base underside |
| 4 | **hanger-screw** (MHA-034) | hex head (external) | AF 7 × 2.5 | 3.5 × 12.5 | 1 / 1 | Pen-hanger strap → wheel bar, driven from behind | ✓ | **³⁄₁₆″** | ³⁄₁₆″-24 · 2 BA | 1.06 mm / 24 | 60° (55°) | ½″ (12.5) | small hex, old A/F ≈0.34″; consider slotted pan instead |
| 5 | **slotted-screw** (MHA-101) | slotted cheese (slot omitted) | 8 × 2.5 | 4 × 18 | 4 / 4 | Alignment-pinion rig pivot-block hold-downs (2/block) | ✓ | **³⁄₁₆″** | ³⁄₁₆″-24 · 2 BA | 1.06 mm / 24 | 60° (55°) | ¾″ (18) | cheese dₖ≈7.1, k≈3.3, slot 0.75×1.5 |
| 6 | **thumb-screw** (MHA-075) | knurled ("reeded") disc, no slot; cosmetic M3 | 10 × 5 (24×Ø1 flutes) | 3 × 12 | 2 / 1 | Locks magnifying-lever clamp block (+ output fixture, *not placed*) | ◐ | **⅛″** | ⅛″-40 · 4 BA | 0.64 mm / 40 | 60° | ½″ (12) | knurled brass thumb head ≈3–3.5 D dia |
| 7 | **pinch-screw** (MHA-054) | plain/slotted (omitted) | 6 × 2.5 | 2.9 × 6.2 | 5 / 5 | Column-clamp collar pinch screws (platen rails + wheel-bar), modeled backed-out | ✓ | **⅛″** | ⅛″-40 · 4 BA | 0.64 mm / 40 | 60° (55°) | ¼″ (6) | slotted cheese *or* small knurled |
| 8 | **foot-screw** (MHA-103) | fillister-size, slotted, **black** | 5.5 × 2.2 | 2.9 × 8 | 2 / 2 | Rig thin-foot hold-downs (return-spring foot + arbor-pedestal flange) | ✓ | **⅛″** | ⅛″-40 · 4 BA | 0.64 mm / 40 | 60° (55°) | ⅜″ (8) | black cheese dₖ≈4.8, k≈2.2 |
| 9 | **cone-lock-knob** (MHA-093) | domed thumb knob + washer flange + stud | body 13, washer 18, R5 dome | stud 6.35 × 6.35 | 1 / 1 | Clamps cone swing-platform to base (lock engage/disengage) | ✓ | **¼″** | ¼″-20 · 0 BA | 1.27 mm / 20 | 60° (55°) | stud ¼″ (6.35) + base engagement | chrome knurled/domed knob |
| 10 | **cone-pivot-screw** (MHA-094) | slotted shoulder screw (slot **modeled** 1.6×1.2) | head 9.5 × 3 | shoulder 6.35 × 12.35 | 1 / 1 | Physical p1 swing pivot; shoulder rides plate, threads into base | ✓ | **¼″** shoulder | ¼″-20 · — | 1.27 mm / 20 | 60° (55°) | ½″ (12.35) | slotted cheese/fillister head dₖ≈9.5 |
| 11 | **cone-tip-adjuster** (MHA-097) | slotted screw (slot **modeled** 1.5×1.5), blind cup end | — | 7.9 × 14 | 1 / 1 | Threads into tip-block counterbore; takes up cone-stack axial end-play | ✓ | **⁵⁄₁₆″** | ⁵⁄₁₆″-18 · — | 1.41 mm / 18 | 60° (55°) | ⁹⁄₁₆″ (14) | headless grub-style set/adjuster screw |
| 12 | **cone-tip-pinch-screw** (MHA-098) | small slotted (slot **modeled** 0.8×0.8) | 4.8 × 2 | 2.4 × 8 | 1 / 1 | Squeezes tip-block slit closed → clamps adjuster threads | ✓ | **³⁄₃₂–⅛″** | ⅛″-40 · 6 BA | 0.64 mm / 40 | 60° (55°) | ⅜″ (8) | tiny slotted cheese dₖ≈4.8 |
| 13 | **pen-set-screw** (MHA-052) | black knurled knob, no slot; cosmetic M3 | 9 × 5 (22×Ø1 flutes) | 3 × 15 | 1 / 1 | Threads up through pen-frame rail to set pen-to-paper angle | ✓ | **⅛″** | ⅛″-40 · 4 BA | 0.64 mm / 40 | 60° | ⅝″ (15) | knurled brass/blackened thumb head |
| 14 | **swing-stop-screw** (MHA-095) | slotted (slot **modeled** 1.2×1.0) | 8 × 2.5 | 4 × 14 (8 proud) | 1 / 1 | Stands in base to bump swing plate → limits p1 disengage travel | ✓ | **³⁄₁₆″** | ³⁄₁₆″-24 · 2 BA | 1.06 mm / 24 | 60° (55°) | ⁹⁄₁₆″ (14) | slotted cheese dₖ≈7.1 |
| 15 | **transgear-knob-shaft** (MHA-078) ⚑knob | brass thumb knob on a geared shaft (reeding omitted) | knob 20 × 6.5 | shaft 9.525 × 58 | 1 / 1 | Latch-arm transgear control knob (a hand control, not a hold-down) | ✓ | **⅜″** shaft | n/a (plain shaft; knob) | — | — | 58 | knurled brass knob Ø20 |

**Pins used as fasteners (built parts):**

| # | Part (MHA #) | Type | CAD dims (mm) | Qty book / CAD | Location | In model | Period note |
|---|---|---|---|---|---|---|---|
| 16 | **crank-pin** (MHA-024) | tapered pin, no head | big 6 → small 5, L 45 | 1 / **0** | Removable taper pin affixing crank arm to crankshaft (pulled to swap crankshaft gear) — self-labeled "tapered pin" in ch11 | ✗ | period taper ≈ **1:48** (0.021″/in); driven/drifted, brass split-ring + retaining chain (ch11 shows both) |
| 17 | **pinion-cam-pin** (MHA-100) | cylindrical dowel pin | Ø3 × 17.5 | 2 / 2 | Cam-follower pin pressed through each pinion swing-strap tail | ✓ | plain ground dowel, press fit (no thread) |

⚑ transgear-knob-shaft is a **control knob**, not a clamping fastener — listed for completeness.

---

## 2. Fasteners SEEN in the book but NOT (or only partially) in the CAD model

These are the fidelity gaps — hardware the real machine carries that the current
model omits or collapses into a simplification. Quantities are best estimates
from the imagery. All are **slotted / square-head / knurled** (period-correct);
none exist as a placed CAD fastener today.

| # | Fastener (location) | Book evidence | Est. qty | Type / drive | → Nominal & thread | In model | Modeling gap |
|---|---|---|---|---|---|---|---|
| A | **Frame-corner column clamp screws** — green corner castings pinching the 4 polished steel columns | ch30 every view; ch31 corner joints; the dominant *structural* fastener | ~8 (1–2 × 4 top corners; ± bottom) | slotted set/pinch screw, radial | **¼″-20 BSW/Sellers**, 55/60° | ✗ | corner bosses modeled (Ø48/bore Ø25.5) but **no clamp screw** — biggest single gap |
| B | **Column split-collar cross-bar clamp screws** — hold horizontal cross-bars on the columns | ch30 page004/005/007/008 | ~4 | slotted pinch screw | **³⁄₁₆–¼″** | ◐ | some overlap the 5 modeled `pinch-screw` collars; frame cross-bar collars extra |
| C | **Counter-spring gooseneck square-head pinch screw** — pinches the adjustable post in its socket | ch19 p.45 "square-head screw pinches the post"; dims 10×10×6 head, Ø5 shank | 1 | **square head**, slotless | **³⁄₁₆″** square-head | ◐ | modeled as `gooseneck-clamp` *feature*, not a discrete fastener |
| D | **Counter-spring anchor screw + flat washer** — spring end-hook loops under the washer | ch19 page001_img02 (clearest shot) | 1 (+washer) | slotted cheese + washer | **⅛–³⁄₁₆″** | ✗ | anchor screw + washer not modeled |
| E | **Summing-lever knife-mount square-head bolt + stirrup** | ch18 p.42/43; dims "square-head bolt + stirrup strap → collapsed to block + Ø8 stud" | 1 | square head | **⁵⁄₁₆″** (Ø8 stud) | ◐ | collapsed to a block+stud simplification |
| F | **Counter-spring tension-rod hex nut + square nut** — on the vertical tension/feed stud at the top frame | ch18 img01, ch19 img05 (hex), img04 (square) | 1 hex + 1 square | **hex nut + square nut** | **⁵⁄₁₆″** | ✗ | nuts not modeled |
| G | **Magnifying-wheel axle hex nut + washer** — retains wheel/drum on axle | ch21 page001/002 hub macros (self-evident nut + washer) | 1 (+washer) | **hex nut** | **³⁄₁₆–¼″** | ◐ | dims say "washer + hex nut collapsed to a Ø9×4 collar" |
| H | **Measuring-stick knurled thumb-screw + 2 slotted brass face screws** | ch16 page001_img04 (clear) | 1 knurled + 2 slotted | knurled thumb + slotted cheese (brass) | thumb **⅛″**; face **³⁄₃₂–⅛″** | ✗ | `measuring-stick` part exists; its clamp screws not modeled |
| I | **Amplitude-bar / rocker-arm bracket & pivot-retaining screws** | ch14, ch15 page002_img04 (bracket-to-frame + pivot retainers) | ~6–10 | slotted round/cheese | **⅛–³⁄₁₆″** | ✗ | rocker pivot uses shaft+bushings; bracket screws omitted |
| J | **Gear bearing-cap / pillow-block hold-down screws** — cone & cylinder gear green bearing caps | ch12 page002_img09 (paired cap screws), ch13 pedestals, ch31 img08 (2 on cone pillar) | ~12–20 | slotted cheese (paired) | **³⁄₁₆–¼″** | ✗ | bearings simplified; cap screws omitted throughout |
| K | **Gear-hub set-screws / retaining collars & nuts** — clamp gear hubs to arbors | ch13, ch23 page003 (2 radial set-screws in brass hub), ch12 (threaded shaft-end + brass nut) | ~6+ | slotted grub set-screw / brass nut | **⅛″** grub | ✗ | gears bored/soldered (no keyway policy); hub set-screws omitted |
| L | **Nameplate corner screws** — fix the "WM Gaertner & Co" brass maker's plate | ch26 page001_img01 (4 brass slotted CSK/round screws, one per corner) | 4 | slotted **countersunk** brass | **³⁄₃₂–⅛″**, **90°** CSK | ✗ | `nameplate` part exists; mounting screws not modeled |
| M | **Gearbox-cradle base-corner square-head hold-down bolts** | ch30 page008; ch31 img04 | 2–4 | **square head** | **¼–⁵⁄₁₆″** | ✗ | frame cast as one piece; cradle bolts omitted |
| N | **Chain-sprocket central nut / retaining screw** | ch23 page002, ch30 page002/009 | 1–2 | hex nut / slotted | **¼″** | ✗ | sprocket retention omitted |
| O | **Base leveling feet / base-plate corner screws** | ch19 img03, ch22 img06, ch30 base corners (faint) | ~4 | slotted / leveling foot | **¼″** | ✗ | uncertain in imagery; not modeled |
| P | **Crank wood-handle end retaining screw** | ch11 page002_img03/06, ch13 page002_05 (slotted cap on the turned handle) | 1 | slotted, capping handle spindle | **⅛″** | ✗ | `crank-handle` modeled; end screw omitted |
| Q | **Crank tapered-pin retaining ring + brass screw-eyes/chain** | ch11 page002 (brass ring under pin head + wire eyes/chain) | 1 ring + ~2 eyes | brass split-ring + screw-eyes | small | ✗ | chain "lost" on original; ring/eyes omitted |
| R | **Pinion-rig T-handle / tommy-bar clamp screws** | ch25 page002_img07/08 (2 tommy-bar clamps, "6 mm") | 2 | tommy-bar clamp screw | **¼″** | ◐ | partially covered by `pinion-handle`; verify against imagery |

---

## 3. Roll-up

**Distinct fastener families across the whole machine (both tables):**

- **Slotted cheese / fillister screws** — the workhorse (platen rack & guides &
  clips, bearing caps, brackets, rig blocks, nameplate). Brass on brass, steel on
  steel/castings. Sizes ⅛″–³⁄₁₆″.
- **Slotted round / dome-head screws** — bracket & pivot retainers (ambiguous
  screw-vs-rivet on several polished dome heads).
- **Slotted countersunk screws** — platen rack (flush), nameplate. **90°** CSK
  period-plausible.
- **Hex-head bolts (external hex)** — the *few* larger structural hold-downs
  (rocker-support portal, A-frame uprights, lag hold-downs). Use **old/large A/F**.
- **Square-head bolts & nuts** — counter-spring post, summing-lever knife-mount,
  gearbox-cradle corners, tension studs. Distinctly period (pre-hex-standardization).
- **Knurled ("reeded") thumb-screws** — hand adjustments (magnifying-lever clamp,
  pen angle, measuring stick, cone lock, transgear knob). No drive slot.
- **Grub / set / adjuster screws** — cone-tip adjuster & pinch, gear-hub set-screws.
- **Pins** — crank taper pin (≈1:48), pinion cam dowels, gear cross-pin.

**In-model coverage:** 15 fastener parts + 2 pins are built; of those, ~12 are
placed as intended, `fillister-screw`/`thumb-screw` are under-placed, and
`hex-bolt`/`crank-pin` are built but **placed in no assembly**. The real machine
carries **dozens more** slotted bearing-cap / bracket / rack / nameplate screws
(§2 A–R) that are currently omitted or collapsed — the largest being the **frame-
corner column clamp screws (§2-A)** and the pervasive **gear bearing-cap screws
(§2-J)**.

**Anachronisms to avoid (from the key):** hex-socket/Allen (1910), Phillips
(1930s), Torx, ISO metric series, circlips/retaining rings (1920s+), Nyloc
(1941), and the WWII-reduced ("modern") small hex. Everything on this 1898
Gaertner machine is **slotted, square-head, knurled, or pinned**.

---

## 4. Confidence & next steps

- **High confidence:** fastener *presence, type, location, and count* per table
  §1 and the "clear" imagery rows in §2. The Gaertner/Chicago/1898 provenance.
- **Medium:** nominal sizes (derived from low-fi CAD scale cues + book scale keys
  like ch15's ¼″ bar and ch24's "6 mm" callout). Re-measure against the annotated
  photos when modeling each part.
- **Low (must re-check at build time):** exact pitch, thread engagement length,
  and head heights — all cosmetic here, so pick per the §0 convention and move on.
- **Open decision for the owner:** commit to **Sellers/US-Standard 60°** (provenance-
  correct) vs the repo key's **Whitworth 55°** for the ≥¼″ screws, and **BA vs US
  gauge** for the < ¼″ instrument screws. The visible difference at model scale is
  negligible; pick one for consistency before the fastener-detailing pass.

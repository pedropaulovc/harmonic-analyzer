# Period-Accurate Fastener Parameters (c. 1890)

> [!WARNING]
> **PERIOD-ACCURATE FASTENERS ARE ON HOLD — DO NOT IMPLEMENT (until further notice).**
> The period thread systems described below (**Whitworth / BSW**, **British
> Association / BA**, Sellers) are **not** to be used in the CAD build for now.
> **Code and CAD scripts must use US customary (inch) fasteners instead** —
> standard UNC/UNF fractional-inch sizes. This document is retained as reference
> only; treat every BA/Whitworth recommendation here as **suspended** until this
> notice is lifted.

Reference data for hand-modelling the analyzer's fasteners in SolidWorks with
1890-correct thread forms and head/nut geometry. The SolidWorks Toolbox is **not**
period-appropriate: every Toolbox library is keyed to a standards body founded
after 1890 (ANSI 1918, ISO 1947, DIN 1917, JIS 1949, BSI 1901…), and its hallmark
parts — hex-socket (Allen, 1910), Phillips (1930s), retaining rings, metric series —
are outright anachronistic. Model the fasteners by hand instead.

## Thread system by fastener class

| Fastener class | System | Why period-correct |
|---|---|---|
| Bolts, nuts, screws ≥ 1/4″ | **Whitworth (BSW)** | First national thread standard, Joseph Whitworth **1841**; universal in Britain by 1860 |
| Small instrument screws (< 1/4″) | **British Association (BA)** | Proposed **1884**, Thury-derived; the "scientific" instrument thread |
| (US alternative, if desired) | Sellers / U.S. Standard | William Sellers **1864**, adopted ~1868; 60° form |

Avoid while modelling: 60° V-threads on British parts (reads as Unified/metric),
hex-socket / Phillips / Torx drives, and the reduced modern hex sizes.

---

## 1. Whitworth (BSW) thread form

Profile is identical for every size; only pitch scales. Sweep this along the helix.

| Parameter | Value | Notes |
|---|---|---|
| Included thread angle | **55°** | symmetric → 27.5° per flank |
| Pitch, p | **1 / TPI** in | 20 TPI → p = 0.0500″ |
| Sharp-V height, H | 0.960491 · p | H = p / (2·tan 27.5°) |
| **Real thread depth, h** | **0.640327 · p** | = ⅔ H (top ⅙ + bottom ⅙ of H rounded away) |
| **Crest & root radius, r** | **0.137329 · p** | crest and root rounded to the *same* radius — the Whitworth signature |
| Minor (core) dia | D − 2h = D − 1.28065·p | |
| Effective (pitch) dia | D − h = D − 0.640327·p | |

**SW recipe:** sketch a 55° isosceles V of full height H = 0.9605 p, truncate top and
bottom by H/6 each, blend radius r = 0.13733 p onto both crest and root, then sweep
along a helix of pitch p. SW's built-in Thread feature has no Whitworth/BA profile —
use a custom swept cut (or a cosmetic thread on lightweight parts).

### BSW coarse series (analyzer range)

| Nominal | TPI | Pitch p (in) | Core dia (in) | Effective dia (in) |
|---|---|---|---|---|
| 1/8″  | 40 | 0.02500 | 0.0930 | 0.1090 |
| 3/16″ | 24 | 0.04167 | 0.1341 | 0.1608 |
| 1/4″  | 20 | 0.05000 | 0.1860 | 0.2180 |
| 5/16″ | 18 | 0.05556 | 0.2414 | 0.2769 |
| 3/8″  | 16 | 0.06250 | 0.2950 | 0.3350 |
| 7/16″ | 14 | 0.07143 | 0.3460 | 0.3918 |
| 1/2″  | 12 | 0.08333 | 0.3933 | 0.4466 |
| 5/8″  | 11 | 0.09091 | 0.5086 | 0.5668 |
| 3/4″  | 10 | 0.10000 | 0.6219 | 0.6897 |

Core/effective diameters computed from the form constants above.

---

## 2. British Association (BA) thread form — small instrument screws

| Parameter | Value |
|---|---|
| Included thread angle | **47.5°** |
| Thread depth | **0.6 · p** (= 3⁄5 p) |
| Crest & root radius | **0.18083 · p** |
| Pitch progression | each number = 0.9 × previous pitch |

| Size | Major dia (mm) | Pitch (mm) | ≈ TPI |
|---|---|---|---|
| 0 BA  | 6.00 | 1.00 | 25.4 |
| 2 BA  | 4.70 | 0.81 | 31.4 |
| 4 BA  | 3.60 | 0.66 | 38.5 |
| 6 BA  | 2.80 | 0.53 | 47.9 |
| 8 BA  | 2.20 | 0.43 | 59.1 |
| 10 BA | 1.70 | 0.35 | 72.6 |

Core dia = major − 2(0.6 p); effective = major − 0.6 p.

---

## 3. Hex head & nut proportions (Whitworth)

Use the **old/large** across-flats (A/F) for an authentic 1890 look — the WWII
austerity reduction (codified in BS 1083) shrank the Whitworth hexagon by one size,
so a modern nut looks too dainty on a period machine. Across-corners
e = A/F ÷ cos30° = **1.1547 × A/F**.

| Nominal | **Old A/F (1890)** | Across-corners | Modern A/F (BS 1083) |
|---|---|---|---|
| 1/4″  | **0.525″** | 0.606″ | 0.445″ |
| 5/16″ | **0.600″** | 0.693″ | 0.525″ |
| 3/8″  | **0.710″** | 0.820″ | 0.600″ |
| 7/16″ | **0.820″** | 0.947″ | 0.710″ |
| 1/2″  | **0.920″** | 1.062″ | 0.820″ |

Old series = modern shifted up one size; cross-checked against the well-documented
"large" 1/2″ Whitworth = 0.920″.

**Thickness / height (traditional Whitworth proportions):**
- Standard (full) nut thickness ≈ **1.0 · D** (½″ nut ≈ 0.50″). Modern BS 1083 runs ~0.875 D.
- Lock / thin nut ≈ **0.6 · D**.
- Bolt-head thickness ≈ **0.7 · D**.
- Chamfer the top face at 30° (120° cone) so flats meet the chamfer at the six corners.

---

## 4. Slotted cheese-head screw (British "cheese" ≈ US fillister)

Exact BSW/BSF dimensions (BS 450 — codifies the traditional 1.5 D head that long
predates the standard):

| Nominal | Head dia (dk) | Head height (k) | Slot width (n) | Slot depth (t) |
|---|---|---|---|---|
| 1/8″  | 0.188″ | 0.087″ | 0.039″ | 0.039″ |
| 3/16″ | 0.281″ | 0.131″ | 0.050″ | 0.059″ |
| 1/4″  | 0.375″ | 0.175″ | 0.061″ | 0.079″ |
| 5/16″ | 0.469″ | 0.219″ | 0.071″ | 0.098″ |
| 3/8″  | 0.562″ | 0.262″ | 0.082″ | 0.118″ |
| 7/16″ | 0.656″ | 0.306″ | 0.093″ | 0.138″ |
| 1/2″  | 0.750″ | 0.350″ | 0.104″ | 0.157″ |

**Proportional rules (any size):** head dia ≈ **1.5 D**, head height ≈ **0.7 D**,
slot width ≈ **0.16 D**, slot depth ≈ **0.45 × head height**. Cheese head = straight
cylindrical sides, slightly rounded top edge.

Other period heads by the same D-proportions: **countersunk** ≈ 2 D dia — but note
British 1890 countersinks were often **90°**, not the US 82°; **round/dome head** ≈
1.8 D dia × 0.7 D high.

---

## Chronology of anachronisms (do NOT use)

| Feature | First available | Verdict for 1890 |
|---|---|---|
| Hex socket / Allen drive | 1910 (Allen patent 960,244) | ✗ |
| Phillips / cross recess | 1930s | ✗ |
| Torx / hex-lobe | 1960s | ✗ |
| ISO metric series | mid-20th c. | ✗ |
| Retaining rings / circlips | 1920s–40s | ✗ |
| Nylon-insert lock nut (Nyloc) | 1941 | ✗ |
| Reduced ("modern") Whitworth hex | WWII | ✗ (use large A/F) |

---

## Sources

- British Standard Whitworth — https://en.wikipedia.org/wiki/British_Standard_Whitworth
- British Association screw threads — https://en.wikipedia.org/wiki/British_Association_screw_threads
- BS 1083 precision hexagon nuts (BSW/BSF) — https://www.globalfastener.com/standards/detail_2736.html
- BS 450 slotted cheese-head screws (BSW/BSF) — https://www.globalfastener.com/standards/detail.php?sid=MzQwNA==
- ASME landmark, U.S. Standard screw threads (Sellers 1864) — https://www.asme.org/about-asme/engineering-history/landmarks/234-the-united-states-standard-screw-threads
- Allen wrench/screw origin (1910) — https://ironcubeworks.com/who-invented-the-allen-wrench/

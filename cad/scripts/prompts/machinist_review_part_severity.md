Pass 2 — classification. Assign each distinct candidate exactly ONE defect
type: apply the specific cases named in the table first, and use this
precedence only when one defect meets more than one type:

    contradiction > missing > unbuildable > over_specification
        > presentation > shortfall > polish

Then file it in that type's category. Never file one defect twice, never
invent a hybrid category such as "minor clarity", and never move a finding to
a lower category because it feels minor, because an experienced machinist could
work out the intent, or because the fix is easy — the type decides. Separate
defects on one feature (its mate's identity, its band's support, its layout)
are separate findings.

| type | what qualifies | category |
|---|---|---|
| contradiction | two statements that cannot both be obeyed (rule 25) | blockers |
| missing | required information absent everywhere in the package: a feature with no size or location anywhere (a value in a linked numbered note DOES exist; judge its linkage under rule 7); no identifiable mate for a tight band or matched fit, and no acceptance on a matched fit (rule 4, evidence standard below); missing essential interchangeable-fit limits; a mid-air location origin, including a location given only by words such as CENTRED or MIDPOINT (rule 10); a worst-case wall below the floor (.060 in; 1.5 mm on an unconverted metric sheet) or full-thread engagement below 1.5D (rules 17, 18), stated on the sheet or not, unless a supplied owner exception covers that feature and value (rule 20); a section whose represented feature cannot be told anywhere in the package (rule 9); a required finish, mask or bare-surface protection missing from the Finish field (rule 2); a geometric control missing its datums or basics (rule 5); a callout whose unit or process you cannot tell | blockers |
| unbuildable | a feature or callout that is impossible or implausible for every allowed one-off route (rules 16, 21); incompatible controlled fit ranges; an explicit band narrower than its row in the guidelines' "What the shop holds" table with no fit route named at the feature — quote the band, the row and the absent route (rule 4) | blockers |
| over_specification | every frame, datum, roughness symbol, basic box, tight band, decimal place or note line the part does not need; any material or finish instruction repeated outside the title block; narration as rule 7 defines it — a reason over one line or six words, a second reason on one feature, the same reason repeated on several dimensions, design rationale, a reason on an overall or stock size, or an assembly instruction on a part sheet; a clearance hole located tighter than rule 4's clearance bound — except a tight band whose mate is unidentifiable, which is `missing` by precedence | over_specification |
| presentation | a failure of an explicit identification, linkage, notation or layout requirement: content touching or outside the border (rule 13); text inside the silhouette without cause, crossed leaders or text on lines as rule 14 lists them; broken ASME alignment, a view group bunched against one edge, the wrong orientation or a crowded sheet (rule 15; say what should move to its own sheet); a dimension that reads like an overall but is not; a dimension to a hidden line, an internal shape defined only by hidden lines, or hidden lines cluttering a view (rule 9); an unlabelled section, detail or enlarged view, a cutting plane or boundary missing from its parent, a broken section that does not say which like feature it shows, or a size deferred to another view (rule 9); individual location dimensions where rule 10 requires a hole table (count the hole axes, crossings or qualified holes and say so), or an identical callout repeated per hole (rule 10); a location dimension carrying words, or a callout with more than two lines of words (rule 7); a missing or noncompliant isometric (rule 8); a turned part dimensioned against rule 11; a view choice that hides a feature; an ordinary size or location carried only in a note, or a fit-up note not linked to its feature (rule 7); a mate named elsewhere in the package but not at the callout it serves, or named at the callout by catalogue code, slug, shortened number or bare item number (rule 4); a band in its shop-table row but narrower than .002 total on a location, length or setting with no fit route or stated check at the feature, or a converted-millimetre inch band (rule 4); a private phrase, compass direction, undefined project label, prose view name, word-form counterbore or countersink, nonstandard geometric modifier, or mixed units in one view (rule 26) | clarity |
| shortfall | a worst-case wall at or above the floor but below the target (.060 to below .080 in; 1.5 to below 2.0 mm); a below-floor value that a supplied owner exception covers, quoted with its value and exception id | minor |
| polish | a preference that breaks no explicit guideline requirement and changes nothing in how the part is made, checked or read, including rule 26's spelling slips and table or note text that wraps but stays complete and readable | minor |

Rule 4 evidence standard — when is a mate "named"? It applies to every callout
that refers to another part (MATCHES, FOR, ON, IN, FITS, LOCATES, SETS,
CLEARS, SEATS ON, HOLDS), not only to tight bands. The package must PRINT the
mate's full drawing number (`MHA-…`; a kit member also names the member) or
name the mating feature unambiguously, somewhere on its sheets: at the callout
(a flagged note, `SEE NOTE n`, pattern callout or hole-table row linked to the
feature counts as at the callout, rule 7), in a note or in a data block.
Named at the callout by full drawing number: no finding. Named at the callout
by a catalogue or vendor code, a file slug, a shortened number or a bare item
number, or named by drawing number only elsewhere in the package:
`presentation`. A guessed or inferred mate ("likely referenced elsewhere", an
unnamed seat, a generic noun such as COLLAR or SEAT, a mating assembly you
cannot see), or no mate at all: `missing`. Separately, a matched or
selectively fitted pair (rule 4) must identify its mate by BOTH name AND full
drawing number and state its acceptance: missing number is `presentation`;
missing acceptance is `missing`. Whatever fix you prefer, a tight band with no
identifiable mate is `missing` only — never also over_specification. A border
breach, a wording gap or a mate named elsewhere in the package is never a
blocker.

Shop-table standard — apply "What the shop holds" literally. Read each explicit
band's total width, find its row, and decide only whether the band is narrower
than the row and whether a fit route (matched fit with acceptance, match-drill
or transfer, set-at-assembly with its setting, purchased precision stock) is
named at the feature. Use no other capability figure. A thresholds-based
finding (table row, hole-axis count, six-word reason, two lines of words, six
step lines) quotes the count or values it applied.

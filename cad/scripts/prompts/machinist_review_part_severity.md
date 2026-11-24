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
| missing | required information absent everywhere in the package: a feature with no size or location anywhere (a value in a linked numbered note DOES exist; judge its linkage under rule 7; so does a REF location with a trial on a named mate printed in the package, rule 4 form 2); no identifiable mate, or no acceptance, on a fit made to its mate (rule 4, evidence standard below); a mid-air location origin, including a location given only by words such as CENTRED or MIDPOINT (rule 10); a worst-case wall below the floor (.060 in; 1.5 mm on an unconverted metric sheet) or full-thread engagement below 1.5D (rules 17, 18), stated on the sheet or not, unless a supplied owner exception covers that feature and value (rule 20); a section whose represented feature cannot be told anywhere in the package (rule 9); a required finish, mask or bare-surface protection missing from the Finish field (rule 2); a geometric control missing its datums or basics (rule 5); a callout whose unit or process you cannot tell | blockers |
| unbuildable | a feature or callout that is impossible or implausible for every allowed one-off route (rules 16, 21); incompatible controlled fit ranges; an explicit band that passes rule 4's necessity test, is narrower than its row in the guidelines' "What the shop holds" table and has no fit route named at the feature — quote the band, the row and the absent route (rule 4); a band that fails the necessity test is `over_specification`, not this | blockers |
| over_specification | every frame, datum, roughness symbol, basic box, decimal place or note line the part does not need; every REAM and every explicit band narrower than its title-block row that no entry of the package's NECESSITY REGISTER covers, or whose entry gives a reason that is not of its declared kind; a feature in a later form than rule 4's order allows (a REAM where the callout itself says the hole is bonded, bolted, match-drilled or held against one side and no register entry covers it; a band on a reamed hole; limits of size on a hole whose named mate is a made part of this project; a clearance or interference range narrower than .001 wide; a printed interference where rule 23 lets a bond or pin hold); a feature whose acceptance needs a plug gauge, pin pair or gauge set up for that one size — each unless a supplied owner exception covers that feature and value; any material or finish instruction repeated outside the title block; narration as rule 7 defines it — a method or procedure, a rationale paragraph, a dimension written into a reason, a reason over one line or six words, a second reason on one feature, the same reason repeated on several dimensions, design rationale that answers no builder question, a reason on an overall or stock size, or an assembly instruction on a part sheet (a short functional statement that answers a question the builder would foreseeably ask is not narration; rule 4's necessity answer is registered and is never required on the sheet, rule 7); a clearance hole located tighter than rule 4's clearance bound; a view scale printed when it equals the sheet scale (rule 9) | over_specification |
| presentation | a failure of an explicit identification, linkage, notation or layout requirement: content touching or outside the border (rule 13); text inside the silhouette without cause, crossed leaders or text on lines as rule 14 lists them; broken ASME alignment, a view group bunched against one edge, the wrong orientation or a crowded sheet (rule 15; say what should move to its own sheet); a dimension that reads like an overall but is not; a dimension to a hidden line, an internal shape defined only by hidden lines, or hidden lines cluttering a view (rule 9); an unlabelled section, detail or enlarged view, a cutting plane or boundary missing from its parent, a broken section that does not say which like feature it shows, or a size deferred to another view (rule 9); individual location dimensions where rule 10 requires a hole table (count the hole axes, crossings or qualified holes and say so), or an identical callout repeated per hole (rule 10); a location dimension carrying words, or a callout with more than two lines of words (rule 7); a missing or noncompliant isometric (rule 8); a turned part dimensioned against rule 11; a view choice that hides a feature; an ordinary size or location carried only in a note, or a fit-up note not linked to its feature (rule 7); a mate named elsewhere in the package but not at the callout it serves, or named at the callout by catalogue code, slug, a short form that does not complete from the sheet's own number, or bare item number (rule 4); a band in its shop-table row but narrower than .002 total on a location, length or setting with no fit route or stated check at the feature, or a converted-millimetre inch band (rule 4); a private phrase, compass direction, undefined project label, prose view name, word-form counterbore or countersink, nonstandard geometric modifier, or mixed units in one view (rule 26); a hole-table or ordinate origin at a hole centre rather than a picked-up corner (rule 10); a cutting plane drawn as loose arrows, or spanning the whole part for a one-feature section, a plane that misses the spokes or ribs it should cut, or one that leaves cut pieces floating (rule 9); several pictorial views told apart by arrows instead of word labels, or a short requirement hidden behind a flag symbol (rules 7, 9); a coined feature label where a plain name fits (rule 26) | clarity |
| shortfall | a worst-case wall at or above the floor but below the target (.060 to below .080 in; 1.5 to below 2.0 mm); a below-floor value that a supplied owner exception covers, quoted with its value and exception id | minor |
| polish | a preference that breaks no explicit guideline requirement and changes nothing in how the part is made, checked or read, including rule 26's spelling slips and table or note text that wraps but stays complete and readable | minor |

Rule 4 evidence standard — when is a mate "named"? It applies to every callout
that refers to another part (MATCHES, FOR, ON, IN, FITS, LOCATES, SETS,
CLEARS, SEATS ON, HOLDS), not only to tight bands. The package must PRINT the
mate's drawing number (`MHA-…`, or the same-parent short form rule 4 allows;
a kit member also names the member) or
name the mating feature unambiguously, somewhere on its sheets: at the callout
(a flagged note, `SEE NOTE n`, pattern callout or hole-table row linked to the
feature counts as at the callout, rule 7), in a note or in a data block.
Named at the callout by drawing number or allowed short form: no finding.
Named at the callout by a catalogue or vendor code, a file slug, a short form
that does not complete from the sheet's own number, or a bare item number, or
named by drawing number only elsewhere in the package:
`presentation`. A guessed or inferred mate ("likely referenced elsewhere", an
unnamed seat, a generic noun such as COLLAR or SEAT, a mating assembly you
cannot see), or no mate at all: `missing`, for a fit made to its mate. A
band with no mate to try (a stack, a gap, a wall) names none. A
pair made to fit (rule 4) must identify its mate by BOTH name AND full
drawing number and state its acceptance: missing number is `presentation`;
missing acceptance is `missing`, on the sheet of the member that is made to
fit: a callout that says its named mate is made to this feature (`MHA-XX-nn
IS TURNED TO THIS BORE`, or other words that mean it) has its acceptance on
the mate's sheet and needs none
here. A tight band or REAM that no register entry covers is `over_specification`
only (it takes the title-block band) — never also `missing`: do not ask for
a mate on a band nothing shows is needed. A border
breach, a wording gap or a mate named elsewhere in the package is never a
blocker.

Necessity standard — apply rule 4's test before the shop table, and apply it
to the NECESSITY REGISTER in the package input, not to words on the sheet.
A band is narrower than its row only by total width: add its two limits
(`+.000 / -.004` is .004 wide, `±.5°` is 1° wide) and compare with the total
of the title-block row for its decimal places as this sheet's title block
prints it (`.XXX ±.005` is .010 wide, `.XX ±.01` is .020 wide, `±1°` is 2°
wide). State both totals in the finding. A band as wide as its row or wider
is never filed under this standard, however its limits are split.
For each REAM and each explicit band narrower than its title-block row,
quote the callout and the id of the entry that covers it, or say that none
does. An entry covers a feature when its feature text identifies that
callout by view, size or name; do not demand an exact match of wording. No
entry: `over_specification`, whatever the sheet prints beside the feature.
An entry whose reason is not of its declared kind (a fit name, a mate alone,
"it runs", "it locates"), or that the package itself contradicts (a `mesh`
entry on a part with no gear and no gear named as mate):
`over_specification`. Otherwise take the entry as given, never ask for
different words in it, then check the form against rule
4's order and file a later-than-needed form as `over_specification`. Never
ask for a reason to be printed on the sheet. An entry that matches no
feature on the sheet is not a finding. One finding per feature, naming the
form it should take;
never also `missing` for the same feature's mate or acceptance, which are
asked for only once the feature has earned its form. The test does not
apply to a size, length, radius or angle printed at its title-block band
(three places with a function included), a single-limit corner radius or
edge break (`R.03 MAX`), a hole match-drilled or reamed in
place through its mate at assembly, a thread designation or class, gear
tooth data (span, tooth thickness, run-out, a gear's outside and root
diameters, in the gear data block or on a view; a band on one still meets
its shop-table row), a title-block row, or a
purchased part's
catalogue designation or supplier REF size. Rule 3 is unchanged: a
three-place size or location has its function when the feature's callout
names a mate or says what it does (`RUNS ON PIN MHA-XX-nn`); the
necessity test's "a mate alone is not an answer" is not applied to it.

Shop-table standard — for a band that passes, apply "What the shop holds"
literally. Read the band's total width, find its row, and decide only
whether the band is narrower than the row and whether a fit route (a fit
made to its mate with acceptance, match-drill or transfer, set-at-assembly
with its setting, purchased precision stock) is named at the feature. Use no
other capability figure. A thresholds-based finding (table row, hole-axis
count, six-word reason, two lines of words, six step lines, the `.001` floor
on a fit range) quotes the count or values it applied.

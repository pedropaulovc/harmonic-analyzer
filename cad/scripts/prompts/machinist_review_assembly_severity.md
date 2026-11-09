Pass 2 — classification. Assign each distinct candidate exactly ONE defect
type: apply the specific cases named in the table first, and use this
precedence only when one defect meets more than one type:

    contradiction > missing > unbuildable > over_specification
        > presentation > shortfall > polish

Then file it in that type's category. Never file one defect twice, never
invent a hybrid category such as "minor clarity", and never move a finding to
a lower category because it feels minor, because an experienced fitter could
work out the intent, or because the fix is easy — the type decides.

| type | what qualifies | category |
|---|---|---|
| contradiction | BOM rows against balloons, setup sequences across sheets, a table or step against the views, or two views or notes that disagree (rule 25) | blockers |
| missing | what stops assembly or setup: no exploded view or order; no parts list or balloons; a visible part with no identification (rule 22); an assembly fit or adjustment with no identifiable mate, acceptance criterion or procedure; missing essential interchangeability requirements; an ambiguous parked or engaged state; a fixed joint with no printed physical retention (only a CAD mate could hold it), a method rule 23's table says never counts for that load, a press or bond with no fit on the part sheet or no grade, a bond with no cure before load, a retention step with no bench acceptance, a bond or stake on a joint that must open, or no step that makes the retention — including a pivot screw listed only as an external interface (rule 23); demonstrated full-thread engagement below 1.5D or an adjustment range that does not cover the worst-case stack, stated or not, unless a supplied owner exception covers that joint and value (rules 18–20) | blockers |
| unbuildable | incompatible controlled fit ranges; an assembly gap, alignment or setting narrower than the "What the shop holds" assembly row with no indicator, gauge or set-at-assembly route named in its step (rule 4) | blockers |
| over_specification | anything the assembly job does not need: repeated part tolerances, materials or finishes (rule 24), assembly-level GD&T without cause (rule 5), unneeded precision on an assembly check (rule 4), notes restating the title block; a view scale printed when it equals the sheet scale (rule 9) | over_specification |
| presentation | a failure of an explicit identification, linkage, notation, procedure or layout requirement: content touching or outside the border (rule 13); text inside the silhouette without cause, or crossing balloons or leaders (rule 14); broken ASME alignment, a view group bunched against one edge, the wrong orientation or a crowded sheet (rule 15; say which view, BOM or step list should move to its own sheet); views too small to identify parts; a missing or noncompliant isometric (rule 8); an unlabelled section, detail or enlarged view, or one with no boundary or cutting plane on a parent (rule 9); a step order that is hard to follow; a step over six printed lines or doing more than one thing, a check and its remedy in one step, equations or three or more measured variables in prose without a sketch and table, a code defined neither in a labelled table on its sheet nor in a package code key that sheet points to by sheet number, or a setting finer than .XXX with no instrument named (rule 22: one finding that lists EVERY offending step by number with its count; never a sample ending 'and similar'); an exploded view that does not read, including a ballooned part left hidden behind its mate with its balloon on a sliver or hidden face (rule 22; parts seated together where the steps make the order plain are not a defect); a part named by catalogue code, slug or a short form that does not complete from the sheet's own number where the BOM gives it a drawing number, or a matched-fit mate missing its name or number (rule 4); a compass direction, private phrase, undefined label, prose view name or mixed units in one view (rule 26); a hole-table or ordinate origin at a hole centre rather than a picked-up corner (rule 10); a cutting plane drawn as loose arrows, or spanning the whole part for a one-feature section, a plane that misses the spokes or ribs it should cut, or one that leaves cut pieces floating (rule 9); several pictorial views told apart by arrows instead of word labels, or a short requirement hidden behind a flag symbol (rules 7, 9); a coined feature label where a plain name fits (rule 26) | clarity |
| shortfall | a below-floor value that a supplied owner exception covers, quoted with its value and exception id; installed engagement not numerically verifiable from the package | minor |
| polish | a preference that breaks no explicit guideline requirement and changes nothing in how the assembly is built, set up, checked or read, including rule 26's spelling slips, table or note text that wraps but stays complete and readable, and a standard part hatched in a section | minor |

JUDGING ENGAGEMENT AND STACKS
Installed engagement is proven upstream by the source model. Check it where
the package gives the numbers (screw length, clearance stack, tapped depth or
a stated engagement) against rules 18 and 19. Where it does not, record
"installed engagement not numerically verifiable from the package" in minor;
do not invent values or ask the sheet to add them. That allowance covers
numeric engagement depth only; it never waives rule 23's retention means and
the step that makes it.

Pass 2 — classification. Deterministic; no judgment left. Assign each
candidate exactly ONE defect type — the first that applies in this precedence
order:

    contradiction > missing > unbuildable > over_specification
        > presentation > shortfall > polish

Then file it in that type's category. Never file one defect twice, never
invent a hybrid category such as "minor clarity", and never move a finding to
a lower category because it feels minor — the type decides.

| type | what qualifies | category |
|---|---|---|
| contradiction | BOM rows against balloons, setup sequences across sheets, a table or step against the views, or two views or notes that disagree (rule 25) | blockers |
| missing | what stops assembly or setup: no exploded view or order; no parts list or balloons; a visible part with no identification (rule 22); an assembly fit or adjustment with no mate, acceptance criterion or procedure; missing essential interchangeability requirements; an ambiguous parked or engaged state; missing or ineffective retention of a threaded joint exposed to operating loads, or no step that engages it — including a pivot screw listed only as an external interface and a joint whose engagement is not verifiable (rule 23); full-thread engagement under 1.5D or an adjustment range that does not cover the worst-case stack, unless the package states the shortfall (rules 18–20) | blockers |
| unbuildable | incompatible controlled fit ranges; functionally essential precision with a substantiated setting or verification conflict (rule 4) | blockers |
| over_specification | anything the assembly job does not need: repeated part tolerances, materials or finishes (rule 24), assembly-level GD&T without cause (rule 5), unneeded precision on an assembly check (rule 4), notes restating the title block | over_specification |
| presentation | what makes you stop and re-read: content touching or outside the border (rule 13); text inside the silhouette without cause, or crossing balloons or leaders (rule 14); broken ASME alignment, a view group bunched against one edge, the wrong orientation or a crowded sheet (rule 15; say which view, BOM or step list should move to its own sheet); views too small to identify parts; a missing or noncompliant isometric (rule 8); a step order that is hard to follow; an exploded view that does not read; an otherwise identifiable matched-fit mate missing its name or number (rule 4) | clarity |
| shortfall | any shortfall the package states as a plain fact (rule 20), each quoted with its stated value; engagement not verifiable from the package | minor |
| polish | anything that matches NO type above and changes nothing in how the assembly is built, set up or checked | minor |

JUDGING ENGAGEMENT AND STACKS
Installed engagement is proven upstream by the source model. Check it where
the package gives the numbers (screw length, clearance stack, tapped depth or
a stated engagement) against rules 18 and 19. Where it does not, record
"engagement not verifiable from the package" in minor; do not invent values or
ask the sheet to add them. That allowance covers numeric engagement depth only;
it never waives rule 23.

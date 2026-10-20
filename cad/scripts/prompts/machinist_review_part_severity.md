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
| contradiction | two statements that cannot both be obeyed (rule 25) | blockers |
| missing | required information absent everywhere in the package: a feature with no size or location anywhere (a size given only in a note DOES exist and is `presentation`); no named mate for a tight band or matched fit, and no acceptance on a matched fit (rule 4, evidence standard below); missing essential interchangeable-fit limits; a mid-air location origin, including a location given only by words such as CENTRED or MIDPOINT (rule 10); an unstated worst-case wall under 1.5 mm or full-thread engagement under 1.5D (rules 17, 18, 20); a required finish, mask or bare-surface protection missing from the Finish field (rule 2); a geometric control missing its datums or basics (rule 5); a callout whose unit or process you cannot tell | blockers |
| unbuildable | a feature or callout that is impossible or implausible for every allowed one-off route (rules 16, 21); incompatible controlled fit ranges; functionally essential precision with a substantiated machining or verification conflict (rule 4) | blockers |
| over_specification | every frame, datum, roughness symbol, basic box, tight band, decimal place or note line the part does not need, and any material or finish instruction repeated outside the title block — except a tight band whose mate is unnamed, which is `missing` by precedence | over_specification |
| presentation | what makes you stop and re-read: content touching or outside the border (rule 13); text inside the silhouette without cause, crossed leaders or text on lines as rule 14 lists them; broken ASME alignment, a view group bunched against one edge, the wrong orientation or a crowded sheet (rule 15; say what should move to its own sheet); a dimension that reads like an overall but is not; a dimension to a hidden line, an internal shape defined only by hidden lines, or hidden lines cluttering a view (rule 9); a missing or noncompliant isometric (rule 8); a turned part dimensioned against rule 11; a view choice that hides a feature; a dimension or requirement carried only in a note where rule 7 wants it on the feature; a tight band whose mate IS named somewhere in the package but not at the callout it serves (rules 4, 7) | clarity |
| shortfall | a worst-case wall between 1.5 and 2.0 mm at the worst case; any shortfall the sheet states as a plain fact (rule 20), each quoted with its stated value | minor |
| polish | anything that matches NO type above and changes nothing in how the part is made or checked | minor |

Rule 4 evidence standard — when is a mate "named"? The package must PRINT the
mating part's name, drawing number or part number, or name the mating feature
unambiguously, somewhere on its sheets: at the callout (a flagged note
attached to the callout counts as at the callout, rule 7), in a note or in a
data block. A guessed or inferred mate ("likely referenced elsewhere", an
unnamed seat, a generic noun such as COLLAR or SEAT, a mating assembly you
cannot see) is NOT a named mate. Named at the callout: no finding. Named
elsewhere in the package: `presentation`. Named nowhere: `missing`. Separately,
a matched or selectively fitted pair (rule 4) must identify its mate by BOTH
name AND assigned drawing or part number: an otherwise identifiable matched
mate missing its assigned number is `presentation`, whatever else is named.
Whatever fix you prefer, a tight band with no named mate is `missing` only —
never also over_specification. A border breach, a wording gap or a mate named
elsewhere in the package is never a blocker.

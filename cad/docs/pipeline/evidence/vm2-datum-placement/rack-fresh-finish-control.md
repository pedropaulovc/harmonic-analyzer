# Fresh semantic finish insertion control

The [native control receipt](probes/rack-fresh-finish-specific-null/receipt.json)
records a fresh symbol inserted immediately after view-scoped selection of the
exact bore edge at its right rim. No endpoint or symbol-position setter was used.
The endpoint remained `(0.222499999953, 0.175, 0.0015)` metres after insertion,
rebuild, roughness assignment, leader styling, another rebuild and cold reopen.
Every observation has one semantic edge attachment, equality 1 and no dangling
state. The styled symbol reads `Ra 1.6`.

The original finish in the owned diagnostic copy was selected through its
specific `ISFSymbol` using `MultiSelect2`, checked for exact identity and deleted
before insertion. `IAnnotation.Select3` rejected the earlier tested forms even
with the document/view active; the specific-symbol positive control succeeded.
A `null_variant` in MultiSelect2's generated `VT_DISPATCH` Data argument failed
at the COM boundary; the typed wrapper accepts plain `None`. These are bounded
call-shape results, not claims that annotation selection is universally absent.

The [exact probe source](probes/rack-fresh-finish-specific-null/probe_vm2_rack_finish_attachment.py)
has SHA-256 `83c67ad011d0686d92aba8e9f403aa0bbec243a45385a4b1f21fce6ea2d9bfe3`.
The receipt hash is `a73902daf9355615cef0a70d8520dd2bac73687db2b2b8281b3628d488f0550e`.
The saved experimental drawing hash is
`37a4af9530885aa4c322a4e1eb3789b301950e97c76245dbd3151f6dbc6ecce8`.
Source and saved production-control bytes remained unchanged throughout.

This proves the tested insertion sequence on a diagnostic copy. It does not
clear the failed production head or replace the forthcoming corrected recipe's
normal build, cold/move/scale checks, print inspection or full-diff review.

# Silhouette reference shape and owned-feature control

The spring-hook trial at `c059`, adapter `25bc`, PID 31860 retained
`datum-policy-mkm2cgba/pilot.json`, SHA-256
`787d7ffffce747d57751f5f9a84c2d0edd36fefb922f29b1b077ce9c1e2a84c3`.
Both document contexts rejected all five reference returns as empty or the
wrong Python type. Their raw values were discarded, so this does **not** prove
that native IDs were absent. Repeated selection compared equal; the original
expected/selected silhouette comparison returned 0 while faces compared equal.
Drawing dirty flags were True→True and source flags False→False.

The failure-only control now retains each successful native getter's complete
JSON-safe return shape before the **unchanged** byte validator. This includes
the qualified Python type, scalar/sequence values, element types, and real
pywin32 `VARIANT` metadata when present. Unknown objects retain their type and
representation, explicitly labeled unsupported; serialization errors remain
separate. No tuple item, `.value` lookalike or wrapped payload is guessed to be
an accepted reference. Null and empty arrays are distinguishable from rejected
containers such as `bytearray` or nested arrays.

One additional positive control uses the copied source PART's exact named
`Hook` sweep BODYFEATURE, not a silhouette-derived face or geometry match. It
requires the ownership ledger's exact COPY record and the native feature name
and type. The source extension retrieves its reference, compares it with
itself, then resolves it and requires `IsSame(feature, resolved) == 1` with
native status 0. Missing/wrong objects, unknown comparisons and getter failures
remain failed control evidence. The source is never activated or assigned to
the drawing adapter. Both documents' dirty brackets cover all added queries.

The generated binding declares `GetPersistReference3` as one IDispatch input
and one VARIANT return (dispid 98), with no OUT tuple to unwrap.
`GetObjectByPersistReference3` instead has one OUT status and returns the
generated `(object, status)` pair. The existing GTol-command probe already uses
`VT_ARRAY | VT_UI1` for that input, but its integer coercion does not establish
the raw container type returned by the rejected silhouette calls.

Primary bundled references:

- [GetPersistReference3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetPersistReference3.html)
- [GetObjectByPersistReference3](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetObjectByPersistReference3.html)
- [Named BODYFEATURE persistent-reference example](https://help.solidworks.com/2026/english/api/sldworksapi/Get_Object_s_Persistent_Reference_ID_Example_VB.htm)
- [IsSamePersistentID](https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~IsSamePersistentID.html)

Rerun the existing owned datum-policy pilot with `--target spring_hook` under
an explicitly granted seat; no new runner or acceptance mode is added. The
original strict silhouette `IsSame` rejection remains authoritative even when
these diagnostic persistent-reference controls pass. Native validation was
initially pending; its next result is recorded below. No silhouette identity or
API-support conclusion is promoted from offline tests.

## Native unsigned-byte container correction

The next native receipt, `datum-policy-0akutfu6/pilot.json` at `fc0139e2`, has
SHA-256 `ffde2ee3fadd492ed0ced3376322589887e612b73956cbe8b9ff9bbe9ce096fc`.
It establishes `builtins.memoryview`, format `B`, one-dimensional returns:
all five drawing-context objects (silhouettes 1,239 bytes, faces 800 bytes),
four source-context objects (144 bytes), and the source Hook feature (20 bytes).
The source-context expected silhouette returned `None`; there is no positive
source-reference claim for that object. Hook native self-identity was 1.

The decoder now accepts only nonempty, contiguous, one-dimensional unsigned-byte
memoryviews (`format == 'B'`, `itemsize == 1`) in addition to its existing literal
byte containers. Signed, character, multibyte, multidimensional, strided, empty
and released views fail. Real VARIANT wrappers and nested tuples remain rejected.
Raw observations and the strict silhouette identity rejection are unchanged.

This fixes the demonstrated container rejection, not silhouette acceptance.
Native persistent comparisons and the complete feature round trip are still
pending. The receipt's dirty flags were drawing True→True and source False→False;
original/copy hashes remained exact and final guards were empty.

## Native drawing-context identity positive control

At root `7f382136`, adapter `25bc99b1` and licensed PID 31860, receipt
`datum-policy-rm_6b7hu/pilot.json`, SHA-256
`01add2f94a53a3ae4db7a47877723ddb9a23e53616eae67142e5df94c7e71d91`,
records successful native comparison of the decoded references. Every drawing-
context comparison returned 1: both silhouette self-comparisons, requested versus
selected, selected versus repeated selection, and the two underlying faces.
The direct requested/selected `ISldWorks.IsSame` result remained 0.

The source Hook feature also passed: native self identity 1, persistent self
identity 1, and `GetObjectByPersistReference3` returned status 0 with native
identity 1. The source-context silhouette comparison did **not** pass: the
requested reference was absent and the selected reference even compared unequal
to itself (0). The positive silhouette result is drawing-scoped only; raw byte
equality is not used as an acceptance predicate.

Dirty flags stayed drawing True→True and source False→False. Original/owned-copy
hashes stayed exact, cleanup preserved baseline documents and final runtime
guards were empty. Recipe/pilot times were 27.197/127.077 s. The whole pilot
remains failed under the unchanged direct-handle gate; built/cold acceptance
was not reached, and both generic failure observations retained the same
ambiguous semantic-coverage error. They did not retain the rejected snapshots,
so the actual failed predicate is unproved; see the
[observability correction](drawing-semantic-failure-evidence.md).

This disproves the experimental assumption that direct handle inequality alone
establishes a different drawing silhouette. A production correction must retain
exact owning-view and underlying-face identity and raw geometry checks, use
native drawing-context persistent comparison, and reject different/unknown IDs.
Its full recipe/save/cold acceptance is still required.

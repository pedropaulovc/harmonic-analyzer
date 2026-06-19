---
name: verify-sw-api-with-research
description: "When a SolidWorks API claim stops making sense, spin off a research agent to cross-check forums/SO/courses before concluding a dead end"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: ba03bcc4-d81e-4e71-bbc7-7926c9a87d29
---

When the SolidWorks (or any vendor) API behaviour stops making sense — a call
returns None/False with no obvious reason, or you're about to declare an
approach impossible — STOP. Take a step back and spin off a research agent that
searches online: vendor help pages, forum discussions, StackOverflow, blog
write-ups by API experts (CADBooster, CodeStack/Xarial), training courses. Do
NOT conclude a dead end from local experiments + bundled docs alone.

**Why:** the bundled skill docs are a partial mirror; the COM API has sibling
methods with near-identical names and subtly different contracts. A wrong
conclusion can send the build down a 600x-slower path.

**How to apply:** proven case — I concluded named reference axes "can't be
selected at depth 2" after `GetCorrespondingEntity(IRefAxis)` returned None and
hand-built `Axis@part@sub@top` strings failed. The user's web research found the
fix in minutes: `IComponent2.GetCorresponding` (NOT `GetCorrespondingEntity`)
maps ANY persistent-ID object incl. an `IFeature` reference axis/plane; keep the
base `IFeature` (not `GetSpecificFeature2()`'s `IRefAxis`), then `Select2`. See
[[phase-f-motion-study]]. Sources that nailed it: CADBooster "Entities and
GetCorresponding" series, CodeStack assembly-context page.

---
name: negative-result-positive-control
description: Never declare an API/feature dead from self-authored failures alone — reproduce a positive control first, then bisect the delta; state verdicts as "dead under variants tried" with untested deltas enumerated
metadata:
  type: feedback
---

Pedro had to intervene THREE times (2026-07-09, CopyWithMates2 investigation) before I
stopped prematurely ruling the API out: (1) "Probe 3 killed the lever — why?" (my probe
had a bug + wrong array shapes), (2) "did you look at examples?" (I'd read one dialect,
missed the VBA example whose shape differed), (3) "search online for code samples" (a
third-party sample held the missing clue — typed component arrays — and cracked it).
Each time the evidence I had only supported "fails under the variants I authored", and I
reported "dead, period". See [[v018-perf-review]] for the technical resolution.

**Why:** N self-authored failures prove nothing about the feature — they prove my call
shapes fail. A feature that demonstrably works SOMEWHERE (UI, VBA, another machine,
another dialect) is not dead; the delta between the working form and my failing form
CONTAINS the root cause, and bisecting that delta is a terminating search. Extends
[[no-untested-failure-assumptions]] and [[verify-assumptions-live-sw]].

**How to apply:**
- Before any "X is impossible/dead" verdict, obtain a **positive control**: reproduce a
  form known to work (UI action by the user, in-process VBA via `RunMacro2` on a text
  `.swb`, official example verbatim in its native dialect). If NO working form exists
  anywhere, say so — that is itself evidence.
- Once a positive control works, **bisect the delta** to the failing form one variable at
  a time (binding, marshaling, process boundary, declaration types, doc state…). This
  converges; brainstorming more failing variants does not.
- Exhaust reference material in ALL dialects (VBA + C# + VB.NET examples differ in
  load-bearing ways) AND the public web (forums, third-party macro sites) BEFORE
  concluding. A single working third-party sample outweighs any number of my failures.
- Word verdicts honestly: "dead under <list tried>; untested: <list>" — never "dead,
  period" while untested deltas remain. If I can't enumerate what I haven't tried, I
  haven't mapped the space.
- A cheap instant-False/None return is a REJECTION, not an absence — rejections have
  enumerable causes. Suspect my arguments first, the feature last.

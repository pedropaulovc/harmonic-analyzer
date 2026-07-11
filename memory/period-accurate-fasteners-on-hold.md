---
name: period-accurate-fasteners-on-hold
description: Period-accurate (Whitworth/BA/Sellers) fasteners are ON HOLD — CAD code must use US customary (inch) fasteners instead until further notice
metadata:
  type: project
---

**Period-accurate fasteners are ON HOLD until further notice (as of 2026-07-11).**
The 1890-era thread systems — **Whitworth (BSW)**, **British Association (BA)**,
Sellers/US-Standard 60° — are **suspended** for the CAD build. Code and CAD build
scripts must use **US customary (inch) fasteners** instead (standard UNC/UNF
fractional-inch sizes).

**Why:** Pedro placed the period-accurate fastener effort on hold; US customary
is the interim convention for any fastener modelling work.

**How to apply:** Do NOT model or spec Whitworth/BA/Sellers thread forms in
`build_*_screw.py` / `build_*_bolt.py` / part config rows. Use inch UNC/UNF.
The research keys
`research/3-detailed-design/period-accurate-fastener-parameters.md` and
`research/3-detailed-design/fastener-inventory-and-parameters.md` carry a
matching WARNING banner and are reference-only while this hold stands. Related
fastener work: the M6.10 fasteners pass in [[harmonic-analyzer-project]].

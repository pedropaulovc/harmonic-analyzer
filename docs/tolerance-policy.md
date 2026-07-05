# Tolerance & fits policy

Tolerance is part of the **design source**, not a late drawing annotation. Because the output
is a force balance, *inconsistent* fits across the 20 channels bias the equilibrium rather than
just adding noise — **channel-to-channel consistency matters more than absolute precision**.
Fits are therefore shared parameters applied uniformly, never per-part magic numbers.

## Source of truth

Fit classes and clearances live in [`cad/config/tolerances.yaml`](../cad/config/tolerances.yaml)
and flow into geometry and into part custom properties. The build scripts read named fit
classes; they do not hardcode clearance numbers.

## Fit classes (interfaces that must carry a rule)

| Interface | Class | Intent |
|---|---|---|
| shaft ↔ bushing (crank/rocker/lever pivots) | running clearance | hand-cranked, low-speed → generous slip fit, beginner-safe |
| gear ↔ gear mesh (cone↔cylinder, platen rack) | backlash | zero-backlash-in-CAD gears bind in brass |
| cam ↔ follower / connecting rod | contact clearance | follower rides without jamming at dwell |
| amplitude bar ↔ rocker | sliding side clearance | bar slides without binding through full sweep |
| fastener ↔ clearance hole | close / normal | per fastener class |

## Verification

`verify.py` runs a **tolerance audit** (and writes `cad/out/reports/tolerance_audit.csv`) that
fails the build if any part lacks material / tolerance class / process, or any moving interface
lacks a fit class. This is the Gate-E pass.

## Current analytic clearance assertions (kept, being migrated)

The build scripts already assert clearance margins analytically (and raise on violation) — these
are the concrete realizations of the classes above, being lifted into `tolerances.yaml`:

- spring-eye threading margins into the lever hole / under the tab;
- oblique cone↔drum mesh penetration guard (edge slack);
- rack–pinion backlash;
- bushing clearance under the amplitude-bar foot.

## Scope of manufacturing outputs

Reassessed in [`tolerance-gdt-assessment.md`](./tolerance-gdt-assessment.md) §11 — nothing here is
left "deferred":

- **GD&T (lite), surface-finish specs, critical-feature callouts — IN SCOPE.** Held in config,
  stamped into custom properties, audited; geometric intent limited to dial-indicator runout plus
  the rocker form radius and knife-edge controls (see the assessment §5).
- **2D shop drawings — IN SCOPE (planned).** A hobby machinist builds from a dimensioned, toleranced
  print, so generated PDF drawings (Tier-1 precision-critical parts first) are the vehicle that
  carries the tolerances to the bench. Same `SaveAs3` path the STEP/STL export already uses; a new
  `drawing:<stem>` doit task on the COM spine.
- **CAM (STEP→CAM→G-code) — IN SCOPE, deferred until the nominal model is frozen and validated.**
  The build is manual-primary for fidelity, with the PM-30MV **CNC** cutting the repetitive high-count
  parts (20 cams, 19 spacer bushings, cone/cylinder gear train). The primary feed is the **3D solid
  via STEP** (already emitted by `SaveAs3` in `export_models.py`/`cut_release.py`) into **Fusion 360**
  (Makers SKU) → G-code; CAM cuts nominal, so the toleranced print carries fits/finish. Authored after
  the §4 Findings close. Manual mill + lathe still make every one-off part.
- **DXF — narrow role, NOT the primary CAM feed.** 2D only; used only for genuinely flat parts, 2.5D
  contour/indexed profiles (cam/gear-tooth flanks), and inspection-reference overlays — subordinate to
  the STEP→CAM path (which handles the real 3D solids). Carries geometry, not tolerances.

# Known limitations

## Simulation fidelity

- The 21-spring **static force balance is computed, not simulated** — see
  [motion-policy.md](./motion-policy.md). No force/torque, friction, or stress results.
- Basic Motion is a kinematic smoke test, not a dynamics or certification solver.
- Gear meshing uses **gear mates + simplified pitch geometry**, not full tooth-contact, in the
  top assembly (full-tooth contact across 20 channels is unstable/slow and not relied upon).

## Mechanism states not yet fully resolved

- **Pinion / cone-pin engage–disengage** is modeled as rest-state geometry; the live
  engaged-mesh kinematics (a rigid arm can't reach the engaged center distance) is an open
  riddle captured as a rest state only.
- The **roller chain** is placed explicitly link-by-link (the SolidWorks Connected-Linkage
  chain feature has no usable API); it has no live per-link DOF. Chain-internal link contact is
  allowed (reported, not faulted); any link touching a non-link part is still a hard fault.

## Cosmetic / photo-fidelity deferrals

These are tracked against the book photos and are fidelity-only, not mechanism-blocking:

- lever-fan rest pose (photos show it drooped; CAD holds neutral);
- pen-marker plumb vs the book's ~12° tilt;
- round domed cone-pivot-post (modeled as a block);
- white render background vs the plates' black studio background (pipeline-inherent; the gallery
  blend layer compensates).

## Omitted hardware (documented)

Drive-train tapered pin, output-fixture clamp screw, clevis hardware, nameplate screws, and
fillister slots are below render resolution and currently omitted.

## Manufacturing outputs

No 2D drawings, DXF, or CAM outputs yet — the build path is manual milling/turning and the
model is currently a digital/visual artifact.

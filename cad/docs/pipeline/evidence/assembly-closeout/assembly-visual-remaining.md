# Remaining assembly visual inspection

Root Codex inspected the actual PNGs below from frozen head `64c3dab4875354a7d44d709539e001db920a0377`. This is a developing receipt; it does not certify full-build completion.

## Channel

- Image: `cad/out/png/channel/channel_isometric.png`
- SHA-256: `04b7f96c904b5c608e8042d042aca6c3522b03b468da5388fbbb1c8e5ffe3b2d`
- Bytes: 274603
- Modified UTC: 2026-09-08T04:55:10.800960+00:00
- Native `assembly.build channel` completed OK at 2026-09-08T04:55:15.797173Z.

The full mechanism fits inside the isometric image. The repeated vertical rods, upper lever bank and supports, lower bar bank and gear train are visible and consistently aligned. No displaced member, broken silhouette or clipping is apparent. Fine parallel edges are dark and dense, so this image supports overall placement; native gates remain the evidence for mates, hidden contacts and DOF.

## Pen

- Image: `cad/out/png/pen/pen_isometric.png`
- SHA-256: `3d3752ebc86a5142ed7c1940bfab42f94a579e60a6ff7b6abd5ebdf3be038869`
- Bytes: 233621
- Modified UTC: 2026-09-08T04:56:53.716330+00:00
- Native `task assembly:pen` completed OK at 2026-09-08T04:56:57.315998Z.

The complete pen mechanism is visible in the isometric image: upper hanger and screw, thin wire, vertical rod, lower clamp/support, and horizontal marker with its tip. Components are consistently aligned with no obvious displacement or clipping. This is an overall placement inspection; the image does not independently measure wire attachment, hidden contacts or kinematic freedom.

## Drive-train

- Image: `cad/out/png/drive-train/drive-train_isometric.png`
- SHA-256: `48d9cec799957f0301dbfdb5875606ce0508d2f18ec35c52b8ab39102f3afb4a`
- Bytes: 570095
- Modified UTC: 2026-09-08T05:35:51.846848+00:00
- Native `task assembly:drive_train` completed OK at 2026-09-08T05:36:01.131741Z.

The complete gear mechanism fits inside the isometric view. The stepped cone-gear bank, adjacent cylinder-gear bank, lower long pinion, bearings/support blocks, green arbor and crank/control hardware are visible and consistently aligned. No visibly displaced support, missing gear section or clipped mechanism is apparent. Dense tooth edges limit inspection of individual tooth contact; native gates remain the contact/DOF evidence.

## Harmonic analyzer

The full top-level isometric was inspected after completion at frozen head `64c3dab4875354a7d44d709539e001db920a0377`.

- Image: `cad/out/png/harmonic-analyzer/harmonic-analyzer_isometric.png`
- SHA-256: `40e5f45f697e62bcaaef27c9ef7c58dcb442de0bcd5dea86c3cbba361f616be7`
- Native assembly task completed at 2026-09-08 05:46:03.863941 UTC; saved soundness completed at 05:47:36.456011 UTC.

The complete machine fits inside the image. The frame, repeated rods and lever banks, lower gearing, paper platen and pen mechanism align with the separately inspected subassemblies. The spare T18 gear is visibly lying on the base deck at the left of the lower support; the isolated paper-drive render omitted this frame-owned deck. No displaced component or clipped geometry is apparent at this view's scale. Fine contact and hidden geometry are covered by the native checks rather than inferred from the render. All eight fresh assembly isometrics have now been inspected.

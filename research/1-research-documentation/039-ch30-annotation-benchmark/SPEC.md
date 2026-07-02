# ch30 image annotation — SPEC v2 (benchmark edition)

Annotate the 8 photographs of Michelson's harmonic analyzer (ch. 30 "Eight Views",
`C:\src\harmonic-analyzer\references\albert-michelsons-harmonic-analyzer\ch30_images`)
with colored dots marking specific features. Accuracy of dot placement is the top
priority. This spec supersedes v1 (`ch30_annotated/SPEC.md`); the changes are the
dead-center definition, smaller dots, and encouraged cross-referencing.

## Images (original pixel sizes)

| file | view | size (w×h) |
|------|------|-----------|
| page002_img01.png | front | 1749×4143 |
| page003_img01.png | front-left three-quarter | 1204×2854 |
| page004_img01.png | left side | 1776×4209 |
| page005_img01.jpeg | back-left three-quarter | 1204×2854 |
| page006_img01.png | back | 1732×4104 |
| page007_img01.jpeg | back-right three-quarter | 1242×2870 |
| page008_img01.png | right side | 1789×4239 |
| page009_img01.png | front-right three-quarter | 1204×2854 |

View labels are hints — verify against the actual pixels.

## Cross-reference material (USE IT)

Before pinpointing a part in your assigned photo, study what the part actually looks
like in the book's part-detail chapters (same directory root,
`references/albert-michelsons-harmonic-analyzer/`):

- `ch11_images/` — crank, chain, sprockets
- `ch12_images/` — cone gear set
- `ch13_images/` — cylinder gear set
- `ch14_images/` — rocker arms
- `ch25_images/` — pinion gear
- `ch10_images/` — whole-machine overview
- `eight-views-*.png` (directory root) — alternate renditions of the same 8 views

You may also look at the OTHER ch30 view photos to disambiguate what is visible from
your assigned angle. Cross-referencing is strongly encouraged — most identification
errors in the v1 round (cone vs cylinder gear, pinion vs crank-axle sprocket) would
have been avoided by checking these chapters.

## Features to mark

All coordinates in ORIGINAL image pixels.

**Dead center (REVISED definition):** the projected ROTATION-AXIS point of the gear —
the point where its axis of rotation meets the most clearly visible circular end face
/ hub (i.e. the axle/shaft center as seen in the image). End-on: the center of the
circular face. Side-on: the center of the visible end-face ellipse or the exposed
shaft/hub point — NOT the lengthwise midpoint of the gear body. If no end face, hub,
or axle point is resolvable in the view, record the feature as occluded with reason
"axis point not visible".

1. **Pinion dead center** — RED (255,0,0). The small chain sprocket mounted coaxially
   next to / in front of the large brass crank drive gear at platen level. The chain
   wraps it and runs down to the crank. The second sprocket at the crank axle is NOT
   the target; if visible you may add it as `crank_axle_sprocket_center` (red, noted).
2. **Cylinder gear dead center** — ORANGE (255,140,0). The brass cylindrical helical
   gear(s) at the base. For each visible one: `cylinder_gear_center_1` (more visible)
   and `cylinder_gear_center_2`, note which physical gear you believe each is.
3. **Cone gear dead center** — MAGENTA (255,0,255). The conical stack of gears at the
   base. Same rotation-axis rule (its base circle center is usually the markable end).
4. **Rocker arm corners** — YELLOW (255,255,0). The fan of ~20 flat tapered arc-profile
   silver arms pivoting around the central column. Mark the 4 corners (2 at the wide
   pivot/butt end, 2 at the narrow tip end) of the SINGLE most clearly visible arm:
   `rocker_arm_corner_<butt_left|butt_right|tip_left|tip_right>` (left/right as seen in
   the image). Occluded corners get no dot — record them under `occluded`.
5. **Harmonic analyzer corners** — CYAN (0,255,255). The 4 bottom corners of the green
   base slab and the 4 outer corners of the green top frame casting; every one visible
   in the image. Names `analyzer_corner_<top|base>_<front_left|front_right|back_left|back_right>`,
   machine-relative: the FRONT of the machine is the platen/paper side. State your
   assumed orientation in `orientation_note`. Occluded ones go under `occluded`.

## Method constraints (IMPORTANT)

- NO computer-vision edge detection / Hough / template matching / cv2. Locate features
  ONLY by cropping and zooming (PIL `Image.crop` + `resize`) and looking at the crops
  with your vision.
- Iterate per dot: view full image → crop generously around the feature at ≥4× and
  look → pick the pixel → draw the dot on a copy → crop tight (~200 px) around the
  drawn dot at ≥4× and LOOK → adjust until the dot is within ~5 original px.
- A labeled ruler/grid overlay on a crop is allowed (it is not edge detection).
- Convert every viewed coordinate to ORIGINAL pixels (the image viewer reports its
  downscale factor; tight crops avoid the problem).
- Python: run from the repo root `C:\src\harmonic-analyzer` with `uv run python ...`
  (Pillow is in the venv). Keep scratch crops in your scratch dir, never in the
  output dir.

## Output (per image, into your assigned output directory)

1. `<stem>_annotated.png` — original image with:
   - SMALL filled dots, radius = `max(4, round(image_width/300))` (≈4 px on the
     1204-wide images, ≈6 px on the ~1750-wide ones), each with a 1–2 px black
     outline. Dots are small on purpose so off-center placement is visible.
   - a LEGEND box (swatch + feature name per line, plus `occluded: ...` line), white
     text on dark box, TrueType font `C:/Windows/Fonts/arial.ttf` size ≈ width/45.
     The legend MUST NOT overlap any dot — pick its position after the dots are
     placed and check numerically.
2. `<stem>.json`:
   ```json
   {
     "image": "page002_img01.png",
     "view": "front",
     "model": "<your model name, provided in your task message>",
     "width": 1749, "height": 4143,
     "points": [
       {"feature": "pinion_center", "color": "red", "x": 0, "y": 0,
        "confidence": "high|medium|low", "note": "optional"}
     ],
     "occluded": [
       {"feature": "cone_gear_center", "reason": "..."}
     ],
     "orientation_note": "which side of the machine faces the camera"
   }
   ```

Dot accuracy beats speed. Verify EVERY dot with the zoomed post-draw crop before
finishing.

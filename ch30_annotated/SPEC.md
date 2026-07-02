# ch30 image annotation spec

Annotate the 8 photographs of Michelson's harmonic analyzer (20-channel replica, engineerguy book, ch. 30
"views" appendix) in `C:\src\harmonic-analyzer\references\albert-michelsons-harmonic-analyzer\ch30_images`
with colored dots marking specific features. Accuracy of dot placement is the top priority.

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

View labels are hints from a first pass — verify against the actual image and trust the pixels.

## Features to mark

All coordinates in ORIGINAL image pixels.

1. **Pinion dead center** — color RED (255,0,0). The SMALL chain sprocket mounted coaxially
   next to / in front of the LARGE brass crank drive gear at platen level (repo part:
   `crank_pinion` / `chain_sprocket`). The chain wraps it and runs down to the crank axle.
   NOTE: there is a second sprocket down at the crank axle — that one is NOT the target; if
   visible you may add it as feature `crank_axle_sprocket_center` (same red, note in JSON), but
   the required point is the upper sprocket next to the big brass gear. "Dead center" = the
   projected rotation-axis point (center of its circular face / hub) in the image.
2. **Cylinder gear dead center** — color ORANGE (255,140,0). The brass cylindrical (helical)
   gear(s) lying horizontally at the base (repo part: `cylinder_gear`). There are two on the
   machine. For each VISIBLE cylinder gear: if seen roughly end-on, mark the center of the
   circular end face; if seen side-on, mark the midpoint of its rotation axis (center of the
   visible cylinder silhouette along its axis). Name them `cylinder_gear_center_1` (closer /
   more visible) and `cylinder_gear_center_2` in the JSON with a note saying which physical
   gear you believe it is.
3. **Cone gear dead center** — color MAGENTA (255,0,255). The cone-shaped stack of gears at the
   base (repo part: `cone_gear`). Same dead-center rule: end-on → center of the circular base
   face; side-on → midpoint of its rotation axis (halfway between apex and base along the axis).
   Often occluded — check carefully before claiming visibility.
4. **Rocker arm corners** — color YELLOW (255,255,0). The rocker arms are the fan of ~20 flat,
   tapered, arc-profile silver arms pivoting around the central column (repo part:
   `rocker_arm`; they carry the amplitude bars, prominent in the back views). Mark the 4
   corners (2 at the wide pivot/butt end, 2 at the narrow tip end) of the SINGLE most clearly
   visible arm (usually the front-most/top-most of the fan). Name them
   `rocker_arm_corner_<butt_left|butt_right|tip_left|tip_right>` (left/right as seen in the
   image). If a corner is occluded, do NOT dot it — record it under `occluded`. If the whole
   fan is edge-on/unresolvable in a view, record that.
5. **Harmonic analyzer corners** — color CYAN (0,255,255). The outer silhouette corners of the
   machine itself: the 4 bottom corners of the green base slab and the 4 outer corners of the
   green top frame casting. Mark every one that is VISIBLE in the image (typically 2–3 of each
   in a photo; a three-quarter view may show 3 base corners). Name them
   `analyzer_corner_<top|base>_<front_left|front_right|back_left|back_right>` (machine-relative;
   state your assumed orientation in the JSON notes). Occluded ones go under `occluded`.

## Method constraints (IMPORTANT)

- NO computer-vision edge detection / Hough / template matching / cv2. Locate features ONLY by
  zooming and cropping (PIL `Image.crop` + `resize`) and looking at the crops with your vision.
- Iterate: (a) view full image, (b) crop a generous region around the feature at ≥4× zoom and
  look at it, (c) pick the pixel, (d) draw the dot on a copy, (e) crop a tight region (~200 px)
  around the drawn dot at ≥4× and LOOK at it to confirm the dot sits exactly on the feature
  (within ~5 original px), (f) adjust and repeat until it does.
- Drawing a labeled ruler/grid overlay on a crop to read off coordinates is allowed (that is not
  edge detection).
- Watch the Read-tool downscale factor: when you view an image it reports "multiply coordinates
  by N to map to original" — always convert to ORIGINAL pixels. Tight crops shown 1:1 avoid the
  problem.
- Python: run from the repo root with `uv run python ...` (Pillow is in the venv). Put scratch
  crops in a scratch dir, NOT in the output dir.

## Output (per image)

Into the assigned output directory:

1. `<stem>_annotated.png` — original image with:
   - filled dots radius ~10 px (for ~1200 px wide images) to ~14 px (for ~1750 px wide), each
     with a 2–3 px black outline for visibility;
   - a LEGEND box (top-left or top-right, over the black background) listing each color swatch +
     feature name, plus a line `occluded: <comma-separated features>` if any. Use a real TrueType
     font (`C:/Windows/Fonts/arial.ttf`), size ≈ image_width/45, white text on dark box.
2. `<stem>.json`:
   ```json
   {
     "image": "page002_img01.png",
     "view": "front",
     "width": 1749, "height": 4143,
     "points": [
       {"feature": "pinion_center", "color": "red", "x": 0, "y": 0,
        "confidence": "high|medium|low", "note": "optional"}
     ],
     "occluded": [
       {"feature": "cone_gear_center", "reason": "hidden behind crank pedestal"}
     ],
     "orientation_note": "which side of the machine faces the camera"
   }
   ```

Dot accuracy beats speed. Verify EVERY dot with the zoomed post-draw crop before finishing.

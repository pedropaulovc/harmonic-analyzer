# Video companion design

## Data flow

The CAD export supplies native geometry and rest transforms. Generated
`mechanics-data.ts` supplies the dimensions, linkage datums and spring catalog
values used by `mechanics.ts`. `export-mechanics.py` and `export-magnifier.py`
read CAD authority; the website does not infer dimensions from video pixels.

`video-catalog.ts` identifies the seven original videos and their local reference
hashes. `youtube-player.ts` owns the visible official embed. `timeline.ts` reads
independent source observations and selects measured camera/physical input per
view. `main.ts` changes between following playback and paused exploration;
`scene.ts` applies the physical pose to the full native GLB.

The GLB hash and source revision must match the generated mechanical data.
A rejected load never enters the visible scene. Bindings resolve genuine native
component names; missing joints have a separate persistent warning and prevent
complete synchronization acceptance. Original geometry is not decimated, resized
or replaced with proxy parts.

## Physical model

All twenty stations contribute to the torque balance, in their CAD row order
(harmonics 20 through 1). Each station uses the actual eccentric circle and rod
closure, rocker contact arc and amplitude-bar geometry. Loaded extension-spring
force is computed from hook separation, catalog rate and initial tension. The
counter spring and lever weights participate in the nonlinear quasistatic
summing equilibrium. The wire and magnifier then determine wheel rotation and
pen travel. An ideal Fourier sum is not used to drive the physical output.

Interactive amplitude is a normalized CAD slide station, bounded by the native
mechanism. The displayed millimetres are not a calibration of the video's
engraved scale. Per-channel phase rotates that channel's cam. Source states must
supply all twenty amplitudes and phases explicitly.

The engaged bank drive is `crankTurns - driveCrankOffsetTurns`; the disengaged
bank retains `heldChannelTurns`. Returning the platform to the engaged state
changes the coupling offset, preserving the stopped bank's pose while the crank
has moved. This does not rewrite the physical cam phases or retune the counter.
The crank, cone shaft and paper feed retain their own drive motion.

The model omits friction, inertia and tooth-contact dynamics. Quasistatic
constraint rejection retains the last valid rendered geometry and shows an
error. It does not substitute a nominal pose or suppress a failed solve.

## Source coverage

Each observation identifies the original MP4 hash, source dimensions, decoded
presentation time, shot classification, camera and independently observed
landmarks. Camera fitting uses fit points and held-out check points. Mechanism
input must be complete, measured and finite; an absent value is not zero.

Every required frame needs a passing camera and complete physical input for all
of its views. Physical photographs and transitions can also be required when
they have a corresponding native mechanism. A shot cannot escape this rule by
being named a transition or photograph.

Runtime states:

| State | Meaning |
|---|---|
| `matched` | Every required view has passing camera and measured physical input. |
| `unavailable` | Required evidence is missing, incomplete or outside the observation record. |
| `held` | An exempt source interval retains an actual earlier matched pose. |
| `no-machine` | An exempt interval has no earlier match; current exploratory geometry/camera stay unchanged. |

Camera interpolation stays within a matched shot and compatible view. Required
incomplete footage never falls back to a held pose. The player remains usable
when source matching is unavailable; the warning distinguishes video playback
from verified geometry synchronization.

The current observation corpus is incomplete for all seven videos. The guide
interval 771.6709–779.211767 seconds contains a post/thumbclamp whose native CAD
correspondence has not been established. It remains required and blocks footage
acceptance. Source-camera reprojection results conditional on unmeasured poses
are not a complete physical match.

## Browser verification

`verify:sync` checks the original media identity, decoded samples, source-image
provenance and complete observations before launching the production site. It
requires all seven pages, every integer-second sample and recorded change, a
38.4-pixel maximum landmark error and 0.5-second maximum timing error. Missing
media, blocked external playback and missing native geometry fail the command.

The verifier clicks the real YouTube controls and reads the iframe's actual
HTMLMediaElement state, decoded size, duration and currentTime. It rejects ads,
muted playback, seeking/buffering samples and incorrect native content. Reference
review seeks the official player, waits for a paused decoded frame and restores
exploration afterwards. Compact mode must keep the same visible iframe at least
200 by 200 pixels with working pause/resume controls and advancing audible media.

With `?verify=1`, diagnostic three-dimensional landmark markers follow native
node transforms and supported native deformation shaders. They pass through the
same GPU viewport, scissor and mirror rendering path. Readback measures their
actual rendered locations; unsupported, hidden or unresolved landmarks fail.
The diagnostic layer does not replace or mutate native geometry. Captures are
recorded during the draw, and the bridge only reads them afterwards. CPU camera
projection and two aliases of the player's clock are not rendered-pixel or
independent timing evidence.

Paused interaction checks the actual canvas pixels, crank input and unchanged
camera, then verifies pointer-driven orbit while native media remains paused.
A positive mathematical or renderer diagnostic proves only its exercised path;
it does not certify missing footage observations.

## Assets and rights

The full native GLB is approximately 223 MB. The website loads one model and
reuses geometry buffers during motion. Source observations load per video.
Downloaded MP4s, decoded frames, screenshots and verification reports stay
outside tracked publication assets. The site embeds the originals through
YouTube rather than hosting their streams. The 2014 book's non-commercial
material must not enter a commercial website or campaign product.

The default static base path is `/harmonic-analyzer/`. `SIMULATOR_BASE` must be
consistent between Vite build and production verifier. Portfolio sequencing is
owned by the [project board](https://github.com/users/pedropaulovc/projects/1).

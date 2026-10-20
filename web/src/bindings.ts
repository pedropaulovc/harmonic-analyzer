/**
 * Current qualified native component names are the articulation authority.
 * scene.ts projects archived hierarchy names at ingestion, never using a glTF
 * node index or a mesh-array position to choose a binding.
 * Source: SOLIDWORKSGLTF release 39 / 81539e53f5146c06a77541415bd79da673806d96.
 * Historical canonical identity map: cad/config/identity-migration-map.json,
 * SHA-256 1ee9084204cab7025783c5bf0fa98e040cfaa3e4e8200f0d61e58e8dd32c3bfd.
 * The separate current-native-identity projection changes path metadata only;
 * archived model bytes, geometry and this source identity remain unchanged.
 */
export type Motion =
  | 'crank' | 'cone-spin' | 'cone-swing' | 'cylinder' | 'rod' | 'rocker'
  | 'bar' | 'lever' | 'channel-spring' | 'summing' | 'counter-spring'
  | 'gooseneck' | 'magnifier-fixed' | 'magnifier-clamp' | 'magnifier-rod' | 'magnifier-fixture'
  | 'wheel' | 'lever-wire' | 'pen-wire' | 'pen' | 'platen'
  | 'pinion-swing' | 'pinion-cam' | 'pinion-lever'
  | 'paper-knob' | 'paper-feed' | 'paper-sprocket' | 'paper-fixed' | 'chain-link'

export interface Binding {
  id: string
  /** Matched against the complete current-projected CAD component path. */
  pattern: RegExp
  kind: 'single' | 'indexed' | 'group'
  motion: Motion
  /** Exact expected component count; partial resolution remains unverified. */
  expected: number
}

const channel = 'ha-harmonic-analyzer/ch-channel/'
const drive = 'ha-harmonic-analyzer/dt-drive-train/'
const magnifier = 'ha-harmonic-analyzer/mg-magnifier/'
const summing = 'ha-harmonic-analyzer/sm-summing/'
const pen = 'ha-harmonic-analyzer/pn-pen/'
const paper = 'ha-harmonic-analyzer/pd-paper-drive/'

function family(id: string, group: string, name: string, motion: Motion): Binding {
  return { id, pattern: new RegExp(`^${group}${name}-(\\d+)$`), kind: 'indexed', motion, expected: 20 }
}

function group(id: string, path: string, names: string, motion: Motion, expected: number): Binding {
  return { id, pattern: new RegExp(`^${path}(?:${names})$`), kind: expected === 1 ? 'single' : 'group', motion, expected }
}

export const BINDINGS: readonly Binding[] = [
  // build_drive_train_assembly:5464-5501,5695-5745,5785-5795:
  // keeper loop, seat hardware and bonded grip parts ride the keyed crank rig.
  group('crank', drive, '(?:dt-crankshaft|dt-crank-arm|dt-crank-hub|dt-vn-crank-hub-pin|dt-crank-pin|dt-crank-pin-eye|dt-crank-handle-pivot-screw|dt-crank-pin-ring|dt-crank-handle|dt-crank-handle-butt-cup|dt-crank-handle-ferrule|dt-crank-pinion|dt-crank-pinion-pin|dt-crank-seat-washer|dt-vn-keeper-chain|dt-vn-keeper-chain-link|dt-vn-fillister-screw)-1|dt-vn-crank-seat-drive-pin-[12]', 'crank', 19),
  family('coneGears', drive, 'dt-cone-gear', 'cone-spin'),
  // :5994-6023 keys the tip collar to the spinning shaft, not the tip block.
  group('coneShaft', drive, '(?:dt-cone-gear-shaft|dt-crank-drive-gear|dt-vn-cone-tip-collar)-1', 'cone-spin', 3),
  // :5875-5910,5939-5978,6024-6076 carries post/block/fasteners on the plate;
  // :4968-5009 keeps the lock knob and pivot screw base-bolted.
  group('conePlatform', drive, '(?:dt-cone-swing-platform|dt-cone-tip-block|dt-vn-cone-tip-pinch-screw|dt-vn-cone-tip-adjuster|dt-vn-cone-tip-block-screw|dt-cone-pivot-post)-1|dt-vn-post-mount-screw-[12]', 'cone-swing', 8),
  family('cylinderGears', drive, 'dt-cylinder-gear', 'cylinder'),
  family('connectingRods', channel, 'ch-connecting-rod', 'rod'),
  family('rockerArms', channel, 'ch-rocker-arm', 'rocker'),
  family('amplitudeBars', channel, 'ch-amplitude-bar', 'bar'),
  family('channelLevers', channel, 'ch-channel-lever', 'lever'),
  family('channelSprings', channel, 'ch-vn-channel-spring-installed-stretch00', 'channel-spring'),
  family('springSupports', channel, 'ch-vn-spring-hook', 'summing'),
  group('summingLever', summing, '(?:sm-summing-lever|sm-vn-boss-hook)-1', 'summing', 2),
  group('gooseneck', summing, 'sm-gooseneck-1', 'gooseneck', 1),
  group('counterSpring', summing, 'sm-vn-counter-spring-1', 'counter-spring', 1),
  group('magnifierLever', magnifier, '(?:mg-magnifying-lever|mg-magnifying-bracket)-1', 'magnifier-fixed', 2),
  group('magnifierClamp', magnifier, '(?:mg-magnifying-clamp|mg-vn-thumb-screw)-1', 'magnifier-clamp', 2),
  group('magnifierRod', magnifier, 'mg-magnifying-vertical-rod-1', 'magnifier-rod', 1),
  group('magnifyingWheel', magnifier, 'mg-magnifying-wheel-1', 'wheel', 1),
  group('leverWire', magnifier, 'mg-vn-lever-wire-1', 'lever-wire', 1),
  group('penWire', pen, 'pn-vn-pen-wire-1', 'pen-wire', 1),
  group('pen', pen, '(?:pn-pen-rod|pn-pen-v-block|pn-pen-frame|pn-vn-pen-marker|pn-vn-pen-set-screw)-1', 'pen', 5),
  // build_paper_drive_assembly:2185-2476 locks all 33 native carriage bodies
  // to the platen: four clip and ten guide fillisters, eight low lock screws.
  // The guide-lock screws are distinct released parts, not fillisters 15..22.
  group('platen', paper, '(?:pd-platen|pd-platen-rack|pd-platen-paper)-1|(?:pd-platen-clip|pd-platen-guide)-[12]|pd-guide-lock-[1-4]|pd-vn-fillister-screw-(?:[1-9]|1[0-4])|pd-vn-guide-lock-screw-[1-8]', 'platen', 33),
  group('alignmentPinionSwing', drive, 'dt-pinion-bracket-[12]|dt-alignment-pinion-1|dt-pinion-arbor-1|dt-vn-pinion-strap-pin-[123]|dt-pinion-handle-1|dt-pinion-arbor-collar-1', 'pinion-swing', 9),
  group('alignmentPinionCam', drive, 'dt-pinion-cam-[12]|dt-pinion-lift-rod-1|dt-pinion-cam-pin-[12]', 'pinion-cam', 5),
  group('alignmentPinionLever', drive, 'dt-pinion-lever-1|dt-pinion-lever-pin-1', 'pinion-lever', 2),
  // :2699-2844 rigidly joins the collar/shaft/cup hardware about knob axis K.
  // The collar cross-pin and latch-hook rivets are archive-only bodies: scoped
  // to their historical paper-drive parent, without inventing current Numbers.
  group('paperKnob', paper, '(?:pd-transgear-knob-shaft|pd-transgear-thumbnut|pd-transgear-drive-collar|pd-vn-transgear-collar-cross-pin|pd-transgear-knob-cup|pd-vn-transgear-knob-cup-pin|pd-transgear-knob-thrust-ring)-1|pd-vn-transgear-knob-drive-pin-[12]', 'paper-knob', 9),
  // :2598-2662 locks the sleeve, hub and off-axis screws to the disc at stud S.
  group('paperFeed', paper, '(?:pd-rack-pinion|pd-transgear-feed-pinion|pd-transgear-disc-hub)-1|pd-vn-transgear-disc-screw-[123]', 'paper-feed', 6),
  // :56-58,2478-2571,2663-2679 fixes the structure at its authored latched pose.
  // Physical hanger release/swing is not a published MechanismInput DOF.
  group('paperHanger', paper, '(?:pd-transgear-arm|pd-transgear-arm-plate|pd-vn-transgear-latch-pin|pd-transgear-pin|pd-transgear-front-bushing|pd-transgear-rear-bushing|pd-vn-transgear-retaining-ring)-1|pd-vn-transgear-arm-plate-screw-[12]', 'paper-fixed', 9),
  group('paperLatchSupport', paper, '(?:pd-latch-hook|pd-latch-hook-bracket)-1|(?:pd-vn-latch-hook-bracket-screw|pd-vn-latch-hook-rivet)-[12]', 'paper-fixed', 6),
  // transgear_pivot_spring_spec:18-24,46-52: installed disc-spring geometry,
  // not a channel/counter swept-wire spring and not a runtime deformation law.
  group('paperPivotSupport', paper, '(?:pd-vn-transgear-pivot-screw|pd-transgear-pivot-spacer|pd-vn-transgear-pivot-spring)-1', 'paper-fixed', 3),
  // _chain:154-185 / build_paper_drive_assembly:1936-2004: 34 inner + 34 outer.
  group('paperChain', paper, 'pd-vn-chain-(?:outer|inner)-link-(?:[1-9]|[12][0-9]|3[0-4])', 'chain-link', 68),
  group('paperSprockets', paper, 'pd-transgear-removable-[123]', 'paper-sprocket', 3),
  group('magnifierFixture', magnifier, 'mg-output-fixture-1', 'magnifier-fixture', 1),
]

/**
 * Every magnifier thumb-screw instance the model actually contains must ride a
 * declared motion. The output fixture's axial screw (mg-vn-thumb-screw-2, placed by
 * build_mg_magnifier_assembly as 'thumb-screw (output fixture)') is absent from
 * release 39; binding it needs the refreshed GLB census, so until then a model
 * that carries it is reported unverified rather than drawn permanently fixed.
 */
export const UNBOUND_THUMB_SCREW_ISSUE = 'web: bind magnifier fixture thumb-screw-2 to the output fixture at next GLB refresh (https://github.com/pedropaulovc/harmonic-analyzer/issues/1351)'
const MAGNIFIER_THUMB_SCREW = new RegExp(`^${magnifier}mg-vn-thumb-screw-\\d+$`)

/** Present magnifier thumb-screw paths no binding resolves, as unverified-binding messages. */
export function unboundThumbScrewFailures(paths: Iterable<string>): string[] {
  const failures: string[] = []
  for (const path of paths) {
    if (!MAGNIFIER_THUMB_SCREW.test(path) || BINDINGS.some(binding => binding.pattern.test(path))) continue
    failures.push(`${path}: present thumb-screw instance has no motion binding (${UNBOUND_THUMB_SCREW_ISSUE})`)
  }
  return failures
}

/** Physical station number, not harmonic number (instance 1 is harmonic 20). */
export function instanceIndex(name: string, pattern: RegExp): number {
  const captured = name.match(pattern)?.[1]
  return captured ? Number.parseInt(captured, 10) : 0
}

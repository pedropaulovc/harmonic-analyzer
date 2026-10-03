/**
 * Qualified native component names are the articulation authority. GLTFLoader
 * makes duplicate short names unique; scene.ts uses the original userData.name
 * at each hierarchy level, never a glTF node index or a mesh-array position.
 * Source: SOLIDWORKSGLTF release 39 / 81539e53f5146c06a77541415bd79da673806d96.
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
  /** Matched against the complete original CAD component path. */
  pattern: RegExp
  kind: 'single' | 'indexed' | 'group'
  motion: Motion
  /** Exact expected component count; partial resolution remains unverified. */
  expected: number
}

const channel = 'harmonic-analyzer/channel/'
const drive = 'harmonic-analyzer/drive-train/'
const magnifier = 'harmonic-analyzer/magnifier/'
const summing = 'harmonic-analyzer/summing/'
const pen = 'harmonic-analyzer/pen/'
const paper = 'harmonic-analyzer/paper-drive/'

function family(id: string, group: string, name: string, motion: Motion): Binding {
  return { id, pattern: new RegExp(`^${group}${name}-(\\d+)$`), kind: 'indexed', motion, expected: 20 }
}

function group(id: string, path: string, names: string, motion: Motion, expected: number): Binding {
  return { id, pattern: new RegExp(`^${path}(?:${names})$`), kind: expected === 1 ? 'single' : 'group', motion, expected }
}

export const BINDINGS: readonly Binding[] = [
  // build_drive_train_assembly:5464-5501,5695-5745,5785-5795:
  // keeper loop, seat hardware and bonded grip parts ride the keyed crank rig.
  group('crank', drive, '(?:crankshaft|crank-arm|crank-hub|crank-hub-pin|crank-pin|crank-pin-eye|crank-handle-pivot-screw|crank-pin-ring|crank-handle|crank-handle-butt-cup|crank-handle-ferrule|crank-pinion|crank-pinion-pin|crank-seat-washer|keeper-chain|keeper-chain-link|fillister-screw)-1|crank-seat-drive-pin-[12]', 'crank', 19),
  family('coneGears', drive, 'cone-gear', 'cone-spin'),
  // :5994-6023 keys the tip collar to the spinning shaft, not the tip block.
  group('coneShaft', drive, '(?:cone-gear-shaft|crank-drive-gear|cone-tip-collar)-1', 'cone-spin', 3),
  // :5875-5910,5939-5978,6024-6076 carries post/block/fasteners on the plate;
  // :4968-5009 keeps the lock knob and pivot screw base-bolted.
  group('conePlatform', drive, '(?:cone-swing-platform|cone-tip-block|cone-tip-block-screw|cone-tip-pinch-screw|cone-tip-adjuster|cone-pivot-post)-1|post-mount-screw-[12]', 'cone-swing', 8),
  family('cylinderGears', drive, 'cylinder-gear', 'cylinder'),
  family('connectingRods', channel, 'connecting-rod', 'rod'),
  family('rockerArms', channel, 'rocker-arm', 'rocker'),
  family('amplitudeBars', channel, 'amplitude-bar', 'bar'),
  family('channelLevers', channel, 'channel-lever', 'lever'),
  family('channelSprings', channel, 'channel-spring-installed-stretch00', 'channel-spring'),
  family('springSupports', channel, 'spring-hook', 'summing'),
  group('summingLever', summing, '(?:summing-lever|boss-hook)-1', 'summing', 2),
  group('gooseneck', summing, 'gooseneck-1', 'gooseneck', 1),
  group('counterSpring', summing, 'counter-spring-1', 'counter-spring', 1),
  group('magnifierLever', magnifier, '(?:magnifying-lever|magnifying-bracket)-1', 'magnifier-fixed', 2),
  group('magnifierClamp', magnifier, '(?:magnifying-clamp|thumb-screw)-1', 'magnifier-clamp', 2),
  group('magnifierRod', magnifier, 'magnifying-vertical-rod-1', 'magnifier-rod', 1),
  group('magnifyingWheel', magnifier, 'magnifying-wheel-1', 'wheel', 1),
  group('leverWire', magnifier, 'lever-wire-1', 'lever-wire', 1),
  group('penWire', pen, 'pen-wire-1', 'pen-wire', 1),
  group('pen', pen, '(?:pen-rod|pen-v-block|pen-frame|pen-marker|pen-set-screw)-1', 'pen', 5),
  // build_paper_drive_assembly:2185-2476 locks all 33 native carriage bodies
  // to the platen: four clip and ten guide fillisters, eight low lock screws.
  group('platen', paper, '(?:platen|platen-rack|platen-paper)-1|(?:platen-clip|platen-guide)-[12]|guide-lock-[1-4]|fillister-screw-(?:[1-9]|1[0-4])|guide-lock-screw-[1-8]', 'platen', 33),
  group('alignmentPinionSwing', drive, 'pinion-bracket-[12]|alignment-pinion-1|pinion-arbor-1|pinion-strap-pin-[123]|pinion-handle-1|pinion-arbor-collar-1', 'pinion-swing', 9),
  group('alignmentPinionCam', drive, 'pinion-cam-[12]|pinion-lift-rod-1|pinion-cam-pin-[12]', 'pinion-cam', 5),
  group('alignmentPinionLever', drive, 'pinion-lever-1|pinion-lever-pin-1', 'pinion-lever', 2),
  // :2699-2844 rigidly joins the collar/shaft/cup hardware about knob axis K.
  group('paperKnob', paper, '(?:transgear-knob-shaft|transgear-thumbnut|transgear-drive-collar|transgear-collar-cross-pin|transgear-knob-cup|transgear-knob-cup-pin|transgear-knob-thrust-ring)-1|transgear-knob-drive-pin-[12]', 'paper-knob', 9),
  // :2598-2662 locks the sleeve, hub and off-axis screws to the disc at stud S.
  group('paperFeed', paper, '(?:rack-pinion|transgear-feed-pinion|transgear-disc-hub)-1|transgear-disc-screw-[123]', 'paper-feed', 6),
  // :56-58,2478-2571,2663-2679 fixes the structure at its authored latched pose.
  // Physical hanger release/swing is not a published MechanismInput DOF.
  group('paperHanger', paper, '(?:transgear-arm|transgear-arm-plate|transgear-latch-pin|transgear-pin|transgear-front-bushing|transgear-rear-bushing|transgear-retaining-ring)-1|transgear-arm-plate-screw-[12]', 'paper-fixed', 9),
  group('paperLatchSupport', paper, '(?:latch-hook|latch-hook-bracket)-1|(?:latch-hook-bracket-screw|latch-hook-rivet)-[12]', 'paper-fixed', 6),
  // transgear_pivot_spring_spec:18-24,46-52: installed disc-spring geometry,
  // not a channel/counter swept-wire spring and not a runtime deformation law.
  group('paperPivotSupport', paper, '(?:transgear-pivot-screw|transgear-pivot-spacer|transgear-pivot-spring)-1', 'paper-fixed', 3),
  // _chain:154-185 / build_paper_drive_assembly:1936-2004: 34 inner + 34 outer.
  group('paperChain', paper, 'chain-(?:outer|inner)-link-(?:[1-9]|[12][0-9]|3[0-4])', 'chain-link', 68),
  group('paperSprockets', paper, 'transgear-removable-[123]', 'paper-sprocket', 3),
  group('magnifierFixture', magnifier, 'output-fixture-1', 'magnifier-fixture', 1),
]

/** Physical station number, not harmonic number (instance 1 is harmonic 20). */
export function instanceIndex(name: string, pattern: RegExp): number {
  const captured = name.match(pattern)?.[1]
  return captured ? Number.parseInt(captured, 10) : 0
}

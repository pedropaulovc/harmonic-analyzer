import test, { after } from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { Matrix4, Quaternion, Vector3 } from 'three'

// Consumer constraint controls, not recovered source poses or browser/GL proof.
// The provider contains released native bodies with current mechanics transforms;
// it never feeds a previous source override back into the normal baseline.
const server = await createServer({
  root: fileURLToPath(new URL('../', import.meta.url)),
  configFile: false,
  server: { middlewareMode: true, hmr: false, watch: null, ws: false },
  appType: 'custom',
})
after(async () => { await server.close() })
let compileSourceAssemblyState, solveSourceAssembly, createSourceAssemblyBuffer
let SOURCE_ASSEMBLY_DATUMS, SOURCE_ASSEMBLY_GROUPS, SOURCE_KEEPER_ANCHORS
let SOURCE_GEAR_PART_PATHS, SOURCE_CHAIN_PART_PATHS, NATIVE_RUNTIME_INSTANCES, NATIVE_TOOL_CONTACT_DATUMS
let createMechanismInput, createMechanismPose, solveMechanism, MECHANISM_DATA, BINDINGS, PAPER_FEED_MULTIPLIER
try {
  ;({ compileSourceAssemblyState, solveSourceAssembly, createSourceAssemblyBuffer,
    SOURCE_ASSEMBLY_DATUMS, SOURCE_ASSEMBLY_GROUPS, SOURCE_KEEPER_ANCHORS,
    SOURCE_GEAR_PART_PATHS, SOURCE_CHAIN_PART_PATHS, NATIVE_RUNTIME_INSTANCES,
    NATIVE_TOOL_CONTACT_DATUMS } = await server.ssrLoadModule(process.env.SOURCE_ASSEMBLY_MODULE ?? '/src/source-assembly.ts'))
  ;({ createMechanismInput, createMechanismPose, solveMechanism, MECHANISM_DATA } = await server.ssrLoadModule('/src/mechanics.ts'))
  ;({ BINDINGS } = await server.ssrLoadModule('/src/bindings.ts'))
  ;({ PAPER_FEED_MULTIPLIER } = await server.ssrLoadModule('/src/kinematics.ts'))
} catch (error) {
  await server.close()
  throw error
}
const inventory = JSON.parse(await readFile(new URL('../content/v39-source/native-inventory.json', import.meta.url), 'utf8'))
const released = new Map(inventory.inventory.map(row => [row.path, new Matrix4().fromArray(row.world)]))
const ROOT = 'ha-harmonic-analyzer'
const CHANNEL = `${ROOT}/ch-channel`
const DRIVE = `${ROOT}/dt-drive-train/`
const PAPER = `${ROOT}/pd-paper-drive/`
const PEN = `${ROOT}/pn-pen/`
const STICK = `${ROOT}/ha-measuring-stick-1`
const STOP = `${ROOT}/ha-measuring-stick-stop-1`
const HUB = SOURCE_ASSEMBLY_GROUPS.crankCarrier[0]
const PIN = SOURCE_ASSEMBLY_GROUPS.crankPin[0]
const [LOOP, CONNECTOR] = SOURCE_ASSEMBLY_GROUPS.keeper
const NUT = `${PAPER}pd-transgear-thumbnut-1`
const ROD = `${PEN}pn-pen-rod-1`
const GUIDE = `${PEN}pn-pen-hanger-1`
const FRAME = SOURCE_ASSEMBLY_GROUPS.penFrame[0]
const MARKER = `${PEN}pn-pen-marker-1`
const WIRE = `${PEN}pn-pen-wire-1`
const GEAR_IDS = Object.keys(SOURCE_GEAR_PART_PATHS)
const EPS = 2e-8
const provenance = {
  kind: 'chosen-feasible', videoId: 'jfH-NbsmvD4', frameIndex: 1300,
  evidence: 'Synthetic native constraint control, not a measured source trajectory.',
  unobservedDegreesOfFreedom: ['Chosen service poses and complete current normal input.'],
}
function descriptor(domains) { return { kind: 'source-assembly', provenance, ...domains } }
function body(path) {
  const matrix = released.get(path)
  assert.ok(matrix, `Missing released fixture body ${path}`)
  return matrix.clone()
}
function position(matrix) { return new Vector3().setFromMatrixPosition(matrix) }
function pose(matrix) {
  const p = new Vector3(), q = new Quaternion(), s = new Vector3()
  matrix.decompose(p, q, s)
  return { positionMetres: p.toArray(), quaternion: q.normalize().toArray() }
}
function point(matrix, local) { return new Vector3().fromArray(local).applyMatrix4(matrix) }
function axis(matrix, column) { return new Vector3().setFromMatrixColumn(matrix, column).normalize() }
function rotationAt(matrix, angle, x, y) {
  return new Matrix4().makeTranslation(x, y, 0)
    .multiply(new Matrix4().makeRotationZ(angle))
    .multiply(new Matrix4().makeTranslation(-x, -y, 0)).multiply(matrix)
}
function movedRoot() {
  return new Matrix4().compose(new Vector3(.37, -.18, .22),
    new Quaternion().setFromAxisAngle(new Vector3(1, 2, -1).normalize(), .43), new Vector3(1, 1, 1))
}
function fixture({ phase = 0, gearing = 'small-large', crankTurns = 0, root = new Matrix4() } = {}) {
  const input = createMechanismInput(), normal = createMechanismPose()
  input.amplitudes.fill(0); input.phases.fill(phase)
  input.gearing = gearing; input.crankTurns = crankTurns
  solveMechanism(input, normal)
  const matrices = new Map([...released].map(([path, matrix]) => [path, matrix.clone()]))
  const C = MECHANISM_DATA.channel
  for (let station = 1; station <= 20; station++) {
    const j = station - 1, p = 3 * j
    const rocker = `${CHANNEL}/ch-rocker-arm-${station}`
    const bar = `${CHANNEL}/ch-amplitude-bar-${station}`
    const lever = `${CHANNEL}/ch-channel-lever-${station}`
    const r = body(rocker), b = body(bar), l = body(lever)
    matrices.set(rocker, rotationAt(r, normal.rockerAnglesRad[j] - Math.atan2(-r.elements[1], -r.elements[0]), C.pivotMm[0] / 1000, C.pivotMm[1] / 1000))
    const currentBar = rotationAt(b, normal.barAnglesRad[j] - Math.atan2(-b.elements[4], b.elements[5]), b.elements[12], b.elements[13])
    currentBar.setPosition(normal.barOriginsM[p], normal.barOriginsM[p + 1], normal.barOriginsM[p + 2])
    matrices.set(bar, currentBar)
    matrices.set(lever, rotationAt(l, normal.leverAnglesRad[j] - Math.atan2(-l.elements[1], -l.elements[0]), C.fulcrumMm[0] / 1000, C.fulcrumMm[1] / 1000))
  }
  const crankCentre = position(body(`${DRIVE}dt-crankshaft-1`))
  const knobCentre = position(body(`${PAPER}pd-transgear-knob-shaft-1`))
  const feedCentre = position(body(`${PAPER}pd-rack-pinion-1`))
  const knobAngle = normal.crankAngleRad * MECHANISM_DATA.paperDrive.chainRatioFine * PAPER_FEED_MULTIPLIER[gearing]
  const feedAngle = knobAngle * MECHANISM_DATA.paperDrive.externalMeshSense * MECHANISM_DATA.paperDrive.reducerRatio
  for (const [path, matrix] of matrices) {
    const binding = BINDINGS.find(binding => binding.pattern.test(path))
    if (binding?.motion === 'crank') matrices.set(path, rotationAt(matrix, normal.crankAngleRad, crankCentre.x, crankCentre.y))
    else if (binding?.motion === 'paper-knob') matrices.set(path, rotationAt(matrix, knobAngle, knobCentre.x, knobCentre.y))
    else if (binding?.motion === 'paper-feed') matrices.set(path, rotationAt(matrix, feedAngle, feedCentre.x, feedCentre.y))
    else if (binding?.motion === 'pen') matrix.elements[13] += normal.magnifier.penTravelM
  }
  const upperFrame = body(SOURCE_GEAR_PART_PATHS.T24), crankFrame = body(SOURCE_GEAR_PART_PATHS.T12)
  const upperSeat = rotationAt(upperFrame, knobAngle, upperFrame.elements[12], upperFrame.elements[13])
  const crankSeat = rotationAt(crankFrame, normal.crankAngleRad, crankFrame.elements[12], crankFrame.elements[13])
  const seated = gearing === 'medium-medium' ? { upper: 'T18-upper', crank: 'T18-crank' }
    : gearing === 'large-small' ? { upper: 'T12', crank: 'T24' } : { upper: 'T24', crank: 'T12' }
  for (const declaration of Object.values(NATIVE_RUNTIME_INSTANCES)) matrices.set(declaration.partPath, body(declaration.templatePartPath))
  matrices.set(SOURCE_GEAR_PART_PATHS[seated.upper], upperSeat)
  matrices.set(SOURCE_GEAR_PART_PATHS[seated.crank], crankSeat)
  for (const matrix of matrices.values()) matrix.premultiply(root)
  const visible = new Map([...matrices.keys()].map(path => [path, true]))
  for (const id of GEAR_IDS) visible.set(SOURCE_GEAR_PART_PATHS[id], id === seated.upper || id === seated.crank)
  visible.set(NATIVE_RUNTIME_INSTANCES.upperMedium.templatePartPath, false)
  const context = {
    partPaths: [...matrices.keys()],
    readWorldMatrix(path, out) { const m = matrices.get(path); if (!m) return false; out.set(m.elements); return true },
    readVisibility(path) { return visible.get(path) ?? null },
    readGearSeatWorldMatrix(seat, out) {
      const path = SOURCE_GEAR_PART_PATHS[seated[seat]]
      if (!visible.get(path)) return false
      out.set(matrices.get(path).elements); return true
    },
    readSeatedGearPartPath(seat) { const path = SOURCE_GEAR_PART_PATHS[seated[seat]]; return visible.get(path) ? path : null },
  }
  return { input, normal, root, matrices, visible, seated, context }
}
function solve(domains, f = fixture()) {
  const compiled = compileSourceAssemblyState(descriptor(domains))
  const overrides = solveSourceAssembly(compiled, f.context, createSourceAssemblyBuffer())
  // The public result is ephemeral; consumer snapshots must own their copy.
  const entries = new Map(overrides.map(entry => [entry.partPath, structuredClone(entry)]))
  const matrix = path => {
    const current = f.matrices.get(path)
    assert.ok(current, `Unknown consumer body ${path}`)
    const entry = entries.get(path)
    if (!entry) return current.clone()
    const scale = new Vector3(), q = new Quaternion(), p = new Vector3()
    current.decompose(p, q, scale)
    return new Matrix4().compose(new Vector3().fromArray(entry.worldPositionMetres),
      new Quaternion().fromArray(entry.worldQuaternion).normalize(), scale)
  }
  return { compiled, entries, matrix, f }
}
function reject(domains, f = fixture(), reason) {
  assert.throws(() => solve(domains, f), reason)
}
function near(actual, expected, tolerance = EPS, label = 'Native contact') {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${label}: ${actual} versus ${expected}`)
}
function nearPoint(actual, expected, tolerance = EPS, label = 'Native contact point') {
  assert.ok(actual.distanceTo(expected) <= tolerance, `${label}: residual ${actual.distanceTo(expected)} m`)
}
function samePose(a, b, tolerance = 1e-12) {
  nearPoint(position(a), position(b), tolerance, 'Consumer pose origin')
  const qa = pose(a).quaternion, qb = pose(b).quaternion
  const sign = qa.reduce((sum, value, j) => sum + value * qb[j], 0) < 0 ? -1 : 1
  near(Math.max(...qa.map((value, j) => Math.abs(value - sign * qb[j]))), 0, tolerance, 'Consumer pose rotation')
}
function farPose(index = 0) { return { positionMetres: [2 + index, 2, 2], quaternion: [0, 0, 0, 1] } }
function gears(f, changes = {}) {
  const members = Object.fromEntries(GEAR_IDS.map((id, index) => [id,
    id === f.seated.upper ? { attachment: 'upper', phaseRad: 0 }
      : id === f.seated.crank ? { attachment: 'crank', phaseRad: 0 }
        : { attachment: 'stored', pose: farPose(index) }]))
  return { members: { ...members, ...changes } }
}
function closedChain(origin = new Vector3(10, 10, 10), normal = new Vector3(0, 0, 1)) {
  const q = new Quaternion().setFromUnitVectors(new Vector3(0, 0, 1), normal)
  const radius = SOURCE_ASSEMBLY_DATUMS.chainChordMetres / (2 * Math.sin(Math.PI / 68))
  const jointsMetres = Array.from({ length: 68 }, (_, j) => new Vector3(radius * (Math.cos(2 * Math.PI * j / 68) - 1), radius * Math.sin(2 * Math.PI * j / 68), 0).applyQuaternion(q).add(origin).toArray())
  return { attachment: 'held-off-sprockets', jointsMetres, planeNormal: normal.toArray(), contacts: [{ kind: 'held', joint: 0, positionMetres: origin.toArray() }] }
}
function keeper(f, retainedAnchor, delta) {
  return { retainedAnchor, loopPose: pose(f.matrices.get(LOOP).clone().premultiply(delta)),
    connectorPose: pose(f.matrices.get(CONNECTOR).clone().premultiply(delta)) }
}
function crank(f, carrier = { attachment: 'installed' }, pin = { attachment: 'held', pose: farPose() }, retainedAnchor = 'eye') {
  const path = retainedAnchor === 'eye' ? HUB : PIN
  const attachment = retainedAnchor === 'eye' ? carrier : pin
  const current = f.matrices.get(path)
  let delta
  if (attachment.attachment === 'held') {
    const q = new Quaternion().fromArray(attachment.pose.quaternion)
      .multiply(new Quaternion().fromArray(pose(current).quaternion).invert())
    const p = new Vector3().fromArray(attachment.pose.positionMetres).sub(position(current).applyQuaternion(q))
    delta = new Matrix4().compose(p, q, new Vector3(1, 1, 1))
  } else {
    const p = axis(current, retainedAnchor === 'eye' ? 1 : 0).multiplyScalar(-(attachment.travelMetres ?? 0))
    delta = new Matrix4().makeTranslation(p.x, p.y, p.z)
  }
  return { carrier, pin, keeper: keeper(f, retainedAnchor, delta) }
}
function service(f, changes) {
  return { retainingNut: { attachment: 'threaded', releaseTurns: 0 }, gears: gears(f), chain: closedChain(), ...changes }
}
function pen(f, changes = {}) {
  return { rod: { attachment: 'installed' }, yawDeltaRad: 0, vBlock: { attachment: 'rod' },
    frame: { attachment: 'v-block' }, marker: { attachment: 'frame' }, wire: { attachment: 'released', pose: farPose() }, ...changes }
}
function tool(number, station = 1, attachment = 'bar-at-tool-end') {
  return { attachment, station, stopAtStickMetres: SOURCE_ASSEMBLY_DATUMS.stickEngravedZeroMetres
    + number * SOURCE_ASSEMBLY_DATUMS.stickEngravedDivisionMetres - NATIVE_TOOL_CONTACT_DATUMS.stopFrontEdge }
}

// Exact released raw roof vertices, independently observed through consumer poses.
// No analytic R800 support point: the finite facets are the contact authority.
const roof = [
  [-.14524006843566895, .029294639825820923], [-.12604920566082, .025992659851908684],
  [-.1067836731672287, .02315874956548214], [-.08745487034320831, .020794589072465897],
  [-.06807424873113632, .018901577219367027], [-.048653289675712585, .01748083531856537],
  [-.0292035099118948, .016533205285668373], [-.009736426174640656, .016059251502156258],
  [.009736426174640656, .016059251502156258], [.0292035099118948, .016533205285668373],
  [.048653289675712585, .01748083531856537], [.06807424873113632, .018901577219367027],
  [.08745487034320831, .020794589072465897], [.1067836731672287, .02315874956548214],
  [.12604920566082, .025992659851908684], [.14524006843566895, .029294639825820923],
]
function clipRoof(points, coordinate, lo, hi) {
  const samples = []
  for (let j = 0; j < points.length - 1; j++) {
    const a = points[j], b = points[j + 1]
    if (a[coordinate] >= lo && a[coordinate] <= hi) samples.push(a)
    for (const edge of [lo, hi]) if ((edge - a[coordinate]) * (edge - b[coordinate]) < 0) {
      samples.push(a.clone().lerp(b, (edge - a[coordinate]) / (b[coordinate] - a[coordinate])))
    }
  }
  const last = points.at(-1)
  if (last[coordinate] >= lo && last[coordinate] <= hi) samples.push(last)
  return samples
}
function observeBar(result, station) {
  const D = NATIVE_TOOL_CONTACT_DATUMS
  const bar = result.matrix(`${CHANNEL}/ch-amplitude-bar-${station}`)
  const rocker = result.matrix(`${CHANNEL}/ch-rocker-arm-${station}`)
  const lever = result.matrix(`${CHANNEL}/ch-channel-lever-${station}`)
  const currentRoof = roof.map(([x, y]) => point(rocker, [x, y, 0]))
  const inBar = currentRoof.map(p => p.clone().applyMatrix4(bar.clone().invert()))
  const underNotch = clipRoof(inBar, 'z', 0, D.barWidth)
  const gaps = underNotch.map(p => D.notchRoof - p.y)
  assert.ok(Math.min(...gaps) >= -EPS, 'Native notch must not penetrate a finite roof facet')
  near(Math.min(...gaps), 0, EPS, 'Native notch/roof seat')
  for (const p of underNotch) near(p.x, D.barWidth / 2, EPS, 'Native clevis central groove')
  const pin = point(bar, [D.barWidth / 2, D.upperPinHeight, D.barWidth / 2])
  near(pin.distanceTo(position(lever)), D.leverPinRadius, EPS, 'Current 127mm upper pin loop')
  nearPoint(pin, point(lever, [D.leverPinRadius, 0, 0]), EPS, 'Actual native lever/bar hinge')
  const chassisInverse = result.matrix(CHANNEL).invert()
  const b = bar.clone().premultiply(chassisInverse), r = rocker.clone().premultiply(chassisInverse)
  const foot = point(b, [D.barWidth / 2, 0, D.barWidth / 2])
  return { bar, rocker, lever, currentRoof, footStation: foot.x - r.elements[12] }
}
function observeTool(result, station, { closed = true, bar = true } = {}) {
  const D = NATIVE_TOOL_CONTACT_DATUMS
  const rocker = result.matrix(`${CHANNEL}/ch-rocker-arm-${station}`)
  const stick = result.matrix(STICK), stop = result.matrix(STOP)
  const currentRoof = roof.map(([x, y]) => point(rocker, [x, y, 0]))
  nearPoint(point(stop, [D.stopFrontEdge, 0, 0]), currentRoof.at(-1), EPS, 'Stop front edge / finite roof end')
  const inRule = currentRoof.map(p => p.clone().applyMatrix4(stick.clone().invert()))
  for (const p of clipRoof(inRule, 'x', 0, D.ruleLength)) {
    assert.ok(p.z >= D.ruleThickness - EPS, 'Whole native rule must stay above the roof')
  }
  if (!bar) return
  const observed = observeBar(result, station)
  const endInBar = point(stick, [D.ruleLength, D.ruleWidth / 2, D.ruleThickness]).applyMatrix4(observed.bar.clone().invert())
  assert.ok(endInBar.z >= D.barWidth - EPS, 'Rule end must not pass through the native bar')
  if (closed) near(endInBar.z, D.barWidth, EPS, 'Literal RULEND/native bar face')
  return { ...observed, ruleEndGap: endInBar.z - D.barWidth }
}

test('F1: carrier/crank-wheel clearance includes the real 0.7mm installed gap', () => {
  const f = fixture()
  const installedGap = position(f.matrices.get(SOURCE_GEAR_PART_PATHS.T12))
    .sub(point(f.matrices.get(HUB), [0, .02520000003278, 0]))
    .dot(axis(f.matrices.get(SOURCE_GEAR_PART_PATHS.T12), 2))
  reject(service(f, { gears: gears(f, { T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: .01 } }) }), f, /carrier|wheel|crank|clear/i)
  const carrier = { attachment: 'withdrawing', travelMetres: .01 }
  const domains = service(f, { crank: crank(f, carrier), gears: gears(f, { T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: .01 } }) })
  // Carrier withdrawal opens this gap; wheel-only withdrawal closes it.
  const carrierOnly = solve(service(f, { crank: crank(f, carrier) }), f)
  near(position(carrierOnly.matrix(HUB)).distanceTo(position(f.matrices.get(HUB))), .01)
  const equal = solve(domains, f)
  nearPoint(position(equal.matrix(HUB)), position(f.matrices.get(HUB)).addScaledVector(axis(f.matrices.get(HUB), 1), -.01))
  const touching = solve(service(f, { gears: gears(f, { T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: installedGap } }) }), f)
  near(position(touching.matrix(SOURCE_GEAR_PART_PATHS.T12)).sub(point(touching.matrix(HUB), [0, .02520000003278, 0]))
    .dot(axis(touching.matrix(SOURCE_GEAR_PART_PATHS.T12), 2)), 0, EPS, 'Actual carrier/wheel contact boundary')
  reject(service(f, { gears: gears(f, { T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: installedGap + .000001 } }) }), f, /carrier|wheel|crank|clear/i)
  solve(service(f, { crank: crank(f, carrier), gears: gears(f, { T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: .01 + installedGap } }) }), f)
  reject(service(f, { crank: crank(f, { attachment: 'held', pose: pose(f.matrices.get(HUB)) }) }), f, /carrier|shaft|clear|overlap/i)
  const held = solve(service(f, { crank: crank(f, { attachment: 'held', pose: farPose(5) }) }), f)
  assert.ok(position(held.matrix(HUB)).distanceTo(position(f.matrices.get(`${DRIVE}dt-crankshaft-1`))) > 1,
    'Actual held carrier clears the native fixed shaft')
})

test('F2: upper wheel cannot cross a threaded or physically held retaining nut', () => {
  const f = fixture(), releaseTurns = 2
  reject(service(f, { retainingNut: { attachment: 'threaded', releaseTurns: .01 },
    gears: gears(f, { T24: { attachment: 'upper-withdrawing', phaseRad: 0, travelMetres: .01 } }) }), f, /nut|wheel|upper|clear/i)
  // Released nut inner face vs current wheel outer face, plus actual 1/4-20 advance.
  const nutFace = point(f.matrices.get(NUT), [0, 0, 0])
  const gearFace = point(f.matrices.get(SOURCE_GEAR_PART_PATHS.T24), [0, 0, 0])
  const initialGap = nutFace.clone().sub(gearFace).dot(axis(f.matrices.get(NUT), 1))
  const contactTravel = initialGap + releaseTurns * .0254 / 20
  const touching = solve(service(f, { retainingNut: { attachment: 'threaded', releaseTurns },
    gears: gears(f, { T24: { attachment: 'upper-withdrawing', phaseRad: 0, travelMetres: contactTravel } }) }), f)
  near(position(touching.matrix(SOURCE_GEAR_PART_PATHS.T24)).sub(position(touching.matrix(NUT)))
    .dot(axis(touching.matrix(SOURCE_GEAR_PART_PATHS.T24), 2)), 0, EPS, 'Actual partial-thread wheel/nut contact')
  reject(service(f, { retainingNut: { attachment: 'threaded', releaseTurns },
    gears: gears(f, { T24: { attachment: 'upper-withdrawing', phaseRad: 0, travelMetres: contactTravel + .00001 } }) }), f, /nut|wheel|upper|clear/i)
  reject(service(f, { retainingNut: { attachment: 'held', pose: pose(f.matrices.get(NUT)) },
    gears: gears(f, { T24: { attachment: 'upper-withdrawing', phaseRad: 0, travelMetres: .01 } }) }), f, /nut|wheel|upper|clear|overlap/i)
  const releasedNut = solve(service(f, { retainingNut: { attachment: 'held', pose: farPose() },
    gears: gears(f, { T24: { attachment: 'upper-withdrawing', phaseRad: 0, travelMetres: .01 } }) }), f)
  assert.ok(position(releasedNut.matrix(NUT)).distanceTo(position(f.matrices.get(`${PAPER}pd-transgear-knob-shaft-1`))) > 1,
    'Actual held nut clears its native threaded stud')
})

test('F3: a moving hanger or changed gear seat needs an explicit closed native chain', () => {
  const f = fixture()
  reject({ hanger: { attachment: 'open', swingRad: -.3, hookReleaseRad: 0 } }, f, /chain/i)
  const changed = { retainingNut: { attachment: 'threaded', releaseTurns: 0 }, gears: gears(f, {
    T24: { attachment: 'crank', phaseRad: 0 }, T12: { attachment: 'upper', phaseRad: 0 },
  }) }
  reject(changed, f, /chain/i)
  const unchanged = solve({ retainingNut: { attachment: 'threaded', releaseTurns: 0 }, gears: gears(f) }, f)
  for (const id of [f.seated.upper, f.seated.crank]) samePose(unchanged.matrix(SOURCE_GEAR_PART_PATHS[id]), f.matrices.get(SOURCE_GEAR_PART_PATHS[id]))
  const exchanged = solve({ ...changed, retainingNut: { attachment: 'held', pose: farPose() }, chain: closedChain() }, f)
  nearPoint(position(exchanged.matrix(SOURCE_GEAR_PART_PATHS.T12)), position(f.matrices.get(SOURCE_GEAR_PART_PATHS.T24)))
})

function observeLatchAperture(pin, hook) {
  // Actual finite pressed-pin cylinder sampled at both raw strip faces. This
  // independent surface observation is not the solver's ellipse-bound formula.
  const relative = hook.clone().invert().multiply(pin)
  const base = point(relative, [0, 0, 0]), tip = point(relative, [0, .022224999964237213, 0])
  const direction = tip.clone().sub(base), radius = .001587500050
  let maximumRadius = 0
  for (const face of [0, .0006000000867061317]) for (let sample = 0; sample < 2048; sample++) {
    const angle = sample * 2 * Math.PI / 2048
    const radial = point(relative, [radius * Math.cos(angle), 0, radius * Math.sin(angle)])
    const station = (face - radial.z) / direction.z
    assert.ok(station >= 0 && station <= 1, 'Aperture contact must be on the finite pin')
    maximumRadius = Math.max(maximumRadius, Math.hypot(radial.x + station * direction.x + .076543,
      radial.y + station * direction.y + .0036917))
  }
  return maximumRadius
}

test('F4: latch aperture tests the final current geometry, not release history', () => {
  const f = fixture()
  reject({ hanger: { attachment: 'unlatched', swingRad: 0, hookReleaseRad: -.1 } }, f, /hook|positive|range|bound/i)
  const latched = solve({ hanger: { attachment: 'latched', swingRad: 0, hookReleaseRad: 0 } }, f)
  samePose(latched.matrix(`${PAPER}vn-transgear-latch-pin-1`), f.matrices.get(`${PAPER}vn-transgear-latch-pin-1`))
  assert.ok(observeLatchAperture(latched.matrix(`${PAPER}vn-transgear-latch-pin-1`), latched.matrix(`${PAPER}pd-latch-hook-1`)) <= .0027)
  const inside = solve({ hanger: { attachment: 'open', swingRad: .00768479506454, hookReleaseRad: 0 }, chain: closedChain() }, f)
  assert.ok(observeLatchAperture(inside.matrix(`${PAPER}vn-transgear-latch-pin-1`), inside.matrix(`${PAPER}pd-latch-hook-1`)) <= .0027)
  const pivot = f.matrices.get(`${PAPER}pd-transgear-pivot-spacer-1`)
  const outsidePin = rotationAt(f.matrices.get(`${PAPER}vn-transgear-latch-pin-1`), .00768679506454, pivot.elements[12], pivot.elements[13])
  assert.ok(observeLatchAperture(outsidePin, f.matrices.get(`${PAPER}pd-latch-hook-1`)) > .0027001)
  reject({ hanger: { attachment: 'open', swingRad: .00768679506454, hookReleaseRad: 0 }, chain: closedChain() }, f, /latch|hook|aperture|pin/i)
  const clear = solve({ hanger: { attachment: 'open', swingRad: -.3, hookReleaseRad: 0 }, chain: closedChain() }, f)
  const clearRelative = clear.matrix(`${PAPER}pd-latch-hook-1`).invert().multiply(clear.matrix(`${PAPER}vn-transgear-latch-pin-1`))
  const baseZ = point(clearRelative, [0, 0, 0]).z, tipZ = point(clearRelative, [0, .022224999964237213, 0]).z
  const radialZ = .001587500050 * Math.hypot(clearRelative.elements[2], clearRelative.elements[10])
  assert.ok(Math.max(baseZ, tipZ) + radialZ < 0, 'The entire finite pin clears the unchanged hook plane')
})

test('F5: shaft-linked pin, gear and cap families are finite; held pin needs actual clearance', () => {
  const f = fixture()
  // Historical old-shape control: fail on unbounded gear travel, not a newer
  // pin limit datum or retained-anchor descriptor prerequisite.
  reject(service(f, {
    crank: { pin: { attachment: 'installed' }, carrier: { attachment: 'installed' } },
    gears: gears(f, { T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: 10 } }),
  }), f, /T12|finite|travel|range|bound/i)
  const pinAt = SOURCE_ASSEMBLY_DATUMS.pinWithdrawalMaxMetres
  const pinResult = solve({ crank: crank(f, { attachment: 'installed' }, { attachment: 'withdrawing', travelMetres: pinAt }, 'ring') }, f)
  near(position(pinResult.matrix(PIN)).distanceTo(position(f.matrices.get(PIN))), pinAt)
  reject({ crank: crank(f, { attachment: 'installed' }, { attachment: 'withdrawing', travelMetres: 10 }, 'ring') }, f, /pin|travel|range|bound/i)
  reject({ crank: crank(f, { attachment: 'installed' }, { attachment: 'held', pose: pose(f.matrices.get(PIN)) }, 'eye') }, f, /pin|hub|shaft|clear|overlap/i)
  solve({ crank: crank(f) }, f)
  for (const [id, seat, maximum] of [['T24', 'upper', SOURCE_ASSEMBLY_DATUMS.upperGearWithdrawalMaxMetres], ['T12', 'crank', SOURCE_ASSEMBLY_DATUMS.crankGearWithdrawalMaxMetres]]) {
    const changes = { retainingNut: { attachment: 'held', pose: farPose() },
      crank: crank(f, { attachment: 'held', pose: farPose(5) }), gears: gears(f, { [id]: { attachment: `${seat}-withdrawing`, phaseRad: 0, travelMetres: maximum } }) }
    const result = solve(service(f, changes), f)
    near(position(result.matrix(SOURCE_GEAR_PART_PATHS[id])).distanceTo(position(f.matrices.get(SOURCE_GEAR_PART_PATHS[id]))), maximum)
    reject(service(f, { ...changes, gears: gears(f, { [id]: { attachment: `${seat}-withdrawing`, phaseRad: 0, travelMetres: 10 } }) }), f, /gear|T24|T12|travel|range|bound/i)
  }
  for (const [domain, path, maximum] of [['frame', FRAME, .036], ['marker', MARKER, .10999999940395355]]) {
    const result = solve({ pen: pen(f, { [domain]: { attachment: 'inserting', travelMetres: maximum } }) }, f)
    near(position(result.matrix(path)).distanceTo(position(f.matrices.get(path))), maximum)
    reject({ pen: pen(f, { [domain]: { attachment: 'inserting', travelMetres: 10 } }) }, f, /frame|marker|travel|range|bound/i)
  }
})

test('F5: rod withdrawal ends at the actual current fixed guide, not a rest length', () => {
  for (const guideShift of [0, -.002]) {
    const f = fixture({ root: movedRoot() })
    f.matrices.get(GUIDE).elements[12] += axis(f.matrices.get(ROD), 1).x * guideShift
    f.matrices.get(GUIDE).elements[13] += axis(f.matrices.get(ROD), 1).y * guideShift
    f.matrices.get(GUIDE).elements[14] += axis(f.matrices.get(ROD), 1).z * guideShift
    const guideInRod = point(f.matrices.get(GUIDE), [0, -.006000000052154064, 0]).applyMatrix4(f.matrices.get(ROD).clone().invert())
    const clearance = Math.max(0, SOURCE_ASSEMBLY_DATUMS.rodLengthMetres - guideInRod.y)
    const result = solve({ pen: pen(f, { rod: { attachment: 'withdrawing', travelMetres: clearance } }) }, f)
    near(position(result.matrix(ROD)).distanceTo(position(f.matrices.get(ROD))), clearance)
    reject({ pen: pen(f, { rod: { attachment: 'withdrawing', travelMetres: clearance + .00001 } }) }, f, /current.*guide|guide.*clear/i)
    reject({ pen: pen(f, { rod: { attachment: 'withdrawing', travelMetres: 10 } }) }, f, /rod|travel|range|bound/i)
  }
})

test('F6: native keeper retains the actual moving eye/ring and both bead seats', () => {
  const f = fixture({ root: movedRoot() })
  const cases = [crank(f, { attachment: 'withdrawing', travelMetres: .01 }),
    crank(f, { attachment: 'installed' }, { attachment: 'withdrawing', travelMetres: .02 }, 'ring')]
  for (const current of cases) {
    const result = solve({ crank: current }, f)
    const anchor = SOURCE_KEEPER_ANCHORS[current.keeper.retainedAnchor]
    nearPoint(point(result.matrix(anchor.partPath), anchor.localPointMetres), point(result.matrix(LOOP), anchor.loopLocalPointMetres))
    for (const end of [[-.00285, 0, 0], [.00285, 0, 0]]) {
      const loopLocal = point(f.matrices.get(CONNECTOR), end).applyMatrix4(f.matrices.get(LOOP).clone().invert())
      nearPoint(point(result.matrix(CONNECTOR), end), point(result.matrix(LOOP), loopLocal.toArray()), EPS, 'Both native bead seats')
    }
    const escaped = structuredClone(current)
    escaped.keeper.loopPose.positionMetres[0] += 1; escaped.keeper.connectorPose.positionMetres[0] += 1
    reject({ crank: escaped }, f, /retained.*eye|retained.*ring|retained.*contact/i)
    const brokenBead = structuredClone(current)
    brokenBead.keeper.connectorPose.positionMetres[0] += .00025
    reject({ crank: brokenBead }, f, /bead|loop-link/i)
  }
})

test('F7: native printed 0/5/10 close the rule end, finite roof and current 127mm loop', () => {
  for (const root of [new Matrix4(), movedRoot()]) for (const number of [0, 5, 10]) {
    const f = fixture({ root })
    observeTool(solve({ measuringTool: tool(number) }, f), 1)
  }
})

test('F7: current nonhome poses retain real tool contacts; a point loop alone is insufficient', () => {
  for (const phase of [.7, Math.PI / 2, 3 * Math.PI / 2]) for (const number of [5, 10]) {
    const f = fixture({ phase, root: movedRoot() })
    observeTool(solve({ measuringTool: tool(number) }, f), 1)
    const seated = solve({ measuringTool: tool(number, 1, 'on-rocker') }, f)
    observeTool(seated, 1, { bar: false })
    samePose(seated.matrix(`${CHANNEL}/ch-amplitude-bar-1`), f.matrices.get(`${CHANNEL}/ch-amplitude-bar-1`))
  }
  reject({ measuringTool: tool(5) }, fixture({ phase: Math.PI }), /rule|rocker|penetrat|intersect|feasib|contact/i)
})

test('F7: a manual approach stays clear and 250 micrometres beyond closure is rejected', () => {
  const f = fixture()
  const closed = observeTool(solve({ measuringTool: tool(5) }, f), 1)
  for (const fraction of [.25, .5, .75]) {
    const station = closed.footStation * fraction
    const result = solve({ measuringTool: { ...tool(5, 1, 'bar-setting'), barFootStationMetres: station } }, f)
    const observed = observeTool(result, 1, { closed: false })
    near(observed.footStation, station, EPS, 'Literal manual foot station')
    assert.ok(observed.ruleEndGap > .00001, 'Approaching native bar must remain physically clear of the rule end')
  }
  reject({ measuringTool: { ...tool(5, 1, 'bar-setting'), barFootStationMetres: closed.footStation - .00025 } }, f, /rule|bar|penetrat|overlap|feasib|contact/i)
})

test('F7: retained printed5 survives setting station2 to10 and withdrawing the current tool', () => {
  const f = fixture()
  const first = solve({ measuringTool: tool(5) }, f), firstObserved = observeTool(first, 1)
  const second = solve({ manualBars: [{ station: 1, barFootStationMetres: firstObserved.footStation }], measuringTool: tool(10, 2) }, f)
  const secondObserved = observeTool(second, 2)
  samePose(first.matrix(`${CHANNEL}/ch-amplitude-bar-1`), second.matrix(`${CHANNEL}/ch-amplitude-bar-1`), EPS)
  samePose(first.matrix(`${CHANNEL}/ch-channel-lever-1`), second.matrix(`${CHANNEL}/ch-channel-lever-1`), EPS)
  const manualBars = [{ station: 1, barFootStationMetres: firstObserved.footStation }, { station: 2, barFootStationMetres: secondObserved.footStation }]
  const withdrawn = solve({ manualBars, measuringTool: { attachment: 'withdrawn', stickPose: farPose(), stopAtStickMetres: tool(10).stopAtStickMetres } }, f)
  for (const station of [1, 2]) {
    observeBar(withdrawn, station)
    samePose(second.matrix(`${CHANNEL}/ch-amplitude-bar-${station}`), withdrawn.matrix(`${CHANNEL}/ch-amplitude-bar-${station}`), EPS)
  }
  assert.ok(position(withdrawn.matrix(STICK)).distanceTo(position(withdrawn.matrix(`${CHANNEL}/ch-rocker-arm-1`))) > 1,
    'The withdrawn current tool no longer occupies the retained setup contact')
  // No hypothetical rule: retained5 remains feasible at the rejected attached5 phase.
  observeBar(solve({ manualBars: [manualBars[0]] }, fixture({ phase: Math.PI })), 1)
  reject({ manualBars: [manualBars[0], manualBars[0]] }, f, /unique/i)
  reject({ manualBars: [manualBars[0]], measuringTool: tool(5) }, f, /tool.*station|retained.*constraint/i)
  reject({ manualBars: [{ station: 1, barFootStationMetres: .150001 }] }, f, /foot|range|bound/i)
})

test('F7: retained setup covers all twenty physical stations and rejects ambiguous cardinality', () => {
  const f = fixture()
  const footStation = observeTool(solve({ measuringTool: tool(5) }, f), 1).footStation
  const manualBars = Array.from({ length: 20 }, (_, j) => ({ station: j + 1, barFootStationMetres: footStation }))
  const result = solve({ manualBars }, f)
  for (const station of [1, 20]) near(observeBar(result, station).footStation, footStation, EPS, 'Retained station boundary')
  reject({ manualBars: [] }, f, /one through twenty|retained/i)
  reject({ manualBars: [...manualBars, manualBars[0]] }, f, /one through twenty|retained/i)
  for (const station of [0, 21]) reject({ manualBars: [{ station, barFootStationMetres: footStation }] }, f, /station|range|bound/i)
})

test('F8: zero additional gear phase preserves the actual current mounted wheel in every gearing', () => {
  for (const gearing of ['small-large', 'medium-medium', 'large-small']) {
    const f = fixture({ gearing, crankTurns: .137, root: movedRoot() })
    const result = solve({ retainingNut: { attachment: 'threaded', releaseTurns: 0 }, gears: gears(f) }, f)
    for (const seat of ['upper', 'crank']) {
      const path = f.context.readSeatedGearPartPath(seat), current = new Float64Array(16)
      assert.equal(f.context.readGearSeatWorldMatrix(seat, current), true)
      samePose(result.matrix(path), new Matrix4().fromArray(current), 1e-12)
    }
  }
})

test('F9: current inverse-stick stop geometry controls held stop position and closed contacts', () => {
  const f = fixture({ root: movedRoot() }), shifted = fixture({ root: movedRoot() })
  const intrinsicShift = axis(shifted.matrices.get(STICK), 1).multiplyScalar(.0002)
  shifted.matrices.get(STOP).elements[12] += intrinsicShift.x
  shifted.matrices.get(STOP).elements[13] += intrinsicShift.y
  shifted.matrices.get(STOP).elements[14] += intrinsicShift.z
  const measuringTool = { attachment: 'held', stickPose: farPose(), stopAtStickMetres: .12 }
  const original = solve({ measuringTool }, f), current = solve({ measuringTool }, shifted)
  const outputShift = position(current.matrix(STOP)).sub(position(original.matrix(STOP)))
  nearPoint(outputShift, new Vector3(0, .0002, 0), EPS, 'Current stop transverse slide in held stick frame')
  observeTool(solve({ measuringTool: tool(5) }, shifted), 1)
})

test('F11: stop footprint fits just inside both finite rule ends; zero and outside fail', () => {
  const f = fixture(), stickPose = farPose()
  const relative = f.matrices.get(STICK).clone().invert().multiply(f.matrices.get(STOP))
  const e = relative.elements
  const extent = Math.abs(e[0]) * .006000000052154064 + Math.abs(e[4]) * .012000000104308128 + Math.abs(e[8]) * .006000000052154064
  const length = SOURCE_ASSEMBLY_DATUMS.stickLengthMetres
  for (const stopAtStickMetres of [extent + .000001, length - extent - .000001]) {
    const result = solve({ measuringTool: { attachment: 'held', stickPose, stopAtStickMetres } }, f)
    const stopInRule = result.matrix(STICK).invert().multiply(result.matrix(STOP))
    const corners = []
    for (const x of [-.006000000052154064, .006000000052154064]) {
      for (const y of [0, .012000000104308128]) for (const z of [-.006000000052154064, .006000000052154064]) {
        corners.push(point(stopInRule, [x, y, z]).x)
      }
    }
    assert.ok(Math.min(...corners) >= 0 && Math.max(...corners) <= length,
      'Whole consumer stop footprint stays between both literal rule ends')
  }
  for (const stopAtStickMetres of [0, extent - .000001, length - extent + .000001]) {
    reject({ measuringTool: { attachment: 'held', stickPose, stopAtStickMetres } }, f, /stop|finite|footprint|range|bound/i)
  }
})

function toothChain(matrix, id) {
  const teeth = id === 'T24' ? 24 : id === 'T12' ? 12 : 18
  const radius = SOURCE_ASSEMBLY_DATUMS.chainChordMetres / (2 * Math.sin(Math.PI / teeth))
  const origin = point(matrix, [radius * Math.cos(Math.PI / teeth), radius * Math.sin(Math.PI / teeth), .00139999995008111])
  const chain = closedChain(origin, axis(matrix, 2))
  chain.attachment = 'slack-on-sprockets'; chain.contacts = [{ kind: 'sprocket', joint: 0, gear: id, tooth: 0 }]
  return chain
}
test('F12: an unused hidden T18 cannot support the chain; current visible and attached wheels can', () => {
  const f = fixture()
  reject({ chain: toothChain(f.matrices.get(SOURCE_GEAR_PART_PATHS['T18-upper']), 'T18-upper') }, f, /seated.*visible|visible.*wheel/i)
  const visibleChain = toothChain(f.matrices.get(SOURCE_GEAR_PART_PATHS.T24), 'T24')
  const visible = solve({ chain: visibleChain }, f)
  nearPoint(position(visible.matrix(SOURCE_CHAIN_PART_PATHS[0])), new Vector3().fromArray(visibleChain.jointsMetres[0]))
  const mediumChain = toothChain(f.matrices.get(SOURCE_GEAR_PART_PATHS.T24), 'T18-upper')
  const attached = solve({ retainingNut: { attachment: 'threaded', releaseTurns: 0 }, gears: gears(f, {
    T24: { attachment: 'stored', pose: farPose(4) }, 'T18-upper': { attachment: 'upper', phaseRad: 0 },
  }), chain: mediumChain }, f)
  nearPoint(position(attached.matrix(SOURCE_CHAIN_PART_PATHS[0])), new Vector3().fromArray(mediumChain.jointsMetres[0]))
  const missed = structuredClone(visibleChain)
  missed.contacts[0].tooth = 1
  reject({ chain: missed }, f, /roller-pocket|contact/i)
})

test('F13: physical change census ignores equivalent labels, full turns and quaternion signs', () => {
  const f = fixture()
  const pairs = []
  // Start with old-shape-supported bodies so a historical control fails for
  // counting attachment labels, not for the newer measuring-tool contract.
  const open = { hanger: { attachment: 'open', swingRad: -.3, hookReleaseRad: 0 }, chain: closedChain() }
  pairs.push([open, { ...open, hanger: { ...open.hanger, attachment: 'returning' } }])
  const a = service(f), b = structuredClone(a)
  b.gears.members['T18-upper'].attachment = 'held'
  pairs.push([a, b])
  const phase0 = { retainingNut: { attachment: 'threaded', releaseTurns: 0 }, gears: gears(f) }, phaseTurn = structuredClone(phase0)
  phaseTurn.gears.members.T24.phaseRad = 2 * Math.PI; phaseTurn.gears.members.T12.phaseRad = 2 * Math.PI
  pairs.push([phase0, phaseTurn])
  const gearOut = service(f, { gears: gears(f, {
    T24: { attachment: 'upper-withdrawing', phaseRad: 0, travelMetres: .00005 },
    T12: { attachment: 'crank-withdrawing', phaseRad: 0, travelMetres: .0001 },
  }) })
  const gearIn = structuredClone(gearOut)
  gearIn.gears.members.T24.attachment = 'upper-inserting'; gearIn.gears.members.T12.attachment = 'crank-inserting'
  pairs.push([gearOut, gearIn])
  const held = { attachment: 'held', stickPose: farPose(), stopAtStickMetres: .12 }
  pairs.push([{ measuringTool: held }, { measuringTool: { ...held, attachment: 'withdrawn' } }])
  const withdrawing = service(f, { crank: crank(f, { attachment: 'withdrawing', travelMetres: .01 }, { attachment: 'withdrawing', travelMetres: .041 }) })
  const inserting = structuredClone(withdrawing)
  inserting.crank.carrier.attachment = 'inserting'; inserting.crank.pin.attachment = 'inserting'
  pairs.push([withdrawing, inserting])
  const sign = structuredClone(held)
  sign.stickPose.quaternion = sign.stickPose.quaternion.map(value => -value)
  pairs.push([{ measuringTool: held }, { measuringTool: sign }])
  for (const [left, right] of pairs) {
    const first = solve(left, f), second = solve(right, f)
    assert.equal(first.compiled.physicalKey, second.compiled.physicalKey)
    for (const path of first.entries.keys()) samePose(first.matrix(path), second.matrix(path), EPS)
  }
  const moved = structuredClone(held); moved.stickPose.positionMetres[0] += .001
  const first = solve({ measuringTool: held }, f), second = solve({ measuringTool: moved }, f)
  assert.notEqual(first.compiled.physicalKey, second.compiled.physicalKey)
  near(position(first.matrix(STICK)).distanceTo(position(second.matrix(STICK))), .001, EPS, 'True physical tool motion')
})

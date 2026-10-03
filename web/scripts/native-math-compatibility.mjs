import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import ts from 'typescript'
import * as THREE from 'three'

function incompatible(parameter, actual, expected) {
  throw new Error(`Unsupported native runtime parameter ${parameter}: staged ${JSON.stringify(actual) ?? 'missing'}, supported ${JSON.stringify(expected)}. Update and requalify the runtime mathematics before adopting this CAD release. No live outputs replaced.`)
}

function equalNumber(parameter, actual, expected, tolerance = 32 * Number.EPSILON * Math.max(1, Math.abs(expected))) {
  if (!Number.isFinite(actual) || !Number.isFinite(expected) || Math.abs(actual - expected) > tolerance) incompatible(parameter, actual, expected)
}

function arrayLength(parameter, value, expected) {
  if (!Array.isArray(value) || value.length !== expected) incompatible(`${parameter}.length`, value?.length, expected)
}

function numericConstant(source, name) {
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name) || declaration.name.text !== name) continue
      const value = declaration.initializer
      if (value && ts.isNumericLiteral(value)) return Number(value.text)
      if (value && ts.isPrefixUnaryExpression(value) && ts.isNumericLiteral(value.operand)) {
        if (value.operator === ts.SyntaxKind.MinusToken) return -Number(value.operand.text)
        if (value.operator === ts.SyntaxKind.PlusToken) return Number(value.operand.text)
      }
    }
  }
  throw new Error(`Cannot derive fixed ${name} from magnifier.ts; update the native math compatibility gate with the runtime change. No live outputs replaced.`)
}

function variableInitializer(scope, name) {
  let result
  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === name) result = node.initializer
    ts.forEachChild(node, visit)
  }
  visit(scope)
  if (!result) throw new Error(`Cannot derive fixed ${name} from scene.ts; update the native spring compatibility gate with the runtime change. No live outputs replaced.`)
  return result
}

async function runtimeSpringMath(webRoot) {
  const text = await readFile(join(webRoot, 'src/scene.ts'), 'utf8')
  const source = ts.createSourceFile('scene.ts', text, ts.ScriptTarget.Latest, true)
  const deformer = source.statements.find(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === 'createSpringDeformer')
  const curve = deformer?.body?.statements.find(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === 'curve')
  const classify = deformer?.body?.statements.find(statement => ts.isFunctionDeclaration(statement) && statement.name?.text === 'classify')
  if (!curve?.body || !classify?.body) throw new Error('Cannot derive native spring mathematics from scene.ts. No live outputs replaced.')
  const names = new Set(['counter', 'source', 'radius', 'wireRadius', 'turns', 'inset', 'endCorrection'])
  const declarations = deformer.body.statements.filter(statement => ts.isVariableStatement(statement)
    && statement.declarationList.declarations.every(declaration => ts.isIdentifier(declaration.name) && names.has(declaration.name.text)))
  // Run the actual renderer curve and its local shape expressions. No copied
  // spring constants, whole-renderer import, scene mutation or mesh allocation.
  const start = curve.body.statements.findIndex(statement => ts.isVariableStatement(statement)
    && statement.declarationList.declarations.some(declaration => declaration.name.getText(source) === 'shift'))
  const end = curve.body.statements.findIndex(statement => ts.isVariableStatement(statement)
    && statement.declarationList.declarations.some(declaration => declaration.name.getText(source) === 'u'))
  if (start < 0 || end <= start) throw new Error('Cannot derive the native spring transition from scene.ts. No live outputs replaced.')
  const moduleText = `export function springMath(THREE, MECHANISM_DATA, restLengthM, stock) {
    ${declarations.map(statement => statement.getText(source)).join('\n')}
    ${curve.getText(source)}
    function transition(span) {
      ${curve.body.statements.slice(start, end).map(statement => statement.getText(source)).join('\n')}
      return { polar, tangentMm: 3000 * Math.hypot(bx - x2, y2, radius - z2) };
    }
    return { curve, transition, radius, wireRadius, turns, inset, endCorrection,
      hookEyeX: side => ${variableInitializer(classify.body, 'eyeX').getText(source)} };
  }`
  const compiled = ts.transpileModule(moduleText, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  return (await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)).springMath
}

async function assertSpringCompatibility(staged, webRoot) {
  const springMath = await runtimeSpringMath(webRoot)
  const point = new THREE.Vector3(), direction = new THREE.Vector3(), start = new THREE.Vector3()
  for (const [key, stock] of [['spring', 'channel'], ['counter', 'counter']]) {
    const source = staged[key], shape = source?.deformation, parameter = `${key}.deformation`
    const runtime = springMath(THREE, staged, source?.freeLengthMm / 1000, stock)
    equalNumber(`${parameter}.coilEndInsetMm`, shape?.coilEndInsetMm, runtime.inset * 1000)
    equalNumber(`${parameter}.coilEndCorrectionMm`, shape?.coilEndCorrectionMm, runtime.endCorrection * 1000)
    equalNumber(`${parameter}.coilMeanRadiusMm`, shape?.coilMeanRadiusMm, runtime.radius * 1000)
    equalNumber(`${parameter}.wireRadiusMm`, shape?.wireRadiusMm, runtime.wireRadius * 1000)
    if (stock === 'counter') {
      arrayLength(`${parameter}.coilAxis`, shape.coilAxis, 3)
      // One complete winding cancels the radial coordinates and exposes the
      // actual renderer's coil axis without a second fixed-axis constant.
      runtime.curve(0, 0, source.freeLengthMm / 1000, start, direction)
      runtime.curve(0, 1 / runtime.turns, source.freeLengthMm / 1000, point, direction)
      point.sub(start).normalize()
      for (let axis = 0; axis < 3; axis++) equalNumber(`${parameter}.coilAxis[${axis}]`, shape.coilAxis[axis], point.getComponent(axis))
    } else {
      const transition = runtime.transition(source.freeLengthMm / 1000)
      equalNumber(`${parameter}.transitionHandlePolarRad`, shape.transitionHandlePolarRad, transition.polar)
      equalNumber(`${parameter}.transitionTangentMm`, shape.transitionTangentMm, transition.tangentMm)
    }
    arrayLength(`${parameter}.profiles`, shape.profiles, 2)
    for (const [index, profile] of shape.profiles.entries()) {
      const path = `${parameter}.profiles[${index}]`
      equalNumber(`${path}.lengthMm`, profile.lengthMm, index === 0 ? source.freeLengthMm : source.maximumLengthMm)
      const span = profile.lengthMm / 1000
      arrayLength(`${path}.coilEndsMm`, profile.coilEndsMm, 2)
      for (const t of [0, 1]) {
        runtime.curve(0, t, span, point, direction)
        equalNumber(`${path}.coilEndsMm[${t}]`, profile.coilEndsMm[t], point.x * 1000)
      }
      if (stock === 'counter') continue // All non-coil end assemblies stay rigid.
      const hook = springMath(THREE, staged, span, stock)
      arrayLength(`${path}.hookEyeCentresMm`, profile.hookEyeCentresMm, 2)
      for (const [sideIndex, side] of [-1, 1].entries()) {
        arrayLength(`${path}.hookEyeCentresMm[${sideIndex}]`, profile.hookEyeCentresMm[sideIndex], 3)
        for (let axis = 0; axis < 3; axis++) equalNumber(`${path}.hookEyeCentresMm[${sideIndex}][${axis}]`, profile.hookEyeCentresMm[sideIndex][axis], axis === 0 ? hook.hookEyeX(side) * 1000 : 0)
      }
      const control = profile.transitionControlPointsMm
      arrayLength(`${path}.transitionControlPointsMm`, control, 4)
      for (const [controlIndex, coordinates] of control.entries()) arrayLength(`${path}.transitionControlPointsMm[${controlIndex}]`, coordinates, 3)
      for (const t of [0, 0.25, 0.5, 0.75, 1]) {
        runtime.curve(-1, t, span, point, direction)
        const u = 1 - t, weights = [u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3]
        for (let axis = 0; axis < 3; axis++) {
          const actual = weights.reduce((sum, weight, controlIndex) => sum + weight * control[controlIndex][axis], 0)
          // The vendor's free-length B2 has a tiny radial solver residue; the
          // renderer follows the analytic helix tangent. Preserve its native
          // recipe's 1e-6 mm positional agreement only for free interior points.
          const tolerance = index === 0 && t > 0 && t < 1 ? 1e-6 : undefined
          equalNumber(`${path}.transitionControlPointsMm (t=${t})[${axis}]`, actual, point.getComponent(axis) * 1000, tolerance)
        }
      }
    }
  }
}

/**
 * Only assumptions still compiled into the solver/renderer are gated. Geometry,
 * rest poses, spring/catalog data and output-wheel dimensions remain exporter-
 * controlled except for the renderer's fixed spring coil/transition classifier.
 * Expected mathematics comes from the actual runtime, not copied constants.
 * The native source supplies the individual paper stages that kinematics.ts
 * compiles into one feed constant.
 */
export async function assertRuntimeMathCompatibility(staged, current, webRoot) {
  const kinematicsText = await readFile(join(webRoot, 'src/kinematics.ts'), 'utf8')
  const compiled = ts.transpileModule(kinematicsText, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  const runtime = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
  equalNumber('channel.count', staged.channel?.count, runtime.CHANNELS)
  arrayLength('harmonicNumbers', staged.harmonicNumbers, runtime.CHANNELS)
  arrayLength('driveTrain.channelMeshes', staged.driveTrain?.channelMeshes, runtime.CHANNELS)
  arrayLength('driveTrain.crankRatio', staged.driveTrain?.crankRatio, 2)
  const crankRatio = staged.driveTrain.crankRatio[0] / staged.driveTrain.crankRatio[1]
  equalNumber('driveTrain.crankRatio', crankRatio, -runtime.coneShaftAngle(1) / (2 * Math.PI))
  arrayLength('driveTrain.crankTeeth', staged.driveTrain.crankTeeth, 2)
  equalNumber('driveTrain.crankTeeth', staged.driveTrain.crankTeeth[0] / staged.driveTrain.crankTeeth[1], crankRatio)
  for (let index = 0; index < runtime.CHANNELS; index++) {
    const mesh = staged.driveTrain.channelMeshes[index]
    const expectedRatio = runtime.physicalChannelAngle(1, index) / -runtime.coneShaftAngle(1)
    equalNumber(`harmonicNumbers[${index}]`, staged.harmonicNumbers[index], runtime.physicalChannelAngle(1, index) / runtime.fourierArgument(1))
    equalNumber(`driveTrain.channelMeshes[${index}].coneTeeth/cylinderTeeth`, mesh?.coneTeeth / staged.driveTrain.cylinderTeeth, expectedRatio)
    equalNumber(`driveTrain.channelMeshes[${index}].cylinderTeeth`, mesh?.cylinderTeeth, staged.driveTrain.cylinderTeeth)
    arrayLength(`driveTrain.channelMeshes[${index}].ratio`, mesh?.ratio, 2)
    equalNumber(`driveTrain.channelMeshes[${index}].ratio`, mesh.ratio[0] / mesh.ratio[1], expectedRatio)
  }

  const paper = staged.paperDrive
  for (const parameter of ['chainRatioFine', 'reducerRatio', 'feedPitchDiameterMm', 'chainSense', 'externalMeshSense', 'rackFeedSense', 'netTravelSense']) {
    equalNumber(`paperDrive.${parameter}`, paper?.[parameter], current.paperDrive?.[parameter])
  }
  const fineTravel = paper.chainRatioFine * paper.reducerRatio * Math.PI * paper.feedPitchDiameterMm
  equalNumber('paperDrive.fineTravelMmPerCrankRev', paper.fineTravelMmPerCrankRev, fineTravel)
  equalNumber('paperDrive.netTravelSense', paper.netTravelSense, paper.chainSense * paper.externalMeshSense * paper.rackFeedSense)
  for (const [gearing, multiplier] of Object.entries(runtime.PAPER_FEED_MULTIPLIER)) {
    const ratio = gearing === 'small-large' ? paper.chainRatioFine : gearing === 'medium-medium' ? 1 : 1 / paper.chainRatioFine
    equalNumber(`paperDrive.chainRatioFine (${gearing})`, ratio / paper.chainRatioFine, multiplier)
    equalNumber(`paperDrive signed feed (${gearing})`, paper.netTravelSense * fineTravel * multiplier / 1000, runtime.paperTravelM(1, gearing))
  }

  arrayLength('magnifier.clampRadiusBandMm', staged.magnifier?.clampRadiusBandMm, 3)
  const bounds = [runtime.MAGNIFIER_RATIO_MIN, runtime.MAGNIFIER_RATIO_BUILT, runtime.MAGNIFIER_RATIO_MAX]
  for (let index = 0; index < bounds.length; index++) {
    equalNumber(`magnifier.clampRadiusBandMm[${index}]/summing.anchorArmMm`, staged.magnifier.clampRadiusBandMm[index] / staged.summing?.anchorArmMm, bounds[index])
  }
  const magnifierText = await readFile(join(webRoot, 'src/magnifier.ts'), 'utf8')
  const source = ts.createSourceFile('magnifier.ts', magnifierText, ts.ScriptTarget.Latest, true)
  arrayLength('magnifier.penRestMm', staged.magnifier.penRestMm, 3)
  for (const [index, name] of ['PEN_X', 'PEN_Y', 'PEN_Z'].entries()) {
    // Native GLB translations carry the same 0.002 mm rest-frame tolerance as
    // export-mechanics.py; this is not a tolerance on ratios or decoded geometry.
    equalNumber(`magnifier.penRestMm[${index}] (${name})`, staged.magnifier.penRestMm[index] / 1000, numericConstant(source, name), 0.002 / 1000)
  }

  await assertSpringCompatibility(staged, webRoot)
}

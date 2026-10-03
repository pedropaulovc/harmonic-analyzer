import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import ts from 'typescript'

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

/**
 * Only assumptions still compiled into the solver/renderer are gated. Geometry,
 * rest poses, spring/catalog data, output-wheel dimensions and provenance remain
 * exporter-controlled. The expected mathematics comes from the actual runtime,
 * not another copy of its constants. The current native source supplies the
 * individual paper stages that kinematics.ts compiles into one feed constant.
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
}

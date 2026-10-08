const text = value => typeof value === 'string' && Boolean(value.trim())
const closed = (value, fields) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field))
const same = (a, b) => {
  if (a === b) return true
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false
  const keys = Object.keys(a)
  return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) && same(a[key], b[key]))
}

/** This original donor has no possible independent tracker proof, regardless of seed lookup. */
export function sourceIntrinsicTemplateIssue(point) {
  return point?.method === 'template-match' && !Object.hasOwn(point, 'trackingEvidence')
    ? { code: 'template-provenance', reason: 'Independent manual seed and actual source-view/source-feature reacquisition correlations must be retained' }
    : null
}

/** Manual source qualification is not a native-pose measurement or fidelity approval. */
export function sourceVisibilityError(frame, view) {
  if (!Object.hasOwn(view, 'sourceVisibility')) return null
  const qualification = view.sourceVisibility
  if (!closed(qualification, ['kind', 'reasonCode', 'sourceImage', 'rectSourcePixels', 'manualSourceAudit'])
    || qualification.kind !== 'policy-excluded'
    || !['blurred-navigation-background', 'text-covered-navigation-background', 'unreadable-near-black-fade'].includes(qualification.reasonCode)
    || !closed(qualification.manualSourceAudit, ['method', 'evidence'])
    || qualification.manualSourceAudit.method !== 'manual-source-pixel-inspection'
    || !text(qualification.manualSourceAudit.evidence)) return 'Source visibility needs a closed approved unreadable-ROI reason and actual manual full-ROI source audit'
  const image = frame.sourceImage
  const hashField = image?.pixelFormat === 'gray8' ? 'sha256Gray8' : image?.pixelFormat === 'bgr8' ? 'sha256Bgr8' : null
  if (!hashField || !closed(image, ['frameIndex', 'pixelFormat', 'width', 'height', 'sourceSha256', hashField])
    || !Number.isSafeInteger(image.frameIndex) || image.frameIndex < 0 || image.width !== 1920 || image.height !== 1080
    || typeof image.sourceSha256 !== 'string' || typeof image[hashField] !== 'string'
    || !/^[0-9a-f]{64}$/.test(image.sourceSha256) || !/^[0-9a-f]{64}$/.test(image[hashField])
    || !same(qualification.sourceImage, image)) return 'Source visibility audit must bind the exact actual frame source image'
  const rect = view.rectSourcePixels
  if (!Array.isArray(rect) || rect.length !== 4
    || !Number.isFinite(rect[0]) || !Number.isFinite(rect[1]) || !Number.isFinite(rect[2]) || !Number.isFinite(rect[3])
    || rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0
    || rect[0] + rect[2] > image.width || rect[1] + rect[3] > image.height
    || !same(qualification.rectSourcePixels, rect)) return 'Source visibility audit must cover the exact complete physical source ROI'
  if (view.nativeLineChecks?.length || (frame.landmarks ?? []).some(point => (point.viewId ?? 'main') === view.id
    && (!sourceIntrinsicTemplateIssue(point) || !text(point.anchorId) || point.status !== 'observed'
      || !['fit', 'check'].includes(point.role) || !Array.isArray(point.pixel) || point.pixel.length !== 2
      || !Number.isFinite(point.pixel[0]) || !Number.isFinite(point.pixel[1])
      || point.pixel[0] < rect[0] || point.pixel[0] >= rect[0] + rect[2]
      || point.pixel[1] < rect[1] || point.pixel[1] >= rect[1] + rect[3]
      || !Number.isFinite(point.uncertaintyPx) || point.uncertaintyPx < 0
      || point.measurementEvidence && typeof point.measurementEvidence === 'object'
        && (Object.hasOwn(point.measurementEvidence, 'sourceImage') && !same(point.measurementEvidence.sourceImage, image)
          || Object.hasOwn(point.measurementEvidence, 'sourceSha256Bgr8') && point.measurementEvidence.sourceSha256Bgr8 !== image.sha256Bgr8
          || Object.hasOwn(point.measurementEvidence, 'sourceSha256Gray8') && point.measurementEvidence.sourceSha256Gray8 !== image.sha256Gray8))))
    return 'A source-readable or malformed landmark or line cannot be hidden by a visibility exclusion'
  return null
}

export function policyExcludedSourceView(frame, view) {
  return Object.hasOwn(view, 'sourceVisibility') && sourceVisibilityError(frame, view) === null
}

/** Explicit physical views cannot be waived by navigation/classification labels. */
export function physicalSourceFrameRequired(frame, otherwiseRequired = false) {
  return otherwiseRequired || Object.hasOwn(frame, 'views')
    && (!Array.isArray(frame.views) || frame.views.length > 0)
}

const validRect = rect => Array.isArray(rect) && rect.length === 4 && rect.every(Number.isFinite)
  && rect[0] >= 0 && rect[1] >= 0 && rect[2] > 0 && rect[3] > 0
  && rect[0] + rect[2] <= 1920 && rect[1] + rect[3] <= 1080
const validComposite = composite => composite == null
  || closed(composite, ['mode']) && composite.mode === 'opaque'
  || closed(composite, ['mode', 'groupId', 'imageLayerId', 'opacity']) && composite.mode === 'crossfade'
    && text(composite.groupId) && text(composite.imageLayerId) && Number.isFinite(composite.opacity)
    && composite.opacity >= 0 && composite.opacity <= 1
const hasWarp = view => view.imagePlaneWarp != null || view.resolvedImagePlaneWarp != null || view.imagePlaneWarpMeasurement != null

/** Exactly zero in the existing valid crossfade contract contributes no source pixels. */
export function zeroOpacitySourceView(view) {
  return validRect(view.rectSourcePixels) && validComposite(view.composite)
    && view.composite?.mode === 'crossfade' && view.composite.opacity === 0
}

/** Ordinary exact ordered opaque rectangle coverage only, never a readability policy exception. */
export function fullyCoveringSourceView(frame, view) {
  const views = frame.views, index = views?.indexOf(view) ?? -1
  if (index < 0 || !validRect(view.rectSourcePixels) || !validComposite(view.composite) || hasWarp(view)) return null
  const own = view.rectSourcePixels, a = view.composite
  for (let laterIndex = index + 1; laterIndex < views.length; laterIndex++) {
    const later = views[laterIndex], b = later.composite, rect = later.rectSourcePixels
    if (!validRect(rect) || !validComposite(b) || hasWarp(later)
      || b?.mode === 'crossfade' && (b.opacity !== 1
        || a?.mode === 'crossfade' && a.groupId === b.groupId && a.imageLayerId !== b.imageLayerId)) continue
    if (rect[0] <= own[0] && rect[1] <= own[1]
      && rect[0] + rect[2] >= own[0] + own[2] && rect[1] + rect[3] >= own[1] + own[3]) return later
  }
  return null
}

/** Invalid qualifications remain required; record/runtime validators reject them separately. */
export function requiredSourceViews(frame) {
  return (frame?.views ?? []).filter(view => !policyExcludedSourceView(frame, view)
    && !zeroOpacitySourceView(view) && !fullyCoveringSourceView(frame, view))
}

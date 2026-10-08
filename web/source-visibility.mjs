const text = value => typeof value === 'string' && Boolean(value.trim())
const closed = (value, fields) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field))
const same = (a, b) => {
  if (a === b) return true
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false
  const keys = Object.keys(a)
  return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) && same(a[key], b[key]))
}

/** Manual source qualification is not a native-pose measurement or fidelity approval. */
export function sourceVisibilityError(frame, view) {
  if (!Object.hasOwn(view, 'sourceVisibility')) return null
  const qualification = view.sourceVisibility
  if (!closed(qualification, ['kind', 'reasonCode', 'sourceImage', 'rectSourcePixels', 'manualSourceAudit'])
    || qualification.kind !== 'policy-excluded'
    || !['blurred-navigation-background', 'text-covered-navigation-background'].includes(qualification.reasonCode)
    || !closed(qualification.manualSourceAudit, ['method', 'evidence'])
    || qualification.manualSourceAudit.method !== 'manual-source-pixel-inspection'
    || !text(qualification.manualSourceAudit.evidence)) return 'Source visibility needs a closed navigation-background reason and actual manual full-ROI source audit'
  const image = frame.sourceImage
  const hashField = image?.pixelFormat === 'gray8' ? 'sha256Gray8' : image?.pixelFormat === 'bgr8' ? 'sha256Bgr8' : null
  if (!hashField || !closed(image, ['frameIndex', 'pixelFormat', 'width', 'height', 'sourceSha256', hashField])
    || !Number.isSafeInteger(image.frameIndex) || image.frameIndex < 0 || image.width !== 1920 || image.height !== 1080
    || !/^[0-9a-f]{64}$/.test(image.sourceSha256) || !/^[0-9a-f]{64}$/.test(image[hashField])
    || !same(qualification.sourceImage, image)) return 'Source visibility audit must bind the exact actual frame source image'
  const rect = view.rectSourcePixels
  if (!Array.isArray(rect) || rect.length !== 4 || !rect.every(Number.isFinite)
    || rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0
    || rect[0] + rect[2] > image.width || rect[1] + rect[3] > image.height
    || !same(qualification.rectSourcePixels, rect)) return 'Source visibility audit must cover the exact complete physical source ROI'
  if ((frame.landmarks ?? []).some(point => (point.viewId ?? 'main') === view.id)
    || view.nativeLineChecks?.length) return 'A source-readable landmark or line cannot be hidden by a background visibility exclusion'
  return null
}

export function policyExcludedSourceView(frame, view) {
  return Object.hasOwn(view, 'sourceVisibility') && sourceVisibilityError(frame, view) === null
}

/** Invalid qualifications remain required; record/runtime validators reject them separately. */
export function requiredSourceViews(frame) {
  return (frame.views ?? []).filter(view => !policyExcludedSourceView(frame, view))
}

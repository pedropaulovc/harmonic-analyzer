import type { SourceImageIdentity } from './src/source-witness'

export interface SourceVisibilityQualification {
  kind: 'policy-excluded'
  reasonCode: 'blurred-navigation-background' | 'text-covered-navigation-background' | 'unreadable-near-black-fade'
  sourceImage: SourceImageIdentity
  rectSourcePixels: [number, number, number, number]
  manualSourceAudit: { method: 'manual-source-pixel-inspection'; evidence: string }
}
interface VisibilityView {
  id: string
  rectSourcePixels: [number, number, number, number]
  sourceVisibility?: SourceVisibilityQualification
  nativeLineChecks?: readonly unknown[]
}
interface VisibilityFrame<T extends VisibilityView> {
  sourceImage?: SourceImageIdentity
  views?: T[]
  landmarks?: readonly { viewId?: string }[]
}
export function sourceIntrinsicTemplateIssue(point: { method?: unknown; trackingEvidence?: unknown }): { code: 'template-provenance'; reason: string } | null
export function sourceVisibilityError<T extends VisibilityView>(frame: VisibilityFrame<T>, view: T): string | null
export function policyExcludedSourceView<T extends VisibilityView>(frame: VisibilityFrame<T>, view: T): boolean
export function requiredSourceViews<T extends VisibilityView>(frame: VisibilityFrame<T>): T[]

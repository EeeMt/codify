/**
 * The guide's reading tiers. A chapter declares one in its front matter, and a
 * heading may override it for a single section, so a must-read section can sit
 * inside a deep-dive chapter and a deep section inside a practical one.
 */
export type GuideTier = 'core' | 'deep' | 'tips'

/** Display order, and the order the sidebar groups them in. */
export const GUIDE_TIERS: readonly GuideTier[] = ['core', 'deep', 'tips']

/** Narrowing guard for the two places a tier arrives as untrusted text. */
export function isGuideTier(value: unknown): value is GuideTier {
  return typeof value === 'string' && (GUIDE_TIERS as readonly string[]).includes(value)
}

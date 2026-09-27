// Static policy summary derived from SUPPORT_POLICY.pdf. Falls back to ''
// for any branch name the policy doesn't cover.
export const SUPPORT_STATUS: Record<string, string> = {
  main: 'active',
  'release/2.x': 'maintenance · until 2027-06-30',
  'release/1.x': 'security-only · until 2026-12-31',
  'release/0.9': 'end-of-life · since 2026-03-31',
};

export function supportStatusFor(branch: string): string {
  return SUPPORT_STATUS[branch] ?? '';
}

export function isEndOfLife(branch: string): boolean {
  return supportStatusFor(branch).startsWith('end-of-life');
}

// Plain-language version of the same policy, for first-time visitors. The
// precise dates still live in supportStatusFor() and surface as a tooltip.
export const PLAIN_STATUS: Record<string, string> = {
  main: 'newest version',
  'release/2.x': 'older · fully supported',
  'release/1.x': 'older · security fixes only',
  'release/0.9': 'retired · no fixes',
};

export function plainStatusFor(branch: string): string {
  return PLAIN_STATUS[branch] ?? '';
}

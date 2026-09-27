import type { CellTestRow } from './model';

export function verdictTone(verdict: CellTestRow['verdict']): 'proven' | 'review' | 'muted' {
  if (verdict === 'proves') return 'proven';
  if (verdict === 'already_passing') return 'review';
  return 'muted';
}

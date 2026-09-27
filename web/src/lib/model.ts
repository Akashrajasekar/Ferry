import planRaw from '../data/plan.json';
import resultsRaw from '../data/results.json';
import auditRaw from '../data/audit.json';
import tryRaw from '../data/try.json';
import metricsRaw from '../data/metrics.json';
import type { PlanFile, PlanCitation } from '../types/plan';
import type { ResultFlag, ResultTest, ResultsFile } from '../types/results';
import type { AuditFile } from '../types/audit';
import type { TryFile } from '../types/try';
import type { PortFile } from '../types/port';
import type { MetricsFile } from '../types/metrics';
import { supportStatusFor, isEndOfLife } from '../content';

const plan = planRaw as PlanFile;
const results = resultsRaw as ResultsFile;
const audit = auditRaw as AuditFile;
const tryLog = tryRaw as TryFile;
const metrics = metricsRaw as MetricsFile;

const portModules = import.meta.glob('../data/ports/*.json', { eager: true }) as Record<
  string,
  { default: PortFile }
>;

const DASH = '—';

export type FixKind = 'security' | 'feature fix' | 'bug fix';

export interface Fix {
  letter: string;
  sha: string;
  shortSha: string;
  subject: string;
  kind: FixKind;
}

export type CellStatusKind = 'adapted_proven' | 'clean_proven' | 'escalated' | 'pending' | 'skip' | 'na';

export interface DisplayFlag {
  title: string;
  body: string;
}

export interface CellTestRow {
  id: string;
  before: 'fails' | 'passes';
  after: 'fails' | 'passes';
  verdict: 'proves' | 'already_passing' | 'guards' | 'other';
  verdictLabel: string;
}

export interface Cell {
  key: string;
  fixLetter: string;
  fixSha: string;
  shortSha: string;
  subject: string;
  branch: string;
  statusKind: CellStatusKind;
  statusLabel: string;
  reviewRequired: boolean;
  reason: string;
  citationText: string;
  flags: DisplayFlag[];
  adaptations: string[];
  attempts: number | null;
  tests: CellTestRow[];
  fixDiff: string | undefined;
  backportDiff: string | undefined;
  hasProof: boolean;
}

export interface Metrics {
  fixesAudited: number;
  missingSecurityFixes: number;
  decisions: number;
  citations: number;
  portsProven: number;
  portsAttempted: number;
  cleanCount: number;
  adaptedCount: number;
  escalatedCount: number;
  reviewFlags: number;
  bobcoinsTotal: number | null;
  bobcoinsPerAdaptedPort: number | null;
  manualBaselineMinutes: number | null;
  ferryRunMinutes: number | null;
  ferryPerPortMinutes: number | null;
  ferrySpeedupPerPort: number | null;
  conflictedPorts: number;
}

export interface PipelineStep {
  id: 'audit' | 'scope' | 'try' | 'adapt' | 'verify' | 'report';
  result: string;
}

export type AuditOutcomeTone =
  | 'proven'
  | 'bob'
  | 'skip'
  | 'na'
  | 'backported'
  | 'present'
  | 'detected'
  | 'missing';

export interface AuditOutcome {
  label: string;
  tone: AuditOutcomeTone;
  cellKey?: string;
  tooltip?: string;
}

export interface AuditRow {
  shortSha: string;
  subject: string;
  kind: FixKind;
  outcomes: Record<string, AuditOutcome>;
}

export interface ViewModel {
  fixes: Fix[];
  branches: string[];
  cells: Cell[];
  cellsByKey: Map<string, Cell>;
  metrics: Metrics;
  pipeline: PipelineStep[];
  auditRows: AuditRow[];
  defaultCellKey: string | null;
}

function shortSha(sha: string): string {
  return sha.slice(0, 7);
}

function sanitizeBranch(branch: string): string {
  return branch.replace(/\//g, '-');
}

function letterFor(index: number): string {
  return String.fromCharCode(65 + index);
}

function classifyKind(category: string | undefined, subject: string): FixKind {
  if (category === 'security' || /^fix\(security\)/i.test(subject)) return 'security';
  if (category === 'feature-fix') return 'feature fix';
  return 'bug fix';
}

function branchSortKey(branch: string): number {
  const m = branch.match(/(\d+)\.(\d+|x)/);
  if (!m) return Number.POSITIVE_INFINITY;
  const major = parseInt(m[1], 10);
  const minor = m[2] === 'x' ? 0 : parseInt(m[2], 10);
  return major * 1000 + minor;
}

function citationText(citation: PlanCitation | undefined): string {
  if (!citation?.doc) return '';
  return citation.section ? `${citation.doc} ${citation.section}` : citation.doc;
}

function humaniseFlagKind(kind: string): string {
  const words = kind.replace(/_/g, ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function displayFlag(flag: ResultFlag): DisplayFlag {
  if (flag.kind === 'existing_test_modified') {
    const fns = (flag.functions ?? []).join(', ') || 'a regression test';
    return {
      title: 'Behaviour change: sign-off requested',
      body: `This fix changes tested behaviour on this branch, so ${fns} was updated. Routed to a release manager for sign-off.`,
    };
  }
  if (flag.kind === 'test_passes_without_fix') {
    const tests = (flag.tests ?? []).join(', ') || 'A test';
    return {
      title: 'Precision check: already-passing test',
      body: `${tests} already passes on this branch without the fix, so the proof for this port comes from its other regression tests. Flagged for a quick review.`,
    };
  }
  const details = [flag.reason, flag.file, ...(flag.functions ?? []), ...(flag.tests ?? [])]
    .filter((v): v is string => Boolean(v))
    .join(' — ');
  return {
    title: humaniseFlagKind(flag.kind),
    body: details || 'Flagged for review.',
  };
}

function testVerdict(
  test: ResultTest,
  alreadyPassingIds: Set<string>,
): { verdict: CellTestRow['verdict']; label: string } {
  if (alreadyPassingIds.has(test.id) || test.kind === 'test_passes_without_fix') {
    return { verdict: 'already_passing', label: 'already passing' };
  }
  if (test.kind === 'preserves_behaviour') {
    return { verdict: 'guards', label: 'guards behaviour' };
  }
  if (test.failed_before && test.passed_after) {
    return { verdict: 'proves', label: 'proves the fix' };
  }
  return { verdict: 'other', label: 'not proven' };
}

function statusFromMethod(
  method: string | undefined,
  f2p: boolean | undefined,
  p2p: boolean | undefined,
): { kind: CellStatusKind; label: string } {
  const proven = Boolean(f2p) && Boolean(p2p);
  switch (method) {
    case 'adapted':
      return proven
        ? { kind: 'adapted_proven', label: 'adapted + proven' }
        : { kind: 'escalated', label: 'escalated' };
    case 'clean':
      return proven
        ? { kind: 'clean_proven', label: 'clean + proven' }
        : { kind: 'escalated', label: 'escalated' };
    case 'escalated':
      return { kind: 'escalated', label: 'escalated' };
    case 'pending':
      return { kind: 'pending', label: 'pending' };
    case 'skip':
      return { kind: 'skip', label: 'skip' };
    case 'not_applicable':
      return { kind: 'na', label: 'n/a' };
    default:
      return { kind: 'pending', label: 'pending' };
  }
}

function statusFromDecision(decision: string | undefined): { kind: CellStatusKind; label: string } {
  switch (decision) {
    case 'skip':
      return { kind: 'skip', label: 'skip' };
    case 'not_applicable':
      return { kind: 'na', label: 'n/a' };
    default:
      return { kind: 'pending', label: 'pending' };
  }
}

function findPort(shaVal: string, branch: string): PortFile | null {
  const key = `${shortSha(shaVal)}__${sanitizeBranch(branch)}`;
  for (const path in portModules) {
    if (path.endsWith(`/${key}.json`)) {
      return portModules[path].default;
    }
  }
  return null;
}

function buildFixes(): Fix[] {
  return plan.fixes.map((f, i) => ({
    letter: letterFor(i),
    sha: f.sha,
    shortSha: shortSha(f.sha),
    subject: f.subject,
    kind: classifyKind(f.category, f.subject),
  }));
}

function buildBranches(): string[] {
  const set = new Set<string>();
  for (const fix of plan.fixes) {
    for (const target of fix.targets) set.add(target.branch);
  }
  return [...set].sort((a, b) => branchSortKey(a) - branchSortKey(b));
}

function buildCells(fixes: Fix[]): Cell[] {
  const cells: Cell[] = [];
  for (const fix of fixes) {
    const planFix = plan.fixes.find((f) => f.sha === fix.sha);
    if (!planFix) continue;
    for (const target of planFix.targets) {
      const branch = target.branch;
      const resultEntry = results.find((r) => r.sha === fix.sha && r.branch === branch);
      const status = resultEntry
        ? statusFromMethod(resultEntry.method, resultEntry.f2p, resultEntry.p2p)
        : statusFromDecision(target.decision);

      const reason = resultEntry?.reason ?? target.reason ?? '';
      const cite = citationText(resultEntry?.citation ?? target.citation);
      const flags = (resultEntry?.flags ?? []).map(displayFlag);
      const alreadyPassingIds = new Set<string>(
        (resultEntry?.flags ?? [])
          .filter((f) => f.kind === 'test_passes_without_fix')
          .flatMap((f) => f.tests ?? []),
      );
      const port = findPort(fix.sha, branch);
      const tests: CellTestRow[] = (resultEntry?.tests ?? []).map((t) => {
        const v = testVerdict(t, alreadyPassingIds);
        return {
          id: t.id,
          before: t.failed_before ? 'fails' : 'passes',
          after: t.passed_after ? 'passes' : 'fails',
          verdict: v.verdict,
          verdictLabel: v.label,
        };
      });

      cells.push({
        key: `${fix.letter}-${sanitizeBranch(branch)}`,
        fixLetter: fix.letter,
        fixSha: fix.sha,
        shortSha: fix.shortSha,
        subject: fix.subject,
        branch,
        statusKind: status.kind,
        statusLabel: status.label,
        reviewRequired: Boolean(resultEntry?.review_required),
        reason,
        citationText: cite,
        flags,
        adaptations: port?.adaptations ?? [],
        attempts: port?.attempts ?? null,
        tests,
        fixDiff: resultEntry?.fix_diff,
        backportDiff: resultEntry?.backport_diff,
        hasProof: tests.length > 0,
      });
    }
  }
  return cells;
}

function buildMetrics(cells: Cell[]): Metrics {
  const decisions = plan.fixes.reduce((sum, f) => sum + f.targets.length, 0);
  const citations = plan.fixes.reduce(
    (sum, f) => sum + f.targets.filter((t) => t.citation?.doc).length,
    0,
  );

  const securityAuditEntries = audit.filter((a) => a.kind === 'security');
  const missingSecurityFixes = securityAuditEntries.filter((a) =>
    Object.values(a.branches).every((status) => status === 'missing'),
  ).length;

  const adaptedCells = cells.filter((c) => c.statusKind === 'adapted_proven');
  const cleanCells = cells.filter((c) => c.statusKind === 'clean_proven');
  const escalatedCells = cells.filter((c) => c.statusKind === 'escalated');
  const provenCount = adaptedCells.length + cleanCells.length;
  const attemptedCount = provenCount + escalatedCells.length;
  const reviewFlags = cells.reduce((sum, c) => sum + c.flags.length, 0);

  const bobcoinsByTask = metrics.bobcoins_by_task ?? {};
  const bobcoinsTotal = Object.values(bobcoinsByTask).length
    ? Object.values(bobcoinsByTask).reduce((a, b) => a + b, 0)
    : null;
  const t06 = bobcoinsByTask.T06;
  const bobcoinsPerAdaptedPort =
    typeof t06 === 'number' && adaptedCells.length > 0
      ? Math.round((t06 / adaptedCells.length) * 100) / 100
      : null;

  const conflictedPorts = tryLog.filter((t) => t.status === 'conflict').length;

  const manualBaselineMinutes = metrics.manual_baseline_minutes ?? null;
  const ferryRunMinutes = metrics.ferry_run_minutes ?? null;
  const ferryPerPortMinutesRaw =
    ferryRunMinutes !== null && conflictedPorts > 0 ? ferryRunMinutes / conflictedPorts : null;
  const ferryPerPortMinutes =
    ferryPerPortMinutesRaw !== null ? Math.round(ferryPerPortMinutesRaw * 10) / 10 : null;
  // Speedup is derived from the unrounded per-port time so it doesn't drift
  // from displaying the rounded 3.6 min/port figure (double-rounding would
  // give 4.6x here instead of the correct 4.5x).
  const ferrySpeedupPerPort =
    ferryPerPortMinutesRaw !== null && manualBaselineMinutes !== null && ferryPerPortMinutesRaw > 0
      ? Math.round((manualBaselineMinutes / ferryPerPortMinutesRaw) * 10) / 10
      : null;

  return {
    fixesAudited: audit.length,
    missingSecurityFixes,
    decisions,
    citations,
    portsProven: provenCount,
    portsAttempted: attemptedCount,
    cleanCount: cleanCells.length,
    adaptedCount: adaptedCells.length,
    escalatedCount: escalatedCells.length,
    reviewFlags,
    bobcoinsTotal,
    bobcoinsPerAdaptedPort,
    manualBaselineMinutes,
    ferryRunMinutes,
    ferryPerPortMinutes,
    ferrySpeedupPerPort,
    conflictedPorts,
  };
}

function buildPipeline(m: Metrics): PipelineStep[] {
  const tryClean = tryLog.filter((t) => t.status === 'clean_pass').length;
  const tryConflict = tryLog.filter((t) => t.status === 'conflict').length;
  const portedCount = Object.values(portModules).filter((mod) => mod.default.status === 'ported').length;

  return [
    { id: 'audit', result: `${m.fixesAudited} fixes · ${m.missingSecurityFixes} security gaps` },
    { id: 'scope', result: `${m.decisions} decisions · ${m.citations} citations` },
    { id: 'try', result: `${tryClean} clean · ${tryConflict} conflicts` },
    { id: 'adapt', result: `${m.conflictedPorts} subagents · ${portedCount} ported` },
    { id: 'verify', result: `${m.portsProven}/${m.portsAttempted} proven · ${m.reviewFlags} flags` },
    { id: 'report', result: 'matrix · diffs · changelogs' },
  ];
}

// Policy for a commit that was never scoped into a plan (not in plan.json):
// an end-of-life branch never receives fixes, a security-only branch only
// takes security fixes, and anything left over is a genuine audit finding
// still waiting on a scope + adapt pass. Returns null when neither policy
// rule excuses the branch, so the caller falls through to "detected".
function policyOutcomeForUnplanned(branch: string, kind: FixKind): AuditOutcome | null {
  if (isEndOfLife(branch)) {
    return { label: 'not required · end-of-life', tone: 'skip' };
  }
  if (supportStatusFor(branch).startsWith('security-only') && kind !== 'security') {
    return { label: 'not required · security-only', tone: 'skip' };
  }
  return null;
}

function computeOutcome(
  entry: AuditFile[number],
  branch: string,
  fixesBySha: Map<string, Fix>,
): AuditOutcome {
  const sha = entry.sha;
  const planFix = plan.fixes.find((f) => f.sha === sha);
  const inPlan = Boolean(planFix);
  const kind = classifyKind(entry.kind === 'security' ? 'security' : undefined, entry.subject);

  const resultEntry = results.find((r) => r.sha === sha && r.branch === branch);
  if (resultEntry?.f2p && resultEntry?.p2p) {
    const fix = fixesBySha.get(sha);
    const cellKey = fix ? cellKeyFor(fix.letter, branch) : undefined;
    if (resultEntry.method === 'clean') {
      return { label: 'clean port & proven · awaiting merge', tone: 'bob', cellKey };
    }
    return { label: 'ported & proven · awaiting merge', tone: 'proven', cellKey };
  }

  const target = planFix?.targets.find((t) => t.branch === branch);
  if (target?.decision === 'skip') {
    return {
      label: 'skipped by policy',
      tone: 'skip',
      tooltip: citationText(target.citation) || undefined,
    };
  }
  if (target?.decision === 'not_applicable') {
    return { label: 'not applicable', tone: 'na' };
  }

  const auditStatus = entry.branches[branch] ?? '';
  if (auditStatus.startsWith('backported:')) {
    return { label: `already backported · ${auditStatus.split(':')[1]}`, tone: 'backported' };
  }
  if (auditStatus === 'present') {
    return { label: 'present', tone: 'present' };
  }
  if (auditStatus === 'missing' && !inPlan) {
    const policyOutcome = policyOutcomeForUnplanned(branch, kind);
    if (policyOutcome) return policyOutcome;
    return {
      label: 'detected · ready for next run',
      tone: 'detected',
      tooltip: "Found by Ferry's audit. Run scope + adapt to port it.",
    };
  }
  return { label: 'missing', tone: 'missing' };
}

function buildAuditRows(fixes: Fix[], branches: string[]): AuditRow[] {
  const fixesBySha = new Map(fixes.map((f) => [f.sha, f]));
  return audit.map((entry) => ({
    shortSha: shortSha(entry.sha),
    subject: entry.subject,
    kind: classifyKind(entry.kind === 'security' ? 'security' : undefined, entry.subject),
    outcomes: Object.fromEntries(branches.map((b) => [b, computeOutcome(entry, b, fixesBySha)])),
  }));
}

function pickDefaultCellKey(cells: Cell[]): string | null {
  const adaptedWithReview = cells.find((c) => c.statusKind === 'adapted_proven' && c.reviewRequired);
  if (adaptedWithReview) return adaptedWithReview.key;
  const adapted = cells.find((c) => c.statusKind === 'adapted_proven');
  if (adapted) return adapted.key;
  return cells[0]?.key ?? null;
}

function build(): ViewModel {
  const fixes = buildFixes();
  const branches = buildBranches();
  const cells = buildCells(fixes);
  const cellMetrics = buildMetrics(cells);
  const pipeline = buildPipeline(cellMetrics);
  const auditRows = buildAuditRows(fixes, branches);
  const defaultCellKey = pickDefaultCellKey(cells);

  return {
    fixes,
    branches,
    cells,
    cellsByKey: new Map(cells.map((c) => [c.key, c])),
    metrics: cellMetrics,
    pipeline,
    auditRows,
    defaultCellKey,
  };
}

export const viewModel: ViewModel = build();

export function cellKeyFor(fixLetter: string, branch: string): string {
  return `${fixLetter}-${sanitizeBranch(branch)}`;
}

export function fmt(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) return DASH;
  return `${value}${suffix}`;
}

export function ratio(a: number | null | undefined, b: number | null | undefined): string {
  if (a === null || a === undefined || b === null || b === undefined) return DASH;
  return `${a}/${b}`;
}

export { supportStatusFor, isEndOfLife, DASH };

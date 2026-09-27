export interface ResultTest {
  id: string;
  failed_before?: boolean;
  passed_after?: boolean;
  proves_fix?: boolean;
  kind?: string;
}

export interface ResultFlag {
  kind: string;
  tests?: string[];
  reason?: string;
  file?: string;
  functions?: string[];
}

export interface ResultCitation {
  doc: string;
  section?: string;
}

export interface ResultSuite {
  passed?: number;
  failed?: number;
}

export interface ResultEntry {
  sha: string;
  branch: string;
  method: string;
  reason?: string;
  citation?: ResultCitation;
  f2p?: boolean;
  p2p?: boolean;
  fail_before?: boolean;
  fail_before_reason?: string;
  pass_after?: boolean;
  suite?: ResultSuite;
  tests?: ResultTest[];
  flags?: ResultFlag[];
  review_required?: boolean;
  seconds?: number;
  fix_diff?: string;
  backport_diff?: string;
}

export type ResultsFile = ResultEntry[];

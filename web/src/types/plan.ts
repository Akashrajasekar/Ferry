export interface PlanCitation {
  doc: string;
  section?: string;
}

export interface PlanTarget {
  branch: string;
  decision: string;
  reason?: string;
  citation?: PlanCitation;
}

export interface PlanFix {
  sha: string;
  subject: string;
  category?: string;
  targets: PlanTarget[];
}

export interface PlanFile {
  fixes: PlanFix[];
}

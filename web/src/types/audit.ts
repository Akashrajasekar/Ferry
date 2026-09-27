export interface AuditEntry {
  sha: string;
  subject: string;
  kind?: string;
  branches: Record<string, string>;
}

export type AuditFile = AuditEntry[];

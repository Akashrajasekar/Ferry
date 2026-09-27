export interface TryConflict {
  type?: string;
  file?: string;
}

export interface TryEntry {
  sha: string;
  branch: string;
  status: string;
  worktree?: string;
  backport_branch?: string;
  conflicts?: TryConflict[];
  seconds?: number;
}

export type TryFile = TryEntry[];

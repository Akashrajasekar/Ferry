export type DiffLineType = 'hunk' | 'add' | 'del' | 'context';

export interface DiffLine {
  type: DiffLineType;
  text: string;
}

export interface DiffFile {
  path: string;
  lines: DiffLine[];
}

// Parses a unified-diff string (as produced by `git show`/`git diff`) into
// file headers + hunk lines only. Commit metadata, `index` lines and the
// `---`/`+++` file markers are dropped since they add noise, not signal.
export function parseDiff(raw: string | undefined): DiffFile[] {
  if (!raw) return [];
  const files: DiffFile[] = [];
  let current: DiffFile | null = null;

  for (const line of raw.split('\n')) {
    if (line.startsWith('diff --git')) {
      const match = line.match(/^diff --git a\/(.+?) b\/(.+)$/);
      const path = match ? match[2] : line.replace(/^diff --git /, '');
      current = { path, lines: [] };
      files.push(current);
      continue;
    }
    if (!current) continue;
    if (line.startsWith('index ') || line.startsWith('--- ') || line.startsWith('+++ ')) continue;

    if (line.startsWith('@@')) {
      current.lines.push({ type: 'hunk', text: line });
    } else if (line.startsWith('+')) {
      current.lines.push({ type: 'add', text: line });
    } else if (line.startsWith('-')) {
      current.lines.push({ type: 'del', text: line });
    } else if (line.length > 0) {
      current.lines.push({ type: 'context', text: line });
    }
  }
  return files;
}

export function isTestFile(path: string): boolean {
  return /test/i.test(path);
}

// Code files first, test files after — stable sort preserves original order within each group.
export function sortCodeFirst(files: DiffFile[]): DiffFile[] {
  return [...files].sort((a, b) => Number(isTestFile(a.path)) - Number(isTestFile(b.path)));
}

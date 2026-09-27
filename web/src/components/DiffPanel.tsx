import { useMemo, useState } from 'react';
import styles from './DiffPanel.module.css';
import { parseDiff, sortCodeFirst, type DiffFile, type DiffLine } from '../lib/diff';

const COLLAPSE_THRESHOLD = 40;

interface Props {
  diff: string | undefined;
  emptyLabel: string;
  wrap?: boolean;
}

function lineClass(type: DiffLine['type']): string {
  switch (type) {
    case 'hunk':
      return styles.hunk;
    case 'add':
      return styles.add;
    case 'del':
      return styles.del;
    default:
      return styles.context;
  }
}

function FileBlock({ file, wrap }: { file: DiffFile; wrap: boolean }) {
  const lineCount = file.lines.length;
  const [expanded, setExpanded] = useState(lineCount <= COLLAPSE_THRESHOLD);

  return (
    <div className={styles.fileBlock}>
      <button
        type="button"
        className={styles.fileHeader}
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <span className={styles.fileHeaderPath}>{file.path}</span>
        <span className={styles.fileHeaderMeta}>
          {lineCount} lines <span aria-hidden="true">{expanded ? '−' : '+'}</span>
        </span>
      </button>
      {expanded && (
        <pre className={`${styles.code} ${wrap ? styles.wrap : ''}`}>
          {file.lines.map((line, i) => (
            <div key={i} className={`${styles.line} ${lineClass(line.type)}`}>
              {line.text}
            </div>
          ))}
        </pre>
      )}
      {!expanded && (
        <button type="button" className={styles.showAll} onClick={() => setExpanded(true)}>
          Show all {lineCount} lines
        </button>
      )}
    </div>
  );
}

export function DiffPanel({ diff, emptyLabel, wrap = false }: Props) {
  const files = useMemo(() => sortCodeFirst(parseDiff(diff)), [diff]);

  if (files.length === 0) {
    return (
      <div className={styles.panel}>
        <p className={styles.empty}>{emptyLabel}</p>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {files.map((file) => (
        <FileBlock key={file.path} file={file} wrap={wrap} />
      ))}
    </div>
  );
}

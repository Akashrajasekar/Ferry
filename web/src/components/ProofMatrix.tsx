import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './ProofMatrix.module.css';
import { DetailPanel } from './DetailPanel';
import type { ViewModel } from '../lib/model';
import { cellKeyFor } from '../lib/model';

interface Props {
  vm: ViewModel;
}

function hashForKey(key: string): string {
  return `cell-${key}`;
}

function keyFromHash(hash: string): string | null {
  const clean = hash.replace(/^#/, '');
  return clean.startsWith('cell-') ? clean.slice('cell-'.length) : null;
}

export function ProofMatrix({ vm }: Props) {
  const { fixes, branches, cellsByKey, defaultCellKey } = vm;
  const [selectedKey, setSelectedKey] = useState<string | null>(defaultCellKey);
  const tileRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const detailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const syncFromHash = () => {
      const key = keyFromHash(window.location.hash);
      if (key && cellsByKey.has(key)) setSelectedKey(key);
    };
    syncFromHash();
    window.addEventListener('hashchange', syncFromHash);
    return () => window.removeEventListener('hashchange', syncFromHash);
  }, [cellsByKey]);

  const selectCell = useCallback((key: string) => {
    setSelectedKey(key);
    window.history.replaceState(null, '', `#${hashForKey(key)}`);
    if (window.matchMedia('(max-width: 1023px)').matches) {
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      requestAnimationFrame(() => {
        detailRef.current?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      });
    }
  }, []);

  const handleArrowNav = (rowIdx: number, colIdx: number, dir: 'up' | 'down' | 'left' | 'right') => {
    let nextRow = rowIdx;
    let nextCol = colIdx;
    if (dir === 'up') nextRow = Math.max(0, rowIdx - 1);
    if (dir === 'down') nextRow = Math.min(fixes.length - 1, rowIdx + 1);
    if (dir === 'left') nextCol = Math.max(0, colIdx - 1);
    if (dir === 'right') nextCol = Math.min(branches.length - 1, colIdx + 1);

    const fix = fixes[nextRow];
    const branch = branches[nextCol];
    const key = cellKeyFor(fix.letter, branch);
    const el = tileRefs.current.get(key);
    el?.focus();
    selectCell(key);
  };

  const selectedCell = selectedKey ? cellsByKey.get(selectedKey) ?? null : null;
  const gridTemplateColumns = `minmax(220px, 2fr) repeat(${branches.length}, minmax(120px, 1fr))`;

  return (
    <section id="matrix" className={styles.section} aria-labelledby="matrix-heading">
      <div className="container">
        <div className={styles.header}>
          <p className={styles.eyebrow}>PROOF MATRIX</p>
          <h2 id="matrix-heading" className={styles.heading}>
            Click any cell. See why, what changed, and the proof.
          </h2>
        </div>

        <div className={styles.matrixScroll}>
          <div
            className={styles.matrixGrid}
            style={{ gridTemplateColumns }}
            role="table"
            aria-label="Proof matrix"
          >
            <div className={styles.gridRow} role="row">
              <div role="columnheader" className={`${styles.cell} ${styles.cornerCell}`}>
                Fix
              </div>
              {branches.map((branch) => (
                <div key={branch} role="columnheader" className={`${styles.cell} ${styles.branchHeaderCell}`}>
                  {branch}
                </div>
              ))}
            </div>

            {fixes.map((fix, rowIdx) => (
              <div className={styles.gridRow} role="row" key={fix.letter}>
                <div role="rowheader" className={`${styles.cell} ${styles.fixCell}`}>
                  <div className={styles.rowTop}>
                    <span className={styles.rowLetter}>{fix.letter}</span>
                    <span className={styles.rowSha}>{fix.shortSha}</span>
                    <span
                      className={`${styles.kindChip} ${fix.kind === 'security' ? styles.security : ''}`}
                    >
                      {fix.kind}
                    </span>
                  </div>
                  <p className={styles.rowSubject}>{fix.subject}</p>
                </div>

                {branches.map((branch, colIdx) => {
                  const key = cellKeyFor(fix.letter, branch);
                  const cell = cellsByKey.get(key);
                  if (!cell) return <div key={branch} role="cell" className={`${styles.cell} ${styles.tileCell}`} />;
                  const isSelected = selectedKey === key;
                  return (
                    <div key={branch} role="cell" className={`${styles.cell} ${styles.tileCell}`}>
                      <button
                        type="button"
                        ref={(el) => {
                          if (el) tileRefs.current.set(key, el);
                          else tileRefs.current.delete(key);
                        }}
                        className={`${styles.tile} ${styles[cell.statusKind]} ${
                          isSelected ? styles.selected : ''
                        }`}
                        aria-pressed={isSelected}
                        aria-label={`Fix ${fix.letter} on ${branch}: ${cell.statusLabel}${
                          cell.reviewRequired ? ', review requested' : ''
                        }`}
                        onClick={() => selectCell(key)}
                        onKeyDown={(e) => {
                          if (e.key === 'ArrowUp') {
                            e.preventDefault();
                            handleArrowNav(rowIdx, colIdx, 'up');
                          } else if (e.key === 'ArrowDown') {
                            e.preventDefault();
                            handleArrowNav(rowIdx, colIdx, 'down');
                          } else if (e.key === 'ArrowLeft') {
                            e.preventDefault();
                            handleArrowNav(rowIdx, colIdx, 'left');
                          } else if (e.key === 'ArrowRight') {
                            e.preventDefault();
                            handleArrowNav(rowIdx, colIdx, 'right');
                          }
                        }}
                      >
                        {cell.statusLabel}
                        {cell.reviewRequired && (
                          <span className={styles.reviewDot} aria-hidden="true" />
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        <div className={styles.legend}>
          <span className={styles.legendItem}>
            <span
              className={styles.legendSwatch}
              style={{ background: 'var(--proven-surface)', borderColor: 'var(--proven-border)' }}
            />
            adapted / clean + proven
          </span>
          <span className={styles.legendItem}>
            <span
              className={styles.legendSwatch}
              style={{ background: 'var(--review-surface)', borderColor: 'var(--review-border)' }}
            />
            escalated
          </span>
          <span className={styles.legendItem}>
            <span
              className={styles.legendSwatch}
              style={{ background: 'var(--skip-surface)', borderColor: 'var(--na-border)' }}
            />
            skip / n/a
          </span>
          <span className={styles.legendItem}>
            <span className={styles.reviewDot} style={{ position: 'static' }} />
            review requested
          </span>
        </div>

        <div ref={detailRef} className={styles.detailWrap}>
          {selectedCell && <DetailPanel cell={selectedCell} />}
        </div>
      </div>
    </section>
  );
}

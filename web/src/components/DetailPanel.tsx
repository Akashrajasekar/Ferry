import { useId, useRef, useState, type KeyboardEvent } from 'react';
import styles from './DetailPanel.module.css';
import { DiffPanel } from './DiffPanel';
import type { Cell } from '../lib/model';
import { verdictTone } from '../lib/testVerdictStyle';
import { useMediaQuery } from '../hooks/useMediaQuery';

interface Props {
  cell: Cell;
}

type TabId = 'why' | 'changed' | 'proof' | 'diff';

function verdictClass(verdict: Cell['tests'][number]['verdict']): string {
  const tone = verdictTone(verdict);
  if (tone === 'proven') return styles.verdictProven;
  if (tone === 'review') return styles.verdictReview;
  return styles.verdictMuted;
}

function testFunctionName(id: string): string {
  const parts = id.split('::');
  return parts[parts.length - 1] || id;
}

export function DetailPanel({ cell }: Props) {
  return (
    <div className={styles.panel}>
      <p className={styles.path}>
        Fix {cell.fixLetter} · {cell.shortSha} → {cell.branch}
      </p>
      <h3 className={styles.subject}>{cell.subject}</h3>

      <div className={styles.badgeRow}>
        <span className={`${styles.badge} ${styles[cell.statusKind]}`}>{cell.statusLabel}</span>
        {cell.reviewRequired && (
          <span className={styles.reviewBadge}>
            <svg width="8" height="8" aria-hidden="true">
              <circle cx="4" cy="4" r="4" fill="var(--review)" />
            </svg>
            review requested
          </span>
        )}
      </div>

      <DetailTabs key={cell.key} cell={cell} />
    </div>
  );
}

function DetailTabs({ cell }: { cell: Cell }) {
  const hasWhy = Boolean(cell.reason) || cell.flags.length > 0;
  const hasChanged = cell.adaptations.length > 0;
  const hasProof = cell.tests.length > 0;
  const hasDiff = Boolean(cell.fixDiff || cell.backportDiff);

  const tabs: { id: TabId; label: string }[] = [];
  if (hasWhy) tabs.push({ id: 'why', label: 'Why' });
  if (hasChanged) tabs.push({ id: 'changed', label: 'What changed' });
  if (hasProof) tabs.push({ id: 'proof', label: 'Proof' });
  if (hasDiff) tabs.push({ id: 'diff', label: 'Diff' });

  const [active, setActive] = useState<TabId | null>(tabs[0]?.id ?? null);
  const tabRefs = useRef<Map<TabId, HTMLButtonElement>>(new Map());
  const baseId = useId();

  if (tabs.length === 0 || active === null) return null;

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, idx: number) => {
    let nextIdx = idx;
    if (e.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') nextIdx = 0;
    else if (e.key === 'End') nextIdx = tabs.length - 1;
    else return;
    e.preventDefault();
    const nextId = tabs[nextIdx].id;
    setActive(nextId);
    tabRefs.current.get(nextId)?.focus();
  };

  return (
    <div className={styles.tabsWrap}>
      <div role="tablist" aria-label="Proof details" className={styles.tabList}>
        {tabs.map((tab, idx) => {
          const selected = tab.id === active;
          return (
            <button
              key={tab.id}
              ref={(el) => {
                if (el) tabRefs.current.set(tab.id, el);
                else tabRefs.current.delete(tab.id);
              }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              className={`${styles.tab} ${selected ? styles.tabSelected : ''}`}
              onClick={() => setActive(tab.id)}
              onKeyDown={(e) => onKeyDown(e, idx)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {tabs.map((tab) => {
        if (tab.id !== active) return null;
        return (
          <div
            key={tab.id}
            role="tabpanel"
            id={`${baseId}-panel-${tab.id}`}
            aria-labelledby={`${baseId}-tab-${tab.id}`}
            tabIndex={0}
            className={styles.tabPanel}
          >
            {tab.id === 'why' && <WhyTab cell={cell} />}
            {tab.id === 'changed' && <ChangedTab cell={cell} />}
            {tab.id === 'proof' && <ProofTab cell={cell} />}
            {tab.id === 'diff' && <DiffTab cell={cell} />}
          </div>
        );
      })}
    </div>
  );
}

function WhyTab({ cell }: { cell: Cell }) {
  return (
    <div>
      {cell.reason && (
        <div className={styles.whyBox}>
          <p className={styles.reasonText}>{cell.reason}</p>
          {cell.citationText && <p className={styles.citationText}>↳ {cell.citationText}</p>}
        </div>
      )}
      {cell.flags.map((flag, i) => (
        <div key={i} className={styles.flagBox}>
          <p className={styles.flagTitle}>{flag.title}</p>
          <p className={styles.flagBody}>{flag.body}</p>
        </div>
      ))}
    </div>
  );
}

const ADAPTATIONS_LIMIT = 4;

function ChangedTab({ cell }: { cell: Cell }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? cell.adaptations : cell.adaptations.slice(0, ADAPTATIONS_LIMIT);
  const attempts = cell.attempts ?? cell.adaptations.length;
  const remaining = cell.adaptations.length - ADAPTATIONS_LIMIT;

  return (
    <div>
      <p className={styles.tabIntro}>
        {attempts} attempt{attempts === 1 ? '' : 's'}
      </p>
      <ul className={styles.adaptList}>
        {visible.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
      {!showAll && remaining > 0 && (
        <button type="button" className={styles.showMoreBtn} onClick={() => setShowAll(true)}>
          Show {remaining} more
        </button>
      )}
    </div>
  );
}

function ProofTab({ cell }: { cell: Cell }) {
  return (
    <>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Test</th>
              <th scope="col">Before</th>
              <th scope="col">After</th>
              <th scope="col">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {cell.tests.map((t) => (
              <tr key={t.id}>
                <td className={styles.testId} title={t.id}>
                  {testFunctionName(t.id)}
                </td>
                <td>{t.before}</td>
                <td>{t.after}</td>
                <td className={verdictClass(t.verdict)}>{t.verdictLabel}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className={styles.testCards}>
        {cell.tests.map((t) => (
          <div key={t.id} className={styles.testCard} title={t.id}>
            <p className={styles.testCardName}>{testFunctionName(t.id)}</p>
            <div className={styles.testCardRow}>
              <span>Before</span>
              <span>{t.before}</span>
            </div>
            <div className={styles.testCardRow}>
              <span>After</span>
              <span>{t.after}</span>
            </div>
            <p className={verdictClass(t.verdict)}>{t.verdictLabel}</p>
          </div>
        ))}
      </div>
    </>
  );
}

function DiffTab({ cell }: { cell: Cell }) {
  const isWide = useMediaQuery('(min-width: 1100px)');
  const [modeOverride, setModeOverride] = useState<'side' | 'stacked' | null>(null);
  const mode = modeOverride ?? (isWide ? 'side' : 'stacked');
  const wrap = mode === 'stacked';

  return (
    <div>
      <div className={styles.diffToggle} role="group" aria-label="Diff layout">
        <button
          type="button"
          className={`${styles.toggleBtn} ${mode === 'side' ? styles.toggleActive : ''}`}
          aria-pressed={mode === 'side'}
          onClick={() => setModeOverride('side')}
        >
          Side by side
        </button>
        <button
          type="button"
          className={`${styles.toggleBtn} ${mode === 'stacked' ? styles.toggleActive : ''}`}
          aria-pressed={mode === 'stacked'}
          onClick={() => setModeOverride('stacked')}
        >
          Stacked
        </button>
      </div>

      <div className={`${styles.diffGrid} ${mode === 'side' ? styles.diffSide : styles.diffStacked}`}>
        <div className={styles.diffCol}>
          <h4>Original fix (main)</h4>
          <DiffPanel diff={cell.fixDiff} emptyLabel="No code change on this branch" wrap={wrap} />
        </div>
        <div className={styles.diffCol}>
          <h4>Backport ({cell.branch})</h4>
          <DiffPanel diff={cell.backportDiff} emptyLabel="No code change on this branch" wrap={wrap} />
        </div>
      </div>
    </div>
  );
}

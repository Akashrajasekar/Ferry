import styles from './AuditTable.module.css';
import type { AuditOutcome, AuditRow, ViewModel } from '../lib/model';

interface Props {
  vm: ViewModel;
}

function jumpToCell(cellKey: string) {
  window.location.hash = `#cell-${cellKey}`;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.getElementById('matrix')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
}

function OutcomePill({ outcome }: { outcome: AuditOutcome }) {
  const cls = `${styles.outcome} ${styles[outcome.tone]}`;
  if (outcome.cellKey) {
    return (
      <button type="button" className={cls} onClick={() => jumpToCell(outcome.cellKey!)}>
        {outcome.label}
      </button>
    );
  }
  return (
    <span className={cls} title={outcome.tooltip}>
      {outcome.label}
    </span>
  );
}

export function AuditTable({ vm }: Props) {
  const branches = vm.branches;
  const securityDetected = vm.auditRows.filter(
    (r) => r.kind === 'security' && Object.values(r.outcomes).some((o) => o.tone === 'detected'),
  ).length;

  const summary = [
    `${vm.metrics.fixesAudited} fixes audited`,
    `${vm.metrics.portsProven} ports proven`,
    securityDetected > 0
      ? `${securityDetected} more security fix${
          securityDetected === 1 ? '' : 'es'
        } detected, ready for the next run`
      : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <section aria-labelledby="audit-heading" className={styles.section}>
      <div className="container">
        <h2 id="audit-heading" className={styles.heading}>
          Audit → outcome
        </h2>
        <p className={styles.subtitle}>
          What the audit found on each release branch, and what Ferry did about it.
        </p>
        <p className={styles.summary}>{summary}</p>

        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Commit</th>
                <th scope="col">Subject</th>
                <th scope="col">Kind</th>
                {branches.map((b) => (
                  <th key={b} scope="col">
                    {b}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vm.auditRows.map((row: AuditRow) => (
                <tr key={row.shortSha}>
                  <td className={styles.sha}>{row.shortSha}</td>
                  <td>{row.subject}</td>
                  <td>
                    <span
                      className={`${styles.kindChip} ${row.kind === 'security' ? styles.security : ''}`}
                    >
                      {row.kind}
                    </span>
                  </td>
                  {branches.map((b) => (
                    <td key={b} className={styles.outcomeCell}>
                      <OutcomePill outcome={row.outcomes[b]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className={styles.cards}>
          {vm.auditRows.map((row: AuditRow) => (
            <div key={row.shortSha} className={styles.mobileCard}>
              <div className={styles.mobileTop}>
                <span className={styles.sha}>{row.shortSha}</span>
                <span
                  className={`${styles.kindChip} ${row.kind === 'security' ? styles.security : ''}`}
                >
                  {row.kind}
                </span>
              </div>
              <p className={styles.mobileSubject}>{row.subject}</p>
              <div className={styles.mobileBranches}>
                {branches.map((b) => (
                  <div key={b} className={styles.mobileBranchRow}>
                    <span>{b}</span>
                    <OutcomePill outcome={row.outcomes[b]} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

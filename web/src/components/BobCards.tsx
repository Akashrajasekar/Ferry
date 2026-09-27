import styles from './BobCards.module.css';
import type { Metrics } from '../lib/model';

interface Props {
  metrics: Metrics;
}

export function BobCards({ metrics }: Props) {
  return (
    <section id="bob" className={styles.section} aria-labelledby="bob-heading">
      <div className="container">
        <div className={styles.header}>
          <p className={styles.eyebrow}>BUILT WITH IBM BOB</p>
          <h2 id="bob-heading" className={styles.heading}>
            Built with Bob. Runs on Bob.
          </h2>
        </div>

        <div className={styles.grid}>
          <div className={styles.card}>
            <p className={styles.tag}>.bob/custom_modes.yaml</p>
            <p className={styles.title}>Ferry custom mode</p>
            <p className={styles.desc}>
              A backport-engineer role that can only edit backport worktrees, never main.
            </p>
          </div>

          <div className={styles.card}>
            <p className={styles.tag}>skills/backport-adapt</p>
            <p className={styles.title}>Backport skill</p>
            <p className={styles.desc}>
              Trace renames, adapt to the branch&rsquo;s API, port the test, prove it, or escalate.
            </p>
          </div>

          <div className={styles.card}>
            <p className={styles.tag}>Plan mode · PDF + DOCX</p>
            <p className={styles.title}>Document understanding</p>
            <p className={styles.desc}>
              Bob reads the support policy and advisory, and cites a section for every decision.
            </p>
          </div>

          <div className={styles.card}>
            <p className={styles.tag}>{metrics.adaptedCount} in parallel</p>
            <p className={styles.title}>Subagents</p>
            <p className={styles.desc}>
              One per conflicted port, each in its own context window and worktree.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

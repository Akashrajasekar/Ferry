import styles from './Impact.module.css';
import type { Metrics } from '../lib/model';
import { DASH, fmt } from '../lib/model';

interface Props {
  metrics: Metrics;
}

export function Impact({ metrics }: Props) {
  const n = metrics.conflictedPorts;

  return (
    <section aria-label="Impact" className={styles.section}>
      <div className={`container ${styles.grid}`}>
        <div className={styles.card}>
          <p className={styles.label}>BY HAND</p>
          <p className={styles.value}>{fmt(metrics.manualBaselineMinutes)} min</p>
          <p className={styles.desc}>For one conflicted backport, ported and adapted by hand.</p>
        </div>

        <div className={`${styles.card} ${styles.bob}`}>
          <p className={styles.label}>WITH FERRY</p>
          <p className={styles.value}>
            {metrics.ferryRunMinutes === null ? DASH : metrics.ferryRunMinutes} min
          </p>
          <p className={styles.desc}>
            For {n} conflicted backport{n === 1 ? '' : 's'} in parallel, each adapted and proven.
          </p>
        </div>

        <div className={styles.card}>
          <p className={styles.label}>COST</p>
          <p className={styles.value}>0 Bobcoins</p>
          <p className={styles.desc}>For clean cherry-picks — no adaptation needed.</p>
          <p className={styles.sub}>
            {metrics.bobcoinsPerAdaptedPort === null ? DASH : metrics.bobcoinsPerAdaptedPort}{' '}
            Bobcoins per adapted port
          </p>
        </div>
      </div>
    </section>
  );
}

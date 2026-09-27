import styles from './MetricsStrip.module.css';
import { useCountUp } from '../hooks/useCountUp';
import type { Metrics } from '../lib/model';
import { DASH } from '../lib/model';

interface Props {
  metrics: Metrics;
}

function StatNumber({ target, tone }: { target: number; tone?: 'proven' | 'review' | 'bob' }) {
  const { ref, value } = useCountUp<HTMLSpanElement>(target);
  const cls = tone ? `${styles.value} ${styles[tone]}` : styles.value;
  return (
    <span ref={ref} className={cls}>
      {value}
    </span>
  );
}

function StatRatio({
  numerator,
  denominator,
  tone,
}: {
  numerator: number;
  denominator: number;
  tone?: 'proven' | 'review' | 'bob';
}) {
  const { ref, value } = useCountUp<HTMLSpanElement>(numerator);
  const cls = tone ? `${styles.value} ${styles[tone]}` : styles.value;
  return (
    <span ref={ref} className={cls}>
      {value}/{denominator}
    </span>
  );
}

export function MetricsStrip({ metrics }: Props) {
  return (
    <section aria-label="Key metrics" className={styles.section}>
      <div className={`container ${styles.grid}`}>
        <div className={styles.tile}>
          <StatNumber target={metrics.fixesAudited} />
          <p className={styles.label}>Fixes audited</p>
        </div>
        <div className={styles.tile}>
          <StatRatio numerator={metrics.citations} denominator={metrics.decisions} />
          <p className={styles.label}>Decisions cited</p>
        </div>
        <div className={styles.tile}>
          <StatRatio numerator={metrics.portsProven} denominator={metrics.portsAttempted} tone="proven" />
          <p className={styles.label}>Ports proven</p>
        </div>
        <div className={styles.tile}>
          <StatNumber target={metrics.adaptedCount} tone="bob" />
          <p className={styles.label}>Parallel Bob subagents</p>
        </div>
        <div className={styles.tile}>
          <StatNumber target={metrics.reviewFlags} tone="review" />
          <p className={styles.label}>Review flags</p>
        </div>
        <div className={styles.tile}>
          <span className={`${styles.value} ${styles.bob}`}>
            {metrics.bobcoinsPerAdaptedPort === null ? DASH : metrics.bobcoinsPerAdaptedPort}
          </span>
          <p className={styles.label}>Bobcoins / adapted port</p>
        </div>
      </div>
    </section>
  );
}

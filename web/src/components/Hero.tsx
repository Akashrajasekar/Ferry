import styles from './Hero.module.css';
import { ReleaseRiver } from './ReleaseRiver';
import type { ViewModel } from '../lib/model';
import { fmt } from '../lib/model';

interface Props {
  vm: ViewModel;
}

export function Hero({ vm }: Props) {
  return (
    <section id="top" className={styles.hero} aria-label="Introduction">
      <div className={`container ${styles.grid}`}>
        <div>
          <p className={styles.eyebrow}>AI BACKPORTING · PROVEN BY TESTS</p>
          <h1 className={styles.title}>A fix on main isn&rsquo;t a fix for your customers.</h1>
          <p className={styles.subtext}>
            Until it reaches every release they run. Ferry carries each fix into every supported
            branch, adapts it where the code has moved on, and proves every port with tests.
          </p>

          <div className={styles.callout}>
            <span className={styles.calloutDot} aria-hidden="true" />
            <p className={styles.calloutText}>
              <strong>{fmt(vm.metrics.missingSecurityFixes)} security fixes</strong> on main were
              silently missing from every supported release branch — found by Ferry&rsquo;s audit
              in seconds.
            </p>
          </div>

          <div className={styles.ctaRow}>
            <a className={styles.btnPrimary} href="#matrix">
              Open the proof matrix
            </a>
            <a className={styles.btnSecondary} href="#run">
              See how it works
            </a>
          </div>
        </div>

        <div className={styles.riverCard}>
          <ReleaseRiver fixes={vm.fixes} branches={vm.branches} cellsByKey={vm.cellsByKey} />
        </div>
      </div>
    </section>
  );
}

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
            Software teams often support several versions of their product at the same time. When
            a bug or security hole is fixed in the newest version, that fix has to be copied into
            every older version customers still use. This is called <strong>backporting</strong> —
            and it&rsquo;s slow, manual work, because older versions of the code look different.
          </p>
          <p className={styles.subtext}>
            <strong>Ferry does it automatically:</strong> it finds fixes that older versions are
            missing, uses IBM Bob to adapt each fix to the older code, and runs tests to prove
            every copy works.
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

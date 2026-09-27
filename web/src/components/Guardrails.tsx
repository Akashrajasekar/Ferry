import styles from './Guardrails.module.css';

export function Guardrails() {
  return (
    <section id="guardrails" className={styles.section} aria-labelledby="guardrails-heading">
      <div className="container">
        <div className={styles.header}>
          <p className={styles.eyebrow}>PROOF &amp; GUARDRAILS</p>
          <h2 id="guardrails-heading" className={styles.heading}>
            Every port proven. Every judgment call surfaced.
          </h2>
        </div>

        <div className={styles.grid}>
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Proof, per test</h3>
            <p className={styles.cardBody}>
              Each regression test must fail before the fix and pass after it, and the
              branch&rsquo;s full suite must stay green; only a genuine test failure counts as
              proof, so every green cell is earned.
            </p>
          </div>

          <div className={`${styles.card} ${styles.review}`}>
            <h3 className={styles.cardTitle}>Precision proof checks</h3>
            <p className={styles.cardBody}>
              Ferry proves every test individually; if a test already passes without the fix, it
              is highlighted for a quick review, so the evidence behind every port stays airtight.
            </p>
          </div>

          <div className={`${styles.card} ${styles.review}`}>
            <h3 className={styles.cardTitle}>Release managers stay in control</h3>
            <p className={styles.cardBody}>
              When a fix changes tested behaviour on a maintenance branch, Ferry ports it, proves
              it, and routes it for sign-off.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

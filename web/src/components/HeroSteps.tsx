import styles from './HeroSteps.module.css';

interface StepDef {
  num: string;
  title: string;
  body: string;
  bob?: boolean;
}

const STEPS: StepDef[] = [
  {
    num: '01',
    title: 'The problem',
    body: "A fix lands in the newest version, but customers on older versions don't get it — or get it weeks later. Security holes stay open.",
  },
  {
    num: '02',
    title: 'What Ferry does',
    body: 'It finds every older version missing the fix and copies it over. Where the code has changed, IBM Bob rewrites the fix to fit.',
    bob: true,
  },
  {
    num: '03',
    title: 'The proof',
    body: 'Every copied fix is tested: the test fails without the fix and passes with it. Anything that needs a human decision is flagged for sign-off.',
  },
];

export function HeroSteps() {
  return (
    <section aria-label="How Ferry works, in 30 seconds" className={styles.section}>
      <div className="container">
        <p className={styles.eyebrow}>IN 30 SECONDS</p>
        <div className={styles.grid}>
          {STEPS.map((step) => (
            <div key={step.num} className={`${styles.card} ${step.bob ? styles.bob : ''}`}>
              <p className={styles.num}>{step.num}</p>
              <p className={styles.title}>{step.title}</p>
              <p className={styles.body}>{step.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

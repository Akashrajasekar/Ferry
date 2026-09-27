import styles from './RunSteps.module.css';
import type { PipelineStep } from '../lib/model';

interface StepDef {
  id: PipelineStep['id'];
  num: string;
  title: string;
  by: 'bob' | 'script';
  description: string;
}

const STEPS: StepDef[] = [
  {
    id: 'audit',
    num: '01',
    title: 'Audit',
    by: 'script',
    description:
      'Scans every commit on main against every release branch to find fixes that never made it across.',
  },
  {
    id: 'scope',
    num: '02',
    title: 'Scope',
    by: 'bob',
    description:
      'Reads the support policy and security advisory, then decides which branches each fix belongs on — with a citation for every call.',
  },
  {
    id: 'try',
    num: '03',
    title: 'Try',
    by: 'script',
    description:
      'Attempts a clean cherry-pick on each target branch and flags exactly where the code has moved on.',
  },
  {
    id: 'adapt',
    num: '04',
    title: 'Adapt',
    by: 'bob',
    description:
      'Traces renames and API drift, ports the fix and its test to each conflicted branch, and proves the port before moving on.',
  },
  {
    id: 'verify',
    num: '05',
    title: 'Verify',
    by: 'script',
    description:
      "Runs every regression test before and after the fix, and the branch's full suite, so every proven port has earned it.",
  },
  {
    id: 'report',
    num: '06',
    title: 'Report',
    by: 'script',
    description:
      'Builds the proof matrix, the diffs, and the changelog entries for every branch, ready for a release manager.',
  },
];

interface Props {
  pipeline: PipelineStep[];
}

export function RunSteps({ pipeline }: Props) {
  const resultFor = (id: PipelineStep['id']) => pipeline.find((p) => p.id === id)?.result ?? '—';

  return (
    <section id="run" className={styles.section} aria-labelledby="run-heading">
      <div className="container">
        <div className={styles.header}>
          <p className={styles.eyebrow}>THE RUN</p>
          <h2 id="run-heading" className={styles.heading}>
            Six steps. Bob does the thinking, scripts do the rest.
          </h2>
          <div className={styles.legend}>
            <span className={styles.legendItem}>
              <span className={`${styles.legendChip} ${styles.bobChip}`} aria-hidden="true" />
              IBM Bob
            </span>
            <span className={styles.legendItem}>
              <span className={`${styles.legendChip} ${styles.scriptChip}`} aria-hidden="true" />
              deterministic script
            </span>
          </div>
        </div>

        <ol className={styles.grid}>
          {STEPS.map((step) => (
            <li key={step.id} className={`${styles.card} ${step.by === 'bob' ? styles.bob : ''}`}>
              <div className={styles.cardTop}>
                <span className={styles.step}>{step.num}</span>
                <span className={`${styles.chip} ${step.by === 'bob' ? styles.bobChipText : ''}`}>
                  {step.by === 'bob' ? 'IBM Bob' : 'script'}
                </span>
              </div>
              <h3 className={styles.cardTitle}>{step.title}</h3>
              <p className={styles.cardDesc}>{step.description}</p>
              <p className={`${styles.cardResult} mono`}>{resultFor(step.id)}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

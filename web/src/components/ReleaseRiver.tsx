import { useId } from 'react';
import styles from './ReleaseRiver.module.css';
import type { Cell, Fix } from '../lib/model';
import { cellKeyFor, isEndOfLife, supportStatusFor } from '../lib/model';
import { plainStatusFor } from '../content';

interface Props {
  fixes: Fix[];
  branches: string[];
  cellsByKey: Map<string, Cell>;
}

const LANE_GAP = 68;
const TOP_PAD = 46;
const LEFT_PAD = 190;
const RIGHT_PAD = 30;
const SVG_WIDTH = 660;
const DOT_R = 11;
const BADGE_W = 48;
const BADGE_H = 24;

export function ReleaseRiver({ fixes, branches, cellsByKey }: Props) {
  const titleId = useId();
  const mainY = TOP_PAD;
  const laneY = (i: number) => TOP_PAD + (i + 1) * LANE_GAP;
  const svgHeight = TOP_PAD + (branches.length + 1) * LANE_GAP + 24;

  const usableWidth = SVG_WIDTH - LEFT_PAD - RIGHT_PAD;
  const dotSpacing = usableWidth / Math.max(fixes.length, 1);
  const dotX = (i: number) => LEFT_PAD + dotSpacing * (i + 0.5);

  const fixHasAnyRoute = (fix: Fix) =>
    branches.some((branch) => {
      const cell = cellsByKey.get(cellKeyFor(fix.letter, branch));
      return cell?.statusKind === 'adapted_proven' || cell?.statusKind === 'clean_proven';
    });

  return (
    <div className={styles.wrap}>
      <p className={styles.caption}>
        <strong>How to read this:</strong> each line is a version of the product.{' '}
        <strong>main</strong> is the newest; the lines below are older versions customers still
        run. Dots <strong>A–D</strong> are fixes made on main, and the dashed lines show Ferry
        carrying each fix down to older versions. <strong>✓</strong> means the copied fix was
        tested and works.
      </p>

      <svg
        className={styles.svg}
        viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
        role="img"
        aria-labelledby={titleId}
      >
        <title id={titleId}>
          Release river: fixes on main routed and proven across supported release branches
        </title>

        {/* main lane */}
        <line
          x1={LEFT_PAD}
          y1={mainY}
          x2={SVG_WIDTH - RIGHT_PAD}
          y2={mainY}
          stroke="var(--bob)"
          strokeWidth={2.5}
        />
        <text x={16} y={mainY - 7} className={styles.laneLabel} fill="var(--bob-light)">
          main
          <title>{supportStatusFor('main')}</title>
        </text>
        <text x={16} y={mainY + 15} className={styles.laneStatus}>
          {plainStatusFor('main')}
        </text>

        {fixes.map((fix, i) => (
          <g key={fix.letter}>
            <circle cx={dotX(i)} cy={mainY} r={DOT_R} fill="var(--bob)" />
            <text x={dotX(i)} y={mainY + 1} className={styles.dotLetter}>
              {fix.letter}
            </text>
            {!fixHasAnyRoute(fix) && (
              <text x={dotX(i)} y={mainY + DOT_R + 15} className={styles.naNote}>
                n/a
              </text>
            )}
          </g>
        ))}

        {/* branch lanes */}
        {branches.map((branch, bi) => {
          const y = laneY(bi);
          const eol = isEndOfLife(branch);
          return (
            <g key={branch}>
              <line
                x1={LEFT_PAD}
                y1={y}
                x2={SVG_WIDTH - RIGHT_PAD}
                y2={y}
                stroke="var(--border-strong)"
                strokeWidth={2}
                strokeDasharray={eol ? '4 5' : undefined}
                opacity={eol ? 0.55 : 1}
              />
              <text
                x={16}
                y={y - 7}
                className={styles.laneLabel}
                fill={eol ? 'var(--muted)' : 'var(--text-2)'}
              >
                {branch}
                <title>{supportStatusFor(branch)}</title>
              </text>
              <text x={16} y={y + 15} className={styles.laneStatus}>
                {plainStatusFor(branch)}
              </text>

              {fixes.map((fix, fi) => {
                const cell = cellsByKey.get(cellKeyFor(fix.letter, branch));
                if (!cell) return null;
                const isAdapted = cell.statusKind === 'adapted_proven';
                const isClean = cell.statusKind === 'clean_proven';
                if (!isAdapted && !isClean) return null;
                const x = dotX(fi);
                return (
                  <g key={fix.letter}>
                    <path
                      d={`M ${x} ${mainY + DOT_R} L ${x} ${y - BADGE_H / 2}`}
                      className={isAdapted ? styles.routeAdapted : styles.routeClean}
                    />
                    <rect
                      x={x - BADGE_W / 2}
                      y={y - BADGE_H / 2}
                      width={BADGE_W}
                      height={BADGE_H}
                      rx={BADGE_H / 2}
                      fill={isAdapted ? 'var(--proven-surface)' : 'var(--bob-surface)'}
                      stroke={isAdapted ? 'var(--proven-border)' : 'var(--bob-border)'}
                    />
                    <text
                      x={x}
                      y={y + 1}
                      className={styles.badgeText}
                      fill={isAdapted ? 'var(--proven)' : 'var(--bob-light)'}
                    >
                      {fix.letter} ✓
                    </text>
                    {cell.reviewRequired && (
                      <circle cx={x + BADGE_W / 2 - 4} cy={y - BADGE_H / 2} r={4} fill="var(--review)" />
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <span className={styles.legendSwatch} style={{ background: 'var(--proven)' }} />
          adapted by Bob, proven
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendSwatch} style={{ background: 'var(--bob-light)' }} />
          clean cherry-pick, proven
        </span>
        <span className={styles.legendItem}>
          <span className={styles.legendSwatch} style={{ background: 'var(--review)' }} />
          flagged for sign-off
        </span>
      </div>
    </div>
  );
}

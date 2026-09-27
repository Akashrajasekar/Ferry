import { useEffect, useRef, useState } from 'react';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Animates from 0 to `target` once the ref scrolls into view. Runs once.
export function useCountUp<T extends HTMLElement = HTMLElement>(target: number | null, durationMs = 900) {
  const ref = useRef<T | null>(null);
  const [value, setValue] = useState(0);
  const startedRef = useRef(false);

  useEffect(() => {
    if (target === null) return;
    const el = ref.current;
    if (!el) return;

    if (prefersReducedMotion()) {
      setValue(target);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !startedRef.current) {
            startedRef.current = true;
            const start = performance.now();
            const tick = (now: number) => {
              const progress = Math.min(1, (now - start) / durationMs);
              const eased = 1 - Math.pow(1 - progress, 3);
              setValue(Math.round(eased * target));
              if (progress < 1) requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
            observer.disconnect();
          }
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [target, durationMs]);

  return { ref, value };
}

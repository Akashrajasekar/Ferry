import { useEffect, useRef, useState } from 'react';
import styles from './Nav.module.css';
import { FerryLogo } from './FerryLogo';

const GITHUB_URL = 'https://github.com/Akashrajasekar/Ferry';

const LINKS = [
  { href: '#run', label: 'The run' },
  { href: '#matrix', label: 'Proof matrix' },
  { href: '#guardrails', label: 'Proof & guardrails' },
  { href: '#bob', label: 'Built with IBM Bob' },
];

export function Nav() {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className={styles.nav}>
      <nav className={`container ${styles.inner}`} aria-label="Primary">
        <a href="#top" className={styles.brand}>
          <FerryLogo size={26} />
          Ferry
        </a>

        <ul className={styles.links}>
          {LINKS.map((link) => (
            <li key={link.href}>
              <a href={link.href}>{link.label}</a>
            </li>
          ))}
        </ul>

        <div className={styles.actions}>
          <a className={styles.ghBtn} href={GITHUB_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
          <button
            type="button"
            className={styles.menuBtn}
            aria-expanded={open}
            aria-controls="mobile-nav-panel"
            aria-label={open ? 'Close menu' : 'Open menu'}
            onClick={() => setOpen((v) => !v)}
          >
            <span />
          </button>
        </div>
      </nav>

      {open && (
        <div id="mobile-nav-panel" ref={panelRef} className={styles.mobilePanel}>
          {LINKS.map((link) => (
            <a key={link.href} href={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </a>
          ))}
          <a className={styles.mobileGh} href={GITHUB_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
        </div>
      )}
    </header>
  );
}

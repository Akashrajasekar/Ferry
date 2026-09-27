import styles from './Footer.module.css';

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.row}`}>
        <span className={styles.brand}>
          <span className={styles.dot} aria-hidden="true" />
          Ferry is built with and runs on IBM Bob · IBM Bob 2.0 Hackathon
        </span>
        <a className={styles.link} href="https://github.com/Akashrajasekar/Ferry" target="_blank" rel="noreferrer">
          github.com/Akashrajasekar/Ferry
        </a>
      </div>
    </footer>
  );
}

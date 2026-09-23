import styles from './HomePage.module.css';

export default function HomePage() {
  return (
    <main className={styles.page}>
      <section className={styles.hero} aria-labelledby="app-title">
        <p className={styles.status}>Early development</p>
        <h1 id="app-title" className={styles.title}>
          RepoPilot
        </h1>
        <p className={styles.tagline}>AI-assisted GitHub pull request review</p>
        <p className={styles.description}>
          Analyze pull requests, surface risks, and generate structured review feedback.
        </p>
      </section>
    </main>
  );
}

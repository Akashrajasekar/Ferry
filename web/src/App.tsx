import { Nav } from './components/Nav';
import { Hero } from './components/Hero';
import { HeroSteps } from './components/HeroSteps';
import { MetricsStrip } from './components/MetricsStrip';
import { RunSteps } from './components/RunSteps';
import { ProofMatrix } from './components/ProofMatrix';
import { Impact } from './components/Impact';
import { Guardrails } from './components/Guardrails';
import { AuditTable } from './components/AuditTable';
import { BobCards } from './components/BobCards';
import { Footer } from './components/Footer';
import { Reveal } from './components/Reveal';
import { viewModel } from './lib/model';

export default function App() {
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <Nav />
      <main id="main-content">
        <Hero vm={viewModel} />
        <Reveal>
          <HeroSteps />
        </Reveal>
        <Reveal>
          <MetricsStrip metrics={viewModel.metrics} />
        </Reveal>
        <Reveal>
          <RunSteps pipeline={viewModel.pipeline} />
        </Reveal>
        <Reveal>
          <ProofMatrix vm={viewModel} />
        </Reveal>
        <Reveal>
          <Impact metrics={viewModel.metrics} />
        </Reveal>
        <Reveal>
          <Guardrails />
        </Reveal>
        <Reveal>
          <AuditTable vm={viewModel} />
        </Reveal>
        <Reveal>
          <BobCards metrics={viewModel.metrics} />
        </Reveal>
      </main>
      <Footer />
    </>
  );
}

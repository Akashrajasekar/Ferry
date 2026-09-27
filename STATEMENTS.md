# Ferry — Submission Statements

---

## Problem & Solution Statement

**The problem.** When a bug or security fix lands on `main`, every supported release branch needs it too. This is backporting, and it is still mostly manual. Backport bots such as those used by ClickHouse or Microsoft CCF only handle the easy case: if a cherry-pick applies cleanly, they open a PR; if it conflicts, a human takes over. Conflicts are the norm on long-lived branches, because files move and functions are renamed between versions. So fixes reach older releases late or never, leaving LTS customers exposed after the fix "shipped". Research prototypes like PortGPT show LLMs can adapt patches, but no developer tool productizes it.

**What Ferry does.** Ferry carries a fix from `main` into every supported release branch and proves every port with tests. It runs a six-step pipeline:

1. **Audit** finds fix commits on `main` that are missing from release branches.
2. **Scope** reads the support policy (PDF) and security advisory (DOCX) and decides, per branch, whether to port, skip or mark not applicable, citing the section behind each decision.
3. **Try** attempts a plain cherry-pick; clean ports cost zero AI effort.
4. **Adapt** sends each conflicted port to its own IBM Bob subagent, running in parallel, which traces renames and moves through git history, adapts the fix to that branch's API and ports the regression test.
5. **Verify** requires every regression test to fail before the fix and pass after it, plus the full suite to pass. A test that fails for the wrong reason, like an import error, does not count as proof.
6. **Report** publishes a dashboard with the release matrix, per-test evidence, side-by-side diffs and changelogs.

**Guardrails built in.** Ferry routes judgment calls to a release manager: when a fix changes tested behaviour on a branch (an existing test was updated), or when a test already passes without the fix, so the proof must come from the other tests. Every port stays auditable.

**Results on the demo project** (a Python library with four diverged release lines):

- The audit found 6 fix commits, including 2 security fixes silently missing from every release branch.
- Scoping from the documents matched the policy for all 12 fix × branch decisions, each with a citation.
- 4 ports were proven: 1 clean cherry-pick (0 Bobcoins) and 3 conflicted ports adapted by 3 parallel subagents, all passing fail-before, pass-after and the full suite.
- 2 review flags were raised: one behaviour change needing sign-off, and one precision check on an already-passing test.
- Backporting one conflicted fix by hand took **16.4 minutes** (a conservative, guided baseline). Ferry adapted and proved **three** conflicted ports in parallel in **10.9 minutes** — about **3.6 minutes per port**, roughly **4.5x faster per port** than doing it by hand.

**Impact.** Proven backports shorten the window in which older releases stay exposed, and make every decision auditable: why a branch was skipped, what was adapted, and which test proves it. Next: a GitHub Action running `audit` on every merge.

---

## IBM Bob Usage Statement

IBM Bob IDE is both how Ferry was built and the engine it runs on.

**Ferry runs on Bob.**

- **Custom mode.** A project-scoped "Ferry" mode (`.bob/custom_modes.yaml`) defines a backport-engineer role with deliberately constrained tools: read, execute, subagent, and edit restricted by regex to backport worktrees and port-result files. Ferry cannot touch `main` or its own source code while porting.
- **Skill.** `backport-adapt` (`.bob/skills/backport-adapt/SKILL.md`) encodes the procedure every port follows: understand the fix; locate moved and renamed code with `git log --follow`, `git log -S` and grep; adapt to the branch's API; port the test without weakening it; commit with a `Backport of <sha>` trailer; prove it with `ferry verify`; escalate after three failed attempts.
- **Parallel subagents.** Each conflicted (fix, branch) pair runs in its own subagent with an isolated context window. Three ran in parallel and all three ports were proven.
- **Document understanding.** In Plan mode, Bob read `SUPPORT_POLICY.pdf` and `SECURITY_ADVISORY.docx` and produced all 12 scoping decisions with section citations, correctly ruling that an end-of-life policy overrides the advisory's "affected" list. It also used git evidence to mark code-absent fixes as not applicable.
- **Rules and AGENTS.md** keep every task consistent: mechanical work belongs in scripts, and no port counts as done without `verify`.

**Ferry was built with Bob.** In Agent mode, Bob wrote:

- the demo scenario generator;
- the whole `ferry` CLI (`audit`, `try`, `verify`, `report`, `reset`);
- the per-test junit-based proof and review-flag logic;
- the concurrency-safe results merging that parallel subagents required;
- the dashboard generator;
- the test suite.

Session summaries for every task are in `bob_sessions/`.

**Designed for Bobcoin efficiency.** Bob is only used where reasoning is needed: scoping from documents and adapting conflicted ports. Everything mechanical (git operations, test runs, verification, reporting) is a deterministic Python script. Clean cherry-picks never call Bob. JSON files in `.ferry/` pass state between steps, so each Bob task stays small. The whole project, including building Ferry, used **30.6 Bobcoins**; the three adapted ports used **4.28 (about 1.4 per port)**.

**Proof-backed by design.** Every port Bob produces goes through independent per-test verification before it is marked proven, so Bob's speed comes with evidence a reviewer can inspect in one click.

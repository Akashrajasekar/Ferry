# ⛴️ Ferry — every fix, every supported release, proven

**Ferry backports fixes from `main` into every supported release branch, adapts them where the code has diverged using parallel IBM Bob subagents, and proves every port with fail-before / pass-after tests.**

- 🌐 **Live dashboard:** https://ferry-snowy.vercel.app/
- 🎬 **Demo video:** https://drive.google.com/file/d/1tTNnEEV-8XBI5H33Sfjrz62Q491XwMWN/view?usp=sharing
- 🏆 Built for the IBM Bob 2.0 Hackathon (lablab.ai, September 2026)

---

## The problem

When a fix lands on `main`, every supported release branch needs it too. Existing backport bots only handle clean cherry-picks; when a cherry-pick conflicts (files moved, functions renamed, signatures changed), a human takes over. That is slow, error-prone and often skipped, so customers on older releases stay exposed after the fix has "shipped".

## How Ferry works

```
audit  ->  scope  ->  try  ->  adapt  ->  verify  ->  report
```

| Step       | What happens                                                                                                              | Who does it                                   |
| ---------- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| **audit**  | Finds fix commits on `main` missing from each release branch (patch-id and backport-trailer aware)                        | Python script                                 |
| **scope**  | Reads `SUPPORT_POLICY.pdf` + `SECURITY_ADVISORY.docx` and decides port / skip / not applicable per branch, with citations | IBM Bob (Plan mode)                           |
| **try**    | Plain `git cherry-pick -x` in an isolated worktree per branch; clean ports cost zero AI                                   | Python script                                 |
| **adapt**  | One Bob subagent per conflicted port, in parallel: traces renames and moves, adapts the fix, ports the regression test    | IBM Bob (Ferry mode + `backport-adapt` skill) |
| **verify** | Per test: must fail before the fix and pass after; full suite must pass; flags anything a human should review             | Python script                                 |
| **report** | Dashboard (release matrix, per-test evidence, side-by-side diffs, review flags) + changelog per branch                    | Python script                                 |

### Review flags

Ferry routes judgment calls to a human reviewer. It flags:

- **`existing_test_modified`**: the fix changes tested behaviour on that branch, so a pre-existing test was updated. Routed to a release manager for sign-off.
- **`test_passes_without_fix`**: precision check. A test already passes without the fix, so the port's proof comes from its other tests; highlighted for a quick review.

## Results (demo project)

| Metric                                               | Result                                                 |
| ---------------------------------------------------- | ------------------------------------------------------ |
| Fix commits audited                                  | 6 (2 security fixes missing from every release branch) |
| Scoping decisions from documents                     | 12 of 12 correct, each with a citation                 |
| Ports proven (fail-before + pass-after + full suite) | 4 of 4                                                 |
| Clean cherry-picks                                   | 1 (0 Bobcoins)                                         |
| Conflicted ports adapted by parallel Bob subagents   | 3                                                      |
| Review flags raised                                  | 2                                                      |
| One conflicted backport by hand                      | 16.4 min (guided, conservative baseline)               |
| Three conflicted backports with Ferry, in parallel   | 10.9 min (~3.6 min/port — 4.5x faster per port than by hand) |
| Total Bobcoins (building + running Ferry)            | 30.6                                                   |

## Quick start

Requires Python 3.10+ and git.

```bash
pip install -r requirements.txt
python -m ferry scenario     # build the demo repo + policy documents
python -m ferry audit        # find fixes missing from release branches

# Scope: done by Bob in Plan mode (task T05) -> .ferry/plan.json
# To reuse Bob's saved decisions instead, copy them into place:
#   macOS/Linux:  cp results/ferry-state/plan.json .ferry/plan.json
#   Windows:      copy results\ferry-state\plan.json .ferry\plan.json

python -m ferry try          # plain cherry-picks
# Adapt: in Bob IDE, switch to the Ferry mode and run the adapt prompt (task T06)
python -m ferry verify       # prove every port
python -m ferry report       # build docs/index.html
```

Run Ferry's own tests with `python -m pytest -q`.

## How IBM Bob is used

- **Custom mode:** [`.bob/custom_modes.yaml`](.bob/custom_modes.yaml). The Ferry mode can read, execute and spawn subagents, and can edit only backport worktrees and port-result files.
- **Skill:** [`.bob/skills/backport-adapt/SKILL.md`](.bob/skills/backport-adapt/SKILL.md), the step-by-step backport procedure every subagent follows.
- **Rules:** [`AGENTS.md`](AGENTS.md) and [`.bob/rules/`](.bob/rules/).
- **Document understanding:** Bob read the policy PDF and advisory DOCX to scope every port with citations.
- **Parallel subagents:** one per conflicted (fix, branch) pair, each in an isolated context.
- **Built with Bob:** the CLI, verification logic, dashboard generator, demo scenario and tests were written with Bob in Agent mode. Session summaries are in [`bob_sessions/`](bob_sessions/).

## Repository layout

```
.bob/            Ferry mode, backport-adapt skill, rules
ferry/           CLI: audit, try, verify, report, reset
scenario/        demo repo + document generators
tests/           tests for Ferry itself
docs/            generated dashboard (GitHub Pages)
results/         final run state + changelogs
bob_sessions/    IBM Bob task session summaries
```

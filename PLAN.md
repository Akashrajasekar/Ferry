# PLAN.md — Ferry

> **How to use this file in IBM Bob**
>
> - Put this file in the repo root. Do NOT copy it into `AGENTS.md` or `.bob/rules/` (those load on every request and waste Bobcoins).
> - Start each task in a **new context window**, then reference only what you need, e.g. `@PLAN.md` + "Do Task T03".
> - Every task below has: goal, prompt to paste, acceptance criteria, coin budget, screenshot name.
> - Steps marked **[HUMAN]** are done by you, not Bob.

---

## 0. Status tracker (Bob: tick the box at the end of each task)

- [x] T01 Bob foundation (AGENTS.md, custom mode, skill, rules)
- [x] T02 Scenario generator + policy documents
- [x] T03 CLI part 1: `audit`, `try`
- [x] T04 CLI part 2: `verify`, `report`
- [x] T05 Scope fixes from documents (Plan mode)
- [x] T06 Adaptive ports with parallel subagents (Ferry mode)
- [x] T07 Dashboard polish + GitHub Pages
- [ ] T08 Final clean end-to-end run (recorded)
- [ ] H1–H6 Human submission steps (Section 9)

---

## 1. Project summary

**Ferry** carries a bug/security fix from `main` into every _supported_ release branch, adapts it where the code has diverged, and **proves** each port with tests.

- Existing backport bots only handle conflict-free cherry-picks; conflicts go to a human. Ferry targets exactly that conflicted case.
- Research (PortGPT, BackportBench) shows LLM backporting is feasible; no developer tool productizes it.

**Hackathon constraints**

- Deadline: **Sep 27, 7:00 PM GST**. Target submit time: 5:00 PM GST.
- Budget: **40 Bobcoins total**. Bob is used only where reasoning is needed; everything mechanical is a plain Python script.
- Bob IDE must be a core component. Bob task session screenshots go in `bob_sessions/`.

---

## 2. Rules for Bob (apply to every task)

1. Keep changes minimal and scoped to the task. Do not refactor unrelated files.
2. Deterministic logic (git, tests, JSON, HTML) goes in Python scripts, never in chat reasoning.
3. Python 3.10+, standard library + `pytest`, `reportlab`, `python-docx` only. No web frameworks.
4. Never edit the `main` branch of the demo repo. All port edits happen in `workspace/worktrees/**`.
5. Never claim a port succeeded unless `python -m ferry verify` passes for it.
6. After each task: run the acceptance checks, tick the box in Section 0, and summarize in ≤5 lines.
7. Do not read `workspace/` unless the task needs it. Do not re-read this whole file; read only the sections named in the task.

---

## 3. Repository layout (target)

```
ferry/                          # repo root
├── PLAN.md  README.md  LICENSE (MIT)  STATEMENTS.md  AGENTS.md
├── .bob/
│   ├── custom_modes.yaml       # "ferry" mode (Appendix A)
│   ├── rules/01-ferry.md       # short always-on rules (Appendix C)
│   └── skills/backport-adapt/SKILL.md   # (Appendix B)
├── ferry/                      # Python package, run as `python -m ferry <cmd>`
│   ├── __main__.py  cli.py  gitops.py  audit.py  mechanical.py  verify.py  report.py
├── scenario/
│   ├── build_scenario.py       # builds workspace/demo-ledger (Section 4)
│   └── make_docs.py            # builds SUPPORT_POLICY.pdf + SECURITY_ADVISORY.docx
├── tests/                      # tests for Ferry itself
├── workspace/                  # GENERATED, git-ignored
│   ├── demo-ledger/            # the demo repo with release branches
│   └── worktrees/              # one worktree per (fix, branch)
├── .ferry/                     # GENERATED state (JSON contracts, Section 5)
├── results/                    # committed copy of the final run's .ferry + changelogs
├── docs/index.html             # dashboard (GitHub Pages)
├── bob_sessions/               # Bob task summary screenshots
└── slides/
```

`.gitignore` must include `workspace/` and `.ferry/`.

---

## 4. Demo scenario spec (`scenario/build_scenario.py`)

Creates a fresh git repo at `workspace/demo-ledger` (delete and recreate if it exists). Package name `ledger`, tests with pytest. Use fixed author/date env vars so SHAs are reproducible.

### 4.1 History to build (in order)

| Step | Commit(s) on main                                                                                                                                                                                                                | Branch/tag created after step      |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| 1    | v0.9: `ledger/money.py` with `round_money(x: float) -> float` using `round(x, 2)`; `ledger/export.py` with `export_invoice(invoice, path)` writing text to `path`; `ledger/templates.py` with `HEADER = "Invocie"` (typo); tests | tag `v0.9.0`, branch `release/0.9` |
| 2    | v1 features (e.g. line-item totals)                                                                                                                                                                                              | tag `v1.0.0`, branch `release/1.x` |
| 3    | v2: rename `round_money` → `round_amount(x: Decimal) -> Decimal`; change `export_invoice(invoice, filename, out_dir)` (new signature, body rewritten)                                                                            | tag `v2.0.0`, branch `release/2.x` |
| 4    | Seeded gap fixes: `fix: handle empty line items` and `fix(security): escape customer name in export header`. Cherry-pick ONLY the first into `release/2.x` with `-x`                                                             | —                                  |
| 5    | v3: move `ledger/money.py` → `ledger/money/rounding.py`; move `ledger/export.py` → `ledger/exporters/pdf.py` and restructure its body; add `ledger/discounts.py` (new in 3.0)                                                    | tag `v3.0.0`                       |
| 6    | The four demo fixes (below), each ONE commit containing code + regression test                                                                                                                                                   | —                                  |

`ledger/templates.py` must stay byte-identical from step 1 to step 6 so Fix C cherry-picks cleanly.

### 4.2 The four demo fixes (on main)

| Fix | Commit subject                                                           | Change                                                                       | Regression test                                              |
| --- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- | ------------------------------------------------------------ |
| A   | `fix(security): prevent path traversal in invoice export (FSA-2026-001)` | Reject absolute paths and `..`; resolve path and require it inside `out_dir` | `tests/test_export_security.py::test_rejects_path_traversal` |
| B   | `fix: use banker's rounding for currency`                                | `ROUND_HALF_EVEN` in rounding                                                | `tests/test_rounding.py::test_half_even`                     |
| C   | `fix: correct typo in invoice header`                                    | `"Invocie"` → `"Invoice"`                                                    | `tests/test_templates.py::test_header_spelling`              |
| D   | `fix: cap discounts at 100%`                                             | clamp in `discounts.py`                                                      | `tests/test_discounts.py::test_cap`                          |

### 4.3 Expected outcomes (acceptance for T02; tweak divergence until true)

| Fix | release/0.9 | release/1.x                       | release/2.x                       |
| --- | ----------- | --------------------------------- | --------------------------------- |
| A   | skip (EOL)  | cherry-pick **conflicts** → adapt | cherry-pick **conflicts** → adapt |
| B   | skip (EOL)  | skip (security-only)              | cherry-pick **conflicts** → adapt |
| C   | skip (EOL)  | skip (security-only)              | **clean** cherry-pick, tests pass |
| D   | skip        | not applicable (code absent)      | not applicable (code absent)      |

Also: `audit` must report the two step-4 fixes — "escape customer name" missing from 1.x and 2.x; "handle empty line items" present in 2.x via `(cherry picked from commit …)` trailer, missing from 1.x.

If git rename detection makes A or B apply cleanly, make the old-branch function bodies differ more until they conflict.

### 4.4 Documents (`scenario/make_docs.py`, output to `workspace/docs/`)

**SUPPORT_POLICY.pdf** (2 pages, numbered sections):

- §1 Versions: 3.x (main) Active. 2.x Maintenance — bug and security fixes until 2027-06-30. 1.x Security-only — security fixes only until 2026-12-31. 0.9 End-of-life since 2026-03-31, no fixes.
- §2 Definitions: a "security fix" is any fix referencing an FSA advisory or tagged `fix(security)`.
- §3 Backport process: every port must include the regression test and a `Backport of <sha>` trailer.

**SECURITY_ADVISORY.docx**: FSA-2026-001, path traversal in `export_invoice`. Affected: 0.9.0–3.0.0. Fixed in: 1.4.3, 2.2.1, 3.0.1. 0.9 not fixed (EOL). Severity: High.

All data is synthetic. No personal information.

---

## 5. JSON contracts (`.ferry/`)

Branch names are sanitized for filenames: `release/1.x` → `release-1.x`. `short` = first 7 chars of SHA.

**`.ferry/audit.json`** (written by `audit`)

```json
[
  {
    "sha": "...",
    "subject": "...",
    "kind": "fix|security",
    "branches": { "release/1.x": "missing|present|backported:<sha>" }
  }
]
```

**`.ferry/plan.json`** (written by Bob in T05)

```json
{
  "fixes": [
    {
      "sha": "...",
      "subject": "...",
      "category": "security|bugfix|feature-fix",
      "targets": [
        {
          "branch": "release/1.x",
          "decision": "port|skip|not_applicable",
          "reason": "...",
          "citation": { "doc": "SUPPORT_POLICY.pdf", "section": "§1" }
        }
      ]
    }
  ]
}
```

**`.ferry/try.json`** (written by `try`)

```json
[
  {
    "sha": "...",
    "branch": "release/2.x",
    "status": "clean_pass|conflict|test_fail|skipped",
    "worktree": "workspace/worktrees/<short>__release-2.x",
    "backport_branch": "backport/<short>/release-2.x"
  }
]
```

**`.ferry/ports/<short>__<branch>.json`** (written by Bob subagents in T06)

```json
{
  "sha": "...",
  "branch": "...",
  "status": "ported|escalated",
  "attempts": 1,
  "adaptations": [
    "round_money renamed to round_amount in v2 (found via git log -S)"
  ],
  "files_changed": ["..."],
  "tests_ported": ["tests/...::test_..."],
  "notes": "..."
}
```

**`.ferry/results.json`** (written by `verify`)

```json
[
  {
    "sha": "...",
    "branch": "...",
    "method": "clean|adapted|skipped|not_applicable|escalated",
    "f2p": true,
    "p2p": true,
    "fail_before": true,
    "pass_after": true,
    "suite": { "passed": 0, "failed": 0 },
    "seconds": 0.0
  }
]
```

**`metrics.json`** (repo root, filled in by a human)

```json
{ "manual_baseline_minutes": null, "bobcoins_by_task": {}, "notes": "" }
```

---

## 6. CLI spec (`python -m ferry <command>`)

| Command                           | Behavior                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scenario`                        | runs `scenario/build_scenario.py` then `scenario/make_docs.py`                                                                                                                                                                                                                                                                                                                                                                                                              |
| `audit`                           | For each commit on main whose subject starts with `fix`: for each `release/*` branch, mark `present` if `git cherry` shows it applied (patch-id), `backported:<sha>` if a commit on the branch has trailer `(cherry picked from commit <sha>)` or `Backport of <sha>`, else `missing`. Write `audit.json` and print a table with a count of missing security fixes.                                                                                                         |
| `try`                             | Read `plan.json`. For each `decision == port`: create worktree `workspace/worktrees/<short>__<branch>` on new branch `backport/<short>/<branch>` from the release branch; `git cherry-pick -x <sha>`. On conflict: `git cherry-pick --abort`, leave the worktree clean on the release head, status `conflict`. If clean: run pytest; status `clean_pass` or `test_fail`. Write `try.json`.                                                                                  |
| `verify [--fix SHA] [--branch B]` | For each clean or adapted port: (1) identify regression test(s) = test files touched by the backport commit; (2) **fail_before**: in a temp worktree at the release-branch head, copy in only those test files and run them — must FAIL; (3) **pass_after**: run them on the backport branch — must PASS; (4) **p2p**: full suite on the backport branch — must PASS. `f2p = fail_before and pass_after`. Merge into `results.json`. Exit code 1 if any checked port fails. |
| `report`                          | From `plan.json`, `results.json`, `ports/*.json`, `audit.json`, `metrics.json`: write `docs/index.html` (self-contained, no external requests) and `results/CHANGELOG-<branch>.md`; copy `.ferry/` to `results/ferry-state/`.                                                                                                                                                                                                                                               |
| `reset`                           | delete `workspace/worktrees`, `backport/*` branches in demo repo, and `.ferry/` (keep `plan.json` if `--keep-plan`).                                                                                                                                                                                                                                                                                                                                                        |

Every backport commit message must end with `Backport of <full sha>`.

**Dashboard content (`docs/index.html`)**

- Header: "Ferry — every fix, every supported release, proven".
- Metrics bar: fixes audited, missing security fixes found, ports proven (f2p+p2p), clean vs adapted vs escalated, Bobcoins used, manual baseline vs Ferry time.
- Matrix: rows = fixes, columns = release branches. Cell colors: green = proven, blue = clean cherry-pick proven, amber = escalated, grey = skip/not applicable.
- Click a cell → details: decision + policy citation, adaptations list, fail-before/pass-after evidence, changed files.
- Light/dark via `prefers-color-scheme`. Must work when opened as a local file and on GitHub Pages.

---

## 7. Bobcoin budget (40 total — check Bobalytics after every task)

| Task    | Mode         | Budget | If over budget                              |
| ------- | ------------ | ------ | ------------------------------------------- |
| T01     | Agent        | 3      | copy Appendices A–C by hand instead         |
| T02     | Agent        | 3      | simplify history; keep Section 4.3 true     |
| T03     | Agent        | 3      | —                                           |
| T04     | Agent        | 3      | write `report` HTML by hand from a template |
| T05     | Plan → Agent | 2      | —                                           |
| T06     | Ferry        | 8      | reduce to Fix A only                        |
| T07     | Agent        | 2      | skip polish                                 |
| T08     | Ferry        | 5      | record from T06 results                     |
| Reserve | —            | 11     | —                                           |

Cost-saving habits: new context window per task; mention only needed files with `@`; don't paste logs larger than needed; clean cherry-picks never call Bob.

---

## 8. Tasks

### T01 — Bob foundation

**Screenshot:** `bob_sessions/<team>_task01_foundation.png`

**[HUMAN] first:** create the public GitHub repo (MIT license), clone it, open it in Bob IDE, confirm the hackathon account in Settings → General, add `PLAN.md`.

**Prompt (Agent mode):**

```
Read @PLAN.md sections 2, 3 and Appendices A, B, C only.
1. Create AGENTS.md at the repo root: a 10-line project summary for Ferry plus the rules from section 2. Keep it under 25 lines.
2. Create .bob/custom_modes.yaml exactly from Appendix A. If my Bob version uses a different schema or tool-group names (especially for subagents), adapt it so the mode can read, edit only the allowed paths, run commands, and spawn subagents; tell me what you changed.
3. Create .bob/skills/backport-adapt/SKILL.md from Appendix B and .bob/rules/01-ferry.md from Appendix C.
4. Create .gitignore (workspace/, .ferry/, __pycache__/, .venv/), an empty metrics.json per section 5, and folders bob_sessions/, results/, docs/, slides/ with .gitkeep files.
Then tick T01 in section 0.
```

**Acceptance:** the "Ferry" mode appears in the mode picker; the skill is listed.

---

### T02 — Scenario generator + documents

**Screenshot:** `bob_sessions/<team>_task02_scenario.png`

**Prompt (Agent mode):**

```
Read @PLAN.md section 4 only.
Write scenario/build_scenario.py and scenario/make_docs.py exactly to that spec, plus ferry/__main__.py and ferry/cli.py with only the `scenario` command wired up.
Run `python -m ferry scenario`. Then prove section 4.3 by hand with plain git: for fixes A, B, C try `git cherry-pick -x` onto the branches marked "adapt"/"clean" in a throwaway worktree and report which conflict. Adjust the history until every outcome in 4.3 matches. Do not implement any other CLI command yet. Tick T02.
```

**Acceptance:** the 4.3 table matches reality; both documents open correctly.

**[HUMAN] right after T02 — manual baseline (important for your impact claim):**
Start a stopwatch. By hand, without AI, backport Fix A to `release/1.x` in a throwaway worktree: resolve the conflict, port the test, make the suite pass. Stop the watch. Write the minutes into `metrics.json` → `manual_baseline_minutes`. Then delete that worktree.

---

### T03 — CLI part 1: `audit` and `try`

**Screenshot:** `bob_sessions/<team>_task03_cli_audit_try.png`

**Prompt (Agent mode):**

```
Read @PLAN.md sections 5 and 6 (rows `audit`, `try`, `reset` only).
Implement ferry/gitops.py (thin subprocess wrappers, all git calls go through it), ferry/audit.py, ferry/mechanical.py, and wire `audit`, `try`, `reset` into ferry/cli.py.
For testing `try` before T05 exists, add `--plan-fixture` that uses a hard-coded plan matching section 4.3.
Add tests in tests/ for audit classification and branch-name sanitizing.
Run: python -m ferry reset && python -m ferry scenario && python -m ferry audit && python -m ferry try --plan-fixture
Show me the audit table and try.json. Tick T03.
```

**Acceptance:** audit shows the seeded gap (section 4.3 note); `try` gives `clean_pass` for C on 2.x and `conflict` for A (1.x, 2.x) and B (2.x).

---

### T04 — CLI part 2: `verify` and `report`

**Screenshot:** `bob_sessions/<team>_task04_cli_verify_report.png`

**Prompt (Agent mode):**

```
Read @PLAN.md sections 5 and 6 (rows `verify`, `report`, and "Dashboard content").
Implement ferry/verify.py and ferry/report.py and wire them into the CLI. verify must implement fail_before / pass_after / p2p exactly as specified, using a temporary worktree for fail_before, and must merge (not overwrite) results.json.
report must produce a single self-contained docs/index.html with the matrix and cell details, plus results/CHANGELOG-<branch>.md.
Run verify on the clean Fix C port and generate the report. Tick T04.
```

**Acceptance:** Fix C on 2.x shows `fail_before=true, pass_after=true, p2p=true`; `docs/index.html` opens locally and shows the matrix.

---

### T05 — Scope from documents (Plan mode)

**Screenshot:** `bob_sessions/<team>_task05_scope_from_docs.png`

**Prompt (Plan mode, then switch to Agent to write the file):**

```
Read @PLAN.md section 5 (plan.json contract) and @workspace/docs/SUPPORT_POLICY.pdf and @workspace/docs/SECURITY_ADVISORY.docx and @.ferry/audit.json.
For fixes A, B, C, D (section 4.2 subjects), decide for each of release/0.9, release/1.x, release/2.x: port, skip, or not_applicable.
- Use the policy and advisory for port/skip, citing the document and section for every decision.
- Use `git -C workspace/demo-ledger ls-tree` / `git log` to decide not_applicable (the changed code does not exist on that branch).
Write .ferry/plan.json. Show a table of decisions with citations. Tick T05.
```

**Acceptance:** decisions equal section 4.3; every decision has a citation.

Then run (no Bob): `python -m ferry try` (without the fixture), then `python -m ferry verify`.

---

### T06 — Adaptive ports with parallel subagents (Ferry mode)

**Screenshot:** `bob_sessions/<team>_task06_parallel_ports.png` (capture the parallel subagent panel too: `<team>_task06_subagents_panel.png`)

**Prompt (switch to the Ferry mode):**

```
Read @.ferry/try.json and @.ferry/plan.json.
For every entry with status "conflict" or "test_fail", spawn one subagent, in parallel, each using the backport-adapt skill for exactly one (fix, branch) pair and its worktree.
Each subagent must write .ferry/ports/<short>__<branch>.json and must not finish as "ported" unless `python -m ferry verify --fix <sha> --branch <branch>` passes.
When all subagents return, run `python -m ferry verify` and `python -m ferry report`, and give me a 5-line summary: ported, escalated, adaptations found. Tick T06.
```

**Acceptance:** A on 1.x and 2.x and B on 2.x are `f2p=true, p2p=true`, or honestly escalated with a reason.

If a port stays red after two runs: tighten the skill (Appendix B) with the specific missing step, then retry once. If it still fails, keep it as the escalation example for the demo.

---

### T07 — Dashboard polish + GitHub Pages

**Screenshot:** `bob_sessions/<team>_task07_dashboard.png`

**Prompt (Agent mode):**

```
Read @PLAN.md section 6 "Dashboard content" and @ferry/report.py.
Polish docs/index.html: clear metrics bar, readable matrix on mobile (horizontal scroll inside its own container), cell details panel, legend, and a short "How Ferry works" strip (audit → scope → try → adapt → verify → report). Keep it one self-contained file, no external requests. Regenerate it. Tick T07.
```

**[HUMAN]:** fill `bobcoins_by_task` in `metrics.json` from your task summaries, run `python -m ferry report`, commit, push, then GitHub → Settings → Pages → deploy from branch `main`, folder `/docs`. Open the URL in an incognito window. This is your **Application URL**.

---

### T08 — Final clean end-to-end run (record this)

**Screenshot:** `bob_sessions/<team>_task08_final_run.png`

**[HUMAN]:** start screen recording, then run:

```
python -m ferry reset --keep-plan
python -m ferry scenario
python -m ferry audit
python -m ferry try
```

Then paste the T06 prompt again in the Ferry mode (show the subagent panel), then:

```
python -m ferry verify
python -m ferry report
```

Open `docs/index.html`. Copy `.ferry/` into `results/` (report does this), commit and push.

---

## 9. Human submission steps (no Bob)

**H1 — Screenshots.** Every team member: Bob panel → Tasks → open each task → click the task header → screenshot the consumption summary → save as `bob_sessions/<team>_taskNN_<desc>.png`. Check no keys/credentials are visible.

**H2 — README.md.** One-line pitch, GIF of the dashboard, video link, Pages link, quick start (`pip install -r requirements.txt`, then the T08 commands), how Bob was used (link to `.bob/`), results table, MIT license.

**H3 — STATEMENTS.md** (each ≤500 words — count them):

- _Problem & Solution:_ the backport problem and exposure window; why current bots stop at conflicts; PortGPT is research-only; how Ferry works; your measured results (manual baseline vs Ferry, ports proven, coins per port, zero coins for clean ports).
- _IBM Bob Usage:_ custom Ferry mode, backport-adapt skill, AGENTS.md + rules, Plan mode reading the PDF/DOCX with citations, parallel subagents per branch, verify-gated success, Bobcoin strategy with real numbers, which files Bob wrote.

**H4 — Video (≤3:00, ≥90 s live)**

| Time      | Content                                                                                                         |
| --------- | --------------------------------------------------------------------------------------------------------------- |
| 0:00–0:20 | Hook: `ferry audit` shows a security fix missing from release branches                                          |
| 0:20–0:35 | Problem: bots only do clean cherry-picks; conflicts go to humans                                                |
| 0:35–2:15 | LIVE: scope with citations → try (clean vs conflict) → Ferry mode subagent panel → verify red→green → dashboard |
| 2:15–2:45 | Impact numbers from metrics.json                                                                                |
| 2:45–3:00 | How Bob was used, close                                                                                         |

**H5 — Slides (8) → `slides/ferry.pdf`.** Hook · Problem · Why current tools fail · How Ferry works · Live results matrix · Impact metrics · IBM Bob usage · Next steps (GitHub Action running `audit` on every merge; real-project trials).

**H6 — Cover image** (16:9: green matrix screenshot + "Ferry" wordmark) and the lablab form: title, short description, long description, both statements, tags (IBM Bob, Python, Git, Developer Tools, Application Maintenance, Security, Release Management), repo URL, platform = Web (GitHub Pages), application URL, video, slides. Submit by 5:00 PM GST.

---

## Appendix A — `.bob/custom_modes.yaml`

```yaml
customModes:
  - slug: ferry
    name: "Ferry"
    roleDefinition: >-
      You are Ferry, a careful backport engineer. You carry a fix from main into
      older release branches whose code has diverged, adapt it with minimal
      changes, port its regression test, and prove the result with ferry verify.
    whenToUse: >-
      Use when a fix must be backported to release branches and a plain
      cherry-pick conflicted or failed tests.
    customInstructions: >-
      Work only inside workspace/worktrees/** and .ferry/ports/**. Never modify
      the main branch. Follow the backport-adapt skill for every port. Prefer
      the smallest change that preserves the fix's intent on the older code.
      Never report "ported" unless `python -m ferry verify --fix <sha>
      --branch <branch>` exits 0. After 3 failed attempts stop and write an
      escalation with the exact blocker. Every backport commit message ends
      with "Backport of <full sha>".
    groups:
      - read
      - - edit
        - fileRegex: (^|/)(workspace/worktrees/|\.ferry/ports/)
          description: Backport worktrees and port result files only
      - execute
      - subagent
```

_Note for Bob (T01): if subagent spawning needs an extra tool group or an `allowedSubagents` field in this Bob version, add it._

---

## Appendix B — `.bob/skills/backport-adapt/SKILL.md`

```markdown
---
name: backport-adapt
description: Adapt one fix commit from main onto one older release branch whose code has diverged, port its regression test, and prove it with ferry verify.
---

# backport-adapt

Input: one (fix sha, release branch) pair and its worktree path from .ferry/try.json.

1. Understand the fix: `git -C workspace/demo-ledger show <sha>`. Name the intent in one sentence and list the regression test(s) it adds.
2. Locate each changed symbol on the target branch (run in the worktree):
   - `git log --follow --name-status -- <path>` to find moved files
   - `git log -S "<symbol>" --oneline` to find renames
   - `grep -rn "<symbol or distinctive line>" ledger/`
     Record every rename or move you find.
3. Apply the fix by hand to the equivalent code on the target branch. Keep the target branch's own signatures and style. Do not bring in unrelated main-branch changes.
4. Port the regression test: adapt imports, function names and signatures to the target branch. Do not weaken assertions.
5. Commit in the worktree on the backport branch with message: `<original subject> [<branch>]` + blank line + `Backport of <full sha>`.
6. Run `python -m ferry verify --fix <sha> --branch <branch>`.
   - Pass → write the port JSON with status "ported".
   - Fail → read the failure, fix, amend the commit, retry. Maximum 3 attempts.
   - Still failing → `git reset --hard <release branch head>` in the worktree and write status "escalated" with the exact blocker.
7. Write `.ferry/ports/<short>__<sanitized-branch>.json` per the contract in PLAN.md section 5, then return a 3-line summary.
```

---

## Appendix C — `.bob/rules/01-ferry.md`

```markdown
- This repo is Ferry: a backporting tool. The plan is in PLAN.md; read only the sections a task names.
- Mechanical work belongs in Python scripts under ferry/; do not simulate it in chat.
- Never edit the main branch of workspace/demo-ledger.
- A port is successful only if `python -m ferry verify` passes for it.
- Keep answers short: what changed, what was run, the result.
```

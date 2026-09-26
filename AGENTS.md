# Ferry — AGENTS.md

Ferry carries a bug or security fix from `main` into every supported release branch, adapts it
where the code has diverged, and proves each port with tests.

**Pipeline:** audit → scope → try → adapt → verify → report

- `audit` – find fixes on main that are missing from release branches
- `scope` – decide port / skip / not_applicable per branch using policy documents
- `try` – attempt a clean cherry-pick; flag conflicts
- `adapt` – resolve conflicts with minimal changes, port the regression test
- `verify` – prove fail_before / pass_after / full-suite pass
- `report` – produce the dashboard and changelogs

## Rules (apply to every task)

1. Keep changes minimal and scoped to the task. Do not refactor unrelated files.
2. Deterministic logic (git, tests, JSON, HTML) goes in Python scripts, never in chat reasoning.
3. Python 3.10+, standard library + `pytest`, `reportlab`, `python-docx` only. No web frameworks.
4. Never edit the `main` branch of the demo repo. All port edits happen in `workspace/worktrees/**`.
5. Never claim a port succeeded unless `python -m ferry verify` passes for it.
6. After each task: run the acceptance checks, tick the box in Section 0, and summarize in 5 lines.
7. Do not read `workspace/` unless the task needs it. Do not re-read PLAN.md in full; read only the sections named in the task.

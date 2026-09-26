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
   - Pass -> write the port JSON with status "ported".
   - Fail -> read the failure, fix, amend the commit, retry. Maximum 3 attempts.
   - Still failing -> `git reset --hard <release branch head>` in the worktree and write status "escalated" with the exact blocker.
7. Write `.ferry/ports/<short>__<sanitized-branch>.json` per the contract in PLAN.md section 5, then return a 3-line summary.

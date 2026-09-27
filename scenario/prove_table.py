"""
prove_table.py – prove section 4.3 by attempting cherry-picks in throwaway worktrees.

Prints a results table and exits non-zero if any outcome differs from spec.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "workspace" / "demo-ledger"
WORKTREES_DIR = REPO_ROOT / "workspace" / "worktrees-proof"

# Expected outcomes per section 4.3
# True = conflicts, False = clean
EXPECTED = {
    # (fix_subject_key, branch): conflicts?
    ("A", "release/1.x"): True,   # adapt
    ("A", "release/2.x"): True,   # adapt
    ("B", "release/2.x"): True,   # adapt
    ("C", "release/2.x"): False,  # clean
}


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print(f"  git {' '.join(args)} => rc={result.returncode}")
        print("  STDERR:", result.stderr[:400])
    return result


def _remove_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def get_fix_shas() -> dict[str, str]:
    """Return {fix_label: sha} for A, B, C, D from main log."""
    result = git(["log", "--oneline", "main"], cwd=DEMO)
    shas: dict[str, str] = {}
    subjects = {
        "A": "fix(security): prevent path traversal",
        "B": "fix: use banker's rounding",
        "C": "fix: correct typo in invoice header",
        "D": "fix: cap discounts",
    }
    for line in result.stdout.splitlines():
        sha, _, msg = line.partition(" ")
        for label, needle in subjects.items():
            if needle.lower() in msg.lower():
                shas[label] = sha
    return shas


def try_cherry_pick(fix_label: str, fix_sha: str, branch: str) -> bool:
    """
    Return True if cherry-pick conflicts, False if clean.
    Always aborts and removes the worktree afterward.
    """
    safe = branch.replace("/", "-")
    wt = WORKTREES_DIR / f"proof-{fix_label}-{safe}"
    if wt.exists():
        git(["worktree", "remove", "--force", str(wt)], cwd=DEMO, check=False)
        shutil.rmtree(str(wt), onerror=_remove_readonly)

    # Create worktree on the release branch
    git(["worktree", "add", str(wt), branch], cwd=DEMO)

    # Attempt cherry-pick
    result = git(["cherry-pick", "-x", fix_sha], cwd=wt, check=False)
    conflicts = result.returncode != 0

    # Clean up
    if conflicts:
        git(["cherry-pick", "--abort"], cwd=wt, check=False)
    else:
        git(["reset", "--hard", f"HEAD~1"], cwd=wt, check=False)

    git(["worktree", "remove", "--force", str(wt)], cwd=DEMO, check=False)
    if wt.exists():
        shutil.rmtree(str(wt), onerror=_remove_readonly)

    return conflicts


def main() -> None:
    # Clean up old proof worktrees
    if WORKTREES_DIR.exists():
        shutil.rmtree(str(WORKTREES_DIR), onerror=_remove_readonly)
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)

    shas = get_fix_shas()
    print(f"Fix SHAs: { {k: v for k, v in shas.items()} }")
    print()

    # Prune stale worktree refs
    git(["worktree", "prune"], cwd=DEMO)

    results: dict[tuple[str, str], bool] = {}
    for (fix, branch), expected_conflict in EXPECTED.items():
        sha = shas[fix]
        print(f"  Testing Fix {fix} on {branch} (sha={sha[:7]}) ...", end=" ", flush=True)
        actual_conflict = try_cherry_pick(fix, sha, branch)
        outcome = "CONFLICT" if actual_conflict else "CLEAN"
        expected_outcome = "CONFLICT" if expected_conflict else "CLEAN"
        match = "OK" if actual_conflict == expected_conflict else "MISMATCH"
        print(f"{outcome} (expected {expected_outcome}) {match}")
        results[(fix, branch)] = actual_conflict

    print()
    print("=" * 65)
    print(f"{'Fix':<5} {'Branch':<15} {'Actual':<10} {'Expected':<10} {'Match'}")
    print("-" * 65)
    all_ok = True
    for (fix, branch), actual_conflict in results.items():
        exp_conflict = EXPECTED[(fix, branch)]
        actual_s = "CONFLICT" if actual_conflict else "CLEAN"
        exp_s    = "CONFLICT" if exp_conflict else "CLEAN"
        ok = actual_conflict == exp_conflict
        if not ok:
            all_ok = False
        print(f"  {fix:<4} {branch:<15} {actual_s:<10} {exp_s:<10} {'OK' if ok else 'MISMATCH'}")
    print("=" * 65)
    if all_ok:
        print("All outcomes match section 4.3. OK")
    else:
        print("SOME OUTCOMES DO NOT MATCH. Adjust build_scenario.py and rerun.")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""ferry/mechanical.py – the `try` and `reset` commands."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path

from .gitops import git, run_pytest, sanitize_branch

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "workspace" / "demo-ledger"
WORKTREES_DIR = REPO_ROOT / "workspace" / "worktrees"
FERRY_DIR = REPO_ROOT / ".ferry"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _remove_readonly(func, path, _exc):
    """onerror handler for shutil.rmtree on Windows read-only files."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _worktree_name(short: str, branch: str) -> str:
    return f"{short}__{sanitize_branch(branch)}"


def _backport_branch(short: str, branch: str) -> str:
    return f"backport/{short}/{sanitize_branch(branch)}"


def _parse_conflicts(output: str) -> list[dict]:
    """Parse git's conflict output for conflicted files and types."""
    conflicts: list[dict] = []
    seen: set[str] = set()
    for line in output.splitlines():
        # "CONFLICT (content): Merge conflict in path/to/file"
        m = re.search(r"CONFLICT \(([^)]+)\):.*?(?:in|between|of) (.+)$", line)
        if m:
            ctype = m.group(1).strip()
            path = m.group(2).strip()
            key = (ctype, path)
            if key not in seen:
                seen.add(key)
                conflicts.append({"type": ctype, "file": path})
            continue
        # Fallback: any "CONFLICT" line
        if "CONFLICT" in line and line not in seen:
            seen.add(line)
            conflicts.append({"type": "unknown", "file": line.strip()})
    return conflicts


# ---------------------------------------------------------------------------
# Hard-coded plan fixture (section 4.3)
# ---------------------------------------------------------------------------
_FIXTURE_SUBJECTS = {
    "A": "fix(security): prevent path traversal in invoice export",
    "B": "fix: use banker's rounding",
    "C": "fix: correct typo in invoice header",
}
_FIXTURE_PORTS = [
    ("A", "release/1.x"),
    ("A", "release/2.x"),
    ("B", "release/2.x"),
    ("C", "release/2.x"),
]


def _get_fixture_plan(demo: Path) -> list[dict]:
    """Build the plan fixture from the demo repo's main log."""
    log = git(["log", "main", "--format=%H %s"], cwd=demo)
    sha_map: dict[str, str] = {}
    for line in log.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, subject = line.partition(" ")
        for label, needle in _FIXTURE_SUBJECTS.items():
            if subject.startswith(needle):
                sha_map[label] = sha

    missing = [k for k in _FIXTURE_SUBJECTS if k not in sha_map]
    if missing:
        raise RuntimeError(
            f"Could not find fixture commits for fix(es): {missing}\n"
            f"Run `ferry scenario` first."
        )

    targets: list[dict] = []
    for label, branch in _FIXTURE_PORTS:
        sha = sha_map[label]
        targets.append(
            {
                "sha": sha,
                "subject": next(
                    v for k, v in _FIXTURE_SUBJECTS.items() if k == label
                ),
                "branch": branch,
                "decision": "port",
            }
        )
    return targets


# ---------------------------------------------------------------------------
# try command
# ---------------------------------------------------------------------------

def _do_cherry_pick(target: dict, demo: Path) -> dict:
    """Cherry-pick one target; return result dict for try.json."""
    sha = target["sha"]
    branch = target["branch"]
    short = sha[:7]
    wt_name = _worktree_name(short, branch)
    wt_path = WORKTREES_DIR / wt_name
    bp_branch = _backport_branch(short, branch)

    t0 = time.monotonic()

    # Remove any existing worktree
    if wt_path.exists():
        git(["worktree", "remove", "--force", str(wt_path)], cwd=demo, check=False)
        shutil.rmtree(str(wt_path), onerror=_remove_readonly)

    # Delete old backport branch if present
    git(["branch", "-D", bp_branch], cwd=demo, check=False)

    # Create worktree on a new branch from the release branch
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
    git(
        ["worktree", "add", "-b", bp_branch, str(wt_path), branch],
        cwd=demo,
    )

    base: dict = {
        "sha": sha,
        "branch": branch,
        "worktree": str(wt_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "backport_branch": bp_branch,
        "conflicts": [],
        "seconds": 0.0,
    }

    # Cherry-pick
    cp_result = git(
        ["cherry-pick", "-x", sha],
        cwd=wt_path,
        check=False,
    )

    if cp_result.returncode != 0:
        combined = cp_result.stdout + cp_result.stderr
        # Detect "already present" (empty commit)
        if "nothing to commit" in combined or "nothing added to commit" in combined or "empty commit" in combined.lower():
            git(["cherry-pick", "--abort"], cwd=wt_path, check=False)
            base["status"] = "already_present"
        else:
            # Genuine conflict
            conflicts = _parse_conflicts(combined)
            git(["cherry-pick", "--abort"], cwd=wt_path, check=False)
            base["status"] = "conflict"
            base["conflicts"] = conflicts
        base["seconds"] = round(time.monotonic() - t0, 2)
        return base

    # Clean pick — amend commit message with Backport trailer
    log1 = git(["log", "-1", "--format=%B"], cwd=wt_path)
    orig_msg = log1.stdout.rstrip()
    new_msg = orig_msg + f"\n\nBackport of {sha}"
    git(["commit", "--amend", "-m", new_msg], cwd=wt_path)

    # Run pytest
    pytest_result = run_pytest(wt_path)
    base["seconds"] = round(time.monotonic() - t0, 2)
    base["status"] = "clean_pass" if pytest_result["exit_code"] == 0 else "test_fail"
    base["pytest"] = {
        "passed": pytest_result["passed"],
        "failed": pytest_result["failed"],
    }
    return base


def cmd_try(args) -> int:
    """Entry point for `ferry try [--plan-fixture]`."""
    if not DEMO.exists():
        print("ERROR: workspace/demo-ledger does not exist. Run `ferry scenario` first.",
              file=sys.stderr)
        return 1

    plan_path = FERRY_DIR / "plan.json"
    if getattr(args, "plan_fixture", False):
        print("==> Using hard-coded plan fixture (section 4.3) …")
        try:
            targets = _get_fixture_plan(DEMO)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    else:
        if not plan_path.exists():
            print("ERROR: .ferry/plan.json not found. Use --plan-fixture or run scope first.",
                  file=sys.stderr)
            return 1
        data = json.loads(plan_path.read_text(encoding="utf-8"))
        targets = []
        for fix in data.get("fixes", []):
            for t in fix.get("targets", []):
                if t.get("decision") == "port":
                    targets.append(
                        {
                            "sha": fix["sha"],
                            "subject": fix["subject"],
                            "branch": t["branch"],
                            "decision": "port",
                        }
                    )

    print(f"==> Running cherry-picks for {len(targets)} target(s) …\n")
    results: list[dict] = []
    for target in targets:
        short = target["sha"][:7]
        print(f"  {short}  {target['branch']} … ", end="", flush=True)
        entry = _do_cherry_pick(target, DEMO)
        print(entry["status"])
        results.append(entry)

    # Write try.json (minimal fields per contract + extras)
    FERRY_DIR.mkdir(exist_ok=True)
    try_entries = [
        {
            "sha": r["sha"],
            "branch": r["branch"],
            "status": r["status"],
            "worktree": r.get("worktree", ""),
            "backport_branch": r.get("backport_branch", ""),
            "conflicts": r.get("conflicts", []),
            "seconds": r.get("seconds", 0.0),
        }
        for r in results
    ]
    (FERRY_DIR / "try.json").write_text(
        json.dumps(try_entries, indent=2), encoding="utf-8"
    )
    print(f"\n    Written .ferry/try.json")

    _print_try_table(results)
    return 0


def _print_try_table(results: list[dict]) -> None:
    print()
    print(f"{'SHA':<7}  {'Branch':<15}  {'Status':<14}  {'Seconds':>7}")
    print("-" * 52)
    for r in results:
        sha7 = r["sha"][:7]
        branch = r["branch"][:15]
        status = r["status"]
        secs = r.get("seconds", 0.0)
        print(f"{sha7:<7}  {branch:<15}  {status:<14}  {secs:>7.2f}s")


# ---------------------------------------------------------------------------
# reset command
# ---------------------------------------------------------------------------

def cmd_reset(args) -> int:
    """Entry point for `ferry reset`."""
    keep_plan = getattr(args, "keep_plan", False)

    # 1. Remove all worktrees under workspace/worktrees
    if WORKTREES_DIR.exists():
        print(f"==> Removing worktrees at {WORKTREES_DIR} …")
        for wt in WORKTREES_DIR.iterdir():
            if wt.is_dir():
                try:
                    git(["worktree", "remove", "--force", str(wt)], cwd=DEMO, check=False)
                except Exception:
                    pass
        shutil.rmtree(str(WORKTREES_DIR), onerror=_remove_readonly)
        print("    Done.")
    else:
        print("==> workspace/worktrees: absent, nothing to remove.")

    # 2. git worktree prune
    if DEMO.exists():
        print("==> Running git worktree prune …")
        git(["worktree", "prune"], cwd=DEMO, check=False)

    # 3. Delete backport/* branches
    if DEMO.exists():
        print("==> Deleting backport/* branches …")
        br_result = git(
            ["branch", "--format=%(refname:short)"], cwd=DEMO, check=False
        )
        deleted = 0
        for b in br_result.stdout.splitlines():
            b = b.strip()
            if b.startswith("backport/"):
                git(["branch", "-D", b], cwd=DEMO, check=False)
                deleted += 1
        print(f"    Deleted {deleted} backport branch(es).")

    # 4. Delete .ferry/ (keep plan.json if --keep-plan)
    if FERRY_DIR.exists():
        if keep_plan and (FERRY_DIR / "plan.json").exists():
            plan_data = (FERRY_DIR / "plan.json").read_bytes()
            print(f"==> Deleting .ferry/ (keeping plan.json) …")
            shutil.rmtree(str(FERRY_DIR), onerror=_remove_readonly)
            FERRY_DIR.mkdir()
            (FERRY_DIR / "plan.json").write_bytes(plan_data)
        else:
            print(f"==> Deleting .ferry/ …")
            shutil.rmtree(str(FERRY_DIR), onerror=_remove_readonly)
        print("    Done.")
    else:
        print("==> .ferry/: absent, nothing to remove.")

    print("==> Reset complete.")
    return 0

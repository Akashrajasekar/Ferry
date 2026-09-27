"""ferry/verify.py – the `verify` command.

For each eligible port (clean_pass in try.json, or ported in ports/*.json):
  1. Identify regression test files touched by the backport commit.
  2. fail_before: temp worktree at release-branch head, inject only those test
     files, run pytest → must exit 1 (ran and failed). Any other exit code
     means fail_before=False, reason="test did not run cleanly before the fix".
  3. pass_after: run those test files on the backport worktree → must exit 0.
  4. p2p: full suite on backport worktree → must exit 0.
  5. Write/merge results into .ferry/results.json.
"""
from __future__ import annotations

import json
import os
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


def _backport_commit(wt_path: Path, bp_branch: str) -> str:
    """Return the SHA of the tip of the backport branch (i.e. the port commit)."""
    result = git(["rev-parse", bp_branch], cwd=DEMO)
    return result.stdout.strip()


def _test_files_in_commit(wt_path: Path, commit_sha: str) -> list[str]:
    """Return test files (under tests/) added or modified by commit_sha."""
    result = git(
        ["diff-tree", "--no-commit-id", "-r", "--name-only", "--diff-filter=AM",
         commit_sha],
        cwd=wt_path,
    )
    files = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if path.startswith("tests/") and path.endswith(".py"):
            files.append(path)
    return files


def _git_show_file(commit_sha: str, file_path: str, wt_path: Path) -> bytes:
    """Get file content from a specific commit."""
    result = git(
        ["show", f"{commit_sha}:{file_path}"],
        cwd=wt_path,
    )
    return result.stdout.encode("utf-8", errors="replace")


def _run_pytest_files(cwd: Path, files: list[str]) -> dict:
    """Run pytest on specific files only."""
    import subprocess
    import re

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + files,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    passed = 0
    failed = 0
    for line in (result.stdout + result.stderr).splitlines():
        m = re.search(r"(\d+) passed", line)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", line)
        if m:
            failed = int(m.group(1))

    return {
        "passed": passed,
        "failed": failed,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _check_fail_before(
    release_branch: str,
    test_files: list[str],
    commit_sha: str,  # backport commit to borrow test content from
    wt_path: Path,    # backport worktree (used to read test file content)
) -> tuple[bool, str]:
    """
    Create a temporary worktree at release_branch head, inject only the
    regression test files (from the backport commit), run pytest.

    Returns (fail_before: bool, reason: str).
    fail_before = True only if exit_code == 1.
    """
    tmp_name = f"_fb_{release_branch.replace('/', '-')}_{commit_sha[:7]}"
    tmp_path = WORKTREES_DIR / tmp_name

    # Clean up any leftover
    if tmp_path.exists():
        git(["worktree", "remove", "--force", str(tmp_path)], cwd=DEMO, check=False)
        shutil.rmtree(str(tmp_path), onerror=_remove_readonly)

    try:
        WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
        git(
            ["worktree", "add", "--detach", str(tmp_path), release_branch],
            cwd=DEMO,
        )

        # Inject only the test files from the backport commit
        for rel_file in test_files:
            content = _git_show_file(commit_sha, rel_file, wt_path)
            dest = tmp_path / rel_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

        # Run pytest on just those files
        r = _run_pytest_files(tmp_path, test_files)
        ec = r["exit_code"]

        if ec == 1:
            return True, ""
        else:
            return False, "test did not run cleanly before the fix"
    finally:
        # Always remove the temp worktree
        if tmp_path.exists():
            git(["worktree", "remove", "--force", str(tmp_path)], cwd=DEMO, check=False)
            shutil.rmtree(str(tmp_path), onerror=_remove_readonly)
        git(["worktree", "prune"], cwd=DEMO, check=False)


def _truncate_diff(text: str, max_lines: int = 400) -> str:
    lines = text.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return text
    return "".join(lines[:max_lines]) + f"\n... (truncated at {max_lines} lines)\n"


def _get_diffs(fix_sha: str, backport_commit: str, wt_path: Path) -> tuple[str, str]:
    """Return (fix_diff, backport_diff) each truncated to 400 lines."""
    # fix_diff: git show <fix_sha> but only source and test files
    show_fix = git(["show", fix_sha], cwd=DEMO, check=False)
    fix_diff = _truncate_diff(show_fix.stdout)

    # backport_diff: git show <backport_commit>
    show_bp = git(["show", backport_commit], cwd=wt_path, check=False)
    backport_diff = _truncate_diff(show_bp.stdout)

    return fix_diff, backport_diff


# ---------------------------------------------------------------------------
# Core verification logic
# ---------------------------------------------------------------------------

def verify_port(
    sha: str,
    branch: str,
    method: str,
    wt_path: Path,
    bp_branch: str,
) -> dict:
    """Verify one port; return a results.json entry."""
    t0 = time.monotonic()

    # Get the backport commit SHA
    bp_commit = _backport_commit(wt_path, bp_branch)

    # Find regression test files
    test_files = _test_files_in_commit(wt_path, bp_commit)

    result: dict = {
        "sha": sha,
        "branch": branch,
        "method": method,
        "f2p": False,
        "p2p": False,
        "fail_before": False,
        "fail_before_reason": "",
        "pass_after": False,
        "suite": {"passed": 0, "failed": 0},
        "seconds": 0.0,
    }

    if not test_files:
        result["fail_before_reason"] = "no regression test files found"
        result["seconds"] = round(time.monotonic() - t0, 2)
        return result

    # fail_before
    fail_before, fb_reason = _check_fail_before(branch, test_files, bp_commit, wt_path)
    result["fail_before"] = fail_before
    result["fail_before_reason"] = fb_reason

    # pass_after
    pa_result = _run_pytest_files(wt_path, test_files)
    pass_after = pa_result["exit_code"] == 0
    result["pass_after"] = pass_after

    # f2p
    result["f2p"] = fail_before and pass_after

    # p2p: full suite
    p2p_result = run_pytest(wt_path)
    result["p2p"] = p2p_result["exit_code"] == 0
    result["suite"] = {
        "passed": p2p_result["passed"],
        "failed": p2p_result["failed"],
    }

    # Diffs
    fix_diff, bp_diff = _get_diffs(sha, bp_commit, wt_path)
    result["fix_diff"] = fix_diff
    result["backport_diff"] = bp_diff

    result["seconds"] = round(time.monotonic() - t0, 2)
    return result


# ---------------------------------------------------------------------------
# Results merging
# ---------------------------------------------------------------------------

def _load_results() -> list[dict]:
    p = FERRY_DIR / "results.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def _save_results(entries: list[dict]) -> None:
    FERRY_DIR.mkdir(exist_ok=True)
    (FERRY_DIR / "results.json").write_text(
        json.dumps(entries, indent=2), encoding="utf-8"
    )


def _merge_results(existing: list[dict], new_entries: list[dict]) -> list[dict]:
    """Update matching (sha, branch) entries; append new ones."""
    index: dict[tuple, int] = {
        (e["sha"], e["branch"]): i for i, e in enumerate(existing)
    }
    result = list(existing)
    for entry in new_entries:
        key = (entry["sha"], entry["branch"])
        if key in index:
            result[index[key]] = entry
        else:
            result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def cmd_verify(args) -> int:
    """Entry point for `ferry verify [--fix SHA] [--branch B]`."""
    if not DEMO.exists():
        print("ERROR: workspace/demo-ledger not found. Run ferry scenario first.",
              file=sys.stderr)
        return 1

    fix_filter = getattr(args, "fix", None)
    branch_filter = getattr(args, "branch", None)

    # Load try.json
    try_path = FERRY_DIR / "try.json"
    try_entries: list[dict] = []
    if try_path.exists():
        try_entries = json.loads(try_path.read_text(encoding="utf-8"))

    # Load ports/*.json
    ports_dir = FERRY_DIR / "ports"
    port_files: list[dict] = []
    if ports_dir.exists():
        for pf in ports_dir.glob("*.json"):
            try:
                port_files.append(json.loads(pf.read_text(encoding="utf-8")))
            except Exception:
                pass

    # Load plan.json for skip/not_applicable entries
    plan_path = FERRY_DIR / "plan.json"
    plan_data: dict = {}
    if plan_path.exists():
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))

    # Build set of (sha, branch) that have a ported port file
    ported_set: dict[tuple, dict] = {}
    for pf in port_files:
        if pf.get("status") == "ported":
            key = (pf["sha"], pf["branch"])
            ported_set[key] = pf

    # Collect eligible ports
    eligible: list[dict] = []  # {sha, branch, method, wt_path, bp_branch}

    seen: set[tuple] = set()

    for te in try_entries:
        sha = te["sha"]
        branch = te["branch"]
        key = (sha, branch)

        if fix_filter and not sha.startswith(fix_filter):
            continue
        if branch_filter and branch != branch_filter:
            continue

        if te.get("status") == "clean_pass":
            wt_name = Path(te.get("worktree", "")).name
            wt_path = REPO_ROOT / te.get("worktree", "")
            bp_branch = te.get("backport_branch", "")
            if not wt_path.exists():
                print(f"  WARN: worktree missing for {sha[:7]} {branch}, skipping")
                continue
            eligible.append({
                "sha": sha,
                "branch": branch,
                "method": "clean",
                "wt_path": wt_path,
                "bp_branch": bp_branch,
            })
            seen.add(key)
        elif te.get("status") == "conflict":
            # Check if there's a ported file for it
            if key in ported_set:
                # Will be handled below via port_files
                pass
            else:
                # Record as pending (not checked)
                pass  # collected below from plan.json or recorded separately

    # Add adapted ports (ported port files not already in clean_pass)
    for key, pf in ported_set.items():
        sha, branch = key
        if key in seen:
            continue
        if fix_filter and not sha.startswith(fix_filter):
            continue
        if branch_filter and branch != branch_filter:
            continue

        short = sha[:7]
        san = sanitize_branch(branch)
        wt_name = f"{short}__{san}"
        wt_path = WORKTREES_DIR / wt_name
        bp_branch = f"backport/{short}/{san}"

        if not wt_path.exists():
            print(f"  WARN: worktree missing for adapted port {sha[:7]} {branch}, skipping")
            continue

        eligible.append({
            "sha": sha,
            "branch": branch,
            "method": "adapted",
            "wt_path": wt_path,
            "bp_branch": bp_branch,
        })
        seen.add(key)

    # Run verification
    new_entries: list[dict] = []
    any_failure = False

    for port in eligible:
        sha = port["sha"]
        branch = port["branch"]
        print(f"  Verifying {sha[:7]}  {branch} ({port['method']}) ...", flush=True)
        try:
            entry = verify_port(
                sha=sha,
                branch=branch,
                method=port["method"],
                wt_path=port["wt_path"],
                bp_branch=port["bp_branch"],
            )
        except Exception as exc:
            print(f"    ERROR: {exc}", file=sys.stderr)
            entry = {
                "sha": sha,
                "branch": branch,
                "method": port["method"],
                "f2p": False,
                "p2p": False,
                "fail_before": False,
                "fail_before_reason": str(exc),
                "pass_after": False,
                "suite": {"passed": 0, "failed": 0},
                "seconds": 0.0,
            }
        new_entries.append(entry)
        if not entry["f2p"] or not entry["p2p"]:
            any_failure = True

    # Add pending entries (conflict with no ported file)
    for te in try_entries:
        sha = te["sha"]
        branch = te["branch"]
        key = (sha, branch)
        if te.get("status") == "conflict" and key not in ported_set and key not in seen:
            if fix_filter and not sha.startswith(fix_filter):
                continue
            if branch_filter and branch != branch_filter:
                continue
            new_entries.append({
                "sha": sha,
                "branch": branch,
                "method": "pending",
                "f2p": False,
                "p2p": False,
                "fail_before": False,
                "pass_after": False,
                "suite": {"passed": 0, "failed": 0},
                "seconds": 0.0,
            })

    # Add skip/not_applicable from plan.json
    if plan_data:
        for fix in plan_data.get("fixes", []):
            psha = fix["sha"]
            for t in fix.get("targets", []):
                decision = t.get("decision", "")
                pbranch = t.get("branch", "")
                key = (psha, pbranch)
                if decision in ("skip", "not_applicable") and key not in seen:
                    if fix_filter and not psha.startswith(fix_filter):
                        continue
                    if branch_filter and pbranch != branch_filter:
                        continue
                    new_entries.append({
                        "sha": psha,
                        "branch": pbranch,
                        "method": decision,
                        "reason": t.get("reason", ""),
                        "citation": t.get("citation", {}),
                        "f2p": False,
                        "p2p": False,
                        "fail_before": False,
                        "pass_after": False,
                        "suite": {"passed": 0, "failed": 0},
                        "seconds": 0.0,
                    })

    # Merge into results.json
    existing = _load_results()
    merged = _merge_results(existing, new_entries)
    _save_results(merged)
    print(f"\n    Written .ferry/results.json ({len(merged)} entries)")

    # Print ASCII table
    _print_verify_table(new_entries)

    return 1 if any_failure else 0


def _print_verify_table(entries: list[dict]) -> None:
    rows = [e for e in entries if e["method"] not in ("pending", "skip", "not_applicable")]
    if not rows:
        print("\n  No ports verified.")
        return
    print()
    print(f"{'SHA':<7}  {'Branch':<15}  {'Method':<9}  {'FB':<5}  {'PA':<5}  {'P2P':<5}  {'Secs':>6}")
    print("-" * 65)
    for e in rows:
        sha7 = e["sha"][:7]
        branch = e["branch"][:15]
        method = e["method"][:9]
        fb = "true" if e.get("fail_before") else "false"
        pa = "true" if e.get("pass_after") else "false"
        p2p = "true" if e.get("p2p") else "false"
        secs = e.get("seconds", 0.0)
        print(f"{sha7:<7}  {branch:<15}  {method:<9}  {fb:<5}  {pa:<5}  {p2p:<5}  {secs:>6.2f}s")

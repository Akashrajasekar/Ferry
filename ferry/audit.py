"""ferry/audit.py – the `audit` command.

Finds all fix commits on main that are missing from release branches.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .gitops import git, sanitize_branch

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "workspace" / "demo-ledger"
FERRY_DIR = REPO_ROOT / ".ferry"


def _fix_commits(demo: Path) -> list[dict]:
    """Return all commits on main whose subject starts with 'fix'."""
    result = git(
        ["log", "main", "--format=%H %s"],
        cwd=demo,
    )
    commits = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, _, subject = line.partition(" ")
        if subject.lower().startswith("fix"):
            kind = "security" if subject.startswith("fix(security)") else "fix"
            commits.append({"sha": sha, "subject": subject, "kind": kind})
    return commits


def _release_branches(demo: Path) -> list[str]:
    """Return list of release/* branch names (sorted)."""
    result = git(["branch", "--format=%(refname:short)"], cwd=demo)
    branches = [
        b.strip()
        for b in result.stdout.splitlines()
        if b.strip().startswith("release/")
    ]
    return sorted(branches)


def _backport_shas_on_branch(demo: Path, branch: str, merge_base: str) -> list[tuple[str, str]]:
    """Return (backport_commit_sha, original_sha) pairs on branch after merge-base.

    backport_commit_sha is the SHA of the commit on the release branch that
    contains the trailer; original_sha is the SHA it references.
    """
    # Use a separator line containing the SHA so we can parse it reliably.
    # Format: one line of "COMMIT:<sha>", then the body (%B), then a blank
    # line (git adds one between entries when %B is used).
    result = git(
        ["log", f"{merge_base}..{branch}", "--format=COMMIT:%H%n%B"],
        cwd=demo,
    )
    found: list[tuple[str, str]] = []
    current_commit = ""
    for line in result.stdout.splitlines():
        if line.startswith("COMMIT:"):
            current_commit = line[7:].strip()
            continue
        # "(cherry picked from commit <sha>)"
        m = re.search(r"\(cherry picked from commit ([0-9a-f]+)\)", line)
        if m and current_commit:
            found.append((current_commit, m.group(1)))
        # "Backport of <sha>"
        m = re.search(r"Backport of ([0-9a-f]+)", line)
        if m and current_commit:
            found.append((current_commit, m.group(1)))
    return found


def _classify(demo: Path, sha: str, branch: str, backported_pairs: list[tuple[str, str]]) -> str:
    """Classify a fix commit for one branch."""
    # a) backported: check trailer SHAs — report the backport commit SHA
    for bp_commit_sha, orig_sha in backported_pairs:
        if orig_sha.startswith(sha) or sha.startswith(orig_sha):
            return f"backported:{bp_commit_sha[:7]}"

    # b) present: git merge-base --is-ancestor OR git cherry shows "-"
    anc = git(
        ["merge-base", "--is-ancestor", sha, branch],
        cwd=demo,
        check=False,
    )
    if anc.returncode == 0:
        return "present"

    # git cherry: lines starting with "-" mean patch is already applied
    cherry = git(
        ["cherry", branch, sha],
        cwd=demo,
        check=False,
    )
    if cherry.returncode == 0:
        for line in cherry.stdout.splitlines():
            if line.startswith("- "):
                return "present"

    return "missing"


def run_audit(demo: Path = DEMO) -> list[dict]:
    """Run audit logic; return the audit entries list."""
    commits = _fix_commits(demo)
    branches = _release_branches(demo)

    # Pre-compute backported SHAs per branch
    branch_backports: dict[str, list[str]] = {}
    for branch in branches:
        mb_result = git(
            ["merge-base", "main", branch],
            cwd=demo,
        )
        merge_base = mb_result.stdout.strip()
        branch_backports[branch] = _backport_shas_on_branch(demo, branch, merge_base)

    entries: list[dict] = []
    for commit in commits:
        sha = commit["sha"]
        branch_statuses: dict[str, str] = {}
        for branch in branches:
            branch_statuses[branch] = _classify(
                demo, sha, branch, branch_backports[branch]
            )
        entries.append(
            {
                "sha": sha,
                "subject": commit["subject"],
                "kind": commit["kind"],
                "branches": branch_statuses,
            }
        )
    return entries


def print_table(entries: list[dict], branches: list[str]) -> None:
    """Print ASCII audit table."""
    short = 7
    subj_w = 50
    col_w = max(len(b) for b in branches) + 2

    header = f"{'SHA':<{short}}  {'Subject':<{subj_w}}"
    for b in branches:
        header += f"  {b:<{col_w}}"
    print(header)
    print("-" * len(header))

    for e in entries:
        sha7 = e["sha"][:short]
        subj = e["subject"][:subj_w]
        row = f"{sha7:<{short}}  {subj:<{subj_w}}"
        for b in branches:
            status = e["branches"].get(b, "?")
            row += f"  {status:<{col_w}}"
        print(row)

    print()
    # Summary line per branch
    for b in branches:
        missing_sec = sum(
            1
            for e in entries
            if e["kind"] == "security" and e["branches"].get(b) == "missing"
        )
        print(f"  {b}: {missing_sec} missing security fix(es)")


def cmd_audit(_args) -> int:
    """Entry point for `ferry audit`."""
    if not DEMO.exists():
        print("ERROR: workspace/demo-ledger does not exist. Run `ferry scenario` first.",
              file=sys.stderr)
        return 1

    print("==> Auditing fix commits on main …")
    entries = run_audit()
    branches = sorted({b for e in entries for b in e["branches"]})

    FERRY_DIR.mkdir(exist_ok=True)
    audit_path = FERRY_DIR / "audit.json"
    audit_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"    Written {audit_path}")
    print()

    print_table(entries, branches)
    return 0

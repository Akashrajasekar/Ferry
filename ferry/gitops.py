"""ferry/gitops.py – thin subprocess wrappers for git and pytest.

Every git call in the project goes through this module.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path


def git(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    """Run git with *args* in *cwd*.

    Always passes args as a list (no shell=True).
    Raises RuntimeError with git's stderr on non-zero exit when check=True.
    """
    cmd = ["git"] + args
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={result.returncode})\n{stderr}"
        )
    return result


def run_pytest(cwd: Path) -> dict:
    """Run pytest -q -p no:cacheprovider in *cwd*.

    Returns {"passed": int, "failed": int, "exit_code": int}.
    """
    t0 = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    elapsed = time.monotonic() - t0

    passed = 0
    failed = 0
    # Parse summary line like "3 passed, 1 failed in 0.12s"
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
        "seconds": round(elapsed, 2),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def sanitize_branch(branch: str) -> str:
    """Sanitize a branch name for use in file paths and branch names.

    release/1.x  ->  release-1.x
    """
    return branch.replace("/", "-")

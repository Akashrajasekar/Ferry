"""tests/test_verify_fail_before.py

Verify that _check_fail_before returns (False, reason) when the injected
regression test file has an import error (pytest exit code 2, not 1).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args}: {result.stderr.strip()}")
    return result


def _make_tiny_repo(base: Path) -> tuple[Path, str]:
    """Create a minimal git repo with one commit that adds a broken test file.

    Returns (repo_path, commit_sha_of_broken_test_commit).
    """
    repo = base / "tiny-repo"
    repo.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": "2024-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2024-01-01T00:00:00+00:00",
    }

    def git(args, cwd=repo, check=True):
        r = subprocess.run(
            ["git"] + args, cwd=str(cwd),
            capture_output=True, text=True, env=env,
        )
        if check and r.returncode != 0:
            raise RuntimeError(f"git {args}: {r.stderr.strip()}")
        return r

    git(["init", str(repo)], cwd=base)
    git(["config", "user.email", "test@example.com"])
    git(["config", "user.name", "Test"])

    # Initial commit: empty ledger
    (repo / "ledger").mkdir()
    (repo / "ledger" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "init"])
    # Mark release branch
    git(["branch", "release/1.x"])

    # Second commit: add a test with a broken import (import error → exit 2)
    broken_test = (
        "import nonexistent_module_xyz  # this will cause an ImportError\n"
        "\n"
        "def test_something():\n"
        "    assert False\n"
    )
    (repo / "tests" / "test_broken.py").write_text(broken_test, encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "fix: add broken test\n\nBackport of deadbeef"])

    sha = git(["rev-parse", "HEAD"]).stdout.strip()
    return repo, sha


@pytest.fixture()
def tiny_repo(tmp_path):
    return _make_tiny_repo(tmp_path)


def test_fail_before_false_on_import_error(tmp_path, monkeypatch):
    """_check_fail_before must return (False, reason) when pytest exits with
    code 2 (collection/import error), not 1 (tests ran and failed)."""

    repo, bp_commit = _make_tiny_repo(tmp_path)

    # Patch WORKTREES_DIR so temp worktrees land inside tmp_path
    import ferry.verify as vmod
    monkeypatch.setattr(vmod, "DEMO", repo)
    monkeypatch.setattr(vmod, "WORKTREES_DIR", tmp_path / "worktrees")

    # The backport commit contains tests/test_broken.py
    # We run _check_fail_before against release/1.x (the release branch head)
    fail_before, reason = vmod._check_fail_before(
        release_branch="release/1.x",
        test_files=["tests/test_broken.py"],
        commit_sha=bp_commit,   # borrow test content from here
        wt_path=repo,
    )

    assert fail_before is False, (
        "fail_before must be False when pytest exits with code 2 (import error), "
        f"but got {fail_before!r}"
    )
    assert reason == "test did not run cleanly before the fix", (
        f"Unexpected reason: {reason!r}"
    )

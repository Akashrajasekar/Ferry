"""tests/test_review_flags.py

Tests for:
  - existing_test_modified detection (scoped to modified function names)
  - test_passes_without_fix detection (only when pytest.raises present)
  - preserves_behaviour classification (passes before+after, no pytest.raises → no flag)
using small throwaway git repos in tmp_path.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared git helper
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": "2024-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2024-01-01T00:00:00+00:00",
    }
    result = subprocess.run(
        ["git"] + args, cwd=str(cwd),
        capture_output=True, text=True, env=env,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {args}: {result.stderr.strip()}")
    return result


# ---------------------------------------------------------------------------
# Test: existing_test_modified — includes modified function names
# ---------------------------------------------------------------------------

def _make_repo_with_existing_test_modified(base: Path) -> tuple[Path, str]:
    """
    Repo layout:
    - Initial commit + release/1.x: tests/test_money.py has test_basic (body A)
    - Backport commit: modifies test_basic (body B) and adds test_new_func (new)
      and adds tests/test_extra.py (entirely new file)
    """
    repo = base / "repo-etm"
    repo.mkdir(parents=True, exist_ok=True)

    def git(args, cwd=repo, check=True):
        return _git(args, cwd=cwd, check=check)

    git(["init", str(repo)], cwd=base)
    git(["config", "user.email", "test@example.com"])
    git(["config", "user.name", "Test"])

    (repo / "ledger").mkdir()
    (repo / "ledger" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
    # test_basic exists on the branch
    (repo / "tests" / "test_money.py").write_text(
        "def test_basic():\n    assert 1 == 1\n",
        encoding="utf-8",
    )
    git(["add", "."])
    git(["commit", "-m", "initial"])
    git(["branch", "release/1.x"])

    # Backport commit: modifies test_basic body + adds test_new_func + new file
    (repo / "tests" / "test_money.py").write_text(
        "def test_basic():\n    assert 2 == 2  # changed\n\n"
        "def test_new_func():\n    assert True\n",
        encoding="utf-8",
    )
    (repo / "tests" / "test_extra.py").write_text(
        "def test_extra():\n    pass\n",
        encoding="utf-8",
    )
    git(["add", "."])
    git(["commit", "-m", "fix: update tests"])

    sha = git(["rev-parse", "HEAD"]).stdout.strip()
    return repo, sha


def test_existing_test_modified_includes_function_names(tmp_path, monkeypatch):
    """existing_test_modified must list the modified test function names (test_basic),
    NOT the newly added ones (test_new_func), and NOT flag test_extra.py (new file)."""

    repo, bp_commit = _make_repo_with_existing_test_modified(tmp_path)

    import ferry.verify as vmod
    monkeypatch.setattr(vmod, "DEMO", repo)

    # Compute scoped functions: test_basic (modified) + test_new_func (added)
    # from test_money.py; test_extra.py is all-new.
    scoped = vmod._get_scoped_functions(
        bp_commit,
        ["tests/test_money.py", "tests/test_extra.py"],
        "release/1.x",
        repo,
    )

    flags = vmod._compute_flags(
        sha="abc1234abc1234abc1234abc1234abc1234abc1234",
        branch="release/1.x",
        bp_commit=bp_commit,
        test_files=["tests/test_money.py", "tests/test_extra.py"],
        wt_path=repo,
        per_test_before={},
        scoped=scoped,
        bp_src_by_file={},
    )

    etm_flags = [f for f in flags if f["kind"] == "existing_test_modified"]
    # Only test_money.py existed on the branch — test_extra.py is new
    etm_files = [f["file"] for f in etm_flags]
    assert "tests/test_money.py" in etm_files, (
        f"Expected tests/test_money.py in existing_test_modified, got: {etm_files}"
    )
    assert "tests/test_extra.py" not in etm_files, (
        "tests/test_extra.py should not be flagged (it's new)"
    )

    # The modified function must be test_basic; test_new_func is new, not modified
    etm = next(f for f in etm_flags if f["file"] == "tests/test_money.py")
    assert "test_basic" in etm["functions"], (
        f"test_basic should be listed as modified, got: {etm['functions']}"
    )
    assert "test_new_func" not in etm["functions"], (
        f"test_new_func is new (not modified), should not appear: {etm['functions']}"
    )


# ---------------------------------------------------------------------------
# Test: test_passes_without_fix — only when pytest.raises present
# ---------------------------------------------------------------------------

def _make_repo_for_tpwf(base: Path) -> tuple[Path, str, str]:
    """
    Repo layout:
    - release/1.x: ledger/__init__.py has VALUE=42; export_invoice raises on bad input.
    - Backport commit adds tests/test_sec.py with:
        * test_raises_on_bad: uses pytest.raises (the security check already works on branch)
        * test_no_raises: plain assertion (no pytest.raises)
    Returns (repo, bp_commit, bp_src_content).
    """
    repo = base / "repo-tpwf"
    repo.mkdir(parents=True, exist_ok=True)

    def git(args, cwd=repo, check=True):
        return _git(args, cwd=cwd, check=check)

    git(["init", str(repo)], cwd=base)
    git(["config", "user.email", "test@example.com"])
    git(["config", "user.name", "Test"])

    (repo / "ledger").mkdir()
    (repo / "ledger" / "__init__.py").write_text(
        "VALUE = 42\n\ndef export(path):\n    if '..' in path:\n        raise ValueError\n    return path\n",
        encoding="utf-8",
    )
    (repo / "tests").mkdir()
    (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "initial"])
    git(["branch", "release/1.x"])

    test_src = (
        "import pytest\n"
        "from ledger import VALUE, export\n"
        "\n"
        "def test_raises_on_bad():\n"
        "    with pytest.raises(ValueError):\n"
        "        export('../evil')\n"
        "\n"
        "def test_no_raises():\n"
        "    assert VALUE == 42\n"
    )
    (repo / "tests" / "test_sec.py").write_text(test_src, encoding="utf-8")
    git(["add", "."])
    git(["commit", "-m", "fix: add tests"])

    sha = git(["rev-parse", "HEAD"]).stdout.strip()
    return repo, sha, test_src


def test_test_passes_without_fix_only_when_pytest_raises(tmp_path, monkeypatch):
    """test_passes_without_fix must be emitted only for scoped tests that pass before
    AND whose body contains pytest.raises.  test_no_raises (passes before, no raises)
    must NOT trigger the flag — it should be classified as preserves_behaviour."""

    repo, bp_commit, bp_src = _make_repo_for_tpwf(tmp_path)

    import ferry.verify as vmod
    monkeypatch.setattr(vmod, "DEMO", repo)
    monkeypatch.setattr(vmod, "WORKTREES_DIR", tmp_path / "worktrees")

    # Simulate: both tests passed before the fix (branch already has the fix)
    per_test_before = {
        "tests/test_sec.py::test_raises_on_bad": {"passed": True, "failed": False},
        "tests/test_sec.py::test_no_raises":     {"passed": True, "failed": False},
    }

    bp_src_by_file = {"tests/test_sec.py": bp_src}

    # scoped: both functions are new (test_sec.py didn't exist on branch)
    scoped = {"tests/test_sec.py": ["test_raises_on_bad", "test_no_raises"]}

    flags = vmod._compute_flags(
        sha="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        branch="release/1.x",
        bp_commit=bp_commit,
        test_files=["tests/test_sec.py"],
        wt_path=repo,
        per_test_before=per_test_before,
        scoped=scoped,
        bp_src_by_file=bp_src_by_file,
    )

    tpwf_flags = [f for f in flags if f["kind"] == "test_passes_without_fix"]
    assert len(tpwf_flags) == 1, (
        f"Expected exactly one test_passes_without_fix flag, got: {flags}"
    )
    assert "tests/test_sec.py::test_raises_on_bad" in tpwf_flags[0]["tests"], (
        f"test_raises_on_bad should be flagged, got: {tpwf_flags[0]}"
    )
    assert "tests/test_sec.py::test_no_raises" not in tpwf_flags[0]["tests"], (
        "test_no_raises must NOT be flagged (no pytest.raises)"
    )

    # Verify preserves_behaviour classification in tests[] via verify_port logic
    # (test inline using _function_body_has_pytest_raises)
    assert vmod._function_body_has_pytest_raises("test_raises_on_bad", bp_src), \
        "test_raises_on_bad should have pytest.raises detected"
    assert not vmod._function_body_has_pytest_raises("test_no_raises", bp_src), \
        "test_no_raises should NOT have pytest.raises detected"

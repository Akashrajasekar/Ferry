"""ferry/verify.py – the `verify` command.

For each eligible port (clean_pass in try.json, or ported in ports/*.json):
  1. Identify regression test files touched by the backport commit.
  2. Scope: regression tests = only test FUNCTIONS added or modified by the
     backport commit (compare function bodies between the release branch head
     and the backport commit), not every test in a touched file.
  3. fail_before: temp worktree at release-branch head, inject only those test
     files, run only the scoped test functions via nodeids → must FAIL (exit 1).
  4. pass_after: run the scoped test functions on the backport worktree → must PASS.
  5. p2p: full suite on backport worktree → must PASS.
  6. Write/merge results into .ferry/results.json.

Per-test proof:
  - Run with --junitxml; extract per-function results.
  - Test IDs are normalised to "tests/file.py::func_name" (worktree-path prefix stripped).
  - A function "proves the fix" if it failed_before AND passed_after.
  - A function that passed both before and after:
    * if its body contains pytest.raises → flag "test_passes_without_fix"
      (reason: "expects an error that already happens without the fix, so it proves nothing")
    * otherwise → classify as "preserves_behaviour" in tests[] (no flag, shown in
      the per-test table as "guards existing behaviour")

Review flags (stored as flags[] on each result, review_required = true if any):
  - existing_test_modified: backport commit modifies a test file that already
    existed on the release branch head. Includes file path AND the modified function names.
  - test_case_removed: a test function present in the original fix's test file is
    missing from the ported test file. Includes the function names.
  - test_passes_without_fix: scoped regression test passed before the fix AND its
    body contains pytest.raises.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
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


def _parse_junit_xml(xml_path: Path) -> dict[str, dict]:
    """Parse junitxml output; return {normalised_test_id: {passed, failed}}."""
    results: dict[str, dict] = {}
    if not xml_path.exists():
        return results
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        for tc in root.findall(".//testcase"):
            classname = tc.get("classname", "")
            name = tc.get("name", "")
            failed = tc.find("failure") is not None or tc.find("error") is not None
            skipped = tc.find("skipped") is not None
            passed = not failed and not skipped
            # Normalise: strip all leading path segments to "tests/..." form.
            # classname in junitxml uses dots: e.g.
            #   "workspace.worktrees.70183af__release-2.x.tests.test_foo"
            # We want "tests/test_foo::func_name".
            test_id = _normalise_test_id(classname, name)
            results[test_id] = {"passed": passed, "failed": failed}
    except Exception:
        pass
    return results


def _normalise_test_id(classname: str, funcname: str) -> str:
    """
    Convert a junitxml classname + funcname to a stable short ID.

    pytest uses classname = dotted path from cwd, e.g.
      "workspace.worktrees.70183af__release-2.x.tests.test_foo"
    We normalise to "tests/test_foo.py::funcname".
    """
    # Find the first "tests" segment
    parts = classname.replace("\\", "/").split(".")
    try:
        idx = next(i for i, p in enumerate(parts) if p == "tests")
        file_parts = parts[idx:]  # ["tests", "test_foo"]
        file_path = "/".join(file_parts) + ".py"
    except StopIteration:
        # Fallback: use classname as-is
        file_path = classname.replace(".", "/")
    return f"{file_path}::{funcname}"


def _run_pytest_nodeids_with_junit(cwd: Path, nodeids: list[str]) -> dict:
    """Run pytest on explicit nodeids with --junitxml; return exit_code + per-test."""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        junit_path = Path(f.name)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             f"--junitxml={junit_path}"] + nodeids,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        per_test = _parse_junit_xml(junit_path)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "per_test": per_test,
        }
    finally:
        try:
            junit_path.unlink()
        except Exception:
            pass


def _run_pytest_files_with_junit(cwd: Path, files: list[str]) -> dict:
    """Run pytest on file paths with --junitxml (used when no scoped nodeids)."""
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
        junit_path = Path(f.name)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             f"--junitxml={junit_path}"] + files,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        per_test = _parse_junit_xml(junit_path)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "per_test": per_test,
        }
    finally:
        try:
            junit_path.unlink()
        except Exception:
            pass


def _run_pytest_files(cwd: Path, files: list[str]) -> dict:
    """Run pytest on specific files only (legacy, no junitxml)."""
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


# ---------------------------------------------------------------------------
# Scoped regression-test detection
# ---------------------------------------------------------------------------

def _extract_test_functions(source: str) -> list[str]:
    """Extract top-level test function names from Python source via AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                names.append(node.name)
    return names


def _get_function_node(func_name: str, source: str) -> ast.FunctionDef | None:
    """Return the AST node for func_name in source, or None."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                return node
    return None


def _function_body_text(func_name: str, source: str) -> str:
    """Return the source lines of the function body as a string, for comparison."""
    node = _get_function_node(func_name, source)
    if node is None:
        return ""
    lines = source.splitlines()
    # lineno is 1-based; end_lineno available in Python 3.8+
    try:
        body_lines = lines[node.lineno - 1: node.end_lineno]
    except AttributeError:
        body_lines = lines[node.lineno - 1:]
    return "\n".join(body_lines)


def _function_body_has_pytest_raises(func_name: str, source: str) -> bool:
    """Return True if the function body contains a pytest.raises call."""
    node = _get_function_node(func_name, source)
    if node is None:
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            # pytest.raises(...)
            func = child.func
            if isinstance(func, ast.Attribute) and func.attr == "raises":
                val = func.value
                if isinstance(val, ast.Name) and val.id == "pytest":
                    return True
            # raises(...) bare (unlikely but check)
            if isinstance(func, ast.Name) and func.id == "raises":
                return True
    return False


def _get_scoped_functions(
    bp_commit: str,
    test_files: list[str],
    branch: str,
    wt_path: Path,
) -> dict[str, list[str]]:
    """
    For each test file in test_files, return the test function names that were
    added or whose body changed between the release branch head and the
    backport commit.

    Returns {rel_file: [func_name, ...]} — only files/functions that actually changed.
    """
    scoped: dict[str, list[str]] = {}

    for tf in test_files:
        # Content at backport commit (what we'll inject)
        bp_result = git(["show", f"{bp_commit}:{tf}"], cwd=wt_path, check=False)
        bp_src = bp_result.stdout if bp_result.returncode == 0 else ""

        # Content at release branch head
        head_result = git(["show", f"{branch}:{tf}"], cwd=DEMO, check=False)
        head_src = head_result.stdout if head_result.returncode == 0 else ""

        bp_funcs = _extract_test_functions(bp_src)
        head_funcs = set(_extract_test_functions(head_src))

        changed = []
        for fn in bp_funcs:
            if fn not in head_funcs:
                # New function
                changed.append(fn)
            else:
                # Existing function — compare bodies
                bp_body = _function_body_text(fn, bp_src)
                head_body = _function_body_text(fn, head_src)
                if bp_body.strip() != head_body.strip():
                    changed.append(fn)

        if changed:
            scoped[tf] = changed

    return scoped


def _build_nodeids(scoped: dict[str, list[str]]) -> list[str]:
    """Convert scoped {file: [func, ...]} to pytest nodeids ["file::func", ...]."""
    nodeids = []
    for tf, funcs in scoped.items():
        for fn in funcs:
            nodeids.append(f"{tf}::{fn}")
    return nodeids


# ---------------------------------------------------------------------------
# fail_before with scoped nodeids
# ---------------------------------------------------------------------------

def _check_fail_before_with_junit(
    release_branch: str,
    test_files: list[str],
    commit_sha: str,
    wt_path: Path,
    nodeids: list[str] | None = None,
) -> tuple[bool, str, dict[str, dict]]:
    """
    Create a temporary worktree at release_branch head, inject only the
    regression test files (from the backport commit), run the scoped nodeids
    (or all files if nodeids is None) with --junitxml.

    Returns (fail_before, reason, per_test).
    fail_before = True only if exit_code == 1.
    """
    tmp_name = f"_fb_{release_branch.replace('/', '-')}_{commit_sha[:7]}"
    tmp_path = WORKTREES_DIR / tmp_name

    if tmp_path.exists():
        git(["worktree", "remove", "--force", str(tmp_path)], cwd=DEMO, check=False)
        shutil.rmtree(str(tmp_path), onerror=_remove_readonly)

    try:
        WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
        git(
            ["worktree", "add", "--detach", str(tmp_path), release_branch],
            cwd=DEMO,
        )

        # Inject the test files from the backport commit
        for rel_file in test_files:
            content = _git_show_file(commit_sha, rel_file, wt_path)
            dest = tmp_path / rel_file
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

        # Run only the scoped nodeids if provided, else all files
        if nodeids:
            r = _run_pytest_nodeids_with_junit(tmp_path, nodeids)
        else:
            r = _run_pytest_files_with_junit(tmp_path, test_files)

        ec = r["exit_code"]
        per_test = r["per_test"]

        if ec == 1:
            return True, "", per_test
        else:
            return False, "test did not run cleanly before the fix", per_test
    finally:
        if tmp_path.exists():
            git(["worktree", "remove", "--force", str(tmp_path)], cwd=DEMO, check=False)
            shutil.rmtree(str(tmp_path), onerror=_remove_readonly)
        git(["worktree", "prune"], cwd=DEMO, check=False)


# Keep old _check_fail_before for backwards compat with tests
def _check_fail_before(
    release_branch: str,
    test_files: list[str],
    commit_sha: str,
    wt_path: Path,
) -> tuple[bool, str]:
    """Thin wrapper around the junitxml variant, discarding per-test data."""
    fail_before, reason, _ = _check_fail_before_with_junit(
        release_branch, test_files, commit_sha, wt_path
    )
    return fail_before, reason


def _truncate_diff(text: str, max_lines: int = 400) -> str:
    lines = text.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return text
    return "".join(lines[:max_lines]) + f"\n... (truncated at {max_lines} lines)\n"


def _get_diffs(fix_sha: str, backport_commit: str, wt_path: Path) -> tuple[str, str]:
    """Return (fix_diff, backport_diff) each truncated to 400 lines."""
    show_fix = git(["show", fix_sha], cwd=DEMO, check=False)
    fix_diff = _truncate_diff(show_fix.stdout)

    show_bp = git(["show", backport_commit], cwd=wt_path, check=False)
    backport_diff = _truncate_diff(show_bp.stdout)

    return fix_diff, backport_diff


# ---------------------------------------------------------------------------
# Review flag helpers
# ---------------------------------------------------------------------------

def _file_exists_on_branch(file_path: str, branch: str) -> bool:
    """Check if file_path exists on the given branch in DEMO."""
    result = git(
        ["ls-tree", "--name-only", branch, file_path],
        cwd=DEMO,
        check=False,
    )
    return bool(result.stdout.strip())


def _compute_flags(
    sha: str,
    branch: str,
    bp_commit: str,
    test_files: list[str],
    wt_path: Path,
    per_test_before: dict[str, dict],
    scoped: dict[str, list[str]],
    bp_src_by_file: dict[str, str],
) -> list[dict]:
    """Compute review flags for a port."""
    flags: list[dict] = []

    # 1. existing_test_modified: test file that already existed on branch AND
    #    has functions modified by the backport commit.
    for tf in test_files:
        if _file_exists_on_branch(tf, branch):
            # The modified functions are those in scoped[tf] that also existed on branch
            head_result = git(["show", f"{branch}:{tf}"], cwd=DEMO, check=False)
            head_src = head_result.stdout if head_result.returncode == 0 else ""
            head_funcs = set(_extract_test_functions(head_src))

            modified_fns = [
                fn for fn in scoped.get(tf, [])
                if fn in head_funcs
            ]
            # Include even if modified_fns is empty — file itself existed
            flags.append({
                "kind": "existing_test_modified",
                "file": tf,
                "functions": sorted(modified_fns),
            })

    # 2. test_case_removed: test function present in original fix missing from port
    for tf in test_files:
        orig_result = git(["show", f"{sha}:{tf}"], cwd=DEMO, check=False)
        orig_src = orig_result.stdout if orig_result.returncode == 0 else ""
        orig_fns = set(_extract_test_functions(orig_src))

        ported_result = git(["show", f"{bp_commit}:{tf}"], cwd=wt_path, check=False)
        ported_src = ported_result.stdout if ported_result.returncode == 0 else ""
        ported_fns = set(_extract_test_functions(ported_src))

        removed = sorted(orig_fns - ported_fns)
        if removed:
            flags.append({
                "kind": "test_case_removed",
                "file": tf,
                "functions": removed,
            })

    # 3. test_passes_without_fix: scoped test that passed before AND has pytest.raises.
    #    (plain passing tests without pytest.raises are classified as preserves_behaviour,
    #    no flag.)
    passes_with_raises: list[str] = []
    for test_id, info in per_test_before.items():
        if not info.get("passed"):
            continue
        # Extract function name from normalised id "tests/file.py::func"
        func_name = test_id.split("::")[-1]
        # Find source for this function
        has_raises = False
        for tf, src in bp_src_by_file.items():
            if _function_body_has_pytest_raises(func_name, src):
                has_raises = True
                break
        if has_raises:
            passes_with_raises.append(test_id)

    if passes_with_raises:
        flags.append({
            "kind": "test_passes_without_fix",
            "tests": passes_with_raises,
            "reason": "expects an error that already happens without the fix, so it proves nothing",
        })

    return flags


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

    bp_commit = _backport_commit(wt_path, bp_branch)
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
        "tests": [],
        "flags": [],
        "review_required": False,
        "seconds": 0.0,
    }

    if not test_files:
        result["fail_before_reason"] = "no regression test files found"
        result["seconds"] = round(time.monotonic() - t0, 2)
        return result

    # --- Scope: functions added or modified by the backport commit ---
    scoped = _get_scoped_functions(bp_commit, test_files, branch, wt_path)

    # Cache backport source per file (for pytest.raises detection later)
    bp_src_by_file: dict[str, str] = {}
    for tf in test_files:
        r = git(["show", f"{bp_commit}:{tf}"], cwd=wt_path, check=False)
        bp_src_by_file[tf] = r.stdout if r.returncode == 0 else ""

    # fail_before nodeids: use scoped functions from the commit content
    # (injected into the temp worktree verbatim from the commit)
    fb_nodeids = _build_nodeids(scoped)

    # pass_after nodeids: scoped functions actually present on disk in the worktree
    # (adapted ports may rename/remove functions; only run what exists)
    pa_scoped: dict[str, list[str]] = {}
    for tf, fns in scoped.items():
        disk_path = wt_path / tf
        if disk_path.exists():
            disk_fns = set(_extract_test_functions(disk_path.read_text(encoding="utf-8", errors="replace")))
            present = [fn for fn in fns if fn in disk_fns]
            if present:
                pa_scoped[tf] = present
    pa_nodeids = _build_nodeids(pa_scoped)

    # --- fail_before ---
    fail_before, fb_reason, per_test_before = _check_fail_before_with_junit(
        branch, test_files, bp_commit, wt_path, fb_nodeids or None
    )
    result["fail_before"] = fail_before
    result["fail_before_reason"] = fb_reason

    # --- pass_after ---
    if pa_nodeids:
        pa_r = _run_pytest_nodeids_with_junit(wt_path, pa_nodeids)
    elif test_files:
        pa_r = _run_pytest_files_with_junit(wt_path, test_files)
    else:
        pa_r = {"exit_code": 5, "per_test": {}}
    pass_after = pa_r["exit_code"] == 0
    result["pass_after"] = pass_after
    per_test_after = pa_r["per_test"]

    result["f2p"] = fail_before and pass_after

    # --- Build per-test table (scoped functions only) ---
    # Collect all normalised IDs seen across both runs
    all_ids = sorted(set(per_test_before) | set(per_test_after))
    tests_list = []
    for tid in all_ids:
        fb_info = per_test_before.get(tid, {})
        pa_info = per_test_after.get(tid, {})
        failed_before = fb_info.get("failed", False)
        passed_after_val = pa_info.get("passed", False)
        proves_fix = failed_before and passed_after_val

        # Classify tests that pass both before and after
        kind = "regression"
        if not failed_before and passed_after_val:
            func_name = tid.split("::")[-1]
            has_raises = any(
                _function_body_has_pytest_raises(func_name, src)
                for src in bp_src_by_file.values()
            )
            kind = "test_passes_without_fix" if has_raises else "preserves_behaviour"

        tests_list.append({
            "id": tid,
            "failed_before": failed_before,
            "passed_after": passed_after_val,
            "proves_fix": proves_fix,
            "kind": kind,
        })
    result["tests"] = tests_list

    # --- p2p: full suite ---
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

    # --- Review flags ---
    flags = _compute_flags(
        sha=sha,
        branch=branch,
        bp_commit=bp_commit,
        test_files=test_files,
        wt_path=wt_path,
        per_test_before=per_test_before,
        scoped=scoped,
        bp_src_by_file=bp_src_by_file,
    )
    result["flags"] = flags
    result["review_required"] = len(flags) > 0

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

    try_path = FERRY_DIR / "try.json"
    try_entries: list[dict] = []
    if try_path.exists():
        try_entries = json.loads(try_path.read_text(encoding="utf-8"))

    ports_dir = FERRY_DIR / "ports"
    port_files: list[dict] = []
    if ports_dir.exists():
        for pf in ports_dir.glob("*.json"):
            try:
                port_files.append(json.loads(pf.read_text(encoding="utf-8")))
            except Exception:
                pass

    plan_path = FERRY_DIR / "plan.json"
    plan_data: dict = {}
    if plan_path.exists():
        plan_data = json.loads(plan_path.read_text(encoding="utf-8"))

    ported_set: dict[tuple, dict] = {}
    for pf in port_files:
        if pf.get("status") == "ported":
            key = (pf["sha"], pf["branch"])
            ported_set[key] = pf

    eligible: list[dict] = []
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
            pass  # handled via port_files or recorded as pending

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
                "tests": [],
                "flags": [],
                "review_required": False,
                "seconds": 0.0,
            }
        new_entries.append(entry)
        if not entry["f2p"] or not entry["p2p"]:
            any_failure = True

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
                "tests": [],
                "flags": [],
                "review_required": False,
                "seconds": 0.0,
            })

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
                        "tests": [],
                        "flags": [],
                        "review_required": False,
                        "seconds": 0.0,
                    })

    existing = _load_results()
    merged = _merge_results(existing, new_entries)
    _save_results(merged)
    print(f"\n    Written .ferry/results.json ({len(merged)} entries)")

    _print_verify_table(new_entries)
    return 1 if any_failure else 0


def _print_verify_table(entries: list[dict]) -> None:
    rows = [e for e in entries if e["method"] not in ("pending", "skip", "not_applicable")]
    if not rows:
        print("\n  No ports verified.")
        return
    print()
    print(f"{'SHA':<7}  {'Branch':<15}  {'Method':<9}  {'FB':<5}  {'PA':<5}  {'P2P':<5}  {'RR':<5}  {'Secs':>6}")
    print("-" * 72)
    for e in rows:
        sha7 = e["sha"][:7]
        branch = e["branch"][:15]
        method = e["method"][:9]
        fb = "true" if e.get("fail_before") else "false"
        pa = "true" if e.get("pass_after") else "false"
        p2p = "true" if e.get("p2p") else "false"
        rr = "true" if e.get("review_required") else "false"
        secs = e.get("seconds", 0.0)
        print(f"{sha7:<7}  {branch:<15}  {method:<9}  {fb:<5}  {pa:<5}  {p2p:<5}  {rr:<5}  {secs:>6.2f}s")

    flag_rows = [e for e in rows if e.get("flags")]
    if flag_rows:
        print()
        print("  Review flags:")
        for e in flag_rows:
            sha7 = e["sha"][:7]
            for flag in e["flags"]:
                kind = flag["kind"]
                if kind == "existing_test_modified":
                    fns = flag.get("functions", [])
                    fn_str = (", ".join(fns)) if fns else "(none)"
                    print(f"    {sha7}  {e['branch']:<20}  existing_test_modified:"
                          f" {flag['file']}  functions={fn_str}")
                elif kind == "test_case_removed":
                    print(f"    {sha7}  {e['branch']:<20}  test_case_removed:"
                          f" {flag['file']}  removed={flag.get('functions', [])}")
                elif kind == "test_passes_without_fix":
                    tests = flag.get("tests", [])
                    for t in tests:
                        print(f"    {sha7}  {e['branch']:<20}  test_passes_without_fix:"
                              f" {t}")

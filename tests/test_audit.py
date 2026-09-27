"""tests/test_audit.py – audit classification against the demo repo.

Requires workspace/demo-ledger to exist (run `ferry scenario` first).
Tests are skipped if the demo repo is absent.
"""
from __future__ import annotations

import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO = REPO_ROOT / "workspace" / "demo-ledger"


@pytest.fixture(scope="module")
def audit_entries():
    """Run audit against the demo repo and return the entries list."""
    if not DEMO.exists():
        pytest.skip("workspace/demo-ledger not found; run `ferry scenario` first")
    from ferry.audit import run_audit
    return run_audit(DEMO)


def test_empty_items_backported_on_2x(audit_entries):
    """'handle empty line items' must be backported:<sha> on release/2.x.

    The SHA reported must be the backport commit on release/2.x, not the
    original commit on main.
    """
    import subprocess
    from pathlib import Path

    entry = next(
        (e for e in audit_entries if "handle empty line items" in e["subject"]),
        None,
    )
    assert entry is not None, "Could not find 'handle empty line items' in audit entries"
    status = entry["branches"].get("release/2.x", "")
    assert status.startswith("backported:"), (
        f"Expected backported:<sha> on release/2.x, got {status!r}"
    )

    # Verify that the reported short SHA is the backport commit on release/2.x,
    # not the original main commit.
    reported_short = status[len("backported:"):]
    main_sha = entry["sha"]
    assert not main_sha.startswith(reported_short), (
        f"backported SHA {reported_short!r} must be the release-branch commit, "
        f"not the main SHA {main_sha[:7]!r}"
    )


def test_empty_items_missing_on_1x(audit_entries):
    """'handle empty line items' must be missing on release/1.x."""
    entry = next(
        (e for e in audit_entries if "handle empty line items" in e["subject"]),
        None,
    )
    assert entry is not None
    status = entry["branches"].get("release/1.x", "")
    assert status == "missing", (
        f"Expected missing on release/1.x, got {status!r}"
    )


def test_escape_customer_missing_on_1x(audit_entries):
    """'escape customer name' must be missing on release/1.x."""
    entry = next(
        (e for e in audit_entries if "escape customer name" in e["subject"]),
        None,
    )
    assert entry is not None, "Could not find 'escape customer name' in audit entries"
    status = entry["branches"].get("release/1.x", "")
    assert status == "missing", (
        f"Expected missing on release/1.x, got {status!r}"
    )


def test_escape_customer_missing_on_2x(audit_entries):
    """'escape customer name' must be missing on release/2.x."""
    entry = next(
        (e for e in audit_entries if "escape customer name" in e["subject"]),
        None,
    )
    assert entry is not None
    status = entry["branches"].get("release/2.x", "")
    assert status == "missing", (
        f"Expected missing on release/2.x, got {status!r}"
    )

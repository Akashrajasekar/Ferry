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
    """'handle empty line items' must be backported:<sha> on release/2.x."""
    entry = next(
        (e for e in audit_entries if "handle empty line items" in e["subject"]),
        None,
    )
    assert entry is not None, "Could not find 'handle empty line items' in audit entries"
    status = entry["branches"].get("release/2.x", "")
    assert status.startswith("backported:"), (
        f"Expected backported:<sha> on release/2.x, got {status!r}"
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

"""
build_scenario.py – creates workspace/demo-ledger from scratch.

Every git operation uses fixed GIT_AUTHOR_* / GIT_COMMITTER_* env vars so
SHAs are reproducible across machines.  All file I/O uses newline="\\n".
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = REPO_ROOT / "workspace"
DEMO = WORKSPACE / "demo-ledger"

# ---------------------------------------------------------------------------
# Fixed identity – must never change so SHAs are stable
# ---------------------------------------------------------------------------
AUTHOR_NAME = "Ferry Bot"
AUTHOR_EMAIL = "ferry@example.com"
BASE_DATE = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)


def _date(offset_days: int) -> str:
    d = BASE_DATE + timedelta(days=offset_days)
    return d.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _env(offset_days: int) -> dict:
    dt = _date(offset_days)
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL": AUTHOR_EMAIL,
        "GIT_AUTHOR_DATE": dt,
        "GIT_COMMITTER_NAME": AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": AUTHOR_EMAIL,
        "GIT_COMMITTER_DATE": dt,
    }


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def git(args: list[str], *, cwd: Path = DEMO, env: dict | None = None,
        check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git"] + args
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env or os.environ,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise RuntimeError(f"git {' '.join(args)} failed (rc={result.returncode})")
    return result


def commit(message: str, day: int) -> None:
    git(["add", "-A"], env=_env(day))
    git(["commit", "-m", message], env=_env(day))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# Remove read-only files (Windows .git objects)
# ---------------------------------------------------------------------------
def _remove_readonly(func, path, _exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def delete_demo_repo() -> None:
    if DEMO.exists():
        shutil.rmtree(str(DEMO), onerror=_remove_readonly)


# ---------------------------------------------------------------------------
# Step 1 – v0.9 baseline
# ---------------------------------------------------------------------------
MONEY_V09 = """\
\"\"\"money.py – monetary helpers (v0.9)\"\"\"


def round_money(x: float) -> float:
    \"\"\"Round to 2 decimal places.\"\"\"
    return round(x, 2)
"""

EXPORT_V09 = """\
\"\"\"ledger/export.py – invoice export (v0.9)\"\"\"
from pathlib import Path


def export_invoice(invoice: dict, path: str) -> None:
    \"\"\"Write invoice as plain text to *path*.\"\"\"
    out = Path(path)
    lines = []
    lines.append(f"Customer: {invoice.get('customer', '')}")
    for item in invoice.get("items", []):
        lines.append(f"  {item['name']}: {item['amount']}")
    out.write_text("\\n".join(lines), encoding="utf-8")
"""

TEMPLATES_V09 = '''\
"""templates.py – shared constants."""

HEADER = "Invocie"  # NOTE: intentional typo – do NOT change this line
'''

INIT_V09 = '''\
"""ledger package (v0.9)"""
from .money import round_money
from .export import export_invoice
from .templates import HEADER

__version__ = "0.9.0"
'''

TEST_MONEY_V09 = """\
\"\"\"Tests for money.py (v0.9)\"\"\"
from ledger.money import round_money


def test_round_money_basic():
    assert round_money(1.005) == 1.0  # standard rounding
    assert round_money(2.345) == 2.35


def test_round_money_negative():
    assert round_money(-1.005) == -1.0
"""

TEST_EXPORT_V09 = """\
\"\"\"Tests for export.py (v0.9)\"\"\"
import tempfile
from pathlib import Path
from ledger.export import export_invoice


def test_export_creates_file(tmp_path):
    inv = {"customer": "Acme", "items": [{"name": "Widget", "amount": 9.99}]}
    out = tmp_path / "inv.txt"
    export_invoice(inv, str(out))
    assert out.exists()
    text = out.read_text()
    assert "Acme" in text
    assert "Widget" in text
"""

CONFTEST_V09 = """\
# conftest.py – add ledger package to sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
"""

SETUP_CFG = """\
[metadata]
name = ledger
version = 0.9.0

[options]
packages = ledger
"""


def step1_v09(day: int) -> None:
    write(DEMO / "ledger" / "money.py", MONEY_V09)
    write(DEMO / "ledger" / "export.py", EXPORT_V09)
    write(DEMO / "ledger" / "templates.py", TEMPLATES_V09)
    write(DEMO / "ledger" / "__init__.py", INIT_V09)
    write(DEMO / "tests" / "test_money.py", TEST_MONEY_V09)
    write(DEMO / "tests" / "test_export.py", TEST_EXPORT_V09)
    write(DEMO / "conftest.py", CONFTEST_V09)
    write(DEMO / "setup.cfg", SETUP_CFG)
    commit("feat: v0.9 baseline – money, export, templates", day)


# ---------------------------------------------------------------------------
# Step 2 – v1 (line-item totals, richer export)
# ---------------------------------------------------------------------------
MONEY_V1 = """\
\"\"\"money.py – monetary helpers (v1)\"\"\"


def round_money(x: float) -> float:
    \"\"\"Round to 2 decimal places.\"\"\"
    return round(x, 2)


def line_item_total(qty: int, unit_price: float) -> float:
    \"\"\"Return quantity * unit_price, rounded.\"\"\"
    return round_money(qty * unit_price)
"""

EXPORT_V1 = """\
\"\"\"ledger/export.py – invoice export (v1)\"\"\"
from pathlib import Path


def export_invoice(invoice: dict, path: str) -> None:
    \"\"\"Write invoice as plain text to *path*.\"\"\"
    out = Path(path)
    lines = []
    lines.append(f"Customer: {invoice.get('customer', '')}")
    for item in invoice.get("items", []):
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    out.write_text("\\n".join(lines), encoding="utf-8")
"""

INIT_V1 = '''\
"""ledger package (v1)"""
from .money import round_money, line_item_total
from .export import export_invoice
from .templates import HEADER

__version__ = "1.0.0"
'''

TEST_MONEY_V1 = """\
\"\"\"Tests for money.py (v1)\"\"\"
from ledger.money import round_money, line_item_total


def test_round_money_basic():
    assert round_money(1.005) == 1.0
    assert round_money(2.345) == 2.35


def test_line_item_total():
    assert line_item_total(3, 2.50) == 7.50
    assert line_item_total(1, 9.99) == 9.99
"""

TEST_EXPORT_V1 = """\
\"\"\"Tests for export.py (v1)\"\"\"
from ledger.export import export_invoice


def test_export_creates_file(tmp_path):
    inv = {
        "customer": "Acme",
        "items": [{"name": "Widget", "amount": 9.99, "qty": 2}],
    }
    out = tmp_path / "inv.txt"
    export_invoice(inv, str(out))
    assert out.exists()
    text = out.read_text()
    assert "Acme" in text
    assert "Widget" in text
"""


def step2_v1(day: int) -> None:
    write(DEMO / "ledger" / "money.py", MONEY_V1)
    write(DEMO / "ledger" / "export.py", EXPORT_V1)
    write(DEMO / "ledger" / "__init__.py", INIT_V1)
    write(DEMO / "tests" / "test_money.py", TEST_MONEY_V1)
    write(DEMO / "tests" / "test_export.py", TEST_EXPORT_V1)
    commit("feat: v1 – line-item totals, richer export", day)


# ---------------------------------------------------------------------------
# Step 3 – v2 (rename round_money→round_amount, new export signature)
# ---------------------------------------------------------------------------
MONEY_V2 = """\
\"\"\"money.py – monetary helpers (v2)\"\"\"
from decimal import Decimal, ROUND_HALF_UP


def round_amount(x: Decimal) -> Decimal:
    \"\"\"Round Decimal to 2 decimal places (ROUND_HALF_UP).\"\"\"
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def line_item_total(qty: int, unit_price: Decimal) -> Decimal:
    \"\"\"Return quantity * unit_price, rounded.\"\"\"
    return round_amount(qty * unit_price)
"""

EXPORT_V2 = """\
\"\"\"ledger/export.py – invoice export (v2)\"\"\"
from pathlib import Path


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text.

    Parameters
    ----------
    invoice : dict
    filename : str   – name of the output file (no directory component)
    out_dir  : str   – directory to write into
    \"\"\"
    dest = Path(out_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"Customer: {invoice.get('customer', '')}")
    for item in invoice.get("items", []):
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""

INIT_V2 = '''\
"""ledger package (v2)"""
from .money import round_amount, line_item_total
from .export import export_invoice
from .templates import HEADER

__version__ = "2.0.0"
'''

TEST_MONEY_V2 = """\
\"\"\"Tests for money.py (v2)\"\"\"
from decimal import Decimal
from ledger.money import round_amount, line_item_total


def test_round_amount_basic():
    assert round_amount(Decimal("1.005")) == Decimal("1.01")
    assert round_amount(Decimal("2.344")) == Decimal("2.34")


def test_line_item_total():
    assert line_item_total(3, Decimal("2.50")) == Decimal("7.50")
"""

TEST_EXPORT_V2 = """\
\"\"\"Tests for export.py (v2)\"\"\"
from ledger.export import export_invoice


def test_export_creates_file(tmp_path):
    inv = {
        "customer": "Acme",
        "items": [{"name": "Widget", "amount": 9.99, "qty": 2}],
    }
    dest = export_invoice(inv, "inv.txt", str(tmp_path))
    assert dest.exists()
    text = dest.read_text()
    assert "Acme" in text
"""


def step3_v2(day: int) -> None:
    write(DEMO / "ledger" / "money.py", MONEY_V2)
    write(DEMO / "ledger" / "export.py", EXPORT_V2)
    write(DEMO / "ledger" / "__init__.py", INIT_V2)
    write(DEMO / "tests" / "test_money.py", TEST_MONEY_V2)
    write(DEMO / "tests" / "test_export.py", TEST_EXPORT_V2)
    commit("feat: v2 – Decimal rounding, new export signature", day)


# ---------------------------------------------------------------------------
# Step 4 – gap fixes on main
# ---------------------------------------------------------------------------
EXPORT_EMPTY_ITEMS = """\
\"\"\"ledger/export.py – invoice export (v2 + empty-items fix)\"\"\"
from pathlib import Path


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text.

    Parameters
    ----------
    invoice : dict
    filename : str   – name of the output file (no directory component)
    out_dir  : str   – directory to write into
    \"\"\"
    dest = Path(out_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"Customer: {invoice.get('customer', '')}")
    items = invoice.get("items") or []
    if not items:
        lines.append("  (no items)")
    for item in items:
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""

TEST_EMPTY_ITEMS = """\
\"\"\"Regression test: handle empty line items.\"\"\"
from ledger.export import export_invoice


def test_empty_items(tmp_path):
    inv = {"customer": "Acme", "items": []}
    dest = export_invoice(inv, "empty.txt", str(tmp_path))
    assert "(no items)" in dest.read_text()
"""

EXPORT_ESCAPE = """\
\"\"\"ledger/export.py – invoice export (v2 + security: escape customer name)\"\"\"
from pathlib import Path
import html


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text.\"\"\"
    dest = Path(out_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    customer = html.escape(str(invoice.get("customer", "")))
    lines.append(f"Customer: {customer}")
    items = invoice.get("items") or []
    if not items:
        lines.append("  (no items)")
    for item in items:
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""

TEST_ESCAPE = """\
\"\"\"Regression test: escape customer name in export header.\"\"\"
from ledger.export import export_invoice


def test_escape_customer_name(tmp_path):
    inv = {"customer": "<Evil Corp & Co>", "items": []}
    dest = export_invoice(inv, "esc.txt", str(tmp_path))
    text = dest.read_text()
    assert "<Evil" not in text
    assert "&lt;" in text or "Evil Corp" in text
"""


def step4_gap_fixes(days: tuple[int, int]) -> tuple[str, str]:
    """Add two gap-fix commits on main; return their SHAs."""
    # Fix 1: handle empty line items
    write(DEMO / "ledger" / "export.py", EXPORT_EMPTY_ITEMS)
    write(DEMO / "tests" / "test_empty_items.py", TEST_EMPTY_ITEMS)
    commit("fix: handle empty line items", days[0])
    r1 = git(["rev-parse", "HEAD"])
    sha_empty = r1.stdout.strip()

    # Fix 2: escape customer name
    write(DEMO / "ledger" / "export.py", EXPORT_ESCAPE)
    write(DEMO / "tests" / "test_escape.py", TEST_ESCAPE)
    commit("fix(security): escape customer name in export header", days[1])
    r2 = git(["rev-parse", "HEAD"])
    sha_escape = r2.stdout.strip()

    return sha_empty, sha_escape


# ---------------------------------------------------------------------------
# Step 5 – v3 restructure
# ---------------------------------------------------------------------------
MONEY_ROUNDING_V3 = """\
\"\"\"ledger/money/rounding.py – monetary rounding (v3)\"\"\"
from decimal import Decimal, ROUND_HALF_UP


def round_amount(x: Decimal) -> Decimal:
    \"\"\"Round Decimal to 2 decimal places (ROUND_HALF_UP).\"\"\"
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def line_item_total(qty: int, unit_price: Decimal) -> Decimal:
    \"\"\"Return quantity * unit_price, rounded.\"\"\"
    return round_amount(qty * unit_price)
"""

MONEY_ROUNDING_INIT = '''\
"""ledger.money package"""
from .rounding import round_amount, line_item_total
'''

EXPORT_PDF_V3 = """\
\"\"\"ledger/exporters/pdf.py – invoice export (v3)\"\"\"
from pathlib import Path
import html


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text to out_dir/filename.

    Validates filename: must not be absolute and must not contain '..'.
    Validates out_dir: resolved dest must be inside out_dir.
    \"\"\"
    dest_dir = Path(out_dir).resolve()
    dest = (dest_dir / filename).resolve()
    if not str(dest).startswith(str(dest_dir)):
        raise ValueError(f"Path traversal detected: {filename!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    customer = html.escape(str(invoice.get("customer", "")))
    lines.append(f"Customer: {customer}")
    items = invoice.get("items") or []
    if not items:
        lines.append("  (no items)")
    for item in items:
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""

EXPORTERS_INIT_V3 = '''\
"""ledger.exporters package"""
from .pdf import export_invoice
'''

DISCOUNTS_V3 = """\
\"\"\"ledger/discounts.py – discount helpers (new in v3)\"\"\"


def apply_discount(amount: float, rate: float) -> float:
    \"\"\"Apply a discount *rate* (0–1) to *amount*.

    The rate is clamped to [0, 1] so discounts cannot exceed 100 %.
    \"\"\"
    rate = max(0.0, min(1.0, rate))
    return amount * (1.0 - rate)
"""

INIT_V3 = '''\
"""ledger package (v3)"""
from .money.rounding import round_amount, line_item_total
from .exporters.pdf import export_invoice
from .templates import HEADER
from .discounts import apply_discount

__version__ = "3.0.0"
'''

TEST_MONEY_V3 = """\
\"\"\"Tests for ledger.money.rounding (v3)\"\"\"
from decimal import Decimal
from ledger.money.rounding import round_amount, line_item_total


def test_round_amount_basic():
    # Use values that don't hit the half-even boundary so this test
    # passes both before and after Fix B (ROUND_HALF_UP -> ROUND_HALF_EVEN).
    assert round_amount(Decimal("1.006")) == Decimal("1.01")
    assert round_amount(Decimal("2.344")) == Decimal("2.34")


def test_line_item_total():
    assert line_item_total(3, Decimal("2.50")) == Decimal("7.50")
"""

TEST_EXPORT_V3 = """\
\"\"\"Tests for ledger.exporters.pdf (v3)\"\"\"
import pytest
from ledger.exporters.pdf import export_invoice


def test_export_creates_file(tmp_path):
    inv = {
        "customer": "Acme",
        "items": [{"name": "Widget", "amount": 9.99, "qty": 2}],
    }
    dest = export_invoice(inv, "inv.txt", str(tmp_path))
    assert dest.exists()
    assert "Acme" in dest.read_text()
"""

TEST_DISCOUNTS_V3 = """\
\"\"\"Tests for discounts.py\"\"\"
from ledger.discounts import apply_discount


def test_basic_discount():
    assert apply_discount(100.0, 0.10) == 90.0


def test_zero_discount():
    assert apply_discount(100.0, 0.0) == 100.0
"""

TEST_EMPTY_ITEMS_V3 = """\
\"\"\"Regression test: handle empty line items (v3 paths)\"\"\"
from ledger.exporters.pdf import export_invoice


def test_empty_items(tmp_path):
    inv = {"customer": "Acme", "items": []}
    dest = export_invoice(inv, "empty.txt", str(tmp_path))
    assert "(no items)" in dest.read_text()
"""

TEST_ESCAPE_V3 = """\
\"\"\"Regression test: escape customer name (v3 paths)\"\"\"
from ledger.exporters.pdf import export_invoice


def test_escape_customer_name(tmp_path):
    inv = {"customer": "<Evil Corp & Co>", "items": []}
    dest = export_invoice(inv, "esc.txt", str(tmp_path))
    text = dest.read_text()
    assert "<Evil" not in text
"""


def step5_v3(day: int) -> None:
    # Remove old flat modules
    for old in ["money.py", "export.py"]:
        p = DEMO / "ledger" / old
        if p.exists():
            p.unlink()
    # New structure
    write(DEMO / "ledger" / "money" / "__init__.py", MONEY_ROUNDING_INIT)
    write(DEMO / "ledger" / "money" / "rounding.py", MONEY_ROUNDING_V3)
    write(DEMO / "ledger" / "exporters" / "__init__.py", EXPORTERS_INIT_V3)
    write(DEMO / "ledger" / "exporters" / "pdf.py", EXPORT_PDF_V3)
    write(DEMO / "ledger" / "discounts.py", DISCOUNTS_V3)
    write(DEMO / "ledger" / "__init__.py", INIT_V3)
    # Tests
    write(DEMO / "tests" / "test_money.py", TEST_MONEY_V3)
    write(DEMO / "tests" / "test_export.py", TEST_EXPORT_V3)
    write(DEMO / "tests" / "test_discounts.py", TEST_DISCOUNTS_V3)
    write(DEMO / "tests" / "test_empty_items.py", TEST_EMPTY_ITEMS_V3)
    write(DEMO / "tests" / "test_escape.py", TEST_ESCAPE_V3)
    # Remove old test files that no longer apply
    for old_t in ["test_money.py"]:
        pass  # overwritten above
    commit("feat: v3 – restructure into sub-packages, add discounts", day)


# ---------------------------------------------------------------------------
# Step 6 – four demo fixes on main
# ---------------------------------------------------------------------------

# Fix A – prevent path traversal
FIX_A_EXPORT = """\
\"\"\"ledger/exporters/pdf.py – invoice export (v3 + FSA-2026-001 fix)\"\"\"
from pathlib import Path
import html


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text to out_dir/filename.

    Security: rejects absolute paths and path traversal in *filename*.
    The resolved destination must be inside *out_dir*.
    \"\"\"
    if Path(filename).is_absolute():
        raise ValueError(f"filename must be relative, got {filename!r}")
    if ".." in Path(filename).parts:
        raise ValueError(f"filename must not contain '..', got {filename!r}")
    dest_dir = Path(out_dir).resolve()
    dest = (dest_dir / filename).resolve()
    if not str(dest).startswith(str(dest_dir) + os.sep) and dest != dest_dir:
        raise ValueError(f"Path traversal detected: {filename!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    customer = html.escape(str(invoice.get("customer", "")))
    lines.append(f"Customer: {customer}")
    items = invoice.get("items") or []
    if not items:
        lines.append("  (no items)")
    for item in items:
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""

FIX_A_EXPORT = """\
\"\"\"ledger/exporters/pdf.py – invoice export (v3 + FSA-2026-001 fix)\"\"\"
import os
from pathlib import Path
import html


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text to out_dir/filename.

    Security: rejects absolute paths and path traversal in *filename*.
    The resolved destination must be inside *out_dir*.
    \"\"\"
    if Path(filename).is_absolute():
        raise ValueError(f"filename must be relative, got {filename!r}")
    if ".." in Path(filename).parts:
        raise ValueError(f"filename must not contain '..', got {filename!r}")
    dest_dir = Path(out_dir).resolve()
    dest = (dest_dir / filename).resolve()
    if not str(dest).startswith(str(dest_dir)):
        raise ValueError(f"Path traversal detected: {filename!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    customer = html.escape(str(invoice.get("customer", "")))
    lines.append(f"Customer: {customer}")
    items = invoice.get("items") or []
    if not items:
        lines.append("  (no items)")
    for item in items:
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""

TEST_FIX_A = """\
\"\"\"Regression test: path traversal prevention (FSA-2026-001)\"\"\"
import pytest
from ledger.exporters.pdf import export_invoice


def test_rejects_path_traversal(tmp_path):
    inv = {"customer": "Acme", "items": []}
    with pytest.raises((ValueError, OSError)):
        export_invoice(inv, "../evil.txt", str(tmp_path))


def test_rejects_absolute_path(tmp_path):
    inv = {"customer": "Acme", "items": []}
    with pytest.raises((ValueError, OSError)):
        export_invoice(inv, "/etc/passwd", str(tmp_path))


def test_normal_export_still_works(tmp_path):
    inv = {"customer": "Acme", "items": [{"name": "X", "amount": 1.0, "qty": 1}]}
    dest = export_invoice(inv, "ok.txt", str(tmp_path))
    assert dest.exists()
"""

# Fix B – banker's rounding
FIX_B_ROUNDING = """\
\"\"\"ledger/money/rounding.py – monetary rounding (v3 + banker's rounding fix)\"\"\"
from decimal import Decimal, ROUND_HALF_EVEN


def round_amount(x: Decimal) -> Decimal:
    \"\"\"Round Decimal to 2 decimal places using ROUND_HALF_EVEN (banker's rounding).\"\"\"
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def line_item_total(qty: int, unit_price: Decimal) -> Decimal:
    \"\"\"Return quantity * unit_price, rounded.\"\"\"
    return round_amount(qty * unit_price)
"""

TEST_FIX_B = """\
\"\"\"Regression test: banker's rounding (ROUND_HALF_EVEN)\"\"\"
from decimal import Decimal
from ledger.money.rounding import round_amount


def test_half_even():
    # 0.5 rounds to nearest even: 0.5 -> 0.0 is wrong; 2.5 -> 2 (even)
    assert round_amount(Decimal("2.5")) == Decimal("2.50")
    # 2.125 -> 2.12 (2 is even)
    assert round_amount(Decimal("2.125")) == Decimal("2.12")
    # 2.135 -> 2.14 (4 is even)
    assert round_amount(Decimal("2.135")) == Decimal("2.14")
"""

# Fix C – typo in templates.py  (file must be byte-identical from step 1 to step 5)
FIX_C_TEMPLATES = '''\
"""templates.py – shared constants."""

HEADER = "Invoice"
'''

TEST_FIX_C = """\
\"\"\"Regression test: invoice header spelling\"\"\"
from ledger.templates import HEADER


def test_header_spelling():
    assert HEADER == "Invoice", f"Expected 'Invoice', got {HEADER!r}"
"""

# Fix D – cap discounts
FIX_D_DISCOUNTS = """\
\"\"\"ledger/discounts.py – discount helpers (v3 + cap fix)\"\"\"


def apply_discount(amount: float, rate: float) -> float:
    \"\"\"Apply a discount *rate* (0–1) to *amount*.

    The rate is clamped to [0, 1] so discounts cannot exceed 100 %.
    \"\"\"
    rate = max(0.0, min(1.0, rate))
    return amount * (1.0 - rate)
"""

TEST_FIX_D = """\
\"\"\"Regression test: cap discounts at 100%\"\"\"
from ledger.discounts import apply_discount


def test_cap():
    # discount > 100 % must not produce negative amount
    assert apply_discount(100.0, 1.5) == 0.0
    assert apply_discount(100.0, 2.0) == 0.0


def test_normal_discount():
    assert apply_discount(200.0, 0.25) == 150.0
"""


def step6_demo_fixes(start_day: int) -> None:
    day = start_day

    # Fix A
    write(DEMO / "ledger" / "exporters" / "pdf.py", FIX_A_EXPORT)
    write(DEMO / "tests" / "test_export_security.py", TEST_FIX_A)
    commit("fix(security): prevent path traversal in invoice export (FSA-2026-001)", day)
    day += 1

    # Fix B
    write(DEMO / "ledger" / "money" / "rounding.py", FIX_B_ROUNDING)
    write(DEMO / "tests" / "test_rounding.py", TEST_FIX_B)
    commit("fix: use banker's rounding for currency", day)
    day += 1

    # Fix C
    write(DEMO / "ledger" / "templates.py", FIX_C_TEMPLATES)
    write(DEMO / "tests" / "test_templates.py", TEST_FIX_C)
    commit("fix: correct typo in invoice header", day)
    day += 1

    # Fix D
    write(DEMO / "ledger" / "discounts.py", FIX_D_DISCOUNTS)
    write(DEMO / "tests" / "test_discounts.py", TEST_FIX_D)
    commit("fix: cap discounts at 100%", day)


# ---------------------------------------------------------------------------
# Pytest runner helper
# ---------------------------------------------------------------------------
def run_pytest(cwd: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    if result.returncode != 0:
        print(result.stderr[-1000:])
        raise RuntimeError(f"pytest failed in {cwd}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    WORKSPACE.mkdir(exist_ok=True)
    (WORKSPACE / "docs").mkdir(exist_ok=True)

    print("==> Deleting old demo-ledger …")
    delete_demo_repo()

    print("==> Initialising fresh repo …")
    DEMO.mkdir(parents=True)
    git(["init", "-b", "main"], cwd=DEMO)
    git(["config", "core.autocrlf", "false"], cwd=DEMO)
    git(["config", "core.eol", "lf"], cwd=DEMO)
    git(["config", "user.email", AUTHOR_EMAIL], cwd=DEMO)
    git(["config", "user.name", AUTHOR_NAME], cwd=DEMO)
    # Add .gitignore so __pycache__ never blocks branch switches
    write(DEMO / ".gitignore", "__pycache__/\n*.pyc\n*.pyo\n.pytest_cache/\n*.egg-info/\n")
    git(["add", ".gitignore"], env=_env(0))
    git(["commit", "-m", "chore: add .gitignore"], env=_env(0))

    # ---- Step 1: v0.9 ----
    print("==> Step 1: v0.9 baseline …")
    day = 0
    step1_v09(day); day += 1
    run_pytest(DEMO)
    git(["tag", "v0.9.0"], env=_env(day))
    git(["checkout", "-b", "release/0.9"], env=_env(day))
    git(["checkout", "main"], env=_env(day))

    # ---- Step 2: v1 ----
    print("==> Step 2: v1 features …")
    step2_v1(day); day += 1
    run_pytest(DEMO)
    git(["tag", "v1.0.0"], env=_env(day))
    git(["checkout", "-b", "release/1.x"], env=_env(day))
    git(["checkout", "main"], env=_env(day))

    # ---- Step 3: v2 ----
    print("==> Step 3: v2 – Decimal rounding …")
    step3_v2(day); day += 1
    run_pytest(DEMO)
    git(["tag", "v2.0.0"], env=_env(day))
    git(["checkout", "-b", "release/2.x"], env=_env(day))
    git(["checkout", "main"], env=_env(day))

    # ---- Step 4: gap fixes on main ----
    print("==> Step 4: gap fixes …")
    sha_empty, sha_escape = step4_gap_fixes((day, day + 1))
    day += 2
    run_pytest(DEMO)

    # Cherry-pick "handle empty line items" into release/2.x
    print("==> Cherry-picking empty-items fix into release/2.x …")
    git(["checkout", "release/2.x"], env=_env(day))

    # Build a compatible version of the empty-items fix for release/2.x
    # (release/2.x still has the v2 export.py – we patch that one)
    EXPORT_EMPTY_V2 = """\
\"\"\"ledger/export.py – invoice export (v2 + empty-items fix)\"\"\"
from pathlib import Path


def export_invoice(invoice: dict, filename: str, out_dir: str) -> Path:
    \"\"\"Write invoice as plain text.\"\"\"
    dest = Path(out_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"Customer: {invoice.get('customer', '')}")
    items = invoice.get("items") or []
    if not items:
        lines.append("  (no items)")
    for item in items:
        total = item.get("qty", 1) * item.get("amount", 0)
        lines.append(f"  {item['name']}: {item['amount']} x {item.get('qty',1)} = {total}")
    dest.write_text("\\n".join(lines), encoding="utf-8")
    return dest
"""
    TEST_EMPTY_V2 = """\
\"\"\"Regression test: handle empty line items (v2 paths)\"\"\"
from ledger.export import export_invoice


def test_empty_items(tmp_path):
    inv = {"customer": "Acme", "items": []}
    dest = export_invoice(inv, "empty.txt", str(tmp_path))
    assert "(no items)" in dest.read_text()
"""
    write(DEMO / "ledger" / "export.py", EXPORT_EMPTY_V2)
    write(DEMO / "tests" / "test_empty_items.py", TEST_EMPTY_V2)
    git(["add", "-A"], env=_env(day))
    git(["commit", "-m",
         f"fix: handle empty line items\n\n(cherry picked from commit {sha_empty})"],
        env=_env(day))
    run_pytest(DEMO)

    git(["checkout", "main"], env=_env(day))
    day += 1

    # ---- Step 5: v3 ----
    print("==> Step 5: v3 – restructure …")
    step5_v3(day); day += 1
    run_pytest(DEMO)
    git(["tag", "v3.0.0"], env=_env(day))

    # ---- Step 6: four demo fixes on main ----
    print("==> Step 6: four demo fixes …")
    step6_demo_fixes(day)
    run_pytest(DEMO)

    # ---- Verify all branches ----
    for branch in ["release/0.9", "release/1.x", "release/2.x"]:
        print(f"==> Verifying {branch} …")
        git(["checkout", branch])
        run_pytest(DEMO)
    git(["checkout", "main"])

    print("\n==> build_scenario.py DONE")
    print(f"    main  : {git(['rev-parse', 'HEAD']).stdout.strip()}")
    for b in ["release/0.9", "release/1.x", "release/2.x"]:
        sha = git(["rev-parse", b]).stdout.strip()
        print(f"    {b}: {sha}")


if __name__ == "__main__":
    main()

"""ferry/cli.py – command-line interface for Ferry."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIO_DIR = REPO_ROOT / "scenario"


def cmd_scenario(_args: argparse.Namespace) -> int:
    """Run build_scenario.py then make_docs.py."""
    scripts = [
        SCENARIO_DIR / "build_scenario.py",
        SCENARIO_DIR / "make_docs.py",
    ]
    for script in scripts:
        print(f"==> Running {script.name} …")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            print(f"ERROR: {script.name} exited with code {result.returncode}",
                  file=sys.stderr)
            return result.returncode
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    from .audit import cmd_audit as _audit
    return _audit(args)


def cmd_try(args: argparse.Namespace) -> int:
    from .mechanical import cmd_try as _try
    return _try(args)


def cmd_reset(args: argparse.Namespace) -> int:
    from .mechanical import cmd_reset as _reset
    return _reset(args)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ferry",
        description="Ferry – automated backporting tool",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # scenario command
    scenario_p = sub.add_parser(
        "scenario",
        help="Build workspace/demo-ledger and generate policy documents",
    )
    scenario_p.set_defaults(func=cmd_scenario)

    # audit command
    audit_p = sub.add_parser(
        "audit",
        help="Audit fix commits on main against release branches",
    )
    audit_p.set_defaults(func=cmd_audit)

    # try command
    try_p = sub.add_parser(
        "try",
        help="Cherry-pick ports from plan.json (or fixture)",
    )
    try_p.add_argument(
        "--plan-fixture",
        action="store_true",
        default=False,
        help="Use hard-coded plan fixture from section 4.3 instead of plan.json",
    )
    try_p.set_defaults(func=cmd_try)

    # reset command
    reset_p = sub.add_parser(
        "reset",
        help="Remove worktrees, backport branches, and .ferry/",
    )
    reset_p.add_argument(
        "--keep-plan",
        action="store_true",
        default=False,
        help="Keep .ferry/plan.json when deleting .ferry/",
    )
    reset_p.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

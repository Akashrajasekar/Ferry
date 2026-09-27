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

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

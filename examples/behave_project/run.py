#!/usr/bin/env python
"""Run the example Behave project and generate a JSON report.

Usage:
    python run.py

This script runs behave with the modern JSON formatter against the
example feature files and writes the report to report.json.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE_DIR = Path(__file__).resolve().parent


def main() -> int:
    env = {
        "PYTHONPATH": str(PROJECT_ROOT),
        "PATH": __import__("os").environ.get("PATH", ""),
    }
    cmd = [
        sys.executable, "-m", "behave",
        "--format", "behave_modern_json_report:ModernJSONFormatter",
        "--outfile", "report.json",
        "--no-color",
        "features",
    ]
    print(f"Running: {' '.join(cmd)}")
    print(f"Working dir: {EXAMPLE_DIR}")
    print()
    result = subprocess.run(cmd, cwd=EXAMPLE_DIR, env={**__import__("os").environ, **env})
    report_path = EXAMPLE_DIR / "report.json"
    if report_path.exists():
        size = report_path.stat().st_size
        print(f"\nReport generated: {report_path} ({size} bytes)")
    else:
        print("\nWARNING: report.json was not generated")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

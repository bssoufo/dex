"""Verification CLI for Dex data quality.

Usage:
    uv run python -m backend.src.etl.verify.cli [--checks-only] [--dashboard-only] [--report-only]

Default (no flags): runs all three -- dashboard, checks, and report.

This CLI is READ-ONLY. It loads, checks, and reports. It does NOT
modify any data files. Plan 03 handles actual data fixes.
"""

from __future__ import annotations

import argparse

from .checks import load_all_models, run_all_checks
from .completeness import render_completeness_matrix
from .not_available import build_not_available_list, classify_null_fields
from .report import render_anomaly_report


def main() -> None:
    """Entry point for the verification CLI."""
    parser = argparse.ArgumentParser(
        description="Dex data verification CLI -- read-only quality dashboard"
    )
    parser.add_argument(
        "--checks-only",
        action="store_true",
        help="Run verification checks only (no dashboard or report)",
    )
    parser.add_argument(
        "--dashboard-only",
        action="store_true",
        help="Show completeness dashboard only",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Show anomaly report only",
    )
    args = parser.parse_args()

    models = load_all_models()
    run_all = not (args.checks_only or args.dashboard_only or args.report_only)

    # Section 1: Completeness dashboard
    if run_all or args.dashboard_only:
        render_completeness_matrix(models)

    # Section 2+3: Run checks (needed for both checks-only and report)
    results = None
    if run_all or args.checks_only or args.report_only:
        results = [run_all_checks(m) for m in models]

    # Section 3: Anomaly report
    if run_all or args.report_only:
        assert results is not None
        render_anomaly_report(results)

    # Section 4: Not-available field summary (full run only)
    if run_all:
        from rich.console import Console

        console = Console()
        total_na = sum(len(build_not_available_list(m)) for m in models)
        console.print(
            f"\n[bold]Not-Available Fields:[/] {total_na} total across "
            f"{len(models)} models"
        )
        classification = classify_null_fields(models)
        console.print(f"  Part numbers: {classification['part_numbers']}")
        console.print(f"  Universal nulls: {classification['universal_nulls']}")
        console.print(
            f"  Manufacturer-specific: {classification['manufacturer_specific']}"
        )

    # Section 5: Checks summary (checks-only mode)
    if args.checks_only and results:
        from rich.console import Console

        console = Console()
        total_anomalies = sum(len(r.anomalies) for r in results)
        console.print(
            f"\n[bold]Checks complete:[/] {total_anomalies} anomalies "
            f"across {len(results)} models"
        )


if __name__ == "__main__":
    main()

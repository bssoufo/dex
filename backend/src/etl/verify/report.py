"""Human-readable anomaly report with severity grouping.

Renders a grouped, scannable anomaly report using rich. Groups anomalies
by severity (error first, then warning, then info) and sorts within each
group by model name.

Usage:
    from backend.src.etl.verify.report import render_anomaly_report
    from backend.src.etl.verify.checks import load_all_models, run_all_checks

    models = load_all_models()
    results = [run_all_checks(m) for m in models]
    render_anomaly_report(results)
"""

from __future__ import annotations

from rich.console import Console

from .checks import Anomaly, VerificationResult


def render_anomaly_report(results: list[VerificationResult]) -> None:
    """Render a grouped anomaly report using rich.

    Groups anomalies by severity (error first, then warning, then info).
    Within each severity group, sorts by model name for scannability.
    Prints total counts at the top for quick triage.
    """
    console = Console()
    all_anomalies: list[Anomaly] = []
    for r in results:
        all_anomalies.extend(r.anomalies)

    errors = [a for a in all_anomalies if a.severity == "error"]
    warnings = [a for a in all_anomalies if a.severity == "warning"]
    infos = [a for a in all_anomalies if a.severity == "info"]

    console.print(f"\n[bold]Anomaly Report[/bold]")
    console.print(
        f"Total: {len(all_anomalies)} anomalies "
        f"({len(errors)} errors, {len(warnings)} warnings, {len(infos)} info)\n"
    )

    if errors:
        console.print("[bold red]ERRORS (require fix):[/]")
        for a in sorted(errors, key=lambda x: x.model_name):
            console.print(
                f"  [{a.check_name}] {a.model_name}/{a.category}: {a.message}"
            )

    if warnings:
        console.print("\n[bold yellow]WARNINGS (review recommended):[/]")
        for a in sorted(warnings, key=lambda x: x.model_name):
            console.print(
                f"  [{a.check_name}] {a.model_name}/{a.category}: {a.message}"
            )

    if infos:
        console.print("\n[bold blue]INFO (acknowledged):[/]")
        for a in sorted(infos, key=lambda x: x.model_name):
            console.print(
                f"  [{a.check_name}] {a.model_name}/{a.category}: {a.message}"
            )

    # Summary line
    checks_passed = sum(r.checks_passed for r in results)
    checks_failed = sum(r.checks_failed for r in results)
    console.print(
        f"\n[bold]Check Results:[/] {checks_passed} passed, "
        f"{checks_failed} failed across {len(results)} models"
    )

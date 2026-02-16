"""Completeness dashboard for Dex spa model data.

Renders a 19x10 color-coded matrix showing OK/NULL/EMPTY status for
every model-category pair. Uses rich for terminal output.

Usage:
    from backend.src.etl.verify.completeness import render_completeness_matrix
    from backend.src.etl.verify.checks import load_all_models

    models = load_all_models()
    render_completeness_matrix(models)
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from backend.src.schema.models import SpaModel

from .checks import _is_category_all_null

CATEGORIES = [
    "jet_pumps",
    "circulation_pump",
    "spa_pak",
    "topside_control",
    "jets",
    "headrests",
    "filters",
    "heater",
    "lighting",
    "cover",
]


def categorize_field(model: SpaModel, category: str) -> str:
    """Return status: 'OK', 'NULL', or 'EMPTY' for a category.

    - NULL: category field is None on the model
    - EMPTY: category exists but all meaningful fields are None/empty
    - OK: category has at least one non-null meaningful field
    """
    cat_data = getattr(model, category, None)
    if cat_data is None:
        return "NULL"
    if _is_category_all_null(cat_data):
        return "EMPTY"
    return "OK"


def compute_completeness_stats(models: list[SpaModel]) -> dict:
    """Return dict with ok/null/empty counts and per-model breakdowns.

    Returns:
        {
            "ok": int,
            "null": int,
            "empty": int,
            "total": int,
            "models": [
                {"name": str, "ok": int, "null": int, "empty": int},
                ...
            ]
        }
    """
    ok_total = 0
    null_total = 0
    empty_total = 0
    model_breakdowns = []

    for model in models:
        ok = 0
        null = 0
        empty = 0
        for cat in CATEGORIES:
            status = categorize_field(model, cat)
            if status == "OK":
                ok += 1
            elif status == "NULL":
                null += 1
            else:
                empty += 1
        ok_total += ok
        null_total += null
        empty_total += empty
        model_breakdowns.append(
            {
                "name": f"{model.manufacturer.value}/{model.model_name}",
                "ok": ok,
                "null": null,
                "empty": empty,
            }
        )

    return {
        "ok": ok_total,
        "null": null_total,
        "empty": empty_total,
        "total": len(models) * len(CATEGORIES),
        "models": model_breakdowns,
    }


def render_completeness_matrix(models: list[SpaModel]) -> None:
    """Render 19x10 matrix with rich color coding.

    Columns: one per category (truncated to 8 chars for table width).
    Rows: one per model (manufacturer prefix / model name).
    Cells: [green]OK[/], [yellow]EMPTY[/], or [bold red]NULL[/].
    Final column: score (OK count / 10).
    """
    console = Console()
    table = Table(title="Dex Data Completeness (19 models x 10 categories)")

    table.add_column("Model", style="bold", width=22)
    for cat in CATEGORIES:
        table.add_column(cat[:8], justify="center", width=9)
    table.add_column("Score", justify="right", width=6)

    for model in models:
        name = f"{model.manufacturer.value[:3]}/{model.model_name}"
        row: list[str] = [name]
        ok_count = 0

        for cat in CATEGORIES:
            status = categorize_field(model, cat)
            if status == "NULL":
                row.append("[bold red]NULL[/]")
            elif status == "EMPTY":
                row.append("[yellow]EMPTY[/]")
            else:
                row.append("[green]OK[/]")
                ok_count += 1

        row.append(f"{ok_count}/10")
        table.add_row(*row)

    console.print(table)

    # Print summary stats below the table
    stats = compute_completeness_stats(models)
    console.print(
        f"\n[bold]Summary:[/] {stats['ok']}/{stats['total']} OK, "
        f"{stats['null']}/{stats['total']} NULL, "
        f"{stats['empty']}/{stats['total']} EMPTY"
    )

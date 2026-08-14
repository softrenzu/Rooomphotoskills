from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from .pipeline import run_drive_pipeline

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Google Drive の物件写真を選定・補正して掲載用に出力します。")
console = Console()


def _show_summary(summary: dict) -> None:
    console.print(f"対象画像: {summary['total_images']}枚")
    console.print(f"採用画像: {summary['selected_images']}枚")
    console.print(f"品質/重複等で除外: {summary['rejected_images']}枚")
    table = Table("順位", "ファイル", "カテゴリ", "品質", "理由")
    for i, row in enumerate(summary["selected"], start=1):
        table.add_row(str(i), row["name"], row["category"], f"{row['quality_score']:.3f}", row["reason"])
    console.print(table)
    if summary.get("output_folder_id"):
        console.print(f"出力フォルダ: https://drive.google.com/drive/folders/{summary['output_folder_id']}")


@app.command("drive")
def drive_command(
    folder: str = typer.Argument(..., help="Google Drive フォルダ URL または folder ID"),
    credentials: str | None = typer.Option(None, "--credentials", help="Google OAuth Desktop App credentials.json"),
    token_file: str | None = typer.Option(None, "--token-file", help="OAuth token 保存先"),
    output_folder_name: str = typer.Option("リスティング用_加工済み", "--output-folder-name"),
    min_selected: int = typer.Option(15, "--min-selected", min=1),
    max_selected: int = typer.Option(28, "--max-selected", min=1),
    dry_run: bool = typer.Option(False, "--dry-run", help="Driveへ出力せず選定だけ実行"),
    json_output: bool = typer.Option(False, "--json", help="結果をJSONで表示"),
):
    """Drive内の写真から掲載価値の高いものだけを選び、別フォルダへ出力します。"""
    try:
        summary = run_drive_pipeline(
            folder_url_or_id=folder,
            credentials=credentials,
            token_file=token_file,
            output_folder_name=output_folder_name,
            min_selected=min_selected,
            max_selected=max_selected,
            dry_run=dry_run,
            progress=lambda message: console.print(message, highlight=False),
        )
    except Exception as exc:
        console.print(f"[red]エラー:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    if json_output:
        console.print_json(json.dumps(summary, ensure_ascii=False))
    else:
        _show_summary(summary)


if __name__ == "__main__":
    app()

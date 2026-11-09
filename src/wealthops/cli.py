"""Command-line interface for WealthOps."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from .config import Settings
from .pipeline import (
    apply_seed,
    build,
    export,
    generate,
    load,
    reset_database,
    run_quality,
    status,
    transform,
)


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    if args.data_dir:
        settings = replace(settings, data_dir=Path(args.data_dir))
    if args.export_dir:
        settings = replace(settings, export_dir=Path(args.export_dir))
    if args.db:
        settings = replace(settings, data_dir=Path(args.db).parent)
    if getattr(args, "clients", None) is not None:
        settings = replace(settings, n_clients=int(args.clients))
    if getattr(args, "advisors", None) is not None:
        settings = replace(settings, n_advisors=int(args.advisors))
    if getattr(args, "months", None) is not None:
        settings = replace(settings, months=int(args.months))
    return apply_seed(settings, args.seed)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wealthops",
        description="WealthOps synthetic wealth-management analytics workbench.",
    )
    parser.add_argument("--data-dir", help="Directory for DuckDB and raw parquet files")
    parser.add_argument("--export-dir", help="Directory for exported CSV marts")
    parser.add_argument("--db", help="Explicit DuckDB database path")
    parser.add_argument("--seed", type=int, help="Override the synthetic data seed")
    parser.add_argument("--clients", type=int, help="Number of synthetic clients to generate")
    parser.add_argument("--advisors", type=int, help="Number of synthetic advisors to generate")
    parser.add_argument("--months", type=int, help="Number of observation months to simulate")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("generate", help="Generate seeded parquet data")
    sub.add_parser("load", help="Load parquet data into the operational schema")
    sub.add_parser("transform", help="Build dimensions, facts and KPI views")
    sub.add_parser("quality", help="Run data-quality checks (exit 1 on failure)")
    sub.add_parser("export", help="Export KPI views to CSV")
    sub.add_parser("status", help="Show database counts and quality status")
    sub.add_parser("reset", help="Delete the local DuckDB database")

    build_p = sub.add_parser("build", help="Run generate, load, transform, quality and export")
    build_p.add_argument("--reset", action="store_true", help="Delete the database first")

    nlq_p = sub.add_parser("nlq", help="Ask a governed analytics question")
    nlq_p.add_argument("question", help="Natural-language question")
    nlq_p.add_argument("--limit", type=int, default=200, help="Forced result row limit")
    nlq_p.add_argument("--show-sql", action="store_true", help="Print generated SQL")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = _settings(args)
    verbose = not args.quiet

    if args.command == "generate":
        generate(settings, verbose=verbose)
        return 0
    if args.command == "load":
        load(settings, verbose=verbose)
        return 0
    if args.command == "transform":
        transform(settings, verbose=verbose)
        return 0
    if args.command == "quality":
        results = run_quality(settings, verbose=verbose)
        return 0 if (results["status"] == "PASS").all() else 1
    if args.command == "export":
        export(settings, verbose=verbose)
        return 0
    if args.command == "reset":
        reset_database(settings)
        if verbose:
            print(f"[reset] removed {settings.db_path}")
        return 0
    if args.command == "status":
        info = status(settings)
        print(json.dumps(info, indent=2))
        return 0
    if args.command == "nlq":
        from .nlq.engine import NLQEngine

        engine = NLQEngine(settings, row_limit=args.limit)
        result = engine.ask(args.question)
        if args.show_sql and result.sql:
            print("SQL:")
            print(result.sql)
            print()
        if result.error:
            print(f"Blocked: {result.error}", file=sys.stderr)
            return 2
        print(result.frame.to_string(index=False))
        return 0
    if args.command == "build":
        summary = build(settings, seed=None, reset=args.reset, verbose=verbose)
        return 0 if summary["quality"]["failed"] == 0 else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

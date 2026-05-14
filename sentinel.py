from __future__ import annotations

import argparse
import logging
import sys

from sentinel.agent.agent import run_agent
from sentinel.config import load_config
from sentinel.core.api import run_api
from sentinel.core.collector import run_collector
from sentinel.core.archive import run_archive
from sentinel.core.purge import run_purge
from sentinel.core.report import run_report
from sentinel.core.pilot import run_pilot
from sentinel.core.stack import run_stack
from sentinel.tools.simulator import run_simulator
from sentinel.ui.app import run_ui


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sentinel Phase 1 runtime")
    parser.add_argument(
        "role",
        nargs='?',
        default="pilot",
        choices=("agent", "collector", "report", "ui", "simulate", "purge", "archive", "api", "stack", "pilot"),
        help="Runtime role to start (default: pilot)",
    )
    parser.add_argument(
        "--config",
        default=None,  # Will be resolved based on role
        help="Path to YAML configuration",
    )
    parser.add_argument(
        "--node-id",
        default=None,
        help="Optional node_id filter for report mode",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of rows to return in report mode",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print compact report summary instead of full datasets",
    )
    parser.add_argument(
        "--compact-payloads",
        action="store_true",
        help="Print compact payload fields in report mode",
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=10,
        help="Number of synthetic nodes in simulate mode",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=60,
        help="Duration for simulate mode; 0 means run until interrupted",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=1.0,
        help="Send interval for simulate mode",
    )
    parser.add_argument(
        "--before",
        default="",
        help="Purge records older than this date (YYYY-MM-DD) in purge mode",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show purge impact without deleting data",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Allow destructive purge execution",
    )
    parser.add_argument(
        "--output-dir",
        default="./data/archive",
        help="Archive output directory for parquet mode",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    # Resolve config path based on role if not explicitly provided
    if args.config is None:
        if args.role == "pilot":
            args.config = "config/pilot.config.yaml"
        else:
            args.config = "config/config.yaml"

    config = load_config(args.config)

    if args.role == "agent":
        run_agent(config)
    elif args.role == "collector":
        run_collector(config)
    elif args.role == "simulate":
        run_simulator(
            config,
            nodes=args.nodes,
            duration_seconds=args.duration_seconds,
            interval_seconds=args.interval_seconds,
        )
    elif args.role == "purge":
        run_purge(
            config,
            before=args.before,
            dry_run=bool(args.dry_run or not args.confirm),
            confirm=args.confirm,
        )
    elif args.role == "archive":
        run_archive(
            config,
            before=args.before,
            output_dir=args.output_dir,
            dry_run=bool(args.dry_run or not args.confirm),
        )
    elif args.role == "api":
        run_api(config)
    elif args.role == "stack":
        run_stack(config_path=args.config, python_executable=sys.executable)
    elif args.role == "pilot":
        run_pilot(config=config, config_path=args.config, executable_path=sys.executable)
    else:
        if args.role == "report":
            run_report(
                config,
                node_id=args.node_id,
                limit=args.limit,
                summary_only=args.summary_only,
                compact_payloads=args.compact_payloads,
            )
        else:
            run_ui(config)


if __name__ == "__main__":
    main()

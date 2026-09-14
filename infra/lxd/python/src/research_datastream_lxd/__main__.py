"""Entry point: `python -m research_datastream_lxd`.

Run by the systemd unit on the controller. Also usable ad-hoc with `--once`
(fire one run, bypassing the scheduler) or `--fire-init` (fire every run of one
init, fanning out all VPUs/members as the scheduler would).
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import runner, scheduler
from .config import ScheduledRun, load_datastream


def _configure_logging(level: str, failure_log: str | None = None) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    if failure_log:
        _attach_failure_log(failure_log)


def _attach_failure_log(path: str) -> None:
    """Route the `…failures` logger to a per-day log file (active file `path`,
    rolled to `path.YYYY-MM-DD` at each midnight)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(
        path, when="midnight", backupCount=30, utc=True,
    )
    handler.suffix = "%Y-%m-%d"
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logging.getLogger("research_datastream_lxd.failures").addHandler(handler)
    logging.getLogger(__name__).info("logging run failures to %s (rotated daily)", path)


def _build_output_check(kind: str | None) -> runner.OutputCheck | None:
    if not kind or kind == "none":
        return None
    if kind == "s3":
        return runner.S3OutputCheck(region=os.environ.get("AWS_REGION", "us-east-1"))
    raise ValueError(f"unknown output check: {kind}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research-datastream-lxd")
    parser.add_argument(
        "--datastreams-dir",
        type=Path,
        default=Path(os.environ.get("RDS_LXD_DATASTREAMS_DIR", "/etc/research-datastream-lxd/datastreams")),
        help="Directory containing per-datastream subdirs with YAML + templates.",
    )
    parser.add_argument(
        "--output-check",
        choices=["none", "s3"],
        default=os.environ.get("RDS_LXD_OUTPUT_CHECK", "none"),
        help="Backend for verifying run outputs landed where expected.",
    )
    parser.add_argument(
        "--once",
        metavar="DATASTREAM[:GROUP[:INIT[:VPU[:MEMBER]]]]",
        help="Run a single scheduled run immediately and exit (bypasses scheduler). "
        "VPU/MEMBER narrow per-VPU datastreams (e.g. cfe-nom:short_range:06:09).",
    )
    parser.add_argument(
        "--fire-init",
        metavar="DATASTREAM:GROUP:INIT",
        help="Fire EVERY run of one init immediately and exit (bypasses scheduler). "
        "For per-VPU datastreams this fans out all VPUs (and members) of the init "
        "exactly as the scheduler would at that init's cron time "
        "(e.g. cfe-nom:short_range:00 -> all 20 VPUs).",
    )
    parser.add_argument(
        "--core-budget",
        type=int,
        default=int(os.environ.get("RDS_LXD_CORE_BUDGET", scheduler.DEFAULT_CORE_BUDGET)),
        help="Max cpu cores in flight across concurrent scheduler runs "
        "(default: %(default)s = half the host's cores; env RDS_LXD_CORE_BUDGET).",
    )
    parser.add_argument(
        "--memory-pct",
        type=float,
        default=float(os.environ.get("RDS_LXD_MEMORY_PCT", scheduler.DEFAULT_MEMORY_PCT)),
        help="Per-node memory guard: never place a run that would push a member's "
        "live RAM usage past this fraction of its total (default: %(default)s; env "
        "RDS_LXD_MEMORY_PCT). 0 disables it (cores become the only limit).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.environ.get("RDS_LXD_MAX_CONCURRENT_RUNS", scheduler.DEFAULT_MAX_CONCURRENT_RUNS)),
        help="Max simultaneous runs for the --fire-init fan-out (default: "
        "%(default)s; env RDS_LXD_MAX_CONCURRENT_RUNS; 1 = sequential). The "
        "scheduler bounds concurrency by --core-budget, not this flag.",
    )
    parser.add_argument(
        "--stagger-s",
        type=float,
        default=float(os.environ.get("RDS_LXD_STAGGER_S", scheduler.DEFAULT_STAGGER_S)),
        help="Seconds between consecutive run launches, to spread launch-time "
        "network load (default: %(default)s; env RDS_LXD_STAGGER_S; 0 disables). "
        "Applies to both the scheduler and --fire-init.",
    )
    parser.add_argument("--log-level", default=os.environ.get("RDS_LXD_LOG_LEVEL", "INFO"))
    parser.add_argument(
        "--failure-log",
        default=os.environ.get("RDS_LXD_FAILURE_LOG"),
        help="Path to a log file recording runs that fail to produce output "
        "(env RDS_LXD_FAILURE_LOG). Rolls to a new file each day; unset disables "
        "the file (failures still go to the console).",
    )
    args = parser.parse_args(argv)

    _configure_logging(args.log_level, args.failure_log)
    output_check = _build_output_check(args.output_check)

    if args.once and args.fire_init:
        print("--once and --fire-init are mutually exclusive", file=sys.stderr)
        return 1
    if args.once:
        return _run_once(args.datastreams_dir, args.once, output_check)
    if args.fire_init:
        return _fire_init(args.datastreams_dir, args.fire_init, output_check,
                          args.concurrency, args.stagger_s)

    scheduler.run_forever(
        args.datastreams_dir,
        output_check=output_check,
        core_budget=args.core_budget,
        mem_pct=args.memory_pct,
        stagger_s=args.stagger_s,
    )
    return 0


def _match_runs(datastreams_dir: Path, selector: str) -> tuple[str, list[ScheduledRun]]:
    """Resolve a DATASTREAM[:GROUP[:INIT[:VPU[:MEMBER]]]] selector to its runs."""
    parts = selector.split(":")
    ds_name = parts[0]
    group = parts[1] if len(parts) > 1 else None
    init = parts[2] if len(parts) > 2 else None
    vpu = parts[3] if len(parts) > 3 else None
    member = parts[4] if len(parts) > 4 else None

    ds = load_datastream(datastreams_dir / ds_name)
    matching = [
        r for r in ds.runs
        if (group is None or r.group == group)
        and (init is None or r.init == init)
        and (vpu is None or r.vpu == vpu)
        and (member is None or r.member == member)
    ]
    return ds_name, matching


def _run_once(datastreams_dir: Path, selector: str, output_check) -> int:
    _, matching = _match_runs(datastreams_dir, selector)
    if not matching:
        print(f"no runs matched {selector}", file=sys.stderr)
        return 1
    if len(matching) > 1:
        print(f"selector {selector} matched {len(matching)} runs; be more specific "
              f"(or use --fire-init to run them all)", file=sys.stderr)
        for r in matching:
            sel = ":".join(p for p in [r.datastream, r.group, r.init, r.vpu, r.member or None] if p)
            print(f"  {sel}", file=sys.stderr)
        return 1

    result = runner.run(matching[0], output_check=output_check)
    return 0 if result.get("ii_pass") else 2


def _fire_init(datastreams_dir: Path, selector: str, output_check, concurrency: int,
               stagger_s: float = 3.0) -> int:
    """
    Fire every run matched by `selector` concurrently — the scheduler's fan-out.
    """
    log = logging.getLogger(__name__)
    _, matching = _match_runs(datastreams_dir, selector)
    if not matching:
        print(f"no runs matched {selector}", file=sys.stderr)
        return 1

    workers = max(1, concurrency)
    log.info(
        "firing %d run(s) for %s with concurrency=%d, stagger=%.0fs (first %d): %s",
        len(matching), selector, workers, stagger_s, min(workers, len(matching)),
        [r.name for r in matching],
    )

    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for i, rs in enumerate(matching):
            # Stagger only the initial batch (see docstring); later submits queue.
            if 0 < i < workers and stagger_s > 0:
                time.sleep(stagger_s)
            log.info("submitting %s (%d/%d)", rs.name, i + 1, len(matching))
            futures[pool.submit(runner.run, rs, output_check=output_check)] = rs
        for fut in futures:
            rs = futures[fut]
            try:
                results[rs.name] = bool(fut.result().get("ii_pass"))
            except Exception:  # noqa: BLE001 — runner.run shouldn't raise, but be safe
                log.exception("run %s raised", rs.name)
                results[rs.name] = False

    passed = sum(1 for ok in results.values() if ok)
    failed = len(results) - passed
    log.info("=== fire-init %s complete: %d passed, %d failed ===", selector, passed, failed)
    for name in sorted(results):
        print(f"  {'PASS' if results[name] else 'FAIL'}  {name}", file=sys.stderr)
    return 0 if failed == 0 else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""Fire datastream runs at configured cron times.

Concurrency is bounded by two gates, not a fixed job count:
  1. cores  — cluster-wide: cpu handed out stays <= core_budget.
  2. memory — per-node: each run is placed on the cluster member with the most
              free RAM and pinned there (`target=`), keeping that node's usage
              under a fraction of its RAM. Per-node because a node OOMs on *its*
              own RAM even when the cluster total looks fine. Effective load is
              max(live measured usage, our in-flight reservations).

Launches are staggered so a burst on the same cron tick doesn't hit the
network / S3 / image store all at once.
"""

from __future__ import annotations

import logging
import re
import signal
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from . import runner
from .config import Datastream, ScheduledRun, load_all
from .lxd import LXDClient

log = logging.getLogger(__name__)

# Cluster-wide cpu budget (--core-budget / RDS_LXD_CORE_BUDGET).
TOTAL_HOST_CORES = 512
DEFAULT_CORE_BUDGET = TOTAL_HOST_CORES // 2  # 256

# Per-node memory guard: don't place a run on a member whose RAM would then
# exceed this fraction of its total. 0/None disables (--memory-pct).
DEFAULT_MEMORY_PCT = 0.80

# How often the memory monitor re-samples RAM and wakes memory-blocked waiters.
DEFAULT_MEM_MONITOR_INTERVAL_S = 10.0

# Seconds between consecutive launches, to spread launch-time load. 0 disables.
DEFAULT_STAGGER_S = 10.0

# Threadpool size for the --fire-init fan-out; the scheduler itself sizes from
# the core budget (see build_scheduler).
DEFAULT_MAX_CONCURRENT_RUNS = 20

# Sentinel returned by placement when no member currently has room.
_NO_FIT = object()


_MEM_UNITS_GIB = {
    "": 1.0, "b": 1 / 1024**3,
    "kib": 1 / 1024**2, "kb": 1e3 / 1024**3,
    "mib": 1 / 1024, "mb": 1e6 / 1024**3,
    "gib": 1.0, "gb": 1e9 / 1024**3,
    "tib": 1024.0, "tb": 1e12 / 1024**3,
}
_MEM_RE = re.compile(r"^\s*([\d.]+)\s*([a-zA-Z]*)\s*$")


def parse_mem_gib(value: object) -> float:
    """Parse an LXD-style memory string ('64GiB', '32GB', '512MiB', '8') to GiB.

    Bare numbers are treated as GiB (the unit the YAML configs use). Unknown or
    unparseable values yield 0.0 so a run is never blocked by a bad size string.
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    m = _MEM_RE.match(str(value))
    if not m:
        log.warning("unparseable memory value %r; treating as 0", value)
        return 0.0
    qty, unit = m.group(1), m.group(2).lower()
    factor = _MEM_UNITS_GIB.get(unit)
    if factor is None:
        log.warning("unknown memory unit in %r; treating as 0", value)
        return 0.0
    return float(qty) * factor


class ResourceLimiter:
    """Admit + place runs across cluster members, and space launches.

    Gates: a cluster-wide core budget and a per-node memory ceiling (`mem_pct` *
    that member's RAM). `reserve()` picks the member with the most headroom that
    fits the run and yields it as the target to pin the launch to. Effective
    load is max(measured_used, our_reserved). `members=[None]` (non-clustered)
    or no mem_pct/totals turns the memory gate off and yields None placement.
    """

    def __init__(
        self,
        core_budget: int,
        stagger_s: float = 0.0,
        members: list[str | None] | None = None,
        node_total_gib: dict[str | None, float] | None = None,
        mem_pct: float | None = None,
        measure_used_gib: Callable[[], dict[str | None, float]] | None = None,
        monitor_interval_s: float = DEFAULT_MEM_MONITOR_INTERVAL_S,
    ) -> None:
        self._core_budget = max(1, int(core_budget))
        self._cores_avail = self._core_budget
        self._cond = threading.Condition()
        self._stagger_s = max(0.0, float(stagger_s))
        self._launch_lock = threading.Lock()
        self._last_launch: float | None = None  # monotonic seconds

        self._members: list[str | None] = members if members else [None]
        self._reserved: dict[str | None, float] = {m: 0.0 for m in self._members}
        self._measured: dict[str | None, float] = {m: 0.0 for m in self._members}

        self._measure = measure_used_gib
        node_total_gib = node_total_gib or {}
        self._guard_on = bool(mem_pct and mem_pct > 0 and node_total_gib)
        self._ceiling: dict[str | None, float] = (
            {m: float(node_total_gib.get(m, 0.0)) * float(mem_pct) for m in self._members}
            if self._guard_on else {}
        )
        self._monitor_interval_s = max(1.0, float(monitor_interval_s))
        self._stop = threading.Event()

        if self._guard_on:
            if self._measure is not None:
                try:
                    self._measured.update(self._measure())
                except Exception as e:  # noqa: BLE001
                    log.warning("initial host memory sample failed (%s); starting at 0", e)
                threading.Thread(target=self._monitor, name="rds-mem-monitor", daemon=True).start()
            log.info(
                "per-node memory guard active: %d member(s), ceilings %s GiB (%.0f%%), "
                "live sampling=%s",
                len(self._members),
                {m: round(c) for m, c in self._ceiling.items()},
                float(mem_pct) * 100,
                "on" if self._measure else "off (calculated only)",
            )

    def _monitor(self) -> None:
        while not self._stop.wait(self._monitor_interval_s):
            try:
                used = self._measure()
            except Exception as e:  # noqa: BLE001
                log.warning("host memory sample failed (%s); keeping last values", e)
                continue
            with self._cond:
                self._measured.update(used)
                self._cond.notify_all()  # a node may have freed; re-check waiters
        log.debug("memory monitor stopped")

    def stop(self) -> None:
        self._stop.set()

    def _effective(self, member: str | None) -> float:
        """Current effective load on a member: the larger of what's measured
        live and what we've reserved but may not be measured yet."""
        return max(self._measured.get(member, 0.0), self._reserved.get(member, 0.0))

    def _choose_member(self, mem: float):
        """Pick the best member for a `mem`-GiB run (most headroom that fits),
        or _NO_FIT if none currently has room. Returns None when the guard is
        off (let LXD place). A run too large for any member's ceiling is placed
        on the emptiest member with a warning rather than blocking forever."""
        if not self._guard_on:
            return None
        best = max(self._members, key=lambda m: self._ceiling[m] - self._effective(m))
        best_head = self._ceiling[best] - self._effective(best)
        if best_head >= mem:
            return best
        if mem > max(self._ceiling.values()):
            log.error(
                "run needs %.0f GiB > every member's ceiling (max %.0f GiB); placing on "
                "%s anyway (check sizing / --memory-pct)",
                mem, max(self._ceiling.values()), best,
            )
            return best
        return _NO_FIT

    @contextmanager
    def reserve(self, cores: int, mem_gib: float):
        cores = max(1, min(int(cores), self._core_budget))
        mem = max(0.0, float(mem_gib))
        with self._cond:
            while True:
                target = self._choose_member(mem) if self._cores_avail >= cores else _NO_FIT
                if target is not _NO_FIT:
                    break
                log.debug(
                    "waiting for %d cores / %.0f GiB (avail %d cores; load %s GiB)",
                    cores, mem, self._cores_avail,
                    {m: round(self._effective(m)) for m in self._members},
                )
                self._cond.wait(timeout=self._monitor_interval_s)
            self._cores_avail -= cores
            self._reserved[target] += mem
            log.info(
                "reserved %d cores / %.0f GiB on %s (%d/%d cores; member load now %.0f GiB%s)",
                cores, mem, target if target is not None else "auto",
                self._core_budget - self._cores_avail, self._core_budget,
                self._effective(target),
                f"/{self._ceiling[target]:.0f}" if self._guard_on else "",
            )
        try:
            self._stagger()
            yield target
        finally:
            with self._cond:
                self._cores_avail += cores
                self._reserved[target] -= mem
                self._cond.notify_all()
            log.info(
                "released %d cores / %.0f GiB on %s (%d/%d cores)",
                cores, mem, target if target is not None else "auto",
                self._core_budget - self._cores_avail, self._core_budget,
            )

    def _stagger(self) -> None:
        """Block until at least `stagger_s` has elapsed since the previous
        launch. Serializes the gap across threads so a co-firing batch ramps up
        one run per interval instead of all at once."""
        if self._stagger_s <= 0:
            return
        with self._launch_lock:
            if self._last_launch is not None:
                wait = self._stagger_s - (time.monotonic() - self._last_launch)
                if wait > 0:
                    log.debug("staggering launch by %.1fs", wait)
                    time.sleep(wait)
            self._last_launch = time.monotonic()


def _min_run_cpu(datastreams: list[Datastream]) -> int:
    """Smallest cpu request across all runs — used to size the threadpool so the
    budgets, not the worker count, are the binding limits."""
    cpus = [
        int(r.resources["cpu"])
        for ds in datastreams
        for r in ds.runs
        if r.resources.get("cpu")
    ]
    return min(cpus) if cpus else 1


def _discover_nodes(
    lxd_client: LXDClient, mem_pct: float | None
) -> tuple[list[str | None], dict[str | None, float], Callable[[], dict] | None, float | None]:
    """Return (members, node_total_gib, measure_fn, mem_pct), querying cluster
    members and per-member RAM. If the guard is requested but the host can't
    report memory, returns it disabled (mem_pct=None)."""
    if not (mem_pct and mem_pct > 0):
        return [None], {}, None, None
    try:
        members: list[str | None] = list(lxd_client.cluster_members()) or [None]
        node_total = {m: lxd_client.host_memory_gib(target=m)[1] for m in members}
        measure = lambda: {m: lxd_client.host_memory_gib(target=m)[0] for m in members}  # noqa: E731
        log.info("cluster members: %s; per-node RAM (GiB): %s",
                 [m or "single-host" for m in members], {m: round(t) for m, t in node_total.items()})
        return members, node_total, measure, mem_pct
    except Exception as e:  # noqa: BLE001
        log.warning(
            "host/cluster memory unavailable from LXD (%s); per-node memory guard "
            "DISABLED — only the core budget limits concurrency", e,
        )
        return [None], {}, None, None


def build_scheduler(
    datastreams: list[Datastream],
    lxd_client: LXDClient | None = None,
    output_check: runner.OutputCheck | None = None,
    core_budget: int = DEFAULT_CORE_BUDGET,
    mem_pct: float | None = DEFAULT_MEMORY_PCT,
    stagger_s: float = DEFAULT_STAGGER_S,
    max_workers: int | None = None,
    monitor_interval_s: float = DEFAULT_MEM_MONITOR_INTERVAL_S,
) -> BlockingScheduler:
    """Build (but don't start) a scheduler with all runs registered. The
    threadpool is sized so the budgets, not the worker count, bind; pass
    `max_workers` to override."""
    lxd_client = lxd_client or LXDClient()
    if max_workers is None:
        max_workers = max(1, core_budget // _min_run_cpu(datastreams))

    members, node_total, measure, mem_pct = _discover_nodes(lxd_client, mem_pct)

    limiter = ResourceLimiter(
        core_budget,
        stagger_s=stagger_s,
        members=members,
        node_total_gib=node_total,
        mem_pct=mem_pct,
        measure_used_gib=measure,
        monitor_interval_s=monitor_interval_s,
    )
    sched = BlockingScheduler(
        executors={"default": {"type": "threadpool", "max_workers": max_workers}},
        # misfire_grace_time=None: never drop a late job. Many runs share a cron
        # tick and queue behind the budgets, so a finite grace would drop the
        # ones that wait too long. coalesce collapses a backlog of the SAME job;
        # max_instances=1 stops a slow run overlapping its own next tick.
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": None},
    )

    for ds in datastreams:
        for rs in ds.runs:
            _register(sched, rs, lxd_client, output_check, limiter)
            log.info("registered %s [%s %s]", rs.name, rs.cron, rs.timezone)

    log.info(
        "core budget=%d, memory guard=%s, threadpool max_workers=%d, stagger=%.1fs",
        core_budget,
        f"{mem_pct*100:.0f}% per node" if mem_pct else "off",
        max_workers, stagger_s,
    )
    return sched


def _register(
    sched: BlockingScheduler,
    run_spec: ScheduledRun,
    lxd_client: LXDClient,
    output_check: runner.OutputCheck | None,
    limiter: ResourceLimiter,
) -> None:
    trigger = CronTrigger.from_crontab(run_spec.cron, timezone=run_spec.timezone)
    cores = int(run_spec.resources.get("cpu", 1) or 1)
    mem_gib = parse_mem_gib(run_spec.resources.get("memory"))

    def _job(rs: ScheduledRun = run_spec, cores: int = cores, mem_gib: float = mem_gib) -> None:
        log.info("firing %s (requesting %d cores / %.0f GiB)", rs.name, cores, mem_gib)
        try:
            # Block until a member has room, then pin the run there for its whole
            # lifetime so the node's reservation reflects real load.
            with limiter.reserve(cores, mem_gib) as target:
                log.info("starting %s on %s", rs.name, target if target is not None else "auto")
                runner.run(rs, lxd_client=lxd_client, output_check=output_check, target=target)
        except Exception:
            log.exception("unhandled error in run %s", rs.name)

    sched.add_job(_job, trigger=trigger, id=run_spec.name, name=run_spec.name, replace_existing=True)


def run_forever(
    datastreams_dir: Path,
    env: dict | None = None,
    output_check: runner.OutputCheck | None = None,
    core_budget: int = DEFAULT_CORE_BUDGET,
    mem_pct: float | None = DEFAULT_MEMORY_PCT,
    stagger_s: float = DEFAULT_STAGGER_S,
) -> None:
    """Load configs, start the scheduler, handle SIGTERM cleanly."""
    datastreams = load_all(datastreams_dir, env=env)
    log.info("loaded %d datastream(s): %s", len(datastreams), [d.name for d in datastreams])
    total_runs = sum(len(d.runs) for d in datastreams)
    log.info(
        "registering %d scheduled runs (core budget %d, memory guard %s)",
        total_runs, core_budget, f"{mem_pct*100:.0f}% per node" if mem_pct else "off",
    )

    sched = build_scheduler(
        datastreams,
        output_check=output_check,
        core_budget=core_budget,
        mem_pct=mem_pct,
        stagger_s=stagger_s,
    )

    def _handle(signum, _frame):
        log.info("signal %d received; shutting down", signum)
        sched.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    log.info("scheduler starting")
    sched.start()

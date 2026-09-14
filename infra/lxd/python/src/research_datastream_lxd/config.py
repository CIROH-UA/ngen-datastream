"""Datastream definition loader.

One YAML file per directory declares schedule groups; each group expands to N
scheduled runs (one per init cycle, fanned out per VPU/member). Replaces the
AWS aws_scheduler_schedule resources from each datastream's schedules.tf.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ScheduledRun:
    """One concrete scheduled run: a specific init cycle in a specific group."""

    datastream: str                # e.g. "forcing"
    group: str                     # e.g. "short_range"
    init: str                      # e.g. "06"
    cron: str                      # "minute hour day-of-month month day-of-week"
    timezone: str                  # IANA tz name
    resources: dict[str, Any]      # cpu, memory, disk, image
    run_options: dict[str, Any]    # timeout_s, n_retries_allowed, check_output, delete_instance
    template_path: Path            # jinja-ish .tpl file with commands + run config
    context: dict[str, Any]        # template variables (run_type_l, member_suffix, ...)
    vpu: str | None = None         # set when the group fans out per-VPU (cfe-nom); None for forcing
    member: str = ""               # ensemble member id; "" when the group has no members

    @property
    def name(self) -> str:
        parts = [self.datastream, self.group, f"init{self.init}"]
        if self.vpu is not None:
            parts.append(f"vpu{self.vpu}")
        if self.member:
            parts.append(f"mem{self.member}")
        return "_".join(parts)


@dataclass
class Datastream:
    name: str
    path: Path
    template_path: Path
    defaults: dict[str, Any] = field(default_factory=dict)
    runs: list[ScheduledRun] = field(default_factory=list)


def _cron(hour_expr: str, minute_expr: str, init: int, member: int = 0) -> str:
    """Render a cron line from hour/minute arithmetic exprs (e.g.
    hour_expr="({init} + 1) % 24"), mirroring the AWS schedules.tf cron formulas.
    """
    # Restricted eval: only init/member names + floor, arithmetic only.
    import math
    allowed = {"__builtins__": {}}
    scope = {"init": init, "member": member, "floor": math.floor}
    hour = eval(hour_expr.format(init=init, member=member), allowed, scope)  # noqa: S307
    minute = eval(str(minute_expr).format(init=init, member=member), allowed, scope)  # noqa: S307
    return f"{int(minute) % 60} {int(hour) % 24} * * *"


def load_datastream(ds_dir: Path, env: dict[str, Any] | None = None) -> Datastream:
    """Load a single datastream from a directory containing `<name>.yaml`."""
    env = env or {}
    yaml_candidates = list(ds_dir.glob("*.yaml"))
    if not yaml_candidates:
        raise FileNotFoundError(f"no YAML definition in {ds_dir}")
    if len(yaml_candidates) > 1:
        raise ValueError(f"multiple YAML definitions in {ds_dir}: {yaml_candidates}")
    spec_path = yaml_candidates[0]
    spec = yaml.safe_load(spec_path.read_text())

    name = spec["name"]
    template_path = ds_dir / spec["template"]
    if not template_path.exists():
        raise FileNotFoundError(f"template not found: {template_path}")

    defaults = spec.get("defaults", {})
    timezone = spec.get("timezone", "UTC")

    ds = Datastream(name=name, path=ds_dir, template_path=template_path, defaults=defaults)

    # Optional table mapping an AWS instance type -> LXD cpu/memory, so a
    # per-VPU `vpus:` map can reuse AWS instance types verbatim.
    instance_types = spec.get("instance_types", {})

    for group_name, group in spec.get("schedule_groups", {}).items():
        base_resources = {**defaults.get("resources", {}), **group.get("resources", {})}
        run_options = {**defaults.get("run_options", {}), **group.get("run_options", {})}
        hour_expr = group.get("hour_expr", "{init}")
        minute_expr = group.get("minute_expr", "0")
        volume_size = group.get("volume_size")  # GiB; mirrors AWS EBS volume_size

        # Two optional fan-out dimensions on top of init_cycles:
        #   vpus:    {vpu -> instance_type} — one run per VPU, sized per VPU.
        #   members: [ids]                  — one run per ensemble member.
        # Forcing declares neither, so it stays one run per init (unchanged).
        vpus = group.get("vpus")
        vpu_items = list(vpus.items()) if vpus else [(None, None)]
        members = group.get("members")
        member_items = [str(m) for m in members] if members else [None]

        for init in group["init_cycles"]:
            for vpu, instance_type in vpu_items:
                resources = dict(base_resources)
                if instance_type is not None:
                    itype = instance_types.get(instance_type)
                    if itype is None:
                        raise KeyError(
                            f"{spec_path}: group '{group_name}' references instance type "
                            f"'{instance_type}' (vpu {vpu}) absent from top-level instance_types"
                        )
                    resources["cpu"] = itype["cpu"]
                    resources["memory"] = itype["memory"]
                if volume_size is not None:
                    resources["disk"] = f"{volume_size}GiB"

                # nprocs for the datastream tools: they default to
                # os.cpu_count() (host cores, ignoring the cgroup), so pass it
                # explicitly. cpu-1 leaves a core for the OS (ngen convention).
                cpu = resources.get("cpu")
                nprocs = (cpu - 1) if isinstance(cpu, int) and cpu > 1 else None

                for member in member_items:
                    context = {
                        "init": init,
                        "group": group_name,
                        **defaults.get("context", {}),
                        **group.get("context", {}),
                        **env,
                    }
                    if vpu is not None:
                        context["vpu"] = vpu
                    if nprocs is not None:
                        context["nprocs"] = nprocs
                    if member is not None:
                        # member_suffix/_path mirror the AWS schedules.tf locals.
                        context["member"] = member
                        context["member_suffix"] = f"_{member}"
                        context["member_path"] = f"/{member}"
                    else:
                        context.setdefault("member", "")
                        context.setdefault("member_suffix", "")
                        context.setdefault("member_path", "")

                    ds.runs.append(
                        ScheduledRun(
                            datastream=name,
                            group=group_name,
                            init=init,
                            cron=_cron(hour_expr, minute_expr, int(init), int(member) if member else 0),
                            timezone=timezone,
                            resources=resources,
                            run_options=run_options,
                            template_path=template_path,
                            context=context,
                            vpu=vpu,
                            member=member or "",
                        )
                    )

    return ds


def load_all(datastreams_dir: Path, env: dict[str, Any] | None = None) -> list[Datastream]:
    """Load every datastream under `datastreams_dir/<name>/<name>.yaml`."""
    if not datastreams_dir.exists():
        raise FileNotFoundError(f"datastreams dir not found: {datastreams_dir}")
    out: list[Datastream] = []
    for child in sorted(datastreams_dir.iterdir()):
        if child.is_dir() and list(child.glob("*.yaml")):
            out.append(load_datastream(child, env=env))
    return out

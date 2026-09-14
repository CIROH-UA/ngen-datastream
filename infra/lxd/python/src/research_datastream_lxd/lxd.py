from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import pylxd
from pylxd.exceptions import LXDAPIException, NotFound
from requests.exceptions import ConnectionError as RequestsConnectionError

log = logging.getLogger(__name__)

DEFAULT_EXEC_UID = 0
DEFAULT_EXEC_GID = 0
DEFAULT_EXEC_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
DEFAULT_EXEC_HOME = "/root"
DEFAULT_EXEC_CWD = "/"
EXEC_WAIT_TIMEOUT_S = 30
EXEC_STDOUT_FILE = "/tmp/.rds_exec.out"
EXEC_STDERR_FILE = "/tmp/.rds_exec.err"

@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0


def _resolve_verify(env_value: str | None, default: bool | str) -> bool | str:
    """
    Interpret LXD_VERIFY: unset -> `default`; false/0/no -> False (skip,
    insecure); true/1/yes -> True (system CA); anything else -> a cert path to pin."""
    if env_value is None:
        return default
    lowered = env_value.strip().lower()
    if lowered in ("false", "0", "no"):
        return False
    if lowered in ("true", "1", "yes"):
        return True
    return env_value


class LXDClient:
    """Wraps a pylxd.Client. Defaults to the local LXD unix socket; for remote
    use pass endpoint + cert or set LXD_ENDPOINT / LXD_CERT_FILE / LXD_KEY_FILE /
    LXD_VERIFY. See _resolve_verify for LXD_VERIFY semantics."""

    def __init__(
        self,
        endpoint: str | None = None,
        cert: tuple[str, str] | None = None,
        verify: bool | str = True,
        project: str | None = None,
    ):
        endpoint = endpoint or os.environ.get("LXD_ENDPOINT")
        lxd_project = project or os.environ.get("LXD_PROJECT") or None
        if endpoint:
            if cert is None:
                cert_file = os.environ.get("LXD_CERT_FILE")
                key_file = os.environ.get("LXD_KEY_FILE")
                if cert_file and key_file:
                    cert = (cert_file, key_file)
            verify = _resolve_verify(os.environ.get("LXD_VERIFY"), verify)
            if verify is False:
                # Silence the per-request InsecureRequestWarning.
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self._client = pylxd.Client(endpoint=endpoint, cert=cert, verify=verify, project=lxd_project)
        else:
            self._client = pylxd.Client(project=lxd_project)

    # ---- lifecycle ------------------------------------------------------

    def launch_instance(
        self,
        name: str,
        image: str,
        profiles: list[str] | None = None,
        resources: dict[str, Any] | None = None,
        wait: bool = True,
        running_timeout_s: int = 300,
        target: str | None = None,
    ):
        """Create and start a new instance, returning the pylxd Instance.

        `resources` is a flat dict ({cpu, memory, disk, ...}) translated to LXD
        config + devices. `target` pins the instance to a cluster member.
        """
        config: dict[str, str] = {}
        devices: dict[str, dict[str, str]] = {}
        resources = resources or {}
        config["security.nesting"] = "true"
        config["limits.cpu"] = str(resources["cpu"])
        config["limits.memory"] = str(resources["memory"])
        devices["root"] = {
            "type": "disk",
            "path": "/",
            "pool": resources.get("storage_pool", "default"),
            "size": str(resources["disk"]),
        }

        # image format: "ubuntu:22.04" -> server=ubuntu, alias=22.04
        if ":" in image:
            server_alias, alias = image.split(":", 1)
            image_servers = {
                "ubuntu": "https://cloud-images.ubuntu.com/releases",
                "images": "https://images.linuxcontainers.org",
            }
            source: dict[str, str] = {
                "type": "image",
                "protocol": "simplestreams",
                "server": image_servers.get(server_alias, image_servers["ubuntu"]),
                "alias": alias,
            }
        else:
            # LXD instance create requires fingerprint, not alias.
            # Resolve the alias here so the create spec is unambiguous.
            img = self._client.images.get_by_alias(image)
            source = {"type": "image", "fingerprint": img.fingerprint}

        instance_type = resources.get("type", "virtual-machine")
        spec = {
            "name": name,
            "type": instance_type,
            "source": source,
            "profiles": profiles or ["default"],
            "config": config,
            "devices": devices,
        }

        log.info("launching LXD instance %s (image=%s, target=%s)", name, image, target or "auto")
        instance = self._client.instances.create(spec, wait=True, target=target)
        instance.start(wait=True)

        if wait:
            self._wait_for_running(instance, timeout_s=running_timeout_s)
        return instance

    def _wait_for_running(self, instance, timeout_s: int = 300) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            instance.sync()
            status = instance.status.lower()
            if status == "running":
                log.info("instance %s is running", instance.name)
                return
            log.info("instance %s status: %s", instance.name, status)
            time.sleep(2)
        raise TimeoutError(f"instance {instance.name} did not reach running in {timeout_s}s")

    # ---- exec -----------------------------------------------------------

    def execute(
        self,
        instance,
        commands: list[str],
        timeout_s: int = 86400,
        environment: dict[str, str] | None = None,
        user: int | None = DEFAULT_EXEC_UID,
        group: int | None = DEFAULT_EXEC_GID,
        cwd: str = DEFAULT_EXEC_CWD,
    ) -> ExecResult:
        """
        Run shell commands inside the instance and block until completion.
        """
        env = dict(environment or {})
        env.setdefault("PATH", DEFAULT_EXEC_PATH)
        env.setdefault("HOME", DEFAULT_EXEC_HOME)
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        exit_code = 0
        t0 = time.time()
        for i, command in enumerate(commands):
            log.info(
                "exec %d/%d on %s (timeout=%ds, uid=%s gid=%s): %s",
                i + 1, len(commands), instance.name, timeout_s, user, group, command[:200],
            )
            time.sleep(5)  # stagger commands within a run to ease S3 request pressure
            exit_code, out_i, err_i = self._exec_polling(
                instance, command, env, user, group, cwd, timeout_s,
            )
            stdout_parts.append(out_i)
            stderr_parts.append(err_i)
            log.info(
                "exec %d/%d on %s finished in %.1fs rc=%d",
                i + 1, len(commands), instance.name, time.time() - t0, exit_code,
            )
            if exit_code != 0:
                break

        return ExecResult(exit_code, "".join(stdout_parts), "".join(stderr_parts))

    def _exec_polling(
        self,
        instance,
        command: str,
        env: dict[str, str],
        user: int | None,
        group: int | None,
        cwd: str,
        timeout_s: int,
    ) -> tuple[int, str, str]:
        """
        Poll instance indefinitely for command status
        """
        from pylxd.models.operation import Operation

        # Redirect output to files we pull via the files API afterward.
        wrapped = f"{{ {command} ; }} > {EXEC_STDOUT_FILE} 2> {EXEC_STDERR_FILE}"
        response = instance.api["exec"].post(json={
            "command": ["/bin/bash", "-lc", wrapped],
            "environment": env,
            "wait-for-websocket": False,
            "interactive": False,
            "user": user,
            "group": group,
            "cwd": cwd,
        })
        op_id = Operation.extract_operation_id(response.json()["operation"])

        t0 = time.time()
        op_meta: dict[str, Any] | None = None
        while True:
            try:
                resp = instance.client.api.operations[op_id].wait.get(
                    params={"timeout": EXEC_WAIT_TIMEOUT_S}
                )
                op_meta = resp.json()["metadata"]
                # LXD op status: <200 running, >=200 terminal (success or failure).
                if op_meta.get("status_code", 0) >= 200:
                    break
            except NotFound:
                # Op reaped before we read it; trust rc 0 and recover logs below.
                log.warning(
                    "exec op %s on %s already reaped; treating as complete (rc unknown -> 0)",
                    op_id, instance.name,
                )
                op_meta = None
                break
            except LXDAPIException as e:
                # "context deadline exceeded" = the ?timeout slice elapsed with the
                # op still running ("ask again"), not a failure. Other errors are real.
                if "context deadline exceeded" not in str(e).lower():
                    raise
                log.debug("exec op %s still running after %ds slice; re-waiting",
                          op_id, EXEC_WAIT_TIMEOUT_S)
            except RequestsConnectionError as e:
                log.warning("wait on exec op %s on %s dropped (%s); retrying",
                            op_id, instance.name, e)
                time.sleep(2)
            if time.time() - t0 > timeout_s:
                raise TimeoutError(
                    f"exec on {instance.name} exceeded {timeout_s}s (op {op_id} still running)"
                )

        # Output files persist independent of the op record, readable either way.
        stdout = self._read_instance_file(instance, EXEC_STDOUT_FILE)
        stderr = self._read_instance_file(instance, EXEC_STDERR_FILE)

        if op_meta is None:
            # Reaped before we read the rc (see NotFound above); trust rc 0.
            return 0, stdout, stderr

        inner = op_meta.get("metadata") or {}
        # The command's own rc (the op can be "Success" with a non-zero command).
        exit_code = int(inner.get("return", -1))
        return exit_code, stdout, stderr

    def _read_instance_file(self, instance, path: str) -> str:
        """Read a file from inside the instance via the files API."""
        try:
            data = instance.files.get(path)
        except (RequestsConnectionError, LXDAPIException, NotFound) as e:
            log.warning("could not read %s on %s: %s", path, instance.name, e)
            return ""
        if isinstance(data, (bytes, bytearray)):
            return data.decode("utf-8", errors="replace")
        return str(data)

    # ---- host metrics ---------------------------------------------------

    def cluster_members(self) -> list[str]:
        """Return cluster member names, or [] if this LXD isn't clustered."""
        try:
            cl = self._client.api.cluster.get().json()["metadata"]
            if not cl.get("enabled"):
                return []
            return [m.server_name for m in self._client.cluster.members.all()]
        except Exception as e:  # noqa: BLE001 — any failure: fall back to single host
            log.warning("could not enumerate cluster members (%s); treating as single host", e)
            return []

    def host_memory_gib(self, target: str | None = None) -> tuple[float, float]:
        """Return (used, total) RAM in GiB for one host (cluster member `target`,
        else the member serving the request). `used` is 0.0 if unreported."""
        params = {"target": target} if target else None
        mem = self._client.api.resources.get(params=params).json()["metadata"]["memory"]
        if "total" not in mem:
            raise KeyError("LXD /1.0/resources memory lacks total")
        used = float(mem["used"]) / 1024**3 if "used" in mem else 0.0
        return used, float(mem["total"]) / 1024**3

    # ---- teardown -------------------------------------------------------

    def stop_and_delete(self, instance_name: str, delete_disk: bool = True, attempts: int = 3) -> None:
        """Stop and delete the instance, retrying on transient API errors."""
        for attempt in range(1, attempts + 1):
            try:
                instance = self._client.instances.get(instance_name)
            except NotFound:
                log.info("instance %s already gone", instance_name)
                return
            except RequestsConnectionError as e:
                log.warning("teardown attempt %d/%d: lookup of %s hit %s; retrying",
                            attempt, attempts, instance_name, e)
                time.sleep(5)
                continue

            try:
                instance.sync()
                if instance.status.lower() != "stopped":
                    log.info("stopping %s (attempt %d/%d)", instance_name, attempt, attempts)
                    instance.stop(force=True, wait=True)
                if delete_disk:
                    log.info("deleting %s", instance_name)
                    instance.delete(wait=True)
                else:
                    log.info("leaving %s stopped (delete_disk=False)", instance_name)
                return
            except NotFound:
                log.info("instance %s gone during teardown", instance_name)
                return
            except (RequestsConnectionError, LXDAPIException) as e:
                log.warning("teardown attempt %d/%d for %s hit %s; retrying",
                            attempt, attempts, instance_name, e)
                time.sleep(5)

        log.error(
            "FAILED to tear down %s after %d attempts; instance may be lingering — "
            "clean up manually: lxc delete -f %s", instance_name, attempts, instance_name,
        )

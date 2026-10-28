#!/usr/bin/env python3
"""Fail-closed updater for the single-host live Compose deployment."""
from __future__ import annotations

import argparse
from contextlib import closing
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPOSITORY = "DerPyro/wolfs-garage"
GIT_URL = "https://github.com/DerPyro/wolfs-garage.git"
API_ROOT = "https://api.github.com/repos/DerPyro/wolfs-garage"
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
IMAGE_PREFIX_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,180}$")


class UpdateError(RuntimeError):
    pass


def load_config(env_file):
    """Read simple KEY=value config without shell expansion or code execution."""
    values = {}
    for line_number, raw_line in enumerate(Path(env_file).read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise UpdateError(f"Invalid updater config line {line_number}.")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not value or "\x00" in value:
            raise UpdateError(f"Invalid updater config line {line_number}.")
        if key in values:
            raise UpdateError(f"Duplicate updater config key {key}.")
        values[key] = value

    required = {
        "GARAGE_COMPOSE_FILE", "GARAGE_RELEASE_ROOT", "GARAGE_UPDATE_STATE_DIR",
        "GARAGE_DATA_VOLUME", "GARAGE_ORIGIN_NETWORK", "GARAGE_PUBLIC_ORIGIN",
        "GARAGE_IMAGE_PREFIX", "GARAGE_HEALTH_TIMEOUT",
        "GARAGE_MAINTENANCE_PREPARE", "GARAGE_MAINTENANCE_FINISH",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise UpdateError("Missing updater config keys: " + ", ".join(missing))
    for key in ("GARAGE_COMPOSE_FILE", "GARAGE_RELEASE_ROOT", "GARAGE_UPDATE_STATE_DIR",
                "GARAGE_MAINTENANCE_PREPARE", "GARAGE_MAINTENANCE_FINISH"):
        if not Path(values[key]).is_absolute():
            raise UpdateError(f"{key} must be an absolute path.")
    for key in ("GARAGE_DATA_VOLUME", "GARAGE_ORIGIN_NETWORK"):
        if not NAME_PATTERN.fullmatch(values[key]):
            raise UpdateError(f"Invalid {key}.")
    if not IMAGE_PREFIX_PATTERN.fullmatch(values["GARAGE_IMAGE_PREFIX"]):
        raise UpdateError("Invalid GARAGE_IMAGE_PREFIX.")
    if not re.fullmatch(r"[0-9]{1,4}", values["GARAGE_HEALTH_TIMEOUT"]):
        raise UpdateError("Invalid GARAGE_HEALTH_TIMEOUT.")
    if not 10 <= int(values["GARAGE_HEALTH_TIMEOUT"]) <= 900:
        raise UpdateError("GARAGE_HEALTH_TIMEOUT must be between 10 and 900 seconds.")
    from urllib.parse import urlsplit
    origin = urlsplit(values["GARAGE_PUBLIC_ORIGIN"])
    if origin.scheme != "https" or not origin.hostname or origin.username or origin.password or origin.path not in ("", "/") or origin.query or origin.fragment:
        raise UpdateError("GARAGE_PUBLIC_ORIGIN must be a single HTTPS origin.")
    return values


def _validate_root_managed_file(file_path, *, private=False, executable=False):
    """Reject symlinks and writable path components for root-executed inputs."""
    path = Path(file_path).absolute()
    for component in reversed(path.parents):
        try:
            component_stat = component.lstat()
        except OSError as exc:
            raise UpdateError("Root-managed path is unavailable.") from exc
        if (not stat.S_ISDIR(component_stat.st_mode) or component_stat.st_uid != 0
                or component_stat.st_mode & 0o022):
            raise UpdateError("Root-managed path parents must be root-owned and not group/other writable.")
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise UpdateError("Root-managed file is unavailable.") from exc
    if (not stat.S_ISREG(file_stat.st_mode) or file_stat.st_uid != 0
            or file_stat.st_mode & 0o022
            or (private and file_stat.st_mode & 0o077)
            or (executable and not file_stat.st_mode & 0o111)):
        raise UpdateError("Root-managed file has unsafe ownership or permissions.")


def validate_root_config_file(env_file):
    """Require the production config to be a private, root-owned regular file."""
    path = Path(env_file)
    _validate_root_managed_file(path, private=True)


def _github_json(url):
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "wolfs-garage-live-updater"})
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except Exception as exc:
        raise UpdateError("GitHub API check failed.") from exc


def github_main_sha():
    value = _github_json(f"{API_ROOT}/commits/main")
    sha = value.get("sha") if isinstance(value, dict) else None
    if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
        raise UpdateError("GitHub returned an invalid main commit.")
    return sha


def checks_succeeded(sha):
    if not isinstance(sha, str) or not SHA_PATTERN.fullmatch(sha):
        raise UpdateError("Invalid source commit SHA.")
    query = urlencode({"head_sha": sha, "event": "push", "branch": "main", "status": "completed", "per_page": 100})
    value = _github_json(f"{API_ROOT}/actions/workflows/checks.yml/runs?{query}")
    runs = value.get("workflow_runs") if isinstance(value, dict) else None
    if not isinstance(runs, list):
        raise UpdateError("GitHub returned invalid workflow data.")
    matching = [run for run in runs if isinstance(run, dict)
                and run.get("head_sha") == sha and run.get("event") == "push"
                and run.get("head_branch") == "main" and run.get("name") == "Checks"]
    if not matching:
        return False
    return matching[0].get("status") == "completed" and matching[0].get("conclusion") == "success"


def _run(args, *, env=None, capture=False, timeout=1800):
    try:
        result = subprocess.run(args, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                                stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
                                timeout=timeout, check=False, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"Command failed: {Path(args[0]).name}.") from exc
    if result.returncode:
        raise UpdateError(f"Command failed: {Path(args[0]).name} (exit {result.returncode}).")
    return result.stdout.strip() if capture else ""


def _compose(config, image, *args, capture=False):
    env = os.environ.copy()
    env["GARAGE_IMAGE"] = image
    return _run(["docker", "compose", "--project-name", "wolfs-garage-live",
                 "--env-file", config["GARAGE_ENV_FILE"], "-f", config["GARAGE_COMPOSE_FILE"], *args],
                env=env, capture=capture, timeout=1800)


def _safe_hook(path):
    hook = Path(path)
    _validate_root_managed_file(hook, executable=True)
    _run([str(hook)], timeout=120)


def _compose_environment(config, env_file):
    result = dict(config)
    result["GARAGE_ENV_FILE"] = str(Path(env_file))
    return result


def _running_image(config, compose_config):
    container = _compose(compose_config, config["GARAGE_IMAGE_PREFIX"] + ":bootstrap", "ps", "-q", "garage_live", capture=True)
    if not container or "\n" in container:
        raise UpdateError("Expected exactly one running garage_live container.")
    image = _run(["docker", "inspect", "--format", "{{.Config.Image}}", container], capture=True)
    if not image:
        raise UpdateError("Could not identify the current container image.")
    return image, container


def _health(container, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = _run(["docker", "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", container], capture=True)
        if state == "healthy":
            return True
        if state == "unhealthy" or state == "none":
            return False
        time.sleep(2)
    return False


def _service_container(compose_config, image):
    value = _compose(compose_config, image, "ps", "-q", "garage_live", capture=True)
    if not value or "\n" in value:
        raise UpdateError("Could not find the garage_live container.")
    return value


def _backup_from_volume(image, volume, workdir, filename):
    _run(["docker", "run", "--rm", "--network", "none", "--user", "0:0", "--read-only",
          "--cap-drop=ALL", "--cap-add=DAC_OVERRIDE",
          "--security-opt=no-new-privileges", "--pids-limit", "128",
          "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m",
          "--mount", f"type=volume,src={volume},dst=/var/lib/wolfs-garage,readonly",
          "--mount", f"type=bind,src={workdir},dst=/backup",
          "--env", "GARAGE_DB=/var/lib/wolfs-garage/garage.sqlite3", image,
          "python", "-m", "wolfs_garage", "backup", f"/backup/{filename}"], timeout=300)


def _schema(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
            rows = db.execute("SELECT schema FROM meta").fetchall()
            if len(rows) != 1 or type(rows[0][0]) is not int:
                raise UpdateError("Database schema metadata is invalid.")
            return rows[0][0]
    except sqlite3.Error as exc:
        raise UpdateError("Could not inspect database schema.") from exc


def _image_schema(image):
    value = _run(["docker", "run", "--rm", "--network", "none", "--read-only",
                  "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit", "128", image,
                  "python", "-c", "from wolfs_garage.store import SCHEMA; print(SCHEMA)"], capture=True, timeout=60)
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise UpdateError("Candidate image did not report a valid schema.")
    return int(value)


def _candidate_preflight(old_image, candidate, config):
    state_dir = Path(config["GARAGE_UPDATE_STATE_DIR"])
    with tempfile.TemporaryDirectory(prefix="preflight-", dir=state_dir) as temp_name:
        workdir = Path(temp_name)
        _backup_from_volume(old_image, config["GARAGE_DATA_VOLUME"], workdir, "source.sqlite3")
        original_schema = _schema(workdir / "source.sqlite3")
        shutil.copyfile(workdir / "source.sqlite3", workdir / "candidate.sqlite3")
        os.chmod(workdir / "candidate.sqlite3", 0o600)
        candidate_schema = _image_schema(candidate)
        if original_schema != candidate_schema or candidate_schema not in {3, 4}:
            raise UpdateError("Automatic update blocked: live and candidate schemas must match supported schema 3 or 4.")
        _run(["docker", "run", "--rm", "--network", "none", "--user", "0:0", "--read-only",
              "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit", "128",
              "--mount", f"type=bind,src={workdir},dst=/work",
              "--env", "GARAGE_DB=/work/candidate.sqlite3", candidate,
              "python", "-m", "wolfs_garage", "upgrade-db", "/work/preflight-backup.sqlite3"], timeout=300)
        _run(["docker", "run", "--rm", "--network", "none", "--user", "0:0", "--read-only",
              "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit", "128",
              "--mount", f"type=bind,src={workdir},dst=/work",
              "--env", "GARAGE_DB=/work/candidate.sqlite3", candidate,
              "python", "-m", "wolfs_garage", "check-db"], timeout=300)
        if _schema(workdir / "candidate.sqlite3") != candidate_schema:
            raise UpdateError("Automatic update blocked: isolated candidate check changed the database schema.")
        return candidate_schema


def _write_active_sha(state_dir, sha):
    target = Path(state_dir) / "active-main-sha"
    temp = Path(state_dir) / f".active-main-sha-{os.getpid()}"
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as output:
            fd = -1
            output.write(sha + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, target)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise


def _deploy_candidate(candidate, old_image, sha, config, compose_config, candidate_schema=None):
    prepare = config["GARAGE_MAINTENANCE_PREPARE"]
    finish = config["GARAGE_MAINTENANCE_FINISH"]
    prepare_attempted = False
    release_attempted = False
    backup_path = Path(config["GARAGE_UPDATE_STATE_DIR"]) / f"live-before-{time.time_ns()}-{sha[:12]}.sqlite3"
    timeout = int(config["GARAGE_HEALTH_TIMEOUT"])
    old_stop_attempted = False
    candidate_start_attempted = False
    try:
        prepare_attempted = True
        _safe_hook(prepare)
        old_stop_attempted = True
        _compose(compose_config, old_image, "stop", "garage_live")
        with tempfile.TemporaryDirectory(prefix="live-backup-", dir=config["GARAGE_UPDATE_STATE_DIR"]) as temp:
            _backup_from_volume(old_image, config["GARAGE_DATA_VOLUME"], Path(temp), backup_path.name)
            moved = Path(temp) / backup_path.name
            os.link(moved, backup_path, follow_symlinks=False)
        old_schema = _schema(backup_path)
        if candidate_schema is None:
            candidate_schema = _image_schema(candidate)
        if (old_schema != candidate_schema or old_schema not in {3, 4}
                or candidate_schema not in {3, 4}):
            raise UpdateError("Automatic update blocked: live and candidate schemas must match supported schema 3 or 4.")

        candidate_start_attempted = True
        _compose(compose_config, candidate, "up", "-d", "--no-deps", "garage_live")
        container = _service_container(compose_config, candidate)
        if not _health(container, timeout):
            raise UpdateError("Candidate container did not become healthy.")
        _run(["docker", "exec", container, "python", "-m", "wolfs_garage", "check-db"], timeout=120)
        if github_main_sha() != sha or not checks_succeeded(sha):
            raise UpdateError("Source stopped being the latest tested main commit during deployment.")
        release_attempted = True
        _safe_hook(finish)
        return
    except BaseException:
        if prepare_attempted and not release_attempted and (old_stop_attempted or candidate_start_attempted):
            if candidate_start_attempted:
                try:
                    _compose(compose_config, candidate, "stop", "garage_live")
                except Exception:
                    pass
            try:
                _compose(compose_config, old_image, "up", "-d", "--no-deps", "garage_live")
                old_container = _service_container(compose_config, old_image)
                if _health(old_container, timeout):
                    _run(["docker", "exec", old_container, "python", "-m", "wolfs_garage", "check-db"], timeout=120)
                    _safe_hook(finish)
            except Exception:
                # Leave proxy maintenance enabled if the prior service cannot
                # be proven healthy; the database and checked backup are kept.
                pass
        elif prepare_attempted and not release_attempted:
            try:
                _safe_hook(finish)
            except Exception:
                pass
        raise


def update_once(config, env_file):
    config = _compose_environment(config, env_file)
    state_dir = Path(config["GARAGE_UPDATE_STATE_DIR"])
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_stat = state_dir.lstat()
    if (not stat.S_ISDIR(state_stat.st_mode) or state_stat.st_mode & 0o077
            or (os.geteuid() == 0 and state_stat.st_uid != 0)):
        raise UpdateError("Updater state directory must be owned by the updater and private.")
    os.chmod(state_dir, 0o700)
    docker_config = state_dir / "docker"
    docker_config.mkdir(mode=0o700, exist_ok=True)
    docker_config_stat = docker_config.lstat()
    if (not stat.S_ISDIR(docker_config_stat.st_mode) or docker_config_stat.st_mode & 0o077
            or (os.geteuid() == 0 and docker_config_stat.st_uid != 0)):
        raise UpdateError("Docker config directory must be owned by the updater and private.")
    os.chmod(docker_config, 0o700)
    lock_path = state_dir / "update.lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("An updater run is already active.")
        os.close(lock_fd)
        return False
    try:
        sha = github_main_sha()
        active_path = state_dir / "active-main-sha"
        try:
            active_sha = active_path.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            active_sha = ""
        if active_sha == sha:
            actual_image, active_container = _running_image(config, config)
            expected_image = f"{config['GARAGE_IMAGE_PREFIX']}:{sha}"
            if (actual_image == expected_image
                    and _health(active_container, int(config["GARAGE_HEALTH_TIMEOUT"]))):
                print(f"Latest tested main already active and healthy: {sha}.")
                return False
            print("Recorded active release differs from the running healthy image; checking for a safe repair.")
        if not checks_succeeded(sha):
            print(f"No completed successful Checks push for main {sha}; no update.")
            return False

        release_root = Path(config["GARAGE_RELEASE_ROOT"])
        release_root.mkdir(mode=0o755, parents=True, exist_ok=True)
        release = release_root / sha
        if not release.exists():
            temp = Path(tempfile.mkdtemp(prefix=f".{sha}-", dir=release_root))
            try:
                _run(["git", "clone", "--no-checkout", GIT_URL, str(temp)], timeout=600)
                _run(["git", "-C", str(temp), "checkout", "--detach", sha], timeout=120)
                checked = _run(["git", "-C", str(temp), "rev-parse", "HEAD"], capture=True)
                if checked != sha:
                    raise UpdateError("Checkout does not match validated source SHA.")
                os.replace(temp, release)
            except BaseException:
                shutil.rmtree(temp, ignore_errors=True)
                raise
        else:
            checked = _run(["git", "-C", str(release), "rev-parse", "HEAD"], capture=True)
            if checked != sha:
                raise UpdateError("Existing release checkout does not match validated source SHA.")

        candidate = f"{config['GARAGE_IMAGE_PREFIX']}:{sha}"
        _run(["docker", "build", "--label", f"org.opencontainers.image.revision={sha}",
              "-f", str(release / "deploy/Dockerfile.standalone"), "-t", candidate, str(release)], timeout=1800)
        old_image, old_container = _running_image(config, config)
        candidate_schema = _candidate_preflight(old_image, candidate, config)
        if github_main_sha() != sha or not checks_succeeded(sha):
            print(f"Main moved from {sha} before deployment; retrying on the next timer tick.")
            return False
        if old_image == candidate:
            if not _health(old_container, int(config["GARAGE_HEALTH_TIMEOUT"])):
                raise UpdateError("Already-running candidate is not healthy.")
            _run(["docker", "exec", old_container, "python", "-m", "wolfs_garage", "check-db"], timeout=120)
            _safe_hook(config["GARAGE_MAINTENANCE_FINISH"])
            _write_active_sha(state_dir, sha)
            print(f"Latest tested main is already running: {sha}.")
            return False
        _deploy_candidate(candidate, old_image, sha, config, config, candidate_schema)
        _write_active_sha(state_dir, sha)
        print(f"Updated Wolfs Garage to tested main {sha}.")
        return True
    finally:
        os.close(lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update Wolfs Garage from the latest tested main commit")
    parser.add_argument("--env-file", default="/etc/wolfs-garage/live.env")
    parser.add_argument("--once", action="store_true", help="Run one update check and exit")
    args = parser.parse_args(argv)
    try:
        validate_root_config_file(args.env_file)
        config = load_config(args.env_file)
        _validate_root_managed_file(config["GARAGE_COMPOSE_FILE"])
        update_once(config, args.env_file)
    except UpdateError as exc:
        print(f"Wolfs Garage updater stopped safely: {exc}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f"Wolfs Garage updater stopped safely ({type(exc).__name__}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail-closed updater for the isolated synthetic public demo."""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


_SPEC = importlib.util.spec_from_file_location("garage_live_updater", Path(__file__).with_name("update-live.py"))
_LIVE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LIVE)
UpdateError = _LIVE.UpdateError
github_main_sha = _LIVE.github_main_sha
checks_succeeded = _LIVE.checks_succeeded
_run = _LIVE._run
_validate_root_managed_file = _LIVE._validate_root_managed_file
_validate_root_config_file = _LIVE.validate_root_config_file

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
PROJECT_PATTERN = re.compile(r"^wolfs-garage-demo(?:-[a-z0-9][a-z0-9-]{0,29})?$")
IMAGE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,180}$")
REPOSITORY = "https://github.com/DerPyro/wolfs-garage.git"
APP, PROXY = "demo_app", "demo_proxy"
NGINX, LIMITS = "demo.nginx.conf.template", "demo.nginx-limits.conf.template"
JOURNAL = "rollback-journal.json"
DEFAULT_NGINX_IMAGE = "nginx@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236"


def _parse_env(path):
    result = {}
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise UpdateError(f"Invalid environment file line {number}.")
        key, value = (part.strip() for part in line.split("=", 1))
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or not value or "\x00" in value or key in result:
            raise UpdateError(f"Invalid environment file line {number}.")
        result[key] = value
    return result


def load_config(path):
    values = _parse_env(path)
    required = {"DEMO_COMPOSE_FILE", "DEMO_ENV_FILE", "DEMO_RELEASE_ROOT", "DEMO_STATE_DIR",
                "DEMO_IMAGE_PREFIX", "DEMO_HEALTH_TIMEOUT", "DEMO_ORIGIN", "DEMO_PROJECT"}
    missing = sorted(required - values.keys())
    if missing:
        raise UpdateError("Missing demo updater config keys: " + ", ".join(missing))
    for key in ("DEMO_COMPOSE_FILE", "DEMO_ENV_FILE", "DEMO_RELEASE_ROOT", "DEMO_STATE_DIR"):
        if not Path(values[key]).is_absolute():
            raise UpdateError(f"{key} must be an absolute path.")
    if "DEMO_CONNECTOR_FILE" in values and not Path(values["DEMO_CONNECTOR_FILE"]).is_absolute():
        raise UpdateError("DEMO_CONNECTOR_FILE must be an absolute path.")
    if not PROJECT_PATTERN.fullmatch(values["DEMO_PROJECT"]):
        raise UpdateError("DEMO_PROJECT must start with wolfs-garage-demo.")
    if not IMAGE_PATTERN.fullmatch(values["DEMO_IMAGE_PREFIX"]):
        raise UpdateError("Invalid DEMO_IMAGE_PREFIX.")
    if not re.fullmatch(r"[0-9]{1,4}", values["DEMO_HEALTH_TIMEOUT"]) or not 10 <= int(values["DEMO_HEALTH_TIMEOUT"]) <= 900:
        raise UpdateError("DEMO_HEALTH_TIMEOUT must be between 10 and 900 seconds.")
    origin = urlsplit(values["DEMO_ORIGIN"])
    if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password
            or origin.path not in ("", "/") or origin.query or origin.fragment):
        raise UpdateError("DEMO_ORIGIN must be a single HTTPS origin.")
    runtime = _parse_env(values["DEMO_ENV_FILE"])
    port = runtime.get("GARAGE_DEMO_PORT", "18996")
    if not re.fullmatch(r"[0-9]{1,5}", port) or not 1 <= int(port) <= 65535:
        raise UpdateError("GARAGE_DEMO_PORT in DEMO_ENV_FILE is invalid.")
    values["_RUNTIME_PORT"] = port
    values["_NGINX_IMAGE"] = runtime.get("GARAGE_DEMO_NGINX_IMAGE", DEFAULT_NGINX_IMAGE)
    if not re.fullmatch(r"nginx@sha256:[0-9a-f]{64}", values["_NGINX_IMAGE"]):
        raise UpdateError("GARAGE_DEMO_NGINX_IMAGE must be a digest-pinned nginx image.")
    return values


def _private_dir(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or (os.geteuid() == 0 and info.st_uid != 0):
        raise UpdateError("Demo updater state directory must be updater-owned and private.")
    os.chmod(path, 0o700)
    return path


def _atomic_json(target, value):
    target = Path(target)
    temp = target.with_name(f".{target.name}-{os.getpid()}-{time.time_ns()}")
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            fd = -1
            json.dump(value, out, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, target)
        dirfd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        dirfd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        temp.unlink(missing_ok=True)
        raise


def _write_active(state, sha):
    target = Path(state) / "active-main-sha"
    temp = Path(state) / f".active-{os.getpid()}-{time.time_ns()}"
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as out:
            fd = -1
            out.write(sha + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, target)
        dirfd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        temp.unlink(missing_ok=True)
        raise


def _runtime_env(config, *, port=None):
    env = os.environ.copy()
    env.update({"GARAGE_DEMO_IMAGE": "", "GARAGE_DEMO_TEMPLATE_DIR": "",
                "GARAGE_DEMO_PORT": str(port if port is not None else config["_RUNTIME_PORT"]),
                "GARAGE_PUBLIC_ORIGIN": config["DEMO_ORIGIN"],
                "GARAGE_DEMO_HOST": urlsplit(config["DEMO_ORIGIN"]).netloc})
    return env


def _compose(config, image, templates, *args, project=None, connector=True, port=None, override=None, capture=False):
    command = ["docker", "compose", "--project-name", project or config["DEMO_PROJECT"],
               "--env-file", config["DEMO_ENV_FILE"]]
    # The operator overlay is intentionally earlier than the updater-controlled runtime file.
    if connector and config.get("DEMO_CONNECTOR_FILE"):
        command += ["-f", config["DEMO_CONNECTOR_FILE"]]
    command += ["-f", config["DEMO_COMPOSE_FILE"]]
    if override is not None:
        command += ["-f", str(override)]
    command += list(args)
    env = _runtime_env(config, port=port)
    env.update({"GARAGE_DEMO_IMAGE": image, "GARAGE_DEMO_TEMPLATE_DIR": str(templates)})
    return _run(command, env=env, capture=capture, timeout=1800)


def _service_container(config, image, templates, service, **kwargs):
    value = _compose(config, image, templates, "ps", "-q", service, capture=True, **kwargs)
    if not value or "\n" in value:
        raise UpdateError(f"Could not identify exactly one {service} container.")
    return value


def _image_of(container):
    value = _run(["docker", "inspect", "--format", "{{.Config.Image}}", container], capture=True)
    if not value:
        raise UpdateError("Could not identify running demo image.")
    return value


def _template_dir(container):
    try:
        mounts = json.loads(_run(["docker", "inspect", "--format", "{{json .Mounts}}", container], capture=True))
    except (ValueError, TypeError) as exc:
        raise UpdateError("Could not inspect running demo proxy template mounts.") from exc
    expected = {"/etc/nginx/templates/demo.conf.template": NGINX,
                "/etc/nginx/templates/demo-limits.conf.template": LIMITS}
    found = {}
    for mount in mounts:
        if isinstance(mount, dict) and mount.get("Destination") in expected:
            source = Path(mount.get("Source", ""))
            _validate_root_managed_file(source)
            if source.name != expected[mount["Destination"]]:
                raise UpdateError("Running proxy template mounts do not match the expected files.")
            found[mount["Destination"]] = source
    if set(found) != set(expected) or found[next(iter(expected))].parent != found[next(reversed(expected))].parent:
        raise UpdateError("Running proxy must mount both templates from one checked directory.")
    return found[next(iter(expected))].parent


def _templates_match_release(actual_dir, release, sha):
    """Match mounted proxy inputs to the clean immutable source commit, including rollback snapshots."""
    if _run(["git", "-C", str(release), "rev-parse", "HEAD"], capture=True) != sha:
        return False
    if _run(["git", "-C", str(release), "status", "--porcelain"], capture=True):
        return False
    for name in (NGINX, LIMITS):
        mounted, checked = Path(actual_dir) / name, Path(release) / "deploy" / name
        _validate_root_managed_file(mounted)
        _validate_root_managed_file(checked)
        mounted_blob = _run(["git", "-C", str(release), "hash-object", "--", str(mounted)], capture=True)
        committed_blob = _run(["git", "-C", str(release), "rev-parse", "--verify", f"{sha}:deploy/{name}"], capture=True)
        if (not re.fullmatch(r"[0-9a-f]{40}", mounted_blob)
                or not re.fullmatch(r"[0-9a-f]{40}", committed_blob)
                or mounted_blob != committed_blob):
            return False
    return True


def _healthy(container, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = _run(["docker", "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", container], capture=True)
        if state == "healthy":
            return True
        if state in ("unhealthy", "none"):
            return False
        time.sleep(2)
    return False


def _http(port, host, path):
    request = Request(f"http://127.0.0.1:{port}{path}", headers={"Host": host})
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()
    except (OSError, URLError) as exc:
        raise UpdateError("Loopback demo proxy HTTP check failed.") from exc


def _verify_http(port, host, *, synthetic=False):
    status, _ = _http(port, host, "/healthz")
    if status != 200:
        raise UpdateError("Demo proxy health check failed for its configured Host.")
    status, body = _http(port, host, "/garage-api/capabilities")
    try:
        capabilities = json.loads(body)
    except ValueError as exc:
        raise UpdateError("Demo capabilities endpoint returned invalid JSON.") from exc
    if status != 200 or not isinstance(capabilities, dict) or capabilities.get("demo", {}).get("shared") is not True:
        raise UpdateError("Demo capabilities check failed.")
    if not synthetic:
        return
    status, body = _http(port, host, "/garage-api/vehicles")
    if status != 200:
        raise UpdateError("Demo vehicle endpoint failed.")
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise UpdateError("Demo vehicle endpoint returned invalid JSON.") from exc
    vehicles = data.get("vehicles") if isinstance(data, dict) else data
    if not isinstance(vehicles, list) or len(vehicles) != 5:
        raise UpdateError("Demo does not expose its five seeded synthetic vehicles.")
    for path in ("/garage-api/backup", "/garage-api/export"):
        status, _ = _http(port, host, path)
        if status < 400:
            raise UpdateError("Demo unexpectedly exposes backup or export data.")


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _override_file(path, *, image, templates, host, port):
    lines = ["services:", "  demo_app:", f"    image: {json.dumps(image)}", "  demo_proxy:",
             "    volumes:",
             f"      - {json.dumps(str(Path(templates) / NGINX) + ':/etc/nginx/templates/demo.conf.template:ro')}",
             f"      - {json.dumps(str(Path(templates) / LIMITS) + ':/etc/nginx/templates/demo-limits.conf.template:ro')}",
             "    environment:", f"      GARAGE_DEMO_HOST: {json.dumps(host)}"]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _install_release(config, sha):
    root = Path(config["DEMO_RELEASE_ROOT"])
    root.mkdir(mode=0o755, parents=True, exist_ok=True)
    release = root / sha
    if not release.exists():
        temp = Path(tempfile.mkdtemp(prefix=f".{sha}-", dir=root))
        try:
            _run(["git", "clone", "--no-checkout", REPOSITORY, str(temp)], timeout=600)
            _run(["git", "-C", str(temp), "checkout", "--detach", sha], timeout=120)
            if _run(["git", "-C", str(temp), "rev-parse", "HEAD"], capture=True) != sha:
                raise UpdateError("Demo checkout did not match the validated main SHA.")
            os.replace(temp, release)
        except BaseException:
            shutil.rmtree(temp, ignore_errors=True)
            raise
    elif _run(["git", "-C", str(release), "rev-parse", "HEAD"], capture=True) != sha:
        raise UpdateError("Existing demo checkout does not match its SHA.")
    if _run(["git", "-C", str(release), "status", "--porcelain"], capture=True):
        raise UpdateError("Existing demo checkout is not clean.")
    for name in (NGINX, LIMITS):
        template = release / "deploy" / name
        _validate_root_managed_file(template)
        # The proxy runs as UID 101; systemd's private umask otherwise leaves git checkout files unreadable.
        os.chmod(template, 0o644)
    return release


def _build(config, release, sha):
    image = f"{config['DEMO_IMAGE_PREFIX']}:{sha}"
    _run(["docker", "build", "--label", f"org.opencontainers.image.revision={sha}",
          "-f", str(release / "deploy/Dockerfile.standalone"), "-t", image, str(release)], timeout=1800)
    return image


def _preflight(config, release, image, sha, state):
    project = f"{config['DEMO_PROJECT']}-check-{sha[:8]}"
    port = _port()
    host = urlsplit(config["DEMO_ORIGIN"]).netloc
    templates = release / "deploy"
    override = Path(state) / f"preflight-{sha}.yaml"
    _override_file(override, image=image, templates=templates, host=host, port=port)
    _atomic_json(Path(state) / "preflight-active.json",
                 {"version": 1, "project": project, "port": port, "image": image,
                  "templates": str(templates), "override": str(override)})
    try:
        _compose(config, image, templates, "up", "-d", "--no-deps", "--no-build", APP,
                 project=project, connector=False, port=port, override=override)
        app = _service_container(config, image, templates, APP, project=project, connector=False, port=port, override=override)
        if not _healthy(app, int(config["DEMO_HEALTH_TIMEOUT"])):
            raise UpdateError("Candidate demo app failed its isolated health check.")
        _compose(config, image, templates, "up", "-d", "--no-deps", "--no-build", PROXY,
                 project=project, connector=False, port=port, override=override)
        proxy = _service_container(config, image, templates, PROXY, project=project, connector=False, port=port, override=override)
        if not _healthy(proxy, int(config["DEMO_HEALTH_TIMEOUT"])):
            raise UpdateError("Candidate demo proxy failed its isolated health check.")
        _verify_http(port, host, synthetic=True)
    finally:
        _compose(config, image, templates, "down", "--remove-orphans", project=project,
                 connector=False, port=port, override=override)
        override.unlink(missing_ok=True)
        (Path(state) / "preflight-active.json").unlink(missing_ok=True)


def _recover_preflight(config, state):
    path = Path(state) / "preflight-active.json"
    try:
        path.lstat()
    except FileNotFoundError:
        return
    _validate_root_managed_file(path, private=True)
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
        project, port = item["project"], item["port"]
        image, templates, override = item["image"], Path(item["templates"]), Path(item["override"])
        if (item.get("version") != 1 or project != f"{config['DEMO_PROJECT']}-check-{image.rsplit(':', 1)[-1][:8]}"
                or type(port) is not int or not 1 <= port <= 65535
                or not re.fullmatch(re.escape(config["DEMO_IMAGE_PREFIX"]) + r":[0-9a-f]{40}", image)
                or not templates.is_absolute() or not override.is_relative_to(Path(state))):
            raise ValueError
        _validate_root_managed_file(templates / NGINX)
        _validate_root_managed_file(templates / LIMITS)
        _validate_root_managed_file(override, private=True)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise UpdateError("Interrupted demo preflight record is invalid.") from exc
    _compose(config, image, templates, "down", "--remove-orphans", project=project,
             connector=False, port=port, override=override)
    override.unlink(missing_ok=True)
    path.unlink(missing_ok=True)


def _snapshot_templates(state, old_dir, old_sha):
    root = Path(state) / "rollback-templates"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    dest = Path(tempfile.mkdtemp(prefix=f"{old_sha}-", dir=root))
    for name in (NGINX, LIMITS):
        src = old_dir / name
        _validate_root_managed_file(src)
        target = dest / name
        shutil.copyfile(src, target)
        # NGINX runs as UID 101; the private state directory protects these read-only binds.
        os.chmod(target, 0o644)
        with target.open("rb") as stream:
            os.fsync(stream.fileno())
    return dest


def _write_journal(state, *, sha, old_sha, old_image, old_templates):
    snapshots = _snapshot_templates(state, old_templates, old_sha)
    value = {"version": 1, "candidate": sha,
             "previous": {"sha": old_sha, "image": old_image, "templates": str(snapshots)}}
    _atomic_json(Path(state) / JOURNAL, value)
    return value


def _read_journal(state, config):
    path = Path(state) / JOURNAL
    try:
        path.lstat()
    except FileNotFoundError:
        return None
    _validate_root_managed_file(path, private=True)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        old = value["previous"]
        if (value.get("version") != 1 or not SHA_PATTERN.fullmatch(value["candidate"])
                or not SHA_PATTERN.fullmatch(old["sha"])):
            raise ValueError
        if not re.fullmatch(re.escape(config["DEMO_IMAGE_PREFIX"]) + r":[0-9a-f]{40}", old["image"]):
            raise ValueError
        template_dir = Path(old["templates"])
        if not template_dir.is_absolute() or not template_dir.is_relative_to(Path(state)):
            raise ValueError
        for name in (NGINX, LIMITS):
            _validate_root_managed_file(template_dir / name)
        return value
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise UpdateError("Demo rollback journal is invalid; refusing to continue.") from exc


def _clear_journal(state):
    path = Path(state) / JOURNAL
    path.unlink(missing_ok=True)
    dfd = os.open(state, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _recover(config, state, journal):
    previous = journal["previous"]
    image, templates = previous["image"], Path(previous["templates"])
    timeout = int(config["DEMO_HEALTH_TIMEOUT"])
    override = Path(state) / "recovery-compose.yaml"
    _override_file(override, image=image, templates=templates,
                   host=urlsplit(config["DEMO_ORIGIN"]).netloc, port=int(config["_RUNTIME_PORT"]))
    _compose(config, image, templates, "up", "-d", "--no-deps", "--no-build", APP, override=override)
    app = _service_container(config, image, templates, APP, override=override)
    if not _healthy(app, timeout):
        raise UpdateError("Rollback app is unhealthy; recovery journal retained.")
    _compose(config, image, templates, "up", "-d", "--no-deps", "--no-build", "--force-recreate", PROXY, override=override)
    proxy = _service_container(config, image, templates, PROXY, override=override)
    if not _healthy(proxy, timeout):
        raise UpdateError("Rollback proxy is unhealthy; recovery journal retained.")
    _verify_deployed(config, image, templates, app, proxy)
    _write_active(state, previous["sha"])
    _clear_journal(state)
    override.unlink(missing_ok=True)


def _verify_deployed(config, image, templates, app, proxy):
    if _image_of(app) != image:
        raise UpdateError("Running demo app image does not match the selected release.")
    if _image_of(proxy) != config["_NGINX_IMAGE"]:
        raise UpdateError("Running demo proxy image does not match the pinned nginx image.")
    actual_templates = _template_dir(proxy)
    if actual_templates.resolve() != Path(templates).resolve():
        raise UpdateError("Running demo proxy does not use the selected release templates.")
    if not _healthy(app, int(config["DEMO_HEALTH_TIMEOUT"])) or not _healthy(proxy, int(config["DEMO_HEALTH_TIMEOUT"])):
        raise UpdateError("Demo app/proxy health check failed.")
    host = urlsplit(config["DEMO_ORIGIN"]).netloc
    _verify_http(int(config["_RUNTIME_PORT"]), host)


def update_once(config):
    state = _private_dir(config["DEMO_STATE_DIR"])
    lock_fd = os.open(state / "update.lock", os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        return False
    try:
        journal = _read_journal(state, config)
        if journal:
            _recover(config, state, journal)
        _recover_preflight(config, state)
        marker = state / "active-main-sha"
        try:
            old_sha = marker.read_text(encoding="ascii").strip()
        except FileNotFoundError:
            old_sha = ""
        if not SHA_PATTERN.fullmatch(old_sha):
            raise UpdateError("Initialize active-main-sha to the currently installed demo commit first.")
        old_templates = Path(config["DEMO_RELEASE_ROOT"]) / old_sha / "deploy"
        # Inspect actual runtime identity and mounts; config paths alone are not evidence of the running release.
        baseline = f"{config['DEMO_IMAGE_PREFIX']}:{old_sha}"
        old_app = _service_container(config, baseline, old_templates, APP)
        old_image = _image_of(old_app)
        old_proxy = _service_container(config, old_image, old_templates, PROXY)
        old_templates = _template_dir(old_proxy)
        sha = github_main_sha()
        if sha == old_sha and old_image == baseline and _healthy(old_app, int(config["DEMO_HEALTH_TIMEOUT"])):
            proxy_healthy = _healthy(old_proxy, int(config["DEMO_HEALTH_TIMEOUT"]))
            canonical_release = Path(config["DEMO_RELEASE_ROOT"]) / old_sha
            if proxy_healthy and _templates_match_release(old_templates, canonical_release, old_sha):
                _verify_deployed(config, old_image, old_templates, old_app, old_proxy)
                print(f"Latest tested main already active and healthy: {sha}.")
                return False
        if not checks_succeeded(sha):
            print(f"No completed successful Checks push for main {sha}; no update.")
            return False
        release = _install_release(config, sha)
        candidate = _build(config, release, sha)
        _preflight(config, release, candidate, sha, state)
        if github_main_sha() != sha or not checks_succeeded(sha):
            print("Main moved before deployment; retrying on the next timer tick.")
            return False
        journal = _write_journal(state, sha=sha, old_sha=old_sha, old_image=old_image, old_templates=old_templates)
        timeout = int(config["DEMO_HEALTH_TIMEOUT"])
        candidate_templates = release / "deploy"
        candidate_override = Path(state) / f"candidate-{sha}.yaml"
        _override_file(candidate_override, image=candidate, templates=candidate_templates,
                       host=urlsplit(config["DEMO_ORIGIN"]).netloc, port=int(config["_RUNTIME_PORT"]))
        try:
            # Replace only the app first. The proxy and connector stay untouched until app health passes.
            _compose(config, candidate, candidate_templates, "up", "-d", "--no-deps", "--no-build", "--force-recreate", APP, override=candidate_override)
            app = _service_container(config, candidate, candidate_templates, APP, override=candidate_override)
            if not _healthy(app, timeout):
                raise UpdateError("Candidate demo app did not become healthy.")
            _compose(config, candidate, candidate_templates, "up", "-d", "--no-deps", "--no-build", "--force-recreate", PROXY, override=candidate_override)
            proxy = _service_container(config, candidate, candidate_templates, PROXY, override=candidate_override)
            if not _healthy(proxy, timeout):
                raise UpdateError("Candidate demo proxy did not become healthy.")
            _verify_deployed(config, candidate, candidate_templates, app, proxy)
            if github_main_sha() != sha or not checks_succeeded(sha):
                raise UpdateError("Main stopped being the latest green push during deployment.")
        except BaseException:
            try:
                _recover(config, state, journal)
            finally:
                candidate_override.unlink(missing_ok=True)
            raise
        candidate_override.unlink(missing_ok=True)
        # Keep the journal until the marker is durable: recovery always resets both runtime and marker.
        _write_active(state, sha)
        _clear_journal(state)
        print(f"Updated public demo to tested main {sha}; synthetic data restarted fresh.")
        return True
    finally:
        os.close(lock_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Update the isolated synthetic demo from tested main")
    parser.add_argument("--env-file", default="/etc/wolfs-garage-demo/update.env")
    parser.add_argument("--once", action="store_true", help="Run one update check and exit")
    args = parser.parse_args(argv)
    try:
        _validate_root_config_file(args.env_file)
        config = load_config(args.env_file)
        _validate_root_managed_file(config["DEMO_COMPOSE_FILE"])
        _validate_root_managed_file(config["DEMO_ENV_FILE"], private=True)
        if config.get("DEMO_CONNECTOR_FILE"):
            _validate_root_managed_file(config["DEMO_CONNECTOR_FILE"], private=True)
        update_once(config)
    except UpdateError as exc:
        print(f"Wolfs Garage demo updater stopped safely: {exc}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Wolfs Garage demo updater stopped safely ({type(exc).__name__}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

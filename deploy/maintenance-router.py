#!/usr/bin/env python3
"""Switch a root-managed Nginx config template through an existing bind mount."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time


class MaintenanceError(RuntimeError):
    pass


def _managed_file(path, *, private=False):
    path = Path(path).absolute()
    for parent in reversed(path.parents):
        try:
            info = parent.lstat()
        except OSError as exc:
            raise MaintenanceError("Configured path is unavailable.") from exc
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise MaintenanceError("Configured path parents must be root-owned and not writable by group/other.")
    try:
        info = path.lstat()
    except OSError as exc:
        raise MaintenanceError("Configured file is unavailable.") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
            or (private and info.st_mode & 0o077)):
        raise MaintenanceError("Configured file has unsafe ownership or permissions.")
    return path


def load_config(path):
    config_path = _managed_file(path, private=True)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MaintenanceError("Maintenance config is invalid.") from exc
    if not isinstance(config, dict) or set(config) != {"normal", "maintenance", "target", "container"}:
        raise MaintenanceError("Maintenance config must contain normal, maintenance, target, and container.")
    for key in ("normal", "maintenance", "target"):
        value = config[key]
        if not isinstance(value, str) or not Path(value).is_absolute():
            raise MaintenanceError(f"{key} must be an absolute path.")
        config[key] = _managed_file(value, private=(key != "target"))
    if config["normal"] == config["maintenance"] or config["target"] in {config["normal"], config["maintenance"]}:
        raise MaintenanceError("Router target and templates must be separate files.")
    if not isinstance(config["container"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", config["container"]):
        raise MaintenanceError("Invalid Nginx container name.")
    return config


def _run_docker(container, *args):
    try:
        result = subprocess.run(["docker", "exec", container, *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MaintenanceError("Nginx control command failed.") from exc
    if result.returncode:
        raise MaintenanceError("Nginx rejected the maintenance config operation.")


def _write_all(fd, value):
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    remaining = memoryview(value)
    while remaining:
        count = os.write(fd, remaining)
        if count <= 0:
            raise OSError("Short write while updating Nginx config.")
        remaining = remaining[count:]
    os.fsync(fd)


def _replace_contents(target, content):
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(target, flags)
    except OSError as exc:
        raise MaintenanceError("Could not open the existing Nginx config target.") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_size > 2_000_000:
            raise MaintenanceError("Nginx config target is not a safe regular file.")
        original = os.read(fd, info.st_size + 1)
        if len(original) != info.st_size:
            raise MaintenanceError("Nginx config target changed while being read.")
        try:
            _write_all(fd, content)
        except BaseException as write_error:
            try:
                _write_all(fd, original)
            except OSError as restore_error:
                raise MaintenanceError("Config write and in-place restoration both failed.") from restore_error
            raise write_error
        return original
    finally:
        os.close(fd)


def switch(config, mode):
    template_key = "maintenance" if mode == "prepare" else "normal"
    template = config[template_key].read_bytes()
    _managed_file(config["target"])
    previous = _replace_contents(config["target"], template)
    try:
        _run_docker(config["container"], "nginx", "-t")
        _run_docker(config["container"], "nginx", "-s", "reload")
    except BaseException as exc:
        try:
            _replace_contents(config["target"], previous)
            _run_docker(config["container"], "nginx", "-t")
            _run_docker(config["container"], "nginx", "-s", "reload")
        except BaseException as restore_error:
            raise MaintenanceError("Nginx config failed and in-place rollback could not be confirmed.") from restore_error
        raise exc
    if mode == "prepare":
        time.sleep(3)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Switch the existing Nginx router to/from maintenance")
    parser.add_argument("--config", required=True)
    parser.add_argument("--mode", choices=("prepare", "finish"), required=True)
    args = parser.parse_args(argv)
    try:
        switch(load_config(args.config), args.mode)
    except MaintenanceError as exc:
        print(f"Maintenance router operation failed safely: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Maintenance router operation failed safely ({type(exc).__name__}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

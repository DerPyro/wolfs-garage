#!/usr/bin/env python3
"""Validate release source metadata without importing the application."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys


REPOSITORY = "DerPyro/wolfs-garage"
IMAGE = "ghcr.io/derpyro/wolfs-garage"
VERSION_TEXT = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:(?:a|b|rc)(?:0|[1-9][0-9]*))?"
VERSION_PATTERN = re.compile(VERSION_TEXT + r"\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


class MetadataError(ValueError):
    """The workflow event or checked-out Git source is not publishable."""


def _git(*args):
    result = subprocess.run(
        ["git", *args], check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git command failed"
        raise MetadataError(detail)
    return result.stdout.strip()


def _version_from_source():
    source = Path("wolfs_garage/__init__.py").read_text(encoding="utf-8")
    module = ast.parse(source, filename="wolfs_garage/__init__.py")
    assignments = []

    def target_mentions_version(target):
        if isinstance(target, ast.Name):
            return target.id == "__version__"
        if isinstance(target, (ast.Tuple, ast.List)):
            return any(target_mentions_version(item) for item in target.elts)
        if isinstance(target, ast.Starred):
            return target_mentions_version(target.value)
        return False

    for node in module.body:
        if isinstance(node, ast.Assign) and any(target_mentions_version(target) for target in node.targets):
            assignments.append(node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and target_mentions_version(node.target):
            assignments.append(node.value)
    if len(assignments) != 1:
        if not assignments:
            raise MetadataError("wolfs_garage.__version__ is not a module-level assignment")
        raise MetadataError("wolfs_garage.__version__ must have exactly one module-level assignment")
    value = assignments[0]
    if value is None:
        raise MetadataError("wolfs_garage.__version__ is not a module-level assignment")
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        raise MetadataError("wolfs_garage.__version__ must be a literal string")
    version = value.value
    if not VERSION_PATTERN.fullmatch(version):
        raise MetadataError("application version must be strict MAJOR.MINOR.PATCH with optional aN, bN, or rcN")
    return version


def _read_event(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetadataError("GitHub event file is unavailable or invalid JSON") from exc
    if not isinstance(value, dict):
        raise MetadataError("GitHub event payload must be a JSON object")
    return value


def validate(event_name, repository, event, version):
    if repository != REPOSITORY:
        raise MetadataError("this release workflow is restricted to DerPyro/wolfs-garage")
    source_sha = _git("rev-parse", "--verify", "HEAD^{commit}").lower()
    if not SHA_PATTERN.fullmatch(source_sha):
        raise MetadataError("checked-out source did not resolve to a full commit SHA")

    if event_name == "workflow_dispatch":
        return {"source_sha": source_sha, "version": version, "image": IMAGE, "publish": False}
    if event_name != "release":
        raise MetadataError("only release publication or manual build-only events are supported")
    if event.get("action") != "published":
        raise MetadataError("release event action must be published")
    release = event.get("release")
    if not isinstance(release, dict) or release.get("draft") is not False:
        raise MetadataError("release must be published and not a draft")
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not re.fullmatch(r"v" + re.escape(version), tag):
        raise MetadataError("published release tag must be v plus the exact application version")
    if not re.fullmatch(r"v" + VERSION_TEXT, tag):
        raise MetadataError("release tag must use strict vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH[aN|bN|rcN]")

    tag_sha = _git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}").lower()
    if not SHA_PATTERN.fullmatch(tag_sha) or tag_sha != source_sha:
        raise MetadataError("checked-out HEAD must exactly match the published tag commit")
    _git("rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", tag_sha, "refs/remotes/origin/main"],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if ancestry.returncode == 1:
        raise MetadataError("release tag commit must be an ancestor of origin/main")
    if ancestry.returncode != 0:
        raise MetadataError(ancestry.stderr.strip() or "could not validate origin/main ancestry")
    return {"source_sha": source_sha, "version": version, "image": IMAGE, "publish": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--output", help="write compact JSON to this file instead of stdout")
    args = parser.parse_args(argv)
    try:
        event_name = os.environ.get("GITHUB_EVENT_NAME", "")
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if not event_name or not repository:
            raise MetadataError("GITHUB_EVENT_NAME and GITHUB_REPOSITORY are required")
        if not args.event_path:
            raise MetadataError("--event-path or GITHUB_EVENT_PATH is required")
        event = _read_event(args.event_path)
        output = validate(event_name, repository, event, _version_from_source())
        rendered = json.dumps(output, separators=(",", ":"))
        if args.output:
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
        return 0
    except (MetadataError, OSError, SyntaxError, UnicodeError) as exc:
        print(f"release metadata validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

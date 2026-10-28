"""Release metadata validation uses isolated, synthetic local Git repositories."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_metadata.py"
REPOSITORY = "DerPyro/wolfs-garage"
VERSION = "0.1.0a4"
TAG = f"v{VERSION}"


class SyntheticRepository:
    def __init__(self, root, version=VERSION):
        self.root = Path(root)
        self.root.mkdir(parents=True)
        self._git("init", "--initial-branch=main")
        self._git("config", "user.name", "Release metadata test")
        self._git("config", "user.email", "release-test@example.invalid")
        package = self.root / "wolfs_garage"
        package.mkdir()
        (package / "__init__.py").write_text(f'__version__ = "{version}"\n', encoding="utf-8")
        (self.root / "README.md").write_text("synthetic repository\n", encoding="utf-8")
        self._git("add", "wolfs_garage/__init__.py", "README.md")
        self.head = self._commit("release source")
        self._git("update-ref", "refs/remotes/origin/main", self.head)
        self._git("tag", "-a", TAG, "-m", "synthetic release", self.head)

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def _commit(self, message):
        self._git("commit", "-m", message)
        return self._git("rev-parse", "HEAD").stdout.strip()

    def add_commit(self, message="later source"):
        (self.root / "README.md").write_text(message + "\n", encoding="utf-8")
        self._git("add", "README.md")
        return self._commit(message)

    def event(self, *, action="published", tag=TAG, draft=False, prerelease=True):
        return {"action": action, "release": {"tag_name": tag, "draft": draft,
                                                "prerelease": prerelease}}


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="wg-release-metadata-")
        self.repo = SyntheticRepository(Path(self.temporary.name) / "repo")
        self.event_path = Path(self.temporary.name) / "event.json"

    def tearDown(self):
        self.temporary.cleanup()

    def write_event(self, payload):
        self.event_path.write_text(json.dumps(payload), encoding="utf-8")
        return self.event_path

    def invoke(self, event_name="release", payload=None, *, repository=REPOSITORY,
               output_path=None, extra_env=None, use_event_path_flag=True):
        payload = payload if payload is not None else self.repo.event()
        event_path = self.write_event(payload)
        environment = os.environ.copy()
        for key in ("GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH", "GITHUB_REPOSITORY", "GITHUB_REF"):
            environment.pop(key, None)
        environment.update({"GITHUB_EVENT_NAME": event_name, "GITHUB_REPOSITORY": repository})
        if not use_event_path_flag:
            environment["GITHUB_EVENT_PATH"] = str(event_path)
        if extra_env:
            environment.update(extra_env)
        command = [sys.executable, str(SCRIPT)]
        if use_event_path_flag:
            command.extend(["--event-path", str(event_path)])
        if output_path is not None:
            command.extend(["--output", str(output_path)])
        return subprocess.run(command, cwd=self.repo.root, env=environment, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)

    def assert_rejected_without_output(self, **kwargs):
        result = self.invoke(**kwargs)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "", "Rejected release metadata must not emit partial stdout outputs")
        return result

    def test_matching_published_prerelease_emits_exact_metadata(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        self.assertEqual(metadata, {
            "source_sha": self.repo.head,
            "version": VERSION,
            "image": "ghcr.io/derpyro/wolfs-garage",
            "publish": True,
        })

    def test_event_path_environment_and_optional_output_file(self):
        output = Path(self.temporary.name) / "metadata.json"
        result = self.invoke(output_path=output, use_event_path_flag=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {
            "source_sha": self.repo.head,
            "version": VERSION,
            "image": "ghcr.io/derpyro/wolfs-garage",
            "publish": True,
        })

    def test_dispatch_is_build_only_even_with_release_fields_and_tag_ref(self):
        result = self.invoke(event_name="workflow_dispatch", payload=self.repo.event(),
                             extra_env={"GITHUB_REF": f"refs/tags/{TAG}"})
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads(result.stdout)
        self.assertEqual(metadata["source_sha"], self.repo.head)
        self.assertEqual(metadata["version"], VERSION)
        self.assertEqual(metadata["image"], "ghcr.io/derpyro/wolfs-garage")
        self.assertIs(metadata["publish"], False)

    def test_unknown_event_and_wrong_repository_are_rejected_without_outputs(self):
        self.assert_rejected_without_output(event_name="push")
        self.assert_rejected_without_output(repository="someone-else/wolfs-garage")
        self.assert_rejected_without_output(repository="DerPyro/Wolfs-Garage")

    def test_release_must_be_published_not_draft_and_tag_must_match_version(self):
        self.assert_rejected_without_output(payload=self.repo.event(action="created"))
        self.assert_rejected_without_output(payload=self.repo.event(draft=True))
        self.assert_rejected_without_output(payload=self.repo.event(tag="v0.1.0a3"))
        self.assert_rejected_without_output(payload={"action": "published", "release": {"draft": False}})

    def test_release_tag_commit_must_be_checked_out_head(self):
        tagged = self.repo.head
        later = self.repo.add_commit()
        self.repo._git("update-ref", "refs/remotes/origin/main", later)
        self.assert_rejected_without_output()
        self.assertNotEqual(tagged, later)

    def test_release_commit_must_be_ancestor_of_origin_main(self):
        first = self.repo.head
        later = self.repo.add_commit()
        self.repo._git("tag", "-d", TAG)
        self.repo._git("tag", "-a", TAG, "-m", "tag at current source", later)
        self.repo._git("update-ref", "refs/remotes/origin/main", first)
        self.assert_rejected_without_output()

    def test_invalid_version_and_malicious_tag_fail_without_shell_effects(self):
        invalid_repo_path = Path(self.temporary.name) / "invalid-version"
        invalid_repo = SyntheticRepository.__new__(SyntheticRepository)
        invalid_repo.root = invalid_repo_path
        invalid_repo.root.mkdir()
        invalid_repo._git("init", "--initial-branch=main")
        invalid_repo._git("config", "user.name", "Release metadata test")
        invalid_repo._git("config", "user.email", "release-test@example.invalid")
        (invalid_repo_path / "wolfs_garage").mkdir()
        (invalid_repo_path / "wolfs_garage" / "__init__.py").write_text('__version__ = "latest"\n', encoding="utf-8")
        invalid_repo._git("add", "wolfs_garage/__init__.py")
        invalid_head = invalid_repo._commit("invalid version")
        invalid_repo._git("update-ref", "refs/remotes/origin/main", invalid_head)
        invalid_repo._git("tag", "-a", "vlatest", "-m", "invalid", invalid_head)
        original_repo = self.repo
        self.repo = invalid_repo
        self.assert_rejected_without_output(payload=invalid_repo.event())
        self.repo = original_repo

        marker = Path(self.temporary.name) / "shell-was-run"
        malicious = f"v{VERSION}$(touch {marker})"
        self.assert_rejected_without_output(payload=self.repo.event(tag=malicious))
        self.assertFalse(marker.exists(), "Tag text must never be interpreted by a shell")

    def test_multiple_module_level_version_assignments_are_rejected(self):
        version_file = self.repo.root / "wolfs_garage" / "__init__.py"
        valid_source = version_file.read_text(encoding="utf-8")
        for source in (
            f'__version__ = "{VERSION}"\n__version__ = "9.9.9"\n',
            f'__version__: str = "{VERSION}"\n__version__ = "{VERSION}"\n',
        ):
            with self.subTest(source=source):
                version_file.write_text(source, encoding="utf-8")
                self.assert_rejected_without_output()
        version_file.write_text(valid_source, encoding="utf-8")

    def test_failed_output_file_run_does_not_create_or_modify_outputs(self):
        output = Path(self.temporary.name) / "must-not-exist.json"
        result = self.invoke(payload=self.repo.event(tag="v9.9.9"), output_path=output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

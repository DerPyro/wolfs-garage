"""Tests for the fail-closed live updater using mocks and temporary directories."""
import importlib.util
import io
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "update-live.py"
SPEC = importlib.util.spec_from_file_location("garage_live_updater", SCRIPT)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)

SHA = "a" * 40
OLD_SHA = "b" * 40


def config_for(root):
    root = Path(root)
    return {
        "GARAGE_COMPOSE_FILE": str(root / "compose.yaml"),
        "GARAGE_RELEASE_ROOT": str(root / "releases"),
        "GARAGE_UPDATE_STATE_DIR": str(root / "state"),
        "GARAGE_DATA_VOLUME": "garage-data",
        "GARAGE_ORIGIN_NETWORK": "proxy-private",
        "GARAGE_PUBLIC_ORIGIN": "https://garage.example.invalid",
        "GARAGE_IMAGE_PREFIX": "wolfs-garage-live",
        "GARAGE_HEALTH_TIMEOUT": "60",
        "GARAGE_MAINTENANCE_PREPARE": str(root / "prepare"),
        "GARAGE_MAINTENANCE_FINISH": str(root / "finish"),
    }


class LiveUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wg-live-update-")
        self.root = Path(self.temp.name)
        self.env_file = self.root / "live.env"
        self.config = config_for(self.root)
        self.config["GARAGE_ENV_FILE"] = str(self.env_file)

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, overrides=None):
        values = {**self.config, **(overrides or {})}
        self.env_file.write_text("".join(f"{key}={value}\n" for key, value in values.items()
                                         if key != "GARAGE_ENV_FILE"), encoding="utf-8")

    def test_config_is_plain_data_and_rejects_duplicates_shell_syntax_and_non_origin_urls(self):
        self.write_config()
        self.assertEqual(updater.load_config(self.env_file)["GARAGE_DATA_VOLUME"], "garage-data")
        self.env_file.write_text(self.env_file.read_text() + "GARAGE_DATA_VOLUME=other\n", encoding="utf-8")
        with self.assertRaises(updater.UpdateError):
            updater.load_config(self.env_file)
        self.write_config({"GARAGE_PUBLIC_ORIGIN": "https://example.invalid; touch /tmp/not-run"})
        with self.assertRaises(updater.UpdateError):
            updater.load_config(self.env_file)
        self.write_config({"GARAGE_IMAGE_PREFIX": "$(touch /tmp/not-run)"})
        with self.assertRaises(updater.UpdateError):
            updater.load_config(self.env_file)

    def test_checks_accept_only_successful_push_run_for_exact_main_sha(self):
        base = {"head_sha": SHA, "event": "push", "head_branch": "main", "name": "Checks",
                "status": "completed", "conclusion": "success"}
        with mock.patch.object(updater, "_github_json", return_value={"workflow_runs": [base]}) as request:
            self.assertTrue(updater.checks_succeeded(SHA))
            url = request.call_args.args[0]
            self.assertIn("head_sha=" + SHA, url)
            self.assertIn("event=push", url)
            self.assertIn("branch=main", url)
        for runs in (
            [],
            [{**base, "head_sha": OLD_SHA}],
            [{**base, "event": "workflow_dispatch"}],
            [{**base, "head_branch": "feature"}],
            [{**base, "name": "Other workflow"}],
            [{**base, "status": "in_progress", "conclusion": None}],
            [{**base, "conclusion": "failure"}],
        ):
            with self.subTest(runs=runs), mock.patch.object(updater, "_github_json", return_value={"workflow_runs": runs}):
                self.assertFalse(updater.checks_succeeded(SHA))

    def test_github_api_uses_public_read_only_request_without_authentication_header(self):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(b'{"sha":"' + SHA.encode("ascii") + b'"}')
        with mock.patch.object(updater, "urlopen", return_value=response) as request_call:
            self.assertEqual(updater.github_main_sha(), SHA)
        request = request_call.call_args.args[0]
        self.assertEqual(request.full_url, updater.API_ROOT + "/commits/main")
        self.assertNotIn("Authorization", request.headers)

    def test_active_commit_is_skipped_without_cloning_or_deployment(self):
        state = Path(self.config["GARAGE_UPDATE_STATE_DIR"])
        state.mkdir(mode=0o700)
        (state / "active-main-sha").write_text(SHA + "\n", encoding="ascii")
        with mock.patch.object(updater, "github_main_sha", return_value=SHA), \
             mock.patch.object(updater, "checks_succeeded") as checks, \
             mock.patch.object(updater, "_run") as run, \
             mock.patch.object(updater, "_running_image", return_value=("wolfs-garage-live:" + SHA, "healthy-container")) as running, \
             mock.patch.object(updater, "_health", return_value=True) as health, \
             mock.patch.object(updater, "_deploy_candidate") as deploy:
            self.assertFalse(updater.update_once(self.config, self.env_file))
        checks.assert_not_called()
        run.assert_not_called()
        running.assert_called_once()
        health.assert_called_once_with("healthy-container", 60)
        deploy.assert_not_called()

    def test_active_marker_with_running_image_drift_passes_ci_gate_and_repairs(self):
        state = Path(self.config["GARAGE_UPDATE_STATE_DIR"])
        state.mkdir(mode=0o700)
        (state / "active-main-sha").write_text(SHA + "\n", encoding="ascii")
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:2] == ["git", "clone"]:
                Path(args[-1]).mkdir(parents=True, exist_ok=True)
            if len(args) >= 5 and args[:2] == ["git", "-C"] and args[3:5] == ["rev-parse", "HEAD"]:
                return SHA
            return ""

        with mock.patch.object(updater, "github_main_sha", return_value=SHA), \
             mock.patch.object(updater, "checks_succeeded", return_value=True) as checks, \
             mock.patch.object(updater, "_run", side_effect=fake_run), \
             mock.patch.object(updater, "_running_image", return_value=("wolfs-garage-live:older", "old-container")), \
             mock.patch.object(updater, "_health", return_value=True), \
             mock.patch.object(updater, "_candidate_preflight") as preflight, \
             mock.patch.object(updater, "_deploy_candidate") as deploy:
            self.assertTrue(updater.update_once(self.config, self.env_file))
        self.assertEqual(checks.call_args_list, [mock.call(SHA), mock.call(SHA)])
        preflight.assert_called_once_with("wolfs-garage-live:older", "wolfs-garage-live:" + SHA, mock.ANY)
        deploy.assert_called_once()
        self.assertTrue(any(args[:2] == ["docker", "build"] for args in calls))

    def test_absent_or_failed_ci_does_not_build_or_stop_live_service(self):
        for result in (False,):  # no workflow run and a failed run both fail this contract
            with self.subTest(result=result), \
                 mock.patch.object(updater, "github_main_sha", return_value=SHA), \
                 mock.patch.object(updater, "checks_succeeded", return_value=result), \
                 mock.patch.object(updater, "_run") as run, \
                 mock.patch.object(updater, "_deploy_candidate") as deploy:
                self.assertFalse(updater.update_once(self.config, self.env_file))
                run.assert_not_called()
                deploy.assert_not_called()

    def test_successful_update_checks_out_and_builds_the_validated_exact_sha(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            if args[:2] == ["git", "clone"]:
                Path(args[-1]).mkdir(parents=True, exist_ok=True)
            if len(args) >= 5 and args[:2] == ["git", "-C"] and args[3:5] == ["rev-parse", "HEAD"]:
                return SHA
            return ""

        with mock.patch.object(updater, "github_main_sha", return_value=SHA), \
             mock.patch.object(updater, "checks_succeeded", return_value=True), \
             mock.patch.object(updater, "_run", side_effect=fake_run), \
             mock.patch.object(updater, "_running_image", return_value=("wolfs-garage-live:old", "container")), \
             mock.patch.object(updater, "_candidate_preflight") as preflight, \
             mock.patch.object(updater, "_deploy_candidate") as deploy:
            self.assertTrue(updater.update_once(self.config, self.env_file))
        checkout = next(args for args in calls if len(args) >= 4 and args[:2] == ["git", "-C"] and args[3] == "checkout")
        self.assertEqual(checkout[-2:], ["--detach", SHA])
        build = next(args for args in calls if args[:2] == ["docker", "build"])
        self.assertIn("wolfs-garage-live:" + SHA, build)
        self.assertIn("org.opencontainers.image.revision=" + SHA, build)
        self.assertNotIn("login", " ".join(" ".join(args) for args in calls).lower())
        self.assertNotIn("push", " ".join(" ".join(args) for args in calls).lower())
        preflight.assert_called_once_with("wolfs-garage-live:old", "wolfs-garage-live:" + SHA, mock.ANY)
        deploy.assert_called_once()
        self.assertEqual((Path(self.config["GARAGE_UPDATE_STATE_DIR"]) / "active-main-sha").read_text().strip(), SHA)

    def test_command_execution_uses_argument_vectors_without_shell_or_config_secrets(self):
        with mock.patch.object(updater.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="", stderr="")) as run:
            updater._run(["git", "checkout", "--detach", SHA])
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["git", "checkout", "--detach", SHA])
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("GARAGE_TOKEN", kwargs.get("env") or {})
        self.assertIs(kwargs["stdin"], updater.subprocess.DEVNULL)

    def test_candidate_preflight_accepts_only_matching_schema3_or_schema4(self):
        state = Path(self.config["GARAGE_UPDATE_STATE_DIR"])
        state.mkdir(mode=0o700)

        def preflight(original_schema, candidate_schema):
            def make_backup(image, volume, workdir, filename):
                path = Path(workdir) / filename
                with closing(sqlite3.connect(path)) as database:
                    with database:
                        database.execute("CREATE TABLE meta (schema INTEGER NOT NULL)")
                        database.execute("INSERT INTO meta VALUES (?)", (original_schema,))

            with mock.patch.object(updater, "_backup_from_volume", side_effect=make_backup), \
                 mock.patch.object(updater, "_image_schema", return_value=candidate_schema), \
                 mock.patch.object(updater, "_run") as run:
                if original_schema == candidate_schema and original_schema in {3, 4}:
                    updater._candidate_preflight("old:sha", "new:sha", self.config)
                    self.assertEqual(run.call_count, 2, "same-schema candidate check remains isolated")
                else:
                    with self.assertRaisesRegex(updater.UpdateError, "schemas must match supported schema 3 or 4"):
                        updater._candidate_preflight("old:sha", "new:sha", self.config)
                    run.assert_not_called()

        for schema in (3, 4):
            with self.subTest(live=schema, candidate=schema):
                preflight(schema, schema)
        for live, candidate in ((3, 4), (4, 3), (2, 2)):
            with self.subTest(live=live, candidate=candidate):
                preflight(live, candidate)

    def test_failed_prepare_hook_does_not_stop_or_restart_live_service(self):
        with mock.patch.object(updater, "_safe_hook", side_effect=[updater.UpdateError("prepare failed"), None]) as hook, \
             mock.patch.object(updater, "_compose") as compose:
            with self.assertRaisesRegex(updater.UpdateError, "prepare failed"):
                updater._deploy_candidate("new:sha", "old:sha", SHA, self.config, self.config)
        self.assertEqual(hook.call_count, 2, "best effort finish handles a partially applied hook")
        compose.assert_not_called()


if __name__ == "__main__":
    unittest.main()

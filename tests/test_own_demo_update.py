"""Unit coverage for the isolated demo updater's cutover and recovery rules."""
import importlib.util
import json
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "deploy" / "update-demo.py"
SPEC = importlib.util.spec_from_file_location("garage_demo_updater", SCRIPT)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)

OLD = "a" * 40
NEW = "b" * 40


def config_for(root):
    root = Path(root)
    return {
        "DEMO_COMPOSE_FILE": str(root / "compose.runtime.yaml"),
        "DEMO_ENV_FILE": str(root / "demo.env"),
        "DEMO_CONNECTOR_FILE": str(root / "connector.yaml"),
        "DEMO_RELEASE_ROOT": str(root / "releases"),
        "DEMO_STATE_DIR": str(root / "state"),
        "DEMO_IMAGE_PREFIX": "wolfs-garage-demo",
        "DEMO_HEALTH_TIMEOUT": "30",
        "DEMO_ORIGIN": "https://demo.example.invalid",
        "DEMO_PROJECT": "wolfs-garage-demo-rehearsal",
        "_RUNTIME_PORT": "18998",
    }


class DemoUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wg-demo-updater-")
        self.root = Path(self.temp.name)
        self.config = config_for(self.root)
        self.state = Path(self.config["DEMO_STATE_DIR"])
        self.state.mkdir(mode=0o700)
        self.release = Path(self.config["DEMO_RELEASE_ROOT"]) / OLD / "deploy"
        self.release.mkdir(parents=True)
        (self.release / updater.NGINX).write_text("old nginx\n")
        (self.release / updater.LIMITS).write_text("old limits\n")
        (self.state / "active-main-sha").write_text(OLD + "\n")

    def tearDown(self):
        self.temp.cleanup()

    def _mocked_update(self, *, proxy_health=True):
        calls = []
        queried_services = []

        def compose(config, image, templates, *args, **kwargs):
            calls.append((args, kwargs, image, Path(templates)))
            return ""

        def service(config, image, templates, service, **kwargs):
            queried_services.append((service, image, Path(templates)))
            if service == updater.APP:
                return "old-app" if len(queried_services) == 1 else "new-app"
            return "old-proxy" if len(queried_services) == 2 else "new-proxy"

        def healthy(container, timeout):
            if container == "new-proxy":
                return proxy_health
            return True

        def image_of(container):
            return f"wolfs-garage-demo:{OLD}" if container == "old-app" else f"wolfs-garage-demo:{NEW}"

        def templates(container):
            return self.release if container in ("old-proxy", "new-proxy") else self.release

        return calls, queried_services, compose, service, healthy, image_of, templates

    def _patch_update(self, *, proxy_health=True, green=True):
        calls, services, compose, service, healthy, image_of, templates = self._mocked_update(proxy_health=proxy_health)
        stack = ExitStack()
        stack.enter_context(mock.patch.object(updater, "github_main_sha", return_value=NEW))
        stack.enter_context(mock.patch.object(updater, "checks_succeeded", return_value=green))
        stack.enter_context(mock.patch.object(updater, "_service_container", side_effect=service))
        stack.enter_context(mock.patch.object(updater, "_compose", side_effect=compose))
        stack.enter_context(mock.patch.object(updater, "_image_of", side_effect=image_of))
        stack.enter_context(mock.patch.object(updater, "_template_dir", side_effect=templates))
        stack.enter_context(mock.patch.object(updater, "_healthy", side_effect=healthy))
        stack.enter_context(mock.patch.object(updater, "_install_release", return_value=self.root / "candidate"))
        stack.enter_context(mock.patch.object(updater, "_build", return_value=f"wolfs-garage-demo:{NEW}"))
        stack.enter_context(mock.patch.object(updater, "_preflight"))
        stack.enter_context(mock.patch.object(updater, "_verify_deployed"))
        stack.enter_context(mock.patch.object(updater, "_write_journal", return_value={
            "version": 1, "candidate": NEW,
            "previous": {"sha": OLD, "image": f"wolfs-garage-demo:{OLD}", "templates": str(self.release)}}))
        stack.enter_context(mock.patch.object(updater, "_clear_journal"))
        stack.enter_context(mock.patch.object(updater, "_recover"))
        return stack, calls, services

    def test_config_accepts_optional_connector_and_rehearsal_project_prefix(self):
        env = self.root / "runtime.env"
        env.write_text("GARAGE_DEMO_PORT=18998\n")
        cfg = self.root / "updater.env"
        values = {**self.config, "DEMO_ENV_FILE": str(env)}
        cfg.write_text("".join(f"{k}={v}\n" for k, v in values.items() if not k.startswith("_")))
        parsed = updater.load_config(cfg)
        self.assertEqual(parsed["_RUNTIME_PORT"], "18998")
        values["DEMO_PROJECT"] = "wolfs-garage-demo-rehearsal"
        self.assertEqual(updater.load_config(cfg)["DEMO_PROJECT"], "wolfs-garage-demo-rehearsal")
        values["DEMO_PROJECT"] = "unrelated-stack"
        cfg.write_text("".join(f"{k}={v}\n" for k, v in values.items() if not k.startswith("_")))
        with self.assertRaises(updater.UpdateError):
            updater.load_config(cfg)

    def test_generated_final_override_pins_image_and_binds_both_absolute_templates(self):
        override = self.root / "override.yaml"
        updater._override_file(override, image=f"wolfs-garage-demo:{NEW}", templates=self.release,
                              host="demo.example.invalid", port=18998)
        content = override.read_text()
        self.assertIn(f"wolfs-garage-demo:{NEW}", content)
        self.assertIn(str(self.release / updater.NGINX), content)
        self.assertIn(str(self.release / updater.LIMITS), content)
        self.assertEqual(override.stat().st_mode & 0o777, 0o600)

    def test_same_sha_template_drift_does_not_match_checked_release(self):
        release = self.root / "source-checkout"
        checked = release / "deploy"
        checked.mkdir(parents=True)
        actual = self.root / "mounted-templates"
        actual.mkdir()
        expected = {updater.NGINX: "server { listen 8080; }\n",
                    updater.LIMITS: "limit_req_zone $binary_remote_addr zone=demo:10m;\n"}
        for name, content in expected.items():
            (checked / name).write_text(content)
            (actual / name).write_text(content)
        updater._run(["git", "init", str(release)])
        updater._run(["git", "-C", str(release), "config", "user.name", "Updater Test"])
        updater._run(["git", "-C", str(release), "config", "user.email", "updater-test@example.invalid"])
        updater._run(["git", "-C", str(release), "add", "deploy"])
        updater._run(["git", "-C", str(release), "commit", "-m", "template fixture"])
        sha = updater._run(["git", "-C", str(release), "rev-parse", "HEAD"], capture=True)

        with mock.patch.object(updater, "_validate_root_managed_file", return_value=None):
            self.assertTrue(updater._templates_match_release(actual, release, sha))
            (actual / updater.NGINX).write_text("server { listen 8080; # changed\n}\n")
            self.assertFalse(updater._templates_match_release(actual, release, sha))

    def test_release_install_makes_nginx_templates_readable_under_private_service_umask(self):
        source = self.root / "source-repository"
        deploy = source / "deploy"
        deploy.mkdir(parents=True)
        for name in (updater.NGINX, updater.LIMITS):
            (deploy / name).write_text("template\n")
        updater._run(["git", "init", str(source)])
        updater._run(["git", "-C", str(source), "config", "user.name", "Updater Test"])
        updater._run(["git", "-C", str(source), "config", "user.email", "updater-test@example.invalid"])
        updater._run(["git", "-C", str(source), "add", "deploy"])
        updater._run(["git", "-C", str(source), "commit", "-m", "template fixture"])
        sha = updater._run(["git", "-C", str(source), "rev-parse", "HEAD"], capture=True)
        config = {**self.config, "DEMO_RELEASE_ROOT": str(self.root / "release-root")}

        def validate_before_chmod(path):
            self.assertEqual(Path(path).stat().st_mode & 0o777, 0o600)

        previous_umask = os.umask(0o077)
        try:
            with mock.patch.object(updater, "REPOSITORY", str(source)), \
                 mock.patch.object(updater, "_validate_root_managed_file", side_effect=validate_before_chmod):
                release = updater._install_release(config, sha)
        finally:
            os.umask(previous_umask)
        for name in (updater.NGINX, updater.LIMITS):
            self.assertEqual((release / "deploy" / name).stat().st_mode & 0o777, 0o644)

    def test_failed_ci_gate_does_not_build_or_cut_over(self):
        stack, calls, _ = self._patch_update(green=False)
        with stack, mock.patch.object(updater, "_build") as build:
            self.assertFalse(updater.update_once(self.config))
        build.assert_not_called()
        self.assertEqual(calls, [])
        self.assertEqual((self.state / "active-main-sha").read_text().strip(), OLD)

    def test_green_update_builds_exact_commit_and_recreates_app_before_proxy(self):
        stack, calls, _ = self._patch_update()
        with stack, mock.patch.object(updater, "_build", return_value=f"wolfs-garage-demo:{NEW}") as build:
            self.assertTrue(updater.update_once(self.config))
        build.assert_called_once_with(self.config, self.root / "candidate", NEW)
        cutovers = [(args, kwargs) for args, kwargs, _, _ in calls if "up" in args]
        app_index = next(i for i, (args, _) in enumerate(cutovers) if updater.APP in args and "--force-recreate" in args)
        proxy_index = next(i for i, (args, _) in enumerate(cutovers) if updater.PROXY in args)
        self.assertLess(app_index, proxy_index)
        for args, kwargs in cutovers:
            self.assertIn("--no-deps", args)
            self.assertNotIn("connector.yaml", " ".join(str(value) for value in args))
            self.assertTrue(kwargs.get("override"))
        self.assertEqual((self.state / "active-main-sha").read_text().strip(), NEW)

    def test_proxy_failure_calls_rollback_and_keeps_old_marker(self):
        stack, calls, _ = self._patch_update(proxy_health=False)
        with stack as context:
            recover = context.enter_context(mock.patch.object(updater, "_recover"))
            with self.assertRaises(updater.UpdateError):
                updater.update_once(self.config)
        recover.assert_called_once()
        self.assertEqual((self.state / "active-main-sha").read_text().strip(), OLD)

    def test_interrupted_journal_recovery_restores_marker_before_new_main_lookup(self):
        journal = {"version": 1, "candidate": NEW,
                   "previous": {"sha": OLD, "image": f"wolfs-garage-demo:{OLD}", "templates": str(self.release)}}
        (self.state / updater.JOURNAL).write_text(json.dumps(journal))
        with mock.patch.object(updater, "_validate_root_managed_file", return_value=None), \
             mock.patch.object(updater, "_read_journal", return_value=journal), \
             mock.patch.object(updater, "_recover", side_effect=lambda cfg, state, j: updater._write_active(state, OLD)), \
             mock.patch.object(updater, "_recover_preflight"), \
             mock.patch.object(updater, "_service_container", side_effect=["old-app", "old-proxy"]), \
             mock.patch.object(updater, "_image_of", return_value=f"wolfs-garage-demo:{OLD}"), \
             mock.patch.object(updater, "_template_dir", return_value=self.release), \
             mock.patch.object(updater, "_templates_match_release", return_value=True), \
             mock.patch.object(updater, "github_main_sha", return_value=OLD) as main_sha, \
             mock.patch.object(updater, "checks_succeeded", return_value=True), \
             mock.patch.object(updater, "_healthy", return_value=True), \
             mock.patch.object(updater, "_verify_deployed"):
            self.assertFalse(updater.update_once(self.config))
        main_sha.assert_called_once()
        self.assertEqual((self.state / "active-main-sha").read_text().strip(), OLD)

    def test_rollback_uses_publicly_readable_unique_template_snapshots(self):
        with mock.patch.object(updater, "_validate_root_managed_file", return_value=None):
            first = updater._snapshot_templates(self.state, self.release, OLD)
            second = updater._snapshot_templates(self.state, self.release, OLD)
        self.assertNotEqual(first, second)
        self.assertEqual((first / updater.NGINX).stat().st_mode & 0o777, 0o644)
        self.assertEqual((second / updater.LIMITS).read_text(), "old limits\n")

    def test_real_recovery_restores_old_marker_and_clears_journal_only_after_checks(self):
        snapshot = self.state / "rollback-templates" / OLD
        snapshot.mkdir(parents=True)
        for name in (updater.NGINX, updater.LIMITS):
            (snapshot / name).write_text("old\n")
            (snapshot / name).chmod(0o644)
        (self.state / "active-main-sha").write_text(NEW + "\n")
        journal = {"version": 1, "candidate": NEW,
                   "previous": {"sha": OLD, "image": f"wolfs-garage-demo:{OLD}", "templates": str(snapshot)}}
        (self.state / updater.JOURNAL).write_text(json.dumps(journal))
        with mock.patch.object(updater, "_compose") as compose, \
             mock.patch.object(updater, "_service_container", side_effect=["restored-app", "restored-proxy"]), \
             mock.patch.object(updater, "_healthy", return_value=True), \
             mock.patch.object(updater, "_verify_deployed") as verify:
            updater._recover(self.config, self.state, journal)
        self.assertEqual((self.state / "active-main-sha").read_text().strip(), OLD)
        self.assertFalse((self.state / updater.JOURNAL).exists())
        verify.assert_called_once()
        self.assertEqual(compose.call_count, 2)

    def test_steady_state_http_check_does_not_require_five_vehicles(self):
        with mock.patch.object(updater, "_http", side_effect=[(200, b""),
             (200, b'{"demo":{"shared":true},"features":[]}')]) as request:
            updater._verify_http(18998, "demo.example.invalid", synthetic=False)
        self.assertEqual(request.call_count, 2)

    def test_connector_overlay_is_ordered_before_generated_final_runtime_override(self):
        with mock.patch.object(updater, "_run", return_value="") as run:
            updater._compose(self.config, f"wolfs-garage-demo:{NEW}", self.release, "config", override=self.root / "last.yaml")
        command = run.call_args.args[0]
        self.assertLess(command.index(self.config["DEMO_CONNECTOR_FILE"]), command.index(self.config["DEMO_COMPOSE_FILE"]))
        self.assertEqual(command[-3:], ["-f", str(self.root / "last.yaml"), "config"])


if __name__ == "__main__":
    unittest.main()

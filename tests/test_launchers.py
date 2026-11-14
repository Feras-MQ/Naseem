"""Operator launchers work outside the checkout and never silently install/open USB."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location("naseem_launcher_" + name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


start = load_script("start")
setup_usb = load_script("setup_usb")


class LauncherTests(unittest.TestCase):
    def test_source_cli_from_another_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/start.py"), "--help"],
                                    cwd=directory, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("simulate", result.stdout)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_invalid_cli_preserves_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/start.py"), "not-a-command"],
                                    cwd=directory, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_default_demo_with_spaces_and_arabic_checkout_path(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "Naseem demo نسيم"
            (checkout / "scripts").mkdir(parents=True)
            shutil.copytree(ROOT / "naseem", checkout / "naseem", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy2(ROOT / "scripts/start.py", checkout / "scripts/start.py")
            for unused in range(2):
                # Force a legacy Windows-like redirected encoding. The launcher
                # must configure UTF-8 before printing the Arabic path.
                environment = dict(os.environ, PYTHONIOENCODING="cp1252")
                result = subprocess.run([sys.executable, str(checkout / "scripts/start.py")],
                                        cwd=directory, env=environment, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("SYNTHETIC DEMO ONLY", result.stdout)
                self.assertIn("report.html", result.stdout)
            outputs = list((checkout / "data/demos").iterdir())
            self.assertEqual(len(outputs), 2)
            for output in outputs:
                self.assertTrue((output / "report.html").is_file())
                self.assertEqual(json.loads((output / "summary.json").read_text())["accepted"], 72)
                self.assertFalse((output / "INCOMPLETE.txt").exists())
            self.assertFalse((checkout / ".venv").exists())

    def test_usb_entrypoint_prints_unicode_errors_with_legacy_redirect_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "Naseem project نسيم"
            (checkout / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/setup_usb.py", checkout / "scripts/setup_usb.py")
            (checkout / "pyproject.toml").write_text("[project]\nname='naseem-prototype'\n", encoding="utf-8")
            # A foreign directory fails before interpreter probing or downloads.
            (checkout / ".venv").mkdir()
            keep = checkout / ".venv/keep.txt"
            keep.write_text("keep")
            result = subprocess.run([sys.executable, str(checkout / "scripts/setup_usb.py")],
                                    cwd=directory, env=dict(os.environ, PYTHONIOENCODING="cp1252"),
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("نسيم", result.stderr)
            self.assertIn("not a Python virtual environment", result.stderr)
            self.assertNotIn("UnicodeEncodeError", result.stderr)
            self.assertEqual(keep.read_text(), "keep")

    def test_demo_failure_reports_nonzero(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(start, "ROOT", Path(directory)), \
                patch("naseem.demo.create_demo", side_effect=OSError("test storage failure")), redirect_stderr(io.StringIO()) as error:
            self.assertEqual(start.main([]), 2)
            self.assertIn("test storage failure", error.getvalue())


class UsbSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Naseem project نسيم"
        self.root.mkdir()
        (self.root / "pyproject.toml").write_text("[project]\nname='naseem-prototype'\n", encoding="utf-8")
        self.environment = self.root / ".venv"

    def make_environment(self, environment=None, shared=False):
        environment = Path(environment or self.environment)
        environment.mkdir(exist_ok=True)
        (environment / "pyvenv.cfg").write_text(
            "include-system-site-packages = " + ("true" if shared else "false") + "\n", encoding="utf-8")
        executable = setup_usb.environment_python(environment)
        executable.parent.mkdir(exist_ok=True)
        executable.write_text("fake interpreter used only with mocked subprocess\n", encoding="utf-8")
        return executable

    def probe(self, prefix=None, base_prefix=None, version=None):
        return SimpleNamespace(stdout=json.dumps({"prefix": str(prefix or self.environment),
                "base_prefix": str(base_prefix or self.root / "system-python"), "version": version or [3, 12, 0]}))

    def test_foreign_existing_directory_is_untouched(self):
        self.environment.mkdir()
        keep = self.environment / "important.txt"
        keep.write_text("keep")
        with patch.object(setup_usb.subprocess, "run") as run, patch.object(setup_usb.venv, "EnvBuilder") as builder:
            with self.assertRaisesRegex(RuntimeError, "not a Python virtual environment"):
                setup_usb.setup(self.root)
            run.assert_not_called()
            builder.assert_not_called()
        self.assertEqual(keep.read_text(), "keep")

    def test_reuse_valid_venv_installs_only_into_verified_interpreter(self):
        executable = self.make_environment()
        with patch.object(setup_usb.subprocess, "run", side_effect=[self.probe(), SimpleNamespace(returncode=0)]) as run, \
                patch.object(setup_usb.venv, "EnvBuilder") as builder, redirect_stdout(io.StringIO()):
            self.assertEqual(setup_usb.setup(self.root), 0)
            builder.assert_not_called()
            command = run.call_args_list[1].args[0]
            # Windows temp paths may use an 8.3 alias (RUNNER~1), whereas
            # setup canonicalizes the root. Both spellings must identify the
            # same local interpreter, rather than matching raw path strings.
            self.assertTrue(Path(command[0]).samefile(executable))
            self.assertIn("--require-virtualenv", command)
            self.assertIn("--isolated", command)
            self.assertEqual(command[-1], str(self.root.resolve()) + "[serial]")
            self.assertEqual(run.call_args_list[1].kwargs["cwd"], self.root.resolve())
            self.assertTrue(run.call_args_list[1].kwargs["check"])

    def test_new_environment_created_without_clearing(self):
        builder_instance = Mock()
        builder_instance.create.side_effect = self.make_environment
        with patch.object(setup_usb.venv, "EnvBuilder", return_value=builder_instance) as builder, \
                patch.object(setup_usb.subprocess, "run", side_effect=[self.probe(), SimpleNamespace(returncode=0)]), redirect_stdout(io.StringIO()):
            self.assertEqual(setup_usb.setup(self.root), 0)
            builder.assert_called_once_with(with_pip=True, system_site_packages=False, clear=False)
            builder_instance.create.assert_called_once_with(self.environment.resolve())

    def test_shared_site_packages_rejected_before_interpreter_run(self):
        self.make_environment(shared=True)
        with patch.object(setup_usb.subprocess, "run") as run, self.assertRaisesRegex(RuntimeError, "isolated"):
            setup_usb.setup(self.root)
        run.assert_not_called()

    def test_system_or_misdirected_or_old_python_is_rejected(self):
        self.make_environment()
        for probe in (self.probe(base_prefix=self.environment), self.probe(prefix=self.root / "elsewhere"),
                      self.probe(version=[3, 9, 0])):
            with self.subTest(probe=probe), patch.object(setup_usb.subprocess, "run", return_value=probe) as run, \
                    self.assertRaisesRegex(RuntimeError, "Refusing to install"):
                setup_usb.setup(self.root)
            self.assertEqual(run.call_count, 1)

    @unittest.skipIf(sys.platform == "win32", "Unprivileged Windows symlink creation is not assumed")
    def test_linked_environment_is_rejected(self):
        other = self.root / "other"
        other.mkdir()
        self.environment.symlink_to(other, target_is_directory=True)
        with patch.object(setup_usb.subprocess, "run") as run, self.assertRaisesRegex(RuntimeError, "linked"):
            setup_usb.setup(self.root)
        run.assert_not_called()

    def test_windows_reparse_point_environment_is_rejected(self):
        self.make_environment()
        attributes = SimpleNamespace(st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=attributes), \
                patch.object(setup_usb.subprocess, "run") as run, self.assertRaisesRegex(RuntimeError, "linked"):
            setup_usb.verify_environment(self.environment)
        run.assert_not_called()

    def test_failed_install_is_nonzero_and_environment_preserved(self):
        executable = self.make_environment()
        with patch.object(setup_usb, "setup", side_effect=subprocess.CalledProcessError(1, [str(executable), "pip"])), \
                redirect_stderr(io.StringIO()) as error:
            self.assertEqual(setup_usb.main([]), 2)
        self.assertTrue(executable.exists())
        self.assertIn("USB setup stopped", error.getvalue())


if __name__ == "__main__":
    unittest.main()

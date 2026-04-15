import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lirox.utils import dependency_bootstrap as db


class DependencyBootstrapTests(unittest.TestCase):
    def test_required_package_map_reads_requirements(self):
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp) / "requirements.txt"
            req.write_text(
                "\n".join(
                    [
                        "rich>=13.0.0",
                        "prompt-toolkit>=3.0.0",
                        "duckduckgo-search>=6.1.0",
                        "# comment",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch("lirox.utils.dependency_bootstrap._repo_root", Path(tmp)):
                pkg_map = db.required_package_map()
            self.assertEqual(pkg_map["rich"], "rich")
            self.assertEqual(pkg_map["prompt-toolkit"], "prompt_toolkit")
            self.assertEqual(pkg_map["duckduckgo-search"], "duckduckgo_search")

    def test_install_missing_packages_falls_back_to_individual_installs(self):
        with mock.patch("lirox.utils.dependency_bootstrap.run_pip_install", side_effect=[False, True, False, False]) as mocked_install:
            installed, failed = db.install_missing_packages(["rich", "requests"])
        self.assertEqual(installed, ["rich"])
        self.assertEqual(failed, ["requests"])
        self.assertEqual(mocked_install.call_count, 4)
        self.assertEqual(mocked_install.call_args_list[0].args[0], ["rich", "requests"])

    def test_manual_install_hint_windows(self):
        with mock.patch("lirox.utils.dependency_bootstrap.platform.system", return_value="Windows"):
            hint = db.manual_install_hint(["rich"])
        self.assertIn("py -m pip install rich", hint)

    def test_manual_install_hint_posix(self):
        with mock.patch("lirox.utils.dependency_bootstrap.platform.system", return_value="Linux"):
            hint = db.manual_install_hint(["rich"])
        self.assertIn("python3 -m pip install rich", hint)

    def test_format_failed_packages_message(self):
        with mock.patch("lirox.utils.dependency_bootstrap.platform.system", return_value="Linux"):
            message = db.format_failed_packages_message(["rich"])
        self.assertIn("Failed packages: rich", message)
        self.assertIn("python3 -m pip install rich", message)


if __name__ == "__main__":
    unittest.main()

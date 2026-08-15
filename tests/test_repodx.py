import tempfile
import unittest
from pathlib import Path

import repodx


class RepoDxTests(unittest.TestCase):
    def test_find_junk_files_reports_expected_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            (repo_path / "cache.tmp").write_text("tmp", encoding="utf-8")
            (repo_path / ".DS_Store").write_text("mac", encoding="utf-8")
            (repo_path / "__pycache__").mkdir()
            (repo_path / "__pycache__" / "example.pyc").write_text(
                "cache", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "node_modules" / "example.txt").write_text(
                "module", encoding="utf-8"
            )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(
                result,
                [
                    ".DS_Store",
                    "__pycache__/",
                    "cache.tmp",
                    "debug.log",
                    "node_modules/",
                ],
            )

    def test_find_junk_files_skips_ignored_node_modules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/\n", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_check_gitignore_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, ["Missing .gitignore file"])

    def test_check_gitignore_reports_missing_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing .gitignore entry: __pycache__/",
                    "Missing .gitignore entry: node_modules/",
                ],
            )

    def test_check_readme_accepts_english_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n## Installation\n\n## Usage\n", encoding="utf-8"
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_turkish_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n## Kurulum\n\n## Kullanım\n", encoding="utf-8"
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_reports_missing_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text("# Project\n", encoding="utf-8")

            result = repodx.check_readme(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing README heading: Installation",
                    "Missing README heading: Usage",
                ],
            )

    def test_build_report_combines_all_checks(self):
        sample_path = Path("sample_repo")

        report = repodx.build_report(sample_path)

        self.assertEqual(
            report,
            {
                "junk_items": [
                    "__pycache__/",
                    "cache.tmp",
                    "debug.log",
                    "node_modules/",
                ],
                "gitignore_issues": [
                    "Missing .gitignore entry: __pycache__/",
                    "Missing .gitignore entry: .env",
                    "Missing .gitignore entry: node_modules/",
                ],
                "readme_issues": [
                    "Missing README heading: Installation",
                    "Missing README heading: Usage",
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()

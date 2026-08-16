import tempfile
import unittest
from unittest import mock
from pathlib import Path

import repodx


SAMPLE_DIR = Path(__file__).parent / "sample"


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

    def test_find_junk_files_skips_ignored_pycache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/\n", encoding="utf-8"
            )
            (repo_path / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_skips_directories_ignored_with_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/*\n__pycache__/*\n", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_skips_directories_ignored_with_double_star_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/**\n__pycache__/**\n", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_does_not_report_files_inside_junk_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "__pycache__").mkdir()
            (repo_path / "__pycache__" / "debug.log").write_text(
                "log", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "node_modules" / "cache.tmp").write_text(
                "tmp", encoding="utf-8"
            )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["__pycache__/", "node_modules/"])

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

    def test_check_gitignore_accepts_common_entry_variations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "**/__pycache__/\n.env\n**/node_modules\n", encoding="utf-8"
            )

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, [])

    def test_check_gitignore_accepts_directory_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/*\n.env\nnode_modules/*\n", encoding="utf-8"
            )

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, [])

    def test_check_gitignore_accepts_double_star_directory_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/**\n.env\nnode_modules/**\n", encoding="utf-8"
            )

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, [])

    def test_has_gitignore_entry_accepts_double_star_prefix_and_slash_variants(self):
        entries = ["**/__pycache__/", ".env", "**/node_modules"]

        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules"))

    def test_has_gitignore_entry_accepts_directory_content_globs(self):
        entries = ["**/__pycache__/*", ".env", "node_modules/*"]

        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules/"))

    def test_has_gitignore_entry_accepts_double_star_content_globs(self):
        entries = ["**/__pycache__/**", ".env", "node_modules/**"]

        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules/"))

    def test_check_gitignore_reports_unreadable_file(self):
        repo_path = SAMPLE_DIR / "bad_gitignore_repo"

        result = repodx.check_gitignore(repo_path)

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("Could not read .gitignore:"))

    def test_check_gitignore_reports_os_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")

            with mock.patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                result = repodx.check_gitignore(repo_path)

            self.assertEqual(len(result), 1)
            self.assertEqual(
                result[0], "Could not read .gitignore: permission denied"
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

    def test_check_readme_reports_unreadable_file(self):
        repo_path = SAMPLE_DIR / "bad_readme_repo"

        result = repodx.check_readme(repo_path)

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("Could not read README.md:"))

    def test_check_readme_ignores_heading_like_lines_inside_code_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n"
                "```python\n"
                "# Installation\n"
                "# Usage\n"
                "```\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing README heading: Installation",
                    "Missing README heading: Usage",
                ],
            )

    def test_check_readme_accepts_real_headings_around_code_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n"
                "## Installation\n\n"
                "```python\n"
                "# Not a heading\n"
                "```\n\n"
                "## Usage\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_reports_os_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text("# Project\n", encoding="utf-8")

            with mock.patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                result = repodx.check_readme(repo_path)

            self.assertEqual(
                result, ["Could not read README.md: permission denied"]
            )

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

import base64
import ctypes
from ctypes import wintypes
import io
import json
import os
import re
import shutil
import subprocess
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

    def test_find_junk_files_reports_unignored_virtual_environment_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            for name in [".venv", "venv", "env"]:
                (repo_path / name).mkdir()
                (repo_path / name / "pyvenv.cfg").write_text(
                    "home = /usr/bin\n", encoding="utf-8"
                )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [".venv/", "env/", "venv/"])

    def test_find_junk_files_skips_ignored_virtual_environment_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                ".venv/\nvenv/\nenv/\n", encoding="utf-8"
            )
            for name in [".venv", "venv", "env"]:
                (repo_path / name).mkdir()
                (repo_path / name / "pyvenv.cfg").write_text(
                    "home = /usr/bin\n", encoding="utf-8"
                )

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

    def test_find_junk_files_ignores_env_folders_that_are_not_virtualenvs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "env").mkdir()
            (repo_path / "env" / "production.yaml").write_text(
                "debug: false\n", encoding="utf-8"
            )
            (repo_path / "env" / "deploy.log").write_text("log", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["env/deploy.log"])

    def test_find_junk_files_skips_files_ignored_by_gitignore_patterns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "*.log\n**/*.tmp\n.DS_Store\n", encoding="utf-8"
            )
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            (repo_path / "src").mkdir()
            (repo_path / "src" / "cache.tmp").write_text("tmp", encoding="utf-8")
            (repo_path / "src" / ".DS_Store").write_text("mac", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_respects_gitignore_negation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "*.log\n!keep/**\n", encoding="utf-8"
            )
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            (repo_path / "keep").mkdir()
            (repo_path / "keep" / "trace.log").write_text("log", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["keep/trace.log"])

    def test_find_junk_files_matches_suffixes_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "DEBUG.LOG").write_text("log", encoding="utf-8")
            (repo_path / "Cache.Tmp").write_text("tmp", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["Cache.Tmp", "DEBUG.LOG"])

    def test_find_junk_files_does_not_walk_into_junk_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/\n", encoding="utf-8"
            )
            (repo_path / "node_modules" / "pkg").mkdir(parents=True)
            visited = []
            real_walk = repodx.os.walk

            def recording_walk(top):
                for current_dir, dir_names, file_names in real_walk(top):
                    visited.append(Path(current_dir).name)
                    yield current_dir, dir_names, file_names

            with mock.patch.object(repodx.os, "walk", recording_walk):
                result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])
            self.assertNotIn("node_modules", visited)
            self.assertNotIn("pkg", visited)

    def test_find_junk_files_respects_negated_directory_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/\nnode_modules/\n!fixtures/**\n", encoding="utf-8"
            )
            (repo_path / "__pycache__").mkdir()
            (repo_path / "fixtures" / "__pycache__").mkdir(parents=True)
            (repo_path / "fixtures" / "node_modules").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(
                result, ["fixtures/__pycache__/", "fixtures/node_modules/"]
            )

    def test_find_junk_files_skips_contents_of_ignored_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text("build/\n", encoding="utf-8")
            (repo_path / "build").mkdir()
            (repo_path / "build" / "output.log").write_text("log", encoding="utf-8")
            (repo_path / "build" / "__pycache__").mkdir()

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

    def test_check_readme_accepts_setext_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "Project\n=======\n\nInstallation\n------------\n\nUsage\n-----\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_quickstart_style_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text("# App\n\n## Quickstart\n", encoding="utf-8")

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_closed_atx_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project #\n\n## Installation ##\n\n## Usage ##\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_lowercase_file_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "readme.md").write_text(
                "# Project\n\n## Installation\n\n## Usage\n", encoding="utf-8"
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_rst_readme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.rst").write_text(
                "Project\n=======\n\nInstallation\n~~~~~~~~~~~~\n\nUsage\n^^^^^\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, ["Missing README file"])

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

    def test_check_readme_ignores_setext_headings_inside_code_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n"
                "```text\n"
                "Installation\n"
                "------------\n"
                "Usage\n"
                "-----\n"
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

    def test_build_report_scores_sample_repo(self):
        report = repodx.build_report(Path("sample_repo"))
        found = {(finding["id"], finding["path"], finding["detail"]) for finding in report["findings"]}

        self.assertEqual(report["counts"], {"critical": 3, "warning": 7, "info": 3})
        self.assertEqual(report["grade"], "F")
        self.assertIn(("database-url", "app.js", "hunter...7v"), found)
        self.assertIn(("env-file", ".env", None), found)
        self.assertIn(("firebase-rules", "firestore.rules", None), found)
        self.assertIn(("supabase-rls", "supabase/migrations/001_init.sql", "profiles"), found)
        self.assertIn(("junk", "node_modules/", None), found)
        self.assertIn(("license", None, None), found)
        self.assertIn(("env-example", None, None), found)


def fake(*parts):
    """Join parts at runtime so no scanner sees a literal key in this file."""
    return "".join(parts)


def make_repo(temp_dir, files):
    repo_path = Path(temp_dir)

    for relative_text, content in files.items():
        path = repo_path / relative_text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return repo_path


def findings_for(repo_path, check_id):
    report = repodx.build_report(repo_path)
    return [finding for finding in report["findings"] if finding["id"] == check_id]


class SecretScanTests(unittest.TestCase):
    def test_detects_provider_keys(self):
        keys = {
            "OpenAI API key": fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2"),
            "OpenRouter API key": fake(
                "sk-", "or-v1-", "f1e2d3c4b5a69788796a5b4c3d2e1f0af9e8d7c6b5a49382716f0e1d2c3ba4b7"
            ),
            "Anthropic API key": fake("sk-", "ant-", "api03-", "A1b2C3d4E5f6G7h8I9j0"),
            "AWS access key": fake("AKIA", "Q7ZT4MWX9RB2KD5N"),
            "GitHub token": fake("ghp", "_", "q7ZT4mWx9Rb2Kd5Nf8Lp3Hs6Vc1Yj0GuE4tA"),
            "GitLab token": fake("glpat", "-", "Q7zT4mWx9Rb2Kd5Nf8Lp"),
            "npm access token": fake("npm_", "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"),
            "Shopify token": fake("shpat", "_", "9f4e6a2b7c8d0a1b2c3d4e5f6a7b8c9d"),
            "DigitalOcean token": fake("dop_v1_", "f1e2d3c4b5a69788796a5b4c3d2e1f0af9e8d7c6b5a49382716f0e1d2c3ba4b7"),
            "PyPI API token": fake(
                "pypi-", "AgEIcHlwaS5vcmc", "q7ZT4mWx9Rb2Kd5Nf8Lp3Hs6Vc1Yj0GuE4tA_BnC7Xq2Zw5Mu6"
            ),
            "Stripe secret key": fake("sk", "_live_", "A1b2C3d4E5f6G7h8I9j0K1"),
            "Supabase secret key": fake("sb", "_secret_", "A1b2C3d4E5f6G7h8I9j0K1"),
            "Perplexity API key": fake("pplx", "-", "Q7zT4mWx9Rb2Kd5Nf8Lp3Hs6Vc1Yj0GuE4tA9BnC7Xq2Zw5M"),
            "Replicate API token": fake("r8", "_", "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S"),
            "Discord webhook URL": fake(
                "https://discord.com/api/webhooks/",
                "908172635490817263/",
                "A1b2C3d4E5f6G7h8I9j0K1_lmn-OPQR",
            ),
            "Slack webhook URL": fake(
                "https://hooks.slack.com/services/",
                "TXZ9MQKPLR/",
                "BZQ8NPRVMC/",
                "aZ7qLm9P2vRt6NsQ4xYb",
            ),
        }

        for name, key in keys.items():
            with self.subTest(name=name):
                hits = repodx.scan_line_for_secrets(f'const key = "{key}";')

                self.assertEqual([(hit[0], hit[1], hit[2]) for hit in hits], [("secret", "critical", name)])

    def test_detects_digitalocean_oauth_token(self):
        key = fake("doo_v1_", "f1e2d3c4b5a69788796a5b4c3d2e1f0af9e8d7c6b5a49382716f0e1d2c3ba4b7")

        hits = repodx.scan_line_for_secrets(f'DIGITALOCEAN_TOKEN="{key}"')

        self.assertEqual([(hit[0], hit[1], hit[2]) for hit in hits], [("secret", "critical", "DigitalOcean token")])

    def test_detects_slack_webhook_url(self):
        url = fake("https://hooks.slack.com/services/", "T012AB3CDE", "/", "B012EF4GHI", "/", "a1B2c3D4e5F6g7H8i9J0k1")
        hits = repodx.scan_line_for_secrets(f"SLACK_WEBHOOK={url}")

        self.assertEqual(
            [(hit[0], hit[1], hit[2]) for hit in hits],
            [("secret", "critical", "Slack webhook URL")],
        )

    def test_ignores_placeholder_slack_webhook_url(self):
        line = fake("webhook: ", "https://hooks.slack.com/services/XXXX/XXXX/XXXX")

        self.assertEqual(repodx.scan_line_for_secrets(line), [])

    def test_ignores_documentation_placeholders(self):
        lines = [
            fake("aws_key = '", "AKIA", "IOSFODNN7EXAMPLE", "'"),
            fake("SLACK_TOKEN=", "xoxb", "-0000000000-0000000000-abc"),
            fake("api_key: '", "sb_secret_", "abcdefghijklmnopqrstuv", "'"),
            fake("client_secret: '", "sb_secret_", "live_example_9f4d3a206b2e", "'"),
            "postgres://postgres:[YOUR-PASSWORD]@db.abc.supabase.co:5432/postgres",
            "postgres://postgres:********@db.abc.supabase.co:5432/postgres",
            "postgres://app:$DB_PASSWORD@db.abc.supabase.co:5432/postgres",
            "postgres://postgres:sbp_111222333aaabbbccc@db.prod-host.dev/postgres",
            "postgresql://postgres:..@db.<ref>.supabase.co:5432/postgres",
            "postgres://postgres:s3cr3t-value@db.{project-ref}.supabase.co/postgres",
            "psql postgres://postgres:my_password@proxy.wasm.dev:5432",
            "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN",
            "https://hooks.slack.com/services/XXXX/XXXX/XXXX",
        ]

        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(repodx.scan_line_for_secrets(line), [])

    def test_ignores_supabase_cli_demo_jwt(self):
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"iss": "supabase-demo", "role": "service_role"}).encode()
        ).decode().rstrip("=")

        self.assertEqual(repodx.scan_line_for_secrets(f"k='{header}.{payload}.c2lnbmF0dXJlc2ln'"), [])

    def test_private_key_needs_a_real_body(self):
        header = fake("-----BEGIN ", "RSA PRIVATE KEY-----")
        body = "MIIEowIBAAKCAQEAu7Qx9Zp3Lk2Vn8Wm4Rt6Yc1Hb5Jd0Gf7Ne2Sa9Ku3Xo8Pi6Lq4" * 2
        real = f'key = "{header}\\n{body}\\n-----END RSA PRIVATE KEY-----"\n'
        multiline = f"{header}\n{body[:64]}\n{body[64:]}\n"
        template = f'key = "{header}\\n...\\n-----END RSA PRIVATE KEY-----"\n'
        docs = f"> PRIVATE_KEY=\"{header}\n> ...\n> Kh9NV...\n"

        self.assertEqual(list(repodx.find_private_keys(real)), [1])
        self.assertEqual(list(repodx.find_private_keys(multiline)), [1])
        self.assertEqual(list(repodx.find_private_keys(template)), [])
        self.assertEqual(list(repodx.find_private_keys(docs)), [])

    def test_secrets_in_test_files_are_warnings(self):
        key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {"src/app.js": f"k='{key}'\n", "tests/test_app.py": f"k='{key}'\n", "src/api.test.ts": f"k='{key}'\n"},
            )

            result = findings_for(repo_path, "secret")

        self.assertEqual(
            sorted((f["path"], f["severity"], f["title"]) for f in result),
            [
                ("src/api.test.ts", "warning", "OpenAI API key in a test or example file"),
                ("src/app.js", "critical", "OpenAI API key"),
                ("tests/test_app.py", "warning", "OpenAI API key in a test or example file"),
            ],
        )

    def test_reports_secret_location_and_masks_value(self):
        key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"src/app.js": f"// setup\nconst key = '{key}';\n"})

            result = findings_for(repo_path, "secret")

        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["path"], result[0]["line"]), ("src/app.js", 2))
        self.assertEqual(result[0]["detail"], "sk-pro...l2")
        self.assertNotIn(key, result[0]["detail"])

    def test_skips_files_ignored_by_gitignore(self):
        key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {".gitignore": ".env\n", ".env": f"OPENAI_API_KEY={key}\n"})

            self.assertEqual(findings_for(repo_path, "secret"), [])
            self.assertEqual(findings_for(repo_path, "env-file"), [])

    def test_inline_ignore_marker_suppresses_finding(self):
        key = fake("AKIA", "Q7ZT4MWX9RB2KD5N")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"docs.md": f"Example: {key} <!-- repodx:ignore -->\n"})

            self.assertEqual(findings_for(repo_path, "secret"), [])

    def test_repodxignore_excludes_paths(self):
        key = fake("AKIA", "Q7ZT4MWX9RB2KD5N")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {".repodxignore": "fixtures/\n", "fixtures/key.txt": key, "fixtures/node_modules/x.js": ""},
            )

            report = repodx.build_report(repo_path)

        self.assertEqual([f for f in report["findings"] if f["path"] and "fixtures" in f["path"]], [])

    def test_skips_binary_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "image.png").write_bytes(b"\x89PNG\0" + fake("AKIA", "Q7ZT4MWX9RB2KD5N").encode())

            self.assertEqual(findings_for(repo_path, "secret"), [])

    def test_google_key_is_a_warning(self):
        hits = repodx.scan_line_for_secrets(fake("apiKey: 'AIza", "Sy8Q7ZT4mWx9Rb2Kd5Nf8Lp3Hs6Vc1Yj0Gu", "'"))

        self.assertEqual([(hit[0], hit[1]) for hit in hits], [("google-api-key", "warning")])

    def test_detects_supabase_service_role_jwt_but_not_anon(self):
        def jwt(role):
            header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
            payload = base64.urlsafe_b64encode(
                json.dumps({"iss": "supabase", "role": role}).encode()
            ).decode().rstrip("=")
            return f"{header}.{payload}.c2lnbmF0dXJlc2lnbmF0dXJl"

        service_hits = repodx.scan_line_for_secrets(f"key = '{jwt('service_role')}'")
        anon_hits = repodx.scan_line_for_secrets(f"key = '{jwt('anon')}'")

        self.assertEqual([hit[0] for hit in service_hits], ["supabase-service-role"])
        self.assertEqual(anon_hits, [])

    def test_database_url_detects_percent_encoded_passwords(self):
        for scheme in ("postgres", "postgresql", "mysql", "mariadb", "mongodb", "mongodb+srv", "redis", "rediss", "amqp", "amqps"):
            for escape in ("%40", "%3A", "%2F", "%2f", "%25", "%24", "%D0%AD"):
                password = fake("q7Zv", escape, "R9mK")

                with self.subTest(scheme=scheme, escape=escape):
                    hits = repodx.scan_line_for_secrets(f"{scheme}://app:{password}@db.prod.example.net/app")

                    self.assertEqual(
                        hits, [("database-url", "critical", "Database URL with password", password)]
                    )

    def test_database_url_still_ignores_percent_templates(self):
        for password in ("%DB_TOKEN%", "%s", "%(db_token)s", "q7Zv%40%DB_TOKEN%", "your-token%40", "$DB_TOKEN%40"):
            with self.subTest(password=password):
                hits = repodx.scan_line_for_secrets(f"postgres://app:{password}@db.prod.example.net/app")

                self.assertEqual(hits, [])

    def test_reports_encoded_database_password_location_and_masks_value(self):
        password = fake("q7Zv", "%40", "R9mK", "%25", "2w")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {"src/app.js": f"// setup\nconst db = 'postgres://app:{password}@db.prod.example.net/app';\n"},
            )

            result = findings_for(repo_path, "database-url")

        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["path"], result[0]["line"], result[0]["severity"]), ("src/app.js", 2, "critical"))
        self.assertEqual(result[0]["detail"], repodx.mask_secret(password))
        self.assertNotIn(password, json.dumps(result))

    def test_database_url_ignores_local_hosts_and_placeholders(self):
        remote = repodx.scan_line_for_secrets("postgres://app:s3cr3t-value@db.prod.example.net:5432/app")
        local = repodx.scan_line_for_secrets("postgres://app:s3cr3t-value@localhost:5432/app")
        placeholder = repodx.scan_line_for_secrets("postgres://user:password@db.prod.example.net/app")
        template = repodx.scan_line_for_secrets("postgres://user:${DB_PASSWORD}@db.prod.example.net/app")

        self.assertEqual([hit[0] for hit in remote], ["database-url"])
        self.assertEqual((local, placeholder, template), ([], [], []))


class ConfigCheckTests(unittest.TestCase):
    def test_env_file_reported_but_example_is_fine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {".env": "A=1\n", ".env.local": "A=1\n", ".env.production": "A=1\n", ".env.example": "A=\n"},
            )

            result = findings_for(repo_path, "env-file")

        self.assertEqual(
            sorted((f["path"], f["severity"]) for f in result),
            [(".env", "critical"), (".env.local", "critical"), (".env.production", "warning")],
        )

    def test_gitignore_expectations_follow_project_type(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            python_repo = make_repo(temp_dir, {".gitignore": ".env*\n", "main.py": ""})

            self.assertEqual(
                repodx.check_gitignore(python_repo, ["main.py"]),
                ["Missing .gitignore entry: __pycache__/"],
            )
            self.assertEqual(
                repodx.check_gitignore(python_repo, ["package.json"]),
                ["Missing .gitignore entry: node_modules/"],
            )

    def test_github_action_dist_is_not_junk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {".github/actions/label/action.yml": "", ".github/actions/label/dist/index.js": "", "web/dist/app.js": ""},
            )

            self.assertEqual(repodx.find_junk_files(repo_path), ["web/dist/"])

    def test_env_example_variants_are_not_env_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {".env.local.example": "A=\n", "main.py": "import os\nos.getenv('A')\n"})

            self.assertEqual(findings_for(repo_path, "env-file"), [])
            self.assertEqual(findings_for(repo_path, "env-example"), [])

    def test_env_file_with_only_public_variables_is_a_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir, {".env": "# public\nNEXT_PUBLIC_URL=https://example.com\nEXPO_PUBLIC_API=/api\n"}
            )

            result = findings_for(repo_path, "env-file")

        self.assertEqual([f["severity"] for f in result], ["warning"])

    def test_env_file_in_examples_is_a_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"examples/with-db/.env": "A=1\n"})

            result = findings_for(repo_path, "env-file")

        self.assertEqual([f["severity"] for f in result], ["warning"])

    def test_env_example_suggested_when_code_reads_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"main.py": "import os\nkey = os.getenv('KEY')\n"})
            missing = findings_for(repo_path, "env-example")
            (repo_path / ".env.example").write_text("KEY=\n", encoding="utf-8")
            present = findings_for(repo_path, "env-example")

        self.assertEqual(len(missing), 1)
        self.assertEqual(present, [])

    def test_public_prefixed_secret_in_env_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    ".env": (
                        "NEXT_PUBLIC_URL=https://example.com\n"
                        "NEXT_PUBLIC_OPENAI_API_KEY=sk-test\n"
                        "VITE_STRIPE_SECRET_KEY=sk_live_x\n"
                        "EXPO_PUBLIC_AUTH_TOKEN=abc\n"
                    )
                },
            )
            result = findings_for(repo_path, "public-env-secret")

        found = {(f["detail"], f["severity"]) for f in result}
        self.assertEqual(
            found,
            {
                ("NEXT_PUBLIC_OPENAI_API_KEY", "critical"),
                ("VITE_STRIPE_SECRET_KEY", "critical"),
                ("EXPO_PUBLIC_AUTH_TOKEN", "warning"),
            },
        )

    def test_public_prefixed_secret_in_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    "app.ts": (
                        "const key = process.env.NEXT_PUBLIC_ANTHROPIC_API_KEY;\n"
                        "const role = import.meta.env.VITE_SUPABASE_SERVICE_ROLE_KEY;\n"
                        "const ok = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;\n"
                        "const url = process.env.NEXT_PUBLIC_SUPABASE_URL;\n"
                    )
                },
            )
            result = findings_for(repo_path, "public-env-secret")

        found = {(f["detail"], f["severity"]) for f in result}
        self.assertEqual(
            found,
            {
                ("NEXT_PUBLIC_ANTHROPIC_API_KEY", "critical"),
                ("VITE_SUPABASE_SERVICE_ROLE_KEY", "critical"),
            },
        )

    def test_public_by_design_names_are_not_flagged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    ".env": (
                        "NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ\n"
                        "NEXT_PUBLIC_SUPABASE_URL=https://x.supabase.co\n"
                        "NEXT_PUBLIC_FIREBASE_API_KEY=AIza\n"
                        "NEXT_PUBLIC_APP_NAME=Demo\n"
                    )
                },
            )
            self.assertEqual(findings_for(repo_path, "public-env-secret"), [])

    def test_public_prefixed_provider_keys_are_critical(self):
        for name in ("NEXT_PUBLIC_OPENAI_API_KEY", "VITE_ANTHROPIC_API_KEY", "EXPO_PUBLIC_OPENAI_API_KEY"):
            with self.subTest(name=name):
                self.assertEqual(repodx.classify_public_prefixed_secret(name), "critical")

    def test_public_prefixed_secret_in_test_path_is_downgraded(self):
        code = (
            "const role = process.env.NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY;\n"
            "const token = process.env.NEXT_PUBLIC_AUTH_TOKEN;\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {"app.ts": code, "tests/app.test.ts": code, "examples/demo/.env": "VITE_OPENAI_API_KEY=x\n"},
            )
            result = findings_for(repo_path, "public-env-secret")

        found = {(f["path"], f["detail"], f["severity"]) for f in result}
        self.assertEqual(
            found,
            {
                ("app.ts", "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY", "critical"),
                ("app.ts", "NEXT_PUBLIC_AUTH_TOKEN", "warning"),
                ("tests/app.test.ts", "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY", "warning"),
                ("tests/app.test.ts", "NEXT_PUBLIC_AUTH_TOKEN", "info"),
                ("examples/demo/.env", "VITE_OPENAI_API_KEY", "warning"),
            },
        )
        test_titles = [f["title"] for f in result if f["path"] != "app.ts"]
        self.assertTrue(all(title.endswith(" in a test or example file") for title in test_titles))

    def test_public_env_check_skips_files_and_lines_without_a_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    "server.ts": "const key = process.env.OPENAI_API_KEY;\n",
                    "app.ts": (
                        "const a = process.env.SERVICE_ROLE_SECRET;\n"
                        "const b = process.env.NEXT_PUBLIC_API_SECRET;\n"
                    ),
                },
            )
            pattern = mock.Mock(wraps=repodx.PUBLIC_ENV_ACCESS_PATTERN)
            with mock.patch.object(repodx, "PUBLIC_ENV_ACCESS_PATTERN", pattern):
                result = repodx.check_public_env_secrets(repo_path, ["server.ts", "app.ts"])

        self.assertEqual(
            [(f["path"], f["line"], f["detail"]) for f in result],
            [("app.ts", 2, "NEXT_PUBLIC_API_SECRET")],
        )
        scanned = [call.args[0] for call in pattern.finditer.call_args_list]
        self.assertEqual(scanned, ["const b = process.env.NEXT_PUBLIC_API_SECRET;"])

    def test_classify_public_prefixed_secret_helpers(self):
        self.assertEqual(
            repodx.classify_public_prefixed_secret("NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY"),
            "critical",
        )
        self.assertEqual(
            repodx.classify_public_prefixed_secret("VITE_DATABASE_PASSWORD"),
            "warning",
        )
        self.assertIsNone(repodx.classify_public_prefixed_secret("OPENAI_API_KEY"))
        self.assertIsNone(repodx.classify_public_prefixed_secret("NEXT_PUBLIC_SITE_URL"))

    def test_supabase_rls_reports_only_unprotected_public_tables(self):
        sql = (
            "create table public.profiles (id uuid);\n"
            "create table if not exists notes (id int);\n"
            'ALTER TABLE "public"."notes" ENABLE ROW LEVEL SECURITY;\n'
            "create table private.audit (id int);\n"
            "-- create table commented_out (id int);\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"supabase/migrations/001.sql": sql})

            result = findings_for(repo_path, "supabase-rls")

        self.assertEqual([f["detail"] for f in result], ["profiles"])

    def test_firebase_rules_detect_public_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    "firestore.rules": "allow read, write: if true;\n// allow read: if true;\nallow read: if true;\n",
                    "database.rules.json": '{"rules": {".read": true, ".write": "auth != null"}}\n',
                    "storage.rules": "allow read: if request.auth != null;\nallow create: if true;\n",
                },
            )

            result = findings_for(repo_path, "firebase-rules")

        self.assertEqual(
            sorted((f["path"], f["line"], f["severity"]) for f in result),
            [
                ("database.rules.json", 1, "info"),
                ("firestore.rules", 1, "critical"),
                ("firestore.rules", 3, "info"),
                ("storage.rules", 2, "critical"),
            ],
        )

    def test_large_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            with open(repo_path / "model.bin", "wb") as handle:
                handle.truncate(repodx.LARGE_FILE_LIMIT_BYTES + 1)

            with open(repo_path / "video.mp4", "wb") as handle:
                handle.truncate(repodx.LARGE_FILE_WARNING_BYTES + 1)

            result = findings_for(repo_path, "large-file")

        self.assertEqual(
            sorted((f["path"], f["severity"]) for f in result),
            [("model.bin", "critical"), ("video.mp4", "warning")],
        )

    def test_build_output_folders_are_junk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {".next/cache.json": "{}", "dist/app.js": ""})

            self.assertEqual(repodx.find_junk_files(repo_path), [".next/", "dist/"])

    def test_license_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            missing = repodx.check_license(repo_path)
            (repo_path / "LICENSE.md").write_text("MIT", encoding="utf-8")

            self.assertEqual(len(missing), 1)
            self.assertEqual(repodx.check_license(repo_path), [])

    def test_long_agent_file_is_info(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"CLAUDE.md": "- rule\n" * 301, "AGENTS.md": "- rule\n"})

            result = findings_for(repo_path, "agent-file-size")

        self.assertEqual([(f["path"], f["detail"]) for f in result], [("CLAUDE.md", "301 lines")])


class ColorTests(unittest.TestCase):
    def setUp(self):
        self.stream = mock.Mock()
        self.stream.isatty.return_value = True
        self.stream.fileno.return_value = 1
        self.handle = 0x100000001
        self.mode = 0x0012
        self.kernel32 = mock.Mock()
        self.kernel32.GetConsoleMode.side_effect = self.get_console_mode
        self.kernel32.SetConsoleMode.side_effect = self.set_console_mode
        self.msvcrt = mock.Mock()
        self.msvcrt.get_osfhandle.return_value = self.handle
        self.load_library = mock.Mock(return_value=self.kernel32)

        for patcher in [
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch.object(repodx.os, "name", "nt"),
            mock.patch.dict("sys.modules", {"msvcrt": self.msvcrt}),
            mock.patch("ctypes.WinDLL", new=self.load_library, create=True),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def get_console_mode(self, handle, mode):
        ctypes.cast(mode, ctypes.POINTER(wintypes.DWORD))[0] = self.mode
        return 1

    def set_console_mode(self, handle, mode):
        self.mode = mode
        return 1

    def test_windows_tty_enables_vt_and_preserves_existing_flags(self):
        self.assertTrue(repodx.use_color(self.stream))
        # Keep wrapping/LVB flags and enable processed output plus VT processing.
        self.assertEqual(self.mode, 0x0017)
        self.kernel32.SetConsoleMode.assert_called_once_with(self.handle, 0x0017)

    def test_windows_tty_uses_the_supplied_stream_handle(self):
        self.assertTrue(repodx.use_color(self.stream))
        self.msvcrt.get_osfhandle.assert_called_once_with(1)
        self.assertEqual(self.kernel32.GetConsoleMode.call_args[0][0], self.handle)
        self.assertEqual(self.kernel32.GetConsoleMode.argtypes[0], wintypes.HANDLE)
        self.assertEqual(self.kernel32.SetConsoleMode.argtypes[0], wintypes.HANDLE)

    def test_non_windows_tty_does_not_load_windows_apis(self):
        with mock.patch.object(repodx.os, "name", "posix"):
            self.assertTrue(repodx.use_color(self.stream))
        self.load_library.assert_not_called()

    def test_redirected_output_does_not_enable_color(self):
        self.stream.isatty.return_value = False
        self.assertFalse(repodx.use_color(self.stream))
        self.load_library.assert_not_called()

    def test_no_color_disables_color_even_when_empty(self):
        for value in ["", "1"]:
            with self.subTest(value=value), mock.patch.dict(os.environ, {"NO_COLOR": value}):
                self.assertFalse(repodx.use_color(self.stream))
        self.load_library.assert_not_called()

    def test_failed_console_mode_read_disables_color(self):
        self.kernel32.GetConsoleMode.side_effect = None
        self.kernel32.GetConsoleMode.return_value = 0
        self.assertFalse(repodx.use_color(self.stream))
        self.kernel32.SetConsoleMode.assert_not_called()

    def test_failed_console_mode_write_disables_color(self):
        self.kernel32.SetConsoleMode.side_effect = None
        self.kernel32.SetConsoleMode.return_value = 0
        self.assertFalse(repodx.use_color(self.stream))

    def test_unavailable_file_descriptor_disables_color(self):
        for error in [AttributeError("no fileno"), io.UnsupportedOperation("fileno"), ValueError("closed")]:
            with self.subTest(error=error):
                self.stream.fileno.side_effect = error
                self.assertFalse(repodx.use_color(self.stream))
        self.kernel32.GetConsoleMode.assert_not_called()

    def test_invalid_os_handle_disables_color(self):
        self.msvcrt.get_osfhandle.side_effect = OSError("invalid descriptor")
        self.assertFalse(repodx.use_color(self.stream))
        self.kernel32.GetConsoleMode.assert_not_called()


class ReportTests(unittest.TestCase):
    def clean_repo(self, temp_dir):
        return make_repo(
            temp_dir,
            {
                ".gitignore": "__pycache__/\n.env\nnode_modules/\n",
                "LICENSE": "MIT",
                "README.md": "# App\n\n## Installation\n\n## Usage\n",
            },
        )

    def test_clean_repo_scores_100(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = repodx.build_report(self.clean_repo(temp_dir))

        self.assertEqual((report["score"], report["grade"], report["findings"]), (100, "A", []))

    def test_score_counts_each_kind_at_most_three_times(self):
        many = [{"id": "junk", "severity": "warning"}] * 10
        mixed = many + [{"id": "secret", "severity": "critical"}]

        self.assertEqual(repodx.score_findings(many), 100 - 3 * 8)
        self.assertEqual(repodx.score_findings(mixed), 100 - 3 * 8 - 25)

    def test_score_and_grade(self):
        self.assertEqual(repodx.grade_for_score(90), "A")
        self.assertEqual(repodx.grade_for_score(80), "B")
        self.assertEqual(repodx.grade_for_score(65), "C")
        self.assertEqual(repodx.grade_for_score(50), "D")
        self.assertEqual(repodx.grade_for_score(49), "F")

    def test_main_exit_codes_and_fail_on(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)

            with mock.patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(repodx.main([str(repo_path)]), 0)
                (repo_path / "debug.log").write_text("log", encoding="utf-8")
                self.assertEqual(repodx.main([str(repo_path)]), 1)
                self.assertEqual(repodx.main([str(repo_path), "--fail-on", "critical"]), 0)
                self.assertEqual(repodx.main([str(repo_path), "--fail-on", "never"]), 0)

            with mock.patch("sys.stderr", new=io.StringIO()):
                self.assertEqual(repodx.main([str(repo_path / "missing")]), 2)

    def test_quiet_output_is_one_line_and_keeps_exit_codes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                exit_code = repodx.main([str(repo_path), "--quiet"])

            line = output.getvalue().strip()
            self.assertEqual(exit_code, 0)
            self.assertEqual(line.count("\n"), 0)
            self.assertTrue(line.startswith("RepoDx: 100/100 (A), "))
            self.assertIn("critical", line)
            self.assertIn("warnings", line)
            self.assertIn("info", line)

            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            output = io.StringIO()
            with mock.patch("sys.stdout", new=output):
                self.assertEqual(repodx.main([str(repo_path), "--quiet"]), 1)
                self.assertEqual(repodx.main([str(repo_path), "--quiet", "--fail-on", "critical"]), 0)
            quiet_line = output.getvalue().strip().splitlines()[0]
            self.assertTrue(quiet_line.startswith("RepoDx: "))
            self.assertIn("warnings", quiet_line)

            report = repodx.build_report(Path("sample_repo"))
            expected = (
                f"RepoDx: {report['score']}/100 ({report['grade']}), "
                f"{report['counts']['critical']} critical, "
                f"{report['counts']['warning']} warnings, "
                f"{report['counts']['info']} info"
            )
            self.assertEqual(repodx.format_quiet(report), expected)

    def test_quiet_prints_only_score_line(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                code = repodx.main([str(repo_path), "--quiet"])

        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "RepoDx: 100/100 (A), 0 critical, 0 warnings, 0 info\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                code = repodx.main([str(repo_path), "--quiet", "--fail-on", "warning"])

        self.assertEqual(code, 1)
        line = output.getvalue().strip()
        self.assertTrue(line.startswith("RepoDx: "))
        self.assertIn("warnings", line)
        self.assertEqual(line.count("\n"), 0)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                repodx.main([str(repo_path), "--json"])

        data = json.loads(output.getvalue())
        self.assertEqual((data["score"], data["grade"], data["findings"]), (100, "A", []))

    def test_markdown_and_text_output_list_fixes(self):
        report = repodx.build_report(Path("sample_repo"))

        markdown = repodx.format_markdown(report)
        text = repodx.format_text(report)

        self.assertIn("## RepoDx: 0/100 (F)", markdown)
        self.assertIn("| critical | Environment file is not ignored | `.env` |", markdown)
        self.assertIn("[CRITICAL] Firebase rules allow public writes", text)
        self.assertIn("Fix: ", text)
        self.assertNotIn("\033[", text)

    def test_version_is_consistent_across_files(self):
        root = Path(__file__).resolve().parent.parent
        version = repodx.__version__
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn(f'version = "{version}"', pyproject)
        self.assertEqual(re.search(r"^## (\S+)", changelog, re.MULTILINE).group(1), version)
        for name in ("README.md", "docs/README.tr.md"):
            readme = (root / name).read_text(encoding="utf-8")
            with self.subTest(readme=name):
                self.assertEqual(set(re.findall(r"repodx@v([\d.]+)", readme)), {version})
                self.assertEqual(set(re.findall(r"rev: v([\d.]+)", readme)), {version})

    def test_badge(self):
        report = {"score": 94, "grade": "A"}

        self.assertEqual(
            repodx.badge_markdown(report),
            "[![repodx](https://img.shields.io/badge/repodx-A%2094%2F100-brightgreen)]"
            "(https://github.com/omerbek/repodx)",
        )


class FixTests(unittest.TestCase):
    def test_fix_updates_gitignore_and_creates_env_example_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    ".gitignore": "*.tmp",
                    ".env": "OPENAI_API_KEY=" + fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2") + "\nexport PORT=3000\n",
                    "package.json": "{}",
                    "node_modules/x.js": "",
                    "debug.log": "log",
                    "app.js": "const url = process.env.DATABASE_URL;\n",
                },
            )
            before = repodx.build_report(repo_path)

            changes, manual = repodx.apply_fixes(repo_path, before)
            after = repodx.build_report(repo_path)
            second_changes, _ = repodx.apply_fixes(repo_path, after)

            gitignore = (repo_path / ".gitignore").read_text(encoding="utf-8")
            example = (repo_path / ".env.example").read_text(encoding="utf-8")

        self.assertTrue(gitignore.startswith("*.tmp\n\n# Added by repodx --fix\n"))
        for line in [".env", ".env.*", "!.env.example", "node_modules/", "*.log"]:
            self.assertIn("\n" + line + "\n", gitignore)
        self.assertIn("OPENAI_API_KEY=\n", example)
        self.assertIn("PORT=\n", example)
        self.assertIn("DATABASE_URL=\n", example)
        self.assertNotIn("sk-proj", example)
        self.assertEqual(len(changes), 2)
        self.assertTrue(any("git rm -r --cached" in step for step in manual))
        self.assertGreater(after["score"], before["score"])
        self.assertEqual(second_changes, [])

    def test_fix_creates_missing_gitignore(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"main.py": "print('hi')\n"})

            changes, _ = repodx.apply_fixes(repo_path, repodx.build_report(repo_path))
            gitignore = (repo_path / ".gitignore").read_text(encoding="utf-8")

        self.assertEqual(changes, ["Created .gitignore: added __pycache__/, .env"])
        self.assertEqual(gitignore, "# Added by repodx --fix\n__pycache__/\n.env\n")

    def test_fix_leaves_unreadable_gitignore_alone(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_bytes(b"\xff\xfe\x00bad")
            (repo_path / "debug.log").write_text("log", encoding="utf-8")

            changes, manual = repodx.apply_fixes(repo_path, repodx.build_report(repo_path))

            self.assertEqual((repo_path / ".gitignore").read_bytes(), b"\xff\xfe\x00bad")
        self.assertEqual(changes, [])
        self.assertIn("Could not read .gitignore", manual[0])

    def test_fix_keeps_existing_env_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {".env": "A=1\n", ".env.sample": "A=\n"})

            repodx.apply_fixes(repo_path, repodx.build_report(repo_path))

            self.assertFalse((repo_path / ".env.example").exists())
            self.assertEqual((repo_path / ".env.sample").read_text(encoding="utf-8"), "A=\n")

    def test_main_fix_prints_summary_and_uses_rescan_exit_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {"LICENSE": "MIT", "README.md": "# App\n\n## Installation\n\n## Usage\n", "debug.log": "log"},
            )
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                exit_code = repodx.main([str(repo_path), "--fix"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Fixed: Created .gitignore", output.getvalue())
        self.assertIn("-> 100/100 (A)", output.getvalue())


class PromptTests(unittest.TestCase):
    def test_prompt_lists_findings_with_fixes_and_masks_secrets(self):
        key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"src/app.js": f"const k = '{key}';\n"})
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                repodx.main([str(repo_path), "--prompt"])

        prompt = output.getvalue()
        self.assertIn("[CRITICAL] OpenAI API key", prompt)
        self.assertIn("Where: src/app.js:1  (sk-pro...l2)", prompt)
        self.assertIn("How to fix: Delete the key", prompt)
        self.assertIn("run `repodx .`", prompt)
        self.assertNotIn(key, prompt)

    def test_prompt_without_findings(self):
        report = {"findings": [], "score": 100, "grade": "A"}

        self.assertEqual(repodx.format_prompt(report), "RepoDx found no problems in this project. Nothing to fix.")


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class StagedScanTests(unittest.TestCase):
    def git(self, repo_path, *args):
        return subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=repo_path,
            capture_output=True,
        )

    def init_repo(self, repo_path):
        self.assertEqual(self.git(repo_path, "init", "-q").returncode, 0)
        self.assertEqual(self.git(repo_path, "commit", "--allow-empty", "-qm", "initial").returncode, 0)

    def staged_report(self, repo_path):
        output = io.StringIO()
        with mock.patch("sys.stdout", new=output):
            exit_code = repodx.main(
                ["--staged", "--format", "json", "--fail-on", "never", str(repo_path)]
            )
        return exit_code, json.loads(output.getvalue())

    def test_scans_index_contents_and_handles_unusual_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            self.init_repo(repo_path)
            relative_path = "src/odd name\n.js"
            staged_path = repo_path / relative_path
            staged_path.parent.mkdir()
            token = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")
            staged_path.write_text(f"const token = '{token}';\n", encoding="utf-8")
            self.assertEqual(self.git(repo_path, "add", "--", relative_path).returncode, 0)

            # The index still contains the secret after the working copy is cleaned up.
            staged_path.write_text("const token = 'removed from the working tree';\n", encoding="utf-8")
            (repo_path / "unstaged.js").write_text(
                f"const token = '{token}';\n", encoding="utf-8"
            )

            exit_code, report = self.staged_report(repo_path)

        self.assertEqual(exit_code, 0)
        secret_findings = [finding for finding in report["findings"] if finding["id"] != "env-example"]
        self.assertEqual([finding["path"] for finding in secret_findings], [relative_path])
        self.assertNotIn("unstaged.js", {finding["path"] for finding in report["findings"]})
        self.assertNotIn(token, json.dumps(report))

    def test_staged_mode_skips_repository_wide_hygiene_checks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            self.init_repo(repo_path)
            source = repo_path / "src.js"
            source.write_text("const answer = 42;\n", encoding="utf-8")
            self.assertEqual(self.git(repo_path, "add", "src.js").returncode, 0)

            exit_code, report = self.staged_report(repo_path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["files_scanned"], 1)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["score"], 100)

    def test_staged_mode_runs_env_supabase_firebase_and_large_file_checks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            self.init_repo(repo_path)
            files = {
                ".env": "DATABASE_URL=postgres://user:placeholder@db.example.com/app\n",
                "supabase/migrations/001_init.sql": "create table public.profiles (id int);\n",
                "firestore.rules": "allow write: if true;\n",
                "large.bin": "1" * 201,
            }
            for relative_path, contents in files.items():
                path = repo_path / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(contents, encoding="utf-8")
                self.assertEqual(
                    self.git(repo_path, "add", "--", relative_path).returncode,
                    0,
                )

            with mock.patch.multiple(
                repodx,
                LARGE_FILE_WARNING_BYTES=100,
                LARGE_FILE_LIMIT_BYTES=150,
            ):
                exit_code, report = self.staged_report(repo_path)

        self.assertEqual(exit_code, 0)
        found_ids = {finding["id"] for finding in report["findings"]}
        self.assertTrue({"env-file", "supabase-rls", "firebase-rules", "large-file"} <= found_ids)

    def test_staged_mode_reports_non_repository_and_git_errors(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            with mock.patch("sys.stderr", new=output):
                exit_code = repodx.main(["--staged", temp_dir])
            self.assertEqual(exit_code, 2)
            self.assertIn("inside a Git repository", output.getvalue())

            output = io.StringIO()
            with mock.patch("sys.stderr", new=output), mock.patch.object(
                repodx.subprocess, "run", side_effect=FileNotFoundError
            ):
                exit_code = repodx.main(["--staged", temp_dir])
            self.assertEqual(exit_code, 2)
            self.assertIn("Git must be installed", output.getvalue())


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class InstallHookTests(unittest.TestCase):
    def git(self, repo_path, *args):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )

    def test_installs_hook_that_blocks_commits_with_critical_findings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            self.git(repo_path, "init", "-q")

            with mock.patch.object(repodx.shutil, "which", return_value=None), mock.patch(
                "sys.stdout", new=io.StringIO()
            ):
                self.assertEqual(repodx.main([str(repo_path), "--install-hook"]), 0)
                # Reinstalling over our own hook is fine.
                self.assertEqual(repodx.main([str(repo_path), "--install-hook"]), 0)

            hook_path = repo_path / ".git" / "hooks" / "pre-commit"
            self.assertIn(repodx.HOOK_MARKER, hook_path.read_text(encoding="utf-8"))
            self.assertIn("--staged", hook_path.read_text(encoding="utf-8"))
            self.assertTrue(os.access(hook_path, os.X_OK))

            (repo_path / "notes.txt").write_text("hello\n", encoding="utf-8")
            self.git(repo_path, "add", "notes.txt")
            self.assertEqual(self.git(repo_path, "commit", "-qm", "ok").returncode, 0)

            key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")
            (repo_path / "app.js").write_text(f"const k = '{key}';\n", encoding="utf-8")
            self.git(repo_path, "add", "app.js")
            (repo_path / "app.js").write_text("const k = 'removed from the working tree';\n", encoding="utf-8")
            blocked = self.git(repo_path, "commit", "-qm", "leak")

        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("commit blocked", blocked.stdout + blocked.stderr)

    def test_installed_hook_ignores_unstaged_secrets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            self.git(repo_path, "init", "-q")

            with mock.patch.object(repodx.shutil, "which", return_value=None), mock.patch(
                "sys.stdout", new=io.StringIO()
            ):
                self.assertEqual(repodx.main([str(repo_path), "--install-hook"]), 0)

            (repo_path / "notes.txt").write_text("safe staged change\n", encoding="utf-8")
            self.git(repo_path, "add", "notes.txt")
            token = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")
            (repo_path / "unstaged.js").write_text(f"const key = '{token}';\n", encoding="utf-8")
            committed = self.git(repo_path, "commit", "-qm", "safe staged change")

        self.assertEqual(committed.returncode, 0, committed.stdout + committed.stderr)

    def test_does_not_overwrite_a_foreign_hook(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            self.git(repo_path, "init", "-q")
            hook_path = repo_path / ".git" / "hooks" / "pre-commit"
            hook_path.parent.mkdir(parents=True, exist_ok=True)
            hook_path.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

            with mock.patch("sys.stdout", new=io.StringIO()):
                exit_code = repodx.main([str(repo_path), "--install-hook"])

            self.assertEqual(exit_code, 1)
            self.assertEqual(hook_path.read_text(encoding="utf-8"), "#!/bin/sh\necho mine\n")

    def test_outside_a_git_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(repodx, "git_hooks_dir", return_value=None), mock.patch(
                "sys.stderr", new=io.StringIO()
            ):
                self.assertEqual(repodx.main([temp_dir, "--install-hook"]), 2)


if __name__ == "__main__":
    unittest.main()

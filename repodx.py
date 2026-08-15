import argparse
from pathlib import Path
import re


COMMON_GITIGNORE_ENTRIES = ["__pycache__/", ".env", "node_modules/"]
JUNK_DIRECTORY_NAMES = ["__pycache__", "node_modules"]
README_INSTALLATION_HEADINGS = ["installation", "install", "kurulum"]
README_USAGE_HEADINGS = ["usage", "use", "kullanim", "kullanım"]


def read_gitignore_entries(repo_path):
    gitignore_path = repo_path / ".gitignore"

    if not gitignore_path.exists():
        return None, []

    entries = []

    try:
        gitignore_text = gitignore_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [], [f"Could not read .gitignore: {error}"]

    for line in gitignore_text.splitlines():
        clean_line = line.strip()

        if clean_line and not clean_line.startswith("#"):
            entries.append(clean_line)

    return entries, []


def normalize_gitignore_directory_entry(entry):
    normalized_entry = entry.removeprefix("**/").strip("/")

    if normalized_entry.endswith("/*"):
        normalized_entry = normalized_entry[:-2].strip("/")

    return normalized_entry


def has_gitignore_entry(entries, expected_entry):
    if entries is None:
        return False

    normalized_expected = normalize_gitignore_directory_entry(expected_entry)

    for entry in entries:
        normalized_entry = normalize_gitignore_directory_entry(entry)

        if normalized_entry == normalized_expected:
            return True

    return False


def find_junk_files(repo_path):
    entries, _ = read_gitignore_entries(repo_path)
    pycache_is_ignored = has_gitignore_entry(entries, "__pycache__/")
    node_modules_is_ignored = has_gitignore_entry(entries, "node_modules/")
    junk_items = []

    for path in repo_path.rglob("*"):
        relative_path = path.relative_to(repo_path)
        relative_text = relative_path.as_posix()

        if ".git" in relative_path.parts:
            continue

        if any(part in JUNK_DIRECTORY_NAMES for part in relative_path.parts[:-1]):
            continue

        if path.is_dir() and path.name == "__pycache__" and not pycache_is_ignored:
            junk_items.append(relative_text + "/")
            continue

        if path.is_dir() and path.name == "node_modules" and not node_modules_is_ignored:
            junk_items.append(relative_text + "/")
            continue

        if path.is_file() and path.name == ".DS_Store":
            junk_items.append(relative_text)
            continue

        if path.is_file() and path.suffix in [".tmp", ".log"]:
            junk_items.append(relative_text)

    return sorted(junk_items)


def check_gitignore(repo_path):
    entries, read_issues = read_gitignore_entries(repo_path)

    if entries is None:
        return ["Missing .gitignore file"]

    if read_issues:
        return read_issues

    missing_entries = []

    for expected_entry in COMMON_GITIGNORE_ENTRIES:
        if not has_gitignore_entry(entries, expected_entry):
            missing_entries.append(f"Missing .gitignore entry: {expected_entry}")

    return missing_entries


def markdown_headings(markdown_text):
    headings = []

    for line in markdown_text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)

        if match:
            headings.append(match.group(1).strip().lower())

    return headings


def has_any_heading(headings, expected_headings):
    for heading in headings:
        plain_heading = re.sub(r"[^\w\s]", "", heading)

        if plain_heading in expected_headings:
            return True

    return False


def check_readme(repo_path):
    readme_path = repo_path / "README.md"

    if not readme_path.exists():
        return ["Missing README.md file"]

    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [f"Could not read README.md: {error}"]

    headings = markdown_headings(readme_text)
    issues = []

    if not has_any_heading(headings, README_INSTALLATION_HEADINGS):
        issues.append("Missing README heading: Installation")

    if not has_any_heading(headings, README_USAGE_HEADINGS):
        issues.append("Missing README heading: Usage")

    return issues


def build_report(repo_path):
    junk_items = find_junk_files(repo_path)
    gitignore_issues = check_gitignore(repo_path)
    readme_issues = check_readme(repo_path)

    return {
        "junk_items": junk_items,
        "gitignore_issues": gitignore_issues,
        "readme_issues": readme_issues,
    }


def count_issues(report):
    return (
        len(report["junk_items"])
        + len(report["gitignore_issues"])
        + len(report["readme_issues"])
    )


def print_section(title, items):
    print()
    print(title)

    if not items:
        print("  OK")
        return

    for item in items:
        print(f"  - {item}")


def print_report(repo_path, report):
    total_issues = count_issues(report)

    print("RepoDx report")
    print(f"Scanned path: {repo_path}")
    print(f"Issues found: {total_issues}")

    print_section("Junk files", report["junk_items"])
    print_section(".gitignore", report["gitignore_issues"])
    print_section("README", report["readme_issues"])


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scan a repository for basic hygiene issues."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to scan. Defaults to the current folder.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    repo_path = Path(args.path).resolve()

    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Error: path is not a directory: {repo_path}")
        return 2

    report = build_report(repo_path)
    print_report(repo_path, report)

    if count_issues(report) > 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""RepoDx: check a project for leaked secrets and repo hygiene before you push it."""

import argparse
import base64
import fnmatch
import functools
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


__version__ = "0.4.0"

COMMON_GITIGNORE_ENTRIES = ["__pycache__/", ".env", "node_modules/"]
VIRTUAL_ENVIRONMENT_DIRECTORY_NAMES = [".venv", "venv", "env"]
BUILD_OUTPUT_DIRECTORY_NAMES = [".next", ".nuxt", ".svelte-kit", "dist", "coverage"]
JUNK_FILE_SUFFIXES = [".tmp", ".log"]
README_FILE_NAMES = ["readme.md", "readme.markdown", "readme.rst", "readme.txt", "readme"]
README_START_HEADINGS = [
    "quickstart", "quick start", "getting started", "get started", "running locally", "run locally",
    "local development", "baslarken", "başlarken", "hizli baslangic", "hızlı başlangıç",
]
README_INSTALLATION_HEADINGS = ["installation", "install", "installing", "setup", "set up", "kurulum"] + README_START_HEADINGS
README_USAGE_HEADINGS = ["usage", "use", "how to use", "example", "examples", "kullanim", "kullanım"] + README_START_HEADINGS


def read_gitignore_entries(repo_path, file_name=".gitignore"):
    gitignore_path = repo_path / file_name

    if not gitignore_path.exists():
        return None, []

    entries = []

    try:
        gitignore_text = gitignore_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [], [f"Could not read {file_name}: {error}"]

    for line in gitignore_text.splitlines():
        clean_line = line.strip()

        if clean_line and not clean_line.startswith("#"):
            entries.append(clean_line)

    return entries, []


def normalize_gitignore_directory_entry(entry):
    normalized_entry = entry.removeprefix("**/").strip("/")

    while normalized_entry.endswith("/**") or normalized_entry.endswith("/*"):
        if normalized_entry.endswith("/**"):
            normalized_entry = normalized_entry[:-3].strip("/")
        else:
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


@functools.lru_cache(maxsize=None)
def compile_ignore_entries(entries):
    """Turn gitignore lines into (negated, directory_only, file_rules, directory_rules) once."""
    rules = []

    for entry in entries:
        negated = entry.startswith("!")
        pattern = entry.removeprefix("!").removeprefix("**/").lstrip("/").lower()
        directory_only = pattern.endswith("/")
        pattern = pattern.rstrip("/")

        if not pattern:
            continue

        file_rules = [pattern]
        # "node_modules/*" and "node_modules/**" are read as ignoring the folder.
        directory_rules = [pattern, normalize_gitignore_directory_entry(pattern)]
        rules.append(
            (
                negated,
                directory_only,
                [("/" in rule, re.compile(fnmatch.translate(rule))) for rule in file_rules if rule],
                [("/" in rule, re.compile(fnmatch.translate(rule))) for rule in directory_rules if rule],
            )
        )

    return rules


def is_path_ignored(entries, relative_text, is_directory=False):
    if not entries:
        return False

    name = relative_text.rsplit("/", 1)[-1].lower()
    relative_text = relative_text.lower()
    ignored = False

    # Later entries win, so a "!pattern" can re-include an earlier match.
    for negated, directory_only, file_rules, directory_rules in compile_ignore_entries(tuple(entries)):
        if directory_only and not is_directory:
            continue

        rules = directory_rules if is_directory else file_rules

        if any(rule.match(relative_text if has_slash else name) for has_slash, rule in rules):
            ignored = not negated

    return ignored


def is_virtual_environment(path):
    return (path / "pyvenv.cfg").is_file()


def is_junk_directory(path):
    # JavaScript GitHub Actions must commit their dist/ folder.
    if path.name == "dist" and any((path.parent / name).is_file() for name in ["action.yml", "action.yaml"]):
        return False

    if path.name in ["__pycache__", "node_modules"] + BUILD_OUTPUT_DIRECTORY_NAMES:
        return True

    return path.name in VIRTUAL_ENVIRONMENT_DIRECTORY_NAMES and is_virtual_environment(path)


def scan_tree(repo_path):
    """Walk the repo once and return the junk items and the files Git would pick up."""
    entries, _ = read_gitignore_entries(repo_path)
    excluded_entries, _ = read_gitignore_entries(repo_path, ".repodxignore")
    junk_items = []
    files = []

    for current_dir, dir_names, file_names in os.walk(repo_path):
        current_path = Path(current_dir)
        kept_dir_names = []

        for dir_name in dir_names:
            dir_path = current_path / dir_name
            relative_text = dir_path.relative_to(repo_path).as_posix()

            if dir_name == ".git":
                continue

            if is_path_ignored(excluded_entries, relative_text, is_directory=True):
                continue

            is_ignored = is_path_ignored(entries, relative_text, is_directory=True)

            # Junk folders are reported once and never walked into.
            if is_junk_directory(dir_path):
                if not is_ignored:
                    junk_items.append(relative_text + "/")
                continue

            # Git cannot track anything inside an ignored folder.
            if is_ignored:
                continue

            kept_dir_names.append(dir_name)

        dir_names[:] = kept_dir_names

        for file_name in file_names:
            relative_text = (current_path / file_name).relative_to(repo_path).as_posix()

            if is_path_ignored(excluded_entries, relative_text):
                continue

            if is_path_ignored(entries, relative_text):
                continue

            files.append(relative_text)
            is_junk = (
                file_name == ".DS_Store"
                or os.path.splitext(file_name)[1].lower() in JUNK_FILE_SUFFIXES
            )

            if is_junk:
                junk_items.append(relative_text)

    return sorted(junk_items), sorted(files)


def find_junk_files(repo_path):
    return scan_tree(repo_path)[0]


def expected_gitignore_entries(files):
    """Pick the entries that matter for this project. Without a file list, expect all of them."""
    if files is None:
        return COMMON_GITIGNORE_ENTRIES

    names = {relative_text.rsplit("/", 1)[-1] for relative_text in files}
    expected = []

    if any(name.endswith(".py") for name in names):
        expected.append("__pycache__/")

    expected.append(".env")

    if "package.json" in names:
        expected.append("node_modules/")

    return expected


def check_gitignore(repo_path, files=None):
    entries, read_issues = read_gitignore_entries(repo_path)

    if entries is None:
        return ["Missing .gitignore file"]

    if read_issues:
        return read_issues

    missing_entries = []

    for expected_entry in expected_gitignore_entries(files):
        is_directory = expected_entry.endswith("/")

        if has_gitignore_entry(entries, expected_entry) or is_path_ignored(
            entries, expected_entry.rstrip("/"), is_directory
        ):
            continue

        missing_entries.append(f"Missing .gitignore entry: {expected_entry}")

    return missing_entries


def markdown_headings(markdown_text):
    headings = []
    inside_fenced_code_block = False
    previous_text_line = None

    for line in markdown_text.splitlines():
        stripped_line = line.strip()

        if stripped_line.startswith("```") or stripped_line.startswith("~~~"):
            inside_fenced_code_block = not inside_fenced_code_block
            previous_text_line = None
            continue

        if inside_fenced_code_block:
            continue

        if re.match(r"^\s{0,3}(=+|-+)\s*$", line) and previous_text_line:
            headings.append(previous_text_line.strip().lower())
            previous_text_line = None
            continue

        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?\s*$", line)

        if match:
            headings.append(match.group(1).strip().lower())
            previous_text_line = None
            continue

        previous_text_line = stripped_line or None

    return headings


def has_any_heading(headings, expected_headings):
    for heading in headings:
        plain_heading = re.sub(r"[^\w\s]", "", heading)

        if plain_heading in expected_headings:
            return True

    return False


def rst_headings(rst_text):
    headings = []
    previous_text_line = None

    for line in rst_text.splitlines():
        stripped_line = line.strip()

        if re.match(r"^([=\-~^\"'`*+#:.])\1+\s*$", line):
            if previous_text_line:
                headings.append(previous_text_line.lower())
            previous_text_line = None
            continue

        previous_text_line = stripped_line or None

    return headings


def find_readme(repo_path):
    names = {path.name.lower(): path for path in repo_path.iterdir() if path.is_file()}

    for readme_name in README_FILE_NAMES:
        if readme_name in names:
            return names[readme_name]

    return None


def check_readme(repo_path):
    readme_path = find_readme(repo_path)

    if readme_path is None:
        return ["Missing README file"]

    try:
        readme_text = readme_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        return [f"Could not read {readme_path.name}: {error}"]

    if readme_path.suffix.lower() == ".rst":
        headings = rst_headings(readme_text)
    else:
        headings = markdown_headings(readme_text)

    issues = []

    if not has_any_heading(headings, README_INSTALLATION_HEADINGS):
        issues.append("Missing README heading: Installation")

    if not has_any_heading(headings, README_USAGE_HEADINGS):
        issues.append("Missing README heading: Usage")

    return issues


SEVERITIES = ["critical", "warning", "info"]
SEVERITY_PENALTIES = {"critical": 25, "warning": 8, "info": 2}
SCORE_MAX_REPEATS = 3
LARGE_FILE_WARNING_BYTES = 50 * 1024 * 1024
LARGE_FILE_LIMIT_BYTES = 100 * 1024 * 1024
MAX_SCANNED_FILE_BYTES = 2 * 1024 * 1024
AGENT_FILE_NAMES = ["agents.md", "claude.md"]
AGENT_FILE_MAX_LINES = 300
LICENSE_FILE_NAMES = ["license", "license.md", "license.txt", "copying", "unlicense"]
INLINE_IGNORE_MARKER = "repodx:ignore"

# (name, regex). Only patterns with a distinctive prefix, to keep false alarms rare.
SECRET_PATTERNS = [
    ("Anthropic API key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key", r"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{20,}"),
    ("OpenAI API key", r"\bsk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}\b"),
    ("AWS access key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("GitHub token", r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"),
    ("Stripe secret key", r"\b(?:sk|rk)_live_[A-Za-z0-9]{20,}\b"),
    ("Supabase secret key", r"\bsb_secret_[A-Za-z0-9_\-]{20,}"),
    ("Slack token", r"\bxox[abposr]-[A-Za-z0-9\-]{10,}"),
    ("Hugging Face token", r"\bhf_[A-Za-z0-9]{34,}\b"),
    ("Groq API key", r"\bgsk_[A-Za-z0-9]{48,}\b"),
    ("SendGrid API key", r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b"),
    ("Telegram bot token", r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b"),
]
PRIVATE_KEY_PATTERN = r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"
PRIVATE_KEY_MIN_BODY_CHARS = 64
GOOGLE_API_KEY_PATTERN = r"\bAIza[0-9A-Za-z_\-]{35}\b"
JWT_PATTERN = r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
DATABASE_URL_PATTERN = (
    r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|rediss|amqps?)://"
    r"([^\s:/@'\"`]+):([^\s@/'\"`]+)@([^\s/:'\"`?]+)"
)
ENV_USAGE_PATTERN = r"process\.env\.|import\.meta\.env\.|os\.environ|os\.getenv\(|Deno\.env\.get"  # repodx:ignore
LOCAL_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "db", "postgres", "mysql", "redis", "mongo"]
PLACEHOLDER_PASSWORDS = ["password", "passwd", "pass", "secret", "changeme", "admin", "root", "test", "postgres"]
FAKE_VALUE_MARKERS = [
    "example", "xxxx", "your", "dummy", "fake", "placeholder", "sample", "abcdefgh", "12345678",
    "<", "[", "*", "{{", "${", "...",
]
PASSWORD_PLACEHOLDER_MARKERS = ["$", "%", "..", "password"]
TEMPLATE_HOST_MARKERS = ["{", "<", "[", "$"]
PUBLIC_ENV_PREFIXES = ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "PUBLIC_", "EXPO_PUBLIC_", "NUXT_PUBLIC_", "GATSBY_")
TEST_DIRECTORY_NAMES = [
    "test", "tests", "__tests__", "spec", "specs", "fixtures", "__fixtures__", "testdata", "__mocks__", "mocks",
    "example", "examples", "demo", "demos", "samples",
]
TEST_FILE_PATTERN = r"(^test_.*\.py$|_test\.(py|go)$|\.(test|spec)\.[cm]?[jt]sx?$)"

COMPILED_SECRET_PATTERNS = [(name, re.compile(pattern)) for name, pattern in SECRET_PATTERNS]
# Every pattern above contains one of these strings, so lines without them are skipped quickly.
CANDIDATE_LITERALS = [
    "sk-", "AKIA", "ASIA", "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "_live_", "sb_secret_",
    "xox", "hf_", "gsk_", "SG.", ":AA", "AIza", "eyJ", "://",
]


def has_candidate(text):
    return any(literal in text for literal in CANDIDATE_LITERALS)

FIXES = {
    "secret": (
        "Delete the key from the file, then revoke/rotate it in the provider dashboard "
        "(assume it is already stolen if it was ever pushed). Load it from an environment "
        "variable or a secret manager instead, and keep the real value in an ignored .env file."
    ),
    "google-api-key": (
        "Firebase web config keys are public by design and are fine if your Security Rules are strict. "
        "Any other Google key (Gemini, Maps, Cloud) must not be in the repo: rotate it and restrict it "
        "to your app in Google Cloud Console."
    ),
    "database-url": (
        "Move the connection string into an ignored .env file and change the database password: "
        "anyone who can read the repo can log in to your database."
    ),
    "supabase-service-role": (
        "The service_role key bypasses Row Level Security. Never ship it to a browser or commit it: "
        "rotate it in Supabase (Settings > API) and use it only in server code via an environment variable."
    ),
    "supabase-rls": (
        "Add `alter table <name> enable row level security;` and write policies for each table. "
        "Without RLS, anyone with your public anon key can read and change every row."
    ),
    "firebase-rules": (
        "Make sure public access is intended. For private data, replace `if true` / `true` with rules that check `request.auth` (for example "
        "`allow read, write: if request.auth != null && request.auth.uid == userId;`)."
    ),
    "env-file": (
        "Add `.env*` and `!.env.example` to .gitignore, run `git rm --cached <file>`, and rotate any "
        "secret it contained. Commit a `.env.example` with empty values instead."
    ),
    "large-file": (
        "GitHub rejects files over 100 MB and warns over 50 MB. Remove it from the repo, "
        "host it elsewhere, or track it with Git LFS."
    ),
    "junk": (
        "Add it to .gitignore and remove it from Git with `git rm -r --cached <path>`. "
        "Dependencies, caches and build output can always be recreated."
    ),
    "gitignore": "Add the missing entries to .gitignore (see github.com/github/gitignore for templates).",
    "readme": "Add a README.md that says what the project does, how to install it and how to use it.",
    "readme-section": "Add `## Installation` and `## Usage` sections so a stranger can run your project in minutes.",
    "license": (
        "Add a LICENSE file (choosealicense.com). Without one, nobody may legally use or copy your code, "
        "even if the repo is public."
    ),
    "env-example": (
        "Your code reads environment variables, but there is no .env.example. Add one listing every "
        "variable name with an empty or fake value, so others (and AI agents) know what to set."
    ),
    "agent-file-size": (
        "Keep AGENTS.md / CLAUDE.md short (under ~300 lines) and concrete: setup, test command, conventions. "
        "Long instruction files get ignored by coding agents."
    ),
}


def make_finding(check_id, severity, title, path=None, line=None, detail=None):
    return {
        "id": check_id,
        "severity": severity,
        "title": title,
        "path": path,
        "line": line,
        "detail": detail,
        "fix": FIXES[check_id],
    }


def mask_secret(value):
    if len(value) <= 8:
        return "*" * len(value)

    return value[:6] + "..." + value[-2:]


def read_text_file(path):
    try:
        if path.stat().st_size > MAX_SCANNED_FILE_BYTES:
            return None

        data = path.read_bytes()
    except OSError:
        return None

    if b"\0" in data[:4096]:
        return None

    return data.decode("utf-8", errors="replace")


def decode_jwt_payload(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, IndexError):
        return None


def looks_fake(value):
    """Documentation and test values: example markers, long repeated characters, obvious sequences."""
    lowered = value.lower()

    if any(marker in lowered for marker in FAKE_VALUE_MARKERS):
        return True

    if re.search(r"(.)\1{5,}", value):
        return True

    # Values such as 111222333aaabbbccc.
    return len(re.findall(r"(.)\1\1", value)) >= 3


def is_placeholder_password(value):
    lowered = value.lower()

    if lowered in PLACEHOLDER_PASSWORDS or looks_fake(value):
        return True

    return any(marker in value for marker in PASSWORD_PLACEHOLDER_MARKERS)


def is_test_path(relative_text):
    parts = relative_text.lower().split("/")

    if any(part in TEST_DIRECTORY_NAMES for part in parts[:-1]):
        return True

    return re.search(TEST_FILE_PATTERN, parts[-1]) is not None


def scan_line_for_secrets(line):
    """Return (check_id, severity, title, secret_text) tuples found in one line."""
    hits = []

    for name, pattern in COMPILED_SECRET_PATTERNS:
        for match in pattern.finditer(line):
            if not looks_fake(match.group(0)):
                hits.append(("secret", "critical", name, match.group(0)))

    for match in re.finditer(GOOGLE_API_KEY_PATTERN, line):
        if not looks_fake(match.group(0)):
            hits.append(("google-api-key", "warning", "Google API key", match.group(0)))

    for match in re.finditer(JWT_PATTERN, line):
        payload = decode_jwt_payload(match.group(0))

        # "supabase-demo" keys are the public defaults of the local Supabase CLI.
        if (
            isinstance(payload, dict)
            and payload.get("role") == "service_role"
            and payload.get("iss") != "supabase-demo"
        ):
            hits.append(("supabase-service-role", "critical", "Supabase service_role key", match.group(0)))

    for match in re.finditer(DATABASE_URL_PATTERN, line):
        user, password, host = match.groups()

        if host.lower() in LOCAL_HOSTS or is_placeholder_password(password):
            continue

        if any(marker in host + user for marker in TEMPLATE_HOST_MARKERS):
            continue

        hits.append(("database-url", "critical", "Database URL with password", password))

    return hits


def find_private_keys(text):
    """Yield line numbers of private key headers followed by a real key body, not a `...` template."""
    for match in re.finditer(PRIVATE_KEY_PATTERN, text):
        following = text[match.end():match.end() + 400]
        body = re.match(r"(?:\\n|\\r|[\s\"'>*]|[A-Za-z0-9+/=])*", following).group(0)
        body = re.sub(r"\\[nr]", "", body)

        if len(re.findall(r"[A-Za-z0-9+/=]", body)) >= PRIVATE_KEY_MIN_BODY_CHARS:
            yield text.count("\n", 0, match.start()) + 1


def secret_severity_and_title(relative_text, severity, title):
    if severity == "critical" and is_test_path(relative_text):
        return "warning", f"{title} in a test or example file"

    return severity, title


def check_file_contents(repo_path, files):
    findings = []
    uses_env_variables = False

    for relative_text in files:
        text = read_text_file(repo_path / relative_text)

        if text is None:
            continue

        lines = text.splitlines()
        hits = []

        if "PRIVATE KEY-----" in text:
            for line_number in find_private_keys(text):
                hits.append((line_number, "secret", "critical", "Private key", lines[line_number - 1].strip()))

        needs_env_scan = not uses_env_variables and re.search(ENV_USAGE_PATTERN, text)

        if has_candidate(text) or needs_env_scan:
            for line_number, line in enumerate(lines, start=1):
                if INLINE_IGNORE_MARKER in line:
                    continue

                if not uses_env_variables and re.search(ENV_USAGE_PATTERN, line):
                    uses_env_variables = True

                if has_candidate(line):
                    for check_id, severity, title, secret_text in scan_line_for_secrets(line):
                        hits.append((line_number, check_id, severity, title, secret_text))

        for line_number, check_id, severity, title, secret_text in hits:
            if INLINE_IGNORE_MARKER in lines[line_number - 1]:
                continue

            severity, title = secret_severity_and_title(relative_text, severity, title)
            findings.append(
                make_finding(check_id, severity, title, relative_text, line_number, mask_secret(secret_text))
            )

    names = {relative_text.rsplit("/", 1)[-1].lower() for relative_text in files}

    if uses_env_variables and not any(is_env_example_name(name) for name in names):
        findings.append(make_finding("env-example", "info", "No .env.example file"))

    return findings


def is_env_example_name(name):
    return name.startswith(".env") and any(word in name for word in ["example", "sample", "template", "dist"])


def has_only_public_variables(path):
    """True when every variable uses a prefix that frameworks expose to the browser anyway."""
    text = read_text_file(path) or ""
    names = re.findall(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", text, flags=re.MULTILINE)
    return bool(names) and all(name.startswith(PUBLIC_ENV_PREFIXES) for name in names)


def check_env_files(repo_path, files):
    findings = []

    for relative_text in files:
        name = relative_text.rsplit("/", 1)[-1].lower()

        if not re.fullmatch(r"\.env(\..+)?", name) or is_env_example_name(name):
            continue

        # Frameworks such as Next.js commit .env.development/.env.production on purpose.
        if (
            (name == ".env" or name.endswith(".local"))
            and not is_test_path(relative_text)
            and not has_only_public_variables(repo_path / relative_text)
        ):
            findings.append(
                make_finding("env-file", "critical", "Environment file is not ignored", relative_text)
            )
        else:
            findings.append(
                make_finding("env-file", "warning", "Environment file will be committed", relative_text)
            )

    return findings


def check_large_files(repo_path, files):
    findings = []

    for relative_text in files:
        try:
            size = (repo_path / relative_text).stat().st_size
        except OSError:
            continue

        size_text = f"{size / (1024 * 1024):.0f} MB"

        if size > LARGE_FILE_LIMIT_BYTES:
            findings.append(
                make_finding("large-file", "critical", "File too large for GitHub", relative_text, detail=size_text)
            )
        elif size > LARGE_FILE_WARNING_BYTES:
            findings.append(
                make_finding("large-file", "warning", "Large file", relative_text, detail=size_text)
            )

    return findings


def strip_sql_comments(sql_text):
    sql_text = re.sub(r"/\*.*?\*/", " ", sql_text, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql_text)


def sql_table_name(raw_name):
    parts = [part.strip('"').lower() for part in raw_name.split(".")]

    if len(parts) == 2 and parts[0] != "public":
        return None

    return parts[-1]


def check_supabase_rls(repo_path, files):
    created_tables = {}
    protected_tables = set()

    for relative_text in files:
        if not relative_text.lower().endswith(".sql") or "supabase/" not in relative_text.lower():
            continue

        text = read_text_file(repo_path / relative_text)

        if text is None:
            continue

        text = strip_sql_comments(text)

        for match in re.finditer(
            r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\".]+)", text, flags=re.IGNORECASE
        ):
            table_name = sql_table_name(match.group(1))

            if table_name:
                created_tables.setdefault(table_name, relative_text)

        for match in re.finditer(
            r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([\w\".]+)\s+enable\s+row\s+level\s+security",
            text,
            flags=re.IGNORECASE,
        ):
            table_name = sql_table_name(match.group(1))

            if table_name:
                protected_tables.add(table_name)

    return [
        make_finding("supabase-rls", "warning", "Supabase table without Row Level Security", path, detail=table)
        for table, path in sorted(created_tables.items())
        if table not in protected_tables
    ]


def public_firebase_access(code):
    """Return "write", "read" or None for one line of Firebase rules."""
    for match in re.finditer(r"\ballow\s+([\w\s,]+?)\s*:\s*if\s+true\s*;", code):
        operations = re.split(r"[\s,]+", match.group(1).strip())

        if set(operations) & {"write", "create", "update", "delete"}:
            return "write"

        return "read"

    if re.search(r"\"\.write\"\s*:\s*(true|\"true\")", code):
        return "write"

    if re.search(r"\"\.read\"\s*:\s*(true|\"true\")", code):
        return "read"

    return None


def check_firebase_rules(repo_path, files):
    findings = []

    for relative_text in files:
        name = relative_text.rsplit("/", 1)[-1].lower()

        if name not in ["firestore.rules", "storage.rules", "database.rules.json"]:
            continue

        text = read_text_file(repo_path / relative_text) or ""

        for line_number, line in enumerate(text.splitlines(), start=1):
            access = public_firebase_access(line.split("//", 1)[0])

            if access == "write":
                findings.append(
                    make_finding(
                        "firebase-rules", "critical", "Firebase rules allow public writes", relative_text, line_number
                    )
                )
            elif access == "read":
                findings.append(
                    make_finding(
                        "firebase-rules", "info", "Firebase rules allow public reads", relative_text, line_number
                    )
                )

    return findings


def check_license(repo_path):
    names = {path.name.lower() for path in repo_path.iterdir() if path.is_file()}

    if names.intersection(LICENSE_FILE_NAMES):
        return []

    return [make_finding("license", "warning", "No LICENSE file")]


def check_agent_files(repo_path, files):
    findings = []

    for relative_text in files:
        if relative_text.lower() not in AGENT_FILE_NAMES:
            continue

        text = read_text_file(repo_path / relative_text) or ""
        line_count = len(text.splitlines())

        if line_count > AGENT_FILE_MAX_LINES:
            findings.append(
                make_finding(
                    "agent-file-size", "info", "Agent instruction file is long", relative_text, detail=f"{line_count} lines"
                )
            )

    return findings


def hygiene_findings(repo_path, junk_items, files):
    findings = [make_finding("junk", "warning", "Junk committed to the repo", item) for item in junk_items]

    for issue in check_gitignore(repo_path, files):
        prefix = "Missing .gitignore entry: "

        if issue.startswith(prefix):
            findings.append(
                make_finding("gitignore", "warning", "Missing .gitignore entries", detail=issue.removeprefix(prefix))
            )
        else:
            findings.append(make_finding("gitignore", "warning", issue))

    for issue in check_readme(repo_path):
        prefix = "Missing README heading: "

        if issue.startswith(prefix):
            findings.append(
                make_finding("readme-section", "info", "Missing README sections", detail=issue.removeprefix(prefix))
            )
        else:
            findings.append(make_finding("readme", "warning", issue))

    return findings


def build_report(repo_path):
    junk_items, files = scan_tree(repo_path)
    findings = []
    findings += check_file_contents(repo_path, files)
    findings += check_env_files(repo_path, files)
    findings += check_supabase_rls(repo_path, files)
    findings += check_firebase_rules(repo_path, files)
    findings += check_large_files(repo_path, files)
    findings += hygiene_findings(repo_path, junk_items, files)
    findings += check_license(repo_path)
    findings += check_agent_files(repo_path, files)

    findings.sort(key=lambda finding: SEVERITIES.index(finding["severity"]))
    counts = {severity: 0 for severity in SEVERITIES}

    for finding in findings:
        counts[finding["severity"]] += 1

    score = score_findings(findings)

    return {
        "path": str(repo_path),
        "version": __version__,
        "score": score,
        "grade": grade_for_score(score),
        "counts": counts,
        "files_scanned": len(files),
        "findings": findings,
    }


def score_findings(findings):
    """Start at 100 and subtract per finding, counting each kind of problem at most three times."""
    per_kind = {}

    for finding in findings:
        key = (finding["id"], finding["severity"])
        per_kind[key] = per_kind.get(key, 0) + 1

    penalty = sum(
        SEVERITY_PENALTIES[severity] * min(count, SCORE_MAX_REPEATS) for (_check_id, severity), count in per_kind.items()
    )
    return max(0, 100 - penalty)


def grade_for_score(score):
    for grade, minimum in [("A", 90), ("B", 80), ("C", 65), ("D", 50)]:
        if score >= minimum:
            return grade

    return "F"


def count_issues(report):
    return len(report["findings"])


def group_findings(findings):
    """Group findings that share a check and title, keeping severity order."""
    groups = {}

    for finding in findings:
        key = (finding["severity"], finding["id"], finding["title"])
        groups.setdefault(key, []).append(finding)

    return groups


def finding_location(finding):
    if not finding["path"]:
        return finding["detail"] or ""

    location = finding["path"]

    if finding["line"]:
        location += f":{finding['line']}"

    if finding["detail"]:
        location += f"  ({finding['detail']})"

    return location


def use_color(stream):
    return stream.isatty() and "NO_COLOR" not in os.environ  # repodx:ignore


def paint(text, color_code, enabled):
    return f"\033[{color_code}m{text}\033[0m" if enabled else text


def format_text(report, color=False):
    counts = report["counts"]
    grade_colors = {"A": "32", "B": "32", "C": "33", "D": "33", "F": "31"}
    severity_colors = {"critical": "31", "warning": "33", "info": "36"}
    lines = [
        "RepoDx report",
        f"Scanned path: {report['path']} ({report['files_scanned']} files)",
        "Score: "
        + paint(f"{report['score']}/100 ({report['grade']})", "1;" + grade_colors[report["grade"]], color),
        f"Found: {counts['critical']} critical, {counts['warning']} warnings, {counts['info']} info",
    ]

    if not report["findings"]:
        lines += ["", paint("No issues found. Safe to push.", "32", color)]
        return "\n".join(lines)

    for (severity, _check_id, title), group in group_findings(report["findings"]).items():
        lines.append("")
        lines.append(paint(f"[{severity.upper()}] {title}", "1;" + severity_colors[severity], color))

        for finding in group:
            location = finding_location(finding)

            if location:
                lines.append(f"  - {location}")

        lines.append(f"  Fix: {group[0]['fix']}")

    return "\n".join(lines)


def format_quiet(report):
    counts = report["counts"]
    return (
        f"RepoDx: {report['score']}/100 ({report['grade']}), "
        f"{counts['critical']} critical, {counts['warning']} warnings, {counts['info']} info"
    )


def format_markdown(report):
    counts = report["counts"]
    lines = [
        f"## RepoDx: {report['score']}/100 ({report['grade']})",
        "",
        f"{counts['critical']} critical, {counts['warning']} warnings, {counts['info']} info "
        f"in {report['files_scanned']} files.",
    ]

    if not report["findings"]:
        return "\n".join(lines + ["", "No issues found."])

    lines += ["", "| Severity | Issue | Where |", "| --- | --- | --- |"]

    for finding in report["findings"]:
        where = finding_location(finding).replace("|", "\\|")
        where_cell = f"`{where}`" if where else ""
        lines.append(f"| {finding['severity']} | {finding['title']} | {where_cell} |")

    lines += ["", "### How to fix", ""]

    for (_severity, _check_id, title), group in group_findings(report["findings"]).items():
        lines.append(f"- **{title}**: {group[0]['fix']}")

    return "\n".join(lines)


def badge_markdown(report):
    colors = {"A": "brightgreen", "B": "green", "C": "yellow", "D": "orange", "F": "red"}
    message = f"{report['grade']} {report['score']}/100".replace(" ", "%20").replace("/", "%2F")
    url = f"https://img.shields.io/badge/repodx-{message}-{colors[report['grade']]}"
    return f"[![repodx]({url})](https://github.com/omerbek/repodx)"


def should_fail(report, fail_on):
    if fail_on == "never":
        return False

    failing = SEVERITIES[: SEVERITIES.index(fail_on) + 1]
    return any(report["counts"][severity] for severity in failing)


FIX_GITIGNORE_HEADER = "# Added by repodx --fix"
ENV_GITIGNORE_LINES = [".env", ".env.*", "!.env.example"]
ENV_NAME_PATTERN = (
    r"(?:process\.env\.|import\.meta\.env\.|Deno\.env\.get\(\s*['\"]|os\.getenv\(\s*['\"]"
    r"|os\.environ\.get\(\s*['\"]|os\.environ\[\s*['\"])([A-Z][A-Z0-9_]*)"
)  # repodx:ignore
ENV_ASSIGNMENT_PATTERN = r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*="
HOOK_MARKER = "# installed by repodx"


def is_already_ignored(entries, line):
    """Check a .gitignore line against the current entries using a sample path it would cover."""
    if line in entries:
        return True

    if line.startswith("!"):
        return False

    if line.startswith("*."):
        return is_path_ignored(entries, "example" + line[1:])

    if line.endswith("/"):
        return has_gitignore_entry(entries, line) or is_path_ignored(entries, line.rstrip("/"), True)

    return has_gitignore_entry(entries, line) or is_path_ignored(entries, line)


def gitignore_line_for_junk(path):
    name = path.rstrip("/").rsplit("/", 1)[-1]

    if path.endswith("/"):
        return name + "/"

    if name == ".DS_Store":
        return name

    return "*" + os.path.splitext(name)[1].lower()


def gitignore_lines_to_add(repo_path, report, files):
    entries, _ = read_gitignore_entries(repo_path)
    wanted = []

    if entries is None:
        wanted += expected_gitignore_entries(files)

    for finding in report["findings"]:
        if finding["id"] == "gitignore" and finding["detail"]:
            wanted.append(finding["detail"])
        elif finding["id"] == "junk":
            wanted.append(gitignore_line_for_junk(finding["path"]))
        elif finding["id"] == "env-file" and finding["severity"] == "critical":
            wanted += ENV_GITIGNORE_LINES

    lines = []

    for line in wanted:
        if line not in lines and not is_already_ignored(entries or [], line):
            lines.append(line)

    # Only re-include the example file when the lines above would ignore it.
    if lines == ["!.env.example"]:
        return []

    return lines


def env_variable_names(repo_path, files):
    names = []

    for relative_text in files:
        name = relative_text.rsplit("/", 1)[-1].lower()
        text = read_text_file(repo_path / relative_text) or ""

        if "/" not in relative_text and re.fullmatch(r"\.env(\..+)?", name) and not is_env_example_name(name):
            found = re.findall(ENV_ASSIGNMENT_PATTERN, text, flags=re.MULTILINE)
        elif re.search(ENV_USAGE_PATTERN, text):
            found = re.findall(ENV_NAME_PATTERN, text)
        else:
            found = []

        for variable in found:
            if variable not in names:
                names.append(variable)

    return names


def all_env_files(repo_path):
    """Top-level .env files, including ignored ones, which scan_tree leaves out."""
    return sorted(
        path.name
        for path in repo_path.iterdir()
        if path.is_file() and re.fullmatch(r"\.env(\..+)?", path.name.lower()) and not is_env_example_name(path.name.lower())
    )


def apply_fixes(repo_path, report):
    """Apply safe, repeatable fixes. Returns (changes made, steps left for the user)."""
    _junk_items, files = scan_tree(repo_path)
    changes = []
    manual = []

    lines = gitignore_lines_to_add(repo_path, report, files)
    gitignore_path = repo_path / ".gitignore"

    try:
        existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    except (UnicodeDecodeError, OSError):
        manual.append("Could not read .gitignore, so it was not changed. Save it as UTF-8 and run --fix again.")
        lines = []

    if lines:
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        prefix += "\n" if existing else ""
        gitignore_path.write_text(
            existing + prefix + FIX_GITIGNORE_HEADER + "\n" + "\n".join(lines) + "\n", encoding="utf-8"
        )
        action = "Updated" if existing else "Created"
        changes.append(f"{action} .gitignore: added {', '.join(lines)}")

    wants_example = any(finding["id"] in ["env-file", "env-example"] for finding in report["findings"])
    has_example = any(is_env_example_name(path.name.lower()) for path in repo_path.iterdir() if path.is_file())

    if wants_example and not has_example:
        names = env_variable_names(repo_path, files + [name for name in all_env_files(repo_path) if name not in files])

        if names:
            text = "# Copy this file to .env and fill in the values. Created by repodx --fix.\n"
            text += "".join(f"{name}=\n" for name in names)
            (repo_path / ".env.example").write_text(text, encoding="utf-8")
            changes.append(f"Created .env.example with {len(names)} variable name(s) and empty values")

    tracked = [f["path"] for f in report["findings"] if f["id"] in ["junk", "env-file"] and f["severity"] != "info"]

    if tracked:
        paths = " ".join(f'"{path.rstrip("/")}"' for path in tracked)
        manual.append(f"If Git already tracks them, stop tracking (files stay on disk): git rm -r --cached {paths}")

    leaked = [f for f in report["findings"] if f["id"] in ["secret", "supabase-service-role", "database-url"]]

    if leaked:
        manual.append(
            f"Rotate the {len(leaked)} leaked secret(s) in each provider's dashboard, then move them to .env. "
            "Run `repodx --prompt` to get instructions for your AI coding tool."
        )

    return changes, manual


def format_fix_summary(fixes, report):
    lines = ["RepoDx --fix"]

    if fixes["changes"]:
        lines += [f"  Fixed: {change}" for change in fixes["changes"]]
    else:
        lines.append("  Nothing to fix automatically.")

    lines += [f"  Do this yourself: {step}" for step in fixes["manual"]]
    lines.append(f"  Score: {fixes['score_before']} -> {report['score']}/100 ({report['grade']})")
    return "\n".join(lines)


def format_prompt(report):
    if not report["findings"]:
        return "RepoDx found no problems in this project. Nothing to fix."

    lines = [
        f"You are fixing security and repo hygiene problems that RepoDx found in this project "
        f"(score {report['score']}/100, grade {report['grade']}).",
        "",
        "Problems:",
    ]

    for number, ((severity, _check_id, title), group) in enumerate(group_findings(report["findings"]).items(), 1):
        lines.append(f"{number}. [{severity.upper()}] {title}")
        locations = [finding_location(finding) for finding in group if finding_location(finding)]

        if locations:
            lines.append(f"   Where: {'; '.join(locations)}")

        lines.append(f"   How to fix: {group[0]['fix']}")

    lines += [
        "",
        "Rules:",
        "- Never print, log or commit secret values. They are masked above; open the files only to move them.",
        "- Move secrets into environment variables, read them in code, and list the variable names with empty "
        "values in .env.example.",
        "- Keep .env files out of Git with .gitignore. Don't delete or rewrite unrelated code.",
        "- Ask me before running `git rm --cached`, deleting files or rewriting Git history.",
        "- Remind me to rotate every leaked key in the provider dashboard. Removing it from the code is not enough.",
        "- When you're done, run `repodx .` and show me the new score.",
    ]
    return "\n".join(lines)


def git_hooks_dir(repo_path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "hooks"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    hooks_path = Path(result.stdout.strip())
    return hooks_path if hooks_path.is_absolute() else repo_path / hooks_path


def hook_command():
    if shutil.which("repodx"):
        return "repodx"

    # Running from a downloaded repodx.py: call this exact file with this Python.
    return f'"{Path(sys.executable).as_posix()}" "{Path(__file__).resolve().as_posix()}"'


def hook_script():
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER}: blocks commits while RepoDx finds critical problems (leaked keys, .env files).\n"
        "# Skip it once with: git commit --no-verify\n"
        f'output=$({hook_command()} --fail-on critical "$(git rev-parse --show-toplevel)" 2>&1) || {{\n'
        '  echo "$output"\n'
        '  echo ""\n'
        '  echo "repodx: commit blocked because of critical findings above."\n'
        "  exit 1\n"
        "}\n"
    )


def install_hook(repo_path):
    hooks_dir = git_hooks_dir(repo_path)

    if hooks_dir is None:
        print(f"Error: {repo_path} is not inside a Git repository (or git is not installed).", file=sys.stderr)
        return 2

    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists() and HOOK_MARKER not in hook_path.read_text(encoding="utf-8", errors="replace"):
        print(f"A pre-commit hook already exists at {hook_path} and was not installed by RepoDx.")
        print(f"Add this line to it instead: {hook_command()} --fail-on critical .")
        return 1

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(hook_script(), encoding="utf-8")
    hook_path.chmod(0o755)
    print(f"Installed a pre-commit hook at {hook_path}")
    print("Commits are now blocked while RepoDx finds critical problems. Skip once with: git commit --no-verify")
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="repodx",
        description="Check a project for leaked secrets and repo hygiene problems before you push it.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Repository path to scan. Defaults to the current folder.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown", "prompt"],
        default="text",
        help="Output format. Defaults to text.",
    )
    parser.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        help="Shortcut for --format json.",
    )
    parser.add_argument(
        "--prompt",
        dest="format",
        action="store_const",
        const="prompt",
        help="Print a ready-to-paste prompt that tells your AI coding tool how to fix the findings.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe fixes (.gitignore entries, .env.example), then scan again.",
    )
    parser.add_argument(
        "--install-hook",
        action="store_true",
        help="Install a Git pre-commit hook that blocks commits with critical findings.",
    )
    parser.add_argument(
        "--fail-on",
        choices=SEVERITIES + ["never"],
        default="warning",
        help="Exit with code 1 when a finding of this severity or worse exists. Defaults to warning.",
    )
    parser.add_argument(
        "--badge",
        action="store_true",
        help="Print a README badge with your score instead of the report.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the score line for text output.",
    )
    parser.add_argument("--version", action="version", version=f"repodx {__version__}")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    repo_path = Path(args.path).resolve()

    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Error: path is not a directory: {repo_path}", file=sys.stderr)
        return 2

    if args.install_hook:
        return install_hook(repo_path)

    report = build_report(repo_path)
    fixes = None

    if args.fix:
        score_before = report["score"]
        changes, manual = apply_fixes(repo_path, report)
        report = build_report(repo_path)
        fixes = {"changes": changes, "manual": manual, "score_before": score_before}

    if args.badge:
        print(badge_markdown(report))
    elif args.format == "json":
        print(json.dumps(dict(report, fixes=fixes) if fixes else report, indent=2))
    elif args.format == "prompt":
        print(format_prompt(report))
    elif args.quiet and args.format == "text":
        print(format_quiet(report))
    else:
        if fixes:
            print(format_fix_summary(fixes, report) + "\n")

        if args.format == "markdown":
            print(format_markdown(report))
        else:
            print(format_text(report, color=use_color(sys.stdout)))

    return 1 if should_fail(report, args.fail_on) else 0


def cli():
    raise SystemExit(main())


if __name__ == "__main__":
    cli()

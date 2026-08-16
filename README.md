# RepoDx

RepoDx is a tiny command-line repository hygiene checker.

It scans a local folder and reports a few common cleanup issues:

- temporary files such as `.tmp` and `.log`
- Python cache folders such as `__pycache__/`
- `.DS_Store`
- `node_modules/` when it is not ignored
- missing or incomplete `.gitignore`
- missing README installation and usage sections

RepoDx is intentionally small. It does not try to compete with larger audit
tools that run dozens or hundreds of checks. The goal is a fast, readable
starter tool that can be understood by a beginner.

## Installation

Clone the repository and run it with Python:

```powershell
git clone https://github.com/omerbek/repodx.git
cd repodx
python repodx.py .
```

On macOS or Linux:

```bash
git clone https://github.com/omerbek/repodx.git
cd repodx
python3 repodx.py .
```

RepoDx uses only the Python standard library. No package installation is
required.

## Usage

Scan the current folder:

```powershell
python repodx.py .
```

On macOS or Linux:

```bash
python3 repodx.py .
```

Scan another folder:

```powershell
python repodx.py C:\path\to\project
```

On macOS or Linux:

```bash
python3 repodx.py /path/to/project
```

Example output:

```text
RepoDx report
Scanned path: C:\Users\omer\Desktop\githubprojem\sample_repo
Issues found: 9

Junk files
  - __pycache__/
  - cache.tmp
  - debug.log
  - node_modules/

.gitignore
  - Missing .gitignore entry: __pycache__/
  - Missing .gitignore entry: .env
  - Missing .gitignore entry: node_modules/

README
  - Missing README heading: Installation
  - Missing README heading: Usage
```

## Why This Exists

Many AI-assisted projects are created quickly, but their repositories often
keep generated files, local logs, or incomplete documentation. RepoDx gives a
small first-pass report before a project is shared.

## What RepoDx Does Not Do

RepoDx v0.1 does not scan for secrets or API keys. Mature tools such as
Gitleaks and TruffleHog already handle that job better. A future version may
call Gitleaks if it is installed.

RepoDx v0.1 also does not analyze unused dependencies. That problem is easy to
get wrong and is outside the first release.

## Development

The `sample_repo/` folder is intentionally broken. It is used by tests and by
the example report above.

Run the test suite:

```powershell
python -m unittest discover
```

On macOS or Linux:

```bash
python3 -m unittest discover
```

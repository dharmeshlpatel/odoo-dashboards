# Contributing Guidelines

Thank you for contributing! This project enforces strict code quality checks using `pre-commit`, `black`, and `flake8`.

Please follow the steps below before committing code.

---

## Install Project Dependencies

Before setting up `pre-commit`, install the required tools using the following command:

```bash
pip install -r requirements.txt
```

This ensures that the correct versions of `black` and `flake8` are used across all environments.

---

## Pre-Commit Setup

### One-Time Installation

Install `pre-commit` globally (only once per machine or virtual environment):

```bash
pip install pre-commit
```

---

### Repo Setup (One-Time per Repo)

After cloning the repo, run:

```bash
pre-commit install
```

This installs Git hooks that will automatically run checks **before each commit**.

---

### Run All Checks Manually (Optional)

You can manually trigger all pre-commit checks:

```bash
pre-commit run --all-files
```

---

## Tools Enforced

- **Black** – Formats Python code (PEP8 compliant)
- **Flake8** – Lints code for syntax, style, and logical issues

---

## Commit Rejection

If your commit violates rules, it will be blocked with detailed error messages.
- Fix the issues and try committing again.
- Contact the maintainer if you're unsure how to fix a rule.

---

Happy coding!
# Hooks

Local pre-commit hook scripts, registered in [`.pre-commit-config.yaml`](../.pre-commit-config.yaml)
at the repo root.

## Hook Scripts

```
hooks/
├── check_docstrings.py
├── check_local_variable_placement.py
├── check_requirements_up_to_date.py
└── notebook_utils.py
```

- `check_docstrings.py` — fails if a function (`.py` or `.ipynb`) is missing a docstring with a
  description, `args:`, and `returns:` section, or if a docstring/comment line exceeds the length limit.
- `check_local_variable_placement.py` — fails if a function declares local variable assignments
  after other statements instead of at the top of the function body.
- `check_requirements_up_to_date.py` — fails if `.venv` is missing a package declared in
  `requirements.txt`, or has a version that doesn't satisfy its pin.
- `notebook_utils.py` — shared helper to extract Python source from `.ipynb` code cells, used by
  the two AST-based checkers above.

## Pre-commit Checks

Pre-commit runs automatically on every `git commit`. It checks:
- ✅ Trailing whitespace
- ✅ End-of-file formatting
- ✅ YAML and JSON syntax
- ✅ Python code with Black (formatting)
- ✅ Python linting with Flake8
- ✅ Function docstrings: required description, `args:`, and `returns:` sections (`.py` and `.ipynb`)
- ✅ Line length in comments and code (`.ipynb` cells, complements Flake8 for notebooks)
- ✅ Local variable declarations at the top of functions (`.py` and `.ipynb`)
- ✅ `.venv` satisfies every package/pin declared in `requirements.txt`
- ✅ Notebook outputs stripped before committing (`nbstripout`)

### Run Pre-commit Manually

To check all files before committing:

```bash
pre-commit run --all-files
```

To check only staged files:

```bash
pre-commit run
```

# dataform-sqlx-linter

A linter for **Dataform SQLX** files that enforces project coding standards:
- non-empty **table descriptions**
- explicit **schemas** (for `view`, `table`, `incremental`)
- non-empty **column descriptions**

Designed to run locally and in **GitHub Actions**.

---

## Features

- ✅ Single entry point to **run all or selected checks**
- ✅ **Include/Exclude** checks via CLI, env, or config (YAML/JSON)
- ✅ Clear, CI-friendly output + proper exit codes
- ✅ Well-factored code with tests

---

## Requirements

- Python **3.10+**
- Optional: **PyYAML** if you want YAML config files

---

## Install

### Local (editable dev install)

```bash
# from repo root
python -m pip install -e .[dev]
# or, if you don’t want the dev extras:
# python -m pip install -e .
```

> The `[dev]` extra typically includes `pytest`, `ruff`, `mypy`, and `pyyaml`.

If you prefer a minimal install but still want YAML config support:

```bash
python -m pip install -e .[yaml]
```

---

## CLI usage

The package exposes a console script:

```bash
dataform-sqlx-linter path/to/file1.sqlx path/to/file2.sqlx
```

Or via module:

```bash
python -m dataform_sqlx_linter path/to/file1.sqlx path/to/file2.sqlx
```

### Options

- `--include <csv>`: run only these checks (e.g. `description,columns`)
- `--exclude <csv>`: skip these checks (e.g. `schema`)
- `--config <path>`: YAML or JSON config file (see below)
- `--fail-fast`: stop on first failing check

### Examples

Run all checks on 3 files:

```bash
dataform-sqlx-linter defs/a.sqlx defs/b.sqlx defs/c.sqlx
```

Only run description + columns:

```bash
dataform-sqlx-linter --include description,columns defs/a.sqlx
```

Skip schema:

```bash
dataform-sqlx-linter --exclude schema defs/a.sqlx defs/b.sqlx
```

Fail fast:

```bash
dataform-sqlx-linter --fail-fast defs/a.sqlx defs/b.sqlx
```

Use env vars instead of flags:

```bash
CHECKS_INCLUDE=description,columns dataform-sqlx-linter defs/a.sqlx
```

---

## Config file

You can configure include/exclude/fail-fast in YAML or JSON.

**YAML** (`.github/dataform-checks.yml`)

```yaml
include: ["description", "schema", "columns"]
exclude: []
fail_fast: false
```

**JSON**

```json
{ "include": ["description", "columns"], "exclude": ["schema"], "fail_fast": true }
```

Precedence: **CLI > ENV > config file > defaults**.

---

## Checks (what they do)

- **description**  
  Requires non-empty `actionDescriptor.description`. Skips tables with `bigquery.labels.lifecycle_stage: draft`.

- **schema**  
  Parses each `.sqlx` file’s `config { ... }` block.  
  If `type` is present and **not** one of `view|table|incremental`, the file is **skipped**.  
  Otherwise requires an explicitly quoted `schema: "..."` (or `'...'`).

- **columns**  
  Requires a non-empty `actionDescriptor.columns` array and non-empty `description` per column.  
  Skips `lifecycle_stage: draft`.

- **hardcoded_fqns**  
  Looks for hardcoded fully qualified tables names in SQLX files (require `${ref()}` notation).

Exit code is **1** if any selected check reports failures, else **0**.

---

## GitHub Actions

### A) Use the console script directly

```yaml
name: Dataform SQLX Linter

on:
  pull_request:

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # (optional) gather changed files similar to your existing workflow
      - name: Compute changed SQLX files
        id: changed
        run: |
          git fetch origin ${{ github.base_ref }} ${{ github.head_ref }}
          CHANGED=$(git diff --name-only origin/${{ github.base_ref }}...origin/${{ github.head_ref }} | grep '\.sqlx$' | paste -sd,)
          echo "files=$CHANGED" >> "$GITHUB_OUTPUT"
          echo "Changed: $CHANGED"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install linter
        run: |
          python -m pip install --upgrade pip
          python -m pip install dataform-sqlx-linter[yaml]  # or: pip install -e . in your own repo

      - name: Run linter
        if: steps.changed.outputs.files != ''
        run: |
          IFS=',' read -ra FILES <<< "${{ steps.changed.outputs.files }}"
          dataform-sqlx-linter "${FILES[@]}"             --config .github/dataform-checks.yml
```

### A) (If you included the composite action in this repo)
Consumers can do:

```yaml
- name: Run Dataform SQLX Linter
  uses: your-org/dataform-sqlx-linter/.github/actions/run-checks@v1
  with:
    files: ${{ steps.changed.outputs.files }}
    # include: description,columns
    # exclude: schema
    # config: .github/dataform-checks.yml
    # fail-fast: "true"
```

---

## Running tests

From repo root:

```bash
# install dev deps
python -m pip install -e '.[dev]'

# run tests with same interpreter
python -m pytest
```

If you prefer not to install, add `pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = src
addopts = -q
```

…then:

```bash
pytest
```

---

## Local dev

- Reinstall after changes to packaging config:
  ```bash
  python -m pip install -e .
  ```
- Lint & type-check:
  ```bash
  ruff check .
  mypy src/
  ```

---

## License

MIT (or Apache-2.0). Add a `LICENSE` file at the repo root.

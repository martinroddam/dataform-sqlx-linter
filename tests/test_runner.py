import os
from pathlib import Path
import json
import textwrap

import dataform_sqlx_linter.runner as runner


def _stub_checks(monkeypatch, order=None, return_codes=None):
    """
    Replace runner.CHECKS with simple stub functions that:
      - append their name to `calls`
      - return a configured exit code (default 0)
    Optionally, enforce an execution order expectation by inspecting `calls`.
    """
    calls = []

    def make_check(name):
        rc = 0
        if return_codes and name in return_codes:
            rc = return_codes[name]

        def _fn(files):
            calls.append((name, tuple(files)))
            return rc

        return _fn

    fake = {
        "description": make_check("description"),
        "schema": make_check("schema"),
        "columns": make_check("columns"),
    }
    monkeypatch.setattr(runner, "CHECKS", fake, raising=True)
    return calls


def _run_cli(args, monkeypatch=None, env=None, cwd=None):
    """
    Helper to run runner.cli() with controlled env/cwd.
    """
    old_env = dict(os.environ)
    try:
        if env:
            os.environ.update(env)
        if cwd:
            old_cwd = os.getcwd()
            os.chdir(cwd)
        try:
            return runner.cli(args)
        finally:
            if cwd:
                os.chdir(old_cwd)
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_runs_all_by_default(monkeypatch):
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(["a.sqlx", "b.sqlx"])
    assert rc == 0
    # All three checks executed
    names = [n for (n, _) in calls]
    assert set(names) == {"description", "schema", "columns"}
    # Files are passed through to each check
    for _, files in calls:
        assert files == ("a.sqlx", "b.sqlx")


def test_include_only_some(monkeypatch):
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(["--include", "schema,columns", "x.sqlx"])
    assert rc == 0
    names = [n for (n, _) in calls]
    assert names.count("schema") == 1
    assert names.count("columns") == 1
    assert "description" not in names


def test_exclude_takes_effect(monkeypatch):
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(["--exclude", "schema", "x.sqlx"])
    assert rc == 0
    names = [n for (n, _) in calls]
    assert "schema" not in names
    assert set(names) == {"description", "columns"}


def test_fail_fast(monkeypatch):
    calls = _stub_checks(monkeypatch, return_codes={"schema": 1})
    # Order is alphabetical in runner (sorted(selected)) → columns, description, schema
    rc = _run_cli(["--fail-fast", "x.sqlx"])
    # Because fail-fast stops after first failing check (schema), but schema runs last alphabetically.
    assert rc == 1
    names = [n for (n, _) in calls]
    assert names == ["columns", "description", "schema"]


def test_unknown_names_warn_but_continue(monkeypatch, capsys):
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(["--include", "schema,notreal", "x.sqlx"])
    out, err = capsys.readouterr()
    assert "Unknown check in include" in err
    assert rc == 0
    names = [n for (n, _) in calls]
    assert names == ["schema"]


def test_config_file_yaml_precedence_overridden_by_cli(tmp_path: Path, monkeypatch, capsys):
    # YAML config selects columns only, but CLI includes description instead
    cfg = tmp_path / "cfg.yml"
    cfg.write_text(textwrap.dedent("""
        include: ["columns"]
        exclude: []
        fail_fast: false
    """).strip(), encoding="utf-8")

    calls = _stub_checks(monkeypatch)
    rc = _run_cli(
        ["--config", str(cfg), "--include", "description", "file.sqlx"]
    )
    out, err = capsys.readouterr()
    assert rc == 0
    names = [n for (n, _) in calls]
    assert names == ["description"]  # CLI include overrides file include


def test_config_file_json_used_when_yaml_not_installed(tmp_path: Path, monkeypatch, capsys):
    # Use JSON config; select only 'schema'
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"include": ["schema"]}), encoding="utf-8")

    calls = _stub_checks(monkeypatch)
    rc = _run_cli(["--config", str(cfg), "file.sqlx"])
    assert rc == 0
    names = [n for (n, _) in calls]
    assert names == ["schema"]


def test_env_vars_override_config_but_not_cli(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"include": ["columns"]}), encoding="utf-8")

    # ENV overrides file → include 'schema'
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(
        ["--config", str(cfg), "file.sqlx"],
        env={"CHECKS_INCLUDE": "schema"},
    )
    assert rc == 0
    assert [n for (n, _) in calls] == ["schema"]

    # CLI still overrides ENV
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(
        ["--config", str(cfg), "--include", "description", "file.sqlx"],
        env={"CHECKS_INCLUDE": "schema"},
    )
    assert rc == 0
    assert [n for (n, _) in calls] == ["description"]


def test_excluding_everything_results_in_no_checks_selected(monkeypatch, capsys):
    calls = _stub_checks(monkeypatch)
    rc = _run_cli(["--exclude", "schema,description,columns", "file.sqlx"])
    out, err = capsys.readouterr()
    assert rc == 0
    assert "No checks selected" in err
    assert calls == []


def test_fail_fast_stops_early(monkeypatch):
    # Make columns fail; ensure description does NOT run when fail-fast is enabled,
    # given alphabetical order: columns, description, schema.
    calls = _stub_checks(monkeypatch, return_codes={"columns": 1})
    rc = _run_cli(["--fail-fast", "file.sqlx"])
    assert rc == 1
    names = [n for (n, _) in calls]
    assert names == ["columns"]  # stopped before description/schema


def test_files_are_passed_in_exactly(monkeypatch):
    calls = _stub_checks(monkeypatch)
    files = ["defs/a.sqlx", "defs/b.sqlx", "defs/c.sqlx"]
    rc = _run_cli(files)
    assert rc == 0
    for _, f in calls:
        assert f == tuple(files)

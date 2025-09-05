from pathlib import Path
import os
import pytest

from dataform_sqlx_linter.checks.schema import run as run_schema


@pytest.fixture
def write_sqlx(tmp_path: Path):
    def _write(name: str, body: str) -> Path:
        p = tmp_path / name
        p.write_text(body, encoding="utf-8")
        return p
    return _write


def run_in_tmp(tmp_path: Path, files):
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        return run_schema([str(f) for f in files])
    finally:
        os.chdir(old)


def test_pass_with_explicit_schema_and_type_table(write_sqlx, tmp_path):
    f = write_sqlx(
        "ok_table.sqlx",
        """
        config {
          type: "table",
          schema: "analytics"
        }
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 0


def test_pass_with_unquoted_type_incremental(write_sqlx, tmp_path):
    f = write_sqlx(
        "ok_incremental.sqlx",
        """
        config {
          type: incremental,
          schema: "core"
        }
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 0


def test_fail_missing_schema_for_view(write_sqlx, tmp_path):
    f = write_sqlx(
        "missing_schema.sqlx",
        """
        config {
          type: "view"
          // schema intentionally missing
        }
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 1


def test_fail_empty_schema_for_incremental(write_sqlx, tmp_path):
    f = write_sqlx(
        "empty_schema.sqlx",
        """
        config {
          type: "incremental",
          schema: "   "
        }
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 1


def test_skip_for_non_relevant_type(write_sqlx, tmp_path, capsys):
    f = write_sqlx(
        "skip_assertion.sqlx",
        """
        config {
          type: "assertion"
          // no schema on purpose
        }
        select 1;
        """,
    )
    rc = run_in_tmp(tmp_path, [f])
    out, err = capsys.readouterr()
    assert rc == 0
    assert "Skipped skip_assertion.sqlx (type is 'assertion')" in out


def test_fail_missing_config_block(write_sqlx, tmp_path):
    f = write_sqlx(
        "no_config.sqlx",
        """
        -- No config block here
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 1


def test_fail_malformed_config_block(write_sqlx, tmp_path):
    f = write_sqlx(
        "malformed_config.sqlx",
        """
        config {
          type: "table",
          schema: "broken"
        -- missing closing brace on purpose
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 1


def test_fail_when_schema_is_commented_out(write_sqlx, tmp_path):
    f = write_sqlx(
        "commented_schema.sqlx",
        """
        config {
          type: "table",
          /* schema: "should_not_count" */
          // schema: "also_should_not_count"
        }
        select 1;
        """,
    )
    assert run_in_tmp(tmp_path, [f]) == 1


def test_multiple_files_mixed_results(write_sqlx, tmp_path):
    good = write_sqlx(
        "good.sqlx",
        """
        config { type: "table", schema: "valid" }
        select 1;
        """,
    )
    bad = write_sqlx(
        "bad.sqlx",
        """
        config { type: "view" }
        select 1;
        """,
    )
    skipped = write_sqlx(
        "skipped.sqlx",
        """
        config { type: "declaration" }
        select 1;
        """,
    )
    # Overall should fail because of `bad.sqlx`
    assert run_in_tmp(tmp_path, [good, bad, skipped]) == 1
